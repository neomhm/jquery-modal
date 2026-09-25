"""
Held-out TEST layouts from financials.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import financials as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("financials.F07", "financials")
def comparison_with_growth(ctx):
    doc = ctx.doc
    _header(ctx, "key_figures")
    years = _shown_years(ctx)[-2:][::-1]
    doc.traps.add("T3")
    figs = {y: figures(ctx, y) for y in years}
    rows = [[Cell(ctx.kw("fin_item"))] + [_year_cell(ctx, y) for y in years]
            + [Cell("%")]]
    for key in ("fin_revenue", "fin_gross_profit", "fin_operating_profit",
                "fin_net_profit", "fin_equity"):
        a, b = figs[years[0]][key], figs[years[-1]][key]
        growth = (a - b) / abs(b) * 100 if b else 0
        row = [Cell(AText(ctx.kw(key), trap=None if key == "fin_revenue"
                          else "T2"))]
        for y in years:
            row.append(_num_cell(ctx, figs[y][key], "REVENUE" if key ==
                                 "fin_revenue" else None))
        row.append(Cell(ctx.fmt.percent(round(growth, 1))))
        rows.append(row)
    doc.add(Table(rows))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc
