"""products.sections - section rows with the category (T7)."""
from gen import builders as B

ID = "products.sections"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, sections=True)
