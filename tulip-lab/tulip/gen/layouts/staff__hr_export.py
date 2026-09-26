"""
staff.hr_export: An HR export: all text, every column.
"""
from gen import b_people as P

ID = 'staff.hr_export'
TARGET = 'staff'
CSV_ONLY = True


def build(ctx, plan):
    return P.staff(ctx, plan, export=True)
