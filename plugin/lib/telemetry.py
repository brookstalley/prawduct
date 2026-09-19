"""Review telemetry — aggregate the governance ledger (review-proportionality ch.03).

Visible Costs (Principle 9) applied to the framework itself: ``prawduct-hook
review-stats`` turns the append-only event history
(``.prawduct/.governance-ledger.jsonl``) into the numbers the proportionality
arguments need — cost and actionable-finding yield per reviewer role × model ×
mode (the build plan's data requirement 1), a findings-by-file rollup from
finding-level attribution (requirement 2's first cut), and per-``scope``
rollups (the seam requirement 3's phase events will join later), and a
per-``stage`` rollup (``inner`` / ``boundary``, read from the record
``critic-begin`` stamped — the yield query behind the stage-keyed rigor norm).

v1 reports on ``review.*`` event kinds only; other kinds are skipped WITH A
COUNT (forward-compat: a future ``build.chunk`` producer must not crash or
silently vanish from an old reader). Corrupt lines likewise skip-and-count.
Telemetry is pulled, not pushed — nothing in the session hooks calls this.

The ``model`` dimension folds id aliases to a family label (``opus`` covers
``claude-opus-4-8`` and its ``[1m]`` variant; ``fable``/``sonnet``/``haiku``
stay distinct) so the reviewer-model A/B isn't fragmented across the several
id strings one model is recorded under (TEL-4M9X). The raw id stays in each
ledger line untouched — only the aggregation key folds (``_canonical_model``),
so this is a value-semantics change, not a key change: ``REPORT_SCHEMA_VERSION``
stays put. See ``docs/governance-telemetry.md``.

The reader deliberately does NOT reuse ``ledger.iter_events_newest_first``:
that iterator serves the PR-gate fallback (newest-first, per-line stderr
notes); this one is a quiet oldest-first sweep whose contract is honest
*counts* of what was skipped. The ``--json`` shape (top-level
``schema_version`` / ``project`` / ``generated_at``) is the stable machine
contract the cross-project aggregator (TEL-7A4X) builds on — documented in
``docs/governance-telemetry.md``; key changes bump ``REPORT_SCHEMA_VERSION``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from . import gitstate
from .ledger import ledger_path
from .timewindow import in_window, is_usable_bound

#: Report schema. Bumped to 2 when the learning-loop block arrived, to 3 when
#: `units_uncited` joined it, to 4 when verify-pass `observations` joined every
#: stat block, to 5 when `by_stage` joined the groupings, and to 6 when every
#: stat block gained `duration_measured` / `duration_self_reported`: the
#: `--json` shape gained keys each time, and TEL-7A4X keys on this shape.
#: Bumped to 7 when a `window` header and a per-severity `remedies` block
#: joined — the first states the bounds in force so a slice is never mistaken
#: for the whole corpus, the second reports whether a finding ships a fix plan.
#: The contract's prose home is ``docs/governance-telemetry.md``; a bump that
#: does not reach it leaves the published shape and its description disagreeing.
REPORT_SCHEMA_VERSION = 7

#: The two review stages a `review.critic` record can carry (`stage`, written
#: by `critic-begin` onto the manifest and carried through the fact and the
#: findings cache). Anything else — a missing key on an event written before
#: the field existed, or a value this reader does not know — groups as
#: ``None``, rendered "(unrecorded)": "not measured" must not read as a stage.
_STAGES = ("inner", "boundary")

#: Ledger kind -> the tally it feeds. Exact kinds, never a `learning.` prefix
#: match: a future kind this report has no column for must surface as
#: `unknown_kinds` rather than be silently folded into `written`.
_LEARNING_KINDS = {"learning.written": "written", "learning.fired": "fired"}

# Severities with first-class columns. Anything else a record carries lands in
# "other" — counted, never dropped (the validator only requires a non-empty
# severity string, so an unexpected value must stay visible).
_SEVERITIES = ("blocking", "warning", "note")
_ACTIONABLE = frozenset({"blocking", "warning"})

# Findings-by-file rollup cap (build plan: "top-N paths by actionable
# findings"). The human and JSON views share the cap; the JSON carries
# `files_attributed_total` so a truncated list is visible, never silent.
TOP_FILES_LIMIT = 10


def _short_mode(mode) -> str:
    """Grouping key from the persisted verbose mode string —
    ``"final (full review, ready for push)"`` -> ``"final"``.

    Delegated, not reimplemented: the token vocabulary and the rendering this
    undoes both live in ``critic_consolidate``. Lazy, because this fires only
    inside ``review-stats`` and importing the dispatcher for the sake of a
    string split would tax every other caller of this module."""
    from . import critic_consolidate  # noqa: PLC0415 — lazy; see the docstring

    return critic_consolidate.mode_token_of(mode)


# Model-id families. The dispatcher records whatever model string it passed, so
# the SAME model arrives under several ids — ``opus``, ``claude-opus-4-8``, and
# ``claude-opus-4-8[1m]`` are one model; ``fable``/``sonnet``/``haiku`` are
# distinct. review-stats groups by model to answer "is the deeper reviewer tier
# paying off?" (the reviewer-model A/B), so it MUST fold those aliases to one
# family or the dimension is pure noise. Substring match (not an exact map) so a
# new opus/sonnet *version* folds with no code change — the drift-resilience the
# reviewer-model fallback chains chose over pinned ids.
# PAUSED 2026-07-14: reviewer-model tiering was removed (emergency patch —
# reviewers now run on the session model), so the framework currently feeds this
# dimension only one family. The fold is retained unchanged for the planned
# restore of tiering (change-log "reviewer-session-model").
_MODEL_FAMILIES = ("opus", "sonnet", "haiku", "fable")


def _canonical_model(model) -> str | None:
    """Fold a recorded model-id to its Claude family for grouping.

    Returns the family label when one is recognized, the trimmed original when
    it isn't (forward-compat: an unfamiliar model stays visible, never silently
    bucketed under a known family), and ``None`` when no model was recorded.
    """
    if not isinstance(model, str) or not model.strip():
        return None
    lowered = model.lower()
    for family in _MODEL_FAMILIES:
        if family in lowered:
            return family
    return model.strip()


def _read_events(
    path: Path, since: "str | None" = None, until: "str | None" = None,
) -> "tuple[list[dict], dict, dict, str | None]":
    """All reportable ``review.*`` events oldest-first, skip counts, the
    learning-loop tallies, and the read failure if the file could not be
    opened at all.

    ``corrupt_lines``: unparseable JSON, a non-object line, or an envelope
    without a string ``event`` kind. ``unknown_kinds``: a valid envelope whose
    kind this report does not aggregate. ``invalid_payloads``: a kind it DOES
    aggregate whose payload is unusable — a ``review.*`` missing its findings
    list, or a ``learning.*`` with no ``unit_hash``, which can answer none of
    the four questions the learning events exist for.

    **The learning tallies ride this one pass.** They are counts, not events,
    so they do not join ``events_total`` (which means reviews and is read as
    such by every existing consumer); and they are not skips, because a
    counted thing is not a skipped one — bucketing them under
    ``unknown_kinds`` was honest only while nothing read them, and a channel
    produced and never consumed is a defect rather than an inefficiency.

    **The read failure is a third return value, not a fourth key in
    ``skipped``.** An unreadable file is not a skip count, and ``skipped`` is
    published verbatim inside ``review-stats --json`` — a registered payload
    whose key set is documented in ``api-contract.md``. Widening a public
    shape to carry an internal signal is how a payload acquires a key nobody
    registered, which is the defect this bundle's own review caught one
    command over.

    **The window scopes THIS pass, not its result.** Every tally here —
    reviews, skips and the learning counts — must describe the same
    population, or a windowed report prints whole-corpus learning and skip
    numbers under a banner saying it is a slice, and two windows summed by a
    `--json` consumer double-count them. Filtering after the fact re-scopes
    only whichever aggregate the filter happens to touch, which is the shape
    that makes a before/after split show identical numbers in both halves.
    """
    skipped = {"corrupt_lines": 0, "unknown_kinds": 0, "invalid_payloads": 0}
    learning = {"written": 0, "fired": 0}
    units: dict[str, set] = {"written": set(), "fired": set()}
    events: list[dict] = []

    def _finish() -> dict:
        return {
            "written": learning["written"],
            "fired": learning["fired"],
            "units_written": len(units["written"]),
            "units_fired": len(units["fired"]),
            # A SET difference, never a difference of sizes: the two sets are
            # not nested — a rule authored before the emitter shipped can fire
            # without ever being written — and on a migrated fleet repo they
            # are disjoint, where a size subtraction reads 0 forever.
            "units_uncited": len(units["written"] - units["fired"]),
        }

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        # Named for the file, not for one caller: `round_price` reads through
        # here too, so a `review-stats:` prefix would misattribute the failure
        # to a command the reader never ran.
        print(f"governance ledger unreadable ({exc})", file=sys.stderr)
        return events, skipped, _finish(), str(exc).strip()[:80]
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            skipped["corrupt_lines"] += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            skipped["corrupt_lines"] += 1
            continue
        # Before any counter moves: an out-of-window line is not this
        # report's business at all, so it is neither counted nor skipped.
        if not in_window(event.get("ts"), since, until):
            continue
        kind = event["event"]
        if kind in _LEARNING_KINDS:
            payload = event.get("learning")
            unit = payload.get("unit_hash") if isinstance(payload, dict) else None
            if not isinstance(unit, str) or not unit.strip():
                skipped["invalid_payloads"] += 1
                continue
            bucket = _LEARNING_KINDS[kind]
            learning[bucket] += 1
            units[bucket].add(unit)
            continue
        if not kind.startswith("review."):
            skipped["unknown_kinds"] += 1
            continue
        payload = event.get("review")
        if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
            skipped["invalid_payloads"] += 1
            continue
        events.append(event)
    return events, skipped, _finish(), None


def _measured_duration(event: dict) -> "float | None":
    """The interval this event's dispatch mark attests, or ``None``.

    The predicate itself lives in :func:`lib.review_dispatch.measured_interval_seconds`
    — one home, shared with the two `tools/` readers, because all three grade the
    same field for the same comparison and a per-reader copy diverges on the bound
    that makes it safe.
    """
    from .review_dispatch import measured_interval_seconds  # noqa: PLC0415 — lazy, as the module's other imports are

    return measured_interval_seconds(event.get("dispatched_at"), event.get("ts"))


def _extract_row(event: dict) -> dict:
    """The per-event record aggregation runs over (envelope + payload reads
    in one place, so every grouping sees identical values)."""
    actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
    model = actor.get("model")
    role = actor.get("role")
    duration = event.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        duration = None
    # Where the duration CAME FROM, which is a different question from what it
    # is. `dispatched_at` is a clock code read before the reviewer was spawned;
    # `duration_seconds` is the reviewing model's own recollection. Pooling the
    # two re-creates the hazard the field was added to retire, so provenance
    # travels with the row and every grouping reports the two populations apart.
    # Absence is NOT MEASURED, never zero — an event written before the field
    # existed says nothing about its own duration's provenance.
    measured = _measured_duration(event)
    scope = event.get("scope")
    findings = [f for f in event["review"]["findings"] if isinstance(f, dict)]
    # An inner-stage pass demotes what falls outside the inner BLOCKING set
    # into `observations`, so its `findings` undercount what it saw by
    # construction; the demoted count
    # is the only way an over-firing narrowing shows up here. None, not 0, when
    # the event carries no list — events written before the array was persisted
    # say nothing about demotion, and counting them as zero would read as a
    # narrowing that never fired.
    raw_observations = event["review"].get("observations")
    observations = (
        sum(1 for o in raw_observations if isinstance(o, dict))
        if isinstance(raw_observations, list) else None
    )
    severities = [
        f["severity"] if f.get("severity") in _SEVERITIES else "other"
        for f in findings
        if isinstance(f.get("severity"), str)
    ]
    # Does a finding SHIP A FIX PLAN? The severity label says how much a finding
    # is worth; the remedy beside it is what makes it read as work, and the two
    # can disagree — a NOTE carrying a finished fix plan is indistinguishable
    # from a WARNING at the point the builder decides what to do. Counted here
    # so a change to the severity contract can be graded on what reviewers
    # actually write rather than on what the protocol tells them to.
    # Three outcomes, not two. ABSENT (no `recommendation` key at all) is not
    # the same claim as BLANK (the key is there and says nothing): the PR
    # reviewer's findings carry `{goal, severity, file, line, summary}` and have
    # no remedy field in their schema, so folding absence into "wrote no
    # remedy" reports that role at 0% — a statement about its behaviour that
    # its schema makes meaningless. BLANK, by contrast, does count as no
    # remedy — a field present and saying nothing is not a fix plan, and
    # treating it as one would report the contract already satisfied. Counted
    # apart so a rate is only ever computed over findings whose contract HAS
    # the field.
    remedies = []
    for f in findings:
        if not isinstance(f.get("severity"), str):
            continue
        sev = f["severity"] if f["severity"] in _SEVERITIES else "other"
        if "recommendation" not in f:
            remedies.append((sev, "absent", None))
            continue
        rec = f.get("recommendation")
        rec = rec.strip() if isinstance(rec, str) else ""
        if rec:
            remedies.append((sev, "present", len(rec.split())))
        else:
            remedies.append((sev, "blank", None))
    # Read, never derived from the mode: `critic-begin` is the one home of the
    # mode → stage mapping, and an event that predates the field says nothing
    # about its stage. Deriving it here would silently backfill history with a
    # mapping this reader would then own a second copy of.
    stage = event["review"].get("stage")
    return {
        "role": role if isinstance(role, str) else None,
        "model": _canonical_model(model),
        "mode": _short_mode(event["review"].get("mode")),
        "stage": stage if stage in _STAGES else None,
        "scope": scope if isinstance(scope, str) else None,
        "duration": duration,
        # The measured interval where there is one, else None — never a fallback
        # to the estimate, because the whole point is that the two are counted
        # separately.
        "duration_measured": measured,
        "severities": severities,
        "remedies": remedies,
        "findings": findings,
        "observations": observations,
    }


def _population(values: list) -> dict:
    """One duration population's count and median. ``reviews: 0`` with a null
    median is the honest rendering of an empty one — never a zero median, which
    reads as reviews that took no time."""
    return {
        "reviews": len(values),
        "total_seconds": round(sum(values), 1) if values else 0,
        "median_seconds": round(median(values), 1) if values else None,
    }


def _group_stats(rows: list[dict]) -> dict:
    """The stat block every grouping (overall / role×model×mode / scope)
    shares: review count, duration totals, findings by severity,
    actionable rate, findings-per-review."""
    durations = [r["duration"] for r in rows if r["duration"] is not None]
    by_severity = {sev: 0 for sev in (*_SEVERITIES, "other")}
    actionable_reviews = 0
    total_findings = 0
    for r in rows:
        for sev in r["severities"]:
            by_severity[sev] += 1
        total_findings += len(r["severities"])
        if any(sev in _ACTIONABLE for sev in r["severities"]):
            actionable_reviews += 1
    # Per severity: how many findings carry a remedy, and how long it runs.
    # `rate` and `median_words` are None rather than 0 when the severity had no
    # findings at all — "nobody wrote one" and "there was nothing to write one
    # for" are different answers, and a 0% that means the latter reads as the
    # contract already holding.
    remedy_words: dict[str, list[int]] = {sev: [] for sev in (*_SEVERITIES, "other")}
    remedy_kinds: dict[str, dict] = {
        sev: {"present": 0, "blank": 0, "absent": 0} for sev in (*_SEVERITIES, "other")
    }
    for r in rows:
        for sev, kind, words in r["remedies"]:
            remedy_kinds[sev][kind] += 1
            if words is not None:
                remedy_words[sev].append(words)
    remedies = {}
    for sev in (*_SEVERITIES, "other"):
        kinds, words = remedy_kinds[sev], remedy_words[sev]
        total = kinds["present"] + kinds["blank"] + kinds["absent"]
        # The denominator is findings whose schema CARRIES the field. All-absent
        # means the question does not apply to this population, which is a null,
        # never a zero.
        eligible = kinds["present"] + kinds["blank"]
        remedies[sev] = {
            "findings": total,
            "with_remedy": kinds["present"],
            "blank_remedy": kinds["blank"],
            "no_remedy_field": kinds["absent"],
            "rate": round(kinds["present"] / eligible, 3) if eligible else None,
            "median_words": round(median(words), 1) if words else None,
        }
    recording = [r["observations"] for r in rows if r["observations"] is not None]
    # The two populations, never pooled. `duration_total_seconds` and
    # `duration_median_seconds` below are the POOLED figures every existing
    # consumer already reads; they are kept because dropping a published key is a
    # breaking change, but a caller grading a protocol change reads the split —
    # a median over a mixture of clock readings and model recollections is not a
    # measurement of anything.
    measured = [r["duration_measured"] for r in rows if r["duration_measured"] is not None]
    self_reported = [
        r["duration"] for r in rows
        if r["duration"] is not None and r["duration_measured"] is None
    ]
    n = len(rows)
    return {
        "reviews": n,
        "duration_total_seconds": round(sum(durations), 1) if durations else 0,
        "duration_median_seconds": round(median(durations), 1) if durations else None,
        "duration_measured": _population(measured),
        "duration_self_reported": _population(self_reported),
        "findings": by_severity,
        "remedies": remedies,
        "findings_per_review": round(total_findings / n, 2) if n else 0.0,
        "actionable_rate": round(actionable_reviews / n, 3) if n else 0.0,
        "observations": sum(recording),
        "reviews_recording_observations": len(recording),
    }


def _top_files(rows: list[dict]) -> tuple[list[dict], int]:
    """Findings-by-file rollup from per-finding ``files`` attribution —
    (top entries by actionable findings, total attributed paths)."""
    per_path: dict[str, dict[str, int]] = {}
    for r in rows:
        for finding in r["findings"]:
            files = finding.get("files")
            if not isinstance(files, list):
                continue
            actionable = finding.get("severity") in _ACTIONABLE
            for path in files:
                if not isinstance(path, str) or not path.strip():
                    continue
                entry = per_path.setdefault(path, {"actionable_findings": 0, "findings": 0})
                entry["findings"] += 1
                if actionable:
                    entry["actionable_findings"] += 1
    ranked = sorted(
        ({"path": path, **counts} for path, counts in per_path.items()),
        key=lambda e: (-e["actionable_findings"], -e["findings"], e["path"]),
    )
    return ranked[:TOP_FILES_LIMIT], len(per_path)


# The mode a fix commit actually buys. Committing a fix extends HEAD, so the
# cheapest thing that re-closes coverage is ONE `verify-resolutions` pass — a
# cumulative is what a *widened* delta or a lost anchor costs, not what an
# ordinary fix costs. Pricing on any other mode would quote the builder a
# number they will not pay, which is worse than quoting none.
#
# Its knowing understatement, recorded rather than left to be rediscovered: a
# branch with NO prior review has no anchor for a delta pass, so the round that
# closes its gate is a full `cumulative` — the more expensive mode. The quoted
# figure is therefore a floor there, not the price. The callers say "the
# cheapest round that closes it" for that reason; widening the quote to the
# worst case would overprice the common path, which is the case this exists to
# make legible.
PRICED_MODE = "verify-resolutions"

# Below this many recorded rounds a median is one or two runs wearing a
# statistic's clothes. A wrong price is worse than no price here: the whole
# reason this is computed rather than written down is that a stale or
# unrepresentative number drifts and then costs a round to correct — so a thin
# sample reports unavailable rather than guessing.
MIN_PRICED_SAMPLE = 5


def round_price(prawduct_dir: Path, *, mode: str = PRICED_MODE) -> dict:
    """What one more review round costs in THIS repo, derived from its own
    ledger at call time.

    **Why this is derived and never written down.** The price is the single
    most quotable fact in the loop-termination argument, and quoting it is
    exactly how the framework has burned itself before: a number copied into
    prose drifts from the thing it describes, and correcting it costs a review
    round — the very round this helper exists to stop a builder from spending
    (``core.md``: cite the command that re-derives a number, never the
    digits; ``project-preferences.md`` forbids the sibling suite-total claim
    for the same stated reason). So there is one home for the fact and no
    copies: callers ask, they never assert.

    Returns either

    - ``{"status": "priced", "mode", "median_seconds", "reviews"}`` — the
      median duration of the rounds this repo has actually recorded, with the
      sample size it rests on, so a caller can show its work; or
    - ``{"status": "unavailable", "reason"}`` — no ledger, no rounds of this
      mode, none carrying a duration, or too few to be worth quoting.

    **Provenance, recorded so the figure is not defended as more than it is.**
    ``duration_seconds`` reaches the ledger from the reviewer's own partial —
    ``build_fact_body`` takes ``max()`` over the partials, and the reviewer
    contract asks for a best-estimate wall-clock. So this is a median of
    self-reported estimates, not of measured time, and estimates cluster on
    round numbers. It is the right order of magnitude and the honest thing to
    quote today; making it *measurable* means timing the
    ``critic-begin``→``critic-consolidate`` interval in code instead of
    trusting the partial, which is a change to what gets recorded and not to
    what gets read here.

    Unavailable is a first-class answer, not a failure: this is advice, and
    advice fails soft (``architecture.md`` § Direction). It is deliberately
    distinguishable from "free" by callers, because an advisory that goes
    quiet when it breaks manufactures the false confidence it was meant to
    prevent (``core.md``: "advice fails soft" is not "advice fails
    silent").
    """
    path = ledger_path(prawduct_dir)
    if not path.is_file():
        return {"status": "unavailable", "reason": "this repo has no recorded review history yet"}
    events, skipped, _learning, unreadable = _read_events(path)
    # An unreadable ledger is not an empty one. Both produce zero durations, but
    # only one of them is honestly described as "no round records how long it
    # took" — and this reason is PERSISTED into the findings cache, the ledger
    # event and the briefing, where the wrong one reads as a repo with no
    # review history.
    if unreadable:
        return {
            "status": "unavailable",
            "reason": f"this repo's governance ledger could not be read ({unreadable})",
        }
    durations = [
        row["duration"]
        for row in (_extract_row(e) for e in events)
        if row["mode"] == mode and row["duration"] is not None
    ]
    if not durations:
        return {
            "status": "unavailable",
            "reason": f"no {mode} round in this repo's history records how long it took",
        }
    if len(durations) < MIN_PRICED_SAMPLE:
        return {
            "status": "unavailable",
            "reason": (
                f"only {len(durations)} timed {mode} round(s) recorded — too few to quote "
                f"as this repo's price"
            ),
        }
    return {
        "status": "priced",
        "mode": mode,
        "median_seconds": round(median(durations), 1),
        "reviews": len(durations),
    }


def format_minutes(seconds: float) -> str:
    """Render a duration for a reader, in the one place that does it.

    Two near-identical renderings of this quantity shipped in one bundle and
    only one carried the sub-minute guard, so the surface that literally states
    the price could emit "about 0 min" — the false-confidence failure the whole
    round-pricing scope exists to prevent, delivered by its own carrier. The
    *fact* had one home; its *rendering* had two. This is the one home for the
    rendering, and the guard cannot be present in one caller and absent in the
    other because there is no longer an "other".
    """
    minutes = seconds / 60.0
    return "under a minute" if minutes < 1 else f"about {minutes:.0f} min"


def format_round_price(price: dict) -> str:
    """One sentence naming what a round costs, for the messages a builder
    meets at the moment of deciding to spend one.

    Shared by every caller so the phrasing cannot drift between the CLI
    verdict, the gate, and the findings cache — and so the command that
    re-derives the figure is always cited beside it.
    """
    if price.get("status") != "priced":
        return (
            f"What one more round costs here is unavailable ({price.get('reason', 'unknown')}) "
            f"— that is a missing number, not a small one."
        )
    return (
        f"One more round costs {format_minutes(price['median_seconds'])} here (median "
        f"of {price['reviews']} recorded {price['mode']} rounds; re-derive with "
        f"`prawduct-hook review-stats`)."
    )


def aggregate_review_stats(
    events: list[dict], skipped: dict, learning: "dict | None" = None
) -> dict:
    """The report body (everything below the ``project``/``generated_at``
    header the CLI adds) — pure, deterministic, fully derived from its inputs.

    ``learning`` is the tally :func:`_read_events` counted on the same pass;
    omitted, the block renders as zeros, which is the honest reading for a
    ledger holding no learning events."""
    rows = [_extract_row(e) for e in events]

    by_rmm: dict[tuple, list[dict]] = {}
    by_scope: dict[str | None, list[dict]] = {}
    by_stage: dict[str | None, list[dict]] = {}
    for row in rows:
        by_rmm.setdefault((row["role"], row["model"], row["mode"]), []).append(row)
        by_scope.setdefault(row["scope"], []).append(row)
        by_stage.setdefault(row["stage"], []).append(row)

    top_files, files_attributed_total = _top_files(rows)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "events_total": len(rows),
        "skipped": dict(skipped),
        "overall": _group_stats(rows),
        "by_role_model_mode": [
            {"role": role, "model": model, "mode": mode, **_group_stats(group)}
            for (role, model, mode), group in sorted(
                by_rmm.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "", kv[0][2])
            )
        ],
        "by_scope": [
            {"scope": scope, **_group_stats(group)}
            for scope, group in sorted(by_scope.items(), key=lambda kv: kv[0] or "")
        ],
        # The yield query the stage-keyed rigor norm was drawn to answer: what
        # each stage finds, and what the inner stage demotes. Recorded stages
        # first in their own order, the unrecorded bucket last — an event
        # written before the field existed is "not measured", never a stage.
        "by_stage": [
            {"stage": stage, **_group_stats(group)}
            for stage, group in sorted(
                by_stage.items(),
                key=lambda kv: _STAGES.index(kv[0]) if kv[0] in _STAGES else len(_STAGES),
            )
        ],
        "top_files": top_files,
        "files_attributed_total": files_attributed_total,
        # The learning loop's own numbers. `written`/`fired` count EVENTS and
        # `units_*` count distinct rules, and the pair is the point: `written`
        # over `units_written` is how often one rule is re-recorded across
        # sessions, and `units_uncited` — the SET of written units minus the set
        # of fired ones — is the rules no review has ever cited, which is the
        # question the corpus cannot ask itself.
        "learning": dict(
            learning
            if learning is not None
            else {"written": 0, "fired": 0, "units_written": 0, "units_fired": 0, "units_uncited": 0}
        ),
    }


def _fmt_stats(stats: dict) -> str:
    """One stat block as a human line fragment (shared by every grouping)."""
    f = stats["findings"]
    meas, self_rep = stats["duration_measured"], stats["duration_self_reported"]
    med = stats["duration_median_seconds"]
    pct = round(stats["actionable_rate"] * 100)
    recording = stats["reviews_recording_observations"]
    observations = (
        f"observations {stats['observations']} in {recording} recording review(s)"
        if recording else "observations not recorded"
    )
    # Provenance is stated wherever a duration is, so a reader cannot take a
    # median for a measurement without being told how much of it was measured.
    provenance = (
        f"measured {meas['reviews']}"
        + (f" (median {meas['median_seconds']}s)" if meas["median_seconds"] is not None else "")
        + f", self-reported {self_rep['reviews']}"
        + (f" (median {self_rep['median_seconds']}s)" if self_rep["median_seconds"] is not None else "")
    )
    return (
        f"{stats['reviews']} review(s) | duration total {stats['duration_total_seconds']}s, "
        f"median {med if med is not None else '-'}s [{provenance}] | "
        f"B/W/N/other {f['blocking']}/{f['warning']}/{f['note']}/{f['other']} | "
        f"actionable {pct}% | {stats['findings_per_review']} findings/review | "
        f"{observations}"
    )


def _window_line(window: dict) -> list[str]:
    """The windowed banner, or nothing at all.

    A windowed report and a whole-corpus one are otherwise the same shape, and a
    reader who cannot tell them apart will compare one against the other — which
    is the mistake a before/after measurement exists to avoid. Printed loudly
    rather than as a footnote for that reason.
    """
    since, until = window.get("since"), window.get("until")
    if not since and not until:
        return []
    span = f"{since or 'the beginning'} .. {until or 'now'}"
    return [f"WINDOW: {span} — this is a SLICE, not the whole corpus"]


def _fmt_remedies(remedies: dict) -> str:
    """Per severity: how often a finding ships a fix plan, and how long it runs.

    `n/a` is not 0% — it is the answer for a population whose findings carry no
    `recommendation` field at all (the PR reviewer's schema), where a rate would
    be a claim about behaviour the schema cannot support.
    """
    parts = []
    for sev in (*_SEVERITIES, "other"):
        d = remedies.get(sev) or {}
        if not d.get("findings"):
            continue
        if d.get("rate") is None:
            parts.append(f"{sev} n/a ({d['no_remedy_field']} with no remedy field)")
            continue
        pct = round(d["rate"] * 100)
        words = d["median_words"]
        frag = f"{sev} {pct}% of {d['with_remedy'] + d['blank_remedy']}"
        if words is not None:
            frag += f", median {words:g} words"
        if d.get("no_remedy_field"):
            frag += f" (+{d['no_remedy_field']} no field)"
        parts.append(frag)
    return " | ".join(parts) if parts else "(no findings)"


def _render_human(report: dict, ledger_rel: str) -> str:
    sk = report["skipped"]
    lines = [
        f"review-stats — {report['project']} ({ledger_rel})",
        f"events: {report['events_total']} review event(s); skipped: "
        f"{sk['corrupt_lines']} corrupt line(s), {sk['unknown_kinds']} unknown kind(s), "
        f"{sk['invalid_payloads']} invalid payload(s)",
        *_window_line(report.get("window") or {}),
        "",
        f"overall: {_fmt_stats(report['overall'])}",
        f"remedies: {_fmt_remedies(report['overall']['remedies'])}",
        "",
        "by role x model x mode:",
    ]
    for entry in report["by_role_model_mode"]:
        label = f"{entry['role'] or '(unknown)'} / {entry['model'] or '(unknown)'} / {entry['mode']}"
        lines.append(f"  {label}: {_fmt_stats(entry)}")
    lines += ["", "by scope:"]
    for entry in report["by_scope"]:
        lines.append(f"  {entry['scope'] or '(none)'}: {_fmt_stats(entry)}")
    lines += ["", "by stage:"]
    for entry in report["by_stage"]:
        lines.append(f"  {entry['stage'] or '(unrecorded)'}: {_fmt_stats(entry)}")
    lines += ["", f"top files by actionable findings (cap {TOP_FILES_LIMIT}):"]
    if report["top_files"]:
        for entry in report["top_files"]:
            lines.append(
                f"  {entry['path']}: {entry['actionable_findings']} actionable / "
                f"{entry['findings']} total"
            )
        shown = len(report["top_files"])
        if report["files_attributed_total"] > shown:
            lines.append(
                f"  (+{report['files_attributed_total'] - shown} more attributed path(s) below the cap)"
            )
    else:
        lines.append("  (none — no finding carries file attribution yet)")
    lg = report["learning"]
    # Both halves on one line, because the useful number is the DIFFERENCE:
    # rules written that no review has ever cited. Printing only the totals
    # would make a reader do the subtraction, and a reader who has to compute
    # the answer mostly does not.
    lines += ["", (
        f"learning loop: {lg['written']} rule write(s) over {lg['units_written']} "
        f"distinct rule(s); {lg['fired']} citation(s) over {lg['units_fired']} "
        f"distinct rule(s) — {lg['units_uncited']} "
        "written rule(s) no review has cited"
    )]
    return "\n".join(lines)


def review_stats(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook review-stats [--json]`` — see module docstring.

    Exit 0 always when the report can be produced, including a missing ledger
    ("no review history" is an answer, not an error); exit 1 only on bad args.
    """
    usage = "usage: review-stats [--json] [--since <stamp>] [--until <stamp>]"
    as_json = False
    since = until = None
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--json":
            as_json = True
        elif arg in ("--since", "--until"):
            if not rest:
                print(f"review-stats: {arg} needs a value ({usage})", file=sys.stderr)
                return 1
            value = rest.pop(0)
            # Refuse a bound this reader cannot interpret rather than filtering
            # on it as a bare string. A window is read as a before/after
            # comparison, so a bound that silently means something other than
            # what was typed moves events between the two halves and the
            # resulting delta is attributed to the change under test.
            if not is_usable_bound(value):
                print(
                    f"review-stats: {arg} value {value!r} is not a date, month or"
                    f" ISO timestamp ({usage})",
                    file=sys.stderr,
                )
                return 1
            if arg == "--since":
                since = value
            else:
                until = value
        else:
            print(f"review-stats: unknown argument {arg!r} ({usage})", file=sys.stderr)
            return 1

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    path = ledger_path(prawduct_dir)
    if path.is_file():
        # The read failure is already reported to stderr by `_read_events`, and
        # this report's own contract is honest COUNTS — an unreadable ledger
        # renders as the empty report it truthfully is, with the cause on
        # stderr beside it. `round_price` is the caller that must distinguish
        # them, because its reason string gets persisted.
        events, skipped, learning, _unreadable = _read_events(path, since, until)
    else:
        events, skipped = [], {"corrupt_lines": 0, "unknown_kinds": 0, "invalid_payloads": 0}
        learning = {"written": 0, "fired": 0, "units_written": 0, "units_fired": 0, "units_uncited": 0}

    report = aggregate_review_stats(events, skipped, learning)
    # Header fields the pure aggregation can't know — added once, here, so the
    # JSON and human renderings always agree.
    report = {
        "schema_version": report.pop("schema_version"),
        "project": project_dir.resolve().name,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Stated even when null. A windowed report and a whole-corpus one are
        # the same shape, and a consumer that cannot tell them apart will
        # compare one against the other.
        "window": {"since": since, "until": until},
        **report,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return 0
    if not path.is_file():
        print(f"no review history ({path.name} not found — reviews append to it via ledger-append)")
        return 0
    print(_render_human(report, f".prawduct/{path.name}"))
    return 0
