"""normalize.py: every case of Appendix I (they all MUST pass), plus the
spreadsheet and sanity rules of section 14.2."""
import normalize as N

# (number, label, text, lang, country, expected)
# expected: ("amount", value, currency) | ("amount_open", value, [cands])
#           ("ambiguous", [candidate values]) | ("date", y, m, d)
#           ("date_ambiguous", [iso candidates]) | ("year", y, fiscal)
#           ("count", value, qualifier, max) | ("phone", e164)
#           ("form", code, class) | ("hijri", y, m, d)
CASES = [
    (1, "REVENUE", "1 240 000 €", "fr", "FR", ("amount", 1240000, "EUR")),
    (2, "REVENUE", "1 240 000,00 €", "fr", "FR",
     ("amount", 1240000, "EUR")),
    (3, "REVENUE", "1,24 M€", "fr", "FR", ("amount", 1240000, "EUR")),
    (4, "REVENUE", "1,24 million d'euros", "fr", None,
     ("amount", 1240000, "EUR")),
    (5, "REVENUE", "2,5 milliards d'euros", "fr", None,
     ("amount", 2500000000, "EUR")),
    (6, "REVENUE", "CHF 1'240'000.–", "fr", "CH", ("amount", 1240000, "CHF")),
    (7, "REVENUE", "1 240 000,00 $", "fr", "CA", ("amount", 1240000, "CAD")),
    (8, "REVENUE", "1.240.000,00 €", "it", "IT", ("amount", 1240000, "EUR")),
    (9, "REVENUE", "€ 1.240.000", "it", None, ("amount", 1240000, "EUR")),
    (10, "REVENUE", "1,24 milioni di euro", "it", None,
     ("amount", 1240000, "EUR")),
    (11, "REVENUE", "1.240.000 €", "es", "ES", ("amount", 1240000, "EUR")),
    (12, "REVENUE", "240 mil €", "es", "ES", ("amount", 240000, "EUR")),
    (13, "REVENUE", "$1,240,000.00 MXN", "es", "MX",
     ("amount", 1240000, "MXN")),
    (14, "REVENUE", "$ 1.240.000,00", "es", "AR", ("amount", 1240000, "ARS")),
    (15, "REVENUE", "$1.240.000", "es", "CL", ("amount", 1240000, "CLP")),
    (16, "REVENUE", "1,24 millones de euros", "es", None,
     ("amount", 1240000, "EUR")),
    (17, "REVENUE", "$1,240,000", "en", "US", ("amount", 1240000, "USD")),
    (18, "REVENUE", "$1.24M", "en", "US", ("amount", 1240000, "USD")),
    (19, "REVENUE", "£1.2 million", "en", "GB", ("amount", 1200000, "GBP")),
    (20, "REVENUE", "₹12,40,000", "en", "IN", ("amount", 1240000, "INR")),
    (21, "REVENUE", "Rs. 1.24 crore", "en", "IN",
     ("amount", 12400000, "INR")),
    (22, "REVENUE", "₹ 12 लाख", "hi", "IN", ("amount", 1200000, "INR")),
    (23, "REVENUE", "१२,४०,००० रुपये", "hi", "IN",
     ("amount", 1240000, "INR")),
    (24, "REVENUE", "1,24 млн руб.", "ru", "RU", ("amount", 1240000, "RUB")),
    (25, "REVENUE", "1 240 000 ₽", "ru", "RU", ("amount", 1240000, "RUB")),
    (26, "REVENUE", "124 млн тенге", "ru", "KZ",
     ("amount", 124000000, "KZT")),
    (27, "REVENUE", "1.24亿元", "zh", "CN", ("amount", 124000000, "CNY")),
    (28, "REVENUE", "1240万元", "zh", "CN", ("amount", 12400000, "CNY")),
    (29, "REVENUE", "人民币1,240,000.00元", "zh", "CN",
     ("amount", 1240000, "CNY")),
    (30, "REVENUE", "NT$1,240,000", "zh", "TW", ("amount", 1240000, "TWD")),
    (31, "REVENUE", "新台幣124萬元", "zh", "TW", ("amount", 1240000, "TWD")),
    (32, "REVENUE", "HK$1,240,000", "zh", "HK", ("amount", 1240000, "HKD")),
    (33, "REVENUE", "1億2,400万円", "ja", "JP",
     ("amount", 124000000, "JPY")),
    (34, "REVENUE", "¥1,240,000", "ja", "JP", ("amount", 1240000, "JPY")),
    (35, "REVENUE", "１，２４０，０００円", "ja", "JP",
     ("amount", 1240000, "JPY")),
    (36, "REVENUE", "12억 4천만 원", "ko", "KR",
     ("amount", 1240000000, "KRW")),
    (37, "REVENUE", "1,240,000원", "ko", "KR", ("amount", 1240000, "KRW")),
    (38, "REVENUE", "124만 원", "ko", "KR", ("amount", 1240000, "KRW")),
    (39, "REVENUE", "١٬٢٤٠٬٠٠٠ ر.س", "ar", "SA", ("amount", 1240000, "SAR")),
    (40, "REVENUE", "1.24 مليون درهم", "ar", "AE",
     ("amount", 1240000, "AED")),
    (41, "REVENUE", "1.24 مليون درهم", "ar", "MA",
     ("amount", 1240000, "MAD")),
    (42, "REVENUE", "1.24 مليون درهم", "ar", None,
     ("amount_open", 1240000, ["AED", "MAD"])),
    (43, "REVENUE", "١٫٢٤ مليون جنيه", "ar", "EG", ("amount", 1240000, "EGP")),
    (44, "PRICE", "1.240", "es", None, ("amount", 1240, None)),
    (45, "PRICE", "1.240", "en", None, ("amount", 1.24, None)),
    (46, "PRICE", "1.240", None, None, ("ambiguous", [1240, 1.24])),
    (47, "DOC_DATE", "15/03/2024", "fr", "FR", ("date", 2024, 3, 15)),
    (48, "DOC_DATE", "03/15/2024", "en", "US", ("date", 2024, 3, 15)),
    (49, "DOC_DATE", "04/03/2024", "en", "US", ("date", 2024, 4, 3)),
    (50, "DOC_DATE", "04/03/2024", "en", "GB", ("date", 2024, 3, 4)),
    (51, "DOC_DATE", "04/03/2024", "en", None,
     ("date_ambiguous", ["2024-04-03", "2024-03-04"])),
    (52, "DOC_DATE", "15 mars 2024", "fr", None, ("date", 2024, 3, 15)),
    (53, "DOC_DATE", "15 de marzo de 2024", "es", None, ("date", 2024, 3, 15)),
    (54, "DOC_DATE", "15 marzo 2024", "it", None, ("date", 2024, 3, 15)),
    (55, "DOC_DATE", "15 марта 2024 г.", "ru", None, ("date", 2024, 3, 15)),
    (56, "DOC_DATE", "15.03.2024", "ru", None, ("date", 2024, 3, 15)),
    (57, "DOC_DATE", "2024年3月15日", "zh", None, ("date", 2024, 3, 15)),
    (58, "DOC_DATE", "令和6年3月15日", "ja", None, ("date", 2024, 3, 15)),
    (59, "FOUNDED", "令和元年5月", "ja", None, ("date", 2019, 5, None)),
    (60, "FOUNDED", "平成10年", "ja", None, ("date", 1998, None, None)),
    (61, "FOUNDED", "昭和60年", "ja", None, ("date", 1985, None, None)),
    (62, "DOC_DATE", "民國113年3月15日", "zh", "TW", ("date", 2024, 3, 15)),
    (63, "DOC_DATE", "2024년 3월 15일", "ko", None, ("date", 2024, 3, 15)),
    (64, "DOC_DATE", "2024.03.15.", "ko", None, ("date", 2024, 3, 15)),
    (65, "DOC_DATE", "15 मार्च 2024", "hi", None, ("date", 2024, 3, 15)),
    (66, "DOC_DATE", "١٥/٠٣/٢٠٢٤", "ar", "SA", ("date", 2024, 3, 15)),
    (67, "DOC_DATE", "15 مارس 2024", "ar", "EG", ("date", 2024, 3, 15)),
    (68, "DOC_DATE", "1445/09/05هـ", "ar", "SA", ("hijri", 2024, 3, 15)),
    (69, "DOC_DATE", "March 15, 2024", "en", None, ("date", 2024, 3, 15)),
    (70, "DOC_DATE", "15th March 2024", "en", None, ("date", 2024, 3, 15)),
    (71, "FOUNDED", "1998", None, None, ("date", 1998, None, None)),
    (72, "FOUNDED", "Mar. 2019", "en", None, ("date", 2019, 3, None)),
    (73, "REVENUE_YEAR", "FY2023", "en", None, ("year", 2023, None)),
    (74, "REVENUE_YEAR", "FY 2022-23", "en", "IN", ("year", 2023, "2022-23")),
    (75, "REVENUE_YEAR", "exercice 2023", "fr", None, ("year", 2023, None)),
    (76, "REVENUE_YEAR", "2023年度", "ja", None, ("year", 2023, None)),
    (77, "REVENUE_YEAR", "令和5年度", "ja", None, ("year", 2023, None)),
    (78, "REVENUE_YEAR", "2022/2023", None, None, ("year", 2023, "any")),
    (79, "STAFF", "12", "fr", None, ("count", 12, "exact", None)),
    (80, "STAFF", "25명", "ko", None, ("count", 25, "exact", None)),
    (81, "STAFF", "約50名", "ja", None, ("count", 50, "approx", None)),
    (82, "STAFF", "plus de 50", "fr", None, ("count", 50, "over", None)),
    (83, "STAFF", "50+", "en", None, ("count", 50, "over", None)),
    (84, "STAFF", "10-20", "en", None, ("count", 10, "range", 20)),
    (85, "STAFF", "10〜20名", "ja", None, ("count", 10, "range", 20)),
    (86, "STAFF", "约120人", "zh", None, ("count", 120, "approx", None)),
    (87, "STAFF", "100名以上", "ja", None, ("count", 100, "over", None)),
    (88, "S_PHONE", "+33 4 50 12 34 56", "fr", None, ("phone", "+33450123456")),
    (89, "S_PHONE", "03-1234-5678", "ja", "JP", ("phone", "+81312345678")),
    (90, "S_PHONE", "010-1234-5678", "ko", "KR", ("phone", "+821012345678")),
    (91, "S_PHONE", "+91 98765 43210", "hi", None, ("phone", "+919876543210")),
    (92, "S_PHONE", "+7 (495) 123-45-67", "ru", None,
     ("phone", "+74951234567")),
    (93, "LEGAL_FORM", "SARL", "fr", "FR", ("form", "FR_SARL", "company")),
    (94, "LEGAL_FORM", "株式会社", "ja", "JP", ("form", "JP_KK", "company")),
    (95, "LEGAL_FORM", "ИП", "ru", "RU", ("form", "RU_IP", "sole_trader")),
    (96, "LEGAL_FORM", "S.n.c.", "it", "IT", ("form", "IT_SNC", "partnership")),
    (97, "CAPITAL", "1,000万円", "ja", "JP", ("amount", 10000000, "JPY")),
    (98, "REVENUE", "12億4,000万円", "ja", "JP",
     ("amount", 1240000000, "JPY")),
    (99, "REVENUE", "$1,240 million", "en", "US",
     ("amount", 1240000000, "USD")),
    (100, "REVENUE", "1.240 millones de pesos", "es", "MX",
     ("amount", 1240000, "MXN")),
    (101, "REVENUE", "1.240 millones de euros", "es", "ES",
     ("amount", 1240000000, "EUR")),
    (102, "REVENUE", "US$ 1.240 MM", "es", "CO",
     ("amount", 1240000000, "USD")),
    (103, "REVENUE", "5 M", "es", None, ("ambiguous", [5000, 5000000])),
    (104, "REVENUE", "2 billions d'euros", "fr", None,
     ("amount", 2000000000000, "EUR")),
    (105, "PRICE", "١٬٢٤٠ ر.س", "ar", "SA", ("amount", 1240, "SAR")),
    (106, "REVENUE", "1.240.000,00 درهم", "ar", "MA",
     ("amount", 1240000, "MAD")),
    (107, "REVENUE", "1,240,000 ريال", "ar", None,
     ("amount_open", 1240000, ["SAR"])),
    (108, "LINE_TOTAL", "2220.0", "fr", "FR", ("amount", 2220, None)),
    (109, "DOC_DATE", "2024-03-15 00:00:00", None, None,
     ("date", 2024, 3, 15)),
    (110, "DOC_DATE", "04/03/2024", "en", "CA",
     ("date_ambiguous", ["2024-04-03", "2024-03-04"])),
    (111, "STAFF", "12 명", "ko", None, ("count", 12, "exact", None)),
]


def close(a, b):
    return abs(a - b) <= 1e-6 + 1e-12 * abs(b)


def check(case):
    n, label, text, lang, country, want = case
    got = N.normalize(label, text, lang, country)
    kind = want[0]
    where = "case %d %r -> %r" % (n, text, got)
    if kind == "amount":
        assert got["ok"], where
        assert close(got["value"], want[1]), where
        assert got["currency"] == want[2], where
    elif kind == "amount_open":
        assert got["ok"], where
        assert close(got["value"], want[1]), where
        assert got["currency"] is None, where
        for c in want[2]:
            assert c in got["currency_candidates"], where
    elif kind == "ambiguous":
        assert not got["ok"], where
        assert sorted(got["candidates"]) == sorted(want[1]), where
    elif kind == "date":
        assert got["ok"], where
        assert (got["year"], got["month"], got["day"]) == want[1:], where
    elif kind == "date_ambiguous":
        assert not got["ok"], where
        assert sorted(got["candidates"]) == sorted(want[1]), where
    elif kind == "hijri":
        try:
            import hijridate                          # noqa: F401
        except ImportError:
            assert not got["ok"] and got["reason"] == "hijri_unconverted", \
                where
            return
        assert got["ok"], where
        assert (got["year"], got["month"], got["day"]) == want[1:], where
    elif kind == "year":
        assert got["ok"], where
        assert got["year"] == want[1], where
        if want[2] not in (None, "any"):
            assert got["fiscal"] == want[2], where
    elif kind == "count":
        assert got["ok"], where
        assert (got["value"], got["qualifier"], got["max"]) == want[1:], \
            where
    elif kind == "phone":
        assert got["ok"] and got["e164"] == want[1], where
    elif kind == "form":
        assert got["ok"], where
        assert (got["code"], got["class"]) == want[1:], where
    else:
        raise AssertionError("unknown expectation %r" % (want,))


def test_appendix_i_all_cases():
    assert len(CASES) == 111
    assert [c[0] for c in CASES] == list(range(1, 112))
    failures = []
    for case in CASES:
        try:
            check(case)
        except AssertionError as exc:
            failures.append(str(exc))
    assert not failures, "\n".join(failures)


def test_narrow_space_is_real_character():
    assert "\u202f" in CASES[1][2]


def test_never_raises():
    for label in list(N.KIND_OF_LABEL) + ["S_NAME"]:
        for text in ["", "   ", "???", "12/34/5678", "abc 1.2.3,4,5",
                     None]:
            out = N.normalize(label, text, "fr", "FR")
            assert isinstance(out, dict) and "ok" in out


def test_spreadsheet_values():
    assert N.normalize("LINE_TOTAL", "1240000", "fr", "FR")["value"] == \
        1240000
    assert N.normalize("PRICE", "12.5", "it", "IT")["value"] == 12.5
    got = N.normalize("DOC_DATE", "2023-11-02 00:00:00", "ru", "RU")
    assert (got["year"], got["month"], got["day"]) == (2023, 11, 2)


def test_sanity_years():
    assert not N.normalize("FOUNDED", "2999", "en", "US")["ok"]
    assert not N.normalize("DOC_DATE", "15/03/1700", "fr", "FR")["ok"]


def test_reg_id_checksum():
    ok = N.normalize("S_REG_ID", "123 456 782", "fr", "FR")
    assert ok["ok"] and ok["type"] == "FR_SIREN" and \
        ok["checksum"] == "valid"
    bad = N.normalize("S_REG_ID", "123 456 783", "fr", "FR")
    assert not bad["ok"] and bad["reason"] == "checksum"


def test_url_and_email():
    u = N.normalize("S_URL", "https://www.instagram.com/boulangerie", "fr")
    assert u["host"] == "instagram.com" and u["social"] == "instagram"
    e = N.normalize("S_EMAIL", "Contact@Boulangerie-Martin.FR", "fr")
    assert e["value"] == "contact@boulangerie-martin.fr"
