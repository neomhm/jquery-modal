"""
services.from_prices: Some prices start with a 'from' word ('à partir de 35 €').
"""
from gen import b_services as S

ID = 'services.from_prices'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, from_prices=True)
