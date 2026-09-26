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
]


def run_tests(tests):
    """-> (exit code, the last lines of the output)."""
    proc = subprocess.run(
        [sys.executable, str(HERE / "run_all.py")] + tests, cwd=str(PROJECT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
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
        failing = [x.split()[1] for x in lines if x.startswith("  FAIL")]
        ok = code != 0 and failing
        results.append((gid, what, name, failing, time.time() - began))
        print("%-4s %s  %s (%s): %s" % (
            gid, "caught " if ok else "NOT GUARDED", what, name,
            ", ".join(f.split(".")[1] for f in failing) or "every test "
            "still passes"), flush=True)
        if not ok:
            bad.append(gid)
    print("\n%d guards broken one at a time: %d caught, %d not guarded"
          % (len(results), len(results) - len(bad), len(bad)))
    if bad:
        sys.exit("NOT GUARDED: " + ", ".join(bad))


if __name__ == "__main__":
    main(sys.argv[1:])
