class Prompt:
    """Base class for prompt engine."""

    def __init__(self, state_data_viewer=None, **kwargs):

        self.state_data_viewer = state_data_viewer

        for k, v in kwargs.items():
            setattr(self, k, v)

    def render(self):

        command_input = input("Vault/>")

        while command_input not in ["exit", "quit", "q"]:

            if(self.state_data_viewer):
                self.state_data_viewer()
                
            command, options = self.validate_command(command_input)

            if command is not None:
                command(options)

            # Get next command
            command_input = input("Vault/>")

        print("Exiting Vault...")

    def validate_command(self, command: str):

        cmdlets = command.split(" ")
        for k, v in self.cmd_dict.items():
            if cmdlets[0] == k:
                return v, cmdlets[1:]

        print("Invalid command")
        return None, None