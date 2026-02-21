"""Path resolution for governance hooks.

Single implementation of the context resolution that was previously duplicated
across governance-gate.sh, governance-tracker.sh, governance-stop.sh, and
critic-gate.sh. Resolves framework root, prawduct dir, and repo root.

Active-product pointer: In cross-repo sessions (framework hooks managing a
separate product repo), gate/track write an .active-product pointer file
so they resolve the correct product directory per-file. Stop/commit/prompt
do NOT follow the pointer — they validate session-level governance state.
The pointer is cleaned up on session restart.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Context:
    """Resolved governance paths (session-level)."""

    framework_root: str
    prawduct_dir: str
    repo_root: str

    @property
    def session_file(self) -> str:
        return os.path.join(self.prawduct_dir, ".session-governance.json")

    @property
    def activation_marker(self) -> str:
        return os.path.join(self.prawduct_dir, ".orchestrator-activated")

    @property
    def trace_file(self) -> str:
        return os.path.join(self.prawduct_dir, ".session-trace.jsonl")

    @property
    def critic_pending(self) -> str:
        return os.path.join(self.prawduct_dir, ".critic-pending")

    @property
    def critic_findings(self) -> str:
        return os.path.join(self.prawduct_dir, ".critic-findings.json")


def _git_toplevel() -> str:
    """Get the git repo root, or empty string if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _active_product_path(prawduct_dir: str) -> str:
    """Path to the active-product pointer file."""
    return os.path.join(prawduct_dir, ".active-product")


def resolve_product_for_file(file_path: str, fallback_prawduct_dir: str) -> str:
    """Resolve the product .prawduct/ directory for a specific file path.

    Derives the product from the file's git root rather than a global
    pointer. If the file's git root contains .prawduct/, use that.
    Otherwise fall back to the session-level prawduct_dir.

    Args:
        file_path: Absolute path to the file being operated on.
        fallback_prawduct_dir: Session-level .prawduct/ (from Context).

    Returns:
        The prawduct_dir string for the resolved product.
    """
    from .classify import _find_git_root

    if file_path:
        git_root = _find_git_root(file_path)
        if git_root:
            candidate = os.path.join(git_root, ".prawduct")
            if os.path.isdir(candidate):
                return candidate
    return fallback_prawduct_dir


def write_active_product(session_prawduct_dir: str, product_prawduct_dir: str) -> None:
    """Write the active-product pointer file.

    Only writes if the product differs from the session (cross-repo).
    The pointer is a plain text file containing the absolute path to
    the product's .prawduct/ directory.

    Args:
        session_prawduct_dir: The session-level .prawduct/ (from CLAUDE_PROJECT_DIR).
        product_prawduct_dir: The resolved product's .prawduct/.
    """
    if os.path.realpath(product_prawduct_dir) == os.path.realpath(session_prawduct_dir):
        return  # Same dir — no pointer needed (self-hosted or same-repo)

    pointer_path = _active_product_path(session_prawduct_dir)
    try:
        with open(pointer_path, "w") as f:
            f.write(product_prawduct_dir)
    except OSError:
        pass  # Best effort — never block on pointer write failure


def update_product_context(file_path: str, ctx: Context) -> Context:
    """Resolve product from file path and update context if needed.

    If the file belongs to a different product than ctx currently points to,
    writes the active-product pointer and returns a NEW Context with the
    updated prawduct_dir. Context is frozen, so we create a new instance.

    Args:
        file_path: Absolute path to the file being operated on.
        ctx: Current resolved governance context.

    Returns:
        Context — either the original (if no change) or a new one pointing
        to the resolved product.
    """
    product_prawduct_dir = resolve_product_for_file(file_path, ctx.prawduct_dir)

    if os.path.realpath(product_prawduct_dir) == os.path.realpath(ctx.prawduct_dir):
        return ctx  # No change

    # Cross-repo: write pointer and return updated context.
    # The session prawduct_dir (where the pointer lives) is derived from
    # CLAUDE_PROJECT_DIR — which is always the framework repo in cross-repo
    # sessions. We need the *original* session dir, not the already-redirected
    # ctx.prawduct_dir (which may have been updated by a previous pointer read).
    session_prawduct_dir = os.path.join(
        os.environ.get("CLAUDE_PROJECT_DIR", ctx.framework_root), ".prawduct"
    )
    write_active_product(session_prawduct_dir, product_prawduct_dir)

    return Context(
        framework_root=ctx.framework_root,
        prawduct_dir=product_prawduct_dir,
        repo_root=ctx.repo_root,
    )


def resolve(
    framework_root: Optional[str] = None,
    follow_pointer: bool = True,
) -> Context:
    """Resolve all governance paths from environment.

    After computing the initial prawduct_dir from CLAUDE_PROJECT_DIR,
    optionally checks for an .active-product pointer file to redirect
    to a cross-repo product.

    Args:
        framework_root: Explicit framework root. If None, derived from
            GOVERNANCE_FRAMEWORK_ROOT env var (set by hook shims).
        follow_pointer: Whether to follow the .active-product pointer.
            True for gate/track (need product context for the file being
            edited). False for stop/commit/prompt (validate session-level
            state, not a cross-repo product's state).

    Returns:
        Context with all resolved paths.
    """
    if framework_root is None:
        framework_root = os.environ.get("GOVERNANCE_FRAMEWORK_ROOT", "")
    if not framework_root:
        raise ValueError(
            "framework_root must be provided or GOVERNANCE_FRAMEWORK_ROOT must be set"
        )

    repo_root = _git_toplevel()
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")

    if claude_project_dir:
        prawduct_dir = os.path.join(claude_project_dir, ".prawduct")
    elif repo_root:
        prawduct_dir = os.path.join(repo_root, ".prawduct")
    else:
        prawduct_dir = os.path.join(framework_root, ".prawduct")

    # Follow active-product pointer if present and requested.
    # Gate/track follow the pointer to resolve per-file product context.
    # Stop/commit/prompt do NOT follow — they validate the session's own
    # governance state. Following the pointer causes stop to check a
    # different repo's DCP/PFR state, blocking the session with another
    # repo's governance debt.
    if follow_pointer:
        pointer_path = _active_product_path(prawduct_dir)
        if os.path.isfile(pointer_path):
            try:
                with open(pointer_path) as f:
                    target = f.read().strip()
                if target and os.path.isdir(target):
                    prawduct_dir = target
            except OSError:
                pass  # Fall back to original prawduct_dir

    return Context(
        framework_root=framework_root,
        prawduct_dir=prawduct_dir,
        repo_root=repo_root,
    )
