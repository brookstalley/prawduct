---
artifact: build-plan
# Distinct scope from the start — never null (a null scope inherits another
# scope's shipped checkbox flips at regen-views) and never a version (that
# would collide with the release plans).
version: 2
scope: critic-burndown
depends_on: []
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost × run-count, and unit-cost is the reviewer's *payload* → **conforms, and this plan is the norm's lever being exercised as designed**. Chunks 01 and 02 both add prose to the two budgeted payload files, and at planning time both sat within a handful of words of their ceilings — which is why Chunk 01 is a real chunk rather than a two-line edit. Every addition is funded in the same file; **no chunk raises a ceiling**. Current readings live in `LAST_MEASURED_TOKENS` and the ceilings in each file's `test_token_budget`; this disposition deliberately states neither, because a figure restated in a governing document is a figure that goes stale the moment the work it governs lands. **Chunk 01 discharged this**: both files ended smaller than they started, each having gained a check. Funding rule, per owner ruling 2026-08-02: raise a ceiling only when the framework is provably better FOR THE RAISE and upleveling has no headroom left — detail, dates, running tallies, worked examples, and definitions another file owns are cuttable outright"
      - "proportionality ratchets both ways; a control added from 2026-07-29 names its expected yield **and emits that yield observably** → **DEPARTURE, recorded — see [DECISION] under Chunk 01.** #97 and #293 both add controls after the boundary date, so the obligation binds at birth. Goal-level attribution does not discharge it: findings do carry a `goal` field into the persisted fact, but the field is **free text and already drifting** — Framework Check 8 alone appears under four spellings (`Instruction Clarity (Framework Check 8)`, `Framework Check 8 — Instruction Clarity`, `Instruction Clarity (Check 8)`, `Framework Check 8 (Instruction Clarity)`). A sub-check *inside* Goal 1 is a fortiori uncountable. The plan's answer is a stable token in the finding title, per the precedent this repo already set (#327's degraded-reading notice, 'countable by its stable token')"
      - "state-file growth surfaced as an advisory, never a hard block → inapplicable because no chunk changes a size threshold"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary (`CRITICAL:`/`WARNING:`/`NOTE:`/`PRAWDUCT:`/`BLOCKED —…`) with a stdout/stderr channel split → conforms. Chunk 03 appends a sentence to an existing `blocking:` emission on stderr in **two** sites; it introduces no new prefix and moves no channel"
      - "text emitted into a governed product names no prawduct-internal identifier → **conforms, and it binds Chunk 03 tightly.** This norm reached steady-state 2026-08-02 (OBS-7M4D closed the last four sites) and the interim 'only text you touch' exception is retired, so it now binds every emitted string. Chunk 03's new sentence names the *route* (a spanning `cumulative`), never an issue id. Enforcement is reviewer judgment, not a regex — a `print(...)`-argument grep is a floor, not proof, because emitted text can be returned, appended to a printed list, or assembled into a document"
      - "the governance ledger has a single writer; agents never hand-author it → inapplicable because no chunk writes a ledger line"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms. Chunk 03 changes what `check-cumulative-critic` *says*, never what it *decides*: the verdict, the exit code, and the fail-closed posture are untouched. It converts an unreachable instruction into a reachable one, which is the fail-closed arm working as intended rather than being softened"
      - "every fact has one home; every other mention is a reference to it → conforms, and it constrains Chunk 02's shape. The `cross-cutting-concerns.md` row for `risk_surfaces` is an **index entry — a name and a pointer**, not a second copy of the discovery question. If changing the question required editing the row too, the row would already be wrong"
      - "goals and verification bind; prescribed method is advice → conforms. Every `Deliverables` line below is a pre-code guess; a builder who finds a better route takes it and records why. The Acceptance criteria and the norm dispositions bind"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches the review-active mutation guard"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime and instructions, not a product's code"
      - "Python but never Python-specific → inapplicable because no chunk touches per-language gate dispatch"
      - "local-first governance, no network in the governance runtime → inapplicable because no chunk adds a network call"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because no chunk adds a write path into a governed repo"
  - artifact: data-model
    dispositions:
      - "governance verdicts computed from the append-only fact ledger, never from mutable model-written state → conforms. Chunk 03 reads facts to *describe* a verdict more usefully; no model enters the write path and no verdict is recomputed"
      - "facts are immutable and append-only → conforms (Chunk 03 reads only; it appends and edits nothing)"
      - "derived views are disposable and never authoritative → conforms (no chunk makes a gate read a view)"
      - "a fact written by a newer schema is surfaced as a loud block, never silently dropped → inapplicable because no chunk changes the fact schema, additively or otherwise"
      - "two stores, two lifetimes → inapplicable because no chunk moves state between the committed and gitignored stores"
      - "`backlog_service_repo` selects the authoritative store → inapplicable because no chunk reads or writes the backlog store"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version → conforms (this batch is a patch-level change to existing surface)"
      - "exit codes are the contract; message severity is a stable prefix vocabulary; errors are attributed, never stack traces → conforms. Chunk 03 changes message *text* only — no exit code changes meaning, and the added sentence is attributed advice, not a traceback"
      - "additive-first evolution; existing flag names, exit-code meanings and `--json` keys are never repurposed → conforms. No chunk adds, removes or repurposes a flag or a `--json` key"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative — a small feature is a patch bump → conforms (this batch is a patch release)"
      - "gitflow: features branch off `develop` and merge back → conforms (`fix/critic-burndown` is off `develop` at `b271d78`)"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms. Chunk 03 reads finding *titles* out of the evidence store and prints them; that path already exists and this plan neither widens it nor grants those strings any instruction force"
      - "a destructive or irreversible operation requires owner approval at the operation level → inapplicable because no chunk performs one"
      - "a governed product's content never leaves its own repository and owner → inapplicable because no chunk adds an outbound path"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Six already-triaged tracker items, each carrying a stated problem, a repro or a named
site, and an owner-reviewed fix-shape. No discovery is owed. The batch was re-derived from the
live tracker on 2026-08-02 and every item's *ask* was re-read against current machinery rather
than trusted from its citations — which is how the two corrections below were found before any
code was written.

**The cluster was the owner's choice**, made against a four-way comparison (review tail /
backlog-service / critic / deletion-only pass). This plan takes the `critic` area's `stage: ready`
items and nothing else.

**Open assumptions / unknowns:**

- [ASSUMPTION: #165 stays deferred because its own revisit trigger has not fired | LOW impact |
  user can override] #165 (`the ledger anchor's overlap window needs a lock, not a probe`) is the
  seventh `critic`/`stage: ready` item and is **deliberately excluded**. Its recorded trigger is
  *"a SECOND surplus `review.*` event — i.e. any duplicated `review.fact_id` other than the known
  `rev-20260729T233201Z-d91acd9e`."* Measured 2026-08-02 across every `prawduct` worktree ledger:
  394 `review.*` events, 240 carrying a `fact_id` over 239 distinct ids, **surplus 1**, and the one
  duplicate is the known id. The trigger has not fired. **Note the measurement trap:** the ledger is
  per-worktree and gitignored, so counting only this worktree's 28 events returns a false clean —
  the count above sums the primary checkout (366) and this worktree (28). Building #165 now would
  be building against an explicitly unfired condition.
- [ASSUMPTION: #97's deliverable is the closed PR #98's content, revived against current `develop`
  | LOW impact | user can veto] #97 says "a PR implementing exactly this is incoming." That PR
  (#98) was **closed as stale on 2026-07-27 and its content never landed** — the head branch is
  gone, and it targeted `main`, which this repo's release model never merges into. The owner's
  closing comment preserves the proposal text and says so explicitly: *"the proposal's content was
  never landed."* This plan revives that content rather than re-deriving it.
- [ASSUMPTION: #264's sub-item (6) is settled by documenting deletion as intended, not by building
  an archive | MED impact | user can override] The sub-item asks to *decide* PR-review evidence
  retention: archive to `.prawduct/.pr-reviews-archive/` or document why deletion is intended.
  Recommendation is **document deletion**: `.prawduct/.pr-reviews/` is gitignored per-clone scratch,
  the durable record of a review already lives in the shared evidence store as a fact, and an
  archive directory would be a second home for a fact that has one — which the *every fact has one
  home* norm forbids. Building the archive is the reversible-but-wrong option; if the owner wants
  it, it is a separate item, not a sub-bullet.
- [ASSUMPTION: `fix/review-loop-termination` merges after this branch and resolves its own conflicts
  | LOW impact | user can reorder] That branch touches four files this plan also touches
  (`review-protocol.md`, `review-cycle.md`, `building.md`, `test_v5_methodology.py`). Measured: it
  is **267 commits behind `develop` and 2 ahead, with no PR open**, and its two budget-ceiling
  edits (`review-protocol.md` 3530→3620, `building.md` 4600→4660) **are already on `develop`** by
  another path — so most of its apparent diff is a replay against a stale merge-base. Its real
  novel content is `review-cycle.md` (+48 lines). It owes a rebase regardless of this plan.

**What would raise confidence:** N/A at High. The two MED-impact assumptions are both one-line
owner answers and neither blocks a chunk from starting.

## Status

<!-- Derived view (`views_enabled: true`). Mark a chunk shipped by adding a change-log entry
     tagged scope=critic-burndown / status=shipped, then run regen-views.
     Do NOT hand-flip the checkboxes. Stays [ ] on this branch until the release ships —
     a built chunk is recorded in Context below, not by its checkbox. -->

- [ ] Chunk 01: The two new Critic controls, funded not bumped (#97, #293)
- [ ] Chunk 02: The prose batch and the discovery gap (#264, #163)
- [ ] Chunk 03: The code tail — a reachable gate message and two unpinned CLI behaviors (#536, #228)
Context: Plan authored 2026-08-02 on `fix/critic-burndown` off `develop` at `b271d78`, from the
owner's choice of the `critic` `stage: ready` cluster. Six of the seven candidate items are in
scope; #165 is excluded on its own unfired revisit trigger (measured — see Open assumptions).
`active_build_plan` still points at `build-plan-v3.2.0-golive.md` **by design** and must not be
repointed: the gates resolve the *branch's* plan by scope, and `build-plan-backlog-burndown.md` is
retained until the pending `develop`→`main` release regenerates it.

**Chunk 01 CLOSED 2026-08-02** (#97, #293) — built, reviewed, verified, gate satisfied. Three commits:
`8903a9b` (the chunk), `99dd8b2` (the cumulative review's findings), `4e75d03` (the verify pass's).
`check-cumulative-critic` reports coverage composed with 0 unresolved blocking.

Both controls landed with **no ceiling raised**, and both budgeted files came out *smaller* than they
went in despite gaining a check (readings live in `LAST_MEASURED_TOKENS`, which owns them — restating
figures in prose is what staled the last set). Funded by upleveling per the owner's standing rule:
raise a budget only if provably better for the framework AND no headroom remains in cutting detail,
dates, worked examples, and definitions the reader never applies.

**Two review rounds, 0 blocking in both.** The cumulative pass (4 warnings, 13 notes) caught that the
PR half of the yield mechanism named a field that does not exist — two reviewers found it
independently. The verify pass (1 warning, 2 notes) caught that the retire rule written to fix *that*
round counted a denominator its numerator cannot reach. Both were prose asserting something the code
does not support; neither was a logic error in shipped behaviour, which is now thirteen consecutive
rounds of that pattern across this and the previous branch.

Filed rather than built: `#547`, `#548`, `#549`. Next: **Chunk 02** (#264, #163).

## Scaffolding

### Build & Test Configuration

Unchanged. `python3 -m pytest tests/ -q` runs everything (`test_command` in `project-state.yaml`
adds the junit path used by `test-evidence record`). No new dependencies, no scaffold changes —
this is a burn-down batch against existing surface.

**Verify hook behaviour with `python3 plugin/bin/prawduct-hook` from this checkout.** A `$PATH`
`prawduct-hook` resolves to a different tree and will silently answer for the wrong code.

### Verification Strategy

Two of the three chunks ship **instructions**, where the standing trap is that every test which
measures the *artifact* — size, budget, "the right words are present" — passes while the
instruction has no effect on a reader. Chunk 01 therefore verifies its controls by their intended
*reader behaviour*: the added checks must be traceable in a real review's output, which is what the
stable-token decision below exists to make possible. Chunk 03 verifies by running the two CLI paths
directly against this checkout and reading the emitted text, not only by asserting on it.

## Build Chunks

### Chunk 01: The two new Critic controls, funded not bumped (#97, #293)

- **Description:** Land the two protocol strengthenings that both *add a control*, together, because
  they land in the same two budget-bound files and the budget must be settled once. **#97** folds a
  cross-component message-contract check into Goal 1 so it runs in **chunk** mode and is **BLOCKING**
  for an actual mismatch — a consumer that blocks on a signal the producer never emits, or omits a
  terminal/error signal the producer does emit. Matching types is necessary and not sufficient; read
  both ends. Goal 5 gets a one-clause scoping so the two do not overlap: Goal 5 is *downstream*
  consumer impact, Goal 1 owns the inverse (consumer mismodels producer). **#293** adds one mandated
  question to the cumulative and PR protocols: does this capability trace to a documented
  requirement, and is it reachable and consumed end-to-end.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` (the proportionality
  and wall-clock norms — both bind this chunk directly)
- **Deliverables:** the Goal 1 bullet and the Goal 5 scoping clause in
  `plugin/skills/critic/goals-1-3.md` (the chunk-mode payload — this is where a chunk-mode check has
  to live) and `plugin/skills/critic/review-protocol.md`; the mandated scope question in
  `plugin/skills/critic/review-protocol.md` and `plugin/skills/pr/review-protocol.md`; the funding
  trims in the same files; updated `LAST_MEASURED_TOKENS` readings and budget-comment narratives in
  `tests/test_v5_methodology.py`.
- **Tests:** the existing `test_token_budget` and `test_last_measured_tokens_is_current`
  parametrisations must stay green **without a ceiling raise** — that is the chunk's hardest
  acceptance criterion, not a formality. Add a reader-modelling guard: assert the stable finding
  tokens are present in both protocols so a later trim cannot silently delete the countability the
  proportionality norm requires.
- **Acceptance criteria:** `goals-1-3.md` stays under 2000 and `review-protocol.md` under 3620 with
  their `LAST_MEASURED_TOKENS` entries updated to the true readings; each budget comment says what
  the edit cost **and what paid for it**; Goal 1's new bullet is BLOCKING and reachable in chunk
  mode; Goal 5 no longer overlaps it; both the cumulative and PR protocols carry the scope question.
  <!-- No `Type:` declared, so this chunk runs the default `code` protocol. It was drafted as
       `doc-only` on the assumption that strengthening protocols is prose work; that was wrong —
       the chunk ships a new test file and rewrites another, and `doc-only` tells the Critic to
       skip test-evidence checks. Over-declaring Type is the unsafe direction
       (`methodology/planning.md`), so the field is omitted rather than narrowed. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

[DECISION: the two new controls discharge the observable-yield obligation with a **stable token in
the finding title**, not with goal-level attribution | the norm's why is that a control whose
findings are printed and forgotten can never be retired on evidence, only defended on principle —
and goal-level attribution cannot carry the weight here: the persisted `goal` field is free text and
is measurably drifting already (Framework Check 8 appears under four spellings in the shared
evidence store), so a sub-check inside Goal 1 would be uncountable from the day it shipped. A stable token
makes the yield a one-line query against the shared evidence store, which is the specification the
norm's in-transition arm asks a new control to leave behind for the janitor's Norm Health sweep to
build against | user can veto/override]

**The yield each control expects** — the norm's *first* conjunct, which the DECISION above discharges
the second half of and this states explicitly, so the sweep has a baseline rather than a bare count:

- **`cross-component-contract:`** — expected to fire only on diffs that actually cross a process or
  component boundary, which is a minority of chunks in this repo (prawduct is single-process; its
  boundaries are the hook↔skill and hook↔`gh` surfaces). **Retire it if it produces zero BLOCKING
  findings across 20+ reviews of boundary-crossing diffs** — not 20 reviews total, since a check that
  never met its trigger has not been tested. Note the filing case came from a *governed product*, not
  from here, so a low yield in this repo is weak evidence about the check's value to consumers; that
  asymmetry is itself the reason to count trigger-eligible reviews rather than all reviews.
- **`scope-trace:`** — expected to fire rarely and to be *high-value when it does*, because the
  failure it names (a capability with no parent requirement, or one nothing reaches) is the kind that
  survives every other check. **Retire it if it produces zero findings across 30+ `cumulative`
  reviews**, or if its findings prove consistently duplicative of Goal 3's "no extra functionality"
  bullet — the overlap this chunk disambiguated but did not eliminate.

**The PR half is deliberately outside the retire decision, and this is the correction that matters.**
An earlier draft of this rule counted "`cumulative`/PR reviews" — a denominator the numerator cannot
reach. PR findings never enter the shared evidence store: `evidence.KNOWN_KINDS` is
`{review, resolution, disposition}`, all written by `critic-consolidate`, and the PR reviewer's
record lands in `.prawduct/.pr-reviews/` plus a `review.pr` ledger event in
`.prawduct/.governance-ledger.jsonl` — **gitignored and per-worktree**. So a query over the store
would count zero PR findings and read it as "never fired." The token still belongs in the PR protocol
(it makes the finding legible to a human reading the report); it simply cannot contribute evidence to
a retirement, and a rule that counted it would have retired the control on a denominator it never
sampled. Reviving the PR half as evidence needs a cross-worktree ledger sweep — the same measurement
`#165` required — not a bigger threshold.

**Both denominators are honest about their cost.** `scope-trace:`'s is a one-line query over the
store. `cross-component-contract:`'s is not: review facts carry no boundary-crossing classification,
so "reviews of boundary-crossing diffs" is a **hand audit** of `files_changed`. Stated rather than
hidden — a threshold whose denominator is manual will be measured late or not at all, which is an
argument for `#548`'s structured `check:` field carrying the trigger alongside the yield.

These are *stopping rules stated in advance*, not predictions. The norm's own in-transition note says
a control may be retired on a reasoned argument provided the argument states what evidence would have
settled it; these are that statement.

### Chunk 02: The prose batch and the discovery gap (#264, #163)

- **Description:** The five surviving skill-prose clarity fixes from the 2026-06-09 review (#264),
  plus the `risk_surfaces` pipeline gap (#163). #264's five: make `review-protocol.md` step 6
  reference the Modes block's mode→goals mapping instead of the vague "decide checks from signals
  below"; note in `review-cycle.md`'s Learnings Cross-Check that a later learning revoking or
  softening an earlier one **wins**; give `framework-checks.md` Check 7 a concrete avoid/prefer
  example; document the combined 2/2 = 1.0 effect of missing effort/impact defaults in the backlog
  skill's `pick` and drop the stale "(Q6)" label; and settle PR-review evidence retention. #163:
  `risk_surfaces:` decides review depth for every onboarded repo and its Discovery leg is absent —
  Artifact, Builder and Critic are all present, so an unasked question is the thing deciding review
  depth by silent fallback. Add the question to `plugin/methodology/discovery.md` and a registry row
  to `.prawduct/cross-cutting-concerns.md`.
- **Depends on:** Chunk 01 (same two budget-bound files; the budget is settled there first, so this
  chunk's trims are measured against a known-good reading rather than a moving one)
- **Artifacts consumed:** `.prawduct/cross-cutting-concerns.md` (the pipeline coverage matrix #163
  reports the gap against), `.prawduct/artifacts/project-preferences.md` (the Enforcement table — a
  new registry row is assigned a check type, an audit home and a terse why)
- **Deliverables:** the four prose fixes in `plugin/skills/critic/review-protocol.md`,
  `plugin/skills/critic/review-cycle.md`, `plugin/skills/critic/framework-checks.md` and
  `plugin/skills/backlog/SKILL.md`; the retention decision recorded in `plugin/skills/pr/SKILL.md`;
  the risk-surface discovery question in `plugin/methodology/discovery.md`; one registry row in
  `.prawduct/cross-cutting-concerns.md`.
- **Tests:** existing prose guards must stay green — `tests/preferences/test_critic_skill_structure.py`,
  `tests/test_cutover_prose_coherence.py` and the `test_token_budget` family are the ones this
  chunk's files are pinned by. Any new assertion pins the **property**, not one spelling of it.
- **Acceptance criteria:** all five #264 sub-items are landed or explicitly dropped with a recorded
  reason (sub-item 2 was already resolved in 2026-06-10 and must **not** be redone — the item says
  so); `discovery.md` asks a question whose answer is `risk_surfaces:`; the concerns registry has a
  row that is an index entry, not a copy; budgets still green without a raise.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The code tail — a reachable gate message and two unpinned CLI behaviors (#536, #228)

- **Description:** The batch's only code. **#536**: a BLOCKING finding that is *superseded* rather
  than resolved is never revisited, because each `verify-resolutions` pass anchors to the newest
  prior review fact — so it sits in `unresolved_blocking` permanently while the gate message tells
  the operator to run `verify-resolutions`, which is exactly the route that cannot clear it. The
  underlying state self-heals (a later spanning `cumulative` with zero blocking supplies a clean
  path through `coverage_verdict`'s phase-1 search); the defect is that **nothing says so**. Extend
  the message: when an unresolved blocking finding belongs to a fact older than the newest, name the
  spanning `cumulative` as the route that clears it. **#228**: pin two behaviours that were
  hand-verified during discodon-upstream-defects and never tested — `cmd_verify_chunk_refs`
  differentiating its `cannot-verify:` exit message from its `missing-ref:` exit message, and
  `cmd_critic_begin`'s sibling-worktree branch fallback when a worktree has no branch (detached or
  bare). Both are correct today; the gap is coverage, and changing either behaviour is out of scope.
- **Depends on:** none (independent of Chunks 01–02; ordered last so the doc chunks settle the
  budgets first)
- **Artifacts consumed:** `.prawduct/artifacts/observability-strategy.md` (the emitted-text norms
  bind the new sentence), `.prawduct/artifacts/api-contract.md` (exit codes and severity prefixes
  are unchanged and must stay so)
- **Deliverables:** the superseded-blocker clause in **both** emission sites — `plugin/lib/gates.py`
  (`check-cumulative-critic`'s `blocking:` branch) and `plugin/bin/prawduct-hook` (the parallel
  stop-hook message); new `tests/test_hook_cli_regressions.py` for the two #228 behaviours;
  additions to `tests/test_cumulative_gate.py` for the #536 message.
- **Tests:** unit — the superseded case (an unresolved blocking finding on a non-newest fact) emits
  the spanning-`cumulative` sentence and the non-superseded case does not; `cannot-verify:` and
  `missing-ref:` produce distinguishable exit messages; `critic-begin` renders a branchless sibling
  worktree without raising. Assertions pin the property and are verified **red against a different
  phrasing**, not just green against the current one.
- **Acceptance criteria:** both emission sites carry the clause and neither names a prawduct-internal
  identifier; no exit code changes meaning; the two #228 paths each have a test that fails if the
  behaviour collapses; full suite green.
- **Type:** cumulative-final
  <!-- Last chunk of a plan shipping as one PR: its review IS the one
       `/prawduct:critic cumulative` against merge-base...HEAD. Commit first,
       run it once — no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01 — the first chunk changes what every subsequent Critic review in this repo
checks, so its effect is visible on this very branch: Chunk 02's and Chunk 03's own reviews run
under the strengthened Goal 1. That is the earliest honest feedback a governance change can offer,
and it is why Chunk 01 leads rather than the code.

**Note on the usual first-chunk rule:** this plan has no walking skeleton. A burn-down batch against
existing surface has no architecture to prove, and inventing a vertical slice would be ceremony.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes — per-chunk commit is what
scopes `chunk`-mode reviews, and this plan relies on it. The last chunk's `cumulative` review makes
the branch PR-ready; `/prawduct:pr create` is gated on it and runs when the owner asks.

- **After Chunk 01:** confirm the two new controls actually changed reviewer behaviour rather than
  only file contents — the instructions-are-the-deliverable trap. Chunk 02's own review is the first
  evidence.
- **After Chunk 03 (cumulative):** full-bundle review. Verify specifically that the batch did not
  ratchet: three of the six items *add* governance surface (#97, #293, #163), which is the growth
  driver the owner has flagged. The proportionality norm's yield obligation is the counterweight —
  check that it was discharged rather than declared.
