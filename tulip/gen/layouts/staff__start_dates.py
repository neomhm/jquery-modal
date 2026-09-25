"""
staff.start_dates: Start dates, typed or as text.
"""
from gen import b_people as P

ID = 'staff.start_dates'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, start_dates=True)
