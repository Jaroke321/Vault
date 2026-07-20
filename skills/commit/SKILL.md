---
name: commit
description: Reviews changes, write a commit message, commit, and push to origin. Use when the user wants to commit and push work.
disable-model-invocation: true
allowed-tools: Bash
---

## Current git state

Working tree status (staged, unstaged, and untracked):
```
!`git status --short`
```

Recent commits (for message style reference):
```
!`git log --oneline -8`
```

## Instructions

1. **Check for any changes.** If the working tree status above is empty, tell the user there is nothing to commit and stop.

2. **Stage all changes**, tracked and untracked, using the Bash tool:
   - `git add -A`

3. **Get the staged diff** using the Bash tool (`git diff --staged`) to see exactly what will be committed.

4. **Analyze the diff** and write a commit message that:
   - Opens with a short imperative subject line (≤72 chars) summarizing *what* changed
   - Focuses on *why* or *what*, not a line-by-line retelling of the diff
   - Matches the tone and style of the recent commits shown above

5. **Show the proposed commit message** to the user

6. **run** these steps in order using the Bash tool:
   - `git commit -m "<message>"` — create the commit
   - `git push -u origin <branch_name>` — push to remote

7. Report the result: confirm the commit hash and that the push succeeded, or surface any error clearly.
