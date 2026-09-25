"""
clients.address_one_cell: The whole address in one cell.
"""
from gen import b_people as P

ID = 'clients.address_one_cell'
TARGET = 'clients'


def build(ctx, plan):
    return P.clients(ctx, plan, address='one')
