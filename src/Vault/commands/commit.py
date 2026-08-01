from .base import BaseCommand
from ..theme import styled_staged_index
import datetime

class CommitCommand(BaseCommand):

    call_str = "commit" # Tells the prompt the string command in order to call this class

    USAGE = """
  commit                        Commit all pending staged updates to the database
  commit <n> [n ...]            Commit one or more pending updates by index
  commit list                   Show pending staged updates awaiting commit
  commit undo                   Reverse the most recent commit
  commit undo <n>               Reverse the last N commits
  commit history                Show past commits, most recent first (reference for commit undo)
"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._undo_stack = []

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        if options and options[0] in self.sub_commands:
            self.sub_commands[options[0]](options[1:])
            return

        if not options:
           self._commit_all()
           return
        else:
           self._commit_subset(options)

    ####################################
    # Sub-commands
    ####################################
    def _apply_and_capture(self, current_commit, batch):
        """Record one staged commit entry, first capturing the prior row (or None if it
        didn't exist) so the batch can be undone later. record_value/get_value_row
        resolve the record's category internally, so there's no kind to branch on
        here — every category routes through the same two calls.

        Also resolves the record's current price (_investment_price returns None
        for non-priced categories, so this is safe to call unconditionally) and
        passes it through to be stored on the snapshot -- but only for the
        current month. _investment_price resolves the price *now*, and month
        can be past-dated (`update <field> <value> -m YYYY-MM`), so storing it
        for a past month would silently mislabel today's price as that month's.
        NULL for a past-dated commit is the honest answer; task 33's as-of-date
        and provenance fields are the real fix for backfilled history."""

        field_name, month, value = current_commit
        prior = self.db.get_value_row(field_name, month)

        current_month = datetime.datetime.now().strftime("%Y-%m")
        field_id = self.db.get_field_id(field_name)
        price = (
            self._investment_price(field_id)
            if field_id is not None and month == current_month
            else None
        )

        self.db.record_value(field_name, month, value, price=price)

        batch.append((field_name, month, value, prior))

    def _commit_all(self):
        batch = []

        total = len(self.commits)
        for index, current_commit in enumerate(self.commits, start=1):
            print(f"Committing {index}/{total} …")
            self._apply_and_capture(current_commit, batch)

        if batch:
            self._undo_stack.append({"timestamp": datetime.datetime.now(), "entries": batch})

        self.commits.clear()
        if batch:
            self.commits.render()

    def _commit_subset(self, options):
        unique_options = set(options)
        successful_commits = []
        batch = []

        total = len(unique_options)
        for index, commit_str in enumerate(unique_options, start=1):
            print(f"Committing {index}/{total} …")

            try:
                commit_num = int(commit_str)

                if(commit_num > 0 and commit_num <= len(self.commits)):
                    current_commit = self.commits[commit_num-1]
                    self._apply_and_capture(current_commit, batch)
                    successful_commits.append(commit_num-1)

            except ValueError:
                pass

        if batch:
            self._undo_stack.append({"timestamp": datetime.datetime.now(), "entries": batch})

        # Remove from list everything we just commited
        for i in sorted(successful_commits, reverse=True):
            self.commits.pop(i)

        if batch:
            self.commits.render()

    def sub_list(self, options):
        self.commits.render()

    def sub_undo(self, options):
        count = 1
        if options:
            count = self._parse_int(options[0])
            if count is None or count <= 0:
                print(f"[ERROR] Invalid undo count '{options[0]}'")
                self.usage()
                return

        if not self._undo_stack:
            print("Nothing to undo.")
            return

        pop_count = min(count, len(self._undo_stack))

        if not self._confirm(f"Reverse {pop_count} commit(s)?"):
            print("Cancelled.")
            return

        for _ in range(pop_count):
            batch = self._undo_stack.pop()["entries"]
            for field_name, month, _value, prior in reversed(batch):
                if prior is None:
                    self.db.delete_value(field_name, month)
                else:
                    prior_value, recorded_at = prior
                    self.db.record_value(field_name, month, prior_value, recorded_at)

        if pop_count < count:
            print(f"Only {pop_count} commit(s) to undo — reversed all of them.")
        else:
            print(f"Reversed {pop_count} commit(s).")

    def sub_history(self, options):
        if not self._undo_stack:
            print("No commits to show.")
            return

        headers = ["#", "When", "Field", "Month", "Value"]
        rows = []
        for i, batch in enumerate(reversed(self._undo_stack), start=1):
            when = batch["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            for field_name, month, value, _prior in batch["entries"]:
                rows.append([str(i), when, field_name, month, str(value)])

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
