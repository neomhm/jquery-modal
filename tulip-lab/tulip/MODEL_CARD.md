# Model card — Tulip 1, the Importer

**What it does.** Reads the preview of one spreadsheet sheet (the first 16
and last 4 non-empty rows, column types, number formats and the repeating
words of each column) and writes a TulipScript program that imports the
sheet into one of seven tables — products, services, opening_hours, staff,
clients, bookings, invoice_ledger — or refuses it (`not_a_table`,
`no_matching_target`, `missing_required:<field>`, `too_wide`). The program
is never executed as code: `tulipscript.py` parses it and runs it with
plain checks. Every imported value carries the sheet cells it came from.

**Model.** A decoder-only transformer trained from scratch (RMSNorm,
SwiGLU, rotary positions, a key/value cache, tied output layer), with a
byte-level BPE tokenizer trained from scratch. No pretrained weights, no
downloaded model, no external model or API to write data.

| preset | vocabulary | d_model | layers | heads | parameters | file |
|---|---|---|---|---|---|---|
| smoke | 4,000 | 128 | 3 | 4 | 1.1 M | tulip-smoke.pt |
| pilot | 16,000 | 256 | 6 | 4 | 8.9 M | tulip-pilot.pt |
| full | 24,000 | 512 | 8 | 8 | 38.0 M | tulip-1.0.0.pt |

**Training data.** Entirely synthetic: sheets drawn by the generator in
`gen/` from word lists written natively for ten languages and 33 locales,
with the traps real sheets have (title rows, totals rows, repeated
headers, section rows, sizes as columns, two prices, cost columns, notes
rows, currencies only in headers or number formats, names split over
columns, dates and times in one cell, status words). The truth of every
task is the drawn record, and every task passes a self-check with the real
runtime before it is used.

**How it is used.** `tulip.Tulip.import_sheet()` runs the candidate loop:
the greedy program first, then up to 7 sampled programs; the first that
passes every runtime check is the import; a greedy refusal is final;
otherwise the sheet is refused (4 or more refusals) or needs review.

**Evaluation.** See `REPORT.md` and `runs/<preset>/eval_tables.md`:
pass@1, the loop's correct imports, false accepts, refusals, and scores per
language, target and trap, on held-out layouts, headers and activities
(`test_heldout`), held-out locales (`test_locale`) and 30 handwritten real
files.

**Limits.** Trained on synthetic sheets only. Reads `.xlsx`, `.xlsm` and
`.csv` (not `.xls` or `.ods`). One table per sheet, at most 26 non-empty
columns. A row covering several days ("Lun–Ven 9h–18h") is not read.
Formulas saved without a cached value arrive empty. A product whose name
begins with a totals word, on a row with only numbers besides it, is taken
for a totals row. Sheets whose preview does not fit in 4,096 tokens go to
review. Its numbers are those of `REPORT.md`, not a promise for every
sheet: check imports with `import_sheets.py --show`.
