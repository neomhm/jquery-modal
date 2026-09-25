"""
clients.address_split: Street, postcode and city in separate columns.
"""
from gen import b_people as P

ID = 'clients.address_split'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, address='split')
