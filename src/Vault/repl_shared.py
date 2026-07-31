"""Shared REPL infrastructure used by the classic and fixed-layout UIs."""

from pathlib import Path

from .routing import Route

try:
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.lexers import Lexer
except ImportError:
    Completer = None
    FormattedText = None
    KeyBindings = None
    Lexer = None


class ExitSignal(Exception):
    """Raised to leave the interactive REPL (exit command, Ctrl-D, etc.)."""


if Completer is not None:

    class VaultCompleter(Completer):
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

    class VaultLexer(Lexer):
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


if KeyBindings is not None:

    def build_common_key_bindings(*, on_f2, can_exit=lambda: True):
        """Shared Ctrl-D, Esc+Enter, and F2 bindings for both REPL modes."""
        kb = KeyBindings()

        @kb.add("f2")
        def _show_pending(event):
            on_f2()

        @kb.add("c-d")
        def _exit_on_empty(event):
            if can_exit() and not event.current_buffer.text:
                event.app.exit(exception=ExitSignal())

        @kb.add("escape", "enter")
        def _insert_newline(event):
            event.current_buffer.insert_text("\n")

        return kb


def build_prompt_message(project_name):
    if FormattedText is None:
        return None
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


def build_history(prompt):
    """Build the FileHistory/InMemoryHistory backing a Vault REPL session."""
    if InMemoryHistory is None:
        return None
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
