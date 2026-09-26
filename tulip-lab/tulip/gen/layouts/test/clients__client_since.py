"""
clients.client_since: The date the client arrived.
"""
from gen import b_people as P

ID = 'clients.client_since'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, since=True)
