"""
names.py - people, company names, postal addresses, e-mails and web
addresses for every locale.

People come from Faker where Faker passes the checks of section 10.3
(see faker_check.py and data/faker_decisions.json), otherwise from the
locale's own lists (data/<locale>/names.json). Addresses always come from
the locale's own lists, so the address order and the postcode of the
town are right.
"""
import re
import unicodedata

from gen import data as D

_FAKERS = {}


def faker_for(locale_name):
    """A cached Faker instance (None if Faker or the locale is missing)."""
    if locale_name not in _FAKERS:
        try:
            from faker import Faker
            _FAKERS[locale_name] = Faker(locale_name)
        except Exception:
            _FAKERS[locale_name] = None
    return _FAKERS[locale_name]


def uses_faker(loc, what):
    """Did the Faker rule accept this locale for names / addresses?"""
    decisions = D.faker_decisions().get(loc["code"], {})
    return loc.get("faker") and decisions.get(what) == "faker"


# ---------------------------------------------------------------------
#  people
# ---------------------------------------------------------------------
def person(rng, loc, gender=None):
    """-> dict(given, family, full, short, gender, patronymic)."""
    gender = gender or rng.choice(["m", "f"])
    lang = loc["lang"]
    given = family = patronymic = None
    if uses_faker(loc, "names") and rng.random() < 0.5:
        fake = faker_for(loc["faker"])
        fake.seed_instance(rng.getrandbits(32))
        if lang == "ru":
            given = fake.first_name_male() if gender == "m" \
                else fake.first_name_female()
            family = fake.last_name_male() if gender == "m" \
                else fake.last_name_female()
            patronymic = fake.middle_name_male() if gender == "m" \
                else fake.middle_name_female()
        else:
            given = fake.first_name_male() if gender == "m" \
                else fake.first_name_female()
            family = fake.last_name()
    else:
        names = D.locale_list(loc["code"], "names") or {}
        pool_given = names.get("given_male" if gender == "m" else
                               "given_female") or ["Alex"]
        given = rng.choice(pool_given)
        fams = names.get("family") or ["Martin"]
        k = rng.randrange(len(fams))
        family = fams[k]
        if lang == "ru":
            if gender == "f" and names.get("family_female"):
                family = names["family_female"][k]
            pats = names.get("patronymic_male" if gender == "m" else
                             "patronymic_female")
            patronymic = rng.choice(pats) if pats else None
    return build_person(rng, lang, loc, given, family, patronymic, gender)


def build_person(rng, lang, loc, given, family, patronymic, gender):
    if lang in ("zh", "ko"):
        full = family + given
    elif lang == "ja":
        full = family + (" " if rng.random() < 0.6 else "　"
                         if rng.random() < 0.3 else "") + given
    elif lang == "ru":
        if patronymic and rng.random() < 0.7:
            full = "%s %s %s" % (family, given, patronymic)
        else:
            full = "%s %s" % (given, family) if rng.random() < 0.5 \
                else "%s %s" % (family, given)
    elif lang == "es" and loc["country"] in ("ES", "MX", "CO", "CL") and \
            rng.random() < 0.5:
        names = D.locale_list(loc["code"], "names") or {}
        second = rng.choice(names.get("family") or [family])
        full = "%s %s %s" % (given, family, second)
    else:
        full = "%s %s" % (given, family)
    if lang == "ru" and patronymic:
        short = "%s %s. %s." % (family, given[0], patronymic[0])
    elif lang in ("zh", "ja", "ko"):
        short = full
    else:
        short = "%s. %s" % (given[0], family) if given else family
    return {"given": given, "family": family, "full": full.strip(),
            "short": short, "gender": gender, "patronymic": patronymic}


def honorific(rng, lex, gender):
    hon = lex.get("honorifics") or {}
    items = hon.get("male" if gender == "m" else "female") or []
    return rng.choice(items) if items else ""


# ---------------------------------------------------------------------
#  company names
# ---------------------------------------------------------------------
CJK = re.compile(r"[぀-ヿ一-鿿가-힯]")


def is_cjk_text(s):
    return bool(CJK.search(s))


def initials(rng, lang):
    if lang in ("zh", "ja", "ko", "ar", "hi"):
        return "".join(rng.choice("ABCDEFGHJKLMNPRSTVW")
                       for _ in range(rng.choice([2, 3])))
    if lang == "ru":
        return "".join(rng.choice("АБВГДЕКЛМНПРСТ")
                       for _ in range(rng.choice([2, 3])))
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVW")
                      for _ in range(rng.choice([2, 3])))
    return letters if rng.random() < 0.6 else ".".join(letters) + "."


def core_name(rng, loc, lex, act, city, family_person):
    """The name without legal form, from the language's name patterns."""
    patterns = lex.get("name_patterns") or ["{brand}"]
    key = loc["data"]
    words = (act.get("name_words") or {}).get(key) or \
        (act.get("names") or {}).get(key) or ["Services"]
    for _ in range(20):
        pattern = rng.choice(patterns)
        text = pattern.format(
            family=family_person["family"], given=family_person["given"],
            brand=rng.choice(lex.get("brand_words") or ["Nova"]),
            activity_word=rng.choice(words), city=city,
            initials=initials(rng, loc["lang"]))
        text = re.sub(r"\s+", " ", text).strip()
        if 2 <= len(text) <= 60:
            return text
    return text


# names that never take a company form after them (law firms)
NO_FORM_ENDINGS = ("律师事务所", "律師事務所", "律師行", "法律事務所",
                   "법률사무소")


def attach_form(rng, loc, core, form_info, form_text=None):
    """Writes the legal form into the name, before or after, the way the
    country does it. Returns the full legal name."""
    lang = loc["lang"]
    form = form_text or form_info["forms"][0]
    position = rng.choice(form_info["position"])
    low = core.lower()
    if any(low.endswith(f.lower()) or low.startswith(f.lower() + " ")
           for f in form_info["forms"]):
        return core                     # the pattern already holds the form
    if core.endswith(NO_FORM_ENDINGS):
        return core                     # "华信律师事务所", never "...有限公司"
    if lang == "ru" and position == "prefix":
        r = rng.random()
        if r < 0.7:
            quoted = "«%s»" % core
        elif r < 0.9:
            quoted = "“%s”" % core if rng.random() < 0.3 \
                else '"%s"' % core
        else:
            quoted = core
        return "%s %s" % (form, quoted)
    if lang in ("ja", "zh") or (lang == "ko" and form in ("(주)", "㈜")):
        return form + core if position == "prefix" else core + form
    if lang == "ko":
        sep = " " if rng.random() < 0.5 else ""
        return form + sep + core if position == "prefix" \
            else core + sep + form
    if position == "prefix":
        return "%s %s" % (form, core)
    sep = ", " if lang == "en" and form in ("Inc.", "Ltd.", "LLC") and \
        rng.random() < 0.2 else " "
    return core + sep + form


def pick_form_text(rng, loc, form_info):
    """Which written variant of the form this business uses: (株) 20 %,
    ㈱ 5 %, (주) 30 %, ㈜ 10 % (section 10.7)."""
    forms = form_info["forms"]
    code = form_info["code"]
    r = rng.random()
    if code == "JP_KK":
        return "(株)" if r < 0.2 else "㈱" if r < 0.25 else "株式会社"
    if code == "KR_JSH":
        return "(주)" if r < 0.3 else "㈜" if r < 0.4 else "주식회사"
    if code == "IN_PVT" and loc["lang"] == "hi":
        return rng.choice(["Pvt. Ltd.", "Private Limited"]) if r < 0.4 \
            else rng.choice(["प्राइवेट लिमिटेड", "प्रा. लि."])
    return rng.choice(forms)


# ---------------------------------------------------------------------
#  addresses
# ---------------------------------------------------------------------
def _pc(rng, place, field="postcode"):
    value = place.get(field, "")
    if isinstance(value, list):
        return rng.choice(value) if value else ""
    return value or ""


def address(rng, loc, lex, place=None, with_country=False):
    """-> dict(lines=[...], one=..., city=..., postcode=..., country=...)
    lines: the address as printed on several lines; one: on one line."""
    code, lang, country = loc["code"], loc["lang"], loc["country"]
    places = D.locale_list(code, "cities") or [{"city": "?",
                                                 "postcode": ""}]
    streets = (D.locale_list(code, "streets") or {}).get("streets") or \
        ["Main Street"]
    place = place or rng.choice(places)
    street = rng.choice(streets)
    num = str(rng.choice([rng.randint(1, 40), rng.randint(1, 200),
                          rng.randint(1, 1500)]))
    city = place.get("city") or place.get("district") or ""
    cname = (lex.get("country_names") or {}).get(country, "")
    pc = ""
    lines = []
    if country == "JP":
        pc = _pc(rng, place)
        block = "%d-%d-%d" % (rng.randint(1, 5), rng.randint(1, 30),
                              rng.randint(1, 20))
        if rng.random() < 0.3:
            block = "%d丁目%d番%d号" % tuple(int(x) for x in block.split("-"))
        main = "%s%s%s%s" % (place.get("pref", ""), place.get("city", ""),
                             place.get("town", ""), block)
        bld = (street + "%dF" % rng.randint(1, 12)) if rng.random() < 0.5 \
            else ""
        lines = ["〒" + pc, main] + ([bld] if bld else [])
        one = "〒%s %s%s" % (pc, main, (" " + bld) if bld else "")
        city = place.get("city", "")
    elif country == "CN" or (country == "SG" and lang == "zh" and
                             rng.random() < 0.5 and False):
        pc = _pc(rng, place)
        prov = place.get("province", "")
        city_name = place.get("city", "")
        head = city_name if prov == city_name else prov + city_name
        room = "%d室" % rng.randint(101, 2808) if rng.random() < 0.6 else ""
        one = "%s%s%s%d号%s" % (head, place.get("district", ""), street,
                               rng.randint(1, 999), room)
        lines = [one]
        city = city_name
    elif country == "TW":
        pc = _pc(rng, place)
        floor = "%d樓" % rng.randint(2, 20) if rng.random() < 0.6 else ""
        one = "%s%s%s%s%d號%s" % (pc if rng.random() < 0.6 else "",
                                  place.get("city", ""),
                                  place.get("district", ""), street,
                                  rng.randint(1, 300), floor)
        lines = [one]
        city = place.get("city", "")
    elif country == "HK":
        floor = "%d樓%s室" % (rng.randint(2, 40), rng.randint(1, 20)) \
            if rng.random() < 0.7 else ""
        one = "%s%s%s%d號%s" % ("香港" if rng.random() < 0.5 else "",
                               place.get("district", ""), street,
                               rng.randint(1, 300), floor)
        lines = [one]
        city = place.get("district", "")
    elif country == "SG":
        pc = _pc(rng, place)
        unit = "#%02d-%02d" % (rng.randint(1, 30), rng.randint(1, 20))
        if lang == "zh" and rng.random() < 0.5:
            one = "新加坡%s%s%d号%s" % (pc, street, rng.randint(1, 300), unit)
            lines = [one]
        else:
            lines = ["%s %s" % (num, street), unit,
                     "Singapore %s" % pc]
            one = ", ".join(lines)
    elif country == "KR":
        pc = _pc(rng, place)
        main = "%s %s %s %d" % (place.get("sido", ""),
                                place.get("sigungu", ""), street,
                                rng.randint(1, 500))
        extra = ", %d층" % rng.randint(1, 20) if rng.random() < 0.6 else ""
        dong = " (%s)" % place["dong"] if place.get("dong") and \
            rng.random() < 0.5 else ""
        one = main + extra + dong
        lines = [one]
        if rng.random() < 0.3:
            one = "(%s) %s" % (pc, one)
            lines = [one]
        city = place.get("sigungu", "")
    elif country in ("RU", "KZ", "BY"):
        pc = _pc(rng, place)
        region = place.get("region") or ""
        house = "д. %s" % num
        office = rng.choice(["", ", офис %d" % rng.randint(1, 500),
                             ", кв. %d" % rng.randint(1, 200),
                             ", пом. %d" % rng.randint(1, 40)])
        parts = [pc] + ([region] if region and rng.random() < 0.4 else []) + \
            ["г. %s" % city, "%s, %s%s" % (street, house, office)]
        one = ", ".join(p for p in parts if p)
        lines = [one] if rng.random() < 0.6 else \
            ["%s, %s%s" % (street, house, office),
             "%s, г. %s" % (pc, city)]
    elif country in ("SA", "AE", "EG") or (country == "MA" and lang == "ar"):
        pc = _pc(rng, place)
        districts = place.get("districts") or []
        district = rng.choice(districts) if districts else ""
        first = street if rng.random() < 0.5 else "%s %s" % (num, street)
        if country == "AE" and rng.random() < 0.5:
            first = "مكتب %d، %s" % (rng.randint(101, 2505), first)
        parts = [first] + ([district] if district else [])
        second = city + (" " + pc if pc and rng.random() < 0.7 else "")
        lines = ["، ".join(parts), second]
        if rng.random() < 0.3:
            box = "ص.ب %d" % rng.randint(100, 99999)
            lines.append(box)
        one = "، ".join(lines)
    elif country == "IN":
        pc = _pc(rng, place, "pin")
        areas = place.get("areas") or []
        area = rng.choice(areas) if areas else ""
        unit = rng.choice(["", "Shop No. %d, " % rng.randint(1, 40),
                           "Office %d, " % rng.randint(101, 909),
                           "%d, " % rng.randint(1, 300)]) if lang == "en" \
            else rng.choice(["", "%d, " % rng.randint(1, 300),
                             "दुकान नं. %d, " % rng.randint(1, 40)])
        first = "%s%s" % (unit, street) + (", " + area if area else "")
        second = "%s, %s %s" % (place.get("city", ""), place.get("state", ""),
                                pc)
        lines = [first, second]
        one = first + ", " + second
    elif country == "US":
        pc = _pc(rng, place, "zip")
        suite = rng.choice(["", ", Suite %d" % rng.randint(100, 999),
                            ", Unit %d" % rng.randint(1, 50)])
        first = "%s %s%s" % (num, street, suite)
        second = "%s, %s %s" % (city, place.get("state", ""), pc)
        lines = [first, second]
        one = first + ", " + second
    elif country == "GB":
        pc = _pc(rng, place)
        first = "%s %s" % (num, street)
        lines = [first, city, pc] if rng.random() < 0.5 else \
            [first, "%s %s" % (city, pc)]
        one = ", ".join(lines)
    elif country == "AU":
        pc = _pc(rng, place)
        lvl = "Level %d, " % rng.randint(1, 30) if rng.random() < 0.3 else ""
        first = "%s%s %s" % (lvl, num, street)
        second = "%s %s %s" % (city.upper() if rng.random() < 0.3 else city,
                               place.get("state", ""), pc)
        lines = [first, second]
        one = first + ", " + second
    elif country == "CA":
        pc = _pc(rng, place)
        prov = place.get("province", "")
        if lang == "fr":
            first = "%s, %s" % (num, street) + (
                ", bureau %d" % rng.randint(100, 999)
                if rng.random() < 0.4 else "")
            second = "%s (%s)  %s" % (city, {"QC": "Québec", "ON": "Ontario"}
                                     .get(prov, prov), pc) \
                if rng.random() < 0.5 else "%s, %s %s" % (city, prov, pc)
        else:
            first = "%s %s" % (num, street) + (
                ", Suite %d" % rng.randint(100, 999)
                if rng.random() < 0.4 else "")
            second = "%s, %s %s" % (city, prov, pc)
        lines = [first, second]
        one = first + ", " + second
    elif country == "NG":
        areas = place.get("areas") or []
        area = rng.choice(areas) if areas else ""
        first = "%s %s" % (num, street) + (", " + area if area else "")
        lines = [first, "%s, %s" % (city, place.get("state", ""))]
        one = ", ".join(lines)
    elif country in ("BE", "CH") or (country == "IT" and lang == "it" and
                                     False):
        pc = _pc(rng, place)
        first = "%s %s" % (street, num)
        second = "%s %s" % (pc, city)
        lines = [first, second]
        one = first + ", " + second
    elif country == "IT":
        pc = _pc(rng, place)
        prov = place.get("region", "")
        first = "%s %s" % (street, num) if rng.random() < 0.6 else \
            "%s, %s" % (street, num)
        second = "%s %s" % (pc, city) + (" (%s)" % prov if prov else "")
        lines = [first, second]
        one = first + " - " + second if rng.random() < 0.3 else \
            first + ", " + second
    elif country in ("ES", "MX", "AR", "CO", "CL"):
        pc = _pc(rng, place)
        region = place.get("region", "")
        if country == "ES":
            first = "%s, %s" % (street, num) + rng.choice(
                ["", ", %dº %s" % (rng.randint(1, 8), rng.choice("ABCD")),
                 ", local %d" % rng.randint(1, 20)])
            second = "%s %s" % (pc, city) + (
                " (%s)" % region if region and region != city and
                rng.random() < 0.5 else "")
        elif country == "MX":
            districts = place.get("districts") or []
            col = rng.choice(districts) if districts else ""
            first = "%s %s" % (street, num) + (", " + col if col else "")
            second = "C.P. %s, %s, %s" % (pc, city, region) if \
                rng.random() < 0.5 else "%s %s, %s" % (pc, city, region)
        elif country == "AR":
            first = "%s %s" % (street, num) + (
                ", Piso %d" % rng.randint(1, 20) if rng.random() < 0.4
                else "")
            second = "%s %s" % (pc, city) + (", " + region if region and
                                             region != city else "")
        elif country == "CO":
            first = "%s # %d-%d" % (street, rng.randint(1, 120),
                                    rng.randint(1, 99))
            second = city + (", " + region if region else "")
        else:
            first = "%s %s" % (street, num) + (
                ", of. %d" % rng.randint(10, 999) if rng.random() < 0.4
                else "")
            second = city + (", " + region if region else "")
        lines = [first, second]
        one = first + ", " + second
    else:                                   # FR, MA (fr), SN and others
        pc = _pc(rng, place)
        comma = "," if rng.random() < 0.2 else ""
        first = "%s%s %s" % (num, comma, street)
        if rng.random() < 0.15:
            first = rng.choice(["Bât. %s, " % rng.choice("ABC"),
                                "ZA %s, " % city, "Lot %d, " %
                                rng.randint(1, 80)]) + first
        second = ("%s %s" % (pc, city)).strip()
        if rng.random() < 0.1 and country == "FR":
            second = second.upper()
        lines = [first, second]
        one = first + ", " + second
    if with_country and cname and country not in ("JP", "CN", "TW", "KR"):
        lines = lines + [cname]
        one = one + ", " + cname
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in lines if ln.strip()]
    return {"lines": lines, "one": re.sub(r"[ \t]+", " ", one).strip(),
            "city": city, "postcode": pc, "country": country}


# ---------------------------------------------------------------------
#  e-mail and web addresses (always ASCII)
# ---------------------------------------------------------------------
CYR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k",
                "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts",
                "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))
KANA = {}
for row, cons in [("アイウエオ", ""), ("カキクケコ", "k"), ("サシスセソ", "s"),
                  ("タチツテト", "t"), ("ナニヌネノ", "n"), ("ハヒフヘホ", "h"),
                  ("マミムメモ", "m"), ("ヤ_ユ_ヨ", "y"), ("ラリルレロ", "r"),
                  ("ワ___ヲ", "w"), ("ガギグゲゴ", "g"), ("ザジズゼゾ", "z"),
                  ("ダヂヅデド", "d"), ("バビブベボ", "b"), ("パピプペポ", "p")]:
    for ch, v in zip(row, "aiueo"):
        if ch != "_":
            KANA[ch] = cons + v
KANA.update({"ン": "n", "シ": "shi", "チ": "chi", "ツ": "tsu", "フ": "fu",
             "ジ": "ji", "ー": "", "ッ": "", "ヴ": "vu"})
HANGUL_L = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "",
            "j", "jj", "ch", "k", "t", "p", "h"]
HANGUL_V = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae",
            "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
HANGUL_T = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l",
            "l", "p", "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t",
            "p", "t"]
SYLLABLES = ["hua", "xin", "tai", "long", "feng", "da", "heng", "rui", "jia",
             "sheng", "hong", "an", "kai", "yuan", "mei", "tian", "ming",
             "guang", "sun", "yu", "fu", "kang", "le", "bao", "chen", "hai"]


# Japanese readings are not derivable from kanji without a dictionary:
# each kanji gets a plausible Japanese morpheme instead (stable per
# character), so a domain looks Japanese ("yamamotokawa.co.jp") rather
# than Chinese.
JA_MORPHEMES = ["yama", "kawa", "ta", "naka", "moto", "mura", "ki", "shima",
                "da", "no", "hara", "sawa", "fuji", "mori", "ishi", "matsu",
                "i", "o", "saka", "hashi", "kami", "ya", "mizu", "hon",
                "sato", "wa", "ta", "ku", "ko", "tsu", "hira", "nishi"]
ARABIC = dict(zip("ابتثجحخدذرزسشصضطظعغفقكلمنهويةىءأإآؤئ",
                  ["a", "b", "t", "th", "j", "h", "kh", "d", "dh", "r", "z",
                   "s", "sh", "s", "d", "t", "z", "a", "gh", "f", "q", "k",
                   "l", "m", "n", "h", "w", "y", "a", "a", "", "a", "i", "a",
                   "w", "y"]))
DEVA_CONS = dict(zip(
    "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह",
    ["k", "kh", "g", "gh", "n", "ch", "chh", "j", "jh", "n", "t", "th", "d",
     "dh", "n", "t", "th", "d", "dh", "n", "p", "ph", "b", "bh", "m", "y",
     "r", "l", "v", "sh", "sh", "s", "h"]))
DEVA_VOWELS = dict(zip("अआइईउऊएऐओऔऋ", ["a", "a", "i", "i", "u", "u", "e",
                                        "ai", "o", "au", "ri"]))
DEVA_SIGNS = dict(zip("ािीुूेैोौृ", ["a", "i", "i", "u", "u", "e", "ai", "o",
                                      "au", "ri"]))


def _devanagari(word):
    """Simple Hindi transliteration: consonants carry an 'a' unless a
    vowel sign or virama follows; the final 'a' of a word is dropped."""
    out = []
    for k, ch in enumerate(word):
        nxt = word[k + 1] if k + 1 < len(word) else ""
        if ch in DEVA_CONS:
            out.append(DEVA_CONS[ch])
            if nxt not in DEVA_SIGNS and nxt != "्" and nxt:
                out.append("a")
        elif ch in DEVA_VOWELS:
            out.append(DEVA_VOWELS[ch])
        elif ch in DEVA_SIGNS:
            out.append(DEVA_SIGNS[ch])
        elif ch in "ंँ":
            out.append("n")
        elif ch == "ः":
            out.append("h")
        elif ch == "्" or ch == "़":
            continue
        else:
            out.append(ch)
    return "".join(out)


def romanize(text, rng=None, lang=None):
    """A plain ASCII slug of a name, for e-mails and websites."""
    out = []
    text = re.sub(r"[\u0900-\u097F]+", lambda m: _devanagari(m.group(0)),
                  text)
    text = re.sub(r"(^|\s)ال", lambda m: m.group(1) + "al", text)
    for ch in text:
        low = ch.lower()
        if low in CYR:
            out.append(CYR[low])
        elif ch in ARABIC:
            out.append(ARABIC[ch])
        elif ch in KANA:
            out.append(KANA[ch])
        elif "ぁ" <= ch <= "ゖ":
            out.append(KANA.get(chr(ord(ch) + 0x60), ""))
        elif "가" <= ch <= "힣":
            code = ord(ch) - 0xAC00
            ll, vv, tt = code // 588, (code % 588) // 28, code % 28
            out.append(HANGUL_L[ll] + HANGUL_V[vv] + HANGUL_T[tt])
        elif "一" <= ch <= "鿿":
            pool = JA_MORPHEMES if lang == "ja" else SYLLABLES
            out.append(pool[ord(ch) % len(pool)])
        else:
            base = unicodedata.normalize("NFKD", ch)
            base = "".join(c for c in base if c.isascii())
            out.append(base.lower() if base.isalnum() else " ")
    slug = re.sub(r"[^a-z0-9]+", "-", "".join(out)).strip("-")
    return slug


def _short_slug(name, lang):
    """CJK names have no spaces: keep the first 2-4 characters, so the
    domain stays short (real ones are)."""
    cjk = re.findall(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7a3]", name)
    if len(cjk) > 4:
        name = "".join(cjk[:4]) if len(cjk) < 6 else "".join(cjk[:3])
    return romanize(name, lang=lang)


TLD = {"FR": [".fr", ".com"], "BE": [".be"], "CH": [".ch"], "CA": [".ca",
       ".com"], "MA": [".ma"], "SN": [".sn"], "US": [".com", ".net",
       ".us"], "GB": [".co.uk", ".com"], "IN": [".in", ".co.in", ".com"],
       "AU": [".com.au"], "NG": [".com.ng", ".ng"], "RU": [".ru"],
       "KZ": [".kz"], "BY": [".by"], "ES": [".es", ".com"],
       "MX": [".com.mx", ".mx"], "AR": [".com.ar"], "CO": [".com.co",
       ".co"], "CL": [".cl"], "IT": [".it"], "SA": [".sa", ".com.sa",
       ".com"], "AE": [".ae", ".com"], "EG": [".com.eg", ".com"],
       "CN": [".cn", ".com.cn", ".com"], "TW": [".com.tw", ".tw"],
       "HK": [".com.hk", ".hk"], "SG": [".com.sg", ".sg"],
       "JP": [".co.jp", ".jp"], "KR": [".co.kr", ".kr", ".com"]}
FREEMAIL = {"FR": ["orange.fr", "gmail.com", "wanadoo.fr", "free.fr",
                   "sfr.fr"], "RU": ["mail.ru", "yandex.ru", "gmail.com"],
            "KZ": ["mail.ru", "gmail.com"], "BY": ["mail.ru", "tut.by"],
            "JP": ["gmail.com", "yahoo.co.jp"], "KR": ["naver.com",
                                                       "daum.net",
                                                       "gmail.com"],
            "CN": ["qq.com", "163.com", "126.com"], "IN": ["gmail.com",
                                                          "rediffmail.com",
                                                          "yahoo.co.in"],
            "IT": ["libero.it", "gmail.com", "virgilio.it"],
            "ES": ["gmail.com", "hotmail.es"], "MX": ["gmail.com",
                                                      "hotmail.com"],
            "TW": ["gmail.com", "yahoo.com.tw"], "BE": ["skynet.be",
                                                        "gmail.com"]}
LOCAL_PARTS = {"fr": ["contact", "info", "bonjour", "compta", "devis"],
               "es": ["info", "contacto", "ventas", "hola"],
               "it": ["info", "amministrazione", "commerciale"],
               "ru": ["info", "office", "sales", "zakaz"],
               "de": ["info", "kontakt"]}


def web_identity(rng, loc, name_for_slug, person_=None):
    """-> dict(slug, domain, email, website, social) for an org."""
    slug = _short_slug(name_for_slug, loc["lang"]) or rng.choice(
        ["office", "company", "group", "services"])
    parts = slug.split("-")
    if len(slug) > 20 and len(parts) > 1:
        slug = "-".join(parts[:2])
    if rng.random() < 0.3:
        slug = slug.replace("-", "")
    country = loc["country"]
    domain = slug + rng.choice(TLD.get(country, [".com"]))
    local = rng.choice(LOCAL_PARTS.get(loc["lang"], ["info", "contact",
                                                      "sales", "office",
                                                      "hello"]))
    if person_ and rng.random() < 0.25:
        g = romanize(person_["given"], lang=loc["lang"]) or "info"
        f = romanize(person_["family"], lang=loc["lang"]) or "info"
        local = rng.choice(["%s.%s" % (g, f), g, "%s%s" % (g[:1], f)])
    email_domain = domain
    if rng.random() < 0.2 and country in FREEMAIL:
        email_domain = rng.choice(FREEMAIL[country])
        local = slug.replace("-", ".")[:20]
    return {"slug": slug, "domain": domain,
            "email": "%s@%s" % (local, email_domain),
            "website": domain}


def show_url(rng, domain, path=""):
    r = rng.random()
    if r < 0.45:
        return "www." + domain + path
    if r < 0.7:
        return "https://www." + domain + path
    if r < 0.85:
        return domain + path
    return "http://www." + domain + "/" + path.lstrip("/")


SOCIAL = {"CN": ["weibo.com/{s}"], "JP": ["instagram.com/{s}",
                                        "line.me/R/ti/p/@{s}",
                                        "x.com/{s}"],
          "KR": ["instagram.com/{s}", "pf.kakao.com/_{s}",
                 "blog.naver.com/{s}"],
          "RU": ["vk.com/{s}", "t.me/{s}"], "BY": ["vk.com/{s}"],
          "KZ": ["instagram.com/{s}", "vk.com/{s}"]}
SOCIAL_DEFAULT = ["instagram.com/{s}", "facebook.com/{s}",
                  "linkedin.com/company/{s}", "x.com/{s}",
                  "youtube.com/@{s}", "tiktok.com/@{s}"]


def social_link(rng, loc, slug):
    pattern = rng.choice(SOCIAL.get(loc["country"], []) + SOCIAL_DEFAULT)
    text = pattern.format(s=slug.replace("-", ""))
    return ("https://www." + text) if rng.random() < 0.3 else text
