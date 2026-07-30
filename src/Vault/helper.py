import random

# ANSI color codes
BOLD     = "\033[1m"
RESET    = "\033[0m"

BLACK    = "\033[30m"
RED      = "\033[31m"
GREEN    = "\033[32m"
YELLOW   = "\033[33m"
BLUE     = "\033[34m"
MAGENTA  = "\033[35m"
CYAN     = "\033[36m"
WHITE    = "\033[37m"

NOTE_MARKER = "*"
NOTE_LEGEND = "* = has note"

def note_label(name: str, has_note: bool) -> str:
    return name + NOTE_MARKER if has_note else name

def cat_label(name: str, color: str = CYAN) -> str:
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
    print(f"\n{BOLD}{YELLOW}{art}{RESET}")
    if test_mode:
        print(f"{BOLD}{YELLOW}  TEST MODE — in-memory database, changes are not saved{RESET}")
    print()
