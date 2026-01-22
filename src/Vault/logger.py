import datetime
from pathlib import Path

class Logger:
    def __init__(self, log_file: str):
        # Determine the base directory of the project (one level up from src/Vault)
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.log_file = base_dir / log_file

        # Create directory if it doesnt exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, 'a') as f:
            f.write("Starting...\n")

    def _get_timestamp(self):
        """Get current timestamp in readable format"""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, message: str):
        with open(self.log_file, 'a') as f:
            f.write(f"{self._get_timestamp()}: {message}\n")