"""
holdout.py - which layouts, sentence templates and activities are held
out for testing (section 11).

The hold-out groups are drawn ONCE, with seed 7, by
    py gen/make.py --draw-holdout
and saved in gen/holdout.json:
    D = held out for dev_heldout (model selection, calibration)
    T = held out for test_heldout (the final gate)
Everything else is "train". Items added later (improvement rounds) get
their group from a hash of their id: 80 % train, 10 % D, 10 % T.
"""
import functools
import hashlib
import json
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
FILE = HERE / "holdout.json"

# sentence categories that take part in the draw (per language)
CATEGORIES = ["activity", "founded", "staff", "revenue", "services_intro",
              "clients", "hours", "certifications", "location", "capital",
              "legal_form", "traps", "filler"]
ID_PREFIX = {"traps": "trap"}


@functools.lru_cache(maxsize=None)
def load():
    if FILE.exists():
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def reset_cache():
    load.cache_clear()


def hash_group(ident):
    h = int(hashlib.sha1(ident.encode("utf-8")).hexdigest(), 16) % 10
    return "D" if h == 8 else "T" if h == 9 else "train"


def group_of(key, tid):
    """Group of a sentence template of data folder `key`."""
    data = load()
    if not data or not tid:
        return "train"
    g = data.get("templates", {}).get(key, {}).get(tid)
    if g:
        return g
    cat = tid.split(".")[0]
    if cat in CATEGORIES or cat in ID_PREFIX.values():
        return hash_group(key + ":" + tid)         # added after the draw
    return "train"


def layout_group(lid):
    data = load()
    if not data:
        return "train"
    g = data.get("layouts", {}).get(lid)
    return g if g else hash_group(lid)


def activity_group(act):
    return act.get("holdout") or "train"


def sha256():
    if not FILE.exists():
        return None
    return hashlib.sha256(FILE.read_bytes()).hexdigest()


# ---------------------------------------------------------------------
#  the draw
# ---------------------------------------------------------------------
def draw(registry, sentences_by_key):
    """registry: {layout_id: info}; sentences_by_key: {key: sentences
    dict (sentences.json content)}. Returns the holdout dict."""
    rng = random.Random(7)
    out = {"seed": 7, "layouts": {}, "templates": {}, "activities": {}}
    # ---- layouts, grouped by document type
    by_type = {}
    for lid, info in sorted(registry.items()):
        if info.get("heldout_locale"):
            out["layouts"][lid] = "locale"      # used only in test_locale
            continue
        by_type.setdefault(info["doc_type"], []).append(lid)
    for doc_type, ids in sorted(by_type.items()):
        n = len(ids)
        k = max(2, int(round(0.2 * n)))
        if doc_type == "registration":
            chosen = _draw_registration(rng, registry, ids, k)
        else:
            chosen = rng.sample(ids, k)
        n_d = k // 2
        for i, lid in enumerate(chosen):
            out["layouts"][lid] = "D" if i < n_d else "T"
        for lid in ids:
            out["layouts"].setdefault(lid, "train")
    # ---- sentence templates, per language folder and category
    for key in sorted(sentences_by_key):
        sent = sentences_by_key[key]
        groups = {}
        for cat in CATEGORIES:
            items = sent.get(cat) or []
            if cat == "traps":
                pools = {}
                for t in items:
                    pools.setdefault(t["trap"], []).append(t["id"])
                pool_list = [sorted(v) for _, v in sorted(pools.items())]
            else:
                pool_list = [sorted(t["id"] for t in items)]
            for ids in pool_list:
                k = int(round(0.2 * len(ids)))
                chosen = rng.sample(ids, k) if k else []
                n_d = k // 2
                for i, tid in enumerate(chosen):
                    groups[tid] = "D" if i < n_d else "T"
                for tid in ids:
                    groups.setdefault(tid, "train")
        out["templates"][key] = groups
    return out


def _draw_registration(rng, registry, ids, k):
    """Registration layouts are held out only from families with >= 2
    layouts, so that every country keeps one in training."""
    families = {}
    for lid in ids:
        families.setdefault(registry[lid]["family"], []).append(lid)
    eligible = [lid for fam, lids in families.items() if len(lids) >= 2
                for lid in lids]
    chosen = []
    left = {fam: len(lids) for fam, lids in families.items()}
    for lid in rng.sample(sorted(eligible), len(eligible)):
        fam = registry[lid]["family"]
        if left[fam] > 1 and len(chosen) < k:
            chosen.append(lid)
            left[fam] -= 1
    return chosen
