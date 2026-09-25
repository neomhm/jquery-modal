"""Property tests: the annotated twins must give EXACTLY the same text
as ingest.py, and every kept span must still read the same value."""
import random

import chunker
import ingest            # the real file, for the equality check

WORDS = ("facture client total chiffre affaires 2023 SARL Martin rue "
         "des Alpes 01210 Ferney 1 240 000 € salariés depuis 1998 "
         "株式会社 サクラ 売上高 1億2,400万円 매출액 12억 원 ООО «Ромашка» "
         "выручка شركة النور الإيرادات राजस्व लाख").split()


def random_line(rng):
    kind = rng.random()
    if kind < 0.08:
        return ""
    if kind < 0.14:
        return rng.choice(["FACTURE", "ABOUT US", "# Services",
                           "CHIFFRES CLES", "  INVOICE 2024  "])
    n = rng.randint(1, 40)
    line = " ".join(rng.choice(WORDS) for _ in range(n))
    if rng.random() < 0.4:
        line += rng.choice([".", "!", "?", ":", ";"])
    if rng.random() < 0.1:
        line = "   " + line + "  "
    return line


def random_doc(rng):
    lines = [random_line(rng) for _ in range(rng.randint(1, 120))]
    text = "\n".join(lines)
    spans = []
    for _ in range(rng.randint(0, 25)):
        if len(text) < 3:
            break
        s = rng.randrange(0, len(text) - 1)
        e = min(len(text), s + rng.randint(1, 60))
        spans.append((s, e, rng.choice(["S_NAME", "REVENUE", "C_NAME"])))
    return text, spans


def test_split_text(rounds=3000):
    rng = random.Random(1)
    for _ in range(rounds):
        text, spans = random_doc(rng)
        want = ingest.split_text(text)
        got = chunker.split_text_annotated(text, spans)
        assert [c for c, _, _ in got] == want
        for chunk, kept, cut in got:
            for s, e, label in kept:
                # the same characters as somewhere in the source
                assert chunk[s:e] in text
                assert 0 <= s < e <= len(chunk)
            for s, e in cut:
                assert 0 <= s < e <= len(chunk)
        # a span that sits inside one line is never cut
        for s, e, label in spans:
            if "\n" not in text[s:e] and text[s:e].strip():
                value = text[s:e]
                hits = [chunk[a:b] for chunk, kept, _ in got
                        for a, b, lab in kept if lab == label]
                # it is kept unless it was whitespace trimmed away
                if value.strip() == value:
                    assert value in hits or all(
                        value not in c for c, _, _ in got)
    print("split_text: %d random documents identical" % rounds)


def random_table(rng):
    rows = []
    for r in range(rng.randint(1, 12)):
        row = []
        for c in range(rng.randint(1, 6)):
            x = rng.random()
            if x < 0.15:
                row.append(None)
            elif x < 0.25:
                row.append("   ")
            elif x < 0.3:
                row.append("")
            else:
                cell = " ".join(rng.choice(WORDS)
                                for _ in range(rng.randint(1, 4)))
                if rng.random() < 0.2:
                    cell = "  " + cell + " "
                row.append(cell)
        rows.append(row)
    spans = {}
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell and cell.strip() and rng.random() < 0.3:
                raw = cell
                lead = len(raw) - len(raw.lstrip())
                inner = raw.strip()
                s = lead + rng.randrange(0, len(inner))
                e = rng.randint(s + 1, lead + len(inner))
                spans[(r, c)] = [(s, e, rng.choice(["REVENUE", "S_NAME"]))]
    return rows, spans


def test_tables(rounds=3000):
    rng = random.Random(2)
    for _ in range(rounds):
        rows, spans = random_table(rng)
        want = ingest.table_to_text(rows)
        got, got_spans = chunker.table_to_text_annotated(rows, spans)
        assert got == want, (got, want)
        if got is None:
            continue
        values = {cells[c][s:e] for (r, c), lst in spans.items()
                  for s, e, _ in lst for cells in [rows[r]]}
        for s, e, label in got_spans:
            assert got[s:e] in values
    print("table_to_text: %d random tables identical" % rounds)


def test_header_pairing():
    rows = [["Poste", "2023", "2022"],
            ["Chiffre d'affaires", "1 240 000", "1 100 000"],
            ["Résultat net", "85 000", "70 000"]]
    spans = {(0, 1): [(0, 4, "REVENUE_YEAR")],
             (0, 2): [(0, 4, "REVENUE_YEAR")],
             (1, 1): [(0, 9, "REVENUE")],
             (1, 2): [(0, 9, "REVENUE")]}
    text, got = chunker.table_to_text_annotated(rows, spans)
    assert text == ingest.table_to_text(rows)
    seen = [(text[s:e], lab) for s, e, lab in got]
    assert seen == [("2023", "REVENUE_YEAR"), ("1 240 000", "REVENUE"),
                    ("2022", "REVENUE_YEAR"), ("1 100 000", "REVENUE")], seen
    # the profit row keeps its years as O
    line3 = text.split("\n")[2]
    assert all(s < text.index(line3) for s, _, _ in got)
    print("header pairing: ok ->", text.replace("\n", " / "))


def test_sheets(rounds=500):
    rng = random.Random(3)
    for _ in range(rounds):
        rows, spans = random_table(rng)
        rows = rows + [["a%d" % i, "b"] for i in range(rng.randint(0, 60))]
        # what ingest.read_xlsx would make from these rows
        plain = [[("" if c is None else str(c)) for c in row]
                 for row in rows]
        plain = [r for r in plain if any(c.strip() for c in r)]
        want = []
        if plain:
            header, body = plain[0], plain[1:]
            for start in range(0, max(len(body), 1), 25):
                made = ingest.table_to_text([header] + body[start:start + 25])
                if made:
                    want.append("[Sheet1]\n" + made)
        got = chunker.sheet_chunks_annotated("Sheet1", rows, spans)
        assert [t for t, _ in got] == want
    print("sheets: %d random sheets identical" % rounds)


def test_csv(rounds=300):
    """Write real .csv files and compare with ingest.read_csv itself."""
    import csv
    import os
    import tempfile
    rng = random.Random(5)
    for _ in range(rounds):
        rows, spans = random_table(rng)
        rows = [[("" if c is None else c) for c in row] for row in rows]
        rows += [["x%d" % i, " "] for i in range(rng.randint(0, 60))]
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
        want = [text for _, _, text in ingest.read_csv(path)]
        with open(path, encoding="utf-8", newline="") as f:
            back = list(csv.reader(f))
        os.remove(path)
        got = [text for text, _ in chunker.csv_chunks_annotated(back, {})]
        assert got == want
    print("csv: %d real csv files identical" % rounds)


if __name__ == "__main__":
    test_split_text()
    test_tables()
    test_header_pairing()
    test_sheets()
    test_csv()
    print("ALL CHUNKER TESTS PASSED")
