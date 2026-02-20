"""UserPromptSubmit hook: activation reminder + framework version check.

If the Orchestrator hasn't been activated, injects an additionalContext
message reminding Claude to read SKILL.md (HR9). If activated but the
framework version is stale, injects an advisory to run prawduct-init.
Always exits 0 — UserPromptSubmit hooks don't block.
"""

from __future__ import annotations

import json
import os
import subprocess

from .context import Context


def _git_hash(repo_dir: str) -> str | None:
    """Get git HEAD hash for a directory."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _check_framework_version(ctx: Context) -> str | None:
    """Check if product's framework version matches running framework."""
    version_file = os.path.join(ctx.prawduct_dir, "framework-version")
    if not os.path.isfile(version_file):
        return None

    try:
        with open(version_file) as f:
            stored_hash = f.read().strip().split("\n")[0]
    except OSError:
        return None

    if not stored_hash:
        return None

    current_hash = _git_hash(ctx.framework_root)
    if not current_hash:
        return None

    if stored_hash == current_hash:
        return None

    # Derive product dir from prawduct_dir (strip trailing .prawduct/)
    product_dir = os.path.dirname(ctx.prawduct_dir)

    return (
        f"Framework version mismatch: product at {product_dir} uses "
        f"framework {stored_hash[:8]} but current framework is {current_hash[:8]}. "
        f"Run: python3 {ctx.framework_root}/tools/prawduct-init.py "
        f"--json {product_dir}"
    )


def check(ctx: Context) -> str | None:
    """Return JSON additionalContext string if activation needed or version stale, else None."""
    marker = ctx.activation_marker
    if not os.path.isfile(marker):
        msg = (
            f"CRITICAL: Governance is NOT active. You MUST read "
            f"{ctx.framework_root}/skills/orchestrator/SKILL.md and complete "
            f"steps 1-4 (establish project directory, read project-state.yaml, "
            f"activate governance, initialize tracking) BEFORE taking any other action. "
            f"This is HR9 (No Governance Bypass) — no edits, no research, no responses "
            f"until governance is activated."
        )
        return json.dumps({"additionalContext": msg})

    # Check framework version
    version_msg = _check_framework_version(ctx)
    if version_msg:
        return json.dumps({"additionalContext": version_msg})

    return None
