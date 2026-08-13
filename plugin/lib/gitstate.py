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
import re
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


# A disposable worktree's directory basename (Claude Code's Agent tool with
# `isolation: "worktree"`) and its branch. Both are observed harness output, and
# both are required to carry the literal `agent-` prefix plus a hex tail.
#
# The prefix is doing load-bearing work, not decoration. `EnterWorktree` creates
# its worktrees under the SAME `.claude/worktrees/` parent, and those are
# legitimate, user-requested, long-lived session worktrees that must keep being
# governed normally. Matching on the parent directory alone — the detection the
# source bug report proposed — would silence governance in every one of them,
# which is a worse failure than the silent strand this predicate exists to
# close. The parent is therefore necessary but never sufficient.
#
# The DIRECTORY is likewise necessary but not sufficient for `agent-`: the
# branch decides, because the branch is what carries a write out of the tree.
# `is_ephemeral_worktree` owns that reasoning; the two patterns below are only
# the harness's naming.
_EPHEMERAL_DIR_PATTERNS = (
    (re.compile(r"^agent-[0-9a-f]{6,}$"), "agent"),
    (re.compile(r"^wf_[0-9a-z_-]{4,}$", re.IGNORECASE), "workflow"),
)
_EPHEMERAL_BRANCH_PATTERN = re.compile(r"^worktree-agent-[0-9a-f]{6,}$")


def _under_claude_worktrees(project_dir: Path) -> bool:
    """True when some ancestor pair of ``project_dir`` is ``.claude/worktrees``.

    Pure string work on an already-resolved path — no filesystem access and no
    subprocess. This is deliberately the FIRST test in
    :func:`is_ephemeral_worktree` so the common case (every session that is not
    inside a harness-managed worktree) costs nothing on the hook's hot path.
    """
    parts = project_dir.parts
    return any(
        parts[i] == ".claude" and parts[i + 1] == "worktrees"
        for i in range(len(parts) - 2)
    )


def _dir_label(name: str) -> str | None:
    """``"agent"``/``"workflow"``/``None`` from a worktree's basename alone.

    One body for every caller of :data:`_EPHEMERAL_DIR_PATTERNS`, so the
    directory half can never be spelled two ways.
    """
    for pattern, label in _EPHEMERAL_DIR_PATTERNS:
        if pattern.match(name):
            return label
    return None


def ephemeral_kind_of(path: str | Path, branch: str | None) -> str | None:
    """Classify a worktree from its path and branch — no git, no filesystem.

    THE decision function. :func:`is_ephemeral_worktree` probes git for the
    branch and delegates here; :func:`ephemeral_worktree_kind_of_path` passes
    ``branch=None``. Both answers therefore come from one body, which is what
    keeps a live tree and the historical record of that same tree from
    disagreeing about whether it was disposable (#648).

    ``branch=None`` means *unknown or none* — a detached HEAD, a failed probe,
    or a stored record that predates branch capture. It resolves to the
    restrictive answer for an ``agent-`` path: such a tree has no branch that
    could carry a write out, a failing probe must not become a way to unlock
    the guard, and every agent-path fact recorded before this change was in
    fact disposable (the guard refused the durable case), so historical records
    keep exactly the reading they had.

    Why the branch decides at all, and why only for ``agent-``, is in
    :func:`is_ephemeral_worktree`.
    """
    try:
        candidate = Path(path)
    except TypeError:
        return None
    if not _under_claude_worktrees(candidate):
        return None
    dir_label = _dir_label(candidate.name)
    if dir_label == "workflow":
        return "workflow"
    # Normalize `branch` HERE, not in each caller. `path` is already defended
    # two lines up, and a decision function that guards one argument but not
    # the other invites exactly the caller that forgets. A non-string reaches
    # the same answer as absent — the restrictive side — so a malformed field
    # can never promote a disposable tree to durable.
    if not isinstance(branch, str) or not branch:
        branch = None
    scratch = branch is not None and _EPHEMERAL_BRANCH_PATTERN.match(branch) is not None
    if dir_label == "agent":
        return "agent" if (branch is None or scratch) else None
    return "agent" if scratch else None


def ephemeral_worktree_kind_of_path(path: str | Path) -> str | None:
    """Classify a worktree PATH alone as disposable, with no branch to consult.

    Exists for readers that must classify a path they cannot probe: an evidence
    fact records ``actor.worktree`` as a string, and by the time anyone reads it
    that worktree is usually deleted, so no live git probe is possible. Path
    shape is the only signal that survives the tree it describes.

    Prefer :func:`ephemeral_kind_of` wherever a recorded branch IS available —
    since #648 the path alone cannot distinguish a disposable agent worktree
    from a durable one, so this answers the restrictive default for both.
    """
    return ephemeral_kind_of(path, None)


def is_ephemeral_worktree(project_dir: Path) -> str | None:
    """``"agent"``/``"workflow"`` when ``project_dir`` is a DISPOSABLE worktree,
    else ``None``.

    Claude Code gives a subagent dispatched with ``isolation: "worktree"`` — and
    a workflow stage — its own git worktree forked from HEAD, of which only the
    code commit is ever merged back. Such a tree is not a peer checkout:
    everything tracked in it is a HEAD snapshot (so a dispatcher's uncommitted
    governing artifacts are invisible there), and anything written into its
    ``.prawduct/`` dies at merge with no trace. :func:`resolve_project_dir`
    resolves it correctly and has no way to know it is disposable; this is that
    missing predicate.

    Distinct from the cross-worktree mismatch guarded separately (issue #221):
    that asks "is this the session's active worktree", which needs persisted
    session-scoped state. This asks "is this worktree disposable", which is a
    property of the tree itself — true even when it IS correctly resolved — so
    it needs no persisted state and cannot answer #221's question.

    Detection is a conjunction: the ``.claude/worktrees`` ancestor locates the
    harness's worktree root, and the ``agent-``/``wf_`` id shape distinguishes a
    disposable tree from an ``EnterWorktree`` session worktree living under the
    same parent (see :data:`_EPHEMERAL_DIR_PATTERNS`).

    **For ``agent-`` the branch is a second conjunct, not a fallback (#648).**
    What makes a tree disposable is that its code commit returns while its
    ``.prawduct/`` write does not — the two are *separated*, so the write
    strands and the agent is told it succeeded. That separation exists only for
    the harness's own scratch branch. On a real named branch the two are
    inseparable: the branch is what lands, so a ``.prawduct/`` write on it is
    carried; and if the branch is discarded the code goes with it, leaving
    nothing silently ungoverned. Classifying an agent-path tree on
    ``fix/whatever`` as disposable refused every governance write on a branch
    someone was really working — making the Critic gate unsatisfiable with no
    workaround short of evicting the worktree (brookstalley/discodon#2213).

    **That inseparability is ASSUMED, not measured (#648).** It has not been
    verified against the harness's actual disposal policy — doing so means
    dispatching a probe agent, which the session that made this change was
    asked not to do. The falsifier is precise: *if the harness ever merges a
    code commit off a named branch while discarding that branch*, the two are
    separable after all and #594's silent-strand defect returns for exactly
    that case. Anything relying on this predicate to refuse a worktree
    subagent's ``.prawduct/`` write is relying on that assumption too.

    An agent-path tree whose branch cannot be read — detached HEAD, git probe
    failure — is disposable. That is the restrictive answer, and it is the
    right one twice over: a detached HEAD has no branch to carry a write out,
    and a failing probe must not become an accidental way to unlock the guard.

    ``wf_`` stays path-only. A workflow stage gets no named branch of its own,
    so there the path IS the identity; adding the branch conjunct would
    classify every workflow worktree as durable.

    The branch is still consulted as a *fallback* when the directory matches
    nothing, so a future harness change to the directory naming degrades to one
    more signal rather than to silence.

    Never raises (lib convention) — every probe inside fails open to ``None``,
    which is today's behavior: govern the tree normally.
    """
    try:
        project_dir = Path(project_dir)
    except TypeError:
        return None
    # Path shape first, and the ancestor test exactly once: the common case (any
    # tree not under `.claude/worktrees`) answers here having spawned no
    # subprocess, which is what keeps this off the hook's hot path.
    if not _under_claude_worktrees(project_dir):
        return None

    # Only an `agent-` tree's answer depends on the branch, so only it pays for
    # the `current_branch` subprocess — a workflow worktree stays exactly as
    # cheap as it was. This skips the PROBE, never the decision: the answer
    # still comes from `ephemeral_kind_of` on every path, so there is one body
    # to change and no second copy that could mask a defect in the first.
    needs_branch = _dir_label(project_dir.name) != "workflow"
    return ephemeral_kind_of(
        project_dir, current_branch(project_dir) if needs_branch else None
    )


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


def _branch_from_head_file(project_dir: Path) -> tuple[bool, str | None]:
    """``(answered, branch)`` read straight out of git's ``HEAD`` file.

    A fast path for :func:`current_branch`, whose subprocess costs ~70 ms of
    process spawn to read one line — enough that the session briefing calls it
    five times and pays a third of a second for it. This reads the same line.

    ``(False, None)`` means **this reader could not answer**, never "no branch":
    the caller falls back to ``git symbolic-ref``, which searches upward from a
    subdirectory, understands ``.git`` layouts this does not, and is the
    definition of correct. Only ``(True, …)`` is an answer — a detached HEAD
    (raw object id) is ``(True, None)``, which is the same ``None`` the
    subprocess reports, reached without spawning it.

    Linked worktrees are handled because that is where this runs most: their
    ``.git`` is a FILE naming the real git dir, and every worktree has its own
    ``HEAD`` inside it, so reading the shared common dir would report the
    primary checkout's branch — a silent wrong-branch answer, which is exactly
    what :func:`current_branch` exists to prevent.
    """
    git_path = project_dir / ".git"
    try:
        if git_path.is_file():
            pointer = git_path.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir:"):
                return (False, None)
            git_dir = Path(pointer[len("gitdir:"):].strip())
            if not git_dir.is_absolute():
                git_dir = project_dir / git_dir
        elif git_path.is_dir():
            git_dir = git_path
        else:
            return (False, None)
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return (False, None)
    prefix = "ref: refs/heads/"
    if head.startswith(prefix):
        return (True, head[len(prefix):].strip() or None)
    if head.startswith("ref: "):
        return (False, None)  # symbolic, but outside refs/heads — let git name it
    return (True, None)  # a raw object id: detached HEAD


def current_branch(project_dir: Path) -> str | None:
    """The current branch name, ``None`` on a detached HEAD or git failure.

    Used to make the tree a review resolved to VISIBLE (PDT-WT9K) — a silent
    wrong-tree review is the failure this surfaces, so a detached/failed probe
    returns ``None`` rather than a misleading value.

    Answers from git's ``HEAD`` file when it can (:func:`_branch_from_head_file`)
    and shells out otherwise. One function, one contract — the fast path either
    produces the same answer or declines to produce one."""
    answered, branch = _branch_from_head_file(project_dir)
    if answered:
        return branch
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


def local_branches(project_dir: Path) -> set[str] | None:
    """Every local branch name, or ``None`` when git could not be asked.

    ``None`` and ``set()`` are deliberately different answers, and the caller
    must keep them apart: this exists to tell an operator that a plan claims a
    branch nobody has, and "I could not list the branches" is not evidence that
    the branch is missing. Treating the two alike would turn a failed probe into
    a confident accusation on every repo where git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
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


#: A git object id in its two real hex widths: SHA-1 (40) and SHA-256 (64).
#: ``fullmatch`` rather than a ``$``-anchored search on purpose — ``$`` also
#: matches before a trailing newline, so ``"<40 hex>\n"`` would pass a check
#: written the obvious way, and a value read from a line-oriented file is
#: exactly where a stray newline comes from.
_OBJECT_ID_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def is_object_id(value: object) -> bool:
    """Whether ``value`` is a full-length git object id.

    The shape gate a tree id passes before it may reach a git argv or
    contribute a coverage edge. Tree ids arrive from the evidence store, which
    is a plain append-only file shared by every worktree of the clone, so a
    corrupted or hand-edited fact can put an arbitrary string where a tree id
    belongs. argv is list-form with no shell, so the exposure is a token git
    reads as an OPTION (``--upload-pack=…``) rather than shell injection —
    hardening and clearer failures, not an active hole.

    Abbreviated ids are rejected deliberately: everything prawduct writes is
    full-length, so a short id means the value did not come from here.
    """
    return isinstance(value, str) and _OBJECT_ID_RE.fullmatch(value) is not None


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
