"""
Item C of the Tulip 1.1 work order: every column an import maps gets a
band - sure, check or unsure - from the model's probability of the line
that maps it, the agreement of the 8 candidate programs and the
runtime's checks. The thresholds are calibrated per model on held-out
tasks; a model with no calibration never says "sure".
"""
import json
import math
import pathlib
import random
import sqlite3
import tempfile

import torch

import confidence as C
import model as M
import tulipscript as ts
from test_pipeline import BAD, GOOD, FakeTulip, small_sheet

SERVICES = ("target('services')\nheader(1)\nout.name = text(col('A'))\n"
            "out.price = amount(col('B'))")


# ---------------------------------------------------------- the signals
def test_token_logprobs_are_the_full_pass_scores():
    """Teacher forcing: the score of program token i is read at the
    position before it (the classic off-by-one)."""
    torch.manual_seed(0)
    net = M.Tulip(M.Config(120, 32, 2, 4, 64, max_len=64)).eval()
    prompt = [5, 17, 33, 2]
    program = [40, 41, 99, 7, 3]
    got = C.token_logprobs(net, prompt, program)
    with torch.no_grad():
        logp = torch.log_softmax(net(torch.tensor([prompt + program]))[0],
                                 -1)
    want = [logp[len(prompt) - 1 + i, t].item()
            for i, t in enumerate(program)]
    assert len(got) == len(program)
    assert all(abs(a - b) < 1e-4 for a, b in zip(got, want)), (got, want)


def tiny_tokenizer():
    import tok as TK
    texts = [GOOD, BAD, SERVICES, "Produit | Prix"] * 3
    return TK.train_tokenizer(texts, 300)


def test_each_token_belongs_to_its_statement():
    """A doubtful token in the price line lowers the price line only."""
    tokenizer = tiny_tokenizer()
    enc = tokenizer.encode(GOOD, add_special_tokens=False)
    at = GOOD.index("col('B')") + len("col('")        # the letter B
    lps = [math.log(0.5) if a <= at < b else 0.0 for a, b in enc.offsets]
    assert sum(1 for x in lps if x) == 1
    got = C.line_probabilities(tokenizer, GOOD, lps)
    assert abs(got["fields"]["price"][0] - 0.5) < 1e-9
    assert abs(got["fields"]["price"][1] - 0.5) < 1e-9
    assert got["fields"]["name"] == (1.0, 1.0)
    assert got["structure"] == (1.0, 1.0)
    # and a doubtful header row lowers the structure only
    at = GOOD.index("header(1)") + len("header(")
    lps = [math.log(0.25) if a <= at < b else 0.0 for a, b in enc.offsets]
    got = C.line_probabilities(tokenizer, GOOD, lps)
    assert abs(got["structure"][1] - 0.25) < 1e-9
    assert got["fields"]["price"] == (1.0, 1.0)


def test_agreement_counts_same_target_and_same_expression():
    same = GOOD.replace("text(col('A'))", "text( col( 'A' ) )")
    candidates = [GOOD, same, BAD, "refuse('not_a_table')", "out.x = (",
                  SERVICES]
    got = C.agreement(GOOD, candidates)
    # GOOD and its respelling agree; BAD maps other columns; the services
    # program has the same expressions for another table
    assert got == {"name": 2 / 6.0, "price": 2 / 6.0}, got


def test_unreadable_share_comes_from_the_runtime():
    res = ts.Result(rows=[{"name": "a", "price": 1.0},
                          {"name": "b", "price": None},
                          {"name": "c", "price": 2.0}],
                    warnings=["parse_failures:price:1", "helper_raised:x"])
    assert C.unreadable_shares(res) == {"price": 1 / 3.0}


def test_score_uses_all_three_signals():
    """The model's probability of the line, the agreement of the
    candidates and the runtime's checks each lower the score; the
    program's structure (version 1) no longer does."""
    base = {"line_p": 0.99, "line_min_p": 0.99, "structure_p": 0.99,
            "structure_min_p": 0.99, "agreement": 1.0, "unreadable": 0.0,
            "filled": 1.0}
    top = C.score(base)
    for key, worse in (("line_min_p", 0.5), ("agreement", 0.5),
                       ("unreadable", 0.2)):
        assert C.score(dict(base, **{key: worse})) < top, key
    assert C.score(dict(base, structure_min_p=0.2)) == top
    assert 0.0 <= C.score(dict(base, agreement=0.0)) <= top <= 1.0


def test_without_calibration_never_sure():
    assert C.band(1.0, None) == "check"
    assert C.band(0.1, None) == "unsure"
    bands = {"sure": 0.9, "check": 0.5}
    assert [C.band(x, bands) for x in (0.95, 0.9, 0.6, 0.1)] == \
        ["sure", "sure", "check", "unsure"]


# ---------------------------------------------------------- calibration
def synthetic(n, seed):
    """Columns whose chance of being right rises with the score: 50% at
    0, 98% at 0.8, 100% at 1."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        s = rng.random()
        out.append((round(s, 4), rng.random() < 1 - 0.5 * (1 - s) ** 2))
    return out


def test_calibration_holds_on_new_columns():
    fit, new = synthetic(20000, 1), synthetic(20000, 2)
    bands = C.calibrate(fit)
    assert bands and 0 < bands["check"] <= bands["sure"] < 1
    fitted = C.measure(fit, bands)["sure"]
    assert fitted["low95"] >= C.SURE_PRECISION, fitted
    measured = C.measure(new, bands)
    assert measured["sure"]["rate"] >= C.SURE_PRECISION, measured
    assert measured["sure"]["columns"] > 1000
    assert measured["check"]["rate"] >= 0.8
    assert measured["unsure"]["rate"] < 0.8
    # nothing reaches 99%: no "sure" at all
    assert C.calibrate([(s, i % 10 != 0) for i, (s, _) in
                        enumerate(fit)]) is None


def test_calibrate_py_fits_on_even_and_measures_on_odd():
    import calibrate
    per = [{"id": "dev_heldout-%06d" % i,
            "confidence": [{"score": s, "right": ok}]}
           for i, (s, ok) in enumerate(synthetic(20000, 3))]
    bands, rates = calibrate.fit_and_measure(per)
    fit_n = sum(m["columns"] for m in rates["fit"].values())
    new_n = sum(m["columns"] for m in rates["measured"].values())
    assert fit_n == new_n == 10000
    assert rates["measured"]["sure"]["rate"] >= C.SURE_PRECISION


# ---------------------------------------------------------- the import
def gap_sheet():
    """Column B is empty: compact() removes it, so the program's B is the
    sheet's C."""
    import sheets
    return sheets.Sheet("Tarifs", [
        ["Produit", None, "Prix"], ["Pain", None, "1,20"],
        ["Croissant", None, "1,10"], ["Tarte", None, "12,50"]])


class Counting:
    """A FakeTulip that counts the sampled writes."""

    def __new__(cls, programs):
        t = FakeTulip(programs)
        write = t._write
        t.sampled_calls = []

        def counted(preview, n=7, greedy_only=False, sampled_only=False):
            if sampled_only:
                t.sampled_calls.append(n)
            return write(preview, n, greedy_only, sampled_only)
        t._write = counted
        return t


def test_import_gives_each_mapped_column_a_band():
    programs = [GOOD] * 5 + [BAD, SERVICES, "refuse('not_a_table')"]
    t = Counting(programs)
    plain = t._import_sheet(gap_sheet(), ["products"], "fr-FR")
    assert t.sampled_calls == [] and plain["confidence"] is None
    r = t._import_sheet(gap_sheet(), ["products"], "fr-FR",
                        confidence=True)
    assert t.sampled_calls == [7]           # the greedy program won
    for key in ("status", "rows", "program", "sources", "row_numbers",
                "candidates_tried"):
        assert r[key] == plain[key], key    # the import does not change
    conf = r["confidence"]
    assert conf["calibrated"] is False and conf["candidates"] == 8
    cols = dict((c["column"], c) for c in conf["columns"])
    assert list(cols) == ["name", "price"]
    assert cols["name"]["sheet_columns"] == ["A"]
    assert cols["price"]["sheet_columns"] == ["C"]     # the sheet's own
    assert cols["name"]["signals"]["agreement"] == 5 / 8.0
    assert all(c["band"] in ("check", "unsure") for c in cols.values())
    # with a calibration: the columns the candidates agree on are sure
    t = FakeTulip([GOOD] * 8)
    t.bands = {"sure": 0.9, "check": 0.3}
    r = t._import_sheet(gap_sheet(), ["products"], "fr-FR",
                        confidence=True)
    assert [c["band"] for c in r["confidence"]["columns"]] == \
        ["sure", "sure"]
    assert r["confidence"]["calibrated"] is True


def test_a_sampled_winner_uses_the_loops_own_candidates():
    t = Counting(["out.x = (", BAD, GOOD, GOOD, BAD, GOOD, GOOD, GOOD])
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR",
                        confidence=True)
    assert r["status"] == "imported" and r["candidates_tried"] == 3
    assert t.sampled_calls == [7]           # written once, by the loop
    cols = dict((c["column"], c) for c in r["confidence"]["columns"])
    assert cols["price"]["signals"]["agreement"] == 5 / 8.0


def test_opening_hours_columns_share_the_hours_band():
    import sheets
    hours = ("target('opening_hours')\nheader(1)\n"
             "out.day = weekday(col('A'))\nout.hours = hours(col('B'))")
    sheet = sheets.Sheet("Horaires", [["Jour", "Horaires"],
                                      ["lundi", "9h-12h / 14h-19h"],
                                      ["dimanche", "Fermé"]])
    t = FakeTulip([hours] * 8)
    r = t._import_sheet(sheet, ["opening_hours"], "fr-FR", confidence=True)
    cols = r["confidence"]["columns"]
    assert [c["column"] for c in cols] == ["day", "opens", "closes",
                                          "closed"]
    assert len(set((c["score"], c["band"]) for c in cols[1:])) == 1
    assert all(c["field"] == "hours" and c["sheet_columns"] == ["B"]
               for c in cols[1:])


def test_the_band_reaches_tulip_imports_and_the_preview():
    import import_sheets as I
    t = FakeTulip([GOOD] * 8)
    r = t._import_sheet(gap_sheet(), ["products"], "fr-FR",
                        confidence=True)
    r["file"] = "tarifs.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        I.create_tables(db)
        I.store(db, r, "sha", "tulip-1.0.0", 3)
        stored = json.loads(db.execute(
            "SELECT confidence FROM tulip_imports").fetchone()[0])
        db.close()
    assert stored == json.loads(json.dumps(r["confidence"]))
    lines = I.confidence_lines(r)
    assert any("column C -> price: check" in x for x in lines), lines
    assert "not calibrated" in lines[0]


def test_a_calibration_file_is_used_for_its_own_model_only():
    with tempfile.TemporaryDirectory() as tmp:
        model = pathlib.Path(tmp) / "tulip-1.0.0.pt"
        model.write_bytes(b"weights")
        side = C.side_file(model)
        assert side.name == "tulip-1.0.0.confidence.json"
        bands = {"sure": 0.8, "check": 0.4,
                 "score_version": C.SCORE_VERSION,
                 "model_sha256": C.file_sha256(model)}
        side.write_text(json.dumps(bands), encoding="utf-8")
        assert C.load_bands(model)["sure"] == 0.8
        model.write_bytes(b"other weights")          # another model
        assert C.load_bands(model) is None
        meta = {"confidence": {"sure": 0.7, "check": 0.3,
                               "score_version": C.SCORE_VERSION}}
        assert C.load_bands(model, meta)["sure"] == 0.7
        meta["confidence"]["score_version"] = C.SCORE_VERSION + 1
        assert C.load_bands(model, meta) is None     # another score


# ---------------------------------------------------------- the labels
def test_a_column_is_right_when_its_values_are_the_truths():
    task = {"answer": "products", "program": GOOD, "locale": "fr-FR",
            "targets": ["products"]}
    t = FakeTulip([GOOD] * 8)
    r = t._import_sheet(small_sheet(), ["products"], "fr-FR",
                        confidence=True)
    assert C.field_rights(task, r, small_sheet()) == {"name": True,
                                                      "price": True}
    r["rows"][1] = dict(r["rows"][1], price=9.99)
    assert C.field_rights(task, r, small_sheet()) == {"name": True,
                                                      "price": False}
    r["rows"].pop(1)                    # a missed row is not the column's
    r["row_numbers"].pop(1)
    assert C.field_rights(task, r, small_sheet())["price"] is True
    wrong = dict(task, answer="services")
    assert C.field_rights(wrong, r, small_sheet()) == {"name": False,
                                                       "price": False}


def test_the_evaluation_records_the_bands_signals():
    import evaluate as E
    from gen import tasks as T
    task = None
    for i in range(50):
        task, _ = T.make_task("val", 93000 + i)
        if task and task["answer"] == "products":
            break
    t = FakeTulip([task["program"]] * 8)
    per = E.evaluate_split(t, "val", [task], False, lambda *a: None,
                           confidence=True)
    rec = per[0]
    assert rec["loop_ok"] and rec["confidence"]
    assert all(c["right"] for c in rec["confidence"])
    assert all(0 <= c["score"] <= 1 for c in rec["confidence"])
    plain = E.evaluate_split(t, "val", [task], False, lambda *a: None)
    assert "confidence" not in plain[0]


def test_the_build_calibrates_and_the_model_file_carries_it():
    """evaluate.run() fits the bands on dev_heldout and measures them on
    test_heldout (with --dev-only: even and odd dev_heldout tasks);
    build.py writes them into the model file's meta, where Tulip reads
    them."""
    import build
    import evaluate as E
    from tulip import Tulip
    dev = [(s, ok, i) for i, (s, ok) in enumerate(synthetic(8000, 4))]
    test = [(s, ok, i) for i, (s, ok) in enumerate(synthetic(4000, 5))]
    ev = {"confidence": E.confidence_result(
        {"dev_heldout": dev, "test_heldout": test}, False)}
    conf = ev["confidence"]
    assert conf["bands"] and conf["measured_on"].startswith("test_heldout")
    assert sum(m["columns"] for m in conf["measured"].values()) == 4000
    dev_only = E.confidence_result({"dev_heldout": dev}, True)
    assert "odd tasks (%d" % (len(dev) // 2) in dev_only["measured_on"]
    meta = {"confidence": build.model_bands(ev)}
    assert meta["confidence"]["sure"] == conf["bands"]["sure"]
    torch.manual_seed(0)
    net = M.Tulip(M.Config(60, 32, 1, 2, 64, max_len=64)).eval()
    t = Tulip.from_model(net, tiny_tokenizer(), meta)
    assert t.bands and t.bands["sure"] == conf["bands"]["sure"]
    assert build.model_bands({"confidence": {"bands": None}}) is None
    assert Tulip.from_model(net, tiny_tokenizer(), {}).bands is None
    lines = E.confidence_lines(conf)
    assert any(x.startswith("| sure |") for x in lines)


def test_a_model_that_imports_nothing_says_why_it_has_no_bands():
    """A split that was scored but gave no column (a model that imported
    none of its tables: the tiny rehearsal) is not "not scored"."""
    import evaluate as E
    none = E.confidence_result({}, False)
    assert none["bands"] is None and none["why"] == "dev_heldout was not scored"
    empty = E.confidence_result({"dev_heldout": [], "test_heldout": []}, False)
    assert empty["bands"] is None
    assert empty["why"] == "no column of dev_heldout was imported"
    assert "no column of dev_heldout was imported" in \
        " ".join(E.confidence_lines(empty))
