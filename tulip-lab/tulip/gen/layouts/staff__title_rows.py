"""
staff.title_rows: Title lines above the table (T5).
"""
from gen import b_people as P

ID = 'staff.title_rows'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, title=True)
