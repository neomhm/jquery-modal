"""
bookings.staff_price: Who does it and the price.
"""
from gen import b_bookings as K

ID = 'bookings.staff_price'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, staff_price=True)
