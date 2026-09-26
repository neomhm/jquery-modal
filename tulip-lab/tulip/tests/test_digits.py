"""Other digit scripts (section 10.5): every helper that reads ASCII
digits reads Arabic-Indic, Persian, Devanagari and full-width digits too,
and full-width punctuation (： ／ － ． ，), giving the same value.

The conversions are written here on purpose, not imported from gen/:
the generator writes the digits, the helpers read them, and this test
states the contract between the two independently of either."""
import config                    # noqa: F401  (vendor/ wheels: phonenumbers)
import helpers
import test_helpers

ARABIC = "٠١٢٣٤٥٦٧٨٩"
PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
DEVANAGARI = "०१२३४५६७८९"
FULL_PUNCT = {":": "：", "/": "／", "-": "－", ".": "．", ",": "，",
              "%": "％", "(": "（", ")": "）", "~": "～", " ": "　"}


def arabic(text):
    """As gen/render.py writes it: a , or . BETWEEN two digits becomes
    ٬ or ٫ (the dot of ج.م or ر.س stays a dot)."""
    out = []
    for i, ch in enumerate(text):
        between = 0 < i < len(text) - 1 and text[i - 1].isdigit() and \
            text[i + 1].isdigit()
        if "0" <= ch <= "9":
            out.append(ARABIC[int(ch)])
        elif ch == "," and between:
            out.append("٬")
        elif ch == "." and between:
            out.append("٫")
        else:
            out.append(ch)
    return "".join(out)


def script(digits):
    return lambda t: "".join(digits[int(c)] if "0" <= c <= "9" else c
                             for c in t)


def full(text):
    return "".join(chr(ord(c) - 0x30 + 0xFF10) if "0" <= c <= "9" else c
                   for c in text)


def full_punct(text):
    return "".join(FULL_PUNCT.get(c, c) for c in full(text))


VARIANTS = [("arabic", arabic), ("persian", script(PERSIAN)),
            ("devanagari", script(DEVANAGARI)), ("full", full),
            ("full+punct", full_punct)]

# (helper, ASCII text, locale): one or more of every kind of text cell
# the generator fills (dates, times, datetimes, durations, phones, stock
# and other integers, invoice numbers, money, percentages, hours, yes/no)
CELLS = [
    ("date", "15/03/2024", "ar-EG"), ("date", "15-03-2024", "ar-SA"),
    ("date", "2024/03/15", "ja-JP"), ("date", "2024-03-15", "ja-JP"),
    ("date", "2024年3月15日", "ja-JP"), ("date", "15 مارس 2024", "ar-EG"),
    ("date", "15.03.2024", "ar-EG"), ("date", "03/15/2024", "en-US"),
    ("date", "15/03/2024 14:30", "ar-EG"), ("date", "2024-03-15 14:30",
                                             "ja-JP"),
    ("time", "14:30", "ar-SA"), ("time", "2:30 م", "ar-EG"),
    ("time", "14時30分", "ja-JP"), ("time", "午後2:30", "ja-JP"),
    ("time", "15/03/2024 14:30", "ar-EG"), ("time", "9.30", "ar-SA"),
    ("hours", "09:00-18:00", "ar-SA"), ("hours", "9:00 ص - 6:00 م",
                                        "ar-EG"),
    ("hours", "9時〜18時", "ja-JP"), ("hours", "10:00-13:00, 16:00-22:00",
                                     "ar-SA"),
    ("duration", "90", "ar-SA"), ("duration", "1:30", "ja-JP"),
    ("duration", "90 دقيقة", "ar-EG"), ("duration", "45分", "ja-JP"),
    ("duration", "1 ساعة 30 دقيقة", "ar-SA"), ("duration", "1,5 h", "fr-FR"),
    ("phone", "+966 50 123 4567", "ar-SA"), ("phone", "050 123 4567",
                                             "ar-SA"),
    ("phone", "+20 10 1234 5678", "ar-EG"), ("phone", "03-1234-5678",
                                             "ja-JP"),
    ("phone", "(03) 1234-5678", "ja-JP"),
    ("integer", "40", "ar-EG"), ("integer", "1,240", "ar-SA"),
    ("integer", "40 قطعة", "ar-EG"), ("integer", "12個", "ja-JP"),
    ("integer", "-3", "ja-JP"), ("integer", "1,000", "ja-JP"),
    ("amount", "1,240.50", "ar-SA"), ("amount", "1,240.50 ر.س", "ar-SA"),
    ("amount", "ج.م 1,240", "ar-EG"), ("amount", "¥1,240", "ja-JP"),
    ("amount", "1,240円", "ja-JP"), ("amount", "(120.00)", "ar-EG"),
    ("amount", "-45.00", "ja-JP"), ("amount", "1,000万円", "ja-JP"),
    ("amount", "12.5 ألف", "ar-SA"),
    ("currency", "[$€-40C] #,##0.00", "fr-FR"), ("currency", "1,240 ر.س",
                                                 "ar-SA"),
    ("currency", "¥1,240", "ja-JP"),
    ("percent", "15%", "ar-SA"), ("percent", "5.5 %", "ja-JP"),
    ("percent", "0.15", "ar-EG"),
    ("boolean", "1", "ar-SA"), ("boolean", "0", "ja-JP"),
    ("email", "sales2024@example.com", "ar-SA"),
]


def _same(cells):
    wrong = []
    for name, value, locale in cells:
        base = helpers.HELPERS[name](value, locale)
        if base[0] is not True:
            wrong.append("ASCII %s(%r, %r) itself fails" % (name, value,
                                                           locale))
            continue
        for label, convert in VARIANTS:
            other = convert(value)
            if other == value:
                continue
            got = helpers.HELPERS[name](other, locale)
            if got != base or type(got[1]) is not type(base[1]):
                wrong.append("%s %s(%r, %r) -> %r, ASCII gives %r"
                             % (label, name, other, locale, got, base))
    assert not wrong, "\n" + "\n".join(wrong)


def test_every_kind_of_cell_reads_other_digits():
    _same(CELLS)


def test_appendix_i_cases_read_other_digits():
    """Every text case of Appendix I that passes in ASCII gives the same
    answer with its digits in another script - except text(), whose
    result keeps the cell's own characters (NFKC only, section 9)."""
    cells = [(name, value, locale)
             for _, name, value, locale, expected in test_helpers.CASES
             if isinstance(value, str) and name != "text" and
             expected != "FAIL" and expected != "HIJRI" and
             helpers.HELPERS[name](value, locale)[0]]
    assert len(cells) > 100, len(cells)
    _same(cells)


def test_failures_stay_failures():
    """Another digit script never makes an unreadable cell readable."""
    for name, value, locale in [("date", "mars 2024", "fr-FR"),
                                ("amount", "1.240", None),
                                ("integer", "40.5", "ar-SA"),
                                ("time", "25:00", "ja-JP"),
                                ("date", "31/02/2024", "ar-EG")]:
        for label, convert in VARIANTS:
            got = helpers.HELPERS[name](convert(value), locale)
            assert got == (False, None), (label, name, value, got)


def test_text_keeps_arabic_digits_and_folds_full_width():
    """text() is NFKC (section 9): full-width digits become ASCII, and
    Arabic-Indic digits are kept as written - the generator's truth for a
    text field is computed the same way."""
    assert helpers.text("ＩＮＶ－００１２３", "ja-JP") == (True, "INV-00123")
    assert helpers.text("INV-٠٠١٢٣", "ar-SA") == (True, "INV-٠٠١٢٣")
