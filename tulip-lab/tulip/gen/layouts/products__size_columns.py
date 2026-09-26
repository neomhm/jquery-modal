"""products.size_columns - sizes as columns, read with unpivot() (T8)."""
from gen import builders as B

ID = "products.size_columns"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, size_columns=True)
