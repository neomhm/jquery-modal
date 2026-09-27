"""
Section 5 of the Tulip 1.1 work order: REPORT.md compares Tulip 1.1 with
Tulip 1 on the SAME held-out sets. The evaluation splits are drawn from
(split, index) seeds; tests/data/tulip1_tasks.json holds the sha1 of the
tasks Tulip 1's generator (the base tree, generator 1.1.0) drew for a
sample of every evaluation split. The generator must still draw them
byte for byte: what Tulip 1.1 adds (new files, layouts, tables) only
goes into the training split and into new splits of its own.
"""
import hashlib
import json
import pathlib

from gen import tasks as T

HERE = pathlib.Path(__file__).resolve().parent


def test_the_evaluation_splits_are_tulip_1s():
    want = json.loads((HERE / "data" / "tulip1_tasks.json").read_text(
        encoding="utf-8"))
    assert len(want) == 96
    for key, sha in sorted(want.items()):
        split, index = key.rsplit("-", 1)
        task, _ = T.make_task(split, int(index))
        blob = json.dumps(task, sort_keys=True, ensure_ascii=False,
                          default=str)
        assert hashlib.sha1(blob.encode("utf-8")).hexdigest() == sha, key


def test_the_report_compares_with_tulip_1():
    """REPORT.md's comparison takes Tulip 1's eval.json from the data
    upload - never the run's own, never another Tulip 1.1 eval.json - and
    shows both on the same splits and on the unchanged handwritten set."""
    import json
    import tempfile
    import report
    saved = (report.HERE, report.config.runs_dir)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        try:
            report.HERE = tmp
            report.config.runs_dir = lambda p: tmp / "runs" / p
            (tmp / "runs" / "tiny").mkdir(parents=True)
            (tmp / "data").mkdir()
            new = {"preset": "tiny", "model": "best.pt", "confidence": {},
                   "splits": {"test_heldout": {"tasks": 50, "pass1": 0.6,
                                               "loop": 0.7}},
                   "handwritten": {"sheets": 32, "loop": 0.5}}
            (tmp / "runs" / "tiny" / "eval.json").write_text(json.dumps(new))
            # another Tulip 1.1 eval.json in the upload is not Tulip 1's
            (tmp / "data" / "a_newer_eval.json").write_text(json.dumps(new))
            lines = report.compare_section("tiny", new)
            assert "was not given to this run" in " ".join(lines)
            old = {"preset": "tiny", "model": "best.pt",
                   "splits": {"test_heldout": {"tasks": 50, "pass1": 0.5,
                                               "loop": 0.65}},
                   "handwritten": {"sheets": 32, "loop": 0.25}}
            (tmp / "data" / "tulip1_eval.json").write_text(json.dumps(old))
            text = "\n".join(report.compare_section("tiny", new))
            assert "`tulip1_eval.json`" in text
            assert "| test_heldout | pass@1 | 0.6000 | 0.5000 | +0.1000 |" \
                in text, text
            assert "| test_heldout | loop | 0.7000 | 0.6500 | +0.0500 |" \
                in text, text
            assert "| handwritten (32 sheets) | loop | 0.5000 | 0.2500 | " \
                "+0.2500 |" in text, text
            # another preset's Tulip 1 file is not this preset's
            assert "was not given" in " ".join(
                report.compare_section("full", dict(new, preset="full")))
        finally:
            report.HERE, report.config.runs_dir = saved
