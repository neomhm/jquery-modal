"""
gen/multitable.py - sheets that hold two or three tables (Tulip 1.1,
item G), for the evaluation split test_layouts: tables the generator
draws (one locale, one format, different targets) put one under the
other with empty rows between them, or side by side with an empty
column between them. The model never sees such a sheet whole:
blocks.split() cuts it first, and each table is imported on its own - so
the task is kept only when the cut gives back exactly its tables, and
each table's program gives its rows on the cut.

    make(split, index) -> (task or None, reasons)

The task has "answer": "multi" and "parts": one {answer, program, truth,
family} per table, top to bottom (left to right).
"""
import random

import blocks
import config
import sheets


def _grid(task):
    """The task's table from its first filled row, and its program with
    the header row moved up as many rows (a sheet's empty top rows would
    merge with the empty rows between two tables)."""
    import re
    from gen import tasks as T
    s = T.sheet_from_task(task)
    rows, fmts = sheets._trim(s.rows, s.formats)
    lead = 0
    while lead < len(rows) and not any(v is not None for v in rows[lead]):
        lead += 1
    rows = rows[lead:]
    fmts = fmts[lead:] if fmts else fmts
    program = re.sub(r"^header\((\d+)\)$",
                     lambda m: "header(%d)" % (int(m.group(1)) - lead),
                     task["program"], flags=re.M)
    return rows, fmts, program


def _stack(parts, gaps):
    rows, fmts = [], []
    for k, (r, f, _) in enumerate(parts):
        if k:
            rows += [[] for _ in range(gaps[k - 1])]
            fmts += [[] for _ in range(gaps[k - 1])]
        rows += [list(x) for x in r]
        fmts += [list(x) if x else [] for x in (f or [[]] * len(r))]
    return rows, fmts


def _beside(a, b):
    (ra, fa, _), (rb, fb, _) = a, b
    width = max(len(x) for x in ra)
    n = max(len(ra), len(rb))
    rows, fmts = [], []
    for i in range(n):
        left = list(ra[i]) if i < len(ra) else []
        lf = list(fa[i] or []) if fa and i < len(fa) else []
        left += [None] * (width - len(left))
        lf += [None] * (width - len(lf))
        right = list(rb[i]) if i < len(rb) else []
        rf = list(fb[i] or []) if fb and i < len(fb) else []
        rows.append(left + [None] + right)
        fmts.append(lf + [None] + rf)
    return rows, fmts


def make(split, index):
    import gen.sheetkit as K
    from gen import tasks as T
    rng = random.Random(T.seed_of(split, index))
    reasons = []

    def fair(task):
        """A table a reader can tell from the one above it: it has a
        header row."""
        return task is not None and task["answer"] in config.TARGETS and \
            "\nheader(0)" not in task["program"]
    first = None
    for j in range(4):
        task, why = T.make_task(split + "-part", 100 * index + j)
        reasons += why
        if fair(task):
            first = task
            break
    if first is None:
        return None, reasons + ["multi:first"]
    want = rng.choice([2, 2, 3])
    parts, used = [first], {first["answer"]}
    for j in range(10, 20):
        if len(parts) == want:
            break
        kind = rng.choice([t for t in config.TARGETS if t not in used])
        task, why = T.make_task(split + "-part", 100 * index + j,
                                locale=first["locale"], kind=kind,
                                typed=first["format"] == "xlsx")
        if fair(task) and task["answer"] == kind and \
                task["format"] == first["format"]:
            parts.append(task)
            used.add(kind)
    if len(parts) < 2:
        return None, reasons + ["multi:parts"]
    grids = [_grid(p) for p in parts]
    small = all(len(r) <= 40 and max(len(x) for x in r) <= 8
                for r, _, _ in grids)
    if len(parts) == 2 and small and rng.random() < 0.35:
        rows, fmts = _beside(grids[0], grids[1])
        layout = "side_by_side"
    else:
        rows, fmts = _stack(grids, [rng.choice([1, 1, 2, 3])
                                    for _ in grids[1:]])
        layout = "stacked"
    typed = first["format"] == "xlsx"
    sheet = sheets.Sheet(first["sheet"]["name"], rows,
                         fmts if typed else None)
    answers = [p["answer"] for p in parts]
    extra = [t for t in config.TARGETS if t not in answers]
    targets = answers + (rng.sample(extra, 1) if len(answers) < 4 and
                         rng.random() < 0.5 else [])
    rng.shuffle(targets)
    # every table's program gives its rows on the table as placed (from
    # its own first row); whether blocks.split() finds the tables is what
    # the evaluation measures - a wrong cut is a wrong sheet, not a
    # dropped task
    for part, (r, f, program) in zip(parts, grids):
        res, problems = K.self_check(program, sheets.Sheet(
            sheet.name, r, f if typed else None), part["locale"], targets)
        if res is None or problems or not K.truth_matches(res,
                                                          part["truth"]):
            return None, reasons + ["multi:self_check"]
    cut = blocks.split(sheet)
    return {
        "id": "%s-%06d" % (split, index), "split": split,
        "lang": first["lang"], "locale": first["locale"],
        "activity": first["activity"], "family": "multi_table." + layout,
        "traps": [], "targets": targets, "answer": "multi",
        "format": first["format"],
        "sheet": {"name": sheet.name,
                  "rows": [[T.tag(v) for v in r] for r in rows],
                  "formats": sheet.formats},
        "preview": None, "program": None, "truth": [],
        "parts": [{"answer": p["answer"], "program": g[2],
                   "truth": p["truth"], "family": p["family"]}
                  for p, g in zip(parts, grids)],
        "cut_found": len(cut) == len(parts),
        "holdout": [], "n_rows": sum(p["n_rows"] for p in parts),
    }, reasons
