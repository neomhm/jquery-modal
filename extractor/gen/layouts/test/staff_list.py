"""
Held-out TEST layouts from staff_list.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import staff_list as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("staff_list.S01", "staff_list")
def staff_table(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    doc.add(Heading(title))
    doc.add(Para(ctx.name(ctx.S), prose=False))
    rows = [[Cell(ctx.kw("sl_name")), Cell(ctx.kw("sl_position")),
             Cell(ctx.kw("sl_department")), Cell(ctx.kw("sl_start_date"))]]
    for e in _people(ctx):
        start = datetime.date(ctx.rng.randint(2005, 2025),
                              ctx.rng.randint(1, 12), ctx.rng.randint(1, 28))
        dept = e[3] if len(e) > 3 else (ctx.lst("departments") or [""])[0]
        rows.append([_name_cell(ctx, e), Cell(e[2]), Cell(dept),
                     Cell(ctx.date_o(start),
                          AText(ctx.fmt.date(start, "sheet")[0]))])
    doc.add(Table(rows))
    tot = _total(ctx)
    if tot is not None:
        doc.add(Para(tot, prose=False))
    return doc
