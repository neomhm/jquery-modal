"""products.category_sheet - one sheet per category: the category is the sheet's name."""
from gen import builders as B

ID = "products.category_sheet"
TARGET = "products"


def build(ctx, plan):
    return B.products(ctx, plan, category_sheet=True)
