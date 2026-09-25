"""
Stage 1 - turn a folder of documents into good chunks in a database.

    py ingest.py "C:\\Users\\Laurent\\documents to publish"
        Reads every PDF, Word, Excel, CSV and text file in the folder
        (and its subfolders), splits them on real boundaries, and
        stores the pieces in documents.db.

    py ingest.py show
        Prints 30 chunks at random. Read them. This is the test.

    py ingest.py stats
        What is in the database.

Nothing is cut in the middle: tables stay whole, headings stay with
the paragraph under them, and every chunk remembers the file and page
it came from.

First: py -m pip install pdfplumber python-docx openpyxl
"""
import os
import re
import sqlite3
import sys
import random

DB = 'documents.db'
TARGET = 900        # aim for chunks of about this many characters
BIGGEST = 1800      # never go past this, except for a whole table


# ============================================================
#  The database
# ============================================================
def database():
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS files (
                      id INTEGER PRIMARY KEY,
                      path TEXT UNIQUE,
                      kind TEXT,
                      bytes INTEGER,
                      modified REAL,
                      added TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS chunks (
                      id INTEGER PRIMARY KEY,
                      file_id INTEGER,
                      page INTEGER,
                      ordinal INTEGER,
                      kind TEXT,
                      text TEXT)""")
    return db


# ============================================================
#  Splitting - the part that matters
# ============================================================
HEADING = re.compile(r'^\s*(#{1,6}\s+\S|[A-Z][A-Z0-9 \-/&]{3,}\s*$)')


def looks_like_heading(line):
    return bool(HEADING.match(line)) and len(line.strip()) < 90


def split_text(text):
    """Group lines into chunks. A heading always starts a new chunk.
    A chunk ends at a blank line or a finished sentence, once it is
    big enough - so nothing is ever cut mid-sentence.

    This works on line-per-line text out of a PDF just as well as on
    paragraphs separated by blank lines, which matters: PDFs almost
    never contain blank lines.
    """
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
    # a lone title or page header is no use on its own - give it to
    # the chunk it belongs with
    joined = []
    for piece in chunks:
        if joined and len(joined[-1]) < 120:
            joined[-1] = joined[-1] + "\n" + piece
        else:
            joined.append(piece)
    return joined


def table_to_text(rows):
    """A table becomes one chunk, as lines of label: value."""
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


# ============================================================
#  Readers - one per kind of file
# ============================================================
def read_pdf(path):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            for rows in page.extract_tables() or []:
                made = table_to_text(rows)
                if made:
                    out.append((number, 'table', made))
            words = page.extract_text() or ""
            for piece in split_text(words):
                out.append((number, 'text', piece))
    return out


def read_docx(path):
    import docx
    document = docx.Document(path)
    out, buffer = [], []
    for paragraph in document.paragraphs:
        line = paragraph.text.strip()
        if not line:
            buffer.append("")
            continue
        if paragraph.style.name.startswith('Heading'):
            buffer.append("")
            buffer.append(line.upper())
        else:
            buffer.append(line)
    for piece in split_text("\n".join(buffer)):
        out.append((1, 'text', piece))
    for table in document.tables:
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        made = table_to_text(rows)
        if made:
            out.append((1, 'table', made))
    return out


def read_xlsx(path):
    import openpyxl
    book = openpyxl.load_workbook(path, data_only=True)
    out = []
    for number, sheet in enumerate(book.worksheets, start=1):
        rows = [[("" if c is None else str(c)) for c in row]
                for row in sheet.iter_rows(values_only=True)]
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            continue
        header, body = rows[0], rows[1:]
        # keep the header with every group of rows
        for start in range(0, max(len(body), 1), 25):
            made = table_to_text([header] + body[start:start + 25])
            if made:
                out.append((number, 'sheet', "[%s]\n%s"
                            % (sheet.title, made)))
    return out


def read_csv(path):
    import csv
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        rows = [row for row in csv.reader(f) if any(row)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    out = []
    for start in range(0, max(len(body), 1), 25):
        made = table_to_text([header] + body[start:start + 25])
        if made:
            out.append((1, 'sheet', made))
    return out


def read_plain(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    return [(1, 'text', piece) for piece in split_text(text)]


READERS = {'.pdf': read_pdf, '.docx': read_docx, '.xlsx': read_xlsx,
           '.xlsm': read_xlsx, '.csv': read_csv, '.txt': read_plain,
           '.md': read_plain}


# ============================================================
#  Reading the folder
# ============================================================
def ingest(folder):
    db = database()
    found = skipped = added = 0
    for here, _, names in os.walk(folder):
        for name in sorted(names):
            path = os.path.join(here, name)
            kind = os.path.splitext(name)[1].lower()
            if kind not in READERS or name.startswith('~$'):
                continue
            found += 1
            stat = os.stat(path)
            row = db.execute("SELECT id, bytes, modified FROM files"
                             " WHERE path = ?", (path,)).fetchone()
            if row and row[1] == stat.st_size and row[2] == stat.st_mtime:
                skipped += 1
                continue
            try:
                pieces = READERS[kind](path)
            except ImportError as missing:
                print("  ! %s needs a library: %s" % (name, missing))
                continue
            except Exception as problem:
                print("  ! could not read %s: %s" % (name, problem))
                continue
            if row:
                db.execute("DELETE FROM chunks WHERE file_id = ?",
                           (row[0],))
                db.execute("DELETE FROM files WHERE id = ?", (row[0],))
            cursor = db.execute(
                "INSERT INTO files (path, kind, bytes, modified, added)"
                " VALUES (?, ?, ?, ?, datetime('now'))",
                (path, kind, stat.st_size, stat.st_mtime))
            for ordinal, (page, sort, text) in enumerate(pieces):
                db.execute("INSERT INTO chunks (file_id, page, ordinal,"
                           " kind, text) VALUES (?, ?, ?, ?, ?)",
                           (cursor.lastrowid, page, ordinal, sort, text))
            db.commit()
            added += 1
            print("  + %-45s %4d chunks" % (name[:45], len(pieces)))
    db.close()
    print("\n%d files found, %d read, %d unchanged" %
          (found, added, skipped))
    stats()


def stats():
    db = database()
    files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    pieces = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if not pieces:
        print("Nothing in the database yet.")
        db.close()
        return
    sizes = [r[0] for r in db.execute("SELECT LENGTH(text) FROM chunks")]
    print("\n%d files, %s chunks" % (files, format(pieces, ',')))
    print("Chunk size: shortest %d, average %d, longest %d characters"
          % (min(sizes), sum(sizes) // len(sizes), max(sizes)))
    for kind, count in db.execute("SELECT kind, COUNT(*) FROM chunks"
                                  " GROUP BY kind ORDER BY 2 DESC"):
        print("   %-8s %d" % (kind, count))
    db.close()


def show(how_many=30):
    db = database()
    rows = db.execute(
        "SELECT files.path, chunks.page, chunks.kind, chunks.text"
        " FROM chunks JOIN files ON files.id = chunks.file_id").fetchall()
    db.close()
    if not rows:
        print("Nothing to show - run the folder first.")
        return
    for path, page, kind, text in random.sample(
            rows, min(how_many, len(rows))):
        print("=" * 70)
        print("%s  page %s  (%s, %d characters)"
              % (os.path.basename(path), page, kind, len(text)))
        print("-" * 70)
        print(text[:700] + ("..." if len(text) > 700 else ""))
    print("=" * 70)
    print("Read these. Is any table cut in half? Any heading stranded")
    print("from its paragraph? Fix the splitting before going further.")


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['show']:
        show()
    elif args[:1] == ['stats']:
        stats()
    elif args and os.path.isdir(args[0]):
        ingest(args[0])
    else:
        print(__doc__)
