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
from fnmatch import fnmatch
from pathlib import Path

from . import buildplan_refs
from .core import read_list_yaml_key, read_str_yaml_key

_BASE_BRANCH_KEY = "base_branch"
_DEFAULT_BASE_CANDIDATES = ("origin/main", "main", "HEAD~1")

# Extensions whose files carry no executable behavior the symbol-grep coverage
# floor can vouch for — prose docs and non-code config. A changed file with one
# of these is exempt from the BLOCKING floor and reported as an informational
# NOTE instead (COV-8R2K), so a docs/config-only change on an otherwise-clean
# tree no longer forces a waiver or a token reference-test. This generalizes the
# ``.md`` carve-out the PR doc-only fast path (``_pr_diff_is_doc_only``) already
# applies; that gate's stricter ``.md``-only contract is deliberately unchanged
# (a doc-only PR is a narrower claim than a coverage-floor exemption).
_NON_EXECUTABLE_EXTENSIONS = frozenset({
    ".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".txt",
})

# Optional project-state override: extra glob patterns whose matching files are
# also treated as non-executable. The safe default (the extension set above)
# needs a config seam so a repo can exempt a path whose extension *looks*
# executable but isn't (a generated ``.py`` fixture, vendored data) without
# neutralizing the whole floor — the anti-"opinionated default" escape hatch.
_COVERAGE_EXEMPT_PATHS_KEY = "coverage_exempt_paths"


def is_non_executable_path(
    path: str, *, exempt_globs: tuple[str, ...] = ()
) -> bool:
    """True when ``path`` carries no executable behavior the coverage floor can
    judge: a prose/config file by extension (``_NON_EXECUTABLE_EXTENSIONS``), or
    a repo-relative path matching one of the optional ``exempt_globs``.

    ``exempt_globs`` is the project-configured override (see
    :func:`coverage_exempt_globs`); matching is ``fnmatch`` over the repo-
    relative path, so ``generated/*`` or ``vendor/*`` exempt those subtrees.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _NON_EXECUTABLE_EXTENSIONS:
        return True
    return any(fnmatch(path, pattern) for pattern in exempt_globs)


def coverage_exempt_globs(project_dir: Path) -> tuple[str, ...]:
    """The optional ``coverage_exempt_paths:`` override from project-state.yaml —
    extra glob patterns whose matching files :func:`is_non_executable_path`
    treats as non-executable. Empty tuple when the key is unset or empty.
    """
    declared = read_list_yaml_key(
        project_dir / ".prawduct" / "project-state.yaml", _COVERAGE_EXEMPT_PATHS_KEY
    )
    return tuple(declared) if declared else ()


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
    when the diff is non-empty, every file ends in ``.md``, AND no file is
    governance-protected (``skills/``, ``methodology/``, ``templates/``,
    root ``CLAUDE.md`` — PR-5K8D). The status
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

    # Governance-protected paths are never doc-only even as .md: fork-skill
    # prose, methodology, and templates ARE behavioral logic here, so a
    # skills/*.md change must not skip the reviewers (PR-5K8D). Same bound
    # list as the Type: trivial gate — one source of truth.
    protected = [
        v for f in files if (v := buildplan_refs.protected_path_violation(f))
    ]
    if protected:
        sample = "; ".join(protected[:3])
        more = f" (+{len(protected) - 3} more)" if len(protected) > 3 else ""
        return False, f"not-doc-only: governance-protected paths in PR: {sample}{more}"

    return True, f"doc-only: {len(files)} file(s) in {base}...HEAD all .md"


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

    Exit 0 when every file in ``merge-base...HEAD`` ends in ``.md`` and the
    diff is non-empty — the `/prawduct:pr` skill uses this to skip the cumulative-
    Critic and PR-reviewer gates, mirroring the session-end stop-hook
    behavior (`_session_changes_are_doc_only`) at the PR boundary. The
    stop hook's PR-review evidence gate (Gate 3) consults the same helper
    so a doc-only PR doesn't get blocked at session end for missing
    evidence — symmetric behavior across both gates.

    Exit 1 otherwise (any non-``.md`` file, any governance-protected path —
    skill/methodology/template prose is behavioral logic, never "docs" —
    empty diff, no resolvable base branch, or git failure). Fails closed:
    when the gate cannot be evaluated, fall through to the full review path
    rather than silently skipping it.
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
