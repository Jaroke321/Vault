from .base import PricedCategory


class Investment(PricedCategory):
    """Priced holdings valued via a live/cached/override market price — metals (oz),
    stocks/ETFs (shares), or any other quantity that needs a per-record unit + symbol.
    Absorbs today's commodity/PriceFetcher machinery."""

    name = "investment"
    snapshot_table = "investment_snapshots"
    meta_table = "investment_meta"

    @classmethod
    def meta_ddl(cls) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {cls.meta_table} (
                field_id       INTEGER PRIMARY KEY REFERENCES fields(id),
                unit           TEXT NOT NULL,
                symbol         TEXT NOT NULL,
                override_price REAL,
                cached_price   REAL,
                cached_at      TEXT
            )
        """

    @classmethod
    def usd_value(cls, amount: float, price: float | None = None) -> float:
        """amount is the recorded quantity; price is the resolved per-unit market
        price (override -> live -> cached), or None if unavailable."""
        if price is None:
            return 0.0
        return amount * price

    @classmethod
    def display_unit(cls, meta_row=None) -> str:
        """meta_row is an investment_meta row: (field_id, unit, symbol,
        override_price, cached_price, cached_at)."""
        if meta_row is None:
            return cls.unit_default
        return meta_row[1]
