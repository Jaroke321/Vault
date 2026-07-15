import argparse
import datetime
import time
from pathlib import Path
from rich.progress import track

# Extra imports of useful things
from .prompt import Prompt
from .logger import Logger
from .db_handler import DBHandler
from .price_fetcher import PriceFetcher
from .helper import *

# Command classes
from .commands import FieldCommand, UpdateCommand, CommitCommand

def main():
    parser = argparse.ArgumentParser(prog="vault")
    parser.add_argument("--test", action="store_true", help="Launch interactive test mode with in-memory dummy data")
    args = parser.parse_args()

    logger = Logger(log_file="logs/Vault.log")

    if args.test:
        import os, tempfile
        from .test_data import seed_test_db
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        tmp_path = Path(tmp.name)
        try:
            db = DBHandler(db_path=tmp_path)
            seed_test_db(db)
            CLI(logger, db, price_fetcher=None, test_mode=True).run()
        finally:
            os.unlink(tmp_path)
    else:
        db = DBHandler()
        fetcher = PriceFetcher(db, logger)
        fetcher.fetch_all()
        CLI(logger, db, fetcher).run()


class CLI:
    """Implementation class for the Vault finance tracker. Records monthly financial
    snapshots across user-defined fields organized into categories."""

    def __init__(self, logger, db=None, price_fetcher=None, test_mode=False):

        self.logger = logger
        self.db = db if db is not None else DBHandler()
        self.price_fetcher = price_fetcher
        self.test_mode = test_mode
        self.project_name = "[TEST] Vault" if test_mode else "Vault"
        self.commits = []
        self.need_print = True

        # Need to init classes before using
        command_class_list = [ FieldCommand, UpdateCommand, CommitCommand]
        self.command_classes = self.load_command_classes(command_class_list)

        # Handle any command calls available to the user that is not in its own command class
        # This will allow the user to call the key value and the prompt will then pass any options
        # to the function tied to that command
        self.commands = {
            "show":      self.cmd_show,
            "summary":   self.cmd_summary,
            "commodity": self.cmd_commodity,
            "help":      self.cmd_help,
        }

        # add command class entry points to the commands list
        self.commands |= self.command_classes

    def run(self):
        print_banner()
        if self.test_mode:
            print(f"{BOLD}{YELLOW}  *** TEST MODE — in-memory database, no changes will be saved ***{RESET}\n")
        prompt = Prompt(project_name=self.project_name, logger=self.logger, state_data_viewer=self.commit_viewer, cmd_dict=self.commands)
        prompt.render()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def load_command_classes(self, command_class_list: list) -> dict:

        commands = {}

        for cls in command_class_list:
            instance = cls(self.db, self.logger, self.price_fetcher, self.commits)
            commands.update(instance.init_command())

        return commands


    def commit_viewer(self):
        if not self.commits or self.need_print == False:
            self.need_print = True
            return

        headers = ["#", "Field", "Month", "Value"]
        rows = [[str(i), c[0], c[1], str(c[2])] for i, c in enumerate(self.commits, start=1)]

        widths = [len(h) for h in headers]
        for row in rows:
            for j, cell in enumerate(row):
                widths[j] = max(widths[j], len(cell))

        fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
        sep = "  " + "  ".join("-" * w for w in widths)

        print(fmt.format(*headers))
        print(sep)
        for row in rows:
            line = fmt.format(*row)
            colored_num = f"{BOLD}{MAGENTA}{row[0]}{RESET}"
            line = line.replace(row[0], colored_num, 1)
            print(line)

    def cmd_show(self, options: list):
        self.need_print = False

        num_months = 6     # default value for trend data

        if not options:    # User just said to show all data (i.e `show`)
            month_list, active_fields, data = self.db.get_history(months=num_months)
            if not month_list:
                print("No snapshots recorded yet.")
                return
            self._print_table(month_list, active_fields, data)

        elif len(options) == 1: # User either inputed a field / category name or a number ( i.e. show 12 || show savings )
            # Cover case where user is inputing months
            num_months = self._parse_int(options[0])
            if num_months:

                month_list, active_fields, data = self.db.get_history(months=num_months)
                if month_list:
                    self._print_table(month_list, active_fields, data)

            elif self._is_a_field_name(options[0]):   
                # Try case where user is looking for a field or category
                field_name = options[0]
                num_months = 6
                rows = self.db.get_history(field_name=field_name, months=num_months)
                unit = self.db.get_field_unit(field_name)
                self._print_field_trend(field_name, rows, unit)

            elif self._is_a_category_name(options[0]):
                # try case where user is inputing an entire category
                cat_name = options[0]
                num_months = 6
                field_list = self.db.get_fields_by_category(category_name=cat_name)

                for field in field_list:
                    rows = self.db.get_history(field_name=field, months=num_months)
                    unit = self.db.get_field_unit(field)
                    self._print_field_trend(field, rows, unit)

            else:
                print(f"Couldnt find any record for the value {options[0]}")

        elif len(options) == 2: # User entered in field and months i.e. `show debt 9`

            field_name = options[0]

            num_months = self._parse_int(options[1])
            if num_months:

                rows = self.db.get_history(field_name=field_name, months=num_months)
                if not rows:
                    print(f"No history found for field '{field_name}'.")
                    return
                unit = self.db.get_field_unit(field_name)
                self._print_field_trend(field_name, rows, unit)

        else:
            print(f"Too many options given to the show command.")

    def cmd_summary(self, options: list):
        self.need_print = False

        rows = self.db.get_latest_values()
        if not rows:
            print("No data recorded yet.")
            return

        DEBT_CATEGORIES = {"debt"}
        MONETARY_UNITS = {"$", "€", "£", "¥"}

        assets = 0.0
        liabilities = 0.0
        current_cat = None

        print("\n  === Net Worth Summary ===")

        for field_name, category_name, unit, value, asset_value, field_id in rows:

            if category_name != current_cat:
                print(f"\n  {cat_label(category_name)}")
                current_cat = category_name
                
            is_debt = category_name.lower() in DEBT_CATEGORIES
            is_monetary = unit in MONETARY_UNITS

            if is_debt and asset_value is not None:
                equity = asset_value - value
                liabilities += value
                assets      += asset_value
                print(f"    {field_name:<20} balance:  {format_value(value, unit):>16}  (liability)")
                print(f"    {'':<20} value:    {format_value(asset_value, unit):>16}")
                print(f"    {'':<20} equity:   {format_value(equity, unit):>16}")

            elif is_debt:
                print(f"    {field_name:<20} {format_value(value, unit):>16}  (liability)")
                liabilities += value
                    
            elif is_monetary:
                print(f"    {field_name:<20} {format_value(value, unit):>16}")
                assets += value

            elif self.price_fetcher is not None:
                price = self.price_fetcher.get_price(field_id)

                if price is not None:
                    usd_equiv = value * price
                    assets += usd_equiv
                    print(f"    {field_name:<20} {format_value(value, unit):>10} ~ {format_value(usd_equiv, '$'):>12} (@{format_value(price, '$')}/{unit})")

                else:
                    print(f"    {field_name:<20} {format_value(value, unit):>10} (no price)")


            else:
                print(f"    {field_name:<20} {format_value(value, unit):>16}")
            
        net = assets - liabilities
        print(f"\n  {'Assets:':<20} ${assets:>12,.2f}")
        print(f"  {'Liabilities:':<20} ${liabilities:>12,.2f}")
        print(f"  {'Net Worth:':<20} ${net:>12,.2f}")
        print()
        self.logger.log(f"Summary viewed: assets={assets:.2f}, liabilities={liabilities:.2f}, net={net:.2f}")

    def cmd_commodity(self, options: list):
        self.need_print = False

        # TODO: Need to refactor this function. It is looking haggard

        if not options:
            print("Usage: commodity tag <field> <commodity> | commodity untag <field> | commodity override <field> <price>|clear | commodity list | commodity refresh")
            return

        sub = options[0]

        if sub == "tag":
            if len(options) < 3:
                # print("Usage: commodity tag <field> <commodity>")
                # print(f"  Names:   {', '.join(sorted(PriceFetcher.NAME_TO_SYMBOL.keys()))}")
                # print(f"  Symbols: {', '.join(sorted(PriceFetcher.SYMBOL_TO_TICKER.keys()))}")

                # TODO:
                # Need to think about how to apply a commodity to an entire category
                # This will be useful for the user and can avoid the awkward command of
                # commodity tag gold gold
                # instead the user should be able to type in commodity tag metals
                # and if metals is a category in storage
                # We will attempt to commodify all of them



                return
            field_name = options[1]
            symbol = PriceFetcher.resolve_symbol(options[2])
            if symbol is None:
                print(f"Unknown commodity '{options[2]}'.")
                print(f"  Names:   {', '.join(sorted(PriceFetcher.NAME_TO_SYMBOL.keys()))}")
                print(f"  Symbols: {', '.join(sorted(PriceFetcher.SYMBOL_TO_TICKER.keys()))}")
                return
            success = self.db.set_commodity(field_name, symbol)
            if success:
                print(f"Field '{field_name}' tagged as {symbol}.")
                self.logger.log(f"Commodity tag set: {field_name} -> {symbol}")
            else:
                print(f"No active field named '{field_name}'.")

        elif sub == "untag":
            if len(options) < 2:
                print("Usage: commodity untag <field>")
                return
            success = self.db.remove_commodity(options[1])
            if success:
                print(f"Commodity tag removed from '{options[1]}'.")
            else:
                print(f"No commodity tag found for '{options[1]}'.")

        elif sub == "override":
            if len(options) < 3:
                print("Usage: commodity override <field> <price> | commodity override <field> clear")
                return
            field_name, raw = options[1], options[2]
            if raw.lower() == "clear":
                price = None
            else:
                price = self._parse_float(raw)
                if price is None:
                    print(f"Invalid price '{raw}'. Must be a number or 'clear'.")
                    return
            success = self.db.set_commodity_override(field_name, price)
            if success:
                if price is None:
                    print(f"Override cleared for '{field_name}'. Using live/cached price.")
                else:
                    print(f"Override price set for '{field_name}': {format_value(price, '$')}/unit.")
                self.logger.log(f"Commodity override set: {field_name} -> {price}")
            else:
                print(f"No commodity tag found for '{field_name}'. Use 'commodity tag' first.")

        elif sub == "list":
            if self.price_fetcher is None:
                print("Price fetcher not available.")
                return
            status_rows = self.price_fetcher.get_fetch_status()
            if not status_rows:
                print("No commodity-tagged fields. Use 'commodity tag <field> <symbol>' to add one.")
                return
            print(f"\n  {'Field':<20}  {'Symbol':<6}  {'Price':>12}  {'Source':<12}  {'Cached At'}")
            print("  " + "-" * 72)
            for field_name, symbol, price, source, cached_at in status_rows:
                price_str = format_value(price, '$') if price is not None else "N/A"
                age_str = cached_at[:19] if cached_at else "never"
                print(f"  {field_name:<20}  {symbol:<6}  {price_str:>12}  {source:<12}  {age_str}")
            print()

        elif sub == "refresh":
            if self.price_fetcher is None:
                print("Price fetcher not available.")
                return
            print("Refreshing commodity prices...")
            fetched = self.price_fetcher.fetch_all()
            if fetched:
                for sym, price in sorted(fetched.items()):
                    print(f"  {sym}: {format_value(price, '$')}")
            else:
                print("  No prices fetched (no tagged fields or fetch failed).")

        else:
            print(f"Unknown subcommand '{sub}'. Use: tag, untag, override, list, refresh")

    def cmd_help(self, options: list):
        self.need_print = False

        print("""
  Vault Commands:
    field add <category> <name>          Register a new tracked field
    field remove <name>                  Deactivate a field (history preserved)
    field list                           Show all active fields by category
    field set <category> unit <unit>     Set display unit for a category (default: $)

    update                               Interactively stage values for all fields this month
    update <field> <value>               Stage a value for a single field
    update <field> <value> <asset>       Stage a value + asset value for a debt field

    commit                        Commit all pending staged updates to the database
    commit <n> [n ...]            Commit one or more pending updates by index

    show                          Table of last 6 months across all fields
    show <n>                      Table of last N months across all fields
    show <field>                  Month-over-month trend for one field
    show <field> <n>              Trend for one field over last N months

    summary                       Net worth snapshot (assets minus debts)

    commodity tag <field> <commodity>     Tag a field as a commodity (e.g. 'gold' or 'XAU')
    commodity untag <field>               Remove commodity tag from a field
    commodity override <field> <price>    Lock a manual price per unit for this field
    commodity override <field> clear      Remove price lock (use live/cached price)
    commodity list                        Show all tagged fields with current prices and source
    commodity refresh                     Re-fetch live prices for all tagged fields

    help                          Show this help message
    exit / quit / q               Exit Vault
        """)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_int(self, raw:str):
        try:
            cleaned = raw.replace("$", "").replace(",", "").strip()
            return int(cleaned)
        except ValueError:
            return None

    def _parse_float(self, raw: str):
        try:
            cleaned = raw.replace("$", "").replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            return None
        
    def _is_a_field_name(self, raw: str):
        all_fields = [f for f, c, u in self.db.get_active_fields()]

        if raw.lower() in all_fields:
            return True
        return False

    def _is_a_category_name(self, raw: str):
        all_cats = self.db.get_categories()

        if raw.lower() in all_cats:
            return True
        return False

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
                print(f"\n  {cat_label(category_name)}")
                current_cat = category_name
            row = f"  {field_name:<{NAME_W}}"
            for month in month_list:
                val = data.get(field_name, {}).get(month)
                cell = format_value(val, unit) if val is not None else "--"
                row += f"  {cell:>{COL_W}}"
            print(row)
        print()

    def _print_field_trend(self, field_name, rows, unit: str = "$"):
        print(f"\n  Trend for '{field_name}':")
        print(f"  {'Month':<10}  {'Value':>17}  {'Delta':>17}")
        print("  " + "-" * 50)

        prev_value = None
        for month, value in rows:
            val_str = format_value(value, unit)
            if prev_value is None:
                delta_str_color = "--"
            else:
                delta = value - prev_value
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}{format_value(abs(delta), unit)}"
                color = GREEN if delta >= 0 else RED
                delta_str_color = cat_label(delta_str, color)
            print(f"  {month:<10}  {val_str:>17}  {delta_str_color:>17}")
            prev_value = value
        print()

if __name__ == "__main__":
    main()
