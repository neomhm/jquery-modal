"""products.catalogue - a full catalogue: code, category, VAT, stock, unit, barcode, active."""
from gen import builders as B

ID = "products.catalogue"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, catalogue=True)
