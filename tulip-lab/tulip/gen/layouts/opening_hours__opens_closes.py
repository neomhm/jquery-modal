"""
opening_hours.opens_closes: Opening and closing times in two columns: hours(join('-', ...)).
"""
from gen import b_hours as O

ID = 'opening_hours.opens_closes'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, opens_closes=True)
