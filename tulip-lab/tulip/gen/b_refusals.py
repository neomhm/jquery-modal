"""
gen/b_refusals.py - sheets the model must refuse (section 10.3):

  not_a_table        pivot / summary tables, matrices, chart data, budget
                     sheets, notes pages, agenda week grids
  no_matching_target a real table for a target that was not offered
  missing_required   a matching table without a required field (T15)
  too_wide           more than 26 columns

Each builder returns {sheet, program, targets, traps, answer} (the task
maker adds the preview), or None to draw again.
"""
import datetime
import math

import config
import helpers as H
import sheets
from gen import sheetkit as K

REF = datetime.date(2026, 6, 30)


def offer(rng, answer=None, exclude=()):
    """1-4 offered targets; with `answer`, it is always among them."""
    others = [t for t in config.TARGETS if t != answer and t not in exclude]
    k = rng.choice([1, 1, 2, 2, 3, 4]) - (1 if answer else 0)
    chosen = rng.sample(others, max(0, min(k, len(others))))
    if answer:
        chosen.append(answer)
    if not chosen:
        chosen = rng.sample(others, 1)
    rng.shuffle(chosen)
    return chosen


def result(ctx, rows, program, targets, answer, name=None, formats=None,
           traps=()):
    from gen.tasks import sheet_name_ok
    sheet = sheets.Sheet(sheet_name_ok(name or ctx.sheet_name("other")),
                         [[K.to_grid_cell(v) for v in r] for r in rows],
                         formats if ctx.typed else None)
    return {"sheet": sheet, "program": program, "targets": targets,
            "traps": list(traps), "answer": answer}


def money(ctx, x):
    v, _ = ctx.fmt.money(x, symbol=not ctx.typed and ctx.rng.random() < 0.5)
    return v


def amount_usd(ctx, lo, hi):
    x = math.exp(ctx.rng.uniform(math.log(lo), math.log(hi)))
    return round(x * ctx.loc["usd_rate"] * ctx.loc["price_level"],
                 2 if ctx.loc["cents"] else 0)


def month_labels(ctx, k):
    start = ctx.rng.randint(1, 12 - k + 1) if k <= 12 else 1
    short = ctx.rng.random() < 0.5
    return [ctx.fmt.month_name(m, short=short) for m in range(start,
                                                                start + k)]


# ---------------------------------------------------------------------
#  not_a_table
# ---------------------------------------------------------------------
def pivot(ctx, plan):
    """Sums per category and month, with a total row and column."""
    rng = ctx.rng
    cats = list(ctx.words.get("categories") or [])
    if len(cats) < 2:
        return None
    cats = rng.sample(cats, min(len(cats), rng.randint(2, 6)))
    months = month_labels(ctx, rng.randint(3, 12))
    total_word = rng.choice(ctx.values.get("totals") or ["Total"])
    rows = []
    title = ctx.title("products") if rng.random() < 0.5 else None
    if title:
        rows.append([title])
        rows.append([])
    rows.append([ctx.word("summary_label") or ""] + months + [total_word])
    col_sums = [0.0] * len(months)
    for c in cats:
        vals = [amount_usd(ctx, 50, 5000) for _ in months]
        col_sums = [a + b for a, b in zip(col_sums, vals)]
        rows.append([c] + [money(ctx, v) for v in vals] +
                    [money(ctx, round(sum(vals), 2))])
    rows.append([total_word] + [money(ctx, round(v, 2)) for v in col_sums] +
                [money(ctx, round(sum(col_sums), 2))])
    return result(ctx, rows, "refuse('not_a_table')", offer(rng),
                  "not_a_table")


def matrix(ctx, plan):
    """Staff x weekdays: shift codes in the cells."""
    rng = ctx.rng
    people = [ctx.person()["full"] for _ in range(rng.randint(3, 10))]
    wd = ctx.values.get("weekdays") or {}
    days = (wd.get("short") or wd.get("full") or [])[:7]
    if len(days) < 5:
        return None
    days = days[:rng.choice([5, 6, 7])]
    codes = rng.choice([["M", "A", "N", "-"], ["8-16", "12-20", "OFF"],
                        ["X", "", "X"], ["1", "2", "R"]])
    rows = []
    if rng.random() < 0.6:
        rows.append([ctx.title("staff") or ctx.business_name()])
    rows.append([""] + days)
    for p in people:
        rows.append([p] + [rng.choice(codes) for _ in days])
    return result(ctx, rows, "refuse('not_a_table')",
                  offer(rng), "not_a_table")


def chart_data(ctx, plan):
    """Two or three short series by month, the source of a chart."""
    rng = ctx.rng
    series = list((ctx.values.get("not_a_table") or {}).get("chart") or [])
    if not series:
        return None
    series = rng.sample(series, min(len(series), rng.randint(1, 3)))
    months = month_labels(ctx, rng.randint(4, 12))
    rows = [[""] + series]
    for m in months:
        rows.append([m] + [rng.randint(5, 900) if ctx.typed else
                           str(rng.randint(5, 900)) for _ in series])
    if rng.random() < 0.5:
        rows = [[s] + [r[i + 1] for r in rows[1:]]
                for i, s in enumerate(series)]
        rows.insert(0, [""] + months)
    return result(ctx, rows, "refuse('not_a_table')", offer(rng),
                  "not_a_table")


def budget(ctx, plan):
    rng = ctx.rng
    b = ctx.values.get("budget") or {}
    heads, lines = b.get("headers") or [], b.get("lines") or []
    if len(heads) < 3 or len(lines) < 4:
        return None
    lines = rng.sample(lines, min(len(lines), rng.randint(4, 12)))
    cols = rng.sample(heads, min(len(heads), rng.randint(3, 5)))
    rows = []
    if rng.random() < 0.7:
        rows.append([rng.choice(heads) + " %d" % REF.year])
        rows.append([])
    rows.append(cols)
    total_word = rng.choice(ctx.values.get("totals") or ["Total"])
    sums = [0.0] * (len(cols) - 1)
    for line in lines:
        vals = [amount_usd(ctx, 100, 20000) for _ in cols[1:]]
        sums = [a + v for a, v in zip(sums, vals)]
        rows.append([line] + [money(ctx, v) for v in vals])
    rows.append([total_word] + [money(ctx, round(v, 2)) for v in sums])
    return result(ctx, rows, "refuse('not_a_table')", offer(rng),
                  "not_a_table")


def notes_page(ctx, plan):
    rng = ctx.rng
    notes = list((ctx.values.get("not_a_table") or {}).get("notes_page")
                 or [])
    if len(notes) < 3:
        return None
    rows = []
    if rng.random() < 0.6:
        rows.append([ctx.business_name()])
    if rng.random() < 0.5:
        rows.append([ctx.fmt.date_text(REF - datetime.timedelta(
            days=rng.randint(0, 30)))])
    rows.append([])
    for line in rng.sample(notes, min(len(notes), rng.randint(3, 8))):
        rows.append([("- " if rng.random() < 0.3 else "") + line])
        if rng.random() < 0.3:
            rows.append([])
    return result(ctx, rows, "refuse('not_a_table')", offer(rng),
                  "not_a_table")


def summary(ctx, plan):
    """Label / value pairs (a dashboard), not a list of records."""
    rng = ctx.rng
    labels = list((ctx.values.get("not_a_table") or {}).get("summary")
                  or [])
    if len(labels) < 3:
        return None
    rows = []
    if rng.random() < 0.7:
        rows.append([ctx.title("invoice_ledger") or ctx.business_name()])
        rows.append([])
    for lab in rng.sample(labels, min(len(labels), rng.randint(3, 8))):
        rows.append([lab, money(ctx, amount_usd(ctx, 100, 90000))])
    return result(ctx, rows, "refuse('not_a_table')", offer(rng),
                  "not_a_table")


def agenda_grid(ctx, plan):
    """A week agenda: time slots down, days across, clients in cells."""
    rng = ctx.rng
    wd = ctx.values.get("weekdays") or {}
    days = (wd.get("full") or [])[:rng.choice([5, 6])]
    if len(days) < 5:
        return None
    slots = []
    h = rng.choice([8, 9])
    for _ in range(rng.randint(6, 12)):
        slots.append("%02d:%02d" % (h, 0))
        h += 1
    rows = [[""] + days]
    names = [ctx.person()["full"] for _ in range(8)]
    for s in slots:
        rows.append([s] + [rng.choice(names) if rng.random() < 0.4 else None
                           for _ in days])
    if all(v is None for r in rows[1:] for v in r[1:]):
        rows[1][1] = names[0]
    return result(ctx, rows, "refuse('not_a_table')",
                  offer(rng, exclude=()), "not_a_table")


# ---------------------------------------------------------------------
#  a real table: not offered, missing a required field, too wide
# ---------------------------------------------------------------------
def build_table(ctx, plan, target):
    from gen import b_bookings, b_hours, b_ledger, b_people, b_services
    from gen import builders as B
    make = {"products": B.products, "services": b_services.services,
            "opening_hours": b_hours.opening_hours,
            "staff": b_people.staff, "clients": b_people.clients,
            "bookings": b_bookings.bookings,
            "invoice_ledger": b_ledger.invoice_ledger}[target]
    return make(ctx, dict(plan, target=target))


def checked(ctx, table, rng):
    """Assemble and self-check a real table (it must be importable as its
    own target). -> small sheet or None."""
    done, why = K.finish(table, ctx.fmt, rng, table.sheet_name or
                         ctx.sheet_name(table.target), ctx.code,
                         [table.target])
    return done["sheet"] if done else None


def not_offered(ctx, plan):
    rng = ctx.rng
    target = plan["target"]
    table = build_table(ctx, plan, target)
    if table is None:
        return None
    sheet = checked(ctx, table, rng)
    if sheet is None:
        return None
    # judge by what the rows are: never offer the true target (nor, for a
    # list of people, the other list of people it could pass for)
    close = {"staff": ("clients",), "clients": ("staff",)}.get(target, ())
    targets = offer(rng, exclude=(target,) + close)
    return {"sheet": sheet, "program": "refuse('no_matching_target')",
            "targets": targets, "traps": sorted(table.traps),
            "answer": "no_matching_target", "digits": True}


# the required field a real sheet can lack, and the columns that show it
MISSING = {"products": ("price", ("price", "price_excl")),
           "bookings": ("start_time", ("start", "end", "range", "dur")),
           "invoice_ledger": ("number", ("number",))}


def missing_required(ctx, plan):
    rng = ctx.rng
    target = plan["target"]
    if target not in MISSING:
        return None
    field, keys = MISSING[target]
    extra = {}
    if target == "bookings":
        extra = {"datetime_cell": False, "day_sections": False}
    from gen import b_bookings, b_ledger
    from gen import builders as B
    if target == "products":
        table = B.products(ctx, dict(plan, target=target))
    elif target == "bookings":
        table = b_bookings.bookings(ctx, dict(plan, target=target), **extra)
    else:
        table = b_ledger.invoice_ledger(ctx, dict(plan, target=target))
    if table is None:
        return None
    if table.unpivot or table.sections:
        return None
    sheet = checked(ctx, table, rng)          # it was a valid table...
    if sheet is None:
        return None
    for k in keys:                            # ...until the field went
        if table.has(k):
            table.columns = [c for c in table.columns if c.key != k]
    table.blocks = [[k for k in b if table.has(k)] for b in table.blocks]
    table.blocks = [b for b in table.blocks if b]
    if table.total_label_key and not table.has(table.total_label_key):
        table.totals, table.subtotals = None, []
    if not table.columns:
        return None
    rows, fmts, _, letters = K.assemble(table, ctx.fmt, rng)
    if not letters:
        return None
    small, _ = sheets.compact(sheets.Sheet(
        table.sheet_name or ctx.sheet_name(target),
        [[K.to_grid_cell(v) for v in r] for r in rows],
        fmts if ctx.typed else None))
    return {"sheet": small,
            "program": "refuse('missing_required:%s')" % field,
            "targets": offer(rng, answer=target),
            "traps": sorted(table.traps | {"T15"}),
            "answer": "missing_required:%s" % field, "digits": True}


def too_wide(ctx, plan):
    """A table with 27-40 columns: a CRM or ERP export."""
    rng = ctx.rng
    target = plan["target"]
    table = build_table(ctx, dict(plan, extra=0), target)
    if table is None:
        return None
    from gen import modifiers as M
    want = rng.randint(27, 40) - len(table.columns)
    k = 0
    while want > 0 and k < 80:
        k += 1
        before = len(table.columns)
        M.extra_columns(ctx, table, 1)
        if len(table.columns) > before:
            table.columns[-1].key = "wide%d" % k
            want -= 1
    if len(table.columns) <= 26:
        return None
    K.digit_pass(table, ctx.fmt, rng)          # section 10.5
    rows, fmts, _, letters = K.assemble(table, ctx.fmt, rng)
    small, _ = sheets.compact(sheets.Sheet(
        ctx.sheet_name(target), [[K.to_grid_cell(v) for v in r]
                                 for r in rows],
        fmts if ctx.typed else None))
    if max(len(r) for r in small.rows) <= 26:
        return None
    return {"sheet": small, "program": "refuse('too_wide')",
            "targets": offer(rng, answer=target), "traps": [],
            "answer": "too_wide", "digits": True}
