"""The review dispatch clock — a code-written stopwatch for review duration.

``duration_seconds`` on a ``review.*`` ledger event is **self-reported by the
reviewing model**: it is the reviewer's own recollection of how long it took,
written into the evidence record it produces. Read against this module's clock on
the same rows it runs high, worst on short reviews (the measurements are in
``documentation/consumer-build-metrics.md`` hazard 2). So it is a fallback for
unmarked rows, never a measurement, and a performance target stated against it is
a target stated against an estimate.

How weak the estimate is, measured rather than supposed: across the first 1,026
ledger rounds, ``duration_seconds`` took 63 distinct values, 80% of them
multiples of 30 seconds and 23% of them exactly ``300``. That is a model
answering "about five minutes", and no amount of averaging turns it into a
clock. ``prawduct-hook review-stats`` reports the measured and self-reported
populations separately for exactly this reason, but it publishes only
``{reviews, total_seconds, median_seconds}`` per population — the distinct-value
count and the clustering share come from a scan of
``.prawduct/.governance-ledger.jsonl`` over ``duration_seconds``, and must be
re-derived there rather than from the command.

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
age threshold it invents no number. For a ``review.pr`` the tree it is checked
against is the one the reviewer READ (its evidence's ``commit_reviewed``), not
``HEAD`` at append time. The caller fixes the review's findings before appending,
so ``HEAD`` has usually moved by then. The tree moving is not the same thing as
this being a different review. The residual it does not cover is a
re-dispatch at the *same* tree with no fresh mark, which inflates the interval;
``/prawduct:pr`` marks on every dispatch, and :func:`measured_interval_seconds`
carries a plausibility bound for what gets through anyway. That bound lives HERE,
with the marker semantics, rather than in whichever consumer happened to be
written first: the interval predicate has one home and every reader calls it, so
a second consumer cannot inherit the mechanism without the bound that makes it
safe.

**One slot PER CONSUMING EVENT KIND, and that is the whole concurrency design.**
The Critic and the PR reviewer run at the same time by deliberate arrangement
(``nonfunctional-requirements.md``: the two boundary reviews run in parallel,
never sequentially), so a ``review.critic`` append that cleared a *shared*
marker would delete a live PR review's measurement — silently, and only on the
timing where the two actually overlap, which is the timing the design wants.
Giving each kind its own file makes that failure **unreachable rather than
avoided**: there is no shared cell to clear, so no ordering of the two appends
can lose either measurement. That is the norm's own instruction — races are
avoided by construction wherever a design choice can avoid them
(``architecture.md`` § Direction) — applied in preference to the narrower fix of
widening one consumer set, which keeps the shared cell and asks every future
caller to be careful around it.

A kind absent from :data:`MARKER_BASENAMES` consumes nothing and marks nothing;
adding one is adding a file, never a second consumer of someone else's.

This is per-clone state with a per-clone lifetime: a stopwatch, not an answer, so
it is gitignored and never committed (``data-model.md``: two stores, two
lifetimes).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

#: One marker file per consuming event kind — see the module docstring on
#: concurrency. The mapping IS the design: two kinds cannot contend because they
#: never address the same path, so this is the place a future kind is added, and
#: adding one here gives it a slot rather than a share of someone else's.
#:
#: ``review.pr``'s basename is unchanged from when it was the only one. A rename
#: would strand any marker a running PR review had already written, turning a
#: plugin upgrade mid-review into a lost measurement for no benefit.
MARKER_BASENAMES = {
    "review.pr": ".pr-review-dispatch.json",
    "review.critic": ".critic-review-dispatch.json",
}

#: The event kinds whose append consumes a dispatch mark — derived from the
#: mapping rather than restated, so a kind can never have a file and no
#: consumer, or a consumer and no file.
CONSUMING_EVENT_KINDS = frozenset(MARKER_BASENAMES)


def head_sha(project_dir: Path) -> str | None:
    """Current ``HEAD``, or ``None`` when git could not answer.

    One home for the MARKER/ENVELOPE pair, which is the property this design
    needs — not for the repo, and the difference is worth stating because the
    counterexample already exists: ``gitstate._git_head_sha`` has answered the
    same question since before this function, returns ``""`` on failure rather
    than ``None``, and is live in ``critic_mode``. Staleness here is decided by
    comparing a marker's tree against the appending event's tree, so if those two
    readers disagreed — over that exact failure spelling, or across a commit
    landing between two calls — the disagreement would render as an abandoned
    run. Both sides of that comparison come through this function, so they
    cannot. No current consumer compares the two functions; a future one must
    route through one of them rather than assume they agree.

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

    **The one home for this predicate.** Every reader of a dispatch interval asks
    it, through :func:`event_interval_seconds` (a ledger event) or
    :func:`fact_interval_seconds` (a review fact), and never computes its own.
    Written out at each reader it diverged immediately: one carried the
    plausibility bound and the others refused only a negative interval, so a
    stale same-tree mark inflated exactly the medians a before/after comparison
    is read from.

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


#: The tree argument :func:`consume` receives when the review's own record names
#: a commit this repo cannot resolve. It is refused by name. Comparing it as text
#: would only ever produce a "different tree" reason, which would call a real
#: review an abandoned one.
UNRESOLVED_TREE = "<unresolved>"


def event_interval_seconds(event: dict) -> "float | None":
    """Seconds a ledger event's dispatch mark attests, or ``None``.

    The event-level door to :func:`measured_interval_seconds`, and the one
    place that decides where an interval ENDS. A ``review.pr`` event carries
    ``review_written_at``, the time the reviewer's evidence file was written.
    That is the end, because the append comes later: the caller fixes findings
    between the two, and that time is not review time. Every other event ends at
    its own ``ts``, which is also the fallback for rows written before the key
    existed. All three readers call this, so none of them picks the end on its
    own.
    """
    end = event.get("review_written_at")
    if not isinstance(end, str):
        end = event.get("ts")
    return measured_interval_seconds(event.get("dispatched_at"), end)


def fact_interval_seconds(fact: dict) -> "float | None":
    """Seconds a review FACT's dispatch mark attests, or ``None``.

    The fact-level door to :func:`measured_interval_seconds`, beside
    :func:`event_interval_seconds` and for the same reason: the one place that
    decides where the interval ends. A review fact carries the mark's stamp as
    the optional body key ``dispatched_at`` (``critic-consolidate`` reads the
    mark with :func:`peek` when it mints the fact), and the interval ends at the
    fact's own envelope ``ts`` — the moment consolidation recorded the review,
    which is the same end a ``review.critic`` ledger event's ``ts`` marks.

    The fact is the carrier that reaches every worktree: the evidence store is
    shared by the whole clone, while a ledger is per worktree, so a reader
    joining to the ledger sees only its own worktree's rounds. ``None`` is NOT
    MEASURED — a fact minted before the key existed, or from a review that was
    never marked, has no clock and its duration is the reviewer's estimate.
    """
    if not isinstance(fact, dict):
        return None
    body = fact.get("body")
    if not isinstance(body, dict):
        return None
    return measured_interval_seconds(body.get("dispatched_at"), fact.get("ts"))


def resolve_commit(project_dir: Path, rev) -> str | None:
    """``rev`` as a full commit sha, or ``None`` when it names no commit here.

    The PR reviewer records the tree it read as ``commit_reviewed``. The
    protocol asks for a full sha, but an abbreviated one names the same commit,
    so it is resolved rather than compared as text. A strict text match would
    report a real review as an abandoned one.
    """
    if not isinstance(rev, str) or not rev.strip():
        return None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{rev.strip()}^{{commit}}"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def file_written_at(path: Path) -> str | None:
    """``path``'s mtime as a UTC stamp in the marker's own format, or ``None``.

    Second resolution, truncated, like :func:`begin`'s stamp. Both are
    truncated the same way, so a file written after a mark can never read as
    earlier than it.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def marker_path(prawduct_dir: Path, event_kind: str) -> Path:
    """This kind's marker file.

    Raises ``KeyError`` for a kind that owns no slot. That is deliberate and it
    is the safe direction: the alternative — falling back to some default path —
    would silently hand a new kind another kind's cell, which is precisely the
    contention the per-kind mapping exists to make unreachable.
    """
    return prawduct_dir / MARKER_BASENAMES[event_kind]


def begin(prawduct_dir: Path, event_kind: str, head: str | None) -> dict:
    """Mark a dispatch of ``event_kind`` now. Returns the record written.

    Overwrites unconditionally — the newest dispatch is the one an append is
    measuring, and a previous mark that was never consumed is by definition
    abandoned. Unconditional overwrite is scoped to THIS kind's slot; it has
    never been, and must not become, a reason for one kind to touch another's.
    """
    record = {
        "dispatched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": head,
    }
    prawduct_dir.mkdir(parents=True, exist_ok=True)
    marker_path(prawduct_dir, event_kind).write_text(
        json.dumps(record) + "\n", encoding="utf-8"
    )
    return record


def peek(prawduct_dir: Path, event_kind: str, head: str | None) -> tuple[str | None, str]:
    """Read the dispatch stamp WITHOUT clearing it. Returns ``(stamp, reason)``.

    The same judgement :func:`consume` makes, over the same marker, with the same
    tree check — for a reader that must see the mark before its consumer does.
    ``critic-consolidate`` mints the review fact before it appends the ledger
    event, and the ledger append is what consumes the mark; the fact body carries
    the stamp too (so a clone-shared store can answer "how long did this round
    take" for every worktree, not only the one whose ledger holds the event), so
    it reads the mark here and leaves it for the append.

    One judgement, two verbs: the reasons, the refusals and the tree check live
    in :func:`_judge`, so a fact and a ledger event minted from the same mark
    cannot disagree about whether it was this review's.
    """
    stamp, reason, _looked = _judge(prawduct_dir, event_kind, head)
    return stamp, reason


def consume(prawduct_dir: Path, event_kind: str, head: str | None) -> tuple[str | None, str]:
    """Take the dispatch stamp for an append. Returns ``(stamp, reason)``.

    ``head`` is the tree this review was OF: the envelope's ``HEAD`` for a
    Critic append, and the resolved ``commit_reviewed`` for a PR append.

    ``stamp`` is ``None`` whenever the append must be recorded as not measured,
    and ``reason`` always says which case it was — an unnamed degradation on an
    advisory path manufactures the false success it exists to prevent.

    The marker is cleared whenever this function looked at it, including when the
    tree did not match. Each mark belongs to one dispatch and each append consumes
    the newest one, so a mark that did not match this append has no later review
    to match. Leaving it would fail the same way on every future append.
    """
    stamp, reason, looked = _judge(prawduct_dir, event_kind, head)
    if looked:
        marker_path(prawduct_dir, event_kind).unlink(missing_ok=True)
    return stamp, reason


def _judge(
    prawduct_dir: Path, event_kind: str, head: str | None
) -> tuple[str | None, str, bool]:
    """``(stamp, reason, looked)`` for this kind's mark against ``head``.

    ``looked`` is whether a marker file existed to judge — the condition under
    which :func:`consume` clears it. Reads only; never writes or removes.
    """
    if event_kind not in CONSUMING_EVENT_KINDS:
        return None, f"{event_kind} does not consume a dispatch mark", False

    path = marker_path(prawduct_dir, event_kind)
    if not path.is_file():
        return None, "no dispatch mark (review was not marked before it was spawned)", False

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, (
            f"dispatch mark unreadable ({exc.__class__.__name__}) — recorded as not measured"
        ), True

    if not isinstance(record, dict):
        return None, "dispatch mark is not an object — recorded as not measured", True
    stamp = record.get("dispatched_at")
    if not isinstance(stamp, str) or not stamp.strip():
        return None, "dispatch mark carries no timestamp — recorded as not measured", True

    marked_head = record.get("head")
    if head == UNRESOLVED_TREE:
        return None, (
            "dispatch mark cannot be checked against a tree (the review's "
            "commit_reviewed names no commit in this repo), so it is recorded "
            "as not measured"
        ), True
    if marked_head is None or head is None:
        # Both sides null compares EQUAL, which would attach the mark with no
        # staleness protection at all — on the one input where we cannot show it
        # is this review's. Unverifiable is not the same as verified.
        return None, (
            "dispatch mark cannot be checked against a tree (git did not answer "
            f"at {'mark' if marked_head is None else 'append'} time) — recorded "
            "as not measured"
        ), True
    if marked_head != head:
        return None, (
            f"dispatch mark is for a different tree ({_short(marked_head)} != "
            f"{_short(head)}) — an abandoned run's mark, recorded as not measured"
        ), True
    return stamp, f"measured from a dispatch mark at {stamp}", True


def _short(head: str | None) -> str:
    """A sha for a one-line reason, or a word saying there wasn't one."""
    if not isinstance(head, str) or not head.strip():
        return "no-head"
    return head[:8]
