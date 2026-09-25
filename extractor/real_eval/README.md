# real_eval - your own labelled chunks

This folder is empty on purpose. Put here chunks of **real** documents
that you labelled yourself: they are the truest test of the Extractor.

## Format

One `.jsonl` file per batch (for example `real_eval\2026-10-fr.jsonl`),
one JSON object per line - the same format as `handwritten\`:

```json
{"id": "real-fr-01", "lang": "fr", "doc_type": "invoice", "text": "…", "spans": [{"label": "S_NAME", "value": "Plomberie Dubois", "occurrence": 1}]}
```

* `id`: any unique name.
* `lang`: one of `ar zh en fr ru es it hi ja ko`.
* `doc_type`: one of `invoice quote brochure registration financials
  price_list staff_list contract letter terms other`.
* `text`: the chunk exactly as `ingest.py` stored it (copy it from
  `py ingest.py show`, or from the `chunks` table of `documents.db`).
* `spans`: every fact, with its label (the 25 types of section 5 of the
  build instructions, repeated in `gen\data\BRIEFING_FOR_WRITERS.md`), the
  exact `value` as written, and `occurrence` - which appearance of that
  value in the text is meant (1 = the first).

## Check a file

```powershell
py gold.py real_eval
```

It stops with a clear message when a value cannot be found in its text,
and warns about values that end with punctuation or appear again
unlabelled.

## Score the model on them

```powershell
py build.py full --from evaluate
```

The scores appear in `REPORT.md` and `runs\full\eval_tables.md`. The
chunks here are never used for training.
