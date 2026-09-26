"""
gen/filetypes.py - a generated task as a real .xls, .ods or PDF file
(Tulip 1.1, item G): the sheet is written with gen/realfile.py, read back
with sheets.load() - the very readers Tulip uses - and the task becomes
what the reader gives: its sheet, its preview, its format. It is kept only
if its program still passes the self-check with the real runtime and
gives the same rows (truth first).

    convert(task, "pdf") -> (task, None) or (None, reason)

An .xlsx task can become .xls or .ods (typed cells, number formats), a
.csv task a PDF (text cells). Refusals whose answer depends on the
columns (too_wide, missing_required) are not converted.
"""
import pathlib
import tempfile

import config
import sheets

MADE_FROM = {"xls": "xlsx", "ods": "xlsx", "pdf": "csv"}
# the share of the training tasks of each format that are converted
TRAIN_SHARE = {"xls": 0.08, "ods": 0.08, "pdf": 0.2}


def convertible(task, kind):
    if task.get("format") != MADE_FROM[kind]:
        return False
    answer = task["answer"]
    return answer in config.TARGETS or answer in ("not_a_table",
                                                  "no_matching_target")


def _file_name(sheet, kind):
    from gen import realfile as RF
    stem = "".join("_" if ch in RF.BAD_NAME else ch for ch in sheet.name)
    return "%s.%s" % (stem.strip() or "Sheet1", kind)


def convert(task, kind):
    """The task written as `kind` and read back -> (task, None), or
    (None, reason) when the file does not give the task back."""
    import gen.sheetkit as K
    from gen import realfile as RF
    from gen import tasks as T
    if not convertible(task, kind):
        return None, "file_%s:not_convertible" % kind
    sheet = T.sheet_from_task(task)
    with tempfile.TemporaryDirectory(prefix="tulip-ft-") as tmp:
        path = pathlib.Path(tmp) / _file_name(sheet, kind)
        try:
            if kind == "xls":
                RF.write_xls(sheet, path)
            elif kind == "ods":
                RF.write_ods(sheet, path, task["locale"])
            else:
                right = _numeric_columns(sheet)
                RF.write_pdf(sheet, path, right=right)
            back = sheets.load(path, task["locale"])
        except Exception as e:
            return None, "file_%s:%s" % (kind, type(e).__name__)
    if len(back) != 1:
        return None, "file_%s:sheets" % kind
    back = back[0]
    back.name = sheet.name            # a PDF is named after its file
    if task["answer"] in config.TARGETS:
        res, problems = K.self_check(task["program"], back, task["locale"],
                                     task["targets"])
        if res is None or problems or not K.truth_matches(res,
                                                          task["truth"]):
            return None, "file_%s:self_check" % kind
    small, _ = sheets.compact(back)
    preview = sheets.preview(small, task["targets"], task["locale"])
    out = dict(task, format=kind, preview=preview)
    out["sheet"] = {"name": back.name,
                    "rows": [[T.tag(v) for v in r] for r in back.rows],
                    "formats": back.formats}
    return out, None


def _numeric_columns(sheet):
    """Columns whose filled cells are mostly numbers: written flush right,
    as report writers print them."""
    import tulipscript as ts
    width = max([len(r) for r in sheet.rows] + [0])
    right = []
    for j in range(width):
        cells = [r[j] for r in sheet.rows if j < len(r) and r[j] not in
                 (None, "")]
        if cells and sum(1 for c in cells if ts._numberish(c)) * 2 > \
                len(cells):
            right.append(j)
    return tuple(right)
