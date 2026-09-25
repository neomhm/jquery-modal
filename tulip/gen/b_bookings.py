"""
gen/b_bookings.py - the bookings builder: appointments with a date, a
start time and optionally an end time or a duration, the client, the
service, the person doing it, a status word and a price.

The date and time can sit in one cell (trap T11): the program then reads
the same column twice, with date(...) and time(...).
"""
import datetime

import helpers as H
from gen import b_services as S
from gen import builders as B
from gen import columns as C
from gen import modifiers as M
from gen.b_people import date_column
from gen.sheetkit import Column, Table

REF = datetime.date(2026, 6, 30)
STATUSES = ("confirmed", "pending", "completed", "cancelled", "no_show")


def booking_records(ctx, n):
    """Appointments in agenda order (by date, then time)."""
    rng = ctx.rng
    items = [it for it in ctx.items("service")
             if (it.get("minutes") or [30, 60])[0] < 480]
    if len(items) < 2:
        return []
    items = rng.sample(items, min(len(items), rng.randint(3, 8)))
    staff = [ctx.person() for _ in range(rng.randint(1, 4))]
    clients = [ctx.person()["full"] for _ in range(max(3, n // 2))]
    open_h = rng.choice([8, 9, 9, 10])
    close_h = rng.choice([17, 18, 19, 20])
    grid = rng.choice([15, 30, 30, 60])
    day = REF - datetime.timedelta(days=rng.randint(0, 45))
    out = []
    while len(out) < n:
        if day.weekday() == 6 and rng.random() < 0.8:
            day += datetime.timedelta(days=1)
            continue
        minute = open_h * 60
        for _ in range(rng.randint(1, 8)):
            if len(out) >= n:
                break
            it = rng.choice(items)
            lo, hi = it.get("minutes") or [30, 60]
            lo = min(lo, 240)
            hi = max(lo, min(hi, 240))
            dur = max(grid, int(round(rng.randint(lo, hi) /
                                      float(grid))) * grid)
            minute += rng.choice([0, 0, grid, 2 * grid])
            if minute + dur > close_h * 60:
                break
            start = datetime.time(minute // 60, minute % 60)
            end_m = minute + dur
            end = datetime.time(end_m // 60, end_m % 60)
            past = day < REF
            if past:
                status = rng.choices(["completed", "no_show", "cancelled",
                                      "confirmed"], [75, 8, 12, 5])[0]
            else:
                status = rng.choices(["confirmed", "pending", "cancelled"],
                                     [70, 20, 10])[0]
            who = rng.choice(staff)
            out.append({"date": day, "start": start, "end": end,
                        "minutes": dur, "client": rng.choice(clients),
                        "service": it["name"], "staff": who["full"],
                        "status": status, "price": ctx.price(it["usd"]),
                        "price_excl": None})
            minute = end_m
        day += datetime.timedelta(days=rng.choice([1, 1, 1, 2]))
    return out


def status_words(ctx, key, statuses, allow_other=True):
    """One word per status value (the same word every time: VALUES shows
    each once) and maybe a word with no enum equivalent. -> ({status:
    word}, other word or None) or None."""
    rng = ctx.rng
    table = ctx.values.get(key) or {}
    chosen = {}
    used = set()
    for s in sorted(set(statuses)):
        words = [w for w in table.get(s) or []
                 if len(w) <= 19 and w.casefold() not in used]
        if not words:
            return None
        w = rng.choice(words)
        chosen[s] = w
        used.add(w.casefold())
    other = None
    if allow_other and rng.random() < 0.12:
        words = [w for w in table.get("other") or []
                 if len(w) <= 19 and w.casefold() not in used]
        other = rng.choice(words) if words else None
    return chosen, other


def status_column(ctx, t, key, header, statuses, field, truth, values_key):
    """T12: a status column mapped with lookup(). When a word with no
    enum value covers more than 2% of rows, the field is left out."""
    rng = ctx.rng
    got = status_words(ctx, values_key, statuses)
    if got is None:
        return False
    words, other = got
    cells = [words[s] for s in statuses]
    n_other = 0
    if other:
        k = max(1, int(round(len(cells) * rng.uniform(0.05, 0.2))))
        for i in rng.sample(range(len(cells)), min(k, len(cells) - 1)):
            cells[i] = other
        n_other = sum(1 for c in cells if c == other)
    distinct = list(dict.fromkeys(cells))
    # VALUES shows the words only if some repeat and there are at most 12
    # different texts (the header counts too)
    if len(distinct) + 1 > 12 or len(distinct) >= len(cells):
        return False
    t.add(Column(key, header, cells))
    t.traps.add("T12")
    if other and n_other > 0.02 * len(cells):
        return True                    # status left out (section 6)
    pairs = ", ".join("%r: %r" % (w, next(s for s, x in words.items()
                                          if x == w))
                      for w in distinct)
    t.outs.append((field, "lookup(col({%s}), {%s})" % (key, pairs)))
    for rec, s, c in zip(truth, statuses, cells):
        if c != other:
            rec[field] = s
    return True


def time_column(ctx, t, key, header, times, field, truth):
    cells, fmts = [], []
    for x in times:
        v, fm = ctx.fmt.time(x)
        if H.time(v, ctx.code) != (True, "%02d:%02d" % (x.hour, x.minute)):
            return False
        cells.append(v)
        fmts.append(fm)
    t.add(Column(key, header, cells, fmts))
    t.outs.append((field, "time(col({%s}))" % key))
    for rec, x in zip(truth, times):
        rec[field] = "%02d:%02d" % (x.hour, x.minute)
    return True


def hm(x):
    return "%02d:%02d" % (x.hour, x.minute)


def bookings(ctx, plan, *, datetime_cell=None, end="maybe", status=None,
             staff_price=False, day_sections=False, title=False):
    """end: 'column' (end time), 'range' ('09:00-10:00' in one cell),
    'duration', 'none' or 'maybe'."""
    rng = ctx.rng
    traps = set(plan["traps"])
    if title:
        traps.add("T5")
    plan = dict(plan, traps=traps)
    recs = booking_records(ctx, plan["n"])
    if len(recs) < 3:
        return None
    t = Table("bookings")
    truth = [{} for _ in recs]
    if datetime_cell is None:
        datetime_cell = "T11" in traps and not day_sections
    if end == "maybe":
        end = "range" if "T9" in traps and not datetime_cell and \
            not day_sections else rng.choice(["column", "none", "none",
                                              "duration"])
    if datetime_cell and end == "range":
        end = "column"
    # ---- date and start time
    if day_sections:
        titles = []
        for r in recs:
            v = ctx.fmt.date_text(r["date"])
            if H.date(v, ctx.code) != (True, r["date"].isoformat()):
                return None
            titles.append(v)
        groups = []
        for i, title_text in enumerate(titles):
            if i == 0 or title_text != titles[i - 1]:
                groups.append((title_text, [i]))
            else:
                groups[-1][1].append(i)
        if len(groups) < 2:
            return None
        for title_text, idx in groups:
            t.sections.append((idx[0], title_text))
        t.outs.append(("date", "date(col('section'))"))
        for rec, r in zip(truth, recs):
            rec["date"] = r["date"].isoformat()
    elif datetime_cell:
        cells, fmts = [], []
        for r in recs:
            v, fm = ctx.fmt.datetime_cell(r["date"], r["start"])
            if H.date(v, ctx.code) != (True, r["date"].isoformat()) or \
                    H.time(v, ctx.code) != (True, hm(r["start"])):
                return None
            cells.append(v)
            fmts.append(fm)
        t.add(Column("when", ctx.header("booking_datetime"), cells, fmts))
        t.outs.append(("date", "date(col({when}))"))
        t.outs.append(("start_time", "time(col({when}))"))
        for rec, r in zip(truth, recs):
            rec["date"] = r["date"].isoformat()
            rec["start_time"] = hm(r["start"])
        t.traps.add("T11")
    if not day_sections and not datetime_cell:
        if not date_column(ctx, t, "date", ctx.header("booking_date"),
                           [r["date"] for r in recs], "date", truth):
            return None
        if any("date" not in rec for rec in truth):
            return None
    if not datetime_cell:
        if end == "range":
            texts = []
            sep = rng.choice(["-", " - ", "–", " – "])
            for r in recs:
                a = ctx.fmt.time_text(r["start"])
                b = ctx.fmt.time_text(r["end"])
                if sep.strip() in a or sep.strip() in b or \
                        H.time(a, ctx.code) != (True, hm(r["start"])) or \
                        H.time(b, ctx.code) != (True, hm(r["end"])):
                    return None
                texts.append(a + sep + b)
            import unicodedata
            nsep = unicodedata.normalize("NFKC", sep)
            t.add(Column("range", ctx.header("time_range"), texts))
            t.outs.append(("start_time",
                           "time(part(col({range}), %r, 0))" % nsep))
            t.outs.append(("end_time",
                           "time(part(col({range}), %r, 1))" % nsep))
            for rec, r in zip(truth, recs):
                rec["start_time"] = hm(r["start"])
                rec["end_time"] = hm(r["end"])
            t.traps.add("T9")
        elif not time_column(ctx, t, "start", ctx.header("start_time"),
                             [r["start"] for r in recs], "start_time",
                             truth):
            return None
    if end == "column":
        if not time_column(ctx, t, "end", ctx.header("end_time"),
                           [r["end"] for r in recs], "end_time", truth):
            return None
        t.blocks.append([k for k in ("start", "end") if t.has(k)])
    elif end == "duration":
        if not S.duration_column(ctx, t, "dur", ctx.header("duration"),
                                 [r["minutes"] for r in recs],
                                 "duration_min", truth):
            return None
    # ---- who and what
    if rng.random() < 0.85:
        C.text_column(ctx, t, "client", ctx.header("booking_client"),
                      [r["client"] for r in recs], "client", truth,
                      digits=False)
    if rng.random() < 0.75:
        C.text_column(ctx, t, "service", ctx.header("booking_service"),
                      [r["service"] for r in recs], "service", truth)
    if staff_price or rng.random() < 0.3:
        C.text_column(ctx, t, "staff", ctx.header("performer"),
                      [r["staff"] for r in recs], "staff", truth,
                      digits=False)
    if status is None:
        status = "T12" in traps
    if status:
        status_column(ctx, t, "status", ctx.header("booking_status"),
                      [r["status"] for r in recs], "status", truth,
                      "booking_status")
    has_price = False
    if staff_price or rng.random() < 0.3:
        C.price_block(ctx, t, recs, truth,
                      dict(plan, traps=traps - {"T2"}), tax=False)
        has_price = True
    if day_sections and len(t.columns) < 2:
        return None
    t.truth = truth
    text_keys = [k for k in ("client", "service", "staff") if t.has(k)]
    label_key = "client" if t.has("client") else \
        "service" if t.has("service") else None
    spec = None
    if has_price and label_key:
        spec = {"label_key": label_key, "sum_keys": ["price"],
                "amounts_of": {"price": [rec.get("price") for rec in truth]},
                "groups": None}
    M.decorate(ctx, t, plan, text_keys=text_keys, totals_spec=spec)
    return t
