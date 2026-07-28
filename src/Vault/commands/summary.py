from .base import BaseCommand
from ..data_types import CATEGORIES

class SummaryCommand(BaseCommand):

    call_str = "summary" # Tells the prompt the string command in order to call this class

    USAGE = """
  summary                       Net worth snapshot (assets minus debts)
"""

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        rows = self.db.get_latest_values()
        if not rows:
            print("No data recorded yet.")
            return

        assets = 0.0
        liabilities = 0.0
        current_cat = None

        print("\n  === Net Worth Summary ===")

        for field_name, category_name, unit, amount, field_id in rows:
            category_cls = CATEGORIES[category_name]

            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name

            if category_cls.is_liability:
                liabilities += amount
                self._print_debt_row(field_name, unit, amount, field_id)

            elif category_cls.is_priced:
                price = self._investment_price(field_id)
                if price is not None:
                    usd_equiv = category_cls.usd_value(amount, price)
                    assets += usd_equiv
                    print(
                        f"    {field_name:<20} {self.format_value(amount, unit):>10} "
                        f"~ {self.format_value(usd_equiv, '$'):>12} "
                        f"(@{self.format_value(price, '$')}/{unit})"
                    )
                else:
                    print(f"    {field_name:<20} {self.format_value(amount, unit):>10} (no price)")

            else:
                assets += amount
                print(f"    {field_name:<20} {self.format_value(amount, unit):>16}")

        net = assets - liabilities
        print(f"\n  {'Assets:':<20} ${assets:>12,.2f}")
        print(f"  {'Liabilities:':<20} ${liabilities:>12,.2f}")
        print(f"  {'Net Worth:':<20} ${net:>12,.2f}")
        print()
        self.logger.log(f"Summary viewed: assets={assets:.2f}, liabilities={liabilities:.2f}, net={net:.2f}")

    ####################################
    # Rendering
    ####################################
    def _print_debt_row(self, field_name: str, unit: str, amount: float, field_id: int):
        """Print a Debt row — plain liability line, or the display-only
        balance/backing-value/equity trio when linked to a backing record.
        The link never affects assets/liabilities totals: the backing record's own
        value is already counted (or excluded, if unpriced) via its own row above."""
        apr = self.db.get_apr(field_id)
        backing = self.db.get_backing_info(field_id)
        if backing is None:
            print(f"    {field_name:<20} {self.format_value(amount, unit):>16}  (liability)")
            self._print_apr_line(apr)
            return

        backing_name, backing_category, backing_amount, backing_id = backing
        backing_cls = CATEGORIES[backing_category]

        if backing_cls.is_priced:
            backing_price = self._investment_price(backing_id)
            backing_usd = backing_cls.usd_value(backing_amount, backing_price) if backing_price is not None else None
        else:
            backing_usd = backing_cls.usd_value(backing_amount)

        if backing_usd is None:
            print(f"    {field_name:<20} {self.format_value(amount, unit):>16}  (liability, backing price unavailable)")
            self._print_apr_line(apr)
            return

        equity = backing_usd - amount
        print(f"    {field_name:<20} balance:  {self.format_value(amount, unit):>16}  (liability)")
        self._print_apr_line(apr)
        print(f"    {'':<20} backed by '{backing_name}': {self.format_value(backing_usd, '$'):>16}")
        print(f"    {'':<20} equity:   {self.format_value(equity, '$'):>16}")

    def _print_apr_line(self, apr: float | None) -> None:
        if apr is not None:
            print(f"    {'':<20} APR: {apr:.2f}%")
