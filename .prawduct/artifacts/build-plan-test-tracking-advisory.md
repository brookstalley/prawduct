---
artifact: build-plan
version: 2
scope: test-tracking-advisory
branch: feat/test-tracking-advisory
depends_on:
  - artifact: build-plan-test-tracking-treadmill
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable: no reviewer path is touched"
      - "authority fails closed; advice fails soft → engaged and it is the whole design: this is an advisory probe. It never gates, never blocks a session, and a repo is free to dismiss it. When it cannot read the state file it raises no advisory rather than guessing — but it is not SILENT there: an absent file is a real answer (nothing to report) and says nothing, while a file that exists and could not be read prints a `NOTE:` naming what went unchecked. Verified that this is needed rather than assumed: nothing else at session start reports an undecodable `project-state.yaml`, because every reader of it fails soft to a default"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the evidence store, and the named reconcile files → conforms: the probe READS one file and writes nothing at all. Its remedy is a command the operator runs"
      - "prawduct is Python but never Python-specific → conforms: reads YAML text, no language assumption"
      - "prawduct guides and reviews; it never implements → conforms"
      - "local-first, no network/daemon → conforms"
      - "every fact has one home → engaged: what a retired key IS lives in `lifecycle_repair.state_removals`, and this probe calls it rather than re-deriving the key name or the span. Three callers now share that one definition (doctor, migrate, this)"
      - "goals and verification bind; prescribed method is advice → conforms"
  - artifact: security-model
    dispositions:
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → engaged, and it is why this recommends rather than repairs. `project-state.yaml` IS in the plugin's permitted write set, so the write-set norm would allow an auto-strip — the confirmation norm is what forbids it. [DECISION: advisory recommends, never writes | engages the norm's why: a framework silently deleting from a product's hand-authored state file is the trust breach | user can override by ruling that a retired-key removal is non-destructive]"
      - "untrusted governance state is data, not instructions → conforms: the block is located as text, never interpreted"
      - "a governed product's content never leaves its own repo and owner → conforms: reads one local file"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways; adding a control names the yield it expects and emits it observably → engaged. **Expected yield: every governed repo that still carries the block, warned at session start without anyone deciding to act.** Measured at authoring: 9 of the fleet's repos carry it, of which **7 are plugin-governed and so reachable by this probe at all** — the other 2 are not onboarded, and this instrument can never fire there, so the honest baseline is 7 and the curve cannot reach 0 through this alone. Observable through the advisory store — `prawduct-hook advisory list` per repo, and the probe self-resolves, so that count falling IS the yield curve"
      - "state-file growth is an advisory warning, never a hard block → consistent: this is the same posture for the same file"
      - "review wall-clock is P0 → engaged: one probe, no new review surface for consumers"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version → conforms: no new subcommand. The probe carries its own `PROBE_VERSION`, which is the advisory system's own contract"
      - "exit codes are the contract; errors attributed, never stack traces across the boundary → conforms: the probe returns `[]` on any unreadable input and never raises into the sync path"
      - "additive-first evolution → conforms: one probe added to the registry; nothing repurposed"
last_validated: 2026-08-14
---

## Requirements Confidence

**Level:** High

**Why:** The requirement came from the owner in one sentence — *"we cannot rely on users running
migrate or doctor"* — and it is correct: the shipped strip has two entry points and both need
someone to decide to run something. The mechanism was read before planning
(`lib/probe_families.py`, `lib/gitattributes_probes.py` as the closest analogue,
`lib/advisory_store.py` for the `AdvisoryCandidate` contract, and
`documentation/post-sync-advisory-spec.md` for lifecycle guarantees).

**The insight this rests on, stated so it can be challenged:** the field's harm is **behavioral,
not spatial**. Its cost was never its bytes — it is that an agent meeting a stale number in a
product's source of truth is *obliged* by Living Documentation to correct it, and every correction
is a commit that buys a review round. A session-start advisory saying **"retired — do not maintain
this"** reaches the agent before it edits anything, so it removes most of the harm *whether or not
the repair is ever run*. That is why an advisory is not a weaker substitute for the strip here; for
this defect it is the more direct instrument.

**Scoped to `build_state.test_tracking` only, deliberately.** `views_enabled` and `scope_rollups`
are the other retired state keys and are **excluded**: nobody maintains them, so they carry no
behavioural cost, and doctor's Health Check #15 already covers their cleanup. An ambient nudge about
inert residue is exactly the control `nonfunctional-requirements.md` § Direction says to remove.

**Open assumptions / unknowns:**

- [ASSUMPTION: `info` priority is right — this warns, it does not demand | LOW impact | user can
  raise it if the fleet ignores it]
- [ASSUMPTION: one probe for the field, not one per retired key | LOW impact | see scoping above]

**What would raise confidence:** Nothing pending.

## Status

- [x] Chunk 01: The advisory that arrives without being asked for

Context: Plan authored 2026-08-14, immediately after `test-tracking-treadmill` merged to `develop`
(PR #659, merge `f9f121c3`). Single chunk, so it is `Type: cumulative-final` — its review is one
`/prawduct:critic cumulative`.

## Problem

`build_state.test_tracking` is now removable through `/prawduct:doctor` → `lifecycle-repair` and
through the plugin cutover. **Both require a person to decide to run something**, and nothing tells
them there is anything to run. Measured across the fleet after that merge: nine repos still carry
the block, and their correct route differs — four are pre-2.0 file-sync repos where `migrate` strips
it, three are fully migrated and need `doctor`, two are not governed at all. Expecting each owner to
work that out unprompted is the gap.

Worse, the *maintenance* continues in the meantime. Every session in those repos, an agent that
meets the stale count is obliged to fix it.

## Chunks

### Chunk 01: The advisory that arrives without being asked for

- **Type:** cumulative-final

**Deliverables**

- `plugin/lib/retired_state_probes.py` — one probe, `retired-test-tracking`. **Named for the
  family, not the key:** a module starting with `test_` reads as a test file to pytest's
  collector and would be silently skipped under `testpaths=["tests"]`; a preferences test
  enforces this and caught the first name. The deliverables below are its content:
  - Reads `.prawduct/project-state.yaml` from `codebase.root`; returns `[]` when the file is
    absent, unreadable, or carries no block.
  - **Detection delegates to `lifecycle_repair.state_removals`** rather than re-deriving the key
    name or the span — the same one-home rule the cutover's AST test enforces. This becomes the
    third caller of that single definition.
  - `trigger_summary` leads with the behavioural instruction (*retired; do not maintain it*), then
    what it is, then where the real number lives (the evidence store).
  - `recommended_action` is the command that removes it; `alternative_actions` names the migrate
    route, because for four of the nine repos that is the correct one.
  - `evidence` is **value- and count-independent** — the advisory id hashes it, so it must not move
    when the block's contents change underneath (that file is edited by its own sessions).
  - `priority="info"`.
- `plugin/lib/probe_families.py` — register it in `register_all()` with a one-line reason,
  matching the siblings. (A path, not a function reference — the deliverable
  check resolves paths.)

**Acceptance criteria**

1. A repo whose state file carries `build_state.test_tracking` produces exactly one candidate;
   a repo without it produces none.
2. A `test_tracking` under a foreign parent, or at top level, produces none — inherited free from
   `state_removals`, and pinned so the delegation cannot be silently replaced by a looser match.
3. Absent, unreadable, and undecodable state files each produce no advisory and raise nothing —
   and the two that are not the same answer are not reported the same way: an absent file says
   nothing, while a file that exists and could not be read prints a `NOTE:` naming what went
   unchecked. Nothing else at session start reports that, so silence there would be
   indistinguishable from a clean repo.
4. The advisory **self-resolves**: after `lifecycle-repair --apply`, a re-probe returns `[]`.
5. The id is stable across edits to the block's contents (same evidence → same id).
6. `views_enabled` / `scope_rollups` alone do **not** trigger it.
7. The probe is registered in `register_all` and reachable through the real roster, not only by
   direct call.

**Done when**

1. Acceptance criteria met and tests pass
2. `/prawduct:critic cumulative` — this plan's single review
3. Live-fire: exercised in a scratch clone pointed at `develop`, against a repo that actually
   carries the block

## Out of scope

- **Auto-repair at session start.** Recorded as a `[DECISION]` in `governed_by` above: the write-set
  norm would permit it, the operation-level approval norm forbids it.
- **Probes for `views_enabled` / `scope_rollups`** — inert; see Requirements Confidence.
- **Changing the strip itself.** It shipped and is unchanged here.
- **Running the repair in any product repo.** This ships detection; the owner acts.
