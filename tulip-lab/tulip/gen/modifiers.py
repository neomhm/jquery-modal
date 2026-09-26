"""
gen/modifiers.py - the traps and variations every family can take:
title rows above the header (T5), totals and subtotals (T4), notes rows
under the table (T14), repeated header rows (T6), blank rows, irrelevant
extra columns (section 10.5) and two-row headers.

A family calls `decorate(ctx, table, plan, ...)` after building its
columns and truth; each modifier records its trap id in table.traps.
"""
import datetime
import string

import helpers as H
import tulipscript as ts
from gen.sheetkit import Column

REF = datetime.date(2026, 6, 30)


# ---------------------------------------------------------------------
#  extra columns (0-5 irrelevant columns)
# ---------------------------------------------------------------------
def extra_columns(ctx, table, count):
    rng, n = ctx.rng, table.n
    kinds = ["code", "date", "person", "word", "number"]
    used = set(c.header for c in table.columns)
    for k in range(count):
        kind = rng.choice(kinds)
        header = ctx.extra_header(kind)
        if header in used:
            continue
        used.add(header)
        cells = []
        if kind == "code":
            prefix = rng.choice(["", "A", "R", "L", "Z"])
            cells = ["%s%d-%02d" % (prefix, rng.randint(1, 30),
                                    rng.randint(1, 99))
                     if rng.random() < 0.85 else None for _ in range(n)]
        elif kind == "date":
            cells = [ctx.fmt.date(REF - datetime.timedelta(
                days=rng.randint(1, 900)))[0] for _ in range(n)]
        elif kind == "person":
            pool = [ctx.person()["full"] for _ in range(3)]
            cells = [rng.choice(pool) for _ in range(n)]
        elif kind == "word":
            pool = [w for w in (ctx.words.get("categories") or [])] + \
                [ctx.company()[:18] for _ in range(2)]
            pool = pool[:rng.randint(2, 5)] or ["-"]
            cells = [rng.choice(pool) for _ in range(n)]
        else:
            cells = [rng.choice([rng.randint(1, 50), rng.randint(1, 999)])
                     for _ in range(n)]
            if not ctx.typed:
                cells = [str(c) for c in cells]
        if all(c is None for c in cells):
            cells[0] = "1"
        table.add(Column("extra%d" % k, header, cells, kind="extra"))


# ---------------------------------------------------------------------
#  title rows, notes rows, repeated headers, blank rows
# ---------------------------------------------------------------------
def title_rows(ctx, table):
    """T5: one to three lines above the header."""
    rng = ctx.rng
    lines = []
    first = ctx.title(table.target)
    if first:
        lines.append(first)
    if rng.random() < 0.35:
        lines.append(ctx.business_name())
    if rng.random() < 0.2:
        lines.append(ctx.fmt.date_text(REF - datetime.timedelta(
            days=rng.randint(0, 60))))
    if not lines:
        return
    table.title_rows = lines
    table.blank_after_title = rng.random() < 0.7
    table.traps.add("T5")


def notes_rows(ctx, table, text_keys):
    """T14: lines under the table. They sit in a column that no required
    field reads with anything but text() - so the rows come out as
    'empty' (not imported, no filter needed)."""
    required = set(f for f, _, req in ts.SCHEMAS[table.target] if req)
    # a notes line may sit in a text column, but never in the one column
    # that holds EVERY required field (the line would become a record)
    text_keys = [k for k in text_keys if plain_text(table, k) and
                 not required <= set(fields_reading(table, k))]
    if not text_keys:
        return
    rng = ctx.rng
    lines = []
    for _ in range(rng.choice([1, 1, 2])):
        line = ctx.notes_row()
        if line and line not in lines and \
                not any(line.casefold().startswith(w.casefold())
                        for w in H.TOTALS):
            lines.append(line)
    if not lines:
        return
    table.notes_rows = lines
    table.notes_key = rng.choice(text_keys)
    table.traps.add("T14")


def fields_reading(table, key):
    return [f for f, tpl in table.outs if "{%s}" % key in tpl]


def plain_text(table, key):
    """True when the program reads column `key` only as text({key}) - a
    notes line there gives an empty row, never a parse failure."""
    if key in table.unpivot:
        return False
    mentions = [tpl for _, tpl in table.outs if "{%s}" % key in tpl]
    return all(tpl == "text(col({%s}))" % key for tpl in mentions)


def repeated_headers(ctx, table):
    """T6: the header row repeated inside the table (printed exports)."""
    if table.n < 12:
        return
    rng = ctx.rng
    every = rng.randint(8, 30)
    table.repeat_header_at = list(range(every, table.n, every))
    if table.repeat_header_at:
        table.traps.add("T6")


def blank_rows(ctx, table):
    rng = ctx.rng
    if table.n >= 6 and rng.random() < 0.3:
        table.blank_rows_at = rng.sample(range(2, table.n),
                                         min(rng.randint(1, 2),
                                             table.n - 2))


# ---------------------------------------------------------------------
#  totals and subtotals (T4)
# ---------------------------------------------------------------------
def totals(ctx, table, label_key, sum_keys, amounts_of, groups=None,
           force_groups=False):
    """A TOTAL row at the end and, with groups (record index ranges),
    subtotal rows after each group. amounts_of: {key: [amount per
    record]}. The label goes in label_key's column."""
    rng = ctx.rng
    words_total = ctx.values.get("totals") or ["Total"]
    words_sub = ctx.values.get("subtotals") or words_total
    cents = ctx.loc["cents"]

    def sums(idx):
        out = {}
        for key in sum_keys:
            vals = [amounts_of[key][i] for i in idx
                    if amounts_of[key][i] is not None]
            if vals:
                out[key] = round(sum(vals), 2 if cents else 0)
        return out

    if groups and (force_groups or rng.random() < 0.6):
        word = rng.choice(words_sub)
        for name, idx in groups:
            label = word + (" " + name if name and rng.random() < 0.7
                            else "")
            table.subtotals.append((idx[-1], label, sums(idx)))
    if not table.subtotals or rng.random() < 0.7:
        label = rng.choice(words_total)
        if rng.random() < 0.3 and ctx.lang in ("fr", "en", "es", "it",
                                                "ru"):
            label = label.upper()
        table.totals = (label, sums(range(table.n)))
    table.total_label_key = label_key
    table.traps.add("T4")


# ---------------------------------------------------------------------
#  two-row header
# ---------------------------------------------------------------------
def group_row(ctx, table, groups):
    """groups: {group key: [column keys]} -> labels above them."""
    for gkey, keys in groups.items():
        label = ctx.group_label(gkey)
        for k in keys:
            if table.has(k):
                table.group_labels[k] = label


# ---------------------------------------------------------------------
#  everything at once
# ---------------------------------------------------------------------
def decorate(ctx, table, plan, text_keys=(), totals_spec=None):
    """Apply the plan's traps that every family supports."""
    rng = ctx.rng
    traps = plan["traps"]
    if plan.get("extra", 0):
        extra_columns(ctx, table, plan["extra"])
    if "T5" in traps:
        title_rows(ctx, table)
    if "T4" in traps and totals_spec and table.n >= 8:
        totals(ctx, table, **totals_spec)
    if "T14" in traps:
        notes_rows(ctx, table, list(text_keys))
    if "T6" in traps:
        repeated_headers(ctx, table)
    blank_rows(ctx, table)
