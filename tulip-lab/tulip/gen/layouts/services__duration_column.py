"""
services.duration_column: The duration in its own column.
"""
from gen import b_services as S

ID = 'services.duration_column'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, duration='column')
