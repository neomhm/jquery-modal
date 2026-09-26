"""
config.py - every preset setting of Tulip and every path, in one place.

Nothing here needs torch, so the generator and check.py can import it on
a machine where torch is not installed yet.

The three presets (section 13 of the build instructions):
    smoke  - proves the whole pipeline runs, in minutes
    pilot  - a CPU run for error analysis; a usable test model
    full   - the real model (needs a GPU with 8 GB or more)
"""
import hashlib
import json
import os
import pathlib
import sys
from datetime import date

VERSION = "1.0.0"              # version of the model file (tulip-1.0.0.pt)
GENERATOR_VERSION = "1.1.0"    # bump when the synthetic data changes on purpose

HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------
#  vendor/: the small pure-Python packages Tulip needs that the MEGA9
#  /train venv does not have (openpyxl + et_xmlfile, phonenumbers,
#  hijridate), shipped as their original PyPI wheel files (sha256 in
#  DECISIONS.md, "Offline build"). Python imports straight from a wheel
#  on sys.path, so nothing is installed and no network is needed: the
#  /train run unit has none (PrivateNetwork=yes). They come FIRST on the
#  path, so every machine generates with the same versions, and
#  PYTHONPATH carries them to the processes the build starts.
# ---------------------------------------------------------------------
VENDOR = HERE / "vendor"


def use_vendor():
    """Puts every vendor/*.whl on sys.path (and on PYTHONPATH for child
    processes). -> the list of wheel files (empty without vendor/)."""
    wheels = sorted(str(p) for p in VENDOR.glob("*.whl")) \
        if VENDOR.is_dir() else []
    for wheel in reversed(wheels):
        if wheel not in sys.path:
            sys.path.insert(0, wheel)
    if wheels:
        old = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
               if p and p not in wheels]
        os.environ["PYTHONPATH"] = os.pathsep.join(wheels + old)
    return wheels


VENDORED = use_vendor()

# ---------------------------------------------------------------------
#  How much of the machine one build may take. NEVER one process per
#  core: on MEGA9 (32 threads, 31 GB) one process per core took the
#  whole machine and the kernel's out-of-memory killer took a training
#  run with it (2026-09-26). At most MAX_WORKERS processes for the
#  generator and the evaluation, and at most MAX_THREADS torch threads
#  per process; TULIP_WORKERS / TULIP_THREADS may lower them, never
#  raise them. Measured under the /train unit's 12 GB cap: see
#  DECISIONS.md, "Offline build".
# ---------------------------------------------------------------------
MAX_WORKERS = 4
MAX_THREADS = 4


def _env_count(name, ceiling):
    try:
        wanted = int(os.environ.get(name, "") or ceiling)
    except ValueError:
        wanted = ceiling
    return max(1, min(ceiling, wanted, os.cpu_count() or 1))


def workers():
    """Processes for the generator and the evaluation (1..MAX_WORKERS)."""
    return _env_count("TULIP_WORKERS", MAX_WORKERS)


def threads():
    """torch threads for one process (1..MAX_THREADS)."""
    return _env_count("TULIP_THREADS", MAX_THREADS)

# All dates of the synthetic world are relative to this day. The
# generator never looks at the real clock (section 10.1).
REFERENCE_DATE = date(2026, 6, 30)

# The ten languages, in this FIXED order (section 3)
LANGS = ["ar", "zh", "en", "fr", "ru", "es", "it", "hi", "ja", "ko"]

# The seven targets, in the order of section 6
TARGETS = ["products", "services", "opening_hours", "staff", "clients",
           "bookings", "invoice_ledger"]

# The data splits, in the order they are generated (section 11)
SPLITS = ["train", "val", "dev_heldout", "test_seen", "test_heldout",
          "test_locale", "traps"]
EVAL_SPLITS = ["val", "dev_heldout", "test_seen", "test_heldout",
               "test_locale", "traps"]
DEV_SPLITS = ["val", "dev_heldout"]          # the only ones ever read

# The candidate loop of section 7.2 (also stored in the model file)
SAMPLING = {"n_sampled": 7, "temperature": 0.7, "top_p": 0.95,
            "trial_rows": 500, "max_new_tokens": 600}

# Model selection (section 14): greedy execution match on a fixed
# sample of this many dev_heldout tasks
SELECTION_SAMPLE = 1000
MICRO_TOKENS = 16000          # a micro-batch never holds more tokens

# ---------------------------------------------------------------------
#  Presets (sections 11, 13 and 14). Times are in minutes.
# ---------------------------------------------------------------------
PRESETS = {
    # tiny: a plumbing rehearsal in minutes on a CPU (the smoke model and
    # evaluation sizes, 40 training steps). It proves the stages, the
    # files and the progress lines, not the model.
    "tiny": {
        "vocab_size": 4000, "d_model": 128, "n_layer": 3, "n_head": 4,
        "ffn_hidden": 352, "max_len": 2048, "dropout": 0.0,
        # 3,000 train tasks, not 1,000: the trap-rate self-checks are
        # sampling noise at 1,000 (T2 19% / T4 39% measured on a correct
        # generator, 2026-09-27)
        "tasks": {"train": 3000, "val": 50, "dev_heldout": 50,
                  "test_seen": 50, "test_heldout": 50, "test_locale": 20,
                  "traps": 30},
        "train": {"steps": 40, "epochs": None, "minutes": None,
                  "lr": 2e-3, "tokens_per_batch": 8000, "eval": "end"},
    },
    "smoke": {
        "vocab_size": 4000, "d_model": 128, "n_layer": 3, "n_head": 4,
        "ffn_hidden": 352, "max_len": 2048, "dropout": 0.0,
        "tasks": {"train": 1000, "val": 50, "dev_heldout": 50,
                  "test_seen": 50, "test_heldout": 50, "test_locale": 20,
                  "traps": 30},
        "train": {"steps": 1200, "epochs": None, "minutes": None,
                  "lr": 2e-3, "tokens_per_batch": 8000, "eval": "end"},
    },
    "pilot": {
        # dropout 0.0, not 0.1: see DECISIONS.md (on a CPU, dropout makes
        # PyTorch use its slow attention; one epoch never repeats data)
        "vocab_size": 16000, "d_model": 256, "n_layer": 6, "n_head": 4,
        "ffn_hidden": 704, "max_len": 4096, "dropout": 0.0,
        # train 60,000 = 2x, improvement round 1 (DECISIONS.md)
        "tasks": {"train": 60000, "val": 500, "dev_heldout": 500,
                  "test_seen": 500, "test_heldout": 500, "test_locale": 200,
                  "traps": 300},
        "train": {"steps": None, "epochs": 1, "minutes": 90,
                  "lr": 1e-3, "tokens_per_batch": 16000,
                  "eval": "every_15_min"},
    },
    "full": {
        "vocab_size": 24000, "d_model": 512, "n_layer": 8, "n_head": 8,
        "ffn_hidden": 1408, "max_len": 4096, "dropout": 0.1,
        "tasks": {"train": 400000, "val": 4000, "dev_heldout": 4000,
                  "test_seen": 4000, "test_heldout": 4000,
                  "test_locale": 2000, "traps": 3000},
        "train": {"steps": None, "epochs": 3, "minutes": 360,
                  "lr": 6e-4, "tokens_per_batch": 64000,
                  "eval": "quarter_epoch"},
    },
}

# The model id written into documents.db is the model file's stem
MODEL_FILES = {"full": "tulip-%s.pt" % VERSION,
               "pilot": "tulip-pilot.pt",
               "smoke": "tulip-smoke.pt",
               "tiny": "tulip-tiny.pt"}


def data_dir(preset):
    return HERE / "data" / preset


def runs_dir(preset):
    return HERE / "runs" / preset


def work_dir(preset):
    """Bulky intermediate files (packed token arrays, the resumable
    checkpoint, the best weights before export). A HIDDEN folder: the
    /train page sends back what a run made by file kind, and skips hidden
    folders -- without this a full run would send back gigabytes of .npz
    and three copies of the weights."""
    return runs_dir(preset) / ".work"


def preset_hash(preset, *extra):
    """A short fingerprint of a preset's settings (plus anything else a
    stage depends on). A stage is re-run when its fingerprint changes."""
    blob = json.dumps([PRESETS[preset], VERSION, GENERATOR_VERSION] +
                      list(extra), sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


# The libraries' own thread pools follow the same ceiling: the tokenizer
# library (Rayon) and OpenMP otherwise start one thread per core. Set
# before they are imported; a value the caller already set is kept.
for _name in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, str(threads()))
