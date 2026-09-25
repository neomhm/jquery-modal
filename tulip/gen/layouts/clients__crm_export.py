"""
clients.crm_export: A CRM export with many columns.
"""
from gen import b_people as P

ID = 'clients.crm_export'
TARGET = 'clients'
CSV_ONLY = True


def build(ctx, plan):
    return P.clients(ctx, plan, crm=True)
