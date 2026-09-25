# Language data — what each file holds

One folder per language (`ar zh en fr ru es it hi ja ko`), plus **`zh-Hant`**:
Traditional Chinese as written in Taiwan and Hong Kong. `zh` holds Simplified
Chinese (mainland China, Singapore). Both carry the language label `zh`; the
generator uses `zh-Hant` for the TW and HK locales. Per-locale lists live in
folders named after the locale (`fr-FR`, `zh-TW` …).

The generator (`gen/*.py`) never contains words of any language. Every word,
keyword, sentence and heading lives in the JSON files below, so they can be read
and extended without touching code. After any edit, run:

```
py gen/validate_data.py
```

It checks every file and prints what is missing or wrong.

**Golden rules for everyone who writes these files**

1. Write **natively**, the way real documents read in that country. Never
   translate word for word. Invent your own sentences; do not copy text from the
   internet.
2. Chinese, Japanese: write without spaces between words, as the language is
   written. Korean: normal Korean spacing.
3. Slots (`{S_NAME}`, `{city}` …) are replaced by the generator. **UPPER-CASE slots
   become labelled spans; lower-case slots are plain text (label O).** Only the
   slots listed in this file exist.
4. **A labelled slot never touches a letter** of Latin, Cyrillic, Arabic or
   Devanagari script: write `{S_NAME} est`, never `{S_NAME}s` or `l{S_NAME}`.
   In Chinese, Japanese and Korean, touching is normal and allowed
   (`{S_NAME}は`, `{FOUNDED}에`, `成立于{FOUNDED}`).
5. **Arabic:** never attach a clitic (و ب ل ك ف ال) to a slot. Write
   `والشركة` or `، {S_NAME}` — never `و{S_NAME}` or `ب{FOUNDED}`.
6. **Korean particles** after a slot: write `{은/는}`, `{이/가}`, `{을/를}`,
   `{과/와}`, `{으로/로}` right after the slot; the generator picks the right one
   (`{S_NAME}{은/는}` → `한빛전자는`, `(주)한결은`).
7. Templates are one line (no `\n`). Keep sentences grammatical **whatever the
   value is**: a business name can be masculine or feminine, singular or plural
   — use constructions that do not agree with it ("L'entreprise …", "Notre
   équipe …", "Компания …", "الشركة …").
8. Never write a keyword that a slot already contains: `{S_REG_ID}`,
   `{C_REG_ID}` and `{ACTIVITY_CODE}` produce their own keyword ("SIRET 123 456
   782 00010", "ИНН 7707083893", "APE 1071C").

## Slots

### Labelled slots (UPPER CASE → a span)

| slot | becomes |
|---|---|
| `{S_NAME}` | the subject organisation's name as used in this document (may include its legal form) |
| `{S_NAME:legal}` | the subject's full legal name, with legal form |
| `{S_ADDRESS}` | the subject's full postal address, on one line |
| `{S_PHONE}` `{S_EMAIL}` `{S_URL}` | a phone number, e-mail, website / social link of the subject (write the keyword yourself: "Tél. {S_PHONE}") |
| `{S_PERSON}` | the subject's manager / owner / director: the name only (write the title yourself or use `{manager_title}`) |
| `{S_REG_ID}` | keyword + registration number, e.g. "SIRET 123 456 782 00010" (only the number is labelled) |
| `{C_NAME}` | one counterparty / client **organisation** (each `{C_NAME}` in a template is a different one) |
| `{C_NAME_LIST}` | 2–4 client organisations joined with the language's list separators |
| `{C_ADDRESS}` `{C_REG_ID}` | the counterparty's address / keyword + registration number |
| `{LEGAL_FORM}` | the subject's legal form standing on its own, e.g. "SARL", "株式会社" |
| `{CAPITAL}` | share capital with currency, e.g. "10 000 €", "1,000万円" |
| `{FOUNDED}` | founding year: "1998"; zh/ja "1998年" (ja also "平成10年"); ko "1998년" |
| `{FOUNDED:date}` | full founding date: "15 mars 1998", "1998年3月15日", "15.03.1998" |
| `{FOUNDED:month}` | month and year: "mars 1998", "1998年3月". Russian: only after a colon (nominative) |
| `{STAFF}` | number of employees, maybe with approximation: "12", "plus de 50", "約50名", "25명", "约120人" — zh/ja/ko include the counter (人 名 명); other languages add the noun with `{staff_noun}` |
| `{REVENUE}` `{REVENUE_YEAR}` | latest annual revenue with currency ("1,24 M€", "12億4,000万円") and its year ("2023", "FY 2022-23", "2023年度") |
| `{REVENUE_PREV}` `{REVENUE_YEAR_PREV}` | the previous year's revenue and year |
| `{ACTIVITY}` | one activity phrase of the business, a bare noun phrase without article ("boulangerie-pâtisserie artisanale") |
| `{ACTIVITY_CODE}` | keyword + code: "APE 1071C", "ОКВЭД 10.71" |
| `{SERVICE}` | one product or service the subject sells |
| `{SERVICE_LIST}` | 2–5 services joined with list separators |
| `{HOURS}` | compact opening hours: "Lun–Ven 7h–19h, Sam 7h–13h", "平日 9:00〜18:00" |
| `{HOURS:prose}` | opening hours as a phrase: "du lundi au vendredi de 9h à 18h" |
| `{CERT}` `{CERT_LIST}` | one / several certifications, labels, awards or memberships |
| `{DOC_DATE}` | the issue date of THIS document (only in `phrases.place_date`, letters and contract signatures) |

### Plain slots (lower case → O)

| slot | becomes |
|---|---|
| `{city}` `{country}` | a city / country name |
| `{year}` | a year that is **not** a founding year (renovation, move, award, model year, offer validity) |
| `{date}` `{date_start}` `{date_end}` | a date that is not the document's issue date |
| `{weekday}` `{time}` | a weekday name, a time of day |
| `{n_days}` | a number of days ("30") |
| `{n_years}` `{n_clients}` `{n_shops}` `{n_vehicles}` `{n_products}` `{n_projects}` `{n_countries}` | number + noun, e.g. "20 ans", "500 clients", "3 boutiques" (from `lexicon.counted`) |
| `{partner}` `{supplier}` `{bank}` `{competitor}` `{other_org}` | the name of another organisation (partner, supplier, bank, competitor, anyone else) |
| `{other_address}` | the address of another organisation |
| `{client_founded}` | the founding year of a client (not of the subject) |
| `{person}` `{position}` | a person who is **not** the manager, and their job title |
| `{manager_title}` | a manager title word, e.g. "Gérant", "代表取締役" |
| `{staff_noun}` | the word for employees, agreeing with the `{STAFF}` number |
| `{amount}` `{percent}` `{quantity}` | an amount that is not revenue / total / price, a percentage, a quantity |
| `{invoice_no}` `{order_no}` | a document number |
| `{currency}` | a currency name ("euros") |
| `{p}` `{n}` | page number and page count |

## `<lang>/lexicon.json`

```json
{
  "lang": "fr",
  "months": {"full": [12 names], "short": [12 abbreviations as written, with or without dot]},
  "weekdays": {"full": [7, Monday first], "short": [7]},
  "numbers": {"units": [21 words: 0..20], "tens": {"20": "vingt", "30": "trente", ..., "90": "quatre-vingt-dix"},
              "hundreds": {"100": "cent", "200": "deux cents", ..., "900": "neuf cents"},
              "big": {"1000": "mille", "1000000": "million", "1000000000": "milliard"}},
  "currency_names": {"EUR": ["euro", "euros"], "USD": ["dollar", "dollars"], ...},
  "kw": {"<concept>": ["variant", "variant", ...], ...},
  "units": {"piece": [...], "hour": [...], ...},
  "staff_noun": {"one": "salarié", "other": "salariés"},
  "counted": {"years": {"one": "{n} an", "other": "{n} ans"}, "clients": {...}, "shops": {...},
              "vehicles": {...}, "products": {...}, "projects": {...}, "countries": {...}},
  "manager_titles": ["Gérant", "Président", ...],
  "positions": ["Comptable", "Assistante de direction", ...],
  "departments": ["Comptabilité", "Ventes", ...],
  "honorifics": {"male": ["M."], "female": ["Mme"]},
  "list_join": {"sep": ", ", "last": " et "},
  "country_names": {"FR": "France", ...},
  "brand_words": [...],
  "name_patterns": ["{activity_word} {family}", "{brand}", ...],
  "orgs": {"banks": {"FR": [...], ...}, "registry": {"FR": [...]}, "tax_office": {"FR": [...]},
           "auditor": [...], "notary": [...], "hosting": [...], "insurers": [...],
           "public_bodies": [...], "associations": [...]},
  "certs": [{"name": "ISO 9001", "countries": ["*"], "groups": ["*"]}, ...]
}
```

* `months`: Russian also `"genitive"` (января …). Arabic: `"full"` = the Egyptian/Gulf
  series (يناير فبراير …), plus `"levantine"` (كانون الثاني شباط …), `"maghrebi"`
  (يناير فبراير مارس أبريل ماي يونيو يوليوز غشت شتنبر أكتوبر نونبر دجنبر) and `"hijri"`
  (محرم صفر ربيع الأول …). Japanese / Chinese / Korean: `"full"` = 1月 … 12月 (1월 …);
  `"short"` may repeat them.
* `numbers`: the plain number words (for amounts written in words). Hindi: `"units"`
  holds 0..100 (101 words, because Hindi numbers 21–99 are irregular). Chinese: also
  `"financial"` = the capital-form characters 零壹贰叁肆伍陆柒捌玖拾佰仟 in order
  (`zh-Hant`: 零壹貳參肆伍陸柒捌玖拾佰仟).
* `currency_names`: every currency used by this language's locales, plus EUR and USD.
* `kw`: **every concept of `concepts.json`**, each a list of variants as really written
  (≥ 3 wherever the language has them). Keep real capitalisation.
* `units`: every unit of `concepts.json`.
* `staff_noun` and `counted`: plural forms, keyed by the language's plural categories:
  `one`/`other` (en fr es it hi), `one`/`few`/`many` (ru), `zero`/`one`/`two`/`few`/
  `many`/`other` (ar), `other` only (zh ja ko). `counted` values contain `{n}` and
  include the noun or counter: "{n} ans", "{n} года", "{n}年", "{n}개 매장", "{n} عاماً".
* `manager_titles` ≥ 6 · `positions` ≥ 15 (people who are not the manager: accountant,
  sales, assistant, technician, driver, cook …) · `departments` ≥ 8.
* `honorifics`: prefixes; a suffix (様, 님, 先生) is written with a leading `~`
  ("~様").
* `list_join`: how lists are written ("A, B et C" → sep ", ", last " et "). Arabic:
  do not attach و to the next item (use "، " for both, or " و " with spaces).
* `country_names`: all 29 countries: SA AE EG MA CN TW HK SG US GB IN AU CA NG FR BE CH
  SN RU KZ BY ES MX AR CO CL IT JP KR.
* `brand_words` ≥ 60: short invented or fanciful words used as company brands, in this
  language's script ("Novalis", "サクラ", "한빛", "华信", "Ромашка", "النور", "श्री गणेश").
* `name_patterns` ≥ 6: how company names are built in this language, from `{family}`
  `{given}` `{brand}` `{activity_word}` `{city}` `{initials}`. Do **not** add the legal
  form (the generator attaches it, before or after, per country). Examples:
  fr `"{activity_word} {family}"`, `"{brand} {activity_word}"`, `"{activity_word} du {city}"`,
  `"{family} & Fils"`; ja `"{brand}{activity_word}"`; zh `"{city}{brand}{activity_word}"`;
  ar `"{brand} {activity_word}"` with activity words like "للتجارة".
* `orgs`: `banks` = real bank names per country of this language's locales (≥ 6 each);
  `registry` and `tax_office` = per country, ≥ 2 name patterns (may use `{city}`);
  `auditor` ≥ 4 accounting / audit firm patterns (use `{family}`); `notary` ≥ 2;
  `hosting` ≥ 4 web hosts; `insurers` ≥ 4; `public_bodies` ≥ 6 patterns (town hall,
  school, hospital, ministry … with `{city}` or `{family}`); `associations` ≥ 4 patterns.
  These names are always O.
* `certs` ≥ 20: certifications, quality labels, awards and memberships, each with
  `countries` (ISO codes or `"*"`) and `groups` (activity groups — food hospitality
  construction auto retail it professional creative transport realestate services
  education beauty health manufacturing — or `"*"`).

## `<lang>/sentences.json`

Sentence templates with slots. Categories marked **H** take part in the hold-out draw
(20 % of them are kept for testing only), so they need an `id` and at least 20 entries.

```json
{
  "lang": "fr",
  "activity": [{"id": "activity.fr.01", "text": "Notre métier : {ACTIVITY}."}, ...],
  ...
  "traps": [{"id": "trap.fr.01", "trap": "T7", "text": "Nos locaux ont été rénovés en {year}."}, ...],
  "filler": [{"id": "filler.fr.01", "text": "..."}, ...],
  "legal_footer": [{"id": "footer.fr.01", "countries": ["FR"], "text": "..."}],
  "invoice_notes": {...}, "phrases": {...}, "letters": {...}, "contract": {...},
  "terms": {...}, "web": {...}, "noise": {...}
}
```

| category | H | min | must contain | notes |
|---|---|---|---|---|
| `activity` | H | 20 | `{ACTIVITY}` | |
| `founded` | H | 20 | `{FOUNDED}`, `{FOUNDED:date}` or `{FOUNDED:month}` | the particle / preposition stays outside |
| `staff` | H | 20 | `{STAFF}` | add `{staff_noun}` where the language needs a noun |
| `revenue` | H | 20 | `{REVENUE}` | may add `{REVENUE_YEAR}`, `{REVENUE_PREV}`, `{REVENUE_YEAR_PREV}` |
| `services_intro` | H | 20 | `{SERVICE}` or `{SERVICE_LIST}` | |
| `clients` | H | 20 | `{C_NAME}` or `{C_NAME_LIST}` | client organisations named as references |
| `hours` | H | 20 | `{HOURS}` or `{HOURS:prose}` | |
| `certifications` | H | 20 | `{CERT}` or `{CERT_LIST}` | |
| `location` | H | 20 | one of `{S_ADDRESS}` `{S_PHONE}` `{S_EMAIL}` `{S_URL}` | |
| `capital` | H | 20 | `{CAPITAL}` | |
| `legal_form` | H | 20 | `{LEGAL_FORM}` | |
| `traps` | H | 48 | see below | each has `"trap"` |
| `filler` | H | 40 | no UPPER-CASE slot | neutral business sentences |

Every template of the fact categories may also use other slots (`{S_NAME}`, `{city}` …).
Write varied lengths: some 4-word labels ("Effectif : {STAFF}"), most full sentences.

**Traps** (≥ 8 of each): sentences that look like a fact but are **not** one.
* `T1` an amount near revenue-like words that is not revenue: "Notre plus gros chantier,
  d'une valeur de {amount}, …" (use `{amount}`).
* `T5` third parties: partners, banks, suppliers, competitors, a client's own founding
  year (`{partner}` `{bank}` `{supplier}` `{competitor}` `{client_founded}`).
* `T7` years that are not the founding year (`{year}`): renovated in, moved in, award
  year, offer valid until, model year.
* `T8` numbers that look like staff counts but are not: `{n_years}` of experience,
  `{n_clients}`, `{n_shops}`, `{n_vehicles}`, `{n_products}`, `{n_projects}`.
* `T11` people who are not the manager: `{person}` with `{position}`.
* `T13` client references (`{C_NAME}`) next to partner / supplier mentions (`{partner}`
  `{supplier}`) in the same sentence.

**Other categories** (plain strings, no ids needed, not held out):

* `legal_footer`: ≥ 3 per country of this language's locales; objects with `countries`.
  Legal mentions as printed at the bottom of invoices / letters, e.g.
  `"{S_NAME:legal} – {LEGAL_FORM} au capital de {CAPITAL} – {S_REG_ID} – {ACTIVITY_CODE}"`.
* `invoice_notes`: `payment_terms` ≥ 5 · `late_penalty` ≥ 2 · `vat_exempt` ≥ 2 · `thanks`
  ≥ 4 · `quote_validity` ≥ 3 · `quote_acceptance` ≥ 3 · `credit_reason` ≥ 3. Only lower-case
  slots (`{n_days}` `{date}` `{percent}` `{invoice_no}` `{amount}`).
* `phrases`: `page_x_of_y` ≥ 2 (`{p}` `{n}`) · `place_date` ≥ 2 (`{city}`, `{DOC_DATE}`)
  · `fin_amounts_note` ≥ 2 (`{currency}`; never "in thousands") · `fin_period` ≥ 2
  (`{date_start}` `{date_end}`) · `price_validity` ≥ 2 (`{date}`) · `signature_line` ≥ 2 ·
  `amount_in_words_intro` ≥ 2 (the words written before an amount in words, e.g.
  "Arrêté la présente facture à la somme de", "Rupees").
* `letters`: one object per scenario, `{"subject": [≥ 2], "body": [≥ 4]}`. `S_` means
  the **sending** organisation, `C_` the **addressed** organisation. Bodies are paragraphs
  (1–3 sentences each).

  | scenario | sender (S) | addressee (C) | notes |
  |---|---|---|---|
  | `payment_reminder` | the business | a client org | `{invoice_no}` `{date}` `{amount}` are O |
  | `quote_followup` | the business | a client org | may use `{SERVICE}` |
  | `price_change` | the business | a client org | a percentage, never a price |
  | `appointment` | the business | a client org | `{date}` `{time}` |
  | `closure` | the business | none | holiday closure, `{date_start}` `{date_end}`, may use `{HOURS}` |
  | `move` | the business | none | announces the NEW address `{S_ADDRESS}` |
  | `new_service` | the business | a client org | `{SERVICE}` / `{SERVICE_LIST}` |
  | `thanks` | the business | a client org | |
  | `order_to_supplier` | the business | a supplier org | the goods ordered are O text |
  | `letter_to_bank` | the business | none | the bank is `{bank}` (O) |
  | `order_from_client` | a client org | the business | the business's services are O here |
  | `complaint_from_client` | a client org | the business | |
  | `quote_request` | a client org | the business | |
  | `supplier_offer` | a supplier org | the business | the supplier's own offer: `{SERVICE}` of S |
  | `bank_notice` | none (a bank, `{bank}`) | the business | no S_ slot at all |
  | `loan_offer` | none (a bank) | the business | no S_ slot; amounts O |
  | `tax_reminder` | none (tax office, `{other_org}`) | the business | no S_ slot |
  | `registry_notice` | none (registry, `{other_org}`) | the business | no S_ slot |

* `contract`: lists of clause texts (≥ 2 each): `parties_provider` (S = the provider:
  `{S_NAME:legal}` `{LEGAL_FORM}` `{CAPITAL}` `{S_ADDRESS}` `{S_REG_ID}` `{S_PERSON}`
  `{manager_title}`), `parties_client` (C = the client: `{C_NAME}` `{C_ADDRESS}` `{C_REG_ID}`,
  its representative is `{person}` `{position}`), `preamble`, `object` (`{SERVICE}` or
  `{SERVICE_LIST}`), `duration`, `price` (`{amount}`), `payment` (`{n_days}`),
  `obligations`, `confidentiality`, `liability`, `termination`, `law` (`{city}`),
  `signature` (with `{city}` and `{DOC_DATE}`).
* `terms`: `cgv` ≥ 12 articles of general terms of sale · `privacy` ≥ 8 · `legal_notice`
  ≥ 8 lines (publisher: `{S_NAME:legal}` `{LEGAL_FORM}` `{CAPITAL}` `{S_ADDRESS}` `{S_REG_ID}`
  `{S_PHONE}` `{S_EMAIL}`; publication director `{S_PERSON}`; host `{other_org}`
  `{other_address}`) · `cookies` ≥ 3. May use S_ slots, `{S_URL}`, `{n_days}`, `{percent}`.
* `web`: `testimonials` ≥ 6 (customer quotes, `{person}`), `news` ≥ 6 (short news items of
  the business, `{date}`, may use `{SERVICE}`), `cta` ≥ 6 (calls to action).
* `noise`: text with **no** UPPER-CASE slots, except `press`: `meeting` ≥ 6 (internal
  meeting notes), `recipe` ≥ 4, `manual` ≥ 6 (instructions for a device / software),
  `news` ≥ 6 (general news, not about the business), `todo` ≥ 4, `memo` ≥ 6 (internal
  memos), `generic` ≥ 12 (any other everyday text), `press` ≥ 6 (a press article clearly
  about the business: may use `{S_NAME}` `{FOUNDED}` `{STAFF}` `{staff_noun}` `{ACTIVITY}`
  `{S_PERSON}` `{manager_title}` `{REVENUE}` `{REVENUE_YEAR}` `{city}`).

## `<lang>/titles.json`

```json
{
  "lang": "fr",
  "doc": {"invoice": [...], "tax_invoice": [...], "quote": [...], "proforma": [...],
          "receipt": [...], "credit_note": [...], "price_list": [...], "staff_list": [...],
          "purchase_order": [...]},
  "brochure": {"about": [...], "services": [...], "team": [...], "contact": [...],
               "clients": [...], "hours": [...], "history": [...], "values": [...],
               "certifications": [...], "why_us": [...], "news": [...], "testimonials": [...],
               "faq": [...], "location": [...], "taglines": [...]},
  "financials": {"income_statement": [...], "balance_sheet": [...], "annual_accounts": [...],
                 "key_figures": [...], "tax_summary": [...], "notes": [...]},
  "contract": {"titles": [...], "articles": {"definitions": [...], "object": [...], "duration": [...],
               "price": [...], "payment": [...], "obligations": [...], "confidentiality": [...],
               "liability": [...], "termination": [...], "law": [...], "signatures": [...]}},
  "terms": {"cgv": [...], "privacy": [...], "legal_notice": [...], "cookies": [...],
            "articles": {"scope": [...], "orders": [...], "prices": [...], "payment": [...],
                         "delivery": [...], "warranty": [...], "liability": [...],
                         "withdrawal": [...], "disputes": [...], "data_controller": [...],
                         "data_collected": [...], "purposes": [...], "retention": [...],
                         "rights": [...], "publisher": [...], "hosting": [...],
                         "intellectual_property": [...]}},
  "other": {"meeting": [...], "manual": [...], "recipe": [...], "news": [...], "memo": [...],
            "todo": [...], "press": [...], "report": [...]}
}
```

Minimums: `doc.*` ≥ 2 (≥ 1 for tax_invoice, proforma, purchase_order), `brochure.*` ≥ 2
(`taglines` ≥ 8: short slogans with no slot), `financials.*` ≥ 2, `contract.titles` ≥ 4,
every other list ≥ 1. Titles contain no slots, except `taglines` may use `{city}`.

## `<lang>/activities_part.json` (merged into `activities.json` by `gen/merge_data.py`)

```json
{
  "bakery": {
    "names": ["boulangerie-pâtisserie", "boulangerie"],
    "name_words": ["Boulangerie", "Fournil", "Pâtisserie"],
    "phrases": ["boulangerie-pâtisserie artisanale", "fabrication de pain au levain", ...],
    "services": [{"name": "Baguette tradition", "usd": [1.2, 1.8], "unit": "piece"}, ...]
  },
  ...all 40 activity ids of activities_base.json...
}
```

* `names` 2–3: what the activity is called. `name_words` 1–4: words used **inside company
  names** ("Boulangerie", "製パン", "베이커리", "للمخبوزات"). `phrases` 3–6: activity
  phrases as a business states them (≤ 200 characters, bare noun phrases without article).
* `services` 10–15: products or services such a business sells in this language's
  countries, natively named, with a typical US-dollar price range per unit and a unit
  from `concepts.json → units`. Never shipping, discounts, deposits, taxes or fees.

## `<locale>/names.json`, `streets.json`, `cities.json`

Own lists for every locale (the generator uses Faker only where it passes the checks of
section 10.3). One folder per locale, e.g. `gen/data/fr-FR/`.

* `names.json`: `{"given_male": [≥ 30], "given_female": [≥ 30], "family": [≥ 60]}`.
  Russian-script locales also `"family_female"` (same order as `family`),
  `"patronymic_male"` and `"patronymic_female"` (≥ 20 each). Names in the script used in
  that locale's documents.
* `streets.json`: `{"streets": [≥ 40]}` — street names with their type word as written in
  addresses ("rue des Alpes", "Via Roma", "ул. Ленина", "شارع التحرير", "테헤란로",
  "建国路"). Japan: building names instead ("サクラビル", "第2山田ビル").
* `cities.json`: a list of ≥ 30 places, with **real** postcodes of that place:

  | locales | fields |
  |---|---|
  | most | `{"city": "Lyon", "postcode": "69003", "region": ""}` — `postcode` may be a list; `region` = what addresses show (IT province code "MI", ES province, MX state "CDMX", AR "CABA", RU oblast …) |
  | ja-JP | `{"pref": "東京都", "city": "千代田区", "town": "丸の内", "postcode": "100-0005"}` |
  | zh-CN | `{"province": "广东省", "city": "深圳市", "district": "南山区", "postcode": "518057"}` (municipalities: province = city = "北京市") |
  | zh-TW | `{"city": "臺北市", "district": "信義區", "postcode": "110"}` |
  | zh-HK | `{"district": "中環", "region": "香港島"}` (no postcode) |
  | zh-SG | `{"city": "新加坡", "district": "...", "postcode": "018956"}` |
  | ko-KR | `{"sido": "서울특별시", "sigungu": "강남구", "dong": "역삼동", "postcode": "06236"}` |
  | en-IN, hi-IN | `{"city": "Mumbai", "state": "Maharashtra", "pin": "400069", "areas": ["Andheri East", ...]}` |
  | en-US | `{"city": "Chicago", "state": "IL", "zip": "60601"}` |
  | en-AU | `{"city": "Sydney", "state": "NSW", "postcode": "2000"}` |
  | en-CA, fr-CA | `{"city": "Toronto", "province": "ON", "postcode": "M5V 2T6"}` |
  | en-NG | `{"city": "Lagos", "state": "Lagos State", "areas": ["Victoria Island", ...]}` |
  | ar-SA, ar-EG, ar-MA, ar-AE | `{"city": "الرياض", "postcode": "12211", "districts": ["حي العليا", ...]}` (AE: `"postcode": ""`) |
  | es-MX | also `"districts": ["Col. Del Valle", ...]` (colonias) |
