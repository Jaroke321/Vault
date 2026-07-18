class ExitSignal(Exception):
    pass


class Prompt:
    """Base class for prompt engine."""

    def __init__(self, state_data_viewer=None, **kwargs):

        self.state_data_viewer = state_data_viewer

        for k, v in kwargs.items():
            setattr(self, k, v)

    def render(self):

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

        print("Exiting Vault...")

    def validate_command(self, command: str):

        cmdlets = command.split(" ")

        cmd_actual = self.cmd_dict.get(cmdlets[0])
        if cmd_actual is not None:
            return cmd_actual, cmdlets[1:]

        print(f"Unknown command '{cmdlets[0]}'. Type 'help' to see available commands.")
        return None, None