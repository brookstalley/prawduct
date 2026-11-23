"""The one owner of "what time is it now" for prawduct's records and gates.

The records the plugin stamps and later compares (an evidence fact, the
``.session-start`` marker, a ledger event, a backlog sync, an advisory
transition), and the comparisons against them, read the wall clock through
:func:`now`; each read that does not is listed with its reason in
``tests/test_clock.py``. Which clock a read uses is decided by what it is
compared with, not by the module that makes it: a stamp that leaves its module
and meets one of these records reads :func:`now`, wherever it was minted. The gates compare such stamps with git's own dates: the Stop gate's session-work walk bounds the
HEAD reflog by the ``.session-start`` stamp, and git dates a reflog entry by the
committer date. A process whose stamps and whose commits read two different
clocks gets that comparison wrong, so a test suite that pins git's dates has to
pin this clock to the same instant, or "a commit made after the session began"
reads as made before it.

:data:`FROZEN_ENV` is that pin. It is unmistakably a test fixture: nothing a
consumer's shell or CI would set for another reason carries the name, and a
value that does not parse is ignored rather than trusted. Its value has git's
own internal date form, ``@<epoch seconds> +0000``, so one literal can set it
and ``GIT_AUTHOR_DATE``/``GIT_COMMITTER_DATE`` together. It is an environment
variable because the hook runs as a subprocess of the harness (and of tests),
and an environment variable is what reaches a child unasked.

What does NOT read this clock, on purpose:

* durations and timeouts, which use :func:`time.monotonic` and so are untouched
  by a frozen wall clock;
* ages measured against a file's mtime or another process's real start, which
  the filesystem and the OS date by the real clock (a frozen "now" would make
  every such file look older or younger than it is). The exception is a file
  :func:`date_file` dated, whose mtime is on this clock: a reader that ages it
  beside real mtimes (``stranded_work``'s worktree liveness) carries its stamp
  across first;
* staleness and TTL logic under test, which takes an injected instant.

Stdlib only, no relative imports: ``bin/prawduct-hook`` imports it from its own
plugin tree before anything else of ``lib/`` is needed.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

#: The environment variable that freezes :func:`now`. Test-only by name.
FROZEN_ENV = "PRAWDUCT_TEST_ONLY_FROZEN_NOW"

#: git's internal date form, which is also what :data:`FROZEN_ENV` holds. Only
#: UTC: a frozen instant with another zone would have to be rendered in it,
#: and nothing here renders a local time from it.
_GIT_INTERNAL_DATE = re.compile(r"@(\d+) \+0000")


def frozen() -> "datetime | None":
    """The instant :data:`FROZEN_ENV` pins, or ``None`` when the clock is real.

    A value that does not parse is ``None``: the variable exists only for the
    test suite, which always sets a well-formed one, so a malformed value is
    someone else's and is not obeyed."""
    match = _GIT_INTERNAL_DATE.fullmatch(os.environ.get(FROZEN_ENV, "").strip())
    if match is None:
        return None
    return datetime.fromtimestamp(int(match.group(1)), timezone.utc)


def now() -> datetime:
    """The current instant, timezone-aware UTC: the frozen one when pinned."""
    pinned = frozen()
    return pinned if pinned is not None else datetime.now(timezone.utc)


def now_iso() -> str:
    """:func:`now` as the ``YYYY-MM-DDTHH:MM:SSZ`` stamp the plugin's records use."""
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def local_today() -> date:
    """Today's date on this machine's local calendar, from :func:`now`."""
    pinned = frozen()
    return pinned.astimezone().date() if pinned is not None else date.today()


def date_file(path: Path) -> None:
    """Give ``path`` the frozen instant as its mtime and atime; with a real clock, do nothing.

    For a marker whose time is read back from its mtime as well as from its
    content (``.session-start``): the filesystem dates a write by the real
    clock, so under a frozen one the two readings would disagree. Raises
    ``OSError`` as :func:`os.utime` does."""
    pinned = frozen()
    if pinned is not None:
        seconds = pinned.timestamp()
        os.utime(path, (seconds, seconds))
