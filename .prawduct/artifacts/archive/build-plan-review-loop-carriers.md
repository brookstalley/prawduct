---
artifact: build-plan
version: 2
scope: review-loop-carriers
depends_on: []
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "Review wall-clock is a P0 constraint; reviewer payload is a lever → conforms, and this plan is the lever pulled. Every carrier added is paid for: the gate line and the severity narrowing are ~17-35 words of prose each, with the worked instances in code that costs the reviewer nothing until dispatch. Neither protocol ceiling was raised; both additions were funded by trims the files' own budget comments designate."
      - "State-file growth past its size threshold is an advisory that prompts compaction, never a hard block → CONFORMS; recorded as inapplicable on first writing, and that premise was wrong. The plan does touch a state file: `fact_to_cache_record` now carries `next_action`, and `ledger_append` copies that record verbatim into each `review.critic` event, so every ledger line grows by the string — on an append-only file pruned by hand. The disposition survives on the norm's actual obligation rather than on non-applicability: the norm forbids a HARD BLOCK on size, and nothing here adds one; growth is surfaced advisorily as before. Corrected rather than quietly re-worded, because the original reasoning would have licensed the next writer to skip the question entirely. Worth stating precisely either way, because Chunk 03 does trim three files against ceilings that DO fail a test: `building.md`, `review-protocol.md` and `goals-1-3.md` are shipped reviewer payload, not state. Payload is paid for on every review and is authored, so a ceiling is affordable and a bump is a decision; state accumulates as a by-product of working, where a hard block would stop the work that produced it. Different objects, opposite correct answers."
      - "Adding a control names the yield it expects AND emits that yield observably → **Chunk 01's `diagnose_fix_churn` is a second DEPARTURE**, and its absence from this disposition was itself the gap: the norm is retroactive to controls added from 2026-07-29, so a control this plan introduced went ungraded while its siblings were graded. The advisory fires into `check_cumulative_critic`'s stderr and lands in no store, so post-release nobody can say whether it fired, how often, or wrongly — the same unobservable-over-firing shape as Chunk 02, and it cannot be retired or defended on evidence. Not mitigated in-scope: unlike the demotion count, there is no builder-facing number to ask for, and the honest fix is a persisted signal, which is the lock-in question already FILED for Chunk 02's half. Recorded here rather than fixed, and the two departures should be closed together by that one design. Its degraded path is not the gap — `unavailable` vs `None` is distinguished and the gate says which."
      - "Adding a control names the yield it expects AND emits that yield observably → DEPARTURE, recorded. Chunk 02's narrowing emits yield only half-way. Under-firing is detectable (`review-stats` groups by mode, so a verify-resolutions row still carrying warnings proves the rule never landed); over-firing is not, because a demoted OBSERVATION lives in the fork's report and `build_fact_body` carries `findings`/`counts` but drops the reviewer's prose. Verify-mode W/N will read zero post-release — true by construction, evidence of nothing. Mitigated in-scope by having the directive ask for a demotion count, so the number reaches the builder. The structured field that would make it telemetry-visible is a persisted-format change (lock-in, per `building.md`'s Decision Research) with a real design question of its own — self-reported vs. derived — so it is FILED rather than improvised into a fix batch. Surfaced by this chunk's own review, which is the norm working. **Chunk 03 CONFORMS on the same norm, and the contrast is the point.** Its yield is the count-shaped finding, which is persisted: findings live in the evidence store with their titles and recommendations, so the rate is a query over `<git-common-dir>/prawduct/evidence.jsonl` — match findings whose subject is a count, over total findings, before and after the release. Nothing new has to be recorded for it to be answerable, which is exactly what Chunk 02 lacked. Per this chunk's own rule the query is cited rather than its output: a baseline written here would be a prose copy of a number the store already owns."
  - artifact: observability-strategy
    dispositions:
      - "Terminal signals use the stable severity-prefix vocabulary; stdout = agent → conforms. `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` opens with `PRAWDUCT:` on stdout, addressed to the reviewer agent."
      - "The governance ledger has a single writer (`ledger-append`); agents never hand-author it → CONFORMS. Recorded as inapplicable on first writing, on the premise that no chunk touches a ledger event; that premise is false and the sibling `nonfunctional-requirements` disposition above already corrects it — `fact_to_cache_record`'s `next_action` reaches every `review.critic` line because `ledger_append` copies the findings record verbatim into the event's `review` payload. So this plan DOES change ledger content, and the norm still holds for the reason that matters: the content arrives through `ledger-append`, which remains the single writer, and no agent hand-authors a line. Two dispositions of the same fact disagreed for one review cycle, which is the one-home norm's own failure mode showing up inside the record that cites it."
      - "Text emitted into a governed product names no prawduct-internal identifier → conforms, and Chunk 03 is where it bites. The inert-count cap is prose a reviewer copies into a finding a product's builder reads, so it carries the plain-language reason (the figure, that nothing reads it, that no edit is wanted) and no requirement id — `CRT-3W6P` and the R-numbers stay in this plan and in non-emitted docstrings. Split out of the severity-prefix disposition above, where it had been folded in and would have gone uncounted."
  - artifact: architecture
    dispositions:
      - "An independent reviewer never mutates the session it reviews, enforced at the mutation site → conforms, untouched. Every chunk here changes what a reviewer RATES and what it is told, never what it writes; the `critic-begin`→`critic-consolidate` window that refuses `clear` is unmodified. Chunk 02's narrowing moves findings out of `findings` and into the reviewer's own report, which is the reviewer's own output — not a session write."
      - "Authority fails closed; advice fails soft → conforms, and this is the load-bearing check on Chunk 03. A severity cap looks like it weakens an authority, but NOTE and WARNING sit on the same side of the boundary: neither appears in `unresolved_blocking`, so neither gates anything, and capping between them moves nothing across. The same algebra Chunk 02's `test_it_is_true_that_only_blocking_gates` pins for the narrowing covers the cap; if `unresolved_blocking` ever admitted a WARNING, both would need re-reading together."
      - "Local-first: no network, no daemon → inapplicable. No chunk adds an I/O path of any kind."
      - "The plugin writes nothing into a governed repo except its own state, the evidence store, and the files it must reconcile → inapplicable. No write path is added or changed; Chunk 01's `next_action` rides in `.critic-findings.json`, which the lifecycle commands already regenerate."
      - "Python-implemented, never Python-specific → conforms. The count rule and the cap are language-agnostic statements about prose in records, dispatched per nothing; no gate or canary gains a language assumption."
      - "Prawduct guides and reviews; it never implements → conforms. The builder-side rule lands in a methodology guide as guidance, and the reviewer-side cap in a review protocol as a severity rule. Neither writes product code, config or tooling."
      - "Goals and verification bind; prescribed method is advice → invoked, and recorded. The plan prescribed 'a mode-conditional section' in `goals-1-3.md`; the goal was that a `verify-resolutions` reviewer meets the narrowing before assigning severity. A section in `## Severity` would have satisfied the prescription and failed the goal, since that heading sits below all three goal sections. Shipped as a preamble clause, with the ordering — not the presence — pinned by test."
      - "Every fact has one home; every other mention is a reference → conforms with a stated exception. The rule's home is `goals-1-3.md`'s preamble (the reviewer's protocol). `SKILL.md`, `review-cycle.md`'s table and its supply-side section are references; the directive is the only other authoritative statement, and it is authoritative precisely where the protocol has no rating — the escalated classes. That split is stated in both places rather than left implicit."
last_validated: 2026-08-04
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.4
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** The problem was measured, not inferred — two evidence stores and one full
consumer transcript, all on the released v3.2.3. The parent requirement (#167,
CRT-3W6P) already states the design constraint this plan honors, and the owner chose
the scope directly (layers 1+2; both sides on numbers) after seeing the measurement.

**Open assumptions / unknowns:** none that change the build.

**What would raise confidence:** N/A — the next real signal is post-release telemetry
(`prawduct-hook review-stats`), not more design.

## The problem, measured

The framework's loop-termination rule **shipped correctly in v3.2.3** and does not
reach the actor who needs it.

`methodology/building.md` "Resolve findings" and `skills/critic/review-cycle.md`
§ "The review loop terminates" both say the right thing: zero blocking ends the review,
WARNING/NOTE gate nothing, batch every fix into ONE commit, accept is the default. In
the consumer session that ran ten Critic rounds on one branch, the builder read
**neither file** (zero occurrences of either path in the transcript) and never invoked
`/prawduct:methodology`. It never entered the build cycle at all, because the branch
had no build plan — `record_lint` recorded exactly that: *"no build plan under
artifacts/ declares [this scope]"*.

Every carrier of the rule is a **pull** carrier:

| Carrier | Read by | Reached the builder |
|---|---|---|
| `methodology/building.md` § Resolve findings | a builder entering a build plan | no — no plan existed |
| `skills/critic/review-cycle.md` § The review loop terminates | nobody in the builder role | no |
| `_BATCH_FIX_DIRECTIVE` (`critic_consolidate.py`) | whoever runs `critic-consolidate` | **no — 7 reviewer-fork contexts, 0 builder contexts** |

The directive's own docstring already records why (the comment above
`RESOLUTION_IS_A_CLAIM_DIRECTIVE`):
*"Nor does it carry to the builder: the Critic skill is `context: fork`, and the fork's
report-back instruction enumerates findings and a summary, not the consolidator's
stdout."* On the single-pass path the reviewing fork runs consolidate itself, so the
one runtime carrier prints into the reviewer's context and dies there.

Meanwhile both **push** carriers that do reach the builder at the decision point say
*review again*: `check-cumulative-critic`'s `uncovered:` stderr (`gates.check_cumulative_critic`)
names two remedies, both full reviews; and findings arrive carrying `recommendation` text
with no statement of what gates.

**Scale, from the evidence stores since the v3.2.3 tag (2026-08-02):**

| | discodon | prawduct |
|---|---|---|
| review facts | 92 | 96 |
| findings | 806 | 618 |
| blocking | 30 (3.7%) | — |
| zero-blocking `verify-resolutions` rounds | 60 of 92 | 45 of 96 |
| longest consecutive chain | 9 | 4 |

Five of the ten-round session's nine `verify-resolutions` invocations open with
*"close coverage to committed HEAD"* — reviews run to satisfy a gate, not to get review
value. That is the signature this plan targets.

**The second half is supply.** A round that runs still has to find nothing new to fix,
or it manufactures the next one. `verify-resolutions` today runs Goals 1-3 over the fix
delta and rates what it notices at any severity, so round N+1 reliably hands the builder
new WARNING/NOTE work — and the review's own change-log and record prose is the surface
it walks. The narrowest recurring instance is the contestable count: roughly one finding
in eleven across that window is count-shaped, and `goals-1-3.md`'s chunk-`Type:`
paragraph actively directs doc-only Goal 1 at *"prose and numeric counts"*.

## Requirements

| Req | Source | This plan |
|---|---|---|
| R1 — the exit condition reaches the builder without depending on a file the builder may never open | #167 ("nothing detects an agent running round N+1 against an already-passing gate") | Chunk 01 |
| R2 — the gate that reports the gap distinguishes fix churn from new work, and names the disposition escape | #167 ("the discriminator is what moved the tree between rounds") | Chunk 01 |
| R3 — a re-review cannot manufacture non-blocking work | #167 open question 3 ("whether verify-resolutions should review the delta at all") | Chunk 02 |
| R4 — inert contestable counts stop generating correction rounds, on both the writing and the reviewing side | the numbers item filed 2026-08-04 | Chunk 03 |

**Out of scope, deliberately:** #167's `critic-begin` *refusal*. Refusing a round leaves
coverage open with no path to close it — the PR gate then blocks with no remedy, which
is a worse failure than the loop. The refusal needs a paired coverage-closing route
designed first; this plan makes the loop terminate without needing it.

## Status

- [x] Chunk 01: The exit condition and the fix-churn diagnosis reach the builder
- [x] Chunk 02: `verify-resolutions` adjudicates; it does not re-review
- [x] Chunk 03: Contestable counts, on both sides

Context: Plan authored 2026-08-04 on `fix/review-loop-carriers`, cut from `develop` at
`dbb42f3`, after reading the ten-round consumer transcript and both evidence stores.
Parent requirement #167 (CRT-3W6P) stays open — its structural-refusal half is
explicitly out of scope here.

Chunk 01 is **complete**: three commits (`a92ea7b`, `7a2b3c3`, `d7ba236`), suite green
(`prawduct-hook test-status`), and `check-cumulative-critic` **satisfied** — coverage
spans merge-base to HEAD over 3 review facts with 0 unresolved blocking.

Three review rounds, each one gate-required and none warning-driven: the cumulative
(0 blocking, 7W/11N), a verify pass to record the resolution facts and close coverage
after the fix batch (which raised 1 genuine BLOCKING — the handoff carrier had no
test), and a third to clear that blocker. Every non-blocking finding was dispositioned
rather than fixed-and-re-reviewed: **11 accepted as facts, 12 fixed in two batches**,
zero filed. The third reviewer stated plainly that round 4 was not gate-required, and
the loop stopped there.

Design change worth carrying: the gate line is **code-owned** (`next_action_line`,
emitted as `NEXT-ACTION:`) and the protocols only order it relayed. Forced by the two
protocol files sitting at hard token ceilings, and better anyway — the builder meets
the same sentence from the fork's report, from `.critic-findings.json`, and now from
the generated handoff. Neither ceiling was raised; both additions were funded by trims
the files' own budget comments designated. **Carry that pattern into Chunk 02**: put
the verify-resolutions narrowing in a dispatch directive beside
`RESOLUTION_IS_A_CLAIM_DIRECTIVE` (emission site `cmd_critic_begin`, already gated on
the mode) rather than in `goals-1-3.md`, which has ~8 tokens of headroom.

Chunk 02 is **complete**. Both findings owed in from Chunk 01's dispositions on
`rev-20260804T181325Z-071df9b4` shipped in the same batch: `diagnose_fix_churn` now
*requires* `diff_fn`/`key_fn` with the unreachable unmemoized fallback deleted (a
dropped argument is a `TypeError`, not a ~5-minute hang on the interactive PR path),
and `test_next_action_survives_a_clean_pass_with_no_findings`'s docstring states what it
actually pins.

**The one deviation, recorded not narrowed:** the `goals-1-3.md` deliverable was written
as "a mode-conditional section" and shipped as a one-sentence preamble clause. The
ceiling forced the size (1992 → 1994 of <2000, funded by trims the file's own budget
comment designates); *placement* was the more interesting constraint, and it came from
`learnings.md` rather than from the plan. `## Severity` is the obvious home and sits
below all three goal sections, so a reviewer has assigned every WARNING before reaching
it — the same present-and-inert shape as the `SKILL.md` header that said read
`review-protocol.md` "first" 26 lines above the routing that said otherwise, with six
artifact-measuring guardrails green throughout. The rule went in the preamble and
`test_the_protocol_carries_it_before_any_severity_is_assigned` asserts the *ordering*.
Chunk 01's split-by-cost pattern carried cleanly: the 17-word rule in prose, the worked
instances and descent in `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` where there is no budget.

The narrowing also surfaced a contradiction the plan had not anticipated:
`review-cycle.md` step 3 rated "a workaround instead of root cause" **WARNING** inside
the one mode that now records no warnings. Re-routed rather than deleted — a WARNING
gates nothing, so it was the wrong instrument too; the honest verdict is that the
finding is unresolved, expressed by withholding the resolution, which fails closed.

Chunk 02's review was a coordinator `final` (`rev-20260804T184741Z-4692c54c`): **0 blocking,
8 warnings, 8 notes**, dispositioned in ONE pass — 13 fixed in one commit, 2 accepted as
recorded facts, 1 filed. All three reviewers converged on the same seam, and they were right:
the five-class carve-out claimed those classes were "already BLOCKING-rated in `goals-1-3.md`",
and that was **false for two of five** (security is mixed there — auth/authz and vulnerable
dependencies are WARNING — and fix-by-fudging is not rated in that file at all). A safety
argument resting on a false claim is not a safety argument; the carve-out is now an escalation
that says so, with the guardrail split in two so neither half can drift silently.

The `verify-resolutions` pass over that fix commit (`rev-20260804T191544Z-ea418c92`) recorded
**0 findings, 13 fixed / 1 waived**, and `check-cumulative-critic` is **satisfied** —
merge-base→HEAD over 5 review facts, 0 unresolved blocking. Two rounds, both gate-required,
and the reviewer stated that nothing in the second required another.

**The acceptance criterion was met by the pass that tested it.** "A `verify-resolutions` pass
over a clean fix delta records zero findings and the gate passes" — it did, and it reported
**5 demoted observations** with a stated count, which is the mitigation for the yield gap
working on its first real use. Those five are carried into Chunk 03's batch (which owes a
review anyway) rather than fixed now; two of them are defects in Chunk 02's own fixes, one
being the line-vs-clause slack reintroduced in a sibling of the test that just fixed it.

Next: Chunk 03 — and it is `Type: cumulative-final`, so its single `/prawduct:critic
cumulative` is both the chunk's review and the PR gate's evidence.

## Verification Strategy

Every chunk is verified by running the changed command against a real repo state, not
only by unit test: `prawduct-hook critic-consolidate` on a fixture review to read the
emitted `next_action`, and `prawduct-hook check-cumulative-critic` on a branch whose only
delta is a fix commit, to read the fix-churn NOTE. Prose changes to a fork-read protocol
are pinned by test, because nothing else can observe them.

## Build Chunks

### Chunk 01: The exit condition and the fix-churn diagnosis reach the builder

- **Description:** Make the two push carriers the builder actually meets carry the rule.
  The findings cache is read by the builder by contract, so what gates goes *in* it,
  computed in code. The `uncovered:` gate message is the exact decision point, so it
  learns to say when the gap is the builder's own non-blocking fixes.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/critic_consolidate.py` — `fact_to_cache_record` gains `next_action`,
    derived from the fact's own severity counts. Blocking present: fix them, batch into
    ONE commit, ONE `verify-resolutions`. Zero blocking: the review is over, and the
    line names `prawduct-hook disposition <fact_id> <fid> --accept "<reason>"` with its
    own review id already substituted.
  - `plugin/lib/coverage.py` — new `diagnose_fix_churn`: the newest review fact on
    HEAD's lineage, with zero unresolved blocking, whose judgeable delta to HEAD is
    confined to files that review's own findings named.
  - `plugin/lib/gates.py` — the `uncovered:` branch prints the fix-churn NOTE before the
    generic remedy, in the slot the stale-remote-base NOTE already established.
  - `plugin/skills/critic/goals-1-3.md` and `plugin/skills/critic/review-protocol.md` —
    the report-back contract gains a required closing line stating the gate verdict, so
    the fork's returned summary carries it even when the builder reads no file.
- **Tests:** unit — `next_action` for each severity shape; `diagnose_fix_churn` returns
  None for a genuine outside change (the #167 counter-example: a merge widening the delta
  past the named files) and a diagnosis for a pure fix commit; a fact with unresolved
  blocking never diagnoses as churn. Prose pins for both protocol files.
- **Acceptance criteria:** a builder that reads only `.critic-findings.json` learns the
  review is over and how to accept; a builder that runs only the gate learns its gap is
  self-inflicted and how to close it without another full review.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `verify-resolutions` adjudicates; it does not re-review

- **Description:** Round N+1 exists to answer one question — were the named findings
  resolved? Today it also walks the fix delta at full severity and hands back new
  WARNING/NOTE work, which is round N+2's supply. Narrow it: new findings in
  `verify-resolutions` are **BLOCKING only**; anything else the reviewer notices is
  reported as an advisory observation in prose, where it informs without becoming work.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `plugin/skills/critic/goals-1-3.md` — the mode-conditional rule. **Shipped as a
    one-sentence clause in the PREAMBLE, not as the "mode-conditional section" this
    line originally specified** — recorded rather than silently narrowed, for two
    reasons. (1) The file has ~5 words of headroom against a hard ceiling and its
    standing rule is trim-or-relocate; a section was unaffordable and a bump was not on
    offer. (2) The obvious home, `## Severity`, sits *below* all three goal sections, so
    a reviewer assigns every WARNING before reaching it — the section would have been
    present and inert (the `SKILL.md`-header precedent: ordering beats presence). The
    classes that matter in a fix delta (weakened tests, dropped requirements, untested
    changed behavior, security, fix-by-fudging) stay BLOCKING in this mode. **As first
    written this line claimed they were "already BLOCKING-rated" in `goals-1-3.md`, and
    the chunk's own review proved that false for two of five** — auth/authz on new
    endpoints and known-vulnerable dependencies are WARNING there, and fix-by-fudging is
    not rated in that file at all. Half the carve-out is therefore an *escalation* and
    the directive says so. Enforced across the file boundary by two guards, split so
    neither half can drift silently — the citation half is
    `test_the_carve_out_classes_the_protocol_rates_are_still_blocking` and the
    escalation half is `test_the_escalated_carve_out_classes_are_named_as_escalations`,
    which pins the protocol's *lower* rating so stale wording fails. Both judge per
    clause, not per line. (Each name is on one line deliberately: wrapping inside the
    backticks makes the plan un-greppable for the very guard it cites, which is R-7's
    own failure mode reintroduced typographically — caught by the verify pass.)
  - `plugin/lib/critic_consolidate.py` — `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`, a
    dispatch-time directive beside `RESOLUTION_IS_A_CLAIM_DIRECTIVE`, printed by
    `critic-begin` for this mode. It carries what the ceiling displaced: the worked
    instances, the measured rationale, the descent. Printed *before* the resolution
    directive — the reviewer rates the delta before it judges the prior findings, and
    the gate-weakening warning keeps the tail.
  - `plugin/skills/critic/SKILL.md` — the per-mode scope line. **Not in the original
    deliverable list; added during the build and recorded here rather than dropped.**
    That line exists so no mode has to open `review-cycle.md` for scope, and the
    narrowing *is* scope — a summary omitting it describes a mode that rates
    everything, to the first file the fork reads. Pinned, per this plan's own
    Verification Strategy, by
    `test_the_per_mode_scope_line_carries_the_severity_narrowing`.
  - `plugin/skills/critic/review-cycle.md` — the per-mode table and the termination
    section record the narrowed contract.
  - Carried in from Chunk 01's accepted findings (dispositions on
    `rev-20260804T181325Z-071df9b4`): make `key_fn` required on
    `coverage.diagnose_fix_churn` and delete the unreachable unmemoized fallback —
    a dropped argument should be a `TypeError`, not a ~5-minute hang on the
    interactive PR path; and reword the test docstring that claims a
    `fact_to_cache_record` coupling it does not assert.
- **Tests:** prose pins that the mode-conditional rule exists and that the BLOCKING
  classes are named; a directive test in the shape of `TestResolutionIsAClaimDirective`.
- **Acceptance criteria:** a `verify-resolutions` pass over a clean fix delta records
  zero findings and the gate passes — there is no round N+2 to generate.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Contestable counts, on both sides

- **Description:** Stop the exchange at its source and cap it at its sink. A count that
  nothing reads is not worth a commit, and a reviewer who corrects one should say so in
  the finding rather than leave the builder to infer it.
- **Depends on:** Chunk 02
- **Deliverables:**
  - `plugin/methodology/building.md` — the builder-side norm, beside the existing
    self-contained-comments rule: don't write a contestable count where the number is
    inert; omit it, qualify it, or cite the query that regenerates it. Load-bearing
    numbers stay exact.
  - `plugin/skills/critic/goals-1-3.md` — drop `numeric counts` from the doc-only Goal 1
    line; add the severity cap: a finding whose only subject is a count in inert prose is
    a NOTE and must carry the inert qualifier (true figure, that nothing reads it, and
    that no edit is wanted).
  - `plugin/skills/critic/review-protocol.md` — the same cap in the severity contract.
  - `plugin/skills/critic/review-cycle.md` — **not in the original deliverable list;
    added during the build and recorded here rather than dropped.** Two reasons, and
    both are coherence rather than scope creep. (1) Its Per-Chunk Type selector table
    carries the doc-only row a *second* time, verbatim — removing `numeric counts` from
    one copy and not the other leaves a reviewer that consults the table with an explicit
    mandate to hunt the very findings the cap exists to demote, which is worse than
    leaving both. (2) It receives `review-protocol.md`'s relocated "Extending This Skill"
    section (see below). Both halves are pinned.
- **Tests:** prose pins on all three files, including that `numeric counts` no longer
  appears as a doc-only Goal 1 target — asserted on both carriers of that row.

**Placement, decided the opposite way from Chunk 02, and recorded because the contrast
is the interesting part.** Chunk 02's narrowing went in the PREAMBLE precisely to stay
out of `## Severity`, which sits below all three goal sections. The cap goes IN the
`## Severity` NOTE legend entry. That is not a reversal: the narrowing governs *whether
to report at all*, a decision a reviewer makes continuously while reading the goals, so
it has to be met first; a severity cap is a *lookup* made once at write-up, and the
legend entry already owns the cap's parent rule (record-only prose is a NOTE because
rating it WARNING manufactures the next round). Splitting the instance from its parent
would have created the two-homes problem `architecture.md` forbids. Both placements are
asserted rather than assumed — `assert_inert_count_cap` requires the cap inside the
legend entry, and Chunk 02's ordering pin keeps the narrowing above Goal 1.

**Funding, since all three budgeted files started at or near zero headroom** (building
+0, `review-protocol.md` +7, `goals-1-3.md` +9). No ceiling was raised. `building.md`
paid with two Common Traps restated elsewhere — "Gold plating" (CLAUDE.md's always-loaded
principle roster, the digest stance line) and "Verification theater" (this same file's
own Verify step, both halves) — plus three micro-relocates. `review-protocol.md` paid by
relocating "Extending This Skill" to `review-cycle.md`: maintainer-facing rationale
inside a per-review payload, the same class that file's budget comment records cutting
twice. `goals-1-3.md` paid with the sentence enumerating what `critic-consolidate` does, which
the reviewer neither verifies nor uses. Its *first* funding attempt — the `graded chunk`
entry's two spelled-out guess-paths, apparently redundant under this file's own "raise
it, don't restate it" — was **rejected by a guard whose docstring names that exact edit
as the predicted casualty of a token diet here**: naming one guess-path leaves the other
readable as a clean grade, and the assumption shape then reads as a BLOCKING no `--chunk`
can clear. Second instance of a rule already in learnings, and the reason this chunk's
trims were taken *then verified by suite* rather than by reading. Full accounting in each
file's budget comment.

**Carried in from Chunk 02's verify pass** (five demoted observations, deferred into this
batch because it owed a review anyway — which is the rule Chunk 02 installed, used):
`goals-1-3.md`'s two unpinned narrowing clauses now have tests; the escalated-carve-out
guard is judged per CLAUSE, closing the line-vs-clause slack its sibling had just fixed
one method over (verified: the pre-fix assertion passes with the auth-and-authz case promoted to
BLOCKING, the new one fails); the imperative check is derived from the directive's
closing sentence instead of a four-verb whitelist that matched one verb and would have
gone red on any correct rewording; and the plan's nine undispositioned `## Direction`
norms are recorded, taking `governed-by-gap` to 0. The plan's own stale suite total went
with them — a suite-total claim in the plan shipping the rule against suite-total
claims, caught by `record_lint` on the tree that fixes it, and now citing
`prawduct-hook test-status` instead of a figure.
- **Acceptance criteria:** the doc-only protocol no longer directs reviewers to hunt
  counts; a reviewer correcting an inert count produces a NOTE that tells the builder not
  to change it.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then ONE `/prawduct:critic cumulative` — it is this chunk's review and
     the PR gate's evidence
  3. Chunk recorded complete in Status — under `views_enabled: true` that is a
     tagged change-log entry plus `prawduct-hook regen-views`, NOT a hand-flipped
     checkbox. Corrected 2026-08-04: hand-marking is what made
     `_has_unfinished_chunk` false and killed scope inference at the PR gate (#587)
