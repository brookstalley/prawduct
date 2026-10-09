#!/usr/bin/env python3
"""How often a `SAFE TO CLEAR` close gives the message itself as its record.

The `clear-reason` Stop gate (#977) refuses a `SAFE TO CLEAR` whose stated
reason points at the turn ("the questions are in this message"), because a
clear deletes exactly that. Its detector, `standing_block.self_citation`, is a
narrow phrase match tuned on real closes. This re-derives the tuning figures
from Claude Code transcripts on this machine, so they are a command and not a
number copied into prose:

    tools/measure-self-citing-clear.py            # counts, then each hit
    tools/measure-self-citing-clear.py --quiet    # counts only

It counts distinct assistant turns whose closing block reads `SAFE TO CLEAR`
(`standing_block.clear_verdict`), and the ones `self_citation` names. Read each
hit before citing the count: a hit that is a sound reason is a false positive,
and the detector should be narrowed rather than the count reported.

Reads `~/.claude*/projects/*/*.jsonl` with the stdlib and sends nothing anywhere.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from lib import standing_block  # noqa: E402 — path set just above


def _closes(paths):
    """Each distinct assistant text block that closes on SAFE TO CLEAR, with
    the project directory it came from."""
    seen = set()
    for path in paths:
        try:
            lines = Path(path).read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if standing_block.SAFE_TO_CLEAR not in line or '"assistant"' not in line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("type") != "assistant":
                continue
            for part in (record.get("message") or {}).get("content") or []:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = part.get("text") or ""
                if standing_block.clear_verdict(text) != standing_block.SAFE_TO_CLEAR:
                    continue
                key = text[-400:]
                if key in seen:
                    continue
                seen.add(key)
                yield Path(path).parent.name, text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true", help="print the counts only")
    args = parser.parse_args(argv)
    paths = glob.glob(os.path.expanduser("~/.claude*/projects/*/*.jsonl"))
    total, hits = 0, []
    for project, text in _closes(paths):
        total += 1
        phrase = standing_block.self_citation(text)
        if phrase:
            reason = standing_block._paragraphs(standing_block.closing_block(text))[-1]
            hits.append((project, phrase, " ".join(reason.split())[:200]))
    print(f"SAFE TO CLEAR closes: {total}; self-citing: {len(hits)}")
    if not args.quiet:
        for project, phrase, reason in hits:
            print(f"- {project} | {phrase!r} | {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
