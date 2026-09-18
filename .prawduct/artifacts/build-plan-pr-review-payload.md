---
artifact: build-plan
version: 2
scope: pr-review-payload
branch: feat/pr-review-payload
depends_on:
  - artifact: pr-review-payload-discovery
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; unit-cost via payload is a declared lever → conforms — this plan is that norm's application, not an exception to it"
      - "proportionality ratchets both ways; a new control emits its yield observably → conforms — Chunk 03 modifies an existing control rather than adding one, and names its expected yield (findings/review held flat while duration falls), which Chunk 01 makes measurable for the first time"
      - "state-file growth is advisory, never a hard block → inapplicable because this plan adds no size gate"
      - "review rigor is stage-keyed; the boundary stage is never skipped or inferred away → conforms — the PR review is retained at full frequency; only its payload changes"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms — `pr-review-payload` is read-only, and Chunk 04's agent keeps `Write` scoped to its own evidence file"
      - "authority fails closed; advice fails soft; a command's failure posture follows what it produces → conforms — `pr-review-payload` emits no verdict, so it fails soft PER SECTION and names each degradation (advice failing soft is not advice failing silent)"
      - "local-first; no third-party dependencies in the governance runtime → conforms — stdlib only; the backlog section reuses the existing cache read and opens no socket"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms — the dispatch marker is `.prawduct/` state"
      - "written in Python, never specific to Python → conforms — every payload section is language-agnostic; the test-status section reports a verdict the product's own declared command produced"
      - "prawduct guides and reviews; it never implements → conforms"
      - "goals and verification bind; prescribed method is advice → RULING NEEDED — Chunk 03 rewrites what the PR reviewer's four goals BIND to, which is normative content, not method. Recorded as a decision in that chunk rather than assumed."
      - "every fact has one home; every other mention is a reference to it → conforms, and repairs a live violation — `core.md` currently reaches the reviewer twice (auto-injected and re-read), and `pr-review-payload` becomes the one home for the reviewer's context facts"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the internal CLI carries no per-subcommand version → conforms — `pr-review-payload` and `pr-review-dispatch` are internal/unstable, outside the § Operations published surfaces group, so no stability tier or `--version` handle is owed"
      - "exit codes are the contract; errors are attributed, never stack traces → conforms — Chunk 02 states its exit-code table before implementing and cites this artifact rather than inventing a convention"
      - "additive-first evolution; `--json` readers tolerate unknown keys → conforms — `dispatched_at` is a new optional envelope key; no existing key, flag or exit-code meaning is repurposed"
  - artifact: data-model
    dispositions:
      - "governance verdicts come from code-written facts; no model sits in a fact's write path → conforms, and STRENGTHENS — `duration_seconds` is model-written today; Chunk 01's clock is read by code, so the model chooses when to mark dispatch and never what the value is"
      - "facts are immutable and append-only → conforms — `dispatched_at` is written once, at append, never edited"
      - "derived views are disposable and never authoritative → conforms — no gate reads the payload; it is reviewer input, not a verdict"
      - "a governance document reaches a terminal state; it is never deleted → conforms — this plan is archived at the release, not deleted"
      - "every backlog issue conforms to the issue standard's title rules → inapplicable because this plan writes no backlog items except the closes in Chunk 05, which run through `/prawduct:backlog`"
      - "a fact written by a newer schema than the reader blocks loudly → conforms — the envelope key is additive and absence is reported as `not measured`, never as zero"
      - "two stores, two lifetimes — shared committed answers vs per-clone gitignored state → conforms — the dispatch marker is per-clone and gitignored; it is a stopwatch, not an answer"
      - "`backlog_service_repo` selects the authoritative backlog store → conforms — the payload's backlog section calls the existing cache read, which already routes"
partition: serial — 03 consumes 02's command, 04 rewires the dispatch 03 rewrote, and 05 measures all of them
last_validated: null
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem, the measurement and the four waste sources are established in
`pr-review-payload-discovery.md` from the ledger and the Claude Code subagent documentation, and
the norm that authorizes the trade is already ratified. What is unconfirmed is Chunk 04's
mechanism — whether `omitClaudeMd: true` is honored for a **plugin-supplied** agent, as opposed to
a project-level one — and what the goal re-point does to yield, which cannot be known before it
runs.

**Open assumptions / unknowns:**

- `[ASSUMPTION: omitClaudeMd is honored for plugin-supplied agents, not only project-level ones | HIGH impact | user can correct/override]` — the documentation states the field without scoping it to a definition source. Chunk 04's `verify-api` step 0 settles it before any code is written; if it is not honored, that chunk degrades to shrinking what the agent is told to read and the ~27k saving is lost while Chunks 01–03 and 05 are unaffected.
- `[ASSUMPTION: re-pointing the four goals at governance bookkeeping holds findings-per-review roughly flat | MED impact | user can correct/override]` — it names what the reviewer already catches, so it should raise yield per minute rather than lower it; Chunk 05 measures rather than asserts.
- `[ASSUMPTION: the owner wants the ~2-minute target pursued only as far as items 1-5 reach (~4-6 min projected), with the further diff-scoping trade argued separately against post-change numbers | MED impact | user can correct/override]` — the discovery's §6 states the limit; this plan does not bundle the quality trade in on a projection.

**What would raise confidence:** Chunk 04's `verify-api` probe (minutes, and it is step 0 of that
chunk); and Chunk 01 landing before anything else, which converts every later claim from a
projection into a measurement.

## Status

- [ ] Chunk 01: Measure first — a code-written dispatch timestamp on the ledger
- [ ] Chunk 02: `pr-review-payload` — one deterministic call instead of twelve reads
- [ ] Chunk 03: Re-point the protocol — goals, payload wiring, and the output nobody reads
- [ ] Chunk 04: Dispatch as a named agent that does not inherit `CLAUDE.md`
- [ ] Chunk 05: Concurrency, measurement, and the norm reconciliation
Context: Plan authored 2026-09-18 from `pr-review-payload-discovery.md`, on `feat/pr-review-payload` cut from `develop` at 996766e5. Nothing built yet. Next: Chunk 01.

## Scaffolding

No new project scaffolding. This is framework work inside an existing repo: `plugin/lib/`,
`plugin/bin/prawduct-hook`, `plugin/skills/pr/`, `plugin/agents/`, `tests/`. The suite is the
declared `test_command` in `project-state.yaml`; run it through `prawduct-hook test-evidence
record`, never by hand and never recorded afterwards.

### Verification Strategy

Tests are not sufficient here, because the deliverable is partly **instructions**, and a test that
measures an instruction artifact (its size, its budget, the presence of the right words) passes
while the instruction has no effect. Two verifications beyond the suite:

1. **The ledger is the instrument.** `tools/pr-review-yield.py` reports `N measured, M
   self-reported`. Today it reports `0 measured, 122 self-reported`; that is the positive control.
   Chunk 01 is not done until a real dispatch flips a row to measured.
2. **Dogfood the reviewer.** This plan's own PR runs the reviewer it rewrote. That is the only
   verification that reads the protocol in the order an agent reads it. Chunk 05 records the
   measured duration of that run beside the pre-change median, and says plainly if it missed.

## Build Chunks

### Chunk 01: Measure first — a code-written dispatch timestamp on the ledger

- **Description:** A 2-minute target stated against a self-reported estimate is not a target.
  Record when the reviewer was *dispatched*, from a clock code reads, so duration becomes a
  measured interval rather than the reviewing model's recollection. This is the thin vertical
  slice: it touches the state file, the hook, the skill that calls it and the tool that reads it,
  and it proves the measure → change → measure loop before anything is optimized.
- **Depends on:** none
- **Artifacts consumed:** `pr-review-payload-discovery.md` §6 item 1, `data-model.md` (the
  code-written-facts norm)
- **Persisted-format decision — the questions the data must answer.** A new envelope key is
  lock-in regardless of its size, so its consumers' queries are enumerated before the field is
  designed, not inferred from the mechanism:
  - `prawduct-hook review-stats` — median duration per (role, model, mode), and it must be able to
    report measured and self-reported rows **separately**, because pooling them re-creates the
    hazard this chunk exists to retire.
  - `tools/pr-review-yield.py` — the same split for PR reviews alone, before and after a protocol
    change.
  - `tools/measure-consumer-overhead.py` — minutes per review per plugin-version window, across
    repos; this is the query that makes consumer figures comparable at all.
  - The janitor's Norm Health yield sweep (`#563`), when it exists — "what did this control cost,
    and what did it catch."
  From those four: one optional envelope key `dispatched_at`, UTC ISO-8601, written at append from
  a marker. Absence means **not measured**, never zero — every reader above reports the two
  populations separately rather than averaging a missing value into a real one.
- **Deliverables:**
  - new `plugin/lib/review_dispatch.py` — writes and consumes a per-clone
    dispatch marker, new `.prawduct/.pr-review-dispatch.json`. The model chooses *when* to mark; the timestamp is
    `datetime.now(timezone.utc)` inside this module, so no model value enters the write path.
  - `plugin/bin/prawduct-hook` — new `pr-review-dispatch --begin` subcommand; `ledger-append`
    consumes and clears the marker, writing `dispatched_at` into the envelope when one is present
    and omitting the key when none is; `review-stats` splits measured from self-reported.
  - `plugin/lib/ledger.py` — envelope acceptance of the optional key.
  - `tools/measure-consumer-overhead.py` — read `dispatched_at` where present and report
    the measured and self-reported populations separately, as `tools/pr-review-yield.py`
    already does. **This is a deliverable, not a follow-up:** the persisted-format decision
    above names four consumers that must be able to split the two populations, and Chunk 05's
    Done-when step 0 instructs recording this tool's reading. A field whose consumers are
    enumerated in a lock-in decision and then half-built is the accumulation that decision
    exists to prevent. The fourth consumer, the janitor's Norm Health yield sweep, does not
    exist yet (`#563`) and is named so the query has a specification, not built here.
  - `plugin/skills/pr/SKILL.md` — Step 3 marks dispatch immediately before spawning; Step 4's
    existing `ledger-append` line gains no new argument (the marker is ambient, so a caller cannot
    fabricate the value or forget to pass it — it can only fail to mark, which is the honest
    degradation).
  - `.prawduct/artifacts/data-model.md` — the envelope key and its absence semantics.
- **Exposed API:** prawduct-hook-cli
- **Carried into this chunk's commit from the 2026-09-18 planning reviews** (two deletions in
  `tools/pr-review-yield.py` and `tests/test_pr_review_yield_tool.py`, deferred here rather than
  fixed in place because that commit was already verified and these buy no round riding one that
  is being made anyway — this chunk edits both files for `dispatched_at` regardless):
  1. **Delete the history narration from three docstrings.** `_exceeds_upper` ("The earlier fix
     here special-cased the 10-character date…"), the `_event_nested_duration_only` helper ("a
     verify pass flagged that its green measured nothing"), and the month-only test ("This is the
     case the first fix missed"). Keep each docstring's RULE and drop the episode — a shipped
     comment narrating review history is a deletion finding, not a rewording one. The same
     sentences carry an inert "122 real rows" count that nothing reads and that drifts as the
     ledger grows; it goes with them.
  2. **Delete `_parse`'s `TypeError` arm.** It is unreachable: every stamp arrives from
     `json.loads`, so a non-`str` raises `AttributeError` at `.replace()` before `fromisoformat`
     is reached, and only `bytes` would reach `TypeError`, which JSON cannot produce. Pin the
     guarantee, not the mechanism — the `AttributeError` path is already covered.
- **Tests:** `tests/test_governance_ledger.py` — a marked dispatch produces `dispatched_at`; an
  unmarked one omits the key entirely (**never** a null or a zero); a stale marker from an
  abandoned run does not attach to an unrelated later append; `review-stats` reports the two
  populations separately and its measured count is non-zero on a fixture that has one. The
  degradation assertions are the load-bearing half — a field whose absence is ambiguous renders
  the exact inverse of the signal it was added for.
- **Acceptance criteria:** the declared suite passes; `tools/pr-review-yield.py` on a fixture
  ledger reports a non-zero `measured` count, and on this repo's real ledger still reports every
  historical row as self-reported rather than back-filling a guess.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `pr-review-payload` — one deterministic call instead of twelve reads

- **Description:** The reviewer spends 13–18 sequential round-trips assembling context the caller
  and the hooks already hold. Emit it once, deterministically. Passing *facts* is not passing
  reasoning — the reviewer's independence is that it has not seen the builder's thinking, and a
  command that reads `project-state.yaml` and runs `git log` reveals none of it.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `pr-review-payload-discovery.md` §1, `api-contract.md` § Direction
- **Deliverables:**
  - new `plugin/lib/pr_payload.py` — assembles, in one pass: resolved base; `git log --oneline
    <base>..HEAD`; the diff **stat** (never the diff itself — the reviewer reads that once, and a
    second copy is the duplication this plan exists to remove); work description and size/type
    from `project-state.yaml`; the `test-status` verdict as an exit code plus its reason; the
    resolved build plan's path and its `## Status` boxes; the change-log entry for this scope; the
    backlog `resolve` result for every id the branch's commits or change-log cite; and the repo's
    default branch, which the closing-keyword rule needs.
  - `plugin/bin/prawduct-hook` — new `pr-review-payload` subcommand, human and `--json`.
  - new `tests/test_pr_review_payload.py`
- **Failure posture, decided before coding** (`architecture.md`: a command's failure posture
  follows what it produces): this command emits no verdict, so it is **advice and fails soft** —
  but per section, with each degradation **named in the output**. A section that cannot be built
  says why, in the reviewer's own words ("backlog reconciliation unavailable — cache exit 6; R-1
  and R-2 not answered"). It never emits an empty section, because a silent empty reads as
  "checked, nothing found", which manufactures the false success the section exists to prevent.
  The one hard failure is an unresolvable base: no base means no review interval, so that is
  exit 1 with the resolver's own reason, not a degraded section.
- **Exposed API:** prawduct-hook-cli
- **Tests:** each section present on a healthy fixture; each section's degradation path asserted to
  produce a **named** reason rather than an empty value (one test per degradation, because the
  degradation paths are where the invariant actually lives); unresolvable base exits 1; `--json`
  fed to a parser as raw bytes, never through a shell `echo`; and an assertion that the emitted
  section set is **non-empty and contains the sections the command names** — otherwise a green
  test means nothing was assembled.
- **Acceptance criteria:** the declared suite passes; running `prawduct-hook pr-review-payload` on
  this branch emits every section with real values, and running it with the backlog cache moved
  aside emits the named degradation rather than silence.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Re-point the protocol — goals, payload wiring, and the output nobody reads

- **Description:** Three edits to one file, which is why they are one chunk. (a) Replace the six
  numbered "When You Are Activated" reads with the single payload call plus the diff and the
  targeted artifact read that actually yields. (b) **Delete step 6's learnings read.** The reason
  is deliberately NOT "the file is already in context by auto-injection" — Chunk 04 removes that
  auto-injection, so a reason resting on it is false one chunk later, and the recorded reason is
  what the next author edits against. The two reasons that survive Chunk 04: the goal that
  consumes the read has returned **1 finding in 122 reviews**, and the protocol's own Learnings
  Cross-Check section assigns that scan to the `final`/`cumulative` Critic, so this reviewer is
  forbidden to perform it. The duplication is why the waste is currently doubled; it is not why
  the read goes. (c) Delete the output the caller never consumes: the markdown
  `## PR Review` block, which duplicates the JSON the caller actually reads, and the PR Draft,
  which `SKILL.md` Step 5 re-drafts from work context anyway. Then re-point the four goals at what
  the ledger shows this reviewer catches — governance bookkeeping coherence — rather than the
  product-code concerns they are currently written for.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `pr-review-payload-discovery.md` §2 and §3
- **Norm decision, recorded rather than assumed** (`architecture.md`: *goals and verification bind;
  prescribed method is advice*): the goal re-point changes what the reviewer's goals **bind to**,
  which is normative content and not method, so it does not ride as documentation freshness.
  `[DECISION: the PR reviewer's four goals are re-pointed from product-code concerns to the
  governance-bookkeeping coherence the ledger shows they actually catch — 88% of 279 findings, and
  0.7% on the stated debug-code/stray-file bullets | the norm's why is that goals bind and method
  advises, so a goal describing a subject the reviewer does not review is a binding statement that
  is simply false, and leaving it standing costs a reader's trust in the whole table; the
  `.prawduct/` surface is non-judgeable by the coverage algebra, so no Critic layer reviews it and
  this reviewer is its only reader | user can veto/override]`
- **Surfaces this touches** (enumerated up front, because a protocol change cascades and several
  of these carry token-budget guardrails): `plugin/skills/pr/review-protocol.md`,
  `plugin/skills/pr/SKILL.md` Steps 3 and 5, `plugin/methodology/building.md` where it names the
  PR reviewer's reads, and the budget pins in `tests/test_v5_methodology.py`.
- **Deliverables:** `plugin/skills/pr/review-protocol.md`, `plugin/skills/pr/SKILL.md`,
  `plugin/methodology/building.md`
- **Sweep the step-6 references in the same file, not just the step.** Deleting a numbered step
  leaves every sentence that cites it by number dangling, and the worst carrier is in the file
  being edited — the Learnings Cross-Check paragraph says "You read the learnings for context
  (step 6)", a hundred lines below the deletion. Grep `review-protocol.md` for `step 6` **before**
  the sibling files, then renumber what follows. A cross-file sweep feels exhaustive precisely
  because it crossed files, which is what leaves the same-file carrier standing.
- **Budget note:** this chunk is a net **deletion** from `review-protocol.md`, so where a hard
  ceiling and its drift pin both read the same file, lower the ceiling in the same commit — an
  unratcheted slack is a loan the next edit collects silently and green. Assert between the two
  tables, not on one of them.
- **Tests:** `tests/test_pr_reviewer.py`, `tests/test_pr_evidence_contract.py` — the evidence
  contract is unchanged by this chunk and must be pinned as unchanged (the JSON schema the caller
  validates is the surviving output, so cutting the markdown block must not move it); a negative
  assertion that step 6's learnings read is gone, **paired with a positive assertion** that the
  Learnings Cross-Check paragraph naming who *does* own that scan survives — a bare negative
  forbids everything its wording matches.
- **Acceptance criteria:** the declared suite passes; the protocol's activation section names the
  payload command and no longer names `learnings-files`; `tests/test_pr_evidence_contract.py`
  passes unmodified.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Dispatch as a named agent that does not inherit `CLAUDE.md`

- **Description:** A non-fork subagent inherits every level of the `CLAUDE.md` hierarchy including
  project rules, so ~27k tokens of `core.md` plus the root anchor reach a reviewer whose
  instructions are `review-protocol.md` and which is forbidden to use them. A named plugin agent
  with `omitClaudeMd: true` removes that inheritance and lets the tool allowlist be scoped to what
  the role needs.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `pr-review-payload-discovery.md` §2
- **Foreign API:** claude-code-subagent-frontmatter
- **Precedent, and the rule it contradicts:** `plugin/agents/critic-reviewer.md` is already a
  tool-restricted named plugin subagent with `model: inherit`, so this chunk copies a shape this
  repo ships. A `core.md` rule reads *"Tool-restricted reviewer agents must be context:fork SKILLS,
  not named plugin subagents"* — a bare heading carrying no why, contradicted by the shipped
  `critic-reviewer`. **Name it and settle it, never work around it silently:** if `verify-api`
  confirms the named-agent route, that rule is retired in this chunk with its reason recorded; if
  the probe fails, the rule stands and this chunk becomes a fork-skill instead. The rule is not
  edited to match whatever this chunk happens to build.
- **Deliverables:** new `plugin/agents/pr-reviewer.md`; `plugin/skills/pr/SKILL.md` Step 3 (spawn
  the named agent rather than a generic one); `.claude/rules/learnings/core.md` (retire or keep the
  contradicted rule, per the probe); new `tests/test_pr_reviewer_agent.py`
- **The allowlist must carry the backlog cache grant.** `plugin/skills/backlog/cache-reads.md`
  already wrote the warning for exactly this move — add the grant in the same edit that narrows
  the tool set. Scoping an allowlist is where a capability silently disappears, and this one is
  load-bearing: `review-protocol.md` marks **R-2** as the check no other layer in the pipeline
  owns, so an agent that cannot read the backlog cache reports "reconciled" having reconciled
  nothing. The grant is `Bash(prawduct-hook backlog cache-query *)` plus its
  `python3 plugin/bin/prawduct-hook` form, as `critic-reviewer.md` carries it. Pin it: a test
  asserting the narrowed allowlist still admits a cache read, red-verified by removing the grant.
- **Tests:** **port `tests/test_critic_reviewer_agent.py` first, then add** — that file enumerates
  the branches the precedent's design creates (frontmatter shape, tool allowlist bounds, the
  write-path restriction, the dispatch name matching what the caller spawns), and citing a
  precedent without carrying its coverage is how a module borrows a design and leaves its tests
  behind. Then the new case: `omitClaudeMd: true` is present and asserted by property, not by a
  literal string match that any rewording satisfies.
- **Acceptance criteria:** the declared suite passes; a dispatched review completes and writes its
  evidence file with the agent's restricted tool set.
- **Done when:**
  0. verify-api — confirm `omitClaudeMd` is honored for a **plugin-supplied** agent definition, by
     reading the current Claude Code subagent documentation AND dispatching one throwaway agent
     that reports whether it can see a sentinel string present only in `core.md`. A documentation
     sentence is an assertion; the probe is the verification. If the probe cannot distinguish the
     two cases, say so and take the fork-skill route rather than recording a guess as settled.
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Concurrency, measurement, and the norm reconciliation

- **Description:** Close the loop. Dispatch the PR review concurrently with the cumulative Critic,
  which `nonfunctional-requirements.md` § Performance already requires and `SKILL.md` does not do
  (**#678**). Then measure what the previous four chunks bought, record it, and reconcile the two
  norm surfaces this work touched.
- **Depends on:** Chunks 01–04
- **Artifacts consumed:** `nonfunctional-requirements.md` § Performance,
  `pr-review-payload-discovery.md` §4 and §5
- **Type:** cumulative-final
- **Deliverables:**
  - `plugin/skills/pr/SKILL.md` Steps 2 and 3 — concurrent dispatch, with the reconcile point
    stated and the one genuine ordering dependency named rather than implied (a blocking cumulative
    wastes the concurrent PR review's tokens; that is a cost, not a correctness bar, and it is the
    trade to state out loud).
  - `plugin/methodology/building.md` — the gate and the review are concurrent-safe.
  - `.prawduct/change-log.md` — one entry tagged `scope=pr-review-payload`, whose body covers
    **every** chunk this bundle ships, because the body is the release note.
  - `.prawduct/artifacts/nonfunctional-requirements.md` — the measured before/after against the
    ≤ 7-minute boundary target, as a dated measurement plus the command that re-derives it, never
    a present-tense state claim.
- **The `pr-scoped` ruling, surfaced not made:** `nonfunctional-requirements.md` records a
  2026-09-16 owner ruling keeping the `pr-scoped` mode, which `grep -rn "pr-scoped" plugin/` shows
  has not existed in the code since the `pr-scoped`/`pr-full` → `pr` collapse; its 30 ledger rows
  end 2026-07-10. The removal arm's first evidence-based run graded a control that was already
  gone. **This chunk writes no fix.** It presents the finding to the owner with the two readings —
  re-run the arm against `pr` with this plan's measured numbers, or record that the keep was about
  a retired subject — because amending a norm to match the tree is the laundering tell, and a
  governance change cannot supply its own authority.
- **Tests:** `tests/test_v5_methodology.py` (the concurrency sentence and the budget pins);
  `tests/test_pr_reviewer.py`. A test that asserts the ordering claim must assert the **property**
  — that no step states a data dependency the other direction — not one spelling of the sentence.
- **Acceptance criteria:** the declared suite passes; `tools/pr-review-yield.py` on this repo
  reports at least one **measured** PR review; the measured duration of this plan's own PR review
  is recorded beside the 420s pre-change median, including if it missed the projection; `#652` and
  `#678` are updated through `/prawduct:backlog`.
- **Done when:**
  0. Re-run `tools/pr-review-yield.py` and `tools/measure-consumer-overhead.py ../discodon --prs`
     and record both readings with their dates
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can see:** `tools/pr-review-yield.py` flipping a row from self-reported to
measured — the first time this repo can state a review duration as a fact rather than as the
reviewing model's estimate.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review passes. Chunk 05 is
`Type: cumulative-final`, so its review is the one `/prawduct:critic cumulative` that gates
`/prawduct:pr create`.

- **After Chunk 01:** confirm the measurement loop before optimizing against it — a change graded
  by a broken instrument is worse than an ungraded one.
- **After Chunk 03:** the largest prose change and the one carrying a recorded norm decision.
  Re-read `review-protocol.md` end to end in the order an agent reads it, not as a diff.
- **After Chunk 05 (cumulative):** full-bundle review, and the dogfood run — this plan's own PR is
  reviewed by the reviewer it rewrote.
