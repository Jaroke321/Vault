# Vault

A simple Python package to keep track of your metal portfolio.

## Overview

Vault is a CLI tool designed to help you manage and track your metal portfolio.

## Requirements

- Python >= 3.14

## Setup

### Installation from source

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Vault
   ```

2. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

## Usage

After installation, you can run the tool using the `vault` command:

```bash
vault
```

The tool will start an interactive prompt where you can enter commands:

```
Vault/>
```

### Available Commands

- `add` / `buy` / `get`: Logs an add command with specified options.
- `set`: Logs a set command with specified options.

## Project Structure

```
Vault/
├── pyproject.toml      # Project configuration and metadata
├── README.md           # Project documentation
└── src/
    └── Vault/
        ├── __init__.py
        ├── cli.py        # CLI logic and entry point
        ├── db_handler.py # Database interactions (TODO)
        ├── logger.py     # Logging utility
        └── prompt.py     # Interactive prompt implementation
```

## Environment Variables

Currently, no environment variables are required.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (TODO: add LICENSE file).
