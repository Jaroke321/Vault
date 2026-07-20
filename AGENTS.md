# AGENTS.md

Vault is a self-contained interactive CLI (REPL) for personal finance/assets,
backed by embedded SQLite. No servers or external services. See `README.md`
for the command reference.

## Environment

- **Python >= 3.14** via `uv` (`~/.local/bin`); project is editable in `.venv`.
  Activate with `source .venv/bin/activate`, or call `.venv/bin/vault` directly.
- Run: `vault` (real DB) or `vault --test` (seeded in-memory DB; no network;
  no persisted changes). **Never omit `--test` when testing** — that hits the real DB.
- REPL is blocking stdin. Non-interactive: `printf 'summary\nexit\n' | vault --test`.
- Staged `update`s are not saved until `commit`. `exit` / `quit` / `q` leaves the prompt.
- Live prices (`yfinance`) on real startup; degrades to cache when offline.
  `vault.db` and `logs/` are gitignored runtime artifacts.

## Development flow

Work follows this sequence. **Do not advance a stage without explicit user
approval** (except loading a Notion task / writing a plan draft for review).

1. **Load task** — `notion-task` skill. Pulls scope from Tasks Tracker and
   creates/resumes branch `task-<id>-<slug>`.
2. **Plan** — Use the `plan` skill. Writes a detailed, stepped
   implementation plan (with ripple-effect analysis) to a gitignored
   `.md` file under `plans/`. Stop and wait for the user to accept it.
   Do not implement until accepted.
3. **Implement** — Execute the accepted plan only.
4. **Test** — Only when the user asks. Use the `test` skill (not ad-hoc
   `compileall` / `vault --test`). That skill scopes checks to the diff.
5. **Commit + push** — Only when the user asks. Use the `commit` skill.
6. **Draft PR** — Only when the user asks. Use `draft-pr` (`gh pr create --draft`).
   Never open ready-for-review: Claude Code Review runs on draft → ready only.
7. **PR writeup** — Only when the user asks. Use `pr-writeup` to file work,
   tests, description, comments, and reviews into the Notion PR / MR Hub.

Prefer project skills over ad-hoc `git` / `gh` / Notion commands so format
and ordering stay consistent.

## Notion facts

Skills own procedure; keep these IDs here for `pr-writeup` / discovery.
Re-verify by fetching the data source if a skill reports a schema mismatch.

- **Tasks Tracker**: `collection://39b03921-d4c3-8084-950c-000b702f12cb`
  ([page](https://app.notion.com/p/39b03921d4c38021b492c0c0d3b12375)).
  Task ID = `Unique ID` (`auto_increment_id`, bare integer).
- **PR / MR Hub**: `collection://39c03921-d4c3-804b-b41d-000b69dfeada`.
  Writeups use Category `PR Code Review`; link via `Tasks Tracker` relation
  and set `userDefined:URL` to the GitHub PR.
- Relation is two-way — set `Tasks Tracker` on the hub page only; never both sides.
- Branch contract: `task-<task_id>-<slug>` so later skills can recover the
  task ID from `git branch --show-current`.
