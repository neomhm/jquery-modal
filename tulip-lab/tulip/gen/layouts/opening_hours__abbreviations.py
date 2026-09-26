"""
opening_hours.abbreviations: Weekday abbreviations ('lun.', 'Mon').
"""
from gen import b_hours as O

ID = 'opening_hours.abbreviations'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, short=True)
