# Briefing for the writers of Tulip's language data

Tulip reads spreadsheets (price lists, service menus, opening hours, staff
lists, client lists, booking exports, invoice registers) in ten languages
and writes a small program that loads them into fixed tables. It is
trained ONLY on synthetic spreadsheets made by our generator from the word
lists you write. The model will only ever be as good as these lists.

**Write natively.** Write what a real small business in that country puts
in its own spreadsheets: the words an accountant, a shop owner or a
receptionist really types, with their usual abbreviations. Never translate
word for word from English. Never copy text from the internet, never use
an external model or API. You are the native writer.

You write three files for ONE data folder `<L>` (a language code, or
`zh-Hant` = Traditional Chinese for Taiwan and Hong Kong):

* `tulip/gen/data/<L>/headers.json`
* `tulip/gen/data/<L>/values.json`
* `tulip/gen/data/<L>/activities.json`

Check them with `python3 tulip/gen/validate_data.py <L>` until it prints
`OK`. Do not create or change any other file.

Sources you MAY read (our own project data, written natively for the
Extractor): `extractor/gen/data/<L>/activities_part.json` (the items of
the 40 activities, with price ranges in USD), `extractor/gen/data/<L>/
lexicon.json` (months, weekdays, units, job titles, departments...). Use
them as a starting point; fix anything that is wrong.

General rules for every string:

* No leading or trailing spaces, no line breaks, no `|` character.
* At most 40 characters for a header, 32 for a value word.
* Within one list, no two entries that differ only by case or spaces.
* Placeholders, only where this briefing allows them: `{cur}` (the
  currency symbol of the country, e.g. `€`, `руб.`, `円`), `{year}`,
  `{month}` (a month name), `{date}` (a date), `{business}` (the
  business's name).

---

## 1. `headers.json` — column headers

```json
{
  "fields": { "<key>": ["variant", "..."] },
  "traps":  { "<key>": ["variant", "..."] },
  "extra":  { "<kind>": ["variant", "..."] },
  "groups": { "<key>": ["label", "..."] }
}
```

### `fields` — AT LEAST 8 different variants per key (10-12 is better)

Mix: the usual full form, short forms and abbreviations (`Réf.`, `Qté`,
`Tél.`), capitalised and plain forms, forms with a unit or a tax word
where the key allows it (`Prix (€)` is written `Prix ({cur})`, `Durée
(min)`). Every variant must mean exactly its key. One variant of every key
will be kept for testing only, so the more natural variety, the better.

| key | what the column holds | notes |
|---|---|---|
| `sku` | product code / reference | |
| `product_name` | name of the product | "Désignation", "Article" |
| `variant` | size / format / variant of a product | "Taille", "Contenance" |
| `description` | a description | |
| `category` | category / family / section of goods or services | |
| `price` | selling price, NEUTRAL (says nothing about tax) | at least 2 variants with `{cur}` |
| `price_incl` | selling price INCLUDING tax — the header must say it | "Prix TTC"; at least 2 with `{cur}` |
| `price_excl` | selling price EXCLUDING tax — the header must say it | "Prix HT"; at least 2 with `{cur}` |
| `vat_rate` | VAT / sales tax rate | "Taux TVA", "TVA %" |
| `stock` | quantity in stock (on hand) | never "ordered" |
| `unit` | unit of sale | "Unité", "U." |
| `barcode` | EAN / barcode | |
| `active` | is the product active / available / online (yes-no) | "Actif", "En vente" |
| `currency` | a currency column (values like EUR) | |
| `service_name` | name of a service | "Prestation", "Soin" |
| `duration` | duration of a service or booking | at least 2 with "(min)" |
| `performer` | the staff member who performs a service / booking | "Coiffeur", "Praticien", "Intervenant" |
| `day` | day of the week | |
| `hours` | opening hours of the day | "Horaires" |
| `hours_note` | a remark next to opening hours | "Remarque" |
| `morning` | morning opening hours | "Matin" |
| `afternoon` | afternoon / evening opening hours | "Après-midi" |
| `opens` | opening time | "Ouverture" |
| `closes` | closing time | "Fermeture" |
| `person_name` | full name of a person in one cell | "Nom et prénom", "Collaborateur" |
| `first_name` | given name | |
| `last_name` | family name | |
| `role` | job title | "Poste", "Fonction" |
| `department` | department / team | "Service" |
| `email` | email address | |
| `phone` | phone number | |
| `start_date` | hire date | "Date d'entrée" |
| `client_name` | client name in a client list (company or person) | "Client", "Nom du client" |
| `company` | company name | "Société", "Raison sociale" |
| `contact_person` | contact person at a client company | "Contact", "Interlocuteur" |
| `address` | a whole postal address in one cell | "Adresse complète" |
| `street` | street address only | "Adresse", "Rue" |
| `postcode` | postcode | "CP", "Code postal" |
| `city` | city | "Ville", "Localité" |
| `country` | country | |
| `reg_id` | VAT / company registration number | "N° TVA", "SIRET" |
| `client_since` | client since (a date) | "Client depuis" |
| `booking_date` | date of an appointment | "Date", "Jour du RDV" |
| `booking_datetime` | date AND time in one cell | "Date et heure", "Rendez-vous" |
| `start_time` | start time | "Heure", "Début" |
| `end_time` | end time | "Fin" |
| `time_range` | start and end time in one cell (`10:00-11:00`) | "Horaire", "Créneau" |
| `booking_client` | client name in a booking list | |
| `booking_service` | the service booked | "Prestation", "Motif" |
| `booking_status` | status of a booking | "Statut" |
| `invoice_number` | invoice number | "N° facture" |
| `invoice_date` | invoice date | "Date facture" |
| `invoice_client` | client of an invoice | |
| `total` | invoice amount, NEUTRAL (no tax word) | at least 2 with `{cur}` |
| `total_incl` | invoice amount INCLUDING tax — must say it | "Montant TTC" |
| `total_excl` | invoice amount EXCLUDING tax — must say it | "Montant HT" |
| `tax_amount` | the tax amount of an invoice | "TVA", "Montant TVA" |
| `invoice_status` | payment status of an invoice | "Statut", "Règlement" |
| `due_date` | due date | "Échéance" |
| `paid_date` | payment date | "Payée le", "Date de règlement" |
| `patronymic` | Russian only: patronymic (отчество). Other languages: `[]` | |
| `second_last_name` | Spanish only: second surname. Other languages: `[]` | |

### `traps` — AT LEAST 6 variants per key

Columns that LOOK like a field but are not. The model must learn to leave
them alone.

| key | meaning |
|---|---|
| `cost` | cost / purchase price (never the selling price) |
| `margin` | margin |
| `qty_ordered` | quantity ordered |
| `qty_sold` | quantity sold |
| `supplier_ref` | supplier's reference |
| `internal_notes` | internal notes / comments |
| `discount` | discount |

### `extra` — AT LEAST 6 variants per kind

Headers of irrelevant columns that real exports carry.

| kind | examples |
|---|---|
| `code` | internal code, location/shelf, batch, accounting code |
| `date` | created on, last modified, updated |
| `person` | created by, modified by, account manager |
| `word` | brand, colour, material, origin, season, channel |
| `number` | weight, minimum order, number of views, rating |

### `groups` — AT LEAST 4 labels per key

Group labels written ABOVE a header row (a two-row header: "Prix" above
"HT" and "TTC").

| key | above |
|---|---|
| `price` | the price columns |
| `stock` | the stock / quantity columns |
| `product` | the identification columns (code, name) |
| `contact` | the contact columns (phone, email) |
| `dates` | the date columns |

---

## 2. `values.json` — words that appear IN the cells

The helpers (plain code) must read many of these words, so write them
exactly as people type them, and include EVERY word given for your
language in the seed tables at the end of this briefing.

```json
{
  "weekdays": {"full": [7 names, Monday first],
               "short": [7 abbreviations, Monday first],
               "other": [[other spellings of Monday], [..Tuesday], ... 7 lists, may be empty]},
  "months": {"full": [12 names], "short": [12 abbreviations or []]},
  "closed": [at least 3 words meaning "closed" in an opening-hours cell],
  "yes": [at least 3], "no": [at least 3],
  "totals": [at least 3 labels of a TOTAL row],
  "subtotals": [at least 3 labels of a SUBTOTAL row; may be followed by a category name],
  "invoice_status": {"paid": [3+], "unpaid": [3+], "partial": [3+],
                     "overdue": [3+], "cancelled": [3+],
                     "other": [3+ statuses with NO equivalent: draft, quote, pro forma]},
  "booking_status": {"confirmed": [3+], "pending": [3+], "completed": [3+],
                     "cancelled": [3+], "no_show": [3+],
                     "other": [2+ statuses with no equivalent, e.g. "moved"]},
  "tax_included": [4+ phrases meaning "tax included", as written in a price header],
  "tax_excluded": [4+ phrases meaning "tax excluded"],
  "from_words": [2+ words written before a "from" price: "à partir de", "dès"],
  "units": {"piece": [2+], "kg": [1+], "g": [1+], "l": [1+], "ml": [1+],
            "box": [1+], "pack": [1+], "hour": [2+], "day": [1+], "month": [1+],
            "person": [1+], "session": [1+], "set": [1+], "m": [1+], "m2": [1+]},
  "minute_words": [2+ ways to write minutes after a number: "min", "minutes"],
  "hour_words": [2+ ways to write hours after a number: "h", "heures"],
  "am_pm": [["AM", "PM"], ...] or [] when 12-hour times are not used,
  "notes_rows": [6+ lines written UNDER a table; may use {date} {year}],
  "title_rows": {"products": [4+], "services": [4+], "opening_hours": [4+],
                 "staff": [4+], "clients": [4+], "bookings": [4+],
                 "invoice_ledger": [4+]},
  "sheet_names": {"products": [4+], "services": [4+], "opening_hours": [4+],
                  "staff": [4+], "clients": [4+], "bookings": [4+],
                  "invoice_ledger": [4+], "other": [4+]},
  "hours_notes": [5+ remarks next to opening hours: "sur rendez-vous"],
  "balance_rows": [2+ labels of a "balance carried forward" line in a register],
  "credit_note": [2+ words marking a credit note: "Avoir"],
  "not_a_table": {"notes_page": [8+ full sentences of a notes / memo sheet],
                  "summary": [6+ row labels of a summary or pivot table, e.g. "Chiffre d'affaires", "Charges"],
                  "chart": [4+ series names of chart data, e.g. "Ventes", "Visites"]},
  "budget": {"headers": [6+ headers of a budget sheet], "lines": [10+ budget line labels]}
}
```

Rules:

* `title_rows` are title lines above a table: `Tarifs {year}`, `Liste
  des prix – {business}`, `Horaires d'ouverture`, `Registre des factures
  {year}`, `Planning des rendez-vous – {month} {year}`.
* `notes_rows` are lines under a table: `Prix valables jusqu'au {date}`,
  `* Tarifs indicatifs, nous consulter`. They must NOT start with a
  totals word.
* `sheet_names`: short sheet-tab names (at most 25 characters): `Tarifs`,
  `Produits`, `Feuil1` (the default name of a new sheet in that
  language's spreadsheet program belongs in `other`).
* Status words: 3 or more DIFFERENT words per value, as they appear in
  real booking tools and invoice registers (abbreviated, past participle,
  noun...). A word may belong to one value only.
* `yes` / `no`: include the short marks people type in that language.

---

## 3. `activities.json` — what each of the 40 businesses sells

One entry per activity id (the ids of `extractor/gen/data/activities_base.json`):

```json
{
  "bakery": {
    "categories": ["Pains", "Viennoiseries", "Pâtisseries", "Traiteur"],
    "roles": ["Boulanger", "Pâtissier", "Vendeuse", "Apprenti boulanger", "Gérant"],
    "departments": ["Fournil", "Boutique", "Administration"],
    "items": [
      {"name": "Baguette tradition", "kind": "product", "category": "Pains",
       "usd": [1.3, 1.6], "unit": "piece"},
      {"name": "Pizza Margherita", "kind": "product", "category": "Pizzas",
       "usd": [9, 12], "unit": "piece", "variants": ["Petite", "Moyenne", "Grande"]},
      {"name": "Coupe femme", "kind": "service", "category": "Coupes",
       "usd": [35, 55], "unit": "session", "minutes": [30, 60]}
    ]
  }
}
```

* `items`: 15 to 30 per activity (aim for about 20). Start from the
  Extractor's items of that activity (keep their names and USD price
  ranges when they are good) and add more.
* `kind`: `product` for things sold, `service` for work or time sold
  (a hotel night, a lesson, a repair, an hour of consulting).
* `category`: one of the activity's `categories` (3 to 6 of them, as a
  business writes them as section titles or in a category column).
* `usd`: typical price range of ONE unit in US dollars, low then high.
* `unit`: one of piece kg g l ml box pack hour day month person session
  set m m2.
* `minutes`: services only — typical duration range in minutes (low,
  high), between 5 and 480. Every service has it.
* `variants`: optional, products only — 2 to 4 sizes or formats in
  increasing order (the price grows with the size). Give variants to at
  least 3 products of each activity that sells products.
* `roles`: 5 to 8 job titles of that business. `departments`: 2 to 4.
* Names: at most 32 characters, no `|`, no line breaks; they must not
  contain ` - `, ` – ` or ` / ` (those separate a name from its size in
  some sheets).

---

## 4. Seeds you MUST include (from the build instructions)

Everything listed here for your language must appear in your files
(weekdays in `weekdays`, closed / yes / no / totals in their lists,
statuses in `invoice_status` / `booking_status`, tax words in
`tax_included` / `tax_excluded`).

WEEKDAYS (Monday → Sunday)
* ar: الاثنين (also الإثنين) · الثلاثاء · الأربعاء · الخميس · الجمعة · السبت · الأحد
* zh: 星期一 … 星期日 (星期天) · 礼拜一 … (Traditional 禮拜一 …); short 周一 … 周日 · 週一 … 週日
* en: Monday … Sunday; Mon Tue Wed Thu Fri Sat Sun
* fr: lundi mardi mercredi jeudi vendredi samedi dimanche; lun. mar. mer. jeu. ven. sam. dim.
* ru: понедельник вторник среда четверг пятница суббота воскресенье; пн вт ср чт пт сб вс
* es: lunes martes miércoles jueves viernes sábado domingo; lun mar mié jue vie sáb dom · L M X J V S D (X = miércoles)
* it: lunedì martedì mercoledì giovedì venerdì sabato domenica; lun mar mer gio ven sab dom
* hi: सोमवार मंगलवार बुधवार गुरुवार शुक्रवार शनिवार रविवार
* ja: 月曜日 火曜日 水曜日 木曜日 金曜日 土曜日 日曜日; 月 火 水 木 金 土 日
* ko: 월요일 화요일 수요일 목요일 금요일 토요일 일요일; 월 화 수 목 금 토 일 · hanja 月 火 水 木 金 土 日

CLOSED · YES / NO · TOTALS
* ar: مغلق · عطلة | نعم / لا | المجموع · الإجمالي · المجموع الفرعي
* zh: 休息 · 不营业 · 公休 (不營業) | 是 / 否 · 有 / 无 (無) · √ / × · ○ / × | 合计 · 小计 · 总计 (合計 · 小計 · 總計)
* en: Closed | Yes / No | Total · Subtotal · Grand total
* fr: Fermé | Oui / Non | Total · Sous-total · Total général
* ru: Выходной · Закрыто | Да / Нет · + · х (Cyrillic tick) | Итого · Всего
* es: Cerrado | Sí (Si) / No | Total · Subtotal · Total general
* it: Chiuso | Sì (Si) / No | Totale · Subtotale · Totale generale
* hi: बंद · अवकाश | हाँ (हां) / नहीं | कुल · कुल योग · उप-योग · योगफल (NEVER the bare word योग)
* ja: 定休日 · 休み · 休業 | はい / いいえ · 有 / 無 · ○ / × | 合計 · 小計 · 総計
* ko: 휴무 · 정기휴무 · 휴일 | 예 (네) / 아니요 (아니오) · 유 / 무 · O / X | 합계 · 소계 · 총계

STATUS WORDS (invoice paid / unpaid / partial / overdue / cancelled; booking confirmed / pending / completed / cancelled / no_show)
* paid: مدفوعة · 已付款 · Paid · Payée / Réglée · Оплачен · Pagada · Pagata · भुगतान हो गया · 入金済 / 支払済 · 결제완료 / 입금완료
* unpaid: غير مدفوعة · 未付款 · Unpaid / Outstanding · Impayée / Non réglée · Не оплачен · Pendiente de pago · Da pagare · बकाया · 未入金 / 未払い · 미결제 / 미입금
* partial: مدفوعة جزئياً · 部分付款 · Partially paid · Partiellement payée · Частично оплачен · Pago parcial · Pagata parzialmente · आंशिक भुगतान · 一部入金 · 부분입금
* overdue: متأخرة · 逾期 · Overdue · En retard / Échue · Просрочен · Vencida · Scaduta · अतिदेय · 期日超過 · 연체
* cancelled (invoice): ملغاة · 已作废 · Cancelled (Canceled) / Void · Annulée · Аннулирован · Anulada · Annullata · रद्द · 取消 · 취소
* confirmed: مؤكد · 已确认 · Confirmed / Booked · Confirmé · Подтверждено · Confirmada · Confermata · पुष्टि हुई · 予約確定 · 예약확정
* pending: قيد الانتظار · 待确认 · Pending · En attente / À confirmer · Ожидает подтверждения · Por confirmar · In attesa · लंबित · 仮予約 · 확인대기
* completed: مكتمل · 已完成 · Completed / Done · Terminé · Выполнено · Realizada · Completata · पूर्ण · 完了 / 来店済 · 완료 / 방문완료
* cancelled (booking): ملغى (ملغي) · 已取消 · Cancelled (Canceled) · Annulé · Отменено · Cancelada · Annullata / Disdetta · रद्द · キャンセル · 예약취소
* no_show: لم يحضر · 未到店 · No-show · Absent · Неявка · No se presentó · Non presentato · अनुपस्थित · 無断キャンセル · 노쇼

(A word may be the same for invoices and bookings — "Annullata", "रद्द" —
because the two status lists are separate.)

TAX WORDS (included | excluded)
* ar: شامل الضريبة · شامل ضريبة القيمة المضافة | غير شامل الضريبة · بدون ضريبة
* zh: 含税 · 含稅 · 价税合计 | 不含税 · 未税 · 不含稅
* en: incl. VAT · VAT included · including GST · inc. GST · MRP (en-IN) | excl. VAT · excluding VAT · VAT not included · + VAT · plus GST
* fr: TTC · TVAC (BE) · TVA comprise · toutes taxes comprises | HT · HTVA (BE) · hors taxes · TVA non comprise
* ru: с НДС · включая НДС · в т.ч. НДС | без НДС · не включая НДС
* es: IVA incluido · IVA incl. · PVP | sin IVA · IVA no incluido · + IVA · más IVA
* it: IVA inclusa · IVA compresa | IVA esclusa · IVA non inclusa · + IVA · oltre IVA
* hi: कर सहित · GST सहित | कर रहित · GST अतिरिक्त
* ja: 税込 · 内税 | 税抜 · 税別 · 外税
* ko: 부가세 포함 · VAT 포함 | 부가세 별도 · 부가세 미포함 · VAT 불포함

`zh` (Simplified, for mainland China and Singapore) and `zh-Hant`
(Traditional, for Taiwan and Hong Kong) are two separate folders: write
each fully in its own script and in its own local usage (Taiwan says 統一
編號, 發票, 營業時間; Hong Kong says 營業時間, 發票 / 單據...).
