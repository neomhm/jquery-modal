"""
history.py - a re-imported sheet UPDATES its rows instead of replacing
them, and every change is kept (Tulip 1.1, item E).

When a changed file is imported again, each sheet's new rows are paired
with its current rows by the table's key (keys.match_keys: a product by
its SKU, else its barcode, else its name and variant; an opening range by
its day and rank; ...):

  * a new key         -> the row is added             (history: added)
  * a key in both     -> the row is updated in place when a value changed
                         (history: one "changed" row per changed column,
                         with the old and the new value); only its sheet
                         row and sources are updated when nothing changed
  * a key that is gone -> the row is MARKED removed (_removed = when),
                         never deleted              (history: removed)

    croissant | price | 1.1 -> 1.2 | 2026-03-03T09:12:00 | tarifs.xlsx row 12

A sheet that is now refused or needs review keeps its current rows (a
failed import says nothing about the business). A sheet imported into
another table than before has its rows marked removed in the old one.
An unchanged file is not imported again at all (import_sheets.unchanged),
so it changes nothing.

Tables (made by import_sheets.create_tables):
    tulip_<target>: _key (the key the row was paired by) and _removed
    tulip_history:  id, target, file, sheet, key, change, field, old, new
                    (JSON), row (the sheet row), import_id, row_id (the
                    row's rowid in tulip_<target>), at
"""
import json

import contract
import keys

HISTORY_TABLE = """CREATE TABLE IF NOT EXISTS tulip_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, file TEXT,
    sheet TEXT, key TEXT, change TEXT, field TEXT, old TEXT, new TEXT,
    row INTEGER, import_id INTEGER, row_id INTEGER, at TEXT)"""


def to_sql(column, value):
    if value is None:
        return None
    if column["format"] == "boolean":
        return 1 if value else 0
    return value


def from_sql(column, value):
    """A stored value back in its declared format (booleans are 0 / 1 in
    SQLite)."""
    if value is None:
        return None
    if column["format"] == "boolean":
        return bool(value)
    return value


def current_rows(db, target, file, sheet):
    """-> [(rowid, {column: value}, sheet row)] of the sheet's rows that
    are not removed, in sheet order."""
    cols = contract.columns(target)
    names = ", ".join('"%s"' % c["name"] for c in cols)
    out = []
    for r in db.execute(
            'SELECT rowid, %s, _row FROM "tulip_%s" WHERE _file = ? AND '
            '_sheet = ? AND _removed IS NULL ORDER BY _row, rowid'
            % (names, target), (file, sheet)):
        values = dict((c["name"], from_sql(c, v))
                      for c, v in zip(cols, r[1:-1]) if v is not None)
        out.append((r[0], values, r[-1]))
    return out


def _log(db, target, file, sheet, key, change, field, old, new, row,
         import_id, row_id, at):
    db.execute("INSERT INTO tulip_history (target, file, sheet, key, change, "
               "field, old, new, row, import_id, row_id, at) VALUES "
               "(?,?,?,?,?,?,?,?,?,?,?,?)",
               (target, file, sheet, key, change, field,
                None if old is None else json.dumps(old, ensure_ascii=False),
                None if new is None else json.dumps(new, ensure_ascii=False),
                row, import_id, row_id, at))


def _mark_removed(db, target, rowid, at):
    """A removed row stays, marked with when it was removed."""
    db.execute('UPDATE "tulip_%s" SET _removed = ? WHERE rowid = ?'
               % target, (at, rowid))


def remove_all(db, target, file, sheet, import_id, at):
    """Mark every current row of the sheet in tulip_<target> removed
    (the sheet now goes to another table). -> how many."""
    old = current_rows(db, target, file, sheet)
    _, old_keys, _ = keys.match_keys(target, [v for _, v, _ in old], [])
    for (rowid, _, row), key in zip(old, old_keys):
        _mark_removed(db, target, rowid, at)
        _log(db, target, file, sheet, key, "removed", None, None, None, row,
             import_id, rowid, at)
    return len(old)


def apply(db, target, file, sheet, rows, sources, numbers, import_id, at):
    """The sheet's new rows (in the declared format) against its current
    rows in tulip_<target>. -> {"added", "changed", "removed", "same"}."""
    cols = contract.columns(target)
    names = [c["name"] for c in cols]
    old = current_rows(db, target, file, sheet)
    _, old_keys, new_keys = keys.match_keys(
        target, [v for _, v, _ in old], rows)
    by_key = dict((k, o) for k, o in zip(old_keys, old))
    counts = {"added": 0, "changed": 0, "removed": 0, "same": 0}
    insert = 'INSERT INTO "tulip_%s" (%s, _file, _sheet, _row, _sources, ' \
        '_import_id, _key, _removed) VALUES (%s)' % (
            target, ", ".join('"%s"' % n for n in names),
            ", ".join("?" * (len(names) + 7)))
    seen = set()
    for record, srcs, row, key in zip(rows, sources, numbers, new_keys):
        values = [to_sql(c, record.get(c["name"])) for c in cols]
        src = json.dumps(srcs, default=str)
        if key not in by_key:
            cur = db.execute(insert, values + [file, sheet, row, src,
                                               import_id, key, None])
            _log(db, target, file, sheet, key, "added", None, None, None, row,
                 import_id, cur.lastrowid, at)
            counts["added"] += 1
            continue
        seen.add(key)
        rowid, before, _ = by_key[key]
        changed = [c for c in cols
                   if before.get(c["name"]) != record.get(c["name"])]
        db.execute('UPDATE "tulip_%s" SET %s, _row = ?, _sources = ?, '
                   '_import_id = ?, _key = ? WHERE rowid = ?' % (
                       target, ", ".join('"%s" = ?' % n for n in names)),
                   values + [row, src, import_id, key, rowid])
        for c in changed:
            _log(db, target, file, sheet, key, "changed", c["name"],
                 before.get(c["name"]), record.get(c["name"]), row,
                 import_id, rowid, at)
        counts["changed" if changed else "same"] += 1
    for key, (rowid, before, row) in zip(old_keys, old):
        if key in seen:
            continue
        _mark_removed(db, target, rowid, at)
        _log(db, target, file, sheet, key, "removed", None, None, None, row,
             import_id, rowid, at)
        counts["removed"] += 1
    return counts
