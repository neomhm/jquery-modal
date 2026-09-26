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
def evaluate_split(runner, split, tasks, keep_examples, log):
    per = []
    started = time.time()
    for k, t in enumerate(tasks):
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
                                    greedy=greedy or None)
        loop_cpu = greedy_cpu + time.process_time() - t1
        imported = loop["status"] in ("imported", "imported_with_warnings")
        rows = clean(loop["rows"]) if imported else None
        if answer_refusal:
            loop_ok = loop["status"] == "refused" and \
                loop["reason"] == answer_refusal
        else:
            loop_ok = imported and rows == clean(t["truth"])
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
        if keep_examples and not (p1 and loop_ok):
            rec["group"] = error_group(t, greedy, loop)
            rec["greedy"] = greedy
            rec["truth_program"] = t["program"]
        per.append(rec)
        if (k + 1) % 100 == 0:
            log("  %s: %d / %d (%.0f s)" % (split, k + 1, len(tasks),
                                            time.time() - started))
    return per


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
    ok = []
    per_lang = collections.defaultdict(list)
    for item in lines:
        path = folder / item["file"]
        found = [s for s in sheets.load(path, item["locale"])
                 if s.name == item["sheet"]]
        if not found:
            ok.append(False)
            continue
        res = runner._import_sheet(found[0], item["targets"],
                                   item["locale"])
        target_answer = item["answer"] in config.TARGETS
        if target_answer:
            good = res["status"] in ("imported", "imported_with_warnings") \
                and clean(res["rows"]) == clean(item["truth"])
        else:
            good = res["status"] == "refused" and \
                res["reason"] == item["answer"]
        ok.append(bool(good))
        per_lang[item["locale"].split("-")[0]].append(bool(good))
    return {"sheets": len(lines), "loop": mean(ok),
            "by_lang": dict((k, mean(v)) for k, v in sorted(
                per_lang.items()))}


# ---------------------------------------------------------------------
#  several processes at once (one CPU thread each): writing one program
#  is a chain of small steps that one thread runs as fast as four
# ---------------------------------------------------------------------
_RUNNER = None


def _worker_init(path):
    global _RUNNER
    from tulip import Tulip
    torch.set_num_threads(1)
    _RUNNER = Tulip(path, threads=1)


def _worker_job(job):
    split, tasks, keep = job
    return evaluate_split(_RUNNER, split, tasks, keep, lambda *a: None)


def evaluate_parallel(path, split, tasks, keep, workers, log):
    import multiprocessing
    if workers <= 1 or len(tasks) < 8:
        _worker_init(path)
        return evaluate_split(_RUNNER, split, tasks, keep, log)
    size = max(1, len(tasks) // (workers * 6))
    jobs = [(split, tasks[k:k + size], keep)
            for k in range(0, len(tasks), size)]
    per = []
    started = time.time()
    with multiprocessing.get_context("spawn").Pool(
            workers, initializer=_worker_init, initargs=(str(path),)) as pool:
        for part in pool.imap(_worker_job, jobs):
            per += part
            log("  %s: %d / %d (%.0f s)" % (split, len(per), len(tasks),
                                            time.time() - started))
    return per


def run(preset, dev_only=False, model_path=None, log=print, workers=None):
    import os
    from tulip import Tulip
    out = config.runs_dir(preset)
    path = model_path or (out / "best.pt")
    workers = workers or os.cpu_count() or 1
    splits = list(config.DEV_SPLITS) if dev_only else list(config.SPLITS[1:])
    result = {"preset": preset, "dev_only": dev_only, "model": str(
        pathlib.Path(path).name), "splits": {}, "errors": {}}
    for split in splits:
        tasks = read_tasks(preset, split)
        log("evaluating %s (%d tasks, %d processes)" % (split, len(tasks),
                                                       workers))
        per = evaluate_parallel(path, split, tasks, split in ERROR_SPLITS,
                                workers, log)
        result["splits"][split] = summarize(per)
        if split in ERROR_SPLITS:
            groups = collections.Counter(r["group"] for r in per
                                         if "group" in r)
            result["errors"][split] = {
                "groups": dict(groups.most_common()),
                "examples": [r for r in per if "group" in r][:400]}
    if not dev_only:
        runner = Tulip(path)
        result["handwritten"] = evaluate_folder(runner, HERE / "handwritten",
                                                log)
        result["real_eval"] = evaluate_folder(runner, HERE / "real_eval",
                                              log)
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
    rows = []
    for num, name, target, split, key, bound, op in GATE:
        s = result["splits"].get(split) or {}
        v = s.get(key)
        if v is None:
            rows.append((num, name, target, "not run", ""))
            continue
        ok = v >= bound if op == ">=" else v <= bound
        rows.append((num, name, target, "%.4f" % v, "PASS" if ok else
                     "FAIL"))
    th = result["splits"].get("test_heldout") or {}
    if th.get("loop_by_lang"):
        worst = min(list(th["loop_by_lang"].values()) +
                    list(th["loop_by_answer"].values()))
        rows.append(("7", "every language and target, loop, test_heldout",
                     ">= 0.88", "%.4f (lowest)" % worst,
                     "PASS" if worst >= 0.88 else "FAIL"))
    tr = result["splits"].get("traps") or {}
    if tr.get("loop_by_trap"):
        worst = min(tr["loop_by_trap"].values())
        rows.append(("8", "every trap (traps split, loop)", ">= 0.85",
                     "%.4f (lowest)" % worst,
                     "PASS" if worst >= 0.85 else "FAIL"))
    invented = sum((s.get("invented_values") or 0)
                   for s in result["splits"].values())
    rows.append(("9", "invented values", "= 0", str(invented),
                 "PASS" if invented == 0 else "FAIL"))
    hw = result.get("handwritten") or {}
    rows.append(("11", "handwritten files, loop", "report (>= 0.80 hoped)",
                 "%.4f of %d sheets" % (hw["loop"], hw["sheets"])
                 if hw.get("loop") is not None else "not run", ""))
    return rows


def tables(result):
    lines = ["# Tulip evaluation - preset %s%s" % (
        result["preset"], " (dev splits only)" if result["dev_only"] else ""),
        "", "Model file: `%s`" % result["model"], ""]
    lines += ["## Section 16 targets (the gate applies to the full preset)",
              "", "| # | measure | target | value | result |",
              "|---|---|---|---|---|"]
    for r in gate_rows(result):
        lines.append("| %s |" % " | ".join(r))
    lines += ["", "## Per split", "",
              "| split | tasks | pass@1 | loop | loop (importable) | "
              "false accepts | refusal P / R | target acc. | needs_review "
              "| CPU s greedy med / p95 | CPU s loop med / p95 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for split, s in result["splits"].items():
        if not s.get("tasks"):
            continue
        c = s["cpu_seconds"]
        lines.append("| %s | %d | %s | %s | %s | %d (%.1f%%) | %.3f / %.3f "
                     "| %s | %s | %s / %s | %s / %s |" % (
                         split, s["tasks"], s["pass1"], s["loop"],
                         s["loop_importable"], s["false_accepts"],
                         100 * s["false_accept_share"],
                         s["refusal_precision"], s["refusal_recall"],
                         s["target_accuracy"], s["needs_review"],
                         c["greedy_median"], c["greedy_p95"],
                         c["loop_median"], c["loop_p95"]))
    for split, s in result["splits"].items():
        if not s.get("tasks"):
            continue
        lines += ["", "### %s: loop by language, target and trap" % split,
                  ""]
        lines.append("languages: " + ", ".join(
            "%s %s" % kv for kv in s["loop_by_lang"].items()))
        lines.append("")
        lines.append("targets: " + ", ".join(
            "%s %s" % kv for kv in s["loop_by_answer"].items()))
        lines.append("")
        lines.append("traps: " + ", ".join(
            "%s %s" % kv for kv in s["loop_by_trap"].items()))
    if result.get("errors"):
        lines += ["", "## Error groups (val and dev_heldout only)", ""]
        for split, e in result["errors"].items():
            lines.append("%s: %s" % (split, ", ".join(
                "%s %d" % kv for kv in e["groups"].items()) or "none"))
            lines.append("")
    for name in ("handwritten", "real_eval"):
        h = result.get(name)
        if h is not None:
            lines += ["", "## %s" % name, "",
                      "sheets: %s, loop: %s" % (h.get("sheets"),
                                                h.get("loop"))]
            if h.get("by_lang"):
                lines.append("")
                lines.append("by language: " + ", ".join(
                    "%s %s" % kv for kv in h["by_lang"].items()))
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
