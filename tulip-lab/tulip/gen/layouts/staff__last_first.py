"""
staff.last_first: Last name column first on the sheet (T10).
"""
from gen import b_people as P

ID = 'staff.last_first'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, split_names=True, last_first=True)
