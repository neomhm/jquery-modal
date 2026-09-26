"""
Run every test in this folder:

    py tests/run_all.py

Each test_*.py file holds functions whose names start with test_.
They are plain Python (no pytest needed). A test fails by raising.
"""
import importlib
import pathlib
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))     # the project folder
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    failed, passed = [], 0
    for path in sorted(HERE.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            func = getattr(module, name)
            if not callable(func):
                continue
            began = time.time()
            try:
                func()
                passed += 1
                print("  ok    %s.%s  (%.1fs)" % (path.stem, name,
                                                  time.time() - began))
            except Exception:
                failed.append("%s.%s" % (path.stem, name))
                print("  FAIL  %s.%s" % (path.stem, name))
                traceback.print_exc()
    print("\n%d passed, %d failed" % (passed, len(failed)))
    if failed:
        sys.exit("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
