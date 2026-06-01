#!/usr/bin/env python3
"""Prawduct plugin SessionStart banner.

Chunk 1 of the v2.0.0 plugin-distribution build plan — the thin vertical slice
that proves the plugin loads, the SessionStart hook fires, and the version is
read from the bundled ``plugin.json`` (the version source of truth, design §5).
The full session briefing and the version-delta banner arrive in Chunk 5 / 7;
this script intentionally does the minimum to prove the layers connect.

Governing invariant (design §2): the plugin ships immutable, read-only code.
This script reads ONLY plugin-bundled files via ``${CLAUDE_PLUGIN_ROOT}`` and
writes nothing. All mutable, per-repo state lives in
``${CLAUDE_PROJECT_DIR}/.prawduct/`` and is not touched here.

Output channel: SessionStart hook stdout is surfaced to the user (as a
"hook success" line) and added to the model's context — matching how the
legacy ``tools/product-hook`` SessionStart hook emits its briefing.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def plugin_root() -> Path:
    """Resolve the plugin root.

    Prefers ``CLAUDE_PLUGIN_ROOT`` (set by Claude Code when the hook fires).
    Falls back to the parent of this file's directory (``hooks/`` -> root) so
    the script is also runnable directly, e.g. from tests.
    """
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


def read_version(root: Path) -> str:
    """Read the semver ``version`` from the bundled plugin manifest."""
    manifest = root / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return str(data.get("version", "unknown"))


def main() -> int:
    try:
        version = read_version(plugin_root())
    except Exception as exc:  # prawduct:ok-broad-except — a banner failure must never break session start
        print(f"NOTE: Prawduct banner could not read plugin version: {exc}", file=sys.stderr)
        return 0
    print(f"═══ Prawduct v{version} (plugin) ═══")
    return 0


if __name__ == "__main__":
    sys.exit(main())
