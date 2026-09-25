"""
gen/tasks.py - plan and make ONE task (split, index): a sheet, its
preview, its program and its true rows.

The random generator of a task is seeded from (split, index), so every
task can be made again exactly (section 10.1).
"""
import datetime
import hashlib
import importlib
import math
import pathlib
import random

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
REFUSALS = ("no_matching_target", "missing_required", "not_a_table",
            "too_wide")

# section 10.4: how often each trap is DRAWN for a task of that target
# (a family may not be able to show it, so these sit above the minimum
# rates the checks require)
TRAPS = {
    "products": {"T1": 0.36, "T2": 0.25, "T3": 0.13, "T4": 0.46,
                 "T5": 0.52, "T6": 0.12, "T13": 0.33, "T14": 0.22},
    "services": {"T2": 0.25, "T4": 0.46, "T5": 0.52, "T6": 0.12,
                 "T13": 0.33, "T14": 0.22},
    "opening_hours": {"T5": 0.52, "T14": 0.22},
    "staff": {"T4": 0.46, "T5": 0.52, "T6": 0.12, "T14": 0.22},
    "clients": {"T4": 0.46, "T5": 0.52, "T6": 0.12, "T14": 0.22},
    "bookings": {"T4": 0.30, "T5": 0.52, "T6": 0.12, "T12": 0.72,
                 "T13": 0.33, "T14": 0.22},
    "invoice_ledger": {"T4": 0.46, "T5": 0.52, "T6": 0.12, "T12": 0.72,
                       "T13": 0.33, "T14": 0.22},
}
# rows: log-uniform 3-400, then capped by what the table can hold
MAX_ROWS = {"products": 400, "services": 60, "opening_hours": 7,
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


def holdout():
    path = HERE / "holdout.json"
    return D.read_json(path) or {}


def group_of_family(fid, hold):
    return (hold.get("families") or {}).get(fid, "train")


def group_of_activity(act):
    return act.get("holdout") or "train"


# ---------------------------------------------------------------------
#  planning
# ---------------------------------------------------------------------
def seed_of(split, index):
    digest = hashlib.sha1(("%s-%d" % (split, index)).encode()).hexdigest()
    return int(digest[:16], 16)


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


def choose_family(rng, split, target, hold):
    allowed = {"train", "D"} if split == "dev_heldout" else \
        {"train", "T"} if split == "test_heldout" else {"train"}
    fams = [f for fid, f in families().items()
            if f.TARGET == target and group_of_family(fid, hold) in allowed]
    if not fams:
        return None
    weights = [(f, getattr(f, "WEIGHT", 1.0)) for f in fams]
    return weighted(rng, weights)


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
def make_task(split, index, folders=None, tries=12):
    """-> (task dict, None) or (None, reason)."""
    hold = holdout()
    folders = folders or D.folders_ready()
    reason = "no_try"
    for attempt in range(tries):
        rng = random.Random(seed_of(split, index) + 7919 * attempt)
        task, reason = _attempt(rng, split, index, hold, folders)
        if task:
            return task, None
    return None, reason


def _attempt(rng, split, index, hold, folders):
    code = choose_locale(rng, split, index, folders)
    if code is None:
        return None, "no_locale"
    kind = weighted(rng, SHARES)
    if kind in REFUSALS:
        fams = [f for fid, f in families().items()
                if f.TARGET == "refusals" and getattr(f, "REASON", "") ==
                kind and group_of_family(fid, hold) in (
                    {"train", "D"} if split == "dev_heldout" else
                    {"train", "T"} if split == "test_heldout" else
                    {"train"})]
        if not fams:
            return None, "no_refusal_family"
        family = rng.choice(fams)
        target_for_activity = getattr(family, "LOOKS_LIKE", None) or \
            rng.choice(config.TARGETS)
    else:
        family = choose_family(rng, split, kind, hold)
        if family is None:
            return None, "no_family"
        target_for_activity = kind
    loc = D.locale(code)
    act = choose_activity(rng, split, loc["data"], target_for_activity)
    if act is None:
        return None, "no_activity"
    typed = rng.random() < 0.7 and not getattr(family, "CSV_ONLY", False)
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
    name = table.sheet_name or ctx.sheet_name(answer)
    done, why = K.finish(table, ctx.fmt, rng, name, code, targets)
    if done is None:
        return None, why
    # the hold-out rule of the split (section 11)
    groups = set(g for (_, _, g) in ctx.used)
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
    return task_dict(split, index, ctx, family, table, done["sheet"],
                     done["program"], table.truth, targets, answer,
                     sorted(table.traps), typed, code, act), None


def finish_refusal(ctx, family, plan, built, split, index, code, act,
                   typed):
    """built: {sheet, program, targets, traps, answer}."""
    small, _ = sheets.compact(built["sheet"])
    groups = set(g for (_, _, g) in ctx.used)
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

    class T:
        pass
    return task_dict(split, index, ctx, family, None, small,
                     ts.canonical(built["program"]), [], built["targets"],
                     built["answer"], sorted(built.get("traps") or []),
                     typed, code, act), None


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
              targets, answer, traps, typed, code, act):
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
    }
