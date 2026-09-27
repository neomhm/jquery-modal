"""
Item G of the Tulip 1.1 work order, the code part: tables in PDFs (read
back from where their text is written), old Excel .xls and LibreOffice
.ods files, several tables on one sheet, and several days in one cell
("Lun-Ven"). The readers are checked on sheets the generator draws, in
every format they are written in.
"""
import pathlib
import tempfile

import config
import sheets
import tulipscript as ts
from gen import realfile as RF
from gen import tasks as T
from test_pipeline import FakeTulip

N_TASKS = 40


def generated(n=N_TASKS, start=96000):
    out = []
    for i in range(n):
        task, _ = T.make_task("val", start + i)
        if task:
            out.append(task)
    return out


_TASKS = None


def tasks():
    global _TASKS
    if _TASKS is None:
        _TASKS = generated()
    return _TASKS


def self_check(task, sheet):
    import gen.sheetkit as K
    res, problems = K.self_check(task["program"], sheet, task["locale"],
                                 task["targets"])
    if task["answer"] not in config.TARGETS:
        return True
    return res is not None and not problems and \
        K.truth_matches(res, task["truth"])


def file_name(sheet, kind):
    return "".join("_" if ch in RF.BAD_NAME else ch
                   for ch in sheet.name) + "." + kind


def same_cells(a, b):
    """Equal grids; ODS stores a duration and a time of day alike (a
    'time' value), so 4:00 as a duration and 04:00 are the same cell."""
    import datetime

    def plain(v):
        if isinstance(v, datetime.timedelta):
            return ("t", int(v.total_seconds()))
        if isinstance(v, datetime.time):
            return ("t", v.hour * 3600 + v.minute * 60 + v.second)
        return v
    return [[plain(v) for v in r] for r in a] == \
        [[plain(v) for v in r] for r in b]


# ---------------------------------------------------------- the readers
def test_xls_gives_the_xlsx_preview():
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for task in tasks():
            if task["format"] != "xlsx":
                continue
            sheet = T.sheet_from_task(task)
            path = pathlib.Path(tmp) / (task["id"] + ".xls")
            RF.write_xls(sheet, path)
            back = sheets.load(path, task["locale"])[0]
            small, _ = sheets.compact(back)
            assert sheets.preview(small, task["targets"], task["locale"]) \
                == task["preview"], task["id"]
            assert self_check(task, back), task["id"]
            n += 1
    assert n >= 20


def test_ods_keeps_every_value():
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for task in tasks():
            if task["format"] != "xlsx":
                continue
            sheet = T.sheet_from_task(task)
            path = pathlib.Path(tmp) / (task["id"] + ".ods")
            RF.write_ods(sheet, path, task["locale"])
            back = sheets.load(path, task["locale"])[0]
            assert same_cells(back.rows, sheets._trim(sheet.rows)[0]), \
                task["id"]
            assert self_check(task, back), task["id"]
            n += 1
    assert n >= 20


def test_pdf_gives_back_the_table():
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for task in tasks():
            if task["format"] != "csv":
                continue
            sheet = T.sheet_from_task(task)
            folder = pathlib.Path(tmp) / task["id"]
            folder.mkdir()
            path = folder / file_name(sheet, "pdf")
            RF.write_pdf(sheet, path)
            back = sheets.load(path, task["locale"])
            assert len(back) == 1, task["id"]
            assert self_check(task, back[0]), task["id"]
            if len(sheet.rows) < 55:       # one page: the very same grid
                want = [[None if v in (None, "") else str(v).strip()
                         for v in r] for r in sheet.rows]
                assert back[0].rows == sheets._trim(want)[0], task["id"]
            n += 1
    assert n >= 8


def test_pdf_in_every_script():
    """Arabic is stored in visual order in PDFs, as PDF writers store it;
    the reader gives it back in reading order, numbers included."""
    rows = [["Tarifs au 01/03/2026"], [], ["Produit", "Prix", "Stock"],
            ["Pain au chocolat", "1,30", "40"], ["牛奶 1升", "12,50", "3"],
            ["خبز عربي", "3,00", "7"], ["قطعة 12", "5", "1"],
            ["السعر 12,50 ر.س", "6", "2"], ["हिंदी शब्द", "4", "1"],
            ["Сок 1 л", "99", "2"], ["우유", "1.500", "8"],
            ["クロワッサン", "250", "5"]]
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "t.pdf"
        from gen import pdfwrite
        pdfwrite.write_pdf(path, rows, right=(1, 2))
        back = sheets.load(path)[0]
    assert back.rows == sheets._trim(rows)[0]


def test_a_pdf_table_goes_on_over_pages():
    rows = [["Produit", "Prix"]] + [["Article %d" % i, "%d,50" % i]
                                    for i in range(150)]
    rows.append(["Total", "999"])
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "long.pdf"
        from gen import pdfwrite
        pdfwrite.write_pdf(path, rows, right=(1,), repeat_header=0)
        back = sheets.load(path)
    assert len(back) == 1 and back[0].name == "long"
    got = [r for r in back[0].rows if r != ["Produit", "Prix"]]
    assert got == rows[1:]


def test_a_scanned_pdf_needs_review():
    from gen import pdfwrite
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "scan.pdf"
        pdfwrite._write(path, [b"0 0 1 rg 0 0 100 100 re f"],
                        pdfwrite._Font(), 595, 842)
        t = FakeTulip(["target('products')"])
        out = t.import_file(path, ["products"], "fr-FR")
    assert len(out) == 1
    assert out[0]["status"] == "needs_review"
    assert out[0]["reason"] == "scanned_pdf"


def test_ods_repeats_are_not_expanded():
    """LibreOffice writes the empty rest of a sheet as one row repeated a
    million times: it is never expanded."""
    import zipfile
    content = (
        '<?xml version="1.0" encoding="UTF-8"?><office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:spreadsheet><table:table table:name="T">'
        '<table:table-row><table:table-cell office:value-type="string">'
        '<text:p>Produit</text:p></table:table-cell>'
        '<table:table-cell table:number-columns-repeated="3"/>'
        '<table:table-cell office:value-type="string"><text:p>Prix'
        '</text:p></table:table-cell><table:table-cell '
        'table:number-columns-repeated="16379"/></table:table-row>'
        '<table:table-row><table:table-cell office:value-type="string">'
        '<text:p>Pain</text:p></table:table-cell><table:table-cell '
        'table:number-columns-repeated="3"/><table:table-cell '
        'office:value-type="float" office:value="1.2"><text:p>1,20</text:p>'
        '</table:table-cell></table:table-row>'
        '<table:table-row table:number-rows-repeated="1048574">'
        '<table:table-cell table:number-columns-repeated="16384"/>'
        '</table:table-row></table:table></office:spreadsheet>'
        '</office:body></office:document-content>')
    import time
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "t.ods"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype",
                       "application/vnd.oasis.opendocument.spreadsheet")
            z.writestr("content.xml", content)
        began = time.time()
        back = sheets.load(path)[0]
        took = time.time() - began
    assert back.rows == [["Produit", None, None, None, "Prix"],
                         ["Pain", None, None, None, 1.2]]
    # expanded, the million rows of 16,384 cells would take minutes and
    # gigabytes; not expanded, a few milliseconds
    assert took < 5.0, took


def test_every_readable_file_type_is_imported():
    import import_sheets as I
    assert set(I.READABLE) == {".xlsx", ".xlsm", ".csv", ".xls", ".ods",
                               ".pdf"}


# ---------------------------------------------------------- days
DAY_CASES = [
    ("Lun–Ven", "fr-FR", (0, 1, 2, 3, 4)),
    ("du lundi au vendredi", "fr-FR", (0, 1, 2, 3, 4)),
    ("lundi, mercredi et vendredi", "fr-FR", (0, 2, 4)),
    ("en semaine", "fr-FR", (0, 1, 2, 3, 4)),
    ("Mon-Fri", "en-GB", (0, 1, 2, 3, 4)),
    ("Sat & Sun", "en-US", (5, 6)),
    ("Sat-Mon", "en-US", (5, 6, 0)),
    ("every day", "en-US", (0, 1, 2, 3, 4, 5, 6)),
    ("月～金", "ja-JP", (0, 1, 2, 3, 4)),
    ("月曜日から金曜日", "ja-JP", (0, 1, 2, 3, 4)),
    ("土日", "ja-JP", (5, 6)),
    ("周一至周五", "zh-CN", (0, 1, 2, 3, 4)),
    ("星期一到星期五", "zh-CN", (0, 1, 2, 3, 4)),
    ("월~금", "ko-KR", (0, 1, 2, 3, 4)),
    ("월요일부터 금요일까지", "ko-KR", (0, 1, 2, 3, 4)),
    ("Пн–Пт", "ru-RU", (0, 1, 2, 3, 4)),
    ("с понедельника по пятницу", "ru-RU", (0, 1, 2, 3, 4)),
    ("من الاثنين إلى الجمعة", "ar-SA", (0, 1, 2, 3, 4)),
    ("السبت - الخميس", "ar-EG", (5, 6, 0, 1, 2, 3)),
    ("सोमवार से शुक्रवार", "hi-IN", (0, 1, 2, 3, 4)),
    ("de lunes a viernes", "es-MX", (0, 1, 2, 3, 4)),
    ("L-V", "es-ES", (0, 1, 2, 3, 4)),
    ("dal lunedì al venerdì", "it-IT", (0, 1, 2, 3, 4)),
    ("lundi", "fr-FR", (0,)),
]


def test_several_days_in_one_cell_in_every_language():
    import helpers as H
    langs = set()
    for text, locale, want in DAY_CASES:
        assert H.weekdays(text, locale) == (True, want), (text, locale)
        langs.add(locale.split("-")[0])
    assert langs == set(config.LANGS)
    for text in ("9h-18h", "Fermé", "", "Pain", "12"):
        assert H.weekdays(text, "fr-FR")[0] is False, text


HOURS_PROGRAM = ("target('opening_hours')\nheader(1)\n"
                 "out.day = weekdays(col('A'))\nout.hours = hours(col('B'))")


def test_a_day_range_row_becomes_one_row_per_day():
    import contract
    import helpers as H
    sheet = sheets.Sheet("Horaires", [
        ["Jours", "Horaires"], ["Lun–Ven", "9h-12h / 14h-19h"],
        ["Samedi", "9h-12h"], ["Dimanche", "Fermé"]])
    prog = ts.parse(HOURS_PROGRAM)
    res = ts.run(prog, sheet, H.HELPERS, "fr-FR", ["opening_hours"],
                 H.TOTALS)
    assert res.status == "imported", res.problems
    assert [r["day"] for r in res.rows] == [0, 1, 2, 3, 4, 5, 6]
    assert res.row_numbers == [2, 2, 2, 2, 2, 3, 4]
    assert all(s["day"] == [(2, "A")] for s in res.sources[:5])
    rows = contract.convert_rows("opening_hours", res.rows)
    assert len(rows) == 12 and rows[-1] == {"day": "sunday", "opens": None,
                                            "closes": None, "closed": True}
    assert contract.to_internal("opening_hours", *contract.convert(
        "opening_hours", res.rows, None, res.row_numbers)[::2]) == res.rows
    # a program with weekday() reads the same sheet as before: the range
    # is not a day
    old = ts.run(ts.parse(HOURS_PROGRAM.replace("weekdays", "weekday")),
                 sheet, H.HELPERS, "fr-FR", ["opening_hours"], H.TOTALS)
    assert [r["day"] for r in old.rows] == [5, 6]
    assert ts.canonical(HOURS_PROGRAM) == HOURS_PROGRAM


def test_the_new_splits_go_round_every_language():
    """A task's language is index % 10. Each half of test_layouts (even
    indexes: several days in one cell; odd: several tables) must still
    have all ten, and the .xls / .ods choice must not follow the index
    (it gave .xls to five languages and .ods to the other five)."""
    for half in (0, 1):
        langs = set(T.D.locale(T.layout_locale("test_layouts", 2 * i + half))
                    ["lang"] for i in range(20))
        assert langs == set(config.LANGS), (half, sorted(langs))
    for split in ("test_files", "train"):
        seen = set((i % 10, T.file_kind(split, i, "xlsx"))
                   for i in range(400))
        assert seen == set((slot, kind) for slot in range(10)
                           for kind in ("xls", "ods")), split
    assert T.file_kind("train", 7, "csv") == "pdf"
    # the drawn sheets (and every table of a multi-table sheet) are in
    # that language
    for i in (4, 5, 6, 7):
        task, _ = T.make_task("test_layouts", i)
        assert task is not None, i
        assert task["locale"] == T.layout_locale("test_layouts", i), i


def test_the_data_checks_find_a_missing_language():
    from gen import checks

    def fake(lang, fmt="xlsx", **more):
        return dict({"lang": lang, "format": fmt}, **more)
    every = [fake(l) for l in config.LANGS for _ in range(3)]
    splits = dict((s, list(every)) for s in config.SPLITS)
    splits["test_layouts"] = every + [fake(l, multi=True) for l in
                                      config.LANGS for _ in range(3)]
    assert checks.language_gaps(splits) == []
    # the day-range half of test_layouts in five languages only
    splits["test_layouts"] = [fake(l) for l in config.LANGS[::2]
                              for _ in range(6)] + \
        [fake(l, multi=True) for l in config.LANGS for _ in range(3)]
    assert checks.language_gaps(splits) == [
        "test_layouts, several days: no zh, fr, es, hi, ko"]
    # .xls in five languages only
    splits["test_layouts"] = every + [fake(l, multi=True) for l in
                                      config.LANGS for _ in range(3)]
    splits["test_files"] = [fake(l, "xls") for l in config.LANGS[::2]
                            for _ in range(6)] + \
        [fake(l, "ods") for l in config.LANGS for _ in range(3)]
    assert checks.language_gaps(splits) == [
        "test_files .xls: no zh, fr, es, hi, ko"]


def test_weekdays_only_fills_a_day():
    try:
        ts.parse("target('products')\nheader(1)\n"
                 "out.name = weekdays(col('A'))\nout.price = amount(col('B'))")
        raise AssertionError("weekdays() accepted for a text field")
    except ts.TulipError as e:
        assert e.code == "wrong_kind"


# ---------------------------------------------------------- tables
def test_tables_on_one_sheet_are_found():
    import blocks
    cases = {
        "one table": ([["TARIFS 2026"], [], ["Produit", "Prix"],
                       ["Pain", "1,20"], ["Croissant", "1,10"], [],
                       ["Total", "2,30"]], [(0, 0)]),
        "a blank row inside": ([["Nom", "Rôle", "Email"],
                                ["Marie", "Vendeuse", "m@x.fr"], [],
                                ["Paul", "Boulanger", "p@x.fr"]], [(0, 0)]),
        "the header repeated": ([["Produit", "Prix"], ["Pain", "1,20"], [],
                                 ["Produit", "Prix"], ["Tarte", "12,50"]],
                                [(0, 0)]),
        "notes after": ([["Produit", "Prix"], ["Pain", "1,20"], [],
                         ["Conditions générales : paiement à 30 jours"]],
                        [(0, 0)]),
        "two tables": ([["Produits"], ["Produit", "Prix"], ["Pain", "1,20"],
                        ["Croissant", "1,10"], [], [], ["Horaires"],
                        ["Jour", "Horaires"], ["Lundi", "9h-19h"],
                        ["Mardi", "9h-19h"]], [(0, 0), (6, 0)]),
        "side by side": ([["Produit", "Prix", None, "Jour", "Horaires"],
                          ["Pain", "1,20", None, "Lundi", "9h-19h"],
                          ["Croissant", "1,10", None, "Mardi", "9h-19h"]],
                         [(0, 0), (0, 3)]),
    }
    for name, (rows, want) in cases.items():
        parts = blocks.split(sheets.Sheet("S", rows))
        got = [(getattr(p, "row_offset", 0), getattr(p, "column_offset", 0))
               for p in parts]
        assert got == want, (name, got)


def test_single_table_sheets_are_never_cut():
    """The generator's sheets and the handwritten set hold one table
    each: none is cut."""
    import blocks
    for task in tasks():
        assert len(blocks.split(T.sheet_from_task(task))) == 1, task["id"]
    here = pathlib.Path(__file__).resolve().parent.parent / "handwritten"
    n = 0
    for path in sorted(here.glob("*")):
        if path.suffix in (".xlsx", ".csv"):
            for s in sheets.load(path):
                assert len(blocks.split(s)) == 1, (path.name, s.name)
                n += 1
    assert n >= 30


class ByPreview:
    """A stand-in writer that picks its program by what the preview
    shows."""

    def __new__(cls, choose):
        t = FakeTulip(["x"])

        def write(preview, n=7, greedy_only=False, sampled_only=False):
            p = choose(preview)
            if greedy_only:
                return [p]
            return [None if sampled_only else p] + [p] * n
        t._write = write
        return t


def test_each_table_is_imported_on_its_own():
    rows = [["Tarifs 2026"], ["Produit", "Prix", None, "Jour", "Horaires"],
            ["Pain", "1,20", None, "Lundi", "9h-19h"],
            ["Croissant", "1,10", None, "Mardi", "9h-19h"], [], [],
            ["Personnel"], ["Nom", "Email"], ["Marie", "marie@x.fr"],
            ["Paul", "paul@x.fr"]]
    # each table is read from its own R1: a title row above the header
    # makes it header(2), as the model reads it in the preview
    programs = {
        "Produit": "target('products')\nheader(2)\nout.name = "
                   "text(col('A'))\nout.price = amount(col('B'))",
        "Jour": "target('opening_hours')\nheader(1)\nout.day = "
                "weekday(col('A'))\nout.hours = hours(col('B'))",
        "Email": "target('staff')\nheader(2)\nout.name = text(col('A'))\n"
                 "out.email = email(col('B'))"}

    def choose(preview):
        head = [x for x in preview.splitlines() if x.startswith("R")][0:3]
        for word, p in programs.items():
            if any(word in x for x in head):
                return p
        return "refuse('not_a_table')"
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "tout.csv"
        path.write_text("\n".join(";".join("" if v is None else v
                                           for v in r) for r in rows),
                        encoding="utf-8")
        out = ByPreview(choose).import_file(path, ["products", "staff",
                                                   "opening_hours"],
                                            "fr-FR")
    assert [(r["sheet"], r["status"], r["target"]) for r in out] == [
        ("tout #1", "imported", "products"),
        ("tout #2", "imported", "opening_hours"),
        ("tout #3", "imported", "staff")]
    # the sheet's own rows and letters
    assert out[0]["row_numbers"] == [3, 4]
    assert out[0]["sources"][0]["price"] == [(3, "B")]
    assert out[1]["row_numbers"] == [3, 4]
    assert out[1]["sources"][0]["opens"] == [(3, "E")]
    assert out[2]["row_numbers"] == [9, 10]
    assert out[2]["sources"][1]["email"] == [(10, "B")]


def test_typed_rows_after_a_blank_row_are_data():
    """A bookings sheet by day: after a blank row, a row of a time, a
    duration and texts is data, not the header of a new table (it was
    cut in two before headers had to be texts)."""
    import blocks
    import datetime
    t = datetime.time
    rows = [["Hora", "Duración", "Especialista", "Servicio", "Estado"],
            ["17 de junio de 2026"],
            [t(8, 0), "30 min", "Ángel Soler", "Corte", "Realizada"],
            [t(9, 30), "30 min", "Ángel Soler", "Depilación", "Realizada"],
            [],
            [t(11, 0), datetime.timedelta(minutes=30), "Ángel Soler",
             "Depilación de piernas", "Reservada"],
            [t(12, 0), 30, "Ángel Soler", "Corte infantil", "Cancelada"],
            [t(12, 30), "30 min", "Elena Mas", "Corte", "Reservada"]]
    assert len(blocks.split(sheets.Sheet("Citas", rows))) == 1
