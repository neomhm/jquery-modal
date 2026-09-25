# REPORT - The Extractor 1.0.0

## 1. Summary

Presets run: smoke. The last one, **smoke**, was evaluated on every set.  
No gate for smoke (section 17); 8 of the full gate's lines would fail.  
Most important next step: build the full model on a GPU - `py build.py full` on the desktop, or the MEGA9 /train card.

## 2. Environment

| item | value |
|---|---|
| os | Linux 6.18.44-fc-v37 |
| python | 3.11.15 |
| torch | 2.14.0+cu130 |
| device |  |
| backend | cpu |
| cpu_count | 4 |
| ram_gb | 16.9 |
| free_disk_gb | 22.7 |
| wiki_reachable | True |

smoke: Wikipedia not used (smoke) 

## 3. Data

### smoke

| split | folders | documents | chunks | empty chunks | chunks per language |
|---|---|---|---|---|---|
| train | 64 | 1427 | 3269 | 20.8% | ar 296 en 318 es 365 fr 319 hi 317 it 385 ja 318 ko 303 ru 306 zh 342 |
| val | 10 | 219 | 472 | 26.1% | ar 33 en 43 es 77 fr 42 hi 55 it 35 ja 52 ko 38 ru 38 zh 59 |
| dev_heldout | 10 | 227 | 590 | 25.8% | ar 49 en 79 es 62 fr 60 hi 71 it 69 ja 40 ko 66 ru 50 zh 44 |
| test_seen | 10 | 218 | 490 | 23.5% | ar 46 en 35 es 31 fr 54 hi 47 it 61 ja 48 ko 62 ru 62 zh 44 |
| test_heldout | 10 | 214 | 570 | 24.4% | ar 64 en 51 es 72 fr 59 hi 49 it 62 ja 39 ko 56 ru 51 zh 67 |
| test_locale | 5 | 101 | 237 | 30.0% | ar 50 en 49 es 55 fr 45 it 38 |
| traps | 3 | 52 | 124 | 9.7% | ar 43 en 39 zh 42 |

Train chunks per document type: brochure 542, contract 82, financials 54, invoice 1753, letter 217, other 253, price_list 31, quote 202, registration 70, staff_list 20, terms 45.  
Per source format: csv 7, docx 466, md 258, pdf 2131, txt 266, xlsx 141.  
Spans per label: ACTIVITY 166, ACTIVITY_CODE 16, CAPITAL 32, CERT 20, C_ADDRESS 653, C_NAME 946, C_REG_ID 394, DOC_DATE 1141, DOC_TOTAL 1047, FOUNDED 73, HOURS 30, LEGAL_FORM 62, LINE_TOTAL 3300, PRICE 3201, REVENUE 119, REVENUE_YEAR 114, SERVICE 4560, STAFF 85, S_ADDRESS 1592, S_EMAIL 426, S_NAME 2185, S_PERSON 442, S_PHONE 985, S_REG_ID 783, S_URL 312.

Generator self-checks (10.9):

```
PASS  1 spans valid                      5752 chunks, 0 problems []
PASS  2a truth for normalizable spans    20572 spans, 0 without truth []
PASS  2b chunks == verbatim ingest.py    1001 documents, 0 differ
PASS  3a label-free train chunks         20.8% of 3269
PASS  3b languages 10% +- 2 points       ar 9.1 zh 10.5 en 9.7 fr 9.8 ru 9.4 es 11.2 it 11.8 hi 9.7 ja 9.7 ko 9.3
PASS  4 T1 invoices                      100.0% (min 97%)
PASS  4 T1 brochure+financial chunks     18.1% (min 10%)
PASS  4 T2 financial statements          97.5% (min 97%)
PASS  4 T3 financial statements          65.0% (min 60%)
PASS  4 T4 invoices                      27.8% (min 20%)
PASS  4 T5 brochure chunks               32.3% (min 15%)
PASS  4 T6 invoices                      100.0% (min 97%)
PASS  4 T7 brochure chunks               36.9% (min 20%)
PASS  4 T8 brochure chunks               41.0% (min 20%)
PASS  4 T9 invoices                      35.7% (min 30%)
PASS  4 T10 invoices (listed countries)  36.1% (min 30%)
PASS  4 T10 invoices (elsewhere)         20.7% (min 10%)
PASS  4 T11 letters+brochures            54.9% (min 20%)
PASS  4 T12 chunks                       20.8% (min 20%)
PASS  4 T13 brochure chunks              16.4% (min 10%)
PASS  4 T14 registration+financials      100.0% (min 97%)
PASS  4 T15 invoices                     99.3% (min 97%)
PASS  5 normalize() == truth (country)   99.97% of 20572
      normalize() with the language only: 94.68% of 20572
PASS  6a hold-out ids                    0 problems []
PASS  6b dev_heldout content rule        0 of 10 folders break it
PASS  6b test_heldout content rule       0 of 10 folders break it
PASS  8 Faker rule                       24 locales use Faker for names; 0 problems []
```

Boundary rate 100.000% (7097 spans of val + dev_heldout). Characters per token (val): ar 2.10, en 2.20, es 2.40, fr 2.45, hi 2.16, it 2.60, ja 1.12, ko 1.21, ru 2.17, zh 1.05.

## 4. Models

| preset | d/layers/heads/ffn | vocab | pretrain steps | pretrain min | masked acc | finetune steps | finetune min | dev_heldout F1 (no thresholds) | temperature |
|---|---|---|---|---|---|---|---|---|---|
| smoke | 128/2/2/352 | 8000 | 100 | 0.2 | 0.0783 | 150 | 0.1 | 0.0 | 0.85 |

## 5. Results

### smoke

| # | measure | target (full) | measured | result |
|---|---|---|---|---|
| 1 | test_seen strict micro-F1 | >= 0.97 | 0.0 | FAIL |
| 2 | test_heldout strict micro-F1 | >= 0.92 | 0.0 | FAIL |
| 3 | test_heldout micro-F1, every language | >= 0.88 | 0.0000 (ar) | FAIL |
| 4 | test_heldout F1 of the 13 key labels (lowest) | >= 0.85 | 0.0000 (ACTIVITY) | FAIL |
| 5 | traps: REVENUE precision (T1-T3) | >= 0.97 | 1.0 | PASS |
| 6 | traps: role swaps (T4) | <= 2% | 0.0 | PASS |
| 7 | false spans per 100 empty chunks (T12) | <= 2 | 0.0 | PASS |
| 8 | doc-type accuracy (test_heldout) | >= 0.93 | 0.5947 | FAIL |
| 9 | language accuracy (test_heldout) | >= 0.99 | 0.1333 | FAIL |
| 10 | folder level, test_heldout: 11 REQUIRED fields | >= 0.90 | 0.1091 | FAIL |
| 11 | folder level: business name | >= 0.97 | 0.0 | FAIL |
| 12 | folder level: invented values | = 0 | 0 | PASS |
| 13 | tokenizer boundary rate | >= 99.5% | 100.000% | PASS |
| 14 | normalizer on generated spans, true country | >= 99% | 99.97% (language only 94.68%) | PASS |
| 15 | handwritten set micro-F1 | report (0.80 hoped) | 0.0 | report |
| 16 | test_locale micro-F1 / calibration error (ECE, test_heldout) / speed | report | 0.0 / 0.0 / 157.18 | report |

Full tables: `runs/smoke/eval_tables.md` (delivered with this report).

## 6. Error analysis (dev_heldout and val only)

| label | lang | doc type | kind | count | two examples |
|---|---|---|---|---|---|
| SERVICE | hi | invoice | missed | 160 | `एसी वार्षिक   रखरखाव अनुबंध (एएमसी)` · `सबमर्सिबल पंप इंस्टॉलेशन` |
| LINE_TOTAL | hi | invoice | missed | 159 | `4,733.60` · `33,929.35` |
| SERVICE | ja | invoice | missed | 135 | `卒業アルバム制作` · `出張撮影（1時間）` |
| SERVICE | en | invoice | missed | 134 | `Vine tomatoes` · `Bananas` |
| PRICE | hi | invoice | missed | 130 | `2,366.80` · `2,609.95` |
| LINE_TOTAL | en | invoice | missed | 129 | `$53.20` · `$ 12.07` |
| LINE_TOTAL | ja | invoice | missed | 125 | `22,441` · `22,326` |
| SERVICE | ko | invoice | missed | 118 | `계약서 검토` · `변호사 자문 (타임차지)` |
| SERVICE | zh | invoice | missed | 117 | `燃气壁挂炉安装` · `坐便器安装` |
| PRICE | en | invoice | missed | 115 | `12.13` · `13.94` |

## 7. Improvement rounds

None yet.

## 8. Deviations and decisions

Every decision is in `DECISIONS.md`, by topic: Environment, Language data (section 10.2), Names and addresses: the Faker rule (section 10.3), Generator (section 10), Normalizer and verifier (section 14), Test discipline, Profile builder (section 15), Suggestions (for FIXED sections - not applied).

## 9. Known limits

* The training data is synthetic: generated documents in ten languages,
  plus Wikipedia for pretraining. Real documents will surprise it; the
  handwritten set is the closest measure of that.
* No OCR: scanned PDFs give no text to ingest.py, so nothing to extract.
* Arabic PDFs may come out of pdfplumber in visual (reversed) order.
* Hindi PDFs with legacy fonts may garble the vowel signs.
* Languages outside the ten are not supported (the language head will
  still name one of the ten).

## 10. Next steps for Laurent

Build the full model on the desktop (GPU), in `C:\Users\neomh\new model\extractor`:

```powershell
py build.py full
```

Or upload `extractor-package.zip` to the /train card and choose MEGA9.

Then use it on a folder, on the laptop:

```powershell
py extract_db.py "C:\Users\Laurent\new model\documents.db"
```

```powershell
py profile.py "C:\Users\Laurent\new model\documents.db"
```
