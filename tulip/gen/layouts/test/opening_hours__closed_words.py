"""
opening_hours.closed_words: Several closed days, written as words.
"""
from gen import b_hours as O

ID = 'opening_hours.closed_words'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, many_closed=True)
