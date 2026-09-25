"""
chunker.py - the exact chunking rules of ingest.py, plus "annotated"
twins that carry labelled spans through the same cuts.

The first half is copied from ingest.py WITHOUT CHANGES. Never edit it
here: if ingest.py changes, copy it again. The test in test_chunker.py
proves that the annotated twins produce byte-identical text.

A span is (start, end, label) in character positions, end exclusive,
exactly like Python slicing: text[start:end] is the labelled value.
"""
import re

TARGET = 900        # aim for chunks of about this many characters
BIGGEST = 1800      # never go past this, except for a whole table

# ------------------------------------------------------------------
#  Copied verbatim from ingest.py
# ------------------------------------------------------------------
HEADING = re.compile(r'^\s*(#{1,6}\s+\S|[A-Z][A-Z0-9 \-/&]{3,}\s*$)')


def looks_like_heading(line):
    return bool(HEADING.match(line)) and len(line.strip()) < 90


def split_text(text):
    chunks, current = [], []

    def finish():
        joined = "\n".join(current).strip()
        if len(joined) > 20:
            chunks.append(joined)
        del current[:]

    for line in text.split("\n"):
        bare = line.strip()
        size = sum(len(piece) + 1 for piece in current)
        ended = bool(current) and current[-1].rstrip().endswith(
            ('.', '!', '?', ':', ';'))
        if current and bare and looks_like_heading(line):
            finish()
        elif size >= TARGET and (not bare or ended):
            finish()
        elif size >= BIGGEST:
            finish()
        if bare or current:
            current.append(line)
    finish()
    joined = []
    for piece in chunks:
        if joined and len(joined[-1]) < 120:
            joined[-1] = joined[-1] + "\n" + piece
        else:
            joined.append(piece)
    return joined


def table_to_text(rows):
    rows = [[(cell or "").strip() for cell in row] for row in rows
            if any(cell for cell in row)]
    if not rows:
        return None
    header = rows[0]
    lines = [" | ".join(header)]
    for row in rows[1:]:
        pairs = ["%s: %s" % (header[i] if i < len(header) else "col%d" % i,
                             cell)
                 for i, cell in enumerate(row) if cell]
        lines.append("; ".join(pairs))
    return "\n".join(lines)


# ------------------------------------------------------------------
#  Annotated twins
# ------------------------------------------------------------------
def _project(chunk_len, doc_pos, spans):
    """doc_pos[i] = position in the document of chunk character i
    (or -1 for a joining newline that is not in the document).
    Returns (kept, cut): kept spans fully and contiguously inside the
    chunk, and cut ranges = pieces of spans that a boundary sliced."""
    where = {p: i for i, p in enumerate(doc_pos) if p >= 0}
    kept, cut = [], []
    for s, e, label in spans:
        mapped = [where.get(p) for p in range(s, e)]
        inside = [m for m in mapped if m is not None]
        if not inside:
            continue
        whole = (len(inside) == len(mapped) and
                 inside == list(range(inside[0], inside[0] + len(inside))))
        if whole:
            kept.append((inside[0], inside[-1] + 1, label))
        else:
            start = prev = inside[0]
            for m in inside[1:]:
                if m != prev + 1:
                    cut.append((start, prev + 1))
                    start = m
                prev = m
            cut.append((start, prev + 1))
    return kept, cut


def split_text_annotated(text, spans):
    """Same chunks as split_text(text), with spans carried along.

    Returns a list of (chunk_text, kept_spans, cut_ranges).
    kept_spans are (start, end, label) inside chunk_text.
    cut_ranges are (start, end) inside chunk_text that belong to a
    span sliced by a chunk boundary: training must IGNORE those
    characters (label -100), never call them O and never call them
    the label."""
    lines = text.split("\n")
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    ranges, current = [], []          # current = line numbers

    def finish():
        joined = "\n".join(lines[i] for i in current).strip()
        if len(joined) > 20:
            a = starts[current[0]]
            b = starts[current[-1]] + len(lines[current[-1]])
            raw = text[a:b]
            lead = len(raw) - len(raw.lstrip())
            trail = len(raw) - len(raw.rstrip())
            ranges.append((a + lead, b - trail))
            assert text[a + lead:b - trail] == joined
        del current[:]

    for n, line in enumerate(lines):
        bare = line.strip()
        size = sum(len(lines[i]) + 1 for i in current)
        ended = bool(current) and lines[current[-1]].rstrip().endswith(
            ('.', '!', '?', ':', ';'))
        if current and bare and looks_like_heading(line):
            finish()
        elif size >= TARGET and (not bare or ended):
            finish()
        elif size >= BIGGEST:
            finish()
        if bare or current:
            current.append(n)
    finish()

    # the "give a short piece to the next one" step, on segments
    merged = []                       # each = list of (a, b) doc ranges
    for a, b in ranges:
        if merged and _length(merged[-1]) < 120:
            merged[-1].append((a, b))
        else:
            merged.append([(a, b)])

    out = []
    for segments in merged:
        pieces, doc_pos = [], []
        for k, (a, b) in enumerate(segments):
            if k:
                prev_end = segments[k - 1][1]
                # the joining newline IS the document's newline only
                # when nothing was dropped between the two segments
                doc_pos.append(prev_end if (a == prev_end + 1 and
                                            text[prev_end] == "\n") else -1)
                pieces.append("\n")
            pieces.append(text[a:b])
            doc_pos.extend(range(a, b))
        chunk = "".join(pieces)
        assert all(chunk[i] == text[p] for i, p in enumerate(doc_pos)
                   if p >= 0)
        kept, cut = _project(len(chunk), doc_pos, spans)
        out.append((chunk, kept, cut))
    return out


def _length(segments):
    return sum(b - a for a, b in segments) + len(segments) - 1


# Labels that a header cell may carry into a data row. The header
# occurrence inside "header: value" is labelled only when the value
# cell of THAT row carries one of the paired labels. Everywhere else
# (the header line itself, other rows) the header text is O.
HEADER_PAIRING = {'REVENUE_YEAR': {'REVENUE'}}


def table_to_text_annotated(rows, cell_spans):
    """Same text as table_to_text(rows).

    rows: list of rows, each a list of cell strings (or None).
    cell_spans: {(row_index, col_index): [(start, end, label), ...]}
        positions inside the ORIGINAL (unstripped) cell string, using
        the ORIGINAL row numbering (before empty rows are dropped).
    Returns (text, spans) or (None, []) if the table is empty."""
    kept_rows = []
    for r, row in enumerate(rows):
        if any(cell for cell in row):
            kept_rows.append((r, row))
    if not kept_rows:
        return None, []

    cleaned = []                      # (orig_r, [cells], [shift])
    for r, row in kept_rows:
        cells, shifts = [], []
        for cell in row:
            raw = cell or ""
            cells.append(raw.strip())
            shifts.append(len(raw) - len(raw.lstrip()))
        cleaned.append((r, cells, shifts))

    def spans_in(r, c, shift, width, offset):
        found = []
        for s, e, label in cell_spans.get((r, c), []):
            s2, e2 = s - shift, e - shift
            if s2 >= 0 and e2 <= width and e2 > s2:
                found.append((offset + s2, offset + e2, label))
        return found

    head_r, header, head_shift = cleaned[0]
    text_parts, spans = [" | ".join(header)], []
    pos = len(text_parts[0])
    for r, cells, shifts in cleaned[1:]:
        pos += 1                                  # the "\n"
        line_start = pos
        pairs, line_spans = [], []
        cursor = line_start
        first = True
        for i, cell in enumerate(cells):
            if not cell:
                continue
            if not first:
                cursor += 2                       # "; "
            first = False
            name = header[i] if i < len(header) else "col%d" % i
            value_spans = spans_in(r, i, shifts[i], len(cell),
                                   cursor + len(name) + 2)
            if i < len(header):
                row_labels = {lab for _, _, lab in value_spans}
                for s, e, lab in cell_spans.get((head_r, i), []):
                    if HEADER_PAIRING.get(lab, set()) & row_labels:
                        s2, e2 = s - head_shift[i], e - head_shift[i]
                        if 0 <= s2 < e2 <= len(name):
                            line_spans.append((cursor + s2, cursor + e2,
                                               lab))
            line_spans.extend(value_spans)
            pairs.append("%s: %s" % (name, cell))
            cursor += len(name) + 2 + len(cell)
        line = "; ".join(pairs)
        text_parts.append(line)
        spans.extend(line_spans)
        pos = line_start + len(line)
    text = "\n".join(text_parts)
    return text, sorted(set(spans))


def sheet_chunks_annotated(title, rows, cell_spans):
    """Mirror of ingest.read_xlsx for ONE sheet: rows of strings,
    empty rows dropped, header repeated on every group of 25 rows,
    each chunk prefixed with "[title]\\n". Returns a list of
    (chunk_text, spans)."""
    rows = [[("" if c is None else str(c)) for c in row] for row in rows]
    keep = [(r, row) for r, row in enumerate(rows)
            if any(c.strip() for c in row)]
    if not keep:
        return []
    (head_r, header), body = keep[0], keep[1:]
    out = []
    for start in range(0, max(len(body), 1), 25):
        group = [(head_r, header)] + body[start:start + 25]
        sub_rows = [row for _, row in group]
        sub_spans = {}
        for new_r, (old_r, row) in enumerate(group):
            for c in range(len(row)):
                if (old_r, c) in cell_spans:
                    sub_spans[(new_r, c)] = cell_spans[(old_r, c)]
        made, spans = table_to_text_annotated(sub_rows, sub_spans)
        if made:
            prefix = "[%s]\n" % title
            out.append((prefix + made,
                        [(s + len(prefix), e + len(prefix), lab)
                         for s, e, lab in spans]))
    return out


def csv_chunks_annotated(rows, cell_spans):
    """Mirror of ingest.read_csv: rows as csv.reader gives them (lists
    of strings), rows with no non-empty string dropped, header repeated
    on every group of 25 rows, NO title line. Returns (text, spans)."""
    keep = [(r, row) for r, row in enumerate(rows) if any(row)]
    if not keep:
        return []
    (head_r, header), body = keep[0], keep[1:]
    out = []
    for start in range(0, max(len(body), 1), 25):
        group = [(head_r, header)] + body[start:start + 25]
        sub_rows = [row for _, row in group]
        sub_spans = {}
        for new_r, (old_r, row) in enumerate(group):
            for c in range(len(row)):
                if (old_r, c) in cell_spans:
                    sub_spans[(new_r, c)] = cell_spans[(old_r, c)]
        made, spans = table_to_text_annotated(sub_rows, sub_spans)
        if made:
            out.append((made, spans))
    return out
