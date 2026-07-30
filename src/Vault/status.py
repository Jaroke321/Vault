try:
    from prompt_toolkit.formatted_text import FormattedText
except ImportError:
    FormattedText = None


class StatusLine:
    """Builds bottom-toolbar status fragments from pending commits and price data."""

    def __init__(self, pending_commits, price_fetcher=None, *, test_mode=False):
        self.pending_commits = pending_commits
        self.price_fetcher = price_fetcher
        self.test_mode = test_mode

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
