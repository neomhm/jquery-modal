"""
decode.py - from the model's per-token scores to exact character spans.

Two steps, both plain code:
  1. viterbi(): pick the best label sequence that is LEGAL in BIO
     (an I-X may only follow B-X or I-X). This removes broken spans
     like "O I-REVENUE I-REVENUE" instead of guessing where they start.
  2. spans_from_labels(): turn the label sequence into (start, end,
     TYPE, score) using the token offsets. The value is always a slice
     of the original chunk - the model can never write a character
     that is not in the source.
"""
import math

import torch


def label_names(types):
    """["O", "B-T1", "I-T1", "B-T2", "I-T2", ...] in a FIXED order."""
    names = ["O"]
    for t in types:
        names += ["B-" + t, "I-" + t]
    return names


def allowed_transitions(names):
    """allowed[i][j] = True if label j may follow label i."""
    n = len(names)
    allowed = torch.ones(n, n, dtype=torch.bool)
    for j, name in enumerate(names):
        if name.startswith("I-"):
            kind = name[2:]
            for i, prev in enumerate(names):
                if prev not in ("B-" + kind, "I-" + kind):
                    allowed[i, j] = False
    start_ok = torch.tensor([not nm.startswith("I-") for nm in names])
    return allowed, start_ok


def viterbi(log_probs, allowed, start_ok):
    """log_probs: (T, K) CPU tensor of log-probabilities for ONE
    sequence (padding already removed). Returns T label indices."""
    T, K = log_probs.shape
    if T == 0:
        return []
    neg = -1e9
    trans = torch.where(allowed, 0.0, neg)                 # (K, K)
    score = log_probs[0] + torch.where(start_ok, 0.0, neg)
    back = []
    for t in range(1, T):
        cand = score[:, None] + trans                      # (K, K)
        best, idx = cand.max(dim=0)
        score = best + log_probs[t]
        back.append(idx)
    path = [int(score.argmax())]
    for idx in reversed(back):
        path.append(int(idx[path[-1]]))
    return path[::-1]


def spans_from_labels(path, probs, offsets, names):
    """path: label index per token; probs: (T, K) probabilities;
    offsets: (start, end, is_space) per token (from tok.encode).
    Returns [(start, end, TYPE, score)], score = mean probability of the
    chosen label over the span's non-space tokens."""
    spans, cur = [], None       # cur = [start, end, TYPE, [p...]]
    for t, lab in enumerate(path):
        name = names[lab]
        a, b, space = offsets[t]
        p = float(probs[t, lab])
        if name.startswith("B-") and not space:
            if cur:
                spans.append(cur)
            cur = [a, b, name[2:], [p]]
        elif name.startswith("I-") and cur and name[2:] == cur[2]:
            if not space:
                cur[1] = b
                cur[3].append(p)
        else:
            if cur:
                spans.append(cur)
            cur = None
    if cur:
        spans.append(cur)
    return [(s, e, kind, sum(ps) / len(ps)) for s, e, kind, ps in spans]


def window_starts(n, window, stride):
    """Start positions of the windows that cover n tokens."""
    if n <= window:
        return [0]
    starts = list(range(0, n - window, stride)) + [n - window]
    return sorted(set(starts))


@torch.no_grad()
def predict_long(net, ids, window=1024, stride=768, temperature=1.0):
    """Token log-probs, doc-type and language log-probs for ONE chunk of
    any length. Chunks longer than `window` tokens are read in
    overlapping windows; each token takes its scores from the window in
    which it sits farthest from an edge (most context on both sides).
    The two pooled heads are averaged over windows, weighted by length.

    Runs on whatever device the model is on (CPU, CUDA or ROCm) and
    always RETURNS CPU tensors, because viterbi() works on the CPU.
    `temperature` is the calibrated value: token logits are divided by
    it before the softmax."""
    device = next(net.parameters()).device
    n = len(ids)
    starts = window_starts(n, window, stride)
    token_lp = [None] * n
    best_room = [-1] * n
    doc_sum, lang_sum, weight = 0.0, 0.0, 0
    for s in starts:
        piece = torch.tensor([ids[s:s + window]], device=device)
        keep = torch.ones_like(piece, dtype=torch.bool)
        h = net(piece, keep)
        logits = net.token_logits(h)[0].float() / temperature
        lp = torch.log_softmax(logits, -1).cpu()
        m = piece.shape[1]
        for j in range(m):
            room = min(j, m - 1 - j)
            if room > best_room[s + j]:
                best_room[s + j] = room
                token_lp[s + j] = lp[j]
        doc_sum = doc_sum + torch.softmax(
            net.doc_logits(h, keep)[0].float(), -1).cpu() * m
        lang_sum = lang_sum + torch.softmax(
            net.lang_logits(h, keep)[0].float(), -1).cpu() * m
        weight += m
    return (torch.stack(token_lp) if n else torch.zeros(0),
            (doc_sum / max(weight, 1)).log(),
            (lang_sum / max(weight, 1)).log())
