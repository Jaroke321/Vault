from .prompt import Prompt
from .logger import Logger

def main():

    logger = Logger(log_file="logs/Vault_testing_1.log")

    commands = {"add": ["add", "buy", "get"]}

    prompt = Prompt(project_name="Vault", logger=logger, cmd_dict=commands)

    prompt.render()

if __name__ == "__main__":
    main()