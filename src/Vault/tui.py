"""Fixed-layout full-screen TUI for the Vault REPL.

The VAULT header stays pinned at the top, each command's output refills one
fixed output pane in place, and the input line and status bar never move.
Only activates for a TTY stdin/stdout session (see `cli.py`); piped runs use
the scrolling `Prompt.render()` REPL unchanged.
"""

from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, VSplit, Window, WindowAlign
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import AppendAutoSuggestion, BeforeInput

from .helper import header_lines
from .prompt import (
    ExitSignal,
    VAULT_STYLE,
    _build_history,
    _build_prompt_message,
    _VaultCompleter,
    _VaultLexer,
)


class VaultApp:
    """Full-screen prompt_toolkit Application driving the fixed-layout REPL."""

    def __init__(self, prompt, *, input=None, output=None):
        self.prompt = prompt
        self._body: list[tuple[str, str]] = []

        self.input_buffer = Buffer(
            history=_build_history(prompt),
            completer=FuzzyCompleter(_VaultCompleter(prompt)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=False,
            multiline=False,
            accept_handler=self._on_accept,
        )

        header_control = FormattedTextControl(
            lambda: [("class:header", line) for line in header_lines(prompt.project_name.startswith("[TEST]"))]
        )
        header_window = Window(header_control, height=Dimension.exact(3))

        self.output_control = FormattedTextControl(lambda: self._body)
        output_window = Window(self.output_control, wrap_lines=False)

        rule_window = Window(
            FormattedTextControl(lambda: [("class:rule", "─" * 1000)]),
            height=Dimension.exact(1),
        )

        input_control = BufferControl(
            buffer=self.input_buffer,
            lexer=_VaultLexer(prompt),
            input_processors=[
                BeforeInput(_build_prompt_message(prompt.project_name)),
                AppendAutoSuggestion(),
            ],
        )
        input_window = Window(
            input_control,
            height=Dimension(min=1, max=5),
        )

        status_window = VSplit([
            Window(FormattedTextControl(self._toolbar_text)),
            Window(FormattedTextControl(self._rprompt_text), align=WindowAlign.RIGHT, dont_extend_width=True),
        ], height=Dimension.exact(1))

        self.root_container = FloatContainer(
            content=HSplit([
                header_window,
                output_window,
                rule_window,
                input_window,
                status_window,
            ]),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=MultiColumnCompletionsMenu(),
                ),
            ],
        )

        self.layout = Layout(self.root_container, focused_element=input_window)

        self.key_bindings = self._build_key_bindings()

        self.application = Application(
            layout=self.layout,
            style=VAULT_STYLE,
            key_bindings=self.key_bindings,
            full_screen=True,
            input=input,
            output=output,
        )

    def _toolbar_text(self):
        if self.prompt.status_line is None:
            return ""
        return self.prompt.status_line.toolbar_text()

    def _rprompt_text(self):
        if self.prompt.status_line is None:
            return ""
        return self.prompt.status_line.rprompt_text()

    def _build_key_bindings(self):
        kb = KeyBindings()

        @kb.add("c-d")
        def _exit_on_empty(event):
            if not event.current_buffer.text:
                event.app.exit(exception=ExitSignal())

        @kb.add("escape", "enter")
        def _insert_newline(event):
            event.current_buffer.insert_text("\n")

        return kb

    def _on_accept(self, buffer):
        text = buffer.text
        self._body = [("", f"{self.prompt.project_name}/> {text}")]
        return False

    def run(self):
        self.application.run()
