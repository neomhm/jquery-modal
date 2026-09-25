# The Extractor

The Extractor reads the chunks that `ingest.py` made from a business's
documents and marks the facts in them: names, addresses, registration
numbers, phones, legal form, founding date, staff, revenue, services,
clients and more, in ten languages. It is a small encoder trained from
scratch; it never writes text, it only marks pieces of the chunk, so it
cannot invent a value. `profile.py` then turns those marks into one
business profile, with the source of every value.

## Step 1 - check the machine

On the desktop, open PowerShell in `C:\Users\neomh\new model\extractor`:

```powershell
cd "C:\Users\neomh\new model\extractor"
```

```powershell
py check.py
```

It prints the Python, torch and GPU it found, and the preset `build.py`
will choose (`full` with a GPU, `pilot` without). It never installs or
changes torch.

## Step 2 - build

On the desktop (GPU), in `C:\Users\neomh\new model\extractor`:

```powershell
py build.py full
```

On MEGA9: upload `extractor-package.zip` to the /train card and choose
MEGA9. The card runs `build.py`, which chooses `full` by itself when
there is a GPU.

On Linux:

```bash
python3 build.py full
```

The build downloads plain-text Wikipedia, generates the training data,
trains, calibrates, evaluates and writes `REPORT.md`. It takes about 6 to
10 hours on a GPU. If it stops, it says which stage failed; after fixing
it, run the same command again: finished stages are skipped. To redo one
stage and everything after it:

```powershell
py build.py full --from finetune
```

## Step 3 - keep the model file

The build writes `extractor-1.0.0.pt` next to `build.py`. Keep it: it is
the only file that cannot be rebuilt from code (everything else is in the
package). `extractor-pilot.pt`, delivered with this package, is a smaller
test model trained on a CPU.

## Step 4 - use it on a real folder (laptop)

Once, install what `ingest.py` needs to read PDF, Word and Excel files:

```powershell
py -m pip install pdfplumber python-docx openpyxl
```

Put `extractor-1.0.0.pt` (or `extractor-pilot.pt`) in
`C:\Users\Laurent\new model\extractor`. Then, in PowerShell:

```powershell
cd "C:\Users\Laurent\new model"
```

```powershell
py ingest.py "C:\Users\Laurent\documents to publish"
```

This makes `C:\Users\Laurent\new model\documents.db`. Then:

```powershell
cd "C:\Users\Laurent\new model\extractor"
```

```powershell
py extract_db.py "C:\Users\Laurent\new model\documents.db"
```

```powershell
py profile.py "C:\Users\Laurent\new model\documents.db"
```

`profile.py` prints the profile as a table and writes
`C:\Users\Laurent\new model\profile.json`, plus the tables `profile` and
`profile_summary` in `documents.db`. When files change, run the three
commands again: only the new or changed chunks are extracted.

To use the pilot model while the full one is not built yet:

```powershell
py extract_db.py "C:\Users\Laurent\new model\documents.db" --model "C:\Users\Laurent\new model\extractor\extractor-pilot.pt"
```

## How `plan.py` calls it

```python
import threading, torch
from extractor import Extractor
torch.set_num_threads(8)                 # once per process; shared by every model in it
extractor = Extractor(r"C:\Users\Laurent\new model\extractor\extractor-1.0.0.pt")
extractor_lock = threading.Lock()        # one lock per model, so Daisy can work at the same time
with extractor_lock:
    results = extractor.extract(list_of_chunk_texts, batch_size=16)
```

Each result is a dict: `language`, `doc_type`, their scores, the eleven
document-type probabilities, and `spans` (label, start, end, text, score,
accepted). See the top of `extractor.py`.

## Adding your own labelled chunks (`real_eval/`)

Real documents are the best test. Put chunks you labelled yourself in
`real_eval\*.jsonl`, one JSON object per line, like the hand-written gold
set in `handwritten\`:

```json
{"id": "real-fr-01", "lang": "fr", "doc_type": "invoice", "text": "…", "spans": [{"label": "S_NAME", "value": "Plomberie Dubois", "occurrence": 1}]}
```

`occurrence` says which appearance of the value in the text is meant (1
is the first). Check a file before using it:

```powershell
py gold.py real_eval
```

The next build (or `py build.py full --from evaluate`) scores them and
adds them to `REPORT.md`. The labelling rules are in section 5 of the
build instructions and are repeated in `gen\data\BRIEFING_FOR_WRITERS.md`.

## What is in this folder

* `build.py` - the one command; `check.py` - the machine check
* `gen\` - the synthetic data generator (`gen\data\` holds every word
  list and sentence, per language)
* `tok.py`, `model.py`, `decode.py`, `chunker.py`, `ingest.py` - the
  tokenizer, the network, the decoder, the chunker (copied from the build
  instructions)
* `corpus.py`, `pack.py`, `pretrain.py`, `finetune.py`, `calibrate.py`,
  `evaluate.py`, `report.py` - the build stages
* `extractor.py`, `extract_db.py`, `verify.py`, `normalize.py`,
  `profile.py` - what you use
* `tests\` - `py tests\run_all.py`
* `REPORT.md`, `DECISIONS.md`, `MODEL_CARD.md` - what was built, why,
  and how well it works
