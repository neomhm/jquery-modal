"""
gen/columns.py - the records of each target and the columns that show
them, shared by the layout families.

Each `*_records` function draws the TRUE rows of a table. Each column
builder adds one Column to a Table, one program line (with the column's
KEY in braces in place of its letter) and the matching true values.
"""
import datetime
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
    """[{name, variant, category, price, stock, ...}] - true rows."""
    rng = ctx.rng
    items = ctx.items("product")
    if not items:
        return []
    combos = []
    for it in items:
        if with_variants and it.get("variants"):
            for k, v in enumerate(it["variants"]):
                combos.append((it, v, k))
        else:
            combos.append((it, None, 0))
    if with_variants:
        combos = [c for c in combos if c[1] is not None] or combos
    rng.shuffle(combos)
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
    for i, (it, variant, k) in enumerate(combos):
        if it["name"] not in base_prices:
            base_prices[it["name"]] = ctx.price(it["usd"])
        base = base_prices[it["name"]]
        factor = [1.0, 1.35, 1.7, 2.1][k] if variant else 1.0
        price = base if not variant else \
            ctx_price_scaled(ctx, base, factor)
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


def ctx_price_scaled(ctx, base, factor):
    from gen.ctx import nice_price
    return nice_price(base * factor, ctx.loc["cents"], ctx.rng)


# =====================================================================
#  services
# =====================================================================
def service_records(ctx, n):
    rng = ctx.rng
    items = ctx.items("service")
    if not items:
        return []
    items = list(items)
    rng.shuffle(items)
    items = items[:n]
    cats = ctx.words.get("categories") or []
    order = dict((c, i) for i, c in enumerate(cats))
    if rng.random() < 0.7:
        items.sort(key=lambda it: order.get(it.get("category"), 99))
    staff = [ctx.person() for _ in range(rng.randint(2, 5))]
    vat = ctx.vat()
    out = []
    for it in items:
        lo, hi = it.get("minutes") or [30, 60]
        minutes = rng.randint(lo, hi)
        minutes = max(5, int(round(minutes / 5.0)) * 5)
        if minutes > 60:
            minutes = int(round(minutes / 15.0)) * 15
        if lo >= 480:
            minutes = None        # a night, a project: no real duration
        price = ctx.price(it["usd"])
        who = rng.choice(staff)
        out.append({"name": it["name"], "category": it.get("category"),
                    "price": price, "price_excl": ctx.excl(price, vat),
                    "vat_rate": vat, "duration_min": minutes,
                    "staff": who["full"], "staff_person": who,
                    "unit": it.get("unit") or "session"})
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
    choice = ctx.rng.choice(variants)
    text = ctx._decorate(choice)
    if choice == d and text is not None:
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
