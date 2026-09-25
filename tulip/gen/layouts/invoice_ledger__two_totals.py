"""
invoice_ledger.two_totals: Totals without tax, tax, with tax: total is the one with tax.
"""
from gen import b_ledger as G

ID = 'invoice_ledger.two_totals'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, two_totals=True)
