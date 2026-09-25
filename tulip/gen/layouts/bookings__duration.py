"""
bookings.duration: A duration instead of an end time.
"""
from gen import b_bookings as K

ID = 'bookings.duration'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, end='duration')
