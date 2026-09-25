"""
verify.py - checks every span that extract() returns (section 14.1).

Three checks, in order:
  1. Source check (hard): chunk_text[start:end] must equal the span's
     text, otherwise the span is 'rejected' (a bug, must never happen).
  2. Confidence: a span the model did not accept is 'low_confidence'
     (stored, never used by the profile).
  3. Format (soft): normalize() reads the value. Success -> 'verified'
     with the value; failure -> 'format_warning' with the reason. A
     registration number whose check digit fails gets 'format_warning'
     with the reason 'checksum'.

The check-digit algorithms of Appendix J live here, written from the
build instructions and independently of the generator (gen/ids.py), so
that each one checks the other (tests/test_verify.py).
"""
import re

import normalize as N

# languages with one main country: verify passes it to normalize()
DEFAULT_COUNTRY = {"ja": "JP", "ko": "KR", "hi": "IN", "it": "IT"}


# =====================================================================
#  check digits (Appendix J)
# =====================================================================
def luhn_ok(digits):
    total = 0
    for k, ch in enumerate(reversed(digits)):
        d = int(ch)
        if k % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def siren_ok(c):
    return len(c) == 9 and c.isdigit() and luhn_ok(c)


def siret_ok(c):
    if len(c) != 14 or not c.isdigit():
        return False
    if c.startswith("356000000"):             # La Poste
        return sum(int(ch) for ch in c) % 5 == 0
    return luhn_ok(c)


def piva_ok(c):
    c = c[2:] if c.startswith("IT") else c
    if len(c) != 11 or not c.isdigit():
        return False
    total = 0
    for k, ch in enumerate(c[:10]):
        d = int(ch)
        if k % 2 == 1:                        # 2nd, 4th ... positions
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(c[10])


def inn10_ok(c):
    if len(c) != 10 or not c.isdigit():
        return False
    weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    total = sum(int(c[k]) * w for k, w in enumerate(weights))
    return total % 11 % 10 == int(c[9])


def kr_brn_ok(c):
    if len(c) != 10 or not c.isdigit():
        return False
    weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    total = sum(int(c[k]) * w for k, w in enumerate(weights))
    total += int(c[8]) * 5 // 10
    return (10 - total % 10) % 10 == int(c[9])


def abn_ok(c):
    if len(c) != 11 or not c.isdigit():
        return False
    digits = [int(ch) for ch in c]
    digits[0] -= 1
    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    return sum(d * w for d, w in zip(digits, weights)) % 89 == 0


B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_ok(c):
    if len(c) != 15 or any(ch not in B36 for ch in c):
        return False
    total = 0
    for k, ch in enumerate(c[:14]):
        product = B36.index(ch) * (1 if k % 2 == 0 else 2)
        total += product // 36 + product % 36
    return B36[(36 - total % 36) % 36] == c[14]


USCC = "0123456789ABCDEFGHJKLMNPQRTUWXY"


def uscc_ok(c):
    if len(c) != 18 or any(ch not in USCC for ch in c):
        return False
    weights = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30,
               28]
    total = sum(USCC.index(c[k]) * w for k, w in enumerate(weights))
    return USCC[(31 - total % 31) % 31] == c[17]


def jp_corp_ok(c):
    if len(c) != 13 or not c.isdigit():
        return False
    rest = c[1:]
    total = 0
    for k, ch in enumerate(reversed(rest)):
        total += int(ch) * (1 if k % 2 == 0 else 2)
    return 9 - total % 9 == int(c[0])


def tw_ubn_ok(c):
    if len(c) != 8 or not c.isdigit():
        return False
    weights = [1, 2, 1, 2, 1, 2, 4, 1]
    total = 0
    for ch, w in zip(c, weights):
        total += sum(int(x) for x in str(int(ch) * w))
    return total % 5 == 0 or (c[6] == "7" and (total + 1) % 5 == 0)


def rut_ok(c):
    c = c.upper()
    if not re.fullmatch(r"\d{7,8}[0-9K]", c):
        return False
    body, dv = c[:-1], c[-1]
    total = 0
    for k, ch in enumerate(reversed(body)):
        total += int(ch) * (2 + k % 6)
    check = 11 - total % 11
    expected = "0" if check == 11 else "K" if check == 10 else str(check)
    return dv == expected


def cuit_ok(c):
    if len(c) != 11 or not c.isdigit():
        return False
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(c[k]) * w for k, w in enumerate(weights))
    check = 11 - total % 11
    check = 0 if check == 11 else 9 if check == 10 else check
    return check == int(c[10])


CHECKERS = {"FR_SIREN": siren_ok, "FR_SIRET": siret_ok, "IT_PIVA": piva_ok,
            "RU_INN10": inn10_ok, "KR_BRN": kr_brn_ok, "AU_ABN": abn_ok,
            "IN_GSTIN": gstin_ok, "CN_USCC": uscc_ok, "JP_CORP": jp_corp_ok,
            "TW_UBN": tw_ubn_ok, "CL_RUT": rut_ok, "AR_CUIT": cuit_ok}


def check_digits(type_, compact):
    """True when the check digit of an Appendix J type is right (types
    without an algorithm here are always True)."""
    fn = CHECKERS.get(type_)
    if fn is None:
        return True
    try:
        return bool(fn(N.compact_id(compact)))
    except (ValueError, IndexError):
        return False


# =====================================================================
#  one span
# =====================================================================
def verify_span(span, chunk_text, lang=None, country=None):
    """span: a dict of extract() ('label', 'start', 'end', 'text',
    'score', 'accepted'). -> {'status', 'normalized', 'reason'}."""
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or \
            chunk_text[start:end] != span.get("text"):
        return {"status": "rejected", "normalized": None,
                "reason": "source_mismatch"}
    if country is None:
        country = DEFAULT_COUNTRY.get(lang)
    value = N.normalize(span["label"], span["text"], lang, country)
    if not span.get("accepted", True):
        return {"status": "low_confidence", "normalized": value,
                "reason": "below_threshold"}
    if value.get("ok"):
        return {"status": "verified", "normalized": value, "reason": None}
    return {"status": "format_warning", "normalized": value,
            "reason": value.get("reason")}


def verify_chunk(result, chunk_text, country=None):
    """Verifies every span of one extract() result (in place: adds
    'status', 'normalized' and 'reason' to each span)."""
    lang = result.get("language")
    for span in result.get("spans", []):
        span.update(verify_span(span, chunk_text, lang, country))
    return result
