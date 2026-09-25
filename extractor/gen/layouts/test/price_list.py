"""
Held-out TEST layouts from price_list.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import price_list as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("price_list.P04", "price_list")
def menu(ctx):
    """A menu / board in sections."""
    doc = ctx.doc
    title = _setup(ctx)
    S = ctx.S
    doc.add(Heading(ctx.name(S)))
    items = _services(ctx)
    half = max(1, len(items) // 2)
    for k, part in enumerate([items[:half], items[half:]]):
        if not part:
            continue
        doc.add(Heading(title if k == 0 else ctx.kw("pl_category"),
                        level=2))
        out = []
        for s in part:
            line = AText().add(ctx.service(s["name"]))
            line.add(pick(ctx, ["  ", " – ", "\t", " ... "]))
            line.add(ctx.money(s["price"], "PRICE"))
            out.append(line)
        doc.add(Para(lines(*out), prose=False))
    if S.hours and presence_ok(ctx, S, "hours"):
        doc.add(Para(AText(ctx.label("hours")).add(ctx.hours(S)),
                     prose=False))
    return doc
