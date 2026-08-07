from .base import Category, MonetaryCategory, PricedCategory, FieldStatus, SnapshotSource
from .monetary import Cash, Retirement, Asset
from .debt import Debt
from .investment import Investment

# Fixed, closed set of categories — the single source of truth for "what categories
# exist," consumed by DBHandler (table creation), field-add validation, and summary.
CATEGORIES: dict[str, type[Category]] = {
    c.name: c for c in (Cash, Retirement, Asset, Debt, Investment)
}
