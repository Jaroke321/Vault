"""Semantic colors for Vault command output (ANSI) and REPL chrome (prompt_toolkit)."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from prompt_toolkit.styles import Style
except ImportError:
    Style = None

# Raw ANSI primitives — re-exported through helper.py for command output.
BOLD = "\033[1m"
RESET = "\033[0m"
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


@dataclass(frozen=True)
class SemanticColor:
    """One semantic color in both terminal escape and prompt_toolkit form."""

    ansi: str = ""
    ptk: str = ""


@dataclass(frozen=True)
class Theme:
    accent: SemanticColor
    header: SemanticColor
    positive: SemanticColor
    negative: SemanticColor
    muted: SemanticColor
    staged_index: SemanticColor
    prompt_name: SemanticColor
    prompt_test: SemanticColor
    prompt_sep: SemanticColor
    status_default: SemanticColor
    status_staged: SemanticColor
    status_month: SemanticColor
    status_prices: SemanticColor
    status_test: SemanticColor
    status_net: SemanticColor
    lexer_known: SemanticColor
    lexer_unknown: SemanticColor
    rule: SemanticColor


DEFAULT = Theme(
    accent=SemanticColor(ansi=CYAN, ptk="ansicyan bold"),
    header=SemanticColor(ansi=CYAN, ptk="ansicyan bold"),
    positive=SemanticColor(ansi=GREEN, ptk="ansigreen bold"),
    negative=SemanticColor(ansi=RED, ptk="ansired"),
    muted=SemanticColor(ptk="ansibrightblack"),
    staged_index=SemanticColor(ansi=MAGENTA, ptk="ansimagenta"),
    prompt_name=SemanticColor(ansi=CYAN, ptk="ansicyan bold"),
    prompt_test=SemanticColor(ansi=YELLOW, ptk="ansiyellow bold"),
    prompt_sep=SemanticColor(ptk="ansibrightblack"),
    status_default=SemanticColor(),
    status_staged=SemanticColor(ansi=BOLD, ptk="bold"),
    status_month=SemanticColor(ansi=CYAN, ptk="ansicyan"),
    status_prices=SemanticColor(ansi=GREEN, ptk="ansigreen"),
    status_test=SemanticColor(ansi=YELLOW, ptk="ansiyellow bold"),
    status_net=SemanticColor(ansi=MAGENTA, ptk="ansimagenta"),
    lexer_known=SemanticColor(ansi=GREEN, ptk="ansigreen bold"),
    lexer_unknown=SemanticColor(ansi=RED, ptk="ansired"),
    rule=SemanticColor(ptk="ansibrightblack"),
)

# Convenience ANSI re-exports for callers that want a semantic name directly.
ACCENT = DEFAULT.accent.ansi
HEADER = DEFAULT.header.ansi
POSITIVE = DEFAULT.positive.ansi
NEGATIVE = DEFAULT.negative.ansi
STAGED_INDEX = DEFAULT.staged_index.ansi


def ansi(theme: Theme, name: str) -> str:
    """Return the ANSI escape sequence for a semantic color on `theme`."""
    return getattr(theme, name).ansi


def styled_staged_index(text: str, theme: Theme = DEFAULT) -> str:
    """Bold, themed index cell for staged/history tables."""
    return f"{BOLD}{theme.staged_index.ansi}{text}{RESET}"


def build_ptk_style(theme: Theme = DEFAULT):
    """Build the prompt_toolkit Style dict for REPL/TUI chrome."""
    if Style is None:
        return None
    t = theme
    return Style.from_dict({
        "status.default": t.status_default.ptk,
        "status.staged": t.status_staged.ptk,
        "status.month": t.status_month.ptk,
        "status.prices": t.status_prices.ptk,
        "status.test": t.status_test.ptk,
        "status.net": t.status_net.ptk,
        "prompt.test": t.prompt_test.ptk,
        "prompt.name": t.prompt_name.ptk,
        "prompt.sep": t.prompt_sep.ptk,
        "lexer.command.known": t.lexer_known.ptk,
        "lexer.command.unknown": t.lexer_unknown.ptk,
        "header": t.header.ptk,
        "rule": t.rule.ptk,
    })
