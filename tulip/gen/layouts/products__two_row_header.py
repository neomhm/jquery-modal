"""products.two_row_header - group labels above the header row."""
from gen import builders as B

ID = "products.two_row_header"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, two_row=True)
