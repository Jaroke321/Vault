"""Pipe-input harness for keystroke-level Vault REPL checks."""

from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from typing import Callable

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from Vault.logger import Logger
from Vault.prompt import ExitSignal, Prompt, create_repl_session

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


__all__ = ["VaultReplHarness", "ExitSignal", "feed_text", "feed_ctrl_d", "feed_f2"]
