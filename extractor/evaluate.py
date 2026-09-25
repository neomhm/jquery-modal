"""
evaluate.py - stage "evaluate" (section 17).

    py evaluate.py pilot              every set, once, at the end
    py evaluate.py pilot --dev-only   val and dev_heldout only (rounds)

It scores runs/<preset>/model_eval.pt (written by calibrate.py):
  * spans: strict and relaxed micro-F1 on accepted spans, per label,
    language, document type and source format; role swaps;
  * document-type and language accuracy;
  * traps, trap by trap (the traps split);
  * folder level, end to end: each folder of test_heldout and test_seen
    becomes a documents.db, then extract_db -> verify -> profile, and the
    profile is compared with the folder truth;
  * calibration error, speed, the handwritten set, real_eval.
Writes runs/<preset>/eval.json and eval_tables.md.

Test discipline (section 11): this file only ever prints and writes
AGGREGATE numbers for the test splits and the handwritten set - never an
example. Examples (for error analysis) are written for val and
dev_heldout only, to runs/<preset>/errors_dev.jsonl.
"""
import argparse
import gzip
import json
import pathlib
import resource
import sys
import time
import unicodedata

import config
import extract_db
import gold
import normalize as N
import profile as PR

HERE = pathlib.Path(__file__).resolve().parent
ROLE_PAIRS = {"S_NAME": "C_NAME", "C_NAME": "S_NAME",
              "S_ADDRESS": "C_ADDRESS", "C_ADDRESS": "S_ADDRESS",
              "S_REG_ID": "C_REG_ID", "C_REG_ID": "S_REG_ID"}
FACT_TYPES = set(config.TYPES[10:])           # types 11-25
EXAMPLES_ALLOWED = {"val", "dev_heldout"}


# =====================================================================
#  span-level scoring
# =====================================================================
def read_split(preset, split):
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class Counts:
    """True positives, predicted and gold counts -> P, R, F1."""

    def __init__(self):
        self.tp = self.pred = self.gold = 0

    def add(self, tp, pred, gold):
        self.tp += tp
        self.pred += pred
        self.gold += gold

    def prf(self):
        p = self.tp / self.pred if self.pred else (1.0 if not self.gold
                                                   else 0.0)
        r = self.tp / self.gold if self.gold else (1.0 if not self.pred
                                                   else 0.0)
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {"precision": round(p, 4), "recall": round(r, 4),
                "f1": round(f, 4), "tp": self.tp, "pred": self.pred,
                "gold": self.gold}


def overlap(a, b):
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return inter / max(a[1] - a[0], b[1] - b[0]) if inter > 0 else 0.0


def score_chunks(chunks, preds):
    """All span-level numbers for one set of chunks."""
    micro, relaxed = Counts(), Counts()
    per = {"label": {}, "lang": {}, "doc_type": {}, "source": {}}
    role_total = role_swaps = 0
    doc_ok = lang_ok = 0
    bins = [[0, 0.0, 0] for _ in range(10)]      # n, sum score, correct
    empty_chunks = empty_false = 0
    for c, p in zip(chunks, preds):
        gold_set = {(s, e, lab) for s, e, lab in c["spans"]}
        acc = [x for x in p["spans"] if x["accepted"]]
        pred_set = {(x["start"], x["end"], x["label"]) for x in acc}
        tp = gold_set & pred_set
        micro.add(len(tp), len(pred_set), len(gold_set))
        # relaxed: same label, >= 50% character overlap (greedy)
        used, rtp = set(), 0
        for g in gold_set:
            for q in pred_set:
                if q not in used and q[2] == g[2] and overlap(g, q) >= 0.5:
                    used.add(q)
                    rtp += 1
                    break
        relaxed.add(rtp, len(pred_set), len(gold_set))
        for lab in {x[2] for x in gold_set | pred_set}:
            per["label"].setdefault(lab, Counts()).add(
                sum(1 for x in tp if x[2] == lab),
                sum(1 for x in pred_set if x[2] == lab),
                sum(1 for x in gold_set if x[2] == lab))
        for key, value in (("lang", c.get("lang")),
                           ("doc_type", c.get("doc_type")),
                           ("source", c.get("source", "handwritten"))):
            per[key].setdefault(value, Counts()).add(len(tp), len(pred_set),
                                                     len(gold_set))
        # role swaps: right text, S and C exchanged
        for s, e, lab in gold_set:
            if lab in ROLE_PAIRS:
                role_total += 1
                if (s, e, ROLE_PAIRS[lab]) in pred_set:
                    role_swaps += 1
        doc_ok += p["doc_type"] == c.get("doc_type")
        lang_ok += p["language"] == c.get("lang")
        for x in acc:
            b = min(9, int(x["score"] * 10))
            bins[b][0] += 1
            bins[b][1] += x["score"]
            bins[b][2] += (x["start"], x["end"], x["label"]) in gold_set
        if not gold_set:
            empty_chunks += 1
            empty_false += len(pred_set)
    n = sum(b[0] for b in bins)
    ece = sum(abs(b[2] / b[0] - b[1] / b[0]) * b[0] / n
              for b in bins if b[0]) if n else 0.0
    return {"chunks": len(chunks), "strict": micro.prf(),
            "relaxed": relaxed.prf(),
            "per_label": {k: v.prf() for k, v in sorted(per["label"].items())},
            "per_lang": {k: v.prf() for k, v in sorted(per["lang"].items())},
            "per_doc_type": {k: v.prf() for k, v in
                             sorted(per["doc_type"].items())},
            "per_source": {k: v.prf() for k, v in
                           sorted(per["source"].items())},
            "role_swap_rate": round(role_swaps / max(1, role_total), 4),
            "role_spans": role_total,
            "doc_type_accuracy": round(doc_ok / max(1, len(chunks)), 4),
            "language_accuracy": round(lang_ok / max(1, len(chunks)), 4),
            "ece": round(ece, 4),
            "false_spans_per_100_empty": round(
                100 * empty_false / max(1, empty_chunks), 2),
            "empty_chunks": empty_chunks}


def label_counts(chunks, preds, labels, only=None):
    c = Counts()
    for ch, p in zip(chunks, preds):
        gold_set = {(s, e, lab) for s, e, lab in ch["spans"]
                    if lab in labels}
        pred_set = {(x["start"], x["end"], x["label"]) for x in p["spans"]
                    if x["accepted"] and x["label"] in labels}
        c.add(len(gold_set & pred_set), len(pred_set), len(gold_set))
    return c.prf()


def trap_scores(chunks, preds):
    """Section 17, trap table: each trap on the chunks that contain it."""
    out = {}

    def sub(trap):
        pairs = [(c, p) for c, p in zip(chunks, preds)
                 if trap in c.get("traps", [])]
        return [a for a, _ in pairs], [b for _, b in pairs]

    for trap in ["T%d" % k for k in range(1, 16)]:
        cs, ps = sub(trap)
        if not cs:
            continue
        r = {"chunks": len(cs)}
        if trap == "T1":
            r["REVENUE_precision"] = label_counts(cs, ps, {"REVENUE"})[
                "precision"]
            r["DOC_TOTAL_f1"] = label_counts(cs, ps, {"DOC_TOTAL"})["f1"]
        elif trap in ("T2", "T3"):
            rev = label_counts(cs, ps, {"REVENUE"})
            r["REVENUE_precision"] = rev["precision"]
            r["REVENUE_recall"] = rev["recall"]
            r["REVENUE_YEAR_f1"] = label_counts(cs, ps, {"REVENUE_YEAR"})[
                "f1"]
        elif trap == "T4":
            right = swapped = 0
            for c, p in zip(cs, ps):
                pred = {(x["start"], x["end"]): x["label"]
                        for x in p["spans"] if x["accepted"]}
                for s, e, lab in c["spans"]:
                    if lab in ROLE_PAIRS and (s, e) in pred:
                        if pred[(s, e)] == lab:
                            right += 1
                        elif pred[(s, e)] == ROLE_PAIRS[lab]:
                            swapped += 1
            r["role_accuracy"] = round(right / max(1, right + swapped), 4)
            r["role_swap_rate"] = round(swapped / max(1, right + swapped),
                                        4)
        elif trap == "T5":
            false = 0
            for c, p in zip(cs, ps):
                gold_set = {(s, e, lab) for s, e, lab in c["spans"]}
                false += sum(1 for x in p["spans"] if x["accepted"] and (
                    x["label"].startswith("S_") or x["label"] in FACT_TYPES)
                    and (x["start"], x["end"], x["label"]) not in gold_set)
            r["false_S_or_fact_per_100_chunks"] = round(
                100 * false / len(cs), 2)
        elif trap == "T6":
            r["S_PHONE_precision"] = label_counts(cs, ps, {"S_PHONE"})[
                "precision"]
            r["S_REG_ID_precision"] = label_counts(cs, ps, {"S_REG_ID"})[
                "precision"]
        elif trap == "T12":
            false = sum(sum(1 for x in p["spans"] if x["accepted"])
                        for c, p in zip(cs, ps) if not c["spans"])
            empty = sum(1 for c in cs if not c["spans"])
            r["false_spans_per_100_empty"] = round(100 * false /
                                                   max(1, empty), 2)
        elif trap == "T13":
            r["C_NAME_f1"] = label_counts(cs, ps, {"C_NAME"})["f1"]
        else:
            lab = {"T7": "FOUNDED", "T8": "STAFF", "T9": "SERVICE",
                   "T10": "DOC_TOTAL", "T11": "S_PERSON", "T14": "S_NAME",
                   "T15": "DOC_DATE"}[trap]
            r["%s_precision" % lab] = label_counts(cs, ps, {lab})[
                "precision"]
        out[trap] = r
    cs = [c for c in chunks if {"T1", "T2", "T3"} & set(c.get("traps", []))]
    ps = [p for c, p in zip(chunks, preds)
          if {"T1", "T2", "T3"} & set(c.get("traps", []))]
    out["T1-T3 REVENUE precision"] = label_counts(cs, ps, {"REVENUE"})[
        "precision"]
    return out


# =====================================================================
#  folder level (end to end)
# =====================================================================
class GoldExtractor:
    """Returns the TRUE spans as if a perfect model had found them - to
    measure the profile builder alone (used in tests and diagnostics)."""

    def __init__(self, chunks):
        self.by_text = {}
        for c in chunks:
            self.by_text.setdefault(c["text"], c)

    def extract(self, texts, batch_size=16):
        out = []
        for text in texts:
            c = self.by_text.get(text)
            spans = [{"label": lab, "start": s, "end": e, "text": text[s:e],
                      "score": 1.0, "accepted": True}
                     for s, e, lab in (c["spans"] if c else [])]
            probs = [0.0] * len(config.DOC_TYPES)
            doc = c["doc_type"] if c else "other"
            probs[config.DOC_TYPES.index(doc)] = 1.0
            out.append({"language": c["lang"] if c else None,
                        "language_score": 1.0, "doc_type": doc,
                        "doc_type_score": 1.0, "doc_type_probs": probs,
                        "spans": spans})
        return out


def _key_text(t):
    return PR.text_key(t or "")


def same_value(kind, got, want):
    """Profile value vs truth, after normalization."""
    if got is None or want is None:
        return False
    if kind == "amount":
        return abs(got - want) <= 0.005 * abs(want) + 0.01
    return got == want


def staff_ok(norm, truth):
    """A staff count matches the true number (qualifiers respected)."""
    if not norm or truth is None:
        return False
    v, q, mx = norm.get("value"), norm.get("qualifier"), norm.get("max")
    if q == "exact":
        return v == truth
    if q == "approx":
        return abs(v - truth) <= max(5, 0.15 * truth)
    if q == "over":
        return truth >= v and truth <= v + max(10, 0.5 * v)
    if q == "under":
        return truth < v
    if q == "range":
        return v <= truth <= (mx or v)
    return False


def compare_folder(profile, truth):
    """-> {field: True / False} for the fields of section 17, plus the
    conflicts."""
    f = profile["fields"]
    found = truth["found"]
    res, conflicts = {}, []

    def status(name):
        return f[name]["status"]

    def not_found_ok(name, flag):
        """not_found is right exactly when the truth is not_found."""
        return status(name) == "not_found" and not flag

    def candidates(name):
        rec = f[name]
        vals = [rec.get("value")] + [a["value"] for a in
                                     rec.get("alternatives", [])]
        return [v for v in vals if v]

    def judge(name, flag, test):
        if not flag:
            res[name] = status(name) == "not_found"
            return
        if status(name) == "not_found":
            res[name] = False
            return
        if status(name) == "conflict":
            conflicts.append(name)
            res[name] = any(test(v) for v in candidates(name))
            return
        res[name] = test(f[name]["value"])

    # business name: legal or trading name, same key
    names = {PR.name_key(truth["legal_name"]),
             PR.name_key(truth["trading_name"])} - {""}
    bn = f["business_name"]
    if not found["business_name"]:
        res["business_name"] = bn["status"] == "not_found"
    else:
        got = {PR.name_key(bn.get("legal_name") or ""),
               PR.name_key(bn.get("trading_name") or "")} - {""}
        res["business_name"] = bool(got & names)
    addresses = {_key_text(a) for a in truth.get("address_variants") or
                 [truth["address"]]}
    judge("address", found["address"],
          lambda v: _key_text(v.get("text")) in addresses)
    true_ids = {r["compact"] for r in truth["reg_ids"]}
    if not found["reg_id"]:
        res["reg_id"] = status("reg_id") == "not_found"
    else:
        got = {(v.get("normalized") or {}).get("compact") or
               N.compact_id(v["text"]) for v in f["reg_id"]["value"]}
        res["reg_id"] = bool(got & true_ids) and got <= true_ids
    phones = {(v.get("normalized") or {}).get("e164")
              for v in f["phones"]["value"]}
    emails = {(v.get("normalized") or {}).get("value")
              for v in f["emails"]["value"]}
    if not found["contact"]:
        res["contact"] = status("contact") == "not_found"
    else:
        res["contact"] = bool(phones & set(truth["phones"]) or
                              emails & set(truth["emails"]))
    judge("legal_form", found["legal_form"],
          lambda v: (v.get("normalized") or {}).get("code") ==
          truth["legal_form"]["code"])

    def founded_ok(v):
        n = v.get("normalized") or {}
        t = truth["founded"]
        if n.get("year") != t["year"]:
            return False
        for k in ("month", "day"):
            if n.get(k) is not None and n.get(k) != t[k]:
                return False
        return True
    judge("founded", found["founded"], founded_ok)
    judge("staff", found["staff"],
          lambda v: staff_ok(v.get("normalized"), truth["staff"]))
    acts = {_key_text(a) for a in truth["activities"]}
    judge("activity", found["activity"],
          lambda v: _key_text(v.get("text")) in acts)
    code = (truth.get("activity_code") or {}).get("code")
    judge("activity_code", found.get("activity_code", False),
          lambda v: code is not None and (v.get("normalized") or {}).get(
              "code") == code.replace(".", "").upper())
    judge("capital", found.get("capital", False),
          lambda v: same_value("amount", (v.get("normalized") or {}).get(
              "value"), truth["capital"]))
    rev = truth.get("revenue") or {}
    rv = f["revenue"]
    if not found["revenue"]:
        res["revenue"] = rv["status"] == "not_found"
    elif rv["status"] == "not_found" or not rv.get("value"):
        res["revenue"] = False
    else:
        v = rv["value"]
        res["revenue"] = v.get("year") == rev.get("year") and same_value(
            "amount", (v.get("normalized") or {}).get("value"),
            rev.get("amount"))
    true_services = {_key_text(t) for t in truth["services"]}
    got_services = {_key_text(v["text"]) for v in f["services"]["value"]}
    if not found["services"]:
        res["services"] = status("services") == "not_found"
    else:
        res["services"] = f1_of(got_services, true_services) >= 0.8
    true_orgs = {PR.name_key(t) for t in
                 truth["clients"]["organisations"]} - {""}
    got_orgs = {PR.name_key(o["text"]) for o in
                f["clients"]["value"]["organisations"]} - {""}
    if not found["clients"]:
        res["clients"] = status("clients") == "not_found"
    elif true_orgs:
        res["clients"] = f1_of(got_orgs, true_orgs) >= 0.8
    else:
        res["clients"] = (f["clients"]["value"][
            "private_customer_documents"] >= 3) == (
            truth["clients"]["private_customer_documents"] >= 3)
    res["country"] = f["country"]["value"]["text"] == truth["country"]
    return res, conflicts


def f1_of(got, want):
    if not got and not want:
        return 1.0
    tp = len(got & want)
    p = tp / len(got) if got else 0.0
    r = tp / len(want) if want else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def folder_level(preset, split, extractor, model_id, log=print,
                 limit=None):
    """Runs extract_db -> verify -> profile on every folder of a split
    and compares each profile with its truth."""
    chunks = read_split(preset, split)
    truths = []
    path = config.data_dir(preset) / ("folders_%s.jsonl.gz" % split)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        truths = [json.loads(line) for line in f]
    by_folder = {}
    for c in chunks:
        by_folder.setdefault(c["folder"], []).append(c)
    fields = ["business_name", "address", "reg_id", "contact",
              "legal_form", "founded", "staff", "activity",
              "activity_code", "capital", "revenue", "services", "clients",
              "country"]
    correct = {k: 0 for k in fields}
    required_acc, invented, cov_err, conflicts, n = [], 0, [], 0, 0
    for truth in truths[:limit]:
        cs = by_folder.get(truth["folder"], [])
        if not cs:
            continue
        db, _ = extract_db.build_folder_db(cs)
        extract_db.process(db, extractor, model_id, log=lambda *a: None)
        prof = PR.build(db, model_id)
        res, conf = compare_folder(prof, truth)
        conflicts += len(conf)
        invented += len(PR.check_invariant(prof, db))
        for k in fields:
            correct[k] += bool(res.get(k))
        required_acc.append(sum(bool(res.get(k)) for k in PR.REQUIRED) /
                            len(PR.REQUIRED))
        true_cov = sum(1 for k in PR.REQUIRED if truth["found"].get(k)) / \
            len(PR.REQUIRED)
        cov_err.append(abs(prof["summary"]["coverage"] - true_cov))
        n += 1
        db.close()
    return {"folders": n,
            "field_accuracy": {k: round(v / max(1, n), 4)
                               for k, v in correct.items()},
            "required_mean_accuracy": round(sum(required_acc) /
                                            max(1, len(required_acc)), 4),
            "invented_values": invented,
            "conflicts_per_folder": round(conflicts / max(1, n), 3),
            "coverage_error": round(sum(cov_err) / max(1, len(cov_err)), 4)}


# =====================================================================
#  speed
# =====================================================================
def speed(model_path, chunks):
    from extractor import Extractor
    ex = Extractor(model_path, threads=4)
    texts = [c["text"] for c in chunks[:500]]
    t0 = time.time()
    ex.extract(texts, batch_size=16)
    seconds = time.time() - t0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return {"chunks": len(texts),
            "chunks_per_second": round(len(texts) / max(seconds, 1e-9), 2),
            "peak_ram_mb": round(peak, 1), "threads": 4, "batch": 16}


# =====================================================================
def run(preset, dev_only=False, log=print, folder_limit=None):
    from extractor import Extractor
    out = config.runs_dir(preset)
    model_path = out / "model_eval.pt"
    ex = Extractor(model_path)
    model_id = config.MODEL_FILES[preset].rsplit(".", 1)[0]
    result = {"preset": preset, "dev_only": dev_only, "splits": {},
              "folder_level": {}}
    splits = ["val", "dev_heldout"] if dev_only else \
        ["val", "dev_heldout", "test_seen", "test_heldout", "test_locale",
         "traps"]
    errors = []
    for split in splits:
        chunks = read_split(preset, split)
        if not chunks:
            continue
        t0 = time.time()
        preds = ex.extract([c["text"] for c in chunks])
        scores = score_chunks(chunks, preds)
        scores["seconds"] = round(time.time() - t0, 1)
        if split == "traps":
            scores["traps"] = trap_scores(chunks, preds)
        if split in EXAMPLES_ALLOWED:
            errors += collect_errors(chunks, preds)
        result["splits"][split] = scores
        log("%-12s strict F1 %.4f  relaxed %.4f  doc %.3f  lang %.3f" % (
            split, scores["strict"]["f1"], scores["relaxed"]["f1"],
            scores["doc_type_accuracy"], scores["language_accuracy"]))
    for split in (["dev_heldout"] if dev_only else
                  ["test_heldout", "test_seen"]):
        t0 = time.time()
        fl = folder_level(preset, split, ex, model_id, log,
                          limit=folder_limit)
        fl["seconds"] = round(time.time() - t0, 1)
        result["folder_level"][split] = fl
        log("folder level %s: required fields %.3f, business name %.3f, "
            "invented %d" % (split, fl["required_mean_accuracy"],
                             fl["field_accuracy"]["business_name"],
                             fl["invented_values"]))
    if not dev_only:
        hw = gold.load_folder(HERE / "handwritten")
        if hw:
            preds = ex.extract([c["text"] for c in hw])
            result["handwritten"] = score_chunks(hw, preds)
        real = gold.load_folder(HERE / "real_eval")
        if real:
            preds = ex.extract([c["text"] for c in real])
            result["real_eval"] = score_chunks(real, preds)
        test = read_split(preset, "test_heldout")
        result["speed"] = speed(model_path, test)
    tok_report = out / "tokenizer_report.json"
    if tok_report.exists():
        rep = json.loads(tok_report.read_text(encoding="utf-8"))
        result["boundary_rate"] = rep["boundary_rate"]
        result["chars_per_token"] = rep["chars_per_token"]
    with open(out / "errors_dev.jsonl", "w", encoding="utf-8") as f:
        for row in errors:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(out / "eval.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    write_tables(result, out / "eval_tables.md")
    return result


def collect_errors(chunks, preds):
    """Errors of val / dev_heldout for the improvement rounds."""
    rows = []
    for c, p in zip(chunks, preds):
        gold_set = {(s, e, lab) for s, e, lab in c["spans"]}
        pred_set = {(x["start"], x["end"], x["label"]) for x in p["spans"]
                    if x["accepted"]}
        for s, e, lab in gold_set - pred_set:
            kind = "missed"
            for q in pred_set:
                if (q[0], q[1]) == (s, e):
                    kind = "role_swap" if ROLE_PAIRS.get(lab) == q[2] \
                        else "wrong_label"
                elif q[2] == lab and overlap((s, e), q) > 0:
                    kind = "boundary"
            rows.append({"chunk": c["id"], "lang": c["lang"],
                         "doc_type": c["doc_type"], "layout": c["layout"],
                         "label": lab, "kind": kind,
                         "gold": c["text"][s:e],
                         "context": c["text"][max(0, s - 60):e + 60]})
        for s, e, lab in pred_set - gold_set:
            if any((g[0], g[1]) == (s, e) for g in gold_set) or any(
                    g[2] == lab and overlap((s, e), g) > 0
                    for g in gold_set):
                continue                    # counted above
            rows.append({"chunk": c["id"], "lang": c["lang"],
                         "doc_type": c["doc_type"], "layout": c["layout"],
                         "label": lab, "kind": "spurious",
                         "pred": c["text"][s:e],
                         "context": c["text"][max(0, s - 60):e + 60]})
    return rows


# =====================================================================
#  tables
# =====================================================================
def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def write_tables(result, path):
    parts = ["# Evaluation - preset %s%s" % (
        result["preset"], " (dev-only: val and dev_heldout)"
        if result["dev_only"] else "")]
    rows = []
    for split, s in result["splits"].items():
        rows.append([split, s["chunks"], s["strict"]["f1"],
                     s["strict"]["precision"], s["strict"]["recall"],
                     s["relaxed"]["f1"], s["role_swap_rate"],
                     s["doc_type_accuracy"], s["language_accuracy"],
                     s["false_spans_per_100_empty"], s["ece"]])
    parts.append("## Spans\n\n" + md_table(
        ["split", "chunks", "strict F1", "P", "R", "relaxed F1",
         "role swaps", "doc type acc", "lang acc", "false/100 empty",
         "ECE"], rows))
    main = result["splits"].get("test_heldout") or \
        result["splits"].get("dev_heldout")
    main_name = "test_heldout" if "test_heldout" in result["splits"] \
        else "dev_heldout"
    if main:
        parts.append("## Per label (%s)\n\n" % main_name + md_table(
            ["label", "F1", "P", "R", "gold"],
            [[k, v["f1"], v["precision"], v["recall"], v["gold"]]
             for k, v in main["per_label"].items()]))
        parts.append("## Per language (%s)\n\n" % main_name + md_table(
            ["lang", "F1", "P", "R"],
            [[k, v["f1"], v["precision"], v["recall"]]
             for k, v in main["per_lang"].items()]))
        parts.append("## Per document type (%s)\n\n" % main_name + md_table(
            ["doc type", "F1", "P", "R"],
            [[k, v["f1"], v["precision"], v["recall"]]
             for k, v in main["per_doc_type"].items()]))
        parts.append("## Per source format (%s)\n\n" % main_name +
                     md_table(["source", "F1", "P", "R"],
                              [[k, v["f1"], v["precision"], v["recall"]]
                               for k, v in main["per_source"].items()]))
    traps = (result["splits"].get("traps") or {}).get("traps")
    if traps:
        rows = []
        for k, v in traps.items():
            if isinstance(v, dict):
                rows.append([k, v.get("chunks"), ", ".join(
                    "%s %s" % (a, b) for a, b in v.items()
                    if a != "chunks")])
            else:
                rows.append([k, "", v])
        parts.append("## Traps\n\n" + md_table(["trap", "chunks", "scores"],
                                               rows))
    for split, fl in result["folder_level"].items():
        rows = [[k, v] for k, v in fl["field_accuracy"].items()]
        rows += [["REQUIRED mean", fl["required_mean_accuracy"]],
                 ["invented values", fl["invented_values"]],
                 ["conflicts per folder", fl["conflicts_per_folder"]],
                 ["coverage error", fl["coverage_error"]],
                 ["folders", fl["folders"]]]
        parts.append("## Folder level (%s)\n\n" % split +
                     md_table(["field", "accuracy"], rows))
    for name in ("handwritten", "real_eval"):
        if result.get(name):
            s = result[name]
            parts.append("## %s\n\n" % name + md_table(
                ["chunks", "strict F1", "P", "R", "relaxed F1"],
                [[s["chunks"], s["strict"]["f1"], s["strict"]["precision"],
                  s["strict"]["recall"], s["relaxed"]["f1"]]]))
    if result.get("speed"):
        s = result["speed"]
        parts.append("## Speed\n\n%s chunks/s on CPU (threads %d, batch "
                     "%d, %d chunks), peak RAM %s MB" % (
                         s["chunks_per_second"], s["threads"], s["batch"],
                         s["chunks"], s["peak_ram_mb"]))
    if result.get("boundary_rate") is not None:
        parts.append("## Tokenizer\n\nboundary rate %.3f%%; characters "
                     "per token: %s" % (
                         100 * result["boundary_rate"], ", ".join(
                             "%s %.2f" % kv for kv in
                             result["chars_per_token"].items())))
    pathlib.Path(path).write_text("\n\n".join(parts) + "\n",
                                  encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("preset", nargs="?", default="smoke")
    ap.add_argument("--dev-only", action="store_true")
    args = ap.parse_args()
    run(args.preset, args.dev_only)
    del unicodedata
