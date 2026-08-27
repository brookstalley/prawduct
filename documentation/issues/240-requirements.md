# Issue #240 — Governance: Treat Strategy-Artifact Backfill as Retroactive Discovery: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-08-21 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/240`

Related: GOV-4X9M (this item's id alias, `.prawduct/backlog.md:1790-1881`); GOV-2T6K (shipped —
the `architecture.md` template, closing the one hard scaffolding dependency this item's provenance
note flagged); GOV-5K3M (the solo authoring of prawduct's own 7 strategy-class artifacts that
surfaced this failure mode); GOV-EXI2 (reactive systems can't detect absence); issue #257 (the
2026-08-11 ruling that deleted the work-model tripwire this issue's own text names as a likely
detection substrate).

## Problem

Authoring a strategy-class artifact (data model, security model, NFR, operational spec,
observability strategy, plus the characteristic-triggered API contract and architecture) is a solo
agent task. Solo authoring tends to codify current practice as if it were intended design, because
the agent cannot know the owner's actual intent — intent lives in the owner's head, not the repo.
The Critic currently rewards this failure mode: a cumulative review praised prawduct's own 7
artifacts for being "accurate to prawduct's actual system," and accuracy-to-current-code is the
wrong success metric for a document meant to lead development (`.prawduct/backlog.md:1793-1794`,
observed live during GOV-5K3M).

The source issue proposes treating backfill as an interview (reusing discovery, not building a
second flow), a Critic check that flags a purely-descriptive backfilled artifact as a finding,
layered opt-outs, and a two-type divergence model (code-below-norm vs. norm-below-best-practice)
built on the existing norm lifecycle. This document grounds those proposals against the current
codebase, corrects one load-bearing assumption the issue makes about its own detection mechanism,
and resolves what a requirements pass can decide now versus what stays open for design.

## Grounding facts

Re-verified against the current tree (2026-08-21):

- **The issue's named detection substrate no longer exists.** The issue speculates detection is
  "likely built on the work-model tripwire / jurisdiction+coverage machinery." The work-model
  tripwire **was deleted 2026-08-11** by owner ruling on #257: it fired on ordinary conversational
  prompts and had stopped carrying signal; requirements-precede-code enforcement moved to a
  review-time question instead (`plugin/lib/work_model_index.py:18-30`; `plugin/CHANGELOG.md:
  171-175`). `jurisdiction_candidates` (the surviving half of "jurisdiction+coverage machinery,"
  `plugin/lib/work_model_index.py`) ranks candidate governing artifacts by vocabulary overlap
  against a plan's `governed_by:` field — it matches text against artifacts that **already exist**;
  it is not a missing-artifact detector. This means the issue's assumed JIT ("you asked to add
  logging but there's no observability-strategy") detection path has no live substrate to build on
  today — it would be new detection work, not a reuse.
- **All 7 strategy-class templates exist today** (`data-model.md`, `security-model.md`,
  `nonfunctional-requirements.md`, `operational-spec.md`, `observability-strategy.md`,
  `api-contract.md`, `architecture.md`) — the one hard dependency the issue's provenance note
  flagged (`templates/architecture.md` missing) shipped 2026-07-17 as GOV-2T6K
  (`.prawduct/change-log.md:11027-11036`).
- **Every one of the 7 templates already carries an optional `## Direction` convention** — an
  identical boilerplate HTML comment (e.g. `plugin/templates/architecture.md:45-53`,
  `data-model.md:20-28`) instructing: add a `## Direction` heading only with a real entry
  (Statement/Why/Status), because a bare heading reads as ratified norms to the advisory probes.
  This is the existing recording mechanism for "intended design" — it is not new, but it is
  **optional and currently under-used**: none of the 7 templates reference `discovery.md`, and
  `discovery.md` itself never names any of the 7 artifacts or a Direction concept anywhere in its
  230 lines (confirmed by grep). Nothing today prompts an author to populate it during backfill.
- **The norm lifecycle (Migrate / Grandfather / Contain, birth, `Status: in-transition`, stall
  detection) is a real, fully-built mechanism in `plugin/docs/norms.md`** (410 lines) —
  Authority Rule (`:17-40`), Anatomy of a Norm (`:93-114`), Birth + the 3 retroactivity dispositions
  (`:118-140`), stall detection on the tracking item (`:189-198`), ambient/structural-characteristic
  re-open (`:217-235`), and an existing ratification flow for adopting norms on existing products
  (`:311-333`, via `/prawduct:doctor`). GOV-4X9M's own text says to reuse this wholesale for
  divergence handling; grounding confirms it is mature enough to reuse as-is, and that Migrate is
  the literal mechanism the issue's "Type 1" maps to.
- **No existing Critic check flags a purely-descriptive artifact.** Critic enforcement today
  (`norms.md`'s Enforcement table, `:238`; `plugin/skills/critic/goals-1-3.md:33`) catches
  *amendment* of an existing ratified `## Direction` entry to match code (the "amend tell") — it
  does not evaluate an artifact at *authoring/backfill* time for whether it states intent at all.
  Principle 3 (Living Documentation — "documentation describes what IS, not what SHOULD BE; when
  docs don't match reality, fix the docs or fix the code") is the standing counter-pressure the
  Critic exhibited when it praised accuracy-to-code — any new check here must coexist with
  Principle 3 for every other document, not override it repo-wide.
- **None of the four headline mechanisms exist anywhere outside the GOV-4X9M backlog entry's own
  prose.** A repo-wide search for `decline-once`, `decline-this-doc`, `decline-everything` returns
  zero hits. `backfill` appears only for unrelated mechanical backfills (plan-backfill archiving,
  reconciliation-mode `project-state.yaml` backfill in `discovery.md:76`). `(not relevant — …)` is a
  real, shipped, **binary** existence stub (`planning.md:53`, `coverage_probes.py` docstring,
  `norms.md`'s Adoption section) — it is not the graduated three-layer opt-out the issue proposes,
  but it is the exact mechanism a "decline-this-doc" layer should reuse rather than reinvent.
- **`feedback_artifacts_express_intent` and `feedback_advisor_first` are not committed anywhere.**
  Neither appears in `.prawduct/learnings.md` or `learnings-detail.md`; both exist only as
  not-yet-promoted memory names referenced inside GOV-4X9M's own backlog text
  (`.prawduct/backlog.md:1799-1800,1815`). "Artifacts should express intent" is currently an
  informal idea, not a rule in `planning.md` — confirmed by grep: the phrase appears nowhere in
  `planning.md`'s 197 lines, which frames `## Direction` purely as a norm-binding device
  (`planning.md:95-100`), not as backfill's default authoring stance.

## Decisions

**1. Detection stays on the existing coverage signal — this item builds no successor to the
deleted tripwire.** `coverage_probes.py`'s `UNIVERSAL_ARTIFACTS`/`TRIGGERED_ARTIFACTS` existence
check (session-start / `/prawduct:doctor` advisory) is the trigger for offering backfill-interview
mode. The issue's "mid-request JIT nudge, calibrated to stakes" is a genuinely separate, harder
detection problem whose one named substrate no longer exists (#257's own disposition: replaced by
a review-time question, not a mid-conversation signal) — building a new one is out of scope here,
not silently assumed solved.

**2. The interview reuses discovery.md's existing flow via one new fork, not a second flow.**
When backfill-interview mode is offered for a strategy-class artifact whose code already exists
(the defining backfill condition — code precedes the doc), `discovery.md` gains an explicit mode
question before authoring: draft-from-what's-built vs. first-principles, and capture-current-state
vs. set-direction. This is new methodology text in `discovery.md` (a per-artifact elicitation gap
the grounding pass confirms is real — no `## Surface Data Model`/`Security`/`Architecture` sections
exist today), not a new mechanism.

**3. Backfilled artifacts default to stating intended design via the existing `## Direction`
convention, populated rather than left bare.** This reuses the templates' existing optional
heading — the change is behavioral (backfill in "set direction" mode must populate it) not
structural (no new heading, no new template field).

**4. Divergence handling reuses `norms.md`'s Migrate/Grandfather/Contain wholesale — Type 1 is
literally Migrate.** Code-below-norm (the documented goal is genuinely best practice, code lags) is
recorded exactly as `norms.md:118-140` already describes: norm born `Status: in-transition`,
divergences become a sized backlog item wired as the norm's tracking ref so stall detection
applies. No new taxonomy is invented for Type 1.

**5. Type 2 (norm-below-best-practice) needs one genuinely new rule: elicit-then-always-ratify with
honest labeling.** `norms.md`'s existing ratification flow does not today distinguish "the owner is
knowingly choosing something sub-optimal" from an ordinary ratification — nothing currently requires
eliciting the *why* before recording, or labeling the outcome differently depending on whether that
why resolves the concern. The agent never vetoes (every best practice is a defeasible heuristic the
developer may have context the agent lacks — Principle 23, owner-authority), but the record must be
honest: a why that resolves the concern records as a legitimate context-specific decision; a why
that doesn't still ratifies, but records the unresolved concern on the record rather than omitting
it. The only thing the agent ever declines is to launder — label a knowingly sub-optimal choice as
recommended practice.

**6. The Critic objective-flip is scoped narrowly: strategy-class Direction content authored via
this flow only, never a general documentation check.** Principle 3 continues to govern every other
document unchanged. The new check fires only when a strategy-class artifact's `## Direction`
section was populated through backfill-interview mode and merely restates current code behavior
with no elicited rationale beyond "this is what exists" — this keeps the two rules from
contradicting each other repo-wide.

**7. Opt-outs are three layers, two of which already exist in another form.** Decline-once (default
for ambiguity; no stub written; re-offered next time the same coverage trigger fires — never
calendar-triggered) is net new behavior. Decline-this-doc reuses the **existing** `(not relevant —
X)` stub convention already shipped in `coverage_probes.py`/`planning.md` — not a second stub
mechanism. Decline-everything is one new, reversible, project-scoped preference that suppresses
proactive backfill nudges only; it does not touch mechanical gates or `/prawduct:doctor`'s on-demand
answers.

**8. Validating an opt-out against recorded characteristics reuses the existing
structural-characteristic re-open, pending a design-stage confirmation of the code path.** A
`(not relevant — X)` stub's expiry on a structural-characteristic flip is already described as
existing machinery (`norms.md:217-235`); this item requires strategy-class stubs go through that
same path, and leaves confirming/wiring the exact code path to design.

## Requirements

MUST unless marked SHOULD.

- **BKF1** When a strategy-class artifact's coverage trigger fires (`coverage_probes.py`'s
  `UNIVERSAL_ARTIFACTS`/`TRIGGERED_ARTIFACTS` existence signal) for a product where the governed
  behavior already exists in code, `discovery.md` offers the backfill mode fork (Decision 2) before
  authoring begins — not a silent solo draft.
- **BKF2** A backfill session conducted in "set direction" / first-principles mode MUST NOT close
  with a bare or absent `## Direction` section — at least one populated entry (Statement, Why,
  Status per `norms.md`'s existing Anatomy of a Norm) is required before the artifact is considered
  authored.
- **BKF3** A backfill session conducted in "capture current state" mode is explicitly permitted to
  leave `## Direction` absent — this item does not force intent-stating on an owner who has declared
  the doc is descriptive-by-choice; Principle 3 governs that document as normal.
- **BKF4** Type 1 divergence (an elicited Direction entry the current code does not yet satisfy) is
  recorded via `norms.md`'s existing Migrate disposition — norm born `Status: in-transition`, a
  sized backlog item as its tracking ref. No new divergence-recording mechanism is built.
- **BKF5** Type 2 (the owner wants to ratify a norm below best practice) always ratifies — the
  agent never withholds ratification — but MUST elicit the owner's why first, and MUST record the
  outcome honestly: as a legitimate context-specific decision when the why resolves the concern, or
  as an unresolved concern noted alongside the ratified norm when it does not. Laundering a
  knowingly sub-optimal choice as "recommended practice" is the one outcome this item forbids.
- **BKF6** The Critic gains a new check, scoped exclusively to strategy-class `## Direction` content
  populated via backfill-interview mode (Decision 6): a purely-restates-current-behavior entry with
  no distinguishable elicited rationale is a finding. This check MUST NOT fire on any document or
  Direction entry authored outside this flow — Principle 3's existing scope is otherwise unchanged.
- **BKF7** Three opt-out layers exist: decline-once (default; no stub; re-offered on the next
  trigger of the same coverage signal), decline-this-doc (writes the existing `(not relevant — X)`
  stub — reused, not reinvented), decline-everything (one new, reversible, project-scoped
  preference suppressing proactive backfill nudges only; `/prawduct:doctor` and mechanical gates
  remain unaffected).
- **BKF8** No new mid-conversation "requested work implies a missing artifact" detector is built by
  this item. The backfill flow's only trigger is the existing session-start/doctor coverage signal
  (BKF1) — a successor to the deleted work-model tripwire, if ever built, is separate work.
  (SHOULD, to make explicit that this is a deliberate scope line rather than an oversight.)
- **BKF9** A strategy-class `(not relevant — X)` stub written via decline-this-doc is subject to
  the same structural-characteristic re-open `norms.md` already describes for other stubs — the
  design pass confirms and, if needed, wires the exact code path; this item does not invent a
  second validation mechanism.

## Acceptance

- [ ] A backfill session (coverage-trigger fires on a product whose code precedes the doc) offers
      the mode fork before authoring, per BKF1.
- [ ] A "set direction" backfill cannot close with a bare/absent Direction section (BKF2); a
      "capture current state" backfill may (BKF3).
- [ ] Type 1 divergence is recorded through `norms.md`'s existing Migrate disposition, not a new
      mechanism (BKF4).
- [ ] Type 2 is always ratified, elicits the why first, and labels the outcome honestly rather than
      laundering a sub-optimal choice as recommended (BKF5).
- [ ] The Critic's new check fires only on backfill-populated strategy-class Direction content and
      leaves Principle 3's governance of every other document untouched (BKF6).
- [ ] All three opt-out layers exist; decline-this-doc reuses the existing stub convention rather
      than a second one (BKF7).
- [ ] No new mid-conversation missing-artifact detector ships as part of this item (BKF8).

## Scope-out (this item)

- A replacement for the deleted work-model tripwire, or any new mechanism for detecting that
  requested work implies a missing/thin artifact mid-conversation — a separate, harder problem;
  #257's disposition (moved to a review-time question, `scope-trace:`) stands until a further item
  addresses it.
- Re-deriving prawduct's own 7 already-authored artifacts through this flow once it exists — a
  natural follow-up, not required to ship this capability.
- Whether first-response proactive advisory surfacing actually helps vs. annoys — an empirical
  question the source issue itself frames as "secondary, test don't design."
- The exact Critic check's name, default severity, and the precise judgment mechanism for
  "purely restates current behavior with no elicited rationale" — design-stage.
- The exact `/prawduct:doctor` / session-start UX copy for offering the mode fork, and the exact
  code path confirming a strategy-class stub is already subject to the structural-characteristic
  re-open (BKF9) — design-stage.
- Any rewrite of Principle 3's own text — this item scopes a narrow, flow-specific Critic check
  around it, not a principle amendment.

## Evidence / references

- `.prawduct/backlog.md:1790-1881` (GOV-4X9M) — the full design conversation this item drafts
  requirements from, including the Type 1/Type 2 correction and the no-veto correction.
- `plugin/lib/work_model_index.py:18-30` — the work-model tripwire's deletion, its disposition
  (#257), and `jurisdiction_candidates`, the surviving vocabulary-overlap ranking that is not a
  missing-artifact detector.
- `plugin/CHANGELOG.md:171-175` — corroborating changelog entry for the tripwire deletion.
- `plugin/templates/architecture.md:45-53`, `data-model.md:20-28`, and the equivalent boilerplate in
  the other 5 strategy-class templates — the existing optional `## Direction` convention.
- `.prawduct/change-log.md:11027-11036` — GOV-2T6K, the `architecture.md` template shipping and
  closing the one hard scaffolding dependency.
- `plugin/methodology/discovery.md` (230 lines, grepped in full) — confirms no `## Surface Data
  Model`/`Security`/`Architecture` sections and no reference to any of the 7 templates by name.
- `plugin/methodology/planning.md:53,95-100` — strategy-class artifact coverage tracking and the
  existing (norm-only) framing of `## Direction`; confirms no "express intent by default" rule.
- `plugin/docs/norms.md:17-40,93-140,189-198,217-268,311-333` — the Authority Rule, Anatomy of a
  Norm, the 3 retroactivity dispositions, stall detection, ambient re-open, and the existing
  ratification flow this item reuses wholesale.
- `plugin/skills/critic/goals-1-3.md:33` — the existing "amend tell" enforcement, distinguished from
  the net-new authoring/backfill-time check this item requires.
- `.prawduct/backlog.md:1799-1800,1815` — the `feedback_artifacts_express_intent` /
  `feedback_advisor_first` memory references, confirmed absent from `learnings.md`.
- Repo-wide grep for `decline-once`, `decline-this-doc`, `decline-everything` — zero hits, confirming
  the layered opt-out model is entirely greenfield.
