"""
gen/sheetkit.py - build one sheet, its program and its truth.

A layout family (gen/layouts/*.py) describes a table as COLUMNS (a header
and one cell per record), the program's out lines (with column KEYS in
place of letters), and the TRUE output rows. The kit then:

  1. orders the columns (shuffled, with 0-5 irrelevant extra columns),
  2. writes the rows: title rows, a blank row, a group-label row (two-row
     header), the header row, the data rows with section rows, blank
     rows, repeated header rows and subtotals, a totals row, notes rows,
  3. writes the program (letters in place of keys, canonical form),
  4. runs the program with the REAL runtime and helpers and checks that
     it gives exactly the true rows (the self-check of section 10.1).

Only a task that passes the self-check is kept.
"""
import datetime
import string

import helpers as H
import sheets
import tulipscript as ts

LETTERS = ts.LETTERS


class Column:
    """One column: header text, one cell per record, formats (xlsx)."""

    def __init__(self, key, header, cells, fmts=None, kind="field"):
        self.key = key
        self.header = header
        self.cells = list(cells)
        self.fmts = list(fmts) if fmts is not None else [None] * len(cells)
        self.kind = kind            # field | extra | trap
        self.group = None           # label above it (two-row header)
        self.symbol = False         # text amounts show the currency


class Table:
    """Everything a family decides about one sheet."""

    def __init__(self, target):
        self.target = target
        self.columns = []           # [Column]
        self.blocks = []            # [[key, key]]: stay together, in order
        self.outs = []              # [(field, template)] - {key} -> letter
        self.truth = []             # the true output rows
        self.keeps = []             # [(predicate, key, extra...)]
        self.unpivot = []           # [key]
        self.sections = []          # [(record index, title)]
        self.subtotals = []         # [(after record index, label, {key: value})]
        self.totals = None          # (label, {key: value}) or None
        self.total_label_key = None  # the column holding totals words
        self.title_rows = []        # texts above the header
        self.blank_after_title = False
        self.group_labels = {}      # key -> label (two-row header)
        self.notes_rows = []        # texts below the table
        self.notes_key = None       # the column holding notes rows
        self.repeat_header_at = []  # record indexes
        self.blank_rows_at = []     # record indexes
        self.no_header = False      # header(0)
        self.traps = set()
        self.first_column_fixed = []  # keys that stay first (e.g. name)
        self.shuffle = True
        self.sheet_name = None      # the sheet's name, when it matters

    def col(self, key):
        for c in self.columns:
            if c.key == key:
                return c
        raise KeyError(key)

    def has(self, key):
        return any(c.key == key for c in self.columns)

    def add(self, column):
        self.columns.append(column)
        return column

    @property
    def n(self):
        return len(self.columns[0].cells) if self.columns else 0


def ordered_columns(table, rng):
    """Blocks of columns in their final order."""
    blocks, placed = [], set()
    for block in table.blocks:
        blocks.append(list(block))
        placed.update(block)
    for c in table.columns:
        if c.key not in placed:
            blocks.append([c.key])
    fixed = [b for b in blocks if any(k in table.first_column_fixed
                                      for k in b)]
    rest = [b for b in blocks if b not in fixed]
    if table.shuffle and rng.random() < 0.6:
        rng.shuffle(rest)
    order = fixed + rest
    return [k for b in order for k in b]


def cell_text_for_header(value):
    return value


def assemble(table, fmt, rng):
    """-> (grid, formats, header_row, letters {key: letter})."""
    keys = ordered_columns(table, rng)
    if len(keys) > 26:
        letters = {}
    else:
        letters = dict((k, LETTERS[i]) for i, k in enumerate(keys))
    cols = [table.col(k) for k in keys]
    width = len(cols)
    rows, fmts = [], []

    def add(row, fmt_row=None):
        rows.append(row)
        fmts.append(fmt_row or [None] * width)

    for text in table.title_rows:
        add([text] + [None] * (width - 1))
    if table.title_rows and table.blank_after_title:
        add([None] * width)
    if table.group_labels:
        row = [None] * width
        seen = set()
        for i, c in enumerate(cols):
            label = table.group_labels.get(c.key)
            if label and label not in seen:
                row[i] = label
                seen.add(label)
        add(row)
    header_row = 0
    header = [c.header for c in cols]
    if not table.no_header:
        add(list(header))
        header_row = len(rows)
    section_at = dict(table.sections)
    subtotal_after = {}
    for i, label, sums in table.subtotals:
        subtotal_after.setdefault(i, []).append((label, sums))
    first_col = cols[0].key if cols else None
    for i in range(table.n):
        if i in table.blank_rows_at:
            add([None] * width)
        if i in table.repeat_header_at and not table.no_header:
            add(list(header))
        if i in section_at:
            row = [None] * width
            row[0] = section_at[i]
            add(row)
        add([c.cells[i] for c in cols], [c.fmts[i] for c in cols])
        for label, sums in subtotal_after.get(i, []):
            add(summary_row(cols, table.total_label_key or first_col,
                            label, sums, fmt))
    if table.totals:
        label, sums = table.totals
        if rng.random() < 0.3:
            add([None] * width)
        add(summary_row(cols, table.total_label_key or first_col, label,
                        sums, fmt))
    if table.notes_rows:
        if rng.random() < 0.5:
            add([None] * width)
        # with sections(), a one-cell row is a section title: it must sit
        # in the same (first) column as the other titles
        where = [c.key for c in cols].index(table.notes_key) \
            if table.notes_key in [c.key for c in cols] and \
            not table.sections else 0
        for text in table.notes_rows:
            row = [None] * width
            row[where] = text
            add(row)
    return rows, fmts, header_row, letters


def summary_row(cols, label_key, label, sums, fmt):
    """A totals / subtotal row: the label in its column, the sums in
    theirs, nothing else."""
    row = [None] * len(cols)
    for i, c in enumerate(cols):
        if c.key == label_key:
            row[i] = label
        elif c.key in sums:
            # the same style as the column (a currency read from the
            # cells must be readable on these rows too)
            value, _ = fmt.money(sums[c.key], symbol=c.symbol) \
                if not isinstance(sums[c.key], int) or fmt.typed \
                else (str(sums[c.key]), None)
            row[i] = value
    return row


def program_text(table, header_row, letters):
    """The program with letters in place of keys, in canonical form."""
    def fill(template):
        out = template
        for k, letter in letters.items():
            out = out.replace("{%s}" % k, "'%s'" % letter)
        return out

    lines = ["target(%r)" % table.target, "header(%d)" % header_row]
    if table.sections:
        lines.append("sections()")
    for keep in table.keeps:
        pred, key = keep[0], keep[1]
        where = "'section'" if key == "section" else "'%s'" % letters[key]
        extra = "".join(", %r" % x for x in keep[2:])
        lines.append("keep(%s(%s%s))" % (pred, where, extra))
    if table.unpivot:
        lines.append("unpivot(%s)" % ", ".join("'%s'" % letters[k]
                                               for k in table.unpivot))
    order = [f for f, _, _ in ts.SCHEMAS[table.target]]
    for field, template in sorted(table.outs,
                                  key=lambda o: order.index(o[0])):
        lines.append("out.%s = %s" % (field, fill(template)))
    return ts.canonical("\n".join(lines))


class Sheet:
    def __init__(self, name, rows, formats=None):
        self.name, self.rows, self.formats = name, rows, formats


def clean_rows(rows):
    """Remove None keys - the comparison of section 10.6."""
    return [dict((k, v) for k, v in r.items() if v is not None)
            for r in rows]


def self_check(program, sheet, locale, targets):
    """Run the program with the real runtime and helpers.
    -> (result, problems) where problems is a list of words."""
    try:
        prog = ts.parse(program)
    except ts.TulipError as e:
        return None, ["parse:" + e.code]
    res = ts.run(prog, sheet, H.HELPERS, locale, targets, H.TOTALS)
    return res, list(res.problems)


def truth_matches(res, truth):
    return clean_rows(res.rows) == clean_rows(truth)


# check 5 of section 10.8: how many true values the helpers gave back
VALUE_STATS = {"values": 0, "wrong": 0}


def count_values(res, truth):
    got = clean_rows(res.rows) if res is not None else []
    want = clean_rows(truth)
    total = sum(len(r) for r in want)
    wrong = 0
    for i, r in enumerate(want):
        g = got[i] if i < len(got) else {}
        wrong += sum(1 for k, v in r.items() if g.get(k) != v)
    VALUE_STATS["values"] += total
    VALUE_STATS["wrong"] += wrong


def to_grid_cell(v):
    """Values as sheets.load() would give them back from a real file
    (xlsx: dates as datetimes, whole floats as ints)."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, datetime.date) and not isinstance(v,
                                                      datetime.datetime):
        return datetime.datetime(v.year, v.month, v.day)
    return v


def finish(table, fmt, rng, name, locale, targets):
    """Assemble, write the program, self-check (adding a totals filter
    when a totals row would be imported). -> dict or (None, reason)."""
    rows, fmts, header_row, letters = assemble(table, fmt, rng)
    if not letters:
        return None, "too_wide_by_accident"
    rows = [[to_grid_cell(v) for v in r] for r in rows]
    sheet_obj = sheets.Sheet(name, rows, fmts if fmt.typed else None)
    small, original = sheets.compact(sheet_obj)
    if len(original) != max(len(r) for r in rows):
        return None, "empty_column"
    program = program_text(table, header_row, letters)
    res, problems = self_check(program, small, locale, targets)
    if res is not None and any(p.startswith("totals_row_imported")
                               for p in problems) and \
            table.total_label_key and \
            not any(k[0] == "not_total" for k in table.keeps):
        table.keeps.append(("not_total", table.total_label_key))
        program = program_text(table, header_row, letters)
        res, problems = self_check(program, small, locale, targets)
    count_values(res, table.truth)
    if res is None or problems or res.status not in (
            "imported", "imported_with_warnings"):
        return None, "self_check:" + ",".join(problems[:3])
    if not truth_matches(res, table.truth):
        return None, "truth_mismatch"
    return {"sheet": small, "program": program, "header_row": header_row,
            "letters": letters, "result": res}, None
