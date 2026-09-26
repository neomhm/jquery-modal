"""
Item D of the Tulip 1.1 work order: the owner's corrections are kept in
tulip_corrections, and the exporter turns them into lessons in the
generator's task format that pass the generator's self-check with the
real runtime. Done when a correction round-trips.
"""
import json
import pathlib
import sqlite3
import tempfile

import corrections as R
import evaluate as E
import import_sheets as I
from gen import tasks as T
from test_pipeline import FakeTulip

# Tulip read the price without tax (B); the owner wants the one with (C)
WRONG = ("target('products')\nheader(1)\nout.name = text(col('A'))\n"
         "out.price = amount(col('B'))")
LINES = ["Produit;Prix HT;Prix TTC", "Pain;1,00;1,20", "Croissant;0,92;1,10",
         "Tarte;10,42;12,50"]
TASK_KEYS = {"id", "split", "lang", "locale", "activity", "family", "traps",
             "targets", "answer", "format", "sheet", "preview", "program",
             "truth", "holdout", "n_rows"}


def setup(tmp, program=WRONG, lines=LINES):
    folder = pathlib.Path(tmp) / "docs"
    folder.mkdir()
    path = folder / "tarifs.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
    I.create_tables(db)
    I.import_path(db, FakeTulip([program] * 8), path, ["products"],
                  "fr-FR", "tulip-1.0.0", {}, False, False, folder)
    import_id = db.execute("SELECT MAX(id) FROM tulip_imports").fetchone()[0]
    return db, import_id


def lessons_of(path):
    return [json.loads(x) for x in pathlib.Path(path).read_text(
        encoding="utf-8").splitlines() if x.strip()]


def test_a_remapped_column_round_trips_into_a_lesson():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        cid = R.record(db, import_id, "remap", mapping={"price": "C"},
                       shared=True)
        row = db.execute("SELECT kind, program, corrected_program, checked, "
                         "preview FROM tulip_corrections WHERE id = ?",
                         (cid,)).fetchone()
        assert row[0] == "remap" and row[1] == WRONG
        assert row[2] == WRONG.replace("col('B')", "col('C')")
        assert row[3] == 1 and row[4].startswith("TARGETS")
        out = pathlib.Path(tmp) / "lessons.jsonl"
        counts = R.export(db, out, forbidden=set())
        assert counts["lessons"] == 1 and not counts["rejected"], counts
        lesson = lessons_of(out)[0]
        assert set(lesson) == TASK_KEYS          # the generator's format
        assert lesson["truth"] == [{"name": "Pain", "price": 1.2},
                                   {"name": "Croissant", "price": 1.1},
                                   {"name": "Tarte", "price": 12.5}]
        # the generator's self-check with the real runtime, and the
        # evaluation's own reading of a task
        assert R.lesson_problems(lesson) == []
        assert E.pass_at_1(lesson, lesson["program"],
                           T.sheet_from_task(lesson))
        # and the self-check does catch a lesson that is not right
        bad = json.loads(json.dumps(lesson))
        bad["truth"][0]["price"] = 9.99
        assert "self_check:truth" in R.lesson_problems(bad)
        bad = dict(lesson, program=lesson["program"].replace(" = ", "  =  "))
        assert "not_canonical" in R.lesson_problems(bad)
        bad = dict(lesson, preview=lesson["preview"] + " ")
        assert "preview_differs" in R.lesson_problems(bad)
        bad = dict(lesson, program=WRONG)
        assert "self_check:truth" in R.lesson_problems(bad)
        db.close()


def test_a_refused_sheet_is_unrefused_with_a_mapping():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp, "refuse('not_a_table')")
        assert db.execute("SELECT status FROM tulip_imports WHERE id = ?",
                          (import_id,)).fetchone() == ("refused",)
        R.record(db, import_id, "unrefuse", target="products", header=1,
                 mapping={"name": "A", "price": "C"}, shared=True)
        out = pathlib.Path(tmp) / "lessons.jsonl"
        assert R.export(db, out, forbidden=set())["lessons"] == 1
        lesson = lessons_of(out)[0]
        assert lesson["answer"] == "products"
        assert lesson["program"] == WRONG.replace("col('B')", "col('C')")
        assert R.lesson_problems(lesson) == []
        db.close()


def test_an_import_that_should_have_been_refused():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        R.record(db, import_id, "refuse", reason="not_a_table", shared=True)
        out = pathlib.Path(tmp) / "lessons.jsonl"
        assert R.export(db, out, forbidden=set())["lessons"] == 1
        lesson = lessons_of(out)[0]
        assert lesson["answer"] == "not_a_table" and lesson["truth"] == []
        assert R.lesson_problems(lesson) == []
        db.close()


def test_the_owner_names_the_sheets_own_letters():
    """Column B is empty: the program reads the compacted sheet, where the
    sheet's D is C."""
    lines = ["Produit;;Prix HT;Prix TTC", "Pain;;1,00;1,20",
             "Croissant;;0,92;1,10"]
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp, WRONG, lines)
        cid = R.record(db, import_id, "remap", mapping={"price": "D"})
        got = db.execute("SELECT corrected_program, checked FROM "
                         "tulip_corrections WHERE id = ?", (cid,)).fetchone()
        assert got == (WRONG.replace("col('B')", "col('C')"), 1)
        db.close()


def test_corrections_stay_on_the_pc_unless_shared():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        cid = R.record(db, import_id, "remap", mapping={"price": "C"})
        out = pathlib.Path(tmp) / "lessons.jsonl"
        counts = R.export(db, out, forbidden=set())
        assert counts["lessons"] == 0 and counts["private"] == 1
        assert lessons_of(out) == []
        assert R.export(db, out, include_private=True,
                        forbidden=set())["lessons"] == 1
        R.share(db, cid)
        assert R.export(db, out, forbidden=set())["lessons"] == 1
        db.close()


def test_a_correction_the_runtime_rejects_is_never_a_lesson():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        # the names are no prices: every price cell fails to read
        cid = R.record(db, import_id, "remap", mapping={"price": "A"},
                       shared=True)
        checked, problems = db.execute(
            "SELECT checked, problems FROM tulip_corrections WHERE id = ?",
            (cid,)).fetchone()
        assert checked == 0 and json.loads(problems)
        counts = R.export(db, pathlib.Path(tmp) / "l.jsonl", forbidden=set())
        assert counts["lessons"] == 0
        assert counts["rejected"][0][0] == cid
        db.close()


def test_an_evaluation_sheet_is_never_a_lesson():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        R.record(db, import_id, "remap", mapping={"price": "C"}, shared=True)
        import sheets
        small, _ = sheets.compact(sheets.load(
            pathlib.Path(tmp) / "docs" / "tarifs.csv")[0])
        counts = R.export(db, pathlib.Path(tmp) / "l.jsonl",
                          forbidden={R.rows_hash(small.rows)})
        assert counts["lessons"] == 0
        assert counts["rejected"][0][1] == ["evaluation_sheet"]
        db.close()
    # the handwritten set is among the evaluation sheets
    hashes = R.evaluation_hashes(presets=[])
    assert len(hashes) >= 30


def test_a_fixed_value_is_a_case_for_the_cell_readers():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        R.record(db, import_id, "value",
                 value={"row": 3, "column": "price", "new": 1.1},
                 shared=True)
        out = pathlib.Path(tmp) / "lessons.jsonl"
        counts = R.export(db, out, forbidden=set())
        assert counts["values"] == 1 and counts["lessons"] == 0
        case = lessons_of(out.with_suffix(".values.jsonl"))[0]
        assert case == {"id": case["id"], "helper": "amount",
                        "locale": "fr-FR", "cell": "0,92", "expected": 1.1,
                        "column": "price", "row": 3}
        db.close()


def test_a_changed_file_is_not_corrected_blindly():
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        path = pathlib.Path(tmp) / "docs" / "tarifs.csv"
        path.write_text(path.read_text(encoding="utf-8") + "Éclair;2;2,40\n",
                        encoding="utf-8")
        try:
            R.record(db, import_id, "remap", mapping={"price": "C"})
            raise AssertionError("recorded against a changed file")
        except ValueError as e:
            assert "changed since this import" in str(e)
        db.close()


def test_exported_lessons_join_the_next_training_round():
    """gen/make.py adds the lessons it finds (a lessons/ folder, or the
    /train card's data upload) to the training split, each checked again;
    a lesson that fails the self-check or is an evaluation sheet is left
    out."""
    import gzip
    import sheets
    from gen import make
    with tempfile.TemporaryDirectory() as tmp:
        db, import_id = setup(tmp)
        R.record(db, import_id, "remap", mapping={"price": "C"}, shared=True)
        out = pathlib.Path(tmp) / "lessons.jsonl"
        assert R.export(db, out, forbidden=set())["lessons"] == 1
        good = lessons_of(out)[0]
        bad = json.loads(json.dumps(good))
        bad["id"] = "correction-000002"
        bad["truth"][0]["price"] = 9.99            # fails the self-check
        other = dict(good, id="correction-000003")
        other["sheet"] = dict(good["sheet"], rows=good["sheet"]["rows"] +
                              [[{"t": "s", "v": "Brioche"},
                                {"t": "s", "v": "4,00"},
                                {"t": "s", "v": "4,80"}]])
        other["preview"] = sheets.preview(T.sheet_from_task(other),
                                          other["targets"], other["locale"])
        other["truth"] = good["truth"] + [{"name": "Brioche", "price": 4.8}]
        other["n_rows"] = 4
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(bad) + "\n" + json.dumps(other) + "\n")
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        train = data / "train.jsonl.gz"
        with gzip.open(train, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"id": "train-000000"}) + "\n")
        saved = (make.lesson_files, make.config.data_dir,
                 R.evaluation_hashes)
        make.lesson_files = lambda: [out]
        make.config.data_dir = lambda preset: data
        # the good lesson's sheet is an evaluation sheet this time
        R.evaluation_hashes = lambda presets=None: {
            R.rows_hash(T.sheet_from_task(good).rows)}
        try:
            got = make.add_lessons("tiny", lambda *a: None)
        finally:
            (make.lesson_files, make.config.data_dir,
             R.evaluation_hashes) = saved
        assert got["files"] == 1 and got["lessons"] == 1, got
        assert got["rejected"] == {"self_check": 1, "evaluation_sheet": 1}
        with gzip.open(train, "rt", encoding="utf-8") as f:
            ids = [json.loads(x)["id"] for x in f if x.strip()]
        assert ids == ["train-000000", "correction-000003"]
        db.close()
