import datetime
import yfinance as yf


class PriceFetcher:
    """Fetches live spot prices for commodity symbols using yfinance.

    Price resolution priority for get_price():
        1. override_price (user-locked manual price)
        2. Live price fetched at startup (self._prices)
        3. cached_price stored in DB from last successful fetch
        4. None — field excluded from net worth
    """

    SYMBOL_TO_TICKER = {
        # Precious metals
        "XAU": "GC=F",
        "XAG": "SI=F",
        "XPT": "PL=F",
        "XPD": "PA=F",
        # Base metals
        "HG":  "HG=F",   # Copper futures
        # Energy
        "CL":  "CL=F",   # WTI Crude Oil futures
        "BZ":  "BZ=F",   # Brent Crude futures
        "NG":  "NG=F",   # Natural Gas futures
        # Agricultural
        "ZW":  "ZW=F",   # Wheat futures
        "ZC":  "ZC=F",   # Corn futures
        "ZS":  "ZS=F",   # Soybean futures
        "KC":  "KC=F",   # Coffee futures
        "SB":  "SB=F",   # Sugar futures
        "CC":  "CC=F",   # Cocoa futures
        "CT":  "CT=F",   # Cotton futures
    }

    # Category + display unit per symbol. Static reference data for `commodity
    # options`; groupings mirror the comment sections above — keep all three
    # collections in sync when adding a symbol. All prices are USD.
    SYMBOL_TO_CATEGORY = {
        "XAU": "Precious metals", "XAG": "Precious metals",
        "XPT": "Precious metals", "XPD": "Precious metals",
        "HG":  "Base metals",
        "CL":  "Energy", "BZ": "Energy", "NG": "Energy",
        "ZW":  "Agricultural", "ZC": "Agricultural", "ZS": "Agricultural",
        "KC":  "Agricultural", "SB": "Agricultural", "CC": "Agricultural", "CT": "Agricultural",
    }

    SYMBOL_TO_UNIT = {
        "XAU": "troy oz", "XAG": "troy oz", "XPT": "troy oz", "XPD": "troy oz",
        "HG":  "lb",
        "CL":  "barrel", "BZ": "barrel", "NG": "MMBtu",
        "ZW":  "bushel", "ZC": "bushel", "ZS": "bushel",
        "KC":  "lb", "SB": "lb", "CC": "metric ton", "CT": "lb",
    }

    NAME_TO_SYMBOL = {
        # Precious metals
        "gold":         "XAU",
        "silver":       "XAG",
        "platinum":     "XPT",
        "palladium":    "XPD",
        # Base metals
        "copper":       "HG",
        # Energy
        "oil":          "CL",
        "crude oil":    "CL",
        "wti":          "CL",
        "brent":        "BZ",
        "natural gas":  "NG",
        # Agricultural
        "wheat":        "ZW",
        "corn":         "ZC",
        "soybeans":     "ZS",
        "soybean":      "ZS",
        "coffee":       "KC",
        "sugar":        "SB",
        "cocoa":        "CC",
        "cotton":       "CT",
    }

    @classmethod
    def resolve_symbol(cls, raw: str) -> str:
        """Resolve a friendly name or symbol to a canonical commodity symbol.

        Unrecognized input passes through as a literal ticker (e.g. a stock/ETF
        symbol, which is already its own ticker) rather than returning None.
        """
        key = raw.lower()
        if key in cls.NAME_TO_SYMBOL:
            return cls.NAME_TO_SYMBOL[key]
        upper = raw.upper()
        if upper in cls.SYMBOL_TO_TICKER:
            return upper
        return raw.strip().upper()

    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        # {symbol: price} populated by fetch_all()
        self._prices: dict[str, float] = {}
        # {field_id: (override_price, cached_price)} populated by fetch_all()
        self._field_meta: dict[int, tuple] = {}

    def fetch_all(self) -> dict[str, float]:
        """Fetch live prices for every commodity-tagged field.

        Updates the DB cache for each successful fetch.
        Returns {symbol: price}. Never raises.
        """

        commodity_fields = self.db.get_commodity_fields()
        if not commodity_fields:
            return {}

        # Build field_id → meta map and collect unique symbols
        symbols_needed: set[str] = set()
        for field_id, field_name, symbol, override_price, cached_price, cached_at in commodity_fields:
            self._field_meta[field_id] = (symbol, override_price, cached_price)
            if override_price is None:
                symbols_needed.add(symbol)

        # Fetch each distinct symbol once
        fetched: dict[str, float] = {}
        for symbol in symbols_needed:
            price = self._fetch_symbol(symbol)
            if price is not None:
                fetched[symbol] = price

        # Write back to DB cache and populate in-memory dict
        now = datetime.datetime.now().isoformat()
        for field_id, field_name, symbol, override_price, cached_price, cached_at in commodity_fields:
            if symbol in fetched:
                self.db.update_cached_price(field_id, fetched[symbol], now)
                # Refresh cached value in meta
                self._field_meta[field_id] = (symbol, override_price, fetched[symbol])

        self._prices = fetched

        if fetched:
            price_summary = "  ".join(f"{sym}={price:,.2f}" for sym, price in sorted(fetched.items()))
            self.logger.log(f"Commodity prices fetched: {price_summary}")

        return fetched

    def get_price(self, field_id: int) -> float | None:
        """Return the best available price for a field, or None if unavailable."""
        meta = self._field_meta.get(field_id)
        if meta is None:
            # Field is not tagged as a commodity
            return None

        symbol, override_price, cached_price = meta

        if override_price is not None:
            return override_price

        if symbol in self._prices:
            return self._prices[symbol]

        if cached_price is not None:
            return cached_price

        return None

    def probe_symbol(self, symbol: str) -> float | None:
        """Live-fetch a single symbol's price, or None if it can't be resolved.

        Used by 'commodity tag' to validate a pass-through ticker at tag time.
        """
        return self._fetch_symbol(symbol)

    def get_fetch_status(self) -> list[tuple]:
        """Return display info for each tagged field: (field_name, symbol, price, source, cached_at).

        source is one of: 'override', 'live', 'cached', 'unavailable'
        """
        rows = self.db.get_commodity_fields()
        result = []
        for field_id, field_name, symbol, override_price, cached_price, cached_at in rows:
            if override_price is not None:
                result.append((field_name, symbol, override_price, "override", cached_at))
            elif symbol in self._prices:
                result.append((field_name, symbol, self._prices[symbol], "live", cached_at))
            elif cached_price is not None:
                result.append((field_name, symbol, cached_price, "cached", cached_at))
            else:
                result.append((field_name, symbol, None, "unavailable", cached_at))
        return result

    def _fetch_symbol(self, symbol: str) -> float | None:
        # Pass-through tickers (stocks/ETFs) aren't in SYMBOL_TO_TICKER — a stock's
        # symbol is already its yfinance ticker, unlike futures-style commodities.
        ticker_name = self.SYMBOL_TO_TICKER.get(symbol, symbol)
        try:
            ticker = yf.Ticker(ticker_name)
            price = ticker.fast_info.last_price
            if price and price > 0:
                return float(price)
            self.logger.log(f"No price data returned for {symbol} ({ticker_name})")
            return None
        except Exception as e:
            self.logger.log(f"Failed to fetch price for {symbol} ({ticker_name}): {e}")
            return None
