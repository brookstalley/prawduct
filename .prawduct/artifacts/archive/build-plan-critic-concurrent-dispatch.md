<!-- Build Plan: critic-concurrent-dispatch (target: patch — v3.2.6)

     WRITTEN AFTER THE WORK, and that is the honest record rather than a
     formality. The fix was taken under owner-declared urgency ("get with great
     urgency but ALSO triple-check the approach and correctness") against a
     defect actively destroying completed reviews in a consuming repo, and I
     went straight to code. `views_enabled: true` means a statusless change-log
     scope must resolve to a plan file, so the omission surfaced at
     `regen-views` — a gate catching a real process departure, working exactly
     as designed. Recording it here beats attributing the work to
     `build-plan-critic-session-guard.md`, which is a DIFFERENT defect's plan,
     shipped in v2.0.14, and whose scope would have been a false record.

     Parent requirement: brookstalley/prawduct#602 (near-duplicate of #171),
     and `incoming-bugs/concurrent-critic-dispatch-destroys-a-completed-
     coordinator-review.md` with the prawduct-repo triage notes appended.
-->
---
artifact: build-plan
# Namespaces this plan's chunk numbering and matches the change-log entry's
# `scope=`, which is what `regen-views` resolves to find this file.
scope: critic-concurrent-dispatch
version: 2
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews — enforced at the mutation site, not by tool-restriction alone → conforms, and this plan IS that norm reaching its second mutation site: `clear` consulted the critic-active marker and `critic-begin`, the more destructive operation, never did"
      - "authority fails closed; advice fails soft → conforms — the guard refuses a destructive dispatch (authority) while every refusal names a working remedy (advice)"
      - "prawduct guides and reviews; it never implements → inapplicable because this is prawduct's own runtime, not a governed product's code"
  - artifact: data-model
    dispositions:
      - "facts are immutable and append-only; a state change is a new fact → conforms — nothing here edits or deletes a fact; the defect was that a fact could be attributed to a review that never read the files, which this prevents at dispatch"
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.6
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** The defect was observed live three times (2026-07-29, 07-30, 08-05) with
partials, manifests and ledger state preserved from the last incident; the mechanism was
verified in code before any fix (`remove_partials` has exactly two call sites; a partial
is bound to `commit_reviewed` and nothing else); and #171 carried a prior design for the
same fix, read before writing.

**Open assumptions / unknowns:**
- `[ASSUMPTION: refusing is correct where auto-consolidating a complete roster would also have been possible | MED impact | auto-consolidation from the dispatch path was rejected as too clever — it would make `critic-begin` do something other than its name; the Stop hook already self-heals]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 1: The in-flight guard — `critic-begin` refuses rather than displacing a live review
- [x] Chunk 2: The guard's own escape — `critic-discard`, and a refusal that names a remedy reaching the state
Context: Built on `fix/critic-concurrent-dispatch` off `develop` on 2026-08-05, commits `8bcdf14` and `409ae3e`. Both chunks complete; suite 3751 green. Chunk 2 exists **because the cumulative review of Chunk 1 found that Chunk 1 created a state nothing could clear** — that finding is the reason this is two chunks and not one. **Part 2 of the underlying defect is deliberately NOT in this plan**: a partial carries no review identity (`partial_path` is keyed by role alone; `commit_reviewed` is the only binding), which is what would make the class impossible rather than unreachable. It stays open on #602/#171, and whoever builds it must know the documented recovery works *because* of that defect — a `critic-recover` would have to re-stamp, not copy. The state-machine reachability test agreed with the owner is filed on #602 and sequenced **after** part 2, since the `review_id` binding changes the states it would pin.

## Build Chunks

### Chunk 1: The in-flight guard

- **Description:** `begin_review` refuses when a review is still live, instead of archiving its partials and overwriting its manifest. Placed in `begin_review` rather than the CLI wrapper, per #171 and `architecture.md`'s enforced-at-the-mutation-site norm.
- **Depends on:** none
- **Artifacts consumed:** `incoming-bugs/concurrent-critic-dispatch-destroys-a-completed-coordinator-review.md`; #602; #171.
- **Deliverables:**
  1. `plugin/lib/critic_consolidate.py` — the guard (refuse on a live marker **or** a complete roster at any age) plus `active_dispatch_refusal`.
  2. `tests/test_critic_session_guard.py` — `TestConcurrentDispatchGuard`.
  3. `tests/test_critic_consolidate.py` — two existing tests' setup routed through `critic-end` between dispatches; every assertion unchanged.
- **Tests:** as above; four were watched failing with the guard disabled.
- **Acceptance criteria:** a dispatch over a live review refuses and leaves manifest + partials intact; an orphaned leftover with no marker still sweeps; suite green.
- **Critic mode:** cumulative
- **Type:** code
- **Done when:** built, reviewed, blocking findings resolved, committed.

### Chunk 2: The guard's own escape

- **Description:** The cumulative review's BLOCKING finding. Consolidation fail-closes *without* removing partials so a fix can retry, and `critic-end` clears only the marker — so a failed consolidate stranded a complete roster that nothing expired and no command cleared. A guard that cannot be escaped is its own outage.
- **Depends on:** Chunk 1
- **Artifacts consumed:** `plugin/lib/critic_marker.py` (the three-corrections resilience design this violated).
- **Deliverables:**
  1. `plugin/bin/prawduct-hook` — new `critic-discard` (archive-first; deliberately NOT folded into `critic-end`, which is what an agent reaches for whenever a review looks dead).
  2. `plugin/lib/critic_marker.py` — `review_active(sweep=False)`, so the dispatch path stops deleting the marker the Stop hook's recovery advice is gated on.
  3. `plugin/lib/critic_consolidate.py` — the refusal branches on whether a marker is live; no false TTL promise where nothing expires.
  4. `tests/test_critic_session_guard.py` — the stranded-roster, discard-unblocks, and no-sweep tests; two overclaiming docstrings rescoped to what their fixtures build.
- **Tests:** as above; both new behaviours watched failing under mutation.
- **Acceptance criteria:** every reachable refusing state has at least one documented command that clears it; suite green.
- **Critic mode:** verify-resolutions
- **Type:** code
- **Done when:** built, reviewed, blocking findings resolved, committed.

## Governance Checkpoints

**Commit & PR cadence:** one commit per chunk; the Chunk 1 `cumulative` was the bundle review and the Chunk 2 `verify-resolutions` re-covers the fix delta. Target: patch release v3.2.6.
