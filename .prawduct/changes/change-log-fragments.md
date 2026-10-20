---
schema: 1
type: feature
scope: change-log-fragments
date: 2026-10-19
title: prawduct records each change as its own fragment file, and the release cut ships them
---
#1012, wave 1. Each branch used to edit two shared files: `.prawduct/change-log.md` and the open
`plugin/CHANGELOG.md` section. That cost merge conflicts (#1019), a `merge=union` driver that
resurrects archived entries (#857), hand-written tags nothing validated, and consumer notes written
in bulk at the cut. Prawduct now records each scope as one validated file in `.prawduct/changes/`.
Plan: `.prawduct/artifacts/build-plan-change-log-fragments.md`; design:
`documentation/issues/1012-design.md`.

### Chunk 01: the format
- `lib/change_fragments.py` is the format's single owner: parse, validate (a stable code per
  problem), render as an archive entry and as consumer text.
- Schema: `schema: 1` (a higher value is refused), `type` from a closed set of seven, `scope` equal
  to the filename stem, `date`, `title`, optional `closes` (backlog item IDs) and `reopens`, and a
  required `## Consumer note` holding text or `none: <reason>`.
- Template: `plugin/templates/change-fragment.md`.

### Chunk 02: the readers and the PR gate
- `release_readiness.pending_scopes` owns the release-pending set: legacy pending entries plus
  fragments. A scope pending in both shapes is refused.
- `check-releasability`, PR Step 1c (`check-change-log-entry`), `pr_payload` and `record_lint` read
  fragments. A fragment problem refuses by code.
- The PR body's `Closes` lines and the Merge Flow's close come from `closes:`.

### Chunk 03: the cut
- `prawduct-hook cut-change-log --release vX.Y.Z [--scope S]... [--apply]` ships the release
  plan's `ships` rows. It archives each into its month bucket tagged `release=`, puts its note
  under the open CHANGELOG section's headline (never writing the headline), and removes it.
- Withheld fragments stay pending. Every refusal writes nothing, and a re-run adds nothing twice.
- It refuses when the CHANGELOG's top section is not the release being cut, so notes never land
  in a section that is already published.
- Two branches that each add a fragment merge cleanly with no union driver.

### Chunk 04: the migration
- `prawduct-hook migrate-change-log [--apply]` converts a legacy log's release-pending entries into
  fragments, refusing by name any entry its author has to decide about.
- It ran on this repo: `testament-evidence` and `release-v3.7.1` are now fragments, and
  `check-releasability --release v3.7.2` names the same pending scopes as before.
- The scope slug now allows single interior dots, because this repo's version-named scopes need
  them.
- The release runbooks, `documentation/release-process.md`, the PR skill, the change-log template
  and the data-model and API-contract artifacts describe fragments. The July ledger proposal is
  archived as superseded.
- `plugin/methodology/building.md` no longer calls edits to the plan, the change-log or
  `.prawduct/` safe while the Critic runs: any tracked edit needs an attestation (`review-cycle.md`).

## Consumer note
Prawduct records its own changes as one file per scope in `.prawduct/changes/` and ships them with a
new release command, `cut-change-log`. **Your repo is unaffected:** every reader still accepts the
single-file `.prawduct/change-log.md`, and moving onboarded repos onto fragments is a later
release. `prawduct-hook migrate-change-log` exists for that move, but it is not yet part of
`/prawduct:migrate` or `/prawduct:doctor`.
