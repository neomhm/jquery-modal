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
        # section 10.5: Arabic-Indic / full-width digits in text cells.
        # digits_done: the builder already drew this column's digit mode
        # (digit_mode); digits_never: never other digits (a barcode)
        self.digits_done = False
        self.digit_mode = None
        self.digits_never = False


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
            # cells must be readable on these rows too) - and its digits
            value, _ = fmt.money(sums[c.key], symbol=c.symbol) \
                if not isinstance(sums[c.key], int) or fmt.typed \
                else (str(sums[c.key]), None)
            if c.digit_mode and isinstance(value, str):
                value = fmt.digits(value, c.digit_mode == "arab",
                                   c.digit_mode == "full")
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


# =====================================================================
#  digits (section 10.5): Arabic-Indic digits in 50% (ar-SA) / 60%
#  (ar-EG) / 20% (ar-AE) and full-width digits in 25% (ja) of the text
#  cells. The builders draw a mode for their text and money columns;
#  this pass draws one for every OTHER text column that holds digits
#  (dates, times, phones, counts, durations, hours, codes written as
#  text, the columns nobody reads), and for the title rows, the notes
#  rows and the section titles - one draw per column, as people type a
#  whole column one way. A column is converted only where the truth
#  cannot move (it is read by a helper that returns a number, a date, a
#  phone... never its text) or where the truth is recomputed by a rule
#  first proven on the column as written (text(col), text(part(col))).
#  If the self-check then fails, each conversion is tried alone and the
#  ones the helpers cannot read are undone (DIGIT_STATS counts them) -
#  a digit style never costs a task.
# =====================================================================
import ast as _ast
import collections as _collections
import re as _re
import unicodedata as _ud

# readers whose result does not keep the cell's digits
DIGIT_READERS = {"amount", "integer", "percent", "date", "time", "hours",
                 "duration", "phone", "currency", "boolean", "weekday",
                 "tax_included"}
DIGIT_STATS = _collections.Counter()
DIGIT_EXAMPLES = {}
ASCII_DIGIT = _re.compile(r"[0-9]")


def digit_draw(loc, rng):
    """The mode of one column: 'arab', 'full' or None (columns.digit_mode
    with the sheet's own generator)."""
    d = loc.get("digits") or {}
    if "arab" in d and rng.random() < d["arab"]:
        return "arab"
    if "full" in d and rng.random() < d["full"]:
        return "full"
    return None


def _occurrences(table):
    """{column key | 'value' | 'section': [(path, field, call)]}: every
    col() the program reads, with the calls around it (innermost first)."""
    out = _collections.defaultdict(list)
    for field, template in table.outs:
        src = _re.sub(r"\{(\w+)\}", r"'@@\1'", template)
        try:
            tree = _ast.parse(src, mode="eval")
        except SyntaxError:
            continue

        def walk(node, parents):
            if isinstance(node, _ast.Call) and \
                    getattr(node.func, "id", "") == "col" and node.args and \
                    isinstance(node.args[0], _ast.Constant):
                arg = node.args[0].value
                key = arg[2:] if arg.startswith("@@") else arg
                out[key].append(([getattr(p.func, "id", "?")
                                  for p in reversed(parents)], field,
                                 parents[-1] if parents else None))
                return
            if isinstance(node, _ast.Call):
                parents = parents + [node]
            for child in _ast.iter_child_nodes(node):
                walk(child, parents)
        walk(tree.body, [])
    for pred_key in table.keeps:
        out[pred_key[1]].append((["keep:" + pred_key[0]], None, None))
    return out


def _part_piece(value, sep, index):
    """part() of the runtime (tulipscript): NFKC, split, strip."""
    text = _ud.normalize("NFKC", str(value))
    pieces = [p.strip() for p in text.split(_ud.normalize("NFKC", sep))]
    try:
        piece = pieces[index]
    except IndexError:
        return None
    return piece or None


def _text_rule(path, call, template_is_whole):
    """A function giving the truth of a text field from the cell, or None
    when the field's text cannot be derived from this cell alone."""
    if not template_is_whole:
        return None
    if path == ["text"]:
        return lambda v: H.text(v, None)[1] if v is not None else None
    if path == ["part", "text"] and call is not None:
        args = call.args
        if len(args) == 3 and isinstance(args[1], _ast.Constant):
            sep = args[1].value
            idx = args[2].value if isinstance(args[2], _ast.Constant) else \
                -args[2].operand.value

            def rule(v):
                if v is None:
                    return None
                piece = _part_piece(v, sep, idx)
                return H.text(piece, None)[1] if piece else None
            return rule
    return None


class _Conversion:
    """One reversible change: a column, the section titles, the title or
    notes rows."""

    def __init__(self, role, apply, revert, probe=None):
        self.role, self._apply, self._revert = role, apply, revert
        self.probe = probe
        self.on = False

    def apply(self):
        if not self.on:
            self._apply()
            self.on = True

    def revert(self):
        if self.on:
            self._revert()
            self.on = False


MACHINE_TEXT = _re.compile(r"@|https?:|www\.", _re.I)


def _convert(fmt, mode, value):
    """A text cell in other digits; an e-mail address or a web address
    is machine text and keeps its ASCII digits."""
    if isinstance(value, str) and ASCII_DIGIT.search(value) and \
            not MACHINE_TEXT.search(value):
        return fmt.digits(value, mode == "arab", mode == "full")
    return value


def _role_of(paths):
    """A short name for the report: the reader(s) of a column."""
    names = sorted(set("/".join(p for p in path if p not in ("first",))
                       for path, _, _ in paths)) or ["not read"]
    return ",".join(names)


def digit_pass(table, fmt, rng):
    """Draws and applies the digit mode of every text column (and of the
    title / notes / section rows) no builder decided. -> [_Conversion]."""
    loc = fmt.loc
    if not (loc.get("digits") or {}):
        return []
    occ = _occurrences(table)
    whole = dict((f, t) for f, t in table.outs)
    aligned = not table.unpivot and len(table.truth) == table.n
    todo = []
    for c in table.columns:
        if c.digits_done or c.digits_never or c.kind == "header":
            continue
        if not any(isinstance(v, str) and ASCII_DIGIT.search(v)
                   for v in c.cells):
            continue
        paths = list(occ.get(c.key, []))
        if c.key in table.unpivot:
            paths += occ.get("value", [])
        rules, ok = [], True
        for path, field, call in paths:
            if path and path[0].startswith("keep:"):
                if path[0] not in ("keep:not_total", "keep:not_empty"):
                    ok = False
                continue
            if path and (path[0] in DIGIT_READERS or
                         (len(path) > 1 and path[0] in ("join", "part",
                                                        "first") and
                          path[1] in DIGIT_READERS)):
                continue
            # a text field: its truth follows the cell, by a rule proven
            # on the column as written
            this = "col({%s})" % c.key
            rule = _text_rule(path, call, aligned and field and
                              whole.get(field, "").count(this) == 1 and
                              whole.get(field, "").count("col(") == 1)
            if rule is None:
                ok = False
                break
            if any(rule(v) != rec.get(field)
                   for v, rec in zip(c.cells, table.truth)):
                ok = False
                break
            rules.append((field, rule))
        if not ok:
            DIGIT_STATS["kept (text truth): " + _role_of(paths)] += 1
            continue
        mode = digit_draw(loc, rng)
        if mode is None:
            continue
        todo.append(_column_conversion(table, c, fmt, mode, rules,
                                       _role_of(paths)))
    # section titles: one draw for all of them
    if table.sections and any(ASCII_DIGIT.search(t or "")
                              for _, t in table.sections):
        paths = occ.get("section", [])
        conv = _sections_conversion(table, fmt, loc, rng, paths, aligned)
        if conv is not None:
            todo.append(conv)
    # title rows and notes rows (nobody reads them)
    for attr in ("title_rows", "notes_rows"):
        texts = getattr(table, attr)
        if any(isinstance(t, str) and ASCII_DIGIT.search(t)
               for t in texts):
            mode = digit_draw(loc, rng)
            if mode:
                todo.append(_list_conversion(table, attr, fmt, mode))
    for conv in todo:
        conv.apply()
    return todo


def _column_conversion(table, c, fmt, mode, rules, role):
    old_cells = list(c.cells)
    new_cells = [_convert(fmt, mode, v) for v in old_cells]
    old_truth = [dict((f, rec.get(f)) for f, _ in rules)
                 for rec in table.truth] if rules else []

    def apply():
        c.cells = list(new_cells)
        c.digit_mode = mode
        for field, rule in rules:
            for rec, v in zip(table.truth, new_cells):
                x = rule(v)
                if x is None:
                    rec.pop(field, None)
                else:
                    rec[field] = x

    def revert():
        c.cells = list(old_cells)
        c.digit_mode = None
        for rec, old in zip(table.truth, old_truth):
            for f, v in old.items():
                if v is None:
                    rec.pop(f, None)
                else:
                    rec[f] = v
    return _Conversion(role, apply, revert, (old_cells, new_cells))


def _sections_conversion(table, fmt, loc, rng, paths, aligned):
    fields = []
    for path, field, call in paths:
        if path and path[0] in DIGIT_READERS:
            continue
        if path == ["text"] and aligned:
            fields.append(field)
            continue
        return None
    old = list(table.sections)
    title_of, current = [], None
    starts = dict(old)
    for i in range(table.n):
        current = starts.get(i, current)
        title_of.append(current)
    for f in fields:
        if any(rec.get(f) != (H.text(t, None)[1] if t else None)
               for rec, t in zip(table.truth, title_of)):
            return None
    mode = digit_draw(loc, rng)
    if mode is None:
        return None
    new = [(i, _convert(fmt, mode, t)) for i, t in old]
    saved = [dict((f, rec.get(f)) for f in fields) for rec in table.truth]

    def apply():
        table.sections = list(new)
        starts = dict(new)
        current = None
        for i, rec in enumerate(table.truth):
            current = starts.get(i, current)
            for f in fields:
                rec[f] = H.text(current, None)[1]

    def revert():
        table.sections = list(old)
        for rec, s in zip(table.truth, saved):
            rec.update(s)
    return _Conversion("sections:" + (",".join(
        sorted(set("/".join(p) for p, _, _ in paths))) or "not read"),
        apply, revert)


def _list_conversion(table, attr, fmt, mode):
    old = list(getattr(table, attr))
    new = [_convert(fmt, mode, t) for t in old]
    return _Conversion(attr, lambda: setattr(table, attr, list(new)),
                       lambda: setattr(table, attr, list(old)))


def finish(table, fmt, rng, name, locale, targets):
    """Draw the digit styles, assemble, write the program, self-check.
    -> dict or (None, reason)."""
    convs = digit_pass(table, fmt, rng)
    state = rng.getstate()

    def attempt():
        rng.setstate(state)
        return _finish_once(table, fmt, rng, name, locale, targets)
    done, why, res = attempt()
    if done is None and convs:
        for conv in convs:
            conv.revert()
        base = attempt()
        if base[0] is None:
            done, why, res = base            # not the digits
        else:
            good = []
            for conv in convs:
                conv.apply()
                trial = attempt()
                conv.revert()
                if trial[0] is not None:
                    good.append(conv)
                else:
                    DIGIT_STATS["undone: " + conv.role] += 1
                    _example(conv, locale)
            for conv in good:
                conv.apply()
            done, why, res = attempt()
            if done is None:
                for conv in good:
                    conv.revert()
                done, why, res = attempt()
    for conv in convs:
        if conv.on:
            DIGIT_STATS["converted: " + conv.role] += 1
    if why not in ("too_wide_by_accident", "empty_column"):
        count_values(res, table.truth)       # check 5 of section 10.8
    if done is None:
        return None, why
    return done, None


def _example(conv, locale):
    """The first cell of an undone column whose reader answers
    differently once its digits changed (kept for the report)."""
    if conv.probe is None or conv.role in DIGIT_EXAMPLES:
        return
    reader = conv.role.split("/")[-1].split(",")[0]
    func = H.HELPERS.get(reader)
    old_cells, new_cells = conv.probe
    for a, b in zip(old_cells, new_cells):
        if a != b and func is not None and func(a, locale) != func(b,
                                                                  locale):
            DIGIT_EXAMPLES[conv.role] = (locale, b, func(a, locale))
            return
    DIGIT_EXAMPLES[conv.role] = (locale, None, None)


def _finish_once(table, fmt, rng, name, locale, targets):
    rows, fmts, header_row, letters = assemble(table, fmt, rng)
    if not letters:
        return None, "too_wide_by_accident", None
    rows = [[to_grid_cell(v) for v in r] for r in rows]
    sheet_obj = sheets.Sheet(name, rows, fmts if fmt.typed else None)
    small, original = sheets.compact(sheet_obj)
    if len(original) != max(len(r) for r in rows):
        return None, "empty_column", None
    program = program_text(table, header_row, letters)
    res, problems = self_check(program, small, locale, targets)
    # a totals row is imported, or cannot be read (a subtotal label in
    # a column read with part(): on a long sheet, more of them than the
    # runtime's tolerance): the program filters them out
    if res is not None and any(p.startswith("totals_row_imported") or
                               (p.startswith("parse_failures") and
                                (table.totals or table.subtotals))
                               for p in problems) and \
            table.total_label_key and \
            not any(k[0] == "not_total" for k in table.keeps):
        table.keeps.append(("not_total", table.total_label_key))
        program = program_text(table, header_row, letters)
        res, problems = self_check(program, small, locale, targets)
    if res is None or problems or res.status not in (
            "imported", "imported_with_warnings"):
        return None, "self_check:" + ",".join(problems[:3]), res
    if not truth_matches(res, table.truth):
        return None, "truth_mismatch", res
    return {"sheet": small, "program": program, "header_row": header_row,
            "letters": letters, "result": res}, None, res
