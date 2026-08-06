# Release plan — v3.2.6

**Cut from:** **whole-develop at Phase 2** — the tip as of the promotion, not a pinned commit.
`K withheld = 0` selects whole-develop promotion, which makes the tip the answer.
**Previous release:** v3.2.5

## Version decision

**Patch bump, 3.2.5 → 3.2.6.** Owner-directed ("+0.0.1"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded, because this release has exactly the shape v3.2.5 recorded and declined to call minor,
and consistency between the two is the point.** It adds a new hook subcommand (`critic-discard`)
and a **pre-dispatch refusal** — a path that previously accepted a dispatch now rejects it. Under
the observed (unratified) minor tier — *a substantial new capability or a subsystem going live* —
neither qualifies:

- `critic-discard` is a **recovery hatch, not a capability.** It exists only so the refusal below
  has a remedy that reaches every state it can produce. Nothing calls it in the normal path; it
  gates nothing.
- The refusal **is the fix, not a new bound.** The prior behaviour was to archive an in-flight
  review's partials, overwrite its manifest, and report success — losing completed findings
  silently. Refusing is what makes the reported success true. Nothing an adopter depends on changes
  shape: a dispatch with no review in flight behaves exactly as before, and an *orphaned* leftover
  from a dead review is still swept.
- No persisted format changes and no gate semantic breaks.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| critic-concurrent-dispatch | ships | |

`K withheld = 0` → **whole-develop promotion** (runbook Phase 2 steps 14–20), not the pruned path.

### Blocker liveness — vacuous by construction, not skipped

This repo is on the GitHub Issues backlog backend (`backlog_service_repo: brookstalley/prawduct`),
so `.prawduct/backlog.md` is frozen history and blocker liveness cannot be read from it — the
condition that makes `check-releasability` refuse with `cannot-verify-blockers:`. It does not fire
here for the same reason it did not at v3.2.3 or v3.2.5: **the gate reads blocker liveness only for
rows that name a blocker, and no row here does.** The one scope ships, so there is no withholding
decision whose premise could have expired.

### The release-pending set — how it was derived

Per runbook step 2, the boundary (topmost tag line carrying `release=`) is `.prawduct/change-log.md:54`
(`release=v3.2.5`). **One** statusless entry sits above it (`:8`) and none below, carrying
`scope=critic-concurrent-dispatch` — matching exactly what `check-releasability` enumerated. The
entry carries a `scope=` key, so there is no unscoped-and-invisible entry.

The per-candidate **code test** was run rather than inferred from position:

| Probe | v3.2.5 | develop |
|---|---|---|
| `critic-discard` in `plugin/bin/prawduct-hook` | 0 occurrences | 3 |
| `active_dispatch_refusal` in `plugin/lib/critic_consolidate.py` | 0 occurrences | 3 |

Both absent from the previous release's tree ⇒ genuinely unreleased.

*(Counts are a measurement of one tree on 2026-08-05, not a property of the repo.
`check-releasability` is the live answer.)*

**Also carried, and deliberately not a classification row:** `07c785c`, the runbook correction that
has sat on `develop` since the v3.2.5 promotion. Doc-only, no change-log entry, therefore not
release-pending and not a scope. It rides the whole-develop promotion as content.

## Consumer-facing headline

> A second Critic dispatch can no longer destroy the review already running — and every state it
> refuses now names a command that clears it.

## What ships

**`critic-concurrent-dispatch` (Chunks 1–2) — the whole release.** `begin_review` archived the
partials directory and overwrote the manifest unconditionally, with no check for an in-flight
review. Dispatching over one erased completed findings, and left the displaced review's reviewers
running so their partials landed in the *new* review's directory — where a partial bound only to
`commit_reviewed` is indistinguishable from one written for it, and consolidates as a review that
never read those files.

Observed live three times: 2026-07-29 (manifest overwrite, chunk attribution lost), 2026-07-30 (two
single-pass reviews contending for one `reviewer.json`; the loser's BLOCKING finding silently
discarded), and 2026-08-05 (a completed three-reviewer cumulative carrying two blocking findings,
swept a minute after its last partial landed — no fact, no ledger anchor). Reported from a product
repo (**#602**, near-duplicate of **#171**).

- **The guard** refuses on a live critic-active marker **or a complete roster at any age.** The
  second condition is the one the incidents needed: age tells you whether more reviewers are
  coming, not whether findings already written are worth keeping.
- **The escape.** `prawduct-hook critic-discard` — archive-first, never a bare delete, and
  deliberately not folded into `critic-end`, which is what an agent reaches for whenever a review
  looks dead. A guard that cannot be escaped is its own outage, and the first version of this fix
  was one: consolidation fail-closes *without* removing partials, so a failed consolidate stranded
  a complete roster nothing could clear. Its own cumulative review caught that.
- **The dispatch path stopped sweeping the marker it reads** (`review_active(sweep=False)`) — the
  Stop hook's abandoned-review branch is gated on marker presence and prints the manual-recovery
  advice, so a sweeping read would have deleted the signal producing those instructions.

**Not a v3.2.5 regression, and this is worth stating in the notes** because it was reported as one
and three consumer sessions hit it in the days after that release. `_archive_leftovers` is in the
3.2.3 / 3.2.4 / 3.2.5 trees alike, and `cmd_critic_begin` carried no guard in any of them. Latent
across at least three releases; nothing needed reverting.

**What is deliberately NOT in this release.** Part 2 of the defect — binding a partial to a
`review_id` rather than only to a commit — stays open on #602/#171, together with the state-machine
reachability test, which is sequenced *after* it because the binding changes the states it would
pin. This release closes the reachable path; part 2 is what makes the class impossible.

## Runbook step 11 — `active_build_plan`

The pointer is already `null` on `develop` and this release's `regen-views` flips both chunks of
`build-plan-critic-concurrent-dispatch.md` to shipped. Nothing to clear and nothing to repoint —
`null` is the honest value when no work is in flight, per the same reasoning v3.2.5 recorded.

**Known consequence, chosen rather than discovered** (identical to v3.2.3 and v3.2.5): with the
pointer null, `has_build_plan` is False, which downgrades the reflection gate to advisory and skips
the Stop-hook Critic gate. The prep commit and the Phase 2 promotion therefore run ungated.
Accepted for the same reason: Phase 2 authors nothing, its real protections are the runbook's
content-identity and version checks, and feeding the gate a false input is the stale-pointer shape
that has already caused three wrong verdicts.

## Ship-time actions

- **Leave #602 and #171 OPEN.** This release ships part 1 only. Both issues carry part 2 and the
  state-machine follow-up; closing either would lose that scope.
- Confirm **#603** (the PR) shows as merged — it targets `develop`, not the default branch, so
  nothing auto-closes.

## Owner release gate

**None declared for v3.2.6.** No go-live, no persisted-format change, no advisory whose audience
widens, and one scope.

**Residual risk, stated:** the refusal is the one change that can turn a previously-succeeding call
into a failure. Its blast radius is bounded on both sides. A **false positive** costs a refused
dispatch, and the refusal names a working remedy for every state it can produce (that property is
the subject of Chunk 2, and of four tests watched failing under mutation). A **false negative**
restores the status quo ante, which is the behaviour every prior release shipped. The prior
behaviour on the exact path being refused was silent loss of a completed review, so the asymmetry
runs strongly toward refusing.

**Verified end-to-end during the release itself, not only by suite:** four Critic rounds ran against
this branch through the new guard, including one dispatched while an earlier review was live — the
whole mechanism was exercised on the release it ships in.
