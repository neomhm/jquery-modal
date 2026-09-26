"""
import_sheets.py - import every sheet of a folder into documents.db
(section 15.2), the database that ingest.py and the Extractor also use.

    py import_sheets.py "C:\\Users\\Laurent\\documents to publish" --db "C:\\Users\\Laurent\\new model\\documents.db" --targets products,services --locale fr-FR
    ... --show      prints, for each sheet, the status, the program and the
                    first 5 imported rows next to their source row numbers

Tables it writes:
  * tulip_<target>: one per target; the schema fields, plus _file,
    _sheet, _row, _sources (JSON) and _import_id.
  * tulip_imports: one row per sheet (status, reason, program,
    problems, warnings, rows in and out, the model, ...).

Re-importing:
  * a sheet already imported from a file with the same sha1 by the same
    model (imported / imported_with_warnings) is skipped;
  * refused and needs_review sheets are tried again when the model
    changes;
  * a changed file replaces that sheet's earlier rows, in one
    transaction.
Hidden sheets are processed too and marked hidden. .xls, .ods and other
files are listed as skipped_file_type.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

import config
import sheets
import tulipscript as ts

HERE = pathlib.Path(__file__).resolve().parent
READABLE = (".xlsx", ".xlsm", ".csv")
SQL_TYPE = {"text": "TEXT", "currency": "TEXT", "date": "TEXT",
            "time": "TEXT", "hours": "TEXT", "email": "TEXT",
            "phone": "TEXT", "amount": "REAL", "percent": "REAL",
            "integer": "INTEGER", "duration": "INTEGER",
            "weekday": "INTEGER", "boolean": "INTEGER"}


def sql_type(kind):
    return "TEXT" if kind.startswith("enum:") else SQL_TYPE[kind]


# ---------------------------------------------------------------------
#  the database
# ---------------------------------------------------------------------
def create_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS tulip_imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, file TEXT, sheet TEXT,
        file_sha1 TEXT, target TEXT, status TEXT, reason TEXT,
        program TEXT, problems TEXT, warnings TEXT, rows_in INTEGER,
        rows_out INTEGER, skipped TEXT, model TEXT,
        candidates_tried INTEGER, hidden INTEGER, created TEXT)""")
    for target, fields in ts.SCHEMAS.items():
        cols = ", ".join('"%s" %s' % (f, sql_type(k)) for f, k, _ in fields)
        db.execute('CREATE TABLE IF NOT EXISTS "tulip_%s" (%s, _file TEXT, '
                   '_sheet TEXT, _row INTEGER, _sources TEXT, '
                   '_import_id INTEGER)' % (target, cols))


def previous(db, file, sheet):
    return db.execute("SELECT id, file_sha1, status, model FROM "
                      "tulip_imports WHERE file = ? AND sheet = ? ORDER BY "
                      "id DESC LIMIT 1", (file, sheet)).fetchone()


def to_sql(kind, value):
    if value is None:
        return None
    if kind == "boolean":
        return 1 if value else 0
    return value


def store(db, result, file_sha1, model_id, rows_in):
    """One transaction: the old rows of this sheet go, the new ones come."""
    with db:
        old = db.execute("SELECT id, target FROM tulip_imports WHERE "
                         "file = ? AND sheet = ?", (result["file"],
                                                    result["sheet"]))
        for import_id, target in old.fetchall():
            if target:
                db.execute('DELETE FROM "tulip_%s" WHERE _import_id = ?' %
                           target, (import_id,))
        cur = db.execute(
            "INSERT INTO tulip_imports (file, sheet, file_sha1, target, "
            "status, reason, program, problems, warnings, rows_in, "
            "rows_out, skipped, model, candidates_tried, hidden, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (result["file"], result["sheet"], file_sha1, result["target"],
             result["status"], result["reason"], result["program"],
             json.dumps(result["problems"], ensure_ascii=False),
             json.dumps(result["warnings"], ensure_ascii=False), rows_in,
             len(result["rows"]),
             json.dumps(result["skipped"], ensure_ascii=False, default=str),
             model_id, result["candidates_tried"],
             1 if result.get("hidden") else 0,
             datetime.datetime.now().isoformat(timespec="seconds")))
        import_id = cur.lastrowid
        target = result["target"]
        if target and result["status"] in ("imported",
                                            "imported_with_warnings"):
            fields = ts.SCHEMAS[target]
            names = [f for f, _, _ in fields]
            sql = 'INSERT INTO "tulip_%s" (%s, _file, _sheet, _row, ' \
                  '_sources, _import_id) VALUES (%s)' % (
                      target, ", ".join('"%s"' % n for n in names),
                      ", ".join("?" * (len(names) + 5)))
            for record, srcs, row in zip(result["rows"], result["sources"],
                                         result["row_numbers"]):
                values = [to_sql(k, record.get(f)) for f, k, _ in fields]
                db.execute(sql, values + [result["file"], result["sheet"],
                                          row, json.dumps(srcs,
                                                          default=str),
                                          import_id])
        return import_id


# ---------------------------------------------------------------------
#  model and locale
# ---------------------------------------------------------------------
def default_model():
    for name in (config.MODEL_FILES["full"], config.MODEL_FILES["pilot"]):
        path = HERE / name
        if path.exists():
            return path
    return None


def locale_from_db(db):
    """Section 15.2: the country from profile_summary, the language from
    chunk_meta (both written by the Extractor)."""
    from gen import data as D
    try:
        country = db.execute("SELECT country FROM profile_summary "
                             "WHERE id = 1").fetchone()
        language = db.execute("SELECT language FROM chunk_meta GROUP BY "
                              "language ORDER BY COUNT(*) DESC LIMIT 1"
                              ).fetchone()
    except sqlite3.Error:
        country = language = None
    if not language or not language[0]:
        raise SystemExit("No --locale given and documents.db has no "
                         "language yet: give --locale, e.g. --locale fr-FR")
    lang = str(language[0]).split("-")[0].lower()
    if lang not in config.LANGS:
        raise SystemExit("The documents are in '%s', which Tulip does not "
                         "read (it reads: %s)." % (lang,
                                                   ", ".join(config.LANGS)))
    code = "%s-%s" % (lang, (country[0] if country and country[0]
                             else "").upper())
    if code in D.locales():
        return code
    # not an Appendix F pair: the language's first locale for numbers and
    # dates (the country is kept for currency and phone by the helpers)
    first = [c for c, v in D.locales().items() if v["lang"] == lang][0]
    return first if not (country and country[0]) else \
        "%s-%s" % (lang, country[0].upper())


# ---------------------------------------------------------------------
def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Import sheets with Tulip")
    ap.add_argument("folder")
    ap.add_argument("--db", required=True)
    ap.add_argument("--targets", default=",".join(config.TARGETS))
    ap.add_argument("--locale")
    ap.add_argument("--model")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--threads", type=int)
    args = ap.parse_args()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in config.TARGETS]
    if bad:
        raise SystemExit("unknown target(s): %s (choose from %s)" % (
            ", ".join(bad), ", ".join(config.TARGETS)))
    model_path = pathlib.Path(args.model) if args.model else default_model()
    if not model_path or not model_path.exists():
        raise SystemExit("No model file: build one with 'py build.py' or "
                         "give --model")
    model_id = model_path.stem
    db = sqlite3.connect(args.db)
    create_tables(db)
    locale = args.locale or locale_from_db(db)
    from tulip import Tulip
    tulip = Tulip(model_path, threads=args.threads)
    folder = pathlib.Path(args.folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    counts = {}
    for path in files:
        if path.suffix.lower() not in READABLE:
            counts["skipped_file_type"] = counts.get("skipped_file_type",
                                                     0) + 1
            print("skipped_file_type  %s" % path.name)
            continue
        sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
        for sheet in sheets.load(path, locale):
            prev = previous(db, str(path), sheet.name)
            if prev and prev[1] == sha1 and prev[3] == model_id and \
                    prev[2] in ("imported", "imported_with_warnings"):
                counts["unchanged"] = counts.get("unchanged", 0) + 1
                continue
            if prev and prev[1] == sha1 and prev[3] == model_id:
                counts["unchanged"] = counts.get("unchanged", 0) + 1
                continue                 # refused / needs_review, same model
            sheet.file = str(path)
            result = tulip.import_sheet(sheet, targets, locale)
            result["file"] = str(path)
            rows_in = max(0, len(sheet.rows) - 1)
            store(db, result, sha1, model_id, rows_in)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            print("%-22s %s | %s%s" % (result["status"], path.name,
                                       sheet.name, (" (%s)" % result["reason"])
                                       if result["reason"] else ""))
            if args.show:
                show(result)
    db.close()
    print("done: " + ", ".join("%s %d" % kv for kv in sorted(
        counts.items())))
    return 0


def show(result):
    print("  program:")
    for line in (result["program"] or "").splitlines():
        print("    " + line)
    for record, row in list(zip(result["rows"], result["row_numbers"]))[:5]:
        print("  row %s: %s" % (row, json.dumps(record, ensure_ascii=False,
                                                default=str)))
    if result["skipped"]:
        print("  skipped rows: %s" % result["skipped"][:5])
    print()


if __name__ == "__main__":
    sys.exit(main())
