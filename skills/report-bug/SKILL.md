---
description: File a bug report about PRAWDUCT ITSELF (its skills, hooks, gates, or methodology — not a bug in this product). Writes into the configured incoming-bugs drop-box when a local prawduct checkout is reachable; otherwise captures the bug in THIS product's own backlog and points at GitHub issues. Use when a prawduct gate/skill/hook misbehaves while you work in a product repo.
argument-hint: "[short description of the prawduct bug]"
user-invocable: true
disable-model-invocation: false
---

You are filing a bug report about **prawduct itself** — a defect in its skills,
hooks, gates, `prawduct-hook` subcommands, `lib/`, or methodology — discovered
while working in a product repo that prawduct governs. The report travels
**upstream** to the prawduct project. This channel is **active** only when a
prawduct checkout is reachable on this machine; otherwise it stays inert and the
bug is captured locally instead. Never let this skill error.

## 1. Confirm the bug is in prawduct, not in this product

Before anything else, decide: is the defect in **prawduct's own machinery**
(a `/prawduct:*` skill, a Stop/SessionStart gate, a `prawduct-hook` subcommand,
`lib/`, a methodology guide), or in **this product's** code/specs/backlog?

- **Product bug** → STOP. This is the wrong channel. File it in the product's own
  backlog (`/prawduct:backlog add`) and do not write an upstream report.
- **Prawduct bug** → continue.

If you're unsure, say which way you're leaning and why, and ask the user to
confirm before filing.

## 2. Resolve the inbox

Run:

```
prawduct-hook bug-inbox
```

- **Exit 0** — it prints the inbox directory path. Go to step 3.
- **Exit 1** — no inbox is configured/reachable (the normal case for a plugin-only
  user). Go to step 4. This is not an error.

## 3. File the report upstream (inbox reachable)

1. Read the template at `${CLAUDE_SKILL_DIR}/../../templates/incoming-bug-report.md`
   and fill every field. Be concrete: lead with the symptom, name the exact
   prawduct surface in **Component**, and mark verified-vs-inferred honestly in
   **Root cause** (Principle 5 — Honest Confidence).
2. Derive a filename: kebab-case the title (lowercase, spaces and punctuation →
   single hyphens), append `.md`. E.g. *"Stop gate blocks on in-flight background
   work"* → `stop-gate-blocks-on-in-flight-background-work.md`.
3. **Write** the filled report to `<inbox>/<slug>.md` (the inbox path from step 2).
   The drop-box is gitignored on the prawduct side — a plain file write, no git
   operations, no commit.
4. Confirm to the user: the exact path written, and that a prawduct session will
   triage it (`/prawduct:report-bug` documents the receiving side).

## 4. Capture locally (no inbox — inert fallback)

No upstream checkout is reachable, so **do not** attempt any upstream write, and
**do not** error or nag. Instead:

1. Capture the bug in **this product's own** backlog so the signal isn't lost:
   `/prawduct:backlog add` an item describing the prawduct defect, tagged
   `area=prawduct-upstream` so it's findable as an upstream-facing item.
2. Tell the user they can also report it directly at the canonical issue tracker:
   **https://github.com/brookstalley/prawduct/issues**

That's it — the bug is recorded; nothing fails.

## Why the channel is inert by default

The inbox resolves from machine-specific local signals — the
`PRAWDUCT_BUG_INBOX` env var, then a gitignored `.prawduct/.bug-inbox` pointer
file — and from nothing else. A plugin-only user configures neither, so
resolution returns nothing and this skill takes the local-capture path. The path
is deliberately *not* committed project state: it is an absolute path on one
machine and must not travel to other clones or CI. To turn the channel on, point
`PRAWDUCT_BUG_INBOX` (or `.prawduct/.bug-inbox`) at your prawduct checkout's
`incoming-bugs/` directory.
