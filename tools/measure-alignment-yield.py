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
    tools/measure-alignment-yield.py --until 2026-10-09 --save-baseline   # first read of a baseline
    tools/measure-alignment-yield.py --json

Per project and in total, over owner requests in the window:

- ``requests``: owner turns — typed text, not tool results, slash-command
  echoes, hook output, interrupted-request markers or compaction summaries
  (Claude Code writes those as user records flagged ``isCompactSummary``).
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
- ``goal_questions``: owner turns asking what the product or the work is trying to achieve
  ("what are we really trying to achieve", "how does this meet our goals", "who is this
  for"). The goal-grounding change (`goal-grounding-discovery.md`) exists so the agent asks
  these first, so this should fall once governed products run it: compare a window ending
  when prawduct-live first carried the change with one starting after, like with like. A LEAD, read by hand like ``corrections``.

"Governed" means the session received the prawduct session digest, or its working
directory carries `.prawduct/` today. The digest is the evidence that survives a
deleted worktree or a cloud container. Sessions run from a temp directory are
scripted trials, not an owner, and are skipped.

Health (``health:``) is tallied over the transcripts the window selects, so two windows'
health can be compared. A transcript belongs to the window its first timestamped record falls
in; one with no timestamp at all, or unreadable, is tallied into every window (and named), since
a transcript format change is what health exists to show.

Claude Code prunes transcripts after 30 days, so a baseline cannot be re-read. The first time a
baseline window is read, pass ``--save-baseline``: its per-window counts (totals only: no text,
paths or project names) go to a committed file, once, never overwritten. A later run of the same
window reports its live counts against the saved ones and says when transcripts have been pruned.
The saved counts are then the baseline to cite.

The 2026-10-08 audit's "asked first on 24 of 138" came from a hand-selected
subset of build turns, so this script does not reproduce it; its own figures
over the window before 2026-10-09 are the baseline a later run compares
against, like with like.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BUILD_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BASH_WRITE = re.compile(r"(cat\s*>|sed -i|>>?\s*\S+\.(py|ts|tsx|js|md|yaml|yml|json|toml))")
CORRECTION = re.compile(
    r"\b(wrong|not what i|that's not|thats not|why did you|undo|revert|"
    r"should have asked|didn't ask|did not ask|not right)\b",
    re.IGNORECASE,
)
GOAL_QUESTION = re.compile(
    r"(what (are )?(we|we're|we’re|this|it)\b[^.?!\n]{0,40}?(trying to|here to) (achieve|do|accomplish|build)"
    r"|how does (this|that|it)( \w+)? (meet|serve|fit|support|advance) (our |the )?(product )?goals?"
    r"|who is (this|it) (really )?for\b"
    r"|what(?:'s|\u2019s| is) the (real )?(goal|point|purpose) (here|of (this|the product)))",
    re.IGNORECASE,
)
NOT_TYPED = ("<local-command", "<command-name>", "<task-notification", "Caveat:",
             "[Request interrupted", "<system-reminder>")
DEFAULT_GLOB = "~/.claude*/projects/*/*.jsonl"
DEFAULT_MIN_CHARS = 60
#: Where a baseline window's counts are saved, beside the repo's other committed measurements.
DEFAULT_BASELINES = (Path(__file__).resolve().parent.parent
                     / ".prawduct" / "research" / "alignment-yield" / "baselines.json")
#: A slash command's echo opens a turn of its own that is not an owner request, so what a
#: skill does is never charged to the typed request before it.
SLASH_ECHO = ("<command-name>", "<command-message>")
#: The digest's opening words (`plugin/methodology/session-digest.md`); a test pins the two together.
DIGEST_MARKER = "This repo is governed by"
#: Sessions run from a temp directory are scripted trials and probes, not an owner at work.
SCRATCH_PREFIXES = ("/private/tmp/", "/tmp/", "/private/var/folders/", "/var/folders/")
KEYS = ("requests", "substantive", "asked_first", "mid_build_asks", "corrections",
        "goal_questions")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text")


def _user_kind(rec: dict) -> str | None:
    """'owner' for a typed request, 'slash' for a slash-command echo, None otherwise."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    if rec.get("isCompactSummary"):
        # Claude Code's compaction summary is a user record the owner never typed. It opens no
        # turn: what the agent does after it continues the request it summarises.
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


def read_session(path: Path, health: collections.Counter | None = None
                 ) -> tuple[list[dict], bool, str]:
    """One dict per turn (the request and what the agent did before the next one), whether
    the session received the prawduct digest, and the day (YYYY-MM-DD) of its first timestamped
    record, "" when none has one. Turns opened by a slash command
    carry ``owner: False``. Lines that do not parse are counted in ``health``, because a
    transcript format change shows up as falling counts and nothing else would say so."""
    health = health if health is not None else collections.Counter()
    out: list[dict] = []
    cur: dict | None = None
    digest = False
    first_ts = ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                health["lines_unparsed"] += 1
                continue
            if not isinstance(rec, dict):
                continue
            if not first_ts and isinstance(rec.get("timestamp"), str):
                first_ts = rec["timestamp"][:10]
            if rec.get("isSidechain"):
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
    return out, digest, first_ts


def _in_window(day: str, since: str | None, until: str | None) -> bool:
    return not ((since and day < since) or (until and day >= until))


def measure(paths, since: str | None, until: str | None, min_chars: int,
            skip_prefixes: tuple[str, ...] = SCRATCH_PREFIXES,
            health: collections.Counter | None = None,
            selected: list | None = None) -> dict:
    """Counts per (project, governed) over the owner turns in the window. Turns are windowed one
    by one, so a session spanning a boundary counts its turns on each side. ``health`` and
    ``selected`` (the transcripts the window selects, appended) are windowed by transcript: those
    whose first timestamped record falls in the window. A transcript with no timestamp cannot be
    placed, so it is tallied into every window and named in ``health``, as is an unreadable one."""
    health = health if health is not None else collections.Counter()
    by = collections.defaultdict(collections.Counter)
    windowed = bool(since or until)
    for path in paths:
        local = collections.Counter()
        try:
            session, digest, first_ts = read_session(Path(path), local)
        except OSError:
            health["transcripts_unreadable"] += 1
            continue
        if windowed and not first_ts:
            local["transcripts_without_timestamp"] += 1
        placed = not (windowed and first_ts) or _in_window(first_ts, since, until)
        if placed and selected is not None and (first_ts or not windowed):
            selected.append(path)
        project = Path(path).parent.name
        for i, t in enumerate(session):
            if not t["owner"]:
                continue
            if windowed and not t["ts"]:
                local["turns_without_timestamp"] += 1
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
            if GOAL_QUESTION.search(t["req"]):
                row["goal_questions"] += 1
        if placed:
            health.update(local)
    return by


class BaselineError(ValueError):
    """The baseline file exists but is not one this tool wrote or understands."""


def window_key(since: str | None, until: str | None) -> str:
    return f"{since or ''}..{until or ''}"


def load_baselines(path: Path) -> dict:
    """The saved baselines, or an empty store when the file is absent. A file that is present and
    unreadable is an error, never an empty store, so a save cannot replace it."""
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except FileNotFoundError:
        return {"schema": 1, "windows": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"{path}: {exc}") from exc
    if not (isinstance(store, dict) and store.get("schema") == 1
            and isinstance(store.get("windows"), dict)):
        raise BaselineError(f"{path}: not a schema-1 baselines file")
    return store


def _tool_basis() -> str:
    """The git blob id of this script as it is now, what `git rev-parse HEAD:<path>` prints
    once committed, so a saved reading names the instrument that produced it."""
    data = Path(__file__).read_bytes()
    return "blob:" + hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _save_baseline(path: Path, store: dict, key: str, entry: dict) -> bool:
    """Write ``entry`` under ``key`` unless that window is already saved; True when written."""
    if key in store["windows"]:
        return False
    store["windows"][key] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".prawduct.tmp")  # core.TEMP_SUFFIX: ignored under .prawduct/
    tmp.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True


def _saved_blob(basis) -> str | None:
    """The script's git blob id a saved ``tool_basis`` names, or None when it cannot be told:
    ``blob:<id>`` is its own answer; ``commit:<sha>`` is looked up in this repo's history."""
    if not isinstance(basis, str):
        return None
    if basis.startswith("blob:"):
        return basis[5:] or None
    if basis.startswith("commit:") and len(basis) > 7:
        rel = Path(__file__).resolve().relative_to(Path(__file__).resolve().parent.parent)
        try:
            out = subprocess.run(["git", "rev-parse", f"{basis[7:]}:{rel.as_posix()}"],
                                 cwd=Path(__file__).resolve().parent, capture_output=True,
                                 text=True, timeout=10, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        return out or None
    return None


def _instrument(saved_basis) -> str:
    """'same', 'different' or 'unknown': whether the saved reading came from this script as it is
    now. The current basis hashes the file's bytes, so a dirty tree or a copy outside git is
    'different' from any commit it does not match; 'unknown' is only a saved basis that names no
    resolvable script version."""
    blob = _saved_blob(saved_basis)
    if blob is None:
        return "unknown"
    return "same" if "blob:" + blob == _tool_basis() else "different"


def _against_saved(entry: dict, total: dict, min_chars: int) -> dict:
    """The saved reading beside the live one. A live count below its saved one has two possible
    causes: transcripts were pruned, or the instrument changed (a counting fix lowers counts too).
    Only when the saved reading came from this same script is a shortfall attributed to pruning."""
    out = {"read": entry.get("read"), "source": entry.get("source"),
           "tool_basis": entry.get("tool_basis"), "counts": entry.get("counts"),
           "note": entry.get("note")}
    if entry.get("min_chars") != min_chars:
        out["comparable"] = False
        return out
    out["comparable"] = True
    vs: dict = {}
    for side, saved in (entry.get("counts") or {}).items():
        if saved is None:
            continue
        live = total[side == "governed"]
        vs[side] = {k: {"saved": v, "live": live[k]} for k, v in saved.items() if v is not None}
    out["vs_live"] = vs
    out["instrument"] = _instrument(entry.get("tool_basis"))
    short = any(c["live"] < c["saved"] for side in vs.values() for c in side.values())
    out["short"] = short
    out["pruned"] = short and out["instrument"] == "same"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", help="first day included, YYYY-MM-DD")
    ap.add_argument("--until", help="first day excluded, YYYY-MM-DD")
    ap.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS,
                    help=f"shortest request counted as substantive (default {DEFAULT_MIN_CHARS})")
    ap.add_argument("--glob", default=DEFAULT_GLOB, help=f"transcripts (default {DEFAULT_GLOB})")
    ap.add_argument("--baseline-file", default=str(DEFAULT_BASELINES),
                    help="saved baseline counts (default: the committed file; '' to ignore it)")
    ap.add_argument("--save-baseline", action="store_true",
                    help="save this window's counts to the baseline file, unless already saved")
    ap.add_argument("--read-date", help="date recorded as the baseline's read date (default today)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    baseline_path = Path(args.baseline_file) if args.baseline_file else None
    if args.save_baseline and baseline_path is None:
        print("--save-baseline needs a --baseline-file", file=sys.stderr)
        return 2
    read_date = (args.read_date or datetime.date.today().isoformat()) if args.save_baseline else None
    if args.save_baseline and not (args.until and args.until <= read_date):
        print("--save-baseline needs a closed window: --until set and not after the read date "
              f"({read_date}); an open window's counts would still grow and a save is never "
              "replaced", file=sys.stderr)
        return 2
    store = None
    if baseline_path is not None:
        try:
            store = load_baselines(baseline_path)
        except BaselineError as exc:
            print(f"baseline file unusable, nothing written: {exc}", file=sys.stderr)
            return 2

    paths = sorted(glob.glob(os.path.expanduser(args.glob)))
    health = collections.Counter()
    selected: list = []
    by = measure(paths, args.since, args.until, args.min_chars, health=health, selected=selected)
    total = {True: collections.Counter({k: 0 for k in KEYS}),
             False: collections.Counter({k: 0 for k in KEYS})}
    for (_, governed), row in by.items():
        total[governed].update(row)

    key = window_key(args.since, args.until)
    saved_now = False
    if args.save_baseline and not selected and key not in store["windows"]:
        print("--save-baseline: no transcript falls in the window (check --glob and the dates), "
              "nothing written", file=sys.stderr)
        return 2
    if args.save_baseline:
        entry = {"window": {"since": args.since, "until": args.until},
                 "read": read_date, "source": "measured",
                 "tool_basis": _tool_basis(), "min_chars": args.min_chars,
                 "counts": {"governed": {k: total[True][k] for k in KEYS},
                            "ungoverned": {k: total[False][k] for k in KEYS}},
                 "health": dict(health)}
        saved_now = _save_baseline(baseline_path, store, key, entry)
    saved = (_against_saved(store["windows"][key], total, args.min_chars)
             if store and key in store["windows"] else None)

    if args.json:
        doc = {"window": {"since": args.since, "until": args.until},
               "transcripts": len(selected), "transcripts_on_disk": len(paths),
               "projects": [{"project": p, "governed": g, **row}
                            for (p, g), row in sorted(by.items())],
               "total": {"governed": total[True], "ungoverned": total[False]},
               "health": dict(health)}
        if args.save_baseline:
            doc["baseline_saved"] = saved_now
        if saved is not None:
            doc["saved_baseline"] = saved
        json.dump(doc, sys.stdout, indent=2)
        print()
        return 0

    print(f"{len(selected)} transcripts in the window ({len(paths)} on disk), "
          f"window {args.since or '…'} to {args.until or '…'}")
    print(f"{'project':48} gov  requests substantive asked_first mid_build_asks corrections* "
          f"goal_questions*")
    for (p, g), row in sorted(by.items()):
        print(f"{p[-48:]:48} {'yes' if g else 'no ':4} {row['requests']:8} {row['substantive']:11} "
              f"{row['asked_first']:11} {row['mid_build_asks']:14} {row['corrections']:12} "
              f"{row['goal_questions']:15}")
    for g in (True, False):
        row = total[g]
        print(f"{'TOTAL ' + ('governed' if g else 'ungoverned'):48} {'':4} {row['requests']:8} "
              f"{row['substantive']:11} {row['asked_first']:11} {row['mid_build_asks']:14} "
              f"{row['corrections']:12} {row['goal_questions']:15}")
    print("* corrections and goal_questions are leads: read each before citing the count.")
    if args.save_baseline:
        print("baseline " + ("saved" if saved_now else "already saved, kept")
              + f" for {key} in {baseline_path}")
    if saved is not None:
        print(f"saved baseline {key} (read {saved['read']}, {saved['source']}):")
        if not saved["comparable"]:
            print("  not comparable: it was read with a different --min-chars")
        for side, counts in saved.get("vs_live", {}).items():
            print(f"  {side}: " + ", ".join(f"{k} {c['saved']} (live {c['live']})"
                                            for k, c in counts.items()))
        if saved.get("pruned"):
            print("  live counts fall short of the saved ones, read by this same script: "
                  "transcripts were pruned, so cite the saved counts for this window.")
        elif saved.get("short"):
            if saved["instrument"] == "different":
                print("  live counts fall short of the saved ones, but the saved reading came "
                      "from a different version of this script: the shortfall may be pruning, "
                      "the counting change, or both. Do not read it as pruning.")
            else:
                print("  live counts fall short of the saved ones, and the saved reading's "
                      "script version cannot be resolved here: the shortfall may be pruning or "
                      "a counting change.")
    if health:
        print("health: " + ", ".join(f"{k} {v}" for k, v in sorted(health.items()))
              + " — a jump between runs is a transcript format change before it is a result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
