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

Work follows this sequence, one stage at a time. **After finishing a stage,
stop and wait for the user to explicitly say to move forward** — never
chain into the next stage on your own, even when it seems obvious. Starting
the action a stage itself calls for (loading a task, drafting a plan,
implementing) doesn't need pre-approval; what's gated is moving on
afterward.

1. **Load task** — `notion-task` skill. Pulls scope from Tasks Tracker and
   creates/resumes branch `task-<id>-<slug>`. Stop; wait to be told to plan.
2. **Plan** — `plan` skill. Writes a detailed, stepped implementation plan
   (with ripple-effect analysis) to a gitignored `.md` file under `plans/`.
   Stop and wait for the user to accept it. Do not implement until accepted.
3. **Implement** — `implement` skill. Writes the code for the accepted plan
   (or the task as scoped in chat). Only a quick smoke test and a cleanup
   pass happen here — not real testing. Stop; wait to be told to test.
4. **Test** — Only when the user asks. `test` skill (not ad-hoc
   `compileall` / `vault --test`) — scopes thorough, edge-case checks to
   the diff. Stop after reporting results.
5. **Commit + push** — Only when the user asks. `commit` skill. Stop after
   pushing.
6. **Draft PR** — Only when the user asks. `draft-pr`
   (`gh pr create --draft`). Never open ready-for-review: Claude Code Review
   runs on draft → ready only. Stop after opening.
7. **PR writeup** — Only when the user asks. `pr-writeup` files work,
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
