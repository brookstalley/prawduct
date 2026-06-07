"""Diff-base resolution + coverage / PR fast-path gates for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 5) — the diff-base
resolution layer (honoring the ``base_branch:`` gitflow knob) and the coverage /
PR fast-path inspection it feeds: which files changed against the base, whether a
PR diff is documentation-only, and whether every commit on the branch is
``Type: trivial`` fileset-eligible. Pure git inspection + path classification —
no mutation.

Depends on its lib siblings ``core`` (for ``read_str_yaml_key`` — the canonical
twin of the hook's parity-pinned inline mirror, reached directly as
``critic_mode``/``views``/``buildplan_refs`` do) and ``buildplan_refs`` (for
``_classify_trivial_change``), plus the stdlib — a clean DAG node
(``buildplan_refs`` ← ``coverage``). The hook calls these lazily via
``_coverage()``, keeping its top level lib-free (ch.1 isolation invariant).

The two coverage/critic *gate commands* that consume this layer
(``cmd_verify_coverage`` / ``cmd_check_cumulative_critic``) stay in the hook for
now: their bodies also depend on the evidence-schema / critic-findings validators
slated for Chunk 6 (``gates``), and the plan's DAG runs ``coverage`` ← ``gates``
— so they move with ``gates`` (where ``gates`` → ``coverage`` is legal) rather
than pulling gates logic forward into this module. The two *PR fast-path* gate
commands (``check_pr_doc_only`` / ``check_pr_trivial``) are gates-free and move
here; the hook keeps thin ``cmd_*`` wrappers delegating to them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import buildplan_refs
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
    """Shared helper: is the PR diff (``merge-base...HEAD``) all ``.md``?

    Returns ``(is_doc_only, status_message)``. ``is_doc_only`` is True only
    when the diff is non-empty AND every file ends in ``.md``. The status
    message names the specific reason for False (``no-base``, ``git-failed``,
    ``empty-diff``, ``not-doc-only: <files>``) so both the CLI gate and the
    stop-hook Gate 3 can surface actionable detail without re-implementing
    the diff inspection. Base resolution mirrors ``_coverage_resolve_base``
    so the helper sees the same diff surface as the cumulative-Critic flow.
    """
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

    non_md = [f for f in files if not f.endswith(".md")]
    if non_md:
        sample = ", ".join(non_md[:3])
        more = f" (+{len(non_md) - 3} more)" if len(non_md) > 3 else ""
        return False, f"not-doc-only: PR includes non-.md files: {sample}{more}"

    return True, f"doc-only: {len(files)} file(s) in {base}...HEAD all .md"


def _pr_diff_is_trivial(project_dir: Path) -> tuple[bool, str]:
    """Shared helper: is every commit on ``merge-base...HEAD`` fileset-
    eligible per Chunk 04's ``Type: trivial`` path bounds?

    Returns ``(is_trivial, status_message)``. ``is_trivial`` is True only
    when at least one commit exists ahead of base AND every commit's
    file changes satisfy ``_classify_trivial_change``. The first
    violating commit short-circuits with a reason naming the SHA and
    the specific bound (e.g.
    ``"not-trivial: commit a1b2c3d skill-file-edited: skills/foo.md"``).

    Mirrors ``_pr_diff_is_doc_only`` at the PR boundary — same base
    resolution via ``_coverage_resolve_base``, same fail-closed posture
    on missing base / git failure / empty diff. Does NOT re-validate
    rationale fit; that's the per-chunk Critic's job at chunk-mode
    review time. This helper trusts that every chunk's rationale was
    Critic-passed and only checks the structural file-set bounds.

    Per-commit (not cumulative) walk: a PR that adds an ``skills/``
    file in commit 1 and removes it in commit 2 has an empty cumulative
    diff but is NOT fast-path eligible — the commit 1 violation is
    real signal that the work crossed a catastrophic-blast-radius
    boundary at least once during the build.
    """
    base, base_note = _coverage_resolve_base(project_dir)
    if base is None:
        return False, f"no-base: {base_note}"

    # `git log --name-status --format=%H` emits one commit SHA per line
    # followed by one tab-separated <status>\t<path> (or
    # <status>\t<src>\t<dst> for renames) line per changed file, with
    # a blank line between commits. Reverse order is irrelevant — we
    # short-circuit on first violation regardless.
    proc = subprocess.run(
        [
            "git",
            "log",
            "--name-status",
            "-M",  # enable rename detection so test-renamed-out-of-tests/ trips
            "--format=%H",
            f"{base}..HEAD",
        ],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return False, f"git-failed: git log {base}..HEAD failed: {proc.stderr.strip()}"

    lines = proc.stdout.splitlines()
    if not any(line.strip() for line in lines):
        return False, f"empty-diff: no commits ahead of {base}"

    current_sha: str | None = None
    commits_seen = 0
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        # A bare 40-hex line is a commit header.
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            current_sha = line
            commits_seen += 1
            continue
        # Otherwise it's a name-status entry for the current commit.
        if current_sha is None:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()
        if not status:
            continue
        # R<score> / C<score> rows are: <status>\t<src>\t<dst>
        src_path: str | None = None
        if status[0] in ("R", "C") and len(parts) >= 3:
            src_path = parts[1].strip()
            path = parts[2].strip()
        else:
            path = parts[-1].strip()
        if not path:
            continue
        # v1.5.1 Chunk 04(b): metadata-path filtering lives inside
        # `_classify_trivial_change` (handles both src and dst). Single
        # check site = no drift between this PR-boundary gate and the
        # stop-hook gate in `_is_trivial_fileset_eligible`.
        is_addition = status == "A"
        is_deletion = status == "D"
        violation = buildplan_refs._classify_trivial_change(
            path=path,
            src_path=src_path,
            is_addition=is_addition,
            is_deletion=is_deletion,
        )
        if violation is not None:
            return False, f"not-trivial: commit {current_sha[:7]} {violation}"

    return True, (
        f"trivial: {commits_seen} commit(s) ahead of {base} all fileset-eligible"
    )


def check_pr_doc_only(project_dir: Path) -> int:
    """Fast-path gate for `/prawduct:pr create`: report whether the PR diff is doc-only.

    Exit 0 when every file in ``merge-base...HEAD`` ends in ``.md`` and the
    diff is non-empty — the `/prawduct:pr` skill uses this to skip the cumulative-
    Critic and PR-reviewer gates, mirroring the session-end stop-hook
    behavior (`_session_changes_are_doc_only`) at the PR boundary. The
    stop hook's PR-review evidence gate (Gate 3) consults the same helper
    so a doc-only PR doesn't get blocked at session end for missing
    evidence — symmetric behavior across both gates.

    Exit 1 otherwise (any non-``.md`` file, empty diff, no resolvable base
    branch, or git failure). Fails closed: when the gate cannot be evaluated,
    fall through to the full review path rather than silently skipping it.
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


def check_pr_trivial(project_dir: Path) -> int:
    """Fast-path gate for `/prawduct:pr create`: report whether every commit in
    ``merge-base...HEAD`` is fileset-eligible per Chunk 04's
    ``Type: trivial`` path bounds.

    Exit 0 when at least one commit exists ahead of base AND every
    commit clears the bounds — the `/prawduct:pr` skill skips the cumulative-
    Critic and PR-reviewer gates in this case. This is the PR-boundary
    parallel to the doc-only fast-path: same fail-closed shape, same
    Gate-3 alignment at session end.

    Exit 1 otherwise (any commit touches ``skills/``/``methodology/``/
    ``templates/``/``CLAUDE.md``, adds a new file, removes a test
    file, empty diff, no resolvable base, or git failure). Fails
    closed: when the gate cannot be evaluated, fall through to the
    full review path rather than silently skipping it.
    """
    is_trivial, status = _pr_diff_is_trivial(project_dir)
    if is_trivial:
        print(
            f"{status} — cumulative-Critic and PR-reviewer gates may be skipped."
        )
        return 0
    suffix = (
        ". Trivial fast-path is not applicable."
        if status.startswith("empty-diff")
        else ". Falling back to full review path."
        if status.startswith(("no-base", "git-failed"))
        else ". Full review required."
    )
    print(f"{status}{suffix}", file=sys.stderr)
    return 1
