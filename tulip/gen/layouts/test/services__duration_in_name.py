"""
services.duration_in_name: The duration inside the name cell ('Coupe - 30 min'), split with part().
"""
from gen import b_services as S

ID = 'services.duration_in_name'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, duration='name')
