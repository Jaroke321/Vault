---
name: pr-writeup
description: Fetch a GitHub PR (current branch's, or a given number), synthesize its description/comments/code review into a writeup, and file that writeup as a new page in this project's Notion PR-hub database, linked to whichever Notion task it belongs to. Use when the user says "write up this PR", "put this PR in Notion", "log this PR to the PR hub", or similar.
disable-model-invocation: true
argument-hint: [pr-number]
allowed-tools: Bash, mcp__claude_ai_Notion__notion-search, mcp__claude_ai_Notion__notion-query-data-sources, mcp__claude_ai_Notion__notion-fetch, mcp__claude_ai_Notion__notion-create-pages, mcp__claude_ai_Notion__notion-get-users
---

Files an entry in this project's Notion PR-hub database summarizing a
GitHub PR — its description, discussion, and code review — and links it to
whichever Notion task the PR belongs to, if any.

This skill has no hardcoded database facts — every project (or every
workspace) may point at a different Notion database, or none at all. It
learns where to write by reading project docs first, the same way the
`test` skill learns how to run tests before running them.

This creates a page other people in the workspace may see. Always show the
drafted writeup and target task link for confirmation before creating it.

## Step 1 — Learn this project's Notion PR-hub facts

Check `AGENTS.md`, `CLAUDE.md`, or similar project docs at the repo root
for a documented Notion integration section — look for a PR/writeup
database's data source ID and its schema (title property, a status-like
property and its options, a relation property back to a tasks database, a
URL property, an optional reviewers property), plus the linked tasks
database's data source ID and task-ID property.

**If documented**, use those facts directly — don't re-discover them.

**If not documented**, ask the user which Notion database PR writeups
should go in (don't guess or invent one). Once they point you at it:
1. `notion-search` / `notion-fetch` it to get its data source URL and full
   schema (property names, types, and — for the status property — its
   option values).
2. If it has a relation property pointing at a tasks/issues database,
   fetch that database's schema too (you'll need its task-ID property to
   resolve task numbers in Step 3).
3. Tell the user what you found and suggest they add it to `AGENTS.md` (or
   equivalent) so future runs of this skill — and anything else that
   touches the same integration — don't have to rediscover it. Offer to
   write it yourself if they'd like; don't do it silently.

Keep the resolved property names/types in mind for Steps 5 and 7 below —
they vary per project, don't assume the ones from any one example.

## Step 2 — Resolve the PR

```bash
gh repo view --json nameWithOwner -q .nameWithOwner   # sanity check we're in a GH repo
```

- If invoked with a numeric argument, that's the PR number.
- Otherwise, resolve the current branch's PR:

```bash
gh pr view --json number,url,title,body,state,isDraft,mergedAt,headRefName,baseRefName,author
```

If that fails (no PR for the current branch and no argument given), ask
the user for a PR number rather than guessing.

## Step 3 — Gather everything from the PR

```bash
NUM=<resolved number>
gh pr view "$NUM" --json number,url,title,body,state,isDraft,mergedAt,headRefName,baseRefName,author,comments,reviews,commits,files
gh api "repos/{owner}/{repo}/pulls/$NUM/comments"   # inline code-review comments (not included above)
```

- `body` — the PR description.
- `comments` — top-level conversation comments.
- `reviews` — review verdicts (approved / changes requested / commented) with their summary bodies.
- The `gh api` call — inline, line-level code review comments (the actual "code review" content).
- `commits`/`files` — for understanding the scope of the change; don't dump these raw, use them for context.

If `gh api .../comments` returns empty, that just means no inline review
comments were left — not a fetch failure.

## Step 4 — Determine the linked Notion task

Only attempt this if Step 1 found (or the user gave you) a tasks database
to relate against. Check, in order, and use the first that resolves:

1. **PR body** — search `body` for a link to a page in that tasks
   database (or, generically, any `notion.so`/`app.notion.com` URL — this
   is often present under a "Notion Task" heading if the PR was opened by
   a companion skill like `draft-pr`). If found, that URL *is* the task
   page — fetch it directly, no query needed.
2. **Branch name contract** — if this project documents a branch-naming
   convention that encodes a task number (e.g. `task-<N>-<slug>`, as used
   by this repo's `notion-task` skill — see `AGENTS.md`), extract the ID
   from `headRefName` and query the tasks database's ID property for it.

If neither resolves, there's no Notion task to link — proceed without one
and say so plainly (don't guess or fabricate a task).

If a task *was* found, fetch its page to confirm its title and get the
page URL for the relation.

## Step 5 — Synthesize the writeup

Don't paste raw comments/reviews — write a real summary, the same way the
`test` skill turns raw failures into a report rather than a dump. Structure:

```
## Summary
<what this PR does, 2-5 bullets, drawn from the description and diff scope>

## Outcome
<merged/open/draft/closed — and if reviewed, the review verdicts (who approved,
who requested changes, and why, in one line each)>

## Discussion & review notes
<synthesized points from comments + inline review comments — group by theme,
not by comment order; call out anything that changed as a result (a comment
that led to a fix) if it's evident from the thread>

## Linked task              <- only if Step 4 resolved one
[<task title>](<task page url>)
```

## Step 6 — Reviewers (best-effort, optional)

Only if the PR-hub schema has a person-type reviewers property *and* the
PR had actual GitHub reviews: try to match each reviewer's GitHub display
name to a Notion workspace user via `notion-get-users`. If a match isn't
reasonably confident (name mismatch, multiple candidates), leave that
reviewer out rather than guessing wrong — this field is a nice-to-have,
not the point of the writeup.

## Step 7 — Create the page

Using the data source ID and property names/types resolved in Step 1,
create one page via `notion-create-pages` with `parent.data_source_id` set
to the PR-hub data source, and properties populated from what you now
know:
- Title property → `PR #<num>: <PR title>`
- Status-like property → map PR state to whichever of its options means
  open/merged/rejected (`isDraft`/open state → the "open" option;
  `mergedAt` set → the "merged" option; closed without `mergedAt` → the
  "rejected"/"closed" option). Use the schema's actual option names, not
  the literal words "open"/"merged"/"rejected", if they differ.
- URL property → the GitHub PR URL
- Relation-to-tasks property → the resolved task's page URL, if any
- Reviewers property → resolved Notion user IDs, if any
- Content → the Step 5 writeup, as markdown

Omit relation/reviewers properties entirely if nothing resolved for them —
don't send empty arrays as a stand-in.

## Step 8 — Report

Give the user the new Notion page's URL, and confirm whether it's linked
to a task (name it) or not.

## Gotchas

- **If the relation between the PR-hub database and the tasks database is
  two-way** (check: does the tasks database have a relation property whose
  `propertyUrl` points back at the same property you're setting?), only
  set it from the *new* PR-hub page's side (Step 8). Don't also try to
  update the task page's relation property by hand — that's redundant and
  risks fighting Notion's own sync. If it's one-way instead, you may need
  to update the task page separately to get the back-link; check before
  assuming either way.
- **Don't invoke the `notion-task` or `draft-pr` skills from here** — this
  skill only needs to *read* the task page for its title/URL, not run
  their branch-management side effects.
- If the PR body's Notion link and the branch-name-derived task ID would
  point to different tasks, prefer the PR body link — it's the more
  direct, human-authored signal for *this specific PR*.
