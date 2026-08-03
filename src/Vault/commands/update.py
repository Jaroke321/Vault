from .base import BaseCommand
import datetime

from ..data_types import CATEGORIES
from ..pending_commits import StagedUpdate

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
  update [--as-of YYYY-MM-DD]                                                                       Interactively stage values for all fields (default: current month)
  update <field> <value> [-m YYYY-MM] [--as-of YYYY-MM-DD] [--contribution <usd>] [--price <usd>]    Stage a value for a single field (value or quantity, per its category); --price only for priced categories
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

        options, as_of, error = self._extract_as_of(options, target_month)
        if error:
            print(f"[ERROR] {error}")
            self.usage()
            return

        options, contribution, error = self._extract_float_flag(options, "--contribution", "Contribution")
        if error:
            print(f"[ERROR] {error}")
            self.usage()
            return

        options, price, error = self._extract_float_flag(options, "--price", "Price")
        if error:
            print(f"[ERROR] {error}")
            self.usage()
            return

        if not options:
            if contribution is not None or price is not None:
                print("[ERROR] --contribution/--price only apply to 'update <field> <value>', not interactive mode")
                self.usage()
                return
            self._interactive_update(target_month, as_of)
        elif len(options) == 2:
           self._single_update(options, target_month, as_of, contribution, price)
        else:
           self.usage()

    def _extract_flag(
        self, options: list, flag_names: tuple[str, ...], label: str, missing_hint: str,
        parse, describe_invalid,
    ) -> tuple[list, object | None, str | None]:
        """Strip a `flag <value>` pair (any alias in flag_names) from options;
        return (rest, value|None, error|None). Empty-string tokens (from double
        spaces in the naive split) are dropped. Shared token-walking mechanic
        behind -m/--month, --as-of, --contribution, and --price:
          - `parse(token)` returns the parsed value, or None to reject it
          - `describe_invalid(token)` builds the "Invalid ..." message for a
            rejected token -- what counts as valid, and how to explain why,
            differs per flag, so that part stays with each caller.
        """
        cleaned = [tok for tok in options if tok != ""]
        rest: list[str] = []
        value = None
        i = 0
        while i < len(cleaned):
            tok = cleaned[i]
            if tok in flag_names:
                if value is not None:
                    return options, None, f"{label} flag specified more than once"
                if i + 1 >= len(cleaned):
                    return options, None, f"Missing value after {label.lower()} flag ({missing_hint})"
                parsed = parse(cleaned[i + 1])
                if parsed is None:
                    return options, None, describe_invalid(cleaned[i + 1])
                value = parsed
                i += 2
                continue
            rest.append(tok)
            i += 1
        return rest, value, None

    def _extract_target_month(self, options: list) -> tuple[list, str | None, str | None]:
        """Strip -m/--month from options; return (rest, month|None, error|None).
        When the flag is absent, month is None so the caller uses the current month."""
        return self._extract_flag(
            options, ("-m", "--month"), "Month", "-m YYYY-MM",
            self._parse_month_string,
            lambda tok: f"Invalid month '{tok}' (expected YYYY-MM, not in the future)",
        )

    def _extract_as_of(self, options: list, target_month: str) -> tuple[list, str | None, str | None]:
        """Strip --as-of from options; return (rest, as_of|None, error|None).

        Applies uniformly to both the interactive and single-value forms, the same
        way -m/--month does -- there's no reason an as-of override should only be
        available in one. Validated against `target_month` (already resolved from
        -m or the current month), since an as-of date belongs to a specific month.
        """
        return self._extract_flag(
            options, ("--as-of",), "As-of", "--as-of YYYY-MM-DD",
            lambda tok: self._parse_as_of_date(tok, target_month),
            lambda tok: f"Invalid as-of date '{tok}' (expected YYYY-MM-DD, within {target_month})",
        )

    def _extract_float_flag(self, options: list, flag: str, label: str) -> tuple[list, float | None, str | None]:
        """Strip a `flag <number>` pair from options; return (rest, value|None,
        error|None). Shared by --contribution and --price, which both take a bare
        float with no further validation at this layer -- category-specific
        validation (e.g. rejecting --price for a non-priced record) happens in
        _single_update, once the field's category is known."""
        return self._extract_flag(
            options, (flag,), label, f"{flag} <amount>",
            self._parse_float,
            lambda tok: f"Invalid {label.lower()} '{tok}' (expected a number)",
        )

    @staticmethod
    def _previous_month(month: str) -> str:
        year, mon = map(int, month.split("-", 1))
        if mon == 1:
            return f"{year - 1}-12"
        return f"{year:04d}-{mon - 1:02d}"

    def _staged_value(self, field_name, target_month):
        for entry in self.commits:
            if entry.field_name == field_name and entry.month == target_month:
                return entry.value
        return None

    def _print_field_context(self, field_name, category, unit, target_month, previous_month):
        prior = self.db.get_value(field_name, previous_month)
        current = self.db.get_value(field_name, target_month)
        staged = self._staged_value(field_name, target_month)

        print(f"\n  {field_name} ({category}) · {target_month}")
        if prior is not None:
            print(f"    prior {previous_month}: {self.format_value(prior, unit)}")
        else:
            print(f"    prior {previous_month}: (none)")
        if current is not None:
            print(f"    saved {target_month}:  {self.format_value(current, unit)}")
        if staged is not None:
            print(f"    staged:         {self.format_value(staged, unit)}")

    def _ask_field_amount(self, unit, index, total):
        message = f"  amount ({unit}) [{index}/{total}]: "
        return self._ask(
            message,
            placeholder="blank to skip",
            validator=_NumericValidator(),
        )

    def _ask_field_contribution(self, index, total):
        """Always labelled '$', unlike _ask_field_amount's unit -- contribution is
        USD in/out regardless of the record's own unit (shares, troy oz, ...), so
        an investment's contribution prompt reads differently from its amount
        prompt on purpose."""
        message = f"  contribution ($) [{index}/{total}]: "
        return self._ask(
            message,
            placeholder="blank to skip",
            validator=_NumericValidator(),
        )

    ####################################
    # Sub-commands
    ####################################
    def _interactive_update(self, target_month, as_of=None):
        if not self._can_prompt_interactively():
            self.usage()
            return

        previous_month = self._previous_month(target_month)
        staged = []
        fields = list(self.db.get_active_fields())
        total = len(fields)

        print(f"\n  Interactive update for {target_month} ({total} fields)")
        print("  Enter an amount, blank to skip, Ctrl-C to cancel.\n")

        try:
            for index, (field_name, category, unit) in enumerate(fields, start=1):
                self._print_field_context(field_name, category, unit, target_month, previous_month)
                raw = self._ask_field_amount(unit, index, total)

                if not raw.strip():
                    continue

                amount = self._parse_float(raw)
                if amount is None:
                    continue

                current = self.db.get_value(field_name, target_month)
                already_staged = self._staged_value(field_name, target_month)
                if amount == current or amount == already_staged:
                    continue

                if current is not None and current != amount:
                    print(
                        f"[WARN] Overwriting value for {field_name} {target_month}: "
                        f"{self.format_value(current, unit)} → {self.format_value(amount, unit)}"
                    )

                contribution_raw = self._ask_field_contribution(index, total)
                contribution = (
                    self._parse_float(contribution_raw) if contribution_raw.strip() else None
                )

                staged.append(StagedUpdate(
                    field_name, target_month, amount, as_of=as_of, contribution=contribution,
                ))
        except KeyboardInterrupt:
            print("\nUpdate cancelled.")
            return

        for entry in staged:
            self.commits.append(entry)

        if staged:
            print(f"\n  Staged {len(staged)} update(s). Use 'commit list' to review.")
        else:
            print("\n  No changes staged.")

    def _single_update(self, options, target_month, as_of=None, contribution=None, price=None):
        field_name, raw = options[0], options[1]
        success = False

        amount = self._parse_float(raw)
        field_name_exists = self._is_a_field_name(field_name)

        if field_name_exists and amount is not None:
            if price is not None:
                category = self.db.get_field_category(field_name)
                if not CATEGORIES[category].is_priced:
                    print(
                        f"[ERROR] --price only applies to priced categories (investment); "
                        f"'{field_name}' is {category}"
                    )
                    return False

            old = self.db.get_value(field_name, target_month)
            if old is not None and old != amount:
                print(
                    f"[WARN] Overwriting value for {field_name} {target_month}: "
                    f"{self.format_value(old)} → {self.format_value(amount)}"
                )

            self.commits.append(StagedUpdate(
                field_name, target_month, amount,
                as_of=as_of, contribution=contribution, price=price,
            ))
            success = True

        else:
            print("[ERROR] Either field name doesnt exist yet, or the value was invalid")
            success = False

        return success
