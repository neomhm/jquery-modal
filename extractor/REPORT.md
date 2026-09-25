# REPORT - The Extractor 1.0.0

## 1. Summary

Presets run: smoke, pilot. The last one, **pilot**, was evaluated on val and dev_heldout only (dev-only run).  
No gate for pilot (section 17); 0 of the full gate's lines would fail.  
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
pilot: Wikipedia used {'ar': '10.0M', 'zh': '3.0M', 'en': '10.0M', 'fr': '10.0M', 'ru': '10.0M', 'es': '10.0M', 'it': '10.0M', 'hi': '10.0M', 'ja': '3.0M', 'ko': '4.0M'}

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

### pilot

| split | folders | documents | chunks | empty chunks | chunks per language |
|---|---|---|---|---|---|
| train | 3010 | 66693 | 157496 | 22.3% | ar 15286 en 17091 es 16874 fr 17824 hi 15023 it 17346 ja 14176 ko 14227 ru 15448 zh 14201 |
| val | 150 | 3359 | 7959 | 21.1% | ar 758 en 913 es 885 fr 826 hi 748 it 911 ja 710 ko 737 ru 745 zh 726 |
| dev_heldout | 300 | 6543 | 15379 | 22.8% | ar 1441 en 1712 es 1632 fr 1729 hi 1498 it 1709 ja 1318 ko 1458 ru 1514 zh 1368 |
| test_seen | 300 | 6603 | 15482 | 22.9% | ar 1519 en 1715 es 1751 fr 1619 hi 1647 it 1646 ja 1385 ko 1300 ru 1543 zh 1357 |
| test_heldout | 300 | 6584 | 15376 | 24.2% | ar 1607 en 1687 es 1513 fr 1683 hi 1557 it 1793 ja 1352 ko 1311 ru 1473 zh 1400 |
| test_locale | 100 | 2200 | 5449 | 23.5% | ar 812 en 817 es 846 fr 829 it 806 ru 696 zh 643 |
| traps | 24 | 431 | 1020 | 12.3% | ar 136 en 137 es 83 fr 124 hi 79 it 83 ja 90 ko 81 ru 103 zh 104 |

Train chunks per document type: brochure 26993, contract 3575, financials 2524, invoice 81960, letter 9384, other 13342, price_list 1390, quote 12308, registration 2865, staff_list 1006, terms 2149.  
Per source format: csv 231, docx 24346, md 14562, pdf 100341, txt 10827, xlsx 7189.  
Spans per label: ACTIVITY 8231, ACTIVITY_CODE 898, CAPITAL 1486, CERT 859, C_ADDRESS 31837, C_NAME 46562, C_REG_ID 19581, DOC_DATE 53193, DOC_TOTAL 51064, FOUNDED 3670, HOURS 1209, LEGAL_FORM 2809, LINE_TOTAL 163898, PRICE 161134, REVENUE 6144, REVENUE_YEAR 5824, SERVICE 219358, STAFF 3610, S_ADDRESS 73533, S_EMAIL 20204, S_NAME 98673, S_PERSON 19684, S_PHONE 46674, S_REG_ID 36448, S_URL 13195.

Generator self-checks (10.9):

```
PASS  1 spans valid                      218161 chunks, 0 problems []
PASS  2a truth for normalizable spans    796461 spans, 0 without truth []
PASS  2b chunks == verbatim ingest.py    1001 documents, 0 differ
PASS  3a label-free train chunks         22.3% of 157496
PASS  3b languages 10% +- 2 points       ar 9.7 zh 9.0 en 10.9 fr 11.3 ru 9.8 es 10.7 it 11.0 hi 9.5 ja 9.0 ko 9.0
PASS  4 T1 invoices                      100.0% (min 97%)
PASS  4 T1 brochure+financial chunks     18.7% (min 10%)
PASS  4 T2 financial statements          98.5% (min 97%)
PASS  4 T3 financial statements          77.1% (min 60%)
PASS  4 T4 invoices                      27.1% (min 20%)
PASS  4 T5 brochure chunks               30.9% (min 15%)
PASS  4 T6 invoices                      100.0% (min 97%)
PASS  4 T7 brochure chunks               37.1% (min 20%)
PASS  4 T8 brochure chunks               38.9% (min 20%)
PASS  4 T9 invoices                      35.2% (min 30%)
PASS  4 T10 invoices (listed countries)  33.3% (min 30%)
PASS  4 T10 invoices (elsewhere)         20.9% (min 10%)
PASS  4 T11 letters+brochures            61.3% (min 20%)
PASS  4 T12 chunks                       22.3% (min 20%)
PASS  4 T13 brochure chunks              16.8% (min 10%)
PASS  4 T14 registration+financials      98.8% (min 97%)
PASS  4 T15 invoices                     99.7% (min 97%)
PASS  5 normalize() == truth (country)   99.95% of 796461
      normalize() with the language only: 94.35% of 796461
PASS  6a hold-out ids                    0 problems []
PASS  6b dev_heldout content rule        0 of 300 folders break it
PASS  6b test_heldout content rule       0 of 300 folders break it
PASS  8 Faker rule                       24 locales use Faker for names; 0 problems []
```

Boundary rate 100.000% (160795 spans of val + dev_heldout). Characters per token (val): ar 2.70, en 2.63, es 2.76, fr 2.97, hi 2.50, it 3.00, ja 1.14, ko 1.28, ru 2.66, zh 1.17.

## 4. Models

| preset | parameters | d/layers/heads/ffn | vocab | pretrain steps | pretrain min | final MLM loss (held-out) | masked-LM accuracy | finetune steps | finetune min | final finetune loss | chosen step | dev_heldout F1 (sample, no thresholds) | temperature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| smoke | 1.5M | 128/2/2/352 | 8000 | 100 | 0.2 | 6.6451 | 0.0783 | 150 | 0.1 |  | 150 | 0.0 | 0.5 |
| pilot | 11.5M | 256/4/4/704 | 32000 | 810 | 58.2 | 5.0484 | 0.2311 | 4627 | 79.3 | 0.0431 | 4374 | 0.9527 | 1.25 |

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

### pilot (dev-only)

| # | measure | target (full) | measured | result |
|---|---|---|---|---|
| 1 | test_seen strict micro-F1 | >= 0.97 | not measured | - |
| 2 | test_heldout strict micro-F1 | >= 0.92 | not measured | - |
| 3 | test_heldout micro-F1, every language | >= 0.88 | not measured | - |
| 4 | test_heldout F1 of the 13 key labels (lowest) | >= 0.85 | not measured | - |
| 5 | traps: REVENUE precision (T1-T3) | >= 0.97 | not measured | - |
| 6 | traps: role swaps (T4) | <= 2% | not measured | - |
| 7 | false spans per 100 empty chunks (T12) | <= 2 | not measured | - |
| 8 | doc-type accuracy (test_heldout) | >= 0.93 | not measured | - |
| 9 | language accuracy (test_heldout) | >= 0.99 | not measured | - |
| 10 | folder level, test_heldout: 11 REQUIRED fields | >= 0.90 | not measured | - |
| 11 | folder level: business name | >= 0.97 | not measured | - |
| 12 | folder level: invented values | = 0 | 0 | PASS |
| 13 | tokenizer boundary rate | >= 99.5% | 100.000% | PASS |
| 14 | normalizer on generated spans, true country | >= 99% | 99.95% (language only 94.35%) | PASS |
| 15 | handwritten set micro-F1 | report (0.80 hoped) | not measured | report |
| 16 | test_locale micro-F1 / calibration error (ECE, test_heldout) / speed | report | None / None / None | report |

### Calibration (pilot)

Temperature 1.25 and the per-label thresholds are fitted on dev_heldout (rules: 20 by 'precision>=0.97', 5 by 'best F1'). Expected calibration error (10 bins) of the accepted span scores, per split: val 0.0026, dev_heldout 0.0169.

| label | threshold | rule | precision | recall | predicted | gold |
|---|---|---|---|---|---|---|
| S_NAME | 0.85 | precision>=0.97 | 0.9728 | 0.9075 | 8339 | 8939 |
| S_ADDRESS | 0.3 | precision>=0.97 | 0.9805 | 0.9891 | 6657 | 6599 |
| S_REG_ID | 0.3 | precision>=0.97 | 0.9768 | 0.9763 | 4224 | 4226 |
| S_PHONE | 0.3 | precision>=0.97 | 0.9841 | 0.9918 | 4790 | 4753 |
| S_EMAIL | 0.3 | precision>=0.97 | 0.9864 | 0.986 | 2861 | 2862 |
| S_URL | 0.3 | precision>=0.97 | 0.982 | 0.9868 | 1671 | 1663 |
| S_PERSON | 0.9 | precision>=0.97 | 0.9809 | 0.7928 | 1412 | 1747 |
| C_NAME | 0.95 | precision>=0.97 | 0.9835 | 0.6317 | 3205 | 4990 |
| C_ADDRESS | 0.65 | precision>=0.97 | 0.9736 | 0.9718 | 2763 | 2768 |
| C_REG_ID | 0.55 | precision>=0.97 | 0.9742 | 0.9752 | 1939 | 1937 |
| LEGAL_FORM | 0.6 | precision>=0.97 | 0.9731 | 0.8702 | 186 | 208 |
| CAPITAL | 0.5 | precision>=0.97 | 0.97 | 0.2658 | 100 | 365 |
| FOUNDED | 0.85 | precision>=0.97 | 0.9705 | 0.4901 | 305 | 604 |
| STAFF | 0.9 | precision>=0.97 | 0.9839 | 0.2675 | 62 | 228 |
| REVENUE | 0.9 | best F1 | 0.7544 | 0.8925 | 737 | 623 |
| REVENUE_YEAR | 0.65 | best F1 | 0.7751 | 0.9304 | 845 | 704 |
| ACTIVITY | 0.7 | best F1 | 0.6872 | 0.5669 | 697 | 845 |
| ACTIVITY_CODE | 0.45 | precision>=0.97 | 0.9825 | 0.8358 | 57 | 67 |
| SERVICE | 0.95 | precision>=0.97 | 0.9764 | 0.9185 | 19291 | 20506 |
| HOURS | 0.9 | best F1 | 0.8714 | 0.8472 | 70 | 72 |
| CERT | 0.4 | best F1 | 0.6667 | 0.4118 | 21 | 34 |
| DOC_DATE | 0.45 | precision>=0.97 | 0.97 | 0.9961 | 5068 | 4935 |
| DOC_TOTAL | 0.3 | precision>=0.97 | 0.9872 | 0.9973 | 5159 | 5107 |
| LINE_TOTAL | 0.65 | precision>=0.97 | 0.9717 | 0.9941 | 16987 | 16605 |
| PRICE | 0.3 | precision>=0.97 | 0.9775 | 0.9823 | 15760 | 15684 |

### Detailed tables (pilot)

The same tables are in `runs/pilot/eval_tables.md`.

### Spans

| split | chunks | strict F1 | P | R | relaxed F1 | role swaps | doc type acc | lang acc | false/100 empty | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| val | 7959 | 0.975 | 0.9896 | 0.9609 | 0.9808 | 0.0027 | 0.9534 | 0.9977 | 0.95 | 0.0026 |
| dev_heldout | 15379 | 0.9537 | 0.9716 | 0.9365 | 0.9621 | 0.0044 | 0.9445 | 0.9984 | 4.22 | 0.0169 |

### Per label (dev_heldout)

| label | F1 | P | R | gold |
|---|---|---|---|---|
| ACTIVITY | 0.6213 | 0.6872 | 0.5669 | 845 |
| ACTIVITY_CODE | 0.9032 | 0.9825 | 0.8358 | 67 |
| CAPITAL | 0.4172 | 0.97 | 0.2658 | 365 |
| CERT | 0.5091 | 0.6667 | 0.4118 | 34 |
| C_ADDRESS | 0.9727 | 0.9736 | 0.9718 | 2768 |
| C_NAME | 0.7692 | 0.9835 | 0.6317 | 4990 |
| C_REG_ID | 0.9747 | 0.9742 | 0.9752 | 1937 |
| DOC_DATE | 0.9829 | 0.97 | 0.9961 | 4935 |
| DOC_TOTAL | 0.9922 | 0.9872 | 0.9973 | 5107 |
| FOUNDED | 0.6513 | 0.9705 | 0.4901 | 604 |
| HOURS | 0.8592 | 0.8714 | 0.8472 | 72 |
| LEGAL_FORM | 0.9188 | 0.9731 | 0.8702 | 208 |
| LINE_TOTAL | 0.9828 | 0.9717 | 0.9941 | 16605 |
| PRICE | 0.9799 | 0.9775 | 0.9823 | 15684 |
| REVENUE | 0.8182 | 0.7554 | 0.8925 | 623 |
| REVENUE_YEAR | 0.8457 | 0.7751 | 0.9304 | 704 |
| SERVICE | 0.9466 | 0.9764 | 0.9185 | 20506 |
| STAFF | 0.4207 | 0.9839 | 0.2675 | 228 |
| S_ADDRESS | 0.9848 | 0.9805 | 0.9891 | 6599 |
| S_EMAIL | 0.9862 | 0.9864 | 0.986 | 2862 |
| S_NAME | 0.939 | 0.9728 | 0.9075 | 8939 |
| S_PERSON | 0.8771 | 0.9816 | 0.7928 | 1747 |
| S_PHONE | 0.9879 | 0.9841 | 0.9918 | 4753 |
| S_REG_ID | 0.9766 | 0.9768 | 0.9763 | 4226 |
| S_URL | 0.9844 | 0.982 | 0.9868 | 1663 |

### Per language (dev_heldout)

| lang | F1 | P | R |
|---|---|---|---|
| ar | 0.9592 | 0.98 | 0.9393 |
| en | 0.9422 | 0.9574 | 0.9275 |
| es | 0.9465 | 0.9623 | 0.9312 |
| fr | 0.9496 | 0.9701 | 0.93 |
| hi | 0.9588 | 0.9783 | 0.9401 |
| it | 0.9548 | 0.9734 | 0.9368 |
| ja | 0.9659 | 0.9837 | 0.9487 |
| ko | 0.942 | 0.9601 | 0.9247 |
| ru | 0.9666 | 0.9775 | 0.9559 |
| zh | 0.9522 | 0.9747 | 0.9307 |

### Per document type (dev_heldout)

| doc type | F1 | P | R |
|---|---|---|---|
| brochure | 0.7159 | 0.9012 | 0.5938 |
| contract | 0.8813 | 0.9697 | 0.8078 |
| financials | 0.6996 | 0.6131 | 0.8145 |
| invoice | 0.9841 | 0.9903 | 0.9779 |
| letter | 0.9327 | 0.9717 | 0.8967 |
| other | 0.3158 | 0.5 | 0.2308 |
| price_list | 0.9236 | 0.9676 | 0.8835 |
| quote | 0.9239 | 0.9435 | 0.905 |
| registration | 0.9717 | 0.9757 | 0.9678 |
| staff_list | 0.5867 | 0.9851 | 0.4177 |
| terms | 0.7762 | 0.8673 | 0.7025 |

### Per source format (dev_heldout)

| source | F1 | P | R |
|---|---|---|---|
| csv | 0.9206 | 0.9861 | 0.8632 |
| docx | 0.9381 | 0.9718 | 0.9067 |
| md | 0.8871 | 0.9532 | 0.8296 |
| pdf | 0.9607 | 0.9714 | 0.9502 |
| txt | 0.9388 | 0.9766 | 0.9039 |
| xlsx | 0.9627 | 0.9762 | 0.9494 |

### Folder level (dev_heldout)

| field | accuracy |
|---|---|
| business_name | 0.98 |
| address | 0.97 |
| reg_id | 0.8433 |
| contact | 0.99 |
| legal_form | 0.9567 |
| founded | 0.8033 |
| staff | 0.7567 |
| activity | 0.75 |
| activity_code | 0.99 |
| capital | 0.8 |
| revenue | 0.9433 |
| services | 0.8933 |
| clients | 0.68 |
| country | 1.0 |
| REQUIRED mean | 0.8697 |
| invented values | 0 |
| conflicts per folder | 0.227 |
| coverage error | 0.0785 |
| folders | 300 |

### Tokenizer

boundary rate 100.000%; characters per token: ar 2.70, en 2.63, es 2.76, fr 2.97, hi 2.50, it 3.00, ja 1.14, ko 1.28, ru 2.66, zh 1.17


## 6. Error analysis (dev_heldout only)

The ten largest groups of errors of the last model on dev_heldout, by label x language x document type x kind.

| label | lang | doc type | kind | count | two examples |
|---|---|---|---|---|---|
| C_NAME | it | brochure | missed | 161 | `Estetica Porzio Srl` in "biamo curato la fornitura per Estetica Porzio Srl, uno dei principali / operato"<br>`W.C. Agency SRL` in " come Fratelli Avogadro SpA e W.C. Agency SRL confermano la qualità / del n" |
| C_NAME | zh | brochure | missed | 128 | `唐記房屋` in "对象包括福州市卓越财务咨询有限公司、上海市顾明装饰有限公司、唐記房屋和上海市霍氏百货有限公司等企事业单位。我们的技术团队平均拥有"<br>`福州市卓越财务咨询有限公司` in "户 / 收到您的需求后，我们会尽快安排专人跟进。服务对象包括福州市卓越财务咨询有限公司、上海市顾明装饰有限公司、唐記房屋和上海市霍氏百货有限公司等" |
| LINE_TOTAL | en | financials | spurious | 125 | `2,861,222` in "pment; 2025: 2,871,447; 2024: 2,861,222 / Account: Stock-in-Trade; 20"<br>`2` in " for Liabilities and Charges; 2025: 110,724; 2024: 241,902 / " |
| C_NAME | ko | brochure | missed | 124 | `주식회사 한빛` in "주요 고객사 / 주식회사 한빛, (주)성남시 수정구출력센터, 종로구마케팅 및 주식회"<br>`(주)성남시 수정구출력센터` in "주요 고객사 / 주식회사 한빛, (주)성남시 수정구출력센터, 종로구마케팅 및 주식회사 스마트세무회계 등 여러 기" |
| C_NAME | fr | brochure | missed | 120 | `SCI Christelle Lejeune` in "uveaux locaux de notre client SCI Christelle Lejeune. /  / 14/06/2025 – Retrouvez-"<br>`SARL Lacroix Distribution` in "uveaux locaux de notre client SARL Lacroix Distribution. /  / Nous vous répondrons da" |
| C_NAME | es | brochure | missed | 102 | `Salón de Belleza Olea S.A. de C.V.` in "tre nuestros clientes figuran Salón de Belleza Olea S.A. de C.V., Supermercado Sergio S.A. de "<br>`Obras y Reformas Castro S. de R.L. de C.V.` in "rencias: Alvarez e Hijos SL y Obras y Reformas Castro S. de R.L. de C.V. Los plazos de entrega pueden " |
| C_NAME | ar | brochure | missed | 89 | `الشعاع للأنظمة والبرمجيات ش.م.ح` in "زنا مشروع التجهيز الكامل لمقر الشعاع للأنظمة والبرمجيات ش.م.ح. /  / «أنصح بالتعامل مع أولاد"<br>`الشعاع للأنظمة والبرمجيات ش.م.ح` in "قائمة العملاء / وقع اختيار الشعاع للأنظمة والبرمجيات ش.م.ح علينا لتنفيذ مشروع التجهيز ال" |
| C_NAME | hi | brochure | missed | 82 | `GLT सिक्योरिटी एंड एलाइड सर्विसेज़ Private Limited` in " सर्विस पार्टनर के रूप में हम GLT सिक्योरिटी एंड एलाइड सर्विसेज़ Private Limited, डायमंड इंफ्राटेक लिमिटेड और "<br>`पवनपुत्र एंटरप्राइजेज` in ", डायमंड इंफ्राटेक लिमिटेड और पवनपुत्र एंटरप्राइजेज को सेवाएँ दे रहे हैं।" |
| LINE_TOTAL | ko | financials | spurious | 82 | `1` in "022: 424,881,479 / 항목: 매입채무 및 기타채무; 2024: "<br>`2` in ",304,635 424,881,479 / 매입채무 및 기타채무  514,6" |
| C_NAME | ja | brochure | missed | 81 | `㈱鈴木マート` in "## 納入実績 / 導入事例：㈱鈴木マート様港区の皆さまに支えられ、ここまで歩んでまいりました。201"<br>`(有)KSF経営研究所` in "月21日　一部商品の価格改定について /  / 主要販売先：(有)KSF経営研究所、株式会社飛鳥ビルメンテナンス、丸栄ストア株式会社／主要仕入" |

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
