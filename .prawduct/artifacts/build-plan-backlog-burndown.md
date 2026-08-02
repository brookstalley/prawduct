---
artifact: build-plan
version: 2
# Distinct scope from the start. Never null and never a version: a null scope
# inherits another scope's shipped checkbox flips at regen-views, and a version
# tag would collide with the release plans.
scope: backlog-burndown
depends_on: []
governed_by:
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary + stdout/stderr channel split → conforms (the three new emissions — Chunk 02's degraded-progress notice, Chunk 04's truncation error and untriaged bucket — use the existing prefixes on the documented channel)"
      - "ledger has a single writer; agents never hand-author it → inapplicable because no chunk writes a ledger line; Chunk 03 changes the *inputs* to code-written records, not the writer"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms, and Chunk 04 closes this norm's `in-transition` residue (the four remaining sites). Binds the new emissions too: none may name an issue id"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms (Chunk 03 and Chunk 04 harden code-side paths only)"
      - "facts immutable and append-only → conforms (Chunk 04 validates on read/compose; it never edits a fact)"
      - "derived views never authoritative → conforms, and Chunk 02 repairs a violation: the `new` exemption must expire against `resolve_chunk_progress`, never against the checkbox view"
      - "newer-schema fact surfaced, never dropped → **conforms** (reason corrected 2026-08-02 by PR review). The original reading — *inapplicable because no chunk changes the fact schema* — is false: Chunk 03 adds `scope_chosen_by` to the persisted review-fact body and changes `record_lint.counts` values from int to int-or-null inside that same body. Both are **additive**, so `evidence.SCHEMA_VERSION` stays 1 and an older reader ignores an unknown key rather than dropping the fact — the conclusion held, the stated reason did not. Recorded rather than quietly repaired because a disposition is what the owner vetoes, and this is the drift class the plan exists to fix, one artifact over"
      - "two stores, two lifetimes → inapplicable because no chunk moves state between the committed and gitignored stores"
      - "`backlog_service_repo` selects the authoritative store; frozen markdown is never live → conforms, and Chunk 01 is what makes the next repo's cutover satisfy it"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → **ruled 2026-08-01**, conforms elsewhere. `regen-views` is **advice**: it emits no verdict and no gate reads its output, so the fail-closed half never attaches and `data-model.md`'s *derived views are never authoritative* decides the posture. Fail-soft is **per view**, which preserves VWS-6R4T's *no silent partial flips* by moving the atomicity unit from the run to the view. Precedence recorded on both norms; ruling in `learnings.md` [[regen-views-is-advice]]. Chunk 03's ancestor guard fails closed to cumulative/final and #327 instantiates *advice fails soft is not advice fails silent* — both unaffected"
      - "every fact has one home; every other mention is a reference → conforms, and Chunk 02 repairs a violation: the chunk-heading guard test is a second implementation of a contract `plugin/lib/buildplan_refs.py` owns"
      - "goals and verification bind; prescribed method is advice → conforms (this plan's Deliverables are pre-code guesses; a builder who finds a better route takes it and records why)"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches the review-active mutation guard"
      - "local-first governance, no network in the governance runtime → inapplicable because Chunk 04 refactors the existing opt-in backlog transport and adds no surface"
      - "the plugin writes nothing into a governed repo except its own state → conforms (Chunk 01's banner is written into `.prawduct/backlog.md`, which is prawduct's own state)"
      - "Python but never Python-specific → inapplicable because no chunk touches per-language gate dispatch"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime, not a product's"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; run-count is a lever → conforms, and it is why the batch is 4 chunks rather than one per item"
      - "proportionality ratchets both ways; a new control names the yield it expects and emits it observably → conforms *conditionally* — Chunk 02 adds one control (#327's degraded-reading notice), so that chunk must state its expected yield and make the notice countable. Done-when step 2 carries it"
      - "state-file growth surfaced as an advisory, never a hard block → inapplicable because no chunk changes a size threshold"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative — a small feature is a patch bump → conforms (this batch is a patch release)"
      - "gitflow: features branch off `develop` and merge back → conforms (`fix/backlog-burndown` is off `develop`)"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; no per-subcommand version → conforms"
      - "exit codes are the contract; stable severity prefixes; errors attributed, never stack traces → conforms (Chunk 04's malformed-SHA path yields no edge and no traceback; the truncation signal is an attributed `TransportError`)"
      - "additive-first evolution; `--json` keys are never repurposed → conforms with a recorded decision, see [DECISION] under Chunk 04 — #532 changes the *value* `open` reports, not the key's documented meaning. **Chunk 02 DEPARTS on the flag-repurposing clause and conforms on the rest**: `--check` now does the opposite of what it documented, which is a repurposing wearing a deprecation's clothes and is recorded as a departure rather than claimed as conformance (the norm's why is about consumers pinned at version N, and every `--check` consumer is prose, not code). The exit-3 sentinel is separately additive and conforms — it repurposes neither 1 nor 2. Both recorded as [DECISION] blocks; `api-contract.md`'s sentinel registry and Deprecated inventory updated to match"
      - "exit codes are the contract; unknown flags rejected with a usage error (exit 2) → Chunk 02 **repairs a live violation**: `cmd_regen_views` reads `--check` by membership test and silently ignores every other argument"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms"
      - "a destructive or irreversible operation requires owner approval at the operation level → conforms, and Chunk 01 sharpens the runbook whose operation-level gate this is"
      - "a governed product's content never leaves its own repo and owner → inapplicable because the upstream-filing path is explicitly out of this batch (#234 and #217 stay gated)"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Sixteen already-triaged tracker items, each carrying a stated problem, a repro, and an
owner-reviewed fix-shape. No discovery is owed: every item was filed against observed behavior,
and the batch was re-derived from the live tracker on 2026-08-01 with each item's *ask* re-read
against current machinery rather than trusted from its citations.

**#533 is the one exception and is confident for a different reason** (added to Chunk 04 on
2026-08-01). It is a *feature* request from outside, so there is no repro to re-read — but it needs
no discovery either: the filer named two live consumers, three candidate shapes, and their
preference, and the value being published already exists and is already depended on. What is being
decided is only whether to publish it, which the owner has answered.

**Open assumptions / unknowns:**

- [ASSUMPTION: #233 and #352 are satisfied rather than abandoned | LOW impact | user can veto]
  #233's three acceptance boxes are met by v3.2.0 Chunk 06 (`verify-migration` exit 0 with five
  empty lists, `backlog_service_repo` set, ids resolving); #352's own closing condition reads
  *"closes when the backlog-service slice ships"*, and it shipped. Chunk 01 closes both as
  `shipped`. Reversible — reopening an issue costs nothing.
- [ASSUMPTION: #211's authoritative contract is the production matcher, not the guard test | MED
  impact | user can override] The item asks for a deliberate decision and forbids narrowing
  `_CHUNK_ID_SEP`. This plan widens the test. The alternative — declaring the strict
  `### Chunk NN:` form the *authored* standard and re-labelling the test as a style guard — is a
  norm decision, not a defect fix, and would need its own recorded ruling.
- [ASSUMPTION: #201's three remaining legs land in one chunk | MED impact | user can defer legs]
  One of its four legs already shipped (see Chunk 02); recursive discovery, the broadened
  chunk-line matcher, and decoupled view regeneration ship together. The item names decoupling as
  the load-bearing half, and splitting it would leave the trap — prawduct's own error message
  recommending the action that triggers the bug — live for another cycle.
- [DECISION: `regen-views` is **advice** and fails soft at the granularity of one view; the
  atomicity unit moves from the run to the view | the authority norm's why is that a verdict must
  not be satisfiable by feeding it garbage, which reaches a command only where a verdict exists to
  corrupt — `regen-views` emits none and no gate reads its output, so `data-model.md`'s
  *derived views are never authoritative* decides the posture. VWS-6R4T's *no silent partial flips*
  is preserved, not reversed: a view whose inputs are invalid is skipped and reported, never written
  half-right, and `apply_regen` already writes each view as one whole file | owner ruled 2026-08-01;
  recorded in `learnings.md` [[regen-views-is-advice]] with precedence on both norms]
- [DECISION: `regen-views` loses `--check`; there is ONE mode and views always regenerate |
  owner-stated requirement 2026-08-01. `check_only` is consulted only *after* the validation block
  returns 2 (`plugin/bin/prawduct-hook:3028-3043`), so `--check` and the real run validate and fail
  identically — the two-step pre-flight every release plan prescribes cannot catch anything the
  single run doesn't. Worse, `--check` exits 0 while writes are *pending*, so a clean check means
  "the tags parse," not "the views are correct": #201's reporting repo lost six release-notes
  sections and ran `scope_rollups` at 34 keys instead of 62 while the check read clean
  (`.prawduct/backlog.md:1101`). Always-writing makes that drift structurally impossible. Coheres
  with the ruling above — "always regenerated" and "one bad tag writes nothing" cannot both hold |
  user can veto/override]
- [DECISION: `--check` is **repurposed under a deprecation notice** — it keeps parsing, prints a
  stderr deprecation notice, and performs the full regen; removal defers to the next major |
  **This DEPARTS from `api-contract.md`'s additive-first norm and the departure is the clause
  *"existing flag names … are never repurposed"*, not the *"deprecation is signalled, not silent"*
  clause it satisfies.** An earlier draft of this decision claimed conformance by engaging only the
  second, which was the wrong half: the norm's reference example, `stamp-merged`, still *does what
  it documented* while warning, whereas `--check` now does the opposite of "writes nothing." Calling
  that a deprecation would have laundered a semantic change through a compatibility mechanism.
  Recorded as a departure instead. Why it is the right departure: the norm's why is that a consumer
  pinned at version N must not break at N+1, and the consumers here are **documentation read by
  humans, not pinned code** — no hook, skill, or gate invokes `--check` (verified by search). A hard
  removal would break every stale runbook at once; the repurposing makes them write, which is the
  behaviour the owner asked for and the one they wanted next anyway. Deleting the flag outright is
  the same departure plus a broken command, so it buys nothing | user can veto/override]
- [DECISION: `regen-views` gains a documented exit-**3** sentinel = *partial: some views suppressed,
  the rest written* | the writer scheme already assigns 0=written, 1=refused/incomplete install,
  2=usage or validation error with nothing written, and per-view fail-soft creates a fourth outcome
  that none of them names. Reusing 1 would collide with the ImportError case and reusing 2 would
  claim nothing was written when views WERE. `api-contract.md` already documents per-command
  sentinels beyond 0/1/2 (`critic-begin` 2 = scope-widened; `backlog verify-migration` 4 =
  completeness), so a documented sentinel is the established additive route and repurposes no
  existing meaning | user can veto/override]

**What would raise confidence:** N/A — the residual uncertainty is scope preference, not knowledge.

## Scope

**In:** seventeen items, re-derived by `refs:` co-location: **#528, #530** (Chunk 01);
**#201, #211, #224, #327, #333** (Chunk 02); **#206, #208, #218, #288, #344** (Chunk 03);
**#209, #307, #313, #532, #533** (Chunk 04). Plus two dispositions with no code: **#233, #352**.
Sixteen were `stage: ready` at authoring; **#533 was added to Chunk 04 on 2026-08-01 at owner
request** — an externally-filed feature, not a burn-down item, admitted because it shares the
chunk's defining property (no surface in common with anything else in the batch).

**Explicitly out, and why — do not quietly restore any of these:**

| Item | Why out |
|---|---|
| #330 | It *is* v3.2.0-golive Chunk 07 (the advisory lift), owned by the primary checkout. Not a file collision — a scope collision. |
| #128, #161 | Re-staged `ready` → `design` on 2026-08-01. Both make an unused number exact; `gates.py` evaluates only `failed`. |
| #234 | Gated behind #217 (upstream consent and taxonomy). The drop-box may not retire before its replacement exists. |
| #190, #325 | Cite `plugin/lib/briefing.py`, dirty on `feature/upgrade-discovery-relay` right now. |
| #213, #329 | Cite `documentation/backlog-service-requirements.md`, dirty on the same branch. |
| #163, #165, #177, #232, #235, #326, #331, #347 | Ready and clear, but M-effort with real design content. Deliberately deferred to keep this batch reviewable. |

## Verification Strategy

Each chunk is verified by its own targeted tests plus the full suite, then exercised the way the
affected operator would meet it:

- **Chunk 01** is verified by *reading the runbook as an operator following it*, in order, against
  the hallucinote gate exercise — the two defects are ordering and omission, which no test sees.
- **Chunks 02–04** are verified by running the affected hook command from **this checkout**
  (`python3 plugin/bin/prawduct-hook …`) and reading its output. A `$PATH` `prawduct-hook` resolves
  to a different tree and will silently verify the wrong code.

**This plan was a live reproduction of two of its own items.** `active_build_plan` points at
`artifacts/build-plan-v3.2.0-golive.md`, which belongs to another worktree; this branch builds a
different plan, and nothing checked the two agree. That is exactly #208 and #344. Until Chunk 03
landed, every review on this branch graded the golive plan's deliverables against this diff and
reported zeros that read identically to a clean check.

~~**Operating rule until Chunk 03 lands:** pass mode, scope and chunk explicitly on every
dispatch — `python3 plugin/bin/prawduct-hook critic-begin --mode <m> --scope backlog-burndown
--chunk NN`.~~ **Struck 2026-08-01 by Chunk 03, the `--scope` half genuinely and the rest by
narrowing.** `critic-begin` now derives the scope itself when the dispatch omits it, by matching the
branch name against the scopes plans declare — `fix/backlog-burndown` resolves to this plan, and the
manifest, the review fact and the ledger event all name it. The workaround is no longer required,
and passing `--scope` here would only re-assert what code already answers. What still binds: **pass
`--mode` and `--chunk`.** `--mode` because inference reads a session-start branch marker that a
worktree can outdate, and `--chunk` because record-lint otherwise infers it from Status, which on a
`views_enabled` plan names the chunk *after* the one just built.

Do **not** repoint `active_build_plan` — the pointer is single-slot, the golive plan is legitimately
in progress, and repointing was never the fix (#344's own evidence says so). Chunk 03's whole shape
is resolving *around* a correct pointer rather than correcting it.

## Project Structure

Existing surfaces only; this plan creates no files.

```
plugin/skills/backlog/migration-scrub.md   Chunk 01
plugin/lib/buildplan_refs.py, views.py,
        plugin/bin/prawduct-hook (cmd_regen_views)  Chunk 02
plugin/lib/critic_mode.py,
        critic_consolidate.py, record_lint.py   Chunk 03
plugin/lib/evidence.py, backlog/*.py,
        backlog/cli.py, plugin/bin/prawduct-hook  Chunk 04
```

### Module Boundaries

`plugin/lib/buildplan_refs.py` owns the one answer to "which chunk is in progress"
(`resolve_chunk_progress`). Chunk 02 keeps it that way — no second progress reading is introduced,
and the `new` exemption expiry consumes that function rather than re-deriving from checkboxes.

## Build Chunks

### Chunk 01: The migration runbook's two operator-facing defects

- **Description:** `plugin/skills/backlog/migration-scrub.md` tells an operator to dispose before
  it verifies, and never tells them to mark the source file dead. Both were found by prawduct's own
  cutover and fixed only *here*, by hand — the fleet still ships the defects. This chunk is
  sequenced first because the v3.2.3 owner-gate exercise against `brookstalley/hallucinote` depends
  on both: its Stage 5 asks the operator to confirm the runbook now reads verify-then-dispose, and
  it does not. Also records the two dispositions the migration already earned.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/operational-spec.md` (§ Direction — owner approval at
  the operation level), `.prawduct/artifacts/data-model.md` (§ Direction — the frozen-markdown norm)
- **Deliverables:**
  - **#528** — `plugin/skills/backlog/migration-scrub.md`: `verify-migration` moves **before** the
    Step 4 disposals, with the reason stated in the runbook, not just the commit. The gate certifies
    *the migration* (nothing stranded); merges and drops are tracker actions taken after it, and the
    frozen markdown is expected to diverge from the tracker thereafter. Step 6's cutover keeps its
    own gate reference — the fix is ordering plus rationale, not moving the gate out of the cutover.
  - **#530** — same file, Step 6: instruct the operator to write a frozen-history banner at the head
    of the source. Two constraints the hand-written one taught, both of which must survive into the
    instruction: the banner is a **blockquote, not an HTML comment** (a comment is invisible in
    GitHub's rendered view — a reader saw a heading and a list of open items with no signal at all),
    and the **rollback clause ships with it**. Adding the banner mutates a file the rollback note
    claims is never mutated; a rollback that unsets the scalar and closes the issues without
    reverting the banner leaves the restored backlog announcing that it is frozen and redirecting to
    a tracker that was just closed.
- **Tests:** none — prose in a skill file, no machinery. Verification is the read-through below.
- **Acceptance criteria:** an operator following the runbook top to bottom runs the gate before any
  disposal, and finishes with a source file that announces it is dead. Read it in order against the
  hallucinote exercise's Stage 4→5→6 and confirm no step contradicts another.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met; the runbook read through in order with no residual contradiction
  2. `/prawduct:backlog update brookstalley/prawduct#233 status=shipped` and
     `#352 status=shipped`, each with a one-line reason naming what satisfied it
  3. `python3 plugin/bin/prawduct-hook critic-begin --mode chunk --scope backlog-burndown --chunk 01`,
     review run, blocking findings resolved
  4. Committed with a change-log entry tagged `scope=backlog-burndown`

### Chunk 02: Plan discovery and plan reading

- **Description:** Defects in how the runtime decides what a build plan is and what it says (five
  tracker items, several legs each), plus one owner-requested simplification (`regen-views`
  collapses to a single always-writing mode).
  They interlock: #201's broadened chunk-line matcher and #211's guard-test drift are the same
  question — which chunk-heading contract is authoritative — answered in two places, and #224 and
  #327 both depend on `resolve_chunk_progress` being the single progress answer.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` (§ Direction — every fact has one
  home), `.prawduct/artifacts/nonfunctional-requirements.md` (§ Direction — proportionality
  ratchets both ways)
- **Deliverables:**
  - **#201** — `plugin/lib/views.py`, `plugin/lib/buildplan_refs.py`. **The item is stale in one leg;
    verified against the code 2026-08-01, and the builder must re-verify rather than trust either
    reading.** Leg status as of `ddb6dd1`:
    - **Leg 2 — the frontmatter filter — has ALREADY LANDED.** `_declares_non_build_plan_artifact`
      excludes files declaring a non-`build-plan` artifact type, mirrored at both sites, added
      2026-08-01 after a scope-tagged collapse-map artifact stopped `regen-views` writing views for
      every scope. **Do not rebuild it.** One residual is deliberate and stays: a file declaring *no*
      `artifact:` key at all is still treated as a plan, because excluding it would silently drop a
      real plan predating the convention.
    - **Leg 1 — recursive discovery — is live.** Both sites are still `artifacts_dir.glob("*.md")`
      (`plugin/lib/views.py` `build_scope_to_plan_map` and `diagnose_scope_plan_coverage`), so nested
      plans are invisible and the directory is not configurable. Four surveyed repos carry 16 nested
      plans each.
    - **Leg 3 — the chunk-line matcher — is live.** `CHUNK_LINE_RE` still pins the colon form with no
      tolerance for `**` or an em-dash, so those checkboxes can never flip. Answer it *together with*
      #211: one contract, one home.
    - **Leg 4 — decoupling — is live, and was a ruling, not a defect fix. RULED 2026-08-01:
      `regen-views` is advice and fails soft per view** (see § Requirements Confidence and
      `learnings.md` [[regen-views-is-advice]]). Build it as: errors partition by the view they can
      affect. `diagnose_scope_plan_coverage`'s errors are scope-local — they suppress only that
      scope's `## Status` view; release-notes and scope-rollups have no plan-roster dependency and
      are still written. `validate_status_values` and `validate_tag_conflicts` stay fatal for the
      views they touch, because a typo'd `status=` means an entry never contributes its flip, which
      IS a half-right Status view. Exit non-zero whenever any view was suppressed — soft is not
      silent. The trap the item names is real either way: prawduct's own error message tells the
      user to set `views_enabled: true`, which on a 16-nested-plan repo fails closed on everything.
  - **NEW — collapse `regen-views` to one mode (owner requirement 2026-08-01, not from #201).**
    `plugin/bin/prawduct-hook`. Views always regenerate; there is no dry run. Same edit to the same
    error block as leg 4, which is why it lands here rather than in its own chunk. Three things to
    get right: (a) **`--check` is DEPRECATED, not deleted** — see the [DECISION] below; it prints a
    stderr deprecation notice and performs the full regen, so the mode collapses while the flag
    survives one cycle per `api-contract.md`'s deprecation norm; (b) an **unknown flag must exit 2**
    — today `check_only = "--check" in (args or [])` ignores every other argument, which already
    violates `api-contract.md:223` (*"unknown flags rejected with a usage error (exit 2)"*), so this
    is conformance, not a new control; (c) the **doc cascade is larger than the code change** and is
    part of this deliverable, not follow-up: `documentation/release-process.md` (steps at :101 and :154),
    `.prawduct/artifacts/kernel-inventory-2026-07-12.md:45` (the row records `--check` as a HARD
    kernel gate), `learnings-detail.md:615` and `:631` (both prescribe verifying with `--check`),
    `.prawduct/artifacts/change-log-ledger-design.md:266,277` (a *future* design that plans to
    assert byte-identity via a non-writing check — it needs a different mechanism, and saying so is
    in scope; building it is not). **Out of scope and deliberately not edited:
    `.prawduct/artifacts/build-plan-v3.2.0-golive.md:743`** — it belongs to the primary checkout's
    active plan; flag it in the handoff for that worktree instead. Historical release plans
    (v3.1.1-hotfix, v3.2.1, backlog-service-golive, single-pr-bookkeeping, backlog-rework) are
    records of what was done and are **not** rewritten.
  - **#211** — `tests/test_build_plan_resolution.py`: widen `_parseable_body_chunk_ids` to match
    production (`##` or `###`, and any of `: — – ( -` or end-of-line). **Do not narrow
    `_CHUNK_ID_SEP` to match the stale test** — that re-breaks the em-dash research-plan form on
    purpose enabled earlier. If the widening lands alongside #201's matcher, state in the docstring
    which module owns the contract and cite it rather than restating it.
  - **#224** — `plugin/lib/buildplan_refs.py`: the `new` forward-ref exemption expires when the chunk
    completes. Two edges the item names: (a) checkboxes are a derived view that stays `[ ]` on a
    feature branch, so re-derive against `resolve_chunk_progress`, not "first unchecked box", and
    fail *toward* the exemption when completion is uncertain; (b) the qualifier currently matches
    `new` before any backticked path including adjectival prose, so constrain the match to sit inside
    a Deliverables list item at the same time.
  - **#327** — `plugin/lib/buildplan_refs.py`: announce a degraded git-derived chunk reading,
    narrowed to `views_enabled` true **and** the git path bailed. Reporting the `views_enabled`-unset
    case is pure noise. **The fix is not a diagnostic at the failure point** — `_git_aware_progress`
    is on the SessionStart/Stop hot path. Pick a deliberately-invoked surface (`handoff preview`,
    `verify-chunk-refs`, or the briefing's Resume line). `has_status_items=False` already
    distinguishes "no plan" from "plan read, git path bailed" with no new plumbing.
  - **#333** — `plugin/lib/buildplan_refs.py`: `_GIT_REF_PREFIXES` covers Conventional-Commits
    (`feat/`, `chore/`, `refactor/`, `perf/`, `ci/`, `wip/`) and bot prefixes (`dependabot/`,
    `renovate/`) — or, better, is replaced by a shape rule that does not require guessing a repo's
    conventions. `missing-ref:` is BLOCKING in `plugin/skills/critic/review-protocol.md`, so every
    consumer not on git-flow currently gets a spurious blocking finding.
- **Tests:** unit — the widened heading matcher against both hash depths and all five separators;
  exemption expiry across an open chunk, a completed chunk, and an *uncertain* completion (must fail
  toward the exemption); the degraded-reading notice fires on `views_enabled` + git-bail and stays
  silent on `views_enabled` unset; each new branch prefix parses as a ref, not a path; `--check` is
  gone and an unknown flag exits 2. Integration — `regen-views` completes release-notes and
  scope-rollup regeneration with one scope unresolvable, exiting non-zero while having written both;
  and a typo'd `status=` fails the run CLOSED (exit 2, nothing written) rather than suppressing one
  view — an entry that cannot be interpreted would leave a Status view half-right, which is the bug
  class the per-view rule exists to preserve, so it is deliberately NOT scope-local. **Existing `--check` tests
  (`tests/test_views.py`, `tests/spikes/change_log_roundtrip.py`) are rewritten against the single
  mode, not deleted** — each one asserts a validation behaviour that must survive the collapse.
- **Acceptance criteria:** `python3 plugin/bin/prawduct-hook verify-chunk-refs` and `regen-views` both
  behave as specified against this repo; full suite green.
- **Done when:**
  0. **DONE 2026-08-01.** The authority-vs-advice ruling on #201's decoupling leg is recorded —
     before that leg's code. `learnings.md` + `learnings-detail.md` [[regen-views-is-advice]],
     `Rulings:` on both colliding norms, `[DECISION: …]` ×2 in § Requirements Confidence
  1. Acceptance criteria met and tests pass
  2. #327's expected yield is stated in the change-log entry and the notice is countable, per the
     proportionality norm — a control whose findings are printed and forgotten can never be retired
     on evidence
  3. `python3 plugin/bin/prawduct-hook critic-begin --mode chunk --scope backlog-burndown --chunk 02`,
     review run, blocking findings resolved
  4. Committed with a change-log entry tagged `scope=backlog-burndown`

### Chunk 03: Critic dispatch anchoring and review-record attribution

- **Description:** Five defects in which tree a review looks at and which plan the record says it
  reviewed. #206, #288 and #218 are all inside `plugin/lib/critic_mode.py` and
  `plugin/lib/critic_consolidate.py` — #218 is explicitly a rider on #288's function. #208 and #344
  are the two halves of one attribution failure, and #208's own evidence names #344 as its narrow
  leg, not its replacement. This chunk also removes the operating rule this plan runs under.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` (§ Direction — authority fails
  closed), `.prawduct/artifacts/data-model.md` (§ Direction — no model in a fact's write path)
- **Deliverables:**
  - **#206** — `plugin/lib/critic_consolidate.py`: `verify-resolutions` intent is detected by **tree
    inequality** (prior `head_tree` != capture `head_tree`), not by the commit set. Today a commit
    that merely materializes the already-reviewed tree moves the anchor to committed HEAD while the
    delta computes empty, so the refusal reads *"everything is reviewed"* when it means *"everything
    I chose to look at is reviewed"*. Fix the message too — it is silent in the direction that loses
    governance.
  - **#288** — `plugin/lib/critic_mode.py`: require a review anchor to be an ancestor of HEAD
    (`git merge-base --is-ancestor <anchor> HEAD`), failing **closed** — exit 1 and any other failure
    both demote to cumulative/final. `_commit_resolves` succeeds for any object including a sibling
    tip. **The item's "zero occurrences of `is-ancestor` anywhere under `lib/`" is stale** — verified
    2026-08-01: `plugin/lib/coverage.py` and `plugin/lib/briefing.py` both run it already. Reuse
    their invocation shape rather than minting a third; the gap is in `critic_mode.py` specifically. **Port caveat:** do not restore `gates._compute_verify_resolutions_scope`; it was deleted in
    the kernel-v3 cutover and is asserted-absent by a stays-deleted pin in
    `tests/test_cumulative_gate.py`. Redirect that half to `critic_consolidate._prior_review_fact`.
    Keep the ported test pattern that asserts the *old* guard would have passed. This does **not**
    close the same-lineage cross-bundle chain folded into it — that case has the anchor genuinely an
    ancestor of HEAD, so an ancestor guard passes it; say so rather than claiming closure.
  - **#218** — `plugin/lib/critic_mode.py`: the rule-1 docstring names `_verify_resolutions_gate_check`,
    deleted in the same cutover. Repoint at `plugin/lib/coverage_algebra.py`'s `coverage_verdict` or
    `critic_consolidate._prior_review_fact`, or drop the mirror clause. Lands as a rider on #288
    because it sits in the function #288 edits.
  - **#344** — `plugin/lib/critic_consolidate.py`, `plugin/lib/record_lint.py`: thread `scope` into
    `lint_records` / `lint_records_safe` — it is already a live local in `begin_review` and is written
    into the manifest eighteen lines below the call that omits it — and prefer the scope-named plan
    over the `active_build_plan` pointer. When the two **disagree** that is the `unchecked` case, not
    a silent grade of whichever won. **The counters must say so:** four zeros currently read
    identically to a clean check, and five consecutive reviews had those zeros quoted as "0 findings"
    by readers who did not read the caveat line above them.
  - **#208** — `plugin/lib/critic_mode.py`: inference checks for a non-empty interval before returning
    a working-tree-scoped mode, and rule 4 confirms the plan relates to the branch's changes. The
    wider blast radius is records, not mode: an unbounded pointer has attributed a manifest, a review
    fact and a ledger event to an unrelated plan on three observed occasions. **"Clear the pointer" is
    not the fix** — the pointer was correct each time.
  - **Design decisions taken at build time.** The acceptance criterion ("the record names
    `backlog-burndown` *without* `--scope`") requires a scope the dispatch was not given, and #344's
    two sentences — *prefer the scope-named plan* and *disagreement is the `unchecked` case* — read
    as contradictory until you separate "which plan do I grade" from "what do I say about it". Both
    resolutions are recorded here rather than inferred from the diff:
    [DECISION: scope, when the dispatch omits it, is inferred from the branch name — its last
    segment, accepted ONLY when it matches a `scope:` that some build plan in the artifacts
    directory actually declares **and that plan still has an unchecked chunk** | it is a *match
    against declared data*, not a guess: `fix/backlog-burndown` → `backlog-burndown` →
    `build-plan-backlog-burndown.md`. A branch whose name matches nothing (the primary checkout on
    `develop`) infers nothing and keeps today's behaviour exactly. The liveness clause was added
    after Critic finding R-6: a long-lived repo accumulates dozens of finished plans, and without it
    a branch named `fix/gate-noise` would attribute to one of them and could raise a BLOCKING
    `chunk-ref-missing` about its deliverables. **"Finished" is sharp only under `views_enabled`**,
    where boxes flip at release; elsewhere they flip per chunk, so a plan reads finished from its
    last tick until merge and attribution falls back to the pointer for that window — a lapse of
    the improvement rather than a new defect, stated here because a vetoable record that is one
    qualification behind the code is what the owner would be vetoing. **The residual case, stated rather than
    waved at:** a branch whose name matches an *unfinished* plan it is not building will be
    attributed to that plan. A name is the only signal available, so nothing here can tell those
    apart; the remedy is explicit `--scope`. An earlier draft of this block claimed the inference
    "can only ever ADD attribution, never redirect it" — that is true of the no-match case only, and
    the Critic caught the justification being stronger than the code. Alternatives rejected: parsing
    the branch's change-log `scope=` tags (sounder, but an 830KB parse on an inference path), and
    repointing `active_build_plan` (#344's own evidence says the pointer was correct) | user can veto]
    [DECISION: a resolved scope-named plan is GRADED, and the `unchecked` case is reserved for a
    scope that resolves NO plan | "prefer X" and "disagreement is unchecked" cannot both hold of the
    same case. Preferring the scope-named plan means the pointer is simply not the subject — there is
    no ambiguity left to report, and `plan_graded` now names the file so the choice is legible in the
    record. What IS unresolvable is a dispatch naming a scope no plan declares: falling back to the
    pointer there is exactly the silent grade of another plan this item was filed for | user can veto]
    [DECISION: `counts[check]` is `None` when the check produced no answer and an integer when it
    ran — and `chunk-ref-missing` is `None` exactly when `chunk_graded` is `None`, so the two fields
    stop disagreeing | this is the counters half of the ask. No new `chunk-ref-missing unchecked —`
    line is emitted for the ordinary no-chunk review: `review-cycle.md` grades that prefix BLOCKING,
    and it names that exact false-blocker ("a branch that builds no chunk has no `--chunk` to
    supply"). The null counter carries the honesty; the severity vocabulary is untouched | user can veto]
    [DECISION: rule 4 confirms the plan relates to the branch when it CAN, and declares the
    assumption in its rationale when it cannot — it never declines on an unconfirmable pointer | a
    branch whose name matches a declared scope grounds inference on THAT plan (strictly better than
    declining to `final`, and it makes mode inference and the record agree on the subject). A branch
    that matches nothing cannot be shown unrelated either, and declining there would demote every
    ordinary repo whose branch names differ from its scopes. The rationale lands in `mode_chosen_by`,
    which is the observable-yield channel `nonfunctional-requirements.md` § Direction requires of a
    new control | user can veto]
- **Tests:** unit — tree-inequality intent detection across the vouching-commit flow; ancestor guard
  proving `_commit_resolves` is True while the ancestor check is False before asserting the demote;
  scope disagreement yields `unchecked` with counters that differ from a clean check; rule 4 declines
  on an unrelated plan and on an empty interval. Integration — a `verify-resolutions` dispatch over a
  dirty tree containing unreviewed work no longer exits 1.
- **Acceptance criteria:** run the review of this very chunk **without** `--scope` and confirm the
  record now names `backlog-burndown` rather than the golive plan; full suite green.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. The Verification Strategy's operating rule is struck — record that the explicit-`--scope`
     workaround is no longer required, and why
  3. `python3 plugin/bin/prawduct-hook critic-begin --mode chunk --chunk 03`, review run, blocking
     findings resolved. **No `--scope`** — passing it here would contradict the acceptance
     criterion directly above, which is that this very review resolves the scope without it.
  4. Committed with a change-log entry tagged `scope=backlog-burndown`

### Chunk 04: The independent tail

- **Description:** Five small items that share no surface with each other — which is exactly why they
  are batched last: no ordering constraint among them, and one review pass covers all five. Two are
  hardening, one closes a norm's outstanding residue, one is a counting defect, and one publishes an
  already-depended-on constant as a supported surface.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `.prawduct/artifacts/observability-strategy.md` (§ Direction — the
  no-internal-identifier norm this chunk closes), `.prawduct/artifacts/api-contract.md` (§ Direction
  — additive-first evolution)
- **Deliverables:**
  - **#307** — `plugin/lib/evidence.py`: shape-validate tree SHAs at the read/compose boundary against
    `^([0-9a-f]{40}|[0-9a-f]{64})$` before they reach git argv. A non-conforming SHA is treated like
    any malformed fact — it **weakens coverage** (yields no edge) and never crashes the gate. Not an
    active hole: argv is list-form with no shell, so the exposure is git option injection or confusing
    failures.
  - **#209** — `plugin/bin/prawduct-hook` (`cmd_clear`'s critic-active refusal),
    `plugin/lib/backlog/cli.py` (the `_HELP` `reconcile-labels` and `import` lines),
    `plugin/lib/critic_consolidate.py` (`validate_partial`'s waived-disposition error): replace each
    prawduct-internal id in operator-facing text with the plain-language reason it stood for; the id
    stays in the adjacent comment or docstring, which the norm permits. Anchored by symbol, not line
    number — the original line anchors rotted within a day. Closing this records that ongoing
    enforcement is the Critic's judgment, not a regex: prefixes are open-ended, so the sweep heuristic
    is not exhaustive.
  - **#313** — `plugin/lib/backlog/transport.py`, `query.py`, `migrate.py`, `core.py`: extract one
    shared issue-list paginator to replace the four near-identical loops and converge their bounds, so
    there is one place to fail loud instead of four divergent caps. A cap trip raises an attributed
    `TransportError(unavailable, 'result truncated at N pages')` or surfaces through the envelope —
    today `export`, which is the backup path, cannot distinguish truncated from complete.
  - **#532** — the backlog counting path: stage-less items are counted as open and surfaced as an
    explicit untriaged bucket, the same surface-by-exception posture `/prawduct:doctor` uses. An
    untriaged item must be *louder* than a triaged one, never quieter. `counts` already prints a
    `(none)` stage bucket for the whole corpus, so the information sits one line from the undercount
    it causes. **Collision constraint:** land the fix in the backlog query layer. `plugin/lib/briefing.py`
    is dirty on `feature/upgrade-discovery-relay` in the primary checkout — if the briefing surface
    must change, coordinate with that session first rather than editing it here.
    [DECISION: #532 changes the value `open` reports for an unchanged corpus (158 → 167 on this repo)
    without renaming the key | the key's documented meaning is "open items" and the defect was that
    the value did not match it — this restores the contract rather than repurposing it, and the
    alternative (a new key beside a knowingly-wrong one) leaves the wrong number as the default read
    | user can veto]
  - **#533** — `plugin/bin/prawduct-hook`, `plugin/lib/migrate_plugin.py`: publish `INSTALL_REFERENCE`
    as a stable surface via a `print-install-reference` subcommand emitting the dict as JSON on
    stdout. It is the canonical statement of how a repo references the plugin, and it is a *private
    module constant with no published form* — so two independent external consumers arrived at
    AST-parsing it within a week of each other, one of them the tool that repaired the fleet after a
    transcribed copy went stale. Both chose parsing over transcribing deliberately, because a copy
    drifts silently; the fragile workaround is the only safe option currently offered. Today's
    stability is an argument from **coupling, not promise** (`init_product.py` imports it, so a rename
    breaks prawduct's own code), which is fine to rely on informally and not something to build a
    fleet's install-correctness on. The subcommand is the cheapest of the three shapes the filer
    proposed and their stated preference: no new file, and introspectable from a repo that has the
    plugin installed but not vendored — the normal case. Lands as a new **Exposed API** row in
    `api-contract.md`, since publishing it is the entire point and an unlisted public command is the
    same defect one layer out. Added 2026-08-01 at owner request; the marketplace `ref` and
    `autoUpdate` values ship exactly as the constant holds them — this publishes the value, it does
    not re-decide it.
  - **Scope-out, stated so it is not silently dropped:** backfilling stage labels on the 64 stage-less
    **closed** items. They are already dispositioned and do not affect the pending figure.
- **Tests:** unit — a malformed SHA in a fact produces no edge and no traceback; the shared paginator's
  cap trip raises rather than returning a prefix, across all four call sites; stage-less items appear
  in the open count and in an untriaged bucket; `print-install-reference` emits JSON that round-trips
  to `INSTALL_REFERENCE` **by comparison against the constant, never against a transcribed literal** —
  a copy in the test is the same drift the item was filed about. Preferences — the
  no-internal-identifier guard, if one exists, still passes over the four edited sites.
- **Acceptance criteria:** `python3 plugin/bin/prawduct-hook backlog counts --repo brookstalley/prawduct`
  reconciles against `gh issue list --state open` exactly; the four operator-facing strings read as
  plain language; `print-install-reference | python3 -c 'import json,sys; json.load(sys.stdin)'`
  succeeds and its output equals the constant; full suite green.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then
     `python3 plugin/bin/prawduct-hook critic-begin --mode cumulative --chunk 04`,
     review run, blocking findings resolved. (`--scope` is no longer passed — Chunk 03 made the
     branch name derive it; see the struck operating rule in § Verification Strategy.)
  3. Each of the seventeen items closed via `/prawduct:backlog update <owner/repo#number> status=shipped`
     — the full id form is required; a bare number errors
  3b. **Reply on #533** once it lands: the filer offered to send the PR and asked to be told, and has
     two call sites plus a downstream contract test to retarget the day it ships. A published surface
     nobody is told about leaves both consumers on the AST-parsing workaround this closes.
  4. Change-log entries tagged `scope=backlog-burndown`, then `regen-views`

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run the hallucinote owner-gate exercise against a runbook whose Stage 4→6
ordering is correct and whose cutover leaves a source file that announces it is dead — the two
things that exercise would otherwise have failed to confirm.

## Governance Checkpoints

1. **After Chunk 01** — the batch's first review under the explicit-`--scope` operating rule.
   Confirm the record names `backlog-burndown`. If it does not, the workaround is insufficient and
   Chunk 03 moves ahead of Chunk 02.
2. **After Chunk 03** — attribution is fixed; confirm against a review dispatched *without*
   `--scope` before relying on it, and strike the operating rule only after that passes.
3. **Chunk 04 cumulative** — the whole-bundle pass that also gates `/prawduct:pr create`.

## Status

<!-- Derived view (`views_enabled: true`). Mark a chunk shipped by adding a change-log entry
     tagged scope=backlog-burndown / status=shipped, then run regen-views.
     Do NOT hand-flip the checkboxes. Stays [ ] on this branch until the release ships. -->

- [ ] Chunk 01: The migration runbook's two operator-facing defects
- [ ] Chunk 02: Plan discovery and plan reading
- [ ] Chunk 03: Critic dispatch anchoring and review-record attribution
- [ ] Chunk 04: The independent tail
Context: Plan authored 2026-08-01 on `fix/backlog-burndown`, from a re-derivation of the 168 open
tracker items by `refs:` co-location. **Chunks 01, 02 and 03 are built, reviewed and committed**;
Chunk 04 is next, and now carries a fifth item (#533, added at owner request).
`active_build_plan` still points at `artifacts/build-plan-v3.2.0-golive.md` and **must not be
repointed** — that plan is in progress in the primary checkout, the pointer is single-slot, and
repointing was the wrong fix for the attribution defect Chunk 03 closes by resolving *around* it.
**Dispatch with `--mode <m> --chunk NN`, and NOT `--scope`** — Chunk 03 made the branch name derive
it, and this line prescribing the old workaround is what the Critic caught twice; see
§ Verification Strategy for what still binds and why. Next: Chunk 04.
