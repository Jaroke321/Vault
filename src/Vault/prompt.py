class Prompt:
    """Base class for prompt engine."""

    def __init__(self, state_data_viewer=None, **kwargs):

        self.state_data_viewer = state_data_viewer

        for k, v in kwargs.items():
            setattr(self, k, v)

    def render(self):

        command_input = input("Vault/>")

        while command_input not in ["exit", "quit", "q"]:

            command, options = self.validate_command(command_input)
                
            if command is not None:
                command(options)
                

            if(self.state_data_viewer):
                self.state_data_viewer()

            command_input = input("Vault/>")

        print("Exiting Vault...")

    def validate_command(self, command: str):

        cmdlets = command.split(" ")

        cmd_actual = self.cmd_dict.get(cmdlets[0])
        if cmd_actual is not None:
            return cmd_actual, cmdlets[1:]

        print(f"Unknown command '{cmdlets[0]}'. Type 'help' to see available commands.")
        return None, None