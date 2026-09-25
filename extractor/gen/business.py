"""
business.py - the business universe (section 10.3): one truth record per
folder, plus the other organisations its documents mention (clients,
suppliers, a sister organisation).

Every value is drawn with the folder's own random.Random, so a folder is
the same every time it is generated.
"""
import datetime
import math

import phonenumbers

from gen import data as D
from gen import ids as I
from gen import names as N

REF = datetime.date(2026, 6, 30)        # config.REFERENCE_DATE

# presence: probability that a fact appears in at least one document
PRESENCE = {"trading_name": 0.6, "legal_form": 0.95, "reg_id": 0.9,
            "phone": 0.9, "email": 0.85, "website": 0.7, "manager": 0.7,
            "founded": 0.8, "staff": 0.7, "revenue": 0.6, "capital": 0.5,
            "activity": 0.9, "activity_code": 0.5, "services": 1.0,
            "clients": 0.85, "hours": 0.5, "certs": 0.3}

# derived activity-code systems (section 10.3: real code when known,
# otherwise a format-correct plausible code)
DERIVED = {
    "CNAE": lambda c: c["NACE"].replace(".", ""),
    "NOGA": lambda c: c["NACE"].replace(".", "") + "00",
    "OKED": lambda c: c["NACE"].replace(".", "") + "0",
    "CLAE": lambda c: c["CIIU"] + "00",
    "SSIC": lambda c: c["NIC"],
    "SII": lambda c: c["CIIU"] + "00",
    "SA": lambda c: c["_isic"] + "01",
    "AE": lambda c: c["_isic"] + ".01",
}


def activity_code(act, system):
    codes = dict(act["codes"])
    codes["_isic"] = act["isic"]
    if system in codes:
        return codes[system]
    if system in DERIVED:
        return DERIVED[system](codes)
    return None


def loguniform(rng, lo, hi):
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


def nice_round(x):
    """Rounds a capital amount the way people choose one: 1, 2, 2.5, 5
    times a power of ten."""
    if x < 1:
        return 1
    power = 10 ** int(math.floor(math.log10(x)))
    for m in (1, 2, 2.5, 3, 5, 10):
        if x <= m * power * 1.25:
            return int(m * power)
    return int(10 * power)


def random_date(rng, start, end):
    days = (end - start).days
    return start + datetime.timedelta(days=rng.randint(0, max(0, days)))


# ---------------------------------------------------------------------
#  phone numbers that phonenumbers accepts as valid
# ---------------------------------------------------------------------
def valid_phone(rng, region, mobile=False):
    """A random number that phonenumbers accepts as a valid fixed line
    (or mobile) number of the region. Only the length comes from the
    library's example number: the digits are random, so numbers do not
    all start like the example."""
    PNT = phonenumbers.PhoneNumberType
    kind = PNT.MOBILE if mobile else PNT.FIXED_LINE
    example = phonenumbers.example_number_for_type(region, kind) or \
        phonenumbers.example_number(region)
    # national_significant_number keeps Italy's leading zero
    national = phonenumbers.national_significant_number(example)
    n = len(national)
    ok_types = (kind, PNT.FIXED_LINE_OR_MOBILE)
    for attempt in range(600):
        if attempt < 400:
            first = "0" + rng.choice("123456789") if national[0] == "0" \
                else rng.choice("123456789")
            cand = first + "".join(
                rng.choice("0123456789") for _ in range(n - len(first)))
        else:                           # keep the example's prefix
            keep = 1 if attempt < 500 else 2
            cand = national[:keep] + "".join(
                rng.choice("0123456789") for _ in range(n - keep))
        try:
            num = phonenumbers.parse("+%d%s" % (example.country_code, cand))
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(num) and \
                phonenumbers.number_type(num) in ok_types and \
                phonenumbers.region_code_for_number(num) == region:
            return phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.E164)
    return phonenumbers.format_number(example,
                                      phonenumbers.PhoneNumberFormat.E164)


# ---------------------------------------------------------------------
#  organisations
# ---------------------------------------------------------------------
class Org:
    """Any organisation: the business, a client, a supplier, a sister.
    Attributes are plain values; documents decide how to write them."""

    def __repr__(self):
        return "Org(%s, %s)" % (self.legal, self.loc["code"])

    def display_names(self):
        names = [self.legal]
        if self.trading and self.trading != self.legal:
            names.append(self.trading)
        return names


def choose_form(rng, loc, want_class=None):
    forms = loc["legal_forms"]
    if want_class is None:
        r = rng.random()
        want_class = "company" if r < 0.75 else "sole_trader" \
            if r < 0.95 else "other"
    if want_class == "other":
        pool = [f for f in forms if f["class"] in ("partnership", "other")]
    else:
        pool = [f for f in forms if f["class"] == want_class]
    if not pool:
        pool = [f for f in forms if f["class"] == "company"]
    total = sum(f["weight"] for f in pool)
    r = rng.random() * total
    for f in pool:
        r -= f["weight"]
        if r <= 0:
            return f
    return pool[-1]


def make_org(rng, loc_code, act, role="business", light=False,
             want_class=None, family_hint=None):
    """Builds one organisation. light=True for clients and suppliers
    (only what their mentions need)."""
    loc = D.locale(loc_code)
    lex = D.lexicon(loc["data"])
    o = Org()
    o.role, o.loc, o.lex, o.act = role, loc, lex, act
    o.lang, o.country = loc["lang"], loc["country"]
    o.form = choose_form(rng, loc, want_class)
    o.cls = o.form["class"]
    o.form_text = N.pick_form_text(rng, loc, o.form)
    o.manager = N.person(rng, loc)
    titles = lex.get("manager_titles") or ["Director"]
    o.manager_title = rng.choice(titles)
    o.address = N.address(rng, loc, lex)
    city = o.address["city"] or "?"
    # ---- the name
    if o.cls == "sole_trader" and not o.form["attach"] and \
            rng.random() < 0.35:
        core = o.manager["full"]            # "Jean Martin, plombier" (R8)
        o.name_is_person = True
    else:
        core = N.core_name(rng, loc, lex, act, city,
                           family_hint or o.manager)
        o.name_is_person = False
    o.core = core
    if o.form["attach"] and (o.cls != "sole_trader" or
                             o.form["code"] in ("RU_IP", "KZ_IP", "BY_IP",
                                                "NG_ENT")):
        if o.form["code"] in ("RU_IP", "KZ_IP", "BY_IP"):
            o.legal = "%s %s" % (o.form_text, o.manager["full"]
                                 if rng.random() < 0.5 else
                                 o.manager["short"])
            o.core = o.legal.split(" ", 1)[1]
        else:
            o.legal = N.attach_form(rng, loc, core, o.form, o.form_text)
    else:
        o.legal = core
    o.trading = o.legal
    if role == "business" and rng.random() < 0.4:
        other = N.core_name(rng, loc, lex, act, city, o.manager)
        if other != core:
            o.trading = other
    # ---- identifiers
    o.reg_ids = make_reg_ids(rng, loc, o, light)
    o.phones = [valid_phone(rng, loc["phone_region"])]
    if not light and rng.random() < 0.4:
        o.phones.append(valid_phone(rng, loc["phone_region"], mobile=True))
    o.fax = valid_phone(rng, loc["phone_region"]) if rng.random() < 0.3 \
        else None
    # the domain comes from the name without its legal form
    web = N.web_identity(rng, loc, o.trading if o.trading != o.legal
                         else o.core, o.manager)
    o.email = web["email"] if rng.random() < 0.85 else None
    o.website = web["website"] if rng.random() < 0.7 else None
    o.social = N.social_link(rng, loc, web["slug"]) \
        if rng.random() < 0.4 else None
    o.slug = web["slug"]
    if light:
        return o
    # ---- facts
    o.founded = founding_date(rng)
    if o.cls == "sole_trader":
        o.staff = rng.randint(0, 5)
    else:
        o.staff = max(1, int(round(loguniform(rng, 1, 500))))
    o.revenue = make_revenue(rng, loc, o.staff)
    o.capital = None
    if o.cls == "company":
        rng_range = (o.form.get("capital") or {}).get("range") or \
            loc["capital"]
        o.capital = nice_round(loguniform(rng, max(1, rng_range[0]),
                                          rng_range[1]))
    ac = loc.get("activity_code")
    o.act_system = ac["system"] if ac else None
    o.act_code = activity_code(act, o.act_system) if ac else None
    o.services = make_services(rng, loc, act)
    o.hours = make_hours(rng, act) if (
        (act["customers"] != "B2B" and act["hours"] and rng.random() < 0.8)
        or (act["customers"] == "B2B" and rng.random() < 0.2)) else None
    o.certs = make_certs(rng, loc, lex, act)
    return o


def founding_date(rng):
    year = max(1950, 2025 - int(rng.expovariate(1 / 12.0)))
    start = datetime.date(year, 1, 1)
    end = min(datetime.date(year, 12, 31), REF - datetime.timedelta(days=200))
    return random_date(rng, start, end)


def make_reg_ids(rng, loc, o, light):
    kind = o.cls if o.cls != "other" else "company"
    info = {"kind": kind, "family": o.manager["family"],
            "given": o.manager["given"], "female": o.manager["gender"] == "f",
            "name": o.core, "initial": (N.romanize(o.core)[:1] or "A").upper()}
    types = [r for r in loc["reg_ids"]
             if not r.get("only") or r["only"] == kind or
             (r["only"] == "company" and kind in ("company", "partnership"))]
    chosen = [types[0]] if types else []
    for r in types[1:]:
        if len(chosen) < 3 and rng.random() < r["weight"] * (0.4 if light
                                                            else 0.8):
            chosen.append(r)
    out = []
    shared = {}
    for r in chosen:
        t = r["type"]
        if t in ("FR_SIREN", "FR_SIRET", "FR_TVA"):
            shared.setdefault("siren", I.make_id(rng, "FR_SIREN"))
            info["siren"] = shared["siren"]
        if t == "RU_INN":
            t = "RU_INN12" if kind == "sole_trader" else "RU_INN10"
        if t == "IN_GSTIN" and "pan" in shared:
            info["pan"] = shared["pan"]
        compact = I.make_id(rng, t, info)
        if t == "IN_PAN":
            shared["pan"] = compact
        if t == "IT_PIVA":
            info["piva"] = compact
        if t == "CA_BN":
            info["bn"] = compact
        if t == "JP_CORP":
            info["corp"] = compact
        out.append({"type": t, "compact": compact, "labels": r["labels"]})
    return out


def make_revenue(rng, loc, staff):
    """2-3 consecutive years, consistent with the staff count (roughly
    50k-250k USD-equivalent per employee), growth -20 % .. +30 %."""
    years = rng.choice([2, 3, 3])
    last = rng.choice([2025, 2025, 2024])
    per_head = rng.uniform(50000, 250000)
    base_usd = per_head * max(staff, 0.5)
    value = base_usd * loc["usd_rate"]
    out = {}
    for y in range(last, last - years, -1):
        out[y] = round_sig3(value)
        value = value / (1 + rng.uniform(-0.2, 0.3))
    return dict(sorted(out.items()))


def round_sig3(x):
    if x <= 0:
        return 0
    d = 3 - int(math.floor(math.log10(x))) - 1
    return float(round(x, d)) if d > 0 else float(int(round(x, d)))


def local_price(loc, usd, main_loc):
    return usd * loc["usd_rate"] * loc["price_level"] / \
        max(0.05, main_loc["price_level"])


def nice_price(value, cents):
    """Prices end the way shop prices do: .90, .50, whole numbers."""
    if value >= 1000:
        return float(int(round(value, -1)))
    if value >= 100:
        return float(int(round(value)))
    if not cents:
        return float(max(1, int(round(value))))
    return round(round(value * 2) / 2 - (0.1 if value > 5 else 0), 2) \
        if value > 1 else round(value, 2)


def make_services(rng, loc, act):
    key = loc["data"]
    pool = (act.get("services") or {}).get(key) or []
    if not pool:
        return []
    main = D.locale(D.language_settings()["main_locale"].get(key, loc["code"]))
    n = min(len(pool), rng.randint(5, 15))
    chosen = rng.sample(pool, n)
    out = []
    for s in chosen:
        lo, hi = s["usd"]
        usd = loguniform(rng, max(lo, 0.01), max(hi, lo * 1.001))
        price = nice_price(local_price(loc, usd, main), loc["cents"])
        out.append({"name": s["name"], "price": max(price, 0.01),
                    "unit": s["unit"]})
    return out


def make_hours(rng, act):
    """A weekly schedule: list of (first_day, last_day, [slots])."""
    group = act.get("group")
    if group == "food":
        open_h = rng.choice([6, 7, 7, 8, 11, 12])
        close_h = rng.choice([14, 19, 20, 22, 23])
        if open_h >= 11:
            slots = [((open_h, 0), (14, 30)), ((19, 0), (close_h, 0))] \
                if close_h >= 22 else [((open_h, 0), (close_h, 0))]
        else:
            slots = [((open_h, 0), (close_h, rng.choice([0, 30])))]
    else:
        open_h = rng.choice([8, 9, 9, 10])
        close_h = rng.choice([17, 18, 18, 19, 20])
        if rng.random() < 0.4:
            slots = [((open_h, 0), (12, rng.choice([0, 30]))),
                     ((14, 0), (close_h, 0))]
        else:
            slots = [((open_h, rng.choice([0, 0, 30])), (close_h, 0))]
    schedule = [(0, 4, slots)]
    r = rng.random()
    if r < 0.6:
        schedule.append((5, 5, [((slots[0][0][0], 0),
                                 (rng.choice([12, 13, 17, 18]), 0))]))
    elif r < 0.75:
        schedule = [(0, 5, slots)]
    elif r < 0.85:
        schedule = [(0, 6, slots)]
    return schedule


def make_certs(rng, loc, lex, act):
    pool = [c for c in lex.get("certs") or []
            if ("*" in c["countries"] or loc["country"] in c["countries"])
            and ("*" in c["groups"] or act.get("group") in c["groups"])]
    if not pool or rng.random() < 0.55:
        return []
    return [c["name"] for c in rng.sample(pool, min(len(pool),
                                                    rng.randint(1, 3)))]


# ---------------------------------------------------------------------
#  the folder's business, with everything around it
# ---------------------------------------------------------------------
def make_business(rng, loc_code, act, client_locales, other_acts):
    """The subject of a folder and its world. client_locales: training
    locales a client may come from (never a held-out one). other_acts:
    activities for clients / suppliers / sister organisations."""
    biz = make_org(rng, loc_code, act, "business")
    loc = biz.loc
    biz.presence = {k: rng.random() < p for k, p in PRESENCE.items()}
    if biz.capital is None:
        biz.presence["capital"] = False
    if not biz.hours:
        biz.presence["hours"] = False
    if not biz.certs:
        biz.presence["certs"] = False
    if biz.staff == 0:
        biz.presence["staff"] = False
    if not biz.email:
        biz.presence["email"] = False
    if not biz.website and not biz.social:
        biz.presence["website"] = False
    if not biz.act_code:
        biz.presence["activity_code"] = False
    # ---- clients: organisations (B2B) and private persons (B2C)
    cust = act["customers"]
    n_orgs = rng.randint(5, 40) if cust == "B2B" else \
        rng.randint(0, 5) if cust == "B2C" else rng.randint(3, 15)
    biz.clients = []
    for _ in range(n_orgs):
        cl_loc = loc_code
        if rng.random() < 0.1 and client_locales:
            cl_loc = rng.choice(client_locales)
        biz.clients.append(make_org(rng, cl_loc, rng.choice(other_acts),
                                    "client", light=True))
    biz.private_share = 0.0 if cust == "B2B" else \
        0.85 if cust == "B2C" else 0.5
    biz.suppliers = [make_org(rng, loc_code, rng.choice(other_acts),
                              "supplier", light=True)
                     for _ in range(rng.randint(2, 5))]
    for s in biz.suppliers:        # suppliers need facts for their invoices
        s.services = make_services(rng, s.loc, s.act) or [
            {"name": "?", "price": 10.0, "unit": "piece"}]
    # ---- deliberate difficulties (section 10.3)
    biz.outdated = None
    if rng.random() < 0.05:
        field = "address" if rng.random() < 0.6 else "staff"
        if field == "address":
            biz.old_address = N.address(rng, loc, biz.lex)
            biz.move_date = random_date(rng, datetime.date(2023, 6, 1),
                                        datetime.date(2025, 6, 1))
            biz.outdated = {"field": "address",
                            "old": biz.old_address["one"],
                            "current": biz.address["one"],
                            "changed": biz.move_date.isoformat()}
        elif biz.staff >= 3:
            biz.old_staff = max(1, int(biz.staff * rng.uniform(0.5, 0.8)))
            biz.outdated = {"field": "staff", "old": biz.old_staff,
                            "current": biz.staff}
    biz.sister = None
    if rng.random() < 0.05:
        sister = make_org(rng, loc_code, rng.choice(other_acts), "sister",
                          family_hint=biz.manager)
        sister.services = make_services(rng, sister.loc, sister.act)
        biz.sister = sister
    return biz


def private_person(rng, loc_code):
    """A private customer: name and address are O (rule R9)."""
    loc = D.locale(loc_code)
    lex = D.lexicon(loc["data"])
    p = N.person(rng, loc)
    p["address"] = N.address(rng, loc, lex)
    p["private"] = True
    return p
