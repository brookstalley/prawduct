"""Observed hook receipts for the experimental Codex adapter.

Receipts are diagnostic evidence, not proof that Codex currently trusts hooks.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def repo_identity(project: Path) -> str | None:
    """Identify a governed checkout by its canonical Git common directory."""
    try:
        root = Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=project,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()).resolve(strict=True)
        common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], cwd=root,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        git_dir = (root / common).resolve(strict=True)
        if not (root / ".prawduct").is_dir():
            return None
        return hashlib.sha256(str(git_dir).encode()).hexdigest()
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def _state_dir(project: Path) -> Path | None:
    configured = os.environ.get("PLUGIN_DATA")
    if not configured or not Path(configured).is_absolute():
        return None
    directory = Path(configured).resolve()
    try:
        directory.relative_to(project.resolve())
        return None  # A receipt must live outside the governed checkout.
    except ValueError:
        return directory / "prawduct-observed-hooks"


def marker_path(project: Path, session_id: str | None) -> Path | None:
    identity = repo_identity(project)
    directory = _state_dir(project)
    if identity is None or directory is None or not session_id:
        return None
    key = hashlib.sha256(f"{identity}\0{session_id}".encode()).hexdigest()
    return directory / f"{key}.json"


def read_marker(project: Path, session_id: str | None) -> dict | None:
    path = marker_path(project, session_id)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(data, dict) or data.get("repo_identity") != repo_identity(project)
            or data.get("session_id") != session_id or not isinstance(data.get("events"), list)):
        return None
    return data


def record(project: Path, event, *, source: str | None = None,
           overflow: bool | None = None) -> bool:
    """Record one fired hook; a valid boundary replaces only its own marker."""
    path = marker_path(project, event.session_id)
    if path is None or (event.event == "session_start" and event.session_boundary is None):
        return False
    previous = None if event.session_boundary is True else read_marker(project, event.session_id)
    data = previous or {
        "repo_identity": repo_identity(project), "session_id": event.session_id, "events": [],
    }
    item = {
        "event": event.event,
        "fields_present": sorted(event.fields_present),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    if event.event == "session_start":
        item.update(source=source, boundary=event.session_boundary, overflow=overflow)
    data["events"].append(item)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".receipt-", delete=False) as temp:
            json.dump(data, temp, sort_keys=True)
            temp_path = Path(temp.name)
        try:
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
    except OSError:
        return False
    return True
