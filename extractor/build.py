"""
build.py - the one command that builds the Extractor (section 21).

    py build.py                  full with a GPU, pilot without
    py build.py pilot
    py build.py pilot --from finetune
    py build.py pilot --dev-only
    py build.py full --force     (full on a CPU: very slow)

Stages, in order:
    check      checks the machine, installs missing packages (never torch)
    corpus     plain-text Wikipedia (skipped in smoke)
    generate   the synthetic data, then its self-checks
    tokenizer  trains the tokenizer; boundary rate, characters per token
    pack       token arrays for pretraining and fine-tuning
    pretrain   masked language modelling
    finetune   the labels
    calibrate  temperature and thresholds -> runs/<preset>/model_eval.pt
    evaluate   every set (--dev-only: val and dev_heldout only)
    export     extractor-<version>.pt / extractor-pilot.pt next to this file
    report     REPORT.md

Each stage writes runs/<preset>/<stage>.done (settings fingerprint, time
taken, key numbers). A stage whose .done matches the current settings is
skipped. --from STAGE runs that stage and every stage after it again.
If a stage fails, the build stops and says which one:
    Stopped: 'finetune' failed. Fix that before going on.
Everything is also written to runs/<preset>/build.log.
"""
import argparse
import datetime
import importlib
import json
import pathlib
import shutil
import subprocess
import sys
import time
import traceback

import config

HERE = pathlib.Path(__file__).resolve().parent
STAGES = ["check", "corpus", "generate", "tokenizer", "pack", "pretrain",
          "finetune", "calibrate", "evaluate", "export", "report"]
PIP_PACKAGES = {"tokenizers": "tokenizers>=0.20", "faker": "faker>=30",
                "phonenumbers": "phonenumbers", "numpy": "numpy",
                "datasets": "datasets", "hijridate": "hijridate"}


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
    """check.py, then install the packages that are missing (never
    torch: MEGA9 and the desktop have builds that must not be
    replaced)."""
    import check
    env = check.collect()
    missing = [p for p, v in env["packages"].items()
               if v in (None, "missing") and p in PIP_PACKAGES]
    for name in missing:
        log("installing %s ..." % name)
        cmd = [sys.executable, "-m", "pip", "install", PIP_PACKAGES[name]]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode != 0 and "externally-managed" in (
                done.stderr or ""):
            done = subprocess.run(cmd + ["--break-system-packages"],
                                  capture_output=True, text=True)
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
    if "torch" in env.get("missing_required", []) or not env.get(
            "torch_ok"):
        raise RuntimeError("torch >= 2.4 is required (build.py never "
                           "installs it): python -m pip install torch")
    still = [p for p in env.get("missing_required", []) if p != "torch"]
    if still:
        raise RuntimeError("missing packages: %s" % ", ".join(still))
    if preset == "full" and env.get("device") == "cpu" and not args.force:
        raise RuntimeError("the full preset needs a GPU with >= 12 GB; use "
                           "'py build.py pilot', or --force to run it on "
                           "the CPU anyway (days)")
    return {"device": env.get("device"), "wiki_reachable":
            env.get("wiki_reachable"), "torch": env.get("torch")}


def stage_corpus(preset, args, log):
    if preset == "smoke":
        out = config.corpus_dir(preset)
        out.mkdir(parents=True, exist_ok=True)
        (out / "corpus_stats.json").write_text(json.dumps(
            {"preset": preset, "wiki": "not used (smoke)",
             "languages": {}}), encoding="utf-8")
        return {"wiki": "not used (smoke)"}
    # its own process: the 'datasets' library can crash at shutdown
    done = subprocess.run([sys.executable, str(HERE / "corpus.py"), preset],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    for line in (done.stdout or "").splitlines():
        log("  " + line)
    stats_path = config.corpus_dir(preset) / "corpus_stats.json"
    if not stats_path.exists():
        raise RuntimeError("corpus.py wrote no corpus_stats.json: %s" %
                           (done.stderr or "")[-500:])
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    return {"wiki": stats["wiki"],
            "chars": {k: v.get("chars", 0) for k, v in
                      stats.get("languages", {}).items()}}


def stage_generate(preset, args, log):
    sys.path.insert(0, str(HERE))
    from gen import make, checks
    import gen.layouts                                   # noqa: F401
    stats = make.generate(preset, log=log)
    ok = checks.run(preset, log=log)
    data_stats(preset)
    if not ok:
        raise RuntimeError("gen/make.py --check failed: see "
                           "data/%s/checks.txt" % preset)
    return {"splits": stats}


def stage_tokenizer(preset, args, log):
    import pack
    rep = pack.tokenizer_stage(preset, log)
    return {"boundary_rate": rep["boundary_rate"],
            "chars_per_token": rep["chars_per_token"]}


def stage_pack(preset, args, log):
    import pack
    return pack.pack_stage(preset, log)


def stage_pretrain(preset, args, log):
    import pretrain
    state = pretrain.run(preset, log)
    return {"steps": state["step"], "minutes": round(state["seconds"] / 60,
                                                     1),
            "masked_accuracy": state.get("final_masked_accuracy"),
            "eval_loss": state.get("final_eval_loss"),
            "wiki": state.get("wiki")}


def stage_finetune(preset, args, log):
    import finetune
    return finetune.run(preset, log)


def stage_calibrate(preset, args, log):
    import calibrate
    return calibrate.run(preset, log)


def stage_evaluate(preset, args, log):
    import evaluate
    result = evaluate.run(preset, dev_only=args.dev_only, log=log)
    return key_numbers(result)


def stage_export(preset, args, log):
    import torch
    out = config.runs_dir(preset)
    blob = torch.load(out / "model_eval.pt", map_location="cpu",
                      weights_only=False)
    ev = json.loads((out / "eval.json").read_text(encoding="utf-8"))
    blob["meta"]["evaluation"] = key_numbers(ev)
    blob["meta"]["exported"] = datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds")
    target = HERE / config.MODEL_FILES[preset]
    tmp = target.with_suffix(".tmp")
    torch.save(blob, tmp)
    tmp.replace(target)
    log("exported %s (%.1f MB)" % (target.name,
                                   target.stat().st_size / 1e6))
    return {"file": target.name, "mb": round(target.stat().st_size / 1e6,
                                             1)}


def stage_report(preset, args, log):
    import report
    path = report.write(log=log)
    return {"report": str(path.name)}


def key_numbers(ev):
    """The few numbers stored in .done files and in the model's meta."""
    out = {"dev_only": ev.get("dev_only")}
    for split, s in ev.get("splits", {}).items():
        out[split] = s["strict"]["f1"]
    for split, fl in ev.get("folder_level", {}).items():
        out["folder_" + split] = fl["required_mean_accuracy"]
        out["invented_" + split] = fl["invented_values"]
    if ev.get("handwritten"):
        out["handwritten"] = ev["handwritten"]["strict"]["f1"]
    return out


def data_stats(preset):
    """Folders, documents and chunks per split and language; chunks per
    doc type, source format and label; share of empty chunks."""
    import gzip
    stats = {}
    for split in config.SPLITS:
        path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
        if not path.exists():
            continue
        s = {"folders": set(), "docs": set(), "chunks": 0, "empty": 0,
             "by_lang": {}, "by_doc_type": {}, "by_source": {},
             "by_label": {}}
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                s["folders"].add(c["folder"])
                s["docs"].add(c["doc"])
                s["chunks"] += 1
                s["empty"] += not c["spans"]
                for key, value in (("by_lang", c["lang"]),
                                   ("by_doc_type", c["doc_type"]),
                                   ("by_source", c["source"])):
                    s[key][value] = s[key].get(value, 0) + 1
                for _, _, lab in c["spans"]:
                    s["by_label"][lab] = s["by_label"].get(lab, 0) + 1
        s["folders"] = len(s["folders"])
        s["docs"] = len(s["docs"])
        stats[split] = s
    out = config.runs_dir(preset)
    out.mkdir(parents=True, exist_ok=True)
    (out / "data_stats.json").write_text(json.dumps(stats, indent=1),
                                         encoding="utf-8")
    return stats


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
    ap = argparse.ArgumentParser(description="Build the Extractor")
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
