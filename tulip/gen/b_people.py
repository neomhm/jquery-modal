"""
gen/b_people.py - the staff and clients builders: lists of people and
organisations with names (in one cell, or split over columns and joined
back in the locale's order), roles, contact details, addresses and dates.

Every phone, e-mail and date cell is checked with the real helper before
it goes into a sheet; a cell the helper would not read is left empty.
"""
import datetime

import helpers as H
from gen import builders as B
from gen import columns as C
from gen import data as D
from gen import modifiers as M
from gen.sheetkit import Column, Table

REF = datetime.date(2026, 6, 30)
CJK_LANGS = ("zh", "ja", "ko")


def is_cjk(text):
    return bool(text) and all(
        "぀" <= ch <= "ヿ" or "㐀" <= ch <= "鿿" or
        "가" <= ch <= "힯" or "豈" <= ch <= "﫿"
        for ch in text)


# ---------------------------------------------------------------------
#  names split over columns (trap T10)
# ---------------------------------------------------------------------
def name_parts(ctx, people):
    """-> (parts [(key, field_key, [texts])] in the locale's joining
    order, separator) or None."""
    lang = ctx.lang
    given = [p["given"] for p in people]
    family = [p["family"] for p in people]
    if lang in ("zh", "ko"):
        sep = "" if all(is_cjk(g) and is_cjk(f)
                        for g, f in zip(given, family)) else " "
        return [("last", "last_name", family),
                ("first", "first_name", given)], sep
    if lang == "ja":
        return [("last", "last_name", family),
                ("first", "first_name", given)], " "
    if lang == "ru":
        parts = [("last", "last_name", family),
                 ("first", "first_name", given)]
        pats = [p.get("patronymic") for p in people]
        if all(pats) and ctx.rng.random() < 0.5 and \
                ctx.hdr.get("patronymic"):
            parts.append(("patronymic", "patronymic", pats))
        return parts, " "
    parts = [("first", "first_name", given), ("last", "last_name", family)]
    if lang == "es" and ctx.hdr.get("second_last_name") and \
            ctx.rng.random() < 0.4:
        names = D.locale_list(ctx.code, "names") or {}
        pool = names.get("family") or family
        parts.append(("second", "second_last_name",
                      [ctx.rng.choice(pool) for _ in people]))
    return parts, " "


def split_name_columns(ctx, t, people, truth, field="name"):
    """First / last name columns (both orders on the sheet), joined in
    the locale's order by the program. -> True or False."""
    rng = ctx.rng
    got = name_parts(ctx, people)
    if not got:
        return False
    parts, sep = got
    upper_family = rng.random() < 0.2 and ctx.lang in ("fr", "en", "es",
                                                       "it", "ru")
    for key, fkey, texts in parts:
        if key in ("last", "second") and upper_family:
            texts = [x.upper() for x in texts]
        C.text_column(ctx, t, key, ctx.header(fkey), texts, None, None,
                      digits=False)
    keys = [k for k, _, _ in parts]
    shown = list(keys)
    if rng.random() < 0.5:
        shown.reverse()                 # last name first on the sheet
    t.blocks.append(shown)
    args = ", ".join("col({%s})" % k for k in keys)
    t.outs.append((field, "text(join(%r, %s))" % (sep, args)))
    for i, rec in enumerate(truth):
        pieces = [t.col(k).cells[i] for k in keys]
        pieces = [p.strip() for p in pieces if p and p.strip()]
        rec[field] = C.norm_text(sep.join(pieces))
    t.traps.add("T10")
    return True


# ---------------------------------------------------------------------
#  contact columns
# ---------------------------------------------------------------------
def phone_column(ctx, t, key, header, e164s, field, truth):
    cells = []
    for e in e164s:
        if e is None:
            cells.append(None)
            continue
        text = ctx.fmt.phone_text(e)
        cells.append(text if H.phone(text, ctx.code) == (True, e) else None)
    if all(c is None for c in cells):
        return False
    t.add(Column(key, header, cells))
    t.outs.append((field, "phone(col({%s}))" % key))
    for rec, c, e in zip(truth, cells, e164s):
        if c is not None:
            rec[field] = e
    return True


def email_column(ctx, t, key, header, emails, field, truth):
    cells = []
    for e in emails:
        if not e:
            cells.append(None)
            continue
        text = e if ctx.rng.random() < 0.9 else e.capitalize()
        ok, got = H.email(text, ctx.code)
        cells.append(text if ok and got == e.lower() else None)
    if all(c is None for c in cells):
        return False
    t.add(Column(key, header, cells))
    t.outs.append((field, "email(col({%s}))" % key))
    for rec, c in zip(truth, cells):
        if c is not None:
            rec[field] = H.email(c, ctx.code)[1]
    return True


def date_column(ctx, t, key, header, dates, field, truth):
    cells, fmts = [], []
    for d in dates:
        if d is None:
            cells.append(None)
            fmts.append(None)
            continue
        v, fm = ctx.fmt.date(d)
        if H.date(v, ctx.code) != (True, d.isoformat()):
            v, fm = None, None
        cells.append(v)
        fmts.append(fm)
    if all(c is None for c in cells):
        return False
    t.add(Column(key, header, cells, fmts))
    t.outs.append((field, "date(col({%s}))" % key))
    for rec, c, d in zip(truth, cells, dates):
        if c is not None:
            rec[field] = d.isoformat()
    return True


def count_total(ctx, t, name_key):
    """T4 for lists of people: a last row 'Total: 23' in the name
    column (a program must drop it with keep(not_total(...)))."""
    rng = ctx.rng
    words = ctx.values.get("totals") or []
    words = [w for w in words if H.TOTALS and
             any(w.casefold().startswith(x.casefold()) for x in H.TOTALS)]
    if not words or t.n < 8 or t.sections:
        return               # with sections() a one-cell row is a title
    word = rng.choice(words)
    label = rng.choice(["%s: %d", "%s %d", "%s : %d"]) % (word, t.n) \
        if ctx.lang != "fr" else rng.choice(["%s : %d", "%s %d"]) % (word,
                                                                    t.n)
    t.totals = (label, {})
    t.total_label_key = name_key
    t.traps.add("T4")


# ---------------------------------------------------------------------
#  staff
# ---------------------------------------------------------------------
def staff_records(ctx, n):
    rng = ctx.rng
    roles = ctx.words.get("roles") or []
    depts = ctx.words.get("departments") or []
    if not roles:
        return []
    domain_person = ctx.person()
    out = []
    seen = set()
    for _ in range(n * 2):
        if len(out) >= n:
            break
        p = ctx.person()
        if p["full"] in seen:
            continue
        seen.add(p["full"])
        out.append({
            "person": p, "full": p["full"],
            "role": rng.choice(roles),
            "department": rng.choice(depts) if depts else None,
            "email": ctx.email_for(ctx.business_name(), p),
            "phone": ctx.phone(mobile=True),
            "start_date": REF - datetime.timedelta(
                days=rng.randint(20, 365 * 15))})
    del domain_person
    return out


def staff(ctx, plan, *, split_names=None, last_first=False,
          role_department=False, contacts=False, start_dates=False,
          dept_sections=False, title=False, export=False):
    rng = ctx.rng
    traps = set(plan["traps"])
    if title:
        traps.add("T5")
    plan = dict(plan, traps=traps)
    recs = staff_records(ctx, plan["n"])
    if len(recs) < 3:
        return None
    t = Table("staff")
    truth = [{} for _ in recs]
    people = [r["person"] for r in recs]
    if split_names is None:
        split_names = "T10" in traps
    if split_names:
        if not split_name_columns(ctx, t, people, truth):
            return None
        if last_first:
            key_order = [b for b in t.blocks[-1]]
            if key_order[0] != "last":
                t.blocks[-1] = list(reversed(key_order))
    else:
        C.text_column(ctx, t, "name", ctx.header("person_name"),
                      [r["full"] for r in recs], "name", truth,
                      digits=False)
    name_keys = [k for k in ("name", "first", "last") if t.has(k)]
    t.first_column_fixed = name_keys[:1] if rng.random() < 0.7 else []
    if dept_sections:
        depts = [r["department"] for r in recs]
        order = sorted(range(len(recs)), key=lambda i: depts[i] or "")
        recs = [recs[i] for i in order]
        truth_sorted = [truth[i] for i in order]
        for c in t.columns:
            c.cells = [c.cells[i] for i in order]
            c.fmts = [c.fmts[i] for i in order]
        truth = truth_sorted
        if B.add_sections(ctx, t, [r["department"] for r in recs], truth,
                          "department") is None:
            return None
        t.first_column_fixed = name_keys[:1]
    if role_department or export or dept_sections or rng.random() < 0.7:
        C.text_column(ctx, t, "role", ctx.header("role"),
                      [r["role"] for r in recs], "role", truth, digits=False)
    if (role_department or export) and not dept_sections and \
            any(r["department"] for r in recs):
        C.text_column(ctx, t, "department", ctx.header("department"),
                      [r["department"] for r in recs], "department", truth,
                      digits=False)
    if contacts or export or rng.random() < 0.35:
        email_column(ctx, t, "email", ctx.header("email"),
                     [r["email"] if rng.random() < 0.95 else None
                      for r in recs], "email", truth)
    if contacts or export or rng.random() < 0.35:
        phone_column(ctx, t, "phone", ctx.header("phone"),
                     [r["phone"] if rng.random() < 0.95 else None
                      for r in recs], "phone", truth)
    if start_dates or export or rng.random() < 0.3:
        date_column(ctx, t, "start", ctx.header("start_date"),
                    [r["start_date"] for r in recs], "start_date", truth)
    if dept_sections and len(t.columns) < 2:
        return None
    t.truth = truth
    text_keys = [k for k in ("name", "role", "department") if t.has(k)]
    M.decorate(ctx, t, plan, text_keys=text_keys, totals_spec=None)
    if "T4" in traps and not t.subtotals:
        count_total(ctx, t, name_keys[0])
    return t


# ---------------------------------------------------------------------
#  clients
# ---------------------------------------------------------------------
SPLIT_ADDRESS = ("FR", "BE", "CH", "IT", "ES", "MX", "AR", "CO", "CL", "US",
                 "GB", "AU", "CA", "IN", "NG", "RU", "KZ", "BY", "SA", "AE",
                 "EG", "MA", "SN")


def client_records(ctx, n, persons=False):
    rng = ctx.rng
    out, seen = [], set()
    for _ in range(n * 3):
        if len(out) >= n:
            break
        contact = ctx.person()
        if persons:
            name = contact["full"]
        else:
            name = ctx.company()
        if not name or name in seen:
            continue
        seen.add(name)
        addr = ctx.address()
        out.append({
            "name": name, "contact": contact["full"], "person": contact,
            "email": ctx.email_for(name if not persons else
                                   contact["full"], contact),
            "phone": ctx.phone(),
            "address": addr, "reg_id": None if persons else ctx.reg_id(),
            "since": REF - datetime.timedelta(days=rng.randint(10, 365 * 8)),
            "country": ctx.country_name()})
    return out


def clients(ctx, plan, *, persons=False, split_names=None,
            address="maybe", registration=False, since=False,
            crm=False, title=False):
    """address: 'one' (one cell), 'split' (street / postcode / city),
    'none' or 'maybe'."""
    rng = ctx.rng
    traps = set(plan["traps"])
    if title:
        traps.add("T5")
    plan = dict(plan, traps=traps)
    if split_names is None:
        split_names = persons and "T10" in traps
    if split_names:
        persons = True
    recs = client_records(ctx, plan["n"], persons=persons)
    if len(recs) < 3:
        return None
    t = Table("clients")
    truth = [{} for _ in recs]
    if split_names:
        if not split_name_columns(ctx, t, [r["person"] for r in recs],
                                  truth):
            return None
    else:
        C.text_column(ctx, t, "name", ctx.header(
            "client_name" if persons or rng.random() < 0.5 else "company"),
                      [r["name"] for r in recs], "name", truth,
                      digits=False)
    name_keys = [k for k in ("name", "first", "last") if t.has(k)]
    t.first_column_fixed = name_keys[:1] if rng.random() < 0.7 else []
    if not persons and (crm or rng.random() < 0.6):
        C.text_column(ctx, t, "contact", ctx.header("contact_person"),
                      [r["contact"] if rng.random() < 0.9 else None
                       for r in recs], "contact_person", truth,
                      digits=False)
    if crm or rng.random() < 0.6:
        email_column(ctx, t, "email", ctx.header("email"),
                     [r["email"] if rng.random() < 0.9 else None
                      for r in recs], "email", truth)
    if crm or rng.random() < 0.6:
        phone_column(ctx, t, "phone", ctx.header("phone"),
                     [r["phone"] if rng.random() < 0.9 else None
                      for r in recs], "phone", truth)
    if address == "maybe":
        address = rng.choice(["one", "split", "none"])
    if address == "split" and ctx.country not in SPLIT_ADDRESS:
        address = "one"
    if address == "one":
        C.text_column(ctx, t, "address", ctx.header("address"),
                      [r["address"]["one"] for r in recs], "address", truth,
                      digits=False)
    if address == "split" and any(len(r["address"]["lines"]) < 2
                                  for r in recs):
        address = "one"
    if address == "split":
        streets = [r["address"]["lines"][0] for r in recs]
        pcs = [r["address"]["postcode"] or None for r in recs]
        cities = [r["address"]["city"] or None for r in recs]
        C.text_column(ctx, t, "street", ctx.header("street"), streets,
                      "address", truth, digits=False)
        if any(pcs):
            C.text_column(ctx, t, "postcode", ctx.header("postcode"), pcs,
                          "postcode", truth, noise=False, digits=False)
        C.text_column(ctx, t, "city", ctx.header("city"), cities, "city",
                      truth, digits=False)
        t.blocks.append([k for k in ("street", "postcode", "city")
                         if t.has(k)])
        if crm or rng.random() < 0.3:
            cn = recs[0]["country"]
            if cn:
                C.text_column(ctx, t, "country", ctx.header("country"),
                              [cn] * len(recs), "country", truth,
                              digits=False)
    if not persons and (registration or crm or rng.random() < 0.2):
        ids = [r["reg_id"] for r in recs]
        if sum(1 for x in ids if x) >= max(2, len(ids) // 2):
            C.text_column(ctx, t, "reg", ctx.header("reg_id"), ids, "reg_id",
                          truth, noise=False, digits=False)
    if since or crm or rng.random() < 0.25:
        date_column(ctx, t, "since", ctx.header("client_since"),
                    [r["since"] for r in recs], "client_since", truth)
    t.truth = truth
    text_keys = [k for k in ("name", "contact", "city") if t.has(k)]
    M.decorate(ctx, t, plan, text_keys=text_keys, totals_spec=None)
    if "T4" in traps:
        count_total(ctx, t, name_keys[0])
    return t
