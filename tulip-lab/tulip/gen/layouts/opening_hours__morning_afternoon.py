"""
opening_hours.morning_afternoon: Morning and afternoon columns: hours(join(', ', ...)).
"""
from gen import b_hours as O

ID = 'opening_hours.morning_afternoon'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, morning_afternoon=True)
