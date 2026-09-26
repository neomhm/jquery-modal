"""
clients.title_rows: Title lines above the table (T5).
"""
from gen import b_people as P

ID = 'clients.title_rows'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, title=True)
