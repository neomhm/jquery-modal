"""products.simple - a plain price list."""
from gen import builders as B

ID = "products.simple"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan)
