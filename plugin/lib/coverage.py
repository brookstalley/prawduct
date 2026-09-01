"""Diff-base resolution + coverage / PR fast-path gates for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 5) — the diff-base
resolution layer (honoring the ``base_branch:`` gitflow knob) and the coverage /
PR fast-path inspection it feeds: which files changed against the base, whether a
PR diff is documentation-only, and whether every commit on the branch is
``Type: trivial`` fileset-eligible. Pure git inspection + path classification —
no mutation.

Depends on its lib siblings ``core`` (for ``read_str_yaml_key`` — the canonical
twin of the hook's parity-pinned inline mirror, reached directly as
``critic_mode``/``views``/``buildplan_refs`` do) and — lazily, inside
``_pr_diff_is_doc_only`` — ``coverage_algebra`` (for the one judgeability
predicate, kernel-v3 chunk 04), plus the stdlib. The hook calls these lazily
via ``_coverage()``, keeping its top level lib-free (ch.1 isolation
invariant).

The two coverage/critic *gate commands* that consume this layer
(``cmd_verify_coverage`` / ``cmd_check_cumulative_critic``) stay in the hook for
now: their bodies also depend on the evidence-schema / critic-findings validators
slated for Chunk 6 (``gates``), and the plan's DAG runs ``coverage`` ← ``gates``
— so they move with ``gates`` (where ``gates`` → ``coverage`` is legal) rather
than pulling gates logic forward into this module. The *PR fast-path* gate
command (``check_pr_doc_only``) is gates-free and moves here; the hook keeps a
thin ``cmd_*`` wrapper delegating to it. (The parallel ``check_pr_trivial`` /
``_pr_diff_is_trivial`` fast-path was retired — fileset-eligibility was being used
as a *detector* of triviality rather than the *enforcement* of a per-chunk
``Type: trivial`` declaration, so feature clusters that only touch existing files
skipped both review gates.)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .change_log import CHANGE_LOG_REL_PATH
from .core import read_str_yaml_key

_BASE_BRANCH_KEY = "base_branch"
_DEFAULT_BASE_CANDIDATES = ("origin/main", "main", "HEAD~1")


def _git_ref_exists(project_dir: Path, ref: str) -> bool:
    """True if ``git rev-parse --verify <ref>`` resolves in ``project_dir``."""
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode == 0


def _resolve_base_branch(project_dir: Path) -> tuple[str | None, str]:
    """Resolve the git diff/merge base, honoring a configured ``base_branch:``.

    The 2.0.0 gitflow ship-blocker fix (build-plan Chunk 5): on a gitflow repo
    where feature branches cut from ``develop``, the hardcoded ``main``-first
    candidate list resolved the PR/coverage gates **and** the reviewer/cumulative
    base to ``merge-base(main, HEAD)`` — the whole ``develop..main`` range
    (a 2-commit branch reviewed as the entire promotion delta). When
    ``project-state.yaml`` sets ``base_branch: develop`` (top-level scalar), that
    branch becomes the base; ``origin/<b>`` is preferred over the bare ``<b>``
    for a stable remote-tracking merge-base. A configured-but-unresolvable base
    fails closed (returns None) so the misconfiguration surfaces rather than
    silently diffing the wrong range. When the knob is unset, falls back to the
    historical candidate list, so trunk repos are unaffected.

    Returns ``(base, base)`` on success or ``(None, reason)`` on failure — the
    same contract the gate callers already destructure.
    """
    configured = read_str_yaml_key(
        project_dir / ".prawduct" / "project-state.yaml", _BASE_BRANCH_KEY
    )
    if configured:
        for ref in (f"origin/{configured}", configured):
            if _git_ref_exists(project_dir, ref):
                return ref, ref
        return None, (
            f"configured base_branch {configured!r} not found "
            f"(tried origin/{configured}, {configured})"
        )

    for candidate in _DEFAULT_BASE_CANDIDATES:
        if _git_ref_exists(project_dir, candidate):
            return candidate, candidate
    return None, (
        "no base candidate resolved (origin/main, main, HEAD~1 all absent)"
    )


def diagnose_stale_remote_base(project_dir: Path, base_ref: str) -> dict | None:
    """Detect a *stale remote integration base* — the COV-7K4N condition.

    When ``base_ref`` is a remote-tracking ref (``origin/<b>``) and the local
    ``<b>`` is ahead of it (integration commits — a merge or a ``release-prep``
    — committed locally but never pushed), the merge-base anchors to the STALE
    remote. A feature built on those unpushed local commits then reads as
    spanning the whole unshipped range, so ``check_cumulative_critic`` can
    report ``uncovered`` on already-reviewed work whose every commit carries a
    clean review fact. The remedy is ``git push origin <b>`` — a required
    release step anyway — which fast-forwards the remote and re-anchors the
    merge-base to ``<b>``'s tree, where the feature's review chain begins.

    Returns ``None`` unless ``base_ref`` is ``origin/<b>`` with a local ``<b>``
    that exists and is ahead of it; otherwise::

        {"local", "remote", "commits_ahead", "ancestor_of_head",
         "release_prep_subject"}

    ``ancestor_of_head`` distinguishes the false-``uncovered`` case (local
    ``<b>`` is an ancestor of HEAD, so pushing moves the merge-base forward and
    the gate re-composes to a pass) from a diverged local branch (where pushing
    would not help — the gate hint suppresses itself). ``release_prep_subject``
    is the newest unpushed ``release-prep(...)`` subject in ``origin/<b>..<b>``
    or ``None`` — the "phantom release" signal the session-start advisory keys
    on. Never raises; any git failure or shape mismatch returns ``None`` (the
    callers degrade to their generic path).
    """
    from . import evidence  # noqa: PLC0415 -- lazy: mirrors resolve_merge_base_tree's import posture; avoids import-cycle risk at module load

    prefix = "origin/"
    if not base_ref or not base_ref.startswith(prefix):
        return None
    local = base_ref[len(prefix):]
    if not local:
        return None
    # Route every git touch through evidence.run_git (which converts subprocess
    # failures to a nonzero rc) so the "never raises" contract holds — the module
    # helper _git_ref_exists uses a bare subprocess.run that could surface
    # TimeoutExpired/OSError. A missing local branch (rc != 0) is not stale.
    rc, _, _ = evidence.run_git(project_dir, "rev-parse", "--verify", "--quiet", local)
    if rc != 0:
        return None
    rc, ahead_out, _ = evidence.run_git(
        project_dir, "rev-list", "--count", f"{base_ref}..{local}"
    )
    if rc != 0 or not ahead_out.isdigit():
        return None
    commits_ahead = int(ahead_out)
    if commits_ahead <= 0:
        return None
    anc_rc, _, _ = evidence.run_git(
        project_dir, "merge-base", "--is-ancestor", local, "HEAD"
    )
    rc, subjects, _ = evidence.run_git(
        project_dir, "log", "--format=%s", f"{base_ref}..{local}"
    )
    release_prep_subject = None
    if rc == 0:
        for line in subjects.splitlines():
            stripped = line.strip()
            if stripped.startswith("release-prep("):
                release_prep_subject = stripped  # log is newest-first → newest match
                break
    return {
        "local": local,
        "remote": base_ref,
        "commits_ahead": commits_ahead,
        "ancestor_of_head": anc_rc == 0,
        "release_prep_subject": release_prep_subject,
    }


def diagnose_fix_churn(
    project_dir: Path,
    facts: "list[dict]",
    head_tree: str,
    base_tree: str,
    merge_base: str,
    verdict_fn,
) -> "dict | None":
    """Detect the gap a builder dug for themselves: **the whole uncovered span**
    is a review of this branch, plus edits confined to files that review's own
    findings named, and that review left nothing blocking.

    This is the ``uncovered`` case that should not have existed. The gate's
    generic remedy names only full reviews, so a builder staring at it runs
    one — and that round reviews the prose the last fix wrote, finds something
    true about it, and buys the next round. Measured on a released version,
    one consumer branch reached ten rounds this way; across two evidence
    stores in the same window, most reviews were zero-blocking re-reviews.
    Naming the condition is what lets the message offer ``disposition``
    instead of a fourth reviewer.

    The discriminator is deliberately **what moved the tree**, never a round
    counter — CRT-3W6P's own counter-example is a round that looked like waste
    and was not, because a merge had brought thousands of unreviewed lines into
    functions the branch already touched.

    **Both ends of the span have to be proved, not just the last leg.** The
    message this feeds characterizes the whole gap, so proving only
    anchor→HEAD would let two shapes through, and both are false positives in
    the direction that sends unreviewed work to merge:

    * *The anchor predates the branch.* ``merge-base --is-ancestor`` alone is
      satisfied by every fact on the base branch, and the store is shared
      across worktrees. A branch with no review of its own would anchor on the
      last review of ``develop`` — and since reviews in one repo name the same
      hot files over and over, a whole unreviewed branch could land inside the
      subset test. So the anchor must also be a **descendant of the
      merge-base**: a review at or before the merge-base by definition never
      saw this branch. This is also what keeps the merge case honest — after
      merging the base in, a base-side fact can become *nearer* by commit
      distance than the branch's own review, which would switch the anchor and
      drop the merged-in lines out of the delta.
    * *The gap is upstream of the anchor.* ``uncovered`` means composition
      failed somewhere in base→HEAD, and it need not have failed on the last
      leg — an earlier dirty-tree review or selective commit leaves a hole
      below an anchor whose own delta is pure churn. Then "one verify pass
      closes this" is false and the builder is back in the loop. So coverage
      must **compose from the base tree up to the anchor's tree**; only the
      anchor→HEAD leg may be the churn.

    **The bound this does NOT prove, stated beside the two it does.** The
    subset test is ``set(judgeable delta) <= {files the anchor's findings
    named}`` — *file* granularity. It rules out work in a file that review
    never looked at; it cannot tell a fix from substantial new work written
    into a file some finding merely named. The consequence is asymmetric and
    lands downstream: the remedy this feeds is ``verify-resolutions``, which
    since CRT-3W6P rates new findings BLOCKING-only, so a false positive here
    routes genuinely unreviewed content to the narrowest review in the
    framework. That is bounded rather than open — the carve-out keeps
    weakened tests, dropped requirements, untested changed behavior, security
    and fix-by-fudging blocking in that mode — but it is a real bound, and the
    caller's message must not assert content-level certainty on file-level
    evidence. Closing it properly needs a content discriminator (hunk overlap
    against the findings' own line ranges), which the findings record does not
    carry today.

    Returns ``None`` when the condition does not hold, and a dict otherwise::

        {"status": "churn", "fact_id", "delta_files", "named_files",
         "warning", "note"}
      | {"status": "unavailable", "reason": str}

    The two negatives are **not** the same answer, and collapsing them is the
    shape ``learnings.md`` names: *"'Advice fails soft' is not 'advice fails
    silent' — a degraded advisory path must still name its consequence, or it
    manufactures the false success it was meant to prevent."* ``None`` means
    the diagnosis ran and this is not churn; ``unavailable`` means it could not
    run, which the caller says out loud so a control that never fires can be
    told apart from one that never ran. Never raises — *given* its arguments:
    ``verdict_fn`` is required, deliberately, so that omitting it is a
    ``TypeError`` at the call site rather than the silent slow path this
    diagnosis cannot afford (see the comment at its call).
    """
    from . import coverage_algebra, evidence  # noqa: PLC0415 -- lazy: matches diagnose_stale_remote_base's import posture; avoids an import cycle at module load

    if not head_tree or not base_tree or not merge_base or not isinstance(facts, list):
        return {"status": "unavailable", "reason": "missing span endpoints"}

    resolved = coverage_algebra.resolution_index(facts)
    candidates = []
    degraded: "str | None" = None
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        fact_head_tree = body.get("head_tree")
        head_commit = body.get("head_commit")
        # A dirty-tree review records `head_commit: null` — it vouches for a
        # tree no commit materialized, so "is it behind HEAD?" has no answer
        # and the lineage filters below cannot run. Skip rather than guess;
        # this is a genuine non-candidate, not a degradation.
        if not fact_head_tree or not head_commit or fact_head_tree == head_tree:
            continue
        anc_rc, _, anc_err = evidence.run_git(
            project_dir, "merge-base", "--is-ancestor", head_commit, "HEAD"
        )
        if anc_rc not in (0, 1):
            # rc 1 is a clean "not an ancestor" — another branch's fact, and
            # the filter that keeps a sibling worktree's review from anchoring
            # a diagnosis about this one. Anything else is git failing, which
            # is a different fact about the world and must not read as "no".
            degraded = degraded or f"ancestry check failed ({anc_err.strip()[:80]})"
            continue
        if anc_rc == 1:
            continue
        # ...and strictly AFTER the merge-base, or it never saw this branch.
        mb_rc, _, mb_err = evidence.run_git(
            project_dir, "merge-base", "--is-ancestor", merge_base, head_commit
        )
        if mb_rc not in (0, 1):
            degraded = degraded or f"merge-base check failed ({mb_err.strip()[:80]})"
            continue
        if mb_rc == 1 or head_commit.startswith(merge_base) or merge_base.startswith(head_commit):
            continue
        rc, distance, err = evidence.run_git(
            project_dir, "rev-list", "--count", f"{head_commit}..HEAD"
        )
        if rc != 0 or not distance.isdigit():
            degraded = degraded or f"distance to HEAD unresolvable ({err.strip()[:80]})"
            continue
        candidates.append((int(distance), fact.get("ts") or "", fact))

    if not candidates:
        return {"status": "unavailable", "reason": degraded} if degraded else None
    # "Nearest" means nearest to HEAD *on the lineage*, not latest by clock.
    # The store is shared across every worktree of a clone, so wall-clock order
    # is not this branch's order — a sibling worktree's review can carry a
    # later timestamp than the one that vouches for the commit below HEAD.
    # Timestamp breaks ties only when two facts sit at the same distance.
    nearest = min(c[0] for c in candidates)
    newest = max((c for c in candidates if c[0] == nearest), key=lambda c: c[1])[2]

    # A round that IS required stays required: an unresolved blocker means the
    # builder owes a verify pass regardless of what moved the tree.
    if coverage_algebra.unresolved_blocking(newest, resolved):
        return None

    body = newest.get("body") or {}
    anchor_tree = body["head_tree"]

    # Everything below the anchor must already compose, or the gap is not the
    # last leg and the remedy this feeds would not close it.
    #
    # `verdict_fn` is threaded in and REQUIRED rather than defaulted. It carries
    # both properties this call cannot do without: the n-key free-edge form (the
    # pairwise fallback measures at ~5.6k `git diff` subprocesses on this repo's
    # store, twice per verdict), and the cross-call memo — this runs on the
    # interactive `/prawduct:pr create` path, inside a diagnosis the gate message
    # calls "the cheap check". A caller that forgets it is a `TypeError` at the
    # call site, which is the failure a maintainer can see; a default made it a
    # silent multi-minute hang instead.
    upstream = verdict_fn(facts, base_tree, anchor_tree)
    # Known gap, accepted: a git failure inside the verdict renders here as
    # "nothing composes", the same shape the status split above exists to
    # separate. Distinguishing them needs the failure surfaced through
    # `coverage_verdict` itself, which every gate shares — a wider change than
    # this diagnosis, and the failure direction is the safe one (silence, not a
    # false claim).
    if upstream.get("status") != "covered":
        return None

    delta = evidence.tree_diff(project_dir, anchor_tree, head_tree)
    if delta is None:
        return {"status": "unavailable", "reason": "anchor→HEAD diff unresolvable"}
    judgeable = coverage_algebra.judgeable_files(delta)
    if not judgeable:
        # Nothing judgeable moved — this composes as a free edge and is not the
        # uncovered case at all. Whatever brought the caller here, it is not
        # this.
        return None

    named: set[str] = set()
    for finding in body.get("findings") or []:
        for path in finding.get("files") or []:
            if isinstance(path, str) and path:
                named.add(path)
    if not named or not set(judgeable) <= named:
        return None

    counts = body.get("counts") or {}
    return {
        "status": "churn",
        "fact_id": newest.get("id"),
        "delta_files": sorted(judgeable),
        "named_files": sorted(named),
        "warning": counts.get("warning", 0),
        "note": counts.get("note", 0),
    }


def diagnose_base_advance_transfer(
    project_dir: Path,
    facts: "list[dict]",
    base_tree: str,
    head_tree: str,
    diff_fn,
    verdict_fn,
) -> "dict | None":
    """Can a review taken *before* the base branch advanced still vouch for the
    span the advance created?

    A base sync moves the required span's start node, so no fact begins there
    and composition reports ``uncovered`` — even when the branch's own diff did
    not move a byte. The transfer is the computed answer: a span already covered
    transfers to the required one when the two spans hold *the same branch diff*.

    Conditions 1 and 2 are this function's; condition 3 is the caller's
    (:func:`gates.suite_vouches_for_tree`, which owns the evidence and
    states what it requires)::

        1. the two spans' judgeable changed-file sets are identical
        2. for every such file f: blob(HEAD, f) == blob(head', f)
                             and  blob(base, f) == blob(base', f)

    **Soundness boundary — byte equality ACROSS contexts, never content
    equivalence WITHIN one.** The 2026-07-29 ruling (COV-3M8Q) bans relaxing
    judgeability by normalizing content, because a comment-only edit can change
    behavior in this repo (a ``prawduct:allow`` pragma suppresses a compliance
    check while leaving the AST identical). Nothing here is normalized: every
    comparison is git's own tree-to-tree diff over the exact paths, so **any**
    edit to a branch file — comments included — makes the diff non-empty and
    denies the transfer. What the transfer asserts is narrower than what the
    ruling forbids: not "this changed file need not be reviewed", but "this
    byte-identical change *was* reviewed, and the advance touched none of it".

    The one genuinely new exposure is the reviewed diff interacting with
    advanced context in *disjoint* files, which no re-read of an unchanged diff
    would catch either. Condition 3 is what prices it — the suite, not the
    transferred review, vouches for semantic interaction with the new base. It
    lives with the caller so a near miss can be reported as the cheap remedy it
    is: run the suite, not another review.

    **Candidates are selected by content, not by lineage.** A commit-ancestry
    filter would be the obvious way to mean "this branch's own reviews", and it
    is wrong twice: it excludes the rebase case (rebasing rewrites the very
    commits the branch's facts anchor to, so every one of them leaves HEAD's
    history while the trees they vouch for are untouched), and it is not what
    soundness rests on. Conditions 1–3 are statements about content: a span
    whose judgeable diff is byte-identical on both sides reviewed *this* change,
    whichever branch or worktree it was taken on. What lineage would have bought
    is cost control, and the ``files_changed`` prune below buys that directly.

    Returns::

        {"status": "match", "prior_fact_id", "prior_reviews", "prior_base",
         "prior_head", "files": [...], "advance_files": [...] | None}
      | {"status": "unavailable", "reason": str}
      | None                                    # no transferable prior span

    ``advance_files`` is ``None`` — not ``[]`` — when the advance's own diff
    could not be read. It is message detail only, so an unreadable one does not
    deny a transfer the three conditions already granted; but a caller rendering
    it as "the advance touched 0 files" would be asserting something nothing
    checked, which is why the two are distinguishable.

    ``unavailable`` is kept distinct from ``None`` for the reason
    :func:`diagnose_fix_churn` states: a degraded check that says nothing is
    indistinguishable from one that found nothing. Never raises; every git or
    object failure denies the transfer rather than granting it (authority fails
    closed).
    """
    from . import coverage_algebra, evidence  # noqa: PLC0415 -- lazy: matches diagnose_fix_churn's import posture; avoids an import cycle at module load

    if not head_tree or not base_tree or not isinstance(facts, list):
        return {"status": "unavailable", "reason": "missing span endpoints"}

    branch_diff = diff_fn(base_tree, head_tree)
    if branch_diff is None:
        return {"status": "unavailable", "reason": "branch diff unresolvable"}
    required = set(coverage_algebra.judgeable_files(branch_diff))
    if not required:
        # Nothing judgeable differs across the required span — that composes as
        # a free edge, so whatever brought the caller here, it is not this.
        return None
    paths = sorted(required)

    # Endpoints, not whole facts: the span a branch already had covered is
    # routinely composed rather than carried by one fact — a cumulative
    # (merge-base → tip) followed by a verify-resolutions pass (tip → fixed tip)
    # leaves the covered span running from the FIRST fact's base to the LAST
    # one's head, a pair no single fact holds. Newest-appended first, so the
    # branch's most recent state is tried before older ones.
    #
    # The prune is a COST bound, not one of the conditions — it can only deny a
    # transfer the three conditions would have granted, never grant one they
    # would not. It is the store, not the branch, that makes it necessary: every
    # worktree of the clone appends to the same file, and each surviving
    # endpoint costs a git call below.
    #
    # It is close to necessary and deliberately not exactly so. A fact on the
    # path from b' to h' spans a sub-interval, so its ``files_changed`` sits
    # inside the path's CUMULATIVE changed set — which is a superset of the
    # span's NET diff whenever the branch touched a file and then put it back.
    # After such a revert the fact that carries an endpoint is pruned and a
    # sound transfer is silently missed. Accepted rather than widened: the
    # failure is a denial (the operator gets today's remedy, not a wrong pass),
    # and dropping the prune would put the git work back in proportion to a
    # store that grows forever.
    prior_bases: list[str] = []
    prior_heads: list[str] = []
    for fact in reversed(facts):
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        prior_base, prior_head = body.get("base_tree"), body.get("head_tree")
        changed = body.get("files_changed")
        if not prior_base or not prior_head or not isinstance(changed, list):
            continue
        if not set(coverage_algebra.judgeable_files(changed)) <= required:
            continue
        if prior_base not in prior_bases:
            prior_bases.append(prior_base)
        if prior_head not in prior_heads:
            prior_heads.append(prior_head)
    if not prior_bases or not prior_heads:
        return None

    # Condition 2, one pathspec-limited diff per distinct endpoint: a candidate
    # endpoint survives only when it agrees with the required span's endpoint on
    # EVERY file the branch changed. Each candidate list is already distinct and
    # each is asked about ONE anchor, so there is nothing to memoize — an
    # earlier version cached on (candidate, anchor) and could never hit.
    # A path set large enough to overflow git's argv makes the diff fail, which
    # reads as "could not be computed" and denies, the same direction as every
    # other failure here.
    degraded: "str | None" = None

    def _survivors(candidates: list[str], anchor: str) -> list[str]:
        nonlocal degraded
        kept = []
        for candidate in candidates:
            if candidate == anchor:
                kept.append(candidate)
                continue
            differing = evidence.tree_diff(
                project_dir, candidate, anchor, paths=paths
            )
            if differing is None:
                degraded = degraded or "a candidate tree could not be diffed"
            elif not differing:
                kept.append(candidate)
        return kept

    surviving_heads = _survivors(prior_heads, head_tree)
    surviving_bases = _survivors(prior_bases, base_tree)

    for prior_head in surviving_heads:
        for prior_base in surviving_bases:
            if (prior_base, prior_head) == (base_tree, head_tree):
                continue  # the span that just failed to compose
            # Condition 1. Set equality, not the containment the blob checks
            # already force: a prior span that changed MORE files than this one
            # saw work no longer in the required span (reverted, or absorbed
            # upstream), and a review of a different fileset is not a review of
            # this one.
            prior_diff = diff_fn(prior_base, prior_head)
            if prior_diff is None:
                degraded = degraded or "a candidate span could not be diffed"
                continue
            if set(coverage_algebra.judgeable_files(prior_diff)) != required:
                continue
            # ...and the prior span must itself be COVERED — which is where
            # "zero unresolved blocking findings on its path" comes from. A
            # blocked prior span transfers nothing: the blocker is still owed.
            prior_verdict = verdict_fn(facts, prior_base, prior_head)
            if prior_verdict.get("status") != "covered":
                continue
            reviews = [
                step for step in prior_verdict.get("path", [])
                if step.get("kind") == "review"
            ]
            advance = evidence.tree_diff(project_dir, prior_base, base_tree)
            return {
                "status": "match",
                "prior_fact_id": reviews[-1].get("id") if reviews else None,
                "prior_reviews": len(reviews),
                "prior_base": prior_base,
                "prior_head": prior_head,
                "files": paths,
                "advance_files": (
                    None
                    if advance is None
                    else sorted(coverage_algebra.judgeable_files(advance))
                ),
            }

    return {"status": "unavailable", "reason": degraded} if degraded else None


def count_branch_rounds(
    project_dir: Path, facts: "list[dict]", merge_base: str
) -> dict:
    """How many review rounds this branch has already bought, and what they cost.

    Everything the uncovered gate prints is a pure function of the current
    tree, so round five reads exactly like round one — measured on a consumer
    branch that ran six of them and reported that block #6 was
    indistinguishable from block #1. This is the discriminator that lets a
    repeat round *look* like one.

    It is derived from the branch's own facts, never a stored counter: the
    evidence store is shared by every worktree of the clone, so "how many
    reviews exist" is not "how many this branch bought". A round is this
    branch's when the commit it was taken against lies strictly after the
    merge-base on HEAD's lineage. ``head_commit`` is that commit for a review
    of committed state; a dirty-tree review records ``head_commit: null`` and
    is placed by ``dispatch_commit``, the commit HEAD sat at when the reviewer
    was dispatched — that round was spent on this branch's work just as surely,
    and dropping it would undercount exactly the mid-chunk reviews a long
    branch accumulates most of.

    **The count is a documented lower bound in one case**, and the asymmetry is
    deliberate: a dirty-tree review taken before the branch's first commit sits
    AT the merge-base, and ``merge_base..HEAD`` excludes it. Widening the span
    to include the merge-base commit would sweep in the *base branch's* own
    reviews, which is the error that tells a first-round builder they are on
    round four. Undercounting says "at least this many"; overcounting says
    something false in the direction that discredits the whole message.

    One ``git rev-list`` answers both lineage questions by set membership, so
    this adds a single subprocess rather than the two-ancestry-checks-per-fact
    that :func:`diagnose_fix_churn` pays — it runs on the interactive
    ``/prawduct:pr create`` path against a store holding every review the clone
    has ever recorded.

    Returns ``{"status": "counted", "rounds", "seconds", "timed"}`` — with
    ``seconds`` ``None`` when no attributed round recorded a duration — or
    ``{"status": "unavailable", "reason"}``. Never raises: this is advice, and
    advice fails soft. It is deliberately not silent, because a tally that
    vanishes when it breaks reads as "round one" to the builder it exists to
    warn (``learnings.md``: "'advice fails soft' is not 'advice fails silent'").
    """
    from . import evidence  # noqa: PLC0415 -- lazy: mirrors diagnose_fix_churn's import posture; avoids an import cycle at module load

    if not merge_base:
        return {"status": "unavailable", "reason": "no merge-base to count from"}
    if not isinstance(facts, list):
        return {"status": "unavailable", "reason": "the evidence store did not read"}
    rc, out, err = evidence.run_git(project_dir, "rev-list", f"{merge_base}..HEAD")
    if rc != 0:
        return {
            "status": "unavailable",
            "reason": f"this branch's commits are unresolvable ({err.strip()[:80]})",
        }
    on_branch = {line.strip() for line in out.splitlines() if line.strip()}

    rounds = 0
    durations: list[float] = []
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        commit = body.get("head_commit") or body.get("dispatch_commit")
        if not isinstance(commit, str) or commit not in on_branch:
            continue
        rounds += 1
        seconds = body.get("duration_seconds")
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            durations.append(float(seconds))
    return {
        "status": "counted",
        "rounds": rounds,
        "seconds": round(sum(durations), 1) if durations else None,
        "timed": len(durations),
    }


def format_branch_rounds(tally: "dict | None") -> str:
    """The uncovered gate's one sentence about *which* round this is.

    One function owns the whole sentence and decides which of the three
    readings leads, so no call site can assemble a variant of its own
    (``learnings.md``: advice with an exception stapled on still leads with the
    advice). The figure is computed from the branch's own rounds at call time
    and never written down — a duration copied into prose drifts, and
    correcting it costs the review round this message exists to save.

    **It asks for a reason rather than discouraging the round**, and it names
    what a good reason looks like. A repeat round is sometimes exactly right —
    CRT-3W6P's counter-example is a round that looked like waste and was not,
    because a merge had brought thousands of unreviewed lines into files the
    branch already touched. A bare "you have spent four already" would suppress
    that round, so the sentence descends to the two cases: a merge or genuinely
    new work answers it, one more fix commit does not. A reader agrees with a
    general prompt and spends the round anyway.
    """
    if not tally or tally.get("status") != "counted":
        reason = (tally or {}).get("reason", "unknown")
        return (
            f"NOTE: which round this is could not be derived ({reason}) — read the "
            f"round count as unknown, not as one."
        )
    n = tally["rounds"]
    if not n:
        return (
            "NOTE: no review round has been recorded against this branch since the "
            "merge-base, so this gap is unreviewed work rather than a repeat — the "
            "next round is this branch's first."
        )
    spent = ""
    if tally.get("seconds"):
        from . import telemetry  # noqa: PLC0415 — lazy keeps this module's import DAG light

        # Only when some round went untimed: "1 of 1 timed" is noise, and a
        # reader who has to parse it stops reading the sentence that matters.
        partial = "" if tally["timed"] >= n else f", {tally['timed']} of {n} timed"
        # Named as THIS BRANCH's spend because the other number a builder meets
        # in the same session — `telemetry.format_round_price` — is a repo-wide
        # median. Two unlabelled durations in one workflow read as one number
        # that disagrees with itself.
        #
        # Rendered through the shared formatter, which owns the sub-minute
        # guard: this function had that guard and the price sentence did not,
        # which is how the surface that literally states the price could say
        # "about 0 min".
        cost = telemetry.format_minutes(tally["seconds"])
        spent = (
            f", costing {cost} so far "
            f"(this branch's own rounds{partial}, not a repo-wide median)"
        )
    plural = "" if n == 1 else "s"
    return (
        f"NOTE: this branch has already recorded {n} review round{plural} since the "
        f"merge-base{spent} — so the next one is round {n + 1}, not its first. The "
        f"gate is still uncovered after {'it' if n == 1 else 'them'}: name what "
        f"round {n + 1} will do differently before you spend it — a merge or "
        f"genuinely new work is a good answer, 'one more fix commit' is not."
    )


def resolve_merge_base_tree(project_dir: Path) -> dict:
    """Resolve base branch → merge-base commit → that commit's tree SHA —
    the shared prelude of every gate/dispatch that anchors an interval at
    the PR span. One implementation (kernel-v3 ch.06 review dedup):
    ``gates.check_cumulative_critic``, ``gates._merge_base_verdict``, and
    ``critic_consolidate.begin_review`` each carried a divergent copy — the
    same drift class the judgeability-predicate consolidation killed.

    Returns ``{"status": "ok", "base_branch", "merge_base", "tree"}`` or
    ``{"status": "error", "step": "resolve-base" | "merge-base" |
    "rev-parse", "reason"}``. ``reason`` carries the full detail; callers
    map ``step`` onto their own error posture (loud stderr with a per-step
    remedy, silent degradation, or an error dict).
    """
    from . import evidence  # noqa: PLC0415 -- lazy: mirrors the gates/consolidate import posture; avoids import-cycle risk at module load

    base_branch, base_reason = _resolve_base_branch(project_dir)
    if base_branch is None:
        return {"status": "error", "step": "resolve-base", "reason": base_reason}
    rc, merge_base, err = evidence.run_git(
        project_dir, "merge-base", base_branch, "HEAD"
    )
    if rc != 0 or not merge_base:
        return {
            "status": "error",
            "step": "merge-base",
            "reason": f"merge-base {base_branch}..HEAD failed ({err})",
        }
    rc, tree, err = evidence.run_git(
        project_dir, "rev-parse", f"{merge_base}^{{tree}}"
    )
    if rc != 0 or not tree:
        return {
            "status": "error",
            "step": "rev-parse",
            "reason": f"cannot resolve {merge_base[:12]}^{{tree}} ({err})",
        }
    return {
        "status": "ok",
        "base_branch": base_branch,
        "merge_base": merge_base,
        "tree": tree,
    }


def _coverage_resolve_base(project_dir: Path) -> tuple[str | None, str]:
    """Pick the git diff base for coverage verification. Mirrors
    ``_resolve_base`` in ``bin/test-reference-verify`` so writer (verifier)
    and reader (verify-coverage) examine the same set of changes. If the
    bases diverge, every chunk's verify-coverage would emit spurious
    missing-coverage findings on files outside the verifier's base. Delegates
    to ``_resolve_base_branch`` so the gates honor the ``base_branch:`` knob.
    """
    return _resolve_base_branch(project_dir)


def _coverage_changed_files(project_dir: Path, base: str) -> list[str]:
    """Files changed between ``base`` and the working tree, union untracked.
    Mirrors ``_changed_files`` in ``bin/test-reference-verify`` — same
    union over ``git diff`` + ``git ls-files --others --exclude-standard``
    so verify-coverage sees exactly the file set the verifier scored.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", base],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    files = {line.strip() for line in proc.stdout.splitlines() if line.strip()}

    proc2 = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc2.returncode == 0:
        files.update(line.strip() for line in proc2.stdout.splitlines() if line.strip())
    return sorted(files)


def _pr_diff_is_doc_only(project_dir: Path) -> tuple[bool, str]:
    """Shared helper: does the PR diff (``merge-base...HEAD``) need review?

    Returns ``(is_doc_only, status_message)``. ``is_doc_only`` is True only
    when the diff is non-empty and NO changed file is judgeable — the one
    predicate (``coverage_algebra.is_judgeable_path``, kernel-v3 chunk 04)
    answers this, replacing this helper's own ``.md`` + protected-path copy
    (one of the divergent doc-only sites behind CRT-5D8Q) — **and no changed
    file is live state a non-hermetic test reads** (``TEST_COUPLED_STATE``,
    COV-4H7N). The fast path skips the Critic, the PR review AND the suite in
    one move, so it has to clear both questions: PR #125 changed only
    ``.prawduct/*.md`` plus ``project-state.yaml``, rode this path, and broke
    ``test_norm_probes`` on develop with nothing to catch it. The two reasons
    are reported separately because the remedies differ — one needs a review,
    the other needs a suite run. A
    governance-protected ``.md`` (``skills/``, ``methodology/``,
    ``templates/``, root ``CLAUDE.md`` — PR-5K8D) is judgeable, so it still
    never rides the fast path. The status message names the specific reason
    for False (``no-base``, ``git-failed``, ``empty-diff``,
    ``not-doc-only: <files>``) so both the CLI gate and the stop-hook Gate 3
    can surface actionable detail without re-implementing the diff
    inspection. Base resolution mirrors ``_coverage_resolve_base`` so the
    helper sees the same diff surface as the cumulative-Critic flow.
    """
    from . import coverage_algebra  # noqa: PLC0415 — lazy keeps this module's import DAG light

    base, base_note = _coverage_resolve_base(project_dir)
    if base is None:
        return False, f"no-base: {base_note}"

    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return False, f"git-failed: git diff {base}...HEAD failed: {proc.stderr.strip()}"

    files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not files:
        return False, f"empty-diff: no files changed in {base}...HEAD"

    judgeable = coverage_algebra.judgeable_files(files)
    if judgeable:
        sample = ", ".join(judgeable[:3])
        more = f" (+{len(judgeable) - 3} more)" if len(judgeable) > 3 else ""
        return False, f"not-doc-only: PR includes review-needing files: {sample}{more}"

    coupled = [f for f in coverage_algebra.suite_coupled_files(files) if f not in judgeable]
    if coupled:
        sample = ", ".join(coupled[:3])
        more = f" (+{len(coupled) - 3} more)" if len(coupled) > 3 else ""
        return False, (
            "not-doc-only: PR includes live state a non-hermetic test reads: "
            f"{sample}{more}"
        )

    return True, (
        f"doc-only: {len(files)} file(s) in {base}...HEAD, none judgeable"
    )


def check_change_log_entry(project_dir: Path) -> int:
    """PR-boundary probe: a code-changing branch must add a change-log entry.

    A branch whose ``merge-base...HEAD`` diff contains **judgeable** work — as
    :func:`coverage_algebra.is_judgeable_path` defines it, the same predicate
    ``check-pr-doc-only`` and the coverage gates ask — can only be shipped by the
    release flow if a change-log entry exists for it. Historically nothing
    checked this, so a branch could merge with NO entry and the gap surfaced only
    at release reconstruction (REL-6C3W — CRT-7B4M/#82, found at the v2.0.16
    release). The `/prawduct:pr` Create flow (Step 1c) runs this probe and STOPs
    on failure.

    **Judgeability is not "is it ``.md``", and this docstring used to say it
    was.** Session metadata under ``.prawduct/`` is not ``.md`` and is *not*
    judgeable; governance-protected prose (``skills/``, ``methodology/``,
    ``templates/``, root ``CLAUDE.md``) *is* ``.md`` and *is* judgeable, because
    skill prose is behavioral logic. Cite the predicate rather than restating its
    rule here — a prose copy is the fourth classifier this function shipped once
    already.

    Exit 0 when:
      * the diff is empty, or holds no judgeable file, or
      * a judgeable diff includes ``.prawduct/change-log.md`` AND that diff
        ADDS at least one entry header (a ``+## `` line) — merely editing an
        existing entry's text does not vouch for new work.

    Exit 1 otherwise, with a named reason on stderr (``no-entry``,
    ``entry-edited-not-added``, ``no-base``, ``git-failed``). Un-evaluable
    git state fails closed — the caller falls back to manual judgment rather
    than silently skipping the probe (same posture as ``check_pr_doc_only``).
    """
    base, base_note = _coverage_resolve_base(project_dir)
    if base is None:
        print(f"no-base: {base_note}. Check the change-log by hand.", file=sys.stderr)
        return 1

    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        print(
            f"git-failed: git diff {base}...HEAD failed: {proc.stderr.strip()}."
            " Check the change-log by hand.",
            file=sys.stderr,
        )
        return 1

    files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    # THE predicate, shared with `check-pr-doc-only` (CRT-5D8Q). This used to be
    # an inline `not f.endswith(".md")`, which is a FOURTH classifier that the
    # CRT-5D8Q consolidation never folded in — so the two gates at the same PR
    # boundary answered oppositely about the same file. `.prawduct/` session
    # metadata (`corpus-state.json`, evidence, findings) is not `.md`, so this
    # gate called it code while `check-pr-doc-only` correctly called it
    # non-judgeable and skipped the review gates entirely.
    #
    # Reported from a consuming repo, and worse than a spurious block: the
    # remedy text is executable advice, and it was wrong advice. The
    # `.prawduct/corpus-state.json` that triggered it was another session's
    # corpus refresh riding along on a cherry-pick, so following the gate would
    # have written a change-log entry describing someone else's work as the
    # author's own — a gate demanding a false provenance record.
    from . import coverage_algebra  # noqa: PLC0415 — lazy keeps this module's import DAG light

    judgeable = coverage_algebra.judgeable_files(files)
    if not files:
        print(f"empty-diff: no files changed in {base}...HEAD — no entry required.")
        return 0
    if not judgeable:
        print(
            f"doc-only: none of the {len(files)} changed file(s) are judgeable "
            "(docs and session metadata only) — no entry required."
        )
        return 0

    if CHANGE_LOG_REL_PATH not in files:
        sample = ", ".join(judgeable[:3])
        more = f" (+{len(judgeable) - 3} more)" if len(judgeable) > 3 else ""
        print(
            f"no-entry: branch changes code ({sample}{more}) but "
            f"{CHANGE_LOG_REL_PATH} is untouched — add a change-log entry for "
            f"this work before opening the PR.",
            file=sys.stderr,
        )
        return 1

    proc2 = subprocess.run(
        ["git", "diff", f"{base}...HEAD", "--", CHANGE_LOG_REL_PATH],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc2.returncode != 0:
        print(
            f"git-failed: git diff of {CHANGE_LOG_REL_PATH} failed: "
            f"{proc2.stderr.strip()}. Check the change-log by hand.",
            file=sys.stderr,
        )
        return 1
    added_header = any(
        line.startswith("+## ") for line in proc2.stdout.splitlines()
    )
    if not added_header:
        print(
            f"entry-edited-not-added: {CHANGE_LOG_REL_PATH} changed but no new "
            f"entry header (+## ...) was added — editing an existing entry does "
            f"not vouch for this branch's code changes.",
            file=sys.stderr,
        )
        return 1

    print(f"entry-present: {CHANGE_LOG_REL_PATH} adds a new entry in {base}...HEAD.")
    return 0


def check_pr_doc_only(project_dir: Path) -> int:
    """Fast-path gate for `/prawduct:pr create`: report whether the PR diff is doc-only.

    Exit 0 when the diff in ``merge-base...HEAD`` is non-empty and contains
    no judgeable file (``coverage_algebra.is_judgeable_path`` — the one
    predicate) — the `/prawduct:pr` skill uses this to skip the cumulative-
    Critic and PR-reviewer gates, mirroring the session-end stop-hook
    carveout (`gates.session_changes_all_non_judgeable`) at the PR boundary.
    The stop hook's PR-review evidence gate (Gate 3) consults the same
    helper so a doc-only PR doesn't get blocked at session end for missing
    evidence — symmetric behavior across both gates.

    Exit 1 otherwise (any judgeable file — including governance-protected
    ``.md``: skill/methodology/template prose is behavioral logic, never
    "docs" — empty diff, no resolvable base branch, or git failure). Fails
    closed: when the gate cannot be evaluated, fall through to the full
    review path rather than silently skipping it.
    """
    is_doc_only, status = _pr_diff_is_doc_only(project_dir)
    if is_doc_only:
        print(
            f"{status} — cumulative-Critic and PR-reviewer gates may be skipped."
        )
        return 0
    suffix = (
        ". Doc-only fast-path is not applicable."
        if status.startswith("empty-diff")
        else ". Falling back to full review path."
        if status.startswith(("no-base", "git-failed"))
        else ". Full review required."
    )
    print(f"{status}{suffix}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Pricing a commit before it is made
# ---------------------------------------------------------------------------


def _working_tree_paths(project_dir: Path) -> "tuple[list[str] | None, str | None]":
    """Every path with an uncommitted change — staged, unstaged, untracked —
    as ``(paths, None)``, or ``(None, reason)`` when git cannot be read.

    **The reason is returned rather than dropped** because it is the only
    diagnosis of an ``unknown`` verdict that will ever exist: nothing else logs
    it, so once this function returns, a missing git, a not-a-repository, and
    the 30s timeout are indistinguishable to everyone downstream. The sibling
    advisory in this module (:func:`count_branch_rounds`) already carries its
    git error forward this way, and a waivered broad catch is expected to
    surface its context at a real boundary rather than swallow it.

    Deliberately NOT session-scoped, unlike ``gitstate._get_session_changed_files``:
    the question here is what *this commit* will contain, and a commit takes
    the whole working tree regardless of which session dirtied it. A rename
    contributes BOTH of its paths, because the review interval sees both sides.

    Runs its own ``git status`` rather than reusing
    ``gitstate.git_status_output`` for one reason: ``-uall``. The shared helper
    uses plain ``--porcelain``, which collapses an untracked directory to a
    single ``src/`` entry — enough for the session-baseline comparison it
    serves, and wrong here twice over. Classifying a directory names a path
    the builder cannot act on, and a directory holding only free files
    classifies as judgeable because it is neither metadata nor ``.md``,
    pricing a free commit as costly. The shared helper is left alone: its
    flags are load-bearing for the baseline callers, and widening them there
    would change what every session treats as a change.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- an advisory must not crash the caller; the cause is carried out in `reason`
        return None, f"git status failed ({str(exc).strip()[:80]})"
    if proc.returncode != 0:
        return None, f"git status failed ({proc.stderr.strip()[:80] or 'no detail'})"
    status_output = proc.stdout

    from . import gitstate  # noqa: PLC0415 — lazy keeps this module's import DAG light

    paths: set[str] = set()
    for line in status_output.splitlines():
        parsed = gitstate.parse_porcelain_line(line)
        if parsed is None:
            continue
        _status, src_path, path = parsed
        paths.add(path)
        if src_path:
            paths.add(src_path)
    return sorted(paths), None


def _expand_directory_arguments(
    project_dir: Path, paths: "list[str]"
) -> "tuple[list[str] | None, str | None]":
    """Replace any argument naming a directory with the changed files under it.

    `git add docs/` stages the changed files beneath `docs/`, never an entry
    called `docs/` — so pricing the directory string is pricing something that
    is never committed. It also gets the answer wrong: a directory is neither
    metadata nor ``.md``, so ``is_judgeable_path`` calls it judgeable, and a
    directory holding nothing but doc files is reported as costing a round.

    This is the explicit-argument twin of the ``-uall`` expansion
    ``_working_tree_paths`` already does for the no-argument form; both exist
    so the command prices what a commit would actually contain. A path that is
    not a directory — including one that does not exist yet — is left exactly
    as given, so a builder can price a file before creating it.

    **A git failure here returns ``(None, reason)``, never an empty expansion.**
    Collapsing the two (`_working_tree_paths(...) or []`) made an unreadable
    tree look like a directory holding no changes, which the caller then priced
    as ``free`` — breaking the module's load-bearing asymmetry on the one form
    it was not pinned for, and telling a builder whose `index.lock` is held
    that the commit is free. The no-argument form has always degraded to
    ``unknown``; this is the twin of that guarantee.
    """
    changed: "list[str] | None" = None
    out: list[str] = []
    for path in paths:
        if not (project_dir / path).is_dir():
            out.append(path)
            continue
        if changed is None:
            changed, reason = _working_tree_paths(project_dir)
            if changed is None:
                return None, reason
        prefix = path.rstrip("/") + "/"
        out.extend(p for p in changed if p.startswith(prefix))
    return sorted(set(out)), None


def commit_cost(project_dir: Path, paths: "list[str] | None" = None) -> dict:
    """Does committing these paths cost a review round?

    The builder-facing half of the question the coverage gates answer after
    the fact. It reuses ``coverage_algebra.is_judgeable_path`` rather than
    re-deriving the classification, which is the whole point: an independent
    copy could disagree with the gate that will actually charge for the
    commit, and a pricing tool that is wrong about the price is worse than
    none. There is one predicate, and this asks it.

    ``paths`` omitted reads the working tree — the real question is almost
    always "does committing what I have now cost a round?", and requiring the
    builder to enumerate paths reintroduces the judgement call this removes.

    Returns ``{"source", "paths", "judgeable", "free"}``, or a ``"reason"``
    alongside an empty path list when git could not be read. ``judgeable``
    non-empty means committing buys a round; empty with a non-empty ``paths``
    means the commit is free.

    **Both forms set ``reason`` on a git failure**, and the reason carries the
    cause rather than a fixed string. The argument form reaches git too — a
    directory argument expands through the working tree — so the "unknown,
    never free" asymmetry has to hold on both, not just on the form that was
    pinned for it.
    """
    from . import coverage_algebra  # noqa: PLC0415 — lazy keeps this module's import DAG light

    if paths is None:
        found, reason = _working_tree_paths(project_dir)
        source = "working-tree"
    else:
        given = sorted({p.strip() for p in paths if p.strip()})
        found, reason = _expand_directory_arguments(project_dir, given)
        source = "arguments"
    if found is None:
        return {
            "source": source,
            "paths": [],
            "judgeable": [],
            "free": [],
            "reason": reason or "git status could not be read",
        }
    paths = found

    judgeable = coverage_algebra.judgeable_files(paths)
    judgeable_set = set(judgeable)
    return {
        "source": source,
        "paths": paths,
        "judgeable": judgeable,
        "free": [p for p in paths if p not in judgeable_set],
    }


def cost_of_commit(project_dir: Path, argv: "list[str]") -> int:
    """Body of ``prawduct-hook cost-of-commit [--json] [<paths>...]``.

    Answers, BEFORE the commit, the question a builder could previously only
    answer after making it: does committing this buy a review round? The
    verdict token leads on stdout (the agent-facing channel) so a caller can
    branch on one word; the reasoning follows for a reader.

    Read-only and advisory — it gates nothing, and it exits 0 whether the
    answer is "free" or "costs a round", because both are answers. Exit 1 is
    reserved for bad arguments, and the degraded git path reports ``unknown``
    with its reason rather than a reassuring "free" that would send the
    builder into exactly the commit this exists to price.
    """
    from . import gitstate  # noqa: PLC0415 — lazy keeps this module's import DAG light

    as_json = False
    paths: list[str] = []
    for arg in argv:
        if arg == "--json":
            as_json = True
        elif arg.startswith("-"):
            print(
                f"cost-of-commit: unknown argument {arg!r} "
                "(usage: cost-of-commit [--json] [<paths>...])",
                file=sys.stderr,
            )
            return 1
        else:
            paths.append(arg)

    given_paths = bool(paths)
    cost = commit_cost(project_dir, paths or None)

    # Unguarded, like this module's sibling lazy imports: telemetry ships in
    # the same package, so a failure here is a broken install and an exception
    # is the honest report. Swallowing it would drop the price sentence
    # silently — and a message that goes quiet when it breaks is the failure
    # mode `format_round_price` exists to avoid.
    from . import telemetry  # noqa: PLC0415 — lazy keeps this module's import DAG light

    price = telemetry.round_price(gitstate.get_prawduct_dir(project_dir))
    price_sentence = telemetry.format_round_price(price)

    if cost.get("reason"):
        verdict = "unknown"
    elif not cost["paths"]:
        verdict = "free"
    elif cost["judgeable"]:
        verdict = "costs-a-round"
    else:
        verdict = "free"

    if as_json:
        print(json.dumps({"verdict": verdict, **cost, "round_price": price}, indent=2))
        return 0

    print(verdict)
    if verdict == "unknown":
        print(
            f"Could not price this commit ({cost['reason']}) — that is a missing "
            f"answer, not a free one. Treat it as costing a round until you can re-run."
        )
        return 0
    if not cost["paths"]:
        # Three readings, not two. A directory argument expands to the changed
        # files beneath it, so `cost-of-commit docs/` on a clean `docs/` arrives
        # here WITH arguments and an empty expansion — and "no paths were given"
        # then reads as "your argument was dropped", which is a wrong-tool
        # inference in an advisory whose only value is being trusted.
        if cost["source"] == "working-tree":
            print("Nothing is uncommitted, so there is nothing to price.")
        elif given_paths:
            print(
                "The path(s) given hold no uncommitted change, so there is nothing "
                "to price."
            )
        else:
            print("No paths were given, so there is nothing to price.")
        return 0

    n_judgeable, n_free, n_total = len(cost["judgeable"]), len(cost["free"]), len(cost["paths"])
    if cost["judgeable"]:
        print(
            f"{n_judgeable} of {n_total} path(s) move review coverage — committing them "
            f"re-opens the cumulative Critic gate, and you pay the cheapest round "
            f"that closes it again:"
        )
        for path in cost["judgeable"]:
            print(f"  {path}")
        if cost["free"]:
            print(f"The other {n_free} move no coverage and cost nothing to commit.")
        print(price_sentence)
        print(
            "If these are fixes for findings that gate nothing, committing them is "
            "optional — accepting those findings costs nothing at all."
        )
    else:
        print(
            f"None of the {n_total} path(s) move review coverage — commit them without "
            f"buying a review round."
        )
    return 0
