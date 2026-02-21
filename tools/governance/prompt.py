"""UserPromptSubmit hook: activation reminder + framework version check + stage reminders.

If the Orchestrator hasn't been activated, injects an additionalContext
message reminding Claude to read SKILL.md (HR9). If activated but the
framework version is stale, injects an advisory to run prawduct-init.
When governance is active, injects stage-appropriate protocol reminders
based on current governance state.
Always exits 0 — UserPromptSubmit hooks don't block.
"""

from __future__ import annotations

import json
import os
import subprocess

from .context import Context
from .state import SessionState


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

    # Stage-aware protocol reminders (lightweight, only when debt exists)
    reminder = _stage_reminders(ctx)
    if reminder:
        return json.dumps({"additionalContext": reminder})

    return None


def _stage_reminders(ctx: Context) -> str | None:
    """Generate contextual reminders based on current governance state."""
    state = SessionState.load(ctx.session_file)
    if not state.current_stage:
        return None

    parts: list[str] = []

    # DCP classification pending
    if state.dcp.needs_classification:
        n = state.dcp.triggered_at_file_count
        parts.append(
            f"{n} files edited — classify this change (mechanical/enhancement/structural) "
            f"before continuing. See stage-6-iteration.md DCP."
        )

    # PFR required but no RCA yet
    if state.pfr.required and not state.pfr.rca and not state.pfr.cosmetic_justification:
        files = ", ".join(state.pfr.governance_sensitive_files[:3])
        parts.append(
            f"Governance-sensitive file(s) edited ({files}). "
            f"Write root cause analysis to pfr_state.rca before continuing."
        )

    # Chunks without review (Stage 5/6 with active build)
    debt = state.governance.chunks_completed_without_review
    if debt > 0:
        parts.append(
            f"{debt} chunk(s) completed without Critic review. "
            f"Run Governance Review before editing product files."
        )

    # Stage 6: classify feedback before acting (no state tracking needed —
    # this is a standing reminder that fires when no other debt exists)
    if state.current_stage == "iteration" and not parts:
        dcp = state.dcp
        if not dcp.active and not dcp.needs_classification:
            parts.append(
                "Stage 6: classify feedback (cosmetic/functional/directional) before "
                "implementing. See stage-6-iteration.md."
            )

    if not parts:
        return None

    return "Governance reminders: " + " | ".join(parts)
