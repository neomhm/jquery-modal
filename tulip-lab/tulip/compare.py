"""
compare.py - compare the imported sheets with each other (Tulip 1.1,
item B). Plain code over documents.db; the model is not used.

    py compare.py --db "C:\\Users\\Laurent\\new model\\documents.db"
    (import_sheets.py runs it after every folder import)

Rows of one table that describe the same thing - the same key after
normalisation (keys.group_key: a product's name and variant after NFKC,
case folding, accents and units: "Baguette 0,25 kg" = "BAGUETTE 250 g") -
are grouped across sheets and files (and within one sheet). A group of
two or more is:

  * a duplicate      every value the same, or
  * a contradiction  some column holds different values (the croissant is
                     1.10 in one price list and 1.20 in another).

Each group is ONE question for the owner's data-check step, in
tulip_conflicts: the key, the columns that disagree, every source with
its values and its cells, the preferred source and the rule that chose
it. Nothing is merged, changed or dropped: the rows of tulip_<table> stay
exactly as they are, and every source of a group is listed.

The preferred source (tested in tests/test_compare.py):
  1. the newest DOCUMENT date - the date a sheet states in its title or
     footer rows, its name or its file name ("Tarifs au 01/03/2026",
     "Carte 2026") - when every source states one; two dates are compared
     at the precision of the less precise ("2026" and "2026-03-01" are
     not told apart);
  2. then, among those still level, the newest FILE date (the file's
     modification time);
  3. then a file the business wrote over a supplier's (a file in a folder
     named "suppliers", "fournisseurs", "proveedores", "поставщики",
     "供应商", "仕入先", "공급업체", "الموردين", "आपूर्तिकर्ता"... in the
     ten languages);
  4. else no preference: the owner decides ("tie").

A question is asked once: running the comparison again keeps the
questions whose rows did not change (with the owner's answer, if any);
a question whose rows changed or went away is marked "gone" (kept, not
deleted) and the new state is asked.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys

import contract
import helpers as H
import keys

CONFLICTS_TABLE = """CREATE TABLE IF NOT EXISTS tulip_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, key TEXT,
    kind TEXT, columns TEXT, records TEXT, preferred TEXT, rule TEXT,
    question TEXT, status TEXT, answer TEXT, fingerprint TEXT,
    created TEXT, updated TEXT)"""

SUPPLIER_WORDS = [
    "supplier", "suppliers", "vendor", "vendors", "fournisseur",
    "fournisseurs", "proveedor", "proveedores", "fornitore", "fornitori",
    "поставщик", "поставщики", "поставщиков", "مورد", "موردين",
    "الموردين", "المورد", "供应商", "供货商", "仕入先", "仕入れ先",
    "サプライヤー", "공급업체", "공급처", "आपूर्तिकर्ता", "सप्लायर"]


# ---------------------------------------------------------------------
#  where a sheet comes from: its dates and who wrote it
# ---------------------------------------------------------------------
def origin(path, root=None):
    """"supplier" when a folder of the path (below root) is named like
    a suppliers' folder, else "business"."""
    path = pathlib.Path(path)
    try:
        parts = path.parent.relative_to(root).parts if root else \
            path.parent.parts
    except ValueError:
        parts = path.parent.parts
    words = set(keys.normal(w) for w in SUPPLIER_WORDS)
    for part in parts:
        t = keys.normal(part)
        if any(w in t.split() or (w and not w.isascii() and w in t)
               for w in words):
            return "supplier"
    return "business"


def file_date(path):
    """The file's modification time, ISO 8601 (None if unreadable)."""
    try:
        stamp = os.stat(path).st_mtime
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(stamp).isoformat(
        timespec="seconds")


_NUMERIC = re.compile(r"(?<!\d)(\d{1,4}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,4})"
                      r"(?!\d)")
_CJK = re.compile(r"(\d{4})\s*[年년]\s*(\d{1,2})\s*[月월](?:\s*(\d{1,2})\s*"
                  r"[日일])?")
_YEAR = re.compile(r"(?<!\d)(19[89]\d|20\d\d)(?!\d)")


def dates_in(text, locale):
    """Every date a text states, as "YYYY-MM-DD", "YYYY-MM" or "YYYY"."""
    if isinstance(text, (datetime.date, datetime.datetime)):
        d = text.date() if isinstance(text, datetime.datetime) else text
        return [d.isoformat()]
    if not isinstance(text, str) or not text.strip():
        return []
    t = H.ascii_digits(H.clean(text))
    out = []
    for m in _NUMERIC.finditer(t):
        ok, value = H.date(m.group(1), locale)
        if ok and value:
            out.append(value)
    for m in _CJK.finditer(t):
        y, mo, d = m.group(1), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12:
            out.append("%s-%02d-%02d" % (y, mo, int(d)) if d else
                       "%s-%02d" % (y, mo))
    covered = " ".join(out)
    months, _ = H.month_table()
    words = H.key(t).replace(",", " ").split()
    for i, w in enumerate(words):
        w = w.rstrip(".")
        if w in months and not re.fullmatch(r"\d+", w):
            for j in (i + 1, i + 2, i - 1):
                if 0 <= j < len(words) and re.fullmatch(
                        r"(19[89]\d|20\d\d)", words[j]):
                    value = "%s-%02d" % (words[j], months[w])
                    if not any(c.startswith(value) for c in out):
                        out.append(value)
                    break
    for m in _YEAR.finditer(t):
        if m.group(1) not in covered and not any(
                c.startswith(m.group(1)) for c in out):
            out.append(m.group(1))
    return out


def document_date(sheet, row_numbers, locale, file_name=""):
    """The newest date the sheet states outside its data rows (its title
    and footer rows), its name or its file name; None if none."""
    first = min(row_numbers) if row_numbers else len(sheet.rows) + 1
    last = max(row_numbers) if row_numbers else 0
    texts = [sheet.name, pathlib.Path(file_name).stem]
    for n, row in enumerate(sheet.rows, 1):
        if n < first or n > last:
            texts += [v for v in row if v is not None]
    found = [d for t in texts for d in dates_in(t, locale)]
    return max(found, key=lambda d: (d + "-00-00")[:10]) if found else None


# ---------------------------------------------------------------------
#  the preferred source
# ---------------------------------------------------------------------
def _newest(candidates, field):
    """The candidates whose `field` is the newest, two values compared at
    the precision of the less precise ("2026" is level with "2026-03-01"
    and newer than "2025-12-31"); None when a candidate has none."""
    if any(not c.get(field) for c in candidates):
        return None
    top = max((c[field] for c in candidates),
              key=lambda d: d if len(d) > 10 else (d + "-00-00")[:10])

    def level(d):
        n = min(len(d), len(top))
        return d[:n] == top[:n]
    return [c for c in candidates if level(c[field])]


def prefer(sources):
    """sources: [{document_date, file_date, origin, ...}] -> (the
    preferred source or None, the rule that decided)."""
    candidates = list(sources)
    for rule, field in (("document_date", "document_date"),
                        ("file_date", "file_date")):
        newest = _newest(candidates, field)
        if newest is None:
            continue
        if len(newest) == 1:
            return newest[0], rule
        candidates = newest
    business = [c for c in candidates if c.get("origin") == "business"]
    if len(business) == 1 and len(candidates) > 1:
        return business[0], "business_over_supplier"
    return None, "tie"


# ---------------------------------------------------------------------
#  groups
# ---------------------------------------------------------------------
def _cells(sources, column):
    """[[row, "B"], ...] -> ["B12", ...]"""
    return ["%s%s" % (c, r) for r, c in (sources or {}).get(column, [])]


def records_of(db, target, imports):
    """The table's current rows as sources to compare: one per row, or
    for opening hours one per day of a sheet (all its ranges)."""
    cols = contract.columns(target)
    names = [c["name"] for c in cols]
    out = []
    rows = db.execute(
        'SELECT rowid, %s, _file, _sheet, _row, _sources, _import_id FROM '
        '"tulip_%s" WHERE _removed IS NULL ORDER BY _file, _sheet, _row, '
        'rowid' % (", ".join('"%s"' % n for n in names), target))
    for r in rows:
        values = dict((c["name"], v if c["format"] != "boolean" or v is None
                       else bool(v)) for c, v in zip(cols, r[1:1 + len(cols)])
                      if v is not None)
        file, sheet, row, srcs, import_id = r[1 + len(cols):]
        srcs = json.loads(srcs) if srcs else {}
        info = imports.get(import_id, {})
        rec = {"file": file, "sheet": sheet, "row": row, "row_id": r[0],
               "values": values,
               "cells": dict((n, _cells(srcs, n)) for n in values),
               "document_date": info.get("document_date"),
               "file_date": info.get("file_date"),
               "origin": info.get("origin") or "business"}
        if target == "opening_hours" and out and \
                out[-1]["file"] == file and out[-1]["sheet"] == sheet and \
                out[-1]["values"].get("day") == values.get("day"):
            prev = out[-1]
            prev["ranges"].append(dict((k, values.get(k)) for k in (
                "opens", "closes", "closed")))
            prev["rows"].append(row)
            continue
        if target == "opening_hours":
            rec["ranges"] = [dict((k, values.get(k)) for k in (
                "opens", "closes", "closed"))]
            rec["rows"] = [row]
        out.append(rec)
    return out


def _compared(target, rec):
    """What is compared: the values, with a day's ranges as one."""
    values = dict(rec["values"])
    if target == "opening_hours":
        for k in ("opens", "closes", "closed"):
            values.pop(k, None)
        values["hours"] = [(r["opens"], r["closes"], r["closed"])
                           for r in rec["ranges"]]
    return values


def groups(db, target, imports):
    """-> [(key, [records])] of every key held by two or more rows."""
    by_key = {}
    for rec in records_of(db, target, imports):
        k = keys.group_key(target, rec["values"])
        if k is not None:
            by_key.setdefault(k, []).append(rec)
    return [(k, recs) for k, recs in sorted(by_key.items())
            if len(recs) > 1]


def _where(rec):
    rows = rec.get("rows") or [rec["row"]]
    return "%s, %s, row %s" % (pathlib.Path(rec["file"]).name, rec["sheet"],
                               "/".join(str(r) for r in rows))


def question(target, key, recs, columns, preferred, rule):
    """The owner's question, in plain words."""
    name = recs[0]["values"].get(keys.GROUP_KEY[target][0])
    if not columns:
        text = "%r is listed %d times with the same values: %s." % (
            name, len(recs), "; ".join(_where(r) for r in recs))
    else:
        parts = []
        for col in columns:
            seen = []
            for r in recs:
                v = _compared(target, r).get(col)
                cells = r["cells"].get(col) or r["cells"].get("closed") \
                    or []
                seen.append("%s (%s%s)" % (
                    json.dumps(v, ensure_ascii=False), _where(r),
                    ", cell " + " ".join(cells) if cells else ""))
            parts.append("%s: %s" % (col, " vs ".join(seen)))
        text = "%r differs between %d sources - %s. Which is right?" % (
            name, len(recs), "; ".join(parts))
    if preferred is not None:
        text += " Preferred by the rule (%s): %s." % (
            rule.replace("_", " "), _where(preferred))
    else:
        text += " No rule decides: please choose."
    return text


def _fingerprint(target, key, recs):
    blob = json.dumps([target, key, [[r["file"], r["sheet"], r.get("rows")
                                      or r["row"], _compared(target, r)]
                                     for r in recs]],
                      sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def imports_info(db):
    """{import id: {document_date, file_date, origin}}"""
    cols = [r[1] for r in db.execute("PRAGMA table_info(tulip_imports)")]
    want = [c for c in ("document_date", "file_date", "origin") if c in cols]
    out = {}
    for r in db.execute("SELECT id%s FROM tulip_imports" % "".join(
            ", " + c for c in want)):
        out[r[0]] = dict(zip(want, r[1:]))
    return out


def run(db, now=None):
    """Compare every table; -> {"duplicates", "contradictions", "new",
    "kept", "gone"}. Writes tulip_conflicts only."""
    at = now or datetime.datetime.now().isoformat(timespec="seconds")
    summary = {"duplicates": 0, "contradictions": 0, "new": 0, "kept": 0,
               "gone": 0}
    with db:
        db.execute(CONFLICTS_TABLE)
        imports = imports_info(db)
        live = set()
        for target in contract.tables():
            try:
                found = groups(db, target, imports)
            except sqlite3.OperationalError:
                continue                  # no such table yet
            for key, recs in found:
                values = [_compared(target, r) for r in recs]
                names = []
                for v in values:
                    names += [n for n in v if n not in names and n not in
                              keys.GROUP_KEY[target]]
                columns = [n for n in names if len(set(json.dumps(
                    v.get(n), sort_keys=True, ensure_ascii=False,
                    default=str) for v in values if v.get(n) is not None))
                    > 1]
                kind = "contradiction" if columns else "duplicate"
                summary[kind + "s"] += 1
                fp = _fingerprint(target, key, recs)
                live.add(fp)
                if db.execute("SELECT 1 FROM tulip_conflicts WHERE "
                              "fingerprint = ? AND status != 'gone'",
                              (fp,)).fetchone():
                    summary["kept"] += 1
                    continue
                preferred, rule = prefer(recs)
                db.execute(
                    "INSERT INTO tulip_conflicts (target, key, kind, columns, "
                    "records, preferred, rule, question, status, answer, "
                    "fingerprint, created, updated) VALUES "
                    "(?,?,?,?,?,?,?,?,'open',NULL,?,?,?)",
                    (target, key, kind, json.dumps(columns),
                     json.dumps(recs, ensure_ascii=False, default=str),
                     json.dumps(dict((k, preferred[k]) for k in (
                         "file", "sheet", "row", "row_id"))
                         if preferred else None),
                     rule, question(target, key, recs, columns, preferred,
                                    rule), fp, at, at))
                summary["new"] += 1
        for cid, fp in db.execute("SELECT id, fingerprint FROM "
                                  "tulip_conflicts WHERE status != 'gone'"
                                  ).fetchall():
            if fp not in live:
                db.execute("UPDATE tulip_conflicts SET status = 'gone', "
                           "updated = ? WHERE id = ?", (at, cid))
                summary["gone"] += 1
    return summary


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Compare the imported sheets")
    ap.add_argument("--db", required=True)
    ap.add_argument("--show", action="store_true",
                    help="print every open question")
    args = ap.parse_args(argv)
    db = sqlite3.connect(args.db)
    s = run(db)
    print("compare: %(duplicates)d duplicates, %(contradictions)d "
          "contradictions (%(new)d new questions, %(kept)d already asked, "
          "%(gone)d gone)" % s)
    if args.show:
        for (text,) in db.execute("SELECT question FROM tulip_conflicts "
                                  "WHERE status = 'open' ORDER BY id"):
            print("  - " + text)
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
