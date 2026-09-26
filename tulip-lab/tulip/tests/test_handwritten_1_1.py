"""
Tulip 1.1's handwritten set (handwritten_1_1/): 13 real files of the new
kinds and layouts - PDFs written by another program (reportlab, with its
own embedded fonts: Latin, Arabic, Cyrillic, Chinese), .xls, .ods, two
sheets of several tables, several days in one cell - in eight languages.
Their truth was written by hand. The files are frozen (sha256 below and
in DECISIONS.md), and every truth line is still given by its canonical
program (programs.json) through the real readers and the real runtime:
the readers read these files right.
"""
import hashlib
import json
import pathlib

import blocks
import evaluate as E
import helpers as H
import sheets
import tulipscript as ts

HERE = pathlib.Path(__file__).resolve().parent.parent / "handwritten_1_1"
FROZEN = {
    "hw11-ar-hours.xlsx":
        "e5805072cde12fec878813a73cc46c435b49c8e58e2a10cb9334670d40c3c12e",
    "hw11-ar-services.pdf":
        "e042f1a8139d8cd5319b889062e1f1501fe1c59501991c59e93cc10b03449f25",
    "hw11-en-hours.xlsx":
        "5d9b5e7ac2b5c5bea936cbd470a0958b753e81f137131dd05a9e48f75503e3ae",
    "hw11-en-supplier.pdf":
        "245bf4935062d40f13a5375c9d6d2642602e373e1564c2773e8c9ae0d32f28b7",
    "hw11-es-clientes.xls":
        "70448befa5c6b5a404b6aa1c5e357f28775d9e30879c1920863d16749a93e711",
    "hw11-fr-boutique.xlsx":
        "7303d16150812196470921aa3fc9a00f639a8508ec3f93427a895f81a91bf9c2",
    "hw11-fr-tarifs.pdf":
        "3e36bd06980fbbbbc9fadeb9fb165e097fcfa6e8dac86730facdc62f40c3bf8c",
    "hw11-hi-bookings.ods":
        "d03e7a852ef503c41d2af69b3cca7bad90718b308ce5b1538e39d9f6950d7009",
    "hw11-it-listino.xls":
        "c809aaf98ccd9c5a7fbd66d0cc65fede7bcacd8e81d3526bdcfd83eb6e2b08e5",
    "hw11-ja-menu.ods":
        "837958bbd8560fff5cbae916509df8619a6b7be8862c8f10bb4e8baa8bd17ae8",
    "hw11-ko-cafe.csv":
        "9b4eb0524312a7d21d6679ac11e6031d340eeae65e8beacb9f015fab7d3710f7",
    "hw11-ru-staff.pdf":
        "f5ef3ed1b735464680a434858443b255fe467f5daf7d6b6453e9367b2f4f217b",
    "hw11-zh-hours.pdf":
        "4bb771159ab75550de9df68aafff8a8d7be89fad6a29c2778e6abd6555514e4f",
    "programs.json":
        "911e3ca40b2461f8b58286b7b2ba7eae642fbec8a8efd9523ab68290c52d1ea0",
    "truth.jsonl":
        "66b082517254ea7d122a5f0731cd835da718b89dd00922944eb8e716ef128ed1",
}


def test_the_set_is_frozen():
    got = dict((p.name, hashlib.sha256(p.read_bytes()).hexdigest())
               for p in sorted(HERE.iterdir()) if p.is_file())
    assert got == FROZEN


def test_every_truth_is_read_from_its_file():
    lines = [json.loads(x) for x in (HERE / "truth.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]
    programs = json.loads((HERE / "programs.json").read_text(
        encoding="utf-8"))
    assert len(lines) == 15
    kinds = set()
    for item in lines:
        path = HERE / item["file"]
        kinds.add(path.suffix)
        parts = [p for s in sheets.load(path, item["locale"])
                 for p in blocks.split(s)]
        found = [p for p in parts if p.name == item["sheet"]]
        assert found, (item["file"], item["sheet"], [p.name for p in parts])
        small, _ = sheets.compact(found[0])
        prog = ts.parse(programs["%s|%s" % (item["file"], item["sheet"])])
        res = ts.run(prog, small, H.HELPERS, item["locale"],
                     item["targets"], H.TOTALS)
        assert not res.problems, (item["file"], res.problems)
        assert E.clean(res.rows) == E.clean(item["truth"]), item["file"]
    assert kinds == {".pdf", ".xls", ".ods", ".xlsx", ".csv"}
