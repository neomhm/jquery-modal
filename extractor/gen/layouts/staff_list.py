"""
staff_list.py - staff lists, org charts and HR exports (5 layouts).
The manager's row is S_PERSON; every other name is O (T11); salaries
and identity numbers are always O (rule R7); a total headcount is STAFF.
"""
import datetime

from gen import ids as I
from gen.doc import Cell, Heading, Para, Table
from gen.layouts.common import kv, layout, lines, maybe, pick, presence_ok
from gen.names import person
from gen.text import AText


def _setup(ctx):
    doc = ctx.doc
    t = ctx.title("doc", "staff_list")
    doc.meta["title_text"] = t
    doc.meta["sheet_title"] = t[:28]
    return t


def _people(ctx, n=None):
    S = ctx.S
    staff = ctx.staff_value(S) or 3
    n = n or min(staff, ctx.rng.randint(3, 20))
    out = []
    if presence_ok(ctx, S, "manager"):
        out.append(("manager", S.manager, S.manager_title))
    positions = ctx.lst("positions") or ["Assistant"]
    departments = ctx.lst("departments") or ["Admin"]
    for _ in range(max(1, n - len(out))):
        p = person(ctx.rng, ctx.loc)
        out.append(("staff", p, ctx.rng.choice(positions),
                    ctx.rng.choice(departments)))
    return out


def _name_cell(ctx, entry):
    if entry[0] == "manager":
        return Cell(ctx.person(ctx.S, short=False))
    return Cell(AText(entry[1]["full"], trap="T11"))


def _total(ctx):
    S = ctx.S
    if not S.staff or not presence_ok(ctx, S, "staff"):
        return None
    return AText(ctx.label("sl_total")).add(ctx.staff(S, "exact"))


@layout("staff_list.S01", "staff_list")
def staff_table(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    doc.add(Heading(title))
    doc.add(Para(ctx.name(ctx.S), prose=False))
    rows = [[Cell(ctx.kw("sl_name")), Cell(ctx.kw("sl_position")),
             Cell(ctx.kw("sl_department")), Cell(ctx.kw("sl_start_date"))]]
    for e in _people(ctx):
        start = datetime.date(ctx.rng.randint(2005, 2025),
                              ctx.rng.randint(1, 12), ctx.rng.randint(1, 28))
        dept = e[3] if len(e) > 3 else (ctx.lst("departments") or [""])[0]
        rows.append([_name_cell(ctx, e), Cell(e[2]), Cell(dept),
                     Cell(ctx.date_o(start),
                          AText(ctx.fmt.date(start, "sheet")[0]))])
    doc.add(Table(rows))
    tot = _total(ctx)
    if tot is not None:
        doc.add(Para(tot, prose=False))
    return doc


@layout("staff_list.S02", "staff_list")
def org_chart(ctx):
    doc = ctx.doc
    _setup(ctx)
    S = ctx.S
    doc.add(Heading(ctx.name(S)))
    out = []
    people = _people(ctx, ctx.rng.randint(4, 10))
    for e in people:
        if e[0] == "manager":
            out.append(AText(e[2] + ": ").add(ctx.person(S)))
    for e in people:
        if e[0] != "manager":
            out.append(AText("  %s – %s (%s)" % (e[3], e[1]["full"], e[2]),
                             trap="T11"))
    doc.add(Para(lines(*out), prose=False))
    tot = _total(ctx)
    if tot is not None:
        doc.add(Para(tot, prose=False))
    return doc


@layout("staff_list.S03", "staff_list")
def hr_export(ctx):
    """An HR export with ids, contracts and salaries (all O)."""
    doc = ctx.doc
    _setup(ctx)
    rows = [[Cell(ctx.kw("sl_employee_id")), Cell(ctx.kw("sl_name")),
             Cell(ctx.kw("sl_position")), Cell(ctx.kw("sl_contract")),
             Cell(ctx.kw("sl_salary"))]]
    contracts = ctx.lex.get("kw", {}).get("contract_types") or ["CDI"]
    for k, e in enumerate(_people(ctx), start=1):
        salary = ctx.rng.randint(18, 90) * 1000 * ctx.loc["usd_rate"] * \
            ctx.loc["price_level"] / 12
        rows.append([Cell(AText("E%04d" % (100 + k), trap="T6")),
                     _name_cell(ctx, e), Cell(e[2]),
                     Cell(ctx.rng.choice(contracts)),
                     Cell(AText(ctx.fmt.num(round(salary, -1), 0)),
                          AText(str(int(round(salary, -1)))))])
    doc.add(Table(rows))
    return doc


@layout("staff_list.S04", "staff_list")
def phone_directory(ctx):
    doc = ctx.doc
    title = _setup(ctx)
    doc.add(Heading(title))
    out = []
    for e in _people(ctx):
        ext = "%d" % ctx.rng.randint(100, 499)
        if e[0] == "manager":
            out.append(AText().add(ctx.person(ctx.S)).add(
                " – %s – %s %s" % (e[2], ctx.kw("sl_phone"), ext)))
        else:
            out.append(AText("%s – %s – %s %s" % (e[1]["full"], e[2],
                                                 ctx.kw("sl_phone"), ext),
                             trap="T11"))
    doc.add(Para(lines(*out), prose=False))
    return doc


@layout("staff_list.S05", "staff_list")
def headcount_summary(ctx):
    """Headcount by department with the total (STAFF) and an identity
    document column for the manager (O, rule R7)."""
    doc = ctx.doc
    title = _setup(ctx)
    S = ctx.S
    doc.add(Heading(title))
    doc.add(Para(ctx.name(S), prose=False))
    n = ctx.staff_value(S) or 3
    depts = (ctx.lst("departments") or ["A", "B"])[:ctx.rng.randint(2, 4)]
    left = n
    rows = [[Cell(ctx.kw("sl_department")), Cell(ctx.kw("staff"))]]
    for k, d in enumerate(depts):
        c = left if k == len(depts) - 1 else ctx.rng.randint(0, left)
        left -= c
        rows.append([Cell(d), Cell(AText(str(c), trap="T8"))])
    doc.add(Table(rows))
    tot = _total(ctx)
    if tot is not None:
        doc.add(Para(tot, prose=False))
    if presence_ok(ctx, S, "manager"):
        pid = I.personal_id(ctx.rng, ctx.country)
        doc.add(Para(AText(S.manager_title + ": ").add(ctx.person(S)).add(
            AText(" – ID %s" % pid, trap="T6")), prose=False))
    return doc
