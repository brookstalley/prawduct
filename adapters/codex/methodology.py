#!/usr/bin/env python3
"""Resolve canonical Prawduct methodology files at skill use time."""

from __future__ import annotations

import sys

from session_start import _canonical_plugin


def main() -> int:
    root = _canonical_plugin()
    overview = root / "skills" / "methodology" / "SKILL.md" if root is not None else None
    guide = root / "methodology" / "building.md" if root is not None else None
    if overview is None or guide is None or not overview.is_file() or not guide.is_file():
        print("Prawduct experimental Codex methodology unavailable: canonical overview or building guide missing.",
              file=sys.stderr)
        return 2
    print(overview.resolve())
    print(guide.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
