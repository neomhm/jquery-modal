"""
services.csv_export: An export from a booking tool: all text, more columns.
"""
from gen import b_services as S

ID = 'services.csv_export'
TARGET = 'services'
CSV_ONLY = True


def build(ctx, plan):
    return S.services(ctx, plan, export=True)
