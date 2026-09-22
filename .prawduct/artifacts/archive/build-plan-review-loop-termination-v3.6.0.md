---
artifact: build-plan
version: 2
scope: review-loop-termination
branch: fix/review-loop-termination
partition: serial — all three chunks edit `critic_consolidate.py` and read the coverage/evidence path; 02 consumes a coverage verdict and 03 edits the close copy beside it, so delegates would collide on the same seam
depends_on:
  - artifact: review-loop-nontermination-diagnosis
related_issues:
  - "brookstalley/prawduct#167 — `critic: refuse a full re-round when zero blocking findings remain` (OPEN, stage:design, technical design at `documentation/issues/167-design.md`, 2026-09-15). ADJACENT, NOT OVERLAPPING, and checked rather than assumed: #167's own Scope-out section excludes BOTH Chunk 02 ('any UI/wording change to the NEXT-ACTION carrier itself — untouched') and Chunk 03 ('any change to `diagnose_fix_churn` or its `gates.py` caller'). It works at DISPATCH (a new `begin_review` refusal, exit 5); this plan works at CONSOLIDATION and COMPOSITION. Nothing here edits a file #167's 'Files touched' table claims except `critic_consolidate.py`, and in a different function"
  - "brookstalley/prawduct#167 names Chunk 01's gap as its own blocking dependency: its Scope-out defers 'the true zero-finding-anchor double-verify' because 'it needs observations to become checkable facts first, which is a separate, currently-unfiled gap'. Chunk 01 IS that gap. Landing it lets #167's D3 extend to the case #167 had to scope out — so the two compound rather than collide, and the sequencing is worth stating out loud to whoever builds second"
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never from mutable model-written state → ENGAGED by Chunk 01, and it is the chunk's central constraint: an accepted observation must enter as a fact written by deterministic code from validated reviewer content, never as model-written state a gate later reads. No gate reads an accepted observation at all (it gates nothing by construction), so the norm is satisfied by the weaker path too — but the design takes the stronger one so the record is queryable"
      - "facts are immutable and append-only → conforms; an accepted observation is a NEW fact, never an edit to the review fact that demoted it"
      - "derived views are disposable and never authoritative → conforms; nothing persists a derived verdict (Chunk 03's grant, which would have been computed per call, was cut)"
      - "a governance document reaches a terminal state, never deleted → inapplicable, because no chunk touches plan archival"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → inapplicable, because no chunk writes a backlog item"
      - "a newer-schema fact surfaces as a loud block → ENGAGED by Chunk 01: if the observation disposition lands as a new fact kind or a new field, `evidence status` must still exit 2 on a schema-ahead read. Chunk 01's acceptance names this"
      - "two stores, two lifetimes → conforms; nothing moves between the committed store and the gitignored nags/caches"
      - "`backlog_service_repo` selects the authoritative backlog store → inapplicable, because no chunk reads the backlog"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; cost = unit-cost × run-count, both levers → this plan IS that norm being acted on. Run-count is the target; the measured baseline is in the diagnosis and in `norm_health` (2026-09-16)"
      - "proportionality ratchets both ways; a control that never blocks is removed by default → ENGAGED, and it cut against Chunk 03 as first written: granting coverage REMOVES a control (the mandated round), and no evidence the ledger holds could bound what the file-level grant would let through — one reason the grant was cut (Chunk 03, revised). Nothing that ships removes a control"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable, because no chunk changes a size gate"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → ENGAGED by Chunk 01: an accepted observation is written by the BUILDER through `disposition`, never by the reviewer. Nothing here gives a reviewer subagent a write path it lacks"
      - "authority fails closed; advice fails soft → ENGAGED by Chunk 03 as first written, and decisive: a coverage grant is authority, and failing closed on a degraded read is not enough when a SUCCESSFUL read is only file-level evidence. The grant was cut; what ships is advice (message text) and a predicate left narrow, both of which fail soft by construction"
      - "local-first: no network, no daemon, no third-party runtime dependency → conforms; file reads and git only"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "prawduct is Python but never Python-specific → conforms; no chunk classifies a product file by language"
      - "prawduct guides and reviews; it never implements → conforms; no product code is written"
      - "goals and verification bind; prescribed method is advice → the fix shapes below are the DIAGNOSIS's best guess, made 2026-08-25 before this code was re-read. A builder who finds a better route takes it and records why; what binds is the round-count reduction and the miss-rate floor stated per chunk"
      - "every fact has one home → ENGAGED: the argument for each fix lives in the diagnosis, and the chunks cite it rather than restating it. Chunk 02 specifically must not mint a second home for the span verdict — it renders the value `check-cumulative-critic` already computes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the internal CLI subcommand surface carries no per-subcommand version → conforms; the plugin version covers it"
      - "exit codes are the contract, on a documented and consistent scheme → ENGAGED by Chunk 01 (a new `disposition` arm needs an exit-code meaning); Chunk 03, revised, changes no exit code"
      - "additive-first evolution: flags and `--json` keys are added, never repurposed → ENGAGED by Chunk 01. `--accept` must keep its current meaning; an observation arm is a new spelling or a widened id domain, never a redefinition of the existing one"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use a stable severity-prefix vocabulary, stdout agent-facing / stderr user-facing → ENGAGED by Chunk 02: the joined delta+span line is agent-facing and must not invent a new prefix"
      - "the governance ledger has a single writer → conforms; no chunk hand-authors the ledger"
      - "text emitted into a governed product names no prawduct-internal identifier → ENGAGED by Chunk 02: the joined line must say what is uncovered in plain language, with no RC/fid/chunk id"
last_validated: 2026-09-16
lifecycle: completed
archived: 2026-09-20
released_in: v3.6.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High for Chunk 01, Medium for Chunks 02-03.

**Why the split:** the fork below was Chunk 01's only open question and it is now decided against
the three consumer queries — see "Decision — how an accepted observation is recorded" in Chunk 01.
Chunks 02 and 03 stay Medium on the reasons that follow.

**Why:** The problem is measured, not inferred — 9 root causes against 728 review facts, an
independent consumer report (#716) corroborating two of them, and a 2026-09-16 re-measurement
confirming nothing improved in the three weeks after (mean reviews/chain 2.5 → 2.7; VR share
50% → 55%; wall-clock per chain 16.3 → 19.2 min). The three fixes are the diagnosis's own top
three by leverage, and two of them are message/composition changes over values the framework
already computes.

**Chunk 01's central fork, DECIDED 2026-09-16** — kept here because the reasoning the two routes
were weighed on is what a later reader needs; the answer and its consumer-query table are in
Chunk 01. `dispositions.record` refuses a fid it cannot find, so today an observation has no id to
disposition against. Two routes were on the table, and they differ in what they lock in:

- **(a) Persist demoted observations as findings** at a severity no gate reads. Gives every
  observation a real fid; changes the shape of the review fact.
- **(b) Relax the fid domain** so `disposition` accepts an observation reference without the
  finding being persisted. Smaller; leaves the accepted observation's *subject* unrecoverable
  from the store later.

**This is a persisted-format decision and therefore a lock-in decision regardless of size.**
Per `planning.md`, the questions the data must answer are enumerated before fields are designed,
and they are elicited from the consumers rather than inferred from the mechanism. The consumers
here are: `render-dispositions` (the census — "is this finding dispositioned?"), the future
yield query that `nonfunctional-requirements.md`'s proportionality norm is waiting on ("what did
this control catch, and what was waved through?"), and a human reading back why a round was not
spent. **Chunk 01 does not design fields until those three have stated their queries.**

**What raised Chunk 01 to High:** the fork answered with the three consumer queries written down,
which was its first deliverable.

**Open assumptions:**

- `[ASSUMPTION: the owner wants round-count reduced without accepting any additional miss rate | HIGH impact | user can correct]` — this is why the diagnosis's withdrawn fix #7 (incremental cumulative) stays out of scope, and why Chunk 03's coverage grant was cut rather than built (Chunk 03, revised). If some miss-rate increase IS acceptable in exchange for a larger cut, the shape of this plan changes and #7 comes back on the table.
- `[ASSUMPTION: fixing the three mechanisms is worth doing even though the evidence says the real blocker was organizational, not mechanical | MED impact | user can correct]` — see the advisory note below.

## Advisory note — what I would do differently

**Three things, and the first is not a chunk.**

**1. Work IS moving on the round pump — just not on these three fixes.** An earlier draft of
this note said a measured diagnosis had "sat unplanned for three weeks" and implied nobody was
acting. That was checked afterwards and is **not fair**: `#167` is open at `stage:design` with a
22KB technical design written 2026-09-15, it measures the same pump (27 rounds/4.5h on #724's
branch, 10 rounds at a consumer, six rounds twice here), and it lands a dispatch-time refusal
that none of these three chunks touch. The correction matters because the wrong version of this
note would have argued for re-planning work already in flight — which is the exact failure the
repo's own handoff identifies as its root cause (scheduled sessions re-deriving work they cannot
see).

**What IS true and still worth saying:** the three fixes in THIS plan are unshipped, RC7 is
ranked #1 by the diagnosis's own leverage ordering, and #167's design independently names RC7's
gap as *"currently-unfiled"* — so the highest-leverage item in a 2026-08-25 diagnosis was still
unfiled on 2026-09-15, while a second document re-derived the need for it from the other
direction. That is a *routing* failure, not an analysis failure, and it is the same shape as
#180 — *"The Critic review loop has no structural exit condition"* — being **closed 2026-08-01,
three weeks before the diagnosis re-derived the same problem.** **My recommendation: this plan
ships, and somebody looks at how a filed diagnosis fails to become filed items.** Not folded
into a chunk: it is not engineering work and I do not know the answer.

**A concrete, free step that closes half of it now:** put a comment on #167 pointing at this
plan, so the next reader of that design finds its scoped-out dependency has a home. Per
`project-preferences.md`, a comment on an existing item is not filing and is unrestricted.

**2. I would consider cutting Chunk 03.** *(Taken 2026-09-16: the grant is cut — see Chunk 03, revised.)* It is the only one of the three that changes what
governance *believes* rather than what it *says*. Chunks 01 and 02 cannot let a defect through
by construction — an accepted observation gates exactly what it gated before (nothing), and a
more honest message gates nothing at all. Chunk 03 grants coverage, which is authority, and its
warrant is a predicate over facts. The case for it was that `diagnose_fix_churn` already
proves the condition; the case against, which won, is that its predicate compares whole files
and would have skipped the first verify pass #167's D2 keeps.

**3. The measured yield floor may matter more than all three.** The diagnosis's fix #6 — tell
the agent a full review returns 13-18 true findings *regardless of round*, because that is the
reviewer's floor and not a signal about the code — is the only item that changes what the agent
believes. Its own text warns that without it "the mechanism fixes above get routed around by the
same diligence." I have left it out because it is a prose change to `review-cycle.md` whose
effect is unmeasurable in the short run and which I would rather land after the mechanisms, with
a re-measurement to point at. **That is a judgment call and it may be the wrong order.**

## Status

- [x] Chunk 01: An observation can be accepted on the record, not only fixed (RC7)
- [x] Chunk 02: A clean delta stops reading as branch clearance (RC8)
- [x] Chunk 03: The coverage grant is cut; the observations close prices fixing (RC5, revised)

## Chunk 01: An observation can be accepted on the record, not only fixed (RC7)

**Type:** code

**Why first:** it is the thin vertical slice — it touches consolidation (where the demotion
happens), the disposition path (where the record is written), the evidence store (where it
lands), and the census (where it is read back). Proving those four connect is what validates the
approach before Chunks 02 and 03 widen it. It is also the diagnosis's #1 by leverage and its
lowest-risk item: an accepted observation gates exactly what it gated before, which is nothing.

**The defect.** `verify-resolutions` demotes every non-BLOCKING finding to an *observation*.
Observations are never persisted as findings, and `dispositions.record` refuses any fid it
cannot find (`dispositions.py`). So a demoted observation can be discharged in exactly two ways:
**fix it**, which moves the tree and buys a coverage round, or **say nothing**, which loses the
reasoning. There is no "considered, declined, here's why". #716 reports its author fixing
observations *because accepting them left no trace*, and two of those fix commits triggered
rounds 4 and 5 of six.

**Deliverables** (method is advice — see `governed_by` on goals-and-verification):
1. **The fork, decided and written down first.** Route (a) or (b) from Requirements Confidence,
   with the three consumer queries (`render-dispositions`, the future yield query, a human
   reading back) stated before any field is designed.
2. The chosen mechanism, with `--accept <reason>` reaching an observation.
3. Census correctness: an accepted observation reads as dispositioned, not as `undispositioned`.

**Done when:**
- An observation surfaced by a `verify-resolutions` pass can be accepted with a reason, and the
  acceptance survives into the evidence store as a fact.
- `render-dispositions` no longer reports an accepted observation as `undispositioned`.
- **No gate's verdict changes.** A test pins that an accepted observation is read by no gate —
  this is the whole safety argument and it is asserted, not assumed.
- `evidence status` still exits 2 on a schema-ahead read (data-model § newer-schema).
- `--accept`'s existing meaning for a real finding is unchanged (api-contract § additive-first).
- Full suite green.
- `/prawduct:critic` — findings resolved.

### Decision — how an accepted observation is recorded (deliverable 1)

**Chosen: a sibling `observations[]` array on the review fact body**, ids `O-n`, reachable by
`disposition` through a widened id domain. Owner-confirmed 2026-09-16. This is route (a) from
Requirements Confidence, corrected on one detail: the observations do **not** enter `findings`.

**What the code said that the fork's framing did not.** Observations are not data anywhere today
— `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` routes them to an `### Observations` heading *in prose*,
and the partial's only structured channel is `findings[]`. So route (b) does not merely leave the
subject unrecoverable later; the subject is never captured at all, and a disposition against it
would be a reason string bolted to an opaque id.

**The three consumer queries, answered before any field was designed:**

| Consumer | Its query | What it needs recorded | (a) as written | (b) | Chosen |
|---|---|---|---|---|---|
| `render-dispositions` | is this answered? | a joinable id, a title to show | works, but observations enter `counts`/`by_severity` and every un-accepted one reads `undispositioned` — record-debt the demotion exists to remove | invisible: `census` builds rows from the fact's `findings`, and `prior_dispositions` skips a disposition whose finding is not indexed | separate array + separate census block; `undispositioned` keeps counting findings only |
| the yield query (`nonfunctional-requirements.md` proportionality) | what did this control catch, and what did it wave through? | the observation's title, goal and cited files | answerable | unanswerable — acceptances countable, subjects lost | answerable, and it is what makes over-firing of the verify-mode narrowing visible for the first time |
| a human reading back | why was a round not spent on this? | subject and reason co-located | yes | reason without subject | yes |

**Why a sibling array rather than findings.** `build_fact_body` already carries `record_lint` on
exactly these terms — *data about the review, not a finding in it; never reaches `counts`, so it
cannot move a verdict, and no gate reads it.* An observation is that shape. Keeping it out of
`findings` is what makes this chunk's "no gate's verdict changes" true **by construction** rather
than by audit: `coverage_algebra` never sees the array at all.

**Additive, per `api-contract.md`.** `--accept` keeps its meaning exactly — record why this will
not be fixed. What widens is the id domain it accepts, which is the spelling that norm sanctions.

**A recorded position is departed from here, and it is #585's.** `#585` (*verify-mode demotion
count never reaches the evidence store*) scopes out *"persisting the demoted observations
themselves (deliberately not facts)"* and asks only for a **count**. A count cannot be
dispositioned, so it cannot deliver this chunk's requirement. The departure is narrower than it
reads: nothing here mints an observation *fact* — the array is a field on the review fact, beside
`findings` and `record_lint`, so the store grows no new kind. #585's own acceptance falls out as
a by-product (the count is `len(observations)`); its remaining leg is surfacing that count in
`review-stats`, which is **not** in this chunk's Done-when and stays #585's.

**Resolutions stay findings-only.** `_known_findings_index` is not widened — a resolution may
still only target a finding. That is the fail-closed side of the join and nothing here needs it.

**Why `O-n` and not `OBS-n`.** #716's own reproduction reaches for `OBS-3`, so it is the spelling
the next reader will try. It is already taken: `OBS-` is this repo's backlog **area** prefix for
observability (`OBS-4C1K`, cited in `docs/norms.md` and `test_norm_probes.py`). An id vocabulary
shared between review observations and backlog items would collide in exactly the records that
join on ids.

**#585 and #167 are reconciled on the tracker**, which is where the departure and the dependency
respectively had to land — a comment on an existing item is not filing and is unrestricted
(`project-preferences.md` § Backlog filing). #585 carries the departure from its own Scope-out and
keeps its `review-stats` leg; #167 is told the gap its design calls "currently-unfiled" has
landed, and is warned about both the non-verify refusal and the `OBS-` collision above.

## Chunk 02: A clean delta stops reading as branch clearance (RC8)

**Type:** code

**The defect.** `verify-resolutions` covers only its own delta, but on a clean close its headline
is `0 blocking, 0 other findings — THE REVIEW IS OVER` (`critic_consolidate.py`). The
span-vs-delta qualifier exists only as `_COVERAGE_IS_A_SEPARATE_QUESTION`, which tells the reader
to go *ask* the gate rather than stating the answer the framework has already computed. In #716
the author relayed "the branch is clean" to the repo owner after round 3; round 4's cumulative
found a blocking defect present since chunk 1, structurally invisible to every verify round
because it was never inside one of their diffs. Both facts were true — the delta was clean, the
span was never reviewed — and nothing said the second.

**This is the under-review direction**, and it costs rounds too: the escalation it hides arrives
later and more expensively.

**Deliverables:**
1. On a clean `verify-resolutions` close, join the delta verdict and the span verdict in one
   breath — "this delta is clean; the branch is NOT covered, N commits unspanned."
2. Render the value `check-cumulative-critic` computes. **Do not compute a second one**
   (architecture § every fact has one home).

**Done when:**
- A clean verify close on an uncovered branch states both facts in its headline, not in a
  parenthetical.
- A clean verify close on a *covered* branch says so, and does not manufacture a warning.
- The line names no prawduct-internal identifier and invents no new severity prefix
  (observability § both norms).
- Full suite green.
- `/prawduct:critic` — findings resolved.

**Riding this chunk's commit — two notes from Chunk 01's review.** Both are judgeable fixes that
would each have bought their own round; carried here because this chunk buys one anyway. They are
written down because an unwritten deferral is a drop.

1. **Pin the `observations` key in `goals-1-3.md`.** Chunk 01 raised that file's ceiling 2345 →
   2400 arguing the JSON block must SHOW the key a reviewer is told to write, and then pinned
   nothing — `test_carries_what_the_pointers_used_to_fetch` does not assert it, and the file sits
   at 2399 against the new ceiling, so the next editor needing a token trims the unguarded clause.
   The twin carrier in `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` IS pinned, which is why this is a
   note and not worse.
2. **Say `<fid|oid>` where the builder is actually told what to type.** `dispositions._RECORD_USAGE`
   and `review-cycle.md`'s operational disposition section both still read `<fid>`; the widened
   domain is stated eight lines earlier, under a re-review heading. Not a contradiction, and the
   rendered census teaches the rule — but the usage string is what a refused invocation prints.

## Chunk 03: The coverage grant is cut; the observations close prices fixing (RC5, revised)

**Type:** code

**Revised 2026-09-16, owner-confirmed, before any code.** The original chunk — *"a provably
unnecessary round is granted, not narrated and charged"* — composed `diagnose_fix_churn`'s
condition as covered. **That grant is cut.** What ships is the two items that rode on this chunk,
plus the recorded reasons, so the grant is not re-derived from the diagnosis a third time.

### Why the grant is cut

1. **The predicate cannot carry authority, and its own docstring says so.** Its subset test is
   *file*-granular: it cannot tell a fix from new work written into a file some finding named, and
   it states that the message it feeds "must not assert content-level certainty on file-level
   evidence." Today a false positive routes to `verify-resolutions`, which still blocks on weakened
   tests, dropped requirements, untested behaviour and fix-by-fudging. A grant turns that same
   false positive into **no review at all**. The discriminator the docstring names (hunk overlap
   against each finding's line range) is not in the findings record, and deliverable 3 of the
   original chunk ruled out content comparison. "Provably" was never true of the evidence.
2. **It contradicts #167's design.** `documentation/issues/167-design.md` D2 (test case 2) holds
   that the **first** `verify-resolutions` after a full round always runs, "regardless of that
   round's severity mix", because it is the pass that establishes coverage over the fix commit.
   #167 refuses only a verify anchored on a verify. The grant would have skipped exactly the pass
   D2 protects. The "adjacent, not overlapping" claim in `related_issues` was true of files, not of
   policy.

**What would reopen it:** the findings record carrying line ranges, so churn can be proved at hunk
granularity — and even then, scoped to #167's D2 rather than to every anchor. The more likely
useful successor is narrower: when #167 refuses a round at dispatch, that refused round has no
review fact, so `check-cumulative-critic` may still report the span `uncovered`. Making a #167
refusal compose at the gate is the grant's real home, and it lands after #167 (noted on the issue).

### What ships

1. **The observations-only clean close prices fixing.** The `0 blocking, 0 findings, N
   observations` arm ended at its coverage clause, so the one clean close that still carries
   fixable items never said what fixing costs, how to price a batch first, or that a fix can ride
   the next chunk's commit. It now carries the same cost-of-fixing guidance (extracted to one
   constant both arms share), the ride-along route and the round price as the warnings arm. The
   span verdict still precedes them (Chunk 02's headline requirement).
2. **Observation-cited files stay out of the churn predicate — decided, not defaulted.** Widening
   `named` would widen what the gate calls churn on evidence already only file-level, from items
   the reviewer did not even rate as findings. Recorded beside the loop in `coverage.py` and
   pinned by a test that fails if observation files are ever counted.

**Done when:**
- The observations close carries the fix-cost guidance, the ride-along route and the price, after
  the span clause; the 0/0/0 close with nothing to fix carries none of them.
- The duration guard still scans the text that moved into constants.
- A delta confined to a file only an observation named is not diagnosed as churn.
- Full suite green.
- `/prawduct:critic` — findings resolved.

## Out of scope

- **Making `cumulative` incremental** (diagnosis fix #7). Proposed and **withdrawn there on
  evidence**: #716's round-4 cumulative caught a blocking defect present since chunk 1, inside a
  span an earlier review had already covered. Composed coverage records that a tree *was
  reviewed*, never that it is *correct*; residual scoping would have skipped that read. If RC4 is
  attacked, attack repeat-cumulative **output volume**, not scope.
- **The yield-floor prose change** (diagnosis fix #6) — deliberately deferred, see advisory note 3.
- **Dropping non-judgeable files from reviewer scope** (diagnosis Option 1) — live as #771 at
  `stage:design`; not re-planned here.
- **Why #180 was closed with the defect live, and why RC7 was still unfiled on 2026-09-15** —
  advisory note 1. Not engineering work.
- **#167's dispatch-time refusal** — a separate item with its own design
  (`documentation/issues/167-design.md`). Do not re-derive it here. It composes with this plan
  additively (it refuses rounds upstream; this plan changes consolidation and close copy), but
  its builder re-reads Chunk 01's observations mechanism before starting.

## Verification strategy

Beyond the suite: each chunk is exercised against this repo's own review flow, which is the
product. Chunk 01 by accepting a real observation from a real `verify-resolutions` pass and
reading the census back. Chunk 02 by closing a verify round clean on a branch known to be
uncovered and reading the headline. Chunk 03 by producing the churn condition deliberately (a
clean review, then an edit confined to files its findings named) and confirming no round is
charged — then by breaking the fact read and confirming one is.

**Chunk 03 as revised** is exercised by reading the observations close off a real verify pass. The
churn-produce-then-break exercise above belonged to the cut grant and does not apply.

**Governance checkpoint after Chunk 01** — it decides the persisted format every later consumer
reads. Re-measure before/after round counts at plan close, against the `norm_health` 2026-09-16
baseline, so this plan's own yield is observable rather than asserted.
