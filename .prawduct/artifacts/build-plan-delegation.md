---
artifact: build-plan
version: 2
scope: delegation
branch: fix/delegate-verification-ceiling
depends_on:
  - artifact: delegation-and-verification-cost-discovery
partition: serial — 01, 02 and 04 all edit the same methodology and skill files; 03 is independent but too small to brief
last_validated: 2026-08-21
---

## Requirements Confidence

**Level:** High

**Why:** Problem, success and scope each state in a sentence, and the design was ruled
three times by the owner into a narrower shape than it started (`§7` of the discovery
artifact). What prawduct will and will not own is settled, and the out-of-scope list is
explicit enough to refuse a re-proposal.

**Open assumptions / unknowns:**

- `[ASSUMPTION: guidance placed where the coordinator already stops changes behaviour where
  guidance in a file has not | HIGH impact | falsifiable]` — the load-bearing bet. The
  evidence that the weaker form fails is 0.34% delegation across 31,220 tool calls.
- `[ASSUMPTION: learning "a new framework-wide DEFAULT must land in the session digest"
  does not apply here | MED impact | user can override]` — its stated failure is that
  *place-once preferences and the thin anchor* don't reach migrated repos. These rules ride
  `building.md` and `planning.md`, which ship with the plugin and are read on demand by
  every governed repo. The owner ruled against a digest line on cost grounds; this records
  why the learning does not overturn that rather than leaving the two silently in tension.

**What would raise confidence:** re-running the transcript sweep a few build cycles after
this ships. It answers the load-bearing assumption directly and cheaply — the miner is
`scratchpad/mine_agents.py` in this session's scratch, worth re-authoring rather than
preserving.

## Status

- [x] Chunk 01: The guide exists and is reachable from where a builder already is
- [x] Chunk 02: The question arrives where the coordinator already stops
- [x] Chunk 03: The record can say it was degraded
- [ ] Chunk 04: Policy and promotion

Context: Plan written 2026-08-21 against `delegation-and-verification-cost-discovery.md`,
all rulings recorded there in §7. The verification-ceiling correction itself already
landed ahead of this plan (`008bd5f0`, `f348922c`) — it was ruled a stop-the-bleeding fix
and is R17, not a chunk.

Chunk 01 done 2026-08-21, in two passes: the guide, routing at four sites, the `building.md`
pointer — then reopened at its own checkpoint and amended with **R18**, the default on *whether* to
delegate, which the first pass had no answer for at all. `building.md`'s permissive line is now that
default rather than another permission.
Two rulings landed with it and bind the rest of the plan. **The digest ruling was
narrowed, not reversed** — `delegation` is named in both always-injected rosters
(CLAUDE.md and `session-digest.md`), because a roster omitting a live topic is false on
the one surface an agent reads before opening anything; a delegation *rule* there stays
ruled out. The owner's words: "start this way and dogfood, and if we need to promote to
more tokens in CLAUDE.md we will" — so the injected ceilings were deliberately NOT
ratcheted with the cut that funded it, and that headroom is reserved for the promotion.
**The budget audit the plan ordered was run and it paid** (−53 against a +40 pointer,
`building.md` ceiling ratcheted 4800 → 4775), so Chunks 02-04 inherit no budget debt.
Next: Chunk 03.

Chunk 02 done 2026-08-21. `planning.md` gains `### Partition: Serial or Delegated` inside Build
Planning — the plan-time question (*what would prove this chunk on its own?*), the record-either-way
rule, the unconditional disclosure, the four ask-reasons as a **closed list** against three standing
negatives, and the durable-approval offer. The decision lands in a new plan-level `partition:`
frontmatter field, which this plan now carries itself. **R6's second placement was not in this
chunk's description and is now built:** the question also fires at a chunk close, from
`building.md`'s delegation-section *preamble* — the Critic's one finding (R-1, warning, fixed not
accepted) was that a first draft put it in the `**Parallel chunks:**` bullet, which reaches only a
coordinator already fanning out, while the reader it exists for is the one whose plan says serial.
The guarding test now pins the preamble rather than the section, and was proved red on that exact
regression. `building.md`'s ceiling did not move.

Chunk 03 done 2026-08-21, and it is the only code on the branch. `.test-evidence.json` gains an
optional **`degraded`** field carrying the reason a run did not cover what its counts imply, set by
`test-evidence record --degraded "<reason>"`; presence is the flag, so a blank reason is refused by
both the CLI and the schema. Both evidence readers refuse a degraded record from the one body they
share — session-freshness and the base-advance transfer have to agree about what a run SAYS — and
`--no-rerun` carries the flag forward, without which a restamp would launder a degraded record
clean while running nothing. `verify_coverage` deliberately does NOT refuse one: at `referenced`
level its answer is tree-derived, so which tests executed cannot change it; the docstring names the
`executed`-level condition that would retire the reasoning. `delegation.md`'s *unattributable
green* — the one anti-pattern whose remedy was not a judgment call — now names the flag.
**Acceptance was met on a real degraded run**: a genuine partial run of this repo's own suite that
exited 0 having executed a fraction of what it collects, ingested, flagged, and refused by
`test-status`. The checkpoint this chunk owed fired: an ordinary record is untouched, proved both
by a test that goes red when the writer emits `false` instead of omitting the key, and on this
repo's own record.
Critic: 0 blocking, 0 warning, 1 note — that `learnings.md` still asserted relax-only as a property
of the *gate*, which `degraded` narrows to the tree-validity clause. Fixed in both learnings files
rather than accepted.
Next: Chunk 04.

## Scaffolding

### Project Initialization

None — this extends an existing plugin. No new dependencies, no new runtime surface.

### Build & Test Configuration

Unchanged: `python3 -m pytest tests/ -q` from the repo root. Chunks 01-02 and 04 add cases
to the existing methodology and doctor test modules; Chunk 03 is the only one touching
`plugin/lib/`.

### Verification Strategy

Chunks 01-02 and 04 are prose and routing, so their real verification is **invocation, not
assertion**: run `/prawduct:methodology delegation` and confirm it opens the guide; draw a
plan and confirm the partition prompt fires; run `/prawduct:doctor` against a sibling repo
(discodon is the richest, samsung the sparsest) and confirm the proposal is recognisable
rather than generic. Tests pin that the surfaces exist; only a human reading can say the
guidance is good, and that judgment is the Critic's.

Chunk 03 is verified by a record written from a real degraded run, not a synthetic one.

## Project Structure

```
plugin/
├── methodology/delegation.md        # new — the guide (Chunk 01)
├── methodology/building.md          # pointer (01), already carries the ceiling rule
├── methodology/planning.md          # partition + disclose prompts (02)
├── skills/methodology/SKILL.md      # routing, FOUR sites (01)
├── skills/doctor/SKILL.md           # detect / propose / ratify (04)
├── templates/project-preferences.md # delegation policy rows (04)
├── lib/gates.py                     # the degraded record's schema + both readers (03)
└── bin/prawduct-hook                # `record --degraded` — the writer (03)
```

### Module Boundaries

The guide owns the canonical detail; `building.md` and `planning.md` carry pointers and the
one rule each already needs inline. **Nothing that names a consumer's test command, runner,
marker or tier may enter any of these files** — §6 of the discovery artifact is the bar, and
it is the single easiest thing to violate while writing helpful-sounding prose.

## Build Chunks

### Chunk 01: The guide exists and is reachable from where a builder already is

- **Description:** The thin slice: a guide with real content, routed, and pointed at from
  the file a builder is already required to read. A guide nothing reaches is not a
  deliverable, which is why routing and the pointer land here rather than later.
- **Depends on:** none
- **Artifacts consumed:** `delegation-and-verification-cost-discovery.md` §4.1-4.4, §4.8;
  **R18** (added 2026-08-21 at this chunk's own checkpoint — see below)
- **Deliverables:** new `plugin/methodology/delegation.md` — **when to delegate and when to stay
  serial (R18)**, what a delegate is for, the considerations as
  questions, the seven anti-patterns each with its tell, the qualitative brief contract;
  routing in `plugin/skills/methodology/SKILL.md` at **four sites** (frontmatter
  `description`, `argument-hint`, the topic list, the phase list); a pointer in
  `plugin/methodology/building.md` § Delegating Work to Subagents
- **Tests:** the guide is registered in `LAST_MEASURED_TOKENS` with a budget; every
  anti-pattern carries a tell (the shape check that makes them fire rather than read as
  true); all four routing sites name the topic — a three-of-four edit is the predictable
  miss and the test is what catches it
- **Acceptance criteria:** `/prawduct:methodology delegation` opens the guide; `building.md`
  reaches it; suite green
- **Budget note — do this BEFORE spending the pointer's tokens:** `building.md` sits at
  4774 against 4800. Learning *"a token budget is raised only when the framework is provably
  better for the raise and upleveling has no headroom left — cut the class, not the words…
  what looks unaffordable is usually history"* was **not** applied before that ceiling was
  raised. Audit for a removable class first (dates, running tallies, worked examples,
  definitions another file owns) and give back what you find. Do not fund the pointer by
  moving existing prose into the new guide — that is the *"never fund a budget by moving
  prose between files"* rule, and it would make the raise retroactively unearned.
- **Amended 2026-08-21, mid-chunk, by the checkpoint below doing its job.** The guide as first
  built answered *how* to delegate and never *whether* — it went straight to the verification
  contract. R18 (a stated default, the cases that defeat it, and the route to
  `project-preferences.md`) is the fix, and it amends R3's questions-not-rules framing at one
  point: a default is a rule, and it is the one thing questions cannot supply, because an agent
  with no default answers "should I delegate?" by not delegating. **This is the second time the
  permissive-line approach has been tried** — `building.md`'s "when chunks are independent and
  parallelizable" was in force for the whole 0.34% measurement — so R18 is a default, not another
  permission. Its plan-time form is Chunk 02's to carry.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The question arrives where the coordinator already stops

- **Description:** The placement bet, made real. The delegation question fires when chunk
  boundaries are drawn, the partition decision is recorded either way, and a plan that will
  delegate discloses it when presented — asking only on an enumerated reason.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `delegation-and-verification-cost-discovery.md` §4.5, §4.6;
  requirements R6-R11
- **Deliverables:** `plugin/methodology/planning.md` — the partition prompt at chunk-boundary
  drawing, and the disclose-and-consent rule at plan presentation; the four reasons to ask
  and the three standing negatives, as a **closed list**; `plugin/templates/build-plan.md`
  gains the partition decision as a plan-level field so "serial, because X" has somewhere to
  be recorded rather than being merely encouraged. **Plus `plugin/methodology/building.md`,
  which this chunk's description did not name:** R6 states TWO placements and the chunk
  covered only the plan-time one. A chunk close is the other, and `building.md` is the only
  file a coordinator reads there — so its delegation section re-raises the partition
  question, carrying the trigger while the guide keeps the why. Paid for in place; the
  ceiling did not move.
- **Tests:** the ask-condition is enumerable (a test that the list is closed, not open-ended
  — an open condition is what makes an agent ask defensively every time); the template's new
  field round-trips through whatever reads plan frontmatter
- **Considered and deliberately NOT built:** a Critic check that a plan records a partition
  decision. `partition:` is a record, not a gate — ruling 6 is that prawduct states the goal
  and not the mechanism, and `skills/critic/review-protocol.md` has 5 tokens of headroom, so
  arming it is a budget decision for the owner rather than a line to slip into this chunk.
  Recorded here so the absence reads as a decision rather than as a miss.
- **Acceptance criteria:** drawing a plan surfaces the partition question; a delegating plan
  presented to the user discloses count, isolation, what is touched, and what delegates will
  not do; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The record can say it was degraded

- **Description:** The one chunk with code. `.test-evidence.json` can today record a green
  for a run that silently dropped part of its suite. The framework's own record gains the
  vocabulary to say so; the coordinator supplies the observation.
- **Depends on:** Chunk 01 (the anti-pattern the record's absence explains)
- **Artifacts consumed:** requirements R16 and its design note
- **Deliverables:** a `degraded` field on the evidence record with a required reason;
  `plugin/lib/gates.py` treats a degraded record as not-fresh-enough rather than as a pass;
  the guide's *unattributable green* anti-pattern points at how to set it
- **Design constraint, already settled — do not relitigate:** junit reports a test count and
  has no notion of *collected*, so "compare collected to reported" is unavailable from the
  report. Comparing against the last recorded count is noisy on legitimate test-count
  changes; parsing a runner's summary requires per-runner knowledge that §6 forbids. The
  record therefore **carries** the flag rather than deriving it — owner-ruled.
- **Tests:** a degraded record does not satisfy the gate; a degraded record without a reason
  is refused; an ordinary record is unaffected (the regression that matters — this touches
  the path every governed repo's Stop hook runs)
- **Acceptance criteria:** a record written from a genuinely degraded run reports as
  degraded and does not pass the gate; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Policy and promotion

- **Description:** Where a project records what it decided, in its own words, and how a
  working practice becomes durable instead of being retyped every session.
- **Depends on:** Chunks 01-03
- **Artifacts consumed:** `delegation-and-verification-cost-discovery.md` §4.7; R12-R14
- **Deliverables:** `plugin/templates/project-preferences.md` gains delegation policy rows —
  prose, in the project's vocabulary, including `off` and pre-approved — plus their
  Enforcement-table entries; `plugin/skills/doctor/SKILL.md` gains detect-and-propose from
  what the repo already encodes (markers, scripts, Makefile/justfile targets, CI jobs) and
  the one-step promotion of an observed practice to a ratified preference
- **Tests:** the proposal is derived from repo evidence rather than emitted unconditionally
  (a proposal that always fires is noise, and this repo's own orphan-term hook is the
  cautionary tale `norms.md` cites); `off` and pre-approved are both honoured
- **Acceptance criteria:** `/prawduct:doctor` on a sibling repo proposes something
  recognisable as that repo's actual practice; approving it writes a preference row; suite
  green
- **Type:** cumulative-final
- **Done when:**
  0. Re-read §6 of the discovery artifact against the whole branch diff — the failure mode
     of a guidance feature is mechanism creeping back in as helpful prose
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `/prawduct:methodology delegation` and read the guidance that
will govern every subsequent delegation — including in this plan's own later chunks, which
is the honest test of whether it is any good.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 04's
`cumulative` review makes the branch PR-ready; `/prawduct:pr create` when asked.

- **After Chunk 01:** confirm the guide reads as considerations rather than rules. If it has
  become a procedure, that is the design failing quietly and it is cheapest to catch here.
  **Fired, 2026-08-21, and caught the opposite defect** — not procedure but *incompleteness*: the
  guide answered how and never whether. Worth recording, because the checkpoint was written to look
  for one failure and its value was catching a different one. A checkpoint that names a specific
  failure still has to be read as "is this good", or it only ever finds what it was told to expect.
- **After Chunk 03:** the only code on the branch, and it sits on the path every governed
  repo's Stop hook runs. Confirm an ordinary record is untouched.
- **Chunk 03 is independent** of 01, 02 and 04 and closes a hole that is live today. If this
  branch stalls, pull it forward rather than letting it wait.

## Delegation

**This plan is built serially, by one agent.** Recorded rather than assumed, per its own
R7 — and worth stating plainly given the subject: the chunks are dependency-ordered
(01 → 02 → 04, with 03 independent but small), and the only genuinely parallel pair is 02
and 03, which together would not repay a brief. The feature exists so that a *plan that
should* fan out says so; this one should not.
