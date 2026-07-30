"""Run keystroke-level smoke checks against the Vault REPL harness.

Usage (from the repo root, with the project venv active):

    python -m repl_harness
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from Vault.pending_commits import PendingCommits
from Vault.routing import Route
from Vault.status import StatusLine

from .harness import ExitSignal, VaultReplHarness, feed_ctrl_d, feed_f2, feed_text


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


def main():
    checks = [
        ("basic prompt", check_basic_prompt),
        ("Ctrl-D exit", check_ctrl_d_exits),
        ("F2 pending table", check_f2_renders_pending_table),
    ]

    for name, check in checks:
        check()
        print(f"ok: {name}")

    print(f"{len(checks)} harness checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
