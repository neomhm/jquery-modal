"""
bookings.title_rows: Title lines above the table (T5).
"""
from gen import b_bookings as K

ID = 'bookings.title_rows'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, title=True)
