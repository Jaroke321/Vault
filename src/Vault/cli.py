import datetime

from .prompt import Prompt
from .logger import Logger
from .db_handler import DBHandler
from .helper import *

def main():
    logger = Logger(log_file="logs/Vault.log")
    CLI(logger).run()


class CLI:
    """Implementation class for the Vault finance tracker. Records monthly financial
    snapshots across user-defined fields organized into categories."""

    def __init__(self, logger):
        self.logger = logger
        self.db = DBHandler()
        self.commits = []

        self.commands = {
            "field":   self.cmd_field,
            "update":  self.cmd_update,
            "commit":  self.commit,
            "show":    self.cmd_show,
            "summary": self.cmd_summary,
            "help":    self.cmd_help,
        }

    def run(self):
        print_banner()
        prompt = Prompt(project_name="Vault", logger=self.logger, state_data_viewer=self.commit_viewer, cmd_dict=self.commands)
        prompt.render()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def commit_viewer(self):

        for i, commit in enumerate(self.commits, start=1):
            print(cat_label(str(i), RED), end="")
            for val in commit:
                print(f" | {val}", end="")
            print(" | ")

    def cmd_field(self, options: list):
        if not options:
            print("Usage: field add <category> <name> | field remove <name> | field list")
            return

        sub = options[0]

        if sub == "add":
            if len(options) < 3:
                print("Usage: field add <category> <name>")
                return
            category, name = options[1], options[2]
            if " " in name or " " in category:
                print("Field and category names cannot contain spaces.")
                return
            success = self.db.add_field(name, category)
            if success:
                print(f"Field '{name}' added under category '{category}'.")
                self.logger.log(f"Field added: {name} (category: {category})")
            else:
                print(f"Field '{name}' already exists.")

        elif sub == "remove":
            if len(options) < 2:
                print("Usage: field remove <name>")
                return
            name = options[1]
            success = self.db.deactivate_field(name)
            if success:
                print(f"Field '{name}' deactivated. History is preserved.")
                self.logger.log(f"Field deactivated: {name}")
            else:
                print(f"No active field named '{name}' found.")

        elif sub == "list":
            fields = self.db.get_active_fields()
            if not fields:
                print("No active fields. Use 'field add <category> <name>' to add one.")
                return
            current_cat = None
            for field_name, category_name in fields:
                if category_name != current_cat:
                    print(f"\n  {cat_label(category_name)}")
                    current_cat = category_name
                print(f"    - {field_name}")
            print()

        else:
            print(f"Unknown subcommand '{sub}'. Use: add, remove, list")

    def cmd_update(self, options: list):

        current_month = datetime.datetime.now().strftime("%Y-%m")

        if not options:
            fields = self.db.get_active_fields()
            if not fields:
                print("No active fields to log. Use 'field add' first.")
                return
            print(f"Updating values for {current_month}. Press Enter to skip a field.")
            recorded = 0
            for field_name, category_name in fields:
                raw = input(f"  {category_name}/{field_name}: ").strip()
                if raw == "":
                    continue
                value = self._parse_float(raw)
                if value is None:
                    print(f"    Skipping '{field_name}': '{raw}' is not a valid number.")
                    continue
                self.db.record_value(field_name, current_month, value)
                self.commits.append([field_name, current_month, value])
                recorded += 1
                if category_name.lower() == "debt":
                    raw_asset = input(
                        f"    {field_name} asset value (press Enter to skip): "
                    ).strip()
                    if raw_asset != "":
                        asset_value = self._parse_float(raw_asset)
                        if asset_value is None:
                            print(f"    Skipping asset value for '{field_name}': '{raw_asset}' is not a valid number.")
                        else:
                            self.db.record_asset_value(field_name, current_month, asset_value)
                            self.commits.append([field_name, current_month, asset_value])
            print(f"Updated {recorded} value(s) for {current_month}.")
            self.logger.log(f"Interactive update: {recorded} value(s) recorded for {current_month}")

        elif len(options) >= 2:
            field_name, raw = options[0], options[1]
            value = self._parse_float(raw)
            if value is None:
                print(f"Invalid value '{raw}'. Must be a number.")
                return
            success = self.db.record_value(field_name, current_month, value)
            self.commits.append([field_name, current_month, value])
            if success:
                # print(f"Recorded {value:,.2f} for '{field_name}' ({current_month}).")
                self.logger.log(f"Recorded {value} for {field_name} ({current_month})")
            else:
                print(f"No active field named '{field_name}'. Use 'field list' to see active fields.")
                return
            if len(options) >= 3:
                asset_value = self._parse_float(options[2])
                if asset_value is None:
                    print(f"Invalid asset value '{options[2]}'. Must be a number.")
                else:
                    asset_success = self.db.record_asset_value(field_name, current_month, asset_value)
                    self.commits.append([field_name, current_month, asset_value])
                    if asset_success:
                        # print(f"Recorded asset value {asset_value:,.2f} for '{field_name}' ({current_month}).")
                        self.logger.log(f"Recorded asset value {asset_value} for {field_name} ({current_month})")
                    else:
                        print(f"Asset value not recorded: '{field_name}' is not an active debt field.")

        else:
            print("Usage: update | update <field_name> <value>")

    def commit(self, options: list):


        if not options: # user just typed `commit`, we will take this as a batch process
            self._commit_all()
            return

        unique_options = set(options)
        successful_commits = []

        for commit_str in unique_options:

            try:
                commit_num = int(commit_str)

                if(commit_num > 0 and commit_num < len(self.commits)):
                    current_commit = self.commits[commit_num-1]
                    # TODO: Figure out how to handle commits to db 
                    successful_commits.append(commit_num)
                    
            except ValueError:

                print(f"Invalid value given to the commit command, skipping.")

        # Remove from list everything we just commited
        for i in sorted(successful_commits, reverse=True):
            self.commits.pop(i)

    def cmd_show(self, options: list):

        num_months = 6     # default value for trend data

        if not options:    # User just said to show all data (i.e `show`)
            month_list, active_fields, data = self.db.get_history(months=num_months)
            if not month_list:
                print("No snapshots recorded yet.")
                return
            self._print_table(month_list, active_fields, data)

        elif len(options) == 1: # User either inputed a field name or a number ( i.e. show 12 || show debt )
            try:              # Cover case where user said `show {months}`
                num_months = int(options[0])
                month_list, active_fields, data = self.db.get_history(months=num_months)
                if not month_list:
                    print("No snapshots recorded yet.")
                    return
                self._print_table(month_list, active_fields, data)

            except ValueError: # Handle case where user said `show {field}`
                
                field_name = options[0]
                rows = self.db.get_history(field_name=field_name, months=num_months)
                if not rows:
                    print(f"No history found for field '{field_name}'.")
                    return
                self._print_field_trend(field_name, rows)

        elif len(options) == 2: # User entered in field and months i.e. `show debt 9`

            field_name = options[0]

            try:
                num_months = int(options[1])
            except ValueError:
                print(f"Invalid month count '{options[1]}'. Using 6.")

            rows = self.db.get_history(field_name=field_name, months=num_months)
            if not rows:
                print(f"No history found for field '{field_name}'.")
                return
            self._print_field_trend(field_name, rows)

        else:
            print(f"Too many options given to the show command.")

    def cmd_summary(self, options: list):
        rows = self.db.get_latest_values()
        if not rows:
            print("No data recorded yet.")
            return

        DEBT_CATEGORIES = {"debt"}

        assets = 0.0
        liabilities = 0.0
        current_cat = None

        print("\n  === Net Worth Summary ===")
        for field_name, category_name, value, asset_value in rows:
            if category_name != current_cat:
                print(f"\n  {cat_label(category_name)}")
                current_cat = category_name
            is_debt = category_name.lower() in DEBT_CATEGORIES

            if is_debt and asset_value is not None:
                equity = asset_value - value
                print(f"    {field_name:<20} balance:  ${value:>12,.2f}  (liability)")
                print(f"    {'':<20} value:    ${asset_value:>12,.2f}")
                print(f"    {'':<20} equity:   ${equity:>12,.2f}")
                liabilities += value
                assets      += asset_value
            elif is_debt:
                print(f"    {field_name:<20} ${value:>12,.2f}  (liability)")
                liabilities += value
            else:
                print(f"    {field_name:<20} ${value:>12,.2f}")
                assets += value
            

        net = assets - liabilities
        print(f"\n  {'Assets:':<20} ${assets:>12,.2f}")
        print(f"  {'Liabilities:':<20} ${liabilities:>12,.2f}")
        print(f"  {'Net Worth:':<20} ${net:>12,.2f}")
        print()
        self.logger.log(f"Summary viewed: assets={assets:.2f}, liabilities={liabilities:.2f}, net={net:.2f}")

    def cmd_help(self, options: list):
        print("""
  Vault Commands:
    field add <category> <name>   Register a new tracked field
    field remove <name>           Deactivate a field (history preserved)
    field list                    Show all active fields by category

    update                        Interactively update all fields for this month
    update <field> <value>        Update a single field value for this month

    commit                        Commit all pending updates
    commit <n> [n ...]            Commit one or more pending updates by index

    show                          Table of last 6 months across all fields
    show <n>                      Table of last N months across all fields
    show <field>                  Month-over-month trend for one field
    show <field> <n>              Trend for one field over last N months

    summary                       Net worth snapshot (assets minus debts)

    help                          Show this help message
    exit / quit / q               Exit Vault
        """)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_float(self, raw: str):
        try:
            cleaned = raw.replace("$", "").replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            return None

    def _print_table(self, month_list, active_fields, data):
        COL_W = 14
        NAME_W = 22

        header = f"\n  {'Field':<{NAME_W}}"
        for month in month_list:
            header += f"  {month:>{COL_W}}"
        print(header)
        print("  " + "-" * (NAME_W + (COL_W + 2) * len(month_list)))

        current_cat = None
        for field_name, category_name in active_fields:
            if category_name != current_cat:
                print(f"\n  {cat_label(category_name)}")
                current_cat = category_name
            row = f"  {field_name:<{NAME_W}}"
            for month in month_list:
                val = data.get(field_name, {}).get(month)
                cell = f"${val:,.2f}" if val is not None else "--"
                row += f"  {cell:>{COL_W}}"
            print(row)
        print()

    def _print_field_trend(self, field_name, rows):
        print(f"\n  Trend for '{field_name}':")
        print(f"  {'Month':<10}  {'Value':>14}  {'Delta':>14}")
        print("  " + "-" * 44)

        prev_value = None
        for month, value in rows:
            if prev_value is None:
                delta_str = "--"
            else:
                delta = value - prev_value
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}${delta:,.2f}"
                color = GREEN if delta >= 0 else RED
                delta_str_color = cat_label(delta_str, color)
            print(f"  {month:<10}  ${value:>13,.2f}  {delta_str_color:>14}")
            prev_value = value
        print()

    def _commit_all(self):

        for current_commit in self.commits:
            # TODO: Commit the current commit
            pass

        self.commits.clear()


if __name__ == "__main__":
    main()
