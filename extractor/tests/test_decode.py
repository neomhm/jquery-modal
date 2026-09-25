"""Decoder: Viterbi repairs illegal BIO sequences, long chunks are read
in overlapping windows with exactly one prediction per token."""
import torch

import decode
import model as M


def test_viterbi_repairs_broken_span():
    names = decode.label_names(["A", "B"])
    allowed, start_ok = decode.allowed_transitions(names)
    # arg-max alone would read O I-A I-A O - an I without its B
    probs = torch.tensor([[0.6, 0.3, 0.05, 0.03, 0.02],
                          [0.1, 0.2, 0.6, 0.05, 0.05],
                          [0.1, 0.1, 0.7, 0.05, 0.05],
                          [0.8, 0.05, 0.05, 0.05, 0.05]])
    path = decode.viterbi(probs.log(), allowed, start_ok)
    assert [names[i] for i in path] == ["B-A", "I-A", "I-A", "O"]


def test_spans_skip_whitespace_tokens():
    names = decode.label_names(["X"])
    # "12 rue\n01210 Gex": the newline token sits inside the span
    offsets = [(0, 2, False), (3, 6, False), (6, 7, True),
               (7, 12, False), (13, 16, False)]
    path = [1, 2, 2, 2, 2]
    probs = torch.full((5, 3), 0.9)
    spans = decode.spans_from_labels(path, probs, offsets, names)
    assert [(s, e, k) for s, e, k, _ in spans] == [(0, 16, "X")]


def test_windows_cover_every_token_once():
    assert decode.window_starts(500, 1024, 768) == [0]
    assert decode.window_starts(3000, 1024, 768) == [0, 768, 1536, 1976]
    torch.manual_seed(0)
    net = M.Extractor(M.Config(300, 64, 2, 2, 128, max_len=64,
                               n_labels=5)).eval()
    ids = torch.randint(5, 300, (200,)).tolist()
    token_lp, doc_lp, lang_lp = decode.predict_long(net, ids, window=64,
                                                    stride=48, temperature=1.3)
    assert token_lp.shape == (200, 5)
    assert token_lp.device.type == "cpu"
    # each row is a proper distribution
    assert torch.allclose(token_lp.exp().sum(-1), torch.ones(200), atol=1e-4)
    assert doc_lp.shape == (11,) and lang_lp.shape == (10,)
    assert torch.isfinite(token_lp).all()


def test_predict_long_on_gpu_if_present():
    """The model may sit on CUDA / ROCm (MEGA9, the desktop): windows must
    be built on the model's device and come back on the CPU."""
    if not torch.cuda.is_available():
        print("    (no GPU here - skipped)")
        return
    net = M.Extractor(M.Config(300, 64, 2, 2, 128, max_len=64,
                               n_labels=5)).cuda().eval()
    ids = torch.randint(5, 300, (150,)).tolist()
    token_lp, doc_lp, lang_lp = decode.predict_long(net, ids, window=64,
                                                    stride=48)
    assert token_lp.device.type == "cpu" and token_lp.shape == (150, 5)
