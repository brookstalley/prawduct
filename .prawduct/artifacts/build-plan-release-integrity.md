---
artifact: build-plan
version: 2
scope: release-integrity
depends_on: []
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the internal CLI subcommand surface carries no per-subcommand version → conforms. No chunk adds `--version` to any subcommand"
      - "**Ruling 2026-08-02 (install-reference-is-published): the `stable` tier is exactly `print-install-reference` and `version` — read-only, one value on stdout, exit 0, additive-only, removal requires a major** → **binds Chunk 01 and rules out the obvious fix.** `version` is a published surface, so *refusing to answer* — the shape I proposed to the owner as 'make it refuse rather than guess' — would break the contract by moving it off exit 0 and off one-value-stdout. Chunk 01 therefore keeps stdout and the exit code exactly as they are and carries provenance on **stderr**. The strategic intent (a wrong number must stop looking like a right one) is preserved; the mechanism the owner and I first reached for is not available"
      - "additive-first evolution, tolerant readers; deprecation signalled via stderr notice, never silent → conforms, and it is the precedent Chunk 01 follows: stderr is already this surface's channel for saying something the stdout value cannot"
      - "revisit trigger: *binding a third party to a `--json` shape* → **engaged by Chunk 02.** Giving `version` a machine-readable provenance form is what makes report-bug's stamp trustworthy, and it is exactly the trigger the ruling named. Recorded as a [DECISION] under Chunk 02 rather than taken silently"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft; **a command's failure posture follows what it produces** → conforms, and it settles Chunk 01's shape independently of the api-contract ruling. `version` produces information, not a verdict, so it degrades to a note rather than blocking. Two norms, same answer, different reasons"
      - "*advice fails soft is not advice fails silent — a degraded path must still name its consequence* → binds Chunk 01's stderr text. The note says what is now unreliable (the number just printed may not be the plugin governing this session), not merely that a variable was unset"
      - "local-first governance, no network in the governance runtime → **binds Chunk 03 and selected its design.** The staleness probe compares against the on-disk marketplace snapshot, never a network fetch. This is why the probe is advisory-grade and can only under-report, never over-report"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; Chunk 03 writes only through the existing advisory store"
  - artifact: operational-spec
    dispositions:
      - "**the version bump IS the release mechanism: manifest `version` is the auto-update cache key; an unchanged `version` keeps the cached copy** → **this plan's root cause, stated as a norm.** The norm is written from the forgot-to-bump direction ('a release that forgets the version bump does not ship'). The failure found on 2026-08-04 is its unstated inverse: bumping the key on `develop` at Phase 1 while the content lands on `main` at Phase 2 publishes the key ahead of the tree, and the key never changes again. Chunks 04–05 verify the consumer-visible end state rather than restating the norm"
      - "gitflow: `develop` integrates, `main` is the release surface; promotion is a separate single-parent step → conforms. No chunk changes the promotion model; Chunk 05's workflow triggers on tag push, after promotion, and never performs one"
      - "versioning is conservative — a small feature is a patch bump → conforms; this scope is a patch"
  - artifact: nonfunctional-requirements
    dispositions:
      - "**text emitted into a governed product names no prawduct-internal identifier — plain-language reason only; steady-state, binds unconditionally** → binds Chunk 01's stderr string, Chunk 03's advisory text and Chunk 04's output. No requirement, chunk or backlog id appears in any emitted string"
      - "no probe or gate on the hot path may block or noticeably delay session start → **binds Chunk 03.** The staleness probe reads two small JSON files already on disk and must add no directory walk and no network call"
      - "state-file growth past threshold is an advisory warning, never a hard block → inapplicable; no chunk changes state-file growth behaviour"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms, and Chunk 03 is a fresh instance: the marketplace snapshot is third-party-writable content read only as a version string to compare, never as anything executable or directive"
      - "**a destructive or irreversible operation requires explicit owner approval at the OPERATION level, naming blast radius** → **binds Chunk 05 and is its open question.** Publishing a GitHub Release notifies watchers and is not cleanly retractable. A workflow firing on tag push performs that act with no human present at the moment of publish. Recorded as a [DECISION] needing an owner ruling under Chunk 05 — not resolved by this plan"
      - "a governed product's content never leaves its own repository and owner → conforms. Chunk 05's workflow runs inside this repo and publishes only this repo's own CHANGELOG; Chunk 03 sends nothing outward"
---

# Build plan — release integrity

## Why this exists

Investigating "the v3.2.3 release was weird" (2026-08-04) found the release itself clean —
`v3.2.3` → `c479709`, all four version files agreeing at every 3.2.x tag — and three
independent defects around it. They share one cause: **every check in the release process is
expressed as a git command run by the person doing the release, and nothing verifies what an
installed consumer actually receives.** The one channel that reports back from consumers — the
version stamped into upstream bug reports — runs on the unsound path, so the loop that would
have reported any of this is disabled by the same defect it would report.

Already delivered outside these chunks (commit `2968d66`, and the v3.2.3 Release published
2026-08-04): the runbook publish step and the two Done-when checks.

## Requirements Confidence

**Medium.** The problem, the success criteria and the scope are each statable in a sentence, and
all three defects were reproduced rather than inferred. Two mechanisms the fix depends on are
*asserted in project records and contradicted by measurement*, and until they are settled the
shape of Chunks 01–02 is not fully determined.

**What would raise it:** Chunk 01's first step — a direct measurement of where
`CLAUDE_PLUGIN_ROOT` and `CLAUDE_SKILL_DIR` actually substitute. That is a ten-minute probe, and
it is deliberately the first thing this plan does.

## Measurement — Chunk 01 step 1, run 2026-08-04

Run before any edit, because two records assert what it measures.

**Result.** In the Bash tool env, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_SKILL_DIR` and
`CLAUDE_PROJECT_DIR` are **all absent** — the env carries ten `CLAUDE_*` variables and none of
them is a plugin, skill or project path. *A contradicting result would have printed a path for
`CLAUDE_PLUGIN_ROOT`; it printed empty, and the variable is not in the environment at all.*

**So there are three substitution mechanisms, not one, and only two of them pin anything:**

| Caller | Mechanism | Pinned? |
|---|---|---|
| Hooks | Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` into the hook command (`hooks/hooks.json`) | yes |
| Skill prose | Claude Code expands `${CLAUDE_SKILL_DIR}` **into the prose at load time** — observed twice this session, e.g. the methodology skill rendered as an absolute `…/plugin/skills/methodology/../../methodology/building.md` | yes |
| Bare `prawduct-hook` in a Bash command | none — PATH decides, and `_plugin_root()` falls back to the script's own directory | **no** |

**Both records this plan flagged are wrong, in different ways.** `_plugin_root()`'s docstring
claims the variable reaches the Bash tool env: false. `learnings-detail.md` says it substitutes in
"bash/subprocess env": true only of hook-spawned subprocesses, which is a much narrower claim than
it reads as. And `${CLAUDE_SKILL_DIR}` is **not** an environment variable — it is a prose-time
expansion, so Chunk 02's route works, but not for the reason the plan assumed.

**Refinement to the diagnosis, recorded against my own earlier framing.** Claude Code appends the
*installed* plugin's versioned `bin/` to PATH (measured: `…/cache/claude-plugins-official/swift-lsp/1.0.0/bin`
is on PATH, and no shell profile puts it there). So a consumer's bare `prawduct-hook` normally
resolves to the same tree the hooks use — which makes plain PATH roulette a *less* likely
explanation for the "hook says 3.2.1, plugin says 3.2.3" report than I first said. The likelier
single cause is the cache-key pin (Chunk 03's target): the install stays at 3.2.1 while the
marketplace advertises 3.2.3. **This raises Chunk 03's priority above Chunks 01–02.** The
unpinned-invocation defect is still real and still measured — it just probably is not what bit
that user.

## Open assumptions

- `[ASSUMPTION: CLAUDE_PLUGIN_ROOT is absent from the Bash tool env | HIGH impact | user can correct]`
  Measured absent in this session (`env | grep -c` → 0), and `_plugin_root`'s own docstring plus
  `learnings-detail.md` both assert it *is* present in "bash/subprocess env". One of the two is
  wrong. This is the premise of the whole plan, and the learnings corpus already warns about this
  exact shape — *five mutually-consistent records, one implementation, no overlap* — written about
  this very function. Chunk 01 settles it by measurement before anything is built on it.
- `[ASSUMPTION: skill prose can reach the plugin root via ${CLAUDE_SKILL_DIR}/../../ | HIGH impact | user can correct]`
  `learnings-detail.md` states `${CLAUDE_PLUGIN_ROOT}` does **not** substitute in skill prose and
  that `${CLAUDE_SKILL_DIR}/../../` is the established route. **This invalidates the fix I
  described to the owner** ("route the 8 skills through `${CLAUDE_PLUGIN_ROOT}`"). Chunk 02 is
  planned on the `CLAUDE_SKILL_DIR` route instead, and verifies it before editing eight files.
- `[ASSUMPTION: the marketplace snapshot is a usable staleness comparator | MED impact | user can defer]`
  A github-source marketplace is a snapshot directory, not a git clone (`.gcs-sha`, no `.git`) —
  verified — and carries the plugin manifest, so the comparison needs no network. But its own
  freshness is Claude Code's to control: a stale snapshot makes the probe say nothing rather than
  say something wrong. Under-reporting is the acceptable direction; it is still a real ceiling on
  what Chunk 03 can promise.
- ~~`[ASSUMPTION: publishing a Release on tag push is acceptable automation]`~~ **Resolved by owner
  ruling 2026-08-04: auto-verify, manual publish.** Chunk 05 builds the verification half only.
  The security-model norm is satisfied without an exception being needed — no irreversible
  outward-facing act sits on a trigger.

## Verification strategy

Tests are necessary and not sufficient here: two of the three defects were invisible to a green
suite because they live in *how the process is invoked*, not in what a function returns. So each
chunk carries a real-invocation check alongside its tests — and per the standing learnings rule,
framework `bin/`/`lib/` changes are exercised with `python3 plugin/bin/prawduct-hook` from the
worktree, never the PATH-resolved `prawduct-hook`, which is a different checkout. That rule is
itself evidence for this plan: the hazard is known well enough to have been written down.

For every test added, name the change that would turn it red. The version work is especially
exposed: a matrix that varies only the environment variable cannot discriminate the two
implementations it exists to distinguish (the corpus records exactly that miss on this function).
Chunk 01's matrix varies **both** the env var and the script's own location.

---

## Chunk 01 — `version` tells you when it cannot pin

**Type:** code · **Critic mode:** final *(architectural keystone: Chunks 02–04 all consume this
resolution contract; its coherence matters before they build on it)*

**Deliverables**
- A measurement, recorded in the plan, of where `CLAUDE_PLUGIN_ROOT` and `CLAUDE_SKILL_DIR`
  actually substitute — hook command, Bash tool env, skill prose. This lands before any edit.
- `_plugin_root()` distinguishes *pinned* (env-supplied) from *inferred* (script-relative)
  resolution instead of collapsing both into a bare string.
- `prawduct-hook version` keeps **stdout and exit code exactly as they are** — one bare semver,
  exit 0 — and emits a plain-language note on **stderr** when the version is inferred rather than
  pinned, naming the consequence.
- The `_plugin_root()` docstring's claim about the Bash tool env is corrected to match the
  measurement, whichever way it falls.

**Done when**
1. The measurement is recorded, including what a contradicting result would have looked like.
2. Tests vary env var **and** script location independently; each new test names the change that
   would turn it red.
3. Stdout is byte-identical to today's for the pinned case — the published-surface contract.
4. `python3 plugin/bin/prawduct-hook version` exercised from the worktree.
5. `/prawduct:critic` passes with no unresolved blocking findings.

## Chunk 02 — the skills stop asking PATH which prawduct they are governed by

**Type:** code

**Surfaces** (8 skills invoke bare `prawduct-hook`): `critic`, `pr`, `advisory`, `doctor`,
`backlog`, `onboard`, `migrate`, `repo-disable` — each with prose *and* an `allowed-tools`
pattern, so the count of files to touch is 8 and the count of edits is at least 16.

**Deliverables**
- Skill prose invokes a pinned path via the route Chunk 01 measured; `allowed-tools` patterns
  updated to permit that form.
- `report-bug` stamps a version obtained through the pinned route.
- `[DECISION: give `version` a machine-readable provenance form | the api-contract ruling's own
  revisit trigger is "binding a third party to a `--json` shape", and report-bug is that third
  party | user can veto — the alternative is report-bug parsing stderr, which is worse]`

**Done when**
1. No skill invokes a PATH-resolved `prawduct-hook`.
2. A test pins the invocation form across all 8 skills, so a ninth skill cannot regress silently.
3. `/prawduct:critic` passes.

## Chunk 03 — a repo running a stale plugin says so

**Type:** code

> **Design corrected 2026-08-04 before any code, by reading the precedent.**
> The plan originally put the whole check in an advisory probe reading the marketplace snapshot
> under `~/.claude/plugins/`. **That violates the runtime boundary**: no probe reads machine-level
> state, verified by absence — `expanduser` and `Path.home()` appear nowhere in
> `plugin/lib/*_probes.py`, and the two `~/.claude` hits in `install_reference_probes.py` are both
> prose. That module is the closest precedent and it documents *declining this exact read*,
> routing the machine-level half to `/prawduct:doctor`, "which is model-side and can read the
> machine-level file." The two halves are complementary checks, not two ends of one loop — and
> this chunk copies that structure rather than breaking the boundary it established.

**The split, and what each half can honestly claim**

- **Ambient half — advisory probe, project-dir only.** Fires on *version regression*: the running
  plugin's version is **lower** than `.prawduct/.prawduct-version`, the marker the banner already
  maintains in this repo. An install that goes backwards is the cache-pin symptom, and both inputs
  are already inside the boundary — the plugin's own manifest and the repo's own marker.
- **Authoritative half — `/prawduct:doctor` health check, model-side.** Compares the running
  version against the marketplace snapshot's manifest. This is the half that answers "you are
  behind," and it is the half that must not live in a probe.

**The limitation, stated rather than discovered later.** The ambient half cannot see a repo that
has been stale since *before* it ever saw a newer version — which is the documented discodon shape
(pinned at 3.0.4, never saw 3.1.0; its marker reads 3.0.4 too). That case is only reachable by the
doctor half, and therefore only when someone runs doctor. **This does not fully close the loop, and
the plan should not claim it does.**

> **Sequencing decision 2026-08-04 — the probe half is deferred, and this is not a descope.**
> `feat/advisory-actionability` is in flight and rewrites the probe-facing contract: it adds
> `owner_action` and `prerequisite_of` to `AdvisoryCandidate` and updates **all seven** probe
> modules to populate them (358 insertions / 248 deletions across 9 files). A probe authored here
> today would ship without `owner_action` — the exact field that branch exists to require, and one
> its tests pin — making it the only non-conforming probe in the tree the moment those branches
> meet, plus a near-certain conflict in `probe_families.register_all()`.
> **So: build the doctor half now, and the probe half on top of the new contract once
> advisory-actionability reaches `develop`.** Chunks 04 and 05 touch no advisory code and are
> unblocked either way.

**Deliverables — now**
- A new `/prawduct:doctor` health check for the behind-latest comparison (model-side, so it may
  read the machine-level marketplace snapshot; this is the half that answers "you are behind").
- Health-check text carries the consequence in plain language and no internal ids.

**Deliverables — after `feat/advisory-actionability` lands on `develop`**
- New `plugin/lib/staleness_probes.py`, registered via the established lazy-import pattern;
  regression check only; no machine-level read; **written against the `owner_action` /
  `prerequisite_of` contract**, not retrofitted onto it.

**Done when**
1. The probe reads nothing outside the project dir and the plugin root — asserted by a test, not
   by inspection, so a later edit cannot quietly reintroduce the read.
2. Probe tests cover: regression, equal, ahead, absent marker, malformed marker.
3. At least one test reads a **real** artifact rather than only a hand-written fixture.
4. Verified silent against this repo, *and* confirmed this repo is genuinely out of the target
   state — not that the probe was narrowed until quiet.
5. The doctor half is exercised against this machine's install, which is currently stale
   (3.2.3 recorded at the prep commit) and is therefore a live positive case.
6. `/prawduct:critic` passes.

## Chunk 04 — `check-released`, the mirror of `check-releasability`

**Type:** code

> **The GitHub Release check is a network call, and `architecture.md` § Direction says the
> governance runtime takes none.** Not a blocker, but it must be decided rather than typed.
> `[DECISION: `check-released` is an operator/CI command, not a session gate — it never runs on
> the hot path, never blocks a session, and carries no session governance verdict, so the
> local-first norm's subject does not cover it. But the norm is not waved away either: the
> **local** checks (version files, tag on `main`, install resolution) run with no network and
> fail closed, and the Release check is a **separately reported third state** — verified /
> failed / unverifiable-because-`gh`-is-absent — so a machine without `gh` gets a usable answer
> instead of a false red. In CI `gh` is always present, which is where the check is authoritative
> | user can veto: the alternative is putting the Release check behind an explicit `--remote`
> flag, which is more orthodox but makes the CI invocation the non-default one]`

**Deliverables**
- `prawduct-hook check-released vX.Y.Z`: version files agree with the tag, tag is on `main`,
  a GitHub Release exists, the local install resolves to the released tree.
- Body in `lib/`, thin `cmd_` wrapper in `bin/prawduct-hook` — the established shape for every
  neighbouring subcommand, and what the precedent's tests import.
- Explicit arg scan; unknown tokens are usage errors (exit 2), never ignored — copied from
  `check_releasability`, whose comment records why the `in argv` shortcut is wrong here.
- Dispatch arm, usage string, and the human-readable output path — not only `--json`.

**Done when**
1. `tests/test_release_readiness.py` cases are **ported first**, per the standing rule that a new
   subcommand modelled on a precedent copies the precedent's test file before adding its own.
2. Both the human formatter and `--json` are tested.
3. Run against `v3.2.3` — it must pass now that the Release exists, and must have failed before it.
4. `/prawduct:critic` passes.

## Chunk 05 — CI: run the suite, and verify what shipped

**Type:** code

There is no CI in this repo at all — no `.github/` of any kind — so `tests/` runs only when
someone remembers. That gap is independent of releases and is the larger half of this chunk.

**Deliverables**
- A workflow running the suite on push and PR.
- A tag-push workflow running Chunk 04's `check-released`.
- `[DECISION: CI verifies the Release; it never publishes one | **owner ruling, 2026-08-04.**
  Publishing notifies watchers and is not cleanly retractable, and `security-model.md` § Direction
  requires explicit owner approval at the operation level for such an act — a tag-push trigger has
  no human at the moment of publish. A red build on a forgotten publish step buys most of the
  benefit at none of that cost | ruled, not assumed]`
- **No publish step is built.** A forgotten publish surfaces as a failing `check-released`, which
  is the intended mechanism. The pruned-release hazard — its CHANGELOG section describes the whole
  cut, so publishing verbatim would announce withheld work — is therefore moot in CI and stays a
  human-read warning in `runbooks/promote-a-pruned-release.md`.

**Done when**
1. The suite runs green in CI on a real push.
2. `check-released` runs on tag push and is red for a deliberately broken input.
3. The workflow contains no publish step, and a reader can tell that is deliberate.
4. `/prawduct:critic` passes.

---

## Governance checkpoints

- **After Chunk 01** — architecture validation. If the measurement contradicts the plan's premise,
  stop and re-plan rather than proceeding: Chunks 02–04 all rest on it.
- **After Chunk 03** — midpoint; re-read the whole trajectory against the norms above.
- **Before Chunk 05** — the security-model decision must be settled, not assumed.
