"""
other.py - everything else found in a business folder (10 layouts):
meeting notes, recipes, manuals, unrelated news, to-do lists, memos,
plannings, notes ... Nothing is labelled, except in a press article
that is clearly about the business (rule R5, "other").
"""
import datetime

from gen.doc import Cell, Heading, Para, Table
from gen.layouts.common import layout, lines, maybe, pick
from gen.text import AText


def _title(ctx, key):
    items = (ctx.titles_.get("other") or {}).get(key) or [key]
    t = ctx.rng.choice(items)
    ctx.doc.meta["title_text"] = t
    return t


def _noise(ctx, key, n):
    items = (ctx.sent.get("noise") or {}).get(key) or []
    order = list(range(len(items)))
    ctx.rng.shuffle(order)
    out = []
    for k in order[:n]:
        if ctx.can_fill(items[k]):
            try:
                out.append(ctx.fill(items[k], "noise.%s.%s.%02d" %
                                    (key, ctx.lang, k + 1)))
            except Exception:
                pass
    return out


def _simple(ctx, key, title_key, n):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, title_key)))
    for at in _noise(ctx, key, n):
        doc.add(Para(at, prose=maybe(ctx, 0.7)))
    return doc


@layout("other.O01", "other")
def meeting_notes(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "meeting")))
    when = ctx.date_o(datetime.date(2025, ctx.rng.randint(1, 12),
                                    ctx.rng.randint(1, 28)))
    doc.add(Para(AText(when), prose=False))
    people = ", ".join(ctx.plain("person") for _ in range(
        ctx.rng.randint(2, 4)))
    doc.add(Para(AText(people), prose=False))
    for at in _noise(ctx, "meeting", ctx.rng.randint(2, 4)):
        doc.add(Para(AText("- ").add(at), prose=False))
    return doc


@layout("other.O02", "other")
def recipe(ctx):
    return _simple(ctx, "recipe", "recipe", ctx.rng.randint(2, 4))


@layout("other.O03", "other")
def manual(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "manual")))
    for k, at in enumerate(_noise(ctx, "manual", ctx.rng.randint(3, 6)),
                           start=1):
        doc.add(Para(AText("%d. " % k).add(at)))
    return doc


@layout("other.O04", "other")
def news_article(ctx):
    return _simple(ctx, "news", "news", ctx.rng.randint(2, 4))


@layout("other.O05", "other")
def todo_list(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "todo")))
    items = _noise(ctx, "todo", ctx.rng.randint(2, 4))
    doc.add(Para(lines(*[AText(pick(ctx, ["[ ] ", "- ", "* ", ""])).add(at)
                         for at in items]), prose=False))
    return doc


@layout("other.O06", "other")
def memo(ctx):
    return _simple(ctx, "memo", "memo", ctx.rng.randint(2, 4))


@layout("other.O07", "other")
def generic_text(ctx):
    doc = ctx.doc
    ctx.doc.meta["title_text"] = "notes"
    for at in _noise(ctx, "generic", ctx.rng.randint(2, 5)):
        doc.add(Para(at))
    return doc


@layout("other.O08", "other")
def press_article(ctx):
    """A press article about the business: its facts are labelled."""
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "press")))
    for at in _noise(ctx, "press", ctx.rng.randint(2, 4)):
        doc.add(Para(at))
    return doc


@layout("other.O09", "other")
def planning_table(ctx):
    """A weekly planning: people and tasks (all O)."""
    doc = ctx.doc
    days = ctx.lex["weekdays"]["full"][:5]
    rows = [[Cell("")] + [Cell(d) for d in days]]
    tasks = _noise(ctx, "todo", 4) or [AText("-")]
    for _ in range(ctx.rng.randint(2, 5)):
        row = [Cell(ctx.plain("person"))]
        for _ in days:
            t = ctx.rng.choice(tasks).text[:30] if maybe(ctx, 0.6) else ""
            row.append(Cell(t))
        rows.append(row)
    ctx.doc.meta["title_text"] = "planning"
    doc.add(Heading(_title(ctx, "report")))
    doc.add(Table(rows))
    return doc


@layout("other.O10", "other")
def internal_report(ctx):
    doc = ctx.doc
    doc.add(Heading(_title(ctx, "report")))
    for at in _noise(ctx, pick(ctx, ["memo", "generic", "meeting"]),
                     ctx.rng.randint(2, 4)):
        doc.add(Para(at))
    return doc
