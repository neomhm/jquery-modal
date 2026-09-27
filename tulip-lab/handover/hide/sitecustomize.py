"""Rehearsal only: makes this Python look like the /train venv, which has
no openpyxl, et_xmlfile, phonenumbers, hijridate, faker, xlrd, xlwt or
PDF library. Their system copies are hidden; a copy from vendor/ (a
wheel on sys.path) still imports."""
import importlib.machinery
import sys

HIDDEN = {"openpyxl", "et_xmlfile", "phonenumbers", "hijridate", "faker",
          "xlrd", "xlwt", "pypdf", "PyPDF2", "pdfplumber", "fitz",
          "reportlab", "pdfminer", "cryptography", "Crypto", "cffi"}
SYSTEM = ("dist-packages", "site-packages")


class HideSystemCopies:
    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if "." in name or name not in HIDDEN:
            return None
        allowed = [p for p in sys.path if not p.rstrip("/").endswith(SYSTEM)]
        spec = importlib.machinery.PathFinder.find_spec(name, allowed)
        if spec is None:
            raise ModuleNotFoundError(
                "No module named %r (not in the /train venv)" % name,
                name=name)
        return spec


sys.meta_path.insert(0, HideSystemCopies)
