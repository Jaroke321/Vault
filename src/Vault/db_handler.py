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
                    name TEXT NOT NULL UNIQUE
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

    def get_active_fields(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.name, c.name
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
                """SELECT f.name, c.name, s.value
                   FROM snapshots s
                   JOIN fields f ON f.id = s.field_id
                   JOIN categories c ON c.id = f.category_id
                   WHERE f.deactivated_at IS NULL
                     AND s.month = (
                         SELECT MAX(s2.month)
                         FROM snapshots s2
                         WHERE s2.field_id = f.id
                     )
                   ORDER BY c.name, f.name"""
            ).fetchall()
            return rows
