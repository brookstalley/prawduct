"""Stop hook validation.

Replaces governance-stop.sh logic. Checks all session-end governance
requirements and blocks when critical debt exists.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from . import trace as tr
from .context import Context
from .state import SessionState


@dataclass
class StopDecision:
    """Stop validation result."""

    allowed: bool
    debts: list[str] = field(default_factory=list)


# Maximum age for Critic findings before considered stale
FINDINGS_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 hours

# Minimum number of Critic checks for valid findings
MIN_CRITIC_CHECKS = 4


def validate(
    hook_input: dict, ctx: Context, state: SessionState
) -> StopDecision:
    """Check all session-end governance requirements.

    Args:
        hook_input: Hook JSON (may contain stop_hook_active flag).
        ctx: Resolved governance context.
        state: Session state to check.

    Returns:
        StopDecision with allowed=True or debts list.
    """
    # Prevent infinite loops
    if hook_input.get("stop_hook_active", False):
        return StopDecision(allowed=True)

    if not os.path.isfile(state.path):
        return StopDecision(allowed=True)

    debts: list[str] = []

    _check_framework_coverage(state, ctx, debts)
    _check_product_governance(state, debts)
    _check_pfr(state, debts)
    _check_dcp(state, ctx, debts)
    _check_compaction(ctx, debts)
    _check_observation_gaps(state, ctx, debts)

    tr.event(state, "stop_check", {
        "debts_found": len(debts),
        "debts_detail": debts,
    })
    state.save()

    if debts:
        return StopDecision(allowed=False, debts=debts)
    return StopDecision(allowed=True)


def _check_framework_coverage(
    state: SessionState, ctx: Context, debts: list[str]
) -> None:
    """Framework files edited without Critic review."""
    edited_files = [entry["path"] for entry in state.framework_edits.files]
    if not edited_files:
        return

    findings_path = ctx.critic_findings
    if not os.path.isfile(findings_path):
        file_list = ", ".join(edited_files[:5])
        debts.append(f"No Critic review for: {file_list}")
        return

    try:
        with open(findings_path) as f:
            findings = json.load(f)
    except (OSError, json.JSONDecodeError):
        debts.append("Critic findings file invalid")
        return

    file_age = time.time() - os.path.getmtime(findings_path)
    if file_age > FINDINGS_MAX_AGE_SECONDS:
        debts.append("Critic findings stale (>2h)")
        return

    if findings.get("total_checks", 0) < MIN_CRITIC_CHECKS:
        debts.append(
            f'Critic findings: {findings.get("total_checks", 0)} checks (need {MIN_CRITIC_CHECKS}+)'
        )
        return

    reviewed = set(findings.get("reviewed_files", []))
    uncovered = [f for f in edited_files if f not in reviewed]
    if uncovered:
        debts.append(f"{len(uncovered)} edited file(s) not in Critic findings")


def _check_product_governance(state: SessionState, debts: list[str]) -> None:
    """Chunks without review, overdue checkpoints, and unreviewed product edits."""
    gov = state.governance
    if gov.chunks_completed_without_review > 0 and not gov.retroactive_review_in_progress:
        debts.append(
            f"{gov.chunks_completed_without_review} chunk(s) without Critic review"
        )
    if gov.governance_checkpoints_due:
        debts.append(
            f"{len(gov.governance_checkpoints_due)} governance checkpoint(s) overdue"
        )

    # Stage 6: ad-hoc product edits without Critic review
    # In Stage 5, chunks have built-in review gates. In Stage 6, ad-hoc edits
    # need explicit review. Threshold of 3+ files matches DCP proportionality.
    if (
        state.current_stage == "iteration"
        and gov.product_files_changed >= 3
        and not gov.last_critic_review_chunk
    ):
        debts.append(
            f"{gov.product_files_changed} product file(s) edited without Critic review. "
            "Run a Critic review before ending the session."
        )


def _check_pfr(state: SessionState, debts: list[str]) -> None:
    """PFR completion requirements.

    Uses PFRState.is_satisfied() for consistent evaluation across all
    enforcement points (gate, commit, stop, tracker).
    """
    pfr = state.pfr
    if pfr.is_satisfied():
        # Satisfied (not required, cosmetic, or has RCA).
        # Still check for observation file if RCA was provided.
        if pfr.required and pfr.rca and not pfr.cosmetic_justification and not pfr.observation_file:
            gov_files = ", ".join(pfr.governance_sensitive_files[:5])
            debts.append(
                f"PFR: governance-sensitive files edited ({gov_files}) but no observation captured. "
                "Create observation via tools/capture-observation.sh, then set pfr_state.observation_file."
            )
        return

    debts.append(
        "PFR: governance-sensitive files edited without root cause analysis. "
        "Write RCA to pfr_state.rca in .prawduct/.session-governance.json."
    )


def _check_dcp(state: SessionState, ctx: Context, debts: list[str]) -> None:
    """DCP classification and completion requirements."""
    dcp = state.dcp

    # Classification trigger without active DCP
    if dcp.needs_classification and not dcp.active:
        debts.append(
            f"DCP: {dcp.triggered_at_file_count}+ governed files edited without change classification. "
            f"Read {ctx.framework_root}/skills/orchestrator/stage-6-iteration.md and classify per DCP tiers."
        )

    if not dcp.active:
        return

    # Active DCP checks
    if dcp.tier == "structural" and not dcp.plan_stage_review_completed:
        debts.append("DCP: plan-stage review incomplete")

    if dcp.total_phases > 1 and dcp.phases_reviewed_count == 0:
        debts.append(f"DCP: 0/{dcp.total_phases} phase reviews done")

    if not dcp.observation_captured:
        debts.append("DCP: observation not captured")

    if not dcp.retrospective_completed:
        debts.append("DCP: retrospective incomplete")

    # Artifact freshness for enhancement/structural
    if dcp.tier in ("enhancement", "structural") and not dcp.artifacts_verified:
        debts.append(
            "DCP: artifact freshness not verified. "
            "Read artifact_manifest in project-state.yaml, identify artifacts describing "
            "affected behavior, verify each is current, update stale ones, then record "
            "the list in directional_change.artifacts_verified"
        )


def _check_compaction(ctx: Context, debts: list[str]) -> None:
    """project-state.yaml compaction debt."""
    state_file = os.path.join(ctx.prawduct_dir, "project-state.yaml")
    if not os.path.isfile(state_file):
        return

    compact_tool = os.path.join(ctx.framework_root, "tools", "compact-project-state.sh")
    if not os.path.isfile(compact_tool):
        return

    try:
        result = subprocess.run(
            [compact_tool, "--check", state_file],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 1:
            debts.append("project-state.yaml needs compaction. Run: tools/compact-project-state.sh")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass  # Never block on tool failure


def _check_observation_gaps(
    state: SessionState, ctx: Context, debts: list[str]
) -> None:
    """Critic findings with warning/blocking severity but no observations captured."""
    if state.governance.observations_captured_this_session > 0:
        return

    findings_path = ctx.critic_findings
    if not os.path.isfile(findings_path):
        return

    try:
        findings_mtime = os.path.getmtime(findings_path)

        # Only check findings created during current session
        findings_in_session = True
        if state.session_started:
            try:
                session_ts = datetime.fromisoformat(
                    state.session_started.replace("Z", "+00:00")
                ).timestamp()
                findings_in_session = findings_mtime >= session_ts
            except (ValueError, TypeError):
                pass

        if not findings_in_session:
            return

        with open(findings_path) as f:
            findings_data = json.load(f)

        highest_sev = findings_data.get("highest_severity", "pass")
        if highest_sev in ("warning", "blocking"):
            debts.append(
                f"Critic findings have {highest_sev}-severity issues but 0 observations "
                "captured this session. Capture observations to framework-observations/ "
                "and increment observations_captured_this_session."
            )
    except (OSError, json.JSONDecodeError):
        pass  # Never block on file read failure
