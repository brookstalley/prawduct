---
artifact: build-plan
version: 1
scope: review-round-pricing
depends_on: []
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "Review wall-clock is a P0 constraint; cost = unit-cost × run-count, both levers → conforms, and this plan pulls run-count. Every part exists to stop a round being started, never to make one cheaper. The one place it SPENDS unit-cost is Chunk 03's addition to the PR reviewer's payload; that file carries no token ceiling (verified — the five ceilings in `test_v5_methodology.py` cover `building.md`, the CRITIC `review-protocol.md`, `goals-1-3.md`, `review-cycle.md` and `framework-checks.md`, not `skills/pr/review-protocol.md`), so the spend is real but unconstrained, and it is ~40 words against a 7-minute boundary budget."
      - "A new control names its expected yield AND emits that yield observably → CONFORMS for all three controls, and the contrast with the predecessor plan is the point. `build-plan-review-loop-carriers.md` recorded TWO departures on this norm because its controls fired into stderr and landed in no store. These three are answerable from the evidence store without recording anything new: the yield is rounds-per-scope, and `prawduct-hook review-stats` already groups by scope. The query is cited rather than its output (learnings L351), and the baseline is whatever the store holds at the merge commit — not a number copied into this plan, which would be the very defect Chunk 03 of the predecessor plan shipped to stop."
      - "`cost-of-commit`'s own firing rate is NOT observable, and that is recorded rather than waived → the yield norm is about controls that FIRE and produce findings; a query command answers on demand and emits no finding, so there is no fire-rate to ratchet against. Applicability is recorded, not assumed (planning.md), so: INAPPLICABLE, because the removal test the norm exists to enable — 'has fired repeatedly with no blocking finding' — has no referent for a command the builder invokes deliberately. If it is later wired into a hook that runs it unasked, that reading expires and it becomes a firing control."
      - "State-file growth past its size threshold is an advisory, never a hard block → CONFORMS, and the first writing of this row said 'inapplicable — no chunk writes to a state file', which is true of Chunk 01 and false of Chunk 02. `next_action_line` grew by roughly a hundred words on BOTH arms (the price sentence, the accept route, the ride-along), and that string does not stay in a derived view: `ledger.ledger_append` sets `\"review\": record` from the whole `.critic-findings.json` record, so every `review.critic` line in the append-only `.governance-ledger.jsonl` carries it, and `briefing.py` prints it verbatim as `NEXT-ACTION:` in every session briefing that has a findings file. Disposed on the norm's actual obligation: the growth is real and per-review, no hard block was added, and the cost is the advisory kind this norm permits. Nothing shipped is wrong — the record was."
      - "Recorded because the repo has already paid for this exact correction once: `build-plan-review-loop-carriers.md` wrote the same 'inapplicable' premise, discovered the same `ledger_append` copy, and corrected its entry in writing. Repeating the miss one plan later means the deliberation was owed and skipped, not that the conclusion changed. It also answers the contract-surface question: `next_action`'s consumers are `fact_to_cache_record` → the findings cache → `ledger_append` and `briefing.py`, and only the first was reasoned about when the string was widened."
  - artifact: observability-strategy
    dispositions:
      - "Severity-prefix vocabulary with stdout = agent-facing, stderr = user-and-diagnostics → conforms. `cost-of-commit` is read by an agent deciding whether to commit, so its verdict goes to **stdout**; the gate's round tally rides the existing `uncovered:` stderr block where the rest of the diagnosis already lives. No new prefix is coined."
      - "Text emitted into a governed product names no prawduct-internal identifier → conforms, and Chunk 03 is where it bites hardest, because the PR reviewer's prose is copied into findings a product's builder reads. The addition names the plain consequence (fixing these re-opens the cumulative gate) and no requirement id; ids stay in this plan and in non-emitted docstrings."
      - "The governance ledger has a single writer (`ledger-append`) → conforms. The pricing helper is a pure READER of the ledger. No chunk appends an event."
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms, and this is the load-bearing check. All three controls are ADVICE: `cost-of-commit` answers a question and gates nothing; the tally and the parity line are advisory prose inside messages no gate reads. None appears in `unresolved_blocking`. **The failure posture follows what the command produces** (learnings L24 ruling): an unreadable or too-thin ledger must degrade to 'the price is unavailable', never to a wrong number and never to a refusal."
      - "An independent reviewer never mutates the session it reviews → conforms, untouched. Nothing here writes to a review's session state; the `critic-begin`→`critic-consolidate` window is unmodified."
      - "Every fact has one home; every other mention is a reference → conforms, and it drove the chunk split. 'What a review round costs in this repo' gets exactly ONE home — the pricing helper in `telemetry.py` — consumed by the CLI command, the gate tally, and `next_action_line`. Three call sites computing their own median is the drift this norm exists to stop."
      - "Goals and verification bind; prescribed method is advice → invoked pre-emptively for Chunk 02. The goal is that a builder reading a repeat round's gate output can tell it is a repeat; whether that is a count, a duration, or both is the builder's call at implementation time."
      - "Local-first: no network, no daemon → conforms. The ledger is a local file."
      - "Prawduct guides and reviews; it never implements → conforms. `cost-of-commit` reports on the product's own paths and writes nothing into them."
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms, and this plan is unusually clean on it: NOTHING here writes at all. `cost-of-commit`, the pricing helper and the round tally are pure readers; the three message changes emit to stdout/stderr. No chunk creates, edits, or deletes a file in a governed repo."
      - "Written in Python, never specific to Python; gates dispatch per file by language → conforms. Every classification added routes through `coverage_algebra.is_judgeable_path`, which decides by PATH and never opens a file or infers a language — so `cost-of-commit` answers identically in a Go or TypeScript product. The round tally is language-blind by construction (it counts facts, not code)."
  - artifact: data-model
    dispositions:
      - "No persisted schema is introduced or changed → conforms across both chunks. The pricing helper derives from the ledger's existing event shape via `telemetry._extract_row`; Chunk 02's round tally reads two fields `build_fact_body` already writes (`dispatch_commit`, `duration_seconds`). Neither adds a field, and no reader of a NEW shape is created."
      - "Governance verdicts are computed from the append-only fact ledger, never from mutable model-written state; no model sits in a fact's write path → conforms. Everything added is a READER — the tally consumes the same fact list the gate already read, and no chunk appends, edits, or authors a fact. The one model-written input in this area (the reviewer's partial) is untouched."
      - "Facts are immutable and append-only; a state change is a new fact → conforms, untouched. No chunk mutates a fact, and the tally deliberately derives the round count at call time rather than persisting a counter — a stored count would be exactly the mutable state this norm forbids, and would drift from the facts it summarizes."
      - "Derived views are disposable and never authoritative — no gate reads a view to reach a verdict → conforms, and this is the load-bearing check for Chunk 02. `.critic-findings.json`'s `next_action` gains the round price, and no gate reads that file; the gate's own tally is printed prose that no verdict consumes. Nothing added can move a verdict."
      - "A fact written by a newer schema than the reader is a loud block, never silently dropped → inapplicable, because no new reader of the store is introduced. `count_branch_rounds` is handed the fact list the gate already obtained through `evidence.read_facts` + `_store_precheck`, which performs the schema-ahead block before any caller sees a fact. Reading the store directly would have made this applicable; taking the caller's list is what keeps it out."
      - "Two stores, two lifetimes: shared committed answers distinct from per-clone gitignored nags and caches → conforms. Two stores are read for two different questions — the evidence store for which rounds THIS BRANCH bought, the governance ledger for this repo's median round cost — and neither gains a writer or a cross-reference. The gate message labels which figure came from which, so the reader is never handed two unattributed durations."
      - "`backlog_service_repo` selects the authoritative backlog store → inapplicable. No chunk reads or writes a backlog on either backend."
  - artifact: api-contract
    dispositions:
      - "Added late, and its absence was itself the defect: this plan adds a CLI subcommand AND a new `--json` payload, which is the most obvious entry into this artifact's jurisdiction, and the omission is why `cost-of-commit --json` shipped registered in § Operations but not in the § Inputs & Outputs emitter list. Recorded here rather than quietly fixed, because a `governed_by:` gap explains a class of misses, not one."
      - "Additive-first evolution / tolerant readers → conforms. `cost-of-commit --json` is a NEW payload with no prior readers, so nothing can break on it; the one existing payload touched is `.critic-findings.json`'s record, which gains `next_action` CONTENT (not a key) and whose readers already tolerate unknown fields."
      - "The exit code is the contract → conforms, and stated explicitly in the registration because this command inverts the usual reading: it exits 0 for every answer it can give, INCLUDING `unknown`, because it gates nothing and a nonzero exit would read as a refusal. 1 is reserved for bad arguments. An advisory that exits nonzero on 'the answer is expensive' would be an authority wearing advice's clothes."
      - "Every `--json` emitter is enumerated with its key set → NOW conforms; it did not when Chunk 01 shipped. The list's own stated reason is that a payload documented only by its exit code is a shape a caller has to reverse-engineer, and the two precedents are both registered despite having no consumer for exactly that reason."
last_validated: 2026-08-05
---

## Requirements Confidence

**Level:** High

**Why:** The problem is measured on a released version, the parent requirement is
open and explicit about what it does and does not cover, and the owner chose the
scope directly (the four parts below) after seeing the measurement. The reporting
agent's account is unusually diagnostic — it names not just what it did but which
sentence it read and where it was standing when it relapsed.

**Open assumptions / unknowns:**

`[ASSUMPTION: the price worth quoting is wall-clock, not tokens | MED impact | user
can correct]` — the reporter argued in tokens (~90k/round). The ledger records
**duration** and not tokens, so a token figure could only be hardcoded, which
learnings L351 and the project's own no-prose-numbers preference forbid. Quoting
minutes is honest and re-derivable; quoting tokens is not. If the user wants a
token figure, the ledger has to start recording one first — that is a persisted-format
change and a separate item.

**What would raise confidence:** N/A for the build. The real signal is post-release:
rounds-per-scope in `prawduct-hook review-stats`.

## The problem, measured

**v3.2.4 shipped the fix for this and a consumer on v3.2.4 still ran six rounds.**
That is the whole reason this plan exists, and it is what separates it from
`build-plan-review-loop-carriers.md`, which targeted the same failure one release ago.

The predecessor plan's diagnosis was that every carrier of the loop-termination rule
was a *pull* carrier. It shipped three *push* carriers: `next_action` in
`.critic-findings.json`, the `NEXT-ACTION:` relay through both protocol files, and the
cumulative gate's fix-churn NOTE. All three landed. The reporting agent **read them** —
it quotes `critic_consolidate.py:301` verbatim. It then ran six rounds anyway and wrote
up why. Five failures, in its words:

1. *"It stated a rule, not a price. I never saw a number."*
2. *"I was locally compliant every single time. Each batch was one commit followed by
   one review. What I violated was starting a new batch. The wording bounds the batch;
   it doesn't bound the sequence."*
3. *"The warning wasn't where the temptation was. When I decided to make the hygiene
   commit, I was reading the PR reviewer's findings — the Critic's NEXT-ACTION wasn't
   on screen."*
4. *"The gate re-fires identically. Block #6 read exactly like block #1."*
5. *"I couldn't price a commit before making it. I learned .gitignore wasn't a free
   edge after committing it."*

**Verified against the code, not taken on report:**

| Claim | Verified |
|---|---|
| `.gitignore` costs a round | **yes** — no `METADATA_PREFIXES` match, not `.md`, so `coverage_algebra.is_judgeable_path` returns True |
| the PR reviewer never mentions round cost | **yes** — nothing in `skills/pr/review-protocol.md` says a non-blocking fix re-opens the cumulative gate |
| the blocking branch quotes no price and no accept route | **yes** — `next_action_line`'s blocking arm says "turns one review into several"; the *zero-blocking* arm is the one carrying `disposition --accept`, the gates-nothing statement, and the free-path list |
| round 5's gate output equals round 1's | **yes** — `check_cumulative_critic`'s `uncovered:` block is a pure function of the current tree state; nothing consults how many rounds preceded it |

**The price, from this repo's own ledger** (`prawduct-hook review-stats`, 439 review
events) — cited as a query, not copied as digits, per learnings L351: the
`verify-resolutions` row carries the median round duration and the blocking count
across those rounds. Read it there; a figure written into this plan would be stale by
the next review and would itself buy the correction round this plan exists to prevent.
The reporter's independent "~5 minutes" is corroborated by that row, which is what
promotes its account from anecdote to measurement.

## Requirements

Parent item: **#600** (filed 2026-08-05, `stage: ready`), whose `related` records #167.

| Req | Source | This plan |
|---|---|---|
| R1 — a builder can learn whether a commit costs a review round **before** making it | reporter failure 5; #167 mitigation 4's structural half (its doc half shipped as `CRT-9B4K`) | Chunk 01 |
| R2 — the price of a round is stated where the round is decided, derived from this repo's history rather than asserted | reporter failure 1 | Chunks 01, 02 |
| R3 — a repeat round does not present identically to a first round | reporter failure 4 | Chunk 02 |
| R4 — the blocking-branch message carries what the zero-blocking branch already carries | reporter failure 1, read against `next_action_line` | Chunk 02 |
| R5 — the round-cost warning appears in the PR reviewer's output, where the relapse starts | reporter failure 3 | Chunk 03 |
| R6 — the routes offered at a finding name the **ride-along**: carrying a small fix into the next chunk's commit, which was going to buy a round anyway | owner, mid-build 2026-08-05 | Chunk 03 (both the PR protocol and the Critic's builder-facing line) |

**R6 arrived mid-build and is recorded here rather than built silently.** The owner's point:
the routes on offer were fix-now (buys a round), accept, and file — and the cheapest real option
was missing. When a plan has further judgeable chunks, a small fix carried into the next chunk's
commit costs *nothing extra*, because that commit buys a round regardless. It is explicitly not
always right (a fix that changes what the bundle claims to ship belongs in the bundle), so it is
offered as an option with its condition attached, never as the default. It applies to Critic
findings and PR-review findings alike, which is why R6 lands on both surfaces in one chunk even
though the message half belongs to Chunk 02's family.

**Out of scope, deliberately — and this is the honest limit of the plan.** #167's
`critic-begin` **refusal** is untouched. Reporter failure 2 (*"the wording bounds the
batch; it doesn't bound the sequence"*) is an argument that **no amount of advice closes
this**, and nothing in R1-R5 closes it either: every part here makes the price legible
to a builder who is free to accept it six times. This is the third round of
advice-improvement on one failure (`CRT-8N5V` prose → v3.2.4 carriers → this plan).
Recorded up front so that if the loop persists after this ships, the conclusion is
already written down: build the refusal, stop improving the message.

## Verification Strategy

Unit tests do not settle whether a message *reaches* anyone, and learnings L349 is
explicit that for instruction deliverables, size and right-words-present guardrails all
pass while the instruction has no effect. So each chunk is additionally verified by
running the real command against real repo state:

- Chunk 01 — `prawduct-hook cost-of-commit` against an actual dirty tree containing
  both a free path and a judgeable one, reading the verdict as a builder would.
- Chunk 02 — `prawduct-hook check-cumulative-critic` on a branch with a real multi-round
  review history, confirming the output differs from a first-round branch's.
- Chunk 03 — read the changed protocol section in full at the point a PR reviewer meets
  it, checking it does not contradict the "do not re-derive the Critic's work" boundary
  three paragraphs above it.

## Build Chunks

### Chunk 01: One home for what a round costs, and a command that answers before the commit

- **Description:** The thin vertical slice, and the only part that removes a judgment
  call rather than adding advice. Two pieces, deliberately together because the second
  is the first's only consumer until Chunk 02: a pricing helper that owns the fact
  "what a review round costs in this repo", and the `cost-of-commit` command that
  prices a specific set of paths. The command wraps the existing pure
  `coverage_algebra.is_judgeable_path` — the classification already exists and is
  already the gate's own predicate, so the command cannot disagree with the gate that
  will later charge for the commit. With no arguments it prices the current
  working-tree changes (the actual question — "does committing *this* cost a round?");
  with paths it prices those.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/telemetry.py` — a pricing helper deriving round cost from the ledger's
    existing rows. Returns the price **and the sample size it rests on**, or an
    explicit unavailable state; it must not report a median over a handful of reviews
    as if it were this repo's price. Degradation names its consequence rather than
    falling silent (learnings L325).
  - `plugin/lib/coverage.py` — the paths→verdict function: which of these paths are
    judgeable, and therefore whether committing them moves coverage.
  - `plugin/bin/prawduct-hook` — new `cost-of-commit [<paths>...]` dispatch, its usage
    string, and its entry in `_EPHEMERAL_SAFE_COMMANDS` (it is strictly read-only, and
    an ephemeral worktree is exactly where an agent needs to price a commit).
  - Verdict on **stdout** (agent-facing, per the observability norm), naming the
    judgeable paths that cost a round and stating plainly that the rest are free.
- **Tests:** unit — a free-only path set reports free; a set containing one judgeable
  path reports that it costs a round and names which path; `.gitignore` specifically
  is judgeable (the reporter's case, pinned so it cannot silently become free); the
  no-argument form reads the working tree; the pricing helper returns unavailable
  rather than a misleading median on a too-small sample, and unavailable is
  distinguishable from free. Human-path output is asserted, not only `--json`
  (learnings L301).
- **Acceptance criteria:** a builder who has staged a change can run one command and
  learn whether committing it will cost a review round, without reading any file and
  without having to know what "judgeable" means. Running it against a `.gitignore`-only
  change answers the question the reporter could only answer after committing.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Verified against a real dirty tree per the Verification Strategy
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: The message knows which round this is, and both branches carry the price

- **Description:** Two message defects with one cause — the messages are pure functions
  of the current tree and never consult how the builder got here. Per learnings L29,
  **one function owns each message and decides which route leads**; the tally is not
  appended to the existing churn NOTE, because advice with an exception stapled on
  still leads with the advice.
- **Depends on:** Chunk 01 (consumes the pricing helper)
- **Deliverables:**
  - `plugin/lib/coverage.py` — derive the round count for the current work from the
    evidence store (review facts on this branch since the merge-base). The
    discriminator stays what moved the tree, never a bare counter — the existing
    `diagnose_fix_churn` already distinguishes churn from genuine outside change, and
    the tally reports alongside that judgement rather than replacing it.
  - `plugin/lib/gates.py` — the `uncovered:` branch states which round this is and what
    the preceding ones cost, so round 5 does not read as round 1.
  - **`cost-of-commit` must be named by the carriers that already reach the builder.**
    Found while building Chunk 01 and recorded here rather than left implicit: a command
    the builder has to already know about is a *pull* carrier, which is the precise
    failure v3.2.4 diagnosed and this plan is the second attempt at. Chunk 01 delivers
    the answer; this chunk is what makes anyone ask the question. It is named in the
    gate's churn NOTE and in `next_action_line`'s free-path sentence, which today
    enumerates free paths in prose the builder must match by hand.
  - `plugin/lib/critic_consolidate.py` — `next_action_line`'s **blocking** arm reaches
    parity with the zero-blocking arm: it already says batch-and-review-once, but it
    does not price the round or name the accept route for the non-blocking findings it
    tells the builder to decide in the same pass. Both arms quote the price from the
    Chunk 01 helper, never a literal.
- **Tests:** unit — the blocking arm names the price and the accept route; a first-round
  branch and a fifth-round branch produce different gate output; the tally degrades to
  silence-with-a-reason, not to a wrong count, when the store is unreadable; **no arm
  of either message contains a hardcoded duration** (the regression this repo has
  already paid for twice — assert the wrong form is ABSENT, not merely that the right
  form is present, per the gate-message sweep in `learnings-detail.md`).
- **Acceptance criteria:** a builder meeting the gate on round 5 is told it is round 5
  and what rounds 1-4 cost; a builder meeting a blocking finding is told what fixing it
  will cost and how to accept the findings that gate nothing.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Verified against a real multi-round branch per the Verification Strategy
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: The warning where the relapse starts

- **Description:** The reporter's third failure is the cheapest to fix and the one no
  previous plan addressed: it was reading the **PR reviewer's** findings when it decided
  to make the commit that re-opened the gate, and the PR reviewer's protocol has never
  said that fixing its own non-blocking findings costs a Critic round. The addition sits
  under the reviewer's existing scope boundary, which already tells it not to re-derive
  the Critic's work — this extends that logic to the reviewer's own output rather than
  contradicting it.
- **Depends on:** none (independent of 01 and 02; ordered last so its review is the
  bundle's cumulative pass)
- **Deliverables:**
  - `plugin/skills/pr/review-protocol.md` — the reviewer's non-blocking findings carry
    the consequence: acting on them re-opens the cumulative Critic gate, so they are
    batched with anything outstanding or accepted. Plain language, no requirement id
    (the emitted-text norm — this prose is copied into findings a product's builder
    reads).
- **Tests:** prose pins — the statement is present, and it is positioned where a
  reviewer reaches it **before** writing findings rather than after (the placement
  failure the predecessor plan hit in `goals-1-3.md`, where a correct rule sat below
  every section that needed it). Ordering is what gets asserted, not mere presence.
- **Acceptance criteria:** a PR reviewer about to file a NOTE has already read what
  filing it will cost the builder.
- **Type:** doc-only, `cumulative-final`
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Read in full at the reviewer's entry point per the Verification Strategy
  3. `/prawduct:critic cumulative` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

## Status

- [ ] Chunk 01: One home for what a round costs, and a command that answers before the commit
- [ ] Chunk 02: The message knows which round this is, and both branches carry the price
- [ ] Chunk 03: The warning where the relapse starts

**Chunk 01 is complete** — committed as `89c9c8f`, suite green at that tree (the evidence store
records pass/fail per tree; `prawduct-hook test-status` answers for the current one), verified
against a real dirty tree per the Verification Strategy (the reporter's `.gitignore` case answers
`costs-a-round` in one command; a doc-only set answers `free`). Status checkboxes above stay `[ ]`
until the release regenerates them — `views_enabled` is set, so the change-log entry tagged
`chunks=01` is what records completion.

One review round, gate-required, not warning-driven: `rev-20260805T180741Z-dfcbc2f5` — 0 blocking,
2 warnings, 3 notes. **Two of the five were already fixed by the deep-scrub running concurrently
with the review**, which is `building.md`'s "scrub while it runs, it often pre-resolves findings"
behaving as advertised; they are dispositioned as stale-against-HEAD rather than re-fixed. The
directory-argument warning and the misattributed ledger diagnostic were fixed in the same batch. No
second round was started, and none was required.

**Chunk 02 is complete** — the tally leads the uncovered block (derived from the branch's own
review facts, placing dirty-tree rounds by `dispatch_commit`, undercounting at the merge-base by
documented choice), both arms of `next_action_line` carry the round price and the accept route, and
`cost-of-commit` is named by the two carriers that already reach a builder mid-commit. Verified
against this branch's real gate output per the Verification Strategy — which is where the singular
grammar defects were caught, no unit test having run it at *n*=1. The free-path enumeration in
`next_action_line` was deleted rather than extended: it was a second authoritative copy of
`is_judgeable_path`, and its drift-guard test is now a pin that it stays deleted. One pre-existing
hardcoded duration (`_BATCH_FIX_DIRECTIVE`'s "5-10 minute rounds") was removed on the way through,
found by widening the no-hardcoded-duration sweep — which is scoped to price-bearing surfaces, not
whole modules, because those modules also carry reviewer-liveness durations that are expectations
rather than prices.

**Chunk 03 is complete** — the round-cost statement sits above every finding-producing section of
`skills/pr/review-protocol.md`, with ordering asserted rather than presence. Its bound is delegated
to `cost-of-commit` rather than restated: the first draft claimed a `.md`-only fix moves no
coverage, which is false for the governance-protected `.md` a product reviewer meets, and reading
the paragraph as its audience is what caught it. **R6 (the ride-along route) landed here too**,
across both the PR protocol and `next_action_line`'s two arms — recorded as a requirement before
being built, offered with its condition, and explicitly distinguished from the deferral the same
message warns against.

**Two things the next session must know.** First, HEAD's tree is *not* the tree that review
anchored to — the fixes landed after it — so `check-cumulative-critic` will report a gap on this
branch. That is expected and needs no round now: Chunk 03 is `cumulative-final`, and its single
`/prawduct:critic cumulative` spans `merge-base...HEAD` and closes it. Do not spend a
`verify-resolutions` pass to close it early. Second, finding R-2 was recorded with
`disposition --accept` when it was actually **fixed**; the reason string says so, but the record
type is wrong. The CLI offers only `--accept`/`--file` — a fixed finding is meant to be discharged
by a `verify-resolutions` resolution fact — and the store is append-only, so this is noted rather
than corrected. It gates nothing (R-2 is a warning).

Context: Plan authored 2026-08-05 on `fix/review-round-pricing`, cut from `develop` at
`9dcff56`, from a consumer agent's write-up of a six-round branch on v3.2.4 — the first
post-fix datum on `build-plan-review-loop-carriers.md`. Parent requirement #167
(`CRT-3W6P`) stays open; its structural-refusal half is explicitly out of scope here,
for the reason recorded under Requirements.
