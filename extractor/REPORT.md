# REPORT - The Extractor 1.0.0

## 1. Summary

Presets run: smoke, pilot (not full: no GPU here). The last one, **pilot**, was evaluated on every set: strict micro-F1 test_seen 0.977, test_heldout 0.922, test_locale 0.925, handwritten 0.482.  
No gate for pilot (section 17); 3 of the full gate's lines would fail.  
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
| free_disk_gb | 21.9 |
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
| smoke | 1.5M | 128/2/2/352 | 8000 | 100 | 0.2 | 6.6451 | 0.0783 | 150 | 0.2 | 2.5257 | 150 | 0.0 | 0.85 |
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
| 16 | test_locale micro-F1 / calibration error (ECE, test_heldout) / speed | report | 0.0 / 0.0 / 142.96 | report |

### pilot

| # | measure | target (full) | measured | result |
|---|---|---|---|---|
| 1 | test_seen strict micro-F1 | >= 0.97 | 0.977 | PASS |
| 2 | test_heldout strict micro-F1 | >= 0.92 | 0.9216 | PASS |
| 3 | test_heldout micro-F1, every language | >= 0.88 | 0.9055 (ja) | PASS |
| 4 | test_heldout F1 of the 13 key labels (lowest) | >= 0.85 | 0.2657 (STAFF) | FAIL |
| 5 | traps: REVENUE precision (T1-T3) | >= 0.97 | 0.9846 | PASS |
| 6 | traps: role swaps (T4) | <= 2% | 0.0 | PASS |
| 7 | false spans per 100 empty chunks (T12) | <= 2 | 1.6 | PASS |
| 8 | doc-type accuracy (test_heldout) | >= 0.93 | 0.9196 | FAIL |
| 9 | language accuracy (test_heldout) | >= 0.99 | 0.9981 | PASS |
| 10 | folder level, test_heldout: 11 REQUIRED fields | >= 0.90 | 0.8073 | FAIL |
| 11 | folder level: business name | >= 0.97 | 0.98 | PASS |
| 12 | folder level: invented values | = 0 | 0 | PASS |
| 13 | tokenizer boundary rate | >= 99.5% | 100.000% | PASS |
| 14 | normalizer on generated spans, true country | >= 99% | 99.95% (language only 94.35%) | PASS |
| 15 | handwritten set micro-F1 | report (0.80 hoped) | 0.4821 | report |
| 16 | test_locale micro-F1 / calibration error (ECE, test_heldout) / speed | report | 0.9248 / 0.0271 / 105.01 | report |

**Diagnosis (pilot):**

The pilot has no gate (section 17), but three lines of the full gate
would fail with it; the report marks them FAIL. What the numbers say
(test sets: aggregate numbers only - no test example was looked at):

* **Line 4 (key labels >= 0.85):** below it on test_heldout are STAFF
  0.266 (precision 0.972, recall 0.154), FOUNDED 0.644 (0.993 / 0.477),
  REVENUE 0.701 (0.959 / 0.552), C_NAME 0.718 (0.942 / 0.580), ACTIVITY
  0.719 (0.793 / 0.657) and REVENUE_YEAR 0.791 (0.925 / 0.691). Precision
  is high and recall low: the thresholds that give 97% precision on
  dev_heldout are high for these labels (STAFF 0.90, FOUNDED 0.85, C_NAME
  0.95), and the dev_heldout analysis ("Improvement rounds" above) shows
  that the misses are facts written in phrasings and layouts the model
  never saw. A larger model trained longer on more folders (full) should
  close part of the gap; more training phrasings for these facts would
  close more.
* **Line 8 (doc-type accuracy >= 0.93):** 0.920 on test_heldout, against
  0.960 on test_seen and 0.945 on dev_heldout: the document type of
  chunks from held-out layouts is harder to recognise.
* **Line 10 (folder level, required fields >= 0.90):** 0.807 on
  test_heldout (0.933 on test_seen). The fields below 0.90 are reg_id
  0.537, staff 0.497, clients 0.527 and founded 0.747. They follow the
  span misses above; reg_id also fails when a single wrong or partial ID
  is kept (the rule wants no wrong ID). On dev_heldout the same field is
  0.843, so most of the test_heldout drop comes from the test-only held-out
  layouts and phrasings.
* **Handwritten set:** strict micro-F1 0.482 (precision 0.546, recall
  0.432; 661 of 1,531 spans found). The set is written in styles the
  generator does not produce, on purpose (forwarded email chains, web
  pages with menus, chat messages, notes). It is the clearest sign that
  real documents will be harder than the synthetic test sets; labelled
  real chunks in `real_eval/` will measure it properly.

### Calibration (pilot)

Temperature 1.25 and the per-label thresholds are fitted on dev_heldout (rules: 20 by 'precision>=0.97', 5 by 'best F1'). Expected calibration error (10 bins) of the accepted span scores, per split: val 0.0026, dev_heldout 0.0169, test_seen 0.0015, test_heldout 0.0271, test_locale 0.0396, traps 0.0056.

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
| test_seen | 15482 | 0.977 | 0.9908 | 0.9635 | 0.9823 | 0.0019 | 0.9603 | 0.9977 | 0.39 | 0.0015 |
| test_heldout | 15376 | 0.9216 | 0.9499 | 0.8949 | 0.9342 | 0.0536 | 0.9196 | 0.9981 | 5.56 | 0.0271 |
| test_locale | 5449 | 0.9248 | 0.9394 | 0.9106 | 0.9585 | 0.0049 | 0.9589 | 0.9978 | 0.7 | 0.0396 |
| traps | 1020 | 0.9739 | 0.987 | 0.9612 | 0.9833 | 0.0 | 0.999 | 0.998 | 1.6 | 0.0056 |

### Per label (test_heldout)

| label | F1 | P | R | gold |
|---|---|---|---|---|
| ACTIVITY | 0.7187 | 0.7935 | 0.6568 | 813 |
| ACTIVITY_CODE | 0.8473 | 0.9663 | 0.7544 | 114 |
| CAPITAL | 0.9196 | 0.947 | 0.8938 | 160 |
| CERT | 0.2478 | 0.5833 | 0.1573 | 89 |
| C_ADDRESS | 0.816 | 0.743 | 0.9049 | 2313 |
| C_NAME | 0.7178 | 0.9415 | 0.58 | 4079 |
| C_REG_ID | 0.8103 | 0.7183 | 0.9294 | 1827 |
| DOC_DATE | 0.9527 | 0.946 | 0.9594 | 5077 |
| DOC_TOTAL | 0.9171 | 0.9674 | 0.8718 | 5072 |
| FOUNDED | 0.6444 | 0.9931 | 0.4769 | 606 |
| HOURS | 0.9176 | 0.9286 | 0.907 | 86 |
| LEGAL_FORM | 0.9277 | 0.9646 | 0.8934 | 244 |
| LINE_TOTAL | 0.9974 | 0.996 | 0.9989 | 18515 |
| PRICE | 0.9357 | 0.9279 | 0.9436 | 18611 |
| REVENUE | 0.7009 | 0.9593 | 0.5522 | 853 |
| REVENUE_YEAR | 0.791 | 0.9255 | 0.6907 | 792 |
| SERVICE | 0.9595 | 0.9856 | 0.9347 | 21570 |
| STAFF | 0.2657 | 0.9722 | 0.1538 | 455 |
| S_ADDRESS | 0.8971 | 0.9268 | 0.8692 | 6324 |
| S_EMAIL | 0.9869 | 0.9838 | 0.99 | 1101 |
| S_NAME | 0.8853 | 0.9493 | 0.8294 | 8616 |
| S_PERSON | 0.6671 | 0.9671 | 0.5092 | 2076 |
| S_PHONE | 0.9914 | 0.9878 | 0.995 | 2775 |
| S_REG_ID | 0.881 | 0.9471 | 0.8235 | 4153 |
| S_URL | 0.9778 | 0.9772 | 0.9785 | 744 |

### Per language (test_heldout)

| lang | F1 | P | R |
|---|---|---|---|
| ar | 0.93 | 0.9535 | 0.9076 |
| en | 0.9255 | 0.9511 | 0.9013 |
| es | 0.9244 | 0.9479 | 0.9019 |
| fr | 0.9176 | 0.9501 | 0.8873 |
| hi | 0.9281 | 0.9585 | 0.8995 |
| it | 0.9401 | 0.9685 | 0.9134 |
| ja | 0.9055 | 0.9274 | 0.8845 |
| ko | 0.9084 | 0.9485 | 0.8716 |
| ru | 0.9095 | 0.936 | 0.8845 |
| zh | 0.9222 | 0.9535 | 0.8928 |

### Per document type (test_heldout)

| doc type | F1 | P | R |
|---|---|---|---|
| brochure | 0.6883 | 0.9125 | 0.5526 |
| contract | 0.8873 | 0.9679 | 0.819 |
| financials | 0.8894 | 0.9167 | 0.8636 |
| invoice | 0.9342 | 0.9474 | 0.9214 |
| letter | 0.8808 | 0.9622 | 0.8121 |
| other | 0.3111 | 0.2593 | 0.3889 |
| price_list | 0.9422 | 0.9842 | 0.9037 |
| quote | 0.9726 | 0.9843 | 0.9611 |
| registration | 0.9385 | 0.9632 | 0.9152 |
| staff_list | 0.3493 | 0.4545 | 0.2837 |
| terms | 0.8212 | 0.8684 | 0.7788 |

### Per source format (test_heldout)

| source | F1 | P | R |
|---|---|---|---|
| csv | 0.8028 | 0.8261 | 0.7808 |
| docx | 0.8969 | 0.9343 | 0.8625 |
| md | 0.8612 | 0.9411 | 0.7938 |
| pdf | 0.9322 | 0.9532 | 0.912 |
| txt | 0.8958 | 0.955 | 0.8435 |
| xlsx | 0.9161 | 0.9443 | 0.8896 |

### Traps

| trap | chunks | scores |
|---|---|---|
| T1 | 422 | REVENUE_precision 0.9375, DOC_TOTAL_f1 0.9972 |
| T2 | 27 | REVENUE_precision 0.9831, REVENUE_recall 0.9206, REVENUE_YEAR_f1 0.9587 |
| T3 | 25 | REVENUE_precision 0.9831, REVENUE_recall 0.9206, REVENUE_YEAR_f1 0.9587 |
| T4 | 203 | role_accuracy 1.0, role_swap_rate 0.0 |
| T5 | 160 | false_S_or_fact_per_100_chunks 8.75 |
| T6 | 429 | S_PHONE_precision 0.9953, S_REG_ID_precision 1.0 |
| T7 | 177 | FOUNDED_precision 1.0 |
| T8 | 182 | STAFF_precision 1.0 |
| T9 | 276 | SERVICE_precision 0.9895 |
| T10 | 81 | DOC_TOTAL_precision 1.0 |
| T11 | 194 | S_PERSON_precision 1.0 |
| T12 | 125 | false_spans_per_100_empty 1.6 |
| T13 | 75 | C_NAME_f1 0.8776 |
| T14 | 49 | S_NAME_precision 1.0 |
| T15 | 249 | DOC_DATE_precision 1.0 |
| T1-T3 REVENUE precision |  | 0.9846 |

### Folder level (test_heldout)

| field | accuracy |
|---|---|
| business_name | 0.98 |
| address | 0.9633 |
| reg_id | 0.5367 |
| contact | 0.97 |
| legal_form | 0.9367 |
| founded | 0.7467 |
| staff | 0.4967 |
| activity | 0.8567 |
| activity_code | 0.9567 |
| capital | 0.9767 |
| revenue | 0.96 |
| services | 0.9067 |
| clients | 0.5267 |
| country | 0.9933 |
| REQUIRED mean | 0.8073 |
| invented values | 0 |
| conflicts per folder | 0.15 |
| coverage error | 0.0888 |
| folders | 300 |

### Folder level (test_seen)

| field | accuracy |
|---|---|
| business_name | 0.9967 |
| address | 0.99 |
| reg_id | 0.9533 |
| contact | 0.9933 |
| legal_form | 0.9767 |
| founded | 0.9 |
| staff | 0.66 |
| activity | 0.9133 |
| activity_code | 0.9867 |
| capital | 0.9967 |
| revenue | 0.9967 |
| services | 0.9833 |
| clients | 0.9 |
| country | 0.9967 |
| REQUIRED mean | 0.933 |
| invented values | 0 |
| conflicts per folder | 0.133 |
| coverage error | 0.0588 |
| folders | 300 |

### handwritten

| chunks | strict F1 | P | R | relaxed F1 |
|---|---|---|---|---|
| 100 | 0.4821 | 0.5458 | 0.4317 | 0.566 |

### Speed

105.01 chunks/s on CPU (threads 4, batch 16, 500 chunks), peak RAM 2168.6 MB

### Tokenizer

boundary rate 100.000%; characters per token: ar 2.70, en 2.63, es 2.76, fr 2.97, hi 2.50, it 3.00, ja 1.14, ko 1.28, ru 2.66, zh 1.17


## 6. Error analysis (dev_heldout only)

The ten largest groups of errors of the last model on dev_heldout, by label x language x document type x kind.

| label | lang | doc type | kind | count | two examples |
|---|---|---|---|---|---|
| C_NAME | it | brochure | missed | 161 | `Estetica Porzio Srl` in "biamo curato la fornitura per Estetica Porzio Srl, uno dei principali / operato"<br>`Photo Desenzano del Garda` in "Referenze: / Bramble L.L.C. e Photo Desenzano del Garda – Partner tecnologico: F.lli " |
| C_NAME | zh | brochure | missed | 128 | `福州市卓越财务咨询有限公司` in "户 / 收到您的需求后，我们会尽快安排专人跟进。服务对象包括福州市卓越财务咨询有限公司、上海市顾明装饰有限公司、唐記房屋和上海市霍氏百货有限公司等"<br>`唐記房屋` in "对象包括福州市卓越财务咨询有限公司、上海市顾明装饰有限公司、唐記房屋和上海市霍氏百货有限公司等企事业单位。我们的技术团队平均拥有" |
| LINE_TOTAL | en | financials | spurious | 125 | `2,861,222` in "pment; 2025: 2,871,447; 2024: 2,861,222 / Account: Stock-in-Trade; 20"<br>`2` in " for Liabilities and Charges; 2025: 110,724; 2024: 241,902 / " |
| C_NAME | ko | brochure | missed | 124 | `중앙` in "주시기 바랍니다. 종로구제빵소주식회사의 플랫폼을 통해 중앙에 서비스를 제공하고 있습니다."<br>`주식회사 한빛` in "주요 고객사 / 주식회사 한빛, (주)성남시 수정구출력센터, 종로구마케팅 및 주식회" |
| C_NAME | fr | brochure | missed | 120 | `SCI Christelle Lejeune` in "uveaux locaux de notre client SCI Christelle Lejeune. /  / 14/06/2025 – Retrouvez-"<br>`SARL Lacroix Distribution` in "uveaux locaux de notre client SARL Lacroix Distribution. /  / Nous vous répondrons da" |
| C_NAME | es | brochure | missed | 102 | `Obras y Reformas Castro S. de R.L. de C.V.` in "rencias: Alvarez e Hijos SL y Obras y Reformas Castro S. de R.L. de C.V. Los plazos de entrega pueden "<br>`Alvarez e Hijos SL` in "Referencias / Referencias: Alvarez e Hijos SL y Obras y Reformas Castro S. " |
| C_NAME | ar | brochure | missed | 89 | `الشعاع للأنظمة والبرمجيات ش.م.ح` in "زنا مشروع التجهيز الكامل لمقر الشعاع للأنظمة والبرمجيات ش.م.ح. /  / «أنصح بالتعامل مع أولاد"<br>`الشعاع للأنظمة والبرمجيات ش.م.ح` in "قائمة العملاء / وقع اختيار الشعاع للأنظمة والبرمجيات ش.م.ح علينا لتنفيذ مشروع التجهيز ال" |
| C_NAME | hi | brochure | missed | 82 | `GLT सिक्योरिटी एंड एलाइड सर्विसेज़ Private Limited` in " सर्विस पार्टनर के रूप में हम GLT सिक्योरिटी एंड एलाइड सर्विसेज़ Private Limited, डायमंड इंफ्राटेक लिमिटेड और "<br>`पवनपुत्र एंटरप्राइजेज` in ", डायमंड इंफ्राटेक लिमिटेड और पवनपुत्र एंटरप्राइजेज को सेवाएँ दे रहे हैं।" |
| LINE_TOTAL | ko | financials | spurious | 82 | `1` in "022: 424,881,479 / 항목: 매입채무 및 기타채무; 2024: "<br>`2` in ",304,635 424,881,479 / 매입채무 및 기타채무  514,6" |
| C_NAME | ja | brochure | missed | 81 | `㈱鈴木マート` in "## 納入実績 / 導入事例：㈱鈴木マート様港区の皆さまに支えられ、ここまで歩んでまいりました。201"<br>`(有)KSF経営研究所` in "月21日　一部商品の価格改定について /  / 主要販売先：(有)KSF経営研究所、株式会社飛鳥ビルメンテナンス、丸栄ストア株式会社／主要仕入" |

## 7. Improvement rounds

**None were run: the first pilot run already met the stop rule of
section 23** (pilot: dev_heldout >= 0.85). Its dev-only evaluation gave
strict micro-F1 (accepted spans, after calibration) **0.9537 on
dev_heldout** and 0.9750 on val; dev_heldout folder level 0.870 on the
required fields, 0.980 on the business name, 0 invented values. The full
evaluation was then run once (`build.py pilot --from evaluate`).

The error analysis of section 23 was still done, on val and dev_heldout
only (`runs/pilot/errors_dev.jsonl`), for the report and for whoever
builds the next data version. What was seen:

* **10,502 errors** (dev_heldout 8,277, val 2,225): missed 7,117,
  spurious 1,601, boundary 1,384, wrong label 228, role swap 172. By
  label: C_NAME 2,353, SERVICE 2,261, S_NAME 1,298, PRICE 587, S_PERSON
  545, ACTIVITY 520, LINE_TOTAL 490, FOUNDED 348, STAFF 284, CAPITAL 270.
  110 examples from the largest groups were read one by one.
* **Held-out layouts and phrasings are the main source.** On dev_heldout,
  chunks from training layouts score F1 0.963 and chunks from the 12
  held-out (D) layouts 0.948, but four layouts are far lower:
  `brochure.B06` (D) 0.565 (1,640 of 2,836 spans missed: client
  references, founding dates, activity statements written in held-out
  phrasings such as "服务对象包括…等企事业单位", "Dal 2004 a oggi",
  "Мы открылись в 2024 году"), `staff_list.S02` (D) 0.581,
  `financials.F02` (D) 0.620 (share capital rows read as REVENUE; 341
  spurious LINE_TOTAL and 165 spurious REVENUE_YEAR, some on pieces of
  numbers such as "202" of "2025") and `brochure.B09` (a training layout,
  whose dev_heldout chunks carry held-out phrasings) 0.626.
* **The precision rule of the thresholds turns uncertain right answers
  into misses:** C_NAME needs a score of 0.95, STAFF and S_PERSON 0.90,
  S_NAME and FOUNDED 0.85 to reach 97% precision on dev_heldout; on val
  (seen layouts and phrasings) 1,702 of the 2,225 errors are misses.
* **Data problems noticed (not fixed, since no round was run):**
  1. product names that contain commas ("Whole milk, 2 L", "Object
     storage, 1 TB") are also used in comma-separated lists in running
     text, where their boundaries are ambiguous even for a person;
  2. a counterparty that is a sole trader named after its owner is
     `C_NAME` (R8/R9), a private customer is `O`, and some documents
     show the first without any business cue (no registration number,
     no trade word), so the two cannot be told apart from the text;
  3. Japanese and Korean company names built from a full city and ward
     ("仙台市宮城野区ペイント", "안산시 상록구헬스"), which real names
     do not do (Chinese names with the city, "上海市…有限公司", are
     normal);
  4. a legal form repeated after a name that already has it
     ("合发印务有限公司（有限公司）");
  5. in `invoice.L09`, the payment-terms cell of non-English invoices
     shows a bare number of days that does not match the due date.
* **What a next round should change** (for example if the full build
  misses gate line 4 on FOUNDED, STAFF, ACTIVITY or C_NAME): more
  training phrasings for client references, founding dates, activity
  statements and staff counts in every language; more forms of balance
  sheets and income statements; the five data problems above.

## 8. Deviations and decisions

Every decision is in `DECISIONS.md`, by topic: Environment, Language data (section 10.2), Names and addresses: the Faker rule (section 10.3), Generator (section 10), Normalizer and verifier (section 14), Test discipline, Profile builder (section 15), Build pipeline (sections 7-9, 12, 13, 17, 21), Improvement rounds, Diagnosis - pilot, Delivery, Suggestions (for FIXED sections - not applied).

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

### Delivery

* The files were sent with this environment's file-delivery tool, which
  takes at most 30 MiB per file. `extractor-pilot.pt` (48.6 MB) is over
  that limit, so it was sent in two halves, `extractor-pilot.pt.part1` and
  `extractor-pilot.pt.part2`. Joined, they are byte for byte the evaluated
  file; its SHA-256 is
  `B2C03128D622A2C3A2E1FC37BD9A450FE59D223A1AE842D2A7C147C48878323E`.
  To join them, put both halves in `C:\Users\Laurent\new model\extractor`
  and run, in PowerShell:

```powershell
cd "C:\Users\Laurent\new model\extractor"
```

```powershell
cmd /c copy /b extractor-pilot.pt.part1+extractor-pilot.pt.part2 extractor-pilot.pt
```

```powershell
(Get-FileHash extractor-pilot.pt).Hash
```

  The last command must print the SHA-256 above; the two halves can then
  be deleted.
* No folder `C:\Users\Laurent\new model` was connected to this session,
  so nothing was written there.
