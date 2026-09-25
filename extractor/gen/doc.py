"""
doc.py - the shape of a generated document before it becomes a file.

A layout (gen/layouts/*.py) returns a Doc: a list of pages, each a list
of blocks. render.py then turns the Doc into what ingest.py would read
from a PDF, Word, Excel, CSV or text file.

Blocks:
    Para(at, prose=True)   lines of text (AText); prose may be hard-wrapped
    Heading(at, level)     a title line (Word upper-cases it, Markdown #)
    Table(rows)            rows of Cell; the first row is the header
    Columns(left, right)   two blocks side by side (seller | customer)
    Blank()                an empty line
"""
from gen.text import AText


class Cell:
    """One table cell. raw = the same value as a spreadsheet stores it
    (AText of '2220.0' or '2024-03-15 00:00:00'), or None for text."""

    def __init__(self, at, raw=None):
        self.at = at if isinstance(at, AText) else AText(at or "")
        self.raw = raw

    def __repr__(self):
        return "Cell(%r)" % self.at.text


class Para:
    def __init__(self, at, prose=True):
        self.at = at if isinstance(at, AText) else AText(at)
        self.prose = prose


class Heading:
    def __init__(self, at, level=1):
        self.at = at if isinstance(at, AText) else AText(at)
        self.level = level


class Table:
    def __init__(self, rows, title=None):
        self.rows = [[c if isinstance(c, Cell) else Cell(c) for c in row]
                     for row in rows]
        self.title = title


class Columns:
    def __init__(self, left, right):
        self.left = left if isinstance(left, AText) else AText(left)
        self.right = right if isinstance(right, AText) else AText(right)


class Blank:
    pass


class Doc:
    def __init__(self, doc_type, kind, layout):
        self.doc_type = doc_type        # one of config.DOC_TYPES
        self.kind = kind                # invoice / receipt / credit_note ...
        self.layout = layout            # e.g. "invoice.L05"
        self.pages = [[]]
        self.templates = []             # ids of the templates used
        self.traps = set()              # traps shown by the whole document
        self.date = None                # the DOC_DATE, if any
        self.direction = "none"         # sales / purchase / none
        self.meta = {}

    def add(self, block):
        self.pages[-1].append(block)
        return block

    def new_page(self):
        if self.pages[-1]:
            self.pages.append([])

    def blocks(self):
        for page in self.pages:
            for block in page:
                yield block
