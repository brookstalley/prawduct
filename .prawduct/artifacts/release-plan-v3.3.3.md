---
artifact: release-plan
version: 1
release: v3.3.3
last_validated: 2026-08-11
---

# Release plan — v3.3.3

An expedited patch cut same-day on v3.3.2, carrying one scope. Nothing withheld.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| retired-hook-subcommands | ships | |

## What ships

One fix, for a defect v3.3.2 introduced and shipped.

**`build-index` and `user-prompt-submit` are callable again, inert.** v3.3.2 deleted both from the
binary *and* their registrations in `hooks.json` in one commit. Unregistering them was right;
deleting them was not. The harness pins a plugin version **per project** and updates those pins
lazily, then resolves the binary independently of the registration — so for one update cycle a repo
runs a pre-3.3.2 `hooks.json` against a 3.3.2 binary, and that pairing invokes names the dispatcher
no longer has. Usage text on stderr, exit 1, surfaced as `SessionStart:clear hook error` at every
session start and, through `UserPromptSubmit`, once per prompt.

Both now exit 0 silently, write nothing, and tolerate unknown flags and stdin payloads. `hooks.json`
still does **not** register them — that half of v3.3.2 was correct and is pinned so the repair
cannot resurrect the hooks.

`regen-views` and `stamp-merged` join them in `_EPHEMERAL_SAFE_COMMANDS`. They carried the same
disposable-worktree gap behind the same false "exits 0 everywhere" docstring since they were
emptied; the fail-closed pre-dispatch guard refused all four with exit 1 inside a
`.claude/worktrees/agent-*` tree. One classification, not four decisions.

## Why a patch

A defect fix with no new capability and no gate semantics changed. The two restored commands do
nothing — they exist so a stale registration gets exit 0 instead of a usage error. Conservative
versioning norm (`operational-spec.md` § Direction, 2026-07-17) reads this as a patch without
argument, and no minor-tier signal applies: nothing goes live, no subsystem changes.

## Why expedited rather than riding the next promotion

v3.3.2 is tagged and live. Every product repo that has not yet updated its pin hits this at session
start and once per prompt, and the only exit is a release carrying the fix. Nothing is lost while a
repo is stranded — the two failing hooks are hooks with no work left to do — but the noise is
continuous and it looks like governance breaking.

## Two normative questions left OPEN for the owner

Neither is settled by this release, and both are recorded rather than decided by side effect.

1. **Should `[[harness-only-removal-is-not-a-major]]` require an inert-retention window?** Its
   warrant — that these two "had exactly one caller … so no caller could observe the gap" — was
   falsified in the field the same day it was ratified. The tier permission it actually grants
   (harness-only removal need not spend a major) is untouched; what is withdrawn is the
   atomic-update reasoning. v3.3.3 implements the reading *unregister now, delete only when no
   supported install still registers it*, but the code is the repair, not the ratification.
   Recorded at `api-contract.md` § Direction.

2. **Should the deprecation norm gain a *silent-when-the-caller-is-a-registration* clause?** The two
   restored commands print nothing on either stream, which "Deprecation is signalled, not silent"
   forbids as written. Recorded as a dated departure beneath the clause rather than by softening it
   — softening was the first attempt and the PR reviewer correctly called it amend-to-match-own-code.
   If the answer is no, the remedy is to make them warn on stderr; never stdout, which a hook
   injects into the model's context.

**Related, and worth the owner's attention alongside #1:** backlog #120 (ref-pinned marketplace
installs never update) *falsifies the retention rule's own premise* — "by which point no supported
install still registers it" never arrives for a pinned install, which turns the one-cycle window
into an indefinite one.

## Verification

- `check-releasability --release v3.3.3` → releasable, 1 shipping, 0 withheld
- Suite green; the count lives in `.prawduct/.test-evidence.json`
- Review: cumulative (2 blocking, both fixed) → verify-resolutions (0 findings) → PR review
  (0 blocking; 1 warning fixed, 1 note accepted)
- The reported defect reproduced against the shipped 3.3.2 binary before the fix and re-measured
  after — including the ephemeral-worktree case, in a real ephemeral worktree, with the refusal path
  proved live in the same fixture

## No build plan

`check-releasability` warns that this scope ships with no build-plan file. That is the correct
outcome, not an omission: a two-file bugfix is *small* under `building.md`'s size scaling, which
calls for understand → build → verify → update artifacts, and reserves a build plan for medium+
work. Recorded here so the advisory is dispositioned rather than ignored.
