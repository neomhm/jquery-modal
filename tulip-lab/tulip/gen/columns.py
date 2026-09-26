"""
gen/columns.py - the records of each target and the columns that show
them, shared by the layout families.

Each `*_records` function draws the TRUE rows of a table. Each column
builder adds one Column to a Table, one program line (with the column's
KEY in braces in place of its letter) and the matching true values.
"""
import datetime
import math
import re
import string

import helpers as H
from gen.sheetkit import Column

REF_TIME = datetime.time


# =====================================================================
#  small helpers
# =====================================================================
def norm_text(value):
    """The value text() gives for a cell (the truth of text fields)."""
    ok, out = H.text(value, None)
    return out if ok else None


def noisy_text(ctx, text):
    """Leading / trailing spaces now and then (section 10.5)."""
    r = ctx.rng.random()
    if r < 0.04:
        return " " + text
    if r < 0.08:
        return text + " "
    return text


def digit_mode(ctx):
    """Arabic-Indic or full-width digits for the text cells of one
    column (section 10.5)."""
    d = ctx.loc.get("digits") or {}
    if "arab" in d and ctx.rng.random() < d["arab"]:
        return "arab"
    if "full" in d and ctx.rng.random() < d["full"]:
        return "full"
    return None


def apply_digits(ctx, value, mode):
    if mode and isinstance(value, str):
        return ctx.fmt.digits(value, mode == "arab", mode == "full")
    return value


def sku_maker(ctx):
    rng = ctx.rng
    style = rng.choice(["LN", "LNN", "N", "L-N", "LLL-N", "YN"])
    letters = "".join(rng.choice(string.ascii_uppercase)
                      for _ in range(rng.choice([1, 2, 3])))
    start = rng.randint(1, 900)
    width = rng.choice([2, 3, 4, 5])
    used = set()

    def make(i, cat_index=0):
        n = start + i * rng.choice([1, 1, 1, 2, 5, 10])
        if style == "LN":
            s = "%s%0*d" % (letters, width, n)
        elif style == "LNN":
            s = "%s-%0*d" % (letters, width, n)
        elif style == "N":
            s = "%0*d" % (max(width, 4), n + 1000 * (cat_index + 1))
        elif style == "L-N":
            s = "%s-%d" % (string.ascii_uppercase[cat_index % 26], n)
        elif style == "LLL-N":
            s = "%s-%04d" % (letters, n)
        else:
            s = "%d%04d" % (ctx_year(ctx) % 100, n)
        while s in used:
            s += "A"
        used.add(s)
        return s
    return make


def ctx_year(ctx):
    return 2026


def ean13(rng):
    body = [rng.randint(0, 9) for _ in range(12)]
    body[0] = rng.choice([3, 4, 5, 7, 8, 9])
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(body))
    return "".join(map(str, body)) + str((10 - total % 10) % 10)


def unit_word(ctx, unit_key):
    words = (ctx.values.get("units") or {}).get(unit_key) or [unit_key]
    return ctx.rng.choice(words)


# =====================================================================
#  products
# =====================================================================
def product_records(ctx, n, with_variants=False, grouped=False):
    """[{name, variant, category, price, stock, ...}] - true rows.

    A sheet longer than the activity has items (section 10.3: 3-400
    rows, the spec's own example is a 300-line catalogue) lists the same
    items in several quantities, as trade catalogues do: pack counts,
    weights, volumes or lengths, written with the language's own unit
    words (values.json "units"). Such a line keeps its item's name and
    has its quantity as its variant ("12 pce", "500 g", "1 L")."""
    rng = ctx.rng
    items = ctx.items("product")
    if not items:
        return []
    combos = []
    for it in items:
        if with_variants and it.get("variants"):
            for k, v in enumerate(it["variants"]):
                combos.append((it, v, k, None))
        else:
            combos.append((it, None, 0, None))
    if with_variants:
        combos = [c for c in combos if c[1] is not None] or combos
    rng.shuffle(combos)
    if n > len(combos):
        extra = quantity_lines(ctx, items, combos)
        rng.shuffle(extra)
        combos += extra[:n - len(combos)]
    combos = combos[:n]
    # keep the categories together (price lists are grouped)
    cats = ctx.words.get("categories") or []
    order = dict((c, i) for i, c in enumerate(cats))
    if grouped or rng.random() < 0.7:
        combos.sort(key=lambda c: (order.get(c[0].get("category"), 99),
                                   items.index(c[0]), c[2]))
    vat = ctx.vat()
    make_sku = sku_maker(ctx)
    out = []
    base_prices = {}
    for i, (it, variant, k, factor) in enumerate(combos):
        if it["name"] not in base_prices:
            base_prices[it["name"]] = ctx.price(it["usd"])
        base = base_prices[it["name"]]
        if factor is not None:
            price = ctx_price_scaled(ctx, base, factor)
        elif variant:
            price = ctx_price_scaled(ctx, base, [1.0, 1.35, 1.7, 2.1][
                min(k, 3)])
        else:
            price = base
        cost = round(price * rng.uniform(0.35, 0.7),
                     2 if ctx.loc["cents"] else 0)
        out.append({
            "name": it["name"], "variant": variant,
            "category": it.get("category"),
            "cat_index": order.get(it.get("category"), 0),
            "price": price, "price_excl": ctx.excl(price, vat),
            "vat_rate": vat, "cost": float(cost),
            "stock": rng.choice([0, rng.randint(1, 20), rng.randint(5, 120),
                                 rng.randint(50, 2500)]),
            "qty_ordered": rng.randint(1, 60),
            "sku": make_sku(i, order.get(it.get("category"), 0)),
            "unit": it.get("unit") or "piece",
            "barcode": ean13(rng), "active": rng.random() < 0.85,
            "usd": it["usd"]})
    return out


# quantities of a catalogue line: (number, unit key, factor on the price
# of the item's own unit). Whole numbers only.
PACK_COUNTS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 24, 25, 30, 36,
               40, 48, 50, 60, 72, 80, 100, 120, 144, 150, 200, 250, 500]
WEIGHTS = [(50, "g"), (100, "g"), (125, "g"), (150, "g"), (200, "g"),
           (250, "g"), (300, "g"), (400, "g"), (500, "g"), (750, "g"),
           (1, "kg"), (2, "kg"), (3, "kg"), (5, "kg"), (10, "kg"),
           (15, "kg"), (20, "kg"), (25, "kg")]
VOLUMES = [(50, "ml"), (100, "ml"), (150, "ml"), (200, "ml"), (250, "ml"),
           (330, "ml"), (500, "ml"), (750, "ml"), (1, "l"), (2, "l"),
           (3, "l"), (5, "l"), (10, "l"), (20, "l")]
LENGTHS = [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 25, 30, 50, 100]
TIME_COUNTS = {"month": [2, 3, 4, 6, 9, 12, 18, 24, 36],
               "day": [2, 3, 4, 5, 7, 10, 14, 20, 30],
               "hour": [2, 3, 4, 5, 8, 10, 12, 20, 40],
               "session": [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30]}
PER_UNIT = ("par ", "per ", "a ", "al ", "all'", "le ", "l'", "por ",
            "प्रति", "لل", "p.p", "cad", "each", "ea", "mensu", "mensi",
            "شهري", "يومي", "月額", "a persona", "a testa")


# nouns that would need a plural after a number, and per-unit forms
NOT_AFTER_A_NUMBER = {"box", "set", "kit", "day", "pp", "ea", "mes", "dia",
                      "día", "ora", "час", "hora", "item", "unit"}


def count_word(ctx, unit_key):
    """The word written after a number for this unit ('12 pce', '500 g',
    '12個'), one per unit and sheet. Latin and Cyrillic scripts: an
    abbreviation only (at most 3 letters, or ending with a dot), because
    a full noun would need its plural; Hindi: no noun whose plural
    changes its -ā ending; never a per-unit form ('par personne',
    'each', 'للساعة'), never a word that starts with a number ('1시간')."""
    cache = ctx.__dict__.setdefault("_count_words", {})
    if unit_key in cache:
        return cache[unit_key]
    words = []
    for w in (ctx.values.get("units") or {}).get(unit_key) or []:
        low = w.casefold()
        if not w or w[0].isdigit() or " " in w or \
                any(low.startswith(p) for p in PER_UNIT) or \
                low in NOT_AFTER_A_NUMBER:
            continue
        alphabetic = all(ord(ch) < 0x0530 for ch in w)
        if alphabetic and ctx.lang not in ("zh", "ja", "ko") and \
                not (len(w) <= 3 or w.endswith(".")):
            continue
        if ctx.lang == "hi" and w.endswith("\u093e"):
            continue
        words.append(w)
    cache[unit_key] = ctx.rng.choice(words) if words else None
    return cache[unit_key]


def qty_text(ctx, number, word):
    """'12 pce', '500 g', '12個' (CJK: no space before a CJK word)."""
    cjk = ctx.lang in ("zh", "ja", "ko") and not word[:1].isascii()
    return "%d%s%s" % (number, "" if cjk else " ", word)


def quantity_options(ctx, it):
    """[(quantity text, k, price factor)] of one item, or [] when its own
    variants are quantities already ('100 шт.', '500 g')."""
    if any(ch.isdigit() for v in it.get("variants") or [] for ch in v):
        return more_of_its_quantities(it)
    unit = it.get("unit") or "piece"
    if unit in ("kg", "g"):
        ref = 1000.0 if unit == "kg" else 100.0
        options = [(q, u, ((q * (1000 if u == "kg" else 1)) / ref) ** 0.95)
                   for q, u in WEIGHTS]
    elif unit in ("l", "ml"):
        ref = 1000.0 if unit == "l" else 100.0
        options = [(q, u, ((q * (1000 if u == "l" else 1)) / ref) ** 0.95)
                   for q, u in VOLUMES]
    elif unit == "m":
        options = [(q, "m", q ** 0.97) for q in LENGTHS]
    elif unit in TIME_COUNTS:
        options = [(q, unit, q ** 0.92) for q in TIME_COUNTS[unit]]
    else:
        u = unit if unit in ("piece", "box", "pack", "set",
                             "person") else "piece"
        options = [(q, u, q ** 0.93) for q in PACK_COUNTS]
    out = []
    for k, (q, u, factor) in enumerate(options):
        word = count_word(ctx, u)
        if word:
            out.append((qty_text(ctx, q, word), 10 + k, factor))
    return out


LADDER = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 25, 30, 40, 50, 60, 75,
          100, 120, 150, 200, 250, 300, 400, 500, 600, 750, 1000, 1500,
          2000, 2500, 3000, 5000, 10000]
QTY = re.compile(r"^(\d+)(\s*)(\D+)$")


def more_of_its_quantities(it):
    """An item whose own variants are quantities of ONE unit written the
    same way ('100 шт.', '500 шт.', '1000 шт.'): more quantities of that
    unit, written the same way, near its own range. [] otherwise."""
    parts = [QTY.match(v.strip()) for v in it.get("variants") or []]
    if not parts or not all(parts) or \
            len(set((m.group(2), m.group(3)) for m in parts)) != 1:
        return []
    have = [int(m.group(1)) for m in parts]
    q0, sp, word = have[0], parts[0].group(2), parts[0].group(3)
    if q0 <= 0:
        return []
    lo, hi = min(have) / 4.0, max(have) * 10.0
    # the price grows the way its own variants' prices grow (their
    # factors in product_records: 1, 1.35, 1.7, 2.1)
    last = len(have) - 1
    alpha = 0.9
    if have[last] != q0 and last > 0:
        alpha = math.log([1.0, 1.35, 1.7, 2.1][min(last, 3)]) / \
            math.log(have[last] / float(q0))
        alpha = max(0.2, min(1.0, abs(alpha)))
    out = []
    for k, q in enumerate(LADDER):
        if lo <= q <= hi and q not in have:
            out.append(("%d%s%s" % (q, sp, word), 10 + k,
                        (q / float(q0)) ** alpha))
    return out


def quantity_lines(ctx, items, taken):
    """More lines for a long catalogue: [(item, quantity text, k,
    price factor)] that no drawn line already has."""
    have = set((c[0]["name"], c[1]) for c in taken)
    out = []
    for it in items:
        for text, k, factor in quantity_options(ctx, it):
            if (it["name"], text) in have:
                continue
            have.add((it["name"], text))
            out.append((it, text, k, factor))
    return out


def with_quantity(ctx, name, variant):
    """A catalogue line shown in one cell: 'Croissant 12 pce'."""
    return "%s %s" % (name, variant) if variant else name


def ctx_price_scaled(ctx, base, factor):
    from gen.ctx import nice_price
    return nice_price(base * factor, ctx.loc["cents"], ctx.rng)


# =====================================================================
#  services
# =====================================================================
def service_records(ctx, n, packages=True):
    """[{name, category, price, duration_min, staff, ...}] - true rows.

    A list longer than the activity has services sells the same service
    for several durations ('Massage' 30 / 45 / 60 / 90 min, flag
    "timed") and as packages of several hours, days or visits, named with
    the language's own unit words ('Cours particulier 10 h')."""
    rng = ctx.rng
    items = ctx.items("service")
    if not items:
        return []
    items = list(items)
    rng.shuffle(items)
    lines = [(it, None, None, 0) for it in items]
    if n > len(lines):
        extra = service_lines(ctx, items)
        if not packages:
            # every line needs a duration (the duration is written
            # inside the name): other lengths only, no packages
            extra = [e for e in extra if e[1] is not None]
        rng.shuffle(extra)
        chosen, rest = extra[:n - len(lines)], extra[n - len(lines):]
        # a service sold at several lengths is listed by length only (no
        # extra line with a length drawn at random between them)
        timed = set(id(e[0]) for e in chosen if e[1] is not None)
        lines = [ln for ln in lines if id(ln[0]) not in timed] + chosen
        for e in rest:
            if len(lines) >= n:
                break
            if e[1] is None or id(e[0]) in timed:
                lines.append(e)
    lines = lines[:n]
    cats = ctx.words.get("categories") or []
    order = dict((c, i) for i, c in enumerate(cats))
    if rng.random() < 0.7 or len(lines) > len(items):
        pos = dict((it["name"], i) for i, it in enumerate(items))
        lines.sort(key=lambda ln: (order.get(ln[0].get("category"), 99),
                                   pos[ln[0]["name"]], ln[3]))
    staff = [ctx.person() for _ in range(rng.randint(2, 5))]
    vat = ctx.vat()
    out = []
    base_prices = {}
    for it, minutes_fixed, pack, _ in lines:
        lo, hi = it.get("minutes") or [30, 60]
        if it["name"] not in base_prices:
            base_prices[it["name"]] = ctx.price(it["usd"])
        base = base_prices[it["name"]]
        name, timed = it["name"], False
        if minutes_fixed is not None:
            minutes, timed = minutes_fixed, True
            mid = max(15.0, (lo + hi) / 2.0)
            price = ctx_price_scaled(ctx, base, (minutes / mid) ** 0.9)
        elif pack is not None:
            text, factor = pack
            name = with_quantity(ctx, it["name"], text)
            minutes = None        # a package of several visits
            price = ctx_price_scaled(ctx, base, factor)
        else:
            minutes = rng.randint(lo, hi)
            minutes = max(5, int(round(minutes / 5.0)) * 5)
            if minutes > 60:
                minutes = int(round(minutes / 15.0)) * 15
            if lo >= 480:
                minutes = None    # a night, a project: no real duration
            price = base
        who = rng.choice(staff)
        out.append({"name": name, "category": it.get("category"),
                    "price": price, "price_excl": ctx.excl(price, vat),
                    "vat_rate": vat, "duration_min": minutes,
                    "timed": timed,
                    "staff": who["full"], "staff_person": who,
                    "unit": it.get("unit") or "session"})
    # one line per (name, duration): the first line of a service drew
    # its duration at random, and a timed line of the same length goes
    seen, keep = set(), []
    for r in out:
        k = (r["name"], r["duration_min"])
        if k in seen:
            continue
        seen.add(k)
        keep.append(r)
    return keep


def service_lines(ctx, items):
    """More lines for a long list: (item, minutes, None, k) for other
    durations and (item, None, (text, price factor), k) for packages."""
    out = []
    for it in items:
        lo, hi = it.get("minutes") or [30, 60]
        if lo < 480:
            first = max(15, int(lo // 2 // 15) * 15)
            last = min(480, max(hi * 3, lo + 60))
            steps = list(range(first, last + 1, 15))
            for k, m in enumerate(steps):
                out.append((it, m, None, 1 + k))
        unit = it.get("unit") or "session"
        if unit in ("hour", "day", "month", "person", "session", "set"):
            word = count_word(ctx, unit)
            if word:
                counts = TIME_COUNTS.get(unit) or \
                    [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40, 50]
                for k, q in enumerate(counts):
                    out.append((it, None, (qty_text(ctx, q, word),
                                           q ** 0.92), 100 + k))
    return out


# =====================================================================
#  generic columns
# =====================================================================
def text_column(ctx, table, key, header, texts, field=None, truth=None,
                noise=True, digits=True):
    """A text column; when `field` is given, out.field = text(col(key))
    and the truth of each record is the normalized text."""
    mode = digit_mode(ctx) if digits else None
    cells = []
    for t in texts:
        if t is None or t == "":
            cells.append(None)
            continue
        v = noisy_text(ctx, t) if noise else t
        cells.append(apply_digits(ctx, v, mode))
    col = table.add(Column(key, header, cells))
    # digits=False: sheetkit's digit pass decides (it checks the truth)
    col.digits_done, col.digit_mode = digits, mode
    if field:
        table.outs.append((field, "text(col({%s}))" % key))
        for rec, cell in zip(truth, cells):
            v = norm_text(cell) if cell is not None else None
            if v is not None:
                rec[field] = v
    return col


def money_column(ctx, table, key, header, amounts, field, truth,
                 show="cell"):
    """An amount column. show: 'cell' (symbol in text cells), 'format'
    (xlsx number format with the currency), 'none' (plain numbers)."""
    f = ctx.fmt
    cells, fmts = [], []
    mode = digit_mode(ctx)
    for a in amounts:
        if a is None:
            cells.append(None)
            fmts.append(None)
            continue
        if f.typed:
            v, fm = f.money(a, fmt_currency=(show == "format"))
        else:
            v, fm = f.money(a, symbol=(show == "cell"))
            v = apply_digits(ctx, v, mode)
        cells.append(v)
        fmts.append(fm)
    col = table.add(Column(key, header, cells, fmts))
    col.symbol = show == "cell" and not f.typed
    col.digits_done, col.digit_mode = True, (mode if not f.typed else None)
    if field:
        table.outs.append((field, "amount(col({%s}))" % key))
        for rec, a in zip(truth, amounts):
            if a is not None:
                rec[field] = float(a)
    return col


def integer_column(ctx, table, key, header, numbers, field, truth,
                   unit=None):
    f = ctx.fmt
    cells, fmts = [], []
    for n in numbers:
        if n is None:
            cells.append(None)
            fmts.append(None)
            continue
        v, fm = f.integer(n, unit)
        cells.append(v)
        fmts.append(fm)
    col = table.add(Column(key, header, cells, fmts))
    if field:
        table.outs.append((field, "integer(col({%s}))" % key))
        for rec, n in zip(truth, numbers):
            if n is not None:
                rec[field] = int(n)
    return col


def percent_column(ctx, table, key, header, rates, field, truth):
    f = ctx.fmt
    cells, fmts = [], []
    for r in rates:
        v, fm = f.percent(r)
        cells.append(v)
        fmts.append(fm)
    table.add(Column(key, header, cells, fmts))
    table.outs.append((field, "percent(col({%s}))" % key))
    for rec, r in zip(truth, rates):
        rec[field] = round(r, 6)


def boolean_column(ctx, table, key, header, flags, field, truth):
    """yes/no words, marks or typed booleans; always boolean(col())."""
    f, rng = ctx.fmt, ctx.rng
    code = ctx.code
    style = rng.choice(["words", "words", "marks", "typed", "digits"])
    if style == "typed" and not f.typed:
        style = "words"
    yes = [w for w in ctx.values.get("yes") or []
           if H.boolean(w, code) == (True, True)]
    no = [w for w in ctx.values.get("no") or []
          if H.boolean(w, code) == (True, False)]
    if not yes or not no:
        style = "digits"
    cells = []
    if style == "words":
        pair = (rng.choice(yes), rng.choice(no))
        cells = [pair[0] if b else pair[1] for b in flags]
    elif style == "marks":
        if ctx.lang in ("zh", "ja", "ko"):
            t, fl = rng.choice([("○", "×"), ("O", "X"), ("√", "×")])
        else:
            t, fl = rng.choice([("✓", "✗"), ("x", None), ("X", None),
                                ("✔", "✘")])
        cells = [t if b else fl for b in flags]
    elif style == "typed":
        cells = [bool(b) for b in flags]
    else:
        cells = ["1" if b else "0" for b in flags] if not f.typed \
            else [1 if b else 0 for b in flags]
    table.add(Column(key, header, cells))
    table.outs.append((field, "boolean(col({%s}))" % key))
    for rec, b, cell in zip(truth, flags, cells):
        if cell is not None:
            rec[field] = bool(b)


# =====================================================================
#  the price block (products, services): one or two prices, where the
#  currency shows, tax_included from the header
# =====================================================================
# "from" words written after the price (3,000円〜, 35元起, 5万원부터)
SUFFIX_FROM = ("起", "〜", "～", "~", "から", "より", "부터", "से", "से शुरू")


def from_text(ctx, word, cell):
    if word in SUFFIX_FROM or ctx.lang in ("ja", "ko"):
        return "%s%s" % (cell, word) if ctx.lang in ("zh", "ja", "ko") \
            else "%s %s" % (cell, word)
    return "%s %s" % (word, cell)


def header_with_cur(ctx, key):
    variants = [v for v in ctx.hdr.get(key) or [] if "{cur}" in v]
    d = ctx._held(key).get("D")
    if ctx.split != "dev_heldout":
        variants = [v for v in variants if v != d]
    if not variants:
        return None
    text = ctx.pick_allowed(variants, ctx._decorate)
    if text is not None and ctx.held_groups(text):
        ctx.use("D", text)
    return text


def price_block(ctx, table, recs, truth, plan, field="price",
                allow_from=False, tax=True):
    """Adds the price column(s) and the currency / tax_included lines.
    tax=False: a table with no tax_included field (bookings): one plain
    price column. Returns the key of the column that holds `field`."""
    rng = ctx.rng
    traps = plan["traps"]
    two = "T2" in traps and tax
    t13 = "T13" in traps
    typed = ctx.typed
    # where the currency shows
    if t13:
        show = "format" if typed and rng.random() < 0.5 else "none"
        header_cur = show == "none" or rng.random() < 0.4
    else:
        show = rng.choice(["cell", "cell", "none"]) if not typed else \
            rng.choice(["none", "none", "format"])
        header_cur = False
        if show == "format":
            table.traps.add("T13")
    if two:
        h_excl = header_with_cur(ctx, "price_excl") if header_cur else None
        h_incl = header_with_cur(ctx, "price_incl") if header_cur else None
        if header_cur and (not h_excl or not h_incl):
            header_cur, show = False, ("cell" if not typed else "format")
        h_excl = h_excl or ctx.header("price_excl", cur=False)
        h_incl = h_incl or ctx.header("price_incl", cur=False)
        if H.tax_included(h_incl, ctx.code) != (True, True) or \
                H.tax_included(h_excl, ctx.code) != (True, False):
            two = False
    if two:
        money_column(ctx, table, "price_excl", h_excl,
                     [r["price_excl"] for r in recs], None, truth, show)
        money_column(ctx, table, "price", h_incl,
                     [r["price"] for r in recs], field, truth, show)
        table.blocks.append(["price_excl", "price"] if rng.random() < 0.8
                            else ["price", "price_excl"])
        tax_value = True
        table.traps.add("T2")
    else:
        kind = rng.choice(["price", "price", "price", "price_incl",
                           "price_excl"]) if tax else "price"
        header = header_with_cur(ctx, kind) if header_cur else None
        if header_cur and not header:
            header_cur = False
            if show == "none":
                show = "cell" if not typed else "format"
        header = header or ctx.header(kind, cur=False) or \
            ctx.header_plain("price")
        ok, tax_value = H.tax_included(header, ctx.code)
        if not ok or not tax:
            tax_value = None
        amounts = [r["price_excl"] if tax_value is False else r["price"]
                   for r in recs]
        col = money_column(ctx, table, "price", header, amounts, field,
                           truth, show)
        if allow_from and not typed and show != "format" and \
                rng.random() < 0.3:
            words = list(ctx.values.get("from_words") or [])
            if words:
                word = rng.choice(words)
                for i, (c, a) in enumerate(zip(col.cells, amounts)):
                    if c is None or rng.random() < 0.5:
                        continue
                    text = from_text(ctx, word, c)
                    if H.amount(text, ctx.code) == (True, float(a)):
                        col.cells[i] = text
    # a header that shows a currency is always used (the model sees it)
    ok, cur = H.currency(table.col("price").header, ctx.code)
    if ok and cur != ctx.loc["currency"]:
        return None
    header_cur = ok
    # currency: the sources that show it, in the order cell, format, header
    sources = []
    if show == "cell" and not typed:
        sources.append("currency(col({price}))")
    if show == "format" and typed:
        sources.append("currency(format_of({price}))")
    if header_cur:
        sources.append("currency(header_of({price}))")
        if show != "cell":
            table.traps.add("T13")
    if sources:
        expr = sources[0] if len(sources) == 1 else \
            "first(%s)" % ", ".join(sources)
        table.outs.append(("currency", expr))
        for rec in truth:
            # header_of() answers on every row, even without a price
            if field in rec or header_cur:
                rec["currency"] = ctx.loc["currency"]
    if tax_value is not None:
        table.outs.append(("tax_included", "tax_included(header_of({price}))"))
        for rec in truth:
            rec["tax_included"] = tax_value
    return "price"
