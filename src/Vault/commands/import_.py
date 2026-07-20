import csv
from pathlib import Path

from .base import BaseCommand


class ImportCommand(BaseCommand):

    call_str = "import"
    mutates_commits = True

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        if not options:
            self.usage()
            return

        sub = options[0]
        if sub in self.sub_commands:
            self.sub_commands[sub](options[1:])
        else:
            print(f"Unknown subcommand '{sub}'. Use: csv")

    def usage(self):
        print("Usage: import csv <filename>")

    ####################################
    # Sub-commands
    ####################################
    def sub_csv(self, options: list):
        """`import csv <filename>` — read a wide-format CSV (export shape) back into
        the database. New field/month values commit immediately; cells that would
        overwrite an existing value are staged for review via show/commit."""

        if not options:
            self.usage()
            return

        filename = options[0]
        path = Path(filename)
        if not path.is_file():
            print(f"[ERROR] File not found: '{filename}'")
            return

        try:
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        except OSError as e:
            print(f"[ERROR] Could not read '{filename}': {e}")
            return

        if not rows:
            print(f"[ERROR] File is empty: '{filename}'")
            return

        parsed = self._parse_header(rows)
        if parsed is None:
            return
        columns, data_rows, legacy_errors = parsed

        # Auto-create fields/categories from the header (modern CSV only).
        for field_name, category, _ in columns:
            if category is not None:
                self.db.add_field(field_name, category)

        field_names = [name for name, _, _ in columns]
        existing = self.db.get_field_values(field_names)

        committed = 0
        staged = 0
        skipped_empty = 0
        skipped_invalid = 0
        warnings = []

        for row in data_rows:
            if not row:
                continue
            month = row[0]
            values = row[1:]
            for field_name, _, col_idx in columns:
                if col_idx >= len(values):
                    skipped_empty += 1
                    continue
                cell = values[col_idx]
                if cell == "":
                    skipped_empty += 1
                    continue
                value = self._parse_float(cell)
                if value is None:
                    skipped_invalid += 1
                    warnings.append(
                        f"[WARN] Skipped invalid value at {month}/{field_name}: '{cell}'"
                    )
                    continue

                if field_name not in existing or month not in existing[field_name]:
                    self.db.record_value(field_name, month, value)
                    committed += 1
                else:
                    self.commits.append([field_name, month, value, "value"])
                    staged += 1

        skipped = skipped_empty + skipped_invalid
        print(
            f"Imported '{filename}': {committed} new values committed, "
            f"{staged} staged for review, {skipped} skipped."
        )
        for err in legacy_errors:
            print(err)
        for warn in warnings:
            print(warn)

        self.logger.log(
            f"CSV imported from {filename}: {committed} committed, "
            f"{staged} staged, {skipped} skipped"
        )

    ####################################
    # Helpers
    ####################################
    def _parse_header(self, rows: list):
        """Parse category/field header rows.

        Returns (columns, data_rows, legacy_errors) or None on a hard error.
        columns is [(field_name, category_or_None, col_index), ...] where col_index
        is the 0-based position in the value portion of each data row.
        """

        row0 = rows[0]
        if not row0:
            print("[ERROR] CSV header row is empty.")
            return None

        has_category_row = row0[0].lower() == "category"
        if has_category_row:
            categories = [c.lower() for c in row0[1:]]
            if len(rows) < 2:
                print("[ERROR] CSV is missing the field-name header row.")
                return None
            header = rows[1]
            data_rows = rows[2:]
        else:
            categories = None
            header = row0
            data_rows = rows[1:]

        if not header or header[0].lower() != "month":
            print("[ERROR] Expected a 'month' header row (got "
                  f"'{header[0] if header else ''}')")
            return None

        field_names = [name.lower() for name in header[1:]]
        legacy_errors = []
        columns = []

        if has_category_row:
            cats = list(categories) + [None] * max(0, len(field_names) - len(categories))
            for i, name in enumerate(field_names):
                columns.append((name, cats[i], i))
        else:
            for i, name in enumerate(field_names):
                if self._is_a_field_name(name):
                    columns.append((name, None, i))
                else:
                    legacy_errors.append(
                        f"[ERROR] Unknown field '{name}' in legacy CSV "
                        f"(no category row to auto-create); column skipped."
                    )

        return columns, data_rows, legacy_errors
