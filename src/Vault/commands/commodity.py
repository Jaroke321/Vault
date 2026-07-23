import datetime
from .base import BaseCommand
from ..price_fetcher import PriceFetcher

class CommodityCommand(BaseCommand):

    call_str = "commodity" # Tells the prompt the string command in order to call this class

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
            print(f"Unknown subcommand '{sub}'. Use: tag, untag, override, list, refresh")

    def usage(self):
        print("Usage: commodity tag <field> <commodity> | commodity untag <field> | commodity override <field> <price>|clear | commodity list | commodity refresh")

    ####################################
    # Sub-commands
    ####################################
    def sub_tag(self, options: list):

        # Error checking
        if len(options) < 2:

            # TODO:
            # Need to think about how to apply a commodity to an entire category
            # This will be useful for the user and can avoid the awkward command of
            # commodity tag gold gold
            # instead the user should be able to type in commodity tag metals
            # and if metals is a category in storage
            # We will attempt to commodify all of them

            return

        # Business logic
        field_name = options[0]
        symbol = PriceFetcher.resolve_symbol(options[1])

        # Known commodity symbols (metals, etc.) tag instantly, same as always — the
        # static list is still their typo safety net. Pass-through tickers (anything
        # not in the static maps) have no such list, so validate them live instead.
        live_price = None
        if symbol not in PriceFetcher.SYMBOL_TO_TICKER and self.price_fetcher is not None:
            live_price = self.price_fetcher.probe_symbol(symbol)
            if live_price is None:
                print(f"Could not resolve '{options[1]}' as a live ticker — check the symbol and your connection.")
                return

        success = self.db.set_commodity(field_name, symbol)
        if success:
            print(f"Field '{field_name}' tagged as {symbol}.")
            self.logger.log(f"Commodity tag set: {field_name} -> {symbol}")
            if live_price is not None:
                now = datetime.datetime.now().isoformat()
                self.db.set_commodity_cache(field_name, live_price, now)
        else:
            print(f"No active field named '{field_name}'.")

    def sub_untag(self, options: list):

        # Error checking
        if len(options) < 1:
            print("Usage: commodity untag <field>")
            return

        # Business logic
        success = self.db.remove_commodity(options[0])
        if success:
            print(f"Commodity tag removed from '{options[0]}'.")
        else:
            print(f"No commodity tag found for '{options[0]}'.")

    def sub_override(self, options: list):

        # Error checking
        if len(options) < 2:
            print("Usage: commodity override <field> <price> | commodity override <field> clear")
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
        success = self.db.set_commodity_override(field_name, price)
        if success:
            if price is None:
                print(f"Override cleared for '{field_name}'. Using live/cached price.")
            else:
                print(f"Override price set for '{field_name}': {self.format_value(price, '$')}/unit.")
            self.logger.log(f"Commodity override set: {field_name} -> {price}")
        else:
            print(f"No commodity tag found for '{field_name}'. Use 'commodity tag' first.")

    def sub_list(self, options: list):

        # Business logic
        status_rows = self._fetch_status()
        if not status_rows:
            print("No commodity-tagged fields. Use 'commodity tag <field> <symbol>' to add one.")
            return

        print(f"\n  {'Field':<20}  {'Symbol':<6}  {'Price':>12}  {'Source':<12}  {'Cached At'}")
        print("  " + "-" * 72)
        for field_name, symbol, price, source, cached_at in status_rows:
            price_str = self.format_value(price, '$') if price is not None else "N/A"
            age_str = cached_at[:19] if cached_at else "never"
            print(f"  {field_name:<20}  {symbol:<6}  {price_str:>12}  {source:<12}  {age_str}")
        print()

    def _fetch_status(self) -> list[tuple]:
        """Return display info for each tagged field: (field_name, symbol, price, source, cached_at).

        Defers to price_fetcher.get_fetch_status() when a fetcher is present (it also
        knows about freshly-fetched live prices). Otherwise falls back to override/cached
        prices read straight from the DB, so 'commodity list' still works without a
        fetcher (e.g. --test mode). source is one of: 'override', 'cached', 'unavailable'
        (plus 'live' when a fetcher supplied it).
        """
        if self.price_fetcher is not None:
            return self.price_fetcher.get_fetch_status()

        result = []
        for field_id, field_name, symbol, override_price, cached_price, cached_at in self.db.get_commodity_fields():
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
        print("Refreshing commodity prices...")
        fetched = self.price_fetcher.fetch_all()
        if fetched:
            for sym, price in sorted(fetched.items()):
                print(f"  {sym}: {self.format_value(price, '$')}")
        else:
            print("  No prices fetched (no tagged fields or fetch failed).")
