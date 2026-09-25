"""
services.two_prices: Prices with and without tax (T2).
"""
from gen import b_services as S

ID = 'services.two_prices'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, force_two_prices=True)
