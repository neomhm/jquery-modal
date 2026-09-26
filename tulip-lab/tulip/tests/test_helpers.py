"""The helpers: every case of Appendix I of the build instructions
(all MUST pass), plus the cases added while building (numbers 1001+).
Invisible characters are written as \\u escapes: case 7 has a U+202F
narrow no-break space, case 147 two U+200F right-to-left marks."""
import datetime
from datetime import time, timedelta

import helpers

datetime_ = datetime.datetime

# (number, helper, input, locale, expected); "FAIL" = (False, None)
CASES = [
    (1, 'text', '  Baguette   tradition ', 'fr-FR', 'Baguette tradition'),
    (2, 'text', 12345.0, None, '12345'),
    (3, 'text', '\uff22\uff0d\uff11\uff12', 'ja-JP', 'B-12'),
    (4, 'text', datetime_(2024, 3, 15), None, '2024-03-15'),
    (5, 'amount', 1.3, 'fr-FR', 1.3),
    (6, 'amount', '1,30 \u20ac', 'fr-FR', 1.3),
    (7, 'amount', '1\u202f240,50', 'fr-FR', 1240.5),
    (8, 'amount', '$1,240.50', 'en-US', 1240.5),
    (9, 'amount', '1.240,50 \u20ac', 'it-IT', 1240.5),
    (10, 'amount', '(120,00)', 'fr-FR', -120.0),
    (11, 'amount', '-45.00', 'en-GB', -45.0),
    (12, 'amount', '\xa51,240', 'ja-JP', 1240.0),
    (13, 'amount', '\u0661\u066c\u0662\u0664\u0660\u066b\u0665\u0660', 'ar-SA', 1240.5),
    (14, 'amount', '\u20b912,40,000', 'hi-IN', 1240000.0),
    (15, 'amount', "CHF 1'240.50", 'fr-CH', 1240.5),
    (16, 'amount', '1.240', 'es-ES', 1240.0),
    (17, 'amount', '1.240', 'en-US', 1.24),
    (18, 'amount', '1 200 \u0440\u0443\u0431.', 'ru-RU', 1200.0),
    (19, 'amount', '1,000\u4e07\u5186', 'ja-JP', 10000000.0),
    (20, 'amount', '12\uc5b5 \uc6d0', 'ko-KR', 1200000000.0),
    (21, 'amount', 'sur demande', 'fr-FR', 'FAIL'),
    (22, 'amount', '1.240', None, 'FAIL'),
    (23, 'currency', '1,30 \u20ac', 'fr-FR', 'EUR'),
    (24, 'currency', '[$\u20ac-40C] #,##0.00', 'fr-FR', 'EUR'),
    (25, 'currency', '#,##0 "\u20bd"', 'ru-RU', 'RUB'),
    (26, 'currency', 'Prix (\u20ac)', 'fr-FR', 'EUR'),
    (27, 'currency', '$12.00', 'en-US', 'USD'),
    (28, 'currency', '$12.00', 'es-MX', 'MXN'),
    (29, 'currency', '\xa51,240', 'ja-JP', 'JPY'),
    (30, 'currency', '\xa51,240', 'zh-CN', 'CNY'),
    (31, 'currency', '\u20a91,240', 'ko-KR', 'KRW'),
    (32, 'currency', 'Prix TTC', 'fr-FR', 'FAIL'),
    (33, 'currency', 1.3, 'fr-FR', 'FAIL'),
    (34, 'integer', 40, None, 40),
    (35, 'integer', 40.0, None, 40),
    (36, 'integer', '40 pcs', 'en-US', 40),
    (37, 'integer', '1 200', 'fr-FR', 1200),
    (38, 'integer', '\u0664\u0660', 'ar-EG', 40),
    (39, 'integer', 40.5, None, 'FAIL'),
    (40, 'percent', '20 %', 'fr-FR', 0.2),
    (41, 'percent', 0.2, None, 0.2),
    (42, 'percent', 20, None, 0.2),
    (43, 'percent', '5,5 %', 'fr-FR', 0.055),
    (44, 'percent', '5.5%', 'en-US', 0.055),
    (45, 'date', datetime_(2024, 3, 15), None, '2024-03-15'),
    (46, 'date', '15/03/2024', 'fr-FR', '2024-03-15'),
    (47, 'date', '03/15/2024', 'en-US', '2024-03-15'),
    (48, 'date', '2024\u5e743\u670815\u65e5', 'ja-JP', '2024-03-15'),
    (49, 'date', '\u4ee4\u548c6\u5e743\u670815\u65e5', 'ja-JP', '2024-03-15'),
    (50, 'date', '15 mars 2024', 'fr-FR', '2024-03-15'),
    (51, 'date', '15.03.2024', 'ru-RU', '2024-03-15'),
    (52, 'date', '2024-03-15 00:00:00', None, '2024-03-15'),
    (53, 'date', 'mars 2024', 'fr-FR', 'FAIL'),
    (54, 'date', '2024.03.15.', 'ko-KR', '2024-03-15'),
    (55, 'time', time(14, 30), None, '14:30'),
    (56, 'time', datetime_(2024, 3, 15, 14, 30), None, '14:30'),
    (57, 'time', '14h30', 'fr-FR', '14:30'),
    (58, 'time', '14h', 'fr-FR', '14:00'),
    (59, 'time', '2:30 PM', 'en-US', '14:30'),
    (60, 'time', '12:15 AM', 'en-US', '00:15'),
    (61, 'time', '14\u664230\u5206', 'ja-JP', '14:30'),
    (62, 'time', '\uc624\ud6c4 2\uc2dc 30\ubd84', 'ko-KR', '14:30'),
    (63, 'time', '09:30:00', None, '09:30'),
    (64, 'hours', '9h-12h / 14h-19h', 'fr-FR', '09:00-12:00, 14:00-19:00'),
    (65, 'hours', '09:00\u201318:00', 'en-GB', '09:00-18:00'),
    (66, 'hours', '9:00 AM - 5:30 PM', 'en-US', '09:00-17:30'),
    (67, 'hours', '9\u6642\u301c18\u6642', 'ja-JP', '09:00-18:00'),
    (68, 'hours', '09:00:00-12:00:00', None, '09:00-12:00'),
    (69, 'hours', 'Ferm\xe9', 'fr-FR', 'closed'),
    (70, 'hours', '\u5b9a\u4f11\u65e5', 'ja-JP', 'closed'),
    (71, 'hours', '\ud734\ubb34', 'ko-KR', 'closed'),
    (72, 'weekday', 'Lundi', 'fr-FR', 0),
    (73, 'weekday', 'Mon', 'en-US', 0),
    (74, 'weekday', '\u6708\u66dc\u65e5', 'ja-JP', 0),
    (75, 'weekday', '\u6708', 'ja-JP', 0),
    (76, 'weekday', '\u6708', 'zh-CN', 'FAIL'),
    (77, 'weekday', '\u661f\u671f\u65e5', 'zh-CN', 6),
    (78, 'weekday', '\u5468\u4e09', 'zh-CN', 2),
    (79, 'weekday', '\uc6d4', 'ko-KR', 0),
    (80, 'weekday', '\u0627\u0644\u0623\u062d\u062f', 'ar-SA', 6),
    (81, 'weekday', '\u0938\u094b\u092e\u0935\u093e\u0930', 'hi-IN', 0),
    (82, 'weekday', '\u041f\u0442', 'ru-RU', 4),
    (83, 'weekday', 's\xe1bado', 'es-ES', 5),
    (84, 'weekday', 'Domenica', 'it-IT', 6),
    (85, 'boolean', 'Oui', 'fr-FR', True),
    (86, 'boolean', 'non', 'fr-FR', False),
    (87, 'boolean', '\u2713', None, True),
    (88, 'boolean', 'x', 'fr-FR', True),
    (89, 'boolean', '\xd7', 'ja-JP', False),
    (90, 'boolean', '\u25cb', 'ja-JP', True),
    (91, 'boolean', 'X', 'ko-KR', False),
    (92, 'boolean', 'O', 'ko-KR', True),
    (93, 'boolean', '\xd7', 'fr-FR', 'FAIL'),
    (94, 'boolean', 'S\xed', 'es-ES', True),
    (95, 'boolean', '\u041d\u0435\u0442', 'ru-RU', False),
    (96, 'boolean', '\u662f', 'zh-CN', True),
    (97, 'boolean', '\uc544\ub2c8\uc694', 'ko-KR', False),
    (98, 'boolean', '\u0646\u0639\u0645', 'ar-SA', True),
    (99, 'boolean', '\u0928\u0939\u0940\u0902', 'hi-IN', False),
    (100, 'boolean', True, None, True),
    (101, 'boolean', 0, None, False),
    (102, 'boolean', 'peut-\xeatre', 'fr-FR', 'FAIL'),
    (103, 'phone', '04 50 12 34 56', 'fr-FR', '+33450123456'),
    (104, 'phone', '03-1234-5678', 'ja-JP', '+81312345678'),
    (105, 'phone', '+41 22 123 45 67', 'fr-FR', '+41221234567'),
    (106, 'phone', '12', 'fr-FR', 'FAIL'),
    (107, 'email', ' Contact@Martin.fr ', None, 'contact@martin.fr'),
    (108, 'email', 'martin.fr', None, 'FAIL'),
    (109, 'duration', '30 min', 'fr-FR', 30),
    (110, 'duration', '1h30', 'fr-FR', 90),
    (111, 'duration', '1 h 30', 'fr-FR', 90),
    (112, 'duration', 90, None, 90),
    (113, 'duration', '1:30', 'en-US', 90),
    (114, 'duration', time(1, 30), None, 90),
    (115, 'duration', '1,5 h', 'fr-FR', 90),
    (116, 'duration', '2 heures', 'fr-FR', 120),
    (117, 'duration', '45\u5206', 'ja-JP', 45),
    (118, 'duration', '1\uc2dc\uac04 30\ubd84', 'ko-KR', 90),
    (119, 'tax_included', 'Prix TTC', 'fr-FR', True),
    (120, 'tax_included', 'Prix HT', 'fr-FR', False),
    (121, 'tax_included', 'Price incl. VAT', 'en-GB', True),
    (122, 'tax_included', 'Price excl. VAT', 'en-GB', False),
    (123, 'tax_included', 'Precio IVA incluido', 'es-ES', True),
    (124, 'tax_included', 'Precio sin IVA', 'es-ES', False),
    (125, 'tax_included', 'Prezzo IVA inclusa', 'it-IT', True),
    (126, 'tax_included', 'Prezzo IVA esclusa', 'it-IT', False),
    (127, 'tax_included', '\u0426\u0435\u043d\u0430 \u0441 \u041d\u0414\u0421', 'ru-RU', True),
    (128, 'tax_included', '\u0426\u0435\u043d\u0430 \u0431\u0435\u0437 \u041d\u0414\u0421', 'ru-RU', False),
    (129, 'tax_included', '\u542b\u7a0e\u4ef7', 'zh-CN', True),
    (130, 'tax_included', '\u4e0d\u542b\u7a0e\u4ef7', 'zh-CN', False),
    (131, 'tax_included', '\u7a0e\u8fbc\u4fa1\u683c', 'ja-JP', True),
    (132, 'tax_included', '\u7a0e\u629c\u4fa1\u683c', 'ja-JP', False),
    (133, 'tax_included', '\ubd80\uac00\uc138 \ud3ec\ud568', 'ko-KR', True),
    (134, 'tax_included', '\ubd80\uac00\uc138 \ubcc4\ub3c4', 'ko-KR', False),
    (135, 'tax_included', '\u0627\u0644\u0633\u0639\u0631 \u0634\u0627\u0645\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629', 'ar-SA', True),
    (136, 'tax_included', '\u0627\u0644\u0633\u0639\u0631 \u063a\u064a\u0631 \u0634\u0627\u0645\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629', 'ar-SA', False),
    (137, 'tax_included', '\u0915\u0930 \u0938\u0939\u093f\u0924 \u092e\u0942\u0932\u094d\u092f', 'hi-IN', True),
    (138, 'tax_included', '\u0915\u0930 \u0930\u0939\u093f\u0924 \u092e\u0942\u0932\u094d\u092f', 'hi-IN', False),
    (139, 'tax_included', 'Prix', 'fr-FR', 'FAIL'),
    (140, 'boolean', '\u221a', 'zh-CN', True),
    (141, 'boolean', 'x', 'zh-CN', False),
    (142, 'boolean', '\u0445', 'ru-RU', True),
    (143, 'boolean', '+', 'ru-RU', True),
    (144, 'time', '\u5348\u5f8c2\u664230\u5206', 'ja-JP', '14:30'),
    (145, 'time', '\u4e0b\u53482:30', 'zh-CN', '14:30'),
    (146, 'time', '15/03/2024 14:30', 'fr-FR', '14:30'),
    (147, 'date', '15\u200f/3\u200f/2024', 'ar-SA', '2024-03-15'),
    (148, 'date', '1445/09/05\u0647\u0640', 'ar-SA', 'HIJRI'),
    (149, 'date', '15/03/24', 'fr-FR', '2024-03-15'),
    (150, 'date', '15/03/2024', 'zh-HK', '2024-03-15'),
    (151, 'amount', '35\u201350 \u20ac', 'fr-FR', 'FAIL'),
    (152, 'amount', 14.759999999999998, None, 14.76),
    (153, 'amount', 'CHF 1\u2019240.50', 'fr-CH', 1240.5),
    (154, 'percent', 1, None, 1.0),
    (155, 'percent', '1%', 'en-US', 0.01),
    (156, 'currency', '120 \u5143', 'zh-TW', 'TWD'),
    (157, 'currency', '120 \u0440\u0443\u0431.', 'ru-BY', 'BYN'),
    (158, 'currency', '\ufdfc 50', 'ar-SA', 'SAR'),
    (159, 'weekday', 'X', 'es-ES', 2),
    (160, 'weekday', '\u91d1', 'ko-KR', 4),
    (161, 'tax_included', 'IVA no incluido', 'es-ES', False),
    (162, 'tax_included', 'VAT not included', 'en-GB', False),
    (163, 'tax_included', 'TVA non comprise', 'fr-FR', False),
    (164, 'tax_included', '\ubd80\uac00\uc138 \ubbf8\ud3ec\ud568', 'ko-KR', False),
    (165, 'tax_included', '\u043d\u0435 \u0432\u043a\u043b\u044e\u0447\u0430\u044f \u041d\u0414\u0421', 'ru-RU', False),
    (166, 'tax_included', 'MRP', 'en-IN', True),
    (167, 'duration', timedelta(seconds=5400), None, 90),
    # added while building (section 6: date and time in one cell)
    (1001, 'date', '15/03/2024 14:30', 'fr-FR', '2024-03-15'),
    (1002, 'date', '03/15/2024 2:30 PM', 'en-US', '2024-03-15'),
    (1003, 'date', '2024年3月15日 14時30分', 'ja-JP', '2024-03-15'),
    (1004, 'amount', '1 240,50 бел. руб.', 'ru-BY', 1240.5),
    (1005, 'currency', '1 240,50 бел. руб.', 'ru-BY', 'BYN'),
    (1006, 'amount', '1,000万円', 'ja-JP', 10000000.0),
    (1007, 'integer', '5 m²', 'fr-FR', 5),
    (1008, 'integer', '12 m3', 'en-US', 12),
    (1009, 'integer', '3 x 2', 'en-US', 'FAIL'),
    (1010, 'hours', 'Fermé, Fermé', 'fr-FR', 'closed'),
    (1011, 'hours', 'Closed, 14:00-18:00', 'en-GB', '14:00-18:00'),
    (1012, 'amount', '3,000円〜', 'ja-JP', 3000.0),
    (1013, 'amount', '35元起', 'zh-CN', 35.0),
    (1014, 'boolean', '〇', 'ja-JP', True),
    (1015, 'boolean', '〇', 'fr-FR', 'FAIL'),
    (1016, 'time', '9:00 صباحاً', 'ar-SA', '09:00'),
    (1017, 'amount', '由$380起', 'zh-HK', 380.0),
    (1018, 'time', '6:00 p. m.', 'es-MX', '18:00'),
    (1019, 'hours', '9:00 a. m. - 6:00 p. m.', 'es-MX', '09:00-18:00'),
    (1020, 'hours', '9:00 a.m. - 6:00 p.m.', 'en-US', '09:00-18:00'),
    (1021, 'hours', 'de 9 a 13 y de 16 a 20', 'es-ES', 'FAIL'),
    (1022, 'hours', '9:00 a 13:00 y 16:00 a 20:00', 'es-ES', '09:00-13:00, 16:00-20:00'),
]


def _hijridate_installed():
    try:
        import hijridate                                  # noqa: F401
        return True
    except ImportError:
        return False


def _check(cases):
    wrong = []
    for number, name, value, locale, expected in cases:
        got = helpers.HELPERS[name](value, locale)
        if expected == "HIJRI":
            expected = "2024-03-15" if _hijridate_installed() else "FAIL"
        if expected == "FAIL":
            ok = got == (False, None)
        else:
            ok = got[0] is True and got[1] == expected and \
                type(got[1]) is type(expected)
        if not ok:
            wrong.append("case %s: %s(%r, %r) -> %r, expected %r"
                         % (number, name, value, locale, got, expected))
    assert not wrong, "\n" + "\n".join(wrong)


def test_appendix_i_cases():
    _check(CASES)


def test_helpers_never_raise():
    odd = [None, "", " ", object(), float("nan"), float("inf"), -1, 10 ** 30,
           b"bytes", ["list"], {"a": 1}, datetime.date(2024, 1, 1),
           "\u200f\u200e", "١٢٣", "∞", "1e999", "--", "(", "()", "%",
           "¥", "12:99", "31/02/2024", "99:00", "0/0/0"]
    for name, helper in helpers.HELPERS.items():
        for value in odd:
            for locale in (None, "fr-FR", "xx-YY", "ar", ""):
                ok, result = helper(value, locale)
                assert ok in (True, False), (name, value)
                if not ok:
                    assert result is None, (name, value, result)


def test_totals_words_cover_every_language():
    words = set(helpers.TOTALS)
    for w in ("total", "sous-total", "итого", "合计", "合計", "小计", "합계",
              "कुल", "المجموع", "totale", "subtotal"):
        assert w in words or any(x.casefold() == w for x in words), w
    assert "योग" not in words          # it also means yoga

