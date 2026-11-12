"""Governance-event ledger — append-only review history (review-proportionality ch.02).

The single-slot ``.prawduct/.critic-findings.json`` stays the canonical "latest
record" every existing consumer reads; this module adds an append-only EVENT
history alongside it at ``.prawduct/.governance-ledger.jsonl`` — one JSON event
per line. The ledger exists to answer the elicited analytics questions (the
build plan's "Ledger data requirements"): reviewer-model efficiency per role,
findings density per code path, wall clock per phase per feature, and
cross-project aggregation (TEL-7A4X). Fields exist to serve those questions.

**Envelope/payload split.** Every event shares the envelope —
``{schema_version, event, ts, duration_seconds, project, scope, chunk,
actor: {role, model}, git: {head, base}}`` — plus three OPTIONAL envelope keys.
``dispatched_at`` is written whenever a ``review.*`` append finds the dispatch
marker belonging to its OWN kind (``data-model.md`` carries its semantics;
each consuming kind owns a separate marker file, so two kinds in flight at
once never clear each other's measurement).
``review_written_at`` rode beside a kept ``dispatched_at`` on a recorded
``review.pr`` — when the reviewer's evidence was written, where that interval
ends; readers still honour it (``review_dispatch.event_interval_seconds``).
``trigger`` is written on every ``review.critic`` event — which of
:data:`CONSOLIDATION_TRIGGERS` consolidated the review — and on no other kind.
They are enumerated here because
this sentence is what a maintainer reads to decide whether a key is envelope or
payload, and an aggregator written from an enumeration that omits one will not
find it. The event then nests its kind-specific
payload beneath a family-named key (``review`` for ``review.critic`` and the
recorded ``review.pr``; ``learning`` for ``learning.*``). Aggregators key on
the envelope without understanding every payload; consumers skip unknown
event kinds and unknown fields. Emitted: ``review.critic`` (a review
happened), plus ``learning.written`` and ``learning.fired`` — a
rule authored this session, and a rule a Critic finding cited — which are
what let an audit of the learning loop read a number instead of sampling
transcripts. (``build.chunk`` / ``plan.authored`` / ``discovery.session``
are accommodated by the envelope and deliberately NOT built — see the build
plan's Out of scope.) Two additive kinds change no existing line's meaning,
so ``schema_version`` stays 1. ``review.pr`` was emitted by the PR reviewer's
flow until that reviewer was retired; the kind is now refused at the CLI
(:data:`_RETIRED_KINDS`), and the events already recorded stay readable by
``review-stats`` (``lib.telemetry``) and ``tools/pr-review-yield.py``. (``stats``
reads the evidence store, never this ledger.)

**Structural writer.** The agent never hand-authors JSONL: ``prawduct-hook
ledger-append`` reads the just-written findings file, validates it,
computes the envelope itself, and appends ONE line in a single
``O_APPEND``-mode write. The ``learning.*`` kinds are refused AT that CLI —
their fields are derived (a unit hash from the corpus, a session from disk),
so a typed one measures nothing; :func:`append_learning_event` is their one
entry point, and it is idempotent because the Stop hook re-observes the same
new rule on every turn of a session.

Validation lives at the append boundary because ``_append_event`` is the only writer — the CLI for review kinds, :func:`append_learning_event` for learning kinds — ``review.critic`` payloads through
``lib.gates.validate_critic_findings`` (the derived-cache schema), read from
the canonical ``.critic-findings.json``. ``duration_seconds`` and
``actor.model`` come from the findings record / ``--model`` — both
nullable, never invented.

**Scope attribution.** An event records the scope its caller hands it, or
``null`` — never one this module derives. A review event's ``--scope`` comes
from the dispatch manifest, where ``critic-begin`` recorded the checkout's
work-unit binding (``lib.work_unit``) or an explicit override; a learning
event's comes from the caller that knows which review or session it measured.
This module used to fill a missing scope from the active build plan, and that
fallback is what attributed a review of one branch to an unrelated plan's
scope: the manifest said ``none`` and the ledger said otherwise, so the two
records of one review described different work.

Size is unbounded-but-tiny (one line per event). If a long-lived repo ever
needs pruning, truncate oldest-first by line — every line is self-contained;
no tooling is built for this until a real ledger needs it.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import gitstate, review_dispatch

LEDGER_BASENAME = ".governance-ledger.jsonl"
LEDGER_SCHEMA_VERSION = 1

# Event kind -> actor role. Fail-closed: unknown kinds are rejected at append
# (learnings: "Escape hatches in classification create silent failures").
_EVENT_ROLES = {
    "review.critic": "critic",
    # The learning loop's two measurements. `written` is the builder's act (a
    # rule authored this session); `fired` is the critic's (a finding that
    # cited one). Both are MACHINE-emitted — see `_MACHINE_ONLY_PREFIX`.
    "learning.written": "builder",
    "learning.fired": "critic",
    # A rule REWRITTEN by `learnings-compact`: `from_hash` is the unit it was,
    # `unit_hash` the unit it became. Not a new rule, so it is neither counted
    # as written nor allowed to orphan the rule's citation history.
    "learning.compacted": "builder",
    # The paired native review (#1130): one event per Critic review a
    # development build paired, written by `native-review record` from the
    # wrapper's text. Its payload sits under `review` with a `findings` list so
    # `review-stats` reads it as one more role beside `critic`.
    "review.native": "native",
}

#: Kinds only their own writer appends, outside the `learning.` family. A
#: hand-appended `review.native` would be built from `.critic-findings.json`,
#: which is the Critic's review, not the native one.
_MACHINE_ONLY_KINDS = frozenset({"review.native"})

#: Kinds the CLI refuses. A hand-appended learning event would be a measurement
#: of nothing: the emitters derive `unit_hash` from the corpus and `session`
#: from disk, and a typed one can agree with neither — so the instrument would
#: report a rule that fired without a review, or a rule nobody wrote. The
#: refusal is what keeps a `learning.*` line meaning what the join assumes.
_MACHINE_ONLY_PREFIX = "learning."

#: Which code path consolidated a Critic review — the `trigger` envelope key of a
#: `review.critic` event. Three paths reach the same `consolidate()` and leave the
#: same fact, findings file and cleared marker, so a dead trigger looks exactly
#: like a working one while the other two cover for it. The value is named by the
#: CALLER and never inferred: from inside `consolidate()` the paths are
#: indistinguishable, which is the whole problem.
CONSOLIDATION_TRIGGERS = ("subagent-stop", "explicit", "session-end-backstop")

#: Kinds this plugin once wrote and no longer does, and why — refused at the CLI
#: with that reason rather than as an unknown kind, because the caller is a stale
#: session's skill text and the reason is what tells it to restart. Events of
#: these kinds already on a ledger stay valid and are still read.
_RETIRED_KINDS = {
    "review.pr": (
        "the PR reviewer was retired; /prawduct:pr no longer dispatches one, so "
        "there is no PR review to record. Restart the session so the current "
        "skill loads. Recorded review.pr events stay readable by review-stats "
        "and tools/pr-review-yield.py."
    ),
}


def _cli_appendable() -> list[str]:
    """The kinds `ledger-append` accepts, for its own error message — derived
    so a kind added above cannot be advertised as hand-appendable by accident.
    """
    return sorted(
        k for k in _EVENT_ROLES
        if not k.startswith(_MACHINE_ONLY_PREFIX) and k not in _MACHINE_ONLY_KINDS
    )


def ledger_path(prawduct_dir: Path) -> Path:
    return prawduct_dir / LEDGER_BASENAME


def _append_event(
    project_dir: Path,
    prawduct_dir: Path,
    event_kind: str,
    payload_key: str,
    payload,
    *,
    duration_seconds=None,
    scope: str | None = None,
    chunk: str | None = None,
    actor_model: str | None = None,
    trigger: str | None = None,
    dispatched_at: str | None = None,
) -> Path:
    """Build the envelope and append ONE line. The only writer.

    Every kind shares this function so the envelope cannot fork: a second
    hand-built one would drift on the fields nothing local reads — ``project``,
    ``git.base``, the ``ts`` format — and those are exactly the fields
    cross-project aggregation (TEL-7A4X) keys on, so the drift would surface
    a fleet away from the code that caused it. The kind-specific part is one
    argument pair: the family key and the payload beneath it.

    Returns ``(ledger path, dispatch reason)`` — the path for the caller's own
    message, and the reason for what it did about the dispatch clock, which is
    always a NAMED outcome (``lib.review_dispatch``: an unnamed degradation on an
    advisory path manufactures the false success it exists to prevent).

    The dispatch mark is consumed HERE rather than at the CLI so that the ``head``
    the marker is checked against is the identical value the envelope records — two
    ``rev-parse`` calls could in principle straddle a commit and disagree, and the
    disagreement would read as an abandoned run.
    """
    base, _reason = _resolve_base(project_dir)
    head = review_dispatch.head_sha(project_dir)
    marked_at, dispatch_reason = review_dispatch.consume(prawduct_dir, event_kind, head)
    # A kind with no dispatch-mark slot may carry its own code-read clock (the
    # native review's dispatch time, stamped by `critic-begin`); a mark, where
    # the kind has one, is the stronger witness and wins.
    if marked_at is None and dispatched_at is not None:
        marked_at, dispatch_reason = dispatched_at, "dispatch time stamped by the caller's dispatch"
    dispatched_at = marked_at
    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event": event_kind,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration_seconds,
        "project": gitstate.project_label(project_dir),
        "scope": scope,
        "chunk": chunk,
        "actor": {"role": _EVENT_ROLES[event_kind], "model": actor_model},
        "git": {
            "head": head,
            "base": base,
        },
        payload_key: payload,
    }
    if trigger is not None:
        event["trigger"] = trigger
    # Present only when measured. An absent key is "not measured"; a null or a zero
    # would be a VALUE naming the absence, which reads as deliberate and which every
    # consumer would then have to special-case to avoid averaging into a real one.
    if dispatched_at is not None:
        event["dispatched_at"] = dispatched_at
    path = ledger_path(prawduct_dir)
    prawduct_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event) + "\n"
    # "a" opens O_APPEND; one write() call keeps concurrent appends whole.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
    return path, dispatch_reason


def ledger_append(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook ledger-append`` — see module docstring.

    Usage: ``ledger-append --event review.critic --trigger <t> [--scope <scope>]
    [--chunk <id>] [--model <id>]``. ``--trigger`` is required (one of
    :data:`CONSOLIDATION_TRIGGERS`). ``--findings`` is refused: the canonical
    ``.critic-findings.json`` is the only trusted source, and the flag existed
    for the retired ``review.pr`` kind, which is itself refused with its reason
    (:data:`_RETIRED_KINDS`). Exit 0 on append; exit 1 with a stderr reason on
    bad args, an unknown or retired event kind, or a missing/invalid findings
    file (an invalid record must not enter the review history; no gate reads
    the ledger, but ``review-stats`` and the round price do).
    """
    event_kind: str | None = None
    scope: str | None = None
    chunk: str | None = None
    model: str | None = None
    findings_arg: str | None = None
    trigger: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--event", "--scope", "--chunk", "--model", "--findings", "--trigger"):
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                print(f"ledger-append: {arg} requires a value", file=sys.stderr)
                return 1
            value = argv[i + 1]
            if arg == "--event":
                event_kind = value
            elif arg == "--scope":
                scope = value
            elif arg == "--chunk":
                chunk = value
            elif arg == "--findings":
                findings_arg = value
            elif arg == "--trigger":
                trigger = value
            else:
                model = value
            i += 2
        else:
            print(f"ledger-append: unknown argument {arg!r}", file=sys.stderr)
            return 1

    if event_kind is None:
        print("ledger-append: --event is required", file=sys.stderr)
        return 1
    # Checked BEFORE membership so `learning.written` and a mistyped
    # `learning.writen` get the same true answer — nothing under this prefix is
    # hand-appendable, and listing the real kinds as "allowed" would invite the
    # caller to fix the spelling and try again.
    if event_kind.startswith(_MACHINE_ONLY_PREFIX):
        print(
            f"ledger-append: {event_kind!r} is emitted by the Stop hook and "
            "critic-consolidate, never by hand — a typed learning event "
            "carries a unit hash and a session nothing derived, so it "
            "measures nothing. Those two record it themselves; there is "
            "nothing to append here.",
            file=sys.stderr,
        )
        return 1
    if event_kind in _MACHINE_ONLY_KINDS:
        print(
            f"ledger-append: {event_kind!r} is written by `prawduct-hook "
            "native-review record`, never by hand — it is built from the native "
            "review's own text, which this command does not read.",
            file=sys.stderr,
        )
        return 1
    if event_kind in _RETIRED_KINDS:
        print(f"ledger-append: {event_kind!r} is retired — {_RETIRED_KINDS[event_kind]}", file=sys.stderr)
        return 1
    if event_kind not in _EVENT_ROLES:
        allowed = ", ".join(_cli_appendable())
        print(
            f"ledger-append: unknown event kind {event_kind!r} (allowed: "
            f"{allowed}). Unknown kinds are rejected, not guessed.",
            file=sys.stderr,
        )
        return 1

    if event_kind == "review.critic":
        if trigger not in CONSOLIDATION_TRIGGERS:
            got = "none given" if trigger is None else f"got {trigger!r}"
            print(
                "ledger-append: review.critic requires --trigger "
                f"{'|'.join(CONSOLIDATION_TRIGGERS)} ({got}) — the code path that "
                "consolidated the review names itself, or a dead path is "
                "indistinguishable from a working one.",
                file=sys.stderr,
            )
            return 1
    elif trigger is not None:
        print(
            f"ledger-append: --trigger is only valid for review.critic — "
            f"{event_kind} has one writer and nothing to attribute.",
            file=sys.stderr,
        )
        return 1

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if findings_arg is not None:
        print(
            "ledger-append: --findings is refused — review.critic reads the "
            "canonical .critic-findings.json, and the kind that took a path "
            "(review.pr) is retired.",
            file=sys.stderr,
        )
        return 1
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        print(
            f"ledger-append: no findings record at {findings_path} — write "
            "the findings file first, then append.",
            file=sys.stderr,
        )
        return 1

    from . import gates  # noqa: PLC0415 — lazy; avoids a gates<->ledger import cycle

    if not gates.validate_critic_findings(findings_path):
        print(
            f"ledger-append: {findings_path} failed schema validation — an "
            "invalid record must not enter the review history review-stats reads.",
            file=sys.stderr,
        )
        return 1
    record = json.loads(findings_path.read_text())

    duration = record.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        duration = None
    record_model = record.get("model")
    actor_model = model or (
        record_model if isinstance(record_model, str) and record_model.strip() else None
    )

    path, dispatch_reason = _append_event(
        project_dir,
        prawduct_dir,
        event_kind,
        "review",
        record,
        duration_seconds=duration,
        scope=scope,
        chunk=chunk,
        actor_model=actor_model,
        trigger=trigger,
    )
    print(
        f"appended: {event_kind} -> {path} "
        f"(scope={scope or '-'}, chunk={chunk or '-'}, model={actor_model or '-'}"
        + (f", trigger={trigger}" if trigger else "")
        + ")"
    )
    print(f"duration: {dispatch_reason}")
    return 0


def _resolve_base(project_dir: Path) -> tuple[str | None, str]:
    """The canonical base resolution (``coverage._resolve_base_branch``),
    nullable on failure — the envelope records what was knowable, no more."""
    try:
        from . import coverage  # noqa: PLC0415 — lazy keeps ledger import light

        return coverage._resolve_base_branch(project_dir)
    except Exception:  # prawduct:allow prawduct/broad-except -- envelope fields are nullable, never fatal
        return None, "base resolution failed"


def _learning_key(kind: str, learning: dict) -> tuple:
    """The idempotence key of a learning event, from its payload.

    One home, used by both the probe and the writer: a key built twice is a key
    that can be built two ways, and the two would disagree the first time a
    field is added — silently, as a duplicate line rather than an error.
    """
    return (
        kind,
        learning.get("session"),
        learning.get("file"),
        learning.get("unit_hash"),
        learning.get("review_id"),
        # Two rules merged into one share every field above; the unit each
        # came FROM is what keeps them two events. None for the other kinds.
        learning.get("from_hash"),
    )


def learning_event_exists(
    prawduct_dir: Path,
    kind: str,
    *,
    file: str,
    unit_hash: str,
    session: "str | None",
    review_id: "str | None" = None,
) -> bool:
    """True if this exact learning event is already on the ledger.

    The same shape as :func:`review_event_exists` and for the same reason: the
    ledger has no key and no dedupe, and its lines are COUNTED — so a repeat
    emission inflates the instrument rather than being harmless. The repeat here
    is structural, not exceptional: the Stop hook runs every turn, so a rule
    written once is re-observed as "new since the session base" on every turn
    until the session ends, and a re-consolidation re-reads the same findings.
    The key is what makes that a no-op.

    ``session`` participates in the key, so the SAME rule written in two
    sessions is two events — which is what question 1 (rules written per
    session) needs. ``review_id`` likewise separates two reviews citing one
    rule, and is ``None`` for ``learning.written``.

    Cost is one ledger read per probe, and — as the paragraph above says — a
    unit stays "new since the session base" for the rest of the session, so a
    caller looping over a corpus must not pay this per unit: pass the set
    :func:`learning_events_seen` returns to :func:`append_learning_event`,
    which reads the ledger ONCE and answers every probe from memory. This
    per-call form is for the single-event callers.
    """
    want = _learning_key(kind, {
        "session": session, "file": file, "unit_hash": unit_hash, "review_id": review_id,
    })
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        if event.get("event") != kind:
            continue
        learning = event.get("learning")
        if not isinstance(learning, dict):
            continue
        if _learning_key(kind, learning) == want:
            return True
    return False


def compaction_map(prawduct_dir: Path) -> "dict[str, str]":
    """``learning.compacted`` as ``{from_hash: unit_hash}``, the NEWEST event
    winning where one unit was compacted twice.

    The one home for this map: the worksheet's ``cited`` column and
    ``review-stats`` both read citations through it, and two private copies
    that walked the ledger in opposite orders disagreed about which mapping won.
    """
    out: dict[str, str] = {}
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        if event.get("event") != "learning.compacted":
            continue
        learning = event.get("learning")
        if not isinstance(learning, dict):
            continue
        old, new = learning.get("from_hash"), learning.get("unit_hash")
        if isinstance(old, str) and isinstance(new, str) and old and new:
            out.setdefault(old, new)  # newest-first, so the first seen wins
    return out


def canonical_unit(became: "dict[str, str]", unit: str) -> str:
    """Follow ``became`` from ``unit`` to the unit it is now. Cycle-safe."""
    seen: set[str] = set()
    while unit in became and unit not in seen:
        seen.add(unit)
        unit = became[unit]
    return unit


def compacted_unit_hashes(prawduct_dir: Path) -> "set[str]":
    """Every unit a ``learnings-compact`` apply WROTE, from one ledger read.

    The Stop hook's ``learning.written`` emitter skips these: a rewritten rule
    is the old rule in fewer words, and counting it as written would report a
    compaction as hundreds of new rules and make "rules never cited" read as
    the whole corpus.
    """
    out: set[str] = set()
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        if event.get("event") != "learning.compacted":
            continue
        learning = event.get("learning")
        if isinstance(learning, dict) and isinstance(learning.get("unit_hash"), str):
            out.add(learning["unit_hash"])
    return out


def learning_events_seen(prawduct_dir: Path) -> "set[tuple]":
    """Every learning-event key on the ledger, from ONE read — the amortized
    form of :func:`learning_event_exists` for callers that probe a corpus's
    worth of units on one Stop (a 300-rule file re-observed every turn is 300
    whole-file reads otherwise, on a hook this repo budgets per turn)."""
    seen: set[tuple] = set()
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        kind = event.get("event")
        learning = event.get("learning")
        if kind in _EVENT_ROLES and isinstance(learning, dict) and kind.startswith("learning."):
            seen.add(_learning_key(kind, learning))
    return seen


def append_learning_event(
    project_dir: Path,
    kind: str,
    *,
    file: str,
    unit_hash: str,
    review_id: "str | None" = None,
    seen: "set[tuple] | None" = None,
    from_hash: "str | None" = None,
    scope: "str | None" = None,
) -> bool:
    """Append one ``learning.*`` event. ``True`` when a line was written,
    ``False`` when this exact event was already recorded.

    ``seen`` is the amortized dedupe: a caller probing many units on one turn
    passes the set :func:`learning_events_seen` returned (one ledger read) and
    this function answers from it and keeps it current — the per-unit ledger
    read is the default only for the single-event callers.

    Not reachable from the CLI (see :data:`_MACHINE_ONLY_PREFIX`): the two
    callers are the Stop hook, which derives the unit hashes by diffing the
    corpus against the session's base revision, and ``critic-consolidate``,
    which derives them from the units a finding cited. Both are measurements of
    something that already happened, so both are best-effort at their call
    sites — a ledger failure must never change a gate's verdict or a
    consolidation's exit code.

    ``scope`` is the work unit the caller measured — ``critic-consolidate``
    passes the scope its review recorded — and ``null`` when it has none to
    give; it is not looked up here (see the module docstring).

    ``session`` is :func:`evidence._session_epoch`, nullable and never invented:
    a fixture or a headless probe has no session, and a made-up id would put
    those events in a bucket of their own rather than leaving them uncounted.

    Raises ``ValueError`` for a kind outside :data:`_EVENT_ROLES` — fail-closed
    at the write boundary, exactly as the CLI does, because the caller catching
    it turns the mistake into a visible NOTE rather than a mystery line.
    """
    if kind not in _EVENT_ROLES or not kind.startswith(_MACHINE_ONLY_PREFIX):
        known = ", ".join(
            sorted(k for k in _EVENT_ROLES if k.startswith(_MACHINE_ONLY_PREFIX))
        )
        raise ValueError(
            f"append_learning_event: {kind!r} is not a learning event kind "
            f"(this plugin emits: {known})"
        )

    from . import evidence  # noqa: PLC0415 — lazy; evidence is heavy and this is a leaf call

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    session = evidence._session_epoch(project_dir)
    key = _learning_key(kind, {
        "session": session, "file": file, "unit_hash": unit_hash,
        "review_id": review_id, "from_hash": from_hash,
    })
    if seen is not None:
        if key in seen:
            return False
        seen.add(key)
    elif from_hash is None and learning_event_exists(
        prawduct_dir, kind, file=file, unit_hash=unit_hash,
        session=session, review_id=review_id,
    ):
        return False
    elif from_hash is not None and key in learning_events_seen(prawduct_dir):
        return False
    # `learning.*` is not a consuming kind, so the reason is always the "does not
    # consume" one — read and dropped rather than ignored by accident.
    _path, _dispatch_reason = _append_event(
        project_dir,
        prawduct_dir,
        kind,
        "learning",
        {
            "file": file,
            "unit_hash": unit_hash,
            "session": session,
            "review_id": review_id,
            **({"from_hash": from_hash} if from_hash else {}),
        },
        # A measurement of an act, not of a duration, and no model produced it:
        # both stay null rather than being given a plausible value.
        duration_seconds=None,
        scope=scope,
        actor_model=None,
    )
    return True


def append_native_review_event(
    project_dir: Path,
    prawduct_dir: Path,
    payload: dict,
    *,
    model: "str | None",
    scope: "str | None",
    dispatched_at: "str | None",
    duration_seconds: "float | None",
) -> Path:
    """Append one ``review.native`` event — the only writer of the kind,
    called by ``native_review.record``. ``dispatched_at`` is the dispatch time
    ``critic-begin`` stamped, so the duration is a code clock, not a report."""
    path, _reason = _append_event(
        project_dir, prawduct_dir, "review.native", "review", payload,
        duration_seconds=duration_seconds, scope=scope, actor_model=model,
        dispatched_at=dispatched_at,
    )
    return path


def native_review_event_exists(prawduct_dir: Path, review_id: str) -> bool:
    """True if a ``review.native`` event already records the native run paired
    with Critic review ``review_id`` — ``record``'s idempotency probe."""
    if not isinstance(review_id, str) or not review_id:
        return False
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        review = event.get("review")
        if (
            event.get("event") == "review.native"
            and isinstance(review, dict)
            and review.get("critic_review_id") == review_id
        ):
            return True
    return False


def review_event_exists(prawduct_dir: Path, fact_id: str) -> bool:
    """True if a ``review.*`` event already anchors this evidence fact.

    The idempotency probe the anchor lacked. The evidence fact survives a
    second consolidation by ``(kind, id)`` first-wins dedupe, but this ledger
    has no key and no dedupe, so the same review could anchor twice and be
    counted twice by ``review-stats`` — inflating the exact instrument review
    proportionality is judged on. Observed live 2026-07-29: one fact anchored
    two ``review.critic`` events a second apart.

    **Two reachable paths, and this closes one of them.** A *replay* — the same
    manifest and partials re-materializing after a success, or a crash between
    the fact append and ``remove_partials`` — is closed completely: the probe
    sees the earlier anchor. An *overlap*, two consolidations running past the
    manifest check at once, is only narrowed: this is read-then-write with no
    lock, so both callers can probe before either appends. The window shrinks
    from the whole consolidate body to the microseconds between probe and
    append. Not "exactly once" — and note that requiring the three coordinator
    reviewers to dispatch concurrently made overlap *more* reachable, not less.
    A maintainer who sees this recur should look for the lock, not a third
    caller.

    Cheap because it stops at the first match and reviews anchor near the tail;
    unparseable lines are skipped by the shared reader rather than trusted.
    """
    if not isinstance(fact_id, str) or not fact_id:
        return False
    for _lineno, event in iter_events_newest_first(prawduct_dir):
        review = event.get("review")
        if isinstance(review, dict) and review.get("fact_id") == fact_id:
            return True
    return False


def iter_events_newest_first(prawduct_dir: Path):
    """Yield ``(line_number, event_dict)`` newest-first, skipping unparseable
    lines and non-dict events with one stderr note each — a corrupt line must
    never crash a consumer."""
    path = ledger_path(prawduct_dir)
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ledger: unreadable ({exc}) — skipping", file=sys.stderr)
        return
    for lineno in range(len(lines), 0, -1):
        raw = lines[lineno - 1].strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            print(
                f"ledger: skipping unparseable line {lineno} of {path.name}",
                file=sys.stderr,
            )
            continue
        if not isinstance(event, dict):
            print(
                f"ledger: skipping non-object line {lineno} of {path.name}",
                file=sys.stderr,
            )
            continue
        yield lineno, event
