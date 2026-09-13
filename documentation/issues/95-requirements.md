# Issue #95 — Critic Skill: Invocation + Output Contract for Programmatic / Non-Git-Artifact Review: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-09-01 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/95`

Related: companion issue #96 (session-continuity / intent-reconciliation — same TangleClaw
engagement, separate topic, out of scope here — Scope-out); `.prawduct/artifacts/api-contract.md`
(the CLI stability-tier framework D2/D3 below reuse rather than duplicate); issue #334 (a
single-latest-fact view stands in for the evidence store — the same `.critic-findings.json`-as-
derived-view fact D2's grounding relies on).

## Problem

Four questions from an external collaborator (TangleClaw, building a session-rules
self-improvement loop on top of prawduct's governance) about whether the Critic skill has, or
intends, contract guarantees beyond its current file-backed, single-repo, interactive-session
design. Filed 2026-06-17 against v2.1.5; the reporter re-validated against `develop` on
2026-07-31 and partially retracted Q2 after the kernel v3 evidence-store cutover changed its
premise. Re-verified in this pass against the current `develop` branch (2026-09-01) — all four
still stand, one (Q2) in narrowed form:

- **Q1 — no non-git review mode.** `_VALID_ARG_MODES` (`plugin/lib/critic_mode.py:101` as of
  this pass; `:89` at the reporter's 2026-07-31 check — the module has grown, the set is
  unchanged) is exactly `{chunk, final, cumulative, verify-resolutions}`; all four resolve their
  review interval from git state (`critic_mode.py`'s module docstring). There is no way to hand
  the Critic a proposed artifact that is not a tracked file in the working tree — e.g., a row
  about to be written to SQLite.
- **Q2 — narrowed, still open.** The reporter's original framing ("output-path override, to stop
  an out-of-band pass from clobbering the build-chunk record") described the pre-v3 data plane,
  where the model hand-wrote `.critic-findings.json` and it was authoritative. That premise is
  gone: the file is now a derived view `critic-consolidate` regenerates from the append-only
  evidence store (`critic_consolidate.py:3065-3066`; CLAUDE.md states no gate reads the cache
  file), so nothing is clobbered. What survives, per the reporter's own re-check: every
  consolidated review — build-cycle or not — unconditionally appends a `review.critic` event to
  the governance ledger (`critic_consolidate.py:3079-3103`), which `review-stats` counts for
  cost/yield telemetry. A scheduled, non-build-cycle caller inflates that instrument against
  reviews that were never part of a build cycle.
- **Q3 — invocation status undocumented.** `plugin/skills/critic/SKILL.md`'s frontmatter carries
  `disable-model-invocation: false`, so a model-driven, non-human-typed invocation of
  `/prawduct:critic` works mechanically. Nowhere does the skill, `api-contract.md`, or CLAUDE.md
  state whether that is a **supported, stable pattern** a third party may build automation on, or
  an artifact of the framework's own internal usage that happens to also work when driven from
  outside. The reporter names this the one question blocking a decision on their side.
- **Q4 — the workaround is real but undocumented.** Staging a proposed artifact as a tracked file
  and running `chunk` mode against it is the only path that exists today (Q1's finding — there is
  no interval a mode can resolve against otherwise). The reporter's own trap — staging under
  `.prawduct/` is invisible to git because it is gitignored, so the staged file must live at an
  ordinary tracked path — is real and is not written down anywhere a third party would find it
  before hitting it.

## Grounding facts

- All four Critic modes derive their review interval from git state; there is no interval concept
  independent of a commit/working-tree comparison (`plugin/lib/critic_mode.py`, module docstring
  and `_VALID_ARG_MODES`).
- The kernel v3 data plane is code-written and append-only: `critic-begin` derives the manifest,
  reviewers write partials, `critic-consolidate` appends one fact per review to the shared
  evidence store (`evidence.append_fact(project_dir, "review", review_id, body)`,
  `critic_consolidate.py:3006`) and regenerates `.critic-findings.json` as a derived cache
  (`critic_consolidate.py:3065-3066`) — no gate reads the cache file directly.
- `critic-consolidate` unconditionally appends a `review.critic` governance-ledger event once per
  review, idempotent by `review_id` but not suppressible by any flag
  (`critic_consolidate.py:3080-3103`; `plugin/lib/ledger.py:65`,
  `_EVENT_ROLES = {"review.critic": "critic", "review.pr": "pr"}`). The append's own comment
  states why there is no dedupe beyond the idempotency check: `review-stats` counts these lines,
  so a second consolidation — or, symmetrically, a caller-suppressed one — corrupts the same
  proportionality instrument from the other direction.
- `.prawduct/artifacts/api-contract.md` already governs prawduct's programmatic surfaces and
  states the policy this item's decisions must fit inside: the CLI subcommand surface — every
  `prawduct-hook` subcommand beyond two named read-only commands — is **internal/unstable**,
  "a consumer that binds to another subcommand gets no promise" (`api-contract.md:34-35, :51`).
  It also records a live precedent for promoting a subcommand to a stable, externally-supported
  tier once a real external caller appears (the `print-install-reference`/`version` ruling,
  `api-contract.md:50-55`) — the mechanism this item's decisions reuse rather than duplicating.
- CLAUDE.md's own "The Critic — Independent Review" section instructs a builder session to invoke
  `/prawduct:critic` itself, mid-session, as a normal step. Model-driven invocation of the Critic
  **within the repo the Critic is governing** is not an edge case; it is the framework's designed
  primary usage. The reporter's Q3 is narrower than that: an **external product's own automated
  loop**, potentially unattended/scheduled rather than interactive, invoking `/prawduct:critic` —
  a pattern CLAUDE.md does not describe either way.
- Companion issue #96 (session-continuity / intent-reconciliation) is the same TangleClaw
  engagement, filed by the reporter as a separate topic. Out of scope here.

## Decisions

### D1 — Q1: no new non-git review mode; the tracked-file workaround is confirmed as the permanent pattern

Adding a fifth mode with a git-independent interval would fork the one property kernel v3's
dispatch exists to guarantee: `critic-begin` derives the reviewed interval **deterministically
from git state**, never from a model's say-so (kernel v3 D8; restated in `SKILL.md`'s role
comment — "The data plane is deterministic"). A non-file-backed artifact (a SQLite row, an inline
string) has no git identity to derive `commit_reviewed`, `files_reviewed`, or a demotable interval
from — supporting it honestly means either (a) a second, parallel non-deterministic dispatch path
outside kernel v3's evidence-store model, duplicating the manifest/consolidate machinery for a use
case with exactly one known caller, or (b) requiring the caller to give the artifact a git
identity first, which the tracked-file workaround already does. (b) is cheaper, already works,
and keeps every review — file-backed or staged — inside the one deterministic data plane the rest
of the framework relies on. **Decision: no new mode. The tracked-file-plus-`chunk`-mode pattern is
confirmed as the intended, permanent path, not a stopgap**, and D4 makes it documented rather than
discovered-by-trial.

### D2 — Q2: no ledger-suppression flag; classify by caller intent instead of adding an escape hatch

Two shapes could stop a scheduled non-build-cycle caller from inflating `review-stats`: suppress
the ledger append for that call (an opt-out flag on `critic-begin`/`critic-consolidate`), or give
such calls a distinct event kind the aggregator already knows to exclude. The opt-out shape is
rejected: the append's own idempotency comment (`critic_consolidate.py:3080-3087`) treats
under-counting and over-counting as the same failure class — "this ledger has neither key nor
dedupe... a second consolidation would double-count" — and a caller-supplied suppression flag
reintroduces that failure mode in the opposite direction, indistinguishable on disk from a review
that silently failed to anchor. **Decision: add an explicit non-build-cycle event kind** rather
than a suppression flag — `review.critic` gains a sibling (exact name/shape left to design; e.g.
a distinct event string or a `--source external` argument on the existing one) that `review-stats`
excludes from build-cycle cost/yield aggregation by construction. The review is still recorded —
nothing is silently dropped (Principle 5, Honest Confidence) — it just does not corrupt the
proportionality instrument. This is additive to the ledger's event vocabulary, which
`api-contract.md`'s additive-first evolution norm (`api-contract.md:59-60`) already permits
without a stability-tier promotion, since the ledger is not part of the two-command stable tier
either way.

### D3 — Q3: model-driven invocation is supported for a governed repo's own session; unattended/external-loop invocation is a distinct, currently unratified case

Two different claims hide under "is model-driven invocation supported":

1. **An agent, mid-session, in a repo the Critic is reviewing, invokes `/prawduct:critic` itself**
   (no human types the slash command). This is not merely permitted by
   `disable-model-invocation: false` — it is CLAUDE.md's own instructed builder behavior ("Follow
   the plan — run the Critic after acceptance criteria pass"). **This is already a supported,
   stable pattern.** This item's contribution is saying so somewhere a third party building on
   prawduct would find it (D4) — today the only evidence is CLAUDE.md's second-person instruction
   to *this* framework's own builder session, which a reader outside the repo has no reason to
   read as a portable guarantee.
2. **An unattended, possibly scheduled automation invokes `/prawduct:critic` against a
   prawduct-onboarded repo with no interactive session driving it and no build-plan/chunk
   context** — the reporter's actual case. Nothing in the skill, `api-contract.md`, or CLAUDE.md
   rules this in or out; it has never been exercised or tested. **Decision: this item states the
   gap and stops short of ratifying it.** Declaring it supported without having exercised an
   unattended invocation — does the session-mutation guard's TTL behave sanely with no session to
   `/clear`? does a scheduled caller's own orchestration correctly serialize per repo, given the
   critic-active marker allows exactly one live review at a time (`SKILL.md`'s "No session event
   releases a live marker" invariant)? — would be an unearned guarantee. The design-stage
   deliverable is a short, explicit statement of these untested edges, not a claim that they don't
   exist.

### D4 — Q4: document the tracked-file workaround and the `.prawduct/`-gitignore trap as the endorsed pattern

Confirmed by D1 as the permanent path, so it earns a real home rather than living only in this
issue and the reporter's own trial-and-error. **Decision:** `plugin/skills/critic/SKILL.md` (or a
short FAQ-shaped doc it points to — placement is design-stage) gains a stated pattern: to review a
proposed artifact that is not yet committed anywhere in its target form, stage it as an ordinary
tracked file (never under `.prawduct/`, which is gitignored and invisible to the Critic's
`git status`/`git diff`) and run `chunk` mode against it. This closes the exact gap Q4 named — a
caller currently has to discover the gitignore trap by hitting it, the way this reporter did.

## Requirements

MUST unless marked SHOULD.

- **CRT1** No new Critic mode is added for non-file-backed artifacts (D1). The existing four-mode,
  git-anchored contract is unchanged.
- **CRT2** The governance ledger gains a way to record a Critic review that is not part of a build
  cycle without it being counted by `review-stats`'s build-cycle cost/yield aggregation (D2). The
  existing `review.critic` event, its idempotency behavior, and every current consumer of it are
  unchanged for build-cycle reviews.
- **CRT3** Documentation (SKILL.md and/or CLAUDE.md — placement decided at design) states
  explicitly that a governed repo's own session invoking `/prawduct:critic` autonomously,
  mid-session, is a supported and intended pattern, not an accident of
  `disable-model-invocation: false` (D3.1).
- **CRT4** Documentation separately and explicitly states that unattended/scheduled invocation
  with no interactive session present is **not yet a ratified pattern**, and names the specific
  untested edges (session-mutation-guard TTL behavior with no session; cross-invocation
  serialization under the single-live-review marker) a caller would need to verify before relying
  on it (D3.2). This is a documentation requirement, not a code change — no new guarantee is made,
  only an existing gap named.
- **CRT5** The stage-as-tracked-file + `chunk`-mode pattern for reviewing a proposed artifact
  before it lands is written down as the endorsed approach, including the `.prawduct/`-is-
  gitignored caveat, somewhere a third party integrating with prawduct would find it before
  hitting the trap (D4).
- **CRT6** SHOULD: the reporter (or the issue thread) receives a summary of these decisions, since
  Q3 was explicitly named as the one blocking a decision on their side.

## Acceptance

- [ ] Q1 has a recorded, permanent answer (no new mode) rather than remaining open.
- [ ] Q2's narrowed ask (ledger inflation, not clobbering) has a decided mechanism (a new
      event kind) rather than an added suppression flag.
- [ ] Q3's two distinct claims — in-repo autonomous invocation vs. unattended external-loop
      invocation — are each answered separately: one confirmed supported, the other named as an
      open, unratified gap with its specific untested edges listed.
- [ ] Q4's workaround is written down somewhere a third-party integrator would find it, including
      the gitignore trap.

## Scope-out (this item)

- **Implementing CRT2's new ledger event kind.** Naming and wiring it (event-kind string,
  `review-stats` exclusion logic, whether it is a new `--event` value or a `--source` argument on
  the existing one) is design-stage work; this item only decides that suppression is rejected in
  favor of classification.
- **Writing the exact CRT3/CRT4/CRT5 documentation text and choosing its precise location**
  (SKILL.md vs. CLAUDE.md vs. a new FAQ doc). Left to design, per this repo's convention of
  splitting requirements (what must be true) from design (exact wording/placement) — compare
  183-requirements.md's identical split for its OV1/OV2.
- **Exercising an actual unattended/scheduled Critic invocation to validate D3.2's named edges.**
  This item states that they are untested, not that they are broken; running one is live-session
  work belonging to whichever item eventually ratifies the pattern (or to the reporter's own
  integration work), not to a docs-only requirements pass.
- **Companion issue #96** (session-continuity / intent-reconciliation). Same reporter, same
  engagement, explicitly filed as a separate topic.
- **Promoting any part of the internal CLI subcommand surface to `api-contract.md`'s stable
  tier.** Nothing here asks a third party to bind to a `prawduct-hook` subcommand directly; every
  decision above operates at the skill/documentation layer, so `api-contract.md`'s revisit trigger
  ("a third subcommand needing the stable tier") is not fired by this item.

## Evidence / references

- `plugin/skills/critic/SKILL.md` — frontmatter (`disable-model-invocation: false`,
  `user-invocable: true`), and the "Getting Started" mode-resolution/dispatch/roster steps D1 and
  D3 read against, including the "No session event releases a live marker" invariant D3.2 cites.
- `plugin/lib/critic_mode.py` — `_VALID_ARG_MODES` (`:101` as of this pass) and the module
  docstring's four-rule, git-anchored inference (Q1's grounding).
- `plugin/lib/critic_consolidate.py:3006` (`evidence.append_fact` — the review fact),
  `:3065-3066` (`.critic-findings.json` regenerated as a derived cache), and `:3079-3103` (the
  unconditional, idempotent-by-`review_id` `review.critic` ledger append and its own
  double-count/under-count comment) — Q2's grounding, both the retracted pre-v3 premise and the
  surviving ledger-inflation concern.
- `plugin/lib/ledger.py:65` — `_EVENT_ROLES`, the closed vocabulary CRT2's new event kind extends.
- `.prawduct/artifacts/api-contract.md:20-35, :50-55` — the existing internal/unstable default for
  the CLI subcommand surface, and the precedent (the `print-install-reference`/`version`
  stable-tier ruling) this item's decisions deliberately reuse rather than duplicate.
- `CLAUDE.md` § "The Critic — Independent Review" — the framework's own instruction for a builder
  session to invoke `/prawduct:critic` mid-session, which D3.1 confirms as the supported pattern
  for an in-repo session.
- Issue #95 comment `5138070386` (2026-07-31) — the reporter's own re-validation against
  `develop`, including the Q2 partial retraction D2 continues from, and the explicit "Q3... is the
  one blocking a decision on my side" flag CRT3/CRT4/CRT6 answer.
- Issue #96 — companion, out of scope (Scope-out).
