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
import re

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


# ---------------------------------------------------------------------
#  moving the T items out of the way (done once, right after the draw)
# ---------------------------------------------------------------------
TEST_DIR = HERE / "layouts" / "test"


def move_test_items(result, registry, log=print):
    """Moves every T item where section 10.2 says it lives:
    * T sentence templates -> gen/data/<key>/sentences_test.json
    * T layouts (code)     -> gen/layouts/test/<module>.py
    * T registration families -> gen/layouts/test/registration_test.json
    The generator still finds them (data.sentences() merges the test
    file; gen/layouts/__init__ imports the test package), but nobody
    needs to open those files again."""
    import ast
    data_dir = HERE / "data"
    # ---- sentence templates
    moved_templates = 0
    for key, groups in sorted(result["templates"].items()):
        path = data_dir / key / "sentences.json"
        sent = json.loads(path.read_text(encoding="utf-8"))
        test = {}
        for cat in CATEGORIES:
            items = sent.get(cat) or []
            keep = [t for t in items if groups.get(t["id"]) != "T"]
            gone = [t for t in items if groups.get(t["id"]) == "T"]
            if gone:
                sent[cat] = keep
                test[cat] = gone
                moved_templates += len(gone)
        path.write_text(json.dumps(sent, ensure_ascii=False, indent=2) +
                        "\n", encoding="utf-8")
        (data_dir / key / "sentences_test.json").write_text(
            json.dumps(test, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    # ---- layouts written as code
    TEST_DIR.mkdir(exist_ok=True)
    t_ids = {lid for lid, g in result["layouts"].items() if g == "T"}
    by_module = {}
    for lid in sorted(t_ids):
        info = registry[lid]
        if info["doc_type"] == "registration":
            continue
        module = info["fn"].__module__.rsplit(".", 1)[-1]
        by_module.setdefault(module, []).append(lid)
    moved_layouts = 0
    for module, lids in sorted(by_module.items()):
        path = HERE / "layouts" / (module + ".py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        cut = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(
                        dec.func, "id", None) == "layout" and dec.args and \
                        getattr(dec.args[0], "value", None) in lids:
                    first = min(d.lineno for d in node.decorator_list)
                    cut.append((first, node.end_lineno))
        lines = source.splitlines(keepends=True)
        pieces = []
        for first, last in sorted(cut, reverse=True):
            pieces.insert(0, "".join(lines[first - 1:last]))
            del lines[first - 1:last]
        kept = re.sub(r"\n{3,}", "\n\n\n", "".join(lines)).rstrip() + "\n"
        path.write_text(kept, encoding="utf-8")
        header = ('"""\nHeld-out TEST layouts from %s.py (hold-out set T, '
                  'section 11).\nMoved here by the hold-out draw; they are '
                  'used only in test_heldout.\n"""\nfrom gen.layouts import '
                  '%s as _base\n\nglobals().update({k: v for k, v in '
                  'vars(_base).items()\n                 if not '
                  'k.startswith("__")})\n' % (module, module))
        body = "\n\n".join(p.rstrip() + "\n" for p in pieces)
        (TEST_DIR / (module + ".py")).write_text(
            header + "\n\n" + body, encoding="utf-8")
        moved_layouts += len(pieces)
    # ---- registration families (data)
    reg_path = data_dir / "registration.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    families = reg.get("families", {})
    test_fams = {}
    for lid in sorted(t_ids):
        if registry[lid]["doc_type"] == "registration":
            fid = lid.split(".", 1)[1]
            if fid in families:
                test_fams[fid] = families.pop(fid)
    reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    (TEST_DIR / "registration_test.json").write_text(
        json.dumps({"families": test_fams}, ensure_ascii=False, indent=1) +
        "\n", encoding="utf-8")
    log("moved %d sentence templates, %d code layouts and %d registration "
        "families to their test files" % (moved_templates, moved_layouts,
                                          len(test_fams)))
