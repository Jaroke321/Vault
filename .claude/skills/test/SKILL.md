---
name: test
description: Run Vault checks scoped to what actually changed — compileall plus vault --test sessions invented from the diff to hit new/changed code paths — then turn failures into an actionable report. Use when asked to run tests, check whether recent changes pass, or diagnose test failures.
---

# Test

Run only the checks relevant to what changed, then explain failures — don't
just dump raw output back at the user.

Vault has **no pytest/unittest suite**. Checks are: `python -m compileall`
plus agent-built sessions piped into `vault --test`. There is no smoke-test
shell harness — read the diff and invent sessions that exercise the changed
code (see Vault section below). Do not default to a canned baseline.

## Step 1 — Determine what changed

Get the full set of changed files for this session, not just the working tree:

```bash
git diff --name-only HEAD                                             # uncommitted changes
git diff --name-only "$(git merge-base HEAD <default-branch>)" HEAD   # + this session's commits
```

- Detect `<default-branch>` via `git symbolic-ref refs/remotes/origin/HEAD`, falling back to `main`/`master`.
- If there's no git repo, or no sensible base to diff against, ask the user what changed instead of guessing.
- Union both file lists — this is the diff scope for the rest of this skill.

## Step 2 — Learn how this project tests

For this repo, use the **Vault** section below (and `AGENTS.md`). Do not invent
a pytest/Makefile flow. If working in a different project, fall back to reading
`AGENTS.md` / `CLAUDE.md` / README Testing sections as usual.

## Step 3 — Scope the run to the diff

Do **not** stop at file names or the path→session floor table. Read the actual
diff (`git diff` / commit range), then design sessions that exercise the new
or changed behavior (see Vault **Diff → checks**). Skip docs/skills-only diffs
(no vault run).

State the targeted command(s) — and which changed lines/branches they aim to
hit — before running them.

## Step 4 — Run it

Execute the scoped command(s). Run all of them even if an earlier one fails, so the report is complete.

## Step 5 — Interpret failures

Don't just paste the raw output. For each failure:
- Open the failing check and the source it exercises (Grep/Read).
- Cross-reference against the Step 1 diff — a failure touching changed code is almost always caused by that change; a failure in something the diff never touched is more likely pre-existing/flaky — say so explicitly.
- Trace the actual root cause rather than describing the symptom generically.

## Step 6 — Report format

For each failure:

### `<test name>`
- **Failure**: one line — what broke (assertion, exception, missing output, nonzero exit)
- **Likely cause**: root-caused explanation citing `file:line`, noting whether it's tied to a file from the Step 1 diff
- **Suggested fix**: a concrete change; include a short code snippet if the fix isn't obvious from the description

If everything passes, say so plainly along with what was actually run and what
the sessions were meant to cover (e.g. "compileall + 2 vault --test sessions
hitting the new debt-asset update branch and field rename — all passed") —
don't invent a report.
End with a one-line summary: `X/Y passed` (plus a note if you fell back to
baseline or widened scope).

---

## Vault — how to run checks

### Binary / mode

- Call `.venv/bin/vault --test` (or `vault --test` with the venv activated).
- **Never** omit `--test` — bare `vault` writes the real `vault.db` at the repo root.
- The project is already installed editable into `.venv` (Python via `uv`; see
  `AGENTS.md`). Do **not** run `pip install -e .` or recreate the venv unless
  `.venv/bin/vault` is missing — then follow `AGENTS.md` / `uv`, not ad-hoc pip.
- `--test` seeds an in-memory DB from `src/Vault/test_data.py` (fields include
  `checking`, `brokerage`, `401k`, `mortgage`, `car_loan`, `gold`, `silver`),
  with no network and no persisted writes.

### Driving the REPL

Vault is a blocking REPL that reads newline-separated commands from stdin.
End every session with `exit` (or `quit` / `q`):

```bash
printf 'summary\nexit\n' | .venv/bin/vault --test
```

Capture stdout+stderr, require exit status 0, and assert markers implied by the
commands you ran (examples: `TEST MODE`, `Net Worth Summary`, a field name you
added/updated, `Trend for '…':`, `Exiting Vault...`).

### Gotchas

- `commit` shows a rich progress bar (~0.5s per staged item) — a short pause is expected.
- `update` with no args only prints usage; use `update <field> <value>` (debt fields may need an asset value too).
- `commodity list` / `commodity refresh` print "Price fetcher not available." in `--test` — expected (`price_fetcher=None`). Prefer `commodity tag` / `untag` / `override` for smoke checks.

### Diff → checks

The path table below is a **floor** (which command area to touch at least once),
not the full test plan. Prefer **dynamic sessions derived from the diff**.

1. **Any `src/` file changed** — run:

   ```bash
   .venv/bin/python -m compileall -q src && echo "compile ok"
   ```

2. **Read the patch, invent coverage** — for each changed `src/` file:

   - Open the hunks (`git diff` / commit range). Note new branches, args,
     error messages, renames, and call sites.
   - Design one or more piped REPL sessions whose commands would execute that
     new code. Prefer happy path **and** at least one edge/error path when the
     diff adds validation or alternate branches.
   - Assert markers that prove the new path ran (new success text, specific
     error string, updated values, etc.) — not only generic `TEST MODE`.
   - Use seeded fields from `test_data.py` when possible; add temporary fields
     via `field add` when the change needs a fresh name/category.
   - Union coverage across changed areas into as few sessions as practical,
     but split when setup would interfere.

3. **Floor sessions** — if after reading the diff you still need a starting
   point for which CLI surface to poke, use this table. **Never** substitute
   the baseline row for a command module whose diff you can exercise more
   specifically. Baseline is last resort for opaque shared modules only, and
   you must say so in the report.

| Changed area | Floor (minimum surface to touch) |
|---|---|
| `src/Vault/commands/field.py` | `field` subcommands relevant to the hunks (`list` / `add` / …) |
| `src/Vault/commands/update.py` | `update` with args matching the changed branch (savings vs debt/asset) |
| `src/Vault/commands/commit.py` | stage with `update` then `commit` |
| `src/Vault/commands/show.py` | `show` forms touched by the diff (all vs named/id) |
| `src/Vault/commands/summary.py` | `summary` (plus setup that makes new summary logic visible) |
| `src/Vault/commands/commodity.py` | `tag` / `untag` / `override` as relevant — not `refresh` alone |
| `help.py`, `base.py`, `cli.py`, `db_handler.py`, `test_data.py`, other `src/Vault/*` | Derive from the hunks; **baseline** (`field list` → `summary` → `exit`) only if you cannot map a tighter session |
| Docs / `.claude/skills` / workflows only | no vault run; compileall N/A |

4. Count each distinct check (compileall, each session) toward `X/Y passed`.
