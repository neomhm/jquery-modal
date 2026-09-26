"""
refusals.pivot: A pivot / summary table: sums per category and month.
"""
from gen import b_refusals as R

ID = 'refusals.pivot'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.pivot(ctx, plan)
