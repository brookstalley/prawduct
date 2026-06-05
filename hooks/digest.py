#!/usr/bin/env python3
"""Prawduct plugin SessionStart guidance digest.

Chunk 6 of the v2.0.0 plugin-distribution build plan. Injects a compact,
*supplemental* governance digest into the model's context at session start via
the SessionStart ``additionalContext`` channel (design §4: the full methodology
lives in the plugin and is read on demand through the ``/prawduct:*`` reader
skills; this digest is the session-start reminder, not a replacement for the
authoritative rules in CLAUDE.md).

Output contract (verified against the Claude Code hooks reference, 2026-06-01):
a SessionStart hook injects context by printing
``{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "…"}}``
to stdout. Multiple SessionStart hooks compose — the banner (plain stdout) and
the ``prawduct-hook clear`` briefing (plain stdout) still render alongside this
JSON form. additionalContext over ~10,000 characters is spilled to a file by
Claude Code, so the digest is deliberately kept well under that.

Governing invariant (design §2): the plugin ships immutable, read-only code.
This script reads ONLY the plugin-bundled digest via ``${CLAUDE_PLUGIN_ROOT}``
(the whole plugin tree is copied into the cache on install, so a plugin-root
file resolves there) and writes nothing. All mutable, per-repo state lives in
``${CLAUDE_PROJECT_DIR}/.prawduct/`` and is not touched here.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Source of truth for the digest text — one canonical document bundled at the
# plugin root. This is the distilled session-start dose; the /prawduct:methodology
# reader skills serve the full guides on demand.
DIGEST_RELPATH = ("methodology", "session-digest.md")


def plugin_root() -> Path:
    """Resolve the plugin root.

    Prefers ``CLAUDE_PLUGIN_ROOT`` (set by Claude Code when the hook fires, and
    exported to hook subprocesses). Falls back to the parent of this file's
    directory (``hooks/`` -> root) so the script is runnable directly in tests.
    """
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


def read_digest(root: Path) -> str:
    """Read the bundled session-start guidance digest."""
    return (root.joinpath(*DIGEST_RELPATH)).read_text(encoding="utf-8").strip()


def in_prawduct_repo() -> bool:
    """True when the consuming repo is Prawduct-governed — i.e. has a ``.prawduct/``.

    The plugin is user-scoped, so this SessionStart hook fires in *every* repo the
    user opens. The digest is product-session governance guidance; it must stay
    silent in repos that never onboarded. This mirrors the gate the banner
    (``hooks/banner.py``) and the Stop hook (``prawduct-hook`` ``cmd_stop``) already
    apply — ``.prawduct/`` is the single is-this-a-Prawduct-repo marker.

    The repo is ``CLAUDE_PROJECT_DIR`` (Claude Code sets it for every hook),
    falling back to cwd for direct invocation. Read-only: only ``.is_dir()``.
    """
    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    return (proj / ".prawduct").is_dir()


def main() -> int:
    # Emit the governance digest only in a Prawduct-governed repo; stay silent
    # (and write nothing) everywhere else. Without this the user-scoped plugin
    # injects governance context into every repo the user opens (see banner.py /
    # cmd_stop, which already gate on .prawduct/).
    if not in_prawduct_repo():
        return 0
    try:
        digest = read_digest(plugin_root())
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a digest failure must never break session start
        print(f"NOTE: Prawduct could not read the session digest: {exc}", file=sys.stderr)
        return 0
    if not digest:
        return 0
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": digest,
        }
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
