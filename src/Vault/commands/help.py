from .base import BaseCommand

class HelpCommand(BaseCommand):

    call_str = ["help", "h"] # Tells the prompt the string command(s) in order to call this class

    USAGE = """
  help / h                      Show all Vault commands
  <command> usage               Detailed help for any command
"""

    HELP_TEXT = """
  Vault Commands:
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

    update                               Interactively stage values for all fields (default: current month)
    update <field> <value> [-m YYYY-MM]  Stage a value for a single field (value or quantity, per its category)

    commit                        Commit all pending staged updates to the database
    commit <n> [n ...]            Commit one or more pending updates by index
    commit undo                   Reverse the most recent commit
    commit undo <n>               Reverse the last N commits
    commit history                Show past commits, most recent first (reference for commit undo)

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

    investment override <field> <price>   Lock a manual price per unit for this field
    investment override <field> clear     Remove price lock (use live/cached price)
    investment list                       Show all investment records with current prices and source
    investment options                    Show known commodity symbols, names, and units
    investment refresh                    Re-fetch live prices for all investment records

    help / h                      Show this help message
    <command> usage               Detailed help for any command
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
