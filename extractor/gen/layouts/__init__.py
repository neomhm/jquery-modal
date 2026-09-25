"""
The layouts. Importing this package registers every layout in
gen.layouts.common.REGISTRY, including the held-out test layouts in
gen/layouts/test/ (moved there by the hold-out draw).
"""
import importlib
import pathlib

from gen.layouts.common import REGISTRY

HERE = pathlib.Path(__file__).resolve().parent

MODULES = ["invoice", "quote", "brochure", "financials", "price_list",
           "staff_list", "contract", "letter", "terms", "other",
           "registration"]

for _name in MODULES:
    importlib.import_module("gen.layouts." + _name)

_test = HERE / "test"
if _test.exists():
    for _path in sorted(_test.glob("*.py")):
        if _path.stem != "__init__":
            importlib.import_module("gen.layouts.test." + _path.stem)
