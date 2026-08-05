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

import subprocess
import sys
from pathlib import Path

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
    diff_fn,
    key_fn,
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
    ``diff_fn`` and ``key_fn`` are required, deliberately, so that omitting one
    is a ``TypeError`` at the call site rather than the silent slow path this
    diagnosis cannot afford (see the comment at the ``coverage_verdict`` call).
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
    # `diff_fn`/`key_fn` are threaded in and REQUIRED rather than defaulted:
    # without a `key_fn`, `_find_path` takes the pairwise free-edge branch,
    # which `_tree_key_fn`'s own docstring measures on this repo's store at
    # ~5.6k `git diff` subprocesses — twice per verdict, with no memo between
    # the passes. This runs on the interactive `/prawduct:pr create` path,
    # inside a diagnosis the gate message calls "the cheap check", so it has to
    # use the n-key form every other gate uses. A caller that forgets one is a
    # `TypeError` at the call site, which is the failure a maintainer can see —
    # the defaults made it a silent ~5-minute hang instead.
    upstream = coverage_algebra.coverage_verdict(
        facts, base_tree, anchor_tree, diff_fn, key_fn
    )
    # Known gap, accepted: a `diff_fn` that fails renders here as "nothing
    # composes", the same shape the status split above exists to separate.
    # Distinguishing them needs the failure surfaced through `coverage_verdict`
    # itself, which every gate shares — a wider change than this diagnosis, and
    # the failure direction is the safe one (silence, not a false claim).
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
    (one of the divergent doc-only sites behind CRT-5D8Q). A
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

    return True, (
        f"doc-only: {len(files)} file(s) in {base}...HEAD, none judgeable"
    )


_CHANGE_LOG_REL_PATH = ".prawduct/change-log.md"


def check_change_log_entry(project_dir: Path) -> int:
    """PR-boundary probe: a code-changing branch must add a change-log entry.

    A branch whose ``merge-base...HEAD`` diff touches any non-``.md`` file is
    code-changing work that the release flow can only ship if a change-log
    entry exists for it — historically nothing checked this, so a branch could
    merge with NO entry and the gap surfaced only at release reconstruction
    (REL-6C3W — CRT-7B4M/#82, found at the v2.0.16 release). The
    `/prawduct:pr` Create flow (Step 1c) runs this probe and STOPs on failure.

    Exit 0 when:
      * the diff is empty or all-``.md`` (doc-only work needs no entry), or
      * a non-``.md`` diff includes ``.prawduct/change-log.md`` AND that diff
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
    non_md = [f for f in files if not f.endswith(".md")]
    if not files:
        print(f"empty-diff: no files changed in {base}...HEAD — no entry required.")
        return 0
    if not non_md:
        print(f"doc-only: all {len(files)} changed file(s) are .md — no entry required.")
        return 0

    if _CHANGE_LOG_REL_PATH not in files:
        sample = ", ".join(non_md[:3])
        more = f" (+{len(non_md) - 3} more)" if len(non_md) > 3 else ""
        print(
            f"no-entry: branch changes code ({sample}{more}) but "
            f"{_CHANGE_LOG_REL_PATH} is untouched — add a change-log entry for "
            f"this work before opening the PR.",
            file=sys.stderr,
        )
        return 1

    proc2 = subprocess.run(
        ["git", "diff", f"{base}...HEAD", "--", _CHANGE_LOG_REL_PATH],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc2.returncode != 0:
        print(
            f"git-failed: git diff of {_CHANGE_LOG_REL_PATH} failed: "
            f"{proc2.stderr.strip()}. Check the change-log by hand.",
            file=sys.stderr,
        )
        return 1
    added_header = any(
        line.startswith("+## ") for line in proc2.stdout.splitlines()
    )
    if not added_header:
        print(
            f"entry-edited-not-added: {_CHANGE_LOG_REL_PATH} changed but no new "
            f"entry header (+## ...) was added — editing an existing entry does "
            f"not vouch for this branch's code changes.",
            file=sys.stderr,
        )
        return 1

    print(f"entry-present: {_CHANGE_LOG_REL_PATH} adds a new entry in {base}...HEAD.")
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
