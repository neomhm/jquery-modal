"""
extractor.py - the inference API (section 13). Other code, including the
PLAN's plan.py, depends on exactly this:

    from extractor import Extractor
    ex = Extractor("extractor-pilot.pt")           # device="cpu"
    results = ex.extract(["Boulangerie Martin SARL ..."], batch_size=16)

For each text the model gives one label per token; decode.viterbi picks
the best LEGAL label sequence (BIO), and every span is a slice of the
text - the model cannot write a character that is not in the source.

Output per text:
    {"language": "fr", "language_score": 0.998,
     "doc_type": "invoice", "doc_type_score": 0.97,
     "doc_type_probs": [11 values in the order of config.DOC_TYPES],
     "spans": [{"label": "S_NAME", "start": 0, "end": 23,
                "text": "Boulangerie Martin SARL", "score": 0.991,
                "accepted": true}]}
An empty or whitespace-only text gives nulls and no spans.

Threads: Extractor(path, threads=8) calls torch.set_num_threads(8). That
setting is PROCESS-WIDE: it changes every model in the process. extract()
is protected by a lock, so several threads may call it safely.
"""
import threading

import torch

import config
import decode
import model as M
import tok as T


def predict(net, tokenizer, texts, max_len, temperature=1.0,
            thresholds=None, batch_size=16, labels=None, keep_probs=False):
    """The whole decoding path, shared by the API, fine-tuning,
    calibration and evaluation. Returns one dict per text (the format
    above). keep_probs=True also returns the token log-probabilities
    and the offsets (for calibration)."""
    labels = labels or config.LABELS
    types = [n[2:] for n in labels if n.startswith("B-")]
    allowed, start_ok = decode.allowed_transitions(labels)
    device = next(net.parameters()).device
    out = [None] * len(texts)
    encoded = []
    for i, text in enumerate(texts):
        if not text or not text.strip():
            out[i] = {"language": None, "language_score": None,
                      "doc_type": None, "doc_type_score": None,
                      "doc_type_probs": None, "spans": []}
            continue
        ids, offsets = T.encode(tokenizer, text)
        if not ids:
            out[i] = {"language": None, "language_score": None,
                      "doc_type": None, "doc_type_score": None,
                      "doc_type_probs": None, "spans": []}
            continue
        encoded.append((i, ids, offsets))
    short = [e for e in encoded if len(e[1]) <= max_len]
    long_ = [e for e in encoded if len(e[1]) > max_len]
    results = {}
    short.sort(key=lambda e: len(e[1]))
    with torch.inference_mode():
        for k in range(0, len(short), batch_size):
            group = short[k:k + batch_size]
            n = max(len(e[1]) for e in group)
            ids = torch.full((len(group), n), T.PAD, dtype=torch.long)
            keep = torch.zeros((len(group), n), dtype=torch.bool)
            for j, (_, seq, _) in enumerate(group):
                ids[j, :len(seq)] = torch.tensor(seq)
                keep[j, :len(seq)] = True
            ids, keep = ids.to(device), keep.to(device)
            h = net(ids, keep)
            tok_logits = net.token_logits(h).float().cpu() / temperature
            doc_lp = torch.log_softmax(net.doc_logits(h, keep).float(),
                                       -1).cpu()
            lang_lp = torch.log_softmax(net.lang_logits(h, keep).float(),
                                        -1).cpu()
            for j, (i, seq, offsets) in enumerate(group):
                lp = torch.log_softmax(tok_logits[j, :len(seq)], -1)
                results[i] = (lp, doc_lp[j], lang_lp[j], offsets)
        for i, seq, offsets in long_:
            lp, doc_lp, lang_lp = decode.predict_long(
                net, seq, window=max_len, stride=max_len * 3 // 4,
                temperature=temperature)
            results[i] = (lp, doc_lp, lang_lp, offsets)
    for i, (lp, doc_lp, lang_lp, offsets) in results.items():
        path = decode.viterbi(lp, allowed, start_ok)
        probs = lp.exp()
        spans = []
        text = texts[i]
        for s, e, kind, score in decode.spans_from_labels(path, probs,
                                                          offsets, labels):
            spans.append({"label": kind, "start": s, "end": e,
                          "text": text[s:e], "score": round(score, 4),
                          "accepted": (thresholds is None or
                                       score >= thresholds.get(kind, 0.5))})
        doc_p = doc_lp.exp()
        lang_p = lang_lp.exp()
        d, g = int(doc_p.argmax()), int(lang_p.argmax())
        out[i] = {"language": config.LANGS[g],
                  "language_score": round(float(lang_p[g]), 4),
                  "doc_type": config.DOC_TYPES[d],
                  "doc_type_score": round(float(doc_p[d]), 4),
                  "doc_type_probs": [round(float(x), 4) for x in doc_p],
                  "spans": spans}
        if keep_probs:
            out[i]["_log_probs"] = lp
            out[i]["_offsets"] = offsets
    del types
    return out


class Extractor:
    """Loads a model file once; extract() may then be called many
    times, from several threads."""

    def __init__(self, path, device="cpu", threads=None):
        if threads:
            torch.set_num_threads(int(threads))      # process-wide
        self.device = torch.device(device)
        self.net, tokenizer_json, meta = M.load(str(path), self.device)
        self.net.eval()
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_str(tokenizer_json)
        self.meta = meta
        self.version = meta.get("version", config.VERSION)
        self.labels = meta.get("labels", config.LABELS)
        self.doc_types = meta.get("doc_types", config.DOC_TYPES)
        self.languages = meta.get("langs", config.LANGS)
        self.thresholds = meta.get("thresholds") or {}
        self.temperature = float(meta.get("temperature") or 1.0)
        self.max_len = int(meta.get("max_len") or
                           self.net.config.max_len)
        self._lock = threading.Lock()

    def extract(self, texts, batch_size=16):
        """list[str] -> list[dict] (see the top of this file)."""
        if isinstance(texts, str):
            raise TypeError("extract() takes a list of texts")
        with self._lock:
            return predict(self.net, self.tokenizer, list(texts),
                           self.max_len, self.temperature,
                           self.thresholds, batch_size, self.labels)
