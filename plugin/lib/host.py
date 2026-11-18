"""The host seam: the one place prawduct reads what its host harness hands a
hook, and writes what the host reads back.

Prawduct's governance engine is host-neutral; the harness that runs it is not.
Each host passes a hook its own payload, exports its own root variables, and
reads its own response shapes. Everything that depends on those three lives
here, so a second host (#928) is a second implementation of this module rather
than a patch at every call site:

- **Payloads.** :func:`read_event` turns the parsed hook stdin into a
  :class:`HostEvent`. It is the only reader of host payload keys.
- **Roots.** :func:`plugin_root`, :func:`project_dir_hint`, :func:`config_home`
  and :func:`config_roots` are the only readers of the host's environment.
- **The session's record.** :func:`other_session_wrote_since` and
  :func:`session_tool_activity` read the host's transcript of the session
  (the ``transcript_path`` a Stop payload names): whether a second session
  wrote beside it, when this one had a tool call or ``!`` command running,
  and which files its edit tools targeted. The second keeps what it parsed in
  a cache file the caller names, so each read parses only appended bytes.
- **Responses.** :func:`emit_session_context`, :func:`emit_stop_advisory` and
  :func:`block` are the only writers of structured hook responses and of the
  Stop hook's blocking exit.

Not yet here: plain text the entry points print in place. That is the
``clear --session-start`` briefing and the banner on stdout, and the notes
``cmd_stop`` writes to stderr ahead of its block (the worktree redirect,
waivers, deferrals, the Critic-mode and learnings notes). Claude Code reads
both channels — SessionStart stdout is context, and a blocking Stop's whole
stderr is its reason — so for Claude they are response text too. A host that
reads them differently moves them into this module (#1038).

``PRAWDUCT_HOST`` names the host, ``claude`` when unset. A host adapter's hook
registration sets it explicitly rather than prawduct detecting the host from
its environment, because hosts export each other's variables for compatibility
(Codex exports ``CLAUDE_PLUGIN_ROOT``), so detection would guess wrong. An
unknown name fails closed: each hook entry point asks
:func:`unknown_host_reason` and refuses to run. Claude is the only host
implemented, so the readers and writers below are Claude's.

This module imports nothing from ``lib``. The hook entry points load it by file
path before ``lib`` is importable, because it is what tells them where ``lib``
is.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: The variable a host adapter sets to name its host.
HOST_VARIABLE = "PRAWDUCT_HOST"
DEFAULT_HOST = "claude"
KNOWN_HOSTS = frozenset({DEFAULT_HOST})

#: The hook events prawduct handles, in host-neutral names.
EVENTS = frozenset({"session_start", "stop", "subagent_stop"})

#: The Stop hook's blocking exit. The reason goes on stderr.
BLOCK_EXIT = 2

# Claude's names for what a hook reads.
_PLUGIN_ROOT_VAR = "CLAUDE_PLUGIN_ROOT"
_PROJECT_DIR_VAR = "CLAUDE_PROJECT_DIR"
_CONFIG_DIR_VAR = "CLAUDE_CONFIG_DIR"
_MESSAGE_KEY = "last_assistant_message"
_TASKS_KEY = "background_tasks"
_CWD_KEY = "cwd"
_AGENT_TYPE_KEY = "agent_type"
_TRANSCRIPT_KEY = "transcript_path"

#: Longest background-task label kept; a description or command can be long.
_TASK_LABEL_CHARS = 80


# --- host selection ----------------------------------------------------------


def host_name() -> str:
    """The host this process runs under: ``PRAWDUCT_HOST``, or ``claude``.
    Case is not significant: ``Claude`` names the same host, and a value that
    blocks every Stop should not turn on capitalisation."""
    return os.environ.get(HOST_VARIABLE, "").strip().lower() or DEFAULT_HOST


def unknown_host_reason() -> str | None:
    """Why this process must not run its hook, or ``None`` when the host is known.

    The reason names the variable and its value, because the fix is in the
    adapter's hook registration, not in the repo being governed.
    """
    name = host_name()
    if name in KNOWN_HOSTS:
        return None
    known = ", ".join(sorted(KNOWN_HOSTS))
    return (
        f"{HOST_VARIABLE}={name!r} names a host this prawduct plugin does not "
        f"implement (known: {known}), so its hooks cannot read this host's "
        f"payloads or answer in its format. Fix the {HOST_VARIABLE} value in the "
        "host adapter's hook registration, or unset it to run as Claude Code."
    )


# --- payloads ----------------------------------------------------------------


@dataclass(frozen=True)
class HostEvent:
    """One hook invocation's payload, in host-neutral terms.

    ``None`` means the payload did not carry the field, or carried it in a shape
    that says nothing; ``fields_present`` keeps the difference between a field
    that was absent and one that was sent as ``null`` or garbage. No Claude path
    reads it: it is for a host adapter, which has to report which signals its
    host's payload actually carries (#1038's doctor detection), and a gate
    reads an absent and a null message the same way.

    ``background_tasks`` is the in-flight harness tasks as ``<type>:<ident>``
    labels: ``None`` when the payload had no such field, empty when it had one
    with no usable entry.

    ``transcript_path`` is where the host keeps this session's own record of
    what it did, kept exactly as sent; :func:`other_session_wrote_since` and
    :func:`session_tool_activity` are its readers.
    """

    event: str
    last_assistant_message: str | None = None
    background_tasks: tuple[str, ...] | None = None
    cwd: str | None = None
    agent_type: str | None = None
    transcript_path: str | None = None
    fields_present: frozenset[str] = field(default_factory=frozenset)


def read_event(event: str, raw: object) -> HostEvent:
    """Normalize a parsed hook payload into a :class:`HostEvent`.

    ``raw`` is what the hook read from stdin, already parsed; anything but a
    dict reads as an empty payload, so a hook run by hand or fed garbage gets
    each gate's no-signal behaviour. Never raises on payload content. An
    ``event`` outside :data:`EVENTS` is a caller bug and raises ``ValueError``.
    """
    if event not in EVENTS:
        raise ValueError(f"unknown hook event {event!r}; expected one of {sorted(EVENTS)}")
    payload = raw if isinstance(raw, dict) else {}
    message = payload.get(_MESSAGE_KEY)
    return HostEvent(
        event=event,
        last_assistant_message=message if isinstance(message, str) else None,
        background_tasks=_task_labels(payload) if _TASKS_KEY in payload else None,
        cwd=_path_text(payload.get(_CWD_KEY)),
        agent_type=_text(payload.get(_AGENT_TYPE_KEY)),
        transcript_path=_path_text(payload.get(_TRANSCRIPT_KEY)),
        fields_present=frozenset(k for k in payload if isinstance(k, str)),
    )


def _text(value: object) -> str | None:
    """A non-blank string, stripped; anything else is ``None``."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _path_text(value: object) -> str | None:
    """A non-blank string kept exactly as sent — a path may carry spaces at
    its ends; anything else is ``None``."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _task_labels(payload: dict) -> tuple[str, ...]:
    """Label each usable entry of Claude Code's ``background_tasks`` array
    (v2.1.145+) as ``<type>:<ident>``, preferring the most human-meaningful
    identifier the entry carries. A non-list, or a list with no dict entries,
    labels nothing."""
    tasks = payload.get(_TASKS_KEY)
    if not isinstance(tasks, list):
        return ()
    labels: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        ttype = _text(task.get("type")) or "task"
        ident = None
        for key in ("name", _AGENT_TYPE_KEY, "description", "command", "id"):
            ident = _text(task.get(key))
            if ident:
                break
        labels.append((f"{ttype}:{ident}" if ident else ttype)[:_TASK_LABEL_CHARS])
    return tuple(labels)


# --- the session's own record ------------------------------------------------

#: Seconds either side of a moment still read as the same moment. git stamps a
#: commit or a HEAD move in whole seconds, the host stamps a tool call when it
#: records the request rather than when the command runs, and a transcript
#: written within this of the session's start belongs to the boundary itself
#: (the previous session's last lines at a ``/clear``), not to a second session.
ACTIVITY_SLACK_SECONDS = 2


#: The tools whose call names the file it changes, and the input key naming it.
#: Read off this machine's transcripts (2026-11-15): Edit and Write carry an
#: absolute ``file_path``; MultiEdit and NotebookEdit are Claude Code's other
#: file editors, with the key its tool schema gives them.
EDIT_TOOLS = {
    "Edit": "file_path",
    "Write": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}

#: How Claude Code records a ``!`` (bash mode) command, which is not a tool
#: call: a user message whose content opens with the input tag, stamped when it
#: was entered, then one opening with an output tag, stamped when it ended.
_BANG_INPUT = "<bash-input>"
_BANG_OUTPUTS = ("<bash-stdout>", "<bash-stderr>")

#: Bytes just before the cached offset re-read to confirm the transcript still
#: holds what was parsed. A replaced file is caught by its inode, a truncated one
#: by its size; this catches one truncated and written again, or rewritten in
#: place up to where it was read. The host only appends to a transcript, so a
#: change further back than this is not checked for.
PREFIX_CHECK_BYTES = 256

#: Transcripts the activity cache keeps, least recently read evicted first. A
#: checkout sees one transcript per session (and per ``/clear``), and two or
#: three sessions at once; the oldest entries are finished sessions.
ACTIVITY_CACHE_TRANSCRIPTS = 8

_CACHE_SCHEMA = 1


@dataclass(frozen=True)
class ToolActivity:
    """When a session was acting, and what it edited, from its own transcript.

    ``covered_from`` is the transcript's first timestamped record: it says
    nothing about any moment before it. ``windows`` holds one ``(start, end)``
    pair of epoch seconds per tool call and per ``!`` command; ``end`` is
    ``math.inf`` for one that can still be acting, which is a background call,
    or a call or command with no result recorded yet. ``edited_paths`` is every
    path an :data:`EDIT_TOOLS` call named, exactly as the call named it.
    """

    covered_from: float
    windows: tuple[tuple[float, float], ...]
    edited_paths: frozenset[str] = frozenset()

    def acting_at(self, when: float) -> bool | None:
        """``True`` when a tool call or ``!`` command was running at ``when``,
        ``False`` when none was, and ``None`` when the transcript does not
        cover ``when``."""
        slack = ACTIVITY_SLACK_SECONDS
        if when < self.covered_from - slack:
            return None
        return any(start - slack <= when <= end + slack for start, end in self.windows)


def other_session_wrote_since(transcript_path: str, since: float) -> bool | None:
    """Whether another session's transcript in this session's transcript
    folder was written after ``since`` (epoch seconds).

    Claude Code keeps one folder of top-level ``*.jsonl`` transcripts per
    launch directory, so a sibling written since this session started is a
    second session working in the same checkout. Only modification times are
    read. A subagent's transcript sits in a subfolder and is not a sibling.
    ``None`` when this session's own transcript is not there or the folder
    cannot be listed: that is no evidence either way.
    """
    own = Path(transcript_path)
    try:
        if not own.is_file():
            return None
        with os.scandir(own.parent) as entries:
            for entry in entries:
                if entry.name == own.name or not entry.name.endswith(".jsonl"):
                    continue
                if not entry.is_file():
                    continue
                if entry.stat().st_mtime > since + ACTIVITY_SLACK_SECONDS:
                    return True
    except OSError:
        return None
    return False


class _TranscriptScan:
    """What :func:`session_tool_activity` has read of one transcript so far.

    Fed one line at a time, in file order, so a scan resumed from the cache and
    fed only the appended lines ends where a scan of the whole file would.
    ``broken`` is a line that would not parse, forgiven while it is the last;
    ``dead`` is a line after it, which no later append can undo.
    """

    def __init__(self) -> None:
        self.first: float | None = None
        self.starts: dict[str, float] = {}
        self.ends: dict[str, float] = {}
        self.background: set[str] = set()
        self.bangs: list[list[float | None]] = []
        self.edited: set[str] = set()
        self.broken = False
        self.dead = False

    def feed(self, raw: bytes) -> None:
        line = raw.decode("utf-8", errors="replace")
        if not line.strip() or self.dead:
            return
        if self.broken:
            self.dead = True
            return
        try:
            record = json.loads(line)
        except ValueError:
            self.broken = True
            return
        if not isinstance(record, dict):
            return
        when = _epoch(record.get("timestamp"))
        if when is None:
            return
        self.first = when if self.first is None else min(self.first, when)
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            self._user_text(record, content, when)
            return
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use" and isinstance(block.get("id"), str):
                call = block["id"]
                self.starts[call] = min(self.starts.get(call, when), when)
                args = block.get("input")
                if not isinstance(args, dict):
                    continue
                if args.get("run_in_background"):
                    self.background.add(call)
                key = EDIT_TOOLS.get(block.get("name"))
                target = args.get(key) if key else None
                if isinstance(target, str) and target:
                    self.edited.add(target)
            elif kind == "tool_result" and isinstance(block.get("tool_use_id"), str):
                call = block["tool_use_id"]
                self.ends[call] = max(self.ends.get(call, when), when)
            elif kind == "text" and isinstance(block.get("text"), str):
                self._user_text(record, block["text"], when)

    def _user_text(self, record: dict, text: str, when: float) -> None:
        """A ``!`` command's input opens a window; its output closes the
        latest one still open. Only a user record that opens with the tag is
        one: text that merely mentions it is a prompt."""
        if record.get("type") != "user":
            return
        if text.startswith(_BANG_INPUT):
            self.bangs.append([when, None])
        elif text.startswith(_BANG_OUTPUTS):
            for window in reversed(self.bangs):
                if window[1] is None:
                    window[1] = when
                    break

    def activity(self) -> ToolActivity | None:
        # No call at all, or a result naming a call never seen, is a transcript
        # this reader does not understand (the host's format moved), not a
        # session that never acted: read as idle throughout, it would disown the
        # session's own commits.
        if self.dead or self.first is None or not self.starts:
            return None
        if not self.ends.keys() <= self.starts.keys():
            return None
        windows = tuple(
            (start, math.inf if call in self.background or call not in self.ends
             else self.ends[call])
            for call, start in self.starts.items()
        ) + tuple(
            (start, math.inf if end is None else end) for start, end in self.bangs
        )
        return ToolActivity(
            covered_from=self.first, windows=windows, edited_paths=frozenset(self.edited)
        )

    def copy(self) -> "_TranscriptScan":
        return _TranscriptScan.from_json(self.to_json())

    def to_json(self) -> dict:
        return {
            "first": self.first,
            "starts": self.starts,
            "ends": self.ends,
            "background": sorted(self.background),
            "bangs": [list(b) for b in self.bangs],
            "edited": sorted(self.edited),
            "broken": self.broken,
            "dead": self.dead,
        }

    @classmethod
    def from_json(cls, data: object) -> "_TranscriptScan":
        """Raises ``ValueError`` on anything but :meth:`to_json`'s shape."""
        number = (int, float)
        if not isinstance(data, dict):
            raise ValueError("not a scan")
        scan = cls()
        first = data.get("first")
        if first is not None and (isinstance(first, bool) or not isinstance(first, number)):
            raise ValueError("first")
        scan.first = first
        for name in ("starts", "ends"):
            stamps = data.get(name)
            if not isinstance(stamps, dict) or not all(
                isinstance(v, number) and not isinstance(v, bool) for v in stamps.values()
            ):
                raise ValueError(name)
            setattr(scan, name, dict(stamps))
        for name in ("background", "edited"):
            items = data.get(name)
            if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
                raise ValueError(name)
            setattr(scan, name, set(items))
        bangs = data.get("bangs")
        if not isinstance(bangs, list) or not all(
            isinstance(b, list) and len(b) == 2 and isinstance(b[0], number)
            and (b[1] is None or isinstance(b[1], number))
            for b in bangs
        ):
            raise ValueError("bangs")
        scan.bangs = [list(b) for b in bangs]
        for name in ("broken", "dead"):
            flag = data.get(name)
            if not isinstance(flag, bool):
                raise ValueError(name)
            setattr(scan, name, flag)
        return scan


def session_tool_activity(
    transcript_path: str, cache_path: str | None = None
) -> ToolActivity | None:
    """This session's tool calls, ``!`` commands and edited paths, read from
    its Claude Code transcript.

    A ``tool_use`` block in a timestamped record opens a call and the
    ``tool_result`` naming its id closes it. A call whose input sets
    ``run_in_background`` stays open, since its command outlives the call. A
    ``!`` command's ``<bash-input>`` user message opens a window and its
    ``<bash-stdout>``/``<bash-stderr>`` message closes it. An :data:`EDIT_TOOLS`
    call adds the path it names to ``edited_paths``. ``None`` when the
    transcript cannot be read, holds no timestamped record or no tool call, has
    a result for a call it never opened, or has an unparseable line before its
    last one. Only a final line can be mid-write; a broken one earlier may have
    hidden a call, and a missing call would read as a moment the session was
    idle.

    **Cost bound.** With ``cache_path``, what was parsed is kept there, keyed by
    the transcript's path, device, inode and the byte offset parsed up to, and
    a call reads only the bytes appended since the last one, plus
    :data:`PREFIX_CHECK_BYTES` before that offset to confirm the file still
    holds what was parsed. The whole transcript is read only on the first call,
    or when the entry is missing or unreadable, or the file was replaced,
    truncated or rewritten. The cache file itself grows with the session's
    number of tool calls, ``!`` commands and edited paths (tens of bytes each),
    never with the tool output that makes a transcript large, and holds at
    most :data:`ACTIVITY_CACHE_TRANSCRIPTS` transcripts. Without ``cache_path``
    every call reads the whole transcript. A cache that cannot be read or
    written costs a full read, never a different answer.
    """
    try:
        with open(transcript_path, "rb") as fh:
            stat = os.fstat(fh.fileno())
            scan, offset, recent = _cached_scan(fh, stat, transcript_path, cache_path)
            fh.seek(offset)
            tail = b""
            for raw in fh:
                if not raw.endswith(b"\n"):
                    tail = raw  # the host may be mid-append: parsed, not kept
                    break
                scan.feed(raw)
                offset += len(raw)
                # The next call's prefix check, from bytes already in hand.
                recent = (recent + raw)[-PREFIX_CHECK_BYTES:]
    except (OSError, ValueError):  # ValueError: a path with a NUL in it
        return None
    if cache_path:
        _store_scan(cache_path, transcript_path, stat, offset, _digest(recent), scan)
    if tail:
        scan = scan.copy()
        scan.feed(tail)
    return scan.activity()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_cache(cache_path: str) -> dict:
    """The cache's transcript entries, or empty when there is no usable cache."""
    try:
        with open(cache_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("schema") != _CACHE_SCHEMA:
        return {}
    entries = data.get("transcripts")
    return entries if isinstance(entries, dict) else {}


def _cached_scan(
    fh, stat: os.stat_result, transcript_path: str, cache_path: str | None
) -> tuple[_TranscriptScan, int, bytes]:
    """The scan to resume, the offset to resume from, and the
    :data:`PREFIX_CHECK_BYTES` before it: the cached scan when its entry still
    describes this file, else a fresh scan from byte 0. The prefix is the one
    read of the transcript before the offset."""
    if not cache_path:
        return _TranscriptScan(), 0, b""
    entry = _read_cache(cache_path).get(transcript_path)
    try:
        if not isinstance(entry, dict):
            raise ValueError("no entry")
        offset = entry["offset"]
        if not (
            type(offset) is int
            and 0 <= offset <= stat.st_size
            and entry["dev"] == stat.st_dev
            and entry["inode"] == stat.st_ino
        ):
            raise ValueError("another file")
        scan = _TranscriptScan.from_json(entry["scan"])
        start = max(0, offset - PREFIX_CHECK_BYTES)
        fh.seek(start)
        prefix = fh.read(offset - start)
        if _digest(prefix) != entry["check"]:
            raise ValueError("rewritten")
    except (KeyError, ValueError):
        return _TranscriptScan(), 0, b""
    return scan, offset, prefix


def _store_scan(
    cache_path: str,
    transcript_path: str,
    stat: os.stat_result,
    offset: int,
    check: str,
    scan: _TranscriptScan,
) -> None:
    """Write this transcript's entry, evicting the least recently read past
    :data:`ACTIVITY_CACHE_TRANSCRIPTS`. Best effort: a write that fails costs
    the next call a full read. Two sessions sharing a checkout share the file;
    the write is atomic, and a lost race costs a full read too."""
    entries = _read_cache(cache_path)
    entries[transcript_path] = {
        "dev": stat.st_dev,
        "inode": stat.st_ino,
        "offset": offset,
        "check": check,
        "read_at": time.time(),
        "scan": scan.to_json(),
    }

    def _read_at(item: tuple[str, object]) -> float:
        value = item[1].get("read_at") if isinstance(item[1], dict) else None
        return value if isinstance(value, (int, float)) else 0.0

    kept = dict(sorted(entries.items(), key=_read_at)[-ACTIVITY_CACHE_TRANSCRIPTS:])
    tmp = f"{cache_path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", errors="backslashreplace") as out:
            json.dump({"schema": _CACHE_SCHEMA, "transcripts": kept}, out)
        os.replace(tmp, cache_path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _epoch(value: object) -> float | None:
    """Epoch seconds of an ISO 8601 timestamp, read as UTC when it names no
    zone; ``None`` for anything else."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.timestamp()


# --- roots -------------------------------------------------------------------


def plugin_root() -> str:
    """The plugin's root directory: the host's plugin-root variable, else the
    directory above this file's (``lib/`` -> root), so a hook run directly in
    tests or a ``--plugin-dir`` probe resolves without the variable."""
    return os.environ.get(_PLUGIN_ROOT_VAR) or str(Path(__file__).resolve().parent.parent)


def project_dir_hint() -> str | None:
    """The directory the host launched the session in, or ``None`` when unset.

    A hint, not the answer: ``gitstate.resolve_project_dir`` follows the
    session into a worktree of the same repo, which the host's value does not.
    """
    return os.environ.get(_PROJECT_DIR_VAR) or None


def config_home(env: dict | None = None, home: Path | None = None) -> Path:
    """The host's configuration home: the configured override, else
    ``~/.claude``. Raises what ``Path.home()`` raises when no home resolves;
    callers that must not fail catch it."""
    env = os.environ if env is None else env
    configured = env.get(_CONFIG_DIR_VAR)
    if configured:
        return Path(configured).expanduser()
    return (Path.home() if home is None else home) / ".claude"


def config_roots(env: dict | None = None, home: Path | None = None) -> list[Path]:
    """Every directory that may be a configuration home for this host, most
    specific first: the configured override, ``~/.claude``, then each
    ``~/.claude-*`` (alternate profiles). Candidates only — not filtered by
    existence or de-duplicated, because what each caller needs inside them
    differs. A home that cannot be resolved yields only the override, if any."""
    env = os.environ if env is None else env
    roots: list[Path] = []
    configured = env.get(_CONFIG_DIR_VAR)
    if configured:
        roots.append(Path(configured).expanduser())
    try:
        home = Path.home() if home is None else home
    except (RuntimeError, KeyError, OSError):
        return roots
    roots.append(home / ".claude")
    try:
        roots.extend(sorted(home.glob(".claude-*")))
    except OSError:
        pass
    return roots


# --- responses ---------------------------------------------------------------


def emit_session_context(text: str, *, reload_skills: bool = False) -> None:
    """Put ``text`` in the model's context at session start.

    ``reload_skills`` asks the host to re-scan skill bodies, which it caches per
    session; a host that does not know the key ignores it.
    """
    output: dict = {"hookEventName": "SessionStart", "additionalContext": text}
    if reload_skills:
        output["reloadSkills"] = True
    print(json.dumps({"hookSpecificOutput": output}))


def emit_stop_advisory(text: str) -> None:
    """Show ``text`` to the user at a Stop that does not block.

    It reaches the user only: Claude Code's Stop hook has no channel into the
    model's context that does not also start another turn.
    """
    print(json.dumps({"systemMessage": text}))


def block(reason: str) -> int:
    """Block the Stop with ``reason``, which reaches both the model and the user.

    Writes ``reason`` to stderr exactly as given and returns the exit code the
    caller must return.
    """
    sys.stderr.write(reason)
    return BLOCK_EXIT
