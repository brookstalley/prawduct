#!/usr/bin/env python3
"""Experimental Codex SessionStart bridge into the canonical Prawduct plugin.

The adapter owns registration and dispatch only. All governance text and state
transitions remain in the canonical ``plugin/`` tree.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CANONICAL_ROOT_VAR = "PRAWDUCT_CANONICAL_PLUGIN_ROOT"
REQUIRED_FILES = (
    "lib/host.py", "hooks/banner.py", "hooks/digest.py",
    "bin/prawduct-hook", "methodology/session-digest.md",
)


def _canonical_plugin() -> Path | None:
    """Use an explicit installed root, or the adjacent source-checkout tree."""
    configured = os.environ.get(CANONICAL_ROOT_VAR)
    if configured is not None:
        if not configured.strip() or not Path(configured).is_absolute():
            return None
        candidate = Path(configured)
    else:
        candidate = Path(__file__).resolve().parents[2] / "plugin"
    try:
        root = candidate.resolve(strict=True)
        if root.is_dir() and all((root / name).is_file() for name in REQUIRED_FILES):
            return root
    except (OSError, RuntimeError):
        pass
    return None


PLUGIN = _canonical_plugin()
if PLUGIN is not None:
    sys.path.insert(0, str(PLUGIN))
    from lib import host  # noqa: E402

CONTEXT_LIMIT = 5000
EXPERIMENTAL = "Prawduct experimental Codex Phase 1 SessionStart briefing."
REFUSAL = "Prawduct experimental Codex SessionStart refused: missing or unverified source; no session state changed."
UNAVAILABLE = ("Prawduct experimental Codex SessionStart unavailable: canonical "
               "plugin root missing or invalid. Set PRAWDUCT_CANONICAL_PLUGIN_ROOT "
               "to the absolute path of Prawduct's plugin/ directory; no session state changed.")


def _run(path: Path, args: list[str], project: Path) -> tuple[str, str]:
    env = os.environ.copy()
    env[host.HOST_VARIABLE] = "codex"
    env[host._CODEX_PROJECT_DIR_VAR] = str(project)
    result = subprocess.run(
        [sys.executable, str(path), *args], cwd=project, env=env,
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode:
        return "", f"Prawduct experimental SessionStart: {path.name} exited {result.returncode}: {result.stderr.strip()}"
    return result.stdout.strip(), result.stderr.strip()


def _digest_text(output: str) -> str:
    if not output:
        return ""
    try:
        return json.loads(output)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        return "Prawduct experimental SessionStart: digest response could not be read."


def _context(parts: list[str]) -> str:
    text = "\n\n".join(part for part in parts if part)
    # Codex's handler threshold is approximate tokens. Four characters per
    # token is a conservative local signal, not a promise of host tokenization.
    if len(text) // 4 > CONTEXT_LIMIT:
        return ("Prawduct experimental Codex SessionStart context exceeds the "
                "5000-token handler limit; read the full briefing from Prawduct state.\n" + text)
    return text


def main() -> int:
    if PLUGIN is None:
        # The host seam is unavailable, so fail the hook with a readable
        # diagnostic. No canonical script or state write has run.
        print(UNAVAILABLE, file=sys.stderr)
        return 1
    os.environ[host.HOST_VARIABLE] = "codex"
    try:
        raw = json.load(sys.stdin)
    except (ValueError, OSError):
        raw = {}
    event = host.read_event("session_start", raw)
    if event.session_boundary is None:
        host.emit_session_context(f"{EXPERIMENTAL}\n{REFUSAL}")
        return 0
    if not event.cwd:
        host.emit_session_context(f"{EXPERIMENTAL}\nPrawduct SessionStart refused: missing cwd.")
        return 0
    from lib.gitstate import resolve_project_dir

    project = resolve_project_dir(event.cwd, Path(event.cwd))
    if not (project / ".prawduct").is_dir():
        return 0
    from observation import record

    parts = [EXPERIMENTAL]
    for script, args in (
        (PLUGIN / "hooks" / "banner.py", []),
        (PLUGIN / "hooks" / "digest.py", []),
        (PLUGIN / "bin" / "prawduct-hook", ["clear", "--session-start"] + ([] if event.session_boundary else ["--brief-only"])),
    ):
        output, errors = _run(script, args, project)
        # stderr notices that Claude shows in its terminal must be visible to
        # the Codex model. Place them before the briefing from this command.
        if errors:
            parts.append(errors)
        if output:
            parts.append(_digest_text(output) if script.name == "digest.py" else output)
    core = project / ".claude" / "rules" / "learnings" / "core.md"
    if core.is_file():
        parts.append("Prawduct core learnings:\n" + core.read_text(encoding="utf-8"))
    context = _context(parts)
    record(project, event, source=event.source,
           overflow=context.startswith("Prawduct experimental Codex SessionStart context exceeds"))
    host.emit_session_context(context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
