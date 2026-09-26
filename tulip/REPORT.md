# Tulip 1 — the Importer: build report

## 1. Summary

* **smoke**: dev_heldout pass@1 0.000 / loop 0.020; val pass@1 0.020 / loop 0.020 (dev splits only)
* **pilot**: dev_heldout pass@1 0.082 / loop 0.086; val pass@1 0.096 / loop 0.084 (dev splits only)

## 2. Environment

| item | value |
|---|---|
| OS | Linux 6.18.44-fc-v37 |
| Python | 3.11.15 |
| torch | 2.14.0+cu130 |
| backend | cpu |
| device | CPU only |
| CPU count / RAM GB | 4 / 16.9 |
| measured TFLOPS | cpu_fp32 0.46, cpu_bf16 1.201 |
| packages | torch 2.14.0+cu130, tokenizers 0.23.2, openpyxl 3.1.5, phonenumbers 9.0.40, numpy 2.4.6, hijridate 2.6.0 |

## 3. Data — smoke

| split | tasks | discards (self-check) | duplicates dropped | not made | real-file round trips | different previews |
|---|---|---|---|---|---|---|
| train | 1000 | 1 | 0 | 0 | 10 | 0 |
| val | 50 | 0 | 0 | 0 | 1 | 0 |
| dev_heldout | 50 | 0 | 0 | 0 | 1 | 0 |
| test_seen | 50 | 0 | 0 | 0 | 1 | 0 |
| test_heldout | 50 | 0 | 0 | 0 | 1 | 0 |
| test_locale | 20 | 0 | 0 | 0 | 1 | 0 |
| traps | 30 | 0 | 0 | 0 | 1 | 0 |

train, by language: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%

train, by answer: products 23.2%, services 13.1%, clients 11.6%, opening_hours 11.2%, invoice_ledger 10.9%, staff 10.8%, bookings 8.7%, no_matching_target 4.9%, missing_required 3.0%, not_a_table 2.3%, too_wide 0.3%

refusal share: 10.5%

train, by family (62 families): bookings.date_time 10, bookings.day_sections 11, bookings.duration 18, bookings.staff_price 8, bookings.start_end 14, bookings.time_range 14, bookings.title_rows 12, clients.address_one_cell 18, clients.address_split 17, clients.crm_export 11, clients.first_last 20, clients.private_persons 15, clients.registration 20, clients.title_rows 15, invoice_ledger.credit_notes 19, invoice_ledger.csv_export 20, invoice_ledger.currency_header 18, invoice_ledger.due_paid 12, invoice_ledger.monthly_subtotals 5, invoice_ledger.status 12, invoice_ledger.title_rows 23, opening_hours.abbreviations 2, opening_hours.days_columns 47, opening_hours.days_rows 15, opening_hours.morning_afternoon 14, opening_hours.notes_column 15, opening_hours.opens_closes 19, products.catalogue 23, products.csv_export 19, products.currency_header 18, products.extra_columns 18, products.repeated_headers 19, products.sections 15, products.simple 23, products.size_columns 14, products.size_columns_sections 14, products.title_rows 16, products.totals 23, products.two_prices 22, products.two_row_header 8, refusals.agenda_grid 5, refusals.budget 5, refusals.matrix 5, refusals.missing_required 30, refusals.not_offered 49, refusals.notes_page 4, refusals.pivot 4, refusals.too_wide 3, services.csv_export 18, services.duration_column 26, services.from_prices 21, services.sections 9, services.staff_column 22, services.title_rows 19, services.two_prices 16, staff.department_sections 10, staff.first_last 15, staff.full_name 15, staff.hr_export 15, staff.last_first 19, staff.role_department 19, staff.start_dates 15

Generator self-checks (section 10.8):

* PASS 1 self-check discards <= 0.5%
  * 1 discards of 1251 tasks (0.08%); 0 tasks could not be made
* PASS 2 programs canonical
  * 0 not canonical
* PASS 3 traps, families, languages
  * T1 31% of products (needs 30%)
  * T2 24% of products and services (needs 20%)
  * T3 12% of products (needs 10%)
  * T4 43% of tables with >= 8 rows (needs 40%)
  * T5 58% of tables (needs 50%)
  * T6 11% of tables (needs 10%)
  * T7 28% of products and services (needs 25%)
  * T8 18% of products (needs 15%)
  * T8 44% of opening_hours (needs 40%)
  * T9 17% of tables (needs 15%)
  * T10 57% of staff (needs 50%)
  * T10 57% of clients (needs 30%)
  * T11 41% of bookings (needs 40%)
  * T12 77% of bookings and ledgers (needs 70%)
  * T13 42% of amount tables (needs 30%)
  * T14 29% of tables (needs 20%)
  * missing_required (T15) 3.0% of tasks (3.5%)
  * no_matching_target 4.9% of tasks (6.0%)
  * not_a_table 2.3% of tasks (2.0%)
  * too_wide 0.3% of tasks (0.5%)
  * every family appears in its splits
  * languages: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%
* PASS 4 real-file round trip (1%)
  * 16 files, 0 with a different preview
* PASS 5 helpers give the truth >= 99.5%
  * 100.000% of 259346 values
* PASS 6 hold-out rules
  * all kept
* PASS 7 token lengths
  * checked by the tokenizer stage (pack)
* PASS 8 NFKC programs, lookup keys in the preview
  * 0 programs not NFKC, 0 lookup keys not in VALUES

Preview tokens per language (train):

| language | p50 | p95 | max |
|---|---|---|---|
| ar | 848 | 1978 | 4639 |
| en | 883 | 1853 | 2588 |
| es | 842 | 2071 | 2212 |
| fr | 878 | 1912 | 2124 |
| hi | 1058 | 2200 | 3066 |
| it | 906 | 1943 | 2298 |
| ja | 897 | 2130 | 4891 |
| ko | 857 | 2058 | 2699 |
| ru | 884 | 2094 | 2453 |
| zh | 819 | 1640 | 2434 |

Tasks over 4,096 tokens: 2 of 1250 (0.2%). Tokenizer round trip on val programs: 0 failures.

## 4. Model — smoke

Preset **smoke**: vocabulary 4000, d_model 128, 3 layers, 4 heads, ffn 352, max_len 2048, dropout 0.0.

Parameters: 1115008 (603008 outside the embedding). Steps: 1200 of 1200 planned (9.68 epochs), 4.3 training minutes. Chosen checkpoint: step 1200 (dev sample execution match 0.0000).

Loss curve (step: smoothed loss): 50: 5.119, 350: 0.686, 650: 0.435, 950: 0.316, 1200: 0.246

Model-selection evaluations: step 1200: 0.000

## 5. Results — smoke

_Only val and dev_heldout were scored (the improvement rounds); the test splits are scored once at the end._

| # | measure | target | value | result |
|---|---|---|---|---|
| 1 | test_seen pass@1 | >= 0.97 | not run |  |
| 2 | test_heldout pass@1 | >= 0.90 | not run |  |
| 3 | test_heldout loop: correct imports among importable tasks | >= 0.95 | not run |  |
| 4 | test_heldout false accepts among the loop's imports | <= 2% | not run |  |
| 5a | refusal precision (test_heldout, loop) | >= 0.95 | not run |  |
| 5b | refusal recall (test_heldout, loop) | >= 0.90 | not run |  |
| 6 | target choice accuracy (test_heldout) | >= 0.97 | not run |  |
| 9 | invented values | = 0 | 0 | PASS |
| 11 | handwritten files, loop | report (>= 0.80 hoped) | not run |  |

The gate applies to the full preset only; for smoke these are reported, not gated (section 16).

#### Per split

| split | tasks | pass@1 | loop | loop (importable) | false accepts | refusal P / R | target acc. | needs_review | CPU s greedy med / p95 | CPU s loop med / p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| val | 50 | 0.02 | 0.02 | 0.0213 | 1 (50.0%) | 0.0 / 0.0 | 0.1277 | 0.92 | 0.192 / 0.364 | 1.298 / 2.298 |
| dev_heldout | 50 | 0.0 | 0.02 | 0.0233 | 1 (50.0%) | 0.0 / 0.0 | 0.1395 | 0.94 | 0.177 / 0.39 | 1.147 / 2.52 |

##### val: loop by language, target and trap

languages: ar 0.0, en 0.0, es 0.0, fr 0.0, hi 0.0, it 0.0, ja 0.0, ko 0.0, ru 0.2, zh 0.0

targets: bookings 0.0, clients 0.0, invoice_ledger 0.0, opening_hours 0.1429, products 0.0, refusal 0.0, services 0.0, staff 0.0

traps: T1 0.0, T2 0.0, T4 0.0, T5 0.0, T6 0.0, T7 0.0, T8 0.0, T9 0.0, T10 0.0, T11 0.0, T12 0.0, T13 0.0, T14 0.0

##### dev_heldout: loop by language, target and trap

languages: ar 0.0, en 0.0, es 0.0, fr 0.0, hi 0.0, it 0.0, ja 0.0, ko 0.0, ru 0.0, zh 0.2

targets: bookings 0.0, clients 0.0, invoice_ledger 0.0, opening_hours 0.2, products 0.0, refusal 0.0, services 0.0, staff 0.0

traps: T1 0.0, T2 0.0, T3 0.0, T4 0.0, T5 0.0, T6 0.0, T7 0.0, T8 0.0, T9 0.0, T10 0.0, T11 0.0, T12 0.0, T13 0.0, T14 0.0

#### Error groups (val and dev_heldout only)

val: unparsable_program 43, wrong_header_row 3, wrong_column 1, wrong_layout 1, refused_importable 1

dev_heldout: unparsable_program 43, wrong_header_row 4, wrong_helper 1, wrong_target 1, wrong_layout 1



## 6. Error analysis — smoke (dev_heldout only)

* **unparsable_program**: 43
  * `dev_heldout-000000` (bookings.datetime_cell, ar): wrote `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(col('A'))` - expected `target('bookings') / header(1) / out.date = date(col('D')) / out.start_time = time(col('D'))`
  * `dev_heldout-000002` (services.staff_column, en): wrote `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('services') / header(4) / sections() / out.name = text(col('A'))`
* **wrong_header_row**: 4
  * `dev_heldout-000007` (bookings.title_rows, hi): wrote `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(part(col('A'), ' – ', 0))` - expected `target('bookings') / header(3) / out.date = date(col('A')) / out.start_time = time(col('B'))`
  * `dev_heldout-000010` (services.duration_column, ar): wrote `target('services') / header(1) / out.name = text(col('A')) / out.category = text(col('B'))` - expected `target('services') / header(4) / out.name = text(col('A')) / out.price = amount(col('C'))`
* **wrong_helper**: 1
  * `dev_heldout-000001` (opening_hours.morning_afternoon, zh): wrote `target('opening_hours') / header(1) / out.day = weekday(col('A')) / out.hours = hours(join('-', col('B'), col('C')))` - expected `target('opening_hours') / header(1) / out.day = weekday(col('A')) / out.hours = hours(join(', ', col('B'), col('C')))`
* **wrong_target**: 1
  * `dev_heldout-000046` (staff.department_sections, it): wrote `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('staff') / header(2) / sections() / out.name = text(join(' ', col('A'), col('B')))`
* **wrong_layout**: 1
  * `dev_heldout-000047` (products.currency_header, hi): wrote `target('products') / header(1) / sections() / out.sku = text(col('A'))` - expected `target('products') / header(1) / out.name = text(col('E')) / out.category = text(col('A'))`

## 3. Data — pilot

| split | tasks | discards (self-check) | duplicates dropped | not made | real-file round trips | different previews |
|---|---|---|---|---|---|---|
| train | 30000 | 92 | 0 | 0 | 300 | 0 |
| val | 500 | 0 | 0 | 0 | 5 | 0 |
| dev_heldout | 500 | 2 | 0 | 0 | 5 | 0 |
| test_seen | 500 | 0 | 0 | 0 | 5 | 0 |
| test_heldout | 500 | 1 | 0 | 0 | 5 | 0 |
| test_locale | 200 | 1 | 0 | 0 | 2 | 0 |
| traps | 300 | 1 | 0 | 0 | 3 | 0 |

train, by language: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%

train, by answer: products 21.7%, services 13.6%, invoice_ledger 11.6%, clients 10.5%, opening_hours 10.4%, bookings 10.2%, staff 9.9%, no_matching_target 6.3%, missing_required 3.3%, not_a_table 2.0%, too_wide 0.5%

refusal share: 12.0%

train, by family (62 families): bookings.date_time 451, bookings.day_sections 432, bookings.duration 435, bookings.staff_price 419, bookings.start_end 419, bookings.time_range 444, bookings.title_rows 471, clients.address_one_cell 458, clients.address_split 450, clients.crm_export 439, clients.first_last 466, clients.private_persons 435, clients.registration 459, clients.title_rows 430, invoice_ledger.credit_notes 524, invoice_ledger.csv_export 540, invoice_ledger.currency_header 548, invoice_ledger.due_paid 520, invoice_ledger.monthly_subtotals 217, invoice_ledger.status 552, invoice_ledger.title_rows 573, opening_hours.abbreviations 395, opening_hours.days_columns 1177, opening_hours.days_rows 390, opening_hours.morning_afternoon 378, opening_hours.notes_column 387, opening_hours.opens_closes 400, products.catalogue 525, products.csv_export 537, products.currency_header 526, products.extra_columns 544, products.repeated_headers 528, products.sections 403, products.simple 523, products.size_columns 409, products.size_columns_sections 349, products.title_rows 552, products.totals 539, products.two_prices 523, products.two_row_header 550, refusals.agenda_grid 124, refusals.budget 131, refusals.matrix 119, refusals.missing_required 978, refusals.not_offered 1890, refusals.notes_page 116, refusals.pivot 110, refusals.too_wide 147, services.csv_export 628, services.duration_column 589, services.from_prices 634, services.sections 333, services.staff_column 654, services.title_rows 644, services.two_prices 607, staff.department_sections 392, staff.first_last 435, staff.full_name 446, staff.hr_export 410, staff.last_first 435, staff.role_department 441, staff.start_dates 420

Generator self-checks (section 10.8):

* PASS 1 self-check discards <= 0.5%
  * 97 discards of 32597 tasks (0.30%); 0 tasks could not be made
* PASS 2 programs canonical
  * 0 not canonical
* PASS 3 traps, families, languages
  * T1 35% of products (needs 30%)
  * T2 24% of products and services (needs 20%)
  * T3 13% of products (needs 10%)
  * T4 44% of tables with >= 8 rows (needs 40%)
  * T5 57% of tables (needs 50%)
  * T6 10% of tables (needs 10%)
  * T7 28% of products and services (needs 25%)
  * T8 16% of products (needs 15%)
  * T8 48% of opening_hours (needs 40%)
  * T9 16% of tables (needs 15%)
  * T10 55% of staff (needs 50%)
  * T10 53% of clients (needs 30%)
  * T11 42% of bookings (needs 40%)
  * T12 77% of bookings and ledgers (needs 70%)
  * T13 40% of amount tables (needs 30%)
  * T14 29% of tables (needs 20%)
  * missing_required (T15) 3.3% of tasks (3.5%)
  * no_matching_target 6.3% of tasks (6.0%)
  * not_a_table 2.0% of tasks (2.0%)
  * too_wide 0.5% of tasks (0.5%)
  * every family appears in its splits
  * languages: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%
* PASS 4 real-file round trip (1%)
  * 325 files, 0 with a different preview
* PASS 5 helpers give the truth >= 99.5%
  * 99.998% of 7126182 values
* PASS 6 hold-out rules
  * all kept
* PASS 7 token lengths
  * checked by the tokenizer stage (pack)
* PASS 8 NFKC programs, lookup keys in the preview
  * 0 programs not NFKC, 0 lookup keys not in VALUES

Preview tokens per language (train):

| language | p50 | p95 | max |
|---|---|---|---|
| ar | 768 | 1802 | 4093 |
| en | 791 | 1766 | 4609 |
| es | 773 | 1830 | 4400 |
| fr | 807 | 1834 | 3873 |
| hi | 767 | 1838 | 3631 |
| it | 753 | 1737 | 4288 |
| ja | 839 | 1897 | 4726 |
| ko | 814 | 1884 | 4932 |
| ru | 836 | 1875 | 4901 |
| zh | 780 | 1845 | 4733 |

Tasks over 4,096 tokens: 32 of 32500 (0.1%). Tokenizer round trip on val programs: 0 failures.

## 4. Model — pilot

Preset **pilot**: vocabulary 16000, d_model 256, 6 layers, 4 heads, ffn 704, max_len 4096, dropout 0.0.

Parameters: 8916224 (4820224 outside the embedding). Steps: 1920 of 1921 planned (1.00 epochs), 62.1 training minutes. Chosen checkpoint: step 1855 (dev sample execution match 0.0820).

Loss curve (step: smoothed loss): 50: 5.181, 500: 0.351, 1000: 0.246, 1450: 0.226, 1900: 0.186

Model-selection evaluations: step 461: 0.002, step 932: 0.004, step 1382: 0.042, step 1855: 0.082, step 1920: 0.082

## 5. Results — pilot

_Only val and dev_heldout were scored (the improvement rounds); the test splits are scored once at the end._

| # | measure | target | value | result |
|---|---|---|---|---|
| 1 | test_seen pass@1 | >= 0.97 | not run |  |
| 2 | test_heldout pass@1 | >= 0.90 | not run |  |
| 3 | test_heldout loop: correct imports among importable tasks | >= 0.95 | not run |  |
| 4 | test_heldout false accepts among the loop's imports | <= 2% | not run |  |
| 5a | refusal precision (test_heldout, loop) | >= 0.95 | not run |  |
| 5b | refusal recall (test_heldout, loop) | >= 0.90 | not run |  |
| 6 | target choice accuracy (test_heldout) | >= 0.97 | not run |  |
| 9 | invented values | = 0 | 0 | PASS |
| 11 | handwritten files, loop | report (>= 0.80 hoped) | not run |  |

The gate applies to the full preset only; for pilot these are reported, not gated (section 16).

#### Per split

| split | tasks | pass@1 | loop | loop (importable) | false accepts | refusal P / R | target acc. | needs_review | CPU s greedy med / p95 | CPU s loop med / p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| val | 500 | 0.096 | 0.084 | 0.0804 | 96 (72.7%) | 0.5833333333333334 / 0.1346153846153846 | 0.8103 | 0.712 | 0.593 / 1.4 | 4.761 / 13.638 |
| dev_heldout | 500 | 0.082 | 0.086 | 0.0542 | 93 (79.5%) | 0.8695652173913043 / 0.3508771929824561 | 0.7652 | 0.72 | 0.629 / 1.506 | 4.973 / 15.001 |

##### val: loop by language, target and trap

languages: ar 0.18, en 0.08, es 0.06, fr 0.02, hi 0.1, it 0.06, ja 0.1, ko 0.06, ru 0.08, zh 0.1

targets: bookings 0.0, clients 0.0612, invoice_ledger 0.0, opening_hours 0.3582, products 0.0515, refusal 0.1154, services 0.0, staff 0.069

traps: T1 0.0, T2 0.0, T3 0.0, T4 0.0492, T5 0.0295, T6 0.0, T7 0.0, T8 0.2653, T9 0.0, T10 0.0323, T11 0.0455, T12 0.0109, T13 0.0, T14 0.0226, T15 0.0

##### dev_heldout: loop by language, target and trap

languages: ar 0.06, en 0.02, es 0.1, fr 0.16, hi 0.1, it 0.02, ja 0.08, ko 0.12, ru 0.08, zh 0.12

targets: bookings 0.0, clients 0.0556, invoice_ledger 0.0, opening_hours 0.2979, products 0.0217, refusal 0.3333, services 0.0, staff 0.0735

traps: T1 0.0, T2 0.0, T3 0.0, T4 0.0329, T5 0.0339, T6 0.0345, T7 0.0, T8 0.25, T9 0.0, T10 0.0909, T11 0.0, T12 0.0, T13 0.0, T14 0.0127, T15 0.0

#### Error groups (val and dev_heldout only)

val: wrong_header_row 199, unparsable_program 92, missing_field 51, wrong_refusal 35, wrong_layout 28, extra_field 24, wrong_column 17, wrong_filter 6, missing_filter 6, wrong_helper 4, wrong_target 2, refused_importable 2

dev_heldout: wrong_header_row 230, unparsable_program 110, missing_field 34, wrong_refusal 27, extra_field 18, wrong_layout 16, wrong_column 14, missing_filter 6, wrong_target 5, wrong_filter 3, refused_importable 2, wrong_helper 1



## 6. Error analysis — pilot (dev_heldout only)

* **wrong_header_row**: 230
  * `dev_heldout-000002` (services.staff_column, en): wrote `target('services') / header(1) / out.name = text(col('A')) / out.category = text(col('B'))` - expected `target('services') / header(4) / sections() / out.name = text(col('A'))`
  * `dev_heldout-000005` (staff.full_name, es): wrote `target('staff') / header(1) / keep(not_total('F')) / out.name = text(col('A'))` - expected `target('staff') / header(2) / keep(not_total('G')) / out.name = text(col('G'))`
* **unparsable_program**: 110
  * `dev_heldout-000000` (bookings.datetime_cell, ar): wrote `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(col('A'))` - expected `target('bookings') / header(1) / out.date = date(col('D')) / out.start_time = time(col('D'))`
  * `dev_heldout-000003` (clients.companies, fr): wrote `target('clients') / header(1) / out.name = text(part(col('A'), ' / ', 0)) / out.address = text(col('B'))` - expected `target('clients') / header(1) / out.name = text(col('A')) / out.contact_person = text(col('E'))`
* **missing_field**: 34
  * `dev_heldout-000025` (products.category_sheet, es): wrote `target('products') / header(1) / out.sku = text(col('B')) / out.name = text(col('C'))` - expected `target('products') / header(1) / out.sku = text(col('A')) / out.name = text(col('B'))`
  * `dev_heldout-000047` (products.currency_header, hi): wrote `target('products') / header(1) / out.sku = text(col('A')) / out.name = text(col('B'))` - expected `target('products') / header(1) / out.name = text(col('E')) / out.category = text(col('A'))`
* **wrong_refusal**: 27
  * `dev_heldout-000013` (refusals.not_offered, fr): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `refuse('no_matching_target')`
  * `dev_heldout-000017` (refusals.not_offered, hi): wrote `target('services') / header(1) / out.name = text(col('A')) / out.category = text(col('B'))` - expected `refuse('no_matching_target')`
* **extra_field**: 18
  * `dev_heldout-000022` (products.extra_columns, en): wrote `target('products') / header(1) / sections() / out.sku = text(col('A'))` - expected `target('products') / header(1) / sections() / out.sku = text(col('A'))`
  * `dev_heldout-000049` (clients.companies, ko): wrote `target('clients') / header(1) / out.name = text(col('A')) / out.contact_person = text(col('B'))` - expected `target('clients') / header(1) / out.name = text(col('E')) / out.phone = phone(col('A'))`
* **wrong_layout**: 16
  * `dev_heldout-000042` (services.simple, en): wrote `target('services') / header(1) / out.name = text(col('A')) / out.price = amount(col('B'))` - expected `target('services') / header(1) / sections() / out.name = text(col('A'))`
  * `dev_heldout-000067` (staff.department_sections, hi): wrote `target('staff') / header(1) / out.name = text(join(' ', col('B'), col('A'))) / out.role = text(col('C'))` - expected `target('staff') / header(1) / sections() / out.name = text(col('A'))`
* **wrong_column**: 14
  * `dev_heldout-000008` (staff.hr_export, ja): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))`
  * `dev_heldout-000027` (clients.companies, hi): wrote `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))`
* **missing_filter**: 6
  * `dev_heldout-000035` (products.totals, es): wrote `target('products') / header(3) / sections() / out.name = text(col('A'))` - expected `target('products') / header(3) / keep(not_total('A')) / out.name = text(col('A'))`
  * `dev_heldout-000147` (clients.companies, hi): wrote `target('clients') / header(1) / out.name = text(col('A')) / out.contact_person = text(col('B'))` - expected `target('clients') / header(1) / keep(not_total('D')) / out.name = text(col('D'))`
* **wrong_target**: 5
  * `dev_heldout-000023` (invoice_ledger.credit_notes, fr): wrote `target('services') / header(1) / out.name = text(col('A')) / out.price = amount(col('B'))` - expected `target('invoice_ledger') / header(3) / out.number = text(col('A')) / out.date = date(col('B'))`
  * `dev_heldout-000036` (products.category_sheet, it): wrote `target('services') / header(1) / out.name = text(col('A')) / out.price = amount(col('B'))` - expected `target('products') / header(1) / out.sku = text(col('B')) / out.name = text(col('E'))`
* **wrong_filter**: 3
  * `dev_heldout-000077` (staff.last_first, hi): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(join(' ', col('B'), col('A')))` - expected `target('staff') / header(1) / keep(not_total('B')) / out.name = text(join(' ', col('B'), col('A')))`
  * `dev_heldout-000214` (products.repeated_headers, ru): wrote `target('products') / header(1) / keep(not_total('B')) / out.sku = text(col('A'))` - expected `target('products') / header(1) / keep(not_total('F')) / out.sku = text(col('A'))`

## 7. Improvement rounds

None yet.

## 8. Deviations and decisions

See DECISIONS.md; the main ones:

### Data and generator

1. **Language folders.** Eleven data folders for the ten languages:
   Traditional Chinese (zh-TW, zh-HK) has its own folder `zh-Hant`, as
   Appendix F's `data` column says. The helpers read both Chinese folders
   as the language `zh`.
2. **Who wrote the language data.** The headers, cell words and
   activities of each language (`gen/data/<folder>/headers.json`,
   `values.json`, `activities.json`) were written natively, one writer
   per language folder, from the briefing in
   `gen/data/BRIEFING_FOR_WRITERS.md`, and checked by
   `gen/validate_data.py` and against the real helpers. No translation
   tool, external model or internet text was used.
3. **Reused from the Extractor build.** Names, streets and cities per
   locale (`gen/data/<locale>/`), company-name words (`business.json`)
   and the registration-number generator (`gen/ids.py`) come from the
   Extractor's generator, which was also written from scratch. No Faker.
4. **Item prices.** An item's `usd` range describes prices in the
   folder's main country (fr-FR, en-US, ja-JP...). A price in another
   country of the same language is scaled by the ratio of price levels
   (`usd × rate × level / main level`), the Extractor's convention.
5. **Items whose duration is only a placeholder** (hotel nights,
   projects: `minutes` of 480 or more) get no duration in the sheet.
6. **Families are thin modules.** Each `gen/layouts/<target>__<id>.py`
   calls its target's builder with the features that define it (sizes as
   columns, section rows, a two-row header...). 78 families: products 15,
   services 9, opening_hours 8, staff 9, clients 9, bookings 9,
   invoice_ledger 9, refusals 10.
7. **Traps are drawn per task** at rates above the minimums of section
   10.4 (`gen/tasks.py`, `TRAPS`), and a family shows a drawn trap when it
   can; the checks measure the rates actually reached on `train`
   (`py gen/make.py smoke --check`). T4 is measured over every table with
   8 or more rows, T5/T6/T9/T14 over every table (refusals excluded), T13
   over tables with an amount.
8. **Row caps per target.** 3–400 rows log-uniform, capped at 60 for
   services and 7 for opening_hours (one row per day), 120 for staff.
9. **Totals filter convention.** A program gets `keep(not_total(<label
   column>))` only when a totals / subtotal row would otherwise be
   imported (the runtime's `totals_row_imported` check); a totals row
   that is already an empty row (for example a ledger's monthly subtotal
   without a date) needs no filter.
10. **Lists of people have a "Total: 23" row** in the name column when T4
    is drawn (a count of the people): the program must filter it.
11. **Notes rows (T14)** go into a column the program reads only as
    `text(col(...))`, and never into the one column that holds every
    required field (the line would become a record); with `sections()`
    they go in the first column, where a one-cell row is a title.
12. **Status words** are at most 19 characters (the VALUES line cuts at
    20). One word per status value per sheet. When a word with no enum
    value (draft, quote...) appears, it covers more than 2% of the rows,
    so the program leaves `status` out (section 6).
13. **A header that shows a currency is always used** in the program's
    `currency` (the model sees it), even when the family did not plan it.
14. **Arabic-Indic digits** replace a separator only between two digits
    (the dot of `ج.م` or `ر.س` stays a dot).
15. **Refusals.** The `answer` of a refusal task is its reason
    (`not_a_table`, `no_matching_target`, `missing_required:<field>`,
    `too_wide`). A table of one list of people is never offered as the
    other list of people (staff / clients) for `no_matching_target`.
    `missing_required` removes `price` (products), the times (bookings)
    or the invoice number (ledgers) from a table that was valid first.
16. **Task records** carry two fields besides section 10.7: `holdout`
    (the hold-out groups the sheet really shows) and `n_rows`. The checks
    use them.
17. **Discards** (check 1) count only self-check failures (a program that
    does not give the truth or fails a runtime check). A family that
    cannot draw its layout for the chosen activity or locale is "declined"
    and the task is drawn again; both are logged in `stats.json`.
18. **Every lookup key must be in the VALUES line;** a task where a layout
    pushed a status column past VALUES (more than 12 texts) is drawn
    again, and the day-grouped bookings layout keeps its status column
    out of column A.
19. **Real files.** For the 1% round trip, a CSV is written with every row
    padded to the sheet's width (as Excel writes CSV), so the delimiter
    can be sniffed; sheet names are made safe for files.

### Hold-out groups (section 11)

20. Drawn once, seed 7, by `gen/holdout.py` (`py gen/make.py
    --draw-holdout`). Per language folder and field with at least 4
    variants: one D and one T variant, preferring variants no other field
    of that language uses (so a held-out header is really unseen). The T
    variants were moved to `headers_test.json`; `holdout.json` stores only
    the D variants, the D family names and the list of known items.
21. Per target one D and one T family, never one that would leave a trap
    without a training family (measured by building 40 tasks of every
    family). For refusals, only the `not_a_table` families (7 of them) can
    be held out, so every refusal reason stays in training.
22. In `dev_heldout` and `test_heldout`, every third task uses one of the
    split's held-out families in turn, so each of them appears even in
    small splits.
23. **Honesty note:** when the draw was committed, `git status` printed
    the file names of the 8 moved T families. Their code was written
    before the draw; no test example was looked at.

### Helpers (each fix has a test, cases 1001+)

24. `integer()` reads a unit ending in 2 or 3 (`5 m²` after NFKC).
25. `hours()`: 

## 9. Known limits

* Training data is synthetic.
* `.xls` / `.ods` files are not read.
* At most 26 non-empty columns; one table per sheet.
* One row covering several days ("Lun–Ven 9h–18h") is not read.
* Formulas saved without a cached value arrive as empty.
* A product whose name begins with a totals word ("Total Care …") on a row
  with only numbers besides it is taken for a totals row.

## 10. Next steps for Laurent

On the desktop (RTX 4080), in PowerShell:

```powershell
cd "C:\Users\neomh\new model\tulip"
```
```powershell
py check.py
```
```powershell
py build.py full
```

Then import a real folder and look at the result:

```powershell
py import_sheets.py "C:\Users\Laurent\documents to publish" --db "C:\Users\Laurent\new model\documents.db" --targets products,services,opening_hours --locale fr-FR --show
```
