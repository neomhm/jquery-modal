"""
contract.py - the one declared format of every output column
(tables.schema.json), and the conversion of Tulip's rows into it.

Tulip's program works with its own field kinds (section 6 of the build
instructions): a weekday is 0-6, a day's hours are one text such as
"09:00-12:00, 14:00-19:00", a VAT rate is a fraction (0.055). The PLAN's
other parts - the loader, Daisy - want other forms (a day name, opens and
closes, a percent). Instead of every reader guessing, ONE file declares
the format of every column, and Tulip converts its rows at output, after
the runtime has checked them:

    import contract
    rows, sources, numbers = contract.convert("opening_hours", rows,
                                              sources, numbers)
    problems = contract.check_rows("opening_hours", rows)   # [] when fine

The model and TulipScript are unchanged, so this works with every model
file. Only the Python standard library is used, so the loader and Daisy
can import this file (or read tables.schema.json themselves).

    load()                 the schema (tables.schema.json), read once
    columns(table)         the declared columns of a table, in order
    sql_type(column)       its SQLite type
    convert(...)           Tulip's rows -> rows in the declared format
    to_internal(...)       the reverse (tests prove nothing is lost)
    check_value / check_rows   is every value in its declared format?
"""
import datetime
import functools
import json
import math
import pathlib
import re
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "tables.schema.json"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday"]
# one opening range in Tulip's hours text: "09:00-12:00"
RANGE = re.compile(r"^([0-2][0-9]:[0-5][0-9])-([0-2][0-9]:[0-5][0-9])$")


@functools.lru_cache(maxsize=None)
def load(path=None):
    """The schema as a dict, read once (tables.schema.json)."""
    path = pathlib.Path(path) if path else SCHEMA_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def version():
    return load()["version"]


def tables():
    return list(load()["tables"])


def columns(table):
    """The declared columns of a table, in their order: [{name, format,
    required, values, tulip...}]."""
    return load()["tables"][table]["columns"]


def column_names(table):
    return [c["name"] for c in columns(table)]


def sql_type(column):
    return load()["formats"][column["format"]]["sql"]


def _source_field(column):
    """The field of Tulip's row a column comes from (its own name unless
    the schema says otherwise)."""
    return (column.get("tulip") or {}).get("field", column["name"])


# ---------------------------------------------------------------------
#  Tulip's rows -> the declared format
# ---------------------------------------------------------------------
def hours_ranges(text):
    """Tulip's hours text -> [(opens, closes)], or [] for "closed".
    ValueError on anything else (the hours() helper never writes it)."""
    if text == "closed":
        return []
    out = []
    for part in text.split(", "):
        m = RANGE.match(part)
        if not m:
            raise ValueError("not a Tulip hours text: %r" % text)
        out.append((m.group(1), m.group(2)))
    return out


def normal_text(value):
    """The text format: NFKC, trimmed, single spaces. Tulip's text() helper
    already writes this, except when it removed a direction mark from
    between a letter and its accent ("e" + U+200E + U+0301): the letter
    and the accent then only become one character (é) here."""
    return " ".join(unicodedata.normalize("NFKC", value).split()) or None


def _convert_value(how, value):
    """One value, by the converter named in the schema."""
    if value is None:
        return None
    if how == "weekday_name":
        return DAYS[value]
    if how == "fraction_to_percent":
        # 0.055 -> 5.5 (rounded, so 0.07 does not become 7.000000000000001)
        return round(float(value) * 100, 4)
    raise ValueError("unknown converter %r" % how)


def convert(table, rows, sources=None, row_numbers=None):
    """Tulip's rows (and their sources and sheet row numbers) -> rows in
    the declared format of tables.schema.json.

    A column whose Tulip field the program did not assign is left out of
    the row, as Tulip leaves it out (section 10.6); an assigned field
    with no value gives None. A table with a "split" field (opening
    hours) gives one row per range of that field: the sources and the
    row number of the sheet row are repeated on each."""
    spec = load()["tables"][table]
    cols = spec["columns"]
    split = (spec.get("tulip") or {}).get("split")
    sources = sources if sources is not None else [{} for _ in rows]
    row_numbers = row_numbers if row_numbers is not None else \
        [None] * len(rows)
    out_rows, out_sources, out_numbers = [], [], []
    for row, src, number in zip(rows, sources, row_numbers):
        pieces = [None]                   # one output row, no split
        if split and row.get(split) is not None:
            ranges = hours_ranges(row[split])
            pieces = ranges if ranges else ["closed"]
        for piece in pieces:
            new, new_src = {}, {}
            for col in cols:
                field = _source_field(col)
                if field not in row:
                    continue              # not in this sheet
                how = (col.get("tulip") or {}).get("convert")
                value = row[field]
                if how in ("range_opens", "range_closes", "range_closed"):
                    if value is None:
                        value = None
                    elif how == "range_closed":
                        value = piece == "closed"
                    elif piece == "closed":
                        value = None
                    else:
                        value = piece[0] if how == "range_opens" \
                            else piece[1]
                elif how:
                    value = _convert_value(how, value)
                if col["format"] == "text" and isinstance(value, str):
                    value = normal_text(value)
                new[col["name"]] = value
                if field in src:
                    new_src[col["name"]] = list(src[field])
            out_rows.append(new)
            out_sources.append(new_src)
            out_numbers.append(number)
    return out_rows, out_sources, out_numbers


def convert_rows(table, rows):
    """convert() for rows alone (the truth of a task, for instance)."""
    return convert(table, rows)[0]


# ---------------------------------------------------------------------
#  the reverse, to prove the conversion loses nothing
# ---------------------------------------------------------------------
def to_internal(table, rows, row_numbers):
    """Rows in the declared format (with their sheet row numbers) ->
    Tulip's rows. The rows convert() split from one sheet row - same
    row number, same day, all open - are joined back into one."""
    spec = load()["tables"][table]
    cols = spec["columns"]
    split = (spec.get("tulip") or {}).get("split")
    out, out_numbers = [], []
    for row, number in zip(rows, row_numbers):
        base = {}
        for col in cols:
            how = (col.get("tulip") or {}).get("convert")
            if col["name"] not in row or how in ("range_opens",
                                                 "range_closes",
                                                 "range_closed"):
                continue
            value = row[col["name"]]
            if value is not None and how == "weekday_name":
                value = DAYS.index(value)
            elif value is not None and how == "fraction_to_percent":
                value = round(value / 100.0, 6)
            base[_source_field(col)] = value
        if split and "closed" in row:
            part = None if row["closed"] is None else \
                "closed" if row["closed"] else \
                "%s-%s" % (row["opens"], row["closes"])
            same = out and out_numbers[-1] == number and \
                out[-1].get("day") == base.get("day") and \
                part not in (None, "closed") and \
                out[-1].get(split) not in (None, "closed")
            if same:
                out[-1][split] += ", " + part   # the next range of a day
                continue
            base[split] = part
        out.append(base)
        out_numbers.append(number)
    return out


# ---------------------------------------------------------------------
#  is every value in its declared format?
# ---------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _pattern(fmt):
    p = load()["formats"][fmt].get("pattern")
    return re.compile(p) if p else None


def check_value(column, value):
    """None when the value is in the column's declared format, else a
    short reason."""
    if value is None:
        return "required" if column.get("required") else None
    fmt = column["format"]
    spec = load()["formats"][fmt]
    kind = spec["json"]
    if kind == "boolean":
        if not isinstance(value, bool):
            return "not a boolean"
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return "not an integer"
        if fmt == "minutes" and value < 0:
            return "negative minutes"
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value):
            return "not a number"
    elif kind == "string":
        if not isinstance(value, str):
            return "not a string"
        if fmt == "text":
            if not value or unicodedata.normalize("NFKC", value) != value \
                    or " ".join(value.split()) != value:
                return "text not NFKC / trimmed / single-spaced"
        pattern = _pattern(fmt)
        if pattern and not pattern.match(value):
            return "does not match %s" % fmt
        if fmt == "date":
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                return "not a calendar date"
        if fmt == "email" and value != value.lower():
            return "e-mail not lower case"
        allowed = column.get("values") or spec.get("values")
        if allowed and value not in allowed:
            return "not one of %s" % "/".join(allowed)
    return None


def check_rows(table, rows):
    """-> ["<column>: <reason> (row i)", ...], [] when every value of
    every row is in its declared format. A column not in the schema is a
    problem too, and so is an opening range with no opens or closes."""
    cols = dict((c["name"], c) for c in columns(table))
    problems = []
    for i, row in enumerate(rows):
        for name, value in row.items():
            col = cols.get(name)
            if col is None:
                problems.append("%s: not a column of %s (row %d)"
                                % (name, table, i))
                continue
            why = check_value(col, value)
            if why:
                problems.append("%s: %s (row %d)" % (name, why, i))
        if table == "opening_hours" and row.get("closed") is False and \
                (not row.get("opens") or not row.get("closes")):
            problems.append("opens/closes: missing on an open day (row %d)"
                            % i)
        if table == "opening_hours" and row.get("closed") is True and \
                (row.get("opens") or row.get("closes")):
            problems.append("opens/closes: set on a closed day (row %d)" % i)
    return problems
