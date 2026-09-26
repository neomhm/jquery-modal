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
