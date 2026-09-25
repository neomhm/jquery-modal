"""
calibrate.py - stage "calibrate" (section 21).

    py calibrate.py pilot

1. Temperature T: the value in [0.5, 3.0] (step 0.05) that minimizes the
   negative log-likelihood of the true token labels on dev_heldout. The
   token logits are divided by T before the softmax, so scores mean what
   they say ("0.9" is right about 9 times in 10).
2. Thresholds: for each span type, the smallest tau in {0.30, 0.35, ...,
   0.95} that gives strict precision >= 0.97 on dev_heldout with at least
   10 predicted spans; if no tau reaches 0.97, the tau with the best F1.
   A span is 'accepted' when its score >= the threshold of its type.
3. Writes runs/<preset>/calibration.json and model_eval.pt: the complete,
   self-contained model file (weights, tokenizer, labels, temperature,
   thresholds) that evaluate.py and export use.
"""
import datetime
import json
import sys

import numpy as np
import torch

import config
import finetune as FT
from gen import holdout as H
import model as M
import pack
from extractor import predict

TEMPS = [round(0.5 + 0.05 * k, 2) for k in range(51)]
TAUS = [round(0.30 + 0.05 * k, 2) for k in range(14)]


@torch.inference_mode()
def fit_temperature(net, preset, max_len, batch_tokens=16000):
    """-> (best T, {T: NLL})."""
    data = pack.load_split(preset, "dev_heldout")
    device = next(net.parameters()).device
    order = sorted(range(len(data["ids"])), key=lambda i: len(data["ids"][i]))
    nll = np.zeros(len(TEMPS))
    count = 0
    temps = torch.tensor(TEMPS).view(-1, 1, 1)
    k = 0
    while k < len(order):
        batch = []
        longest = 0
        while k < len(order):
            i = order[k]
            n = min(len(data["ids"][i]), max_len)
            if batch and max(longest, n) * (len(batch) + 1) > batch_tokens:
                break
            batch.append(i)
            longest = max(longest, n)
            k += 1
        rows = [(np.asarray(data["ids"][i][:max_len], dtype=np.int64),
                 np.asarray(data["labels"][i][:max_len], dtype=np.int64),
                 0, 0) for i in batch]
        ids, keep, labels, _, _ = FT.to_tensors(rows, device)
        logits = net.token_logits(net(ids, keep)).float().cpu()
        labels = labels.cpu()
        mask = labels != -100
        if not mask.any():
            continue
        lg = logits[mask]                              # (N, K)
        gold = labels[mask]                            # (N,)
        scaled = lg.unsqueeze(0) / temps               # (T, N, K)
        lse = torch.logsumexp(scaled, dim=-1)          # (T, N)
        picked = scaled.gather(-1, gold.view(1, -1, 1).expand(
            len(TEMPS), -1, 1)).squeeze(-1)
        nll += (lse - picked).sum(dim=1).numpy()
        count += int(mask.sum())
    curve = {t: float(v / max(1, count)) for t, v in zip(TEMPS, nll)}
    best = min(curve, key=curve.get)
    return best, curve


def fit_thresholds(net, tokenizer, chunks, max_len, temperature):
    """-> ({type: tau}, {type: details})."""
    preds = predict(net, tokenizer, [c["text"] for c in chunks], max_len,
                    temperature=temperature)
    scored = {t: [] for t in config.TYPES}        # (score, correct)
    gold_count = {t: 0 for t in config.TYPES}
    for c, p in zip(chunks, preds):
        gold = {(s, e, lab) for s, e, lab in c["spans"]}
        for s, e, lab in gold:
            gold_count[lab] += 1
        for x in p["spans"]:
            scored[x["label"]].append(
                (x["score"], (x["start"], x["end"], x["label"]) in gold))
    thresholds, details = {}, {}
    for t in config.TYPES:
        rows = []
        for tau in TAUS:
            acc = [ok for sc, ok in scored[t] if sc >= tau]
            tp = sum(acc)
            prec = tp / len(acc) if acc else 0.0
            rec = tp / gold_count[t] if gold_count[t] else 0.0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            rows.append((tau, len(acc), prec, rec, f1))
        ok = [r for r in rows if r[2] >= 0.97 and r[1] >= 10]
        if ok:
            chosen, rule = ok[0], "precision>=0.97"
        else:
            chosen, rule = max(rows, key=lambda r: (r[4], -r[0])), "best F1"
        thresholds[t] = chosen[0]
        details[t] = {"tau": chosen[0], "rule": rule, "predicted": chosen[1],
                      "precision": round(chosen[2], 4),
                      "recall": round(chosen[3], 4), "f1": round(chosen[4], 4),
                      "gold": gold_count[t]}
    return thresholds, details


def run(preset, log=print):
    out = config.runs_dir(preset)
    # the GPU when there is one (much faster on the full preset)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net, tokenizer_json, meta = M.load(str(out / "finetune_best.pt"), device)
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_str(tokenizer_json)
    max_len = meta.get("max_len") or net.config.max_len
    temperature, curve = fit_temperature(net, preset, max_len)
    log("temperature %.2f (NLL %.4f; at 1.0: %.4f)" % (
        temperature, curve[temperature], curve[1.0]))
    dev = FT.read_split(preset, "dev_heldout")
    thresholds, details = fit_thresholds(net, tokenizer, dev, max_len,
                                         temperature)
    log("thresholds: %s" % {k: v for k, v in thresholds.items()})
    calib = {"temperature": temperature, "nll_curve": curve,
             "thresholds": thresholds, "details": details}
    with open(out / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=1)
    meta = dict(meta)
    meta.update(model_meta(preset))
    meta.update({"stage": "calibrated", "temperature": temperature,
                 "thresholds": thresholds, "max_len": max_len})
    M.save(out / "model_eval.pt", net, tokenizer_json, meta)
    return {"temperature": temperature,
            "thresholds_at_097": sum(1 for d in details.values()
                                     if d["rule"] == "precision>=0.97"),
            "types": len(details)}


def model_meta(preset):
    """The export meta of section 21 (the evaluation numbers are added
    by the export stage)."""
    out = config.runs_dir(preset)
    meta = {"version": config.VERSION, "preset": preset,
            "created": datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="seconds"),
            "labels": config.LABELS, "types": config.TYPES,
            "doc_types": config.DOC_TYPES, "langs": config.LANGS,
            "generator_version": config.GENERATOR_VERSION,
            "holdout_sha256": H.sha256()}
    rep = out / "tokenizer_report.json"
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        meta["boundary_rate"] = r["boundary_rate"]
    stats = config.corpus_dir(preset) / "corpus_stats.json"
    if stats.exists():
        s = json.loads(stats.read_text(encoding="utf-8"))
        meta["wikipedia"] = s.get("wiki")
        meta["wikipedia_chars"] = {k: v.get("chars", 0) for k, v in
                                   s.get("languages", {}).items()}
    else:
        meta["wikipedia"] = "not used"
    return meta


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "smoke")))
