"""The runtime around the model, after the conformance check of
26 September 2026: every skipped row is listed (section 7.1), one bad
file never stops a folder import, targets are 1 to 4 known names, and
three helper fixes (Arabic tax words, a locale outside Appendix F, long
date cells)."""
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time

import config
import helpers as H
import sheets
from test_pipeline import FakeTulip, GOOD, small_sheet

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent

# the keys tulip_seam.py (the PLAN's caller) reads from every result
SEAM_KEYS = {"file", "sheet", "status", "target", "reason", "program",
             "candidates_tried", "rows", "sources", "row_numbers",
             "skipped", "problems", "warnings", "seconds"}

NOTES = ("target('products')\nheader(1)\nkeep(not_total('A'))\n"
         "out.name = text(col('A'))\nout.price = amount(col('B'))")


def notes_sheet():
    """60 products, then one unreadable price, one notes line (only
    column C filled) and a totals row, which keep() removes."""
    rows = [["Produit", "Prix", "Note"]]
    rows += [["Article %d" % i, "%d,50" % (i + 1), None] for i in range(60)]
    rows.append(["Baguette", "sur demande", None])            # row 62
    rows.append([None, None, "Prix au 1er mars"])              # row 63
    rows.append(["Total", "1 900,00", None])                   # row 64
    return sheets.Sheet("Tarifs", rows)


# ---------------------------------------------------------- skipped rows
def test_every_skipped_row_is_listed_with_its_reason():
    t = FakeTulip([NOTES])
    r = t._import_sheet(notes_sheet(), ["products"], "fr-FR")
    assert r["status"] == "imported_with_warnings", r["problems"]
    assert len(r["rows"]) == 60
    assert r["skipped"] == [(62, "unreadable:price"),
                            (63, "empty_required"),
                            (64, "totals_row")], r["skipped"]
    assert SEAM_KEYS <= set(r)
    # the values themselves are untouched
    assert r["rows"][0] == {"name": "Article 0", "price": 1.5}


def test_a_notes_row_alone_is_listed():
    """The case the audit found: imported_with_warnings with skipped=[]
    and warnings=[]."""
    sheet = small_sheet()
    sheet.rows.append([None, None, "livraison offerte"])
    t = FakeTulip([GOOD])
    r = t._import_sheet(sheet, ["products"], "fr-FR")
    assert r["status"] == "imported_with_warnings"
    assert r["skipped"] == [(5, "empty_required")]


def test_clean_sheet_has_no_skipped_rows():
    r = FakeTulip([GOOD])._import_sheet(small_sheet(), ["products"],
                                        "fr-FR")
    assert r["status"] == "imported" and r["skipped"] == []


# ---------------------------------------------------------- bad files
def _bad_files(tmp):
    tmp = pathlib.Path(tmp)
    good = tmp / "a_good.csv"
    good.write_text("Produit;Prix\nPain;1,20\nCroissant;1,10\n"
                    "Tarte;12,50\n", encoding="utf-8")
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["Produit", "Prix"])
    full = tmp / "whole.xlsx"
    wb.save(full)
    cut = tmp / "b_truncated.xlsx"
    cut.write_bytes(full.read_bytes()[:700])
    full.unlink()
    binary = tmp / "c_binary.csv"
    binary.write_bytes(bytes(range(256)) * 8)
    return good, cut, binary


def test_import_file_never_raises_on_a_bad_file():
    t = FakeTulip([GOOD])
    with tempfile.TemporaryDirectory() as tmp:
        good, cut, binary = _bad_files(tmp)
        for path, kind in ((cut, "BadZipFile"), (binary, "csv.Error")):
            out = t.import_file(path, ["products"], "fr-FR")
            assert len(out) == 1, out
            r = out[0]
            assert r["status"] == "needs_review", r
            assert r["reason"] == "unreadable_file:" + kind, r["reason"]
            assert r["file"] == str(path) and r["sheet"] == ""
            assert SEAM_KEYS <= set(r)
        out = t.import_file(good, ["products"], "fr-FR")
        assert [r["status"] for r in out] == ["imported"]


def test_one_exception_on_a_sheet_is_that_sheet_only():
    t = FakeTulip([GOOD])

    def boom(*args, **kwargs):
        raise RuntimeError("the writer broke")
    t._write = boom
    with tempfile.TemporaryDirectory() as tmp:
        good, _, _ = _bad_files(tmp)
        r = t.import_file(good, ["products"], "fr-FR")[0]
    assert r["status"] == "needs_review"
    assert r["reason"] == "exception:RuntimeError"


def test_import_sheets_records_a_bad_file_and_goes_on():
    import import_sheets as I
    t = FakeTulip([GOOD])
    with tempfile.TemporaryDirectory() as tmp:
        good, cut, binary = _bad_files(tmp)
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        I.create_tables(db)
        counts = {}
        for path in sorted([cut, good, binary]):
            counts = I.import_path(db, t, path, ["products"], "fr-FR",
                                   "tulip-pilot", counts)
        assert counts == {"imported": 1, "needs_review": 2}, counts
        got = db.execute("SELECT file, sheet, status, reason, rows_out "
                         "FROM tulip_imports ORDER BY file").fetchall()
        assert [g[2:] for g in got] == [
            ("imported", None, 3),
            ("needs_review", "unreadable_file:BadZipFile", 0),
            ("needs_review", "unreadable_file:csv.Error", 0)], got
        assert got[1][1] == "" and got[2][1] == ""
        n = db.execute('SELECT COUNT(*) FROM "tulip_products"').fetchone()
        assert n[0] == 3
        # the same broken file with the same model is not tried again
        counts = I.import_path(db, t, cut, ["products"], "fr-FR",
                               "tulip-pilot", {})
        assert counts == {"unchanged": 1}
        # once the file reads, its "unreadable" line goes
        binary.write_bytes(good.read_bytes())
        counts = I.import_path(db, t, binary, ["products"], "fr-FR",
                               "tulip-pilot", {})
        assert counts == {"imported": 1}
        left = db.execute("SELECT sheet, status FROM tulip_imports WHERE "
                          "file = ?", (str(binary),)).fetchall()
        assert left == [(binary.stem, "imported")], left
        db.close()


# ---------------------------------------------------------- targets
def test_targets_must_be_one_to_four_known_names():
    import tulip as T
    t = FakeTulip([GOOD])
    for bad in (None, [], "products", ["product"], ["products"] * 2,
                ["products", "services", "staff", "clients",
                 "opening_hours"]):
        for call in (lambda: t.import_file("x.csv", bad, "fr-FR"),
                     lambda: t.import_sheet(small_sheet(), bad, "fr-FR")):
            try:
                call()
            except ValueError as e:
                assert "target" in str(e), str(e)
            else:
                raise AssertionError("accepted targets %r" % (bad,))
    assert T.check_targets(("products",)) == ["products"]
    assert len(T.check_targets(config.TARGETS[:4])) == 4


def test_command_line_requires_targets():
    with tempfile.TemporaryDirectory() as tmp:
        for args in ([], ["--targets", ",".join(config.TARGETS)]):
            p = subprocess.run(
                [sys.executable, str(PROJECT / "import_sheets.py"), tmp,
                 "--db", str(pathlib.Path(tmp) / "d.db"),
                 "--locale", "fr-FR"] + args,
                capture_output=True, text=True, timeout=300)
            assert p.returncode == 2, (args, p.returncode, p.stderr[-500:])
            assert "targets" in p.stderr, p.stderr[-500:]


# ---------------------------------------------------------- helpers
def test_arabic_tax_words():
    for word, answer in (("شامل", True), ("شاملة", True),
                         ("شامل الضريبة", True), ("السعر (شامل)", True),
                         ("يشمل الضريبة", True), ("مع الضريبة", True),
                         ("غير شامل", False), ("غير شاملة", False),
                         ("غير شامل الضريبة", False),
                         ("لا يشمل الضريبة", False),
                         ("بدون ضريبة", False), ("قبل الضريبة", False)):
        for locale in ("ar-SA", "ar-EG", None):
            assert H.tax_included(word, locale) == (True, answer), \
                (word, locale, H.tax_included(word, locale))


def test_locale_outside_appendix_f_reads_dates_like_the_first_locale():
    """Section 15.2: en-DE is not an Appendix F pair, so its dates are
    en-US's (M/D/Y); its currency and phone keep the real country."""
    assert H.date("03/04/2024", "en-DE") == (True, "2024-03-04")
    assert H.date("03/04/2024", "en-GB") == (True, "2024-04-03")
    assert H.date("03/04/2024", "fr-LU") == (True, "2024-04-03")
    assert H.amount("1,240", "fr-LU") == (True, 1.24)       # fr-FR: comma
    assert H.amount("1,240", "en-DE") == (True, 1240.0)
    # no country, or an unknown language: unchanged
    assert H.date("03/04/2024", "en") == (True, "2024-04-03")
    assert H.date("03/04/2024", None) == (True, "2024-04-03")
    assert H.format_country("en", "DE") == "US"
    assert H.format_country("zh", "MO") == "CN"
    assert H.format_country("ar", "EG") == "EG"
    assert H.format_country("de", "DE") == "DE"


def test_first_locale_table_matches_locales_json():
    from gen import data as D
    first = {}
    for code, v in D.locales().items():
        first.setdefault(v["lang"], []).append(code.split("-")[1])
    assert first == dict((k, list(v)) for k, v in H.APPENDIX_F.items())


def test_long_cells_are_cheap():
    """date() used to grow with the square of the cell (40,000
    characters: 42 s)."""
    for cell in ("1 " * 20000, "15/03/2024 " * 4000, "a" * 40000,
                 "١ " * 20000):
        for name in ("date", "time", "amount", "hours", "duration"):
            began = time.time()
            got = H.HELPERS[name](cell, "fr-FR")
            assert time.time() - began < 1.0, (name, cell[:20])
            assert got == (False, None)
    # the longest ordinary forms still read
    assert H.date("15 de septiembre de 2024 14:30:00", "es-ES") == \
        (True, "2024-09-15")
    assert H.date("\u200f15 " + "\u200f" * 300 + "مارس 2024", "ar-EG") == \
        (True, "2024-03-15")
    assert H.date("  15   mars   2024  " + " " * 300, "fr-FR") == \
        (True, "2024-03-15")
