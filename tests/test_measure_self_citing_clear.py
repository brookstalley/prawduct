"""Guards for `tools/measure-self-citing-clear.py`.

The script re-derives the `clear-reason` detector's tuning figures from
transcripts. What could make it report a number it does not have: counting a
close that is not `SAFE TO CLEAR`, counting the same close twice (a transcript
repeats a turn across resumes), or reading a user turn as an assistant one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-self-citing-clear.py"


def _turn(kind: str, text: str) -> str:
    return json.dumps({"type": kind, "message": {"content": [{"type": "text", "text": text}]}})


def _close(verdict: str, reason: str) -> str:
    return f"Done.\n\n---\n\n`STATE` — x.\n\n`YOUR TURN` — y.\n\n`{verdict}` — {reason}"


def test_counts_distinct_safe_closes_and_names_self_citations(tmp_path):
    project = tmp_path / ".claude" / "projects" / "-repo"
    project.mkdir(parents=True)
    self_citing = _close("SAFE TO CLEAR", "the questions are in this message.")
    lines = [
        _turn("assistant", self_citing),
        _turn("assistant", self_citing),  # the same turn again, as after a resume
        _turn("assistant", _close("SAFE TO CLEAR", "the findings are in the handoff notes.")),
        _turn("assistant", _close("DO NOT CLEAR", "the questions are in this message.")),
        _turn("user", self_citing),
    ]
    (project / "s.jsonl").write_text("\n".join(lines) + "\n")
    result = subprocess.run(
        [sys.executable, str(_TOOL)],
        capture_output=True, text=True, env={**os.environ, "HOME": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "SAFE TO CLEAR closes: 2; self-citing: 1"
    assert "'are in this message'" in result.stdout
