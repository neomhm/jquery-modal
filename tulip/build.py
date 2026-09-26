"""
build.py - the one command that builds Tulip (section 20).

    py build.py                  full with a GPU, pilot without
    py build.py pilot
    py build.py pilot --from train
    py build.py pilot --dev-only
    py build.py full --force     (full on a CPU: very slow)

Stages, in order:
    check      checks the machine; installs missing packages (never torch)
    generate   gen/make.py for the preset's splits, then its self-checks
    tokenizer  trains the tokenizer; length report; round-trip check
    pack       token arrays with labels
    train      section 14 -> runs/<preset>/best.pt
    evaluate   section 16 (--dev-only: val and dev_heldout only)
    export     the model file next to this script: tulip-1.0.0.pt (full),
               tulip-pilot.pt or tulip-smoke.pt
    report     writes this preset's part of REPORT.md

Each stage writes runs/<preset>/<stage>.done (settings fingerprint, time
taken, key numbers). A stage whose .done matches the current settings is
skipped. --from STAGE runs that stage and every stage after it again.
If a stage fails, the build stops and says which one:
    Stopped: 'train' failed. Fix that before going on.
Everything is also written to runs/<preset>/build.log.
"""
import argparse
import datetime
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import time
import traceback

import config

HERE = pathlib.Path(__file__).resolve().parent
STAGES = ["check", "generate", "tokenizer", "pack", "train", "evaluate",
          "export", "report"]
PIP_PACKAGES = {"tokenizers": "tokenizers>=0.20", "openpyxl": "openpyxl>=3.1",
                "phonenumbers": "phonenumbers", "numpy": "numpy",
                "hijridate": "hijridate"}


class Log:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, *parts):
        line = " ".join(str(p) for p in parts)
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        print("[%s] %s" % (stamp, line), flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (stamp, line))


# =====================================================================
#  stages
# =====================================================================
def stage_check(preset, args, log):
    """check.py, then install the packages that are missing (never torch:
    MEGA9 has a ROCm build and the desktop a CUDA build that must not be
    replaced)."""
    import check
    env = check.collect()
    missing = [p for p in env.get("missing_required", []) +
               env.get("missing_optional", []) if p in PIP_PACKAGES]
    for name in missing:
        log("installing %s ..." % name)
        cmd = [sys.executable, "-m", "pip", "install", PIP_PACKAGES[name]]
        done = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if done.returncode != 0 and "externally-managed" in (
                done.stderr or ""):
            done = subprocess.run(cmd + ["--break-system-packages"],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        log("  %s: %s" % (name, "ok" if done.returncode == 0 else
                          "FAILED (%s)" % (done.stderr or "")[-200:]))
    if missing:
        importlib.invalidate_caches()
        env = check.collect()
    check.show(env)
    out = HERE / "runs" / "env.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    if not env.get("torch_ok"):
        raise RuntimeError("torch >= 2.4 is required and build.py never "
                           "installs it: py -m pip install torch")
    still = [p for p in env.get("missing_required", []) if p != "torch"]
    if still:
        raise RuntimeError("missing packages: %s" % ", ".join(still))
    if preset == "full" and not env.get("gpu") and not args.force:
        raise RuntimeError("the full preset needs a GPU with 8 GB or more; "
                           "use 'py build.py pilot', or --force to run it "
                           "on the CPU anyway (days)")
    for w in env.get("warnings", []):
        log("WARNING: %s" % w)
    return {"backend": env.get("backend"), "gpu": env.get("device_name"),
            "torch": env.get("torch")}


def stage_generate(preset, args, log):
    from gen import checks, make
    make.make(preset, log=log)
    report = checks.run(preset)
    text = checks.format_report(report)
    for line in text.splitlines():
        log(line)
    (config.runs_dir(preset)).mkdir(parents=True, exist_ok=True)
    (config.runs_dir(preset) / "generator_checks.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("the generator self-checks failed (section 10.8)")
    return {"splits": report["splits"]}


def stage_tokenizer(preset, args, log):
    import pack
    from gen import checks
    report = pack.train_tokenizer(preset, log)
    counts = report.pop("token_counts")
    check7 = checks.run(preset, token_counts=counts)
    c7 = [c for c in check7["checks"] if c["check"].startswith("7")][0]
    log("%s: %s" % (c7["check"], c7["detail"]))
    if not c7["ok"]:
        raise RuntimeError("too many tasks over 4,096 tokens")
    return {"vocab": report["vocab_size"],
            "over_limit": report["over_limit"],
            "round_trip_failed": report["round_trip"]["failed"]}


def stage_pack(preset, args, log):
    import pack
    return pack.pack(preset, log)


def stage_train(preset, args, log):
    import train
    r = train.run(preset, log)
    return dict((k, r[k]) for k in ("steps", "epochs", "train_minutes",
                                    "chosen_step", "dev_sample_exec_match",
                                    "parameters"))


def stage_evaluate(preset, args, log):
    import evaluate
    r = evaluate.run(preset, dev_only=args.dev_only, log=log)
    return key_numbers(r)


def stage_export(preset, args, log):
    """The self-contained model file: weights, tokenizer and meta."""
    import torch
    import helpers as H
    import model as M
    import tulipscript as ts
    out = config.runs_dir(preset)
    net, tokenizer_json, meta = M.load(out / "best.pt")
    ev = json.loads((out / "eval.json").read_text(encoding="utf-8"))
    target = HERE / config.MODEL_FILES[preset]
    hold = (HERE / "gen" / "holdout.json").read_bytes()
    meta = dict(meta)
    meta.update({
        "version": config.VERSION, "preset": preset,
        "model_id": target.stem,
        "schemas": ts.SCHEMAS, "enums": ts.ENUMS,
        "sampling": config.SAMPLING,
        "totals": list(H.TOTALS),
        "evaluation": key_numbers(ev),
        "generator_version": config.GENERATOR_VERSION,
        "holdout_sha1": hashlib.sha1(hold).hexdigest(),
        "reference_date": config.REFERENCE_DATE.isoformat(),
        "exported": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")})
    tmp = target.with_suffix(".tmp")
    M.save(tmp, net, tokenizer_json, meta)
    tmp.replace(target)
    del torch
    log("model file: %s (%.1f MB)" % (target.name,
                                      target.stat().st_size / 1e6))
    return {"file": target.name,
            "mb": round(target.stat().st_size / 1e6, 1)}


def stage_report(preset, args, log):
    import report
    path = report.write(preset, log=log)
    return {"report": path.name}


def key_numbers(ev):
    """The few numbers stored in .done files and in the model's meta."""
    out = {"dev_only": ev.get("dev_only")}
    for split, s in ev.get("splits", {}).items():
        if s.get("tasks"):
            out[split] = {"pass1": s["pass1"], "loop": s["loop"],
                          "false_accepts": s["false_accepts"]}
    if ev.get("handwritten") and ev["handwritten"].get("loop") is not None:
        out["handwritten_loop"] = ev["handwritten"]["loop"]
    return out


STAGE_FUNCS = {name: globals()["stage_" + name] for name in STAGES}


# =====================================================================
#  bookkeeping
# =====================================================================
def fingerprint(preset, stage, args):
    """What a stage depends on: the preset's settings, the versions, and
    for 'evaluate' whether it scored everything or only the dev sets."""
    extra = [stage]
    if stage in ("evaluate", "export", "report"):
        extra.append("dev_only" if args.dev_only else "all")
    return config.preset_hash(preset, *extra)


def done_path(preset, stage):
    return config.runs_dir(preset) / ("%s.done" % stage)


def is_done(preset, stage, args):
    path = done_path(preset, stage)
    if not path.exists():
        return False
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return rec.get("hash") == fingerprint(preset, stage, args)


def mark_done(preset, stage, args, seconds, numbers):
    path = done_path(preset, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "stage": stage, "preset": preset,
        "hash": fingerprint(preset, stage, args),
        "seconds": round(seconds, 1),
        "finished": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "numbers": numbers}, indent=1, ensure_ascii=False, default=str),
        encoding="utf-8")


def default_preset():
    try:
        import torch
        return "full" if torch.cuda.is_available() else "pilot"
    except ImportError:
        return "pilot"


def main():
    ap = argparse.ArgumentParser(description="Build Tulip")
    ap.add_argument("preset", nargs="?", choices=list(config.PRESETS))
    ap.add_argument("--from", dest="start", choices=STAGES,
                    help="run this stage and every stage after it again")
    ap.add_argument("--force", action="store_true",
                    help="allow the full preset on a CPU")
    ap.add_argument("--dev-only", action="store_true",
                    help="evaluate val and dev_heldout only")
    args = ap.parse_args()
    preset = args.preset or default_preset()
    log = Log(config.runs_dir(preset) / "build.log")
    log("build %s%s%s" % (preset, " from " + args.start if args.start
                          else "", " (dev-only)" if args.dev_only else ""))
    forced = STAGES[STAGES.index(args.start):] if args.start else []
    began = time.time()
    for stage in STAGES:
        if stage not in forced and is_done(preset, stage, args):
            log("%-10s already done - skipped" % stage)
            continue
        log("%-10s ..." % stage)
        t0 = time.time()
        try:
            numbers = STAGE_FUNCS[stage](preset, args, log)
        except Exception as exc:
            log(traceback.format_exc())
            log("Stopped: '%s' failed. Fix that before going on. (%s)" % (
                stage, exc))
            return 1
        mark_done(preset, stage, args, time.time() - t0, numbers)
        log("%-10s done in %.1f min" % (stage, (time.time() - t0) / 60))
    log("build %s finished in %.1f min" % (preset,
                                           (time.time() - began) / 60))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
