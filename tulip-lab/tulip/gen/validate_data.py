"""
validate_data.py - check the word lists of one data folder (or all).

    py gen/validate_data.py fr
    py gen/validate_data.py            (every folder)

Checks the shape and the counts that gen/data/BRIEFING_FOR_WRITERS.md
asks for: every key present, enough variants, no duplicates, no
forbidden characters, valid placeholders, 15-30 items per activity...
Prints OK or the list of problems.
"""
import json
import pathlib
import re
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
FOLDERS = ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi", "ja",
           "ko"]

FIELD_KEYS = [
    "sku", "product_name", "variant", "description", "category", "price",
    "price_incl", "price_excl", "vat_rate", "stock", "unit", "barcode",
    "active", "currency", "service_name", "duration", "performer", "day",
    "hours", "hours_note", "morning", "afternoon", "opens", "closes",
    "person_name", "first_name", "last_name", "role", "department",
    "email", "phone", "start_date", "client_name", "company",
    "contact_person", "address", "street", "postcode", "city", "country",
    "reg_id", "client_since", "booking_date", "booking_datetime",
    "start_time", "end_time", "time_range", "booking_client",
    "booking_service", "booking_status", "invoice_number", "invoice_date",
    "invoice_client", "total", "total_incl", "total_excl", "tax_amount",
    "invoice_status", "due_date", "paid_date", "patronymic",
    "second_last_name"]
ONLY_IN = {"patronymic": "ru", "second_last_name": "es"}
CUR_KEYS = ["price", "price_incl", "price_excl", "total"]
TRAP_KEYS = ["cost", "margin", "qty_ordered", "qty_sold", "supplier_ref",
             "internal_notes", "discount"]
EXTRA_KINDS = ["code", "date", "person", "word", "number"]
GROUP_KEYS = ["price", "stock", "product", "contact", "dates"]
TARGETS = ["products", "services", "opening_hours", "staff", "clients",
           "bookings", "invoice_ledger"]
UNITS = ["piece", "kg", "g", "l", "ml", "box", "pack", "hour", "day",
         "month", "person", "session", "set", "m", "m2"]
PLACEHOLDER = re.compile(r"\{([a-z]+)\}")
ALLOWED_PLACEHOLDERS = {"cur", "year", "month", "date", "business"}


def activity_ids():
    base = pathlib.Path(__file__).resolve().parents[2] / "extractor" / \
        "gen" / "data" / "activities_base.json"
    local = DATA / "activities_base.json"
    path = local if local.exists() else base
    return [a["id"] for a in json.loads(path.read_text(
        encoding="utf-8"))["activities"]]


class Problems(list):
    def add(self, where, text):
        self.append("%s: %s" % (where, text))


def check_strings(p, where, items, minimum, max_len=40, placeholders=()):
    if not isinstance(items, list):
        p.add(where, "must be a list")
        return
    if len(items) < minimum:
        p.add(where, "has %d entries, needs at least %d" % (len(items),
                                                            minimum))
    seen = set()
    for s in items:
        if not isinstance(s, str) or not s:
            p.add(where, "empty or not text: %r" % (s,))
            continue
        if s != s.strip() or "\n" in s or "|" in s or "  " in s:
            p.add(where, "spaces, line break or | in %r" % s)
        if len(s) > max_len:
            p.add(where, "longer than %d characters: %r" % (max_len, s))
        key = " ".join(unicodedata.normalize("NFKC", s).casefold().split())
        if key in seen:
            p.add(where, "duplicate %r" % s)
        seen.add(key)
        for name in PLACEHOLDER.findall(s):
            if name not in placeholders:
                p.add(where, "placeholder {%s} not allowed here: %r"
                      % (name, s))


def check_headers(folder, p):
    path = DATA / folder / "headers.json"
    if not path.exists():
        p.add(folder, "headers.json missing")
        return
    try:
        h = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        p.add("headers.json", "not valid JSON: %s" % e)
        return
    lang = folder.split("-")[0]
    fields = h.get("fields") or {}
    for key in FIELD_KEYS:
        where = "headers.fields.%s" % key
        if key in ONLY_IN:
            if ONLY_IN[key] == lang:
                check_strings(p, where, fields.get(key), 8)
            elif fields.get(key):
                p.add(where, "must be [] for this language")
            continue
        check_strings(p, where, fields.get(key), 8,
                      placeholders={"cur"} if key in CUR_KEYS + [
                          "total_incl", "total_excl", "tax_amount"]
                      else ())
        if key in CUR_KEYS:
            with_cur = [v for v in fields.get(key) or [] if "{cur}" in v]
            if len(with_cur) < 2:
                p.add(where, "needs at least 2 variants with {cur}")
    for key in fields:
        if key not in FIELD_KEYS:
            p.add("headers.fields", "unknown key %r" % key)
    for key in TRAP_KEYS:
        check_strings(p, "headers.traps.%s" % key,
                      (h.get("traps") or {}).get(key), 6,
                      placeholders={"cur"})
    for kind in EXTRA_KINDS:
        check_strings(p, "headers.extra.%s" % kind,
                      (h.get("extra") or {}).get(kind), 6)
    for key in GROUP_KEYS:
        check_strings(p, "headers.groups.%s" % key,
                      (h.get("groups") or {}).get(key), 4)


def check_values(folder, p):
    path = DATA / folder / "values.json"
    if not path.exists():
        p.add(folder, "values.json missing")
        return
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        p.add("values.json", "not valid JSON: %s" % e)
        return
    wd = v.get("weekdays") or {}
    if len(wd.get("full") or []) != 7:
        p.add("values.weekdays.full", "needs exactly 7 names")
    if wd.get("short") and len(wd["short"]) != 7:
        p.add("values.weekdays.short", "needs exactly 7 (or be empty)")
    if wd.get("other") and len(wd["other"]) != 7:
        p.add("values.weekdays.other", "needs 7 lists")
    months = v.get("months") or {}
    if len(months.get("full") or []) != 12:
        p.add("values.months.full", "needs exactly 12 names")
    if months.get("short") and len(months["short"]) != 12:
        p.add("values.months.short", "needs 12 (or be empty)")
    for key, n in (("closed", 3), ("yes", 3), ("no", 3), ("totals", 3),
                   ("subtotals", 3), ("tax_included", 4),
                   ("tax_excluded", 4), ("from_words", 2),
                   ("minute_words", 2), ("hour_words", 2),
                   ("hours_notes", 5), ("balance_rows", 2),
                   ("credit_note", 2)):
        check_strings(p, "values.%s" % key, v.get(key), n, 32)
    check_strings(p, "values.notes_rows", v.get("notes_rows"), 6, 60,
                  placeholders={"date", "year"})
    statuses = {}
    for group, values in (("invoice_status", ["paid", "unpaid", "partial",
                                              "overdue", "cancelled"]),
                          ("booking_status", ["confirmed", "pending",
                                              "completed", "cancelled",
                                              "no_show"])):
        g = v.get(group) or {}
        seen = {}
        for value in values + ["other"]:
            check_strings(p, "values.%s.%s" % (group, value), g.get(value),
                          2 if value == "other" and group == "booking_status"
                          else 3, 32)
            for w in g.get(value) or []:
                k = " ".join(unicodedata.normalize("NFKC", w)
                             .casefold().split())
                if k in seen and seen[k] != value:
                    p.add("values.%s" % group, "%r is in both %s and %s"
                          % (w, seen[k], value))
                seen[k] = value
        statuses[group] = seen
    units = v.get("units") or {}
    for u in UNITS:
        check_strings(p, "values.units.%s" % u, units.get(u),
                      2 if u in ("piece", "hour") else 1, 20)
    for t in TARGETS:
        check_strings(p, "values.title_rows.%s" % t,
                      (v.get("title_rows") or {}).get(t), 4, 60,
                      placeholders={"year", "month", "business"})
        check_strings(p, "values.sheet_names.%s" % t,
                      (v.get("sheet_names") or {}).get(t), 4, 25,
                      placeholders={"year"})
    check_strings(p, "values.sheet_names.other",
                  (v.get("sheet_names") or {}).get("other"), 4, 25)
    nat = v.get("not_a_table") or {}
    check_strings(p, "values.not_a_table.notes_page", nat.get("notes_page"),
                  8, 120)
    check_strings(p, "values.not_a_table.summary", nat.get("summary"), 6, 40)
    check_strings(p, "values.not_a_table.chart", nat.get("chart"), 4, 40)
    budget = v.get("budget") or {}
    check_strings(p, "values.budget.headers", budget.get("headers"), 6, 40)
    check_strings(p, "values.budget.lines", budget.get("lines"), 10, 40)
    if not isinstance(v.get("am_pm"), list):
        p.add("values.am_pm", "must be a list (may be empty)")
    totals = set(" ".join(unicodedata.normalize("NFKC", w).casefold().split())
                 for w in (v.get("totals") or []) + (v.get("subtotals") or []))
    for line in v.get("notes_rows") or []:
        k = unicodedata.normalize("NFKC", line).casefold()
        if any(k.startswith(t) for t in totals):
            p.add("values.notes_rows", "starts with a totals word: %r" % line)


def check_activities(folder, p):
    path = DATA / folder / "activities.json"
    if not path.exists():
        p.add(folder, "activities.json missing")
        return
    try:
        acts = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        p.add("activities.json", "not valid JSON: %s" % e)
        return
    for aid in activity_ids():
        a = acts.get(aid)
        where = "activities.%s" % aid
        if not a:
            p.add(where, "missing")
            continue
        cats = a.get("categories") or []
        check_strings(p, where + ".categories", cats, 3, 32)
        if len(cats) > 6:
            p.add(where + ".categories", "at most 6")
        check_strings(p, where + ".roles", a.get("roles"), 5, 40)
        check_strings(p, where + ".departments", a.get("departments"), 2, 40)
        items = a.get("items") or []
        if not 15 <= len(items) <= 30:
            p.add(where + ".items", "has %d items, needs 15-30" % len(items))
        names = set()
        products_with_variants = 0
        n_products = 0
        for i, it in enumerate(items):
            w = "%s.items[%d]" % (where, i)
            name = it.get("name")
            if not isinstance(name, str) or not name or len(name) > 32 \
                    or name != name.strip() or "|" in name or "\n" in name \
                    or any(sep in name for sep in (" - ", " – ", " / ")):
                p.add(w, "bad name %r" % (name,))
            key = (name or "").casefold()
            if key in names:
                p.add(w, "duplicate name %r" % name)
            names.add(key)
            if it.get("kind") not in ("product", "service"):
                p.add(w, "kind must be product or service")
            if it.get("category") not in cats:
                p.add(w, "category %r not in categories" % it.get("category"))
            usd = it.get("usd")
            if not (isinstance(usd, list) and len(usd) == 2 and
                    all(isinstance(x, (int, float)) for x in usd) and
                    0 < usd[0] <= usd[1]):
                p.add(w, "usd must be [low, high] with 0 < low <= high")
            if it.get("unit") not in UNITS:
                p.add(w, "unknown unit %r" % it.get("unit"))
            if it.get("kind") == "service":
                m = it.get("minutes")
                if not (isinstance(m, list) and len(m) == 2 and
                        all(isinstance(x, int) for x in m) and
                        5 <= m[0] <= m[1] <= 480):
                    p.add(w, "services need minutes [low, high], 5-480")
                if it.get("variants"):
                    p.add(w, "variants are for products only")
            else:
                n_products += 1
                if it.get("variants"):
                    products_with_variants += 1
                    vs = it["variants"]
                    if not (isinstance(vs, list) and 2 <= len(vs) <= 4):
                        p.add(w, "variants: 2 to 4 labels")
                    else:
                        check_strings(p, w + ".variants", vs, 2, 20)
        if n_products >= 8 and products_with_variants < 3:
            p.add(where, "give variants to at least 3 products")


def validate(folder):
    p = Problems()
    check_headers(folder, p)
    check_values(folder, p)
    check_activities(folder, p)
    return p


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    folders = sys.argv[1:] or FOLDERS
    bad = 0
    for folder in folders:
        problems = validate(folder)
        if problems:
            bad += 1
            print("%s: %d problem(s)" % (folder, len(problems)))
            for line in problems[:80]:
                print("  " + line)
        else:
            print("%s: OK" % folder)
    sys.exit(1 if bad else 0)
