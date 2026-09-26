"""
bookings.start_end: Start and end time columns.
"""
from gen import b_bookings as K

ID = 'bookings.start_end'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, end='column')
