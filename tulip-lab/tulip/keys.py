"""
keys.py - when do two rows describe the same thing? (Tulip 1.1, items B
and E). Plain code over the rows in the declared format.

    keys.normal("Pain au Chocolat 70 g")   -> "pain au chocolat 70g"
    keys.group_key("products", row)         -> the key that groups rows of
                                               several sheets (compare.py)
    keys.match_keys("products", old, new)   -> the keys that pair the rows
                                               of two versions of ONE sheet
                                               (history.py)

A key is a normalised text: Unicode NFKC, case folded, accents of Latin,
Greek and Cyrillic letters and Arabic short vowels removed (never the
vowel signs of Hindi or the marks of Japanese kana, which change the
word), Arabic alef forms and Persian ی ک folded, punctuation made spaces,
single spaces, and quantities in one unit: "0,25 kg", "250 gr" and
"250g" are all "250g"; "1 L", "100 cl" and "1000 ml" are all "1000ml"
(the unit words of the ten languages come from gen/data/*/values.json).
"""
import re
import unicodedata

import helpers as H

# the columns that make a row's identity, for grouping rows of several
# sheets (B): what every source of the same thing shares
GROUP_KEY = {
    "products": ["name", "variant"],
    "services": ["name"],
    "opening_hours": ["day"],
    "staff": ["name"],
    "clients": ["name"],
    "bookings": ["date", "start_time", "client"],
    "invoice_ledger": ["number"],
}

# for pairing the rows of two versions of one sheet (E): the first of
# these that EVERY row of both versions has; the last is always usable
MATCH_KEYS = {
    "products": [["sku"], ["barcode"], ["name", "variant"]],
    "services": [["name"]],
    "opening_hours": [["day", "#"]],       # "#": the range's rank in its day
    "staff": [["email"], ["name"]],
    "clients": [["reg_id"], ["email"], ["name"]],
    "bookings": [["date", "start_time", "client"]],
    "invoice_ledger": [["number"]],
}

# a quantity and its unit -> grams or millilitres
FACTORS = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1),
           "cl": ("ml", 10), "dl": ("ml", 100), "l": ("ml", 1000)}
EXTRA_UNITS = {"cl": ["cl", "сл"], "dl": ["dl", "дл"]}


def _unit_words():
    """{normalised unit word: unit} from every language's values.json."""
    words = {}
    for datas in H._values().values():
        for data in datas:
            for unit, forms in (data.get("units") or {}).items():
                if unit in FACTORS:
                    for w in forms:
                        words[_fold(w).strip(". ")] = unit
    for unit, forms in EXTRA_UNITS.items():
        for w in forms:
            words[w] = unit
    return words


_UNITS = None
_QUANTITY = None


def _quantity_rx():
    global _UNITS, _QUANTITY
    if _QUANTITY is None:
        _UNITS = _unit_words()
        alternation = "|".join(re.escape(w) for w in sorted(
            _UNITS, key=len, reverse=True) if w)
        # a number (not the end of a longer one), maybe a space, a unit
        # word that is not the start of a longer word ("250 g", "0,25kg",
        # "1 л", "牛奶1升"); "x6" pack counts stay as they are
        _QUANTITY = re.compile(
            r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s?(%s)(?![^\W\d_])" % alternation)
    return _QUANTITY


def _fold(text):
    """NFKC, case folded, Latin/Greek/Cyrillic accents and Arabic short
    vowels removed, Arabic letter forms folded."""
    t = unicodedata.normalize("NFKC", str(text)).casefold()
    out = []
    for ch in unicodedata.normalize("NFD", t):
        if unicodedata.category(ch) == "Mn" and out and \
                ord(out[-1]) < 0x0530:
            continue                   # an accent on a Latin/Greek/Cyrillic
        if "ً" <= ch <= "ٟ" or ch in "ٰـ":
            continue                   # Arabic short vowels, tatweel
        out.append(ch)
    t = unicodedata.normalize("NFC", "".join(out))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ی", "ي"),
                 ("ک", "ك")):
        t = t.replace(a, b)
    return t


def _number(text):
    return float(text.replace(",", "."))


def normal_units(text):
    """Quantities in grams or millilitres: "0,25 kg" -> "250g"."""
    rx = _quantity_rx()

    def one(m):
        unit = _UNITS.get(m.group(2))
        if unit is None:
            return m.group(0)
        base, factor = FACTORS[unit]
        value = _number(m.group(1)) * factor
        return "%s%s" % (("%.3f" % value).rstrip("0").rstrip("."), base)
    return rx.sub(one, text)


def normal(value):
    """A value -> its key text ("" for None)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    t = _fold(H.ascii_digits(str(value)))
    t = normal_units(t)
    # letters, marks (Hindi vowel signs) and digits stay; the rest is a
    # space
    t = "".join(ch if unicodedata.category(ch)[0] in "LMN" else " "
                for ch in t)
    # digits apart from letters: "牛奶1000ml" and "牛奶 1000 ml" are one
    t = re.sub(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])", " ", t)
    return " ".join(t.split())


def group_key(target, row):
    """The key under which rows of several sheets are the same thing, or
    None when the row has none of its key's values."""
    parts = [normal(row.get(c)) for c in GROUP_KEY[target]]
    if not parts[0]:
        return None
    return "|".join(parts)


def _ranks(target, rows):
    """For opening hours: the rank of each row among its day's rows."""
    seen, out = {}, []
    for row in rows:
        day = row.get("day")
        seen[day] = seen.get(day, 0) + 1
        out.append(seen[day])
    return out


def match_keys(target, old_rows, new_rows):
    """-> (the columns used, keys of old_rows, keys of new_rows): the
    first key of MATCH_KEYS[target] that every row of both versions has
    (a sheet that gained a SKU column is paired by name). Rows with the
    same key are paired in their order: the n-th of one version with the
    n-th of the other."""
    choices = MATCH_KEYS[target]
    for cols in choices:
        plain = [c for c in cols if c != "#"]
        if cols is choices[-1] or all(
                all(r.get(c) not in (None, "") for c in plain[:1])
                for r in list(old_rows) + list(new_rows)):
            break

    def keys(rows):
        ranks = _ranks(target, rows)
        out, count = [], {}
        for row, rank in zip(rows, ranks):
            k = "|".join(str(rank) if c == "#" else normal(row.get(c))
                         for c in cols)
            count[k] = count.get(k, 0) + 1
            out.append(k if count[k] == 1 else "%s#%d" % (k, count[k]))
        return out
    return cols, keys(old_rows), keys(new_rows)
