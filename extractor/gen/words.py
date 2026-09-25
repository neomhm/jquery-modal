"""
words.py - amounts written in words, as printed on invoices (trap T10:
always O). "Rupees One Lakh Twenty-Four Thousand Only", "Arrêté la
présente facture à la somme de mille deux cent quarante euros",
"壹万贰仟肆佰元整", "فقط ألف ومائتان وأربعون ريالاً لا غير",
"금 일백이십사만원정".

Each converter takes a non-negative integer and returns words. The
grammar is in code; it is simple on purpose (these words are never
labelled, they only have to look real).
"""

EN_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen",
            "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
            "nineteen"]
EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty",
           "seventy", "eighty", "ninety"]


def en_below_1000(n):
    out = []
    if n >= 100:
        out.append(EN_UNITS[n // 100] + " hundred")
        n %= 100
        if n:
            out.append("and")
    if n >= 20:
        out.append(EN_TENS[n // 10] + ("-" + EN_UNITS[n % 10]
                                       if n % 10 else ""))
    elif n or not out:
        out.append(EN_UNITS[n])
    return " ".join(out)


def english(n, indian=False):
    if n == 0:
        return "zero"
    parts = []
    scales = [(10 ** 7, "crore"), (10 ** 5, "lakh"), (1000, "thousand")] \
        if indian else [(10 ** 9, "billion"), (10 ** 6, "million"),
                        (1000, "thousand")]
    for size, word in scales:
        if n >= size:
            head = n // size
            parts.append((english(head, indian) if head >= 1000
                          else en_below_1000(head)) + " " + word)
            n %= size
    if n:
        parts.append(en_below_1000(n))
    return " ".join(parts)


FR_UNITS = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept",
            "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
            "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
FR_TENS = ["", "dix", "vingt", "trente", "quarante", "cinquante",
           "soixante"]


def fr_below_100(n):
    if n < 20:
        return FR_UNITS[n]
    if n < 70:
        t, u = divmod(n, 10)
        if u == 0:
            return FR_TENS[t]
        return FR_TENS[t] + ("-et-un" if u == 1 else "-" + FR_UNITS[u])
    if n < 80:
        return "soixante" + ("-et-" if n == 71 else "-") + FR_UNITS[n - 60]
    if n == 80:
        return "quatre-vingts"
    return "quatre-vingt-" + FR_UNITS[n - 80]


def fr_below_1000(n):
    h, r = divmod(n, 100)
    out = []
    if h:
        if h == 1:
            out.append("cent")
        else:
            out.append(FR_UNITS[h] + (" cents" if r == 0 else " cent"))
    if r or not out:
        out.append(fr_below_100(r))
    return " ".join(out)


def french(n):
    if n == 0:
        return "zéro"
    out = []
    for size, one, many in [(10 ** 9, "un milliard", "milliards"),
                            (10 ** 6, "un million", "millions")]:
        if n >= size:
            head = n // size
            out.append(one if head == 1 else french(head) + " " + many)
            n %= size
    if n >= 1000:
        head = n // 1000
        out.append("mille" if head == 1 else
                   fr_below_1000(head).replace("cents", "cent") + " mille")
        n %= 1000
    if n:
        out.append(fr_below_1000(n))
    return " ".join(out)


ES_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
            "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
            "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
            "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
            "veinticinco", "veintiséis", "veintisiete", "veintiocho",
            "veintinueve"]
ES_TENS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta",
           "setenta", "ochenta", "noventa"]
ES_HUND = ["", "ciento", "doscientos", "trescientos", "cuatrocientos",
           "quinientos", "seiscientos", "setecientos", "ochocientos",
           "novecientos"]


def es_below_1000(n, apocope=True):
    if n == 100:
        return "cien"
    h, r = divmod(n, 100)
    out = [ES_HUND[h]] if h else []
    if r:
        if r < 30:
            word = ES_UNITS[r]
        else:
            t, u = divmod(r, 10)
            word = ES_TENS[t] + (" y " + ES_UNITS[u] if u else "")
        if apocope and word.endswith("uno"):
            word = word[:-1]
            if word == "veintiun":
                word = "veintiún"
        out.append(word)
    return " ".join(out) or "cero"


def spanish(n):
    if n == 0:
        return "cero"
    out = []
    if n >= 10 ** 6:
        head = n // 10 ** 6
        out.append("un millón" if head == 1 else
                   es_below_1000(head) + " millones")
        n %= 10 ** 6
    if n >= 1000:
        head = n // 1000
        out.append("mil" if head == 1 else es_below_1000(head) + " mil")
        n %= 1000
    if n:
        out.append(es_below_1000(n, apocope=False))
    return " ".join(out)


IT_UNITS = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette",
            "otto", "nove", "dieci", "undici", "dodici", "tredici",
            "quattordici", "quindici", "sedici", "diciassette", "diciotto",
            "diciannove"]
IT_TENS = ["", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta",
           "settanta", "ottanta", "novanta"]


def it_below_1000(n):
    h, r = divmod(n, 100)
    out = ""
    if h:
        out = ("cento" if h == 1 else IT_UNITS[h] + "cento")
    if r:
        if r < 20:
            word = IT_UNITS[r]
        else:
            t, u = divmod(r, 10)
            tens = IT_TENS[t]
            if u in (1, 8):
                tens = tens[:-1]
            word = tens + (IT_UNITS[u] if u else "")
            if u == 3:
                word = word[:-3] + "tré"
        out += word
    return out or "zero"


def italian(n):
    if n == 0:
        return "zero"
    out = ""
    if n >= 10 ** 6:
        head = n // 10 ** 6
        out += ("unmilione" if head == 1 else
                it_below_1000(head) + "milioni")
        n %= 10 ** 6
    if n >= 1000:
        head = n // 1000
        out += "mille" if head == 1 else it_below_1000(head) + "mila"
        n %= 1000
    if n:
        out += it_below_1000(n)
    return out


RU_UNITS_M = ["ноль", "один", "два", "три", "четыре", "пять", "шесть",
              "семь", "восемь", "девять", "десять", "одиннадцать",
              "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
              "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
RU_UNITS_F = ["ноль", "одна", "две"] + RU_UNITS_M[3:]
RU_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят",
           "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
RU_HUND = ["", "сто", "двести", "триста", "четыреста", "пятьсот",
           "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def ru_below_1000(n, female=False):
    units = RU_UNITS_F if female else RU_UNITS_M
    h, r = divmod(n, 100)
    out = [RU_HUND[h]] if h else []
    if r >= 20:
        out.append(RU_TENS[r // 10])
        if r % 10:
            out.append(units[r % 10])
    elif r:
        out.append(units[r])
    return " ".join(out)


def ru_plural(n, forms):
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def russian(n):
    if n == 0:
        return "ноль"
    out = []
    for size, female, forms in [(10 ** 9, False, ("миллиард", "миллиарда",
                                                  "миллиардов")),
                                (10 ** 6, False, ("миллион", "миллиона",
                                                  "миллионов")),
                                (1000, True, ("тысяча", "тысячи", "тысяч"))]:
        if n >= size:
            head = n // size
            out.append(ru_below_1000(head, female) + " " +
                       ru_plural(head, forms))
            n %= size
    if n:
        out.append(ru_below_1000(n))
    return " ".join(out)


def russian_rubles(n, kopecks=0, currency="RUB"):
    word = {"RUB": ("рубль", "рубля", "рублей"),
            "BYN": ("белорусский рубль", "белорусских рубля",
                    "белорусских рублей"),
            "KZT": ("тенге", "тенге", "тенге")}.get(currency,
                                                   ("рубль", "рубля",
                                                    "рублей"))
    text = russian(n)
    text = text[0].upper() + text[1:]
    tail = "%02d %s" % (kopecks, ru_plural(kopecks, ("копейка", "копейки",
                                                      "копеек"))) \
        if currency != "KZT" else "%02d тиын" % kopecks
    return "%s %s %s" % (text, ru_plural(n, word), tail)


HI_0_100 = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह "
            "पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस चौबीस पच्चीस "
            "छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस "
            "छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस "
            "पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन "
            "चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ "
            "पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर "
            "चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी "
            "तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानबे "
            "बानबे तिरानबे चौरानबे पचानबे छियानबे सत्तानबे अट्ठानबे निन्यानबे "
            "सौ").split()


def hindi(n):
    if n == 0:
        return HI_0_100[0]
    out = []
    for size, word in [(10 ** 7, "करोड़"), (10 ** 5, "लाख"),
                       (1000, "हज़ार"), (100, "सौ")]:
        if n >= size:
            head = n // size
            out.append((hindi(head) if head > 99 else HI_0_100[head]) +
                       " " + word)
            n %= size
    if n:
        out.append(HI_0_100[n])
    return " ".join(out)


ZH_FIN_S = "零壹贰叁肆伍陆柒捌玖"
ZH_FIN_T = "零壹貳參肆伍陸柒捌玖"


def zh_financial(n, traditional=False):
    """Capital-form (大写) Chinese numerals: 12400 -> 壹万贰仟肆佰."""
    digits = ZH_FIN_T if traditional else ZH_FIN_S
    units = ["", "拾", "佰", "仟"]
    big = ["", "萬" if traditional else "万", "億" if traditional else "亿"]
    if n == 0:
        return digits[0]
    groups = []
    while n:
        groups.append(n % 10000)
        n //= 10000
    out = ""
    zero_pending = False
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi]
        if g == 0:
            zero_pending = True
            continue
        part = ""
        started = False
        for pos in range(3, -1, -1):
            d = g // 10 ** pos % 10
            if d:
                if zero_pending and (out or started):
                    part += digits[0]
                zero_pending = False
                part += digits[d] + units[pos]
                started = True
            elif started or out:
                zero_pending = True
        out += part + big[gi]
        zero_pending = zero_pending or g < 1000 and gi > 0 and False
    return out


KO_DIG = "영일이삼사오육칠팔구"


def korean(n):
    """Sino-Korean reading, as on receipts: 1240000 -> 일백이십사만."""
    if n == 0:
        return "영"
    units = ["", "십", "백", "천"]
    big = ["", "만", "억", "조"]
    out = ""
    gi = 0
    parts = []
    while n:
        g = n % 10000
        if g:
            part = ""
            for pos in range(3, -1, -1):
                d = g // 10 ** pos % 10
                if d:
                    part += KO_DIG[d] + units[pos]
            parts.append(part + big[gi])
        n //= 10000
        gi += 1
    return "".join(reversed(parts))


AR_UNITS = ["صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة",
            "ثمانية", "تسعة", "عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر",
            "أربعة عشر", "خمسة عشر", "ستة عشر", "سبعة عشر", "ثمانية عشر",
            "تسعة عشر"]
AR_TENS = ["", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون",
           "ثمانون", "تسعون"]
AR_HUND = ["", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة",
           "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]


def ar_below_1000(n):
    h, r = divmod(n, 100)
    parts = [AR_HUND[h]] if h else []
    if r:
        if r < 20:
            parts.append(AR_UNITS[r])
        else:
            t, u = divmod(r, 10)
            parts.append((AR_UNITS[u] + " و" if u else "") + AR_TENS[t])
    return " و".join(parts)


def arabic(n):
    if n == 0:
        return "صفر"
    parts = []
    for size, one, two, few, many in [
            (10 ** 6, "مليون", "مليونان", "ملايين", "مليون"),
            (1000, "ألف", "ألفان", "آلاف", "ألف")]:
        if n >= size:
            head = n // size
            if head == 1:
                parts.append(one)
            elif head == 2:
                parts.append(two)
            elif 3 <= head <= 10:
                parts.append(ar_below_1000(head) + " " + few)
            else:
                parts.append(ar_below_1000(head) + " " + many)
            n %= size
    if n:
        parts.append(ar_below_1000(n))
    return " و".join(parts)


def amount_in_words(rng, lang, loc, value, lex):
    """Returns the O text of an amount written in words, in the style of
    the locale (or None when the locale has no such habit)."""
    whole = int(value)
    cents = int(round((value - whole) * 100))
    cur = loc["currency"]
    country = loc["country"]
    if lang == "en":
        indian = country == "IN"
        words = english(whole, indian).title().replace(" And ", " and ")
        name = {"INR": "Rupees", "USD": "US Dollars", "GBP": "Pounds",
                "AUD": "Australian Dollars", "CAD": "Canadian Dollars",
                "NGN": "Naira"}.get(cur, cur)
        if indian:
            text = "Rupees %s" % words
            if cents:
                text += " and %s Paise" % english(cents).title()
            return text + " Only"
        return "%s %s%s only" % (words, name, " and %02d/100" % cents
                                 if cents else "")
    if lang == "fr":
        name = {"EUR": "euros", "CHF": "francs suisses", "CAD": "dollars",
                "MAD": "dirhams", "XOF": "francs CFA"}.get(cur, cur)
        text = french(whole) + " " + name
        if cents:
            text += " et %s centimes" % french(cents)
        return text
    if lang == "es":
        name = {"EUR": "euros", "MXN": "pesos", "ARS": "pesos",
                "COP": "pesos", "CLP": "pesos"}.get(cur, cur)
        text = spanish(whole).upper() + " " + name.upper()
        if cur == "MXN":
            return "(%s %02d/100 M.N.)" % (text, cents)
        return text + (" CON %02d/100" % cents if cents else "")
    if lang == "it":
        return "%s/%02d" % (italian(whole), cents)
    if lang == "ru":
        return russian_rubles(whole, cents, cur)
    if lang == "hi":
        text = "%s रुपये" % hindi(whole)
        if cents:
            text += " और %s पैसे" % hindi(cents)
        return text + " मात्र"
    if lang == "zh":
        trad = loc["data"] == "zh-Hant"
        text = zh_financial(whole, trad)
        unit = "圓" if trad else "元"
        if cents:
            jiao, fen = divmod(cents, 10)
            digits = ZH_FIN_T if trad else ZH_FIN_S
            tail = ""
            if jiao:
                tail += digits[jiao] + "角"
            if fen:
                tail += digits[fen] + "分"
            return text + unit + tail
        return text + unit + "整"
    if lang == "ko":
        return "금 %s원정" % korean(whole)
    if lang == "ar":
        name = {"SAR": "ريال سعودي", "AED": "درهم إماراتي",
                "EGP": "جنيه مصري", "MAD": "درهم"}.get(cur, cur)
        text = "فقط %s %s" % (arabic(whole), name)
        if cents:
            text += " و%s %s" % (arabic(cents),
                                 "هللة" if cur == "SAR" else "فلس"
                                 if cur == "AED" else "قرش")
        return text + " لا غير"
    return None
