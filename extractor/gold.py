"""
gold.py - read hand-labelled chunks (handwritten/ and real_eval/).

One JSON object per line:
    {"id": "hw-fr-03", "lang": "fr", "doc_type": "letter", "text": "...",
     "spans": [{"label": "S_NAME", "value": "Plomberie Dubois",
                "occurrence": 1}]}

`occurrence` says which appearance of `value` in `text` is meant
(1 = the first). The loader turns every span into character offsets and
STOPS with an error if a value cannot be found - a gold set with a typo
would silently score the model wrongly.

    py gold.py handwritten/fr.jsonl      check one file and show its spans
    py gold.py handwritten               check every file of a folder
"""
import json
import pathlib
import sys

import config

# sentence punctuation that a span must not end with (rule R2)
END_PUNCT = (".", ",", ";", ":", "،", "。", "、", "，", "；", "：")


class GoldError(ValueError):
    pass


def find_occurrence(text, value, occurrence):
    """Start of the n-th (1-based) appearance of value in text, or -1."""
    start = -1
    for _ in range(occurrence):
        start = text.find(value, start + 1)
        if start < 0:
            return -1
    return start


def convert(record, where="?"):
    """One gold record -> {"id", "lang", "doc_type", "text",
    "spans": [(start, end, label), ...]}. Raises GoldError."""
    for key in ("id", "lang", "doc_type", "text", "spans"):
        if key not in record:
            raise GoldError("%s: missing key %r" % (where, key))
    if record["lang"] not in config.LANGS:
        raise GoldError("%s: unknown lang %r" % (where, record["lang"]))
    if record["doc_type"] not in config.DOC_TYPES:
        raise GoldError("%s: unknown doc_type %r" % (where, record["doc_type"]))
    text = record["text"]
    spans = []
    for n, span in enumerate(record["spans"]):
        label = span.get("label")
        value = span.get("value")
        occurrence = span.get("occurrence", 1)
        if label not in config.TYPES:
            raise GoldError("%s span %d: unknown label %r" % (where, n, label))
        if not isinstance(value, str) or not value:
            raise GoldError("%s span %d: empty value" % (where, n))
        if value != value.strip():
            raise GoldError("%s span %d: value %r has outer whitespace"
                            % (where, n, value))
        start = find_occurrence(text, value, int(occurrence))
        if start < 0:
            raise GoldError("%s span %d: value %r (occurrence %s) not found "
                            "in the text" % (where, n, value, occurrence))
        spans.append((start, start + len(value), label))
    spans.sort()
    for (s1, e1, l1), (s2, e2, l2) in zip(spans, spans[1:]):
        if s2 < e1:
            raise GoldError("%s: spans overlap: %r and %r"
                            % (where, text[s1:e1], text[s2:e2]))
    return {"id": record["id"], "lang": record["lang"],
            "doc_type": record["doc_type"], "text": text, "spans": spans}


def warnings_for(item):
    """Soft checks: trailing punctuation (R2) and unlabelled repeats (R3)."""
    out = []
    text = item["text"]
    if not 200 <= len(text) <= 1500:
        out.append("%s: text is %d characters (200-1500 expected)"
                   % (item["id"], len(text)))
    labelled = {(s, e) for s, e, _ in item["spans"]}
    for s, e, label in item["spans"]:
        value = text[s:e]
        if value.endswith(END_PUNCT):
            out.append("%s: %s value ends with punctuation: %r (fine only "
                       "for abbreviations like 'Ltd.' or 'S.A.')"
                       % (item["id"], label, value))
        # every occurrence of the value should be labelled (rule R3)
        pos = text.find(value)
        while pos >= 0:
            if (pos, pos + len(value)) not in labelled and not any(
                    a <= pos < b for a, b in labelled):
                out.append("%s: %r appears again at %d unlabelled (R3)"
                           % (item["id"], value, pos))
                break
            pos = text.find(value, pos + 1)
    return out


def load_file(path):
    items = []
    path = pathlib.Path(path)
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            where = "%s line %d" % (path.name, number)
            try:
                record = json.loads(line)
            except json.JSONDecodeError as problem:
                raise GoldError("%s: not valid JSON: %s" % (where, problem))
            items.append(convert(record, where))
    return items


def load_folder(folder):
    """Every *.jsonl file of a folder (sorted), or [] if there is none."""
    folder = pathlib.Path(folder)
    items = []
    for path in sorted(folder.glob("*.jsonl")):
        items.extend(load_file(path))
    return items


def main(args):
    target = pathlib.Path(args[0]) if args else config.HERE / "handwritten"
    paths = sorted(target.glob("*.jsonl")) if target.is_dir() else [target]
    total = 0
    problems = 0
    for path in paths:
        try:
            items = load_file(path)
        except GoldError as problem:
            print("ERROR", problem)
            problems += 1
            continue
        ids = [i["id"] for i in items]
        if len(set(ids)) != len(ids):
            print("ERROR %s: duplicate ids" % path.name)
            problems += 1
        for item in items:
            total += 1
            print("%-10s %-12s %5d chars %3d spans" % (
                item["id"], item["doc_type"], len(item["text"]),
                len(item["spans"])))
            for s, e, label in item["spans"]:
                print("      %-13s %r" % (label, item["text"][s:e]))
            for w in warnings_for(item):
                print("  warning:", w)
    print("\n%d chunks checked, %d files with errors" % (total, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
