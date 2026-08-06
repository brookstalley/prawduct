<!-- Build Plan: critic-review-identity (target: patch — v3.2.7)

     Part 2 of the concurrent-dispatch defect. Part 1 shipped in v3.2.6
     (`build-plan-critic-concurrent-dispatch.md`) and closed the REACHABLE path:
     `critic-begin` refuses rather than displacing a live review. This plan makes
     the class impossible rather than unreachable, which is the distinction
     #602's fix shape draws and the reason both issues stayed open.

     Parent requirement: brookstalley/prawduct#602 (§ "Fix shape — two parts",
     part 2) and brookstalley/prawduct#171 (the role-keyed `partial_path`
     rendezvous, its "second, distinct collision path"). Merge candidates; this
     plan discharges the shared part-2 of both.

     Sequenced BEFORE the state-machine reachability test agreed with the owner
     and filed as a comment on #602 — that comment says so explicitly, because
     the review-identity binding changes the states such a test would pin.
-->
---
artifact: build-plan
# Namespaces this plan's chunk numbering and matches the change-log entries'
# `scope=`, which is what `regen-views` resolves to find this file.
scope: critic-review-identity
version: 2
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews — enforced at the mutation site, not by tool-restriction alone → conforms, and this plan carries that norm to the rendezvous: today a reviewer's write site is `<role>.json`, shared by every review in the worktree, so a straggler mutates a review it is not part of; keying the path by review id makes that write structurally impossible rather than merely refused upstream"
      - "authority fails closed; advice fails soft → conforms — `consolidate` is authority and fails closed on a partial whose `dispatch_id` is not the manifest's `id`; the foreign-partial and legacy-partial diagnostics in the incomplete no-op inform and fail soft"
      - "every fact has one home; every other mention is a reference to it → conforms, and it is why the manifest carries the rendezvous paths. The partial-path SHAPE is today restated in five places (code plus four instruction surfaces); adding a review-id segment to all five would create five copies of a more complex fact. `critic-begin` writes the resolved per-role paths into the manifest instead, and every instruction surface references the manifest entry — the shape gets one home, in the code that owns it. [DECISION: carry resolved rendezvous paths in the manifest rather than restating the new filename shape in each instruction surface | the norm's why is that a fact needing N edits already has N−1 wrong copies, and this fact is about to need all five edited at once — the moment to collapse it is now, not after the next shape change | user can veto/override]"
      - "goals and verification bind; prescribed method is advice → conforms — the Deliverables below name the routes I expect; the acceptance criteria are what bind"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms — every path this plan adds or moves is under `.prawduct/`"
      - "prawduct is written in Python and must never be specific to Python → inapplicable because nothing here inspects or classifies product code"
      - "prawduct guides and reviews; it never implements → inapplicable because this is prawduct's own runtime, not a governed product's code (owner ruling 2026-07-29, restated in the norm's Scope)"
      - "local-first: governance coordination is process-spawn + atomically-written files + git → conforms — no new surface of any kind"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution: new subcommands/flags are added; existing flag names, exit-code meanings and `--json` keys are never repurposed → conforms — `critic-restore` is a new subcommand, no existing flag or exit code changes meaning, and nothing here emits the manifest as `--json`"
      - "the evidence store is independently schema-versioned with forward-incompatibility detection → inapplicable because the dispatch manifest is per-clone scratch state with a single writer and a single reader in the same release, not the store. It is versioned by loud rejection instead (`validate_manifest`'s CRT-W2NV pin), which is the posture the sibling data-model norm prescribes"
  - artifact: observability-strategy
    dispositions:
      - "text emitted into a governed product names no prawduct-internal identifier — hook stdout/stderr carries the plain-language reason; ids stay in comments, tests and plans → conforms, and it binds every message this plan adds: the foreign-partial, legacy-partial and restore-refusal messages say what is on disk and what to run, never an issue number or a learning id. Runtime review ids (`rev-…`) are operator-facing data, not internal identifiers, and stay"
  - artifact: data-model
    dispositions:
      - "governance verdicts are computed from the append-only fact ledger, never from mutable model-written state — no model sits in a fact's write path → conforms, and this strengthens it: a reviewer's judgment currently enters a fact whose identity code cannot verify, because the only binding between partial and manifest is `commit_reviewed`. The manifest is code-written and the review id with it, so binding to that id keeps the check inside the code-written half"
      - "facts are immutable and append-only; a state change is a new fact → conforms — nothing here edits or deletes a fact. The defect is that a fact can be attributed to a review that never read the files; this makes the misattribution unrepresentable rather than repairing it after the fact"
      - "a fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped → conforms, and the manifest's new required `rendezvous` key inherits the same posture: an older manifest fails `validate_manifest` loudly (the CRT-W2NV pin's shape), and a partial written to the pre-keyed path is NAMED in the incomplete no-op with the reload remedy rather than being invisible"
      - "derived views are disposable and never authoritative → conforms — `.critic-findings.json` is untouched by this plan"
      - "two stores, two lifetimes → conforms — the partials directory and its archive are per-clone and already gitignored"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The requirement is documented on two open issues with converging fix shapes,
both re-read in full before planning, and the mechanism was verified in code rather than
recalled: `partial_path` is keyed by role alone (`critic_consolidate.py:579`), and
`consolidate` validates a partial's `commit_reviewed` against the manifest and nothing
else (`:2033`). `active_dispatch_refusal`'s own docstring already states the defect this
plan closes. The owner chose the scope (content binding *and* filename keying) over the
two narrower alternatives before planning began.

**Open assumptions / unknowns:**
- `[ASSUMPTION: a flat, review-id-suffixed filename is preferred to a per-review subdirectory | MED impact | user chose this scope explicitly; a subdirectory isolates identically but relocates the manifest, `_archive_leftovers`, `remove_partials`, `critic-discard`, the gitignore entries and the Stop-hook escape recipe — blast radius out of proportion to the defect]`
- `[ASSUMPTION: a partial written to the OLD unkeyed path is refused-and-named rather than accepted as a fallback | HIGH impact | user can override — accepting it would reopen the hole for exactly the straggler this plan exists to stop, so the version-skew case is served by a named remedy instead]`

**What would raise confidence:** N/A (High).

## Status

- [ ] Chunk 1: The rendezvous carries review identity
- [ ] Chunk 2: `critic-restore` — the recovery this binding replaces
Context: Plan written 2026-08-05 on `fix/critic-review-identity` off `develop` at `5812a02`
(v3.2.6 released, nothing else in flight). Nothing built yet. Next: Chunk 1.

## Build Chunks

### Chunk 1: The rendezvous carries review identity

- **Description:** A partial is bound to the review that dispatched it, at both layers
  the two issues name. **Filename** (#171): `partial_path` and `started_path` gain a
  review-id segment, so two reviews in one worktree can never contend for one path and a
  straggler from an abandoned review cannot satisfy another review's roster. **Content**
  (#602): the partial declares the dispatching review's id and `consolidate` fails closed
  when it is not the manifest's — belt-and-braces once the names diverge, and the check
  that still fires when a reviewer is handed the wrong id in its dispatch prompt.

  **The field is `dispatch_id`, not `review_id`, and the name is a finding not a
  preference.** The partial ALREADY carries `resolutions[].review_id`, meaning the *prior*
  review whose finding is being dispositioned. A top-level `review_id` meaning "the review
  that dispatched me" would put two different referents under one token in one
  model-written record — the transcription seam `learnings.md` names as the place
  identifiers silently degrade (its live instance, a partial's `name` becoming a fact's
  `title`, cost a firing control). `dispatch_id` also matches the module's existing
  vocabulary — `dispatch_commit`, `dispatch_age_minutes` — so the pairing with the
  manifest's `id` is stated once, in the validator, rather than inferred.

  **The comparison strips before it judges**, per the `files: []` precedent in this same
  module: a fail-closed validator guarding a model-written field must reject genuine
  ambiguity and tolerate the encoding variant that normalizes identically. A mismatched or
  missing id is genuine ambiguity — the `commit_reviewed` class exactly — and hard-fails.
  Surrounding whitespace is not, and must not abort a whole consolidation. That precedent
  also notes its own strictness was never codified by a test, so both sides are tested
  here: the stripped variant consolidates, the genuine mismatch fails closed.

  The path shape gets **one home**. `critic-begin` resolves the per-role partial and
  started paths and records them in the manifest under `rendezvous`; the instruction
  surfaces stop spelling the filename and reference that entry instead. This is the
  `every fact has one home` norm applied at the moment the fact would otherwise be copied
  five times (see `governed_by` dispositions).

  **Version skew is the one behaviour change a reader will hit.** A stale cached skill
  writes to the pre-keyed `<role>.json`, which the new consolidator does not look for.
  Accepting it as a fallback would reopen the hole, so instead the incomplete no-op names
  the file, says what wrote it, and gives the reload remedy — the same posture
  `critic-begin --mode`'s required-flag refusal already takes, and the same
  refusal-names-a-reaching-remedy rule Chunk 2 of the part-1 plan established.

- **Depends on:** none (part 1 shipped in v3.2.6)
- **Artifacts consumed:** brookstalley/prawduct#602 (fix shape part 2; the
  `critic_consolidate.py:1890` binding analysis); brookstalley/prawduct#171 (the
  `partial_path` rendezvous, and the 2026-07-30 incident where the loser's only signal was
  a failed `Write` and a BLOCKING finding went unrecorded);
  `.prawduct/artifacts/build-plan-critic-concurrent-dispatch.md` (part 1, whose Status
  Context hands this plan its scope); `.prawduct/artifacts/architecture.md` §Direction;
  `.prawduct/artifacts/data-model.md` §Direction.
- **Deliverables:**
  1. `plugin/lib/critic_consolidate.py` — `partial_path`/`started_path` keyed by review
     id; `rendezvous` written by `begin_review` and required by `validate_manifest`;
     `dispatch_id` required by `validate_partial` and compared (stripped) against the manifest in
     `consolidate`; `pending_state`, `started_age_minutes` and `_incomplete_noop_message`
     routed through the manifest's id; foreign-partial and legacy-partial diagnostics in
     the incomplete no-op.
  2. `plugin/agents/critic-reviewer.md` — the write path becomes the manifest's
     `rendezvous` entry for the reviewer's role; the partial schema gains `dispatch_id`.
  3. `plugin/skills/critic/review-protocol.md` — the coordinator dispatch prompt template
     and the single-pass partial schema.
  4. `plugin/skills/critic/goals-1-3.md` — the single-pass write path and schema.
  5. `plugin/skills/critic/SKILL.md` — the single-pass write path in step 7.
  6. `plugin/skills/critic/review-cycle.md` — the manifest key list gains `rendezvous`.
  7. `tests/test_critic_consolidate.py`, `tests/test_critic_session_guard.py`,
     `tests/test_critic_reviewer_agent.py`, `tests/scenarios/kernel_v3_harness.py` — the
     existing partial writers routed through the keyed path, plus new coverage: a
     straggler from another review neither satisfies nor poisons the current roster; a
     `dispatch_id` mismatch fails closed while a whitespace-padded one consolidates; a legacy
     unkeyed partial is named with its remedy.
- **Tests:** as above. Every new behaviour is watched failing before the code that
  satisfies it — the straggler and mismatch cases by mutation, the diagnostics by
  asserting the message before writing it.
- **Acceptance criteria:**
  1. A partial written for review A, present in the partials directory at an unchanged
     HEAD while review B is pending, does **not** count toward B's roster and does **not**
     overwrite B's own partial for that role.
  2. A partial whose `dispatch_id` is not the manifest's `id` fails consolidation closed,
     naming both ids; one that differs only by surrounding whitespace consolidates.
  3. A partial at the pre-keyed `<role>.json` path is reported by name in the incomplete
     no-op, together with the reason (a skill older than this hook) and a remedy that
     reaches the state.
  4. The partial-path shape appears in exactly one place in the codebase; no instruction
     surface spells it.
  5. Suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** built, acceptance criteria pass, `/prawduct:critic` run, blocking
  findings resolved, change-log entry tagged `scope=critic-review-identity`, committed.

### Chunk 2: `critic-restore` — the recovery this binding replaces

- **Description:** Chunk 1 removes a recovery path that worked, and owing a replacement is
  the reason this is in the plan rather than the backlog. #602 states it plainly: *"The
  documented recovery works precisely because of defect 2"* — copying an archived review's
  partials into the current review's directory succeeds only because a partial is bound to
  a commit rather than to a review. After Chunk 1 that copy is inert, and it should be:
  it was always a mis-attribution, recording one review's findings under another's id.

  The honest replacement restores the archived review **as itself** and consolidates it:
  `prawduct-hook critic-restore <review-id>` copies that review's manifest and partials
  back out of `.critic-partials-archive/`, refusing while anything is pending so it can
  never merge two reviews' files into one directory. Because Chunk 1 keys the names by
  review id, a restored set is self-identifying and the round trip is lossless — the same
  property that makes the mis-attributing copy impossible makes the honest one safe.

  Every message that currently ends at "archived to X" gains the command that gets X back.

- **Depends on:** Chunk 1
- **Artifacts consumed:** `plugin/lib/critic_consolidate.py` (`_archive_leftovers`,
  `ARCHIVE_DIRNAME`, `_ARCHIVE_KEEP` — the archive this reads from, and the newest-3
  retention that bounds what is restorable); the part-1 plan's Chunk 2, whose acceptance
  criterion — *every reachable refusing state has at least one documented command that
  clears it* — is the rule this chunk applies to the state Chunk 1 creates.
- **Deliverables:**
  1. `plugin/bin/prawduct-hook` — `cmd_critic_restore`, refusing when a review is pending
     (naming `critic-consolidate`, `critic-end` or `critic-discard` per the state on disk)
     and when the named review is not in the archive (listing what is).
  2. `plugin/lib/critic_consolidate.py` — the restore itself, beside `_archive_leftovers`
     so the write and its inverse stay adjacent; `critic-discard`'s output and
     `active_dispatch_refusal`'s complete-roster escape name it.
  3. `plugin/skills/critic/SKILL.md` — one line placing `critic-restore` beside
     `critic-discard`, both marked as the main session's, not the reviewer's.
  4. `tests/test_critic_session_guard.py` — restore-then-consolidate round-trips an
     archived review to a fact carrying its own id; restore refuses onto a non-empty
     partials directory; restore of an unknown id names what is available.
- **Tests:** as above; the round trip is the load-bearing one — it is what proves the
  recovery this chunk documents actually reaches the state it claims.
- **Acceptance criteria:**
  1. An unconsolidated review archived by a later dispatch can be restored and
     consolidated, and the resulting fact carries **its own** review id.
  2. Restore refuses while any review is pending, naming a remedy that reaches that state.
  3. No message in the subsystem ends at "archived to X" without naming how to get it back.
  4. Suite green.
- **Critic mode:** cumulative
- **Type:** cumulative-final
- **Done when:** built, acceptance criteria pass, `/prawduct:critic cumulative` run,
  blocking findings resolved, change-log entry tagged `scope=critic-review-identity`,
  committed, `/prawduct:pr`.

## Governance Checkpoints

**After Chunk 1** — the architecture checkpoint, and it is not pro forma here: Chunk 1
changes the mechanism that reviews it. The plugin runs from its installed copy rather than
the working tree, so the branch's own reviews are unaffected while building; the exposure
is the release, where a review dispatched by the old code and consolidated by the new one
must fail loudly rather than silently. Acceptance criterion 3 is that check, and the
checkpoint is where to confirm it holds before Chunk 2 builds on it.

**Commit & PR cadence:** one commit per chunk; the Chunk 2 `cumulative` is the bundle
review and the `/prawduct:pr create` gate. Target: patch release v3.2.7.

**Deliberately not in this plan:** the state-machine reachability test (#602 comment,
owner-approved, sequenced after this work — the review-identity binding changes the states it
would pin); the `building.md` re-invoke caveat and the Stop hook's `rm -rf
.prawduct/.critic-partials` escape, both reverted at the v3.2.6 release and named in
`e876826`; `critic-status` (#602's "separable residual" observability half).
