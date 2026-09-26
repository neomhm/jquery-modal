"""
gen/checks.py - the generator self-checks of section 10.8. They MUST pass
before training:

  1. every task passes the self-check; at most 0.5% discarded
  2. every program is canonical
  3. every trap reaches its rate; every family appears; each language is
     10% +- 2 points
  4. 1% real-file round trip: identical previews
  5. helpers return the truth for >= 99.5% of generated values
  6. hold-out rules of every split (section 11)
  7. preview + program <= 4,096 tokens for >= 99% of tasks (once the
     tokenizer exists)
  8. NFKC(program) == program, every lookup key appears in the preview

Only aggregate numbers are computed for the test splits: no example is
printed from them.
"""
import ast
import json
import unicodedata

import config
import tulipscript as ts

# section 10.4: (trap, rate, which tasks count)
AMOUNT_TARGETS = ("products", "services", "bookings", "invoice_ledger")
TRAP_RULES = [
    ("T1", 0.30, "products", lambda t: t["answer"] == "products"),
    ("T2", 0.20, "products and services",
     lambda t: t["answer"] in ("products", "services")),
    ("T3", 0.10, "products", lambda t: t["answer"] == "products"),
    ("T4", 0.40, "tables with >= 8 rows",
     lambda t: t["answer"] in config.TARGETS and t["n_rows"] >= 8),
    ("T5", 0.50, "tables", lambda t: t["answer"] in config.TARGETS),
    ("T6", 0.10, "tables", lambda t: t["answer"] in config.TARGETS),
    ("T7", 0.25, "products and services",
     lambda t: t["answer"] in ("products", "services")),
    ("T8", 0.15, "products", lambda t: t["answer"] == "products"),
    ("T8", 0.40, "opening_hours", lambda t: t["answer"] == "opening_hours"),
    ("T9", 0.15, "tables", lambda t: t["answer"] in config.TARGETS),
    ("T10", 0.50, "staff", lambda t: t["answer"] == "staff"),
    ("T10", 0.30, "clients", lambda t: t["answer"] == "clients"),
    ("T11", 0.40, "bookings", lambda t: t["answer"] == "bookings"),
    ("T12", 0.70, "bookings and ledgers",
     lambda t: t["answer"] in ("bookings", "invoice_ledger")),
    ("T13", 0.30, "amount tables",
     lambda t: t["answer"] in AMOUNT_TARGETS and "amount(" in t["program"]),
    ("T14", 0.20, "tables", lambda t: t["answer"] in config.TARGETS),
]
SHARE_RULES = [("missing_required (T15)", 0.035,
                lambda t: t["answer"].startswith("missing_required")),
               ("no_matching_target", 0.06,
                lambda t: t["answer"] == "no_matching_target"),
               ("not_a_table", 0.02, lambda t: t["answer"] == "not_a_table"),
               ("too_wide", 0.005, lambda t: t["answer"] == "too_wide")]


def lookup_keys(program):
    keys = []
    for node in ast.walk(ast.parse(program)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == \
                "lookup" and len(node.args) == 2 and \
                isinstance(node.args[1], ast.Dict):
            keys += [k.value for k in node.args[1].keys]
    return keys


def values_line(preview):
    return "\n".join(line for line in preview.splitlines()
                     if line.startswith("VALUES "))


def run(preset, token_counts=None):
    """-> report dict. token_counts: {task id: tokens} once the
    tokenizer exists (check 7)."""
    from gen import make
    from gen import tasks as T
    stats = json.loads((config.data_dir(preset) / "stats.json")
                       .read_text(encoding="utf-8"))
    report = {"preset": preset, "checks": [], "passed": True}

    def check(name, ok, detail):
        report["checks"].append({"check": name, "ok": bool(ok),
                                 "detail": detail})
        if not ok:
            report["passed"] = False

    # only the light fields of every task (a split can be gigabytes)
    keep = ("id", "lang", "locale", "family", "traps", "answer", "program",
            "holdout", "n_rows")

    def light(t):
        out = dict((k, t.get(k)) for k in keep)
        out["values"] = values_line(t["preview"])
        return out
    splits = dict((s, [light(t) for t in make.iter_split(preset, s)])
                  for s in config.SPLITS)
    everything = [t for s in config.SPLITS for t in splits[s]]
    # 1. discards
    tried = sum(v["made"] + v["duplicates"] + v["discards"]
                for v in stats["splits"].values())
    discards = sum(v["discards"] for v in stats["splits"].values())
    failed = sum(v["failed"] for v in stats["splits"].values())
    share = discards / max(1, tried)
    check("1 self-check discards <= 0.5%", share <= 0.005,
          "%d discards of %d tasks (%.2f%%); %d tasks could not be made" %
          (discards, tried, 100 * share, failed))
    # 2. canonical
    bad = sum(1 for t in everything if ts.canonical(t["program"]) !=
              t["program"])
    check("2 programs canonical", bad == 0, "%d not canonical" % bad)
    # 3. traps, families, languages (on train)
    train = splits["train"]
    lines = []
    ok3 = True
    for trap, rate, label, where in TRAP_RULES:
        pool = [t for t in train if where(t)]
        if not pool:
            lines.append("%s: no %s" % (trap, label))
            ok3 = False
            continue
        got = sum(1 for t in pool if trap in t["traps"]) / len(pool)
        good = got >= rate
        ok3 = ok3 and good
        lines.append("%s %.0f%% of %s (needs %.0f%%)%s" % (
            trap, 100 * got, label, 100 * rate, "" if good else "  <- LOW"))
    for label, rate, where in SHARE_RULES:
        got = sum(1 for t in train if where(t)) / max(1, len(train))
        good = abs(got - rate) <= max(0.01, rate * 0.3)
        ok3 = ok3 and good
        lines.append("%s %.1f%% of tasks (%.1f%%)%s" % (
            label, 100 * got, 100 * rate, "" if good else "  <- OFF"))
    hold = T.holdout()
    fams = T.families()
    missing = []
    for fid in fams:
        group = T.group_of_family(fid, hold)
        split = {"train": "train", "D": "dev_heldout",
                 "T": "test_heldout"}[group]
        if not any(t["family"] == fid for t in splits[split]):
            missing.append(fid if group != "T" else "(a T family)")
    if missing:
        ok3 = False
        lines.append("families never used: %s" % ", ".join(missing[:10]))
    else:
        lines.append("every family appears in its splits")
    langs = dict((l, sum(1 for t in train if t["lang"] == l)
                  / max(1, len(train))) for l in config.LANGS)
    lang_ok = all(abs(v - 0.10) <= 0.02 for v in langs.values())
    ok3 = ok3 and lang_ok
    lines.append("languages: " + ", ".join("%s %.1f%%" % (l, 100 * v)
                                           for l, v in langs.items()))
    check("3 traps, families, languages", ok3, "\n".join(lines))
    # 4. round trips
    n_rt = sum(v["round_trips"] for v in stats["splits"].values())
    fails = [f for v in stats["splits"].values()
             for f in v["round_trip_failures"]]
    check("4 real-file round trip (1%)", n_rt > 0 and not fails,
          "%d files, %d with a different preview" % (n_rt, len(fails)))
    # 5. helper values
    values = sum(v["values"] for v in stats["splits"].values())
    wrong = sum(v["wrong_values"] for v in stats["splits"].values())
    share = 1 - wrong / max(1, values)
    check("5 helpers give the truth >= 99.5%", share >= 0.995,
          "%.3f%% of %d values" % (100 * share, values))
    # 6. hold-out rules
    problems = collections_counter()
    held_locales = set(T.HELD_OUT_LOCALES)
    for split, tasks in splits.items():
        for t in tasks:
            groups = set(t.get("holdout") or [])
            if split in ("train", "val", "test_seen", "traps",
                         "test_locale") and groups:
                problems["%s has hold-out items" % split] += 1
            if split == "dev_heldout" and ("D" not in groups or
                                           "T" in groups):
                problems["dev_heldout rule"] += 1
            if split == "test_heldout" and ("T" not in groups or
                                            "D" in groups):
                problems["test_heldout rule"] += 1
            if (t["locale"] in held_locales) != (split == "test_locale"):
                problems["held-out locale in %s" % split] += 1
    check("6 hold-out rules", not problems,
          "; ".join("%s: %d" % kv for kv in problems.items()) or "all kept")
    # 7. token lengths
    if token_counts:
        over = sum(1 for n in token_counts.values() if n > 4096)
        share = over / max(1, len(token_counts))
        check("7 preview + program <= 4,096 tokens for >= 99%",
              share <= 0.01, "%d of %d over (%.2f%%)" % (
                  over, len(token_counts), 100 * share))
    else:
        report["checks"].append({"check": "7 token lengths", "ok": True,
                                 "detail": "checked by the tokenizer "
                                           "stage (pack)"})
    # 8. NFKC and lookup keys
    bad_nfkc = sum(1 for t in everything
                   if unicodedata.normalize("NFKC", t["program"]) !=
                   t["program"])
    bad_keys = 0
    for t in everything:
        keys = lookup_keys(t["program"])
        if keys:
            shown = t["values"]
            bad_keys += sum(1 for k in keys if k not in shown)
    check("8 NFKC programs, lookup keys in the preview",
          bad_nfkc == 0 and bad_keys == 0,
          "%d programs not NFKC, %d lookup keys not in VALUES" % (
              bad_nfkc, bad_keys))
    report["splits"] = dict((s, len(v)) for s, v in splits.items())
    return report


def collections_counter():
    import collections
    return collections.Counter()


def format_report(report):
    out = ["Generator self-checks (section 10.8), preset %s" %
           report["preset"]]
    for c in report["checks"]:
        out.append("%s  %s" % ("PASS" if c["ok"] else "FAIL", c["check"]))
        for line in str(c["detail"]).splitlines():
            out.append("        " + line)
    out.append("ALL PASSED" if report["passed"] else "SOME CHECKS FAILED")
    return "\n".join(out)
