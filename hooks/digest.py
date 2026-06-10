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

# Source of truth for the digest text — one canonical document per variant,
# bundled at the plugin root. This is the distilled session-start dose; the
# /prawduct:methodology reader skills serve the full guides on demand.
#
# Two variants (review-fixes Chunk 4): the FULL digest is the only carrier of
# framework defaults for product repos (thin-anchor CLAUDE.md), but in the
# prawduct framework repo itself it duplicated 40-50% of the always-loaded
# CLAUDE.md nearly 1:1. The SLIM variant — pointers to CLAUDE.md plus only the
# rules CLAUDE.md does not restate — is emitted when the governed repo IS the
# framework (see is_framework_repo); every product repo keeps the full digest.
DIGEST_RELPATH = ("methodology", "session-digest.md")
SLIM_DIGEST_RELPATH = ("methodology", "session-digest-slim.md")


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


def read_digest(root: Path, slim: bool = False) -> str:
    """Read the bundled session-start guidance digest.

    With ``slim=True``, prefer the slim variant; fall back to the full digest
    when the slim file is missing or empty (an older cached plugin copy may not
    bundle it yet — a framework session must still get *a* digest, never none).
    """
    if slim:
        try:
            text = root.joinpath(*SLIM_DIGEST_RELPATH).read_text(encoding="utf-8").strip()
            if text:
                return text
        except OSError:
            pass  # stale plugin cache without the slim variant -> full digest
    return (root.joinpath(*DIGEST_RELPATH)).read_text(encoding="utf-8").strip()


def project_dir() -> Path:
    """The governed repo — ``CLAUDE_PROJECT_DIR`` (Claude Code sets it for every
    hook), falling back to cwd for direct invocation."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def in_prawduct_repo() -> bool:
    """True when the consuming repo is Prawduct-governed — i.e. has a ``.prawduct/``.

    The plugin is user-scoped, so this SessionStart hook fires in *every* repo the
    user opens. The digest is product-session governance guidance; it must stay
    silent in repos that never onboarded. This mirrors the gate the banner
    (``hooks/banner.py``) and the Stop hook (``prawduct-hook`` ``cmd_stop``) already
    apply — ``.prawduct/`` is the single is-this-a-Prawduct-repo marker.

    Read-only: only ``.is_dir()``.
    """
    return (project_dir() / ".prawduct").is_dir()


def is_framework_repo(proj: Path) -> bool:
    """True when the governed repo IS the prawduct framework itself.

    Marker: ``.claude-plugin/plugin.json`` at the repo root with
    ``"name": "prawduct"`` — the plugin manifest only the framework repo carries
    (product repos install the plugin from the marketplace cache; their repo
    roots have no ``.claude-plugin/``). Fail-safe: any read or parse anomaly
    classifies as NOT the framework — the full digest is the safe default,
    never a crash and never a silently slimmed product session.
    """
    manifest = proj / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("name") == "prawduct"


def main() -> int:
    # Emit the governance digest only in a Prawduct-governed repo; stay silent
    # (and write nothing) everywhere else. Without this the user-scoped plugin
    # injects governance context into every repo the user opens (see banner.py /
    # cmd_stop, which already gate on .prawduct/).
    if not in_prawduct_repo():
        return 0
    try:
        digest = read_digest(plugin_root(), slim=is_framework_repo(project_dir()))
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
