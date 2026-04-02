import sqlite3
import datetime
from pathlib import Path


class DBHandler:

    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.db_path = base_dir / "vault.db"
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    unit TEXT NOT NULL DEFAULT '$'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fields (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT NOT NULL UNIQUE,
                    category_id    INTEGER NOT NULL REFERENCES categories(id),
                    created_at     TEXT NOT NULL,
                    deactivated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id    INTEGER NOT NULL REFERENCES fields(id),
                    month       TEXT NOT NULL,
                    value       REAL NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(field_id, month)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debt_asset_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id    INTEGER NOT NULL REFERENCES fields(id),
                    month       TEXT NOT NULL,
                    asset_value REAL NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(field_id, month)
                )
            """)
            self._migrate(conn)
            conn.commit()

    def _migrate(self, conn):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(categories)").fetchall()]
        if "unit" not in cols:
            conn.execute("ALTER TABLE categories ADD COLUMN unit TEXT NOT NULL DEFAULT '$'")
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

    def record_value(self, field_name: str, month: str, value: float) -> bool:
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
                """INSERT INTO snapshots (field_id, month, value, recorded_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(field_id, month)
                   DO UPDATE SET value = excluded.value,
                                 recorded_at = excluded.recorded_at""",
                (field_id, month, value, datetime.datetime.now().isoformat())
            )
            conn.commit()
            return True

    def record_asset_value(self, field_name: str, month: str, asset_value: float) -> bool:
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
            conn.execute(
                """INSERT INTO debt_asset_snapshots (field_id, month, asset_value, recorded_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(field_id, month)
                   DO UPDATE SET asset_value = excluded.asset_value,
                                 recorded_at = excluded.recorded_at""",
                (field_id, month, asset_value, datetime.datetime.now().isoformat())
            )
            conn.commit()
            return True

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

    def get_latest_values(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name, c.name, c.unit, s.value, das.asset_value
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
