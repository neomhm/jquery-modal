"""products.repeated_headers - a printed export that repeats its header row (T6)."""
from gen import builders as B

ID = "products.repeated_headers"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, force_traps=('T6',))
