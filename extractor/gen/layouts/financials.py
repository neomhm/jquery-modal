"""
financials.py - annual accounts, income statements, balance sheets, key
figures and tax-return summaries (8 layouts).

Only the revenue lines are REVENUE (with their REVENUE_YEAR); every other
line - costs, profits, assets, equity - is O (trap T2). Two or three
years side by side are trap T3. The accountant / auditor names are O
(trap T14). The share-capital line of a balance sheet is CAPITAL.
"""
import datetime
import random
import zlib

from gen.doc import Blank, Cell, Heading, Para, Table
from gen.layouts.common import kv, layout, lines, maybe, pick, presence_ok, \
    try_
from gen.text import AText


def figures(ctx, y):
    """Plausible accounts of year y, consistent with the revenue."""
    rng = ctx.rng
    S = ctx.S
    r = S.revenue[y]
    # a stable seed per (company, year): the same figures in every
    # document of the folder (never Python's hash(), which is salted)
    rnd = random.Random(zlib.crc32(("%s|%d" % (S.legal, y)).encode("utf-8")))
    cogs = r * rnd.uniform(0.25, 0.55)
    ext = r * rnd.uniform(0.06, 0.18)
    pers = r * rnd.uniform(0.15, 0.38)
    taxes = r * rnd.uniform(0.005, 0.03)
    depr = r * rnd.uniform(0.01, 0.05)
    other = r * rnd.uniform(0.0, 0.03)
    op = r + other - cogs - ext - pers - taxes - depr
    fin = -r * rnd.uniform(0.0, 0.012)
    tax = max(0.0, (op + fin) * 0.25)
    net = op + fin - tax
    assets = r * rnd.uniform(0.4, 1.2)
    equity = assets * rnd.uniform(0.2, 0.6)
    cash = assets * rnd.uniform(0.05, 0.3)
    return {"fin_revenue": r, "fin_other_income": other,
            "fin_cost_of_sales": cogs, "fin_external_charges": ext,
            "fin_personnel_costs": pers, "fin_taxes_duties": taxes,
            "fin_depreciation": depr, "fin_operating_profit": op,
            "fin_financial_result": fin, "fin_income_tax": tax,
            "fin_net_profit": net, "fin_gross_profit": r - cogs,
            "fin_total_assets": assets, "fin_equity": equity,
            "fin_cash": cash, "fin_fixed_assets": assets * 0.4,
            "fin_current_assets": assets * 0.6,
            "fin_receivables": assets * rnd.uniform(0.1, 0.3),
            "fin_inventory": assets * rnd.uniform(0.0, 0.2),
            "fin_debts": assets * rnd.uniform(0.1, 0.4),
            "fin_payables": assets * rnd.uniform(0.05, 0.25),
            "fin_reserves": max(0.0, equity - (S.capital or 0)),
            "fin_provisions": assets * rnd.uniform(0.0, 0.05),
            "fin_total_liabilities": assets}


INCOME_ROWS = ["fin_revenue", "fin_other_income", "fin_cost_of_sales",
               "fin_gross_profit", "fin_external_charges",
               "fin_personnel_costs", "fin_taxes_duties",
               "fin_depreciation", "fin_operating_profit",
               "fin_financial_result", "fin_income_tax", "fin_net_profit"]
BALANCE_ROWS = ["fin_fixed_assets", "fin_inventory", "fin_receivables",
                "fin_cash", "fin_total_assets", "fin_share_capital",
                "fin_reserves", "fin_equity", "fin_provisions", "fin_debts",
                "fin_payables", "fin_total_liabilities"]


def _shown_years(ctx):
    """The revenue years a statement dated doc.date can show: only
    closed years (an old statement never shows later figures)."""
    ys = sorted(ctx.S.revenue)
    if ctx.doc.date is not None:
        closed = [y for y in ys if y < ctx.doc.date.year]
        ys = closed or ys[:1]
    return ys


def _years(ctx, max_years=3):
    ys = _shown_years(ctx)
    if maybe(ctx, 0.6) and len(ys) >= 2:          # T3: years side by side
        k = min(len(ys), max_years, ctx.rng.choice([2, 3]))
        ctx.doc.traps.add("T3")
        return ys[-k:][::-1]
    return [ys[-1]]


def _num_cell(ctx, value, label=None):
    v = int(round(value))
    neg = v < 0
    text = ctx.fmt.num(abs(v), 0)
    if neg:
        text = pick(ctx, ["-" + text, "(" + text + ")"])
    at = AText(text, label, {"kind": "amount", "value": float(v),
                             "currency": None} if label else None)
    raw = AText(str(v), label, {"kind": "amount", "value": float(v),
                                "currency": None} if label else None)
    return Cell(at, raw)


def _year_cell(ctx, y, header=True):
    text, truth = ctx.fmt.rev_year(y)
    at = AText(text, "REVENUE_YEAR", truth)
    if header:
        at.spans[0]["cond"] = True
    return Cell(at, AText(str(y), "REVENUE_YEAR",
                          {"kind": "year", "year": y, "fiscal": None}))


def statement_table(ctx, years, rows, capital_label=True):
    S = ctx.S
    header = [Cell(ctx.kw("fin_item"))] + [_year_cell(ctx, y) for y in years]
    table = [header]
    figs = {y: figures(ctx, y) for y in years}
    for key in rows:
        label = ctx.kw(key)
        row = [Cell(label)]
        for y in years:
            if key == "fin_share_capital":
                if not S.capital:
                    break
                row.append(_num_cell(ctx, S.capital, "CAPITAL" if
                                     capital_label else None))
            else:
                row.append(_num_cell(ctx, figs[y][key],
                                     "REVENUE" if key == "fin_revenue"
                                     else None))
        if len(row) == 1 + len(years):
            if key not in ("fin_revenue", "fin_share_capital"):
                row[0].at.mark_trap("T2")
            table.append(row)
    return Table(table)


def _header(ctx, key):
    doc = ctx.doc
    S = ctx.S
    t = ctx.title("financials", key)
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    doc.add(Heading(t))
    doc.add(Para(lines(ctx.name(S, legal=True), ctx.addr(S) if
                       maybe(ctx, 0.5) else None,
                       try_(ctx.reg_id, S) if presence_ok(ctx, S, "reg_id")
                       and maybe(ctx, 0.6) else None), prose=False))
    y = max(_shown_years(ctx))
    ctx._counts["fy"] = y
    period = ctx.phrase("phrases", "fin_period")
    if period is not None:
        doc.add(Para(period, prose=False))
    note = ctx.phrase("phrases", "fin_amounts_note")
    if note is not None:
        doc.add(Para(note, prose=False))


def _signoff(ctx):
    """Prepared by an accountant, audited by an auditor (O, T14), and
    the date of the statement (DOC_DATE)."""
    rng = ctx.rng
    orgs = ctx.lex.get("orgs") or {}
    parts = []
    auditors = orgs.get("auditor") or ["Audit {family}"]
    firm = rng.choice(auditors).format(family=ctx.plain("person").split()[-1],
                                       city=ctx.plain("city"))
    parts.append(AText(ctx.label(pick(ctx, ["fin_prepared_by",
                                            "fin_accountant"])) + firm,
                       trap="T14"))
    if maybe(ctx, 0.5):
        firm2 = rng.choice(auditors).format(
            family=ctx.plain("person").split()[-1], city=ctx.plain("city"))
        parts.append(AText(ctx.label("fin_auditor") + firm2, trap="T14"))
    place = ctx.phrase("phrases", "place_date")
    parts.append(place if place is not None else kv(ctx, "date",
                                                    ctx.doc_date()))
    return lines(*parts)


def _t1_note(ctx):
    if maybe(ctx, 0.25):
        at = ctx.say("traps", trap="T1")
        if at is not None:
            return at
    return None


# ---------------------------------------------------------------------
@layout("financials.F01", "financials")
def income_statement(ctx):
    doc = ctx.doc
    _header(ctx, "income_statement")
    years = _years(ctx)
    doc.add(statement_table(ctx, years, INCOME_ROWS))
    note = _t1_note(ctx)
    if note is not None:
        doc.add(Para(note))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


@layout("financials.F02", "financials")
def balance_and_income(ctx):
    doc = ctx.doc
    _header(ctx, "annual_accounts")
    years = _years(ctx)
    doc.add(Heading(ctx.title("financials", "balance_sheet"), level=2))
    doc.add(statement_table(ctx, years, BALANCE_ROWS))
    doc.new_page()
    doc.add(Heading(ctx.title("financials", "income_statement"), level=2))
    doc.add(statement_table(ctx, years, INCOME_ROWS))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


@layout("financials.F03", "financials")
def key_figures(ctx):
    """Rows per year: year | revenue | net profit | staff."""
    doc = ctx.doc
    S = ctx.S
    t = ctx.title("financials", "key_figures")
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    doc.add(Heading(t))
    doc.add(Para(ctx.name(S), prose=False))
    years = _shown_years(ctx)[::-1]
    if len(years) > 1:
        doc.traps.add("T3")
    rows = [[Cell(ctx.kw("year")), Cell(ctx.kw("revenue")),
             Cell(AText(ctx.kw("fin_net_profit"), trap="T2")),
             Cell(ctx.kw("staff"))]]
    for k, y in enumerate(years):
        f = figures(ctx, y)
        staff_cell = Cell("")
        if k == 0 and S.staff and presence_ok(ctx, S, "staff"):
            staff_cell = Cell(ctx.staff(S, "exact"))
        rows.append([_year_cell(ctx, y, header=False),
                     _num_cell(ctx, f["fin_revenue"], "REVENUE"),
                     _num_cell(ctx, f["fin_net_profit"]), staff_cell])
    doc.add(Table(rows))
    note = ctx.phrase("phrases", "fin_amounts_note")
    if note is not None:
        doc.add(Para(note, prose=False))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


@layout("financials.F04", "financials")
def tax_summary(ctx):
    """A tax-return summary written as label: value lines."""
    doc = ctx.doc
    S = ctx.S
    t = ctx.title("financials", "tax_summary")
    doc.meta["title_text"] = t
    doc.add(Heading(t))
    y = max(_shown_years(ctx))
    f = figures(ctx, y)
    items = [kv(ctx, "company_name", ctx.name(S, legal=True))]
    rid = try_(ctx.reg_id, S) if presence_ok(ctx, S, "reg_id") else None
    if rid is not None:
        items.append(rid)
    items.append(AText(ctx.label("fiscal_year")).add(ctx.rev_year(S, y)))
    items.append(kv(ctx, "fin_revenue", AText(ctx.fmt.num(f["fin_revenue"],
                                                          0), "REVENUE",
                                              {"kind": "amount",
                                               "value": float(int(round(
                                                   f["fin_revenue"]))),
                                               "currency": None})))
    for key in ("fin_personnel_costs", "fin_operating_profit",
                "fin_income_tax", "fin_net_profit"):
        items.append(AText(ctx.label(key) + ctx.fmt.num(f[key], 0),
                           trap="T2"))
    if S.staff and presence_ok(ctx, S, "staff") and maybe(ctx, 0.6):
        items.append(kv(ctx, "staff", ctx.staff(S, "exact")))
    doc.add(Para(lines(*items), prose=False))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


@layout("financials.F05", "financials")
def management_report(ctx):
    """Annual report prose with the figures in sentences."""
    doc = ctx.doc
    _header(ctx, "annual_accounts")
    body = []
    for cat in ("revenue", "revenue", "staff"):
        at = ctx.say(cat)
        if at is not None:
            body.append(at)
    t = ctx.say("traps", trap=pick(ctx, ["T1", "T1", "T8"]))
    if t is not None:
        body.append(t)
    f = figures(ctx, max(_shown_years(ctx)))
    body.append(AText(ctx.kw("fin_net_profit") + ctx.colon() + " " +
                      ctx.fmt.money_prose(f["fin_net_profit"])[0]
                      if f["fin_net_profit"] > 0 else
                      ctx.kw("fin_net_profit") + ctx.colon() + " -" +
                      ctx.fmt.money_prose(-f["fin_net_profit"])[0],
                      trap="T2"))
    sep = "" if ctx.lang in ("zh", "ja") else " "
    doc.add(Para(AText.join(body, sep)))
    years = _years(ctx, 2)
    doc.add(statement_table(ctx, years, INCOME_ROWS[:3] +
                            ["fin_operating_profit", "fin_net_profit"]))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


@layout("financials.F06", "financials")
def dotted_statement(ctx):
    """An income statement typed as text with dotted leaders."""
    doc = ctx.doc
    _header(ctx, "income_statement")
    years = _years(ctx)
    head = AText(ctx.kw("fin_item") + "  ")
    for k, y in enumerate(years):
        if k:
            head.add("   ")
        text, truth = ctx.fmt.rev_year(y)
        head.add(text, "REVENUE_YEAR", truth, cond=True)
    out = [head]
    figs = {y: figures(ctx, y) for y in years}
    for key in INCOME_ROWS:
        line = AText(ctx.kw(key) + " " + "." * ctx.rng.randint(3, 12) + " ")
        for k, y in enumerate(years):
            if k:
                line.add("   ")
            v = figs[y][key]
            text = ctx.fmt.num(abs(v), 0)
            if v < 0:
                text = "-" + text
            if key == "fin_revenue":
                line.add(text, "REVENUE", {"kind": "amount",
                                           "value": float(int(round(v))),
                                           "currency": None})
            else:
                line.add(text)
        if key != "fin_revenue":
            line.mark_trap("T2")
        out.append(line)
    doc.add(Para(lines(*out), prose=False))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc


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


@layout("financials.F08", "financials")
def simplified_accounts(ctx):
    """Small-business accounts: one year, few lines, average staff."""
    doc = ctx.doc
    _header(ctx, "annual_accounts")
    y = max(_shown_years(ctx))
    doc.add(statement_table(ctx, [y], ["fin_revenue", "fin_cost_of_sales",
                                       "fin_external_charges",
                                       "fin_personnel_costs",
                                       "fin_net_profit"]))
    S = ctx.S
    if S.staff and presence_ok(ctx, S, "staff"):
        doc.add(Para(kv(ctx, "staff", ctx.staff(S)), prose=False))
    doc.add(Para(_signoff(ctx), prose=False))
    return doc
