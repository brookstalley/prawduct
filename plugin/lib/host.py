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
- **Responses.** :func:`emit_session_context`, :func:`emit_stop_advisory` and
  :func:`block` are the only writers of host response shapes and of the Stop
  hook's blocking exit.

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
import os
import sys
from dataclasses import dataclass, field
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

#: Longest background-task label kept; a description or command can be long.
_TASK_LABEL_CHARS = 80


# --- host selection ----------------------------------------------------------


def host_name() -> str:
    """The host this process runs under: ``PRAWDUCT_HOST``, or ``claude``."""
    return os.environ.get(HOST_VARIABLE, "").strip() or DEFAULT_HOST


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
    that was absent and one that was sent as ``null`` or garbage.

    ``background_tasks`` is the in-flight harness tasks as ``<type>:<ident>``
    labels: ``None`` when the payload had no such field, empty when it had one
    with no usable entry.
    """

    event: str
    last_assistant_message: str | None = None
    background_tasks: tuple[str, ...] | None = None
    cwd: str | None = None
    agent_type: str | None = None
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
