"""products.csv_export - an export from a shop system (all text)."""
from gen import builders as B

ID = "products.csv_export"
TARGET = "products"
CSV_ONLY = True


def build(ctx, plan):
    return B.products(ctx, plan, export=True)
