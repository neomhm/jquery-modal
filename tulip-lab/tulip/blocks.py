"""
blocks.py - several tables on one sheet (Tulip 1.1, item G). Plain code,
before the model: a sheet that holds two or more tables is cut into one
sheet per table, and each is imported - or refused - on its own.

    blocks.split(sheet) -> [sheet]           one sheet: nothing to cut

A new table starts after an empty row, or beside an empty column, where a
HEADER row starts: two cells or more, none of them a number, and either
known header words (the generator's header lists of the ten languages)
or numbers in the rows under it. Everything else stays with the table
above it: a blank row inside a table, a totals or notes row after it, the
same header repeated, a title above the first table. A sheet with one
table is returned unchanged, so it is read exactly as before.

Each table is a sheet of its own rows, from R1 (the model reads it as it
reads any sheet), named "<sheet> #2"; its `row_offset` and
`column_offset` say where it lies in the sheet, and tulip.py moves the
row numbers and cells of its import back to the sheet's own.
"""
import copy
import functools
import json
import pathlib

import sheets

HERE = pathlib.Path(__file__).resolve().parent
LOOKAHEAD = 5          # rows under a header searched for numbers
TITLE_ROWS = 3         # one-cell rows (title, name, date) above a header


@functools.lru_cache(maxsize=None)
def header_words():
    """Every header text of the generator's lists (never the held-out
    ones of headers_test.json), normalised."""
    import tulipscript as ts
    words = set()
    for path in sorted((HERE / "gen" / "data").glob("*/headers.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for part in ("fields", "extra"):
            for variants in (data.get(part) or {}).values():
                for w in variants if isinstance(variants, list) else []:
                    if isinstance(w, str) and w.strip():
                        words.add(ts.norm(w))
    return frozenset(words)


def _filled(row):
    return [(j, v) for j, v in enumerate(row) if not sheets._blank(v)]


def _numberish(v):
    import tulipscript as ts
    return ts._numberish(v) or hasattr(v, "year")


def _is_header(rows, i, end):
    """Row i (of a run ending at `end`) starts a table."""
    import tulipscript as ts
    cells = _filled(rows[i])
    if len(cells) < 2 or i >= end:
        return False
    # a header is texts: a time, a date, a duration or a number is data
    if any(not isinstance(v, str) or _numberish(v) or len(v) > 40
           for _, v in cells):
        return False
    known = sum(1 for _, v in cells if ts.norm(v) in header_words())
    if 2 * known >= len(cells):
        return True
    cols = set(j for j, _ in cells)
    for r in rows[i + 1:min(end, i + LOOKAHEAD) + 1]:
        if any(_numberish(v) for j, v in _filled(r) if j in cols):
            return True
    return False


def _signature(row):
    import tulipscript as ts
    return tuple((j, ts.norm(v)) for j, v in _filled(row))


def _runs(rows, lo, hi):
    """Maximal runs of non-empty rows between lo and hi (inclusive)."""
    out, start = [], None
    for i in range(lo, hi + 1):
        empty = not _filled(rows[i]) if i < len(rows) else True
        if not empty and start is None:
            start = i
        if empty and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, hi))
    return out


def _header_of_run(rows, a, b):
    """The header row of a run of rows: its first row, or the first after
    at most TITLE_ROWS rows of one cell (a title, a business name, a
    date); None when the run starts with data."""
    for i in range(a, min(a + TITLE_ROWS, b) + 1):
        if _is_header(rows, i, b):
            return i
        if len(_filled(rows[i])) > 1:
            return None
    return None


def _vertical(rows):
    """-> [(first row, last row)] of the tables, top to bottom; [] when
    there is one. A run of one-cell rows (titles, notes) goes with the
    table under it, or with the one above when no table follows."""
    blocks = []                  # [first, last, header row, kind]
    for a, b in _runs(rows, 0, len(rows) - 1):
        h = _header_of_run(rows, a, b)
        one_cell = all(len(_filled(rows[i])) <= 1 for i in range(a, b + 1))
        last_table = next((x for x in reversed(blocks) if x[3] == "table"),
                          None)
        if h is not None and last_table is not None and \
                last_table[2] is not None and \
                _signature(rows[h]) == _signature(rows[last_table[2]]):
            # the same header again: the same table goes on
            if blocks[-1][3] == "title":
                blocks.pop()
            last_table[1] = b
        elif h is not None:
            if blocks and blocks[-1][3] == "title":
                blocks[-1] = [blocks[-1][0], b, h, "table"]
            else:
                blocks.append([a, b, h, "table"])
        elif one_cell:
            blocks.append([a, b, None, "title"])
        elif blocks:
            # rows with no header: the table above goes on (a blank row
            # inside it), a title run between them included
            if blocks[-1][3] == "title" and len(blocks) > 1:
                blocks.pop()
            blocks[-1][1] = b
            blocks[-1][3] = "table"
        else:
            blocks.append([a, b, None, "table"])
    # a title run with no table under it: notes of the table above
    while len(blocks) > 1 and blocks[-1][3] == "title":
        blocks[-2][1] = blocks[-1][1]
        blocks.pop()
    tables = [x for x in blocks if x[3] == "table" and x[2] is not None]
    if len(tables) < 2:
        return []
    return [(x[0], x[1]) for x in blocks]


def _horizontal(rows, a, b):
    """-> [(first column, last column)] of side by side tables in rows
    a..b, left to right; [] when there is one."""
    width = max([len(r) for r in rows[a:b + 1]] + [0])
    used = [any(j < len(r) and not sheets._blank(r[j])
                for r in rows[a:b + 1]) for j in range(width)]
    groups, start = [], None
    for j in range(width + 1):
        if j < width and used[j] and start is None:
            start = j
        if (j == width or not used[j]) and start is not None:
            groups.append((start, j - 1))
            start = None
    if len(groups) < 2:
        return []
    tables = []
    for c0, c1 in groups:
        part = [list(r[c0:c1 + 1]) for r in rows[a:b + 1]]
        if c1 > c0 and any(_is_header(part, i, len(part) - 1)
                           for i in range(min(2, len(part)))):
            tables.append((c0, c1))
        elif tables:
            tables[-1] = (tables[-1][0], c1)
        elif groups:
            continue
    return tables if len(tables) > 1 else []


def _part(sheet, a, b, c0, c1, k):
    rows = [list(r[c0:c1 + 1]) if c1 is not None else list(r)
            for r in sheet.rows[a:b + 1]]
    fmts = None
    if sheet.formats:
        fmts = [list(f[c0:c1 + 1]) if (f and c1 is not None) else
                list(f or []) for f in sheet.formats[a:b + 1]]
    while rows and not _filled(rows[0]):          # from its first row
        rows.pop(0)
        if fmts:
            fmts.pop(0)
        a += 1
    rows, fmts = sheets._trim(rows, fmts)
    part = copy.copy(sheet)
    part.name = "%s #%d" % (sheet.name, k)
    part.rows, part.formats = rows, fmts
    part.row_offset, part.column_offset = a, c0 or 0
    return part


def split(sheet):
    """The tables of a sheet, one sheet each ([sheet] when one)."""
    rows = sheet.rows
    if not rows:
        return [sheet]
    vertical = _vertical(rows) or [(0, len(rows) - 1)]
    out = []
    for a, b in vertical:
        across = _horizontal(rows, a, b)
        if across:
            out += [(a, b, c0, c1) for c0, c1 in across]
        else:
            out.append((a, b, 0, None))
    if len(out) < 2:
        return [sheet]
    return [_part(sheet, a, b, c0, c1, k)
            for k, (a, b, c0, c1) in enumerate(out, 1)]
