from .base import BaseCommand
from rich.progress import track
import datetime
import time

class CommitCommand(BaseCommand):

    call_str = "commit" # Tells the prompt the string command in order to call this class
    mutates_commits = True

    USAGE = """
  commit                        Commit all pending staged updates to the database
  commit <n> [n ...]            Commit one or more pending updates by index
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
        didn't exist) so the batch can be undone later."""

        field_name, month, value, kind = current_commit
        if kind == "value":
            prior = self.db.get_value_row(field_name, month)
            self.db.record_value(field_name, month, value)
        else:
            prior = self.db.get_asset_value_row(field_name, month)
            self.db.record_asset_value(field_name, month, value)

        batch.append((kind, field_name, month, value, prior))

    def _commit_all(self):
        batch = []

        for current_commit in track(self.commits, description="Commiting Changes..."):
            time.sleep(0.25)
            self._apply_and_capture(current_commit, batch)

        if batch:
            self._undo_stack.append({"timestamp": datetime.datetime.now(), "entries": batch})

        self.commits.clear()

    def _commit_subset(self, options):
        unique_options = set(options)
        successful_commits = []
        batch = []

        for commit_str in track(unique_options, description="Commiting Changes..."):
            time.sleep(0.5)

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

        for _ in range(pop_count):
            batch = self._undo_stack.pop()["entries"]
            for kind, field_name, month, _value, prior in reversed(batch):
                if prior is None:
                    if kind == "value":
                        self.db.delete_value(field_name, month)
                    else:
                        self.db.delete_asset_value(field_name, month)
                else:
                    prior_value, recorded_at = prior
                    if kind == "value":
                        self.db.record_value(field_name, month, prior_value, recorded_at)
                    else:
                        self.db.record_asset_value(field_name, month, prior_value, recorded_at)

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
            for _kind, field_name, month, value, _prior in batch["entries"]:
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
            colored_num = f"{self.BOLD}{self.MAGENTA}{row[0]}{self.RESET}"
            line = line.replace(row[0], colored_num, 1)
            print(line)
