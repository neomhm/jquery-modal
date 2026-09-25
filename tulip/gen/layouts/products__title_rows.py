"""products.title_rows - title rows and a blank row above the header (T5)."""
from gen import builders as B

ID = "products.title_rows"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, force_traps=('T5',))
