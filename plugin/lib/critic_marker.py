"""Critic-active session marker — the CRT-3X9D session-mutation guard.

The Critic is documented as structurally unable to run executables (review by
code analysis only). But the coordinator pattern dispatches review subagents via
the ``Agent`` tool, and Agent-spawned subagents do NOT inherit the Critic skill's
restricted ``allowed-tools`` — they run with the session's default Bash latitude.
During the STH-9V4K ch.7 review a subagent ran ``prawduct-hook clear``, which is
destructive: it archives/deletes ``.session-reflected``, rewrites
``.session-start`` (making fresh test evidence read "stale"), and recaptures the
git baseline. An independent reviewer clobbered the session it was reviewing.

This module enforces the real invariant — *an independent reviewer must not be
able to mutate the session it is reviewing* — at the mutation site rather than
relying on a tool restriction that doesn't hold for subagents.

**Lifecycle.** ``prawduct-hook critic-begin`` writes ``.prawduct/.critic-active``
at the start of a review; ``critic-end`` removes it. Session-mutating ``clear``
consults :func:`review_active` and refuses (with an override) while a review is
plausibly in progress.

**Resilience (the design priority — see CRT-3X9D).** A crashed/hung Critic that
never calls ``critic-end`` must not permanently brick ``clear``. Three
independent corrections, no one of which has to be perfect:

1. **TTL auto-expiry** — a marker older than :data:`CRITIC_ACTIVE_TTL_SECONDS`
   stops counting as active, so it blocks nothing. Expiry is what makes a
   marker *removable*; what actually removes it is (2).
2. **Session-boundary sweep** — a genuine session boundary (``clear
   --session-start`` *without* ``--brief-only``: only ``startup`` and ``clear``)
   deletes a marker that has already failed the TTL above **and whose review
   nothing can still recover**. What licenses deleting a marker someone else
   wrote is that a review is dispatched by a process, so the sweep's first
   question is *is that process gone?*

   Source is only a proxy for that question, and the sweep is scoped twice
   because the proxy leaks in both directions. It does **not** fire on
   continuations (SCN-5B8Q): ``compact`` fires mid-session *in-process* and
   ``fork``'s parent session is frequently still running, so a marker seen there
   is very likely **live**. And at a boundary it is gated on freshness rather
   than fired outright, because ``clear`` discards the transcript *without*
   ending the process — it passes the was-the-transcript-restored test that
   sorts the boundary column, while failing the process-death test this act
   actually needs, so a subagent dispatched before it may still be writing.

   The asymmetry decides every uncertain case, and both halves are worth
   pricing honestly:

   *Sweeping a live marker* is a **silent** governance failure. It disarms this
   guard and the Stop hook's abandoned-review backstop — which does not merely
   block on the marker but **consolidates** a review whose reviewers all
   reported, so a wrongly-swept marker destroys a recovery, not just a signal.

   *Retaining a dead one* is **loud**, and costs more than the TTL below —
   do not state it as TTL-bounded. Two readers hold different liveness
   predicates. ``critic_consolidate.begin_review`` refuses a new dispatch while
   this marker is within the TTL, and that refusal is **not** overridable by
   ``--force``, so a dead-but-fresh marker blocks the next ``/prawduct:critic``
   until it expires. The Stop hook's backstop reads :func:`marker_present`,
   which has **no TTL at all** and so keeps firing past it. Both are recoverable
   by a named command the refusal prints (``critic-end``, ``critic-discard``),
   which is what keeps this the cheaper error — but "at most the TTL" is false
   for the second reader and understates the first.

   The TTL answers only that first question, and answering it is not enough to
   license the delete. A review whose reviewers have **all reported** is one
   deterministic step from being recorded — the Stop hook's backstop runs that
   step itself, keyed on :func:`marker_present` — so removing the marker there
   throws away a finished review's findings to tidy up after a process that
   already did its job. The sweep therefore asks the roster too
   (:func:`boundary_sweep`), and a complete one is retained at any age.
   Announced, not silent: age-plus-complete is precisely the state an operator
   is entitled to hear about, since nothing else in the new session knows a
   review is sitting there consolidated-but-unrecorded.
3. **Explicit override** — the refusal message names the act that ends a review
   (``critic-end``, and what that costs on one whose reviewers all reported) or
   forces the one command (``clear --force``). Not ``rm``: a bare delete does
   the same damage while saying nothing, which is the silence this guard is
   built to remove.

**Failure stance — decided by AGE, not by readability.** A *missing* marker is
not active. A *corrupt or unparseable* one is not therefore dead: the freshness
signal is the embedded ``started_at`` when parseable and **falls back to the
file's mtime**, so a recently-written corrupt marker still counts as active
(protective, and pinned by ``test_corrupt_marker_falls_back_to_mtime``) while an
old one expires like any other. Only when neither signal is readable at all is
the marker treated as not active.

That distinction is load-bearing now that the session-boundary sweep keys on
this predicate (:func:`boundary_sweep`): "corrupt ⇒ swept" would delete a
marker a reviewer had just written and mangled, which is the silent failure the
gate exists to close. The two loud overrides (``--force``, ``rm``) are what keep
the protective direction from bricking anyone.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .core import atomic_write_text

#: A review is considered active only within this window of its start. Critic
#: reviews target 4–10 min (final/cumulative); 30 min protects a slow review
#: while a crashed marker frees within the window. One knob, deliberately
#: generous — over-blocking is recoverable (override); under-protecting is the
#: bug this guards against.
#:
#: **Do not re-price this from the review-duration ledger.** The obvious move —
#: take the distribution of recorded ``duration_seconds`` and set the window
#: above its tail — measures the wrong quantity twice over. That figure is
#: SELF-REPORTED by the reviewing agent, and a coordinator review records the
#: ``max()`` across its reviewers; what this constant governs is marker
#: WALL-CLOCK age, which spans dispatch plus every reviewer plus consolidation
#: plus coordinator turn latency, and is therefore strictly longer than any
#: self-report. A comfortable margin between the two is an artefact of
#: comparing them, not evidence that the window is safe. The derivation is
#: committed at ``.prawduct/research/critic-liveness-2026-08-19/measure.py``
#: (section A) — run it rather than quoting its digits.
#:
#: What makes the number tolerable is that expiry no longer decides alone:
#: :func:`boundary_sweep` retains a marker whose reviewers have all reported,
#: at any age, so a review that outruns this window loses nothing by doing so.
CRITIC_ACTIVE_TTL_SECONDS = 1800

MARKER_NAME = ".critic-active"


def _marker_path(prawduct_dir: Path) -> Path:
    return prawduct_dir / MARKER_NAME


def write_marker(prawduct_dir: Path) -> bool:
    """Write the critic-active marker with a server-side UTC start timestamp.

    Returns True if written, False if ``prawduct_dir`` does not exist (the
    Critic only runs inside an onboarded repo; outside one this is a no-op).

    **Nothing renews a marker mid-review.** ``critic-begin`` is the only caller,
    so the timestamp is a *dispatch* time and the TTL runs from it untouched — a
    review that takes longer than the TTL does not extend its own protection by
    working harder, because no code path re-writes the file while reviewers are
    running. A re-write here is a NEW dispatch, not a renewal, which is why
    ``begin_review`` refuses to reach it while a review is still live. What
    protects an over-running review instead: the marker is kept once its roster
    is complete (:func:`boundary_sweep`), and whichever way it goes, the act
    says so. The single-writer fact is pinned by
    ``test_nothing_renews_a_marker_mid_review`` — a second writer makes the
    paragraph above false.
    """
    if not prawduct_dir.is_dir():
        return False
    # No pid field: this function runs in the short-lived critic-begin hook
    # process, so any pid recorded here is dead by the time a reader checks it —
    # `ps -p <pid>` then reads as "the review died" on every healthy review, and
    # nothing in the framework consumes the field. Liveness is answered by
    # `started_at` age here and per-role started markers in critic_consolidate.
    payload = {
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "critic",
    }
    atomic_write_text(_marker_path(prawduct_dir), json.dumps(payload))
    return True


def clear_marker(prawduct_dir: Path) -> bool:
    """Remove the marker. Idempotent: returns False if it was already absent.

    Never raises on a missing file (the common case after a session-boundary
    release, or after the explicit end/discard acts).
    """
    marker = _marker_path(prawduct_dir)
    try:
        marker.unlink()
        return True
    except FileNotFoundError:
        return False


#: What :func:`boundary_sweep` did — a token, deliberately not a bool.
#:
#: The act has several outcomes and only SOME of them mean "a marker is still
#: there for a reason", so a caller branching on truthiness would announce a
#: retention on the path where there was nothing to retain. One bit cannot say
#: which of these happened, and this is a decision whose branches a caller has
#: to tell apart: an announcement is owed on two of them and forbidden on a
#: third. A call site written against a boolean raises ``AttributeError`` here
#: rather than reading any token as "retained".
SWEEP_ABSENT = "absent"
SWEEP_RETAINED_LIVE = "retained-live"
SWEEP_RETAINED_COMPLETE = "retained-complete"
SWEEP_RETAINED_UNKNOWN = "retained-unknown"
SWEEP_SWEPT = "swept"

#: The tokens on which a marker survives the boundary. Named as a set so a
#: caller asks "was anything kept?" without re-listing the reasons — a new
#: retention reason then reaches every caller by being added here.
SWEEP_RETAINED = frozenset(
    {SWEEP_RETAINED_LIVE, SWEEP_RETAINED_COMPLETE, SWEEP_RETAINED_UNKNOWN}
)


#: Why the roster question could not be answered, when it could not. Set by
#: :func:`_roster_is_complete` and read by whoever announces the retention:
#: "the consolidation lib failed to answer" is not a diagnosis, and on the one
#: path where that lib is genuinely broken the exception is the only thing that
#: says which way. Module state rather than a return value because the token
#: `boundary_sweep` returns is what every caller branches on, and widening that
#: to a tuple would make the common paths carry a field only one of them has.
LAST_ROSTER_ERROR: str | None = None


def _roster_is_complete(prawduct_dir: Path) -> bool | None:
    """Has every reviewer of the pending review reported? ``None`` = unanswerable.

    Three-valued on purpose. "No" and "cannot tell" license different acts here,
    and collapsing them would make an import failure delete a review nobody
    looked at.

    The import is lazy because ``critic_consolidate`` imports THIS module at its
    top — a module-level import back would be a cycle — and because it keeps a
    3000-line module off the session-start path in the overwhelmingly common
    case: the only caller reaches this after establishing that a marker file
    exists at all, which happens only when a review was dispatched and never
    ended. An unreadable manifest is a real answer of "not complete", not an
    unanswerable one; ``pending_state`` already classifies it.
    """
    global LAST_ROSTER_ERROR
    LAST_ROSTER_ERROR = None
    try:
        from . import critic_consolidate  # noqa: PLC0415 — import cycle + hot path, see docstring

        state, _missing = critic_consolidate.pending_state(prawduct_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- an unanswerable roster must not take the boundary down
        LAST_ROSTER_ERROR = f"{type(exc).__name__}: {exc}"
        return None
    return state == "complete"


def boundary_sweep(prawduct_dir: Path) -> str:
    """The session-boundary sweep: release the marker unless its review can
    still be finished. Returns one of the ``SWEEP_*`` tokens above.

    Two conditions retain, and they are different questions:

    * **Live** — inside :data:`CRITIC_ACTIVE_TTL_SECONDS`. The reviewers may
      still be writing; ``clear`` discards a transcript without ending the
      process that dispatched them.
    * **Complete roster** — every reviewer reported, at *any* age. The TTL has
      released the marker as a liveness claim, and deleting it anyway would be
      the expensive direction: the Stop hook's backstop keys on
      :func:`marker_present` and consolidates such a review by itself, so the
      marker is not a stale flag here but the handle on a finished review's
      findings. A review that outruns the TTL is exactly the review that most
      needs recording.

    Anything else is swept — and the caller is told, because this is the branch
    that destroys something. The module docstring prices the asymmetry: sweeping
    is the *silent* failure, so the one thing the sweep may not do is happen
    quietly.

    :func:`review_active` only asks, so the roster question below is always put
    to a marker that is still there. A predicate that deleted while answering
    would decide this function's question before it was asked.
    """
    if not _marker_path(prawduct_dir).is_file():
        return SWEEP_ABSENT
    live, _age = review_active(prawduct_dir)
    if live:
        return SWEEP_RETAINED_LIVE
    complete = _roster_is_complete(prawduct_dir)
    if complete is None:
        # Unanswerable → retain. The module's asymmetry decides it: retaining a
        # dead marker is loud and reversible by a named command, sweeping a
        # recoverable one is silent and costs a whole review round.
        return SWEEP_RETAINED_UNKNOWN
    if complete:
        return SWEEP_RETAINED_COMPLETE
    clear_marker(prawduct_dir)
    return SWEEP_SWEPT


def marker_present(prawduct_dir: Path) -> bool:
    """Is the critic-active marker file present right now? Non-mutating.

    Distinct from :func:`review_active`: this reports raw presence with NO TTL
    and NO sweep. The TTL/sweep in ``review_active`` exist so a crashed review
    can't brick ``clear`` forever — a *liveness* question. This answers a
    different one the Stop hook needs (CRT-9K7T follow-up): *did a review that
    ran ``critic-begin`` ever reach ``critic-end``?* A present marker means it
    did NOT (``critic-end`` always clears first), so steps 7-8 — findings write,
    ledger anchor — likely never landed either. The Stop hook must only INSPECT
    this, never sweep it (that would erase the very signal it blocks on and
    silently mutate the session it is gating), so this stays read-only.
    """
    return _marker_path(prawduct_dir).is_file()


def _marker_age_seconds(marker: Path) -> float | None:
    """Age of the marker in seconds from its embedded ``started_at``, falling
    back to file mtime. Returns None only if neither signal is readable (treated
    as stale by the caller)."""
    now = datetime.now(timezone.utc)
    try:
        data = json.loads(marker.read_text())
        started = datetime.strptime(data["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return (now - started).total_seconds()
    except (OSError, ValueError, KeyError, TypeError):
        # Corrupt/old-format marker — fall back to mtime so a marker without a
        # parseable timestamp still expires rather than blocking forever.
        try:
            mtime = datetime.fromtimestamp(marker.stat().st_mtime, tz=timezone.utc)
            return (now - mtime).total_seconds()
        except OSError:
            return None


def review_active(prawduct_dir: Path) -> tuple[bool, float | None]:
    """Is a Critic review plausibly in progress right now? **Asks only.**

    Returns ``(active, age_seconds)``. ``active`` is True only when the marker
    exists AND its age is within :data:`CRITIC_ACTIVE_TTL_SECONDS`.
    **Unreadable is not the same as stale** — the module docstring's "decided by
    AGE, not by readability" is the rule, and ``_marker_age_seconds`` falls back
    to mtime, so a freshly-written corrupt marker is still ACTIVE.

    **This removes nothing.** Expiry is not sufficient grounds to delete a
    marker — :func:`boundary_sweep` keeps one whose reviewers have all reported
    — so a predicate that unlinked as a side effect of answering would be a
    second, silent home for that decision, reachable by any caller who merely
    wanted to ask, and a bare ``clear`` asking this question would destroy the
    completed review the boundary protects. One function decides whether a
    marker may go (:func:`boundary_sweep`); the explicit acts — ``critic-end``,
    ``critic-discard``, a successful consolidation, ``--force`` — call
    :func:`clear_marker` by name. Asking is free and changes nothing.
    """
    marker = _marker_path(prawduct_dir)
    if not marker.is_file():
        return (False, None)
    age = _marker_age_seconds(marker)
    if age is not None and age <= CRITIC_ACTIVE_TTL_SECONDS:
        return (True, age)
    return (False, None)
