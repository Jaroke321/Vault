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

            # Assumes exactly one level of subcommands: a token-count heuristic against
            # a flat dict[str, list[str]]. A command with a second level of subcommands
            # won't error here — it'll silently complete against the wrong list. A
            # token-path lookup would be needed to support deeper nesting.
            if not tokens_before or (
                len(tokens_before) <= 1 and not text_before.endswith(" ")
            ):
                for name in sorted(
                    n for n in self._prompt.cmd_dict if n.startswith(word)
                ):
                    usage = self._prompt.command_usage.get(name, "")
                    meta = usage.split("\n")[0] if usage else None
                    yield Completion(
                        name, start_position=-len(word), display_meta=meta
                    )
            else:
                cmd = tokens_before[0]
                subcommands = self._prompt.subcommands.get(cmd, [])
                for name in sorted(
                    n for n in subcommands if n.startswith(word)
                ):
                    yield Completion(name, start_position=-len(word))


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
