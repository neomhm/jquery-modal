"""
gen/builders.py - one builder per target. A layout family
(gen/layouts/<family>.py) calls its target's builder with the features
that make the family what it is (sizes as columns, section rows, a
two-row header...). The traps drawn for the task (plan["traps"]) are
added on top when the family allows them.

Every builder returns a sheetkit.Table (columns, program lines with
column keys, true rows) or None when this activity / locale cannot make
that layout (the task is then drawn again).
"""
import datetime

import helpers as H
from gen import columns as C
from gen import modifiers as M
from gen.sheetkit import Column, Table

REF = datetime.date(2026, 6, 30)
SEPARATORS = [" – ", " - ", " / ", " | "]


def part_separator(ctx, values):
    """A separator that occurs in none of the values."""
    options = [" – ", " - ", " / ", ", "]
    ctx.rng.shuffle(options)
    for sep in options:
        if not any(sep in v for v in values if v):
            return sep
    return None


def add_sections(ctx, t, titles, truth, field):
    """Section rows before each run of equal titles (one title per
    record); out.field = text(col('section')). -> [(title, [record
    indexes])] or None when the runs are too short to be sections."""
    rng = ctx.rng
    upper = rng.random() < 0.4 and ctx.lang in ("fr", "en", "es", "it",
                                                 "ru")
    groups = []
    for i, title in enumerate(titles):
        if not title:
            return None
        if i == 0 or title != titles[i - 1]:
            shown = title.upper() if upper else title
            groups.append((shown, [i]))
        else:
            groups[-1][1].append(i)
    if len(groups) < 2 or len(groups) > len(titles) / 2:
        return None
    for shown, idx in groups:
        t.sections.append((idx[0], shown))
        for i in idx:
            truth[i][field] = C.norm_text(shown)
    t.outs.append((field, "text(col('section'))"))
    t.traps.add("T7")
    return groups


def trap_columns(ctx, table, recs, kinds):
    """Columns that look like fields but are not (T1 cost, T3 quantities,
    margin, supplier reference, notes, discount)."""
    rng, f = ctx.rng, ctx.fmt
    for kind in kinds:
        header = ctx.trap_header(kind)
        if kind == "cost":
            C.money_column(ctx, table, "cost", header,
                           [r["cost"] for r in recs], None, [],
                           "cell" if not f.typed and rng.random() < 0.5
                           else "none")
            table.col("cost").kind = "trap"
            table.traps.add("T1")
        elif kind in ("qty_ordered", "qty_sold"):
            C.integer_column(ctx, table, kind, header,
                             [r["qty_ordered"] for r in recs], None, [])
            table.col(kind).kind = "trap"
            table.traps.add("T3")
        elif kind == "margin":
            margins = [round(r["price"] - r["cost"], 2) for r in recs]
            C.money_column(ctx, table, "margin", header, margins, None, [],
                           "none")
            table.col("margin").kind = "trap"
        elif kind == "discount":
            rates = [rng.choice([0, 0, 0.05, 0.1, 0.15]) for _ in recs]
            cells = [f.percent(x)[0] if x else None for x in rates]
            if all(c is None for c in cells):
                cells[0] = f.percent(0.1)[0]
            table.add(Column("discount", header, cells, kind="trap"))
        elif kind == "supplier_ref":
            cells = ["%s-%05d" % (rng.choice(["FRN", "SUP", "F", "P"]),
                                  rng.randint(1, 99999)) for _ in recs]
            table.add(Column("supplier_ref", header, cells, kind="trap"))
        elif kind == "internal_notes":
            pool = (ctx.values.get("not_a_table") or {}).get("notes_page") \
                or [ctx.word("hours_notes") or "-"]
            notes = [rng.choice(pool) for _ in range(3)]
            cells = [rng.choice(notes) if rng.random() < 0.3 else None
                     for _ in recs]
            if all(c is None for c in cells):
                cells[0] = notes[0]
            table.add(Column("internal_notes", header, cells, kind="trap"))


# =====================================================================
#  products
# =====================================================================
def products(ctx, plan, *, name_size=False, size_columns=False,
             sections=False, two_row=False, catalogue=False,
             inventory=False, export=False, category_sheet=False,
             force_two_prices=False, force_traps=()):
    rng = ctx.rng
    traps = set(plan["traps"]) | set(force_traps)
    if force_two_prices:
        traps.add("T2")
    plan = dict(plan, traps=traps)
    n = plan["n"]
    # traps drawn for the task that this family can also show
    plain = not (name_size or size_columns or two_row or category_sheet or
                 sections)
    variants = sum(1 for it in ctx.items("product") if it.get("variants"))
    drawn_sections = False
    if plain and "T8" in traps and variants >= 2:
        size_columns = True
    elif plain and "T9" in traps and variants >= 2:
        name_size = True
    if not (sections or size_columns or category_sheet) and "T7" in traps:
        sections, drawn_sections = True, True
    if size_columns:
        return products_size_columns(ctx, plan, sections)
    recs = C.product_records(ctx, n, with_variants=name_size,
                             grouped=sections)
    if len(recs) < 2:
        return None
    if category_sheet:
        # one sheet per category: keep the biggest category that can be a
        # sheet name (at most 31 characters, none of []:*?/\\)
        counts = {}
        for r in C.product_records(ctx, 400):
            counts.setdefault(r["category"], []).append(r)
        good = [(len(v), k) for k, v in counts.items()
                if k and len(k) <= 31 and not any(ch in k for ch in
                                                  "[]:*?/\\")]
        if not good:
            return None
        cat = max(good)[1]
        recs = counts[cat][:n]
    t = Table("products")
    truth = [{} for _ in recs]
    # ---- name (and size in the same cell)
    names = [r["name"] for r in recs]
    if name_size:
        if not all(r["variant"] for r in recs):
            return None
        sep = part_separator(ctx, names + [r["variant"] for r in recs])
        if sep is None:
            return None
        cells = ["%s%s%s" % (r["name"], sep, r["variant"]) for r in recs]
        header = ctx.header("product_name")
        t.add(Column("name", header, [C.noisy_text(ctx, c) for c in cells]))
        t.outs.append(("name", "text(part(col({name}), %r, 0))" % sep))
        t.outs.append(("variant", "text(part(col({name}), %r, 1))" % sep))
        for rec, r in zip(truth, recs):
            rec["name"] = C.norm_text(r["name"])
            rec["variant"] = C.norm_text(r["variant"])
        t.traps.add("T9")
    else:
        show_variant = any(r["variant"] for r in recs) and \
            rng.random() < 0.8
        if not show_variant:
            # no variant column: a catalogue line's quantity is part of
            # its name ('Croissant 12 pce'), so every line stays distinct
            names = [C.with_quantity(ctx, r["name"], r["variant"])
                     for r in recs]
        C.text_column(ctx, t, "name", ctx.header("product_name"), names,
                      "name", truth)
        if show_variant:
            C.text_column(ctx, t, "variant", ctx.header("variant"),
                          [r["variant"] for r in recs], "variant", truth)
    # ---- the sku
    want_sku = catalogue or inventory or export or rng.random() < 0.55
    if want_sku:
        C.text_column(ctx, t, "sku", ctx.header("sku"),
                      [r["sku"] for r in recs], "sku", truth, noise=False)
        if rng.random() < 0.7:
            t.blocks.append(["sku", "name"])
    # ---- category: section rows, a column, or the sheet's name
    cats = [r["category"] for r in recs]
    if sections:
        groups = []
        for i, r in enumerate(recs):
            if i == 0 or r["category"] != recs[i - 1]["category"]:
                title = r["category"]
                if rng.random() < 0.4 and ctx.lang in ("fr", "en", "es",
                                                       "it", "ru"):
                    title = title.upper()
                t.sections.append((i, title))
                groups.append(title)
        if len(t.sections) < 2 or len(t.sections) > len(recs) / 2:
            if not drawn_sections:
                return None
            t.sections, sections = [], False
    if sections:
        t.outs.append(("category", "text(col('section'))"))
        current = None
        section_at = dict(t.sections)
        for i, rec in enumerate(truth):
            current = section_at.get(i, current)
            rec["category"] = C.norm_text(current)
        t.traps.add("T7")
        t.first_column_fixed = ["name"]
    elif category_sheet:
        t.outs.append(("category", "text(sheet_title())"))
        for rec in truth:
            rec["category"] = C.norm_text(cats[0])
    elif catalogue or export or rng.random() < 0.35:
        C.text_column(ctx, t, "category", ctx.header("category"), cats,
                      "category", truth)
    # ---- price(s), currency, tax_included
    C.price_block(ctx, t, recs, truth, plan)
    # ---- more fields
    if catalogue or export or rng.random() < 0.15:
        C.percent_column(ctx, t, "vat_rate", ctx.header("vat_rate"),
                         [r["vat_rate"] for r in recs], "vat_rate", truth)
    if catalogue or inventory or export or rng.random() < 0.35:
        units = rng.random() < 0.3 and not export
        unit_words = [C.unit_word(ctx, r["unit"]) for r in recs]
        stocks = [r["stock"] for r in recs]
        if any(u[:1].isdigit() for u in unit_words):
            units = False           # '90 1인' is not a count of 90
        if units and not ctx.typed:
            cells = ["%s %s" % (ctx.fmt.integer(s)[0], u)
                     for s, u in zip(stocks, unit_words)]
            t.add(Column("stock", ctx.header("stock"), cells))
            t.outs.append(("stock", "integer(col({stock}))"))
            for rec, s in zip(truth, stocks):
                rec["stock"] = s
        else:
            C.integer_column(ctx, t, "stock", ctx.header("stock"), stocks,
                             "stock", truth)
    if catalogue or inventory or rng.random() < 0.12:
        C.text_column(ctx, t, "unit", ctx.header("unit"),
                      [C.unit_word(ctx, r["unit"]) for r in recs], "unit",
                      truth)
    if catalogue or export or rng.random() < 0.08:
        C.text_column(ctx, t, "barcode", ctx.header("barcode"),
                      [r["barcode"] for r in recs], "barcode", truth,
                      noise=False, digits=False)
    if catalogue or export or rng.random() < 0.08:
        C.boolean_column(ctx, t, "active", ctx.header("active"),
                         [r["active"] for r in recs], "active", truth)
    # ---- trap columns: cost (T1), quantities (T3), margin, notes...
    kinds = []
    if "T1" in traps:
        kinds.append("cost")
    if "T3" in traps:
        kinds.append(rng.choice(["qty_ordered", "qty_sold"]))
    if inventory or export or rng.random() < 0.15:
        kinds += rng.sample(["margin", "supplier_ref", "internal_notes",
                             "discount"], rng.randint(1, 2))
    trap_columns(ctx, t, recs, kinds)
    if two_row:
        groups = {"product": ["sku", "name", "variant"],
                  "price": ["price_excl", "price", "cost", "margin"],
                  "stock": ["stock", "unit", "qty_ordered", "qty_sold"]}
        M.group_row(ctx, t, groups)
        if len(set(t.group_labels.values())) < 2:
            return None
    t.truth = truth
    # ---- modifiers: extra columns, title rows, totals, notes...
    text_keys = [k for k in ("name", "variant", "category") if t.has(k)]
    groups = None
    if sections:
        groups = []
        bounds = [i for i, _ in t.sections] + [len(recs)]
        for (i, title), j in zip(t.sections, bounds[1:]):
            groups.append((title, list(range(i, j))))
    M.decorate(ctx, t, plan, text_keys=text_keys,
               totals_spec={"label_key": "name", "sum_keys": ["price"],
                            "amounts_of": {"price": [
                                truth[i].get("price") for i in
                                range(len(recs))]},
                            "groups": groups})
    if category_sheet:
        t.sheet_name = cats[0]
    return t


def products_size_columns(ctx, plan, sections):
    """T8: sizes as columns - one row per product, one price per size;
    unpivot() turns it into one row per product and size. A product
    without a size leaves that cell empty (unpivot skips it)."""
    rng = ctx.rng
    cats = ctx.words.get("categories") or []
    order = dict((c, i) for i, c in enumerate(cats))
    by_name = {}
    rows, common = [], []
    if rng.random() < 0.5 or plan["n"] > 12:
        # quantities as columns ('6 pce | 12 pce | 24 pce'), one price per
        # quantity: a wholesale price list, as long as the activity has
        # items sold in that unit
        groups = {}
        for it in ctx.items("product"):
            opts = C.quantity_options(ctx, it)
            if opts:
                groups.setdefault(tuple(o[0] for o in opts), []).append(
                    (it, opts))
        if groups:
            texts, members = max(groups.items(), key=lambda kv: len(kv[1]))
            k = rng.randint(2, min(5, len(texts)))
            picked = sorted(rng.sample(range(len(texts)), k))
            members = list(members)
            rng.shuffle(members)
            if sections:
                members.sort(key=lambda m: order.get(m[0].get("category"),
                                                      99))
            members = members[:max(2, plan["n"])]
            common = [texts[j] for j in picked]
            for it, opts in members:
                base = ctx.price(it["usd"])
                by_name[it["name"]] = dict(
                    (opts[j][0], C.ctx_price_scaled(ctx, base, opts[j][2]))
                    for j in picked)
                rows.append(it)
    if len(rows) < 2:
        rows, common, by_name = [], [], {}
        items = [it for it in ctx.items("product") if it.get("variants")]
        rng.shuffle(items)
        if sections:
            items.sort(key=lambda it: order.get(it.get("category"), 99))
        for it in items:
            union = common + [v for v in it["variants"] if v not in common]
            if len(union) > 5:
                continue
            rows.append(it)
            common = union
            if len(rows) >= max(2, plan["n"] // 2):
                break
        if len(rows) < 2 or len(common) < 2:
            return None
        for it in rows:
            recs = []
            base = ctx.price(it["usd"])
            for k, v in enumerate(it["variants"]):
                recs.append((v, C.ctx_price_scaled(
                    ctx, base, [1.0, 1.35, 1.7, 2.1, 2.5][min(k, 4)])))
            by_name[it["name"]] = dict(recs)
    rows = [{"name": it["name"], "category": it.get("category")}
            for it in rows]
    t = Table("products")
    truth_rows = []
    C.text_column(ctx, t, "name", ctx.header("product_name"),
                  [r["name"] for r in rows], None, [])
    keys = []
    typed = ctx.typed
    # format_of() needs a real column letter, so an unpivoted price takes
    # its currency from the cells (text) or not at all
    show = "cell" if not typed and rng.random() < 0.6 else "none"
    for k, size in enumerate(common):
        key = "size%d" % k
        amounts = [by_name[r["name"]].get(size) for r in rows]
        C.money_column(ctx, t, key, size, amounts, None, [], show)
        keys.append(key)
    t.blocks.append(keys)
    t.unpivot = keys
    t.traps.add("T8")
    t.first_column_fixed = ["name"]
    t.outs.append(("name", "text(col({name}))"))
    t.outs.append(("variant", "text(col('name'))"))
    t.outs.append(("price", "amount(col('value'))"))
    if show == "cell":
        t.outs.append(("currency", "currency(col('value'))"))
    row_of = []
    for i, r in enumerate(rows):
        for size in common:
            if by_name[r["name"]].get(size) is None:
                continue
            # the name as the cell shows it (its digits may be
            # Arabic-Indic or full-width, section 10.5)
            rec = {"name": C.norm_text(t.col("name").cells[i]),
                   "variant": C.norm_text(size),
                   "price": float(by_name[r["name"]][size])}
            if show == "cell":
                rec["currency"] = ctx.loc["currency"]
            truth_rows.append(rec)
            row_of.append(i)
    if sections:
        cats = [r["category"] for r in rows]
        runs = sum(1 for i in range(len(rows))
                   if i == 0 or cats[i] != cats[i - 1])
        # a section needs rows under it: at most one title per two rows
        if len(set(cats)) >= 2 and runs <= len(rows) / 2:
            for i, r in enumerate(rows):
                if i == 0 or r["category"] != rows[i - 1]["category"]:
                    t.sections.append((i, r["category"]))
            t.outs.append(("category", "text(col('section'))"))
            section_at = dict(t.sections)
            current = None
            per_row = []
            for i in range(len(rows)):
                current = section_at.get(i, current)
                per_row.append(current)
            for j, rec in enumerate(truth_rows):
                rec["category"] = C.norm_text(per_row[row_of[j]])
            t.traps.add("T7")
    t.truth = truth_rows
    M.decorate(ctx, t, dict(plan, extra=min(plan.get("extra", 0), 2)),
               text_keys=["name"])
    return t
