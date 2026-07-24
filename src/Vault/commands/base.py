from abc import ABC, abstractmethod
import datetime
import re
from ..helper import (
    cat_label, format_value, print_banner, sparkline,
    BOLD, RESET,
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE,
)

class BaseCommand(ABC):

    # Helper functions — available to all subclasses via self.<name>(...)
    cat_label    = staticmethod(cat_label)
    format_value = staticmethod(format_value)
    print_banner = staticmethod(print_banner)
    sparkline    = staticmethod(sparkline)

    # ANSI color constants
    BOLD, RESET  = BOLD, RESET
    BLACK, RED, GREEN, YELLOW = BLACK, RED, GREEN, YELLOW
    BLUE, MAGENTA, CYAN, WHITE = BLUE, MAGENTA, CYAN, WHITE

    # Whether this command mutates the shared pending-commits list. CLI uses this to
    # decide whether the commits table should reprint after the command runs.
    mutates_commits = False

    # Detailed usage text printed by `<command> usage` and internal error paths.
    USAGE: str | None = None

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
    def call_str(self) -> str | list[str]:
        """The top-level command name(s) used to register this class (e.g. 'field', or
        ['help', 'h'] to register aliases)."""

    @property
    def call_strs(self) -> list[str]:
        """call_str normalized to a list, regardless of whether a subclass declared a
        single string or a list of aliases."""

        return [self.call_str] if isinstance(self.call_str, str) else list(self.call_str)

    @abstractmethod
    def entry_point(self, options: dict):
        """Return {command_name: callable} for registration."""

    def init_command(self) -> dict:
        """Return {command_name: entry_point} for each alias in call_strs, to register
        calling this class."""

        return {alias: self.entry_point for alias in self.call_strs}

    def usage(self):
        """Print this command's detailed usage text."""
        if self.USAGE:
            print(self.USAGE.strip())
        else:
            print(f"Usage: {self.call_strs[0]} — no detailed usage available.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_int(self, raw: str):
        try:
            return int(raw.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _parse_month_year(self, raw_month: str, raw_year: str) -> str | None:
        month = self._parse_int(raw_month)
        year = self._parse_int(raw_year)
        if month is None or year is None:
            return None
        if month < 1 or month > 12:
            return None
        if year < 100:
            year = 2000 + year
        elif year < 1000 or year > 9999:
            return None
        return f"{year:04d}-{month:02d}"

    def _parse_month_string(self, raw: str) -> str | None:
        """Validate a YYYY-MM token; return normalized form or None.

        Requires exactly four digits, a hyphen, and two digits. Month must be
        1–12, and the month must not be after the current month.
        """
        if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}", raw):
            return None
        year_s, month_s = raw.split("-", 1)
        year = self._parse_int(year_s)
        month = self._parse_int(month_s)
        if year is None or month is None:
            return None
        if month < 1 or month > 12:
            return None
        normalized = f"{year:04d}-{month:02d}"
        current_month = datetime.datetime.now().strftime("%Y-%m")
        if normalized > current_month:
            return None
        return normalized

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

    def _commodity_price(self, field_id: int):
        """Return the best available price for a commodity-tagged field, or None.

        If a live price_fetcher is present, defers to it (override -> live -> cached).
        Otherwise falls back to reading override/cached prices straight from the DB, so
        they're still available when price_fetcher is None (e.g. --test mode).
        """
        if self.price_fetcher is not None:
            return self.price_fetcher.get_price(field_id)

        for row_field_id, _, _, override_price, cached_price, _ in self.db.get_commodity_fields():
            if row_field_id != field_id:
                continue
            if override_price is not None:
                return override_price
            return cached_price

        return None
