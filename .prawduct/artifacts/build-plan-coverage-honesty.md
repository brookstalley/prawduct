---
artifact: build-plan
version: 2
scope: coverage-honesty
branch: fix/coverage-honesty
depends_on:
  - artifact: architecture
  - artifact: nonfunctional-requirements
  - artifact: observability-strategy
  - artifact: data-model
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; unit-cost via the reviewer's payload → conforms — Chunk 01 treats the goals-1-3.md ceiling as a governed quantity, not a style preference; the plan is 4 chunks / 4 reviews, three of them 3-goal chunk mode"
      - "proportionality ratchets both ways; a control emits its yield observably → conforms, and Chunk 03 IS this norm applied. Note the norm is in-transition with retroactivity CONTAIN — controls added from 2026-07-29 carry the obligation at birth. The base-advance transfer shipped in v3.4.0 (2026-08-19), so it is a born-obligated control, not a legacy one assessed later"
      - "state-file growth is an advisory warning, never a hard block → inapplicable because no chunk here touches a size threshold; the learnings-corpus question this plan declined is recorded under Deferred"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms — every surface this plan touches is advice (a survey, a diagnostic, a release warning) and every one degrades to a note, never silence. `[[L342]]`: advice fails soft is not advice fails silent, which is this plan's whole subject"
      - "a language with no populated rules is reported as unchecked, never silently passed → conforms, and its stated reason — a silent no-op and a clean pass are indistinguishable at the output — is the ratified posture Chunk 02 applies to unscoped plans. The norm's own subject is language dispatch; the reason generalizes and is cited as such, not stretched"
      - "every fact has one home; a fact is the whole predicate, not a token inside it → RULED 2026-08-20, at the category level, recorded on the norm in architecture.md § Direction: a rule whose readers load disjoint payloads may carry one statement per carrier when a construction pins their agreement. Chunk 01 is that case and tests/test_finding_scope_rule.py is the construction"
      - "prawduct is written in Python and must never be specific to Python → conforms — markdown structure, evidence records and prose; no language-specific parsing"
      - "goals and verification bind; prescribed method is advice → conforms — the call sites named in deliverables are the author's best guess, made before the code was re-read at build time; a builder finding a better route takes it and records why"
      - "the plugin writes nothing into a governed repo except its own state and the shared evidence store → conforms — Chunk 03's only new write is a guard-refusal fact in the existing store"
      - "an independent reviewer never mutates the session it reviews → conforms — no chunk changes what a reviewer may write; Chunk 01 adds output a reviewer READS at dispatch, which is the coordinator side, not the reviewer side"
      - "local-first: governance coordination is process-spawn, atomically-written files and the git object database, no network and no third-party runtime dependency → conforms — every chunk is stdlib, files and git"
      - "prawduct guides and reviews; it never implements, and never re-implements what a product's own tooling owns → conforms — no chunk adds a check an ecosystem linter owns; Chunk 01 hands a reviewer a rule rather than mechanizing a judgement"
  - artifact: data-model
    dispositions:
      - "guard-refusal fact body: `guard` is the grouping key every yield query groups on; the interval is nested under `interval`, never spread to the body's top level; the kind is purely observational and cannot become authoritative; single sink `evidence.append_guard_refusal` → conforms — Chunk 03 adds no fact kind and no schema change, reuses the sink, and keeps the nesting its granted sibling already uses. This is the most specific norm governing Chunk 03 and it is why that chunk is cheap"
      - "facts are immutable and append-only; a state change is a new fact → conforms — Chunk 03 appends, never edits"
      - "governance verdicts are computed from the append-only ledger, never from model-written state → conforms — no chunk puts a model in a fact's write path"
      - "derived views are disposable and never authoritative → conforms — Chunk 02's published unscoped-plan fact is diagnostic; no gate reads it to reach a verdict"
      - "archival: a governance document reaches a terminal state; readers prune `archive/` at directory level; a resolver goes live-first then archive → conforms, and note this norm NAMES `plan_index.iter_scoped_plan_candidates` as one of its mechanisms. Chunk 02 therefore does not change what that walk yields for any document in this corpus; it publishes the skipped set beside it. One narrow exception is recorded rather than smoothed over: folding the `artifact:` read onto the module's single scalar reader makes `artifact: null` read as no declaration, so such a document is kept as a plan rather than excluded — the fail-safe direction the module already documents, matched by no document in this repo, and pinned at the walk by a test"
      - "every issue written to the backlog store conforms to the issue standard's title rules → inapplicable because no chunk writes a backlog item; the items this plan advances are dispositioned, not authored"
      - "a fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped → conforms, and it is the posture Chunk 02 applies one level up: an unreadable-to-the-map plan becomes a reported figure rather than a silent omission"
      - "two stores, two lifetimes — shared committed answers kept distinct from per-clone gitignored nags and caches → conforms — Chunk 03 appends to the shared evidence store, which is where its sibling grant already writes; nothing moves between the two"
      - "`backlog_service_repo` selects the authoritative backlog store and readers reach it through /prawduct:backlog → conforms — this plan read the backlog only through `backlog cache-query`, and files nothing"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with a stdout/stderr channel split → conforms — Chunk 03's denial line and Chunk 04's warning adopt the existing prefixes and channels rather than inventing wording"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms — `instance` / `class` / `none` and the transfer denial reasons are plain language; the backlog ids in this plan stay on the non-emitted side, which is where a build plan is"
      - "the governance ledger has a single writer → conforms — no chunk writes the ledger"
last_validated: 2026-08-20
---

## Requirements Confidence

**Level:** Medium

**Why:** All four problems were verified in code before this plan was written — each names the
function and line where it holds — and three were also observed firing in a consumer repo
(`../discodon`) within one day of its v3.4.0 upgrade. Chunks 02–04 are High on their own: the
requirement, the success test and the shape of the fix are each statable in one sentence, and each
has a working in-repo precedent to copy. The plan was Medium because Chunk 01's delivery route was
undecided under a pinned token ceiling. **That is now RULED and built** (see Chunk 01's
`[DECISION]` and the category ruling recorded on architecture.md's norm), so nothing in the plan
is waiting on information any longer. The level stays Medium as the honest record of what was
true when the chunks were authored; the three assumptions below are what remain vetoable.

**Open assumptions / unknowns:**

- `[ASSUMPTION: a verify-resolutions reviewer omitting the Scope line is a delivery gap, not
  reviewer non-compliance | HIGH impact | user can veto]` — the rule is absent from the only file
  that mode reads, which is sufficient to explain the omission. It is not proof the reviewer would
  comply if told; n=1 observed finding. If Chunk 01 delivers the rule and the next
  verify-resolutions finding still omits it, the escalation the v3.4.0 notes already wrote down
  applies — make it machine-checkable — and that is a separate cycle.
- `[ASSUMPTION: "Scope: none" should be blessed rather than eliminated | MED impact | user can
  override]` — the three observed uses are mandated cross-check passes that must report even when
  clean, so they name no defect to bound. The alternative is exempting those notes from the Scope
  line entirely. Blessing a value is the smaller change and keeps the line's presence uniform,
  which is what makes its absence meaningful.
- `[ASSUMPTION: the transfer's silent no-candidate outcome warrants a stored record, not only a
  message | MED impact | user can descope Chunk 03 to the message alone]` — `[[L440]]` says
  observable beats stored: do not add a field for a signal derivable from what git or the provider
  already maintains. The denial is **not** so derivable — its reason is a function of the evidence
  store's contents at the moment of the check, and the store is append-only, so a later reader
  cannot reconstruct which candidates existed then. That is the argument for storing it, and it is
  the argument Chunk 03 must survive rather than assume.

**What would raise confidence:** Chunk 01's step 0 — read `goals-1-3.md` against its ceiling pin
and cost the routes. That closes the only Medium item; nothing else is waiting on information.

## Status

- [x] Chunk 01: The Scope rule reaches every mode that raises findings, and its vocabulary covers the mandated notes
- [x] Chunk 02: The unscoped-plan blind spot gets a published fact, and its consumers state their coverage
- [ ] Chunk 03: The base-advance transfer's silent outcome gets a voice and a falsifiable record
- [ ] Chunk 04: A release-pending scope missing from the consumer digest is warned, advisory-only

Context: **Chunks 01 and 02 are complete** (2026-08-20/21). Chunk 02 shipped as
`plan_index.unscoped_candidates` (the walk) + `buildplan_refs.plans_missing_scope` (the answer
consumers call), with the shape predicate in `buildplan_refs` because `plan_index` cannot import
it back and must stay light. **Read the three `[DECISION]` blocks in the chunk before touching
this area** — the predicate was settled by measurement over this repo's own 91 known-real plans,
not by taste.

**Five surfaces now state their coverage**, which is more than the deliverables named and is the
Critic's doing: `plan_backfill.survey`, the `plan-backfill` report, the dispatch gap sentence,
`lifecycle-repair` (its own `unscoped` key plus a stale-Status walk that covers unscoped plans),
and the release gate, which **caveats** rather than suppresses. That last one was stating
something FALSE, not merely incomplete, and no chunk owned it.

Three review rounds, and rounds two and three were bought by builder omissions rather than review
churn: a class finding closed by adding call sites, one of which routed a diagnostic fact onto
`lifecycle-repair`'s fatal `unreadable` channel (permanent `/prawduct:doctor` degraded, unclearable
by `--apply`), shipped without consumer tests. Both fixed and mutation-pinned;
`check-cumulative-critic` is satisfied. Suite 4961 / 0 / 11.

Next: **Chunk 03** (the base-advance transfer's silent denial). Nothing blocks it. Two things are
worth carrying in: the cross-cutting-concerns row added here (*a scan that reports a set states
what it could not evaluate*) records that **nothing pins that a SIXTH reported total acquires the
obligation** — the construction R-7 asked for remains unbuilt, and finding R-1 of the last round
was its first cost. And `.prawduct/.handoff-notes.md` carries the rest.

One item genuinely needs the owner and blocks nothing: the category ruling recorded on
architecture.md's "every fact has one home" norm carries no owner attribution, where its two
siblings say "Owner decision, 2026-07-31" / "Owner amendment, 2026-08-11". It is captured in the
vetoable `[DECISION: … | user can veto/override]` shape, so it conforms — but a reader cannot tell
proposed from ratified at a glance.

## Scaffolding

Not applicable — a fix plan against a mature repo with an established suite. No new dependencies,
no new structure, no initialization. `python3 -m pytest` at the repo root runs everything; every
chunk adds to the existing `tests/` tree.

### Verification Strategy

Tests carry chunks 01, 02 and 04: each fix has a deterministic predicate and a natural failing case
to pin first. Two test-design rules bind across the plan and are not restated per chunk:

- **Never derive a fixture from the mechanism under test** (`[[L502]]`) — a fixture built by asking
  the resolver converts that resolver's failure into a skip, and a skip is indistinguishable from a
  pass. Walk the directory; make the precondition an `assert` that names the defect.
- **Prove the guard can go red against the real corpus** (`[[L504]]`, `[[L448]]`) — a test re-read
  from the same frontmatter the map is keyed from is a consistent lie agreeing with itself. Every
  chunk here needs a positive control: confirm the instrument moves when it should, not only that
  it is quiet when nothing is wrong.

Chunk 03 additionally needs an exercised path — the transfer's outcomes are reachable only through
a real span, so verify by constructing a branch whose base advanced and reading what the gate
prints, not by asserting a reason string in isolation.

Chunk 01 has a verification layer no test reaches: after it ships, the next `verify-resolutions`
review in this repo either carries a Scope line on a site-naming finding or it does not. That is
what the headline assumption is waiting on, and it belongs in the chunk-close reflection.

## Build Chunks

### Chunk 01: The Scope rule reaches every mode that raises findings, and its vocabulary covers the mandated notes

- **Description:** The `**Scope:** instance | class` finding-format rule lives only in
  `plugin/skills/critic/review-protocol.md`, which `final` and `cumulative` read. `chunk` and
  `verify-resolutions` read `plugin/skills/critic/goals-1-3.md`, which has no Scope rule at all —
  so a `verify-resolutions` reviewer is told (by `RESOLUTION_IS_A_CLAIM_DIRECTIVE` in
  `plugin/lib/critic_consolidate.py`) to *grade* a class finding rigorously, and never told to
  *label* the new blocking findings it raises. `plugin/CHANGELOG.md` asserts that
  `verify-resolutions` has the rule and names only `chunk` as the gap; that first clause is false.

  **Step 0 is a real decision, and the governing rules pull against each other.** The authoring rule
  was left out of `goals-1-3.md` deliberately — `tests/test_critic_consolidate.py` records that the
  file "sat 2 tokens under its ceiling" when the grading clause was written, which is why that
  clause took the code-emitted route. Four constraints bound the choice:

  - `[[L78]]` — apparent duplication across governing docs may be the *receipt* for a budget already
    paid. Check for a pinning test before cutting anything, and **never fund a budget by moving
    prose between files**; raise the ceiling rather than spend the redundancy twice.
  - `[[L396]]` — if a raise is not available, cut the *class*, not the words: dates, running tallies,
    worked examples, and definitions another file owns. What looks unaffordable is usually history.
  - `[[L80]]` — a trim under a hard budget ratchets the ceiling **in the same commit**. Unratcheted
    slack is a loan the next edit collects silently and green.
  - `plugin/skills/critic/review-cycle.md` already states the placement test: maintainer guidance
    lives there precisely *because* the protocol is a payload loaded under a ceiling. A finding-
    *format* rule is read by the reviewer mid-review, so by that same test it belongs in a payload,
    not behind a reference. That narrows the space: a shared file both payloads open is likely the
    wrong answer for this rule even though it is the tidiest answer to "one home".

  `[DECISION: the authoring rule is delivered by CODE at dispatch (`FINDING_SCOPE_DIRECTIVE`,
  emitted by `critic-begin` to the modes `GOALS_1_3_MODES` names), not by prose in
  `goals-1-3.md` | the plan budgeted an ~11-token format line; step 0 found the real rule is the
  ~110-token clause at `review-protocol.md` § Severity Levels, against 3 tokens of headroom — and
  the repo has already ruled this exact case, twice: the GRADING half of this same rule took the
  code route for the identical reason, and `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`'s docstring
  records the general precedent that for the modes it serves a rating can live nowhere but the
  directive | user can veto]`

  **What step 0 changed about this chunk, recorded because the plan said something else.** The
  plan called Chunk 01 `doc-only` and priced it as a prose edit. It is a code change: the rule
  was never an 11-token format line, and the grep that suggested it was had matched
  `review-protocol.md:167`'s Output Format entry while missing the actual rule at line 124, which
  uses backticks. The plan's estimate was wrong in the direction that matters — it under-priced
  the work — and the governance checkpoint after this chunk is where that gets weighed.

  **A second finding worth naming: the `none` value cost a second budget negotiation.** Adding it
  to `review-protocol.md` needed ~13 tokens against 6 of headroom, funded by dropping a worked
  example that was *also* Python-specific in a file whose architecture norm forbids exactly that.
  That is the same rivalry this plan cited when declining `#644` — and it arrived inside the
  chunk that made the argument, which is the strongest available evidence the argument was right.

  **Third value.** Three findings in the observed consumer review used `Scope: none` — the priors
  cross-check, the learnings cross-check, and the backlog reconciliation. All three are mandated
  passes that must report even when clean, so they name no defect to bound. Bless `none` and say
  what it is for, so its use stays bounded to no-defect reporting rather than becoming the escape
  hatch from a rule with teeth.

  **The CHANGELOG correction is itself a coverage claim** (`[[L154]]`): before writing that the rule
  now reaches mode X, run the query that would falsify it — read the file that mode actually loads.
  Coverage claims are this repo's highest-frequency error class, and the clause being corrected is
  one.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction ("every fact has one
  home"), `.prawduct/artifacts/nonfunctional-requirements.md` § Direction (review wall-clock,
  payload unit-cost)
- **Deliverables:** the Scope authoring rule reaching `chunk` and `verify-resolutions` by the route
  step 0 chooses; the `none` value defined in `plugin/skills/critic/review-protocol.md` alongside
  `instance | class`; the false clause in `plugin/CHANGELOG.md` corrected to state what v3.4.0
  actually shipped and what this release fixes
- **Tests:** a test pinning that **every mode that can raise a finding reaches the Scope rule**,
  asserted per mode against the file that mode actually reads — so the next payload split cannot
  silently drop it again. This is the construction; a test naming today's two files is the
  enumeration that would not have caught the original gap. If step 0's route spends tokens, ratchet
  the ceiling pin in `tests/test_critic_consolidate.py` in the same commit, carrying the new figure
  and saying in the docstring what paid for it.
- **Acceptance criteria:** `python3 -m pytest` passes; the new per-mode test fails when the rule is
  removed from any one mode's payload; `plugin/CHANGELOG.md` no longer claims coverage that does
  not exist
  <!-- Type is the default `code`: step 0 chose the code-emitted route, so the `doc-only` this
       chunk was planned as would now be an over-declaration, which is the unsafe direction. -->
- **Done when:**
  0. Step 0 — cost the routes against the four constraints and the ceiling pin; record the choice as
     the `[DECISION]` above, in this chunk, before editing a payload file
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The unscoped-plan blind spot gets a published fact, and its consumers state their coverage

- **Description:** `plan_index.iter_scoped_plan_candidates` yields only scope-declaring build plans
  — `if scope:` and nothing else. A plan that is perfectly readable but declares no frontmatter
  `scope:` is invisible to **every** consumer of that walk, and none of them says so.
  `plan_backfill.survey` reports `shipped` / `blocked` / `unshipped` buckets that read as the whole
  artifacts directory; in the surveyed consumer repo those buckets describe 60 of 134 plans.

  **This repo has already been bitten by it, which is better evidence than the survey.** `[[L166]]`
  records the v3.3.4 recurrence: a plan tagged `scope: v3.3.4-batch` across five change-log scopes
  produced five *"no build-plan file"* advisories and a `plan-backfill` that swept nothing. Same
  root, different surface — and `[[L70]]` states the general form: a value the parser cannot read
  yields null, and **null is no answer, not a pass**.

  **The ratified posture is already written down.** `architecture.md` § Direction requires a
  language with no populated rules to be reported as *unchecked*, never silently passed, and states
  the reason generally: a silent no-op and a clean pass are indistinguishable at the output. That
  reason is what this chunk applies.

  **It is a class, and it closes by a construction, not an enumeration.** The same walk feeds
  `plugin/lib/plan_backfill.py`, `plugin/lib/lifecycle_repair.py` (twice), and two sites inside
  `plugin/lib/plan_index.py` itself — one of which is `build_scope_to_plan_map`, the map
  `release_readiness._plan_coverage_warnings` uses, where an unscoped plan yields a *false* warning
  rather than a silent skip. Fixing the three most visible callers leaves the next one blind.

  **The precedent is in the same module.** `plan_index.unreadable_candidates` solves the identical
  problem for *unreadable* files: the walk keeps swallowing them because that is right for a map,
  and the fact is published separately on a cold path for callers that need coverage honesty. Its
  docstring states the rule — "the swallow stays where the map needs it and the fact is published
  here instead." The archival norm in `data-model.md` names this walk as one of its mechanisms, so
  not changing what it yields is conformance, not caution. `[[L148]]` gives the structural reason
  the published fact must sit **outside** the walk: a check inside the fallible flow cannot catch
  that flow's own skip.

  **Known hazard for this chunk specifically** (`[[L490]]`): the fix adds a return key to
  `survey`'s result. Grep every reader of the existing keys before committing — a fix that
  relocates or re-partitions data silently unwires whoever read the old shape.

  `[REQUIREMENT SURFACED MID-BUILD 2026-08-20: what makes an UNSCOPED document a build plan]`
  The description above says "the live plans that declare no `scope:`" and assumes the walk's
  existing plan predicate answers it. It does not. `plan_index._declares_non_build_plan_artifact`
  excludes only a document declaring some *other* `artifact:` type, and treats a document
  declaring none as a plan — a fail-safe direction chosen for the map, where a declared `scope:`
  is already strong evidence of plan-ness. The unscoped population has no such evidence, and the
  predicate was never exposed to it. Measured against this repo's live `.prawduct/artifacts/` on
  2026-08-20: **22 documents pass it, and 20 are not build plans** — release plans, spikes,
  audits, investigations, `project-preferences.md`, `boundary-patterns.md`. A control that names
  20 non-plans on its first run is the shape `nonfunctional-requirements.md` § Direction removes
  by default, so the requirement is real and it decides what the operator's coverage figure
  *means*.

  `[DECISION: an unscoped document is a build plan only on POSITIVE evidence — it declares
  `artifact: build-plan`, or carries a `## Status` roster item, or carries a chunk heading |
  user can veto]` Chosen by measurement, not by taste. Across the 91 known-real build plans in
  this repo (90 archived + the live scoped one) the three signals score 90/91, 90/91 and
  **91/91**, and their union is 91/91 — no known-real plan is missed. Against the 22 unscoped
  live candidates the union names exactly 2, and both are genuinely build plans
  (`v1.5-critic-proportionality-plan.md`, which declares the type and carries 8 chunks, and
  `waiver-pragma-plan.md`, which carries a 3-item Status roster and no parseable chunk heading —
  `#642`'s cause 2 shape). Reproduce with the probe in the chunk's test.

  `[DECISION: an EXPLICIT `scope:` opt-out is not reported | user can override]`
  `parse_build_plan_frontmatter_scope` already distinguishes `(True, None)` — `scope:` set to the
  YAML null literal, the documented "do not scope-filter me" — from `(False, None)`, the key
  simply absent. Only the second is a blind spot; the first is a declared choice, and reporting a
  declared choice back as a coverage gap is a control that can never go quiet. Zero instances of
  the opt-out exist in the 138-document corpus, so this costs nothing today and keeps the
  parser's existing semantic rather than inventing a second one.

  `[DECISION: the published fact lives in `buildplan_refs`, with the walk staying in
  `plan_index` | user can veto]` The deliverable below names `plan_index.py`, written before the
  code was re-read — and the plan's own `governed_by` disposition on *"goals and verification
  bind; prescribed method is advice"* says a builder finding a better route takes it and records
  why. Here it is forced: `buildplan_refs` imports `plan_index`, so `plan_index` cannot import
  back, and the positive-evidence predicate needs `status_section_bounds` and `_CHUNK_HEADING_RE`,
  which `buildplan_refs` owns. `plan_index`'s own module docstring makes its lightness a
  requirement — it runs at every session start and every session end. So `plan_index` keeps the
  walk as `unscoped_candidates(artifacts_dir, *, looks_like_plan)` (the sibling to
  `unreadable_candidates` the deliverable asks for) and `buildplan_refs.plans_missing_scope`
  supplies the shape predicate and is what consumers call. The predicate is a REQUIRED
  keyword-only argument, because a default would hand a forgetful caller the 20-item noise list
  in silence.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction ("unchecked, never
  silently passed"), `.prawduct/artifacts/data-model.md` § Direction (archival)
- **Deliverables:** a published-fact sibling to `unreadable_candidates` in
  `plugin/lib/plan_index.py` naming the live plans that declare no `scope:`; `plan_backfill.survey`
  and the `prawduct-hook plan-backfill` report stating what the sweep could not evaluate and why,
  so the operator reads a coverage figure rather than an implied complete one; the same fact
  surfaced where `critic-begin` already reports `chunk-ref-missing unchecked`, which is `#642`'s
  remaining cause 1
- **Tests:** unit — an artifacts tree mixing scoped, unscoped and non-plan markdown returns exactly
  the unscoped plans, prunes the archive subtree, and leaves the hot walk's yield unchanged;
  integration —
  `plan-backfill` on that tree reports a nonzero could-not-evaluate count and zero on a fully-scoped
  tree. Fixtures are walked, never resolved (`[[L502]]`), and the positive control is the mixed tree
  going red before the fix.
- **Acceptance criteria:** `python3 -m pytest` passes; a `plan-backfill` dry run against a tree with
  unscoped plans never again reports a bucket total that reads as the whole directory
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The base-advance transfer's silent outcome gets a voice and a falsifiable record

- **Description:** The transfer has three outcomes and only two of them speak.
  `gates.record_transfer_grant` records a grant, deduped by span. A *degraded* check prints "the
  base-advance transfer check could not run (…)" via `gates.transfer_remedy`. But the ordinary
  denial — no candidate span survived — returns `None` from `plugin/lib/coverage.py` and prints
  nothing at all. So zero recorded firings cannot be told apart from "never offered a case," which
  is exactly the state the surveyed consumer repo is in after a day on v3.4.0.

  **The norm is the one `record_transfer_grant`'s own docstring cites, and its clock has already
  started.** `nonfunctional-requirements.md` § Direction requires a control to name its expected
  yield *and emit that yield observably*, "since it can never be retired on evidence, only defended
  on principle." The norm is **in-transition** with retroactivity **contain**: controls added from
  2026-07-29 carry the obligation at birth, earlier ones are assessed as the janitor's Norm Health
  sweep gains yield data. The transfer shipped 2026-08-19. It is born-obligated, so this is the
  norm's plain requirement rather than a retroactive tidy-up. `#655` shipped the grant half and
  scoped denials out explicitly; this is the other half.

  **The wording half is `#672`'s, and that item marks it "worth fixing either way."** It records a
  builder reading past "could not run" four times before realising it named the cheap path — an
  unavailable-check message where the operator needed the reason the transfer did not apply.
  `[[L342]]`: advice fails soft is not advice fails silent. `[[L538]]`: a refusal predicate is not a
  severity predicate — the denial reason says what happened, and does not by itself set a tier.

  **The append-volume question is the real design risk and is not hand-waved.** Denials are far more
  common than grants and the gate is polled several times a session, so a naive record per poll
  would grow the store without bound *and* invalidate `verdict_cache` on every poll, re-introducing
  the cold path v3.4.0's memo exists to remove. The grant path already solved this by keying on
  `(base_tree, target_tree, prior_base, prior_head)`, which bounds records by *distinct span*. Reuse
  that key. If a distinct-span bound is still too loose for denials, the fallback is the message
  without the record, and that trade is recorded rather than taken silently.

  **What the fact may and may not be** is fixed by `data-model.md` § Direction and needs no
  invention: `guard` is the grouping key and is authoritative even over a caller-supplied body; the
  interval nests under `interval` and never spreads to the body's top level, because that level
  carries `base_tree`/`head_tree` for coverage edges and no reader walking bodies for edges may
  mistake a refusal for one; the kind is purely observational and cannot become authoritative;
  single sink `evidence.append_guard_refusal`. Same hazard as Chunk 02 (`[[L490]]`): this adds a
  return key to the transfer result — grep the readers of the existing keys first.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` § Direction
  (proportionality), `.prawduct/artifacts/data-model.md` § Direction (guard-refusal fact body),
  `.prawduct/artifacts/observability-strategy.md` § Direction (severity vocabulary, channel split)
- **Deliverables:** a denial record alongside `record_transfer_grant` in `plugin/lib/gates.py`,
  span-deduped on the key its granted sibling uses and appended through
  `evidence.append_guard_refusal` — no new fact kind, no schema change; a denial reason from
  `plugin/lib/coverage.py` naming why the transfer did not apply rather than returning silence;
  `gates.transfer_remedy` distinguishing "denied because X" from "the check could not run", with
  the wording keeping its single home
- **Tests:** unit — a span with no surviving candidate produces a denial reason and exactly one
  record; repeated polls on an unchanged repo append nothing further; a degraded check still reads
  as unavailable and not as a denial. Positive control (`[[L448]]`): a span that *should* grant
  still grants and still records, so the instrument is shown to move in both directions.
  Beyond tests, exercise a real advanced-base span per the Verification Strategy.
- **Acceptance criteria:** `python3 -m pytest` passes; `prawduct-hook evidence list --kind
  guard-refusal` can answer "was the transfer ever offered a case" on a repo where it has never
  granted; the store does not grow per poll and `verdict_cache` is not invalidated per poll
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: A release-pending scope missing from the consumer digest is warned, advisory-only

- **Description:** `#702`, filed from the v3.4.0 cut itself: a release-pending scope can reach the
  tag with zero consumer-facing notes in `plugin/CHANGELOG.md` and no gate asks whether the digest
  covers it. At that cut, `scope=tactical-efficiency` carried nine `release=v3.4.0` change-log
  entries and no mention in the digest; the notes were hand-written after someone noticed. The
  failure is silent and asymmetric — a section full of good notes reads as finished, so the missing
  scope is invisible exactly when the digest looks healthy. `[[L192]]` is the neighbouring rule at
  entry level: the body *is* the release note, so a deliverable the prose omits ships invisibly.

  It rides with this plan because it is the same defect as the other three in different clothes: a
  surface reporting complete coverage of something it only partly saw. It is also the mechanical
  backstop for what Chunk 01 fixes by hand — Chunk 01 corrects one false digest claim; this makes
  the *absence* of a scope from the digest something a gate can see.

  **Advisory only, and that is a requirement rather than a preference.** Matching a scope to prose
  is necessarily fuzzy, and `architecture.md` § Direction splits authority from advice: a fuzzy test
  must never hold a release. `[[L132]]` bounds where it looks — "it is history, leave it" is a
  per-section test, so only the open `-dev` section states pending claims and only it is examined.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction ("authority fails
  closed; advice fails soft")
- **Deliverables:** a coverage warning in `plugin/lib/release_readiness.py`, modelled on the sibling
  `_plan_coverage_warnings` in the same module, testing each release-pending scope against the open
  `## vX.Y.Z-dev` section of `plugin/CHANGELOG.md`; advisory only — it never changes
  `check_releasability`'s exit code
- **Tests:** unit — warns once per release-pending scope absent from the open `-dev` section;
  no warning for a represented scope; the gate's exit code is identical with and without the
  warning present. Note `[[L500]]`: a test asserting against this repo's own live state pins the
  current release phase and will go red at the next cut — pin a constructed fixture, and if a
  live-state assertion is unavoidable, say which emptiness it rejects.
- **Acceptance criteria:** `python3 -m pytest` passes; replaying the v3.4.0 cut's state produces the
  warning for `scope=tactical-efficiency`
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over the whole branch —
       commit first, run it once, no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** read the corrected `plugin/CHANGELOG.md` claim, and see on the next
`verify-resolutions` review in this repo whether a site-naming finding now carries its Scope line.
That is what the plan's headline assumption is waiting on, and it is available as soon as Chunk 01
lands rather than at the end of the branch.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit is what
scopes `chunk`-mode reviews). Chunk 04's `cumulative` review makes the branch PR-ready —
`/prawduct:pr create` is gated on it and runs when the user asks for a PR.

- **After Chunk 01:** confirm the delivery route held. If step 0's decision cost more than the trim
  it was weighed against, stop and re-decide rather than carrying the cost into three more chunks.
  This is the plan's only real architectural fork.
- **Before Chunk 04:** re-read what Chunks 02 and 03 shipped against this plan's claim that all four
  are one defect class. If they are not — if "reports a subset as the whole" turned out to be a
  narrative rather than a shared root — say so in the change-log entry rather than letting the
  plan's framing outlive its evidence.

## Deferred, with reasons

Recorded here rather than lost: a deferral with no durable home degrades into nobody being able to
say what was decided, and a build plan is the free, non-judgeable place for one.

- **`#644`** (deprecation decisions checked for presence, not conformance) touches both
  `plugin/skills/critic/goals-1-3.md` and `plugin/skills/critic/review-protocol.md` — the same two
  payload files Chunk 01 opens — and looks like a free ride-along. It is not: it needs *new prose in
  the same file whose ceiling Chunk 01 is already negotiating*, so the two are rivals for one
  budget, not partners. It is also `effort:M` with an open severity-tier decision. Adjacent file is
  not the same as cheap bundle.
- **`#672`'s design halves** (superseded blockers keyed by round id; the transfer denied by any
  conflict resolution) stay in `#672`, which is `stage: design` for good reason. Only its
  diagnostic-wording half — the part the item itself marks "worth fixing either way" — is in
  Chunk 03.
- **The learnings-corpus size question.** `#369` and `#449` both shipped and the corpus has regrown:
  87KB here, 144KB in the surveyed consumer, against a 40KB threshold, with the nudge firing every
  session. `#369`'s own title records that it had already been firing without changing behaviour. A
  fourth compaction pass is the third rework (Principle 26) — the signal is that a nudge with no
  mechanism behind it is the wrong control, and that is a design question, not a sweep.
- **The proportionality norm's missing yield query.** Chunk 03 emits a signal that the norm's own
  consumer — the janitor's Norm Health sweep — cannot yet read; the enabling half is tracked as
  `LNG-5W8R`. Emitting first is still right (the record is what a later query reads, and an
  unemitted firing is unrecoverable), but this plan does not close the loop and should not be read
  as having done so.
