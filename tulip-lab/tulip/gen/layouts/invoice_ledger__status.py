"""
invoice_ledger.status: A status column mapped with lookup() (T12).
"""
from gen import b_ledger as G

ID = 'invoice_ledger.status'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, status=True)
