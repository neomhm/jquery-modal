"""
render.py - turns a Doc into the chunks ingest.py would store for it
(section 10.5), through the annotated chunker of Appendix B.

    pdf   per page: each table as a 'table' chunk, then the page text
          (which ALSO holds the table rows, as lines of cells joined by
          spaces) through split_text
    docx  every paragraph (headings in UPPER CASE after a blank line)
          through split_text as page 1, then each table as a chunk
    xlsx  per sheet: [title] + header + groups of 25 rows
    csv   header + groups of 25 rows, no title line
    txt / md  split_text on the whole file

Returns a list of pieces: (page, kind, text, spans, cut, traps) where
spans are (start, end, label) and truth is looked up afterwards.
"""
import chunker
from gen import noise as NZ
from gen.doc import Blank, Columns, Heading, Para, Table
from gen.text import AText

COND = "REVENUE_YEAR?"     # a header-line year, kept only before revenue


# ---------------------------------------------------------------------
#  small helpers
# ---------------------------------------------------------------------
def _spans_for_chunker(at, cond_ok=False):
    """AText spans -> [(s, e, label)] plus trap pseudo-spans."""
    out = []
    for sp in at.spans:
        label = sp["label"]
        if sp.get("cond") and not cond_ok:
            label = COND
        out.append((sp["s"], sp["e"], label))
    for tr in at.traps:
        if tr["e"] > tr["s"]:
            out.append((tr["s"], tr["e"], "TRAP:" + tr["trap"]))
    return out


def _split_labels(spans):
    """Separates real spans from trap marks; resolves conditional
    header-line years (kept only when a REVENUE follows in the chunk)."""
    real = [s for s in spans if not s[2].startswith("TRAP:")]
    traps = sorted({s[2][5:] for s in spans if s[2].startswith("TRAP:")})
    out = []
    for s, e, label in real:
        if label == COND:
            if any(l2 == "REVENUE" and s2 > s for s2, _, l2 in real):
                out.append((s, e, "REVENUE_YEAR"))
            continue
        out.append((s, e, label))
    return sorted(set(out)), traps


def row_text(cells, rng, sep=None):
    """A table row as pdfplumber prints it: cells joined by spaces."""
    parts = [c.at for c in cells if c.at.text.strip()]
    return AText.join(parts, sep or " ")


def table_as_lines(table, rng, style="pdf"):
    """A table as lines of text (PDF page text, txt, md)."""
    lines = []
    header = table.rows[0] if table.rows else []
    for r, row in enumerate(table.rows):
        if style == "md":
            cells = [c.at for c in row]
            line = AText("| ")
            line.add(AText.join(cells, " | "))
            line.add(" |")
            lines.append(line)
            if r == 0:
                lines.append(AText("|" + "|".join("---" for _ in row) + "|"))
        elif style == "txt":
            line = AText()
            for k, c in enumerate(row):
                if k:
                    line.add(rng.choice(["\t", "   ", "    "]))
                line.add(c.at)
            lines.append(line)
        else:
            lines.append(row_text(row, rng, " " if rng.random() < 0.85
                                  else "  "))
    for line in lines:
        # header cells carry conditional years: they become COND in text
        for sp in line.spans:
            if sp.get("cond"):
                sp["label"] = "REVENUE_YEAR"
    return [ln for ln in lines if ln.text.strip()]


def cells_for_chunker(table, raw=False, rng=None):
    rows, spans = [], {}
    for r, row in enumerate(table.rows):
        out_row = []
        for c, cell in enumerate(row):
            at = cell.raw if (raw and cell.raw is not None and
                              (rng is None or rng.random() < 0.92)) \
                else cell.at
            out_row.append(at.text)
            if at.spans or at.traps:
                spans[(r, c)] = [(sp["s"], sp["e"], sp["label"])
                                 for sp in at.spans] + \
                    [(t["s"], t["e"], "TRAP:" + t["trap"])
                     for t in at.traps if t["e"] > t["s"]]
        rows.append(out_row)
    return rows, spans


def table_chunk(table):
    rows, cell_spans = cells_for_chunker(table)
    text, spans = chunker.table_to_text_annotated(rows, cell_spans)
    if text is None:
        return None
    real, traps = _split_labels(spans)
    return text, real, traps


# ---------------------------------------------------------------------
#  page text
# ---------------------------------------------------------------------
def page_text(blocks, rng, fmt, ctx, doc):
    """The text of one page (PDF), or of the whole file (txt / md)."""
    parts = []
    lang = ctx.lang
    wrap = fmt == "pdf" and rng.random() < 0.4
    for block in blocks:
        if isinstance(block, Blank):
            if fmt != "pdf":
                parts.append(AText(""))
            continue
        if isinstance(block, Heading):
            at = block.at.copy()
            if fmt == "md":
                at = AText("#" * min(block.level + 1, 3) + " ").add(at)
            elif fmt == "txt" and rng.random() < 0.3:
                at = _upper(at)
            if fmt != "pdf" and parts:
                parts.append(AText(""))
            parts.append(at)
            continue
        if isinstance(block, Para):
            at = block.at.copy()
            if block.prose and wrap:
                NZ.hard_wrap(at, rng, lang)
            parts.append(at)
            if fmt != "pdf" and block.prose:
                parts.append(AText(""))
            continue
        if isinstance(block, Table):
            style = "pdf" if fmt == "pdf" else fmt
            lines = table_as_lines(block, rng, style)
            if fmt != "pdf":
                parts.append(AText(""))
            parts.extend(lines)
            if fmt != "pdf":
                parts.append(AText(""))
            continue
        if isinstance(block, Columns):
            if fmt == "pdf" and doc.meta.get("side_by_side"):
                parts.append(NZ.side_by_side(block.left, block.right, rng))
            else:
                parts.append(block.left.copy())
                if fmt != "pdf":
                    parts.append(AText(""))
                parts.append(block.right.copy())
            continue
    out = AText()
    for k, part in enumerate(parts):
        if k:
            out.add("\n")
        out.add(part)
    # collapse runs of more than one blank line (never in PDF anyway)
    return out


def _upper(at):
    return at.map_chars(lambda ch: ch.upper() if len(ch.upper()) == 1
                        else ch)


# ---------------------------------------------------------------------
#  the formats
# ---------------------------------------------------------------------
def render_pdf(doc, rng, ctx, sources):
    pieces = []
    n_pages = len(doc.pages)
    header_footer = n_pages > 1 and rng.random() < 0.5
    for number, blocks in enumerate(doc.pages, start=1):
        for block in blocks:
            if isinstance(block, Table):
                made = table_chunk(block)
                sources.append(("table", cells_for_chunker(block)[0]))
                if made:
                    text, spans, traps = made
                    pieces.append((number, "table", text, spans, [], traps))
        at = page_text(blocks, rng, "pdf", ctx, doc)
        if header_footer:
            foot = doc.meta.get("footer_line")
            page_line = doc.meta.get("page_line")
            extra = AText()
            if foot is not None:
                extra.add("\n").add(foot.copy())
            if page_line:
                extra.add("\n").add(page_line(number, n_pages))
            at.add(extra)
        sources.append(("split", at.text))
        spans = _spans_for_chunker(at)
        for chunk, kept, cut in chunker.split_text_annotated(at.text, spans):
            real, traps = _split_labels(kept)
            pieces.append((number, "text", chunk, real, cut, traps))
    return pieces


def render_docx(doc, rng, ctx, sources):
    lines = []
    tables = []
    for block in doc.blocks():
        if isinstance(block, Table):
            tables.append(block)
        elif isinstance(block, Columns):
            if rng.random() < 0.5:
                tables.append(Table([[block.left, block.right]]))
            else:
                lines.append(block.left.copy())
                lines.append(block.right.copy())
        elif isinstance(block, Heading):
            lines.append(AText(""))
            lines.append(_upper(block.at.copy()))
        elif isinstance(block, Blank):
            lines.append(AText(""))
        elif isinstance(block, Para):
            lines.append(block.at.copy())
            if block.prose and rng.random() < 0.5:
                lines.append(AText(""))
    text = AText()
    for k, line in enumerate(lines):
        if k:
            text.add("\n")
        text.add(line)
    pieces = []
    sources.append(("split", text.text))
    spans = _spans_for_chunker(text)
    for chunk, kept, cut in chunker.split_text_annotated(text.text, spans):
        real, traps = _split_labels(kept)
        pieces.append((1, "text", chunk, real, cut, traps))
    for table in tables:
        sources.append(("table", cells_for_chunker(table)[0]))
        made = table_chunk(table)
        if made:
            t, s, tr = made
            pieces.append((1, "table", t, s, [], tr))
    return pieces


def sheet_rows(doc, rng, ctx):
    """The grid of an Excel sheet made from the document's blocks."""
    rows = []
    raw_doc = rng.random() < 0.6
    for block in doc.blocks():
        if isinstance(block, Table):
            for row in block.rows:
                rows.append([(c.raw if raw_doc and c.raw is not None and
                              rng.random() < 0.92 else c.at) for c in row])
        elif isinstance(block, Heading):
            rows.append([block.at])
        elif isinstance(block, Para):
            for line in block.at.lines():
                if not line.text.strip():
                    continue
                cut = _kv_split(line)
                rows.append(cut if cut and rng.random() < 0.6 else [line])
        elif isinstance(block, Columns):
            left, right = block.left.lines(), block.right.lines()
            for i in range(max(len(left), len(right))):
                a = left[i] if i < len(left) else AText()
                b = right[i] if i < len(right) else AText()
                rows.append([a, AText(""), b])
    return rows


def _kv_split(line):
    """'Label: value' -> [label, value] cells (no span may be cut)."""
    text = line.text
    for sep in (": ", "：", " : "):
        k = text.find(sep)
        if 0 < k < 40:
            if any(sp["s"] < k + len(sep) and sp["e"] > k for sp in
                   line.spans):
                return None
            a = AText(text[:k])
            b = AText()
            b.text = text[k + len(sep):]
            shift = k + len(sep)
            for sp in line.spans:
                sp2 = dict(sp)
                sp2["s"] -= shift
                sp2["e"] -= shift
                b.spans.append(sp2)
            for tr in line.traps:
                b.traps.append({"s": max(0, tr["s"] - shift),
                                "e": max(0, tr["e"] - shift),
                                "trap": tr["trap"]})
            return [a, b]
    return None


def _grid_for_chunker(rows):
    out_rows, spans = [], {}
    for r, row in enumerate(rows):
        out = []
        for c, at in enumerate(row):
            out.append(at.text)
            items = [(sp["s"], sp["e"], sp["label"]) for sp in at.spans] + \
                [(t["s"], t["e"], "TRAP:" + t["trap"]) for t in at.traps
                 if t["e"] > t["s"]]
            if items:
                spans[(r, c)] = items
        out_rows.append(out)
    return out_rows, spans


def _neutral_header(rows, title):
    """ingest uses the first non-empty row as the header of the whole
    sheet, and header cells never carry labels - so a first row that
    holds a labelled value gets a neutral title row before it."""
    first = next((row for row in rows if any(at.text.strip()
                                             for at in row)), None)
    if first and any(sp["label"] != "REVENUE_YEAR" for at in first
                     for sp in at.spans):
        rows.insert(0, [AText(title)])
    return rows


def render_xlsx(doc, rng, ctx, sources):
    rows = sheet_rows(doc, rng, ctx)
    title = doc.meta.get("sheet_title") or "Sheet1"
    rows = _neutral_header(rows, doc.meta.get("title_text") or title)
    grid, spans = _grid_for_chunker(rows)
    sources.append(("sheet", title, grid))
    pieces = []
    for text, got in chunker.sheet_chunks_annotated(title, grid, spans):
        real, traps = _split_labels(got)
        pieces.append((1, "sheet", text, real, [], traps))
    return pieces


def render_csv(doc, rng, ctx, sources):
    rows = []
    for block in doc.blocks():
        if isinstance(block, Table):
            for row in block.rows:
                rows.append([(c.raw if c.raw is not None and
                              rng.random() < 0.7 else c.at) for c in row])
    rows = _neutral_header(rows, doc.meta.get("title_text") or "export")
    grid, spans = _grid_for_chunker(rows)
    # csv.reader gives "" for empty cells, never None
    grid = [[c or "" for c in row] for row in grid]
    sources.append(("csv", grid))
    pieces = []
    for text, got in chunker.csv_chunks_annotated(grid, spans):
        real, traps = _split_labels(got)
        pieces.append((1, "sheet", text, real, [], traps))
    return pieces


def render_text(doc, rng, ctx, fmt, sources):
    blocks = [b for b in doc.blocks()]
    at = page_text(blocks, rng, fmt, ctx, doc)
    sources.append(("split", at.text))
    spans = _spans_for_chunker(at)
    pieces = []
    for chunk, kept, cut in chunker.split_text_annotated(at.text, spans):
        real, traps = _split_labels(kept)
        pieces.append((1, "text", chunk, real, cut, traps))
    return pieces


def render(doc, fmt, rng, ctx):
    """-> (pieces, sources). sources = what ingest.py itself would be
    given (page texts, table rows, sheet grids), for the self-check."""
    sources = []
    if fmt == "pdf":
        pieces = render_pdf(doc, rng, ctx, sources)
    elif fmt == "docx":
        pieces = render_docx(doc, rng, ctx, sources)
    elif fmt == "xlsx":
        pieces = render_xlsx(doc, rng, ctx, sources)
    elif fmt == "csv":
        pieces = render_csv(doc, rng, ctx, sources)
    else:
        pieces = render_text(doc, rng, ctx, fmt, sources)
    return pieces, sources


def verbatim_texts(sources):
    """The chunk texts the VERBATIM ingest.py functions give for the same
    sources (section 10.9, check 2)."""
    import ingest
    out = []
    for src in sources:
        if src[0] == "split":
            out.extend(ingest.split_text(src[1]))
        elif src[0] == "table":
            made = ingest.table_to_text(src[1])
            if made:
                out.append(made)
        elif src[0] == "sheet":
            title, grid = src[1], src[2]
            rows = [[("" if c is None else str(c)) for c in row]
                    for row in grid]
            rows = [r for r in rows if any(c.strip() for c in r)]
            if rows:
                header, body = rows[0], rows[1:]
                for start in range(0, max(len(body), 1), 25):
                    made = ingest.table_to_text([header] +
                                                body[start:start + 25])
                    if made:
                        out.append("[%s]\n%s" % (title, made))
        elif src[0] == "csv":
            rows = [row for row in src[1] if any(row)]
            if rows:
                header, body = rows[0], rows[1:]
                for start in range(0, max(len(body), 1), 25):
                    made = ingest.table_to_text([header] +
                                                body[start:start + 25])
                    if made:
                        out.append(made)
    return out
