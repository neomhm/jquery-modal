"""
Held-out TEST layouts from quote.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import quote as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


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
