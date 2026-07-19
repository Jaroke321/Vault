from .base import BaseCommand

class ShowCommand(BaseCommand):

    call_str = ["show", "s"] # Tells the prompt the string command(s) in order to call this class

    DEFAULT_MONTHS = 6

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
    def _show_history(self, num_months: int = DEFAULT_MONTHS):
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

    def _show_field_trend(self, field_name: str, num_months: int = DEFAULT_MONTHS):
        rows = self.db.get_history(field_name=field_name, months=num_months)
        if not rows:
            print(f"No history found for field '{field_name}'.")
            return
        unit = self.db.get_field_unit(field_name)
        self._print_field_trend(field_name, rows, unit)

    def _show_category_trend(self, cat_name: str, num_months: int = DEFAULT_MONTHS):
        field_list = self.db.get_fields_by_category(category_name=cat_name)
        for field in field_list:
            self._show_field_trend(field, num_months)

    ####################################
    # Rendering
    ####################################
    def _print_table(self, month_list, active_fields, data):
        COL_W = 14
        NAME_W = 22

        header = f"\n  {'Field':<{NAME_W}}"
        for month in month_list:
            header += f"  {month:>{COL_W}}"
        print(header)
        print("  " + "-" * (NAME_W + (COL_W + 2) * len(month_list)))

        current_cat = None
        for field_name, category_name, unit in active_fields:
            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name
            row = f"  {field_name:<{NAME_W}}"
            for month in month_list:
                val = data.get(field_name, {}).get(month)
                cell = self.format_value(val, unit) if val is not None else "--"
                row += f"  {cell:>{COL_W}}"
            print(row)
        print()

    def _print_field_trend(self, field_name, rows, unit: str = "$"):
        print(f"\n  Trend for '{field_name}':")

        values = [value for _, value in rows]
        color = self.GREEN if values[-1] >= values[0] else self.RED
        print(f"  {self.cat_label(self.sparkline(values), color)}")

        print(f"  {'Month':<10}  {'Value':>17}  {'Delta':>17}")
        print("  " + "-" * 50)

        prev_value = None
        for month, value in rows:
            val_str = self.format_value(value, unit)
            if prev_value is None:
                delta_str_color = "--"
            else:
                delta = value - prev_value
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}{self.format_value(abs(delta), unit)}"
                color = self.GREEN if delta >= 0 else self.RED
                delta_str_color = self.cat_label(delta_str, color)
            print(f"  {month:<10}  {val_str:>17}  {delta_str_color:>17}")
            prev_value = value
        print()
