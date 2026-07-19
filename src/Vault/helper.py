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

_VAULT_ART = (
    f"{BOLD}{YELLOW}" +
    r"""
       ___________________________________________________
      ||  _______________________________________________  ||
   ===||  |                                           |  ||===
   ===||  |   .=====================================. |  ||===
   ===||  |  /   .===============================.   \|  ||===
      ||  | /   /   ___________________________   \   |  ||
   ===||  ||   |   /   .===================.   \   |  ||  ||===
   ===||  ||   |  |        """ +
    f"{WHITE}V A U L T{BOLD}{YELLOW}" +
    r"""            |  |  ||  ||===
   ===||  ||   |  |   /   _____________     \   |  |  ||  ||===
   ===||  ||   |  |  |   / /    |    \ \    |  |  |  ||  ||===
   ===||  ||   |  |  |  | | ---[O]--- | |   |  |  |  ||  ||===
   ===||  ||   |  |  |   \ \    |    / /    |  |  |  ||  ||===
   ===||  ||   |  |   \   \_____________/   /   |  |  ||  ||===
   ===||  ||   |   \   '==================='   /|  |  ||  ||===
      ||  | \   \   \_________________________/ /   |  ||
   ===||  |  \   '=================================' /  ||===
   ===||  |   '======================================'  ||===
      ||  |___________________________________________|  ||
      ||_________________________________________________||
""" + RESET
)

def print_banner():
    print(_VAULT_ART)
