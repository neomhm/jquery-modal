"""
pack.py - stages "tokenizer" and "pack".

    py pack.py tokenizer pilot
    py pack.py pack pilot

tokenizer (section 7)
    Trains the byte-level BPE of tok.py on a language-balanced mix:
    Wikipedia (per language: tok_wiki_chars of the preset) plus the
    synthetic train chunks (30% of all characters). Smoke uses the
    synthetic chunks only. Then measures, on val (+ dev_heldout for the
    boundary rate):
      * characters per token, per language
      * the boundary rate: the share of spans whose start and end fall
        on token edges (tok.boundary_ok). It MUST be >= 99.5%; below
        that the stage fails, because the generator broke rule R2.
    Writes runs/<preset>/tokenizer.json and tokenizer_report.json.

pack (sections 9.4 and 12)
    Pretraining: one uint16 array per source in runs/<preset>/pack/
    (wiki_<lang>.npy, wikieval_<lang>.npy, syn_<lang>.npy): all the
    paragraphs of the source tokenized and joined with [SEP].
    Fine-tuning: per split, the chunks as token ids and one label per
    token (tok.token_labels), plus the document type and language, in
    ft_<split>.npz.
"""
import gzip
import json
import random
import sys
import time

import numpy as np

import config
import tok as T

SEP = T.SEP


def read_chunks(preset, split):
    path = config.data_dir(preset) / ("%s.jsonl.gz" % split)
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def read_lines(path):
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line


def wiki_available(preset):
    stats = config.corpus_dir(preset) / "corpus_stats.json"
    if not stats.exists():
        return False
    data = json.loads(stats.read_text(encoding="utf-8"))
    return data.get("wiki") == "used"


# =====================================================================
#  tokenizer
# =====================================================================
def tokenizer_texts(preset, log):
    """The training text: a list of strings, balanced by language."""
    settings = config.PRESETS[preset]
    texts, wiki_chars = [], 0
    per_lang = {}
    if settings.get("tok_wiki_chars") and wiki_available(preset):
        caps = settings["tok_wiki_chars"]
        for lang in config.LANGS:
            cap = caps.get(lang, caps["default"])
            got = 0
            for para in read_lines(config.corpus_dir(preset) /
                                   ("wiki_%s.txt.gz" % lang)):
                texts.append(para)
                got += len(para)
                if got >= cap:
                    break
            per_lang[lang] = got
            wiki_chars += got
    # synthetic train chunks: 30% of all characters (all of them in smoke)
    chunks = [c["text"] for c in read_chunks(preset, "train")]
    random.Random(1).shuffle(chunks)
    if wiki_chars:
        want = wiki_chars * 0.3 / 0.7
        got = 0
        for text in chunks:
            texts.append(text)
            got += len(text)
            if got >= want:
                break
        syn = got
    else:
        texts.extend(chunks)
        syn = sum(len(t) for t in chunks)
    log("tokenizer text: %.1fM chars of Wikipedia %s, %.1fM synthetic" % (
        wiki_chars / 1e6, per_lang or "", syn / 1e6))
    return texts, {"wiki_chars": per_lang, "synthetic_chars": syn}


def tokenizer_stage(preset, log=print):
    began = time.time()
    out = config.runs_dir(preset)
    out.mkdir(parents=True, exist_ok=True)
    texts, sources = tokenizer_texts(preset, log)
    tok = T.train_tokenizer(texts, config.PRESETS[preset]["vocab_size"])
    tok.save(str(out / "tokenizer.json"))
    report = measure(tok, preset)
    report["sources"] = sources
    report["vocab_size"] = tok.get_vocab_size()
    report["seconds"] = round(time.time() - began, 1)
    with open(out / "tokenizer_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    log("boundary rate %.3f%% (%d spans); chars per token %s" % (
        100 * report["boundary_rate"], report["boundary_spans"],
        {k: round(v, 2) for k, v in report["chars_per_token"].items()}))
    if report["boundary_rate"] < 0.995:
        raise RuntimeError("boundary rate %.3f%% < 99.5%%: the generator "
                           "breaks rule R2 somewhere - see "
                           "tokenizer_report.json" %
                           (100 * report["boundary_rate"]))
    return report


def measure(tok, preset):
    """Characters per token (val) and the boundary rate (val +
    dev_heldout), with the 20 worst failures."""
    chars, tokens = {}, {}
    ok = total = 0
    failures = []
    for split in ("val", "dev_heldout"):
        for c in read_chunks(preset, split):
            ids, offsets = T.encode(tok, c["text"])
            if split == "val":
                chars[c["lang"]] = chars.get(c["lang"], 0) + len(c["text"])
                tokens[c["lang"]] = tokens.get(c["lang"], 0) + len(ids)
            for s, e, label in c["spans"]:
                total += 1
                if T.boundary_ok(offsets, s, e):
                    ok += 1
                elif len(failures) < 20:
                    failures.append({"chunk": c["id"], "label": label,
                                     "span": c["text"][s:e],
                                     "context": c["text"][max(0, s - 15):
                                                          e + 15]})
    return {"boundary_rate": ok / max(1, total), "boundary_spans": total,
            "boundary_failures": failures,
            "chars_per_token": {lg: chars[lg] / max(1, tokens[lg])
                                for lg in sorted(chars)}}


def load_tokenizer(preset):
    from tokenizers import Tokenizer
    return Tokenizer.from_file(str(config.runs_dir(preset) /
                                   "tokenizer.json"))


# =====================================================================
#  pack
# =====================================================================
def encode_paragraphs(tok, lines, batch=2000):
    """Token ids of paragraphs joined by [SEP], as one uint16 array."""
    parts = []
    buf = []

    def flush():
        for enc in tok.encode_batch(buf, add_special_tokens=False):
            parts.append(np.asarray(enc.ids, dtype=np.uint16))
            parts.append(np.asarray([SEP], dtype=np.uint16))
        buf.clear()
    for line in lines:
        buf.append(line)
        if len(buf) >= batch:
            flush()
    if buf:
        flush()
    if not parts:
        return np.zeros(0, dtype=np.uint16)
    return np.concatenate(parts)


def pack_stage(preset, log=print):
    began = time.time()
    tok = load_tokenizer(preset)
    assert tok.get_vocab_size() < 65536
    out = config.runs_dir(preset) / "pack"
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    # ---- pretraining: Wikipedia, per language
    if wiki_available(preset):
        for lang in config.LANGS:
            for kind, name in (("wiki", "wiki_%s.txt.gz"),
                               ("wikieval", "wiki_%s_eval.txt.gz")):
                arr = encode_paragraphs(tok, read_lines(
                    config.corpus_dir(preset) / (name % lang)))
                np.save(out / ("%s_%s.npy" % (kind, lang)), arr)
                counts["%s_%s" % (kind, lang)] = int(arr.size)
    extra = sorted(config.corpus_dir(preset).glob("extra_*.txt.gz"))
    for path in extra:
        lang = path.name[len("extra_"):-len(".txt.gz")]
        arr = encode_paragraphs(tok, read_lines(path))
        np.save(out / ("extra_%s.npy" % lang), arr)
        counts["extra_%s" % lang] = int(arr.size)
    # ---- pretraining: synthetic train chunks, per language
    by_lang = {lang: [] for lang in config.LANGS}
    for c in read_chunks(preset, "train"):
        by_lang[c["lang"]].append(c["text"])
    for lang, texts in by_lang.items():
        arr = encode_paragraphs(tok, texts)
        np.save(out / ("syn_%s.npy" % lang), arr)
        counts["syn_%s" % lang] = int(arr.size)
    # ---- fine-tuning: every split
    for split in config.SPLITS:
        n = pack_split(tok, preset, split, out)
        counts["ft_%s" % split] = n
    log("packed in %.0fs: %s" % (time.time() - began, counts))
    return counts


def pack_split(tok, preset, split, out):
    """ft_<split>.npz: flat token ids and labels, with the start of each
    chunk; plus doc type, language and the chunk ids."""
    ids_all, lab_all, starts = [], [], [0]
    doc, lang, cids = [], [], []
    for c in read_chunks(preset, split):
        ids, offsets = T.encode(tok, c["text"])
        labels = T.token_labels(offsets, [tuple(s) for s in c["spans"]],
                                [tuple(x) for x in c.get("cut", [])],
                                config.LABEL_ID)
        ids_all.append(np.asarray(ids, dtype=np.uint16))
        lab_all.append(np.asarray(labels, dtype=np.int8))
        starts.append(starts[-1] + len(ids))
        doc.append(config.DOC_TYPES.index(c["doc_type"]))
        lang.append(config.LANGS.index(c["lang"]))
        cids.append(c["id"])
    if not cids:
        return 0
    np.savez(out / ("ft_%s.npz" % split),
             ids=np.concatenate(ids_all), labels=np.concatenate(lab_all),
             starts=np.asarray(starts, dtype=np.int64),
             doc=np.asarray(doc, dtype=np.int8),
             lang=np.asarray(lang, dtype=np.int8),
             chunk_ids=np.asarray(cids))
    return len(cids)


def load_split(preset, split):
    """-> dict with 'ids', 'labels' (lists of arrays per chunk), 'doc',
    'lang', 'chunk_ids'; None when the split was not packed."""
    path = config.runs_dir(preset) / "pack" / ("ft_%s.npz" % split)
    if not path.exists():
        return None
    # Read each array ONCE: every z["..."] reads and unpacks the whole
    # array again, and a slice keeps its whole array alive - slicing
    # z["ids"] per chunk would hold one full copy per chunk in memory.
    with np.load(path) as z:
        starts = z["starts"]
        all_ids = z["ids"]
        all_labels = z["labels"]
        doc, lang = z["doc"], z["lang"]
        chunk_ids = list(z["chunk_ids"])
    ids = [all_ids[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]
    labels = [all_labels[starts[i]:starts[i + 1]]
              for i in range(len(starts) - 1)]
    return {"ids": ids, "labels": labels, "doc": doc, "lang": lang,
            "chunk_ids": chunk_ids}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    what = sys.argv[1]
    preset = sys.argv[2] if len(sys.argv) > 2 else "smoke"
    if what == "tokenizer":
        tokenizer_stage(preset)
    else:
        pack_stage(preset)
