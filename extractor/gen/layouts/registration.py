"""
registration.py - register extracts, licences and tax-registration
certificates, one layout per country family (data in
gen/data/registration.json; held-out families in
gen/layouts/test/registration_test.json).

S is the REGISTERED organisation (never the registry office, which is O
and trap T14). The registration / incorporation date is FOUNDED; the
date the extract was issued is DOC_DATE.
"""
import datetime
import json
import pathlib
import re

from gen import data as D
from gen import ids as I
from gen.ctx import CannotFill
from gen.doc import Cell, Heading, Para, Table
from gen.layouts.common import REGISTRY, lines, maybe, pick, presence_ok
from gen.text import AText

HERE = pathlib.Path(__file__).resolve().parent

# families whose documents exist only for companies
COMPANIES_ONLY = {"FR_kbis", "GB_coi", "GB_overview", "IN_coi", "AU_asic",
                  "CA_corp", "RU_egrul", "RU_tax_cert", "ES_nota",
                  "JP_touki", "KR_touki", "US_state", "IT_visura",
                  "SG_acra", "NG_cac", "BY_cert", "CH_it_rc", "CH_rc"}


def load_families():
    fams = dict(D.registration_families().get("families", {}))
    test = HERE / "test" / "registration_test.json"
    if test.exists():
        with open(test, encoding="utf-8") as f:
            fams.update(json.load(f).get("families", {}))
    return fams


def ensure_reg_id(org, type_, rng):
    """The registered number of this type (derived from the business's
    other numbers when possible), added to its identifiers so the
    folder truth knows it."""
    for r in org.reg_ids:
        if r["type"] == type_ or (type_ in ("RU_INN10", "RU_INN12") and
                                  r["type"] in ("RU_INN10", "RU_INN12")):
            return r
    info = {"kind": org.cls if org.cls != "other" else "company",
            "family": org.manager["family"], "given": org.manager["given"],
            "name": org.core}
    for r in org.reg_ids:
        if r["type"] in ("FR_SIRET", "FR_TVA", "FR_SIREN"):
            info["siren"] = r["compact"][-9:] if r["type"] == "FR_TVA" \
                else r["compact"][:9]
        if r["type"] == "IN_PAN":
            info["pan"] = r["compact"]
        if r["type"] == "JP_CORP":
            info["corp"] = r["compact"]
    compact = I.make_id(rng, type_, info)
    labels = [x["labels"] for x in org.loc["reg_ids"]
              if x["type"] == type_ or
              (x["type"] == "RU_INN" and type_.startswith("RU_INN"))]
    entry = {"type": type_, "compact": compact,
             "labels": labels[0] if labels else [type_]}
    org.reg_ids.append(entry)
    return entry


def _fill_literal(ctx, text):
    rng = ctx.rng
    place = ctx.S.address
    region = ""
    for p in (D.locale_list(ctx.loc["code"], "cities") or []):
        if p.get("city") == place.get("city"):
            region = p.get("region") or p.get("state") or \
                p.get("province") or ""
            break
    return (text.replace("{city}", place.get("city") or "")
            .replace("{region}", region or place.get("city") or "")
            .replace("{n}", str(rng.randint(10, 99999)))
            .replace("{future}", ctx.date_o(datetime.date(
                rng.randint(2070, 2120), rng.randint(1, 12),
                rng.randint(1, 28)))))


def _activity_items(ctx, S):
    phrases = (S.act.get("phrases") or {}).get(ctx.key) or []
    services = [s["name"] for s in (S.services or [])]
    rest = [p for p in phrases[1:]] + services[:4]
    ctx.rng.shuffle(rest)
    return rest[:ctx.rng.randint(1, 4)]


def field_value(ctx, field):
    """The value of one row (an AText), or None to skip the row."""
    S, rng = ctx.S, ctx.rng
    if field == "legal":
        return ctx.name(S, legal=True)
    if field == "legal_long":
        form = S.form
        if form.get("long") and form.get("attach") and S.lang == "ru":
            text = "%s «%s»" % (form["long"][0], S.core.strip("«»\"“”"))
            return AText(text.upper() if ctx.caps else text, "S_NAME")
        return ctx.name(S, legal=True)
    if field == "trading":
        if S.trading == S.legal:
            return None
        return ctx.name(S, legal=False)
    if field in ("form", "form_long"):
        if not presence_ok(ctx, S, "legal_form"):
            return None
        return ctx.legal_form(S, long=(field == "form_long"))
    if field == "capital":
        if not S.capital or not presence_ok(ctx, S, "capital"):
            return None
        return ctx.capital(S, prose=False)
    if field == "capital_bare":
        if not S.capital or not presence_ok(ctx, S, "capital"):
            return None
        return AText(ctx.fmt.num(S.capital, 0), "CAPITAL",
                     {"kind": "amount", "value": float(S.capital),
                      "currency": None})
    if field == "address":
        return ctx.addr(S, multiline=maybe(ctx, 0.3))
    if field == "founded":
        if not presence_ok(ctx, S, "founded"):
            return None
        return ctx.founded(S, "date")
    if field == "activity":
        if not presence_ok(ctx, S, "activity"):
            return None
        first = ctx.activity(S)
        rest = _activity_items(ctx, S)
        if not rest or maybe(ctx, 0.3):
            return first
        if ctx.lang in ("ja", "ko"):
            out = AText("1．" if ctx.lang == "ja" else "1. ").add(first)
            for k, item in enumerate(rest, start=2):
                out.add("\n%d%s%s" % (k, "．" if ctx.lang == "ja" else ". ",
                                      item))
            return out
        sep = "；" if ctx.lang == "zh" else "; "
        out = AText().add(first)
        for item in rest:
            out.add(sep + item)
        return out
    if field == "activity_code":
        if not S.act_code or not presence_ok(ctx, S, "activity_code"):
            return None
        return ctx.act_code(S, keyword=False)
    if field == "code_and_activity":
        out = AText()
        if S.act_code and presence_ok(ctx, S, "activity_code"):
            out.add(ctx.act_code(S, keyword=False))
        if presence_ok(ctx, S, "activity"):
            if out.text:
                out.add(pick(ctx, [" – ", " ", " - ", ": "]))
            out.add(ctx.activity(S))
        return out if out.text else None
    if field == "manager":
        if not presence_ok(ctx, S, "manager"):
            return None
        return ctx.person(S, short=False)
    if field == "phone":
        if not presence_ok(ctx, S, "phone"):
            return None
        return ctx.phone(S)
    if field == "email":
        if not S.email or not presence_ok(ctx, S, "email"):
            return None
        return ctx.email(S)
    if field == "url":
        if not S.website or not presence_ok(ctx, S, "website"):
            return None
        return ctx.url(S, social=False)
    if field.startswith("reg:"):
        if not presence_ok(ctx, S, "reg_id"):
            return None
        r = ensure_reg_id(S, field[4:], rng)
        return AText(I.show(rng, r["type"], r["compact"]), "S_REG_ID",
                     {"kind": "reg_id", "compact": r["compact"],
                      "type": r["type"]})
    if field == "doc_date":
        return ctx.doc_date()
    if field == "o_date":
        d = S.founded + datetime.timedelta(days=rng.randint(0, 900))
        return AText(ctx.date_o(d), trap="T15")
    if field == "birth":
        d = datetime.date(rng.randint(1950, 1995), rng.randint(1, 12),
                          rng.randint(1, 28))
        return AText(ctx.date_o(d) + ((" – " + ctx.plain("city"))
                                      if maybe(ctx, 0.5) else ""))
    if field == "registry":
        regs = ((ctx.lex.get("orgs") or {}).get("registry") or {}).get(
            ctx.country) or ["Registry"]
        return AText(_fill_literal(ctx, rng.choice(regs)), trap="T14")
    if field == "o_person":
        return AText("%s – %s" % (ctx.plain("person"),
                                  ctx.plain("position")), trap="T14")
    if field == "o_org":
        return AText("%s, %s" % (ctx.plain("other_org"),
                                 ctx.plain("other_address")), trap="T14")
    if field == "staff":
        if not S.staff or not presence_ok(ctx, S, "staff"):
            return None
        return ctx.staff(S, "exact")
    if field.startswith("o:"):
        return AText(_fill_literal(ctx, field[2:]))
    return None


def render_family(ctx, fid, spec):
    doc = ctx.doc
    rng = ctx.rng
    S = ctx.S
    title = rng.choice(spec["title"])
    authority = _fill_literal(ctx, rng.choice(spec["authority"]))
    doc.meta["title_text"] = title
    doc.meta["sheet_title"] = title[:28]
    doc.add(Para(AText(authority, trap="T14"), prose=False))
    doc.add(Heading(title))
    style = spec.get("style", "kv")
    colon = ctx.colon()
    kv_lines = []
    table_rows = []
    values = {}
    for label, field in spec["rows"]:
        if field == "section":
            if style == "table":
                table_rows.append([Cell(label), Cell("")])
            else:
                if kv_lines:
                    doc.add(Para(lines(*kv_lines), prose=False))
                    kv_lines = []
                doc.add(Heading(label, level=2))
            continue
        try:
            value = field_value(ctx, field)
        except CannotFill:
            value = None
        if value is None:
            continue
        values[field] = value
        if style == "table":
            table_rows.append([Cell(label), Cell(value)])
        else:
            line = AText(label + colon + " ")
            line.add(value)
            kv_lines.append(line)
    if style == "table" and table_rows:
        header = [Cell(ctx.kw("fin_item")), Cell(ctx.kw("description"))]
        doc.add(Table([header] + table_rows))
    if kv_lines:
        doc.add(Para(lines(*kv_lines), prose=False))
    if style == "cert":
        for text in spec.get("prose", []):
            doc.add(Para(_cert_text(ctx, text), prose=True))
    closing = spec.get("closing")
    if closing:
        doc.add(Para(AText(rng.choice(closing)), prose=False))
    return doc


SLOT = re.compile(r"\{([^{}]+)\}")


def _cert_text(ctx, text):
    out = AText()
    pos = 0
    for m in SLOT.finditer(text):
        out.add(text[pos:m.start()])
        name = m.group(1)
        if name == "address_multi":
            out.add(ctx.addr(ctx.S, multiline=True))
        elif name == "o_control":
            out.add((ctx.S.core[:4] or "NAME").upper())
        else:
            try:
                value = field_value(ctx, name)
            except CannotFill:
                value = None
            out.add(value if value is not None else AText(""))
        pos = m.end()
    out.add(text[pos:])
    return out


def register_all():
    """One layout per family, id registration.<family id>."""
    for fid, spec in load_families().items():
        lid = "registration." + fid

        def make(fid=fid, spec=spec):
            def fn(ctx):
                return render_family(ctx, fid, spec)
            fn.__name__ = "registration_" + fid
            return fn
        REGISTRY[lid] = {"id": lid, "fn": make(), "doc_type":
                         "registration", "kind": "registration",
                         "family": spec["locales"][0],
                         "locales": spec["locales"],
                         "heldout_locale": bool(spec.get("heldout")),
                         "companies_only": fid in COMPANIES_ONLY}


register_all()
