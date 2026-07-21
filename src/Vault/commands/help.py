from .base import BaseCommand

class HelpCommand(BaseCommand):

    call_str = ["help", "h"] # Tells the prompt the string command(s) in order to call this class

    HELP_TEXT = """
  Vault Commands:
    field add <category> <name>          Register a new tracked field
    field remove <name>                  Deactivate a field (history preserved)
    field list                           Show all active fields by category
    field set <category> unit <unit>     Set display unit for a category (default: $)

    update                               Interactively stage values for all fields (default: current month)
    update <field> <value> [-m YYYY-MM]  Stage a value for a single field
    update <field> <value> <asset> [-m YYYY-MM]  Stage value + asset for a debt field

    commit                        Commit all pending staged updates to the database
    commit <n> [n ...]            Commit one or more pending updates by index

    show / s                      Table of last 6 months across all fields
    show <n>                      Table of last N months across all fields
    show <field>                  Month-over-month trend for one field
    show <field> <n>              Trend for one field over last N months

    diff <m1> <y1> <m2> <y2>      Compare all fields between two months
    diff <field> <m1> <y1> <m2> <y2>   Compare one field between two months

    summary                       Net worth snapshot (assets minus debts)

    export csv                    Dump full recorded history to CSV (stdout)
    export csv <filename>         Dump full recorded history to CSV (file)
    import csv <filename>         Import a wide-format CSV back into the database

    commodity tag <field> <commodity>     Tag a field as a commodity (e.g. 'gold' or 'XAU')
    commodity untag <field>               Remove commodity tag from a field
    commodity override <field> <price>    Lock a manual price per unit for this field
    commodity override <field> clear      Remove price lock (use live/cached price)
    commodity list                        Show all tagged fields with current prices and source
    commodity refresh                     Re-fetch live prices for all tagged fields

    help / h                      Show this help message
    exit / quit / q               Exit Vault
        """

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        self._print_help()

    ####################################
    # Rendering
    ####################################
    def _print_help(self):
        print(self.HELP_TEXT)
