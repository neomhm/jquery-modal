"""
refusals.budget: A budget sheet: budget lines, planned and actual amounts.
"""
from gen import b_refusals as R

ID = 'refusals.budget'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.budget(ctx, plan)
