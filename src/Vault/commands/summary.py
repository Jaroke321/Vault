from .base import BaseCommand
from ..data_types import CATEGORIES

class SummaryCommand(BaseCommand):

    call_str = "summary" # Tells the prompt the string command in order to call this class

    USAGE = """
  summary                       Net worth snapshot (assets minus debts)
"""

    ROW_INDENT = "    "
    TOTAL_INDENT = "  "
    NAME_W = 22
    VALUE_W = 18
    SUB_LABEL_W = 18
    QTY_W = 18
    USD_W = 14

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
        notes = self.db.get_notes()
        any_noted = False

        print("\n  === Net Worth Summary ===")

        for field_name, category_name, unit, amount, field_id in rows:
            category_cls = CATEGORIES[category_name]
            has_note = field_name in notes
            if has_note:
                any_noted = True
            label = self.note_label(field_name, has_note)

            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name

            if category_cls.is_liability:
                liabilities += amount
                self._print_debt_row(label, unit, amount, field_id)

            elif category_cls.is_priced:
                price = self._investment_price(field_id)
                if price is not None:
                    usd_equiv = category_cls.usd_value(amount, price)
                    assets += usd_equiv
                    self._print_investment_row(
                        label, amount, unit, usd_equiv, price,
                    )
                else:
                    self._print_main_row(
                        label, self.format_value(amount, unit), "(no price)"
                    )

            else:
                assets += amount
                self._print_main_row(label, self.format_value(amount, unit))

        net = assets - liabilities
        total_label_w = len(self.ROW_INDENT) + self.NAME_W - len(self.TOTAL_INDENT)
        print(f"\n{self.TOTAL_INDENT}{'Assets:':<{total_label_w}}{self.format_value(assets, '$'):>{self.VALUE_W}}")
        print(f"{self.TOTAL_INDENT}{'Liabilities:':<{total_label_w}}{self.format_value(liabilities, '$'):>{self.VALUE_W}}")
        print(f"{self.TOTAL_INDENT}{'Net Worth:':<{total_label_w}}{self.format_value(net, '$'):>{self.VALUE_W}}")
        if any_noted:
            print(f"  {self.NOTE_LEGEND}")
        print()
        self.logger.log(f"Summary viewed: assets={assets:.2f}, liabilities={liabilities:.2f}, net={net:.2f}")

    ####################################
    # Rendering
    ####################################
    def _print_main_row(self, label: str, value: str, tag: str = "") -> None:
        tag_part = f"  {tag}" if tag else ""
        print(
            f"{self.ROW_INDENT}{label:<{self.NAME_W}}"
            f"{value:>{self.VALUE_W}}{tag_part}"
        )

    def _print_sub_row(self, sub_label: str, value: str | None = None) -> None:
        if value is None:
            print(
                f"{self.ROW_INDENT}{'':<{self.NAME_W}}"
                f"{sub_label}"
            )
        else:
            print(
                f"{self.ROW_INDENT}{'':<{self.NAME_W}}"
                f"{sub_label:<{self.SUB_LABEL_W}}{value:>{self.VALUE_W}}"
            )

    def _print_investment_row(
        self,
        label: str,
        amount: float,
        unit: str,
        usd_equiv: float,
        price: float,
    ) -> None:
        qty = self.format_value(amount, unit)
        usd = self.format_value(usd_equiv, "$")
        rate = f"(@{self.format_value(price, '$')}/{unit})"
        print(
            f"{self.ROW_INDENT}{label:<{self.NAME_W}}"
            f"{qty:>{self.QTY_W}}  ~ {usd:>{self.USD_W}}  {rate}"
        )

    def _print_debt_row(self, field_name: str, unit: str, amount: float, field_id: int):
        """Print a Debt row — plain liability line, or the display-only
        balance/backing-value/equity trio when linked to a backing record.
        The link never affects assets/liabilities totals: the backing record's own
        value is already counted (or excluded, if unpriced) via its own row above."""
        apr = self.db.get_apr(field_id)
        value = self.format_value(amount, unit)
        backing = self.db.get_backing_info(field_id)
        if backing is None:
            self._print_main_row(field_name, value, "(liability)")
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
            self._print_main_row(field_name, value, "(liability, backing price unavailable)")
            self._print_apr_line(apr)
            return

        equity = backing_usd - amount
        self._print_main_row(field_name, value, "(liability)")
        self._print_apr_line(apr)
        self._print_sub_row(f"backed by {backing_name}", self.format_value(backing_usd, "$"))
        self._print_sub_row("equity", self.format_value(equity, "$"))

    def _print_apr_line(self, apr: float | None) -> None:
        if apr is not None:
            self._print_sub_row(f"APR: {apr:.2f}%")
