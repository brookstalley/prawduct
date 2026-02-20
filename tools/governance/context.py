"""Path resolution for governance hooks.

Single implementation of the context resolution that was previously duplicated
across governance-gate.sh, governance-tracker.sh, governance-stop.sh, and
critic-gate.sh. Resolves framework root, prawduct dir, and repo root.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProductPaths:
    """Resolved paths for a specific product's .prawduct/ directory.

    Used by gate/track to operate on the correct product when multiple
    repos are active concurrently. Derived from the file being operated
    on (its git root), not from a global pointer.
    """

    prawduct_dir: str  # e.g. /path/to/worldground/.prawduct

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


def resolve_product_for_file(file_path: str, fallback_prawduct_dir: str) -> ProductPaths:
    """Resolve the product .prawduct/ for a specific file path.

    Derives the product from the file's git root rather than a global
    pointer. If the file's git root contains .prawduct/, use that.
    Otherwise fall back to the session-level prawduct_dir.

    Args:
        file_path: Absolute path to the file being operated on.
        fallback_prawduct_dir: Session-level .prawduct/ (from Context).

    Returns:
        ProductPaths for the resolved product.
    """
    from .classify import _find_git_root

    if file_path:
        git_root = _find_git_root(file_path)
        if git_root:
            candidate = os.path.join(git_root, ".prawduct")
            if os.path.isdir(candidate):
                return ProductPaths(prawduct_dir=candidate)
    return ProductPaths(prawduct_dir=fallback_prawduct_dir)


def resolve(framework_root: Optional[str] = None) -> Context:
    """Resolve all governance paths from environment.

    Args:
        framework_root: Explicit framework root. If None, derived from
            GOVERNANCE_FRAMEWORK_ROOT env var (set by hook shims).

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

    return Context(
        framework_root=framework_root,
        prawduct_dir=prawduct_dir,
        repo_root=repo_root,
    )
