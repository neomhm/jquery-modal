"""
Held-out TEST layouts from brochure.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import brochure as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("brochure.B03", "brochure")
def history_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.title("brochure", "history")))
    body = prose(ctx, ["founded", "activity"], traps=["T7"] + _traps(ctx),
                 fillers=(1, 2))
    if body is not None:
        doc.add(Para(body))
    body = prose(ctx, ["staff", "revenue", "clients"], traps=_traps(ctx))
    if body is not None:
        doc.add(Para(body))
    _section(ctx, "values", [], traps=False, fillers=(2, 4))
    _end(ctx)
    return doc
