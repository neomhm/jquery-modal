"""
import_sheets.py - import every sheet of a folder into documents.db
(section 15.2), the database that ingest.py and the Extractor also use.

    py import_sheets.py "C:\\Users\\Laurent\\documents to publish" --db "C:\\Users\\Laurent\\new model\\documents.db" --targets products,services --locale fr-FR
    ... --show      prints, for each sheet, the status, the program, how
                    sure Tulip is of each column (sure / check / unsure)
                    and the first 5 imported rows next to their source
                    row numbers
    ... --no-confidence   no bands (faster)

Tables it writes:
  * tulip_<target>: one per target; the columns of tables.schema.json
    (the one declared format every part of the PLAN reads: day names,
    opens / closes, VAT in percent...), plus _file, _sheet, _row,
    _sources (JSON) and _import_id.
  * tulip_imports: one row per sheet (status, reason, program,
    problems, warnings, rows in and out, the model, the schema version
    in "contract", and in "confidence" the band of every mapped column
    as JSON: {"calibrated", "columns": [{column, sheet_columns, band,
    score, signals}]}, ...).
A table made by an older version with other columns is renamed
tulip_<target>_before_<version> (never deleted), and sheets imported
under another schema version are imported again.

Re-importing:
  * a sheet already imported from a file with the same sha1 by the same
    model (imported / imported_with_warnings) is skipped: an unchanged
    file changes nothing;
  * refused and needs_review sheets are tried again when the model
    changes;
  * a changed file UPDATES that sheet's rows by key, in one transaction
    (history.py): new rows are added, changed rows updated in place,
    rows no longer there marked removed (_removed), never deleted; every
    change is a row of tulip_history (old and new value, when, which
    file and sheet row). A sheet that is now refused or needs review
    keeps its rows.
Hidden sheets are processed too and marked hidden. .xlsx, .xlsm, .xls,
.ods, .csv and PDF files (their text tables; a scanned PDF needs review:
no OCR) are read; other files are listed as skipped_file_type.
One bad file never stops the folder: a file that cannot be read (a
corrupt .xlsx, a binary .csv) gets ONE tulip_imports row, sheet "",
status needs_review, reason unreadable_file:<exception type>; it is
tried again when the file or the model changes. An exception on one
sheet gives that sheet needs_review, reason exception:<type>.
--targets is required: 1 to 4 of the seven targets (the PLAN offers at
most 4 per call, and the model was trained on 1 to 4).
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

import blocks
import compare
import config
import contract
import history
import sheets

HERE = pathlib.Path(__file__).resolve().parent
READABLE = sheets.READABLE
BOOKKEEPING = [("_file", "TEXT"), ("_sheet", "TEXT"), ("_row", "INTEGER"),
               ("_sources", "TEXT"), ("_import_id", "INTEGER"),
               ("_key", "TEXT"), ("_removed", "TEXT")]
# columns a Tulip 1.1 table made before item E lacks: added in place
ADDED_LATER = [("_key", "TEXT"), ("_removed", "TEXT")]
# columns tulip_imports gained after Tulip 1 (added to an older database)
IMPORT_EXTRA = [("contract", "TEXT"), ("confidence", "TEXT"),
                ("document_date", "TEXT"), ("file_date", "TEXT"),
                ("origin", "TEXT"), ("locale", "TEXT"), ("targets", "TEXT")]


# ---------------------------------------------------------------------
#  the database
# ---------------------------------------------------------------------
def table_columns(db, name):
    return [r[1] for r in db.execute('PRAGMA table_info("%s")' % name)]


def create_tables(db):
    """tulip_imports and one tulip_<target> table per target, with the
    columns and SQL types of tables.schema.json. A tulip_<target> table
    an older version made with other columns is renamed, never deleted,
    and a new one is made."""
    with db:
        db.execute("""CREATE TABLE IF NOT EXISTS tulip_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file TEXT, sheet TEXT,
            file_sha1 TEXT, target TEXT, status TEXT, reason TEXT,
            program TEXT, problems TEXT, warnings TEXT, rows_in INTEGER,
            rows_out INTEGER, skipped TEXT, model TEXT,
            candidates_tried INTEGER, hidden INTEGER, created TEXT,
            contract TEXT, confidence TEXT, document_date TEXT,
            file_date TEXT, origin TEXT, locale TEXT, targets TEXT)""")
        have = table_columns(db, "tulip_imports")
        for name, kind in IMPORT_EXTRA:
            if name not in have:
                db.execute("ALTER TABLE tulip_imports ADD COLUMN %s %s"
                           % (name, kind))
        db.execute(history.HISTORY_TABLE)
        for target in contract.tables():
            want = contract.column_names(target) + [n for n, _ in
                                                    BOOKKEEPING]
            name = "tulip_%s" % target
            have = table_columns(db, name)
            missing = want[len(have):]
            if have and have == want[:len(have)] and missing and all(
                    m in [n for n, _ in ADDED_LATER] for m in missing):
                for n, kind in ADDED_LATER:
                    if n in missing:
                        db.execute('ALTER TABLE "%s" ADD COLUMN %s %s'
                                   % (name, n, kind))
                have = want
            if have and have != want:
                old = "%s_before_%s" % (name, contract.version().replace(
                    ".", "_").replace("-", "_"))
                k = 1
                while table_columns(db, old + ("_%d" % k if k > 1 else "")):
                    k += 1
                db.execute('ALTER TABLE "%s" RENAME TO "%s"' % (
                    name, old + ("_%d" % k if k > 1 else "")))
            cols = ", ".join('"%s" %s' % (c["name"], contract.sql_type(c))
                             for c in contract.columns(target))
            db.execute('CREATE TABLE IF NOT EXISTS "%s" (%s, %s)' % (
                name, cols, ", ".join("%s %s" % b for b in BOOKKEEPING)))


def previous(db, file, sheet):
    return db.execute("SELECT id, file_sha1, status, model, contract FROM "
                      "tulip_imports WHERE file = ? AND sheet = ? ORDER BY "
                      "id DESC LIMIT 1", (file, sheet)).fetchone()


def unchanged(prev, sha1, model_id):
    """Nothing new to try: the same file, the same model and the same
    schema version as the last import of this sheet."""
    return bool(prev and sha1 and prev[1] == sha1 and prev[3] == model_id
                and prev[4] == contract.version())


to_sql = history.to_sql


def store(db, result, file_sha1, model_id, rows_in, now=None):
    """One transaction: the import's line in tulip_imports and, when the
    sheet was imported, its rows UPDATED by key (history.py): added,
    changed in place, or marked removed - never deleted - with one
    tulip_history row per change. result["changes"] gets the counts.
    A sheet that is refused or needs review keeps its current rows."""
    at = now or datetime.datetime.now().isoformat(timespec="seconds")
    with db:
        cur = db.execute(
            "INSERT INTO tulip_imports (file, sheet, file_sha1, target, "
            "status, reason, program, problems, warnings, rows_in, "
            "rows_out, skipped, model, candidates_tried, hidden, created, "
            "contract, confidence, document_date, file_date, origin, "
            "locale, targets) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (result["file"], result["sheet"], file_sha1, result["target"],
             result["status"], result["reason"], result["program"],
             json.dumps(result["problems"], ensure_ascii=False),
             json.dumps(result["warnings"], ensure_ascii=False), rows_in,
             len(result["rows"]),
             json.dumps(result["skipped"], ensure_ascii=False, default=str),
             model_id, result["candidates_tried"],
             1 if result.get("hidden") else 0, at,
             contract.version(),
             json.dumps(result.get("confidence"), ensure_ascii=False)
             if result.get("confidence") is not None else None,
             result.get("document_date"), result.get("file_date"),
             result.get("origin"), result.get("locale"),
             json.dumps(result["targets"]) if result.get("targets")
             else None))
        import_id = cur.lastrowid
        target = result["target"]
        if target and result["status"] in ("imported",
                                            "imported_with_warnings"):
            moved = sum(history.remove_all(db, other, result["file"],
                                           result["sheet"], import_id, at)
                        for other in contract.tables() if other != target)
            result["changes"] = history.apply(
                db, target, result["file"], result["sheet"], result["rows"],
                result["sources"], result["row_numbers"], import_id, at)
            if moved:
                result["changes"]["removed_from_other_table"] = moved
        return import_id


# ---------------------------------------------------------------------
#  model and locale
# ---------------------------------------------------------------------
def default_model():
    """The newest model file next to this script: tulip-1.1.0.pt, else
    Tulip 1's tulip-1.0.0.pt, else the pilot."""
    for name in (config.MODEL_FILES["full"], "tulip-1.0.0.pt",
                 config.MODEL_FILES["pilot"]):
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
    ap.add_argument("--targets", required=True,
                    help="1 to 4 of: %s (comma-separated)" % ", ".join(
                        config.TARGETS))
    ap.add_argument("--locale")
    ap.add_argument("--model")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--threads", type=int)
    ap.add_argument("--no-confidence", action="store_true",
                    help="skip the confidence bands (faster: the 7 "
                    "sampled programs are then only written when the "
                    "greedy one fails)")
    args = ap.parse_args()
    from tulip import Tulip, check_targets
    try:
        targets = check_targets([t.strip() for t in args.targets.split(",")
                                 if t.strip()])
    except ValueError as e:
        ap.error(str(e))
    model_path = pathlib.Path(args.model) if args.model else default_model()
    if not model_path or not model_path.exists():
        raise SystemExit("No model file: build one with 'py build.py' or "
                         "give --model")
    model_id = model_path.stem
    db = sqlite3.connect(args.db)
    create_tables(db)
    locale = args.locale or locale_from_db(db)
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
        counts = import_path(db, tulip, path, targets, locale, model_id,
                             counts, args.show, not args.no_confidence,
                             folder)
    print("done: " + ", ".join("%s %d" % kv for kv in sorted(
        counts.items())))
    # the sheets against each other: duplicates and contradictions become
    # questions in tulip_conflicts; no row is changed (compare.py)
    s = compare.run(db)
    print("compare: %(duplicates)d duplicates, %(contradictions)d "
          "contradictions (%(new)d new questions, %(gone)d gone)" % s)
    db.close()
    return 0


def import_path(db, tulip, path, targets, locale, model_id, counts,
                show_rows=False, confidence=True, root=None):
    """Every sheet of one readable file into the database. Never raises
    for a bad file: it is recorded (unreadable_file:<type>) and the
    folder goes on."""
    from tulip import unreadable_file
    try:
        sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError as e:
        sha1, loaded, error = None, [], e
    else:
        try:
            loaded, error = sheets.load(path, locale), None
        except Exception as e:
            loaded, error = [], e
    if error is not None:
        prev = previous(db, str(path), "")
        if unchanged(prev, sha1, model_id):
            counts["unchanged"] = counts.get("unchanged", 0) + 1
            return counts
        result = unreadable_file(path, error)
        store(db, result, sha1, model_id, 0)
        report(result, path.name, counts, False)
        return counts
    # the file reads now: an earlier "unreadable file" line for it goes
    with db:
        db.execute("DELETE FROM tulip_imports WHERE file = ? AND sheet = '' "
                   "AND target IS NULL AND reason LIKE 'unreadable_file:%'",
                   (str(path),))
    # several tables on one sheet: one import each (blocks.py)
    for sheet in (part for whole in loaded for part in blocks.split(whole)):
        prev = previous(db, str(path), sheet.name)
        if unchanged(prev, sha1, model_id):
            # imported / imported_with_warnings, or refused / needs_review
            # by this same model under this schema: nothing new to try
            counts["unchanged"] = counts.get("unchanged", 0) + 1
            continue
        sheet.file = str(path)
        result = tulip.import_sheet_safely(sheet, targets, locale,
                                           confidence)
        result["file"] = str(path)
        # where the sheet comes from, for compare.py's preferred source
        result["document_date"] = compare.document_date(
            sheet, result["row_numbers"], locale, path.name)
        result["file_date"] = compare.file_date(path)
        result["origin"] = compare.origin(path, root)
        # what the model was asked, for the owner's corrections
        result["locale"], result["targets"] = locale, list(targets)
        rows_in = max(0, len(sheet.rows) - 1)
        store(db, result, sha1, model_id, rows_in)
        report(result, path.name, counts, show_rows)
    return counts


def report(result, name, counts, show_rows):
    counts[result["status"]] = counts.get(result["status"], 0) + 1
    ch = result.get("changes") or {}
    changes = ", ".join("%d %s" % (ch[k], k) for k in (
        "added", "changed", "removed", "removed_from_other_table")
        if ch.get(k))
    print("%-22s %s | %s%s%s" % (result["status"], name, result["sheet"],
                                 (" (%s)" % result["reason"])
                                 if result["reason"] else "",
                                 (" - rows: %s" % changes) if changes
                                 else ""))
    if show_rows:
        show(result)


def confidence_lines(result):
    """The preview's lines for the bands: "column C -> price: sure"."""
    conf = result.get("confidence")
    if not conf or not conf.get("columns"):
        return []
    out = ["  how sure (%s):" % ("calibrated for this model"
                                 if conf.get("calibrated") else
                                 "not calibrated for this model: no "
                                 "column is 'sure'; run calibrate.py")]
    for col in conf["columns"]:
        letters = col["sheet_columns"]
        where = ("column " if len(letters) == 1 else "columns ") + \
            " + ".join(letters) if letters else "the sheet"
        out.append("    %s -> %s: %s (%.3f)" % (where, col["column"],
                                                col["band"], col["score"]))
    return out


def show(result):
    print("  program:")
    for line in (result["program"] or "").splitlines():
        print("    " + line)
    for line in confidence_lines(result):
        print(line)
    for record, row in list(zip(result["rows"], result["row_numbers"]))[:5]:
        print("  row %s: %s" % (row, json.dumps(record, ensure_ascii=False,
                                                default=str)))
    if result["skipped"]:
        print("  skipped rows: %s" % result["skipped"][:5])
    print()


if __name__ == "__main__":
    sys.exit(main())
