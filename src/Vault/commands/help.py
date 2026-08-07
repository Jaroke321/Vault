from .base import BaseCommand


class HelpCommand(BaseCommand):

    call_str = ["help", "h"] # Tells the prompt the string command(s) in order to call this class

    USAGE = """
  help / h                      Show all Vault commands
  <command> usage               Detailed help for any command
"""

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        self._print_help()

    ####################################
    # Rendering
    ####################################
    def _print_help(self):
        from . import COMMAND_CLASSES

        print("\n  Vault Commands:")
        sections = []
        for cls in COMMAND_CLASSES:
            usage = cls.USAGE.lstrip("\n").rstrip()
            if not usage:
                continue
            # USAGE lines are 2-space indented; overview help uses 4 spaces under the header.
            lines = [f"  {line}" for line in usage.splitlines()]
            sections.append("\n".join(lines))
        print("\n\n".join(sections))
