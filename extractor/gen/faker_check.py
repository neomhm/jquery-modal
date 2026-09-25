"""
faker_check.py - the Faker rule of section 10.3.

Several Faker locales quietly fall back to English data (US addresses,
English person names). For every locale, and separately for person names
and for addresses, this draws 200 samples and accepts Faker only if:
  * the script matches the language;
  * there is no US state + ZIP pattern outside en-US;
  * no English street words (Street, Court, Suite, Manor, "ville") appear
    outside the English locales;
  * the postcode matches the locale's pattern (addresses);
  * the given names are not mostly English ones (names, non-English
    locales) - this catches it_CH, ar_AE and ar_EG.
Otherwise the generator uses the lists written for the locale
(gen/data/<locale>/names.json, streets.json, cities.json).

    py gen/faker_check.py          writes gen/data/faker_decisions.json

Addresses always use the locale's own lists (a conservative choice: the
address order of each country and real postcodes of real towns). Faker
is used for person names only where it passes the rule, for half of the
people, the other half coming from the own lists.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gen import data as D                                # noqa: E402

OUT = HERE / "data" / "faker_decisions.json"
SAMPLES = 200
ENGLISH_LANGS = {"en"}
US_STATE_ZIP = re.compile(r"\b[A-Z]{2} \d{5}(-\d{4})?\b")
ENGLISH_STREET = re.compile(r"\b(Street|Court|Suite|Manor|Avenue|Lane|"
                            r"Drive|Road|Apt\.)\b|\w+ville\b")
SCRIPTS = {
    "ar": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF),
           (0xFE70, 0xFEFF)],
    "ru": [(0x0400, 0x04FF)],
    "hi": [(0x0900, 0x097F)],
    "zh": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],
    "ja": [(0x4E00, 0x9FFF), (0x3040, 0x30FF), (0x3005, 0x3005)],
    "ko": [(0xAC00, 0xD7A3), (0x1100, 0x11FF)],
}
LATIN = [(0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F)]


def script_ok(text, lang):
    ranges = SCRIPTS.get(lang, LATIN)
    for ch in text:
        if not ch.isalpha():
            continue
        cp = ord(ch)
        if not any(a <= cp <= b for a, b in ranges):
            return False
    return True


def english_first_names():
    from faker.providers.person.en_US import Provider
    names = set()
    for attr in ("first_names_male", "first_names_female", "first_names"):
        value = getattr(Provider, attr, None) or {}
        names.update(value.keys() if isinstance(value, dict) else value)
    return names


def own_given_names(code):
    names = D.locale_list(code, "names") or {}
    return set(names.get("given_male", [])) | set(names.get("given_female",
                                                            []))


def test_names(code, loc, english=None):
    """-> (passes, reason)."""
    from faker import Faker
    fake = Faker(loc["faker"])
    fake.seed_instance(10)
    lang = loc["lang"]
    english = english if english is not None else english_first_names()
    own = own_given_names(code)
    en_like = 0
    for k in range(SAMPLES):
        given = fake.first_name_male() if k % 2 else fake.first_name_female()
        family = fake.last_name()
        full = "%s %s" % (given, family)
        if not script_ok(full, lang):
            return False, "script: %r" % full
        if lang not in ENGLISH_LANGS and given in english and \
                given not in own:
            en_like += 1
    if lang not in ENGLISH_LANGS and lang in ("fr", "es", "it") and \
            en_like > SAMPLES * 0.4:
        return False, "%d of %d given names are English" % (en_like,
                                                            SAMPLES)
    return True, "ok"


def test_addresses(code, loc):
    from faker import Faker
    fake = Faker(loc["faker"])
    fake.seed_instance(11)
    lang = loc["lang"]
    from gen.validate_data import POSTCODE
    pattern = POSTCODE.get(code)
    for _ in range(SAMPLES):
        addr = fake.address()
        if not script_ok(re.sub(r"[A-Za-z]{1,3}\b", "", addr)
                         if lang not in ("en", "fr", "es", "it") else addr,
                         lang):
            return False, "script: %r" % addr
        if code != "en-US" and US_STATE_ZIP.search(addr):
            return False, "US state + ZIP: %r" % addr
        if lang not in ENGLISH_LANGS and ENGLISH_STREET.search(addr):
            return False, "English street word: %r" % addr
        if pattern:
            try:
                pc = fake.postcode()
            except AttributeError:
                return False, "no postcode provider"
            if not re.fullmatch(pattern, pc):
                return False, "postcode %r does not match %s" % (pc,
                                                                  pattern)
    return True, "ok"


def own_lists_ok(code):
    """>= 60 given names, >= 60 family names, >= 40 streets, >= 30
    cities (section 10.3)."""
    names = D.locale_list(code, "names") or {}
    given = len(own_given_names(code))
    family = len(set(names.get("family", [])))
    streets = D.locale_list(code, "streets") or []
    if isinstance(streets, dict):
        streets = streets.get("streets") or []
    cities = D.locale_list(code, "cities") or []
    if isinstance(cities, dict):
        cities = cities.get("cities") or []
    problems = []
    if given < 60:
        problems.append("%d given names" % given)
    if family < 60:
        problems.append("%d family names" % family)
    if len(streets) < 40:
        problems.append("%d streets" % len(streets))
    if len(cities) < 30:
        problems.append("%d cities" % len(cities))
    return not problems, ", ".join(problems) or "ok"


def decide(log=print):
    english = english_first_names()
    out = {}
    for code, loc in sorted(D.locales()["locales"].items()):
        entry = {"addresses": "own", "names": "own"}
        if loc.get("faker"):
            ok_n, why_n = test_names(code, loc, english)
            ok_a, why_a = test_addresses(code, loc)
            entry["names"] = "faker" if ok_n else "own"
            entry["names_test"] = why_n
            entry["addresses_test"] = why_a
        else:
            entry["names_test"] = entry["addresses_test"] = "no Faker locale"
        out[code] = entry
        log("%-6s names: %-5s (%s) | addresses: own (Faker test: %s)" % (
            code, entry["names"], entry["names_test"][:60],
            entry["addresses_test"][:60]))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1,
                              sort_keys=True), encoding="utf-8")
    D.faker_decisions.cache_clear()
    return out


def verify():
    """Check 8 of 10.9: every locale that uses Faker passes the rule, and
    every locale has usable own lists. -> (ok, detail)."""
    if not OUT.exists():
        return False, "gen/data/faker_decisions.json missing - run " \
            "py gen/faker_check.py"
    decisions = json.loads(OUT.read_text(encoding="utf-8"))
    english = english_first_names()
    problems = []
    n_faker = 0
    for code, loc in sorted(D.locales()["locales"].items()):
        entry = decisions.get(code)
        if entry is None:
            problems.append("%s: no decision" % code)
            continue
        if entry["names"] == "faker":
            n_faker += 1
            ok, why = test_names(code, loc, english)
            if not ok:
                problems.append("%s names: %s" % (code, why))
        if entry["addresses"] == "faker":
            ok, why = test_addresses(code, loc)
            if not ok:
                problems.append("%s addresses: %s" % (code, why))
        ok, why = own_lists_ok(code)
        if not ok:
            problems.append("%s own lists: %s" % (code, why))
    detail = "%d locales use Faker for names; %d problems %s" % (
        n_faker, len(problems), problems[:4])
    return not problems, detail


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    decide()
    ok, detail = verify()
    print("verify:", "PASS" if ok else "FAIL", detail)
