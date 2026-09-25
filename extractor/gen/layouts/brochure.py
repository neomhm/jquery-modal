"""
brochure.py - brochures, "about us" pages and website pages (10 layouts).

The subject S is the business presenting itself; C_NAME is only used for
clients named as references (rule R5). Trap sentences (T1 T5 T7 T8 T11
T13) are mixed in, at the rates of section 10.6.
"""
from gen.doc import Blank, Cell, Heading, Para, Table
from gen.layouts.common import (contact_lines, kv, layout, legal_footer,
                                lines, maybe, pick, presence_ok, prose,
                                try_)
from gen.text import AText

TRAP_RATES = {"T1": 0.12, "T5": 0.2, "T7": 0.25, "T8": 0.25, "T11": 0.2,
              "T13": 0.12}


def _traps(ctx, boost=1.0):
    boost *= ctx.rules.get("trap_boost", 1.0)
    return [t for t, p in TRAP_RATES.items() if maybe(ctx, p * boost)]


def _setup(ctx):
    doc = ctx.doc
    t = ctx.title("brochure", "about")
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    return t


def _section(ctx, title_key, cats, traps=True, fillers=(0, 2)):
    doc = ctx.doc
    body = prose(ctx, cats, traps=_traps(ctx) if traps else None,
                 fillers=fillers)
    if body is None:
        return
    doc.add(Heading(ctx.title("brochure", title_key)))
    doc.add(Para(body))


def _tagline(ctx):
    items = (ctx.titles_.get("brochure") or {}).get("taglines") or []
    if not items:
        return None
    text = ctx.rng.choice(items)
    if "{city}" in text:
        text = text.replace("{city}", ctx.plain("city"))
    return text


def _service_list(ctx, n=None, bullet=None):
    S = ctx.S
    if not S.services:
        return None
    k = min(len(S.services), n or ctx.rng.randint(3, 8))
    bullet = bullet if bullet is not None else pick(ctx, ["- ", "• ", "* ",
                                                          "", "– "])
    items = [AText(bullet).add(ctx.service(s["name"]))
             for s in ctx.rng.sample(S.services, k)]
    return lines(*items)


def _contact(ctx):
    S = ctx.S
    parts = [ctx.name(S) if maybe(ctx, 0.5) else None,
             ctx.addr(S, multiline=maybe(ctx, 0.5))]
    cl = contact_lines(ctx, S)
    if cl is not None:
        parts.append(cl)
    if presence_ok(ctx, S, "hours") and S.hours and maybe(ctx, 0.7):
        parts.append(AText(ctx.label("hours")).add(ctx.hours(S)))
    return lines(*parts)


def _end(ctx):
    if maybe(ctx, 0.4):
        foot = legal_footer(ctx)
        if foot is not None:
            ctx.doc.add(Para(foot))


# ---------------------------------------------------------------------
@layout("brochure.B01", "brochure")
def about_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.name(ctx.S)))
    tag = _tagline(ctx)
    if tag:
        doc.add(Para(AText(tag), prose=False))
    _section(ctx, "about", ["activity", "founded", "staff", "location"])
    services = _service_list(ctx)
    if services is not None:
        doc.add(Heading(ctx.title("brochure", "services")))
        intro = ctx.say("services_intro")
        if intro is not None:
            doc.add(Para(intro))
        doc.add(Para(services, prose=False))
    doc.add(Heading(ctx.title("brochure", "contact")))
    doc.add(Para(_contact(ctx), prose=False))
    _end(ctx)
    return doc


@layout("brochure.B02", "brochure")
def flyer(ctx):
    doc = ctx.doc
    _setup(ctx)
    tag = _tagline(ctx)
    doc.add(Heading(ctx.name(ctx.S)))
    if tag:
        doc.add(Heading(tag, level=2))
    body = prose(ctx, ["services_intro", "activity"], traps=_traps(ctx))
    if body is not None:
        doc.add(Para(body))
    services = _service_list(ctx, bullet="✓ ")
    if services is not None:
        doc.add(Para(services, prose=False))
    hours = ctx.say("hours")
    if hours is not None:
        doc.add(Para(hours))
    cta = ctx.phrase("web", "cta")
    if cta is not None:
        doc.add(Para(cta, prose=False))
    doc.add(Para(_contact(ctx), prose=False))
    return doc


@layout("brochure.B04", "brochure")
def services_catalogue(ctx):
    """One short paragraph per service."""
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.title("brochure", "services")))
    intro = ctx.say("services_intro")
    if intro is not None:
        doc.add(Para(intro))
    S = ctx.S
    with_prices = maybe(ctx, 0.6)
    for s in ctx.rng.sample(S.services, min(len(S.services),
                                            ctx.rng.randint(3, 6))):
        doc.add(Heading(ctx.service(s["name"]), level=2))
        if with_prices:
            line = AText(ctx.label(pick(ctx, ["pl_price", "unit_price"])))
            line.add(ctx.money(s["price"], "PRICE"))
            unit = ctx.unit(s["unit"])
            if unit and maybe(ctx, 0.5):
                line.add(" / " + unit)
            doc.add(Para(line, prose=False))
    _section(ctx, "why_us", ["certifications"], fillers=(1, 2))
    doc.add(Para(_contact(ctx), prose=False))
    return doc


@layout("brochure.B05", "brochure")
def key_facts(ctx):
    """A company profile as a list of facts (label: value)."""
    doc = ctx.doc
    _setup(ctx)
    S, biz = ctx.S, ctx.biz
    rng = ctx.rng
    intro = prose(ctx, ["activity"], fillers=(0, 1))
    doc.add(Heading(ctx.title("brochure", "about")))
    if intro is not None:
        doc.add(Para(intro))
    facts = [kv(ctx, "company_name", ctx.name(S, legal=True))]
    if S.trading != S.legal and maybe(ctx, 0.7):
        facts.append(kv(ctx, "trade_name", ctx.name(S, legal=False)))
    if presence_ok(ctx, S, "legal_form") and maybe(ctx, 0.8):
        facts.append(kv(ctx, "legal_form", ctx.legal_form(S)))
    if presence_ok(ctx, S, "founded"):
        facts.append(kv(ctx, "founded", ctx.founded(
            S, pick(ctx, ["year", "year", "month", "date"]))))
    if presence_ok(ctx, S, "capital") and S.capital:
        facts.append(kv(ctx, "capital", ctx.capital(S)))
    if presence_ok(ctx, S, "manager"):
        facts.append(AText(S.manager_title + ctx.colon() + " ").add(
            ctx.person(S)))
    if presence_ok(ctx, S, "staff") and S.staff:
        facts.append(kv(ctx, "staff", ctx.staff(S)))
    if presence_ok(ctx, S, "revenue") and S.revenue:
        y = max(S.revenue)
        line = AText(ctx.kw("revenue") + " ")
        line.add(ctx.rev_year(S, y))
        line.add(ctx.colon() + " ").add(ctx.revenue(S, y))
        facts.append(line)
    if presence_ok(ctx, S, "activity") and maybe(ctx, 0.7):
        act = try_(ctx.activity, S)
        if act is not None:
            facts.append(kv(ctx, "activity", act))
    if presence_ok(ctx, S, "activity_code") and S.act_code and \
            maybe(ctx, 0.6):
        facts.append(ctx.act_code(S))
    if presence_ok(ctx, S, "certs") and S.certs:
        facts.append(kv(ctx, "certifications",
                        ctx.join_list([ctx.cert(c) for c in S.certs])))
    facts.append(kv(ctx, "address", ctx.addr(S)))
    if presence_ok(ctx, S, "reg_id") and maybe(ctx, 0.6):
        rid = try_(ctx.reg_id, S)
        if rid is not None:
            facts.append(rid)
    if presence_ok(ctx, S, "website") and (S.website or S.social):
        facts.append(kv(ctx, "web", ctx.url(S)))
    if rng.random() < 0.3:
        trap = ctx.say("traps", trap=pick(ctx, ["T5", "T8"]))
        if trap is not None:
            facts.append(trap)
    doc.add(Para(lines(*facts), prose=False))
    return doc


@layout("brochure.B06", "brochure")
def references_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.title("brochure", "clients")))
    body = prose(ctx, ["clients"], traps=["T13"] if maybe(ctx, 0.6)
                 else _traps(ctx), fillers=(0, 1))
    if body is not None:
        doc.add(Para(body))
    doc.add(Heading(ctx.title("brochure", "testimonials")))
    quotes = []
    for _ in range(ctx.rng.randint(1, 3)):
        q = ctx.phrase("web", "testimonials")
        if q is not None:
            quotes.append(q)
    if quotes:
        doc.add(Para(lines(*quotes)))
    _section(ctx, "about", ["activity", "founded"], fillers=(0, 1))
    return doc


@layout("brochure.B07", "brochure")
def team_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    S = ctx.S
    doc.add(Heading(ctx.title("brochure", "team")))
    parts = []
    if presence_ok(ctx, S, "manager"):
        head = AText(S.manager_title + " – ").add(ctx.person(S))
        parts.append(head)
    for _ in range(ctx.rng.randint(1, 4)):
        parts.append(AText("%s – %s" % (ctx.plain("person"),
                                        ctx.plain("position")), trap="T11"))
    doc.add(Para(lines(*parts), prose=False))
    body = prose(ctx, ["staff"], traps=["T11"] + _traps(ctx),
                 fillers=(1, 2))
    if body is not None:
        doc.add(Para(body))
    _section(ctx, "values", [], traps=False, fillers=(1, 3))
    return doc


@layout("brochure.B08", "brochure")
def news_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.name(ctx.S)))
    doc.add(Heading(ctx.title("brochure", "news"), level=2))
    for _ in range(ctx.rng.randint(2, 4)):
        item = ctx.phrase("web", "news")
        if item is not None:
            doc.add(Para(item))
    _section(ctx, "about", ["activity", "location"])
    return doc


@layout("brochure.B09", "brochure")
def why_us(ctx):
    doc = ctx.doc
    _setup(ctx)
    doc.add(Heading(ctx.title("brochure", "why_us")))
    body = prose(ctx, ["certifications", "staff"], traps=["T8"] +
                 _traps(ctx), fillers=(1, 3))
    if body is not None:
        doc.add(Para(body))
    if ctx.S.certs and presence_ok(ctx, ctx.S, "certs"):
        doc.add(Heading(ctx.title("brochure", "certifications")))
        doc.add(Para(lines(*[AText("- ").add(ctx.cert(c))
                             for c in ctx.S.certs]), prose=False))
    _section(ctx, "services", ["services_intro"])
    cta = ctx.phrase("web", "cta")
    if cta is not None:
        doc.add(Para(cta, prose=False))
    return doc


@layout("brochure.B10", "brochure")
def location_page(ctx):
    doc = ctx.doc
    _setup(ctx)
    S = ctx.S
    doc.add(Heading(ctx.title("brochure", "location")))
    body = prose(ctx, ["location", "hours"], traps=_traps(ctx),
                 fillers=(0, 1))
    if body is not None:
        doc.add(Para(body))
    doc.add(Heading(ctx.title("brochure", "hours")))
    if S.hours and presence_ok(ctx, S, "hours"):
        doc.add(Para(ctx.hours(S, pick(ctx, ["compact", "prose"])),
                     prose=False))
    doc.add(Heading(ctx.title("brochure", "contact")))
    doc.add(Para(_contact(ctx), prose=False))
    _end(ctx)
    return doc
