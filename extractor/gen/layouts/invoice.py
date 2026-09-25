"""
invoice.py - invoices (12 layouts), receipts (3) and credit notes (2).

The subject S is the issuer (the business on its sales invoices, a
supplier on purchase invoices); C is the customer: an organisation
(C_NAME ...) or a private person (plain text, rule R9).
"""
import datetime

from gen.doc import Blank, Cell, Columns, Heading, Para, Table
from gen.layouts.common import (amount_words, bank_block, contact_lines,
                                dates_block, footer_line, id_lines,
                                invoice_data, items_lines, items_table, kv,
                                layout, legal_footer, lines, maybe,
                                money_cell, org_block, page_line_fn,
                                payment_terms, pick, presence_ok,
                                signature, totals_lines, totals_rows, try_)
from gen.text import AText


def _setup(ctx, kind="invoice", title_key=None):
    doc = ctx.doc
    doc.meta["footer_line"] = footer_line(ctx)
    doc.meta["page_line"] = page_line_fn(ctx)
    key = title_key or pick(ctx, ["invoice", "invoice", "tax_invoice"]
                            if kind == "invoice" else [kind])
    t = ctx.title("doc", key)
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    return t


def _words_wanted(ctx):
    return maybe(ctx, ctx.loc.get("amount_in_words", 0.1) *
                 ctx.rules.get("trap_boost", 1.0))


def _customer(ctx, concept=None, **kw):
    return org_block(ctx, ctx.C, concept or pick(ctx, ["bill_to", "bill_to",
                                                       "buyer"]),
                     contact=False, ids=not isinstance(ctx.C, dict), **kw)


def _notes(ctx, inv):
    out = []
    if inv["exempt"]:
        out.append(ctx.phrase("invoice_notes", "vat_exempt"))
    pt = payment_terms(ctx)
    if pt is not None:
        out.append(pt)
    if maybe(ctx, 0.3) and ctx.country == "FR":
        out.append(ctx.phrase("invoice_notes", "late_penalty"))
    if maybe(ctx, 0.4):
        out.append(ctx.phrase("invoice_notes", "thanks"))
    return lines(*[o for o in out if o is not None]) if any(
        o is not None for o in out) else None


# ---------------------------------------------------------------------
@layout("invoice.L01", "invoice")
def classic_two_columns(ctx):
    """Title, number and date; seller | customer side by side; lines;
    totals; payment terms; bank details; legal footer."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    doc.add(Heading(title))
    doc.add(Para(dates_block(ctx, inv), prose=False))
    doc.add(Columns(org_block(ctx, ctx.S, None, person=True),
                    _customer(ctx)))
    doc.add(items_table(ctx, inv))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    if _words_wanted(ctx):
        aw = amount_words(ctx, inv["total"])
        if aw is not None:
            doc.add(Para(aw))
    notes = _notes(ctx, inv)
    if notes is not None:
        doc.add(Para(notes))
    if maybe(ctx, 0.6):
        doc.add(Para(bank_block(ctx), prose=False))
    foot = legal_footer(ctx)
    if foot is not None:
        doc.add(Para(foot))
    return doc


@layout("invoice.L02", "invoice")
def title_first_stacked(ctx):
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    doc.add(Para(org_block(ctx, ctx.S, "seller", person=True),
                 prose=False))
    doc.add(Heading(title))
    doc.add(Para(_customer(ctx), prose=False))
    doc.add(Para(dates_block(ctx, inv), prose=False))
    table = items_table(ctx, inv, with_rate=True)
    width = len(table.rows[0])
    table.rows.extend(totals_rows(ctx, inv, max(2, width)))
    doc.add(table)
    if _words_wanted(ctx):
        aw = amount_words(ctx, inv["total"])
        if aw is not None:
            doc.add(Para(aw))
    notes = _notes(ctx, inv)
    if notes is not None:
        doc.add(Para(notes))
    return doc


@layout("invoice.L03", "invoice")
def compact_text(ctx):
    """A small invoice written as lines, no table."""
    doc, inv = ctx.doc, invoice_data(ctx, n_lines=pick(ctx, [1, 2, 3]))
    title = _setup(ctx)
    rng = ctx.rng
    head = AText.join([ctx.name(ctx.S), ctx.addr(ctx.S)],
                      rng.choice([" – ", ", ", " | "]))
    tel = try_(ctx.phone, ctx.S) if presence_ok(ctx, ctx.S, "phone") \
        else None
    if tel is not None:
        head.add(" – ").add(tel)
    doc.add(Para(head, prose=False))
    first = AText(title + " ").add(AText(inv["number"], trap="T6"))
    first.add(" – ").add(ctx.doc_date())
    doc.add(Para(first, prose=False))
    cust = AText(ctx.label("bill_to"))
    cust.add(ctx.name(ctx.C))
    if not isinstance(ctx.C, dict) and maybe(ctx, 0.5):
        cust.add(", ").add(ctx.addr(ctx.C))
    doc.add(Para(cust, prose=False))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    due = AText(ctx.label("due_date") + ctx.date_o(inv["due_date"]),
                trap="T15")
    doc.add(Para(due, prose=False))
    idl = id_lines(ctx, ctx.S)
    if idl is not None:
        doc.add(Para(idl, prose=False))
    return doc


@layout("invoice.L04", "invoice")
def tax_invoice_detailed(ctx):
    """Tax invoice with registration numbers of both parties, item codes,
    tax breakdown, amount in words and an authorised signatory."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx, title_key="tax_invoice")
    rng = ctx.rng
    doc.add(Heading(title))
    doc.add(Para(org_block(ctx, ctx.S, None, contact=True, ids=True),
                 prose=False))
    doc.add(Para(dates_block(ctx, inv), prose=False))
    doc.add(Para(_customer(ctx, "buyer"), prose=False))
    doc.add(items_table(ctx, inv, cols=pick(ctx, [
        ["no", "description", "code", "qty", "unit_price", "amount"],
        ["no", "code", "description", "qty", "unit", "unit_price", "rate",
         "amount"]])))
    tl = []
    tl.append(kv(ctx, "total_excl", ctx.money(inv["subtotal"])))
    if inv["tax"]:
        if ctx.country == "IN":
            half = round(inv["tax"] / 2, inv["decimals"])
            rate = inv["rate"] / 2
            tl.append(AText("CGST %s: %s" % (ctx.fmt.percent(rate),
                                             ctx.money(half).text),
                            trap="T6"))
            tl.append(AText("SGST %s: %s" % (ctx.fmt.percent(rate),
                                             ctx.money(half).text),
                            trap="T6"))
        else:
            tl.append(AText(ctx.label("total_tax") +
                            ctx.money(inv["tax"]).text, trap="T6"))
    tl.append(kv(ctx, "total_payable", ctx.money(inv["total"], "DOC_TOTAL"))
              .mark_trap("T1"))
    doc.add(Para(lines(*tl), prose=False))
    aw = amount_words(ctx, inv["total"])
    if aw is not None:
        doc.add(Para(aw))
    doc.add(Para(bank_block(ctx), prose=False))
    sig = signature(ctx)
    if sig is not None:
        doc.add(Para(sig, prose=False))
    return doc


@layout("invoice.L05", "invoice")
def party_tables(ctx):
    """Buyer and seller as label/value tables (fapiao-like), then the
    lines, then the total in words and in figures."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    doc.add(Heading(title))
    top = [AText(ctx.label("invoice_no")).add(AText(inv["number"],
                                                    trap="T6")),
           kv(ctx, "invoice_date", ctx.doc_date())]
    doc.add(Para(lines(*top), prose=False))

    def party(org, concept):
        rows = [[Cell(ctx.kw(concept)), Cell("")]]
        rows.append([Cell(ctx.kw("company_name")), Cell(ctx.name(org))])
        if not isinstance(org, dict):
            rid = try_(ctx.reg_id, org, None, False)
            if rid is not None and presence_ok(ctx, org, "reg_id"):
                rows.append([Cell(ctx.kw("tax_id")), Cell(rid)])
            addr = ctx.addr(org)
            tel = try_(ctx.phone, org) if ctx.role(org) == "S" else None
            if tel is not None and presence_ok(ctx, org, "phone"):
                addr.add(" ").add(tel)
            rows.append([Cell(ctx.kw("address")), Cell(addr)])
            if ctx.role(org) == "S" and maybe(ctx, 0.6):
                rows.append([Cell(ctx.kw("bank")),
                             Cell(bank_block(ctx).text.replace("\n", " "))])
        return Table(rows)
    doc.add(party(ctx.C, "buyer"))
    doc.add(items_table(ctx, inv, cols=["description", "unit", "qty",
                                        "unit_price", "amount", "rate"]))
    words = amount_words(ctx, inv["total"])
    total_row = [Cell(ctx.kw("total_payable")),
                 Cell(words if words is not None else ""),
                 money_cell(ctx, inv["total"], "DOC_TOTAL", "doc")]
    doc.add(Table([[Cell(ctx.kw("subtotal")), Cell(ctx.kw("vat")),
                    Cell(ctx.kw("total"))],
                   [money_cell(ctx, inv["subtotal"]),
                    money_cell(ctx, inv["tax"]),
                    money_cell(ctx, inv["total"], "DOC_TOTAL")],
                   total_row]))
    doc.add(party(ctx.S, "seller"))
    return doc


@layout("invoice.L06", "invoice")
def customer_first(ctx):
    """Customer at the top left, issuer at the right; the amount due
    comes before the lines (Japanese style)."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    rng = ctx.rng
    doc.add(Heading(title))
    cust = AText()
    cust.add(ctx.name(ctx.C))
    if ctx.lang == "ja":
        cust.add(" 御中" if not isinstance(ctx.C, dict) else " 様")
    elif ctx.lang == "ko":
        cust.add(" 귀하")
    cust2 = lines(cust, None if isinstance(ctx.C, dict) or maybe(ctx, 0.5)
                  else ctx.addr(ctx.C))
    right = lines(dates_block(ctx, inv, show_due=False),
                  org_block(ctx, ctx.S, None, ids=True))
    doc.add(Columns(cust2, right))
    due_line = AText(ctx.label(pick(ctx, ["total_payable", "total_incl"])))
    due_line.add(ctx.money(inv["total"], "DOC_TOTAL"))
    due_line.mark_trap("T1")
    doc.add(Para(due_line, prose=False))
    doc.add(Para(AText(ctx.label("due_date") +
                       ctx.date_o(inv["due_date"]), trap="T15"),
                 prose=False))
    table = items_table(ctx, inv)
    table.rows.extend(totals_rows(ctx, inv, max(2, len(table.rows[0]))))
    doc.add(table)
    doc.add(Para(bank_block(ctx), prose=False))
    return doc


@layout("invoice.L07", "invoice")
def party_grid(ctx):
    """One grid with the supplier and the customer side by side (label,
    supplier value, label, customer value), then the lines."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    doc.add(Heading(title))
    doc.add(Para(kv(ctx, "invoice_date", ctx.doc_date()), prose=False))
    S, C = ctx.S, ctx.C
    rows = [[Cell(ctx.kw("seller")), Cell(""), Cell(ctx.kw("buyer")),
             Cell("")]]
    rid_s = try_(ctx.reg_id, S, None, False) if presence_ok(ctx, S,
                                                            "reg_id") \
        else None
    rid_c = try_(ctx.reg_id, C, None, False) if not isinstance(C, dict) \
        else None
    rows.append([Cell(ctx.kw("registration_no")), Cell(rid_s or ""),
                 Cell(ctx.kw("registration_no")), Cell(rid_c or "")])
    rows.append([Cell(ctx.kw("company_name")), Cell(ctx.name(S)),
                 Cell(ctx.kw("company_name")), Cell(ctx.name(C))])
    if presence_ok(ctx, S, "manager"):
        rows.append([Cell(ctx.kw("manager")), Cell(ctx.person(S)),
                     Cell(ctx.kw("manager")),
                     Cell(C.manager["full"] if not isinstance(C, dict)
                          else "")])
    rows.append([Cell(ctx.kw("address")), Cell(ctx.addr(S)),
                 Cell(ctx.kw("address")),
                 Cell(ctx.addr(C) if not isinstance(C, dict) else
                      AText(C["address"]["one"]))])
    act = try_(ctx.activity, S) if presence_ok(ctx, S, "activity") \
        else None
    if act is not None and maybe(ctx, 0.6):
        rows.append([Cell(ctx.kw("activity")), Cell(act), Cell(""),
                     Cell("")])
    doc.add(Table(rows))
    doc.add(items_table(ctx, inv, cols=["description", "qty", "unit_price",
                                        "amount"]))
    doc.add(Para(totals_lines(ctx, inv, total_concept="total_payable"),
                 prose=False))
    if _words_wanted(ctx):
        aw = amount_words(ctx, inv["total"])
        if aw is not None:
            doc.add(Para(aw))
    doc.add(Para(AText(ctx.label("due_date") + ctx.date_o(inv["due_date"]),
                       trap="T15"), prose=False))
    return doc


@layout("invoice.L08", "invoice")
def bank_first(ctx):
    """Bank details of the supplier first, then 'Invoice No. .. of ..',
    supplier and buyer on one line each, lines, totals, count of items
    with the total in figures and in words, signatures."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    rng = ctx.rng
    doc.add(Para(bank_block(ctx), prose=False))
    head = AText(title + " № ").add(AText(inv["number"], trap="T6"))
    head.add({"ru": " от ", "fr": " du ", "es": " del ", "it": " del ",
              "en": " dated "}.get(ctx.lang, " "))
    head.add(ctx.doc_date(style="long" if maybe(ctx, 0.5) else None))
    doc.add(Heading(head))

    def one_line(org, concept):
        out = AText(ctx.label(concept))
        parts = [ctx.name(org)]
        if not isinstance(org, dict):
            rid = try_(ctx.reg_id, org) if presence_ok(ctx, org, "reg_id") \
                else None
            if rid is not None:
                parts.append(rid)
            parts.append(ctx.addr(org))
        else:
            parts.append(AText(org["address"]["one"]))
        out.add(AText.join(parts, ", "))
        return out
    doc.add(Para(one_line(ctx.S, "seller"), prose=False))
    doc.add(Para(one_line(ctx.C, "buyer"), prose=False))
    doc.add(items_table(ctx, inv, cols=["no", "description", "qty", "unit",
                                        "unit_price", "amount"]))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    count = AText("%d, " % len(inv["items"]))
    count.add(ctx.money(inv["total"], "DOC_TOTAL"))
    doc.add(Para(AText(ctx.kw("total") + " ").add(count), prose=False))
    aw = amount_words(ctx, inv["total"])
    if aw is not None:
        doc.add(Para(aw))
    sig = []
    if presence_ok(ctx, ctx.S, "manager"):
        sig.append(AText(ctx.S.manager_title + " ____ ").add(
            ctx.person(ctx.S, short=True)))
    sig.append(AText(ctx.rng.choice(ctx.lst("positions") or ["-"]) +
                     " ____ " + ctx.plain("person"), trap="T11"))
    doc.add(Para(lines(*sig), prose=False))
    return doc


@layout("invoice.L09", "invoice")
def us_style(ctx):
    """Name and contact at the top, INVOICE, Bill To | Ship To, a meta
    table (number, date, terms, due date), lines, totals, thanks."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    S, C = ctx.S, ctx.C
    top = [ctx.name(S), ctx.addr(S, multiline=True)]
    cl = contact_lines(ctx, S, one_line=True)
    if cl is not None:
        top.append(cl)
    doc.add(Para(lines(*top), prose=False))
    doc.add(Heading(title.upper() if maybe(ctx, 0.5) else title))
    ship = lines(AText(ctx.kw("ship_to")),
                 ctx.name(C) if not isinstance(C, dict) else AText(C["full"]),
                 ctx.addr(C, multiline=True) if not isinstance(C, dict)
                 else AText("\n".join(C["address"]["lines"])))
    doc.add(Columns(_customer(ctx, "bill_to", multiline_address=True),
                    ship))
    meta = Table([[Cell(ctx.kw("invoice_no")), Cell(ctx.kw("date")),
                   Cell(ctx.kw("payment_terms")), Cell(ctx.kw("due_date"))],
                  [Cell(AText(inv["number"], trap="T6")),
                   Cell(ctx.doc_date()),
                   Cell("Net %d" % max(1, (inv["due_date"] -
                                           ctx.doc.date).days)
                        if ctx.lang == "en" else
                        ctx.plain("n_days")),
                   Cell(AText(ctx.date_o(inv["due_date"]), trap="T15"))]])
    doc.add(meta)
    doc.add(items_table(ctx, inv, cols=["code", "description", "qty",
                                        "unit_price", "amount"],
                        currency_style=pick(ctx, ["bare", "doc"])))
    doc.add(Para(totals_lines(ctx, inv, total_concept=pick(
        ctx, ["total", "balance_due", "total_payable"])), prose=False))
    thanks = ctx.phrase("invoice_notes", "thanks")
    if thanks is not None:
        doc.add(Para(thanks))
    return doc


@layout("invoice.L10", "invoice")
def e_invoice(ctx):
    """Printout of an electronic invoice: seller and buyer as label:value
    lines with their tax numbers, lines, totals, a QR code mention."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx, title_key="tax_invoice")
    S, C = ctx.S, ctx.C
    doc.add(Heading(title))
    doc.add(Para(dates_block(ctx, inv), prose=False))
    s_lines = [AText(ctx.kw("seller")),
               kv(ctx, "company_name", ctx.name(S))]
    if presence_ok(ctx, S, "reg_id"):
        rid = try_(ctx.reg_id, S, None, False)
        if rid is not None:
            s_lines.append(kv(ctx, "vat_no", rid))
    s_lines.append(kv(ctx, "address", ctx.addr(S)))
    c_lines = [AText(ctx.kw("buyer")), kv(ctx, "company_name", ctx.name(C))]
    if not isinstance(C, dict):
        rid = try_(ctx.reg_id, C, None, False)
        if rid is not None:
            c_lines.append(kv(ctx, "vat_no", rid))
        c_lines.append(kv(ctx, "address", ctx.addr(C)))
    doc.add(Columns(lines(*s_lines), lines(*c_lines)))
    doc.add(items_table(ctx, inv, cols=["description", "unit_price", "qty",
                                        "rate", "amount"]))
    doc.add(Para(totals_lines(ctx, inv, total_concept="total_incl"),
                 prose=False))
    doc.add(Para(AText("[QR]"), prose=False))
    notes = _notes(ctx, inv)
    if notes is not None:
        doc.add(Para(notes))
    return doc


@layout("invoice.L11", "invoice")
def spreadsheet_grid(ctx):
    """The whole invoice as one grid, like an invoice template made in a
    spreadsheet (the title is the first row)."""
    doc, inv = ctx.doc, invoice_data(ctx)
    title = _setup(ctx)
    S, C = ctx.S, ctx.C
    rows = [[Cell(title), Cell(""), Cell(""), Cell("")]]
    rows.append([Cell(ctx.name(S)), Cell(""), Cell(ctx.kw("invoice_no")),
                 Cell(AText(inv["number"], trap="T6"))])
    rows.append([Cell(ctx.addr(S)), Cell(""), Cell(ctx.kw("date")),
                 Cell(ctx.doc_date(), AText(ctx.fmt.date(
                     ctx.doc.date, "sheet")[0], "DOC_DATE",
                     ctx.fmt.date(ctx.doc.date, "sheet")[1]))])
    tel = try_(ctx.phone, S) if presence_ok(ctx, S, "phone") else None
    rows.append([Cell(tel if tel is not None else ""), Cell(""),
                 Cell(ctx.kw("due_date")),
                 Cell(AText(ctx.date_o(inv["due_date"]), trap="T15"),
                      AText(ctx.fmt.date(inv["due_date"], "sheet")[0],
                            trap="T15"))])
    rows.append([Cell(ctx.kw("bill_to")), Cell(""), Cell(""), Cell("")])
    rows.append([Cell(ctx.name(C)), Cell(""), Cell(""), Cell("")])
    if not isinstance(C, dict):
        rows.append([Cell(ctx.addr(C)), Cell(""), Cell(""), Cell("")])
    rows.append([Cell(ctx.kw("description")), Cell(ctx.kw("qty")),
                 Cell(ctx.kw("unit_price")), Cell(ctx.kw("amount"))])
    from gen.layouts.common import qty_cell
    for item in inv["items"]:
        rows.append([Cell(ctx.service(item["name"])),
                     qty_cell(ctx, item["qty"]),
                     money_cell(ctx, item["price"], "PRICE"),
                     money_cell(ctx, item["amount"], "LINE_TOTAL")])
    rows.append([Cell(""), Cell(""), Cell(ctx.kw("subtotal")),
                 money_cell(ctx, inv["subtotal"])])
    if inv["tax"]:
        rows.append([Cell(""), Cell(""), Cell(ctx.kw("vat")),
                     money_cell(ctx, inv["tax"])])
    rows.append([Cell(""), Cell(""), Cell(ctx.kw("total_payable")),
                 money_cell(ctx, inv["total"], "DOC_TOTAL")])
    doc.add(Table(rows))
    return doc


@layout("invoice.L12", "invoice")
def freelance_letter(ctx):
    """A freelancer's invoice written like a short letter."""
    doc, inv = ctx.doc, invoice_data(ctx, n_lines=pick(ctx, [1, 1, 2, 3]))
    title = _setup(ctx)
    S, C = ctx.S, ctx.C
    doc.add(Para(lines(ctx.name(S), ctx.addr(S, multiline=True)),
                 prose=False))
    doc.add(Para(_customer(ctx, "bill_to"), prose=False))
    place = ctx.phrase("phrases", "place_date")
    if place is not None:
        doc.add(Para(place, prose=False))
    else:
        doc.add(Para(ctx.doc_date(), prose=False))
    doc.add(Heading(AText(title + " ").add(AText(inv["number"],
                                                 trap="T6"))))
    intro = ctx.say("services_intro")
    if intro is not None:
        doc.add(Para(intro))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    doc.add(Para(totals_lines(ctx, inv), prose=False))
    pt = payment_terms(ctx)
    if pt is not None:
        doc.add(Para(pt))
    doc.add(Para(AText(ctx.label("due_date") + ctx.date_o(inv["due_date"]),
                       trap="T15"), prose=False))
    if maybe(ctx, 0.7):
        doc.add(Para(bank_block(ctx), prose=False))
    sig = signature(ctx)
    if sig is not None:
        doc.add(Para(sig, prose=False))
    return doc


# ---------------------------------------------------------------------
#  receipts
# ---------------------------------------------------------------------
@layout("receipt.R01", "invoice", kind="receipt")
def shop_ticket(ctx):
    doc, inv = ctx.doc, invoice_data(ctx, allow_extras=False)
    _setup(ctx, "receipt")
    S = ctx.S
    rng = ctx.rng
    head = [ctx.name(S), ctx.addr(S, multiline=maybe(ctx, 0.5))]
    tel = try_(ctx.phone, S) if presence_ok(ctx, S, "phone") else None
    if tel is not None:
        head.append(AText(ctx.kw("tel") + " ").add(tel))
    rid = id_lines(ctx, S, max_ids=1)
    if rid is not None:
        head.append(rid)
    doc.add(Para(lines(*head), prose=False))
    when = ctx.doc_date()
    when.add(" %02d:%02d" % (rng.randint(7, 21), rng.randint(0, 59)))
    doc.add(Para(lines(when, AText(ctx.label("receipt_no") +
                                   inv["number"], trap="T6")),
                 prose=False))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    tl = [kv(ctx, pick(ctx, ["total", "total_incl"]),
             ctx.money(inv["total"], "DOC_TOTAL")).mark_trap("T1")]
    if inv["tax"]:
        tl.append(AText("%s %s  %s" % (ctx.kw("vat"),
                                        ctx.fmt.percent(inv["rate"]),
                                        ctx.money(inv["tax"]).text),
                        trap="T6"))
    methods = ctx.lex.get("kw", {}).get("payment_methods") or ["Cash"]
    tl.append(AText(ctx.label("payment_method") + rng.choice(methods)))
    doc.add(Para(lines(*tl), prose=False))
    thanks = ctx.phrase("invoice_notes", "thanks")
    if thanks is not None:
        doc.add(Para(thanks, prose=False))
    return doc


@layout("receipt.R02", "invoice", kind="receipt")
def payment_receipt(ctx):
    """'Received from X the sum of Y for Z' - a payment receipt."""
    doc, inv = ctx.doc, invoice_data(ctx, n_lines=1, allow_extras=False)
    title = _setup(ctx, "receipt")
    S, C = ctx.S, ctx.C
    doc.add(Heading(AText(title + " ").add(AText(inv["number"], trap="T6"))))
    doc.add(Para(lines(ctx.name(S), ctx.addr(S)), prose=False))
    doc.add(Para(kv(ctx, "date", ctx.doc_date()), prose=False))
    rows = [AText(ctx.label("buyer")).add(ctx.name(C)),
            AText(ctx.label("amount")).add(ctx.money(inv["total"],
                                                     "DOC_TOTAL")),
            AText(ctx.label("description")).add(
                ctx.service(inv["items"][0]["name"]))]
    doc.add(Para(lines(*rows), prose=False))
    if _words_wanted(ctx):
        aw = amount_words(ctx, inv["total"])
        if aw is not None:
            doc.add(Para(aw))
    methods = ctx.lex.get("kw", {}).get("payment_methods") or ["Cash"]
    doc.add(Para(AText(ctx.label("payment_method") +
                       ctx.rng.choice(methods)), prose=False))
    sig = signature(ctx)
    if sig is not None:
        doc.add(Para(sig, prose=False))
    return doc


@layout("receipt.R03", "invoice", kind="receipt")
def restaurant_bill(ctx):
    doc, inv = ctx.doc, invoice_data(ctx, allow_extras=False)
    _setup(ctx, "receipt")
    rng = ctx.rng
    S = ctx.S
    doc.add(Heading(ctx.name(S)))
    doc.add(Para(ctx.addr(S), prose=False))
    meta = AText("#%d  " % rng.randint(1, 60), trap="T6")
    meta.add(ctx.doc_date())
    doc.add(Para(meta, prose=False))
    doc.add(Para(items_lines(ctx, inv), prose=False))
    fee = round(inv["subtotal"] * 0.1, inv["decimals"])
    tl = [kv(ctx, "subtotal", ctx.money(inv["subtotal"])),
          AText(ctx.kw("fee") + "  " + ctx.money(fee).text, trap="T9")]
    total = round(inv["total"] + fee, inv["decimals"])
    tl.append(kv(ctx, "total", ctx.money(total, "DOC_TOTAL"))
              .mark_trap("T1"))
    doc.add(Para(lines(*tl), prose=False))
    hrs = try_(ctx.hours, S) if presence_ok(ctx, S, "hours") else None
    if hrs is not None and maybe(ctx, 0.5):
        doc.add(Para(AText(ctx.label("hours")).add(hrs), prose=False))
    thanks = ctx.phrase("invoice_notes", "thanks")
    if thanks is not None:
        doc.add(Para(thanks, prose=False))
    return doc


# ---------------------------------------------------------------------
#  credit notes
# ---------------------------------------------------------------------
@layout("credit.C01", "invoice", kind="credit_note")
def credit_note(ctx):
    doc, inv = ctx.doc, invoice_data(ctx, n_lines=pick(ctx, [1, 2]),
                                     allow_extras=False)
    title = _setup(ctx, "credit_note")
    doc.add(Columns(org_block(ctx, ctx.S, None), _customer(ctx)))
    doc.add(Heading(AText(title + " ").add(AText(ctx.doc_number("credit"),
                                                 trap="T6"))))
    doc.add(Para(kv(ctx, "date", ctx.doc_date()), prose=False))
    reason = ctx.phrase("invoice_notes", "credit_reason")
    if reason is not None:
        doc.add(Para(reason))
    ref = AText(ctx.label("reference") + ctx.doc_number("invoice") +
                " – " + ctx.date_o(ctx.doc.date - datetime.timedelta(
                    days=ctx.rng.randint(10, 90))), trap="T15")
    doc.add(Para(ref, prose=False))
    doc.add(items_table(ctx, inv, cols=["description", "qty", "unit_price",
                                        "amount"]))
    doc.add(Para(totals_lines(ctx, inv, total_concept="total_incl"),
                 prose=False))
    return doc


@layout("credit.C02", "invoice", kind="credit_note")
def credit_memo_short(ctx):
    doc, inv = ctx.doc, invoice_data(ctx, n_lines=1, allow_extras=False)
    title = _setup(ctx, "credit_note")
    doc.add(Para(lines(ctx.name(ctx.S), ctx.addr(ctx.S)), prose=False))
    doc.add(Heading(title))
    body = [AText(ctx.label("credit_note_no") + ctx.doc_number("credit"),
                  trap="T6"),
            kv(ctx, "date", ctx.doc_date()),
            AText(ctx.label("buyer")).add(ctx.name(ctx.C)),
            AText(ctx.label("description")).add(
                ctx.service(inv["items"][0]["name"])),
            kv(ctx, "total", ctx.money(inv["total"], "DOC_TOTAL"))]
    doc.add(Para(lines(*body), prose=False))
    reason = ctx.phrase("invoice_notes", "credit_reason")
    if reason is not None:
        doc.add(Para(reason))
    return doc
