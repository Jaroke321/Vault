from .base import BaseCommand

class SummaryCommand(BaseCommand):

    call_str = "summary" # Tells the prompt the string command in order to call this class

    DEBT_CATEGORIES = {"debt"}
    MONETARY_UNITS = {"$", "€", "£", "¥"}

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

        for field_name, category_name, unit, value, asset_value, field_id in rows:

            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name

            is_debt = category_name.lower() in self.DEBT_CATEGORIES
            is_monetary = unit in self.MONETARY_UNITS

            if is_debt and asset_value is not None:
                equity = asset_value - value
                liabilities += value
                assets      += asset_value
                print(f"    {field_name:<20} balance:  {self.format_value(value, unit):>16}  (liability)")
                print(f"    {'':<20} value:    {self.format_value(asset_value, unit):>16}")
                print(f"    {'':<20} equity:   {self.format_value(equity, unit):>16}")

            elif is_debt:
                print(f"    {field_name:<20} {self.format_value(value, unit):>16}  (liability)")
                liabilities += value

            elif is_monetary:
                print(f"    {field_name:<20} {self.format_value(value, unit):>16}")
                assets += value

            elif self.price_fetcher is not None:
                price = self.price_fetcher.get_price(field_id)

                if price is not None:
                    usd_equiv = value * price
                    assets += usd_equiv
                    print(f"    {field_name:<20} {self.format_value(value, unit):>10} ~ {self.format_value(usd_equiv, '$'):>12} (@{self.format_value(price, '$')}/{unit})")

                else:
                    print(f"    {field_name:<20} {self.format_value(value, unit):>10} (no price)")

            else:
                print(f"    {field_name:<20} {self.format_value(value, unit):>16}")

        net = assets - liabilities
        print(f"\n  {'Assets:':<20} ${assets:>12,.2f}")
        print(f"  {'Liabilities:':<20} ${liabilities:>12,.2f}")
        print(f"  {'Net Worth:':<20} ${net:>12,.2f}")
        print()
        self.logger.log(f"Summary viewed: assets={assets:.2f}, liabilities={liabilities:.2f}, net={net:.2f}")

    def init_command(self) -> dict:

        return {self.call_str: self.entry_point}
