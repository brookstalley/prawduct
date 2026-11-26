---
schema: 1
type: feature
scope: boundary-review-per-release
date: 2026-11-25
title: A repo can move its boundary review to the release with boundary_review per_release
closes: [brookstalley/prawduct#1232]
---
A repo that releases several times a day pays a boundary review at every PR, even for a small
feature whose inner review already read all of it (#1223), and a fix for a non-blocking finding
buys its own verify round (#1222). Both wait on one mechanism: a boundary review that runs once per
release batch, and a release check that blocks until it has. This scope builds it behind an opt-in
key. The stage-keyed review norm gains an amendment the owner confirmed on 2026-11-25: the boundary
review for eligible work is moved to the release, never skipped.

### Chunk 01: the boundary_review key, read from the integration branch
`boundary_review:` in `project-state.yaml` takes `per_pr` (the default) or `per_release`, read by one
reader, `review_lane.boundary_review_policy`. A PR's policy is the value at the merge-base with the
integration branch, so the branch that adds `per_release` is still judged `per_pr`: a governance
change cannot supply its own authority. A branch may drop the key, which is the stricter direction.
The release check's reader reads it at the integration branch's tip. Anything but exactly
`per_release` reads `per_pr`. The key is documented in `docs/project-state-keys.md` and hinted in
the state template, and the NFR amendment is recorded beneath the clause, whose words stay as
ratified. `per_release` is read and changes nothing yet: no gate, inference or review consults it
until the later chunks of this scope land.

### Chunk 02: a release anchor, and every judgeable commit since it
Wave 1's `check-boundary-coverage` found merges only through the fragments they added, so work
committed on the base without a fragment was invisible to it, and a release check that blocks on
its answer would have passed that work unread. The op now finds the release anchor, the nearer the
tip of the newest first-parent commit adding a release file under `.prawduct/releases/` and the
oldest first-parent commit containing the merge-base of the base and the newest version tag. The
second serves repos that write no release files, including those that tag each release on a merge
into `main` the integration branch never contains: the merge-base is the integration commit that
was released. It then classifies every
first-parent commit after the anchor that changes a judgeable file, unioned with the fragment join
and de-duplicated by commit, so a scope a pruned release withheld stays classified. One `git log`
lists the whole walk. A repo with neither anchor gets the fragment join alone, and the report says
there was no anchor. A new covered class, `release-bookkeeping`, is a single-parent commit whose
judgeable changes are all files `release_version_files:` declares at its parent: the reopen commit
after a cut, which read `direct` before. An undeclared repo's fallback layout never qualifies. A
merge whose branch changed nothing judgeable but whose merge commit edits a judgeable file now reads
`uncovered`, not `no-judgeable`, because the walk reaches such merges. The count line names the
anchor and how many commits the walk found. It is still advice, and `check-releasability`'s exit is
unchanged.

## Consumer note
A new opt-in key, `boundary_review:` in `.prawduct/project-state.yaml` (see
`/prawduct:methodology project-state`). At this point `per_release` is read and changes nothing;
leave it unset. Nothing changes for a repo that does not set it.

`check-boundary-coverage` (and the count line `check-releasability` prints) now also lists every
judgeable commit since your last release, including work committed on the integration branch
without a change fragment, so expect more entries and a count line that names the release anchor.
`--json` adds `anchor`, `no_anchor_reason` and each entry's `source` (`fragment`, `walk` or
`both`), and a new covered class, `release-bookkeeping`, for a commit that changes only the files
you declare in `release_version_files:`. Neither command's exit code changes.
