"""
formats.py - how each locale WRITES numbers, amounts, dates, years,
staff counts, phone numbers and opening hours, together with the
normalized truth of every value (section 14.2 forms).

Every function returns (text, truth). The text is exactly what goes into
the document; the truth is what normalize() must give back for it.

Digits are always written here in ASCII. A document that uses
Arabic-Indic, Devanagari or full-width digits is converted afterwards,
character by character (noise.convert_digits), so spans never move. In
Arabic-Indic documents the separators are already the Arabic ones
(U+066C thousands, U+066B decimal).
"""
import datetime
import math

import phonenumbers

from gen import data as D

try:                                    # optional: Hijri dates (ar-SA)
    from hijridate import Gregorian
except Exception:                       # pragma: no cover
    Gregorian = None

# ---------------------------------------------------------------------
#  plural categories (CLDR, simplified to what the lexicons use)
# ---------------------------------------------------------------------


def plural(lang, n):
    n = int(n)
    if lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    if lang == "ar":
        if n == 0:
            return "zero"
        if n == 1:
            return "one"
        if n == 2:
            return "two"
        if 3 <= n % 100 <= 10:
            return "few"
        if 11 <= n % 100 <= 99:
            return "many"
        return "other"
    if lang in ("zh", "ja", "ko"):
        return "other"
    if lang in ("fr", "hi"):
        return "one" if n in (0, 1) else "other"
    return "one" if n == 1 else "other"


def plural_form(forms, lang, n):
    """forms = {"one": ..., "other": ...}; falls back gracefully."""
    cat = plural(lang, n)
    for key in (cat, "other", "many", "one"):
        if key in forms:
            return forms[key]
    return next(iter(forms.values()))


# ---------------------------------------------------------------------
#  plain numbers
# ---------------------------------------------------------------------
def group_int(digits, sep, indian=False):
    """'1240000' -> '1,240,000' (or Indian '12,40,000')."""
    if not sep:
        return digits
    if indian and len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        return sep.join(parts + [tail])
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return sep.join(parts)


def number(value, decimals, dec_sep, grp_sep, indian=False):
    text = "%.*f" % (decimals, abs(value))
    negative = value < 0 and float(text) != 0
    ip, _, fp = text.partition(".")
    out = group_int(ip, grp_sep, indian)
    if decimals:
        out += dec_sep + fp
    return "-" + out if negative else out


def short_num(x, dec_sep=".", max_dec=2):
    """1.24 -> '1.24', 1.2 -> '1.2', 12.0 -> '12' (with dec_sep)."""
    text = ("%.*f" % (max_dec, x)).rstrip("0").rstrip(".")
    return text.replace(".", dec_sep)


def round_sig(x, sig=3):
    if x <= 0:
        return 0
    d = sig - int(math.floor(math.log10(abs(x)))) - 1
    return round(x, d) if d > 0 else float(int(round(x, d)))


# ---------------------------------------------------------------------
#  the formatter of one document
# ---------------------------------------------------------------------
MONTH_LONG = {"en_us": "{M} {D}, {Y}", "en": "{D} {M} {Y}",
              "fr": "{D} {M} {Y}", "es": "{D} de {M} de {Y}",
              "it": "{D} {M} {Y}", "ru": "{D} {M} {Y} г.",
              "hi": "{D} {M} {Y}", "ar": "{D} {M} {Y}"}
ERAS = [(2019, 5, 1, "令和"), (1989, 1, 8, "平成"), (1926, 12, 25, "昭和"),
        (1912, 7, 30, "大正"), (1868, 1, 25, "明治")]


class Fmt:
    """Formats values for ONE document. The document's choices (which
    thousands separator, where the currency goes, which date style) are
    drawn once here, so a document is consistent with itself - like a
    real one."""

    def __init__(self, rng, loc, lex, digits=None):
        self.rng = rng
        self.loc = loc
        self.lex = lex
        self.lang = loc["lang"]
        self.country = loc["country"]
        self.digits = digits
        self.indian = loc.get("grouping") == "indian"
        self.dec = loc["decimal"]
        self.grp = rng.choice(loc["group"]) if loc["group"] else ""
        if digits == "arab":
            self.dec, self.grp = "٫", "٬"
        # currency position and form, fixed for the document
        before, after = loc["currency_before"], loc["currency_after"]
        if before and (not after or rng.random() < self._before_share()):
            self.cur_pos, self.cur_form = "before", rng.choice(before)
        else:
            self.cur_pos, self.cur_form = "after", rng.choice(after)
        self.cents = loc["cents"]
        self.dash_cents = rng.random() < loc.get("dash_cents", 0)
        # date style of the document
        dates = loc["dates"]
        self.date_style = "numeric"
        r = rng.random()
        for style in ("hijri", "era", "minguo"):
            share = dates.get(style, 0)
            if r < share:
                self.date_style = style
                break
            r -= share
        else:
            if rng.random() < dates.get("cjk", 0):
                self.date_style = "cjk"
            elif rng.random() < dates.get("long", 0):
                self.date_style = "long"
        if self.date_style == "hijri" and Gregorian is None:
            self.date_style = "numeric"
        self.numeric_date = rng.choice(dates["numeric"])

    def _before_share(self):
        return {"en": 0.9, "zh": 0.6, "ja": 0.5, "ko": 0.4, "es": 0.6,
                "it": 0.5, "hi": 0.8}.get(self.lang, 0.2)

    # -------------------------------------------------------------
    def num(self, value, decimals=0):
        return number(value, decimals, self.dec, self.grp, self.indian)

    def int_text(self, n):
        return str(int(n))

    # -------------------------------------------------------------
    #  amounts
    # -------------------------------------------------------------
    def money(self, value, style="doc", decimals=None):
        """A full amount with currency. style: 'doc' (the document's
        form), 'code' (ISO code), 'word' (currency word), 'bare' (no
        currency). Returns (text, truth)."""
        cur = self.loc["currency"]
        if decimals is None:
            decimals = 2 if self.cents else 0
        value = round(value, decimals)
        body = self.num(value, decimals)
        if decimals and self.dash_cents and abs(value - round(value)) < 1e-9:
            body = self.num(value, 0) + ".–"
        truth = {"kind": "amount", "value": float(value), "currency": cur}
        if style == "bare":
            truth["currency"] = None
            return body, truth
        if style == "code":
            text = (cur + " " + body) if self.rng.random() < 0.5 \
                else (body + " " + cur)
            return text, truth
        if style == "word":
            words = (self.lex.get("currency_names") or {}).get(cur)
            if words:
                if self.lang == "ru" and len(words) >= 3:
                    cat = plural("ru", int(value)) if abs(
                        value - round(value)) < 1e-9 else "few"
                    word = {"one": words[0], "few": words[1],
                            "many": words[2]}[cat]
                elif self.lang == "ar" or len(words) == 1:
                    word = words[0]
                else:
                    word = words[1] if value >= 2 else words[0]
                return self._join_after(body, word), truth
        form = self.cur_form
        if self.cur_pos == "before":
            glue = "" if form in ("$", "£", "€", "¥", "￥", "₹", "₩", "₦",
                                  "NT$", "HK$", "S$", "US$", "A$", "C$",
                                  "CA$", "₸", "₽") \
                and self.rng.random() < 0.75 else " "
            return form + glue + body, truth
        return self._join_after(body, form), truth

    def _join_after(self, body, form):
        if self.lang in ("zh", "ja") or form in ("원", "원정", "円", "元"):
            return body + form
        return body + " " + form

    def raw_number(self, value, decimals=2):
        """What openpyxl gives back for a number cell: str(float) or
        str(int). No currency, no grouping (section 10.5)."""
        if decimals == 0 or abs(value - round(value)) < 1e-9 and \
                self.rng.random() < 0.5:
            text = str(int(round(value)))
        else:
            text = repr(round(float(value), decimals))
        return text, {"kind": "amount", "value": float(round(value, 2)),
                      "currency": None}

    def money_prose(self, value):
        """An amount as written in running text, often with a magnitude
        word ("1,24 M€", "12億4,000万円"). The value is first rounded to 3
        significant digits and the text says exactly that value."""
        value = round_sig(value, 3)
        options = self._magnitude_options(value)
        if not options or self.rng.random() < 0.25:
            decimals = 0 if value >= 1000 or not self.cents else 2
            return self.money(value, decimals=decimals)
        text, v, cur = self.rng.choice(options)
        return text, {"kind": "amount", "value": float(v), "currency": cur}

    def _magnitude_options(self, v):
        lang, cur, country = self.lang, self.loc["currency"], self.country
        dec = "," if self.dec in (",", "٫") and lang not in (
            "zh", "ja", "ko") else "."
        if self.digits == "arab":
            dec = "٫"
        sym_before = [f for f in self.loc["currency_before"]
                      if not f.isalpha() or f in ("US$",)]
        words = (self.lex.get("currency_names") or {}).get(cur) or []
        word_pl = words[-1] if words else cur
        opts = []

        def add(text, value=v, currency=cur):
            opts.append((text, value, currency))

        m, b, k = v / 1e6, v / 1e9, v / 1e3
        if lang == "en":
            sym = sym_before[0] if sym_before else cur + " "
            if self.indian:
                if v >= 1e7:
                    add("%s%s crore" % (sym, short_num(v / 1e7)))
                    add("INR %s crore" % short_num(v / 1e7))
                if 1e5 <= v < 1e8:
                    add("%s%s lakh" % (sym, short_num(v / 1e5)))
            else:
                if v >= 1e6:
                    add("%s%s million" % (sym, short_num(m)))
                    add("%s%sM" % (sym, short_num(m)))
                    add("%s %s million" % (cur, short_num(m)))
                    add("%s million %s" % (short_num(m), word_pl))
                if v >= 1e9:
                    add("%s%s billion" % (sym, short_num(b)))
                if 1e4 <= v < 1e6:
                    add("%s%sK" % (sym, short_num(k)))
        elif lang == "fr":
            unit = {"EUR": ("€", "d'euros"), "CHF": ("CHF", "de francs"),
                    "CAD": ("$", "de dollars"), "MAD": ("DH", "de dirhams"),
                    "XOF": ("FCFA", "de francs CFA")}.get(cur, (cur, cur))
            if v >= 1e6:
                w = "million" if m < 2 else "millions"
                add("%s %s %s" % (short_num(m, dec), w, unit[1]))
                if cur == "EUR":
                    add("%s M€" % short_num(m, dec))
                elif cur == "CHF":
                    add("CHF %s million" % short_num(m, dec))
                elif cur == "MAD":
                    add("%s MDH" % short_num(m, dec))
            if v >= 1e9:
                w = "milliard" if b < 2 else "milliards"
                add("%s %s %s" % (short_num(b, dec), w, unit[1]))
            if 1e4 <= v < 1e6 and cur == "EUR":
                add("%s k€" % short_num(k, dec))
        elif lang == "es":
            unit = {"EUR": "de euros", "MXN": "de pesos", "ARS": "de pesos",
                    "COP": "de pesos", "CLP": "de pesos"}.get(cur, cur)
            if v >= 1e6:
                w = "millón" if m < 2 else "millones"
                add("%s %s %s" % (short_num(m, dec), w, unit))
                if cur == "EUR":
                    add("%s M€" % short_num(m, dec))
                if country == "CO" and v >= 1e8:
                    add("$ %s MM" % self.num(m, 0))
            if 1e4 <= v < 1e6:
                add("%s mil %s" % (self.num(k, 0) if k >= 1000 else
                                   short_num(k, dec),
                                   "€" if cur == "EUR" else "pesos"))
        elif lang == "it":
            unit = "di euro" if cur == "EUR" else "di franchi"
            if v >= 1e6:
                w = "milione" if m < 2 else "milioni"
                add("%s %s %s" % (short_num(m, dec), w, unit))
                if cur == "EUR":
                    add("€ %s mln" % short_num(m, dec))
            if v >= 1e9:
                w = "miliardo" if b < 2 else "miliardi"
                add("%s %s %s" % (short_num(b, dec), w, unit))
            if 1e4 <= v < 1e6:
                add("%s mila euro" % self.num(k, 0))
        elif lang == "ru":
            unit = {"RUB": "руб.", "KZT": "тенге", "BYN": "руб."}.get(cur, cur)
            if v >= 1e6:
                add("%s млн %s" % (short_num(m, dec), unit))
                if cur == "RUB":
                    add("%s млн ₽" % short_num(m, dec))
            if v >= 1e9:
                add("%s млрд %s" % (short_num(b, dec), unit))
            if 1e4 <= v < 1e6:
                add("%s тыс. %s" % (short_num(k, dec), unit))
        elif lang == "ar":
            unit = {"SAR": "ريال", "AED": "درهم", "EGP": "جنيه",
                    "MAD": "درهم"}.get(cur, cur)
            ar_dec = "٫" if self.digits == "arab" else "."
            if v >= 1e6:
                add("%s مليون %s" % (short_num(m, ar_dec), unit))
            if v >= 1e9:
                add("%s مليار %s" % (short_num(b, ar_dec), unit))
            if 1e4 <= v < 1e6:
                add("%s ألف %s" % (self.num(k, 0) if k >= 100 else
                                   short_num(k, ar_dec), unit))
        elif lang == "hi":
            if v >= 1e7:
                add("₹%s करोड़" % short_num(v / 1e7))
                add("%s करोड़ रुपये" % short_num(v / 1e7))
            if 1e5 <= v < 1e8:
                add("₹%s लाख" % short_num(v / 1e5))
                add("%s लाख रुपये" % short_num(v / 1e5))
        elif lang in ("zh", "ja", "ko"):
            opts.extend(self._cjk_magnitude(v))
        return opts

    def _cjk_magnitude(self, v):
        lang, cur = self.lang, self.loc["currency"]
        trad = self.loc["data"] == "zh-Hant"
        wan = "萬" if trad else ("万" if lang in ("zh", "ja") else "만")
        yi = {"zh": "億" if trad else "亿", "ja": "億", "ko": "억"}[lang]
        out = []
        v = int(round(v))
        if lang == "ja":
            suffix, pre = "円", ""
        elif lang == "ko":
            suffix, pre = " 원" if self.rng.random() < 0.6 else "원", ""
        else:
            suffix = "元"
            pre = {"CNY": self.rng.choice(["", "人民币"]),
                   "TWD": self.rng.choice(["", "新臺幣", "新台幣"]),
                   "HKD": self.rng.choice(["", "港幣"]),
                   "SGD": ""}.get(cur, "")
            if cur == "HKD":
                suffix = self.rng.choice(["元", "港元"])
            if cur == "SGD":
                suffix = "新元"
        if v >= 1e8:
            oku, rest = divmod(v, 10 ** 8)
            man = rest // 10 ** 4
            if rest % 10 ** 4 == 0:
                if lang == "ko" and man and man % 1000 == 0 and \
                        self.rng.random() < 0.5:
                    text = "%d%s %d천만%s" % (oku, yi, man // 1000, suffix)
                elif man:
                    sep = " " if lang == "ko" else ""
                    text = "%s%s%s%s%s" % (group_int(str(oku), ","), yi, sep,
                                           group_int(str(man), ","), wan)
                    text += suffix
                else:
                    text = "%s%s%s" % (group_int(str(oku), ","), yi, suffix)
                out.append((pre + text, float(v), cur))
            if lang == "zh" and v % 10 ** 6 == 0:
                out.append((pre + "%s%s%s" % (short_num(v / 1e8), yi, suffix),
                            float(v), cur))
        if 1e4 <= v and v % 10 ** 4 == 0 and v < 1e12:
            man = v // 10 ** 4
            out.append((pre + "%s%s%s" % (group_int(str(man), ","), wan,
                                          suffix), float(v), cur))
        return out

    # -------------------------------------------------------------
    #  dates
    # -------------------------------------------------------------
    def month_name(self, m, form="full"):
        months = self.lex["months"]
        if self.lang == "ru" and form == "genitive":
            return months.get("genitive", months["full"])[m - 1]
        return months.get(form, months["full"])[m - 1]

    def date(self, d, style=None, truth_kind="date"):
        """A full date. style: None = the document's style, or one of
        numeric / long / cjk / era / minguo / hijri / iso / sheet /
        short (2-digit year). Returns (text, truth)."""
        style = style or self.date_style
        truth = {"kind": "date", "year": d.year, "month": d.month,
                 "day": d.day}
        lang = self.lang
        if style == "sheet":
            return "%04d-%02d-%02d 00:00:00" % (d.year, d.month, d.day), truth
        if style == "iso":
            return "%04d-%02d-%02d" % (d.year, d.month, d.day), truth
        if style == "era" and lang == "ja":
            return self._era(d, day=True), truth
        if style == "minguo" and self.country == "TW":
            y = d.year - 1911
            form = self.rng.choice(["民國%d年%d月%d日", "%d年%d月%d日",
                                    "%d/%02d/%02d", "民國%d/%02d/%02d"])
            return form % (y, d.month, d.day), truth
        if style == "hijri" and Gregorian is not None:
            h = Gregorian(d.year, d.month, d.day).to_hijri()
            if self.rng.random() < 0.6:
                text = "%04d/%02d/%02dهـ" % (h.year, h.month, h.day)
            else:
                months = self.lex["months"].get("hijri")
                text = "%d %s %dهـ" % (h.day, months[h.month - 1], h.year) \
                    if months else "%04d/%02d/%02dهـ" % (h.year, h.month,
                                                      h.day)
            return text, truth
        if style == "cjk" or (style == "long" and lang in ("zh", "ja")):
            if lang == "ko":
                return "%d년 %d월 %d일" % (d.year, d.month, d.day), truth
            return "%d年%d月%d日" % (d.year, d.month, d.day), truth
        if style == "long" and lang == "ko":
            return "%d년 %d월 %d일" % (d.year, d.month, d.day), truth
        if style == "long":
            return self._long_date(d), truth
        if style == "short":
            pattern = self.numeric_date.replace("YYYY", "YY")
            if "YY" not in pattern or pattern.startswith("YY"):
                pattern = self.numeric_date
            return self._numeric(d, pattern), truth
        return self._numeric(d, self.numeric_date), truth

    def _numeric(self, d, pattern):
        out = pattern
        out = out.replace("YYYY", "%04d" % d.year)
        out = out.replace("YY", "%02d" % (d.year % 100))
        out = out.replace("MM", "%02d" % d.month).replace("DD", "%02d" % d.day)
        out = out.replace("M", str(d.month)).replace("D", str(d.day))
        return out

    def _long_date(self, d):
        lang = self.lang
        if lang == "en":
            pattern = MONTH_LONG["en_us"] if self.country in ("US", "CA") \
                else MONTH_LONG["en"]
            month = self.month_name(d.month)
            day = str(d.day)
            if self.country not in ("US", "CA") and self.rng.random() < 0.2:
                day += {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd",
                        23: "rd", 31: "st"}.get(d.day, "th")
            return pattern.replace("{M}", month).replace(
                "{D}", day).replace("{Y}", str(d.year))
        if lang == "ru":
            month = self.month_name(d.month, "genitive")
        else:
            month = self.month_name(d.month)
        pattern = MONTH_LONG.get(lang, "{D} {M} {Y}")
        day = str(d.day)
        if lang == "fr" and d.day == 1 and self.rng.random() < 0.5:
            day = "1er"
        return pattern.replace("{D}", day).replace("{M}", month).replace(
            "{Y}", str(d.year))

    def _era(self, d, day=True, month=True):
        for y, m, dd, name in ERAS:
            if (d.year, d.month, d.day) >= (y, m, dd):
                n = d.year - y + 1
                num = "元" if n == 1 and self.rng.random() < 0.7 else str(n)
                text = "%s%s年" % (name, num)
                if month:
                    text += "%d月" % d.month
                if day:
                    text += "%d日" % d.day
                return text
        return "%d年%d月%d日" % (d.year, d.month, d.day)

    def founded(self, d, kind="year"):
        """FOUNDED as a year, a month + year, or a full date."""
        lang = self.lang
        if kind == "date":
            if self.date_style in ("hijri",):
                return self.date(d, "numeric")
            return self.date(d, None if self.date_style != "numeric"
                             else self.rng.choice(["numeric", "long"]))
        truth = {"kind": "date", "year": d.year, "month": None, "day": None}
        if kind == "month":
            truth["month"] = d.month
            if lang == "ja" and self.rng.random() < 0.3:
                return self._era(d, day=False), truth
            if lang in ("zh", "ja"):
                return "%d年%d月" % (d.year, d.month), truth
            if lang == "ko":
                return "%d년 %d월" % (d.year, d.month), truth
            if lang == "en" and self.rng.random() < 0.4:
                short = self.lex["months"]["short"][d.month - 1]
                return "%s %d" % (short, d.year), truth
            month = self.month_name(d.month)
            if lang == "es":
                return "%s de %d" % (month, d.year), truth
            return "%s %d" % (month, d.year), truth
        if lang == "ja":
            if self.rng.random() < 0.25:
                return self._era(d, day=False, month=False), truth
            return "%d年" % d.year, truth
        if lang == "zh":
            return "%d年" % d.year, truth
        if lang == "ko":
            return "%d년" % d.year, truth
        return str(d.year), truth

    def rev_year(self, y, fiscal=None):
        """REVENUE_YEAR: '2023', 'FY 2022-23', '2023年度', '令和5年度' ..."""
        truth = {"kind": "year", "year": y, "fiscal": None}
        lang, r = self.lang, self.rng.random()
        if fiscal == "india" or (self.loc.get("fiscal") == "india" and
                                 r < 0.6):
            truth["fiscal"] = "%d-%02d" % (y - 1, y % 100)
            form = self.rng.choice(["FY %d-%02d", "FY%d-%02d", "%d-%02d"])
            return form % (y - 1, y % 100), truth
        if lang == "ja":
            if r < 0.3:
                n = y - 2018
                return ("令和%d年度" % n if n > 1 else "令和元年度"), truth
            return self.rng.choice(["%d年度", "%d年"]) % y, truth
        if lang == "zh":
            return self.rng.choice(["%d年", "%d年度", "%d"]) % y, truth
        if lang == "ko":
            return self.rng.choice(["%d년", "%d"]) % y, truth
        if lang == "ru" and r < 0.3:
            return "%d г." % y, truth
        if lang == "en" and r < 0.15:
            return self.rng.choice(["FY%d", "FY %d"]) % y, truth
        if r < 0.05:
            return "%d/%d" % (y - 1, y), truth
        return str(y), truth

    # -------------------------------------------------------------
    #  staff counts
    # -------------------------------------------------------------
    STAFF_FORMS = {
        "en": {"exact": ["{n}"], "approx": ["about {n}", "around {n}",
                                            "approximately {n}"],
               "over": ["over {n}", "more than {n}", "{n}+"],
               "under": ["fewer than {n}", "less than {n}", "under {n}"],
               "range": ["{a}-{b}", "{a}–{b}"]},
        "fr": {"exact": ["{n}"], "approx": ["environ {n}", "près de {n}"],
               "over": ["plus de {n}"], "under": ["moins de {n}"],
               "range": ["{a} à {b}", "{a}-{b}"]},
        "es": {"exact": ["{n}"], "approx": ["unos {n}", "cerca de {n}"],
               "over": ["más de {n}"], "under": ["menos de {n}"],
               "range": ["{a}-{b}", "entre {a} y {b}"]},
        "it": {"exact": ["{n}"], "approx": ["circa {n}", "quasi {n}"],
               "over": ["oltre {n}", "più di {n}"],
               "under": ["meno di {n}"], "range": ["{a}-{b}", "da {a} a {b}"]},
        "ru": {"exact": ["{n}"], "approx": ["около {n}", "примерно {n}"],
               "over": ["более {n}", "свыше {n}"], "under": ["менее {n}"],
               "range": ["от {a} до {b}", "{a}-{b}"]},
        "ar": {"exact": ["{n}"], "approx": ["حوالي {n}"],
               "over": ["أكثر من {n}"], "under": ["أقل من {n}"],
               "range": ["{a}-{b}", "من {a} إلى {b}"]},
        "hi": {"exact": ["{n}"], "approx": ["लगभग {n}"],
               "over": ["{n} से अधिक"], "under": ["{n} से कम"],
               "range": ["{a}-{b}"]},
        "zh": {"exact": ["{n}人", "{n}名"], "approx": ["约{n}人", "约{n}名"],
               "over": ["{n}余人", "{n}人以上", "{n}多人"],
               "under": ["不足{n}人"], "range": ["{a}-{b}人", "{a}至{b}人"]},
        "ja": {"exact": ["{n}名", "{n}人"], "approx": ["約{n}名", "約{n}人"],
               "over": ["{n}名以上", "{n}人以上"], "under": ["{n}名未満"],
               "range": ["{a}〜{b}名", "{a}～{b}名"]},
        "ko": {"exact": ["{n}명"], "approx": ["약 {n}명"],
               "over": ["{n}여 명", "{n}명 이상"], "under": ["{n}명 미만"],
               "range": ["{a}~{b}명"]},
    }

    def staff(self, n, qualifier=None):
        """STAFF with its qualifier: exact / approx / over / under /
        range. Round numbers go with approx/over/under, like in life."""
        forms = self.STAFF_FORMS[self.lang]
        if qualifier is None:
            qualifier = "exact"
            r = self.rng.random()
            if n >= 20 and r < 0.35:
                qualifier = self.rng.choice(["approx", "over", "over",
                                             "range"])
        truth = {"kind": "count", "value": n, "qualifier": qualifier,
                 "max": None}
        if qualifier == "range":
            step = 10 if n >= 20 else 5
            a = max(1, (n // step) * step)
            b = a + step
            truth.update(value=a, max=b)
            text = self.rng.choice(forms["range"]).format(
                a=self.num(a), b=self.num(b))
            return text, truth
        if qualifier in ("approx", "over", "under"):
            step = 10 if n >= 20 else 5
            n2 = max(step, int(round(n / step)) * step)
            if qualifier == "over":
                n2 = max(step, (n // step) * step)
            if qualifier == "under":
                n2 = (n // step + 1) * step
            truth["value"] = n2
            return self.rng.choice(forms[qualifier]).format(
                n=self.num(n2)), truth
        return self.rng.choice(forms["exact"]).format(n=self.num(n)), truth

    # -------------------------------------------------------------
    #  percentages, quantities
    # -------------------------------------------------------------
    def percent(self, p):
        body = short_num(p, self.dec if self.dec != "٫" else "٫")
        if self.lang == "fr":
            return body + " %" if self.rng.random() < 0.5 \
                else body + " %"
        if self.lang in ("ru", "es", "it") and self.rng.random() < 0.3:
            return body + " %"
        return body + "%"

    # -------------------------------------------------------------
    #  phone numbers
    # -------------------------------------------------------------
    def phone(self, e164, style=None):
        """A phone number (phonenumbers object or E.164 string) as the
        locale writes it. Returns (text, truth)."""
        num = phonenumbers.parse(e164, None) if isinstance(e164, str) \
            else e164
        e = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        truth = {"kind": "phone", "e164": e}
        style = style or self.rng.choice(["national", "national",
                                          "international", "international",
                                          "local"])
        if style == "e164":
            return e, truth
        if style == "international":
            return phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.INTERNATIONAL), truth
        text = phonenumbers.format_number(
            num, phonenumbers.PhoneNumberFormat.NATIONAL)
        if style == "local":
            c = self.country
            digits = "".join(ch for ch in text if ch.isdigit())
            if c in ("FR", "MA", "BE") and len(digits) == 10:
                sep = self.rng.choice([".", " ", ""])
                text = sep.join(digits[i:i + 2] for i in range(0, 10, 2))
            elif c == "RU" and len(digits) == 11:
                text = "+7 (%s) %s-%s-%s" % (digits[1:4], digits[4:7],
                                             digits[7:9], digits[9:])
            elif c in ("US", "CA") and len(digits) == 10:
                text = "%s-%s-%s" % (digits[:3], digits[3:6], digits[6:])
            elif c == "IT":
                text = text.replace(" ", "")
        return text, truth

    # -------------------------------------------------------------
    #  opening hours
    # -------------------------------------------------------------
    def hours(self, schedule, style="compact"):
        """schedule: list of (first_day, last_day, [(open, close), ...])
        with days 0 = Monday and times as (h, m). Returns (text, None):
        HOURS has no format rule, it is normalized as text."""
        lang = self.lang
        days_full = self.lex["weekdays"]["full"]
        days_short = self.lex["weekdays"]["short"]
        rng = self.rng
        use_short = style == "compact"
        parts = []
        for d1, d2, slots in schedule:
            if lang in ("zh", "ja", "ko"):
                parts.append(self._cjk_hours(d1, d2, slots, days_short,
                                             days_full))
                continue
            name = days_short if use_short else days_full
            if d1 == d2:
                days = name[d1]
            elif style == "compact":
                days = "%s%s%s" % (name[d1], rng.choice(["–", "-", " - "]),
                                   name[d2])
            else:
                days = self._day_range_prose(name[d1], name[d2])
            times = self._join_slots(slots, style)
            if style == "compact":
                parts.append("%s%s%s" % (days, rng.choice([" ", ": ", " : "]),
                                         times))
            else:
                parts.append("%s %s" % (days, times))
        joiner = rng.choice([", ", " ; ", " / "]) if style == "compact" \
            else self._and()
        return joiner.join(parts), None

    def _and(self):
        words = (self.lex.get("kw") or {}).get("and") or ["and"]
        return " %s " % words[0]

    def _day_range_prose(self, a, b):
        lang = self.lang
        pattern = {"fr": "du {a} au {b}", "en": "{a} to {b}",
                   "es": "de {a} a {b}", "it": "dal {a} al {b}",
                   "ru": "с {a} по {b}", "ar": "من {a} إلى {b}",
                   "hi": "{a} से {b}"}.get(lang, "{a} - {b}")
        return pattern.format(a=a.lower() if lang in ("fr", "es", "it", "ru")
                              else a, b=b.lower() if lang in
                              ("fr", "es", "it", "ru") else b)

    def _time(self, h, m):
        lang, rng = self.lang, self.rng
        if lang == "fr":
            return ("%dh%02d" % (h, m)) if m else rng.choice(["%dh", "%dh00"]) \
                % h
        if lang == "en" and self.country in ("US", "CA", "AU") and \
                rng.random() < 0.6:
            suffix = "am" if h < 12 else "pm"
            h12 = h % 12 or 12
            return ("%d:%02d%s" % (h12, m, suffix)) if m else "%d%s" % (
                h12, suffix)
        if lang == "ar" and rng.random() < 0.5:
            suffix = "ص" if h < 12 else "م"
            return "%d:%02d %s" % (h % 12 or 12, m, suffix)
        return "%d:%02d" % (h, m) if rng.random() < 0.5 else "%02d:%02d" % (
            h, m)

    def _join_slots(self, slots, style):
        lang = self.lang
        out = []
        for (h1, m1), (h2, m2) in slots:
            a, b = self._time(h1, m1), self._time(h2, m2)
            if style == "compact":
                out.append("%s%s%s" % (a, self.rng.choice(["–", "-", " - "]),
                                       b))
            else:
                pattern = {"fr": "de {a} à {b}", "en": "{a} to {b}",
                           "es": "de {a} a {b}", "it": "dalle {a} alle {b}",
                           "ru": "с {a} до {b}", "ar": "من {a} إلى {b}",
                           "hi": "{a} से {b} तक"}.get(lang, "{a}-{b}")
                out.append(pattern.format(a=a, b=b))
        if style == "compact":
            return self.rng.choice([" / ", ", ", " et " if lang == "fr"
                                    else " / "]).join(out)
        return self._and().join(out)

    def _cjk_hours(self, d1, d2, slots, short, full):
        lang, rng = self.lang, self.rng
        if lang == "ja":
            if (d1, d2) == (0, 4) and rng.random() < 0.5:
                days = "平日"
            else:
                days = short[d1] if d1 == d2 else "%s〜%s" % (short[d1],
                                                             short[d2])
            sep = rng.choice(["〜", "～", "-"])
        elif lang == "ko":
            if (d1, d2) == (0, 4) and rng.random() < 0.5:
                days = "평일"
            else:
                days = short[d1] if d1 == d2 else "%s~%s" % (short[d1],
                                                            short[d2])
            sep = rng.choice(["~", " - ", "-"])
        else:
            if (d1, d2) == (0, 6) and rng.random() < 0.5:
                days = "每天" if self.loc["data"] == "zh" else "每日"
            else:
                days = full[d1] if d1 == d2 else "%s至%s" % (full[d1],
                                                            full[d2])
            sep = rng.choice(["-", "—", "～"])
        times = []
        for (h1, m1), (h2, m2) in slots:
            times.append("%d:%02d%s%d:%02d" % (h1, m1, sep, h2, m2))
        return "%s %s" % (days, " ".join(times) if lang != "ko" else
                          ", ".join(times))
