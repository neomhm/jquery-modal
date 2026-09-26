"""
gen/b_ledger.py - the invoice_ledger builder: a register of invoices with
a number, a date, the client, the total (with tax when both are shown),
the tax, a status word, due and paid dates. Credit notes have negative
amounts; monthly subtotal rows are left out by the program.
"""
import datetime
import math

import helpers as H
from gen import b_bookings as BK
from gen import columns as C
from gen import modifiers as M
from gen.b_people import date_column
from gen.sheetkit import Column, Table

REF = datetime.date(2026, 6, 30)


def number_maker(ctx):
    rng = ctx.rng
    year = REF.year - rng.choice([0, 0, 1])
    style = rng.choice(["F{y}-{n:04d}", "INV-{n:05d}", "{y}/{n:03d}",
                        "FA{yy}{n:04d}", "{n}", "{y}-{n:04d}", "N{n:06d}"])
    start = rng.randint(1, 900)

    def make(i, credit=False):
        n = start + i
        text = style.format(y=year, yy=year % 100, n=n)
        if credit:
            prefix = rng.choice(["AV-", "CN-", "C-", "R-"])
            text = prefix + text
        return text
    return make


def ledger_records(ctx, n, credit_notes=False):
    rng = ctx.rng
    clients = [ctx.company() for _ in range(rng.randint(3, 15))]
    clients = [c for c in clients if c] or ["-"]
    make = number_maker(ctx)
    vat = ctx.vat()
    cents = ctx.loc["cents"]
    rate = ctx.loc["usd_rate"] * ctx.loc["price_level"]
    days = sorted(rng.randint(0, 360) for _ in range(n))
    terms = rng.choice([15, 30, 30, 45, 60])
    out = []
    credit_i = 0
    for i, back in enumerate(reversed(days)):
        date = REF - datetime.timedelta(days=back)
        credit = credit_notes and i > 0 and rng.random() < 0.12
        usd = math.exp(rng.uniform(math.log(40), math.log(6000)))
        excl = round(usd * rate, 2 if cents else 0)
        if excl <= 0:
            excl = 1.0
        tax = round(excl * vat, 2 if cents else 0)
        incl = round(excl + tax, 2 if cents else 0)
        due = date + datetime.timedelta(days=terms)
        age = (REF - date).days
        if credit:
            excl, tax, incl = -excl, -tax, -incl
            status = rng.choice(["paid", "cancelled", "paid"])
        elif age > terms + 20:
            status = rng.choices(["paid", "overdue", "cancelled",
                                  "partial"], [85, 7, 4, 4])[0]
        elif age > terms:
            status = rng.choices(["paid", "overdue", "partial"],
                                 [60, 30, 10])[0]
        else:
            status = rng.choices(["unpaid", "paid", "partial"],
                                 [60, 30, 10])[0]
        paid = None
        if status == "paid":
            paid = date + datetime.timedelta(days=rng.randint(0, terms + 15))
            if paid > REF:
                paid = REF
        out.append({"number": make(i if not credit else credit_i,
                                   credit=credit),
                    "date": date, "client": rng.choice(clients),
                    "excl": float(excl), "tax": float(tax),
                    "incl": float(incl), "status": status, "due": due,
                    "paid": paid, "credit": credit})
        if credit:
            credit_i += 1
    numbers = [r["number"] for r in out]
    if len(set(numbers)) != len(numbers):
        return []
    return out


def money_cells(ctx, amounts, show):
    """Amounts (maybe negative) in the sheet's style, each read back with
    amount(). -> (cells, fmts) or None."""
    f, rng = ctx.fmt, ctx.rng
    mode = C.digit_mode(ctx)
    accounting = rng.random() < 0.3
    cells, fmts = [], []
    for a in amounts:
        if a is None:
            cells.append(None)
            fmts.append(None)
            continue
        if f.typed:
            v, fm = f.money(a, fmt_currency=(show == "format"))
        else:
            v, fm = f.money(abs(a), symbol=(show == "cell"))
            if a < 0:
                v = "(%s)" % v if accounting else "-" + v
            v = C.apply_digits(ctx, v, mode)
        if H.amount(v, ctx.code) != (True, round(float(a), 6)):
            return None
        cells.append(v)
        fmts.append(fm)
    return cells, fmts, (mode if not f.typed else None)


def invoice_ledger(ctx, plan, *, two_totals=False, status=None,
                   due_paid=False, credit_notes=False, monthly=False,
                   currency_header=False, title=False, export=False):
    rng = ctx.rng
    traps = set(plan["traps"])
    if title:
        traps.add("T5")
    if currency_header:
        traps.add("T13")
    if monthly:
        traps.add("T4")
    plan = dict(plan, traps=traps)
    recs = ledger_records(ctx, plan["n"], credit_notes=credit_notes)
    if len(recs) < 3:
        return None
    t = Table("invoice_ledger")
    truth = [{} for _ in recs]
    C.text_column(ctx, t, "number", ctx.header("invoice_number"),
                  [r["number"] for r in recs], "number", truth, noise=False,
                  digits=False)
    if not date_column(ctx, t, "date", ctx.header("invoice_date"),
                       [r["date"] for r in recs], "date", truth):
        return None
    if any("date" not in rec for rec in truth):
        return None
    t.blocks.append(["number", "date"] if rng.random() < 0.7
                    else ["date", "number"])
    t.first_column_fixed = ["number"] if rng.random() < 0.6 else []
    if export or rng.random() < 0.9:
        C.text_column(ctx, t, "client", ctx.header("invoice_client"),
                      [r["client"] for r in recs], "client", truth,
                      digits=False)
    # ---- the amounts and where the currency shows
    typed = ctx.typed
    t13 = "T13" in traps
    if t13:
        show = "format" if typed and rng.random() < 0.5 else "none"
        header_cur = show == "none" or rng.random() < 0.4
    else:
        show = rng.choice(["cell", "none", "none"]) if not typed else \
            rng.choice(["none", "none", "format"])
        header_cur = False
        if show == "format":
            t.traps.add("T13")

    shown = ["incl"]
    if two_totals or export or rng.random() < 0.25:
        shown = rng.choice([["excl", "tax", "incl"], ["excl", "incl"],
                            ["excl", "tax", "incl"]])
    keys = {"excl": "total_excl", "tax": "tax_amount", "incl": "total_incl"}
    total_key = "amt_incl"
    for part in shown:
        hkey = keys[part] if len(shown) > 1 else "total"
        header = C.header_with_cur(ctx, hkey) if header_cur and \
            part == "incl" else None
        if header_cur and part == "incl" and header is None:
            header_cur = False
            if show == "none":
                show = "cell" if not typed else "format"
        header = header or ctx.header(hkey, cur=False)
        got = money_cells(ctx, [r[part] for r in recs], show)
        if got is None:
            return None
        cells, fmts, mode = got
        col = "amt_" + part
        added = t.add(Column(col, header, cells, fmts))
        added.symbol = show == "cell" and not typed
        added.digits_done, added.digit_mode = True, mode
        if part == "incl":
            t.outs.append(("total", "amount(col({%s}))" % col))
            for rec, r in zip(truth, recs):
                rec["total"] = r["incl"]
        elif part == "tax":
            t.outs.append(("tax", "amount(col({%s}))" % col))
            for rec, r in zip(truth, recs):
                rec["tax"] = r["tax"]
    # a header that shows a currency is always used (the model sees it)
    ok, cur = H.currency(t.col(total_key).header, ctx.code)
    if ok and cur != ctx.loc["currency"]:
        return None
    header_cur = ok
    t.blocks.append(["amt_" + p for p in shown])
    sources = []
    if show == "cell" and not typed:
        sources.append("currency(col({%s}))" % total_key)
    if show == "format" and typed:
        sources.append("currency(format_of({%s}))" % total_key)
    if header_cur:
        sources.append("currency(header_of({%s}))" % total_key)
        if show != "cell":
            t.traps.add("T13")
    if sources:
        expr = sources[0] if len(sources) == 1 else \
            "first(%s)" % ", ".join(sources)
        t.outs.append(("currency", expr))
        for rec in truth:
            rec["currency"] = ctx.loc["currency"]
    # ---- status, due and paid dates
    if status is None:
        status = "T12" in traps
    if status:
        BK.status_column(ctx, t, "status", ctx.header("invoice_status"),
                         [r["status"] for r in recs], "status", truth,
                         "invoice_status")
    if due_paid or export or rng.random() < 0.3:
        date_column(ctx, t, "due", ctx.header("due_date"),
                    [r["due"] for r in recs], "due_date", truth)
    if due_paid or export or rng.random() < 0.2:
        if any(r["paid"] for r in recs):
            date_column(ctx, t, "paid", ctx.header("paid_date"),
                        [r["paid"] for r in recs], "paid_date", truth)
    t.truth = truth
    # ---- modifiers: monthly subtotals, totals, notes...
    label_key = "client" if t.has("client") else "number"
    groups = None
    months = {}
    for i, r in enumerate(recs):
        months.setdefault((r["date"].year, r["date"].month), []).append(i)
    if monthly and len(months) >= 2 and (len(months) + 1) <= 0.25 * len(recs):
        groups = []
        for (y, m), idx in sorted(months.items()):
            groups.append((ctx.fmt.month_name(m), idx))
    elif monthly:
        return None
    amounts = {total_key: [r["incl"] for r in recs]}
    spec = {"label_key": label_key, "sum_keys": [total_key],
            "amounts_of": amounts, "groups": groups}
    M.decorate(ctx, t, plan, text_keys=[k for k in ("client",)
                                        if t.has(k)],
               totals_spec=None if monthly else spec)
    if monthly:
        M.totals(ctx, t, force_groups=True, **spec)
    return t
