"""
invoice_ledger.due_paid: Due and paid dates.
"""
from gen import b_ledger as G

ID = 'invoice_ledger.due_paid'
TARGET = 'invoice_ledger'


def build(ctx, plan):
    return G.invoice_ledger(ctx, plan, due_paid=True)
