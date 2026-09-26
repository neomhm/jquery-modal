"""
pack.py - stages "tokenizer" and "pack" (sections 12 and 14).

    py pack.py pilot tokenizer     train the tokenizer on train previews
                                   and programs -> runs/<preset>/tokenizer.json
    py pack.py pilot pack          token arrays with labels
                                   -> runs/<preset>/.work/pack/<split>.npz

A training sequence is  preview [PROGRAM] program [END]; the labels are
-100 (ignored) on the preview and [PROGRAM], and the program's own tokens
on the program and [END] (model.training_pair). Tasks longer than the
preset's max_len are dropped from training and counted (section 8).

The tokenizer report: preview tokens per language (p50, p95, max), the
share of tasks over 4,096 tokens (MUST be <= 1%), and the round trip
decode(encode(program)) == NFKC(program) for every val program (MUST be
100%).
"""
import array
import json
import sys
import unicodedata

import numpy as np

import config
import model as M
import tok as TK
from gen.make import iter_split

LIMIT = 4096


def train_tokenizer(preset, log=print):
    out = config.runs_dir(preset)
    out.mkdir(parents=True, exist_ok=True)
    def texts():
        # one task at a time: a whole split in memory can be gigabytes
        for t in iter_split(preset, "train"):
            yield t["preview"]
            yield t["program"]
    tok = TK.train_tokenizer(texts(), config.PRESETS[preset]["vocab_size"])
    (out / "tokenizer.json").write_text(tok.to_str(), encoding="utf-8")
    report = length_report(preset, tok, log)
    # the per-task counts (one per task: 421,000 at full size) stay in
    # memory for the caller's check 7; the file keeps the summary
    (out / "tokenizer_report.json").write_text(
        json.dumps(dict((k, v) for k, v in report.items()
                        if k != "token_counts"), indent=1,
                   ensure_ascii=False), encoding="utf-8")
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
        for t in iter_split(preset, split):
            n_prev = len(TK.encode(tok, t["preview"]))
            n = n_prev + len(TK.encode(tok, t["program"])) + 2
            counts[t["id"]] = n
            total += 1
            if total % 50000 == 0:
                log("tokenizer: %d tasks measured" % total)
            over += n > LIMIT
            if split == "train":
                per_lang.setdefault(t["lang"], []).append(n_prev)
    failed = 0
    n_val = 0
    for t in iter_split(preset, "val"):
        n_val += 1
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
        "round_trip": {"programs": n_val,
                       "failed": failed},
        "token_counts": counts}
    log("tokenizer: vocab %d, %d of %d tasks over %d tokens, round trip "
        "failures %d" % (report["vocab_size"], over, total, LIMIT, failed))
    return report


def pack_dir(preset):
    """In the hidden work folder: the /train page must not send back
    gigabytes of token arrays as if they were a model."""
    return config.work_dir(preset) / "pack"


def pack(preset, log=print):
    """Token arrays for train (and val, for the validation loss curve)."""
    tok = load_tokenizer(preset)
    max_len = config.PRESETS[preset]["max_len"]
    folder = pack_dir(preset)
    folder.mkdir(parents=True, exist_ok=True)
    stats = {}
    for split in ("train", "val"):
        # COMPACT ARRAYS, never Python lists: at full size (about 380
        # million tokens) a list of ints is ~36 bytes a token, far over the
        # /train unit's 12 GB; array('i') is 4. np.frombuffer shares the
        # memory, and savez writes it in chunks, so nothing is copied whole.
        ids_all, lab_all = array.array("i"), array.array("i")
        offsets, dropped = array.array("q", [0]), 0
        n_seen = 0
        for t in iter_split(preset, split):
            n_seen += 1
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
            if n_seen % 50000 == 0:
                log("pack %s: %d tasks read" % (split, n_seen))
        np.savez(folder / ("%s.npz" % split),
                 ids=np.frombuffer(ids_all, dtype=np.int32),
                 labels=np.frombuffer(lab_all, dtype=np.int32),
                 offsets=np.frombuffer(offsets, dtype=np.int64))
        stats[split] = {"sequences": len(offsets) - 1, "dropped": dropped,
                        "tokens": len(ids_all)}
        log("pack %s: %d sequences, %d tokens, %d too long (dropped)" % (
            split, len(offsets) - 1, len(ids_all), dropped))
        del ids_all, lab_all, offsets       # freed before the next split
    return stats


class Packed:
    """A packed split: sequence i is ids[offsets[i]:offsets[i+1]]."""

    def __init__(self, preset, split):
        blob = np.load(pack_dir(preset) / ("%s.npz" % split))
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
