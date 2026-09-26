"""
refusals.matrix: A matrix: people x weekdays with shift codes.
"""
from gen import b_refusals as R

ID = 'refusals.matrix'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.matrix(ctx, plan)
