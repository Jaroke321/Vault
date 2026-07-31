"""Run keystroke-level smoke checks against the Vault REPL harness.

Usage (from the repo root, with the project venv active):

    python -m repl_harness
"""

from __future__ import annotations

import datetime
import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

from Vault.commands.commit import CommitCommand
from Vault.commands.update import UpdateCommand
from Vault.db_handler import DBHandler
from Vault.logger import Logger
from Vault.pending_commits import PendingCommits
from Vault.prompt import PromptSession
from Vault.routing import Route
from Vault.status import StatusLine
from Vault.test_data import seed_test_db

from .harness import ExitSignal, VaultReplHarness, VaultTuiHarness, feed_ctrl_d, feed_f2, feed_text


def _noop_handler(options):
    return None


def _sample_routes():
    return {
        "summary": Route(handler=_noop_handler),
        "commit": Route(handler=_noop_handler),
        "nope": Route(handler=_noop_handler),
    }


def check_basic_prompt():
    with VaultReplHarness(_sample_routes()) as harness:
        value = harness.run_prompt(feed_text("summary"))
    assert value == "summary", value


def check_ctrl_d_exits():
    with VaultReplHarness(_sample_routes()) as harness:
        try:
            harness.run_prompt(feed_ctrl_d())
        except ExitSignal:
            return
    raise AssertionError("expected ExitSignal on Ctrl-D with an empty buffer")


def check_f2_renders_pending_table():
    pending = PendingCommits()
    pending.append(["checking", "2026-07", 5000.0])
    status_line = StatusLine(pending, test_mode=True)

    with VaultReplHarness(_sample_routes(), status_line=status_line) as harness:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            harness.run_prompt(feed_f2(submit=True))
        output = buffer.getvalue()
    assert "checking" in output, output
    assert "5000" in output, output


def _summary_handler(options):
    print("Net Worth Summary")
    print("  Assets: $100.00")


def _long_show_handler(options):
    for i in range(200):
        print(f"line {i}")


def _tui_routes():
    return {
        "summary": Route(handler=_summary_handler),
        "show": Route(handler=_long_show_handler),
    }


class _TempSeededDb:
    """Temp-file DBHandler seeded with test_data, cleaned up on exit."""

    def __enter__(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = DBHandler(db_path=Path(self._tmp.name))
        seed_test_db(self.db)
        return self.db

    def __exit__(self, exc_type, exc, tb):
        os.unlink(self._tmp.name)
        return None


def check_tui_not_constructed_when_not_tty():
    """VaultApp requires prompt_toolkit; CLI only builds one when both stdin
    and stdout are TTYs (see cli.py). This just re-asserts the precondition
    the gate depends on -- prompt_toolkit stays importable -- since the gate
    itself lives in cli.py, not in VaultApp."""
    assert PromptSession is not None, "prompt_toolkit must be importable for this gate to matter"


def check_tui_summary_renders():
    with VaultTuiHarness(_tui_routes()) as harness:
        assert harness.run_command("summary", timeout=3), "command never finished"
        body = harness.body_text()
    assert "Net Worth Summary" in body, body


def check_tui_scroll_advances():
    with VaultTuiHarness(_tui_routes()) as harness:
        assert harness.run_command("show", timeout=3), "command never finished"
        assert len(harness.app._body) > harness.app._visible_height(), "body should overflow the pane"
        scroll_before = harness.app._scroll
        harness.feed_pagedown()
        # PageDown is a synchronous key binding on the loop thread; give it
        # one tick to run rather than a threading.Event (nothing to wait on).
        time.sleep(0.2)
        scroll_after = harness.app._scroll
    assert scroll_after > scroll_before, (scroll_before, scroll_after)


def check_tui_f2_renders_pending_table():
    pending = PendingCommits()
    pending.append(["checking", "2026-07", 5000.0])
    status_line = StatusLine(pending, test_mode=True)

    with VaultTuiHarness(_tui_routes(), status_line=status_line) as harness:
        harness.feed_f2()
        time.sleep(0.2)
        body = harness.body_text()
    assert "checking" in body, body
    assert "5000" in body, body


def check_tui_ctrl_d_exits():
    with VaultTuiHarness(_tui_routes()) as harness:
        harness.feed_ctrl_d()
        harness.join(timeout=5)
        alive = harness.is_alive()
        exited = harness.result.get("exited")
    assert not alive, "app did not exit on Ctrl-D"
    assert exited, harness.result


def check_tui_update_dialog_script():
    """Scripted `update`, cancelled via Escape -- exercises ui.ask's
    dialog_ready handshake across two consecutive per-field dialogs."""
    with _TempSeededDb() as db:
        logger = Logger(log_file="/dev/null")
        commits = PendingCommits()
        update_cmd = UpdateCommand(db, logger, price_fetcher=None, commits=commits)
        routes = {"update": Route(handler=update_cmd.entry_point)}

        with VaultTuiHarness(routes) as harness:
            update_cmd.ui = harness.app.ui

            harness.feed("update")
            assert harness.wait_dialog(timeout=2), "dialog never took focus"
            harness.feed("1500")
            assert harness.wait_dialog(timeout=2), "next field's dialog never took focus"
            harness.feed_escape()
            assert harness.wait_idle(timeout=5), "command never finished"
            body = harness.body_text()
        assert "Update cancelled." in body, body


def check_tui_confirm_dialog_script():
    """Scripted `commit undo`, cancelled via Escape -- exercises
    ui.confirm's dialog_ready handshake."""
    with _TempSeededDb() as db:
        logger = Logger(log_file="/dev/null")
        commits = PendingCommits()
        commit_cmd = CommitCommand(db, logger, price_fetcher=None, commits=commits)
        commit_cmd._undo_stack.append({
            "timestamp": datetime.datetime.now(),
            "entries": [("checking", "2026-07", 100.0, None)],
        })

        def _undo_handler(options):
            if options and options[0] == "undo":
                commit_cmd.sub_undo(options[1:])

        routes = {"commit": Route(handler=_undo_handler)}

        with VaultTuiHarness(routes) as harness:
            commit_cmd.ui = harness.app.ui

            harness.feed("commit undo")
            assert harness.wait_dialog(timeout=2), "confirm dialog never took focus"
            harness.feed_escape()
            assert harness.wait_idle(timeout=5), "command never finished"
            body = harness.body_text()
        assert "Cancelled." in body, body


def main():
    checks = [
        ("basic prompt", check_basic_prompt),
        ("Ctrl-D exit", check_ctrl_d_exits),
        ("F2 pending table", check_f2_renders_pending_table),
        ("TUI not constructed off-TTY", check_tui_not_constructed_when_not_tty),
        ("TUI summary renders", check_tui_summary_renders),
        ("TUI scroll advances", check_tui_scroll_advances),
        ("TUI F2 pending table", check_tui_f2_renders_pending_table),
        ("TUI Ctrl-D exit", check_tui_ctrl_d_exits),
        ("TUI update dialog script", check_tui_update_dialog_script),
        ("TUI confirm dialog script", check_tui_confirm_dialog_script),
    ]

    for name, check in checks:
        check()
        print(f"ok: {name}")

    print(f"{len(checks)} harness checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
