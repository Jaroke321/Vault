from abc import ABC, abstractmethod
from ..helper import (
    cat_label, format_value, print_banner,
    BOLD, RESET,
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE,
)

class BaseCommand(ABC):

    # Helper functions — available to all subclasses via self.<name>(...)
    cat_label    = staticmethod(cat_label)
    format_value = staticmethod(format_value)
    print_banner = staticmethod(print_banner)

    # ANSI color constants
    BOLD, RESET  = BOLD, RESET
    BLACK, RED, GREEN, YELLOW = BLACK, RED, GREEN, YELLOW
    BLUE, MAGENTA, CYAN, WHITE = BLUE, MAGENTA, CYAN, WHITE

    def __init__(self, db, logger, price_fetcher=None, commits=None):
        self.db = db
        self.logger = logger
        self.price_fetcher = price_fetcher
        self.commits = commits
        
        self.sub_commands = {
            name.removeprefix("sub_"): getattr(self, name)
            for name in dir(self)
            if name.startswith("sub_")
        }

    @property
    @abstractmethod
    def call_str(self) -> str:
        """The top-level command name used to register this class (e.g. 'field')."""

    @abstractmethod
    def entry_point(self, options: dict):
        """Return {command_name: callable} for registration."""

    @abstractmethod
    def init_command(self) -> dict:
        """Return {command_name: entry_point} to register calling this class"""

        return {}


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_int(self, raw: str):
        try:
            return int(raw.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _parse_float(self, raw: str):
        try:
            return float(raw.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _is_a_field_name(self, raw: str) -> bool:
        all_fields = [f for f, c, u in self.db.get_active_fields()]
        return raw.lower() in all_fields

    def _is_a_category_name(self, raw: str) -> bool:
        return raw.lower() in self.db.get_categories()
