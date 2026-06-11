<!-- Build Plan — gate-hardening (STH-4F7C + STH-8M3V + CRT-2N7V)
     Three independent small fixes from the 2026-06-09/10 framework audits,
     batched as one bundle on feature/gate-hardening. For HOW to build
     (governance, test discipline, Critic review), read /prawduct:building.
-->
---
artifact: build-plan
version: 2
scope: gate-hardening
depends_on:
  - artifact: project-preferences
last_validated: 2026-06-10
---

## Requirements Confidence

**Level:** High

**Why:** All three items are audited backlog entries at `stage: ready` with the exact code sites enumerated and re-confirmed against HEAD during planning (2026-06-10); the requirement of each is statable in one sentence.

**Open assumptions / unknowns:**
- [ASSUMPTION: the three items ship as one PR bundle to `develop` on `feature/gate-hardening` | MED impact | user can override]
- [ASSUMPTION: `atomic_write_text` lives in `lib/core.py` (modeled on the existing tmp+`os.replace` writer for `.test-evidence.json` in `bin/prawduct-hook` ~L1188); `bin/prawduct-hook` call sites use the established lazy `_core()`-style import | LOW impact | user can override]
- [ASSUMPTION: `.gates-waived` has no code write site (pre-plan grep found none — it appears to be agent-written via the Write tool). Chunk 02 verifies; if confirmed, it is documented as out of the helper's reach rather than converted | LOW impact | user can defer]
- [ASSUMPTION: chunk 03's fix lands wherever the root cause is (skill prose, hook helper, or a documented harness limitation) — its exact shape is an implementation unknown, not a requirements unknown; the requirement (explicit mode arg wins and records `mode_chosen_by: "explicit-args"`, or the documented contract is corrected) is fixed | MED impact | user can correct]

**What would raise confidence:** N/A.

## Status

- [x] Chunk 01: Extract shared Critic-freshness gate to lib/gates.py (STH-4F7C)
- [x] Chunk 02: atomic_write_text + cmd_clear OSError guards (STH-8M3V)
- [x] Chunk 03: Honor explicit /prawduct:critic mode argument (CRT-2N7V)
Context: All three chunks built and committed 2026-06-10/11 (ch.01 04f571a, ch.02 cd644be, ch.03 b5f0c2c). Cumulative Critic: 0 blocking / 0 warnings / 3 backlog-reconciliation NOTEs — ready for PR. Ch.03 caveat: the explicit-args fix is verified at the helper layer + contract pins; live end-to-end verification deferred post-release (CRT-9L2F — the bundle's own cumulative still recorded inference rationale; undetermined whether the edited skill ran). Follow-ups filed: STH-9T4F (two remaining non-atomic writes), CRT-9L2F.

## Scaffolding

Existing repo — no scaffold. Tests run via `python3 -m pytest tests/ -q` from the repo root. No new dependencies.

### Verification Strategy

Two-layer verify per the MET-6W3J lesson ("tests green" ≠ "surface correct"): (1) the pytest suite; (2) exercise the real product surface on this repo — for chunk 01, run the actual session-start briefing path (`_check_previous_session_gates`) and `prawduct-hook` stop-gate against contrived `.prawduct` state; for chunk 02, run `prawduct-hook clear --session-start` end-to-end and confirm state files land correctly; for chunk 03, invoke `/prawduct:critic <mode>` with an explicit arg and inspect `mode_chosen_by` in the findings file.

## Project Structure

No new modules expected except possibly none at all — chunk 01 adds a function to `lib/gates.py`, chunk 02 adds a helper to `lib/core.py`. Module boundaries per `project-preferences`: `bin/` entry points (lazy lib imports on hot paths), `lib/` implementation; return-value error handling (`status`/`reason` dicts), exceptions escape only at CLI boundaries.

## Build Chunks

### Chunk 01: Extract shared Critic-freshness gate to lib/gates.py (STH-4F7C)

- **Description:** The mtime-vs-session-start Critic-findings freshness check is duplicated nearly verbatim in `cmd_stop` (`bin/prawduct-hook` ~L795-820) and `_check_previous_session_gates` (`lib/briefing.py` ~L951-979), and the copies have diverged: cmd_stop runs the verify-resolutions scope check (`_verify_resolutions_gate_check`); the briefing copy does not, so the session-start advisory can report a stale verify-resolutions record as satisfying. Extract one shared gate function into `lib/gates.py` (return-value style, e.g. `{satisfied, reason}` — distinguishing "stale/invalid" from "fresh but scope-exceeded" so cmd_stop keeps its distinct blocker messaging) and repoint both call sites. This *changes briefing behavior on purpose*: the briefing copy gains the scope check. Per the gate-input-edit learning, grep both predicates' call sites before and after; per the parity-pin learning, confirm neither copy carries a `# intentional inline mirror` pin (pre-plan read: neither does — the briefing copy already lives in `lib/`, so the import-light rationale doesn't apply).
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/project-preferences.md`
- **Deliverables:** new shared function in `lib/gates.py`; `bin/prawduct-hook` cmd_stop and `lib/briefing.py` `_check_previous_session_gates` both delegating to it; tests in `tests/`
- **Tests:** unit tests on the shared function (fresh+valid+in-scope → satisfied; same-second tie → NOT fresh, preserving the strict-`>` STH-6B4R convention; missing `.session-start` → not satisfied; fresh verify-resolutions record with out-of-scope diff → not satisfied with scope reason); regression test that the briefing path now reports a warning for the stale-scope case it previously passed; existing cmd_stop gate tests stay green; a call-site parity test asserting both consumers reference the shared function (guards against re-divergence).
- **Acceptance criteria:** full suite passes; the briefing warning fires on a fresh-but-out-of-scope verify-resolutions record (the live gap); cmd_stop blocker text unchanged for both blocker variants.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status (via tagged change-log entry — views enabled)

### Chunk 02: atomic_write_text + cmd_clear OSError guards (STH-8M3V)

- **Description:** Add one shared `atomic_write_text(path, text)` helper to `lib/core.py` (tmp sibling + `os.replace`, modeled on the `.test-evidence.json` writer) and convert the audited non-atomic state-file writes: `.session-start` (`bin/prawduct-hook` ~L472), `.session-git-baseline` (~L567), `.session-handoff.md` (`lib/briefing.py` ~L912), `.advisories.json` (`lib/advisory_store.py` `write_store` ~L333). Verify `.gates-waived` (groomed into the set, but pre-plan grep found no code write site — likely agent-written; document if so). Guard the unguarded hot-path I/O in `cmd_clear`: the session-file unlink loop (~L465-468) and the `.session-start` write, plus the baseline write — OSError must not traceback the SessionStart hook; match the surrounding best-effort stance (stderr NOTE, continue). Sub-item already done: `gitstate._get_session_changed_files` already has its `(UnicodeDecodeError, OSError)` guard (`lib/gitstate.py:320`) — no change. Out of scope (note for backlog at chunk close): two further non-atomic sites found during planning, `lib/critic_marker.py:75` and `lib/operator_verification.py:251`.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/project-preferences.md`
- **Deliverables:** `atomic_write_text` in `lib/core.py`; converted call sites in `bin/prawduct-hook`, `lib/briefing.py`, `lib/advisory_store.py`; OSError guards in `cmd_clear`; tests in `tests/`
- **Tests:** unit tests for `atomic_write_text` (content written, existing file replaced, no `.tmp` residue on success, OSError propagation/return contract); cmd_clear resilience tests (monkeypatched OSError on unlink and on the `.session-start`/baseline writes → exit 0, no traceback); `write_store` keeps its `{status: error}` contract on OSError.
- **Acceptance criteria:** full suite passes; `prawduct-hook clear --session-start` runs end-to-end on this repo and `.session-start`/`.session-git-baseline` land with correct content and no `.tmp` residue.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status (via tagged change-log entry)

### Chunk 03: Honor explicit /prawduct:critic mode argument (CRT-2N7V)

- **Description:** Investigate-and-fix. Observed 2026-06-10 (feature/do-next ch.01): invoking the Critic skill with args `chunk` ran rule-1b inference instead, recording the verbatim inference rationale as `mode_chosen_by` — the documented explicit-args override (`skills/critic/SKILL.md` step 1: explicit `$ARGUMENTS` > plan-override > inference) didn't take effect in the forked skill. Step 1: reproduce — determine whether Skill-tool args reach `$ARGUMENTS` in `context: fork` execution (the `$ARGUMENTS` placeholder sits alone at SKILL.md ~L40), and re-read the CRT-3M8Q fix (#58) to see whether it covered explicit args or only the plan-field override. Step 2: fix at the root cause — likely candidates: skill prose restructure so the arg is unmissable, a hook-helper path (e.g. `infer-critic-mode <explicit-mode>` honoring an argument), or, if it is a genuine harness limitation, correct the documented contract instead (never leave prose promising behavior that can't happen). Step 3: whatever the fix, add the cheapest durable check available (a test if the fix is in hook/lib code; a doc-consistency assertion if prose-only).
- **Depends on:** none
- **Artifacts consumed:** `skills/critic/SKILL.md`, `lib/critic_mode.py`, backlog entries CRT-2N7V/CRT-3M8Q
- **Deliverables:** fix in `skills/critic/SKILL.md` and/or `lib/critic_mode.py`/`bin/prawduct-hook` per root cause; investigation findings recorded in the change-log entry rationale
- **Tests:** per fix shape (see step 3 above); existing `infer-critic-mode` tests stay green.
- **Acceptance criteria:** an explicit mode argument to `/prawduct:critic` demonstrably wins over inference and records `mode_chosen_by: "explicit-args"` (verified live in this chunk's own review where feasible), OR the contract prose is corrected to match reality with the limitation documented.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run against `merge-base...HEAD` (this IS the chunk's review and the `/prawduct:pr create` gate) and blocking findings resolved
  3. Chunk marked `[x]` in Status (via tagged change-log entry)

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** N/A in the product-UI sense — framework-internal fixes. After chunk 01 the session-start briefing correctly warns on stale verify-resolutions records.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after its Critic review passes; chunk 03 is `Type: cumulative-final` — commit first, then one `/prawduct:critic cumulative` serves as both its review and the PR gate. PR to `develop` via `/prawduct:pr` when the user asks.

- After chunk 03: cumulative review over the full bundle (the three fixes are independent; coherence risk concentrates in chunk 01's behavior-changing extraction).
