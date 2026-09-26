"""
refusals.chart_data: The data behind a chart: a few series by month.
"""
from gen import b_refusals as R

ID = 'refusals.chart_data'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.chart_data(ctx, plan)
