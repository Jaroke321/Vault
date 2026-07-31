import sys
from pathlib import Path

from .repl_shared import ExitSignal
from .routing import Route

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.shortcuts import CompleteStyle
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.key_binding import KeyBindings
except ImportError:
    PromptSession = None
    Style = None
    FormattedText = None
    Lexer = None
    KeyBindings = None


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
            """Walk `tokens` through `routes` via `Route.walk`, requiring a full
            match. Returns the reached node's children, or None if any token
            doesn't match (e.g. a runtime value like a field name)."""

            if not tokens:
                return routes

            route, remaining = Route.walk(routes, tokens)
            if route is None or remaining:
                return None
            return route.children

    class _VaultLexer(Lexer):
        def __init__(self, prompt):
            self._prompt = prompt

        def lex_document(self, document):
            def get_line(lineno):
                if lineno > 0:
                    lines = document.text.split("\n")
                    if lineno < len(lines):
                        return [("", lines[lineno])]
                    return []

                text = document.text
                if not text:
                    return [("", "")]

                index = 0
                while index < len(text) and text[index].isspace():
                    index += 1

                end = index
                while end < len(text) and not text[end].isspace():
                    end += 1

                first = text[index:end]
                if not first:
                    return [("", text)]

                style = (
                    "class:lexer.command.known"
                    if first in self._prompt.routes
                    else "class:lexer.command.unknown"
                )
                return [("", text[:index]), (style, first), ("", text[end:])]

            return get_line

    def _build_key_bindings(prompt):
        kb = KeyBindings()

        @kb.add("f2")
        def _show_pending(event):
            if prompt.status_line is not None:
                prompt.status_line.pending_commits.render()

        @kb.add("c-d")
        def _exit_on_empty(event):
            if not event.current_buffer.text:
                event.app.exit(exception=ExitSignal())

        @kb.add("escape", "enter")
        def _insert_newline(event):
            event.current_buffer.insert_text("\n")

        return kb


if PromptSession is not None:
    VAULT_STYLE = Style.from_dict({
        "status.default": "",
        "status.staged": "bold",
        "status.month": "ansicyan",
        "status.prices": "ansigreen",
        "status.test": "ansiyellow bold",
        "status.net": "ansimagenta",
        "prompt.test": "ansiyellow bold",
        "prompt.name": "ansicyan bold",
        "prompt.sep": "ansibrightblack",
        "lexer.command.known": "ansigreen bold",
        "lexer.command.unknown": "ansired",
        "header": "ansiyellow bold",
        "rule": "ansibrightblack",
    })
else:
    VAULT_STYLE = None


def _build_prompt_message(project_name):
    if project_name.startswith("[TEST] "):
        name = project_name.removeprefix("[TEST] ")
        return FormattedText([
            ("class:prompt.test", "[TEST]"),
            ("class:prompt.name", f" {name}"),
            ("class:prompt.sep", "/>"),
        ])
    return FormattedText([
        ("class:prompt.name", project_name),
        ("class:prompt.sep", "/>"),
    ])


def _build_history(prompt):
    """Build the FileHistory/InMemoryHistory backing a Vault REPL session."""
    if not prompt.history_path:
        return InMemoryHistory()

    try:
        history_file = Path(prompt.history_path)
        history_file.parent.mkdir(parents=True, exist_ok=True)
        if not history_file.exists():
            prompt.logger.log(
                f"[history] no existing history file at {prompt.history_path}, starting fresh"
            )
        return FileHistory(prompt.history_path)
    except OSError as e:
        prompt.logger.log(
            f"[history] failed to write history file {prompt.history_path}: {e}"
        )
        return InMemoryHistory()


def create_repl_session(prompt, *, input=None, output=None):
    """Build a PromptSession with the same settings as the interactive Vault REPL."""
    if PromptSession is None:
        raise RuntimeError("prompt_toolkit is required for an interactive REPL session")

    session_kwargs = dict(
        history=_build_history(prompt),
        completer=FuzzyCompleter(_VaultCompleter(prompt)),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        complete_while_typing=False,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=VAULT_STYLE,
        lexer=_VaultLexer(prompt),
        key_bindings=_build_key_bindings(prompt),
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
        self._prompt_message = (
            _build_prompt_message(project_name)
            if FormattedText is not None else None
        )

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
