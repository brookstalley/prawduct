"""Session state management for governance.

Single read/write path for .session-governance.json, replacing the duplicated
JSON manipulation in all 4 hooks. Includes schema versioning: reads v1 (current
bash hooks, no schema_version field) and v2 (Python module format). Always
writes v2.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


CURRENT_SCHEMA_VERSION = 2


@dataclass
class PFRState:
    """Post-Fix Reflection state."""

    required: bool = False
    rca: str = ""  # Natural language root cause analysis (v2)
    governance_sensitive_files: list[str] = field(default_factory=list)
    observation_file: Optional[str] = None
    cosmetic_justification: Optional[str] = None
    # v1 compat fields (read but not written)
    _v1_diagnosis_written: bool = False
    _v1_diagnosis: Optional[dict] = None


@dataclass
class DCPState:
    """Directional Change Protocol state."""

    active: bool = False
    needs_classification: bool = False
    triggered_at_file_count: int = 0
    tier: Optional[str] = None
    plan_description: Optional[str] = None
    plan_stage_review_completed: bool = False
    retrospective_completed: bool = False
    total_phases: int = 0
    phases_reviewed_count: int = 0
    observation_captured: bool = False
    artifacts_verified: list[str] = field(default_factory=list)


@dataclass
class GovernanceState:
    """Product governance tracking."""

    chunks_completed_without_review: int = 0
    last_critic_review_chunk: Optional[str] = None
    last_frp_stage: str = ""
    stage_transitions_without_frp: int = 0
    observations_captured_this_session: int = 0
    product_files_changed: int = 0
    last_product_file_edit: Optional[str] = None
    governance_checkpoints_due: list[str] = field(default_factory=list)
    last_updated: Optional[str] = None


@dataclass
class FrameworkEdits:
    """Framework edit tracking."""

    files: list[dict] = field(default_factory=list)
    total_edits: int = 0


@dataclass
class TraceBuffer:
    """In-session trace event buffer."""

    events: list[dict] = field(default_factory=list)


class SessionState:
    """Read/write .session-governance.json with structured access.

    Handles schema versioning: reads v1 (no schema_version) and v2.
    Always writes v2.
    """

    def __init__(self, path: str):
        self.path = path
        self.schema_version: int = CURRENT_SCHEMA_VERSION
        self.product_dir: str = ""
        self.product_output_dir: str = ""
        self.current_stage: str = ""
        self.session_started: str = ""
        self.pfr = PFRState()
        self.dcp = DCPState()
        self.governance = GovernanceState()
        self.framework_edits = FrameworkEdits()
        self.trace = TraceBuffer()
        self._raw: dict[str, Any] = {}

    @classmethod
    def load(cls, path: str) -> SessionState:
        """Load session state from file. Creates empty state if file missing."""
        state = cls(path)
        if not os.path.isfile(path):
            return state
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return state

        state._raw = data
        version = data.get("schema_version", 1)
        state.schema_version = version

        # Core fields
        state.product_dir = data.get("product_dir", "")
        state.product_output_dir = data.get("product_output_dir", "")
        state.current_stage = data.get("current_stage", "")
        state.session_started = data.get("session_started", "")

        # Framework edits
        fe = data.get("framework_edits", {})
        state.framework_edits = FrameworkEdits(
            files=fe.get("files", []),
            total_edits=fe.get("total_edits", 0),
        )

        # Governance state
        gov = data.get("governance_state", {})
        state.governance = GovernanceState(
            chunks_completed_without_review=gov.get("chunks_completed_without_review", 0),
            last_critic_review_chunk=gov.get("last_critic_review_chunk"),
            last_frp_stage=gov.get("last_frp_stage", ""),
            stage_transitions_without_frp=gov.get("stage_transitions_without_frp", 0),
            observations_captured_this_session=gov.get("observations_captured_this_session", 0),
            product_files_changed=gov.get("product_files_changed", 0),
            last_product_file_edit=gov.get("last_product_file_edit"),
            governance_checkpoints_due=gov.get("governance_checkpoints_due", []),
            last_updated=gov.get("last_updated"),
        )

        # DCP state
        dc = data.get("directional_change", {})
        state.dcp = DCPState(
            active=dc.get("active", False),
            needs_classification=dc.get("needs_classification", False),
            triggered_at_file_count=dc.get("triggered_at_file_count", 0),
            tier=dc.get("tier"),
            plan_description=dc.get("plan_description"),
            plan_stage_review_completed=dc.get("plan_stage_review_completed", False),
            retrospective_completed=dc.get("retrospective_completed", False),
            total_phases=dc.get("total_phases", 0),
            phases_reviewed_count=dc.get("phases_reviewed_count", 0),
            observation_captured=dc.get("observation_captured", False),
            artifacts_verified=dc.get("artifacts_verified", []),
        )

        # PFR state — handle v1 and v2 formats
        pfr = data.get("pfr_state", {})
        if version == 1:
            # v1: structured diagnosis with diagnosis_written flag
            state.pfr = PFRState(
                required=pfr.get("required", False),
                rca=_upgrade_pfr_v1_to_rca(pfr),
                governance_sensitive_files=pfr.get("governance_sensitive_files", []),
                observation_file=pfr.get("observation_file"),
                cosmetic_justification=pfr.get("cosmetic_justification"),
                _v1_diagnosis_written=pfr.get("diagnosis_written", False),
                _v1_diagnosis=pfr.get("diagnosis"),
            )
        else:
            # v2: natural language RCA
            state.pfr = PFRState(
                required=pfr.get("required", False),
                rca=pfr.get("rca", ""),
                governance_sensitive_files=pfr.get("governance_sensitive_files", []),
                observation_file=pfr.get("observation_file"),
                cosmetic_justification=pfr.get("cosmetic_justification"),
            )

        # Trace buffer: in-memory only, no longer loaded from session file.
        # Traces are written directly to .session-trace.jsonl by trace.event().
        # Legacy "trace" key in file is ignored on load.
        state.trace = TraceBuffer()

        return state

    def save(self) -> None:
        """Save session state as v2 format."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "product_dir": self.product_dir,
            "product_output_dir": self.product_output_dir,
            "current_stage": self.current_stage,
            "session_started": self.session_started,
            "framework_edits": {
                "files": self.framework_edits.files,
                "total_edits": self.framework_edits.total_edits,
            },
            "governance_state": {
                "chunks_completed_without_review": self.governance.chunks_completed_without_review,
                "last_critic_review_chunk": self.governance.last_critic_review_chunk,
                "last_frp_stage": self.governance.last_frp_stage,
                "stage_transitions_without_frp": self.governance.stage_transitions_without_frp,
                "observations_captured_this_session": self.governance.observations_captured_this_session,
                "product_files_changed": self.governance.product_files_changed,
                "last_product_file_edit": self.governance.last_product_file_edit,
                "governance_checkpoints_due": self.governance.governance_checkpoints_due,
                "last_updated": self.governance.last_updated,
            },
            "directional_change": {
                "active": self.dcp.active,
                "needs_classification": self.dcp.needs_classification,
                "triggered_at_file_count": self.dcp.triggered_at_file_count,
                "tier": self.dcp.tier,
                "plan_description": self.dcp.plan_description,
                "plan_stage_review_completed": self.dcp.plan_stage_review_completed,
                "retrospective_completed": self.dcp.retrospective_completed,
                "total_phases": self.dcp.total_phases,
                "phases_reviewed_count": self.dcp.phases_reviewed_count,
                "observation_captured": self.dcp.observation_captured,
                "artifacts_verified": self.dcp.artifacts_verified,
            },
            "pfr_state": {
                "required": self.pfr.required,
                "rca": self.pfr.rca,
                "governance_sensitive_files": self.pfr.governance_sensitive_files,
                "observation_file": self.pfr.observation_file,
                "cosmetic_justification": self.pfr.cosmetic_justification,
            },
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def to_dict(self) -> dict[str, Any]:
        """Return the full state as a dict (for trace archival)."""
        # Force a save-like serialization
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "product_dir": self.product_dir,
            "product_output_dir": self.product_output_dir,
            "current_stage": self.current_stage,
            "session_started": self.session_started,
            "framework_edits": {
                "files": self.framework_edits.files,
                "total_edits": self.framework_edits.total_edits,
            },
            "governance_state": {
                "chunks_completed_without_review": self.governance.chunks_completed_without_review,
                "last_critic_review_chunk": self.governance.last_critic_review_chunk,
                "last_frp_stage": self.governance.last_frp_stage,
                "stage_transitions_without_frp": self.governance.stage_transitions_without_frp,
                "observations_captured_this_session": self.governance.observations_captured_this_session,
                "product_files_changed": self.governance.product_files_changed,
                "last_product_file_edit": self.governance.last_product_file_edit,
                "governance_checkpoints_due": self.governance.governance_checkpoints_due,
                "last_updated": self.governance.last_updated,
            },
            "directional_change": {
                "active": self.dcp.active,
                "needs_classification": self.dcp.needs_classification,
                "triggered_at_file_count": self.dcp.triggered_at_file_count,
                "tier": self.dcp.tier,
                "plan_description": self.dcp.plan_description,
                "plan_stage_review_completed": self.dcp.plan_stage_review_completed,
                "retrospective_completed": self.dcp.retrospective_completed,
                "total_phases": self.dcp.total_phases,
                "phases_reviewed_count": self.dcp.phases_reviewed_count,
                "observation_captured": self.dcp.observation_captured,
                "artifacts_verified": self.dcp.artifacts_verified,
            },
            "pfr_state": {
                "required": self.pfr.required,
                "rca": self.pfr.rca,
                "governance_sensitive_files": self.pfr.governance_sensitive_files,
                "observation_file": self.pfr.observation_file,
                "cosmetic_justification": self.pfr.cosmetic_justification,
            },
        }


def _upgrade_pfr_v1_to_rca(pfr: dict) -> str:
    """Convert v1 structured PFR diagnosis to v2 natural language RCA.

    If diagnosis_written is true and a diagnosis dict exists, synthesize
    a natural language RCA from the structured fields.
    """
    if not pfr.get("diagnosis_written", False):
        return ""
    diagnosis = pfr.get("diagnosis")
    if not diagnosis or not isinstance(diagnosis, dict):
        return ""

    parts = []
    if diagnosis.get("symptom"):
        parts.append(f"Symptom: {diagnosis['symptom']}")
    five_whys = diagnosis.get("five_whys", [])
    if five_whys:
        for i, why in enumerate(five_whys, 1):
            parts.append(f"Why {i}: {why}")
    if diagnosis.get("root_cause"):
        parts.append(f"Root cause: {diagnosis['root_cause']}")
    if diagnosis.get("root_cause_category"):
        parts.append(f"Category: {diagnosis['root_cause_category']}")
    if diagnosis.get("meta_fix_plan"):
        parts.append(f"Meta-fix: {diagnosis['meta_fix_plan']}")
    return " | ".join(parts) if parts else ""


def now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
