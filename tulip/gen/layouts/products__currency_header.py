"""products.currency_header - the currency only in the header or the number format (T13)."""
from gen import builders as B

ID = "products.currency_header"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, force_traps=('T13',))
