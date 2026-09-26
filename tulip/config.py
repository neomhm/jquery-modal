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
import pathlib
from datetime import date

VERSION = "1.0.0"              # version of the model file (tulip-1.0.0.pt)
GENERATOR_VERSION = "1.0.0"    # bump when the synthetic data changes on purpose

HERE = pathlib.Path(__file__).resolve().parent

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
               "smoke": "tulip-smoke.pt"}


def data_dir(preset):
    return HERE / "data" / preset


def runs_dir(preset):
    return HERE / "runs" / preset


def preset_hash(preset, *extra):
    """A short fingerprint of a preset's settings (plus anything else a
    stage depends on). A stage is re-run when its fingerprint changes."""
    blob = json.dumps([PRESETS[preset], VERSION, GENERATOR_VERSION] +
                      list(extra), sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]
