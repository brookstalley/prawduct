"""Is a `test-evidence record` attempt still running? (#1178)

Since #679 the recorder voids the standing ``.test-evidence.json`` before the
suite runs, so every reader sees stale while a run is in flight — the same
answer an abandoned or failed run gives. An agent that sees stale tends to start
a second suite run on top of the first. The void therefore carries an
``in_progress`` stamp (:func:`stamp`), and this module answers, from that stamp,
which of the two it is:

* :data:`RUNNING` — the recorder process is alive on this machine;
* :data:`GONE` — it is not, and no record landed, so the attempt was refused,
  failed, or was killed (``test-status`` calls this *interrupted*);
* :data:`ELSEWHERE` — the stamp names another machine, whose processes this one
  cannot see. Treated as running, but only for a while: see below.

**A pid is not an identity, so liveness is checked against the start time.**
Once the recorder dies its pid can be handed to an unrelated process, which
would then read as a run that never ends. ``ps -o stat=,etime=`` (POSIX, on
macOS and Linux alike) gives the live process's age; a process that started
after the stamp was written cannot be the recorder that wrote it. The stamp is
written by the recorder after it starts, so the real recorder always started
before ``started_at``; :data:`_START_SLACK_SECONDS` absorbs ``ps``'s whole-second
rounding. An unreaped zombie is dead.

**Every state that cannot be checked has an end** (#1178 R-2/R-7). A stamp from
another machine, or a live pid ``ps`` could not confirm as the recorder (no
``ps``, or it hung), reads as running only until it is older than
:func:`unverified_bound` — several times the last recorded run's duration, never
less than a floor — and as :data:`GONE` after that. Without the bound, a
recorder that died on another machine read as running forever, and every
refusal said to wait and not start another run: advice that, obeyed, never
ends. The cost of the bound is the opposite error: a recorder still going past
it reads as interrupted, and the reader runs the suite once more. Never a false
green, because running and interrupted both refuse.

**"Another machine" is a boot, not a hostname.** A pid means something only
within one boot of one kernel and, on Linux, one pid namespace, so that is what
:func:`this_machine` names: the kernel's boot id and pid namespace on Linux,
the boot time elsewhere (``sysctl kern.boottime``: macOS and the BSDs). macOS
renames the host with the network and a container differs from its host, so a
hostname check read a recorder on the same laptop as another host's. A stamp
written before ``machine`` existed, or on a platform that yields none, falls
back to the hostname.

**One probe per stamp per verdict.** One gate evaluation reads the record
through several readers (the freshness verdict, the store fallback, the tree
question, the remedy), and each used to run ``ps`` again. The local probe is
memoised on the stamp's identity (pid and start) until :func:`forget`, which
``test-status --wait`` calls before every poll — the one long-lived caller that
needs a recorder's death noticed in-process. A hook is a fresh process per call.

Read by ``gates.record_in_progress`` (the sentence every gate's refusal and
``test-status`` print) and ``gates.test_status`` (the three labels, the elapsed
estimate, ``--wait``). Nothing here writes.
"""

from __future__ import annotations

import functools
import os
import socket
import subprocess
import sys
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

#: How long a recorder whose life cannot be checked reads as running: this many
#: times the last recorded run's duration, and never less than the floor. The
#: factor leaves room for a contended or slower run; the floor covers a first
#: run (no duration yet) and a suite whose last run was short.
UNVERIFIED_FACTOR = 3
UNVERIFIED_FLOOR_SECONDS = 1800

#: Whole seconds ``ps`` rounds a process's age to, plus clock granularity.
_START_SLACK_SECONDS = 2
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def this_host() -> str:
    """The hostname: shown to the reader, and the identity only for a stamp
    that carries no ``machine``."""
    return socket.gethostname()


@functools.cache
def this_machine() -> "str | None":
    """The scope a pid is meaningful in — this boot, and on Linux this pid
    namespace — or ``None`` when the platform does not say. Stable across
    hostname changes, unlike :func:`this_host`, and different in a container."""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as handle:
                boot = handle.read().strip()
            namespace = os.readlink("/proc/self/ns/pid")
        except OSError:
            return None
        return f"linux:{boot}:{namespace}" if boot and namespace else None
    try:
        proc = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # `{ sec = 1793628903, usec = 957122 } Mon Nov  2 06:15:03 2026`
    fields = proc.stdout.replace(",", " ").split()
    try:
        sec = fields[fields.index("sec") + 2]
        usec = fields[fields.index("usec") + 2]
    except (ValueError, IndexError):
        return None
    if proc.returncode != 0 or not (sec.isdigit() and usec.isdigit()):
        return None
    return f"boot:{sec}.{usec}"


def stamp(command: str, started_at: str) -> dict:
    """The ``in_progress`` value the recorder writes into its void: who to ask
    whether the run is still going, and what it is running."""
    value = {
        "pid": os.getpid(),
        "host": this_host(),
        "started_at": started_at,
        "command": command,
    }
    machine = this_machine()
    if machine:
        value["machine"] = machine
    return value


def unverified_bound(previous_seconds: object) -> float:
    """Seconds a recorder whose life cannot be checked reads as running."""
    if (
        isinstance(previous_seconds, (int, float))
        and not isinstance(previous_seconds, bool)
        and previous_seconds > 0
    ):
        return max(float(UNVERIFIED_FLOOR_SECONDS), UNVERIFIED_FACTOR * float(previous_seconds))
    return float(UNVERIFIED_FLOOR_SECONDS)


#: The local probe's answers, keyed on the stamp's identity (pid, start); see
#: the module docstring. Cleared by :func:`forget`.
_PROBED: "dict[tuple, tuple[str, str, bool]]" = {}


def forget() -> None:
    """Drop memoised probe answers, so the next read asks the process table
    again. ``test-status --wait`` calls it before every poll."""
    _PROBED.clear()


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


def _elsewhere(in_progress: dict) -> "str | None":
    """The name of the other machine this stamp was written on, or ``None``
    when it was written on this one."""
    host = in_progress.get("host")
    shown = host if isinstance(host, str) and host else "another machine"
    theirs, ours = in_progress.get("machine"), this_machine()
    if isinstance(theirs, str) and theirs and ours:
        return shown if theirs != ours else None
    if isinstance(host, str) and host and host != this_host():
        return shown
    return None


def _past_bound(in_progress: dict, previous_seconds: object) -> "tuple[bool, str]":
    """Whether an unverifiable stamp is past :func:`unverified_bound`, and a
    clause saying when it gets there, or that it has."""
    bound = unverified_bound(previous_seconds)
    started = _parse_ts(in_progress.get("started_at"))
    if started is None:
        return True, "and when it started cannot be read"
    age = datetime.now(timezone.utc).timestamp() - started.timestamp()
    if age > bound:
        return True, f"and it started more than {_duration(bound)} ago, the most it is waited for"
    deadline = datetime.fromtimestamp(started.timestamp() + bound, timezone.utc)
    return False, (
        f"it reads as interrupted from {deadline.strftime(_TS_FORMAT)} "
        f"({_duration(bound)} after it started)"
    )


def recorder_state(in_progress: object, previous_seconds: object = None) -> "tuple[str, str]":
    """``(state, why)`` for an ``in_progress`` stamp; ``why`` is a clause for
    the caller's sentence, empty when there is nothing to add.
    ``previous_seconds`` is the last recorded run's duration, which sets how
    long a recorder that cannot be checked reads as running."""
    if not isinstance(in_progress, dict):
        return GONE, "the in-progress stamp is not readable"
    pid = in_progress.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return GONE, "the in-progress stamp names no process"
    other = _elsewhere(in_progress)
    if other is not None:
        past, when = _past_bound(in_progress, previous_seconds)
        where = f"it was started on {other}, whose processes this machine cannot see"
        if past:
            return GONE, f"{where}, {when}"
        return ELSEWHERE, f"{where}; {when}"
    key = (pid, in_progress.get("started_at"))
    if key not in _PROBED:
        _PROBED[key] = _probe(pid, in_progress)
    state, why, verified = _PROBED[key]
    if state == RUNNING and not verified:
        past, when = _past_bound(in_progress, previous_seconds)
        return (GONE, f"{why}, {when}") if past else (state, f"{why}; {when}")
    return state, why


def _probe(pid: int, in_progress: dict) -> "tuple[str, str, bool]":
    """Ask this machine's process table about ``pid``: ``(state, why,
    verified)``. ``verified`` is False for a live pid that could not be
    confirmed as the recorder — ``kill`` or ``ps`` itself failed — whose
    running answer :func:`recorder_state` then bounds by age."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return GONE, f"no process has pid {pid}", True
    except PermissionError:
        pass  # alive, owned by another user
    except OSError as exc:
        return RUNNING, f"whether pid {pid} is alive could not be checked ({exc})", False
    try:
        proc = subprocess.run(
            ["ps", "-o", "stat=,etime=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            RUNNING,
            f"pid {pid} is alive; whether it is still the recorder was not checked ({exc})",
            False,
        )
    fields = proc.stdout.split()
    if proc.returncode != 0 or len(fields) < 2:
        return GONE, f"no process has pid {pid}", True
    if fields[0].startswith("Z"):
        return GONE, f"pid {pid} has exited", True
    age = _etime_seconds(fields[-1])
    started = _parse_ts(in_progress.get("started_at"))
    if age is not None and started is not None:
        process_start = datetime.now(timezone.utc).timestamp() - age
        if process_start > started.timestamp() + _START_SLACK_SECONDS:
            return GONE, f"pid {pid} was reused by a process that started after the run", True
    return RUNNING, "", True


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
