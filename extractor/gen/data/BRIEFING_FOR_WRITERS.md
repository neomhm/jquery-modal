# Briefing for language-data writers — the Extractor project

You are helping build the **Extractor**: a small multilingual model that reads chunks of
business documents (invoices, brochures, registration papers, letters, price lists …) in
ten languages and marks spans such as the company name, address, founding year, revenue.
It is trained ONLY on synthetic documents made by a generator from the data files you are
writing now. **The model will be only as good as the natural, native, varied text you write.**
Documents must read the way real documents read in each country: real business phrasing,
real keywords, real formats — not translations of English.

The generator is code (not your concern). You write JSON data files in
`/home/user/jquery-modal/extractor/gen/data/`, exactly as specified in
`/home/user/jquery-modal/extractor/gen/data/SCHEMA.md` (read it completely first).

Rules for you:
* Write every word yourself, natively. Do not copy text from the internet, do not call any
  external tool or API to produce text, do not translate word for word.
* Work only on the files you are assigned. Never modify, move or delete any other file.
* Do not ask questions — decide sensibly yourself and keep going.
* Write the JSON files with a file-writing tool (UTF-8). Large files may be written in
  several steps (e.g. write a first half, then extend it), but the final file must be one
  valid JSON document.
* When done, run the validator on your files (command given in your task) and fix every
  ERROR until it reports 0 errors. Warnings are allowed but look at them.
* Finish with a short report: files written, counts, anything notable.

Below: the labelling rules of the model (section 5 of the build instructions). You do not
label anything yourself — slots do that — but your sentences must be consistent with these
rules: an UPPER-CASE slot must always be something the rules would label, and text that
the rules say is O (not labelled) must only ever come from lower-case slots or plain words.

## 5. Label schema and labelling rules — FIXED

### 5.1 The 25 span types (fixed order — this order defines the label ids)

In the examples, `⟦…⟧` marks the span. Keywords around it are **not** part of the span.

| # | type | what it is | examples |
|---|---|---|---|
| 1 | `S_NAME` | name of the subject organisation, as written, **including** an attached legal form | `⟦Boulangerie Martin SARL⟧` · `⟦株式会社サクラ商事⟧は` · `⟦ООО «Ромашка»⟧` · `⟦(주)한빛전자⟧` · `⟦शर्मा ट्रेडर्स प्राइवेट लिमिटेड⟧` |
| 2 | `S_ADDRESS` | full postal address of the subject; may span two or more lines | `Siège : ⟦12 rue des Alpes, 01210 Ferney-Voltaire⟧` · `⟦〒100-0005 東京都千代田区丸の内1-2-3⟧` |
| 3 | `S_REG_ID` | a company / tax / VAT registration number of the subject: the value only | `SIRET ⟦123 456 782 00010⟧` · `ИНН ⟦7707083893⟧` · `GSTIN: ⟦27AAPFU0939F1ZV⟧` · `統一編號 ⟦04595257⟧` |
| 4 | `S_PHONE` | a phone number of the subject (**never a fax**) | `Tél. ⟦+33 4 50 12 34 56⟧ – Fax 04 50 12 34 57` |
| 5 | `S_EMAIL` | an email address of the subject | `⟦contact@martin-boulangerie.fr⟧` |
| 6 | `S_URL` | a website or social-media address of the subject | `⟦www.sakura-shoji.co.jp⟧` · `⟦instagram.com/chezmartin⟧` |
| 7 | `S_PERSON` | the subject's legal representative, manager, owner or director: the name only, without the title | `Gérant : ⟦Jean Martin⟧` · `代表取締役 ⟦山田 太郎⟧` · `Генеральный директор ⟦Иванов И. И.⟧` |
| 8 | `C_NAME` | the counterparty **organisation**: customer, buyer or addressee; also client organisations named as references. Private persons are never `C_` (rule R9). | `Client : ⟦Hôtel du Lac⟧` · `⟦株式会社ABC⟧ 御中` · `购买方：⟦北京华信科技有限公司⟧` |
| 9 | `C_ADDRESS` | the counterparty organisation's postal address | |
| 10 | `C_REG_ID` | the counterparty organisation's registration / tax number | `GSTIN of recipient: ⟦29AAACB1234C1ZB⟧` |
| 11 | `LEGAL_FORM` | the subject's legal form, **only when written apart from the name** | `Forme juridique : ⟦SAS⟧` · `⟦SARL⟧ au capital de 10 000 €` · `企业类型：⟦有限责任公司⟧` |
| 12 | `CAPITAL` | share capital amount, with currency | `au capital de ⟦10 000 €⟧` · `資本金 ⟦1,000万円⟧` |
| 13 | `FOUNDED` | founding / incorporation / registration / opening date or year: **the date expression only**. CJK date characters (年月日, 년월일) belong to it; prepositions and particles (en, in, since, с, منذ, に, 에) do not. | `depuis ⟦1998⟧` · `⟦1998年⟧に設立` · `⟦2005년⟧에 설립` · `设立日期：⟦2015年6月8日⟧` |
| 14 | `STAFF` | number of employees of the subject: the number, plus approximation words and attached counters (名, 人, 명), **without** the noun | `⟦12⟧ salariés` · `従業員数 ⟦約50名⟧` · `직원 수 ⟦25명⟧` · `⟦plus de 50⟧ collaborateurs` |
| 15 | `REVENUE` | annual revenue / turnover of the subject, with currency and magnitude words. **Never** profit, an invoice total, a single order or a monthly figure. | `CA 2023 : ⟦1,24 M€⟧` · `売上高 ⟦12億4,000万円⟧` · `매출액 ⟦124억 원⟧` |
| 16 | `REVENUE_YEAR` | the year or period that a revenue figure refers to | `Chiffre d'affaires ⟦2023⟧` · `⟦FY 2022-23⟧` · `⟦令和5年度⟧` |
| 17 | `ACTIVITY` | the phrase stating what the subject does (≤ 200 characters). If an official scope is a long list, only the **first** item or clause. | `⟦boulangerie-pâtisserie artisanale⟧` · `经营范围：⟦软件开发⟧；信息技术咨询服务…` |
| 18 | `ACTIVITY_CODE` | an official **activity** classification code of any version (e.g. ATECO 2007 or ATECO 2025): NAF/APE, ATECO, NAICS, SIC, ОКВЭД, CNAE, SCIAN, ANZSIC, NIC, SSIC, CIIU, JSIC, KSIC. **Never** a product code (HSN, SAC, HS, SKU, EAN). | `Code APE ⟦1071C⟧` · `ОКВЭД ⟦10.71⟧` · `ATECO ⟦10.71.10⟧` |
| 19 | `SERVICE` | one product or service offered or sold by the subject: an invoice/quote line description, a price-list item, or a service-list item. **Never** shipping, discount, deposit, tax or fee lines. | `⟦Livraison viennoiseries⟧` · `⟦Website maintenance (monthly)⟧` |
| 20 | `HOURS` | the full opening-hours expression; may span lines | `⟦Lun–Ven 7h–19h, Sam 7h–13h⟧` · `⟦平日 9:00〜18:00⟧` |
| 21 | `CERT` | a certification, quality label, award or membership **name** | `⟦ISO 9001⟧` · `⟦Qualibat RGE⟧` · `⟦Maître Artisan⟧` |
| 22 | `DOC_DATE` | the **issue** date of an invoice, quote, receipt, letter, contract, registration extract or financial statement. **Never** a due, delivery or period date. | `Date : ⟦15/03/2024⟧ – Échéance : 14/04/2024` |
| 23 | `DOC_TOTAL` | the **final amount payable** of an invoice / quote / receipt (incl. tax). Subtotals and tax amounts are `O`. | `Total TTC ⟦2 220,00 €⟧` · `价税合计（小写）⟦¥12,400.00⟧` |
| 24 | `LINE_TOTAL` | the amount of one invoice / quote line | |
| 25 | `PRICE` | a unit price, in a price list, quote or invoice line | |

Label ids: `O` = 0; then for type k (1-based, in the table's order) `B-type` = 2k−1 and `I-type` = 2k. That gives **51 labels**. Build them with `decode.label_names(TYPES)` (Appendix E) and never reorder.

### 5.2 General rules

* **R1 — value only.** Never include the keyword or label: "Total :", "SIRET", "設立", "매출액", "Client:".
* **R2 — trimming.** A span never starts or ends with whitespace. It never ends with sentence punctuation (`. , ; : ، 。 、 ，`) unless that punctuation belongs to the written form:
  * abbreviation dots: `Pvt. Ltd.`, `S.A.`, `S.r.l.`
  * closing quotes or brackets of a name: `«Ромашка»`, `（株）`
* **R3 — every occurrence.** If a value appears several times in a chunk, label every occurrence.
* **R4 — no nesting, no overlap.** The more specific span wins:
  * A name with its legal form attached is one `S_NAME`. `LEGAL_FORM` is used only when the form stands apart.
  * Emails and URLs are their own spans; a name inside them is not labelled.
* **R5 — roles.** Decide S and C per document with this table:

| document type | S = subject | C = counterparty |
|---|---|---|
| invoice, receipt, credit note, quote | the issuer / seller | the customer: bill-to, buyer, 御中, 购买方, 공급받는자 |
| letter, email | the sending organisation — **except** a bank, registry, tax office or other public authority: then there is **no S** (the sender is `O`, rule R7) | the addressed organisation (so in a letter from a bank to the business, the business is `C_`) |
| contract | the party providing the goods or service | the client / buyer party |
| brochure, web page, price list, terms, staff list | the organisation presenting itself | clients named as references ("our clients include …") |
| registration extract, licence, certificate | the **registered** organisation (never the registry office) | — |
| financial statements | the **reporting** organisation (never the auditor or accountant) | — |
| other (press article, notes, manual) | only if the text is clearly about one organisation as its subject; otherwise nobody | — |

* **R6 — facts belong to S.** Fact types 11–25 always describe the S of **that** document. Facts about anyone else are `O`.
  * On a *purchase* invoice (S = a supplier), the supplier's lines, total and date are still labelled `SERVICE`, `LINE_TOTAL`, `DOC_TOTAL`, `DOC_DATE`.
  * `profile.py` later discards them, because that S is not the business. The model never has to know which organisation is "the business".
* **R7 — always `O`:**
  * **Other organisations:** bank names; registry, auditor and tax-office names; partners, suppliers mentioned in passing, competitors.
  * **Banking and personal data:** IBAN / account / SWIFT numbers; personal ID numbers; salaries.
  * **Document references:** invoice, order and customer numbers; page numbers.
  * **Amounts that are not the fields:** tax amounts and rates; subtotals; discounts, deposits, shipping and fees; amounts in words; profit, costs, assets and equity; share counts.
  * **Other numbers and codes:** quantities; percentages; product codes (HSN, SAC, HS, SKU, EAN); fax numbers.
  * **Other dates:** due dates, delivery dates, period dates.
  * **Look-alikes:** years of experience; counts of clients, products, shops or vehicles; award years unless they are inside a `CERT` name.
* **R8 — sole traders.**
  * A number shown as the business's tax or registration number is `S_REG_ID`, even when it is also the owner's personal tax number: PAN, ИИН, 12-digit ИНН, NIF / DNI, 13-character RFC, codice fiscale, RUT.
  * Identity-card and passport numbers, shown as identity documents, stay `O`.
  * The owner's name is `S_PERSON` when presented as owner. If the trade name is the person's name ("Jean Martin, plombier"), it is `S_NAME`.
* **R9 — private persons are never counterparties.** A private individual's name and address on a bill-to line, receipt or letter are `O`. `C_` labels are only for organisations: companies, sole-trader businesses with a trade name, public bodies and associations. This keeps private customers out of the profile. `profile.py` counts sales documents without a `C_NAME` as "private-customer documents" instead (15.6).


## Extracts from section 10 (generator principles, traps, noise)

### 10.1 Principles

* **You write every template and every word list yourself, natively, in all ten languages.** Do not translate word for word, do not call any external model or API, and do not copy text from the internet. Documents must read the way real documents read in that country.
* **Deterministic.** Every random choice uses `random.Random(seed)`, with the seed derived from (split name, folder index). Running the generator twice gives byte-identical data.
  * All dates are relative to `config.REFERENCE_DATE = date(2026, 6, 30)`. Never call `date.today()` or `datetime.now()` inside `gen/`.
* **Spans are created, never searched for.** Every labelled span comes from filling a slot with a known value, so its exact text and its normalized truth are known. The only exception is the handwritten set.
* **Chunking goes through Appendix B**, which reproduces ingest.py byte for byte and carries spans through the cuts. Parts of spans sliced by a chunk boundary become **cut ranges**; their tokens are ignored in training (label −100).
* **Readable data.** Code goes in `gen/*.py`. Language data goes in `gen/data/<lang>/*.json`, so Laurent can read and extend it. Every template has an id such as `brochure.founded.fr.07` or `invoice.L05`.

### 10.2 What you MUST write

### 10.6 Traps — MUST reach these rates

Each chunk record lists the trap ids it contains, so the traps suite can be scored trap by trap.

| id | trap | rate |
|---|---|---|
| T1 | invoice totals and single large orders near revenue-like words ("our biggest contract, worth €2M" → `O`) | every invoice; 10% of brochure and financial chunks |
| T2 | financial statements with ≥ 4 non-revenue rows (costs, gross / operating / net profit, assets, equity) | every financial statement |
| T3 | 2–3 years of revenue side by side | 60% of financial statements |
| T4 | purchase invoices (roles flipped: the business is `C_`) | ≥ 20% of invoices |
| T5 | third parties in prose: partners, banks, suppliers, competitors, a client's own founding year | 15% of brochure chunks |
| T6 | number look-alikes: phone next to fax, IBAN, invoice / order / customer numbers, postcodes, VAT rates, quantities | every invoice |
| T7 | non-founding years: awards, "renovated in", "moved in", offer validity, model years | 20% of brochure chunks |
| T8 | staff look-alikes: "20 years of experience", "500 clients", "3 shops", "12 vehicles" | 20% of brochure chunks |
| T9 | non-service invoice lines: shipping, discount, deposit, fee | 30% of invoices |
| T10 | amounts in words ("Rupees One Lakh … Only", "Arrêté la présente facture à la somme de …", 大写 壹万贰仟…, "فقط … لا غير", "금 일백이십사만원정") | 30% of invoices in IN, FR, MA, CN, TW, SA, AE, EG, KR; 10% elsewhere |
| T11 | people who are not the manager: sales contact, accountant, assistant | 20% of letters and brochures |
| T12 | chunks with no labels at all | ≥ 20% of all train chunks |
| T13 | client references (`C_NAME`) next to partner / supplier mentions (`O`) | 10% of brochure chunks |
| T14 | registry, auditor, notary and bank names in registration and financial documents (`O`) | every such document |
| T15 | due date and delivery date next to the issue date | every invoice |

### 10.7 Noise and variation — MUST, at these rates

**PDF text artefacts:**

* **Side by side:** seller block and buyer block merged line by line with 4–20 spaces, as pdfplumber does with two columns. 30% of PDF invoices and quotes.
* **Hard wraps:** at 60–110 characters, mid-sentence. 40% of PDF prose.
* **Hyphenation at a wrap:** fr, es, it, en, ru; 5% of wraps.
* **Repeated page header / footer:** a company footer line and "Page 1/2". 50% of multi-page PDFs.

**Spacing and OCR:**

* **Extra spaces or tabs** between words: 10% of documents.
* **OCR noise:** 1–2% character substitutions (0↔O, 1↔l, rn↔m, é→e) in 3% of documents. Spans keep the noised text; mark the chunk `noised: true`; do not test the normalizer on it.

**Digits and scripts:**

* Arabic-Indic digits: 50% of SA and 60% of EG documents.
* Devanagari digits: 20% of hi documents.
* Full-width digits: 25% of ja, 10% of zh.
* Script by locale: Traditional Chinese for TW and HK; Simplified for CN and SG.

**Names:**

* ALL-CAPS company names (Latin / Cyrillic): 10%.
* Japanese: (株) 20% and ㈱ 5% instead of 株式会社.
* Korean: (주) 30% and ㈜ 10% instead of 주식회사.
* Russian names in «» 70%, "" 20%, bare 10%.

**Language:**

* English words or labels mixed in: hi 30%, ar 20%, ja 15%, ko 10%, zh 10%, ru 5%.
* Bilingual labels ("Invoice / Facture", "فاتورة / Invoice"): 5% overall; 25% in CA, CH, BE, MA, HK, AE, SA.
* Accents dropped (fr, es, it): 5% of documents.

### 10.8 Output format
