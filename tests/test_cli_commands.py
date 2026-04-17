"""Integration tests for CLI command methods.

Commands are called directly (bypassing the REPL) with a test DB and logger.
The `cli` and `seeded_db` fixtures are defined in conftest.py.
"""
import pytest
from conftest import seed_db


# ---------------------------------------------------------------------------
# cmd_field
# ---------------------------------------------------------------------------

def test_cmd_field_no_args_prints_usage(cli, capsys):
    cli.cmd_field([])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cmd_field_add(cli):
    cli.cmd_field(["add", "savings", "checking"])
    fields = [row[0] for row in cli.db.get_active_fields()]
    assert "checking" in fields


def test_cmd_field_add_duplicate(cli, capsys):
    cli.cmd_field(["add", "savings", "checking"])
    cli.cmd_field(["add", "savings", "checking"])
    out = capsys.readouterr().out
    assert "already exists" in out


def test_cmd_field_remove(cli):
    cli.cmd_field(["add", "savings", "checking"])
    cli.cmd_field(["remove", "checking"])
    assert cli.db.get_active_fields() == []


def test_cmd_field_remove_nonexistent(cli, capsys):
    cli.cmd_field(["remove", "ghost"])
    out = capsys.readouterr().out
    assert "No active field" in out


def test_cmd_field_list_empty(cli, capsys):
    cli.cmd_field(["list"])
    out = capsys.readouterr().out
    assert "No active fields" in out


def test_cmd_field_list_shows_fields(cli, capsys):
    cli.cmd_field(["add", "savings", "checking"])
    cli.cmd_field(["list"])
    out = capsys.readouterr().out
    assert "checking" in out


def test_cmd_field_set_unit(cli):
    cli.cmd_field(["add", "metals", "gold"])
    cli.cmd_field(["set", "metals", "unit", "oz"])
    assert cli.db.get_field_unit("gold") == "oz"


def test_cmd_field_unknown_subcommand(cli, capsys):
    cli.cmd_field(["bogus"])
    out = capsys.readouterr().out
    assert "Unknown subcommand" in out


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------

def test_cmd_show_empty_db(cli, capsys):
    cli.cmd_show([])
    # should not raise — empty state is valid


def test_cmd_show_with_data(cli, capsys):
    seed_db(cli.db)
    cli.cmd_show([])
    out = capsys.readouterr().out
    assert "checking" in out or "savings" in out


# ---------------------------------------------------------------------------
# cmd_summary
# ---------------------------------------------------------------------------

def test_cmd_summary_empty_db(cli, capsys):
    cli.cmd_summary([])
    # should not raise


def test_cmd_summary_with_data(cli, capsys):
    seed_db(cli.db)
    cli.cmd_summary([])
    out = capsys.readouterr().out
    assert out is not None  # smoke test — summary renders without crashing


# ---------------------------------------------------------------------------
# cmd_commit / cmd_update staging
# ---------------------------------------------------------------------------

def test_cmd_commit_empty_commits(cli, capsys):
    cli.cmd_commit([])
    out = capsys.readouterr().out
    assert "Nothing" in out or "no" in out.lower() or out == ""


def test_commit_all_writes_to_db(cli):
    seed_db(cli.db)
    cli.commits = [("checking", "2026-03", 5500.0)]
    cli._commit_all()
    history = cli.db.get_history("checking")
    months = [row[0] for row in history]
    assert "2026-03" in months


# ---------------------------------------------------------------------------
# cmd_help
# ---------------------------------------------------------------------------

def test_cmd_help(cli, capsys):
    cli.cmd_help([])
    out = capsys.readouterr().out
    assert len(out) > 0
