"""profile.py: the invariant of 15.9 (every value shown is the exact text
of one of its sources, or its normalization), name clusters (15.3) and
revenue-year pairing (15.7). The folders are generated here, in memory,
and the TRUE spans are fed through extract_db -> verify -> profile, so
these tests never depend on a trained model."""
import copy

import evaluate as E
import extract_db
import profile as PR


def _profile_of(split, index, locale=None):
    import gen.layouts                                   # noqa: F401
    from gen import make
    chunks, truth = make.make_folder(split, index, locale=locale)
    db, _ = extract_db.build_folder_db(chunks)
    extract_db.process(db, E.GoldExtractor(chunks), "gold",
                       log=lambda *a: None)
    return db, PR.build(db, "gold"), truth


def test_invariant_holds_on_generated_folders():
    for index, locale in ((0, "fr-FR"), (1, "ja-JP"), (2, "ar-SA"),
                          (3, "hi-IN"), (4, "ru-RU"), (5, "es-MX")):
        db, prof, truth = _profile_of("test_profile", index, locale)
        problems = PR.check_invariant(prof, db)
        assert problems == [], (locale, problems)
        assert prof["summary"]["found"] >= 5, (locale, prof["summary"])


def test_invariant_catches_an_invented_value():
    db, prof, _ = _profile_of("test_profile", 0, "fr-FR")
    bad = copy.deepcopy(prof)
    field = next(name for name, f in bad["fields"].items()
                 if isinstance(f.get("value"), dict) and
                 f["value"].get("text") and name not in ("country",
                                                         "business_name"))
    bad["fields"][field]["value"]["text"] += " (invented)"
    assert PR.check_invariant(bad, db) != []


def test_business_found_from_its_documents():
    ok = 0
    for index in range(8):
        db, prof, truth = _profile_of("test_profile", 10 + index)
        res, _ = E.compare_folder(prof, truth)
        ok += res["business_name"]
    assert ok >= 7


def test_name_keys():
    assert PR.name_key("Boulangerie Martin SARL") == \
        PR.name_key("BOULANGERIE MARTIN")
    assert PR.name_key("株式会社サクラ商事") == PR.name_key("サクラ商事")
    assert PR.same_organisation(PR.name_key("サクラ商事"),
                                PR.name_key("サクラ商事株式会社 東京支店"))
    assert not PR.same_organisation(PR.name_key("Martin"),
                                    PR.name_key("Dupont"))


class _Span:
    def __init__(self, chunk_id, start, end, text, year=None):
        self.chunk_id, self.start, self.end, self.text = (chunk_id, start,
                                                          end, text)
        self.norm = {"ok": True, "kind": "year", "year": year} if year \
            else {}


def test_revenue_pairing_rules():
    text = ("Chiffre d'affaires\n2023 2022\n1 240 000 € 1 100 000 €\n"
            "Exercice 2021 : 950 000 €")
    chunks = {1: (1, 1, 0, "text", text)}

    def at(value, year=None, start=0):
        s = text.index(value, start)
        return _Span(1, s, s + len(value), value, year)
    y23, y22 = at("2023", 2023), at("2022", 2022)
    y21 = at("2021", 2021, text.index("Exercice"))
    r1, r2 = at("1 240 000 €"), at("1 100 000 €")
    r3 = at("950 000 €")
    pairs = dict((r.text, y.text if y else None) for r, y in
                 PR.pair_revenue([r1, r2, r3], [y23, y22, y21], chunks))
    assert pairs["1 240 000 €"] == "2023"        # rule 3, in order
    assert pairs["1 100 000 €"] == "2022"
    assert pairs["950 000 €"] == "2021"          # rule 1, same line
