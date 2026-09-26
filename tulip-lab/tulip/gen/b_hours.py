"""
gen/b_hours.py - the opening_hours builder: one row per day (or one
column per day, unpivoted), the day's hours in one normalized text
("09:00-12:00, 14:00-19:00") or "closed".

Every rendered day name and hours text is checked with the real helpers
(weekday, hours) before it goes into a sheet: truth first.
"""
import datetime

import helpers as H
from gen import columns as C
from gen import modifiers as M
from gen.sheetkit import Column, Table


def tm(h, m=0):
    return datetime.time(h, m)


def schedule(ctx, lunch=None):
    """-> 7 lists of (start, end) ranges, Monday first; [] = closed."""
    rng = ctx.rng
    if lunch is None:
        lunch = rng.random() < (0.6 if ctx.lang in ("fr", "it", "es")
                                else 0.15)
    start = tm(rng.choice([7, 8, 8, 9, 9, 9, 10]), rng.choice([0, 0, 0, 30]))
    end = tm(rng.choice([17, 18, 18, 19, 19, 20]), rng.choice([0, 0, 30]))
    if lunch:
        l1 = tm(rng.choice([12, 12, 13]), rng.choice([0, 0, 30]))
        l2 = tm(l1.hour + rng.choice([1, 1, 2]), rng.choice([0, 0, 30]))
        week = [(start, l1), (l2, end)]
    else:
        week = [(start, end)]
    days = [list(week) for _ in range(7)]
    r = rng.random()
    if r < 0.3:
        days[5] = []
    elif r < 0.7:
        sat_end = tm(rng.choice([12, 13, 16, 17, 18]), 0)
        days[5] = [(start, sat_end)] if sat_end > start else list(week)
    days[6] = [] if rng.random() < 0.75 else [(tm(rng.choice([9, 10])),
                                               tm(rng.choice([12, 13])))]
    if rng.random() < 0.15:
        days[0] = []
    if rng.random() < 0.15:                       # a late opening
        d = rng.randint(1, 4)
        if days[d]:
            a, b = days[d][-1]
            later = tm(min(22, b.hour + rng.choice([1, 2])), b.minute)
            days[d] = days[d][:-1] + [(a, later)]
    return days


def truth_hours(ranges):
    if not ranges:
        return "closed"
    return ", ".join("%02d:%02d-%02d:%02d" % (a.hour, a.minute, b.hour,
                                              b.minute) for a, b in ranges)


def day_order(ctx):
    rng = ctx.rng
    if ctx.lang == "ar" and rng.random() < 0.6:
        first = rng.choice([5, 6])                # Saturday or Sunday
    elif ctx.country in ("US", "CA") and rng.random() < 0.3:
        first = 6
    else:
        first = 0
    return [(first + k) % 7 for k in range(7)]


def day_names(ctx, form):
    """-> {day: text} for one form, every text read back by weekday(); or
    None when a day has no readable name in that form."""
    f, rng = ctx.fmt, ctx.rng
    wd = ctx.values.get("weekdays") or {}
    out = {}
    for d in range(7):
        if form == "other":
            options = list((wd.get("other") or [[]] * 7)[d] or [])
        else:
            options = [f.weekday_text(d, form)]
        options = [o for o in options
                   if H.weekday(o, ctx.code) == (True, d)]
        if not options:
            return None
        out[d] = rng.choice(options)
    return out


def pick_day_names(ctx, short=False):
    rng = ctx.rng
    forms = ["short"] if short else \
        ["full", "full", "full", "short", "short", "other"]
    rng.shuffle(forms)
    for form in forms + ["full"]:
        names = day_names(ctx, form)
        if names:
            return names, form
    return None, None


def hours_cell(ctx, ranges):
    """-> text, or None when the helper would not read it back."""
    text = ctx.fmt.hours_text(ranges)
    if H.hours(text, ctx.code) != (True, truth_hours(ranges)):
        return None
    return text


def opening_hours(ctx, plan, *, columns=None, morning_afternoon=False,
                  opens_closes=False, notes=False, short=False,
                  many_closed=False, title=False):
    """columns: days as columns (unpivot, trap T8); None = decided by the
    drawn traps."""
    rng = ctx.rng
    traps = set(plan["traps"])
    if title:
        traps.add("T5")
    plan = dict(plan, traps=traps)
    row_layouts = morning_afternoon or opens_closes or notes
    if columns is None:
        columns = "T8" in traps and not row_layouts
    days = schedule(ctx, lunch=True if morning_afternoon else
                    False if opens_closes else None)
    if many_closed:
        for d in rng.sample(range(7), rng.randint(2, 3)):
            days[d] = []
    order = day_order(ctx)
    if rng.random() < 0.15 and not columns:
        order = [d for d in order if d != 6 or days[6]]   # Sunday left out
    names, _ = pick_day_names(ctx, short)
    if names is None:
        return None
    t = Table("opening_hours")
    if columns:
        return hours_as_columns(ctx, plan, t, days, order, names)
    truth = [{} for _ in order]
    C.text_column(ctx, t, "day", ctx.header("day"),
                  [names[d] for d in order], None, None, noise=True,
                  digits=False)
    t.outs.append(("day", "weekday(col({day}))"))
    for rec, d in zip(truth, order):
        rec["day"] = d
    t.first_column_fixed = ["day"]
    if morning_afternoon:
        closed = ctx.fmt.closed_word()
        m_cells, a_cells = [], []
        for d in order:
            r = days[d]
            if not r:
                m_cells.append(closed)
                a_cells.append(closed if rng.random() < 0.6 else None)
            elif len(r) == 2:
                m_cells.append(hours_cell(ctx, [r[0]]))
                a_cells.append(hours_cell(ctx, [r[1]]))
            elif r[0][1] <= tm(14):
                m_cells.append(hours_cell(ctx, r))
                a_cells.append(closed if rng.random() < 0.5 else None)
            else:
                m_cells.append(closed if rng.random() < 0.5 else None)
                a_cells.append(hours_cell(ctx, r))
        if any(c is None and days[d] and len(days[d]) == 2
               for c, d in zip(m_cells + a_cells, order + order)):
            return None
        t.add(Column("morning", ctx.header("morning"), m_cells))
        t.add(Column("afternoon", ctx.header("afternoon"), a_cells))
        t.blocks.append(["morning", "afternoon"])
        t.outs.append(("hours", "hours(join(', ', col({morning}), "
                                "col({afternoon})))"))
        for rec, m, a, d in zip(truth, m_cells, a_cells, order):
            joined = ", ".join(x.strip() for x in (m, a) if x and x.strip())
            if H.hours(joined, ctx.code) != (True, truth_hours(days[d])):
                return None
            rec["hours"] = truth_hours(days[d])
    elif opens_closes:
        o_cells, c_cells, fmts_o, fmts_c = [], [], [], []
        for d in order:
            r = days[d]
            if not r:
                o_cells.append(ctx.fmt.closed_word())
                c_cells.append(None)
                fmts_o.append(None)
                fmts_c.append(None)
                continue
            if len(r) != 1:
                return None
            (a, b), = r
            va, fa = ctx.fmt.time(a)
            vb, fb = ctx.fmt.time(b)
            o_cells.append(va)
            c_cells.append(vb)
            fmts_o.append(fa)
            fmts_c.append(fb)
        t.add(Column("opens", ctx.header("opens"), o_cells, fmts_o))
        t.add(Column("closes", ctx.header("closes"), c_cells, fmts_c))
        t.blocks.append(["opens", "closes"])
        t.outs.append(("hours", "hours(join('-', col({opens}), "
                                "col({closes})))"))
        import tulipscript as ts
        for rec, o, c, d in zip(truth, o_cells, c_cells, order):
            parts = [ts._as_text(x).strip() for x in (o, c)
                     if x is not None and ts._as_text(x).strip()]
            if H.hours("-".join(parts), ctx.code) != \
                    (True, truth_hours(days[d])):
                return None
            rec["hours"] = truth_hours(days[d])
    else:
        cells = []
        for d in order:
            cell = hours_cell(ctx, days[d])
            if cell is None:
                return None
            cells.append(cell)
        t.add(Column("hours", ctx.header("hours"), cells))
        t.outs.append(("hours", "hours(col({hours}))"))
        for rec, d in zip(truth, order):
            rec["hours"] = truth_hours(days[d])
    if notes:
        pool = [w for w in ctx.values.get("hours_notes") or []]
        if not pool:
            return None
        cells = [None] * len(order)
        for k in rng.sample(range(len(order)), rng.randint(1, 3)):
            cells[k] = rng.choice(pool)
        C.text_column(ctx, t, "note", ctx.header("hours_note"), cells,
                      "note", truth, digits=False)
    t.truth = truth
    M.decorate(ctx, t, dict(plan, extra=min(plan.get("extra", 0), 2)),
               text_keys=["note"] if notes else [], totals_spec=None)
    return t


def hours_as_columns(ctx, plan, t, days, order, names):
    """T8: a header row of day names and one row of hours;
    unpivot(...) gives one row per day."""
    rng = ctx.rng
    closed = ctx.fmt.closed_word()
    truth = []
    keys = []
    label = rng.random() < 0.5
    if label:
        text = ctx.title("opening_hours") or ctx.business_name()
        t.add(Column("label", ctx.header_plain("hours") if rng.random() <
                     0.5 else None, [text]))
        t.first_column_fixed = ["label"]
    for d in order:
        r = days[d]
        if r:
            cell = hours_cell(ctx, r)
            if cell is None:
                return None
        else:
            cell = closed if rng.random() < 0.8 else None
        key = "d%d" % d
        t.add(Column(key, names[d], [cell]))
        keys.append(key)
        if cell is not None:
            truth.append({"day": d, "hours": truth_hours(r)})
    t.blocks.append(keys)
    t.unpivot = keys
    t.outs.append(("day", "weekday(col('name'))"))
    t.outs.append(("hours", "hours(col('value'))"))
    t.traps.add("T8")
    t.shuffle = False
    t.truth = truth
    if "T5" in plan["traps"]:
        M.title_rows(ctx, t)
    return t


# =====================================================================
#  several days in one cell (Tulip 1.1, item G): "Lun–Ven | 9h–18h"
# =====================================================================
# how a range of days is written, per language; {a} and {b} are day
# names in the sheet's form. Every text is read back by weekdays()
# before it goes into a sheet (truth first).
RANGE_FORMS = {
    "fr": ["{a}–{b}", "{a}-{b}", "{a} - {b}", "{a} au {b}", "du {a} au {b}",
           "{a} à {b}"],
    "en": ["{a}–{b}", "{a}-{b}", "{a} - {b}", "{a} to {b}",
           "{a} through {b}"],
    "es": ["{a}–{b}", "{a}-{b}", "{a} a {b}", "de {a} a {b}"],
    "it": ["{a}–{b}", "{a}-{b}", "{a} - {b}", "da {a} a {b}"],
    "ru": ["{a}–{b}", "{a}-{b}", "{a} - {b}"],
    "ar": ["{a} - {b}", "{a}-{b}", "من {a} إلى {b}", "{a} إلى {b}"],
    "zh": ["{a}至{b}", "{a}到{b}", "{a}-{b}", "{a}～{b}"],
    "ja": ["{a}～{b}", "{a}〜{b}", "{a}-{b}", "{a}から{b}"],
    "ko": ["{a}~{b}", "{a}-{b}", "{a} ~ {b}"],
    "hi": ["{a} से {b}", "{a}-{b}", "{a} - {b}"],
}
LIST_FORMS = {
    "fr": ["{a} et {b}", "{a}, {b}", "{a} & {b}"],
    "en": ["{a} & {b}", "{a} and {b}", "{a}, {b}", "{a}/{b}"],
    "es": ["{a} y {b}", "{a}, {b}"], "it": ["{a} e {b}", "{a}, {b}"],
    "ru": ["{a} и {b}", "{a}, {b}"], "ar": ["{a} و {b}", "{a}، {b}"],
    "zh": ["{a}、{b}", "{a}和{b}"], "ja": ["{a}・{b}", "{a}、{b}"],
    "ko": ["{a}, {b}", "{a}·{b}"], "hi": ["{a} और {b}", "{a}, {b}"],
}


def day_runs(order, days):
    """Consecutive days (in the sheet's order) with the same hours ->
    [[day, ...], ...]."""
    runs = []
    for d in order:
        if runs and days[runs[-1][-1]] == days[d]:
            runs[-1].append(d)
        else:
            runs.append([d])
    return runs


def run_text(ctx, run, names):
    """The text of a run of days - "Lun–Ven", "Sam & Dim", or one day -
    or None when no form of it is read back as exactly these days."""
    import helpers as H2
    rng = ctx.rng
    if len(run) == 1:
        return names[run[0]]
    forms = list(RANGE_FORMS.get(ctx.lang, ["{a}-{b}"]))
    if len(run) == 2:
        forms += LIST_FORMS.get(ctx.lang, [])
    rng.shuffle(forms)
    for form in forms:
        text = form.format(a=names[run[0]], b=names[run[-1]])
        if H2.weekdays(text, ctx.code) == (True, tuple(run)):
            return text
    return None


def opening_hours_ranges(ctx, plan):
    """One row per run of days with the same hours: "Lun–Ven | 9h–18h",
    "Sam | 9h–12h", "Dim | Fermé"; out.day = weekdays(col(...)) gives
    one row per day."""
    rng = ctx.rng
    days = schedule(ctx)
    order = [0, 1, 2, 3, 4, 5, 6] if ctx.lang != "ar" or \
        rng.random() < 0.5 else [5, 6, 0, 1, 2, 3, 4]
    runs = day_runs(order, days)
    if all(len(r) == 1 for r in runs):
        return None                       # nothing to put in one cell
    names, _ = pick_day_names(ctx, short=rng.random() < 0.6)
    if names is None:
        return None
    t = Table("opening_hours")
    texts, cells, truth = [], [], []
    for run in runs:
        text = run_text(ctx, run, names)
        cell = hours_cell(ctx, days[run[0]])
        if text is None or cell is None:
            return None
        texts.append(text)
        cells.append(cell)
    C.text_column(ctx, t, "day", ctx.header("day"), texts, None, None,
                  noise=False, digits=False)
    t.outs.append(("day", "weekdays(col({day}))"))
    t.first_column_fixed = ["day"]
    t.add(Column("hours", ctx.header("hours"), cells))
    t.outs.append(("hours", "hours(col({hours}))"))
    # the truth, one record per sheet row: the days of the row as a
    # tuple, which sheetkit.clean_rows() makes one row per day - as the
    # runtime does with weekdays()
    for run in runs:
        truth.append({"day": tuple(run), "hours": truth_hours(days[run[0]])})
    t.truth = truth
    t.shuffle = False
    M.decorate(ctx, t, dict(plan, extra=min(plan.get("extra", 0), 2)),
               text_keys=[], totals_spec=None)
    return t
