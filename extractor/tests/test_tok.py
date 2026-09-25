"""Tokenizer: offsets are exact in all ten scripts, and every value can
be cut back out of its text from the BIO labels."""
import random

import torch

import decode
import tok

SAMPLES = [
    ("Boulangerie Martin SARL — 12 rue des Alpes, 01210 Ferney-Voltaire",
     ["Boulangerie Martin SARL", "12 rue des Alpes, 01210 Ferney-Voltaire"]),
    ("株式会社サクラ商事は1998年に設立されました。従業員数は約50名です。",
     ["株式会社サクラ商事", "1998年", "約50名"]),
    ("한빛전자는 2005년에 설립되었으며 직원 수는 25명입니다.",
     ["한빛전자", "2005년", "25명"]),
    ("购买方：北京华信科技有限公司 统一社会信用代码：91110108MA01ABCD2X",
     ["北京华信科技有限公司", "91110108MA01ABCD2X"]),
    ("شركة النور للتجارة ذ.م.م، الرياض — الإيرادات ١٬٢٤٠٬٠٠٠ ر.س",
     ["شركة النور للتجارة ذ.م.م", "١٬٢٤٠٬٠٠٠ ر.س"]),
    ("शर्मा ट्रेडर्स प्राइवेट लिमिटेड की स्थापना 1998 में हुई, कारोबार ₹12,40,000",
     ["शर्मा ट्रेडर्स प्राइवेट लिमिटेड", "1998", "₹12,40,000"]),
    ("ООО «Ромашка», выручка за 2023 год — 1,24 млн руб.",
     ["ООО «Ромашка»", "2023", "1,24 млн руб."]),
    ("資本金：１，０００万円　設立：令和元年５月",
     ["１，０００万円", "令和元年５月"]),
    ("Chiffre d'affaires 2023 : 1 240 000 € (2022 : 1,1 M€)",
     ["1 240 000 €", "1,1 M€"]),
    ("Fatturato: € 1.240.000,00 — Sede legale: Via Roma 12, 20121 Milano",
     ["€ 1.240.000,00", "Via Roma 12, 20121 Milano"]),
    ("Facturación anual: US$ 1.2 million — RFC: ABC120315XY9",
     ["US$ 1.2 million", "ABC120315XY9"]),
    ("Contact: info@sakura-shoji.co.jp / https://www.sakura-shoji.co.jp",
     ["info@sakura-shoji.co.jp", "https://www.sakura-shoji.co.jp"]),
]


def corpus():
    rng = random.Random(0)
    base = [t for t, _ in SAMPLES]
    for _ in range(400):
        t = rng.choice(base)
        words = t.split(" ")
        rng.shuffle(words)
        yield " ".join(words)
        yield t


def test_tokenizer():
    tk = tok.train_tokenizer(corpus(), vocab_size=1200)
    print("vocab", tk.get_vocab_size())
    labels = {"O": 0, "B-X": 1, "I-X": 2}
    bad = 0
    total = 0
    for text, values in SAMPLES:
        ids, offs = tok.encode(tk, text)
        # offsets are inside the original text and in order
        assert all(0 <= a <= b <= len(text) for a, b, _ in offs)
        spans = []
        for v in values:
            s = text.index(v)
            spans.append((s, s + len(v), "X"))
            total += 1
            if not tok.boundary_ok(offs, s, s + len(v)):
                bad += 1
                print("  boundary mismatch:", repr(v),
                      [text[a:b] for a, b, _ in offs if a < s + len(v) and b > s])
        lab = tok.token_labels(offs, spans, [], labels)
        # rebuild the values from the labels, exactly as inference will
        names = ["O", "B-X", "I-X"]
        probs = torch.nn.functional.one_hot(torch.tensor(lab), 3).float()
        got = [(s, e) for s, e, _, _ in
               decode.spans_from_labels(lab, probs, offs, names)]
        rebuilt = [text[a:b] for a, b in got]
        print("%-3d tokens | %s" % (len(ids), rebuilt))
        assert rebuilt == values, (rebuilt, values)
    print("boundary ok: %d/%d" % (total - bad, total))
    assert bad == 0
    # full-width digits really become plain digits for the model
    ids, _ = tok.encode(tk, "１２３")
    assert tk.decode(ids) == "123", tk.decode(ids)
    print("ALL TOKENIZER TESTS PASSED")


if __name__ == "__main__":
    test_tokenizer()
