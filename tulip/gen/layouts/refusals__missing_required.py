"""
refusals.missing_required: A matching table without a required field (T15).
"""
from gen import b_refusals as R

ID = 'refusals.missing_required'
TARGET = "refusals"
REASON = 'missing_required'


def pick_target(rng):
    """The target whose table lacks a field."""
    return rng.choice(["products", "products", "bookings",
                       "invoice_ledger"])


def build(ctx, plan):
    return R.missing_required(ctx, plan)
