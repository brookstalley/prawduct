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

### Chunk 03: the release batch review, and the relax-only rule that credits it
A release that defers boundary reviews needs a review that reads what was deferred, and a rule
that credits it without loosening any PR gate. `critic-begin --mode cumulative --span release`
dispatches that review on the integration base's own checkout, at its tip, with a clean tree. Its
interval is the release anchor to HEAD. It rates the changed files of every release entry no
boundary review covered and reads the rest of the span as `files_context`. The manifest records
`span: release` with a `span_reason` naming the anchor. It refuses, naming the code and writing
nothing, off the base or off its tip (`off-base`), on a dirty tree (`dirty-tree`), with no anchor
(`no-anchor`), when the classification cannot run (`unevaluable`), or when the entries owed a read
change nothing that still differs from the anchor (`no-subject`). It exits 3 when every entry is
already covered. `--force` overrides none of these.

A release-span fact is never a coverage edge, even when it rated every file, so no PR gate verdict
can turn covered because it exists. Its blocking findings still stand at the trees it read, as every
review's do, so it can block a span standing on those trees, never cover one. The release
check credits it through a new pure rule, `coverage_algebra.batch_review_covers`: an entry is
`batch-covered` when a boundary review on the base brackets it on the first-parent line, rated every
judgeable file of the entry still changed across its interval, and no unresolved blocker stands at
its two trees. Wave 1's batch rule is the special case of a review that rated every file. The rule
now applies to work committed on the base as well as to merges. A squash merge whose PR review
spans exactly the trees it landed reads `batch-covered`, where it read `direct`. A fix committed on
the base after such a review is `batch-covered` when `verify-resolutions` and free edges alone
compose the review's tree to it and the review's blockers are resolved. A new not-covered class,
`tail-deferred`, names a fix tail the PR gate deferred to the release. The PR gate's deferral that
produces it is a later chunk of this scope.

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

`critic-begin --mode cumulative --span release`, run on your integration branch, reviews everything
since your last release that no boundary review read, and `check-boundary-coverage` then reads that
work `batch-covered`. You do not need it while `boundary_review` is `per_pr`. A squash merge whose
PR review read exactly what it landed now reads `batch-covered` instead of `direct`.
