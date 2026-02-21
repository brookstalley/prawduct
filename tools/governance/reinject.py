"""SessionStart compact hook: post-compaction context reinject.

Outputs minimal recovery text after context compaction: skill file paths,
current governance debt, and instruction to re-read from disk.
"""

from __future__ import annotations

import json
import os

from .context import Context


def build_reinject(ctx: Context) -> str:
    """Build the reinject text block for post-compaction recovery."""
    session_file = ctx.session_file
    debt_lines: list[str] = []

    if os.path.isfile(session_file):
        try:
            with open(session_file) as f:
                session = json.load(f)

            fw = session.get("framework_edits", {})
            fw_files = fw.get("files", [])
            if fw_files:
                debt_lines.append(f"Framework files edited: {len(fw_files)}")

            gov = session.get("governance_state", {})
            chunks = gov.get("chunks_completed_without_review", 0)
            if chunks > 0:
                debt_lines.append(f"Chunks without review: {chunks}")
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    parts = [
        "CONTEXT RESTORED AFTER COMPACTION.",
        "",
        f"Skill files are on disk \u2014 read them when needed or when hooks block you.",
        f"Start: {ctx.framework_root}/skills/orchestrator/SKILL.md",
        f"Critic: invoke as agent per {ctx.framework_root}/skills/orchestrator/protocols/agent-invocation.md \u00a7 Critic Agent Protocol",
    ]

    if debt_lines:
        parts.append("")
        parts.append("GOVERNANCE DEBT:")
        parts.extend(debt_lines)

    return "\n".join(parts)
