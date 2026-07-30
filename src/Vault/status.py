try:
    from prompt_toolkit.formatted_text import FormattedText
except ImportError:
    FormattedText = None

from .data_types import CATEGORIES
from .helper import format_value


class StatusLine:
    """Builds bottom-toolbar and rprompt status fragments from pending commits and price data."""

    def __init__(self, pending_commits, price_fetcher=None, *, db=None, test_mode=False):
        self.pending_commits = pending_commits
        self.price_fetcher = price_fetcher
        self.db = db
        self.test_mode = test_mode
        self._cached_net_worth = None
        self.refresh_net_worth()

    def _price_freshness(self):
        if self.price_fetcher is None:
            return "n/a"
        statuses = self.price_fetcher.get_fetch_status()
        if not statuses:
            return "n/a"
        sources = {row[3] for row in statuses}
        if "live" in sources:
            return "live"
        if "cached" in sources:
            return "cached"
        if "override" in sources:
            return "override"
        if "unavailable" in sources:
            return "unavailable"
        return "n/a"

    def _target_month_text(self):
        months = self.pending_commits.target_months()
        if not months:
            return None
        if len(months) == 1:
            return months[0]
        return ", ".join(months)

    def toolbar_text(self):
        """Return styled toolbar fragments, or a plain string without prompt_toolkit."""
        fragments = [
            ("status.staged", f"{self.pending_commits.staged_count} staged"),
        ]

        month = self._target_month_text()
        if month:
            fragments.extend([
                ("status.default", " · "),
                ("status.month", month),
            ])

        fragments.extend([
            ("status.default", " · "),
            ("status.prices", f"prices: {self._price_freshness()}"),
        ])

        if self.test_mode:
            fragments.extend([
                ("status.default", " · "),
                ("status.test", "[TEST]"),
            ])

        if FormattedText is not None:
            return FormattedText(fragments)
        return "".join(text for _, text in fragments)

    def refresh_net_worth(self):
        if self.db is None:
            self._cached_net_worth = None
            return
        self._cached_net_worth = self._compute_net_worth()

    def _investment_price(self, field_id):
        if self.price_fetcher is not None:
            return self.price_fetcher.get_price(field_id)

        for row_field_id, _, _, override_price, cached_price, _ in self.db.get_investment_fields():
            if row_field_id != field_id:
                continue
            if override_price is not None:
                return override_price
            return cached_price

        return None

    def _compute_net_worth(self):
        rows = self.db.get_latest_values()
        if not rows:
            return None

        assets = 0.0
        liabilities = 0.0
        for _field_name, category_name, _unit, amount, field_id in rows:
            category_cls = CATEGORIES[category_name]
            if category_cls.is_liability:
                liabilities += amount
            elif category_cls.is_priced:
                price = self._investment_price(field_id)
                if price is not None:
                    assets += category_cls.usd_value(amount, price)
            else:
                assets += amount

        return assets - liabilities

    def rprompt_text(self):
        """Return right-aligned net worth, using the cached value."""
        if self._cached_net_worth is None:
            text = "net: n/a"
        else:
            text = f"net: {format_value(self._cached_net_worth, '$')}"

        fragments = [("status.net", text)]
        if FormattedText is not None:
            return FormattedText(fragments)
        return text
