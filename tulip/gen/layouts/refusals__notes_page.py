"""
refusals.notes_page: A page of notes, one sentence per row.
"""
from gen import b_refusals as R

ID = 'refusals.notes_page'
TARGET = "refusals"
REASON = 'not_a_table'


def build(ctx, plan):
    return R.notes_page(ctx, plan)
