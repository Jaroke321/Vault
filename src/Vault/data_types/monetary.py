from .base import MonetaryCategory


class Cash(MonetaryCategory):
    """Liquid accounts: checking, savings, HYSA, etc."""

    name = "cash"
    snapshot_table = "cash_snapshots"


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
