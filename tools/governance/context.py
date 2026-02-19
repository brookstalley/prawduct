"""Path resolution for governance hooks.

Single implementation of the context resolution that was previously duplicated
across governance-gate.sh, governance-tracker.sh, governance-stop.sh, and
critic-gate.sh. Resolves framework root, prawduct dir, product prawduct dir,
and repo root.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Context:
    """Resolved governance paths."""

    framework_root: str
    prawduct_dir: str
    product_prawduct: str
    repo_root: str

    @property
    def session_file(self) -> str:
        return os.path.join(self.product_prawduct, ".session-governance.json")

    @property
    def activation_marker(self) -> str:
        return os.path.join(self.prawduct_dir, ".orchestrator-activated")

    @property
    def trace_file(self) -> str:
        return os.path.join(self.product_prawduct, ".session-trace.jsonl")

    @property
    def critic_pending(self) -> str:
        return os.path.join(self.product_prawduct, ".critic-pending")

    @property
    def critic_findings(self) -> str:
        return os.path.join(self.product_prawduct, ".critic-findings.json")


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


def _resolve_product_prawduct(claude_project_dir: str, prawduct_dir: str) -> str:
    """Resolve product .prawduct/ via .active-product pointer.

    Checks: claude_project_dir/.prawduct/.active-product -> target_dir/.prawduct
    Falls back to prawduct_dir.
    """
    active_product_path = os.path.join(claude_project_dir, ".prawduct", ".active-product")
    if os.path.isfile(active_product_path):
        try:
            with open(active_product_path) as f:
                target_dir = f.read().strip()
            target_prawduct = os.path.join(target_dir, ".prawduct")
            if os.path.isdir(target_prawduct):
                return target_prawduct
        except OSError:
            pass
    return prawduct_dir


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

    if claude_project_dir:
        product_prawduct = _resolve_product_prawduct(claude_project_dir, prawduct_dir)
    else:
        product_prawduct = prawduct_dir

    return Context(
        framework_root=framework_root,
        prawduct_dir=prawduct_dir,
        product_prawduct=product_prawduct,
        repo_root=repo_root,
    )
