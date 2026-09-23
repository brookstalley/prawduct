# Issue #830 — Governance: Severity Should Select the Channel, Not Just the Label: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-23 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/830`

Related: #724 (the 27-round report — the parent program this and its siblings come from), #834
(open sibling, same 2026-09-18 governance-ledger scan; already has a requirements doc,
`documentation/issues/834-requirements.md`, which this one follows for style and which flags that
`scope=` is the shared join key across this whole program). #829, #831, #832, #833 are the four
closed siblings from the same scan and are load-bearing evidence for this item specifically (see
Grounding facts) — none of them has a `documentation/issues/` doc (confirmed by direct listing), so
their GitHub issue bodies and comments are the only record of what they actually decided.

## Problem

Notes are the largest severity class (53% of 4,321 findings in the original 2026-09-18 measurement)
and gate nothing, yet every one currently has to be individually dispositioned (FIX / ACCEPT / FILE)
before a review reads as resolved — the same obligation a BLOCKING finding carries. That wall of
undifferentiated findings is what makes a clean review still read as a work queue. The issue proposes
that notes leave the review result and accumulate in a standing digest read at release instead, with
warnings staying in the result but not buying their own round, and asks for some record that answers
whether a note ever mattered (prevented a later blocker).

**The headline number needs re-measurement before it grounds a design.** Sibling #829's own
2026-09-18 re-measurement comment found that the identical pooled 2026-09-18 warrant, applied to a
different sibling, "pools reviews from two different eras of the code it is about, and the split
inverts its central claim" — non-blocking findings per `verify-resolutions` round fell from 2.04 to
0.09 (96%) after a 2026-08-04 change this item's own program had not yet accounted for. The same
caution applies here: #830's 53%/2,294-notes figure is a pre/post-2026-08-04 pool, and the era split
matters (Grounding facts).

## Grounding facts

Re-verified against the current tree (2026-09-23), combining direct reads with an independent
Explore-agent pass over the same code; both converge on the facts below.

- **Review rigor is already a ratified, stage-keyed norm, and it already does most of what this issue
  asks for — at the inner stage only.** `nonfunctional-requirements.md` § Direction, *"Review rigor is
  stage-keyed"* (owner-ratified 2026-09-17): the **inner stage** — any review of an uncommitted or
  delta interval (`chunk`, `final`, `verify-resolutions`) — blocks only on the inner BLOCKING set and
  reports everything else as an **observation**: recorded, answerable, never a `findings` entry, never
  a round-buying item. The **boundary stage** — `cumulative` and the PR review — **"runs the full
  severity table and is never skipped or inferred away."** That second clause is the crux of this
  item: it is exactly what #830's "notes leave the review result" proposal would need to reconcile
  with or amend, because #830 does not scope itself to a stage.
- **The observation-demotion mechanism this norm describes is fully built and load-bearing, not
  aspirational.** `_validate_observations` (`plugin/lib/critic_consolidate.py:3106-3132`): an
  observation mirrors a finding minus severity, lives in a namespace disjoint from findings (`O-n` vs.
  finding ids), is answerable via `prawduct-hook disposition <review> O-n --accept`
  (`plugin/lib/dispositions.py`, id domain "findings PLUS observations", refusal logic at
  `:457-480`), and **refuses `severity: blocking` outright** — the array cannot smuggle a blocker past
  the gate. Consolidation **fail-closed refuses an `observations` array from a boundary-stage partial**
  (`critic_consolidate.py:4729-4740`), with the comment stating why: without the refusal, "an array
  outside `findings` that the boundary could write is... a severity-laundering path — a `cumulative`
  reviewer could put nine warnings in it and consolidate a 0/0/0 review with nothing anywhere
  reporting the difference." **This is the exact code this item's proposal collides with**, and it
  exists specifically to make the stage-keyed norm's boundary clause unbypassable.
- **Today, every severity — including NOTE — is required to take an individual disposition, and this
  is a prose/reporting obligation, not a hard code refusal.** `plugin/skills/critic/review-cycle.md:291-294`,
  verbatim: *"Severity does not exempt. BLOCKING, WARNING and NOTE all take a disposition; only the
  bar for ACCEPT differs... Exempting NOTE just moves the pump — NOTE was the majority of findings in
  the review that prompted this rule."* No function in `dispositions.py:349-554` (`record`, the
  disposition CLI writer) refuses a WARNING or NOTE disposition action — the only severity-keyed
  refusals are BLOCKING-only (`:482-505`, requires `--owner-ruling` to accept, refuses `--fixed`
  outside `verify-resolutions`). The pressure comes from `next_action_line`
  (`critic_consolidate.py:795-908`), which tells the builder to "decide the WARNING/NOTE findings in
  that SAME pass," and from the census's own reporting of `"undispositioned"` debt
  (`dispositions.py:819-843`, `_summarize`) and its rendered line, *"every finding takes an ACCEPT,
  FIX or FILE regardless of severity"* (`:915-919`).
- **That "no exemption" rule is itself a correction of an earlier, measured failure — and the failure
  mode matters for this item's design, not just its history.** `review-cycle.md:268-276`: the prior
  rule ("file the rest") let the backlog become the disposal route for every finding a thorough review
  produced; measured on this repo, open items went **50 → 180 in 26 days, 67 Critic-sourced, 53 never
  touched**. `:293-294` states plainly that exempting NOTE from disposition "just moves the pump"
  back toward that same backlog-dumping failure, because filing was the only other outlet a NOTE had.
  **A "digest" that works by filing each note as a backlog item would reproduce the exact regression
  this rule already exists to prevent.** The mechanism this item builds has to be a third route — read
  and recorded, not filed and not individually actioned — not a rebranded version of the route that
  was already tried and measured to fail.
- **Gating already excludes notes; this item is about disposition/delivery, not about what gates.**
  `coverage_algebra.py:333-344` (`unresolved_blocking`) walks only BLOCKING findings when computing
  whether a review clears a gate. `review-cycle.md:104` states the PR gate already treats WARNING and
  NOTE as advisory. The issue's own scope-out ("does not change what severity a reviewer assigns —
  only where that severity is delivered") is consistent with this: severity assignment and gating
  logic are unaffected either way.
- **Sibling #832 ("stop writing remedies for NOTE-severity findings") was closed `not_planned`
  2026-09-18, and its closing comment is the single most load-bearing piece of evidence for how this
  item should be scoped.** Quoting it directly: a branch (`feat/review-yield-instrument`, formerly
  `fix/note-remedy-contract`) was opened and stopped after one chunk, because (1) suppressing the
  remedy text "removes information rather than changing an incentive," (2) it is satisfiable by a
  reviewer simply re-rating NOTE as WARNING, defeating the metric while reading as success, and (3) it
  fights the schema — `critic_consolidate.py:3005`/`:2931` require a non-empty `recommendation` on
  every finding/observation, fail-closed. The comment's own re-measurement, **`--since 2026-08-04`**:
  of the notes that still buy a round, **`cumulative` (opus + fable) accounts for 992 of 1,141 (87%)**,
  against 137 for `chunk`/`final` and 12 for `verify-resolutions` — i.e., **inner-stage demotion has
  already absorbed almost all of the volume this issue is measuring pre-fix; the boundary stage is
  where the remaining cost actually lives.** Its explicit recommendation: *"Extending the demotion
  there is #830, not this item. It is the bigger change, because `nonfunctional-requirements.md`
  ratifies 'the boundary stage runs the full severity table and is never skipped' — so it needs a
  recorded decision or an amendment, and a plan of its own."*
- **#832's branch did ship one piece standalone, and it is already in the tree: the remedy-rate
  telemetry this item's Acceptance criteria partially need.** `plugin/lib/telemetry.py:74-75`
  (`_SEVERITIES`, `_ACTIONABLE = frozenset({"blocking", "warning"})` — notes are already coded as
  non-actionable in the framework's own telemetry), `:355-381` (per-severity `with_remedy` /
  `blank_remedy` / `no_remedy_field` counts and remedy word-length stats), rendered at `:697-710`; the
  `--since`/`--until` date-window flags on `review-stats` (`:772-797`) are also already live. Per
  #832's comment, this is "the before-measurement every one of #829–#834 will be graded against":
  baseline **1,141 of 1,141 notes carry a remedy, median 122 words** (post-2026-08-04).
- **What this telemetry does NOT answer: "did a note ever prevent a blocker."** The governance ledger
  (`.prawduct/.governance-ledger.jsonl`, `plugin/lib/ledger.py`) embeds the entire findings record —
  severity, fid, goal, summary — on every `review.critic`/`review.pr` event (`ledger.py:165-225`), and
  `review-stats` (`telemetry.py:584-671`) already aggregates B/W/N counts and an "actionable %" figure
  from it. But there is no field or join anywhere in `dispositions.py`, `evidence.py`, or
  `critic_consolidate.py` linking one finding to a *later* finding it warned about or a disposition it
  changed — the only cross-review linkage concept that exists is a review *fact* being superseded for
  gate purposes (`coverage_algebra.py:508,573,600,615`), not a per-finding causal pointer. The issue's
  own "Honest uncertainty" framing is accurate as written: this is a genuinely new capability, not
  something the ledger already answers and nobody queried.
- **`.critic-findings.json` — the file notes would need to leave — is already declared a derived view
  no gate reads**, restated three times in one module (`critic_consolidate.py:766, 807, 830`, design
  decision D7): "`critic-consolidate` output plus `.critic-findings.json` is the ONLY surface the
  builder is guaranteed to meet... no gate may read it." Reshaping what this file carries (e.g.,
  routing NOTE-severity items elsewhere) is therefore safe with respect to every gate, which all read
  the underlying review *fact* via `coverage_algebra`, not this cache.
- **A prior "digest read at release" artifact exists in this exact framework, and it was retired as a
  derived-view failure — the risk is not hypothetical.** `.prawduct/release-notes.md:1-11`: *"This
  file is history, not a current record. Nothing maintains it... Derived views are retired: the
  change log is the only record of what shipped in which release, and it always was — this was a
  digest of it."* `plugin/lib/lifecycle_repair.py:97, :116-122` now actively detects and flags a live
  `release-notes.md` as stale residue in onboarded products. Any new "notes digest" that is a
  hand- or session-maintained standing file, rather than something regenerated on demand from the
  ledger/evidence store, risks repeating this exact, already-paid-for lesson.
  `plugin/lib/release_readiness.py:42-45` (`_DIGEST_REL_PATH = "plugin/CHANGELOG.md"`) is the closest
  existing "digest read at release" precedent still standing — `check_releasability`
  (`release_readiness.py:761`, invoked as Step 0 of `documentation/release-process.md:138-145`) opens
  its topmost section and runs purely advisory content checks (`_digest_advisories`, `:623-…`, never
  touches the exit code). It is a narrative *consumer* digest specific to this plugin repo (per its
  own docstring, it "never lands in a consuming repo's tree"), not a governance-findings digest, and
  has no equivalent in a per-product `.prawduct/change-log.md` — so it is architectural precedent for
  the *pattern* (advisory-only, read at a named release step), not a ready-made mechanism to extend.
- **Naming collision risk: "digest" already names something else in this framework.**
  `plugin/hooks/digest.py` builds the SessionStart `additionalContext` "session digest," subject to
  its own hard character ceiling per `.claude/rules/learnings/core.md`'s digest-budget rule. A
  findings/notes artifact read at release is a different object serving a different reader at a
  different time; reusing the bare word "digest" without qualifying it risks exactly the ambiguity
  that rule warns about for a shared vocabulary term.
- **No project-preference surface currently carries a posture like this, but the natural home already
  exists if one is needed.** `plugin/templates/project-preferences.md` `## Workflow` (`:40-52`) hosts
  governance-posture settings of this shape (`PR creation`, `PR merge`, `Delegation`), each paired with
  an `## Enforcement` row (`:60-87`) naming its mechanism and audit home. No existing row addresses
  note/finding channel routing.

## Decisions

**1. This item's scope is the boundary stage specifically (`cumulative`, PR review) — not a rewrite of
severity delivery in general.** The inner stage (`chunk`, `final`, `verify-resolutions`) already
demotes everything below its BLOCKING set to observations, already measured effective (2.04 → 0.09
non-blocking findings per `verify-resolutions` round, #829's comment), and that item is closed.
Re-opening inner-stage behavior here would duplicate #829's disposition. What remains, per #832's own
closing recommendation and its 87%-boundary measurement, is whether and how NOTE-severity findings at
the boundary stage stop requiring individual disposition.

**2. The target behavior collides with a ratified, owner-decided norm, so this item cannot ship as a
silent behavior change — it must resolve the collision explicitly, as a recorded decision.** The
`stage-keyed review rigor` norm's boundary clause ("runs the full severity table and is never skipped
or inferred away," amended 2026-09-17) and the code that enforces it fail-closed
(`critic_consolidate.py:4729-4740`) are both direct obstacles to "notes leave the review result" at
the boundary stage. Two readings are available and design must pick one, on the record: **(a)** the
norm governs whether the boundary reviewer *assesses* against the full table (it does, unchanged —
Decision 3 below) and is silent on the *delivery channel* for an item once assessed, so this item does
not conflict with the norm as written; or **(b)** the norm's plain language ("never skipped or
inferred away") reaches delivery too, and this item needs a formal amendment through the same
`[DECISION: ...]` process the norm itself was ratified under. This item's design stage does not
proceed past this question un-answered.

**3. Severity assessment is unchanged; only what happens to a NOTE-severity item after it is
assessed changes.** Restated from the issue's own scope-out and confirmed by Grounding facts
(notes already do not gate, at either stage): a boundary-stage reviewer continues to rate every item
against the full severity table exactly as today. This item narrows to the channel a NOTE-rated item
is delivered through and the disposition obligation attached to it.

**4. The new channel must not be "file it" by another name.** `review-cycle.md:291-294`'s own
history — the prior "file the rest" default caused a measured 50→180-item, 53-untouched backlog
regression, and its author explicitly warned that exempting NOTE from disposition "just moves the
pump" toward the same failure — rules out satisfying this item by routing boundary-stage notes into
the backlog as individual filed items. The channel must be something that is recorded and queryable in
aggregate without minting N new individually-owed items — the `observations`/disposition pattern
(`dispositions.py`, `O-n` ids, answerable but not obligatory) is the closest existing precedent for
that shape, though it is inner-stage-only today and not a drop-in fit for the boundary without the
Decision-2 resolution.

**5. Whatever satisfies "read at release" is a live query over existing evidence, not a new persisted,
hand-maintained file.** The ledger already carries every finding's severity on every review event
(`ledger.py`), and `review-stats` already aggregates B/W/N counts from it
(`telemetry.py:584-671`). Building a second, separately-maintained "digest" file repeats the
`release-notes.md` derived-view failure (Grounding facts) for no benefit over querying the store that
already holds the data. If a persisted artifact is chosen anyway over a live query, it must be
regenerated at read time, never hand- or session-edited.

**6. "Did a note ever prevent a blocker" is new work, not a report against existing data.** No
existing field or join supports it (Grounding facts). This item states explicitly whether that
question stays in scope as a new causal join (which needs its own design: what counts as "prevented,"
what the linking field is, at what point it's recorded) or is descoped to the remedy-rate proxy
telemetry already ships (`with_remedy`/`blank_remedy`, `telemetry.py:355-381`) — a correlational
stand-in, not an answer to the literal question, and the difference should be stated rather than
blurred.

**7. Before design, re-run the headline measurement split by era and by stage.** The issue's
53%/2,294-notes figure is a pre/post-2026-08-04 pool; #829's own re-measurement comment shows that
kind of pool can invert a sibling item's central claim. #832's `--since 2026-08-04` boundary-stage
figure (992 of 1,141 remaining notes, 87%) is the more defensible number to design against, and it
should be re-derived fresh (`prawduct-hook review-stats --since <date>`, filtered to `stage: boundary`
/ `cumulative`) rather than copied forward.

## Requirements

MUST unless marked SHOULD.

- **CHN1** A NOTE-severity finding produced by a boundary-stage review (`cumulative`, PR review) does
  not require an individual FIX/ACCEPT/FILE disposition before that review is considered resolved —
  extending, at the boundary and pending Decision 2, the same disposition relief the inner stage's
  `observations` mechanism already provides.
- **CHN2** Before CHN1 ships in code, a recorded decision resolves whether it is compatible with the
  stage-keyed-rigor norm's boundary clause as written, or amends that norm through the same
  `[DECISION: ...]` / owner-ratification process the norm itself carries (Decision 2). The change to
  `critic_consolidate.py`'s boundary-stage observations refusal (`:4729-4740`) does not land ahead of
  this decision.
- **CHN3** A boundary-stage reviewer continues to assess every item against the full severity table —
  this item changes delivery and disposition obligation for NOTE-severity items only, never what a
  reviewer rates something (Decision 3).
- **CHN4** WARNING-severity findings at the boundary stage are unaffected by this item: they remain in
  the review result and individually dispositioned, as today. ("Warnings... never buy their own
  round" is #831's territory, already shipped; this item does not reopen it.)
- **CHN5** The mechanism that receives redirected NOTE findings does not mint a new individually-owed
  item per note (no per-note backlog filing) — per Decision 4, reusing the existing
  observations/disposition id-namespace pattern unless a concrete, stated reason rules that reuse out.
- **CHN6 (SHOULD)** "Read at release" is implemented as a live query over the existing evidence
  store/ledger, not a new persisted, hand- or session-maintained file (Decision 5).
- **CHN7** Any new artifact, field, or CLI surface this item introduces is named distinctly from the
  existing SessionStart "session digest" (`plugin/hooks/digest.py`), to avoid the vocabulary collision
  named in Grounding facts.
- **CHN8** This item states explicitly, on the record, whether "did a note ever prevent a blocker" is
  in scope as new causal-join work or descoped to the existing remedy-rate proxy telemetry — not left
  implicit (Decision 6).
- **CHN9 (SHOULD)** Before implementation, the problem-size measurement backing this item's design is
  re-run split by era (pre/post 2026-08-04) and by stage (inner/boundary), per Decision 7, and the
  design targets the boundary-stage remainder rather than the pooled two-era figure the issue text
  carries forward.

## Acceptance

- [ ] CHN2's compatibility question is resolved with a recorded decision — compatible-as-written, or a
      stated amendment — before any change to the boundary-stage `observations` refusal in
      `critic_consolidate.py`.
- [ ] A re-measurement, split by era and by stage per CHN9, grounds the design's stated target problem
      size (expected: the boundary-stage remainder, not the pooled 53%/2,294 figure).
- [ ] The design names which existing mechanism it extends (observations/disposition, a new
      evidence-store query, `review-stats`) and states why a new parallel storage mechanism is or is
      not warranted, per CHN5/CHN6.
- [ ] CHN8's scope decision (causal join vs. remedy-rate proxy) is stated explicitly in the design, not
      left to be inferred from what got built.
- [ ] The design's proposed channel for a redirected NOTE does not require an individual filed backlog
      item per note (CHN5), and explains in one sentence why it does not reproduce the failure
      `review-cycle.md:268-276` records.

## Scope-out (this item)

- Inner-stage behavior (`chunk`, `final`, `verify-resolutions`) — already shipped and measured
  effective; re-litigating it duplicates #829's closed disposition.
- WARNING-severity delivery, and the fix/accept cost-lead framing at the disposition moment — that is
  #831, already shipped (`review-cost-decision` scope).
- Suppressing or shortening a NOTE's remedy text — that was #832's proposal and was explicitly
  evaluated and rejected (closed `not_planned`) as fighting the schema and being satisfiable by
  re-rating NOTE as WARNING rather than changing the underlying incentive.
- Changing what severity a reviewer assigns to a finding, at either stage (issue's own scope-out,
  reaffirmed by Decision 3).
- The exact query/CLI surface for "read at release," the exact wording of any norm amendment CHN2
  turns out to need, and the exact design of the causal join for CHN8 if kept in scope — all
  design-stage.

## Evidence / references

- `nonfunctional-requirements.md` § Direction, *"Review rigor is stage-keyed"* — the ratified norm's
  inner/boundary split and the boundary clause this item must reconcile with.
- `plugin/lib/critic_consolidate.py:83-86` (severity vocabulary, `_SEVERITY_RANK`), `:301-304`
  (`.critic-findings.json` as the builder's only guaranteed surface), `:766, :807, :830` (D7: the
  findings cache is a derived view no gate reads), `:795-908` (`next_action_line`), `:3106-3132`
  (`_validate_observations`), `:4133-4368` (`_severity_counts`, `build_fact_body`,
  `fact_to_cache_record`), `:4729-4740` (the boundary-stage `observations` refusal — "a
  severity-laundering path").
- `plugin/lib/gates.py:634-673` (`_validate_critic_findings_data` — finding schema).
- `plugin/lib/coverage_algebra.py:333-344` (`unresolved_blocking` — gates on BLOCKING only, at either
  stage).
- `plugin/lib/dispositions.py:112-121` (severity ordering), `:349-554` (`record`, BLOCKING-only
  refusals at `:482-505`), `:639-844` (`census`, `_summarize`, `"undispositioned"`), `:851-919`
  (`render_markdown`, the "Severity does not exempt" line as rendered output).
- `plugin/lib/ledger.py:76-107` (paths), `:165-376` (`_append_event`, `ledger_append` — full findings
  record embedded per event).
- `plugin/lib/telemetry.py:57-80` (`_SEVERITIES`, `_ACTIONABLE`), `:355-381` (remedy-rate stats),
  `:584-671` (`aggregate_review_stats`, the B/W/N/actionable% instrument), `:772-797`
  (`--since`/`--until`).
- `plugin/lib/release_readiness.py:42-45` (`_DIGEST_REL_PATH`), `:441-680` (`_digest_advisories`),
  `:761` (`check_releasability`).
- `plugin/lib/lifecycle_repair.py:97, :116-122` (detects a live `release-notes.md` as stale residue).
- `.prawduct/release-notes.md:1-11` ("Derived views are retired... this was a digest of it").
- `plugin/hooks/digest.py` — the existing "session digest," the naming-collision risk in Grounding
  facts.
- `plugin/skills/critic/review-cycle.md:104` (PR gate treats WARNING/NOTE as advisory), `:268-276`
  ("Why the default moved" — the backlog-dumping regression this item must not reproduce), `:291-294`
  ("Severity does not exempt").
- `plugin/skills/pr/review-protocol.md:161-163` (PR reviewer's severity contract).
- `documentation/release-process.md:127-145` (release checklist, Step 0 = `check-releasability`).
- `plugin/templates/project-preferences.md:40-52` (`## Workflow`), `:60-87` (`## Enforcement`) — the
  natural home for a posture setting, if design decides one is needed.
- GitHub issue #830 — problem statement, proposed change, and the original acceptance criteria this
  document grounds and re-scopes.
- GitHub issue #832 (closed `not_planned`, 2026-09-18) and its closing comment — the single most
  load-bearing piece of evidence for this item's scope (the 87% boundary-stage figure, the explicit
  "extending the demotion there is #830, not this item" recommendation, and the shipped
  remedy-rate-telemetry chunk).
- GitHub issue #829 (closed `completed`, 2026-09-18) and its closing comment — the era-split
  methodology this item's own headline number should be re-run through (Decision 7 / CHN9).
- GitHub issues #831, #833 (closed `completed`, shipped as scope `review-cost-decision`,
  `.prawduct/change-log.md`, 2026-09-19 entry) — confirms what is already shipped from this program
  and therefore out of this item's scope.
- `documentation/issues/834-requirements.md` — the template this document's structure follows, and the
  source of the `scope=` join-key coordination note.
