"""
opening_hours.title_rows: Title lines above the table (T5).
"""
from gen import b_hours as O

ID = 'opening_hours.title_rows'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, title=True)
