# Release plan — v3.2.3

**Cut from:** `origin/develop` @ `d9fe20b` (PR #531 merged 2026-08-01)
**Previous release:** v3.2.2

## Version decision

**Patch bump, 3.2.2 → 3.2.3.** Owner-directed ("+0.0.1"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded because a minor is arguable here and was not taken.** This release carries the largest
consumer-visible code delta since v3.2.0 — `audit_learnings_cmd.py` (+428), `backlog/migrate.py`
(+234), `critic_consolidate.py` (+175), `views.py` (+130) — and it adds a genuinely new capability
(`superseded-by=` retirement in `audit-learnings`). It stays a patch because **nothing goes live and
no persisted format or gate semantic breaks**: `superseded-by=` is an additive metadata key that
fails closed on every ambiguity, the two new delivery sites *print* rather than gate, and the
backlog service remains opt-in per repo. No behaviour an adopter depends on changes shape.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| v3.2.0-golive | ships | |
| learnings-firing | ships | |
| backlog-service-v1 | ships | |
| record-mechanization | ships | |

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

**Status at time of writing: PENDING.** Owner elected to hold at the Phase 1 checkpoint —
`origin/develop` fully prepped, nothing published. Record the result in
`.prawduct/operator-verification.md` as this release's go/no-go evidence, naming which sibling repos
were exercised and what was checked, then run Phase 2.

## Runbook departure — `active_build_plan` NOT cleared

Phase 1 step 11 says set `active_build_plan:` to `null`. **Not done, deliberately** — the same
departure recorded at v3.2.2, for the same reason and against a different plan. The pointer holds
`artifacts/build-plan-v3.2.0-golive.md`, and that plan is **not** completed by this release: Chunk 06
ships here, but Chunks 01, 05, 07, 08 and 09 remain unchecked (07 and 08 were deferred out of v3.2.0
and never re-cut). Clearing the pointer would orphan a live plan mid-flight.

Step 11 should be conditional on the plan having no unchecked chunks left. Filed rather than fixed
here — a runbook edit mid-release is its own change needing its own review, and this is now the
**second consecutive release** to record the identical departure, which makes it debt rather than a
one-off.
