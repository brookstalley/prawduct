#!/usr/bin/env python3
"""Price each native `/code-review` fork a Claude Code session ran.

Usage: python3 -I fork_costs.py <session-transcript-dir>/subagents

A code-review fork is a subagent transcript whose first user message opens
with "Review target:"; its recipe line (`<level> effort → …`) is the level the
review actually RAN, which is not always the level asked for. Prints one row
per fork: the recipe level, model, wall clock from first to last record, and
token sums. The model, not this script, is what prices them.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

RECIPE = re.compile(r"`(\w+) effort → ")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


def fork_row(path: Path) -> dict | None:
    first = None
    stamps: list[str] = []
    models: set[str] = set()
    tokens = {"cache_create": 0, "cache_read": 0, "input": 0, "output": 0}
    for line in path.open(encoding="utf-8"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("timestamp"):
            stamps.append(record["timestamp"])
        message = record.get("message") or {}
        if first is None and record.get("type") == "user":
            first = _text(message.get("content", ""))
        usage = message.get("usage")
        if record.get("type") == "assistant" and usage:
            models.add(message.get("model", "?"))
            tokens["cache_create"] += usage.get("cache_creation_input_tokens", 0)
            tokens["cache_read"] += usage.get("cache_read_input_tokens", 0)
            tokens["input"] += usage.get("input_tokens", 0)
            tokens["output"] += usage.get("output_tokens", 0)
    if not first or not first.startswith("Review target:") or len(stamps) < 2:
        return None
    recipe = RECIPE.search(first)
    seconds = (
        datetime.fromisoformat(stamps[-1].replace("Z", "+00:00"))
        - datetime.fromisoformat(stamps[0].replace("Z", "+00:00"))
    ).total_seconds()
    return {
        "fork": path.stem,
        "target": first.splitlines()[0].removeprefix("Review target:").strip(),
        "recipe": recipe.group(1) if recipe else None,
        "models": sorted(models),
        "seconds": seconds,
        **tokens,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    rows = [r for p in sorted(Path(argv[1]).glob("agent-*.jsonl")) if (r := fork_row(p))]
    for row in rows:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
