"""
Tests of the pipeline around the model: the generator (a few tasks and
their self-check), real-file round trips, training batches and the
learning-rate schedule, gradient accumulation, the candidate loop of
tulip.py (with a stand-in writer) and the database of import_sheets.py.
"""
import json
import pathlib
import sqlite3
import tempfile

import numpy as np
import torch

import config
import model as M
import tok as TK
import tulipscript as ts


def test_generated_tasks_pass_their_own_program():
    import evaluate as E
    from gen import tasks as T
    made = 0
    for i in range(40):
        task, _ = T.make_task("val", 90000 + i)
        if task is None:
            continue
        made += 1
        assert ts.canonical(task["program"]) == task["program"]
        sheet = T.sheet_from_task(task)
        assert E.pass_at_1(task, task["program"], sheet), task["id"]
    assert made >= 36


def test_real_file_round_trip():
    from gen import realfile
    from gen import tasks as T
    with tempfile.TemporaryDirectory() as tmp:
        n = 0
        for i in range(12):
            task, _ = T.make_task("val", 91000 + i)
            if task:
                ok, detail = realfile.round_trip(task, tmp)
                assert ok, detail
                n += 1
        assert n >= 10


def test_learning_rate_schedule():
    import train
    peak = 1e-3
    assert abs(train.lr_at(0, 10000, peak) - peak / 200) < 1e-12  # 2% = 200
    assert abs(train.lr_at(199, 10000, peak) - peak) < 1e-12
    assert abs(train.lr_at(9999, 10000, peak) - 0.1 * peak) < 1e-6
    # at least 100 warm-up steps
    assert train.lr_at(0, 1000, peak) == peak / 100


def test_batches_cover_everything_within_budget():
    import train
    rng = np.random.default_rng(0)
    lengths = rng.integers(50, 2000, size=500)
    batches = train.epoch_batches(lengths, 8000, np.random.default_rng(1))
    seen = sorted(i for b in batches for i in b)
    assert seen == list(range(500))
    for b in batches:
        assert len(b) == 1 or max(lengths[i] for i in b) * len(b) <= 8000


def test_micro_batches_add_up_to_the_batch():
    """Gradients of one batch are the same whether it is cut into 1 or
    several micro-batches (the out-of-memory fallback)."""
    import train
    torch.manual_seed(0)
    net = M.Tulip(M.Config(vocab_size=50, d_model=32, n_layer=1, n_head=2,
                           ffn_hidden=64, max_len=64))
    rows = []
    rng = np.random.default_rng(3)
    for n in (10, 14, 9, 20):
        prompt = list(rng.integers(4, 50, size=n))
        program = list(rng.integers(4, 50, size=5))
        rows.append(tuple(np.asarray(x) for x in M.training_pair(
            prompt, program, TK.PROGRAM, TK.END)))
    dev = torch.device("cpu")
    grads = []
    for parts in (1, 4):
        net.zero_grad()
        state = {"parts": parts}
        train.forward_backward(net, rows, dev, None, None, state, print)
        grads.append(torch.cat([p.grad.flatten() for p in net.parameters()
                                if p.grad is not None]))
    assert torch.allclose(grads[0], grads[1], atol=1e-6)


class FakeTulip:
    """The candidate loop of tulip.Tulip with a stand-in writer."""

    def __new__(cls, programs):
        from tulip import Tulip
        obj = Tulip.__new__(Tulip)
        obj.sampling = dict(config.SAMPLING)
        import helpers as H
        import threading
        obj.totals = tuple(H.TOTALS)
        obj.max_len = 10 ** 6
        obj._lock = threading.Lock()
        obj.fits = lambda preview: True
        obj._write = lambda preview, n=7, greedy_only=False: \
            programs[:1] if greedy_only else programs[:1 + n]
        return obj


def small_sheet():
    import sheets
    rows = [["Produit", "Prix"], ["Pain", "1,20"], ["Croissant", "1,10"],
            ["Tarte", "12,50"]]
    return sheets.Sheet("Tarifs", rows)


GOOD = ("target('products')\nheader(1)\nout.name = text(col('A'))\n"
        "out.price = amount(col('B'))")
BAD = ("target('products')\nheader(1)\nout.name = text(col('B'))\n"
       "out.price = amount(col('A'))")


def test_loop_greedy_import_and_refusal_is_final():
    t = FakeTulip([GOOD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR")
    assert r["status"] == "imported" and len(r["rows"]) == 3
    assert r["rows"][2] == {"name": "Tarte", "price": 12.5}
    t = FakeTulip(["refuse('not_a_table')", GOOD, GOOD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR")
    assert r["status"] == "refused" and r["reason"] == "not_a_table"


def test_loop_takes_first_sampled_candidate_that_passes():
    t = FakeTulip([BAD, "garbage (", BAD, GOOD, BAD, BAD, BAD, BAD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR")
    assert r["status"] == "imported" and r["candidates_tried"] == 4


def test_loop_refuses_with_majority_else_needs_review():
    ref = "refuse('no_matching_target')"
    t = FakeTulip([BAD, ref, ref, ref, ref, BAD, BAD, BAD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR")
    assert r["status"] == "refused" and r["reason"] == "no_matching_target"
    t = FakeTulip([BAD, ref, BAD, BAD, BAD, BAD, BAD, BAD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR")
    assert r["status"] == "needs_review"


def test_import_sheets_database_and_reimport():
    import import_sheets as I
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        I.create_tables(db)
        t = FakeTulip([GOOD])
        result = t._import_sheet(small_sheet(), ["products"], "fr-FR")
        result["file"] = "tarifs.xlsx"
        I.store(db, result, "sha-1", "tulip-pilot", 3)
        rows = db.execute('SELECT name, price, _row FROM "tulip_products" '
                          'ORDER BY _row').fetchall()
        assert rows == [("Pain", 1.2, 2), ("Croissant", 1.1, 3),
                        ("Tarte", 12.5, 4)]
        # a changed file replaces the sheet's rows
        I.store(db, result, "sha-2", "tulip-pilot", 3)
        n = db.execute('SELECT COUNT(*) FROM "tulip_products"').fetchone()[0]
        assert n == 3
        prev = I.previous(db, "tarifs.xlsx", "Tarifs")
        assert prev[1] == "sha-2" and prev[3] == "tulip-pilot"
        db.close()


def test_evaluation_summary_counts():
    import evaluate as E
    per = [{"refusal_task": False, "imported": True, "loop_ok": True,
            "pass1": True, "status": "imported", "target_ok": True,
            "false_accept": False, "invented": 0, "lang": "fr",
            "answer": "products", "traps": ["T4"], "greedy_cpu": 1.0,
            "loop_cpu": 1.0},
           {"refusal_task": False, "imported": True, "loop_ok": False,
            "pass1": False, "status": "imported", "target_ok": True,
            "false_accept": True, "invented": 0, "lang": "fr",
            "answer": "products", "traps": [], "greedy_cpu": 2.0,
            "loop_cpu": 3.0},
           {"refusal_task": True, "imported": False, "loop_ok": True,
            "pass1": True, "status": "refused", "target_ok": None,
            "false_accept": False, "invented": 0, "lang": "ja",
            "answer": "not_a_table", "traps": [], "greedy_cpu": 1.0,
            "loop_cpu": 1.0}]
    s = E.summarize(per)
    assert s["false_accept_share"] == 0.5
    assert s["refusal_precision"] == 1.0 and s["refusal_recall"] == 1.0
    assert s["loop_importable"] == 0.5 and s["loop_by_trap"] == {"T4": 1.0}
    assert json.dumps(s)
