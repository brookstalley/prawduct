"""PostToolUse edit tracking.

Replaces governance-tracker.sh logic (~287 lines). Tracks edited files,
updates governance state, triggers DCP/PFR when thresholds are met.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Optional

from . import trace as tr
from .classify import GOVERNANCE_SENSITIVE_PREFIXES, classify
from .context import Context, ProductPaths
from .state import SessionState, now_iso


# DCP trigger threshold: distinct governed files before classification required
DCP_FILE_THRESHOLD = 3

# File prefixes that are documentation/config — not behavioral changes.
# When ALL edited files match these, DCP auto-classifies as mechanical.
DOC_ONLY_PREFIXES = (
    "docs/",
    "templates/",
    ".prawduct/artifacts/",
    ".prawduct/framework-observations/",
)
DOC_ONLY_FILES = (
    "README.md",
    "CLAUDE.md",
    ".claude/settings.json",
)


def track(tool_input: dict, ctx: Context, state: SessionState, product: ProductPaths = None) -> None:
    """Track an edit. Update state, trigger DCP/PFR if needed.

    Args:
        tool_input: Hook JSON with tool_name and tool_input.
        ctx: Resolved governance context.
        state: Session state to update (modified in place, caller saves).
        product: Per-file product paths (resolved from file's git root).
    """
    inner = tool_input.get("tool_input", {})
    file_path = inner.get("file_path", "")
    if not file_path:
        return

    fc = classify(file_path, ctx)

    # Ungoverned files: nothing to track
    if not fc.is_framework and not fc.is_product:
        return

    timestamp = now_iso()

    if fc.is_framework:
        _track_framework_edit(fc, file_path, timestamp, ctx, state, product=product)
    elif fc.is_product:
        _track_product_edit(fc, file_path, timestamp, ctx, state)

    state.governance.last_updated = timestamp


def _track_framework_edit(
    fc, file_path: str, timestamp: str, ctx: Context, state: SessionState, product: ProductPaths = None
) -> None:
    """Track a framework file edit."""
    rel_path = fc.rel_path
    edits = state.framework_edits

    # Update file entry
    found = False
    for entry in edits.files:
        if entry["path"] == rel_path:
            entry["edit_count"] += 1
            entry["last_modified"] = timestamp
            found = True
            break
    if not found:
        edits.files.append({
            "path": rel_path,
            "first_modified": timestamp,
            "last_modified": timestamp,
            "edit_count": 1,
        })
    edits.total_edits += 1

    # Maintain .critic-pending flag
    pending_path = product.critic_pending if product else ctx.critic_pending
    try:
        with open(pending_path, "w") as f:
            f.write(timestamp)
    except OSError:
        pass

    # DCP trigger: 3+ distinct governed files without active DCP
    distinct_files = len(edits.files)
    dcp = state.dcp
    already_classified = dcp.tier is not None
    if (
        distinct_files >= DCP_FILE_THRESHOLD
        and not dcp.active
        and not dcp.needs_classification
        and not already_classified
    ):
        # Auto-classify as mechanical if all edits are doc/config only
        if _all_doc_only(edits.files):
            dcp.tier = "mechanical"
            dcp.triggered_at_file_count = distinct_files
        else:
            dcp.needs_classification = True
            dcp.triggered_at_file_count = distinct_files

    # PFR trigger: governance-sensitive files (existing only).
    # New files are additive — they can't break existing behavior, so they
    # don't require root cause analysis. PFR protects against thoughtless
    # modifications to existing governance code, not new capability creation.
    # Note: this hook runs PostToolUse (file already on disk), so we use
    # git ls-files to check if the file is tracked — untracked = new.
    is_gov_sensitive = any(
        rel_path.startswith(p) for p in GOVERNANCE_SENSITIVE_PREFIXES
    )
    is_new_file = is_gov_sensitive and not _is_git_tracked(file_path)

    if is_gov_sensitive and not is_new_file:
        pfr = state.pfr
        if not pfr.required:
            # First governance-sensitive edit — initialize PFR
            pfr.required = True
            pfr.governance_sensitive_files = [rel_path]
        else:
            # Already tracking — add file if not listed
            if rel_path not in pfr.governance_sensitive_files:
                pfr.governance_sensitive_files.append(rel_path)

    classification = "governance_sensitive" if is_gov_sensitive else "framework"
    tr.event(state, "edit_tracked", {
        "file": rel_path,
        "classification": "framework",
        "governance_sensitive": is_gov_sensitive,
        "distinct_files": distinct_files,
        "triggers": _active_triggers(state),
    })


def _track_product_edit(
    fc, file_path: str, timestamp: str, ctx: Context, state: SessionState
) -> None:
    """Track a product file edit."""
    basename = os.path.basename(file_path)
    gov = state.governance

    if basename == "project-state.yaml":
        _track_project_state_change(file_path, state)
    else:
        gov.product_files_changed += 1
        gov.last_product_file_edit = timestamp

    tr.event(state, "edit_tracked", {
        "file": fc.rel_path or basename,
        "classification": "product",
        "governance_sensitive": False,
    })


def _track_project_state_change(file_path: str, state: SessionState) -> None:
    """Track changes to project-state.yaml: chunk review counting,
    stage transitions, governance checkpoints.

    Uses correct field names: chunk_id/id (not 'name' primary).
    """
    try:
        import yaml
    except ImportError:
        return

    try:
        with open(file_path) as f:
            ps = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return

    if not ps:
        return

    gov = state.governance
    build_plan = ps.get("build_plan", {})
    chunks = build_plan.get("chunks", [])
    build_state = ps.get("build_state", {})
    reviews = build_state.get("reviews", [])

    # Chunk review counting — use correct field names
    reviewed_chunks: set[str] = set()
    for review in reviews:
        # Reviews use chunk_id (primary) or chunk or after_chunk
        chunk_id = review.get("chunk_id", review.get("chunk", review.get("after_chunk", "")))
        if chunk_id:
            reviewed_chunks.add(chunk_id)

    unreviewed = []
    for chunk in chunks:
        status = chunk.get("status", "pending")
        # Chunks use id (primary) or name
        chunk_id = chunk.get("id", chunk.get("name", ""))
        if status in ("complete", "review") and chunk_id not in reviewed_chunks:
            unreviewed.append(chunk_id)

    gov.chunks_completed_without_review = len(unreviewed)

    # Stage transition tracking
    current_stage = ps.get("current_stage", "")
    if current_stage and gov.last_frp_stage and current_stage != gov.last_frp_stage:
        gov.stage_transitions_without_frp += 1

    # Governance checkpoint detection
    checkpoints = build_plan.get("governance_checkpoints", [])
    completed_chunk_count = sum(1 for c in chunks if c.get("status") == "complete")
    overdue: list[str] = []
    for cp in checkpoints:
        trigger = cp.get("after_chunk", cp.get("trigger", ""))
        completed = cp.get("completed", False)
        if not completed:
            if isinstance(trigger, int) and completed_chunk_count >= trigger:
                overdue.append(f"after chunk {trigger}")
            elif isinstance(trigger, str):
                for chunk in chunks:
                    cid = chunk.get("id", chunk.get("name", ""))
                    if cid == trigger and chunk.get("status") == "complete":
                        overdue.append(f'after "{trigger}"')
                        break
    gov.governance_checkpoints_due = overdue


def _is_git_tracked(file_path: str) -> bool:
    """Check if a file is tracked by git (exists in the index).

    Untracked files are new — they were just created by the current tool
    call and haven't been committed yet. This is safe in PostToolUse
    because git index state doesn't change until git add.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True  # Fail safe: assume tracked (trigger PFR)


def _all_doc_only(files: list[dict]) -> bool:
    """Check if all tracked files are documentation/config (not behavioral)."""
    for entry in files:
        path = entry.get("path", "")
        if any(path.startswith(p) for p in DOC_ONLY_PREFIXES):
            continue
        if path in DOC_ONLY_FILES:
            continue
        return False
    return True


def _active_triggers(state: SessionState) -> list[str]:
    """List currently active governance triggers for trace context."""
    triggers = []
    if state.dcp.needs_classification:
        triggers.append("dcp_classification")
    if state.dcp.active:
        triggers.append(f"dcp_{state.dcp.tier}")
    if state.pfr.required:
        triggers.append("pfr")
    return triggers
