"""
opening_hours.days_rows: One row per day: the day and its hours.
"""
from gen import b_hours as O

ID = 'opening_hours.days_rows'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, columns=False)
