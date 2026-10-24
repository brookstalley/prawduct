---
artifact: build-plan
version: 2
scope: refusal-reasons
branch: feature/1044-refusal-reasons
partition: serial — one chunk; the sink, its first producer and its reader share one shape
last_validated: 2026-10-24
---

## Goals

**Response taken:** Proceed, citing #1044 — the owner confirmed it 2026-10-24 and asked that the design generalize beyond the Stop hook.

**Product:** Make "does this control earn its cost?" answerable on evidence. #1044 asks it of `clear-verdict` and `clear-reason`, which caused 5 of 8 Stop blocks on plugin 3.7 (`prawduct-hook stats`, 2026-10-24). A quarter-long data clock starts only when this lands.

**Architecture:** The general pattern already exists. The owner's 2026-09-30 ruling put every control firing through one sink, `evidence.append_guard_refusal`, with families told apart by a `guard` prefix (#563 widens its producers). What no producer records is *why* it fired. So the generalization is a class-level addition to the sink, not a Stop-hook telemetry system:

- `reason`: a short slug from a closed set the control declares — never turn text.
- `observed`: a few machine observations taken at firing time (booleans or `None` for "could not tell").
- The catch-vs-slip **verdict is derived in `stats` at read time** from reason + observed, never stored, so the definition can be revised without losing data (the same move #951 makes).

Inferred, owner may override: hooks are the wrong unit (SessionStart never refuses; one Stop hook runs many gates; most controls are not hooks), so the unit is the control.

**Verdict definitions (inferred, revisable because derived):**
- `clear-reason`: the harm is a clear losing what only the turn held. `notes_present` true → *slip* (a record existed; the reason misnamed it); false → *catch*.
- `clear-verdict`: the harm is a reader told to hold a session for nothing. `work_live` true (harness background tasks or a live Critic marker) → *slip* (the hold was right; only the disposition label was wrong); false → *catch*. An unreaped delegate is not observable, so `work_live` can under-read; that biases toward *catch*, which is the direction that keeps a gate.

**Constraints:** Recording stays advice: it never changes an exit code, and a failed append prints a `NOTE:`. No turn text leaves the hook. `contribution.py` reads named `stats.aggregate` keys, so added keys must not move any it reads.

**Tradeoffs accepted:** Only the two clear gates get reasons now; other gates record `reason` absent, reported as `unspecified`. #908 (reflection gate) adopts the same field when it is built.

**Decisions made mid-build:**
- 2026-10-24, the owner: telemetry is not only about blocking. Session start should record which advisories it offered, among other things. So `reason`/`observed` are specified for *any* control firing, blocking or not, and nothing in the sink or in `stats`' reason counting is refusal-specific. Non-blocking firings close the loop through an **outcome** (an offered advisory later resolved or dismissed), not a catch/slip verdict. Advisory exposure (one fact per advisory per session it is offered in, deduped on advisory id + session) is recorded on #563 as its probe producer's design, not built here: session start is a hot path and earns its own review. *(Alignment-pass miss: the first Goals line read #1044 as Stop-only.)*

**Level:** High — the issue's acceptance is explicit; the shape follows an existing owner ruling.

## Status

- [x] Chunk 01: Reason + observations on control firings; clear gates as first producer; `stats` reports by reason and derived verdict

Context: Single chunk. Done when: tests pass (`tests/test_stop_block_facts.py`, `tests/test_stats.py`, `tests/test_stop_verdict_defer.py`), `plugin/docs/governance-telemetry.md` documents the fields and verdict rules, a change fragment exists, and `/prawduct:critic` passes.

## Chunk 01: Reason + observations on control firings

**Delivers:**
1. `evidence.append_guard_refusal(..., reason=None, observed=None)`: validated (slug reason; flat dict of bool/None/int/slug observations) and written into the body as `reason` / `observed`. An invalid value is refused like an invalid guard name.
2. `evidence.append_stop_block(project_dir, gates, details=None)`: `details` maps gate id → `{reason, observed}`.
3. `standing_block`: self-citation patterns carry a kind (`in-this-message`, `message-holds`, `above-below`); `self_citation_match` returns phrase + kind; `self_citation` is unchanged. `gates.turn_self_citation` exposes it.
4. `prawduct-hook` Stop: `_GateMessage` carries `reason` / `observed`; `clear-verdict` records `handed-over-your-turn` | `handed-over-complete`; `clear-reason` records the citation kind; both observe `work_live` and `notes_present`. `_record_stop_block` passes them through.
5. `stats`: `stop_blocks.by_gate_reason` and `stop_blocks.verdicts` (catch / slip / unclassified per gate), `guard_refusals.by_guard_reason`; human report prints the per-gate reason line; `REPORT_SCHEMA_VERSION` 1 → 2.
6. `plugin/docs/governance-telemetry.md`: the fields, the closed reason sets, the verdict rules and that they are derived.

**Acceptance:**
- A blocked clear-verdict Stop's fact carries its reason and observations; a clear-reason Stop's carries the citation kind.
- No fact body contains the turn's text (the matched phrase is not recorded).
- `stats` reports refusals by reason per gate and a derived verdict; a gate with no reason reports `unspecified`.
- Recording failure still keeps the block and says so.
