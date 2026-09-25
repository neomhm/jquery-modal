"""
report.py - writes REPORT.md (section 25) from what the builds left in
runs/ and data/. Called by the 'report' stage of build.py.

    py report.py

Every number comes from a file written by a stage (env.json, the .done
records, data_stats.json, tokenizer_report.json, calibration.json,
eval.json, checks.txt). Nothing is typed by hand here, so the report can
be rebuilt at any time. Error analysis uses val and dev_heldout only
(errors_dev.jsonl), never a test split.
"""
import collections
import json
import pathlib
import re
import sys

import config

HERE = pathlib.Path(__file__).resolve().parent
GATE_LABELS = ["S_NAME", "S_ADDRESS", "S_REG_ID", "S_PHONE", "S_EMAIL",
               "LEGAL_FORM", "FOUNDED", "STAFF", "REVENUE", "REVENUE_YEAR",
               "ACTIVITY", "SERVICE", "C_NAME"]


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
            if (config.runs_dir(p) / "eval.json").exists()]


def done(preset, stage):
    return read_json(config.runs_dir(preset) / ("%s.done" % stage)) or {}


def normalizer_rates(preset):
    path = config.data_dir(preset) / "checks.txt"
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"5 normalize\(\) == truth \(country\)\s+([\d.]+)%", text)
    m2 = re.search(r"language only: ([\d.]+)%", text)
    return (float(m.group(1)) / 100 if m else None,
            float(m2.group(1)) / 100 if m2 else None)


# ---------------------------------------------------------------------
#  the gate table of section 17
# ---------------------------------------------------------------------
def gate_rows(preset, ev):
    s = ev.get("splits", {})
    th = s.get("test_heldout") or {}
    rows = []

    def row(n, what, target, value, ok):
        if value is None:
            rows.append([n, what, target, "not measured", "-"])
        else:
            rows.append([n, what, target, value, "PASS" if ok else "FAIL"])
    ts = (s.get("test_seen") or {}).get("strict", {}).get("f1")
    row(1, "test_seen strict micro-F1", ">= 0.97", ts, ts is not None and
        ts >= 0.97)
    f = th.get("strict", {}).get("f1")
    row(2, "test_heldout strict micro-F1", ">= 0.92", f, f is not None and
        f >= 0.92)
    langs = th.get("per_lang") or {}
    worst = min(((v["f1"], k) for k, v in langs.items()), default=None)
    row(3, "test_heldout micro-F1, every language", ">= 0.88",
        "%.4f (%s)" % worst if worst else None,
        worst is not None and worst[0] >= 0.88)
    labels = th.get("per_label") or {}
    vals = [(labels[k]["f1"], k) for k in GATE_LABELS if k in labels]
    worst = min(vals, default=None)
    row(4, "test_heldout F1 of the 13 key labels (lowest)", ">= 0.85",
        "%.4f (%s)" % worst if worst else None,
        worst is not None and worst[0] >= 0.85)
    traps = (s.get("traps") or {}).get("traps") or {}
    v = traps.get("T1-T3 REVENUE precision")
    row(5, "traps: REVENUE precision (T1-T3)", ">= 0.97", v,
        v is not None and v >= 0.97)
    v = (traps.get("T4") or {}).get("role_swap_rate")
    row(6, "traps: role swaps (T4)", "<= 2%", v, v is not None and v <= 0.02)
    v = (traps.get("T12") or {}).get("false_spans_per_100_empty")
    row(7, "false spans per 100 empty chunks (T12)", "<= 2", v,
        v is not None and v <= 2)
    v = th.get("doc_type_accuracy")
    row(8, "doc-type accuracy (test_heldout)", ">= 0.93", v,
        v is not None and v >= 0.93)
    v = th.get("language_accuracy")
    row(9, "language accuracy (test_heldout)", ">= 0.99", v,
        v is not None and v >= 0.99)
    fl = (ev.get("folder_level") or {}).get("test_heldout") or {}
    v = fl.get("required_mean_accuracy")
    row(10, "folder level, test_heldout: 11 REQUIRED fields", ">= 0.90", v,
        v is not None and v >= 0.90)
    v = (fl.get("field_accuracy") or {}).get("business_name")
    row(11, "folder level: business name", ">= 0.97", v,
        v is not None and v >= 0.97)
    inv = [x.get("invented_values") for x in
           (ev.get("folder_level") or {}).values()]
    v = sum(inv) if inv else None
    row(12, "folder level: invented values", "= 0", v, v == 0)
    v = ev.get("boundary_rate")
    row(13, "tokenizer boundary rate", ">= 99.5%",
        None if v is None else "%.3f%%" % (100 * v),
        v is not None and v >= 0.995)
    rate, lang_rate = normalizer_rates(preset)
    row(14, "normalizer on generated spans, true country", ">= 99%",
        None if rate is None else "%.2f%% (language only %.2f%%)" % (
            100 * rate, 100 * (lang_rate or 0)),
        rate is not None and rate >= 0.99)
    hw = ev.get("handwritten")
    rows.append([15, "handwritten set micro-F1", "report (0.80 hoped)",
                 hw["strict"]["f1"] if hw else "not measured", "report"])
    tl = (s.get("test_locale") or {}).get("strict", {}).get("f1")
    rows.append([16, "test_locale micro-F1 / calibration error (ECE, "
                 "test_heldout) / speed", "report",
                 "%s / %s / %s" % (tl, th.get("ece"), (ev.get("speed") or
                                                     {}).get(
                     "chunks_per_second")), "report"])
    return rows


# ---------------------------------------------------------------------
#  error analysis (val + dev_heldout only)
# ---------------------------------------------------------------------
def error_groups(preset, top=10, split="dev_heldout"):
    """The largest error groups (label x language x doc type x kind) of
    one split. Section 25 asks for dev_heldout only."""
    path = config.runs_dir(preset) / "errors_dev.jsonl"
    if not path.exists():
        return []
    groups = collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if not e["chunk"].startswith(split + "-"):
                continue
            groups[(e["label"], e["lang"], e["doc_type"], e["kind"])].append(
                e)
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))[:top]
    return ranked


def short_example(e):
    """One short example of an error: the value, and a few characters of
    text around it."""
    value = (e.get("gold") or e.get("pred") or "").replace("\n", " ")
    context = (e.get("context") or "").replace("\n", " | ")
    at = context.find(value) if value else -1
    if at >= 0:
        context = context[max(0, at - 30):at + len(value) + 30]
    else:
        context = context[:80]
    text = "`%s`" % value[:50].replace("`", "'")
    if e.get("kind") in ("wrong_label", "role_swap") and e.get("pred_label"):
        text += " as %s" % e["pred_label"]
    if e.get("kind") == "boundary" and e.get("pred") is not None:
        text += " (marked `%s`)" % e["pred"][:50].replace("`", "'")
    return text + " in \"%s\"" % context.replace("`", "'").replace("|", "/")


def parameter_count(preset):
    """Parameters of the preset's model: recorded by fine-tuning, or
    read from the pretraining line of the build log."""
    n = done(preset, "finetune").get("numbers", {}).get("parameters")
    if n:
        return "%.1fM" % (n / 1e6)
    log = config.runs_dir(preset) / "build.log"
    if log.exists():
        m = re.findall(r"([\d.]+)M parameters",
                       log.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m[-1] + "M"
    return None


# ---------------------------------------------------------------------
def write(log=print):
    runs = presets_run()
    env = read_json(HERE / "runs" / "env.json") or {}
    parts = ["# REPORT - The Extractor %s" % config.VERSION]
    # 1. summary
    main = runs[-1] if runs else None
    ev_main = read_json(config.runs_dir(main) / "eval.json") if main else {}
    summary = []
    if main:
        gate = gate_rows(main, ev_main)
        fails = [r for r in gate if r[4] == "FAIL"]
        sp = ev_main.get("splits") or {}

        def f1_of(split):
            v = (sp.get(split) or {}).get("strict", {}).get("f1")
            return "%.3f" % v if v is not None else "-"
        hw = (ev_main.get("handwritten") or {}).get("strict", {}).get("f1")
        summary.append(
            "Presets run: %s%s. The last one, **%s**, was %s: strict "
            "micro-F1 test_seen %s, test_heldout %s, test_locale %s, "
            "handwritten %s." % (
                ", ".join(runs), "" if "full" in runs else
                " (not full: no GPU here)", main,
                "evaluated on val and dev_heldout only (dev-only run)"
                if ev_main.get("dev_only") else "evaluated on every set",
                f1_of("test_seen"), f1_of("test_heldout"),
                f1_of("test_locale"),
                "%.3f" % hw if hw is not None else "-"))
        if main == "full":
            summary.append("Gate (section 17): %s." % (
                "PASSED" if not fails else "FAILED on %d line(s)" %
                len(fails)))
        else:
            summary.append("No gate for %s (section 17); %d of the full "
                           "gate's lines would fail." % (main, len(fails)))
    summary.append("Most important next step: build the full model on a "
                   "GPU - `py build.py full` on the desktop, or the "
                   "MEGA9 /train card.")
    parts.append("## 1. Summary\n\n" + "  \n".join(summary))
    # 2. environment
    rows = [[k, env.get(k)] for k in ("os", "python", "torch", "backend",
                                       "gpu", "device_name",
                                       "device_memory_gb", "cpu_count",
                                       "ram_gb", "free_disk_gb",
                                       "wiki_reachable")]
    wiki = []
    for p in runs:
        stats = read_json(config.corpus_dir(p) / "corpus_stats.json") or {}
        wiki.append("%s: Wikipedia %s %s" % (p, stats.get("wiki", "?"), {
            k: "%.1fM" % (v.get("chars", 0) / 1e6)
            for k, v in (stats.get("languages") or {}).items()} or ""))
    parts.append("## 2. Environment\n\n" + md_table(["item", "value"], rows)
                 + "\n\n" + "  \n".join(wiki))
    # 3. data
    data_parts = []
    for p in runs:
        ds = read_json(config.runs_dir(p) / "data_stats.json") or {}
        rows = [[split, s["folders"], s["docs"], s["chunks"],
                 "%.1f%%" % (100 * s["empty"] / max(1, s["chunks"])),
                 " ".join("%s %d" % kv for kv in sorted(
                     s["by_lang"].items()))]
                for split, s in ds.items()]
        data_parts.append("### %s\n\n" % p + md_table(
            ["split", "folders", "documents", "chunks", "empty chunks",
             "chunks per language"], rows))
        tr = ds.get("train")
        if tr:
            data_parts.append("Train chunks per document type: " + ", ".join(
                "%s %d" % kv for kv in sorted(tr["by_doc_type"].items())) +
                ".  \nPer source format: " + ", ".join(
                "%s %d" % kv for kv in sorted(tr["by_source"].items())) +
                ".  \nSpans per label: " + ", ".join(
                "%s %d" % kv for kv in sorted(tr["by_label"].items())) + ".")
        checks = config.data_dir(p) / "checks.txt"
        if checks.exists():
            data_parts.append("Generator self-checks (10.9):\n\n```\n" +
                              checks.read_text(encoding="utf-8") + "```")
        tok = read_json(config.runs_dir(p) / "tokenizer_report.json")
        if tok:
            data_parts.append(
                "Boundary rate %.3f%% (%d spans of val + dev_heldout). "
                "Characters per token (val): %s." % (
                    100 * tok["boundary_rate"], tok["boundary_spans"],
                    ", ".join("%s %.2f" % kv for kv in
                              tok["chars_per_token"].items())))
            if tok.get("boundary_failures"):
                data_parts.append("Boundary failures (up to 20): " +
                                  "; ".join("%s %r" % (x["label"], x["span"])
                                            for x in tok["boundary_failures"]))
    parts.append("## 3. Data\n\n" + "\n\n".join(data_parts))
    # 4. models
    rows = []
    for p in runs:
        pre = done(p, "pretrain").get("numbers", {})
        ft = done(p, "finetune").get("numbers", {})
        cal = read_json(config.runs_dir(p) / "calibration.json") or {}
        s = config.PRESETS[p]
        rows.append([p, parameter_count(p),
                     "%d/%d/%d/%d" % (s["d_model"], s["n_layer"],
                                      s["n_head"], s["ffn_hidden"]),
                     s["vocab_size"], pre.get("steps"), pre.get("minutes"),
                     pre.get("eval_loss"), pre.get("masked_accuracy"),
                     ft.get("steps"), ft.get("train_minutes"),
                     ft.get("final_loss"), ft.get("chosen_step"),
                     ft.get("dev_heldout_f1"), cal.get("temperature")])
    parts.append("## 4. Models\n\n" + md_table(
        ["preset", "parameters", "d/layers/heads/ffn", "vocab",
         "pretrain steps", "pretrain min", "final MLM loss (held-out)",
         "masked-LM accuracy", "finetune steps", "finetune min",
         "final finetune loss", "chosen step",
         "dev_heldout F1 (sample, no thresholds)", "temperature"], rows) +
        "\n\nThe fine-tuning loss is CE(tokens) + 0.3 CE(doc type) + 0.1 "
        "CE(language), smoothed over the last steps. The masked-LM numbers "
        "are measured on held-out Wikipedia and synthetic text.")
    # 5. results
    res = []
    dec = (HERE / "DECISIONS.md").read_text(encoding="utf-8") \
        if (HERE / "DECISIONS.md").exists() else ""
    for p in runs:
        ev = read_json(config.runs_dir(p) / "eval.json") or {}
        res.append("### %s%s\n\n" % (p, " (dev-only)" if ev.get("dev_only")
                                     else "") + md_table(
            ["#", "measure", "target (full)", "measured", "result"],
            gate_rows(p, ev)))
        # the diagnosis of the lines that fail, written in DECISIONS.md
        m = re.search(r"## Diagnosis - %s\n(.*?)(\n## |\Z)" % re.escape(p),
                      dec, re.S)
        if m:
            res.append("**Diagnosis (%s):**\n\n%s" % (p, m.group(1).strip()))
    if main:
        cal = read_json(config.runs_dir(main) / "calibration.json") or {}
        ev = ev_main
        if cal:
            details = cal.get("details", {})
            rules = collections.Counter(d.get("rule") for d in
                                        details.values())
            eces = ", ".join("%s %.4f" % (split, v["ece"]) for split, v in
                             (ev.get("splits") or {}).items()
                             if v.get("ece") is not None)
            res.append("### Calibration (%s)\n\nTemperature %.2f and the "
                       "per-label thresholds are fitted on dev_heldout "
                       "(rules: %s). Expected calibration error (10 bins) "
                       "of the accepted span scores, per split: %s." % (
                           main, cal.get("temperature", 0),
                           ", ".join("%d by '%s'" % (n, r) for r, n in
                                     rules.most_common()), eces) + "\n\n" +
                       md_table(["label", "threshold", "rule", "precision",
                                 "recall", "predicted", "gold"],
                                [[k, d.get("tau"), d.get("rule"),
                                  d.get("precision"), d.get("recall"),
                                  d.get("predicted"), d.get("gold")]
                                 for k, d in details.items()]))
        tables = config.runs_dir(main) / "eval_tables.md"
        if tables.exists():
            body = tables.read_text(encoding="utf-8")
            body = re.sub(r"^# .*\n", "", body, count=1)
            body = re.sub(r"^## ", "### ", body, flags=re.M)
            res.append("### Detailed tables (%s)\n\nThe same tables are "
                       "in `runs/%s/eval_tables.md`.\n%s" % (main, main,
                                                              body))
    parts.append("## 5. Results\n\n" + "\n\n".join(res))
    # 6. error analysis
    ea = []
    if main:
        for (label, lang, doc, kind), items in error_groups(main):
            ea.append([label, lang, doc, kind, len(items),
                       "<br>".join(short_example(e) for e in items[:2])])
    parts.append("## 6. Error analysis (dev_heldout only)\n\n" + (
        "The ten largest groups of errors of the last model on "
        "dev_heldout, by label x language x document type x kind.\n\n" +
        md_table(["label", "lang", "doc type", "kind", "count",
                  "two examples"], ea) if ea else "No errors file."))
    # 7. improvement rounds, 8. deviations: from DECISIONS.md
    dec = (HERE / "DECISIONS.md").read_text(encoding="utf-8") \
        if (HERE / "DECISIONS.md").exists() else ""
    m = re.search(r"## Improvement rounds\n(.*?)(\n## |\Z)", dec, re.S)
    parts.append("## 7. Improvement rounds\n\n" + (
        m.group(1).strip() if m else "None yet."))
    heads = re.findall(r"^## (.+)$", dec, re.M)
    parts.append("## 8. Deviations and decisions\n\nEvery decision is in "
                 "`DECISIONS.md`, by topic: " + ", ".join(heads) + ".")
    parts.append("""## 9. Known limits

* The training data is synthetic: generated documents in ten languages,
  plus Wikipedia for pretraining. Real documents will surprise it; the
  handwritten set is the closest measure of that.
* No OCR: scanned PDFs give no text to ingest.py, so nothing to extract.
* Arabic PDFs may come out of pdfplumber in visual (reversed) order.
* Hindi PDFs with legacy fonts may garble the vowel signs.
* Languages outside the ten are not supported (the language head will
  still name one of the ten).""")
    parts.append("""## 10. Next steps for Laurent

**Build the full model** on the desktop (GPU). In PowerShell:

```powershell
cd "C:\\Users\\neomh\\new model\\extractor"
```

```powershell
py check.py
```

```powershell
py build.py full
```

Or upload `extractor-package.zip` to the /train card and choose MEGA9.
It takes about 6 to 10 hours; it writes `extractor-1.0.0.pt` and a new
`REPORT.md` with the gate of section 17.

**Use it on a real folder.** Copy `extractor-1.0.0.pt` to
`C:\\Users\\Laurent\\new model\\extractor` on the laptop, then:

```powershell
cd "C:\\Users\\Laurent\\new model"
```

```powershell
py ingest.py "C:\\Users\\Laurent\\documents to publish"
```

```powershell
cd "C:\\Users\\Laurent\\new model\\extractor"
```

```powershell
py extract_db.py "C:\\Users\\Laurent\\new model\\documents.db"
```

```powershell
py profile.py "C:\\Users\\Laurent\\new model\\documents.db"
```

**Measure it on real documents.** Label a few real chunks in
`real_eval\\` (see `README.md`), then, on the desktop:

```powershell
py build.py full --from evaluate
```""")
    # how the files reached Laurent (for example a model file sent in
    # parts), written in DECISIONS.md
    m = re.search(r"## Delivery\n(.*?)(\n## |\Z)", dec, re.S)
    if m:
        parts.append("### Delivery\n\n" + m.group(1).strip())
    path = HERE / "REPORT.md"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    log("REPORT.md written")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    write()
