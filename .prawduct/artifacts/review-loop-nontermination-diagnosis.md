# Diagnosis: why review cycles do not terminate

Status: discovery / not yet planned. Measured 2026-08-25 against this clone's shared
evidence store (`.git/prawduct/evidence.jsonl`, 3334 facts, 728 review facts,
2026-07-13 → 2026-08-24). Every number below is computed from that store, not recalled.

A second, independent source is folded in: **consumer report #716** (2026-08-25, prawduct
v3.4.0, private product repo) — a 6-round / 55-minute cycle on a docs-restructuring branch.
It corroborates RC1 and RC2 from outside this clone, supplies RC7, and is the only evidence
that argues *against* one of the fixes below. Its headline finding matters for calibration:
**zero false positives across 61 findings.** This is a routing and signalling problem, not a
reviewer-quality problem — "make the reviewer less picky" is the wrong lever.

## The measurements

| Measure | Value |
|---|---|
| Review facts | 728 across 149 tree-linked chains (4.9 reviews per work cycle) |
| Findings | 3826 — 236 BLOCKING (6%), 1606 WARNING, 1992 NOTE |
| Reviews returning zero BLOCKING | 560 / 728 = **77%** |
| Longest chains | 34, 22, 21, 21, 20, 20, 18, 17 reviews |
| Chain of 22 (2026-07-28 → 07-29) | **one** BLOCKING finding in 22 reviews |
| Reviews per BLOCKING finding found | 3.1 |

### Full-review yield does not decay

Cumulative/final reviews, bucketed by their index within a chain:

| Round | n | avg findings | BLOCKING | WARNING | NOTE | share of findings on non-judgeable files |
|---|---|---|---|---|---|---|
| 1 | 100 | 13.5 | 74 | 557 | 719 | 37% |
| 2 | 45 | 15.4 | 27 | 291 | 377 | 35% |
| 3 | 22 | 15.5 | 10 | 142 | 188 | 36% |
| 4 | 14 | 18.4 | 4 | 121 | 133 | 39% |
| 5+ | 19 | 13.8 | 9 | 120 | 134 | 36% |

Findings whose title repeats an earlier finding in the same chain: **1%**. Every round
finds genuinely new things.

BLOCKING decays hard (74 → 27 → 10 → 4). Total yield does not — it is flat to rising.

### Judgeability

| Measure | Value |
|---|---|
| Findings whose only subject is a non-judgeable (free-to-edit) file | 1372 / 3826 = **36%** |
| Non-blocking findings in that class | 1320 (34% of all findings) |
| BLOCKING findings in that class | 54 (**23% of all BLOCKING**) |
| Reviews whose *entire* yield was non-judgeable-only findings | 68 / 534 = 13% |
| Free-interval dispatch refusals (`critic-begin` exit 3) | **6 in 728 = 0.8%** |

Top non-judgeable finding targets: `.prawduct/change-log.md` (360), `.prawduct/backlog.md`
(290), `.prawduct/learnings.md` (190), `.prawduct/cross-cutting-concerns.md` (121),
`.prawduct/project-state.yaml` (105). The framework's own bookkeeping is the single
largest finding surface.

## Root causes

**RC1 — The exit condition and the re-entry condition are the same event.**
Coverage is keyed on the exact tree. Any judgeable fix moves the tree; a moved tree is
`uncovered`; `uncovered` mandates a review. So "act on a finding" and "be done" cannot
happen in one step. The only genuinely free disposition is ACCEPT. `review-cycle.md`
tells the builder FIX is right for "anything cheap" — but cheap-to-fix is exactly the
class where the mandated round costs an order of magnitude more than the fix. The cost
gradient runs backwards from the intuition and no document says so.

**RC2 — Reviewer yield is a function of surface × effort, not of defect density.**
Corroborated independently by #716: a 343-line throwaway verification script drew 15
actionable / 31 total findings — #4 in that repo by actionable findings, above most
production modules — while the 2,600-line prose relocation it existed to verify drew
essentially none. Roughly 5 of its 6 rounds hardened the instrument, not the deliverable.
Attention scaled with *new code volume*, not with risk or with what ships.

The framework's stated model (`review-cycle.md`, "Diminishing-returns signal") predicts
that by round 3 a pass is finding defects in the record of round 2. Measured: round 3
returns 15.5 findings, 99% of them new, with the same 36% non-judgeable share as round 1.
A competent reviewer pointed at 30 files with 7 goals will always return 13–18 true
findings. **"Review until clean" has no fixed point at full mode.** The agents are not
malfunctioning; they are correctly observing that the stated stopping heuristic is false
of their own data, and they cannot stop on a rule they can falsify.

**RC3 — Batching destroys the free-doc allowance (the intersection).**
`coverage_algebra._free_edge_files` returns `None` if *any* judgeable file appears in the
interval: judgeability is interval-scoped and all-or-nothing, not per-file. Meanwhile
`review-cycle.md` directs "Batch the fixes: ONE commit, then ONE `verify-resolutions`",
and `critic_consolidate._BATCH_FIX_DIRECTIVE` prints it on every review that lands
findings. Batching guarantees mixed intervals. So the framework's own anti-loop advice is
what disables the mechanism designed to make prose fixes cost nothing. Firing rate: 0.8%.
Two mechanisms, each correct alone, that cancel.

**RC4 — `cumulative` has no incrementality.**
`critic_consolidate.begin_review` derives cumulative's interval as merge-base tree → HEAD
tree, unconditionally. Coverage *composes* incrementally; review does not. The 6th
cumulative on a branch re-reads all 66 files from scratch at full severity, including
everything five prior clean rounds already vouched for — and returns another 13 WARNING
+ 17 NOTE. `verify-resolutions` received the BLOCKING-only narrowing; `cumulative` received
nothing. The expensive mode is the uncapped one. Observed chain shapes are
`cumulative → verify×N → cumulative → verify×N → …`, and it is the repeated *cumulative*
that carries the cost.

**RC5 — The framework can already prove a round is unnecessary, and prints the proof
instead of acting on it.**
`coverage.diagnose_fix_churn` detects exactly the condition "the whole uncovered span is a
clean review of this branch plus edits confined to files that review's own findings named."
Its only consumer is `gates.py:1674`, which renders it as a `NOTE:` — and then still
directs the builder to run `verify-resolutions`. A provably-unnecessary round is diagnosed,
narrated, and charged for.

**RC7 — The severity narrowing created a class of finding that cannot be accepted.**
`verify-resolutions` demotes every non-BLOCKING finding to an *observation*
(`critic_consolidate`, "an observation is not a recorded fact"). Observations are never
persisted as findings, and `dispositions.record` refuses any fid it cannot find
(`dispositions.py:371`). So a demoted observation can be discharged in exactly two ways:
**fix it** — which extends HEAD and buys a coverage round — or **say nothing**, which loses
the reasoning. There is no "considered, declined, here's why" on the record. Report #716
names this directly: its author fixed several observations *because accepting them left no
trace*, and two of those fix commits are what triggered rounds 4 and 5 of six. The mechanism
built to stop the pump (BLOCKING-only rating) started a new one, by removing the free
disposition from exactly the findings it demoted. This is the cheapest defect here to fix and
has the most direct effect on round count.

**RC8 — A clean verify round reads as branch-level clearance.**
From #716. `verify-resolutions` covers only its own delta, but on a clean close its
NEXT-ACTION headline is "0 blocking, 0 other findings — THE REVIEW IS OVER". The
span-vs-delta qualifier exists only as a parenthetical. The report's author relayed "the
branch is clean" to the repo owner after round 3; round 4's cumulative then found a blocking
defect present since chunk 1 and structurally invisible to every verify round, because it was
never inside one of their diffs. Both facts are true and not in tension — *the delta was
clean, the span was never reviewed* — and nothing in the output says the second. This is the
one failure here in the **under**-review direction, and it also costs rounds: the escalation
it hides arrives later and more expensively.

**RC6 — BLOCKING on a non-judgeable surface is unclearable except by a full dispatch.**
Only a `verify-resolutions` resolution fact unblocks a blocking finding. 54 blocking
findings (23%) target only files that are free to edit. A record-grade defect on
`change-log.md` therefore mandates a review round to clear, while the same file could be
rewritten wholesale for free. The severity bar in `review-cycle.md` ("a finding whose only
subject is a non-judgeable record is a NOTE unless it ships or misleads") is prose the
reviewer is asked to remember; nothing enforces it at consolidation.

## RC9 — A FIX that costs nothing cannot be recorded as a FIX

Found live, dogfooding Chunk 01's own review (2026-08-25). A FIX's only machine-readable trace is
the resolution fact a `verify-resolutions` pass appends. A fix confined to non-judgeable paths buys
no round — which is the outcome the whole framework is steering toward — so **no verify pass runs,
and no resolution fact is ever written.** `render-dispositions` then reports the finding as
`undispositioned` forever.

Measured on the review of Chunk 01: two WARNINGs (R-2, R-3) were fixed completely, the batch priced
`free` by `cost-of-commit`, and the census still reads *"3 undispositioned — every finding takes an
ACCEPT, FIX or FILE regardless of severity."*

The incentive this creates is the inverted gradient again, one level up. An agent that wants a clean
census has two routes that work — **ACCEPT it** (a fact, free) or **buy a round** (a resolution
fact) — and one that does not: fix it for free. So the cheapest and most virtuous action is the only
one the record cannot see, and the two visible options are "don't fix it" and "spend ten minutes".
This sits directly beside RC7 (a demoted observation cannot be accepted) and has the same shape: a
disposition vocabulary with a hole exactly where the cheap correct action is.

**Fix:** let a fix be recordable without a review — `disposition <review> <fid> --fixed "<what
changed>"`, valid only where the change is confined to non-judgeable paths (the same predicate,
verified at record time, so it can never launder a judgeable fix past a gate). A BLOCKING finding
still clears only through a real resolution fact; nothing about gating changes.

## Recommended fixes, in leverage order

Ordered by (round-count reduction) / (cost + risk). 1–3 are small and carry no miss-rate
risk; 4–5 are mechanism changes; 6 is the belief change without which the rest get routed
around. **7 is listed to be argued against, not adopted as stated.**

1. **Make demoted observations dispositionable** (RC7). Either let `disposition` accept
   observation ids, or have consolidation persist them at a severity that gates nothing but
   carries a reasoned `--accept`. Today the only way to leave a trace on an observation is to
   fix it, and fixing it buys a round. Smallest change here, most direct effect on round
   count, zero risk to rigor — an accepted observation gates exactly what it gated before:
   nothing.
2. **Join the delta fact and the span fact on a clean verify round** (RC8). When
   `verify-resolutions` closes clean *and* `check-cumulative-critic` is still `uncovered`,
   say both in one breath: "this delta is clean; the branch is NOT covered, N commits
   unspanned." Both values are already computed; nothing joins them at the moment the author
   decides what to do next. Prevents the false-clean misreport and the expensive late
   escalation it hides.
3. **Turn `diagnose_fix_churn` into a grant instead of a NOTE** (RC5). When the whole gap is
   the builder's own non-blocking fixes inside files a clean review already saw, compose it
   as covered rather than printing a paragraph explaining that the round is unnecessary and
   then charging for it. Strictly narrower than the base-advance transfer already granted,
   and provable from the same facts.
4. **Compose over the judgeable projection of the tree, not the tree** (RC3, most of RC1).
   Make node identity in `coverage_algebra` the judgeable-content key — `_free_classes`
   already computes it — so the free edge stops being a special case discovered by search and
   becomes the default quotient. Prose fixes then ride free *even when batched with code*,
   which is what the batch directive currently makes impossible. Same predicate, no soundness
   loss: a comment-only `.py` edit stays judgeable, governance-protected `.md` stays
   judgeable. This is the fix for the intersection you named.
5. **Enforce the non-judgeable severity bar in code** (RC6). At consolidation, a BLOCKING
   whose files are all non-judgeable is demoted with a message unless it clears the "it ships"
   bar. Consider reclassifying genuinely-shipping prose (`CHANGELOG.md`, `README.md`) as
   judgeable so that bar has a real home. Also worth pairing with #716's suggestion 3: print
   the "name what round N+1 will do differently" challenge at **dispatch**, from
   `/prawduct:critic`, rather than from the gate after the round is already spent — and on
   the verify path, which is the path that escalates.
6. **Tell the agent the truth about yield** (RC2). Replace the "diminishing-returns signal"
   paragraph, which predicts decay that the data does not show, with the measured fact: *a
   full review returns 13–18 true findings regardless of round; that is the reviewer's floor,
   not a signal about your code.* An agent that knows the floor can stop at it. An agent told
   "by round 3 it's just record churn" checks, sees real new code findings, and correctly
   concludes the rule does not describe its situation — then keeps going. This is the only
   item that changes what the agent *believes*, and without it the mechanism fixes above get
   routed around by the same diligence.

### 7. Making `cumulative` incremental — proposed, then withdrawn

The obvious fix for RC4 is to derive cumulative's per-file scope as the residual of composed
coverage over merge-base→HEAD, running only the integration goals across the whole span.
**Report #716 is direct evidence against it.** Its round 4 — a full cumulative — found a
blocking defect that had been present since chunk 1 and inside a span an earlier review had
already covered. Composed coverage records that a tree *was reviewed*, never that it is
*correct*; a second full read genuinely finds what the first missed. Residual scoping would
have skipped exactly that read.

So RC4 is real and expensive, but the residual-scoping fix trades round count for miss rate,
and #716 prices that trade with a concrete miss. If RC4 is worth attacking, attack the
**output volume** of a repeat cumulative rather than its **scope** — the re-read is what
catches the chunk-1 defect; the fresh crop of 13 WARNING + 17 NOTE about already-covered prose
is what buys the round. Fixes 1, 3 and 4 above already absorb most of that cost without
touching what the reviewer reads.

---

# Second pass: options review (2026-08-25)

Four owner-proposed ideas, stress-tested against the store, plus alternatives. New
measurements: **39% of files handed to reviewers are non-judgeable** (5,869 of 14,860
file-slots across 728 reviews); coordinator reviews are 3 roles × ~25 files = ~75 file-reads,
**the same 25 files read three times**; roster is a fixed `(correctness, design,
sustainability)` triple, never sharded by file.

Already shipped, do not rebuild: `prior_dispositions` in the manifest suppresses re-raising
accepted findings (`review-protocol.md:67`, `agents/critic-reviewer.md:50`), and
`prawduct-hook cost-of-commit` already computes free-vs-charged paths — #716 says
"discoverability is the only issue."

## Option 1 — Exempt doc files from review

**Adopt, in a narrowed form.** Judgeability currently governs *coverage* but not *reading*:
non-judgeable files are still handed to reviewers and still rated, which is 39% of reader
load and 36% of findings. Making judgeability govern **review scope** as well is nearly free
— the predicate exists and is already computed per dispatch.

Not as a blanket exemption. Two things break: in this repo `.md` under `skills/`,
`methodology/`, `templates/` *is* behavioural logic (already judgeable, so already retained),
and 54 BLOCKING findings (23% of all blocking) target only non-judgeable files — some of
those clear the protocol's "it ships" bar and are real.

**Shape:** drop non-judgeable files from per-round reviewer scope. Add one **records pass**
that runs once per branch at `final`/`cumulative` only, checking only the two bars already in
the severity contract ("it ships" / "it misleads into action"). Cost falls from *per round*
to *once*; the shipping-falsehood case keeps a home.

## Option 2 — Guidance: docs always in their own commits

**Reject as a design; keep as a one-line stopgap.** It is strictly dominated by composing
over the judgeable projection (fix 4, first pass):

- It is discipline, not mechanism — it must be remembered every commit, and it directly
  contradicts the standing batch directive.
- **It cannot work where most reviews happen.** `chunk` and `final` review the *dirty working
  tree*, which has no commits to segregate. A doc edit and a code edit in one uncommitted tree
  cannot be split by commit hygiene.

Projection gets the same benefit mechanically, works on dirty trees, and needs nothing
remembered. Segregation is worth one sentence as an interim habit while projection is built,
nothing more.

## Option 3 — Let the Critic make trivial fixes

**The instinct is right; the naive version does not help.** If the reviewer edits the tree
after recording, the fix moves the tree, and a moved tree is `uncovered` — **the round is
bought either way.** Who made the edit is not what costs; moving the tree is.

**The version that works: reviewer-proposed record patches.** The reviewer emits fixes as a
*patch* inside its partial. `critic-consolidate` validates that every hunk lands on a
**non-judgeable path**, applies it, and records the review fact against the **post-apply
tree**. Then:

- **No round is bought** — coverage lands on the fixed tree, because the fix preceded the fact.
- **Independence is not violated on anything that gates.** Restricted to non-judgeable paths,
  the patch cannot touch code or governance-protected prose. The reviewer vouches only for a
  class that gates nothing by construction.
- **The no-execution contract survives.** The reviewer still neither runs nor edits: it
  proposes a diff, and code applies it at a single deterministic point.
- **No concurrency hazard.** Consolidation is one writer; a reviewer editing live would race
  the builder, who the docs explicitly tell to do prep work during the 4–10 minute wait.

Answer to "what reviews the Critic's changes": nothing needs to, because the patch is confined
to surfaces where nothing is gated and any subsequent edit is free. Residual risks worth
naming: patch application must fail closed (a hunk that will not apply aborts the whole patch,
never partially applies), the applied diff must be rendered to the builder verbatim rather than
summarised, and scope creep toward "just this one code fix" must be blocked in code, not prose.

## Option 4 — Parallelize the Critic harder

**Partly adopt — and one interaction is a trap.**

**The trap: adding reviewers increases finding supply.** Yield scales with surface × effort
(RC2). A 7-reviewer roster returns more findings than a 3-reviewer roster, and finding supply
is the actual bottleneck. Cutting latency 2× while round count stays at 30 is worth far less
than cutting rounds 30 → 5, and buying the latency with more reviewers makes rounds worse.
**Parallelize only in ways that cut reading, not in ways that add lenses.**

Two that qualify:

- **Drop non-judgeable files from scope** (Option 1) — −39% reader load, and it cuts yield at
  the same time. Same lever, both problems.
- **Shard by file, not only by lens.** Today each of 3 roles reads all ~25 files: ~75
  file-reads for 25 files. Sharding files across reviewers, with the lenses distributed rather
  than replicated, approaches 25 file-reads. The honest cost is losing three-lens depth per
  file — which, given the yield data, is a cost paid in findings nobody was going to act on.

A third worth measuring before building: a shared structured digest pass feeding three cheap
lens passes. Higher risk (digest fidelity), so measure the first two first.

## Other options

**A. Budget the rounds.** Declare a round budget at dispatch, spend from it, and when it is
exhausted auto-ACCEPT every remaining non-blocking finding with a rendered census in the PR
body. BLOCKING never auto-accepts, so nothing that gates is affected. The data says finding
yield has no fixed point — **if there is no natural stopping point, the only principled stop
is a declared budget.** Arbitrary-but-visible beats arbitrary-but-hidden, and it fits
"governance is CI."

**B. Render cost-to-clear on every finding.** `cost_of_commit` (`coverage.py:1149`) already
computes whether a path is free or charged. Render it per finding at the decision point:
`FIX: free (non-judgeable)` / `FIX: buys 1 review round` / `ACCEPT: free`. Today the builder
decides 15 dispositions with no idea that fixing the typo costs ten minutes and accepting it
costs nothing. This is the Visible Costs principle applied to the framework's own governance,
it needs no new mechanism, and #716 reports the underlying tool works and is merely
undiscoverable.

**C. Defer non-blocking findings to one end-of-branch report.** During the build cycle the
builder sees BLOCKING only; WARNING/NOTE accumulate in the store and land once, as a quality
report on the PR. Removes the diligence trigger outright — an agent cannot be pulled off-task
by findings it is not shown. Strongest single lever on round count; the cost is that cheap
in-context fixes stop happening mid-build, which is real. Pairs well with A.

**D. At-floor auto-close.** A round returning zero BLOCKING whose non-blocking yield sits
inside the measured floor (13–18) is a *no-signal* round. Record it, mark the scope at-floor,
and auto-close on the second consecutive one. Uses the empirical floor as the stopping rule
instead of a heuristic the agent can falsify.

## Recommended first cut

Options 1 + B + A, then 3 (record patches), then 4's file-sharding. Option 1 alone cuts
reader load 39% and finding supply ~36%; B fixes the inverted cost gradient for the price of a
render call; A supplies the terminating rule the data says nothing else will supply.
