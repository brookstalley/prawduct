# Critic: Coordinator Pattern

Read this only when the manifest's roster is `correctness`/`design`/`sustainability`. You are the
coordinator: you dispatch the three reviewers and stop. The reviewers never read this file; their
contract is `agents/critic-reviewer.md`.

## Coordinator Pattern

Persistence is **decoupled from the review**: reviewers write partials, `critic-consolidate` merges them against the code-written manifest, and no model authors a file the data plane trusts.

1. **Assess** (coordinator): read project state and the manifest (review id, `commit_reviewed`, `files_changed`, and `signals` — the code-rendered `Stage · Judgeable files · Type` line; you compose none), run git diff. The manifest's `tier` is telemetry only and selects no model.

2. **Dispatch** three **`critic-reviewer`** subagents (Agent tool, `subagent_type: critic-reviewer`) — **all three Agent calls in ONE message, concurrently.** With **no `model:` override** — they inherit the session model (`critic-reviewer` declares `model: inherit`). Each reviews ONLY its goals and writes ONLY the two files the manifest's `rendezvous` names for its role — never `.critic-findings.json`, `critic-consolidate`, or `critic-end`. Prompt template — substitute `<ROLE>`/`<GOALS>`/`<SHA>`/`<ID>`/`<STARTED>`/`<PARTIAL>`/`<SIGNALS>` from the manifest (`commit_reviewed`, `id`, `rendezvous.<ROLE>`, `signals` verbatim), `[dir]` from its `worktree`, and `<MANIFEST>` as `[dir]` + `.prawduct/.critic-partials/manifest.json`:

   > "Critic reviewer (`<ROLE>`). FIRST: write your liveness marker `<STARTED>` (content: `<ROLE>`). Then read `[critic path]` for goal definitions. Review ONLY <GOALS>. Project (absolute): `[dir]` — anchor every path and every `git -C` there, never your cwd. Read `files_reviewed` (subject, findings-eligible) and `files_oracle` (read, do not rate) from `<MANIFEST>`. Signals: <SIGNALS>. Commit under review: `<SHA>` — record it verbatim as `commit_reviewed`, and confirm `git -C [dir] rev-parse HEAD` equals it before reading anything. Review id: `<ID>` — record it verbatim as `dispatch_id`. NO tests/builds. Write ONLY your partial to `<PARTIAL>`; nothing else."

   - **`[dir]` is the manifest's `worktree`** — already absolute, and the tree `critic-begin` measured. A subagent does not inherit your cwd, so a relative path resolves into the primary checkout: a different tree at a different commit, which reviews clean.
   - **Never paste the file lists into the prompt**: you write the prompts one after another, so a list delays the last reviewer's start by its length.
   - **correctness reviewer** (role `correctness`) — Goals 1, 2, 3.
   - **design reviewer** (role `design`) — Goals 4, 7 + the Framework-Specific Checks when they apply.
   - **sustainability reviewer** (role `sustainability`) — Goals 5, 6 + the Learnings Cross-Check and Backlog Reconciliation (as NOTE findings in its partial) + the Records Pass over the oracle files.

3. **Stop — do not resume to aggregate.** The `SubagentStop` hook runs `critic-consolidate` as each reviewer finishes (no-op until all roles report, then merges once). You do NOT write findings, append the ledger, or run `critic-end` — `critic-consolidate` does all three and clears the marker.
