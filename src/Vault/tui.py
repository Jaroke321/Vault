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
import io
import queue
import threading
import traceback

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, VSplit, Window, WindowAlign
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import AfterInput, AppendAutoSuggestion, BeforeInput, ConditionalProcessor
from prompt_toolkit.widgets import Button, Dialog, Label, TextArea

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


def _clip_line(line: list[tuple[str, str]], width: int) -> list[tuple[str, str]]:
    """Clip a line's (style, text) fragments to `width` visible columns.

    Fragments here already have ANSI separated into style tags by
    _split_ansi_lines, so this is plain text-width clipping across
    fragments -- no escape sequences to preserve, unlike truncate_ansi.
    """
    clipped: list[tuple[str, str]] = []
    remaining = width
    for style, text in line:
        if remaining <= 0:
            break
        if len(text) > remaining:
            clipped.append((style, text[:remaining]))
            remaining = 0
        else:
            clipped.append((style, text))
            remaining -= len(text)
    return clipped


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


class _Cancelled:
    """Sentinel pushed by a dialog's cancel path; `ask()` turns it into a
    synthesized KeyboardInterrupt on the worker thread, since Ctrl-C is no
    longer delivered as a signal once the terminal is in raw mode."""


_CANCELLED = _Cancelled()


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

    def ask(self, message: str, *, placeholder: str = "", validator=None) -> str:
        """Block the calling (worker) thread until the user submits or cancels a value.

        Raises KeyboardInterrupt (synthesized, not OS-delivered) if cancelled,
        matching what `pt_prompt` raised on Ctrl-C -- so callers written against
        the old `except KeyboardInterrupt` cancel path need no changes.
        """
        result_queue: queue.Queue = queue.Queue()

        def _show():
            def _dismiss():
                self._app.root_container.floats.remove(dialog_float)
                self._app.layout.focus(self._app.input_window)
                self.dialog_ready.clear()
                self._app.application.invalidate()

            def _submit():
                # TextArea only *displays* validation state -- it does not refuse
                # acceptance on its own when triggered via a button rather than Enter.
                if not text_area.buffer.validate():
                    return
                value = text_area.text
                _dismiss()
                result_queue.put(value)

            def _cancel():
                _dismiss()
                result_queue.put(_CANCELLED)

            is_empty = Condition(lambda: text_area.text == "")
            text_area = TextArea(
                multiline=False,
                validator=validator,
                input_processors=[
                    ConditionalProcessor(
                        AfterInput(placeholder, style="class:dialog.placeholder"),
                        filter=is_empty,
                    ),
                ],
                accept_handler=lambda buf: _submit() or False,
            )

            cancel_kb = KeyBindings()
            cancel_kb.add("escape")(lambda event: _cancel())
            existing_bindings = text_area.control.key_bindings
            text_area.control.key_bindings = (
                merge_key_bindings([existing_bindings, cancel_kb])
                if existing_bindings is not None
                else cancel_kb
            )

            dialog = Dialog(
                title="Input",
                body=HSplit([Label(text=message), text_area]),
                buttons=[
                    Button(text="OK", handler=_submit),
                    Button(text="Cancel", handler=_cancel),
                ],
                modal=True,
            )
            dialog_float = Float(content=dialog)
            self._app.root_container.floats.append(dialog_float)
            self._app.layout.focus(text_area)
            self.dialog_ready.set()
            self._app.application.invalidate()

        self._app.application.loop.call_soon_threadsafe(_show)
        value = result_queue.get()
        if value is _CANCELLED:
            raise KeyboardInterrupt
        return value


class VaultApp:
    """Full-screen prompt_toolkit Application driving the fixed-layout REPL."""

    def __init__(self, prompt, *, input=None, output=None):
        self.prompt = prompt
        self._body: list[list[tuple[str, str]]] = []
        self._busy = False
        self._scroll = 0
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

        self.output_control = FormattedTextControl(self._render_body)
        self.output_window = Window(self.output_control, wrap_lines=False)

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
                self.output_window,
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
        if self._busy:
            return [("class:rule", "running…")]
        total = len(self._body)
        if total == 0:
            return [("class:rule", "")]
        height = self._visible_height()
        first = min(self._scroll, max(total - 1, 0)) + 1
        last = min(self._scroll + height, total)
        return [("class:rule", f"lines {first}–{last} of {total} · PgUp/PgDn")]

    def _visible_height(self) -> int:
        """Best-known visible row count of the output pane.

        Prefers the Window's own render_info (accurate after the first paint,
        follows terminal resizes); falls back to the fixed chrome height
        (header 3 + rule 1 + input 1 + status 1) before anything has rendered.
        """
        render_info = self.output_window.render_info
        if render_info is not None:
            return render_info.window_height
        return max(self.application.output.get_size().rows - 6, 1)

    def _max_scroll(self) -> int:
        return max(len(self._body) - self._visible_height(), 0)

    def _clamp_scroll(self) -> None:
        self._scroll = max(0, min(self._scroll, self._max_scroll()))

    def _render_body(self):
        height = self._visible_height()
        render_info = self.output_window.render_info
        width = render_info.window_width if render_info is not None else 80
        visible = self._body[self._scroll:self._scroll + height]
        clipped = [_clip_line(line, width) for line in visible]
        return _join_lines(clipped)

    def _build_key_bindings(self):
        kb = KeyBindings()

        @kb.add("c-d")
        def _exit_on_empty(event):
            if not self._busy and not event.current_buffer.text:
                event.app.exit(exception=ExitSignal())

        @kb.add("escape", "enter")
        def _insert_newline(event):
            event.current_buffer.insert_text("\n")

        @kb.add("f2")
        def _show_pending(event):
            if self._busy or self.prompt.status_line is None:
                return
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.prompt.status_line.pending_commits.render()
            text = captured.getvalue()
            if not text:
                return
            self._body = _split_ansi_lines(text)
            self._scroll = 0

        @kb.add("pageup")
        def _scroll_up(event):
            self._scroll -= self._visible_height()
            self._clamp_scroll()

        @kb.add("pagedown")
        def _scroll_down(event):
            self._scroll += self._visible_height()
            self._clamp_scroll()

        @kb.add("c-home")
        def _scroll_top(event):
            self._scroll = 0

        @kb.add("c-end")
        def _scroll_bottom(event):
            self._scroll = self._max_scroll()

        return kb

    def _on_accept(self, buffer):
        text = buffer.text
        tokens = text.split()

        if not tokens:
            self._body = []
            self._scroll = 0
            return False

        command, options = self.prompt.validate_command(text)

        if command is None:
            echo = f"{self.prompt.project_name}/> {text}"
            lines = _split_ansi_lines(echo)
            lines.append([("", f"Unknown command '{tokens[0]}'. Type 'help' to see available commands.")])
            self._body = lines
            self._scroll = 0
            return False

        self._body = _split_ansi_lines(f"{self.prompt.project_name}/> {text}")
        self._scroll = 0
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
