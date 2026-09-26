"""
gen/b_services.py - the services builder: work or time sold (a haircut,
a lesson, a repair), with prices, durations and the person doing it.

A layout family (gen/layouts/services__*.py) calls services() with the
features that make it what it is; the task's traps are added on top.
"""
import helpers as H
from gen import builders as B
from gen import columns as C
from gen import modifiers as M
from gen.sheetkit import Column, Table


def duration_column(ctx, table, key, header, minutes, field, truth):
    """A duration column: '45 min', '1h30', '1:30', typed minutes or
    [h]:mm. Every cell is checked with the real helper. -> False when a
    cell cannot be written in a readable way."""
    f, rng = ctx.fmt, ctx.rng
    words = [w for w in ctx.values.get("minute_words") or [] if w]
    plain = any(w.casefold() in header.casefold() for w in words) and \
        rng.random() < 0.6
    cells, fmts = [], []
    for m in minutes:
        if m is None:
            cells.append(None)
            fmts.append(None)
            continue
        v, fm = f.duration(m, plain=plain)
        if H.duration(v, ctx.code) != (True, m):
            return False
        cells.append(v)
        fmts.append(fm)
    if all(c is None for c in cells):
        return False
    table.add(Column(key, header, cells, fmts))
    table.outs.append((field, "duration(col({%s}))" % key))
    for rec, m in zip(truth, minutes):
        if m is not None:
            rec[field] = int(m)
    return True


def name_duration(ctx, minutes):
    """A duration written inside a service's name: the sheet's duration
    style, but never a bare number."""
    style = ctx.fmt.duration_style
    return ctx.fmt.duration_text(minutes, "MIN" if style == "PLAIN"
                                 else style)


def services(ctx, plan, *, duration="maybe", from_prices=False,
             sections=False, staff=False, force_two_prices=False,
             title=False, category_column=False, export=False):
    """duration: 'column', 'name' (inside the name, split with part),
    'none' or 'maybe'."""
    rng = ctx.rng
    traps = set(plan["traps"])
    if force_two_prices:
        traps.add("T2")
    if title:
        traps.add("T5")
    plan = dict(plan, traps=traps)
    drawn_sections = False
    if not sections and "T7" in traps:
        sections, drawn_sections = True, True
    if duration == "maybe" and "T9" in traps:
        duration = "name"
    recs = C.service_records(ctx, plan["n"], packages=duration != "name")
    if len(recs) < 3:
        return None
    t = Table("services")
    truth = [{} for _ in recs]
    minutes = [r["duration_min"] for r in recs]
    if duration == "maybe":
        duration = rng.choice(["column", "column", "column", "none"])
    if duration == "name" and any(m is None for m in minutes):
        duration = "column"
    if duration == "none" and any(r["timed"] for r in recs):
        # the same service at several lengths and no duration column:
        # the length is part of the name ('Massage 60 min')
        count = {}
        for r in recs:
            count[r["name"]] = count.get(r["name"], 0) + 1
        for r in recs:
            if r["duration_min"] is not None and count[r["name"]] > 1:
                r["name"] = "%s %s" % (r["name"], name_duration(ctx, r[
                    "duration_min"]))
    # ---- the name, with the duration inside it or not
    names = [r["name"] for r in recs]
    if duration == "name":
        texts = [ctx.fmt.duration_text(m) for m in minutes]
        sep = B.part_separator(ctx, names + texts)
        if sep is None or any(H.duration(x, ctx.code) != (True, m)
                              for x, m in zip(texts, minutes)):
            duration = "column"
        else:
            cells = ["%s%s%s" % (n, sep, d) for n, d in zip(names, texts)]
            t.add(Column("name", ctx.header("service_name"),
                         [C.noisy_text(ctx, c) for c in cells]))
            t.outs.append(("name", "text(part(col({name}), %r, 0))" % sep))
            t.outs.append(("duration_min",
                           "duration(part(col({name}), %r, 1))" % sep))
            for rec, n, m in zip(truth, names, minutes):
                rec["name"] = C.norm_text(n)
                rec["duration_min"] = m
            t.traps.add("T9")
    if duration != "name":
        C.text_column(ctx, t, "name", ctx.header("service_name"), names,
                      "name", truth)
    # ---- category: section rows or a column
    cats = [r["category"] for r in recs]
    groups = None
    if sections:
        groups = B.add_sections(ctx, t, cats, truth, "category")
        if groups is None and not drawn_sections:
            return None
        sections = groups is not None
        if sections:
            t.first_column_fixed = ["name"]
    if not sections and (category_column or export or rng.random() < 0.3):
        C.text_column(ctx, t, "category", ctx.header("category"), cats,
                      "category", truth)
    # ---- duration in its own column
    if duration == "column":
        if not duration_column(ctx, t, "duration", ctx.header("duration"),
                               minutes, "duration_min", truth):
            return None
    # ---- price(s), currency, tax_included (a few lists have no price)
    if "T2" in traps or from_prices or rng.random() < 0.94:
        C.price_block(ctx, t, recs, truth, plan, allow_from=from_prices)
    # ---- who does it
    if staff or rng.random() < 0.15:
        C.text_column(ctx, t, "staff", ctx.header("performer"),
                      [r["staff"] for r in recs], "staff", truth)
    # a section row is a row with ONE filled cell: every data row needs 2
    if sections and (len(t.columns) < 2 or any(
            sum(1 for c in t.columns if c.cells[i] not in (None, ""))
            < 2 for i in range(len(recs)))):
        return None
    t.truth = truth
    text_keys = [k for k in ("name", "category", "staff") if t.has(k)]
    M.decorate(ctx, t, plan, text_keys=text_keys, totals_spec=None)
    return t
