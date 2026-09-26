"""products.size_columns_sections - sizes as columns and section rows (T8, T7)."""
from gen import builders as B

ID = "products.size_columns_sections"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, size_columns=True, sections=True)
