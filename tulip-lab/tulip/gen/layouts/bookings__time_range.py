"""
bookings.time_range: '09:00-10:00' in one cell, split with part().
"""
from gen import b_bookings as K

ID = 'bookings.time_range'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, datetime_cell=False, end='range')
