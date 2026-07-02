<!-- Build Plan — gate-exemption-boundary (CRT-5D8Q)
     For HOW to build (governance, test discipline, Critic review), read
     /prawduct:building before starting.
-->
---
artifact: build-plan
version: 2
scope: gate-exemption-boundary
depends_on: []
last_validated: 2026-07-02
---

# Build Plan — gate-exemption-boundary (CRT-5D8Q)

## Requirements Confidence

**Level:** High

**Why:** The defect was observed live this session (feature/changelog-fail-loud), both
helpers were read at HEAD before planning, and the fix-shape is a one-predicate
alignment with an already-declared boundary (the chain gap-check's `.md` +
`_is_metadata_path` exemption, gate-soundness ch.5).

**The problem (observed, not inferred):** `_record_covers_head` (`lib/gates.py`, the
CRT-7M2D coverage rule shared by the cumulative and chain paths of
`check-cumulative-critic`) exempts **only `.md`** files when judging whether a record
still covers HEAD. But `_compute_verify_resolutions_scope` filters **all**
`_is_metadata_path` files (`.prawduct/`, `.claude/settings.json`) from the verify
delta, and the chain gap-check in `_evaluate_pr_gate_record` exempts **both** `.md`
and metadata. Consequence: a routine post-cumulative metadata-only commit (e.g.
repointing `active_build_plan` in `project-state.yaml`) marks the cumulative `stale`
and demands a verify-resolutions chain record — but the verify scope computes an
empty delta, returns `no-actionable-findings`, and the SKILL's literal demotion to
`final` produces a non-gate-qualifying record. When the ledger-fallback window has
lapsed (cumulative ledger event predates session start), the gate **deadlocks**: a
clean branch cannot satisfy its own PR gate. Observed 2026-07-02; the Critic
hand-anchored a chain record to route around it.

**Success:** a metadata-only delta after a cumulative (or chain) record keeps the
record HEAD-covering — the gate stays `satisfied` with no extra review — while any
non-`.md`, non-metadata delta still reads `stale` (fail-closed preserved). The exact
live deadlock scenario has a regression test.

**Out of scope:** `_compute_verify_resolutions_scope` (its metadata filter is correct
and load-bearing — it exists to prevent false demotion); CRT-8H3R (branch-switch
chain unsoundness — separate item); `check-pr-doc-only` (different gate answering a
different question — whether to skip review entirely, bounded by
governance-protected paths, not by `_is_metadata_path`); any change to
`_METADATA_PREFIXES` itself.

**Open assumptions / unknowns:**
- [ASSUMPTION: alignment direction is "coverage exempts metadata" (loosen
  `_record_covers_head`), not "verify scope counts metadata" (tighten the scope
  helper) | MED impact | user can override] Rationale: the chain gap-check already
  declares `.md`+metadata as the boundary of what a code review must vouch for
  (gate-soundness ch.5 declared decision); the scope helper's filter was built
  deliberately to stop metadata churn from demoting legitimate verify flows; and
  review wall-clock is P0 — the other direction would force review passes over
  `.prawduct/` state churn that reviews can't add value on.

**What would raise confidence:** N/A.

## Status

- [ ] Chunk 01: Align `_record_covers_head` to the `.md` + metadata exemption boundary
Context: Plan authored 2026-07-02 on feature/gate-exemption-boundary (off develop
@ b3b641f, post PR #115 merge). Not started.

## Scaffolding

Existing repo — no scaffold. Tests: `pytest tests/test_cumulative_gate.py` while
iterating; full suite (`python -m pytest -q`, 1529 at branch point) before commit.
Verify hook behavior via repo-local `./bin/prawduct-hook` / `python3 bin/prawduct-hook`,
never the PATH-installed plugin copy (learnings: installed v2.2.3 silently lacks new
behavior).

### Verification Strategy

Beyond tests, reproduce the live deadlock against a scratch repo (self-hosting
caution — this edits the PR gate this very branch must later pass):
1. Scratch repo: cumulative record at commit X, then a metadata-only commit
   (`.prawduct/project-state.yaml`) → `check-cumulative-critic` exits 0 (today: exit 1
   `stale`).
2. Same setup plus a `lib/*.py` edit in the delta → still exits 1 `stale` (the
   exemption must not over-exempt; "give every skip-gate a regression test that a
   non-eligible case still BLOCKS").
3. This repo at HEAD: `./bin/prawduct-hook check-cumulative-critic` behaves
   identically to the installed copy on a clean tree (no behavior drift on the
   satisfied path).

## Build Chunks

### Chunk 01: Align `_record_covers_head` to the `.md` + metadata exemption boundary

- **Description:** Make the CRT-7M2D coverage rule exempt the same file classes the
  chain gap-check already exempts, so all three gate predicates agree on what a code
  review must vouch for. Scope changes by pattern: *the coverage predicate and every
  prose statement of it*, not line addresses.
- **Depends on:** none
- **Artifacts consumed:** this plan; `.prawduct/backlog.md` (CRT-5D8Q entry)
- **Deliverables:**
  - `lib/gates.py::_record_covers_head` — the non-doc filter becomes
    "not `.md` AND not `gitstate._is_metadata_path(f)`"; docstring updated to state
    the full exemption (docs OR framework/session metadata) and why it mirrors the
    chain gap-check (gate-soundness ch.5 symmetry).
  - `lib/gates.py::check_cumulative_critic` docstring + the `stale` stderr messages
    in `_evaluate_pr_gate_record` — "(Doc-only — all .md — changes ... never require
    a re-run)" wording updated to name both exempt classes.
  - `tests/test_cumulative_gate.py` — new: metadata-only delta since review →
    covered/exit 0 (the CRT-5D8Q deadlock regression, both cumulative and chain
    record paths); metadata + code delta → still stale/exit 1; existing
    `.md`-exemption tests untouched.
  - Prose surfaces stating the old boundary (Living Documentation cascade):
    `skills/pr/SKILL.md` Step 2 ("or only docs changed since — CRT-7M2D"),
    `skills/critic/review-cycle.md` PR-gate paragraph, `docs/release-process.md`
    CRT-7M2D coverage-gate sentence — each updated to "docs (`.md`) or `.prawduct/`
    framework metadata".
- **Tests:** unit tests on `_record_covers_head` via the gate entry point (existing
  file's pattern: tmp git repo + findings fixture). Required cases: metadata-only
  delta covered; mixed metadata+code delta stale; `.claude/settings.json` delta
  covered (second `_METADATA_PREFIXES` entry — exercise the predicate, not one
  prefix); chain-record coverage path gets the same metadata-only case.
- **Acceptance criteria:**
  - `pytest tests/test_cumulative_gate.py` passes with the new cases; full suite green.
  - Live checks 1–3 in Verification Strategy hold.
  - `grep -n "only docs\|doc-only (\`.md\`)" skills/pr/SKILL.md skills/critic/review-cycle.md docs/release-process.md`
    shows no stale statement of the old boundary.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run against merge-base...HEAD and
     blocking findings resolved (this chunk's review IS the cumulative — no separate
     `final`)
  3. Chunk marked `[x]` in Status (flips at release via regen-views; entry statusless
     on branch)
  4. Backlog hygiene: CRT-5D8Q updated via `/prawduct:backlog` (shipped → Archive at
     close-out); change-log entry added
     (`type=fix | chunks=01 | scope=gate-exemption-boundary`, statusless on branch)

## Early Feedback Milestone

**Milestone chunk:** 01 (single-chunk plan). **What the user can do:** a
metadata-only post-review commit no longer stales the PR gate — observable via
`prawduct-hook check-cumulative-critic` on the next real branch.

## Governance Checkpoints

**Commit & PR cadence:** commit the chunk after tests pass; the chunk's one
`/prawduct:critic cumulative` is both its review and the `/prawduct:pr create` gate.
PR to develop via `/prawduct:pr` when the user asks. Risk tier will classify
`escalate` (touches `lib/gates.py` gate logic + `skills/` prose) — expect the depth
reviewer.

- After chunk 01: cumulative Critic (the review), then PR reviewer at create.
