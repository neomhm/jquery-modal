"""
Held-out TEST layouts from other.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import other as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("other.O01", "other")
def meeting_notes(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "meeting")))
    when = ctx.date_o(datetime.date(2025, ctx.rng.randint(1, 12),
                                    ctx.rng.randint(1, 28)))
    doc.add(Para(AText(when), prose=False))
    people = ", ".join(ctx.plain("person") for _ in range(
        ctx.rng.randint(2, 4)))
    doc.add(Para(AText(people), prose=False))
    for at in _noise(ctx, "meeting", ctx.rng.randint(2, 4)):
        doc.add(Para(AText("- ").add(at), prose=False))
    return doc
