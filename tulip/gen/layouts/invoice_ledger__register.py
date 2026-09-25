"""
invoice_ledger.register: Number, date, client, total.
"""
from gen import b_ledger as G

ID = 'invoice_ledger.register'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan)
