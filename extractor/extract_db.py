"""
extract_db.py - runs the Extractor over every chunk of documents.db
(section 16).

    py extract_db.py "C:\\Users\\Laurent\\new model\\documents.db"

Options:
    --model PATH   the model file (default: extractor-1.0.0.pt, else
                   extractor-pilot.pt, next to this script)
    --redo         delete this model's rows first and do everything again
    --threads N    CPU threads (default 4)

What it does:
  * adds the tables `extractions` and `chunk_meta` (IF NOT EXISTS);
  * deletes this model's rows whose chunk no longer exists;
  * processes every chunk that has no chunk_meta row for this model, or
    whose text changed since (sha1 of the text) - ingest.py can reuse a
    chunk id after a file changes, so the hash matters;
  * writes each batch of 16 chunks in one transaction;
  * checks every span with verify.py and prints a summary.
The model id stored in the rows is the model file's stem
('extractor-1.0.0', 'extractor-pilot'), so two models never mix.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

import verify

HERE = pathlib.Path(__file__).resolve().parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY,
    chunk_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    label TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    text TEXT NOT NULL,
    score REAL NOT NULL,
    status TEXT NOT NULL,
    normalized TEXT,
    reason TEXT,
    created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS extractions_chunk ON extractions(chunk_id);
CREATE TABLE IF NOT EXISTS chunk_meta (
    chunk_id INTEGER NOT NULL, model TEXT NOT NULL,
    text_sha1 TEXT NOT NULL,
    language TEXT, language_score REAL, doc_type TEXT, doc_type_score REAL,
    doc_type_probs TEXT,
    created TEXT NOT NULL,
    PRIMARY KEY (chunk_id, model));
"""


def default_model():
    for name in ("extractor-1.0.0.pt", "extractor-pilot.pt"):
        path = HERE / name
        if path.exists():
            return path
    return None


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def sha1(text):
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def ensure_tables(db):
    db.executescript(SCHEMA)


def process(db, extractor, model_id, redo=False, batch_size=16, log=print):
    """Extracts, verifies and stores. -> summary dict."""
    ensure_tables(db)
    with db:
        if redo:
            db.execute("DELETE FROM extractions WHERE model = ?",
                       (model_id,))
            db.execute("DELETE FROM chunk_meta WHERE model = ?", (model_id,))
        # rows of chunks that no longer exist
        db.execute("DELETE FROM extractions WHERE model = ? AND chunk_id "
                   "NOT IN (SELECT id FROM chunks)", (model_id,))
        db.execute("DELETE FROM chunk_meta WHERE model = ? AND chunk_id "
                   "NOT IN (SELECT id FROM chunks)", (model_id,))
    done = {cid: h for cid, h in db.execute(
        "SELECT chunk_id, text_sha1 FROM chunk_meta WHERE model = ?",
        (model_id,))}
    todo = [(cid, text) for cid, text in db.execute(
        "SELECT id, text FROM chunks ORDER BY id")
        if done.get(cid) != sha1(text)]
    summary = {"chunks": len(todo), "spans": {}, "languages": {},
               "doc_types": {}}
    for k in range(0, len(todo), batch_size):
        group = todo[k:k + batch_size]
        results = extractor.extract([text or "" for _, text in group],
                                    batch_size=batch_size)
        stamp = now()
        with db:                             # one transaction per batch
            for (cid, text), res in zip(group, results):
                text = text or ""
                db.execute("DELETE FROM extractions WHERE model = ? AND "
                           "chunk_id = ?", (model_id, cid))
                db.execute(
                    "INSERT OR REPLACE INTO chunk_meta VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cid, model_id, sha1(text), res["language"],
                     res["language_score"], res["doc_type"],
                     res["doc_type_score"],
                     json.dumps(res["doc_type_probs"]), stamp))
                lang = res["language"]
                summary["languages"][lang] = \
                    summary["languages"].get(lang, 0) + 1
                summary["doc_types"][res["doc_type"]] = \
                    summary["doc_types"].get(res["doc_type"], 0) + 1
                for span in res["spans"]:
                    checked = verify.verify_span(span, text, lang)
                    db.execute(
                        "INSERT INTO extractions (chunk_id, model, label, "
                        "start_char, end_char, text, score, status, "
                        "normalized, reason, created) VALUES "
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (cid, model_id, span["label"], span["start"],
                         span["end"], span["text"], span["score"],
                         checked["status"],
                         json.dumps(checked["normalized"],
                                    ensure_ascii=False),
                         checked["reason"], stamp))
                    st = checked["status"]
                    summary["spans"][st] = summary["spans"].get(st, 0) + 1
    return summary


def main():
    ap = argparse.ArgumentParser(description="Extract facts into "
                                             "documents.db")
    ap.add_argument("db")
    ap.add_argument("--model")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    path = pathlib.Path(args.model) if args.model else default_model()
    if path is None or not path.exists():
        print("No model file found. Put extractor-1.0.0.pt (or "
              "extractor-pilot.pt) next to extract_db.py, or use --model.")
        return 1
    from extractor import Extractor
    ex = Extractor(path, threads=args.threads)
    db = sqlite3.connect(args.db)
    model_id = path.stem
    summary = process(db, ex, model_id, redo=args.redo)
    print("model %s: %d chunks processed" % (model_id, summary["chunks"]))
    print("spans by status:", json.dumps(summary["spans"]))
    print("languages:", json.dumps(summary["languages"]))
    print("document types:", json.dumps(summary["doc_types"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())


def build_folder_db(chunks, path=":memory:"):
    """A documents.db with ingest.py's exact schema, made from the chunk
    records of one generated folder (files.path = the file name).
    The two CREATE statements are those of ingest.database().
    -> (connection, {chunk record id: chunks.id})."""
    db = sqlite3.connect(str(path))
    for statement in ("""CREATE TABLE IF NOT EXISTS files (
                          id INTEGER PRIMARY KEY, path TEXT UNIQUE,
                          kind TEXT, bytes INTEGER, modified REAL,
                          added TEXT)""",
                      """CREATE TABLE IF NOT EXISTS chunks (
                          id INTEGER PRIMARY KEY, file_id INTEGER,
                          page INTEGER, ordinal INTEGER, kind TEXT,
                          text TEXT)"""):
        db.execute(statement)
    file_ids, chunk_ids = {}, {}
    with db:
        for c in chunks:
            if c["file_name"] not in file_ids:
                cur = db.execute(
                    "INSERT INTO files (path, kind, bytes, modified, added) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (c["file_name"], c["source"], len(c["text"]), 0.0,
                     "synthetic"))
                file_ids[c["file_name"]] = cur.lastrowid
            cur = db.execute(
                "INSERT INTO chunks (file_id, page, ordinal, kind, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (file_ids[c["file_name"]], c["page"], c["ordinal"],
                 c["chunk_kind"], c["text"]))
            chunk_ids[c["id"]] = cur.lastrowid
    return db, chunk_ids
