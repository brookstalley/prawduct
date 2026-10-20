---
schema: 1
type: feature
scope: change-log-fragments-wave-2
date: 2026-10-20
title: Onboarded repos can record changes as fragments, and existing ones have a migration that works on real logs
closes: [brookstalley/prawduct#1023]
---
#1023, wave 2 of #1012. Wave 1 moved prawduct itself onto `.prawduct/changes/` fragments; this
wave makes a fragments-only repo a correctly read repo and gives every onboarded repo a path onto
it. Plan: `.prawduct/artifacts/build-plan-change-log-fragments-wave-2.md`.

### Chunk 01: a fragments-only repo reads correctly
- `change_log_archive.load_all_text` reads an absent live log as empty for every history reader
  (`release_readiness`, `plan_backfill`, `record_lint`); only an unreadable one is `None`.
- `archive_would_be_ignored` keys on whichever change record git tracks: the live log or the
  fragment directory.
- The `gitattributes` probe advises removing `merge=union` once a repo records fragments and no
  legacy entry is pending; legacy repos still get the advice to add it. This repo drops its
  `.gitattributes`.
- `init-product` scaffolds `.prawduct/changes/.gitkeep` and no `change-log.md`, and leaves a repo
  already on the legacy log alone.

### Chunk 02: existing repos migrate
- `migrate-change-log` converts what real logs carry: tag keys a fragment has no field for become a
  `Legacy tags:` narrative line, pending entries sharing a scope merge into one fragment, dash
  headers parse, more type synonyms map, and a missing type takes an owner-chosen
  `--default-type`, listed per entry. A log with nothing pending still adopts fragments.
- It refuses (`plugin-pin-too-old`) when the committed install reference pins a release older
  than v3.7.2.
- `/prawduct:doctor` offers it (check #22); `/prawduct:migrate` runs the same procedure as a second commit for a repo leaving file-sync.
- PR Step 1c answers `fragment-present-untracked` from the on-disk fragments when git ignores
  the directory, and both its remedies name the un-ignore pattern.

### Chunk 03: trunk PRs own their change record
- `change_fragments.branch_change_record` is the one owner of "this PR's change record": a
  fragment the branch added, or an archive entry it added by cutting its own fragment.
  `scope_change_record` answers after the merge. Step 1c (`fragment-cut`), the reviewer payload
  and the new `prawduct-hook change-record` (the merge-time close) read through them.
- PR Step 1d tells a versioned trunk branch to cut its own fragments; an unversioned trunk keeps
  them pending.
- Plugin prose that still described the legacy log as the only record now says "change record".

## Consumer note
Products can now record each change as its own file in `.prawduct/changes/` instead of editing the shared `change-log.md`, so two branches no longer conflict over the change record. New products start that way. For an existing product, `/prawduct:doctor` offers the move and makes it with your approval, as one revertible commit. Entries with no type need one `--default-type` you choose, and the dry run shows every guess first. On a trunk-based product that tracks versions, each PR cuts its own change record into the archive as it ships.
