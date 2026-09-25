"""
config.py - every fixed list and every preset setting of the Extractor,
in one place.

Nothing here needs torch, so the generator and check.py can import it on
a machine where torch is not installed yet.

The three presets (section 8 of the build instructions):
    smoke  - proves the whole pipeline runs, in minutes
    pilot  - a CPU run for error analysis; a usable test model
    full   - the real model (needs a GPU with 12 GB or more)
"""
import hashlib
import json
import pathlib
from datetime import date

VERSION = "1.0.0"              # version of the model file (extractor-1.0.0.pt)
GENERATOR_VERSION = "1.0.0"    # bump when the synthetic data changes on purpose

HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------
#  The 25 span types - FIXED ORDER (section 5.1). This order defines the
#  label ids: O = 0, B-type = 2k-1, I-type = 2k for type number k.
# ---------------------------------------------------------------------
TYPES = [
    "S_NAME", "S_ADDRESS", "S_REG_ID", "S_PHONE", "S_EMAIL", "S_URL",
    "S_PERSON", "C_NAME", "C_ADDRESS", "C_REG_ID", "LEGAL_FORM", "CAPITAL",
    "FOUNDED", "STAFF", "REVENUE", "REVENUE_YEAR", "ACTIVITY",
    "ACTIVITY_CODE", "SERVICE", "HOURS", "CERT", "DOC_DATE", "DOC_TOTAL",
    "LINE_TOTAL", "PRICE",
]


def _label_names(types):
    # The same rule as decode.label_names() (Appendix E). decode.py needs
    # torch, config.py must not, so the rule is repeated here and
    # tests/test_config.py proves the two lists are identical.
    names = ["O"]
    for t in types:
        names += ["B-" + t, "I-" + t]
    return names


LABELS = _label_names(TYPES)                  # 51 names
LABEL_ID = {name: i for i, name in enumerate(LABELS)}

# The 11 document types - FIXED ORDER (section 6)
DOC_TYPES = ["invoice", "quote", "brochure", "registration", "financials",
             "price_list", "staff_list", "contract", "letter", "terms",
             "other"]

# The 10 languages - FIXED ORDER (section 3)
LANGS = ["ar", "zh", "en", "fr", "ru", "es", "it", "hi", "ja", "ko"]

# Which labels have a format rule, and of what kind (section 14.2)
KIND_OF_LABEL = {
    "REVENUE": "amount", "CAPITAL": "amount", "DOC_TOTAL": "amount",
    "LINE_TOTAL": "amount", "PRICE": "amount",
    "FOUNDED": "date", "DOC_DATE": "date",
    "REVENUE_YEAR": "year",
    "STAFF": "count",
    "S_PHONE": "phone",
    "S_EMAIL": "email", "S_URL": "url",
    "S_REG_ID": "reg_id", "C_REG_ID": "reg_id",
    "LEGAL_FORM": "legal_form",
    "ACTIVITY_CODE": "activity_code",
}

# All dates of the synthetic world are relative to this day. The
# generator never looks at the real clock (section 10.1).
REFERENCE_DATE = date(2026, 6, 30)

# The data splits, in the order they are generated
SPLITS = ["train", "val", "dev_heldout", "test_seen", "test_heldout",
          "test_locale", "traps"]
EVAL_SPLITS = ["val", "dev_heldout", "test_seen", "test_heldout",
               "test_locale", "traps"]

# ---------------------------------------------------------------------
#  Presets (section 8). Times are in minutes.
# ---------------------------------------------------------------------
PRESETS = {
    "smoke": {
        "vocab_size": 8000, "d_model": 128, "n_layer": 2, "n_head": 2,
        "ffn_hidden": 352, "max_len": 512, "dropout": 0.0,
        "folders": {"train": 60, "val": 10, "dev_heldout": 10,
                    "test_seen": 10, "test_heldout": 10, "test_locale": 5},
        "traps_chunks": 100,
        # tokenizer training text: synthetic train chunks only
        "tok_wiki_chars": None,
        "wiki_caps": None,                     # no Wikipedia in smoke
        "pretrain": {"steps": 100, "batch": 16, "seq_len": 256,
                     "lr": 1e-3, "minutes": None},
        "finetune": {"steps": 150, "tokens_per_batch": 4000, "lr": 5e-4,
                     "epochs": None, "minutes": None,
                     "eval": "end"},
    },
    "pilot": {
        "vocab_size": 32000, "d_model": 256, "n_layer": 4, "n_head": 4,
        "ffn_hidden": 704, "max_len": 1024, "dropout": 0.1,
        "folders": {"train": 3000, "val": 150, "dev_heldout": 300,
                    "test_seen": 300, "test_heldout": 300,
                    "test_locale": 100},
        "traps_chunks": 1000,
        # characters of Wikipedia per language for the tokenizer
        "tok_wiki_chars": {"default": 3_000_000, "zh": 1_000_000,
                           "ja": 1_000_000, "ko": 1_300_000},
        "wiki_caps": {"default": 10_000_000, "ko": 4_000_000,
                      "zh": 3_000_000, "ja": 3_000_000},
        "pretrain": {"steps": None, "batch": 32, "seq_len": 512,
                     "lr": 8e-4, "minutes": 60},
        "finetune": {"steps": None, "tokens_per_batch": 8000, "lr": 5e-4,
                     "epochs": 1, "minutes": 90,
                     "eval": "every_15_min"},
    },
    "full": {
        "vocab_size": 48000, "d_model": 384, "n_layer": 8, "n_head": 6,
        "ffn_hidden": 1024, "max_len": 1024, "dropout": 0.1,
        "folders": {"train": 24000, "val": 600, "dev_heldout": 1000,
                    "test_seen": 1000, "test_heldout": 1000,
                    "test_locale": 300},
        "traps_chunks": 3000,
        "tok_wiki_chars": {"default": 20_000_000, "zh": 7_000_000,
                           "ja": 7_000_000, "ko": 9_000_000},
        "wiki_caps": {"default": 120_000_000, "ko": 45_000_000,
                      "zh": 35_000_000, "ja": 35_000_000},
        # 12,000 steps: batch 128 x 512 for the first 80 %, then
        # 64 x 1024 for the last 20 %; at most 8 hours
        "pretrain": {"steps": 12000, "batch": 128, "seq_len": 512,
                     "late_batch": 64, "late_seq_len": 1024,
                     "late_share": 0.2, "lr": 6e-4, "minutes": 480},
        "finetune": {"steps": None, "tokens_per_batch": 48000,
                     "lr": 3e-4, "epochs": 3, "minutes": 300,
                     "eval": "quarter_epoch"},
    },
}

# The model id written into documents.db is the model file's stem
MODEL_FILES = {"full": "extractor-%s.pt" % VERSION,
               "pilot": "extractor-pilot.pt",
               "smoke": "extractor-smoke.pt"}


def data_dir(preset):
    return HERE / "data" / preset


def runs_dir(preset):
    return HERE / "runs" / preset


def corpus_dir(preset):
    return HERE / "corpus" / preset


def preset_hash(preset, *extra):
    """A short fingerprint of a preset's settings (plus anything else a
    stage depends on). A stage is re-run when its fingerprint changes."""
    blob = json.dumps([PRESETS[preset], VERSION, GENERATOR_VERSION] +
                      list(extra), sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]
