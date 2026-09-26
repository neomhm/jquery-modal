"""
bookings.datetime_cell: Date and time in one cell: date(col) and time(col) (T11).
"""
from gen import b_bookings as K

ID = 'bookings.datetime_cell'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, datetime_cell=True)
