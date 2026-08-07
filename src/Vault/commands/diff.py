from .base import BaseCommand
from ..helper import TABLE_COL_W, TABLE_NAME_W


class DiffCommand(BaseCommand):

    call_str = ["diff", "d"]

    USAGE = """
  diff <m1> <y1> <m2> <y2>      Compare all fields between two months
  diff <field> <m1> <y1> <m2> <y2>   Compare one field between two months
"""

    def entry_point(self, options: list):
        """Direct input to the correct sub-command based on argument count."""

        if len(options) == 4:
            self._diff_all_fields_over_months(
                options[0], options[1], options[2], options[3]
            )
        elif len(options) == 5:
            self._diff_field_over_months(
                options[0], options[1], options[2], options[3], options[4]
            )
        else:
            self.usage()

    ####################################
    # Sub-commands
    ####################################

    def _diff_all_fields_over_months(self, raw_m1, raw_y1, raw_m2, raw_y2):
        """`diff <m1> <y1> <m2> <y2>` — compare all active fields between two months."""
        month1, month2 = self._parse_month_pair(
            raw_m1, raw_y1, raw_m2, raw_y2
        )
        if month1 is None or month2 is None:
            return
        self._diff_all_fields(month1, month2)

    def _diff_field_over_months(self, field_name, raw_m1, raw_y1, raw_m2, raw_y2):
        """`diff <field> <m1> <y1> <m2> <y2>` — compare one field between two months."""
        if not self._is_a_field_name(field_name):
            print(f"Couldnt find any record for the value {field_name}")
            return
        month1, month2 = self._parse_month_pair(
            raw_m1, raw_y1, raw_m2, raw_y2
        )
        if month1 is None or month2 is None:
            return
        self._diff_single_field(field_name, month1, month2)
    def _parse_month_pair(self, raw_m1, raw_y1, raw_m2, raw_y2):
        month1 = self._parse_month_year(raw_m1, raw_y1)
        if month1 is None:
            print(
                "Invalid month/year in first pair: "
                f"'{raw_m1}' '{raw_y1}' (month must be 1-12, year 2 or 4 digits)"
            )
            return None, None

        month2 = self._parse_month_year(raw_m2, raw_y2)
        if month2 is None:
            print(
                "Invalid month/year in second pair: "
                f"'{raw_m2}' '{raw_y2}' (month must be 1-12, year 2 or 4 digits)"
            )
            return None, None

        return month1, month2

    ####################################
    # Rendering
    ####################################

    def _diff_all_fields(self, month1: str, month2: str):
        values1 = self.db.get_values_for_month(month1)
        values2 = self.db.get_values_for_month(month2)

        if not values1 and not values2:
            print(f"No data recorded for {month1} or {month2}.")
            return

        active_fields = self.db.get_active_fields()
        self._print_table(month1, month2, active_fields, values1, values2)

    def _diff_single_field(self, field_name: str, month1: str, month2: str):
        values1 = self.db.get_values_for_month(month1)
        values2 = self.db.get_values_for_month(month2)
        unit = self.db.get_field_unit(field_name)

        val1 = values1.get(field_name.lower())
        val2 = values2.get(field_name.lower())

        print(f"\n  Diff for '{field_name}':")
        print(f"  {'Month':<10}  {'Value':>17}  {'Delta':>17}")
        print("  " + "-" * 50)

        val1_str = self.format_value(val1, unit) if val1 is not None else "--"
        print(f"  {month1:<10}  {val1_str:>17}  {'--':>17}")

        val2_str = self.format_value(val2, unit) if val2 is not None else "--"
        if val1 is not None and val2 is not None:
            delta = val2 - val1
            sign = "+" if delta >= 0 else ""
            delta_str = f"{sign}{self.format_value(abs(delta), unit)}"
            color = self.GREEN if delta >= 0 else self.RED
            delta_str_color = self.cat_label(delta_str, color)
        else:
            delta_str_color = "--"
        print(f"  {month2:<10}  {val2_str:>17}  {delta_str_color:>17}")
        print()

    def _print_table(self, month1, month2, active_fields, values1, values2):
        """Per-record note marker, matching ShowCommand._print_table's grid exactly
        (same self.db.get_notes() source) -- the per-snapshot note added in show's
        single-field trend (step 19) has no equivalent here, since this grid has no
        natural place to attach a per-month marker to a specific cell."""
        notes = self.db.get_notes()
        any_noted = False

        header = f"\n  {'Field':<{TABLE_NAME_W}}  {month1:>{TABLE_COL_W}}  {month2:>{TABLE_COL_W}}  {'Delta':>{TABLE_COL_W}}"
        print(header)
        print("  " + "-" * (TABLE_NAME_W + (TABLE_COL_W + 2) * 3))

        current_cat = None
        for field_name, category_name, unit in active_fields:
            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name

            has_note = field_name in notes
            if has_note:
                any_noted = True
            label = self.note_label(field_name, has_note)

            val1 = values1.get(field_name)
            val2 = values2.get(field_name)

            cell1 = self.format_value(val1, unit) if val1 is not None else "--"
            cell2 = self.format_value(val2, unit) if val2 is not None else "--"

            if val1 is not None and val2 is not None:
                delta = val2 - val1
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}{self.format_value(abs(delta), unit)}"
                color = self.GREEN if delta >= 0 else self.RED
                delta_cell = self.cat_label(delta_str, color)
            else:
                delta_cell = "--"

            row = (
                f"  {label:<{TABLE_NAME_W}}  {cell1:>{TABLE_COL_W}}"
                f"  {cell2:>{TABLE_COL_W}}  {delta_cell:>{TABLE_COL_W}}"
            )
            print(row)
        if any_noted:
            print(f"  {self.NOTE_LEGEND}")
        print()
