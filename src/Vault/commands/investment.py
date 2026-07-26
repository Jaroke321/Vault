from .base import BaseCommand
from ..price_fetcher import PriceFetcher

class InvestmentCommand(BaseCommand):

    call_str = "investment" # Tells the prompt the string command in order to call this class

    USAGE = """
  investment override <field> <price>   Lock a manual price per unit for this field
  investment override <field> clear     Remove price lock (use live/cached price)
  investment list                       Show all investment records with current prices and source
  investment options                    Show known commodity symbols, names, and units
  investment refresh                    Re-fetch live prices for all investment records
"""

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
            print(f"Unknown subcommand '{sub}'. Use: override, list, options, refresh")

    ####################################
    # Sub-commands
    ####################################
    def sub_override(self, options: list):

        # Error checking
        if len(options) < 2:
            print("Usage: investment override <field> <price> | investment override <field> clear")
            return

        # Business logic
        field_name, raw = options[0], options[1]
        if raw.lower() == "clear":
            price = None
        else:
            price = self._parse_float(raw)
            if price is None:
                print(f"Invalid price '{raw}'. Must be a number or 'clear'.")
                return
        success = self.db.set_override(field_name, price)
        if success:
            if price is None:
                print(f"Override cleared for '{field_name}'. Using live/cached price.")
            else:
                print(f"Override price set for '{field_name}': {self.format_value(price, '$')}/unit.")
            self.logger.log(f"Investment override set: {field_name} -> {price}")
        else:
            print(f"No investment record named '{field_name}'. Use 'field add investment' first.")

    def sub_options(self, options: list):
        """List all known commodity symbols, their name aliases, and unit, grouped by
        category. Static reference data — no DB or price_fetcher access, so this works
        identically with or without --test/network."""

        aliases_by_symbol: dict[str, list[str]] = {}
        for name, symbol in PriceFetcher.NAME_TO_SYMBOL.items():
            aliases_by_symbol.setdefault(symbol, []).append(name)

        current_cat = None
        for symbol in PriceFetcher.SYMBOL_TO_TICKER:
            category = PriceFetcher.SYMBOL_TO_CATEGORY[symbol]
            if category != current_cat:
                print(f"\n  {self.cat_label(category)}")
                current_cat = category
            names = ", ".join(aliases_by_symbol.get(symbol, []))
            unit = PriceFetcher.SYMBOL_TO_UNIT[symbol]
            print(f"    {symbol:<6}{names:<22}{unit}")
        print(
            "\n  Tag a record with a symbol or name at add time, e.g. "
            "'field add investment <name> XAU' or 'field add investment <name> gold'."
        )
        print("  Any other input is treated as a pass-through stock/ETF ticker, validated live at add time.\n")

    def sub_list(self, options: list):

        # Business logic
        status_rows = self._fetch_status()
        if not status_rows:
            print("No investment records. Use 'field add investment <name> <symbol>' to add one.")
            return

        print(f"\n  {'Field':<20}  {'Symbol':<6}  {'Price':>12}  {'Source':<12}  {'Cached At'}")
        print("  " + "-" * 72)
        for field_name, symbol, price, source, cached_at in status_rows:
            price_str = self.format_value(price, '$') if price is not None else "N/A"
            age_str = cached_at[:19] if cached_at else "never"
            print(f"  {field_name:<20}  {symbol:<6}  {price_str:>12}  {source:<12}  {age_str}")
        print()

    def _fetch_status(self) -> list[tuple]:
        """Return display info for each investment record: (field_name, symbol, price, source, cached_at).

        Defers to price_fetcher.get_fetch_status() when a fetcher is present (it also
        knows about freshly-fetched live prices). Otherwise falls back to override/cached
        prices read straight from the DB, so 'investment list' still works without a
        fetcher (e.g. --test mode). source is one of: 'override', 'cached', 'unavailable'
        (plus 'live' when a fetcher supplied it).
        """
        if self.price_fetcher is not None:
            return self.price_fetcher.get_fetch_status()

        result = []
        for field_id, field_name, symbol, override_price, cached_price, cached_at in self.db.get_investment_fields():
            if override_price is not None:
                result.append((field_name, symbol, override_price, "override", cached_at))
            elif cached_price is not None:
                result.append((field_name, symbol, cached_price, "cached", cached_at))
            else:
                result.append((field_name, symbol, None, "unavailable", cached_at))
        return result

    def sub_refresh(self, options: list):

        # Error checking
        if self.price_fetcher is None:
            print("Price fetcher not available.")
            return

        # Business logic
        print("Refreshing investment prices...")
        fetched = self.price_fetcher.fetch_all()
        if fetched:
            for sym, price in sorted(fetched.items()):
                print(f"  {sym}: {self.format_value(price, '$')}")
        else:
            print("  No prices fetched (no investment records or fetch failed).")
