"""
gen/tasks.py - plan and make ONE task (split, index): a sheet, its
preview, its program and its true rows.

The random generator of a task is seeded from (split, index), so every
task can be made again exactly (section 10.1).
"""
import datetime
import functools
import hashlib
import importlib
import math
import pathlib
import random
import re
import unicodedata

import config
import sheets
import tulipscript as ts
from gen import data as D
from gen import sheetkit as K
from gen.ctx import Ctx

HERE = pathlib.Path(__file__).resolve().parent

# section 10.3: share of tasks
SHARES = [("products", 0.22), ("services", 0.14), ("opening_hours", 0.10),
          ("staff", 0.10), ("clients", 0.10), ("bookings", 0.10),
          ("invoice_ledger", 0.12), ("no_matching_target", 0.06),
          ("missing_required", 0.035), ("not_a_table", 0.02),
          ("too_wide", 0.005)]
# section 10.3: 70% xlsx (typed values, number formats), 30% CSV (text)
XLSX_SHARE = 0.70
REFUSALS = ("no_matching_target", "missing_required", "not_a_table",
            "too_wide")

# section 10.4: how often each trap is DRAWN for a task of that target
# (a family may not be able to show it, so these sit above the minimum
# rates the checks require)
TRAPS = {
    "products": {"T1": 0.36, "T2": 0.34, "T3": 0.16, "T4": 0.7, "T5": 0.52,
                 "T6": 0.25, "T7": 0.35, "T8": 0.08, "T9": 0.7,
                 "T13": 0.33, "T14": 0.45},
    "services": {"T2": 0.34, "T5": 0.52, "T6": 0.25, "T7": 0.35, "T9": 0.7,
                 "T13": 0.33, "T14": 0.45},
    "opening_hours": {"T5": 0.52, "T8": 0.8, "T14": 0.45},
    "staff": {"T4": 0.65, "T5": 0.52, "T6": 0.25, "T10": 0.45, "T14": 0.45},
    "clients": {"T4": 0.65, "T5": 0.52, "T6": 0.25, "T10": 0.55, "T14": 0.45},
    "bookings": {"T4": 0.65, "T5": 0.52, "T6": 0.25, "T9": 0.55, "T11": 0.6,
                 "T12": 0.75, "T13": 0.33, "T14": 0.45},
    "invoice_ledger": {"T4": 0.65, "T5": 0.52, "T6": 0.25, "T12": 0.75,
                       "T13": 0.33, "T14": 0.45},
}
# rows: log-uniform 3-400, then capped by what the table can hold
MAX_ROWS = {"products": 400, "services": 400, "opening_hours": 7,
            "staff": 120, "clients": 400, "bookings": 400,
            "invoice_ledger": 400}
HELD_OUT_LOCALES = ["ar-MA", "zh-SG", "en-NG", "fr-SN", "ru-BY", "es-CL",
                    "it-CH"]


# ---------------------------------------------------------------------
#  the families
# ---------------------------------------------------------------------
def load_families():
    """{family id: module} from gen/layouts/*.py and gen/layouts/test/."""
    out = {}
    for folder, package in ((HERE / "layouts", "gen.layouts"),
                            (HERE / "layouts" / "test", "gen.layouts.test")):
        for path in sorted(folder.glob("*.py")):
            if path.stem.startswith("_"):
                continue
            module = importlib.import_module("%s.%s" % (package, path.stem))
            out[module.ID] = module
    return out


_FAMILIES = None


def families():
    global _FAMILIES
    if _FAMILIES is None:
        _FAMILIES = load_families()
    return _FAMILIES


@functools.lru_cache(maxsize=None)
def holdout():
    """gen/holdout.json (drawn once by gen/holdout.py), or {} before."""
    path = HERE / "holdout.json"
    return D.read_json(path) or {}


def group_of_new(item_id):
    """An item added after the hold-out draw: 80% train, 10% D, 10% T,
    from a hash of its id (section 11)."""
    x = int(hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "D" if x == 0 else "T" if x == 1 else "train"


def group_of_family(fid, hold):
    """T: the module lives in gen/layouts/test/. D: named in
    gen/holdout.json. A family newer than the draw: by hash."""
    module = families().get(fid)
    if module is not None and module.__name__.startswith("gen.layouts.test"):
        return "T"
    fams = hold.get("families") or {}
    if fid in fams:
        return fams[fid]
    if hold and fid not in (hold.get("known_families") or []):
        return group_of_new(fid)
    return "train"


def group_of_activity(act):
    return act.get("holdout") or "train"


# ---------------------------------------------------------------------
#  planning
# ---------------------------------------------------------------------
def seed_of(split, index):
    digest = hashlib.sha1(("%s-%d" % (split, index)).encode()).hexdigest()
    return int(digest[:16], 16)


R2 = (0.7548776662466927, 0.5698402909980532)   # 1/p, 1/p^2 (plastic p)


def r2_point(split, index):
    """The index-th point of the R2 sequence in the unit square, shifted
    per split -> (u, v)."""
    shift = (seed_of(split, 0) % 10007) / 10007.0
    return ((shift + (index + 1) * R2[0]) % 1.0,
            (shift * 0.5 + (index + 1) * R2[1]) % 1.0)


def weighted_at(x, pairs):
    """The item of `pairs` at position x (0..1) of the cumulative
    weights."""
    total = sum(w for _, w in pairs)
    x *= total
    for item, w in pairs:
        x -= w
        if x < 0:
            return item
    return pairs[-1][0]


def weighted(rng, pairs):
    total = sum(w for _, w in pairs)
    x = rng.random() * total
    for item, w in pairs:
        x -= w
        if x <= 0:
            return item
    return pairs[-1][0]


def choose_locale(rng, split, index, folders):
    langs = [l for l in config.LANGS
             if any(D.locale(c)["lang"] == l and D.locale(c)["data"] in
                    folders for c in D.locales())]
    if split == "test_locale":
        codes = [c for c in HELD_OUT_LOCALES if D.locale(c)["data"] in
                 folders]
        return codes[index % len(codes)] if codes else None
    lang = langs[index % len(langs)]
    pairs = [(c, v["weight"]) for c, v in D.locales().items()
             if v["lang"] == lang and v["weight"] > 0 and v["data"] in
             folders]
    return weighted(rng, pairs) if pairs else None


def suitable(act, folder, target):
    words = act["words"].get(folder) or {}
    items = words.get("items") or []
    n_prod = sum(1 for i in items if i.get("kind") == "product")
    n_serv = sum(1 for i in items if i.get("kind") == "service")
    if target == "products":
        return n_prod >= 5
    if target in ("services", "bookings"):
        return n_serv >= 4
    if target == "opening_hours":
        return act.get("hours") or act.get("customers") == "B2C"
    return bool(items)


def choose_activity(rng, split, folder, target):
    allowed = {"train", "D"} if split == "dev_heldout" else \
        {"train", "T"} if split == "test_heldout" else {"train"}
    acts = [a for a in D.activities()
            if group_of_activity(a) in allowed and suitable(a, folder,
                                                            target)]
    return rng.choice(acts) if acts else None


def choose_family(rng, split, target, hold, xlsx=None):
    """A layout family of the target, by weight. xlsx (the task's format,
    drawn once per task): an xlsx task never gets a CSV-only family; a
    CSV task gets one with probability c / 0.3 (c: the CSV-only families'
    share of the weight), so that every family keeps its weight AND the
    tasks are 70% xlsx whatever families decline (section 10.3)."""
    allowed = {"train", "D"} if split == "dev_heldout" else \
        {"train", "T"} if split == "test_heldout" else {"train"}
    fams = [f for fid, f in families().items()
            if f.TARGET == target and group_of_family(fid, hold) in allowed]
    if not fams:
        return None
    weights = [(f, getattr(f, "WEIGHT", 1.0)) for f in fams]
    if xlsx is None:
        return weighted(rng, weights)
    csv = [(f, w) for f, w in weights if getattr(f, "CSV_ONLY", False)]
    other = [(f, w) for f, w in weights if not getattr(f, "CSV_ONLY", False)]
    total = sum(w for _, w in weights)
    c = sum(w for _, w in csv) / total
    if xlsx or not csv:
        return weighted(rng, other or weights)
    if not other or rng.random() < min(1.0, c / (1.0 - XLSX_SHARE)):
        return weighted(rng, csv)
    return weighted(rng, other)


def draw_traps(rng, target, split):
    rates = TRAPS.get(target, {})
    boost = 2.0 if split == "traps" else 1.0
    return set(t for t, p in rates.items() if rng.random() < min(0.95,
                                                                  p * boost))


def rows_count(rng, target):
    n = int(round(math.exp(rng.uniform(math.log(3), math.log(400)))))
    return max(3, min(n, MAX_ROWS[target]))


def offered_targets(rng, answer, exclude=()):
    others = [t for t in config.TARGETS if t != answer and t not in exclude]
    k = rng.choice([0, 0, 1, 1, 2, 3])
    chosen = rng.sample(others, k)
    if answer and answer not in exclude:
        chosen.append(answer)
    if not chosen:
        chosen = rng.sample(others, 1)
    rng.shuffle(chosen)
    return chosen


# ---------------------------------------------------------------------
#  making a task
# ---------------------------------------------------------------------
def make_task(split, index, folders=None, tries=12, hold=None):
    """-> (task dict or None, [reason of every failed attempt])."""
    hold = holdout() if hold is None else hold
    folders = folders or D.folders_ready()
    reasons = []
    # WHAT the task is (its kind: a target or a refusal reason) and the
    # coin that decides its format are drawn ONCE per task, not again at
    # every attempt: a kind or a format whose layouts decline more often
    # would otherwise lose its share to the others (missing_required was
    # 3.1% for 3.5% drawn, xlsx 64% for 70%), section 10.3.
    # Both come from a low-discrepancy (R2) sequence over the task index,
    # so a split's shares are the drawn shares to within a few tasks, not
    # to within the noise of a random draw.
    u, coin = r2_point(split, index)
    kind = weighted_at(u, SHARES)
    for attempt in range(tries):
        rng = random.Random(seed_of(split, index) + 7919 * attempt)
        task, reason = _attempt(rng, split, index, hold, folders, kind,
                                coin)
        if task:
            return task, reasons
        reasons.append(reason)
    return None, reasons


def sheet_name_ok(name):
    """A name a real .xlsx sheet or .csv file can carry."""
    name = "".join("_" if ch in '[]:*?/\\' else ch for ch in name)
    return name.strip()[:31] or "Sheet1"


def is_discard(reason):
    """A self-check failure (section 10.1), as opposed to a layout that
    did not fit the drawn items (drawn again, not counted)."""
    return bool(reason) and (reason.startswith("self_check") or
                             reason in ("truth_mismatch", "empty_column"))


# ---------------------------------------------------------------------
#  hold-out header TEXTS (section 11). A header variant is compared the
#  way the model will see it: the tokenizer normalises NFKC, and case is
#  decorated at random, so 'Prix（€）' and 'PRIX (€)' are the same item.
#  A variant with {cur} matches that text with any currency symbol of
#  the language folder's locales.
# ---------------------------------------------------------------------
def norm_text(text):
    """NFKC, single spaces, case-folded: how two header texts compare."""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split()) \
        .casefold()


@functools.lru_cache(maxsize=None)
def _cur_alternation(folder):
    syms = set()
    for code, loc in D.locales().items():
        if loc["data"] != folder:
            continue
        syms.add(loc["currency"])
        for style in loc["money"]:
            s = style.replace("{n}", "").strip()
            if s:
                syms.add(s)
    syms = sorted(set(norm_text(s) for s in syms if s), key=len,
                  reverse=True)
    return "|".join(re.escape(s) for s in syms)


def _matcher(variants, folder):
    plain, pats = set(), []
    for v in variants:
        n = norm_text(v)
        if "{cur}" in n:
            pats.append(re.compile("^" + re.escape(n).replace(
                re.escape("{cur}"), "(?:%s)" % _cur_alternation(folder)) +
                "$"))
        elif n:
            plain.add(n)
    return plain, tuple(pats)


@functools.lru_cache(maxsize=None)
def held_matchers(folder):
    """{'D': matcher, 'T': matcher} of the header variants held out for a
    language folder: the drawn D variants, the T variants (compared by
    code only - never printed) and variants added after the draw, by
    hash (group_of_new)."""
    hold = holdout()
    per_field = (hold.get("headers") or {}).get(folder) or {}
    d_vars = [v["D"] for v in per_field.values() if v.get("D")]
    t_vars = []
    for vs in (D.headers_test(folder).get("fields") or {}).values():
        t_vars += list(vs)
    for key, vs in (D.headers(folder).get("fields") or {}).items():
        known = (per_field.get(key) or {}).get("known")
        if known is None:
            continue
        for v in vs:
            if v in known:
                continue
            g = group_of_new("%s/%s/%s" % (folder, key, v))
            if g == "D":
                d_vars.append(v)
            elif g == "T":
                t_vars.append(v)
    return {"D": _matcher(d_vars, folder), "T": _matcher(t_vars, folder)}


def held_groups_of_text(folder, text):
    """-> set of the hold-out groups ('D', 'T') a text IS, after
    normalisation."""
    n = norm_text(text)
    out = set()
    if not n:
        return out
    for g, (plain, pats) in held_matchers(folder).items():
        if n in plain or any(p.match(n) for p in pats):
            out.add(g)
    return out


def forbidden_groups(split):
    """Hold-out groups a sheet of this split must never show."""
    return {"dev_heldout": {"T"}, "test_heldout": {"D"}}.get(
        split, {"D", "T"})


def header_area_texts(rows, header_row):
    """The texts of a sheet that play the part of headers: every row down
    to the header row (title rows, group labels of a two-row header, the
    header itself) and every one-cell row below it (section titles,
    notes). header_row None (a refusal): every text of the sheet."""
    out = []
    for i, r in enumerate(rows, 1):
        filled = [v for v in r if v is not None and
                  not (isinstance(v, str) and not v.strip())]
        if header_row is None or i <= header_row or len(filled) == 1:
            out += [v for v in filled if isinstance(v, str)]
    return out


def shown_groups(ctx, sheet, header_row=None):
    """Hold-out groups of the header texts the sheet really shows,
    compared after NFKC and case folding (sections 11, 10.8 check 6)."""
    out = set()
    for text in header_area_texts(sheet.rows, header_row):
        out |= held_groups_of_text(ctx.folder, text)
    return out


def task_shown_groups(task):
    """shown_groups() of a finished task dict (check 6 of 10.8)."""
    m = re.match(r"target\('[a-z_]+'\)\nheader\((\d+)\)", task["program"])
    header_row = int(m.group(1)) if m else None
    rows = [[c["v"] if c and c["t"] == "s" else (None if c is None else 0)
             for c in r] for r in task["sheet"]["rows"]]
    folder = D.locale(task["locale"])["data"]
    out = set()
    for text in header_area_texts(rows, header_row):
        out |= held_groups_of_text(folder, text)
    return out


def held_families(split, hold):
    group = {"dev_heldout": "D", "test_heldout": "T"}.get(split)
    if not group:
        return []
    return [f for fid, f in sorted(families().items())
            if group_of_family(fid, hold) == group]


def _attempt(rng, split, index, hold, folders, kind, coin):
    code = choose_locale(rng, split, index, folders)
    if code is None:
        return None, "no_locale"
    held = held_families(split, hold)
    turn = None
    if held and index % 3 == 0:
        # a third of a hold-out split: its held-out families in turn
        turn = held[(index // 3) % len(held)]
        kind = turn.TARGET if turn.TARGET != "refusals" else turn.REASON
    if kind in REFUSALS:
        fams = [f for fid, f in families().items()
                if f.TARGET == "refusals" and getattr(f, "REASON", "") ==
                kind and group_of_family(fid, hold) in (
                    {"train", "D"} if split == "dev_heldout" else
                    {"train", "T"} if split == "test_heldout" else
                    {"train"})]
        if not fams:
            return None, "no_refusal_family"
        family = turn or rng.choice(fams)
        if hasattr(family, "pick_target"):
            target_for_activity = family.pick_target(rng)
        else:
            target_for_activity = getattr(family, "LOOKS_LIKE", None) or \
                rng.choice(config.TARGETS)
    else:
        family = turn or choose_family(rng, split, kind, hold,
                                       xlsx=coin < XLSX_SHARE)
        if family is None:
            return None, "no_family"
        target_for_activity = kind
    loc = D.locale(code)
    act = choose_activity(rng, split, loc["data"], target_for_activity)
    if act is None:
        return None, "no_activity"
    typed = coin < XLSX_SHARE and not getattr(family, "CSV_ONLY", False)
    if getattr(family, "XLSX_ONLY", False):
        typed = True
    fam_group = group_of_family(family.ID, hold)
    act_group = group_of_activity(act)
    forced = None
    if split == "dev_heldout" and fam_group != "D" and act_group != "D":
        forced = "header"
    if split == "test_heldout" and fam_group != "T" and act_group != "T":
        forced = "header"
    ctx = Ctx(rng, split, code, act, typed, hold, forced)
    plan = {"target": target_for_activity, "family": family.ID,
            "n": rows_count(rng, target_for_activity),
            "traps": draw_traps(rng, target_for_activity, split),
            "extra": rng.choice([0, 0, 0, 1, 1, 2, 3, 4, 5]),
            "split": split}
    built = family.build(ctx, plan)
    if built is None:
        return None, "family_declined"
    if isinstance(built, dict):             # a refusal
        return finish_refusal(ctx, family, plan, built, split, index, code,
                              act, typed)
    table = built
    answer = table.target
    targets = offered_targets(rng, answer)
    name = sheet_name_ok(table.sheet_name or ctx.sheet_name(answer))
    done, why = K.finish(table, ctx.fmt, rng, name, code, targets)
    if done is None:
        return None, why
    # the hold-out rule of the split (section 11)
    groups = shown_groups(ctx, done["sheet"], done["header_row"])
    if fam_group != "train":
        groups.add(fam_group)
    if act_group != "train":
        groups.add(act_group)
    if split == "dev_heldout" and ("D" not in groups or "T" in groups):
        return None, "holdout_rule"
    if split == "test_heldout" and ("T" not in groups or "D" in groups):
        return None, "holdout_rule"
    if split not in ("dev_heldout", "test_heldout") and groups:
        return None, "holdout_rule"
    task = task_dict(split, index, ctx, family, table, done["sheet"],
                     done["program"], table.truth, targets, answer,
                     sorted(table.traps), typed, code, act, groups,
                     table.n)
    # every lookup key must be visible in the VALUES line (section 10.1)
    values = "\n".join(line for line in task["preview"].splitlines()
                       if line.startswith("VALUES "))
    for key in lookup_keys(task["program"]):
        if key not in values:
            return None, "lookup_not_in_values"
    return task, None


def lookup_keys(program):
    import ast
    keys = []
    for node in ast.walk(ast.parse(program)):
        if isinstance(node, ast.Call) and \
                getattr(node.func, "id", "") == "lookup" and \
                len(node.args) == 2 and isinstance(node.args[1], ast.Dict):
            keys += [k.value for k in node.args[1].keys]
    return keys


def digits_in_refusal(ctx, sheet):
    """Section 10.5 on a sheet the program refuses (a pivot, a matrix, a
    budget...): each column's text cells take Arabic-Indic or full-width
    digits at the locale's rate, one draw per column. Nothing reads them,
    so no truth can move. (A refusal built from a real table - not
    offered, missing a field, too wide - got its digits from sheetkit's
    digit pass: built["digits"].)"""
    if not (ctx.loc.get("digits") or {}):
        return
    rows = sheet.rows = [list(r) for r in sheet.rows]
    width = max((len(r) for r in rows), default=0)
    for c in range(width):
        cells = [r[c] for r in rows if c < len(r) and isinstance(r[c], str)]
        if not any(K.ASCII_DIGIT.search(v) for v in cells):
            continue
        mode = K.digit_draw(ctx.loc, ctx.rng)
        if not mode:
            continue
        for r in rows:
            if c < len(r) and isinstance(r[c], str):
                r[c] = K._convert(ctx.fmt, mode, r[c])


def finish_refusal(ctx, family, plan, built, split, index, code, act,
                   typed):
    """built: {sheet, program, targets, traps, answer}."""
    if not built.get("digits"):
        digits_in_refusal(ctx, built["sheet"])
    small, _ = sheets.compact(built["sheet"])
    groups = shown_groups(ctx, small)
    fg = group_of_family(family.ID, holdout())
    if fg != "train":
        groups.add(fg)
    if group_of_activity(act) != "train":
        groups.add(group_of_activity(act))
    if split == "dev_heldout" and ("D" not in groups or "T" in groups):
        return None, "holdout_rule"
    if split == "test_heldout" and ("T" not in groups or "D" in groups):
        return None, "holdout_rule"
    if split not in ("dev_heldout", "test_heldout") and groups:
        return None, "holdout_rule"

    return task_dict(split, index, ctx, family, None, small,
                     ts.canonical(built["program"]), [], built["targets"],
                     built["answer"], sorted(built.get("traps") or []),
                     typed, code, act, groups, len(small.rows)), None


# ---------------------------------------------------------------------
#  the task record (section 10.7)
# ---------------------------------------------------------------------
def tag(v):
    """A cell value -> its tagged JSON form."""
    if v is None:
        return None
    if isinstance(v, bool):
        return {"t": "b", "v": v}
    if isinstance(v, int):
        return {"t": "i", "v": v}
    if isinstance(v, float):
        return {"t": "f", "v": v}
    if isinstance(v, datetime.datetime):
        return {"t": "d", "v": v.isoformat()}
    if isinstance(v, datetime.date):
        return {"t": "D", "v": v.isoformat()}
    if isinstance(v, datetime.time):
        return {"t": "tm", "v": v.isoformat()}
    if isinstance(v, datetime.timedelta):
        return {"t": "td", "v": v.total_seconds()}
    return {"t": "s", "v": str(v)}


def untag(c):
    if c is None:
        return None
    t, v = c["t"], c["v"]
    if t in ("s", "i", "f", "b"):
        return v
    if t == "d":
        return datetime.datetime.fromisoformat(v)
    if t == "D":
        return datetime.date.fromisoformat(v)
    if t == "tm":
        return datetime.time.fromisoformat(v)
    if t == "td":
        return datetime.timedelta(seconds=v)
    return v


def sheet_from_task(task):
    s = task["sheet"]
    rows = [[untag(c) for c in r] for r in s["rows"]]
    return sheets.Sheet(s["name"], rows, s.get("formats"))


def task_dict(split, index, ctx, family, table, sheet, program, truth,
              targets, answer, traps, typed, code, act, groups=(),
              n_rows=0):
    preview = sheets.preview(sheet, targets, code)
    return {
        "id": "%s-%06d" % (split, index), "split": split,
        "lang": ctx.lang, "locale": code, "activity": act["n"],
        "family": family.ID, "traps": traps, "targets": targets,
        "answer": answer, "format": "xlsx" if typed else "csv",
        "sheet": {"name": sheet.name,
                  "rows": [[tag(v) for v in r] for r in sheet.rows],
                  "formats": sheet.formats},
        "preview": preview, "program": program,
        "truth": K.clean_rows(truth),
        # not in section 10.7, used by the checks of section 10.8
        "holdout": sorted(groups), "n_rows": n_rows,
    }
