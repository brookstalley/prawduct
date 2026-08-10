---
artifact: build-plan
version: 2
scope: critic-persistence-redesign
depends_on: [critic-persistence-redesign.md]
last_validated: 2026-07-09
lifecycle: completed
archived: 2026-08-10
released_in: v2.3.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Root cause verified (v2.1.198 background-by-default; SubagentStop exists; fork-dispatched
children survive + write files — all empirically or doc-confirmed this session — see
`critic-persistence-redesign.md`). The findings/ledger schema is unchanged, so downstream gates are
untouched by construction. The one unknown (fork-dispatched subagent survival) was resolved by test.

**Open assumptions / unknowns:**
- [ASSUMPTION: `SubagentStop` fires for fork-dispatched `critic-reviewer` subagents in the installed
  Claude Code, with `cwd`/project context sufficient for the hook to locate `.prawduct/` | MED impact |
  validated empirically in Chunk 04 before relying on it as the primary trigger — the Stop backstop
  (Chunk 01) is the floor regardless]
- [ASSUMPTION: a plugin-shipped custom agent type (`critic-reviewer`) is recognized and its
  `agent_type` is passed to the SubagentStop matcher | MED impact | Chunk 03 validates; fallback is an
  unmatched (`""`) SubagentStop that no-ops unless a manifest is present]

## Status

- [x] Chunk 01: Session-end abandoned-review backstop — the guaranteed loud floor
- [x] Chunk 02: `critic-consolidate` + partial/manifest schema — the deterministic core
- [x] Chunk 03: `critic-reviewer` agent type + coordinator dispatch rewrite (partials, no resume)
- [x] Chunk 04: `SubagentStop` hook — event-driven consolidation trigger
- [x] Chunk 05: Evolve the backstop to consolidate-or-block; reconcile messages (cumulative-final)
Context: New branch `feature/critic-persistence-redesign` off `develop`. Fixes the v2.1.198
background-by-default breakage of the Critic coordinator (design: `critic-persistence-redesign.md`,
Option A). Chunk 01 is already BUILT + tested (moved here from gate-friction-batch, which ships its
own 4 chunks clean). Per-chunk reviews run `chunk` mode (single-pass — unaffected by the breakage);
the branch's `cumulative` review runs on the NEW machinery this branch builds (the fix validates
itself). Related: gate-friction-batch Chunk 03 (critic-end HEAD assertion) lands on develop
separately — rebase onto it before this branch's PR and reconcile the critic-end/consolidate overlap.

## Why one plan / one PR

One coherent architecture change (independent review that can't silently fail). Per-chunk `chunk`
reviews + one `cumulative` on the last chunk (Type: cumulative-final). Splitting would fragment a
single design across PRs and re-pay reviewer passes (P0 wall-clock).

## Scaffolding

### Build & Test Configuration
Existing repo. `python3 -m pytest -q`. Verify `lib/`/`bin/` via the **repo-local** `python3
bin/prawduct-hook`, never the PATH plugin-cache copy. The consolidate core (Chunk 02) is pure lib —
unit-test exhaustively with fake partials/manifest fixtures, no harness needed. Hook-firing (Chunk 04)
needs an empirical validation step (documented) since a Stop/SubagentStop fire is not unit-observable.

### Verification Strategy
Per chunk: affected test files in isolation + exercise the real command via repo-local
`bin/prawduct-hook`. Chunk 04 adds a live harness check (dispatch a `critic-reviewer`, confirm
`critic-consolidate` ran). The branch's own `cumulative` review is the end-to-end proof the rebuilt
coordinator persists.

## Build Chunks

### Chunk 01: Session-end abandoned-review backstop — the guaranteed loud floor

- **Description:** The out-of-fork signal that a coordinator review never persisted is the lingering
  `.critic-active` marker (`critic-begin` ran, `critic-end`/consolidate never did). `cmd_stop` blocks
  loudly on it instead of letting it silently deadlock `check-cumulative-critic` in a later session.
  This is the guaranteed floor beneath every other mechanism: even if the SubagentStop trigger and the
  main loop both no-op, a session cannot end having silently lost the review. (Interim message; Chunk
  05 evolves it to self-heal from partials once `critic-consolidate` exists.)
- **Depends on:** none
- **Deliverables (BUILT):**
  - `lib/critic_marker.py::marker_present` — non-mutating presence check (NOT `review_active`: the
    Stop hook must never sweep the marker it gates on).
  - `bin/prawduct-hook::cmd_stop` — abandoned-review blocker under the Critic-gate conditions +
    `not defer_active` (in-flight reviews defer via `background_tasks`, not false-block); suppress the
    generic findings-freshness blocker when it fires (one cause, one block).
  - `tests/test_stop_abandoned_critic.py` — 9 cases (blocks; suppresses generic; no-sweep; no-marker;
    no-plan; doc-only; waiver; deferral).
- **Acceptance criteria:** scratch fixture with active plan + changes + lingering marker → `cmd_stop`
  exits 2 naming the abandoned review; marker absent → generic gate unchanged; marker not swept. (MET.)
- **Critic mode:** chunk
- **Done when:** 1. tests green in isolation (DONE); 2. `/prawduct:critic` (chunk) run + findings
  resolved; 3. committed + chunk marked.

### Chunk 02: `critic-consolidate` + partial/manifest schema — the deterministic core

- **Description:** The heart of the fix: make persistence a pure function of on-disk state. Reviewers
  write partials; a deterministic, idempotent command merges them into the canonical record. No model
  in the write path.
- **Depends on:** none (schema-only; consumed by later chunks)
- **Deliverables:**
  - New `lib/critic_consolidate.py`: partial schema (`{role, goals, commit_reviewed, model,
    duration_seconds, findings:[{name, goal, severity, recommendation, files?}], summary}`) + manifest
    schema (`{mode, mode_chosen_by, roster, commit_reviewed, scope, chunk, model}`) with validators.
  - `prawduct-hook critic-consolidate` (thin `bin` wrapper): read manifest + roster partials from
    `.prawduct/.critic-partials/`; if every roster role present AND every partial's `commit_reviewed
    == manifest == current HEAD` → merge (union findings; dedup by (file, goal, name); keep highest
    severity) → write `.prawduct/.critic-findings.json` (verbose mode string) → `ledger-append
    --event review.critic` → assert HEAD-coverage (reuse the Chunk-03-style check) → clear marker →
    remove partials+manifest. No-op (exit 0, distinct note) when manifest absent or partials
    incomplete (name missing roles). Non-zero when HEAD moved since dispatch (stale → redo). Idempotent
    (a second call after success is a clean no-op).
  - Dispatch-table + usage entry in `bin/prawduct-hook`.
- **Tests:** new `tests/test_critic_consolidate.py` — real git + real `ledger-append`: complete
  partials at HEAD → findings written (merged/deduped, highest severity), ledger anchor present, marker
  cleared, partials removed, exit 0; missing one role → no-op, names the missing role, nothing written;
  HEAD moved → non-zero stale; malformed/absent partial → fail-closed (no partial-review persisted as
  complete); idempotent second call → clean no-op; findings schema validates against
  `gates.validate_critic_findings`.
- **Acceptance criteria:** in a scratch fixture, writing 3 valid partials + manifest then
  `bin/prawduct-hook critic-consolidate` produces a schema-valid `.critic-findings.json` covering HEAD
  + a `review.critic` ledger anchor + cleared marker; a missing partial blocks with the role named.
- **Critic mode:** chunk
- **Done when:** 1. tests green in isolation; 2. `/prawduct:critic` (chunk); 3. committed + marked.

### Chunk 03: `critic-reviewer` agent type + coordinator dispatch rewrite

- **Description:** Reviewers write their own partials; the coordinator stops expecting to resume.
- **Depends on:** Chunk 02 (partial/manifest schema)
- **Deliverables:**
  - Plugin agent definition `agents/critic-reviewer.md`: restricted tools (no test/build execution —
    makes CRT-3X9D structural), instructed to review its assigned goals and write ONLY its partial to
    `.prawduct/.critic-partials/<role>.json`. Register wherever the plugin declares agents.
  - `skills/critic/review-protocol.md` Coordinator Pattern + `skills/critic/SKILL.md` steps 6-8:
    coordinator resolves mode → `critic-begin` → writes the manifest → dispatches the 3 `critic-reviewer`
    subagents (correctness / design+sustainability-with-crosschecks) → STOPS (no inline consolidation;
    persistence is external and deterministic). Remove the "resume to consolidate then critic-end"
    expectation; point at `critic-consolidate`. `chunk`/`verify-resolutions` (single-pass) documented
    as unchanged.
  - Cascade: reconcile every prose reference to the old "coordinator resumes and writes" flow.
- **Tests:** `tests/test_critic_skill_structure.py` / `test_critic_skill_metadata.py` extensions —
  the agent definition exists with restricted tools; the coordinator prose declares the manifest+partial
  contract and no longer instructs inline consolidation; single-pass modes unchanged.
- **Acceptance criteria:** structure tests pin the agent def + the rewritten coordinator contract.
- **Critic mode:** chunk
- **Done when:** 1. tests green; 2. `/prawduct:critic` (chunk); 3. committed + marked.

### Chunk 04: `SubagentStop` hook — event-driven consolidation trigger

- **Description:** Fire `critic-consolidate` deterministically as each reviewer finishes.
- **Depends on:** Chunks 02, 03
- **Deliverables:**
  - `hooks/hooks.json`: register `SubagentStop` (matcher `critic-reviewer`) → `prawduct-hook
    subagent-stop` (or directly `critic-consolidate`).
  - `bin/prawduct-hook subagent-stop`: read the SubagentStop stdin (cwd/agent_type), resolve the
    project dir, run consolidation best-effort (never block the subagent — advisory exit 0; the Stop
    backstop is the enforcing gate). No-op outside a pending manifest.
  - **Live validation (documented):** dispatch a `critic-reviewer` in a scratch repo, confirm the
    SubagentStop hook ran `critic-consolidate` (a hook fire is not unit-observable — record the manual
    check in `.prawduct/operator-verification.md`).
- **Tests:** `tests/` for the `subagent-stop` command body (stdin parse, project-dir resolution,
  no-op-without-manifest, delegates to consolidate) — the command is unit-testable even though the
  hook wiring is validated live.
- **Acceptance criteria:** `bin/prawduct-hook subagent-stop` with a SubagentStop-shaped stdin runs
  consolidation when a complete manifest+partials exist and no-ops otherwise; the live check confirms
  the registered hook fires.
- **Critic mode:** chunk
- **Done when:** 1. tests green + live check recorded; 2. `/prawduct:critic` (chunk); 3. committed + marked.

### Chunk 05: Evolve the backstop to consolidate-or-block; reconcile messages

- **Description:** With `critic-consolidate` in place, the Chunk 01 floor self-heals instead of only
  blocking.
- **Depends on:** Chunks 02, 04
- **Deliverables:**
  - `bin/prawduct-hook::cmd_stop`: on a lingering marker + active plan + changes: manifest + complete
    partials but findings don't cover HEAD → run `critic-consolidate` (self-heal, no re-run); manifest
    present but partials incomplete → block naming the missing reviewer(s) (re-dispatch just those);
    marker but no manifest → block "a review started but never ran." Update the Chunk 01 message to the
    real flow. Keep the `defer_active` deferral and `critic` waiver.
  - Reconcile any remaining prose (SKILL step 8 parenthetical, review-protocol) to the final flow.
- **Tests:** extend `tests/test_stop_abandoned_critic.py` — complete-partials → self-heal (findings
  written, exit 0); incomplete-partials → block naming missing; marker-no-manifest → block.
- **Acceptance criteria:** scratch fixtures prove all three session-end branches.
- **Type:** cumulative-final
  <!-- Last chunk: its `cumulative` review runs on the rebuilt coordinator (the fix proving itself) and
       gates the PR. Commit first, run cumulative once, no separate final. If the rebuilt coordinator
       has a defect that blocks its own cumulative, that IS the signal to fix before merge. -->
- **Done when:** 1. tests green; 2. committed, then `/prawduct:critic cumulative` on the new machinery,
  findings resolved; 3. chunk marked.

## Governance Checkpoints

- After Chunk 02: the deterministic core is the load-bearing piece — verify the merge/dedup/HEAD-check
  truth table exhaustively before building dispatch on top.
- After Chunk 04: run the live SubagentStop validation before trusting it as the primary trigger.
- Chunk 05 cumulative: the branch's own end-to-end proof that the rebuilt coordinator persists.
