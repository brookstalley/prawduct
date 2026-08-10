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
actor: {role, model}, git: {head, base}}`` — and nests its kind-specific
payload beneath a family-named key (``review`` for both ``review.critic``
and ``review.pr``). Aggregators key on the envelope without understanding
every payload; consumers skip unknown event kinds and unknown fields. v1
emits ``review.critic`` and ``review.pr`` (``build.chunk`` /
``plan.authored`` / ``discovery.session`` are accommodated by the envelope
and deliberately NOT built — see the build plan's Out of scope).

**Structural writer.** The agent never hand-authors JSONL: ``prawduct-hook
ledger-append`` reads the just-written findings file, validates it,
computes the envelope itself, and appends ONE line in a single
``O_APPEND``-mode write. Validation lives at the append boundary because this
is the only writer — ``review.critic`` payloads through
``lib.gates.validate_critic_findings`` (the derived-cache schema),
``review.pr`` payloads through the same bar the stop-hook PR gate applies
(``findings`` list + non-empty ``summary``). ``review.critic`` always reads
the canonical ``.critic-findings.json``; ``review.pr`` requires the caller
to pass ``--findings <path>`` (the branch-derived evidence path the
``/prawduct:pr`` skill already computed). ``duration_seconds`` and
``actor.model`` come from the findings record / ``--model`` — both
nullable, never invented.

**Scope attribution.** ``--scope`` comes from the dispatch manifest, where
``critic-begin`` recorded it — derived in CODE from the branch name matched
against the scopes build plans declare, or passed explicitly as an override.
The ``active_build_plan`` pointer is only the last fallback, because
side-plans (a feature branch whose plan isn't the pointed-at one) would
otherwise mis-attribute the feature key. It used to say the *reviewer* passes
it explicitly; having the agent derive attribution from the pointer is what
misattributed manifests, review facts and ledger events to unrelated plans.

Size is unbounded-but-tiny (one line per event). If a long-lived repo ever
needs pruning, truncate oldest-first by line — every line is self-contained;
no tooling is built for this until a real ledger needs it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import gitstate
from .core import resolve_build_plan_path

LEDGER_BASENAME = ".governance-ledger.jsonl"
LEDGER_SCHEMA_VERSION = 1

# Event kind -> actor role. Fail-closed: unknown kinds are rejected at append
# (learnings: "Escape hatches in classification create silent failures").
_EVENT_ROLES = {"review.critic": "critic", "review.pr": "pr"}


def ledger_path(prawduct_dir: Path) -> Path:
    return prawduct_dir / LEDGER_BASENAME


def _git_capture(project_dir: Path, *args: str) -> str | None:
    """One git read; ``None`` on any failure (the writer must not crash —
    a repo-less fixture still gets an honest ``git: {head: null, ...}``)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception:  # prawduct:allow prawduct/broad-except -- envelope fields are nullable, never fatal
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _scope_from_plan(prawduct_dir: Path) -> str | None:
    """Fallback scope: the active build plan's frontmatter ``scope:`` value,
    else the ``build-plan-<scope>.md`` filename convention, else ``None``."""
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None
    try:
        # Explicit UTF-8, and `UnicodeDecodeError` (a `ValueError`) caught
        # alongside `OSError` — same contract as every other build-plan reader.
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # The canonical frontmatter reader, not a third hand-rolled copy.
    #
    # The driver is coverage, not a live bug: the decoding pin's data-flow
    # mechanism follows content into a known parser, so an inline scan has no
    # edge to follow and this read would have dropped silently out of the pin's
    # view (tests/preferences/test_build_plan_decoding.py). Folding onto the
    # shared reader keeps it visible by construction.
    #
    # The copy this replaced required `---` on line 1, so it could not read the
    # third of this repo's plans that open with a comment header — but on every
    # such plan today the frontmatter `scope:` equals the filename stem, and the
    # stem was its fallback, so the divergence is real in principle and zero in
    # practice here. Stated precisely because the first version of this comment
    # claimed an observable disagreement that does not exist.
    # Still imported lazily, for a reason that survived the split: a
    # module-scope import here would pull the callee into `lib.telemetry` too,
    # which imports `ledger`. `lib.plan_index` is cheap where the module it was
    # split out of was not, so the cost argument is gone — but the coupling
    # would be invisible to
    # the lazy-import pin, which probes only `lib` and `lib.core`, and cheap is
    # not the same as free on a path that never asks.
    from .plan_index import parse_build_plan_frontmatter_scope  # noqa: PLC0415

    _present, scope = parse_build_plan_frontmatter_scope(content)
    if scope:
        return scope
    stem = plan_path.stem
    if stem.startswith("build-plan-") and stem != "build-plan-":
        return stem[len("build-plan-"):]
    return None


def _validate_pr_evidence(record) -> bool:
    """The stop-hook PR gate's bar, applied at the append boundary:
    a dict with a ``findings`` list and a non-empty string ``summary``."""
    return (
        isinstance(record, dict)
        and isinstance(record.get("findings"), list)
        and isinstance(record.get("summary"), str)
        and bool(record["summary"].strip())
    )


def ledger_append(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook ledger-append`` — see module docstring.

    Usage: ``ledger-append --event review.critic|review.pr
    [--findings <path>] [--scope <scope>] [--chunk <id>] [--model <id>]``.
    ``--findings`` is required for ``review.pr`` (the branch-derived evidence
    path the caller computed) and rejected for ``review.critic`` (the
    canonical ``.critic-findings.json`` is the only trusted source). Exit 0
    on append; exit 1 with a stderr reason on bad args, unknown event kind,
    or a missing/invalid findings file (an invalid record must not enter the
    history the PR gate trusts).
    """
    event_kind: str | None = None
    scope: str | None = None
    chunk: str | None = None
    model: str | None = None
    findings_arg: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--event", "--scope", "--chunk", "--model", "--findings"):
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
            else:
                model = value
            i += 2
        else:
            print(f"ledger-append: unknown argument {arg!r}", file=sys.stderr)
            return 1

    if event_kind is None:
        print("ledger-append: --event is required", file=sys.stderr)
        return 1
    if event_kind not in _EVENT_ROLES:
        allowed = ", ".join(sorted(_EVENT_ROLES))
        print(
            f"ledger-append: unknown event kind {event_kind!r} (allowed: "
            f"{allowed}). Unknown kinds are rejected, not guessed.",
            file=sys.stderr,
        )
        return 1

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if event_kind == "review.pr":
        if findings_arg is None:
            print(
                "ledger-append: --findings <path> is required for review.pr "
                "(the .prawduct/.pr-reviews/<branch>.json path the caller "
                "computed).",
                file=sys.stderr,
            )
            return 1
        findings_path = Path(findings_arg)
        if not findings_path.is_absolute():
            findings_path = project_dir / findings_path
    else:
        if findings_arg is not None:
            print(
                "ledger-append: --findings is only valid for review.pr — "
                "review.critic reads the canonical .critic-findings.json.",
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

    if event_kind == "review.pr":
        try:
            record = json.loads(findings_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ledger-append: {findings_path} unreadable ({exc})", file=sys.stderr)
            return 1
        if not _validate_pr_evidence(record):
            print(
                f"ledger-append: {findings_path} failed PR-evidence "
                "validation (findings list + non-empty summary) — an invalid "
                "record must not enter the ledger.",
                file=sys.stderr,
            )
            return 1
    else:
        from . import gates  # noqa: PLC0415 — lazy; avoids a gates<->ledger import cycle

        if not gates.validate_critic_findings(findings_path):
            print(
                f"ledger-append: {findings_path} failed schema validation — an "
                "invalid record must not enter the ledger the PR gate trusts.",
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
    if scope is None:
        scope = _scope_from_plan(prawduct_dir)

    base, _reason = _resolve_base(project_dir)
    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event": event_kind,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "project": project_dir.resolve().name,
        "scope": scope,
        "chunk": chunk,
        "actor": {"role": _EVENT_ROLES[event_kind], "model": actor_model},
        "git": {
            "head": _git_capture(project_dir, "rev-parse", "HEAD"),
            "base": base,
        },
        "review": record,
    }

    path = ledger_path(prawduct_dir)
    prawduct_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event) + "\n"
    # "a" opens O_APPEND; one write() call keeps concurrent appends whole.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
    print(
        f"appended: {event_kind} -> {path} "
        f"(scope={scope or '-'}, chunk={chunk or '-'}, model={actor_model or '-'})"
    )
    return 0


def _resolve_base(project_dir: Path) -> tuple[str | None, str]:
    """The canonical base resolution (``coverage._resolve_base_branch``),
    nullable on failure — the envelope records what was knowable, no more."""
    try:
        from . import coverage  # noqa: PLC0415 — lazy keeps ledger import light

        return coverage._resolve_base_branch(project_dir)
    except Exception:  # prawduct:allow prawduct/broad-except -- envelope fields are nullable, never fatal
        return None, "base resolution failed"


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
    never crash a consumer (the PR-gate fallback reads through this)."""
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
