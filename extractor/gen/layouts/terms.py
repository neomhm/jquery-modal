"""
terms.py - general terms of sale, privacy policies, legal notices and
cookie policies (6 layouts). S is the organisation that publishes them;
the web host named in a legal notice is O.
"""
from gen.doc import Heading, Para
from gen.layouts.common import layout, lines, maybe, pick
from gen.text import AText

CGV_ARTICLES = ["scope", "orders", "prices", "payment", "delivery",
                "warranty", "liability", "withdrawal", "disputes"]
PRIVACY_ARTICLES = ["data_controller", "data_collected", "purposes",
                    "retention", "rights"]


def _title(ctx, key):
    items = (ctx.titles_.get("terms") or {}).get(key) or [key]
    t = ctx.rng.choice(items)
    ctx.doc.meta["title_text"] = t
    return t


def _art_title(ctx, key):
    items = ((ctx.titles_.get("terms") or {}).get("articles") or {}).get(key)
    return ctx.rng.choice(items) if items else None


def _paras(ctx, key, n):
    items = (ctx.sent.get("terms") or {}).get(key) or []
    order = list(range(len(items)))
    ctx.rng.shuffle(order)
    out = []
    for k in order:
        if len(out) >= n:
            break
        if ctx.can_fill(items[k]):
            try:
                out.append(ctx.fill(items[k], "terms.%s.%s.%02d" %
                                    (key, ctx.lang, k + 1)))
            except Exception:
                pass
    return out


def _articles(ctx, key, heads, n):
    doc = ctx.doc
    paras = _paras(ctx, key, n)
    for k, at in enumerate(paras):
        head = _art_title(ctx, heads[k % len(heads)])
        if head and maybe(ctx, 0.8):
            doc.add(Heading("%s %d – %s" % (pick(ctx, ["Art.", "§", ""]),
                                            k + 1, head) if maybe(ctx, 0.5)
                            else head, level=2))
        doc.add(Para(at))
        if k and k % 5 == 0:
            doc.new_page()


@layout("terms.T01", "terms")
def general_terms(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "cgv")))
    if maybe(ctx, 0.6):
        doc.add(Para(ctx.name(ctx.S, legal=True), prose=False))
    _articles(ctx, "cgv", CGV_ARTICLES, ctx.rng.randint(6, 12))
    return doc


@layout("terms.T03", "terms")
def legal_notice(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "legal_notice")))
    paras = _paras(ctx, "legal_notice", ctx.rng.randint(4, 8))
    heads = ["publisher", "hosting", "intellectual_property"]
    for k, at in enumerate(paras):
        if k in (0, 3) and maybe(ctx, 0.7):
            h = _art_title(ctx, heads[min(k // 3, 2)])
            if h:
                doc.add(Heading(h, level=2))
        doc.add(Para(at, prose=maybe(ctx, 0.5)))
    return doc


@layout("terms.T04", "terms")
def cookies_and_privacy(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "cookies")))
    for at in _paras(ctx, "cookies", ctx.rng.randint(2, 4)):
        doc.add(Para(at))
    doc.add(Heading(_title(ctx, "privacy"), level=2))
    for at in _paras(ctx, "privacy", ctx.rng.randint(2, 4)):
        doc.add(Para(at))
    return doc


@layout("terms.T05", "terms")
def online_shop_terms(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "cgv")))
    intro = ctx.say("activity")
    if intro is not None:
        doc.add(Para(intro))
    _articles(ctx, "cgv", ["scope", "orders", "prices", "delivery",
                           "withdrawal", "warranty", "disputes"],
              ctx.rng.randint(5, 9))
    return doc


@layout("terms.T06", "terms")
def notice_and_terms(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "legal_notice")))
    for at in _paras(ctx, "legal_notice", ctx.rng.randint(3, 5)):
        doc.add(Para(at, prose=False))
    doc.new_page()
    doc.add(Heading(_title(ctx, "cgv")))
    _articles(ctx, "cgv", CGV_ARTICLES, ctx.rng.randint(3, 6))
    return doc
