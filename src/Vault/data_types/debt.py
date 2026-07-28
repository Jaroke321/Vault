from .base import MonetaryCategory


class Debt(MonetaryCategory):
    """Liabilities — credit cards, loans, mortgages. Optionally backed by an
    asset-side record (debt_meta.backing_id) purely for the display-only
    balance/value/equity trio in `summary`; net worth is unaffected either way,
    since the backing record's value is counted independently on its own side."""

    name = "debt"
    snapshot_table = "debt_snapshots"
    meta_table = "debt_meta"
    is_liability = True
    has_apr = True
    supports_backing = True

    @classmethod
    def meta_ddl(cls) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {cls.meta_table} (
                field_id   INTEGER PRIMARY KEY REFERENCES fields(id),
                apr        REAL,
                backing_id INTEGER REFERENCES fields(id)
            )
        """
