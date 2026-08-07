from .base import BaseCommand
from ..helper import DEFAULT_HISTORY_MONTHS, TABLE_COL_W, TABLE_NAME_W, visible_len
from ..theme import DEFAULT

class ShowCommand(BaseCommand):

    call_str = ["show", "s"] # Tells the prompt the string command(s) in order to call this class

    USAGE = """
  show / s                      Table of last 6 months across all fields
  show <n>                      Table of last N months across all fields
  show <field>                  Month-over-month trend for one field
  show <field> <n>              Trend for one field over last N months
"""

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        if not options:
            self._show_history()
        elif len(options) == 1:
            self._show_single_arg(options[0])
        elif len(options) == 2:
            self._show_field_over_months(options[0], options[1])
        else:
            print("Too many options given to the show command.")

    ####################################
    # Sub-commands
    ####################################
    def _show_history(self, num_months: int = DEFAULT_HISTORY_MONTHS):
        """`show` | `show <n>` — table of the last N months across all fields."""
        month_list, active_fields, data = self.db.get_history(months=num_months)
        if not month_list:
            print("No snapshots recorded yet.")
            return
        self._print_table(month_list, active_fields, data)

    def _show_single_arg(self, raw: str):
        """`show <n>` | `show <field>` | `show <category>` — dispatch on what the argument looks like."""
        num_months = self._parse_int(raw)

        if num_months:
            self._show_history(num_months)
        elif self._is_a_field_name(raw):
            self._show_field_trend(raw)
        elif self._is_a_category_name(raw):
            self._show_category_trend(raw)
        else:
            print(f"Couldnt find any record for the value {raw}")

    def _show_field_over_months(self, field_name: str, raw_months: str):
        """`show <field> <n>` — trend for one field over the last N months."""
        num_months = self._parse_int(raw_months)
        if num_months:
            self._show_field_trend(field_name, num_months)

    def _show_field_trend(self, field_name: str, num_months: int = DEFAULT_HISTORY_MONTHS):
        rows = self.db.get_history(field_name=field_name, months=num_months)
        if not rows:
            print(f"No history found for field '{field_name}'.")
            return
        unit = self.db.get_field_unit(field_name)
        note = self.db.get_note(field_name)
        apr = self.db.get_field_apr(field_name)
        self._print_field_trend(field_name, rows, unit, note, apr)

    def _show_category_trend(self, cat_name: str, num_months: int = DEFAULT_HISTORY_MONTHS):
        field_list = self.db.get_fields_by_category(category_name=cat_name)
        for field in field_list:
            self._show_field_trend(field, num_months)

    ####################################
    # Rendering
    ####################################
    def _print_table(self, month_list, active_fields, data):
        notes = self.db.get_notes()
        any_noted = False

        header = f"\n  {'Field':<{TABLE_NAME_W}}"
        for month in month_list:
            header += f"  {month:>{TABLE_COL_W}}"
        print(header)
        print("  " + "-" * (TABLE_NAME_W + (TABLE_COL_W + 2) * len(month_list)))

        current_cat = None
        for field_name, category_name, unit in active_fields:
            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name
            has_note = field_name in notes
            if has_note:
                any_noted = True
            label = self.note_label(field_name, has_note)
            row = f"  {label:<{TABLE_NAME_W}}"
            for month in month_list:
                val = data.get(field_name, {}).get(month)
                cell = self.format_value(val, unit) if val is not None else "--"
                row += f"  {cell:>{TABLE_COL_W}}"
            print(row)
        if any_noted:
            print(f"  {self.NOTE_LEGEND}")
        print()

    def _print_field_trend(
        self,
        field_name,
        rows,
        unit: str = "$",
        note: str | None = None,
        apr: float | None = None,
    ):
        """rows are (month, value, contribution, snapshot_note) -- see
        DBHandler.get_history(). `note` here is the per-RECORD note (fields.note,
        shown once above); `snapshot_note` on each row is per-MONTH and rendered
        as a marker + legend, the same convention _print_table uses for record
        notes -- distinct data, same visual language."""
        print(f"\n  Trend for '{field_name}':")
        if note is not None:
            print(f"  Note: {note}")
        if apr is not None:
            print(f"  APR: {apr:.2f}%")

        values = [value for _, value, _, _ in rows]
        color = DEFAULT.positive.ansi if values[-1] >= values[0] else DEFAULT.negative.ansi
        print(f"  {self.cat_label(self.sparkline(values), color)}")

        show_contribution = any(contribution is not None for _, _, contribution, _ in rows)
        any_snapshot_note = any(snapshot_note is not None for _, _, _, snapshot_note in rows)

        header = f"  {'Month':<10}  {'Value':>17}  {'Delta':>17}"
        sep_width = 50
        if show_contribution:
            header += f"  {'Contribution':>14}"
            sep_width += 16
        print(header)
        print("  " + "-" * sep_width)

        prev_value = None
        for month, value, contribution, snapshot_note in rows:
            val_str = self.format_value(value, unit)
            if prev_value is None:
                delta_str_color = "--"
            else:
                delta = value - prev_value
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}{self.format_value(abs(delta), unit)}"
                color = DEFAULT.positive.ansi if delta >= 0 else DEFAULT.negative.ansi
                delta_str_color = self.cat_label(delta_str, color)
            delta_pad = " " * max(17 - visible_len(delta_str_color), 0)
            month_label = self.note_label(month, snapshot_note is not None)
            row = f"  {month_label:<10}  {val_str:>17}  {delta_pad}{delta_str_color}"
            if show_contribution:
                contrib_str = self.format_value(contribution, "$") if contribution is not None else "--"
                row += f"  {contrib_str:>14}"
            print(row)
            prev_value = value
        if any_snapshot_note:
            print(f"  {self.NOTE_LEGEND}")
        print()
