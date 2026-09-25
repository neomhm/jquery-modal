"""End-to-end sanity check of the reference pieces on a toy task:
tokenizer -> labels -> encoder -> Viterbi -> exact spans.
A tiny model must learn to pull a revenue figure and a company name
while ignoring an invoice total that looks just like the revenue."""
import os
import random
import tempfile
import time

import torch
import torch.nn.functional as F

import decode
import model as M
import tok

TYPES = ["S_NAME", "REVENUE", "DOC_TOTAL"]
NAMES = decode.label_names(TYPES)
LID = {n: i for i, n in enumerate(NAMES)}

FIRST = ["Martin", "Sakura", "Hanbit", "Nour", "Sharma", "Romashka",
         "Rossi", "García", "Dupont", "Li", "Kim", "Tanaka"]
KIND = ["Boulangerie", "Traders", "Shoji", "Electronics", "Bakery",
        "Consulting", "Logistics", "Studio"]
FORM = ["SARL", "Pvt Ltd", "株式会社", "LLC", "S.r.l.", "ООО", "GmbH"]
FILL = ("the a of and for with our new team service client order "
        "delivery quality since many years local best offer").split()


def amount(rng):
    n = rng.randint(1000, 9999999)
    style = rng.random()
    if style < 0.33:
        return "{:,}".format(n) + " €"
    if style < 0.66:
        return "$" + "{:,}".format(n)
    return "{:,}".format(n).replace(",", " ") + " EUR"


def example(rng):
    parts, spans = [], []

    def add(text, label=None):
        start = sum(len(p) for p in parts)
        parts.append(text)
        if label:
            spans.append((start, start + len(text), label))

    name = "%s %s %s" % (rng.choice(FIRST), rng.choice(KIND), rng.choice(FORM))
    order = rng.sample(["name", "rev", "tot", "fill", "fill"], 5)
    for part in order:
        if part == "name":
            add(rng.choice(["", "From: ", "Issuer: "]))
            add(name, "S_NAME")
            add(". ")
        elif part == "rev":
            add(rng.choice(["Annual revenue: ", "Turnover 2023: ",
                            "Revenue was "]))
            add(amount(rng), "REVENUE")
            add(". ")
        elif part == "tot":
            add(rng.choice(["Invoice total: ", "Total due: ",
                            "Amount payable "]))
            add(amount(rng), "DOC_TOTAL")
            add(". ")
        else:
            add(" ".join(rng.choice(FILL) for _ in range(rng.randint(2, 9))))
            add(". ")
    return "".join(parts), spans


def batchify(tk, examples):
    ids_list, lab_list = [], []
    for text, spans in examples:
        ids, offs = tok.encode(tk, text)
        ids_list.append(ids)
        lab_list.append(tok.token_labels(offs, spans, [], LID))
    T = max(len(x) for x in ids_list)
    ids = torch.zeros(len(ids_list), T, dtype=torch.long)
    lab = torch.full((len(ids_list), T), -100, dtype=torch.long)
    for i, (a, b) in enumerate(zip(ids_list, lab_list)):
        ids[i, :len(a)] = torch.tensor(a)
        lab[i, :len(b)] = torch.tensor(b)
    return ids, ids != 0, lab


def test_toy_end_to_end():
    torch.manual_seed(0)
    rng = random.Random(0)
    train = [example(rng) for _ in range(3000)]
    test = [example(random.Random(99)) for _ in range(1)] + \
           [example(rng) for _ in range(200)]
    tk = tok.train_tokenizer((t for t, _ in train), vocab_size=800)

    # parameter counts of the real presets
    for name, c in [("smoke", M.Config(8000, 128, 2, 2, 352)),
                    ("pilot", M.Config(32000, 256, 4, 4, 704)),
                    ("full", M.Config(48000, 384, 8, 6, 1024))]:
        total, core = M.Extractor(c).count()
        print("%-6s %6.1fM parameters (%.1fM outside the embedding table)"
              % (name, total / 1e6, core / 1e6))

    c = M.Config(tk.get_vocab_size(), d_model=128, n_layer=2, n_head=2,
                 ffn_hidden=352, max_len=256, dropout=0.0,
                 n_labels=len(NAMES))
    net = M.Extractor(c)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=0.01)

    # one MLM step, to prove the pretraining path runs
    ids, keep, _ = batchify(tk, train[:16])
    new, pos, tgt = M.mask_for_mlm(ids, keep, c.vocab_size)
    loss = F.cross_entropy(net.mlm_logits(net(new, keep), pos), tgt)
    loss.backward()
    opt.zero_grad()
    print("mlm loss at start %.2f (ln vocab = %.2f)"
          % (loss.item(), torch.log(torch.tensor(float(c.vocab_size)))))

    began = time.time()
    for step in range(400):
        batch = rng.sample(train, 32)
        ids, keep, lab = batchify(tk, batch)
        h = net(ids, keep)
        logits = net.token_logits(h)
        loss = F.cross_entropy(logits.view(-1, len(NAMES)), lab.view(-1),
                               ignore_index=-100)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if step % 100 == 0:
            print("step %3d  loss %.3f" % (step, loss.item()))
    print("trained in %.0fs" % (time.time() - began))

    net.eval()
    allowed, start_ok = decode.allowed_transitions(NAMES)
    hit = pred = gold = 0
    with torch.no_grad():
        for text, spans in test:
            ids, offs = tok.encode(tk, text)
            x = torch.tensor([ids])
            h = net(x, x != 0)
            logp = F.log_softmax(net.token_logits(h)[0], -1)
            path = decode.viterbi(logp, allowed, start_ok)
            got = {(s, e, k) for s, e, k, _ in
                   decode.spans_from_labels(path, logp.exp(), offs, NAMES)}
            want = set(spans)
            hit += len(got & want)
            pred += len(got)
            gold += len(want)
    p, r = hit / max(pred, 1), hit / max(gold, 1)
    f1 = 2 * p * r / max(p + r, 1e-9)
    print("exact-span precision %.3f recall %.3f F1 %.3f" % (p, r, f1))
    assert f1 > 0.9, "the toy task should be learned"

    # save / load round trip
    path = os.path.join(tempfile.gettempdir(), "extractor-toy.pt")
    M.save(path, net, tk.to_str(), {"labels": NAMES})
    net2, tj, meta = M.load(path)
    os.remove(path)
    assert meta["labels"] == NAMES
    print("ALL MODEL TESTS PASSED")


if __name__ == "__main__":
    test_toy_end_to_end()
