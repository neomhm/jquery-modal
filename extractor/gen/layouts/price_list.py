"""
price_list.py - price lists, rate cards and menus (6 layouts).
Every item is SERVICE and its price is PRICE; call-out fees and
delivery charges are O.
"""
import datetime

from gen.doc import Cell, Heading, Para, Table
from gen.layouts.common import (contact_lines, kv, layout, lines, maybe,
                                money_cell, pick, presence_ok, try_)
from gen.text import AText


def _setup(ctx):
    doc = ctx.doc
    t = ctx.title("doc", "price_list")
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    return t


def _validity(ctx):
    at = ctx.phrase("phrases", "price_validity")
    if at is not None:
        at.mark_trap("T7")
    return at


def _services(ctx, k=None):
    S = ctx.S
    k = min(len(S.services), k or ctx.rng.randint(5, 15))
    return ctx.rng.sample(S.services, k)


@layout("price_list.P01", "price_list")
def price_table(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    S = ctx.S
    doc.add(Heading(ctx.name(S)))
    doc.add(Heading(title, level=2))
    v = _validity(ctx)
    if v is not None:
        doc.add(Para(v, prose=False))
    rows = [[Cell(ctx.kw("pl_item")), Cell(ctx.kw("pl_unit")),
             Cell(ctx.kw("pl_price"))]]
    for s in _services(ctx):
        rows.append([Cell(ctx.service(s["name"])), Cell(ctx.unit(s["unit"])),
                     money_cell(ctx, s["price"], "PRICE",
                                pick(ctx, ["bare", "doc"]))])
    doc.add(Table(rows))
    doc.add(Para(AText(ctx.kw(pick(ctx, ["pl_incl_tax", "pl_excl_tax"]))),
                 prose=False))
    cl = contact_lines(ctx, S)
    if cl is not None:
        doc.add(Para(lines(ctx.addr(S), cl), prose=False))
    return doc


@layout("price_list.P02", "price_list")
def dotted_list(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    doc.add(Heading(title))
    out = []
    for s in _services(ctx):
        line = AText()
        line.add(ctx.service(s["name"]))
        line.add(" " + "." * ctx.rng.randint(3, 20) + " ")
        line.add(ctx.money(s["price"], "PRICE"))
        if maybe(ctx, 0.4):
            line.add(" / " + ctx.unit(s["unit"]))
        out.append(line)
    doc.add(Para(lines(*out), prose=False))
    v = _validity(ctx)
    if v is not None:
        doc.add(Para(v, prose=False))
    doc.add(Para(lines(ctx.name(ctx.S), ctx.addr(ctx.S)), prose=False))
    return doc


@layout("price_list.P03", "price_list")
def two_prices(ctx):
    """Reference, item, unit, price excl. and incl. tax."""
    doc = ctx.doc
    title = _setup(ctx)
    rate = (ctx.loc.get("vat") or [0])[0]
    rows = [[Cell(ctx.kw("pl_ref")), Cell(ctx.kw("pl_item")),
             Cell(ctx.kw("pl_unit")),
             Cell(ctx.kw("pl_price") + " " + ctx.kw("pl_excl_tax")),
             Cell(ctx.kw("pl_price") + " " + ctx.kw("pl_incl_tax"))]]
    dec = 2 if ctx.loc["cents"] else 0
    for k, s in enumerate(_services(ctx), start=1):
        incl = round(s["price"] * (1 + rate / 100), dec)
        rows.append([Cell(AText("%03d" % k, trap="T6")),
                     Cell(ctx.service(s["name"])),
                     Cell(ctx.unit(s["unit"])),
                     money_cell(ctx, s["price"], "PRICE"),
                     money_cell(ctx, incl, "PRICE")])
    doc.add(Heading(title))
    doc.add(Para(ctx.name(ctx.S), prose=False))
    doc.add(Table(rows))
    return doc


@layout("price_list.P05", "price_list")
def rate_card(ctx):
    """Hourly / daily rates of a trade, with a call-out fee (O)."""
    doc = ctx.doc
    title = _setup(ctx)
    S = ctx.S
    doc.add(Heading(title))
    doc.add(Para(lines(ctx.name(S), ctx.addr(S)), prose=False))
    out = []
    for s in _services(ctx, ctx.rng.randint(3, 8)):
        out.append(AText().add(ctx.service(s["name"])).add(
            ctx.colon() + " ").add(ctx.money(s["price"], "PRICE")).add(
            " / " + ctx.unit(s["unit"])))
    fee = round(ctx.rng.uniform(20, 80) * ctx.loc["usd_rate"] *
                ctx.loc["price_level"], 0)
    out.append(AText(ctx.kw("fee") + ctx.colon() + " " +
                     ctx.money(fee).text, trap="T9"))
    doc.add(Para(lines(*out), prose=False))
    v = _validity(ctx)
    if v is not None:
        doc.add(Para(v, prose=False))
    return doc


@layout("price_list.P06", "price_list")
def packages(ctx):
    """Packages or plans side by side."""
    doc = ctx.doc
    title = _setup(ctx)
    items = _services(ctx, ctx.rng.randint(2, 4))
    doc.add(Heading(title))
    header = [Cell("")] + [Cell(ctx.service(s["name"])) for s in items]
    prices = [Cell(ctx.kw("pl_price"))] + [
        money_cell(ctx, s["price"], "PRICE", "doc") for s in items]
    units = [Cell(ctx.kw("pl_unit"))] + [Cell(ctx.unit(s["unit"]))
                                         for s in items]
    doc.add(Table([[Cell(ctx.kw("pl_item"))] + [Cell("") for _ in items],
                   header[0:1] + header[1:], prices, units]))
    cl = contact_lines(ctx, ctx.S, one_line=True)
    if cl is not None:
        doc.add(Para(cl, prose=False))
    return doc
