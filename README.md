# Vault

A simple Python CLI to track your personal finance and asset portfolio.

## Overview

Vault tracks records across a fixed set of categories — **Cash**, **Retirement**, **Asset**, **Debt**, and **Investment** — records monthly snapshots of their values, and computes your net worth over time. Debt records can be linked to a backing asset (e.g. a mortgage to its house) to show balance/value/equity together, and Investment holdings (physical commodities, stocks, ETFs) are automatically valued using live market prices.

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

Type `<command> usage` for detailed help on any command (e.g. `update usage`).

### Available Commands

#### Field Management

Categories are fixed and code-defined — `cash`, `retirement`, `asset`, `debt`, `investment` — not created at runtime. Each has its own typed fields: `debt` carries an optional interest rate and backing link; `investment` carries a required price-tracking symbol and a per-record unit (so metals in troy oz and stocks in shares can coexist under the same category).

- `field add cash|retirement|asset|debt <name>` — register a new record
- `field add investment <name> <symbol>` — register an investment record; the symbol is required and its unit is derived from it (run `investment options` for known symbols, or use any stock/ETF ticker)
- `field remove <name> [reason]` — close a record, history preserved (reason: `active`/`sold`/`paid_off`/`closed`, default `closed`). Re-adding the same name afterward creates a brand-new record rather than reopening the old one — so selling a house and buying a new one under the same name gives two independent snapshot series, not one record with a value that appears to jump
- `field list` — list all active records grouped by category, each showing its own unit
- `field set <name> note <text>` — attach a free-text note to any record
- `field set <name> apr <rate>` — set a debt's interest rate
- `field set <name> symbol <symbol>` — change an investment's price-tracking symbol
- `field set <name> backing <asset>` / `field set <name> backing clear` — link (or unlink) a debt to an active asset-side record (Asset, Cash, Retirement, or Investment) — purely for the display-only balance/value/equity view in `summary`; it never affects the net worth totals, since the backing record's value is already counted through its own row
- `field set <name> replaces <old-name>` — mark this record as the successor of a prior one sharing the same name (for future reporting continuity)
- `field set <name> status <status>` — relabel a record's lifecycle status directly, independent of closing it

#### Recording Values

Values are staged as pending commits and must be committed to be saved.

- `update` — interactive mode: prompts for all active fields for the current month
- `update <field> <value> [-m YYYY-MM]` — stage a value for a single field (a dollar value for monetary categories, a quantity for Investment); defaults to the current month
- `-m` / `--month` — target a specific month instead of the current one (format `YYYY-MM`, not in the future); the flag can appear anywhere among the arguments, e.g. `update checking 5000 -m 2026-03` or `update -m 2026-03 checking 5000`

#### Committing Values

- `commit` — commit all pending updates (prints any remaining staged entries afterward)
- `commit <n> [n ...]` — commit one or more specific pending updates by index
- `commit list` — show the pending staged table with index numbers
- `commit undo` — reverse the most recent commit
- `commit undo <n>` — reverse the last N commits
- `commit history` — show past commits, most recent first, numbered to match `commit undo <n>`

Staged updates are **not** reprinted after every command. The bottom toolbar shows the staged count and target month(s); use `commit list` or **F2** to review the full table before committing.

Undo is a session-only, in-memory stack — it is not persisted across
restarts. Reversing a commit restores the exact prior row (its value and
original recorded timestamp) if one existed, or removes the row entirely if
the commit had newly created it.

#### Viewing Data

Fields with a note show a trailing `*` in `summary` and `show` table output, with a `* = has note` legend when any noted field appears in that view.

- `show` — table of the last 6 months across all fields
- `show <n>` — table of the last N months
- `show <field>` — month-over-month trend for a single field; prints the field's full note and APR (when set)
- `show <field> <n>` — trend for a single field over the last N months; same note/APR header as `show <field>`
- `show <category>` — trend for each active field in that category (note and APR shown per field when set)
- `diff <m1> <y1> <m2> <y2>` — compare all fields between two months (e.g. `diff 1 26 3 26` → January 2026 vs. March 2026)
- `diff <field> <m1> <y1> <m2> <y2>` — compare one field between two months
- Months are given as `<month> <year>` pairs; two-digit years mean 20xx (`26` → 2026)
- `summary` — net worth snapshot: Cash/Retirement/Asset/Investment as assets, Debt as liabilities. Debts with an APR set show the rate under the balance. A Debt linked via `field set <name> backing <asset>` prints its balance, the backed record's value, and the resulting equity — display only, already reflected in the top-line net worth without double-counting

#### Exporting & Importing Data

- `export csv` — dump the complete recorded history (all months, all active fields) to CSV on stdout
- `export csv <filename>` — same, written to `<filename>` instead
- `import csv <filename>` — read a wide-format CSV (the shape `export csv` produces) back into the database

The CSV is "wide": one row per month, one column per active field, with raw numeric values (no currency formatting) so it can be used directly in a spreadsheet. The first two rows are headers — a `category` row followed by the `month`/field-name row — so each field column carries its category alongside its name. Deactivated fields are excluded, consistent with `show`/`summary`.

On import, fields named in the header under a known, non-`investment` category that don't exist yet are auto-created. A cell with no existing value for that field/month is committed immediately; a cell that would overwrite an existing value is staged as a pending commit instead (review with `commit list`), so nothing is silently overwritten. Empty cells are skipped; non-numeric cells are skipped with a warning; columns naming an unrecognized category are reported as errors and skipped.

**Legacy CSVs** (exported before the category header row existed) still import for columns that name already-active fields. Columns naming unknown fields are reported as errors and skipped — without a category row there is no category to auto-create them under.

**Investment columns are never imported**, in either CSV form — a CSV has no way to carry the symbol a fresh investment record needs, and export itself doesn't distinguish a quantity from a plain value, so there's no reliable way to bring that data back in. Import always reports a warning and skips the column; the CSV round trip is value-only.

#### Investment Pricing

Investment records (metals, other commodities, stocks/ETFs) each carry a required price-tracking symbol and a per-record unit, set when the record is created. On startup, Vault fetches live market prices and uses them to convert quantities to USD in the `summary` output. Prices are cached locally so the last known value is used if a fetch fails.

- `field add investment <name> <symbol>` — register an investment record (see Field Management above); this is the only way to set its symbol, there is no separate tag/untag step
- `investment override <field> <price>` — lock a manual price per unit (takes precedence over live prices)
- `investment override <field> clear` — remove the price lock and resume using live/cached prices
- `investment list` — show all investment records with their current price and source (live, cached, or override)
- `investment options` — list all known commodity symbols, name aliases, and units, grouped by category (static reference data; works without network)
- `investment refresh` — re-fetch live prices mid-session

**Supported symbols:**

| Symbol | Name(s)              | Unit        |
|--------|----------------------|-------------|
| XAU    | gold                 | troy oz     |
| XAG    | silver               | troy oz     |
| XPT    | platinum             | troy oz     |
| XPD    | palladium            | troy oz     |
| HG     | copper               | lb          |
| CL     | oil, crude oil, wti  | barrel      |
| BZ     | brent                | barrel      |
| NG     | natural gas          | MMBtu       |
| ZW     | wheat                | bushel      |
| ZC     | corn                 | bushel      |
| ZS     | soybeans, soybean    | bushel      |
| KC     | coffee               | lb          |
| SB     | sugar                | lb          |
| CC     | cocoa                | metric ton  |
| CT     | cotton               | lb          |

Any other input is treated as a pass-through stock/ETF ticker (a stock's symbol is already its own ticker, unlike the futures-style commodities above), and its unit defaults to `shares`. Unlike the fixed list, pass-through tickers have no static typo protection, so `field add investment` validates them with a live lookup at add time and rejects anything that doesn't resolve — this means adding a stock/ETF requires network access, unlike the instant offline add for `XAU`/etc.

**Example workflow (metal):**

```
field add investment gold_oz XAU
update gold_oz 5
commit
summary
```

The `summary` output will show:
```
  gold_oz              5.0000 troy oz  ~  $16,250.00  (@$3,250.00/troy oz)
```

**Example workflow (stock/ETF):**

```
field add investment shares_aapl AAPL
update shares_aapl 12.5
commit
summary
```

#### Other

- `help` — display available commands
- `<command> usage` — detailed help for any command (e.g. `update usage`)
- `exit` / `quit` / `q` — exit the application

#### Interactive REPL

These features are active only in a real interactive terminal (`vault`, not piped `vault --test`).

**Completion & history**

- `<TAB>` completes command and subcommand names (fuzzy matching — partial names like `sum` can match `summary`)
- While browsing completions, the first line of each command's usage text appears in the menu's metadata column; `<command> usage` still prints the full usage block
- Gray ghost text suggests the most recent matching prior command as you type
- `<Ctrl-R>` opens reverse history search
- Command history persists across sessions in `logs/.vault_history` (skipped in `--test` mode). The history file format changed with the prompt_toolkit switch — pre-existing readline history is not carried over.

**Status line**

- Bottom toolbar: staged count, target month(s), price freshness (`live` / `cached` / `n/a`), and `[TEST]` in test mode
- Right prompt: current net worth (refreshed after each command)

**Input feedback**

- Known commands are highlighted green; unknown first tokens are red (no error text is printed on submit)
- Bare `update` walks active non-investment fields one prompt at a time, prefilled from the prior month

**Key bindings**

- **F2** — show the pending staged table
- **Ctrl-D** (empty line) — exit (same as `exit` / `quit` / `q`)
- **Esc Enter** — insert a newline for multi-line input

Destructive commands (`field remove`, `commit undo`, CSV import overwrites) ask for confirmation in interactive mode; piped input auto-confirms.

**Testing the REPL without a TTY**

`python -m repl_harness` runs programmatic keystroke checks against a pipe-driven session (no database involved). Use it to verify prompt behavior without manual terminal testing.

## Project Structure

```
Vault/
├── pyproject.toml        # Project configuration and metadata
├── README.md             # Project documentation
├── repl_harness/         # Pipe-input REPL test harness (python -m repl_harness)
├── vault.db              # SQLite database (auto-created at runtime)
└── src/
    └── Vault/
        ├── __init__.py
        ├── cli.py          # CLI logic and entry point
        ├── data_types/     # Category classes (Cash, Retirement, Asset, Debt, Investment)
        ├── db_handler.py   # SQLite database layer
        ├── helper.py       # Color codes and formatting utilities
        ├── logger.py       # Logging utility
        ├── price_fetcher.py # Live investment price fetching
        ├── prompt.py       # Interactive prompt implementation
        └── status.py       # REPL status toolbar and net-worth rprompt
```

## License

This project is licensed under the MIT License.
