from .helper import BOLD, MAGENTA, RESET

class PendingCommits:
    """Owns the list of staged-but-not-yet-committed field updates and the logic to
    render them as a table. Shared between UpdateCommand (which stages entries) and
    CommitCommand (which commits and removes them)."""

    def __init__(self):
        self._commits = []
        self._suppress_next_render = False

    def __len__(self):
        return len(self._commits)

    def __iter__(self):
        return iter(self._commits)

    def __getitem__(self, index):
        return self._commits[index]

    def append(self, entry):
        self._commits.append(entry)

    def pop(self, index):
        return self._commits.pop(index)

    def clear(self):
        self._commits.clear()

    def suppress_next_render(self):
        """Skip the next render() call without permanently hiding the table. Used by
        commands that don't mutate the pending list."""
        self._suppress_next_render = True

    def render(self):
        if not self._commits or self._suppress_next_render:
            self._suppress_next_render = False
            return

        headers = ["#", "Field", "Month", "Value"]
        rows = [[str(i), c[0], c[1], str(c[2])] for i, c in enumerate(self._commits, start=1)]

        widths = [len(h) for h in headers]
        for row in rows:
            for j, cell in enumerate(row):
                widths[j] = max(widths[j], len(cell))

        fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
        sep = "  " + "  ".join("-" * w for w in widths)

        print(fmt.format(*headers))
        print(sep)
        for row in rows:
            line = fmt.format(*row)
            colored_num = f"{BOLD}{MAGENTA}{row[0]}{RESET}"
            line = line.replace(row[0], colored_num, 1)
            print(line)
