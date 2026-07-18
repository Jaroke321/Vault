# AGENTS.md

Vault is a single self-contained interactive CLI (a REPL prompt) for tracking personal
finance/assets, backed by an embedded SQLite file. There are no servers, ports, or external
services to start. See `README.md` for the full command reference and usage.

### Environment / running
- The project requires **Python >= 3.14**, which is not available via apt. It is provided by
  `uv` (installed at `~/.local/bin`, on the default `PATH`), and the project is installed
  editable into `.venv`. The startup update script keeps this in sync — you do not
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
- You must use `vault --test` when testing, never omit `--test` since that will interact with the actual DB

### Running tests
- The `test` skill is the only sanctioned way to run Vault's checks. Do not invoke
  `compileall`, the smoke-test driver, or any other test command directly outside of it.
- Only run the `test` skill when the user explicitly asks for it, or when you have just
  finished implementing a task and are verifying the result. Don't run it speculatively
  or after every small edit.

### Software Lifecycle
- The intended stages of development for this project is:
  - Implementing
  - Ready for review
  - Testing
  - Draft PR

### Notion integration (PR / MR Hub)
This project tracks tasks and PR writeups in Notion, via the `notion-task`
and `pr-writeup` skills. Facts below verified live on 2026-07-18 — re-verify
by fetching the data source if a skill reports a schema mismatch.

- **Tasks Tracker** data source: `collection://39b03921-d4c3-8084-950c-000b702f12cb`
  (database page: https://app.notion.com/p/39b03921d4c38021b492c0c0d3b12375).
  Task ID lives in the `Unique ID` property (`auto_increment_id`, a bare
  integer). Other properties: `Task name` (title), `Status`, `Priority`,
  `Effort level`, `Task type`, `Assignee`, `Description`, `Start Date`/
  `End Date`, `Git Branch`, `Projects` (relation), `PR / MR Hub` (relation,
  see below).
- **PR / MR Hub** data source: `collection://39c03921-d4c3-804b-b41d-000b69dfeada`.
  Properties: `Doc name` (title), `Status` (`Open` / `Rejected` / `Merged`),
  `Category` (multi-select — PR writeups use `PR Code Review`), `Reviewers`
  (person), `Tasks Tracker` (relation to the Tasks Tracker data source
  above), `userDefined:URL` (the GitHub PR link).
- **The `Tasks Tracker` ↔ `PR / MR Hub` relation is two-way** — setting
  `Tasks Tracker` on a new PR / MR Hub page automatically makes it appear
  under that task's `PR / MR Hub` field. Never write both sides by hand.
- Branch naming contract: `notion-task` names branches `task-<task_id>-<slug>`
  specifically so downstream tools (code review, `draft-pr`, `pr-writeup`)
  can recover the task ID from `git branch --show-current` without
  re-querying Notion.
