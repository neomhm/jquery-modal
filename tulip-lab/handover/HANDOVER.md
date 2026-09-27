# Tulip 1.1 — hand-over

Work order: `TULIP_1_1_BRIEF.md`, on base tulip-lab d64d6c8 (committed
here as 3be348b). Branch `claude/attached-instructions-vz6bdr`; the
program is commit 6adfea1. Every number below was measured here and names
the set it comes from.

## 1. Where things stand

| item | state |
|---|---|
| A — one declared format per column | **Done.** Works with the Tulip 1 model file. `tables.schema.json` is marked `0.4-draft.tulip-1.1`: contract v0.4 was not available here, so it must be reconciled with it (change only that file). |
| C — a confidence band per mapped column | **Done.** A model built by Tulip 1.1 carries its own calibration (fitted on dev_heldout, measured on test_heldout, written in REPORT.md). Tulip 1's model file needs `py calibrate.py tulip-1.0.0.pt` once; that was **not run here** (the file is not in this environment). Until then it never says "sure". |
| B — compare sheets | **Done.** |
| E — update instead of replace, with history | **Done.** |
| D — corrections as future lessons | **Done.** |
| G — PDF tables, .xls / .ods, several tables per sheet, day ranges | **Code, training data and tests done.** The model learns `weekdays()` (several days in one cell) only in the /train run. |
| F — stock, suppliers, purchase orders, recipes, allergens, variants | **Not done — waiting for you.** The columns are proposed in `tulip/PROPOSED_TABLES.md` with 4 questions at the end. Nothing of F is built or trained. |
| The Tulip 1.1 model | **Not trained** — that is the /train run below. |

## 2. The /train form

| field | value |
|---|---|
| Program | `tulip-package.zip` — 4,925,714 bytes, sha256 `978e22e097a047f9286b2fbd15d83fb666b879d487b3cd3c3f16986a0275282a` (369 files; `handover/make_package.py` rebuilds it byte for byte from the tree) |
| Data (optional) | one zip holding Tulip 1's own `runs/full/eval.json`, renamed `tulip1_eval.json` (so REPORT.md compares 1.1 with 1 on the same held-out sets), and any `lessons.jsonl` from `corrections.py export`. Only .txt .md .csv .json .jsonl, each at most 10 MB. |
| Words | `full` |
| Start from | zero (Tulip always trains from zero; a model loaded into the run is ignored) |

**Train now, or after F?** Training now gives Tulip 1.1 with A–E and G but
without F's tables. F needs your answers, then generator families for its
tables, then another /train run. If you would rather use one /train run,
answer the F questions first.

If REPORT.md says Tulip 1's eval.json was not found (the build looks in
`data/`, `previous/`, `upload/`, `uploads/` next to build.py and in
`../data`; the page may put the data upload elsewhere), put the run's
`runs/full/` folder next to build.py on your PC and run
`py report.py full` with the environment variable `TULIP1_EVAL` naming
Tulip 1's eval.json.

The evaluation scores 2,000 dev_heldout and 2,000 test_heldout tasks with
all 8 candidate programs (for the calibration). If the 24-hour budget runs
short, it skips the last splits of its order (test_locale, then val, then
test_layouts …) and names them "not run (time)".

## 3. The rehearsal

`tulip-package.zip` above, unpacked and run as `python3 build.py tiny` under
the /train unit's limits on this machine (4 CPUs, no GPU): memory capped at
4 GiB and tasks at 512 (cgroups), no network (its own network namespace),
and the venv's packages only (the system copies of openpyxl, et_xmlfile,
phonenumbers, hijridate, xlrd, xlwt, pypdf, reportlab and cryptography
hidden, so only `vendor/` could provide them). One `lessons.jsonl` (a real
exported correction) was put in `data/`, as a data upload would be.

| | |
|---|---|
| result | **exit 0** after 670 s (the build: 11.2 min) |
| stages seen | `Stage 1/8: check`, `2/8: generate`, `3/8: tokenizer`, `4/8: pack`, `5/8: train`, `6/8: evaluate`, `7/8: export`, `8/8: report` |
| steps seen | `step 40/40` (and 438 `progress N%` lines) |
| memory peak | 2.40 GB resident (2,395,901,952 bytes, sampled each second); 2.55 GB with the page cache (the cgroup's own peak); the 4 GiB limit was never hit, no out-of-memory kill |
| tasks peak | 36 of 512 |
| data upload | "lessons: 1 from 1 file(s) joined the training split; rejected: none" |
| generator self-checks | all 8 passed, including the new "every language in every evaluation split" |
| files returned | **12** of at most 60: `tulip-tiny.pt`, `REPORT.md`, `runs/env.json`, `data/tiny/stats.json`, and in `runs/tiny/`: `build.log`, `eval.json`, `eval_tables.md`, `generator_checks.json`, `stages.json`, `tokenizer.json`, `tokenizer_report.json`, `train_result.json` (the 5 files in the hidden `runs/tiny/.work/` are not sent) |

The tiny model is a plumbing check, not a model: it imported nothing
(0.0 on every split), so its REPORT.md says it has no calibration ("no
column of dev_heldout was imported") and that Tulip 1's eval.json was not
given (there is no Tulip 1 tiny run here; the comparison is tested on its
own, and was checked against Tulip 1's real pilot eval.json).

The first rehearsal, on an earlier zip, found three problems, all fixed
before this one: the packaging left out `gen/data` and `tests/data` (the
build stopped at once); the new splits' language skew (commit 40ee8e7);
and a "dev_heldout was not scored" message for a split that was scored.

In `handover/`: `rehearsal-tiny.log` (the whole log),
`rehearsal-returned.txt`, and `rehearse.sh`, `hide/` and `returned.py` to
run it again.

## 4. Tests and measured numbers

* **`python3 tests/run_all.py`** on the program (commit 6adfea1):
  **133 passed, 0 skipped, 0 failed** in 159 s on this 4-core CPU with nothing else running (test_model included). Log: `handover/suite.log`.
* **Guards** (`tests/break_guards.py`): 71. Each guarded line was broken
  once, in a copy of the tree, and its test watched failing: **71 caught,
  0 not guarded** — 63 in one run (`handover/guards-63.log`), then G14–G21
  (`handover/guards-G14-G21.log`). None of the 71 was caught only by a
  crash or a hang (the script counts those as caught, with a 600 s and
  8 GB limit per test).
* **Python 3.12.3** (the /train venv's version; torch is not installed for
  it here), on commit 6adfea1: the 31 tests that need no torch pass, among
  them the check that the six held-out sets are drawn exactly as Tulip 1's
  (96 tasks byte for byte).

| measured | on which set | result |
|---|---|---|
| .xls reader | val tasks 96,000–96,119: the 81 .xlsx tasks written as .xls and read back | 81 pass the self-check; 81 give the same preview as the .xlsx |
| .ods reader | the same 81 written as .ods | 81 pass; 31 give the same preview (the others name their currency and percent formats, by design) |
| PDF reader | the 35 .csv tasks of the same range written as PDFs | 35 pass; 35 give the same preview |
| handwritten 1.1 | 13 files, 15 tables (5 PDFs from another writer, .xls, .ods, two sheets of two tables, day ranges in five languages) | every truth line is given by its canonical program through the real readers and runtime (tested); sha256 frozen in DECISIONS G9 |
| splitter, one table | 1,500 generated sheets (300 each of val, dev_heldout, test_seen, test_heldout, traps) and the 32 handwritten sheets | 0 cut |
| splitter, several tables | the 40 multi-table sheets among the first 80 tasks of test_layouts | 33 cut right (82.5%) |
| new splits' languages | the first 80 tasks of test_layouts | all made; 4 of each language in each half |
| confidence bands, pilot model | dev_heldout tasks 200,200–201,999 (fit on even, measured on odd) | no "sure" band; the fallback "check" was right for 321 of 355 columns (90.4%), "unsure" for 284 of 481 (59.0%) — DECISIONS C6 |
| compare sheets (B) | the test's messy example (three menus and two price lists that disagree) | 1 duplicate and 4 contradictions found, 5 questions recorded; the 13 imported product rows untouched |
| Tulip 1.1 against Tulip 1 | — | written by the /train run into REPORT.md (same six held-out sets, plus Tulip 1's handwritten set) |

## 5. Decisions you should know about, each with its undo

The full list, with the reasons, is `tulip/DECISIONS.md` (sections A–G of
"Tulip 1.1").

| # | decision | how to undo it (one line) |
|---|---|---|
| A1 | One schema file, `tables.schema.json`, marked `0.4-draft.tulip-1.1` (contract v0.4 was not available here: reconcile it) | set a column's format back to Tulip's own kind in `tables.schema.json` and drop its `"tulip"` converter |
| A2 | `day` is lower-case English (`monday` … `sunday`) | remove `"tulip": {"convert": "weekday_name"}` from `day`, give it `"format": "integer"` |
| A3 | Opening hours: one row per opening range (a lunch break gives two rows; a closed day one row with `closed = true`) | replace `opens`/`closes`/`closed` with `{"name": "hours", "format": "text"}` and delete the `"split"` line |
| A4 | `vat_rate` is a percent (5.5 = 5.5 %), rounded to 4 decimals | remove `"tulip": {"convert": "fraction_to_percent"}` from `vat_rate`, give it `"format": "decimal"` |
| A5 | Text is NFKC, trimmed, single-spaced at output | delete the two `normal_text` lines in `contract.convert()` |
| A7 | A value outside its declared format sends the sheet to review (`contract_format`), nothing written | delete the `if wrong:` block in `Tulip._done()` |
| A8 | A Tulip 1 table is renamed `tulip_<t>_before_0_4_draft_tulip_1_1` (rows kept); the first 1.1 run imports every sheet again | `DROP TABLE` the renamed tables once checked; to stop the re-import remove `and prev[4] == contract.version()` in `unchanged()` |
| C2 | Confidence score = agreement of the 8 candidates × weakest token probability of the field's line × readable share of its cells | change `confidence.score()` and bump `SCORE_VERSION` |
| C3 | The 7 sampled programs are always written when bands are wanted (imports take longer; results unchanged) | `import_sheets.py --no-confidence` (or `confidence=False`) |
| C4 | "sure" = right ≥ 99% by the one-sided 95% lower bound; "check" = isotonic chance ≥ 80%; else "unsure" | the `sure=`, `check=`, `rule=` arguments of `confidence.calibrate()` |
| C5 | Thresholds live in the model file (Tulip 1.1) or in `<model>.confidence.json` (Tulip 1, from `calibrate.py`); without them, never "sure" | delete the `.confidence.json` file |
| B1 | Same thing = same table and same normalised key (NFKC, case, accents, Arabic short vowels, units in g/ml) | edit `keys.GROUP_KEY` |
| B3 | Preferred source: newest document date → newest file date → the business's file over a supplier's → a tie you decide | reorder the `for rule, field in` loop of `compare.prefer()` |
| B4 | Never merge or drop: only `tulip_conflicts` is written | n/a |
| B5 | CSV delimiter chosen by consistent cell counts (the sniffer took decimal commas for the delimiter) | put the `csv.Sniffer()` line back in `sheets.read_csv()` |
| E1 | Re-imported rows paired by key (products: SKU, else barcode, else name + variant; staff: e-mail, else name; …) | edit `keys.MATCH_KEYS` |
| E2 | Added rows inserted, changed rows updated in place, missing rows marked `_removed`, never deleted; every change in `tulip_history` | n/a |
| E3 | A sheet now refused or needing review keeps its rows | n/a |
| D3 | Corrections are exported only when you share them | `corrections.py share --undo <id>` |
| D6 | Exported lessons in `lessons/`, `data/` or `upload(s)/` join the next training run, each checked again | set `make.LESSON_FOLDERS = ()` |
| G1 | PDFs read with pypdf 6.19.0 (vendored, BSD-3), crypto packages blocked at import | remove the `.pdf` branch of `sheets.load()` |
| G3 | A scanned PDF (no text) needs review (`scanned_pdf`); no OCR | n/a |
| G4 | `.xls` with xlrd 2.0.2 (vendored); `.ods` with the standard library | remove the `.xls` / `.ods` branches of `sheets.load()` |
| G6 | A sheet of several tables is cut before the model, one import per table | remove the `blocks.split()` loops in `tulip.import_file` and `import_sheets.import_path` |
| G7 | `weekdays()` reads several days in one cell; the row becomes one row per day | remove `weekdays` from `tulipscript.HELPERS` |
| G8 | Generator 1.2.0: new splits `test_files` and `test_layouts`, part of train written as .xls/.ods/PDF, the day-range family; Tulip 1's six evaluation splits unchanged | set `GENERATOR_VERSION` back and remove the `SINCE` family and the two splits from `config.SPLITS` |

## 6. Unfinished, said plainly

1. **F is not done.** It waits for your answers in
   `tulip/PROPOSED_TABLES.md`. The feature catalogue it should follow
   (`plan-lab/design/FEATURES.md`) was not available here.
2. **The Tulip 1.1 model is not trained.** Its numbers, and the comparison
   with Tulip 1, come from the /train run.
3. **Tulip 1's model file has no calibration yet.** Run
   `py calibrate.py tulip-1.0.0.pt` once. The pilot model, measured here,
   never reaches "sure": its 300 best-scored columns were 96.7% right,
   short of 99% (DECISIONS C6). Whether Tulip 1 or Tulip 1.1 reach "sure"
   is unknown until measured.
4. **Contract v0.4 and the walking skeleton** (`plan-lab/`) were not
   available: the schema file is a draft to reconcile, and the skeleton's
   loader (its `days[v]` special case) was not changed.
5. **Several tables on one sheet:** cut right for 33 of the first 40
   multi-table sheets of test_layouts (82.5%). Known misses: a table whose
   header row is quantities ("50 ud.", "4個"), and tables side by side
   (4 of 8 wrong on scratch sheets). A wrong cut is a wrong import of that
   sheet.
6. **PDFs:** text PDFs only (a scanned PDF goes to review, no OCR); tested
   on PDFs from two writers (Tulip's own and reportlab); right-to-left text
   is assumed stored in visual order, as PDF writers store it.
7. **Python 3.12.3:** the /train venv's Python. Here the whole suite and
   the rehearsal ran on Python 3.11 with torch 2.14 (CPU); on Python 3.12.3
   only the 31 tests that need no torch were run (all passed).
