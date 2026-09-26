"""
clients.companies: Organisations with a contact person.
"""
from gen import b_people as P

ID = 'clients.companies'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, persons=False)
