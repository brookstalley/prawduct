---
artifact: design-note
scope: critic-persistence-redesign
status: built — all 5 chunks landed (see build-plan-critic-persistence-redesign.md)
created: 2026-07-09
depends_on: [build-plan-critic-persistence-redesign.md]
---

# Critic Persistence Redesign — Independent Review That Can't Silently Fail

## Problem (root cause, verified)

Claude Code **v2.1.198** (2026-07-01) flipped `Agent`/`Task` subagents to **background-by-default**.
The Critic's `final`/`cumulative` coordinator is a `context: fork` skill that dispatches 3 parallel
review subagents and **resumes inline** to run SKILL steps 7-8 (write `.critic-findings.json` →
`ledger-append` → `critic-end`). Under background-by-default the fork returns before resuming;
completions surface to the **main loop**, not the fork. None of steps 7-8 run:

- `.critic-findings.json` stays frozen at a prior commit,
- no `review.critic` ledger anchor lands (`check-cumulative-critic` → `chain-missing-anchor` deadlock),
- `critic-end` never clears `.critic-active`.

discodon hit this reproducibly (6 re-runs, all abandoned). Chunk 03's exit-time assertion lives
*inside* `critic-end`, so it cannot fire on this "never-reaches-critic-end" variant. Re-running does
not help — the coordinator path is **structurally broken** under v2.1.198+, not flaky.

## Goals (what the design must preserve)

1. **Independence** — reviewers have not seen the builder's reasoning; the builder never *authors*
   findings content (a future auditor can't distinguish honest transcription from fabrication).
2. **Deterministic persistence** — the two writes (findings + ledger anchor) land for HEAD, every
   time, with **no reliance on any model resuming** a context.
3. **Wall-clock (P0)** — parallel reviewers; minimize review run-count; cheap recovery.
4. **Unchanged downstream** — `.critic-findings.json` + ledger schema stay identical, so every
   consumer (`check-cumulative-critic`, Stop gate, PR reviewer) is untouched.
5. **Harness-volatility resilience** — do not depend on background/foreground defaults, fork-resume,
   or main-loop follow-through — the exact behaviors that just broke.

## Core principle

**Separate the model-judgment part (the review) from the deterministic part (consolidation +
persistence).** The review must be independent model agents; persistence must be a pure function of
on-disk state that a hook runs — never something a model has to "come back and finish."

## Recommended design (Option A) — SubagentStop-driven consolidation with per-reviewer partials

1. **`critic-reviewer` agent type** (plugin-shipped `agents/critic-reviewer.md`). Restricted tools
   (no test execution — makes the CRT-3X9D "no executables" constraint *structural*, not prose).
   Its sole deliverable: review its assigned goals and **write its own structured findings partial**
   to `.prawduct/.critic-partials/<role>.json`. Each reviewer writes its own words — no model
   re-transcribes or merges them (this is *stronger* independence than today).

2. **Dispatch (coordinator setup).** `/prawduct:critic` (final/cumulative) resolves mode, runs
   `critic-begin`, writes a **manifest** `.prawduct/.critic-partials/manifest.json`
   (`mode`, `mode_chosen_by`, `roster`, `commit_reviewed = HEAD@dispatch`, `scope`, `chunk`,
   model tier), then dispatches the 3 `critic-reviewer` subagents (correctness / design+sustainability
   — the design/sustainability reviewer also owns the Learnings + Backlog cross-checks and emits them
   as NOTEs in its partial, keeping consolidation model-free).

3. **`prawduct-hook critic-consolidate`** (deterministic, idempotent). Reads manifest + all roster
   partials. If every roster role is present AND every partial's `commit_reviewed == manifest HEAD ==
   current HEAD` → merge (union findings, dedup by file+goal+name, keep highest severity) → write
   `.critic-findings.json` → `ledger-append` → assert HEAD-coverage (subsumes Chunk 03's invariant) →
   clear the marker → remove the partials. No-op when the manifest is absent or partials are
   incomplete; loud (non-zero) when HEAD moved since dispatch (stale → redo). Safe to call any number
   of times, from any context.

4. **`SubagentStop` hook** (matcher: `critic-reviewer`). Runs `critic-consolidate` each time a
   reviewer finishes. The first N-1 firings no-op (incomplete); the last one consolidates and
   persists. **Event-driven, deterministic, zero reliance on fork-resume or main-loop follow-through.**

5. **Stop-hook backstop (Part A, evolved).** At session end, with an active plan + code changes:
   - manifest + complete partials but findings don't cover HEAD → **run consolidate (self-heal)**;
   - manifest present but partials incomplete → **block**, naming the missing reviewer(s)
     (re-dispatch just those — cheaper than a full re-run);
   - marker lingering with no manifest → **block** "a review started but never ran" (the Part A msg).
   This is the guaranteed floor: even if the SubagentStop trigger and the main loop both no-op, the
   session cannot end having silently lost the review — and it finishes from partials already on
   disk, so no completed opus work is thrown away.

6. **`chunk` / `verify-resolutions` modes: unchanged.** They are single-pass inline (no subagent
   dispatch), already reach `critic-end` reliably. The break is specific to subagent-dispatching
   modes; scope the change there.

**Why this meets the goals:** independence is preserved/strengthened (reviewers author their own
partials; a hook merges — no model in the write path); persistence is a deterministic hook fired by a
harness lifecycle event, not a model resume; wall-clock is preserved (parallel reviewers; single-role
re-dispatch on partial loss); downstream schema is identical; and nothing depends on the volatile
background/foreground/fork-resume behaviors.

## The one unknown → build-step-0 verification — RESOLVED (2026-07-09)

Docs did not state whether **fork-dispatched** background subagents survive the dispatcher ending and
still write files. Tested empirically with a faithful proxy (a subagent dispatched a background
sub-subagent that wrote a sentinel, then the parent immediately ended its turn):

- **Result: children SURVIVE and complete.** The sentinel was written (`ALIVE 03:08:38`); the
  background child ran to completion after the parent had emitted its final turn.
- **Bonus mechanism finding:** the harness **defers the parent's completion notification until its
  background children finish** (the parent's ~18s duration matched the child's work; the harness note:
  fires "when this agent stops with no live background children of its own"). So the fork's turn is
  held open until the reviewers finish — but the harness does **not re-invoke the fork** to run
  post-dispatch code. That is precisely the failure: reviewers run, but nothing resumes to consolidate.

**Decision:** keep `context: fork`; **the fork dispatches the reviewers.** They survive and write
partials; `SubagentStop` (a shell hook, not a model turn) fires `critic-consolidate` as each finishes;
and because the fork's completion is deferred until reviewers finish, findings are already persisted by
the time control returns to the main loop. No main-context dispatch needed. Consolidation is
model-free either way.

## Alternatives considered

| Option | Robustness | Surface | Independence | Verdict |
|---|---|---|---|---|
| **A. SubagentStop + partials** (above) | High — no volatile deps | Medium (new agent type, hook, consolidate cmd, partials) | Strengthened | **Recommended** |
| B. Main-context synchronous dispatch (`run_in_background:false`) | Low — depends on foreground semantics that just broke; may be stripped in fork mode | Small (prompt-only) | Weaker (model authors merged findings) | Cheapest, least durable |
| C. Inline sequential review (no subagents) | High — no async at all | Small | Same as today | Loses parallelism (P0 wall-clock) + model diversity |
| D. Workflow tool (native join) | High | Large (new dependency) | Same | **Rejected** — requires explicit user opt-in; wrong for an always-on gate |

Part A of Chunk 05 (the Stop-hook safety net) is **already built and verified**; in this design it
becomes the guaranteed backstop trigger (evolved from "block" to "consolidate-or-block").
