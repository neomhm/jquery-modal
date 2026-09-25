"""
gen/ctx.py - the context of one task: its random generator, locale,
writing styles, words, headers (respecting the hold-out rules of the
split) and the true records of the business.

Truth first (section 10.1): every method that draws a value returns the
TRUE normalized value (a float price, a 'YYYY-MM-DD' date, an E.164
phone...). Writing it into a cell is render.py's job.
"""
import datetime
import math
import re

import config
import helpers as H
from gen import data as D
from gen import ids as IDS
from gen import people as P
from gen.render import Fmt

REF = config.REFERENCE_DATE


class Ctx:
    def __init__(self, rng, split, locale_code, activity, typed, holdout,
                 forced=None):
        self.rng, self.split = rng, split
        self.code = locale_code
        self.loc = D.locale(locale_code)
        self.lang, self.country = self.loc["lang"], self.loc["country"]
        self.folder = self.loc["data"]
        self.typed = typed
        self.fmt = Fmt(rng, self.loc, typed)
        self.values = D.values(self.folder)
        self.hdr = D.headers(self.folder).get("fields") or {}
        self.hdr_all = D.headers(self.folder)
        self.hdr_test = D.headers_test(self.folder).get("fields") or {}
        self.business = D.business(self.folder)
        self.activity = activity
        self.words = activity["words"].get(self.folder) or {}
        self.holdout = holdout or {}
        self.forced = forced          # "header": use a D / T header variant
        self.used = set()             # hold-out items this task used
        self.cur_symbols = self._currency_symbols()
        self.cur_symbol = rng.choice(self.cur_symbols)
        self.people_cache = []

    # -------------------------------------------------------- headers
    def _held(self, key):
        return ((self.holdout.get("headers") or {}).get(self.folder) or
                {}).get(key) or {}

    def header(self, key, cur=True):
        """A header variant for a field key, allowed in this split. The
        first header of a task that must use a hold-out item is that
        item (dev_heldout: D; test_heldout: T)."""
        held = self._held(key)
        variants = list(self.hdr.get(key) or [])
        d_variant = held.get("D")
        t_variants = list(self.hdr_test.get(key) or [])
        pool = [v for v in variants if v != d_variant]
        if self.split == "dev_heldout" and d_variant:
            if self.forced == "header" and not self.used:
                self.used.add(("header", key, "D"))
                return self._decorate(d_variant, cur)
            pool.append(d_variant)
        if self.split == "test_heldout" and t_variants:
            if self.forced == "header" and not self.used:
                self.used.add(("header", key, "T"))
                return self._decorate(self.rng.choice(t_variants), cur)
            pool += t_variants
        if not pool:
            pool = variants or [key]
        choice = self.rng.choice(pool)
        if choice == d_variant:
            self.used.add(("header", key, "D"))
        if choice in t_variants:
            self.used.add(("header", key, "T"))
        return self._decorate(choice, cur)

    def header_plain(self, key):
        """A variant of a field key without a currency placeholder."""
        for _ in range(12):
            h = self.header(key, cur=False)
            if h is not None:
                return h
        return key

    def _decorate(self, text, cur=True):
        if "{cur}" in text:
            if not cur:
                return None
            text = text.replace("{cur}", self.cur_symbol)
        r = self.rng.random()
        if self.lang in ("fr", "en", "es", "it", "ru") and r < 0.1:
            text = text.upper()
        elif self.lang in ("fr", "en", "es", "it", "ru") and r < 0.15:
            text = text.lower()
        return text

    def trap_header(self, key):
        return self._decorate_plain(self.rng.choice(
            (self.hdr_all.get("traps") or {}).get(key) or [key]))

    def extra_header(self, kind):
        return self._decorate_plain(self.rng.choice(
            (self.hdr_all.get("extra") or {}).get(kind) or [kind]))

    def group_label(self, key):
        return self.rng.choice((self.hdr_all.get("groups") or {}).get(key)
                               or [key])

    def _decorate_plain(self, text):
        if "{cur}" in text:
            text = text.replace("{cur}", self.cur_symbol)
        return text

    def _currency_symbols(self):
        """How the currency is written in a header: '€', 'EUR', 'руб.'..."""
        out = []
        for style in self.loc["money"]:
            sym = style.replace("{n}", "").strip()
            if sym and H.currency(sym, self.code) == (True,
                                                      self.loc["currency"]):
                out.append(sym)
        return out or [self.loc["currency"]]

    # -------------------------------------------------------- words
    def word(self, name):
        words = self.values.get(name) or []
        return self.rng.choice(words) if words else None

    def title(self, target, business_name=None):
        titles = (self.values.get("title_rows") or {}).get(target) or []
        if not titles:
            return None
        t = self.rng.choice(titles)
        return t.format(year=REF.year - self.rng.choice([0, 0, 1]),
                        month=self.fmt.month_name(self.rng.randint(1, 12)),
                        business=business_name or self.business_name(),
                        date=self.fmt.date_text(REF))

    def sheet_name(self, target):
        names = (self.values.get("sheet_names") or {}).get(target) or \
            ["Sheet1"]
        name = self.rng.choice(names)
        return name.format(year=REF.year)[:31]

    def notes_row(self):
        rows = self.values.get("notes_rows") or []
        if not rows:
            return None
        return self.rng.choice(rows).format(
            date=self.fmt.date_text(REF + datetime.timedelta(
                days=self.rng.randint(30, 200))), year=REF.year)

    # -------------------------------------------------------- money
    def price(self, usd):
        """A local price from a USD range, rounded the way shops round."""
        lo, hi = usd
        main = D.locale(D.MAIN_LOCALE.get(self.folder, self.code))
        x = self.rng.uniform(lo, hi) * self.loc["usd_rate"] * \
            self.loc["price_level"] / max(0.05, main["price_level"])
        return nice_price(x, self.loc["cents"], self.rng)

    def vat(self):
        rates = self.loc.get("vat") or [0]
        return round(self.rng.choice(rates) / 100.0, 6)

    def excl(self, incl, rate):
        x = incl / (1 + rate)
        return round(x, 2) if self.loc["cents"] else float(round(x))

    # -------------------------------------------------------- items
    def items(self, kind=None):
        items = self.words.get("items") or []
        if kind:
            items = [i for i in items if i.get("kind") == kind]
        return items

    def business_name(self):
        if not hasattr(self, "_bname"):
            person = P.person(self.rng, self.loc)
            place = self.rng.choice(D.locale_list(self.code, "cities") or
                                    [{"city": ""}])
            city = place.get("city") or place.get("district") or ""
            self._bname = P.core_name(self.rng, self.loc, self.business,
                                      self.activity, city, person)
        return self._bname

    # -------------------------------------------------------- people
    def person(self):
        return P.person(self.rng, self.loc)

    def company(self):
        """A company name with or without its legal form."""
        person = P.person(self.rng, self.loc)
        place = self.rng.choice(D.locale_list(self.code, "cities") or
                                [{"city": ""}])
        city = place.get("city") or place.get("district") or ""
        acts = D.activities()
        act = self.rng.choice(acts)
        core = P.core_name(self.rng, self.loc, self.business, act, city,
                           person)
        forms = self.loc.get("legal_forms") or []
        if forms and self.rng.random() < 0.6:
            info = self.rng.choice(forms)
            return P.attach_form(self.rng, self.loc, core, info,
                                 P.pick_form_text(self.rng, self.loc, info))
        return core

    def address(self):
        return P.address(self.rng, self.loc, self.business)

    def email_for(self, name, person=None):
        return P.web_identity(self.rng, self.loc, name, person)["email"] \
            .lower()

    def phone(self, mobile=None):
        return random_phone(self.rng, self.loc["phone_region"], mobile)

    def reg_id(self):
        types = self.loc.get("reg_ids") or []
        if not types:
            return None
        t = self.rng.choice(types)["type"]
        try:
            value = IDS.make_id(self.rng, t)
        except Exception:
            return None
        if isinstance(value, dict):
            value = value.get("display") or value.get("value")
        return value if isinstance(value, str) and value else None

    def country_name(self):
        names = self.business.get("country_names") or {}
        return names.get(self.country)

    # -------------------------------------------------------- dates
    def past_date(self, days_lo, days_hi):
        return REF - datetime.timedelta(days=self.rng.randint(days_lo,
                                                              days_hi))


def nice_price(x, cents, rng):
    """Round a price the way price lists do."""
    if not cents:
        for limit, step in ((100, 1), (1000, 10), (10000, 50),
                            (100000, 100), (1e7, 1000), (1e12, 10000)):
            if x < limit:
                return float(max(step, round(x / step) * step))
    if x < 10:
        v = round(x * 20) / 20.0                   # 0.05 steps
        if rng.random() < 0.3:
            v = math.floor(x) + rng.choice([0.5, 0.9, 0.95, 0.99])
    elif x < 100:
        v = round(x * 2) / 2.0                     # 0.50 steps
        if rng.random() < 0.3:
            v = math.floor(x) + rng.choice([0.9, 0.99])
    elif x < 1000:
        v = float(round(x))
        if rng.random() < 0.4:
            v = float(round(x / 5) * 5)
    else:
        v = float(round(x / 10) * 10)
    return round(max(v, 0.05), 2)


def random_phone(rng, region, mobile=None):
    """A valid phone number of that country, as E.164 (random digits,
    checked by phonenumbers)."""
    import phonenumbers
    from phonenumbers import PhoneNumberType as T
    kinds = [T.MOBILE, T.FIXED_LINE]
    if mobile is True:
        kinds = [T.MOBILE]
    elif mobile is False:
        kinds = [T.FIXED_LINE]
    for _ in range(60):
        kind = rng.choice(kinds)
        example = phonenumbers.example_number_for_type(region, kind)
        if example is None:
            example = phonenumbers.example_number(region)
        if example is None:
            return None
        nsn = str(example.national_number)
        keep = rng.choice([1, 2, 3]) if len(nsn) > 6 else 1
        digits = nsn[:keep] + "".join(str(rng.randint(0, 9))
                                      for _ in range(len(nsn) - keep))
        try:
            num = phonenumbers.parse("+%d%s" % (example.country_code,
                                                digits))
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(num) and \
                phonenumbers.region_code_for_number(num) == region:
            return phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.E164)
    return None
