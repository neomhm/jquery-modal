"""
Held-out TEST layouts from terms.py (hold-out set T, section 11).
Moved here by the hold-out draw; they are used only in test_heldout.
"""
from gen.layouts import terms as _base

globals().update({k: v for k, v in vars(_base).items()
                 if not k.startswith("__")})


@layout("terms.T02", "terms")
def privacy_policy(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "privacy")))
    _articles(ctx, "privacy", PRIVACY_ARTICLES, ctx.rng.randint(4, 8))
    return doc
