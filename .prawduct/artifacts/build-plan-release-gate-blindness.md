---
artifact: build-plan
version: 2
scope: release-gate-blindness
branch: fix/release-gate-blindness
depends_on:
  - artifact: operational-spec
  - artifact: api-contract
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → LOAD-BEARING, and it is what partitions this plan. Chunk 01 produces a releasability VERDICT over work that cannot be classified, so it blocks (exit 1). Chunks 02 and 03's coverage checks merely INFORM — their subject is prose, matched fuzzily — so they warn and never touch the exit code. The split is the norm applied, not a preference."
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no chunk touches a reviewer write path"
      - "local-first: no network, no daemon, no third-party runtime dependency → conforms; file reads only"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state → conforms; every chunk READS and reports, and none writes a governed file"
      - "prawduct is Python but never Python-specific → conforms; the subjects are a change log, a markdown digest and a version string, none language-bound"
      - "prawduct guides and reviews; it never implements → conforms"
      - "goals and verification bind; prescribed method is advice → engaged: Chunk 03's original prescribed method (`wire the headline into release-prep`) names a command that does not exist, and is replaced rather than conformed to — see the chunk's Description"
      - "every fact has one home → LOAD-BEARING for Chunk 02: 'which scopes are release-pending' already has a home in `release_pending_scopes`, so the coverage check consumes it rather than re-deriving the pending set from the change log"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented and consistent scheme → LOAD-BEARING. Chunk 01 refuses with the channel's existing blocking value (1, the same `no-release-plan` uses), NOT a new code and NOT a generic error. Exit 3 is deliberately NOT used: 3 means the gate's SUBJECT could not be read, and here the subject is read fine — it is the WORK that is unclassifiable."
      - "additive-first evolution: existing flag names, exit-code meanings and --json keys are never repurposed → conforms. No exit-code meaning changes: 1 already means 'not releasable'. Chunk 01 adds a new CONDITION that reaches it. Any new `--json` keys are additive."
      - "whole-surface semantic versioning; the internal CLI subcommand surface carries no per-subcommand version → inapplicable; no new subcommand is added"
  - artifact: nonfunctional-requirements
    dispositions:
      - "adding a control names the yield it expects AND emits that yield observably → LOAD-BEARING for all three chunks. Each new check prints what it found (counts, named entries, named scopes) rather than only its verdict, so it can later be retired on evidence instead of defended on principle. Chunk 01's `entries scanned / scopes enumerated / unclassifiable` triple is that emission."
      - "proportionality ratchets both ways → engaged: Chunk 02's check is advisory precisely because its matching is fuzzy; if it proves noisy it is removable on its own emitted evidence"
      - "review wall-clock is a P0 constraint → conforms; three chunks, one Critic pass each, no new review surface"
      - "state-file growth is advisory, never a hard block → inapplicable"
last_validated: 2026-08-27
---

## Requirements Confidence

**Level:** Medium

**Why:** The defect in each of the three items is confirmed against the code, not inferred, and two
of the three were *measured live* on this repo this session. What keeps it off High is Chunk 03:
its backlog item prescribes wiring into a `release-prep` command that **does not exist**, so its
fix shape had to be re-derived rather than read off the item.

Confirmed this session, by reading and running rather than by recall:

- **#168** — the scope guard that drops a scopeless entry is live at `release_readiness.py:67`
  and `:91`; the `if not pending:` branch at `:392` *documents* the blindness in a comment and
  still returns 0. The asymmetry the item names is present exactly as described.
- **#168's stated blocker is not merely downgraded — it is gone twice over.** The item says the fix
  is two-sided because tagging a scopeless entry breaks fail-closed `regen-views`. (a)
  `_plan_coverage_warnings` now reports rather than refuses, and (b) **`regen-views` is a
  deprecated no-op** that prints a warning and does nothing (`prawduct-hook:4258`), and
  `plugin/lib/views.py` has been deleted outright. There is no opposing control left. The item's
  `effort: S` — which the last triage flagged as predating the two-sided datum and needing
  re-rating — is plausible again for that reason, not by reverting to the old estimate.
- **#702** — `plugin/lib/release_readiness.py` contains **zero** references to `CHANGELOG`. The gap
  is total, not partial.
- **Measured live:** 364 change-log entries, 343 tagged, **31 release-pending, of which 0 are
  scopeless**, enumerating 13 pending scopes. So Chunk 01's refusal has **zero false positives on
  this repo today** — the "it would fail a previously-passing gate" objection is real for other
  repos but not for this one, which is what makes it safe to land here and observe.
- **Measured live, and it shaped Chunk 02's design:** of the 13 pending scopes, literal slug
  matching finds only `delegation` in the open `## v3.4.1-dev.2` section — and it reports
  `branch-claim-multiplicity` as uncovered when that scope's consumer notes **are** in the section,
  written without using the slug. The false-positive mode is not hypothetical; it is the first
  case. This is why Chunk 02 is advisory and why its wording must not read as an assertion of
  absence.

**Open assumptions / unknowns:**

- [DECISION 2026-08-27: Chunk 01 REFUSES (exit 1) rather than reporting — owner ruling, taken
  before Chunk 01 was built] The item left refuse-vs-report open and asked for confirmation. The
  owner confirmed refuse. Rationale as put to them: refusing is what *authority fails closed*
  requires — this is a releasability verdict over work that cannot be classified — the remedy is a
  one-line change-log edit, and it costs this repo nothing today (0 scopeless entries, measured).
  The accepted cost lands on a consumer repo carrying a legacy scopeless entry, whose release newly
  refuses; it is mitigated by naming every offending entry so the fix is mechanical, never by
  softening the verdict. **The veto route, if it is ever re-taken:** make it a WARNING in Chunk 01,
  and the rest of the plan is unchanged.
- [ASSUMPTION: Chunk 03's green-suite refusal belongs at Phase 0 alongside the other checks, not at
  a new Phase 2 gate | MED impact | user can correct]
  The item asks release-prep to "refuse to bump or tag on a non-green suite." There is no
  release-prep command — `release-prep(vX.Y.Z)` is a *commit-message convention* for a hand step
  (`coverage.py:157`, `stale_base_probes.py`). Phase 0 is the checkable moment that already exists
  and already gates the release. If the owner wants the refusal at the tagging moment instead, that
  is a different chunk against the runbook's Phase 2, not a variation of this one.
- [ASSUMPTION: the headline check reads the OPEN prerelease section, keyed by the exact manifest
  string | MED impact | user can correct] This follows the rule restored to
  `test_changelog_has_current_version_entry` this cycle. If a product keys its digest differently,
  the check must degrade to a note rather than a refusal — it is a *coverage* check, not authority.

**What would raise confidence:** the owner ruling on the first assumption — taken 2026-08-27, and
recorded above as a decision. The two that remain are MED and change no exit code.

## Status

- [x] Chunk 01: A release-pending entry with no `scope=` stops being invisible
- [ ] Chunk 02: The digest is checked for the scopes the release is actually shipping
- [ ] Chunk 03: The headline exists, and a red suite refuses the release

Context: authored 2026-08-27 after merging #726 and #658. The three items — `#168`, `#702`, `#259`
— were triaged as one class in the prior session's release-readiness pass: **the gate believes it
saw everything it did not see.** They are planned together because all three land in
`plugin/lib/release_readiness.py` and the same runbook phase; three separate branches would buy
three review cycles over one file and conflict with each other on it.

**Two of the three items describe a codebase that has moved.** #259 prescribes wiring into a
`release-prep` command that does not exist, and #168's recorded blocker was removed by work that
landed after it was filed. Both items are updated at merge; the re-derivation is recorded in the
chunks rather than left as a discrepancy for the next reader to rediscover.

## Scaffolding

Existing repo — no initialization. Suite: the declared `test_commands` (`prawduct-hook test-status`
first; only run if it reports `stale`). Record evidence with `prawduct-hook test-evidence record`.

Several governance prose files carry token-budget guardrail tests — when a doc edit trips one,
simplify or deduplicate within the file first, raise the ceiling second, and never relocate text
between files to dodge a budget.

### Verification Strategy

Tests alone cannot answer these, because every chunk's subject is *this repo's own live release
state*, and that state is the thing a release changes. Three rules, all learned here the hard way:

1. **Run the real gate, not only its unit tests.** Each chunk is exercised by
   `prawduct-hook check-releasability --release vX.Y.Z` against this repo, and the output read.
   The measurement in Requirements Confidence is the baseline to compare against.
2. **A test must never assert this repo's current release PHASE as an invariant.** Six
   `TestAgainstTheReal*` guards died at v3.3.0 because tagging emptied the release-pending set and
   archiving emptied the live plan map. Any test that reads the real change log must state *which
   emptiness it rejects* and stay true across a release, or it must use a fixture.
3. **An advisory's EFFECT is what gets tested, not that it fires.** For Chunks 02 and 03: make the
   recommended change on a fixture, observe the promised outcome, and keep the un-made case as the
   control. A recommendation that ships to every consumer's repo has to be known to work, not known
   to print.

## Chunk 01: A release-pending entry with no `scope=` stops being invisible

- **Description:** `check_releasability` enumerates *scopes*; an entry carrying no `scope=` key
  contributes no scope, so it is never enumerated, never classified against the release plan, and
  cannot be withheld — Phase 0 reports `releasable` while unclassified release-pending work exists.
  The code already knows: the `if not pending:` branch names this blindness in a comment and still
  returns 0. **The accounting exists in the branch where nothing is pending and is absent from the
  branch where something is; that asymmetry is the whole bug in one place.** Count release-pending
  *entries* alongside scopes and refuse when the two disagree, naming every offending entry by its
  heading so the remedy is mechanical.
  **This is the thin vertical slice**: change-log parse → `release_readiness` → CLI exit code →
  the runbook step an operator reads. It proves the whole path before Chunks 02–03 widen it.
- **Depends on:** nothing.
- **Artifacts consumed:** `.prawduct/artifacts/api-contract.md` (error model — exit codes),
  `.prawduct/artifacts/architecture.md` (authority fails closed).
- **Deliverables:** `plugin/lib/release_readiness.py` (entry-vs-scope reconciliation, and the
  symmetric accounting in BOTH branches), `tests/test_release_readiness.py`,
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` (Phase 0 step 0 — whose output the
  operator is told to trust as the full list).
- **Tests:** a scopeless release-pending entry refuses, and the message names it; scoped-only
  refuses nothing; the refusal uses exit **1**, not 3 — 3 means the subject could not be READ, and
  here it reads fine, the work is merely unclassifiable; a mixed log reports both counts; the
  `if not pending:` branch keeps its existing accounting unchanged.
  **Fixtures, not this repo's live log** — see Verification Strategy rule 2. One test may read the
  real log, and it must assert the *invariant* (entries ≥ scopes, and the reported triple is
  internally consistent), never today's numbers.
- **Acceptance criteria:** with a scopeless release-pending entry present, Phase 0 refuses and
  names it; with none, behaviour is byte-identical to today, verified by running the real gate
  before and after against this repo's 31 pending / 0 scopeless baseline.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Chunk 02: The digest is checked for the scopes the release is actually shipping

- **Description:** A release-pending scope can reach the tag with **zero** consumer-facing notes in
  `plugin/CHANGELOG.md`, and no gate asks whether the digest covers it. Observed at the v3.4.0 cut:
  `scope=tactical-efficiency` carried nine `release=v3.4.0` entries and no mention in the digest;
  the notes were hand-written at cut time after somebody noticed. The failure is silent and
  asymmetric — **a section full of good notes reads as finished, so the missing scope is invisible
  exactly when the digest looks healthiest.**
  For each release-pending scope, test whether the open prerelease section mentions it; emit one
  WARNING per uncovered scope, modelled on the existing `has no build-plan file` advisory. **Never
  changes the exit code** — matching prose against a slug is necessarily fuzzy, and this plan has a
  live false positive already (`branch-claim-multiplicity` is covered in prose without its slug).
  The wording must therefore say *"could not find … check it"*, not *"is missing"*: an advisory
  that overstates its own certainty is how a fuzzy check gets promoted to a blocking one.
- **Depends on:** Chunk 01 (shares the entry/scope accounting and the same emission style).
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` (a control names its
  expected yield and emits it observably).
- **Deliverables:** `plugin/lib/release_readiness.py`, `tests/test_release_readiness.py`,
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` (Phase 0's advisory roster and Phase 1
  step 5's — the operator meets every other advisory there, so an absent one reads as not existing).
- **Tests:** a scope absent from the open section warns; a scope present does not; the warning
  never changes the exit code (asserted directly, in both the otherwise-passing and
  otherwise-failing cases); a missing or unparseable digest degrades to a note that **names its own
  consequence** rather than passing silently — *advice fails soft is not advice fails silent*.
  **The advisory's EFFECT is tested**: a fixture where the note is added stops warning, and the
  un-added fixture is retained as the control.
- **Acceptance criteria:** run against this repo, it warns for the pending scopes genuinely absent
  from the open `## v3.4.1-dev.2` section and stays silent for `delegation`; exit code unchanged
  from Chunk 01's. Any scope it names is then checked by hand against the section — a false
  positive is a finding about the check, not about the digest.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Chunk 03: The headline exists, and a red suite refuses the release

- **Description:** Two failures, one moment. (a) The consumer-facing headline is a hand step that
  has been forgotten repeatedly — v2.1.6 was tagged and version-bumped with no headline, leaving
  `develop` **red** on `test_changelog_has_current_version_entry` since the release, i.e. **v2.1.6
  shipped on a red suite**; it recurred at v3.0.4 and was backfilled out-of-band. (b) Nothing
  refuses to tag on a non-green suite.
  **The item's prescribed method is replaced, not conformed to** (*goals and verification bind;
  prescribed method is advice*): it says "wire it into release-prep", and **there is no release-prep
  command** — `release-prep(vX.Y.Z)` is a commit-message convention for a hand step. The goal the
  item states is what binds: the headline stops being forgettable, and a red suite stops reaching a
  tag. Phase 0 is the checkable moment that already exists and already gates the release, so both
  land there.
  Note the direction of (b): this is a *verdict* about whether the release may proceed, so unlike
  Chunk 02 it fails closed.
- **Depends on:** Chunks 01–02 (same function, same emission style; landing last avoids three
  rewrites of one output block).
- **Artifacts consumed:** `.prawduct/artifacts/operational-spec.md` (the version bump is the
  release mechanism), `.prawduct/artifacts/api-contract.md` (error model).
- **Deliverables:** `plugin/lib/release_readiness.py`, `tests/test_release_readiness.py`,
  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` (Phase 0 — so the operator meets the
  refusal where they already look).
- **Tests:** a section whose first non-empty line is absent or is the seeded placeholder is caught;
  a real headline passes; **stale** or **missing** test evidence refuses, and evidence recording
  `failed > 0` refuses; a `--degraded` record is treated as stale rather than as a pass (the
  degraded-run distinction exists precisely so a contended run cannot read as green). The headline
  check degrades to a NOTE where the digest is keyed differently — it is coverage, not authority.
- **Acceptance criteria:** against this repo with its current green evidence, Phase 0's verdict is
  unchanged; with evidence deliberately staled, it refuses and says which condition failed. The
  v2.1.6 scenario — version bumped, no headline — is reproduced as a fixture and refused.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over the branch. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**After Chunk 01.** Run `prawduct-hook check-releasability --release v3.4.1` and read the output
against the baseline in Requirements Confidence. That single run answers the plan's riskiest
question — whether refusing is the right posture — while only one chunk's worth of work is
committed, and the assumption is still cheap for the owner to veto.
