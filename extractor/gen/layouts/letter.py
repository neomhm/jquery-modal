"""
letter.py - letters and e-mails (8 layouts).

The scenario (from sentences.json -> letters) decides who is who:
from the business to a client, from a client or a supplier to the
business (then the business is C_), or from a bank / tax office /
registry (then there is no S at all: the sender is O, rule R5/R7).
The ctx is built by make.py with the right S and C for the scenario.
"""
from gen.doc import Blank, Heading, Para
from gen.layouts.common import (contact_lines, kv, layout, legal_footer,
                                lines, maybe, org_block, pick, presence_ok,
                                signature, try_)
from gen.text import AText


def _scenario(ctx):
    return ctx.doc.meta.get("scenario", "thanks")


def _sender_name(ctx):
    """The sending organisation: S, or an O name for banks etc."""
    if ctx.S is not None:
        return ctx.name(ctx.S)
    return AText(ctx.doc.meta.get("sender_name") or ctx.plain("bank"))


def _recipient(ctx):
    C = ctx.C
    if C is None:
        return None
    if isinstance(C, dict):
        return AText("%s\n%s" % (C["full"], "\n".join(C["address"]["lines"])))
    return lines(ctx.name(C), ctx.addr(C, multiline=maybe(ctx, 0.6)))


def _subject(ctx):
    subj = ctx.phrase("letters", _scenario(ctx), "subject")
    if subj is None:
        return None
    return AText(ctx.label("lt_subject")).add(subj)


def _body(ctx, n=None):
    n = n or ctx.rng.randint(2, 4)
    items = (ctx.sent.get("letters") or {}).get(_scenario(ctx), {}).get(
        "body") or []
    out = []
    order = list(range(len(items)))
    ctx.rng.shuffle(order)
    for k in order[:n]:
        text = items[k]
        if not ctx.can_fill(text):
            continue
        try:
            out.append(ctx.fill(text, "letters.%s.body.%s.%02d" %
                                (_scenario(ctx), ctx.lang, k + 1)))
        except Exception:
            continue
    if maybe(ctx, 0.2) and ctx.S is not None:
        t = ctx.say("traps", trap="T11")
        if t is not None:
            out.append(t)
    return out


def _salutation(ctx):
    items = ctx.lex.get("kw", {}).get("lt_salutation") or ["Dear Sir,"]
    return AText(ctx.rng.choice(items))


def _closing(ctx):
    items = ctx.lex.get("kw", {}).get("lt_closing") or ["Regards,"]
    return AText(ctx.rng.choice(items))


def _signoff(ctx):
    if ctx.S is not None:
        return signature(ctx)
    return lines(AText(ctx.plain("person"), trap="T11"),
                 AText(ctx.plain("position")),
                 AText(ctx.doc.meta.get("sender_name") or ""))


def _date_line(ctx):
    place = ctx.phrase("phrases", "place_date")
    return place if place is not None else ctx.doc_date()


def _setup(ctx):
    subj = ctx.phrase("letters", _scenario(ctx), "subject")
    ctx.doc.meta["title_text"] = subj.text if subj is not None else "letter"


# ---------------------------------------------------------------------
@layout("letter.E01", "letter")
def formal_letter(ctx):
    doc = ctx.doc
    _setup(ctx)
    if ctx.S is not None:
        doc.add(Para(org_block(ctx, ctx.S, None, ids=maybe(ctx, 0.3)),
                     prose=False))
    else:
        doc.add(Para(lines(_sender_name(ctx), AText(
            ctx.doc.meta.get("sender_address") or "")), prose=False))
    rec = _recipient(ctx)
    if rec is not None:
        doc.add(Para(rec, prose=False))
    doc.add(Para(_date_line(ctx), prose=False))
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Para(subj, prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    if ctx.S is not None and maybe(ctx, 0.4):
        foot = legal_footer(ctx)
        if foot is not None:
            doc.add(Para(foot))
    return doc


@layout("letter.E02", "letter")
def email(ctx):
    doc = ctx.doc
    _setup(ctx)
    head = [AText(ctx.kw("em_from") + ": ").add(
        ctx.email(ctx.S) if ctx.S is not None and ctx.S.email and
        presence_ok(ctx, ctx.S, "email") else _sender_name(ctx))]
    if ctx.C is not None and not isinstance(ctx.C, dict):
        to = ctx.C.email or ctx.C.slug + "@example.com"
        head.append(AText(ctx.kw("em_to") + ": " + to))
    head.append(AText(ctx.kw("em_date") + ": ").add(ctx.doc_date()))
    subj = ctx.phrase("letters", _scenario(ctx), "subject")
    if subj is not None:
        head.append(AText(ctx.kw("em_subject") + ": ").add(subj))
    doc.add(Para(lines(*head), prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx, ctx.rng.randint(1, 3)):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    if ctx.S is not None:
        cl = contact_lines(ctx, ctx.S)
        if cl is not None:
            doc.add(Para(cl, prose=False))
    return doc


@layout("letter.E03", "letter")
def institutional_letter(ctx):
    """A letter with references and a reference number block (bank,
    administration or business alike)."""
    doc = ctx.doc
    _setup(ctx)
    doc.add(Para(lines(_sender_name(ctx),
                       AText(ctx.doc.meta.get("sender_address") or "")
                       if ctx.S is None else ctx.addr(ctx.S)),
                 prose=False))
    refs = [AText(ctx.label("lt_ref") + "%s/%d" % (
        pick(ctx, ["AB", "CD", "DG", "SR"]), ctx.rng.randint(1000, 99999)),
        trap="T6"),
        kv(ctx, "date", ctx.doc_date())]
    doc.add(Para(lines(*refs), prose=False))
    rec = _recipient(ctx)
    if rec is not None:
        doc.add(Para(rec, prose=False))
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Heading(subj))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    return doc


@layout("letter.E04", "letter")
def circular(ctx):
    """A letter to all customers (closure, move, price change ...)."""
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(_sender_name(ctx)))
    doc.add(Para(_date_line(ctx), prose=False))
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Para(subj, prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx, ctx.rng.randint(2, 3)):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    if ctx.S is not None:
        cl = contact_lines(ctx, ctx.S, one_line=True)
        if cl is not None:
            doc.add(Para(lines(ctx.addr(ctx.S), cl), prose=False))
    return doc


@layout("letter.E06", "letter")
def letter_with_blocks(ctx):
    """Sender at the left, recipient at the right, then the letter."""
    doc = ctx.doc
    _setup(ctx)
    from gen.doc import Columns
    left = org_block(ctx, ctx.S, None, ids=False) if ctx.S is not None \
        else lines(_sender_name(ctx))
    rec = _recipient(ctx) or AText("")
    doc.add(Columns(left, rec))
    doc.add(Para(_date_line(ctx), prose=False))
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Para(subj, prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    return doc


@layout("letter.E07", "letter")
def email_with_signature(ctx):
    """An e-mail whose signature names another contact person (T11)."""
    doc = ctx.doc
    _setup(ctx)
    subj = ctx.phrase("letters", _scenario(ctx), "subject")
    head = [AText(ctx.kw("em_subject") + ": ").add(subj) if subj is not None
            else None, AText(ctx.kw("em_date") + ": ").add(ctx.doc_date())]
    doc.add(Para(lines(*head), prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx, ctx.rng.randint(1, 2)):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    sig = [AText(ctx.plain("person"), trap="T11"),
           AText(ctx.plain("position"))]
    if ctx.S is not None:
        sig.append(ctx.name(ctx.S))
        tel = try_(ctx.phone, ctx.S) if presence_ok(ctx, ctx.S, "phone") \
            else None
        if tel is not None:
            sig.append(AText(ctx.kw("tel") + " ").add(tel))
        if ctx.S.website and presence_ok(ctx, ctx.S, "website"):
            sig.append(ctx.url(ctx.S, social=False))
    doc.add(Para(lines(*sig), prose=False))
    return doc


@layout("letter.E08", "letter")
def letter_with_enclosures(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Para(lines(_sender_name(ctx), ctx.addr(ctx.S)
                       if ctx.S is not None else None), prose=False))
    rec = _recipient(ctx)
    if rec is not None:
        doc.add(Para(rec, prose=False))
    doc.add(Para(_date_line(ctx), prose=False))
    subj = _subject(ctx)
    if subj is not None:
        doc.add(Para(subj, prose=False))
    doc.add(Para(_salutation(ctx), prose=False))
    for b in _body(ctx):
        doc.add(Para(b))
    doc.add(Para(_closing(ctx), prose=False))
    so = _signoff(ctx)
    if so is not None:
        doc.add(Para(so, prose=False))
    doc.add(Para(AText(ctx.label("lt_attachment") + "%d" %
                       ctx.rng.randint(1, 3)), prose=False))
    return doc
