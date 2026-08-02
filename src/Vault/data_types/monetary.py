from .base import MonetaryCategory


class Cash(MonetaryCategory):
    """Liquid accounts: checking, savings, HYSA, etc. has_apr covers the
    high-yield-savings case -- a savings rate is the mirror image of a debt's
    APR, and set_apr/get_apr/get_field_apr are already generic over any
    category declaring meta_table + has_apr, so no new DB code is needed."""

    name = "cash"
    snapshot_table = "cash_snapshots"
    meta_table = "cash_meta"
    has_apr = True

    @classmethod
    def meta_ddl(cls) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {cls.meta_table} (
                field_id INTEGER PRIMARY KEY REFERENCES fields(id),
                apr      REAL
            )
        """


class Retirement(MonetaryCategory):
    """401k/IRA and similar — illiquid, grouped separately from Cash in summary."""

    name = "retirement"
    snapshot_table = "retirement_snapshots"


class Asset(MonetaryCategory):
    """Property and other owned valuables (house, car, ...). Can back a Debt record
    via debt_meta.backing_id, for the display-only balance/value/equity trio in
    `summary` — the link never affects net-worth totals."""

    name = "asset"
    snapshot_table = "asset_snapshots"
