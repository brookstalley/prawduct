"""Migration — the importer, the full-fidelity export, and the minimal merge.

The highest-risk operations in the service, and their exit (API §2.5/§2.3, Data
Model §5/§8). Three concerns, all over the ``transport`` seam (never a model —
INV-1), all **return-value** enveloped (project preference):

1. **`import`** (``import_backlog`` / ``import_items``) — fold a markdown
   ``.prawduct/backlog.md`` (+ archive) into GitHub issues. **Idempotent and
   resumable**, keyed on the permanent ``id:PFX`` alias label (skip-if-exists).
   The alias label is written **atomically in the create** — a crash after the
   create still converges on re-run via the label query, so recovery never
   depends on the crashed process re-running (the claim-atomicity lesson —
   recovery must never hinge on the crashed actor returning — applied here). There is **no rollback**: GitHub never reuses issue
   numbers, so recovery is re-run into the same repo (M6). A durable ``Checkpoint``
   is a fast-path accelerator + audit record, never the correctness key. An
   owner-confirmed MG6 restructure plan (:mod:`restructure`) applies to the
   parsed records *before* the data plane — at create only, never as an edit.

2. **`export`** (``export_backlog``) — a cheap, full-fidelity **dump** to plain
   files: the body block **plus the native graph** (dependencies, sub-issues,
   timeline, assignees). Not a lossless one-liner re-import into a non-GitHub
   backend (out of scope, Data Model §8) — a *backup/inspection* dump (MG2/G5).

3. **`merge`** (``merge``) — the minimal fold A→B the migration scrub needs: a
   **redirect-before-close** so a crash leaves the source open-but-redirected (a
   valid, resolvable state — CRASH-2); nothing is hard-deleted (both bodies
   preserved — DM7). The redirect target is the block-authoritative
   ``superseded_by`` (Data Model §1.2).

The **alias machinery** itself (``id:PFX`` label helpers, redirect-follow) lives
in :mod:`ids` (pure); this module wires it to the transport.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import core, encode, ids, legacy, provision, restructure
from .transport import Transport, TransportError

# The facet metadata keys the importer consumes as `<facet>:value` labels (§3).
# `status` is the status axis (§4). Every *other* metadata key — and an invalid
# `status` value — is preserved verbatim as a block field (the block's additive-
# forever design carries `added`/`reviewed`/`refs`/`related`/… losslessly, so a
# round-trip is byte-faithful — MIG-1, and nothing is silently dropped).
_FACET_META: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")

# The export on-disk layout version (Data Model §8 open-Q5, pinned here). A dump,
# not a queried lock-in schema — re-import into a non-GitHub backend is out of
# scope, so the layout is a build choice bounded only by the NFR §8 fidelity
# contract (body block + native graph). Bumped only on an incompatible layout.
EXPORT_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 1

_STORE_SUBDIR = "prawduct"
_CHECKPOINT_BASENAME = "backlog-import.json"

# The leading ``[PFX]`` marker, stripped from the title (the id lives in the alias).
# Must accept exactly what ``legacy.ID_RE`` accepts, multi-segment ids included: if
# this is narrower, an id it fails to recognize is parsed and aliased upstream but
# left embedded in the title, so the issue reads ``[MIG-M4-REMOVE] Remove the shim``.
_ID_MARKER_RE = re.compile(r"^\s*\[[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\]\s*")


def _diag(message: str) -> None:
    print(f"backlog: {message}", file=sys.stderr)


# Records between progress lines. Count-based rather than time-based so the
# output is deterministic and testable without injecting a clock; at the serial
# `gh` rate VRF-009 measured (~40-45 records/min) this lands roughly every
# 30-40 seconds, which is the cadence the signal is for.
PROGRESS_EVERY = 25


def _emit_progress(done: int, total: int, created: int, skipped: int, collisions: int) -> None:
    """Periodic "still alive, and here is where" during a long import.

    **Distinct from the pacing announcements, deliberately.** Those are
    *exception* reporting — they fire only when a budget binds, and
    ``test_an_unthrottled_run_stays_quiet`` exists to keep them that way,
    because a line per call buries the one message that matters. But VRF-009
    settled that under the serial importer no budget ever binds
    (``rest_point_waits: 0`` **and** ``content_creation_waits: 0``), so on a
    healthy ~900-issue run every one of those paths stays silent for 18-40
    minutes. Progress answers a different question — *is it moving* — and an
    operator with no answer to that is an operator who kills a healthy run
    mid-migration, which for an irreversible bulk write is the expensive
    mistake.

    Emits on **stderr**: `--json` stdout is a machine contract (SEC-1 /
    VRF-004) and a progress line on it would break every caller. Silent for
    runs shorter than one interval — below that there is nothing to reassure
    anyone about, and a line would be the commentary the sibling guard forbids.
    """
    # `done >= total` suppresses a beat on the final record: the run summary and
    # the pacing footer print immediately after, so a heartbeat there would be
    # duplicate noise at the one moment the operator is already being told.
    if done % PROGRESS_EVERY or done >= total:
        return
    tail = f", {collisions} collision(s)" if collisions else ""
    _diag(f"migrating: {done}/{total} — {created} created, {skipped} skipped{tail}")


def run_key(
    content: str, archive_content: str | None = None, plan_text: str | None = None
) -> str:
    """A stable digest of the import *source* (+ any restructure plan), so a
    resume of the same backlog shares its checkpoint entry while a different
    source — or a different confirmed plan — starts fresh (the checkpoint is
    keyed by ``(scope, run_key)``; the skip authority stays the on-GitHub
    alias, so a fresh key only costs re-verification, never duplicates)."""
    payload = (
        (content or "") + "\x00" + (archive_content or "") + "\x00" + (plan_text or "")
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# --- write-pacing (NFR §3/§9 — the content-creation and REST-points budgets) --

# GitHub's per-request REST-point costs for the 900-pts/min secondary rate limit
# (docs.github.com "Rate limits for the REST API", verified 2026-07-24): a write
# (POST/PATCH/PUT/DELETE) is 5 points, a read (GET/HEAD/OPTIONS) is 1.
_REST_WRITE_POINTS = 5
_REST_READ_POINTS = 1


class Pacer:
    """Proactive write-pacing for a migration run, holding it under **both** of
    GitHub's secondary rate limits:

    1. **Content creation** (NFR §3) — issue/comment *creation* is the scarce
       budget: **80/min and 500/hr** (exact caps). ``import`` creates one issue per
       item, so a pure-``open`` run is content-bound and paces across the clock via
       :meth:`before_create` (317 creates ≈ 40 min at the cap — NFR §3.3).
    2. **REST points** (NFR §9) — reads *and* writes both spend the **900 points/min**
       REST burst: 5 points per write, 1 per read (constants above). :meth:`before_points`
       meters this budget; the :class:`_PacingTransport` decorator charges every
       transport **method** call, so reads **and** writes both count. The charge is per
       method, not per HTTP request — a paged read is charged once — so the metered
       total is a **floor** (BKL-3H7W).

    For a *pure-create* workload the content cap binds first (80 creates/min × 5 pts
    = 400 pts/min < 900), which is why creation was the only budget modelled
    originally. But ``--archive-scope all`` imports each archived item as a **create
    *and* a close** (2 writes + the reconcile reads), so at the content cap the
    archive stretch would spend ≈ 80×5 (creates) + 80×5 (closes) + reads > 900
    pts/min — the REST-points budget binds there, and metering only the create would
    breach it (BKL-6X5D part b). Both budgets are enforced together; the effective
    rate is whichever binds.

    Deterministic and injectable: ``now()`` (a monotonic clock) and ``sleep(s)``
    are seams, so the L1 suite runs instantly (small fixtures never hit a cap) and
    the PROBE-RATE tests assert the pacing *decisions* without wall-clock waits.
    Conservative defaults until S2/S3 measure the real constants (NFR §3.5/§9)."""

    def __init__(
        self,
        *,
        per_minute: int = 80,
        per_hour: int = 500,
        per_minute_points: int = 900,
        now=None,
        sleep=None,
    ) -> None:
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_minute_points = per_minute_points
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._events: "deque[float]" = deque()  # creation timestamps (monotonic)
        self._point_events: "deque[tuple[float, int]]" = deque()  # (timestamp, cost)
        self.waits = 0
        self.total_waited = 0.0
        self.point_waits = 0
        self.total_point_waited = 0.0
        self.points_charged = 0  # total REST points this run has spent (run summary)

    def before_create(self) -> None:
        """Block (only if a cap is hit) until a *content-creation* slot is free, then
        record the creation. A no-op while under both the 80/min and 500/hr caps —
        the common case. (The create's REST-point cost is metered separately, at the
        transport, by :meth:`before_points`.)"""
        wait = self._required_wait()
        if wait > 0:
            # Announce BEFORE sleeping. A silent block is indistinguishable from a
            # wedged process, and on the irreversible migration the operator's only
            # alternative reading is "kill it" — the one response that turns a
            # self-resolving pause into a half-done import (BKL-8K2N).
            _diag(
                f"paced: content-creation budget reached "
                f"({self.per_minute}/min, {self.per_hour}/hr) — resuming in {wait:.0f}s"
            )
            self._sleep(wait)
            self.waits += 1
            self.total_waited += wait
        self._events.append(self._now())

    def _required_wait(self) -> float:
        now = self._now()
        while self._events and now - self._events[0] > 3600:
            self._events.popleft()  # prune anything older than the hour window
        waits = [0.0]
        minute_events = [t for t in self._events if now - t <= 60]
        if len(minute_events) >= self.per_minute:
            # Wait just past the oldest in-window creation so one minute-slot frees.
            waits.append(60 - (now - minute_events[0]))
        if len(self._events) >= self.per_hour:
            waits.append(3600 - (now - self._events[0]))
        return max(waits)

    def before_points(self, cost: int) -> None:
        """Block (only if the 900-pts/min REST burst would be breached) until ``cost``
        points of headroom free in the trailing minute, then record the spend. A
        no-op while the window has room — the common case. Called by
        :class:`_PacingTransport` for every transport **method** call (write = 5, read =
        1), so the create-then-close archive stretch stays inside the burst ceiling —
        not just the create (BKL-6X5D part b). Per method, not per HTTP request — a
        paged read is charged once — so ``points_charged`` is a floor (BKL-3H7W)."""
        wait = self._required_points_wait(cost)
        if wait > 0:
            # See before_create: announce before blocking (BKL-8K2N).
            _diag(
                f"paced: rest-point budget reached ({self.per_minute_points} pts/min; "
                f"{self.points_charged} charged so far) — resuming in {wait:.0f}s"
            )
            self._sleep(wait)
            self.point_waits += 1
            self.total_point_waited += wait
        self._point_events.append((self._now(), cost))
        self.points_charged += cost

    def _required_points_wait(self, cost: int) -> float:
        now = self._now()
        while self._point_events and now - self._point_events[0][0] > 60:
            self._point_events.popleft()  # prune anything older than the minute window
        used = sum(c for _, c in self._point_events)
        if used + cost <= self.per_minute_points:
            return 0.0
        # Free (used + cost - ceiling) points: the oldest in-window spends age out of
        # the 60s window first, so wait just past the newest spend we must shed.
        need_to_free = used + cost - self.per_minute_points
        freed = 0
        wait = 0.0
        for ts, spent in self._point_events:
            freed += spent
            wait = 60 - (now - ts)
            if freed >= need_to_free:
                break
        return max(0.0, wait)


class RateLimitBackoff:
    """**Reactive** secondary-rate-limit handling for the irreversible import
    (BKL-3K9N) — the counterpart to the Pacer's **proactive** pacing.

    The Pacer keeps a well-behaved run *under* the content-creation caps, but a
    shared token (the migration reads through the same identity the briefing/gates
    use) can still trip a secondary 429. Without this, a mid-import 429 hard-stops
    into a resumable error, and recovery is a fresh top-level re-run that re-hits the
    still-unelapsed secondary window. Instead, on a ``rate_limited`` failure we
    **pause and retry the same record in the same run** — honoring a server
    ``Retry-After`` when the transport surfaced one (``details['retry_after']``),
    else a bounded exponential backoff. Every import step is idempotent
    (find-or-create skips, reconcile-status converges), so replaying a record after
    the pause never duplicates.

    **Bounded** — after ``max_retries`` the failure propagates and ``import_items``
    returns its resumable envelope, so the never-block ceiling holds: a *persistent*
    rate limit stops the run cleanly rather than spinning forever. Deterministic and
    injectable (``sleep`` is a seam) so the L1 suite asserts the pause *decisions*
    with no wall-clock wait.
    """

    def __init__(
        self,
        *,
        max_retries: int = 5,
        base_seconds: float = 2.0,
        max_seconds: float = 60.0,
        sleep=None,
    ) -> None:
        self.max_retries = max_retries
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds
        self._sleep = sleep or time.sleep
        self.pauses = 0
        self.total_paused = 0.0

    def wait_seconds(self, attempt: int, details: dict | None = None) -> float:
        """The pause before retry ``attempt`` (0-based): a server ``retry_after`` when
        present, else exponential backoff (``base * 2**attempt``) — both floored at 0
        and capped at ``max_seconds`` (so a hostile/huge Retry-After can't hang)."""
        retry_after = _coerce_seconds((details or {}).get("retry_after"))
        chosen = retry_after if retry_after is not None else self.base_seconds * (2 ** attempt)
        return max(0.0, min(chosen, self.max_seconds))

    def pause(self, attempt: int, details: dict | None = None) -> None:
        wait = self.wait_seconds(attempt, details)
        # A REACTIVE pause means GitHub already pushed back — strictly more alarming
        # than the Pacer's proactive waits, and the one an operator most needs to see
        # rather than infer from a stalled terminal (BKL-8K2N). Name the server's
        # Retry-After when it gave one, so "why this long?" is answered in the line.
        served = _coerce_seconds((details or {}).get("retry_after"))
        because = (
            f"server Retry-After: {served:.0f}s"
            if served is not None
            else "exponential backoff"
        )
        _diag(
            f"rate-limited by GitHub — pausing {wait:.0f}s before retry "
            f"{attempt + 1}/{self.max_retries} ({because})"
        )
        self._sleep(wait)
        self.pauses += 1
        self.total_paused += wait


def pacing_summary(pacer: "Pacer", backoff: "RateLimitBackoff") -> dict:
    """The run's pacing telemetry, for the import envelope (BKL-8K2N).

    ``import_items`` has always *constructed* a Pacer, so the run was paced — but
    the counters were never surfaced, and the SPIKE-S2 harness was the only reader
    in the tree. That left the operator of an irreversible ~900-issue migration
    unable to answer "was I throttled, and where did the budget stand?" after the
    fact. This is that answer, and it rides **every** exit path — success and both
    resumable cuts — because a run that stopped is exactly when the question gets
    asked.

    Names match the SPIKE-S2 recorded-facts vocabulary so a dry-run and a real run
    are read side by side without a translation step.
    """
    return {
        "rest_points_charged": pacer.points_charged,
        "rest_point_waits": pacer.point_waits,
        "rest_point_wait_seconds": round(pacer.total_point_waited, 3),
        "content_creation_waits": pacer.waits,
        "content_creation_wait_seconds": round(pacer.total_waited, 3),
        "rate_limit_pauses": backoff.pauses,
        "rate_limit_paused_seconds": round(backoff.total_paused, 3),
        "budgets": {
            "per_minute_creates": pacer.per_minute,
            "per_hour_creates": pacer.per_hour,
            "per_minute_points": pacer.per_minute_points,
        },
    }


def _coerce_seconds(value) -> float | None:
    """A Retry-After value (str or number) as a non-negative float, or ``None`` if
    it is absent/unparseable (→ the caller's exponential backoff)."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class _PacingTransport:
    """A transparent :class:`~lib.backlog.transport.Transport` decorator that meters
    **every transport METHOD call** routed **through it** against the Pacer's
    900-pts/min budget (:meth:`Pacer.before_points`): 5 points per write, 1 per read.

    The charge is per **method**, not per HTTP request. A paged read (``list_labels``
    can issue several requests) is charged once, so the metered total is a **floor**,
    not an exact REST-call count — which is why the operator surface prints ``≥N``
    (BKL-3H7W). Say "every REST call" and the figure reads as exact to the one person
    sizing an irreversible run; drop the qualifier only when BKL-3H7W makes it true.

    Installed on the ``import`` path (:func:`import_items`), whose create-then-close
    archive stretch is the write burst BKL-6X5D part (b) targets; ``merge``/``export``
    are separate, non-bursting ops and use the raw transport.

    Deliberately **not** a ``Transport`` subclass. ``__getattr__`` only fires for
    attributes the instance/class does *not* already define — so proxying via
    ``__getattr__`` requires that the wrapped methods be absent here. That is also
    what makes the metering **non-fragile**: a call is metered by classifying its
    *name* (``get_``/``list_`` = read, ``create_``/``update_``/``add_``/``remove_`` =
    write), and any transport method that fits neither prefix raises rather than
    silently escaping the budget — closing the "only paced call" gap (BKL-6X5D b).

    Because the migration passes *this* wrapper into ``core.set_status`` (the shared
    close/reconcile path), that path's reads and the close write are metered too,
    with no change to ``core``'s signatures."""

    _READ_PREFIXES = ("get_", "list_")
    _WRITE_PREFIXES = ("create_", "update_", "add_", "remove_")

    def __init__(self, transport: Transport, pacer: "Pacer") -> None:
        self._transport = transport
        self._pacer = pacer

    def _cost(self, name: str) -> int:
        if name.startswith(self._READ_PREFIXES):
            return _REST_READ_POINTS
        if name.startswith(self._WRITE_PREFIXES):
            return _REST_WRITE_POINTS
        raise AssertionError(
            f"_PacingTransport: unclassified transport method {name!r} — classify it "
            "as read/write so its REST-point cost is metered (do not bypass the budget)"
        )

    def __getattr__(self, name: str):
        attr = getattr(self._transport, name)
        if name.startswith("_") or not callable(attr):
            return attr
        cost = self._cost(name)

        def paced(*args, **kwargs):
            self._pacer.before_points(cost)
            return attr(*args, **kwargs)

        return paced


# --- durable checkpoint (resumable import accelerator) -----------------------


def checkpoint_path(project_dir: Path) -> Path | None:
    """The clone-shared import-checkpoint path, or ``None`` outside a git repo.

    ``<git-common-dir>/prawduct/backlog-import.json`` — the same clone-shared,
    never-committed home the counts snapshot and evidence store use (mirrors
    ``snapshot.snapshot_path``)."""
    from .. import gitstate  # noqa: PLC0415 — lazy: only the resolver needs git

    common = gitstate.git_common_dir(project_dir)
    if common is None:
        return None
    return common / _STORE_SUBDIR / _CHECKPOINT_BASENAME


class Checkpoint:
    """A durable, resumable import **progress/audit record** — never a skip authority.

    The authoritative idempotency key is the on-GitHub ``id:PFX`` / ``import-key:``
    label written atomically in the create; ``import_items`` skips **only** on that
    live query, so a lost/corrupt/stale checkpoint can neither duplicate an item
    (the query finds it) nor lose one (the query re-creates it). This file just
    records which keys a run reached — a durable, cross-session progress log
    (``is_done`` is a read for reporting, not control flow). Keyed by ``(scope,
    run_key)`` so two different imports never cross-contaminate. JSON, schema-
    versioned, disposable (mirrors ``snapshot.py``); errors degrade to a warning,
    never raise. ``path=None`` is a valid in-memory record."""

    def __init__(self, path: Path | None, scope: str, run_key: str) -> None:
        self.path = path
        self.scope = scope
        self.run_key = run_key
        self.warnings: list[str] = []
        self._done: set[str] = self._load()

    def is_done(self, key: str) -> bool:
        """Whether this run has recorded ``key`` as reached — a **progress read**
        (reporting / a resumed run's summary), not a skip authority."""
        return key in self._done

    def mark(self, key: str) -> None:
        if key in self._done:
            return
        self._done.add(key)
        self._flush()

    def _entry_key(self) -> str:
        return f"{self.scope}\n{self.run_key}"

    def _load(self) -> set[str]:
        if self.path is None:
            return set()
        try:
            raw = self.path.read_text()
        except FileNotFoundError:
            return set()
        except OSError as exc:
            self.warnings.append(f"import checkpoint unreadable ({type(exc).__name__}); starting fresh")
            return set()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.warnings.append("import checkpoint unparseable; starting fresh (checkpoint is disposable)")
            return set()
        if not isinstance(data, dict) or data.get("schema") != CHECKPOINT_SCHEMA_VERSION:
            return set()
        runs = data.get("runs")
        entry = runs.get(self._entry_key()) if isinstance(runs, dict) else None
        done = entry.get("done") if isinstance(entry, dict) else None
        return set(done) if isinstance(done, list) else set()

    def _flush(self) -> None:
        if self.path is None:
            return
        data = {"schema": CHECKPOINT_SCHEMA_VERSION, "runs": {}}
        try:
            existing = json.loads(self.path.read_text())
            if isinstance(existing, dict) and existing.get("schema") == CHECKPOINT_SCHEMA_VERSION:
                runs = existing.get("runs")
                if isinstance(runs, dict):
                    data["runs"] = runs
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        data["runs"][self._entry_key()] = {
            "done": sorted(self._done),
            "updated_at": _iso(datetime.now(timezone.utc)),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=self.path.name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as handle:
                    json.dump(data, handle)
                os.replace(tmp, self.path)  # atomic — a torn checkpoint is impossible
            finally:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
        except OSError as exc:
            self.warnings.append(f"import checkpoint not persisted ({type(exc).__name__})")


# --- import records (the primitive `import_items` consumes) ------------------


class ImportRecord:
    """One item to import — the **structured primitive** the deterministic import
    consumes. The migration scrub hands ``import_items`` a list of these (a concrete
    cleaned set), never a model call or a file format (MIG-5): parsing markdown into
    records is a separate, upstream step (``_records_from_backlog``)."""

    __slots__ = ("pfx", "title", "body", "status", "labels", "block")

    def __init__(
        self,
        *,
        pfx: str | None,
        title: str,
        body: str,
        status: str,
        labels: list[str],
        block: dict,
    ) -> None:
        self.pfx = pfx
        self.title = title
        self.body = body
        self.status = status
        self.labels = labels
        self.block = block

    def key_label(self) -> str:
        """The label the importer keys idempotency on. A hand-minted ``PFX`` → the
        **permanent** ``id:PFX`` alias (identity + key at once). No PFX → an
        ``import-key:<digest>`` marker (idempotency-only, **never** an identity —
        Data Model §5), so an id-less item is still resumable/non-duplicating."""
        if self.pfx:
            return ids.alias_label(self.pfx)
        digest = hashlib.sha256(f"{self.title}\n{self.body}".encode()).hexdigest()[:12]
        return f"import-key:{digest}"


def _records_from_backlog(
    content: str, seen_pfx: dict[str, str] | None = None
) -> tuple[list[ImportRecord], list[dict]]:
    """Parse ``.prawduct/backlog.md`` markdown into import records, flagging
    **duplicate-PFX collisions** (two source items claiming one alias — an
    alias-uniqueness violation, §5/MIG-2). Returns ``(records, collisions)``; a
    collided item is dropped from ``records`` and reported, never silently merged.

    ``seen_pfx`` (pfx → first title) is shared across a multi-file import (main +
    ``--archive``) so a PFX appearing in **both** files is caught as a cross-file
    collision, not silently skipped at the transport by the alias-uniqueness query."""
    parsed = legacy.parse_backlog(content)
    records: list[ImportRecord] = []
    collisions: list[dict] = []
    if seen_pfx is None:
        seen_pfx = {}  # pfx -> first title that claimed it
    for item in parsed.items:
        if item.struck or not item.title:
            continue  # a struck/empty bullet is not an item (mirrors legacy pending)
        pfx = item.item_id if ids.is_pfx(item.item_id) else None
        if pfx is not None and pfx in seen_pfx:
            collisions.append({"pfx": pfx, "title": item.title, "first": seen_pfx[pfx]})
            continue
        if pfx is not None:
            seen_pfx[pfx] = item.title
        records.append(_record_from_item(item, pfx))
    return records, collisions


def _record_from_item(item: legacy.BacklogItem, pfx: str | None) -> ImportRecord:
    """Map one parsed backlog item to an :class:`ImportRecord` (the label/status/
    block split). The ``[PFX]`` marker is stripped from the title (the PFX lives in
    the alias); every non-consumed metadata key is preserved verbatim in the block."""
    title = _ID_MARKER_RE.sub("", item.title).strip()
    status = _target_status(item)
    labels = _labels_for(item, status)
    block = _block_for(item, pfx)
    return ImportRecord(pfx=pfx, title=title, body=item.body, status=status, labels=labels, block=block)


def _target_status(item: legacy.BacklogItem) -> str:
    """The two-axis status *target* for an imported item: the explicit ``status:``
    metadata when it is a valid status, else inferred from the section (``## Archive``
    → closed). An unknown status value does not drive the axis (a bogus status is
    never applied), but it is **preserved verbatim in the block** (``_block_for``) so
    nothing is silently dropped — the migration scrub can see it."""
    meta_status = (item.metadata.get("status") or "").strip()
    if meta_status in encode.STATUS_VALUES:
        return meta_status
    if _is_archived(item.section):
        return "dropped"  # a closed archive item with no valid status decodes as dropped
    return "open"


def _is_archived(section: str) -> bool:
    lower = (section or "").lower()
    return any(word in lower for word in legacy.RESOLVED_SECTION_WORDS)


def _labels_for(item: legacy.BacklogItem, status: str) -> list[str]:
    """The facet labels + the open sub-state ``status:`` label an imported item
    carries at create time (closed states carry none — Data Model §4)."""
    labels: list[str] = []
    for facet in _FACET_META:
        value = (item.metadata.get(facet) or "").strip()
        if value:
            labels.append(f"{facet}:{value}")
    sub_label = encode.canonical_status_label(status)  # only submitted/in-progress
    if sub_label:
        labels.append(sub_label)
    return labels


def _block_for(item: legacy.BacklogItem, pfx: str | None) -> dict:
    """The ``prawduct:`` block for an imported item: ``v:1`` + the ``id_aliases``
    round-trip record + every metadata key not consumed as a label/status,
    preserved verbatim (the block's additive-forever design carries them losslessly
    — MIG-1 metadata fidelity)."""
    block: dict = {"v": "1"}
    if pfx:
        block["id_aliases"] = encode.format_list([pfx])
    for key, value in item.metadata.items():
        if key in _FACET_META:
            continue  # consumed as a `<facet>:value` label
        if key == "status" and value.strip() in encode.STATUS_VALUES:
            continue  # consumed as the status axis (an *invalid* status is preserved)
        block[key] = value
    return block


# --- import ------------------------------------------------------------------


def collect_records(
    content: str, archive_content: str | None = None
) -> tuple[list[ImportRecord], list[dict]]:
    """Parse the import source(s) into ``(records, collisions)`` — the shared
    upstream step for both :func:`import_backlog` and the MG6
    ``restructure-preview`` (which must see byte-for-byte the records the import
    will consume)."""
    seen_pfx: dict[str, str] = {}  # shared across both files → cross-file collisions
    records, collisions = _records_from_backlog(content, seen_pfx)
    if archive_content:
        arc_records, arc_collisions = _records_from_backlog(archive_content, seen_pfx)
        records.extend(arc_records)
        collisions.extend(arc_collisions)
    return records, collisions


# The owner-confirmed archive-scope lever (MG4b), surfaced at scrub time and
# applied by the deterministic importer — a data-plane lever, never a model call.
ARCHIVE_SCOPES: tuple[str, ...] = ("all", "open")


def apply_archive_scope(
    records: list[ImportRecord], archive_scope: str
) -> tuple[list[ImportRecord], int]:
    """Filter ``records`` per the owner's ``--archive-scope`` choice (MG4b).

    - ``all`` (default): import everything, minting a closed issue per archived /
      already-shipped item — the pre-scrub behavior.
    - ``open``: import only the **live/open set**; every record that would be
      created *already closed* (an item whose target status is not an open status —
      archive-section items, explicitly ``dropped``/``shipped`` ones, the whole
      separate ``--archive`` file) is skipped. The skipped items are **not lost**:
      they stay in the **git-tracked source markdown**, which is the migration
      runbook's pre-migration backup — that is the whole point, keeping the
      historical archive in the source file rather than minting a closed issue
      per ancient item.

      They are, however, **outside the migrated tracker**, and that is the
      tradeoff an operator is owed before choosing ``open``: once the product
      cuts over (``backlog_service_repo`` set), the backlog skill treats the
      source markdown as frozen history and does not read it, so ``list`` and
      add-time dedup silently omit the skipped set. (Say ``list``, not
      ``find`` — post-cutover full-text ``find`` is W2-deferred for *every*
      item, so it is not what archive scope costs you.)

      Backfilling later is possible — a re-run under ``all`` is alias-keyed and
      creates no duplicates — but it is **not side-effect free**: the skip path
      still calls :func:`_reconcile_status`, so every already-migrated item is
      driven back to its *markdown* status, reopening anything closed on the
      service since cutover. Do not advertise the re-run as a clean undo.

      Do **not** describe the skipped set as living in the MG2 export:
      :func:`export_backlog` dumps the *migrated repo*, so it runs after the
      import and by construction cannot contain what this filter excluded.

    This lever reduces total write **volume**; it does not enforce the write
    **rate**. The rate ceiling is held by :class:`Pacer`, which paces creates
    across time to stay under the caps whatever the volume — so ``all`` is not
    rate-unsafe, merely slower and noisier. Crediting the archive lever as the
    rate-budget keeper is a known mis-attribution (NF3); do not reintroduce it
    here. Volume still matters for a second reason the Pacer does not cover:
    archived items cost *two* writes each (create-then-close), because the create
    path has no initial-state field.

    Returns ``(kept, skipped_count)``. Pure — no I/O, no model.
    """
    if archive_scope == "open":
        kept = [r for r in records if r.status in encode.OPEN_STATUSES]
        return kept, len(records) - len(kept)
    return records, 0


def import_backlog(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    content: str,
    archive_content: str | None = None,
    plan: dict | None = None,
    archive_scope: str = "all",
    checkpoint: Checkpoint | None = None,
    pacer: Pacer | None = None,
    backoff: RateLimitBackoff | None = None,
) -> dict:
    """Import a ``.prawduct/backlog.md`` (+ optional separate archive file) into
    ``owner/repo``'s issues. Parses markdown into records (flagging duplicate-PFX
    collisions), applies the owner-confirmed ``archive_scope`` lever (MG4b — ``all``
    imports everything, ``open`` skips items that would be created closed), applies
    an optional owner-confirmed restructure ``plan`` (MG6 — validated fail-closed
    *before* anything is written), then runs the deterministic :func:`import_items`.
    Resumable/idempotent (MG1/CRASH-4). The plan applies at create only, so an item
    already on GitHub never has its **title or body** rewritten — but "skipped" is
    not "untouched": the skip branch still reconciles the **status** axis
    (:func:`_reconcile_status`), which is what makes a created-but-crashed-before-close
    item converge on resume (CRASH-4). The consequence beyond resume: a re-run drives
    every already-migrated item back to its *markdown* status, so re-importing to
    backfill an ``open``-scoped migration will reopen anything closed on the service
    since cutover."""
    records, collisions = collect_records(content, archive_content)
    records, archive_skipped = apply_archive_scope(records, archive_scope)
    plan_warnings: list[str] = []
    restructured = 0
    if plan is not None:
        applied = restructure.apply(records, plan)
        if not applied["ok"]:
            return core.error("validation", applied["error"])
        records = applied["records"]
        plan_warnings = applied["warnings"]
        restructured = len(applied["entries"])
    result = import_items(
        transport,
        owner=owner,
        repo=repo,
        records=records,
        collisions=collisions,
        checkpoint=checkpoint,
        pacer=pacer,
        backoff=backoff,
    )
    if result.get("status") == "ok":
        if plan is not None:
            result["data"]["restructured"] = restructured
            result["warnings"] = plan_warnings + result["warnings"]
        if archive_skipped:
            result["data"]["archive_skipped"] = archive_skipped
            result["warnings"] = [
                f"--archive-scope open: {archive_skipped} closed/archived item(s) not "
                "imported as issues (they remain in the git-tracked source markdown, "
                "not in the migrated tracker — post-cutover they are outside list and "
                "add-time dedup; backfilling is possible but re-syncs every item's "
                "status from the markdown, so see the migration-scrub runbook's "
                "`--archive-scope open` backfill guidance under \"Owner confirms\")"
            ] + result["warnings"]
    return result


def import_items(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    records: list[ImportRecord],
    collisions: list[dict] | None = None,
    checkpoint: Checkpoint | None = None,
    pacer: Pacer | None = None,
    backoff: RateLimitBackoff | None = None,
) -> dict:
    """Deterministically import a concrete set of records (MIG-5: no model in the
    data plane). For each record: **find-or-create** by its key label (skip-if-
    exists — idempotent/resumable), then **reconcile status** (idempotent
    ``set-status``, so a resumed item created-but-not-closed converges). The key
    label is written **in the create**, so a crash after the create still skips on
    re-run. Creation is paced (content budget); a mid-run secondary rate limit is
    **paused-and-retried in the same run** (``backoff`` — BKL-3K9N) rather than
    hard-stopping into a fresh re-run that re-hits the unelapsed window. Returns an
    envelope; on a non-rate-limit failure (or an exhausted rate-limit budget) it
    returns a **resumable** error carrying the progress so far — a re-run completes
    the rest (no rollback, M6).

    A status reconcile that fails for a *non*-rate-limit reason does not abort the
    run (:func:`_reconcile_status` explains why the two budgets are treated
    differently); it lands in ``status_unreconciled`` — carried in ``data`` on
    success and in ``error.details`` on either resumable cut, because a deferral
    accrued before a cut is no more recoverable than the audit warnings beside it.
    Every entry there is an item that exists on the target at the **wrong status**,
    which is a thing only ``verify-migration`` can turn into a hard stop."""
    pacer = pacer or Pacer()
    backoff = backoff or RateLimitBackoff()
    # Meter every downstream transport METHOD call against the 900-pts/min budget
    # (a floor, not an exact REST count — see _PacingTransport). Wrapping the
    # transport here means the create, the reconcile reads, and the close write (via
    # core.set_status, which receives this wrapper) all count — not just the create.
    transport = _PacingTransport(transport, pacer)
    collisions = list(collisions or [])
    created: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []
    unreconciled: list[dict] = []
    if checkpoint is not None:
        warnings.extend(checkpoint.warnings)

    alias_index = _AliasIndex(transport, owner, repo)
    total = len(records)
    try:
        for index, record in enumerate(records):
            # The whole (idempotent) record is retried on a rate-limit pause, so a
            # partial attempt never double-counts: outcomes are applied here, once,
            # only after the record fully lands.
            outcome = _import_one_with_retry(
                transport, owner, repo, record, pacer, alias_index, backoff, warnings,
                unreconciled,
            )
            if outcome["outcome"] == "collision":
                collisions.append(outcome["collision"])
            else:
                (created if outcome["outcome"] == "created" else skipped).append(outcome["entry"])
                if checkpoint is not None:
                    checkpoint.mark(outcome["entry"]["key"])
            # Ticks on EVERY record, collisions included — the heartbeat answers
            # "is it moving", and a collision-heavy stretch is exactly when a
            # silent gap would read as a hang. (An earlier shape `continue`d past
            # this and dropped a beat per collision.)
            _emit_progress(index + 1, total, len(created), len(skipped), len(collisions))
    except TransportError as exc:
        result = core.from_transport_error(exc)
        result["error"]["details"].update(
            {
                "created": created,
                "skipped": skipped,
                "collisions": collisions,
                "status_unreconciled": unreconciled,
                "resumable": True,
                "pacing": pacing_summary(pacer, backoff),
            }
        )
        # Carry the audit warnings accrued before the cut (checkpoint notes + per-record
        # self-heal lines). A self-heal line from an already-completed record can't be
        # re-emitted on resume — the restored label makes the record skip the fast path,
        # never re-running the heal — so dropping it here loses it permanently.
        result["warnings"] = warnings
        return result
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6 — unexpected boundary
        _diag(f"unexpected transport failure on import: {type(exc).__name__}")
        # Same contract as the TransportError cut above, for the same reasons: an
        # unexpected boundary failure is no less resumable, and the accrued audit
        # warnings are no less unrecoverable — a self-heal line from an already-
        # completed record never re-emits on resume, so dropping it here loses it
        # permanently. Returning a bare error also contradicted this function's
        # own docstring, which promises the resumable envelope.
        result = core.error(
            "unavailable",
            "the import backend request failed unexpectedly",
            details={
                "created": created,
                "skipped": skipped,
                "collisions": collisions,
                "status_unreconciled": unreconciled,
                "resumable": True,
                "pacing": pacing_summary(pacer, backoff),
            },
        )
        result["warnings"] = warnings
        return result

    for collision in collisions:
        warnings.append(f"alias collision skipped: {collision}")
    if unreconciled:
        # A count, not just the per-item audit lines above it: those scroll past in a
        # 900-item run, and the difference between "imported" and "imported AND at its
        # target status" is exactly what a green completeness gate used to hide.
        # `verify-migration` is the authority that turns this into a hard stop.
        warnings.append(
            f"{len(unreconciled)} item(s) imported but NOT reconciled to their target "
            "status — re-run the import to converge them, then verify-migration"
        )
    data = {
        "repo": f"{owner}/{repo}",
        "created": created,
        "skipped": skipped,
        "collisions": collisions,
        "status_unreconciled": unreconciled,
        "total_source": len(records),
        "pacing": pacing_summary(pacer, backoff),
    }
    return core.ok(data, warnings)


def _import_one_with_retry(
    transport: Transport,
    owner: str,
    repo: str,
    record: ImportRecord,
    pacer: Pacer,
    alias_index: "_AliasIndex",
    backoff: RateLimitBackoff,
    warnings: list[str],
    unreconciled: list[dict],
) -> dict:
    """Import ONE record, **pausing-and-retrying the whole idempotent record** on a
    ``rate_limited`` failure (bounded by ``backoff.max_retries``). Any other failure —
    or an exhausted rate-limit budget — propagates to ``import_items``' resumable
    handler. The successful attempt's warnings merge into ``warnings`` exactly once;
    a retried attempt's partial warnings are discarded, never doubled (BKL-3K9N).
    ``unreconciled`` accrues the same way and for the same reason: a status reconcile
    deferred on one attempt and completed by the retry must not still be reported as
    deferred.

    One reporting consequence of replaying the *whole* record: when the 429 lands on
    the **close**, the create has already succeeded, so the replay's find-or-create
    takes the skip branch and the record is reported ``skipped`` rather than
    ``created``. The counts describe what each successful attempt found, and they
    still sum to the source total; a run whose close stretch was rate-limited will
    simply attribute those items to ``skipped``."""
    attempt = 0
    while True:
        try:
            outcome = _import_one_record(
                transport, owner, repo, record, pacer, alias_index, warnings
            )
            warnings.extend(outcome.pop("warnings"))
            unreconciled.extend(outcome.pop("unreconciled"))
            return outcome
        except TransportError as exc:
            if exc.code == "rate_limited" and attempt < backoff.max_retries:
                backoff.pause(attempt, exc.details)
                attempt += 1
                continue
            raise


def _import_one_record(
    transport: Transport,
    owner: str,
    repo: str,
    record: ImportRecord,
    pacer: Pacer,
    alias_index: "_AliasIndex",
    run_warnings: list[str],
) -> dict:
    """Idempotently import ONE record: find-or-create by its key label, self-heal a
    human-deleted alias, reconcile status. Returns an outcome dict —
    ``created``/``skipped``/``collision`` — with the warnings and deferred status
    reconciles it accrued (both kept local so a rate-limit replay of the whole record
    can't double-count). Every step is idempotent, so replaying the whole record
    after a pause is safe.

    **The alias self-heal line is the one exception, and goes to ``run_warnings``.**
    Everything else here is retry-local by design, but the heal is a *persisted
    write*: once the ``id:PFX`` label is restored, a replay finds it on the fast
    label path, never re-heals, and never re-emits the line — and a later resume
    can't either, for the same reason. Discarding it with a retried attempt would
    lose it permanently, which is exactly the loss BKL-9V2W's envelope fix exists to
    prevent. It can fire at most once per record per run, so promoting it cannot
    double-count."""
    warnings: list[str] = []
    unreconciled: list[dict] = []
    key_label = record.key_label()
    existing = _find_by_key(transport, owner, repo, key_label)
    healed = False
    if not existing and record.pfx:
        # The `id:PFX` label — the primary skip authority — is missing (a human
        # deleted it). Fall back to the durable block `id_aliases` record (§5) so the
        # re-import skips-not-duplicates: GitHub never reuses issue numbers, so a
        # duplicate here would be permanent.
        existing = alias_index.numbers_for(record.pfx)
        healed = bool(existing)
    if len(existing) > 1:
        # Alias uniqueness violated in the repo (§5) — flag, don't guess.
        return {
            "outcome": "collision",
            "collision": {"key": key_label, "refs": [f"{owner}/{repo}#{n}" for n in existing]},
            "warnings": warnings,
            "unreconciled": unreconciled,
        }
    if existing:
        # The skip authority is the on-GitHub alias — its `id:PFX` label, or (when a
        # human deleted that label) its block `id_aliases` record — never the
        # checkpoint (a stale/externally-deleted checkpoint entry must not skip an
        # item that isn't actually on GitHub, or the item is lost). A block-recovered
        # match self-heals the missing label so the alias resolves again and the next
        # run skips on the fast label path.
        if healed:
            _restore_alias_label(transport, owner, repo, existing[0], key_label, run_warnings)
        # Reconcile only the status, so a resumed item created-but-crashed before its
        # close still converges (CRASH-4).
        _reconcile_status(transport, owner, repo, existing[0], record, warnings, unreconciled)
        return {
            "outcome": "skipped",
            "entry": {"key": key_label, "id": _canon(owner, repo, existing[0])},
            "warnings": warnings,
            "unreconciled": unreconciled,
        }

    issue = _create_item(transport, owner, repo, record, pacer)
    number = issue.get("number")
    _reconcile_status(transport, owner, repo, number, record, warnings, unreconciled)
    return {
        "outcome": "created",
        "entry": {"key": key_label, "id": _canon(owner, repo, number), "pfx": record.pfx},
        "warnings": warnings,
        "unreconciled": unreconciled,
    }


def _find_by_key(transport: Transport, owner: str, repo: str, key_label: str) -> list[int]:
    """The issue numbers carrying ``key_label`` (an alias/idempotency marker). More
    than one is an integrity violation the caller flags. Searches all states — a
    resumed item may already be closed (an archive import). The label is the
    **primary** skip authority; when a PFX item's label is missing the caller falls
    back to the block ``id_aliases`` via :class:`_AliasIndex`."""
    issues = transport.list_issues(
        owner, repo, state="all", labels=[key_label], per_page=100, page=1
    )
    # Labels can sit on PRs too; a labeled PR must never count as the item
    # (BKL-5T3J — the raw list interleaves them).
    issues = [issue for issue in issues if not encode.is_pull_request(issue)]
    return [issue["number"] for issue in issues if issue.get("number") is not None]


class _AliasIndex:
    """Lazily-built ``PFX → [issue numbers]`` index over the block ``id_aliases``
    record — the re-import skip-authority when a human deleted the ``id:PFX`` label.

    Built **once, on the first label-miss**, and cached: a clean import or resume
    (every ``id:PFX`` label intact) never triggers the scan, so the common path
    keeps its per-record label lookup; a drifted re-import pays exactly one full-
    issue scan (not one per record). The scan (:func:`core.iter_alias_issues`) may
    raise ``TransportError`` — it runs inside ``import_items``' resumable try."""

    def __init__(self, transport: Transport, owner: str, repo: str) -> None:
        self._transport = transport
        self._owner = owner
        self._repo = repo
        self._index: dict[str, list[int]] | None = None

    def numbers_for(self, pfx: str) -> list[int]:
        if self._index is None:
            self._index = self._build()
        return list(self._index.get(pfx, ()))

    def _build(self) -> dict[str, list[int]]:
        index: dict[str, list[int]] = {}
        for number, pfxs, _labels, _status in core.iter_alias_issues(
            self._transport, self._owner, self._repo
        ):
            for pfx in pfxs:
                index.setdefault(pfx, []).append(number)
        return index


def _restore_alias_label(
    transport: Transport, owner: str, repo: str, number: int, key_label: str, warnings: list
) -> None:
    """Re-add the ``id:PFX`` alias label the block recovered but the issue had lost,
    so the alias resolves again (read path) and the next import skips on the fast
    label path. Ensures the label definition first (a human may have deleted it
    too), then adds it — add-only, never removes (DM7)."""
    provision.ensure_labels(transport, owner, repo, [key_label])
    transport.add_labels(owner, repo, number, [key_label])
    warnings.append(
        f"restored missing alias label {key_label} on {_canon(owner, repo, number)} "
        "from the block id_aliases record"
    )


def _create_item(
    transport: Transport, owner: str, repo: str, record: ImportRecord, pacer: Pacer
) -> dict:
    """Provision the labels the create references, pace the content-budget create,
    then create the issue with the key label **in the create** (atomic idempotency).
    Returns the created issue dict."""
    key_label = record.key_label()
    all_labels = list(record.labels) + [key_label]
    provision.ensure_labels(transport, owner, repo, all_labels)
    # The body↔block framing is the one in encode (shared with `file`), so the
    # importer's fresh block attaches identically — export round-trips depend on it.
    body = encode.compose_body(record.body, record.block)
    pacer.before_create()  # content-creation budget (80/min, 500/hr); the create's
    # 5-pt REST cost — like every other call — is metered by _PacingTransport below.
    return transport.create_issue(owner, repo, title=record.title, body=body, labels=all_labels)


def _reconcile_status(
    transport: Transport,
    owner: str,
    repo: str,
    number: int | None,
    record: ImportRecord,
    warnings: list,
    unreconciled: list[dict],
) -> None:
    """Bring an item to its target status idempotently (only when it differs — a
    freshly-created ``open`` item needs no write). Reuses the crash-safe
    ``core.set_status`` so the two-axis transition has exactly one implementation.

    A deferred reconcile appends to BOTH ``warnings`` (the per-item audit line) and
    ``unreconciled`` (the structured record the run counts) — one event, recorded
    here rather than reassembled by each caller, so the two can never disagree
    about whether a deferral happened.

    **A rate-limited close is re-raised, never deferred.** ``core.set_status``
    catches ``TransportError`` and returns an envelope, so a 429 on the close was
    invisible to the reactive backoff built for exactly this stretch — the
    pause-and-retry only ever saw *creates*, while an ``--archive-scope all`` run
    closes about as many items as it creates. Re-raising puts the close on the same
    retry contract as the create: the whole record replays (every step is
    idempotent, so a replay is safe), and an exhausted budget falls through to the
    resumable envelope exactly as a rate-limited create does.

    **Every other failure still defers to the resume**, deliberately: a *create*
    failure aborts because the content budget is the scarce, risky path, while a
    status reconcile is core-budget and transient, so the item stays open and the
    resume's reconcile converges it. What changes is that the deferral is no longer
    *only* prose in ``warnings`` — it is also counted, so a run that left items
    unreconciled cannot report plain success with the only evidence buried in an
    audit line nobody reads.
    """
    if number is None:
        return
    canonical = _canon(owner, repo, number)
    issue = transport.get_issue(owner, repo, number)
    decoded, _ = encode.decode_item(issue, canonical_id=canonical)
    if decoded.get("status") == record.status:
        return
    result = core.set_status(transport, id_raw=canonical, target=record.status)
    if result.get("status") == "ok":
        return
    failure = result.get("error", {})
    code = failure.get("code")
    if code == "rate_limited":
        # Reconstructed losslessly — `from_transport_error` carries code, message,
        # retryable and details across, so the backoff still reads its Retry-After.
        # The phase and the item are PREPENDED rather than used as an empty-message
        # fallback: this exception is the only evidence that a 429 storm hit the
        # close stretch rather than the creates, and that distinction is the whole
        # reason the close was put on the retry contract.
        raise TransportError(
            code,
            f"status reconcile for {canonical} → {record.status}: "
            + (failure.get("message") or "secondary rate limit"),
            retryable=failure.get("retryable"),
            details=failure.get("details"),
        )
    warnings.append(f"status reconcile deferred for {canonical}: {code}")
    unreconciled.append(
        {"id": canonical, "pfx": record.pfx, "target": record.status, "code": code}
    )


# --- export ------------------------------------------------------------------


def verify_migration(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    content: str,
    archive_content: str | None = None,
    archive_scope: str = "all",
) -> dict:
    """Is every source item present on the target? The completeness gate.

    **Why this is a command and not a checklist line.** The scrub runbook has
    always prescribed the comparison — step 5's *"Total issue count = every
    source item"* — but as a human eyeball step with no tooling behind it.
    ``counts`` reports the target side only and never sees the source. A partial
    import therefore passes unnoticed, and then setting ``backlog_service_repo``
    makes the markdown stop being read, so the failure becomes **invisible at
    exactly the step that should have caught it**. Observed live: a repo
    recorded its cutover with 7 of 9 items never imported.

    **Compares the SOURCE set against alias coverage, never issue counts.**
    Issues filed natively after a cutover carry a ``prawduct`` block but no
    ``id:PFX`` alias, so a raw count comparison passes while source items are
    still stranded — which is precisely how the observed repo looked (17 issues,
    2 aliases, 9 source items).

    **Coverage is necessary but not sufficient — the status has to match too.**
    An item can be present and correctly keyed and still not be migrated: the
    import defers a failed status reconcile so the run can continue, which leaves
    the issue on the target at the wrong status. Under ``--archive-scope all`` a
    rate-limited or flaky close stretch does that in bulk, and a coverage-only
    comparison reports 100% while every archived item sits open. So the gate reads
    the **decoded** status off the same scan (``core.iter_alias_issues``, which
    already fetches all states) and reports any divergence from the source's target
    as ``status_mismatch``. This is the F9 failure mode through a *third* door — the
    gate green, the migration not done — after F9 itself and the unaliasable-id
    class.

    **Two target issues recording one id are ``duplicate_alias``, never
    ``status_mismatch``.** The lists are partitioned by *remedy*, not by symptom, and
    that pair diverges: a mismatch clears on a re-import, an ambiguous alias cannot
    (see :func:`_incompleteness_remedy`). Folding them together would put "re-run the
    import" in front of an operator for whom it is a no-op — the same defect this
    docstring already records above, where a scope mismatch produced "a false
    conflict … on a gate whose prescribed remedy can never clear it."

    A mismatch is deliberately **not** carved out for items a human may have
    legitimately moved on the target since import: the gate runs immediately after
    the import in one operator session, and a false positive here is safe (it says
    incomplete, and re-running the import is idempotent) where a false negative is
    the thing being fixed.

    **An item whose id is not a valid PFX is reported, not excluded.** Alias
    coverage can only speak for items an alias can key, so deriving the source
    set from PFX-bearing records alone would put a hand-written id like
    ``[AUD-TIMBRE-CALIB]`` *outside the comparison* — it imports (under an
    idempotency-only ``import-key:`` marker, so it neither duplicates nor
    strands), the gate compares the remaining items, and a repo one item short
    of complete reports 100% coverage. That is the same silence this command
    exists to end, so ``unaliasable`` conflicts exactly as ``missing`` does.
    Both live backlogs carried one such item when this was written.

    **A duplicate-PFX collision is reported too**, for the same reason. Two source
    items claiming one alias are dropped by :func:`collect_records` rather than
    merged, so a collided item is never created — and, being absent from
    ``records``, it would otherwise leave ``missing`` empty and the gate green.
    That is the F9 failure mode through a second door.

    **The source set is the importer's create set, not a re-derivation of it.**
    This routes through the same ``collect_records`` → :func:`apply_archive_scope`
    pair :func:`import_backlog` uses, because the two must not be able to drift.
    They did: an earlier inline version filtered the MG4b lever by *source file*
    while the importer filters by *status*, so under ``--archive-scope open``
    every closed item in the main ``backlog.md`` was skipped by the import and
    counted as ``missing`` here — a false conflict on the order of 150 items for
    a mature backlog, on a gate whose prescribed remedy ("re-run the import") can
    never clear it. Those items are not stranded and must not be reported as
    though they were: under that lever they stay in the
    git-tracked source markdown by design, which is the point of choosing it.

    **Names the stranded items, never just a count** — a count says something is
    wrong; the ids say what to re-import. ``unaliasable`` reports titles rather
    than ids because a non-PFX marker is not stripped from the title, so the
    title carries the id the operator has to go find.

    Returns ``ok`` only when every source item is accounted for, else a
    ``conflict`` envelope (exit 4: the two stores disagree — a data
    inconsistency, not a bad request). Read-only: it creates nothing and
    reconciles nothing.
    """
    records, collisions = collect_records(content, archive_content)
    records, _archive_skipped = apply_archive_scope(records, archive_scope)
    source = [r.pfx for r in records if r.pfx]
    unaliasable = [r.title for r in records if not r.pfx]
    collided = [f"{c['pfx']} ({c['title']})" for c in collisions]

    try:
        aliased: dict[str, str] = {}
        # PFXs claimed by two issues whose decoded statuses DISAGREE. The importer's
        # collision branch cannot speak for these: it fires on two issues carrying the
        # same `id:PFX` **label**, while this scan derives `pfxs` from the body block
        # `id_aliases` — a deliberately different source of truth (`_AliasIndex` exists
        # because the label can be deleted while the block record survives). So a
        # block-only duplicate is invisible there, and resolving it by whichever page
        # GitHub returned first would let this verdict flip with page order on the gate
        # guarding ~900 irreversible writes. Reported instead: at most one of the two
        # can match the source, so the item is not verifiably at its target either way.
        ambiguous: set[str] = set()
        for _number, pfxs, _labels, status in core.iter_alias_issues(transport, owner, repo):
            for pfx in pfxs:
                if pfx in aliased and aliased[pfx] != status:
                    ambiguous.add(pfx)
                aliased.setdefault(pfx, status)
    except TransportError as exc:
        return core.from_transport_error(exc)

    missing = [p for p in source if p not in aliased]
    # An ambiguous alias is its own recoverability class and must NOT ride in
    # `status_mismatch`: that list's remedy is "re-run the import", which cannot
    # clear this one. The labelled issue already matches, so the re-run's
    # `_find_by_key` returns it and `_reconcile_status` writes nothing; the
    # block-only duplicate carries no label, so `_AliasIndex` is never consulted and
    # it is never touched. The next scan sees the same disagreement and exits 4
    # again — a full ~900-write re-run that converges on nothing. Only a target-side
    # deduplication fixes it.
    duplicate_alias = [p for p in source if p in ambiguous]
    status_mismatch = [
        f"{r.pfx} (source: {r.status}, target: {aliased[r.pfx]})"
        for r in records
        if r.pfx and r.pfx in aliased and r.pfx not in ambiguous and aliased[r.pfx] != r.status
    ]
    data = {
        "repo": f"{owner}/{repo}",
        "source_items": len(records),
        "aliased": len(source) - len(missing),
        "missing": missing,
        "unaliasable": unaliasable,
        "collisions": collided,
        "status_mismatch": status_mismatch,
        "duplicate_alias": duplicate_alias,
    }
    if missing or unaliasable or collided or status_mismatch or duplicate_alias:
        return core.error(
            "conflict",
            f"{len(records)} source item(s) in scope, {data['aliased']} verifiably "
            f"keyed to an issue on {owner}/{repo} — the migration is incomplete; "
            + _incompleteness_remedy(
                missing, unaliasable, collided, status_mismatch, duplicate_alias
            ),
            details=data,
        )
    return core.ok(data)


def _incompleteness_remedy(
    missing: list[str],
    unaliasable: list[str],
    collided: list[str],
    status_mismatch: list[str],
    duplicate_alias: list[str],
) -> str:
    """The operator-facing next step, which differs by *why* an item is absent.

    A ``missing`` item re-imports cleanly — the import is alias-keyed, so already
    -migrated items skip rather than duplicate. An ``unaliasable`` one does not:
    its idempotency key is a digest of title+body, and giving it a real PFX
    changes both the key and the title, so a re-import after the rename **mints a
    second issue** instead of adopting the first. A ``collided`` one is not an
    import problem at all — two source items claim one alias, so the source has to
    be disambiguated before any re-run can help. A ``status_mismatch`` item is
    present and correctly keyed but sitting at the wrong status — a re-run fixes it
    (the skip branch still reconciles the status axis), which puts it in the same
    recoverability class as ``missing`` and not with the two that re-running cannot
    fix. A ``duplicate_alias`` item is the one that looks like ``status_mismatch``
    and behaves like ``collided``: two issues on the *target* record the same PFX at
    different statuses, and a re-import touches neither — the labelled one already
    matches so nothing is written, and the unlabelled one is never looked up — so
    the only fix is a target-side deduplication. Saying "re-run import" for all five
    would be wrong for three of them."""
    parts = []
    if missing:
        parts.append(
            f"re-run import for the {len(missing)} item(s) in `missing` "
            "(alias-keyed, so migrated items skip rather than duplicate)"
        )
    if unaliasable:
        parts.append(
            f"the {len(unaliasable)} item(s) in `unaliasable` carry an id that is not "
            "a valid PFX, so no alias can key them — give each a real PFX in the "
            "source BEFORE importing; after an import, renaming one and re-importing "
            "creates a duplicate rather than adopting the existing issue "
            "(see the scrub runbook, step 6)"
        )
    if collided:
        parts.append(
            f"the {len(collided)} item(s) in `collisions` share a PFX with an earlier "
            "item, so the import dropped them rather than merging two items onto one "
            "alias — give each a distinct PFX in the source, then re-import"
        )
    if status_mismatch:
        parts.append(
            f"the {len(status_mismatch)} item(s) in `status_mismatch` are on the target "
            "at the WRONG status — the issue exists and is keyed, but a status "
            "reconcile never landed (see `status_unreconciled` in the import result); "
            "re-run the import, which reconciles the status axis on already-migrated "
            "items too"
        )
    if duplicate_alias:
        parts.append(
            f"the {len(duplicate_alias)} item(s) in `duplicate_alias` are recorded by "
            "TWO issues on the target whose statuses disagree, so no import can decide "
            "which is authoritative — **do not re-run the import**, which writes to "
            "neither (the labelled issue already matches; the block-only one is never "
            "looked up). Find the pair by searching the target for the id, then "
            "deduplicate there — `merge <duplicate-id> --into <survivor-id>` — and "
            "verify again"
        )
    return "; ".join(parts)


def export_backlog(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    dest: Path,
    now: datetime | None = None,
) -> dict:
    """Full-fidelity **dump** of ``owner/repo``'s backlog to plain JSON files: one
    ``item-<number>.json`` per in-scope item (body block **plus** the native graph
    — dependencies, sub-issues, timeline, assignees) + an ``export-manifest.json``
    (MG2/G5/MIG-3). A cheap dump for backup/inspection, **not** a lossless re-import
    schema (Data Model §8). Returns an envelope; a filesystem or transport failure
    degrades to an error, never raises."""
    now = now or datetime.now(timezone.utc)
    dest = Path(dest)
    warnings: list[str] = []
    try:
        issues = _scan_all(transport, owner, repo)
        dest.mkdir(parents=True, exist_ok=True)
        exported: list[str] = []
        for issue in issues:
            if not encode.is_prawduct_issue(issue):
                continue  # PROV-2 — non-prawduct issues are out of scope
            number = issue.get("number")
            canonical = _canon(owner, repo, number)
            record = _export_record(transport, owner, repo, issue, canonical)
            _write_json(dest / f"item-{number}.json", record)
            exported.append(canonical)
        manifest = {
            "schema": EXPORT_SCHEMA_VERSION,
            "repo": f"{owner}/{repo}",
            "exported_at": _iso(now),
            "count": len(exported),
            "items": exported,
        }
        _write_json(dest / "export-manifest.json", manifest)
    except TransportError as exc:
        return core.from_transport_error(exc)
    except OSError as exc:
        _diag(f"export could not write to {dest}: {type(exc).__name__}")
        return core.error("unavailable", f"export could not write to {dest} ({type(exc).__name__})")
    except json.JSONDecodeError as exc:  # ERR-6
        _diag(f"unexpected transport failure on export: {type(exc).__name__}")
        return core.error("unavailable", "the export backend request failed unexpectedly")

    return core.ok(
        {"repo": f"{owner}/{repo}", "dir": str(dest), "count": len(exported), "items": exported},
        warnings,
    )


def _export_record(
    transport: Transport, owner: str, repo: str, issue: dict, canonical: str
) -> dict:
    """One item's export record: the decoded projection + the **native graph**
    (deps, sub-issues, timeline, assignees) — what makes the dump full-fidelity
    rather than body-only (MIG-3)."""
    number = issue.get("number")
    item, _ = encode.decode_item(issue, canonical_id=canonical)
    block = encode.parse_block(issue.get("body"))
    return {
        "schema": EXPORT_SCHEMA_VERSION,
        "id": canonical,
        "node_id": issue.get("node_id"),
        "number": number,
        "title": issue.get("title"),
        "body": issue.get("body"),
        "status": item.get("status"),
        "stage": item.get("stage"),
        "labels": item.get("labels"),
        "assignees": [a.get("login") for a in issue.get("assignees") or [] if isinstance(a, dict)],
        "block": dict(block.fields),
        "id_aliases": item.get("id_aliases"),
        "superseded_by": item.get("superseded_by"),
        "relationships": {
            "blocked_by": [b["ref"] for b in transport.list_blocked_by(owner, repo, number)],
            "sub_issues": [c["ref"] for c in transport.list_sub_issues(owner, repo, number)],
        },
        "timeline": transport.list_timeline(owner, repo, number),
    }


def _scan_all(transport: Transport, owner: str, repo: str) -> list[dict]:
    """Every issue in the repo across pages (state=all), bounded so a pathological
    repo can never spin forever. Raises ``TransportError`` on failure (caught by the
    caller's envelope boundary)."""
    collected: list[dict] = []
    page = 1
    per_page = 100
    while page <= 1000:  # a very high backstop; a real repo is far smaller
        batch = transport.list_issues(owner, repo, state="all", per_page=per_page, page=page)
        collected.extend(batch)
        if len(batch) < per_page:
            return collected
        page += 1
    _diag("export scan hit the page cap; results truncated")
    return collected


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


# --- merge (minimal fold A→B, redirect-before-close) -------------------------


def merge(
    transport: Transport,
    *,
    source_raw: str,
    target_raw: str,
    default_owner: str | None = None,
    default_repo: tuple[str, str] | None = None,
) -> dict:
    """Fold ``source`` into ``target`` (AU3/DM7): the minimal merge the scrub needs
    to dispose duplicates. **Canonical write order** — write the block
    ``superseded_by`` redirect on the source **before** closing it (CRASH-2), so a
    crash leaves the source **open-but-redirected** (a ref to it resolves to the
    target — a valid, resolvable state) and a re-run completes idempotently; it
    **never closes-then-orphans**. Nothing is hard-deleted — both bodies survive
    (the source is closed, not removed). Idempotent: a re-run is a no-op."""
    try:
        # Either endpoint may be a bare hand-minted PFX, resolved via its id:PFX
        # alias (a label search — I/O), so resolution lives inside the transport try
        # (MG1 — a migrated item's original id stays a valid merge endpoint forever).
        sid = core.resolve_ref(transport, source_raw, default_owner=default_owner, default_repo=default_repo)
        if not sid.ok:
            return core.error(sid.error or "validation", sid.message or f"bad source ID {source_raw!r}")
        tid = core.resolve_ref(transport, target_raw, default_owner=default_owner, default_repo=default_repo)
        if not tid.ok:
            return core.error(tid.error or "validation", tid.message or f"bad target ID {target_raw!r}")
        if sid.canonical == tid.canonical:
            return core.error("validation", "cannot merge an item into itself")

        # Confirm the target exists before redirecting the source at it (a dangling
        # redirect would strand the source pointing at nothing).
        transport.get_issue(tid.owner, tid.repo, tid.number)
        source = transport.get_issue(sid.owner, sid.repo, sid.number)

        # Step 1 — write the redirect on the source FIRST (idempotent upsert).
        old_body = source.get("body") or ""
        new_body = encode.upsert_block_field(old_body, "superseded_by", tid.canonical)
        if new_body != old_body:
            transport.update_issue(sid.owner, sid.repo, sid.number, fields={"body": new_body})

        # Step 2 — close the source as dropped (idempotent, crash-safe set-status).
        close = core.set_status(transport, id_raw=sid.canonical, target="dropped")
        if close.get("status") != "ok":
            return close
    except TransportError as exc:
        return core.from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _diag(f"unexpected transport failure on merge: {type(exc).__name__}")
        return core.error("unavailable", "the merge backend request failed unexpectedly")

    return core.ok(
        {"source": sid.canonical, "target": tid.canonical,
         "superseded_by": tid.canonical, "merged": True}
    )


def resolve(transport: Transport, canonical: str, *, owner: str, repo: str) -> str:
    """Follow a merged-away source to its survivor (CRASH-2). Delegates to
    :func:`core.resolve_survivor` — the single transport wiring of the pure
    redirect-follow, shared with ``get``'s consumer (BKL-5R2K)."""
    del repo  # kept in the public signature for existing callers; follow needs only owner
    return core.resolve_survivor(transport, canonical, owner=owner)


# --- shared helpers ----------------------------------------------------------


def _canon(owner: str, repo: str, number: int | None) -> str:
    return f"{owner}/{repo}#{number}"


def _iso(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
