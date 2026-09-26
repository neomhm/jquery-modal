"""
Item A of the Tulip 1.1 work order: ONE declared format per column,
in tables.schema.json, and Tulip's output converted into it at output
(contract.py). These tests pin every column of every table against the
schema file, on rows the real generator drew in all ten languages, and
check the conversions, that nothing is lost, the database's types, the
migration of a Tulip 1 database and the review guard.
"""
import collections
import pathlib
import sqlite3
import tempfile

import config
import contract
import tulipscript as ts
from test_pipeline import FakeTulip

TASKS_PER_TARGET = 40


def generated_rows():
    """{target: [(task truth rows, locale)]} drawn by the real generator
    (split "val", indexes no split of any preset uses)."""
    from gen import tasks as T
    out = collections.defaultdict(list)
    i = 0
    wanted = dict((t, TASKS_PER_TARGET) for t in config.TARGETS)
    shares = T.SHARES
    try:
        for target in config.TARGETS:
            T.SHARES = [(target, 1.0)]
            while len(out[target]) < wanted[target] and i < 100000:
                task, _ = T.make_task("val", 700000 + i)
                i += 1
                if task and task["answer"] == target:
                    out[target].append((task["truth"], task["locale"]))
    finally:
        T.SHARES = shares
    return out


_ROWS = None


def rows_by_target():
    global _ROWS
    if _ROWS is None:
        _ROWS = generated_rows()
    return _ROWS


# ---------------------------------------------------------- the schema
def test_schema_names_every_table_and_every_field_once():
    """Every field Tulip writes lands in exactly one declared column (or,
    for hours, the three range columns), and every declared column comes
    from a field Tulip writes: nothing is lost, nothing is invented."""
    assert set(contract.tables()) == set(config.TARGETS)
    for target, fields in ts.SCHEMAS.items():
        names = [f for f, _, _ in fields]
        used = collections.Counter()
        for col in contract.columns(target):
            field = (col.get("tulip") or {}).get("field", col["name"])
            assert field in names, (target, col["name"])
            used[field] += 1
        assert set(used) == set(names), (target, set(names) - set(used))
        for field, n in used.items():
            assert n == (3 if (target, field) == ("opening_hours", "hours")
                         else 1), (target, field, n)
        # a required field of Tulip gives a required column
        for f, _, required in fields:
            if required:
                cols = [c for c in contract.columns(target) if (
                    c.get("tulip") or {}).get("field", c["name"]) == f]
                assert any(c.get("required") for c in cols), (target, f)


def test_every_column_has_a_known_format():
    formats = contract.load()["formats"]
    for target in contract.tables():
        for col in contract.columns(target):
            assert col["format"] in formats, (target, col)
            assert contract.sql_type(col) in ("TEXT", "REAL", "INTEGER")
            if col["format"] == "enum":
                assert col.get("values"), (target, col["name"])


def test_enum_values_are_the_runtime_enums():
    for target in contract.tables():
        for col in contract.columns(target):
            if col["format"] == "enum":
                kind = dict((f, k) for f, k, _ in ts.SCHEMAS[target])[
                    col["name"]]
                assert kind.startswith("enum:")
                assert col["values"] == list(ts.ENUMS[kind[5:]]), col


# ---------------------------------------------------------- conversions
def test_the_conversions_the_skeleton_needed():
    """Day of the week: Tulip's 0-6 -> an English day name, opens and
    closes; VAT: Tulip's fraction -> a percent."""
    rows = [{"day": 0, "hours": "09:00-12:00, 14:00-19:00", "note": "RDV"},
            {"day": 6, "hours": "closed"},
            {"day": 2, "hours": "22:00-02:00"}]
    src = [{"day": [(4, "A")], "hours": [(4, "C")], "note": [(4, "D")]},
           {"day": [(5, "A")], "hours": [(5, "C")]},
           {"day": [(6, "A")], "hours": [(6, "C")]}]
    out, out_src, numbers = contract.convert("opening_hours", rows, src,
                                             [4, 5, 6])
    assert out == [
        {"day": "monday", "opens": "09:00", "closes": "12:00",
         "closed": False, "note": "RDV"},
        {"day": "monday", "opens": "14:00", "closes": "19:00",
         "closed": False, "note": "RDV"},
        {"day": "sunday", "opens": None, "closes": None, "closed": True},
        {"day": "wednesday", "opens": "22:00", "closes": "02:00",
         "closed": False}]
    assert numbers == [4, 4, 5, 6]
    assert out_src[1] == {"day": [(4, "A")], "opens": [(4, "C")],
                          "closes": [(4, "C")], "closed": [(4, "C")],
                          "note": [(4, "D")]}
    assert contract.check_rows("opening_hours", out) == []
    got = contract.convert_rows("products", [
        {"name": "Pain", "price": 1.2, "vat_rate": 0.055},
        {"name": "Vin", "price": 9.0, "vat_rate": 0.2},
        {"name": "Thé", "price": 3.0, "vat_rate": 0.07}])
    assert [r["vat_rate"] for r in got] == [5.5, 20.0, 7.0]
    assert contract.check_rows("products", got) == []


def test_unassigned_fields_stay_out_and_empty_values_stay_none():
    got = contract.convert_rows("products", [{"name": "Pain", "price": 1.2,
                                              "vat_rate": None}])
    assert got == [{"name": "Pain", "price": 1.2, "vat_rate": None}]


# ---------------------------------------------------------- every column
def test_every_column_is_pinned_on_generated_rows():
    """The rows the generator drew, in ten languages, converted: every
    value of every column is in its declared format, and every column
    of every table was seen (so none is pinned by accident)."""
    seen = collections.defaultdict(set)
    langs = set()
    for target, items in rows_by_target().items():
        assert len(items) == TASKS_PER_TARGET, target
        for truth, locale in items:
            langs.add(locale.split("-")[0])
            out = contract.convert_rows(target, truth)
            assert contract.check_rows(target, out) == [], (target, locale)
            for row in out:
                for name, value in row.items():
                    if value is not None:
                        seen[target].add(name)
    # the generator never draws a description column (a gap of Tulip 1's
    # training data, listed in REPORT.md); every other column is seen
    never_drawn = {"products": {"description"}, "services": {"description"}}
    for target in contract.tables():
        missing = set(contract.column_names(target)) - seen[target]
        assert missing == never_drawn.get(target, set()), (target, missing)
    assert langs == set(config.LANGS)


def schema_says(fmt, column, value):
    """The schema file read directly, as the loader or Daisy would read it
    (not through contract.py): is the value what the file declares?"""
    import json
    import re
    doc = json.loads(contract.SCHEMA_FILE.read_text(encoding="utf-8"))
    spec = doc["formats"][fmt]
    kind = {"string": str, "integer": int, "boolean": bool,
            "number": (int, float)}[spec["json"]]
    if not isinstance(value, kind) or (
            spec["json"] != "boolean" and isinstance(value, bool)):
        return False
    if "pattern" in spec and not re.match(spec["pattern"], value):
        return False
    allowed = column.get("values") or spec.get("values")
    return not allowed or value in allowed


def test_types_per_format_on_generated_rows():
    """The concrete Python types the loader and Daisy receive, and every
    value checked against the schema file itself."""
    types = {"text": str, "decimal": (int, float), "percent": (int, float),
             "integer": int, "minutes": int, "boolean": bool, "date": str,
             "time": str, "day": str, "currency": str, "email": str,
             "phone": str, "enum": str}
    for target, items in rows_by_target().items():
        cols = dict((c["name"], c) for c in contract.columns(target))
        for truth, _ in items:
            for row in contract.convert_rows(target, truth):
                for name, value in row.items():
                    if value is None:
                        continue
                    fmt = cols[name]["format"]
                    assert isinstance(value, types[fmt]), (target, name)
                    if fmt in ("integer", "minutes", "decimal", "percent"):
                        assert not isinstance(value, bool)
                    assert schema_says(fmt, cols[name], value), \
                        (target, name, value)


def test_nothing_is_lost():
    """convert() then to_internal() gives back Tulip's rows exactly, and a
    VAT rate is always the percent of Tulip's fraction."""
    for target, items in rows_by_target().items():
        for truth, _ in items:
            numbers = list(range(len(truth)))
            out, _, out_numbers = contract.convert(target, truth, None,
                                                   numbers)
            back = contract.to_internal(target, out, out_numbers)
            assert back == truth, target
            if target == "products":
                for row, new in zip(truth, out):
                    if row.get("vat_rate") is not None:
                        assert abs(new["vat_rate"] - 100 * row["vat_rate"]) \
                            < 1e-9, (row, new)


def test_check_value_rejects_the_old_formats():
    col = dict((c["name"], c) for c in contract.columns("opening_hours"))
    assert contract.check_value(col["day"], 0)                 # 0-6
    assert contract.check_value(col["day"], "Monday")          # not lower
    assert contract.check_value(col["opens"], "9:00")          # not HH:MM
    assert contract.check_value(col["opens"], "24:00")
    assert contract.check_value(col["closed"], 1)              # not a bool
    assert contract.check_value(col["day"], None) == "required"
    pcol = dict((c["name"], c) for c in contract.columns("products"))
    assert contract.check_value(pcol["price"], "12.50")        # a string
    assert contract.check_value(pcol["currency"], "€")
    assert contract.check_value(pcol["name"], " Pain")        # untrimmed
    scol = dict((c["name"], c) for c in contract.columns("staff"))
    assert contract.check_value(scol["start_date"], "2024-02-30")
    assert contract.check_value(scol["phone"], "06 12 34 56 78")
    assert contract.check_value(scol["email"], "Marie@Example.fr")
    assert contract.check_rows("opening_hours", [
        {"day": "monday", "closed": False}])                   # no opens
    assert contract.check_rows("products", [{"nom": "Pain"}])  # unknown


# ---------------------------------------------------------- the output
HOURS = ("target('opening_hours')\nheader(1)\nout.day = weekday(col('A'))\n"
         "out.hours = hours(col('B'))")


def hours_sheet():
    import sheets
    return sheets.Sheet("Horaires", [
        ["Jour", "Horaires"], ["lundi", "9h-12h / 14h-19h"],
        ["mardi", "9h-19h"], ["dimanche", "Fermé"]])


def test_import_sheet_writes_the_declared_format():
    t = FakeTulip([HOURS])
    r = t._import_sheet(hours_sheet(), ["opening_hours"], "fr-FR")
    assert r["status"] == "imported", r["problems"]
    assert r["contract"] == contract.version()
    assert r["rows"] == [
        {"day": "monday", "opens": "09:00", "closes": "12:00",
         "closed": False},
        {"day": "monday", "opens": "14:00", "closes": "19:00",
         "closed": False},
        {"day": "tuesday", "opens": "09:00", "closes": "19:00",
         "closed": False},
        {"day": "sunday", "opens": None, "closes": None, "closed": True}]
    assert r["row_numbers"] == [2, 2, 3, 4]
    assert r["sources"][1]["opens"] == [(2, "B")]
    assert r["sources"][3]["day"] == [(4, "A")]


def test_text_is_nfkc_even_after_a_direction_mark():
    """helpers.text() removes direction marks after NFKC: a mark between
    a letter and its accent leaves the two apart. The output joins them
    (the format of text), so the sheet is imported, not sent to review."""
    import sheets
    sheet = sheets.Sheet("Tarifs", [["Produit", "Prix"],
                                    ["Cafe\u200e\u0301  crème", "2,10"]])
    t = FakeTulip(["target('products')\nheader(1)\n"
                   "out.name = text(col('A'))\n"
                   "out.price = amount(col('B'))"])
    r = t._import_sheet(sheet, ["products"], "fr-FR")
    assert r["status"] == "imported", r
    assert r["rows"] == [{"name": "Café crème", "price": 2.1}]


def test_a_value_outside_its_format_goes_to_review():
    """The guard: if a bug ever puts a value outside its declared format,
    the sheet goes to review and no row is written."""
    real = contract.convert

    def broken(table, rows, sources=None, row_numbers=None):
        out, src, numbers = real(table, rows, sources, row_numbers)
        for row in out:
            row["day"] = "Mon"
        return out, src, numbers
    contract.convert = broken
    try:
        t = FakeTulip([HOURS])
        r = t._import_sheet(hours_sheet(), ["opening_hours"], "fr-FR")
    finally:
        contract.convert = real
    assert r["status"] == "needs_review" and r["reason"] == \
        "contract_format", r
    assert r["rows"] == [] and r["problems"]


# ---------------------------------------------------------- the database
def test_database_columns_and_types_follow_the_schema():
    import import_sheets as I
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        I.create_tables(db)
        for target in contract.tables():
            info = db.execute('PRAGMA table_info("tulip_%s")' % target)
            got = [(r[1], r[2]) for r in info]
            want = [(c["name"], contract.sql_type(c))
                    for c in contract.columns(target)] + I.BOOKKEEPING
            assert got == want, target
        t = FakeTulip([HOURS])
        r = t._import_sheet(hours_sheet(), ["opening_hours"], "fr-FR")
        r["file"] = "horaires.xlsx"
        I.store(db, r, "sha", "tulip-1.0.0", 4)
        rows = db.execute('SELECT day, opens, closes, closed, _row FROM '
                          '"tulip_opening_hours" ORDER BY rowid').fetchall()
        assert rows == [("monday", "09:00", "12:00", 0, 2),
                        ("monday", "14:00", "19:00", 0, 2),
                        ("tuesday", "09:00", "19:00", 0, 3),
                        ("sunday", None, None, 1, 4)]
        version = db.execute("SELECT contract FROM tulip_imports").fetchone()
        assert version == (contract.version(),)
        db.close()


def test_a_tulip_1_database_is_migrated_not_lost():
    """A documents.db from Tulip 1 (day 0-6, one hours text): its table
    is renamed, never deleted, and its sheets are imported again."""
    import import_sheets as I
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        db.execute("""CREATE TABLE tulip_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file TEXT, sheet TEXT,
            file_sha1 TEXT, target TEXT, status TEXT, reason TEXT,
            program TEXT, problems TEXT, warnings TEXT, rows_in INTEGER,
            rows_out INTEGER, skipped TEXT, model TEXT,
            candidates_tried INTEGER, hidden INTEGER, created TEXT)""")
        db.execute('CREATE TABLE "tulip_opening_hours" (day INTEGER, '
                   'hours TEXT, note TEXT, _file TEXT, _sheet TEXT, '
                   '_row INTEGER, _sources TEXT, _import_id INTEGER)')
        db.execute('INSERT INTO "tulip_opening_hours" VALUES (0, '
                   '"09:00-19:00", NULL, "h.xlsx", "H", 2, "{}", 1)')
        db.execute("INSERT INTO tulip_imports (file, sheet, file_sha1, "
                   "status, model) VALUES ('h.xlsx', 'H', 'sha', "
                   "'imported', 'tulip-1.0.0')")
        db.commit()
        I.create_tables(db)
        names = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        old = [n for n in names if n.startswith("tulip_opening_hours_before")]
        assert len(old) == 1, names
        assert db.execute('SELECT day, hours FROM "%s"' % old[0]).fetchall() \
            == [(0, "09:00-19:00")]
        assert I.table_columns(db, "tulip_opening_hours")[:5] == \
            ["day", "opens", "closes", "closed", "note"]
        prev = I.previous(db, "h.xlsx", "H")
        assert not I.unchanged(prev, "sha", "tulip-1.0.0")   # re-import
        # a second start changes nothing more
        I.create_tables(db)
        names2 = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        assert sorted(names2) == sorted(names)
        db.close()


def test_evaluation_compares_in_the_declared_format():
    """The evaluation scores the rows Tulip now writes: a truth written in
    Tulip's field kinds (the handwritten set, every task) is converted
    first; a real_eval line copied from --show says so and is not."""
    import json
    import evaluate as E
    assert E.truth_rows("opening_hours", [{"day": 6, "hours": "closed"}]) \
        == [{"day": "sunday", "closed": True}]
    assert E.truth_rows("products", [{"name": "Pain", "price": 1.2,
                                      "vat_rate": 0.055}]) == \
        [{"name": "Pain", "price": 1.2, "vat_rate": 5.5}]
    with tempfile.TemporaryDirectory() as tmp:
        folder = pathlib.Path(tmp)
        (folder / "horaires.csv").write_text(
            "Jour;Horaires\nlundi;9h-19h\ndimanche;Fermé\n",
            encoding="utf-8")
        internal = [{"day": 0, "hours": "09:00-19:00"},
                    {"day": 6, "hours": "closed"}]
        declared = [{"day": "monday", "opens": "09:00", "closes": "19:00",
                     "closed": False},
                    {"day": "sunday", "closed": True}]
        line = {"file": "horaires.csv", "sheet": "horaires",
                "locale": "fr-FR", "targets": ["opening_hours"],
                "answer": "opening_hours"}
        lines = [dict(line, truth=internal),
                 dict(line, truth=declared, truth_format="contract"),
                 dict(line, truth=[{"day": 0, "hours": "09:00-18:00"},
                                   {"day": 6, "hours": "closed"}])]
        (folder / "truth.jsonl").write_text("\n".join(
            json.dumps(x) for x in lines), encoding="utf-8")
        got = E.evaluate_folder(FakeTulip([HOURS]), folder, print)
    assert got["sheets"] == 3
    assert got["loop"] == round(2 / 3, 4), got   # the third is wrong
