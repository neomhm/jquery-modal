"""
services.simple: A plain list: service, price, maybe a duration.
"""
from gen import b_services as S

ID = 'services.simple'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan)
