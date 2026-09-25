"""
ids.py - registration numbers with VALID check digits (Appendix J), plus
the look-alikes that must stay O: IBANs, identity-card numbers.

For every type:
    make(rng, info)  -> compact form (letters and digits only, upper case)
    show(rng, compact) -> the text as printed on a document
    valid(compact)   -> True / False (types with a check digit)

`info` is a small dict about the owner (for example {"kind": "company"}
or a person's name for an Italian codice fiscale).
"""
import string

DIG = string.digits
ALNUM = string.digits + string.ascii_uppercase


def rand_digits(rng, n, first_nonzero=False):
    out = "".join(rng.choice(DIG) for _ in range(n))
    if first_nonzero and out[0] == "0":
        out = rng.choice("123456789") + out[1:]
    return out


# ---------------------------------------------------------------------
#  check-digit algorithms
# ---------------------------------------------------------------------
def luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def luhn_complete(prefix):
    for d in DIG:
        if luhn_ok(prefix + d):
            return prefix + d
    raise ValueError(prefix)


def siret_ok(digits):
    if len(digits) != 14 or not digits.isdigit():
        return False
    if digits.startswith("356000000"):        # La Poste
        return sum(int(c) for c in digits) % 5 == 0
    return luhn_ok(digits)


def piva_ok(d):
    if len(d) != 11 or not d.isdigit():
        return False
    total = 0
    for i, ch in enumerate(d[:10]):
        n = int(ch)
        if i % 2 == 1:                  # 2nd, 4th ... (1-based even)
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(d[10])


def inn10_ok(d):
    if len(d) != 10 or not d.isdigit():
        return False
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return sum(int(a) * b for a, b in zip(d, w)) % 11 % 10 == int(d[9])


def inn12_ok(d):
    if len(d) != 12 or not d.isdigit():
        return False
    w1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    w2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    c1 = sum(int(a) * b for a, b in zip(d, w1)) % 11 % 10
    c2 = sum(int(a) * b for a, b in zip(d, w2)) % 11 % 10
    return c1 == int(d[10]) and c2 == int(d[11])


def ogrn_ok(d):
    if len(d) == 13 and d.isdigit():
        return int(d[:12]) % 11 % 10 == int(d[12])
    if len(d) == 15 and d.isdigit():
        return int(d[:14]) % 13 % 10 == int(d[14])
    return False


def kr_brn_ok(d):
    if len(d) != 10 or not d.isdigit():
        return False
    w = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    s = sum(int(a) * b for a, b in zip(d, w))
    s += int(d[8]) * 5 // 10
    return (10 - s % 10) % 10 == int(d[9])


def kr_crn_ok(d):
    if len(d) != 13 or not d.isdigit():
        return False
    s = sum(int(c) * (1 if i % 2 == 0 else 2) for i, c in enumerate(d[:12]))
    return (10 - s % 10) % 10 == int(d[12])


def abn_ok(d):
    if len(d) != 11 or not d.isdigit():
        return False
    w = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    nums = [int(c) for c in d]
    nums[0] -= 1
    return sum(a * b for a, b in zip(nums, w)) % 89 == 0


def acn_ok(d):
    if len(d) != 9 or not d.isdigit():
        return False
    w = [8, 7, 6, 5, 4, 3, 2, 1]
    s = sum(int(a) * b for a, b in zip(d, w))
    return (10 - s % 10) % 10 == int(d[8])


def gstin_check(first14):
    total = 0
    for i, ch in enumerate(first14):
        v = ALNUM.index(ch)
        p = v * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return ALNUM[(36 - total % 36) % 36]


def gstin_ok(c):
    return (len(c) == 15 and all(ch in ALNUM for ch in c) and
            gstin_check(c[:14]) == c[14])


USCC_ALPHA = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_W = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]


def uscc_check(first17):
    s = sum(USCC_ALPHA.index(ch) * w for ch, w in zip(first17, USCC_W))
    return USCC_ALPHA[(31 - s % 31) % 31]


def uscc_ok(c):
    return (len(c) == 18 and all(ch in USCC_ALPHA for ch in c) and
            uscc_check(c[:17]) == c[17])


def jp_corp_check(last12):
    # weights 1, 2, 1, 2 ... starting from the RIGHT of the 12 digits
    s = 0
    for i, ch in enumerate(reversed(last12)):
        s += int(ch) * (1 if i % 2 == 0 else 2)
    return str(9 - s % 9)


def jp_corp_ok(d):
    return len(d) == 13 and d.isdigit() and jp_corp_check(d[1:]) == d[0]


def tw_ubn_ok(d):
    if len(d) != 8 or not d.isdigit():
        return False
    w = [1, 2, 1, 2, 1, 2, 4, 1]
    s = 0
    for a, b in zip(d, w):
        p = int(a) * b
        s += p // 10 + p % 10
    if s % 5 == 0:
        return True
    return d[6] == "7" and (s + 1) % 5 == 0


def rut_dv(body):
    s, w = 0, 2
    for ch in reversed(body):
        s += int(ch) * w
        w = 2 if w == 7 else w + 1
    r = 11 - s % 11
    return "0" if r == 11 else "K" if r == 10 else str(r)


def rut_ok(c):
    return len(c) >= 2 and c[:-1].isdigit() and rut_dv(c[:-1]) == c[-1]


def cuit_check(first10):
    w = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    r = 11 - sum(int(a) * b for a, b in zip(first10, w)) % 11
    return "0" if r == 11 else "9" if r == 10 else str(r)


def cuit_ok(d):
    return len(d) == 11 and d.isdigit() and cuit_check(d[:10]) == d[10]


def nit_dv(body):
    w = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    s = sum(int(ch) * w[i] for i, ch in enumerate(reversed(body)))
    r = s % 11
    return str(11 - r) if r > 1 else str(r)


def ch_uid_check(first8):
    w = [5, 4, 3, 2, 7, 6, 5, 4]
    r = 11 - sum(int(a) * b for a, b in zip(first8, w)) % 11
    return None if r == 10 else "0" if r == 11 else str(r)


def be_ok(d):
    return len(d) == 10 and d.isdigit() and \
        97 - int(d[:8]) % 97 == int(d[8:])


def gb_vat_ok(d):
    if len(d) != 9 or not d.isdigit():
        return False
    w = [8, 7, 6, 5, 4, 3, 2]
    s = sum(int(a) * b for a, b in zip(d, w)) + int(d[7:])
    return s % 97 == 0 or (s + 55) % 97 == 0


def kz_check(first11):
    w1 = list(range(1, 12))
    s = sum(int(a) * b for a, b in zip(first11, w1)) % 11
    if s == 10:
        w2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        s = sum(int(a) * b for a, b in zip(first11, w2)) % 11
        if s == 10:
            return None
    return str(s)


def unp_check(first8):
    w = [29, 23, 19, 17, 13, 7, 5, 3]
    s = sum(int(a) * b for a, b in zip(first8, w)) % 11
    return None if s == 10 else str(s)


def es_cif_control(body7):
    even = sum(int(body7[i]) for i in (1, 3, 5))
    odd = 0
    for i in (0, 2, 4, 6):
        d = int(body7[i]) * 2
        odd += d // 10 + d % 10
    return (10 - (even + odd) % 10) % 10


DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

RFC_TABLE = {c: i for i, c in enumerate("0123456789")}
RFC_TABLE.update({c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMN")})
RFC_TABLE["&"] = 24
RFC_TABLE.update({c: 25 + i for i, c in enumerate("OPQRSTUVWXYZ")})
RFC_TABLE[" "] = 37
RFC_TABLE["Ñ"] = 38


def rfc_dv(first):
    text = first.rjust(12)
    s = sum(RFC_TABLE.get(ch, 0) * (13 - i) for i, ch in enumerate(text))
    r = 11 - s % 11
    return "0" if r == 11 else "A" if r == 10 else str(r)


CF_ODD = {**{str(i): v for i, v in enumerate(
    [1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
    **dict(zip(string.ascii_uppercase,
               [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6,
                8, 12, 14, 16, 10, 22, 25, 24, 23]))}
CF_EVEN = {**{str(i): i for i in range(10)},
           **{c: i for i, c in enumerate(string.ascii_uppercase)}}


def cf_check(first15):
    s = 0
    for i, ch in enumerate(first15):
        s += CF_ODD[ch] if i % 2 == 0 else CF_EVEN[ch]
    return string.ascii_uppercase[s % 26]


def iban_complete(country, bban):
    """Computes the two check digits of an IBAN (mod 97)."""
    moved = bban + country + "00"
    num = "".join(str(ALNUM.index(ch)) for ch in moved)
    check = 98 - int(num) % 97
    return "%s%02d%s" % (country, check, bban)


# ---------------------------------------------------------------------
#  generators and display forms, per type
# ---------------------------------------------------------------------
def spaced(text, sizes, sep=" "):
    out, pos = [], 0
    for n in sizes:
        out.append(text[pos:pos + n])
        pos += n
    if pos < len(text):
        out.append(text[pos:])
    return sep.join(p for p in out if p)


def _siren(rng):
    return luhn_complete(rand_digits(rng, 8, first_nonzero=True))


def make_id(rng, type_, info=None):
    """-> compact string of a valid identifier of this type."""
    info = info or {}
    if type_ == "FR_SIREN":
        return info.get("siren") or _siren(rng)
    if type_ == "FR_SIRET":
        siren = info.get("siren") or _siren(rng)
        nic = rng.choice(["0001", "0002", "0003", "0004"]) if \
            rng.random() < 0.8 else rand_digits(rng, 4)
        return luhn_complete(siren + nic)
    if type_ == "FR_TVA":
        siren = info.get("siren") or _siren(rng)
        key = (12 + 3 * (int(siren) % 97)) % 97
        return "FR%02d%s" % (key, siren)
    if type_ == "IT_PIVA":
        while True:
            body = rand_digits(rng, 7, first_nonzero=False) + \
                rng.choice(["001", "015", "017", "037", "048", "058",
                            "063", "081", "097", "108"])
            for d in DIG:
                if piva_ok(body + d):
                    return body + d
    if type_ == "IT_CF":
        if info.get("kind") == "company" and info.get("piva"):
            return info["piva"]
        return _codice_fiscale(rng, info)
    if type_ == "IT_REA":
        return info.get("prov", rng.choice(["MI", "RM", "TO", "NA", "BO",
                                            "FI", "VR", "PD"])) + \
            rand_digits(rng, rng.choice([6, 7]), True)
    if type_ == "RU_INN":
        if info.get("kind") == "sole_trader":
            return _inn12(rng, info.get("region"))
        return _inn10(rng, info.get("region"))
    if type_ == "RU_INN10":
        return _inn10(rng, info.get("region"))
    if type_ == "RU_INN12":
        return _inn12(rng, info.get("region"))
    if type_ == "RU_OGRN":
        if info.get("kind") == "sole_trader":
            body = "3" + rand_digits(rng, 13)
            return body + str(int(body) % 13 % 10)
        body = rng.choice(["1", "5"]) + rand_digits(rng, 11)
        return body + str(int(body) % 11 % 10)
    if type_ == "RU_KPP":
        region = info.get("region") or rand_digits(rng, 2, True)
        return region + rand_digits(rng, 2) + "01" + "001"
    if type_ == "KR_BRN":
        mid = rng.choice(["81", "86", "87", "88"]) if \
            info.get("kind") == "company" else "%02d" % rng.randint(1, 79)
        while True:
            body = rand_digits(rng, 3, True) + mid + rand_digits(rng, 4)
            for d in DIG:
                if kr_brn_ok(body + d):
                    return body + d
    if type_ == "KR_CRN":
        body = rng.choice(["110111", "110114", "131111", "134511",
                           "180111", "200111"]) + rand_digits(rng, 6)
        for d in DIG:
            if kr_crn_ok(body + d):
                return body + d
    if type_ == "AU_ABN":
        while True:
            tail = rand_digits(rng, 9)
            for head in range(10, 100):
                cand = str(head) + tail
                if abn_ok(cand):
                    return cand
    if type_ == "AU_ACN":
        body = rand_digits(rng, 8)
        for d in DIG:
            if acn_ok(body + d):
                return body + d
    if type_ == "IN_PAN":
        entity = "C" if info.get("kind") == "company" else \
            "F" if info.get("kind") == "partnership" else "P"
        letter = info.get("initial") or rng.choice(string.ascii_uppercase)
        return ("".join(rng.choice(string.ascii_uppercase) for _ in range(3))
                + entity + letter + rand_digits(rng, 4) +
                rng.choice(string.ascii_uppercase))
    if type_ == "IN_GSTIN":
        state = info.get("state_code") or rng.choice(
            ["27", "29", "07", "33", "24", "09", "19", "36", "06", "32"])
        pan = info.get("pan") or make_id(rng, "IN_PAN", info)
        first14 = state + pan + rng.choice("123") + "Z"
        return first14 + gstin_check(first14)
    if type_ == "IN_CIN":
        return ("U" + rand_digits(rng, 5, True) +
                info.get("state_abbr", rng.choice(["MH", "KA", "DL", "TN",
                                                   "GJ", "UP", "WB", "TG"]))
                + str(rng.randint(1995, 2024)) +
                rng.choice(["PTC", "PTC", "PLC"]) + rand_digits(rng, 6))
    if type_ == "IN_UDYAM":
        return ("UDYAM" + info.get("state_abbr", rng.choice(
            ["MH", "KA", "DL", "TN", "GJ", "UP"])) + "%02d" %
            rng.randint(1, 40) + rand_digits(rng, 7))
    if type_ == "CN_USCC":
        # 91 = enterprise, 92 = individual business (个体工商户),
        # 93 = farmers' cooperative
        kind = (info or {}).get("kind")
        second = "2" if kind == "sole_trader" else "1" \
            if kind in ("company", "partnership") else rng.choice("1123")
        first = "9" + second + \
            rng.choice(["110108", "310115", "440300", "330106", "320102",
                        "510107", "420106", "350100", "370102", "120116"])
        org = "".join(rng.choice(USCC_ALPHA) for _ in range(9))
        first17 = first + org
        return first17 + uscc_check(first17)
    if type_ == "JP_CORP":
        last12 = rand_digits(rng, 12)
        return jp_corp_check(last12) + last12
    if type_ == "JP_TNUM":
        return "T" + (info.get("corp") or make_id(rng, "JP_CORP"))
    if type_ == "TW_UBN":
        while True:
            body = rand_digits(rng, 7)
            for d in DIG:
                if tw_ubn_ok(body + d):
                    return body + d
    if type_ == "CL_RUT":
        body = str(rng.randint(76000000, 77999999)) if \
            info.get("kind") != "sole_trader" else \
            str(rng.randint(6000000, 22000000))
        return body + rut_dv(body)
    if type_ == "AR_CUIT":
        prefix = rng.choice(["30", "33", "30"]) if \
            info.get("kind") != "sole_trader" else rng.choice(["20", "27",
                                                               "23"])
        first10 = prefix + rand_digits(rng, 8, True)
        return first10 + cuit_check(first10)
    if type_ == "CO_NIT":
        body = str(rng.randint(800000000, 901999999)) if \
            info.get("kind") != "sole_trader" else \
            str(rng.randint(10000000, 1099999999))
        return body + nit_dv(body)
    if type_ == "ES_NIF":
        if info.get("kind") == "sole_trader":
            num = rng.randint(10000000, 79999999)
            return "%08d%s" % (num, DNI_LETTERS[num % 23])
        letter = rng.choice("BBBBAB")
        body = rand_digits(rng, 7)
        return letter + body + str(es_cif_control(body))
    if type_ == "MX_RFC":
        return _rfc(rng, info)
    if type_ == "GB_CRN":
        if rng.random() < 0.1:
            return rng.choice(["SC", "NI"]) + rand_digits(rng, 6)
        return "%08d" % rng.randint(1000000, 15999999)
    if type_ == "GB_VAT":
        while True:
            body = rand_digits(rng, 7, True)
            for c in range(97):
                cand = body + "%02d" % c
                if gb_vat_ok(cand):
                    return cand
    if type_ == "CA_BN":
        return luhn_complete(rand_digits(rng, 8, True))
    if type_ == "CA_NEQ":
        return rng.choice(["114", "116", "117", "118", "224"]) + \
            rand_digits(rng, 7)
    if type_ == "CA_TPS":
        return (info.get("bn") or make_id(rng, "CA_BN")) + "RT0001"
    if type_ == "CA_TVQ":
        return rand_digits(rng, 10, True) + "TQ0001"
    if type_ in ("CH_UID", "CH_TVA"):
        while True:
            body = rand_digits(rng, 8, True)
            c = ch_uid_check(body)
            if c is not None:
                return "CHE" + body + c
    if type_ in ("BE_BCE", "BE_TVA"):
        first8 = rng.choice("01") + rand_digits(rng, 7)
        if first8[0] == "0":
            first8 = "0" + rng.choice("45678") + first8[2:]
        d = first8 + "%02d" % (97 - int(first8) % 97)
        return ("BE" + d) if type_ == "BE_TVA" else d
    if type_ == "SA_CR":
        return rng.choice(["1010", "4030", "2050", "1131", "5855"]) + \
            rand_digits(rng, 6)
    if type_ == "SA_VAT":
        return "3" + rand_digits(rng, 13) + "3"
    if type_ == "AE_TRN":
        return "100" + rand_digits(rng, 12)
    if type_ == "AE_LICENSE":
        return rand_digits(rng, rng.choice([6, 7]), True)
    if type_ == "EG_CR":
        return rand_digits(rng, rng.choice([5, 6]), True)
    if type_ == "EG_TAX":
        return rand_digits(rng, 9, True)
    if type_ == "MA_ICE":
        return "00" + rand_digits(rng, 13)
    if type_ == "MA_RC":
        return rand_digits(rng, rng.choice([5, 6]), True)
    if type_ == "MA_IF":
        return rand_digits(rng, rng.choice([7, 8]), True)
    if type_ == "MA_PATENTE":
        return rand_digits(rng, 8, True)
    if type_ == "MA_CNSS":
        return rand_digits(rng, 7, True)
    if type_ == "SN_NINEA":
        return "00" + rand_digits(rng, 7) + rng.choice("123") + \
            rng.choice("ABCGVY") + rng.choice("123")
    if type_ == "SN_RCCM":
        return "SN" + rng.choice(["DKR", "THS", "SLO", "KLK"]) + \
            str(rng.randint(2005, 2024)) + rng.choice("AB") + \
            rand_digits(rng, 5, True)
    if type_ == "BY_UNP":
        while True:
            body = rng.choice("12345679") + rand_digits(rng, 7)
            c = unp_check(body)
            if c is not None:
                return body + c
    if type_ in ("KZ_BIN", "KZ_IIN"):
        while True:
            if type_ == "KZ_BIN":
                body = "%02d%02d" % (rng.randint(0, 24), rng.randint(1, 12)) \
                    + rng.choice("456") + rng.choice("0124") + \
                    rand_digits(rng, 5)
            else:
                y, m, d = rng.randint(60, 99), rng.randint(1, 12), \
                    rng.randint(1, 28)
                body = "%02d%02d%02d" % (y, m, d) + rng.choice("3456") + \
                    rand_digits(rng, 4)
            c = kz_check(body)
            if c is not None:
                return body + c
    if type_ == "US_EIN":
        return rng.choice(["12", "20", "26", "27", "30", "33", "36", "45",
                           "46", "47", "52", "81", "83", "84", "86", "88"]) \
            + rand_digits(rng, 7)
    if type_ == "US_STATE":
        if rng.random() < 0.5:
            return rand_digits(rng, 7, True)
        return rng.choice("CLP") + rand_digits(rng, 7, True)
    if type_ == "NG_RC":
        return rand_digits(rng, rng.choice([6, 7]), True)
    if type_ == "NG_TIN":
        return rand_digits(rng, 8, True) + "0001"
    if type_ == "HK_BR":
        return rand_digits(rng, 8, True)
    if type_ == "HK_CR":
        return rand_digits(rng, 7, True)
    if type_ == "SG_UEN":
        if rng.random() < 0.6:
            return str(rng.randint(2000, 2024)) + rand_digits(rng, 5) + \
                rng.choice("CDEGHKMNRWZ")
        return "53" + rand_digits(rng, 6) + rng.choice("ABCDEJKLMWX")
    raise KeyError(type_)


def _inn10(rng, region=None):
    region = region or rng.choice(["77", "78", "50", "66", "16", "54",
                                   "23", "52", "63", "61"])
    body = region + rand_digits(rng, 7)
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return body + str(sum(int(a) * b for a, b in zip(body, w)) % 11 % 10)


def _inn12(rng, region=None):
    region = region or rng.choice(["77", "78", "50", "66", "16", "54"])
    body = region + rand_digits(rng, 8)
    w1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    c1 = str(sum(int(a) * b for a, b in zip(body, w1)) % 11 % 10)
    body += c1
    w2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    return body + str(sum(int(a) * b for a, b in zip(body, w2)) % 11 % 10)


def _letters(name, n, family=True):
    import unicodedata
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", name.upper())
                    if ch in string.ascii_uppercase)
    cons = [c for c in plain if c not in "AEIOU"]
    vows = [c for c in plain if c in "AEIOU"]
    if not family and len(cons) >= 4:
        cons = [cons[0], cons[2], cons[3]]
    out = (cons + vows + ["X", "X", "X"])[:n]
    return "".join(out)


def _codice_fiscale(rng, info):
    family = info.get("family", "Rossi")
    given = info.get("given", "Mario")
    female = info.get("female", False)
    year = rng.randint(1950, 2000)
    month = "ABCDEHLMPRST"[rng.randint(0, 11)]
    day = rng.randint(1, 28) + (40 if female else 0)
    town = rng.choice("ABCDEFGHILM") + rand_digits(rng, 3)
    first15 = (_letters(family, 3) + _letters(given, 3, family=False) +
               "%02d" % (year % 100) + month + "%02d" % day + town)
    return first15 + cf_check(first15)


def _rfc(rng, info):
    import unicodedata
    letters = string.ascii_uppercase
    if info.get("kind") == "sole_trader":
        head = "".join(rng.choice(letters) for _ in range(4))
        date = "%02d%02d%02d" % (rng.randint(60, 99), rng.randint(1, 12),
                                 rng.randint(1, 28))
    else:
        name = info.get("name", "")
        plain = "".join(ch for ch in unicodedata.normalize(
            "NFKD", name.upper()) if ch in letters)
        head = (plain + "".join(rng.choice(letters) for _ in range(3)))[:3]
        date = "%02d%02d%02d" % (rng.randint(0, 24), rng.randint(1, 12),
                                 rng.randint(1, 28))
    homo = rng.choice(letters + DIG) + rng.choice(letters + DIG)
    first = head + date + homo
    return first + rfc_dv(first)


def show(rng, type_, c):
    """How a compact identifier is printed. Several real-life styles."""
    r = rng.random()
    if type_ == "FR_SIREN":
        return spaced(c, [3, 3, 3]) if r < 0.7 else c
    if type_ == "FR_SIRET":
        if r < 0.55:
            return spaced(c, [3, 3, 3, 5])
        if r < 0.7:
            return spaced(c, [3, 3, 3, 3, 2])
        return c
    if type_ == "FR_TVA":
        return c if r < 0.5 else "%s %s %s" % (c[:2], c[2:4],
                                              spaced(c[4:], [3, 3, 3]))
    if type_ == "IT_PIVA":
        return ("IT" + c) if r < 0.25 else c
    if type_ == "IT_REA":
        return c[:2] + ("-" if r < 0.7 else " ") + c[2:]
    if type_ in ("RU_INN", "RU_INN10", "RU_INN12", "RU_OGRN", "RU_KPP",
                 "KZ_BIN", "KZ_IIN", "BY_UNP", "JP_CORP", "TW_UBN",
                 "CN_USCC", "IN_GSTIN", "IN_PAN", "IN_CIN", "SA_CR",
                 "SA_VAT", "AE_TRN", "AE_LICENSE", "EG_CR", "MA_ICE",
                 "MA_RC", "MA_IF", "MA_PATENTE", "MA_CNSS", "HK_BR",
                 "HK_CR", "SG_UEN", "NG_RC", "US_STATE", "MX_RFC",
                 "JP_TNUM", "GB_CRN"):
        if type_ == "JP_CORP" and r < 0.2:
            return spaced(c, [1, 4, 4, 4], "-")
        if type_ == "HK_BR" and r < 0.3:
            return c + "-000"
        if type_ == "SA_VAT" and r < 0.2:
            return spaced(c, [3, 4, 4, 4])
        return c
    if type_ == "IN_UDYAM":
        return "%s-%s-%s-%s" % (c[:5], c[5:7], c[7:9], c[9:])
    if type_ == "KR_BRN":
        return spaced(c, [3, 2, 5], "-")
    if type_ == "KR_CRN":
        return spaced(c, [6, 7], "-")
    if type_ == "AU_ABN":
        return spaced(c, [2, 3, 3, 3]) if r < 0.8 else c
    if type_ == "AU_ACN":
        return spaced(c, [3, 3, 3]) if r < 0.8 else c
    if type_ == "CL_RUT":
        body, dv = c[:-1], c[-1]
        if r < 0.75:
            return group_dots(body) + "-" + dv
        return body + "-" + dv
    if type_ == "AR_CUIT":
        return spaced(c, [2, 8, 1], "-") if r < 0.85 else c
    if type_ == "CO_NIT":
        body, dv = c[:-1], c[-1]
        return (group_dots(body) if r < 0.7 else body) + "-" + dv
    if type_ == "ES_NIF":
        return c if r < 0.7 else (c[0] + "-" + c[1:] if c[0].isalpha()
                                  else c[:-1] + "-" + c[-1])
    if type_ == "GB_VAT":
        return ("GB " + spaced(c, [3, 4, 2])) if r < 0.6 else ("GB" + c)
    if type_ == "CA_BN":
        return c if r < 0.5 else c + " RT0001"
    if type_ in ("CA_TPS", "CA_TVQ"):
        return c[:-6] + " " + c[-6:] if r < 0.7 else c
    if type_ == "CA_NEQ":
        return c
    if type_ in ("CH_UID", "CH_TVA"):
        return "CHE-%s.%s.%s" % (c[3:6], c[6:9], c[9:12])
    if type_ == "BE_BCE":
        return "%s.%s.%s" % (c[:4], c[4:7], c[7:]) if r < 0.7 else \
            "%s %s %s" % (c[:4], c[4:7], c[7:])
    if type_ == "BE_TVA":
        d = c[2:]
        return "BE%s.%s.%s" % (d[:4], d[4:7], d[7:]) if r < 0.5 else \
            "BE %s %s %s" % (d[:4], d[4:7], d[7:])
    if type_ == "EG_TAX":
        return spaced(c, [3, 3, 3], "-")
    if type_ == "US_EIN":
        return c[:2] + "-" + c[2:]
    if type_ == "NG_TIN":
        return c[:8] + "-" + c[8:]
    if type_ == "SN_NINEA":
        return c[:9] + " " + c[9:]
    if type_ == "SN_RCCM":
        return "%s-%s-%s-%s-%s" % (c[:2], c[2:5], c[5:9], c[9], c[10:])
    if type_ == "IT_CF":
        return c
    return c


def group_dots(digits):
    out = []
    while len(digits) > 3:
        out.insert(0, digits[-3:])
        digits = digits[:-3]
    out.insert(0, digits)
    return ".".join(out)


# ---------------------------------------------------------------------
#  validators, for the types of Appendix J (plus a few more)
# ---------------------------------------------------------------------
VALIDATORS = {
    "FR_SIREN": lambda c: len(c) == 9 and c.isdigit() and luhn_ok(c),
    "FR_SIRET": siret_ok,
    "IT_PIVA": piva_ok,
    "RU_INN10": inn10_ok,
    "RU_INN12": inn12_ok,
    "RU_OGRN": ogrn_ok,
    "KR_BRN": kr_brn_ok,
    "KR_CRN": kr_crn_ok,
    "AU_ABN": abn_ok,
    "AU_ACN": acn_ok,
    "IN_GSTIN": gstin_ok,
    "CN_USCC": uscc_ok,
    "JP_CORP": jp_corp_ok,
    "JP_TNUM": lambda c: c[:1] == "T" and jp_corp_ok(c[1:]),
    "TW_UBN": tw_ubn_ok,
    "CL_RUT": rut_ok,
    "AR_CUIT": cuit_ok,
    "CO_NIT": lambda c: len(c) >= 2 and c.isdigit() and
    nit_dv(c[:-1]) == c[-1],
    "CH_UID": lambda c: len(c) == 12 and c[:3] == "CHE" and c[3:].isdigit()
    and ch_uid_check(c[3:11]) == c[11],
    "BE_BCE": be_ok,
    "BE_TVA": lambda c: c[:2] == "BE" and be_ok(c[2:]),
    "GB_VAT": gb_vat_ok,
    "CA_BN": lambda c: len(c) == 9 and c.isdigit() and luhn_ok(c),
    "FR_TVA": lambda c: len(c) == 13 and c[:2] == "FR" and c[2:].isdigit()
    and int(c[2:4]) == (12 + 3 * (int(c[4:]) % 97)) % 97,
    "KZ_BIN": lambda c: len(c) == 12 and c.isdigit() and
    kz_check(c[:11]) == c[11],
    "KZ_IIN": lambda c: len(c) == 12 and c.isdigit() and
    kz_check(c[:11]) == c[11],
    "BY_UNP": lambda c: len(c) == 9 and c.isdigit() and
    unp_check(c[:8]) == c[8],
}


def validate(type_, compact):
    """True / False, or None when the type has no check digit."""
    fn = VALIDATORS.get(type_)
    if fn is None:
        return None
    try:
        return bool(fn(compact))
    except (ValueError, IndexError, KeyError):
        return False


# ---------------------------------------------------------------------
#  look-alikes that are always O
# ---------------------------------------------------------------------
IBAN_BBAN = {"FR": (10, 11, 2), "BE": (12,), "CH": (17,), "IT": (1, 22),
             "ES": (20,), "SA": (22,), "AE": (19,), "EG": (25,),
             "MA": (24,), "GB": (4, 14), "KZ": (16,), "BY": (4, 20)}


def iban(rng, country):
    """A well-formed IBAN for countries that use them (else None)."""
    parts = IBAN_BBAN.get(country)
    if not parts:
        return None
    if country == "IT":
        bban = rng.choice(string.ascii_uppercase) + rand_digits(rng, 22)
    elif country == "GB":
        bban = rng.choice(["NWBK", "BARC", "LOYD", "HBUK", "MIDL"]) + \
            rand_digits(rng, 14)
    elif country == "BY":
        bban = rng.choice(["AKBB", "BLBB", "BPSB"]) + rand_digits(rng, 20)
    else:
        bban = rand_digits(rng, sum(parts))
    return iban_complete(country, bban)


def show_iban(rng, code):
    if rng.random() < 0.6:
        return " ".join(code[i:i + 4] for i in range(0, len(code), 4))
    return code


def personal_id(rng, country):
    """An identity-card / passport style number (always O, rule R7)."""
    r = rng.random
    if country == "KR":
        return "%02d%02d%02d-%s%s" % (rng.randint(60, 99), rng.randint(1, 12),
                                      rng.randint(1, 28), rng.choice("12"),
                                      rand_digits(rng, 6))
    if country == "CN":
        return rng.choice(["110101", "310104", "440305"]) + \
            "%d%02d%02d" % (rng.randint(1960, 2000), rng.randint(1, 12),
                            rng.randint(1, 28)) + rand_digits(rng, 3) + \
            rng.choice(DIG + "X")
    if country == "IN":
        return "%s %s %s" % (rand_digits(rng, 4, True), rand_digits(rng, 4),
                             rand_digits(rng, 4))
    if country == "US":
        return "%s-%s-%s" % (rand_digits(rng, 3, True), rand_digits(rng, 2),
                             rand_digits(rng, 4))
    if country == "AE":
        return "784-%d-%s-%s" % (rng.randint(1960, 2000), rand_digits(rng, 7),
                                 rng.choice(DIG))
    if country in ("RU", "KZ", "BY"):
        return "%s %s %s" % (rand_digits(rng, 2, True), rand_digits(rng, 2),
                             rand_digits(rng, 6))
    if country == "ES":
        num = rng.randint(10000000, 79999999)
        return "%08d%s" % (num, DNI_LETTERS[num % 23])
    if country == "JP":
        return "%s%s" % (rng.choice(["TK", "TR", "TZ"]), rand_digits(rng, 7))
    if country in ("SA", "EG", "MA", "TW", "HK"):
        return rng.choice(["1", "2"]) + rand_digits(rng, 9) if r() < 0.5 \
            else rng.choice(string.ascii_uppercase) + rand_digits(rng, 9)
    return "%s%s" % ("".join(rng.choice(string.ascii_uppercase)
                             for _ in range(2)), rand_digits(rng, 7))
