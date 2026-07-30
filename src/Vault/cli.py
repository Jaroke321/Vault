import argparse
import datetime
import time
from pathlib import Path
from rich.progress import track

# Extra imports of useful things
from .prompt import Prompt
from .routing import Route
from .logger import Logger
from .db_handler import DBHandler
from .price_fetcher import PriceFetcher
from .pending_commits import PendingCommits
from .status import StatusLine
from .helper import *

# Command classes
from .commands import FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, DiffCommand, HelpCommand, InvestmentCommand, ExportCommand, ImportCommand, ExitCommand

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
        command_class_list = [ FieldCommand, UpdateCommand, CommitCommand, SummaryCommand, ShowCommand, DiffCommand, HelpCommand, InvestmentCommand, ExportCommand, ImportCommand, ExitCommand]
        self.load_command_classes(command_class_list)

    def run(self):
        print_banner(test_mode=self.test_mode)
        history_path = None if self.test_mode else "logs/.vault_history"
        status_line = StatusLine(
            self.pending_commits,
            self.price_fetcher,
            test_mode=self.test_mode,
        )
        prompt = Prompt(
            project_name=self.project_name,
            logger=self.logger,
            routes=self.routes,
            history_path=history_path,
            status_line=status_line,
        )
        prompt.render()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def load_command_classes(self, command_class_list: list) -> None:

        owners = {}       # Maps command name to command class name, used for error checking
        self.routes = {}  # Maps top-level command name to Route

        for cls in command_class_list:
            instance = cls(self.db, self.logger, self.price_fetcher, self.pending_commits)
            usage = instance.usage_text()
            route_children = self._build_route_children(instance, instance.sub_commands)
            for name, entry_point in instance.init_command().items():
                if name in self.routes:
                    raise ValueError(
                        f"Alias '{name}' is claimed by both {owners[name]} and {cls.__name__}."
                    )
                owners[name] = cls.__name__
                self.routes[name] = Route(
                    handler=self._wrap_entry_point(entry_point, instance),
                    usage=usage,
                    children=route_children,
                )

    def _build_route_children(self, instance, sub_commands: dict) -> dict:
        """Recursively fold `sub_commands` (name -> bound method) into `dict[str, Route]`,
        following any `subroute`-tagged children to build depth beyond one level."""

        children = {}
        for name, handler in sub_commands.items():
            grandchild_names = getattr(handler, "subroutes", {})
            grandchildren = {
                child_name: getattr(instance, method_name)
                for child_name, method_name in grandchild_names.items()
            }
            children[name] = Route(
                handler=self._wrap_entry_point(handler, instance),
                children=self._build_route_children(instance, grandchildren),
            )
        return children

    def _wrap_entry_point(self, entry_point, instance):
        def wrapped(options):
            if options and options[0] == "usage":
                instance.usage()
                return
            entry_point(options)

        return wrapped

if __name__ == "__main__":
    main()
