"""
gen/make.py - make the synthetic data of a preset (section 10).

    py gen/make.py smoke                 data/smoke/<split>.jsonl.gz
    py gen/make.py pilot --check         ...then the self-checks (10.8)
    py gen/make.py pilot --check-only    only the self-checks
    py gen/make.py --draw-holdout        draw gen/holdout.json (once)

Every task is made from its (split, index) seed, so the same code and
data always give the same files. Tasks are made by several processes at
once (--workers, default and ceiling: config.MAX_WORKERS = 4).

Besides the task files, data/<preset>/stats.json records what happened:
tasks made, attempts, discards (self-check failures), duplicates dropped
from the evaluation splits, the real-file round trips...
"""
import argparse
import collections
import gzip
import hashlib
import json
import multiprocessing
import os
import pathlib
import shutil
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config                       # noqa: E402
from gen import data as D           # noqa: E402

ROUND_TRIP_EVERY = 100               # 1% of tasks: a real file (10.1)


def write_activities():
    """gen/data/activities.json: the 40 activities of Appendix J with
    every language's items (section 10.2) - rebuilt from
    activities_base.json and gen/data/<folder>/activities.json."""
    out = []
    for a in D.activities():
        a = dict(a)
        out.append(a)
    path = D.DATA / "activities.json"
    text = json.dumps({"activities": out}, ensure_ascii=False, indent=1)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------
#  one task, in a worker process
# ---------------------------------------------------------------------
_TMP = None


def _init(tmp):
    global _TMP
    _TMP = tmp


def make_one(job):
    """(split, index) -> dict with the task (or None) and its stats."""
    from gen import realfile
    from gen import sheetkit as K
    from gen import tasks as T
    split, index = job
    before = dict(K.VALUE_STATS)
    task, reasons = T.make_task(split, index)
    out = {"index": index, "task": task, "reasons": reasons,
           "values": K.VALUE_STATS["values"] - before["values"],
           "wrong": K.VALUE_STATS["wrong"] - before["wrong"],
           "round_trip": None}
    if task and index % ROUND_TRIP_EVERY == 0:
        folder = pathlib.Path(_TMP) / ("%s-%d" % (split, index))
        try:
            ok, detail = realfile.round_trip(task, folder)
        except Exception as e:                 # a file that cannot be
            ok, detail = False, "%s: %s" % (type(e).__name__, e)
        shutil.rmtree(folder, ignore_errors=True)
        out["round_trip"] = [ok, detail[:300]]
    return out


def preview_key(preview):
    return hashlib.sha1(preview.encode("utf-8")).hexdigest()


def make_split(preset, split, n, workers, train_keys, log):
    from gen import tasks as T
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    started = time.time()
    stats = {"requested": n, "made": 0, "failed": 0, "attempts": 0,
             "discards": 0, "declined": 0, "duplicates": 0,
             "values": 0, "wrong_values": 0, "round_trips": 0,
             "round_trip_failures": [], "reasons": collections.Counter()}
    keys = set()
    tmp = tempfile.mkdtemp(prefix="tulip-rt-")
    jobs = ((split, i) for i in range(n))
    # EACH TASK IS WRITTEN AS IT ARRIVES. Holding a whole split's results
    # before writing them (400,000 tasks at full size) does not fit in the
    # /train unit's 12 GB. imap keeps the order, so the file is the same.
    pool = None
    if workers > 1:
        pool = multiprocessing.Pool(workers, initializer=_init,
                                    initargs=(tmp,))
        results = pool.imap(make_one, jobs, chunksize=8)
    else:
        _init(tmp)
        results = (make_one(j) for j in jobs)
    every = max(1, min(5000, n // 20))
    tmp_path = path.with_suffix(".tmp")
    with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
        for k, r in enumerate(results):
            if (k + 1) % every == 0 or k + 1 == n:
                log("  %s: %d / %d tasks (%.0f s), progress %d%%" % (
                    split, k + 1, n, time.time() - started,
                    100 * (k + 1) // n))
            stats["attempts"] += len(r["reasons"]) + (1 if r["task"] else 0)
            for why in r["reasons"]:
                if T.is_discard(why):
                    stats["discards"] += 1
                else:
                    stats["declined"] += 1
                stats["reasons"][why] += 1
            stats["values"] += r["values"]
            stats["wrong_values"] += r["wrong"]
            if r["round_trip"] is not None:
                stats["round_trips"] += 1
                if not r["round_trip"][0]:
                    stats["round_trip_failures"].append(
                        [r["index"], r["round_trip"][1]])
            task = r["task"]
            if task is None:
                stats["failed"] += 1
                continue
            key = preview_key(task["preview"])
            if split == "train":
                train_keys.add(key)
            elif key in train_keys:
                stats["duplicates"] += 1     # section 11: dropped, logged
                continue
            keys.add(key)
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
            stats["made"] += 1
    if pool is not None:
        pool.close()
        pool.join()
    shutil.rmtree(tmp, ignore_errors=True)
    os.replace(tmp_path, path)
    stats["reasons"] = dict(stats["reasons"].most_common(30))
    stats["seconds"] = round(time.time() - started, 1)
    log("  %s: %d tasks, %d discards, %d duplicates dropped, %.0f s" % (
        split, stats["made"], stats["discards"], stats["duplicates"],
        stats["seconds"]))
    return stats


def iter_split(preset, split):
    """The tasks of a split one at a time (a split can be gigabytes)."""
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def read_split(preset, split):
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def make(preset, workers=None, log=print):
    from gen import tasks as T
    if not T.holdout():
        raise SystemExit("draw the hold-out groups first: "
                         "py gen/make.py --draw-holdout")
    write_activities()
    folder = config.data_dir(preset)
    folder.mkdir(parents=True, exist_ok=True)
    # never one process per core (config.workers(): at most 4)
    workers = max(1, min(workers or config.workers(), config.MAX_WORKERS))
    log("generating with %d processes" % workers)
    sizes = config.PRESETS[preset]["tasks"]
    all_stats = {"preset": preset, "generator": config.GENERATOR_VERSION,
                 "splits": {}}
    train_keys = set()
    started = time.time()
    for split in config.SPLITS:
        all_stats["splits"][split] = make_split(preset, split, sizes[split],
                                                workers, train_keys, log)
    all_stats["seconds"] = round(time.time() - started, 1)
    (folder / "stats.json").write_text(
        json.dumps(all_stats, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return all_stats


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("preset", nargs="?", choices=list(config.PRESETS))
    ap.add_argument("--check", action="store_true",
                    help="run the self-checks after making the data")
    ap.add_argument("--check-only", action="store_true",
                    help="only run the self-checks on existing data")
    ap.add_argument("--draw-holdout", action="store_true",
                    help="draw gen/holdout.json (done once)")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if args.draw_holdout:
        from gen import holdout
        print(holdout.draw())
        write_activities()
        return 0
    if not args.preset:
        ap.error("give a preset: smoke, pilot or full")
    if not args.check_only:
        make(args.preset, args.workers)
    if args.check or args.check_only:
        from gen import checks
        report = checks.run(args.preset)
        print(checks.format_report(report))
        return 0 if report["passed"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
