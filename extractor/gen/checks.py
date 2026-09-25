"""
checks.py - the generator self-checks of section 10.9.

    py gen/make.py --preset smoke --check

reads data/<preset>/*.jsonl.gz (generate first) and prints one line per
check: PASS or FAIL, with the numbers. Check 7 (boundary rate) runs later,
in the tokenizer stage of build.py.
"""
import collections
import gzip
import json
import pathlib
import random
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config                                            # noqa: E402
from gen import data as D                                # noqa: E402
from gen import holdout as H                             # noqa: E402

# trap rates of section 10.6: (trap, what is counted, minimum share)
TRAP_T10_COUNTRIES = {"IN", "FR", "MA", "CN", "TW", "SA", "AE", "EG", "KR"}


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


class Report:
    def __init__(self, log=print):
        self.ok = True
        self.log = log
        self.lines = []

    def result(self, name, passed, detail):
        self.ok = self.ok and passed
        line = "%s  %-34s %s" % ("PASS" if passed else "FAIL", name, detail)
        self.lines.append(line)
        self.log(line)


# ---------------------------------------------------------------------
#  1. spans
# ---------------------------------------------------------------------
# splits whose individual examples must never be read (section 11)
PROTECTED = {"test_heldout", "test_locale", "test_seen"}


def example(c, text):
    """An example for a message - or only its id's split for protected
    splits, whose content must never be shown."""
    if c["split"] in PROTECTED:
        return "(%s example hidden)" % c["split"]
    return text


def check_spans(chunks):
    """0 <= start < end <= len(text), no whitespace at the edges, a label
    of the schema, no overlap. Returns a list of problems."""
    problems = []
    labels = set(config.TYPES)
    for c in chunks:
        text = c["text"]
        last_end = -1
        for s, e, label in sorted(c["spans"]):
            where = example(c, "%s [%d:%d] %s" % (c["id"], s, e, label))
            if not (0 <= s < e <= len(text)):
                problems.append("bounds " + where)
                continue
            if label not in labels:
                problems.append("label " + where)
            piece = text[s:e]
            if piece != piece.strip():
                problems.append("whitespace %s %s" % (where, example(
                    c, repr(piece))))
            if s < last_end:
                problems.append("overlap " + where)
            last_end = max(last_end, e)
        for s, e in c.get("cut", []):
            if not (0 <= s < e <= len(text)):
                problems.append(example(c, "cut bounds %s [%d:%d]" % (
                    c["id"], s, e)))
    return problems


# ---------------------------------------------------------------------
#  2. truth entries, and chunks equal to the verbatim ingest.py output
# ---------------------------------------------------------------------
def check_truth(chunks):
    missing, total = [], 0
    for c in chunks:
        if c["noised"]:
            continue
        for i, (s, e, label) in enumerate(c["spans"]):
            if label in config.KIND_OF_LABEL:
                total += 1
                if str(i) not in c["truth"]:
                    missing.append(example(c, "%s %s %r" % (
                        c["id"], label, c["text"][s:e])))
    return missing, total


def check_verbatim(n_docs=1000, split="train", seed=11):
    """Re-generates folders of the split and compares, document by
    document, the annotated chunk texts with what the VERBATIM ingest.py
    functions return for the same plain rendering."""
    import gen.layouts                                   # noqa: F401
    from gen import make
    from gen import render as R
    docs = bad = 0
    examples = []
    index = 0
    while docs < n_docs and index < 5000:
        built = make.make_folder_docs(split, index)
        index += 1
        for doc_id, texts, sources in built:
            docs += 1
            want = R.verbatim_texts(sources)
            if texts != want:
                bad += 1
                if len(examples) < 3:
                    examples.append((doc_id, texts, want))
    return docs, bad, examples


# ---------------------------------------------------------------------
#  3. label-free chunks and languages
# ---------------------------------------------------------------------
def check_mix(chunks):
    n = len(chunks)
    empty = sum(1 for c in chunks if not c["spans"])
    by_lang = collections.Counter(c["lang"] for c in chunks)
    return n, empty, by_lang


# ---------------------------------------------------------------------
#  4. trap rates (section 10.6)
# ---------------------------------------------------------------------
def trap_rates(chunks):
    """-> {trap: (share, minimum, what)}."""
    docs = collections.defaultdict(lambda: {"traps": set(), "type": None,
                                            "country": None, "chunks": 0})
    by_type_chunks = collections.defaultdict(list)
    for c in chunks:
        d = docs[c["doc"]]
        d["traps"].update(c["traps"])
        d["type"] = c["doc_type"]
        d["layout"] = c["layout"]
        d["country"] = c["locale"].split("-")[1]
        d["chunks"] += 1
        by_type_chunks[c["doc_type"]].append(set(c["traps"]))

    def doc_share(trap, types, countries=None, exclude=None,
                  invoices_only=False):
        pool = [d for d in docs.values() if d["type"] in types and
                (countries is None or d["country"] in countries) and
                (exclude is None or d["country"] not in exclude) and
                (not invoices_only or d["layout"].startswith("invoice."))]
        if not pool:
            return None
        return sum(1 for d in pool if trap in d["traps"]) / len(pool)

    def chunk_share(trap, types):
        pool = [t for ty in types for t in by_type_chunks.get(ty, [])]
        if not pool:
            return None
        return sum(1 for t in pool if trap in t) / len(pool)

    inv = ["invoice"]
    # "every invoice": real invoices (a till receipt or a credit note has
    # no due date and is not an invoice)
    out = {
        "T1 invoices": (doc_share("T1", inv, invoices_only=True), 0.97),
        "T1 brochure+financial chunks": (
            chunk_share("T1", ["brochure", "financials"]), 0.10),
        "T2 financial statements": (doc_share("T2", ["financials"]), 0.97),
        "T3 financial statements": (doc_share("T3", ["financials"]), 0.60),
        "T4 invoices": (doc_share("T4", inv), 0.20),
        "T5 brochure chunks": (chunk_share("T5", ["brochure"]), 0.15),
        "T6 invoices": (doc_share("T6", inv, invoices_only=True), 0.97),
        "T7 brochure chunks": (chunk_share("T7", ["brochure"]), 0.20),
        "T8 brochure chunks": (chunk_share("T8", ["brochure"]), 0.20),
        "T9 invoices": (doc_share("T9", inv), 0.30),
        "T10 invoices (listed countries)": (
            doc_share("T10", inv, countries=TRAP_T10_COUNTRIES,
                      invoices_only=True), 0.30),
        "T10 invoices (elsewhere)": (
            doc_share("T10", inv, exclude=TRAP_T10_COUNTRIES,
                      invoices_only=True), 0.10),
        "T11 letters+brochures": (doc_share("T11", ["letter", "brochure"]),
                                  0.20),
        "T12 chunks": (sum(1 for c in chunks if not c["spans"]) /
                       max(1, len(chunks)), 0.20),
        "T13 brochure chunks": (chunk_share("T13", ["brochure"]), 0.10),
        "T14 registration+financials": (
            doc_share("T14", ["registration", "financials"]), 0.97),
        "T15 invoices": (doc_share("T15", inv, invoices_only=True),
                         0.97),
    }
    return out


# ---------------------------------------------------------------------
#  5. normalize() gives back the truth
# ---------------------------------------------------------------------
def same_value(kind, got, want):
    if got is None:
        return False
    if kind == "amount":
        return abs(got.get("value", -1) - want["value"]) < 0.005 and \
            (want.get("currency") is None or
             got.get("currency") in (None, want["currency"]))
    if kind == "date":
        return all(got.get(k) == want.get(k) for k in ("year", "month",
                                                       "day"))
    if kind == "year":
        return got.get("year") == want.get("year")
    if kind == "count":
        return got.get("value") == want.get("value") and \
            got.get("qualifier") == want.get("qualifier")
    if kind == "phone":
        return got.get("e164") == want.get("e164")
    if kind == "email":
        return got.get("value") == want.get("value")
    if kind == "url":
        return got.get("host") == want.get("host")
    if kind == "reg_id":
        return got.get("compact") == want.get("compact")
    if kind == "legal_form":
        return got.get("code") == want.get("code")
    if kind == "activity_code":
        return got.get("code") == want.get("code")
    return got == want


def check_normalize(chunks, with_country=True, failures=None):
    import normalize
    ok = total = 0
    for c in chunks:
        if c["noised"]:
            continue
        country = c["locale"].split("-")[1] if with_country else None
        for i, (s, e, label) in enumerate(c["spans"]):
            want = c["truth"].get(str(i))
            if want is None:
                continue
            kind = config.KIND_OF_LABEL[label]
            got = normalize.normalize(label, c["text"][s:e], lang=c["lang"],
                                      country=country)
            total += 1
            if same_value(kind, got, want):
                ok += 1
            elif failures is not None and len(failures) < 200 and \
                    c["split"] not in PROTECTED:
                failures.append((c["id"], label, c["text"][s:e], want, got))
    return ok, total


# ---------------------------------------------------------------------
#  6. hold-out, by id
# ---------------------------------------------------------------------
def check_holdout(split, chunks, folders):
    """Returns a list of problems for one split."""
    problems = []
    heldout_locales = {c for c, l in D.locales()["locales"].items()
                       if l["heldout"]}
    for c in chunks:
        lg = H.layout_group(c["layout"])
        groups = {lg}
        key = D.locale(c["locale"])["data"]
        for tid in c["templates"]:
            if tid.count(".") >= 2:              # sentence templates
                groups.add(H.group_of(key, tid))
        if split in ("train", "val", "test_seen", "traps"):
            if groups & {"D", "T"}:
                problems.append("%s uses %s" % (c["id"], sorted(
                    groups & {"D", "T"})))
        if split == "dev_heldout" and "T" in groups:
            problems.append("%s uses a T item" % c["id"])
        if split == "test_heldout" and "D" in groups:
            problems.append("%s uses a D item" % c["id"])
        if split != "test_locale" and (c["locale"] in heldout_locales or
                                       lg == "locale"):
            problems.append("%s: held-out locale" % c["id"])
        if split == "test_locale" and groups & {"D", "T"}:
            problems.append("%s: test_locale uses %s" % (c["id"], groups))
    for f in folders:
        act = H.activity_group(D.activity(f["activity_id"]))
        if split in ("train", "val", "test_seen", "traps", "test_locale") \
                and act in ("D", "T"):
            problems.append("%s: held-out activity" % f["folder"])
        if split == "dev_heldout" and act == "T":
            problems.append("%s: T activity" % f["folder"])
        if split == "test_heldout" and act == "D":
            problems.append("%s: D activity" % f["folder"])
        if split != "test_locale":
            bad = set(f.get("partner_locales", [])) & heldout_locales
            if bad:
                problems.append("%s: client / supplier from %s" %
                                (f["folder"], sorted(bad)))
    return problems


def check_heldout_content(split, chunks, folders):
    """A dev_heldout / test_heldout folder uses a held-out activity, or
    has a held-out layout in every document whose type has one."""
    want = "D" if split == "dev_heldout" else "T"
    import gen.layouts                                   # noqa: F401
    from gen.layouts.common import REGISTRY
    types_with = collections.defaultdict(set)
    for lid, info in REGISTRY.items():
        g = H.layout_group(lid)
        if g == want:
            key = info["doc_type"]
            types_with[key].add(
                tuple(info.get("locales") or []) if key == "registration"
                else None)
    by_folder = collections.defaultdict(lambda: collections.defaultdict(
        list))
    for c in chunks:
        by_folder[c["folder"]][c["doc"]].append(c)
    bad = 0
    for f in folders:
        if H.activity_group(D.activity(f["activity_id"])) == want:
            continue
        for doc_id, cs in by_folder.get(f["folder"], {}).items():
            c = cs[0]
            t = c["doc_type"]
            if t not in types_with:
                continue
            if t == "registration" and not any(
                    c["locale"] in locs for locs in types_with[t] if locs):
                continue          # no held-out layout for this country
            key = D.locale(c["locale"])["data"]
            groups = {H.layout_group(c["layout"])}
            for x in cs:
                groups |= {H.group_of(key, tid) for tid in x["templates"]
                           if tid.count(".") >= 2}
            if want not in groups:
                bad += 1
                break
    return bad, len(folders)


# ---------------------------------------------------------------------
#  8. Faker rule
# ---------------------------------------------------------------------
def check_faker():
    from gen import faker_check
    return faker_check.verify()


# ---------------------------------------------------------------------
def run(preset, log=print):
    rep = Report(log)
    data_dir = config.data_dir(preset)
    if not (data_dir / "train.jsonl.gz").exists():
        log("no data in %s - run: py gen/make.py --preset %s" %
            (data_dir, preset))
        return False
    splits = {}
    folders = {}
    for split in config.SPLITS:
        path = data_dir / ("%s.jsonl.gz" % split)
        if path.exists():
            splits[split] = list(read(path))
            folders[split] = list(read(data_dir /
                                       ("folders_%s.jsonl.gz" % split)))
    everything = [c for chunks in splits.values() for c in chunks]
    train = splits["train"]

    # 1
    problems = check_spans(everything)
    rep.result("1 spans valid", not problems, "%d chunks, %d problems %s" % (
        len(everything), len(problems), problems[:3]))
    # 2
    missing, total = check_truth(everything)
    rep.result("2a truth for normalizable spans", not missing,
               "%d spans, %d without truth %s" % (total, len(missing),
                                                  missing[:3]))
    docs, bad, examples = check_verbatim()
    detail = "%d documents, %d differ" % (docs, bad)
    if examples:
        doc_id, got, want = examples[0]
        detail += " e.g. %s: %r vs %r" % (doc_id, got[:2], want[:2])
    rep.result("2b chunks == verbatim ingest.py", bad == 0 and docs >= 1000,
               detail)
    # 3
    n, empty, by_lang = check_mix(train)
    rep.result("3a label-free train chunks", empty / max(1, n) >= 0.20,
               "%.1f%% of %d" % (100 * empty / max(1, n), n))
    shares = {lg: by_lang.get(lg, 0) / max(1, n) for lg in config.LANGS}
    worst = max(abs(v - 0.10) for v in shares.values())
    rep.result("3b languages 10% +- 2 points", worst <= 0.02,
               " ".join("%s %.1f" % (lg, 100 * v) for lg, v in
                        shares.items()))
    # 4
    rates = trap_rates(train)
    for name, (share, minimum) in rates.items():
        if share is None:
            rep.result("4 " + name, False, "no documents to measure")
            continue
        rep.result("4 " + name, share >= minimum,
                   "%.1f%% (min %.0f%%)" % (100 * share, 100 * minimum))
    # 5
    try:
        failures = []
        ok, total = check_normalize(everything, True, failures)
        rate = ok / max(1, total)
        rep.result("5 normalize() == truth (country)", rate >= 0.99,
                   "%.2f%% of %d" % (100 * rate, total))
        ok2, total2 = check_normalize(everything, False)
        log("      normalize() with the language only: %.2f%% of %d" %
            (100 * ok2 / max(1, total2), total2))
        if failures:
            path = data_dir / "normalize_failures.jsonl"
            with open(path, "w", encoding="utf-8") as f:
                for row in failures:
                    f.write(json.dumps(row, ensure_ascii=False,
                                       default=str) + "\n")
            log("      first failures written to %s" % path)
    except ImportError as exc:
        rep.result("5 normalize() == truth", False, "normalize.py: %s" %
                   exc)
    # 6
    all_problems = []
    for split, chunks in splits.items():
        all_problems += check_holdout(split, chunks, folders[split])
    rep.result("6a hold-out ids", not all_problems, "%d problems %s" % (
        len(all_problems), all_problems[:3]))
    for split in ("dev_heldout", "test_heldout"):
        if split in splits:
            bad, total = check_heldout_content(split, splits[split],
                                               folders[split])
            rep.result("6b %s content rule" % split, bad == 0,
                       "%d of %d folders break it" % (bad, total))
    # 8
    try:
        ok8, detail8 = check_faker()
        rep.result("8 Faker rule", ok8, detail8)
    except ImportError as exc:
        rep.result("8 Faker rule", False, str(exc))
    log("ALL CHECKS PASS" if rep.ok else "SOME CHECKS FAIL")
    with open(data_dir / "checks.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lines) + "\n")
    return rep.ok


def nfkc(text):
    return unicodedata.normalize("NFKC", text)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = run(sys.argv[1] if len(sys.argv) > 1 else "smoke")
    sys.exit(0 if ok else 1)
