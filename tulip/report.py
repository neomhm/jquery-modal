"""
report.py - writes REPORT.md (section 24) from what the builds left in
runs/ and data/. Called by the 'report' stage of build.py.

    py report.py

Every number comes from a file written by a stage (env.json, the .done
records, data/<preset>/stats.json, tokenizer_report.json,
train_result.json, eval.json). Nothing is typed by hand here, so the
report can be rebuilt at any time. Error analysis uses dev_heldout only,
never a test split. The improvement rounds are copied from DECISIONS.md.
"""
import collections
import gzip
import json
import pathlib
import sys

import config

HERE = pathlib.Path(__file__).resolve().parent


def read_json(path):
    path = pathlib.Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else str(x)
                                     for x in r) + " |")
    return "\n".join(out)


def presets_run():
    return [p for p in ("smoke", "pilot", "full")
            if (config.runs_dir(p) / "train_result.json").exists()]


def done(preset, stage):
    return read_json(config.runs_dir(preset) / ("%s.done" % stage)) or {}


def pct(x):
    return "" if x is None else "%.1f%%" % (100 * x)


def data_section(preset):
    """Tasks per split, language, target and family; traps; discards."""
    stats = read_json(config.data_dir(preset) / "stats.json") or {}
    lines = []
    rows = []
    for split, s in (stats.get("splits") or {}).items():
        rows.append((split, s["made"], s["discards"], s["duplicates"],
                     s["failed"], s["round_trips"],
                     len(s["round_trip_failures"])))
    lines.append(md_table(["split", "tasks", "discards (self-check)",
                           "duplicates dropped", "not made",
                           "real-file round trips", "different previews"],
                          rows))
    train = []
    path = config.data_dir(preset) / "train.jsonl.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            train = [json.loads(x) for x in f]
    if train:
        n = len(train)
        by_lang = collections.Counter(t["lang"] for t in train)
        by_answer = collections.Counter(
            t["answer"] if t["answer"] in config.TARGETS else
            t["answer"].split(":")[0] for t in train)
        by_family = collections.Counter(t["family"] for t in train)
        lines.append("")
        lines.append("train, by language: " + ", ".join(
            "%s %s" % (l, pct(by_lang[l] / n)) for l in config.LANGS))
        lines.append("")
        lines.append("train, by answer: " + ", ".join(
            "%s %s" % (a, pct(c / n)) for a, c in by_answer.most_common()))
        refusal = sum(1 for t in train if t["answer"] not in config.TARGETS)
        lines.append("")
        lines.append("refusal share: %s" % pct(refusal / n))
        lines.append("")
        lines.append("train, by family (%d families): %s" % (
            len(by_family), ", ".join("%s %d" % kv for kv in
                                      sorted(by_family.items()))))
    checks = read_json(config.runs_dir(preset) / "generator_checks.json")
    if checks:
        lines.append("")
        lines.append("Generator self-checks (section 10.8):")
        lines.append("")
        for c in checks["checks"]:
            lines.append("* %s %s" % ("PASS" if c["ok"] else "FAIL",
                                      c["check"]))
            for d in str(c["detail"]).splitlines():
                lines.append("  * " + d)
    tok = read_json(config.runs_dir(preset) / "tokenizer_report.json")
    if tok:
        lines.append("")
        lines.append("Preview tokens per language (train):")
        lines.append("")
        lines.append(md_table(["language", "p50", "p95", "max"], [
            (l, v["p50"], v["p95"], v["max"]) for l, v in
            tok["preview_tokens"].items()]))
        lines.append("")
        lines.append("Tasks over 4,096 tokens: %d of %d (%s). Tokenizer "
                     "round trip on val programs: %d failures." % (
                         tok["over_limit"], tok["tasks"],
                         pct(tok["over_limit_share"]),
                         tok["round_trip"]["failed"]))
    return "\n".join(lines)


def model_section(preset):
    tr = read_json(config.runs_dir(preset) / "train_result.json") or {}
    s = config.PRESETS[preset]
    lines = ["Preset **%s**: vocabulary %d, d_model %d, %d layers, %d "
             "heads, ffn %d, max_len %d, dropout %.1f." % (
                 preset, s["vocab_size"], s["d_model"], s["n_layer"],
                 s["n_head"], s["ffn_hidden"], s["max_len"], s["dropout"])]
    if tr:
        lines.append("")
        lines.append("Parameters: %d (%d outside the embedding). Steps: %d "
                     "of %s planned (%.2f epochs), %.1f training minutes. "
                     "Chosen checkpoint: step %d (dev sample execution "
                     "match %.4f)." % (
                         tr["parameters"], tr["parameters_outside_embedding"],
                         tr["steps"], tr["total"], tr["epochs"],
                         tr["train_minutes"], tr["chosen_step"],
                         tr["dev_sample_exec_match"]))
        curve = tr.get("loss_curve") or []
        if curve:
            marks = [curve[0], curve[len(curve) // 4], curve[len(curve) // 2],
                     curve[3 * len(curve) // 4], curve[-1]]
            lines.append("")
            lines.append("Loss curve (step: smoothed loss): " + ", ".join(
                "%d: %.3f" % (a, b) for a, b in marks))
        if tr.get("evals"):
            lines.append("")
            lines.append("Model-selection evaluations: " + ", ".join(
                "step %d: %.3f" % (e["step"], e["exec_match"])
                for e in tr["evals"]))
    return "\n".join(lines)


def results_section(preset):
    import evaluate as E
    ev = read_json(config.runs_dir(preset) / "eval.json")
    if not ev:
        return "Not evaluated yet."
    lines = []
    if ev.get("dev_only"):
        lines.append("_Only val and dev_heldout were scored (the "
                     "improvement rounds); the test splits are scored once "
                     "at the end._")
        lines.append("")
    lines.append(md_table(["#", "measure", "target", "value", "result"],
                          E.gate_rows(ev)))
    lines.append("")
    if preset != "full":
        lines.append("The gate applies to the full preset only; for %s "
                     "these are reported, not gated (section 16)." % preset)
        lines.append("")
    tables = (config.runs_dir(preset) / "eval_tables.md")
    if tables.exists():
        text = tables.read_text(encoding="utf-8")
        cut = text.find("## Per split")
        if cut >= 0:
            lines.append(text[cut:].replace("## ", "#### "))
    return "\n".join(lines)


def error_section(preset):
    ev = read_json(config.runs_dir(preset) / "eval.json") or {}
    e = (ev.get("errors") or {}).get("dev_heldout")
    if not e:
        return "No dev_heldout errors recorded."
    lines = []
    for group, count in list(e["groups"].items())[:10]:
        lines.append("* **%s**: %d" % (group, count))
        shown = [x for x in e["examples"] if x.get("group") == group][:2]
        for x in shown:
            lines.append("  * `%s` (%s, %s): wrote `%s` - expected `%s`" % (
                x["id"], x["family"], x["lang"],
                " / ".join(x["greedy"].splitlines()[:4])[:160],
                " / ".join(x["truth_program"].splitlines()[:4])[:160]))
    return "\n".join(lines)


def decisions_part(title):
    path = HERE / "DECISIONS.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    start = text.find("## " + title)
    if start < 0:
        return ""
    end = text.find("\n## ", start + 3)
    return text[start:end if end > 0 else None].split("\n", 1)[1].strip()


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


def write(preset=None, log=print):
    env = read_json(HERE / "runs" / "env.json") or {}
    parts = ["# Tulip 1 — the Importer: build report", ""]
    runs = presets_run()
    summary = []
    for p in runs:
        ev = read_json(config.runs_dir(p) / "eval.json") or {}
        s = ev.get("splits") or {}
        bits = []
        for split in ("test_seen", "test_heldout", "dev_heldout", "val"):
            if (s.get(split) or {}).get("tasks"):
                bits.append("%s pass@1 %.3f / loop %.3f" % (
                    split, s[split]["pass1"], s[split]["loop"]))
        summary.append("* **%s**: %s%s" % (p, "; ".join(bits) or
                                           "not evaluated",
                                           " (dev splits only)"
                                           if ev.get("dev_only") else ""))
    parts += ["## 1. Summary", ""] + (summary or ["Nothing built yet."])
    parts += ["", "## 2. Environment", ""]
    if env:
        tf = env.get("tflops") or {}
        parts.append(md_table(["item", "value"], [
            ("OS", env.get("os")), ("Python", env.get("python")),
            ("torch", env.get("torch")), ("backend", env.get("backend")),
            ("device", env.get("device_name") or "CPU only"),
            ("CPU count / RAM GB", "%s / %s" % (env.get("cpu_count"),
                                                env.get("ram_gb"))),
            ("measured TFLOPS", ", ".join("%s %s" % kv for kv in tf.items())),
            ("packages", ", ".join("%s %s" % kv for kv in
                                   (env.get("packages") or {}).items()))]))
    for p in runs:
        parts += ["", "## 3. Data — %s" % p, "", data_section(p)]
        parts += ["", "## 4. Model — %s" % p, "", model_section(p)]
        parts += ["", "## 5. Results — %s" % p, "", results_section(p)]
        parts += ["", "## 6. Error analysis — %s (dev_heldout only)" % p,
                  "", error_section(p)]
    parts += ["", "## 7. Improvement rounds", "",
              decisions_part("Improvement rounds") or "None yet."]
    parts += ["", "## 8. Deviations and decisions", "",
              "See DECISIONS.md; the main ones:", "",
              decisions_part("Decisions") [:6000] or "None."]
    parts += ["", "## 9. Known limits", "", KNOWN_LIMITS]
    parts += ["", "## 10. Next steps for Laurent", "", NEXT_STEPS, ""]
    path = HERE / "REPORT.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    log("wrote %s" % path.name)
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    write()
