"""
gen/data.py - reads the generator's data files (gen/data/...) once and
keeps them in memory.

    locale(code)            one locale of locales.json (Appendix F)
    locale_list(code, name) gen/data/<locale>/<name>.json (names, streets,
                            cities)
    headers(folder)         column headers of a language folder, WITHOUT
                            the test-only (T) variants
    headers_test(folder)    the T variants (gen/data/<folder>/
                            headers_test.json) - used only to make
                            test_heldout, never read by a person
    values(folder)          words inside cells (values.json)
    business(folder)        company-name words (business.json)
    activities()            the 40 activities with every language's items
"""
import functools
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
FOLDERS = ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi", "ja",
           "ko"]
# the locale whose prices a folder's item prices describe (its "usd"
# ranges are that country's prices converted to dollars)
MAIN_LOCALE = {"ar": "ar-SA", "zh": "zh-CN", "zh-Hant": "zh-TW",
               "en": "en-US", "fr": "fr-FR", "ru": "ru-RU", "es": "es-ES",
               "it": "it-IT", "hi": "hi-IN", "ja": "ja-JP", "ko": "ko-KR"}


def read_json(path):
    path = pathlib.Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def locales():
    return read_json(DATA / "locales.json")["locales"]


def locale(code):
    loc = dict(locales()[code])
    loc["code"] = code
    return loc


@functools.lru_cache(maxsize=None)
def locale_list(code, name):
    return read_json(DATA / code / ("%s.json" % name))


@functools.lru_cache(maxsize=None)
def headers(folder):
    return read_json(DATA / folder / "headers.json") or {}


@functools.lru_cache(maxsize=None)
def headers_test(folder):
    return read_json(DATA / folder / "headers_test.json") or {}


@functools.lru_cache(maxsize=None)
def values(folder):
    return read_json(DATA / folder / "values.json") or {}


@functools.lru_cache(maxsize=None)
def business(folder):
    return read_json(DATA / folder / "business.json") or {}


@functools.lru_cache(maxsize=None)
def activities():
    """[{id, n, en, customers, hours, holdout, words: {folder: {...}}}]:
    the base list with each language folder's items attached."""
    base = read_json(DATA / "activities_base.json")["activities"]
    out = []
    for a in base:
        a = dict(a)
        a["words"] = {}
        for folder in FOLDERS:
            part = read_json(DATA / folder / "activities.json") or {}
            if a["id"] in part:
                a["words"][folder] = part[a["id"]]
        out.append(a)
    return out


@functools.lru_cache(maxsize=None)
def activity(act_id):
    for a in activities():
        if a["id"] == act_id:
            return a
    raise KeyError(act_id)


def folders_ready():
    """The language folders whose three files exist (while data is being
    written, the generator can run on the finished ones)."""
    return [f for f in FOLDERS
            if all((DATA / f / name).exists() for name in
                   ("headers.json", "values.json", "activities.json"))]
