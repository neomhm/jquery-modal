"""
opening_hours.day_ranges: Several days in one cell ("Lun–Ven", "月～金"):
weekdays() gives one row per day (Tulip 1.1).
"""
from gen import b_hours as O

ID = 'opening_hours.day_ranges'
TARGET = 'opening_hours'
SINCE = '1.2.0'      # never drawn for the splits Tulip 1 was scored on
WEIGHT = 1.5


def build(ctx, plan):
    return O.opening_hours_ranges(ctx, plan)
