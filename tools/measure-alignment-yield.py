#!/usr/bin/env python3
"""The alignment pass's yield, from Claude Code transcripts.

The alignment pass (`plugin/methodology/building.md` "Before You Build") is a
control, and the NFR Direction norm says every new control emits observable
yield. Its yield is the owner's own two measures, taken from transcripts rather
than a ledger (`requirements-alignment-discovery.md` § Proposed Design):
questions that interrupted a build, and owner corrections after one. This
reports both, plus the rate the pass exists to raise — asking before building.

    tools/measure-alignment-yield.py --until 2026-10-09        # the baseline window
    tools/measure-alignment-yield.py --since 2026-10-09        # since the pass shipped
    tools/measure-alignment-yield.py --json

Per project and in total, over owner requests in the window:

- ``requests``: owner turns — typed text, not tool results, slash-command
  echoes, hook output or interrupted-request markers.
- ``substantive``: requests that led to a build in the same turn and are at
  least ``--min-chars`` long, so "yes, do it" continuations don't count. A build
  is an Edit/Write/MultiEdit/NotebookEdit, or a Bash command that writes a file.
- ``asked_first``: substantive requests where AskUserQuestion came before the
  first build — the rate the pass should raise.
- ``mid_build_asks``: AskUserQuestion calls after a turn's first build — the
  interruptions the pass should remove.
- ``corrections``: owner turns right after a building turn that read like a
  correction ("wrong", "not what I", "revert"…). A LEAD, not a verdict: the
  2026-10-08 audit read each one by hand, and so should anyone citing the count.

"Governed" means the session received the prawduct session digest, or its working
directory carries `.prawduct/` today. The digest is the evidence that survives a
deleted worktree or a cloud container. Sessions run from a temp directory are
scripted trials, not an owner, and are skipped.

The 2026-10-08 audit's "asked first on 24 of 138" came from a hand-selected
subset of build turns, so this script does not reproduce it; its own figures
over the window before 2026-10-09 are the baseline a later run compares
against, like with like.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

BUILD_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BASH_WRITE = re.compile(r"(cat\s*>|sed -i|>>?\s*\S+\.(py|ts|tsx|js|md|yaml|yml|json|toml))")
CORRECTION = re.compile(
    r"\b(wrong|not what i|that's not|thats not|why did you|undo|revert|"
    r"should have asked|didn't ask|did not ask|not right)\b",
    re.IGNORECASE,
)
NOT_TYPED = ("<local-command", "<command-name>", "<task-notification", "Caveat:",
             "[Request interrupted", "<system-reminder>")
DEFAULT_GLOB = "~/.claude*/projects/*/*.jsonl"
#: Sessions run from a temp directory are scripted trials and probes, not an owner at work.
#: The digest's opening words (`plugin/methodology/session-digest.md`); a test pins the two together.
DIGEST_MARKER = "This repo is governed by"
SCRATCH_PREFIXES = ("/private/tmp/", "/tmp/", "/private/var/folders/", "/var/folders/")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text")


def _is_owner_turn(rec: dict) -> bool:
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return False
    content = rec.get("message", {}).get("content")
    if isinstance(content, list) and any(
            isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
        return False
    text = _text(content).strip()
    return bool(text) and not text.startswith(NOT_TYPED)


def _is_build(block: dict) -> bool:
    name = block.get("name")
    if name in BUILD_TOOLS:
        return True
    return name == "Bash" and bool(BASH_WRITE.search(block.get("input", {}).get("command", "")))


def read_session(path: Path) -> tuple[list[dict], bool]:
    """One dict per owner turn (the request and what the agent did before the next one),
    and whether the session received the prawduct digest."""
    out: list[dict] = []
    cur: dict | None = None
    digest = False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if not digest and DIGEST_MARKER in line:
                digest = True
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("isSidechain"):
                continue
            if _is_owner_turn(rec):
                cur = {"req": _text(rec["message"]["content"]).strip(),
                       "ts": rec.get("timestamp", "")[:10], "cwd": rec.get("cwd", ""),
                       "built": False, "asked_first": False, "mid_build_asks": 0}
                out.append(cur)
            elif cur is not None and rec.get("type") == "assistant":
                for block in rec.get("message", {}).get("content", []) or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") == "AskUserQuestion":
                        if cur["built"]:
                            cur["mid_build_asks"] += 1
                        else:
                            cur["asked_first"] = True
                    if _is_build(block):
                        cur["built"] = True
    return out, digest


def measure(paths, since: str | None, until: str | None, min_chars: int,
            skip_prefixes: tuple[str, ...] = SCRATCH_PREFIXES) -> dict:
    by = collections.defaultdict(collections.Counter)
    for path in paths:
        session, digest = read_session(Path(path))
        project = Path(path).parent.name
        for i, t in enumerate(session):
            if (since and t["ts"] < since) or (until and t["ts"] >= until):
                continue
            if t["cwd"].startswith(skip_prefixes):
                continue
            governed = digest or (bool(t["cwd"]) and os.path.isdir(os.path.join(t["cwd"], ".prawduct")))
            row = by[(project, governed)]
            row["requests"] += 1
            row["mid_build_asks"] += t["mid_build_asks"]
            if t["built"] and len(t["req"]) >= min_chars:
                row["substantive"] += 1
                row["asked_first"] += t["asked_first"]
            if i and session[i - 1]["built"] and CORRECTION.search(t["req"]):
                row["corrections"] += 1
    return by


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", help="first day included, YYYY-MM-DD")
    ap.add_argument("--until", help="first day excluded, YYYY-MM-DD")
    ap.add_argument("--min-chars", type=int, default=60,
                    help="shortest request counted as substantive (default 60)")
    ap.add_argument("--glob", default=DEFAULT_GLOB, help=f"transcripts (default {DEFAULT_GLOB})")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    paths = sorted(glob.glob(os.path.expanduser(args.glob)))
    by = measure(paths, args.since, args.until, args.min_chars)
    total = {True: collections.Counter(), False: collections.Counter()}
    for (_, governed), row in by.items():
        total[governed].update(row)

    if args.json:
        json.dump({"window": {"since": args.since, "until": args.until},
                   "transcripts": len(paths),
                   "projects": [{"project": p, "governed": g, **row}
                                for (p, g), row in sorted(by.items())],
                   "total": {"governed": total[True], "ungoverned": total[False]}},
                  sys.stdout, indent=2)
        print()
        return 0

    print(f"{len(paths)} transcripts, window {args.since or '…'} to {args.until or '…'}")
    print(f"{'project':48} gov  requests substantive asked_first mid_build_asks corrections*")
    for (p, g), row in sorted(by.items()):
        print(f"{p[-48:]:48} {'yes' if g else 'no ':4} {row['requests']:8} {row['substantive']:11} "
              f"{row['asked_first']:11} {row['mid_build_asks']:14} {row['corrections']:12}")
    for g in (True, False):
        row = total[g]
        print(f"{'TOTAL ' + ('governed' if g else 'ungoverned'):48} {'':4} {row['requests']:8} "
              f"{row['substantive']:11} {row['asked_first']:11} {row['mid_build_asks']:14} "
              f"{row['corrections']:12}")
    print("* corrections are leads: read each before citing the count.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
