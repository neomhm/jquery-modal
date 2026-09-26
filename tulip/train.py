"""
train.py - stage "train" (section 14).

    py train.py pilot

The model learns to write the program of a preview:
    sequence = preview [PROGRAM] program [END]
    loss     = next-token cross-entropy on the program and [END] only

Batches: sequences sorted by length inside buckets of 100 batches, filled
up to the preset's token budget (padding included). A batch is cut into
micro-batches of at most 16,000 tokens whose gradients add up (gradient
accumulation); on an out-of-memory error the micro-batches are halved
and their number doubled, and training goes on.

Optimizer AdamW (betas 0.9 / 0.95, eps 1e-8, weight decay 0.1 on the 2-D
weights except the embedding). Learning rate: linear warm-up over 2% of
the steps (at least 100), then linear decay to 10% of the peak.
Gradient clipping at 1.0. bf16 autocast when the GPU supports it, else
fp16 with a GradScaler; fp32 on the CPU.

Time cap: the first 20 steps are timed, then total steps = min(epochs x
steps per epoch, cap / time per step). Model selection: greedy execution
match on a fixed sample of min(1,000, all) dev_heldout tasks, every 15
minutes (pilot), every quarter epoch (full) or at the end (smoke); the
best checkpoint is kept as runs/<preset>/best.pt and training stops after
4 evaluations without improvement. Evaluation time does not count
towards the cap. A checkpoint is saved every 15 minutes; a stopped run
resumes from it.
"""
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch

import config
import model as M
import pack
import tok as TK

CHECKPOINT_EVERY = 15 * 60
EVAL_EVERY = 15 * 60
OUT_OF_MEMORY = getattr(torch, "OutOfMemoryError",
                        torch.cuda.OutOfMemoryError)


def device_and_precision():
    """-> (device, autocast dtype or None). fp32 on the CPU."""
    if torch.cuda.is_available():            # CUDA or ROCm
        dev = torch.device("cuda")
        if torch.cuda.is_bf16_supported():
            return dev, torch.bfloat16
        return dev, torch.float16
    return torch.device("cpu"), None


def model_config(preset, vocab_size):
    s = config.PRESETS[preset]
    return M.Config(vocab_size=vocab_size, d_model=s["d_model"],
                    n_layer=s["n_layer"], n_head=s["n_head"],
                    ffn_hidden=s["ffn_hidden"], max_len=s["max_len"],
                    dropout=s["dropout"])


def param_groups(net, weight_decay=0.1):
    """Weight decay on 2-D weights except the embedding; none on norms."""
    decay, plain = [], []
    for name, p in net.named_parameters():
        if p.dim() >= 2 and not name.startswith("embed"):
            decay.append(p)
        else:
            plain.append(p)
    return [{"params": decay, "weight_decay": weight_decay},
            {"params": plain, "weight_decay": 0.0}]


def lr_at(step, total, peak):
    """Linear warm-up over 2% of the steps (at least 100), then linear
    decay to 10% of the peak."""
    warmup = min(max(100, int(0.02 * total)), max(1, total // 2))
    if step < warmup:
        return peak * (step + 1) / warmup
    frac = (step - warmup) / max(1, total - warmup)
    return peak * (1.0 - 0.9 * min(1.0, frac))


def epoch_batches(lengths, tokens_per_batch, rng):
    """Index lists, one per batch: sorted by length inside buckets of 100
    batches, each filled up to the token budget (padding included)."""
    order = rng.permutation(len(lengths))
    mean = max(1.0, float(np.mean(lengths)))
    per_batch = max(1, int(tokens_per_batch // mean))
    bucket = 100 * per_batch
    batches = []
    for b0 in range(0, len(order), bucket):
        group = sorted(order[b0:b0 + bucket], key=lambda i: lengths[i])
        cur, cur_max = [], 0
        for i in group:
            n = int(lengths[i])
            if cur and max(cur_max, n) * (len(cur) + 1) > tokens_per_batch:
                batches.append(cur)
                cur, cur_max = [], 0
            cur.append(int(i))
            cur_max = max(cur_max, n)
        if cur:
            batches.append(cur)
    rng.shuffle(batches)
    return batches


def micro_batches(rows, parts):
    """Cut a batch into micro-batches of at most MICRO_TOKENS tokens
    (padding included), then into `parts` times more after an
    out-of-memory error."""
    out, cur, cur_max = [], [], 0
    for r in rows:
        n = len(r[0])
        if cur and max(cur_max, n) * (len(cur) + 1) > config.MICRO_TOKENS:
            out.append(cur)
            cur, cur_max = [], 0
        cur.append(r)
        cur_max = max(cur_max, n)
    if cur:
        out.append(cur)
    if parts > 1:
        finer = []
        for mb in out:
            size = max(1, math.ceil(len(mb) / parts))
            finer += [mb[k:k + size] for k in range(0, len(mb), size)]
        out = finer
    return out


def to_tensors(rows, device):
    n = max(len(a) for a, _ in rows)
    ids = torch.full((len(rows), n), TK.PAD, dtype=torch.long)
    labels = torch.full((len(rows), n), M.IGNORE, dtype=torch.long)
    for i, (a, b) in enumerate(rows):
        ids[i, :len(a)] = torch.from_numpy(np.asarray(a, dtype=np.int64))
        labels[i, :len(b)] = torch.from_numpy(np.asarray(b, dtype=np.int64))
    return ids.to(device), labels.to(device)


def forward_backward(net, rows, device, dtype, scaler, state, log):
    """Gradients of one batch, summed over its micro-batches so that the
    result equals one big batch: each micro-batch loss is weighted by its
    share of the batch's program tokens."""
    total = sum(int((np.asarray(b) != M.IGNORE).sum()) for _, b in rows)
    total = max(1, total)
    while True:
        parts = state.get("parts", 1)
        loss_sum = 0.0
        try:
            for mb in micro_batches(rows, parts):
                ids, labels = to_tensors(mb, device)
                count = int((labels[:, 1:] != M.IGNORE).sum())
                if count == 0:
                    continue
                with torch.autocast(device_type=device.type, dtype=dtype,
                                    enabled=dtype is not None):
                    loss = net.loss(ids, labels) * (count / total)
                if scaler:
                    scaler.scale(loss).backward()
                else:
                    loss.backward()
                loss_sum += float(loss.detach())
            return loss_sum
        except OUT_OF_MEMORY:
            net.zero_grad(set_to_none=True)
            if device.type == "cuda":
                torch.cuda.empty_cache()
            if parts >= 64:
                raise
            state["parts"] = parts * 2
            log("out of memory: micro-batches halved (%d parts)" %
                state["parts"])


def save_last(path, net, opt, state, preset):
    tmp = path.with_suffix(".tmp")
    torch.save({"state_dict": net.state_dict(),
                "optimizer": opt.state_dict(), "state": state,
                "preset_hash": config.preset_hash(preset)}, tmp)
    os.replace(tmp, path)


def run(preset, log=print):
    import evaluate as E
    s = config.PRESETS[preset]
    tr = s["train"]
    out = config.runs_dir(preset)
    device, dtype = device_and_precision()
    if device.type == "cpu":
        torch.set_num_threads(os.cpu_count() or 1)
    tokenizer = pack.load_tokenizer(preset)
    tokenizer_json = (out / "tokenizer.json").read_text(encoding="utf-8")
    cfg = model_config(preset, tokenizer.get_vocab_size())
    torch.manual_seed(0)
    net = M.Tulip(cfg).to(device)
    opt = torch.optim.AdamW(param_groups(net), lr=tr["lr"],
                            betas=(0.9, 0.95), eps=1e-8)
    scaler = torch.amp.GradScaler("cuda") if dtype == torch.float16 else None
    train = pack.Packed(preset, "train")
    lengths = train.lengths()
    per_epoch = len(epoch_batches(lengths, tr["tokens_per_batch"],
                                  np.random.default_rng(0)))
    dev = E.read_tasks(preset, "dev_heldout")
    sample = sorted(random.Random(0).sample(
        range(len(dev)), min(config.SELECTION_SAMPLE, len(dev))))
    dev_sample = [dev[i] for i in sample]
    state = {"step": 0, "total": None, "epoch": 0, "pos": 0,
             "train_seconds": 0.0, "evals": [], "best": None,
             "since_best": 0, "done": False, "per_epoch": per_epoch,
             "losses": []}
    last_path = out / "last.pt"
    if last_path.exists():
        blob = torch.load(last_path, map_location=device, weights_only=False)
        if blob.get("preset_hash") == config.preset_hash(preset):
            net.load_state_dict(blob["state_dict"])
            opt.load_state_dict(blob["optimizer"])
            state = blob["state"]
            log("resuming training at step %d" % state["step"])
    log("model: %d parameters (%d outside the embedding); %d sequences, "
        "%d batches per epoch; device %s" % (
            net.count()[0], net.count()[1], len(train), per_epoch,
            device.type))
    if not state["done"]:
        loop(preset, net, opt, scaler, dtype, device, train, lengths,
             dev_sample, tokenizer, tokenizer_json, state, last_path, log)
    best = torch.load(out / "best_weights.pt", map_location=device,
                      weights_only=False)
    net.load_state_dict(best)
    meta = {"version": config.VERSION, "preset": preset,
            "chosen_step": state["best"]["step"],
            "dev_sample_exec_match": state["best"]["score"]}
    M.save(out / "best.pt", net, tokenizer_json, meta)
    result = {"steps": state["step"], "total": state["total"],
              "per_epoch": per_epoch,
              "epochs": round(state["step"] / max(1, per_epoch), 3),
              "train_minutes": round(state["train_seconds"] / 60, 1),
              "evals": state["evals"], "chosen_step": state["best"]["step"],
              "dev_sample_exec_match": state["best"]["score"],
              "loss_curve": state["losses"],
              "parameters": net.count()[0],
              "parameters_outside_embedding": net.count()[1],
              "micro_batch_parts": state.get("parts", 1)}
    (out / "train_result.json").write_text(json.dumps(result, indent=1),
                                           encoding="utf-8")
    log("training done: step %d chosen, dev sample execution match %.4f" %
        (state["best"]["step"], state["best"]["score"]))
    return result


def loop(preset, net, opt, scaler, dtype, device, train, lengths,
         dev_sample, tokenizer, tokenizer_json, state, last_path, log):
    import evaluate as E
    s = config.PRESETS[preset]
    tr = s["train"]
    cap = (tr.get("minutes") or 0) * 60
    batches = epoch_batches(lengths, tr["tokens_per_batch"],
                            np.random.default_rng(1000 + state["epoch"]))
    net.train()
    t_start = time.time() - state["train_seconds"]
    eval_seconds = 0.0
    last_eval = time.time()
    last_ckpt = time.time()
    timing = None
    quarter = max(1, state["per_epoch"] // 4)
    loss_ema = None

    def elapsed():
        return time.time() - t_start - eval_seconds

    def select():
        nonlocal eval_seconds, last_eval
        t0 = time.time()
        net.eval()
        score = E.exec_match(net, tokenizer, dev_sample,
                             s["max_len"])["exec_match"]
        net.train()
        state["evals"].append({"step": state["step"],
                               "exec_match": round(score, 4),
                               "minutes": round(elapsed() / 60, 1)})
        log("dev sample execution match %.4f at step %d (%.0f s)" % (
            score, state["step"], time.time() - t0))
        if state["best"] is None or score > state["best"]["score"]:
            state["best"] = {"score": round(score, 4), "step": state["step"]}
            state["since_best"] = 0
            torch.save(net.state_dict(),
                       config.runs_dir(preset) / "best_weights.pt")
        else:
            state["since_best"] += 1
        eval_seconds += time.time() - t0
        last_eval = time.time()

    while True:
        step = state["step"]
        if state["total"] is not None and step >= state["total"]:
            break
        if cap and elapsed() >= cap:
            log("time cap reached at step %d" % step)
            break
        total = state["total"] or max(step + 1, tr.get("steps") or 1000)
        lr = lr_at(step, total, tr["lr"])
        for g in opt.param_groups:
            g["lr"] = lr
        if state["pos"] >= len(batches):
            state["epoch"] += 1
            state["pos"] = 0
            if tr.get("epochs") and state["epoch"] >= tr["epochs"] and \
                    not tr.get("steps"):
                log("epoch limit reached at step %d" % step)
                break
            batches = epoch_batches(lengths, tr["tokens_per_batch"],
                                    np.random.default_rng(1000 +
                                                          state["epoch"]))
        idx = batches[state["pos"]]
        state["pos"] += 1
        rows = [train.get(i) for i in idx]
        opt.zero_grad(set_to_none=True)
        loss = forward_backward(net, rows, device, dtype, scaler, state, log)
        if scaler:
            scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        if scaler:
            scaler.step(opt)
            scaler.update()
        else:
            opt.step()
        state["step"] = step + 1
        loss_ema = loss if loss_ema is None else 0.95 * loss_ema + 0.05 * loss
        if step == 0:
            timing = time.time()
        if state["total"] is None and state["step"] == 21:
            per_step = (time.time() - timing) / 20
            if tr.get("steps"):
                limit = tr["steps"]
            else:
                limit = state["per_epoch"] * (tr.get("epochs") or 1)
            by_time = int(cap / per_step) if cap else limit
            state["total"] = max(21, min(limit, by_time))
            log("%.2f s per step -> %d steps (%d per epoch)" % (
                per_step, state["total"], state["per_epoch"]))
        if state["step"] % 50 == 0:
            state["losses"].append([state["step"], round(loss_ema, 4)])
            log("step %d loss %.4f lr %.2e (%.1f min)" % (
                state["step"], loss_ema, lr, elapsed() / 60))
        due = False
        if tr["eval"] == "every_15_min" and time.time() - last_eval > \
                EVAL_EVERY:
            due = True
        if tr["eval"] == "quarter_epoch" and state["step"] % quarter == 0:
            due = True
        if due:
            select()
            if state["since_best"] >= 4:
                log("no improvement in 4 evaluations: stopping")
                break
        if time.time() - last_ckpt > CHECKPOINT_EVERY:
            state["train_seconds"] = elapsed()
            save_last(last_path, net, opt, state, preset)
            last_ckpt = time.time()
    state["train_seconds"] = elapsed()
    if not state["evals"] or state["evals"][-1]["step"] != state["step"]:
        select()
    state["done"] = True
    save_last(last_path, net, opt, state, preset)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "smoke"),
                     indent=1)[:4000])
