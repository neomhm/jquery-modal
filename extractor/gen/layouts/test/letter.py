"""
Held-out TEST layouts from letter.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import letter as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("letter.E05", "letter")
def short_note(ctx):
    doc = ctx.doc
    _setup(ctx)
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Para(subj, prose=False))
    doc.add(Para(_date_line(ctx), prose=False))
    for b in _body(ctx, 1):
        doc.add(Para(b))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    return doc
