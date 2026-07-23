---
name: implement
description: Writes the actual code for an accepted plan (a `plans/*.md` file) or a task already scoped in chat — this is where implementation happens. Runs only a quick happy-path smoke test, then a cleanup pass for redundant/sloppy code, then one more short sanity check. Not a substitute for the `test` skill. Use after a plan is accepted, when the user says "implement this" / "start coding" / "write the code", or points at a specific plan file.
disable-model-invocation: false
argument-hint: [path/to/plan.md]
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
---

# Implement

Stage 3 of the dev flow in `AGENTS.md`: **Load task → Plan → Implement →
Test → Commit + push → Draft PR → PR writeup**. This is the only stage that
writes source code. When done, **stop and wait for the user to say to move
forward** — do not run the `test` skill, commit, or open a PR on your own.

## Step 1 — Establish what to implement

In order:

1. **Explicit plan file argument** — read it in full.
2. **A plan already in context** (written earlier this session by the
   `plan` skill) — use it directly; re-read from disk only if it may have
   been edited since.
3. **No plan file at all** — the task is whatever's been discussed in
   chat. Fine for small changes, but confirm scope first if it's not
   already unambiguous.

Treat a plan file as the spec: implement its steps in order. If something
in it turns out to be wrong or inapplicable once you're in the code, stop
and flag it rather than quietly improvising a different approach.

## Step 2 — Write the code

Follow existing conventions (structure, naming, error handling) from
sibling files rather than inventing new patterns. Work through the plan's
steps (or the chat-scoped task) in order, leaving the codebase in a working
state after each step where the plan calls that out.

A quick smoke test while wiring things up — e.g. one `vault --test` run to
confirm a command doesn't crash — is fine if it helps you implement
correctly. This is not the `test` skill: don't scope it to the diff, don't
chase edge cases, don't write a report.

## Step 3 — Cleanup pass

Once the plan's steps are done, review the diff (`git diff`) for anything
unnecessary, redundant, or sloppy: dead code, leftover debug prints,
duplicated logic that should share a helper, over-broad error handling,
unused imports/variables. Use the `simplify` skill if it's available;
otherwise do this pass manually. Fix what you find directly — it's still
part of implementation, not a separate stage.

## Step 4 — Quick sanity check

One short, happy-path run to confirm the cleaned-up code still works — not
real testing. For Vault: a single piped `vault --test` session hitting the
main new/changed command. No edge cases, no error paths, no multi-session
coverage — that's the `test` skill's job, later and only if asked.

## Step 5 — Report and stop

Summarize what was implemented (files touched, brief description) and the
sanity-check result. Then **stop** — do not proceed to the `test` skill,
commit, or open a PR; wait for the user to explicitly say to move forward.

## Gotchas

- Don't confuse Step 4's sanity check with the `test` skill — if the user
  asks you to "test" the change, that means invoke the `test` skill, not
  repeat this step.
- If the plan file doesn't match the current code (edited since, or the
  codebase moved on), stop and tell the user rather than implementing
  against a stale plan.
