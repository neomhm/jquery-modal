"""
sheets.py - read spreadsheets into plain grids, and write the exact text
preview that Tulip reads.

The preview format is FIXED: the generator, the training data and the
runtime all call preview(), so the model always sees the same shape.

    TARGETS products | services
    LOCALE fr-FR
    SHEET 'Tarifs 2024' | rows 57 | columns A-F
    TYPES A:text B:text C:text D:number E:integer F:text
    FORMATS D:'0.00 €'
    VALUES F:Famille | Pains | Viennoiseries | Pâtisseries
    R1 A:TARIFS BOULANGERIE MARTIN 2024
    R3 A:Réf | B:Désignation | C:Taille | D:Prix TTC | E:Stock | F:Famille
    R4 A:B-12 | B:Baguette tradition | C:250 g | D:1.3 | E:40 | F:Pains
    ...
    ... 33 rows not shown ...
    R57 B:TOTAL | D:412.5

Blank rows are left out (their numbers are simply missing), empty cells
are left out, and every cell shows its column letter - so the model can
point at a column with col('D') without copying its header text.

VALUES lists, for every text column with at most 12 different values
that repeat, those values in order of first appearance - taken from the
WHOLE sheet, not only the rows shown. That is how the model can see every
word a lookup() must map (statuses, yes/no marks, weekdays) even when
some of them only occur in rows the preview does not show.
"""
import csv
import datetime
import io
import pathlib
from collections import Counter
from dataclasses import dataclass

MAX_COLUMNS = 26
LETTERS = tuple(chr(ord('A') + i) for i in range(MAX_COLUMNS))
HEAD = 16          # first non-blank rows shown
TAIL = 4           # last non-blank rows shown
CELL_CHARS = 32    # longer cell texts are cut, with "…"
VALUES_MAX = 12    # a column with at most this many different texts...
VALUE_CHARS = 20   # ...lists them in the VALUES line, each cut to this

# the code page a spreadsheet program of that language uses for CSV,
# tried after UTF-8 and before cp1252
LEGACY = {'ja': 'cp932', 'zh-CN': 'gb18030', 'zh-SG': 'gb18030',
          'zh-TW': 'cp950', 'zh-HK': 'cp950', 'ko': 'cp949',
          'ru': 'cp1251', 'ar': 'cp1256'}


@dataclass
class Sheet:
    name: str
    rows: list                 # list of rows; each a list of cell values
    formats: list = None       # same shape: number formats (xlsx only)
    file: str = ''
    hidden: bool = False


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _trim(rows, formats=None):
    """Drop empty cells at the end of rows and empty rows at the end."""
    out_rows, out_fmts = [], []
    for i, row in enumerate(rows):
        row = list(row)
        fmt = list(formats[i]) if formats else None
        while row and _blank(row[-1]):
            row.pop()
            if fmt:
                fmt.pop()
        out_rows.append([None if _blank(v) else v for v in row])
        out_fmts.append(fmt[:len(row)] if fmt is not None else None)
    while out_rows and not out_rows[-1]:
        out_rows.pop()
        out_fmts.pop()
    return out_rows, (out_fmts if formats else None)


def read_xlsx(path):
    """Every sheet of an .xlsx / .xlsm file, with cell values as
    openpyxl gives them (str, int, float, bool, datetime...) and the
    number format of every cell."""
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = []
    try:
        for ws in book.worksheets:
            if hasattr(ws, 'reset_dimensions'):
                ws.reset_dimensions()     # some files lie about their size
            rows, fmts = [], []
            for row in ws.iter_rows():
                rows.append([c.value for c in row])
                fmts.append([getattr(c, 'number_format', None)
                             for c in row])
            rows, fmts = _trim(rows, fmts)
            sheets.append(Sheet(ws.title, rows, fmts, str(path),
                                ws.sheet_state != 'visible'))
    finally:
        book.close()
    return sheets


def read_csv(path, locale=None):
    """One sheet from a .csv file: any common encoding and delimiter.
    All cells are text (or None when empty). The locale picks the
    legacy code page to try after UTF-8 (cp932 for Japanese, cp1251 for
    Russian...); otherwise cp1252 would silently garble those files."""
    raw = pathlib.Path(path).read_bytes()
    order = ['utf-8-sig', 'utf-8']
    if locale:
        legacy = LEGACY.get(locale) or LEGACY.get(locale.split('-')[0])
        if legacy:
            order.append(legacy)
    order.append('cp1252')
    for encoding in order:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode('latin-1')
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ''
        delimiter = max(',;\t|', key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows, _ = _trim(rows)
    return [Sheet(pathlib.Path(path).stem, rows, None, str(path))]


def load(path, locale=None):
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in ('.xlsx', '.xlsm'):
        return read_xlsx(path)
    if suffix == '.csv':
        return read_csv(path, locale)
    return []


def compact(sheet):
    """Remove columns that are empty in every row, so wide exports with
    many unused columns still fit in 26 letters. Returns the new sheet
    and, for each new column, the ORIGINAL letter(s) - sources are
    reported with the original letters."""
    width = max([len(r) for r in sheet.rows] + [0])
    keep = [c for c in range(width)
            if any(c < len(r) and not _blank(r[c]) for r in sheet.rows)]
    rows = [[r[c] if c < len(r) else None for c in keep]
            for r in sheet.rows]
    fmts = None
    if sheet.formats:
        fmts = [[(f[c] if f and c < len(f) else None) for c in keep]
                for f in sheet.formats]
    rows, fmts = _trim(rows, fmts)
    return (Sheet(sheet.name, rows, fmts, sheet.file, sheet.hidden),
            [column_letter(c) for c in keep])


def column_letter(index):
    """0 -> A, 25 -> Z, 26 -> AA (for reporting original columns)."""
    name = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(ord('A') + rest) + name
    return name


def show(v):
    """How one cell is written in the preview."""
    if isinstance(v, bool):
        text = 'TRUE' if v else 'FALSE'
    elif isinstance(v, datetime.datetime):
        # a date typed in Excel comes back as a datetime at midnight
        text = v.date().isoformat() if v.time() == datetime.time(0) \
            else v.isoformat(sep=' ')
    elif isinstance(v, datetime.timedelta):
        text = str(v)                     # [h]:mm durations: '1:30:00'
    elif isinstance(v, (datetime.date, datetime.time)):
        text = v.isoformat()
    elif isinstance(v, float):
        text = repr(v)
    else:
        s = str(v)
        if '\n' in s:
            text = ' ⏎ '.join(' '.join(p.split()) for p in s.splitlines()
                              if p.strip())
        else:
            text = ' '.join(s.split())
    text = text.replace('|', '¦')
    if len(text) > CELL_CHARS:
        text = text[:CELL_CHARS - 1] + '…'
    return text


def _kind(v):
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, int):
        return 'integer'
    if isinstance(v, float):
        return 'number'
    if isinstance(v, datetime.datetime) or isinstance(v, datetime.date):
        return 'date'
    if isinstance(v, datetime.time):
        return 'time'
    if isinstance(v, datetime.timedelta):
        return 'duration'
    return 'text'


def preview(sheet, targets, locale=None):
    rows = sheet.rows
    width = max([len(r) for r in rows] + [0])
    shown_width = min(width, MAX_COLUMNS)
    lines = ['TARGETS ' + ' | '.join(targets),
             'LOCALE ' + (locale or 'unknown')]
    if width == 0:
        cols = 'none'
    elif width > MAX_COLUMNS:
        cols = 'A-Z and more'
    else:
        cols = 'A-' + LETTERS[width - 1]
    lines.append("SHEET %s | rows %d | columns %s"
                 % (repr(sheet.name), len(rows), cols))
    kinds, formats = [], []
    for c in range(shown_width):
        values = [r[c] for r in rows if c < len(r) and not _blank(r[c])]
        if not values:
            kinds.append('%s:empty' % LETTERS[c])
            continue
        top, count = Counter(_kind(v) for v in values).most_common(1)[0]
        kinds.append('%s:%s' % (LETTERS[c],
                                top if count >= 0.6 * len(values)
                                else 'mixed'))
        if sheet.formats:
            fmts = [sheet.formats[i][c] for i, r in enumerate(rows)
                    if c < len(r) and isinstance(r[c], (int, float))
                    and not isinstance(r[c], bool)
                    and sheet.formats[i] and c < len(sheet.formats[i])
                    and sheet.formats[i][c]
                    and sheet.formats[i][c] != 'General']
            if fmts:
                fmt = Counter(fmts).most_common(1)[0][0]
                formats.append('%s:%s' % (LETTERS[c], repr(fmt)))
    lines.append('TYPES ' + ' '.join(kinds))
    if formats:
        lines.append('FORMATS ' + ' '.join(formats))
    for c in range(shown_width):
        texts = [show(r[c]) for r in rows if c < len(r)
                 and isinstance(r[c], str) and not _blank(r[c])]
        distinct = list(dict.fromkeys(texts))
        if 2 <= len(distinct) <= VALUES_MAX and len(distinct) < len(texts):
            cut = [t if len(t) <= VALUE_CHARS else t[:VALUE_CHARS - 1] + '…'
                   for t in distinct]
            lines.append('VALUES %s:%s' % (LETTERS[c], ' | '.join(cut)))
    numbered = [(i + 1, r) for i, r in enumerate(rows)
                if any(not _blank(v) for v in r)]
    if len(numbered) > HEAD + TAIL:
        hidden = len(numbered) - HEAD - TAIL
        chosen = numbered[:HEAD] + [None] + numbered[-TAIL:]
    else:
        hidden, chosen = 0, numbered
    for item in chosen:
        if item is None:
            lines.append('... %d rows not shown ...' % hidden)
            continue
        number, row = item
        cells = ['%s:%s' % (LETTERS[c], show(v))
                 for c, v in enumerate(row[:shown_width]) if not _blank(v)]
        lines.append('R%d %s' % (number, ' | '.join(cells)))
    return '\n'.join(lines)
