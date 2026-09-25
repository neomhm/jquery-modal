"""
data.py - loads the language data (gen/data/...) once and keeps it.

Everything here is read-only after loading. The generator reaches every
word of every language through this module.
"""
import functools
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def locales():
    return read_json(DATA / "locales.json")


def locale(code):
    return locales()["locales"][code]


def language_settings():
    return locales()["language"]


@functools.lru_cache(maxsize=None)
def activities():
    """The 40 activities with their texts in every language. Uses the
    merged activities.json; before the merge (while languages are still
    being written) it combines the base file with the language parts."""
    merged = DATA / "activities.json"
    if merged.exists():
        return read_json(merged)["activities"]
    base = read_json(DATA / "activities_base.json")["activities"]
    out = []
    parts = {}
    for key in data_keys():
        path = DATA / key / "activities_part.json"
        if path.exists():
            parts[key] = read_json(path)
    for act in base:
        a = dict(act)
        for field in ("names", "name_words", "phrases", "services"):
            a[field] = {key: part[act["id"]][field]
                        for key, part in parts.items() if act["id"] in part}
        out.append(a)
    return out


def activity(act_id):
    for a in activities():
        if a["id"] == act_id:
            return a
    raise KeyError(act_id)


def data_keys():
    return ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi", "ja",
            "ko"]


@functools.lru_cache(maxsize=None)
def lexicon(key):
    return read_json(DATA / key / "lexicon.json")


@functools.lru_cache(maxsize=None)
def titles(key):
    return read_json(DATA / key / "titles.json")


@functools.lru_cache(maxsize=None)
def sentences(key):
    """All sentence templates of a language, the held-out ones included
    (sentences_test.json is merged in). Which ones a split may use is
    decided by holdout.py, never here."""
    sent = read_json(DATA / key / "sentences.json")
    test = DATA / key / "sentences_test.json"
    if test.exists():
        extra = read_json(test)
        sent = dict(sent)
        for cat, items in extra.items():
            if isinstance(items, list):
                sent[cat] = list(sent.get(cat, [])) + items
    return sent


@functools.lru_cache(maxsize=None)
def locale_list(code, name):
    """names.json / streets.json / cities.json of one locale."""
    path = DATA / code / (name + ".json")
    return read_json(path) if path.exists() else None


@functools.lru_cache(maxsize=None)
def concepts():
    return read_json(DATA / "concepts.json")


@functools.lru_cache(maxsize=None)
def registration_families():
    path = DATA / "registration.json"
    return read_json(path) if path.exists() else {}


@functools.lru_cache(maxsize=None)
def faker_decisions():
    path = DATA / "faker_decisions.json"
    return read_json(path) if path.exists() else {}
