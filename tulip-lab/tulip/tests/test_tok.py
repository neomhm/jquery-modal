"""Tokenizer: a program comes back out of encode/decode exactly (in NFKC
form), in every script the lookup keys may use."""
import unicodedata

import tok

PROGRAMS = [
    "target('invoice_ledger')\nheader(2)\nkeep(not_total('A'))\n"
    "out.number = text(col('A'))\nout.date = date(col('B'))\n"
    "out.total = amount(col('D'))\n"
    "out.status = lookup(col('E'), {'Payée': 'paid', 'Impayée': 'unpaid'})",
    "target('bookings')\nheader(1)\nout.date = date(col('A'))\n"
    "out.start_time = time(col('A'))\n"
    "out.status = lookup(col('F'), {'予約済み': 'confirmed', "
    "'キャンセル': 'cancelled', '확정': 'confirmed', 'ملغى': 'cancelled'})",
    "target('staff')\nheader(1)\n"
    "out.name = text(join(' ', col('B'), col('A')))\n"
    "out.role = text(part(col('C'), ' – ', 0))",
    "refuse('missing_required:price')",
    "target('products')\nheader(1)\nkeep(not_value('A', 'Ｔｏｔａｌ'))\n"
    "out.name = text(col('B'))\nout.price = amount(col('C'))",
]


def test_round_trip():
    tk = tok.train_tokenizer(PROGRAMS * 20, 400)
    assert tk.token_to_id('[PROGRAM]') == tok.PROGRAM
    for text in PROGRAMS:
        ids = tok.encode(tk, text)
        back = tok.decode(tk, ids + [tok.END, 17, 18])
        assert back == unicodedata.normalize('NFKC', text), (back, text)
