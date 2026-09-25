# DECISIONS.md

Every choice the build instructions did not settle, with the reason. When
something was not covered, the most conservative choice that fits the
instructions was taken. Newest decisions are added at the end of each
section.

## Environment

* **No GPU in the build machine.** `check.py` found no CUDA device, so the
  build uses the `pilot` preset (section 8) and Phase 4 (the full model)
  is skipped. The full preset is ready: `py build.py --preset full` on the
  desktop GPU trains it with the same code.
* **PyTorch from PyPI.** The CPU wheel index (download.pytorch.org) was
  blocked by the network proxy (HTTP 403); the standard PyPI wheel was
  installed instead. `build.py` and `check.py` never install torch.
* **Wikipedia** was reachable, so the pilot tokenizer and pretraining use
  plain-text Wikipedia in the ten languages (section 9).

## Language data (section 10.2)

* **Who wrote it.** The lexicons, sentence templates, titles, activity
  texts and locale lists were written natively per language by separate
  writers (one per language), all following one brief
  (`gen/data/BRIEFING_FOR_WRITERS.md`, which repeats the labelling rules of
  section 5 word for word) and one schema (`gen/data/SCHEMA.md`). Nothing
  was translated word for word, nothing was downloaded, no external model
  or API wrote any of it. `gen/validate_data.py` checks every file
  (slots, counts, label rules, postcode formats); all files pass with 0
  errors.
* **Traditional Chinese has its own data folder** (`gen/data/zh-Hant`),
  used by zh-TW and zh-HK. The language is still `zh` for the language
  head and the reports (section 6 lists ten languages).
* **Currency suffixes.** `円（税込）`, `元整` and `원정` were removed from the
  currency forms used on every amount (they made subtotals read "tax
  included"); they still appear in amounts written in words, where they
  belong.
* **Keywords that exist only in some countries** (HST, CGST, NIF, CUIT,
  統一編號, УНП …) are filtered by country (`gen/ctx.py`, `ONLY_IN`), also
  in English-mixed and bilingual documents.

## Names and addresses: the Faker rule (section 10.3)

* The rule was run with Faker 40.39 (`py gen/faker_check.py`, result in
  `gen/data/faker_decisions.json`).
* **Person names:** Faker passes the rule in 24 locales (ar-SA, en-AU,
  en-CA, en-GB, en-IN, en-NG, en-US, es-AR, es-CL, es-CO, es-ES, es-MX,
  fr-BE, fr-CA, fr-CH, fr-FR, hi-IN, it-IT, ja-JP, ko-KR, ru-RU, zh-CN,
  zh-HK, zh-TW). There, half of the people come from Faker and half from
  the locale's own list. It fails (or has no locale) in ar-AE, ar-EG
  (English names), ar-MA, fr-MA, fr-SN, it-CH (186 of 200 given names
  English), ru-BY, ru-KZ and zh-SG: own lists only.
* **Addresses: own lists everywhere** (conservative). Faker's addresses
  fail the rule in many locales (US-style addresses in ar-*, fr-BE, en-NG,
  it-CH; Suite/Apt. in fr-CA; wrong postcode formats in en-CA, es-AR,
  es-MX), and the own lists give each country's address order with real
  towns and real postcodes.
* Every locale has ≥ 60 given names, ≥ 60 family names, ≥ 40 streets and
  ≥ 30 places (checked by check 8).

## Generator (section 10)

* **Phone numbers** are random digits accepted by `phonenumbers` as valid
  fixed-line or mobile numbers of the region (not variations of the
  library's example number, which made every Italian number
  "02 1234 5678" - a shortcut the model could have learned).
* **E-mail and web domains** come from the name without its legal form.
  Japanese kanji get Japanese-sounding morphemes (no dictionary of readings
  is available); Arabic and Devanagari are transliterated.
* **Registration-number truth** is the letters and digits of the number as
  shown (`315095703 RT0001` → `315095703RT0001`), which is what
  `normalize()` returns.
* **Financial statements:** amounts are exact (no "in thousands" notes);
  the accounting period follows the fiscal year (April–March in India and
  Japan); an older statement never shows later years.
* **Contract amounts are O** (they are not invoice totals); **credit notes**
  carry a positive DOC_TOTAL; INSEE-style staff brackets are not used;
  Korean 업태 (business type) is O.
* **Spreadsheets:** when the first row of a sheet would carry labelled
  values (ingest.py repeats the first row as the key of every row), a
  neutral title row is put first. Receipts and credit notes are never
  spreadsheets; financial statements and registration documents are never
  CSV (a CSV cannot hold their signature lines).
* **Styles kept for the handwritten set only:** web-page chrome, forwarded
  e-mail chains, chat messages and typed copies of handwritten documents
  are not generated, so the handwritten set measures something the model
  has not seen in training.
* **Documents without an S** (letters from a bank, a tax office or a
  registry, rule R5): their date is O. DOC_DATE is a fact type, and rule
  R6 gives fact types to the S only. The handwritten set follows the same
  reading.
* **Label-free chunks (T12, ≥ 20% of train).** The composition of 10.4 is
  dominated by invoices, which are never label-free. The share was reached
  with realistic content, not with more "other" documents: general terms
  of sale printed on the back of invoices (60% in FR, BE, CH, IT, ES, MA,
  SN, CA; 35% elsewhere) and quotes (85% / 60%), where the company is
  named in the first article at most; 3–5 generic sections on web pages
  and brochures (values, why us, testimonials, news, FAQ); 2–4 extra
  sections in internal notes; long PDF documents split over pages.
* **Trap rates** are measured by `gen/checks.py` as follows: "every
  invoice" (T1, T6, T10, T15) means real invoices (layouts `invoice.*`);
  a till receipt or a credit note has no due date. Every invoice chunk
  that contains a DOC_TOTAL is tagged T1. The amount-in-words rate of the
  T10 countries is set to 50% per locale, because some layouts have no
  place for it.
* **Languages** are drawn in turn (folder index), so each has 10% of the
  folders; after generating `train`, extra folders are added for any
  language under 9% of the chunks (check 3b wants 10% ± 2 points).
* **Held-out splits.** A dev_heldout / test_heldout folder without a
  held-out activity uses held-out layouts wherever its document type has
  one, and held-out sentence templates whenever one fits. A receipt or
  credit note, which has no held-out layout of its own, then uses a
  held-out invoice layout.
* **A held-out registration layout made for companies only** (the
  Australian ASIC extract is held out; a sole trader has none): in a
  held-out folder that must use held-out items, such a business gets no
  registration document rather than one without any held-out item. Found
  when the pilot's generator check failed on 1 of 300 test_heldout
  folders; diagnosed and fixed on dev_heldout folders only (the same rule
  with D items), without looking at any test_heldout content.
* **test_locale:** clients and suppliers of a business in a held-out
  locale may come from that same locale. The rule "no client or supplier
  is drawn from a held-out locale" is applied to every other split (it is
  what keeps those locales out of training).
* **Hold-out draw** (section 11, seed 7, done once): per document type as
  required; registration layouts are grouped in country families keyed by
  locale, and only the 7 families with two layouts give one away (3 D,
  4 T). Sentence templates are held out per language and category for the
  11 fact types **and also for trap sentences (per trap id) and filler
  sentences** (more held out than required, never less). Result: 89
  train, 13 D, 15 T and 7 held-out-locale layouts; 490 T templates moved
  to `sentences_test.json`, 11 T layouts to `gen/layouts/test/`, 4 T
  registration families to `gen/layouts/test/registration_test.json`.

## Normalizer and verifier (section 14)

* `normalize()` passes all 111 cases of Appendix I and reads 99.97% of the
  generated spans back to their truth with the country known (check 5);
  94.7% with the language only.
* "Current year" for the sanity rules is `max(today, 2026)`, so data dated
  up to the reference date always passes.
* `B` as a magnitude (`$1.2B`) is read only in English; a lone `M` in
  Spanish is always ambiguous (Appendix I, case 103); `ريال` without a
  country gives the candidates SAR, QAR, OMR, YER.
* Month names come from the lexicons of all languages (every form), plus
  their accent-free spellings (`decembre`), because 5% of fr/es/it
  documents drop accents (10.7).
* The activity-code system is taken from the country (NAF, ATECO, NAICS
  …); `unknown` where the country has no system in the list of 14.2.
* The check digits of Appendix J are written in `verify.py` independently
  of the generator's own code in `gen/ids.py`; a test checks that 1,000
  generated numbers of each type pass `verify.py`. The spec gives no La
  Poste SIRET example; the test uses a constructed one (356 000 000 00010,
  digit sum 15).

## Test discipline

* `gen/checks.py` never prints or saves individual examples of
  test_heldout, test_locale or test_seen (it prints "example hidden").
  Before this was added, one check message showed the text of one
  test_heldout span (a date in upper case, from a generator bug). No
  model output was involved; the bug was fixed in the generator.
* The handwritten set was written by two writers who never opened
  `gen/`, so it is independent of the generator's templates. 100 chunks
  (10 per language), 1,531 spans, every doc-type minimum of Phase 1c met,
  every special style present (forwarded e-mail chains, web pages with
  menus / cookie banners / footers, chat messages, typed handwritten
  notes, invoices in an unusual order). Before freezing, one labelling
  choice was made consistent across the two writers: in a letter from a
  bank (no S, rule R5) the date is O (rule R6), as in the generator; two
  DOC_DATE labels were removed (hw-it-10, hw-ko-10). A financial
  statement keeps its facts even when a table fragment does not name the
  company, because the document's S exists (hw-ja-09).
* **Frozen** (never edited after this point; sha256):
  * `handwritten/ar.jsonl` 3f2904045c0a6f8876979f8d7d4292bdcc6069c198260b5983b045d1b4b4aec1
  * `handwritten/en.jsonl` ad4dd76fe906c73fe629efcf12323faa3d6450a8689fbe24a13a5ee9df5bb87d
  * `handwritten/es.jsonl` 66fb0c1d2ecf26860985d25f61d41bccfad57b3532a062d0335809f622b86eb0
  * `handwritten/fr.jsonl` cec9e030c9c3543984e9f96ecab49fa1d89e8bc39b0f8e82782ecbb17ed44be0
  * `handwritten/hi.jsonl` 0aacb872e5734e16b875669d9e6dcde83fe8209fa6d329b0e58e8f2d225469ea
  * `handwritten/it.jsonl` 4d8342a3fcef368794b3917cd6b3f665a3bcf01228478b76f33f19bb9b03a72d
  * `handwritten/ja.jsonl` 680eecec7c9a55233d20d539e141e9445418a21decb59c0848de6fbbe3a28fe1
  * `handwritten/ko.jsonl` 186318b872707eca605fedc2adf7e960ada45bce1e49830499434b88369073da
  * `handwritten/ru.jsonl` b58d47c4fe2f0458f489cd765332c0516c71f15a86536bc50e8c95f35166f897
  * `handwritten/zh.jsonl` 55ecf04d72c090b68157e7bf279918f47d751111cee4eb5a5cbb24b706b7d085

## Profile builder (section 15)

* **Two extra rules for joining names** (15.3 is not a FIXED section and
  invites extension). (1) A document has one S (rule R5), so every
  S_NAME of one file is the same organisation: a brochure that names both
  the trading name and the legal name joins them. (2) Two subjects that
  share a registration number, a phone number, an e-mail address or a web
  site are one organisation (a sole trader whose invoices show his own
  name and whose brochure shows his trade name). Without these, a
  business whose trading name shares no word with its legal name was
  split in two, and half of its documents were read as someone else's.
* **Authorship (15.5), one extra case:** a file with no S_NAME that shows
  one of the business's identifiers is by the business.
* **C_ facts of the business** are taken from files by others *and* from
  files with no S at all (letters from a bank or a tax office, where the
  business is C_).
* **Country vote (15.6):** every piece of evidence votes only when it
  points to one country among the countries of the folder's language
  (a number that fits the formats of two countries does not vote);
  country names count as whole words ("Cartagena de Indias" is not
  India); a bare "$" does not vote for the US; only the business's own
  facts vote.
* **Registration numbers** that fit no format of the voted country, or
  fail their check digit (an OCR slip), are listed as alternatives, not
  as values.
* **Legal forms written the same in two codes of one country** (Canada's
  "inc." in English and in French) are resolved by the language.
* **Measured with perfect spans** (the true spans fed through
  extract_db → verify → profile, 300 val folders): 99.7% of the fields of
  section 17 right; the misses are OCR-noised texts. So the profile
  builder itself costs almost nothing; the folder-level score measures
  the model.

## Build pipeline (sections 7-9, 12, 13, 17, 21)

* **Files not in the layout of section 20:** `report.py` (the report
  stage, split from `build.py` to keep that file readable) and
  `gold.py` (the loader of the hand-written and real_eval format, section
  20). `gen/checks.py`, `gen/faker_check.py` and `gen/holdout.py` belong
  to the generator.
* **`profile.py` and the standard library.** Python has a standard
  module called `profile`, which `cProfile` imports (PyTorch loads
  cProfile when an optimizer is made). The required file name hides it,
  so `profile.py` loads the standard module from the standard-library
  folder and hands on the three names cProfile uses (`run`, `runctx`,
  `_Utils`).
* **`corpus.py` runs as its own process** and leaves with `os._exit()`:
  the `datasets` library can crash when Python shuts down after
  streaming (seen here). Files are closed before.
* **Pretraining:** the learning rate of the first 20 steps (the ones that
  are timed to set the step count of the time cap) uses a warm-up of 50
  steps; after that the warm-up is max(50, 3% of the steps). The held-out
  1% of Wikipedia paragraphs is chosen by a hash of the text.
* **Fine-tuning:** "buckets of 100 x batch" is read as 100 times the
  number of chunks that fit in one token budget on average. Wikipedia
  batches use windows of 512 tokens. An epoch counts both kinds of
  batches (so 10% of an epoch's steps are Wikipedia).
* **Calibration:** the temperature is fitted on the true token labels of
  dev_heldout, using the first max_len tokens of the few chunks that are
  longer.
* **Evaluation definitions:** a relaxed match is the same label with an
  overlap of at least half of the longer span; T4 role accuracy is
  counted on the spans found with the right boundaries; the folder-level
  staff count is right when it agrees with the true number given its
  qualifier (about / more than / under / range); the true address may be
  written in any of its forms (one line, several lines); the true revenue
  is the most recent year that really appears in the folder.
* **Evaluation time in pretraining.** The masked-accuracy measurements
  (at step 1 and every 200 steps) are left out of the time cap and of
  the timing of the first 20 steps, as section 8 says. The first pilot
  run still counted them (the fix came while it was pretraining): it
  measured 4.44 s per step, about 0.5 s too much, and planned 810 steps
  instead of about 900 (it ran all 810 in 58.2 minutes). Its fine-tuning,
  calibration and evaluation ran with the code of this package; only its
  pretraining ran the earlier accounting. Any later run uses the fixed
  code and so pretrains a little longer.
* **Out of memory in fine-tuning.** Section 12 takes its optimizer and
  precision rules from 9.5, which says never to crash on an out-of-memory
  error. Fine-tuning therefore cuts a batch into 2, 4, 8 ... parts on
  such an error and adds up their gradients; the loss of each part is
  divided by the counts of the whole batch, so the result is the same as
  one pass (checked: equal losses, gradients within 4e-7 for 1, 3 and 14
  parts). Pretraining raises the error instead of looping forever when
  its micro-batch is already 1. Both use `torch.cuda.OutOfMemoryError`
  when `torch.OutOfMemoryError` does not exist (torch 2.4).
* **Devices.** Calibration and evaluation run on the GPU when there is
  one (the whole evaluation of the full preset would take hours on a
  CPU); the speed measurement of section 17 always runs on the CPU.
* **Speed and peak RAM** are measured in a fresh process that loads only
  the Extractor, so the peak RAM is the Extractor's own (about 0.6 GB for
  the smoke model), not that of the evaluation holding every split in
  memory (8 GB). The peak is read with `resource` on Linux and macOS and
  with `GetProcessMemoryInfo` on Windows, where `resource` does not exist.
* **Loading the packed fine-tuning data** reads each array of the `.npz`
  once. The first version sliced `z["ids"]` chunk by chunk; with `.npz`
  files every such access unpacks the whole array again and each slice
  keeps its copy alive, so the smoke train split took 7.4 GB (37 MB now)
  and the pilot's would not have fitted in any memory. Found before the
  pilot's fine-tuning started, by measuring a smoke run.
* **The time-capped stages time their first 20 steps.** Anything else
  running on the machine at that moment lowers the step count of the
  whole stage. It happened once here: a test run during the pilot's
  first pretraining minutes measured 17.5 s per step (205 steps); the
  stage was restarted before its first checkpoint and measured 4.4 s per
  step (810 steps). Nothing heavy runs next to a timed stage since.
* **Work in progress was committed and pushed to the branch
  `claude/attached-instructions-vz6bdr` of the repository this session
  works in**, which is how this environment delivers work to its user.
  Nothing else left the environment (Wikipedia and pip packages were
  downloaded, as allowed).

## Improvement rounds

(Filled in after each round: what was seen on val / dev_heldout, with
counts; what was changed; dev_heldout before and after.)

## Suggestions (for FIXED sections - not applied)

* none yet
