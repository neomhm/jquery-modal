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
  `gen/`, so it is independent of the generator's templates.

## Suggestions (for FIXED sections - not applied)

* none yet
