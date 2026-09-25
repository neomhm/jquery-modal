"""
bookings.date_time: Date and time columns.
"""
from gen import b_bookings as K

ID = 'bookings.date_time'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, end='none')
