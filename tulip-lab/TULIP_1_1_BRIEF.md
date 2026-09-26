# Tulip 1.1 — the work order

Written 2026-09-27 for another Claude session to build. The seven abilities below were
proposed on 2026-09-26 and **confirmed by the owner (Laurent)**. This file is meant to be
self-contained: read it all before changing anything.

## 0. What Tulip is today, and what you start from

Tulip is the **Importer** of PLAN. PLAN is a system where a small business drops its files
in a folder and gets a checked website plus a back-end database. Tulip reads one spreadsheet
sheet (`.xlsx`, `.xlsm`, `.csv`) and writes a short **TulipScript** program. `tulipscript.py`
parses that program and runs it with plain checks, so it never runs as Python. The program
imports the sheet into one of seven tables (`products`, `services`, `opening_hours`, `staff`,
`clients`, `bookings`, `invoice_ledger`) or refuses it (`not_a_table`, `no_matching_target`,
`missing_required:<field>`, `too_wide`).
- Every imported value carries the cells it came from.
- The model is a decoder trained from scratch: 38.0M parameters in the `full` preset, with
  its own BPE tokenizer.
- Its training data is synthetic, drawn by `gen/` in ten languages (ar, zh, en, fr, ru, es,
  it, hi, ja, ko) and 33 locales.
- `tulip.Tulip.import_sheet()` runs a candidate loop: the greedy program, then up to 7
  sampled ones; the first program that passes every runtime check wins.

Read `tulip/README.md`, `tulip/MODEL_CARD.md`, `tulip/DECISIONS.md` and `CONFORMANCE.md`
first.

**Base to start from:** the `tulip-lab` tree **as Tulip 1 is being trained on MEGA9**. It
includes a local preparation pass that made the package conform to the training service
(section 6), capped its worker pools after an out-of-memory incident, and fixed the
generator and the evaluation. That tree is `tulip-lab` commit **1f0bf23** (the zip the owner gives you); its program package is `tulip-package-offline.zip`, sha256 01762d63…07fd, rehearsed on CPU (exit 0, peak 1.17 GB) and tested (55 passed). **Do
not start from the older `tulip-package.zip` (sha256 8ef28d3a…3518)**: it lacks those fixes.

**Tulip 1 is trained unchanged, in parallel with this work.** Tulip 1.1 is the next
training round. Its report must be compared with Tulip 1's on the same test sets (section 7).

## 1. The seven abilities

Items A–E are code around the model and need **no retraining**; they must also work with the
Tulip 1 model file. Items F and G change what she learns and need **Tulip 1.1's training**.

### A. Speak the contract's formats (no retraining)

The walking skeleton (`plan-lab/skeleton`, `lib/loader.py`) found that the pieces disagree:
- **Day of the week:** Tulip returns 0–6. Daisy's tables expect an English day name plus
  separate `opens` and `closes`. The blueprint contract's table is
  `opening_hours(day, hours, note)`.
- **VAT:** Tulip returns a fraction (`0.055`). Daisy's rule is a percent (`5.5`).

**Do:** make Tulip's output follow ONE declared format per column, defined in a single
schema file that Tulip, the loader and Daisy all read.
- Proposed format (reconcile it with the contract version current when you start; v0.4 is
  being written in `plan-lab/design/`):
  - `day` is lower-case English (`monday` … `sunday`)
  - `opens` and `closes` are `HH:MM` in 24-hour time; `closed` is a boolean
  - `vat_rate` is a percent number
  - money is a decimal number, with the currency in its own column as ISO 4217
  - dates are ISO 8601
- Convert in the runtime at output, not in the model.
- **Done when:** the skeleton's loader no longer needs its `days[v]` special case, and a test
  pins every column's type and format against the schema file.

### B. Compare sheets against each other (no retraining)

Today each sheet is imported alone. The test's "messy" example folder had three menus and two
price lists that disagree, and all of them were imported.

**Do:** after a folder's imports, a plain-code pass groups rows that describe the same thing
across sheets and files:
- same table, same normalised key (e.g. product name after NFKC + casefold + unit
  normalisation);
- it detects duplicates and contradictions (same product, different price);
- it picks a **preferred source** by stated rules: the newest document date, then the newest
  file date, then a file the business wrote over a supplier's;
- it records every conflict as a question for the owner's data-check step, with both values
  and both source cells;
- it never silently merges or drops a row.

**Done when:** on the messy example it reports each duplicated product once, with its
conflict listed; nothing is lost; and the rule for the preferred source is written down and
tested.

### C. Show how sure she is, column by column (no retraining)

**Do:** for each imported sheet, give a confidence per mapped column (e.g. "column C → price:
sure; column F → cost: unsure"). Derive it from what the model already produces:
- the program's token log-probabilities at the mapping;
- the agreement among the 8 candidate programs;
- the runtime checks.

Show the level as a band (sure / check / unsure) in the import record (`tulip_imports`) and
in the preview. Calibrate the bands on held-out data so that "sure" is right at least 99% of
the time, and state the measured rate.

**Done when:** the bands are in the output, calibrated, with their measured accuracy in
`REPORT.md`.

### D. Record the owner's corrections as future lessons (no retraining now)

**Do:** when the owner corrects an import at the data-check step (remaps a column, fixes a
value, un-refuses a sheet), store the correction in a table (e.g. `tulip_corrections`) with
the sheet's preview, the program Tulip wrote, and the corrected mapping or program.
- Write the exporter that turns these records into training lessons in the generator's task
  format, so a later training round can include them.
- Privacy: the corrections stay on the owner's PC unless the owner shares them. This follows
  the contract's section 19 (the feedback loop) and its opt-in rules.

**Done when:** a correction round-trips (recorded → exported as a lesson → the lesson passes
the generator's self-check with the real runtime).

### E. Update instead of replace, with history (no retraining)

Today a changed file replaces its earlier rows.

**Do:** when a re-imported sheet changes, compute the difference per row by the table's key:
- added, removed and changed rows, with the changed fields;
- write the new state and keep the history (e.g. "croissant 1.10 → 1.20 on 2026-03-03, from
  tarifs.xlsx row 12");
- removals are marked, never deleted.

The stock, accounting and till features will depend on this.

**Done when:** re-importing an edited price list gives exactly the expected difference and
history rows, and an unchanged file changes nothing.

### F. New tables (retraining: Tulip 1.1)

The owner confirmed that a food business such as a bakery also keeps:
- **stock** (levels by item and location)
- **suppliers**
- **purchase orders**
- **recipes with their ingredients** (a bill of materials: one recipe → many ingredient rows,
  with quantities and units; for production planning and costing)
- **allergens** (the 14 regulated EU allergens per product; the US has its own list; legally
  required for food)
- **product variants** (sizes, weights, packs)

**Do:**
- Add the targets to the schema file (A), the runtime, the generator (sheets drawn natively in
  all ten languages, with the same kinds of traps as today), the self-check, the evaluation
  and the handwritten set.
- Recipes are the hard one. A recipe sheet is often one block per recipe, or one row per
  ingredient with the recipe name repeated or merged. Decide how TulipScript expresses a
  parent/child import and write it down in `DECISIONS.md`.
- **Align every new table's columns with the PLAN feature catalogue** being written at
  `plan-lab/design/FEATURES.md` and `plan-lab/design/features/catalogue-features.json`. Stock,
  recipes and suppliers must mean the same thing in Tulip as in the future till and
  accounting. If the catalogue is not final when you start, propose the columns, list them in
  one place, and **stop for the owner's confirmation before locking them** (the
  vocabulary and the generator depend on them).

**Done when:** every new target has generator coverage in ten languages, held-out test sets,
and a row in `REPORT.md`.

### G. More kinds of files and layouts (retraining: Tulip 1.1)

1. **Tables inside PDFs:** price lists and supplier invoices very often arrive as PDF, and
   neither Tulip nor the Extractor reads a PDF table today.
   - Vendor a pure-Python PDF reader as wheels, as `vendor/` does today (pdfminer.six and
     pdfplumber are candidates; check each licence).
   - Rebuild the table from the text positions into the same preview Tulip reads for a
     spreadsheet.
   - Generate training PDFs from the existing sheet generator.
   - Scanned PDFs (images) are out of scope: no OCR.
2. **Old Excel `.xls` and LibreOffice `.ods`:** pure-Python readers only (e.g. xlrd for
   `.xls`; `.ods` is a zip of XML).
3. **Several tables on one sheet:** detect the blocks, then import each on its own or refuse
   it on its own.
4. **Day ranges in one row:** e.g. "Lun–Ven 9h–18h", "Mon-Fri 9-6", "月～金 9:00-18:00".
   Expand them into one row per day in the helpers, in all ten languages.

**Done when:** each file type and layout has generated training data, held-out tests and
handwritten cases, with per-type scores in `REPORT.md`.

## 2. What Tulip must NOT take on

Exporting sheets (e.g. for the accountant), running stock or the till, and accounting logic
are plain code built on her tables, not model work. Tulip stays an **importer**; that is what
keeps her small and safe.

## 3. Rules that do not change

- The model never runs code. Every value is traced to a cell, and every program passes
  `tulipscript.py`'s checks.
- The candidate loop stays: up to 8 programs, the first that passes the runtime checks wins;
  "needs review" rather than a wrong import.
- No pretrained weights, no downloaded model, no network at run time.
- Test and evaluation sets stay held out: no generated training item may equal a test item.

## 4. Order of work

1. **A** (formats), then **C** (confidence). These are small and unblock the owner's
   data-check step.
2. **B** (compare sheets), **E** (history), **D** (corrections).
3. **F** (new tables) once the feature catalogue's columns are confirmed, and **G** (files and
   layouts) in parallel.
4. Rehearse (section 6), then hand over for training.

Estimate given to the owner: A–E are about 3–4 days of code with no retraining; F and G are
about 5–7 days, then a rehearsal and 3–6 hours of training on MEGA9.

## 5. Tests and evidence

- `py tests/run_all.py` must be green, with the pass and skip counts reported.
- Every new guard gets a test. **Break the code it guards once and watch the test fail**
  before believing it.
- Report measured numbers only; say which set each number is from.
- `REPORT.md` for Tulip 1.1 compares against Tulip 1 on the **same** held-out sets (the new
  targets only against themselves).

## 6. The training service's contract (MEGA9 `/train`)

The package must still conform to it. Anything that breaks one of these fails hours into a
run.
- **The run:** a systemd unit that runs `build.py` from the uploaded program zip.
  - **No network** (`PrivateNetwork=yes`): every dependency must be in the zip or the venv.
  - `MemoryMax=12G` (`MemoryHigh=10G`), `TasksMax=512`, **24 h** at most.
  - The machine has ~31 GB of system RAM for everything, and 16 cores.
- **Pools:** at most **4 workers**; never one per core. A previous Tulip evaluation spawned 30
  × ~1 GB workers and helped cause a machine-wide out-of-memory event.
- **The venv (Python 3.12.3):** torch 2.14 (ROCm 7.2), tokenizers, numpy, datasets,
  transformers, accelerate, peft, safetensors, pandas, pyarrow, pyyaml, regex, psutil, tqdm.
  - **Not present:** openpyxl, phonenumbers, hijridate, faker, and any PDF library. Ship pure-Python
    wheels in `vendor/` with their sha256 in `DECISIONS.md`.
- **Returned files:** only these extensions — .pt .pth .safetensors .bin .ckpt .json .jsonl
  .txt .md .csv .tsv .log .npy .npz .gguf .onnx .model .vocab .yaml .yml .png .svg.
  - At most 60 files; hidden folders are skipped.
- **Progress:** print lines `Stage N/M` and `step N/TOTAL`; the page reads them.
- **Uploads:** a training-data zip may hold only .txt .md .csv .json .jsonl. Each uploaded file
  must be ≤ 10 MB; split into several zips if needed (one data upload may take several).
- **Rehearse before handing over:** a CPU-only run of the whole path with the `tiny` preset,
  under a 4 GB memory cap, must end with exit 0 and return its files.

## 7. What to hand back

- The changed tree (or a patch against the base commit), and the rebuilt program zip(s) with
  size and sha256.
- The exact `/train` form values: program, data, words, start from zero or from Tulip 1.
- The rehearsal log: stages and steps seen, memory peak, files returned.
- A short list of every decision you made that the owner should know about (columns, the
  preferred-source rule, confidence thresholds), each with the one-line way to undo it.
- Anything left unfinished, said plainly.
