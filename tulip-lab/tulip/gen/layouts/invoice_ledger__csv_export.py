"""
invoice_ledger.csv_export: An accounting export: all text, every column.
"""
from gen import b_ledger as G

ID = 'invoice_ledger.csv_export'
TARGET = 'invoice_ledger'
CSV_ONLY = True


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, export=True)
