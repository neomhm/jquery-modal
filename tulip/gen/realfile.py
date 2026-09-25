"""
gen/realfile.py - write a generated sheet as a REAL .xlsx or .csv file and
read it back with sheets.load() (section 10.1: 1% of tasks). The preview
of the file must be identical to the preview of the generated sheet.

    write_xlsx(sheet, path)             typed values and number formats
    write_csv(sheet, path, delimiter)   all text, named after its sheet
    round_trip(task, folder) -> (ok, detail)
"""
import csv
import datetime
import pathlib

import sheets

BAD_NAME = '[]:*?/\\'


def write_xlsx(sheet, path):
    import openpyxl
    book = openpyxl.Workbook()
    ws = book.active
    ws.title = sheet.name[:31]
    for i, row in enumerate(sheet.rows):
        for j, v in enumerate(row):
            if v is None:
                continue
            cell = ws.cell(row=i + 1, column=j + 1, value=v)
            fmt = None
            if sheet.formats and i < len(sheet.formats) and \
                    sheet.formats[i] and j < len(sheet.formats[i]):
                fmt = sheet.formats[i][j]
            if isinstance(v, datetime.timedelta) and not fmt:
                fmt = "[h]:mm"
            if fmt:
                cell.number_format = fmt
    book.save(path)


def write_csv(sheet, path, delimiter=",", encoding="utf-8"):
    """Every row padded to the sheet's width, as Excel writes CSV (a
    title row is 'Tarifs 2026;;;;'), so the delimiter can be sniffed."""
    width = max([len(r) for r in sheet.rows] + [1])
    with open(path, "w", encoding=encoding, newline="") as f:
        w = csv.writer(f, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        for row in sheet.rows:
            cells = ["" if v is None else str(v) for v in row]
            w.writerow(cells + [""] * (width - len(cells)))


def round_trip(task, folder):
    """-> (True, '') when the file's preview equals the task's preview."""
    from gen import data as D
    from gen.tasks import sheet_from_task
    sheet = sheet_from_task(task)
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = "".join("_" if ch in BAD_NAME else ch for ch in sheet.name)
    if task["format"] == "xlsx":
        path = folder / ("%s.xlsx" % task["id"])
        write_xlsx(sheet, path)
    else:
        sub = folder / task["id"]
        sub.mkdir(exist_ok=True)
        path = sub / ("%s.csv" % name)        # a CSV is named after its sheet
        loc = D.locale(task["locale"])
        write_csv(sheet, path, loc.get("csv_delimiter") or ",",
                  "utf-8-sig" if task["lang"] in ("ja", "zh", "ko", "ar",
                                                  "hi", "ru") else "utf-8")
    back = sheets.load(path, task["locale"])
    if not back:
        return False, "not read back"
    small, _ = sheets.compact(back[0])
    again = sheets.preview(small, task["targets"], task["locale"])
    if again != task["preview"]:
        a, b = again.splitlines(), task["preview"].splitlines()
        for x, y in zip(a, b):
            if x != y:
                return False, "file: %s | task: %s" % (x[:120], y[:120])
        return False, "different length"
    return True, ""
