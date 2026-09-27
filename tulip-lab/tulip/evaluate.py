"""
evaluate.py - stage "evaluate" (section 16).

    py evaluate.py pilot              every split, the handwritten files
                                      and real_eval/
    py evaluate.py pilot --dev-only   val and dev_heldout only (every
                                      improvement round)

For every task:
  * pass@1   the greedy program's output rows equal the truth rows (None
             values removed from both); for a refusal task, the greedy
             program refuses with the right reason
  * loop     the whole candidate loop of section 7.2 (tulip.Tulip):
             correct = imported rows equal the truth, or refused with the
             right reason; a false accept = imported rows that differ
Writes runs/<preset>/eval.json and runs/<preset>/eval_tables.md.

Test discipline (section 11): only AGGREGATE numbers are computed for
test_seen, test_heldout, test_locale, traps and the handwritten files.
Error examples are kept for val and dev_heldout only.
"""
import argparse
import collections
import gzip
import json
import pathlib
import statistics
import sys
import time

import numpy as np
import torch

import config
import contract
import sheets
import tulipscript as ts
from gen.tasks import sheet_from_task

HERE = pathlib.Path(__file__).resolve().parent
ERROR_SPLITS = ("val", "dev_heldout")        # the only ones read closely


def read_tasks(preset, split):
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def truth_rows(target, rows, fmt="tulipscript"):
    """The truth in the declared format of tables.schema.json, as the
    loop's rows are (contract.py). A task's truth and the handwritten
    truth.jsonl are written in Tulip's own field kinds ("tulipscript");
    a real_eval line says "truth_format": "contract" when its rows were
    copied from import_sheets.py --show."""
    if fmt == "contract" or target not in config.TARGETS:
        return clean(rows)
    return clean(contract.convert_rows(target, rows))


def clean(rows):
    return [dict((k, v) for k, v in r.items() if v is not None)
            for r in rows]


def refusal_of(program):
    """'refuse(\\'not_a_table\\')' -> 'not_a_table' (None if not one)."""
    try:
        prog = ts.parse(program)
    except Exception:
        return None
    return prog.refusal


def run_program(text, sheet, targets, locale):
    """-> (rows or None, refusal or None). Never raises."""
    import helpers as H
    try:
        prog = ts.parse(text)
    except Exception:
        return None, None
    if prog.refusal:
        return None, prog.refusal
    try:
        res = ts.run(prog, sheet, H.HELPERS, locale, targets, H.TOTALS)
    except Exception:
        return None, None
    return clean(res.rows), None


def pass_at_1(task, program, sheet):
    answer_refusal = refusal_of(task["program"])
    rows, refusal = run_program(program, sheet, task["targets"],
                                task["locale"])
    if answer_refusal:
        return refusal == answer_refusal
    return refusal is None and rows is not None and \
        rows == clean(task["truth"])


def exec_match(net, tokenizer, tasks, max_len):
    """Greedy execution match (model selection, section 14)."""
    from tulip import Tulip
    runner = Tulip.from_model(net, tokenizer)
    good = 0
    for t in tasks:
        sheet = sheet_from_task(t)
        if not runner.fits(t["preview"]):
            continue
        program = runner._write(t["preview"], 0, greedy_only=True)[0]
        good += pass_at_1(t, program, sheet)
    return {"exec_match": good / max(1, len(tasks)), "tasks": len(tasks)}


# ---------------------------------------------------------------------
#  error groups (section 22) - val and dev_heldout only
# ---------------------------------------------------------------------
def error_group(task, greedy, loop):
    truth = task["program"]
    try:
        want = ts.parse(truth)
    except Exception:
        return "bad_truth"
    try:
        got = ts.parse(greedy)
    except Exception:
        return "unparsable_program"
    if want.refusal or got.refusal:
        if want.refusal and got.refusal:
            return "wrong_refusal"
        return "wrong_refusal" if want.refusal else "refused_importable"
    if want.target != got.target:
        return "wrong_target"
    if want.header != got.header:
        return "wrong_header_row"
    if sorted(map(repr, want.keeps)) != sorted(map(repr, got.keeps)):
        return "missing_filter" if len(got.keeps) < len(want.keeps) \
            else "wrong_filter"
    if bool(want.sections) != bool(got.sections) or \
            (want.unpivot or []) != (got.unpivot or []):
        return "wrong_layout"
    import ast
    w_expr, g_expr = dict(want.outs), dict(got.outs)
    if set(w_expr) - set(g_expr):
        return "missing_field"
    if set(g_expr) - set(w_expr):
        return "extra_field"
    for f in w_expr:
        if ast.unparse(w_expr[f]) != ast.unparse(g_expr[f]):
            same_letters = sorted(ts._letters_in(w_expr[f])) == \
                sorted(ts._letters_in(g_expr[f]))
            return "wrong_helper" if same_letters else "wrong_column"
    if loop.get("status") == "needs_review":
        return "needs_review"
    return "same_program_other"


# ---------------------------------------------------------------------
#  one split
# ---------------------------------------------------------------------
def evaluate_split(runner, split, tasks, keep_examples, log,
                   confidence=False):
    """confidence: also give every imported column its confidence
    signals and score, and whether it is right (confidence.py), for the
    calibration of the bands. The loop's result does not change."""
    import confidence as C
    per = []
    started = time.time()
    for k, t in enumerate(tasks):
        if t.get("answer") == "multi":            # several tables (G)
            per.append(multi_record(runner, t))
            continue
        sheet = sheet_from_task(t)
        answer_refusal = refusal_of(t["program"])
        t0 = time.process_time()
        if runner.fits(t["preview"]):
            greedy = runner._write(t["preview"], 0, greedy_only=True)[0]
        else:
            greedy = ""
        greedy_cpu = time.process_time() - t0
        p1 = pass_at_1(t, greedy, sheet) if greedy else False
        t1 = time.process_time()
        loop = runner._import_sheet(sheet, t["targets"], t["locale"],
                                    greedy=greedy or None,
                                    confidence=confidence)
        loop_cpu = greedy_cpu + time.process_time() - t1
        imported = loop["status"] in ("imported", "imported_with_warnings")
        rows = clean(loop["rows"]) if imported else None
        if answer_refusal:
            loop_ok = loop["status"] == "refused" and \
                loop["reason"] == answer_refusal
        else:
            loop_ok = imported and rows == truth_rows(t["answer"],
                                                      t["truth"])
        invented = 0
        if imported:
            for record, srcs in zip(loop["rows"], loop["sources"]):
                for f, v in record.items():
                    if v is not None and not srcs.get(f):
                        invented += 1
        try:
            got_target = ts.parse(greedy).target if greedy else None
        except Exception:
            got_target = None
        rec = {"id": t["id"], "lang": t["lang"], "family": t["family"],
               "format": t.get("format"),
               "answer": t["answer"], "traps": t["traps"],
               "refusal_task": bool(answer_refusal),
               "pass1": bool(p1), "loop_ok": bool(loop_ok),
               "status": loop["status"], "reason": loop["reason"],
               "imported": imported,
               "false_accept": bool(imported and not loop_ok),
               "target_ok": (got_target == t["answer"])
               if not answer_refusal else None,
               "invented": invented, "candidates": loop["candidates_tried"],
               "greedy_cpu": round(greedy_cpu, 3),
               "loop_cpu": round(loop_cpu, 3)}
        if confidence and imported and loop.get("confidence"):
            try:
                rights = C.field_rights(t, loop, sheet)
            except Exception:
                rights = {}
            seen = set()
            rec["confidence"] = []
            for col in loop["confidence"]["columns"]:
                if col["field"] in seen or col["field"] not in rights:
                    continue
                seen.add(col["field"])
                rec["confidence"].append({
                    "field": col["field"], "score": col["score"],
                    "signals": col["signals"],
                    "right": rights[col["field"]]})
        if keep_examples and not (p1 and loop_ok):
            rec["group"] = error_group(t, greedy, loop)
            rec["greedy"] = greedy
            rec["truth_program"] = t["program"]
        per.append(rec)
        if (k + 1) % 100 == 0:
            log("  %s: %d / %d (%.0f s)" % (split, k + 1, len(tasks),
                                            time.time() - started))
    return per


def multi_record(runner, t):
    """A sheet of several tables (test_layouts): blocks.split() cuts it,
    and every table must be imported right on its own. -> one record, as
    evaluate_split() writes for one sheet; its parts in "parts"."""
    import blocks
    sheet = sheet_from_task(t)
    cut = blocks.split(sheet)
    parts = []
    greedy_cpu = loop_cpu = 0.0
    for block, part in zip(cut, t["parts"]):
        small, _ = sheets.compact(block)
        preview = sheets.preview(small, t["targets"], t["locale"])
        t0 = time.process_time()
        greedy = runner._write(preview, 0, greedy_only=True)[0] \
            if runner.fits(preview) else ""
        greedy_cpu += time.process_time() - t0
        as_task = {"program": part["program"], "truth": part["truth"],
                   "targets": t["targets"], "locale": t["locale"]}
        p1 = pass_at_1(as_task, greedy, block) if greedy else False
        t1 = time.process_time()
        loop = runner._import_sheet(block, t["targets"], t["locale"],
                                    greedy=greedy or None)
        loop_cpu += time.process_time() - t1
        imported = loop["status"] in ("imported", "imported_with_warnings")
        ok = imported and clean(loop["rows"]) == truth_rows(part["answer"],
                                                            part["truth"])
        parts.append({"answer": part["answer"], "pass1": bool(p1),
                      "loop_ok": bool(ok), "imported": imported,
                      "target": loop["target"],
                      "candidates": loop["candidates_tried"]})
    whole = len(cut) == len(t["parts"])
    loop_ok = whole and all(x["loop_ok"] for x in parts)
    imported = whole and all(x["imported"] for x in parts)
    return {"id": t["id"], "lang": t["lang"], "family": t["family"],
            "format": t.get("format"), "answer": "multi",
            "traps": t.get("traps") or [], "refusal_task": False,
            "pass1": whole and all(x["pass1"] for x in parts),
            "loop_ok": loop_ok,
            "status": "imported" if imported else "needs_review",
            "reason": None if whole else "tables_%d_of_%d" % (
                len(cut), len(t["parts"])),
            "imported": imported, "false_accept": imported and not loop_ok,
            "target_ok": whole and all(x["target"] == x["answer"]
                                       for x in parts),
            "invented": 0, "candidates": sum(x["candidates"] for x in parts),
            "greedy_cpu": round(greedy_cpu, 3),
            "loop_cpu": round(loop_cpu, 3), "parts": parts}


def summarize(per):
    if not per:
        return {"tasks": 0}
    importable = [r for r in per if not r["refusal_task"]]
    refusal_tasks = [r for r in per if r["refusal_task"]]
    imports = [r for r in per if r["imported"]]
    refused = [r for r in per if r["status"] == "refused"]
    out = {
        "tasks": len(per),
        "pass1": mean(r["pass1"] for r in per),
        "loop": mean(r["loop_ok"] for r in per),
        "loop_importable": mean(r["loop_ok"] for r in importable),
        "false_accepts": sum(r["false_accept"] for r in per),
        "false_accept_share": sum(r["false_accept"] for r in imports) /
        max(1, len(imports)),
        "refusal_precision": sum(1 for r in refused if r["refusal_task"]) /
        max(1, len(refused)),
        "refusal_recall": sum(1 for r in refusal_tasks
                              if r["status"] == "refused") /
        max(1, len(refusal_tasks)),
        "target_accuracy": mean(r["target_ok"] for r in importable),
        "needs_review": mean(r["status"] == "needs_review" for r in per),
        "invented_values": sum(r["invented"] for r in per),
        "cpu_seconds": {
            "greedy_median": med([r["greedy_cpu"] for r in per]),
            "greedy_p95": p95([r["greedy_cpu"] for r in per]),
            "loop_median": med([r["loop_cpu"] for r in per]),
            "loop_p95": p95([r["loop_cpu"] for r in per])},
    }
    for key in ("lang", "answer"):
        groups = collections.defaultdict(list)
        for r in per:
            name = r[key] if key == "lang" or not r["refusal_task"] \
                else "refusal"
            groups[name].append(r["loop_ok"])
        out["loop_by_" + key] = dict((g, round(mean(v), 4))
                                     for g, v in sorted(groups.items()))
    traps = collections.defaultdict(list)
    for r in per:
        for tr in r["traps"]:
            traps[tr].append(r["loop_ok"])
    out["loop_by_trap"] = dict((k, round(mean(v), 4)) for k, v in
                               sorted(traps.items(), key=lambda kv:
                                      int(kv[0][1:])))
    # the tables of section 24 (per language, target, family and trap),
    # each group with its task count, pass@1 and loop - aggregates only,
    # so they are allowed for every split (section 11)
    by = {"lang": collections.defaultdict(list),
          "answer": collections.defaultdict(list),
          "family": collections.defaultdict(list),
          "trap": collections.defaultdict(list),
          "format": collections.defaultdict(list)}
    for r in per:
        by["lang"][r.get("lang")].append(r)
        by["format"][r.get("format") or "?"].append(r)
        by["answer"][r["answer"] if not r["refusal_task"]
                     else "refusal"].append(r)
        by["family"][r.get("family") or "?"].append(r)
        for tr in r.get("traps") or []:
            by["trap"][tr].append(r)
    out["groups"] = dict(
        (key, dict((g, {"tasks": len(rs),
                        "pass1": mean(x["pass1"] for x in rs),
                        "loop": mean(x["loop_ok"] for x in rs)})
                   for g, rs in sorted(groups.items(), key=lambda kv:
                                       str(kv[0]))))
        for key, groups in by.items())
    # the candidate loop (section 7.2): how many candidates it tried, and
    # where the imports came from (the greedy one, or a sampled one)
    tried = [r["candidates"] for r in per if r.get("candidates") is not None]
    if tried:
        greedy_imp = [r for r in imports if r.get("candidates") == 1]
        sampled_imp = [r for r in imports if (r.get("candidates") or 0) > 1]
        out["candidates"] = {
            "mean": round(sum(tried) / len(tried), 3),
            "median": med(tried), "p95": p95(tried), "max": max(tried),
            "histogram": dict((str(k), v) for k, v in
                              sorted(collections.Counter(tried).items())),
            "imports_greedy": len(greedy_imp),
            "imports_greedy_correct": sum(r["loop_ok"] for r in greedy_imp),
            "imports_sampled": len(sampled_imp),
            "imports_sampled_correct": sum(r["loop_ok"]
                                           for r in sampled_imp)}
    out["status_counts"] = dict(collections.Counter(
        r["status"] for r in per).most_common())
    return out


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def med(values):
    return round(statistics.median(values), 3) if values else None


def p95(values):
    return round(float(np.percentile(values, 95)), 3) if values else None


# ---------------------------------------------------------------------
#  the handwritten files and real_eval/
# ---------------------------------------------------------------------
def evaluate_folder(runner, folder, log):
    truth_path = folder / "truth.jsonl"
    if not truth_path.exists():
        return None
    lines = [json.loads(x) for x in truth_path.read_text(
        encoding="utf-8").splitlines() if x.strip()]
    if not lines:
        return {"sheets": 0}
    import blocks
    ok = []
    per_lang = collections.defaultdict(list)
    per_type = collections.defaultdict(list)
    for item in lines:
        path = folder / item["file"]
        # a sheet of several tables is cut as Tulip cuts it: its tables
        # are "<sheet> #1", "<sheet> #2" (the handwritten set of Tulip 1
        # has none)
        found = [part for s in sheets.load(path, item["locale"])
                 for part in blocks.split(s) if part.name == item["sheet"]]
        if not found:
            ok.append(False)
            continue
        res = runner._import_sheet(found[0], item["targets"],
                                   item["locale"])
        target_answer = item["answer"] in config.TARGETS
        if target_answer:
            good = res["status"] in ("imported", "imported_with_warnings") \
                and clean(res["rows"]) == truth_rows(
                    item["answer"], item["truth"],
                    item.get("truth_format", "tulipscript"))
        else:
            good = res["status"] == "refused" and \
                res["reason"] == item["answer"]
        ok.append(bool(good))
        per_lang[item["locale"].split("-")[0]].append(bool(good))
        per_type[path.suffix.lower().lstrip(".")].append(bool(good))
    return {"sheets": len(lines), "loop": mean(ok),
            "by_lang": dict((k, mean(v)) for k, v in sorted(
                per_lang.items())),
            "by_type": dict((k, mean(v)) for k, v in sorted(
                per_type.items()))}


# ---------------------------------------------------------------------
#  several processes at once (one CPU thread each): writing one program
#  is a chain of small steps that one thread runs as fast as four
# ---------------------------------------------------------------------
_RUNNER = None

# The order the splits are scored in: the gate's own splits first, so a
# run that runs out of time loses the least important ones.
EVAL_ORDER = ["test_heldout", "test_seen", "traps", "dev_heldout",
              "test_files", "test_layouts", "val", "test_locale"]
# at most this many processes share the GPU (each loads torch and the
# model; the /train unit has 12 GB of RAM for all of them)
GPU_WORKERS = 2


class OutOfTime(Exception):
    pass


# The confidence bands (Tulip 1.1, item C): fitted on the first
# CONFIDENCE_TASKS tasks of dev_heldout, measured on the first
# CONFIDENCE_TASKS of test_heldout (with --dev-only: fitted on the even
# and measured on the odd tasks of dev_heldout). Those tasks write their
# 8 candidates even when the greedy program passes, so they cost more.
CONFIDENCE_TASKS = 2000
CONFIDENCE_FIT, CONFIDENCE_MEASURE = "dev_heldout", "test_heldout"


def confidence_result(pairs, dev_only):
    """{split: [(score, right)]} -> the bands and their measured rates
    (eval.json "confidence"; build.py puts the bands into the model
    file)."""
    import confidence as C
    if CONFIDENCE_FIT not in pairs:
        return {"bands": None, "why": "%s was not scored" % CONFIDENCE_FIT}
    fit = pairs[CONFIDENCE_FIT]
    if not fit:
        # scored, but the model imported none of its tables
        return {"bands": None,
                "why": "no column of %s was imported" % CONFIDENCE_FIT}
    out = {"score_version": C.SCORE_VERSION,
           "sure_target": C.SURE_PRECISION}
    measure = pairs.get(CONFIDENCE_MEASURE)
    if measure and not dev_only:
        bands = C.calibrate([p[:2] for p in fit])
        out.update(fit_on="%s (%d columns)" % (CONFIDENCE_FIT, len(fit)),
                   measured_on="%s (%d columns)" % (CONFIDENCE_MEASURE,
                                                    len(measure)),
                   fit=C.measure([p[:2] for p in fit], bands),
                   measured=C.measure([p[:2] for p in measure], bands))
    else:
        even = [p[:2] for p in fit if p[2] % 2 == 0]
        odd = [p[:2] for p in fit if p[2] % 2 == 1]
        bands = C.calibrate(even)
        out.update(fit_on="%s, even tasks (%d columns)" % (
            CONFIDENCE_FIT, len(even)),
            measured_on="%s, odd tasks (%d columns)" % (CONFIDENCE_FIT,
                                                        len(odd)),
            fit=C.measure(even, bands), measured=C.measure(odd, bands))
    out["bands"] = bands
    return out


def eval_device():
    """The GPU when there is one (writing programs one token at a time is
    about ten times faster there than on one CPU core), else the CPU."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def _worker_init(path, device="cpu"):
    global _RUNNER
    from tulip import Tulip
    torch.set_num_threads(1)
    _RUNNER = Tulip(path, device=device, threads=1)


def _worker_job(job):
    split, tasks, keep, confidence = job
    return evaluate_split(_RUNNER, split, tasks, keep, lambda *a: None,
                          confidence)


def evaluate_parallel(path, split, tasks, keep, workers, log, device="cpu",
                      deadline=None, confidence=False):
    """Several processes (spawned, never forked: CUDA/ROCm cannot be
    forked), each with its own copy of the model. Raises OutOfTime when
    the deadline passes before the split is finished; a part-scored split
    is never reported. confidence: True, or the number of tasks (the
    first ones) that also get the confidence bands' signals."""
    import multiprocessing
    started = time.time()
    n_conf = len(tasks) if confidence is True else int(confidence or 0)
    if workers <= 1 or len(tasks) < 8:
        _worker_init(path, device)
        per = []
        for k in range(0, len(tasks), 50):
            if deadline and time.time() > deadline:
                raise OutOfTime(split)
            for a, b, conf in ((k, min(k + 50, n_conf), True),
                               (max(k, n_conf), k + 50, False)):
                if a < b:
                    per += evaluate_split(_RUNNER, split, tasks[a:b], keep,
                                          lambda *x: None, conf)
            log("  %s: %d / %d (%.0f s); evaluate progress %d%%" % (
                split, len(per), len(tasks), time.time() - started,
                100 * len(per) // max(1, len(tasks))))
        return per
    size = max(1, min(100, len(tasks) // (workers * 6)))
    jobs = [(split, tasks[k:min(k + size, n_conf)], keep, True)
            for k in range(0, n_conf, size)]
    jobs += [(split, tasks[k:k + size], keep, False)
             for k in range(n_conf, len(tasks), size)]
    per = []
    with multiprocessing.get_context("spawn").Pool(
            workers, initializer=_worker_init,
            initargs=(str(path), device)) as pool:
        for part in pool.imap(_worker_job, jobs):
            per += part
            log("  %s: %d / %d (%.0f s); evaluate progress %d%%" % (
                split, len(per), len(tasks), time.time() - started,
                100 * len(per) // max(1, len(tasks))))
            if deadline and time.time() > deadline and len(per) < len(tasks):
                pool.terminate()
                raise OutOfTime(split)
    return per


def run(preset, dev_only=False, model_path=None, log=print, workers=None,
        deadline=None):
    """deadline: a time.time() after which no split is started or
    finished (build.py sets it from the /train run's 24-hour limit); a
    split that does not fit is listed in "not_run", never scored in
    part."""
    from tulip import Tulip
    out = config.runs_dir(preset)
    path = model_path or (config.work_dir(preset) / "best.pt")
    device = eval_device()
    # never one process per core (config.workers() is at most 4), and at
    # most GPU_WORKERS on the GPU
    workers = max(1, min(workers or config.workers(), config.MAX_WORKERS,
                         GPU_WORKERS if device == "cuda" else
                         config.MAX_WORKERS))
    wanted = list(config.DEV_SPLITS) if dev_only else list(config.SPLITS[1:])
    splits = [s for s in EVAL_ORDER if s in wanted] + \
        [s for s in wanted if s not in EVAL_ORDER]
    result = {"preset": preset, "dev_only": dev_only, "model": str(
        pathlib.Path(path).name), "device": device, "workers": workers,
        "splits": {}, "errors": {}, "not_run": {}, "seconds": {}}
    rate = None                     # seconds per task, measured
    pairs = {}                      # the confidence bands' columns
    for split in splits:
        tasks = read_tasks(preset, split)
        if deadline and (time.time() > deadline or (
                rate and time.time() + rate * len(tasks) > deadline)):
            result["not_run"][split] = "time"
            log("NOT evaluating %s: the run's time budget would be "
                "exceeded (%d tasks at %.2f s each)" % (
                    split, len(tasks), rate or 0))
            continue
        log("evaluating %s (%d tasks, %d processes, %s)" % (
            split, len(tasks), workers, device))
        t0 = time.time()
        n_conf = min(len(tasks), CONFIDENCE_TASKS) if split in (
            CONFIDENCE_FIT, CONFIDENCE_MEASURE) else 0
        try:
            per = evaluate_parallel(path, split, tasks,
                                    split in ERROR_SPLITS, workers, log,
                                    device, deadline, n_conf)
        except OutOfTime:
            result["not_run"][split] = "time"
            log("STOPPED evaluating %s: the run's time budget ran out" %
                split)
            continue
        result["seconds"][split] = round(time.time() - t0, 1)
        if tasks:
            rate = (time.time() - t0) / len(tasks)
        result["splits"][split] = summarize(per)
        if n_conf:
            pairs[split] = [(c["score"], bool(c["right"]),
                             int(r["id"].rsplit("-", 1)[1]))
                            for r in per for c in r.get("confidence", [])]
        if split in ERROR_SPLITS:
            groups = collections.Counter(r["group"] for r in per
                                         if "group" in r)
            result["errors"][split] = {
                "groups": dict(groups.most_common()),
                "examples": [r for r in per if "group" in r][:400]}
    # the dict order of the tables is the usual one, whatever the order
    # the splits were scored in
    result["splits"] = dict((s, result["splits"][s]) for s in wanted
                            if s in result["splits"])
    result["confidence"] = confidence_result(pairs, dev_only)
    if not dev_only:
        runner = Tulip(path, device=device)
        result["handwritten"] = evaluate_folder(runner, HERE / "handwritten",
                                                log)
        result["real_eval"] = evaluate_folder(runner, HERE / "real_eval",
                                              log)
        # Tulip 1.1's handwritten cases (item G): PDF, .xls, .ods,
        # several tables on one sheet, several days in one cell
        result["handwritten_1_1"] = evaluate_folder(
            runner, HERE / "handwritten_1_1", log)
    (out / "eval.json").write_text(json.dumps(result, indent=1,
                                              ensure_ascii=False),
                                   encoding="utf-8")
    (out / "eval_tables.md").write_text(tables(result), encoding="utf-8")
    return result


# ---------------------------------------------------------------------
#  the tables (section 16) and the gate
# ---------------------------------------------------------------------
GATE = [
    ("1", "test_seen pass@1", ">= 0.97", "test_seen", "pass1", 0.97, ">="),
    ("2", "test_heldout pass@1", ">= 0.90", "test_heldout", "pass1", 0.90,
     ">="),
    ("3", "test_heldout loop: correct imports among importable tasks",
     ">= 0.95", "test_heldout", "loop_importable", 0.95, ">="),
    ("4", "test_heldout false accepts among the loop's imports", "<= 2%",
     "test_heldout", "false_accept_share", 0.02, "<="),
    ("5a", "refusal precision (test_heldout, loop)", ">= 0.95",
     "test_heldout", "refusal_precision", 0.95, ">="),
    ("5b", "refusal recall (test_heldout, loop)", ">= 0.90",
     "test_heldout", "refusal_recall", 0.90, ">="),
    ("6", "target choice accuracy (test_heldout)", ">= 0.97",
     "test_heldout", "target_accuracy", 0.97, ">="),
]


def gate_rows(result):
    """The section 16 table: (#, measure, target, value, result) rows,
    all twelve of them, always in the same order. A split that the run's
    time budget skipped ("not_run" in eval.json) reads "not run (time)"
    and NOT RUN - never PASS; a split left out by --dev-only reads "not
    run (dev-only)"."""
    splits = result.get("splits") or {}
    not_run = result.get("not_run") or {}

    def scored(split):
        s = splits.get(split) or {}
        return s if s.get("tasks") else None

    def missing(split):
        """-> (value, result) for a split that has no numbers."""
        if split in not_run:
            return "not run (%s)" % not_run[split], "NOT RUN"
        if result.get("dev_only"):
            return "not run (dev-only)", ""
        return "not run", ""

    def verdict(ok):
        return "PASS" if ok else "FAIL"

    rows = []
    for num, name, target, split, key, bound, op in GATE:
        s = scored(split)
        v = s.get(key) if s else None
        if v is None:
            rows.append((num, name, target) + missing(split))
            continue
        ok = v >= bound if op == ">=" else v <= bound
        shown = "%.2f%%" % (100 * v) if target.endswith("%") else "%.4f" % v
        rows.append((num, name, target, shown, verdict(ok)))

    # 7: the lowest language and the lowest target (refusals are not a
    # target) of test_heldout, loop
    name7 = "every language and every target, loop, test_heldout"
    th = scored("test_heldout")
    if th:
        groups = th.get("groups") or {}
        langs = dict((g, v["loop"]) for g, v in
                     (groups.get("lang") or {}).items()) or \
            dict(th.get("loop_by_lang") or {})
        targets = dict((g, v["loop"]) for g, v in
                       (groups.get("answer") or {}).items()) or \
            dict(th.get("loop_by_answer") or {})
        targets.pop("refusal", None)
        both = [(v, g) for g, v in list(langs.items()) +
                list(targets.items()) if v is not None]
        if both:
            worst, who = min(both)
            rows.append(("7", name7, ">= 0.88",
                         "%.4f (lowest: %s)" % (worst, who),
                         verdict(worst >= 0.88)))
        else:
            rows.append(("7", name7, ">= 0.88", "no groups", ""))
    else:
        rows.append(("7", name7, ">= 0.88") + missing("test_heldout"))

    # 8: the lowest trap of the traps split, loop
    name8 = "every trap (traps split, loop)"
    tr = scored("traps")
    traps = {}
    if tr:
        traps = dict((g, v["loop"]) for g, v in
                     ((tr.get("groups") or {}).get("trap") or {}).items()) \
            or dict(tr.get("loop_by_trap") or {})
    if tr and traps:
        worst, who = min((v, g) for g, v in traps.items())
        rows.append(("8", name8, ">= 0.85", "%.4f (lowest: %s)" % (worst, who),
                     verdict(worst >= 0.85)))
    else:
        rows.append(("8", name8, ">= 0.85") + (
            missing("traps") if not tr else ("no trap tasks", "")))

    # 9: invented values, over every split that was scored
    name9 = "invented values (no source cell / absent lookup key)"
    counted = [sp for sp in splits if scored(sp)]
    if counted:
        invented = sum((splits[sp].get("invented_values") or 0)
                       for sp in counted)
        skipped = sorted(not_run)
        rows.append(("9", name9, "= 0", "%d (in %s%s)" % (
            invented, ", ".join(counted),
            "; not run: %s" % ", ".join(skipped) if skipped else ""),
            "FAIL" if invented else
            "PASS on the scored splits" if skipped else "PASS"))
    else:
        rows.append(("9", name9, "= 0", "no split scored", ""))

    # 10: helpers - the Appendix I cases, run now against helpers.py, and
    # the generated values the generator's self-check counted
    # (data/<preset>/stats.json)
    name10 = "helpers: Appendix I cases / generated values"
    parts, oks = [], []
    try:
        import importlib.util
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location(
            "tulip_test_helpers", HERE / "tests" / "test_helpers.py")
        th_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(th_mod)
        cases = [c for c in th_mod.CASES if c[0] < 1000]
        good = 0
        for case in cases:
            try:
                th_mod._check([case])
                good += 1
            except AssertionError:
                pass
        parts.append("%d / %d cases" % (good, len(cases)))
        oks.append(good == len(cases))
    except Exception as exc:
        parts.append("Appendix I not run (%s)" % type(exc).__name__)
        oks.append(None)
    try:
        stats = json.loads((config.data_dir(result.get("preset") or "")
                            / "stats.json").read_text(encoding="utf-8"))
        values = sum(s.get("values", 0) for s in stats["splits"].values())
        wrong = sum(s.get("wrong_values", 0)
                    for s in stats["splits"].values())
        share = (values - wrong) / values if values else None
        if share is None:
            parts.append("no generated values")
            oks.append(None)
        else:
            parts.append("%.3f%% of %d values" % (100 * share, values))
            oks.append(share >= 0.995)
    except Exception as exc:
        parts.append("generated values not found (%s)" % type(exc).__name__)
        oks.append(None)
    rows.append(("10", name10, "100% / >= 99.5%", " / ".join(parts),
                 "FAIL" if False in oks else
                 "PASS" if all(oks) else "NOT MEASURED"))

    # 11: handwritten, report only
    hw = result.get("handwritten") or {}
    rows.append(("11", "handwritten files, loop", "report (>= 0.80 hoped)",
                 "%.4f of %d sheets" % (hw["loop"], hw["sheets"])
                 if hw.get("loop") is not None else
                 missing("handwritten")[0], "report"))

    # 12: test_locale, needs_review, CPU seconds - report only
    tl = scored("test_locale")
    rows.append(("12a", "test_locale pass@1 / loop", "report",
                 "%.4f / %.4f (%d tasks)" % (tl["pass1"], tl["loop"],
                                             tl["tasks"])
                 if tl else missing("test_locale")[0], "report"))
    base = next((sp for sp in ("test_heldout", "dev_heldout")
                 if scored(sp)), None)
    if base:
        b = splits[base]
        c = b.get("cpu_seconds") or {}
        rows.append(("12b", "needs_review share (loop)", "report",
                     "%.4f (%s)" % (b["needs_review"], base), "report"))
        rows.append(("12c", "CPU seconds per sheet, median / p95, greedy "
                     "and loop", "report",
                     "greedy %s / %s, loop %s / %s (%s)" % (
                         c.get("greedy_median"), c.get("greedy_p95"),
                         c.get("loop_median"), c.get("loop_p95"), base),
                     "report"))
    else:
        rows.append(("12b", "needs_review share (loop)", "report",
                     missing("test_heldout")[0], "report"))
        rows.append(("12c", "CPU seconds per sheet, median / p95, greedy "
                     "and loop", "report", missing("test_heldout")[0],
                     "report"))
    return rows


def confidence_lines(conf):
    """The confidence bands' table (eval_tables.md and REPORT.md)."""
    if not conf:
        return []
    lines = ["", "## Confidence bands (Tulip 1.1, item C)", ""]
    bands = conf.get("bands")
    if not bands:
        return lines + ["No calibration: %s. This model never says "
                        "'sure'." % (conf.get("why") or "too few right "
                                     "columns for a 99% band"), ""]
    lines += ["Thresholds, fitted on %s: sure >= %.4f, check >= %.4f "
              "(score version %s). Measured on %s:" % (
                  conf["fit_on"], bands["sure"], bands["check"],
                  conf.get("score_version"), conf["measured_on"]), "",
              "| band | columns | right | rate | 95% lower bound |",
              "|---|---|---|---|---|"]
    for band in ("sure", "check", "unsure"):
        m = (conf.get("measured") or {}).get(band) or {}
        lines.append("| %s | %s | %s | %s | %s |" % (
            band, m.get("columns", 0), m.get("right", 0),
            "-" if m.get("rate") is None else "%.2f%%" % (100 * m["rate"]),
            "-" if m.get("low95") is None else "%.2f%%" % (
                100 * m["low95"])))
    return lines + [""]


def tables(result):
    lines = ["# Tulip evaluation - preset %s%s" % (
        result["preset"], " (dev splits only)" if result["dev_only"] else ""),
        "", "Model file: `%s`" % result["model"], ""]
    not_run = result.get("not_run") or {}
    if not_run:
        lines += ["**Not run** (the run's time budget): " + ", ".join(
            "%s (%s)" % kv for kv in not_run.items()) + ". These splits "
            "have no numbers; they are never counted as a pass.", ""]
    lines += ["## Section 16 targets (the gate applies to the full preset)",
              "", "| # | measure | target | value | result |",
              "|---|---|---|---|---|"]
    for r in gate_rows(result):
        lines.append("| %s |" % " | ".join(r))
    seconds = result.get("seconds") or {}
    lines += ["", "## Per split", "",
              "| split | tasks | pass@1 | loop | loop (importable) | "
              "false accepts | refusal P / R | target acc. | needs_review "
              "| candidates mean / p95 | CPU s greedy med / p95 | "
              "CPU s loop med / p95 | wall s |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for split, s in result["splits"].items():
        if not s.get("tasks"):
            continue
        c = s["cpu_seconds"]
        cand = s.get("candidates") or {}
        lines.append("| %s | %d | %s | %s | %s | %d (%.1f%%) | %.3f / %.3f "
                     "| %s | %s | %s / %s | %s / %s | %s / %s | %s |" % (
                         split, s["tasks"], s["pass1"], s["loop"],
                         s["loop_importable"], s["false_accepts"],
                         100 * s["false_accept_share"],
                         s["refusal_precision"], s["refusal_recall"],
                         s["target_accuracy"], s["needs_review"],
                         cand.get("mean", ""), cand.get("p95", ""),
                         c["greedy_median"], c["greedy_p95"],
                         c["loop_median"], c["loop_p95"],
                         seconds.get(split, "")))
    for split in not_run:
        lines.append("| %s | not run (%s) |  |  |  |  |  |  |  |  |  |  "
                     "|  |" % (split, not_run[split]))
    for split, s in result["splits"].items():
        if not s.get("tasks"):
            continue
        lines += ["", "### %s: loop by language, target, family and trap"
                  % split, ""]
        groups = s.get("groups")
        if groups:
            for key, label in (("lang", "languages"), ("answer", "targets"),
                               ("family", "families"), ("trap", "traps"),
                               ("format", "file types")):
                lines.append("%s: %s" % (label, ", ".join(
                    "%s %s (%d)" % (g, v["loop"], v["tasks"])
                    for g, v in groups.get(key, {}).items())))
                lines.append("")
        else:
            lines.append("languages: " + ", ".join(
                "%s %s" % kv for kv in s["loop_by_lang"].items()))
            lines.append("")
            lines.append("targets: " + ", ".join(
                "%s %s" % kv for kv in s["loop_by_answer"].items()))
            lines.append("")
            lines.append("traps: " + ", ".join(
                "%s %s" % kv for kv in s["loop_by_trap"].items()))
    lines += confidence_lines(result.get("confidence"))
    if result.get("errors"):
        lines += ["", "## Error groups (val and dev_heldout only)", ""]
        for split, e in result["errors"].items():
            lines.append("%s: %s" % (split, ", ".join(
                "%s %d" % kv for kv in e["groups"].items()) or "none"))
            lines.append("")
    for name in ("handwritten", "real_eval", "handwritten_1_1"):
        h = result.get(name)
        if h is not None:
            lines += ["", "## %s" % name, "",
                      "sheets: %s, loop: %s" % (h.get("sheets"),
                                                h.get("loop"))]
            if h.get("by_lang"):
                lines.append("")
                lines.append("by language: " + ", ".join(
                    "%s %s" % kv for kv in h["by_lang"].items()))
            if h.get("by_type"):
                lines.append("")
                lines.append("by file type: " + ", ".join(
                    "%s %s" % kv for kv in h["by_type"].items()))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("preset")
    ap.add_argument("--dev-only", action="store_true")
    ap.add_argument("--model")
    a = ap.parse_args()
    r = run(a.preset, a.dev_only, a.model)
    print(tables(r))
