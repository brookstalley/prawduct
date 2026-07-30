"""Read-only git + repository-state probes for the prawduct runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 2) — the leaf of the hook
decomposition: every other extracted module depends on these probes, and this
module depends on nothing but the standard library. Pure inspection only — no
mutation of git state (the session-start ``git rm --cached`` untracking stays in
the hook). The hook imports this lazily inside the functions that use it
(``_gitstate()``), keeping the hook's top level lib-free; after the Chunk-1
``lib/__init__`` slim, ``from lib import gitstate`` loads only this module.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def get_prawduct_dir(project_dir: Path) -> Path:
    """``.prawduct/`` under the project dir. Local copy of the hook's bootstrap
    helper so this module stays self-contained (lib never imports from bin/)."""
    return project_dir / ".prawduct"


def _git_toplevel(cwd: Path) -> Path | None:
    """Resolved ``git rev-parse --show-toplevel`` from ``cwd``.

    Returns the work-tree root (the session's *worktree* root when ``cwd`` is
    inside one), or ``None`` when ``cwd`` is not in a git work tree / git is
    unavailable. Never raises — git failures fall through to ``None`` so callers
    can apply their fallback."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        out = result.stdout.strip()
        return Path(out).resolve() if out else None
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        return None


def git_common_dir(cwd: Path) -> Path | None:
    """Resolved shared git common dir for the repo at ``cwd``, or ``None``.

    Public: the kernel-v3 evidence store keys its location off this path
    (kernel-v3-evidence-design.md D1), so it is a load-bearing contract, not
    an internal helper.

    Worktrees of one repository share a single common dir (the real ``.git``),
    so equality of this path is the identity test for "same repository". The
    git output is relative to ``cwd`` in the primary checkout and absolute in a
    linked worktree; ``Path(cwd) / out`` normalizes both (an absolute right
    operand discards the left in pathlib)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        out = result.stdout.strip()
        if not out:
            return None
        return (Path(cwd) / out).resolve()
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        return None


def resolve_project_dir(env_project_dir: str | None, cwd: Path) -> Path:
    """Resolve the project root to the session's *active git worktree*.

    The harness pins ``CLAUDE_PROJECT_DIR`` to where ``claude`` was launched (the
    primary checkout). A session that moves into a git worktree (``EnterWorktree``
    / ``cd``) operates — and the agent-side skills already write ``.prawduct/``
    state — from the worktree's cwd. If the hooks kept resolving against the
    launch dir, hook-read state and agent-written state would land in *different*
    ``.prawduct/`` trees, breaking the Stop / cumulative-critic / critic-mode
    gates for worktree work (STH-4K7N). Resolving here against the worktree
    toplevel of ``cwd`` keeps both sides on the same tree.

    Resolution:
      1. If ``cwd`` is not in a git work tree → ``env_project_dir`` (today's
         behavior), or ``cwd`` when the env var is unset.
      2. If the env pin is unset → the work-tree toplevel of ``cwd``.
      3. If the toplevel equals the env pin → the env pin (single-checkout
         fast path; also normalizes launch-in-subdirectory). This is the no-op
         common case.
      4. Otherwise ``cwd``'s work tree differs from the launch dir: follow it
         only when it is a worktree of the *same* repository (shared
         ``--git-common-dir``); an unrelated repo at ``cwd`` honors the env pin.

    Never raises (lib error-handling convention) — every git probe fails open to
    a path."""
    cwd = Path(cwd).resolve()
    env_dir = Path(env_project_dir).resolve() if env_project_dir else None
    top = _git_toplevel(cwd)

    if top is None:
        return env_dir if env_dir is not None else cwd
    if env_dir is None:
        return top
    if top == env_dir:
        return env_dir
    common_cwd = git_common_dir(cwd)
    if common_cwd is not None and common_cwd == git_common_dir(env_dir):
        return top  # worktree of the same repo — follow the session
    return env_dir  # unrelated repo (or undeterminable) — honor the launch pin


def git_status_output(project_dir: Path) -> str | None:
    """Return raw `git status --porcelain` output, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        return None


def current_branch(project_dir: Path) -> str | None:
    """The current branch name, ``None`` on a detached HEAD or git failure.

    Used to make the tree a review resolved to VISIBLE (PDT-WT9K) — a silent
    wrong-tree review is the failure this surfaces, so a detached/failed probe
    returns ``None`` rather than a misleading value."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        return branch or None
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        return None


def git_has_changes(project_dir: Path, status_output: str | None = None) -> str:
    """Check if there are uncommitted changes. Returns first changed file or empty string.

    ``status_output`` lets a hot-path caller pass a single ``git status --porcelain``
    capture so the family of probes shares one subprocess (STH-6Q9D); ``None`` (the
    default) computes it, so every existing caller is unaffected.
    """
    output = status_output if status_output is not None else git_status_output(project_dir)
    if output is None:
        return ""
    lines = output.strip().splitlines()
    return lines[0] if lines else ""


# Paths that are framework/session metadata — changes to these should
# never trigger reflection or Critic gates. Plugin-only: product-owned state
# and the committed install reference. The file-sync-era entries
# (``.claude/skills/`` for synced framework skills, ``tools/product-hook``)
# are intentionally absent — a plugin repo never carries them, and a
# product's *own* skill under ``.claude/skills/`` is product code that must
# be gated, not excused. The single canonical copy — ``lib/critic_mode.py``'s
# mirror was consolidated onto this one (STH-2K8R). Public: the kernel-v3
# coverage algebra's judgeability predicate keys off it (chunk 02), so it is
# a load-bearing contract like ``git_common_dir``.
METADATA_PREFIXES = (
    ".prawduct/",
    ".claude/settings.json",
)


def _is_metadata_path(filepath: str) -> bool:
    """Check if a file path is framework/session metadata (not user code)."""
    return any(filepath.startswith(p) for p in METADATA_PREFIXES)


def parse_porcelain_line(line: str) -> tuple[str, str | None, str] | None:
    """Parse one ``git status --porcelain`` line into ``(status, src_path, path)``.

    Git QUOTES paths containing spaces or special characters (`` M "my doc.md"``)
    and renders renames as ``R  old -> new`` — a naive ``line.split()[-1]`` returns
    ``doc.md"`` for the quoted form, which made the doc-only classification fail on
    the trailing quote and falsely block doc-only sessions at the Critic/reflection
    gates (review-fixes Chunk 1). ``src_path`` is the rename source (None for
    non-renames); ``path`` is the current/destination path, quote-stripped.
    Returns None for blank or malformed lines. Two accepted caveats, both
    classification-only impact: octal escapes inside quoted paths (non-ASCII
    filenames) are left as-is — quote-stripping is sufficient for path
    *classification* by prefix/suffix, which is all the callers do; and a
    quoted rename SOURCE itself containing ``" -> "`` mis-splits at the first
    arrow (vanishingly rare, still strictly better than the ``split()[-1]``
    parse this replaced).
    """
    if len(line) < 4:
        return None
    status = line[:2]
    raw = line[3:].strip()
    src_path: str | None = None
    if " -> " in raw:
        src_raw, dst_raw = raw.split(" -> ", 1)
        src_path = src_raw.strip()
        if src_path.startswith('"') and src_path.endswith('"'):
            src_path = src_path[1:-1]
        raw = dst_raw.strip()
    path = raw
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    if not path:
        return None
    return status, src_path, path


def git_has_session_changes(project_dir: Path, status_output: str | None = None) -> str:
    """Check if non-metadata uncommitted changes differ from session baseline.

    Compares current git status to the baseline captured at session start.
    Ignores .prawduct/ metadata and framework-managed files.
    Returns first new changed file or empty string. Falls back to
    git_has_changes if no baseline exists (backward compat).

    ``status_output`` (STH-6Q9D): an optional pre-captured ``git status
    --porcelain`` snapshot to reuse instead of spawning git again; ``None``
    computes it (unchanged default behavior).
    """
    prawduct_dir = get_prawduct_dir(project_dir)
    baseline_path = prawduct_dir / ".session-git-baseline"

    if not baseline_path.is_file():
        return git_has_changes(project_dir, status_output)

    current = status_output if status_output is not None else git_status_output(project_dir)
    if current is None:
        return ""

    try:
        baseline = baseline_path.read_text()
    except (UnicodeDecodeError, OSError):
        return ""  # Corrupted baseline — treat as no baseline (safe: permits session end)
    # No whole-output .strip(): it eats the FIRST line's leading status space
    # (" M x" → "M x"), corrupting the fixed-offset porcelain parse. Both sides
    # unstripped, matching the trivial gate's reads (review-fixes Chunk 1).
    baseline_lines = set(baseline.splitlines())
    current_lines = current.splitlines()

    for line in current_lines:
        if line not in baseline_lines:
            parsed = parse_porcelain_line(line)
            if parsed and not _is_metadata_path(parsed[2]):
                return line

    return ""


# _session_changes_are_doc_only moved to lib/gates.py as
# session_changes_all_non_judgeable (kernel-v3 chunk 04): the "doc-only"
# question is now answered by THE judgeability predicate
# (coverage_algebra.is_judgeable_path), and coverage_algebra sits above this
# module in the import DAG.


def git_has_code_changes(project_dir: Path, status_output: str | None = None) -> bool:
    """Check if non-metadata files were modified since session baseline.

    Mirrors git_has_session_changes() baseline-diff logic but returns a bool.
    Skips files that match the session baseline (pre-existing dirt) and
    framework metadata (.prawduct/, .claude/settings.json, etc.).
    ``status_output`` (STH-6Q9D): optional pre-captured porcelain snapshot.
    """
    return bool(git_has_session_changes(project_dir, status_output))


def _is_framework_tooling(f: Path, project_dir: Path) -> bool:
    """True if ``f`` is Prawduct framework infrastructure shipped into a product
    repo (``tools/product-hook`` or ``tools/lib/*``), not the product's own code.

    Used by the "has product code?" heuristic so that sync-delivered tooling
    doesn't make a freshly-initialized empty repo look like it contains source.
    Deliberately NOT used by the compliance canary's source detection: in the
    framework repo itself these paths ARE the source under test.
    """
    try:
        rel = f.relative_to(project_dir).as_posix()
    except ValueError:
        return False
    return rel == "tools/product-hook" or rel.startswith("tools/lib/")


# Suffixes that count as the product's own source code. Shared by the
# project-preferences CRITICAL (cmd_clear) and the discovery-capture probe
# (lib/coverage_probes.probe_discovery_not_captured).
_PRODUCT_CODE_SUFFIXES = (
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".swift", ".kt",
    ".c", ".cpp", ".h",
)


# Directory names pruned from the product-code walk (STH-6Q9D): never descend
# into them. ``node_modules``/``.git`` can hold tens of thousands of files the old
# ``rglob`` enumerated before the per-file filter discarded them; ``.prawduct`` is
# framework state. ``node_modules`` and ``.prawduct`` were already excluded by the
# prior filter; ``.git`` is added — it never holds product source, so the verdict
# is unchanged while the heaviest tree (``.git/objects``) is no longer walked.
_PRODUCT_WALK_PRUNE_DIRS = frozenset({".prawduct", "node_modules", ".git"})


def _has_product_code(project_dir: Path) -> bool:
    """True if the repo contains the product's OWN source code — not framework
    tooling, not ``.prawduct/`` state, not vendored deps. The single definition
    behind both the project-preferences CRITICAL and the discovery-capture nudge.

    Prunes ``node_modules``/``.git``/``.prawduct`` at the directory level
    (STH-6Q9D) so a large ``node_modules`` is never enumerated, and short-circuits
    on the first product-code file — same verdict as the prior ``rglob`` + filter.
    """
    for dirpath, dirnames, filenames in os.walk(str(project_dir)):
        # Prune in place so os.walk never descends into excluded trees.
        dirnames[:] = [d for d in dirnames if d not in _PRODUCT_WALK_PRUNE_DIRS]
        for name in filenames:
            if name == "conftest.py":
                continue
            f = Path(dirpath) / name
            if f.suffix in _PRODUCT_CODE_SUFFIXES and not _is_framework_tooling(
                f, project_dir
            ):
                return True
    return False


# Conventional documentation roots prawduct recognizes — CLAUDE.md (and the
# MIG-6B0R backlog item) both name docs/ and documentation/ as real product-doc
# trees worth keeping on deploy-to-main.
_DOC_ROOTS = ("docs", "documentation")


def _has_product_definition_work(project_dir: Path) -> bool:
    """True if the repo shows deliberate product-definition work — source code OR
    markdown under a documentation root (``docs/`` or ``documentation/``).
    Distinguishes a repo someone has started building or specifying (worth a
    discovery nudge) from a freshly-onboarded empty repo (silent). A doc root is a
    deliberate user creation — ``init-product`` never scaffolds one — so markdown
    there is a real "product work happened" signal.
    """
    if _has_product_code(project_dir):
        return True
    for root in _DOC_ROOTS:
        d = project_dir / root
        if d.is_dir() and any(p.suffix == ".md" for p in d.rglob("*") if p.is_file()):
            return True
    return False


def _discovery_uncaptured(state_path: Path) -> bool:
    """True if ``project-state.yaml`` still carries BOTH template sentinels for the
    canonical discovery outputs — ``classification.domain`` and
    ``product_definition.vision`` both ``null``. Discovery filling either one
    clears its sentinel, so requiring BOTH is conservative: it fires only when
    discovery clearly never ran, never mid-discovery. Mirrors the parser-free
    substring heuristic the project-preferences unfilled check uses.
    """
    try:
        content = state_path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    return "\n  domain: null\n" in content and "\n  vision: null\n" in content


def _read_advisory_store(prawduct_dir: Path) -> dict:
    """Read `.prawduct/.advisories.json` (the post-sync nag log).

    Dependency-light standalone reader: the briefing parses the store directly
    rather than importing the bundled advisory_store, so the hot path stays
    robust even on an incomplete plugin install. (cmd_clear's probe step DOES
    import advisory_store to refresh this file before the briefing is assembled.)
    Missing/unreadable/malformed → empty store; never raises (briefing must not
    break on a bad file).
    """
    path = prawduct_dir / ".advisories.json"
    if not path.is_file():
        return {"schema_version": 1, "advisories": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "advisories": []}
    if not isinstance(data, dict) or not isinstance(data.get("advisories"), list):
        return {"schema_version": 1, "advisories": []}
    return data


def _git_head_sha(project_dir: Path) -> str:
    """Return current HEAD SHA, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        pass
    return ""


def git_path_is_ignored(project_dir: Path, rel_path: str) -> bool:
    """True if ``rel_path`` is git-ignored within ``project_dir``.

    Used by the build-plan ref-existence check so an intentionally-gitignored
    managed path (e.g. ``.prawduct/.bug-inbox``) is not flagged as a missing
    deliverable (BLD-4K7P) — such paths are generated/managed and legitimately
    absent from a fresh checkout. Fail-closed: ``git check-ignore`` exits 0 when
    ignored, 1 when not, and 128 on error (e.g. not a git repo); any non-zero or
    exception returns False ("couldn't prove it's ignored"), so a genuinely
    missing path is still flagged rather than silently passed.
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel_path],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        return result.returncode == 0
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash the ref check
        return False


def git_paths_ignored(project_dir: Path, rel_paths: "list[str]") -> "set[str]":
    """The git-ignored subset of ``rel_paths``, in ONE ``git check-ignore`` call.

    The batched sibling of :func:`git_path_is_ignored`, for callers on the
    session-start hot path where a subprocess per candidate would be the cost —
    ``clear`` was deliberately taken from 25 git subprocesses to 11, and a
    per-path loop here would put that back on a large monorepo.

    Same fail-closed direction as the single-path form: any error, timeout, or
    unparseable output returns the empty set ("couldn't prove anything is
    ignored"), so a caller that skips ignored paths keeps reporting rather than
    silently dropping them. ``check-ignore`` exits 0 when something matched, 1
    when nothing did, and 128 on error; only 0 carries output worth reading.
    """
    if not rel_paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            input="\0".join(rel_paths),
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash a best-effort scan
        return set()
    if result.returncode != 0:
        return set()
    return {p for p in result.stdout.split("\0") if p}


def _get_session_changed_files(project_dir: Path, status_output: str | None = None) -> list[str]:
    """Get files changed since session start. Returns list of file paths.

    ``status_output`` (STH-6Q9D): optional pre-captured porcelain snapshot to
    reuse; ``None`` computes it (unchanged default).
    """
    prawduct_dir = get_prawduct_dir(project_dir)
    current = status_output if status_output is not None else git_status_output(project_dir)
    if current is None:
        return []

    baseline_path = prawduct_dir / ".session-git-baseline"
    baseline_lines: set[str] = set()
    if baseline_path.is_file():
        try:
            # Unstripped on both sides — see git_has_session_changes.
            baseline_lines = set(baseline_path.read_text().splitlines())
        except (UnicodeDecodeError, OSError):
            pass  # Corrupted baseline — same stance as the sibling readers above
    changed = []
    for line in current.splitlines():
        if line and line not in baseline_lines:
            parsed = parse_porcelain_line(line)
            if parsed:
                changed.append(parsed[2])
    return changed
