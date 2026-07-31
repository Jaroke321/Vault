"""Pipe-input harness for keystroke-level Vault REPL checks."""

from __future__ import annotations

import threading
import time
from contextlib import AbstractContextManager
from typing import Callable

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from Vault.logger import Logger
from Vault.prompt import ExitSignal, Prompt, create_repl_session
from Vault.tui import VaultApp, _join_lines

FeedFn = Callable[..., None]


class VaultReplHarness(AbstractContextManager):
    """Context manager that exposes a pipe-driven Vault PromptSession."""

    def __init__(
        self,
        routes,
        *,
        status_line=None,
        project_name: str = "Vault",
        logger=None,
        history_path=None,
    ):
        self.prompt = Prompt(
            project_name=project_name,
            logger=logger or Logger(log_file="/dev/null"),
            routes=routes,
            history_path=history_path,
            status_line=status_line,
        )
        self.pipe = None
        self.output = None
        self.session = None
        self._pipe_cm = None

    def __enter__(self):
        self._pipe_cm = create_pipe_input()
        self.pipe = self._pipe_cm.__enter__()
        self.output = DummyOutput()
        self.session = create_repl_session(
            self.prompt,
            input=self.pipe,
            output=self.output,
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._pipe_cm is not None:
            return self._pipe_cm.__exit__(exc_type, exc, tb)
        return None

    def run_prompt(self, feed: FeedFn, *, message=None, timeout: float = 5.0):
        """Run one prompt in a worker thread while `feed(self.pipe)` sends keys."""
        result: dict = {"value": None, "error": None}
        prompt_message = self.prompt._prompt_message if message is None else message

        def worker():
            try:
                result["value"] = self.session.prompt(prompt_message)
            except BaseException as exc:
                result["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        feed(self.pipe)
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError("prompt did not complete within the timeout")

        if result["error"] is not None:
            raise result["error"]
        return result["value"]


class VaultTuiHarness(AbstractContextManager):
    """Context manager that runs a VaultApp over a pipe in a worker thread.

    Unlike VaultReplHarness (one PromptSession.prompt() call per check),
    VaultApp.run() is a single long-running Application.run() -- the app
    starts once in __enter__ and keeps running until fed Ctrl-D or an
    ExitSignal-raising command. Feed keystrokes with `feed()` and assert on
    `app.idle` / `app.ui.dialog_ready` between feeds rather than feeding
    everything at once: a modal dialog is a second consumer of pipe bytes
    separated in time from the input line, and which one a keystroke reaches
    depends on who holds focus when it's read. Feeding in one shot risks
    keystrokes landing on the wrong side of that handshake -- see step 16 of
    plans/fixedlayouttui.md for the race this avoids.
    """

    def __init__(
        self,
        routes,
        *,
        status_line=None,
        project_name: str = "Vault",
        logger=None,
        history_path=None,
    ):
        self.prompt = Prompt(
            project_name=project_name,
            logger=logger or Logger(log_file="/dev/null"),
            routes=routes,
            history_path=history_path,
            status_line=status_line,
        )
        self.pipe = None
        self.output = None
        self.app: VaultApp | None = None
        self._pipe_cm = None
        self._thread: threading.Thread | None = None
        self.result: dict = {}

    def __enter__(self):
        self._pipe_cm = create_pipe_input()
        self.pipe = self._pipe_cm.__enter__()
        self.output = DummyOutput()
        self.app = VaultApp(self.prompt, input=self.pipe, output=self.output)

        def worker():
            try:
                self.app.run()
            except ExitSignal:
                self.result["exited"] = True
            except BaseException as exc:
                self.result["error"] = exc

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._thread is not None and self._thread.is_alive():
            self.feed_ctrl_d()
            self._thread.join(timeout=5)
        if self._pipe_cm is not None:
            return self._pipe_cm.__exit__(exc_type, exc, tb)
        return None

    def feed(self, text: str, *, submit: bool = True) -> None:
        self.pipe.send_text(text)
        if submit:
            self.pipe.send_text("\r")

    def feed_ctrl_d(self) -> None:
        self.pipe.send_bytes(b"\x04")

    def feed_escape(self) -> None:
        self.pipe.send_bytes(b"\x1b")

    def feed_f2(self) -> None:
        self.pipe.send_bytes(b"\x1b[12~")

    def feed_pagedown(self) -> None:
        self.pipe.send_bytes(b"\x1b[6~")

    def feed_pageup(self) -> None:
        self.pipe.send_bytes(b"\x1b[5~")

    def run_command(self, text: str, *, timeout: float = 5.0) -> bool:
        """Feed a full command line and wait for it to finish dispatching.

        `app.idle` starts pre-set (nothing is running yet), so a bare
        `feed()` + `wait_idle()` can't tell "never started" from "already
        finished" -- both read as set. Clearing it here, immediately before
        the feed that will (eventually) re-set it, removes that ambiguity:
        by the time `feed()` returns, idle is guaranteed clear until
        dispatch completes, so the wait below can only return True once
        _on_accept has actually run and the worker has finished.
        """
        self.app.idle.clear()
        self.feed(text)
        return self.app.idle.wait(timeout)

    def wait_idle(self, timeout: float = 5.0) -> bool:
        return self.app.idle.wait(timeout)

    def wait_dialog(self, timeout: float = 2.0) -> bool:
        return self.app.ui.dialog_ready.wait(timeout)

    def body_text(self) -> str:
        return "".join(text for _, text in _join_lines(self.app._body))

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)


def feed_text(text: str, *, submit: bool = True) -> FeedFn:
    def _feed(pipe):
        pipe.send_text(text)
        if submit:
            pipe.send_text("\r")

    return _feed


def feed_ctrl_d() -> FeedFn:
    def _feed(pipe):
        pipe.send_bytes(b"\x04")

    return _feed


def feed_f2(*, submit: bool = False) -> FeedFn:
    def _feed(pipe):
        pipe.send_bytes(b"\x1b[12~")
        if submit:
            pipe.send_text("\r")

    return _feed


__all__ = [
    "VaultReplHarness",
    "VaultTuiHarness",
    "ExitSignal",
    "feed_text",
    "feed_ctrl_d",
    "feed_f2",
]
