---
artifact: build-plan
version: 2
scope: review-loop-termination
branch: fix/review-loop-termination
partition: serial — all three chunks edit `critic_consolidate.py` and read the coverage/evidence path; 02 and 03 both consume a coverage verdict, so delegates would collide on the same seam
depends_on:
  - artifact: review-loop-nontermination-diagnosis
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never from mutable model-written state → ENGAGED by Chunk 01, and it is the chunk's central constraint: an accepted observation must enter as a fact written by deterministic code from validated reviewer content, never as model-written state a gate later reads. No gate reads an accepted observation at all (it gates nothing by construction), so the norm is satisfied by the weaker path too — but the design takes the stronger one so the record is queryable"
      - "facts are immutable and append-only → conforms; an accepted observation is a NEW fact, never an edit to the review fact that demoted it"
      - "derived views are disposable and never authoritative → conforms; Chunk 03's grant is computed per call from composed coverage, never persisted"
      - "a governance document reaches a terminal state, never deleted → inapplicable, because no chunk touches plan archival"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → inapplicable, because no chunk writes a backlog item"
      - "a newer-schema fact surfaces as a loud block → ENGAGED by Chunk 01: if the observation disposition lands as a new fact kind or a new field, `evidence status` must still exit 2 on a schema-ahead read. Chunk 01's acceptance names this"
      - "two stores, two lifetimes → conforms; nothing moves between the committed store and the gitignored nags/caches"
      - "`backlog_service_repo` selects the authoritative backlog store → inapplicable, because no chunk reads the backlog"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; cost = unit-cost × run-count, both levers → this plan IS that norm being acted on. Run-count is the target; the measured baseline is in the diagnosis and in `norm_health` (2026-09-16)"
      - "proportionality ratchets both ways; a control that never blocks is removed by default → ENGAGED, and it cuts against Chunk 03. Granting coverage REMOVES a control (the mandated round), so the emission arm applies to its inverse: the plan must name what evidence would show the grant let a defect through. Chunk 03's acceptance carries it"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable, because no chunk changes a size gate"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → ENGAGED by Chunk 01: an accepted observation is written by the BUILDER through `disposition`, never by the reviewer. Nothing here gives a reviewer subagent a write path it lacks"
      - "authority fails closed; advice fails soft → ENGAGED by Chunk 03, and it is the risk. A coverage grant is authority, so it must fail CLOSED: any ambiguity in the churn predicate (unreadable facts, a partial read) grants nothing and the round is charged. `diagnose_fix_churn` already returns `unavailable` for exactly this and Chunk 03 must not collapse it into a grant"
      - "local-first: no network, no daemon, no third-party runtime dependency → conforms; file reads and git only"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "prawduct is Python but never Python-specific → conforms; no chunk classifies a product file by language"
      - "prawduct guides and reviews; it never implements → conforms; no product code is written"
      - "goals and verification bind; prescribed method is advice → the fix shapes below are the DIAGNOSIS's best guess, made 2026-08-25 before this code was re-read. A builder who finds a better route takes it and records why; what binds is the round-count reduction and the miss-rate floor stated per chunk"
      - "every fact has one home → ENGAGED: the argument for each fix lives in the diagnosis, and the chunks cite it rather than restating it. Chunk 02 specifically must not mint a second home for the span verdict — it renders the value `check-cumulative-critic` already computes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the internal CLI subcommand surface carries no per-subcommand version → conforms; the plugin version covers it"
      - "exit codes are the contract, on a documented and consistent scheme → ENGAGED by Chunk 01 (a new `disposition` arm needs an exit-code meaning) and Chunk 03 (the grant must not change `check-cumulative-critic`'s exit vocabulary — a granted round still exits 0 `satisfied`, with the reason in the message)"
      - "additive-first evolution: flags and `--json` keys are added, never repurposed → ENGAGED by Chunk 01. `--accept` must keep its current meaning; an observation arm is a new spelling or a widened id domain, never a redefinition of the existing one"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use a stable severity-prefix vocabulary, stdout agent-facing / stderr user-facing → ENGAGED by Chunk 02: the joined delta+span line is agent-facing and must not invent a new prefix"
      - "the governance ledger has a single writer → conforms; no chunk hand-authors the ledger"
      - "text emitted into a governed product names no prawduct-internal identifier → ENGAGED by Chunk 02: the joined line must say what is uncovered in plain language, with no RC/fid/chunk id"
last_validated: 2026-09-16
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem is measured, not inferred — 9 root causes against 728 review facts, an
independent consumer report (#716) corroborating two of them, and a 2026-09-16 re-measurement
confirming nothing improved in the three weeks after (mean reviews/chain 2.5 → 2.7; VR share
50% → 55%; wall-clock per chain 16.3 → 19.2 min). The three fixes are the diagnosis's own top
three by leverage, and two of them are message/composition changes over values the framework
already computes.

**What is NOT confirmed, and it is Chunk 01's central fork:** *how* an accepted observation is
recorded. `evidence.KNOWN_KINDS` is `{review, resolution, disposition}` and
`dispositions.record` refuses a fid it cannot find, so today an observation has no id to
disposition against. Two routes, and they differ in what they lock in:

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

**What would raise this to High:** answering the fork above with the three consumer queries
written down. That is Chunk 01's first deliverable and is cheap — it is a decision, not a spike.

**Open assumptions:**

- `[ASSUMPTION: the owner wants round-count reduced without accepting any additional miss rate | HIGH impact | user can correct]` — this is why the diagnosis's withdrawn fix #7 (incremental cumulative) stays out of scope, and why Chunk 03 is ordered last and carries a fail-closed requirement. If some miss-rate increase IS acceptable in exchange for a larger cut, the shape of this plan changes and #7 comes back on the table.
- `[ASSUMPTION: fixing the three mechanisms is worth doing even though the evidence says the real blocker was organizational, not mechanical | MED impact | user can correct]` — see the advisory note below.

## Advisory note — what I would do differently

**Three things, and the first is not a chunk.**

**1. The mechanisms are not why this is unfixed, and shipping them may not be enough.** The
diagnosis is excellent and three weeks old. In that window one fix shipped (RC9) and the
measured loop got marginally *worse*. The item that should have carried the work — #180, *"The
Critic review loop has no structural exit condition — agents in production get trapped for 3-4
rounds"* — was **closed 2026-08-01, three weeks before the diagnosis re-derived the same problem
from scratch.** A plan that fixes RC7/RC8/RC5 and does not ask why a measured, costed, ranked
diagnosis sat unplanned for three weeks is treating the symptom at the level above the one it
diagnosed. **My recommendation: this plan ships, AND the closure of #180 gets a look as its own
question.** I have not folded that into a chunk because it is not engineering work and I do not
know the answer.

**2. I would consider cutting Chunk 03.** It is the only one of the three that changes what
governance *believes* rather than what it *says*. Chunks 01 and 02 cannot let a defect through
by construction — an accepted observation gates exactly what it gated before (nothing), and a
more honest message gates nothing at all. Chunk 03 grants coverage, which is authority, and its
warrant is a predicate over facts. It is still the right call — `diagnose_fix_churn` already
proves the condition and the framework already pays to compute it — but if only two of these
ship, ship 01 and 02 and leave 03 for when someone can sit with the predicate properly.

**3. The measured yield floor may matter more than all three.** The diagnosis's fix #6 — tell
the agent a full review returns 13-18 true findings *regardless of round*, because that is the
reviewer's floor and not a signal about the code — is the only item that changes what the agent
believes. Its own text warns that without it "the mechanism fixes above get routed around by the
same diligence." I have left it out because it is a prose change to `review-cycle.md` whose
effect is unmeasurable in the short run and which I would rather land after the mechanisms, with
a re-measurement to point at. **That is a judgment call and it may be the wrong order.**

## Status

- [ ] Chunk 01: An observation can be accepted on the record, not only fixed (RC7)
- [ ] Chunk 02: A clean delta stops reading as branch clearance (RC8)
- [ ] Chunk 03: A provably unnecessary round is granted, not narrated and charged (RC5)

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

## Chunk 03: A provably unnecessary round is granted, not narrated and charged (RC5)

**Type:** code

**Ordered last because it is the only chunk that grants authority.** See the advisory note.

**The defect.** `coverage.diagnose_fix_churn` already detects "the whole uncovered span is a
clean review of this branch plus edits confined to files that review's own findings named." Its
only consumer renders it as a `NOTE:` and then still directs the builder to run
`verify-resolutions`. A provably-unnecessary round is diagnosed, narrated, and charged for.

**Deliverables:**
1. Compose the churn condition as covered rather than printing a paragraph and charging.
2. **Fail closed.** `diagnose_fix_churn`'s `unavailable` status must grant nothing — a degraded
   read charges the round (architecture § authority fails closed).

**Done when:**
- The churn condition composes as covered; the round is not charged.
- A degraded or unavailable churn read grants nothing, pinned by a test that makes the predicate
  return `unavailable` and asserts the round is still charged.
- The grant is strictly narrower than the base-advance transfer already granted, and a test says
  so.
- `check-cumulative-critic`'s exit vocabulary is unchanged — a granted round exits 0
  `satisfied` with the reason in the message (api-contract § exit codes).
- **The yield-inverse is named:** the chunk records what evidence would show the grant let a
  defect through, so it can be retired on evidence rather than defended on principle
  (nonfunctional § proportionality, emission arm).
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
- **Why #180 was closed with the defect live** — advisory note 1. Not engineering work.

## Verification strategy

Beyond the suite: each chunk is exercised against this repo's own review flow, which is the
product. Chunk 01 by accepting a real observation from a real `verify-resolutions` pass and
reading the census back. Chunk 02 by closing a verify round clean on a branch known to be
uncovered and reading the headline. Chunk 03 by producing the churn condition deliberately (a
clean review, then an edit confined to files its findings named) and confirming no round is
charged — then by breaking the fact read and confirming one is.

**Governance checkpoint after Chunk 01** — it decides the persisted format every later consumer
reads. Re-measure before/after round counts at plan close, against the `norm_health` 2026-09-16
baseline, so this plan's own yield is observable rather than asserted.
