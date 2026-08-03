from dataclasses import dataclass

from .theme import styled_staged_index


@dataclass
class StagedUpdate:
    """One staged-but-not-yet-committed field update. The task-33 fields default to
    None and are only ever set by a caller that actually collected them (an
    interactive prompt, a CLI flag) -- nothing here assumes they're populated."""

    field_name: str
    month: str
    value: float
    contribution: float | None = None
    as_of: str | None = None
    source: str | None = None
    note: str | None = None
    price: float | None = None


_EXTRA_FIELDS = (
    ("contribution", "Contribution"),
    ("as_of", "As Of"),
    ("source", "Source"),
    ("note", "Note"),
    ("price", "Price"),
)


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
        return sorted({entry.month for entry in self._commits})

    def render(self):
        if not self._commits:
            return

        headers = ["#", "Field", "Month", "Value"]
        label_map = dict(_EXTRA_FIELDS)
        extra_fields = [
            name for name, _ in _EXTRA_FIELDS
            if any(getattr(c, name) is not None for c in self._commits)
        ]
        headers += [label_map[name] for name in extra_fields]

        rows = []
        for i, c in enumerate(self._commits, start=1):
            row = [str(i), c.field_name, c.month, str(c.value)]
            for name in extra_fields:
                value = getattr(c, name)
                row.append(str(value) if value is not None else "")
            rows.append(row)

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
