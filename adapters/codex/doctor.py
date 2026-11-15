#!/usr/bin/env python3
"""Observed-only diagnostics for the experimental Codex adapter."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from observation import read_marker, repo_identity

PINNED_VERSION = "0.156.1"
MAX_RECEIPT_AGE = timedelta(days=1)


def _version() -> dict:
    try:
        output = subprocess.check_output(["codex", "--version"], text=True,
                                         stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        output = "unavailable"
    version = output.split()[-1] if output.split() else "unavailable"
    return {"status": "ok" if version == PINNED_VERSION else "not-verified",
            "detail": f"observed {output}; pinned fixture target {PINNED_VERSION}"}


def _hook_declaration(adapter: Path) -> dict:
    try:
        hooks = json.loads((adapter / "hooks" / "hooks.json").read_text())['hooks']
        expected = {"SessionStart": "session_start.py", "Stop": "stop.py"}
        valid = all(hooks[name][0]["hooks"][0]["command"] ==
                    f'python3 "${{PLUGIN_ROOT}}/{script}"' for name, script in expected.items())
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        valid = False
    return {"status": "ok" if valid else "not-verified",
            "detail": "local hooks.json declares expected adapter commands" if valid
            else "local hooks.json declaration unavailable or changed"}


def _fresh_events(marker: dict | None) -> list[dict]:
    if marker is None:
        return []
    fresh = []
    for event in marker["events"]:
        if not isinstance(event, dict):
            continue
        try:
            observed = datetime.fromisoformat(event["observed_at"])
            if observed.tzinfo is not None and (timedelta(0) <=
                    datetime.now(timezone.utc) - observed <= MAX_RECEIPT_AGE):
                fresh.append(event)
        except (ValueError, TypeError, KeyError):
            continue
    return fresh


def diagnose(project: Path, session_id: str | None, adapter: Path) -> dict:
    identity = repo_identity(project)
    marker = read_marker(project, session_id) if identity and session_id else None
    events = _fresh_events(marker)
    starts = [item for item in events if item.get("event") == "session_start"]
    stops = [item for item in events if item.get("event") == "stop"]
    # Hook stdin carries a current session_id, but this later CLI invocation
    # has no independent documented source for its current session ID. The
    # caller's argument and a matching marker cannot prove currentness.
    def observed(items: list[dict]) -> dict:
        return {"status": "not-verified",
                "detail": "matching receipt exists, but current session identity is unverified"
                if items else "no fresh matching hook observation"}
    return {
        "experimental": True,
        "session_identity": {"status": "not-verified",
                             "detail": "caller-supplied ID is not independent current-session evidence"
                             if identity and session_id else
                             "supply --session-id in a governed repository to inspect receipts"},
        "pinned_codex_version": _version(),
        "hook_declaration": _hook_declaration(adapter),
        "registration": {"status": "not-verified",
                         "detail": "no independent read-only Codex host registry receipt"},
        "trust": {"status": "not-verified", "detail": "no read-only Codex hook trust receipt"},
        "session_start": observed(starts),
        "stop": observed(stops),
        "d9_overflow": {"status": "not-verified",
                        "detail": "overflow receipt exists, but current session identity is unverified"
                        if starts and isinstance(starts[-1].get("overflow"), bool) else
                        "no fresh matching SessionStart overflow observation"},
        "observed_events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", help="hook-supplied session ID whose receipts to inspect")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(diagnose(args.repo.resolve(), args.session_id,
                              Path(__file__).resolve().parent), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
