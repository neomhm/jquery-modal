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
        fmt = list(formats[i] or []) if formats else None
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


def csv_delimiter(sample):
    """The delimiter that splits the most lines into the same number (2 or
    more) of cells; on a tie ; then tab, | and , last. csv.Sniffer took
    the decimal commas of "BAGUETTE 0,25 kg;1,20" for the delimiter."""
    lines = [x for x in sample.splitlines() if x.strip()][:60]
    best, best_score = ',', -1
    for d in ';\t|,':
        try:
            counts = [len(r) for r in csv.reader(lines, delimiter=d)]
        except csv.Error:
            continue
        wide = [c for c in counts if c > 1]
        if not wide:
            continue
        mode = max(set(wide), key=lambda c: (wide.count(c), c))
        score = wide.count(mode)
        if score > best_score:
            best, best_score = d, score
    return best


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
    delimiter = csv_delimiter(text[:4096])
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows, _ = _trim(rows)
    return [Sheet(pathlib.Path(path).stem, rows, None, str(path))]


def _number(v):
    """A stored number as openpyxl gives it: a whole float is an int."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def read_xls(path):
    """Every sheet of an old Excel .xls file (xlrd, vendor/), with the
    same kinds of values and number formats as read_xlsx()."""
    import xlrd
    book = xlrd.open_workbook(str(path), formatting_info=True,
                              on_demand=True)
    out = []
    try:
        for i in range(book.nsheets):
            ws = book.sheet_by_index(i)
            rows, fmts = [], []
            for r in range(ws.nrows):
                row, fmt = [], []
                for c in range(ws.ncols):
                    cell = ws.cell(r, c)
                    kind, v = cell.ctype, cell.value
                    try:
                        xf = book.xf_list[cell.xf_index]
                        f = book.format_map[xf.format_key].format_str
                    except (IndexError, KeyError, TypeError):
                        f = None
                    if kind == xlrd.XL_CELL_DATE and f and \
                            any(u in f.lower() for u in ('[h', '[m', '[s')):
                        v = datetime.timedelta(days=v)   # a duration
                    elif kind == xlrd.XL_CELL_DATE:
                        if v < 1:                  # a time of day
                            t = xlrd.xldate_as_datetime(v, book.datemode)
                            v = datetime.time(t.hour, t.minute, t.second)
                        else:
                            v = xlrd.xldate_as_datetime(v, book.datemode)
                    elif kind == xlrd.XL_CELL_NUMBER:
                        v = _number(v)
                    elif kind == xlrd.XL_CELL_BOOLEAN:
                        v = bool(v)
                    elif kind in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK,
                                  xlrd.XL_CELL_ERROR):
                        v = None
                    row.append(v)
                    fmt.append(f if f and f != 'General' else
                               ('General' if v is not None else None))
                rows.append(row)
                fmts.append(fmt)
            rows, fmts = _trim(rows, fmts)
            out.append(Sheet(ws.name, rows, fmts, str(path),
                             ws.visibility != 0))
            book.unload_sheet(i)
    finally:
        book.release_resources()
    return out


ODS = {'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
       'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
       'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
       'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0'}
ODS_MAX_ROWS = 100000      # a repeated empty row is never expanded past this


def _ods_text(el):
    """The text of an ODS cell: its paragraphs, spaces (text:s), tabs and
    line breaks."""
    t, s = '{%s}' % ODS['text'], []

    def walk(node):
        if node.text:
            s.append(node.text)
        for child in node:
            if child.tag == t + 's':
                s.append(' ' * int(child.get(t + 'c', '1')))
            elif child.tag == t + 'tab':
                s.append('\t')
            elif child.tag == t + 'line-break':
                s.append('\n')
            else:
                walk(child)
            if child.tail:
                s.append(child.tail)
    paragraphs = []
    for p in el.iter(t + 'p'):
        s.clear()
        walk(p)
        paragraphs.append(''.join(s))
    return '\n'.join(paragraphs)


def _ods_value(cell):
    """-> (value, number format) of one table:table-cell."""
    o = '{%s}' % ODS['office']
    kind = cell.get(o + 'value-type')
    text = _ods_text(cell)
    if kind in ('float', 'percentage', 'currency'):
        v = _number(float(cell.get(o + 'value')))
        if kind == 'percentage':
            return v, '0.00%'
        if kind == 'currency':
            return v, '#,##0.00 [$%s]' % (cell.get(o + 'currency') or '')
        return v, 'General'
    if kind == 'date':
        raw = cell.get(o + 'date-value')
        v = datetime.datetime.fromisoformat(raw)
        return v, 'yyyy-mm-dd' if len(raw) <= 10 else 'yyyy-mm-dd hh:mm'
    if kind == 'time':
        raw = cell.get(o + 'time-value') or ''
        import re
        m = re.fullmatch(r'PT(\d+)H(\d+)M(\d+)(?:\.\d+)?S', raw)
        if m:
            h, mi, sec = (int(x) for x in m.groups())
            if h < 24:
                return datetime.time(h, mi, sec), 'hh:mm'
            return datetime.timedelta(hours=h, minutes=mi,
                                      seconds=sec), '[h]:mm'
        return text or None, None
    if kind == 'boolean':
        return cell.get(o + 'boolean-value') == 'true', 'General'
    return (text if text != '' else None), None


def read_ods(path):
    """Every sheet of a LibreOffice .ods file (a zip of XML, read with the
    standard library). Merged-away cells are empty; repeated empty rows
    and columns are not expanded past the last filled one."""
    import zipfile
    import xml.etree.ElementTree as ET
    tb, st = '{%s}' % ODS['table'], '{%s}' % ODS['style']
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('content.xml'))
    hidden_styles = set()
    for style in root.iter(st + 'style'):
        props = style.find(st + 'table-properties')
        if props is not None and props.get(tb + 'display') == 'false':
            hidden_styles.add(style.get(st + 'name'))
    out = []
    for table in root.iter(tb + 'table'):
        rows, fmts, pending_rows = [], [], 0
        for row in table.iter(tb + 'table-row'):
            cells, formats, pending = [], [], 0
            for cell in row:
                if cell.tag not in (tb + 'table-cell',
                                    tb + 'covered-table-cell'):
                    continue
                repeat = int(cell.get(tb + 'number-columns-repeated', '1'))
                value, fmt = (None, None) if cell.tag.endswith(
                    'covered-table-cell') else _ods_value(cell)
                if value is None:
                    pending += repeat
                    continue
                cells += [None] * pending
                formats += [None] * pending
                pending = 0
                cells += [value] * min(repeat, MAX_COLUMNS * 40)
                formats += [fmt] * min(repeat, MAX_COLUMNS * 40)
            repeat = int(row.get(tb + 'number-rows-repeated', '1'))
            if not cells:
                pending_rows += repeat
                continue
            if len(rows) + pending_rows >= ODS_MAX_ROWS:
                break
            rows += [[] for _ in range(pending_rows)]
            fmts += [[] for _ in range(pending_rows)]
            pending_rows = 0
            for _ in range(min(repeat, ODS_MAX_ROWS - len(rows))):
                rows.append(list(cells))
                fmts.append(list(formats))
        rows, fmts = _trim(rows, fmts)
        out.append(Sheet(table.get(tb + 'name') or 'Sheet%d' % (len(out) + 1),
                         rows, fmts, str(path),
                         table.get(tb + 'style-name') in hidden_styles))
    return out


READABLE = ('.xlsx', '.xlsm', '.csv', '.xls', '.ods', '.pdf')


def load(path, locale=None):
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in ('.xlsx', '.xlsm'):
        return read_xlsx(path)
    if suffix == '.csv':
        return read_csv(path, locale)
    if suffix == '.xls':
        return read_xls(path)
    if suffix == '.ods':
        return read_ods(path)
    if suffix == '.pdf':
        import pdftable
        return pdftable.read_pdf(path)
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
