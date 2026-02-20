"""UserPromptSubmit hook: activation reminder + framework version check.

If the Orchestrator hasn't been activated, injects an additionalContext
message reminding Claude to read SKILL.md (HR9). If activated but the
active product's framework version is stale, injects an advisory to
run prawduct-init. Always exits 0 — UserPromptSubmit hooks don't block.
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
    """Check if active product's framework version matches running framework."""
    version_file = os.path.join(ctx.product_prawduct, "framework-version")
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

    # Derive product dir from product_prawduct (strip trailing .prawduct/)
    product_dir = os.path.dirname(ctx.product_prawduct)

    return (
        f"Framework version mismatch: product at {product_dir} uses "
        f"framework {stored_hash[:8]} but current framework is {current_hash[:8]}. "
        f"Run: python3 {ctx.framework_root}/tools/prawduct-init.py "
        f"--json {product_dir}"
    )


def _check_product_context(ctx: Context) -> str | None:
    """Check that the active product pointer resolves to an initialized project.

    Detects cases where .active-product points to a directory without .prawduct/.
    This catches incomplete project setup early — before the gate blocks
    individual edits.
    """
    active_product_path = os.path.join(
        os.environ.get("CLAUDE_PROJECT_DIR", ctx.framework_root),
        ".prawduct", ".active-product"
    )

    if not os.path.isfile(active_product_path):
        return None

    try:
        with open(active_product_path) as f:
            target_dir = f.read().strip()
    except OSError:
        return None

    if not target_dir:
        return None

    target_prawduct = os.path.join(target_dir, ".prawduct")
    if not os.path.isdir(target_prawduct):
        repo_name = os.path.basename(target_dir)
        return (
            f"Product pointer targets {repo_name} but it hasn't been onboarded to Prawduct "
            f"(.prawduct/ not found). Tell the Orchestrator to work on {target_dir} — "
            f"it will run prawduct-init automatically. Or remove the pointer if this "
            f"project shouldn't use Prawduct."
        )

    return None


def check(ctx: Context) -> str | None:
    """Return JSON additionalContext string if activation needed or version stale, else None."""
    marker = ctx.activation_marker
    if not os.path.isfile(marker):
        msg = (
            f"Orchestrator not activated (HR9). "
            f"Read {ctx.framework_root}/skills/orchestrator/SKILL.md steps 2-4 first."
        )
        return json.dumps({"additionalContext": msg})

    # Activation OK — check product context is valid
    product_msg = _check_product_context(ctx)
    if product_msg:
        return json.dumps({"additionalContext": product_msg})

    # Check framework version on active product
    version_msg = _check_framework_version(ctx)
    if version_msg:
        return json.dumps({"additionalContext": version_msg})

    return None
