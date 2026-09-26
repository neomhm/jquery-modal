# Tulip 1 — the Importer: build report

## 1. Summary

* **smoke**: dev_heldout pass@1 0.000 / loop 0.020; val pass@1 0.020 / loop 0.020 (dev splits only)
* **pilot**: dev_heldout pass@1 0.104 / loop 0.136; val pass@1 0.128 / loop 0.146 (dev splits only)

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
| train | 60000 | 184 | 0 | 0 | 600 | 0 |
| val | 500 | 0 | 0 | 0 | 5 | 0 |
| dev_heldout | 500 | 2 | 0 | 0 | 5 | 0 |
| test_seen | 500 | 0 | 0 | 0 | 5 | 0 |
| test_heldout | 500 | 1 | 0 | 0 | 5 | 0 |
| test_locale | 200 | 1 | 0 | 0 | 2 | 0 |
| traps | 300 | 1 | 0 | 0 | 3 | 0 |

train, by language: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%

train, by answer: products 21.5%, services 13.8%, invoice_ledger 11.6%, clients 10.5%, opening_hours 10.3%, bookings 10.2%, staff 10.1%, no_matching_target 6.4%, missing_required 3.1%, not_a_table 2.0%, too_wide 0.5%

refusal share: 12.0%

train, by family (62 families): bookings.date_time 877, bookings.day_sections 860, bookings.duration 868, bookings.staff_price 859, bookings.start_end 880, bookings.time_range 877, bookings.title_rows 898, clients.address_one_cell 979, clients.address_split 905, clients.crm_export 878, clients.first_last 888, clients.private_persons 871, clients.registration 901, clients.title_rows 889, invoice_ledger.credit_notes 1072, invoice_ledger.csv_export 1101, invoice_ledger.currency_header 1093, invoice_ledger.due_paid 1047, invoice_ledger.monthly_subtotals 446, invoice_ledger.status 1066, invoice_ledger.title_rows 1119, opening_hours.abbreviations 729, opening_hours.days_columns 2349, opening_hours.days_rows 801, opening_hours.morning_afternoon 732, opening_hours.notes_column 781, opening_hours.opens_closes 783, products.catalogue 1018, products.csv_export 1055, products.currency_header 1049, products.extra_columns 1094, products.repeated_headers 1073, products.sections 781, products.simple 1019, products.size_columns 835, products.size_columns_sections 698, products.title_rows 1050, products.totals 1073, products.two_prices 1096, products.two_row_header 1067, refusals.agenda_grid 230, refusals.budget 258, refusals.matrix 245, refusals.missing_required 1882, refusals.not_offered 3811, refusals.notes_page 234, refusals.pivot 227, refusals.too_wide 325, services.csv_export 1232, services.duration_column 1226, services.from_prices 1293, services.sections 690, services.staff_column 1276, services.title_rows 1260, services.two_prices 1305, staff.department_sections 778, staff.first_last 883, staff.full_name 898, staff.hr_export 818, staff.last_first 896, staff.role_department 906, staff.start_dates 870

Generator self-checks (section 10.8):

* PASS 1 self-check discards <= 0.5%
  * 189 discards of 62689 tasks (0.30%); 0 tasks could not be made
* PASS 2 programs canonical
  * 0 not canonical
* PASS 3 traps, families, languages
  * T1 35% of products (needs 30%)
  * T2 24% of products and services (needs 20%)
  * T3 13% of products (needs 10%)
  * T4 43% of tables with >= 8 rows (needs 40%)
  * T5 57% of tables (needs 50%)
  * T6 10% of tables (needs 10%)
  * T7 27% of products and services (needs 25%)
  * T8 17% of products (needs 15%)
  * T8 47% of opening_hours (needs 40%)
  * T9 16% of tables (needs 15%)
  * T10 55% of staff (needs 50%)
  * T10 53% of clients (needs 30%)
  * T11 43% of bookings (needs 40%)
  * T12 77% of bookings and ledgers (needs 70%)
  * T13 40% of amount tables (needs 30%)
  * T14 29% of tables (needs 20%)
  * missing_required (T15) 3.1% of tasks (3.5%)
  * no_matching_target 6.4% of tasks (6.0%)
  * not_a_table 2.0% of tasks (2.0%)
  * too_wide 0.5% of tasks (0.5%)
  * every family appears in its splits
  * languages: ar 10.0%, zh 10.0%, en 10.0%, fr 10.0%, ru 10.0%, es 10.0%, it 10.0%, hi 10.0%, ja 10.0%, ko 10.0%
* PASS 4 real-file round trip (1%)
  * 625 files, 0 with a different preview
* PASS 5 helpers give the truth >= 99.5%
  * 99.997% of 13822953 values
* PASS 6 hold-out rules
  * all kept
* PASS 7 token lengths
  * checked by the tokenizer stage (pack)
* PASS 8 NFKC programs, lookup keys in the preview
  * 0 programs not NFKC, 0 lookup keys not in VALUES

Preview tokens per language (train):

| language | p50 | p95 | max |
|---|---|---|---|
| ar | 782 | 1794 | 4307 |
| en | 779 | 1794 | 4618 |
| es | 773 | 1837 | 4462 |
| fr | 785 | 1792 | 4636 |
| hi | 773 | 1810 | 4486 |
| it | 770 | 1745 | 4317 |
| ja | 820 | 1948 | 4970 |
| ko | 815 | 1884 | 4930 |
| ru | 845 | 1870 | 5053 |
| zh | 792 | 1864 | 4732 |

Tasks over 4,096 tokens: 68 of 62500 (0.1%). Tokenizer round trip on val programs: 0 failures.

## 4. Model — pilot

Preset **pilot**: vocabulary 16000, d_model 256, 6 layers, 4 heads, ffn 704, max_len 4096, dropout 0.0.

Parameters: 8916224 (4820224 outside the embedding). Steps: 2711 of 2711 planned (0.70 epochs), 87.1 training minutes. Chosen checkpoint: step 2711 (dev sample execution match 0.1040).

Loss curve (step: smoothed loss): 50: 5.139, 700: 0.349, 1400: 0.227, 2050: 0.164, 2700: 0.165

Model-selection evaluations: step 451: 0.000, step 921: 0.024, step 1392: 0.026, step 1863: 0.074, step 2334: 0.070, step 2711: 0.104

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
| val | 500 | 0.128 | 0.146 | 0.125 | 100 (64.1%) | 0.7142857142857143 / 0.38461538461538464 | 0.8214 | 0.632 | 0.621 / 1.497 | 5.058 / 14.443 |
| dev_heldout | 500 | 0.104 | 0.136 | 0.079 | 78 (69.0%) | 0.5070422535211268 / 0.631578947368421 | 0.7223 | 0.632 | 0.625 / 1.579 | 5.022 / 15.629 |

##### val: loop by language, target and trap

languages: ar 0.18, en 0.2, es 0.14, fr 0.08, hi 0.18, it 0.1, ja 0.08, ko 0.18, ru 0.22, zh 0.1

targets: bookings 0.0, clients 0.0612, invoice_ledger 0.0, opening_hours 0.5522, products 0.0515, refusal 0.3269, services 0.0278, staff 0.1552

traps: T1 0.0, T2 0.0, T3 0.0, T4 0.041, T5 0.0738, T6 0.0612, T7 0.0189, T8 0.5306, T9 0.0278, T10 0.1129, T11 0.0, T12 0.0109, T13 0.0, T14 0.0602, T15 0.2222

##### dev_heldout: loop by language, target and trap

languages: ar 0.08, en 0.02, es 0.14, fr 0.2, hi 0.2, it 0.02, ja 0.08, ko 0.28, ru 0.1, zh 0.24

targets: bookings 0.0164, clients 0.037, invoice_ledger 0.0, opening_hours 0.4894, products 0.0217, refusal 0.5789, services 0.0526, staff 0.0588

traps: T1 0.0278, T2 0.069, T3 0.0, T4 0.0461, T5 0.0949, T6 0.0345, T7 0.0238, T8 0.5714, T9 0.0385, T10 0.0909, T11 0.0217, T12 0.0, T13 0.0206, T14 0.0063, T15 0.25

#### Error groups (val and dev_heldout only)

val: wrong_header_row 201, unparsable_program 84, missing_field 38, wrong_refusal 27, extra_field 26, wrong_layout 22, wrong_column 20, wrong_filter 19, wrong_helper 7, refused_importable 4, wrong_target 3

dev_heldout: wrong_header_row 214, unparsable_program 96, refused_importable 31, missing_field 27, extra_field 22, wrong_refusal 20, wrong_layout 17, wrong_filter 12, wrong_column 9, wrong_helper 5, wrong_target 1, missing_filter 1



## 6. Error analysis — pilot (dev_heldout only)

* **wrong_header_row**: 214
  * `dev_heldout-000002` (services.staff_column, en): wrote `target('services') / header(1) / out.name = text(col('C')) / out.category = text(col('D'))` - expected `target('services') / header(4) / sections() / out.name = text(col('A'))`
  * `dev_heldout-000005` (staff.full_name, es): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('staff') / header(2) / keep(not_total('G')) / out.name = text(col('G'))`
* **unparsable_program**: 96
  * `dev_heldout-000000` (bookings.datetime_cell, ar): wrote `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(col('A'))` - expected `target('bookings') / header(1) / out.date = date(col('D')) / out.start_time = time(col('D'))`
  * `dev_heldout-000004` (invoice_ledger.status, ru): wrote `target('invoice_ledger') / header(1) / out.number = text(col('A')) / out.date = date(col('B'))` - expected `target('invoice_ledger') / header(1) / out.number = text(col('G')) / out.date = date(col('F'))`
* **refused_importable**: 31
  * `dev_heldout-000025` (products.category_sheet, es): wrote `refuse('no_matching_target')` - expected `target('products') / header(1) / out.sku = text(col('A')) / out.name = text(col('B'))`
  * `dev_heldout-000036` (products.category_sheet, it): wrote `refuse('not_a_table')` - expected `target('products') / header(1) / out.sku = text(col('B')) / out.name = text(col('E'))`
* **missing_field**: 27
  * `dev_heldout-000003` (clients.companies, fr): wrote `target('clients') / header(1) / out.name = text(join(' ', col('B'), col('A'))) / out.address = text(col('C'))` - expected `target('clients') / header(1) / out.name = text(col('A')) / out.contact_person = text(col('E'))`
  * `dev_heldout-000022` (products.extra_columns, en): wrote `target('products') / header(1) / sections() / out.sku = text(col('A'))` - expected `target('products') / header(1) / sections() / out.sku = text(col('A'))`
* **extra_field**: 22
  * `dev_heldout-000049` (clients.companies, ko): wrote `target('clients') / header(1) / out.name = text(col('A')) / out.contact_person = text(col('B'))` - expected `target('clients') / header(1) / out.name = text(col('E')) / out.phone = phone(col('A'))`
  * `dev_heldout-000053` (opening_hours.days_rows, fr): wrote `target('opening_hours') / header(1) / out.day = weekday(col('A')) / out.hours = hours(col('B'))` - expected `target('opening_hours') / header(1) / out.day = weekday(col('A')) / out.hours = hours(col('B'))`
* **wrong_refusal**: 20
  * `dev_heldout-000013` (refusals.not_offered, fr): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(join(' ', col('A'), col('B')))` - expected `refuse('no_matching_target')`
  * `dev_heldout-000017` (refusals.not_offered, hi): wrote `target('services') / header(1) / out.name = text(col('A')) / out.category = text(col('B'))` - expected `refuse('no_matching_target')`
* **wrong_layout**: 17
  * `dev_heldout-000042` (services.simple, en): wrote `target('services') / header(1) / out.name = text(col('C')) / out.price = amount(col('B'))` - expected `target('services') / header(1) / sections() / out.name = text(col('A'))`
  * `dev_heldout-000067` (staff.department_sections, hi): wrote `target('staff') / header(1) / out.name = text(col('A')) / out.role = text(col('B'))` - expected `target('staff') / header(1) / sections() / out.name = text(col('A'))`
* **wrong_filter**: 12
  * `dev_heldout-000077` (staff.last_first, hi): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(join(' ', col('A'), col('B')))` - expected `target('staff') / header(1) / keep(not_total('B')) / out.name = text(join(' ', col('B'), col('A')))`
  * `dev_heldout-000085` (products.sections, es): wrote `target('products') / header(1) / sections() / keep(not_total('B'))` - expected `target('products') / header(1) / sections() / keep(not_total('A'))`
* **wrong_column**: 9
  * `dev_heldout-000008` (staff.hr_export, ja): wrote `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('staff') / header(1) / keep(not_total('A')) / out.name = text(col('A'))`
  * `dev_heldout-000027` (clients.companies, hi): wrote `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))` - expected `target('clients') / header(1) / keep(not_total('A')) / out.name = text(col('A'))`
* **wrong_helper**: 5
  * `dev_heldout-000058` (clients.address_split, ja): wrote `target('clients') / header(1) / out.name = text(join(' ', col('A'), col('B'))) / out.address = text(col('C'))` - expected `target('clients') / header(1) / out.name = text(join(' ', col('B'), col('A'))) / out.address = text(col('C'))`
  * `dev_heldout-000226` (bookings.date_time, it): wrote `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(col('A'))` - expected `target('bookings') / header(1) / out.date = date(col('A')) / out.start_time = time(col('A'))`

## 7. Improvement rounds

### Pilot, round 0 (the first pilot build) — the numbers before

30,000 training tasks; training stopped at the one-epoch limit (1,920
steps, 62 minutes; the 90-minute cap was not reached). Dev-sample execution
match during training: 0.002 (step 461), 0.004 (932), 0.042 (1,382), 0.082
(1,855).

| split | pass@1 | loop | needs_review | refusal P / R |
|---|---|---|---|---|
| val | 0.096 | 0.084 | 0.71 | 0.58 / 0.13 |
| dev_heldout | 0.082 | 0.086 | 0.72 | 0.87 / 0.35 |

Error groups (val + dev_heldout, 1,000 tasks): wrong header row 429,
unparsable program 202, missing field 85, wrong refusal 62, wrong layout
44, extra field 42, wrong column 31, filters 21.

Reading the examples (all 429 header-row errors counted, 12 read with
their previews; all 202 unparsable programs classified, 4 read in full):

* **Header row.** In 386 of 429 the model wrote `header(1)` where the
  header sits below 1–4 title rows (truth 2–5). The previews show the
  header clearly (the first multi-cell row, with its row number). Not a
  data problem: the model had not learned it yet.
* **Unparsable programs.** 149 of 202 are `duplicate_lookup_key`: the
  model writes status words from other languages or repeats a key instead
  of copying the VALUES line. Also under-training.
* **Data defect found:** Russian title rows put a month in the genitive
  ("Журнал счетов за января"): cosmetic, fixed after the final
  evaluation (see below).

Cause: under-training (the learning curve was still steep). Change,
allowed by section 22: **2× the training tasks (60,000)**, so training
runs the whole 90-minute cap instead of stopping after one short epoch.

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
