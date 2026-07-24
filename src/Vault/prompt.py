import sys
from pathlib import Path

try:
    import readline
except ImportError:
    readline = None


class ExitSignal(Exception):
    pass


class Prompt:
    """Base class for prompt engine."""

    def __init__(self, project_name, logger, cmd_dict, subcommands, command_usage,
                 history_path=None, state_data_viewer=None):

        self.project_name = project_name
        self.logger = logger
        self.cmd_dict = cmd_dict
        self.subcommands = subcommands
        self.command_usage = command_usage
        self.history_path = history_path
        self.state_data_viewer = state_data_viewer

        self.interactive = readline is not None and sys.stdin.isatty()
        self._readline_initialized = False
        self._completion_matches: list[str] = []

    def render(self):

        if self.interactive:
            self._setup_readline()
            if self.history_path:
                try:
                    readline.read_history_file(self.history_path)
                except FileNotFoundError:
                    pass
                readline.set_history_length(1000)

        try:
            command_input = input(f"{self.project_name}/>")

            while True:

                command, options = self.validate_command(command_input)

                if command is not None:
                    try:
                        command(options)
                    except ExitSignal:
                        break

                    # it might be cool to be able to handle return values from the called function
                    # This would be relevant since the command classes are calling an entry point functin
                    # Right now the entry point function handles its own sub commands
                    # But what if the entry point can return back a dict with sub commands
                    # and then sub commands can return back more dicts with sub commands
                    # could potentially allow for more complex and dynamic decision trees


                if(self.state_data_viewer):
                    self.state_data_viewer()

                command_input = input(f"{self.project_name}/>")

        finally:
            if self.interactive:
                if self.history_path:
                    try:
                        Path(self.history_path).parent.mkdir(parents=True, exist_ok=True)
                        readline.write_history_file(self.history_path)
                    except OSError:
                        pass

        print("Exiting Vault...")

    def _setup_readline(self):
        if self._readline_initialized:
            return

        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        readline.set_completer_delims(" ")
        readline.set_completer(self._complete)
        readline.set_completion_display_matches_hook(self._display_matches)
        self._readline_initialized = True

    def _build_completion_matches(self, text: str) -> list[str]:
        line = readline.get_line_buffer()
        begidx = readline.get_begidx()
        tokens_before = line[:begidx].split()

        if len(tokens_before) <= 1 and not line[:begidx].endswith(" "):
            return sorted(
                name for name in self.cmd_dict if name.startswith(text)
            )

        cmd = tokens_before[0]
        subcommands = self.subcommands.get(cmd, [])
        return sorted(name for name in subcommands if name.startswith(text))

    def _complete(self, text, state):
        if state == 0:
            self._completion_matches = self._build_completion_matches(text)
        try:
            return self._completion_matches[state]
        except IndexError:
            return None

    def _display_matches(self, substitution, matches, longest_match_length):
        line = readline.get_line_buffer()
        begidx = readline.get_begidx()

        if begidx == 0 and len(matches) == 1:
            cmd = matches[0]
            usage = self.command_usage.get(cmd)
            if usage and line[:begidx] + cmd == line.rstrip():
                print()
                print(usage)
                self._redisplay_prompt()
                return

        if matches:
            print()
            print("  ".join(matches))
            self._redisplay_prompt()

    def _redisplay_prompt(self):
        prompt = f"{self.project_name}/>"
        print(prompt + readline.get_line_buffer(), end="")
        sys.stdout.flush()

    def validate_command(self, command: str):

        cmdlets = command.split(" ")

        cmd_actual = self.cmd_dict.get(cmdlets[0])
        if cmd_actual is not None:
            return cmd_actual, cmdlets[1:]

        print(f"Unknown command '{cmdlets[0]}'. Type 'help' to see available commands.")
        return None, None
