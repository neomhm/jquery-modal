"""
opening_hours.notes_column: A notes column ('sur rendez-vous').
"""
from gen import b_hours as O

ID = 'opening_hours.notes_column'
TARGET = 'opening_hours'


def build(ctx, plan):
    return O.opening_hours(ctx, plan, notes=True)
