"""
opening_hours.days_columns: Days as columns, one row of hours: unpivot() (T8).
"""
from gen import b_hours as O

ID = 'opening_hours.days_columns'
TARGET = 'opening_hours'
WEIGHT = 3.0


def build(ctx, plan):
    return O.opening_hours(ctx, plan, columns=True)
