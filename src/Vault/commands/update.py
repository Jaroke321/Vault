from .base import BaseCommand
import datetime

from ..data_types import CATEGORIES

try:
    from prompt_toolkit.validation import Validator, ValidationError
except ImportError:
    Validator = object
    ValidationError = Exception


class _NumericValidator(Validator):
    def validate(self, document):
        text = document.text.strip()
        if not text:
            return
        try:
            float(text.replace("$", "").replace(",", ""))
        except ValueError as exc:
            raise ValidationError(message="Enter a number or leave blank to skip") from exc


class UpdateCommand(BaseCommand):

    call_str = "update" # Tells the prompt the string command in order to call this class

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
           self._interactive_update(target_month)
        elif len(options) == 2:
           self._single_update(options, target_month)
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

    @staticmethod
    def _previous_month(month: str) -> str:
        year, mon = map(int, month.split("-", 1))
        if mon == 1:
            return f"{year - 1}-12"
        return f"{year:04d}-{mon - 1:02d}"

    ####################################
    # Sub-commands
    ####################################
    def _interactive_update(self, target_month):
        if self.prompt_session is None:
            self.usage()
            return

        previous_month = self._previous_month(target_month)
        staged = []

        try:
            for field_name, category, unit in self.db.get_active_fields():
                if CATEGORIES[category].is_priced:
                    continue

                prior = self.db.get_value(field_name, previous_month)
                default = str(prior) if prior is not None else ""
                message = f"{field_name} ({category}, {unit}): "
                raw = self.prompt_session.prompt(
                    message,
                    default=default,
                    placeholder=f"{category} · {unit} · blank to skip",
                    validator=_NumericValidator(),
                )

                if not raw.strip():
                    continue

                amount = self._parse_float(raw)
                if amount is None:
                    continue

                old = self.db.get_value(field_name, target_month)
                if old is not None and old != amount:
                    print(
                        f"[WARN] Overwriting value for {field_name} {target_month}: "
                        f"{self.format_value(old)} → {self.format_value(amount)}"
                    )

                staged.append([field_name, target_month, amount])
        except KeyboardInterrupt:
            print("\nUpdate cancelled.")
            return

        for entry in staged:
            self.commits.append(entry)

    def _single_update(self, options, target_month):
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
