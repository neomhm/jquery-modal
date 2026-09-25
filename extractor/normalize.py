"""
normalize.py - turns the text of a span into a value (section 14.2).

    normalize(label, text, lang=None, country=None) -> dict

It always returns a dict and never raises. "ok" says whether the text
could be read without doubt:

    {"ok": True, "kind": "amount", "value": 1240000.0, "currency": "EUR",
     "currency_candidates": []}
    {"ok": False, "kind": "amount", "reason": "ambiguous_separator",
     "candidates": [1240.0, 1.24]}

This is plain code, never a model. Every rule below comes from section
14.2 of the build instructions; the test cases of Appendix I are in
tests/test_normalize.py.
"""
import datetime
import functools
import json
import pathlib
import re
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
GEN_DATA = HERE / "gen" / "data"

KIND_OF_LABEL = {
    "REVENUE": "amount", "CAPITAL": "amount", "DOC_TOTAL": "amount",
    "LINE_TOTAL": "amount", "PRICE": "amount",
    "FOUNDED": "date", "DOC_DATE": "date",
    "REVENUE_YEAR": "year",
    "STAFF": "count",
    "S_PHONE": "phone",
    "S_EMAIL": "email", "S_URL": "url",
    "S_REG_ID": "reg_id", "C_REG_ID": "reg_id",
    "LEGAL_FORM": "legal_form",
    "ACTIVITY_CODE": "activity_code",
}


def this_year():
    """The current year, never before the synthetic world's reference
    year (2026), so the generated data always passes the sanity rules."""
    return max(datetime.date.today().year, 2026)


# =====================================================================
#  digits and spaces
# =====================================================================
DIGITS = {}
for _base in (0x0660, 0x06F0, 0x0966):        # Arabic-Indic, Persian, Deva
    for _k in range(10):
        DIGITS[chr(_base + _k)] = str(_k)
ARABIC_SEPARATORS = {"٬": ",", "٫": ".", "،": ","}


def ascii_digits(text):
    """NFKC (full-width -> ASCII, odd spaces -> space), then every digit
    script -> ASCII and the Arabic separators -> ',' and '.'.
    Returns (text, had_arabic_indic)."""
    text = unicodedata.normalize("NFKC", text or "")
    had_arabic = any("٠" <= ch <= "٩" or "۰" <= ch <= "۹" or ch in "٬٫"
                     for ch in text)
    out = []
    for ch in text:
        if ch in DIGITS:
            out.append(DIGITS[ch])
        elif ch in "٬٫":
            out.append(ARABIC_SEPARATORS[ch])
        else:
            out.append(ch)
    text = "".join(out)
    text = re.sub(r"[    ​　\t]", " ", text)
    return text, had_arabic


def single_spaces(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")
                  ).strip()


# =====================================================================
#  languages and countries
# =====================================================================
COMMA_DECIMAL_COUNTRIES = {"FR", "BE", "ES", "AR", "CO", "CL", "IT", "RU",
                           "KZ", "BY", "MA", "SN", "PT", "DE", "BR"}
DOT_DECIMAL_COUNTRIES = {"US", "GB", "IN", "AU", "NG", "CN", "TW", "HK",
                         "SG", "JP", "KR", "SA", "AE", "EG", "MX", "CH"}
MAIN_COUNTRY = {"ja": "JP", "ko": "KR", "hi": "IN", "it": "IT"}


def decimal_separator(lang, country):
    """',' or '.', or None when nothing decides (section 14.2, rule 5)."""
    if lang == "ar":
        return "," if country == "MA" else "."
    if lang in ("fr", "it"):
        return "." if country == "CH" else ","
    if lang == "es":
        return "." if country == "MX" else ","
    if lang == "ru":
        return ","
    if lang in ("en", "zh", "ja", "ko", "hi"):
        return "."
    if country in COMMA_DECIMAL_COUNTRIES:
        return ","
    if country in DOT_DECIMAL_COUNTRIES:
        return "."
    return None


# =====================================================================
#  currencies
# =====================================================================
DOLLAR_OF = {"US": "USD", "CA": "CAD", "AU": "AUD", "MX": "MXN",
             "AR": "ARS", "CO": "COP", "CL": "CLP", "SG": "SGD",
             "HK": "HKD", "TW": "TWD", "NZ": "NZD"}
PESO_OF = {"MX": "MXN", "AR": "ARS", "CO": "COP", "CL": "CLP"}


def _dollar(lang, country):
    return DOLLAR_OF.get(country, "USD"), []


def _peso(lang, country):
    if country in PESO_OF:
        return PESO_OF[country], []
    return None, ["MXN", "ARS", "COP", "CLP"]


def _yen_yuan(lang, country):
    if country == "JP" or (country is None and lang == "ja"):
        return "JPY", []
    if country == "CN" or (country is None and lang == "zh"):
        return "CNY", []
    return None, ["JPY", "CNY"]


def _yuan(lang, country):
    code = {"CN": "CNY", "TW": "TWD", "HK": "HKD", "SG": "SGD"}.get(country)
    if code:
        return code, []
    return "CNY", []


def _dirham(lang, country):
    if country == "AE":
        return "AED", []
    if country == "MA":
        return "MAD", []
    return None, ["AED", "MAD"]


def _riyal(lang, country):
    if country == "SA":
        return "SAR", []
    return None, ["SAR", "QAR", "OMR", "YER"]


def _ruble(lang, country):
    if country == "BY":
        return "BYN", []
    return "RUB", []


def _franc(lang, country):
    if country == "CH":
        return "CHF", []
    if country in ("SN", "CI", "ML", "BF", "NE", "TG", "BJ"):
        return "XOF", []
    return None, ["CHF", "XOF"]


def _naira_n(lang, country):
    return ("NGN", []) if country == "NG" else (None, [])


# (token, code or resolver). Longer tokens are tried first; tokens made
# of letters must stand alone (not inside a word).
CURRENCY_TOKENS = [
    # dollars and pesos with a country mark
    ("US$", "USD"), ("U$S", "USD"), ("USD", "USD"), ("NT$", "TWD"),
    ("HK$", "HKD"), ("S$", "SGD"), ("A$", "AUD"), ("AU$", "AUD"),
    ("C$", "CAD"), ("CA$", "CAD"), ("$ CA", "CAD"), ("$CA", "CAD"),
    ("CAD", "CAD"), ("AUD", "AUD"), ("SGD", "SGD"), ("HKD", "HKD"),
    ("TWD", "TWD"), ("NTD", "TWD"), ("NZD", "NZD"),
    ("MXN", "MXN"), ("M.N.", "MXN"), ("ARS", "ARS"), ("COP", "COP"),
    ("CLP", "CLP"), ("pesos mexicanos", "MXN"), ("de pesos", _peso),
    ("pesos", _peso), ("peso", _peso),
    ("dólares", "USD"), ("dolares", "USD"), ("de dollars", _dollar),
    ("dollars", _dollar), ("dollar", _dollar), ("долларов", "USD"),
    ("доллар", "USD"), ("美元", "USD"), ("ドル", "USD"), ("달러", "USD"),
    ("دولار", "USD"), ("डॉलर", "USD"), ("$", _dollar),
    # euro
    ("€", "EUR"), ("EUR", "EUR"), ("d'euros", "EUR"), ("d’euros", "EUR"),
    ("de euros", "EUR"), ("di euro", "EUR"), ("euros", "EUR"),
    ("euro", "EUR"), ("евро", "EUR"), ("يورو", "EUR"), ("यूरो", "EUR"),
    ("ユーロ", "EUR"), ("欧元", "EUR"), ("歐元", "EUR"), ("유로", "EUR"),
    # pound
    ("£", "GBP"), ("GBP", "GBP"), ("pounds", "GBP"), ("pound", "GBP"),
    ("sterling", "GBP"),
    # rupee
    ("₹", "INR"), ("Rs.", "INR"), ("Rs", "INR"), ("INR", "INR"),
    ("₨", "INR"), ("रु.", "INR"), ("रु॰", "INR"), ("रुपये", "INR"),
    ("रुपए", "INR"), ("रुपया", "INR"), ("रु", "INR"), ("Rupees", "INR"),
    ("rupees", "INR"), ("Rupee", "INR"), ("rupee", "INR"),
    # rouble, tenge
    ("бел. руб.", "BYN"), ("бел.руб.", "BYN"), ("BYN", "BYN"),
    ("₽", "RUB"), ("RUB", "RUB"), ("руб.", _ruble), ("рублей", _ruble),
    ("рубля", _ruble), ("рубль", _ruble), ("руб", _ruble), ("р.", _ruble),
    ("₸", "KZT"), ("KZT", "KZT"), ("тенге", "KZT"), ("тг.", "KZT"),
    ("тг", "KZT"),
    # yen, yuan, won
    ("日本円", "JPY"), ("JPY", "JPY"), ("円", "JPY"),
    ("人民币", "CNY"), ("人民幣", "CNY"), ("RMB", "CNY"), ("CNY", "CNY"),
    ("元整", _yuan), ("新臺幣", "TWD"), ("新台幣", "TWD"), ("新台币", "TWD"),
    ("臺幣", "TWD"), ("台幣", "TWD"), ("港幣", "HKD"), ("港币", "HKD"),
    ("港元", "HKD"), ("新加坡元", "SGD"), ("新币", "SGD"), ("新幣", "SGD"),
    ("新元", "SGD"), ("元", _yuan), ("¥", _yen_yuan),
    ("₩", "KRW"), ("KRW", "KRW"), ("원정", "KRW"), ("원", "KRW"),
    # Arabic currencies
    ("ر.س.", "SAR"), ("ر.س", "SAR"), ("ريال سعودي", "SAR"),
    ("SAR", "SAR"), ("ريال", _riyal), ("ريالات", _riyal),
    ("د.إ.", "AED"), ("د.إ", "AED"), ("درهم إماراتي", "AED"),
    ("AED", "AED"), ("د.م.", "MAD"), ("د.م", "MAD"),
    ("درهم مغربي", "MAD"), ("MAD", "MAD"), ("DHS", "MAD"), ("Dhs", "MAD"),
    ("DH", "MAD"), ("de dirhams", "MAD"), ("dirhams", "MAD"),
    ("dirham", "MAD"), ("درهم", _dirham), ("دراهم", _dirham),
    ("ج.م.", "EGP"), ("ج.م", "EGP"), ("جنيه مصري", "EGP"), ("EGP", "EGP"),
    ("جنيه", "EGP"), ("جنيها", "EGP"),
    # francs
    ("de francs CFA", "XOF"), ("francs CFA", "XOF"), ("F CFA", "XOF"),
    ("FCFA", "XOF"), ("XOF", "XOF"), ("CHF", "CHF"), ("Fr.", "CHF"),
    ("francs suisses", "CHF"), ("franchi svizzeri", "CHF"),
    ("franchi", "CHF"), ("de francs", _franc), ("francs", _franc),
    # naira
    ("₦", "NGN"), ("NGN", "NGN"), ("naira", "NGN"),
]
CURRENCY_TOKENS.sort(key=lambda t: -len(t[0]))
WORD_CHARS = r"A-Za-zÀ-ÿА-Яа-яЁё؀-ۿऀ-ॿ"


@functools.lru_cache(maxsize=None)
def _token_regex(token):
    body = re.escape(token)
    if re.search(r"[A-Za-zÀ-ÿА-Яа-яЁё؀-ۿऀ-ॿ]", token):
        body = r"(?<![%s])%s(?![%s])" % (WORD_CHARS, body, WORD_CHARS)
        if token.endswith("."):
            body = body[:-len(r"(?![%s])" % WORD_CHARS)]
    return re.compile(body)


def find_currency(text, lang, country):
    """Removes every currency token from the text.
    -> (text without them, code or None, candidates)."""
    codes, candidates = [], []
    for token, target in CURRENCY_TOKENS:
        rx = _token_regex(token)
        if not rx.search(text):
            continue
        text = rx.sub(" ", text)
        if callable(target):
            code, cands = target(lang, country)
        else:
            code, cands = target, []
        if code:
            codes.append(code)
        else:
            candidates.extend(cands)
    if country == "NG":                  # "N 1,000" in Nigeria
        m = re.search(r"(?<![A-Za-z])N(?=\s?\d)", text)
        if m:
            text = text[:m.start()] + " " + text[m.end():]
            codes.append("NGN")
    code = None
    if codes:
        # an explicit code wins over a symbol ("$1,240,000.00 MXN")
        explicit = [c for c in codes if c != DOLLAR_OF.get(country, "USD")]
        code = explicit[0] if explicit else codes[0]
        candidates = []
    return text, code, sorted(set(candidates))


# =====================================================================
#  magnitude words
# =====================================================================
# (regex, multiplier); 'billion' depends on the language (fr: 1e12)
MAGNITUDES = [
    (r"mil millones", 1e9), (r"MM", 1e6), (r"M€", ("EUR", 1e6)),
    (r"k€", ("EUR", 1e3)), (r"K€", ("EUR", 1e3)), (r"MDHS?", ("MAD", 1e6)),
    (r"MDh", ("MAD", 1e6)),
    (r"millions?", 1e6), (r"millón", 1e6), (r"millones", 1e6),
    (r"milione", 1e6), (r"milioni", 1e6), (r"mln\.?", 1e6),
    (r"Mio\.?", 1e6), (r"mio\.?", 1e6), (r"Mn", 1e6), (r"mn", 1e6),
    (r"млн\.?", 1e6), (r"миллиона?", 1e6), (r"миллионов", 1e6),
    (r"مليون", 1e6), (r"ملايين", 1e6), (r"मिलियन", 1e6),
    (r"milliards?", 1e9), (r"miliardo", 1e9), (r"miliardi", 1e9),
    (r"bn", 1e9), (r"млрд\.?", 1e9), (r"миллиарда?", 1e9),
    (r"مليار", 1e9), (r"مليارات", 1e9), (r"billones", 1e12),
    (r"billón", 1e12), (r"trillions?", 1e12), (r"billions?", "billion"),
    (r"crores?", 1e7), (r"Cr\.?", 1e7), (r"करोड़", 1e7), (r"करोड", 1e7),
    (r"lakhs?", 1e5), (r"lacs?", 1e5), (r"Lakhs?", 1e5), (r"लाख", 1e5),
    (r"thousand", 1e3), (r"mille", 1e3), (r"mila", 1e3), (r"mil", 1e3),
    (r"тыс\.?", 1e3), (r"тысяч[аи]?", 1e3), (r"ألف", 1e3), (r"آلاف", 1e3),
    (r"हज़ार", 1e3), (r"हजार", 1e3), (r"K", 1e3), (r"k", 1e3),
    (r"B", 1e9), (r"M", "M"),
]


def find_magnitude(text, lang):
    """-> (text without the word, multiplier, currency or None,
    ambiguous_m)."""
    for pattern, value in MAGNITUDES:
        rx = re.compile(r"(?<![%s])%s(?![%s])" % (WORD_CHARS, pattern,
                                                  WORD_CHARS))
        m = rx.search(text)
        if not m:
            continue
        if pattern == "B" and lang not in (None, "en"):
            continue
        text = text[:m.start()] + " " + text[m.end():]
        currency = None
        if isinstance(value, tuple):
            currency, value = value
        if value == "billion":
            value = 1e12 if lang == "fr" else 1e9
        if value == "M":
            if lang == "es":
                return text, None, currency, True
            value = 1e6
        return text, value, currency, False
    return text, 1.0, None, False


# =====================================================================
#  reading a number
# =====================================================================
NUMBER_RE = re.compile(r"\d[\d \.,'’]*\d|\d")


def read_number(core, dec, arabic=False):
    """core: digits with separators ('1 240 000,00', "1'240'000").
    dec: the locale's decimal separator or None.
    -> (value, None) or (None, (reason, candidates))."""
    s = re.sub(r"(?<=\d)[ '’](?=\d)", "", core)
    s = s.replace(" ", "")
    if arabic:
        dec = "."
    n_dot, n_comma = s.count("."), s.count(",")
    if n_dot and n_comma:
        decimal = "." if s.rfind(".") > s.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        return _to_float(s.replace(thousands, ""), decimal), None
    if not n_dot and not n_comma:
        return float(s), None
    sep = "." if n_dot else ","
    count = n_dot or n_comma
    if count > 1:                         # 1.240.000 / 12,40,000
        return float(s.replace(sep, "")), None
    after = len(s) - s.rfind(sep) - 1
    if after in (1, 2) or after > 3:
        return _to_float(s, sep), None
    # exactly 3 digits after a single separator: the locale decides
    as_thousands = float(s.replace(sep, ""))
    as_decimal = _to_float(s, sep)
    if dec is None:
        return None, ("ambiguous_separator", [as_thousands, as_decimal])
    return (as_decimal if sep == dec else as_thousands), None


def _to_float(s, decimal):
    if decimal == ",":
        s = s.replace(",", ".")
    return float(s)


CJK_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000,
             "万": 1e4, "萬": 1e4, "亿": 1e8, "億": 1e8, "兆": 1e12,
             "십": 10, "백": 100, "천": 1000, "만": 1e4, "억": 1e8, "조": 1e12}
BIG_UNITS = {"万", "萬", "亿", "億", "兆", "만", "억", "조"}


def read_cjk(text):
    """'1億2,400万' -> 124000000; '12억 4천만' -> 1240000000. Commas
    before a unit are always thousands separators."""
    s = re.sub(r"\s", "", text)
    tokens = re.findall(r"\d[\d,]*(?:\.\d+)?|[十拾百佰千仟万萬亿億兆십백천만억조]",
                        s)
    if not tokens:
        return None
    total, section, current = 0.0, 0.0, None
    for tok in tokens:
        if tok[0].isdigit():
            current = float(tok.replace(",", ""))
        elif tok in BIG_UNITS:
            section += current if current is not None else 0
            total += (section or 1) * CJK_UNITS[tok]
            section, current = 0.0, None
        else:
            section += (current if current is not None else 1) * \
                CJK_UNITS[tok]
            current = None
    total += section + (current or 0)
    return total


def normalize_amount(text, lang=None, country=None):
    t, arabic = ascii_digits(text)
    t = re.sub(r"(\.–|,-|\.-|,–|\.—)(?!\d)", "", t)
    t, code, candidates = find_currency(t, lang, country)
    negative = bool(re.search(r"^\s*[-−–(]|\)\s*$", t.strip())) and \
        bool(re.search(r"\d", t))
    if re.search(r"\d\s*[十拾百佰千仟万萬亿億兆십백천만억조]", t):
        value = read_cjk(t)
        if value is None:
            return {"ok": False, "kind": "amount", "reason": "no_number"}
        return _amount(value, negative, code, candidates)
    t, mult, mag_currency, ambiguous_m = find_magnitude(t, lang)
    if mag_currency and not code:
        code, candidates = mag_currency, []
    m = None
    for m in NUMBER_RE.finditer(t):
        break
    if m is None:
        return {"ok": False, "kind": "amount", "reason": "no_number"}
    core = max(NUMBER_RE.findall(t), key=len)
    value, problem = read_number(core.strip(" .,"), decimal_separator(
        lang, country), arabic)
    if problem:
        reason, cands = problem
        return {"ok": False, "kind": "amount", "reason": reason,
                "candidates": [c * mult for c in cands], "currency": code,
                "currency_candidates": candidates}
    if ambiguous_m:
        return {"ok": False, "kind": "amount", "reason": "ambiguous_M",
                "candidates": [value * 1e3, value * 1e6], "currency": code,
                "currency_candidates": candidates}
    return _amount(value * mult, negative, code, candidates)


def _amount(value, negative, code, candidates):
    value = round(-value if negative else value, 6)
    return {"ok": True, "kind": "amount", "value": float(value),
            "currency": code,
            "currency_candidates": [] if code else candidates}


# =====================================================================
#  dates
# =====================================================================
ERAS = {"明治": 1868, "大正": 1912, "昭和": 1926, "平成": 1989, "令和": 2019}
ENGLISH_MONTHS = ["january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november",
                  "december"]
HIJRI_MONTHS_DEFAULT = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر",
                        "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
                        "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]


def _month_key(name):
    name = unicodedata.normalize("NFKC", name).lower().strip()
    return name.rstrip(".॰")


@functools.lru_cache(maxsize=None)
def month_tables():
    """{name: month} for Gregorian months in every language and form
    (from the lexicons), and {name: month} for Hijri months."""
    greg, hijri = {}, {}
    for k, name in enumerate(ENGLISH_MONTHS):
        greg[name] = k + 1
        greg[name[:3]] = k + 1
    greg["sept"] = 9
    for k, name in enumerate(HIJRI_MONTHS_DEFAULT):
        hijri[_month_key(name)] = k + 1
    hijri[_month_key("ربيع الثاني")] = 4
    hijri[_month_key("جمادى الثانية")] = 6
    hijri[_month_key("جمادى الأول")] = 5
    if GEN_DATA.exists():
        for folder in sorted(GEN_DATA.iterdir()):
            path = folder / "lexicon.json"
            if not path.exists():
                continue
            try:
                lex = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for form, names in (lex.get("months") or {}).items():
                if not isinstance(names, list) or len(names) != 12:
                    continue
                table = hijri if form == "hijri" else greg
                for k, name in enumerate(names):
                    key = _month_key(name)
                    if key and not re.fullmatch(r"\d+\D?", key):
                        table.setdefault(key, k + 1)
    return greg, hijri


def _two_digit_year(y):
    return 2000 + y if y <= 30 else 1900 + y


def _date(year, month=None, day=None, calendar="gregorian"):
    return {"ok": True, "kind": "date", "year": year, "month": month,
            "day": day, "calendar": calendar}


def _check_date(result, label):
    if not result.get("ok"):
        return result
    y, m, d = result["year"], result.get("month"), result.get("day")
    limit = this_year() + (1 if label == "DOC_DATE" else 0)
    if y is None or y < 1800 or y > limit:
        return {"ok": False, "kind": "date", "reason": "implausible_year",
                "candidates": [y]}
    if m is not None and not 1 <= m <= 12:
        return {"ok": False, "kind": "date", "reason": "bad_month"}
    if d is not None:
        try:
            datetime.date(y, m, d)
        except (ValueError, TypeError):
            return {"ok": False, "kind": "date", "reason": "bad_day"}
    return result


def _hijri(y, m, d):
    try:
        from hijridate import Hijri
    except ImportError:
        return {"ok": False, "kind": "date", "reason": "hijri_unconverted",
                "hijri": [y, m, d]}
    try:
        g = Hijri(y, m, d or 1).to_gregorian()
    except (ValueError, OverflowError) as exc:
        return {"ok": False, "kind": "date", "reason": "bad_hijri: %s" % exc}
    return _date(g.year, g.month, g.day if d else None, "hijri")


def normalize_date(text, lang=None, country=None, label="DOC_DATE"):
    return _check_date(_parse_date(text, lang, country), label)


def _parse_date(text, lang, country):
    t, _ = ascii_digits(text)
    t = t.strip()
    # spreadsheet datetime and ISO
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]\d{1,2}:\d{2}"
                     r"(?::\d{2}(?:\.\d+)?)?)?", t)
    if m:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # Japanese eras
    m = re.search(r"(明治|大正|昭和|平成|令和)\s*(元|\d{1,2})\s*年(?:度)?"
                  r"(?:\s*(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日)?", t)
    if m:
        n = 1 if m.group(2) == "元" else int(m.group(2))
        return _date(ERAS[m.group(1)] + n - 1,
                     int(m.group(3)) if m.group(3) else None,
                     int(m.group(4)) if m.group(4) else None,
                     "japanese_era")
    # Minguo (Taiwan)
    minguo = re.search(r"民[國国]", t) is not None
    m = re.search(r"(?:民[國国])?\s*(\d{1,3})\s*年(?:\s*(\d{1,2})\s*月)?"
                  r"(?:\s*(\d{1,2})\s*日)?", t)
    if m and (minguo or (country == "TW" and int(m.group(1)) < 200)):
        return _date(1911 + int(m.group(1)),
                     int(m.group(2)) if m.group(2) else None,
                     int(m.group(3)) if m.group(3) else None, "minguo")
    m = re.fullmatch(r"(?:民[國国])?\s*(\d{2,3})[/.-](\d{1,2})[/.-](\d{1,2})",
                     t)
    if m and (minguo or country == "TW") and int(m.group(1)) < 200:
        return _date(1911 + int(m.group(1)), int(m.group(2)),
                     int(m.group(3)), "minguo")
    # CJK year-first
    m = re.search(r"(\d{4})\s*[年년](?:\s*(\d{1,2})\s*[月월])?"
                  r"(?:\s*(\d{1,2})\s*[日일])?", t)
    if m:
        return _date(int(m.group(1)),
                     int(m.group(2)) if m.group(2) else None,
                     int(m.group(3)) if m.group(3) else None)
    greg, hijri = month_tables()
    is_hijri = "هـ" in t or "ه." in t or t.endswith("ه")
    # Hijri with month names
    for name in sorted(hijri, key=len, reverse=True):
        if name in t.lower():
            nums = [int(x) for x in re.findall(r"\d+", t)]
            year = next((x for x in nums if x > 1000), None)
            day = next((x for x in nums if x <= 30), None)
            if year:
                return _hijri(year, hijri[name], day)
    compact = re.sub(r"\s*([./-])\s*", r"\1", t)
    compact = re.sub(r"(هـ|ه\.?|г\.?|года|م)$", "", compact).strip()
    compact = compact.rstrip(".")
    # numeric, year first
    m = re.fullmatch(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", compact)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if is_hijri or (lang == "ar" and 1300 <= y < 1500):
            return _hijri(y, mo, d)
        return _date(y, mo, d)
    # numeric, day and month first
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})", compact)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        y = int(y) if len(y) == 4 else _two_digit_year(int(y))
        if is_hijri or (lang == "ar" and 1300 <= y < 1500):
            return _hijri(y, b, a)
        return _day_month(a, b, y, lang, country)
    # month + year (numeric): 03/2024, 2024-03
    m = re.fullmatch(r"(\d{1,2})[./-](\d{4})", compact)
    if m:
        return _date(int(m.group(2)), int(m.group(1)))
    # month names
    low = unicodedata.normalize("NFKC", t).lower()
    found = None
    for name in sorted(greg, key=len, reverse=True):
        rx = r"(?<![%s])%s\.?(?![%s])" % (WORD_CHARS, re.escape(name),
                                          WORD_CHARS)
        mm = re.search(rx, low)
        if mm:
            found = (greg[name], mm)
            break
    if found:
        month, mm = found
        rest = low[:mm.start()] + " " + low[mm.end():]
        years = re.findall(r"(?<!\d)(\d{4})(?!\d)", rest)
        days = re.findall(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th|er|re|º|°)?"
                          r"(?!\d)", rest)
        if years:
            year = int(years[0])
            day = int(days[0]) if days else None
            return _date(year, month, day)
        if len(days) >= 2:                  # "15 Mar 24"
            return _date(_two_digit_year(int(days[-1])), month,
                         int(days[0]))
        return {"ok": False, "kind": "date", "reason": "no_year"}
    # a year alone
    m = re.fullmatch(r"(\d{4})", compact)
    if m:
        return _date(int(m.group(1)))
    return {"ok": False, "kind": "date", "reason": "unreadable"}


def _day_month(a, b, y, lang, country):
    """a/b/y where one of a, b is the day and the other the month."""
    if country == "US":
        return _date(y, a, b)
    if country == "CA" or (country is None and lang in ("en", None)):
        if a > 12 and b <= 12:
            return _date(y, b, a)
        if b > 12 and a <= 12:
            return _date(y, a, b)
        if a == b:
            return _date(y, a, b)
        return {"ok": False, "kind": "date", "reason": "ambiguous_order",
                "candidates": ["%04d-%02d-%02d" % (y, a, b),
                               "%04d-%02d-%02d" % (y, b, a)]}
    return _date(y, b, a)


# =====================================================================
#  revenue years
# =====================================================================
def normalize_year(text, lang=None, country=None):
    t, _ = ascii_digits(text)
    m = re.search(r"(明治|大正|昭和|平成|令和)\s*(元|\d{1,2})\s*年", t)
    if m:
        n = 1 if m.group(2) == "元" else int(m.group(2))
        return _year(ERAS[m.group(1)] + n - 1, None)
    m = re.search(r"(?<!\d)(\d{4})\s*[-–—/]\s*(\d{4}|\d{2})(?!\d)", t)
    if m:
        start = int(m.group(1))
        end = m.group(2)
        end = int(end) if len(end) == 4 else (start // 100) * 100 + int(end)
        if end < start:
            end += 100
        if end == start + 1:
            return _year(end, "%d-%02d" % (start, end % 100))
    m = re.search(r"(?:民[國国])\s*(\d{2,3})\s*年", t)
    if m or (country == "TW" and re.fullmatch(r"\s*(\d{2,3})\s*年度?\s*",
                                              t)):
        n = int((m or re.search(r"(\d{2,3})", t)).group(1))
        return _year(1911 + n, None)
    years = re.findall(r"(?<!\d)(\d{4})(?!\d)", t)
    if years:
        return _year(int(years[-1]), None)
    return {"ok": False, "kind": "year", "reason": "no_year"}


def _year(y, fiscal):
    if not 1900 <= y <= this_year() + 1:
        return {"ok": False, "kind": "year", "reason": "implausible_year",
                "candidates": [y]}
    return {"ok": True, "kind": "year", "year": y, "fiscal": fiscal}


# =====================================================================
#  staff counts
# =====================================================================
APPROX = ["environ", "près de", "pres de", "about", "around",
          "approximately", "approx.", "approx", "circa", "ca.", "около",
          "примерно", "почти", "约", "約", "大约", "大約", "약", "حوالي",
          "حوالى", "نحو", "लगभग", "करीब", "unos", "unas", "cerca de",
          "alrededor de", "aproximadamente", "quasi", "circa", "some",
          "nearly", "almost", "presque"]
OVER = ["plus de", "more than", "over", "más de", "mas de", "oltre",
        "più di", "piu di", "более", "свыше", "больше", "أكثر من",
        "اكثر من", "upwards of", "au-delà de"]
OVER_AFTER = ["以上", "이상", "से अधिक", "से ज़्यादा", "से ज्यादा", "+", "余",
              "多", "여", "强"]
UNDER = ["moins de", "less than", "fewer than", "under", "menos de",
         "meno di", "менее", "меньше", "أقل من", "اقل من", "不足", "不到",
         "未満", "미만", "से कम", "up to", "jusqu'à", "hasta"]
UNDER_AFTER = ["未満", "미만", "से कम", "以下", "이하"]
RANGE_WORDS = r"(?:-|–|—|〜|～|~|to|à|a|y|et|and|до|і|и|إلى|الى|至|से|~)"


def normalize_count(text, lang=None, country=None):
    t, _ = ascii_digits(text)
    low = t.lower()
    nums = [int(re.sub(r"[ ,.'’]", "", x)) for x in
            re.findall(r"\d{1,3}(?:[ ,.'’]\d{3})+|\d+", t)]
    if not nums:
        return {"ok": False, "kind": "count", "reason": "no_number"}
    if len(nums) >= 2 and re.search(
            r"\d\s*(?:名|人|명)?\s*%s\s*\D{0,6}?\d" % RANGE_WORDS, low):
        a, b = nums[0], nums[1]
        if a < b:
            return {"ok": True, "kind": "count", "value": a,
                    "qualifier": "range", "max": b}
    qualifier = "exact"
    if any(w in low for w in UNDER) or any(w in low for w in UNDER_AFTER):
        qualifier = "under"
    elif any(re.search(r"(?<![%s])%s(?![%s])" % (WORD_CHARS, re.escape(w),
                                                 WORD_CHARS), low)
             for w in OVER) or any(w in low for w in OVER_AFTER):
        qualifier = "over"
    elif any(w in low for w in APPROX):
        qualifier = "approx"
    return {"ok": True, "kind": "count", "value": nums[0],
            "qualifier": qualifier, "max": None}


# =====================================================================
#  phones, e-mails, web addresses
# =====================================================================
def normalize_phone(text, lang=None, country=None):
    t, _ = ascii_digits(text)
    t = t.strip()
    try:
        import phonenumbers
    except ImportError:
        return {"ok": False, "kind": "phone", "reason": "no_phonenumbers"}
    region = country
    if t.startswith("00"):
        t = "+" + t[2:]
    if not t.startswith("+") and not region:
        return {"ok": False, "kind": "phone", "reason": "no_country"}
    try:
        num = phonenumbers.parse(t, None if t.startswith("+") else region)
    except phonenumbers.NumberParseException as exc:
        return {"ok": False, "kind": "phone", "reason": "unparsable: %s" %
                exc}
    if not phonenumbers.is_possible_number(num):
        return {"ok": False, "kind": "phone", "reason": "impossible_number"}
    return {"ok": True, "kind": "phone",
            "e164": phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.E164),
            "country": phonenumbers.region_code_for_number(num),
            "valid": phonenumbers.is_valid_number(num)}


def normalize_email(text, lang=None, country=None):
    t = unicodedata.normalize("NFKC", text or "").strip().lower()
    t = re.sub(r"^mailto:", "", t)
    t = t.strip("<>()[]\"' ")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", t):
        return {"ok": False, "kind": "email", "reason": "not_an_email"}
    return {"ok": True, "kind": "email", "value": t}


SOCIAL = {"facebook.com": "facebook", "fb.com": "facebook",
          "m.facebook.com": "facebook", "instagram.com": "instagram",
          "linkedin.com": "linkedin", "x.com": "x", "twitter.com": "x",
          "youtube.com": "youtube", "youtu.be": "youtube",
          "tiktok.com": "tiktok", "weibo.com": "weibo",
          "weixin.qq.com": "wechat", "mp.weixin.qq.com": "wechat",
          "line.me": "line", "page.line.me": "line", "kakao.com": "kakao",
          "pf.kakao.com": "kakao", "vk.com": "vk", "vk.ru": "vk"}


def normalize_url(text, lang=None, country=None):
    t = unicodedata.normalize("NFKC", text or "").strip().rstrip(".,;")
    if not re.search(r"[A-Za-z0-9-]+\.[A-Za-z]{2,}", t):
        return {"ok": False, "kind": "url", "reason": "not_a_url"}
    url = t if re.match(r"^[a-z]+://", t, re.I) else "https://" + t
    host = re.sub(r"^[a-z]+://", "", url, flags=re.I).split("/")[0]
    host = host.split("?")[0].split("#")[0].lower()
    host = host[4:] if host.startswith("www.") else host
    social = SOCIAL.get(host)
    if social is None:
        for domain, name in SOCIAL.items():
            if host.endswith("." + domain):
                social = name
    return {"ok": True, "kind": "url", "url": url, "host": host,
            "social": social}


# =====================================================================
#  registration numbers
# =====================================================================
def compact_id(text):
    return re.sub(r"[^0-9A-Za-z]", "", unicodedata.normalize(
        "NFKC", text or "")).upper()


# the pattern of each type, on the compact form
REG_PATTERNS = {
    "FR_SIREN": r"\d{9}", "FR_SIRET": r"\d{14}",
    "FR_TVA": r"FR[0-9A-Z]{2}\d{9}", "FR_RCS": r"RCS[A-Z]+\d{9}",
    "BE_BCE": r"[01]\d{9}", "BE_TVA": r"BE[01]\d{9}",
    "CH_UID": r"CHE\d{9}(MWST|TVA|IVA|HR|RC)*",
    "CH_TVA": r"CHE\d{9}(MWST|TVA|IVA)",
    "CA_BN": r"\d{9}(RT|RC|RP|RR)?(\d{4})?", "CA_NEQ": r"\d{10}",
    "CA_TPS": r"\d{9}RT\d{4}", "CA_TVQ": r"\d{10}TQ\d{4}",
    "MA_ICE": r"\d{15}", "MA_RC": r"\d{3,7}", "MA_IF": r"\d{7,8}",
    "MA_PATENTE": r"\d{8}", "MA_CNSS": r"\d{7}",
    "SN_NINEA": r"\d{7,9}[0-9A-Z]{0,3}", "SN_RCCM": r"SN[A-Z]{3}\d{4}[A-Z]\d+",
    "US_EIN": r"\d{9}", "US_STATE": r"[A-Z]?\d{6,12}",
    "GB_CRN": r"(\d{8}|[A-Z]{2}\d{6})", "GB_VAT": r"(GB)?\d{9}(\d{3})?",
    "IN_PAN": r"[A-Z]{5}\d{4}[A-Z]", "IN_GSTIN": r"\d{2}[A-Z]{5}\d{4}[A-Z]"
    r"[1-9A-Z]Z[0-9A-Z]", "IN_CIN": r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}",
    "IN_UDYAM": r"UDYAM[A-Z]{2}\d{9}",
    "AU_ABN": r"\d{11}", "AU_ACN": r"\d{9}",
    "NG_RC": r"(RC|BN|IT)?\d{5,8}", "NG_TIN": r"\d{8}\d{4}|\d{10,12}",
    "RU_INN10": r"\d{10}", "RU_INN12": r"\d{12}", "RU_OGRN": r"\d{13}",
    "RU_OGRNIP": r"\d{15}", "RU_KPP": r"\d{9}", "KZ_BIN": r"\d{12}",
    "KZ_IIN": r"\d{12}", "BY_UNP": r"\d{9}",
    "ES_NIF": r"[A-Z]\d{7}[0-9A-J]|\d{8}[A-Z]", "MX_RFC":
    r"[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}", "AR_CUIT": r"\d{11}",
    "CO_NIT": r"\d{9,10}", "CL_RUT": r"\d{7,8}[0-9K]",
    "IT_PIVA": r"(IT)?\d{11}", "IT_CF": r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}"
    r"[A-Z]|\d{11}", "IT_REA": r"[A-Z]{2}\d{5,7}",
    "CN_USCC": r"[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}",
    "TW_UBN": r"\d{8}", "HK_BR": r"\d{8}(\d{3})?", "HK_CR": r"\d{7,8}",
    "SG_UEN": r"\d{8,9}[A-Z]|[TSR]\d{2}[A-Z]{2}\d{4}[A-Z]",
    "JP_CORP": r"\d{13}", "JP_TNUM": r"T\d{13}",
    "KR_BRN": r"\d{10}", "KR_CRN": r"\d{13}",
    "SA_CR": r"\d{10}", "SA_VAT": r"3\d{13}3",
    "AE_TRN": r"100\d{12}", "AE_LICENSE": r"[A-Z]{0,3}\d{5,8}",
    "EG_CR": r"\d{4,7}", "EG_TAX": r"\d{9}",
}
COUNTRY_TYPES = {}
for _t in REG_PATTERNS:
    COUNTRY_TYPES.setdefault(_t.split("_")[0], []).append(_t)
CHECKED = {"FR_SIREN", "FR_SIRET", "IT_PIVA", "RU_INN10", "KR_BRN",
           "AU_ABN", "IN_GSTIN", "CN_USCC", "JP_CORP", "TW_UBN", "CL_RUT",
           "AR_CUIT"}


def normalize_reg_id(text, lang=None, country=None):
    compact = compact_id(text)
    if len(compact) < 4 or not re.search(r"\d", compact):
        return {"ok": False, "kind": "reg_id", "reason": "not_an_id",
                "compact": compact}
    import verify
    types = COUNTRY_TYPES.get(country, []) if country else []
    if not types:
        types = list(REG_PATTERNS)
    matching = [t for t in types if re.fullmatch(REG_PATTERNS[t], compact)]
    chosen, checksum = None, "not_checked"
    for t in matching:                   # prefer a type whose check passes
        if t in CHECKED:
            if verify.check_digits(t, compact):
                chosen, checksum = t, "valid"
                break
    if chosen is None:
        unchecked = [t for t in matching if t not in CHECKED]
        if unchecked:
            chosen = unchecked[0]
        elif matching:
            chosen, checksum = matching[0], "invalid"
    result = {"ok": checksum != "invalid", "kind": "reg_id",
              "compact": compact, "type": chosen or "unknown",
              "country": (chosen or "").split("_")[0] or country,
              "checksum": checksum}
    if checksum == "invalid":
        result["reason"] = "checksum"
    return result


# =====================================================================
#  legal forms
# =====================================================================
def _form_key(text):
    t = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"[\s.\-·,()（）«»\"'“”]", "", t)


@functools.lru_cache(maxsize=None)
def legal_form_index():
    """{key: [(country, code, class, lang)]} from gen/data/locales.json."""
    index = {}
    path = GEN_DATA / "locales.json"
    if not path.exists():
        return index
    data = json.loads(path.read_text(encoding="utf-8"))
    for code, loc in sorted(data["locales"].items()):
        for form in loc.get("legal_forms", []):
            for text in list(form.get("forms", [])) + \
                    list(form.get("long", []) or []):
                key = _form_key(text)
                if not key:
                    continue
                entry = (loc["country"], form["code"], form["class"],
                         loc["lang"])
                if entry not in index.setdefault(key, []):
                    index[key].append(entry)
    return index


def normalize_legal_form(text, lang=None, country=None):
    key = _form_key(text)
    hits = legal_form_index().get(key, [])
    if not hits:
        return {"ok": False, "kind": "legal_form", "reason": "unknown_form"}
    pick = [h for h in hits if h[0] == country] if country else []
    if not pick and lang:
        pick = [h for h in hits if h[3] == lang]
    pick = pick or hits
    c, code, cls, _ = pick[0]
    return {"ok": True, "kind": "legal_form", "code": code, "country": c,
            "class": cls, "candidates": sorted({h[1] for h in pick})}


def parse_legal_form(name, country=None):
    """Finds a legal form inside a company name ('Boulangerie Martin
    SARL', '株式会社サクラ'). -> the normalize() dict of the form, or
    None."""
    if not name:
        return None
    index = legal_form_index()
    text = unicodedata.normalize("NFKC", name)
    best = None
    for key, hits in index.items():
        if len(key) < 2:
            continue
        if country and not any(h[0] == country for h in hits):
            continue
        # compare on the same simplified form, at the start or the end
        simple = _form_key(text)
        if simple.endswith(key) or simple.startswith(key):
            if best is None or len(key) > len(best):
                best = key
    if best is None:
        return None
    hits = index[best]
    pick = [h for h in hits if h[0] == country] if country else hits
    c, code, cls, _ = (pick or hits)[0]
    return {"ok": True, "kind": "legal_form", "code": code, "country": c,
            "class": cls}


# =====================================================================
#  activity codes
# =====================================================================
SYSTEM_OF_COUNTRY = {"FR": "NAF", "IT": "ATECO", "US": "NAICS",
                     "CA": "NAICS", "GB": "SIC", "RU": "OKVED",
                     "ES": "CNAE", "MX": "SCIAN", "AU": "ANZSIC",
                     "IN": "NIC", "SG": "SSIC", "CO": "CIIU", "AR": "CIIU",
                     "CL": "CIIU", "JP": "JSIC", "KR": "KSIC"}


def normalize_activity_code(text, lang=None, country=None):
    code = compact_id(text)
    if not code or not re.search(r"\d", code):
        return {"ok": False, "kind": "activity_code", "reason": "no_code"}
    system = SYSTEM_OF_COUNTRY.get(country, "unknown")
    if country == "CA" and lang == "fr":
        system = "SCIAN"
    return {"ok": True, "kind": "activity_code", "system": system,
            "code": code}


# =====================================================================
def normalize(label, text, lang=None, country=None):
    """The value of a span. Always returns a dict; never raises."""
    kind = KIND_OF_LABEL.get(label, "text")
    try:
        if kind == "amount":
            return normalize_amount(text, lang, country)
        if kind == "date":
            return normalize_date(text, lang, country, label)
        if kind == "year":
            return normalize_year(text, lang, country)
        if kind == "count":
            return normalize_count(text, lang, country)
        if kind == "phone":
            return normalize_phone(text, lang, country)
        if kind == "email":
            return normalize_email(text, lang, country)
        if kind == "url":
            return normalize_url(text, lang, country)
        if kind == "reg_id":
            return normalize_reg_id(text, lang, country)
        if kind == "legal_form":
            return normalize_legal_form(text, lang, country)
        if kind == "activity_code":
            return normalize_activity_code(text, lang, country)
        return {"ok": True, "kind": "text", "text": single_spaces(text)}
    except Exception as exc:                 # never raise (14.2)
        return {"ok": False, "kind": kind, "reason": "error: %s" % exc}
