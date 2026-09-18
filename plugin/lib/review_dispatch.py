"""The PR reviewer's dispatch clock — a code-written stopwatch for review duration.

``duration_seconds`` on a ``review.pr`` ledger event is **self-reported by the
reviewing model**: it is the reviewer's own recollection of how long it took,
written into the evidence record it produces. That number is corroborated within
16% where commits are dense enough to check it, which is what licenses using it
at all — but a performance target stated against an estimate is a target stated
against an estimate, and the whole point of a payload change is to be graded.

This module supplies the other half: a per-clone marker written **before** the
reviewer is spawned, from a clock this code reads. The caller chooses *when* to
mark; it never chooses the value, so no model sits in the write path
(``data-model.md``: governance verdicts come from code-written facts).

**Absence means "not measured", never zero.** A run that is never marked, a
marker that cannot be read, a marker belonging to a different tree — all three
produce no ``dispatched_at`` key at all, and every consumer reports the measured
and self-reported populations separately rather than averaging a missing value
into a real one. A field whose absence is ambiguous renders the exact inverse of
the signal it was added for.

**Staleness is answered by the tree, not by a clock.** A review that dies between
the mark and the append leaves its marker behind, and the next append would
otherwise attach a multi-hour interval to an unrelated review. The marker records
the ``HEAD`` it was written at; consumption requires that same ``HEAD``, because
a dispatch made against a different tree is not this review's dispatch. That is
the same question the evidence store asks — facts record trees — and unlike an
age threshold it invents no number. The residual it does not cover is a
re-dispatch at the *same* tree with no fresh mark, which inflates the interval;
``/prawduct:pr`` marks on every dispatch, and :func:`measured_interval_seconds`
carries a plausibility bound for what gets through anyway. That bound lives HERE,
with the marker semantics, rather than in whichever consumer happened to be
written first: the interval predicate has one home and every reader calls it, so
a second consumer cannot inherit the mechanism without the bound that makes it
safe.

**Only ``review.pr`` appends consume it.** The Critic and the PR reviewer can run
concurrently, so a ``review.critic`` append that cleared this marker would delete
a live PR review's measurement — and it would do it silently, on the timing where
the two overlap most.

This is per-clone state with a per-clone lifetime: a stopwatch, not an answer, so
it is gitignored and never committed (``data-model.md``: two stores, two
lifetimes).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MARKER_BASENAME = ".pr-review-dispatch.json"

#: The event kinds whose append consumes a dispatch mark. Deliberately a set of
#: one: see the module docstring on concurrent Critic runs. A kind added here
#: without that argument re-opens the race.
CONSUMING_EVENT_KINDS = frozenset({"review.pr"})


def head_sha(project_dir: Path) -> str | None:
    """Current ``HEAD``, or ``None`` when git could not answer.

    The ONE home for this read, shared with the ledger envelope's ``git.head``.
    Staleness here is decided by comparing a marker's tree against the appending
    event's tree, so two readers of "what is HEAD" could disagree — over a failure
    spelled ``""`` in one and ``None`` in the other, or across a commit landing
    between two calls — and the disagreement would render as an abandoned run.
    One function means the question cannot be asked two ways.

    ``None`` on any failure: the writer must not crash, and a repo-less fixture
    still gets an honest ``git: {head: null}``.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception:  # prawduct:allow prawduct/broad-except -- envelope fields are nullable, never fatal
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


#: The longest interval a dispatch mark may attest. Chosen to sit far outside any
#: real review while still refusing the multi-hour spans a stale mark produces —
#: the tree check catches a mark from a DIFFERENT tree, and this catches the
#: residual it cannot see, a re-dispatch at the same tree with no fresh mark.
#: A refused interval is not an error: the reader falls back to the self-reported
#: estimate and counts the row in that population, so a refused measurement never
#: reads as an absent review.
MAX_PLAUSIBLE_REVIEW_SECONDS = 6 * 60 * 60


def measured_interval_seconds(dispatched_at, wrote_at) -> "float | None":
    """Seconds a dispatch mark attests, or ``None`` when it attests nothing.

    **The one home for this predicate.** Three readers ask it — ``review-stats``,
    ``tools/pr-review-yield.py`` and ``tools/measure-consumer-overhead.py`` — and
    they are grading the same field for the same before/after comparison. Written
    out at each of them it diverged immediately: one carried the plausibility
    bound and the others refused only a negative interval, so a stale same-tree
    mark inflated exactly the medians the comparison is read from.

    ``None`` is NOT MEASURED and never zero. Four ways to get it, all of which
    leave the caller with the self-reported estimate rather than a bad number:

    - either stamp missing or not a string (an event written before the clock
      existed, a hand-edited row, a writer from another toolchain);
    - either stamp unparseable;
    - the pair out of order, which a clock skew or a hand edit can produce — a
      negative interval parses cleanly and would otherwise be labelled measured;
    - an interval past :data:`MAX_PLAUSIBLE_REVIEW_SECONDS`.

    The last two matter most: a nonsense measurement DISPLACING an honest estimate
    is worse than no measurement, because the estimate at least knows it is one.
    """
    if not isinstance(dispatched_at, str) or not isinstance(wrote_at, str):
        return None
    try:
        started = datetime.fromisoformat(dispatched_at.replace("Z", "+00:00"))
        ended = datetime.fromisoformat(wrote_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    seconds = (ended - started).total_seconds()
    if seconds < 0 or seconds > MAX_PLAUSIBLE_REVIEW_SECONDS:
        return None
    return seconds


def marker_path(prawduct_dir: Path) -> Path:
    return prawduct_dir / MARKER_BASENAME


def begin(prawduct_dir: Path, head: str | None) -> dict:
    """Mark a dispatch now. Returns the record written.

    Overwrites unconditionally — the newest dispatch is the one an append is
    measuring, and a previous mark that was never consumed is by definition
    abandoned.
    """
    record = {
        "dispatched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": head,
    }
    prawduct_dir.mkdir(parents=True, exist_ok=True)
    marker_path(prawduct_dir).write_text(json.dumps(record) + "\n", encoding="utf-8")
    return record


def consume(prawduct_dir: Path, event_kind: str, head: str | None) -> tuple[str | None, str]:
    """Take the dispatch stamp for an append. Returns ``(stamp, reason)``.

    ``stamp`` is ``None`` whenever the append must be recorded as not measured,
    and ``reason`` always says which case it was — an unnamed degradation on an
    advisory path manufactures the false success it exists to prevent.

    The marker is cleared whenever this function looked at it, including when the
    tree did not match: ``HEAD`` only moves forward, so a mark that does not match
    today can never legitimately match later, and leaving it would fail the same
    way on every future append.
    """
    if event_kind not in CONSUMING_EVENT_KINDS:
        return None, f"{event_kind} does not consume a dispatch mark"

    path = marker_path(prawduct_dir)
    if not path.is_file():
        return None, "no dispatch mark (review was not marked before it was spawned)"

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        path.unlink(missing_ok=True)
        return None, f"dispatch mark unreadable ({exc.__class__.__name__}) — recorded as not measured"

    path.unlink(missing_ok=True)

    if not isinstance(record, dict):
        return None, "dispatch mark is not an object — recorded as not measured"
    stamp = record.get("dispatched_at")
    if not isinstance(stamp, str) or not stamp.strip():
        return None, "dispatch mark carries no timestamp — recorded as not measured"

    marked_head = record.get("head")
    if marked_head is None or head is None:
        # Both sides null compares EQUAL, which would attach the mark with no
        # staleness protection at all — on the one input where we cannot show it
        # is this review's. Unverifiable is not the same as verified.
        return None, (
            "dispatch mark cannot be checked against a tree (git did not answer "
            f"at {'mark' if marked_head is None else 'append'} time) — recorded "
            "as not measured"
        )
    if marked_head != head:
        return None, (
            f"dispatch mark is for a different tree ({_short(marked_head)} != "
            f"{_short(head)}) — an abandoned run's mark, recorded as not measured"
        )
    return stamp, f"measured from a dispatch mark at {stamp}"


def _short(head: str | None) -> str:
    """A sha for a one-line reason, or a word saying there wasn't one."""
    if not isinstance(head, str) or not head.strip():
        return "no-head"
    return head[:8]
