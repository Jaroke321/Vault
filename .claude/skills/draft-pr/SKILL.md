---
name: draft-pr
description: Open a Draft PR for the current branch. If a Notion task is in context (loaded via the notion-task skill, or recoverable from a task-<N> branch name), the PR description links and summarizes that task; otherwise the description is generated from the diff against the default branch. Use when the user says "open a draft PR", "create a draft PR", "draft PR for this branch", or similar.
disable-model-invocation: true
argument-hint: [notion-task-id]
allowed-tools: Bash, mcp__claude_ai_Notion__notion-query-data-sources, mcp__claude_ai_Notion__notion-fetch, mcp__claude_ai_Notion__notion-search
---

Creates a **draft** PR (`gh pr create --draft`) for the current branch. The
body's source material depends on whether this work is tied to a Notion
task:

- **Notion task in context** → description links the task and summarizes it.
- **No Notion task** → description is generated from `git diff`/`git log`
  against the default branch.

This skill pushes the branch and opens a PR — both visible, hard-to-reverse
actions. Always show the drafted title/body and get explicit confirmation
before running `git push` or `gh pr create`.

## Step 1 — Gather git state

```bash
git rev-parse --is-inside-work-tree          # bail if not a repo
git branch --show-current                    # current branch
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
# fallback if the above is empty: check which of main/master exists on origin
git ls-remote --heads origin main master
```

Use the resolved default branch as `$base` for everything below. If the
current branch *is* `$base`, stop and tell the user there's nothing to PR.

Then check for an existing PR before drafting a new one:

```bash
gh pr view --json url,isDraft,title 2>/dev/null
```

If one already exists, report its URL/title and stop — don't create a
duplicate. (If the user wants it updated instead, that's a different task.)

Check whether there's anything to PR at all:

```bash
git fetch origin "$base" --quiet
git log --oneline "origin/$base..HEAD"
```

If this is empty, tell the user the branch has no commits ahead of
`origin/$base` and stop.

## Step 2 — Determine whether a Notion task applies

Check, in order, and use the first that resolves:

1. **Explicit argument** — if invoked with a bare integer argument, that's
   an explicit Notion task ID override. Use it and skip to Step 3.
2. **Already in this session's context** — if a Notion task was already
   loaded earlier in this conversation (e.g. via the `notion-task` skill),
   reuse that task's details directly. Don't re-fetch.
3. **Branch name contract** — the `notion-task` skill names branches
   `task-<task_id>-<slug>`, specifically so downstream tools like this one
   can recover the task ID. Check the current branch:

   ```bash
   git branch --show-current | grep -oP '^task-\K\d+'
   ```

   If it matches, that's the task ID.

If none of the three resolve, there is no Notion task — go to Step 4 (diff-based description).

## Step 3 — Fetch the Notion task (only if Step 2 resolved an ID)

This uses the same **Tasks Tracker** database as the `notion-task` skill
(keep these facts in sync with that skill if the workspace database ever
changes):

- Data source: `collection://39b03921-d4c3-8084-950c-000b702f12cb`
- Task ID lives in the `Unique ID` property.

```json
{
  "data": {
    "data_source_urls": ["collection://39b03921-d4c3-8084-950c-000b702f12cb"],
    "query": "SELECT * FROM \"collection://39b03921-d4c3-8084-950c-000b702f12cb\" WHERE \"Unique ID\" = ?",
    "params": ["<task_id as string>"]
  }
}
```

Fetch the resulting page with `notion-fetch` to get `Task name`, its URL,
and the `## Task description` body. If the ID doesn't resolve (deleted,
archived, or simply wrong), tell the user, and fall through to Step 4
instead of failing outright — a diff-based description is better than no
PR.

Build the body's Notion section:

```
## Notion Task

[Task <id>: <Task name>](<page url>)

<Task description text, lightly trimmed — not the raw sub-task checklist>
```

Title: `Task <id>: <Task name>`.

Then continue to Step 5 (still add a short Summary of the actual code
changes — the Notion description explains *why*, not *what changed in this
diff*).

## Step 4 — Diff-based description (no Notion task)

```bash
git diff "origin/$base...HEAD"
git log --oneline "origin/$base..HEAD"
```

Read the diff and commit log, then write:
- **Title** — a concise imperative summary (like a commit subject) of the
  overall change, not just the last commit's message.
- **Summary** — 2-5 bullets covering the substantive changes (why, not a
  line-by-line diff retelling).

## Step 5 — Assemble the body

```
## Summary
- <bullet>
- <bullet>

## Notion Task           <- only if Step 3 ran
[Task <id>: <Task name>](<page url>)

<task description>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Step 6 — Confirm, then push and open the PR

Show the user the exact title and body, plus what will happen: branch to
push (if needed) and base branch to PR against. Wait for confirmation —
don't push or create the PR silently, per the same rule this project's
`commit` skill follows.

Check if the branch needs pushing:

```bash
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null   # has upstream?
git rev-list @{u}..HEAD --count 2>/dev/null                        # ahead count
```

On confirmation:

```bash
git push -u origin "$branch"     # only if no upstream, or local is ahead

gh pr create --draft --base "$base" --title "<title>" --body "$(cat <<'EOF'
<body>
EOF
)"
```

Report the PR URL `gh pr create` returns.

## Gotchas

- Don't invoke the `notion-task` skill itself from here — it regenerates a
  branch slug from the task name and may not match the current branch's
  slug exactly, which would create/checkout a *different* branch mid-flow.
  Fetch the Notion page directly (Step 3) instead.
- Session context (Step 2.2) can go stale if the user pivoted to a
  different task since loading it — prefer the branch-name contract
  (Step 2.3) if the two would ever disagree.
- Never use `--no-verify` or force-push here; if `git push` fails because
  the remote branch diverged, stop and ask the user rather than
  force-pushing.
