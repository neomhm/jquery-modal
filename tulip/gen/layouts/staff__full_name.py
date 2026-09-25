"""
staff.full_name: The full name in one cell, kept as written.
"""
from gen import b_people as P

ID = 'staff.full_name'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, split_names=False)
