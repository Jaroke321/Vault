"""Fixed-layout full-screen TUI for the Vault REPL.

The VAULT header stays pinned at the top, each command's output refills one
fixed output pane in place, and the input line and status bar never move.
Only activates for a TTY stdin/stdout session (see `cli.py`); piped runs use
the scrolling `Prompt.render()` REPL unchanged.

Thread invariant: command handlers run on a worker thread (via
run_in_executor) so a slow command can't freeze the UI's event loop. That
worker thread may only *append* to `VaultApp._body` (via `_PaneWriter`) --
list.append and slicing are atomic under the GIL, so concurrent reads from
the render loop are safe. Everything else -- clearing the body, floats,
focus, `_busy`, `_scroll` -- is touched only on the asyncio loop thread,
scheduled with `call_soon_threadsafe` from the worker when needed.
"""

import asyncio
import contextlib
import queue
import threading
import traceback

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, VSplit, Window, WindowAlign
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import AppendAutoSuggestion, BeforeInput
from prompt_toolkit.widgets import Button, Dialog, Label

from .helper import header_lines
from .prompt import (
    ExitSignal,
    VAULT_STYLE,
    _build_history,
    _build_prompt_message,
    _VaultCompleter,
    _VaultLexer,
)


def _split_ansi_lines(text: str) -> list[list[tuple[str, str]]]:
    """Parse ANSI escapes in `text` and split the styled fragments on newlines."""
    lines: list[list[tuple[str, str]]] = [[]]
    for style, chunk in to_formatted_text(ANSI(text)):
        parts = chunk.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((style, part))
    return lines


def _join_lines(lines: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    """Flatten per-line fragment lists back into one fragment list with newlines."""
    joined: list[tuple[str, str]] = []
    for i, line in enumerate(lines):
        if i > 0:
            joined.append(("", "\n"))
        joined.extend(line)
    return joined


class _PaneWriter:
    """A stdout/stderr replacement that streams completed lines into `app._body`.

    Runs on the worker thread. Buffers text until a newline, then parses the
    completed line's ANSI and appends it to `app._body` -- the one mutation
    the worker thread is allowed to make directly (see module docstring).
    Invalidation is scheduled back onto the loop thread and throttled so a
    command printing many lines doesn't flood the render loop with redraws.
    """

    _THROTTLE_SECONDS = 0.05

    def __init__(self, app: "VaultApp", loop: asyncio.AbstractEventLoop):
        self._app = app
        self._loop = loop
        self._pending = ""
        self._invalidate_scheduled = False

    def write(self, text: str) -> int:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._app._body.append(_split_ansi_lines(line)[0])
        self._schedule_invalidate()
        return len(text)

    def flush(self) -> None:
        pass

    def finish(self) -> None:
        """Flush any partial last line (one with no trailing newline)."""
        if self._pending:
            self._app._body.append(_split_ansi_lines(self._pending)[0])
            self._pending = ""
        self._loop.call_soon_threadsafe(self._app.application.invalidate)

    def _schedule_invalidate(self) -> None:
        if self._invalidate_scheduled:
            return
        self._invalidate_scheduled = True

        def _arm_timer():
            self._loop.call_later(self._THROTTLE_SECONDS, _fire)

        def _fire():
            self._invalidate_scheduled = False
            self._app.application.invalidate()

        self._loop.call_soon_threadsafe(_arm_timer)


class TuiUi:
    """Modal dialogs for commands that need to ask the user something.

    Every method here is called from the worker thread (see the module
    docstring's thread invariant) and blocks that thread on a `queue.Queue`
    while the dialog is shown on the loop thread. `dialog_ready` is the
    handshake a test harness needs to feed keystrokes without racing the
    dialog's Float being posted and taking focus.
    """

    def __init__(self, app: "VaultApp"):
        self._app = app
        self.dialog_ready = threading.Event()

    def confirm(self, message: str) -> bool:
        """Block the calling (worker) thread until the user picks Yes/No."""
        result_queue: queue.Queue[bool] = queue.Queue()

        def _show():
            def _respond(value: bool):
                self._app.root_container.floats.remove(dialog_float)
                self._app.layout.focus(self._app.input_window)
                self.dialog_ready.clear()
                self._app.application.invalidate()
                result_queue.put(value)

            dialog = Dialog(
                title="Confirm",
                body=Label(text=message),
                buttons=[
                    Button(text="Yes", handler=lambda: _respond(True)),
                    Button(text="No", handler=lambda: _respond(False)),
                ],
                modal=True,
            )
            dialog_float = Float(content=dialog)
            self._app.root_container.floats.append(dialog_float)
            self._app.layout.focus(dialog)
            self.dialog_ready.set()
            self._app.application.invalidate()

        self._app.application.loop.call_soon_threadsafe(_show)
        return result_queue.get()


class VaultApp:
    """Full-screen prompt_toolkit Application driving the fixed-layout REPL."""

    def __init__(self, prompt, *, input=None, output=None):
        self.prompt = prompt
        self._body: list[list[tuple[str, str]]] = []
        self._busy = False
        self.idle = threading.Event()
        self.idle.set()

        self.input_buffer = Buffer(
            history=_build_history(prompt),
            completer=FuzzyCompleter(_VaultCompleter(prompt)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=False,
            multiline=False,
            read_only=Condition(lambda: self._busy),
            accept_handler=self._on_accept,
        )

        header_control = FormattedTextControl(
            lambda: [("class:header", line) for line in header_lines(prompt.project_name.startswith("[TEST]"))]
        )
        header_window = Window(header_control, height=Dimension.exact(3))

        self.output_control = FormattedTextControl(lambda: _join_lines(self._body))
        output_window = Window(self.output_control, wrap_lines=False)

        rule_window = Window(
            FormattedTextControl(self._rule_text),
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
        self.input_window = Window(
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
                self.input_window,
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

        self.layout = Layout(self.root_container, focused_element=self.input_window)

        self.key_bindings = self._build_key_bindings()

        self.application = Application(
            layout=self.layout,
            style=VAULT_STYLE,
            key_bindings=self.key_bindings,
            full_screen=True,
            input=input,
            output=output,
        )

        self.ui = TuiUi(self)

    def _toolbar_text(self):
        if self.prompt.status_line is None:
            return ""
        return self.prompt.status_line.toolbar_text()

    def _rprompt_text(self):
        if self.prompt.status_line is None:
            return ""
        return self.prompt.status_line.rprompt_text()

    def _rule_text(self):
        return [("class:rule", "running…" if self._busy else "")]

    def _build_key_bindings(self):
        kb = KeyBindings()

        @kb.add("c-d")
        def _exit_on_empty(event):
            if not self._busy and not event.current_buffer.text:
                event.app.exit(exception=ExitSignal())

        @kb.add("escape", "enter")
        def _insert_newline(event):
            event.current_buffer.insert_text("\n")

        return kb

    def _on_accept(self, buffer):
        text = buffer.text
        tokens = text.split()

        if not tokens:
            self._body = []
            return False

        command, options = self.prompt.validate_command(text)

        if command is None:
            echo = f"{self.prompt.project_name}/> {text}"
            lines = _split_ansi_lines(echo)
            lines.append([("", f"Unknown command '{tokens[0]}'. Type 'help' to see available commands.")])
            self._body = lines
            return False

        self._body = _split_ansi_lines(f"{self.prompt.project_name}/> {text}")
        self._busy = True
        self.idle.clear()
        get_app().create_background_task(self._dispatch(command, options))
        return False

    async def _dispatch(self, command, options):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._run_blocking, loop, command, options)
        finally:
            self._busy = False
            self.idle.set()
            self.application.invalidate()

    def _run_blocking(self, loop, command, options):
        """Run `command(options)` on the worker thread, streaming its output into the pane."""
        writer = _PaneWriter(self, loop)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                command(options)
        except ExitSignal:
            writer.finish()
            loop.call_soon_threadsafe(lambda: self.application.exit(exception=ExitSignal()))
            return
        except BaseException:
            writer.write(traceback.format_exc())
        writer.finish()

        if self.prompt.status_line is not None:
            self.prompt.status_line.refresh_net_worth()

    def run(self):
        self.application.run()
