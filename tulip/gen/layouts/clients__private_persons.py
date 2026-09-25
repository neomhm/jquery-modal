"""
clients.private_persons: Private persons: the person's name is the client's name.
"""
from gen import b_people as P

ID = 'clients.private_persons'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, persons=True)
