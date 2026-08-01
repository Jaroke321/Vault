"""Schema migration: categories own their DDL (Category.snapshot_ddl() /
meta_ddl()); init_db() creates any missing table at full declared shape, then
diffs every existing table's live columns against that same DDL and issues
ALTER TABLE ADD COLUMN for anything missing (_sync_table). This is additive
only — a newly declared column must be nullable or have a constant default,
since SQLite can't ADD COLUMN a NOT NULL column without one, or a primary key
at all. Renames, type changes, drops, and data backfills are not supported;
a schema change needing any of those requires a real stepped-migration
mechanism, not this one. When you add a column to a category's DDL, that's
the whole migration — no separate migration step to write or register."""

import sqlite3
import datetime
from pathlib import Path

from .data_types import CATEGORIES, FieldStatus
from .price_fetcher import PriceFetcher


def _declared_columns(ddl: str, table: str) -> dict[str, sqlite3.Row]:
    """Return {column_name: PRAGMA table_info row} for the shape `ddl` declares,
    by executing it against a throwaway in-memory connection rather than parsing
    the DDL string. A dangling `REFERENCES` target is fine here — SQLite doesn't
    resolve foreign keys at CREATE TABLE time."""
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(ddl)
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"]: row for row in rows}


def _live_columns(conn, table: str) -> set[str]:
    """Return the column names actually present on `table` in `conn`. An empty
    result means the table doesn't exist yet — the caller treats that as
    nothing to migrate, since CREATE TABLE IF NOT EXISTS will have just built
    it at full declared shape."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _sync_table(conn, table: str, ddl: str) -> None:
    """Add any column `ddl` declares that `table` is currently missing, via
    ALTER TABLE ADD COLUMN — the additive half of init_db's migration.
    Declared order is preserved so multiple additions land predictably.
    Renames, type changes, and drops are out of scope; see the module
    docstring."""
    declared = _declared_columns(ddl, table)
    live = _live_columns(conn, table)
    for name, col in declared.items():
        if name in live:
            continue
        if col["pk"] or (col["notnull"] and col["dflt_value"] is None):
            raise RuntimeError(
                f"Cannot migrate {table}.{name}: SQLite can't ADD COLUMN a "
                "primary key or a NOT NULL column without a constant default. "
                "Newly declared columns must be nullable or have a constant "
                "default — see the module docstring."
            )
        clause = f"ALTER TABLE {table} ADD COLUMN {name} {col['type']}"
        if col["dflt_value"] is not None:
            clause += f" DEFAULT {col['dflt_value']}"
        conn.execute(clause)


_FIELDS_DDL = """
    CREATE TABLE IF NOT EXISTS fields (
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


class DBHandler:

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            db_path = base_dir / "vault.db"
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Create-then-sync: the fixed CATEGORIES registry (data_types/__init__.py)
        drives table creation (one snapshot table and, where declared, one meta
        table per category, alongside the shared fields registry), then every
        table is diffed against its declared shape and patched with any missing
        columns. See the module docstring for what that migration can and can't
        do. Runs on every startup, so an existing vault.db picks up newly
        declared columns without losing its history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(_FIELDS_DDL)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_fields_active_name
                ON fields(name) WHERE deactivated_at IS NULL
            """)
            for category in CATEGORIES.values():
                conn.execute(category.snapshot_ddl())
                meta_ddl = category.meta_ddl()
                if meta_ddl is not None:
                    conn.execute(meta_ddl)

            _sync_table(conn, "fields", _FIELDS_DDL)
            for category in CATEGORIES.values():
                _sync_table(conn, category.snapshot_table, category.snapshot_ddl())
                meta_ddl = category.meta_ddl()
                if meta_ddl is not None:
                    _sync_table(conn, category.meta_table, meta_ddl)

            conn.commit()

    def get_categories(self) -> list:
        """Return the fixed category names, sorted. Categories are code-defined
        (CATEGORIES) — there is no runtime creation, unlike the old categories table."""
        return sorted(CATEGORIES.keys())

    def add_field(self, name: str, category: str) -> bool:
        """Register a new record under `category`. Categories are fixed — an unknown
        category is rejected. Never reactivates a previously closed record: re-adding a
        name mints a brand new row, so a sold-then-rebought instance (e.g. house ->
        new house) never merges snapshot series with its predecessor. A duplicate
        *active* name is rejected via the ux_fields_active_name unique index."""
        name = name.lower()
        category = category.lower()
        if category not in CATEGORIES:
            return False
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute(
                    "INSERT INTO fields (name, category, created_at) VALUES (?, ?, ?)",
                    (name, category, datetime.datetime.now().isoformat())
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def close_field(self, name: str, reason: str = FieldStatus.CLOSED.value) -> bool:
        """Close (soft-delete) the active record named `name`, tagging it with a
        lifecycle reason. History is preserved; the name frees up for reuse once
        closed. Returns False for an invalid reason or no matching active record."""
        if reason not in FieldStatus.values():
            return False
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(
                "UPDATE fields SET deactivated_at = ?, status = ? WHERE name = ? AND deactivated_at IS NULL",
                (datetime.datetime.now().isoformat(), reason, name.lower())
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_field_category(self, name: str) -> str | None:
        """Return the active record's category name, or None if no active record
        matches."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT category FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (name.lower(),)
            ).fetchone()
        return row[0] if row is not None else None

    def get_fields_by_category(self, category_name: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM fields WHERE category = ? AND deactivated_at IS NULL ORDER BY name",
                (category_name.lower(),)
            ).fetchall()
        return [r[0] for r in rows]

    def _resolve_unit(self, conn, category_cls, field_id: int) -> str:
        """Resolve a record's display unit: fixed for monetary categories, or read
        from its meta table for priced categories (Investment) whose unit varies
        per-record. Falls back to the class default if no meta row exists yet."""
        if not category_cls.is_priced:
            return category_cls.display_unit()
        row = conn.execute(
            f"SELECT * FROM {category_cls.meta_table} WHERE field_id = ?", (field_id,)
        ).fetchone()
        return category_cls.display_unit(row)

    def get_field_unit(self, field_name: str) -> str:
        """Return the active record's display unit, or "$" if no active record
        matches."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, category FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return "$"
            field_id, category = row
            return self._resolve_unit(conn, CATEGORIES[category], field_id)

    def get_active_fields(self) -> list:
        """Return (name, category, unit) for every active record, ordered by
        category then name."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, category FROM fields WHERE deactivated_at IS NULL ORDER BY category, name"
            ).fetchall()
            return [
                (name, category, self._resolve_unit(conn, CATEGORIES[category], field_id))
                for field_id, name, category in rows
            ]

    def set_note(self, name: str, note: str) -> bool:
        """Attach a free-text note to any active record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE fields SET note = ? WHERE name = ? AND deactivated_at IS NULL",
                (note, name.lower())
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_notes(self) -> dict[str, str]:
        """Return {field_name: note} for every active record with a non-empty note."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT name, note FROM fields
                   WHERE deactivated_at IS NULL
                     AND note IS NOT NULL
                     AND note != ''"""
            ).fetchall()
        return {name: note for name, note in rows}

    def get_note(self, name: str) -> str | None:
        """Return the active record's note, or None if absent or empty."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT note FROM fields
                   WHERE name = ? AND deactivated_at IS NULL""",
                (name.lower(),),
            ).fetchone()
        if row is None or row[0] is None or row[0] == "":
            return None
        return row[0]

    def get_field_apr(self, name: str) -> float | None:
        """Return the active record's APR when its category supports it, or None."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (name.lower(),),
            ).fetchone()
        if row is None:
            return None
        return self.get_apr(row[0])

    def set_status(self, name: str, status: str) -> bool:
        """Relabel an active record's lifecycle status directly, independent of
        closing it (e.g. correcting a status set via `field remove`). Rejects
        anything outside FieldStatus."""
        if status not in FieldStatus.values():
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE fields SET status = ? WHERE name = ? AND deactivated_at IS NULL",
                (status, name.lower())
            )
            conn.commit()
            return cursor.rowcount == 1

    def set_apr(self, name: str, apr: float) -> bool:
        """Set an active record's interest rate when its category declares has_apr."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            resolved = self._field_and_category(conn, name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            if not category_cls.has_apr or category_cls.meta_table is None:
                return False
            conn.execute(
                f"""INSERT INTO {category_cls.meta_table} (field_id, apr) VALUES (?, ?)
                   ON CONFLICT(field_id) DO UPDATE SET apr = excluded.apr""",
                (field_id, apr)
            )
            conn.commit()
            return True

    def set_backing(self, name: str, backing_name: str) -> bool:
        """Link a record to an active asset-side backing record when its category
        declares supports_backing — purely for the display-only balance/value/equity
        trio in `summary`; net worth is unaffected either way, since the backing
        record's value is already counted on its own side of the ledger."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            source = self._field_and_category(conn, name)
            if source is None:
                return False
            field_id, category_cls = source
            if not category_cls.supports_backing or category_cls.meta_table is None:
                return False

            backing = self._field_and_category(conn, backing_name)
            if backing is None or backing[1].is_liability:
                return False

            backing_id = backing[0]
            conn.execute(
                f"""INSERT INTO {category_cls.meta_table} (field_id, backing_id) VALUES (?, ?)
                   ON CONFLICT(field_id) DO UPDATE SET backing_id = excluded.backing_id""",
                (field_id, backing_id)
            )
            conn.commit()
            return True

    def clear_backing(self, name: str) -> bool:
        """Remove a record's backing link when its category declares supports_backing."""
        with sqlite3.connect(self.db_path) as conn:
            resolved = self._field_and_category(conn, name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            if not category_cls.supports_backing or category_cls.meta_table is None:
                return False
            cursor = conn.execute(
                f"UPDATE {category_cls.meta_table} SET backing_id = NULL WHERE field_id = ?",
                (field_id,),
            )
            conn.commit()
            return cursor.rowcount == 1

    def set_replaces(self, name: str, old_name: str) -> bool:
        """Mark the active record `name` as the successor of the most recent record
        previously named `old_name` (its own predecessor, e.g. after a sell/rebuy).
        Purely informational for future reporting — no snapshot data is merged."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            resolved = self._field_and_category(conn, name)
            if resolved is None:
                return False
            field_id, _ = resolved

            old_row = conn.execute(
                """SELECT id FROM fields WHERE name = ? AND id != ?
                   ORDER BY created_at DESC LIMIT 1""",
                (old_name.lower(), field_id)
            ).fetchone()
            if old_row is None:
                return False

            conn.execute(
                "UPDATE fields SET replaces_id = ? WHERE id = ?", (old_row[0], field_id)
            )
            conn.commit()
            return True

    def set_investment_symbol(self, name: str, symbol: str) -> bool:
        """Set (or change) a priced record's price-tracking symbol, recomputing its
        display unit alongside it (troy oz/etc. for known commodities, 'shares' for
        pass-through stock/ETF tickers). Only valid for an active is_priced record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            resolved = self._field_and_category(conn, name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            if not category_cls.is_priced or category_cls.meta_table is None:
                return False
            resolved_symbol = PriceFetcher.resolve_symbol(symbol)
            unit = PriceFetcher.SYMBOL_TO_UNIT.get(resolved_symbol, "shares")
            conn.execute(
                f"""INSERT INTO {category_cls.meta_table} (field_id, unit, symbol) VALUES (?, ?, ?)
                   ON CONFLICT(field_id) DO UPDATE SET unit = excluded.unit,
                                                        symbol = excluded.symbol""",
                (field_id, unit, resolved_symbol)
            )
            conn.commit()
            return True

    def _field_and_category(self, conn, field_name: str) -> tuple[int, type] | None:
        """Resolve an active record's (field_id, category class), or None if no
        active record matches. Shared by every category-routed snapshot method."""
        row = conn.execute(
            "SELECT id, category FROM fields WHERE name = ? AND deactivated_at IS NULL",
            (field_name.lower(),)
        ).fetchone()
        if row is None:
            return None
        field_id, category = row
        return field_id, CATEGORIES[category]

    def record_value(self, field_name: str, month: str, amount: float, recorded_at: str | None = None) -> bool:
        """Stage a snapshot for an active record, routed to its category's snapshot
        table and value column ('value' for monetary categories, 'quantity' for
        Investment). Upserts on (field_id, month)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            resolved = self._field_and_category(conn, field_name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            if recorded_at is None:
                recorded_at = datetime.datetime.now().isoformat()
            table, column = category_cls.snapshot_table, category_cls.value_column
            conn.execute(
                f"""INSERT INTO {table} (field_id, month, {column}, recorded_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(field_id, month)
                    DO UPDATE SET {column} = excluded.{column},
                                  recorded_at = excluded.recorded_at""",
                (field_id, month, amount, recorded_at)
            )
            conn.commit()
            return True

    def delete_value(self, field_name: str, month: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            resolved = self._field_and_category(conn, field_name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            cursor = conn.execute(
                f"DELETE FROM {category_cls.snapshot_table} WHERE field_id = ? AND month = ?",
                (field_id, month)
            )
            conn.commit()
            return cursor.rowcount == 1

    def _union_months(self, conn, limit: int | None = None) -> list[str]:
        """Distinct months across every category's snapshot table, ascending. With a
        limit, returns only the most recent N months (still ascending)."""
        parts = " UNION ALL ".join(f"SELECT month FROM {c.snapshot_table}" for c in CATEGORIES.values())
        if limit is None:
            rows = conn.execute(f"SELECT DISTINCT month FROM ({parts}) ORDER BY month").fetchall()
            return [r[0] for r in rows]
        rows = conn.execute(
            f"SELECT DISTINCT month FROM ({parts}) ORDER BY month DESC LIMIT ?", (limit,)
        ).fetchall()
        return sorted(r[0] for r in rows)

    def _snapshot_rows(
        self, conn, months: list[str] | None = None, field_names: list[str] | None = None
    ):
        """Yield (field_name, month, amount) across every category's snapshot table,
        for active records only, optionally filtered to specific months and/or names."""
        for category_cls in CATEGORIES.values():
            clauses = ["f.deactivated_at IS NULL"]
            params: list = []
            if months is not None:
                clauses.append(f"s.month IN ({','.join('?' * len(months))})")
                params.extend(months)
            if field_names is not None:
                clauses.append(f"f.name IN ({','.join('?' * len(field_names))})")
                params.extend(field_names)
            rows = conn.execute(
                f"""SELECT f.name, s.month, s.{category_cls.value_column}
                    FROM {category_cls.snapshot_table} s
                    JOIN fields f ON f.id = s.field_id
                    WHERE {' AND '.join(clauses)}""",
                params,
            ).fetchall()
            yield from rows

    def get_history(self, field_name: str = None, months: int = 6):
        if field_name is not None:
            with sqlite3.connect(self.db_path) as conn:
                resolved = self._field_and_category(conn, field_name)
                if resolved is None:
                    return []
                field_id, category_cls = resolved
                rows = conn.execute(
                    f"""SELECT month, {category_cls.value_column}
                        FROM {category_cls.snapshot_table}
                        WHERE field_id = ?
                        ORDER BY month DESC
                        LIMIT ?""",
                    (field_id, months)
                ).fetchall()
            rows.reverse()
            return rows
        else:
            with sqlite3.connect(self.db_path) as conn:
                month_list = self._union_months(conn, limit=months)

                if not month_list:
                    return ([], [], {})

                active_fields = self.get_active_fields()

                data = {}
                for name, month, amount in self._snapshot_rows(conn, months=month_list):
                    data.setdefault(name, {})[month] = amount

            return (month_list, active_fields, data)

    def get_full_history(self):
        """Return the complete recorded history across all active fields — every distinct
        month on record, not limited to a recent window. Same 3-tuple shape as
        get_history()'s all-fields form: (month_list, active_fields, data)."""
        with sqlite3.connect(self.db_path) as conn:
            month_list = self._union_months(conn)

            if not month_list:
                return ([], [], {})

            active_fields = self.get_active_fields()

            data = {}
            for name, month, amount in self._snapshot_rows(conn, months=month_list):
                data.setdefault(name, {})[month] = amount

        return (month_list, active_fields, data)

    def get_field_values(self, field_names: list[str]) -> dict[str, dict[str, float]]:
        """Return {field_name: {month: value}} for the given *active* records.

        Names are matched case-insensitively and returned lower-cased. Empty input
        returns {} without querying.
        """
        if not field_names:
            return {}

        lowered = [name.lower() for name in field_names]
        with sqlite3.connect(self.db_path) as conn:
            data: dict[str, dict[str, float]] = {}
            for name, month, amount in self._snapshot_rows(conn, field_names=lowered):
                data.setdefault(name, {})[month] = amount
        return data

    def get_values_for_month(self, month: str) -> dict[str, float]:
        """Return {field_name: amount} for active records at the given month, unioned
        across every category's snapshot table.

        Returns {} when the month has no rows — callers distinguish missing data
        from zero by key absence, not by a sentinel value.
        """
        results: dict[str, float] = {}
        with sqlite3.connect(self.db_path) as conn:
            for category_cls in CATEGORIES.values():
                rows = conn.execute(
                    f"""SELECT f.name, s.{category_cls.value_column}
                        FROM {category_cls.snapshot_table} s
                        JOIN fields f ON f.id = s.field_id
                        WHERE f.deactivated_at IS NULL
                          AND s.month = ?""",
                    (month,),
                ).fetchall()
                for name, amount in rows:
                    results[name] = amount
        return results

    def get_value(self, field_name: str, month: str) -> float | None:
        """Return the snapshot amount for one active record+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            resolved = self._field_and_category(conn, field_name)
            if resolved is None:
                return None
            field_id, category_cls = resolved
            row = conn.execute(
                f"""SELECT {category_cls.value_column} FROM {category_cls.snapshot_table}
                    WHERE field_id = ? AND month = ?""",
                (field_id, month),
            ).fetchone()
        return float(row[0]) if row is not None else None

    def get_value_row(self, field_name: str, month: str) -> tuple[float, str] | None:
        """Return (amount, recorded_at) for one active record+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            resolved = self._field_and_category(conn, field_name)
            if resolved is None:
                return None
            field_id, category_cls = resolved
            row = conn.execute(
                f"""SELECT {category_cls.value_column}, recorded_at
                    FROM {category_cls.snapshot_table}
                    WHERE field_id = ? AND month = ?""",
                (field_id, month),
            ).fetchone()
        return (float(row[0]), row[1]) if row is not None else None

    def get_latest_values(self) -> list:
        """Return (name, category, unit, amount, field_id) for the most recent
        snapshot of every active record, ordered by category then name. `amount` is
        the record's raw stored value ('value' for monetary categories, 'quantity'
        for Investment) — callers resolve USD equivalents per-category (e.g. via
        CATEGORIES[category].usd_value()). Records with no recorded snapshot yet are
        excluded, same as before."""
        with sqlite3.connect(self.db_path) as conn:
            results = []
            for category_cls in CATEGORIES.values():
                table, column = category_cls.snapshot_table, category_cls.value_column
                rows = conn.execute(
                    f"""SELECT f.name, f.category, s.{column}, f.id
                        FROM {table} s
                        JOIN fields f ON f.id = s.field_id
                        WHERE f.deactivated_at IS NULL
                          AND s.month = (
                                  SELECT MAX(s2.month) FROM {table} s2 WHERE s2.field_id = f.id
                              )"""
                ).fetchall()
                for name, category, amount, field_id in rows:
                    unit = self._resolve_unit(conn, category_cls, field_id)
                    results.append((name, category, unit, amount, field_id))
        results.sort(key=lambda r: (r[1], r[0]))
        return results

    def get_apr(self, field_id: int) -> float | None:
        """Return the active debt record's APR, or None if absent or not applicable."""
        with sqlite3.connect(self.db_path) as conn:
            source_row = conn.execute(
                "SELECT category FROM fields WHERE id = ? AND deactivated_at IS NULL",
                (field_id,),
            ).fetchone()
            if source_row is None:
                return None
            category_cls = CATEGORIES[source_row[0]]
            if not category_cls.has_apr or category_cls.meta_table is None:
                return None
            row = conn.execute(
                f"SELECT apr FROM {category_cls.meta_table} WHERE field_id = ?",
                (field_id,),
            ).fetchone()
            if row is None or row[0] is None:
                return None
            return float(row[0])

    def get_backing_info(self, field_id: int) -> tuple[str, str, float, int] | None:
        """For a record whose category declares supports_backing, resolve its backing
        link (if any) to the backed record's name, category, latest recorded amount,
        and its own field_id (needed to resolve a live price if the backing record is
        itself priced) — used by `summary` to print the display-only balance/value/
        equity trio. Returns None if unlinked, the backing record is gone, or it has
        no recorded value yet."""
        with sqlite3.connect(self.db_path) as conn:
            source_row = conn.execute(
                "SELECT category FROM fields WHERE id = ? AND deactivated_at IS NULL",
                (field_id,),
            ).fetchone()
            if source_row is None:
                return None
            source_cls = CATEGORIES[source_row[0]]
            if not source_cls.supports_backing or source_cls.meta_table is None:
                return None

            row = conn.execute(
                f"SELECT backing_id FROM {source_cls.meta_table} WHERE field_id = ?",
                (field_id,),
            ).fetchone()
            if row is None or row[0] is None:
                return None
            backing_id = row[0]

            backing_row = conn.execute(
                "SELECT name, category FROM fields WHERE id = ? AND deactivated_at IS NULL",
                (backing_id,)
            ).fetchone()
            if backing_row is None:
                return None
            name, category = backing_row
            table, column = CATEGORIES[category].snapshot_table, CATEGORIES[category].value_column

            value_row = conn.execute(
                f"""SELECT {column} FROM {table}
                    WHERE field_id = ?
                      AND month = (SELECT MAX(month) FROM {table} WHERE field_id = ?)""",
                (backing_id, backing_id)
            ).fetchone()
            if value_row is None:
                return None
            return name, category, float(value_row[0]), backing_id

    def get_investment_fields(self) -> list:
        """Return (field_id, name, symbol, override_price, cached_price, cached_at)
        for every active is_priced record — the price-fetching surface for
        PriceFetcher and `investment list`/`investment refresh`. Tagging itself
        happens at `field add investment <name> <symbol>` time via
        set_investment_symbol; there is no separate tag/untag step."""
        with sqlite3.connect(self.db_path) as conn:
            rows = []
            for category_cls in CATEGORIES.values():
                if not category_cls.is_priced or category_cls.meta_table is None:
                    continue
                rows.extend(conn.execute(
                    f"""SELECT f.id, f.name, m.symbol, m.override_price, m.cached_price, m.cached_at
                       FROM {category_cls.meta_table} m
                       JOIN fields f ON f.id = m.field_id
                       WHERE f.deactivated_at IS NULL"""
                ).fetchall())
        return rows

    def _priced_field_id(self, conn, field_name: str) -> tuple[int, type] | None:
        """Resolve an active is_priced record to (field_id, category class), or None."""
        resolved = self._field_and_category(conn, field_name)
        if resolved is None:
            return None
        field_id, category_cls = resolved
        if not category_cls.is_priced or category_cls.meta_table is None:
            return None
        return field_id, category_cls

    def set_override(self, field_name: str, price) -> bool:
        """Set (or clear, with price=None) an active is_priced record's manual override."""
        with sqlite3.connect(self.db_path) as conn:
            resolved = self._priced_field_id(conn, field_name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            conn.execute(
                f"UPDATE {category_cls.meta_table} SET override_price = ? WHERE field_id = ?",
                (price, field_id)
            )
            conn.commit()
            return True

    def set_cache(self, field_name: str, price: float, timestamp: str) -> bool:
        """Set an active is_priced record's cached price + timestamp from the last live fetch."""
        with sqlite3.connect(self.db_path) as conn:
            resolved = self._priced_field_id(conn, field_name)
            if resolved is None:
                return False
            field_id, category_cls = resolved
            conn.execute(
                f"UPDATE {category_cls.meta_table} SET cached_price = ?, cached_at = ? WHERE field_id = ?",
                (price, timestamp, field_id)
            )
            conn.commit()
            return True

    def update_cached_price(self, field_id: int, price: float, timestamp: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT category FROM fields WHERE id = ? AND deactivated_at IS NULL",
                (field_id,),
            ).fetchone()
            if row is None:
                return
            category_cls = CATEGORIES[row[0]]
            if not category_cls.is_priced or category_cls.meta_table is None:
                return
            conn.execute(
                f"UPDATE {category_cls.meta_table} SET cached_price = ?, cached_at = ? WHERE field_id = ?",
                (price, timestamp, field_id)
            )
            conn.commit()
