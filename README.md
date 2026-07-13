# Vault

A simple Python CLI to track your personal finance and asset portfolio.

## Overview

Vault helps you manage financial fields across categories (e.g. savings, investments, debt), record monthly snapshots of their values, and compute your net worth over time. Fields can have custom units, debt fields support asset value tracking to calculate equity, and physical commodity holdings (gold, silver, etc.) are automatically valued using live market prices.

## Requirements

- Python >= 3.14
- [uv](https://github.com/astral-sh/uv) (recommended for local development)

## Setup

### Installation from source

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Vault
   ```

2. Install the package:
   ```bash
   pip install .
   ```

### Installation from PyPI

If published to PyPI:
```bash
pip install vault-project
```

## Usage

After installation, run the tool with:

```bash
vault
```

This starts an interactive prompt:

```
Vault/>
```

### Available Commands

#### Field Management

- `field add <category> <name>` — register a new tracked field under a category
- `field remove <name>` — deactivate a field (history is preserved)
- `field list` — list all active fields grouped by category
- `field set <category> unit <unit>` — set the display unit for a category (default: `$`)

#### Recording Values

Values are staged as pending commits and must be committed to be saved.

- `update` — interactive mode: prompts for all active fields for the current month
- `update <field> <value>` — stage a value for a single field
- `update <field> <value> <asset_value>` — stage a value + asset value for a debt field

#### Committing Values

- `commit` — commit all pending updates
- `commit <n> [n ...]` — commit one or more specific pending updates by index

#### Viewing Data

- `show` — table of the last 6 months across all fields
- `show <n>` — table of the last N months
- `show <field>` — month-over-month trend for a single field
- `show <field> <n>` — trend for a single field over the last N months
- `summary` — net worth snapshot with assets, liabilities, and equity breakdown

#### Commodity Pricing

Fields with non-monetary units (e.g. `oz`, `g`) can be tagged with a commodity symbol. On startup, Vault fetches live market prices and uses them to convert quantities to USD in the `summary` output. Prices are cached locally so the last known value is used if a fetch fails.

- `commodity tag <field> <symbol>` — tag a field as tracking a commodity (`XAU`, `XAG`, `XPT`, `XPD`)
- `commodity untag <field>` — remove the commodity tag from a field
- `commodity override <field> <price>` — lock a manual price per unit (takes precedence over live prices)
- `commodity override <field> clear` — remove the price lock and resume using live/cached prices
- `commodity list` — show all tagged fields with their current price and source (live, cached, or override)
- `commodity refresh` — re-fetch live prices mid-session

**Supported symbols:**

| Symbol | Commodity  | Unit        |
|--------|------------|-------------|
| XAU    | Gold       | troy oz     |
| XAG    | Silver     | troy oz     |
| XPT    | Platinum   | troy oz     |
| XPD    | Palladium  | troy oz     |

**Example workflow:**

```
field add metals gold_oz
field set metals unit oz
commodity tag gold_oz XAU
update gold_oz 5
commit
summary
```

The `summary` output will show:
```
  gold_oz              5.0000 oz  ~  $16,250.00  (@$3,250.00/oz)
```

#### Other

- `help` — display available commands
- `exit` / `quit` / `q` — exit the application

## Project Structure

```
Vault/
├── pyproject.toml        # Project configuration and metadata
├── README.md             # Project documentation
├── vault.db              # SQLite database (auto-created at runtime)
└── src/
    └── Vault/
        ├── __init__.py
        ├── cli.py          # CLI logic and entry point
        ├── db_handler.py   # SQLite database layer
        ├── helper.py       # Color codes and formatting utilities
        ├── logger.py       # Logging utility
        ├── price_fetcher.py # Live commodity price fetching
        └── prompt.py       # Interactive prompt implementation
```

## License

This project is licensed under the MIT License.
