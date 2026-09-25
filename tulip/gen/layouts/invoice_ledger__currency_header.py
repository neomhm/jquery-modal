"""
invoice_ledger.currency_header: The currency only in the header or number format (T13).
"""
from gen import b_ledger as G

ID = 'invoice_ledger.currency_header'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, currency_header=True)
