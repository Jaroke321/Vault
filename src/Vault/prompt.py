import sys

from .repl_shared import (
    ExitSignal,
    VaultCompleter,
    VaultLexer,
    build_common_key_bindings,
    build_history,
    build_prompt_message,
)
from .routing import Route
from .theme import build_ptk_style

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import FuzzyCompleter
    from prompt_toolkit.shortcuts import CompleteStyle
except ImportError:
    PromptSession = None


def create_repl_session(prompt, *, input=None, output=None):
    """Build a PromptSession with the same settings as the interactive Vault REPL."""
    if PromptSession is None:
        raise RuntimeError("prompt_toolkit is required for an interactive REPL session")

    session_kwargs = dict(
        history=build_history(prompt),
        completer=FuzzyCompleter(VaultCompleter(prompt)),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        complete_while_typing=False,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=build_ptk_style(),
        lexer=VaultLexer(prompt),
        key_bindings=build_common_key_bindings(
            on_f2=lambda: (
                prompt.status_line.pending_commits.render()
                if prompt.status_line is not None
                else None
            ),
        ),
    )
    if prompt.status_line is not None:
        session_kwargs["bottom_toolbar"] = prompt._status_line
        session_kwargs["rprompt"] = prompt._rprompt
    if input is not None:
        session_kwargs["input"] = input
    if output is not None:
        session_kwargs["output"] = output

    return PromptSession(**session_kwargs)


class Prompt:
    """Interactive Vault REPL prompt (prompt_toolkit when available).

    Interactive-only features (completion, toolbar, key bindings, styled input)
    require a TTY. Piped ``vault --test`` sets ``self.interactive`` to False and
    falls back to plain ``input()``. Keystroke-level behavior can be checked with
    ``python -m repl_harness`` (see README).
    """

    def __init__(self, project_name, logger, routes,
                 history_path=None, *, status_line=None):

        self.project_name = project_name
        self.logger = logger
        self.routes = routes
        self.history_path = history_path
        self.status_line = status_line
        self._prompt_str = f"{project_name}/>"
        self._prompt_message = build_prompt_message(project_name)

        self.interactive = PromptSession is not None and sys.stdin.isatty()
        self._session = None

    def render(self):

        if self.interactive:
            self._build_session()

        try:
            while True:
                command_input = self._read_line()
                command, options = self.validate_command(command_input)

                if command is None:
                    continue

                command(options)

                if self.status_line is not None:
                    self.status_line.refresh_net_worth()

                # it might be cool to be able to handle return values from the called function
                # This would be relevant since the command classes are calling an entry point functin
                # Right now the entry point function handles its own sub commands
                # But what if the entry point can return back a dict with sub commands
                # and then sub commands can return back more dicts with sub commands
                # could potentially allow for more complex and dynamic decision trees

        except ExitSignal:
            pass

        print("Exiting Vault...")

    def _read_line(self):
        try:
            if self.interactive and self._session is not None:
                return self._session.prompt(self._prompt_message)
            return input(self._prompt_str)
        except ExitSignal:
            raise
        except (EOFError, KeyboardInterrupt):
            raise ExitSignal() from None

    def _build_session(self):
        if self._session is not None:
            return
        self._session = create_repl_session(self)

    def _status_line(self):
        return self.status_line.toolbar_text()

    def _rprompt(self):
        return self.status_line.rprompt_text()

    def validate_command(self, command: str):

        cmdlets = command.split(" ")

        route, remaining = Route.walk(self.routes, cmdlets)
        if route is not None:
            return route.handler, remaining

        if not self.interactive:
            print(f"Unknown command '{cmdlets[0]}'. Type 'help' to see available commands.")
        return None, None
