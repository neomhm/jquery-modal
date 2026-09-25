"""
bookings.day_sections: Section rows carry the date: date(col('section')).
"""
from gen import b_bookings as K

ID = 'bookings.day_sections'
TARGET = 'bookings'


def build(ctx, plan):
    return K.bookings(ctx, plan, day_sections=True)
