"""products.totals - subtotal and total rows (T4)."""
from gen import builders as B

ID = "products.totals"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, sections=False, force_traps=('T4',))
