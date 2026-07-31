from .base import BaseCommand
from ..repl_shared import ExitSignal

class ExitCommand(BaseCommand):

    call_str = ["exit", "quit", "q"]

    USAGE = """
  exit / quit / q               Exit Vault
"""

    def entry_point(self, options: list):
        raise ExitSignal()
