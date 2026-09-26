"""
staff.contacts: E-mail and phone columns.
"""
from gen import b_people as P

ID = 'staff.contacts'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, contacts=True)
