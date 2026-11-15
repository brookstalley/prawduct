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
  wrote beside it, and when this one had a tool call running.
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

import json
import math
import os
import sys
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


@dataclass(frozen=True)
class ToolActivity:
    """When a session was acting, from its own transcript.

    ``covered_from`` is the transcript's first timestamped record: it says
    nothing about any moment before it. ``windows`` holds one ``(start, end)``
    pair of epoch seconds per tool call; ``end`` is ``math.inf`` for a call that
    can still be acting, which is a background call or one with no result
    recorded yet.
    """

    covered_from: float
    windows: tuple[tuple[float, float], ...]

    def acting_at(self, when: float) -> bool | None:
        """``True`` when a tool call was running at ``when``, ``False`` when
        none was, and ``None`` when the transcript does not cover ``when``."""
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


def session_tool_activity(transcript_path: str) -> ToolActivity | None:
    """This session's tool calls, read from its Claude Code transcript.

    A ``tool_use`` block in a timestamped record opens a call and the
    ``tool_result`` naming its id closes it. A call whose input sets
    ``run_in_background`` stays open, since its command outlives the call.
    ``None`` when the transcript cannot be read, holds no timestamped record
    or no tool call, has a result for a call it never opened, or has an
    unparseable line before its last one. Only a final line can be mid-write;
    a broken one earlier may have hidden a call, and a missing call would read
    as a moment the session was idle.
    """
    starts: dict[str, float] = {}
    ends: dict[str, float] = {}
    background: set[str] = set()
    first: float | None = None
    broken = False
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                if broken:
                    return None
                try:
                    record = json.loads(line)
                except ValueError:
                    broken = True
                    continue
                if not isinstance(record, dict):
                    continue
                when = _epoch(record.get("timestamp"))
                if when is None:
                    continue
                first = when if first is None else min(first, when)
                message = record.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                        call = block["id"]
                        starts[call] = min(starts.get(call, when), when)
                        args = block.get("input")
                        if isinstance(args, dict) and args.get("run_in_background"):
                            background.add(call)
                    elif block.get("type") == "tool_result" and isinstance(
                        block.get("tool_use_id"), str
                    ):
                        call = block["tool_use_id"]
                        ends[call] = max(ends.get(call, when), when)
    except (OSError, ValueError):  # ValueError: a path with a NUL in it
        return None
    # No call at all, or a result naming a call never seen, is a transcript
    # this reader does not understand (the host's format moved), not a
    # session that never acted: read as idle throughout, it would disown the
    # session's own commits.
    if first is None or not starts or not ends.keys() <= starts.keys():
        return None
    windows = tuple(
        (start, math.inf if call in background or call not in ends else ends[call])
        for call, start in starts.items()
    )
    return ToolActivity(covered_from=first, windows=windows)


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
