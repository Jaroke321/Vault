"""Shared REPL infrastructure used by the classic and fixed-layout UIs."""


class ExitSignal(Exception):
    """Raised to leave the interactive REPL (exit command, Ctrl-D, etc.)."""
