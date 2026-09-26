"""
refusals.summary: Label / value pairs of a dashboard.
"""
from gen import b_refusals as R

ID = 'refusals.summary'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.summary(ctx, plan)
