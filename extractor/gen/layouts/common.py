"""
common.py - building blocks shared by the layouts.

A layout is a function  fn(ctx) -> Doc  registered with @layout(id, ...).
It decides WHICH blocks appear and in WHAT order; every word comes from
the lexicon (ctx.kw, ctx.title, ctx.say) and every value from the
business truth (ctx.name, ctx.money ...).
"""
import datetime

from gen.ctx import CannotFill
from gen.doc import Blank, Cell, Columns, Heading, Para, Table
from gen.text import AText

REGISTRY = {}


def layout(lid, doc_type, kind=None, family=None, locales=None):
    """Registers a layout. family / locales: registration layouts are
    tied to a country family and its locales."""
    def deco(fn):
        REGISTRY[lid] = {"id": lid, "fn": fn, "doc_type": doc_type,
                         "kind": kind or doc_type, "family": family,
                         "locales": locales}
        return fn
    return deco


# ---------------------------------------------------------------------
#  small text helpers
# ---------------------------------------------------------------------
def lines(*parts):
    """Joins AText / str parts with newlines, skipping None."""
    out = AText()
    first = True
    for part in parts:
        if part is None:
            continue
        if not first:
            out.add("\n")
        out.add(part)
        first = False
    return out


def kv(ctx, concept, value, sep=None):
    """'Label: value' where value is an AText or a str (O)."""
    out = AText(ctx.label(concept, sep))
    out.add(value if isinstance(value, AText) else AText(str(value)))
    return out


def try_(fn, *args, **kw):
    """Calls a value maker; None when the fact is missing."""
    try:
        return fn(*args, **kw)
    except CannotFill:
        return None


def pick(ctx, items):
    return ctx.rng.choice(items)


def maybe(ctx, p):
    return ctx.rng.random() < p


# ---------------------------------------------------------------------
#  organisation blocks
# ---------------------------------------------------------------------
def org_block(ctx, org, label_concept=None, contact=True, ids=True,
              person=False, multiline_address=None, private=False):
    """The block of an issuer or a customer:
        [label]
        Name
        address (1-3 lines)
        Tel / Fax / E-mail / Web
        registration numbers"""
    rng = ctx.rng
    parts = []
    if label_concept:
        parts.append(AText(ctx.kw(label_concept) +
                           (ctx.colon() if rng.random() < 0.5 else "")))
    if isinstance(org, dict):                   # a private person (O)
        hon = ""
        if rng.random() < 0.4:
            from gen.names import honorific
            hon = honorific(rng, ctx.lex, org["gender"])
        name = org["full"]
        if hon.startswith("~"):
            name = name + hon[1:]
        elif hon:
            name = hon + " " + name
        parts.append(AText(name))
        parts.append(AText("\n".join(org["address"]["lines"])))
        return lines(*parts)
    parts.append(ctx.name(org))
    if multiline_address is None:
        multiline_address = rng.random() < 0.7
    parts.append(ctx.addr(org, multiline=multiline_address))
    if contact and ctx.role(org) == "S":
        cl = contact_lines(ctx, org)
        if cl is not None:
            parts.append(cl)
    elif contact and rng.random() < 0.3:
        tel = try_(ctx.phone, org)
        if tel is not None and ctx.role(org) != "S":
            parts.append(AText(ctx.kw("tel") + " ").add(tel))
    if person and ctx.role(org) == "S" and rng.random() < 0.5:
        p = try_(ctx.person, org)
        if p is not None and ctx.biz.presence.get("manager", True):
            parts.append(AText(org.manager_title + " ").add(p) if
                         rng.random() < 0.6 else kv(ctx, "manager", p))
    if ids:
        idl = id_lines(ctx, org)
        if idl is not None:
            parts.append(idl)
    return lines(*parts)


def presence_ok(ctx, org, fact):
    if org is ctx.biz:
        return ctx.biz.presence.get(fact, True)
    return True


def contact_lines(ctx, org, one_line=None):
    rng = ctx.rng
    items = []
    if presence_ok(ctx, org, "phone"):
        tel = try_(ctx.phone, org)
        if tel is not None:
            items.append(AText(ctx.kw("tel") + (" " if rng.random() < 0.5
                                                 else ctx.colon() + " "))
                         .add(tel))
    if getattr(org, "fax", None) and rng.random() < 0.8:
        items.append(AText(ctx.kw("fax") + " ").add(ctx.fax(org)))
    if presence_ok(ctx, org, "email") and org.email:
        items.append(AText(ctx.kw("email") + ctx.colon() + " ").add(
            ctx.email(org)) if rng.random() < 0.6 else ctx.email(org))
    if presence_ok(ctx, org, "website") and (org.website or org.social) \
            and rng.random() < 0.7:
        items.append(ctx.url(org))
    if not items:
        return None
    if one_line is None:
        one_line = rng.random() < 0.4
    return AText.join(items, rng.choice([" – ", " | ", "  ", " · "])) \
        if one_line else lines(*items)


def id_lines(ctx, org, max_ids=None):
    if not getattr(org, "reg_ids", None):
        return None
    if not presence_ok(ctx, org, "reg_id"):
        return None
    rng = ctx.rng
    ids = list(org.reg_ids)
    k = len(ids) if max_ids is None else min(max_ids, len(ids))
    k = rng.randint(1, k) if k else 0
    out = [ctx.reg_id(org, which=i) for i in range(k)]
    if not out:
        return None
    return AText.join(out, rng.choice(["\n", " – ", "  "])) \
        if len(out) > 1 else out[0]


# ---------------------------------------------------------------------
#  invoices: data
# ---------------------------------------------------------------------
QTY = {"hour": (1, 40), "day": (1, 20), "month": (1, 12), "year": (1, 2),
       "flat": (1, 1), "kg": (1, 50), "m2": (5, 300), "m": (2, 200),
       "night": (1, 7), "person": (2, 120), "session": (1, 12),
       "km": (10, 900), "page": (1, 60), "word": (300, 12000),
       "visit": (1, 4), "box": (1, 30), "set": (1, 10), "lesson": (1, 20),
       "license": (1, 25), "user": (1, 50), "piece": (1, 40)}


def invoice_data(ctx, n_lines=None, allow_extras=True):
    """Lines, subtotal, tax and total of an invoice / quote / receipt."""
    rng = ctx.rng
    S = ctx.S
    services = S.services or [{"name": "Service", "price": 50.0,
                               "unit": "flat"}]
    n = n_lines or rng.choice([1, 1, 2, 2, 3, 3, 4, 5, 6, 8])
    chosen = [rng.choice(services) for _ in range(n)] if n > len(services) \
        else rng.sample(services, n)
    loc = ctx.loc
    decimals = 2 if loc["cents"] else 0
    vat_rates = list(loc.get("vat") or [])
    exempt = (S.cls == "sole_trader" and loc["country"] in ("FR", "BE") and
              rng.random() < 0.5) or not vat_rates
    rate = 0 if exempt else vat_rates[0]
    items = []
    for s in chosen:
        lo, hi = QTY.get(s["unit"], (1, 10))
        qty = rng.randint(lo, min(hi, lo + 12)) if s["unit"] != "word" \
            else rng.randint(lo, hi)
        price = round(s["price"] * rng.uniform(0.92, 1.08),
                      decimals)
        if price <= 0:
            price = 1.0
        amount = round(qty * price, decimals)
        line_rate = rate
        if not exempt and len(vat_rates) > 1 and rng.random() < 0.15:
            line_rate = rng.choice(vat_rates[1:])
        items.append({"name": s["name"], "qty": qty, "unit": s["unit"],
                      "price": price, "amount": amount, "rate": line_rate,
                      "service": True})
    extras = []
    boost = ctx.rules.get("trap_boost", 1.0)
    if allow_extras and rng.random() < 0.4 * boost:
        kinds = ["shipping", "fee", "discount"]
        if ctx.doc.doc_type == "quote":
            kinds.append("deposit")
        kind = rng.choice(kinds)
        base = sum(i["amount"] for i in items)
        if kind == "shipping":
            val = round(rng.uniform(5, 40) * loc["usd_rate"] *
                        loc["price_level"], decimals)
        elif kind == "fee":
            val = round(rng.uniform(3, 30) * loc["usd_rate"] *
                        loc["price_level"], decimals)
        elif kind == "discount":
            val = -round(base * rng.choice([0.05, 0.1, 0.15]), decimals)
        else:
            val = -round(base * rng.choice([0.2, 0.3, 0.5]), decimals)
        extras.append({"kind": kind, "amount": val, "rate": rate})
    subtotal = round(sum(i["amount"] for i in items) +
                     sum(e["amount"] for e in extras if e["kind"] in
                         ("shipping", "fee", "discount")), decimals)
    tax = round(sum(i["amount"] * i["rate"] / 100 for i in items) +
                sum(e["amount"] * e["rate"] / 100 for e in extras
                    if e["kind"] in ("shipping", "fee", "discount")),
                decimals)
    total = round(subtotal + tax, decimals)
    deposit = sum(-e["amount"] for e in extras if e["kind"] == "deposit")
    due = round(total - deposit, decimals)
    d = ctx.doc.date
    return {"items": items, "extras": extras, "subtotal": subtotal,
            "tax": tax, "rate": rate, "total": total, "deposit": deposit,
            "due": due, "exempt": exempt, "decimals": decimals,
            "number": ctx.doc_number("invoice"),
            "order": ctx.doc_number("order") if rng.random() < 0.4 else None,
            "customer_no": ("C%05d" % rng.randint(1, 99999))
            if rng.random() < 0.35 else None,
            "due_date": d + datetime.timedelta(days=rng.choice(
                [0, 8, 10, 14, 15, 30, 30, 30, 45, 60])),
            "delivery_date": d - datetime.timedelta(days=rng.randint(0, 20))}


def money_cell(ctx, value, label=None, style="bare"):
    """A table cell with an amount, and its spreadsheet (raw) twin."""
    at = ctx.money(value, label, style=style)
    raw = ctx.raw_money(value, label)
    return Cell(at, raw)


def qty_cell(ctx, q):
    text = ctx.fmt.num(q) if q >= 1000 else str(q)
    return Cell(AText(text, trap="T6"), AText(str(q), trap="T6"))


def items_table(ctx, inv, cols=None, with_rate=None, currency_style="bare"):
    """The table of invoice lines. cols: list of column keys among
    no, code, description, qty, unit, unit_price, rate, amount."""
    rng = ctx.rng
    if cols is None:
        cols = pick(ctx, [["description", "qty", "unit_price", "amount"],
                          ["no", "description", "qty", "unit", "unit_price",
                           "amount"],
                          ["description", "qty", "unit_price", "rate",
                           "amount"],
                          ["code", "description", "qty", "unit_price",
                           "amount"],
                          ["description", "amount"],
                          ["no", "description", "unit", "qty", "unit_price",
                           "amount"]])
    header = []
    for c in cols:
        concept = {"no": "no", "code": "item_code", "description":
                   "description", "qty": "qty", "unit": "unit",
                   "unit_price": "unit_price", "rate": "vat_rate",
                   "amount": "amount"}[c]
        header.append(Cell(ctx.kw(concept)))
    rows = [header]
    k = 0
    for item in inv["items"]:
        k += 1
        row = []
        for c in cols:
            if c == "no":
                row.append(Cell(str(k)))
            elif c == "code":
                row.append(Cell(AText(item_code(ctx), trap="T6")))
            elif c == "description":
                row.append(Cell(ctx.service(item["name"])))
            elif c == "qty":
                row.append(qty_cell(ctx, item["qty"]))
            elif c == "unit":
                row.append(Cell(ctx.unit(item["unit"])))
            elif c == "unit_price":
                row.append(money_cell(ctx, item["price"], "PRICE",
                                      currency_style))
            elif c == "rate":
                row.append(Cell(AText(ctx.fmt.percent(item["rate"]),
                                      trap="T6")))
            elif c == "amount":
                row.append(money_cell(ctx, item["amount"], "LINE_TOTAL",
                                      currency_style))
        rows.append(row)
    for e in inv["extras"]:
        if e["kind"] == "deposit":
            continue
        row = []
        for c in cols:
            if c == "description":
                row.append(Cell(AText(ctx.kw(e["kind"]), trap="T9")))
            elif c == "amount":
                row.append(Cell(AText(ctx.money(e["amount"], None,
                                                style=currency_style).text,
                                      trap="T9")))
            elif c == "rate":
                row.append(Cell(ctx.fmt.percent(e["rate"])))
            else:
                row.append(Cell(""))
        rows.append(row)
    return Table(rows)


def item_code(ctx):
    rng = ctx.rng
    if ctx.country == "IN":
        return str(rng.choice([9954, 9983, 9987, 1905, 8471, 9963, 9973]))
    style = rng.random()
    if style < 0.4:
        return "%s-%03d" % (rng.choice(["REF", "ART", "SKU", "P"]),
                            rng.randint(1, 999))
    if style < 0.7:
        return str(rng.randint(100000, 999999))
    return "%d%09d" % (rng.randint(300, 899), rng.randint(0, 999999999))


def items_lines(ctx, inv, style=None):
    """Invoice lines written as text lines (no table)."""
    rng = ctx.rng
    out = []
    for item in inv["items"]:
        line = AText()
        if rng.random() < 0.5:
            line.add(AText(str(item["qty"]), trap="T6"))
            line.add(" x ")
            line.add(ctx.service(item["name"]))
            line.add(" @ " if rng.random() < 0.3 else " – ")
            line.add(ctx.money(item["price"], "PRICE"))
            line.add(" = " if rng.random() < 0.5 else "  ")
            line.add(ctx.money(item["amount"], "LINE_TOTAL"))
        else:
            line.add(ctx.service(item["name"]))
            line.add(rng.choice(["  ", " ...... ", " : ", "\t"]))
            line.add(ctx.money(item["amount"], "LINE_TOTAL"))
        out.append(line)
    for e in inv["extras"]:
        if e["kind"] == "deposit":
            continue
        out.append(AText(ctx.kw(e["kind"]) + "  " +
                         ctx.money(e["amount"]).text, trap="T9"))
    return lines(*out)


def totals_lines(ctx, inv, style="kv", total_concept=None):
    """Subtotal / tax / total lines. Only the final payable amount is
    DOC_TOTAL; subtotal and tax are O (rule R7)."""
    rng = ctx.rng
    out = []
    if inv["tax"] or rng.random() < 0.5:
        out.append(kv(ctx, rng.choice(["subtotal", "total_excl"]),
                      ctx.money(inv["subtotal"])))
    if inv["tax"]:
        tax_label = ctx.kw("vat")
        if rng.random() < 0.6:
            tax_label = "%s %s" % (tax_label, ctx.fmt.percent(inv["rate"]))
        out.append(AText(tax_label + ctx.colon() + " ").add(
            ctx.money(inv["tax"])).mark_trap("T6"))
    concept = total_concept or rng.choice(["total_incl", "total_payable",
                                           "total"])
    total_line = kv(ctx, concept, ctx.money(inv["total"], "DOC_TOTAL"))
    total_line.mark_trap("T1")
    out.append(total_line)
    if inv["deposit"]:
        out.append(AText(ctx.kw("deposit") + ctx.colon() + " " +
                         ctx.money(inv["deposit"]).text, trap="T9"))
        out.append(kv(ctx, "balance_due", ctx.money(inv["due"])))
    return lines(*out)


def totals_rows(ctx, inv, width=2):
    """The totals as extra table rows (label cell, amount cell)."""
    rows = []
    pad = [Cell("")] * (width - 2)
    rows.append(pad + [Cell(ctx.kw("subtotal")),
                       money_cell(ctx, inv["subtotal"])])
    if inv["tax"]:
        rows.append(pad + [Cell(AText("%s %s" % (ctx.kw("vat"),
                                                  ctx.fmt.percent(inv["rate"])),
                                      trap="T6")),
                           money_cell(ctx, inv["tax"])])
    rows.append(pad + [Cell(ctx.kw(ctx.rng.choice(["total_incl",
                                                   "total_payable"]))),
                       money_cell(ctx, inv["total"], "DOC_TOTAL")])
    return rows


def dates_block(ctx, inv, number_concept="invoice_no", show_due=True):
    """Number, issue date (DOC_DATE), due and delivery dates (O, T15)."""
    rng = ctx.rng
    out = [AText(ctx.label(number_concept)).add(AText(inv["number"],
                                                      trap="T6"))]
    date_concept = rng.choice(["date", "invoice_date"])
    out.append(kv(ctx, date_concept, ctx.doc_date()))
    if show_due:
        due = AText(ctx.label("due_date") + ctx.date_o(inv["due_date"]),
                    trap="T15")
        out.append(due)
        if rng.random() < 0.6:
            out.append(AText(ctx.label("delivery_date") +
                             ctx.date_o(inv["delivery_date"]), trap="T15"))
    if inv.get("order"):
        out.append(AText(ctx.label("order_no") + inv["order"], trap="T6"))
    if inv.get("customer_no"):
        out.append(AText(ctx.label("customer_no") + inv["customer_no"],
                         trap="T6"))
    rng.shuffle(out[2:])
    return lines(*out)


def bank_block(ctx, org=None):
    """Bank details: always O (rule R7), trap T6."""
    rng = ctx.rng
    from gen import ids as I
    org = org or ctx.S
    banks = ((ctx.lex.get("orgs") or {}).get("banks") or {}).get(
        ctx.country) or ["Bank"]
    out = [AText(ctx.label("bank") + rng.choice(banks))]
    iban = I.iban(rng, ctx.country)
    if iban:
        out.append(AText(ctx.label("iban") + I.show_iban(rng, iban)))
        if rng.random() < 0.6:
            out.append(AText(ctx.label("bic") + "".join(
                rng.choice("ABCDEFGHKLMNPRSTUVWXYZ") for _ in range(4)) +
                ctx.country + "".join(rng.choice("ABCDEFGH23") for _ in
                                      range(2))))
    else:
        out.append(AText(ctx.label("account_no") + "".join(
            rng.choice("0123456789") for _ in range(rng.randint(10, 16)))))
    at = lines(*out)
    at.mark_trap("T6")
    return at


def payment_terms(ctx):
    at = ctx.phrase("invoice_notes", "payment_terms")
    if at is None:
        return None
    return AText(ctx.label("payment_terms")).add(at) if \
        ctx.rng.random() < 0.4 else at


def amount_words(ctx, value):
    """The amount written in words (T10, always O)."""
    from gen.words import amount_in_words
    words = amount_in_words(ctx.rng, ctx.lang, ctx.loc, value, ctx.lex)
    if not words:
        return None
    intro = ctx.phrase("phrases", "amount_in_words_intro")
    out = AText()
    if intro is not None and ctx.rng.random() < 0.7:
        out.add(intro).add(" " if ctx.lang not in ("zh", "ja") else "")
    else:
        out.add(ctx.label("amount_in_words"))
    out.add(words)
    out.mark_trap("T10")
    return out


def legal_footer(ctx):
    """Legal mentions of the issuer for its country."""
    items = [f for f in ctx.sent.get("legal_footer", [])
             if ctx.country in f.get("countries", [])]
    rng = ctx.rng
    rng.shuffle(items)
    for f in items:
        if ctx.can_fill(f["text"]):
            try:
                return ctx.fill(f["text"], f.get("id"))
            except CannotFill:
                continue
    return None


def title_line(ctx, key, section="doc"):
    return Heading(ctx.title(section, key))


def signature(ctx, org=None):
    org = org or ctx.S
    rng = ctx.rng
    parts = []
    sl = ctx.phrase("phrases", "signature_line")
    if sl is not None and rng.random() < 0.5:
        parts.append(sl)
    if org is not None and ctx.role(org) == "S" and \
            presence_ok(ctx, org, "manager") and rng.random() < 0.7:
        parts.append(ctx.person(org))
        parts.append(AText(org.manager_title))
    if org is not None and rng.random() < 0.6:
        parts.append(ctx.name(org))
    return lines(*parts) if parts else None


def page_line_fn(ctx):
    items = (ctx.sent.get("phrases") or {}).get("page_x_of_y") or \
        ["{p}/{n}"]
    pattern = ctx.rng.choice(items)

    def make(p, n):
        return AText(pattern.replace("{p}", str(p)).replace("{n}", str(n)))
    return make


def footer_line(ctx):
    """A one-line company footer repeated on each page (labelled)."""
    S = ctx.S
    if S is None:
        return None
    rng = ctx.rng
    parts = [ctx.name(S)]
    if rng.random() < 0.7:
        parts.append(ctx.addr(S))
    tel = try_(ctx.phone, S) if presence_ok(ctx, S, "phone") else None
    if tel is not None and rng.random() < 0.6:
        parts.append(tel)
    return AText.join(parts, rng.choice([" – ", " | ", " · ", ", "]))


def prose(ctx, categories, n=None, traps=None, fillers=(0, 2)):
    """A paragraph: sentences of the given categories, plus fillers and
    maybe trap sentences."""
    rng = ctx.rng
    sentences = []
    for cat in categories:
        at = ctx.say(cat)
        if at is not None:
            sentences.append(at)
    for trap in traps or []:
        at = ctx.say("traps", trap=trap)
        if at is not None:
            sentences.append(at)
    for _ in range(rng.randint(*fillers)):
        at = ctx.say("filler")
        if at is not None:
            sentences.insert(rng.randint(0, len(sentences)), at)
    if not sentences:
        return None
    sep = "" if ctx.lang in ("zh", "ja") else " "
    return AText.join(sentences, sep)
