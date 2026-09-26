"""
gen/render.py - write true values into cells the way people of each
country type them.

A Fmt object belongs to ONE sheet: it fixes the sheet's styles once (the
money style, the date style, the thousands separator...) so that one
column is written consistently, as in real sheets. Each method returns a
cell value and its number format:

    value, fmt = f.money(12.5)          # xlsx: (12.5, '#,##0.00 "€"')
                                        # csv:  ('12,50 €', None)

`typed` is True for an .xlsx sheet (Excel types: numbers, datetimes,
times...) and False for a .csv sheet (everything is text).

Every style written here must be readable by the helpers (helpers.py):
the generator's self-check runs the real helpers on every generated
sheet and throws away any task where they disagree with the truth.
"""
import datetime
import re

import helpers as H
from gen import data as D

GENITIVE_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
               "июля", "августа", "сентября", "октября", "ноября",
               "декабря"]
ERA_BASES = [("令和", 2019, datetime.date(2019, 5, 1)),
             ("平成", 1989, datetime.date(1989, 1, 8)),
             ("昭和", 1926, datetime.date(1926, 12, 25))]
ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"


def to_arabic_digits(text):
    """ASCII digits -> Arabic-Indic; a separator BETWEEN two digits
    becomes ٬ or ٫ (the dot of ج.م or ر.س stays a dot)."""
    out = []
    for i, ch in enumerate(text):
        between = 0 < i < len(text) - 1 and text[i - 1].isdigit() and \
            text[i + 1].isdigit()
        if "0" <= ch <= "9":
            out.append(ARABIC_INDIC[int(ch)])
        elif ch == "," and between:
            out.append("٬")
        elif ch == "." and between:
            out.append("٫")
        else:
            out.append(ch)
    return "".join(out)


def to_fullwidth_digits(text):
    return "".join(chr(ord(ch) - 0x30 + 0xFF10) if "0" <= ch <= "9" else ch
                   for ch in text)


class Fmt:
    """The writing styles of one sheet."""

    def __init__(self, rng, loc, typed):
        self.rng, self.loc, self.typed = rng, loc, typed
        self.lang, self.country = loc["lang"], loc["country"]
        self.folder = loc["data"]
        self.values = D.values(self.folder)
        self.decimal = loc["decimal"]
        seps = [t for t in loc["thousands"]] + [""]
        if self.lang == "en" and self.country == "IN":
            seps = [","]
        self.thousands = rng.choice(seps)
        self.cents = loc["cents"]
        self.money_style = rng.choice(loc["money"])
        self.money_format = rng.choice(loc["money_formats"])
        self.date_style = rng.choice(loc["dates"])
        self.date_pad = rng.random() < 0.75
        self.two_digit_year = rng.random() < 0.1 and \
            self.date_style in ("D/M/Y", "D.M.Y", "D-M-Y")
        self.time_style = self._pick_time_style()
        self.hour_style = self._pick_hours_style()
        self.duration_style = self._pick_duration_style()
        self.percent_space = rng.random() < (0.7 if self.lang == "fr"
                                             else 0.2)
        self.upper_words = rng.random() < 0.1

    # -------------------------------------------------------- numbers
    def group(self, digits):
        """'1240000' -> '1 240 000' with this sheet's separator (Indian
        lakh grouping for India)."""
        sep = self.thousands
        if not sep or len(digits) <= 3:
            return digits
        if self.country == "IN" and sep == ",":
            head, tail = digits[:-3], digits[-3:]
            parts = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            return ",".join(parts + [tail])
        parts = []
        while len(digits) > 3:
            parts.insert(0, digits[-3:])
            digits = digits[:-3]
        parts.insert(0, digits)
        return sep.join(parts)

    def number_text(self, x, decimals):
        negative = x < 0
        x = abs(x)
        text = "%.*f" % (decimals, x)
        whole, _, frac = text.partition(".")
        out = self.group(whole) + ((self.decimal + frac) if decimals else "")
        return ("-" + out) if negative else out

    def money_decimals(self, x):
        return 2 if self.cents else 0

    def money_text(self, x, symbol=True):
        body = self.number_text(x, self.money_decimals(x))
        if not symbol:
            return body
        if x < 0:
            neg = self.number_text(-x, self.money_decimals(x))
            return "-" + self.money_style.format(n=neg)
        return self.money_style.format(n=body)

    def money(self, x, symbol=True, fmt_currency=False):
        """An amount. symbol: show the currency in a text cell;
        fmt_currency: in xlsx, a number format that shows the currency."""
        if self.typed:
            value = int(x) if float(x).is_integer() else float(x)
            if fmt_currency:
                return value, self.money_format
            return value, "#,##0.00" if self.cents else "#,##0"
        return self.money_text(x, symbol), None

    def integer(self, n, unit=None):
        if self.typed and not unit:
            return int(n), "General"
        text = self.number_text(n, 0) if abs(n) >= 1000 else str(n)
        return (text + " " + unit) if unit else text, None

    def percent(self, rate):
        """rate is a fraction (0.2 = 20 %)."""
        pct = round(rate * 100, 6)
        # as many decimals as the rate needs (8.25 % -> 2), at most 3
        decimals = next(d for d in (0, 1, 2, 3)
                        if d == 3 or round(pct, d) == pct)
        if self.typed and self.rng.random() < 0.7:
            return rate, "0%" if decimals == 0 else "0." + "0" * decimals + "%"
        text = self.number_text(pct, decimals)
        return text + (" %" if self.percent_space else "%"), None

    # -------------------------------------------------------- dates
    def month_name(self, month, short=False):
        if self.lang == "ru":
            return GENITIVE_RU[month - 1]
        months = self.values.get("months") or {}
        names = (months.get("short") if short else None) or \
            months.get("full") or []
        if len(names) == 12:
            return names[month - 1]
        return datetime.date(2000, month, 1).strftime("%B")

    def date_text(self, d, style=None):
        style = style or self.date_style
        y, m, dd = d.year, d.month, d.day
        p = (lambda n: "%02d" % n) if self.date_pad else str
        yy = ("%02d" % (y % 100)) if self.two_digit_year else str(y)
        if style == "D/M/Y":
            return "%s/%s/%s" % (p(dd), p(m), yy)
        if style == "D.M.Y":
            return "%s.%s.%s" % (p(dd), p(m), yy)
        if style == "D-M-Y":
            return "%s-%s-%s" % (p(dd), p(m), yy)
        if style == "M/D/Y":
            return "%s/%s/%s" % (p(m), p(dd), y)
        if style == "Y-M-D":
            return "%04d-%02d-%02d" % (y, m, dd)
        if style == "Y/M/D":
            return "%d/%s/%s" % (y, p(m), p(dd))
        if style == "Y.M.D.":
            return "%d.%s.%s." % (y, p(m), p(dd)) if self.date_pad else \
                "%d. %d. %d." % (y, m, dd)
        if style in ("Y年M月D日",):
            return "%d年%d月%d日" % (y, m, dd)
        if style == "Y년 M월 D일":
            return "%d년 %d월 %d일" % (y, m, dd)
        if style == "民國Y/M/D":
            return "民國%d/%02d/%02d" % (y - 1911, m, dd)
        if style == "ERA":
            for name, base, start in ERA_BASES:
                if d >= start:
                    n = y - base + 1
                    return "%s%s年%d月%d日" % (name, "元" if n == 1 else n,
                                            m, dd)
            return "%d年%d月%d日" % (y, m, dd)
        if style == "MON D, Y":
            return "%s %d, %d" % (self.month_name(m, self.rng.random() <
                                                  0.4), dd, y)
        if style == "D MON Y":
            return "%d %s %d" % (dd, self.month_name(m), y)
        if style == "D de MON de Y":
            return "%d de %s de %d" % (dd, self.month_name(m), y)
        return d.isoformat()

    def date(self, d):
        if self.typed:
            fmt = {"D/M/Y": "dd/mm/yyyy", "D.M.Y": "dd.mm.yyyy",
                   "D-M-Y": "dd-mm-yyyy", "M/D/Y": "m/d/yyyy",
                   "Y-M-D": "yyyy-mm-dd", "Y/M/D": "yyyy/m/d",
                   "Y.M.D.": "yyyy.mm.dd.", "Y年M月D日": 'yyyy"年"m"月"d"日"',
                   "Y년 M월 D일": 'yyyy"년" m"월" d"일"'}.get(
                       self.date_style, "yyyy-mm-dd")
            return datetime.datetime(d.year, d.month, d.day), fmt
        return self.date_text(d), None

    # -------------------------------------------------------- times
    def _pick_time_style(self):
        lang, rng = self.lang, self.rng
        options = ["HH:MM"]
        if lang == "fr":
            options += ["HhMM", "HhMM"]
        if lang == "en" and self.country in ("US", "CA", "AU", "IN", "NG"):
            options += ["AMPM", "AMPM"]
        if lang == "ja":
            options += ["JA", "JA_AMPM"]
        if lang == "ko":
            options += ["KO"]
        if lang == "zh":
            options += ["ZH_AMPM"]
        if lang == "it":
            options += ["HH.MM"]
        return rng.choice(options)

    def time_text(self, t, style=None):
        style = style or self.time_style
        h, m = t.hour, t.minute
        if style == "HhMM":
            return "%dh%02d" % (h, m) if m else "%dh" % h
        if style == "HH.MM":
            return "%02d.%02d" % (h, m)
        if style == "AMPM":
            h12 = h % 12 or 12
            mark = "AM" if h < 12 else "PM"
            if self.rng.random() < 0.3:
                mark = mark.lower()
            return "%d:%02d %s" % (h12, m, mark)
        if style == "JA":
            return "%d時%02d分" % (h, m) if m else "%d時" % h
        if style == "JA_AMPM":
            h12 = h % 12 or 12
            return "%s%d時%s" % ("午前" if h < 12 else "午後", h12,
                                 ("%d分" % m) if m else "")
        if style == "KO":
            h12 = h % 12 or 12
            return "%s %d시%s" % ("오전" if h < 12 else "오후", h12,
                                  (" %d분" % m) if m else "")
        if style == "ZH_AMPM":
            h12 = h % 12 or 12
            return "%s%d:%02d" % ("上午" if h < 12 else "下午", h12, m)
        return "%02d:%02d" % (h, m)

    def time(self, t):
        if self.typed:
            return datetime.time(t.hour, t.minute), \
                "h:mm AM/PM" if self.time_style == "AMPM" else "hh:mm"
        return self.time_text(t), None

    def datetime_cell(self, d, t):
        """A date and a time in one cell (bookings, trap T11)."""
        if self.typed:
            fmt = {"M/D/Y": "m/d/yyyy h:mm AM/PM"}.get(self.date_style,
                                                      "dd/mm/yyyy hh:mm")
            return datetime.datetime(d.year, d.month, d.day, t.hour,
                                     t.minute), fmt
        style = self.date_style if self.date_style not in (
            "ERA", "民國Y/M/D", "MON D, Y", "D MON Y", "D de MON de Y") \
            else "Y-M-D"
        tstyle = self.time_style if self.time_style in (
            "HH:MM", "HhMM", "AMPM") else "HH:MM"
        return "%s %s" % (self.date_text(d, style),
                          self.time_text(t, tstyle)), None

    # -------------------------------------------------------- hours
    def _pick_hours_style(self):
        lang = self.lang
        options = ["HH:MM"]
        if lang == "fr":
            options += ["Hh", "Hh"]
        if lang == "en" and self.country in ("US", "CA", "AU", "IN", "NG"):
            options += ["AMPM"]
        if lang == "ja":
            options += ["JA"]
        if lang == "ko":
            options += ["KO"]
        return self.rng.choice(options)

    def hours_text(self, ranges, closed_word=None):
        """ranges: [(time, time), ...] or [] for closed."""
        if not ranges:
            return closed_word or self.closed_word()
        style = self.hour_style
        dash = self.rng.choice(["-", "–", " - "]) if style not in ("JA",) \
            else "〜"
        if style == "KO":
            dash = self.rng.choice(["~", " - "])
        parts = []
        for a, b in ranges:
            if style == "Hh":
                pa = "%dh%s" % (a.hour, ("%02d" % a.minute) if a.minute
                                else "")
                pb = "%dh%s" % (b.hour, ("%02d" % b.minute) if b.minute
                                else "")
            elif style == "AMPM":
                pa, pb = self.time_text(a, "AMPM"), self.time_text(b, "AMPM")
            elif style == "JA":
                pa = "%d時%s" % (a.hour, ("%d分" % a.minute) if a.minute
                                 else "")
                pb = "%d時%s" % (b.hour, ("%d分" % b.minute) if b.minute
                                 else "")
            elif style == "KO":
                pa, pb = self.time_text(a, "KO"), self.time_text(b, "KO")
            else:
                pa, pb = "%02d:%02d" % (a.hour, a.minute), \
                    "%02d:%02d" % (b.hour, b.minute)
            parts.append(pa + dash + pb)
        joiner = self.rng.choice([" / ", ", ", " / "]) if style == "Hh" \
            else self.rng.choice([", ", " / ", "; "])
        return joiner.join(parts)

    def closed_word(self):
        words = [w for w in self.values.get("closed") or []
                 if H.hours(w, self.loc["code"]) == (True, "closed")]
        return self.rng.choice(words) if words else "-"

    # -------------------------------------------------------- durations
    def _pick_duration_style(self):
        lang = self.lang
        options = ["MIN", "MIN", "HM"]
        if lang in ("fr", "en", "es", "it", "ru"):
            options += ["HhMM"]
        if lang in ("en", "fr"):
            options += ["H:MM"]
        return self.rng.choice(options)

    def minute_word(self):
        words = [w for w in self.values.get("minute_words") or []
                 if H.duration("30 " + w, self.loc["code"]) == (True, 30)]
        return words[0] if words else "min"

    def hour_word(self):
        words = [w for w in self.values.get("hour_words") or []
                 if H.duration("2 " + w, self.loc["code"]) == (True, 120)]
        return words[0] if words else "h"

    def duration_text(self, minutes, style=None):
        style = style or self.duration_style
        h, m = divmod(minutes, 60)
        mw, hw = self.minute_word(), self.hour_word()
        cjk = self.lang in ("zh", "ja", "ko")
        sp = "" if cjk else " "
        if style == "PLAIN":
            return str(minutes)
        if style == "MIN" or h == 0:
            return "%d%s%s" % (minutes, sp, mw)
        if style == "H:MM":
            return "%d:%02d" % (h, m)
        if style == "HhMM" and hw in ("h", "ч", "ч."):
            return "%d%s%s" % (h, hw, ("%02d" % m) if m else "")
        if m == 0:
            return "%d%s%s" % (h, sp, hw)
        return "%d%s%s%s%d%s%s" % (h, sp, hw, " " if not cjk or
                                   self.lang == "ko" else "", m, sp, mw)

    def duration(self, minutes, plain=False):
        if self.typed and (plain or self.rng.random() < 0.3):
            if self.rng.random() < 0.5 or plain:
                return int(minutes), "General"
            return datetime.timedelta(minutes=minutes), "[h]:mm"
        if plain:
            return str(minutes), None
        return self.duration_text(minutes), None

    # -------------------------------------------------------- words
    def weekday_text(self, day, form):
        wd = self.values.get("weekdays") or {}
        names = wd.get(form) or wd.get("full")
        text = names[day]
        if self.upper_words and self.lang not in ("zh", "ja", "ko", "ar",
                                                  "hi"):
            text = text.upper()
        return text

    def yes_no(self, value, words):
        return words[0] if value else words[1]

    def phone_text(self, e164):
        import phonenumbers
        num = phonenumbers.parse(e164, None)
        style = self.rng.choice(["national", "national", "international"])
        if style == "national":
            return phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.NATIONAL)
        return phonenumbers.format_number(
            num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

    def digits(self, text, arabic, full):
        """Arabic-Indic or full-width digits in text cells (section
        10.5), decided per column by the caller."""
        if arabic:
            return to_arabic_digits(text)
        if full:
            return to_fullwidth_digits(text)
        return text
