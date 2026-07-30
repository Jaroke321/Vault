import csv
from pathlib import Path

from .base import BaseCommand
from ..data_types import CATEGORIES


class ImportCommand(BaseCommand):

    call_str = "import"

    USAGE = """
  import csv <filename>         Import a wide-format CSV back into the database
"""

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
        columns, data_rows, header_notes = parsed

        # Auto-create fields from the header (modern CSV only). Investment columns
        # never reach here — _parse_header already filters them out, since a CSV has
        # no way to carry the symbol a fresh investment record needs.
        for field_name, category, _ in columns:
            if category is not None:
                self.db.add_field(field_name, category)

        field_names = [name for name, _, _ in columns]
        existing = self.db.get_field_values(field_names)

        overwrite_count = 0
        for row in data_rows:
            if not row:
                continue
            month = row[0]
            values = row[1:]
            for field_name, _, col_idx in columns:
                if col_idx >= len(values):
                    continue
                cell = values[col_idx]
                if cell == "":
                    continue
                if self._parse_float(cell) is None:
                    continue
                if field_name in existing and month in existing[field_name]:
                    overwrite_count += 1

        if overwrite_count and not self._confirm(
            f"Import will stage {overwrite_count} cell(s) that overwrite existing values. Continue?"
        ):
            print("Import cancelled.")
            return

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
                    self.commits.append([field_name, month, value])
                    staged += 1

        skipped = skipped_empty + skipped_invalid
        print(
            f"Imported '{filename}': {committed} new values committed, "
            f"{staged} staged for review, {skipped} skipped."
        )
        for note in header_notes:
            print(note)
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

        Returns (columns, data_rows, header_notes) or None on a hard error.
        columns is [(field_name, category_or_None, col_index), ...] where col_index
        is the 0-based position in the value portion of each data row. category is
        only set for modern (has-category-row) CSVs; legacy columns match an
        already-active field and carry None.

        Investment columns are always skipped, in both CSV forms: a CSV has no way
        to carry the symbol a fresh investment record needs, and value-only export
        never distinguished a quantity from a plain value in the first place — so
        there's no reliable way back in for that category (value-only round-trip).
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
        header_notes = []
        columns = []

        if has_category_row:
            cats = list(categories) + [None] * max(0, len(field_names) - len(categories))
            for i, name in enumerate(field_names):
                category = cats[i]
                if category is not None and not self._is_a_category_name(category):
                    header_notes.append(
                        f"[ERROR] Unknown category '{category}' for column '{name}'; column skipped."
                    )
                elif category is not None and CATEGORIES[category].is_priced:
                    header_notes.append(
                        f"[WARN] Skipped column '{name}': priced records (e.g. investment) need a "
                        "symbol (set via 'field add'), which a CSV can't carry."
                    )
                else:
                    columns.append((name, category, i))
        else:
            for i, name in enumerate(field_names):
                if not self._is_a_field_name(name):
                    header_notes.append(
                        f"[ERROR] Unknown field '{name}' in legacy CSV "
                        f"(no category row to auto-create); column skipped."
                    )
                elif CATEGORIES[self.db.get_field_category(name)].is_priced:
                    header_notes.append(
                        f"[WARN] Skipped column '{name}': priced records (e.g. investment) need a "
                        "symbol, which a CSV can't carry."
                    )
                else:
                    columns.append((name, None, i))

        return columns, data_rows, header_notes
