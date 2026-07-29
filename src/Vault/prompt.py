import sys
from pathlib import Path

from .routing import Route

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import CompleteStyle, Completer, Completion
    from prompt_toolkit.history import FileHistory, InMemoryHistory
except ImportError:
    PromptSession = None


class ExitSignal(Exception):
    pass


if PromptSession is not None:

    class _VaultCompleter(Completer):
        def __init__(self, prompt):
            self._prompt = prompt

        def get_completions(self, document, complete_event):
            word = document.get_word_before_cursor(WORD=True)
            text_before = document.text_before_cursor
            tokens_before = text_before.split()

            # The word being completed is never itself "typed" yet, so only the
            # tokens before it need to fully match a route.
            if not tokens_before or text_before.endswith(" "):
                complete_tokens = tokens_before
            else:
                complete_tokens = tokens_before[:-1]

            children = self._reached_children(self._prompt.routes, complete_tokens)
            if children is None:
                return

            for name in sorted(n for n in children if n.startswith(word)):
                usage = children[name].usage or ""
                meta = usage.split("\n")[0] if usage else None
                yield Completion(name, start_position=-len(word), display_meta=meta)

        @staticmethod
        def _reached_children(routes, tokens):
            """Walk `tokens` through `routes`, requiring each to match a child
            exactly. Returns the children dict at the end, or None if any token
            doesn't match (e.g. a runtime value like a field name)."""

            children = routes
            for tok in tokens:
                if tok not in children:
                    return None
                children = children[tok].children
            return children


class Prompt:
    """Base class for prompt engine.

    Note: `vault --test` pipes commands via stdin, so `sys.stdin.isatty()` is
    always False there and `self.interactive` is always False in that harness.
    Tab-completion, completion metadata, and history persistence are only
    reachable in a real interactive session, so they can't be exercised by the
    piped-stdin test flow — verify them manually (see README).
    """

    def __init__(self, project_name, logger, routes,
                 history_path=None, state_data_viewer=None):

        self.project_name = project_name
        self.logger = logger
        self.routes = routes
        self.history_path = history_path
        self.state_data_viewer = state_data_viewer
        self._prompt_str = f"{project_name}/>"

        self.interactive = PromptSession is not None and sys.stdin.isatty()
        self._session = None

    def render(self):

        if self.interactive:
            self._build_session()

        command_input = self._read_line()

        while True:

            command, options = self.validate_command(command_input)

            if command is not None:
                try:
                    command(options)
                except ExitSignal:
                    break

                # it might be cool to be able to handle return values from the called function
                # This would be relevant since the command classes are calling an entry point functin
                # Right now the entry point function handles its own sub commands
                # But what if the entry point can return back a dict with sub commands
                # and then sub commands can return back more dicts with sub commands
                # could potentially allow for more complex and dynamic decision trees


            if(self.state_data_viewer):
                self.state_data_viewer()

            command_input = self._read_line()

        print("Exiting Vault...")

    def _read_line(self):
        if self.interactive and self._session is not None:
            return self._session.prompt(self._prompt_str)
        return input(self._prompt_str)

    def _build_session(self):
        if self._session is not None:
            return

        if self.history_path:
            try:
                history_file = Path(self.history_path)
                history_file.parent.mkdir(parents=True, exist_ok=True)
                if not history_file.exists():
                    self.logger.log(
                        f"[history] no existing history file at {self.history_path}, starting fresh"
                    )
                history = FileHistory(self.history_path)
            except OSError as e:
                self.logger.log(
                    f"[history] failed to write history file {self.history_path}: {e}"
                )
                history = InMemoryHistory()
        else:
            history = InMemoryHistory()

        self._session = PromptSession(
            history=history,
            completer=_VaultCompleter(self),
            complete_while_typing=False,
            complete_style=CompleteStyle.MULTI_COLUMN,
        )

    def validate_command(self, command: str):

        cmdlets = command.split(" ")

        route, remaining = Route.walk(self.routes, cmdlets)
        if route is not None:
            return route.handler, remaining

        print(f"Unknown command '{cmdlets[0]}'. Type 'help' to see available commands.")
        return None, None
