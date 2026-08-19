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
   stops counting as active (and is swept on the next read).
2. **Session-boundary sweep** — a genuine session boundary (``clear
   --session-start`` *without* ``--brief-only``: only ``startup`` and ``clear``)
   deletes a marker **that has already failed the TTL above**. What licenses
   deleting a marker someone else wrote is that a review is dispatched by a
   process, so the sweep's real question is *is that process gone?*

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
3. **Explicit override** — the refusal message tells the operator/agent how to
   clear a stale marker (``rm``) or force the one command (``clear --force``).

**Failure stance.** A missing, corrupt, or unparseable marker is treated as
*not active* (fail toward availability, not toward blocking) — the override
exists regardless, and a corrupt marker is far more likely junk than a live
review. The freshness signal is the embedded ``started_at`` timestamp when
parseable, falling back to the file's mtime.
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
CRITIC_ACTIVE_TTL_SECONDS = 1800

MARKER_NAME = ".critic-active"


def _marker_path(prawduct_dir: Path) -> Path:
    return prawduct_dir / MARKER_NAME


def write_marker(prawduct_dir: Path) -> bool:
    """Write the critic-active marker with a server-side UTC start timestamp.

    Returns True if written, False if ``prawduct_dir`` does not exist (the
    Critic only runs inside an onboarded repo; outside one this is a no-op).
    Re-writing refreshes the timestamp, so an over-running review can renew its
    own protection.
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

    Never raises on a missing file (the common case after TTL expiry or a
    session-start sweep).
    """
    marker = _marker_path(prawduct_dir)
    try:
        marker.unlink()
        return True
    except FileNotFoundError:
        return False


def sweep_if_expired(prawduct_dir: Path) -> bool:
    """Release the marker **only if** the TTL has already expired. Returns True
    when a marker survived (a review is still plausibly live), False otherwise.

    The session-boundary sweep, named. It delegates to :func:`review_active`,
    whose sweeping default does exactly this — but a bare ``review_active`` call
    at a boundary is a query used as a command, with its result discarded and its
    intent living only in a comment. The reason a boundary may not simply delete
    the marker is in this module's docstring; this function is how the call site
    says which of the two acts it is performing.
    """
    active, _age = review_active(prawduct_dir)
    return active


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


def review_active(prawduct_dir: Path, sweep: bool = True) -> tuple[bool, float | None]:
    """Is a Critic review plausibly in progress right now?

    Returns ``(active, age_seconds)``. ``active`` is True only when the marker
    exists AND its age is within :data:`CRITIC_ACTIVE_TTL_SECONDS`. A
    stale/unreadable marker is swept (best-effort ``unlink``) and reported as
    not active, so a crashed review self-heals on the next check.

    ``sweep=False`` answers the same question WITHOUT unlinking, and exists
    because the sweep is a side effect that not every caller can afford. The
    Stop hook's abandoned-review branch is gated on :func:`marker_present` and
    is the surface that prints the manual-recovery remedy (``rm`` the marker and
    the partials, then waive). A caller that sweeps on the way past therefore
    deletes the signal that would have produced those instructions — so the
    Critic *dispatch* path reads with ``sweep=False``: refusing a dispatch is
    not the moment to also decide a crashed review is over. ``clear``, whose
    whole problem is that a dead marker must not brick it forever, keeps the
    sweeping default.
    """
    marker = _marker_path(prawduct_dir)
    if not marker.is_file():
        return (False, None)
    age = _marker_age_seconds(marker)
    if age is not None and age <= CRITIC_ACTIVE_TTL_SECONDS:
        return (True, age)
    # Stale or unreadable → report not active. Sweeping is the default because a
    # crashed review must not brick `clear`; see the docstring for who opts out.
    if sweep:
        try:
            marker.unlink()
        except OSError:
            pass
    return (False, None)
