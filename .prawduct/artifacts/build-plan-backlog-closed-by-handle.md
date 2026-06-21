---
artifact: build-plan
version: 2
scope: backlog-closed-by-handle
depends_on: []
last_validated: 2026-06-21
---

# Build Plan — Reconcile the `closed-by:` handle contract (BKL-9K4T)

**Problem.** The backlog `closed-by:` field is contracted as `<chunk-id|tag>` —
an identifier that exists *before* the commit. v2.1.6 (`backlog-ship-in-pr`) then
told builders to archive an item *on the branch that closes it*
(`closed-by=<scope>`), but that rule only updated the "When to mark shipped"
prose; the **contract text** that defines the field — the item-shape line, the
`update … closed-by` step, and the template legend — still said `<chunk-id|tag>`
and never said what handle to use for **non-chunk work** (a standalone
refactor/chore committed directly, with no chunk id or release tag). A builder
with no chunk id reaches for the only stable handle left — the commit SHA — which
a commit cannot contain (a commit can't hold its own final SHA) and which a
`git commit --amend` rewrites, so the ref either is impossible to place in-commit
or dangles. The escape is an extra "fix closed-by" commit — exactly the
separate-bookkeeping-commit churn `backlog-ship-in-pr` set out to remove.
Surfaced as an upstream report (filed from the Hallucinote repo, originally hit
in `puzzles`), triaged to **BKL-9K4T**.

**Success.** Every contract site states the same rule: `closed-by` is a handle
that exists *before* the commit recording it — a chunk id, the branch/feature
**scope** name, or a release/change-log tag — and is **never a bare commit SHA**
(can't sit in its own commit; dangles on `--amend`) **nor an unassigned PR
number** (doesn't exist until the PR opens). For non-chunk work the prescribed
handle is the **branch/scope name**, which is resolvable on-branch and survives
amends/rebases — so the archive stays atomic with the merge with no follow-up
commit. The `update` step warns when handed a bare SHA and records the scope name
instead.

**Out of scope.** Any code change — nothing in `lib/`/`bin/` parses `closed-by`;
it is human-readable provenance, so this is a guidance/contract fix only.
Rewriting the `closed-by` values of already-archived items (historical, mixed
PR#/scope/SHA forms — fine as-is; the contract governs new closures). The
change-log `merged→shipped` two-stage and the `develop→main` release flow
(untouched — those legitimately batch at release). The companion inbox report
about backlog-accuracy / closed-but-not-removed (separate triage).

## Requirements Confidence

**Level:** High — a small doc-only contract reconciliation with no code surface.
The report supplies a verified fix-shape, and v2.1.6 already adopted the
branch/scope handle in one place; this chunk only propagates that same handle to
the field's own contract definition (Principle 13 — Coherent Artifacts: a changed
rule must cascade to the definition it rests on).

## Status

- [ ] Chunk 01: Reconcile the `closed-by` contract + bare-SHA/amend warning

Context: chunk 01 BUILT and review-complete (2026-06-21, single docs work cycle,
branch `feature/backlog-closed-by-handle` off `develop`; the sibling
`feature/hot-path-git-batching` bundle stays merge-ready and untouched). Cumulative
Critic clean (0 blocking / 1 warning / 1 note, both resolved — `refs:` archive-path
corrected; test state confirmed below). BKL-9K4T archived on-branch with
`closed-by=backlog-closed-by-handle` (dogfooding the prescribed handle). Tests:
1351 pass; the lone failure (`test_changelog_has_current_version_entry`) is a
**pre-existing develop-baseline** issue — the v2.1.6 `CHANGELOG.md` headline
(commit `30a4875`) is stranded on `feature/hot-path-git-batching` and never reached
develop, so it is unrelated to this doc-only diff and self-resolves when hot-path
merges. `views_enabled: true` — the checkbox flips at release via the
`scope=backlog-closed-by-handle` change-log tag.

## Chunks

### Chunk 01: Reconcile the `closed-by` contract + bare-SHA/amend warning

- `skills/backlog/SKILL.md`:
  1. "When to mark shipped" rule (the `closed-by=<scope>` clause): clarify
     `<scope>` is the branch/feature or chunk name — a handle already present on
     the branch, not a SHA/PR# assigned later.
  2. Item-shape `closed-by:` definition: a chunk id, branch/scope name, or
     release tag; a handle that exists *before* the commit; never a bare SHA.
  3. `update … status=shipped`: broaden the accepted handle, add the
     bare-SHA/`--amend`-dangle warning, prescribe the branch/scope name for
     non-chunk work, and substitute-and-note when handed a bare SHA.
- `templates/backlog.md`: the `closed-by:` legend line matches the contract
  (handle exists before the commit; never a bare SHA or unassigned PR#).
- **Type:** doc-only (skill prose is behavioral, so Critic review still applies).
- **Done when:**
  1. The four contract sites carry the reconciled rule; `tests/test_backlog_parser.py`
     and the methodology/skill content tests stay green (no content assertion broken).
  2. Reviewed by `/prawduct:critic` (cumulative — this scope ships in one PR).
  3. BKL-9K4T archived on this branch (`status=shipped closed-by=backlog-closed-by-handle`)
     — dogfooding the very handle this chunk prescribes.
  4. Committed and chunk marked `[x]` (via the `scope=` change-log tag at release).
