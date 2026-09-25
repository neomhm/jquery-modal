"""
refusals.too_wide: More than 26 columns.
"""
from gen import b_refusals as R

ID = 'refusals.too_wide'
TARGET = "refusals"
REASON = 'too_wide'


def pick_target(rng):
    """The kind of export that grew too wide."""
    return rng.choice(["products", "clients", "staff"])


def build(ctx, plan):
    return R.too_wide(ctx, plan)
