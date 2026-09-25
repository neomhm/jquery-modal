"""
finetune.py - stage "finetune" (section 12): the model learns the labels.

    py finetune.py pilot

It starts from the pretraining checkpoint and trains three heads at once:
    loss = CE(token labels) + 0.3 x CE(document type) + 0.1 x CE(language)
Token labels of -100 are ignored: cut ranges (10.1), and the tokens of a
span that the edge of a random window cuts (chunks longer than max_len
are read through a random window each epoch).

Batches: chunks sorted by length inside buckets of 100 batches, cut to
the token budget of the preset (padding included), buckets shuffled. In
pilot and full, 10% of the batches are Wikipedia paragraphs whose token
and document labels are -100: they only train the language head.

Model selection: strict micro-F1 on a fixed sample of 2,000 dev_heldout
chunks, through the real decoding path (extractor.predict), with no
thresholds; every 15 minutes (pilot), every quarter epoch (full) or at
the end (smoke). The best checkpoint is kept; training stops after 4
evaluations without improvement. The best two are then compared once on
the whole dev_heldout, and the winner becomes finetune_best.pt.
Evaluation time does not count towards the time cap.
"""
import datetime
import gzip
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

import config
import model as M
import pack
import pretrain as P
from extractor import predict

CHECKPOINT_EVERY = 15 * 60


# ---------------------------------------------------------------------
#  data
# ---------------------------------------------------------------------
def window(ids, labels, max_len, rng):
    """A random window of max_len tokens. The tokens of a span cut by
    either edge of the window get label -100 (section 12)."""
    n = len(ids)
    if n <= max_len:
        return np.asarray(ids, dtype=np.int64), np.asarray(labels,
                                                           dtype=np.int64)
    start = int(rng.integers(0, n - max_len + 1))
    w_ids = np.asarray(ids[start:start + max_len], dtype=np.int64)
    lab = np.asarray(labels[start:start + max_len], dtype=np.int64)
    # left edge: the window starts inside a span (an I- label: even id)
    j = 0
    first = lab[0] if len(lab) else 0
    if first > 0 and first % 2 == 0:
        while j < len(lab) and lab[j] in (first, -100):
            lab[j] = -100
            j += 1
    # right edge: the span goes on after the window
    if start + max_len < n:
        nxt = int(labels[start + max_len])
        if nxt > 0 and nxt % 2 == 0:
            k = len(lab) - 1
            while k >= 0 and lab[k] in (nxt, nxt - 1, -100):
                was = lab[k]
                lab[k] = -100
                k -= 1
                if was == nxt - 1:          # reached the B- of the span
                    break
    return w_ids, lab


def epoch_batches(lengths, tokens_per_batch, max_len, rng):
    """Index lists, one per batch (section 12)."""
    order = rng.permutation(len(lengths))
    mean = max(1.0, float(np.mean(np.minimum(lengths, max_len))))
    per_batch = max(1, int(tokens_per_batch // mean))
    bucket = 100 * per_batch
    batches = []
    for b0 in range(0, len(order), bucket):
        group = sorted(order[b0:b0 + bucket],
                       key=lambda i: min(lengths[i], max_len))
        cur, cur_max = [], 0
        for i in group:
            length = min(lengths[i], max_len)
            if cur and max(cur_max, length) * (len(cur) + 1) > \
                    tokens_per_batch:
                batches.append(cur)
                cur, cur_max = [], 0
            cur.append(int(i))
            cur_max = max(cur_max, length)
        if cur:
            batches.append(cur)
    rng.shuffle(batches)
    return batches


def to_tensors(rows, device):
    """rows: [(ids, labels, doc, lang)] -> padded tensors."""
    n = max(len(r[0]) for r in rows)
    ids = torch.full((len(rows), n), 0, dtype=torch.long)
    labels = torch.full((len(rows), n), -100, dtype=torch.long)
    keep = torch.zeros((len(rows), n), dtype=torch.bool)
    for i, (a, b, _, _) in enumerate(rows):
        ids[i, :len(a)] = torch.from_numpy(a)
        labels[i, :len(b)] = torch.from_numpy(b)
        keep[i, :len(a)] = True
    doc = torch.tensor([r[2] for r in rows], dtype=torch.long)
    lang = torch.tensor([r[3] for r in rows], dtype=torch.long)
    return (ids.to(device), keep.to(device), labels.to(device),
            doc.to(device), lang.to(device))


def wiki_batch(sources, tokens_per_batch, max_len, rng):
    """Wikipedia windows: language labels only."""
    seq = min(512, max_len)
    n = max(1, tokens_per_batch // seq)
    rows = []
    langs = sorted(sources.wiki)
    for _ in range(n):
        lang = langs[int(rng.integers(0, len(langs)))]
        w = sources.window(sources.wiki[lang], seq)
        rows.append((w, np.full(len(w), -100, dtype=np.int64), -100,
                     config.LANGS.index(lang)))
    return rows


def ce(logits, target):
    """Cross-entropy that is 0 (not NaN) when every target is ignored."""
    count = int((target != -100).sum())
    if count == 0:
        return logits.sum() * 0.0
    return F.cross_entropy(logits, target, ignore_index=-100,
                           reduction="sum") / count


# ---------------------------------------------------------------------
#  evaluation through the real decoding path
# ---------------------------------------------------------------------
def read_split(preset, split):
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def strict_f1(net, tokenizer, chunks, max_len, batch_size=16):
    """Strict micro-F1 over all spans (no thresholds)."""
    net.eval()
    preds = predict(net, tokenizer, [c["text"] for c in chunks], max_len,
                    batch_size=batch_size)
    net.train()
    tp = n_pred = n_gold = 0
    for c, p in zip(chunks, preds):
        gold = {(s, e, lab) for s, e, lab in c["spans"]}
        got = {(x["start"], x["end"], x["label"]) for x in p["spans"]}
        tp += len(gold & got)
        n_pred += len(got)
        n_gold += len(gold)
    prec = tp / max(1, n_pred)
    rec = tp / max(1, n_gold)
    return 2 * prec * rec / max(1e-9, prec + rec)


# ---------------------------------------------------------------------
def run(preset, log=print):
    s = config.PRESETS[preset]
    ft = s["finetune"]
    out = config.runs_dir(preset)
    device, dtype = P.device_and_precision()
    from tokenizers import Tokenizer
    tokenizer_json = (out / "tokenizer.json").read_text(encoding="utf-8")
    tokenizer = Tokenizer.from_str(tokenizer_json)
    vocab = tokenizer.get_vocab_size()
    cfg = P.model_config(preset, vocab)
    max_len = cfg.max_len
    net = M.Extractor(cfg).to(device)
    pre = torch.load(out / "pretrain_last.pt", map_location=device,
                     weights_only=False)
    net.load_state_dict(pre["state_dict"])
    opt = torch.optim.AdamW(P.param_groups(net), lr=ft["lr"],
                            betas=(0.9, 0.98), eps=1e-6)
    scaler = torch.amp.GradScaler("cuda") if dtype == torch.float16 else None
    train = pack.load_split(preset, "train")
    lengths = np.array([len(x) for x in train["ids"]])
    rng = np.random.default_rng(1)
    sources = P.Sources(preset, np.random.default_rng(2))
    use_wiki = sources.use_wiki and preset != "smoke"
    dev = read_split(preset, "dev_heldout")
    sample_idx = sorted(random.Random(0).sample(range(len(dev)),
                                                min(2000, len(dev))))
    dev_sample = [dev[i] for i in sample_idx]
    per_epoch = len(epoch_batches(lengths, ft["tokens_per_batch"], max_len,
                                  np.random.default_rng(0)))
    if use_wiki:
        per_epoch = int(math.ceil(per_epoch / 0.9))
    state = {"step": 0, "total": None, "epoch": 0, "pos": 0,
             "train_seconds": 0.0, "evals": [], "best": [],
             "since_best": 0, "done": False, "per_epoch": per_epoch}
    last_path = out / "finetune_last.pt"
    if last_path.exists():
        blob = torch.load(last_path, map_location=device, weights_only=False)
        if blob.get("preset_hash") == config.preset_hash(preset):
            net.load_state_dict(blob["state_dict"])
            opt.load_state_dict(blob["optimizer"])
            state = blob["state"]
            log("resuming fine-tuning at step %d" % state["step"])
    if not state["done"]:
        train_loop(preset, net, opt, scaler, dtype, device, train, lengths,
                   sources, use_wiki, dev_sample, tokenizer, tokenizer_json,
                   state, last_path, log)
    return finish(preset, net, device, tokenizer, tokenizer_json, dev,
                  state, log)


def train_loop(preset, net, opt, scaler, dtype, device, train, lengths,
               sources, use_wiki, dev_sample, tokenizer, tokenizer_json,
               state, last_path, log):
    s = config.PRESETS[preset]
    ft = s["finetune"]
    max_len = s["max_len"]
    cap = (ft.get("minutes") or 0) * 60
    out = config.runs_dir(preset)
    rng = np.random.default_rng(100 + state["step"])
    batches = epoch_batches(lengths, ft["tokens_per_batch"], max_len,
                            np.random.default_rng(1000 + state["epoch"]))
    net.train()
    t_start = time.time() - state["train_seconds"]
    eval_seconds = 0.0
    last_eval = time.time()
    last_ckpt = time.time()
    timing = None
    quarter = max(1, state["per_epoch"] // 4)

    def elapsed():
        return time.time() - t_start - eval_seconds

    while True:
        step = state["step"]
        if state["total"] is not None and step >= state["total"]:
            break
        if cap and elapsed() >= cap:
            log("time cap reached at step %d" % step)
            break
        total = state["total"] or max(step + 1, 1000)
        warmup = max(1, int(0.05 * total))
        lr = P.lr_at(step, total, ft["lr"], warmup, floor=0.0)
        for g in opt.param_groups:
            g["lr"] = lr
        if use_wiki and rng.random() < 0.1:
            rows = wiki_batch(sources, ft["tokens_per_batch"], max_len, rng)
        else:
            if state["pos"] >= len(batches):
                state["epoch"] += 1
                state["pos"] = 0
                batches = epoch_batches(
                    lengths, ft["tokens_per_batch"], max_len,
                    np.random.default_rng(1000 + state["epoch"]))
            idx = batches[state["pos"]]
            state["pos"] += 1
            rows = []
            for i in idx:
                a, b = window(train["ids"][i], train["labels"][i], max_len,
                              rng)
                rows.append((a, b, int(train["doc"][i]),
                             int(train["lang"][i])))
        ids, keep, labels, doc, lang = to_tensors(rows, device)
        with torch.autocast(device_type=device.type, dtype=dtype,
                            enabled=dtype is not None):
            h = net(ids, keep)
            tok_logits = net.token_logits(h).float()
            doc_logits = net.doc_logits(h, keep).float()
            lang_logits = net.lang_logits(h, keep).float()
        loss = ce(tok_logits.reshape(-1, tok_logits.shape[-1]),
                  labels.reshape(-1)) + 0.3 * ce(doc_logits, doc) + \
            0.1 * ce(lang_logits, lang)
        opt.zero_grad(set_to_none=True)
        if scaler:
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
        else:
            loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        if scaler:
            scaler.step(opt)
            scaler.update()
        else:
            opt.step()
        state["step"] = step + 1
        if step == 0:
            timing = time.time()
        if state["total"] is None and state["step"] == 21:
            per_step = (time.time() - timing) / 20
            limit = ft.get("steps") or state["per_epoch"] * (
                ft.get("epochs") or 1)
            by_time = int(cap / per_step) if cap else limit
            state["total"] = max(21, min(limit, by_time))
            log("%.2f s per step -> %d steps (%d per epoch)" % (
                per_step, state["total"], state["per_epoch"]))
        if state["step"] % 100 == 0:
            log("step %d loss %.4f lr %.2e (%.1f min)" % (
                state["step"], float(loss.detach()), lr, elapsed() / 60))
        # ---- model selection
        due = False
        if ft["eval"] == "every_15_min" and time.time() - last_eval > 900:
            due = True
        if ft["eval"] == "quarter_epoch" and state["step"] % quarter == 0:
            due = True
        if due:
            t0 = time.time()
            if evaluate_and_keep(preset, net, tokenizer, dev_sample, state,
                                 log):
                pass
            eval_seconds += time.time() - t0
            last_eval = time.time()
            if state["since_best"] >= 4:
                log("no improvement in 4 evaluations: stopping")
                break
        if time.time() - last_ckpt > CHECKPOINT_EVERY:
            state["train_seconds"] = elapsed()
            save_last(last_path, net, opt, state, preset)
            last_ckpt = time.time()
    state["train_seconds"] = elapsed()
    evaluate_and_keep(preset, net, tokenizer, dev_sample, state, log)
    state["done"] = True
    save_last(last_path, net, opt, state, preset)


def evaluate_and_keep(preset, net, tokenizer, dev_sample, state, log):
    """Scores the current weights on the dev sample; keeps the best two
    on disk. Returns True when this is a new best."""
    out = config.runs_dir(preset)
    f1 = strict_f1(net, tokenizer, dev_sample,
                   config.PRESETS[preset]["max_len"])
    state["evals"].append({"step": state["step"], "f1": round(f1, 4)})
    log("dev sample strict F1 %.4f at step %d" % (f1, state["step"]))
    best = state["best"]                   # [(f1, step, file)], best first
    new_best = not best or f1 > best[0][0]
    state["since_best"] = 0 if new_best else state["since_best"] + 1
    if len(best) < 2 or f1 > best[-1][0]:
        name = "finetune_cand_%d.pt" % state["step"]
        torch.save(net.state_dict(), out / name)
        best.append((f1, state["step"], name))
        best.sort(key=lambda x: -x[0])
        for _, _, old in best[2:]:
            try:
                (out / old).unlink()
            except FileNotFoundError:
                pass
        del best[2:]
    return new_best


def save_last(path, net, opt, state, preset):
    tmp = path.with_suffix(".tmp")
    torch.save({"state_dict": net.state_dict(),
                "optimizer": opt.state_dict(), "state": state,
                "preset_hash": config.preset_hash(preset)}, tmp)
    os.replace(tmp, path)


def finish(preset, net, device, tokenizer, tokenizer_json, dev, state, log):
    """The best two checkpoints are compared once on the whole
    dev_heldout; the winner is saved as finetune_best.pt."""
    out = config.runs_dir(preset)
    max_len = config.PRESETS[preset]["max_len"]
    scores = []
    for f1_sample, step, name in state["best"]:
        net.load_state_dict(torch.load(out / name, map_location=device,
                                       weights_only=False))
        f1 = strict_f1(net, tokenizer, dev, max_len)
        scores.append((f1, step, name))
        log("checkpoint of step %d: dev_heldout strict F1 %.4f" % (step, f1))
    scores.sort(key=lambda x: -x[0])
    f1, step, name = scores[0]
    net.load_state_dict(torch.load(out / name, map_location=device,
                                   weights_only=False))
    meta = {"version": config.VERSION, "preset": preset,
            "stage": "finetune", "labels": config.LABELS,
            "types": config.TYPES, "doc_types": config.DOC_TYPES,
            "langs": config.LANGS, "max_len": max_len,
            "temperature": 1.0, "thresholds": None,
            "chosen_step": step, "dev_heldout_f1": round(f1, 4),
            "created": datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="seconds")}
    M.save(out / "finetune_best.pt", net, tokenizer_json, meta)
    result = {"steps": state["step"], "total": state["total"],
              "epochs": round(state["step"] / max(1, state["per_epoch"]), 3),
              "train_minutes": round(state["train_seconds"] / 60, 1),
              "evals": state["evals"], "chosen_step": step,
              "dev_heldout_f1": round(f1, 4)}
    log("fine-tuning done: step %d chosen, dev_heldout strict F1 %.4f" % (
        step, f1))
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "smoke")))
