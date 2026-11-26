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
reader, `review_lane.boundary_review_policy`. A PR's policy is `per_release` only when the merge-base
with the integration branch, the integration branch's tip and the branch all say so, so the branch
that adds `per_release` is still judged `per_pr` (a governance change cannot supply its own
authority), and so is one forked before the integration branch went back to `per_pr`. A branch may
drop the key, which is the stricter direction.
The release check's reader reads it at the integration branch's tip. Anything but exactly
`per_release` reads `per_pr`. The key is documented in `docs/project-state-keys.md` and hinted in
the state template, and the NFR amendment is recorded beneath the clause, whose words stay as
ratified.

### Chunk 02: a release anchor, and every judgeable commit since it
Wave 1's `check-boundary-coverage` found merges only through the fragments they added, so work
committed on the base without a fragment was invisible to it, and a release check that blocks on
its answer would have passed that work unread. The op now finds the release anchor, the nearer the
tip of the newest first-parent commit adding a release file under `.prawduct/releases/` and the
oldest first-parent commit containing the merge-base of the base and the newest version tag. The
second serves repos that write no release files, including those that tag each release on a merge
into `main` the integration branch never contains: the merge-base is the integration commit that
was released. A candidate that reached the integration branch through a merge's second parent (a
hotfix tag, or `main` merged back with its release file) anchors on the integration branch's own
commit that release shipped, never on the back-merge, so work merged before the back-merge is still
walked; a candidate git cannot resolve falls back to the other, the older. It then classifies every
first-parent commit after the anchor that changes a judgeable file, unioned with the fragment join
and de-duplicated by commit, so a scope a pruned release withheld stays classified. One `git log`
lists the whole walk. A repo with neither anchor gets the fragment join alone, and the report says
there was no anchor. A new covered class, `release-bookkeeping`, is a single-parent commit after the
anchor whose judgeable changes are all files `release_version_files:` declared at the anchor: the
reopen commit after a cut, which read `direct` before. Another, `reverted`, is owed work whose
every judgeable change is back, at the base's tip, to where the release span starts: nothing of it
ships, so a release whose owed work was all reverted needs no batch review. A declaration added since the release never
qualifies, and an undeclared repo's fallback layout never does. A
merge whose branch changed nothing judgeable but whose merge commit edits a judgeable file now reads
`uncovered`, not `no-judgeable`, because the walk reaches such merges. The count line names the
anchor and how many commits the walk found, or that the walk could not run. Prerelease tags order as
SemVer does (`rc.10` above `rc.9`). The op also reads a base-advance transfer grant the Stop gate
recorded for exactly the merged span, the one record when both gates granted it. It is still
advice, and `check-releasability`'s exit is unchanged.

### Chunk 03: the release batch review, and the relax-only rule that credits it
A release that defers boundary reviews needs a review that reads what was deferred, and a rule
that credits it without loosening any PR gate. `/prawduct:critic cumulative` dispatches that review
on the integration base's own checkout, at its tip, with a clean tree, where under `per_release`
`critic-begin --mode cumulative` derives the release span (`--span release` is the explicit form). Its
interval is the release anchor to HEAD (Chunk 06: or from the first parent of an owed entry
older than the anchor). It rates the changed files of every release entry no
boundary review covered and reads the rest of the span as `files_context`. The manifest records
`span: release` with a `span_reason` naming the anchor. It refuses, naming the code and writing
nothing, off the base or off its tip (`off-base`), on a dirty tree (`dirty-tree`), with no anchor
(`no-anchor`), when the classification cannot run (`unevaluable`), or when the entries owed a read
change nothing that still differs from where the span starts (`no-subject`). It exits 3 when every entry is
already covered. `--force` overrides none of these.

A release-span fact is never a coverage edge, even when it rated every file, so no PR gate verdict
can turn covered because it exists. Its blocking findings still stand at the trees it read, as every
review's do, so it can block a span standing on those trees, never cover one. The release
check credits it through a new pure rule, `coverage_algebra.batch_review_covers`: an entry is
`batch-covered` when a boundary review on the base brackets it on the first-parent line, rated every
judgeable file of the entry still changed across its interval, and no unresolved blocker stands at
its two trees or at the entry's own (a merged branch's). Wave 1's batch rule is the special case of a review that rated every file. The rule
now applies to work committed on the base as well as to merges. A squash merge whose PR review
spans exactly the trees it landed reads `batch-covered`, where it read `direct`. A fix committed on
the base after such a review is `batch-covered` when `verify-resolutions` and free edges alone
compose the review's tree to it and the review's blockers are resolved. A new not-covered class,
`tail-deferred`, names a fix tail the PR gate deferred to the release; Chunk 05 produces it.

### Chunk 04: inference answers chunk at an eligible last chunk
Under `per_release`, a branch the lane takes no longer infers the boundary `cumulative` at its
plan's last chunk. One predicate, `critic_mode.lane_eligibility`, decides: the policy in force is
`per_release`, the plan has at most three chunks (the lane's own bound, kept at three even if a
later cadence key widens the short-plan deferral), its last chunk is not `Type: cumulative-final`,
the short-plan shape holds (no `Critic mode:`, not on the base, no risk surface), and the branch
changes at most 10 judgeable files. Anything it cannot read, or a crash, is not eligible. Where
rule 2, rule 4's clean-tree redirect, or an explicit `chunk`/`final` on a clean tree would have
named `cumulative`, inference answers `chunk` over the unreviewed interval with a `per-release
lane` rationale that names the `--chunks` the boundary review would have named, so the dispatch
is not refused as ambiguous; a `chunk` that could not reach the unreviewed commits keeps the
`cumulative`. The short-plan deferral, the Stop gate's warning and block, and the extension
deferral name the lane's review instead of the boundary `cumulative`, and once the lane's review
has finished the plan nothing owes a `cumulative`, so a fix after it takes a verify pass or a lane
`chunk`. An explicit `/prawduct:critic cumulative` still runs the per-PR boundary review. With the
key absent every answer and message is unchanged.

### Chunk 05: a blocker-free fix tail is deferred to the release
A fix for a non-blocking finding no longer buys its own verify round under `per_release` (#1222).
One predicate, `gates.fix_tail_deferral`, decides, for any PR in such a repo, lane or not: the
policy is `per_release`; the branch's coverage composes from the merge-base to a review taken on
the branch with no unresolved blocker; every judgeable file changed since that review is one its
findings named (`coverage.diagnose_fix_churn`'s conditions, file-level evidence); no review of any
tree of the branch carries an unresolved BLOCKING finding; and no path the tail changes is a risk
surface. Asked after the base-advance transfer fails, it gives `check-cumulative-critic` a new
status, `deferred`: exit 0, `satisfied (fix tail deferred to the release)`, and a `NOTE:` naming
the review, the tail's files and the release check that owes them a read. It is a deferral, never
coverage: the Stop gate passes the same tail with that note instead of blocking, and
`check-boundary-coverage` asks the same predicate of a merged branch (its tip, not HEAD) and reads
the merge `tail-deferred`, not covered, until a release batch review has read it. Every reader of
the gate's status handles `deferred`: inference does not name a `cumulative` for it, the clean
verify close says the branch is not covered but passes, and `check-pr-hygiene` lists the reviews
it stands on. A tail on a risk surface, a file the review did not name, an open blocker, or an
anchor review from before the merge-base still buys the verify round, and `per_pr` is unchanged.

### Chunk 06: the release check blocks a per_release release
The moved review and the deferred tail are owed to a check that now blocks. Under `per_release`,
read at the integration branch's tip, `check-releasability` refuses the release with
`boundary-uncovered:` while any entry `check-boundary-coverage` lists is not covered (an unreviewed
merge, a `tail-deferred` tail, work committed on the base), naming each one and the release batch
review that answers it, and with `boundary-unevaluable:` when the check cannot answer, a missing
release anchor included. It asks on the no-pending path too, so work merged with no fragment
cannot ship through "nothing to classify". `check-boundary-coverage --gate` exits 1 and 3 on the
same verdict, prints the policy it read and why, and under `--json` adds `policy` and `gate`; under
`per_pr` it exits 0 and the advice is unchanged, as is every exit of the bare op. Where the
integration branch's state cannot be read at all, a checkout declaring `per_release` is held to
it, the stricter reading for a release. The PR skill's release guard runs `--gate` and stops on
either refusal.

Five routes out that the gate would otherwise have closed: a release batch review's span starts at
the oldest owed entry's first parent when that entry sits before the anchor (a scope a pruned
release withheld), so it can be credited; the batch rule credits an octopus merge, which read
`unknown` for good; a merged branch's unresolved blocker, which no batch review clears, is named in
the roll-call of a `verify-resolutions` pass on the integration branch, so its resolution clears it
and the release passes; the review round budget never charges a release batch review; and
`review-stats` files it under its own `release` span (report schema 15), not `full`. The lane's
eligibility and the fix-tail deferral now read risk surfaces as the integration branch holds them
too (the merge-base and the tip), so a branch cannot rewrite its own `risk_surfaces:` to buy
either. The review close names the lane's review where the lane holds, not a boundary
`cumulative`. `project-state-keys.md` lists every class a correct release can still meet, whether
it blocks, and the way out.

## Consumer note
A new opt-in key, `boundary_review:` in `.prawduct/project-state.yaml` (see
`/prawduct:methodology project-state`). Nothing changes for a repo that does not set it. Set to
`per_release` on your integration branch, an eligible branch's PR is covered by its inner review,
a blocker-free fix tail may merge unreviewed (`check-cumulative-critic` exit 0, `satisfied (fix tail
deferred to the release)`), and `check-releasability` then refuses the release
(`boundary-uncovered:`) until a release batch review on the integration branch has read that work:
`/prawduct:critic cumulative` on its own checkout at its tip with a clean tree, where `critic-begin
--mode cumulative` derives the release span (`--span release` is the explicit form). A merge whose
branch still carries an unresolved BLOCKING finding stays held after that review: fix it on the
integration branch and run `/prawduct:critic verify-resolutions` there, whose roll-call names it.
It also refuses (`boundary-unevaluable:`) when it cannot answer, including when the repo has no
release anchor yet: opt in after your first tagged or cut release. Read the key's entry in
`project-state-keys.md` before opting in; it lists what can still hold a correct release and how
to clear each.

`check-boundary-coverage` (and the count line `check-releasability` prints) now also lists every
judgeable commit since your last release, including work committed on the integration branch
without a change fragment, so expect more entries and a count line that names the release anchor.
`--json` adds `anchor`, `no_anchor_reason`, each entry's `source` (`fragment`, `walk` or
`both`; `walk-failed` when git could not list the commits since the anchor) and each entry's
`blockers` (the unresolved blocking findings on a not-covered entry's own trees), and two new covered
classes: `release-bookkeeping`, for a commit that changes only the files `release_version_files:`
declared at your last release, and `reverted`, for owed work your integration branch has since
put back as it was (`counts` gains both keys). A merge whose fix tail the PR gate deferred reads `tail-deferred`,
not covered. Under `per_pr` neither command's exit code changes; `check-boundary-coverage --gate`
is the blocking reading, exit 0 there.

`/prawduct:critic cumulative`, run on your integration branch's own checkout at its tip, reviews
everything since your last release that no boundary review read, and `check-boundary-coverage` then reads that
work `batch-covered`. You do not need it while `boundary_review` is `per_pr`. A squash merge whose
PR review read exactly what it landed now reads `batch-covered` instead of `direct`.
