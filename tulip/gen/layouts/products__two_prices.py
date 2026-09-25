"""products.two_prices - the price with and without tax (T2)."""
from gen import builders as B

ID = "products.two_prices"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, force_two_prices=True)
