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
#: A slash command's echo opens a turn of its own that is not an owner request, so what a
#: skill does is never charged to the typed request before it.
SLASH_ECHO = ("<command-name>", "<command-message>")
#: The digest's opening words (`plugin/methodology/session-digest.md`); a test pins the two together.
DIGEST_MARKER = "This repo is governed by"
#: Sessions run from a temp directory are scripted trials and probes, not an owner at work.
SCRATCH_PREFIXES = ("/private/tmp/", "/tmp/", "/private/var/folders/", "/var/folders/")
KEYS = ("requests", "substantive", "asked_first", "mid_build_asks", "corrections")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text")


def _user_kind(rec: dict) -> str | None:
    """'owner' for a typed request, 'slash' for a slash-command echo, None otherwise."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    content = rec.get("message", {}).get("content")
    if isinstance(content, list) and any(
            isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
        return None
    text = _text(content).strip()
    if text.startswith(SLASH_ECHO):
        return "slash"
    return "owner" if text and not text.startswith(NOT_TYPED) else None


def _is_build(block: dict) -> bool:
    name = block.get("name")
    if name in BUILD_TOOLS:
        return True
    return name == "Bash" and bool(BASH_WRITE.search(block.get("input", {}).get("command", "")))


def read_session(path: Path, health: collections.Counter | None = None) -> tuple[list[dict], bool]:
    """One dict per turn (the request and what the agent did before the next one), and
    whether the session received the prawduct digest. Turns opened by a slash command
    carry ``owner: False``. Lines that do not parse are counted in ``health``, because a
    transcript format change shows up as falling counts and nothing else would say so."""
    health = health if health is not None else collections.Counter()
    out: list[dict] = []
    cur: dict | None = None
    digest = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                health["lines_unparsed"] += 1
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            kind = _user_kind(rec)
            if kind:
                cur = {"owner": kind == "owner", "req": _text(rec["message"]["content"]).strip(),
                       "ts": (rec.get("timestamp") or "")[:10], "cwd": rec.get("cwd", ""),
                       "built": False, "asked_first": False, "mid_build_asks": 0}
                out.append(cur)
            elif rec.get("type") == "assistant":
                for block in rec.get("message", {}).get("content", []) or []:
                    if cur is None or not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") == "AskUserQuestion":
                        if cur["built"]:
                            cur["mid_build_asks"] += 1
                        else:
                            cur["asked_first"] = True
                    if _is_build(block):
                        cur["built"] = True
            elif not digest and rec.get("type") != "user" and DIGEST_MARKER in line:
                # Hook output, not a conversation turn: an owner or agent quoting the digest
                # does not make a session governed.
                digest = True
    if not any(t["owner"] for t in out):
        health["transcripts_without_owner_turns"] += 1
    return out, digest


def measure(paths, since: str | None, until: str | None, min_chars: int,
            skip_prefixes: tuple[str, ...] = SCRATCH_PREFIXES,
            health: collections.Counter | None = None) -> dict:
    health = health if health is not None else collections.Counter()
    by = collections.defaultdict(collections.Counter)
    for path in paths:
        try:
            session, digest = read_session(Path(path), health)
        except OSError:
            health["transcripts_unreadable"] += 1
            continue
        project = Path(path).parent.name
        for i, t in enumerate(session):
            if not t["owner"]:
                continue
            if (since or until) and not t["ts"]:
                health["turns_without_timestamp"] += 1
                continue
            if (since and t["ts"] < since) or (until and t["ts"] >= until):
                continue
            if t["cwd"].startswith(skip_prefixes):
                continue
            governed = digest or (bool(t["cwd"]) and os.path.isdir(os.path.join(t["cwd"], ".prawduct")))
            row = by[(project, governed)]
            for k in KEYS:
                row[k] += 0
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
    health = collections.Counter()
    by = measure(paths, args.since, args.until, args.min_chars, health=health)
    total = {True: collections.Counter({k: 0 for k in KEYS}),
             False: collections.Counter({k: 0 for k in KEYS})}
    for (_, governed), row in by.items():
        total[governed].update(row)

    if args.json:
        json.dump({"window": {"since": args.since, "until": args.until},
                   "transcripts": len(paths),
                   "projects": [{"project": p, "governed": g, **row}
                                for (p, g), row in sorted(by.items())],
                   "total": {"governed": total[True], "ungoverned": total[False]},
                   "health": dict(health)},
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
    if health:
        print("health: " + ", ".join(f"{k} {v}" for k, v in sorted(health.items()))
              + " — a jump between runs is a transcript format change before it is a result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
