"""
validate_data.py - check the language data files against gen/data/SCHEMA.md.

    py gen/validate_data.py                 every language, every file
    py gen/validate_data.py --lang fr       one language
    py gen/validate_data.py --lang fr --only sentences
        --only is one of: lexicon sentences titles activities locales

Prints every problem found. Exit code 1 if there is at least one ERROR
(warnings do not fail). Run it after every edit of a data file.
"""
import argparse
import json
import pathlib
import re
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"

# data folders: one per language, plus zh-Hant = Traditional Chinese for
# the TW and HK locales (its language label is still "zh")
LANGS = ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi", "ja",
         "ko"]
LANG_OF = {"zh-Hant": "zh"}

# locales per language (held-out locales included: they need lists too)
LANG_LOCALES = {
    "ar": ["ar-SA", "ar-AE", "ar-EG", "ar-MA"],
    "zh": ["zh-CN", "zh-SG"],
    "zh-Hant": ["zh-TW", "zh-HK"],
    "en": ["en-US", "en-GB", "en-IN", "en-AU", "en-CA", "en-NG"],
    "fr": ["fr-FR", "fr-BE", "fr-CH", "fr-CA", "fr-MA", "fr-SN"],
    "ru": ["ru-RU", "ru-KZ", "ru-BY"],
    "es": ["es-ES", "es-MX", "es-AR", "es-CO", "es-CL"],
    "it": ["it-IT", "it-CH"],
    "hi": ["hi-IN"],
    "ja": ["ja-JP"],
    "ko": ["ko-KR"],
}
COUNTRIES = ("SA AE EG MA CN TW HK SG US GB IN AU CA NG FR BE CH SN RU KZ BY "
             "ES MX AR CO CL IT JP KR").split()

# plural categories each language must give (staff_noun, counted)
PLURALS = {"ar": ["zero", "one", "two", "few", "many", "other"],
           "ru": ["one", "few", "many"],
           "zh": ["other"], "ja": ["other"], "ko": ["other"],
           "en": ["one", "other"], "fr": ["one", "other"],
           "es": ["one", "other"], "it": ["one", "other"],
           "hi": ["one", "other"]}

LABELLED = {"S_NAME", "S_NAME:legal", "S_ADDRESS", "S_PHONE", "S_EMAIL",
            "S_URL", "S_PERSON", "S_REG_ID", "C_NAME", "C_NAME_LIST",
            "C_ADDRESS", "C_REG_ID", "LEGAL_FORM", "CAPITAL", "FOUNDED",
            "FOUNDED:date", "FOUNDED:month", "STAFF", "REVENUE",
            "REVENUE_YEAR", "REVENUE_PREV", "REVENUE_YEAR_PREV", "ACTIVITY",
            "ACTIVITY_CODE", "SERVICE", "SERVICE_LIST", "HOURS",
            "HOURS:prose", "CERT", "CERT_LIST", "DOC_DATE"}
PLAIN = {"city", "country", "year", "date", "date_start", "date_end",
         "weekday", "time", "n_days", "n_years", "n_clients", "n_shops",
         "n_vehicles", "n_products", "n_projects", "n_countries", "partner",
         "supplier", "bank", "competitor", "other_org", "other_address",
         "client_founded", "person", "position", "manager_title",
         "staff_noun", "amount", "percent", "quantity", "invoice_no",
         "order_no", "currency", "p", "n"}
KO_PARTICLES = {"은/는", "이/가", "을/를", "과/와", "으로/로"}
S_SLOTS = {s for s in LABELLED if s.startswith("S_")}

HOLDOUT_CATS = {
    "activity": ["ACTIVITY"],
    "founded": ["FOUNDED", "FOUNDED:date", "FOUNDED:month"],
    "staff": ["STAFF"],
    "revenue": ["REVENUE"],
    "services_intro": ["SERVICE", "SERVICE_LIST"],
    "clients": ["C_NAME", "C_NAME_LIST"],
    "hours": ["HOURS", "HOURS:prose"],
    "certifications": ["CERT", "CERT_LIST"],
    "location": ["S_ADDRESS", "S_PHONE", "S_EMAIL", "S_URL"],
    "capital": ["CAPITAL"],
    "legal_form": ["LEGAL_FORM"],
}
TRAP_NEEDS = {
    "T1": [["amount"]],
    "T5": [["partner", "bank", "supplier", "competitor", "client_founded"]],
    "T7": [["year"]],
    "T8": [["n_years", "n_clients", "n_shops", "n_vehicles", "n_products",
            "n_projects"]],
    "T11": [["person"]],
    "T13": [["C_NAME", "C_NAME_LIST"], ["partner", "supplier"]],
}
LETTER_SCENARIOS = {
    # scenario: (has S, has C)
    "payment_reminder": (True, True), "quote_followup": (True, True),
    "price_change": (True, True), "appointment": (True, True),
    "closure": (True, False), "move": (True, False),
    "new_service": (True, True), "thanks": (True, True),
    "order_to_supplier": (True, True), "letter_to_bank": (True, False),
    "order_from_client": (True, True),
    "complaint_from_client": (True, True), "quote_request": (True, True),
    "supplier_offer": (True, True), "bank_notice": (False, True),
    "loan_offer": (False, True), "tax_reminder": (False, True),
    "registry_notice": (False, True),
}
CONTRACT_CLAUSES = ["parties_provider", "parties_client", "preamble",
                    "object", "duration", "price", "payment", "obligations",
                    "confidentiality", "liability", "termination", "law",
                    "signature"]
INVOICE_NOTES = {"payment_terms": 5, "late_penalty": 2, "vat_exempt": 2,
                 "thanks": 4, "quote_validity": 3, "quote_acceptance": 3,
                 "credit_reason": 3}
PHRASES = {"page_x_of_y": (2, ["p", "n"]),
           "place_date": (2, ["city", "DOC_DATE"]),
           "fin_amounts_note": (2, ["currency"]),
           "fin_period": (2, ["date_start", "date_end"]),
           "price_validity": (2, ["date"]),
           "signature_line": (2, []),
           "amount_in_words_intro": (2, [])}
TERMS = {"cgv": 12, "privacy": 8, "legal_notice": 8, "cookies": 3}
WEB = {"testimonials": 6, "news": 6, "cta": 6}
NOISE = {"meeting": 6, "recipe": 4, "manual": 6, "news": 6, "todo": 4,
         "memo": 6, "generic": 12, "press": 6}
PRESS_ALLOWED = {"S_NAME", "FOUNDED", "STAFF", "ACTIVITY", "S_PERSON",
                 "REVENUE", "REVENUE_YEAR", "SERVICE"}
FOOTER_ALLOWED = {"S_NAME", "S_NAME:legal", "LEGAL_FORM", "CAPITAL",
                  "S_ADDRESS", "S_REG_ID", "ACTIVITY_CODE", "S_PHONE",
                  "S_EMAIL", "S_URL"}
GROUPS = ["food", "hospitality", "construction", "auto", "retail", "it",
          "professional", "creative", "transport", "realestate", "services",
          "education", "beauty", "health", "manufacturing"]

TITLES = {
    "doc": {"invoice": 2, "tax_invoice": 1, "quote": 2, "proforma": 1,
            "receipt": 2, "credit_note": 2, "price_list": 2,
            "staff_list": 2, "purchase_order": 1},
    "brochure": {"about": 2, "services": 2, "team": 2, "contact": 2,
                 "clients": 2, "hours": 2, "history": 2, "values": 2,
                 "certifications": 2, "why_us": 2, "news": 2,
                 "testimonials": 2, "faq": 2, "location": 2,
                 "taglines": 8},
    "financials": {"income_statement": 2, "balance_sheet": 2,
                   "annual_accounts": 2, "key_figures": 2,
                   "tax_summary": 2, "notes": 2},
    "other": {"meeting": 1, "manual": 1, "recipe": 1, "news": 1, "memo": 1,
              "todo": 1, "press": 1, "report": 1},
}
CONTRACT_ARTICLES = ["definitions", "object", "duration", "price", "payment",
                     "obligations", "confidentiality", "liability",
                     "termination", "law", "signatures"]
TERMS_ARTICLES = ["scope", "orders", "prices", "payment", "delivery",
                  "warranty", "liability", "withdrawal", "disputes",
                  "data_controller", "data_collected", "purposes",
                  "retention", "rights", "publisher", "hosting",
                  "intellectual_property"]

POSTCODE = {
    "fr-FR": r"\d{5}", "fr-BE": r"\d{4}", "fr-CH": r"\d{4}",
    "it-CH": r"\d{4}", "fr-CA": r"[A-Z]\d[A-Z] \d[A-Z]\d",
    "en-CA": r"[A-Z]\d[A-Z] \d[A-Z]\d", "fr-MA": r"\d{5}",
    "ar-MA": r"\d{5}", "fr-SN": r"(\d{5})?", "en-US": r"\d{5}",
    "en-GB": r"[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}", "en-IN": r"\d{6}",
    "hi-IN": r"\d{6}", "en-AU": r"\d{4}", "en-NG": r"(\d{6})?",
    "ru-RU": r"\d{6}", "ru-KZ": r"\d{6}|[A-Z]\d{2}[A-Z]\d[A-Z]\d",
    "ru-BY": r"\d{6}", "es-ES": r"\d{5}", "es-MX": r"\d{5}",
    "es-AR": r"[A-Z]\d{4}[A-Z]{3}|\d{4}", "es-CO": r"(\d{6})?",
    "es-CL": r"(\d{7})?", "it-IT": r"\d{5}", "ja-JP": r"\d{3}-\d{4}",
    "ko-KR": r"\d{5}", "zh-CN": r"\d{6}", "zh-TW": r"\d{3}(\d{2,3})?",
    "zh-HK": r"", "zh-SG": r"\d{6}", "ar-SA": r"\d{5}", "ar-EG": r"\d{5}",
    "ar-AE": r"",
}
POSTCODE_FIELD = {"en-US": "zip", "en-IN": "pin", "hi-IN": "pin"}
CITY_FIELDS = {
    "ja-JP": ["pref", "city", "town", "postcode"],
    "zh-CN": ["province", "city", "district", "postcode"],
    "zh-TW": ["city", "district", "postcode"],
    "zh-HK": ["district", "region"],
    "zh-SG": ["city", "postcode"],
    "ko-KR": ["sido", "sigungu", "dong", "postcode"],
    "en-IN": ["city", "state", "pin"], "hi-IN": ["city", "state", "pin"],
    "en-US": ["city", "state", "zip"],
    "en-AU": ["city", "state", "postcode"],
    "en-CA": ["city", "province", "postcode"],
    "fr-CA": ["city", "province", "postcode"],
    "en-NG": ["city", "state"],
    "ar-SA": ["city", "postcode", "districts"],
    "ar-EG": ["city", "postcode", "districts"],
    "ar-MA": ["city", "postcode", "districts"],
    "ar-AE": ["city", "postcode", "districts"],
}

SLOT_RE = re.compile(r"\{([^{}]*)\}")


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


def load(path, rep):
    if not path.exists():
        rep.error(str(path.relative_to(HERE)), "file missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as problem:
        rep.error(str(path.relative_to(HERE)), "not valid JSON: %s" % problem)
        return None


def is_str_list(x, minimum=1):
    return (isinstance(x, list) and len(x) >= minimum and
            all(isinstance(s, str) and s.strip() for s in x))


def script_letter(ch):
    """True for a letter of a script where words are separated by spaces
    (a labelled slot must not touch such a letter)."""
    if not ch or not unicodedata.category(ch).startswith(("L", "M")):
        return False
    name = unicodedata.name(ch, "")
    return name.startswith(("LATIN", "CYRILLIC", "ARABIC", "DEVANAGARI",
                            "GREEK"))


def check_template(text, where, rep, lang, allowed=None, need_any=None,
                   multiline=False):
    """Checks one template string. allowed: set of allowed slot names
    (None = every slot). need_any: list of slots, at least one must be
    present. Returns the set of slots used."""
    if not isinstance(text, str) or not text.strip():
        rep.error(where, "empty template")
        return set()
    if "\n" in text and not multiline:
        rep.error(where, "template contains a line break")
    if text != text.strip():
        rep.warn(where, "leading or trailing whitespace")
    depth = 0
    for ch in text:
        depth += (ch == "{") - (ch == "}")
        if depth < 0 or depth > 1:
            rep.error(where, "unbalanced braces: %r" % text)
            return set()
    if depth:
        rep.error(where, "unbalanced braces: %r" % text)
        return set()
    used = set()
    matches = list(SLOT_RE.finditer(text))
    for k, m in enumerate(matches):
        name = m.group(1)
        if name in KO_PARTICLES:
            if lang != "ko":
                rep.error(where, "Korean particle slot {%s} outside Korean"
                          % name)
            elif m.start() == 0 or text[m.start() - 1] != "}":
                rep.error(where, "{%s} must come right after a slot" % name)
            continue
        if name not in LABELLED and name not in PLAIN:
            rep.error(where, "unknown slot {%s}" % name)
            continue
        used.add(name)
        if allowed is not None and name not in allowed:
            rep.error(where, "slot {%s} is not allowed here" % name)
        if name in LABELLED:
            before = text[m.start() - 1] if m.start() else ""
            after = text[m.end()] if m.end() < len(text) else ""
            if script_letter(before) or script_letter(after):
                rep.error(where, "labelled slot {%s} touches a letter: %r"
                          % (name, text[max(0, m.start() - 8):m.end() + 8]))
            if k + 1 < len(matches) and matches[k + 1].start() == m.end() \
                    and matches[k + 1].group(1) in LABELLED:
                rep.error(where, "two labelled slots touch: {%s}{%s}"
                          % (name, matches[k + 1].group(1)))
    if need_any and not (used & set(need_any)):
        rep.error(where, "must contain one of %s: %r"
                  % (" ".join("{%s}" % s for s in need_any), text))
    if lang in ("zh", "ja"):
        if re.search(r"[一-鿿぀-ヿ] [一-鿿぀-ヿ]",
                     text):
            rep.warn(where, "space between CJK characters: %r" % text)
    return used


# ---------------------------------------------------------------------
def check_lexicon(key, rep):
    folder = key                        # the data folder (key is reused)
    lang = LANG_OF.get(key, key)
    path = DATA / key / "lexicon.json"
    lex = load(path, rep)
    if lex is None:
        return
    w = "%s/lexicon.json" % key
    concepts = json.loads((DATA / "concepts.json").read_text(encoding="utf-8"))
    if lex.get("lang") != lang:
        rep.error(w, '"lang" must be "%s"' % lang)
    months = lex.get("months", {})
    for key in ["full", "short"]:
        if not is_str_list(months.get(key), 12) or len(months[key]) != 12:
            rep.error(w, "months.%s must hold 12 strings" % key)
    extra = {"ru": ["genitive"], "ar": ["levantine", "maghrebi", "hijri"]}
    for key in extra.get(lang, []):
        if not is_str_list(months.get(key), 12) or len(months[key]) != 12:
            rep.error(w, "months.%s must hold 12 strings" % key)
    days = lex.get("weekdays", {})
    for key in ["full", "short"]:
        if not is_str_list(days.get(key), 7) or len(days[key]) != 7:
            rep.error(w, "weekdays.%s must hold 7 strings" % key)
    nums = lex.get("numbers", {})
    need_units = 101 if lang == "hi" else 21
    if not is_str_list(nums.get("units"), need_units):
        rep.error(w, "numbers.units must hold %d words" % need_units)
    for key, need in [("tens", ["20", "30", "40", "50", "60", "70", "80",
                                "90"]),
                      ("hundreds", [str(i * 100) for i in range(1, 10)]),
                      ("big", ["1000", "1000000"])]:
        got = nums.get(key, {})
        if lang == "hi" and key == "tens":
            continue
        missing = [k for k in need if not (isinstance(got, dict) and
                                           isinstance(got.get(k), str) and
                                           got.get(k).strip())]
        if missing:
            rep.error(w, "numbers.%s is missing %s" % (key, missing))
    if lang == "zh" and not is_str_list(nums.get("financial"), 10):
        rep.error(w, "numbers.financial must hold the capital-form "
                  "characters")
    cur = lex.get("currency_names", {})
    if not isinstance(cur, dict) or not {"EUR", "USD"} <= set(cur):
        rep.error(w, "currency_names needs at least EUR and USD")
    for code, words in (cur.items() if isinstance(cur, dict) else []):
        if not is_str_list(words):
            rep.error(w, "currency_names.%s must be a list of words" % code)
    kw = lex.get("kw", {})
    for concept in concepts["kw"]:
        value = kw.get(concept)
        if not is_str_list(value):
            rep.error(w, "kw.%s missing or empty" % concept)
        elif concept in ("payment_methods",) and len(value) < 4:
            rep.error(w, "kw.%s needs at least 4 entries" % concept)
        elif concept in ("lt_salutation", "lt_closing", "contract_types",
                         "fin_revenue") and len(value) < 3:
            rep.error(w, "kw.%s needs at least 3 entries" % concept)
    for concept in kw:
        if concept not in concepts["kw"]:
            rep.warn(w, "kw.%s is not in concepts.json (unused)" % concept)
    units = lex.get("units", {})
    for unit in concepts["units"]:
        if not is_str_list(units.get(unit)):
            rep.error(w, "units.%s missing" % unit)
    cats = PLURALS[lang]
    noun = lex.get("staff_noun", {})
    for c in cats:
        if not isinstance(noun.get(c), str):
            rep.error(w, "staff_noun.%s missing" % c)
    counted = lex.get("counted", {})
    for kind in ["years", "clients", "shops", "vehicles", "products",
                 "projects", "countries"]:
        forms = counted.get(kind, {})
        for c in cats:
            if not isinstance(forms.get(c), str) or "{n}" not in forms[c]:
                rep.error(w, "counted.%s.%s missing or without {n}"
                          % (kind, c))
    for key, need in [("manager_titles", 6), ("positions", 15),
                      ("departments", 8), ("brand_words", 60),
                      ("name_patterns", 6)]:
        if not is_str_list(lex.get(key), need):
            rep.error(w, "%s needs at least %d entries (has %d)"
                      % (key, need, len(lex.get(key) or [])))
    for pattern in lex.get("name_patterns", []) or []:
        for m in SLOT_RE.finditer(pattern):
            if m.group(1) not in ("family", "given", "brand",
                                  "activity_word", "city", "initials"):
                rep.error(w, "name pattern uses unknown {%s}: %r"
                          % (m.group(1), pattern))
    hon = lex.get("honorifics", {})
    if not (is_str_list(hon.get("male")) and is_str_list(hon.get("female"))):
        rep.error(w, "honorifics needs male and female lists")
    lj = lex.get("list_join", {})
    if not (isinstance(lj.get("sep"), str) and isinstance(lj.get("last"), str)):
        rep.error(w, "list_join needs sep and last")
    cn = lex.get("country_names", {})
    missing = [c for c in COUNTRIES if not isinstance(cn.get(c), str)]
    if missing:
        rep.error(w, "country_names missing %s" % missing)
    orgs = lex.get("orgs", {})
    countries = sorted({loc.split("-")[1] for loc in LANG_LOCALES[folder]})
    for part in ["banks", "registry", "tax_office"]:
        per = orgs.get(part, {})
        need = 6 if part == "banks" else 2
        for c in countries:
            if not is_str_list(per.get(c) if isinstance(per, dict) else None,
                               need):
                rep.error(w, "orgs.%s.%s needs at least %d entries"
                          % (part, c, need))
    for part, need in [("auditor", 4), ("notary", 2), ("hosting", 4),
                       ("insurers", 4), ("public_bodies", 6),
                       ("associations", 4)]:
        if not is_str_list(orgs.get(part), need):
            rep.error(w, "orgs.%s needs at least %d entries" % (part, need))
    certs = lex.get("certs", [])
    if not isinstance(certs, list) or len(certs) < 20:
        rep.error(w, "certs needs at least 20 entries")
    for c in certs if isinstance(certs, list) else []:
        if not (isinstance(c, dict) and isinstance(c.get("name"), str) and
                is_str_list(c.get("countries")) and
                is_str_list(c.get("groups"))):
            rep.error(w, "bad cert entry %r" % (c,))
            continue
        for g in c["groups"]:
            if g != "*" and g not in GROUPS:
                rep.error(w, "cert %r: unknown group %r" % (c["name"], g))


# ---------------------------------------------------------------------
def check_sentences(key, rep, path=None):
    lang = LANG_OF.get(key, key)
    path = path or DATA / key / "sentences.json"
    sent = load(path, rep)
    if sent is None:
        return
    w = "%s/%s" % (key, path.name)
    test_file = DATA / key / "sentences_test.json"
    held = {}
    if path.name == "sentences.json" and test_file.exists():
        held = json.loads(test_file.read_text(encoding="utf-8"))
    ids = set()
    for cat, need in HOLDOUT_CATS.items():
        items = sent.get(cat, [])
        total = len(items) + len(held.get(cat, []))
        if total < 20:
            rep.error(w, "%s needs at least 20 templates (has %d)"
                      % (cat, total))
        for k, item in enumerate(items):
            where = "%s %s[%d]" % (w, cat, k)
            if not isinstance(item, dict):
                rep.error(where, "must be an object with id and text")
                continue
            check_id(item.get("id"), cat, lang, ids, where, rep)
            check_template(item.get("text"), where, rep, lang,
                           allowed=LABELLED - {"DOC_DATE"} | PLAIN,
                           need_any=need)
    traps = sent.get("traps", [])
    counts = {}
    for k, item in enumerate(traps):
        where = "%s traps[%d]" % (w, k)
        if not isinstance(item, dict):
            rep.error(where, "must be an object")
            continue
        check_id(item.get("id"), "trap", lang, ids, where, rep)
        trap = item.get("trap")
        if trap not in TRAP_NEEDS:
            rep.error(where, "trap must be one of %s" % sorted(TRAP_NEEDS))
            continue
        counts[trap] = counts.get(trap, 0) + 1
        used = check_template(item.get("text"), where, rep, lang,
                              allowed=LABELLED - {"DOC_DATE"} | PLAIN)
        for group in TRAP_NEEDS[trap]:
            if not used & set(group):
                rep.error(where, "%s trap must use one of %s" % (trap, group))
    for trap, (held_items) in [(t, [i for i in held.get("traps", [])
                                    if i.get("trap") == t])
                               for t in TRAP_NEEDS]:
        total = counts.get(trap, 0) + len(held_items)
        if total < 8:
            rep.error(w, "traps: %s needs at least 8 (has %d)" % (trap, total))
    fillers = sent.get("filler", [])
    if len(fillers) + len(held.get("filler", [])) < 40:
        rep.error(w, "filler needs at least 40")
    for k, item in enumerate(fillers):
        where = "%s filler[%d]" % (w, k)
        if not isinstance(item, dict):
            rep.error(where, "must be an object")
            continue
        check_id(item.get("id"), "filler", lang, ids, where, rep)
        check_template(item.get("text"), where, rep, lang, allowed=PLAIN)
    if path.name != "sentences.json":
        return
    # ---- the categories that are not held out
    countries = sorted({loc.split("-")[1] for loc in LANG_LOCALES[key]})
    footers = sent.get("legal_footer", [])
    per_country = {c: 0 for c in countries}
    for k, item in enumerate(footers):
        where = "%s legal_footer[%d]" % (w, k)
        if not isinstance(item, dict) or not is_str_list(item.get("countries")):
            rep.error(where, "needs countries and text")
            continue
        for c in item["countries"]:
            if c in per_country:
                per_country[c] += 1
        check_template(item.get("text"), where, rep, lang,
                       allowed=FOOTER_ALLOWED | {"city", "country"})
    for c, n in per_country.items():
        if n < 3:
            rep.error(w, "legal_footer: country %s needs at least 3 (has %d)"
                      % (c, n))
    notes = sent.get("invoice_notes", {})
    for key, need in INVOICE_NOTES.items():
        items = notes.get(key, [])
        if not is_str_list(items, need):
            rep.error(w, "invoice_notes.%s needs at least %d" % (key, need))
            continue
        for k, text in enumerate(items):
            check_template(text, "%s invoice_notes.%s[%d]" % (w, key, k),
                           rep, lang, allowed=PLAIN)
    phrases = sent.get("phrases", {})
    for key, (need, slots) in PHRASES.items():
        items = phrases.get(key, [])
        if not is_str_list(items, need):
            rep.error(w, "phrases.%s needs at least %d" % (key, need))
            continue
        for k, text in enumerate(items):
            used = check_template(text, "%s phrases.%s[%d]" % (w, key, k),
                                  rep, lang, allowed=PLAIN | {"DOC_DATE"})
            for s in slots:
                if s not in used:
                    rep.error("%s phrases.%s[%d]" % (w, key, k),
                              "must contain {%s}" % s)
    letters = sent.get("letters", {})
    for scen, (has_s, has_c) in LETTER_SCENARIOS.items():
        block = letters.get(scen)
        if not isinstance(block, dict):
            rep.error(w, "letters.%s missing" % scen)
            continue
        allowed = set(PLAIN) | {"DOC_DATE"}
        if has_s:
            allowed |= LABELLED - {"C_NAME", "C_NAME_LIST", "C_ADDRESS",
                                   "C_REG_ID"}
        if has_c:
            allowed |= {"C_NAME", "C_ADDRESS", "C_REG_ID"}
        for part, need in [("subject", 2), ("body", 4)]:
            items = block.get(part, [])
            if not is_str_list(items, need):
                rep.error(w, "letters.%s.%s needs at least %d"
                          % (scen, part, need))
                continue
            for k, text in enumerate(items):
                check_template(text, "%s letters.%s.%s[%d]"
                               % (w, scen, part, k), rep, lang,
                               allowed=allowed)
    contract = sent.get("contract", {})
    for clause in CONTRACT_CLAUSES:
        items = contract.get(clause, [])
        if not is_str_list(items, 2):
            rep.error(w, "contract.%s needs at least 2" % clause)
            continue
        for k, text in enumerate(items):
            used = check_template(text, "%s contract.%s[%d]"
                                  % (w, clause, k), rep, lang)
            if clause == "parties_client" and used & S_SLOTS:
                rep.error("%s contract.%s[%d]" % (w, clause, k),
                          "the client clause must not use S_ slots")
            if clause == "parties_provider" and used & {"C_NAME", "C_ADDRESS",
                                                        "C_REG_ID"}:
                rep.error("%s contract.%s[%d]" % (w, clause, k),
                          "the provider clause must not use C_ slots")
    terms = sent.get("terms", {})
    for key, need in TERMS.items():
        items = terms.get(key, [])
        if not is_str_list(items, need):
            rep.error(w, "terms.%s needs at least %d" % (key, need))
            continue
        for k, text in enumerate(items):
            check_template(text, "%s terms.%s[%d]" % (w, key, k), rep, lang,
                           allowed=S_SLOTS | {"S_NAME:legal", "LEGAL_FORM",
                                              "CAPITAL", "ACTIVITY",
                                              "SERVICE"} | PLAIN)
    web = sent.get("web", {})
    for key, need in WEB.items():
        items = web.get(key, [])
        if not is_str_list(items, need):
            rep.error(w, "web.%s needs at least %d" % (key, need))
            continue
        for k, text in enumerate(items):
            check_template(text, "%s web.%s[%d]" % (w, key, k), rep, lang,
                           allowed={"S_NAME", "SERVICE", "S_PHONE",
                                    "S_EMAIL", "S_URL"} | PLAIN)
    noise = sent.get("noise", {})
    for key, need in NOISE.items():
        items = noise.get(key, [])
        if not is_str_list(items, need):
            rep.error(w, "noise.%s needs at least %d" % (key, need))
            continue
        allowed = PLAIN | (PRESS_ALLOWED if key == "press" else set())
        for k, text in enumerate(items):
            check_template(text, "%s noise.%s[%d]" % (w, key, k), rep, lang,
                           allowed=allowed)


def check_id(value, cat, lang, ids, where, rep):
    pattern = r"^%s\.%s\.\d{2,3}$" % (re.escape(cat), lang)
    if not isinstance(value, str) or not re.match(pattern, value):
        rep.error(where, "id %r must look like %s.%s.07" % (value, cat, lang))
    elif value in ids:
        rep.error(where, "duplicate id %s" % value)
    else:
        ids.add(value)


# ---------------------------------------------------------------------
def check_titles(key, rep):
    t = load(DATA / key / "titles.json", rep)
    if t is None:
        return
    w = "%s/titles.json" % key
    for section, keys in TITLES.items():
        for key, need in keys.items():
            items = (t.get(section) or {}).get(key)
            if not is_str_list(items, need):
                rep.error(w, "%s.%s needs at least %d" % (section, key, need))
            else:
                for s in items:
                    for m in SLOT_RE.finditer(s):
                        if not (key == "taglines" and m.group(1) == "city"):
                            rep.error(w, "%s.%s: no slots allowed: %r"
                                      % (section, key, s))
    contract = t.get("contract") or {}
    if not is_str_list(contract.get("titles"), 4):
        rep.error(w, "contract.titles needs at least 4")
    for key in CONTRACT_ARTICLES:
        if not is_str_list((contract.get("articles") or {}).get(key)):
            rep.error(w, "contract.articles.%s missing" % key)
    terms = t.get("terms") or {}
    for key in ["cgv", "privacy", "legal_notice", "cookies"]:
        if not is_str_list(terms.get(key)):
            rep.error(w, "terms.%s missing" % key)
    for key in TERMS_ARTICLES:
        if not is_str_list((terms.get("articles") or {}).get(key)):
            rep.error(w, "terms.articles.%s missing" % key)


# ---------------------------------------------------------------------
def check_activities(key, rep):
    lang = key
    base = json.loads((DATA / "activities_base.json").read_text(
        encoding="utf-8"))["activities"]
    concepts = json.loads((DATA / "concepts.json").read_text(encoding="utf-8"))
    merged = DATA / "activities.json"
    part_path = DATA / key / "activities_part.json"
    if part_path.exists():
        part = load(part_path, rep)
        w = "%s/activities_part.json" % lang
    elif merged.exists():
        full = load(merged, rep)
        part = {a["id"]: {"names": a["names"].get(lang),
                          "name_words": a["name_words"].get(lang),
                          "phrases": a["phrases"].get(lang),
                          "services": a["services"].get(lang)}
                for a in full["activities"]}
        w = "activities.json[%s]" % lang
    else:
        rep.error(str(part_path.relative_to(HERE)), "file missing")
        return
    if part is None:
        return
    for act in base:
        a = part.get(act["id"])
        where = "%s %s" % (w, act["id"])
        if not isinstance(a, dict):
            rep.error(where, "missing")
            continue
        if not is_str_list(a.get("names"), 2) or len(a["names"]) > 3:
            rep.error(where, "names must hold 2-3 strings")
        if not is_str_list(a.get("name_words"), 1) or len(a["name_words"]) > 4:
            rep.error(where, "name_words must hold 1-4 strings")
        phrases = a.get("phrases")
        if not is_str_list(phrases, 3) or len(phrases) > 6:
            rep.error(where, "phrases must hold 3-6 strings")
        else:
            for p in phrases:
                if len(p) > 200:
                    rep.error(where, "phrase longer than 200 characters")
                if p != p.strip() or p.endswith((".", "。", "।")):
                    rep.error(where, "phrase must be trimmed, without final "
                              "punctuation: %r" % p)
        services = a.get("services")
        if not isinstance(services, list) or not 10 <= len(services) <= 15:
            rep.error(where, "services must hold 10-15 entries")
            continue
        names = set()
        for s in services:
            if not (isinstance(s, dict) and isinstance(s.get("name"), str) and
                    s["name"].strip() == s["name"] and s["name"]):
                rep.error(where, "bad service %r" % (s,))
                continue
            if s["name"] in names:
                rep.error(where, "duplicate service %r" % s["name"])
            names.add(s["name"])
            usd = s.get("usd")
            if not (isinstance(usd, list) and len(usd) == 2 and
                    all(isinstance(x, (int, float)) for x in usd) and
                    0 < usd[0] <= usd[1]):
                rep.error(where, "service %r: usd must be [low, high]"
                          % s["name"])
            if s.get("unit") not in concepts["units"]:
                rep.error(where, "service %r: unit %r not in concepts.json"
                          % (s["name"], s.get("unit")))
    for key in part:
        if key not in {a["id"] for a in base}:
            rep.error(w, "unknown activity id %r" % key)


# ---------------------------------------------------------------------
def check_locales(key, rep):
    lang = LANG_OF.get(key, key)
    for loc in LANG_LOCALES[key]:
        folder = DATA / loc
        names = load(folder / "names.json", rep)
        w = "%s/names.json" % loc
        if names is not None:
            for key, need in [("given_male", 30), ("given_female", 30),
                              ("family", 60)]:
                if not is_str_list(names.get(key), need):
                    rep.error(w, "%s needs at least %d" % (key, need))
            if lang == "ru":
                fam = names.get("family") or []
                fem = names.get("family_female") or []
                if len(fam) != len(fem):
                    rep.error(w, "family_female must match family one by one")
                for key in ["patronymic_male", "patronymic_female"]:
                    if not is_str_list(names.get(key), 20):
                        rep.error(w, "%s needs at least 20" % key)
            dups = {n for n in names.get("family", []) or []
                    if (names.get("family") or []).count(n) > 1}
            if dups:
                rep.warn(w, "duplicate family names %s" % sorted(dups)[:5])
        streets = load(folder / "streets.json", rep)
        if streets is not None and not is_str_list(streets.get("streets"), 40):
            rep.error("%s/streets.json" % loc, "streets needs at least 40")
        cities = load(folder / "cities.json", rep)
        w = "%s/cities.json" % loc
        if cities is None:
            continue
        if not isinstance(cities, list) or len(cities) < 30:
            rep.error(w, "needs at least 30 places")
            continue
        fields = CITY_FIELDS.get(loc, ["city", "postcode"])
        pc_field = POSTCODE_FIELD.get(loc, "postcode")
        regex = re.compile(r"^(%s)$" % POSTCODE.get(loc, r".*"))
        for k, c in enumerate(cities):
            if not isinstance(c, dict):
                rep.error(w, "entry %d is not an object" % k)
                continue
            for f in fields:
                if f not in c:
                    rep.error(w, "entry %d misses %r" % (k, f))
            if pc_field in c:
                codes = c[pc_field] if isinstance(c[pc_field], list) \
                    else [c[pc_field]]
                for code in codes:
                    if not isinstance(code, str) or not regex.match(code):
                        rep.error(w, "entry %d: postcode %r does not match "
                                  "%s" % (k, code, POSTCODE.get(loc)))
            if "districts" in fields and not isinstance(c.get("districts"),
                                                        list):
                rep.error(w, "entry %d: districts must be a list" % k)


CHECKS = {"lexicon": check_lexicon, "sentences": check_sentences,
          "titles": check_titles, "activities": check_activities,
          "locales": check_locales}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=LANGS)
    ap.add_argument("--only", choices=list(CHECKS))
    args = ap.parse_args()
    rep = Report()
    for lang in [args.lang] if args.lang else LANGS:
        for name, check in CHECKS.items():
            if args.only and name != args.only:
                continue
            check(lang, rep)
    for msg in rep.warnings:
        print("warning  " + msg)
    for msg in rep.errors:
        print("ERROR    " + msg)
    print("\n%d errors, %d warnings" % (len(rep.errors), len(rep.warnings)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
