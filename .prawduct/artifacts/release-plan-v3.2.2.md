# Release plan — v3.2.2

**Cut from:** `origin/develop` @ `f5225dd` (PR #146 merged 2026-07-30T21:29Z)
**Previous release:** v3.2.1

## Version decision

**Patch bump, 3.2.1 → 3.2.2.** Owner-directed ("+0.0.1"), and consistent with the ratified norm
(`operational-spec.md` § Direction, 2026-07-17): *versioning is conservative — a small feature is a
patch bump, not a minor-per-feature.*

**Recorded because the call is arguably close.** This release changes two shipped defaults every
onboarded repo inherits — the Critic's roster derivation and a line in the always-injected session
digest — and the runbook's unratified precedent treats "a substantial new capability or a subsystem
going live" as a minor. It is a patch because nothing goes live and no gate semantics or persisted
format breaks: the roster change is a refinement of an existing rule that **cannot reduce review for
any repo**, and the digest line is guidance. No behaviour an adopter depends on changes shape.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| record-mechanization | ships | |

`K withheld = 0` → whole-develop promotion (runbook Phase 2 steps 14–20), not the pruned path.

**Also shipping, unscoped:** the learnings-compaction entry (`type=fix`, no `scope=` — it closed
`LRN-4K8T`, a `stage: ready` chore with no build plan, so there is no plan roster for it to name).
The releasability gate enumerates by `scope=`, so an unscoped entry is invisible to it and must be
tagged by hand at Phase 1 step 3 along with the scoped ones. Flagged here so the tagging sweep does
not miss it — this is exactly the "an unlisted scope ships unexamined" shape Phase 0 exists to catch,
one level down.

## Consumer-facing headline

> Review depth is now a risk question rather than a file count — and no repo is reviewed less than
> before.

## Adopter disclosure owed in the release notes

Carried from the PR review (NOTE, `rev` PR #146). The roster change **cannot reduce** review depth
for any repo: undeclared repos hit the framework-shaped defaults, then the unchanged 5-file fallback.
But depth can silently go **up** — a 2-file diff touching a product's own `skills/`, `bin/*hook*`, or
a contract path listed in `boundary-patterns.md` now draws the three-reviewer coordinator. The only
disclosure today lives in `plugin/templates/project-state.yaml`, which **existing repos never
re-read**. `plugin/CHANGELOG.md` (Phase 1 step 10) is the surface that reaches them; the discovery
and registry half is filed as `CRT-8K6M`.

## Runbook departure #2 — `active_build_plan` NOT cleared

Phase 1 step 11 says set `active_build_plan:` to `null`. **Not done, deliberately.** That step
assumes the release completes the active plan. It does not here: `build-plan-record-mechanization.md`
ships Chunks 02, 03 and 04 in this release (`regen-views` flipped exactly those three) and **Chunk 05
— the change-log ledger spike and go/no-go — is unbuilt.** Clearing the pointer would orphan a live
plan mid-flight and send the next session looking for work that has no anchor.

The Merge Flow's gitflow branch already says to RETAIN plan and pointer until the release, and the
release is what flips shipped chunks — it does not follow that a *partially* shipped plan loses its
pointer. Reading step 11 literally would delete a pointer the very next session needs.

Worth fixing in the runbook: step 11 should be conditional on the plan having no unchecked chunks
left. Not fixed here — a runbook edit mid-release is its own change needing its own review.

## Runbook departure, recorded

Phase 1's prerequisite is "you're on `develop`". `develop` is checked out in a separate worktree
belonging to another session, so prep was done from a **detached HEAD at `origin/develop`** and
pushed with `git push origin HEAD:develop`. The end state on `origin` is identical, and Phase 2
step 15 reads `origin/develop` explicitly rather than the local branch ref, so no downstream step is
affected. The local `develop` ref stays behind until that worktree pulls — expected, not a defect.
