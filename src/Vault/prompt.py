class Prompt:
    """Base class for prompt engine."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def render(self):

        command_input = input("Vault/>")

        while command_input not in ["exit", "quit", "q"]:

            print(f"User Input: {command_input}")

            command, options = self.validate_command(command_input)
            # print (f"Command: {command}")
            # print (f"Asset: {options}")

            if command is not None:
                method = getattr(self, command)
                method(options)

            # Get next command
            command_input = input("Vault/>")

        self.logger.log("Exiting Vault...")

    def validate_command(self, command: str):

        input = command.split(" ")
        for k, v in self.cmd_dict.items():
            if input[0] in v:
                return k, input[1:]

        else:
            print("Invalid command")
            return None, None

    def add(self, options: list):
        print(f"Adding {options}")