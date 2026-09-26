# Tulip 1: conformance check against TULIP_BUILD_INSTRUCTIONS.md

Checked on node1 (MEGA9) on 26 September 2026 (CST), against the package as uploaded (commit a8c0f01 = tulip-package.zip, sha256 8ef28d3a...3518) and the spec kept at ~/plan-lab/reference/TULIP_BUILD_INSTRUCTIONS.md. Read-only check; nothing in the package was changed. Probe scripts and logs stayed in that session's scratch folder.

**Verdict: FAIL as a working importer, broadly conformant as code.** The plain-code parts are sound: the appendix code is byte-identical to the spec, all tests pass, the generator is deterministic, the helpers are strong, and I could not break the runtime. But the only trained model (the pilot) gets 0.13–0.15 pass@1, every gate line except invented values fails, and the `full` preset was never run, so the real gate is still untested. I also found 5 MUST violations, 7 partial ones and several robustness defects.

## (1) Appendix files
All 9 appendix files (A `tulipscript.py`, B `sheets.py`, C `tok.py`, D `model.py`, E the 5 test files) are byte-identical to the spec's code blocks. Since there are no deviations, `DECISIONS.md` has none to log. `~/tulip-package.zip` (sha256 8ef28d3a…3518) matches commit a8c0f01 exactly.

## (3) The package's own tests and generator self-check
- **`tests/run_all.py`:** 39 passed, 0 failed (the 26 appendix tests plus 13 of the package's own).
- **`gen/make.py --check`:** passes at smoke and at pilot size. It reproduces REPORT's numbers exactly: 189 discards of 62,689 (0.30%), 625 real-file round trips with 0 differences, helpers right on 99.997% of values.
- **Tokenizer stage (pilot):** also matches REPORT exactly — 68 of 62,500 tasks over 4,096 tokens, 0 round-trip failures, same per-language p50/p95/max.

My own independent checks:
- **Helpers:** all 167 Appendix I cases pass, with exact result types. 199 of 200 extra probes built from section 9's wording pass. The only miss is `tax_included('شامل')`. The helpers never raised on odd inputs.
- **Re-running every program:** all 62,500 stored programs give their truth and pass every check, in every split.
- **Conventions (60,000 train programs):** no violation of the one-convention rules (`text()` outside, `first()` order, lookup keys in VALUES order, no `lookup` where `boolean` would do).
- **Trap rates, measured from the sheet and program rather than the task's own labels:** T1 34.9%, T3 13.8%, T4 43.3%, T5 57.9%, T6 10.5%, T7 27.4%, T8 16.7% / 47.4%, T9 15.6%, T10 54.9% / 52.9%, T11 42.9%, T13 46.9%, T14 29.4%. All meet their rates. My header-matching count for T2 is only a lower bound (15.7%); 8 hand-checked examples confirm the claimed 24.1% is real.
- **Leakage:** 0 evaluation tasks share a preview, a preview minus its TARGETS line, or the sheet's cells with train.
- **Runtime (a fake model feeding scripted programs):**
  - The candidate-loop rules all hold: a greedy refusal is final, the first passing sample wins, 4 or more refusals out of 8 means refused, otherwise needs_review.
  - All 33 hostile programs were rejected (`__import__`, `exec`, `eval`, `open`, lambdas, comprehensions, f-strings, `while`, 400-deep nesting, huge constants, `10**100` indices), with no side effects.
  - Sources report the original column letters after empty columns are removed.
  - 8 threads sharing one Tulip object gave no errors.
- **`import_sheets.py` with a fake model:** the SQL types, the `tulip_imports` columns, skipping on re-run, replacement of a changed file's rows, hidden sheets and skipped `.xls`/`.ods` all behave as specified.

## (2) MUST violations and partials

| § | Requirement | Status | Evidence |
|---|---|---|---|
| 7.1 / 15.1 | Every skipped row listed with its row number and reason | **Not met** | `tulip.py:219` returns `res.skipped` and drops `res.empty`. A notes row came back `imported_with_warnings` with `skipped=[]` and `warnings=[]`. |
| 10.3 | Sheets 3–400 data rows, log-uniform | **Not met** for products and services (36% of tasks) | Longest product sheet in 60,000 train tasks: 38 rows (0.1% over 30). Longest services sheet: 27. Cause: `gen/columns.py:119` (`combos[:n]`) and `:170` cap rows at the activity's item count. DECISIONS #8 claims caps of 400 and 60. The spec's own "300-line product catalogue" never occurs. |
| 10.3 | 70% xlsx / 30% CSV | Partial | Measured 64% / 36% (`gen/tasks.py:287` plus CSV-only families). Not logged. |
| 10.4 | "MUST reach" rates: missing_required 3.5% | Partial | Measured 3.1%. It passes only because `gen/checks.py:130` accepts ±30%, a tolerance the spec doesn't give. |
| 10.5 | Arabic-Indic digits in 50% (ar-SA) / 60% (ar-EG) of text cells; full-width in 25% (ja) | Partial | Applied only to money and text columns (47% / 55% / 25% of price columns). Dates, times, phones, stock and invoice numbers get 0%. Cell-level rates: 7.8%, 9.7%, 3.7%. See `gen/columns.py:37-51`. |
| 11 / 10.8(6) | No D or T item in train | **Not met** (small) | The train template `單價（{cur}）` renders, after the tokenizer's NFKC normalisation, as the D variant `單價(元)`: it is the price column's header in 17 train tasks. 18 D/T variants equal train group labels (e.g. it `Stock`, fr `Désignation`), which appear in ~270 train header areas. 12 of 500 test_heldout tasks have no other held-out item. The package's check passes because `gen/tasks.py:238` compares raw strings of field headers only. |
| 11 | Never look at individual handwritten results | Minor breach, self-disclosed | One file's status (`hw-it-01`) was viewed after the final scores. |
| 11 | `val` used for loss curves | Not met | `pack.py` packs `val` "for the loss curve"; `train.py` never reads it. |
| 22 | Read at least 100 examples from the largest error groups | **Not met** | DECISIONS says 12 + 4 examples were read in full; the rest were only counted. |
| 20 | `--from STAGE` forces the stage | **Not met (read from the code, not executed)** | `train.py:233-247`: if a finished `last.pt` with the same preset hash exists, training is skipped. After a lexicon change without a GENERATOR_VERSION bump, `--from generate` retrains the tokenizer, then `train.py:248-254` saves the old weights with the new tokenizer into `best.pt`, a mismatched model. |
| 24 | REPORT template | Partial | Headings are out of order (sections 3–6 repeat per preset). Section 8 is cut at 6,000 characters mid-sentence (`report.py:273`), dropping DECISIONS 25–32, including the pilot dropout deviation. Missing: results per family, candidates-tried statistics, gate rows 10 and 12, the third summary line. Error examples are cut to 4 lines (`report.py:189`), so several "wrote / expected" pairs are identical. |
| 15.2 | Locale not in Appendix F uses the language's first locale for dates | Partial | `en-DE` reads `03/04/2024` as 2024-04-03 (day first); en-US rules would give 2024-03-04. |
| 9 | `شامل` means tax included | Partial | `tax_included('شامل', 'ar-SA')` fails. |

- **Met:** §5, §6 and §8 (identical fixed code); §12; §13 (parameter counts measured: 1,115,008 / 8,916,224 / 37,986,816; pilot dropout 0.0 is a logged deviation); §14 (schedule, AdamW, clipping, precision, OOM halving, time cap, model selection); the §15.1 API signatures, 500-row trial, seeded sampling, per-candidate exception handling, `threads` and lock; §16 definitions; §17 code style (no `exec`/`eval`/`compile`, every file opened with utf-8); §18; §19 layout; handwritten set (all 30 file hashes plus `truth.jsonl` match); §23 README contents.
- **Could not verify:** delivery of `tulip-pilot.pt` and `eval_tables.md`. Neither is in the commit or anywhere on this machine.

## Gate failures (pilot, REPORT numbers; the gate formally applies to `full`)
| # | Target | Pilot | Gap |
|---|---|---|---|
| 1 | test_seen pass@1 ≥ 0.97 | 0.128 | −0.84 |
| 2 | test_heldout pass@1 ≥ 0.90 | 0.154 | −0.75 |
| 3 | correct imports among importable ≥ 0.95 | 0.114 | −0.84 |
| 4 | false accepts ≤ 2% | 59.2% | about 30 times the limit |
| 5 | refusal precision / recall ≥ 0.95 / 0.90 | 0.61 / 0.56 | −0.34 / −0.34 |
| 6 | target choice ≥ 0.97 | 0.756 | −0.21 |
| 7 | every language and target ≥ 0.88 | 0.00 (bookings, invoice_ledger) | — |
| 8 | every trap ≥ 0.85 | 0.00 (several traps) | — |
| 9 | invented values = 0 | 0 | PASS (guaranteed by construction) |
| 10 | helpers: Appendix I / generated values | 100% / 99.997% | PASS, but missing from the REPORT table |
| 11 | handwritten (hoped 0.80) | 2 of 32 = 0.06 | report only |

## (4) The pilot's low pass@1
- **What the spec expects:** section 16 sets no gate for the pilot, only "roughly test_seen ≥ 0.85 and test_heldout ≥ 0.70". The gate (0.97 / 0.90 and the other rows) is for `full` only.
- **What DECISIONS and REPORT say:** under-training caused by the CPU budget (4 cores): 2,711 steps, 0.7 epoch, loss still falling. The main errors are writing `header(1)` when the header sits lower, and unparsable programs (repeated lookup keys).
- **My assessment:** under-training is plausible. I found no pipeline defect: stored programs reproduce their truth, the preview is the same in generator and runtime, the tokenizer round-trips, and the loss/schedule tests pass. But "CPU budget" is the wrong framing:
  - The first pilot round stopped at the spec's "at most 1 epoch" rule after 62 minutes, not at the 90-minute time limit.
  - So any CPU gets at most about 1,900 steps with 30,000 tasks, or about 3,870 with the allowed 2× data.
  - The measured curve (0.07 → 0.10 over the last ~850 steps) does not point to 0.85 within that budget.
  - So either the spec's pilot expectation is miscalibrated or the task is harder than assumed.
  - Only a `full` run can settle it, and none exists.
- I did not retrain the pilot: the machine was loaded and, from 17:00, a GPU training unit was active.

## Surprises and robustness
- **One bad file stops a whole folder import:** a corrupt `.xlsx` (BadZipFile) or a binary `.csv` (csv.Error) raises out of `import_sheets.py:204` and `tulip.py:227`. The PLAN's rule is "never a crash".
- **Default targets break the PLAN contract:** `--targets` defaults to all 7 (`import_sheets.py:173`, `tulip.py:241`), with no warning. The PLAN says at most 4 per call, and the model was trained on 1–4.
- **The 500-row trial rejects correct programs:** a lookup key that first appears after data row 500 is rejected in the trial, although the whole sheet passes. Demonstrated (result: needs_review). This comes from the spec itself (7.1 against 7.2).
- **False accepts are built into the design:** a program reading the stock column as the price passes every check. That is why gate 4 depends entirely on the model being right.
- **Slow date reading on long cells:** `date()` time grows with the square of cell length (8,000 characters take 1.2 s; 40,000 take 42 s). The runtime's timeout is only checked between rows (`tulipscript.py:750`).
- **Evaluation can run out of memory:** `evaluate.py:347` starts one process per core (`os.cpu_count()`), each loading torch. On this 32-core box inside the 12 GB limit it was OOM-killed, so I could not complete the smoke build here. Training itself ran (13.2 min; dev match 0.02 at step 1,200).
- **Two smaller oddities:** `build.py:80` falls back to `pip --break-system-packages`, and `refuse('missing_required:__class__')` is accepted (Appendix A's pattern allows any lowercase name).

**Not run:** the smoke evaluate/export/report stages, the real-model API check (`probes/api_real.py`, written but unexecuted) and the `--from train` test. A `geek-train-run@642e2a9281647628` unit running `build.py full` started at 17:00 and was still active, so I stopped importing torch.

**My own slip:** a wrapper script I wrote without an `if __name__ == "__main__"` guard respawned itself. It ran 16:56–17:06 (about 54 CPU-minutes, CPU only, nice 19, 12 GB cap) and overlapped the first ~6 minutes of that training unit before I stopped it.

Everything is in `/tmp/claude-1000/-home-node1/e82d72ba-6cd9-4c70-9ee8-441cc89d23c2/scratchpad/tulip-conf/`: the probe scripts are in `probes/`, and the logs are `tests.log`, `gen_pilot.log`, `sec9.log`, `summary_pilot_v2.txt` and `tok_pilot.log`.