import csv
import sys

from .base import BaseCommand

class ExportCommand(BaseCommand):

    call_str = "export" # Tells the prompt the string command in order to call this class

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        # Error handling
        if not options:
            self.usage()
            return

        # Business logic
        sub = options[0]
        if sub in self.sub_commands:
            self.sub_commands[sub](options[1:])
        else:
            print(f"Unknown subcommand '{sub}'. Use: csv")

    def usage(self):
        print("Usage: export csv [filename]")

    ####################################
    # Sub-commands
    ####################################
    def sub_csv(self, options: list):
        """`export csv` | `export csv <filename>` — dump full recorded history to CSV,
        one row per month and one column per active field. stdout if no filename is
        given, otherwise written to that file."""

        month_list, active_fields, data = self.db.get_full_history()
        if not month_list:
            print("No snapshots recorded yet.")
            return

        filename = options[0] if options else None
        rows = self._build_rows(month_list, active_fields, data)

        if filename is None:
            writer = csv.writer(sys.stdout)
            writer.writerows(rows)
        else:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            print(f"History exported to '{filename}'.")
            self.logger.log(f"History exported to CSV: {filename}")

    ####################################
    # Helpers
    ####################################
    def _build_rows(self, month_list, active_fields, data) -> list:
        category_row = ["category"] + [category for _, category, _ in active_fields]
        header = ["month"] + [name for name, _, _ in active_fields]
        rows = [category_row, header]
        for month in month_list:
            row = [month]
            for field_name, _, _ in active_fields:
                row.append(data.get(field_name, {}).get(month, ""))
            rows.append(row)
        return rows
