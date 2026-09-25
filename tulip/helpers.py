"""
helpers.py - turn cell text into typed values, in the ten languages.

Tulip (the model) only chooses WHICH helper to apply to WHICH column; the
reading itself is done here, in plain code. Every helper has the same
contract (section 9 of the build instructions):

    helper(value, locale) -> (ok, result)

  * it NEVER raises: anything it cannot read gives (False, None);
  * value is a raw cell: str, int, float, bool, datetime, date, time,
    timedelta - or text made by part() / join();
  * locale looks like 'fr-FR', or is None;
  * the result type is fixed by tulipscript._type_ok().

All text is first put in NFKC form (full-width digits become ASCII,
non-breaking spaces become spaces) and cleaned of the invisible
right-to-left marks that Arabic sheets are full of.

The words the helpers know (weekdays, months, yes/no, closed, tax words,
totals...) come from the Appendix H seeds below PLUS every
gen/data/<language>/values.json, so the generator and the helpers always
share one vocabulary.

HELPERS maps each helper's name to its function; TOTALS holds every
totals and subtotal word of the ten languages (the runtime needs them to
recognise totals rows).
"""
import datetime
import functools
import json
import math
import pathlib
import re
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
VALUES_DIR = HERE / "gen" / "data"
FOLDERS = ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi", "ja",
           "ko"]
LANG_OF_FOLDER = {"zh-Hant": "zh"}

FAIL = (False, None)

# ---------------------------------------------------------------------
#  1. cleaning text
# ---------------------------------------------------------------------
# right-to-left and embedding marks: U+200E, U+200F, U+061C,
# U+202A-U+202E, U+2066-U+2069
BIDI = dict.fromkeys(
    [0x200E, 0x200F, 0x061C] + list(range(0x202A, 0x202F)) +
    list(range(0x2066, 0x206A)))

# digits of every script we meet -> ASCII (NFKC already turns full-width
# digits into ASCII)
DIGITS = {}
for _base in (0x0660, 0x06F0, 0x0966):      # Arabic-Indic, Persian, Deva
    for _k in range(10):
        DIGITS[chr(_base + _k)] = str(_k)
DIGITS["٬"] = ","                            # Arabic thousands separator
DIGITS["٫"] = "."                            # Arabic decimal separator


def clean(value):
    """Cell text -> NFKC text without bidi marks, trimmed."""
    text = unicodedata.normalize("NFKC", str(value))
    return text.translate(BIDI).strip()


def ascii_digits(text):
    """Every digit script -> ASCII, and ٬ ٫ -> , ."""
    return "".join(DIGITS.get(ch, ch) for ch in text)


def single_spaces(text):
    return " ".join(text.split())


def key(text):
    """How words are compared: NFKC, no bidi marks, single spaces,
    case-folded, Persian ی ک folded to Arabic ي ك."""
    t = single_spaces(clean(text)).casefold()
    return t.replace("ی", "ي").replace("ک", "ك")


def parse_locale(locale):
    """'fr-FR' -> ('fr', 'FR'); 'ar' -> ('ar', None); None -> (None,
    None)."""
    if not locale or not isinstance(locale, str):
        return None, None
    parts = locale.replace("_", "-").split("-")
    lang = parts[0].lower() or None
    country = parts[-1].upper() if len(parts) > 1 and \
        len(parts[-1]) == 2 else None
    return lang, country


def _guard(func):
    """Decorator: a helper never raises and always returns (ok, result)
    with result None when ok is False."""
    @functools.wraps(func)
    def safe(value, locale=None):
        try:
            if value is None:
                return FAIL
            out = func(value, locale)
        except Exception:
            return FAIL
        if not out or out[0] is not True or out[1] is None:
            return FAIL
        return out
    return safe


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------------
#  2. the words (Appendix H seeds + every values.json)
# ---------------------------------------------------------------------
SEED_WEEKDAYS = {
    "ar": [["الاثنين", "الإثنين"], ["الثلاثاء"], ["الأربعاء"], ["الخميس"],
           ["الجمعة"], ["السبت"], ["الأحد"]],
    "zh": [["星期一", "礼拜一", "禮拜一", "周一", "週一"],
           ["星期二", "礼拜二", "禮拜二", "周二", "週二"],
           ["星期三", "礼拜三", "禮拜三", "周三", "週三"],
           ["星期四", "礼拜四", "禮拜四", "周四", "週四"],
           ["星期五", "礼拜五", "禮拜五", "周五", "週五"],
           ["星期六", "礼拜六", "禮拜六", "周六", "週六"],
           ["星期日", "星期天", "礼拜日", "礼拜天", "禮拜日", "禮拜天",
            "周日", "周天", "週日", "週天"]],
    "en": [["Monday", "Mon"], ["Tuesday", "Tue", "Tues"],
           ["Wednesday", "Wed"], ["Thursday", "Thu", "Thur", "Thurs"],
           ["Friday", "Fri"], ["Saturday", "Sat"], ["Sunday", "Sun"]],
    "fr": [["lundi", "lun."], ["mardi", "mar."], ["mercredi", "mer."],
           ["jeudi", "jeu."], ["vendredi", "ven."], ["samedi", "sam."],
           ["dimanche", "dim."]],
    "ru": [["понедельник", "пн"], ["вторник", "вт"], ["среда", "ср"],
           ["четверг", "чт"], ["пятница", "пт"], ["суббота", "сб"],
           ["воскресенье", "вс"]],
    "es": [["lunes", "lun"], ["martes", "mar"], ["miércoles", "mié"],
           ["jueves", "jue"], ["viernes", "vie"], ["sábado", "sáb"],
           ["domingo", "dom"]],
    "it": [["lunedì", "lun"], ["martedì", "mar"], ["mercoledì", "mer"],
           ["giovedì", "gio"], ["venerdì", "ven"], ["sabato", "sab"],
           ["domenica", "dom"]],
    "hi": [["सोमवार"], ["मंगलवार"], ["बुधवार"], ["गुरुवार"], ["शुक्रवार"],
           ["शनिवार"], ["रविवार"]],
    "ja": [["月曜日", "月曜"], ["火曜日", "火曜"], ["水曜日", "水曜"],
           ["木曜日", "木曜"], ["金曜日", "金曜"], ["土曜日", "土曜"],
           ["日曜日", "日曜"]],
    "ko": [["월요일"], ["화요일"], ["수요일"], ["목요일"], ["금요일"],
           ["토요일"], ["일요일"]],
}
# one character per day, read only for the languages named
HANJA_DAYS = "月火水木金土日"          # ja and ko only, never zh
HANGUL_DAYS = "월화수목금토일"         # ko only
SPANISH_LETTERS = "LMXJVSD"            # es only (X = miércoles)

SEED_CLOSED = {
    "ar": ["مغلق", "عطلة"], "zh": ["休息", "不营业", "公休", "不營業"],
    "en": ["Closed"], "fr": ["Fermé"], "ru": ["Выходной", "Закрыто"],
    "es": ["Cerrado"], "it": ["Chiuso"], "hi": ["बंद", "अवकाश"],
    "ja": ["定休日", "休み", "休業"], "ko": ["휴무", "정기휴무", "휴일"]}
SEED_YES = {
    "ar": ["نعم"], "zh": ["是", "有"], "en": ["Yes"], "fr": ["Oui"],
    "ru": ["Да"], "es": ["Sí", "Si"], "it": ["Sì", "Si"],
    "hi": ["हाँ", "हां"], "ja": ["はい", "有"], "ko": ["예", "네", "유"]}
SEED_NO = {
    "ar": ["لا"], "zh": ["否", "无", "無"], "en": ["No"], "fr": ["Non"],
    "ru": ["Нет"], "es": ["No"], "it": ["No"], "hi": ["नहीं"],
    "ja": ["いいえ", "無"], "ko": ["아니요", "아니오", "무"]}
SEED_TOTALS = {
    "ar": ["المجموع", "الإجمالي", "المجموع الفرعي"],
    "zh": ["合计", "小计", "总计", "合計", "小計", "總計"],
    "en": ["Total", "Subtotal", "Grand total"],
    "fr": ["Total", "Sous-total", "Total général"],
    "ru": ["Итого", "Всего"], "es": ["Total", "Subtotal", "Total general"],
    "it": ["Totale", "Subtotale", "Totale generale"],
    "hi": ["कुल", "कुल योग", "उप-योग", "योगफल"],
    "ja": ["合計", "小計", "総計"], "ko": ["합계", "소계", "총계"]}
SEED_TAX_INCLUDED = {
    "ar": ["شامل الضريبة", "شامل ضريبة القيمة المضافة"],
    "zh": ["含税", "含稅", "价税合计", "價稅合計"],
    "en": ["incl. VAT", "VAT included", "including GST", "inc. GST", "MRP",
           "incl. GST", "including VAT", "inc. VAT", "VAT incl."],
    "fr": ["TTC", "TVAC", "TVA comprise", "toutes taxes comprises"],
    "ru": ["с НДС", "включая НДС", "в т.ч. НДС", "в том числе НДС"],
    "es": ["IVA incluido", "IVA incl.", "PVP", "con IVA"],
    "it": ["IVA inclusa", "IVA compresa", "IVA incl."],
    "hi": ["कर सहित", "GST सहित"], "ja": ["税込", "内税"],
    "ko": ["부가세 포함", "VAT 포함"]}
SEED_TAX_EXCLUDED = {
    "ar": ["غير شامل الضريبة", "بدون ضريبة", "غير شامل"],
    "zh": ["不含税", "未税", "不含稅", "未稅"],
    "en": ["excl. VAT", "excluding VAT", "VAT not included", "+ VAT",
           "plus GST", "excl. GST", "ex. GST", "ex GST", "plus VAT",
           "exc. VAT", "ex. VAT"],
    "fr": ["HT", "HTVA", "hors taxes", "TVA non comprise", "hors TVA"],
    "ru": ["без НДС", "не включая НДС"],
    "es": ["sin IVA", "IVA no incluido", "+ IVA", "más IVA"],
    "it": ["IVA esclusa", "IVA non inclusa", "+ IVA", "oltre IVA"],
    "hi": ["कर रहित", "GST अतिरिक्त"], "ja": ["税抜", "税別", "外税"],
    "ko": ["부가세 별도", "부가세 미포함", "VAT 불포함", "VAT 별도"]}
SEED_FROM = {
    "ar": ["ابتداء من", "ابتداءً من", "يبدأ من", "من"],
    "zh": ["起", "起价"], "en": ["from", "starting at"],
    "fr": ["à partir de", "dès", "à p. de"], "ru": ["от"],
    "es": ["desde", "a partir de"], "it": ["da", "a partire da"],
    "hi": ["से शुरू"], "ja": ["〜", "から"], "ko": ["부터", "~"]}
SEED_MINUTES = {
    "ar": ["دقيقة", "دقائق", "د"], "zh": ["分钟", "分鐘", "分"],
    "en": ["min", "mins", "minutes", "minute"],
    "fr": ["min", "mn", "minutes", "minute"], "ru": ["мин", "мин.", "минут"],
    "es": ["min", "minutos", "minuto"], "it": ["min", "minuti", "minuto"],
    "hi": ["मिनट", "मि."], "ja": ["分", "分間"], "ko": ["분"]}
SEED_HOURS = {
    "ar": ["ساعة", "ساعات", "س"], "zh": ["小时", "小時", "个小时", "個小時"],
    "en": ["h", "hr", "hrs", "hour", "hours"],
    "fr": ["h", "heure", "heures"], "ru": ["ч", "ч.", "час", "часа", "часов"],
    "es": ["h", "hora", "horas"], "it": ["h", "ora", "ore"],
    "hi": ["घंटा", "घंटे", "घं."], "ja": ["時間"], "ko": ["시간"]}
AM_WORDS = ["am", "a.m.", "a.m", "ص", "صباحا", "صباحًا", "上午", "午前", "오전",
            "पूर्वाह्न"]
PM_WORDS = ["pm", "p.m.", "p.m", "م", "مساء", "مساءً", "下午", "午後", "오후",
            "अपराह्न"]

ENGLISH_MONTHS = ["january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november",
                  "december"]
SEED_MONTHS = {
    # Arabic: Egyptian / Gulf names and the Levantine ones
    "ar": [["يناير", "كانون الثاني"], ["فبراير", "شباط"], ["مارس", "آذار"],
           ["أبريل", "ابريل", "إبريل", "نيسان"], ["مايو", "أيار"],
           ["يونيو", "يونيه", "حزيران"], ["يوليو", "يوليه", "تموز"],
           ["أغسطس", "اغسطس", "آب"], ["سبتمبر", "أيلول"],
           ["أكتوبر", "اكتوبر", "تشرين الأول"], ["نوفمبر", "تشرين الثاني"],
           ["ديسمبر", "كانون الأول"]],
    "fr": [["janvier", "janv."], ["février", "févr.", "fevrier"],
           ["mars"], ["avril", "avr."], ["mai"], ["juin"],
           ["juillet", "juil."], ["août", "aout"],
           ["septembre", "sept."], ["octobre", "oct."],
           ["novembre", "nov."], ["décembre", "déc.", "decembre"]],
    # Russian: the genitive form used in dates, and the nominative
    "ru": [["января", "январь", "янв."], ["февраля", "февраль", "февр."],
           ["марта", "март"], ["апреля", "апрель", "апр."],
           ["мая", "май"], ["июня", "июнь"], ["июля", "июль"],
           ["августа", "август", "авг."], ["сентября", "сентябрь", "сент."],
           ["октября", "октябрь", "окт."], ["ноября", "ноябрь", "нояб."],
           ["декабря", "декабрь", "дек."]],
    "es": [["enero"], ["febrero"], ["marzo"], ["abril"], ["mayo"],
           ["junio"], ["julio"], ["agosto"], ["septiembre", "setiembre"],
           ["octubre"], ["noviembre"], ["diciembre"]],
    "it": [["gennaio"], ["febbraio"], ["marzo"], ["aprile"], ["maggio"],
           ["giugno"], ["luglio"], ["agosto"], ["settembre"], ["ottobre"],
           ["novembre"], ["dicembre"]],
    "hi": [["जनवरी"], ["फ़रवरी", "फरवरी"], ["मार्च"], ["अप्रैल"], ["मई"],
           ["जून"], ["जुलाई"], ["अगस्त"], ["सितंबर", "सितम्बर"],
           ["अक्टूबर"], ["नवंबर", "नवम्बर"], ["दिसंबर", "दिसम्बर"]],
}
HIJRI_MONTHS = [["محرم"], ["صفر"], ["ربيع الأول"],
                ["ربيع الآخر", "ربيع الثاني"],
                ["جمادى الأولى", "جمادى الأول"],
                ["جمادى الآخرة", "جمادى الثانية"], ["رجب"], ["شعبان"],
                ["رمضان"], ["شوال"], ["ذو القعدة"], ["ذو الحجة"]]
ERAS = {"明治": 1868, "大正": 1912, "昭和": 1926, "平成": 1989, "令和": 2019}


@functools.lru_cache(maxsize=None)
def _values():
    """{language: values.json content}, the two Chinese folders merged."""
    out = {}
    for folder in FOLDERS:
        path = VALUES_DIR / folder / "values.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.setdefault(LANG_OF_FOLDER.get(folder, folder), []).append(data)
    return out


def _words(name, seeds):
    """{language: [words]} = seeds + the list `name` of every
    values.json of that language."""
    table = dict((lang, list(words)) for lang, words in seeds.items())
    for lang, datas in _values().items():
        for data in datas:
            table.setdefault(lang, []).extend(data.get(name) or [])
    return table


def _all_langs(table):
    return [w for words in table.values() for w in words]


@functools.lru_cache(maxsize=None)
def weekday_table():
    """{language: {key(word): day}} with day 0 = Monday."""
    table = {}
    for lang, days in SEED_WEEKDAYS.items():
        for day, names in enumerate(days):
            for n in names:
                table.setdefault(lang, {})[key(n).rstrip(".")] = day
    for lang, datas in _values().items():
        for data in datas:
            wd = data.get("weekdays") or {}
            for form in ("full", "short"):
                for day, n in enumerate(wd.get(form) or []):
                    if isinstance(n, str) and n:
                        table.setdefault(lang, {})[key(n).rstrip(".")] = day
            for day, names in enumerate(wd.get("other") or []):
                for n in names or []:
                    table.setdefault(lang, {})[key(n).rstrip(".")] = day
    # one-letter / one-character days are handled apart
    for lang in table:
        for k in [k for k in table[lang] if len(k) == 1]:
            del table[lang][k]
    return table


@functools.lru_cache(maxsize=None)
def month_table():
    """{key(month name): month number} for Gregorian months in every
    language, and a separate table for Hijri months."""
    greg = {}
    for k, name in enumerate(ENGLISH_MONTHS):
        greg[name] = k + 1
        greg[name[:3]] = k + 1
    greg["sept"] = 9
    for lang, months in SEED_MONTHS.items():
        for k, names in enumerate(months):
            for n in names:
                greg.setdefault(key(n).rstrip("."), k + 1)
    for lang, datas in _values().items():
        for data in datas:
            m = data.get("months") or {}
            for form in ("full", "short"):
                for k, n in enumerate(m.get(form) or []):
                    if isinstance(n, str) and n and \
                            not re.fullmatch(r"\d+\D?", key(n)):
                        greg.setdefault(key(n).rstrip("."), k + 1)
    # the same name typed without accents (décembre -> decembre)
    for name, k in list(greg.items()):
        bare = "".join(ch for ch in unicodedata.normalize("NFD", name)
                       if not unicodedata.combining(ch))
        if re.fullmatch(r"[a-z.]+", bare):
            greg.setdefault(bare, k)
    hijri = {}
    for k, names in enumerate(HIJRI_MONTHS):
        for n in names:
            hijri[key(n)] = k + 1
    return greg, hijri


@functools.lru_cache(maxsize=None)
def yes_no_table():
    yes = set(key(w) for w in _all_langs(_words("yes", SEED_YES)))
    no = set(key(w) for w in _all_langs(_words("no", SEED_NO)))
    both = yes & no                  # never guess on a word in both lists
    return yes - both, no - both


@functools.lru_cache(maxsize=None)
def closed_words():
    return sorted(set(key(w) for w in _all_langs(
        _words("closed", SEED_CLOSED))), key=len, reverse=True)


@functools.lru_cache(maxsize=None)
def tax_words():
    inc = set(key(w) for w in _all_langs(
        _words("tax_included", SEED_TAX_INCLUDED)))
    exc = set(key(w) for w in _all_langs(
        _words("tax_excluded", SEED_TAX_EXCLUDED)))
    return (sorted(exc, key=len, reverse=True),
            sorted(inc - exc, key=len, reverse=True))


@functools.lru_cache(maxsize=None)
def from_words():
    return sorted(set(key(w) for w in _all_langs(
        _words("from_words", SEED_FROM))), key=len, reverse=True)


@functools.lru_cache(maxsize=None)
def duration_words():
    minutes = set(key(w).rstrip(".") for w in _all_langs(
        _words("minute_words", SEED_MINUTES)))
    hours = set(key(w).rstrip(".") for w in _all_langs(
        _words("hour_words", SEED_HOURS)))
    minutes.update(["'", "′"])
    return (sorted(minutes - hours, key=len, reverse=True),
            sorted(hours - minutes, key=len, reverse=True))


def _totals():
    words = []
    for lang, datas in _values().items():
        for data in datas:
            words += (data.get("totals") or []) + (data.get("subtotals")
                                                   or [])
    words += _all_langs(SEED_TOTALS)
    out, seen = [], set()
    for w in words:
        w = single_spaces(clean(w))
        if not w or key(w) in seen or key(w) == "योग":
            continue
        seen.add(key(w))
        out.append(w)
    return tuple(sorted(out, key=lambda w: (key(w), w)))


# ---------------------------------------------------------------------
#  3. numbers and currencies
# ---------------------------------------------------------------------
def decimal_of(lang, country):
    """The decimal separator of a locale (rule 7 of section 9), or None
    when there is no locale."""
    if lang is None:
        return None
    if lang == "ar":
        return "," if country == "MA" else "."
    if lang in ("fr", "it"):
        return "." if country == "CH" else ","
    if lang == "es":
        return "." if country == "MX" else ","
    if lang == "ru":
        return ","
    return "."


DOLLAR_OF = {"US": "USD", "CA": "CAD", "AU": "AUD", "MX": "MXN",
             "AR": "ARS", "CO": "COP", "CL": "CLP", "SG": "SGD",
             "HK": "HKD", "TW": "TWD", "NZ": "NZD", "NG": "USD"}


def _dollar(lang, country):
    return DOLLAR_OF.get(country, "USD")


def _yen(lang, country):
    if lang == "zh" or country in ("CN", "SG"):
        return "CNY"
    return "JPY"


def _yuan(lang, country):
    return {"TW": "TWD", "HK": "HKD"}.get(country, "CNY")


def _dirham(lang, country):
    return "MAD" if country == "MA" else "AED"


def _ruble(lang, country):
    return "BYN" if country == "BY" else "RUB"


def _riyal(lang, country):
    return "SAR"


# (token, ISO code or a function of the locale). Longer tokens are tried
# first; tokens with letters must stand alone (not inside a word).
CURRENCY_TOKENS = [
    ("US$", "USD"), ("U$S", "USD"), ("NT$", "TWD"), ("HK$", "HKD"),
    ("S$", "SGD"), ("A$", "AUD"), ("AU$", "AUD"), ("C$", "CAD"),
    ("CA$", "CAD"), ("MX$", "MXN"), ("R$", "BRL"), ("$", _dollar),
    ("€", "EUR"), ("euros", "EUR"), ("euro", "EUR"), ("евро", "EUR"),
    ("£", "GBP"), ("₹", "INR"), ("Rs.", "INR"), ("Rs", "INR"),
    ("₨", "INR"), ("रु.", "INR"), ("रुपये", "INR"), ("रुपए", "INR"),
    ("रुपया", "INR"), ("रु", "INR"),
    ("₽", "RUB"), ("руб.", _ruble), ("руб", _ruble), ("рублей", _ruble),
    ("р.", _ruble), ("₸", "KZT"), ("тенге", "KZT"), ("тг", "KZT"),
    ("円", "JPY"), ("¥", _yen), ("人民币", "CNY"), ("人民幣", "CNY"),
    ("RMB", "CNY"), ("新台幣", "TWD"), ("新臺幣", "TWD"), ("港幣", "HKD"),
    ("港元", "HKD"), ("元", _yuan), ("₩", "KRW"), ("원", "KRW"),
    ("ر.س.", "SAR"), ("ر.س", "SAR"), ("﷼", "SAR"), ("⃁", "SAR"),
    ("ريال", _riyal), ("د.إ.", "AED"), ("د.إ", "AED"), ("درهم", _dirham),
    ("د.م.", "MAD"), ("د.م", "MAD"), ("DHS", "MAD"), ("Dhs", "MAD"),
    ("DH", "MAD"), ("ج.م.", "EGP"), ("ج.م", "EGP"), ("جنيه", "EGP"),
    ("Fr.", "CHF"), ("FCFA", "XOF"), ("F CFA", "XOF"), ("₦", "NGN"),
]
ISO_CODES = {"USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD", "MXN", "ARS",
             "COP", "CLP", "SGD", "HKD", "TWD", "CNY", "JPY", "KRW", "INR",
             "RUB", "BYN", "KZT", "SAR", "AED", "EGP", "MAD", "XOF", "NGN",
             "BRL", "NTD"}
CURRENCY_TOKENS += [(c, "TWD" if c == "NTD" else c) for c in ISO_CODES]
CURRENCY_TOKENS.sort(key=lambda t: -len(t[0]))
LETTER = r"[^\W\d_]"


CJK_CHAR = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af"
                      r"\uf900-\ufaff]")


@functools.lru_cache(maxsize=None)
def _token_regex(token):
    """A currency token made of letters must stand alone ("DH" is not
    inside "DHL"); Chinese, Japanese and Korean marks (円 元 원) are
    glued to the number and need no boundary."""
    body = re.escape(token)
    if re.search(LETTER, token) and not CJK_CHAR.search(token):
        body = r"(?<!%s)%s" % (LETTER, body)
        if not token.endswith("."):
            body += r"(?!%s)" % LETTER
    return re.compile(body)


def find_currencies(text, lang, country):
    """-> (text with every currency token removed, [ISO codes found])."""
    text = text.replace("ی", "ي").replace("ک", "ك")
    codes = []
    for token, target in CURRENCY_TOKENS:
        rx = _token_regex(token)
        if not rx.search(text):
            continue
        text = rx.sub(" ", text)
        codes.append(target(lang, country) if callable(target) else target)
    return text, codes


# magnitude words: (pattern, multiplier, languages or None)
MAGNITUDES = [
    (r"mil millones", 1e9, None), (r"MM", 1e6, ("es",)),
    (r"millions?", 1e6, None), (r"millones", 1e6, None),
    (r"millón", 1e6, None), (r"milioni", 1e6, None),
    (r"milione", 1e6, None), (r"milliards?", 1e9, None),
    (r"miliardi", 1e9, None), (r"miliardo", 1e9, None),
    (r"млн\.?", 1e6, None), (r"млрд\.?", 1e9, None),
    (r"тыс\.?", 1e3, None), (r"مليون", 1e6, None), (r"ألف", 1e3, None),
    (r"crores?", 1e7, None), (r"करोड़", 1e7, None), (r"करोड", 1e7, None),
    (r"lakhs?", 1e5, None), (r"लाख", 1e5, None),
    (r"mil", 1e3, ("es",)), (r"k", 1e3, None), (r"K", 1e3, None),
    (r"M", 1e6, "not_es"),
]
CJK_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000,
             "万": 1e4, "萬": 1e4, "亿": 1e8, "億": 1e8, "兆": 1e12,
             "십": 10, "백": 100, "천": 1000, "만": 1e4, "억": 1e8, "조": 1e12}
BIG_UNITS = {"万", "萬", "亿", "億", "兆", "만", "억", "조"}
CJK_UNIT_CHARS = "".join(CJK_UNITS)


def read_cjk(text):
    """'1,000万' -> 1e7; '12억 4천만' -> 1.24e9 (summed by unit). A comma
    just before a unit is always a thousands separator."""
    s = re.sub(r"\s", "", text)
    if re.sub(r"[\d,.%s]" % CJK_UNIT_CHARS, "", s):
        return None                            # something else is left
    tokens = re.findall(r"\d[\d,]*(?:\.\d+)?|[%s]" % CJK_UNIT_CHARS, s)
    if not tokens or not any(t[0].isdigit() for t in tokens):
        return None
    total, section, current = 0.0, 0.0, None
    for tok in tokens:
        if tok[0].isdigit():
            if current is not None:
                return None                    # two numbers in a row
            current = float(tok.replace(",", ""))
        elif tok in BIG_UNITS:
            section += current if current is not None else 0
            total += (section or 1) * CJK_UNITS[tok]
            section, current = 0.0, None
        else:
            section += (current if current is not None else 1) * \
                CJK_UNITS[tok]
            current = None
    return total + section + (current or 0)


def read_number(core, dec):
    """'1 240,50' -> 1240.5 with the separator rules of section 9.
    dec: the locale's decimal separator, or None. Returns None when the
    number cannot be read without guessing."""
    s = re.sub(r"(?<=\d)[ '’](?=\d)", "", core)   # 1 240 / 1'240 / 1’240
    if not re.fullmatch(r"\d[\d.,]*", s) or s[-1] in ".,":
        return None
    n_dot, n_comma = s.count("."), s.count(",")
    if n_dot and n_comma:                    # both: the last one decides
        decimal = "." if s.rfind(".") > s.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        if s.count(decimal) > 1:
            return None
        body = s.replace(thousands, "")
        return float(body.replace(",", ".")) if decimal == "," \
            else float(body)
    if not n_dot and not n_comma:
        return float(s)
    sep = "." if n_dot else ","
    if n_dot + n_comma > 1:                  # 1.240.000 / 12,40,000
        return float(s.replace(sep, ""))
    after = len(s) - s.rfind(sep) - 1
    if after in (1, 2) or after > 3:         # a decimal separator
        return float(s.replace(",", "."))
    if dec is None:                          # exactly 3 digits: the
        return None                          # locale must decide
    if sep == dec:
        return float(s.replace(",", "."))
    return float(s.replace(sep, ""))


def _read_amount(text, locale):
    """Text -> float or None. Currency tokens and "from" words are
    removed first."""
    lang, country = parse_locale(locale)
    t = ascii_digits(clean(text))
    t, _ = find_currencies(t, lang, country)
    low = t.casefold()
    for w in from_words():
        if low.startswith(w + " ") or low.startswith(w) and len(w) > 1 \
                and not w[-1].isalpha():
            t = t[len(w):]
            low = t.casefold()
            break
    t = t.strip()
    # accounting negatives (120,00) and minus signs
    negative = False
    if re.fullmatch(r"\(.*\)", t):
        negative, t = True, t[1:-1].strip()
    if t[:1] in "-−–":
        negative, t = True, t[1:].strip()
    if t[-1:] in "-−" and re.search(r"\d", t):
        negative, t = True, t[:-1].strip()
    t = t.strip()
    if re.search(r"\d\s*[%s]" % CJK_UNIT_CHARS, t):
        value = read_cjk(t)
        if value is None:
            return None
        return -value if negative else value
    mult = 1.0
    for pattern, factor, langs in MAGNITUDES:
        rx = re.compile(r"(?<![^\W\d_])%s(?![^\W\d_])" % pattern)
        m = rx.search(t)
        if not m:
            continue
        if langs == "not_es":
            if lang == "es":
                return None                  # a lone M is ambiguous in es
        elif langs and lang not in langs:
            continue
        t = (t[:m.start()] + " " + t[m.end():]).strip()
        mult = factor
        break
    t = t.strip(" .")
    if not t or not re.fullmatch(r"\d[\d .,'’]*", t):
        return None
    value = read_number(t.strip(), decimal_of(lang, country))
    if value is None:
        return None
    value *= mult
    return -value if negative else value


@_guard
def amount(value, locale=None):
    if isinstance(value, bool):
        return FAIL
    if _is_number(value):
        if not math.isfinite(value):
            return FAIL
        return True, round(float(value), 6)
    if not isinstance(value, str):
        return FAIL
    got = _read_amount(value, locale)
    if got is None or not math.isfinite(got):
        return FAIL
    return True, round(float(got), 6) + 0.0


@_guard
def currency(value, locale=None):
    if not isinstance(value, str):
        return FAIL
    lang, country = parse_locale(locale)
    t = clean(value)
    # Excel number formats: [$€-40C] #,##0.00  /  #,##0 "₽"
    parts = re.findall(r"\[\$([^\]-]*)(?:-[0-9A-Fa-f]+)?\]", t)
    parts += re.findall(r'"([^"]*)"', t)
    texts = parts if parts else [t]
    codes = []
    for part in texts:
        _, found = find_currencies(part, lang, country)
        codes += found
    codes = sorted(set(codes))
    if len(codes) != 1:
        return FAIL                          # none, or several
    return True, codes[0]


@_guard
def integer(value, locale=None):
    if isinstance(value, bool):
        return FAIL
    if isinstance(value, int):
        return True, value
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return True, int(value)
        return FAIL
    if not isinstance(value, str):
        return FAIL
    lang, country = parse_locale(locale)
    t = ascii_digits(clean(value))
    # a unit after the number: 40 pcs, 12 kg, 3 шт.
    m = re.fullmatch(r"([-−]?\s*\d[\d .,'’]*?)\s*([^\W\d_][^\d]*)?", t)
    if not m:
        return FAIL
    number = m.group(1).replace("−", "-").replace(" ", "") \
        if m.group(1).count(" ") and not re.search(r"\d \d", m.group(1)) \
        else m.group(1).replace("−", "-")
    negative = number.strip().startswith("-")
    got = read_number(number.strip().lstrip("-").strip(),
                      decimal_of(lang, country))
    if got is None or not float(got).is_integer():
        return FAIL
    return True, -int(got) if negative else int(got)


@_guard
def percent(value, locale=None):
    if isinstance(value, bool):
        return FAIL
    if _is_number(value):
        if not math.isfinite(value):
            return FAIL
        v = float(value)
        return True, round(v if v <= 1 else v / 100.0, 6)
    if not isinstance(value, str):
        return FAIL
    lang, country = parse_locale(locale)
    t = ascii_digits(clean(value)).replace("٪", "%")
    has_sign = "%" in t
    t = t.replace("%", "").strip()
    if not re.fullmatch(r"-?\d[\d.,]*", t):
        return FAIL
    negative = t.startswith("-")
    got = read_number(t.lstrip("-"), decimal_of(lang, country))
    if got is None:
        # '5,5' or '5.5' with 1 digit after the separator is decimal
        return FAIL
    got = -got if negative else got
    if has_sign or got > 1:
        got = got / 100.0
    return True, round(got, 6)


# ---------------------------------------------------------------------
#  4. dates and times
# ---------------------------------------------------------------------
def _date_text(y, m, d):
    try:
        return datetime.date(y, m, d).isoformat()
    except (ValueError, TypeError):
        return None


def _two_digit_year(y):
    return 2000 + y if y <= 30 else 1900 + y


def _hijri(y, m, d):
    try:
        from hijridate import Hijri
    except ImportError:
        return None
    try:
        g = Hijri(y, m, d).to_gregorian()
    except (ValueError, OverflowError):
        return None
    return _date_text(g.year, g.month, g.day)


def _year_first(lang, country):
    return lang in ("ja", "ko") or (lang == "zh" and
                                    country in (None, "CN", "TW"))


def _read_date(text, locale):
    lang, country = parse_locale(locale)
    t = ascii_digits(clean(text))
    t = single_spaces(t)
    # ISO, with or without a time
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]\d{1,2}:\d{2}"
                     r"(?::\d{2}(?:\.\d+)?)?)?", t)
    if m:
        return _date_text(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # Japanese eras: 令和6年3月15日, 令和元年...
    m = re.fullmatch(r"(明治|大正|昭和|平成|令和)\s*(元|\d{1,2})\s*年\s*(\d{1,2})"
                     r"\s*月\s*(\d{1,2})\s*日", t)
    if m:
        n = 1 if m.group(2) == "元" else int(m.group(2))
        return _date_text(ERAS[m.group(1)] + n - 1, int(m.group(3)),
                          int(m.group(4)))
    # Minguo: 民國113年3月15日 / 民國113/03/15
    m = re.fullmatch(r"民[國国]\s*(\d{1,3})\s*(?:年\s*(\d{1,2})\s*月\s*"
                     r"(\d{1,2})\s*日|[/.-](\d{1,2})[/.-](\d{1,2}))", t)
    if m:
        y = 1911 + int(m.group(1))
        mo, d = (m.group(2), m.group(3)) if m.group(2) else \
            (m.group(4), m.group(5))
        return _date_text(y, int(mo), int(d))
    # CJK and Korean: 2024年3月15日 / 2024년 3월 15일
    m = re.fullmatch(r"(\d{4})\s*[年년]\s*(\d{1,2})\s*[月월]\s*(\d{1,2})\s*"
                     r"[日일]", t)
    if m:
        return _date_text(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    is_hijri = "هـ" in t or t.endswith("ه")
    body = re.sub(r"\s*(هـ|ه)\.?$", "", t)
    body = re.sub(r"\s*([./-])\s*", r"\1", body).rstrip(".")
    # numeric, year first: 2024/03/15, 2024.03.15.
    m = re.fullmatch(r"(\d{4})([./-])(\d{1,2})\2(\d{1,2})", body)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(3)), int(m.group(4))
        if is_hijri or (lang == "ar" and country in (None, "SA")
                        and 1300 <= y < 1500):
            return _hijri(y, mo, d)
        return _date_text(y, mo, d)
    # numeric, day or month first: 15/03/2024, 03/15/2024, 15.03.24
    m = re.fullmatch(r"(\d{1,2})([./-])(\d{1,2})\2(\d{4}|\d{2})", body)
    if m:
        a, b, y = int(m.group(1)), int(m.group(3)), m.group(4)
        y = int(y) if len(y) == 4 else _two_digit_year(int(y))
        if is_hijri or (lang == "ar" and country in (None, "SA")
                        and 1300 <= y < 1500):
            return _hijri(y, b, a)
        if country == "US":
            return _date_text(y, a, b)
        return _date_text(y, b, a)
    # Hijri month names: 5 رمضان 1445
    greg, hijri = month_table()
    low = key(t)
    for name in sorted(hijri, key=len, reverse=True):
        if name in low:
            nums = [int(x) for x in re.findall(r"\d+", low)]
            if len(nums) == 2:
                d, y = (nums if nums[0] <= 30 else nums[::-1])
                return _hijri(y, hijri[name], d)
            return None
    # month names: 15 mars 2024, March 15, 2024, 15 de marzo de 2024,
    # 15 марта 2024 г.
    low = re.sub(r"(?<=\d)(st|nd|rd|th|er|º|°)(?![^\W\d_])", "", low)
    low = re.sub(r"(?<![^\W\d_])(de|del|di|г\.?|года)(?![^\W\d_])", " ",
                 low)
    low = low.replace(",", " ")
    for name in sorted(greg, key=len, reverse=True):
        rx = r"(?<![^\W\d_])%s\.?(?![^\W\d_])" % re.escape(name)
        mm = re.search(rx, low)
        if not mm:
            continue
        rest = (low[:mm.start()] + " " + low[mm.end():]).split()
        if any(not re.fullmatch(r"\d+\.?", r) for r in rest):
            return None
        nums = [int(r.rstrip(".")) for r in rest]
        if len(nums) != 2:
            return None                       # a date without a day fails
        years = [n for n in nums if n > 31]
        if len(years) != 1:
            return None
        y = years[0]
        d = [n for n in nums if n != y or nums.count(n) > 1][0]
        return _date_text(y, greg[name], d)
    return None


@_guard
def date(value, locale=None):
    if isinstance(value, datetime.datetime):
        return True, value.date().isoformat()
    if isinstance(value, datetime.date):
        return True, value.isoformat()
    if not isinstance(value, str):
        return FAIL
    got = _read_date(value, locale)
    return (True, got) if got else FAIL


def _hm(h, m, marker=None):
    """Hour and minute (+ an AM/PM marker) -> 'HH:MM' or None."""
    if marker == "am":
        if not 1 <= h <= 12:
            return None
        h = 0 if h == 12 else h
    elif marker == "pm":
        if not 1 <= h <= 12:
            return None
        h = 12 if h == 12 else h + 12
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return "%02d:%02d" % (h, m)


AMPM_RX = re.compile(r"(?<![^\W\d_])(%s)(?![^\W\d_])" % "|".join(
    re.escape(w) for w in sorted(AM_WORDS + PM_WORDS, key=len, reverse=True)))


def _marker(text):
    """-> (text without its AM/PM word, 'am' / 'pm' / None)."""
    low = text.casefold()
    m = AMPM_RX.search(low)
    if not m:
        return text, None
    word = m.group(1)
    marker = "am" if word in AM_WORDS else "pm"
    return (text[:m.start()] + " " + text[m.end():]).strip(), marker


TIME_PATTERNS = [
    # 14:30, 14:30:00, 9.30 (only with two-digit minutes)
    re.compile(r"^(\d{1,2})[:.](\d{2})(?::\d{2})?$"),
    # 14h30, 14h, 14 h 30, 9H
    re.compile(r"^(\d{1,2})\s*[hH]\s*(\d{2})?$"),
    # 14時30分, 14時 / 2시 30분, 2시
    re.compile(r"^(\d{1,2})\s*[時时시]\s*(?:(\d{1,2})\s*[分분])?$"),
]


def _read_time(text):
    """One time of day (no date) -> 'HH:MM' or None."""
    t = single_spaces(ascii_digits(clean(text)))
    t, marker = _marker(t)
    t = t.strip()
    for rx in TIME_PATTERNS:
        m = rx.match(t)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2)) if m.group(2) else 0
            return _hm(h, mi, marker)
    if marker and re.fullmatch(r"\d{1,2}", t):          # 9 AM
        return _hm(int(t), 0, marker)
    return None


@_guard
def time(value, locale=None):
    if isinstance(value, datetime.datetime):
        return True, "%02d:%02d" % (value.hour, value.minute)
    if isinstance(value, datetime.time):
        return True, "%02d:%02d" % (value.hour, value.minute)
    if not isinstance(value, str):
        return FAIL
    got = _read_time(value)
    if got:
        return True, got
    # the time part of a date and time: 15/03/2024 14:30
    t = single_spaces(ascii_digits(clean(value)))
    m = re.match(r"^(\S+(?:\s+\S+){0,3}?)\s+(\d{1,2}[:.h]\d{2}(?::\d{2})?"
                 r"(?:\s*\S+)?|\S*\d{1,2}\s*[時时시].*)$", t)
    if m and _read_date(m.group(1), locale):
        got = _read_time(m.group(2))
        if got:
            return True, got
    return FAIL


RANGE_RX = re.compile(r"\s*(?:-|–|—|~|〜|～|to|à|a|bis|до|إلى|الى|至|से)\s*")
SLOT_SPLIT = re.compile(r"\s*(?:/|,|;|&|\+|\bet\b|\band\b|\by\b|\be\b|"
                        r"\bи\b|و|、|，|及)\s*")


@_guard
def hours(value, locale=None):
    if not isinstance(value, str):
        return FAIL
    t = single_spaces(ascii_digits(clean(value)))
    if not t:
        return FAIL
    low = key(t)
    words = closed_words()
    if low.rstrip(".!") in words:
        return True, "closed"
    ranges = []
    for slot in SLOT_SPLIT.split(t):
        slot = slot.strip()
        if not slot:
            continue
        if key(slot).rstrip(".!") in words:
            continue                      # "Fermé, 14h-19h": afternoon only
        pieces = [p for p in RANGE_RX.split(slot) if p.strip()]
        if len(pieces) != 2:
            return FAIL
        a, b = pieces
        # "9:00 AM - 5:30 PM" / "오전 9시 - 오후 6시": markers on each side
        start, end = _read_time(a), _read_time(b)
        if start is None or end is None:
            return FAIL
        ranges.append("%s-%s" % (start, end))
    if not ranges:
        return FAIL
    return True, ", ".join(ranges)


@_guard
def weekday(value, locale=None):
    if not isinstance(value, str):
        return FAIL
    lang, country = parse_locale(locale)
    t = key(value).rstrip(".")
    t = re.sub(r"^[(（]\s*|\s*[)）]$", "", t)
    if len(t) == 1:
        raw = clean(value).strip("()（）")
        if raw in HANJA_DAYS and lang in ("ja", "ko"):
            return True, HANJA_DAYS.index(raw)
        if raw in HANGUL_DAYS and lang == "ko":
            return True, HANGUL_DAYS.index(raw)
        if raw.upper() in SPANISH_LETTERS and lang == "es":
            return True, SPANISH_LETTERS.index(raw.upper())
        return FAIL
    table = weekday_table()
    if lang in table and t in table[lang]:
        return True, table[lang][t]
    found = set()
    for words in table.values():
        if t in words:
            found.add(words[t])
    if len(found) == 1:
        return True, found.pop()
    return FAIL


TRUE_MARKS = {"cjk": set("○◯Oo√✓✔"), "ru": set("✓✔√xXхХ"),
              "other": set("✓✔√xX")}
FALSE_MARKS = {"cjk": set("×✕Xx✗✘"), "ru": set("✗✘"), "other": set("✗✘")}


@_guard
def boolean(value, locale=None):
    if isinstance(value, bool):
        return True, value
    if _is_number(value):
        if value == 1:
            return True, True
        if value == 0:
            return True, False
        return FAIL
    if not isinstance(value, str):
        return FAIL
    lang, country = parse_locale(locale)
    raw = clean(value)
    if len(raw) == 1 and not raw.isdigit() and raw != "+":
        group = "cjk" if lang in ("zh", "ja", "ko") else \
            "ru" if lang == "ru" else "other"
        if raw in TRUE_MARKS[group]:
            return True, True
        if raw in FALSE_MARKS[group]:
            return True, False
    t = key(raw).rstrip(".!")
    if t in ("1", "+", "true", "vrai"):
        return True, True
    if t in ("0", "false", "faux"):
        return True, False
    yes, no = yes_no_table()
    if t in yes:
        return True, True
    if t in no:
        return True, False
    return FAIL


@_guard
def phone(value, locale=None):
    import phonenumbers
    if isinstance(value, bool):
        return FAIL
    if isinstance(value, float):
        if not value.is_integer():
            return FAIL
        value = int(value)
    t = ascii_digits(clean(value))
    if not re.search(r"\d", t) or re.search(r"[^\W\d_]{2,}", t):
        return FAIL
    lang, country = parse_locale(locale)
    region = country or {"ja": "JP", "ko": "KR", "hi": "IN",
                         "it": "IT"}.get(lang)
    try:
        number = phonenumbers.parse(t, region)
    except phonenumbers.NumberParseException:
        return FAIL
    if not phonenumbers.is_valid_number(number):
        return FAIL
    return True, phonenumbers.format_number(
        number, phonenumbers.PhoneNumberFormat.E164)


EMAIL_RX = re.compile(r"^[a-z0-9._%+\-']+@[a-z0-9.\-]+\.[a-z]{2,}$")


@_guard
def email(value, locale=None):
    if not isinstance(value, str):
        return FAIL
    t = clean(value).lower()
    if t.startswith("mailto:"):
        t = t[7:]
    t = t.strip()
    if not EMAIL_RX.match(t) or ".." in t:
        return FAIL
    return True, t


def _minutes(total):
    if total is None or total < 0 or abs(total - round(total)) > 1e-6:
        return None
    return int(round(total))


@_guard
def duration(value, locale=None):
    if isinstance(value, bool):
        return FAIL
    if isinstance(value, int):
        return (True, value) if value >= 0 else FAIL
    if isinstance(value, float):
        return (True, int(value)) if value.is_integer() and value >= 0 \
            else FAIL
    if isinstance(value, datetime.timedelta):
        got = _minutes(value.total_seconds() / 60.0)
        return (True, got) if got is not None else FAIL
    if isinstance(value, datetime.time):
        return True, value.hour * 60 + value.minute
    if not isinstance(value, str):
        return FAIL
    t = single_spaces(ascii_digits(clean(value))).casefold()
    # 1:30 (hours:minutes)
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::00)?", t)
    if m:
        return True, int(m.group(1)) * 60 + int(m.group(2))
    if re.fullmatch(r"\d+", t):
        return True, int(t)
    minute_words, hour_words = duration_words()
    word = r"[^\d\s,.]+\.?"
    tokens = re.findall(r"\d+(?:[.,]\d+)?|%s|[^\s]" % word, t)
    total, number, used_unit = 0.0, None, False
    for tok in tokens:
        if re.fullmatch(r"\d+(?:[.,]\d+)?", tok):
            if number is not None:
                if not used_unit:
                    return FAIL
                # "1h30": minutes after an hour count without a word
                total += float(number)
            number = float(tok.replace(",", "."))
            continue
        w = tok.rstrip(".")
        if w in hour_words or w + "." in hour_words:
            if number is None:
                return FAIL
            total += number * 60
            number, used_unit = None, True
        elif w in minute_words or w + "." in minute_words:
            if number is None:
                return FAIL
            total += number
            number, used_unit = None, True
        elif w in ("et", "and", "y", "e", "и", "و"):
            continue
        else:
            # "1h30" is one token for the regex above only when glued
            m = re.fullmatch(r"(\d+)(%s)(\d{1,2})?" % "|".join(
                re.escape(h) for h in hour_words), w)
            if m:
                total += float(m.group(1)) * 60 + float(m.group(3) or 0)
                used_unit = True
                continue
            return FAIL
    if number is not None:
        if not used_unit:
            return FAIL
        total += number                   # "1 h 30": the rest is minutes
    got = _minutes(total)
    if got is None or not used_unit:
        return FAIL
    return True, got


@_guard
def tax_included(value, locale=None):
    if not isinstance(value, str):
        return FAIL
    t = key(value)
    excluded, included = tax_words()
    for group, answer in ((excluded, False), (included, True)):
        for w in group:
            if re.search(r"(?<![^\W_])%s(?![^\W_])" % re.escape(w), t) or \
                    (not re.search(r"[a-zа-я]", w) and w in t):
                return True, answer
    return FAIL


@_guard
def text(value, locale=None):
    if isinstance(value, bool):
        return True, "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return True, str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return FAIL
        if value.is_integer():
            return True, str(int(value))
        return True, repr(round(value, 9))
    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time(0):
            return True, value.date().isoformat()
        return True, value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, (datetime.date, datetime.time)):
        return True, value.isoformat() if isinstance(value, datetime.date) \
            else "%02d:%02d" % (value.hour, value.minute)
    if isinstance(value, datetime.timedelta):
        return True, str(value)
    if not isinstance(value, str):
        return FAIL
    t = single_spaces(clean(value))
    return (True, t) if t else FAIL


HELPERS = {
    "text": text, "amount": amount, "currency": currency,
    "integer": integer, "percent": percent, "date": date, "time": time,
    "hours": hours, "weekday": weekday, "boolean": boolean, "phone": phone,
    "email": email, "duration": duration, "tax_included": tax_included,
}
TOTALS = _totals()
