"""
Item E of the Tulip 1.1 work order: a re-imported sheet updates its rows
by key instead of replacing them; every change is kept in tulip_history;
removals are marked, never deleted; an unchanged file changes nothing.
"""
import json
import pathlib
import sqlite3
import tempfile

import import_sheets as I
import sheets
from test_pipeline import GOOD, FakeTulip

V1 = [["Produit", "Prix"], ["Pain", "1,20"], ["Croissant", "1,10"],
      ["Tarte", "12,50"]]
# croissant 1.10 -> 1.20, the tarte is gone, an eclair is new
V2 = [["Produit", "Prix"], ["Pain", "1,20"], ["Croissant", "1,20"],
      ["Éclair", "2,50"]]


def imported(rows, program=GOOD, name="Tarifs", file="tarifs.xlsx",
             target="products"):
    t = FakeTulip([program])
    r = t._import_sheet(sheets.Sheet(name, rows), [target], "fr-FR")
    assert r["status"] == "imported", r
    r["file"] = file
    return r


def new_db(tmp):
    db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
    I.create_tables(db)
    return db


def history(db):
    return [r for r in db.execute(
        "SELECT target, key, change, field, old, new, row, at FROM "
        "tulip_history ORDER BY id")]


def table(db, target="products"):
    return [r for r in db.execute(
        'SELECT rowid, name, price, _row, _removed FROM "tulip_%s" ORDER BY '
        'rowid' % target)]


def test_an_edited_price_list_gives_exactly_its_differences():
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        r1 = imported(V1)
        I.store(db, r1, "sha1", "tulip-1.0.0", 3, now="2026-03-01T08:00:00")
        assert r1["changes"] == {"added": 3, "changed": 0, "removed": 0,
                                 "same": 0}
        first = table(db)
        r2 = imported(V2)
        I.store(db, r2, "sha2", "tulip-1.0.0", 3, now="2026-03-03T09:12:00")
        assert r2["changes"] == {"added": 1, "changed": 1, "removed": 1,
                                 "same": 1}
        assert history(db)[3:] == [
            ("products", "croissant|", "changed", "price", "1.1", "1.2", 3,
             "2026-03-03T09:12:00"),
            ("products", "eclair|", "added", None, None, None, 4,
             "2026-03-03T09:12:00"),
            ("products", "tarte|", "removed", None, None, None, 4,
             "2026-03-03T09:12:00")]
        rows = table(db)
        # nothing deleted: the tarte is still there, marked removed; the
        # croissant is the same row, updated in place
        assert len(rows) == 4
        assert rows[:3] == [
            (first[0][0], "Pain", 1.2, 2, None),
            (first[1][0], "Croissant", 1.2, 3, None),
            (first[2][0], "Tarte", 12.5, 4, "2026-03-03T09:12:00")]
        assert rows[3][1:] == ("Éclair", 2.5, 4, None)
        db.close()


def test_an_unchanged_file_changes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        folder = pathlib.Path(tmp) / "docs"
        folder.mkdir()
        (folder / "tarifs.csv").write_text(
            "\n".join(";".join(r) for r in V1), encoding="utf-8")
        db = new_db(tmp)
        t = FakeTulip([GOOD])
        path = folder / "tarifs.csv"

        def dump():
            out = []
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE "
                                      "type = 'table' ORDER BY name"):
                out.append((name, db.execute(
                    'SELECT * FROM "%s"' % name).fetchall()))
            return out
        counts = I.import_path(db, t, path, ["products"], "fr-FR",
                               "tulip-1.0.0", {}, False, False)
        assert counts == {"imported": 1}
        before = dump()
        counts = I.import_path(db, t, path, ["products"], "fr-FR",
                               "tulip-1.0.0", {}, False, False)
        assert counts == {"unchanged": 1}
        assert dump() == before
        db.close()


def test_a_failed_reimport_keeps_the_rows():
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(V1), "sha1", "tulip-1.0.0", 3)
        before, logged = table(db), history(db)
        failed = FakeTulip(["out.x = ("] * 8)._import_sheet(
            sheets.Sheet("Tarifs", V2), ["products"], "fr-FR")
        failed["file"] = "tarifs.xlsx"
        assert failed["status"] == "needs_review"
        I.store(db, failed, "sha2", "tulip-1.0.0", 3)
        assert table(db) == before and history(db) == logged
        assert db.execute("SELECT COUNT(*) FROM tulip_imports").fetchone() \
            == (2,)
        db.close()


def test_a_sheet_that_moves_to_another_table():
    services = GOOD.replace("products", "services")
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(V1), "sha1", "tulip-1.0.0", 3)
        r = imported(V1, services, target="services")
        I.store(db, r, "sha2", "tulip-1.0.0", 3, now="2026-03-04T10:00:00")
        assert r["changes"]["added"] == 3
        assert r["changes"]["removed_from_other_table"] == 3
        assert [x[4] for x in table(db)] == ["2026-03-04T10:00:00"] * 3
        assert [x[4] for x in table(db, "services")] == [None] * 3
        assert [h[2] for h in history(db)] == ["added"] * 3 + \
            ["removed"] * 3 + ["added"] * 3
        db.close()


def test_rows_are_paired_by_sku_when_every_row_has_one():
    """A renamed product that keeps its SKU is changed, not removed and
    added."""
    program = ("target('products')\nheader(1)\nout.sku = text(col('A'))\n"
               "out.name = text(col('B'))\nout.price = amount(col('C'))")
    v1 = [["Réf", "Produit", "Prix"], ["P1", "Pain", "1,20"],
          ["P2", "Croissant", "1,10"]]
    v2 = [["Réf", "Produit", "Prix"], ["P1", "Pain de campagne", "1,20"],
          ["P2", "Croissant", "1,10"]]
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(v1, program), "sha1", "tulip-1.0.0", 2)
        r = imported(v2, program)
        I.store(db, r, "sha2", "tulip-1.0.0", 2)
        assert r["changes"] == {"added": 0, "changed": 1, "removed": 0,
                                "same": 1}
        assert history(db)[-1][1:6] == ("p 1", "changed", "name",
                                         '"Pain"', '"Pain de campagne"')
        db.close()


def test_rows_with_the_same_key_pair_in_their_order():
    v1 = [["Produit", "Prix"], ["Café", "1,50"], ["Café", "2,50"]]
    v2 = [["Produit", "Prix"], ["Café", "1,50"], ["Café", "2,80"]]
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(v1), "sha1", "tulip-1.0.0", 2)
        r = imported(v2)
        I.store(db, r, "sha2", "tulip-1.0.0", 2)
        assert r["changes"] == {"added": 0, "changed": 1, "removed": 0,
                                "same": 1}
        assert history(db)[-1][1:6] == ("cafe|#2", "changed", "price",
                                         "2.5", "2.8")
        db.close()


def test_opening_hours_pair_by_day_and_rank():
    program = ("target('opening_hours')\nheader(1)\n"
               "out.day = weekday(col('A'))\nout.hours = hours(col('B'))")
    v1 = [["Jour", "Horaires"], ["lundi", "9h-12h / 14h-19h"],
          ["mardi", "9h-19h"]]
    v2 = [["Jour", "Horaires"], ["lundi", "8h30-12h"], ["mardi", "9h-19h"]]
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(v1, program, target="opening_hours"), "sha1",
                "tulip-1.0.0", 2)
        r = imported(v2, program, target="opening_hours")
        I.store(db, r, "sha2", "tulip-1.0.0", 2)
        assert r["changes"] == {"added": 0, "changed": 1, "removed": 1,
                                "same": 1}
        got = [h[1:6] for h in history(db)[3:]]
        assert got == [("monday|1", "changed", "opens", '"09:00"',
                        '"08:30"'),
                       ("monday|2", "removed", None, None, None)]
        db.close()


def test_a_table_made_before_the_history_gets_its_columns():
    """A Tulip 1.1 table made before item E (no _key, _removed) gets the
    two columns in place; its rows stay."""
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(str(pathlib.Path(tmp) / "documents.db"))
        import contract
        cols = ", ".join('"%s" %s' % (c["name"], contract.sql_type(c))
                         for c in contract.columns("products"))
        db.execute('CREATE TABLE "tulip_products" (%s, _file TEXT, _sheet '
                   'TEXT, _row INTEGER, _sources TEXT, _import_id INTEGER)'
                   % cols)
        db.execute('INSERT INTO "tulip_products" (name, price, _file, '
                   '_sheet, _row) VALUES ("Pain", 1.2, "t.xlsx", "T", 2)')
        db.commit()
        I.create_tables(db)
        names = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        assert not [n for n in names if "before" in n], names
        assert I.table_columns(db, "tulip_products")[-2:] == ["_key",
                                                              "_removed"]
        assert db.execute('SELECT name, _removed FROM "tulip_products"'
                          ).fetchall() == [("Pain", None)]
        db.close()


def test_the_history_values_are_json():
    with tempfile.TemporaryDirectory() as tmp:
        db = new_db(tmp)
        I.store(db, imported(V1), "sha1", "tulip-1.0.0", 3)
        I.store(db, imported(V2), "sha2", "tulip-1.0.0", 3)
        for old, new in db.execute("SELECT old, new FROM tulip_history"):
            for v in (old, new):
                assert v is None or json.loads(v) is not None
        db.close()
