"""
clients.first_last: Private persons with first and last name columns (T10).
"""
from gen import b_people as P

ID = 'clients.first_last'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, split_names=True)
