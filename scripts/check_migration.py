#!/usr/bin/env python3
"""Regression check for the additive schema migration (task 32).

Builds a vault.db with investment_snapshots in its pre-price shape (no
`price` column), seeds one row, then opens it through DBHandler.init_db()
and confirms the column was added and the existing row survived intact
with price IS NULL. Standalone (no pytest suite in this repo) so it can
run from `/test` alongside compileall.

Usage: python3 scripts/check_migration.py
Exits 0 on success, 1 on failure.
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from Vault.db_handler import DBHandler  # noqa: E402

# The fields table's declared shape, duplicated from db_handler._FIELDS_DDL so
# this script can build an old-shape DB without importing private helpers.
OLD_FIELDS_DDL = """
    CREATE TABLE fields (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL,
        category       TEXT    NOT NULL,
        note           TEXT,
        status         TEXT    NOT NULL DEFAULT 'active',
        replaces_id    INTEGER REFERENCES fields(id),
        created_at     TEXT    NOT NULL,
        deactivated_at TEXT
    )
"""

# investment_snapshots as it looked before task 32 added `price`.
OLD_INVESTMENT_SNAPSHOTS_DDL = """
    CREATE TABLE investment_snapshots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        field_id    INTEGER NOT NULL REFERENCES fields(id),
        month       TEXT NOT NULL,
        quantity    REAL NOT NULL,
        recorded_at TEXT NOT NULL,
        UNIQUE(field_id, month)
    )
"""


def build_old_schema_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(OLD_FIELDS_DDL)
        conn.execute(OLD_INVESTMENT_SNAPSHOTS_DDL)
        conn.execute(
            "INSERT INTO fields (id, name, category, created_at) "
            "VALUES (1, 'gold', 'investment', '2026-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO investment_snapshots (field_id, month, quantity, recorded_at) "
            "VALUES (1, '2026-01', 5.0, '2026-01-01T00:00:00')"
        )
        conn.commit()


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    failures: list[str] = []

    try:
        build_old_schema_db(db_path)

        # Constructing DBHandler runs init_db(), which should migrate the
        # existing table in place rather than requiring a fresh DB.
        DBHandler(db_path=db_path)

        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(investment_snapshots)")}
            if "price" not in columns:
                failures.append("price column was not added to investment_snapshots")

            row = conn.execute(
                "SELECT quantity, price FROM investment_snapshots "
                "WHERE field_id = 1 AND month = '2026-01'"
            ).fetchone()
            if row is None:
                failures.append("pre-existing snapshot row did not survive migration")
            else:
                quantity, price = row
                if quantity != 5.0:
                    failures.append(f"pre-existing row's quantity changed: expected 5.0, got {quantity}")
                if price is not None:
                    failures.append(f"pre-existing row's price should be NULL, got {price}")
    finally:
        os.unlink(db_path)

    if failures:
        print("FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "OK: migrated an old-shape investment_snapshots table in place — "
        "price column added, existing row intact with price IS NULL."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
