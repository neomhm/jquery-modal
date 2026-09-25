"""
staff.first_last: First and last name columns, joined in the locale's order (T10).
"""
from gen import b_people as P

ID = 'staff.first_last'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, split_names=True)
