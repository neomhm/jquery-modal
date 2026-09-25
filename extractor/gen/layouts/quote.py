"""
quote.py - quotes, estimates and pro-forma invoices (8 layouts).

Like an invoice: the lines are SERVICE / PRICE / LINE_TOTAL, the final
amount is DOC_TOTAL and the issue date is DOC_DATE. The validity date is
O (like a due date).
"""
import datetime

from gen.doc import Blank, Cell, Columns, Heading, Para, Table
from gen.layouts.common import (amount_words, bank_block, footer_line,
                                id_lines, invoice_data, items_lines,
                                items_table, kv, layout, legal_footer, lines,
                                maybe, money_cell, org_block, page_line_fn,
                                pick, presence_ok, signature, totals_lines,
                                totals_rows, try_)
from gen.text import AText


def _setup(ctx, key=None):
    doc = ctx.doc
    doc.meta["footer_line"] = footer_line(ctx)
    doc.meta["page_line"] = page_line_fn(ctx)
    t = ctx.title("doc", key or "quote")
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    return t


def _quote_data(ctx, **kw):
    inv = invoice_data(ctx, **kw)
    inv["number"] = ctx.doc_number("quote")
    inv["valid"] = ctx.doc.date + datetime.timedelta(
        days=ctx.rng.choice([15, 30, 30, 60, 90]))
    return inv


def _head(ctx, inv, title):
    out = [AText(title + " ").add(AText(inv["number"], trap="T6")),
           kv(ctx, "date", ctx.doc_date()),
           AText(ctx.label("valid_until") + ctx.date_o(inv["valid"]),
                 trap="T15")]
    return lines(*out)


def _customer(ctx, concept="buyer", **kw):
    return org_block(ctx, ctx.C, concept, contact=False,
                     ids=not isinstance(ctx.C, dict), **kw)


def _closing(ctx):
    out = []
    for key in ("quote_validity", "quote_acceptance"):
        at = ctx.phrase("invoice_notes", key)
        if at is not None:
            out.append(at)
    return lines(*out) if out else None


@layout("quote.Q01", "quote")
def classic_quote(ctx):
    doc, inv = ctx.doc, _quote_data(ctx)
    title = _setup(ctx)
    doc.add(Columns(org_block(ctx, ctx.S, None, person=True),
                    _customer(ctx)))
    doc.add(Heading(title))
    doc.add(Para(_head(ctx, inv, ctx.kw("quote_no")), prose=False))
    doc.add(items_table(ctx, inv))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    foot = legal_footer(ctx)
    if foot is not None:
        doc.add(Para(foot))
    return doc


@layout("quote.Q02", "quote")
def estimate_with_intro(ctx):
    doc, inv = ctx.doc, _quote_data(ctx)
    title = _setup(ctx)
    doc.add(Para(lines(ctx.name(ctx.S), ctx.addr(ctx.S, multiline=True)),
                 prose=False))
    doc.add(Para(_customer(ctx, "bill_to"), prose=False))
    doc.add(Heading(title))
    doc.add(Para(_head(ctx, inv, ctx.kw("quote_no")), prose=False))
    intro = ctx.say("services_intro")
    if intro is not None:
        doc.add(Para(intro))
    doc.add(items_table(ctx, inv, cols=["description", "qty", "unit",
                                        "unit_price", "amount"]))
    doc.add(Para(totals_lines(ctx, inv, total_concept="total_incl"),
                 prose=False))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    sig = signature(ctx)
    if sig is not None:
        doc.add(Para(sig, prose=False))
    return doc


@layout("quote.Q03", "quote")
def proforma(ctx):
    doc, inv = ctx.doc, _quote_data(ctx)
    title = _setup(ctx, "proforma")
    doc.add(Heading(title))
    doc.add(Para(org_block(ctx, ctx.S, "seller"), prose=False))
    doc.add(Para(_customer(ctx, "buyer"), prose=False))
    doc.add(Para(lines(AText(ctx.label("reference") + inv["number"],
                             trap="T6"),
                       kv(ctx, "date", ctx.doc_date())), prose=False))
    table = items_table(ctx, inv)
    table.rows.extend(totals_rows(ctx, inv, max(2, len(table.rows[0]))))
    doc.add(table)
    if maybe(ctx, 0.7):
        doc.add(Para(bank_block(ctx), prose=False))
    return doc


@layout("quote.Q04", "quote")
def compact_estimate(ctx):
    doc, inv = ctx.doc, _quote_data(ctx, n_lines=pick(ctx, [1, 2, 3]))
    title = _setup(ctx)
    head = AText.join([ctx.name(ctx.S), ctx.addr(ctx.S)], " – ")
    doc.add(Para(head, prose=False))
    doc.add(Para(_head(ctx, inv, title), prose=False))
    doc.add(Para(AText(ctx.label("buyer")).add(ctx.name(ctx.C)),
                 prose=False))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    return doc


@layout("quote.Q05", "quote")
def two_column_options(ctx):
    """Quote with a basic offer and an option table."""
    doc, inv = ctx.doc, _quote_data(ctx)
    title = _setup(ctx)
    doc.add(Heading(title))
    doc.add(Columns(lines(ctx.name(ctx.S), ctx.addr(ctx.S, multiline=True),
                          id_lines(ctx, ctx.S, max_ids=1)),
                    _customer(ctx, "buyer")))
    doc.add(Para(_head(ctx, inv, ctx.kw("quote_no")), prose=False))
    doc.add(items_table(ctx, inv, cols=["no", "description", "qty",
                                        "unit_price", "amount"]))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    services = ctx.S.services or []
    if len(services) > 3:
        rows = [[Cell(ctx.kw("description")), Cell(ctx.kw("unit_price"))]]
        for s in ctx.rng.sample(services, min(3, len(services))):
            rows.append([Cell(ctx.service(s["name"])),
                         money_cell(ctx, s["price"], "PRICE", "doc")])
        doc.add(Table(rows))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    return doc


@layout("quote.Q06", "quote")
def works_in_lots(ctx):
    """A building-trade quote in lots, each with its own subtotal (O);
    only the grand total is DOC_TOTAL."""
    doc, inv = ctx.doc, _quote_data(ctx, n_lines=pick(ctx, [4, 5, 6]),
                                    allow_extras=False)
    title = _setup(ctx)
    doc.add(Para(org_block(ctx, ctx.S, None, person=True), prose=False))
    doc.add(Para(_customer(ctx), prose=False))
    doc.add(Heading(title))
    doc.add(Para(_head(ctx, inv, ctx.kw("quote_no")), prose=False))
    items = inv["items"]
    half = max(1, len(items) // 2)
    for k, part in enumerate([items[:half], items[half:]], start=1):
        if not part:
            continue
        doc.add(Heading("%s %d" % (ctx.kw("reference"), k), level=2))
        sub = dict(inv, items=part, extras=[])
        doc.add(items_table(ctx, sub, cols=["description", "qty", "unit",
                                            "unit_price", "amount"]))
        value = round(sum(i["amount"] for i in part), inv["decimals"])
        doc.add(Para(kv(ctx, "subtotal", ctx.money(value)), prose=False))
    doc.add(Para(totals_lines(ctx, inv, total_concept="total_incl"),
                 prose=False))
    dep = ctx.phrase("invoice_notes", "payment_terms")
    if dep is not None:
        doc.add(Para(dep))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    return doc


@layout("quote.Q07", "quote")
def subscription_plans(ctx):
    """Monthly plans (PRICE per month) and the first-year total."""
    doc = ctx.doc
    inv = _quote_data(ctx, n_lines=pick(ctx, [1, 2]), allow_extras=False)
    title = _setup(ctx)
    for item in inv["items"]:
        item["qty"] = 12
        item["unit"] = "month"
        item["amount"] = round(item["price"] * 12, inv["decimals"])
    inv["subtotal"] = round(sum(i["amount"] for i in inv["items"]),
                            inv["decimals"])
    inv["tax"] = round(inv["subtotal"] * inv["rate"] / 100, inv["decimals"])
    inv["total"] = round(inv["subtotal"] + inv["tax"], inv["decimals"])
    doc.add(Heading(title))
    doc.add(Para(lines(ctx.name(ctx.S), contact_or_addr(ctx)), prose=False))
    doc.add(Para(AText(ctx.label("buyer")).add(ctx.name(ctx.C)),
                 prose=False))
    doc.add(Para(_head(ctx, inv, ctx.kw("quote_no")), prose=False))
    doc.add(items_table(ctx, inv, cols=["description", "unit_price", "qty",
                                        "amount"]))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    return doc


def contact_or_addr(ctx):
    from gen.layouts.common import contact_lines
    cl = contact_lines(ctx, ctx.S, one_line=True)
    return cl if cl is not None else ctx.addr(ctx.S)


@layout("quote.Q08", "quote")
def email_quote(ctx):
    """An offer sent by e-mail: greeting, lines, total, signature."""
    doc, inv = ctx.doc, _quote_data(ctx, n_lines=pick(ctx, [1, 2, 3]))
    _setup(ctx)
    rng = ctx.rng
    head = [AText(ctx.kw("em_from") + ": ").add(ctx.name(ctx.S)),
            AText(ctx.kw("em_date") + ": ").add(ctx.doc_date())]
    if not isinstance(ctx.C, dict):
        head.insert(1, AText(ctx.kw("em_to") + ": ").add(ctx.name(ctx.C)))
    subj = ctx.phrase("letters", "quote_followup", "subject")
    if subj is not None:
        head.append(AText(ctx.kw("em_subject") + ": ").add(subj))
    doc.add(Para(lines(*head), prose=False))
    sal = ctx.lex.get("kw", {}).get("lt_salutation") or ["Hello,"]
    doc.add(Para(AText(rng.choice(sal)), prose=False))
    intro = ctx.say("services_intro")
    if intro is not None:
        doc.add(Para(intro))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    closing = _closing(ctx)
    if closing is not None:
        doc.add(Para(closing))
    close = ctx.lex.get("kw", {}).get("lt_closing") or ["Regards,"]
    doc.add(Para(AText(rng.choice(close)), prose=False))
    sig = signature(ctx)
    if sig is not None:
        doc.add(Para(sig, prose=False))
    return doc
