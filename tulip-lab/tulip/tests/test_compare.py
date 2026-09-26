"""
Item B of the Tulip 1.1 work order: after a folder's imports, rows that
describe the same thing across sheets and files are grouped; duplicates
and contradictions are reported once each, as questions with every value
and its cells; the preferred source follows the stated rule; nothing is
merged or dropped.
"""
import datetime
import json
import os
import pathlib
import sqlite3
import tempfile

import compare as C
import import_sheets as I
from test_pipeline import FakeTulip

PROGRAM = ("target('products')\nheader(2)\nout.name = text(col('A'))\n"
           "out.price = amount(col('B'))")

# the messy example: three menus and two price lists that disagree
MESSY = {
    "menus/carte-ete.csv": ("Carte été 2025", "2025-06-01 09:00", [
        ("Croissant", "1,10"), ("Pain au chocolat", "1,30"),
        ("Tarte citron", "3,50"), ("Tarte citron", "3,80")]),
    "menus/carte-hiver.csv": ("Carte hiver 2025", "2025-12-01 09:00", [
        ("Croissant", "1,20"), ("Pain au chocolat", "1,30"),
        ("Chocolat chaud", "3,00")]),
    "menus/menu-brunch.csv": ("Menu brunch", "2026-01-10 09:00", [
        ("Chocolat chaud", "3,20"), ("Jus d'orange", "3,50")]),
    "tarifs.csv": ("Tarifs au 01/03/2026", "2026-03-01 10:00", [
        ("CROISSANT", "1,25"), ("Pain au chocolat", "1,30"),
        ("BAGUETTE 0,25 kg", "1,20")]),
    "fournisseurs/grossiste.csv": ("Tarifs au 01/03/2026",
                                   "2026-03-01 10:00", [
                                       ("Baguette 250 g", "0,40")]),
}


def write_messy(root):
    for name, (title, mtime, rows) in MESSY.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [title, "Produit;Prix"] + ["%s;%s" % r for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        stamp = datetime.datetime.strptime(mtime, "%Y-%m-%d %H:%M")
        os.utime(path, (stamp.timestamp(), stamp.timestamp()))


def import_messy(tmp):
    root = pathlib.Path(tmp) / "documents to publish"
    write_messy(root)
    db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
    I.create_tables(db)
    t = FakeTulip([PROGRAM])
    counts = {}
    for path in sorted(root.rglob("*.csv")):
        counts = I.import_path(db, t, path, ["products"], "fr-FR",
                               "tulip-1.0.0", counts, False, False, root)
    assert counts == {"imported": 5}, counts
    return db


def dump(db, table):
    return db.execute('SELECT * FROM "%s" ORDER BY rowid' % table).fetchall()


def conflicts(db):
    out = {}
    for key, kind, columns, records, preferred, rule, question, status in \
            db.execute("SELECT key, kind, columns, records, preferred, rule, "
                       "question, status FROM tulip_conflicts ORDER BY id"):
        out[key] = {"kind": kind, "columns": json.loads(columns),
                    "records": json.loads(records),
                    "preferred": json.loads(preferred) if preferred
                    else None, "rule": rule, "question": question,
                    "status": status}
    return out


def test_the_messy_example():
    with tempfile.TemporaryDirectory() as tmp:
        db = import_messy(tmp)
        before = dump(db, "tulip_products")
        summary = C.run(db, now="2026-03-05T12:00:00")
        assert summary == {"duplicates": 1, "contradictions": 4, "new": 5,
                           "kept": 0, "gone": 0}, summary
        # nothing is merged, changed or dropped
        assert dump(db, "tulip_products") == before
        assert len(before) == 13
        got = conflicts(db)
        # each duplicated product once
        assert sorted(got) == ["baguette 250 g|", "chocolat chaud|",
                               "croissant|", "pain au chocolat|",
                               "tarte citron|"]
        croissant = got["croissant|"]
        assert croissant["kind"] == "contradiction"
        assert croissant["columns"] == ["price"]
        assert [(pathlib.Path(r["file"]).name, r["values"]["price"],
                 r["cells"]["price"]) for r in croissant["records"]] == [
            ("carte-ete.csv", 1.1, ["B3"]), ("carte-hiver.csv", 1.2, ["B3"]),
            ("tarifs.csv", 1.25, ["B3"])]
        # the newest document date: 01/03/2026 beats the two 2025 menus
        assert croissant["rule"] == "document_date"
        assert croissant["preferred"]["file"].endswith("tarifs.csv")
        assert "1.1 (carte-ete.csv" in croissant["question"] and \
            "cell B3" in croissant["question"]
        # a menu with no date: the newest file date decides
        choc = got["chocolat chaud|"]
        assert choc["rule"] == "file_date"
        assert choc["preferred"]["file"].endswith("menu-brunch.csv")
        # same document date, same file date: the business's own list
        # over the supplier's ("0,25 kg" and "250 g" are one product)
        baguette = got["baguette 250 g|"]
        assert baguette["rule"] == "business_over_supplier"
        assert baguette["preferred"]["file"].endswith("tarifs.csv")
        assert [r["origin"] for r in baguette["records"]] == \
            ["supplier", "business"]
        # the same values everywhere: a duplicate, still one question
        pac = got["pain au chocolat|"]
        assert pac["kind"] == "duplicate" and pac["columns"] == []
        assert len(pac["records"]) == 3
        # twice in one sheet, nothing tells them apart: the owner decides
        tarte = got["tarte citron|"]
        assert tarte["rule"] == "tie" and tarte["preferred"] is None
        assert "please choose" in tarte["question"]
        assert all(v["status"] == "open" for v in got.values())
        db.close()


def test_a_question_is_asked_once_and_follows_the_data():
    with tempfile.TemporaryDirectory() as tmp:
        db = import_messy(tmp)
        C.run(db, now="2026-03-05T12:00:00")
        db.execute("UPDATE tulip_conflicts SET status = 'answered', answer "
                   "= 'tarifs.csv' WHERE key = 'croissant|'")
        db.commit()
        again = C.run(db, now="2026-03-06T12:00:00")
        assert again == {"duplicates": 1, "contradictions": 4, "new": 0,
                         "kept": 5, "gone": 0}, again
        assert conflicts(db)["croissant|"]["status"] == "answered"
        # the brunch menu now agrees with the winter menu: its question
        # is gone (kept, marked) and a duplicate is asked instead
        root = pathlib.Path(tmp) / "documents to publish"
        path = root / "menus" / "menu-brunch.csv"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "3,20", "3,00"), encoding="utf-8")
        I.import_path(db, FakeTulip([PROGRAM]), path, ["products"], "fr-FR",
                      "tulip-1.0.0", {}, False, False, root)
        third = C.run(db, now="2026-03-07T12:00:00")
        assert third["gone"] == 1 and third["new"] == 1, third
        rows = db.execute("SELECT kind, status FROM tulip_conflicts WHERE "
                          "key = 'chocolat chaud|' ORDER BY id").fetchall()
        assert rows == [("contradiction", "gone"), ("duplicate", "open")]
        db.close()


def test_removed_rows_are_not_compared():
    with tempfile.TemporaryDirectory() as tmp:
        db = import_messy(tmp)
        root = pathlib.Path(tmp) / "documents to publish"
        path = root / "fournisseurs" / "grossiste.csv"
        path.write_text("Tarifs au 01/03/2026\nProduit;Prix\n"
                        "Farine T65;0,90\n", encoding="utf-8")
        I.import_path(db, FakeTulip([PROGRAM]), path, ["products"], "fr-FR",
                      "tulip-1.0.0", {}, False, False, root)
        C.run(db)
        # the supplier's baguette is marked removed: it is no source now
        assert "baguette 250 g|" not in conflicts(db)
        db.close()


def test_the_preferred_source_rule():
    def src(doc, file, origin="business"):
        return {"document_date": doc, "file_date": file, "origin": origin}
    a = src("2026-03-01", "2026-01-01T00:00:00")
    b = src("2026-02-01", "2026-06-01T00:00:00")
    assert C.prefer([a, b]) == (a, "document_date")
    # "2026" is level with "2026-03-01": the file date decides
    c = src("2026", "2026-06-01T00:00:00")
    assert C.prefer([a, c]) == (c, "file_date")
    # one source states no date: the file date decides
    d = src(None, "2026-07-01T00:00:00")
    assert C.prefer([a, d]) == (d, "file_date")
    # everything level: the business over the supplier
    e = src("2026-03-01", "2026-01-01T00:00:00", "supplier")
    assert C.prefer([e, a]) == (a, "business_over_supplier")
    # nothing tells them apart
    assert C.prefer([a, dict(a)]) == (None, "tie")
    assert C.prefer([e, dict(e)]) == (None, "tie")


def test_dates_and_origins_in_every_language():
    cases = [("Tarifs au 01/03/2026", "fr-FR", ["2026-03-01"]),
             ("Price list March 2026", "en-GB", ["2026-03"]),
             ("Прайс-лист от 15.02.2026", "ru-RU", ["2026-02-15"]),
             ("价目表 2026年3月", "zh-CN", ["2026-03"]),
             ("料金表 2026年3月1日", "ja-JP", ["2026-03-01"]),
             ("가격표 2026년 3월", "ko-KR", ["2026-03"]),
             ("قائمة الأسعار ٢٠٢٦", "ar-SA", ["2026"]),
             ("Listino prezzi 2026", "it-IT", ["2026"]),
             ("Lista de precios 01/03/2026", "es-ES", ["2026-03-01"]),
             ("मूल्य सूची 2026", "hi-IN", ["2026"])]
    for text, locale, want in cases:
        assert C.dates_in(text, locale) == want, (text, C.dates_in(text,
                                                                   locale))
    root = pathlib.Path("/docs")
    for folder in ("Fournisseurs", "suppliers", "Proveedores", "fornitori",
                   "Поставщики", "供应商", "仕入先", "공급업체", "الموردين",
                   "आपूर्तिकर्ता"):
        assert C.origin(root / folder / "a.csv", root) == "supplier", folder
    assert C.origin(root / "menus" / "a.csv", root) == "business"
    # the folder the owner chose is not looked at, only what is inside it
    assert C.origin(pathlib.Path("/suppliers/docs/a.csv"),
                    pathlib.Path("/suppliers/docs")) == "business"
