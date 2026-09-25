"""
pretrain.py - stage "pretrain" (section 9): masked language modelling.

    py pretrain.py pilot

The model reads windows of text in which 20% of the tokens are hidden
(mask_for_mlm of model.py) and learns to guess them. That teaches it the
ten languages before it ever sees a label.

Batches (9.4): windows of seq_len tokens at random places, 85% from
Wikipedia (the same share for each language) and 15% from the synthetic
train chunks. Without Wikipedia: 100% synthetic, balanced by language.

Schedule (9.5): AdamW (0.9, 0.98, eps 1e-6), weight decay 0.01 on 2-D
weights except the embedding table; linear warm-up over 3% of the steps
(at least 50), then linear decay to 10% of the peak; gradient clipping
at 1.0. fp32 on CPU; bf16 (or fp16 with a scaler) on a GPU.

Time cap (section 8): the first 20 steps are timed, then
total steps = min(steps of the preset, cap / time per step).

A checkpoint is saved every 15 minutes and at the end
(runs/<preset>/pretrain_last.pt); a restart resumes from it. On an
out-of-memory error the micro-batch is halved and the accumulation
doubled - the run never crashes for memory.
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

import config
import model as M
import tok as T

CHECKPOINT_EVERY = 15 * 60          # seconds
LOG_EVERY = 200                     # steps


# torch 2.4 has only the CUDA name of this error; later versions have both
OUT_OF_MEMORY = getattr(torch, "OutOfMemoryError",
                        torch.cuda.OutOfMemoryError)


def device_and_precision():
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        if torch.cuda.is_bf16_supported():
            return torch.device("cuda"), torch.bfloat16
        return torch.device("cuda"), torch.float16
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    return torch.device("cpu"), None


def model_config(preset, vocab_size):
    s = config.PRESETS[preset]
    return M.Config(vocab_size=vocab_size, d_model=s["d_model"],
                    n_layer=s["n_layer"], n_head=s["n_head"],
                    ffn_hidden=s["ffn_hidden"], max_len=s["max_len"],
                    dropout=s["dropout"], n_labels=len(config.LABELS),
                    n_doc_types=len(config.DOC_TYPES),
                    n_langs=len(config.LANGS))


def param_groups(net, weight_decay=0.01):
    """Weight decay on 2-D weights, except the embedding table; none on
    norms (and there are no biases)."""
    decay, no_decay = [], []
    for name, p in net.named_parameters():
        if p.ndim >= 2 and not name.startswith("embed."):
            decay.append(p)
        else:
            no_decay.append(p)
    return [{"params": decay, "weight_decay": weight_decay},
            {"params": no_decay, "weight_decay": 0.0}]


def lr_at(step, total, peak, warmup, floor=0.1):
    """Linear warm-up, then linear decay to floor x peak."""
    if step < warmup:
        return peak * (step + 1) / warmup
    frac = (step - warmup) / max(1, total - warmup)
    return peak * (1.0 - (1.0 - floor) * min(1.0, frac))


# ---------------------------------------------------------------------
#  where the windows come from
# ---------------------------------------------------------------------
class Sources:
    """Token arrays of the pack stage, and the rule for drawing windows."""

    def __init__(self, preset, rng):
        self.rng = rng
        pack = config.runs_dir(preset) / "pack"
        self.wiki, self.eval, self.syn = {}, {}, {}
        for lang in config.LANGS:
            for kind, store in (("wiki", self.wiki), ("wikieval", self.eval),
                                ("syn", self.syn), ("extra", self.wiki)):
                path = pack / ("%s_%s.npy" % (kind, lang))
                if path.exists():
                    arr = np.load(path, mmap_mode="r")
                    if arr.size > 16:
                        if kind == "extra" and lang in store:
                            store[lang] = np.concatenate([store[lang], arr])
                        else:
                            store[lang] = arr
        self.use_wiki = bool(self.wiki)

    def window(self, arr, seq_len):
        if arr.size <= seq_len:
            return np.asarray(arr, dtype=np.int64)
        o = int(self.rng.integers(0, arr.size - seq_len))
        return np.asarray(arr[o:o + seq_len], dtype=np.int64)

    def draw(self, seq_len):
        """One window: 85% Wikipedia (languages equal), 15% synthetic."""
        if self.use_wiki and self.rng.random() < 0.85:
            lang = self.rng.choice(sorted(self.wiki))
            return self.window(self.wiki[lang], seq_len)
        lang = self.rng.choice(sorted(self.syn))
        return self.window(self.syn[lang], seq_len)

    def eval_windows(self, seq_len, n, rng):
        pool = self.eval if self.eval else self.syn
        out = []
        langs = sorted(pool)
        for k in range(n):
            arr = pool[langs[k % len(langs)]]
            if arr.size <= seq_len:
                out.append(np.asarray(arr, dtype=np.int64))
            else:
                o = int(rng.integers(0, arr.size - seq_len))
                out.append(np.asarray(arr[o:o + seq_len], dtype=np.int64))
        return out


def make_batch(windows, device):
    n = max(len(w) for w in windows)
    ids = torch.full((len(windows), n), T.PAD, dtype=torch.long)
    keep = torch.zeros((len(windows), n), dtype=torch.bool)
    for i, w in enumerate(windows):
        ids[i, :len(w)] = torch.from_numpy(w)
        keep[i, :len(w)] = True
    return ids.to(device), keep.to(device)


def mlm_loss(net, ids, keep, vocab, generator, dtype):
    new, positions, targets = M.mask_for_mlm(ids, keep, vocab, rate=0.2,
                                             generator=generator)
    if positions.shape[0] == 0:
        return None, 0, 0
    with torch.autocast(device_type=ids.device.type, dtype=dtype,
                        enabled=dtype is not None):
        h = net(new, keep)
        logits = net.mlm_logits(h, positions).float()
    loss = F.cross_entropy(logits, targets)
    correct = int((logits.argmax(-1) == targets).sum())
    return loss, correct, int(targets.numel())


@torch.no_grad()
def masked_accuracy(net, sources, seq_len, device, dtype, vocab, batches=50,
                    batch_size=8):
    net.eval()
    rng = np.random.default_rng(123)
    gen = torch.Generator(device=device).manual_seed(123)
    right = total = 0
    loss_sum = 0.0
    for _ in range(batches):
        ids, keep = make_batch(sources.eval_windows(seq_len, batch_size, rng),
                               device)
        loss, c, n = mlm_loss(net, ids, keep, vocab, gen, dtype)
        if loss is not None:
            right += c
            total += n
            loss_sum += float(loss) * n
    net.train()
    return right / max(1, total), loss_sum / max(1, total)


# ---------------------------------------------------------------------
def run(preset, log=print):
    settings = config.PRESETS[preset]["pretrain"]
    out = config.runs_dir(preset)
    ckpt_path = out / "pretrain_last.pt"
    device, dtype = device_and_precision()
    tokenizer_json = (out / "tokenizer.json").read_text(encoding="utf-8")
    from tokenizers import Tokenizer
    vocab = Tokenizer.from_str(tokenizer_json).get_vocab_size()
    torch.manual_seed(0)
    net = M.Extractor(model_config(preset, vocab)).to(device)
    opt = torch.optim.AdamW(param_groups(net), lr=settings["lr"],
                            betas=(0.9, 0.98), eps=1e-6)
    scaler = torch.amp.GradScaler("cuda") if dtype == torch.float16 else None
    rng = np.random.default_rng(0)
    gen = torch.Generator(device=device).manual_seed(0)
    state = {"step": 0, "total": None, "warmup": 50, "micro": None,
             "seconds": 0.0, "done": False, "log": []}
    if ckpt_path.exists():
        blob = torch.load(ckpt_path, map_location=device, weights_only=False)
        if blob.get("preset_hash") == config.preset_hash(preset):
            net.load_state_dict(blob["state_dict"])
            opt.load_state_dict(blob["optimizer"])
            state = blob["state"]
            rng = np.random.default_rng(state["step"] + 1)
            log("resuming pretraining at step %d" % state["step"])
            if state["done"]:
                log("pretraining already finished")
                return state
    sources = Sources(preset, rng)
    log("pretraining %s: %.1fM parameters, device %s, wikipedia %s" % (
        preset, net.count()[0] / 1e6, device.type, sources.use_wiki))

    def shape_for(step, total):
        if settings.get("late_share") and total and \
                step >= total * (1 - settings["late_share"]):
            return settings["late_batch"], settings["late_seq_len"]
        return settings["batch"], settings["seq_len"]

    net.train()
    last_ckpt = time.time()
    # state["seconds"] is training time only: the time spent measuring
    # the masked accuracy does not count towards the cap (section 8)
    began = time.time() - state["seconds"]
    eval_seconds = 0.0
    cap = (settings.get("minutes") or 0) * 60
    timing_start = None

    def elapsed():
        return time.time() - began - eval_seconds

    while True:
        step = state["step"]
        total = state["total"]
        if total is not None and step >= total:
            break
        if cap and elapsed() >= cap:
            log("time cap reached at step %d" % step)
            break
        batch, seq_len = shape_for(step, total)
        micro = state["micro"] or batch
        lr = lr_at(step, total or max(step + 1, 1000), settings["lr"],
                   state["warmup"])
        for g in opt.param_groups:
            g["lr"] = lr
        try:
            opt.zero_grad(set_to_none=True)
            loss_total = 0.0
            accum = math.ceil(batch / micro)
            for _ in range(accum):
                ids, keep = make_batch([sources.draw(seq_len)
                                        for _ in range(micro)], device)
                loss, _, _ = mlm_loss(net, ids, keep, vocab, gen, dtype)
                if loss is None:
                    continue
                loss = loss / accum
                if scaler:
                    scaler.scale(loss).backward()
                else:
                    loss.backward()
                loss_total += float(loss.detach())
            if scaler:
                scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            if scaler:
                scaler.step(opt)
                scaler.update()
            else:
                opt.step()
        except OUT_OF_MEMORY:
            opt.zero_grad(set_to_none=True)
            if device.type == "cuda":
                torch.cuda.empty_cache()
            if micro == 1:
                raise                  # nothing smaller to try
            state["micro"] = max(1, micro // 2)
            log("out of memory: micro-batch %d -> %d" % (micro,
                                                          state["micro"]))
            continue
        state["step"] = step + 1
        # ---- the step count from the time cap (section 8)
        if step == 0:
            timing_start = elapsed()
        if state["total"] is None and state["step"] == 21:
            per_step = (elapsed() - timing_start) / 20
            limit = settings.get("steps") or 10 ** 9
            by_time = int(cap / per_step) if cap else limit
            state["total"] = max(21, min(limit, by_time))
            state["warmup"] = max(50, int(0.03 * state["total"]))
            state["seconds_per_step"] = per_step
            log("%.2f s per step -> %d steps (warm-up %d)" % (
                per_step, state["total"], state["warmup"]))
        if state["step"] % LOG_EVERY == 0 or state["step"] == 1:
            t0 = time.time()
            acc, eval_loss = masked_accuracy(net, sources, seq_len, device,
                                             dtype, vocab)
            eval_seconds += time.time() - t0
            entry = {"step": state["step"], "loss": round(loss_total, 4),
                     "eval_loss": round(eval_loss, 4),
                     "masked_accuracy": round(acc, 4), "lr": lr,
                     "minutes": round(elapsed() / 60, 1)}
            state["log"].append(entry)
            log("step %(step)d loss %(loss).3f eval %(eval_loss).3f "
                "masked acc %(masked_accuracy).3f" % entry)
        if time.time() - last_ckpt > CHECKPOINT_EVERY:
            state["seconds"] = elapsed()
            save(ckpt_path, net, opt, state, tokenizer_json, preset)
            last_ckpt = time.time()
    state["seconds"] = elapsed()
    acc, eval_loss = masked_accuracy(net, sources, shape_for(0, None)[1],
                                     device, dtype, vocab)
    state["final_masked_accuracy"] = round(acc, 4)
    state["final_eval_loss"] = round(eval_loss, 4)
    state["done"] = True
    state["wiki"] = sources.use_wiki
    save(ckpt_path, net, opt, state, tokenizer_json, preset)
    log("pretraining done: %d steps in %.1f min, masked accuracy %.3f" % (
        state["step"], state["seconds"] / 60, acc))
    return state


def save(path, net, opt, state, tokenizer_json, preset):
    tmp = path.with_suffix(".tmp")
    torch.save({"config": M.asdict(net.config),
                "state_dict": net.state_dict(),
                "optimizer": opt.state_dict(), "state": state,
                "tokenizer": tokenizer_json,
                "preset_hash": config.preset_hash(preset)}, tmp)
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run(sys.argv[1] if len(sys.argv) > 1 else "smoke")
    print(json.dumps({k: v for k, v in result.items() if k != "log"}))
