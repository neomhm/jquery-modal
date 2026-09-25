"""extractor.py (the API of section 13) and extract_db.py (section 16),
with a tiny untrained model made here: the tests check the contract -
formats, empty texts, spans that are slices of the text, thread safety,
the database bookkeeping - not the quality of a model."""
import pathlib
import sqlite3
import tempfile
import threading

import torch

import config
import extract_db
import model as M
import tok as T
from extractor import Extractor

TEXTS = ["Boulangerie Martin SARL, 12 rue des Alpes, 01210 Ferney-Voltaire. "
         "Tél. 04 50 12 34 56. Total TTC : 2 220,00 €",
         "株式会社サクラ商事 〒100-0005 東京都千代田区丸の内1-2-3 設立 1998年",
         "Invoice INV-001 dated 15/03/2024 - Total due $1,240.00"]


def tiny_model(folder):
    tokenizer = T.train_tokenizer(TEXTS * 20, 400)
    cfg = M.Config(vocab_size=tokenizer.get_vocab_size(), d_model=32,
                   n_layer=1, n_head=2, ffn_hidden=64, max_len=64,
                   dropout=0.0, n_labels=len(config.LABELS),
                   n_doc_types=len(config.DOC_TYPES),
                   n_langs=len(config.LANGS))
    torch.manual_seed(0)
    net = M.Extractor(cfg)
    path = pathlib.Path(folder) / "extractor-test.pt"
    M.save(path, net, tokenizer.to_str(),
           {"version": config.VERSION, "labels": config.LABELS,
            "doc_types": config.DOC_TYPES, "langs": config.LANGS,
            "temperature": 1.0, "max_len": 64,
            "thresholds": {t: 0.0 for t in config.TYPES}})
    return path


def test_api_format():
    with tempfile.TemporaryDirectory() as tmp:
        ex = Extractor(tiny_model(tmp), threads=1)
        assert ex.version == config.VERSION
        assert ex.labels == config.LABELS
        assert ex.doc_types == config.DOC_TYPES
        assert ex.languages == config.LANGS
        out = ex.extract(TEXTS + ["", "   \n "], batch_size=2)
        assert len(out) == len(TEXTS) + 2
        for text, r in zip(TEXTS, out):
            assert r["language"] in config.LANGS
            assert r["doc_type"] in config.DOC_TYPES
            assert len(r["doc_type_probs"]) == 11
            assert abs(sum(r["doc_type_probs"]) - 1) < 0.01
            for s in r["spans"]:
                assert s["label"] in config.TYPES
                assert text[s["start"]:s["end"]] == s["text"]
                assert s["text"] == s["text"].strip()
                assert isinstance(s["accepted"], bool)
        for r in out[-2:]:
            assert r == {"language": None, "language_score": None,
                         "doc_type": None, "doc_type_score": None,
                         "doc_type_probs": None, "spans": []}


def test_long_text_and_determinism():
    with tempfile.TemporaryDirectory() as tmp:
        ex = Extractor(tiny_model(tmp))
        long_text = " ".join(TEXTS * 8)             # > max_len tokens
        a = ex.extract([long_text])[0]
        b = ex.extract([long_text])[0]
        assert a == b
        for s in a["spans"]:
            assert long_text[s["start"]:s["end"]] == s["text"]


def test_threads_share_one_extractor():
    with tempfile.TemporaryDirectory() as tmp:
        ex = Extractor(tiny_model(tmp))
        want = ex.extract(TEXTS)
        results, errors = [], []

        def work():
            try:
                results.append(ex.extract(TEXTS))
            except Exception as exc:              # pragma: no cover
                errors.append(exc)
        threads = [threading.Thread(target=work) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors and all(r == want for r in results)


def test_extract_db_bookkeeping():
    with tempfile.TemporaryDirectory() as tmp:
        ex = Extractor(tiny_model(tmp))
        chunks = [{"id": "c%d" % k, "file_name": "f%d.pdf" % (k // 2),
                   "source": "pdf", "page": 1, "ordinal": k,
                   "chunk_kind": "text", "text": text}
                  for k, text in enumerate(TEXTS)]
        db_path = pathlib.Path(tmp) / "documents.db"
        db, ids = extract_db.build_folder_db(chunks, db_path)
        s1 = extract_db.process(db, ex, "extractor-test")
        assert s1["chunks"] == 3
        n_meta = db.execute("SELECT COUNT(*) FROM chunk_meta").fetchone()[0]
        assert n_meta == 3
        # nothing changed: nothing to do
        assert extract_db.process(db, ex, "extractor-test")["chunks"] == 0
        # a chunk's text changes (ingest.py reused the id): redone
        with db:
            db.execute("UPDATE chunks SET text = ? WHERE id = ?",
                       ("Nouvelle facture - Total 10,00 €", ids["c0"]))
        assert extract_db.process(db, ex, "extractor-test")["chunks"] == 1
        # a chunk disappears: its rows go
        with db:
            db.execute("DELETE FROM chunks WHERE id = ?", (ids["c1"],))
        extract_db.process(db, ex, "extractor-test")
        left = db.execute("SELECT COUNT(*) FROM chunk_meta WHERE chunk_id "
                          "= ?", (ids["c1"],)).fetchone()[0]
        assert left == 0
        # every stored span is a slice of its chunk; statuses are known
        for cid, s, e, text, status in db.execute(
                "SELECT e.chunk_id, start_char, end_char, e.text, status "
                "FROM extractions e"):
            chunk = db.execute("SELECT text FROM chunks WHERE id = ?",
                               (cid,)).fetchone()[0]
            assert chunk[s:e] == text
            assert status in ("verified", "format_warning",
                              "low_confidence", "rejected")
            assert status != "rejected"
        # --redo starts again for this model only
        s2 = extract_db.process(db, ex, "extractor-test", redo=True)
        assert s2["chunks"] == 2
        db.close()
        sqlite3.connect(str(db_path)).close()
