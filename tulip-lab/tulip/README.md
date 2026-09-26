# Tulip 1 — the Importer

Tulip reads a spreadsheet (`.xlsx` or `.csv`) and imports its rows into one
of seven tables of your back-end: products, services, opening hours, staff,
clients, bookings or the invoice ledger — or it refuses the sheet and says
why. A small model trained from scratch writes a short program
(TulipScript) that plain code checks and runs, so every imported value comes
from a cell of your sheet. It reads sheets in ten languages: Arabic, Chinese,
English, French, Russian, Spanish, Italian, Hindi, Japanese and Korean.

## Step 1 — check the machine

On the desktop (RTX 4080), open PowerShell in the Tulip folder:

```powershell
cd "C:\Users\neomh\new model\tulip"
```

```powershell
py check.py
```

It prints the machine's details, the measured speed, and the preset
`build.py` would choose. If it says torch is missing, install it first (the
build never installs or upgrades torch):

```powershell
py -m pip install torch --index-url https://download.pytorch.org/whl/cu128
```

## Step 2 — build the model

On the desktop:

```powershell
py build.py full
```

It generates the training data, trains the tokenizer and the model (about 3
hours on an RTX 4080, at most 6), evaluates it and writes `REPORT.md`. If it
stops, run the same command again: finished stages are skipped and training
resumes from its last checkpoint.

On MEGA9: upload `tulip-package.zip` to the /train card as the program,
no training data, the words `full`, and choose MEGA9. The run has no
network: nothing is installed, the small packages come from `vendor/`.
It shows each stage ("Stage 5/8: train") and the training percentage, and
sends back `tulip-1.0.0.pt`, `REPORT.md`, `runs/full/eval_tables.md`, the
`runs/full/*.json` records and `runs/full/build.log`. The model file is
written as soon as training ends, and again with the evaluation numbers.
To check the plumbing first (a few minutes, a useless model), use the
words `tiny`.

On Linux:

```bash
python3 build.py full
```

## Step 3 — keep the model file

The build writes `tulip-1.0.0.pt` next to `build.py`. That one file is the
model: weights, tokenizer and settings. Keep it; `REPORT.md` says how good
it is.

## Step 4 — import a real folder

On the laptop, with the model file in `C:\Users\Laurent\new model\tulip`:

```powershell
cd "C:\Users\Laurent\new model\tulip"
```

```powershell
py import_sheets.py "C:\Users\Laurent\documents to publish" --db "C:\Users\Laurent\new model\documents.db" --targets products,services,opening_hours --locale fr-FR
```

Then look at what it did, sheet by sheet (status, program, and the first 5
rows next to their row numbers):

```powershell
py import_sheets.py "C:\Users\Laurent\documents to publish" --db "C:\Users\Laurent\new model\documents.db" --targets products --locale fr-FR --show
```

The rows go into the tables `tulip_products`, `tulip_services`… of
`documents.db`, and one line per sheet into `tulip_imports` (status, reason,
program, problems). Sheets already imported from an unchanged file are
skipped; a changed file replaces its earlier rows.

Every column has ONE declared format, written in `tables.schema.json`
(see "Reading Tulip's output" below). A `documents.db` made by Tulip 1
is migrated the first time: its tables with the old columns are renamed
`tulip_<table>_before_0_4_draft_tulip_1_1` (nothing is deleted) and every
sheet is imported again in the new format.

## The plan.py snippet

```python
import threading, torch
from tulip import Tulip
torch.set_num_threads(8)                    # once per process; shared by every model in it
tulip = Tulip(r"C:\Users\Laurent\new model\tulip\tulip-1.0.0.pt")
tulip_lock = threading.Lock()               # one lock per model
with tulip_lock:
    results = tulip.import_file(path, targets=["products", "services"], locale="fr-FR")
```

Each result says `imported`, `imported_with_warnings`, `refused` (with a
reason) or `needs_review`, with the rows and the cells each value came from.

## Reading Tulip's output

`tables.schema.json` declares every column of every table: its format,
its SQLite type, whether it is required, and the allowed values. Tulip's
rows follow it exactly (a value that would not is sent to review, never
written), so a reader needs no special case per column:

| format | a value looks like | SQLite |
|---|---|---|
| `day` | `"monday"` … `"sunday"` (lower-case English) | TEXT |
| `time` | `"09:00"`, `"19:30"` (24-hour `HH:MM`) | TEXT |
| `boolean` | `true` / `false` | INTEGER 1 / 0 |
| `percent` | `5.5` for 5.5 % (a VAT rate) | REAL |
| `decimal` | `12.5` (money never carries its currency) | REAL |
| `currency` | `"EUR"` (ISO 4217) | TEXT |
| `date` | `"2026-03-03"` (ISO 8601) | TEXT |
| `minutes`, `integer` | `45`, `12` | INTEGER |
| `email`, `phone` | `"marie@example.fr"`, `"+33612345678"` (E.164) | TEXT |
| `text`, `enum` | NFKC text, single spaces; an enum one of its values | TEXT |

`opening_hours` has one row per opening range: a day with a lunch break
has two rows, a closed day one row with `closed = true` and no `opens`
or `closes`. A loader reads the file once and checks or converts each
value by its format alone:

```python
import contract                        # or json.load(open("tables.schema.json"))
for column in contract.columns("opening_hours"):
    print(column["name"], column["format"], contract.sql_type(column))
problems = contract.check_rows("opening_hours", rows)   # [] when every value is right
```

## Adding your own sheets to the evaluation

Put a sheet and the rows you approved in `real_eval/` — see
`real_eval/README.md`. The next build scores them and shows the result in
`REPORT.md`.

## What is in this folder

* `build.py` — the one command; `check.py` — the machine check
* `tulip.py` — the API; `import_sheets.py` — the command line
* `tables.schema.json` — the declared format of every column;
  `contract.py` — the conversion into it, and its checks
* `tulipscript.py` — the language, its checks and its interpreter
* `sheets.py` — reading files and writing the preview; `helpers.py` — the
  cell readers (numbers, dates, times... in ten languages)
* `gen/` — the synthetic data generator; `handwritten/` — 30 real sheets
  written by hand for the evaluation
* `pack.py`, `train.py`, `evaluate.py`, `report.py`, `model.py`, `tok.py`
* `tests/` — `py tests/run_all.py`; `py tests/break_guards.py` breaks
  every guarded line once and shows the test that catches it
* `vendor/` — openpyxl, et_xmlfile, phonenumbers and hijridate as their
  PyPI wheels, used without installing (hashes in `DECISIONS.md`)
* `REPORT.md`, `DECISIONS.md`, `MODEL_CARD.md`
