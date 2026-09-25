"""
clients.registration: A VAT / company registration column.
"""
from gen import b_people as P

ID = 'clients.registration'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, persons=False, registration=True)
