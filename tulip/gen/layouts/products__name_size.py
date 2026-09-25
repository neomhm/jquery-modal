"""products.name_size - the name and the size in one cell, split with part() (T9)."""
from gen import builders as B

ID = "products.name_size"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, name_size=True)
