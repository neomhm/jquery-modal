"""
services.title_rows: Title lines and a blank row above the header (T5).
"""
from gen import b_services as S

ID = 'services.title_rows'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, title=True)
