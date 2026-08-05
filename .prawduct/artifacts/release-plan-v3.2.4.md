# Release plan — v3.2.4

**Cut from:** **whole-develop at Phase 2** — the tip as of the promotion, not a pinned commit.
*(`K withheld = 0` selects the whole-develop shape, which makes the tip the answer. Stated
relationally rather than pinned to a sha, because v3.2.3's plan recorded five instances of a
measurement that was true when typed and false when read.)*
**Previous release:** v3.2.3 (`c479709`, tagged 2026-08-02)

## Version decision

**Patch bump, 3.2.3 → 3.2.4.** Owner-directed ("ship 3.2.4"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded because two scopes are `type=feature` and a minor is therefore arguable.**
`release-integrity` adds `prawduct-hook check-released` — a genuinely new subcommand that ships in
every product's CLI — and this repo's first CI. It stays a patch because the new capability is
**one operator-invoked subcommand that gates nothing**: no persisted format changes, no gate
semantics change, and nothing an adopter depends on changes shape. The observed-precedent minor tier
(a substantial new capability, or a subsystem going live) is not met by a single verification
command that a consumer must choose to run.

**The one behaviour change that is not merely additive is called out rather than buried:**
`silent-gates` Chunk 01 changes what tree a `verify-resolutions` review anchors to when the prior
review saw a dirty tree. That is a **correctness repair** to an interval that was inverted, not a
semantic change — it alters no fact-schema field and changes nothing on a clean tree — so it does
not reach the major tier under the observed precedent ("a break in gate semantics or persisted state
formats"). Recorded because it is the closest thing in this release to one.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| silent-gates | ships | |
| release-integrity | ships | |
| review-loop-carriers | ships | |
| release-verification-false-reds | ships | |

`K withheld = 0` → **whole-develop promotion** (runbook Phase 2 steps 14–20), not the pruned path.

### The set was derived, not recalled

Measured 2026-08-04 on `release/v3.2.4` @ `522e05a` (tree-identical to `origin/develop`):

- **17 statusless change-log entries, all four scopes above the step-2 boundary** (line 1038, the
  topmost `release=` tag line, `v3.2.3`). The whole-file scope enumeration and the
  boundary-restricted one return the same 17 — so unlike v3.2.3, **no entry sits below the boundary**
  and no entry is unscoped. There is no by-hand tagging of gate-invisible entries this release.
- **The code test agrees with the position test.** All four scopes merged to `develop` *after* the
  v3.2.3 promotion commit (`c479709`, 2026-08-02 21:03): `silent-gates` PR #572 on 2026-08-03,
  `release-integrity` PR #582, `review-loop-carriers` PR #588 and `release-verification-false-reds`
  PR #592 on 2026-08-04. Spot-checked by content rather than by date alone —
  `git show v3.2.3:plugin/bin/prawduct-hook` contains `check-released` **0** times against **3**
  here, so `release-integrity`'s code is absent from the previous release's tree.

### Blocker liveness — vacuous by construction, not skipped

`check-releasability` reads blocker liveness **only for rows that name a blocker**, and no row here
does. Every scope ships, so there is no withholding decision whose premise could have expired and
nothing for the frozen markdown backlog to be consulted about. The `cannot-verify-blockers:` refusal
this cut-over repo would otherwise draw therefore never fires.

Recorded rather than left silent, because "there was nothing to check" and "I did not check" look
identical in hindsight. **The first release that withholds a scope is where `cannot-verify-blockers`
actually bites.**

### No owner release gate carries into this release

v3.2.3 was held behind `build-plan-v3.2.0-golive.md` Chunk 09 items 7 and 8, which bind on v3.2.3
**by their own terms** and were discharged 2026-08-02. Nothing re-binds them here, and no scope in
this release names a gating blocker.

**One fleet-visibility note stands anyway, and it is not a gate.** `silent-gates` changes governance
behaviour that this repo's own suite cannot observe — the norm probes' emphasis tolerance and
table-homing fire only in a *consuming* repo, and doctor Health Check #14 exists specifically for
repos onboarded before the template fix. That is the class item 1 of the v3.2.3 gate existed to
catch. It is recorded as a known limit on what green CI proves here, not converted into a blocker.

## Consumer-facing headline

> The Critic review loop now tells you when it is over — and the governance checks that had gone
> silently dark now say so instead.

## What ships

**`silent-gates` (Chunks 01–06) — the largest scope, and the one whose name is the theme.** Six
batches of *a check that reported nothing while doing nothing*.

- **The wrong binary was running your reviews** (`#227`, Chunk 04). Inside a framework checkout a
  bare `prawduct-hook` on `$PATH` resolves to whatever plugin the environment installed — in the
  observed instance, a sibling worktree. `critic-begin` ran the foreign binary and wrote **no**
  kernel-v3 manifest: no error, no manifest, and the `SubagentStop` `critic-consolidate` no-opped the
  same way, leaving reviews unpersisted. The guard keys on **binary identity**, not version equality
  — a deliberate departure from what `#227` prescribed, because a checkout is routinely ahead of its
  own manifest between releases and version comparison would have passed the very skew it was
  written to catch. **This is the release where that fix goes live:** a guard inside the binary
  cannot protect an invocation of a binary that predates it.
- **A `## Direction` heading is not a norm registry, and its absence is not health** (`#567`,
  Chunk 02). Field-reported from an unrelated product's onboarding. A heading with nothing under it
  certified as a ratified registry, so doctor check #10 would have reported findings against a
  *roadmap* indefinitely; and the absence of a heading permanently silenced the norm-health sweep for
  a product that homes its norms in the preferences Enforcement table — a legitimate homing that got
  no reminder at all, ever, with no signal it was missing.
- **If you write `**Why:**` rather than `Why:`, four norm signals were silently dark** (`#568`,
  `#569`, Chunk 05). All five emphasis forms of `Why` / `Status` / `Rulings` / `Retroactivity` now
  count. The same pass settled what a Direction norm entry *is*, mechanically — **field-bearing**,
  not Why-bearing, because a Why-only definition makes doctor Health Check #10 vacuous by
  construction: the whyless entries it exists to flag would stop being entries at all. A failing
  test forced that correction and the fixture was **not** edited to accommodate the code.
- **The template fix that never reached the installed base** (`#570`, Chunk 06). `#567`'s fix
  shipped the norm-index template **empty**, and `init_product` / `core.write_template` copy a
  template only into a destination that does not exist — so **every already-onboarded repo** still
  carries the two illustrative rows, still reads as having a ratified norm registry, and is still
  nudged about a sweep it owes nothing to. `prawduct-hook norm-index-scaffold` detects them and
  doctor **Health Check #14** offers the repair — reported, never applied unasked. Detection is
  exact-match against the rows prawduct actually shipped, so a scaffold row you have since edited is
  yours and is left alone.
- **Two runtime assumptions that held only on the machine they were written on** (`#562`, `#154`,
  Chunk 03). `core.atomic_write_text` wrote at the *locale* encoding while every reader opens utf-8
  — latent only because the early callers write ASCII JSON, and `.session-handoff.md` is not one of
  those and routinely carries em-dashes. And `audit_learnings_cmd.run_sentinel` spawned a bare
  `python3`, which under any virtualenv is a different interpreter — so every sentinel reported
  failing, and the audit decides which learnings are *structurally enforced*, meaning a false-failing
  sentinel argues for retiring a rule that is in fact still enforced. That was live in this repo's
  own test environment.
- **A `verify-resolutions` review could anchor to a tree in which none of the fixes exist**
  (`#554`, Chunk 01). "Has a commit landed since the prior review?" was answered by tree inequality
  alone, which has two answers that look identical and mean opposite things — and the second (the
  prior review vouched for a **dirty** tree) is the ordinary shape of a `chunk`-mode review:
  **136 of 402 review facts in one clone's store, roughly a third.** Read as a committed delta the
  interval inverts, and the resolution facts — which lift BLOCKING findings — persist against the
  pre-fix tree. Unsound, not merely noisy. Changes behaviour only when the tree is dirty; no
  fact-schema field is added, removed or retyped.

**`review-loop-carriers` (Chunks 01–03) — the review that generates its own next round.** v3.2.3
already said the right thing about when a review is over. A consuming repo **on that exact version**
then ran **ten Critic rounds on one branch**, rounds five onward spent fixing warnings that gated
nothing — because every carrier was a *pull* carrier: the branch had no build plan, so the builder
never entered the cycle that would have made it read either file, and the one runtime carrier printed
in seven reviewer contexts and zero builder contexts. Three carriers now **push**:
`.critic-findings.json` gains a code-computed `next_action`; `critic-consolidate` prints it as
`NEXT-ACTION:` and both protocol files order the reviewer to relay it verbatim as their last line
(which is what closes the single-pass hole — the reviewer is the one running the command); and the
cumulative gate now **diagnoses fix churn**, naming `disposition` rather than offering a generic
"review again". The discriminator is what moved the tree, never a round counter. Alongside:
`verify-resolutions` now rates **new** findings BLOCKING-only, with a five-class carve-out that says
which half is a citation and which half is an **escalation** — the chunk's own review proved the
original "already BLOCKING-rated" claim false for two of the five, and a safety argument resting on a
false claim is not a safety argument. And a finding whose only subject is an inert count is capped at
NOTE, with `numeric counts` removed from the Goal 1 target list so the protocol stops *asking* for
the finding it demotes.

**`release-integrity` (Chunks 04–05) — the check that would have been red for every release this
repo ever cut.** `prawduct-hook check-released vX.Y.Z` verifies a release **from the outside**:
version files agree at the tag's own tree, the tag is contained in `origin/main`, and a GitHub
Release exists. Every previous release check was a git command run by the person doing the release,
so nothing ever asked what a *consumer* receives — and the Releases page was empty for every one of
them, which is the defect users reported as "no tag on GitHub". **Three outcomes, not two:** exit 0
verified, 1 failed, **3 nothing failed but a check could not run**. Folding 3 into *passed* is how it
first shipped in review, and it would have gone green over an empty Releases page. Alongside: this
repository had no `.github/` of any kind, and now runs its suite on every push and PR across a 3.10
and 3.14 matrix, plus a tag-triggered `verify-release` job. **CI verifies a release; it never
publishes one** — an owner ruling, pinned by a guard test, because publishing notifies watchers, is
not cleanly retractable, and a tag-push trigger has no human present when it fires.

**`release-verification-false-reds` (Chunks 01–02) — and this one is aimed at *your* product, not
ours.** `check-released` shipped with prawduct's own layout hard-coded, so a product using
setuptools-scm, or carrying a tooling-only `pyproject.toml`, was graded against a layout it never
claimed and told `not-released`. Products now declare **`release_version_files:`** — path, format,
and the **key path** where the version lives. **The posture splits on provenance, and that split is
the requirement:** a *declared* file that is absent or missing its key is a real defect and reaches
`failed`; undeclared, the built-in tuple is a **guess** and may only reach `ok` or `unverifiable`,
never `failed`. The declaration is read from **the tag's tree**, so reorganising a layout cannot
retroactively fail an old release. Two further false reds closed: `git rev-parse` exits 128 for both
"no such tag" and "not a git repository", and every non-zero was read as the first — so running the
check from any non-repo directory produced a confident `not-released` about a release it never
assessed. TOML reading now delegates to stdlib `tomllib` rather than growing a hand-rolled parser
(LNG-5W8R's own interim rule), which costs an honest `unverifiable` on Python 3.10 and **deletes**
the parser that norm names.

## Runbook departures — two, both recorded

### 1. Phase 1 was prepped on `release/v3.2.4`, not on `develop`

**The runbook's prerequisite is "you're on `develop` with nothing uncommitted and nothing
unpushed."** `develop` is checked out in a **sibling worktree** (`/Users/brookstalley/source/wt-prawduct-backlog`),
and git refuses to check out or force-update a branch held by another worktree. The session running
this release is scoped to its own worktree and must not mutate another's.

**Taken instead:** `git switch -c release/v3.2.4 origin/develop` — verified tree-identical to
`origin/develop` before any edit — with the prep commit delivered by `git push origin HEAD:develop`.
That produces byte-identically the commit on `origin/develop` that the literal steps would have, and
it satisfies the *substance* of the prerequisite (the tree being prepped is exactly `origin/develop`,
and nothing is left local). Phase 2 is unaffected: `main` is checked out in no worktree, so steps
14–20 run literally.

**What this does not fix:** the sibling worktree's local `develop` ref stays behind. That is its own
session's to update, and it has no bearing on what ships — Phase 2 step 15 reads `origin/develop`.

### 2. Steps 20 and 21 are in a race the runbook does not mention — this release won it by ~9 seconds

Not a departure taken, a defect **found**.

`verify-release.yml` fires on the tag push (step 20). `check-released` asks three questions, and one
of them is *does a GitHub Release exist* — which step **21** is what creates. So the automatic run is
dispatched **before** the fact it checks becomes true, and whether it passes depends on whether the
operator publishes the Release faster than a GitHub runner can spin up and reach the check step.

> ⚠️ **This section asserted the run was red "by construction" and "**must** be red". That was
> written before the promotion and is FALSE — measured, not softened.** The tag push dispatched the
> run at **01:43:48Z**; the Release went live at **01:43:59Z**; the run concluded **success** at
> **01:44:08Z**. Runner spin-up, `actions/checkout` at `fetch-depth: 0` and the `origin/main` fetch
> consumed the first ~11 seconds of a 20-second job, so `check-released` ran *after* the Release
> existed and saw all three checks green. The hazard is real and the conclusion inverted: it is a
> **race**, not a guarantee, which is strictly worse to leave unfixed than a deterministic failure
> would be — a deterministic red gets fixed, and a race that usually passes gets learned as noise.
> *(Recorded rather than quietly edited: this repo's rule is that correcting a false claim is
> authoring a new claim, and a release document that silently swaps one confident assertion for its
> opposite teaches nobody why the first one was wrong. The first version reasoned from step ordering
> alone and never asked how long a runner takes to reach the step.)*

**What actually protects it, and it should not have to:** publishing the Release immediately after
pushing the tag. Pause between steps 20 and 21 to read output, answer a question, or check a run —
all of which the runbook's own prose invites — and the window closes. The release process must not
depend on operator typing speed.

**Filed rather than fixed here.** A runbook edit is its own change needing its own review, which is
this repo's standing precedent. It belongs with **`#581`**, and this release supplies two things
that item was waiting on:

1. **The workflow has now passed once against a real tag**, which is `#581`'s stated purpose — so its
   acceptance criterion (delete the `First run only:` paragraph from the runbook's `Done when`) is
   now dischargeable, and leaving that paragraph in place makes the runbook *wrong* for the next
   release: it tells the operator to read a red run as possibly a workflow defect, which is now
   ruled out.
2. **The race above**, which is the more valuable of the two and was not previously known.

## Verification — measured at the promotion, 2026-08-05

`./plugin/bin/prawduct-hook check-released v3.2.4` → **exit 0**, `released: v3.2.4 — 3 of 3
verified`: three version files agreeing at the tag's tree, `tag-on-main: 889127816`, and the Release
URL. **This is the first release in this repo's history for which that command can pass** — it fails
for every earlier tag, because the Releases page was empty for all of them.

Four CI runs green: `verify-release` on the tag, `tests` on the tag, `tests` on `main` (the first
time either has ever run on the release surface — `.github/` reaches `main` in this promotion), and
`tests` on `develop` for the prep commit. Local suite before the prep commit: **3627 passed, 7
skipped**.

**One `Done when` item does NOT pass, and it is a pre-existing condition rather than this release's
doing.** The installed-plugin sha (`ddb6dd1`) is **v3.2.3's prep commit**, not v3.2.4 and not even
v3.2.3's released tree — so this machine's `directory:` marketplace has been serving v3.2.3's *prep*
tree since 2026-08-01, exactly the symptom the runbook's "If this doesn't work" section describes,
one release late. It self-heals here rather than needing the unverified cache-deletion remedy,
because the failure was a cache key that never changed and this release **does** change it
(`3.2.3` → `3.2.4`): the next session start re-resolves. Worth stating plainly for the next
reader — the runbook frames this as a Phase 1–2 *gap* symptom, but the underlying exposure is
permanent for a `directory:` marketplace, since `develop` outruns the version key for the whole
inter-release window. (Inert for the correction commit below: it touches only `.prawduct/artifacts/`,
and the cache resolves `plugin/`.)

## What is deliberately NOT hand-edited

`artifacts/build-plan-release-verification-false-reds.md` is retained on `develop` with both `Status`
checkboxes unchecked, and both of its change-log entries are statusless. **That is the
release-pending state under gitflow, not drift.** Phase 1 step 5's `regen-views` flips every
scope-tagged plan's Status in one pass from the `release=` tags this release stamps. Do not hand-flip
a checkbox and do not delete a plan before the promotion — that would leave the regeneration nothing
to regenerate.

`active_build_plan:` is already `null` (cleared deliberately in PR #592), so Phase 1 step 11 is a
no-op here. **The consequence v3.2.3 recorded still applies and is chosen again:** a null pointer
makes `has_build_plan` False, which downgrades the Stop hook's reflection gate to advisory and skips
the Critic gate entirely, so the prep commit and the promotion run **ungated**. Accepted for the same
three reasons — it is the designed meaning of `null`, the alternative (parking the pointer on a
dormant plan) is the stale-pointer shape that has produced three wrong verdicts, and Phase 2 authors
nothing: it is `git read-tree` plus a push, protected by the step 17/18 content-identity and version
checks rather than by review.
