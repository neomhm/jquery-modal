"""products.extra_columns - cost, margin, supplier and notes columns next to the price (T1)."""
from gen import builders as B

ID = "products.extra_columns"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, inventory=True, force_traps=('T1',))
