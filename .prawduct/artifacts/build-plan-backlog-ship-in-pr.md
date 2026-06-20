---
artifact: build-plan
version: 2
scope: backlog-ship-in-pr
depends_on: []
last_validated: 2026-06-20
---

# Build Plan — Archive a closed backlog item in the closing PR

**Problem.** Marking a backlog item `status=shipped` was framed as a *post-merge
reconciliation* step, so closing an item required a separate bookkeeping
commit/PR after the feature merged — redundant review/PR churn. The D4 rule
("never *infer* status from a view — the builder makes the explicit call")
governs *how* the call is made, not *when*; nothing required waiting until after
the merge.

**Success.** The guidance's primary path is "archive the item on the branch that
closes it, so the archive rides in the feature's own PR and is atomic with the
merge." Reconcile/janitor becomes the explicit fallback for items that slipped
through. Backlog `shipped` (work merged to the integration base) is disambiguated
from a change-log entry's `status=shipped` (released to consumers at the
`develop→main` release) — the latter is untouched.

**Out of scope.** The change-log `merged→shipped` two-stage and the
`develop→main` release flow (those legitimately batch at release and cost no
extra reviewed PR); any code/hook change; `methodology/building.md` (its
chunk-close step already closes affected items on-branch).

## Requirements Confidence

**Level:** High — a small, user-requested guidance clarification with no code
surface; the failure mode it prevents (backlog drift) is strictly reduced by
making the archive atomic with the merge.

## Status

- [x] Chunk 01: On-branch archive guidance (backlog SKILL + Critic review-cycle)

Context: single docs work cycle, 2026-06-20. `views_enabled: true` — the checkbox
flips at release via the `scope=backlog-ship-in-pr` change-log tag.

## Chunks

### Chunk 01: On-branch archive guidance

- `skills/backlog/SKILL.md`: add a "When to mark shipped — in the closing PR, not
  after it" rule (archive on the feature branch, atomic with merge, D4-compliant,
  anti-drift) plus the backlog-vs-change-log `shipped` disambiguation; demote
  "Reconcile shipped work" to the explicit fallback.
- `skills/critic/review-cycle.md`: the Backlog-Reconciliation NOTE nudges
  archiving *now, on this branch* (`closed-by=<scope>`) rather than a separate
  after-merge edit.
- **Type:** doc-only (skill prose is behavioral, so Critic review still applies).
- **Done when:**
  1. The two skill files carry the guidance; `tests/test_v5_methodology.py` and
     `tests/test_backlog_parser.py` stay green (no content assertion broken).
  2. Reviewed in the branch's single cumulative Critic (this scope ships in one
     PR alongside `upstream-bug-reporting`).
  3. Committed and chunk marked `[x]` in Status.
