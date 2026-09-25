"""
gen/holdout.py - draw the hold-out groups ONCE, with seed 7 (section 11),
and write gen/holdout.json.

    header variants  per language folder and field: 1 variant in D, 1 in
                     T. The T variant is MOVED from headers.json to
                     headers_test.json (nobody reads that file).
    layout families  per target: 1 family in D, 1 in T - never one that
                     is the only family showing a trap (or, for refusals,
                     the only family of a refusal reason). The T family's
                     module is MOVED to gen/layouts/test/.
    activities       fixed in Appendix J (activities_base.json).
    locales          the held-out locales go only to test_locale.

Items added later get a group from a hash of their id
(tasks.group_of_new). Run through `py gen/make.py --draw-holdout`.
"""
import json
import pathlib
import random
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gen import data as D          # noqa: E402

SEED = 7


def trap_map(tries=40):
    """{family id: set of traps it showed} - measured by building tasks
    of every family (before any hold-out exists)."""
    from gen import tasks as T
    from gen.ctx import Ctx
    out = {}
    folders = D.folders_ready()
    for fid, fam in sorted(T.families().items()):
        seen = set()
        for i in range(tries):
            rng = random.Random(SEED * 100003 + i * 7919 + len(fid))
            code = T.choose_locale(rng, "train", i, folders)
            loc = D.locale(code)
            if fam.TARGET == "refusals":
                target = fam.pick_target(rng) if hasattr(fam, "pick_target") \
                    else rng.choice(list(T.MAX_ROWS))
            else:
                target = fam.TARGET
            act = T.choose_activity(rng, "train", loc["data"], target)
            if act is None:
                continue
            typed = rng.random() < 0.7 and not getattr(fam, "CSV_ONLY",
                                                        False)
            ctx = Ctx(rng, "train", code, act, typed, {}, None)
            plan = {"target": target, "family": fid,
                    "n": T.rows_count(rng, target),
                    "traps": T.draw_traps(rng, target, "traps"),
                    "extra": rng.choice([0, 1, 2]), "split": "train"}
            try:
                built = fam.build(ctx, plan)
            except Exception:
                built = None
            if built is None:
                continue
            traps = built.get("traps") if isinstance(built, dict) \
                else built.traps
            seen |= set(traps or [])
        out[fid] = seen
    return out


def draw_families(rng, fams, traps):
    """{family id: 'D' | 'T'} - one of each per target."""
    by_target = {}
    for fid, fam in sorted(fams.items()):
        by_target.setdefault(fam.TARGET, []).append(fid)
    chosen = {}
    for target, fids in sorted(by_target.items()):
        pool = list(fids)
        if target == "refusals":
            # keep every refusal reason in training: hold out only among
            # reasons that have several families
            reasons = {}
            for f in fids:
                reasons.setdefault(fams[f].REASON, []).append(f)
            pool = [f for f in fids if len(reasons[fams[f].REASON]) >= 3]
        rng.shuffle(pool)
        held = []
        for fid in pool:
            if len(held) == 2:
                break
            rest = [f for f in fids if f not in held and f != fid]
            # every trap shown by this target's families is still shown
            # by a training family
            needed = set().union(*(traps.get(f, set()) for f in fids))
            kept = set().union(*(traps.get(f, set()) for f in rest)) \
                if rest else set()
            if needed - kept:
                continue
            held.append(fid)
        if len(held) < 2:
            raise SystemExit("cannot hold out 2 families of %s" % target)
        chosen[held[0]] = "D"
        chosen[held[1]] = "T"
    return chosen


def draw(force=False):
    path = HERE / "holdout.json"
    if path.exists() and not force:
        raise SystemExit("gen/holdout.json exists: the draw is done once")
    from gen import tasks as T
    rng = random.Random(SEED)
    fams = T.families()
    traps = trap_map()
    chosen = draw_families(rng, fams, traps)
    # header variants: per folder and field
    headers = {}
    moved = 0
    for folder in D.FOLDERS:
        hpath = D.DATA / folder / "headers.json"
        data = json.loads(hpath.read_text(encoding="utf-8"))
        fields = data.get("fields") or {}
        test = {}
        headers[folder] = {}
        others = {}
        for key, variants in fields.items():
            for v in variants:
                others.setdefault(v.casefold(), set()).add(key)
        for key in sorted(fields):
            variants = list(fields[key])
            if len(variants) < 4:
                continue
            # prefer variants no other field of this language uses, so a
            # held-out header is really unseen
            own = [v for v in variants if others[v.casefold()] == {key}]
            d, t = rng.sample(own if len(own) >= 2 else variants, 2)
            headers[folder][key] = {"D": d, "known": [v for v in variants
                                                      if v != t]}
            fields[key] = [v for v in variants if v != t]
            test[key] = [t]
            moved += 1
        hpath.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        tpath = D.DATA / folder / "headers_test.json"
        tpath.write_text(json.dumps({"fields": test}, ensure_ascii=False,
                                    indent=1), encoding="utf-8")
    # T families go to gen/layouts/test/
    test_dir = HERE / "layouts" / "test"
    test_dir.mkdir(exist_ok=True)
    for fid, group in chosen.items():
        if group != "T":
            continue
        module = fams[fid]
        src = pathlib.Path(module.__file__)
        shutil.move(str(src), str(test_dir / src.name))
    out = {"seed": SEED,
           "families": dict((f, g) for f, g in sorted(chosen.items())
                            if g == "D"),
           "known_families": sorted(f for f in fams if chosen.get(f) != "T"),
           "headers": headers,
           "note": "T items live in headers_test.json and gen/layouts/test/"
                   " - never read them."}
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    T.holdout.cache_clear()
    n_t = sum(1 for g in chosen.values() if g == "T")
    return {"families_D": out["families"], "families_T": n_t,
            "header_variants_moved": moved}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(draw(force="--force" in sys.argv))
