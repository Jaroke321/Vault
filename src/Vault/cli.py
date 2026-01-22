import datetime

from .prompt import Prompt
from .logger import Logger

def main():

    logger = Logger(log_file="logs/Vault.log")

    CLI(logger).run()

class CLI:
    """Implementation class or my entry point into the overall project. This class can be used as an example of how to pull in the
    different classes being used and use them together."""

    def __init__(self, logger):
        self.logger = logger
        self.commits = {}
        self.commit_context = None

        self.commands = {
            "buy": self.add,
            "get": self.add,
            "add": self.add,
            "set": self.set,
            "use": self.use
        }

    def run(self):
        prompt = Prompt(project_name="Vault", logger=self.logger, cmd_dict=self.commands)
        prompt.render()

    def set(self, options: list):
        self.logger.log(f"Got a set command with options: {options}")

    def add(self, options: list):
        self.logger.log(f"Got an add command with options: {options}")

        if options[0] in self.commits.keys():
            print(f"Already have a transaction for {options[0]}. Commit that first before starting a new one.")

        else:
            self.commits[options[0]] = {
                "Amount": None,
                "Price": None,
                "Action": "Buy",
                "Date": self.get_date()
            }

            self.display()

    def use(self, options: list):

        current = self.commits.get(options[0])
        if current is not None:
            # print(current)
            self.commit_context = options[0]
            self.display()
        else:
            print(f"No transaction found for {options[0]}")

    def display(self):

        if self.commit_context is not None:
            current_commit = self.commits.get(self.commit_context)

            print("===================================================")
            print(f"Current Transaction: {self.commit_context}:")
            print(f"  Options:")

            for k, v in current_commit.items():
                print(f"    {k}: {v}")

            print("===================================================")
        else:
            for k, v in self.commits.items():
                print("------------------------------------------------------")
                print(f"Transaction: {k}:")
                print(f"  Options:")
                for a, b in v.items():
                    print(f"    {a}: {b}")

            print("------------------------------------------------------\n\n")




    def get_date(self):
        return datetime.datetime.now().strftime("%Y-%m-%d")


if __name__ == "__main__":
    main()