"""
gen/pdfwrite.py - write a generated sheet as a PDF table (Tulip 1.1,
item G), in pure Python: one text run per cell at its column's position,
the way report writers and accounting programs print price lists and
invoices. Any script: the text is written with a Type0 font (Identity-H)
and a ToUnicode map, so a PDF reader gets the exact characters back. The
font is not embedded (the PDF is read, not printed), so no font file is
needed.

    write_pdf(path, rows, right=(3,), size=9, landscape=False,
              repeat_header=None)

rows: the cells as texts (None for an empty cell), as write_csv writes
them; right: the columns written flush right (numbers); repeat_header:
the index of the header row, written again at the top of every page.
A fully empty row is an empty line, as on paper.
"""
import unicodedata
import zlib

A4 = (595.0, 842.0)
MARGIN = 36.0


def char_width(ch):
    """The advance of one character, in em (an estimate the reader uses
    as well: wide East Asian characters 1, marks 0, others 0.5)."""
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn",
                                                                 "Me",
                                                                 "Cf"):
        return 0.0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 1.0
    return 0.5


def text_width(text, size):
    return sum(char_width(ch) for ch in text) * size


class _Font:
    """Unicode characters -> 2-byte glyph ids, and the ToUnicode map."""

    def __init__(self):
        self.cids = {}

    def encode(self, text):
        out = []
        for ch in text:
            if ch not in self.cids:
                self.cids[ch] = len(self.cids) + 1
            out.append("%04X" % self.cids[ch])
        return "<" + "".join(out) + ">"

    def to_unicode(self):
        pairs = sorted((cid, ch) for ch, cid in self.cids.items())
        lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin",
                 "begincmap", "/CIDSystemInfo << /Registry (Adobe) "
                 "/Ordering (UCS) /Supplement 0 >> def",
                 "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
                 "1 begincodespacerange", "<0000> <FFFF>",
                 "endcodespacerange"]
        for k in range(0, len(pairs), 100):
            chunk = pairs[k:k + 100]
            lines.append("%d beginbfchar" % len(chunk))
            for cid, ch in chunk:
                lines.append("<%04X> <%s>" % (cid, ch.encode(
                    "utf-16-be").hex().upper()))
            lines.append("endbfchar")
        lines += ["endcmap", "CMapName currentdict /CMap defineresource "
                  "pop", "end", "end"]
        return "\n".join(lines).encode("ascii")

    def widths(self):
        """/W: the advance of every glyph, in 1/1000 em."""
        pairs = sorted((cid, ch) for ch, cid in self.cids.items())
        return "[" + " ".join("%d [%d]" % (cid, int(1000 * char_width(ch)))
                              for cid, ch in pairs) + "]"


def layout(rows, size, right=(), page=A4, landscape=False):
    """-> (page width, page height, [x of each column's left edge],
    [width of each column])."""
    width = max([len(r) for r in rows] + [1])
    col_w = [0.0] * width
    for r in rows:
        if sum(1 for v in r if v not in (None, "")) < 2:
            continue                   # a title or note line spans columns
        for j, v in enumerate(r):
            if v not in (None, ""):
                col_w[j] = max(col_w[j], text_width(str(v), size))
    gap = 1.6 * size
    xs, x = [], MARGIN
    for w in col_w:
        xs.append(x)
        x += w + (gap if w else 0.0)
    pw, ph = (page[1], page[0]) if landscape else page
    pw = max(pw, x + MARGIN)
    return pw, ph, xs, col_w


def write_pdf(path, rows, right=(), size=9.0, landscape=False,
              repeat_header=None, leading=1.45):
    import pdftable
    # right-to-left text is stored in visual order, as PDF writers store
    # it (the reader turns it back into reading order)
    rows = [["" if v is None else pdftable.logical(str(v)) for v in r]
            for r in rows]
    pw, ph, xs, col_w = layout(rows, size, right, A4, landscape)
    font = _Font()
    line_h = size * leading
    per_page = max(5, int((ph - 2 * MARGIN) // line_h))
    pages, current = [], []
    header = rows[repeat_header] if repeat_header is not None and \
        repeat_header < len(rows) else None
    for i, r in enumerate(rows):
        if len(current) >= per_page:
            pages.append(current)
            current = [header] if header is not None and i > \
                repeat_header else []
        current.append(r)
    if current or not pages:
        pages.append(current)
    streams = []
    for lines in pages:
        ops = []
        y = ph - MARGIN - size
        for r in lines:
            for j, v in enumerate(r):
                if not v:
                    continue
                x = xs[j] if j < len(xs) else MARGIN
                if j in right and j < len(col_w):
                    x = xs[j] + col_w[j] - text_width(v, size)
                ops.append("BT /F1 %.2f Tf 1 0 0 1 %.2f %.2f Tm %s Tj ET"
                           % (size, x, y, font.encode(v)))
            y -= line_h
        streams.append("\n".join(ops).encode("ascii"))
    _write(path, streams, font, pw, ph)


def _write(path, streams, font, pw, ph):
    """The PDF objects: catalog, pages, one page and content stream per
    page, the Type0 font, its CIDFont and its ToUnicode map."""
    n_pages = len(streams)
    # object numbers: 1 catalog, 2 pages, 3 font, 4 cid font, 5 tounicode,
    # then page k: 6 + 2k, its content 7 + 2k
    objs = {}
    kids = " ".join("%d 0 R" % (6 + 2 * k) for k in range(n_pages))
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (
        kids, n_pages)).encode("ascii")
    objs[3] = (b"<< /Type /Font /Subtype /Type0 /BaseFont /NotoSans "
               b"/Encoding /Identity-H /DescendantFonts [4 0 R] "
               b"/ToUnicode 5 0 R >>")
    objs[4] = ("<< /Type /Font /Subtype /CIDFontType2 /BaseFont /NotoSans "
               "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
               "/Supplement 0 >> /DW 500 /W %s /CIDToGIDMap /Identity >>"
               % font.widths()).encode("ascii")
    cmap = zlib.compress(font.to_unicode())
    objs[5] = (b"<< /Length %d /Filter /FlateDecode >>\nstream\n" %
               len(cmap)) + cmap + b"\nendstream"
    for k, content in enumerate(streams):
        data = zlib.compress(content)
        objs[6 + 2 * k] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.0f %.0f] "
            "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (pw, ph, 7 + 2 * k)).encode("ascii")
        objs[7 + 2 * k] = (b"<< /Length %d /Filter /FlateDecode >>\n"
                           b"stream\n" % len(data)) + data + \
            b"\nendstream"
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + objs[num] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for num in range(1, size):
        out += b"%010d 00000 n \n" % offsets[num]
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (size, xref))
    with open(path, "wb") as f:
        f.write(bytes(out))
