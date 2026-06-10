---
artifact: build-plan
version: 2
scope: do-next
depends_on: []
last_validated: 2026-06-10
---

# Build Plan — Do-next cluster (PR-gate freshness, pointer guard, learnings compaction)

**Problem.** The 2026-06-10 whole-framework audit flagged a do-next cluster of three backlog
items — two gate-soundness holes plus the dominant context-economy cost:

- **CRT-8W3F** — `check_cumulative_critic`'s ledger fallback (`lib/gates.py::_ledger_fallback_record`)
  accepts the newest kind-qualifying `review.critic` event with **no freshness check** — only
  commit-coverage. A days-old cumulative from prior work can satisfy the PR gate when only `.md`
  changed since.
- **STH-5P2W** — a SET `active_build_plan` pointer that resolves to no file silently falls back
  to the default plan path, disabling the Critic gate, plan-aware mode inference, and
  verify-chunk-refs with no signal. Happened live (review-fixes planning commit wrote the
  natural repo-relative form `.prawduct/artifacts/...`; gates were blind for one work cycle).
  The field is also undocumented in `templates/project-state.yaml`.
- **MET-6W3J** — `.prawduct/learnings.md` is ~80KB / 58 rules with 300–600-word entries,
  drifting from its own stated format (rule here, narrative in `learnings-detail.md`). Every
  `/prawduct:learnings` lookup and Critic learnings cross-check pays it, and nothing nudges it
  back down.

**Success.** (1) A ledger-fallback record older than the current session can no longer satisfy
the PR gate — the gate fails closed with its existing honest message. (2) A mis-set build-plan
pointer is impossible to miss: the repo-relative spelling resolves correctly, and a pointer to
a genuinely missing file warns loudly in the session briefing. The field is documented where a
product author looks. (3) `learnings.md` entries are back to When-X-do-Y-because-Z rules with
pointers into `learnings-detail.md` (no narrative deleted — moved), and the session briefing
nudges when the file exceeds the size threshold again.

**Out of scope.** (a) The bounded-age alternative for CRT-8W3F (session-start comparison chosen;
see assumptions). (b) STH-8M3V atomic writes, STH-4F7C gate dedup, STH-5R2Q arg validation —
adjacent stop-hook items, separately filed. (c) Any change to which rules learnings.md carries —
compaction reformats all 58, drops none. (d) MET-5C2H (holistic context audit) — research-stage,
informs nothing here.

## Requirements Confidence

**Level:** High

**Why:** All three items carry audit-confirmed fix-shapes with the defective sites identified by
file and line; two have observed live failures.

**Open assumptions / unknowns:**
- [ASSUMPTION: CRT-8W3F freshness = ledger event envelope `ts >= .prawduct/.session-start`
  content (string compare, both ISO-8601 UTC — the `tests_are_current` model); missing
  `.session-start`, missing/empty `ts` → record skipped (fail closed). The backlog's
  "bounded age" alternative is not built — same-session is stricter and simpler, and the
  fallback's purpose is rescuing a same-flow cumulative that a later chunk review overwrote |
  MED impact | user can override]
- [ASSUMPTION: repo-relative pointer acceptance = strip one leading `.prawduct/` prefix in both
  resolvers (lib/core.py + the parity-pinned hook mirror) before joining; warning fires only
  when the pointer is SET and the resolved file does not exist | LOW impact | user can correct]
- [ASSUMPTION: learnings size-nudge threshold = 40KB on-disk bytes, matching the existing
  project-state.yaml 40KB warning precedent; nudge lives in the session briefing next to the
  existing learnings rule-count line | LOW impact | user can override]

**What would raise confidence:** N/A.

## Status

<!-- views_enabled: checkboxes are derived from scope=do-next change-log entries by
     regen-views at release; do not hand-edit. -->

- [x] Chunk 01: CRT-8W3F — ledger-fallback freshness at the PR gate
- [x] Chunk 02: STH-5P2W — build-plan pointer: repo-relative acceptance + loud missing-file guard
- [x] Chunk 03: MET-6W3J — learnings.md compaction + size nudge
Context: ALL THREE CHUNKS BUILT 2026-06-10 — ch.01 59258bd, ch.02 a5305c0, ch.03 b5439e1
(+ doc follow-up commit). Cumulative Critic at b5439e1: 0 blocking / 1 warning (evidence
currency — resolved by re-recording at HEAD) / 3 notes (learnings pointer NOTE resolved by
switching to the same-heading convention, recorded in plan + change-log; backlog items
CRT-8W3F/STH-5P2W/MET-6W3J archived shipped). Side-captures: CRT-2N7V (explicit Critic-mode
arg not honored), CRT-6J4P (rule-1b chains across bundles). Checkboxes flip at release via
scope=do-next change-log tags. PR-ready (feature/do-next → develop) — PR not yet created.

## Scaffolding

Existing repo — no scaffold. Test runner: `python3 -m pytest tests/ -q` from the repo root.

### Verification Strategy

Beyond unit tests, exercise the gates as a product session would: (1) `prawduct-hook
check-cumulative-critic` against a fixture repo with a stale ledger record and confirm the
stderr names the honest failure; (2) `prawduct-hook briefing`-path functions against a fixture
with a dangling pointer and confirm the warning text; (3) after compaction, run
`/prawduct:learnings <topic>` shape-check by reading the compacted file and confirm rule
integrity (58 rules, each with a detail pointer).

## Build Chunks

### Chunk 01: CRT-8W3F — ledger-fallback freshness at the PR gate

`lib/gates.py::_ledger_fallback_record` scans `.governance-ledger.jsonl` newest-first and
returns the first kind-qualifying `review.critic` payload with no recency bound. Add a
freshness filter mirroring the `tests_are_current` session model:

- Read `.prawduct/.session-start` once before the scan. Fail closed: if the marker is missing
  or unreadable, the fallback returns `None` (the gate's existing honest wrong-mode /
  chain-missing-anchor message stands).
- Per event: require a non-empty string envelope `ts` with `ts >= session_start` (ISO-8601 UTC
  string compare, same idiom as `tests_are_current`). A stale or ts-less event is skipped with
  a one-line stderr note naming why (`ledger: skipping line N (predates session ...)`), matching
  the existing skip-note style. Since `ts` decreases going older, the first stale event means no
  fresher qualifying record exists — but plain filtering is correct and simpler; keep scanning
  semantics unchanged.
- Docstrings: `_ledger_fallback_record` and the `check_cumulative_critic` "Ledger fallback"
  paragraph state the freshness bound and the fail-closed rule.

- **Tests:** extend `tests/test_cumulative_gate.py` ledger-fallback coverage: fresh same-session
  record still passes; record with `ts` predating `.session-start` → gate exits 1 with the
  wrong-mode message (not the fallback); missing `.session-start` → fail closed; event missing
  `ts` → skipped; freshness note appears on stderr.
- **Acceptance criteria:** full suite passes; a stale-ledger fixture run of
  `check_cumulative_critic` exits 1 with the honest message.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed; tagged change-log entry (`chunks=01 | scope=do-next`, statusless on branch)

### Chunk 02: STH-5P2W — build-plan pointer: repo-relative acceptance + loud missing-file guard

- **Depends on:** none (independent of Chunk 01)

Three parts, per the groomed item:

- **Repo-relative acceptance** — in `lib/core.py::resolve_build_plan_path` AND the parity-pinned
  inline mirror `bin/prawduct-hook::_resolve_build_plan_path` (edit both in place — never move a
  parity-pinned mirror): strip one leading `.prawduct/` prefix from the pointer value before
  joining, so the natural repo-relative spelling resolves to the same file as the canonical
  `.prawduct/`-relative form.
- **Loud guard** — in `lib/briefing.py` (session briefing): when the pointer is SET but the
  resolved path is not a file, emit a prominent warning line naming the pointer value and the
  resolved path, and stating the consequence (Critic gate, mode inference, and chunk-ref checks
  fall back to the default plan path). No warning when the pointer is unset.
- **Documentation** — add `active_build_plan` to `templates/project-state.yaml` with a comment
  giving the schema: optional, `.prawduct/`-relative (repo-relative tolerated), names the
  in-progress scope-named plan; unset → `artifacts/build-plan.md`.

- **Tests:** `tests/test_build_plan_resolution.py`: repo-relative form resolves identically in
  both implementations (extend the parity tests); canonical form unchanged; briefing test for
  the dangling-pointer warning (fires when set+missing, silent when unset, silent when set+exists).
- **Acceptance criteria:** full suite passes, including the existing mirror-parity tests.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed; tagged change-log entry (`chunks=02 | scope=do-next`, statusless on branch)

### Chunk 03: MET-6W3J — learnings.md compaction + size nudge

- **Depends on:** none (kept last: largest diff, and its cumulative review closes the branch)
- **Type:** cumulative-final

Two parts, per the item's fix-shape:

- **Compaction** — for each of the 58 entries in `.prawduct/learnings.md`: keep the heading and
  a 1–3 sentence When-X-do-Y-because-Z rule (preserving the `[[...]]` cross-links and principle
  refs); move the narrative body (discovery story, line-level evidence, session context) to
  `.prawduct/learnings-detail.md` under the SAME heading — **moved, never deleted**. Navigation
  is by convention, stated once in the preamble: narrative lives in learnings-detail.md under
  the same heading. **(Revised at build: per-entry `Detail: § <heading>` pointers were the
  original design, but repeating 57 long headings cost ~8KB and pushed the file back over its
  own 40KB threshold — the one-line convention replaces them.)** Target: rules file well under
  the nudge threshold. Entry count must be exactly 58 before and after; spot-check that every
  compacted rule still states When/do/because.
- **Size nudge** — in `lib/briefing.py`, next to the existing learnings rule-count line: when
  `learnings.md` exceeds 40KB on disk, append a warning line advising compaction (rule here,
  narrative to `learnings-detail.md`), mirroring the CLAUDE.md size-check pattern (same
  best-effort exception discipline).

- **Tests:** briefing test for the size nudge (fires >40KB, silent under); no test asserts
  learnings *content* (it's project state, not framework code).
- **Acceptance criteria:** full suite passes; `learnings.md` under 40KB with 58 rule headings;
  `learnings-detail.md` carries the moved narratives.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed; tagged change-log entry (`chunks=03 | scope=do-next`, statusless on branch)
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD` (this chunk's review IS the
     cumulative — commit first, no separate `final`) and blocking findings resolved
  4. Backlog hygiene: update CRT-8W3F, STH-5P2W, MET-6W3J via `/prawduct:backlog`

## Early Feedback Milestone

**Milestone chunk:** 02
**What the user can do:** see the dangling-pointer warning in a session briefing and write the
pointer in either spelling; the PR gate already refuses stale ledger evidence after Chunk 01.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` passes; PR after Chunk 03's
one `/prawduct:critic cumulative` (its review AND the PR gate) passes — one cumulative run for
the branch (review wall clock is P0).

- After chunk 03: cumulative review (Type: cumulative-final), then `/prawduct:pr create`.
