"""
invoice_ledger.title_rows: Title lines above the table (T5).
"""
from gen import b_ledger as G

ID = 'invoice_ledger.title_rows'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, title=True)
