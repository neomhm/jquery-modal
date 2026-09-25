"""
contract.py - service agreements and other contracts (6 layouts).
S is the party that provides the goods or service; C is the client
(rule R5). The signing date is DOC_DATE; amounts in a contract are O.
"""
from gen.doc import Heading, Para
from gen.layouts.common import layout, lines, maybe, pick, signature
from gen.text import AText

ORDER = ["preamble", "object", "duration", "price", "payment",
         "obligations", "confidentiality", "liability", "termination",
         "law"]
ARTICLE_OF = {"object": "object", "duration": "duration", "price": "price",
              "payment": "payment", "obligations": "obligations",
              "confidentiality": "confidentiality",
              "liability": "liability", "termination": "termination",
              "law": "law"}


def _setup(ctx):
    doc = ctx.doc
    items = (ctx.titles_.get("contract") or {}).get("titles") or ["Contract"]
    t = ctx.rng.choice(items)
    doc.meta["title_text"] = t
    return t


def _article(ctx, k, clause, numbered=True):
    doc = ctx.doc
    head = ((ctx.titles_.get("contract") or {}).get("articles") or {}).get(
        ARTICLE_OF.get(clause, clause))
    body = ctx.phrase("contract", clause)
    if body is None:
        return k
    if head:
        title = ctx.rng.choice(head)
        doc.add(Heading("%d. %s" % (k, title) if numbered else title,
                        level=2))
    doc.add(Para(body))
    return k + 1


def _parties(ctx):
    doc = ctx.doc
    p = ctx.phrase("contract", "parties_provider")
    c = ctx.phrase("contract", "parties_client")
    for at in (p, c):
        if at is not None:
            doc.add(Para(at))


def _signatures(ctx):
    doc = ctx.doc
    sig = ctx.phrase("contract", "signature")
    if sig is not None:
        doc.add(Para(sig))
    else:
        doc.add(Para(ctx.doc_date(), prose=False))
    left = signature(ctx)
    if left is not None:
        doc.add(Para(left, prose=False))
    if not isinstance(ctx.C, dict) and ctx.C is not None:
        doc.add(Para(lines(AText(ctx.plain("person"), trap="T11"),
                           ctx.name(ctx.C)), prose=False))


@layout("contract.K02", "contract")
def short_agreement(ctx):
    doc = ctx.doc
    doc.add(Heading(_setup(ctx)))
    _parties(ctx)
    k = 1
    for clause in ("object", "price", "duration", "law"):
        k = _article(ctx, k, clause, numbered=maybe(ctx, 0.5))
    _signatures(ctx)
    return doc


@layout("contract.K03", "contract")
def maintenance_with_annex(ctx):
    """A maintenance contract with an annex listing the services."""
    doc = ctx.doc
    doc.add(Heading(_setup(ctx)))
    _parties(ctx)
    k = 1
    for clause in ("object", "duration", "obligations", "payment",
                   "termination"):
        k = _article(ctx, k, clause)
    _signatures(ctx)
    doc.new_page()
    doc.add(Heading(ctx.kw("services")))
    S = ctx.S
    items = ctx.rng.sample(S.services, min(len(S.services),
                                           ctx.rng.randint(2, 6)))
    doc.add(Para(lines(*[AText("- ").add(ctx.service(s["name"]))
                         for s in items]), prose=False))
    return doc


@layout("contract.K04", "contract")
def framework_agreement(ctx):
    doc = ctx.doc
    doc.add(Heading(_setup(ctx)))
    pre = ctx.phrase("contract", "preamble")
    _parties(ctx)
    if pre is not None:
        doc.add(Para(pre))
    k = 1
    for clause in ("object", "obligations", "price", "confidentiality",
                   "liability", "law"):
        k = _article(ctx, k, clause)
    _signatures(ctx)
    return doc


@layout("contract.K05", "contract")
def numbered_text(ctx):
    """Articles as numbered paragraphs, without headings."""
    doc = ctx.doc
    doc.add(Heading(_setup(ctx)))
    _parties(ctx)
    for k, clause in enumerate(("object", "duration", "price", "payment",
                                "termination", "law"), start=1):
        body = ctx.phrase("contract", clause)
        if body is not None:
            doc.add(Para(AText("%d. " % k).add(body)))
    _signatures(ctx)
    return doc


@layout("contract.K06", "contract")
def two_page_agreement(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    doc.meta["page_line"] = None
    doc.add(Heading(title))
    _parties(ctx)
    k = 1
    for clause in ("object", "duration", "price"):
        k = _article(ctx, k, clause)
    doc.new_page()
    for clause in ("payment", "confidentiality", "liability", "termination",
                   "law"):
        k = _article(ctx, k, clause)
    _signatures(ctx)
    return doc
