<!-- Build Plan: upstream-dependency-policy (target: minor — adds a cross-cutting
     concern, a new spec doc, and a new advisory probe)
     Tier: 1 (Source of Truth)

     Requirements: `.prawduct/artifacts/upstream-dependency-policy-discovery.md`
     (problem, the six clauses, the three enforcement tiers, the detection design,
     five owner rulings, five open assumptions, sources checked 2026-08-05).

     Design stance, inherited from api-design and re-confirmed by the owner:
     FORCE THE DECISION, don't mandate the answer. Every gate here is WARNING or
     advisory; nothing blocks. A product records its intake terms — including
     "none" — and the nudge goes quiet.

     THE GOVERNING SENTENCE, which every chunk answers to: this policy is about
     DEPENDENCIES, not package managers. It governs any upstream artifact whose
     release someone else controls, independent of delivery mechanism. Enumerating
     ecosystems is a non-normative appendix. An ecosystem prawduct has never heard
     of is COVERED and enforced at whatever tier it can reach.
-->
---
artifact: build-plan
version: 2
scope: upstream-dependency-policy
depends_on:
  - artifact: upstream-dependency-policy-discovery
governed_by:
  - artifact: architecture
    dispositions:
      - "prawduct guides and reviews, never implements; writes no product code, config or tooling → conforms — SEE THE ROUTING NOTE BELOW; this norm changed the design"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the evidence store, and the files it must reconcile → conforms, same routing"
      - "written in Python, never specific to Python; a language with no populated rules is reported as *unchecked*, never silently passed → conforms — the scan's third verdict (*unclassified*) IS this norm applied to intake surfaces"
      - "local-first: no network, no daemon, no third-party runtime dependencies → conforms — the probe and doctor check are offline; registry reads live in the product's own tier-3 procedure, which is the product's tooling, not the governance runtime"
      - "every fact has one home; every other mention is a reference → conforms — the six clauses, the tier model and the mapping appendix live only in `plugin/docs/upstream-dependency-policy.md`; all six other surfaces cite it"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "authority fails closed; advice fails soft → conforms — every control added here is advisory or WARNING; none blocks"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms — the trusted-party register is data the agent verifies against reality, never a source of authority"
      - "a governed product's content never leaves its own repository and owner → conforms — this plan adds no network surface to the governance runtime"
      - "destructive/irreversible operations need operation-level owner approval → inapplicable because this plan adds no destructive operation"
  - artifact: nonfunctional-requirements
    dispositions:
      - "adding a control names the yield it expects AND emits that yield observably → conforms — each of the three new controls declares its expected yield in its chunk and emits it where `review-stats`-class tooling can count it; see the Yield Declarations section"
      - "review wall-clock is P0; reviewer payload is the lever → conforms — the Critic addition is one bullet inside an existing goal, held budget-neutral by same-chunk trim"
      - "state-file growth past threshold is advisory, never a hard block → inapplicable"
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes — shared committed answers vs per-clone gitignored nags → conforms — the recorded-policy fact is a shared committed answer; the advisory dismissal is a per-clone nag"
      - "governance verdicts computed from the append-only fact ledger, never model-written state → inapplicable because this plan writes no evidence-store facts"
  - artifact: operational-spec
    dispositions:
      - "gitflow — features branch off `develop` → conforms"
      - "versioning is conservative: a small feature is a patch bump → exception, recorded: minor bump. This is not a small feature — it adds a cross-cutting concern with seven pipeline legs, a new canonical spec document, and a new advisory probe. Same size class as api-design, which shipped minor."
last_validated: null
---

## THE ROUTING NOTE — the norm that changed the design

`prawduct-hook jurisdiction` surfaced a direct conflict between the requirements
document and a ratified `architecture.md` norm, and resolving it improved the design.

**The conflict.** The requirements doc's §7 says conformance drift is *"offered and
applied on confirmation,"* which read as *prawduct writes the product's `.npmrc` /
`dependabot.yml` / workflow pins.* Two architecture norms forbid exactly that:
*"Prawduct guides and reviews; it never implements. It writes no product code, no
config, and no tooling — a best practice enters as a requirement captured at
discovery, Claude Code implements it, and the Critic blocks on a requirement that
went unimplemented"*; and *"the plugin writes nothing into a governed repo except its
own `.prawduct/` state, the shared evidence store, and the files it must reconcile."*
A product's package-manager and CI configs are in neither allowed set.

**The resolution — conform, don't except.** The owner's ruling ("offer, apply on
confirmation") is about *who decides*, not *which process holds the file handle*. So:
**prawduct reports the drift and presents the exact edit; the agent in session writes
it, with the owner's confirmation.** No hook, gate, or probe writes product config.
That satisfies the owner's ruling exactly, conforms to both norms, and is the routing
the first norm literally prescribes — a best practice enters as a requirement and
Claude Code implements it.

**It is also the better design**, which is why this is `conforms` and not an exception:
the agent can act on the surfaces a scanner would have to enumerate, so the
*unclassified* verdict becomes actionable instead of merely honest.

**The same reasoning removed a planned chunk.** A Python conformance scanner walking a
hardcoded list of config filenames would have re-introduced, in code, the exact
allowlist trap §6 of the requirements exists to reject — and would have violated
*"never specific to Python… reported as unchecked, never silently passed."* The
conformance scan is therefore an **agent-performed procedure guided by the spec**
(Chunk 04), not a scanner. Code does only what code does well: check whether the
policy fact exists (Chunk 05).

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each statable in one sentence and are written
up in full in `upstream-dependency-policy-discovery.md`, with five owner rulings
closed on 2026-08-05. The volatility gap — the one real risk in this domain — was
closed by research the same day (requirements §2, sources §12) rather than recalled.
Every insertion point below was located in-file this session by mapping the api-design
feature's seven legs, which is the direct structural precedent.

**Open assumptions / unknowns:** the same seven that requirements §11 now carries — §11 was reconciled to this list rather than left to disagree with it. Two were added at plan-authoring time (the Critic trigger, the probe's absent scan) and one was corrected from §11's original wording after the owner confirmed the fillable template. The five most load-bearing here:

- `[ASSUMPTION: the policy is a decision record (design_decisions.upstream_dependency_policy) + a top-level answer-store fact, with rationale and the trusted-party register as a security-model ## Direction norm entry — not a new strategy-class artifact template | MED impact | owner can promote it to its own artifact template]`
- `[ASSUMPTION: enforcement posture matches api-design end to end — advisory + doctor + janitor + Critic WARNING, never BLOCKING | MED impact | owner can request a blocking gate on updater-config drift]`
- `[ASSUMPTION: the tier-3 update procedure ships as a fillable template consuming the existing runbook machinery, not a generator and not a new artifact class | MED impact | owner can prefer methodology prose, accepting the weaker binding]`
- `[ASSUMPTION: the Critic trigger is an author-declared `**Dependency change:**` build-plan field, mirroring Foreign API's and Exposed API's opt-in model, rather than diff-detected from touched manifests | MED impact | diff-detection is the stronger guarantee but requires classifying "is this a dependency manifest", which is the allowlist trap; deferred to backlog as the api-design precedent did]`
- `[ASSUMPTION: the advisory probe fires universally on the missing fact with no codebase scan at all — because §6 made the trigger universal | LOW impact | the alternative is a scan, which is the rejected allowlist]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Keystone — the policy decision record + capture-point wiring
- [x] Chunk 02: The canonical policy spec + the security-model home
- [x] Chunk 03: Forward Critic gate + the `**Dependency change:**` field
- [x] Chunk 04: Retroactive — doctor check #15 (incl. the conformance procedure) + janitor
- [x] Chunk 05: Migration nudge — the dependency-policy advisory probe (CODE)
- [ ] Chunk 06: Coherence & close — matrix row, Known Gaps overturn, update-procedure template
Context: Plan authored 2026-08-05 on `feature/upstream-dependency-policy` (off `develop`); requirements ruled the same day. Owner confirmed both post-ruling design changes (agent-performed conformance — *"it needs to be adaptable to any platform"* — and the tier-3 fillable runbook template).

**Chunk 01 DONE.** `templates/project-state.yaml` gained the `design_decisions.upstream_dependency_policy` block (7 sub-fields incl. `surfaces`, the per-surface enforcement-tier record) and the commented-out top-level `upstream_dependency_policy_decided` answer-store fact, whose comment records *why this probe has no detection gate* so a later reader doesn't add one. `discovery.md` gained "Surface Upstream Dependency Policy" between Infrastructure Dependencies and Observability — universal trigger, defaults-with-why per Principle 20, CI actions named as the non-manifest intake surface, no ecosystem named as a requirement. `planning.md`'s Dependency Manifest bullet now carries the justification/terms split. 3743 green.

**Three carried notes from Chunk 01's learnings lookup, none silently accepted:**
1. **Chunk 03 gained a deliverable** — the session-digest line (see that chunk). Rule: a new framework-wide default that doesn't reach migrated repos isn't framework-wide.
2. **Legend-refresh gap, recorded not closed.** `templates/project-state.yaml` is scaffold-only, so an already-onboarded repo never gains the new block's commented shape guide. The api-design precedent has the identical gap and routes around it: the *methodology* carries the shape and the advisory's `recommended_action` points there. `discovery.md`'s new section does carry it, so the routing holds — but the propagation surface named by the learning (a `migrate`/refresh step) is deliberately not built. Flagged for the Chunk 01 `final` review to judge.
3. **The `docs/` pointer is deferred to Chunk 02**, where the file exists. This note originally claimed as checked fact that "no commit on this branch carries a dangling reference" — **false, and the Chunk 01 review falsified it with one `ls`**: `discovery.md` was checked and the `templates/project-state.yaml` comment written minutes earlier was not, and it carried the path. Both now name the concept, not the path; Chunk 02 adds the pointers when the target exists. The lesson is the note itself — an assertion that a check was done disarms the next reader's check, so it must not outrun what was actually checked.

**Chunk 01 review dispositions** (`rev-20260805T224332Z-55b52f6c`, 1 blocking / 4 warnings / 2 notes — all FIXED in one batch except the two notes, both accepted): the blocking builder-leg gap → Chunk 03 deliverable 4 above. The dangling template ref → fixed, and this note corrected. The legend-refresh reasoning → the plan claimed api-design has "the identical gap"; it does not, because api-design's probe and doctor check test only *presence* while this design commits doctor #15 and janitor to reading named sub-keys — `discovery.md` now names those sub-keys and says why. The "unchanged" assumptions claim → §11 reconciled. "Five clauses"/six → fixed in §4. Notes accepted: `suite-total-claim` is an inert count the protocol says to leave alone, and backlog reconciliation is unavailable on the Issues backend.

**No `verify-resolutions` round was run** — owner instruction, 2026-08-05, to fix and commit without looping. The blocking finding therefore stays unresolved in the evidence store and the Critic gate will report it until a later review spans this tree; Chunk 02's review is the natural place, since it covers the same files.

**Persisted-schema consumer queries, enumerated before the fields were designed** (planning.md's lock-in rule): the advisory probe asks *does an answer exist* (top-level fact); doctor #15 asks *does it exist* and *is it expressed per surface* (`surfaces`); janitor asks *are trusted parties still trusted and still carrying a why* (`trusted`) and *do install-time execution and pinning still match* (`install_time_execution`, `resolution_pinning`); the Critic asks *is a policy recorded* (presence). Every query has a field.

**Chunk 02 BUILT, under review.** `develop` was merged in first (the branch was cut before
v3.2.6 and the critic-review-identity work; Chunk 03 edits `review-protocol.md` and
`goals-1-3.md`, so it needed their current text and current budgets, not the pre-merge ones).
The `active_build_plan` merge conflict resolved to THIS plan on the merits — develop's side
named a plan that had finished building, which is the dormant-pointer state that slot's own
incident history is made of.

New `plugin/docs/upstream-dependency-policy.md` is the canonical home: governing sentence, six
clauses, three tiers with their three rules, and the mapping appendix marked non-normative.
`templates/security-model.md` gained an `## Upstream Dependencies` section that POINTS at it and
asks only for what is the product's own (chosen values, the trusted register each-with-its-why,
the per-surface tier reached), plus a `## Direction` routing note. The Chunk 01 `docs/` pointer
deferred to here landed on all three surfaces — `discovery.md`, `planning.md`, and the
`project-state.yaml` legend — each citing the spec directly rather than hopping through another.

**The agnosticism guard was red-verified end to end**, not just against planted strings: a
`yarn.lock` planted in Clause 5 of the real file failed
`test_no_normative_statement_names_an_ecosystem` with its line number, and was reverted. Its
form-family covers package managers, both update bots, AND manifest/lockfile names — naming a
manifest file is the allowlist trap even when no tool is named. Tokens colliding with English
(`go`, `pub`, `hex`) are guarded at their qualified spellings so the check cannot cry wolf. A
companion test pins that the same detector fires ≥5 times in the appendix, so green over the
normative body means the property holds rather than the regex being broken.

**Two one-home copies removed while writing the pointers, both self-inflicted by the same
sentence.** Adding "the clauses have one home" above prose that restated the 7-day default made
`security-model.md` and the `project-state.yaml` legend contradict themselves in place; both now
point at the spec, and a `\d+\s*days?` guard keeps the template from regaining a numeric default.
**Left deliberately:** `discovery.md` still carries the defaults in conversational form, because
its job is the elicitation script and an interviewer should not need a second file mid-interview
— the new sentence marks it as such ("what follows is how to elicit them"). Flagged for review
rather than silently kept.

**The Chunk 01 blocking finding is still unresolved in the evidence store** (line above: no
`verify-resolutions` ran, by owner instruction). `check-cumulative-critic` reports the span
uncovered. This chunk's review is the one that covers the same files.

**Chunk 02 review dispositions** (`rev-20260806T043411Z-61463dc4`, `chunk`, 1 blocking / 1 warning
/ 2 notes — all FIXED, none accepted or filed):

- **BLOCKING — the `governed_by` one-home claim was false of the tree.** `discovery.md` restated
  the 7-day default with its why, five clause substances, the tier model's Binds column and the
  intake-surface enumeration, in a form a reader can act on without following the pointer — which
  is the norm's own stated line. The finding's decisive evidence was empirical, not theoretical:
  the copies had **already diverged on day one**, before anyone edited either (spec 9 intake
  surfaces, discovery 7; "extensions" vs "plugins"). Offered an exception as the cheap route and
  it was declined on the merits — the divergence had already happened, so an exception would be
  recording a defect rather than accepting a trade. Fixed by splitting on ownership: **the spec
  owns what the policy says, `discovery.md` owns how to elicit it.** The clause substance, the
  number and the tier semantics are now citations; the trigger, the stance, the prompt-with-CI-
  actions guidance, the risk scaling and Chunk 01's reasoned sub-key list all stay, because those
  are discovery's own and not the spec's.
- **WARNING — the template's pointer did not resolve from the repo it ships into.** `security-
  model.md` is instantiated as a *product's* artifact where no `docs/` exists, and the section's
  entire routing rests on "read them there". Now qualified "in the prawduct plugin (not a path in
  this repo)", following `templates/runbook.md`, which is the one other template aimed at an
  author standing in their own repo.
- **NOTE — the guard covered one of seven surfaces.** Closed rather than accepted: the guards are
  now a parametrized sweep over `_POLICY_SURFACES`, and a roster-non-empty test stops it silently
  scanning nothing. Chunks 03-05 add their Critic bullet, doctor check, janitor theme and probe to
  that tuple; `_ECOSYSTEM_RE` is already reusable.
- **NOTE — the Deliverables list did not name the pointer edits.** Added as deliverable 4.

**A defect the fix commit found in its own tests.** Qualifying the template pointer added the
string `` `## Upstream Dependencies` `` to the Direction comment — and the test's section
extraction used `str.index`, which then bound to that *mid-sentence mention* instead of the real
heading, silently widening the scanned region to include four unrelated sections. Every assertion
still passed. `extract_section` is now line-anchored. The general shape: a test that locates its
subject by substring is one prose edit away from testing the wrong region, and it fails silently
because the wrong region usually still contains the right words.

**Chunk 02 verify pass CLEAN** — `rev-20260806T044630Z-6b01ac0b` over `c54a5dd5..1ad9a90f`
(`5f38dee`), 0 blocking / 0 findings, all four resolutions recorded. The reviewer independently
confirmed `grep -rn "7 days" plugin/` returns exactly one hit (the spec, line 24), that the spec
itself was not in the delta so R-1 was not fixed by fudging the target, and that no test was
weakened — the one deletion is the `str.index` extractor replaced by the strictly stronger
line-anchored `extract_section`.

**Three observations demoted by the verify pass, all ACCEPTED — no further round bought.** The
review said in as many words that it was over; this branch's predecessor spent a whole extra
round on a one-hunk fix after exactly that sentence, and none of these three earns one:
1. `test_does_not_restate_the_numeric_default` is now subsumed by the sweep — harmless duplicate
   coverage, not a wrong test.
2. `test_every_policy_surface_cites_the_spec` asserts the bare basename where its sibling asserts
   the `docs/` prefix, so a basename-only citation would pass. A one-word tightening; both
   surfaces carry the prefix today, so nothing is actually unguarded.
3. `discovery.md:155` uses the unqualified `docs/…` form that R-2 qualified next door. Correct as
   is — methodology files are read by the agent *from the plugin*, where that is house style; the
   template is the one that ships into a repo without a `docs/` directory. Outside the interval.
**If you touch `tests/test_v5_templates.py` for another reason, carry 1 and 2 in.**

**The cumulative gate reports `uncovered`, and that is expected here, not a defect.** The span
runs from `develop`'s merge-base and takes in Chunk 01 plus the `develop` merge, which no single
review covers. Chunk 06's `cumulative` is the designated PR gate for exactly this span.

**Chunk 03 BUILT, reviewed, fixed.** The Goal 2 `**Dependency change:**` check landed in BOTH
Critic roster files, plus the build-plan field, the session-digest line (both variants) and
`building.md`'s Decision Research extension. Every budgeted file funded by trim, no check
weakened: review-protocol.md 3611→3617, goals-1-3.md 1998→1998, building.md 4807→4808, full
digest 9990/10000.

**Two first-choice trims were forbidden by the files' own budget comments, and reading them
first is what saved the change.** Goal 4's `**Norms**` bullet reads as a pure restatement of the
Normative-authority preamble and is pinned by `test_project_preferences_blocking` contracting on
a single LINE — two editors have cut it and put it back, and I would have been the third. Step
2's `model:` restatement is an emergency patch against reviewer-model tiering. What paid
instead: the two severity-legend example lists (the sibling cut `goals-1-3.md` recorded and
generalized, never applied here), the CLAUDE.md-size bullet's definition (`building.md` owns
it), the normative block's two no-verdict claims (the class that file's own divergence rule
marks droppable there first), and the `Test-last` trap (restated `Write tests` in the same
file; its unique consequence clause folded into that step rather than dropped).

**Chunk 03 review dispositions** (`rev-20260806T052204Z-9eb39b07`, `chunk`, 1 blocking / 3
warnings / 2 notes — R-1 to R-5 FIXED, R-6 accepted-as-carry):
- **BLOCKING R-1 — the "or edits an updater config" trigger reached no declaration surface.**
  The chunk's own Description and requirements §7 both name it; every delivered surface scoped
  to upstream *code* ("adds, bumps or vendors"), which an updater-config edit does none of —
  while the spec makes bot-config enforcement **tier 2**, the only tier expressing the security
  fast path. Not descoped anywhere (§11 assumption 4 defers diff-*detection*, not this scope).
  Fixed on all four surfaces: both Critic bullets, the build-plan comment, and `planning.md`.
- **WARNING R-2 — `extract_section`'s new level-derived terminator was untested.** Reverting it
  failed nothing: only one surface uses a `###` heading and neither negative guard has a hit
  anywhere in that file, so all three sweeps passed identically before and after. Now pinned by
  `TestExtractSectionTerminator`, verified to fail against the old fixed `^## ` terminator.
- **WARNING R-3 — `session-digest-slim.md` did not get the rule.** Slim is what THIS repo's
  sessions get, and prawduct's CLAUDE.md does not restate the policy — while prawduct itself
  runs two GitHub Actions workflows, the spec's headline non-manifest intake surface. Added.
- **WARNING R-4 — the two new guards policed whole general-purpose sections.** The Goal 2
  sections are not dedicated policy sections, so the negative guards would have failed a future
  bullet that merely *illustrates* a manifest name or an interval — in the likeliest file in the
  plugin for such an illustration. `_POLICY_SURFACES` entries now carry a scope
  (`section`/`bullet`); `bullet` scopes the negative guards to the declaring line and asserts it
  is non-empty so the narrowing cannot become a vacuous scan. **Chunks 04-05 take `bullet`.**
- **NOTE R-5 — both budget comments understated headroom by one.** Reviewer wanted no edit
  (inert count), but the figures changed anyway with R-1, so the true ones are written.
- **NOTE R-6 — ACCEPTED as a carry**, recorded in Chunk 06 deliverable 5.

**Chunk 03 verify pass CLEAN** — `rev-20260806T053751Z-77b082f3` over `b50031cb..35c32212`
(`70b11a7`), 0 blocking / 0 findings, all four resolutions recorded `fixed`. The reviewer
checked R-1 by grepping the whole tree for the two narrow phrasings (exactly two hits, both the
widened lines), and confirmed R-2's new test fails against the old terminator rather than taking
the claim on trust.

**Four observations demoted by the verify pass, all ACCEPTED — no further round bought.** The
review said in as many words that it was over, and this branch's predecessor spent a whole extra
round after exactly that sentence.
1. **The `bullet`/`section` scope choice is itself unpinned** — flipping either Critic entry back
   to `section` fails nothing today, because neither negative guard has a hit anywhere in either
   file. Same shape as R-2, one level up. **CARRIED INTO CHUNK 04, not accepted-and-dropped**:
   that chunk adds the doctor and janitor surfaces, so it is the commit where a scope pin becomes
   both cheap and meaningful (a `section`-scoped doctor entry would then actually catch prose the
   `bullet` scope spares). Riding a commit already being made buys no extra round.
2. **The full digest dropped "base images"** from the parenthetical to fund "or editing an updater
   config" against 10 characters of headroom. Nothing normative is lost — the rule still reads
   "manifest or not", and the spec, `templates/security-model.md` and `templates/project-state.yaml`
   all still name base images — but the trade was unrecorded. Recorded here.
3. **The two digest variants word the same rule differently** and neither line is pinned by any
   test. Correct as it stands: slim is the framework repo's own surface and deliberately says
   "this repo's own CI actions are the case in point", which is false of a product. Divergence by
   audience, not drift.
4. **Full digest headroom is 10 chars against a hard 10,000-char gate.** The next digest edit
   trims before it adds — this is now the tightest-bound surface in the framework.

**Chunk 04 DONE.** doctor Health Check #15 (two parts: policy recorded, then the agent-performed
conformance scan with its three verdicts and the *unclassified-is-not-clean* rule), the janitor
Dependency Health extension (three intake questions naming their sub-keys, plus the currency
counterweight the theme lacked), a third "legitimately both" entry in `docs/doctor-vs-janitor.md`,
and both new surfaces registered in `_POLICY_SURFACES`. 3850 green.

**Observation 1 is DISCHARGED, not carried again.** `test_the_declared_scope_follows_whether_the_heading_is_dedicated`
derives `section`/`bullet` from whether the heading names the policy, so the choice is a contract
rather than a comment. Verified red three ways: a planted ecosystem name in #15, a planted numeric
default in the janitor closer, and a scope flip on the doctor entry.

**The tool grant widened: doctor's `allowed-tools` gained `Grep`.** #15(b) has to find upstream code
entering by routes no filename predicts, and `learnings.md` records this exact trap on this exact
file ("doctor #9's prose implied a grep its tool-grant lacked"), whose active rule is *extend the
primitive rather than narrow the requirement to fit the tool*. Read/Glob-only would have made
*unclassified* over-report by construction. Three neighbouring claims were reconciled in the same
pass: the Health Check Flow preamble, #9's "read/Glob-only" parenthetical (now a scope claim —
"does not attempt"), and the Important Note bounding Health Check to `.prawduct/`. **Not done, and
deliberately:** #9's own import scan was left alone even though Grep now makes it possible — that is
a behaviour change to an existing check, outside this chunk.

**Chunk 04 review** (`rev-20260806T121807Z-962f8803`, 0 blocking / 2 warnings / 1 note): all three
FIXED in the same commit, none accepted. R-1 — the janitor's new bullets cited nothing, so `bullet`
scope scanned only the closer and the three substantive bullets escaped both negative guards; each
now cites the clause it re-asks, taking the policed set from 1 line to 5, re-verified red. R-2 — the
canonical boundary doc's Subject row and placement rule 1 still bounded doctor to `.prawduct/`,
which #15(b) is the first check to break; both extended, with the Action-model row named as the
invariant that actually decides the split. R-3 — this plan's own Tests line said "none new". **No
`verify-resolutions` round was spent**: the fixes cost coverage (`cost-of-commit` prices 3 of 5
paths as moving it), and Chunk 06's `cumulative` is the designated gate that spans them — closing
it early buys a round and nothing else.

**Chunk 05 DONE.** `plugin/lib/dependency_policy_probes.py` (type `dependency-policy`, feature
`upstream-dependency-policy`), its composition-root line, `tests/test_dependency_policy_probe.py`,
the `_POLICY_SURFACES` `module`-scope entry, and deliverable 2b's pairing across doctor #15, the
routing row, the janitor closer and the probe's own `recommended_action`. 3872 green. The advisory
was observed firing and then resolving in a fixture repo (criterion 2 above).

**Chunk 05 review** (`rev-20260806T125257Z-969df380`, 0 blocking / 3 warnings / 1 note): R-1 to R-3
FIXED, R-4 carried into Chunk 06 deliverable 5b. R-1 — the pairing sentence claimed both surfaces
"resolve on the same recorded fact"; they do not, because #15(a) is satisfied by *either* the block
or the flat fact while the probe sees only the flat fact. Found and fixed during the builder's own
scrub *before* the review landed (the reviewer read the pre-`critic-begin` tree), by naming the
asymmetry rather than softening the claim: a filled block with no mirror now has its own reported
state, pinned by a test that reads a real state file through the real loader. R-2 — criterion 2's
end-to-end check *was* run, in a fixture that was then deleted, so nothing on disk showed it;
recorded above instead. R-3 — three prose surfaces named the advisory as a bare literal with
nothing coupling them to `PROBE_TYPE`, so a rename would leave all three routing readers to an
advisory that no longer exists with the suite green; one parametrized assert per surface now
couples them, red-verified by renaming the type. **No `verify-resolutions` round was spent** —
`cost-of-commit` prices 6 of 8 paths as moving coverage, and Chunk 06's `cumulative` is the
designated gate that spans them.

Next: Chunk 06 — coherence & close. It now carries **5b**, the framework's own unanswered nudge.

## Yield Declarations

`nonfunctional-requirements.md` binds every new control to name its expected yield and
emit it observably, so it can later be retired on evidence rather than defended on
principle. Three controls are added here:

| Control | Expected yield | Emitted where |
|---|---|---|
| `dependency-policy-undeclared` advisory (Ch. 05) | Fires once per product with no recorded policy; goes silent permanently on the recorded fact. A product where it fires and is *dismissed* rather than resolved is the signal the default is wrong. | Advisory store; dismissal vs resolution is already distinguishable there. |
| Critic Goal 2 WARNING on `**Dependency change:**` (Ch. 03) | A chunk that changes dependencies against no recorded policy. Expected to fire rarely after adoption — a sustained zero means the field is not being declared, not that the check works. | Review facts, counted by the existing `review-stats` mode grouping. |
| Doctor check #15 (Ch. 04) | Per-surface tier drift: policy recorded but not expressed where it could be. Expected to be the highest-yield of the three, because tier-1 expression is the leg products will skip. | Doctor's `degraded` classification line. |

## Build Chunks

### Chunk 01: Keystone — the policy decision record + capture-point wiring

- **Description:** Establish the one concept everything else keys off — a *recorded upstream intake policy* — and wire the two capture points (discovery elicits, planning carries). Chunks 02-06 all read this. Thin vertical slice through the spine: data model → discovery capture → planning capture.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/upstream-dependency-policy-discovery.md` (§4 the clauses, §5 the tiers, §6 the trigger design); `.prawduct/cross-cutting-concerns.md`; `plugin/templates/project-state.yaml`; `plugin/methodology/discovery.md`; `plugin/methodology/planning.md`.
- **Deliverables:**
  1. `plugin/templates/project-state.yaml` — under `design_decisions`, an `upstream_dependency_policy` block in house style, defaulting `null`: `minimum_release_age` (default 7 days), `trusted` (the two-tier definition + the declared-party register's pointer), `security_fast_path`, `install_time_execution`, `resolution_pinning`, `new_dependency_intake`, plus `surfaces` — the per-intake-surface record of **which enforcement tier was actually reached** (§5 rule 2), and `status` [active|deferred] + `rationale`. Add a top-level `upstream_dependency_policy_decided` answer-store fact, documented as a commented-out optional key matching the `api_versioning_decided` convention — absent and null both read as undecided. **No `revisit_trigger` field** (owner ruling: revisiting needs no scheduled prompt).
  2. `plugin/methodology/discovery.md` — a new "Surface Upstream Dependency Policy" section, sibling to Error Handling and Observability: asked of **every** product (§6's universal trigger — there is no detection gate), scaled to risk, offering prawduct's defaults with their why rather than interrogating (Principle 20). Must state that a product consuming no upstream code records that in one line, and must name at least one non-package-manager intake surface so the section cannot be read as being about package managers. Unbudgeted file — no trim needed.
  3. `plugin/methodology/planning.md` — the policy's bearing on planning: a chunk that adds or updates a dependency carries the decision, and the artifact-generation list gains the intake policy alongside the Dependency Manifest entry (line 24), which today covers justification only.
- **Tests:** none new (template/doc only). Guard: `plugin/templates/project-state.yaml` must remain valid YAML and existing template-shape tests must pass.
- **Acceptance criteria:**
  1. `plugin/templates/project-state.yaml` parses as valid YAML; the decision block and the commented-out answer-store fact are present in house style.
  2. `python3 -m pytest -q` green (no regressions).
  3. The discovery section is phrased with no ecosystem named as a requirement, states the universal trigger, and names a non-package-manager intake surface.
- **Critic mode:** final
  <!-- Override forward to `final`: this chunk lands the schema Chunks 02-06 consume;
       its shape must be right before anything reads it (planning.md "Override forward
       to final on an early keystone"). -->
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic final` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 02: The canonical policy spec + the security-model home

- **Description:** Write the one file that owns the policy — six clauses, three enforcement tiers, and the mapping appendix marked non-normative — and give the product-facing rationale its home. `architecture.md`'s *every fact has one home* norm makes this chunk the single point of truth every later surface cites rather than restates.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `.prawduct/artifacts/upstream-dependency-policy-discovery.md` (§4, §5, §9); `plugin/docs/norms.md` and `plugin/docs/waivers.md` (the `docs/` spec-file convention); `plugin/templates/security-model.md`.
- **Deliverables:**
  1. new `plugin/docs/upstream-dependency-policy.md` — the canonical spec. Sections: the governing sentence (dependencies, not package managers); the six clauses stated with no ecosystem named; the three enforcement tiers with their three rules (prefer strongest available; record the tier reached per surface; tier 3 is where judgment lives everywhere, not a consolation prize); and a **clearly-marked non-normative mapping appendix** carrying §9's three requirements verbatim — no policy statement may be phrased in terms of a named ecosystem, an absent ecosystem is fully covered at its best reachable tier, and a stale table is a documentation defect and never a coverage gap.
  2. `plugin/templates/security-model.md` — a new "Upstream Dependencies" section in the template's comment style, proportionate-to-risk like its siblings, pointing at the spec above for the clauses and telling the author what belongs *here*: the product's chosen values, its declared trusted parties **each with a why**, and its per-surface tier record. Note in the existing `## Direction` guidance comment that the intake policy is norm-shaped (it binds future work) so it lands as a Direction entry, not loose prose.
  3. **Guard tests** (`tests/test_v5_templates.py`): the spec file states the governing sentence; the mapping appendix is marked non-normative; no clause statement names an ecosystem (the agnosticism guard — this is the test that makes the governing sentence enforceable rather than aspirational); the security-model section exists and points at the spec rather than restating the clauses. The agnosticism and one-home guards sweep **every** surface that states the policy, not the spec alone: requirement 1 binds "policy statement, gate, or check", and a guard on one file is what let the same defect sit unnoticed on a neighbouring one.
  4. **The `docs/` pointers Chunk 01 deferred to here** — `methodology/discovery.md`, `methodology/planning.md`, and the `templates/project-state.yaml` legend each cite the spec directly once it exists. Chunk 01's carried note 3 assigns them to this chunk; listing them here so the deliverable roster matches what the chunk lands.
- **Tests:** the guard tests above. Each fails before the deliverable exists.
- **Acceptance criteria:**
  1. new `plugin/docs/upstream-dependency-policy.md` exists with all sections; the appendix is explicitly non-normative.
  2. The agnosticism guard test passes and would fail if a clause were rewritten to name npm or uv.
  3. `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 03: Forward Critic gate + the `**Dependency change:**` field

- **Description:** The forward gate that prevents new drift: a chunk that changes dependencies, or edits an updater config, against no recorded policy → WARNING. Mirrors the Foreign-API and Exposed-API bullets exactly (Goal 2, author-declared, prose-only, no hook).
- **Depends on:** Chunk 02 (the spec the bullet cites)
- **Artifacts consumed:** `plugin/skills/critic/review-protocol.md` and `plugin/skills/critic/goals-1-3.md` (Goal 2 — the Exposed-API bullet is the model, and the two files carry the check for the single-pass and coordinator rosters respectively); `plugin/templates/build-plan.md`.
- **Deliverables:**
  1. `plugin/skills/critic/review-protocol.md` and `plugin/skills/critic/goals-1-3.md` — under Goal 2, beside the Exposed-API bullet: a chunk declaring `**Dependency change:**` needs a recorded upstream intake policy (`upstream_dependency_policy` present, or an explicit deferral) → **WARNING** if missing. **Both files, not one** — they are the two roster paths and a bullet in only one is a check that fires or not depending on review mode.
  2. `plugin/templates/build-plan.md` — a `**Dependency change:**` field beside `**Foreign API:**` and `**Exposed API:**` (~line 164), same comment style.
  3. `plugin/methodology/session-digest.md` — one line in the hardest-rules block: the agent's own dependency actions are governed by the product's recorded intake policy. **Added to this chunk after Chunk 01's learnings lookup** surfaced the rule *"a new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos."* The digest is the only surface reaching every product vintage, and the owner's requirement was explicitly that the policy binds *"when the agent takes action, everywhere"* — without this line the agent-behavior arm reaches new products only. The digest is token-budget-bound: fund the line by trim in this chunk.
  4. `plugin/methodology/building.md` — extend § Decision Research's `**external dependency**` trigger (line 152, which today reads "long-term library/service reliance") so it covers the *terms* of entry, not only whether to depend at all. **This is requirements §7's second Builder deliverable**, and it had no chunk home until the Chunk 01 review found it — §7 names two (the `planning.md` section, delivered in Chunk 01, and this one) and §8 scopes the builder leg in with no carve-out. `building.md` is at its token ceiling (< 4810): fund the addition by trim in this chunk.
  5. Hold both Critic files, the digest, and `building.md` under their token ceilings (`tests/test_v5_methodology.py`: review-protocol.md < 3620, goals-1-3.md < 2000) by trimming adjacent prose **in this chunk**, never by weakening an existing check.
- **Tests:** none new (the Foreign-API and Exposed-API checks are prose-only on the same model); the existing token-ceiling tests are the guard.
- **Acceptance criteria:**
  1. The bullet reads symmetric to the Exposed-API bullet in **both** files; severity is WARNING.
  2. Both Critic files pass their token-ceiling tests; `python3 -m pytest -q` green.
  3. The build-plan field is present with a comment naming what it triggers.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 04: Retroactive — doctor check #15 (incl. the conformance procedure) + janitor

- **Description:** How an already-built product gets *found*, and the chunk that carries the conformance scan. Per the routing note, the scan is an **agent-performed procedure guided by Chunk 02's spec** — not a Python scanner — which is what lets it recognize intake surfaces no allowlist would enumerate and report *unclassified* honestly.
- **Depends on:** Chunks 01 and 02
- **Artifacts consumed:** `plugin/skills/doctor/SKILL.md` (checks #9 and #11 are the model — a check paired with an advisory probe; #14 is the highest existing number); `plugin/skills/janitor/SKILL.md` (the **Dependency Health** theme already exists at ~line 109 — extend it, do not add a theme); `plugin/docs/doctor-vs-janitor.md` (the placement rule).
- **Deliverables:**
  1. `plugin/skills/doctor/SKILL.md` — health check #15 "Upstream dependency policy", modelled on #9's report-and-recommend shape (no auto-edit). Two parts: **(a)** policy recorded? → `degraded` if not; **(b)** the conformance procedure — enumerate this repo's intake surfaces *by reading, not by matching a filename list*, and for each report **conformant / drifted / unclassified**, present the exact edit for the drifted ones, and write nothing without the owner's yes. Must state explicitly that unclassified surfaces are reported and that a scan finding them **does not report clean**. Extend the degraded-classification line. Add the routing note's rule in one sentence: prawduct reports, the agent applies.
  2. `plugin/skills/janitor/SKILL.md` — extend the existing **Dependency Health** theme with intake questions (is the recorded policy expressed at the best available tier per surface; are declared trusted parties still trusted and still carrying a why; are install-time execution and pinning still as recorded) and add the counterweight the theme currently lacks: today it asks only whether dependencies are *current*, which is one-directional pressure toward taking updates. Survey, not gate.
- **Tests:** *(revised during the build — the original line read "none new (skill prose)", which the diff outgrew.)* Both new surfaces join `_POLICY_SURFACES` in `tests/test_v5_templates.py`, which the roster's own comment had already invited ("a doctor check, a janitor theme… belong in this tuple as they land") — so the sweep, its floor (`>=4` → `>=6`) and its citation guard now cover them. Plus **one genuinely new test**, `test_the_declared_scope_follows_whether_the_heading_is_dedicated`, which is where Chunk 03's carried observation 1 is discharged: the `section`/`bullet` choice is derived from whether the heading names the policy, instead of resting on a comment nobody is bound by. Guard: existing skill-file structure tests must pass.
- **Also edited, listed above as consumed rather than as a deliverable:** `plugin/docs/doctor-vs-janitor.md`. Required by its own placement rule 3 — a concern with both facets must appear there — and it additionally said in prose that API versioning and gitignore were *the only* two such concerns, which this chunk falsifies. The Subject-axis row and placement rule 1 were extended in the same pass, because #15(b) is the first doctor check whose verdict is computed from the product's own tree.
- **Acceptance criteria:**
  1. Check #15 mirrors #9's shape, numbers correctly after #14, and states both the three-valued verdict and the reports-not-writes rule.
  2. The janitor change **extends Dependency Health** rather than adding a theme, and adds the current-ness counterweight.
  3. `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 05: Migration nudge — the dependency-policy advisory probe (CODE)

- **Description:** The ambient trigger — what tells an already-onboarded product it has no recorded intake policy without anyone thinking to run a skill. The only code chunk, and deliberately the simplest possible probe: §6 made the trigger **universal**, so it fires on the missing fact with **no codebase scan at all**. That absence is the design, not an omission — a scan here would be the allowlist the requirements reject.
- **Depends on:** Chunk 01 (the `upstream_dependency_policy_decided` fact)
- **Artifacts consumed:** `plugin/lib/api_versioning_probes.py` (the closest template); `plugin/lib/advisory_store.py` (`register_probe`, `AdvisoryCandidate`, `ProjectState`); `plugin/lib/probe_families.py` (the composition root); `plugin/lib/briefing.py` (renders advisories — no change expected).
- **Deliverables:**
  1. new `plugin/lib/dependency_policy_probes.py` — `FEATURE = "upstream-dependency-policy"`, type `dependency-policy`, v1. Fires an `info` `AdvisoryCandidate` when the top-level `upstream_dependency_policy_decided` fact is falsy; suppressed by the recorded fact. `recommended_action` points at recording the decision. Includes a `register()` mirroring the api-versioning probe's. The module docstring must record *why there is no `Codebase` scan*, so a later reader does not "fix" the omission by adding one.
  2. `plugin/lib/probe_families.py` — register the new family alongside the existing eight in `register_all()`.
  2b. **Carried from Chunk 04 — wire the check↔advisory pair in both directions, which is the half of #9's shape Chunk 04 could not land.** #9 says "this is the on-demand health-check surface for the same signal the `api-versioning` session-start advisory raises ambiently; both resolve on a recorded decision," and #15 was deliberately written *without* that sentence rather than asserting a probe that did not exist yet (the same deferral Chunk 01 made for the `docs/` pointer, for the same reason — a forward reference is a claim, and this branch has already been burned once by one). So here: add the pairing sentence to `plugin/skills/doctor/SKILL.md` check #15 naming the probe's actual advisory type, add the routing-table row's advisory phrasing to match #11-#14's, point the probe's `recommended_action` at check #15 as well as at recording the decision, and restore the "and the ambient nudge" clause to `plugin/skills/janitor/SKILL.md`'s Dependency Health closer. Verify the type string against the shipped probe rather than against this line.
  3. new `tests/test_dependency_policy_probe.py` — fires when the fact is unset; suppressed when set; suppressed when explicitly recorded as "none"; roster registration; and a regression test asserting the probe consults **no** codebase scan (the design property above, pinned so it cannot be silently changed).
  4. **The probe joins `_POLICY_SURFACES`** in `tests/test_v5_templates.py` — the roster's own comment had reserved it a slot ("the advisory probe belongs here too when it lands"). What the probe states to a reader is a few string literals rendered into *every session briefing of every product*, which makes it the widest-read statement of this policy in the plugin and the last surface that should be unguarded. The roster is heading-anchored and the probe is not markdown, so this adds a third scope, `module` (region = the whole file, second element `None`), and the scope test asks of a module the same question it asks of a heading — does the region's own name say it is dedicated to this policy.
- **Tests:** `tests/test_dependency_policy_probe.py` above, plus the three existing sweep guards now covering the probe via the roster entry (deliverable 4). Each behavior has a case that fails before the probe exists and passes after.
- **Also edited, beyond the deliverable list:** `plugin/docs/doctor-vs-janitor.md`. Its "legitimately both" entry for API versioning names that concern's ambient advisory alongside the Critic as the gated part; the upstream entry could not say the same until this chunk, and leaving the sibling bullets asymmetric is the cascade failure the previous chunk's review already caught once on this file.
- **Acceptance criteria:**
  1. New tests pass; `python3 -m pytest -q` green.
  2. Probe is registered — a session-start sync in a repo with no recorded policy surfaces the advisory in the briefing; recording the fact suppresses it. Verify end-to-end, not by unit test alone. **Observed**, against a throwaway fixture repo (`git init` + a minimal `.prawduct/project-state.yaml`), by running `prawduct-hook clear --session-start` twice: the first printed the nudge in the ADVISORIES block with both routes rendered, as `upstream-dependency-policy-dependency-policy-v1-d7cfb2`; appending the one-line fact and re-running moved that entry to `state: "resolved"` and the briefing reported "Resolved since last session: 1". The fixture was deleted afterwards, which is why this line records what was seen — a criterion asking for observation is not met by a test file, and it is not evidenced by a directory that no longer exists.
  3. No new broad `except` without a `# prawduct:allow` waiver; the probe fails open on any read error (advisory infrastructure convention).
- **Critic mode:** chunk
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 06: Coherence & close — matrix row, Known Gaps overturn, update-procedure template

- **Description:** Make the change coherent and self-documenting, then run the one cumulative review that is the PR gate. Includes the tier-3 deliverable and the correction of a framework position this work overturns.
- **Depends on:** Chunks 01-05
- **Artifacts consumed:** `.prawduct/cross-cutting-concerns.md`; `plugin/templates/runbook.md`; `plugin/docs/runbook-authoring.md`; `.prawduct/learnings.md`; `.prawduct/change-log.md`; `pyproject.toml` and `.github/workflows/tests.yml` (deliverable 5c); `tests/preferences/test_ci_workflow_conventions.py` (the sibling convention guard).
- **SCOPE AMENDED MID-CHUNK (2026-08-06), owner-ruled.** Deliverable 5b asked the owner for
  prawduct's own intake terms, and the enumeration done to ask the question well surfaced a live
  clause-5 gap: `pip install ".[dev]"` re-resolves on every CI run, so two runs a week apart can
  install different upstream code with no commit between them. Offered record-the-tier-3-reality vs.
  fix-it-now vs. its own Chunk 07; **the owner chose fix-it-now**, which adds deliverable 5c below
  and makes this chunk `code` rather than doc-only. Recorded here rather than built silently: a
  chunk that grows a code deliverable mid-flight is a requirement arriving during a build, and
  Principle 6's rule is that it goes into the plan before it goes into the tree.
- **Deliverables:**
  1. `.prawduct/cross-cutting-concerns.md` — a new row **"Upstream dependency intake"**, distinct from the existing *Dependency management* row (justification) exactly as *API design (produced)* is distinct from *Foreign API verification* (consumed). Columns per the seven legs in requirements §7.
  2. `.prawduct/cross-cutting-concerns.md` Known Gaps — **overturn the standing position.** The bullet currently reads *"Dependency management has no discovery trigger. Dependencies are a planning concern. This is by design."* Replace it: the justification half remains a planning concern; the **intake** half now has a discovery trigger, and say why the original position no longer holds (the threat model it predates). Do not delete the sentence silently — a reversed position is recorded as a reversal.
  3. new `plugin/templates/upstream-dependency-update-runbook.md` — the tier-3 deliverable (requirements §5): a fillable procedure a product derives from its recorded policy — enumerate available updates, obtain publication times, classify by tier and clause, act — built on the existing runbook machinery and pointed at from `plugin/docs/upstream-dependency-policy.md`. Written per `plugin/docs/runbook-authoring.md`. **Renamed from the planned `dependency-update-runbook.md`**, because the template also joins `_POLICY_SURFACES` at `module` scope and the roster derives "is this region dedicated to the policy" from the region's own name — for a module, its filename. The markdown surfaces spell that `upstream`; the planned name said neither that nor the Python module's `dependency_policy`, so it would have been a whole-file scan the roster could not justify. Renaming was the cheap half; the other half is below. **Two things the template must satisfy that its siblings do not:** it disambiguates the two unrelated "tier" vocabularies (policy enforcement tiers vs. runbook ceremony tiers — a tier-3 *policy* expression is normally a tier-2 *runbook*), and it names no tool, registry or manifest anywhere, because at `module` scope the agnosticism guard scans the whole file and a fillable procedure that named one toolchain would read as inapplicable to every other.
  3b. **`tests/test_v5_templates.py` — the module-scope name rule was Python-specific by accident.** It asserted `"dependency_policy" in stem`, which no markdown filename can satisfy, while the sibling `section` rule asked for `upstream`. Both are now one predicate, `_names_the_policy`, asking the single question the test's own docstring states — *does the region's own name say it is dedicated?* — of whatever names the region, with separators normalised so a hyphenated template and an underscored module answer alike. **Widened, never weakened, and verified as such**: a module named after something else, a dedicated section flipped to `bullet`, and a non-dedicated bullet flipped to `section` all still fail, each naming itself. The roster floor moves `>= 7` → `>= 8`.
  4. `.prawduct/learnings.md` — capture the two meta-lessons this work produced: (a) a policy for a multi-ecosystem concern must key its detection off *the decision being recorded*, not off enumerating the ecosystems, or the detector becomes the allowlist the policy exists to avoid; (b) `prawduct-hook jurisdiction` caught a norm conflict that plain review would have shipped — the conformance-write routing — which is evidence about *when* to run it (before writing the plan, not at review).
  5b. **Carried from Chunk 05's review — the framework has not answered its own nudge.** This repo's `project-state.yaml` carries neither `upstream_dependency_policy_decided` nor the decision block, so from Chunk 05 onward the advisory fires against prawduct itself at every session start, and no chunk in this plan homes the answer. That the nudge fires here is the feature working (prawduct runs CI actions and dev dependencies — it is squarely in scope, and this is the dogfooding case), but shipping a framework-wide nudge that its own repo ignores is the "aspirational rule" shape the norm lifecycle exists to catch. **The terms themselves are an owner decision, not one to infer** — record `design_decisions.upstream_dependency_policy` with the values the owner chooses (defaults-with-why per `docs/upstream-dependency-policy.md`) plus the flat fact, and put the rationale and the trusted register in this repo's `security-model.md` as a `## Direction` entry, exactly as the feature asks of any product.
  5c. **Raise the Python dev extra from tier 3 to tier 1 — the owner ruling above.** New root `constraints.txt` pinning the *whole resolved closure* of the `dev` extra at `==`, and `.github/workflows/tests.yml` installing through it (`pip install -c constraints.txt ".[dev]"`), which is clause 5 expressed in the toolchain's own config rather than in a procedure. Four things this deliverable must get right, each established empirically this session rather than recalled:
      - **The closure, not the four declared names.** `execnet`, `iniconfig`, `packaging`, `pluggy` and `Pygments` are pulled transitively; an unpinned transitive dependency is the same clause-5 hole one rung down.
      - **`pip --python-version` does not evaluate environment markers** — it selects wheel tags only, and evaluates markers against the *running* interpreter. pytest 9.1.1 declares `exceptiongroup; python_version < "3.11"` and `tomli; python_version < "3.11"`, and a resolution run as `--python-version 3.10` on a 3.12 host omits both. The CI matrix's floor leg is 3.10, so the pin set is the **union across environments**, including those two and win32's `colorama`. A constraint is inert for a package nothing requests, so pinning the union costs nothing on the legs that skip them.
      - **`packaging` pins to `26.2`, not the resolver's `26.3`.** 26.3 was published 2026-08-04, two days before this chunk, and prawduct's own clause 1 sets a 7-day minimum release age with `packaging` untrusted. The default install would have taken it silently. This is the policy binding its author on its first application, and it is the strongest evidence available that clause 1 is enforceable rather than decorative.
      - **`setuptools` is deliberately NOT listed.** Verified on pip 26.2.1: a `setuptools==60.0.0` pin — below `[build-system] requires`'s `>=61` floor — was ignored via **both** `-c` and `PIP_CONSTRAINT`, and the isolated build environment fetched 83.0.0 anyway. Listing it would be a decorative pin that reads as coverage and provides none, which the spec's tier rule 2 calls worse than an absent one. It is recorded as an unpinned residual in 5b's `surfaces` record and filed as follow-up.
      Guard test (new, `tests/preferences/test_dependency_resolution_pinning.py`): every name declared in the `dev` extra appears in `constraints.txt` (so a future dependency cannot be added unpinned), every entry is an exact `==` (the file records a resolution and can never become a second declaration of *what* we depend on), and the workflow installs through it. The sibling `test_ci_workflow_conventions.py` already forbids restating the dependency *list* in the workflow, and `-c constraints.txt` does not — the reference (`".[dev]"`) survives unchanged.
  5. `.prawduct/change-log.md` — the feature entry, tagged `scope=upstream-dependency-policy` per the bundle-at-release convention. **Must name one test consolidation**: Chunk 03 deleted `test_does_not_restate_the_numeric_default` (subsumed by `test_no_policy_surface_restates_the_numeric_default`, which sweeps the same file, heading and `\d+\s*days?` property). Goal 1's rule is that legitimate consolidation needs a change-log entry, and this branch bundles change-log at release — so this is where that debt is paid, and naming it here is what stops it being reconstructed from a diff three chunks later.
- **Tests:** `tests/preferences/test_dependency_resolution_pinning.py` (new, deliverable 5c — each case fails before the constraints file is wired); `python3 -m pytest -q` green; all touched token budgets pass.
- **Acceptance criteria:**
  1. The matrix row is present and accurate; the Known Gaps reversal is recorded as a reversal with its reason.
  2. The runbook template exists and is reachable from the spec.
  3. The recorded policy (5b) resolves the `dependency-policy` advisory against this repo, and the `surfaces` record states the tier each intake surface actually reaches — including the residuals, not only the wins.
  4. **5c installs what is pinned and nothing else.** Verified in a clean virtualenv: the resolved set matches `constraints.txt` exactly, `packaging` lands at 26.2 rather than the newest release, and the pin set covers the 3.10 leg's marker-gated packages. The 3.10 and 3.14 CI legs themselves are verified by CI on push — **stated as unverified locally** (no 3.10 interpreter on this machine; wheel availability for cp310/cp314 was confirmed per-package against PyPI instead).
  5. `/prawduct:critic cumulative` against `develop...HEAD` passes with no unresolved BLOCKING — the `/prawduct:pr create` gate.
- **Critic mode:** cumulative
- **Type:** cumulative-final
  <!-- Kept `cumulative-final` after the 5c amendment rather than switched to `code`: the
       marker's job is to tell the gate this is the span-closing review, and that is still
       true. The code deliverable changes what the review must look at, not which review
       this is. -->
- **Also edited, beyond the deliverable list:** `pyproject.toml` — a pointer comment from the
  `dev` extra to `constraints.txt`. The extra's existing comment calls itself "the only home for
  the test dependencies", which stays true of *which* dependencies but would read as covering
  *which versions* once a second file pins those; leaving it unqualified is the one-home claim
  going stale in place, which this branch has already been caught by twice.
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. Committed.
  3. `/prawduct:critic cumulative` run against `develop...HEAD` and blocking findings resolved — this chunk's review AND the PR gate.
  4. Backlog hygiene: file **two** deferred follow-ups via `/prawduct:backlog` — (a) the diff-detected variant of the `**Dependency change:**` trigger (open assumption 4), cross-linked to the api-design equivalent CRT-4Q7K, which is the same deferral for the same reason; and (b) the `setuptools` build-isolation residual from 5c, which no constraints mechanism reaches and which therefore needs `--no-build-isolation` or the removal of the build step altogether.

## Early Feedback Milestone

**Milestone chunk:** 04 — the first point the owner can run `/prawduct:doctor` against a real product and watch check #15 report its three-valued verdict on that product's actual intake surfaces. Chunk 05 then makes the nudge ambient.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its `/prawduct:critic <mode>` passes; the Chunk 01 keystone takes a `final` review; Chunk 06's single `cumulative` is both its own review and the `/prawduct:pr create` gate over `develop...HEAD`. Target: minor release.

- **After Chunk 01:** `final` — validate the decision-record schema before Chunks 02-06 consume it, and specifically that the `surfaces` per-tier record is shaped to carry §5 rule 2 honestly.
- **After Chunk 02:** confirm the agnosticism guard genuinely bites — write a clause naming an ecosystem, watch the test fail, revert. A guard that has never been seen to fail is not known to work.
- **After Chunk 06:** `cumulative` — all seven goals over `develop...HEAD`, the single independent-review gate before any PR.
