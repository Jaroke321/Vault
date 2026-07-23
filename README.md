# Vault

A simple Python CLI to track your personal finance and asset portfolio.

## Overview

Vault helps you manage financial fields across categories (e.g. savings, investments, debt), record monthly snapshots of their values, and compute your net worth over time. Fields can have custom units, debt fields support asset value tracking to calculate equity, and physical commodity holdings (gold, silver, etc.) are automatically valued using live market prices.

## Requirements

- Python >= 3.14

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
- `commit undo` — reverse the most recent commit
- `commit undo <n>` — reverse the last N commits

Undo is a session-only, in-memory stack — it is not persisted across
restarts. Reversing a commit restores the exact prior row (its value and
original recorded timestamp) if one existed, or removes the row entirely if
the commit had newly created it.

#### Viewing Data

- `show` — table of the last 6 months across all fields
- `show <n>` — table of the last N months
- `show <field>` — month-over-month trend for a single field
- `show <field> <n>` — trend for a single field over the last N months
- `diff <m1> <y1> <m2> <y2>` — compare all fields between two months (e.g. `diff 1 26 3 26` → January 2026 vs. March 2026)
- `diff <field> <m1> <y1> <m2> <y2>` — compare one field between two months
- Months are given as `<month> <year>` pairs; two-digit years mean 20xx (`26` → 2026)
- `summary` — net worth snapshot with assets, liabilities, and equity breakdown

#### Exporting & Importing Data

- `export csv` — dump the complete recorded history (all months, all active fields) to CSV on stdout
- `export csv <filename>` — same, written to `<filename>` instead
- `import csv <filename>` — read a wide-format CSV (the shape `export csv` produces) back into the database

The CSV is "wide": one row per month, one column per active field, with raw numeric values (no currency formatting) so it can be used directly in a spreadsheet. The first two rows are headers — a `category` row followed by the `month`/field-name row — so each field column carries its category alongside its name. Deactivated fields are excluded, consistent with `show`/`summary`.

On import, fields and categories named in the header that don't exist yet are auto-created. A cell with no existing value for that field/month is committed immediately; a cell that would overwrite an existing value is staged as a pending commit instead (visible via `show` / `commit`), so nothing is silently overwritten. Empty cells are skipped; non-numeric cells are skipped with a warning.

**Legacy CSVs** (exported before the category header row existed) still import for columns that name already-active fields. Columns naming unknown fields are reported as errors and skipped — without a category row there is no category to auto-create them under.

**Debt asset values are not round-trippable.** Export only writes balance snapshots, not debt asset values (set via `update <field> <balance> <asset>`). Import therefore only ever populates the balance side of a debt field.

#### Commodity Pricing

Fields with non-monetary units (e.g. `oz`, `g`, `shares`) can be tagged with a commodity symbol or a stock/ETF ticker. On startup, Vault fetches live market prices and uses them to convert quantities to USD in the `summary` output. Prices are cached locally so the last known value is used if a fetch fails.

- `commodity tag <field> <symbol>` — tag a field as tracking a commodity (`XAU`, `XAG`, `XPT`, `XPD`) or an arbitrary stock/ETF ticker (e.g. `AAPL`)
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

Any other input is treated as a pass-through stock/ETF ticker (a stock's symbol is already its own ticker, unlike the futures-style commodities above). Unlike the fixed list, pass-through tickers have no static typo protection, so `commodity tag` validates them with a live lookup at tag time and rejects anything that doesn't resolve — this means tagging a stock/ETF requires network access, unlike the instant offline tag for `XAU`/etc.

**Example workflow (metal):**

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

**Example workflow (stock/ETF):**

```
field add brokerage shares_aapl
field set brokerage unit shares
commodity tag shares_aapl AAPL
update shares_aapl 12.5
commit
summary
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
