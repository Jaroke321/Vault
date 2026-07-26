from .base import BaseCommand
from ..data_types import FieldStatus

class FieldCommand(BaseCommand):

    call_str = "field" # Tells the prompt the string command in order to call this class

    USAGE = """
  field add cash|retirement|asset|debt <name>   Register a new record
  field add investment <name> <symbol>          Register an investment record (symbol required)
  field remove <name> [reason]                  Close a record (reason: active|sold|paid_off|closed; default: closed)
  field list                                    Show all active records by category
  field set <name> note <text>                  Attach a free-text note
  field set <name> apr <rate>                   Set a debt's interest rate
  field set <name> symbol <symbol>              Change an investment's price-tracking symbol
  field set <name> backing <asset> | clear      Link (or unlink) a debt to a backing asset-side record
  field set <name> replaces <old-name>          Mark this record as the successor of a prior one
  field set <name> status <status>              Relabel a record's lifecycle status
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
            print(f"Unknown sub command: {sub}")

    ####################################
    # Sub-commands
    ####################################
    def sub_add(self, options: list):

        # Error checking
        if len(options) < 2:
            self.usage()
            return

        category, name = options[0].lower(), options[1]
        if " " in name or " " in category:
            print("Field and category names cannot contain spaces.")
            return

        if not self._is_a_category_name(category):
            print(f"Unknown category '{category}'. Supported: {', '.join(self.db.get_categories())}.")
            return

        if category == "investment":
            if len(options) != 3:
                print("Usage: field add investment <name> <symbol>")
                return
            symbol = options[2]
        elif len(options) != 2:
            print(f"Usage: field add {category} <name>")
            return

        # Business logic
        if not self.db.add_field(name, category):
            print(f"Field '{name}' already exists.")
            return

        if category == "investment":
            self.db.set_investment_symbol(name, symbol)

        print(f"Field '{name}' added under category '{category}'.")
        self.logger.log(f"Field added: {name} (category: {category})")

    def sub_remove(self, options: list):

        # Error checking
        if not options:
            print("Usage: field remove <name> [reason]")
            return

        # Business logic
        name = options[0]
        reason = options[1] if len(options) > 1 else FieldStatus.CLOSED.value

        success = self.db.close_field(name, reason)
        if success:
            print(f"Field '{name}' closed ({reason}). History is preserved.")
            self.logger.log(f"Field closed: {name} ({reason})")
        else:
            valid_reasons = ", ".join(status.value for status in FieldStatus)
            print(f"No active field named '{name}' found, or invalid reason '{reason}' (valid: {valid_reasons}).")

    def sub_list(self, options: list):

        # Error checking
        fields = self.db.get_active_fields()
        if not fields:
            print("No active fields. Use 'field add <category> <name>' to add one.")
            return

        # Business logic — unit is shown per-record (not per-category header), since
        # Investment records can mix units (e.g. troy oz metals alongside share-based
        # tickers) within the same category.
        current_cat = None
        for field_name, category_name, unit in fields:
            if category_name != current_cat:
                print(f"\n  {self.cat_label(category_name)}")
                current_cat = category_name
            unit_str = f" [{unit}]" if unit != "$" else ""
            print(f"    - {field_name}{unit_str}")
        print()

    def sub_set(self, options: list):

        # Error checking
        if len(options) < 2:
            self.usage()
            return

        name, prop = options[0], options[1]
        rest = options[2:]

        if prop == "note":
            if not rest:
                print("Usage: field set <name> note <text>")
                return
            success = self.db.set_note(name, " ".join(rest))
            message = f"Note set for '{name}'."

        elif prop == "apr":
            if len(rest) != 1:
                print("Usage: field set <name> apr <rate>")
                return
            apr = self._parse_float(rest[0])
            if apr is None:
                print(f"Invalid APR '{rest[0]}'.")
                return
            success = self.db.set_apr(name, apr)
            message = f"APR set for '{name}': {apr}."

        elif prop == "symbol":
            if len(rest) != 1:
                print("Usage: field set <name> symbol <symbol>")
                return
            success = self.db.set_investment_symbol(name, rest[0])
            message = f"Symbol set for '{name}'."

        elif prop == "backing":
            if len(rest) != 1:
                print("Usage: field set <name> backing <asset> | field set <name> backing clear")
                return
            if rest[0].lower() == "clear":
                success = self.db.clear_backing(name)
                message = f"Backing link cleared for '{name}'."
            else:
                success = self.db.set_backing(name, rest[0])
                message = f"'{name}' now backed by '{rest[0]}'."

        elif prop == "replaces":
            if len(rest) != 1:
                print("Usage: field set <name> replaces <old-name>")
                return
            success = self.db.set_replaces(name, rest[0])
            message = f"'{name}' marked as successor of '{rest[0]}'."

        elif prop == "status":
            if len(rest) != 1:
                print("Usage: field set <name> status <status>")
                return
            success = self.db.set_status(name, rest[0])
            message = f"Status set for '{name}': {rest[0]}."

        else:
            print(f"Unknown property '{prop}'. Supported: note, apr, symbol, backing, replaces, status")
            return

        if success:
            print(message)
            self.logger.log(f"Field updated: {name} {prop}")
        else:
            print(
                f"Could not set {prop} for '{name}' — check the record exists, "
                "is active, and the category is valid for this property."
            )
