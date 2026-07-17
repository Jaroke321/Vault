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
from .commands import FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, HelpCommand, CommodityCommand

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
        command_class_list = [ FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, HelpCommand, CommodityCommand]
        self.command_classes = self.load_command_classes(command_class_list)

        # add command class entry points to the commands list
        self.commands = self.command_classes

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

if __name__ == "__main__":
    main()
