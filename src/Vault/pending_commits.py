from .theme import styled_staged_index

class PendingCommits:
    """Owns the list of staged-but-not-yet-committed field updates and the logic to
    render them as a table. Shared between UpdateCommand (which stages entries) and
    CommitCommand (which commits and removes them)."""

    def __init__(self):
        self._commits = []

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

    @property
    def staged_count(self):
        return len(self._commits)

    def target_months(self):
        """Distinct months present in staged entries, sorted chronologically."""
        return sorted({entry[1] for entry in self._commits})

    def render(self):
        if not self._commits:
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
            colored_num = styled_staged_index(row[0])
            line = line.replace(row[0], colored_num, 1)
            print(line)
