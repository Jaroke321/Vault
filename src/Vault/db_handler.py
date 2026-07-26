import sqlite3
import datetime
from pathlib import Path

from .data_types import CATEGORIES


class DBHandler:

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            db_path = base_dir / "vault.db"
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Wipe-and-recreate schema — no migration. The fixed CATEGORIES registry
        (data_types/__init__.py) drives table creation: one snapshot table and, where
        declared, one meta table per category, alongside the shared fields registry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("""
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
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_fields_active_name
                ON fields(name) WHERE deactivated_at IS NULL
            """)
            for category in CATEGORIES.values():
                conn.execute(category.snapshot_ddl())
                meta_ddl = category.meta_ddl()
                if meta_ddl is not None:
                    conn.execute(meta_ddl)
            conn.commit()

    def add_category(self, name: str) -> int:
        name = name.lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
            conn.commit()
            row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
            return row[0]

    def add_field(self, name: str, category: str) -> bool:
        name = name.lower()
        category = category.lower()
        category_id = self.add_category(category)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            # Check if a deactivated field with this name exists — reactivate it
            row = conn.execute(
                "SELECT id, deactivated_at FROM fields WHERE name = ?", (name,)
            ).fetchone()
            if row is not None:
                field_id, deactivated_at = row
                if deactivated_at is not None:
                    conn.execute(
                        "UPDATE fields SET deactivated_at = NULL, category_id = ? WHERE id = ?",
                        (category_id, field_id)
                    )
                    conn.commit()
                    return True
                else:
                    return False  # Already active with this name
            try:
                conn.execute(
                    "INSERT INTO fields (name, category_id, created_at, deactivated_at) VALUES (?, ?, ?, NULL)",
                    (name, category_id, datetime.datetime.now().isoformat())
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def deactivate_field(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(
                "UPDATE fields SET deactivated_at = ? WHERE name = ? AND deactivated_at IS NULL",
                (datetime.datetime.now().isoformat(), name.lower())
            )
            conn.commit()
            return cursor.rowcount == 1

    def set_category_unit(self, category: str, unit: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE categories SET unit = ? WHERE name = ?",
                (unit.strip(), category.lower())
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_field_unit(self, field_name: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT c.unit FROM fields f
                   JOIN categories c ON c.id = f.category_id
                   WHERE f.name = ? AND f.deactivated_at IS NULL""",
                (field_name.lower(),)
            ).fetchone()
        return row[0] if row else "$"

    def get_active_fields(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name, c.name, c.unit
                   FROM fields f
                   JOIN categories c ON c.id = f.category_id
                   WHERE f.deactivated_at IS NULL
                   ORDER BY c.name, f.name"""
            ).fetchall()
            return rows

    def get_categories(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM categories ORDER BY name"
            ).fetchall()
            return [c[0] for c in rows]

    def get_fields_by_category(self, category_name: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name
                   FROM fields f
                   JOIN categories c ON c.id = f.category_id
                   WHERE c.name = ? AND f.deactivated_at IS NULL
                   ORDER BY f.name""",
                (category_name,)
            ).fetchall()
            return [r[0] for r in rows]

    def record_value(self, field_name: str, month: str, value: float, recorded_at: str | None = None) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                "SELECT id FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            field_id = row[0]
            if recorded_at is None:
                recorded_at = datetime.datetime.now().isoformat()
            conn.execute(
                """INSERT INTO snapshots (field_id, month, value, recorded_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(field_id, month)
                   DO UPDATE SET value = excluded.value,
                                 recorded_at = excluded.recorded_at""",
                (field_id, month, value, recorded_at)
            )
            conn.commit()
            return True

    def record_asset_value(self, field_name: str, month: str, asset_value: float, recorded_at: str | None = None) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                """SELECT f.id FROM fields f
                   JOIN categories c ON c.id = f.category_id
                   WHERE f.name = ?
                     AND f.deactivated_at IS NULL
                     AND c.name = 'debt'""",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            field_id = row[0]
            if recorded_at is None:
                recorded_at = datetime.datetime.now().isoformat()
            conn.execute(
                """INSERT INTO debt_asset_snapshots (field_id, month, asset_value, recorded_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(field_id, month)
                   DO UPDATE SET asset_value = excluded.asset_value,
                                 recorded_at = excluded.recorded_at""",
                (field_id, month, asset_value, recorded_at)
            )
            conn.commit()
            return True

    def delete_value(self, field_name: str, month: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                "SELECT id FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            field_id = row[0]
            cursor = conn.execute(
                "DELETE FROM snapshots WHERE field_id = ? AND month = ?",
                (field_id, month)
            )
            conn.commit()
            return cursor.rowcount == 1

    def delete_asset_value(self, field_name: str, month: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                """SELECT f.id FROM fields f
                   JOIN categories c ON c.id = f.category_id
                   WHERE f.name = ?
                     AND f.deactivated_at IS NULL
                     AND c.name = 'debt'""",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            field_id = row[0]
            cursor = conn.execute(
                "DELETE FROM debt_asset_snapshots WHERE field_id = ? AND month = ?",
                (field_id, month)
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_history(self, field_name: str = None, months: int = 6):
        if field_name is not None:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """SELECT s.month, s.value
                       FROM snapshots s
                       JOIN fields f ON f.id = s.field_id
                       WHERE f.name = ?
                       ORDER BY s.month DESC
                       LIMIT ?""",
                    (field_name.lower(), months)
                ).fetchall()
            rows.reverse()
            return rows
        else:
            with sqlite3.connect(self.db_path) as conn:
                month_rows = conn.execute(
                    "SELECT DISTINCT month FROM snapshots ORDER BY month DESC LIMIT ?",
                    (months,)
                ).fetchall()
                month_list = sorted([r[0] for r in month_rows])

                if not month_list:
                    return ([], [], {})

                active_fields = self.get_active_fields()

                placeholders = ",".join("?" * len(month_list))
                snapshot_rows = conn.execute(
                    f"""SELECT f.name, s.month, s.value
                        FROM snapshots s
                        JOIN fields f ON f.id = s.field_id
                        WHERE f.deactivated_at IS NULL
                          AND s.month IN ({placeholders})""",
                    month_list
                ).fetchall()

            data = {}
            for field, month, value in snapshot_rows:
                data.setdefault(field, {})[month] = value

            return (month_list, active_fields, data)

    def get_full_history(self):
        """Return the complete recorded history across all active fields — every distinct
        month on record, not limited to a recent window. Same 3-tuple shape as
        get_history()'s all-fields form: (month_list, active_fields, data)."""
        with sqlite3.connect(self.db_path) as conn:
            month_rows = conn.execute(
                "SELECT DISTINCT month FROM snapshots ORDER BY month"
            ).fetchall()
            month_list = [r[0] for r in month_rows]

            if not month_list:
                return ([], [], {})

            active_fields = self.get_active_fields()

            placeholders = ",".join("?" * len(month_list))
            snapshot_rows = conn.execute(
                f"""SELECT f.name, s.month, s.value
                    FROM snapshots s
                    JOIN fields f ON f.id = s.field_id
                    WHERE f.deactivated_at IS NULL
                      AND s.month IN ({placeholders})""",
                month_list
            ).fetchall()

        data = {}
        for field, month, value in snapshot_rows:
            data.setdefault(field, {})[month] = value

        return (month_list, active_fields, data)

    def get_field_values(self, field_names: list[str]) -> dict[str, dict[str, float]]:
        """Return {field_name: {month: value}} from snapshots for the given fields.

        Names are matched case-insensitively and returned lower-cased. Empty input
        returns {} without querying.
        """
        if not field_names:
            return {}

        lowered = [name.lower() for name in field_names]
        placeholders = ",".join("?" * len(lowered))
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT f.name, s.month, s.value
                    FROM snapshots s
                    JOIN fields f ON f.id = s.field_id
                    WHERE f.name IN ({placeholders})""",
                lowered,
            ).fetchall()

        data: dict[str, dict[str, float]] = {}
        for field, month, value in rows:
            data.setdefault(field, {})[month] = value
        return data

    def get_values_for_month(self, month: str) -> dict[str, float]:
        """Return {field_name: value} for active fields at the given month.

        Returns {} when the month has no rows — callers distinguish missing data
        from zero by key absence, not by a sentinel value.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name, s.value
                   FROM snapshots s
                   JOIN fields f ON f.id = s.field_id
                   WHERE f.deactivated_at IS NULL
                     AND s.month = ?""",
                (month,),
            ).fetchall()

        return {field: value for field, value in rows}

    def get_value(self, field_name: str, month: str) -> float | None:
        """Return the snapshot value for one active field+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT s.value
                   FROM snapshots s
                   JOIN fields f ON f.id = s.field_id
                   WHERE f.deactivated_at IS NULL
                     AND f.name = ?
                     AND s.month = ?""",
                (field_name.lower(), month),
            ).fetchone()
        return float(row[0]) if row is not None else None

    def get_asset_value(self, field_name: str, month: str) -> float | None:
        """Return the debt asset snapshot for one active field+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT das.asset_value
                   FROM debt_asset_snapshots das
                   JOIN fields f ON f.id = das.field_id
                   WHERE f.deactivated_at IS NULL
                     AND f.name = ?
                     AND das.month = ?""",
                (field_name.lower(), month),
            ).fetchone()
        return float(row[0]) if row is not None else None

    def get_value_row(self, field_name: str, month: str) -> tuple[float, str] | None:
        """Return (value, recorded_at) for one active field+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT s.value, s.recorded_at
                   FROM snapshots s
                   JOIN fields f ON f.id = s.field_id
                   WHERE f.deactivated_at IS NULL
                     AND f.name = ?
                     AND s.month = ?""",
                (field_name.lower(), month),
            ).fetchone()
        return (float(row[0]), row[1]) if row is not None else None

    def get_asset_value_row(self, field_name: str, month: str) -> tuple[float, str] | None:
        """Return (asset_value, recorded_at) for one active field+month, or None if absent."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT das.asset_value, das.recorded_at
                   FROM debt_asset_snapshots das
                   JOIN fields f ON f.id = das.field_id
                   WHERE f.deactivated_at IS NULL
                     AND f.name = ?
                     AND das.month = ?""",
                (field_name.lower(), month),
            ).fetchone()
        return (float(row[0]), row[1]) if row is not None else None

    def get_latest_values(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name, c.name, c.unit, s.value, das.asset_value, f.id
                   FROM snapshots s
                   JOIN fields f     ON f.id = s.field_id
                   JOIN categories c ON c.id = f.category_id
                   LEFT JOIN debt_asset_snapshots das
                          ON das.field_id = s.field_id
                         AND das.month = (
                                 SELECT MAX(das2.month)
                                 FROM debt_asset_snapshots das2
                                 WHERE das2.field_id = s.field_id
                             )
                   WHERE f.deactivated_at IS NULL
                     AND s.month = (
                             SELECT MAX(s2.month)
                             FROM snapshots s2
                             WHERE s2.field_id = f.id
                         )
                   ORDER BY c.name, f.name"""
            ).fetchall()
            return rows

    def set_commodity(self, field_name: str, symbol: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                "SELECT id FROM fields WHERE name = ? AND deactivated_at IS NULL",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            field_id = row[0]
            conn.execute(
                """INSERT INTO commodity_prices (field_id, symbol)
                   VALUES (?, ?)
                   ON CONFLICT(field_id) DO UPDATE SET symbol = excluded.symbol""",
                (field_id, symbol.upper())
            )
            conn.commit()
            return True

    def remove_commodity(self, field_name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            row = conn.execute(
                "SELECT id FROM fields WHERE name = ?", (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            cursor = conn.execute(
                "DELETE FROM commodity_prices WHERE field_id = ?", (row[0],)
            )
            conn.commit()
            return cursor.rowcount == 1

    def set_commodity_override(self, field_name: str, price) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT cp.id FROM commodity_prices cp
                   JOIN fields f ON f.id = cp.field_id
                   WHERE f.name = ?""",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE commodity_prices SET override_price = ? WHERE id = ?",
                (price, row[0])
            )
            conn.commit()
            return True

    def set_commodity_cache(self, field_name: str, price: float, timestamp: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT cp.id FROM commodity_prices cp
                   JOIN fields f ON f.id = cp.field_id
                   WHERE f.name = ?""",
                (field_name.lower(),)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE commodity_prices SET cached_price = ?, cached_at = ? WHERE id = ?",
                (price, timestamp, row[0])
            )
            conn.commit()
            return True

    def get_commodity_fields(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.id, f.name, cp.symbol, cp.override_price, cp.cached_price, cp.cached_at
                   FROM commodity_prices cp
                   JOIN fields f ON f.id = cp.field_id
                   WHERE f.deactivated_at IS NULL"""
            ).fetchall()
            return rows

    def update_cached_price(self, field_id: int, price: float, timestamp: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE commodity_prices SET cached_price = ?, cached_at = ? WHERE field_id = ?",
                (price, timestamp, field_id)
            )
            conn.commit()
