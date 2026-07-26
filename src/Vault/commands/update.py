from .base import BaseCommand
import datetime

class UpdateCommand(BaseCommand):

    call_str = "update" # Tells the prompt the string command in order to call this class
    mutates_commits = True

    USAGE = """
  update                               Interactively stage values for all fields (default: current month)
  update <field> <value> [-m YYYY-MM]  Stage a value for a single field (value or quantity, per its category)
"""

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        current_month = datetime.datetime.now().strftime("%Y-%m")

        options, flagged_month, error = self._extract_target_month(options)
        if error:
            print(f"[ERROR] {error}")
            self.usage()
            return

        target_month = flagged_month if flagged_month is not None else current_month

        if not options:
           self.usage()
        elif len(options) == 2:
           self.sub_single_update(options, target_month)
        else:
           self.usage()

    def _extract_target_month(self, options: list) -> tuple[list, str | None, str | None]:
        """Strip -m/--month from options; return (rest, month|None, error|None).

        Empty-string tokens (from double spaces in the naive split) are dropped.
        When the flag is absent, month is None so the caller uses the current month.
        """
        cleaned = [tok for tok in options if tok != ""]
        rest: list[str] = []
        month: str | None = None
        i = 0
        while i < len(cleaned):
            tok = cleaned[i]
            if tok in ("-m", "--month"):
                if month is not None:
                    return options, None, "Month flag specified more than once"
                if i + 1 >= len(cleaned):
                    return options, None, "Missing value after month flag (-m YYYY-MM)"
                parsed = self._parse_month_string(cleaned[i + 1])
                if parsed is None:
                    return options, None, f"Invalid month '{cleaned[i + 1]}' (expected YYYY-MM, not in the future)"
                month = parsed
                i += 2
                continue
            rest.append(tok)
            i += 1
        return rest, month, None

    ####################################
    # Sub-commands
    ####################################
    def sub_single_update(self, options, target_month):
        field_name, raw = options[0], options[1]
        success = False

        amount = self._parse_float(raw)
        field_name_exists = self._is_a_field_name(field_name)

        if field_name_exists and amount:
            old = self.db.get_value(field_name, target_month)
            if old is not None and old != amount:
                print(
                    f"[WARN] Overwriting value for {field_name} {target_month}: "
                    f"{self.format_value(old)} → {self.format_value(amount)}"
                )

            self.commits.append([ field_name, target_month, amount ])
            success = True

        else:
            print("[ERROR] Either field name doesnt exist yet, or the value was invalid")
            success = False

        return success
