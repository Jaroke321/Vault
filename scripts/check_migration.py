#!/usr/bin/env python3
"""Regression check for the additive schema migration (tasks 32 and 33).

Two independent checks, each against its own temp DB:
  1. Task 32: a pre-`price` investment_snapshots table gains the column via
     ALTER TABLE ADD COLUMN, with the existing row surviving intact.
  2. Task 33: a pre-task-33 cash_snapshots table gains six new columns the same
     way, AND cash_meta -- a table Cash never had before task 33 -- is created
     from nothing (a plain CREATE TABLE IF NOT EXISTS, not an ADD COLUMN; see
     DBHandler.init_db's create-then-sync split). Also confirms a migrated NULL
     as_of resolves to month-end through DBHandler.resolve_as_of().

Standalone (no pytest suite in this repo) so it can run from `/test` alongside
compileall.

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

# cash_snapshots as it looked before task 33 added as_of/contribution/source/
# note/apr_at_time/interest_accrued -- and before Cash had a meta table at all.
OLD_CASH_SNAPSHOTS_DDL = """
    CREATE TABLE cash_snapshots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        field_id    INTEGER NOT NULL REFERENCES fields(id),
        month       TEXT NOT NULL,
        value       REAL NOT NULL,
        recorded_at TEXT NOT NULL,
        UNIQUE(field_id, month)
    )
"""


def new_temp_db() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return Path(tmp.name)


def check_investment_price_migration(failures: list[str]) -> None:
    """Task 32: pre-price investment_snapshots gains `price`, old row survives
    with price IS NULL."""
    db_path = new_temp_db()
    try:
        with sqlite3.connect(db_path) as conn:
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

        # Constructing DBHandler runs init_db(), which should migrate the
        # existing table in place rather than requiring a fresh DB.
        DBHandler(db_path=db_path)

        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(investment_snapshots)")}
            if "price" not in columns:
                failures.append("[task 32] price column was not added to investment_snapshots")

            row = conn.execute(
                "SELECT quantity, price FROM investment_snapshots "
                "WHERE field_id = 1 AND month = '2026-01'"
            ).fetchone()
            if row is None:
                failures.append("[task 32] pre-existing snapshot row did not survive migration")
            else:
                quantity, price = row
                if quantity != 5.0:
                    failures.append(f"[task 32] pre-existing row's quantity changed: expected 5.0, got {quantity}")
                if price is not None:
                    failures.append(f"[task 32] pre-existing row's price should be NULL, got {price}")
    finally:
        os.unlink(db_path)


def check_cash_task33_migration(failures: list[str]) -> None:
    """Task 33: pre-task-33 cash_snapshots gains as_of/contribution/source/note/
    apr_at_time/interest_accrued; cash_meta is created from nothing (Cash never
    had a meta table before task 33 -- a different init_db code path than
    ALTER TABLE ADD COLUMN); a migrated NULL as_of resolves to month-end."""
    db_path = new_temp_db()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(OLD_FIELDS_DDL)
            conn.execute(OLD_CASH_SNAPSHOTS_DDL)
            conn.execute(
                "INSERT INTO fields (id, name, category, created_at) "
                "VALUES (1, 'checking', 'cash', '2026-01-01T00:00:00')"
            )
            conn.execute(
                "INSERT INTO cash_snapshots (field_id, month, value, recorded_at) "
                "VALUES (1, '2026-01', 5000.0, '2026-01-01T00:00:00')"
            )
            conn.commit()

        DBHandler(db_path=db_path)

        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cash_snapshots)")}
            expected = {"as_of", "contribution", "source", "note", "apr_at_time", "interest_accrued"}
            missing = expected - columns
            if missing:
                failures.append(f"[task 33] cash_snapshots missing columns after migration: {sorted(missing)}")

            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "cash_meta" not in tables:
                failures.append("[task 33] cash_meta table was not created on a DB that predates it")

            row = conn.execute(
                "SELECT value, as_of, contribution, source, note "
                "FROM cash_snapshots WHERE field_id = 1 AND month = '2026-01'"
            ).fetchone()
            if row is None:
                failures.append("[task 33] pre-existing cash_snapshots row did not survive migration")
            else:
                value, as_of, contribution, source, note = row
                if value != 5000.0:
                    failures.append(f"[task 33] pre-existing row's value changed: expected 5000.0, got {value}")
                if as_of is not None:
                    failures.append(f"[task 33] pre-existing row's as_of should be NULL, got {as_of}")
                if contribution is not None:
                    failures.append(f"[task 33] pre-existing row's contribution should be NULL, got {contribution}")
                if source != "manual":
                    failures.append(f"[task 33] pre-existing row's source should default to 'manual', got {source}")
                if note is not None:
                    failures.append(f"[task 33] pre-existing row's note should be NULL, got {note}")

        resolved = DBHandler.resolve_as_of(None, "2026-01", is_priced=False)
        if resolved != "2026-01-31":
            failures.append(
                f"[task 33] resolve_as_of(None, '2026-01', False) should be '2026-01-31', got {resolved!r}"
            )
    finally:
        os.unlink(db_path)


def main() -> int:
    failures: list[str] = []
    check_investment_price_migration(failures)
    check_cash_task33_migration(failures)

    if failures:
        print("FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "OK: migrated an old-shape investment_snapshots table in place — "
        "price column added, existing row intact with price IS NULL.\n"
        "OK: migrated an old-shape cash_snapshots table and created cash_meta "
        "from nothing — six new columns added, existing row intact, "
        "resolve_as_of() falls back to month-end for the migrated NULL as_of."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
