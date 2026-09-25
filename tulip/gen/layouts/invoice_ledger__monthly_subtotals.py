"""
invoice_ledger.monthly_subtotals: Subtotal rows after each month (T4).
"""
from gen import b_ledger as G

ID = 'invoice_ledger.monthly_subtotals'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, monthly=True)
