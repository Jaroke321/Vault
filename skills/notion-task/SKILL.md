---
name: notion-task
description: Load a Notion task (and optionally one of its sub-tasks) as working context by Task ID, and create/resume a git branch encoding the task number. Use when the user says "look at Notion task N", "pull up task N", "load task N sub-task M", "start task N", or references a numbered task from the Tasks Tracker Notion database.
---

Fetches a task from the user's **Tasks Tracker** Notion database by its
numeric Task ID, optionally narrows to one sub-task within it, folds the
content into conversation context for whatever work follows, and creates
(or resumes) a git branch whose name encodes the task number. That
branch name is the hand-off point for a later, separate code-review step
that needs to recover which Notion task a diff belongs to — this skill
does not do code review itself, it just makes the task number recoverable
from `git branch --show-current`. It does not write any other files.

Verified against the live workspace on 2026-07-17 (queried task 7 end to
end); the IDs below are this workspace's actual database, not examples.

## Database facts (hardcoded — this workspace only)

- Database page: `https://app.notion.com/p/39b03921d4c38021b492c0c0d3b12375`
- Data source (for queries): `collection://39b03921-d4c3-8084-950c-000b702f12cb`
- Task ID lives in the **`Unique ID`** property (`auto_increment_id` — a
  bare integer like `7`, never `TASK-7`).
- Other properties: `Task name`, `Status`, `Priority`, `Effort level`,
  `Task type`, `Assignee`, `Description`, `Start Date`/`End Date`,
  `Git Branch`, `Projects` (relation), `PR / MR Hub` (relation).
- **There is no sub-task database or relation.** Sub-tasks are a plain
  GFM checklist (`- [x]` / `- [ ]`) inside the task page body, under a
  `## Sub-tasks` heading. They have no stable ID — only position in that
  list. Pages typically also have `## Task description` above the
  checklist and `## Supporting files` below it.

## Procedure

**1. Parse the request** into `task_id` (required integer) and an
optional `subtask` specifier (everything after the task ID). If
`subtask` is a bare integer, treat it as a 1-based index into the
`## Sub-tasks` checklist. Otherwise treat it as a case-insensitive
substring to match against checklist item text.

**2. Resolve the Task ID to a page**, via `notion-query-data-sources`:

```json
{
  "data": {
    "data_source_urls": ["collection://39b03921-d4c3-8084-950c-000b702f12cb"],
    "query": "SELECT * FROM \"collection://39b03921-d4c3-8084-950c-000b702f12cb\" WHERE \"Unique ID\" = ?",
    "params": ["<task_id as string>"]
  }
}
```

Pass `task_id` as a string param — verified this coerces fine against
the numeric column. The `id` field of the single result row is the page
UUID.

If `results` is empty, the ID may not exist or may be **archived**
(SQL mode has no archive support). Fall back to `notion-search` scoped
to the database — `page_url: "https://app.notion.com/p/39b03921d4c38021b492c0c0d3b12375"`,
`query: "task <task_id>"` — before telling the user the task wasn't found.

**3. Fetch the full page** with `notion-fetch` using the UUID from step 2
(or its `url` field). This returns the properties block plus the
`## Task description` / `## Sub-tasks` / `## Supporting files` content.

**4. If a sub-task was requested**, parse the `- [x]`/`- [ ]` lines under
`## Sub-tasks` in document order and pick the one matching the index or
substring. If nothing matches, say so and show the full checklist
instead of guessing.

**5. Create or resume a git branch encoding `task_id` (and the sub-task,
if any).** Skip this step entirely (and say so) if the working directory
isn't a git repository — check with `git rev-parse --is-inside-work-tree`.

Naming convention: **`task-<task_id>-<slug>`**, where `<slug>` is a
**short (3-6 word) kebab-case summary you write yourself** of whichever
is more specific to what's about to be worked on:
- Sub-task requested → summarize *that sub-task's* checklist text (not
  the parent task name). Different sub-tasks of the same task must
  produce different slugs, so different sub-tasks get different
  branches — working sub-task-to-sub-task shouldn't collide or silently
  reuse another sub-task's branch.
- No sub-task requested → summarize the `Task name` property.

Don't mechanically truncate the raw Notion text at a character limit —
that produces mid-word cutoffs and useless slugs. Write it the way you'd
name a branch by hand: capture the essence, drop filler words. E.g. task
7 with no sub-task ("Convert existing functions / use cases to class
structure") → `task-7-class-based-commands`; task 7 sub-task 3 ("Create
`commands/update.py` → `UpdateCommand(BaseCommand)`; move `cmd_update`
into `entry_point`...") → `task-7-update-command-class`. Lowercase,
alphanumeric-and-hyphens only.

Check for an **exact** existing branch, not a wildcard on the task
number alone (a wildcard would match a sibling sub-task's branch and
wrongly reuse it):

```bash
branch="task-<task_id>-<slug>"
if git rev-parse --verify --quiet "refs/heads/$branch" >/dev/null; then
  git checkout "$branch"
else
  git checkout -b "$branch"
fi
```

Branch from **current HEAD** — don't switch to main/master first, don't
stash or discard anything, don't fetch. If `checkout -b` still fails
because the name exists (a race with the check above), fall back to
plain `git checkout "$branch"`. Report the resulting branch name to the
user either way, including when it was reused rather than created.

**6. Summarize into context** — don't dump the raw fetch payload. Report:
- `Task <id>: <Task name>` — Status, Priority, Effort level
- The branch that was created or resumed
- The `## Task description` text
- Either the full sub-task checklist with checked/unchecked state and a
  completion count (`7/10 done`), or, if a specific sub-task was
  requested, that item's text plus its checked state (and briefly note
  its neighbors for continuity)

This summary is what subsequent work should be grounded in — don't
re-fetch the page again later in the same session unless the user asks
for a refresh.

**7. Mark Notion Task as In Progress** Go back to the notion task that was found and mark it as In Progress if it is not already.

## Gotchas

- **`Git Branch` on the task page is not a reliable signal for "am I on
  the right branch."** Verified example: task 7's `Git Branch` property
  points at `cursor/task-7-commodity-command-64d4`, a different branch
  than what's actually checked out in the repo for that task. Don't
  infer or validate the current git branch from it, and don't confuse it
  with the branch *this skill* creates locally (step 5) — they're
  unrelated, and this skill never writes back to that Notion property.
- **The downstream code-review step's only contract is the `task-<N>`
  token** — it recovers the Notion task ID by regex on the branch name,
  nothing else. Keep the `task-<task_id>-` prefix exact (no `notion-`
  prefix, no zero-padding) even as slugs vary; don't rename branches
  created by this skill by hand.
- **Sub-task numbers are positional, not stable IDs.** If someone adds
  or reorders checklist items in Notion, "sub-task 3" now means
  something else. Always re-derive the index from the live fetch, never
  cache it across sessions.
- **Not every integer is a valid Task ID** — gaps exist (e.g. an
  observed workspace had IDs 6, 7, 8, 10, 11 with 9 missing/archived).
  Don't assume a gap is an error; check the archived fallback in step 2
  before reporting failure.
- **`notion-search` alone is noisy** for this — the workspace has other
  pages (PR-review pages, etc.) that mention "task" without being Tasks
  Tracker rows. Prefer the SQL lookup in step 2; only use search as the
  archived-task fallback, scoped to the database's `page_url`.
