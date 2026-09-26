"""
report.py - writes REPORT.md (section 24) from what the builds left in
runs/ and data/. Called by the 'report' stage of build.py.

    py report.py            (the preset built most recently)
    py report.py pilot

The ten headings of section 24 come once each, in the spec's order.
Sections 3-6 hold one sub-heading per preset: the preset just built
first, then any other preset that has results in runs/ (marked as an
earlier build), so nothing already measured is lost and the order holds.

Every number comes from a file written by a stage (env.json, stages.json
or the .done records, data/<preset>/stats.json, generator_checks.json,
tokenizer_report.json, train_result.json, eval.json). Nothing is typed
by hand here, so the report can be rebuilt at any time. Older runs lack
some keys (val_losses, stopped_by, not_run, per-family numbers); they
are reported as missing, never guessed.

Error analysis (section 6) reads dev_heldout ONLY - never test_heldout,
test_locale or the handwritten files (section 11). Sections 7 and 8 are
copied WHOLE from DECISIONS.md: they are the record of what was changed
and why, and a cut in the middle of one would misreport it.
"""
import collections
import difflib
import gzip
import json
import pathlib
import sys

import config

HERE = pathlib.Path(__file__).resolve().parent
# presets in the order their sub-headings follow the one just built;
# any preset config.py adds later comes last
ORDER = tuple(["full", "pilot", "smoke"] +
              [p for p in config.PRESETS if p not in ("full", "pilot",
                                                      "smoke")])
# plumbing rehearsals: reported when they are the build, never carried
# into another preset's report
REHEARSALS = ("tiny",)
STAGE_ORDER = ("check", "generate", "tokenizer", "pack", "train",
               "evaluate", "export", "report")


def read_json(path):
    path = pathlib.Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else
                                     str(x).replace("|", "\\|")
                                     for x in r) + " |")
    return "\n".join(out)


def pct(x):
    return "" if x is None else "%.1f%%" % (100 * x)


def num(x, fmt="%.4f"):
    return "" if x is None else fmt % x


def has_results(p):
    d = config.runs_dir(p)
    return (d / "train_result.json").exists() or (d / "eval.json").exists()


def presets_run():
    return [p for p in ORDER if has_results(p)]


def latest_preset():
    """The preset whose results were written last (a rehearsal only when
    nothing else has results)."""
    best, when = None, -1.0
    for p in [x for x in ORDER if x not in REHEARSALS] + list(REHEARSALS):
        if best and p in REHEARSALS:
            break
        for name in ("eval.json", "train_result.json"):
            path = config.runs_dir(p) / name
            if path.exists() and path.stat().st_mtime > when:
                best, when = p, path.stat().st_mtime
    return best


def stages_of(preset):
    """{stage: .done record} - stages.json when it exists, else the
    separate .done files (older runs)."""
    st = read_json(config.runs_dir(preset) / "stages.json")
    if isinstance(st, dict) and st:
        return st
    out = {}
    for stage in STAGE_ORDER:
        rec = read_json(config.runs_dir(preset) / ("%s.done" % stage))
        if rec:
            out[stage] = rec
    return out


def hours(seconds):
    if seconds is None:
        return ""
    seconds = int(round(seconds))
    return "%d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60,
                             seconds % 60)


def scored(ev, split):
    s = (ev.get("splits") or {}).get(split) or {}
    return s if s.get("tasks") else None


def split_state(ev, split):
    """How a split without numbers is shown: never as a pass."""
    reason = (ev.get("not_run") or {}).get(split)
    if reason:
        return "not run (%s)" % reason
    if ev.get("dev_only"):
        return "not run (dev-only)"
    return "not run"


# ---------------------------------------------------------------------
#  1. summary (three lines, about the preset just built)
# ---------------------------------------------------------------------
def summary_lines(preset, gate):
    tr = read_json(config.runs_dir(preset) / "train_result.json") or {}
    ev = read_json(config.runs_dir(preset) / "eval.json") or {}
    if tr:
        stopped = {"time_cap": "stopped by the time cap",
                   "epochs": "ran its planned epochs",
                   "steps": "ran its planned steps",
                   "no_improvement": "stopped early (no improvement)"}.get(
                       tr.get("stopped_by"), "stop reason not recorded")
        line1 = ("**%s** (this build): %s parameters; %s steps, %.2f "
                 "epochs, %.1f training minutes, %s; checkpoint of step "
                 "%s kept." % (preset, format(tr.get("parameters", 0), ","),
                               tr.get("steps"), tr.get("epochs") or 0,
                               tr.get("train_minutes") or 0, stopped,
                               tr.get("chosen_step")))
    else:
        line1 = "**%s** (this build): not trained yet." % preset
    bits = []
    for split in ("test_heldout", "test_seen", "dev_heldout", "val"):
        s = scored(ev, split)
        if s:
            bits.append("%s pass@1 %.3f / loop %.3f" % (split, s["pass1"],
                                                        s["loop"]))
    not_run = ev.get("not_run") or {}
    line2 = "Scores: %s%s%s." % (
        "; ".join(bits) or "not evaluated",
        " (dev splits only)" if ev.get("dev_only") else "",
        "; NOT RUN (time): %s" % ", ".join(not_run) if not_run else "")
    if gate:
        failing = [r[0] for r in gate if r[4] == "FAIL"]
        line3 = ("Section 16 table: %d PASS, %d FAIL, %d not run%s%s." % (
            sum(1 for r in gate if r[4].startswith("PASS")), len(failing),
            sum(1 for r in gate if r[3].startswith("not run")),
            " (the gate applies to full only; %s is not gated)" % preset
            if preset != "full" else "",
            "; failing rows: " + ", ".join(failing) if failing else ""))
    else:
        line3 = "Section 16 table: not available (no eval.json)."
    return ["* " + line1, "* " + line2, "* " + line3]


# ---------------------------------------------------------------------
#  2. environment
# ---------------------------------------------------------------------
def env_section():
    env = read_json(HERE / "runs" / "env.json") or {}
    if not env:
        return "runs/env.json not found (the check stage has not run)."
    tf = env.get("tflops") or {}
    dev = env.get("device_name") or "CPU only"
    if env.get("device_memory_gb"):
        dev += " (%s GB%s, bf16 %s)" % (
            env.get("device_memory_gb"),
            ", compute capability %s" % env["compute_capability"]
            if env.get("compute_capability") else "",
            "yes" if env.get("bf16") else "no")
    return md_table(["item", "value"], [
        ("checked", env.get("checked")),
        ("OS", "%s %s" % (env.get("os"), env.get("machine") or "")),
        ("Python", env.get("python")), ("torch", env.get("torch")),
        ("backend", env.get("backend")), ("device", dev),
        ("CPU count / RAM GB", "%s / %s" % (env.get("cpu_count"),
                                            env.get("ram_gb"))),
        ("worker processes / torch threads", "%s / %s" % (
            env.get("workers"), env.get("torch_threads"))),
        ("measured TFLOPS", ", ".join("%s %s" % kv for kv in tf.items())
         or "not measured"),
        ("packages", ", ".join("%s %s" % kv for kv in
                               (env.get("packages") or {}).items()))])


# ---------------------------------------------------------------------
#  3. data
# ---------------------------------------------------------------------
def count_tasks(preset):
    """{split: {"lang": Counter, "answer": Counter, "family": Counter,
    "n": int}} - read one task at a time (a full split is gigabytes)."""
    out = {}
    for split in config.SPLITS:
        path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
        if not path.exists():
            continue
        c = {"lang": collections.Counter(), "answer": collections.Counter(),
             "family": collections.Counter(), "n": 0}
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                t = json.loads(line)
                c["n"] += 1
                c["lang"][t["lang"]] += 1
                a = t["answer"]
                c["answer"][a if a in config.TARGETS
                            else "refusal: " + a.split(":")[0]] += 1
                c["family"][t["family"]] += 1
        out[split] = c
    return out


def cross_table(counts, key, names, label):
    splits = list(counts)
    rows = []
    for name in names:
        rows.append([name] + [counts[s][key].get(name, 0) for s in splits])
    return md_table([label] + splits, rows)


def data_section(preset):
    stats = read_json(config.data_dir(preset) / "stats.json") or {}
    lines = []
    rows = []
    for split, s in (stats.get("splits") or {}).items():
        rows.append((split, s.get("made"), s.get("discards"),
                     s.get("duplicates"), s.get("failed"),
                     s.get("round_trips"),
                     len(s.get("round_trip_failures") or [])))
    if rows:
        lines.append(md_table(["split", "tasks", "discards (self-check)",
                               "duplicates dropped", "not made",
                               "real-file round trips",
                               "different previews"], rows))
        values = sum(s.get("values", 0) for s in stats["splits"].values())
        wrong = sum(s.get("wrong_values", 0)
                    for s in stats["splits"].values())
        lines.append("")
        lines.append("Generator %s; %s values made by the helpers, %d of "
                     "them wrong." % (stats.get("generator"),
                                      format(values, ","), wrong))
    else:
        lines.append("data/%s/stats.json not found." % preset)
    counts = count_tasks(preset)
    if counts:
        answers = [a for a in config.TARGETS] + sorted(
            {a for c in counts.values() for a in c["answer"]
             if a not in config.TARGETS})
        families = sorted({f for c in counts.values() for f in c["family"]})
        lines += ["", "Tasks per language and split:", "",
                  cross_table(counts, "lang", config.LANGS, "language"),
                  "", "Tasks per target (and refusal reason) and split:", "",
                  cross_table(counts, "answer", answers, "answer"), ""]
        lines.append("Refusal share: " + ", ".join(
            "%s %s" % (s, pct(sum(v for a, v in c["answer"].items()
                                  if a not in config.TARGETS) /
                              max(1, c["n"])))
            for s, c in counts.items()))
        lines += ["", "Tasks per family and split (%d families):" %
                  len(families), "",
                  cross_table(counts, "family", families, "family")]
    else:
        lines += ["", "The task files of data/%s are not present; the "
                  "per-language, target and family counts need them." %
                  preset]
    checks = read_json(config.runs_dir(preset) / "generator_checks.json")
    if checks:
        lines += ["", "Generator self-checks (section 10.8; check 3 holds "
                  "the trap rates):", ""]
        for c in checks["checks"]:
            lines.append("* %s %s" % ("PASS" if c["ok"] else "FAIL",
                                      c["check"]))
            for d in str(c["detail"]).splitlines():
                lines.append("  * " + d)
    tok = read_json(config.runs_dir(preset) / "tokenizer_report.json")
    if tok:
        lines += ["", "Preview tokens per language (train):", "",
                  md_table(["language", "p50", "p95", "max"], [
                      (l, v["p50"], v["p95"], v["max"]) for l, v in
                      tok["preview_tokens"].items()]), ""]
        lines.append("Tasks over 4,096 tokens (preview + program): %d of %d "
                     "(%s). Tokenizer round trip on val programs: %d "
                     "failures of %s." % (
                         tok["over_limit"], tok["tasks"],
                         pct(tok["over_limit_share"]),
                         tok["round_trip"]["failed"],
                         tok["round_trip"].get("programs", "?")))
    return "\n".join(lines)


# ---------------------------------------------------------------------
#  4. model
# ---------------------------------------------------------------------
def marks(curve, n=5):
    """n points spread over a [[step, value], ...] curve."""
    if not curve:
        return []
    idx = sorted({round(k * (len(curve) - 1) / (n - 1)) for k in range(n)})
    return [curve[i] for i in idx]


def model_section(preset):
    tr = read_json(config.runs_dir(preset) / "train_result.json") or {}
    s = config.PRESETS[preset]
    t = s["train"]
    lines = ["Preset **%s**: vocabulary %d, d_model %d, %d layers, %d "
             "heads, ffn %d, max_len %d, dropout %.1f; planned: %s." % (
                 preset, s["vocab_size"], s["d_model"], s["n_layer"],
                 s["n_head"], s["ffn_hidden"], s["max_len"], s["dropout"],
                 ", ".join(x for x in (
                     "%d steps" % t["steps"] if t.get("steps") else "",
                     "%d epochs" % t["epochs"] if t.get("epochs") else "",
                     "at most %d minutes (%.1f hours)" % (
                         t["minutes"], t["minutes"] / 60)
                     if t.get("minutes") else "") if x))]
    if not tr:
        return "\n".join(lines + ["", "Not trained yet."])
    lines.append("")
    lines.append("Parameters: %s (%s outside the embedding). Steps: %s of "
                 "%s planned (%.2f epochs), %.1f training minutes. Chosen "
                 "checkpoint: step %s (dev sample execution match %.4f)." % (
                     format(tr["parameters"], ","),
                     format(tr["parameters_outside_embedding"], ","),
                     tr["steps"], tr.get("total"), tr.get("epochs") or 0,
                     tr.get("train_minutes") or 0, tr.get("chosen_step"),
                     tr.get("dev_sample_exec_match") or 0))
    lines.append("")
    why = tr.get("stopped_by")
    if why == "time_cap":
        cap = t.get("minutes")
        lines.append("**Training was stopped by the time cap** (%s) at step "
                     "%s, %.2f epochs into a plan of %s: the model saw "
                     "less data than planned." % (
                         "%d minutes = %.1f hours" % (cap, cap / 60)
                         if cap else "the preset's limit", tr["steps"],
                         tr.get("epochs") or 0,
                         "%s epochs" % t.get("epochs") if t.get("epochs")
                         else "%s steps" % t.get("steps")))
    elif why == "epochs":
        lines.append("Training stopped at its planned epoch limit (%s), "
                     "not by the time cap." % t.get("epochs"))
    elif why == "steps":
        lines.append("Training ran its planned %s steps." % t.get("steps"))
    elif why == "no_improvement":
        lines.append("Training stopped early: the model-selection score "
                     "(dev sample execution match) stopped improving.")
    elif why:
        lines.append("Training stopped by: %s." % why)
    else:
        lines.append("This train_result.json does not say what stopped "
                     "training (written before `stopped_by` was kept).")
    curve = tr.get("loss_curve") or []
    if curve:
        lines.append("")
        lines.append("Training loss (step: smoothed loss): " + ", ".join(
            "%d: %.3f" % (a, b) for a, b in marks(curve)))
    vl = tr.get("val_losses")
    lines.append("")
    if vl:
        low = min(vl, key=lambda x: x[1])
        lines.append("Validation loss (`val` split, at each model-selection "
                     "point, %d points): first %.4f at step %d, lowest "
                     "%.4f at step %d, last %.4f at step %d%s." % (
                         len(vl), vl[0][1], vl[0][0], low[1], low[0],
                         vl[-1][1], vl[-1][0],
                         "; still falling at the end" if len(vl) > 1 and
                         vl[-1][1] <= low[1] and vl[-1][1] < vl[-2][1]
                         else "; rising again after its lowest point"
                         if vl[-1][1] > low[1] else ""))
        if len(vl) > 5:
            lines.append("")
            lines.append("Validation loss curve (step: loss): " + ", ".join(
                "%d: %.4f" % (a, b) for a, b in marks(vl)))
    elif vl is not None:
        lines.append("Validation loss: none measured (no model-selection "
                     "point had a `val` sample).")
    else:
        lines.append("Validation loss: not recorded by this run (written "
                     "before `val_losses` was kept).")
    if tr.get("evals"):
        lines.append("")
        lines.append("Model-selection evaluations (step: dev sample "
                     "execution match): " + ", ".join(
                         "%d: %.3f" % (e["step"], e["exec_match"])
                         for e in tr["evals"]))
    st = stages_of(preset)
    if st:
        lines += ["", "Build stages (from %s):" % (
            "stages.json" if (config.runs_dir(preset) / "stages.json")
            .exists() else "the .done records"), "",
            md_table(["stage", "time (h:mm:ss)", "finished (UTC)"],
                     [(k, hours(v.get("seconds")), v.get("finished"))
                      for k, v in sorted(st.items(), key=lambda kv:
                                         STAGE_ORDER.index(kv[0])
                                         if kv[0] in STAGE_ORDER else 99)])]
    return "\n".join(lines)


# ---------------------------------------------------------------------
#  5. results
# ---------------------------------------------------------------------
def gate_of(ev):
    """evaluate.gate_rows, or None when evaluate.py cannot be imported
    (it imports torch)."""
    if not ev:
        return None
    try:
        import evaluate as E
    except Exception as exc:
        return [("-", "evaluate.py could not be imported (%s)" %
                 type(exc).__name__, "", "", "")]
    return E.gate_rows(ev)


def group_table(ev, key, legacy, label):
    """Rows = groups, columns = scored splits, cell = loop (tasks)."""
    splits = [s for s in (ev.get("splits") or {}) if scored(ev, s)]
    if not splits:
        return None
    cells = {}
    counts = False
    for sp in splits:
        s = ev["splits"][sp]
        g = (s.get("groups") or {}).get(key)
        if g:
            counts = True
            for name, v in g.items():
                cells.setdefault(name, {})[sp] = "%s (%d)" % (
                    num(v["loop"], "%.3f"), v["tasks"])
        elif legacy and s.get(legacy):
            for name, v in s[legacy].items():
                cells.setdefault(name, {})[sp] = num(v, "%.3f")
    if not cells:
        return None
    order = config.LANGS if key == "lang" else \
        list(config.TARGETS) + ["refusal"] if key == "answer" else []
    names = [n for n in order if n in cells] + sorted(
        (n for n in cells if n not in order),
        key=lambda n: (len(n), n) if key == "trap" else (0, n))
    return md_table([label] + splits, [[n] + [cells[n].get(sp, "")
                                              for sp in splits]
                                       for n in names]), counts


def results_section(preset, gate):
    ev = read_json(config.runs_dir(preset) / "eval.json")
    if not ev:
        return "Not evaluated yet."
    lines = []
    if ev.get("dev_only"):
        lines += ["_Only val and dev_heldout were scored (the improvement "
                  "rounds); the test splits are scored once at the end._",
                  ""]
    not_run = ev.get("not_run") or {}
    if not_run:
        lines += ["**Not run because the run's time budget ran out:** %s. "
                  "These splits have no numbers, and every row that needs "
                  "them reads \"not run (time)\" / NOT RUN - never a pass."
                  % ", ".join("%s (%s)" % kv for kv in not_run.items()), ""]
    lines += ["#### Section 16 table", "",
              md_table(["#", "measure", "target", "value", "result"], gate),
              ""]
    if preset != "full":
        lines += ["The gate applies to the full preset only; for %s these "
                  "are reported, not gated (section 16)." % preset, ""]
    # per split
    secs = ev.get("seconds") or {}
    rows = []
    for split in config.EVAL_SPLITS:
        s = scored(ev, split)
        if not s:
            rows.append([split, split_state(ev, split)] + [""] * 9)
            continue
        rows.append([split, s["tasks"], num(s["pass1"]), num(s["loop"]),
                     num(s["loop_importable"]),
                     "%d (%s)" % (s["false_accepts"],
                                  pct(s["false_accept_share"])),
                     "%s / %s" % (num(s["refusal_precision"], "%.3f"),
                                  num(s["refusal_recall"], "%.3f")),
                     num(s["target_accuracy"]), num(s["needs_review"]),
                     s["invented_values"], secs.get(split, "")])
    lines += ["#### Per split", "",
              md_table(["split", "tasks", "pass@1", "loop",
                        "loop (importable)", "false accepts (share of "
                        "imports)", "refusal P / R", "target acc.",
                        "needs_review", "invented values", "wall s"], rows),
              ""]
    # per language, target, family, trap
    for key, legacy, label, title in (
            ("lang", "loop_by_lang", "language", "By language"),
            ("answer", "loop_by_answer", "target", "By target"),
            ("family", None, "family", "By family"),
            ("trap", "loop_by_trap", "trap", "By trap")):
        t = group_table(ev, key, legacy, label)
        lines += ["#### %s (loop%s)" % (title, ", tasks in brackets"
                                        if t and t[1] else ""), ""]
        lines.append(t[0] if t else
                     "Not in this eval.json (evaluated before per-%s "
                     "numbers were kept)." % label)
        lines.append("")
    # the candidate loop
    rows = []
    for split in config.EVAL_SPLITS:
        s = scored(ev, split)
        if not s:
            continue
        c = s.get("candidates")
        st = s.get("status_counts") or {}
        if c:
            rows.append([split, c["mean"], "%s / %s / %s" % (
                c["median"], c["p95"], c["max"]),
                ", ".join("%s: %s" % kv for kv in c["histogram"].items()),
                "%d (%d right)" % (c["imports_greedy"],
                                   c["imports_greedy_correct"]),
                "%d (%d right)" % (c["imports_sampled"],
                                   c["imports_sampled_correct"]),
                num(s["needs_review"]),
                ", ".join("%s %d" % kv for kv in st.items())])
        else:
            rows.append([split, "not kept", "", "", "", "",
                         num(s["needs_review"]), ""])
    lines += ["#### The candidate loop (section 7.2)", "",
              md_table(["split", "candidates tried, mean",
                        "median / p95 / max", "tasks per number tried",
                        "imports from the greedy program",
                        "imports from a sampled program", "needs_review",
                        "loop results"], rows), ""]
    # handwritten, real_eval, test_locale
    lines += ["#### Handwritten files, real_eval and test_locale", ""]
    for name in ("handwritten", "real_eval"):
        h = ev.get(name)
        if h is None:
            lines.append("* %s: %s" % (name, "not run (dev-only)" if
                                       ev.get("dev_only") else "not run"))
        elif not h.get("sheets"):
            lines.append("* %s: no sheets" % name)
        else:
            lines.append("* %s: loop %s over %d sheets%s" % (
                name, num(h.get("loop")), h["sheets"],
                "; by language: " + ", ".join(
                    "%s %s" % (k, num(v, "%.2f"))
                    for k, v in h["by_lang"].items())
                if h.get("by_lang") else ""))
    tl = scored(ev, "test_locale")
    lines.append("* test_locale: %s" % (
        "pass@1 %s, loop %s over %d tasks" % (num(tl["pass1"]),
                                              num(tl["loop"]), tl["tasks"])
        if tl else split_state(ev, "test_locale")))
    lines.append("")
    # speed
    rows = []
    for split in config.EVAL_SPLITS:
        s = scored(ev, split)
        if s:
            c = s["cpu_seconds"]
            rows.append([split, "%s / %s" % (c["greedy_median"],
                                             c["greedy_p95"]),
                         "%s / %s" % (c["loop_median"], c["loop_p95"]),
                         secs.get(split, "")])
    lines += ["#### Speed (CPU seconds per sheet; wall seconds per split)",
              ""]
    if ev.get("device"):
        lines += ["Evaluated on %s with %s process(es)." % (
            ev["device"], ev.get("workers", "?")), ""]
    lines.append(md_table(["split", "greedy median / p95",
                           "loop median / p95", "wall s, whole split"],
                          rows) if rows else "No split scored.")
    return "\n".join(lines)


# ---------------------------------------------------------------------
#  6. error analysis - dev_heldout ONLY (section 11)
# ---------------------------------------------------------------------
def clip(text, width):
    return text if len(text) <= width else text[:width] + " …"


def clip_pair(a, b, width):
    """Cut two long lines around the first place they differ, so the
    difference is always in what is shown."""
    if max(len(a), len(b)) <= width:
        return a, b
    p = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y),
             min(len(a), len(b)))
    start = max(0, p - 40)
    lead = "… " if start else ""
    return (lead + clip(a[start:], width), lead + clip(b[start:], width))


def program_diff(wrote, expected, width=150, most=10):
    """The changed lines of wrote -> expected, as '-' (wrote) and '+'
    (expected) lines. None when the two programs are the same text."""
    a, b = wrote.splitlines(), expected.splitlines()
    if a == b:
        return None
    out = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        olds, news = a[i1:i2], b[j1:j2]
        for k in range(max(len(olds), len(news))):
            o = olds[k] if k < len(olds) else None
            n = news[k] if k < len(news) else None
            if o is not None and n is not None:
                if o.strip() == n.strip():          # whitespace only
                    o, n = repr(o), repr(n)
                o, n = clip_pair(o, n, width)
            if o is not None:
                out.append("- " + clip(o, width + 2))
            if n is not None:
                out.append("+ " + clip(n, width + 2))
    if len(out) > most:
        out = out[:most] + ["  … %d more changed lines" % (len(out) - most)]
    return out


def error_section(preset):
    ev = read_json(config.runs_dir(preset) / "eval.json") or {}
    # dev_heldout ONLY: never test_heldout, test_locale or handwritten
    e = (ev.get("errors") or {}).get("dev_heldout")
    s = scored(ev, "dev_heldout")
    if not e:
        return "No dev_heldout errors recorded%s." % (
            "" if s else " (%s)" % split_state(ev, "dev_heldout"))
    total = sum(e["groups"].values())
    lines = ["%d of %d dev_heldout tasks were wrong at pass@1 or in the "
             "loop. The top groups, each with two examples (`-` what the "
             "model wrote, `+` the expected program; only the lines that "
             "differ):" % (total, s["tasks"] if s else total), ""]
    kept = e.get("examples") or []
    for group, count in list(e["groups"].items())[:10]:
        lines.append("* **%s**: %d (%s of the errors)" % (
            group, count, pct(count / max(1, total))))
        shown = [x for x in kept if x.get("group") == group][:2]
        if not shown:
            lines.append("  * no example kept (eval.json keeps the first "
                         "400 errors)")
        for x in shown:
            head = "  * `%s` (%s, %s; loop: %s%s)" % (
                x["id"], x.get("family"), x.get("lang"), x.get("status"),
                ", " + x["reason"] if x.get("reason") else "")
            wrote = x.get("greedy") or ""
            if not wrote.strip():
                lines.append(head + ": no program written (the preview "
                             "did not fit the model)")
                continue
            diff = program_diff(wrote, x.get("truth_program") or "")
            if diff is None:
                lines.append(head + ": wrote exactly the expected program; "
                             "the difference is the loop's result")
                continue
            lines.append(head + ":")
            lines.append("")
            lines.append("    ```diff")
            lines += ["    " + d for d in diff]
            lines.append("    ```")
            lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------
#  7-8. from DECISIONS.md, whole
# ---------------------------------------------------------------------
def decisions_text():
    path = HERE / "DECISIONS.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def decisions_part(title, text=None):
    """The whole '## <title>' section of DECISIONS.md, without its
    heading. Never cut."""
    text = decisions_text() if text is None else text
    start = text.find("## " + title)
    if start < 0:
        return ""
    end = text.find("\n## ", start + 3)
    return text[start:end if end > 0 else None].split("\n", 1)[1].strip()


def decisions_headings(text):
    return [line[3:].strip() for line in text.splitlines()
            if line.startswith("## ")]


KNOWN_LIMITS = """* Training data is synthetic.
* `.xls` / `.ods` files are not read.
* At most 26 non-empty columns; one table per sheet.
* One row covering several days ("Lun–Ven 9h–18h") is not read.
* Formulas saved without a cached value arrive as empty.
* A product whose name begins with a totals word ("Total Care …") on a row
  with only numbers besides it is taken for a totals row."""

NEXT_STEPS = """On the desktop (RTX 4080), in PowerShell:

```powershell
cd "C:\\Users\\neomh\\new model\\tulip"
```
```powershell
py check.py
```
```powershell
py build.py full
```

Then import a real folder and look at the result:

```powershell
py import_sheets.py "C:\\Users\\Laurent\\documents to publish" --db "C:\\Users\\Laurent\\new model\\documents.db" --targets products,services,opening_hours --locale fr-FR --show
```"""


def sub_heading(p, preset):
    if p == preset:
        return "### %s (this build)" % p
    rec = stages_of(p).get("evaluate") or stages_of(p).get("train") or {}
    return "### %s (an earlier build%s)" % (
        p, ", finished %s" % rec["finished"] if rec.get("finished") else "")


def write(preset=None, log=print):
    preset = preset or latest_preset() or "pilot"
    others = [p for p in presets_run() if p != preset and
              p not in REHEARSALS]
    shown = [preset] + others
    gates = {}
    for p in shown:
        gates[p] = gate_of(read_json(config.runs_dir(p) / "eval.json"))
    parts = ["# Tulip 1 — the Importer: build report", ""]
    parts += ["## 1. Summary", ""] + summary_lines(preset, gates[preset])
    parts += ["", "## 2. Environment", "", env_section()]
    for number, title, fn in (
            (3, "Data", data_section), (4, "Model", model_section),
            (5, "Results", lambda p: results_section(p, gates[p] or [])),
            (6, "Error analysis (dev_heldout only)", error_section)):
        parts += ["", "## %d. %s" % (number, title)]
        for p in shown:
            parts += ["", sub_heading(p, preset), ""]
            if p != preset and not has_results(p):
                parts.append("Nothing built.")
                continue
            parts.append(fn(p))
    text = decisions_text()
    parts += ["", "## 7. Improvement rounds", "",
              decisions_part("Improvement rounds", text) or "None yet."]
    decisions = decisions_part("Decisions", text)
    rest = [h for h in decisions_headings(text)
            if h not in ("Decisions", "Improvement rounds")]
    parts += ["", "## 8. Deviations and decisions", "",
              "Copied whole from DECISIONS.md%s." % (
                  ", which also has: " + "; ".join(rest) if rest else ""),
              "", decisions or "None."]
    parts += ["", "## 9. Known limits", "", KNOWN_LIMITS]
    parts += ["", "## 10. Next steps for Laurent", "", NEXT_STEPS, ""]
    path = HERE / "REPORT.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    log("wrote %s (%s; other presets: %s)" % (path.name, preset,
                                             ", ".join(others) or "none"))
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    write(sys.argv[1] if len(sys.argv) > 1 else None)
