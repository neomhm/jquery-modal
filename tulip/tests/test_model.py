"""The decoder: the key/value cache gives exactly the same scores as a
full pass, generation stops at [END], and a tiny model learns a toy
version of the real task (find the price column, write the program)."""
import os
import random
import tempfile
import time

import torch

import model as M
import tok
import tulipscript as ts

WORDS = {'price': ['Prix TTC', 'Price', 'Precio', 'Prezzo', 'Цена', '价格',
                   '価格', '가격', 'السعر', 'मूल्य'],
         'other': ['Réf', 'Stock', 'Famille', 'Notes', 'Code', 'Qty',
                   'Categoría', 'Колво', '备注', '분류']}


def toy(rng):
    """A preview with the price column at a random letter, and the
    program that reads it."""
    n = rng.randint(3, 6)
    price_at = rng.randrange(1, n)
    headers = [rng.choice(WORDS['other']) for _ in range(n)]
    headers[0] = 'Désignation'
    headers[price_at] = rng.choice(WORDS['price'])
    letters = ts.LETTERS[:n]
    head = ' | '.join('%s:%s' % (l, h) for l, h in zip(letters, headers))
    row = ' | '.join('%s:%s' % (l, rng.randint(1, 99)) for l in letters)
    preview = 'TARGETS products\nR1 %s\nR2 %s' % (head, row)
    program = ("target('products')\nheader(1)\n"
               "out.name = text(col('A'))\n"
               "out.price = amount(col('%s'))" % letters[price_at])
    return preview, ts.canonical(program)


def test_cache_matches_full_pass():
    torch.manual_seed(0)
    net = M.Tulip(M.Config(200, 64, 2, 4, 128, max_len=64)).eval()
    ids = torch.randint(4, 200, (1, 20))
    with torch.no_grad():
        full = net(ids)
        caches = [dict() for _ in net.blocks]
        first = net(ids[:, :12], caches, 0)
        steps = [net(ids[:, i:i + 1], caches, i) for i in range(12, 20)]
    step_logits = torch.cat([first] + steps, dim=1)
    assert torch.allclose(full, step_logits, atol=1e-4), \
        (full - step_logits).abs().max()


def test_loss_only_counts_the_program():
    torch.manual_seed(0)
    net = M.Tulip(M.Config(60, 32, 1, 2, 64, max_len=64)).eval()
    ids, lab = M.training_pair([5, 6, 7, 8], [9, 10, 11], 2, 3)
    ids, lab = torch.tensor([ids]), torch.tensor([lab])
    full = torch.nn.functional.cross_entropy(
        net(ids[:, :-1])[0], lab[0, 1:], ignore_index=M.IGNORE)
    assert torch.allclose(net.loss(ids, lab), full, atol=1e-5)
    assert lab[0].tolist() == [M.IGNORE] * 5 + [9, 10, 11, 3]


def test_generation_stops_at_end():
    torch.manual_seed(0)
    net = M.Tulip(M.Config(50, 32, 1, 2, 64, max_len=64)).eval()
    out = net.generate([5, 6, 7], end_id=3, max_new=10)
    assert len(out) == 1 and len(out[0]) <= 10 and 3 not in out[0]
    many = net.generate([5, 6, 7], end_id=3, max_new=10, n=4,
                        temperature=1.0,
                        generator=torch.Generator().manual_seed(1))
    assert len(many) == 4


def test_toy_task_is_learned():
    rng = random.Random(0)
    torch.manual_seed(0)
    train = [toy(rng) for _ in range(3000)]
    test = [toy(random.Random(1000 + i)) for i in range(60)]
    tk = tok.train_tokenizer((t for pair in train for t in pair), 600)
    c = M.Config(tk.get_vocab_size(), d_model=128, n_layer=3, n_head=4,
                 ffn_hidden=256, max_len=256)
    net = M.Tulip(c)
    steps = 1200
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3)
    # warm up over 100 steps, then decay linearly to 10% (while this test
    # was written, a smaller model trained without a schedule got only
    # about half of the programs right)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 100) * max(0.1, 1 - s / steps))
    pairs = [M.training_pair(tok.encode(tk, p), tok.encode(tk, q),
                             tok.PROGRAM, tok.END) for p, q in train]
    began = time.time()
    for step in range(steps):
        batch = rng.sample(pairs, 32)
        T = max(len(i) for i, _ in batch)
        ids = torch.zeros(len(batch), T, dtype=torch.long)
        lab = torch.full((len(batch), T), M.IGNORE, dtype=torch.long)
        for k, (i, l) in enumerate(batch):
            ids[k, :len(i)] = torch.tensor(i)
            lab[k, :len(l)] = torch.tensor(l)
        loss = net.loss(ids, lab)
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
    net.eval()
    right = 0
    for preview, program in test:
        prompt = tok.encode(tk, preview) + [tok.PROGRAM]
        out = net.generate(prompt, tok.END, max_new=80)[0]
        right += tok.decode(tk, out) == program
    print("    toy: %d/%d programs exactly right after %.0fs, loss %.3f"
          % (right, len(test), time.time() - began, loss.item()))
    assert right >= 0.95 * len(test)
    path = os.path.join(tempfile.gettempdir(), 'tulip-toy.pt')
    M.save(path, net, tk.to_str(), {'version': 'toy'})
    again, tj, meta = M.load(path)
    os.remove(path)
    assert meta['version'] == 'toy'
