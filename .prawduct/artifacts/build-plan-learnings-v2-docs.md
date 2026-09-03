---
artifact: build-plan
version: 2
scope: learnings-v2-docs
branch: feature/learning-system-v2
backlog: brookstalley/prawduct#744
depends_on:
  - artifact: learning-system-v2-discovery
  - artifact: learning-system-audit-2026-09-01
  - artifact: build-plan-learnings-v2-core
  - artifact: build-plan-learnings-v2-delete
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: the version moves once, at the release, across the three mirrored files; nothing here touches a persisted schema"
      - "exit codes are the contract; stable severity prefixes; errors attributed → inapplicable because this plan changes no command's behaviour (code directives print text at an existing site with an existing exit code)"
      - "additive-first evolution; deprecation signalled, removal at a major → conforms: R13 records the two ADDED verbs (`learnings-migrate`, `learnings-files`) in § Operations and the stability tier they sit in; the three retired verbs were recorded as deprecated-inert in Wave 2"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative: a small feature is a patch bump, not a minor-per-feature → ruling needed: the discovery's D1 argues minor (a consumer's repo is rewritten on first session; four verbs and a skill removed; a Stop gate widened) and the norm argues patch; the release chunk frames it and the owner decides before the cut, recorded in the release plan as v3.4.0's was"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in a fact's write path → inapplicable because this plan writes no facts"
      - "facts immutable and append-only → inapplicable"
      - "derived views never authoritative → conforms: the discipline table in `docs/discipline.md` is a hand-authored record of where each rule was delivered, and nothing derives from it"
      - "a governance document reaches a terminal state, never deleted; archival moves it → conforms: the release ARCHIVES the three wave plans through `plan-backfill`, never deletes them"
      - "every backlog write conforms to the title rules → conforms: the release chunk's three filings for #661's sub-findings go through `/prawduct:backlog add`, which enforces them"
      - "a fact written by a newer schema is a loud block → inapplicable"
      - "two stores, two lifetimes → conforms"
      - "backlog_service_repo selects the authoritative store → inapplicable"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with the channel split → conforms: a code directive added at an action site prints on the channel that site already uses"
      - "the governance ledger has a single writer → inapplicable because nothing here writes the ledger"
      - "no prawduct-internal identifier in text emitted into a governed product → conforms: directive text names actions, never ids; the discipline table cites items on the non-emitted side"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable"
      - "authority fails closed; advice fails soft → inapplicable because no gate changes"
      - "local-first → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "never specific to Python → conforms"
      - "prawduct guides and reviews; it never implements → conforms: this wave IS the guidance"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "every fact has one home; every other mention is a reference → conforms, and this wave enforces it on itself: the standing-block specification moves to ONE new home (`methodology/session-hygiene.md`) and every surface that carried it becomes a pointer; the write-path model has one home (`reflection.md`) and the digest's R10 line points at it; each discipline rule gets exactly one delivery surface, recorded in the table"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms: the ten discipline rules are curated by the framework into its own surfaces, never read from a product's corpus at runtime"
      - "a destructive or irreversible operation requires owner approval at the operation level → conforms: the release cut (tag, GitHub Release, promotion to `main`) is outward-facing and irreversible in the consumer fleet, so Chunk 05 stops for the owner's one informed confirmation naming the version and the promotion shape before Phase 2 runs"
      - "no content egress → conforms: the GitHub Release carries this repo's own CHANGELOG section"
partition: >-
  Serial, coordinator only — docs are one voice, and three of the five chunks edit the digest,
  `reflection.md` or the Critic prose files, every one of which sits at or within a few tokens of
  a ceiling that a second author would blow blind; Chunk 04 is the program's PR and Chunk 05 the
  release, both the coordinator's by definition. Precedent: the discovery §8.2 drew Wave 3 serial
  for exactly this reason; Wave 2's parallel run cost five integration seams in prose nobody owned.
last_validated: 2026-09-03
---

## Requirements Confidence

**Level:** Medium

**Why:** R8, R10, R13 and D2 are High — the rewrite target (`reflection.md`, 5,003 tokens, ~60%
standing-block spec) and every test that pins it were read before the chunk was drawn, and the
release follows a runbook this repo has run fourteen times. R12 is Medium: the discovery names
the ten rules and three delivery channels but leaves the per-rule choice to the plan, and two of
the three prose channels (`goals-1-3.md` at 2276/<2278, `review-cycle.md` at 9596/<9597) have no
headroom, so the choice is budget-shaped and each raise must be declared with its reason. D1 is
the owner's: the version decision is framed at the cut, not assumed.

**Open assumptions / unknowns:**

[ASSUMPTION: the standing-block specification moves whole to `methodology/session-hygiene.md`
and `reflection.md` keeps only the work-cycle-boundary close steps and a one-line pointer | MED
impact — six tests pin `reflection.md` as the canonical carrier and all six are renegotiated in
the open to the new file | user can override: keep it in `reflection.md`]

[ASSUMPTION: a `/prawduct:methodology session-hygiene` topic is added so the moved guide has a
reader; the digest's topic list and the skill's routing table each gain one entry | LOW impact |
user can override with a different topic name]

[ASSUMPTION: R12's ten rules are delivered as code directives wherever the rule has a MOMENT a
plugin command runs at, and as Critic-goal or methodology sentences only where no such moment
exists — the discovery's own delivery evidence (audit §3.2) is that code directives fire and
always-loaded prose does not | MED impact — it decides which ceilings are touched | user can
override per rule]

[ASSUMPTION: the version is 3.5.0 (discovery D1, minor) — framed for the owner at the cut, and
`gates.json`'s three `since: "3.5.0"` rows are rewritten if the owner chooses otherwise | HIGH
impact on the cut, none on the build | user decides]

**What would raise confidence:** the owner's version call; it is asked at Chunk 05, where it
is needed, and nothing before it depends on the answer.

## Status

- [ ] Chunk 01: `reflection.md` rewritten to the write-path model; the standing block moves to its own guide
- [ ] Chunk 02: Digest line, contract records, and the residue the two earlier waves left in prose
- [ ] Chunk 03: The discipline seed — ten cross-repo rules delivered where rules fire, recorded in one table
- [ ] Chunk 04: The program's PR to `develop` — its cumulative review is the gate
- [ ] Chunk 05: Release — plan, version, cut, verify, reopen `develop`
Context: Plan drawn 2026-09-03 from the tree at f2dffc6b (Wave 2 complete). Next: Chunk 01.

## Scaffolding

### Project Initialization

None. New files: `plugin/methodology/session-hygiene.md`, `plugin/docs/discipline.md`.

### Dependencies

None added.

### Build & Test Configuration

`uv run pytest -q` runs the suite; invoke the evidence recorder as `uv run python
plugin/bin/prawduct-hook test-evidence record` (the bare `python3` is a different interpreter on
this box). Prose chunks are verified by `tests/test_v5_methodology.py`,
`tests/test_plugin_methodology_digest.py`, `tests/test_v5_templates.py`, `tests/test_plugin_runtime.py`
(the skill's namespaced forms) and `tests/preferences/`; every pinned file's `LAST_MEASURED_TOKENS`
reading moves in the same commit as its edit, ceilings ratchet with cuts and are raised only by
declaration, and the digest's character count stays under 9,500 working (10,000 hard).

### Scaffold Verification

Not applicable.

### Verification Strategy

Beyond tests: after Chunk 01, `/prawduct:methodology session-hygiene` in a fresh session opens
the moved guide, and `/prawduct:methodology reflection` reads as the learning loop and nothing
else. After Chunk 03, each code directive is observed live at its action site in this worktree
(the repo-local hook). After Chunk 05, the next session against the new `main` shows the
version-delta banner naming the release and announcing the three learnings gates.

## Project Structure

```
plugin/methodology/reflection.md          # rewritten: the learning loop and the write path (01)
plugin/methodology/session-hygiene.md     # NEW: the standing block, forward notes, clear verdict (01)
plugin/methodology/session-digest.md      # R10 line; pointer to session-hygiene; topic list (01, 02)
plugin/skills/methodology/SKILL.md        # + session-hygiene topic (01)
plugin/docs/discipline.md                 # NEW: the ten-rule delivery table (03)
plugin/docs/norms.md                      # learnings cross-links repointed (02)
plugin/skills/critic/review-cycle.md      # rule-unit sentence stated from the writer (02); R12 sentences if any (03)
.prawduct/artifacts/api-contract.md       # R13: the added verbs and the contract narrative (02)
.prawduct/artifacts/release-plan-v3.5.0.md  # NEW at the cut (05)
tests/test_v5_methodology.py, tests/test_plugin_methodology_digest.py, tests/test_v5_templates.py
```

### Module Boundaries

`reflection.md` owns the learning loop and the write path; `session-hygiene.md` owns the
standing block and the forward notes; the digest carries one pointer to each and restates
neither. `docs/discipline.md` is the record of where each portable rule lives; the rule itself
lives at exactly one delivery surface.

## Build Chunks

### Chunk 01: `reflection.md` rewritten to the write-path model; the standing block moves to its own guide

- **Description:** R8 and D2 together, because the rewrite is only readable once the ~60% of the
  file that is session-hygiene spec has left it. The learning loop is written to the model the
  two earlier waves built; the standing block gets a home whose name says what it is.
- **Depends on:** none
- **Artifacts consumed:** discovery R8, §7 D2; audit §5 Principles 1, 4, 5 and §3.4; backlog #347
  (both limbs: consolidation is merge-or-delete under the budget, and a rule carries its
  instances inline because the file that fires is the only one read at the moment); the
  ratified single-resolver allowlist entries for `reflection.md` and `norms.md`.
- **Deliverables:**
  - new `plugin/methodology/session-hygiene.md`: the standing-block specification moved from
    `reflection.md` — the shape, the three lines and what each owes, precedence, the live-review
    and ad-hoc-delegate clear verdicts with their deadline derivation, the findings-only rule,
    write-before-the-wait, should-you-clear, the three failure modes, the label procedure, and
    "Forward notes are not a reflection". Moved, not rewritten: every pinned phrase survives
    verbatim (the tests below are the list). Opens with two sentences saying what the file is and
    that `reflection.md` sends readers here from its work-cycle-boundary step.
  - `plugin/methodology/reflection.md` rewritten (target: the file halves): When to Reflect
    (unchanged in substance; the gate sentence already states the new predicate); the process
    steps 1–5 and 7 kept; Step 4 Capture rewritten to the routing model — an **episode** goes to
    `.session-reflected` in the gate's shape; a **rule** goes to `core.md` if cross-cutting or to
    the area file whose `paths:` cover it, stated as a heading that carries the rule, its why and
    the instance that earned it (inline — the file that fires is the only one read at the
    moment); **framework friction** goes upstream through `/prawduct:report-bug` and is never a
    product rule; **portable discipline** is NOT written — say in the reflection why it is
    portable, because the framework curates those (`docs/discipline.md`); the **budget and the
    payment rule** in two sentences (over and grown blocks the next addition; pay from a genuine
    duplicate or raise with a reason, never trim a rule to fit); the descent obligation is
    referenced as living in `core.md`'s header, not restated. Step 6 keeps the persistence,
    deferred-work and backlog-hygiene text and the four close steps, and replaces the
    standing-block body with one pointer sentence to `session-hygiene.md`. "Learning Lifecycle"
    rewritten to audit Principle 4 (provisional → confirmed → incorporated as the ONLY growth
    path; a rule violated twice becomes a test, a hook check, a Critic goal or a methodology
    sentence and is then deleted; git is the history). "Managing Learnings Over Time" deleted —
    its two-file model is gone; what survives of it is the one-sentence budget rule above.
    "Framework Reflection" and "Post-Fix Reflection" kept; the product-feedback sentence names
    `.claude/rules/learnings/`. No `learnings.md`, `learnings-detail.md`, `learnings-history.md`
    or `audit-learnings` anywhere in the file when done.
  - `plugin/methodology/session-digest.md`: the "Close with the standing block" bullet's pointer
    becomes `methodology/session-hygiene.md`; the "Read on demand" topic list gains
    `session-hygiene`. Charged to both digest shapes; paid in place if the bullet can lose a
    clause the new guide now owns, else declared.
  - `plugin/skills/methodology/SKILL.md`: a `session-hygiene` topic row; `building.md`'s pointer
    (`methodology/reflection.md` "Work cycle boundary") repointed to the new guide.
  - `plugin/docs/norms.md`: the norms-are-statute / learnings-are-case-law cross-links stop naming
    `learnings.md`; the allowlist entries for `reflection.md` and `norms.md` deleted (the last two
    `wave-3` entries — the test names any survivor).
  - `tests/test_v5_methodology.py`: a `LAST_MEASURED_TOKENS` reading for the new guide (on-demand
    class: reading, no ceiling) and the moved reading for `reflection.md`; every pin that names
    `reflection.md` as the standing block's canonical carrier repointed to `session-hygiene.md`
    (`test_standing_block_is_on_every_surface_that_claims_it`, the live-review clear pins, the
    axis/precedence pins, the write-before-the-wait pin, `building.md`'s pointer assertion);
    `test_reflection_learning_lifecycle` and `test_cross_references` renegotiated in the open —
    each asserts `.claude/rules/learnings/` where it asserted the deleted files, with the reason
    in the test; `TestMethodologyProseHygiene.METHODOLOGY_GUIDES` gains the new guide.
    `tests/test_plugin_methodology_digest.py` `PHASES` gains the topic. `tests/test_plugin_runtime.py`'s
    namespaced-forms pin still holds.
- **Tests:** the files above; `tests/preferences` (the allowlist shrinks to `learnings_migrate.py`
  and `prawduct-hook` at `none`); a new positive pin that `reflection.md` names all four routes
  (episode / rule / upstream / not-written) and the payment rule, and that `session-hygiene.md`
  carries the standing block's shape.
- **Acceptance criteria:** `uv run pytest -q tests/test_v5_methodology.py
  tests/test_plugin_methodology_digest.py tests/test_v5_templates.py tests/test_plugin_runtime.py
  tests/preferences` passes; `grep -n "learnings.md\|learnings-detail\|learnings-history\|audit-learnings\|reflections.md" plugin/methodology/reflection.md plugin/methodology/session-hygiene.md plugin/docs/norms.md`
  returns nothing; the live check (both topics open in a fresh session) done.
- **Type:** doc-only
- **Critic mode:** final (reviewed in Chunk 04's cumulative — see the decision there)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status (review lands in Chunk 04)

### Chunk 02: Digest line, contract records, and the residue the two earlier waves left in prose

- **Description:** The small, exact edits that make the shipped prose true of the shipped
  code: R10's one digest sentence, R13's api-contract rows and narrative, and three residues the
  Wave 1 and Wave 2 handoffs named.
- **Depends on:** Chunk 01 (the digest's budget is settled there first)
- **Artifacts consumed:** discovery R10, R13; audit §3.6 (the harness-memory overlap R10
  answers); the Wave 1 and Wave 2 handoff notes' release-debt lists; `api-contract.md`
  § Operations and § Surface Inventory; review rev-…f97fa40b's accepted R-5 and R-16.
- **Deliverables:**
  - `plugin/methodology/session-digest.md`: one sentence — the harness's auto-memory holds no
    project state or product rules; `.prawduct/` and `.claude/rules/learnings/` are authoritative.
    A new framework-wide default lands in the digest (this repo's own learning); paid in place or
    declared with its reason, under both shape ceilings and the 9,500-character working budget.
  - `.prawduct/artifacts/api-contract.md`: § Operations rows for `learnings-migrate` (mutating,
    `--apply`-gated, repo lifecycle) and `learnings-files [--for-diff] [--json]` (read-only); the
    stability tier for `learnings-files`, which three `allowed-tools` lists now bind; and the
    contract-change narrative for the program — three verbs deprecated-inert, two added, the
    learnings layout moved, `ledger-append` refusing `learning.*`, `review-stats` schema 2 —
    with the deprecation norm's Why engaged. § Direction is NOT edited (R-16's wording is the
    owner's; recorded in the handoff for their call).
  - `plugin/skills/critic/review-cycle.md` § Learnings Cross-Check: "Rules are undated `##`/`###`
    headings" stated from the writer — a rule unit is what `learnings_files.rule_units` returns
    (a `##`/`###` heading or a top-level bullet), in one clause; net zero against the ceiling by
    trimming the same sentence's restatement, or declared.
  - `documentation/project-structure.md`: the two-repo tree shows `session-hygiene.md` and
    `docs/discipline.md` (the latter added in Chunk 03's commit).
  - `README.md` § Recent Changes: only if the version is a minor (release checklist step 5) —
    deferred to Chunk 05 where the version is known; noted here so it is not dropped.
- **Tests:** `test_v5_methodology.py` readings and ceilings for the digest and `review-cycle.md`;
  the digest character pin; a positive pin for the R10 sentence on the digest (the always-injected
  surface is where a default must reach every session); `tests/preferences`.
- **Acceptance criteria:** `uv run pytest -q tests/test_v5_methodology.py
  tests/test_plugin_methodology_digest.py tests/preferences tests/test_record_lint.py` passes;
  `prawduct-hook verify-records` clean.
- **Type:** doc-only
- **Critic mode:** final (reviewed in Chunk 04's cumulative)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 03: The discipline seed — ten cross-repo rules delivered where rules fire, recorded in one table

- **Description:** The ten lessons the fleet learned independently (audit §3.5) become, each,
  a code directive at the action, a Critic-goal sentence, or a methodology sentence — never an
  always-loaded corpus — and one table records which, so #343's content program has its first
  entry and a place to grow.
- **Depends on:** Chunk 02 (the ceilings are settled)
- **Artifacts consumed:** discovery R12, §5 "write-time routing is an instruction plus a Critic
  goal, never a probe"; audit §3.2 (which channels have measured firing), §3.5 (the ten rules);
  the existing code directives as precedent (`_GREEN_IS_EVIDENCE_DIRECTIVE` at test-evidence
  record, `RESOLUTION_IS_A_CLAIM_DIRECTIVE` and `_BATCH_FIX_DIRECTIVE` in `critic_consolidate`);
  backlog #343's owner ruling (the three-part generality test every promoted rule must pass).
- **Deliverables:**
  - The ten rules, each first checked for an EXISTING home by grep across the digest, the Critic
    goal files, `building.md` and the directive constants (several already have one — "there is
    no pre-existing exception" is on the digest; "green is evidence" is the record directive) —
    a rule with a home gets a table row naming it and no new text. For each rule without one,
    the delivery is chosen by whether the rule has a MOMENT a plugin command runs at: (a) "a
    mutation must be shown to have applied" and "vacuous tests" → the test-evidence record
    directive (extend, not a second directive); (b) "run the canonical full suite" → the same
    site; (c) "interface change means census every consumer", "retiring a claim is a repo-wide
    grep", "built-but-unconsumed is not done", "test both directions" → Critic Goal sentences
    (the review is the moment) — `goals-1-3.md` has no headroom, so these land in ONE new
    subsection of `review-cycle.md`'s final-mode cross-checks or are funded by a declared raise on
    `goals-1-3.md` with the reason that a rule five repos re-learned is worth its tokens; the
    chunk decides and the table says which; (d) "stated cause is a hypothesis" and "probe real
    output" → `building.md` sentences under Investigated Changes if they fit, else the same
    treatment as (c). Every sentence passes the three-part generality test before it lands.
  - new `plugin/docs/discipline.md`: ten rows — rule (one line), the repos that learned it
    (from the audit), the delivery channel, the exact surface, and whether it existed before this
    chunk. A header stating the promotion test and that nothing here is an always-loaded corpus.
  - Code directives that ship in `prawduct-hook` or `lib/` carry a test each (the directive text
    reaches the channel at the action), red-verified; the test-evidence directive's existing test
    is extended in kind.
  - `tests/test_v5_methodology.py`: readings and ceilings for every prose file touched, with each
    raise declared in the ledger comment; a new test that every row's named surface contains its
    sentence (the table and the surfaces pinned against EACH OTHER, read through the plugin root).
- **Tests:** as above; `tests/test_v5_methodology.py`, `tests/test_plugin_runtime.py` (directive
  text at the record site), `tests/test_critic_consolidate.py` if a directive lands there,
  `tests/preferences`.
- **Acceptance criteria:** `uv run pytest -q tests/test_v5_methodology.py tests/test_plugin_runtime.py
  tests/test_critic_consolidate.py tests/preferences` passes; the table has ten rows and the
  cross-pin test reaches all ten; each directive observed live once at its site in this worktree.
- **Type:** code
- **Critic mode:** final (reviewed in Chunk 04's cumulative)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 04: The program's PR to `develop` — its cumulative review is the gate

- **Description:** The one review this wave runs, over the whole program's uncovered span, and
  the PR that carries three waves to `develop`.
- **Depends on:** Chunks 01–03
- **Artifacts consumed:** `skills/pr/SKILL.md` and `skills/pr/review-protocol.md`; Wave 1's plan
  § Governance ("no PR until Wave 3 closes the release; `/prawduct:pr create` is gated on Wave 3's
  cumulative review"); this repo's rule that warnings are effectively blocking.
- **Deliverables:**
  - `[DECISION: Chunks 01–03 get no separate reviews; this chunk's cumulative reviews them
    together with the program's uncovered span | three small prose chunks and one directive set
    are one coherent diff, Wave 1's merged-three precedent found more in one review than in three,
    and review wall clock is this repo's P0 | user can veto: a `chunk` review per chunk]`
  - Full suite recorded under the venv; `/prawduct:critic cumulative`; every blocking AND warning
    finding fixed; `verify-resolutions`; the change-log entry `type=feat | scope=learnings-v2-docs`
    whose body covers Chunks 01–03 and names the two earlier scopes it closes the program for.
  - `/prawduct:pr create` against `develop` with a merge commit; the PR reviewer's findings
    disposed; merge with `--merge`. The three wave plans stay live with their `branch:` claims
    until the release archives them (gitflow rule).
  - The develop merge's debt paid here: every learnings entry added on develop after f3be1f2
    hand-ported into `.claude/rules/learnings/`; the backlog cache re-synced once the v8 reader
    arrives (`prawduct-hook backlog sync --repo brookstalley/prawduct`) and the norm-decay
    advisory re-pointed.
- **Tests:** the full suite, recorded.
- **Acceptance criteria:** cumulative review clean after resolutions; PR merged to `develop`;
  `check-cumulative-critic` reports nothing uncovered on `develop`.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic cumulative` run and every blocking and warning finding resolved
  3. PR merged; chunk marked `[x]` in Status

### Chunk 05: Release — plan, version, cut, verify, reopen `develop`

- **Description:** The release that ships the program, run from
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` in its running order, with the version
  framed for the owner before Phase 1 commits it.
- **Depends on:** Chunk 04
- **Artifacts consumed:** `documentation/release-process.md` § Release checklist; the runbook
  Phases 0–3; `release-plan-v3.4.0.md` as the shape precedent (a minor call recorded against the
  conservative-versioning norm); `plugin/hooks/gates.json`'s three `since: "3.5.0"` rows; the
  Wave 2 handoff's #661 caveat.
- **Deliverables:**
  - **Owner decision, framed before Phase 1:** version 3.5.0 (minor — the discovery's D1: a
    consumer's repo is rewritten on its first session, a skill and three verbs retired, a Stop
    gate widened to every session) versus 3.4.1 (the conservative norm). Recorded in the release
    plan whichever way; `gates.json`'s `since` rows rewritten if not 3.5.0.
  - new `.prawduct/artifacts/release-plan-v3.5.0.md` (or the chosen version): version decision,
    release classification of every release-pending scope on `develop` (this program's three plus
    whatever the peer session landed), the consumer-facing headline, what ships, verification.
  - Phase 0: `check-releasability --release vX.Y.Z` green on a current green suite. Phase 1 on
    `develop`: release-pending set derived per candidate, `release=` tags on the shipping scopes,
    the three version files, `plugin/CHANGELOG.md` section renamed, `README.md` § Recent Changes
    refreshed if minor, `plan-backfill --apply` archives the three wave plans (and any other
    shipped plan), commit, push. Phase 2: promote to `main` and publish the GitHub Release in one
    call. `check-released` exit 0 and the CI verify dispatched. Phase 3: reopen `develop` at the
    next `-dev` patch.
  - Backlog at the release, through `/prawduct:backlog`: #685, #347, #295, #744 → `shipped`;
    #661 → three sub-findings FILED first (`risk_surfaces: []` should warn; no gate detects an
    unpersisted plan; a regression test for a gate switched off by a `build_plan:` key edit), then
    `shipped`; #343 commented (R12 is its first entry; the mechanical-promotion half stays open);
    #304 left open.
- **Tests:** the suite on the candidate tree; `check-released`; the CI run.
- **Acceptance criteria:** `check-released vX.Y.Z` exit 0; the CI verify green; the next session
  against `main` shows the banner naming the release and the three learnings gates.
- **Type:** cleanup
- **Critic mode:** final (nothing judgeable — the runbook's bookkeeping commits; a Critic pass
  is not owed, per the release process)
- **Done when:**
  1. Owner confirmed the version and the promotion shape
  2. Runbook Phases 0–3 complete with their checkpoints green
  3. Chunk marked `[x]`; the three plans archived by the release itself

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** open `/prawduct:methodology reflection` and read a guide about the
learning loop that fits on two screens, then `/prawduct:methodology session-hygiene` for the
standing block — the split the audit asked for, visible before anything else changes.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk; one cumulative review at Chunk 04, which is also the
PR gate; the release is Chunk 05.

- After Chunk 01: every test that pinned `reflection.md` was moved, not weakened — diff the
  assertions, not the pass count.
- Before Chunk 04's review: re-run the widened grep-clean from Wave 2's Chunk 05 and the
  single-resolver allowlist; both must be at their end state.
- Before Chunk 05's Phase 1: the owner's version call is recorded; `check-releasability` is
  green; the `since` rows agree with the version.
