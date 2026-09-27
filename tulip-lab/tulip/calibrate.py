"""
calibrate.py - the confidence bands' thresholds for one model file
(Tulip 1.1, item C).

    py calibrate.py tulip-1.0.0.pt
    py calibrate.py tulip-1.0.0.pt --tasks 1000 --workers 2

A model built by Tulip 1.1's build.py carries its calibration (the
evaluation fits it on dev_heldout and measures it on test_heldout). A
model file made before - Tulip 1 - has none, and then no column is ever
"sure". This command gives it one, without changing the model file:

  1. it draws --tasks held-out tasks (the split dev_heldout: layouts,
     headers and activities never trained on) with the generator;
  2. it imports each with the candidate loop and the bands' signals, and
     checks every mapped column against the task's truth;
  3. it fits the thresholds on the even-numbered tasks - "sure" is the
     lowest score from which the columns are right at least 99% of the
     time (the one-sided 95% lower bound of the share), and it MEASURES
     them on the odd-numbered tasks, which the fit never saw;
  4. it writes <model>.confidence.json next to the model file (the
     thresholds, the measured rates, and the sha256 of the model file,
     so the thresholds are never used for another model).

Time: every task writes 8 programs (the greedy one and 7 sampled ones)
and scores one. Measured for the pilot model (d_model 256, 6 layers) on
a 4-core CPU with 4 processes: 100 tasks in 214 s, so about 70 minutes
for the default 2,000. The Tulip 1 model is larger (d_model 512, 8
layers) and was not timed. On a GPU it uses 2 processes.
"""
import argparse
import datetime
import json
import pathlib
import sys
import time

import config  # noqa: F401  (vendor/ on the path)
import confidence as C

HERE = pathlib.Path(__file__).resolve().parent
SPLIT = "dev_heldout"


def pairs_of(per, keep=lambda rec: True):
    """[(score, right)] of every mapped column of the records kept."""
    return [(c["score"], bool(c["right"])) for rec in per if keep(rec)
            for c in rec.get("confidence", [])]


def index_of(rec):
    return int(rec["id"].rsplit("-", 1)[1])


def fit_and_measure(per, fit=lambda rec: index_of(rec) % 2 == 0,
                    check=lambda rec: index_of(rec) % 2 == 1):
    """-> (bands or None, {"fit": measure, "measured": measure})."""
    fit_pairs = pairs_of(per, fit)
    bands = C.calibrate(fit_pairs)
    return bands, {"fit": C.measure(fit_pairs, bands),
                   "measured": C.measure(pairs_of(per, check), bands)}


def draw_tasks(n, log=print, start=0):
    """n tasks of dev_heldout, by index from `start` (the same tasks on
    every machine: each is made from its split and index)."""
    from gen import tasks as T
    tasks, i, began = [], start, time.time()
    while len(tasks) < n and i < start + 3 * n:
        task, _ = T.make_task(SPLIT, i)
        i += 1
        if task:
            tasks.append(task)
        if len(tasks) % 200 == 0 and task:
            log("  drawn %d / %d tasks (%.0f s)" % (len(tasks), n,
                                                   time.time() - began))
    return tasks


def table(measured):
    """A small text table: band, columns, right, rate, lower bound."""
    lines = ["| band | columns | right | rate | 95% lower bound |",
             "|---|---|---|---|---|"]
    for band in C.BANDS:
        m = measured.get(band) or {}
        lines.append("| %s | %s | %s | %s | %s |" % (
            band, m.get("columns", 0), m.get("right", 0),
            "-" if m.get("rate") is None else "%.2f%%" % (100 * m["rate"]),
            "-" if m.get("low95") is None else
            "%.2f%%" % (100 * m["low95"])))
    return "\n".join(lines)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Calibrate the confidence "
                                 "bands of a Tulip model file")
    ap.add_argument("model")
    ap.add_argument("--tasks", type=int, default=2000,
                    help="held-out tasks to draw (default 2000: half fit "
                    "the thresholds, half measure them)")
    ap.add_argument("--workers", type=int,
                    help="processes (at most %d; 2 on a GPU)"
                    % config.MAX_WORKERS)
    args = ap.parse_args(argv)
    import evaluate as E
    model = pathlib.Path(args.model).resolve()
    if not model.exists():
        ap.error("no model file %s" % model)
    device = E.eval_device()
    workers = max(1, min(args.workers or config.workers(),
                         config.MAX_WORKERS,
                         E.GPU_WORKERS if device == "cuda" else
                         config.MAX_WORKERS))
    print("drawing %d %s tasks" % (args.tasks, SPLIT), flush=True)
    tasks = draw_tasks(args.tasks)
    print("importing them with %s (%d processes, %s)" % (
        model.name, workers, device), flush=True)
    per = E.evaluate_parallel(model, SPLIT, tasks, False, workers,
                              lambda m: print(m, flush=True), device,
                              confidence=True)
    bands, rates = fit_and_measure(per)
    out = {"model_file": model.name, "model_sha256": C.file_sha256(model),
           "score_version": C.SCORE_VERSION,
           "sure_target": C.SURE_PRECISION,
           "calibrated_on": {"split": SPLIT, "tasks": len(per),
                             "fit": "even task indexes",
                             "measured": "odd task indexes"},
           "fit": rates["fit"], "measured": rates["measured"],
           "made": datetime.datetime.now(datetime.timezone.utc)
           .isoformat(timespec="seconds")}
    if bands:
        out.update(bands)
    target = C.side_file(model)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False),
                      encoding="utf-8")
    print()
    if not bands:
        print("Too few right columns for a 'sure' band: this model never "
              "says 'sure'.")
    else:
        print("thresholds: sure >= %.4f, check >= %.4f" % (
            bands["sure"], bands["check"]))
    print("\nmeasured on the odd-numbered tasks (%d columns):" % sum(
        m["columns"] for m in rates["measured"].values()))
    print(table(rates["measured"]))
    print("\nwritten: %s" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
