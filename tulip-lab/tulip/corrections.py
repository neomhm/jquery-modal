"""
corrections.py - the owner's corrections, kept as future lessons
(Tulip 1.1, item D). No retraining now: a later training round can take
the lessons this writes.

At the data-check step the owner corrects an import. Each correction is a
row of tulip_corrections in documents.db, with the sheet's preview (what
the model read), the program Tulip wrote and the corrected mapping or
program:

    py corrections.py record --db documents.db --import 12 --map price=D
        a column remapped (the sheet's own letters, as --show prints them;
        "price=" alone unmaps it)
    py corrections.py record --db documents.db --import 12 \\
        --unrefuse products --header 1 --map name=A --map price=C
        a refused sheet that should have been imported
    py corrections.py record --db documents.db --import 12 --refuse not_a_table
        an import that should have been refused
    py corrections.py record --db documents.db --import 12 --program fixed.txt
        a whole corrected program
    py corrections.py record --db documents.db --import 12 --value 14:price=1.20
        one value fixed (sheet row 14): a lesson for the cell readers, not
        for the program
    py corrections.py list   --db documents.db
    py corrections.py share  --db documents.db 3     this one may leave the PC
    py corrections.py export --db documents.db --out lessons.jsonl

Privacy (the contract's section 19, opt in): corrections stay in
documents.db on the owner's PC. `export` writes only the corrections the
owner shared (`share`), unless `--private` is given for a training run on
the owner's own machine.

`export` writes one lesson per program correction, in the generator's task
format (gen/tasks.task_dict), and keeps only lessons that pass the
generator's self-check with the real runtime (lesson_problems: the program
is canonical, it runs without a problem, its rows are the truth, its lookup
keys are in the preview) and are no evaluation sheet (the handwritten set,
real_eval/, and the generated test splits when they are on this machine).
Value fixes go to a second file as cell-reader cases.
"""
import argparse
import ast
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

import config
import helpers as H
import sheets
import tulipscript as ts

HERE = pathlib.Path(__file__).resolve().parent

CORRECTIONS_TABLE = """CREATE TABLE IF NOT EXISTS tulip_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, import_id INTEGER, file TEXT,
    sheet TEXT, file_sha1 TEXT, kind TEXT, locale TEXT, targets TEXT,
    preview TEXT, program TEXT, corrected_program TEXT, mapping TEXT,
    value TEXT, sheet_rows TEXT, sheet_formats TEXT, checked INTEGER,
    problems TEXT, note TEXT, shared INTEGER DEFAULT 0, created TEXT)"""

KINDS = ("remap", "unrefuse", "refuse", "program", "value")


# ---------------------------------------------------------------------
#  programs from a mapping
# ---------------------------------------------------------------------
def helper_for(kind):
    """The cell reader that gives a field of this kind."""
    if kind in ts.HELPER_KIND and ts.HELPER_KIND[kind] == kind:
        return kind
    for helper, k in ts.HELPER_KIND.items():
        if k == kind:
            return helper
    raise ValueError("a %s field needs a program (a lookup), not a column"
                     % kind)


def _expr(target, field, letter):
    kinds = dict((f, k) for f, k, _ in ts.SCHEMAS[target])
    if field not in kinds:
        raise ValueError("%s has no field %r" % (target, field))
    return ast.parse("%s(col(%r))" % (helper_for(kinds[field]), letter),
                     mode="eval").body


def compact_letter(letter, letters):
    """The sheet's own column letter -> the letter in the compacted sheet
    the program reads (compact() removes the empty columns)."""
    if letter not in letters:
        raise ValueError("column %s is empty or not in the sheet" % letter)
    return ts.LETTERS[letters.index(letter)]


def remapped(program, mapping, letters):
    """The program with the fields of `mapping` read from other columns:
    {field: sheet letter, or None to unmap}."""
    prog = ts.parse(program)
    if prog.refusal:
        raise ValueError("a refusal has no mapping: use --unrefuse")
    outs = dict(prog.outs)
    for field, letter in mapping.items():
        if letter:
            outs[field] = _expr(prog.target, field,
                                compact_letter(letter, letters))
        else:
            outs.pop(field, None)
    order = [f for f, _, _ in ts.SCHEMAS[prog.target]]
    prog.outs = sorted(outs.items(), key=lambda kv: order.index(kv[0]))
    return ts.canonical(ts.format_program(prog))


def unrefused(target, header, mapping, letters):
    """A program for a sheet Tulip refused: its table, its header row and
    {field: sheet letter}."""
    lines = ["target(%r)" % target, "header(%d)" % int(header)]
    order = [f for f, _, _ in ts.SCHEMAS[target]]
    for field in sorted(mapping, key=order.index):
        lines.append("out.%s = %s" % (field, ast.unparse(_expr(
            target, field, compact_letter(mapping[field], letters)))))
    return ts.canonical("\n".join(lines))


# ---------------------------------------------------------------------
#  recording
# ---------------------------------------------------------------------
def create_table(db):
    with db:
        db.execute(CORRECTIONS_TABLE)


def _import_row(db, import_id):
    cols = [r[1] for r in db.execute("PRAGMA table_info(tulip_imports)")]
    row = db.execute("SELECT * FROM tulip_imports WHERE id = ?",
                     (import_id,)).fetchone()
    if row is None:
        raise ValueError("no import %s in tulip_imports" % import_id)
    return dict(zip(cols, row))


def _sheet_now(imp):
    """The sheet as it is on disk now, if it is still the imported file."""
    path = pathlib.Path(imp["file"])
    if not path.exists():
        raise ValueError("%s is no longer there" % path)
    if imp.get("file_sha1") and hashlib.sha1(
            path.read_bytes()).hexdigest() != imp["file_sha1"]:
        raise ValueError("%s changed since this import: import it again, "
                         "then correct the new import" % path.name)
    found = [s for s in sheets.load(path, imp.get("locale"))
             if s.name == imp["sheet"]]
    if not found:
        raise ValueError("no sheet %r in %s" % (imp["sheet"], path.name))
    return found[0]


def check_program(program, small, targets, locale):
    """The runtime's verdict on a corrected program -> [problems]."""
    try:
        prog = ts.parse(program)
    except ts.TulipError as e:
        return ["parse:" + e.code]
    if prog.refusal:
        return []
    res = ts.run(prog, small, H.HELPERS, locale, targets, H.TOTALS)
    if res.status not in ("imported", "imported_with_warnings"):
        return list(res.problems) or [res.status]
    return []


def record(db, import_id, kind, mapping=None, target=None, header=None,
           program=None, reason=None, value=None, note=None, shared=False,
           now=None):
    """Store one correction of an import -> its id. The corrected program
    is checked with the runtime now (checked, problems); a correction the
    runtime rejects is kept, but never becomes a lesson."""
    import gen.tasks as T
    if kind not in KINDS:
        raise ValueError("kind must be one of %s" % ", ".join(KINDS))
    create_table(db)
    imp = _import_row(db, import_id)
    targets = json.loads(imp.get("targets") or "null") or (
        [target] if target else [imp["target"]] if imp["target"] else [])
    locale = imp.get("locale")
    if not targets or not locale:
        raise ValueError("this import does not say its targets and locale "
                         "(imported before Tulip 1.1): import it again")
    sheet = _sheet_now(imp)
    small, letters = sheets.compact(sheet)
    preview = sheets.preview(small, targets, locale)
    corrected = None
    if kind == "remap":
        corrected = remapped(imp["program"], mapping or {}, letters)
    elif kind == "unrefuse":
        if target not in targets:
            targets = targets + [target] if len(targets) < 4 else \
                targets[:3] + [target]
            preview = sheets.preview(small, targets, locale)
        corrected = unrefused(target, header, mapping or {}, letters)
    elif kind == "refuse":
        corrected = ts.canonical("refuse(%r)" % reason)
    elif kind == "program":
        corrected = ts.canonical(program)
    elif kind == "value":
        # the cell: the column's first letter in the program Tulip wrote
        import confidence as C
        expr = dict(ts.parse(imp["program"]).outs).get(value["column"])
        found = C.letters_of(expr) if expr is not None else []
        value = dict(value, letter=found[0] if found else None)
    problems = check_program(corrected, small, targets, locale) \
        if corrected else []
    at = now or datetime.datetime.now().isoformat(timespec="seconds")
    with db:
        cur = db.execute(
            "INSERT INTO tulip_corrections (import_id, file, sheet, "
            "file_sha1, kind, locale, targets, preview, program, "
            "corrected_program, mapping, value, sheet_rows, sheet_formats, "
            "checked, problems, note, shared, created) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (import_id, imp["file"], imp["sheet"], imp.get("file_sha1"), kind,
             locale, json.dumps(targets), preview, imp["program"], corrected,
             json.dumps({"target": target, "header": header,
                         "fields": mapping} if kind == "unrefuse" else
                        mapping, ensure_ascii=False) if mapping else None,
             json.dumps(value, ensure_ascii=False, default=str)
             if value else None,
             json.dumps([[T.tag(v) for v in r] for r in small.rows],
                        ensure_ascii=False),
             json.dumps(small.formats) if small.formats else None,
             0 if problems else 1, json.dumps(problems), note,
             1 if shared else 0, at))
        return cur.lastrowid


def share(db, correction_id, shared=True):
    """The owner's opt in (or out): this correction may leave the PC."""
    with db:
        db.execute("UPDATE tulip_corrections SET shared = ? WHERE id = ?",
                   (1 if shared else 0, correction_id))


# ---------------------------------------------------------------------
#  lessons
# ---------------------------------------------------------------------
def rows_hash(rows):
    """One sheet's cells, whatever their form, as one hash."""
    def plain(v):
        if v is None:
            return None
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v).strip()
    grid = [[plain(v) for v in r] for r in rows]
    while grid and not any(x is not None and x != "" for x in grid[-1]):
        grid.pop()
    return hashlib.sha1(json.dumps(grid, ensure_ascii=False).encode(
        "utf-8")).hexdigest()


def evaluation_hashes(presets=None):
    """The cells of every evaluation sheet: the handwritten set,
    real_eval/, and the generated test splits found on this machine.
    A lesson must never be one of them."""
    import gen.tasks as T
    out = set()
    for folder in (HERE / "handwritten", HERE / "real_eval",
                   HERE / "handwritten_1_1"):
        for path in sorted(folder.glob("*")):
            if path.suffix.lower() not in sheets.READABLE:
                continue
            try:
                for s in sheets.load(path):
                    out.add(rows_hash(s.rows))
                    out.add(rows_hash(sheets.compact(s)[0].rows))
            except Exception:
                continue
    from gen.make import iter_split
    for preset in (list(config.PRESETS) if presets is None else presets):
        for split in config.EVAL_SPLITS:
            for task in iter_split(preset, split):
                out.add(rows_hash(T.sheet_from_task(task).rows))
    return out


def lesson_of(c):
    """A correction row (dict) -> a lesson in the generator's task
    format, or None for a value fix."""
    import gen.sheetkit as K
    import gen.tasks as T
    if not c["corrected_program"]:
        return None
    targets = json.loads(c["targets"])
    rows = [[T.untag(v) for v in r] for r in json.loads(c["sheet_rows"])]
    formats = json.loads(c["sheet_formats"]) if c["sheet_formats"] else None
    small = sheets.Sheet(c["sheet"], rows, formats)
    prog = ts.parse(c["corrected_program"])
    truth = []
    if not prog.refusal:
        res, _ = K.self_check(c["corrected_program"], small, c["locale"],
                              targets)
        truth = K.clean_rows(res.rows) if res is not None else []
    return {
        "id": "correction-%06d" % c["id"], "split": "train",
        "lang": c["locale"].split("-")[0], "locale": c["locale"],
        "activity": None, "family": "correction:%s" % c["kind"],
        "traps": [], "targets": targets,
        "answer": prog.refusal or prog.target,
        "format": "csv" if c["file"].lower().endswith(".csv") else "xlsx",
        "sheet": {"name": c["sheet"],
                  "rows": json.loads(c["sheet_rows"]), "formats": formats},
        "preview": sheets.preview(small, targets, c["locale"]),
        "program": c["corrected_program"], "truth": truth,
        "holdout": [], "n_rows": len(truth)}


def lesson_problems(lesson, forbidden=frozenset()):
    """The generator's self-check (section 10.1) on a lesson, with the
    real runtime -> [problems], [] when it may be trained on."""
    import gen.sheetkit as K
    import gen.tasks as T
    problems = []
    program = lesson["program"]
    try:
        if ts.canonical(program) != program:
            problems.append("not_canonical")
    except ts.TulipError as e:
        return ["parse:" + e.code]
    sheet = T.sheet_from_task(lesson)
    if sheets.preview(sheet, lesson["targets"], lesson["locale"]) != \
            lesson["preview"]:
        problems.append("preview_differs")
    prog = ts.parse(program)
    if prog.refusal:
        if lesson["answer"] != prog.refusal:
            problems.append("answer_differs")
    else:
        res, found = K.self_check(program, sheet, lesson["locale"],
                                  lesson["targets"])
        problems += ["self_check:" + p for p in found]
        if res is None or not K.truth_matches(res, lesson["truth"]):
            problems.append("self_check:truth")
        if not lesson["truth"]:
            problems.append("no_rows")
    values = "\n".join(line for line in lesson["preview"].splitlines()
                       if line.startswith("VALUES "))
    for key in T.lookup_keys(program):
        if key not in values:
            problems.append("lookup_not_in_values")
    if rows_hash(sheet.rows) in forbidden:
        problems.append("evaluation_sheet")
    return problems


def value_case(c):
    """A value fix -> a cell-reader case: the helper the program used for
    that column, the cell as written, the locale and the right value."""
    import gen.tasks as T
    fix = json.loads(c["value"])
    rows = [[T.untag(v) for v in r] for r in json.loads(c["sheet_rows"])]
    prog = ts.parse(c["program"])
    expr = dict(prog.outs).get(fix["column"])
    helper = expr.func.id if isinstance(expr, ast.Call) and isinstance(
        expr.func, ast.Name) else None
    cell = None
    if fix.get("letter"):
        col = ts.LETTERS.index(fix["letter"])
        row = rows[fix["row"] - 1] if 0 < fix["row"] <= len(rows) else []
        cell = row[col] if col < len(row) else None
    return {"id": "correction-%06d" % c["id"], "helper": helper,
            "locale": c["locale"], "cell": cell, "expected": fix["new"],
            "column": fix["column"], "row": fix["row"]}


def export(db, out, include_private=False, values_out=None,
           forbidden=None):
    """Write the lessons (JSON lines) -> {"lessons", "rejected",
    "private", "values"}."""
    create_table(db)
    cols = [r[1] for r in db.execute("PRAGMA table_info(tulip_corrections)")]
    rows = [dict(zip(cols, r)) for r in db.execute(
        "SELECT * FROM tulip_corrections ORDER BY id")]
    forbidden = evaluation_hashes() if forbidden is None else forbidden
    counts = {"lessons": 0, "rejected": [], "private": 0, "values": 0}
    lessons, values = [], []
    for c in rows:
        if not c["shared"] and not include_private:
            counts["private"] += 1
            continue
        if c["kind"] == "value":
            values.append(value_case(c))
            continue
        lesson = lesson_of(c)
        problems = lesson_problems(lesson, forbidden) if lesson else \
            ["no_program"]
        if problems:
            counts["rejected"].append((c["id"], problems))
            continue
        lessons.append(lesson)
    with open(out, "w", encoding="utf-8") as f:
        for lesson in lessons:
            f.write(json.dumps(lesson, ensure_ascii=False) + "\n")
    counts["lessons"] = len(lessons)
    if values:
        path = values_out or pathlib.Path(out).with_suffix(".values.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for v in values:
                f.write(json.dumps(v, ensure_ascii=False, default=str) +
                        "\n")
        counts["values"] = len(values)
    return counts


# ---------------------------------------------------------------------
def _pairs(items):
    out = {}
    for item in items or []:
        field, _, letter = item.partition("=")
        out[field.strip()] = letter.strip().upper() or None
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="The owner's corrections")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--db", required=True)
    r.add_argument("--import", dest="import_id", type=int, required=True)
    r.add_argument("--map", action="append",
                   help="field=LETTER (the sheet's own letter); field= "
                   "unmaps it")
    r.add_argument("--unrefuse", metavar="TARGET")
    r.add_argument("--header", type=int, default=1)
    r.add_argument("--refuse", metavar="REASON")
    r.add_argument("--program", metavar="FILE")
    r.add_argument("--value", metavar="ROW:FIELD=VALUE")
    r.add_argument("--note")
    r.add_argument("--share", action="store_true")
    lst = sub.add_parser("list")
    lst.add_argument("--db", required=True)
    sh = sub.add_parser("share")
    sh.add_argument("--db", required=True)
    sh.add_argument("id", type=int)
    sh.add_argument("--undo", action="store_true")
    ex = sub.add_parser("export")
    ex.add_argument("--db", required=True)
    ex.add_argument("--out", required=True)
    ex.add_argument("--private", action="store_true",
                    help="also the corrections not shared (for training on "
                    "this PC only)")
    args = ap.parse_args(argv)
    db = sqlite3.connect(args.db)
    if args.cmd == "record":
        if args.unrefuse:
            cid = record(db, args.import_id, "unrefuse",
                         mapping=_pairs(args.map), target=args.unrefuse,
                         header=args.header, note=args.note,
                         shared=args.share)
        elif args.refuse:
            cid = record(db, args.import_id, "refuse", reason=args.refuse,
                         note=args.note, shared=args.share)
        elif args.program:
            cid = record(db, args.import_id, "program",
                         program=pathlib.Path(args.program).read_text(
                             encoding="utf-8"), note=args.note,
                         shared=args.share)
        elif args.value:
            where, _, new = args.value.partition("=")
            row, _, field = where.partition(":")
            cid = record(db, args.import_id, "value",
                         value={"row": int(row), "column": field,
                                "new": new}, note=args.note,
                         shared=args.share)
        else:
            cid = record(db, args.import_id, "remap",
                         mapping=_pairs(args.map), note=args.note,
                         shared=args.share)
        c = db.execute("SELECT checked, problems FROM tulip_corrections "
                       "WHERE id = ?", (cid,)).fetchone()
        print("correction %d recorded%s" % (cid, "" if c[0] else
                                            " - the runtime rejects it: %s"
                                            % c[1]))
    elif args.cmd == "list":
        create_table(db)
        for row in db.execute("SELECT id, kind, file, sheet, checked, shared, "
                              "created FROM tulip_corrections ORDER BY id"):
            print("%d  %-8s %s | %s  %s%s  %s" % (
                row[0], row[1], pathlib.Path(row[2]).name, row[3],
                "checked" if row[4] else "REJECTED BY THE RUNTIME",
                ", shared" if row[5] else "", row[6]))
    elif args.cmd == "share":
        share(db, args.id, not args.undo)
    elif args.cmd == "export":
        counts = export(db, args.out, args.private)
        print("%d lessons written to %s; %d not shared (use share, or "
              "--private); %d value fixes; rejected: %s" % (
                  counts["lessons"], args.out, counts["private"],
                  counts["values"], counts["rejected"] or "none"))
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
