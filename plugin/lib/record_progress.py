"""Is a `test-evidence record` attempt still running? (#1178)

Since #679 the recorder voids the standing ``.test-evidence.json`` before the
suite runs, so every reader sees stale while a run is in flight — the same
answer an abandoned or failed run gives. An agent that sees stale tends to start
a second suite run on top of the first. The void therefore carries an
``in_progress`` stamp (:func:`stamp`), and this module answers, from that stamp,
which of the two it is:

* :data:`RUNNING` — the recorder process is alive on this host;
* :data:`GONE` — it is not, and no record landed, so the attempt was refused,
  failed, or was killed (``test-status`` calls this *interrupted*);
* :data:`ELSEWHERE` — the stamp names another host, whose processes this one
  cannot see.

**A pid is not an identity, so liveness is checked against the start time.**
Once the recorder dies its pid can be handed to an unrelated process, which
would then read as a run that never ends. ``ps -o stat=,etime=`` (POSIX, on
macOS and Linux alike) gives the live process's age; a process that started
after the stamp was written cannot be the recorder that wrote it. The stamp is
written by the recorder after it starts, so the real recorder always started
before ``started_at``; :data:`_START_SLACK_SECONDS` absorbs ``ps``'s whole-second
rounding. Without ``ps`` (or if it hangs) the check falls back to the pid alone
and says so — the residual risk is a reused pid reading as running until a
record lands or ``--wait`` times out, never a false green, because a running
state refuses exactly as stale does. An unreaped zombie is dead.

Read by ``gates.run_refusal`` (the refusal text says to wait, not re-run) and
``gates.test_status`` (the three labels, the elapsed estimate, ``--wait``).
Nothing here writes.
"""

from __future__ import annotations

import os
import socket
import subprocess
from datetime import datetime, timezone

RUNNING = "running"
GONE = "gone"
ELSEWHERE = "elsewhere"

#: ``test-status --wait``'s bounds. The default sits under the ten-minute
#: ceiling an agent's shell call usually has, so a bare ``--wait`` returns an
#: answer rather than being killed by its caller; the maximum keeps one call
#: from holding a session for longer than any suite here should take.
WAIT_DEFAULT_SECONDS = 300
WAIT_MAX_SECONDS = 3600
#: How often ``--wait`` re-reads the record.
WAIT_POLL_SECONDS = 1.0
#: ``test-status --wait``'s exit when the timeout expires with the run still in
#: progress: sysexits' EX_TEMPFAIL, "try again later". Not 1 — that is stale,
#: whose remedy (run the suite) is the second run this exists to prevent — and
#: not 3, which means the subject could not be read; this one was read, and is
#: still running.
WAIT_TIMEOUT_EXIT = 75

#: Whole seconds ``ps`` rounds a process's age to, plus clock granularity.
_START_SLACK_SECONDS = 2
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def this_host() -> str:
    return socket.gethostname()


def stamp(command: str, started_at: str) -> dict:
    """The ``in_progress`` value the recorder writes into its void: who to ask
    whether the run is still going, and what it is running."""
    return {
        "pid": os.getpid(),
        "host": this_host(),
        "started_at": started_at,
        "command": command,
    }


def _parse_ts(value: object) -> "datetime | None":
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _etime_seconds(text: str) -> "int | None":
    """``ps``'s ``etime``, ``[[dd-]hh:]mm:ss``, in seconds; None if malformed."""
    days_text, _, clock = text.strip().rpartition("-")
    try:
        days = int(days_text) if days_text else 0
        parts = [int(p) for p in clock.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        hours, minutes, seconds = 0, parts[0], parts[1]
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        return None
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def recorder_state(in_progress: object) -> "tuple[str, str]":
    """``(state, why)`` for an ``in_progress`` stamp; ``why`` is a clause for
    the caller's sentence, empty when there is nothing to add."""
    if not isinstance(in_progress, dict):
        return GONE, "the in-progress stamp is not readable"
    pid = in_progress.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return GONE, "the in-progress stamp names no process"
    host = in_progress.get("host")
    if isinstance(host, str) and host and host != this_host():
        return ELSEWHERE, f"it is running on {host}, whose processes this host cannot see"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return GONE, f"no process has pid {pid}"
    except PermissionError:
        pass  # alive, owned by another user
    except OSError as exc:
        return RUNNING, f"whether pid {pid} is alive could not be checked ({exc})"
    try:
        proc = subprocess.run(
            ["ps", "-o", "stat=,etime=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return RUNNING, f"pid {pid} is alive; whether it is still the recorder was not checked ({exc})"
    fields = proc.stdout.split()
    if proc.returncode != 0 or len(fields) < 2:
        return GONE, f"no process has pid {pid}"
    if fields[0].startswith("Z"):
        return GONE, f"pid {pid} has exited"
    age = _etime_seconds(fields[-1])
    started = _parse_ts(in_progress.get("started_at"))
    if age is not None and started is not None:
        process_start = datetime.now(timezone.utc).timestamp() - age
        if process_start > started.timestamp() + _START_SLACK_SECONDS:
            return GONE, f"pid {pid} was reused by a process that started after the run"
    return RUNNING, ""


def _duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def progress(in_progress: object, previous_seconds: object) -> str:
    """``elapsed Xs`` and, when a previous run's duration is known, how that
    compares — labelled as the estimate it is. Never a percentage: the
    previous run's length says nothing about how far this one has got."""
    started = _parse_ts(in_progress.get("started_at") if isinstance(in_progress, dict) else None)
    if started is None:
        return "elapsed unknown"
    elapsed = max(0.0, datetime.now(timezone.utc).timestamp() - started.timestamp())
    line = f"elapsed {_duration(elapsed)}"
    if (
        isinstance(previous_seconds, (int, float))
        and not isinstance(previous_seconds, bool)
        and previous_seconds > 0
    ):
        prior = _duration(previous_seconds)
        if elapsed <= previous_seconds:
            line += f" of about {prior} (estimate: the last recorded run took {prior})"
        else:
            line += f", past the last recorded run's {prior} (that estimate is exceeded)"
    return line


def describe(in_progress: object) -> str:
    """``pid N, started T: <command>`` for a refusal or a status line."""
    if not isinstance(in_progress, dict):
        return "an unreadable in-progress stamp"
    pid = in_progress.get("pid")
    started = in_progress.get("started_at") or "(unknown)"
    command = in_progress.get("command") or "(unknown command)"
    return f"pid {pid}, started {started}: {command}"
