"""
corpus.py - stage "corpus" (section 9.1 / 9.2): plain-text Wikipedia for
the tokenizer and for pretraining.

    py corpus.py pilot

For each of the ten languages it streams the Wikipedia dump of
2023-11-01 with the `datasets` library, keeps paragraphs of at least 80
characters, and stops at the language's character cap (config.PRESETS).
It writes, in corpus/<preset>/:
    wiki_<lang>.txt.gz        one paragraph per line (99%)
    wiki_<lang>_eval.txt.gz   the other 1%, held out for the MLM check
    corpus_stats.json         characters and paragraphs per language

If Wikipedia cannot be reached, nothing is downloaded: the stats say
"wiki: unavailable" and pretraining uses the synthetic text only (9.2).

Text files in a folder corpus_extra/ (UTF-8, *.txt) are added too: each
paragraph goes to the language whose script and letters it shows most.

Why a separate process: the `datasets` library can crash when Python
shuts down after streaming. build.py runs this file on its own, and the
script leaves with os._exit() once every file is closed.
"""
import gzip
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import zlib

import config

HERE = pathlib.Path(__file__).resolve().parent
MIN_PARAGRAPH = 80


def wiki_reachable(timeout=10):
    """The same test as check.py: can we reach the Hugging Face hub?"""
    import urllib.request
    try:
        urllib.request.urlopen(
            "https://huggingface.co/api/datasets/wikimedia/wikipedia",
            timeout=timeout)
        return True
    except Exception:
        return False


def cap_for(settings, lang):
    caps = settings.get("wiki_caps") or {}
    return caps.get(lang, caps.get("default", 0))


def stream_language(lang, cap, out_train, out_eval, log):
    """Streams one language until `cap` characters. 1 paragraph in 100
    (chosen by a hash of its text, so the split is stable) goes to the
    evaluation file."""
    from datasets import load_dataset
    ds = load_dataset("wikimedia/wikipedia", "20231101." + lang,
                      split="train", streaming=True)
    chars = paragraphs = held = 0
    began = time.time()
    for article in ds:
        for para in article["text"].split("\n"):
            para = para.strip()
            if len(para) < MIN_PARAGRAPH:
                continue
            if zlib.crc32(para.encode("utf-8")) % 100 == 0:
                out_eval.write(para + "\n")
                held += 1
            else:
                out_train.write(para + "\n")
            chars += len(para)
            paragraphs += 1
        if chars >= cap:
            break
    log("  %s: %d paragraphs, %.1fM characters (%d held out) in %.0fs" % (
        lang, paragraphs, chars / 1e6, held, time.time() - began))
    return {"chars": chars, "paragraphs": paragraphs, "held_out": held,
            "complete": chars >= cap}


# -------------------------------------------------------------------
#  corpus_extra/: assign each paragraph to a language by its letters
# -------------------------------------------------------------------
SCRIPT_OF = [("ar", "ARABIC"), ("hi", "DEVANAGARI"), ("ru", "CYRILLIC"),
             ("ko", "HANGUL"), ("ja", "HIRAGANA"), ("ja", "KATAKANA"),
             ("zh", "CJK")]
LATIN_HINTS = {
    "fr": [" le ", " la ", " les ", " des ", " est ", " et ", "é", "è"],
    "es": [" el ", " los ", " las ", " del ", " y ", "ñ", "ó"],
    "it": [" il ", " gli ", " della ", " che ", " è ", " di "],
    "en": [" the ", " and ", " of ", " is ", " to "],
}


def guess_language(text):
    counts = {}
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        for lang, key in SCRIPT_OF:
            if key in name:
                counts[lang] = counts.get(lang, 0) + 1
                break
        else:
            counts["latin"] = counts.get("latin", 0) + 1
    if not counts:
        return None
    best = max(counts, key=counts.get)
    if best == "zh" and counts.get("ja"):
        return "ja"
    if best != "latin":
        return best
    low = " " + text.lower() + " "
    scores = {lang: sum(low.count(h) for h in hints)
              for lang, hints in LATIN_HINTS.items()}
    return max(scores, key=scores.get)


def add_extra(out_dir, log):
    folder = HERE / "corpus_extra"
    if not folder.exists():
        return {}
    added = {}
    files = {}
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for para in re.split(r"\n\s*\n|\n", text):
            para = para.strip()
            if len(para) < MIN_PARAGRAPH:
                continue
            lang = guess_language(para)
            if lang not in config.LANGS:
                continue
            if lang not in files:
                files[lang] = gzip.open(out_dir / ("extra_%s.txt.gz" % lang),
                                        "wt", encoding="utf-8")
            files[lang].write(para + "\n")
            added[lang] = added.get(lang, 0) + len(para)
    for f in files.values():
        f.close()
    if added:
        log("  corpus_extra: %s characters added" % added)
    return added


def build(preset, log=print):
    settings = config.PRESETS[preset]
    out_dir = config.corpus_dir(preset)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"preset": preset, "wiki": "unavailable", "languages": {}}
    if preset == "smoke":
        stats["wiki"] = "not used (smoke)"
    elif not wiki_reachable():
        log("Wikipedia cannot be reached: pretraining will use the "
            "synthetic text only (section 9.2).")
    else:
        try:
            import datasets                              # noqa: F401
        except ImportError:
            log("The 'datasets' package is missing: no Wikipedia.")
        else:
            stats["wiki"] = "used"
            for lang in config.LANGS:
                cap = cap_for(settings, lang)
                train_path = out_dir / ("wiki_%s.txt.gz" % lang)
                eval_path = out_dir / ("wiki_%s_eval.txt.gz" % lang)
                try:
                    with gzip.open(train_path, "wt", encoding="utf-8") as a, \
                            gzip.open(eval_path, "wt", encoding="utf-8") as b:
                        stats["languages"][lang] = stream_language(
                            lang, cap, a, b, log)
                except Exception as exc:          # a language failed
                    log("  %s: failed (%s)" % (lang, exc))
                    stats["languages"][lang] = {"chars": 0, "error": str(exc)}
            if not any(v.get("chars") for v in stats["languages"].values()):
                stats["wiki"] = "unavailable"
    stats["extra"] = add_extra(out_dir, log)
    with open(out_dir / "corpus_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    return stats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    preset = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    result = build(preset)
    print("corpus: wiki %s" % result["wiki"], flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    # leave without the interpreter shutdown that can crash 'datasets'
    os._exit(0)
