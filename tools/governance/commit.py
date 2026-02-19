"""Commit gate + session archival.

Replaces critic-gate.sh logic. Validates commit readiness, archives session
traces, and cleans up session files.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from . import trace as tr
from .context import Context
from .state import SessionState


@dataclass
class CommitDecision:
    """Commit gate result."""

    allowed: bool
    reason: str = ""


def check_and_archive(
    tool_input: dict, ctx: Context, state: SessionState
) -> CommitDecision:
    """Validate commit readiness, archive session, clean up.

    Args:
        tool_input: Hook JSON with tool_input.command.
        ctx: Resolved governance context.
        state: Session state.

    Returns:
        CommitDecision with allowed=True or reason for block.
    """
    inner = tool_input.get("tool_input", {})
    command = inner.get("command", "")

    # Only activate for git commit commands
    if not re.search(r"(^|&&\s*|;\s*)git\s+commit", command):
        return CommitDecision(allowed=True)

    if not ctx.repo_root:
        return CommitDecision(allowed=True)

    # 1. PFR observation gate
    result = _check_pfr_observation(state)
    if not result.allowed:
        tr.event(state, "commit_block", {"rule": "pfr_observation", "reason": result.reason})
        state.save()
        return result

    # 2. Critic evidence check (delegate to critic-reminder.sh)
    result = _check_critic_evidence(ctx)
    if not result.allowed:
        tr.event(state, "commit_block", {"rule": "critic_evidence", "reason": result.reason})
        state.save()
        return result

    # 3. Archive session traces
    tr.event(state, "commit_allowed", {"command": "git commit"})
    traces_dir = os.path.join(ctx.product_prawduct, "traces")
    tr.persist(state, traces_dir)

    # 4. Clean up session files
    _cleanup(ctx)

    return CommitDecision(allowed=True)


def _check_pfr_observation(state: SessionState) -> CommitDecision:
    """If PFR required, observation file must exist."""
    pfr = state.pfr
    if not pfr.required:
        return CommitDecision(allowed=True)

    if not pfr.observation_file:
        return CommitDecision(
            allowed=False,
            reason=(
                "BLOCKED: PFR requires an observation file for governance-sensitive changes.\n"
                "Create one via: tools/capture-observation.sh with root_cause_analysis block,\n"
                "then set pfr_state.observation_file in .prawduct/.session-governance.json."
            ),
        )

    if not os.path.exists(pfr.observation_file):
        return CommitDecision(
            allowed=False,
            reason=f"BLOCKED: observation file not found: {pfr.observation_file}",
        )

    return CommitDecision(allowed=True)


def _check_critic_evidence(ctx: Context) -> CommitDecision:
    """Delegate to critic-reminder.sh for framework file check."""
    critic_tool = os.path.join(ctx.framework_root, "tools", "critic-reminder.sh")
    if not os.path.isfile(critic_tool):
        return CommitDecision(allowed=True)

    # Only check if .critic-pending exists
    if not os.path.isfile(ctx.critic_pending):
        return CommitDecision(allowed=True)

    try:
        result = subprocess.run(
            [critic_tool],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return CommitDecision(allowed=True)
        else:
            return CommitDecision(
                allowed=False,
                reason=(
                    "BLOCKED: Framework governance review required before committing.\n"
                    "Framework files are staged but no Critic review evidence was found.\n"
                    f"Run the Critic: read {ctx.framework_root}/skills/critic/SKILL.md"
                ),
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Never block on tool failure
        return CommitDecision(allowed=True)


def _cleanup(ctx: Context) -> None:
    """Clean up session files after successful commit."""
    for path in [
        os.path.join(ctx.product_prawduct, ".critic-pending"),
        os.path.join(ctx.product_prawduct, ".critic-findings.json"),
        os.path.join(ctx.product_prawduct, ".session-edits.json"),
        os.path.join(ctx.product_prawduct, ".session-governance.json"),
        os.path.join(ctx.product_prawduct, ".session-trace.jsonl"),
        os.path.join(ctx.prawduct_dir, ".orchestrator-activated"),
        os.path.join(ctx.prawduct_dir, ".active-product"),
    ]:
        try:
            os.remove(path)
        except OSError:
            pass
