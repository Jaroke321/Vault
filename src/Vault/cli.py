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
from .pending_commits import PendingCommits
from .helper import *

# Command classes
from .commands import FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, HelpCommand

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
        self.pending_commits = PendingCommits()

        # Need to init classes before using
        command_class_list = [ FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, HelpCommand]
        self.command_classes = self.load_command_classes(command_class_list)

        # Handle any command calls available to the user that is not in its own command class
        # This will allow the user to call the key value and the prompt will then pass any options
        # to the function tied to that command
        self.commands = {
            "commodity": self.cmd_commodity,
        }

        # add command class entry points to the commands list
        self.commands |= self.command_classes

    def run(self):
        print_banner()
        if self.test_mode:
            print(f"{BOLD}{YELLOW}  *** TEST MODE — in-memory database, no changes will be saved ***{RESET}\n")
        prompt = Prompt(project_name=self.project_name, logger=self.logger, state_data_viewer=self.pending_commits.render, cmd_dict=self.commands)
        prompt.render()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def load_command_classes(self, command_class_list: list) -> dict:

        commands = {}

        for cls in command_class_list:
            instance = cls(self.db, self.logger, self.price_fetcher, self.pending_commits)
            for name, entry_point in instance.init_command().items():
                commands[name] = self._wrap_entry_point(entry_point, instance)

        return commands

    def _wrap_entry_point(self, entry_point, instance):
        """Wrap a command class's entry point so the pending-commits table stays in sync
        with whether that command mutates the shared pending-commits list."""

        def wrapped(options):
            entry_point(options)
            if not instance.mutates_commits:
                self.pending_commits.suppress_next_render()

        return wrapped

    def cmd_commodity(self, options: list):
        self.pending_commits.suppress_next_render()

        # TODO: Need to refactor this function. It is looking haggard

        if not options:
            print("Usage: commodity tag <field> <commodity> | commodity untag <field> | commodity override <field> <price>|clear | commodity list | commodity refresh")
            return

        sub = options[0]

        if sub == "tag":
            if len(options) < 3:

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_float(self, raw: str):
        try:
            cleaned = raw.replace("$", "").replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            return None

if __name__ == "__main__":
    main()
