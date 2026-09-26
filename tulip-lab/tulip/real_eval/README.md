# real_eval — your own sheets, with the rows you approved

Put real sheets here that Tulip should import correctly, together with the
rows you checked by hand. `build.py` scores them in the `evaluate` stage and
the result appears in `REPORT.md` and `runs/<preset>/eval_tables.md`.

## How to add a sheet

1. Copy the file (`.xlsx` or `.csv`) into this folder, for example
   `tarifs-boulangerie.xlsx`.
2. Import it once and look at the result:

```powershell
py import_sheets.py "C:\Users\Laurent\new model\tulip\real_eval" --db "C:\Users\Laurent\new model\documents.db" --targets products,services --locale fr-FR --show
```

3. When the rows are right (or after you corrected them), add ONE line per
   sheet to `truth.jsonl` in this folder:

```json
{"file": "tarifs-boulangerie.xlsx", "sheet": "Tarifs", "locale": "fr-FR", "targets": ["products", "services"], "answer": "products", "truth": [{"name": "Baguette tradition", "price": 1.3}]}
```

* `sheet` is the tab name; for a `.csv` file it is the file name without
  `.csv`.
* `answer` is the target (`products`, `services`, `opening_hours`, `staff`,
  `clients`, `bookings`, `invoice_ledger`), or for a sheet that must be
  refused the reason: `not_a_table`, `no_matching_target`,
  `missing_required:<field>` or `too_wide` (then `truth` is `[]`).
* `truth` lists every imported row in sheet order, with only the fields
  that have a value (the field names are in section 6 of the build
  instructions and in `tulipscript.SCHEMAS`).

These sheets are never used for training.
