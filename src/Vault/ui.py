"""Command UI injection contract for interactive REPL sessions.

``cli.py`` sets ``instance.ui`` to a ``TuiUi`` in fixed-layout mode, or
leaves it ``None`` for the classic scrolling REPL.
"""

from typing import Protocol

try:
    from prompt_toolkit.validation import Validator
except ImportError:
    Validator = object  # type: ignore[assignment,misc]


class ReplUi(Protocol):
    def confirm(self, message: str) -> bool:
        """Return True to proceed, False to cancel."""

    def ask(
        self,
        message: str,
        *,
        placeholder: str = "",
        validator: Validator | None = None,
    ) -> str:
        """Return the user's input; cancel raises KeyboardInterrupt."""
