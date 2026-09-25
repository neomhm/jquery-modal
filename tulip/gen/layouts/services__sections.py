"""
services.sections: Section rows name the category of the services below them.
"""
from gen import b_services as S

ID = 'services.sections'
TARGET = 'services'


def build(ctx, plan):
    return S.services(ctx, plan, sections=True)
