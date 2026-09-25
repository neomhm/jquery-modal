"""
services.staff_column: A column names the person who does the service.
"""
from gen import b_services as S

ID = 'services.staff_column'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, staff=True)
