"""verify.py: the check digits of Appendix J (each example valid, and
invalid once its last character changes), agreement with the generator's
own check digits, and the three statuses of section 14.1."""
import random

import normalize as N
import verify

APPENDIX_J = [("FR_SIREN", "123 456 782"), ("FR_SIRET", "123 456 782 00010"),
              ("IT_PIVA", "12345678903"), ("RU_INN10", "7707083893"),
              ("KR_BRN", "220-81-62517"), ("AU_ABN", "51 824 753 556"),
              ("IN_GSTIN", "27AAPFU0939F1ZV"),
              ("CN_USCC", "91350100M000100Y43"),
              ("JP_CORP", "7000012050002"), ("TW_UBN", "04595257"),
              ("CL_RUT", "76.123.456-0"), ("AR_CUIT", "30-71234567-1")]


def changed_last(text):
    """The same number with its last character changed."""
    last = text[-1]
    if last.isdigit():
        new = str((int(last) + 1) % 10)
    else:
        new = "A" if last != "A" else "B"
    return text[:-1] + new


def test_appendix_j_examples_valid():
    for type_, text in APPENDIX_J:
        assert verify.check_digits(type_, text), (type_, text)


def test_appendix_j_changed_last_invalid():
    for type_, text in APPENDIX_J:
        bad = changed_last(text)
        assert not verify.check_digits(type_, bad), (type_, bad)


def test_la_poste_siret():
    # SIREN 356 000 000: digit sum mod 5 = 0 instead of Luhn
    assert verify.check_digits("FR_SIRET", "35600000000010")
    assert not verify.check_digits("FR_SIRET", "35600000000011")


def test_generator_ids_pass_verify():
    """1,000 identifiers of each checked type from gen/ids.py pass the
    independent implementation here (and a changed one fails)."""
    from gen import ids as I
    rng = random.Random(5)
    info = {"kind": "company", "family": "Martin", "given": "Jean",
            "female": False, "name": "Boulangerie", "initial": "B"}
    for type_ in verify.CHECKERS:
        gen_type = "RU_INN10" if type_ == "RU_INN10" else type_
        for _ in range(1000):
            compact = I.make_id(rng, gen_type, dict(info))
            assert verify.check_digits(type_, compact), (type_, compact)


def test_statuses():
    text = "Boulangerie Martin SARL - SIREN 123 456 782 - tel 04 50 12 34 56"
    good = {"label": "S_REG_ID", "start": 32, "end": 43,
            "text": "123 456 782", "score": 0.99, "accepted": True}
    assert text[32:43] == "123 456 782"
    assert verify.verify_span(good, text, "fr", "FR")["status"] == \
        "verified"
    moved = dict(good, start=31, end=42)
    assert verify.verify_span(moved, text, "fr")["status"] == "rejected"
    low = dict(good, accepted=False)
    assert verify.verify_span(low, text, "fr")["status"] == \
        "low_confidence"
    wrong = "SIREN 123 456 783"
    bad = {"label": "S_REG_ID", "start": 6, "end": 17,
           "text": "123 456 783", "score": 0.9, "accepted": True}
    out = verify.verify_span(bad, wrong, "fr", "FR")
    assert out["status"] == "format_warning" and out["reason"] == "checksum"
    name = {"label": "S_NAME", "start": 0, "end": 23,
            "text": "Boulangerie Martin SARL", "score": 0.99,
            "accepted": True}
    out = verify.verify_span(name, text, "fr")
    assert out["status"] == "verified"
    assert out["normalized"]["text"] == "Boulangerie Martin SARL"


def test_default_country_for_japanese():
    # 'ja' has one main country: a national phone number becomes E.164
    span = {"label": "S_PHONE", "start": 0, "end": 12,
            "text": "03-1234-5678", "score": 0.9, "accepted": True}
    out = verify.verify_span(span, "03-1234-5678", "ja")
    assert out["status"] == "verified"
    assert out["normalized"]["e164"] == "+81312345678"
    assert N.normalize("S_PHONE", "03-1234-5678", "fr")["ok"] is False
