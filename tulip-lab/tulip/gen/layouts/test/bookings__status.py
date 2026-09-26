"""
bookings.status: A status column mapped with lookup() (T12).
"""
from gen import b_bookings as K

ID = 'bookings.status'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, status=True)
