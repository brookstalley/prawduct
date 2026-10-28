---
schema: 1
type: feature
scope: consumer-digest
date: 2026-10-26
title: One declared changelog, read at Phase 0 and written at the cut
closes: [brookstalley/prawduct#733]
---

#733, with #1069 folded in. Every product on change fragments had to write a `## Consumer note`,
but only prawduct's own cut delivered it. The Phase 0 check and the cut were hard-coded to
`plugin/CHANGELOG.md` and to prawduct's open-section procedure, so in any other repo the note
reached only the change-log archive.

The owner chose changie's identity model over finding a section by heading. A product declares
`consumer_digest:` in `.prawduct/project-state.yaml`, and prawduct declares its own. At the cut,
the shipping notes are rendered under a generated heading and the headline from
`.prawduct/release-headline.md`, written to `.prawduct/releases/vX.Y.Z.md`, and inserted into the
changelog as a new section above the newest release. The cut never searches for or renames a
section, and changes no other byte. The release file is the record that the release is cut.

- **Chunk 01:** the #733 design was rewritten for the release-file model, with requirement
  amendments A1–A6 (builder, owner can veto).
- **Chunk 02:** new `plugin/lib/consumer_digest.py`, the one home for the declaration, version
  headings, the text model, insertion, rendering and the headline reader.
  - The declaration's path is confined to the repo, and refuses every filesystem spelling of
    `.git` and `.prawduct`: case-folded, HFS+ ignorable characters, NTFS trailing dots and short
    names.
  - `core.write_all_or_none` is byte-exact on write and on rollback, so a CRLF file is no longer
    re-line-ended by a failed write.
  - `TestPrawductGolden` pins prawduct's changelog bytes against today's cut.
- **Chunk 03:** Phase 0 reads the declaration.
  - It warns on a missing or heading-first headline file, and on a section already naming the
    release.
  - It steps aside once the release file exists.
  - An unreadable state file is invalid, not undeclared.
  - The coverage advisory and the open-section reader are deleted, and a pin keeps them deleted
    across every module.
- **Chunk 04:** the cut writes the release file and inserts it, in one transaction with the
  archive.
  - Refusals: `digest-declaration-invalid`, `digest-missing`, `digest-unreadable`,
    `marker-missing`, `release-in-changelog`, `no-headline`, `releases-ignored`,
    `release-already-cut`.
  - Re-runs decide what is held by entry identity, not scope name.
  - The dry run prints the exact section.
  - Releases are dated by local date.
  - `wrong-section` and the text-search idempotency are retired.
- **Chunk 05:** prawduct's own procedure.
  - `plugin/CHANGELOG.md` carries no open `-dev` section.
  - `test_changelog_matches_the_current_version` replaces the old banner contract: a released
    version has its section, and a prerelease has none.
  - The unreleased-claims scan reads pending consumer notes.
  - The release runbooks, `release-process.md` and `api-contract.md` describe the new flow. The
    GitHub Release body now comes from the release file.
- **Chunk 06:** the product surfaces. `project-state-keys.md` documents `consumer_digest:`, the
  template hints it, the fragment template stops over-promising, `project-structure.md` lists
  the new files, and DV6 is amended.
- **Chunk 07:** an end-to-end run on a scratch product with a CRLF, BOM-prefixed Keep a
  Changelog file (two releases, a re-run and a late fragment), and prawduct's own cut run on a
  throwaway copy of this repo.
- **Boundary review fixes:**
  - The cut's changelog refusals are one list, `consumer_digest.preflight`. The cut raises from
    it and Phase 0 warns on all of it, so Phase 0 now also warns on `marker-missing` and
    `releases-ignored`.
  - `retired-claim-survives` treats release files and the declared changelog as history.
  - `write_all_or_none` reports a rollback it could not complete, and every caller's refusal
    says so rather than claiming every file was restored.
  - A release that ships nothing says it kept the headline file.
  - The release runbook treats the headline file as never committed.

## Consumer note
**Release notes now reach your own changelog.** Declare `consumer_digest:` with your changelog's
`path` in `.prawduct/project-state.yaml`. From then on, `cut-change-log --apply` writes each
release's fragment notes into it as a new section above your newest release, and keeps a copy in
`.prawduct/releases/<version>.md`. No other byte of the file changes, line endings included. The
cut never renames a heading, so a tool that dates or tags releases can run after it.
- Layouts: `paragraphs`, `bullets` or `by-type` (Keep a Changelog subsections), with a heading
  and an entry template of your choice.
- An optional headline goes in `.prawduct/release-headline.md`. Set `headline: required` to have
  the cut insist on one.
- The dry run prints the exact section, which you can paste into a release PR as its notes.
- Without the key nothing changes, except that the cut now says how to turn it on.
- Full reference: `/prawduct:methodology project-state`, under `consumer_digest`.
