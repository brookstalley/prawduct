"""PreToolUse gate decisions.

Replaces governance-gate.sh logic (~340 lines bash+Python). Handles:
1. Activation gate (skill reads): block until Orchestrator activated
2. Activation gate (all edits): block governed edits until activated
3. PFR gate: governance-sensitive files need RCA before editing
4. Chunk review gate: product files blocked with review debt
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import trace as tr
from .classify import classify, FileClass
from .context import Context, ProductPaths
from .state import SessionState


@dataclass
class Decision:
    """Gate decision: allow or block."""

    allowed: bool
    reason: str = ""
    rule: str = ""


# Maximum age of an activation marker before it's considered stale
MARKER_MAX_AGE = timedelta(hours=12)

# Minimum length for a non-trivial PFR RCA
PFR_RCA_MIN_LENGTH = 50


def check(tool_input: dict, ctx: Context, state: SessionState, product: ProductPaths = None) -> Decision:
    """Run all applicable gate checks. Return allow or block.

    Args:
        tool_input: Hook JSON with tool_name and tool_input.
        ctx: Resolved governance context.
        state: Current session state (read-only for gate; trace events appended).
        product: Per-file product paths (resolved from file's git root).

    Returns:
        Decision with allowed=True or allowed=False + reason.
    """
    tool_name = tool_input.get("tool_name", "")
    inner = tool_input.get("tool_input", {})
    file_path = inner.get("file_path", "")

    if not file_path:
        return Decision(allowed=True)

    fc = classify(file_path, ctx)

    # --- Read gate: only skill/template files ---
    if tool_name == "Read":
        return _check_read(fc, ctx, state, product=product)

    # --- Edit/Write gate ---
    return _check_edit(fc, file_path, ctx, state, product=product)


def _check_read(fc: FileClass, ctx: Context, state: SessionState, product: ProductPaths = None) -> Decision:
    """Gate for Read operations on skill/template files."""
    if not fc.is_read_gated:
        tr.event(state, "gate_check", {"rule": "read_gated", "result": "skip"})
        return Decision(allowed=True)

    # Check activation
    result = _check_activation(ctx, state, rule_name="read_activation", product=product)
    if not result.allowed:
        return result

    tr.event(state, "gate_check", {"rule": "read_activation", "result": "allow"})
    return Decision(allowed=True)


def _check_edit(
    fc: FileClass, file_path: str, ctx: Context, state: SessionState, product: ProductPaths = None
) -> Decision:
    """Gate for Edit/Write operations."""
    # Ungoverned files: allow unless they're in an unregistered git repo
    if not fc.is_framework and not fc.is_product:
        if fc.is_external_repo:
            result = _check_external_repo(fc, ctx, state, product=product)
            if not result.allowed:
                tr.event(state, "gate_block", {"rule": "external_repo", "file": file_path, "repo": fc.external_repo_root, "reason": result.reason})
                return result
        tr.event(state, "gate_check", {"rule": "governed", "file": fc.rel_path or file_path, "result": "ungoverned"})
        return Decision(allowed=True)

    # 1. Activation gate
    result = _check_activation(ctx, state, rule_name="edit_activation", product=product)
    if not result.allowed:
        tr.event(state, "gate_block", {"rule": "activation", "file": fc.rel_path, "reason": result.reason})
        return result

    # 2. PFR gate (governance-sensitive framework files)
    if fc.is_framework and fc.is_governance_sensitive:
        result = _check_pfr(fc, state)
        if not result.allowed:
            tr.event(state, "gate_block", {"rule": "pfr", "file": fc.rel_path, "reason": result.reason})
            return result
        tr.event(state, "gate_check", {"rule": "pfr", "file": fc.rel_path, "result": "allow"})

    # 3. Chunk review gate (product files)
    if fc.is_product:
        result = _check_chunk_review(file_path, state)
        if not result.allowed:
            tr.event(state, "gate_block", {"rule": "chunk_review", "file": fc.rel_path, "reason": result.reason})
            return result

    tr.event(state, "gate_check", {"rule": "edit", "file": fc.rel_path, "result": "allow"})
    return Decision(allowed=True)


def _is_governance_active(ctx: Context, product: ProductPaths = None) -> bool:
    """Check if governance is currently active (activation marker exists and valid)."""
    marker_path = product.activation_marker if product else ctx.activation_marker
    if not os.path.isfile(marker_path):
        return False
    return _validate_marker(marker_path) == "ok"


def _check_external_repo(
    fc: FileClass, ctx: Context, state: SessionState, product: ProductPaths = None
) -> Decision:
    """Block edits to files in git repos not registered with Prawduct.

    This prevents cross-repo governance escapes where an agent edits files
    in a sibling repository without onboarding it.
    """
    repo_name = os.path.basename(fc.external_repo_root)

    if _is_governance_active(ctx, product=product):
        return Decision(
            allowed=False,
            reason=(
                f"BLOCKED: This file is in a git repository ({repo_name}) that isn't "
                f"onboarded to Prawduct. You're using Prawduct but this repo isn't registered.\n"
                f"\n"
                f"To continue, either:\n"
                f"  1. Onboard this repo: tell the Orchestrator to work on {fc.external_repo_root}\n"
                f"     (it will run prawduct-init automatically)\n"
                f"  2. If you don't want Prawduct governance for this repo, restart Claude Code\n"
                f"     without Prawduct hooks."
            ),
            rule="external_repo",
        )

    return Decision(
        allowed=False,
        reason=(
            f"BLOCKED: Prawduct hooks are active but the Orchestrator hasn't been loaded (HR9). "
            f"This file is in {repo_name}, which isn't onboarded.\n"
            f"\n"
            f"Read {ctx.framework_root}/skills/orchestrator/SKILL.md first to activate governance.\n"
            f"If you don't want Prawduct governance, restart Claude Code without Prawduct hooks."
        ),
        rule="external_repo_no_activation",
    )


def _check_activation(ctx: Context, state: SessionState, rule_name: str, product: ProductPaths = None) -> Decision:
    """Verify Orchestrator activation marker exists, is valid, and is fresh."""
    marker_path = product.activation_marker if product else ctx.activation_marker
    if not os.path.isfile(marker_path):
        return Decision(
            allowed=False,
            reason=f"BLOCKED: Edit requires activation (HR9). Read {ctx.framework_root}/skills/orchestrator/SKILL.md first.",
            rule=rule_name,
        )

    status = _validate_marker(marker_path)
    if status == "invalid":
        return Decision(
            allowed=False,
            reason=f"BLOCKED: Invalid activation marker (HR9). Read {ctx.framework_root}/skills/orchestrator/SKILL.md step 3.",
            rule=rule_name,
        )
    if status == "stale":
        return Decision(
            allowed=False,
            reason=f"BLOCKED: Stale activation marker (HR9). Re-run Session Resumption via {ctx.framework_root}/skills/orchestrator/SKILL.md.",
            rule=rule_name,
        )

    return Decision(allowed=True)


def _validate_marker(marker_path: str) -> str:
    """Validate an activation marker file.

    Returns: "ok", "stale", or "invalid".
    """
    try:
        with open(marker_path) as f:
            content = f.read().strip()
    except OSError:
        return "invalid"

    if "praw-active" not in content:
        return "invalid"

    ts_part = content.replace("praw-active", "").strip().rstrip("Z")
    try:
        if ts_part:
            marker_time = datetime.fromisoformat(ts_part)
        else:
            marker_time = datetime.fromtimestamp(
                os.path.getmtime(marker_path)
            )
        age = datetime.now(timezone.utc).replace(tzinfo=None) - marker_time
        return "ok" if age < MARKER_MAX_AGE else "stale"
    except (ValueError, OSError):
        return "invalid"


def _check_pfr(fc: FileClass, state: SessionState) -> Decision:
    """PFR gate: governance-sensitive files need RCA before editing.

    v2 behavior: checks for non-empty pfr_state.rca (natural language, >=50 chars)
    instead of 5 structured JSON fields.
    """
    pfr = state.pfr

    # Cosmetic escape: only applies to files already covered by the justification.
    # If governance_sensitive_files is non-empty and the current file isn't in it,
    # this is a NEW governance-sensitive edit not covered by the cosmetic justification.
    if pfr.required is False and pfr.cosmetic_justification:
        known_files = pfr.governance_sensitive_files
        if not known_files or fc.rel_path in known_files:
            return Decision(allowed=True)
        # Fall through: new file not covered by existing cosmetic justification

    # Check if RCA exists and is substantive
    if pfr.rca and len(pfr.rca.strip()) >= PFR_RCA_MIN_LENGTH:
        return Decision(allowed=True)

    # v1 compat: if diagnosis_written is true (from v1 session), allow
    if pfr._v1_diagnosis_written:
        return Decision(allowed=True)

    # No PFR state at all yet — this is the first governance-sensitive edit attempt
    # The gate blocks to force the agent to write RCA first
    return Decision(
        allowed=False,
        reason=(
            "BLOCKED: Governance-sensitive file edit requires root cause analysis. (PFR)\n"
            "Before editing, write your root cause analysis to pfr_state.rca in\n"
            ".prawduct/.session-governance.json. Include the 5 whys:\n"
            "  1. What's the immediate problem?\n"
            "  2. Why does it happen?\n"
            "  3. What's the deeper structural cause?\n"
            "  4. What class of problem is this?\n"
            "  5. What would prevent the class, not just this instance?\n"
            "Or if cosmetic: set pfr_state.cosmetic_justification and pfr_state.required: false."
        ),
        rule="pfr",
    )


def _check_chunk_review(file_path: str, state: SessionState) -> Decision:
    """Chunk review gate: product files blocked when review debt exists.

    Exempts project-state.yaml and .session-governance.json.
    """
    basename = os.path.basename(file_path)
    if basename in ("project-state.yaml", ".session-governance.json"):
        return Decision(allowed=True)

    debt = state.governance.chunks_completed_without_review
    if debt > 0:
        return Decision(
            allowed=False,
            reason=f"BLOCKED: {debt} chunk(s) completed without Critic review. Run Governance Review.",
            rule="chunk_review",
        )

    return Decision(allowed=True)
