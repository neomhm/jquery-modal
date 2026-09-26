"""
refusals.agenda_grid: An agenda week grid: time slots down, days across.
"""
from gen import b_refusals as R

ID = 'refusals.agenda_grid'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.agenda_grid(ctx, plan)
