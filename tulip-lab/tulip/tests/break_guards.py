"""
Break every guard once and watch its test fail (section 5 of the Tulip
1.1 work order):

    py tests/break_guards.py            every guard
    py tests/break_guards.py A1 A4      some of them

Each entry below changes ONE piece of guarded code (a text replacement in
one file), runs the tests that guard it in a fresh Python, and expects at
least one of them to FAIL. The file is always put back afterwards, even
on Ctrl+C. A guard whose tests still pass when it is broken is reported
as NOT GUARDED and the script exits with an error.

This is not part of run_all.py: it runs the guarding tests once per
guard, and it edits the files while it runs.
"""
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent

# (id, what the guard is, file, the text, the broken text, tests)
GUARDS = [
    ("A1", "day of the week as a lower-case English name", "contract.py",
     "        return DAYS[value]\n",
     "        return DAYS[value].capitalize()\n",
     ["test_contract.test_the_conversions_the_skeleton_needed",
      "test_contract.test_import_sheet_writes_the_declared_format",
      "test_contract.test_every_column_is_pinned_on_generated_rows"]),
    ("A2", "a VAT rate as a percent, not Tulip's fraction", "contract.py",
     "        return round(float(value) * 100, 4)\n",
     "        return float(value)\n",
     ["test_contract.test_the_conversions_the_skeleton_needed",
      "test_contract.test_nothing_is_lost"]),
    ("A3", "one opening_hours row per range (a lunch break keeps its "
     "afternoon)", "contract.py",
     "            pieces = ranges if ranges else [\"closed\"]\n",
     "            pieces = ranges[:1] if ranges else [\"closed\"]\n",
     ["test_contract.test_the_conversions_the_skeleton_needed",
      "test_contract.test_nothing_is_lost",
      "test_contract.test_import_sheet_writes_the_declared_format"]),
    ("A4", "a value outside its declared format sends the sheet to review",
     "tulip.py",
     "        if wrong:\n",
     "        if False and wrong:\n",
     ["test_contract.test_a_value_outside_its_format_goes_to_review"]),
    ("A5", "check_value refuses a boolean that is not a boolean",
     "contract.py",
     "        if not isinstance(value, bool):\n            return \"not a "
     "boolean\"\n",
     "        pass\n",
     ["test_contract.test_check_value_rejects_the_old_formats"]),
    ("A6", "the schema file is what the rows are pinned against",
     "tables.schema.json",
     "\"values\": [\"monday\", \"tuesday\"",
     "\"values\": [\"Monday\", \"tuesday\"",
     ["test_contract.test_every_column_is_pinned_on_generated_rows",
      "test_contract.test_types_per_format_on_generated_rows"]),
    ("A7", "a Tulip 1 table is renamed, never deleted", "import_sheets.py",
     "                db.execute('ALTER TABLE \"%s\" RENAME TO \"%s\"' % (\n"
     "                    name, old + (\"_%d\" % k if k > 1 else \"\")))\n",
     "                db.execute('DROP TABLE \"%s\"' % name)\n",
     ["test_contract.test_a_tulip_1_database_is_migrated_not_lost"]),
    ("A8", "a sheet imported under an older schema version is imported "
     "again", "import_sheets.py",
     "                and prev[4] == contract.version())\n",
     "                )\n",
     ["test_contract.test_a_tulip_1_database_is_migrated_not_lost"]),
    ("A9", "the evaluation converts a truth written in Tulip's field "
     "kinds", "evaluate.py",
     "    return clean(contract.convert_rows(target, rows))\n",
     "    return clean(rows)\n",
     ["test_contract.test_evaluation_compares_in_the_declared_format"]),
    ("A11", "text is NFKC at output, even after a direction mark",
     "contract.py",
     "                    value = normal_text(value)\n",
     "                    pass\n",
     ["test_contract.test_text_is_nfkc_even_after_a_direction_mark"]),
    ("A10", "the database's column types come from the schema",
     "import_sheets.py",
     "    cols = \", \".join('\"%s\" %s' % (c[\"name\"], contract.sql_type(c))",
     "    cols = \", \".join('\"%s\" %s' % (c[\"name\"], \"TEXT\")",
     ["test_contract.test_database_columns_and_types_follow_the_schema"]),
    ("C1", "a model with no calibration never says sure",
     "confidence.py",
     "        return \"check\" if value >= 0.5 else \"unsure\"\n",
     "        return \"sure\" if value >= 0.5 else \"unsure\"\n",
     ["test_confidence.test_without_calibration_never_sure",
      "test_confidence.test_import_gives_each_mapped_column_a_band"]),
    ("C2", "agreement counts only candidates for the same table",
     "confidence.py",
     "                        if t == target and ex.get(f) == e) / float(n))",
     "                        if ex.get(f) == e) / float(n))",
     ["test_confidence.test_agreement_counts_same_target_and_same_expression",
      "test_confidence.test_import_gives_each_mapped_column_a_band"]),
    ("C3", "a program token's score is read at the position before it",
     "confidence.py",
     "        h = model.hidden(ids)[0, len(prompt_ids) - 1:-1]\n",
     "        h = model.hidden(ids)[0, len(prompt_ids):]\n",
     ["test_confidence.test_token_logprobs_are_the_full_pass_scores"]),
    ("C4", "sure is fitted on the 95% lower bound of its rate",
     "confidence.py",
     "            rate = wilson_low(right, n) if rule == \"low95\" else \\\n",
     "            rate = right / float(n) if rule == \"low95\" else \\\n",
     ["test_confidence.test_calibration_holds_on_new_columns"]),
    ("C5", "when the greedy program wins, the 7 sampled ones are still "
     "written for the agreement", "tulip.py",
     "        if len(candidates) == 1 and seen[\"n_sampled\"] > 0:\n",
     "        if False:\n",
     ["test_confidence.test_import_gives_each_mapped_column_a_band"]),
    ("C6", "the bands name the sheet's own column letters", "tulip.py",
     "                                     lambda x: original((0, x))[1], "
     "bands)}\n",
     "                                     lambda x: x, bands)}\n",
     ["test_confidence.test_import_gives_each_mapped_column_a_band",
      "test_confidence.test_the_band_reaches_tulip_imports_and_the_preview"]),
    ("C7", "a calibration file is only used for the model file it names",
     "confidence.py",
     "            if bands.get(\"model_sha256\") == file_sha256(model_path) "
     "and \\\n",
     "            if True and \\\n",
     ["test_confidence.test_a_calibration_file_is_used_for_its_own_model_only"]),
    ("C8", "a column of an import into the wrong table is wrong",
     "confidence.py",
     "    if target != task[\"answer\"]:\n",
     "    if False:\n",
     ["test_confidence.test_a_column_is_right_when_its_values_are_the_truths"]),
    ("C9", "the bands are stored in tulip_imports", "import_sheets.py",
     "             json.dumps(result.get(\"confidence\"), ensure_ascii=False)\n",
     "             json.dumps(None)\n",
     ["test_confidence.test_the_band_reaches_tulip_imports_and_the_preview"]),
    ("C10", "the runtime's unreadable cells lower the score",
     "confidence.py",
     "            out[parts[1]] = count / float(count + filled.get(parts[1], "
     "0))\n",
     "            out[parts[1]] = 0.0\n",
     ["test_confidence.test_unreadable_share_comes_from_the_runtime"]),
    ("C11", "the evaluation records the bands' signals for the calibration",
     "evaluate.py",
     "                                    confidence=confidence)\n",
     "                                    confidence=False)\n",
     ["test_confidence.test_the_evaluation_records_the_bands_signals"]),
    ("C12", "the build puts the calibration into the model file",
     "build.py",
     "    out = dict(conf[\"bands\"])\n",
     "    return None\n",
     ["test_confidence.test_the_build_calibrates_and_the_model_file_carries_it"]),
    ("C13", "the build measures the bands on test_heldout, which the fit "
     "never saw", "evaluate.py",
     "    if measure and not dev_only:\n",
     "    if False:\n",
     ["test_confidence.test_the_build_calibrates_and_the_model_file_carries_it"]),
    ("E1", "a removed row is marked, never deleted", "history.py",
     "    db.execute('UPDATE \"tulip_%s\" SET _removed = ? WHERE rowid = ?'\n"
     "               % target, (at, rowid))\n",
     "    db.execute('DELETE FROM \"tulip_%s\" WHERE rowid = ?' % target,\n"
     "               (rowid,))\n",
     ["test_history.test_an_edited_price_list_gives_exactly_its_differences",
      "test_history.test_a_sheet_that_moves_to_another_table"]),
    ("E2", "a row whose key is known is updated in place, not added again",
     "history.py",
     "        if key not in by_key:\n",
     "        if True:\n",
     ["test_history.test_an_edited_price_list_gives_exactly_its_differences"]),
    ("E3", "a sheet that now fails to import keeps its rows",
     "import_sheets.py",
     "                result[\"changes\"][\"removed_from_other_table\"] = "
     "moved\n        return import_id\n",
     "                result[\"changes\"][\"removed_from_other_table\"] = "
     "moved\n        else:\n            for t in contract.tables():\n"
     "                history.remove_all(db, t, result[\"file\"], "
     "result[\"sheet\"], import_id, at)\n        return import_id\n",
     ["test_history.test_a_failed_reimport_keeps_the_rows"]),
    ("E4", "products are paired by SKU when every row has one", "keys.py",
     "    \"products\": [[\"sku\"], [\"barcode\"], [\"name\", "
     "\"variant\"]],\n",
     "    \"products\": [[\"name\", \"variant\"]],\n",
     ["test_history.test_rows_are_paired_by_sku_when_every_row_has_one"]),
    ("E5", "the history keeps the old and the new value", "history.py",
     "                 before.get(c[\"name\"]), record.get(c[\"name\"]), "
     "row,\n",
     "                 record.get(c[\"name\"]), before.get(c[\"name\"]), "
     "row,\n",
     ["test_history.test_an_edited_price_list_gives_exactly_its_differences"]),
    ("E6", "an unchanged file is not imported again", "import_sheets.py",
     "            counts[\"unchanged\"] = counts.get(\"unchanged\", 0) + 1"
     "\n            continue\n",
     "            counts[\"unchanged\"] = counts.get(\"unchanged\", 0) + 1"
     "\n",
     ["test_history.test_an_unchanged_file_changes_nothing"]),
    ("E7", "a table made before the history gets its columns in place",
     "import_sheets.py",
     "            if have and have == want[:len(have)] and missing and all(\n",
     "            if False and have == want[:len(have)] and missing and all(\n",
     ["test_history.test_a_table_made_before_the_history_gets_its_columns"]),
    ("E8", "rows with the same key pair in their order", "keys.py",
     "            out.append(k if count[k] == 1 else \"%s#%d\" % (k, count[k]))\n",
     "            out.append(k)\n",
     ["test_history.test_rows_with_the_same_key_pair_in_their_order"]),
    ("B1", "the comparison never changes or drops a row", "compare.py",
     "                summary[\"new\"] += 1\n",
     "                summary[\"new\"] += 1\n                db.execute("
     "'DELETE FROM \"tulip_%s\" WHERE rowid = ?' % target, "
     "(recs[-1][\"row_id\"],))\n",
     ["test_compare.test_the_messy_example"]),
    ("B2", "the document date comes before the file date", "compare.py",
     "    for rule, field in ((\"document_date\", \"document_date\"),\n"
     "                        (\"file_date\", \"file_date\")):\n",
     "    for rule, field in ((\"file_date\", \"file_date\"),\n"
     "                        (\"document_date\", \"document_date\")):\n",
     ["test_compare.test_the_preferred_source_rule",
      "test_compare.test_the_messy_example"]),
    ("B3", "two dates are compared at the precision of the less precise",
     "compare.py",
     "        n = min(len(d), len(top))\n",
     "        n = len(top)\n",
     ["test_compare.test_the_preferred_source_rule"]),
    ("B4", "quantities are one unit in the key (0,25 kg = 250 g)",
     "keys.py",
     "    t = normal_units(t)\n",
     "    pass\n",
     ["test_compare.test_the_messy_example"]),
    ("B5", "keys are case folded", "keys.py",
     "    t = unicodedata.normalize(\"NFKC\", str(text)).casefold()\n",
     "    t = unicodedata.normalize(\"NFKC\", str(text))\n",
     ["test_compare.test_the_messy_example"]),
    ("B6", "rows marked removed are no source", "compare.py",
     "        '\"tulip_%s\" WHERE _removed IS NULL ORDER BY _file, _sheet, "
     "_row, '\n",
     "        '\"tulip_%s\" ORDER BY _file, _sheet, _row, '\n",
     ["test_compare.test_removed_rows_are_not_compared"]),
    ("B7", "a question is asked once", "compare.py",
     "                if db.execute(\"SELECT 1 FROM tulip_conflicts WHERE \"\n",
     "                if False and db.execute(\"SELECT 1 FROM tulip_conflicts "
     "WHERE \"\n",
     ["test_compare.test_a_question_is_asked_once_and_follows_the_data"]),
    ("B8", "a file in a suppliers' folder is a supplier's", "compare.py",
     "            return \"supplier\"\n",
     "            return \"business\"\n",
     ["test_compare.test_the_messy_example",
      "test_compare.test_dates_and_origins_in_every_language"]),
    ("B9", "a spelling of the key is not a contradiction", "compare.py",
     "                    names += [n for n in v if n not in names and n not in"
     "\n                              keys.GROUP_KEY[target]]\n",
     "                    names += [n for n in v if n not in names]\n",
     ["test_compare.test_the_messy_example"]),
    ("B10", "a French CSV with decimal commas splits on ;", "sheets.py",
     "    delimiter = csv_delimiter(text[:4096])\n",
     "    delimiter = csv.Sniffer().sniff(text[:4096], delimiters=',;\\t|')"
     ".delimiter\n",
     ["test_sheets.test_csv_delimiter_is_not_a_decimal_comma",
      "test_compare.test_the_messy_example"]),
    ("D1", "a lesson's rows must be the runtime's rows", "corrections.py",
     "        if res is None or not K.truth_matches(res, lesson[\"truth\"]):\n",
     "        if res is None:\n",
     ["test_corrections.test_a_remapped_column_round_trips_into_a_lesson"]),
    ("D2", "a correction leaves the PC only when shared", "corrections.py",
     "        if not c[\"shared\"] and not include_private:\n",
     "        if False:\n",
     ["test_corrections.test_corrections_stay_on_the_pc_unless_shared"]),
    ("D3", "an evaluation sheet is never a lesson", "corrections.py",
     "    if rows_hash(sheet.rows) in forbidden:\n",
     "    if False:\n",
     ["test_corrections.test_an_evaluation_sheet_is_never_a_lesson"]),
    ("D4", "the owner's letters are the sheet's own", "corrections.py",
     "            outs[field] = _expr(prog.target, field,\n"
     "                                compact_letter(letter, letters))\n",
     "            outs[field] = _expr(prog.target, field, letter)\n",
     ["test_corrections.test_the_owner_names_the_sheets_own_letters"]),
    ("D5", "a file changed since its import is not corrected blindly",
     "corrections.py",
     "    if imp.get(\"file_sha1\") and hashlib.sha1(\n",
     "    if False and hashlib.sha1(\n",
     ["test_corrections.test_a_changed_file_is_not_corrected_blindly"]),
    ("D6", "a lesson's program is canonical", "corrections.py",
     "        if ts.canonical(program) != program:\n",
     "        if False:\n",
     ["test_corrections.test_a_remapped_column_round_trips_into_a_lesson"]),
    ("D7", "a lesson's preview is the sheet's preview", "corrections.py",
     "    if sheets.preview(sheet, lesson[\"targets\"], lesson[\"locale\"]) != \\\n",
     "    if False and sheets.preview(sheet, lesson[\"targets\"], "
     "lesson[\"locale\"]) != \\\n",
     ["test_corrections.test_a_remapped_column_round_trips_into_a_lesson"]),
    ("D8", "a correction the runtime rejects is marked", "corrections.py",
     "    if res.status not in (\"imported\", \"imported_with_warnings\"):\n"
     "        return list(res.problems) or [res.status]\n",
     "    pass\n",
     ["test_corrections.test_a_correction_the_runtime_rejects_is_never_a_lesson"]),
    ("G1", "right-to-left text of a PDF is put back in reading order",
     "pdftable.py",
     "    return [(s, e, logical(t)) for s, e, t in cells]\n",
     "    return [(s, e, t) for s, e, t in cells]\n",
     ["test_files_layouts.test_pdf_in_every_script"]),
    ("G2", "a PDF note that runs on stays in the column it starts in",
     "pdftable.py",
     "        if bs - 1.0 <= s <= be:\n",
     "        if bs - 1.0 <= (s + e) / 2.0 <= be:\n",
     ["test_files_layouts.test_pdf_gives_back_the_table"]),
    ("G3", "an empty line of a PDF is an empty row", "pdftable.py",
     "            if gap >= BLANK_GAP * step:\n",
     "            if False:\n",
     ["test_files_layouts.test_pdf_in_every_script"]),
    ("G4", "a PDF table goes on over pages", "pdftable.py",
     "        if groups and _fits(groups[-1][\"bands\"], bands, size):\n",
     "        if False:\n",
     ["test_files_layouts.test_a_pdf_table_goes_on_over_pages"]),
    ("G5", "a scanned PDF needs review (no OCR)", "tulip.py",
     "    if name == \"ScannedPDF\":            # pdftable.py: no text, no OCR\n",
     "    if False:\n",
     ["test_files_layouts.test_a_scanned_pdf_needs_review"]),
    ("G6", "an ODS empty repeat is never expanded", "sheets.py",
     "                if value is None:\n                    pending += repeat\n"
     "                    continue\n",
     "                if value is None and False:\n                    pending "
     "+= repeat\n                    continue\n",
     ["test_files_layouts.test_ods_repeats_are_not_expanded"]),
    ("G7", "an .xls duration is a duration", "sheets.py",
     "                        v = datetime.timedelta(days=v)   # a duration\n",
     "                        v = datetime.time(0, 0)\n",
     ["test_files_layouts.test_xls_gives_the_xlsx_preview"]),
    ("G8", "a day range is one row per day", "tulipscript.py",
     "            for day in record[f]:\n",
     "            for day in record[f][:1]:\n",
     ["test_files_layouts.test_a_day_range_row_becomes_one_row_per_day"]),
    ("G9", "a day range may wrap round the week", "helpers.py",
     "            d = (d + 1) % 7\n",
     "            d = min(d + 1, 6)\n",
     ["test_files_layouts.test_several_days_in_one_cell_in_every_language"]),
    ("G10", "a new table starts at a header row, not at every blank row",
     "blocks.py",
     "        if _is_header(rows, i, b):\n            return i\n",
     "        return i\n",
     ["test_files_layouts.test_tables_on_one_sheet_are_found",
      "test_files_layouts.test_single_table_sheets_are_never_cut"]),
    ("G11", "the tables' rows and cells are the sheet's own", "tulip.py",
     "        return shifted(out, getattr(sheet, \"row_offset\", 0),\n"
     "                       getattr(sheet, \"column_offset\", 0))\n",
     "        return out\n",
     ["test_files_layouts.test_each_table_is_imported_on_its_own"]),
    ("G12", "a header repeated after a blank row is the same table",
     "blocks.py",
     "                _signature(rows[h]) == _signature(rows[last_table[2]]):\n",
     "                False:\n",
     ["test_files_layouts.test_tables_on_one_sheet_are_found"]),
    ("G13", "a header row is texts: a row of times or durations is data",
     "blocks.py",
     "    if any(not isinstance(v, str) or _numberish(v) or len(v) > 40\n",
     "    if any(_numberish(v) or len(str(v)) > 40\n",
     ["test_files_layouts.test_typed_rows_after_a_blank_row_are_data"]),
    ("G14", "each half of test_layouts goes round the ten languages",
     "gen/tasks.py",
     "    return choose_locale(rng, split, index // 2,\n",
     "    return choose_locale(rng, split, index,\n",
     ["test_files_layouts.test_the_new_splits_go_round_every_language"]),
    ("G15", ".xls or .ods by a hash of the task, not by the language's index",
     "gen/tasks.py",
     '    return "xls" if h % 2 == 0 else "ods"\n',
     '    return "xls" if index % 2 == 0 else "ods"\n',
     ["test_files_layouts.test_the_new_splits_go_round_every_language"]),
    ("G16", "a several-days sheet of test_layouts is drawn in its language",
     "gen/tasks.py",
     "                      locale=layout_locale(split, index, folders),\n",
     "",
     ["test_files_layouts.test_the_new_splits_go_round_every_language"]),
    ("G17", "every table of a multi-table sheet is drawn in its language",
     "gen/multitable.py",
     "                                locale=code)\n",
     "                                )\n",
     ["test_files_layouts.test_the_new_splits_go_round_every_language"]),
    ("G18", "the data checks find a language missing from a split",
     "gen/checks.py",
     "            if absent:\n",
     "            if False:\n",
     ["test_files_layouts.test_the_data_checks_find_a_missing_language"]),
    ("G19", "no bands because nothing was imported is not 'not scored'",
     "evaluate.py",
     "    if CONFIDENCE_FIT not in pairs:\n",
     "    if not pairs.get(CONFIDENCE_FIT):\n",
     ["test_confidence.test_a_model_that_imports_nothing_says_why_it_has_no_"
      "bands"]),
    ("G20", "REPORT.md never takes a Tulip 1.1 eval.json for Tulip 1's",
     "report.py",
     "                \"confidence\" not in ev:\n",
     "                True:\n",
     ["test_same_heldout_sets.test_the_report_compares_with_tulip_1"]),
    ("G21", "the comparison shows Tulip 1's unchanged handwritten set",
     "report.py",
     "    if new_h.get(\"sheets\") or old_h.get(\"sheets\"):\n",
     "    if False:\n",
     ["test_same_heldout_sets.test_the_report_compares_with_tulip_1"]),
]


TIME_LIMIT = 600      # seconds: a test that hangs is a test that fails
MEMORY_LIMIT = 8 << 30   # bytes of address space for one test run: a
#                          broken loop that grows without end stops at
#                          this, not at the machine's memory


def _limit_memory():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, ValueError, OSError):
        pass                              # Windows: no limit


def run_tests(tests):
    """-> (exit code, the lines of the output); a run that hangs past
    TIME_LIMIT gives the code "hang"."""
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / "run_all.py")] + tests,
            cwd=str(PROJECT), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", timeout=TIME_LIMIT,
            preexec_fn=_limit_memory if sys.platform != "win32" else None)
    except subprocess.TimeoutExpired:
        return "hang", ["  FAIL  (hung for %d s)" % TIME_LIMIT]
    lines = [x for x in proc.stdout.splitlines() if x.strip()]
    return proc.returncode, lines


def main(only):
    chosen = [g for g in GUARDS if not only or g[0] in only]
    results, bad = [], []
    for gid, what, name, text, broken, tests in chosen:
        path = PROJECT / name
        original = path.read_text(encoding="utf-8")
        if original.count(text) != 1:
            sys.exit("%s: the guarded text is not found exactly once in %s "
                     "(the code changed; update this entry)" % (gid, name))
        began = time.time()
        code, _ = run_tests(tests)
        if code != 0:
            sys.exit("%s: its tests fail on the unbroken code" % gid)
        try:
            path.write_text(original.replace(text, broken), encoding="utf-8")
            code, lines = run_tests(tests)
        finally:
            path.write_text(original, encoding="utf-8")
        failing = [x.split(None, 1)[1] for x in lines
                   if x.startswith("  FAIL")]
        if code != 0 and not failing:
            failing = ["crashed: " + (lines[-1] if lines else "")]
        ok = code != 0 and failing
        results.append((gid, what, name, failing, time.time() - began))
        print("%-4s %s  %s (%s): %s" % (
            gid, "caught " if ok else "NOT GUARDED", what, name,
            ", ".join(f.split(".")[-1] for f in failing) or
            "every test still passes"), flush=True)
        if not ok:
            bad.append(gid)
            print("      its tests said: %s" % " / ".join(lines[-3:]))
    print("\n%d guards broken one at a time: %d caught, %d not guarded"
          % (len(results), len(results) - len(bad), len(bad)))
    if bad:
        sys.exit("NOT GUARDED: " + ", ".join(bad))


if __name__ == "__main__":
    main(sys.argv[1:])
