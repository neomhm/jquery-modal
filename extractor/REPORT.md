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
| backend | cpu |
| gpu | False |
| device_name |  |
| device_memory_gb |  |
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

| preset | parameters | d/layers/heads/ffn | vocab | pretrain steps | pretrain min | final MLM loss (held-out) | masked-LM accuracy | finetune steps | finetune min | final finetune loss | chosen step | dev_heldout F1 (sample, no thresholds) | temperature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| smoke | 1.5M | 128/2/2/352 | 8000 | 100 | 0.2 | 6.6451 | 0.0783 | 150 | 0.1 |  | 150 | 0.0 | 0.85 |

The fine-tuning loss is CE(tokens) + 0.3 CE(doc type) + 0.1 CE(language), smoothed over the last steps. The masked-LM numbers are measured on held-out Wikipedia and synthetic text.

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

### Calibration (smoke)

Temperature 0.85 and the per-label thresholds are fitted on dev_heldout (rules: 25 by 'best F1'). Expected calibration error (10 bins) of the accepted span scores, per split: val 0.0000, dev_heldout 0.0000, test_seen 0.0000, test_heldout 0.0000, test_locale 0.0000, traps 0.0000.

| label | threshold | rule | precision | recall | predicted | gold |
|---|---|---|---|---|---|---|
| S_NAME | 0.3 | best F1 | 0.0 | 0.0 | 0 | 349 |
| S_ADDRESS | 0.3 | best F1 | 0.0 | 0.0 | 0 | 241 |
| S_REG_ID | 0.3 | best F1 | 0.0 | 0.0 | 0 | 130 |
| S_PHONE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 169 |
| S_EMAIL | 0.3 | best F1 | 0.0 | 0.0 | 0 | 107 |
| S_URL | 0.3 | best F1 | 0.0 | 0.0 | 0 | 57 |
| S_PERSON | 0.3 | best F1 | 0.0 | 0.0 | 0 | 68 |
| C_NAME | 0.3 | best F1 | 0.0 | 0.0 | 0 | 168 |
| C_ADDRESS | 0.3 | best F1 | 0.0 | 0.0 | 0 | 91 |
| C_REG_ID | 0.3 | best F1 | 0.0 | 0.0 | 0 | 48 |
| LEGAL_FORM | 0.3 | best F1 | 0.0 | 0.0 | 0 | 3 |
| CAPITAL | 0.3 | best F1 | 0.0 | 0.0 | 0 | 12 |
| FOUNDED | 0.3 | best F1 | 0.0 | 0.0 | 0 | 24 |
| STAFF | 0.3 | best F1 | 0.0 | 0.0 | 0 | 3 |
| REVENUE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 17 |
| REVENUE_YEAR | 0.3 | best F1 | 0.0 | 0.0 | 0 | 19 |
| ACTIVITY | 0.3 | best F1 | 0.0 | 0.0 | 0 | 28 |
| ACTIVITY_CODE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 2 |
| SERVICE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 783 |
| HOURS | 0.3 | best F1 | 0.0 | 0.0 | 0 | 0 |
| CERT | 0.3 | best F1 | 0.0 | 0.0 | 0 | 0 |
| DOC_DATE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 171 |
| DOC_TOTAL | 0.3 | best F1 | 0.0 | 0.0 | 0 | 188 |
| LINE_TOTAL | 0.3 | best F1 | 0.0 | 0.0 | 0 | 663 |
| PRICE | 0.3 | best F1 | 0.0 | 0.0 | 0 | 597 |

### Detailed tables (smoke)

The same tables are in `runs/smoke/eval_tables.md`.

### Spans

| split | chunks | strict F1 | P | R | relaxed F1 | role swaps | doc type acc | lang acc | false/100 empty | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| val | 472 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.6081 | 0.1843 | 0.0 | 0.0 |
| dev_heldout | 590 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.6237 | 0.1458 | 0.0 | 0.0 |
| test_seen | 490 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.6102 | 0.1837 | 0.0 | 0.0 |
| test_heldout | 570 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5947 | 0.1333 | 0.0 | 0.0 |
| test_locale | 237 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5401 | 0.038 | 0.0 | 0.0 |
| traps | 124 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.75 | 0.0484 | 0.0 | 0.0 |

### Per label (test_heldout)

| label | F1 | P | R | gold |
|---|---|---|---|---|
| ACTIVITY | 0.0 | 0.0 | 0.0 | 29 |
| ACTIVITY_CODE | 0.0 | 0.0 | 0.0 | 6 |
| CAPITAL | 0.0 | 0.0 | 0.0 | 2 |
| CERT | 0.0 | 0.0 | 0.0 | 1 |
| C_ADDRESS | 0.0 | 0.0 | 0.0 | 82 |
| C_NAME | 0.0 | 0.0 | 0.0 | 141 |
| C_REG_ID | 0.0 | 0.0 | 0.0 | 69 |
| DOC_DATE | 0.0 | 0.0 | 0.0 | 170 |
| DOC_TOTAL | 0.0 | 0.0 | 0.0 | 182 |
| FOUNDED | 0.0 | 0.0 | 0.0 | 14 |
| HOURS | 0.0 | 0.0 | 0.0 | 2 |
| LEGAL_FORM | 0.0 | 0.0 | 0.0 | 7 |
| LINE_TOTAL | 0.0 | 0.0 | 0.0 | 699 |
| PRICE | 0.0 | 0.0 | 0.0 | 676 |
| REVENUE | 0.0 | 0.0 | 0.0 | 29 |
| REVENUE_YEAR | 0.0 | 0.0 | 0.0 | 26 |
| SERVICE | 0.0 | 0.0 | 0.0 | 789 |
| STAFF | 0.0 | 0.0 | 0.0 | 15 |
| S_ADDRESS | 0.0 | 0.0 | 0.0 | 235 |
| S_EMAIL | 0.0 | 0.0 | 0.0 | 34 |
| S_NAME | 0.0 | 0.0 | 0.0 | 315 |
| S_PERSON | 0.0 | 0.0 | 0.0 | 73 |
| S_PHONE | 0.0 | 0.0 | 0.0 | 102 |
| S_REG_ID | 0.0 | 0.0 | 0.0 | 176 |
| S_URL | 0.0 | 0.0 | 0.0 | 22 |

### Per language (test_heldout)

| lang | F1 | P | R |
|---|---|---|---|
| ar | 0.0 | 0.0 | 0.0 |
| en | 0.0 | 0.0 | 0.0 |
| es | 0.0 | 0.0 | 0.0 |
| fr | 0.0 | 0.0 | 0.0 |
| hi | 0.0 | 0.0 | 0.0 |
| it | 0.0 | 0.0 | 0.0 |
| ja | 0.0 | 0.0 | 0.0 |
| ko | 0.0 | 0.0 | 0.0 |
| ru | 0.0 | 0.0 | 0.0 |
| zh | 0.0 | 0.0 | 0.0 |

### Per document type (test_heldout)

| doc type | F1 | P | R |
|---|---|---|---|
| brochure | 0.0 | 0.0 | 0.0 |
| contract | 0.0 | 0.0 | 0.0 |
| financials | 0.0 | 0.0 | 0.0 |
| invoice | 0.0 | 0.0 | 0.0 |
| letter | 0.0 | 0.0 | 0.0 |
| other | 1.0 | 1.0 | 1.0 |
| price_list | 0.0 | 0.0 | 0.0 |
| quote | 0.0 | 0.0 | 0.0 |
| registration | 0.0 | 0.0 | 0.0 |
| staff_list | 0.0 | 0.0 | 0.0 |
| terms | 0.0 | 0.0 | 0.0 |

### Per source format (test_heldout)

| source | F1 | P | R |
|---|---|---|---|
| docx | 0.0 | 0.0 | 0.0 |
| md | 0.0 | 0.0 | 0.0 |
| pdf | 0.0 | 0.0 | 0.0 |
| txt | 0.0 | 0.0 | 0.0 |
| xlsx | 0.0 | 0.0 | 0.0 |

### Traps

| trap | chunks | scores |
|---|---|---|
| T1 | 49 | REVENUE_precision 1.0, DOC_TOTAL_f1 0.0 |
| T4 | 23 | role_accuracy 0.0, role_swap_rate 0.0 |
| T5 | 25 | false_S_or_fact_per_100_chunks 0.0 |
| T6 | 45 | S_PHONE_precision 0.0, S_REG_ID_precision 0.0 |
| T7 | 27 | FOUNDED_precision 0.0 |
| T8 | 28 | STAFF_precision 0.0 |
| T9 | 35 | SERVICE_precision 0.0 |
| T10 | 12 | DOC_TOTAL_precision 0.0 |
| T11 | 30 | S_PERSON_precision 1.0 |
| T12 | 12 | false_spans_per_100_empty 0.0 |
| T13 | 12 | C_NAME_f1 0.0 |
| T14 | 4 | S_NAME_precision 0.0 |
| T15 | 26 | DOC_DATE_precision 0.0 |
| T1-T3 REVENUE precision |  | 1.0 |

### Folder level (test_heldout)

| field | accuracy |
|---|---|
| business_name | 0.0 |
| address | 0.0 |
| reg_id | 0.0 |
| contact | 0.0 |
| legal_form | 0.2 |
| founded | 0.4 |
| staff | 0.2 |
| activity | 0.1 |
| activity_code | 0.8 |
| capital | 0.9 |
| revenue | 0.3 |
| services | 0.0 |
| clients | 0.0 |
| country | 0.0 |
| REQUIRED mean | 0.1091 |
| invented values | 0 |
| conflicts per folder | 0.0 |
| coverage error | 0.8909 |
| folders | 10 |

### Folder level (test_seen)

| field | accuracy |
|---|---|
| business_name | 0.0 |
| address | 0.0 |
| reg_id | 0.0 |
| contact | 0.0 |
| legal_form | 0.1 |
| founded | 0.4 |
| staff | 0.5 |
| activity | 0.2 |
| activity_code | 0.9 |
| capital | 0.9 |
| revenue | 0.6 |
| services | 0.0 |
| clients | 0.0 |
| country | 0.0 |
| REQUIRED mean | 0.1636 |
| invented values | 0 |
| conflicts per folder | 0.0 |
| coverage error | 0.8364 |
| folders | 10 |

### handwritten

| chunks | strict F1 | P | R | relaxed F1 |
|---|---|---|---|---|
| 100 | 0.0 | 0.0 | 0.0 | 0.0 |

### Speed

157.18 chunks/s on CPU (threads 4, batch 16, 500 chunks), peak RAM 8046.8 MB

### Tokenizer

boundary rate 100.000%; characters per token: ar 2.10, en 2.20, es 2.40, fr 2.45, hi 2.16, it 2.60, ja 1.12, ko 1.21, ru 2.17, zh 1.05


## 6. Error analysis (dev_heldout only)

The ten largest groups of errors of the last model on dev_heldout, by label x language x document type x kind.

| label | lang | doc type | kind | count | two examples |
|---|---|---|---|---|---|
| LINE_TOTAL | hi | invoice | missed | 111 | `५.१७` in "ेड छपाई; मात्रा (नग): १; रेट: ५.१७; राशि: ५.१७ / Item Code: १९०५"<br>`८४.३०` in "रा (नग): ६; रेट: १४.०५; राशि: ८४.३० / Item Code: ९९८३; विवरण: लेट" |
| SERVICE | hi | invoice | missed | 111 | `ब्लैक एंड व्हाइट फ़ोटोकॉपी` in "ाशि / Item Code: १९०५; विवरण: ब्लैक एंड व्हाइट फ़ोटोकॉपी; मात्रा (नग): २; रेट: १.९४; र"<br>`स्पाइरल बाइंडिंग` in ".४४ / Item Code: ९९८७; विवरण: स्पाइरल बाइंडिंग; मात्रा (नग): १; रेट: ४५.२०; " |
| SERVICE | en | invoice | missed | 86 | `Cross-docking` in "99; Net: 39.80 / Particulars: Cross-docking; Quantity: 7; Rate: 24.75; Ne"<br>`Flatbed haulage` in ".35; Net: 4.55 / Particulars: Flatbed haulage; Quantity: 20; Rate: 1.99; Ne" |
| LINE_TOTAL | en | invoice | missed | 86 | `4.55` in "uantity: 13; Rate: 0.35; Net: 4.55 / Particulars: Flatbed haulag"<br>`173.25` in "uantity: 7; Rate: 24.75; Net: 173.25 / Particulars: Discount Appli" |
| PRICE | en | invoice | missed | 84 | `1.99` in " haulage; Quantity: 20; Rate: 1.99; Net: 39.80 / Particulars: Cr"<br>`0.35` in " freight; Quantity: 13; Rate: 0.35; Net: 4.55 / Particulars: Fla" |
| PRICE | hi | invoice | missed | 83 | `१.९४` in "ोटोकॉपी; मात्रा (नग): २; रेट: १.९४; राशि: ३.८८ / Item Code: ९९८७"<br>`९२०.८६` in "रतियाँ); मात्रा (नग): ४; रेट: ९२०.८६; राशि: ३,६८३.४४ / Item Code: " |
| LINE_TOTAL | it | invoice | missed | 72 | `385,70` in "itario: 38,57; Importo netto: 385,70 / #: 3; Descrizione prodotto:"<br>`75,05` in "itario: 15,01; Importo netto: 75,05 / Descrizione prodotto: Spese" |
| SERVICE | it | invoice | missed | 72 | `Grissini stirati a mano` in "/ #: 5; Descrizione prodotto: Grissini stirati a mano; Q.tà: 5; Unità: kg; Importo "<br>`Torta nuziale a piani` in "/ #: 3; Descrizione prodotto: Torta nuziale a piani; Q.tà: 11; Unità: kg; Importo" |
| LINE_TOTAL | es | invoice | missed | 65 | `530.9` in " col2: 10; col3: 53.09; col4: 530.9 / Expedidor:: P-931; col1: Re"<br>`294.48` in " col2: 12; col3: 24.54; col4: 294.48 / Expedidor:: 141388; col1: M" |
| SERVICE | es | invoice | missed | 65 | `Curso de inglés para empresas (in company)` in "pedidor:: 347514733460; col1: Curso de inglés para empresas (in company); col2: 10; col3: 53.09; col4:"<br>`Mensualidad del curso de alemán` in "8 / Expedidor:: 141388; col1: Mensualidad del curso de alemán; col2: 7; col3: 107.01; col4:" |

## 7. Improvement rounds

(Filled in after each round: what was seen on val / dev_heldout, with
counts; what was changed; dev_heldout before and after.)

## 8. Deviations and decisions

Every decision is in `DECISIONS.md`, by topic: Environment, Language data (section 10.2), Names and addresses: the Faker rule (section 10.3), Generator (section 10), Normalizer and verifier (section 14), Test discipline, Profile builder (section 15), Build pipeline (sections 7-9, 12, 13, 17, 21), Improvement rounds, Suggestions (for FIXED sections - not applied).

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

**Build the full model** on the desktop (GPU). In PowerShell:

```powershell
cd "C:\Users\neomh\new model\extractor"
```

```powershell
py check.py
```

```powershell
py build.py full
```

Or upload `extractor-package.zip` to the /train card and choose MEGA9.
It takes about 6 to 10 hours; it writes `extractor-1.0.0.pt` and a new
`REPORT.md` with the gate of section 17.

**Use it on a real folder.** Copy `extractor-1.0.0.pt` to
`C:\Users\Laurent\new model\extractor` on the laptop, then:

```powershell
cd "C:\Users\Laurent\new model"
```

```powershell
py ingest.py "C:\Users\Laurent\documents to publish"
```

```powershell
cd "C:\Users\Laurent\new model\extractor"
```

```powershell
py extract_db.py "C:\Users\Laurent\new model\documents.db"
```

```powershell
py profile.py "C:\Users\Laurent\new model\documents.db"
```

**Measure it on real documents.** Label a few real chunks in
`real_eval\` (see `README.md`), then, on the desktop:

```powershell
py build.py full --from evaluate
```
