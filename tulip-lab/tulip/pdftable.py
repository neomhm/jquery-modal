"""
pdftable.py - the table of a PDF, rebuilt from where its text is written
(Tulip 1.1, item G). pypdf (vendor/, pure Python, BSD-3-Clause) gives each
piece of text and its position; this file puts the pieces back into rows
and columns: a sheet of text cells, like a CSV file, that Tulip reads as
it reads any sheet.

    read_pdf(path) -> [Sheet]

  1. lines: pieces at the same height (within half a character) are one
     line; a gap of about two lines or more is an empty row, as on paper;
  2. cells: pieces of a line closer than about one character are one
     cell (a word, a sentence); pieces written at the very same place are
     joined in reading order - right to left for Arabic, whose PDFs store
     text in visual order;
  3. columns: the horizontal extents of the cells of every line with two
     cells or more, merged where they overlap, are the columns (numbers
     written flush right overlap by their right edge, texts by their
     left); a title or note line of one cell goes to the column where it
     starts.
Pages with the same columns are one sheet (a table that goes on over
pages; a repeated header row is left to Tulip, which skips it); a page
with other columns starts a new sheet.

A PDF without text - scanned pages - raises ScannedPDF: there is no OCR.
"""
import pathlib
import sys
import unicodedata

import sheets

GAP_CELL = 1.6       # x gap between pieces of one cell, in spaces
LINE_TOL = 0.5       # y difference within one line, in characters
BLANK_GAP = 1.7      # a line gap this many median gaps or more: empty rows


class ScannedPDF(Exception):
    """A PDF whose pages carry no text: scanned images need OCR, which
    Tulip does not do."""


def _pypdf():
    """pypdf without the optional crypto packages: a broken system
    'cryptography' (a Rust panic, not an ImportError) must not stop it,
    and an unencrypted PDF needs no crypto."""
    if "pypdf" in sys.modules:
        return sys.modules["pypdf"]

    class Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("cryptography", "Crypto"):
                raise ImportError("not used by Tulip")
            return None
    blocker = Block()
    sys.meta_path.insert(0, blocker)
    try:
        import pypdf
    finally:
        sys.meta_path.remove(blocker)
    return pypdf


def _width(text, size):
    from gen.pdfwrite import text_width
    return text_width(text, size)


def _rtl(text):
    return any(unicodedata.bidirectional(ch) in ("R", "AL") for ch in text)


def logical(text):
    """A right-to-left text as PDFs store it (visual order: the glyphs
    left to right as they are drawn) -> reading order. The runs of Arabic
    or Hebrew letters are reversed, and so is their order, while numbers
    and Latin words inside keep theirs. The same function turns reading
    order into visual order (the writer uses it)."""
    if not _rtl(text):
        return text

    def kind(ch):
        b = unicodedata.bidirectional(ch)
        return "R" if b in ("R", "AL") else "L" if b in (
            "L", "EN", "AN", "ES", "ET", "CS") else "N"
    runs = []
    for ch in text:
        k = kind(ch)
        if runs and (runs[-1][0] == k or (k == "N" and runs[-1][0] == "R")):
            runs[-1][1].append(ch)
        elif k == "N" and runs:
            runs.append(["N", [ch]])
        else:
            runs.append([k, [ch]])
    out = []
    for k, chars in reversed(runs):
        out.append("".join(reversed(chars)) if k in ("R", "N") else
                   "".join(chars))
    return "".join(out).strip()


def _layout_pieces(page):
    """[(x0, x1, y, size, space, text)] of one page from pypdf's layout
    machinery: every text show operation (Tj, each string of a TJ) with
    its start and its end - the end from the font's own widths."""
    from pypdf._text_extraction._layout_mode._fixed_width_page import \
        recurse_to_target_op, resolve_font
    from pypdf._text_extraction._layout_mode._text_state_manager import \
        TextStateManager
    from pypdf.generic import ContentStream
    contents = page.get("/Contents")
    if contents is None:
        return []
    fonts = page._layout_mode_fonts()
    ops = iter(ContentStream(contents.get_object(), page.pdf,
                             "bytes").operations)
    state, tjs = TextStateManager(), []
    for operands, op in ops:
        if op in (b"BT", b"q"):
            _, found = recurse_to_target_op(
                ops, state, b"ET" if op == b"BT" else b"Q", fonts, True)
            tjs.extend(found)
        elif op == b"Tf":
            state.set_font(resolve_font(fonts, operands[0]), operands[1])
        else:
            state.set_state_param(op, operands)
    out = []
    for tj in tjs:
        text = " ".join((tj.text or "").split())
        if not text or tj.rotated or not tj.font.interpretable:
            continue
        size = abs(tj.font_height) or abs(tj.font_size) or 10.0
        # a space is never wider than about a third of the size (pypdf
        # gives some fonts a whole em)
        space = min(abs(tj.space_tx) or 0.3 * size, 0.35 * size)
        x0, x1 = sorted((tj.tx, tj.displaced_tx))
        out.append((x0, x1, tj.ty, size, space, text))
    return out


def _visitor_pieces(page):
    """The same from pypdf's plain extraction (text inside form objects,
    which the layout machinery does not enter), the ends estimated."""
    found = []

    def visit(text, cm, tm, font, size):
        if not text or not text.strip():
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        scale = (tm[0] ** 2 + tm[1] ** 2) ** 0.5 * \
            (cm[0] ** 2 + cm[1] ** 2) ** 0.5
        size = (size or 10.0) * (scale or 1.0)
        text = " ".join(text.split())
        found.append((x, x + _width(text, size), y, size, 0.3 * size, text))
    page.extract_text(visitor_text=visit)
    return found


def pieces(path):
    """-> [[(x0, x1, y, size, space, text)] per page]."""
    pypdf = _pypdf()
    reader = pypdf.PdfReader(str(path))
    if reader.is_encrypted:
        reader.decrypt("")
    pages = []
    for page in reader.pages:
        try:
            found = _layout_pieces(page)
        except Exception:
            found = []
        if not found:
            found = _visitor_pieces(page)
        pages.append(found)
    return pages


def _lines(page):
    """Pieces -> lines (top to bottom), each a list of pieces left to
    right, and the height of each line."""
    order = sorted(page, key=lambda p: (-p[2], p[0]))
    lines, ys = [], []
    for p in order:
        if lines and abs(ys[-1] - p[2]) <= LINE_TOL * p[3]:
            lines[-1].append(p)
        else:
            lines.append([p])
            ys.append(p[2])
    return [sorted(line) for line in lines], ys


def _cells(line):
    """The pieces of one line -> cells [(start x, end x, text)]: pieces
    closer than GAP_CELL spaces are one cell."""
    cells = []
    for x0, x1, y, size, space, text in line:
        if cells and x0 - cells[-1][1] <= GAP_CELL * space:
            s, e, t = cells[-1]
            joint = "" if x0 - e < 0.25 * space else " "
            cells[-1] = (s, max(e, x1), t + joint + text)
        else:
            cells.append((x0, x1, text))
    return [(s, e, logical(t)) for s, e, t in cells]


def _bands(rows_of_cells, size):
    """The columns: the extents of the cells of lines with two cells or
    more, merged where they overlap."""
    spans = sorted((s, e) for cells in rows_of_cells if len(cells) > 1
                   for s, e, _ in cells)
    bands = []
    for s, e in spans:
        if bands and s <= bands[-1][1] + 0.2 * size:
            bands[-1][1] = max(bands[-1][1], e)
        else:
            bands.append([s, e])
    return bands


def _column(cell, bands):
    """The column a cell starts in (a title or a note that runs on past
    its column stays where it starts); else the nearest."""
    s, e, _ = cell
    for k, (bs, be) in enumerate(bands):
        if bs - 1.0 <= s <= be:
            return k
    return min(range(len(bands)),
               key=lambda k: min(abs(bands[k][0] - s), abs(bands[k][1] - e)))


def _page(page):
    """One page -> (cells of each line, the line heights, the font size)."""
    lines, ys = _lines(page)
    size = sorted(p[3] for p in page)[len(page) // 2]
    return [_cells(line) for line in lines], ys, size


def _grid(cells, ys, size, bands):
    """The lines of one page in the given columns -> rows of texts; a
    gap of about two lines or more gives empty rows."""
    gaps = sorted(ys[i] - ys[i + 1] for i in range(len(ys) - 1))
    step = gaps[len(gaps) // 2] if gaps else size * 1.4
    rows = []
    for i, line_cells in enumerate(cells):
        if i and step > 0:
            gap = ys[i - 1] - ys[i]
            if gap >= BLANK_GAP * step:
                rows += [[] for _ in range(int(round(gap / step)) - 1)]
        row = [None] * len(bands)
        for cell in line_cells:
            k = _column(cell, bands)
            row[k] = cell[2] if row[k] is None else row[k] + " " + cell[2]
        rows.append(row)
    return rows


def _fits(group_bands, bands, size):
    """A page goes on with the table when each of its columns lies in
    one column of the table so far (a last page may fill fewer)."""
    if not bands:
        return True
    for s, e in bands:
        hits = [k for k, (gs, ge) in enumerate(group_bands)
                if s <= ge + size and e >= gs - size]
        if len(hits) != 1:
            return False
    return True


def _union(a, b, size):
    spans = sorted([list(x) for x in a] + [list(x) for x in b])
    out = []
    for s, e in spans:
        if out and s <= out[-1][1] + 0.2 * size:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def read_pdf(path):
    """The tables of a PDF as sheets of text cells (see the top)."""
    pages = pieces(path)
    if not any(pages):
        raise ScannedPDF("%s has no text (scanned pages need OCR)"
                         % pathlib.Path(path).name)
    stem = pathlib.Path(path).stem
    groups = []          # {"first", "last", "pages": [(cells, ys, size)],
    #                       "bands"}
    for n, page in enumerate(pages, 1):
        if not page:
            continue
        cells, ys, size = _page(page)
        bands = _bands(cells, size)
        if groups and _fits(groups[-1]["bands"], bands, size):
            g = groups[-1]
            g["last"] = n
            g["pages"].append((cells, ys, size))
            g["bands"] = _union(g["bands"], bands, size)
        else:
            groups.append({"first": n, "last": n,
                           "pages": [(cells, ys, size)],
                           "bands": bands or [[min(p[0] for p in page),
                                               max(p[1] for p in page)]]})
    out = []
    for g in groups:
        rows = []
        for cells, ys, size in g["pages"]:
            rows += _grid(cells, ys, size, g["bands"])
        name = stem if len(groups) == 1 else "%s p%d%s" % (
            stem, g["first"], "-%d" % g["last"] if g["last"] > g["first"]
            else "")
        rows, _ = sheets._trim(rows)
        out.append(sheets.Sheet(name, rows, None, str(path)))
    return out
