<!-- Build Plan — single-PR bookkeeping (merge is the state change)
     User-reported friction: consumers pushing to protected integration
     branches must open a SECOND PR just for post-merge housekeeping
     (the status=merged stamp commit, trunk-repo shipped flips, build-plan
     retirement). This plan retires every framework step that requires a
     commit to the integration branch outside a PR, without weakening the
     release-integrity guarantees (REL-2N8K / REL-6C3W / REL-9F2T).
-->
---
artifact: build-plan
version: 1
scope: single-pr-bookkeeping
depends_on: []
last_validated: 2026-07-10
---

## Requirements Confidence

**Level:** High

**Why:** The problem is user-stated and observable (two-PR housekeeping on
protected branches). The investigation mapped every consumer of the
`status=merged` stamp and confirmed the release-integrity value lives in the
OTHER REL-9F2T pieces (the `check-change-log-entry` probe, the "flip every
unreleased entry" release rule, fail-closed regen validation) — not in the
stamp. The backlog skill already established the design precedent: bookkeeping
rides in the closing PR, atomic with the merge (an abandoned PR abandons its
bookkeeping too, so state can't drift).

**Problem:** Framework flows require post-merge commits directly on the
integration branch (merge-flow step 6 `stamp-merged` chore commit; trunk-repo
shipped flip + build-plan retirement in step 8; the stale change-log template
saying "tag `status=shipped` as soon as the merge commit lands"). On protected
branches these are impossible without a dedicated housekeeping PR.

**Success:** After this plan, no framework flow instructs a commit to the
integration branch outside a PR. A feature PR carries ALL of its own
bookkeeping; a gitflow release carries the shipped flips in its (single)
release-prep commit/PR. `regen-views` and the release checklist treat
statusless tagged entries as first-class release-pending state.

**Out of scope:** COV-5H3N (resolve-base gitflow default), the governance-only
PR fast-path umbrella item, backlog-mutation atomicity — adjacent backlog items
left as filed. No change to review gates (Critic, PR reviewer, probes).

**Open assumptions / unknowns:**

- [ASSUMPTION: `stamp-merged` (hook command + `stamp_merged` fn) is KEPT
  functional but deprecated — it prints a deprecation notice and still stamps
  (harmless, convergent) so consumer muscle-memory/scripts don't hit an
  unknown-command error; removal deferred to a future major. | MED impact |
  user can override to hard-remove]
- [ASSUMPTION: `status=merged` stays a recognized value forever (existing
  consumer change-logs contain it); statusless-tagged simply becomes the
  EXPECTED release-pending state rather than "stamp missed". | LOW impact |
  user can defer]
- [ASSUMPTION: trunk repos (base = release surface) write their entry
  `status=shipped` ON the feature branch and retire the build plan in the
  closing PR — same atomic-with-merge argument the backlog skill already
  codifies. The status line only becomes visible on the base when the merge
  makes it true. | MED impact | user can override]

**What would raise confidence:** N/A — assumptions are recorded for veto, not
blocking.

## Status

- [ ] Chunk 01: Statusless is release-pending — lib + hook
- [ ] Chunk 02: Flow prose cascade — PR skill, release process, template
Context: plan authored 2026-07-10 from the user's protected-branch friction
report; investigation in-session (all stamp consumers mapped).

## Scaffolding

Not applicable — mature repo; existing pytest suite (`python3 -m pytest -q`).
No new dependencies.

### Verification Strategy

Beyond unit tests: run `prawduct-hook regen-views --check` and
`prawduct-hook stamp-merged` against THIS repo's real change-log (deprecation
notice observable; regen enumerates statusless-tagged scopes). Grep the whole
repo for `stamp-merged`/`status=merged` prose after Chunk 02 to confirm the
cascade left no contradicting instruction (Coherent Artifacts).

## Project Structure

No new modules. Change-log logic stays in `lib/views.py`; `bin/prawduct-hook`
keeps thin wrappers; flow prose in `skills/pr/SKILL.md`,
`docs/release-process.md`, `templates/change-log.md`.

## Build Chunks

### Chunk 01: Statusless is release-pending — lib + hook

- **Description:** Make the code treat a statusless *tagged* entry as
  first-class release-pending state, and deprecate the stamp. (1)
  `collect_release_pending_scopes` also enumerates scopes from statusless
  tagged entries (today: only `shipped`/`merged`), so a batched release's
  `regen-views` flips every pending plan with no stamp ever applied. (2)
  `diagnose_scope_plan_coverage` label for statusless entries reworded:
  "unreleased (statusless — release-pending)" — no longer "merge stamp
  missed?". (3) `cmd_stamp_merged` prints a deprecation notice on stderr
  (statusless = release-pending; stamping optional) while continuing to work;
  `stamp_merged` docstring updated to the new lifecycle. (4) Docstrings in
  `lib/views.py` describing the lifecycle updated: statusless (release-pending,
  merged-by-location once visible on the integration branch) → `shipped`
  (released); `merged` = accepted legacy synonym of statusless.
- **Depends on:** none
- **Artifacts consumed:** this plan; `lib/views.py`; `bin/prawduct-hook`
- **Deliverables:** `lib/views.py`, `bin/prawduct-hook`, tests in
  `tests/test_views.py`
- **Tests:** statusless tagged entry WITH `scope=` is enumerated by
  `collect_release_pending_scopes` (new); shipped/merged enumeration unchanged
  (regression); statusless UNtagged (no tag line) never enumerated; diagnose
  label reworded (existing statusless-diagnose tests updated, coverage not
  weakened); stamp-merged subcommand still stamps AND emits the deprecation
  notice on stderr (existing integration tests extended, not deleted).
- **Acceptance criteria:** `python3 -m pytest -q` passes; `prawduct-hook
  regen-views --check` against this repo's real change-log exits 0 with no new
  unexplained warnings.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (inferred `chunk` mode) and blocking findings
     resolved
  3. Committed and Context updated in Status

### Chunk 02: Flow prose cascade — PR skill, release process, template

- **Description:** Remove every instruction that requires a post-merge commit
  on the integration branch; move the bookkeeping into the PR. (1)
  `skills/pr/SKILL.md`: delete merge-flow step 6 (stamp + chore commit),
  renumber; rework the build-plan step's trunk case — plan retirement, the
  `status=shipped` entry, and regen-views output ride IN the closing PR (new
  Create-flow guidance "the PR carries its own bookkeeping"), post-merge steps
  reduce to local gitignored evidence cleanup; keep a convergent catch-net
  ("bookkeeping found missing after merge folds into the NEXT PR — never a
  dedicated housekeeping PR, never a direct push to a protected base"). (2)
  `docs/release-process.md`: "Change-log `status=` values" section rewritten —
  statusless = expected release-pending state; `merged` = accepted legacy
  stamp, no longer applied by any flow; step-number cross-refs fixed; release
  step 3 wording kept ("every unreleased entry, statusless OR merged"). (3)
  `templates/change-log.md`: comment block rewritten to the real lifecycle
  (statusless in the feature PR → flipped `shipped` at release-prep on gitflow,
  or written `shipped` in the closing PR on trunk); stale
  `in-progress | deferred` status roster corrected to match
  `VALID_STATUS_VALUES`. (4) `methodology/planning.md` merge-flow step-number
  cross-ref updated. (5) `skills/backlog/SKILL.md`: the one clause tying the
  change-log `shipped` flip exclusively to release-prep gains the trunk-repo
  case (closing PR). (6) `tests/test_pr_reviewer.py` flow guardrail tests
  updated to the new step structure (same protections, new numbering).
- **Depends on:** Chunk 01
- **Artifacts consumed:** this plan; `skills/pr/SKILL.md`;
  `docs/release-process.md`; `templates/change-log.md`;
  `methodology/planning.md`; `skills/backlog/SKILL.md`
- **Deliverables:** the five prose files above + `tests/test_pr_reviewer.py`;
  this branch's change-log entry (statusless, scope=single-pr-bookkeeping —
  its own first consumer)
- **Tests:** flow guardrail tests in `tests/test_pr_reviewer.py` pass against
  the new step structure; full suite green; repo-wide grep for
  `stamp-merged` finds only the deprecated command's own code/tests, the
  release-process legacy note, and historical records (CHANGELOG, archived
  backlog/change-log entries).
- **Acceptance criteria:** `python3 -m pytest -q` passes; no framework flow
  instructs a commit to the integration branch outside a PR (verified by the
  grep sweep above).
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass; change-log entry written
  2. Committed, then `/prawduct:critic cumulative` run against
     `merge-base...HEAD` (this chunk's review IS the PR gate) and blocking
     findings resolved
  3. Chunk marked done in Context

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook stamp-merged` and see the
deprecation notice; run `regen-views --check` on a repo with statusless
tagged entries and see their scopes enumerated without any stamp.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` passes; PR
via `/prawduct:pr` after Chunk 02's one `/prawduct:critic cumulative` passes,
when the user asks.

- After Chunk 01: chunk-mode review — the enumeration change is the keystone.
- After Chunk 02: cumulative review over `merge-base...HEAD`
  (`Type: cumulative-final`).
