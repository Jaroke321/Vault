import calendar
import datetime
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
    styled_staged_index,
)

NOTE_MARKER = "*"
NOTE_LEGEND = "* = has note"

DEFAULT_HISTORY_MONTHS = 6
TABLE_NAME_W = 22
TABLE_COL_W = 14

def print_table(headers, rows, *, index_col: int | None = 0):
    """Render a left-aligned table with auto-sized columns and an optional styled index."""
    if not headers:
        return

    widths = [len(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]
    for row in str_rows:
        for j, cell in enumerate(row):
            widths[j] = max(widths[j], len(cell))

    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  " + "  ".join("-" * w for w in widths)

    print(fmt.format(*headers))
    print(sep)
    for row in str_rows:
        line = fmt.format(*row)
        if index_col is not None and index_col < len(row):
            line = line.replace(row[index_col], styled_staged_index(row[index_col]), 1)
        print(line)

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

_MONTH_RE = re.compile(r"\d{4}-\d{2}")

def month_end(month: str) -> str | None:
    """Return the last calendar day of a `YYYY-MM` key as `YYYY-MM-DD`, or None if
    `month` isn't well-formed. Tolerant rather than raising, since CSV import passes
    `month` through without validation (see ImportCommand.sub_csv)."""
    if not isinstance(month, str) or not _MONTH_RE.fullmatch(month):
        return None
    year, mon = int(month[:4]), int(month[5:7])
    if mon < 1 or mon > 12:
        return None
    last_day = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-{last_day:02d}"

def last_trading_day(month: str) -> str | None:
    """Return the most recent weekday on or before `month_end(month)`, as
    `YYYY-MM-DD`, or None if `month` isn't well-formed. Walks back from month-end to
    the nearest Mon-Fri day only -- there is no market holiday calendar here (see
    PriceFetcher, which has no concept of a historical close to validate against),
    so a month-end landing on a market holiday resolves a day off."""
    end = month_end(month)
    if end is None:
        return None
    date = datetime.date.fromisoformat(end)
    while date.weekday() >= 5:  # Saturday=5, Sunday=6
        date -= datetime.timedelta(days=1)
    return date.isoformat()

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
