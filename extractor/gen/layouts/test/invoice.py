"""
Held-out TEST layouts from invoice.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import invoice as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


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
    count = AText(COUNT_LINE.get(ctx.lang, COUNT_LINE["en"]).format(
        n=len(inv["items"])))
    count.add(ctx.money(inv["total"], "DOC_TOTAL"))
    doc.add(Para(count, prose=False))
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
