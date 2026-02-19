# Traces are local-only. This module makes no network calls.
# It does not import urllib, requests, http, or socket.
"""Trace event emission, persistence, and rotation.

Events are written directly to .session-trace.jsonl (one JSON line per event)
on every hook invocation. This avoids mutating .session-governance.json on
every tool call, which caused race conditions when the agent tried to edit
the session state file (hooks would modify it between Read and Edit).

At commit time, events are read from the trace file and archived to
traces/sessions/<ts>.json with a summary line in traces/session-log.jsonl.

Trace events contain governance decisions (gate checks, file classifications,
debt profiles). They never contain file contents, code diffs, user messages,
or product details. File paths are logged for debugging classification bugs.
"""

from __future__ import annotations

import json
import os
import glob as glob_mod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import SessionState


# Maximum session archives to keep (oldest deleted on rotation)
MAX_SESSION_ARCHIVES = 20


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event(state: SessionState, event_type: str, detail: dict) -> None:
    """Append a trace event to .session-trace.jsonl (write-through).

    Called by gate/tracker/stop on every decision. Each call appends one
    JSON line to the trace file and keeps an in-memory copy on the state
    object. The trace file lives alongside .session-governance.json but is
    never read during normal hook operation — only at commit/archive time.

    Args:
        state: Session state (used for in-memory buffer and trace file path).
        event_type: Event type (e.g., "gate_check", "edit_tracked", "stop_check").
        detail: Event-specific data. Must not contain file contents or user messages.
    """
    entry = {
        "ts": now_iso(),
        "v": 1,
        "type": event_type,
        **detail,
    }
    # In-memory buffer (for tests and within-process access)
    state.trace.events.append(entry)

    # Write-through to JSONL file
    trace_path = os.path.join(
        os.path.dirname(state.path), ".session-trace.jsonl"
    )
    try:
        with open(trace_path, "a") as f:
            f.write(json.dumps(entry))
            f.write("\n")
    except OSError:
        pass  # Never fail a hook because trace I/O failed


def _load_trace_events(state: SessionState) -> list[dict]:
    """Read all trace events from .session-trace.jsonl.

    Returns the in-memory buffer if the file doesn't exist (e.g., in tests).
    """
    trace_path = os.path.join(
        os.path.dirname(state.path), ".session-trace.jsonl"
    )
    events = []
    if os.path.isfile(trace_path):
        try:
            with open(trace_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
    # Fall back to in-memory buffer if file was empty/missing
    return events if events else state.trace.events


def persist(state: SessionState, traces_dir: str) -> None:
    """Archive session state and write summary to session log.

    Called by the commit gate after all checks pass.

    Level 2: Full session archive -> traces/sessions/<ts>.json
    Level 1: Summary line -> traces/session-log.jsonl

    Args:
        state: Complete session state to archive.
        traces_dir: Path to the traces directory (e.g., .prawduct/traces/).
    """
    sessions_dir = os.path.join(traces_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    ts = now_iso().replace(":", "-")  # Filesystem-safe timestamp

    # Load events from trace file for archival
    events = _load_trace_events(state)

    # Level 2: full session archive (state + trace events)
    archive_data = state.to_dict()
    archive_data["trace"] = {"events": events}
    archive_path = os.path.join(sessions_dir, f"{ts}.json")
    with open(archive_path, "w") as f:
        json.dump(archive_data, f, indent=2)
        f.write("\n")

    # Level 1: summary line
    summary = _build_summary(state, events)
    log_path = os.path.join(traces_dir, "session-log.jsonl")
    with open(log_path, "a") as f:
        f.write(json.dumps(summary))
        f.write("\n")

    # Rotate: keep only MAX_SESSION_ARCHIVES
    _rotate_archives(sessions_dir)


def _build_summary(state: SessionState, events: list[dict] | None = None) -> dict:
    """Build a Level 1 summary from session state and trace events."""
    if events is None:
        events = _load_trace_events(state)

    # Count gate blocks by rule
    gate_blocks: dict[str, int] = {}
    for ev in events:
        if ev.get("type") == "gate_block":
            rule = ev.get("rule", "unknown")
            gate_blocks[rule] = gate_blocks.get(rule, 0) + 1

    # Count files by classification
    fw_count = 0
    prod_count = 0
    gov_sensitive_count = 0
    for ev in events:
        if ev.get("type") == "edit_tracked":
            cls = ev.get("classification", "")
            if cls == "framework":
                fw_count += 1
            elif cls == "product":
                prod_count += 1
            if ev.get("governance_sensitive"):
                gov_sensitive_count += 1

    return {
        "v": 1,
        "ts": now_iso(),
        "session_started": state.session_started,
        "stage": state.current_stage,
        "files_edited": {
            "framework": fw_count,
            "product": prod_count,
            "governance_sensitive": gov_sensitive_count,
        },
        "gate_blocks": gate_blocks,
        "pfr_triggered": state.pfr.required,
        "dcp_tier": state.dcp.tier,
        "observations_captured": state.governance.observations_captured_this_session,
        "trace_event_count": len(events),
    }


def _rotate_archives(sessions_dir: str) -> None:
    """Keep only the most recent MAX_SESSION_ARCHIVES files."""
    archives = sorted(glob_mod.glob(os.path.join(sessions_dir, "*.json")))
    if len(archives) > MAX_SESSION_ARCHIVES:
        for old in archives[: len(archives) - MAX_SESSION_ARCHIVES]:
            try:
                os.remove(old)
            except OSError:
                pass
