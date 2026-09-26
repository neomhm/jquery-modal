"""
pack.py - stages "tokenizer" and "pack" (sections 12 and 14).

    py pack.py pilot tokenizer     train the tokenizer on train previews
                                   and programs -> runs/<preset>/tokenizer.json
    py pack.py pilot pack          token arrays with labels
                                   -> runs/<preset>/pack/<split>.npz

A training sequence is  preview [PROGRAM] program [END]; the labels are
-100 (ignored) on the preview and [PROGRAM], and the program's own tokens
on the program and [END] (model.training_pair). Tasks longer than the
preset's max_len are dropped from training and counted (section 8).

The tokenizer report: preview tokens per language (p50, p95, max), the
share of tasks over 4,096 tokens (MUST be <= 1%), and the round trip
decode(encode(program)) == NFKC(program) for every val program (MUST be
100%).
"""
import json
import sys
import unicodedata

import numpy as np

import config
import model as M
import tok as TK
from gen.make import read_split

LIMIT = 4096


def train_tokenizer(preset, log=print):
    out = config.runs_dir(preset)
    out.mkdir(parents=True, exist_ok=True)
    train = read_split(preset, "train")
    texts = []
    for t in train:
        texts.append(t["preview"])
        texts.append(t["program"])
    tok = TK.train_tokenizer(texts, config.PRESETS[preset]["vocab_size"])
    (out / "tokenizer.json").write_text(tok.to_str(), encoding="utf-8")
    report = length_report(preset, tok, log)
    (out / "tokenizer_report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    if report["round_trip"]["failed"]:
        raise RuntimeError("tokenizer round trip failed for %d val programs"
                           % report["round_trip"]["failed"])
    if report["over_limit_share"] > 0.01:
        raise RuntimeError("%.2f%% of tasks are over %d tokens (max 1%%)" %
                           (100 * report["over_limit_share"], LIMIT))
    return report


def load_tokenizer(preset):
    from tokenizers import Tokenizer
    path = config.runs_dir(preset) / "tokenizer.json"
    return Tokenizer.from_str(path.read_text(encoding="utf-8"))


def pct(values, q):
    if not values:
        return 0
    return int(np.percentile(np.array(values), q))


def length_report(preset, tok, log=print):
    per_lang = {}
    counts = {}
    over = total = 0
    for split in config.SPLITS:
        for t in read_split(preset, split):
            n_prev = len(TK.encode(tok, t["preview"]))
            n = n_prev + len(TK.encode(tok, t["program"])) + 2
            counts[t["id"]] = n
            total += 1
            over += n > LIMIT
            if split == "train":
                per_lang.setdefault(t["lang"], []).append(n_prev)
    failed = 0
    for t in read_split(preset, "val"):
        ids = TK.encode(tok, t["program"])
        if TK.decode(tok, ids) != unicodedata.normalize("NFKC",
                                                        t["program"]):
            failed += 1
    report = {
        "vocab_size": tok.get_vocab_size(),
        "preview_tokens": dict((l, {"p50": pct(v, 50), "p95": pct(v, 95),
                                    "max": max(v)})
                               for l, v in sorted(per_lang.items())),
        "over_limit": over, "tasks": total,
        "over_limit_share": over / max(1, total),
        "round_trip": {"programs": len(read_split(preset, "val")),
                       "failed": failed},
        "token_counts": counts}
    log("tokenizer: vocab %d, %d of %d tasks over %d tokens, round trip "
        "failures %d" % (report["vocab_size"], over, total, LIMIT, failed))
    return report


def pack(preset, log=print):
    """Token arrays for train (and val, for the loss curve)."""
    tok = load_tokenizer(preset)
    max_len = config.PRESETS[preset]["max_len"]
    folder = config.runs_dir(preset) / "pack"
    folder.mkdir(parents=True, exist_ok=True)
    stats = {}
    for split in ("train", "val"):
        ids_all, lab_all, offsets, dropped = [], [], [0], 0
        for t in read_split(preset, split):
            prompt = TK.encode(tok, t["preview"])
            program = TK.encode(tok, t["program"])
            ids, labels = M.training_pair(prompt, program, TK.PROGRAM,
                                          TK.END)
            if len(ids) > max_len:
                dropped += 1                    # too long: dropped, counted
                continue
            ids_all.extend(ids)
            lab_all.extend(labels)
            offsets.append(len(ids_all))
        np.savez(folder / ("%s.npz" % split),
                 ids=np.array(ids_all, dtype=np.int32),
                 labels=np.array(lab_all, dtype=np.int32),
                 offsets=np.array(offsets, dtype=np.int64))
        stats[split] = {"sequences": len(offsets) - 1, "dropped": dropped,
                        "tokens": len(ids_all)}
        log("pack %s: %d sequences, %d tokens, %d too long (dropped)" % (
            split, len(offsets) - 1, len(ids_all), dropped))
    return stats


class Packed:
    """A packed split: sequence i is ids[offsets[i]:offsets[i+1]]."""

    def __init__(self, preset, split):
        blob = np.load(config.runs_dir(preset) / "pack" / ("%s.npz" % split))
        self.ids = blob["ids"]
        self.labels = blob["labels"]
        self.offsets = blob["offsets"]

    def __len__(self):
        return len(self.offsets) - 1

    def lengths(self):
        return np.diff(self.offsets)

    def get(self, i):
        a, b = self.offsets[i], self.offsets[i + 1]
        return self.ids[a:b], self.labels[a:b]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    preset, what = sys.argv[1], sys.argv[2]
    if what == "tokenizer":
        r = train_tokenizer(preset)
        r.pop("token_counts", None)
        print(json.dumps(r, indent=1))
    else:
        print(json.dumps(pack(preset), indent=1))
