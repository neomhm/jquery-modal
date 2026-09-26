"""
Run every test in this folder:

    py tests/run_all.py
    py tests/run_all.py test_contract              one file
    py tests/run_all.py test_contract.test_nothing_is_lost   one test

Each test_*.py file holds functions whose names start with test_.
They are plain Python (no pytest needed). A test fails by raising, and
is skipped by raising unittest.SkipTest (with the reason).
"""
import importlib
import pathlib
import sys
import time
import traceback
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))     # the project folder
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def wanted(stem, name, only):
    return not only or stem in only or "%s.%s" % (stem, name) in only


def main(only=()):
    failed, passed, skipped = [], 0, []
    for path in sorted(HERE.glob("test_*.py")):
        if only and not any(o.split(".")[0] == path.stem for o in only):
            continue
        module = importlib.import_module(path.stem)
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            func = getattr(module, name)
            if not callable(func) or not wanted(path.stem, name, only):
                continue
            began = time.time()
            try:
                func()
                passed += 1
                print("  ok    %s.%s  (%.1fs)" % (path.stem, name,
                                                  time.time() - began))
            except unittest.SkipTest as e:
                skipped.append("%s.%s" % (path.stem, name))
                print("  skip  %s.%s  (%s)" % (path.stem, name, e))
            except Exception:
                failed.append("%s.%s" % (path.stem, name))
                print("  FAIL  %s.%s" % (path.stem, name))
                traceback.print_exc()
    print("\n%d passed, %d skipped, %d failed" % (passed, len(skipped),
                                                 len(failed)))
    if failed:
        sys.exit("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main(sys.argv[1:])
