import random
import re

from .theme import (
    DEFAULT,
    BLACK,
    BLUE,
    BOLD,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    WHITE,
    YELLOW,
)

NOTE_MARKER = "*"
NOTE_LEGEND = "* = has note"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)

def visible_len(s: str) -> int:
    return len(strip_ansi(s))

def truncate_ansi(s: str, width: int) -> str:
    """Clip `s` to `width` visible columns without splitting an escape sequence.

    Escape sequences themselves never count against `width` and are always
    passed through in full, even if only their trailing part would otherwise
    fit — otherwise a partial `\\x1b[3` could leak into the terminal as text.
    """
    if width <= 0:
        return ""

    out = []
    visible = 0
    pos = 0
    for match in _ANSI_RE.finditer(s):
        if visible >= width:
            break
        chunk = s[pos:match.start()]
        remaining = width - visible
        if len(chunk) > remaining:
            out.append(chunk[:remaining])
            visible = width
            pos = match.start()
            break
        out.append(chunk)
        visible += len(chunk)
        out.append(match.group())
        pos = match.end()

    if visible < width:
        chunk = s[pos:]
        out.append(chunk[:width - visible])

    return "".join(out)

def note_label(name: str, has_note: bool) -> str:
    return name + NOTE_MARKER if has_note else name

def cat_label(name: str, color: str = DEFAULT.accent.ansi) -> str:
    return f"{BOLD}{color}{name.upper()}{RESET}"

_PREFIX_UNITS = {"$", "€", "£", "¥"}

def format_value(value: float, unit: str = "$") -> str:
    if unit in _PREFIX_UNITS:
        return f"{unit}{value:,.2f}"
    return f"{value:,.4f} {unit}"

_SPARKS = "▁▂▃▄▅▆▇█"

def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if lo == hi:
        return _SPARKS[len(_SPARKS) // 2] * len(values)
    return "".join(
        _SPARKS[round((v - lo) / (hi - lo) * (len(_SPARKS) - 1))]
        for v in values
    )

_BANNER_H = """
   ██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗
   ██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝
   ██║   ██║███████║██║   ██║██║     ██║
   ╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║
    ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║
     ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝"""

_BANNER_BLOCKY = """
██     ██    ███    ██     ██ ██       ████████
██     ██   ██ ██   ██     ██ ██          ██
██     ██  ██   ██  ██     ██ ██          ██
██     ██ ██     ██ ██     ██ ██          ██
 ██   ██  █████████ ██     ██ ██          ██
  ██ ██   ██     ██ ██     ██ ██          ██
   ███    ██     ██  ███████  ████████    ██"""

_BANNER_DOUBLE_BLOCKY = """
 █░█ ▄▀█ █░█ █░░ ▀█▀
 ▀▄▀ █▀█ █▄█ █▄▄ ░█░"""

_BANNER_CALVIN = """
╦  ╦╔═╗╦ ╦╦ ╔╦╗
╚╗╔╝╠═╣║ ║║  ║
 ╚╝ ╩ ╩╚═╝╩═╝╩"""

_BANNER_VAULT_FRAME = """
      ╔═══════════════════════════════╗
      ║                               ║
      ║           V · A · U · L · T   ║
      ║               ◉               ║
      ║                               ║
      ╚═══════════════════════════════╝"""

_BANNER_J = r"""
    =========================================
    ||                                     ||
    ||            V A U L T                ||
    ||                 (O)                 ||
    ||_____________________________________||
    ========================================="""

_STARTUP_BANNERS = (
    _BANNER_H,
    # _BANNER_BLOCKY,
    # _BANNER_DOUBLE_BLOCKY,
    # _BANNER_CALVIN,
    # _BANNER_VAULT_FRAME,
    # _BANNER_J,
)

def print_banner(test_mode: bool = False) -> None:
    art = random.choice(_STARTUP_BANNERS)
    header = DEFAULT.header.ansi
    print(f"\n{BOLD}{header}{art}{RESET}")
    if test_mode:
        print(f"{BOLD}{header}  TEST MODE — in-memory database, changes are not saved{RESET}")
    print()

_BANNER_COMPACT = _BANNER_H.strip("\n")
HEADER_HEIGHT = len(_BANNER_COMPACT.split("\n")) + 1  # art rows + marker row

def header_lines(test_mode: bool = False) -> list[str]:
    """Return the fixed TUI header as plain text (no embedded ANSI) -- the TUI
    applies color via the `class:header` style, not literal escape codes."""
    lines = list(_BANNER_COMPACT.split("\n"))
    if test_mode:
        lines.append("  TEST MODE — in-memory database, changes are not saved")
    else:
        lines.append("")
    return lines
