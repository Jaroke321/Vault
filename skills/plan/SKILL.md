---
name: plan
description: Turn the current task context (usually a Notion task loaded via the notion-task skill) into a detailed, stepped implementation plan written to a gitignored .md file, and stop for user approval before any implementation. Use when the user says "write a plan", "plan this out", "make an implementation plan", or after loading a Notion task as the next step in the dev flow.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
---

Writes a thorough, stepped implementation plan for the task currently in
context and saves it to a gitignored file in the repo. This is stage 2 of
the dev flow in `AGENTS.md`: **Load task → Plan → Implement → Test →
Commit + push → Draft PR → PR writeup**. Writing the plan draft does not
require approval to produce, but **the `implement` skill must not run
until the user explicitly accepts the plan.**

This skill only writes the plan file. It does not implement anything, does
not run tests, and does not touch git branches (that's `notion-task`'s job).

## Step 1 — Establish the task context

Prefer, in order:

1. **Already in session context** — a task loaded earlier via the
   `notion-task` skill. Use it directly; don't re-fetch.
2. **Branch name contract** — if no task is in context but the current
   branch matches `task-<id>-<slug>` (see `AGENTS.md`), that's a signal a
   Notion task exists for this work. Invoke the `notion-task` skill
   yourself to load it before continuing, rather than asking the user to.
3. **User-supplied context** — the user describes the task inline, pastes
   a spec, or references a non-Notion source. Use that as-is.

If none of these resolve, ask the user what the plan should cover rather
than guessing.

## Step 2 — Understand the codebase impact

This is the part that separates a real plan from a restated task
description. Before writing a single step:

- **Locate every file the task will touch.** Use Grep/Glob to find the
  relevant modules, not just the obvious one named in the task. For Vault,
  check `src/Vault/commands/`, `src/Vault/db_handler.py`, `src/Vault/cli.py`,
  `src/Vault/test_data.py`, and `help.py` for anything that references the
  behavior being changed.
- **Trace ripple effects.** For each candidate change, ask:
  - Does this change a function signature, CLI argument shape, or DB
    schema that other commands depend on?
  - Does it affect `help.py` output, `test_data.py` seed fixtures, or
    other commands that read the same fields?
  - Does it change staged-vs-committed semantics (`update` → `commit`)
    or anything else `AGENTS.md` calls out as a Vault-specific invariant?
  - Are there other call sites (Grep for the symbol/field name) that
    silently assume the old behavior?
- **Check for existing conventions to follow** — read at least one
  sibling command/module fully so the plan proposes code that matches
  existing patterns (e.g. `BaseCommand` structure, error handling style)
  rather than inventing a new shape.
- If the task is a sub-task from a larger Notion task, skim the sibling
  sub-tasks (already in context from `notion-task`) for anything the
  current step might conflict with or depend on.

Do not skip straight to writing steps from the task description alone —
the point of this skill is catching what the task description doesn't
say.

## Step 3 — Write the plan file

Directory: `plans/` at the repo root (create it if missing). It is
gitignored — see Step 4.

Filename: `task-<id>-<slug>.md` matching the branch-naming convention from
`notion-task` when a Notion task is in context (reuse the exact slug the
branch used, don't regenerate a different one), otherwise
`<short-kebab-slug>.md` describing the work.

Structure the plan as:

```markdown
# Plan: <task title>

Source: <Notion task link, or "user-supplied" if no Notion task>
Branch: <current branch>
Written: <date>

## Goal

<1-3 sentences: what "done" looks like, in outcome terms not
implementation terms.>

## Context & constraints

<Relevant existing behavior, invariants, or conventions this plan must
respect — pulled from Step 2's investigation. Cite file:line for
anything load-bearing.>

## Ripple effects

<Everything from Step 2 that isn't the "obvious" part of the task —
other call sites, schema/CLI-shape changes, docs or fixtures that need
updating, commands whose behavior shifts as a side effect. If genuinely
none, say so explicitly rather than omitting the section — an omission
reads as "not checked," an explicit "none found" reads as "checked.">

## Steps

1. **<short imperative title>** — `path/to/file.py`
   <what changes and why; enough detail that implementation doesn't
   require re-deriving the approach, but not a full code dump>
2. ...

Order steps so each is independently coherent (e.g. schema/model changes
before the commands that use them; shared helpers before call sites) and
the codebase is left in a working state after each one if the plan is
large enough that it might be implemented across multiple sessions.
each step in the plan should be small increments towards the overall goal.
Prefer many small steps to few larger ones.

## Open questions

<Anything ambiguous in the task that you resolved by assumption — state
the assumption explicitly so the user can correct it during review. Omit
this section if there were none.>
```

Keep steps concrete and file-scoped — a step like "update the update
command" is too vague; "add a `--currency` flag to `UpdateCommand` in
`src/Vault/commands/update.py`, threading it through to `db_handler.py`'s
`update_field`" is the right altitude.

## Step 4 — Ensure the plans directory is gitignored

Check `.gitignore` for a `plans/` entry; add one (with a short comment,
matching the style of existing entries) if missing. This is a repo-tracked
change, unlike the plan file itself — mention it to the user if you add it.

```bash
grep -qxF 'plans/' .gitignore || printf '\n# Implementation plans (local scratch, not shipped)\nplans/\n' >> .gitignore
```

## Step 5 — Present and stop

Show the user the plan's path and its full content (or a summary if very
long, but the file itself always has the full detail). Then **stop and
wait for explicit approval** — do not invoke the `implement` skill, do not
edit source files, and do not run `git add`/commit on the plan file (moot
since it's gitignored, but don't start touching source either) until the
user accepts the plan or asks for revisions.

If the user requests changes, edit the same file in place rather than
creating a second version — the file should always reflect the current
accepted (or proposed) plan, not a history of drafts.

## Gotchas

- Don't invoke `notion-task` if a task is already loaded in this session —
  re-fetching risks the same staleness issue called out in that skill's
  own docs.
- Don't write implementation code, even as a "preview," inside the plan
  file — pseudo-code or short illustrative snippets are fine when a step
  is non-obvious, but the plan is a spec, not the implementation.
- If Step 2's investigation surfaces something that makes the task as
  described a bad idea (conflicts with an existing invariant, duplicates
  existing functionality, etc.), say so plainly in **Context & constraints**
  or **Open questions** rather than silently planning around it — the user
  may want to change the task's scope, not just the plan.
