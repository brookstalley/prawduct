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
    result = _check_pfr_observation(state, ctx)
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

    # 3. DCP completion check
    result = _check_dcp(state)
    if not result.allowed:
        tr.event(state, "commit_block", {"rule": "dcp_incomplete", "reason": result.reason})
        state.save()
        return result

    # 4. Archive session traces
    tr.event(state, "commit_allowed", {"command": "git commit"})
    traces_dir = os.path.join(ctx.prawduct_dir, "traces")
    tr.persist(state, traces_dir)

    # 5. Reset per-commit tracking in session state
    # Framework edits and PFR are per-commit concerns — after a successful
    # commit (which required critic review + PFR observation), they should
    # reset so the stop hook doesn't flag already-committed work as debt.
    _reset_per_commit_state(state)

    # 6. Clean up per-commit files
    _cleanup(ctx)

    return CommitDecision(allowed=True)


def _check_pfr_observation(state: SessionState, ctx: Context) -> CommitDecision:
    """If PFR required with RCA, observation file must exist.

    Uses PFRState.is_satisfied() for consistent evaluation across all
    enforcement points (gate, commit, stop, tracker).
    """
    pfr = state.pfr

    if pfr.is_satisfied():
        # Cosmetic or not required: no observation needed
        if pfr.cosmetic_justification or not pfr.required:
            return CommitDecision(allowed=True)

        # Satisfied via RCA: observation file required
        if not pfr.observation_file:
            return CommitDecision(
                allowed=False,
                reason=(
                    "BLOCKED: PFR requires an observation file for governance-sensitive changes.\n"
                    "Create one via: tools/capture-observation.sh with root_cause_analysis block,\n"
                    "then set pfr_state.observation_file in .prawduct/.session-governance.json."
                ),
            )

        # Resolve relative paths: try product directory, then framework root
        # (cross-repo sessions capture observations in the framework repo)
        obs_path = pfr.observation_file
        if not os.path.isabs(obs_path):
            candidate = os.path.join(state.product_dir, obs_path)
            if os.path.exists(candidate):
                obs_path = candidate
            elif ctx.framework_root:
                framework_candidate = os.path.join(ctx.framework_root, obs_path)
                if os.path.exists(framework_candidate):
                    obs_path = framework_candidate
                else:
                    obs_path = candidate  # Use product path for error message
            else:
                obs_path = candidate

        if not os.path.exists(obs_path):
            return CommitDecision(
                allowed=False,
                reason=f"BLOCKED: observation file not found: {pfr.observation_file} (resolved: {obs_path})",
            )

        return CommitDecision(allowed=True)

    # Not satisfied — block with guidance
    return CommitDecision(
        allowed=False,
        reason=(
            "BLOCKED: PFR: governance-sensitive files edited without root cause analysis.\n"
            "Write RCA to pfr_state.rca in .prawduct/.session-governance.json,\n"
            "or set pfr_state.cosmetic_justification if the change is cosmetic."
        ),
    )


def _check_critic_evidence(ctx: Context) -> CommitDecision:
    """Delegate to critic-reminder.sh for framework file check."""
    critic_tool = os.path.join(ctx.framework_root, "tools", "critic-reminder.sh")
    if not os.path.isfile(critic_tool):
        return CommitDecision(allowed=True)

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
                    f"Run the Critic: invoke agent per {ctx.framework_root}/skills/orchestrator/protocols.md § Critic Agent Protocol"
                ),
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Never block on tool failure
        return CommitDecision(allowed=True)


def _check_dcp(state: SessionState) -> CommitDecision:
    """If DCP is active, require completion before commit.

    DCP tracks a directional change (enhancement/structural work). All DCP
    items — observation, retrospective, artifact verification — must be
    complete before the work can be committed. This prevents governance debt
    from being pushed to the remote.
    """
    dcp = state.dcp
    if not dcp.active:
        return CommitDecision(allowed=True)

    debts: list[str] = []

    if not dcp.observation_captured:
        debts.append("observation not captured")
    if not dcp.retrospective_completed:
        debts.append("retrospective incomplete")
    if dcp.tier in ("enhancement", "structural") and not dcp.artifacts_verified:
        debts.append("artifact freshness not verified")
    if dcp.tier == "structural" and not dcp.plan_stage_review_completed:
        debts.append("plan-stage review incomplete")

    if debts:
        items = ", ".join(debts)
        return CommitDecision(
            allowed=False,
            reason=f"BLOCKED: DCP incomplete — {items}. Complete these before committing.",
        )

    return CommitDecision(allowed=True)


def _reset_per_commit_state(state: SessionState) -> None:
    """Reset per-commit tracking after successful commit.

    Framework edits and PFR state are per-commit concerns — they track what
    needs critic review and observation capture before the next commit. After
    a successful commit (which already passed those gates), reset them so
    the stop hook doesn't flag already-committed work as governance debt.
    Session-level state (governance_state, dcp, current_stage) is preserved.
    """
    from .state import FrameworkEdits, PFRState

    state.framework_edits = FrameworkEdits()
    state.pfr = PFRState()
    state.save()


def _cleanup(ctx: Context) -> None:
    """Clean up per-commit artifacts after successful commit.

    Only removes artifacts that are per-commit (critic evidence, pending flags).
    Session-level state (.session-governance.json, .orchestrator-activated,
    .session-trace.jsonl) is preserved — sessions often contain multiple commits,
    and cleaning up after the first would leave subsequent work ungoverned.
    Session-level cleanup happens in the SessionStart hook on /clear or new startup.
    """
    for path in [
        os.path.join(ctx.prawduct_dir, ".critic-pending"),
        os.path.join(ctx.prawduct_dir, ".critic-findings.json"),
        os.path.join(ctx.prawduct_dir, ".session-edits.json"),
    ]:
        try:
            os.remove(path)
        except OSError:
            pass
