"""
invoice_ledger.credit_notes: Credit notes with negative amounts.
"""
from gen import b_ledger as G

ID = 'invoice_ledger.credit_notes'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, credit_notes=True)
