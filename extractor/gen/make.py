"""
make.py - the synthetic data generator (section 10).

    py gen/make.py --preset smoke            generate every split
    py gen/make.py --preset smoke --check    the self-checks of 10.9
    py gen/make.py --draw-holdout            draw the hold-out sets ONCE
    py gen/make.py --sample fr-FR            print one folder, to read it

One folder = one business. Every random choice comes from a
random.Random seeded by (split, folder index), so running the generator
twice gives byte-identical data.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import multiprocessing
import pathlib
import random
import re
import sys
import time
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config                                            # noqa: E402
import normalize as N                                    # noqa: E402
from gen import business as B                            # noqa: E402
from gen import data as D                                # noqa: E402
from gen import holdout as H                             # noqa: E402
from gen import noise as NZ                              # noqa: E402
from gen import render as R                              # noqa: E402
from gen.ctx import CannotFill, DocCtx                   # noqa: E402
from gen.doc import Columns, Heading, Para, Table        # noqa: E402

REF = config.REFERENCE_DATE
TRAINING = {code: loc for code, loc in D.locales()["locales"].items()
            if not loc["heldout"]}
HELDOUT = {code: loc for code, loc in D.locales()["locales"].items()
           if loc["heldout"]}

# share of each source format per document type (section 10.5 overall:
# pdf 50 %, docx 20 %, xlsx 12 %, csv 3 %, txt / md 15 %)
FORMATS = {
    "invoice": {"pdf": 0.62, "docx": 0.12, "xlsx": 0.16, "txt": 0.05,
                "md": 0.05},
    "quote": {"pdf": 0.55, "docx": 0.2, "xlsx": 0.15, "txt": 0.05,
              "md": 0.05},
    "brochure": {"pdf": 0.45, "docx": 0.2, "txt": 0.1, "md": 0.25},
    "registration": {"pdf": 0.85, "docx": 0.05, "txt": 0.1},
    "financials": {"pdf": 0.45, "xlsx": 0.35, "docx": 0.1, "csv": 0.1},
    "price_list": {"pdf": 0.35, "xlsx": 0.3, "csv": 0.15, "docx": 0.1,
                   "md": 0.1},
    "staff_list": {"xlsx": 0.45, "csv": 0.25, "pdf": 0.15, "docx": 0.15},
    "contract": {"pdf": 0.6, "docx": 0.35, "txt": 0.05},
    "letter": {"pdf": 0.35, "docx": 0.3, "txt": 0.35},
    "terms": {"pdf": 0.3, "docx": 0.2, "md": 0.3, "txt": 0.2},
    "other": {"txt": 0.35, "docx": 0.3, "md": 0.15, "pdf": 0.2},
}
EXT = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "csv": ".csv",
       "txt": ".txt", "md": ".md"}
SERVICE_GROUPS = {"construction", "professional", "creative", "it",
                  "services", "transport", "manufacturing", "realestate"}
LETTER_WEIGHTS = {"payment_reminder": 2, "quote_followup": 1,
                  "price_change": 1, "appointment": 1, "closure": 1,
                  "move": 0.3, "new_service": 1, "thanks": 1,
                  "order_to_supplier": 1, "letter_to_bank": 0.5,
                  "order_from_client": 1, "complaint_from_client": 0.5,
                  "quote_request": 1, "supplier_offer": 1,
                  "bank_notice": 1, "loan_offer": 0.5, "tax_reminder": 1,
                  "registry_notice": 0.5}
FROM_CLIENT = {"order_from_client", "complaint_from_client",
               "quote_request"}
TO_CLIENT = {"payment_reminder", "quote_followup", "price_change",
             "appointment", "new_service", "thanks"}
NO_SENDER = {"bank_notice", "loan_offer", "tax_reminder",
             "registry_notice"}


def folder_seed(split, index):
    h = hashlib.sha1(("%s/%d" % (split, index)).encode("utf-8")).hexdigest()
    return int(h[:15], 16)


def weighted(rng, items):
    """items: {key: weight} -> a key."""
    total = sum(items.values())
    r = rng.random() * total
    for k, w in items.items():
        r -= w
        if r <= 0:
            return k
    return k


# ---------------------------------------------------------------------
#  what a split may use
# ---------------------------------------------------------------------
def split_rules(split, heldout_activity=False):
    base = {"allowed": {"train"}, "prefer": None, "p_prefer": 0.0,
            "force_layout": None, "trap_boost": 1.0}
    if split == "dev_heldout":
        base.update(allowed={"train", "D"}, prefer="D",
                    p_prefer=0.6 if heldout_activity else 1.0,
                    force_layout=None if heldout_activity else "D")
    elif split == "test_heldout":
        base.update(allowed={"train", "T"}, prefer="T",
                    p_prefer=0.6 if heldout_activity else 1.0,
                    force_layout=None if heldout_activity else "T")
    elif split == "test_locale":
        base.update(allowed={"train", "locale"})
    elif split == "traps":
        base.update(trap_boost=2.5)
    return base


def choose_locale(rng, split, index, lang=None):
    """Languages in turn (10% each, section 10.3), then a locale of that
    language by the weights of section 3. Held-out locales only in
    test_locale."""
    if split == "test_locale":
        pool = sorted(HELDOUT)
        return pool[index % len(pool)]
    lang = lang or config.LANGS[index % len(config.LANGS)]
    options = {c: l["weight"] for c, l in TRAINING.items()
               if l["lang"] == lang and l["weight"] > 0}
    return weighted(rng, dict(sorted(options.items())))


def choose_activity(rng, split):
    acts = D.activities()
    seen = [a for a in acts if not a.get("holdout")]
    if split == "dev_heldout" and rng.random() < 0.5:
        return rng.choice([a for a in acts if a.get("holdout") == "D"]), True
    if split == "test_heldout" and rng.random() < 0.5:
        return rng.choice([a for a in acts if a.get("holdout") == "T"]), True
    return rng.choice(seen), False


def client_locales(loc_code):
    lang = TRAINING.get(loc_code, HELDOUT.get(loc_code))["lang"]
    same = [c for c, l in TRAINING.items() if l["lang"] == lang and
            c != loc_code]
    return same or ["en-US", "en-GB"]


# ---------------------------------------------------------------------
#  folder composition (section 10.4)
# ---------------------------------------------------------------------
def spread_dates(rng, n, years):
    """n dates over the last 1-3 years, with a little seasonality."""
    start = REF - datetime.timedelta(days=int(365 * years))
    out = []
    for _ in range(n):
        d = B.random_date(rng, start, REF - datetime.timedelta(days=5))
        if rng.random() < 0.3:                 # busier end of year
            d = d.replace(month=rng.choice([10, 11, 12]),
                          day=min(d.day, 28))
            if d > REF:
                d = d.replace(year=d.year - 1)
        out.append(d)
    return sorted(out)


def compose(rng, biz, split):
    """The list of documents of one folder, as plans."""
    act = biz.act
    b2c = act["customers"] == "B2C"
    years = rng.choice([1, 2, 3])
    plans = []
    org_clients = biz.clients

    def customer():
        if org_clients and (rng.random() >= biz.private_share):
            return rng.choice(org_clients)
        return B.private_person(rng, biz.loc["code"])

    n_sales = rng.randint(2, 6) if b2c else rng.randint(3, 12)
    for d in spread_dates(rng, n_sales, years):
        plans.append({"type": "invoice", "kind": "invoice", "S": biz,
                      "C": customer(), "date": d, "direction": "sales"})
    if b2c:
        for d in spread_dates(rng, rng.randint(2, 6), years):
            plans.append({"type": "invoice", "kind": "receipt", "S": biz,
                          "C": B.private_person(rng, biz.loc["code"]),
                          "date": d, "direction": "sales"})
    if rng.random() < 0.1:
        plans.append({"type": "invoice", "kind": "credit_note", "S": biz,
                      "C": customer(), "date": spread_dates(rng, 1,
                                                            years)[0],
                      "direction": "sales"})
    n_quotes = rng.randint(0, 4) if act.get("group") in SERVICE_GROUPS \
        else rng.randint(0, 1)
    for d in spread_dates(rng, n_quotes, years):
        plans.append({"type": "quote", "kind": "quote", "S": biz,
                      "C": customer(), "date": d, "direction": "sales"})
    n_invoices = sum(1 for p in plans if p["type"] == "invoice")
    n_purchase = max(rng.randint(1, 4), int(math.ceil(0.25 * n_invoices)))
    for d in spread_dates(rng, n_purchase, years):
        plans.append({"type": "invoice", "kind": "invoice",
                      "S": rng.choice(biz.suppliers), "C": biz, "date": d,
                      "direction": "purchase"})
    for _ in range(rng.randint(1, 3)):
        plans.append({"type": "brochure", "kind": "brochure", "S": biz,
                      "C": None, "date": None})
    n_reg = rng.randint(1, 2) if rng.random() < 0.7 else 0
    for _ in range(n_reg):
        d = B.random_date(rng, REF - datetime.timedelta(days=700),
                          REF - datetime.timedelta(days=3))
        plans.append({"type": "registration", "kind": "registration",
                      "S": biz, "C": None, "date": d})
    if biz.presence.get("revenue"):          # 60% of folders (10.3, 10.4)
        y = max(biz.revenue)
        d = datetime.date(y + 1, rng.randint(3, 6), rng.randint(1, 28))
        plans.append({"type": "financials", "kind": "financials", "S": biz,
                      "C": None, "date": min(d, REF)})
    if rng.random() < 0.4:
        plans.append({"type": "price_list", "kind": "price_list", "S": biz,
                      "C": None, "date": None})
    if rng.random() < 0.3:
        plans.append({"type": "staff_list", "kind": "staff_list", "S": biz,
                      "C": None, "date": None})
    if org_clients and rng.random() < 0.3:
        for d in spread_dates(rng, rng.randint(1, 2), years):
            plans.append({"type": "contract", "kind": "contract", "S": biz,
                          "C": rng.choice(org_clients), "date": d})
    for d in spread_dates(rng, rng.randint(1, 5), years):
        plans.append(letter_plan(rng, biz, d))
    if rng.random() < 0.3:
        plans.append({"type": "terms", "kind": "terms", "S": biz, "C": None,
                      "date": None})
    for _ in range(rng.randint(1, 3)):
        plans.append({"type": "other", "kind": "other",
                      "S": biz if rng.random() < 0.25 else None, "C": None,
                      "date": None, "press": True})
    # ---- deliberate difficulties
    if biz.outdated and biz.outdated["field"] == "staff" and \
            len(biz.revenue) >= 2:
        # two statements: the older one (old staff count, figures up to
        # the year before) and the latest one
        ys = sorted(biz.revenue)
        old = datetime.date(ys[-2] + 1, 4, rng.randint(1, 28))
        new = min(datetime.date(ys[-1] + 1, 4, rng.randint(1, 28)), REF)
        plans.append({"type": "financials", "kind": "financials", "S": biz,
                      "C": None, "date": old, "old": True})
        plans.append({"type": "financials", "kind": "financials", "S": biz,
                      "C": None, "date": new})
    if biz.sister is not None:
        for _ in range(rng.randint(1, 3)):
            kind = rng.choice(["invoice", "brochure"])
            plans.append({"type": kind, "kind": kind, "S": biz.sister,
                          "C": customer() if kind == "invoice" else None,
                          "date": spread_dates(rng, 1, years)[0]
                          if kind == "invoice" else None,
                          "direction": "sales" if kind == "invoice"
                          else "none", "sister": True})
    rng.shuffle(plans)
    return plans


def letter_plan(rng, biz, d):
    weights = dict(LETTER_WEIGHTS)
    if not biz.clients:
        for s in FROM_CLIENT:
            weights.pop(s, None)
    if biz.outdated and biz.outdated["field"] == "address":
        weights["move"] = 3
    scen = weighted(rng, weights)
    plan = {"type": "letter", "kind": "letter", "date": d,
            "scenario": scen, "direction": "none"}
    lex = biz.lex
    if scen in NO_SENDER:
        plan.update(S=None, C=biz)
        if scen in ("bank_notice", "loan_offer"):
            banks = ((lex.get("orgs") or {}).get("banks") or {}).get(
                biz.country) or ["Bank"]
            plan["sender_name"] = rng.choice(banks)
        else:
            key = "tax_office" if scen == "tax_reminder" else "registry"
            names = ((lex.get("orgs") or {}).get(key) or {}).get(
                biz.country) or ["Office"]
            plan["sender_name"] = rng.choice(names).replace(
                "{city}", biz.address["city"] or "").replace(
                "{n}", str(rng.randint(1, 50)))
        from gen import names as N
        plan["sender_address"] = N.address(rng, biz.loc, lex)["one"]
    elif scen in FROM_CLIENT:
        plan.update(S=rng.choice(biz.clients), C=biz)
    elif scen == "supplier_offer":
        plan.update(S=rng.choice(biz.suppliers), C=biz)
    elif scen == "order_to_supplier":
        plan.update(S=biz, C=rng.choice(biz.suppliers))
    elif scen == "letter_to_bank":
        banks = ((lex.get("orgs") or {}).get("banks") or {}).get(
            biz.country) or ["Bank"]
        from gen import names as N
        bank = {"full": rng.choice(banks), "gender": "m", "private": True,
                "address": N.address(rng, biz.loc, lex)}
        plan.update(S=biz, C=bank)
    elif scen in TO_CLIENT and biz.clients:
        plan.update(S=biz, C=rng.choice(biz.clients))
    else:
        plan.update(S=biz, C=None)
    return plan


# ---------------------------------------------------------------------
#  one document
# ---------------------------------------------------------------------
def pick_layout(rng, plan, loc, rules, split):
    from gen.layouts.common import REGISTRY
    kind = plan["kind"]
    cands = []
    for lid, info in sorted(REGISTRY.items()):
        if info["doc_type"] != plan["type"] or info["kind"] != kind:
            continue
        group = H.layout_group(lid)
        if info["doc_type"] == "registration":
            if loc["code"] not in (info.get("locales") or []):
                continue
            if info.get("heldout_locale"):
                group = "locale"
            S = plan.get("S")
            if info.get("companies_only") and S is not None and \
                    S.cls not in ("company", "other"):
                continue
        if group not in rules["allowed"]:
            continue
        cands.append((lid, group))
    if not cands:
        return None
    force = rules.get("force_layout")
    if force:
        forced = [c for c in cands if c[1] == force]
        if not forced and plan["type"] == "invoice" and kind != "invoice":
            # no held-out receipt / credit-note layout: use a held-out
            # invoice layout, so the document still has its held-out item
            plan["kind"] = "invoice"
            return pick_layout(rng, plan, loc, rules, split)
        if forced:
            cands = forced
    elif split == "test_locale":
        loc_only = [c for c in cands if c[1] == "locale"]
        if loc_only:
            cands = loc_only
    return rng.choice(cands)[0]


# countries where general terms of sale are often printed on the back
# of invoices and quotes
TERMS_ON_BACK = {"FR", "BE", "CH", "IT", "ES", "MA", "SN", "CA"}


def add_terms_page(ctx):
    """General terms of sale on a last page (mostly label-free text)."""
    from gen.layouts import terms as TL
    rng = ctx.rng
    items = (ctx.titles_.get("terms") or {}).get("cgv") or []
    ctx.doc.new_page()
    if items:
        ctx.doc.add(Heading(rng.choice(items)))
    # the company is named in the first article at most; later articles
    # speak of "the seller"
    pool = list(enumerate((ctx.sent.get("terms") or {}).get("cgv") or []))
    rng.shuffle(pool)
    named = [kt for kt in pool if re.search(r"\{[A-Z_]+[:}]", kt[1])]
    plain = [kt for kt in pool if kt not in named]
    chosen = (named[:1] if rng.random() < 0.5 else []) + \
        plain[:rng.randint(4, 9)]
    for n, (k, text) in enumerate(chosen, start=1):
        if not ctx.can_fill(text):
            continue
        try:
            at = ctx.fill(text, "terms.cgv.%s.%02d" % (ctx.lang, k + 1))
        except CannotFill:
            continue
        head = TL._art_title(ctx, TL.CGV_ARTICLES[(n - 1) %
                                                  len(TL.CGV_ARTICLES)])
        if head and rng.random() < 0.7:
            ctx.doc.add(Heading("%d. %s" % (n, head), level=2))
        ctx.doc.add(Para(at))
        if n % 4 == 0:
            ctx.doc.new_page()


def add_web_sections(ctx):
    """Web pages and brochures carry generic sections too: values, why
    choose us, testimonials, news, FAQ-like notes (mostly label-free)."""
    rng = ctx.rng
    from gen.layouts.brochure import _traps
    for key in rng.sample(["values", "why_us", "testimonials", "news",
                           "faq"], rng.randint(3, 5)):
        items = []
        if key in ("values", "why_us", "faq"):
            for _ in range(rng.randint(2, 4)):
                at = ctx.say("filler")
                if at is not None and all(at.text != o.text for o in items):
                    items.append(at)
        else:
            for _ in range(rng.randint(2, 3)):
                at = ctx.phrase("web", key)
                if at is not None and all(at.text != o.text for o in items):
                    items.append(at)
        for trap in _traps(ctx, 1.6):
            at = ctx.say("traps", trap=trap)
            if at is not None:
                items.insert(rng.randint(0, len(items)), at)
        if items:
            ctx.doc.add(Heading(ctx.title("brochure", key)))
            for at in items:
                ctx.doc.add(Para(at))


def add_note_sections(ctx):
    """Internal documents go on: 2-4 more sections of notes."""
    rng = ctx.rng
    titles = (ctx.titles_.get("other") or {})
    for _ in range(rng.randint(2, 4)):
        key = rng.choice(["generic", "memo", "meeting", "todo", "news"])
        pool = list(((ctx.sent.get("noise") or {}).get(key) or []))
        rng.shuffle(pool)
        items = []
        for text in pool[:rng.randint(2, 4)]:
            if ctx.can_fill(text):
                try:
                    items.append(ctx.fill(text))
                except CannotFill:
                    pass
        for _ in range(rng.randint(0, 2)):
            at = ctx.say("filler")
            if at is not None:
                items.append(at)
        heads = titles.get(rng.choice(["memo", "report", "meeting",
                                       "todo"])) or []
        if items:
            if heads:
                ctx.doc.add(Heading(rng.choice(heads), level=2))
            for at in items:
                ctx.doc.add(Para(at))


def paginate(doc, rng):
    """Long PDF documents run over several pages: a new page every 2-4
    sections (a section starts at a heading)."""
    blocks = [b for page in doc.pages for b in page]
    sections, current = [], []
    for b in blocks:
        if isinstance(b, Heading) and current:
            sections.append(current)
            current = []
        current.append(b)
    if current:
        sections.append(current)
    if len(sections) < 2:
        return
    step = {"other": (1, 1), "contract": (1, 3), "terms": (1, 3),
            "brochure": (1, 2)}.get(
        doc.doc_type, (2, 4))
    pages, page, left = [], [], rng.randint(*step)
    for sec in sections:
        if left == 0:
            pages.append(page)
            page, left = [], rng.randint(*step)
        page.extend(sec)
        left -= 1
    if page:
        pages.append(page)
    doc.pages = pages


def all_atexts(doc):
    """Every AText of the document (for noise and the truth map)."""
    for block in doc.blocks():
        if isinstance(block, (Para, Heading)):
            yield block.at, True
        elif isinstance(block, Columns):
            yield block.left, True
            yield block.right, True
        elif isinstance(block, Table):
            for row in block.rows:
                for cell in row:
                    yield cell.at, True
                    if cell.raw is not None:
                        yield cell.raw, False
    for key in ("footer_line",):
        at = doc.meta.get(key)
        if at is not None:
            yield at, True


def apply_noise(doc, ctx, rng):
    noised = False
    ocr = rng.random() < 0.03
    spaces = rng.random() < 0.10
    for at, displayed in all_atexts(doc):
        if not displayed:
            continue                     # spreadsheet values stay as stored
        if ctx.digits:
            NZ.convert_digits(at, ctx.digits)
        if ctx.no_accents:
            NZ.drop_accents(at)
        if spaces:
            NZ.extra_spaces(at, rng)
        if ocr and len(at.text) > 20:
            NZ.ocr_noise(at, rng)
            noised = True
    return noised


def file_name(rng, doc, plan, number):
    title = (doc.meta.get("title_text") or plan["type"]).strip()
    # letters, digits and combining marks (Devanagari vowel signs)
    title = "".join(ch for ch in title if ch in " -_" or
                    unicodedata.category(ch)[0] in "LNM")
    title = "_".join(title.split())[:40] or plan["type"]
    d = plan.get("date")
    r = rng.random()
    if d and r < 0.4:
        base = "%s_%d-%03d" % (title, d.year, number)
    elif d and r < 0.6:
        base = "%s_%04d%02d%02d" % (title, d.year, d.month, d.day)
    elif r < 0.8:
        base = "%s %d" % (title, number)
    else:
        base = title
    return base


def build_document(rng, biz, plan, rules, split, index):
    loc = biz.loc
    lid = pick_layout(rng, plan, loc, rules, split)
    if lid is None:
        return None
    from gen.layouts.common import REGISTRY
    info = REGISTRY[lid]
    S = plan.get("S")
    ctx = DocCtx(rng, biz, S, plan.get("C"), plan["type"], plan["kind"],
                 lid, rules, date=plan.get("date"), old=plan.get("old", False))
    ctx.doc.direction = plan.get("direction", "none")
    ctx.doc.meta["scenario"] = plan.get("scenario")
    ctx.doc.meta["sender_name"] = plan.get("sender_name")
    ctx.doc.meta["sender_address"] = plan.get("sender_address")
    if plan["type"] == "letter" and ctx.doc.date is None:
        ctx.doc.date = plan["date"]
    try:
        doc = info["fn"](ctx)
    except CannotFill:
        return None
    if not any(True for _ in doc.blocks()):
        return None
    if ctx.doc.direction == "purchase":
        doc.traps.add("T4")
    fmt = weighted(rng, FORMATS[plan["type"]])
    if fmt == "csv" and not any(isinstance(b, Table) for b in doc.blocks()):
        fmt = "txt"
    if fmt == "csv" and plan["type"] in ("financials", "registration"):
        fmt = "xlsx"                 # keeps the signature and auditor lines
    if fmt == "xlsx" and plan["kind"] in ("receipt", "credit_note"):
        fmt = "pdf"                  # nobody keeps a till receipt in Excel
    p_terms = {"invoice": (0.6, 0.35), "quote": (0.85, 0.6)}.get(
        plan["kind"])
    if fmt in ("pdf", "docx") and p_terms and rng.random() < p_terms[
            0 if biz.country in TERMS_ON_BACK else 1]:
        add_terms_page(ctx)
    if plan["type"] == "brochure":
        add_web_sections(ctx)
    if plan["type"] == "other" and plan.get("S") is None:
        add_note_sections(ctx)
    if fmt == "pdf" and plan["type"] in ("contract", "terms", "other",
                                          "brochure"):
        paginate(doc, rng)
    if fmt == "pdf" and plan["type"] in ("invoice", "quote") and \
            rng.random() < 0.3:
        doc.meta["side_by_side"] = True
    noised = apply_noise(doc, ctx, rng)
    truth_map = {}
    for at, _ in all_atexts(doc):
        for sp in at.spans:
            key = (sp["label"], at.text[sp["s"]:sp["e"]])
            if sp.get("truth") is not None and (noised is False) and \
                    sp.get("norm", True):
                truth_map.setdefault(key, sp["truth"])
                # Word headings come out in upper case (ingest.py)
                truth_map.setdefault((key[0], key[1].lower()), sp["truth"])
    pieces, sources = R.render(doc, fmt, rng, ctx)
    return {"doc": doc, "ctx": ctx, "fmt": fmt, "pieces": pieces,
            "sources": sources, "noised": noised, "truth_map": truth_map,
            "layout": lid, "plan": plan}


# ---------------------------------------------------------------------
#  one folder
# ---------------------------------------------------------------------
def make_folder_docs(split, index):
    """[(doc id, chunk texts, sources)] of a folder, for check 2."""
    return make_folder(split, index, with_sources=True)[2]


def make_folder(split, index, traps_mode=False, locale=None, lang=None,
                with_sources=False):
    """One folder: (chunk records, folder truth). locale / lang force the
    locale or the language (--sample, tests, language balancing)."""
    rng = random.Random(folder_seed(split, index))
    loc_code = locale or choose_locale(rng, split, index, lang)
    act, held_act = choose_activity(rng, split)
    others = [a for a in D.activities() if not a.get("holdout")]
    biz = B.make_business(rng, loc_code, act, client_locales(loc_code),
                          others)
    rules = split_rules(split, held_act)
    plans = compose(rng, biz, split)
    if traps_mode:
        plans = [p for p in plans if p["type"] in ("invoice", "brochure",
                                                   "financials", "letter",
                                                   "registration")]
        if biz.presence.get("revenue"):
            plans.append({"type": "financials", "kind": "financials",
                          "S": biz, "C": None,
                          "date": min(datetime.date(max(biz.revenue) + 1, 5,
                                                    10), REF)})
    folder_id = "%s-%06d" % (split, index)
    chunks, docs_info, per_doc = [], [], []
    names_used = set()
    seen = new_seen()
    for k, plan in enumerate(plans):
        built = build_document(rng, biz, plan, rules, split, index)
        if built is None:
            continue
        doc, ctx = built["doc"], built["ctx"]
        doc_id = "%s-%02d" % (folder_id, k)
        name = file_name(rng, doc, plan, rng.randint(1, 999))
        base, n = name, 2
        while name + EXT[built["fmt"]] in names_used:   # unique in a folder
            name = "%s (%d)" % (base, n)
            n += 1
        name += EXT[built["fmt"]]
        names_used.add(name)
        by_business = plan.get("S") is biz
        business_is_c = plan.get("C") is biz
        for ordinal, (page, kind, text, spans, cut, traps) in enumerate(
                built["pieces"]):
            truth = {}
            for i, (s, e, label) in enumerate(spans):
                t = built["truth_map"].get((label, text[s:e])) or \
                    built["truth_map"].get((label, text[s:e].lower()))
                if t is not None and label in config.KIND_OF_LABEL:
                    truth[str(i)] = t
            trap_set = set(traps) | set(doc.traps)
            if not spans:
                trap_set.add("T12")
            if plan["type"] == "invoice" and any(
                    lab == "DOC_TOTAL" for _, _, lab in spans):
                trap_set.add("T1")    # an invoice total, never revenue
            chunks.append({
                "id": "%s-%02d" % (doc_id, ordinal), "split": split,
                "folder": folder_id, "doc": doc_id, "file_name": name,
                "source": built["fmt"], "chunk_kind": kind, "page": page,
                "ordinal": ordinal, "locale": loc_code,
                "lang": biz.loc["lang"], "doc_type": plan["type"],
                "direction": doc.direction, "layout": built["layout"],
                "templates": sorted(set(doc.templates)),
                "traps": sorted(trap_set), "noised": built["noised"],
                "text": text, "spans": [[s, e, l] for s, e, l in spans],
                "cut": [[s, e] for s, e in cut], "truth": truth})
            if by_business or business_is_c:
                record_seen(seen, spans, text, built["truth_map"],
                            by_business, plan)
        docs_info.append({"doc": doc_id, "file_name": name,
                          "doc_type": plan["type"], "kind": plan["kind"],
                          "direction": doc.direction,
                          "layout": built["layout"], "format": built["fmt"],
                          "date": plan["date"].isoformat()
                          if plan.get("date") else None,
                          "subject": "business" if by_business else
                          ("sister" if plan.get("sister") else
                           ("none" if plan.get("S") is None else "other")),
                          "business_is_counterparty": business_is_c,
                          "private_customer": isinstance(plan.get("C"),
                                                         dict) and
                          plan["type"] == "invoice" and by_business,
                          "scenario": plan.get("scenario")})
        if with_sources:
            per_doc.append((doc_id, [p[2] for p in built["pieces"]],
                            built["sources"]))
    truth = folder_truth(biz, seen, docs_info, folder_id, split, loc_code,
                         held_act)
    if with_sources:
        return chunks, truth, per_doc
    return chunks, truth


# ---------------------------------------------------------------------
#  folder truth: what really appeared in the business's documents
# ---------------------------------------------------------------------
def new_seen():
    return {"labels": set(), "reg": {}, "phones": set(), "emails": set(),
            "urls": set(), "services": set(), "activities": set(),
            "clients": set(), "names": set(), "founded": None,
            "staff": None, "revenue": {}, "capital": None,
            "legal_form": None, "act_code": None, "certs": set(),
            "hours": set(), "managers": set(), "addresses": set(),
            "private_docs": set(), "rev_years": set()}


def record_seen(seen, spans, text, truth_map, by_business, plan):
    for s, e, label in spans:
        value = text[s:e]
        t = truth_map.get((label, value))
        if by_business:
            seen["labels"].add(label)
            if label == "S_REG_ID" and t:
                seen["reg"][t["compact"]] = t["type"]
            elif label == "S_PHONE" and t:
                seen["phones"].add(t["e164"])
            elif label == "S_EMAIL" and t:
                seen["emails"].add(t["value"])
            elif label == "S_URL" and t:
                seen["urls"].add(t["host"])
            elif label == "SERVICE":
                seen["services"].add(value)
            elif label == "ACTIVITY":
                seen["activities"].add(value)
            elif label == "C_NAME":
                if plan["type"] in ("invoice", "quote", "contract", "letter",
                                    "brochure"):
                    seen["clients"].add(value)
            elif label == "S_NAME":
                seen["names"].add(value)
            elif label == "S_PERSON":
                seen["managers"].add(value)
            elif label == "S_ADDRESS":
                seen["addresses"].add(value)
            elif label == "CERT":
                seen["certs"].add(value)
            elif label == "HOURS":
                seen["hours"].add(value)
            elif label == "FOUNDED" and t:
                seen["founded"] = t
            elif label == "STAFF" and t:
                seen["staff"] = t
            elif label == "LEGAL_FORM" and t:
                seen["legal_form"] = t["code"]
            elif label == "ACTIVITY_CODE" and t:
                seen["act_code"] = t
            elif label == "CAPITAL" and t:
                seen["capital"] = t
            elif label == "REVENUE":
                seen["revenue_seen"] = True
            elif label == "REVENUE_YEAR" and t:
                seen["rev_years"].add(t["year"])
        else:                                 # the business is C here
            if label == "C_REG_ID" and t:
                seen["reg"][t["compact"]] = t["type"]
            if label in ("C_NAME", "C_ADDRESS", "C_REG_ID"):
                seen["labels"].add(label + "@C")


def folder_truth(biz, seen, docs_info, folder_id, split, loc_code,
                 held_act):
    """The truth record of a folder (10.8), after generation: a fact is
    'found' only if it really appeared in a document of the business."""
    lab = seen["labels"]
    # the most recent revenue year that really appeared (an older
    # statement may be the only one in the folder)
    shown = sorted(y for y in seen["rev_years"] if y in biz.revenue)
    y = shown[-1] if shown else (max(biz.revenue) if biz.revenue else None)
    private_docs = sum(1 for d in docs_info if d.get("private_customer"))
    org_clients = sorted(seen["clients"])
    found = {
        "business_name": "S_NAME" in lab,
        "address": "S_ADDRESS" in lab,
        "activity": "ACTIVITY" in lab,
        "services": "SERVICE" in lab,
        "legal_form": "LEGAL_FORM" in lab or any(
            N.parse_legal_form(name, biz.country) for name in
            seen["names"]),
        "reg_id": bool(seen["reg"]),
        "contact": "S_PHONE" in lab or "S_EMAIL" in lab,
        "founded": "FOUNDED" in lab,
        "staff": "STAFF" in lab,
        "revenue": "REVENUE" in lab,
        "clients": bool(org_clients) or private_docs >= 3,
        "activity_code": "ACTIVITY_CODE" in lab,
        "capital": "CAPITAL" in lab,
        "manager": "S_PERSON" in lab,
    }
    current_address = biz.address["one"]
    truth = {
        "folder": folder_id, "split": split, "locale": loc_code,
        "lang": biz.loc["lang"], "country": biz.country,
        "activity_id": biz.act["id"], "heldout_activity": held_act,
        "legal_name": biz.legal, "trading_name": biz.trading,
        "legal_form": {"code": biz.form["code"], "class": biz.cls},
        "address": current_address,
        "address_variants": [biz.address["one"],
                             "\n".join(biz.address["lines"])],
        "addresses_seen": sorted(seen["addresses"]),
        "reg_ids": [{"compact": c, "type": t}
                    for c, t in sorted(seen["reg"].items())],
        "phones": sorted(seen["phones"]), "emails": sorted(seen["emails"]),
        "websites": sorted(seen["urls"]),
        "manager": biz.manager["full"] if seen["managers"] else None,
        "founded": {"year": biz.founded.year, "month": biz.founded.month,
                    "day": biz.founded.day},
        "staff": biz.staff,
        "revenue": {"year": y, "amount": biz.revenue.get(y),
                    "currency": biz.loc["currency"]} if y else None,
        "revenue_all": {str(k): v for k, v in biz.revenue.items()},
        "capital": biz.capital,
        "activity_code": {"system": biz.act_system, "code": biz.act_code}
        if biz.act_code else None,
        "activities": sorted(seen["activities"]),
        "services": sorted(seen["services"]),
        "clients": {"organisations": org_clients,
                    "private_customer_documents": private_docs},
        "certifications": sorted(seen["certs"]),
        "hours": sorted(seen["hours"]),
        "found": found,
        "outdated": biz.outdated,
        "sister": {"legal_name": biz.sister.legal} if biz.sister else None,
        "partner_locales": sorted({o.loc["code"] for o in
                                   biz.clients + biz.suppliers}),
        "documents": [{k: v for k, v in d.items() if not k.startswith("_")}
                      for d in docs_info],
    }
    return truth


# ---------------------------------------------------------------------
#  splits
# ---------------------------------------------------------------------
def _worker(args):
    split, index, traps_mode = args[:3]
    lang = args[3] if len(args) > 3 else None
    import gen.layouts                                   # noqa: F401
    return make_folder(split, index, traps_mode, lang=lang)


def generate_split(preset, split, workers=None, out_dir=None, log=print,
                   train_texts=None):
    settings = config.PRESETS[preset]
    out_dir = pathlib.Path(out_dir or config.data_dir(preset))
    out_dir.mkdir(parents=True, exist_ok=True)
    traps_mode = split == "traps"
    target_chunks = settings["traps_chunks"] if traps_mode else None
    # traps: folders until traps_chunks chunks (upper bound for the pool)
    n = settings["folders"].get(split, 0) if not traps_mode else \
        target_chunks // 4 + 10
    workers = workers or max(1, min(4, (multiprocessing.cpu_count() or 1)))
    began = time.time()
    chunks_out = gzip.open(out_dir / ("%s.jsonl.gz" % split), "wt",
                           encoding="utf-8")
    folders_out = gzip.open(out_dir / ("folders_%s.jsonl.gz" % split), "wt",
                            encoding="utf-8")
    n_chunks = n_folders = dropped = 0
    lang_chunks = {}
    ctx_mp = multiprocessing.get_context("spawn")

    def jobs():
        i = 0
        while True:
            if n is not None and i >= n:
                return
            yield (split, i, traps_mode)
            i += 1

    with ctx_mp.Pool(workers) as pool:
        for chunks, truth in pool.imap(_worker, jobs(), chunksize=4):
            if traps_mode and n_chunks >= target_chunks:
                break
            kept = []
            for c in chunks:
                if train_texts is not None and \
                        nfkc(c["text"]) in train_texts:
                    dropped += 1
                    continue
                kept.append(c)
            for c in kept:
                chunks_out.write(json.dumps(c, ensure_ascii=False) + "\n")
                lang_chunks[c["lang"]] = lang_chunks.get(c["lang"], 0) + 1
            folders_out.write(json.dumps(truth, ensure_ascii=False,
                                         default=str) + "\n")
            n_chunks += len(kept)
            n_folders += 1
            if n_folders % 200 == 0:
                log("  %s: %d folders, %d chunks (%.0fs)" %
                    (split, n_folders, n_chunks, time.time() - began))
            if traps_mode and n_chunks >= target_chunks:
                pool.terminate()
                break
        # languages are drawn in turn, but folders differ in size: top
        # up the languages that fall under 9% of the chunks of train
        # (check 3 wants 10% +- 2 points), with extra folders
        extra = 0
        index = n or 0
        while split == "train" and extra < max(10, (n or 0) // 5):
            share = {lg: lang_chunks.get(lg, 0) / max(1, n_chunks)
                     for lg in config.LANGS}
            low = min(config.LANGS, key=lambda lg: share[lg])
            if share[low] >= 0.09:
                break
            chunks, truth = pool.apply(_worker, ((split, index, False,
                                                  low),))
            index += 1
            extra += 1
            for c in chunks:
                chunks_out.write(json.dumps(c, ensure_ascii=False) + "\n")
                lang_chunks[c["lang"]] = lang_chunks.get(c["lang"], 0) + 1
            folders_out.write(json.dumps(truth, ensure_ascii=False,
                                         default=str) + "\n")
            n_chunks += len(chunks)
            n_folders += 1
    chunks_out.close()
    folders_out.close()
    log("  %s: %d folders, %d chunks, %d duplicates of train dropped "
        "(%.0fs)" % (split, n_folders, n_chunks, dropped,
                     time.time() - began))
    return {"folders": n_folders, "chunks": n_chunks, "dropped": dropped}


def nfkc(text):
    return unicodedata.normalize("NFKC", text)


def read_chunks(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def generate(preset, splits=None, workers=None, log=print):
    out_dir = config.data_dir(preset)
    stats = {}
    splits = splits or config.SPLITS
    train_texts = None
    if "train" in splits:
        stats["train"] = generate_split(preset, "train", workers, out_dir,
                                        log)
    train_path = out_dir / "train.jsonl.gz"
    if train_path.exists():
        train_texts = {nfkc(c["text"]) for c in read_chunks(train_path)}
    for split in splits:
        if split == "train":
            continue
        stats[split] = generate_split(preset, split, workers, out_dir, log,
                                      train_texts)
    with open(out_dir / "generate_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    return stats


# ---------------------------------------------------------------------
#  the hold-out draw (run once, in Phase 1)
# ---------------------------------------------------------------------
def draw_holdout(log=print):
    import gen.layouts                                   # noqa: F401
    from gen.layouts.common import REGISTRY
    if H.FILE.exists():
        log("gen/holdout.json already exists - the draw is done ONCE.")
        return json.loads(H.FILE.read_text(encoding="utf-8"))
    sentences = {}
    for key in D.data_keys():
        path = D.DATA / key / "sentences.json"
        if path.exists():
            sentences[key] = json.loads(path.read_text(encoding="utf-8"))
    result = H.draw(REGISTRY, sentences)
    H.FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1,
                                 sort_keys=True), encoding="utf-8")
    H.reset_cache()
    H.move_test_items(result, REGISTRY, log)
    log("hold-out drawn: %d layouts, %s" % (
        len(result["layouts"]),
        {g: sum(1 for v in result["layouts"].values() if v == g)
         for g in ("train", "D", "T", "locale")}))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(config.PRESETS))
    ap.add_argument("--splits", nargs="*")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--draw-holdout", action="store_true")
    ap.add_argument("--sample", help="a locale, e.g. fr-FR")
    ap.add_argument("--index", type=int, default=0)
    args = ap.parse_args()
    if args.draw_holdout:
        draw_holdout()
        return 0
    if args.sample:
        import gen.layouts                               # noqa: F401
        chunks, truth = make_folder("sample", args.index,
                                    locale=args.sample)
        for c in chunks:
            print("=" * 70)
            print(c["file_name"], c["doc_type"], c["layout"],
                  c["source"], c["chunk_kind"], c["traps"])
            print("-" * 70)
            print(c["text"])
            for s, e, lab in c["spans"]:
                print("   %-14s %r" % (lab, c["text"][s:e]))
        print(json.dumps(truth, ensure_ascii=False, indent=1, default=str))
        return 0
    if args.check:
        from gen import checks
        ok = checks.run(args.preset)
        return 0 if ok else 1
    if args.preset:
        generate(args.preset, args.splits, args.workers)
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
