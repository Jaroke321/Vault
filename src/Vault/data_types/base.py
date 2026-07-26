from abc import ABC
from enum import Enum


class FieldStatus(str, Enum):
    """Lifecycle state of a registry record. Also the source of truth for valid
    `field remove <name> [reason]` / `field set <name> status <value>` arguments."""

    ACTIVE = "active"
    SOLD = "sold"
    PAID_OFF = "paid_off"
    CLOSED = "closed"


class Category(ABC):
    """Declares one category's schema and net-worth behavior. Never instantiated —
    DBHandler and commands read these as class-level declarations via the CATEGORIES
    registry in data_types/__init__.py, so adding a category means adding a class here,
    not touching SQL scattered across the codebase."""

    name: str
    snapshot_table: str
    value_column: str  # "value" or "quantity" — the snapshot table's amount column
    unit_default: str
    meta_table: str | None = None
    is_liability: bool = False
    is_priced: bool = False

    @classmethod
    def snapshot_ddl(cls) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {cls.snapshot_table} (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id    INTEGER NOT NULL REFERENCES fields(id),
                month       TEXT NOT NULL,
                {cls.value_column} REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE(field_id, month)
            )
        """

    @classmethod
    def meta_ddl(cls) -> str | None:
        """Per-record metadata table DDL, or None if this category has no metadata
        beyond the shared registry. Overridden by categories like Debt and Investment."""
        return None

    @classmethod
    def role(cls) -> str:
        """Net-worth contribution: 'asset' or 'liability'."""
        return "liability" if cls.is_liability else "asset"

    @classmethod
    def usd_value(cls, amount: float, price: float | None = None) -> float:
        """Convert a stored snapshot amount to its USD net-worth contribution."""
        return amount

    @classmethod
    def display_unit(cls, meta_row=None) -> str:
        """Unit to display for a record. meta_row is this category's meta-table row
        (or None), for categories whose unit varies per-record rather than being fixed."""
        return cls.unit_default


class MonetaryCategory(Category):
    """Stores a single $ value per month. Base for Cash, Retirement, Asset, Debt."""

    value_column = "value"
    unit_default = "$"


class PricedCategory(Category):
    """Stores a quantity per month, valued via a live/cached/override market price
    rather than a raw dollar figure. Base for Investment."""

    value_column = "quantity"
    unit_default = "unit"  # fallback only; concrete unit is per-record (see display_unit)
    is_priced = True
