"""
refusals.not_offered: A real table whose target was not offered.
"""
from gen import b_refusals as R

ID = 'refusals.not_offered'
TARGET = "refusals"
REASON = 'no_matching_target'


def pick_target(rng):
    import config
    return rng.choice(config.TARGETS)


def build(ctx, plan):
    return R.not_offered(ctx, plan)
