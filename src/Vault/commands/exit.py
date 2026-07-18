from .base import BaseCommand
from ..prompt import ExitSignal

class ExitCommand(BaseCommand):

    call_str = ["exit", "quit", "q"]

    def entry_point(self, options: list):
        raise ExitSignal()
