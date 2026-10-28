#!/usr/bin/env python3
"""Experimental Codex Stop bridge into the canonical Prawduct hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

def main() -> int:
    from session_start import PLUGIN, UNAVAILABLE

    if PLUGIN is None:
        print(UNAVAILABLE.replace("SessionStart", "Stop"), file=sys.stderr)
        return 2
    from lib import host

    os.environ[host.HOST_VARIABLE] = "codex"
    try:
        raw = json.load(sys.stdin)
    except (ValueError, OSError):
        raw = {}
    event = host.read_event("stop", raw)
    project = Path(event.cwd or os.getcwd()).resolve()
    env = os.environ.copy()
    env[host._CODEX_PROJECT_DIR_VAR] = str(project)
    try:
        result = subprocess.run(
            [sys.executable, str(PLUGIN / "bin" / "prawduct-hook"), "stop"],
            input=json.dumps(raw), capture_output=True, text=True,
            cwd=project, env=env, timeout=120, check=False,
        )
    except Exception as exc:
        from observation import record
        record(project, event)
        return host.block(
            f"Prawduct experimental Codex Stop entry error: {type(exc).__name__}: {exc}\n"
            + "\n".join(host.codex_stop_coverage()) + "\n"
        )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    from observation import record
    record(project, event)
    if result.returncode not in (0, 2):
        return host.block(
            f"Prawduct experimental Codex Stop core exited {result.returncode}: "
            f"{result.stderr.strip() or 'no diagnostic'}\n"
            + "\n".join(host.codex_stop_coverage()) + "\n"
        )
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        reason = f"Prawduct experimental Codex Stop entry error: {type(exc).__name__}: {exc}\n"
        try:
            from session_start import PLUGIN
            if PLUGIN is not None:
                sys.path.insert(0, str(PLUGIN))
                from lib import host
                sys.exit(host.block(reason + "\n".join(host.codex_stop_coverage()) + "\n"))
        except ImportError:
            pass
        sys.stderr.write(reason)
        sys.exit(2)
