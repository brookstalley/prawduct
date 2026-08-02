# Release plan — v3.2.3

**Cut from:** **whole-develop at Phase 2** — the tip as of the promotion, not a pinned commit.
*(Originally recorded as `origin/develop` @ `d9fe20b`, PR #531 merged 2026-08-01. Six of the ten
classified scopes landed after `d9fe20b` and it is 76 commits behind as of 2026-08-02, so the pinned
form was describing a cut point that keeps moving. `K withheld = 0` selects whole-develop promotion,
which makes the tip the answer; restated rather than re-pinned so it cannot go stale again.)*
**Previous release:** v3.2.2

## Version decision

**Patch bump, 3.2.2 → 3.2.3.** Owner-directed ("+0.0.1"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded because a minor is arguable here and was not taken.** This release carries the largest
consumer-visible code delta since v3.2.0 — `audit_learnings_cmd.py` (+428), `backlog/migrate.py`
(+234), `critic_consolidate.py` (+175), `views.py` (+130) — and it adds a genuinely new capability
(`superseded-by=` retirement in `audit-learnings`). It stays a patch because **no persisted format
or gate semantic breaks**: `superseded-by=` is an additive metadata key that fails closed on every
ambiguity, and every new delivery site *prints* rather than gates. No behaviour an adopter depends
on changes shape.

**Corrected 2026-08-01 — the original rationale said "nothing goes live," and the
`upgrade-discovery` scope falsifies it.** That scope's Chunk 02 lifts the
`backlog-service-migration-required` hold, so the advisory now fires at `warn` in every un-migrated
repo with a structured backlog; the backlog service is still opt-in to *adopt*, but the nudge toward
it is no longer opt-in to *see*. Patch remains correct under the conservative-versioning norm — the
advisory prints and recommends, it does not gate, and nothing an adopter depends on changes shape —
but the reason is now "it prints rather than gates," not "nothing goes live." Re-recorded rather
than left standing, because a false premise in a version decision is worse than an arguable one.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| v3.2.0-golive | ships | |
| learnings-firing | ships | |
| backlog-service-v1 | ships | |
| record-mechanization | ships | |
| upgrade-discovery | ships | |
| junit-leaf-counting | ships | |
| install-reference-drift | ships | |
| backlog-burndown | ships | |
| critic-burndown | ships | |
| critic-death-signals | ships | |

`K withheld = 0` → **whole-develop promotion** (runbook Phase 2 steps 14–20), not the pruned path.
The v3.1.2 pruning does not carry forward: v3.2.0 promoted whole-develop and re-established
content-identity between `main` and `develop`, and v3.2.1/v3.2.2 held it.

### Blocker liveness — why the post-cutover refusal did not fire

**Measured, not predicted.** `check-releasability --release v3.2.3` returns **exit 0**:

```
releasable: v3.2.3 — 4 release-pending scope(s), 4 shipping, 0 withheld.
  shipping: backlog-service-v1, learnings-firing, record-mechanization, v3.2.0-golive
```

This release was expected to hit `cannot-verify-blockers:` — this repo cut over to the GitHub Issues
backlog on 2026-08-01 (`backlog_service_repo: brookstalley/prawduct`), so `.prawduct/backlog.md` is
frozen history and blocker liveness is no longer readable from it. It did not fire, and the reason is
worth recording: **the gate reads blocker liveness only for rows that name a blocker, and no row
here does.** Every scope ships, so there is no withholding decision whose premise could have expired
and nothing for the frozen backlog to be consulted about.

**Re-measured 2026-08-01, after `upgrade-discovery` joined the release.** The measurement above was
taken before the Phase 1 prep commit (`ddb6dd1`) stamped the first four scopes, and before a fifth
existed; it is kept as the historical record rather than overwritten. Current state:

```
releasable: no release-pending scopes — nothing to classify
  (228 change-log entries scanned, 207 tagged, 6 scope(s) already tagged release=v3.2.3).
```

Re-measured again when `junit-leaf-counting` joined as the sixth scope. **The counts above are from
that measurement and are now two scopes stale**, in two different ways:

- `install-reference-drift` joined as the seventh on 2026-08-02 and is classified in the table
  above. The block was deliberately not re-run for it — no row it could add names a blocker, and the
  vacuity argument below is what actually carries the conclusion.
- **`backlog-burndown` landed on develop the same day (PR #545) and is NOT classified.**
  `check-releasability --release v3.2.3` therefore returns **`not-releasable`** right now:
  *"ERROR: unclassified scope(s) … backlog-burndown"*. That is real and must be cleared before the
  release cuts — it is #545's bookkeeping debt, deliberately not absorbed here, because classifying
  another branch's scope from this one guesses at a disposition its author has not stated.

So the table is seven rows against eight release-pending scopes, and `K withheld = 0` describes the
seven that are classified, not the corpus. This is the *third* time "the counts above are the
current ones" has had to be walked back — which is the point the paragraph already makes, now with
enough instances to stop treating it as bad luck: a measurement quoted in a plan goes stale every
time the release grows. Treat the block as a snapshot with a date, and treat `check-releasability`
as the live answer.

**Cleared 2026-08-02.** `backlog-burndown` (#545), `critic-burndown` (#551) and
`critic-death-signals` (#559) are classified `ships`, taking the table to ten rows, and
`check-releasability --release v3.2.3` returns **exit 0**:

```
releasable: v3.2.3 — 3 release-pending scope(s), 3 shipping, 0 withheld.
  classification: /Users/brookstalley/source/prawduct/.prawduct/artifacts/release-plan-v3.2.3.md
  shipping: backlog-burndown, critic-burndown, critic-death-signals
```

**Read the `3` correctly — it is not the size of the release.** *Release-pending* means "has a
`scope=` key and no `release=` tag," so the seven already-stamped scopes have left the pending set.
Four were stamped by the Phase 1 prep commit (`ddb6dd1` — `backlog-service-v1`, `learnings-firing`,
`record-mechanization`, `v3.2.0-golive`) and three by follow-on classification commits (`c853796`
upgrade-discovery, `8d07019` junit-leaf-counting, `2eabf45` install-reference-drift); the set, not
any single commit, is what emptied the pending bucket. Their rows are not orphans only because the
gate's
orphan check carries a **`ships`-only re-run exemption** for rows whose entries already carry this
release's tag — the same asymmetry the runbook spells out for `withheld` rows, where the identical
situation is an error rather than an exemption. So `K withheld = 0` still selects whole-develop
promotion, and the ten rows still partition the corpus; the header count just answers a narrower
question than "what is in this release" and should not be quoted as if it answered the wider one.

**Why classifying the other two branches' scopes is bookkeeping here and not the guess the bullet
above refused to make.** That refusal was correct *while they were in flight* — a disposition is the
author's to state, and an unmerged branch might not land at all. All three have since merged to
`develop`, which settles it without anyone's intent being inferred: this release takes the
**whole-develop promotion** path, so every scope on `develop` ships by construction. The only way
one of these could be `withheld` is if a named blocker were open against it, and none is. Withholding
any of them would not be a bookkeeping variant — it would make `K > 0` and switch Phase 2 to the
pruned cherry-pick path.

The stale-counts lesson holds and this entry is another instance of it, not an exception: these
counts are a snapshot dated 2026-08-02, and `check-releasability` remains the live answer.

Per `cut-and-publish-a-plugin-release.md` step 0, `no release-pending scopes — nothing to classify`
takes the **same whole-develop promotion path** as `K withheld = 0`. The reasoning above still holds
for the same reason: no row names a blocker.

So the by-hand blocker check the runbook asks a cut-over repo for is **vacuous by construction here**,
not skipped. The distinction matters a release later, when "there was nothing to check" and "I did
not check" look identical in hindsight. The first release after this one that **withholds** a scope
is where `cannot-verify-blockers` will actually bite.

## Also shipping, unscoped — two entries the gate cannot see

The releasability gate enumerates by `scope=`, so a statusless entry with no `scope=` key is
invisible to it and **must be tagged by hand** at Phase 1 step 3. Two here:

| Change-log entry | Tag | Why unscoped |
|---|---|---|
| 2026-07-31: One home per fact, method prescriptions become advice, and the closing block gets a shape | `type=governance` | Three owner decisions (GOV-4T9P, GOV-2R8K, the closing-block shape). Norm decisions have no build plan and so no `## Status` roster to key. |
| 2026-07-31: A turn that ends without saying where things stand… (CRT-9B4K) | `type=fix` | **Deliberate and documented in the entry itself.** Adding `scope=` would make it a release-pending scope with no plan file, which `views.diagnose_scope_plan_coverage` rejects. **Updated 2026-08-01 (regen-views-is-advice ruling):** that is now a *scope-local* error — `regen-views` exits **3**, withholds nothing (there is no plan file, so that scope has no `## Status` view), and writes every other view. The original reason for leaving `scope=` off stands, but the consequence is no longer "breaks every view regeneration"; it is one non-zero exit and a named stderr line. |

Tag both with `| release=v3.2.3 | status=shipped` and **no `scope=`**. This is the same one-level-down
miss Phase 0 exists to catch, and it is REL-6Q4M's open blind spot — its fix has to cover the
planless scope, or the two controls stay mutually exclusive.

## Consumer-facing headline

> Learnings now fire where the mistake gets made rather than waiting in a file to be read — and every
> turn ends by telling you where things stand.

## What ships

**`learnings-firing` (Chunks 01–03) — the flagship.** A corpus of 159 rules was not firing, and the
diagnosis was *delivery*, not authoring. Two rules moved from storage to code-delivery — *green is
evidence only about what could have made it red* prints at `test-evidence record` when the merged
record shows judged code changed, and *a resolution is a claim about the tree* prints at
`critic-begin --mode verify-resolutions`. `audit-learnings` gained `superseded-by=`, so
consolidation is an auditable lifecycle event rather than an unauditable hand-edit. The corpus
collapsed **159 → 149** with every retired rule's distinguishing instance preserved in its
successor's heading.

**The closing block gets a shape** (`type=fix`, CRT-9B4K + an unfiled owner report). Both reports
came from *consuming* repos and neither was about a gate being wrong: a correct "safe to `/clear`"
sentence buried mid-summary is a signal not sent. The block is now `STATE` · `NEXT` · `CLEAR` as
three separate paragraphs, last.

**Two `## Direction` norms** (`type=governance`): *goals and verification bind; prescribed method is
advice* (GOV-4T9P) and *every fact has one home* (GOV-2R8K).

**`backlog-service-v1`.** The completeness gate can now see an item that arrived at the wrong status
(BKL-7V2D); the issue standard stops contradicting itself; fleet migration gains a triage norm and
the archive scope an invariant rather than a status.

**`record-mechanization`.** The learnings guard that was silently dropping three rules is fixed; the
change-log ledger spike ran and falsified its own artifact's premise.

**`v3.2.0-golive` (Chunk 06).** prawduct's own backlog migrated to GitHub Issues — 371 items, 0
stranded, `verify-migration` exit 0. Consumer-visible portion is the hardening this produced:
`migrate.py`, and `migration-scrub.md`'s corrected step ordering.

**`upgrade-discovery` (Chunks 01–03).** Everything prawduct said about itself, it said to stdout —
the agent's channel by this repo's own ratified norm — and the version banner marked itself shown, so
it never rendered again. A relay directive now sits at each emission site: the version-delta block
and the briefing's advisory block (the latter for `warn`/`urgent` only; `info` is excluded because a
nagging channel gets tuned out). Chunk 03 lifts the `backlog-service-migration-required` hold, which
is why **gate item 3 exists** — the lift routes toward an irreversible bulk write, and the relay is
what puts a person in that loop.

**`junit-leaf-counting`** (#128, contributed by @Jason-Vaughan). `test-evidence record` summed a
`tests=` attribute whose meaning is reporter-specific, undercounting nested suites — 6 real tests
recorded as 2, worsening with depth. Counts now come from leaf `<testcase>` elements, with an
attribute fallback decided **per suite**. The per-suite granularity is load-bearing: deciding once
per ingest made every summary-only suite contribute zero the moment any other carried a leaf, and
since `failed` drives `tests_are_current`, that was a false *green* — caught in review, not shipped.

**`install-reference-drift`** (#148). A repo can commit an install reference pinned to a fixed
release ref, or with `autoUpdate: false`, and nothing surfaces it — `/prawduct:doctor` Health Check
#1 asserts the contract but is operator-invoked, and nobody health-checks a repo that appears to be
working. An ambient session-start advisory now fires on the drift, cause-agnostic and self-resolving
from the committed file. **The consumer-visible correction is what the drift actually costs:** the
committed reference and the machine-level `known_marketplaces.json` are *decoupled* — a repo pinned
at `v2.1.5` ran a clean v3.2.2 session — so the drift is inert on a configured machine and strands
the *next clone*, which is Health Check #1's own rationale. The PR's original framing (a
CLI-writes-down / repo-re-seeds loop) was falsified by testing and corrected across all seven sites
that carried it, including the operator-facing summary line. Review also closed a hole the two-field
check could not see at all: `enabledPlugins` — governance switched off entirely — now drifts too, and
HC#1 was widened to assert every field the advisory can fire on, so its recommended action can
actually repair what it reports.

**`backlog-burndown` (Chunks 01–04).** Four batches of governance defects, the largest of them in
how the runtime reads its own artifacts. **The migration runbook now verifies before it disposes**
(`#528`, `#530`) — `verify-migration` compared each covered item against the *source markdown*, so
folding a duplicate would have failed a correct migration; both defects were ones prawduct found by
running its own cutover and had fixed only for itself while the fleet still shipped them.
**`regen-views` became advice rather than authority** (`#201`, `#211`, `#224`, `#327`, `#333`):
one always-writing mode, and one bad scope no longer freezes every view. **A review now knows which
plan it is of, and which tree it looked at** (`#206`, `#208`, `#218`, `#288`, `#344`) — five defects
sharing one shape, a question answered from two places with nothing checking the answers agree.
**Untriaged issues stopped being invisible** (`#532`, `#533`, `#209`, `#307`, `#313`): an issue with
no prawduct provenance at all was dropped from `counts` entirely, so the items least likely to be
looked at were the only ones the tooling could not see.

**`critic-burndown` (Chunks 01–03).** Three Critic controls the protocol never had. **A
cross-component message contract is now Goal 1's business, in chunk mode, BLOCKING** (`#97`) — the
filing case was a two-process app whose consumer awaited a terminal signal the producer's success
path never sends; types matched, unit and IPC tests were green because the fixtures synthesized the
very signal the real producer omits, and in production the flow hangs forever. It was caught only
because a human wrote a pointed reviewer prompt, which made detection **prompt-driven rather than
protocol-driven**. **`risk_surfaces:` stopped deciding review depth through a question nobody asked**
(`#163`) — the fallback is silent by design, so a product that declares nothing is never reviewed
*less* and therefore never learns it could be reviewed *more*; `discovery.md` now asks. **A
superseded BLOCKING finding no longer strands its own advice** (`#536`): each `verify-resolutions`
pass anchors to the newest prior review fact, so a blocker left behind on an earlier round is never
named again — while the gate message prescribed exactly that route. The state self-heals through a
clean `cumulative`; the defect was that nothing said so, so this adds a sentence and moves no verdict.

**`critic-death-signals` (Chunk 1).** "The Critic died" reports from consumers traced to **three
compounding false signals, not a dead review.** A field report supplied the timeline: an agent
checked liveness ~8 minutes into a healthy coordinator review, found `.critic-active`'s `pid` dead,
found zero partials, concluded death *inside* the grace window, re-dispatched — doubling review cost
— and the re-dispatch clobbered the first manifest, erasing the only evidence the first review ran.
The reviewers were alive throughout. One fix per signal: the marker's **`pid` field is gone** (it
recorded the short-lived `critic-begin` process, dead within milliseconds of every dispatch, and
nothing ever read it back — it existed only to tell a reader that a healthy review had died);
reviewers now write a **per-role liveness marker** so "zero partials" no longer reads as "nobody
started"; and a re-dispatch **archives rather than clobbers**, so evidence survives.

## OWNER RELEASE GATE — blocking, held at the Phase 1 checkpoint

`build-plan-v3.2.0-golive.md` Chunk 09 items 7 and 8 bind on this release by their own terms
("Both bind on v3.2.3"). Neither is dischargeable by Claude:

1. **Exercise the candidate in sibling repos via `--plugin-dir`** before anything reaches `main`.
   This release changes fleet-visible governance that is invisible to this repo's own suite and
   shows up only when a *consuming* repo loads the candidate plugin.
2. **"GitHub Issues is working great"** — sharpened by owner ruling 2026-07-28 to *functional
   completeness, not performance*: for every supported scenario, no functional requirement is
   broken, unproven against the real API, or silently wrong. `BKL-2K8V` (pick latency) is an NFR and
   explicitly does **not** gate.
3. **Added 2026-08-01 with the `upgrade-discovery` scope — decide whether the migration advisory
   goes fleet-wide with `BKL-8W2M` unbuilt.** The lift itself is settled: owner ruling 2026-07-24,
   and `BKL-7D3V` explicitly scopes out re-litigating it. What is *not* settled is an interaction
   that post-dates that ruling. `BKL-7D3V` recorded the accepted risk as "a repo that will never
   host on GitHub gets an unresolvable `warn` every session… `BKL-8W2M` is what makes the lift
   survivable" — and `BKL-8W2M` (#197) is still open at `stage:requirements`, i.e. unbuilt and
   unscoped. That risk was accepted when the advisory reached only the **agent**. Chunk 01 of this
   scope relays every `warn` to the **person, in conversation, every session**, which is strictly
   worse than what was accepted and is the exact failure the relay's own `info`-exclusion note
   guards against ("a channel that nags gets tuned out, which would cost the `warn` case its
   audience"). Publishing is the irreversible step; merging to `develop` was not. Either land
   `BKL-8W2M` before Phase 2, or record an explicit second acceptance of the amplified version.

**Status: PARTIAL as of 2026-08-02 — items 2 and 3 discharged, item 1 open and BLOCKING.** Nothing
published.

> **Correction 2026-08-02 (later session): "`origin/develop` fully prepped" was not true when
> written.** Phase 1 step 3 was outstanding — eight change-log entries across `backlog-burndown`,
> `critic-burndown` and `critic-death-signals` still carried no `release=` tag, so steps 4–6 had not
> run either and three build plans' `## Status` sections were unflipped. The classification commit
> (`d4d4f40`) had also not been pushed, so `origin/develop` did not even hold the classification.
> **Phase 1 steps 1–11 were complete in the working tree; steps 12 (commit) and 13 (push) remained.**
> *(Both have since run: `e064128`, pushed to `origin/develop` 2026-08-02. **The Phase 1 checkpoint
> is reached.** Stated as a dated fact rather than a present-tense claim, deliberately — this
> document already records three instances of a quoted measurement going stale, and a fourth
> "everything is current now" would be the same defect again. The live test is below.)*
> The claim was written against the intent rather than the tree. This is the same stale-measurement
> failure the blocker-liveness section above documents three instances of, arriving in a new place:
> the fix there was *treat `check-releasability` as the live answer*, and `check-releasability` was
> in fact green at the time — because it grades **classification**, not **tagging**. A green gate is
> evidence about what that gate measures and nothing else.
>
> **Second-order, caught in review (R-1):** the first draft of this very correction said "Phase 1 is
> complete **now**" while steps 12–13 had not run — reproducing the defect it was written to name,
> two sentences after naming it. Scoped to `1–11` above. The reason a reader must care: Phase 2 step
> 15 sets `main`'s tree from **`origin/develop`**, so an unpushed Phase 1 publishes none of this. Do
> not read "Phase 1 complete" as "the checkpoint is reached" until `git status -sb` shows
> `## develop...origin/develop` with no ahead-count and no file lines.

**Item 2 is discharged** on owner statement plus a verified scope argument: private-repo upstream
filing is **W3 and unbuilt**, and no upstream GitHub-issue path ships in v3.2.3 at all (Chunk 06 of
`build-plan-backlog-service.md` is `- [ ]`), so the carve-out names an out-of-scope capability rather
than an unproven supported scenario. Full evidence, including a correction to the post-release
validation plan the carve-out assumed, is at **`.prawduct/operator-verification.md` § VRF-014**.

**Item 3 is discharged 2026-08-02 by explicit second acceptance.** Owner accepted the amplified
delivery — the advisory reaching the *person* every session with `BKL-8W2M` (#197) unbuilt — as a
minor annoyance, with `BKL-8W2M` intended within days. Recorded with its residual risk
(desensitization of the `warn` channel, bounded by shipping `BKL-8W2M`, and to be re-taken rather
than assumed if that slips) at **`.prawduct/operator-verification.md` § VRF-014 item 3**.

**Item 1 alone remains blocking.** Exercise the candidate in sibling repos via `--plugin-dir`, then
record the result in `.prawduct/operator-verification.md` alongside VRF-014 — naming which sibling
repos were exercised and what was checked — and only then run Phase 2. **Phase 2 must not run on
items 2 and 3 alone**: those two were discharged by argument and by decision respectively, and
neither put the candidate plugin in front of a consuming repo. Item 1 is the only gate item that
executes anything.

## Runbook departure — `active_build_plan`: recorded, then withdrawn

**Originally recorded as a departure; reversed 2026-08-02 when its premise expired.** The departure
read: Phase 1 step 11 says set `active_build_plan:` to `null`, not done deliberately, because the
pointer held `artifacts/build-plan-v3.2.0-golive.md` and that plan is not completed by this release
(Chunk 06 ships; Chunks 01, 05, 07, 08, 09 unchecked, with 07 and 08 deferred out of v3.2.0 and never
re-cut). Clearing it would have orphaned a live plan mid-flight. That reasoning was sound when
written and is kept rather than deleted.

**What changed: the pointer moved.** `fix/critic-death-signals` repointed it at
`artifacts/build-plan-critic-death-signals.md`, and that merged to `develop`. This release's
`regen-views` flipped that plan's only chunk to `shipped`, so the pointer now names a **completed**
plan and clearing it orphans nothing. The departure's own stated fix — *"step 11 should be
conditional on the plan having no unchecked chunks left"* — is satisfied, so step 11 was executed
normally. **v3.2.3 takes no departure here.**

**It was deliberately not repointed at the golive plan instead.** That plan does still carry five
unchecked chunks, but nobody is building them, and `project-state.yaml`'s own comment block records
**three** stale-pointer incidents — each one the pointer naming a plan that was not the plan under
review, each producing a wrong verdict (record-lint grading the wrong plan; two Critic mode-inference
misfires). Pointing at a dormant plan to keep the slot non-empty is the shape that caused all three.
`null` is the honest value when no work is in flight; `/prawduct:backlog pick` sets it next.

**The clear switches off two Stop-hook gates for the rest of this release — chosen, not discovered
(Critic R-2).** `develop` names no declared scope, so `resolve_branch_plan` falls back to the now-null
pointer and `_has_active_build_plan_file` returns False; `_has_build_plan_in_state` also returns False,
because this repo's state carries `build_state:` rather than the `build_plan:`/`chunks:` shape that
function scans. From the next session `has_build_plan` is False, which **downgrades the reflection
gate from BLOCKING to advisory and skips Gate 2 (Critic review) entirely** — the guard is
`if has_changes and has_build_plan:`. So the prep commit and the Phase 2 promotion run ungated.

Accepted rather than reversed, for three reasons. **(1)** This is the designed meaning of `null`, and
the alternative — parking the pointer on a dormant plan to keep a gate armed — is precisely the
stale-pointer shape that produced three wrong verdicts already; buying gate coverage by feeding the
gate a false input is not a trade worth making. **(2)** The gate is a safety net for *unreviewed*
work, and the work it would have caught here was reviewed explicitly instead — this section exists
because that review ran. **(3)** Phase 2 authors nothing: it is `git read-tree` plus a push, and its
real protections are the runbook's step 17/18 content-identity and version checks plus the owner
gate, none of which route through the Critic. **What this does cost:** from here to the end of the
release, review coverage is a thing someone has to *choose*, and reflection will not block if it is
skipped. Re-arming is automatic — the next `/prawduct:backlog pick` sets the pointer.

The step-11 debt is therefore **discharged for this release but not fixed in the runbook** — the
conditional is still unwritten, so the next release whose pointer names an in-flight plan will face
the same call. Filed, not fixed here: a runbook edit mid-release is its own change needing its own
review. **A second item joins it:** step 11 hands the rest of the release to an ungated session and
the runbook does not say so. Both belong in the same runbook edit.
