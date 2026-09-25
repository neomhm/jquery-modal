"""
Held-out TEST layouts from contract.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import contract as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("contract.K01", "contract")
def full_agreement(ctx):
    doc = ctx.doc
    doc.add(Heading(_setup(ctx)))
    _parties(ctx)
    k = 1
    for clause in ORDER:
        if clause == "preamble":
            pre = ctx.phrase("contract", "preamble")
            if pre is not None:
                doc.add(Para(pre))
            continue
        k = _article(ctx, k, clause)
        if k in (4, 8):
            doc.new_page()
    _signatures(ctx)
    return doc
