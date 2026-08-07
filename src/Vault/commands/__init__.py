from .base import BaseCommand
from .field import FieldCommand
from .update import UpdateCommand
from .commit import CommitCommand
from .summary import SummaryCommand
from .show import ShowCommand
from .diff import DiffCommand
from .help import HelpCommand
from .investment import InvestmentCommand
from .export import ExportCommand
from .import_ import ImportCommand
from .exit import ExitCommand

# Single registration point for CLI routing and generated help — add new commands here.
COMMAND_CLASSES: list[type[BaseCommand]] = [
    FieldCommand,
    UpdateCommand,
    CommitCommand,
    ShowCommand,
    DiffCommand,
    SummaryCommand,
    ExportCommand,
    ImportCommand,
    InvestmentCommand,
    HelpCommand,
    ExitCommand,
]

__all__ = [
    "COMMAND_CLASSES",
    "FieldCommand",
    "UpdateCommand",
    "CommitCommand",
    "SummaryCommand",
    "ShowCommand",
    "DiffCommand",
    "HelpCommand",
    "InvestmentCommand",
    "ExportCommand",
    "ImportCommand",
    "ExitCommand",
]
