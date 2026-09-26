# Tulip 1.1, item F — the new tables, PROPOSED (not locked)

The work order asks to align these columns with the PLAN feature catalogue
(`plan-lab/design/FEATURES.md`, `features/catalogue-features.json`). That
catalogue was not available to this session, so the columns below are a
**proposal, listed in one place, waiting for the owner's confirmation**.
Nothing of item F is built or trained until they are confirmed: the
vocabulary, the generator and the model depend on them.

Formats are those of `tables.schema.json` (item A): `text`, `decimal`,
`integer`, `boolean`, `date`, `currency` (ISO 4217), `email`, `phone`
(E.164), `enum`. **Bold** = required (a row without it is not imported).

## stock — levels by item and location

| column | format | meaning |
|---|---|---|
| **item** | text | the product or ingredient, as the business names it |
| sku | text | its reference |
| location | text | shop, storeroom, cold room, van… |
| **quantity** | decimal | the level counted (2.5 kg is 2.5) |
| unit | text | kg, pieces, litres… as written |
| min_quantity | decimal | the reorder level, when the sheet has one |
| unit_cost | decimal | the purchase cost of one unit |
| currency | currency | |
| counted_on | date | the date of the count (a column, or the sheet's title) |

One row per item and location. The stock *value* column that many sheets
carry (quantity × cost) is not imported: it is computed, never typed.

## suppliers

| column | format | meaning |
|---|---|---|
| **name** | text | the company (or the person when there is none) |
| contact_person | text | |
| email | email | |
| phone | phone | |
| address | text | the street line when separate, else the whole address |
| postcode | text | |
| city | text | |
| country | text | |
| reg_id | text | VAT / company number (SIRET, P.IVA, INN, GSTIN…) |
| category | text | what they supply (flour, dairy, packaging…) |
| payment_terms | text | "30 days end of month", as written |
| lead_time_days | integer | days from order to delivery |

## purchase_orders — one row per order line

| column | format | meaning |
|---|---|---|
| **number** | text | the order number (repeated on each of its lines) |
| **date** | date | the order date |
| **supplier** | text | |
| **item** | text | |
| sku | text | the supplier's reference |
| **quantity** | decimal | |
| unit | text | |
| unit_price | decimal | without tax |
| total | decimal | the line total |
| currency | currency | |
| status | enum | draft, sent, confirmed, received, partly_received, cancelled |
| expected_date | date | the delivery date expected |

An order written as a block (number, date and supplier once above its
lines) is read with `sections()` or the new `carry()` below, like recipes.

## recipes — one row per ingredient line (parent/child)

| column | format | meaning |
|---|---|---|
| **recipe** | text | the recipe (the parent), on each of its ingredient rows |
| yield_quantity | decimal | how much one batch makes (12) |
| yield_unit | text | pieces, kg, portions… |
| **ingredient** | text | the child |
| **quantity** | decimal | of the ingredient, for one batch |
| unit | text | g, kg, ml, pieces… as written |
| note | text | "sifted", "at room temperature"… |

**How TulipScript expresses parent/child** (to be written into
DECISIONS.md once confirmed): the child rows are the imported rows, and
the parent is carried onto each of them, never invented:

* a recipe column on every row: `out.recipe = text(col('A'))` (today's
  TulipScript);
* one block per recipe, its name alone on a title row: `sections()` makes
  that row `col('section')`, so `out.recipe = text(col('section'))`
  (today's TulipScript);
* the name only on the first ingredient row, or merged down: a new
  function `carry(col('A'))` - the nearest filled cell above in the same
  column, within the data rows, traced to THAT cell. It is the one
  language change of item F; the runtime checks that a carried value
  never crosses a section title or a repeated header row.

The recipe table itself (one row per recipe, with its yield) is then
plain code: group the rows by recipe. Costing and production planning
are plain code on these rows, not model work (work order, section 2).

## allergens — one row per product and allergen present

| column | format | meaning |
|---|---|---|
| **product** | text | |
| **allergen** | enum | gluten, crustaceans, eggs, fish, peanuts, soy, milk, tree_nuts, celery, mustard, sesame, sulphites, lupin, molluscs |
| **presence** | enum | contains, may_contain ("traces") |
| note | text | "wheat, barley", "in the glaze"… |

The 14 EU allergens (Regulation 1169/2011, Annex II); the US "major food
allergens" (milk, eggs, fish, crustacean shellfish, tree nuts, peanuts,
wheat, soybeans, sesame) are all inside that list (wheat under gluten).
The usual sheet is a matrix - products down, allergens across, a mark in
the cells - which TulipScript already reads with `unpivot()`: the
allergen from the column header through a `lookup()`, the presence from
the mark. An empty cell means "not present" and gives no row.

## product_variants — sizes, weights, packs

| column | format | meaning |
|---|---|---|
| **product** | text | the base product |
| **variant** | text | "250 g", "large", "pack of 6", as written |
| sku | text | |
| barcode | text | |
| price | decimal | |
| currency | currency | |
| tax_included | boolean | |
| quantity | decimal | the net quantity of the variant (250) |
| quantity_unit | text | g, kg, ml, l, pieces |
| pack_size | integer | units in a pack (6) |
| stock | integer | |
| active | boolean | |

`products` keeps its `variant` column for the simple case (one row per
thing sold); `product_variants` is for sheets that list a product's
variants with their own references, sizes and packs.

## Questions for the owner

1. Do these columns mean the same as in the feature catalogue (stock,
   recipes and suppliers especially, for the till and the accounting)?
   Any column to add, rename or drop?
2. Recipes: is "one row per ingredient, the recipe carried on each row"
   right, and is the new `carry()` function acceptable?
3. Allergens: rows only for allergens present (contains / may contain),
   or also an explicit "free from" row?
4. Purchase orders: one row per order line (the order's number, date and
   supplier repeated), as proposed?
