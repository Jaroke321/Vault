# AGENTS.md

## Cursor Cloud specific instructions

Vault is a single self-contained interactive CLI (a REPL prompt) for tracking personal
finance/assets, backed by an embedded SQLite file. There are no servers, ports, or external
services to start. See `README.md` for the full command reference and usage.

### Environment / running
- The project requires **Python >= 3.14**, which is not available via apt. It is provided by
  `uv` (installed at `~/.local/bin`, on the default `PATH`), and the project is installed
  editable into `/workspace/.venv`. The startup update script keeps this in sync — you do not
  need to reinstall manually.
- Activate the environment before running: `source .venv/bin/activate` (or call binaries
  directly, e.g. `.venv/bin/vault`).
- Run the app: `vault` (real DB) or `vault --test` (seeded in-memory temp DB, no network, no
  persisted changes).
- Non-obvious: the app is a blocking REPL that reads from stdin. To drive it non-interactively,
  pipe newline-separated commands, e.g. `printf 'summary\nexit\n' | vault --test`.
- Non-obvious: staged `update`s are NOT saved until you run `commit` (commit shows a ~0.5s/item
  progress bar). `exit`/`quit`/`q` leaves the prompt.
- The real (non-`--test`) app fetches live commodity prices from Yahoo Finance (`yfinance`) on
  startup; it degrades gracefully to cached/override prices when offline.
- `vault.db` is created at the repo root at runtime and is gitignored (`*.db`); logs go to
  `logs/` (also gitignored).

### Tests / lint
- No test framework (pytest, etc.) is configured. The built-in `vault --test` mode is the
  interactive test harness — it seeds a temp DB via `src/Vault/test_data.py`.
- No linter is configured; use `python -m compileall src` as a basic syntax/lint check.
