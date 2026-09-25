"""
tulipscript.py - the small language Tulip writes, and the plain code that
checks it and runs it. Nothing in this file is a model.

A TulipScript program is valid Python syntax, one statement per line, in
this fixed order:

    target('products')            or, alone:   refuse('no_matching_target')
    header(3)                     the sheet row holding the column names (0 = none)
    sections()                    optional: one-cell rows become col('section')
    keep(filled('A'))             0 to 4 row filters
    unpivot('D', 'E', 'F')        optional: one row per listed column
    out.name = text(col('B'))     one line per field used, in schema order
    ...

The program is NEVER given to exec() or eval(). parse() reads it with
Python's ast module and accepts only the shapes listed below; run()
interprets it one row at a time. A program can therefore only read cells
of the sheet and pass them through the helpers: it cannot open files,
reach the network, loop forever, or invent a value.

Every output value remembers the sheet cells it came from.
"""
import ast
import re
import time
import unicodedata
from dataclasses import dataclass, field

MAX_COLUMNS = 26
LETTERS = tuple(chr(ord('A') + i) for i in range(MAX_COLUMNS))
MAX_STATEMENTS = 45
MAX_STRING = 60
MAX_LOOKUP = 50
TIME_LIMIT = 5.0          # seconds, plus PER_ROW for every sheet row
PER_ROW = 0.0005          # ... capped at MAX_TIME
MAX_TIME = 60.0
TOLERANCE = 0.02          # share of rows allowed to fail before rejecting
EMPTY_SHARE = 0.30        # share of rows (and at least 2) allowed to be
#                           empty in a required field before rejecting

# cells that mean "nothing here" in every language
PLACEHOLDERS = {'-', '–', '—', '−', '/', 'n/a', 'n.a.', '..', '...'}

# fields that may be filled from a header, a number format or the sheet
# name alone (no col() in the expression). Every other field must read
# the row's own cells.
CONSTANT_FIELDS = {'currency', 'tax_included', 'vat_rate', 'category',
                   'unit'}

# ------------------------------------------------------------------
#  The seven target tables (FIXED). (field, type, required), in the
#  order the program must assign them.
# ------------------------------------------------------------------
ENUMS = {
    'booking_status': ('confirmed', 'pending', 'completed', 'cancelled',
                       'no_show'),
    'invoice_status': ('paid', 'unpaid', 'partial', 'overdue', 'cancelled'),
}

SCHEMAS = {
    'products': [
        ('sku', 'text', False), ('name', 'text', True),
        ('variant', 'text', False), ('description', 'text', False),
        ('category', 'text', False), ('price', 'amount', True),
        ('currency', 'currency', False), ('tax_included', 'boolean', False),
        ('vat_rate', 'percent', False), ('stock', 'integer', False),
        ('unit', 'text', False), ('barcode', 'text', False),
        ('active', 'boolean', False)],
    'services': [
        ('name', 'text', True), ('description', 'text', False),
        ('category', 'text', False), ('price', 'amount', False),
        ('currency', 'currency', False), ('tax_included', 'boolean', False),
        ('duration_min', 'duration', False), ('staff', 'text', False)],
    'opening_hours': [
        ('day', 'weekday', True), ('hours', 'hours', True),
        ('note', 'text', False)],
    'staff': [
        ('name', 'text', True), ('role', 'text', False),
        ('department', 'text', False), ('email', 'email', False),
        ('phone', 'phone', False), ('start_date', 'date', False)],
    'clients': [
        ('name', 'text', True), ('contact_person', 'text', False),
        ('email', 'email', False), ('phone', 'phone', False),
        ('address', 'text', False), ('postcode', 'text', False),
        ('city', 'text', False), ('country', 'text', False),
        ('reg_id', 'text', False), ('client_since', 'date', False)],
    'bookings': [
        ('date', 'date', True), ('start_time', 'time', True),
        ('end_time', 'time', False), ('duration_min', 'duration', False),
        ('client', 'text', False), ('service', 'text', False),
        ('staff', 'text', False), ('status', 'enum:booking_status', False),
        ('price', 'amount', False), ('currency', 'currency', False)],
    'invoice_ledger': [
        ('number', 'text', True), ('date', 'date', True),
        ('client', 'text', False), ('total', 'amount', True),
        ('tax', 'amount', False), ('currency', 'currency', False),
        ('status', 'enum:invoice_status', False),
        ('due_date', 'date', False), ('paid_date', 'date', False)],
}

# helpers live in helpers.py; each takes (value, locale) and returns
# (ok, result). The name is also the kind of value it produces, except
# tax_included, which produces a boolean.
HELPERS = ('text', 'amount', 'currency', 'integer', 'percent', 'date',
           'time', 'hours', 'weekday', 'boolean', 'phone', 'email',
           'duration', 'tax_included')
HELPER_KIND = dict((h, h) for h in HELPERS)
HELPER_KIND['tax_included'] = 'boolean'

PREDICATES = ('filled', 'is_number', 'is_date', 'not_total', 'not_value')
REFUSAL = re.compile(r'^(no_matching_target|not_a_table|too_wide|'
                     r'missing_required:[a-z_]+)$')


class TulipError(Exception):
    """A program that breaks the rules. `code` is a short fixed word."""

    def __init__(self, code, detail='', line=None):
        super().__init__('%s%s%s' % (code, (': ' + detail) if detail else '',
                                     (' (line %d)' % line) if line else ''))
        self.code, self.detail, self.line = code, detail, line


@dataclass
class Program:
    target: str = None
    refusal: str = None
    header: int = None
    sections: bool = False
    keeps: list = field(default_factory=list)      # [(name, (args...))]
    unpivot: list = None                           # ['D', 'E', ...]
    outs: list = field(default_factory=list)       # [(field, ast.expr)]


def norm(value):
    """How cells, keys and header texts are compared: NFKC, trimmed,
    single spaces, case-folded."""
    text = unicodedata.normalize('NFKC', str(value))
    return ' '.join(text.split()).casefold()


# ------------------------------------------------------------------
#  Reading a program (no sheet needed)
# ------------------------------------------------------------------
def _const(node, kinds, line, what):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) \
            and isinstance(node.operand, ast.Constant) \
            and type(node.operand.value) is int:
        value = -node.operand.value
    elif isinstance(node, ast.Constant):
        value = node.value
    else:
        raise TulipError('expected_constant', what, line)
    if type(value) not in kinds:
        raise TulipError('bad_constant', what, line)
    if isinstance(value, str) and len(value) > MAX_STRING:
        raise TulipError('string_too_long', what, line)
    return value


def _call(node, line):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        raise TulipError('expected_call', ast.unparse(node)[:40], line)
    if node.keywords:
        raise TulipError('keywords_not_allowed', node.func.id, line)
    if any(isinstance(a, ast.Starred) for a in node.args):
        raise TulipError('starred_not_allowed', node.func.id, line)
    return node.func.id, node.args


def _letter(node, prog, line, virtual=()):
    letter = _const(node, (str,), line, 'column')
    if letter not in LETTERS and letter not in virtual:
        raise TulipError('bad_column', letter, line)
    return letter


def _kind(node, prog, line):
    """Check an expression and return the kind of value it produces:
    'raw' (a cell as it is), a helper kind, 'enum' or 'boolean'."""
    name, args = _call(node, line)
    virtual = []
    if prog.sections:
        virtual.append('section')
    if prog.unpivot:
        virtual += ['name', 'value']
    if name == 'col':
        if len(args) != 1:
            raise TulipError('bad_arguments', name, line)
        _letter(args[0], prog, line, virtual)
        return 'raw'
    if name == 'header_of':
        if len(args) != 1 or not prog.header:
            raise TulipError('bad_arguments', name, line)
        _letter(args[0], prog, line)
        return 'raw'
    if name == 'format_of':
        if len(args) != 1:
            raise TulipError('bad_arguments', name, line)
        _letter(args[0], prog, line)
        return 'raw'
    if name == 'sheet_title':
        if args:
            raise TulipError('bad_arguments', name, line)
        return 'raw'
    if name == 'part':
        if len(args) != 3:
            raise TulipError('bad_arguments', name, line)
        if _kind(args[0], prog, line) not in ('raw', 'text'):
            raise TulipError('bad_argument_kind', name, line)
        if not _const(args[1], (str,), line, 'separator'):
            raise TulipError('empty_separator', name, line)
        if not -3 <= _const(args[2], (int,), line, 'index') <= 9:
            raise TulipError('bad_index', name, line)
        return 'raw'
    if name == 'join':
        if len(args) < 3:
            raise TulipError('bad_arguments', name, line)
        _const(args[0], (str,), line, 'separator')
        for a in args[1:]:
            if _kind(a, prog, line) not in ('raw', 'text'):
                raise TulipError('bad_argument_kind', name, line)
        return 'raw'
    if name == 'first':
        if len(args) < 2:
            raise TulipError('bad_arguments', name, line)
        kinds = set(_kind(a, prog, line) for a in args)
        if len(kinds) != 1:
            raise TulipError('mixed_kinds', name, line)
        return kinds.pop()
    if name == 'lookup':
        if len(args) != 2 or not isinstance(args[1], ast.Dict):
            raise TulipError('bad_arguments', name, line)
        if _kind(args[0], prog, line) not in ('raw', 'text'):
            raise TulipError('bad_argument_kind', name, line)
        table = args[1]
        if not 1 <= len(table.keys) <= MAX_LOOKUP or None in table.keys:
            raise TulipError('bad_lookup', name, line)
        keys = [_const(k, (str,), line, 'lookup key') for k in table.keys]
        if len(set(norm(k) for k in keys)) != len(keys):
            raise TulipError('duplicate_lookup_key', name, line)
        values = [_const(v, (str, bool), line, 'lookup value')
                  for v in table.values]
        if len(set(type(v) for v in values)) != 1:
            raise TulipError('mixed_lookup_values', name, line)
        return 'boolean' if type(values[0]) is bool else 'enum'
    if name in HELPERS:
        if len(args) != 1:
            raise TulipError('bad_arguments', name, line)
        if _kind(args[0], prog, line) not in ('raw', 'text'):
            raise TulipError('bad_argument_kind', name, line)
        return HELPER_KIND[name]
    raise TulipError('unknown_function', name, line)


def _lookup_values(node):
    """Every value used by lookup() calls inside an expression."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == 'lookup' and len(sub.args) == 2 \
                and isinstance(sub.args[1], ast.Dict):
            found.update(v.value for v in sub.args[1].values
                         if isinstance(v, ast.Constant))
    return found


def parse(text):
    """Text -> Program, or TulipError. Checks everything that does not
    need the sheet: grammar, order, schema, kinds."""
    try:
        tree = ast.parse(text)
    except SyntaxError as problem:
        raise TulipError('syntax', str(problem.msg), problem.lineno)
    body = tree.body
    if not body:
        raise TulipError('empty_program')
    if len(body) > MAX_STATEMENTS:
        raise TulipError('too_long')
    prog = Program()
    stage = 0     # 0 target, 1 header, 2 sections, 3 keeps, 4 unpivot, 5 outs
    schema = None
    assigned = []
    for stmt in body:
        line = stmt.lineno
        if isinstance(stmt, ast.Assign):
            if prog.target is None or prog.header is None:
                raise TulipError('out_of_order', 'out before header', line)
            if len(stmt.targets) != 1:
                raise TulipError('bad_assignment', '', line)
            tgt = stmt.targets[0]
            if not (isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == 'out'):
                raise TulipError('bad_assignment', '', line)
            fields = [f for f, _, _ in schema]
            if tgt.attr not in fields:
                raise TulipError('unknown_field', tgt.attr, line)
            if tgt.attr in assigned:
                raise TulipError('field_twice', tgt.attr, line)
            if assigned and fields.index(tgt.attr) < \
                    fields.index(assigned[-1]):
                raise TulipError('field_order', tgt.attr, line)
            kind = _kind(stmt.value, prog, line)
            reads_row = any(isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == 'col'
                            for n in ast.walk(stmt.value))
            if not reads_row and tgt.attr not in CONSTANT_FIELDS:
                raise TulipError('constant_field', tgt.attr, line)
            ftype = dict((f, t) for f, t, _ in schema)[tgt.attr]
            if ftype.startswith('enum:'):
                allowed = ENUMS[ftype[5:]]
                if kind != 'enum' or not _lookup_values(stmt.value) \
                        <= set(allowed):
                    raise TulipError('wrong_kind', tgt.attr, line)
            elif kind != ftype:
                raise TulipError('wrong_kind', '%s needs %s, got %s'
                                 % (tgt.attr, ftype, kind), line)
            assigned.append(tgt.attr)
            prog.outs.append((tgt.attr, stmt.value))
            stage = 5
            continue
        if not isinstance(stmt, ast.Expr):
            raise TulipError('statement_not_allowed',
                             type(stmt).__name__, line)
        name, args = _call(stmt.value, line)
        if name == 'refuse':
            if len(body) != 1 or len(args) != 1:
                raise TulipError('refuse_must_be_alone', '', line)
            reason = _const(args[0], (str,), line, 'reason')
            if not REFUSAL.match(reason):
                raise TulipError('bad_refusal', reason, line)
            prog.refusal = reason
            return prog
        if name == 'target':
            if stage != 0 or len(args) != 1:
                raise TulipError('out_of_order', name, line)
            prog.target = _const(args[0], (str,), line, 'target')
            if prog.target not in SCHEMAS:
                raise TulipError('unknown_target', prog.target, line)
            schema = SCHEMAS[prog.target]
            stage = 1
        elif name == 'header':
            if stage != 1 or len(args) != 1:
                raise TulipError('out_of_order', name, line)
            prog.header = _const(args[0], (int,), line, 'row')
            if not 0 <= prog.header <= 1000:
                raise TulipError('bad_header_row', str(prog.header), line)
            stage = 2
        elif name == 'sections':
            if stage != 2 or args:
                raise TulipError('out_of_order', name, line)
            prog.sections = True
            stage = 3
        elif name == 'keep':
            if stage not in (2, 3) or len(args) != 1:
                raise TulipError('out_of_order', name, line)
            pname, pargs = _call(args[0], line)
            if pname not in PREDICATES:
                raise TulipError('unknown_predicate', pname, line)
            want = 2 if pname == 'not_value' else 1
            if len(pargs) != want:
                raise TulipError('bad_arguments', pname, line)
            virtual = ['section'] if prog.sections else []
            letter = _letter(pargs[0], prog, line, virtual)
            extra = tuple(_const(a, (str,), line, 'value')
                          for a in pargs[1:])
            prog.keeps.append((pname, (letter,) + extra))
            if len(prog.keeps) > 4:
                raise TulipError('too_many_filters', '', line)
            stage = 3
        elif name == 'unpivot':
            if stage not in (2, 3) or not 2 <= len(args) <= 20:
                raise TulipError('out_of_order', name, line)
            letters = [_letter(a, prog, line) for a in args]
            if len(set(letters)) != len(letters):
                raise TulipError('duplicate_column', name, line)
            if letters != sorted(letters, key=LETTERS.index):
                raise TulipError('unpivot_order', name, line)
            prog.unpivot = letters
            stage = 4
        else:
            raise TulipError('unknown_statement', name, line)
    if prog.target is None or prog.header is None:
        raise TulipError('incomplete', 'target and header are required')
    missing = [f for f, _, req in schema if req and f not in assigned]
    if missing:
        raise TulipError('required_not_assigned', ','.join(missing))
    return prog


def _lit(value):
    return ast.unparse(ast.Constant(value))


def format_program(prog):
    """Program -> its one canonical text. parse(format_program(p)) gives
    back the same program; training data is always in this form."""
    if prog.refusal:
        return 'refuse(%s)' % _lit(prog.refusal)
    lines = ['target(%s)' % _lit(prog.target), 'header(%d)' % prog.header]
    if prog.sections:
        lines.append('sections()')
    for name, args in sorted(prog.keeps):      # filters: fixed order
        lines.append('keep(%s(%s))' % (name, ', '.join(_lit(a)
                                                      for a in args)))
    if prog.unpivot:
        lines.append('unpivot(%s)' % ', '.join(_lit(a)
                                               for a in prog.unpivot))
    for name, expr in prog.outs:
        lines.append('out.%s = %s' % (name, ast.unparse(expr)))
    return '\n'.join(lines)


def canonical(text):
    return format_program(parse(text))


# ------------------------------------------------------------------
#  Running a program on a sheet
# ------------------------------------------------------------------
@dataclass
class Result:
    status: str = 'rejected'   # imported | imported_with_warnings |
    #                            refused | rejected
    problems: list = field(default_factory=list)   # fatal, fixed words
    warnings: list = field(default_factory=list)
    rows: list = field(default_factory=list)       # [{field: value}]
    sources: list = field(default_factory=list)    # [{field: [(row, col)]}]
    row_numbers: list = field(default_factory=list)
    skipped: list = field(default_factory=list)    # [(row, reason)] - a
    #                     required cell was filled but could not be read
    empty: list = field(default_factory=list)      # rows whose required
    #                     cells are simply empty (e.g. a notes line)
    dropped: list = field(default_factory=list)    # rows removed by keep()
    sections: list = field(default_factory=list)   # section-title rows


def _blank(v):
    if v is None:
        return True
    if isinstance(v, str):
        t = v.strip()
        return not t or t.casefold() in PLACEHOLDERS
    return False


def _as_text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _letters_in(node):
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id in ('col', 'header_of', 'format_of') \
                and sub.args \
                and isinstance(sub.args[0], ast.Constant) \
                and sub.args[0].value in LETTERS:
            found.add(sub.args[0].value)
    return found


def _is_word_char(ch):
    """Letters, combining marks (Hindi matras, Arabic harakat) and digits
    continue a word; anything else ends it."""
    return unicodedata.category(ch)[0] in 'LMN'


def _starts_with_word(text, word):
    """"sous-total pains" starts with "sous-total"; "yogesh" does not
    start with the word "yog"; "小计算器" does not start with "小计"."""
    if not text.startswith(word):
        return False
    return len(text) == len(word) or not _is_word_char(text[len(word)])


def is_total_cell(v, totals):
    """The cell begins with a totals word ("Total", "Sous-total Pains",
    "Итого:", "合计")."""
    if not isinstance(v, str) or _blank(v):
        return False
    text = norm(v)
    return any(_starts_with_word(text, norm(w)) for w in totals)


def _numberish(v):
    """A typed number, or a short text that is mostly a number
    ("412,50 €", "1 240 руб.")."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if not isinstance(v, str):
        return False
    letters = sum(unicodedata.category(ch).startswith('L') for ch in v)
    return any(ch.isdigit() for ch in v) and letters <= 4


def is_totals_row(cells, totals):
    """A row is a totals row when one cell begins with a totals word and
    every OTHER filled cell is a number. "Total Fitness Ltd | Marie |
    +41 22 ..." is a client, not a totals row."""
    filled = [v for v in cells if not _blank(v)]
    for i, v in enumerate(filled):
        if is_total_cell(v, totals):
            others = filled[:i] + filled[i + 1:]
            return all(_numberish(o) for o in others)
    return False


class _Row:
    __slots__ = ('cells', 'number', 'section', 'pivot')

    def __init__(self, cells, number, section=None, pivot=None):
        self.cells, self.number = cells, number
        self.section, self.pivot = section, pivot


def run(prog, sheet, helpers, locale=None, targets=None, totals=None,
        time_limit=None):
    """Run a parsed program on a sheet and check the result.

    sheet: any object with .name and .rows (list of lists of cell values:
           str, int, float, bool, date/datetime/time/timedelta or None),
           and optionally .formats (same shape: Excel number formats).
    helpers: {name: function(value, locale) -> (ok, result)}.
    targets: the target tables the PLAN offered; the program's target
             must be one of them.
    totals: the totals words of all ten languages (helpers.TOTALS).
    Returns a Result. status 'rejected' means: try another candidate."""
    if not totals:
        raise ValueError('totals words are required (helpers.TOTALS)')
    res = Result()
    if prog.refusal:
        res.status = 'refused'
        return res
    started = time.time()
    grid = [list(r) for r in sheet.rows]
    if time_limit is None:
        time_limit = min(MAX_TIME, TIME_LIMIT + PER_ROW * len(grid))
    width = max([len(r) for r in grid] + [0])
    if width > MAX_COLUMNS:
        res.problems.append('too_wide')
        return res
    for r in grid:
        r.extend([None] * (width - len(r)))
    if targets is not None and prog.target not in targets:
        res.problems.append('target_not_offered')
        return res
    if prog.header > len(grid):
        res.problems.append('header_outside_sheet')
        return res
    used = set()
    for _, args in prog.keeps:
        used.add(args[0])
    used.update(prog.unpivot or [])
    for _, expr in prog.outs:
        used |= _letters_in(expr)
    used.discard('section')
    if any(LETTERS.index(l) >= width for l in used):
        res.problems.append('column_outside_sheet')
        return res

    header = grid[prog.header - 1] if prog.header else [None] * width
    header_key = [None if _blank(v) else norm(v) for v in header]

    # 1. data rows: blank rows and repeated header rows are always skipped
    rows = []
    for index in range(prog.header, len(grid)):
        cells = grid[index]
        if all(_blank(v) for v in cells):
            continue
        if prog.header and [None if _blank(v) else norm(v)
                            for v in cells] == header_key:
            continue
        rows.append(_Row(dict(zip(LETTERS, cells)), index + 1))

    # 2. sections: a row with exactly one filled cell is a section title
    if prog.sections:
        current, kept, where = None, [], set()
        for row in rows:
            filled = [(l, v) for l, v in row.cells.items() if not _blank(v)]
            if len(filled) == 1:
                current = (filled[0][1], row.number, filled[0][0])
                res.sections.append(row.number)
                where.add(filled[0][0])
                continue
            row.section = current
            kept.append(row)
        rows = kept
        if len(where) > 1:
            res.problems.append('sections_in_several_columns')
        if len(res.sections) > len(rows):
            res.problems.append('too_many_sections')   # < 1 row each

    # 3. row filters
    def passes(row, name, args):
        if args[0] == 'section':
            v = row.section[0] if row.section else None
        else:
            v = row.cells[args[0]]
        if name == 'filled':
            return not _blank(v)
        if name == 'is_number':
            return not _blank(v) and helpers['amount'](v, locale)[0]
        if name == 'is_date':
            return not _blank(v) and helpers['date'](v, locale)[0]
        if name == 'not_total':
            return not is_total_cell(v, totals)
        if name == 'not_value':
            return _blank(v) or norm(v) != norm(args[1])
        raise TulipError('unknown_predicate', name)

    kept, dropped = [], []
    for row in rows:
        if all(passes(row, n, a) for n, a in prog.keeps):
            kept.append(row)
        else:
            dropped.append(row)

    # 4. unpivot: one row per listed column that has a value
    def expand(row):
        if not prog.unpivot:
            return [row]
        return [_Row(row.cells, row.number, row.section, letter)
                for letter in prog.unpivot if not _blank(row.cells[letter])]

    rows = [r for row in kept for r in expand(row)]

    # 5. evaluate every field on every row
    types = dict((f, t) for f, t, _ in SCHEMAS[prog.target])
    required = [f for f, _, req in SCHEMAS[prog.target] if req]
    fails = dict((f, 0) for f, _ in prog.outs)
    filled_counts = dict((f, 0) for f, _ in prog.outs)
    lookup_seen = {}          # id(dict node) -> set of normalized inputs
    formats = getattr(sheet, 'formats', None) or []

    def value_of(node, row):
        """-> (value, sources, failed). failed = a non-empty cell that a
        helper, lookup or part could not read."""
        name, args = node.func.id, node.args
        if name == 'col':
            letter = args[0].value
            if letter == 'section':
                if not row.section:
                    return None, [], False
                return row.section[0], [(row.section[1], row.section[2])], \
                    False
            if letter == 'name':
                v = header[LETTERS.index(row.pivot)]
                return (None if _blank(v) else v), \
                    [(prog.header, row.pivot)], False
            if letter == 'value':
                return row.cells[row.pivot], [(row.number, row.pivot)], False
            v = row.cells[letter]
            return (None if _blank(v) else v), [(row.number, letter)], False
        if name == 'header_of':
            letter = args[0].value
            v = header[LETTERS.index(letter)]
            return (None if _blank(v) else v), [(prog.header, letter)], False
        if name == 'format_of':
            letter = args[0].value
            i, c = row.number - 1, LETTERS.index(letter)
            v = formats[i][c] if i < len(formats) and formats[i] \
                and c < len(formats[i]) else None
            if v in (None, 'General', '@'):
                v = None
            return v, [(row.number, letter)], False
        if name == 'sheet_title':
            return sheet.name, [('sheet', None)], False
        if name == 'part':
            v, src, failed = value_of(args[0], row)
            if v is None:
                return None, src, failed
            sep = unicodedata.normalize('NFKC', args[1].value)
            index = args[2].value if isinstance(args[2], ast.Constant) \
                else -args[2].operand.value
            text = unicodedata.normalize('NFKC', _as_text(v))
            pieces = [p.strip() for p in text.split(sep)]
            try:
                piece = pieces[index]
            except IndexError:
                return None, src, True
            return (piece or None), src, not piece
        if name == 'join':
            parts, src, failed = [], [], False
            for a in args[1:]:
                v, s, f = value_of(a, row)
                src += s
                failed = failed or f
                if v is not None and _as_text(v).strip():
                    parts.append(_as_text(v).strip())
            return (args[0].value.join(parts) if parts else None), src, \
                failed
        if name == 'first':
            src, failed = [], False
            for a in args:
                v, s, f = value_of(a, row)
                src += s
                failed = failed or f
                if v is not None:
                    return v, s, False
            return None, src, failed
        if name == 'lookup':
            v, src, failed = value_of(args[0], row)
            if v is None:
                return None, src, failed
            table = dict((norm(k.value), val.value)
                         for k, val in zip(args[1].keys, args[1].values))
            key = norm(_as_text(v))
            lookup_seen.setdefault(id(args[1]), set()).add(key)
            if key not in table:
                return None, src, True
            return table[key], src, False
        # a helper
        v, src, failed = value_of(args[0], row)
        if v is None:
            return None, src, failed
        try:
            ok, out = helpers[name](v, locale)
        except Exception:
            ok, out = False, None
            res.warnings.append('helper_raised:' + name)
        if not ok or out is None:
            return None, src, True
        return out, src, False

    def importable(row):
        """Would this (dropped) row have been imported?"""
        for r in expand(row):
            good = True
            for fname, expr in prog.outs:
                if fname in required:
                    value, _, failed = value_of(expr, r)
                    if value is None or failed:
                        good = False
                        break
            if good:
                return True
        return False

    candidates = 0
    totals_imported = []
    for row in rows:
        if time.time() - started > time_limit:
            res.problems.append('timeout')
            return res
        candidates += 1
        record, sources, failed_required = {}, {}, False
        for fname, expr in prog.outs:
            value, src, failed = value_of(expr, row)
            if failed:
                fails[fname] += 1
                if fname in required:
                    failed_required = True
            if value is not None:
                filled_counts[fname] += 1
            record[fname] = value
            sources[fname] = src
        missing = [f for f in required if record.get(f) is None]
        if missing:
            if failed_required:
                res.skipped.append((row.number,
                                    'unreadable:' + ','.join(missing)))
            else:
                res.empty.append(row.number)
            continue
        res.rows.append(record)
        res.sources.append(sources)
        res.row_numbers.append(row.number)
        if is_totals_row(row.cells.values(), totals):
            totals_imported.append(row.number)

    # 6. checks - all plain code, no answer key needed
    allowed = int(TOLERANCE * candidates)
    if not res.rows:
        res.problems.append('no_rows')
    if len(res.skipped) > allowed:
        res.problems.append('required_missing')
    if len(res.empty) > max(2, EMPTY_SHARE * candidates):
        res.problems.append('mostly_empty')
    for fname, count in fails.items():
        base = max(filled_counts[fname] + count, 1)
        if count > int(TOLERANCE * base):
            res.problems.append('parse_failures:' + fname)
        elif count:
            res.warnings.append('parse_failures:%s:%d' % (fname, count))
    bad_drops = [row.number for row in dropped
                 if importable(row)
                 and not is_totals_row(row.cells.values(), totals)]
    if bad_drops:
        res.problems.append('dropped_data_rows:' + ','.join(
            str(n) for n in bad_drops[:5]))
    if totals_imported:
        res.problems.append('totals_row_imported:' + ','.join(
            str(n) for n in totals_imported[:5]))
    for fname, expr in prog.outs:
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Dict):
                seen = lookup_seen.get(id(sub), set())
                unused = [k.value for k in sub.keys
                          if norm(k.value) not in seen]
                if unused:
                    res.problems.append('lookup_key_not_in_source:' +
                                        unused[0][:20])
    if len(res.rows) >= 3 and all(r == res.rows[0] for r in res.rows):
        res.problems.append('degenerate')
    for record in res.rows:
        for fname, value in record.items():
            if value is not None and not _type_ok(types[fname], value):
                res.problems.append('helper_contract:' + fname)
                break
    res.problems += _plausibility(prog.target, res.rows)
    res.dropped = [row.number for row in dropped]
    if res.problems:
        res.status = 'rejected'
    elif res.skipped or res.warnings or res.empty:
        res.status = 'imported_with_warnings'
    else:
        res.status = 'imported'
    return res


def _plausibility(target, rows):
    """Cheap sanity rules. Each allows TOLERANCE of the rows to break it."""
    problems = []
    n = len(rows)
    if not n:
        return problems
    allowed = int(TOLERANCE * n)

    def count(test):
        return sum(1 for r in rows if test(r))

    def get(r, f):
        return r.get(f)

    if target == 'bookings':
        if count(lambda r: get(r, 'end_time') and get(r, 'start_time')
                 and r['end_time'] < r['start_time']) > allowed:
            problems.append('end_before_start')
        if n >= 3 and all(get(r, 'start_time') == '00:00' for r in rows):
            problems.append('midnight_times')
    if target == 'invoice_ledger':
        if count(lambda r: (get(r, 'due_date') and r['due_date'] < r['date'])
                 or (get(r, 'paid_date') and r['paid_date'] < r['date'])) \
                > allowed:
            problems.append('date_order')
        numbers = [norm(r['number']) for r in rows]
        if len(numbers) - len(set(numbers)) > allowed:
            problems.append('duplicate_numbers')
    if target in ('products', 'services'):
        if count(lambda r: get(r, 'price') is not None
                 and r['price'] < 0) > allowed:
            problems.append('negative_price')
    if count(lambda r: get(r, 'duration_min') is not None
             and not 1 <= r['duration_min'] <= 1440) > allowed:
        problems.append('implausible_duration')
    if count(lambda r: get(r, 'vat_rate') is not None
             and not 0 <= r['vat_rate'] <= 0.5) > allowed:
        problems.append('implausible_vat')
    return problems


_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_TIME = re.compile(r'^\d{2}:\d{2}$')


def _type_ok(ftype, v):
    """The contract every helper must keep (section 9 of the spec)."""
    if ftype.startswith('enum:'):
        return v in ENUMS[ftype[5:]]
    return {
        'text': lambda: isinstance(v, str) and v == v.strip() and v != '',
        'amount': lambda: type(v) in (int, float),
        'currency': lambda: isinstance(v, str) and re.match(r'^[A-Z]{3}$', v),
        'boolean': lambda: type(v) is bool,
        'percent': lambda: type(v) in (int, float),
        'integer': lambda: type(v) is int,
        'duration': lambda: type(v) is int and v >= 0,
        'date': lambda: isinstance(v, str) and _DATE.match(v),
        'time': lambda: isinstance(v, str) and _TIME.match(v),
        'hours': lambda: isinstance(v, str) and v != '',
        'weekday': lambda: type(v) is int and 0 <= v <= 6,
        'email': lambda: isinstance(v, str) and '@' in v,
        'phone': lambda: isinstance(v, str) and v.startswith('+'),
    }[ftype]()
