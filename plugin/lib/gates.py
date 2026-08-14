"""Session-end governance gates + test-evidence/critic-findings validators.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 6). Holds the gate
*decision helpers* the Stop hook orchestrates — test-evidence currency + schema
validation, the critic-findings cache schema (validated at its writers:
``critic-consolidate`` and ``ledger-append``), the kernel-v3 composition
gates, build-plan chunk counting, and the trivial/build-plan state probes —
plus the four self-contained gate CLI commands (``test_status`` /
``validate_evidence`` / ``check_cumulative_critic`` / ``verify_coverage``).
The hook keeps thin ``cmd_*`` wrappers delegating here via the lazy
``_gates()`` accessor.

**Review gates answer by composition** (kernel-v3-evidence-design.md D6,
chunk 04). Both review gates load facts via ``lib.evidence`` and delegate the
verdict to ``lib.coverage_algebra`` — the PR gate asks Q1 (does composed
coverage span merge-base tree → HEAD tree with zero unresolved blocking
findings?), the Stop-hook Critic gate asks Q2 (session base tree → current
working tree). No gate reads ``.critic-findings.json`` (a derived cache for
builders/briefings, D7), branches on a review's mode label, or compares file
mtimes against ``.session-start`` — those mechanisms (mode-label acceptance,
``extends_cumulative`` chains, ``_record_covers_head``, verify-resolutions
scope subsets, the ledger fallback) are deleted by design, not preserved.

``cmd_stop`` itself STAYS in the hook (it is the deliberately-inline hot-path
gate per design constraint 1 + Chunk 7, and it uses the hook-resident gate
*attribution* machinery shared with ``cmd_clear``); it calls these helpers via
``_gates()``. ``_has_active_build_plan_file`` and ``_is_trivial_fileset_eligible``
were reassigned here (they are gate logic, lib-clean) from the briefing region.

Depends on its lib siblings ``gitstate`` / ``coverage`` / ``buildplan_refs``
(build-plan Status parsing, including ``_count_build_plan_chunks``),
``evidence`` / ``coverage_algebra`` (the v3 data plane), and ``core``
(``read_bool_yaml_key`` — canonical twin of the hook's parity-pinned inline
mirror), plus the stdlib.
"""


from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from . import (
    buildplan_refs,
    coverage,
    coverage_algebra,
    evidence,
    gitstate,
    verdict_cache,
)
from .core import read_bool_yaml_key


_EVIDENCE_REQUIRED_FIELDS: dict[str, tuple[type, ...]] = {
    "timestamp": (str,),
    "passed": (int,),
    "failed": (int,),
    "skipped": (int,),
    "duration_seconds": (int, float),
    "command": (str,),
}
_EVIDENCE_COVERAGE_FIELDS: dict[str, tuple[type, ...]] = {
    "verifier": (str,),
    "tests_executed": (list,),
    "changes_referenced": (list,),
    "coverage_level": (str,),
}
_EVIDENCE_COVERAGE_LEVELS = frozenset({"referenced", "executed"})
# Optional fields — validated when present, never required. ``changes_unjudged``
# (gate-soundness ch.1) lists changed files the evidence producer structurally
# cannot judge (non-Python, symbol-less, deleted); absent means empty, so
# product-authored evidence and ``executed``-level verifiers that predate the
# field keep their existing gate behavior.
_EVIDENCE_OPTIONAL_FIELDS: dict[str, tuple[type, ...]] = {
    "changes_unjudged": (list,),
    # ``evidence_tree`` (spike-tree-validated-test-evidence.md): the working-tree
    # SHA the recorded run ran against, captured via ``evidence.capture_tree`` at
    # ``record`` time. Consumed ONLY by the additive tree-validity clause in
    # ``tests_are_current`` — a str when present, always omitted (never null) when
    # capture failed or the on-ramp is ``--from-counts``, so old and count-only
    # records keep exactly their pre-clause timestamp-only behavior.
    "evidence_tree": (str,),
}


def _load_test_evidence(prawduct_dir: Path) -> "tuple[dict | None, str]":
    """The saved test-evidence record, or ``(None, reason)`` saying why not.

    The prologue both evidence readers need: on disk, parseable, an object, a
    valid schema, and no failures. It lives here rather than in each because the
    two gates that read it — session-freshness and the base-advance transfer —
    must agree about what a saved run SAYS before they can disagree about what
    it vouches FOR; a new schema field or a different reading of ``failed``
    landing in one reader and not the other is how they come to answer
    differently about the same file.

    The schema check catches writer typos (``ran_at`` for ``timestamp``,
    ``num_passed`` for ``passed``): without it a missing field falls through
    ``.get()`` and the record parses as "no failures, no timestamp", which the
    caller then rejects for the wrong reason.
    """
    evidence_path = prawduct_dir / ".test-evidence.json"
    if not evidence_path.is_file():
        return None, "no .test-evidence.json on disk"
    try:
        record = json.loads(evidence_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"unreadable evidence ({exc})"
    if not isinstance(record, dict):
        return None, "evidence is not a JSON object"
    schema_ok, schema_err = _validate_evidence_schema(record)
    if not schema_ok:
        return None, schema_err
    failed = record.get("failed")
    if isinstance(failed, int) and failed > 0:
        return None, f"{failed} test(s) failing in saved evidence"
    return record, ""


def tests_are_current(project_dir: Path) -> tuple[bool, str]:
    """Decide whether saved test evidence is fresh enough to trust.

    Two ways evidence is current, either sufficient (a disjunction), with
    ``failed == 0`` required for both:

    1. **Session-fresh** — written during this session (timestamp >= session
       start). The "trust the cycle" model: write code → run tests → Critic
       reviews is the trust boundary.
    2. **Tree-valid** — the judgeable-scoped working tree is byte-identical to
       the tree the recorded run ran against (:func:`_test_evidence_tree_valid`).
       An *additive* clause (spike-tree-validated-test-evidence.md) that only
       ever relaxes a timestamp-stale verdict to current, never the reverse:
       structurally incapable of a false stale, the failure class that retired
       the removed content-hash "fingerprint" and ``git_sha`` mechanisms. It
       classifies *paths* (git tree-diff + ``is_judgeable_path``), never file
       *contents* — the standing ``coverage_algebra`` rule that kept those
       mechanisms dead. Records without ``evidence_tree`` (pre-clause, or a
       ``--from-counts`` on-ramp) skip clause 2 and behave exactly as before.

    Falls back to timestamp-only comparison when no session-start marker
    exists (e.g., running outside a governed session).

    Returns (is_current, reason). reason is a short human-readable string suitable
    for printing back to the agent.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    evidence, why_not = _load_test_evidence(prawduct_dir)
    if evidence is None:
        return False, why_not

    # Timestamp check — evidence must have been written during this session.
    evidence_ts = evidence.get("timestamp")
    if not isinstance(evidence_ts, str) or not evidence_ts:
        return False, "no timestamp in evidence"

    session_start = _read_session_start(prawduct_dir)
    if session_start:
        if evidence_ts >= session_start:
            return True, f"evidence from this session ({evidence_ts})"
        # Timestamp-stale — but the additive tree-validity clause can still
        # vouch when nothing judgeable has changed since the recorded run. A
        # relax-only disjunction: it can only turn this stale into current,
        # never the reverse, so it cannot manufacture a false stale.
        recorded_tree = evidence.get("evidence_tree")
        if isinstance(recorded_tree, str) and recorded_tree:
            tree_valid, tree_reason = _test_evidence_tree_valid(project_dir, recorded_tree)
            if tree_valid:
                return True, f"tree-valid despite predating session: {tree_reason}"
        return False, f"evidence predates session ({evidence_ts} < {session_start})"

    # No session-start marker — fall back to recency check.
    # Evidence exists with passing tests and a timestamp, but we can't verify
    # it's from this session. Accept it with a note.
    return True, f"evidence has passing tests ({evidence_ts}, no session marker to verify)"


def _test_evidence_tree_valid(
    project_dir: Path, recorded_tree: str, target_tree: "str | None" = None
) -> tuple[bool, str]:
    """Additive tree-validity clause for :func:`tests_are_current` (clause 2).

    ``target_tree`` names the tree the recorded run is compared AGAINST;
    ``None`` (the default, and every ``tests_are_current`` call) captures the
    current working tree. :func:`suite_vouches_for_tree` passes the tree its
    calling gate composes to, which is not always the working tree — so the two
    differ only in *which* tree, and share this one body. They read the same
    comparison because it is the same comparison; the wording differs because
    the reason is printed to a builder who needs to know which tree was meant.

    Test evidence is *tree-valid* when the judgeable-scoped diff between the
    working tree the recorded run ran against (``recorded_tree``) and the
    current working tree is empty — nothing that needs test coverage changed
    since the run, so the recorded pass still covers the current state. Uses
    the same primitives the v3 review gates trust: ``evidence.capture_tree``
    (temp index, never touches the session — R1), ``evidence.tree_diff``
    (git-native ``diff --name-only``), and ``coverage_algebra.judgeable_files``
    (metadata/session churn and non-protected ``.md`` are not judgeable, so
    the record's own ``.prawduct/.test-evidence.json`` write and doc edits are
    filtered out). Classifies paths, never file contents.

    Fails toward *not valid* (the caller keeps the timestamp verdict) whenever
    the tree cannot be captured or diffed, so a git failure can only leave
    evidence stale — never flip it fresh. Returns ``(is_valid, reason)``.
    """
    if target_tree is None:
        capture = evidence.capture_tree(project_dir)
        if capture.get("status") != "ok":
            return False, f"cannot capture the working tree ({capture.get('reason', 'unknown')})"
        target_tree = capture["tree"]
        same = f"working tree identical to the recorded run ({recorded_tree[:12]})"
        differ = "changed since the run"
        clean = "only non-judgeable paths changed since the run"
    else:
        same = f"the suite ran against this exact tree ({recorded_tree[:12]})"
        differ = "differ between the saved run and the tree this gate vouches for"
        clean = (
            "only non-judgeable paths differ between the saved run and "
            f"{target_tree[:12]}"
        )
    if target_tree == recorded_tree:
        return True, same
    changed = evidence.tree_diff(project_dir, recorded_tree, target_tree)
    if changed is None:
        return False, "tree diff unavailable (missing object or git failure)"
    judgeable = coverage_algebra.judgeable_files(changed)
    if judgeable:
        preview = ", ".join(judgeable[:3]) + ("…" if len(judgeable) > 3 else "")
        return False, f"{len(judgeable)} judgeable path(s) {differ} ({preview})"
    return True, f"{clean} ({len(changed)} metadata/doc file(s))"


def suite_vouches_for_tree(
    project_dir: Path, target_tree: "str | None" = None
) -> tuple[bool, str]:
    """Did the saved suite run actually run against *this* tree?

    Deliberately STRICTER than :func:`tests_are_current`, and the difference is
    the whole point. That function is a disjunction, and its first disjunct —
    session-freshness — asks only *when* the run happened. That is the right
    question for "should this session re-run the suite": the trust model there
    is write code → run tests → Critic reviews, and a run from earlier in the
    same session is inside the cycle.

    It is the wrong question for the base-advance transfer
    (:func:`coverage.diagnose_base_advance_transfer`), whose third condition
    exists to price ONE specific exposure: a reviewed diff meeting an advanced
    base in files nobody re-read. Suite at 09:00, base merged at 11:00, gate at
    11:05 satisfies session-freshness while no run has ever seen the merged
    tree — so the condition would vouch for exactly the state it was added to
    cover, and the pass message's "suite current" would be true of the clock and
    false of the repo.

    So only the tree-validity clause counts here: the run's recorded
    ``evidence_tree`` must be judgeable-identical to the tree in question — see
    ``target_tree`` below for which tree that is. Evidence with no ``evidence_tree`` —
    pre-clause records, and the ``--from-counts`` on-ramp — cannot answer the
    question at all, so it denies rather than falling back to timing.

    **``target_tree`` is the tree the CALLING GATE vouches for, and the two
    gates do not agree on it.** The PR gate composes to ``HEAD^{tree}``; the
    Stop gate composes to the working tree. Defaulting to the working tree for
    both looked harmless and is not: with a dirty tree they differ, so a suite
    run that met the working tree would have vouched for HEAD at the PR gate
    while never having seen it. Passing the target makes each gate check the
    tree it is actually about. ``None`` means the working tree.

    Returns ``(vouches, reason)``; the reason is printed either way, because a
    denial here is the cheapest remedy the gate has to offer.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    record, why_not = _load_test_evidence(prawduct_dir)
    if record is None:
        return False, why_not
    recorded_tree = record.get("evidence_tree")
    if not isinstance(recorded_tree, str) or not recorded_tree:
        return False, (
            "the saved run records no evidence_tree, so nothing can say which "
            "tree it ran against — re-run the suite (or restamp with "
            "`test-evidence record --no-rerun`) so the transfer has a tree to check"
        )
    # `None` means the working tree, which is the Stop gate's own target and
    # which the comparison captures for itself.
    return _test_evidence_tree_valid(project_dir, recorded_tree, target_tree)


def _read_session_start(prawduct_dir: Path) -> str:
    """Content of the ``.session-start`` marker, or ``""`` when the marker is
    missing or unreadable. Used by the test-evidence freshness check
    (:func:`tests_are_current`), which compares ISO-8601 UTC strings
    against it."""
    try:
        return (prawduct_dir / ".session-start").read_text().strip()
    except OSError:
        return ""


def _validate_evidence_schema(evidence: dict) -> tuple[bool, str]:
    """Reject ``.test-evidence.json`` with missing or wrong-typed fields.

    Catches writer typos that would otherwise silently parse via ``.get()``.
    Examples this catches: ``ran_at`` instead of ``timestamp``; ``num_passed``
    instead of ``passed``; passed/failed/skipped emitted as strings.

    v1.4 F4a: the coverage-evidence fields (``verifier`` / ``tests_executed`` /
    ``changes_referenced`` / ``coverage_level``) are required on every record.
    The pre-v1.4 compat path — which accepted ``verifier``-less "legacy"
    evidence (historically called "fingerprint", a tree-hash mechanism removed
    pre-v1.4) — was dropped in M4 when the file-sync engine was retired: the
    plugin runtime always emits the full F4a shape, so there is no remaining
    writer that produces the legacy shape.

    Returns ``(True, "")`` on success, ``(False, reason)`` on failure. Missing
    fields are reported before wrong-typed fields, so a single fix-it pass
    addresses the highest-priority violations first.
    """
    required = {**_EVIDENCE_REQUIRED_FIELDS, **_EVIDENCE_COVERAGE_FIELDS}

    missing: list[str] = []
    wrong_type: list[str] = []
    for field, allowed_types in required.items():
        if field not in evidence:
            missing.append(field)
            continue
        value = evidence[field]
        # TST-1D5W: bool is a subclass of int, so a writer that emits
        # ``{"passed": true}`` would slip through ``isinstance(value, int)`` and
        # be silently read as the integer 1. Reject a bool wherever the field
        # does not explicitly allow it (none of the numeric fields do) — a JSON
        # boolean in a count/duration slot is always writer drift, not a real
        # test count.
        bool_in_int_slot = (
            isinstance(value, bool) and bool not in allowed_types
        )
        if bool_in_int_slot or not isinstance(value, allowed_types):
            wrong_type.append(
                f"{field} must be {' | '.join(t.__name__ for t in allowed_types)}, "
                f"got {type(value).__name__}"
            )
    for field, allowed_types in _EVIDENCE_OPTIONAL_FIELDS.items():
        if field in evidence and not isinstance(evidence[field], allowed_types):
            wrong_type.append(
                f"{field} must be {' | '.join(t.__name__ for t in allowed_types)}, "
                f"got {type(evidence[field]).__name__}"
            )

    if missing:
        return False, f"evidence missing required field(s): {', '.join(sorted(missing))}"
    if wrong_type:
        return False, f"evidence schema violation: {'; '.join(wrong_type)}"

    # Enum check for coverage_level — the field's type is already known good
    # (str) from the loop above; here we just refuse out-of-set values.
    level = evidence.get("coverage_level")
    if isinstance(level, str) and level not in _EVIDENCE_COVERAGE_LEVELS:
        allowed = ", ".join(sorted(_EVIDENCE_COVERAGE_LEVELS))
        return False, (
            f"evidence schema violation: coverage_level must be one of "
            f"{{{allowed}}}, got {level!r}"
        )

    return True, ""


def _read_gates_waived(prawduct_dir: Path) -> dict[str, str]:
    """Load .gates-waived JSON. Returns {} if missing or invalid.

    Format: {"critic": "reason", "pr": "reason", "reflection": "reason"}.
    Each present key signals "this gate does not apply to the current work."
    The agent writes this file when work is genuinely N/A for that gate
    (e.g., docs-only refactor, no PR planned for this branch). The file
    is auto-deleted at session start so waivers never carry across sessions.
    """
    waiver_path = prawduct_dir / ".gates-waived"
    if not waiver_path.is_file():
        return {}
    try:
        data = json.loads(waiver_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # A waiver requires a non-empty *string* reason. Empty strings, missing
    # reasons, and non-string values (booleans, numbers, nested objects) are
    # all rejected. The reason is required so reviewers can audit *why* the
    # gate was bypassed; an "implicit truthy" form would be a silent escape
    # hatch and exactly the kind of pattern the project's learnings warn
    # against.
    out: dict[str, str] = {}
    for key, val in data.items():
        if not isinstance(key, str):
            continue
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def background_tasks_in_flight(stop_input) -> tuple[bool, list[str]]:
    """Decide whether harness-tracked background work is still in flight, from
    the Stop-hook ``background_tasks`` array (Claude Code v2.1.145+; STH-3W7F).

    When a coordinating agent launches a background ``Workflow``/``Task`` and
    yields, the Stop hook fires while the diff is still being produced — the
    Critic/reflection gate would block on "files changed, no review yet" even
    though there is nothing to review yet AND the session cannot actually end
    (the harness re-wakes it when the job lands). This helper detects that state
    so the gate can DEFER (not skip) the block to a later Stop.

    Degradation ladder — the permissive direction (suppressing the block) is
    taken ONLY on a clearly-present, non-empty list; every uncertain case falls
    to the blocking default (fail-closed for a gate = keep blocking):

      - ``background_tasks`` ABSENT (older client, registry unreachable, no
        stdin) → ``(False, [])`` — behave exactly as without the signal.
      - present & EMPTY (genuinely idle) → ``(False, [])`` — block as today.
      - present & NON-EMPTY → ``(True, [labels])`` — defer.
      - any malformed shape (non-dict input, non-list value, list with no
        usable entries) → ``(False, [])`` — never defer on garbage.

    ``labels`` summarize each in-flight task as ``<type>:<name|id>`` for the
    deferral note. No filtering by task type: a session with any live tracked
    task is "paused waiting" anyway, and the deferral re-arms every Stop, so
    over-deferral is cheap (the gate fires the instant the array empties).
    """
    if not isinstance(stop_input, dict):
        return False, []
    tasks = stop_input.get("background_tasks")
    if not isinstance(tasks, list) or not tasks:
        return False, []
    labels: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        ttype = task.get("type")
        ttype = ttype.strip() if isinstance(ttype, str) and ttype.strip() else "task"
        # Prefer the human-meaningful identifier per type, fall back to id.
        ident = None
        for key in ("name", "agent_type", "description", "command", "id"):
            val = task.get(key)
            if isinstance(val, str) and val.strip():
                ident = val.strip()
                break
        label = f"{ttype}:{ident}" if ident else ttype
        # Keep the note compact — a description/command can be long.
        labels.append(label[:80])
    if not labels:
        return False, []
    return True, labels


_CRITIC_MODE_CHUNK = "chunk (lighter pass, not ready for push)"
_CRITIC_MODE_FINAL = "final (full review, ready for push)"
_CRITIC_MODE_CUMULATIVE = "cumulative (bundle review, ready for merge)"
_CRITIC_MODE_VERIFY_RESOLUTIONS = (
    "verify-resolutions (delta review, prior findings only)"
)
_CRITIC_MODE_VALUES = frozenset({
    _CRITIC_MODE_CHUNK,
    _CRITIC_MODE_FINAL,
    _CRITIC_MODE_CUMULATIVE,
    _CRITIC_MODE_VERIFY_RESOLUTIONS,
})


def validate_critic_findings(findings_path: Path) -> bool:
    """Validate that critic findings JSON has required structure.

    Thin path wrapper over :func:`_validate_critic_findings_data` (the data
    form also validates ledger event payloads — review-proportionality
    ch.02, one schema for both homes of the same record).
    """
    try:
        data = json.loads(findings_path.read_text())
        return _validate_critic_findings_data(data)
    except Exception:  # prawduct:allow prawduct/broad-except -- validation must not crash gate check
        return False


def _validate_critic_findings_data(data) -> bool:
    """Validate a critic findings record (dict form).

    Requires: non-empty files_reviewed list, findings list where each entry
    has goal/severity/summary, and a non-empty summary string. The `mode`
    field is optional (legacy hooks pre-v1.3.13 omit it) but, when present,
    must be one of the verbose strings in ``_CRITIC_MODE_VALUES``. The bare
    short tokens (``"chunk"`` / ``"final"``) are rejected — those are the
    caller-side input form, not the persistence form.
    """
    try:
        if not isinstance(data, dict):
            return False
        # Must have a findings list
        findings = data.get("findings")
        if not isinstance(findings, list):
            return False
        # Must have non-empty files_reviewed
        files_reviewed = data.get("files_reviewed")
        if not isinstance(files_reviewed, list) or not files_reviewed:
            return False
        # Each finding must have goal, severity, and summary
        for finding in findings:
            if not isinstance(finding, dict):
                return False
            for field in ("goal", "severity", "summary"):
                val = finding.get(field)
                if not isinstance(val, str) or not val.strip():
                    return False
            # review-proportionality ch.02 — optional per-finding `files`
            # (which files the finding is about): finding-level attribution
            # so findings-density-by-path is computable without parsing
            # summary strings. When present: a list of non-empty strings.
            if "files" in finding:
                files = finding["files"]
                if not isinstance(files, list):
                    return False
                for f in files:
                    if not isinstance(f, str) or not f.strip():
                        return False
        # Must have a non-empty summary
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            return False
        # Mode field is optional (back-compat). If present, must be exactly one
        # of the verbose strings — bare tokens, unknown strings, and non-string
        # values are all rejected so writer drift surfaces here, not later.
        if "mode" in data:
            mode = data["mode"]
            if not isinstance(mode, str) or mode not in _CRITIC_MODE_VALUES:
                return False
        # v1.5 Chunk 01 — commit_reviewed / base_reviewed anchor the delta
        # computation for the verify-resolutions mode (Chunk 02). Optional
        # for back-compat with pre-v1.5 findings files (which simply cannot
        # serve as a verify-resolutions baseline). When present, must be a
        # NON-EMPTY string SHA or None — wrong types and empty strings are
        # writer drift (empty string would silently anchor at no commit,
        # breaking Chunk 02's delta computation), surfaced here.
        for sha_field in ("commit_reviewed", "base_reviewed"):
            if sha_field in data:
                val = data[sha_field]
                if val is None:
                    continue
                if not isinstance(val, str) or not val.strip():
                    return False
        # (The CRT-4J8W ``extends_cumulative`` chain anchor was retired with
        # the chain gate itself — kernel-v3 chunk 04: composition over store
        # facts replaced chain bookkeeping, and no writer emits the field.)
        # v1.5 Chunk 03 — mode_chosen_by records which rule fired in the
        # inference helper, or the literal "explicit-args" when the
        # builder overrode inference. Optional for back-compat. When
        # present, must be a non-empty string — empty strings and wrong
        # types are writer drift (the field's whole purpose is post-hoc
        # introspection of mode selection; empty defeats that).
        if "mode_chosen_by" in data:
            val = data["mode_chosen_by"]
            if not isinstance(val, str) or not val.strip():
                return False
        # review-proportionality ch.02 — optional record-level `model` (the
        # model id the reviewer actually ran as; reviewer-tiering telemetry).
        # Nullable like the sha fields; non-empty string when set.
        if "model" in data:
            val = data["model"]
            if val is not None and (not isinstance(val, str) or not val.strip()):
                return False
        return True
    except Exception:  # prawduct:allow prawduct/broad-except -- validation must not crash gate check
        return False


_SESSION_BASE_TREE_MARKER = ".session-base-tree"


def _read_session_base_tree(prawduct_dir: Path) -> str:
    """Content of the ``.session-base-tree`` marker (the ``HEAD^{tree}`` SHA
    ``cmd_clear`` recorded at session start), or ``""`` when missing or
    unreadable — the session gate then degrades to a HEAD-tree base (its
    jurisdiction shrinks to uncommitted work, exactly the v2 scope)."""
    try:
        return (prawduct_dir / _SESSION_BASE_TREE_MARKER).read_text().strip()
    except OSError:
        return ""


def _store_precheck(read: dict) -> "tuple[str, str] | None":
    """``None`` when a ``read_facts`` result is usable by a gate; else the
    ``(status, reason)`` the gate must fail closed on. A schema-ahead fact
    (written by a NEWER plugin) blocks with the exact remedy — this reader
    cannot know what it attests, and it may be the freshest review (C9
    tier 3: never silently drop, never pass)."""
    if read.get("status") == "error":
        return "error", str(read.get("reason", "evidence store unreadable"))
    ahead = read.get("schema_ahead") or []
    if ahead:
        schemas = sorted({a.get("schema") for a in ahead if a.get("schema")})
        return "schema-ahead", (
            f"{len(ahead)} evidence fact(s) carry schema "
            f"{'/'.join(str(s) for s in schemas)}, newer than this plugin "
            "understands — written by a newer prawduct. Update the plugin "
            "(/reload-plugins or restart Claude Code), then re-run the gate."
        )
    return None


def session_changes_all_non_judgeable(
    project_dir: Path, status_output: "str | None" = None
) -> bool:
    """True when the session changed files but NONE of them needs review
    coverage — the "doc-only" carveout, now answered by THE judgeability
    predicate (``coverage_algebra.is_judgeable_path``, CRT-5D8Q fix) instead
    of a bare ``.endswith(".md")`` copy. A governance-protected ``.md``
    (``skills/``, ``methodology/``, ``templates/``, root ``CLAUDE.md``) is
    judgeable, so editing one no longer skips the reflection/Critic gates.

    Replaces ``gitstate._session_changes_are_doc_only`` (one of the three
    divergent doc-only sites the kernel-v3 inventory flagged); lives here
    because ``gitstate`` sits below ``coverage_algebra`` in the import DAG.
    ``status_output`` (STH-6Q9D): optional pre-captured porcelain snapshot.
    """
    changed = gitstate._get_session_changed_files(project_dir, status_output)
    non_metadata = [f for f in changed if not gitstate._is_metadata_path(f)]
    if not non_metadata:
        return False
    return not coverage_algebra.judgeable_files(non_metadata)


def _cached_diff_fn(project_dir: Path):
    """A ``coverage_algebra.DiffFn`` that memoizes ``evidence.tree_diff`` per
    gate invocation.

    Free-edge *connectivity* no longer comes from here — every production call
    site pairs this with :func:`_tree_key_fn`, so the BFS groups trees by key
    and this function is reached only by ``_attribute_free_steps``, filling in
    the file list for the free steps on a path already found. What the memo
    still buys is the repetition across passes: a gate may run the clean-edges
    search, then the all-edges search, then the merge-base fallback, and the
    same interval can be attributed in more than one of them. Cache scope is
    one verdict call, so staleness cannot leak across gates (same one-capture
    discipline as STH-6Q9D)."""
    cache: dict[tuple[str, str], "list[str] | None"] = {}

    def diff_fn(a: str, b: str) -> "list[str] | None":
        key = (a, b)
        if key not in cache:
            cache[key] = evidence.tree_diff(project_dir, a, b)
        return cache[key]

    return diff_fn


def _tree_key_fn(project_dir: Path):
    """A ``coverage_algebra.KeyFn``: a tree's digest over its JUDGEABLE
    content, so free-edge connectivity costs one ``git ls-tree`` per tree
    instead of one ``git diff`` per pair.

    Memoising the pairwise probe was not enough — the *pair count* is the
    problem, not repeat pairs. Measured on this repo's store (672 facts, 293
    trees) the pairwise form issued 5,597 ``git diff`` subprocesses and spent
    316 s of a 318 s verdict inside them; the store is append-only and shared
    by every worktree of the clone, so that degrades monotonically. Keying
    each tree once is linear in trees and asks the same question.

    ``None`` when the tree cannot be read, which denies a free edge rather
    than granting one — the fast path fails in the same direction as the slow
    one, because this gate is authority and authority fails closed.
    """
    cache: dict[str, "str | None"] = {}

    def key_fn(tree: str) -> "str | None":
        if tree not in cache:
            entries = evidence.tree_entries(project_dir, tree)
            if entries is None:
                cache[tree] = None
            else:
                judgeable = sorted(
                    f"{mode} {object_id} {path}"
                    for mode, object_id, path in entries
                    if coverage_algebra.is_judgeable_path(path)
                )
                cache[tree] = hashlib.sha256(
                    "\n".join(judgeable).encode("utf-8", "surrogateescape")
                ).hexdigest()
        return cache[tree]

    return key_fn


#: Grouping key for the base-advance transfer's yield records. Both review
#: gates emit under this one name, because the question the records answer —
#: "did the transfer ever fire, and did it ever pass something that turned out
#: to need a review?" — is about the control, not about which gate observed it.
_TRANSFER_GUARD = "base-advance-transfer"


def record_transfer_grant(
    project_dir: Path,
    facts: list[dict],
    transfer: dict,
    base_tree: str,
    target_tree: str,
    gate: str,
) -> dict:
    """Emit the base-advance transfer's yield signal. One call per grant, at
    both gates.

    The transfer's justification is a measurement — a review round costs 4-10
    minutes and the transfer removes one whenever a branch syncs a base it does
    not collide with — and this repo's standing norm is that *a control names
    the yield it expects AND emits that yield observably*, retroactively. The
    sibling control in this subsystem (``critic_consolidate.begin_review``'s
    free-interval refusal) satisfies it through the same sink; without a record
    here, nobody can count the transfer's firings, and a yield claim nothing can
    falsify is not a yield claim.

    **The id is a function of the span, and of nothing else.** The gate is
    polled — several times a session on an unchanged repo — and
    ``verdict_cache`` keys the composed verdict on a content hash of the whole
    evidence store, so a record per *poll* would invalidate every memoized
    verdict on every poll and hand back the cold path the memo was built to
    remove. Keying on ``(base_tree, target_tree, prior_base, prior_head)`` makes
    the second and later observations of one grant append nothing at all.

    **The residual, stated:** the first grant DOES append, so the poll after it
    recomputes cold — once per distinct transferred span, against a review round
    saved. What the key removes is the unbounded version, where every poll pays
    that again forever.

    ``gate`` therefore rides in the BODY and not in the key, which is a
    deliberate undercount rather than an oversight. The two gates ask about
    different spans (the PR gate targets HEAD's tree, the Stop gate the working
    tree), so they usually key apart on their own; when they coincide — a clean
    tree at session end — they describe ONE base sync that would have been paid
    off by ONE cumulative review, and counting it twice would inflate the yield
    of the control the record exists to audit. ``count_branch_rounds`` states
    the same preference for the same reason: undercounting says "at least this
    many", overcounting says something false.

    Fail-soft and never silent, exactly like its sibling: the transfer is
    correct whether or not the record lands, so a store failure must not turn a
    granted pass into a gate failure — but it is attributed on stderr, because a
    firing that vanishes leaves the yield query reading a lower bound it does
    not announce. Returns the sink's result so a caller (and a test) can see
    which of appended / duplicate / error happened.
    """
    prior_base, prior_head = transfer.get("prior_base", ""), transfer.get("prior_head", "")
    recorded = evidence.append_guard_refusal(
        project_dir,
        _TRANSFER_GUARD,
        {
            # Nested for the reason the sibling nests its own: a top-level
            # base_tree/head_tree pair is the shape a coverage EDGE has, and no
            # reader walking bodies for edges may mistake a transfer record for
            # one. (``coverage_algebra`` reads ``kind == "review"`` only, so this
            # is belt-and-braces on a property that already holds.)
            "interval": {"base_tree": base_tree, "head_tree": target_tree},
            "prior_interval": {"base_tree": prior_base, "head_tree": prior_head},
            "gate": gate,
            "prior_fact_id": transfer.get("prior_fact_id"),
            "prior_reviews": transfer.get("prior_reviews"),
            "files": list(transfer.get("files") or []),
            "advance_files": transfer.get("advance_files"),
        },
        dedupe_key="\0".join((base_tree, target_tree, prior_base, prior_head)),
        known_facts=facts,
    )
    if recorded.get("status") not in ("appended", "duplicate"):
        print(
            f"{gate}: the base-advance transfer is correct but its firing was NOT "
            f"recorded ({recorded.get('reason', 'unknown')}) — this grant is missing "
            f"from `prawduct-hook evidence list --kind guard-refusal`, so read that "
            f"query as a lower bound.",
            file=sys.stderr,
        )
    return recorded


def session_review_verdict(project_dir: Path, *, record_grants: bool = False) -> dict:
    """The Stop-hook Critic gate's question, answered by composition (Q2):
    does composed review coverage span this session's base tree → the current
    working tree, with zero unresolved blocking findings?

    Replaces the mtime-vs-``.session-start`` freshness check, the
    verify-resolutions scope-subset check, and every read of
    ``.critic-findings.json`` at this gate (kernel-v3 chunk 04). Evidence is
    facts in the shared store; the base is the ``HEAD^{tree}`` recorded at
    session start (``.session-base-tree``), so a fact recorded pre-commit
    vouches for the verbatim commit from any worktree or later session.

    Returns one of::

        {"status": "covered", "path": [...], "base": t, "target": t2,
         "base_source": "marker"|"head-fallback"|"merge-base-fallback"}
      | {"status": "blocked", "unresolved": [...], ...}   # findings listed
      | {"status": "uncovered", "reason": str, ...}
      | {"status": "schema-ahead", "reason": str}
      | {"status": "error", "reason": str}                # fail closed

    Degradations and fallbacks (each deliberate):

    - Marker missing (pre-upgrade session, mid-session worktree entry) →
      base = ``HEAD^{tree}`` now. Jurisdiction shrinks to uncommitted work
      (the v2 scope) rather than wedging a session that cannot re-run
      ``clear``.
    - Session base unreachable but merge-base coverage composes → covered.
      A commit made without review leaves a gap no dispatchable review can
      span from the session base (chunk/final reviews anchor at HEAD's
      tree); composed coverage of merge-base → working tree is the PR
      gate's own bar — strictly stronger evidence about the current state —
      so requiring an unsatisfiable base instead would only train waivers
      (chunk-04 refinement, recorded in the design doc).
    - Merge-base coverage does not compose but transfers across a base
      advance → covered, with a ``transferred`` key naming what vouched.
      This gate asks the PR gate's composition question, so a span the PR
      gate passes by transfer had to pass here too: without it, syncing a
      base cleared ``/prawduct:pr`` and then blocked the same tree at
      session end, sending the builder to run exactly the cumulative round
      the transfer exists to remove. Conditions and their shape:
      :func:`_merge_base_verdict`.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    read = evidence.read_facts(project_dir)
    precheck = _store_precheck(read)
    if precheck is not None:
        status, reason = precheck
        return {"status": status, "reason": reason}
    facts = read.get("facts", [])

    capture = evidence.capture_tree(project_dir)
    if capture.get("status") != "ok":
        return {
            "status": "error",
            "reason": f"cannot capture the working tree: {capture.get('reason', 'unknown')}",
        }
    target = capture["tree"]

    base = _read_session_base_tree(prawduct_dir)
    base_source = "marker"
    if not base:
        base = capture.get("head_tree") or ""
        base_source = "head-fallback"
        if not base:
            return {
                "status": "error",
                "reason": (
                    "no session base tree marker and no HEAD to fall back to — "
                    "commit an initial state, then re-run /prawduct:critic"
                ),
            }

    diff_fn = _cached_diff_fn(project_dir)
    key_fn = _tree_key_fn(project_dir)

    verdict = coverage_algebra.coverage_verdict(facts, base, target, diff_fn, key_fn)
    transfer_note: "str | None" = None
    if verdict["status"] != "covered" and base_source == "marker":
        mb_verdict = _merge_base_verdict(
            project_dir, facts, target, diff_fn, key_fn, record_grants=record_grants
        )
        if mb_verdict is not None:
            transfer_note = mb_verdict.pop("transfer_note", None)
        if mb_verdict is not None and (
            mb_verdict["status"] == "covered"
            or (mb_verdict["status"] == "blocked" and verdict["status"] == "uncovered")
        ):
            verdict = mb_verdict
            base, base_source = mb_verdict["base"], "merge-base-fallback"
    # The near-miss and could-not-run notes are computed against the merge-base
    # span but carried onto whichever verdict is RETURNED, because that is the
    # one the Stop hook renders (as the `reason` in its block message) and this
    # gate has no stderr of its own — the fallback's own verdict is discarded
    # whenever the primary one already blocks, which would drop the cheapest
    # remedy the gate has to offer on exactly the sessions that need it.
    if transfer_note and verdict["status"] == "uncovered":
        verdict["reason"] = f"{verdict.get('reason', 'no path')} — {transfer_note}"
    verdict.update({"base": base, "target": target, "base_source": base_source})
    return verdict


def _merge_base_verdict(
    project_dir: Path,
    facts: list[dict],
    target: str,
    diff_fn,
    key_fn,
    *,
    record_grants: bool = False,
) -> "dict | None":
    """Coverage of merge-base tree → ``target`` — the session gate's
    unwedging fallback (see :func:`session_review_verdict`). ``None`` when
    the merge base cannot be resolved (the primary verdict then stands).

    ``key_fn`` is required, not defaulted: a ``None`` key sends ``_find_path``
    down the pairwise free-edge branch, which :func:`_tree_key_fn` measures on
    this repo's store at ~5.6k ``git diff`` subprocesses. It used to default,
    unreachably — the sole caller passes it — and an unreachable default for a
    silent slow path is a hang waiting for its first caller.

    This path is deliberately NOT memoized while the PR gate is: its target is
    the working tree, which moves on nearly every edit, so a keyed entry would
    almost always miss and the store hash would be pure cost.

    **This is also where the base-advance transfer applies, and only here.** The
    gate's own span (session base tree → working tree) is the wrong one to ask:
    its start node is the tree HEAD sat at when the session opened, which no base
    sync moves, and after a sync the diff across it IS the advance rather than
    the branch's own work — so the transfer's first condition (the two spans hold
    the same branch diff) could not hold, and asking would spend git calls to
    learn nothing. The merge-base span is the PR gate's span with the working
    tree in place of HEAD's tree, which is the shape
    :func:`coverage.diagnose_base_advance_transfer` was written for: after a sync
    the merge-base moves to the new base tip and the required diff becomes
    exactly the branch diff. The substitution costs nothing in soundness —
    uncommitted judgeable work makes the required diff differ from any reviewed
    one and condition 1 denies — and condition 3 lands MORE squarely here than at
    the PR gate, because :func:`suite_vouches_for_tree` defaults to the
    working tree, which is this gate's target.

    Attempted only on ``uncovered``: a ``blocked`` span is owed a blocker, and
    no transfer discharges that (the PR gate returns before its own attempt for
    the same reason). Every unverifiable condition denies, so the fallback fails
    closed exactly as it did before.

    Its cost lands on the failing path only, and lands small: the diagnosis's
    extra verdicts run through the ``diff_fn``/``key_fn`` caches this call
    already built, so the ``git ls-tree`` per tree — the expensive part — is
    paid once for the whole invocation whether one verdict is computed or five.
    The unmemoized-across-calls property above is unchanged.

    Adds ``transfer_note`` — the near-miss or could-not-run sentence — for the
    caller to carry onto the verdict it actually returns; the caller pops it, so
    it never reaches a consumer as part of the verdict shape."""
    resolved = coverage.resolve_merge_base_tree(project_dir)
    if resolved["status"] != "ok":
        return None
    mb_tree = resolved["tree"]
    verdict = coverage_algebra.coverage_verdict(facts, mb_tree, target, diff_fn, key_fn)
    verdict["base"] = mb_tree
    if verdict["status"] != "uncovered":
        return verdict

    def verdict_fn(f: list[dict], base: str, tgt: str) -> dict:
        return coverage_algebra.coverage_verdict(f, base, tgt, diff_fn, key_fn)

    transfer = coverage.diagnose_base_advance_transfer(
        project_dir, facts, mb_tree, target, diff_fn, verdict_fn
    )
    if transfer is None:
        return verdict
    if transfer.get("status") == "unavailable":
        verdict["transfer_note"] = transfer_remedy(transfer, None)
        return verdict
    tests_ok, tests_reason = suite_vouches_for_tree(project_dir)
    if not tests_ok:
        verdict["transfer_note"] = transfer_remedy(transfer, tests_reason)
        return verdict
    # Recording is OPT-IN, and the reason is the second caller. This verdict is
    # read by the Stop gate (authority, session end) and by the session-start
    # briefing (advice), and the briefing wraps the call in a broad `except` —
    # so an append from that path would be a store write on a session-START read
    # path whose fail-soft attribution is swallowed, filed under a gate that did
    # not run. It would also change the store fingerprint at session start,
    # evicting the very memo the previous chunk built. Authority records its own
    # yield; advice observes and writes nothing.
    if record_grants:
        record_transfer_grant(
            project_dir, facts, transfer, mb_tree, target, "session-review-verdict"
        )
    return {
        "status": "covered",
        # No composed path exists over THIS span — the coverage was computed,
        # not walked — so the list is empty rather than borrowed from the prior
        # span, whose steps describe different trees. `transferred` is where a
        # reader (or a test) finds what actually vouched.
        "path": [],
        "base": mb_tree,
        "transferred": {
            "prior_base": transfer["prior_base"],
            "prior_head": transfer["prior_head"],
            "prior_fact_id": transfer["prior_fact_id"],
            "prior_reviews": transfer["prior_reviews"],
            "files": transfer["files"],
            "advance_files": transfer["advance_files"],
            "tests_reason": tests_reason,
        },
    }


_CRITIC_MODE_GOALS_1_3_ONLY = frozenset({
    _CRITIC_MODE_CHUNK,
    _CRITIC_MODE_VERIFY_RESOLUTIONS,
})


def _critic_session_satisfies_gate(project_dir: Path) -> tuple[bool, str]:
    """Check whether the latest Critic review satisfies end-of-cycle synthesis.

    Returns ``(True, "")`` when the gate is satisfied, ``(False, reason)``
    otherwise. The gate is advisory: it fires when a multi-chunk build plan
    has all chunks marked ``[x]`` but the most recent Critic review ran
    Goals 1-3 only — ``chunk`` and ``verify-resolutions`` modes both skip
    end-of-cycle goals (Coherence, Design, Learnings Cross-Check, Backlog
    Reconciliation, Framework-Specific Checks). The mode is telemetry read
    from the latest ``review`` FACT in the evidence store (kernel-v3 chunk
    04: no gate — even an advisory one — reads the ``.critic-findings.json``
    cache); it steers a workflow nudge, never evidence acceptance (D4).

    Specific cases (in order):
    1. No build plan, or no chunks declared → satisfied (non-chunked work).
    2. Single-chunk plan → satisfied (the one Critic run is the final).
    3. Multi-chunk plan with incomplete chunks → satisfied (mid-cycle).
    4. Multi-chunk plan, all chunks ``[x]``, latest review fact's mode is in
       ``_CRITIC_MODE_GOALS_1_3_ONLY`` (chunk or verify-resolutions)
       → unsatisfied. Run ``/prawduct:critic final`` for end-of-cycle synthesis.
    5. Multi-chunk plan, all chunks ``[x]``, latest mode is final/cumulative
       (or no review fact exists — nothing to judge) → satisfied.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    total, complete = buildplan_refs._count_build_plan_chunks(prawduct_dir)
    if total == 0:
        return True, ""
    if total == 1:
        return True, ""
    if complete < total:
        return True, ""

    review_facts = evidence.facts_of_kind(evidence.read_facts(project_dir), "review")
    if not review_facts:
        return True, ""
    latest_body = review_facts[-1].get("body") or {}
    mode = latest_body.get("mode", _CRITIC_MODE_FINAL)
    if mode in _CRITIC_MODE_GOALS_1_3_ONLY:
        return False, (
            f"All {total} chunks complete; last Critic review was "
            f"'{mode}'. Run /prawduct:critic final for end-of-cycle "
            "synthesis (Coherence, Design, Learnings Cross-Check, Backlog "
            "Reconciliation) before pushing."
        )
    return True, ""


def _has_build_plan_in_state(prawduct_dir: Path) -> bool:
    """Check if project-state.yaml contains an ACTIVE build plan.

    Uses string matching rather than YAML parsing for speed and zero dependencies.
    Returns True only when chunks exist with non-complete status. Returns False for:
    - chunks: [] (empty plan, template default)
    - All chunks with status: complete (finished plan)
    - No build_plan section at all
    """
    state_path = prawduct_dir / "project-state.yaml"
    if not state_path.is_file():
        return False
    try:
        content = state_path.read_text()
        if not (content.startswith("build_plan:") or "\nbuild_plan:" in content):
            return False
        if not ("\n  chunks:" in content or content.startswith("  chunks:")):
            return False

        # Scan chunks section for non-complete status entries
        in_chunks = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("chunks:"):
                in_chunks = True
                if "[]" in stripped:
                    return False  # Empty array
                continue
            if in_chunks:
                # Exit chunks on line at same or lesser indent (not blank/comment)
                if line and not line.startswith("    ") and stripped and not stripped.startswith("#"):
                    break
                if stripped.startswith("status:"):
                    status_val = stripped.split(":", 1)[1].strip().strip("\"'")
                    if status_val != "complete":
                        return True
        return False
    except Exception:  # prawduct:allow prawduct/broad-except -- build plan check must not crash gate check
        return False


def _has_active_build_plan_file(
    prawduct_dir: Path, plan_path: "Path | None" = None
) -> bool:
    """Return True if the build plan has at least one incomplete chunk.

    ``plan_path`` names the plan to read, defaulting to this repo's active
    build plan. The Stop hook and the SessionStart advisory both pass the BRANCH's
    plan, so the gate's "should I run" and its "what does the chunk declare"
    cannot answer about different files.

    A completed plan (all [x]) or a missing file both return False — only an
    in-progress plan with remaining work triggers governance gates.

    Deliberately the **checkbox** reading, and never a commit-derived one.
    The two answer different questions: commits answer "which chunk is in
    flight", which is right for reporting; this gate asks "is there still
    governed work", and **a chunk's last commit lands BEFORE its Critic pass and
    its reflection.** Routing this through a git signal once made the blocking
    reflection and Critic gates switch themselves off the moment the final chunk
    was committed — through the whole complete-but-unmerged window, which is
    exactly when the PR-fix and finding-resolution sessions happen. It failed
    silently, because a gate that stops firing looks identical to a gate with
    nothing to say.

    The git-derived progress reading that caused it is gone, so that exact route
    back in is closed. **The rule is not.** A commit-derived chunk signal still
    exists for reporting — ``buildplan_refs.unticked_committed_chunk_notice``,
    which flags a finished-but-unticked chunk — and it is the obvious thing for a
    future editor to reach for here. It must not be: it reports precisely the
    state (work committed, box not yet ticked) in which this gate must still say
    "governed", and consuming it here would reproduce the incident with a
    different callee.
    """
    total, complete = buildplan_refs._count_build_plan_chunks(prawduct_dir, plan_path)
    return total > 0 and complete < total


def _is_trivial_fileset_eligible(project_dir: Path) -> tuple[bool, str]:
    """Check the current session's diff against the ``Type: trivial``
    file-set bounds. Returns ``(eligible, reason)``.

    Bounds (catastrophic-blast-radius classes, regardless of size):
    no edits under ``skills/``, ``methodology/``, or ``templates/``; no
    edits to ``CLAUDE.md``; no test-file removals (porcelain ``D`` under
    ``tests/`` OR rename whose source path is under ``tests/`` — a
    ``git mv`` out of the test directory is semantically a deletion);
    no newly-tracked files (porcelain ``A`` or ``??``).

    Size is intentionally NOT a bound — trivial is a semantic judgment.
    An 80-LOC project-wide rename can qualify; a 5-line state-machine
    change cannot. The semantic claim lives in
    ``**Trivial because:**``; Critic Goal 3 validates rationale-vs-diff
    fit (Chunk 05).

    Reason strings name the specific bound that failed for actionable
    stop-hook messaging — e.g. ``"skill-file-edited: skills/critic/SKILL.md"``.
    The first violating file wins (deterministic order: porcelain
    output ordering); the user fixes one violation at a time.

    Uses session-baseline filtering so pre-session dirt doesn't count
    against the chunk (mirrors ``git_has_session_changes``).

    Path-bound rules are delegated to ``_classify_trivial_change`` (now
    this gate's sole consumer — the PR-boundary ``_pr_diff_is_trivial``
    fast-path that once shared it was retired). This gate enforces a
    *declared* ``Type: trivial`` chunk; it is not a triviality detector.
    """
    output = gitstate.git_status_output(project_dir)
    if output is None:
        # No git or git error — defer to other gates; treat as eligible
        # so the trivial check doesn't fail the build when git itself is
        # the problem.
        return True, ""

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    baseline_path = prawduct_dir / ".session-git-baseline"
    baseline_lines: set[str] = set()
    if baseline_path.is_file():
        try:
            baseline_lines = set(baseline_path.read_text().splitlines())
        except (UnicodeDecodeError, OSError):
            pass

    for line in output.splitlines():
        if not line or line in baseline_lines:
            continue
        parsed = gitstate.parse_porcelain_line(line)
        if parsed is None:
            continue
        status, src_path, path = parsed

        # v1.5.1 Chunk 04(b): metadata-path filtering lives inside
        # `_classify_trivial_change` (returns None for both src and dst
        # metadata paths) — now reached only from this gate (the
        # `_pr_diff_is_trivial` co-consumer was retired).
        is_addition = status[0] == "A" or status == "??"
        is_deletion = "D" in status
        violation = buildplan_refs._classify_trivial_change(
            path=path,
            src_path=src_path,
            is_addition=is_addition,
            is_deletion=is_deletion,
        )
        if violation is not None:
            return False, violation

    return True, ""


def test_status(project_dir: Path) -> int:
    """Print whether saved test evidence is fresh enough to trust.

    Used by builders, the Critic, and the PR reviewer to decide whether to
    re-run the test suite.

    stdout: one line — `current: <reason>` or `stale: <reason>`

    Exit codes:
      0  - tests are current; safe to skip re-running
      1  - tests are stale or no evidence
    """
    is_current, reason = tests_are_current(project_dir)
    if is_current:
        print(f"current: {reason}")
    else:
        print(f"stale: {reason}")
    return 0 if is_current else 1


def validate_evidence(project_dir: Path) -> int:
    """Schema-only check on ``.test-evidence.json``.

    Useful for CI / pre-commit hooks that want a fast schema sanity check
    without the freshness comparison ``test-status`` performs. Returns
    exit 0 only when the file exists, parses, and matches the required
    schema; exit 1 otherwise.
    """
    evidence_path = gitstate.get_prawduct_dir(project_dir) / ".test-evidence.json"
    if not evidence_path.is_file():
        print(f"missing: {evidence_path}", file=sys.stderr)
        return 1
    try:
        evidence = json.loads(evidence_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        return 1
    if not isinstance(evidence, dict):
        print("evidence is not a JSON object", file=sys.stderr)
        return 1
    ok, err = _validate_evidence_schema(evidence)
    if not ok:
        print(f"invalid: {err}", file=sys.stderr)
        return 1
    print("valid")
    return 0


def transfer_remedy(transfer: dict, tests_reason: "str | None") -> str:
    """The remedy prose for a base-advance transfer that did not grant.

    Both gates that attempt the transfer render this — the PR gate's `uncovered`
    block and the Stop gate's ``transfer_note`` — so the wording has one home
    and cannot drift at one site only, the same rule
    :func:`blocking_remedy_lines` states for the blocking remedy. It drifted
    before this had one home: the Stop-gate copy lost the closing sentence, so
    the same builder blocked at session end was told less than the one blocked
    at `/prawduct:pr create`, for the identical condition.

    Two conditions, and they prescribe opposite things:

    - ``tests_reason`` given → every transfer condition held except that no
      saved suite run has met this tree. The remedy is a suite run, which is the
      cheapest route the gate has; it names why timing is not the question.
    - ``tests_reason`` None → the check itself could not run. That is not
      evidence the gap is genuine work, and saying so is the whole point: an
      unavailable check reading as a finding is the fail-open shape inverted.

    Returned as one paragraph without a severity prefix or indentation — each
    caller owns how it announces the line.
    """
    if tests_reason is None:
        return (
            f"the base-advance transfer check could not run ({transfer['reason']}) — "
            "that is not a finding that this gap is genuine work, only that the "
            "cheap check was unavailable"
        )
    return (
        f"the branch's own diff is byte-identical to the span review "
        f"{transfer['prior_fact_id']} already covered ({len(transfer['files'])} "
        "judgeable file(s)), and the base advance touched none of them — the ONLY "
        "condition denying the transfer is that no saved suite run has met this "
        f"tree ({tests_reason}). Run the suite and `prawduct-hook test-evidence "
        "record`, then re-run: the coverage transfers and no review is needed. The "
        "suite is what vouches for the reviewed diff meeting the advanced base — a "
        "run from earlier in this session does not, which is why timing is not what "
        "is checked here."
    )


def blocking_remedy_lines(unresolved: "list[dict] | None") -> list[str]:
    """The whole remedy a blocking verdict prescribes, as unindented lines.

    Both blocking messages render this — this module's PR gate and the Stop
    hook's — so the wording has one home and cannot drift at one site only.
    Each caller owns nothing but its own indentation.

    The standard remedy states the whole golden path, not just the command.
    Naming only "fix them, then verify" leaves the batching to the operator,
    and the loop that actually costs rounds is fix-commit-verify per finding:
    each commit extends HEAD, so each one buys a fresh round whose demoted
    observations tempt the next fix. Fixing everything in the working tree and
    verifying once is sound — a verify pass reads the dirty tree — and the
    verified tree is what gets committed.

    Three cases, because the standard remedy is *wrong* for a superseded
    blocker: one carried by a review fact no verify-resolutions pass will
    anchor to again (``coverage_algebra._verify_anchor_id``). A verify pass
    resolves findings on the fact it anchors to, so it will never name that
    round again, and the state clears only through a spanning review.

    - none superseded → the standard golden-path remedy.
    - some superseded → the standard remedy, then the exception.
    - **all** superseded → the spanning review LEADS. Appending the exception
      after "run verify-resolutions" would hand the operator the one route
      that cannot work as their first instruction, which is the original
      defect in its total case rather than a fix for it.

    Advice, not verdict: a superseded blocker blocks exactly as hard as any
    other, and no exit code moves.
    """
    entries = [e for e in (unresolved or []) if isinstance(e, dict)]
    standard = [
        "Fix ALL of them in the working tree first — do not commit between fixes.",
        "Then run ONE /prawduct:critic verify-resolutions (it reads the dirty tree)",
        "and commit that verified tree verbatim: it records the resolution facts,",
        "so this same evidence passes with no full re-review.",
    ]
    n = sum(1 for e in entries if e.get("superseded"))
    if not n:
        return standard

    spanning = [
        "Fix them, then run /prawduct:critic cumulative — a review spanning the",
        "whole interval supplies a clean path when it records nothing blocking.",
    ]
    if n == len(entries):
        lead = (
            "Superseded: the blocker above sits on an earlier review round"
            if n == 1
            else f"Superseded: all {n} blockers above sit on earlier review rounds"
        )
        return [f"{lead} that no verify-resolutions pass will name again."] + spanning

    noun, verb = ("finding", "belongs") if n == 1 else ("findings", "belong")
    return standard + [
        f"Superseded: {n} {noun} above {verb} to an earlier review round that no",
        "verify-resolutions pass will name again. For those, run",
        "/prawduct:critic cumulative instead — a review spanning the whole",
        "interval supplies a clean path when it records nothing blocking.",
    ]


def check_cumulative_critic(project_dir: Path) -> int:
    """Structural gate for ``/prawduct:pr create`` — Q1, answered by
    composition (kernel-v3-evidence-design.md D6, chunk 04): does composed
    review coverage span ``merge-base(base_branch, HEAD)`` → ``HEAD`` *by
    tree*, with zero unresolved blocking findings on the path?

    Evidence is review/resolution facts in the shared store
    (``lib.evidence``); the verdict is ``coverage_algebra.coverage_verdict``
    over them. No mode label is consulted (CRT-J4PM: chunk + cumulative +
    final facts compose identically), no file mtime is compared, and
    ``.critic-findings.json`` is never read (D7). A review recorded
    pre-commit vouches for the verbatim commit because the commit carries
    the reviewed tree (D3) — so squash-merges stay covered, while a rebase
    leaves a gap composition cannot close (one case of which the transfer
    below closes by computation instead).

    Exit 0 — covered. Exit 1 — anything else, with the specific reason and
    a copy-pasteable remedy on stderr:

    - ``schema-ahead`` — a fact from a newer plugin exists; update the
      plugin before trusting any verdict (C9 tier 3, fail closed).
    - ``blocking`` — coverage composes but carries unresolved BLOCKING
      findings (listed): fix them all in the working tree, then ONE
      ``/prawduct:critic verify-resolutions`` records the resolution facts —
      the same evidence then passes with no full re-review, and the verified
      tree is what gets committed. A finding the message
      marks *superseded* is the exception, and the message says so: it
      sits on a round no verify pass anchors to again, so it clears only
      through a spanning ``/prawduct:critic cumulative``. When EVERY
      blocker is superseded the message leads with that route instead
      (:func:`blocking_remedy_lines`).
    - ``uncovered`` — no evidence path composes: run ``/prawduct:critic
      cumulative``. If a pre-commit review was followed by a SELECTIVE
      commit (only part of the reviewed state committed), the commit's
      tree was never reviewed — ``/prawduct:critic verify-resolutions``
      reviews that delta and closes the gap.

    One computed exception precedes that verdict: when the span went uncovered
    only because the BASE ADVANCED, coverage **transfers** — conditions and
    their rationale in :func:`coverage.diagnose_base_advance_transfer` and
    :func:`suite_vouches_for_tree`, which own them. All hold → exit 0
    with the transfer named, and the firing recorded
    (:func:`record_transfer_grant` — the transfer's yield has to be countable).
    Any unverifiable → no transfer and the remedy above stands unchanged,
    because authority fails closed.

    Composed verdicts are memoized across calls (:mod:`verdict_cache`) — a cold
    one costs 17 s on this repo's store and the gate is polled several times a
    session. The wrapper exists to make the flush unconditional: the body has
    four exit paths, three of them failures, and a memo that only persisted on
    success would leave exactly the repeated-poll case it was built for
    uncached.
    """
    read = evidence.read_facts(project_dir)
    cache = verdict_cache.VerdictCache.for_read(project_dir, read)
    try:
        return _cumulative_critic_verdict(project_dir, read, cache)
    finally:
        # A memo that silently stops working is indistinguishable from one that
        # was never built, and the symptom — every call back on the ~17 s cold
        # path — reads as "the gate is slow again" with nothing to point at.
        # Attributed on the DEGRADED paths only: a working memo says nothing,
        # because a line printed on every successful gate call is noise that
        # trains the reader to skip the block where real remedies live.
        if not cache.enabled:
            print(
                "NOTE: the coverage-verdict memo is inert (no readable evidence "
                "store), so this verdict was computed cold and the next call will "
                "be too.",
                file=sys.stderr,
            )
        elif not cache.flush() and cache.misses:
            print(
                "NOTE: the coverage-verdict memo could not be saved, so the "
                f"{cache.misses} verdict(s) computed here will be recomputed on "
                "the next call. The verdict itself is unaffected.",
                file=sys.stderr,
            )


def _cumulative_critic_verdict(project_dir: Path, read: dict, cache) -> int:
    """:func:`check_cumulative_critic`'s body; see it for the contract."""
    precheck = _store_precheck(read)
    if precheck is not None:
        status, reason = precheck
        print(f"{status}: {reason}", file=sys.stderr)
        return 1

    resolved = coverage.resolve_merge_base_tree(project_dir)
    if resolved["status"] != "ok":
        remedy = {
            "resolve-base": (
                " — cannot determine the PR span. Fix base_branch in "
                "project-state.yaml (or fetch the base) and re-run."
            ),
            "merge-base": ". Re-run once the branch shares history with its base.",
        }.get(resolved.get("step", ""), ".")
        print(f"no-base: {resolved['reason']}{remedy}", file=sys.stderr)
        return 1
    base_tree = resolved["tree"]
    rc, head_tree, err = evidence.run_git(project_dir, "rev-parse", "HEAD^{tree}")
    if rc != 0 or not head_tree:
        print(f"no-head: cannot resolve HEAD^{{tree}} ({err}).", file=sys.stderr)
        return 1

    # Every cached ANSWER is read after the schema-ahead precheck above, and
    # that ordering is the contract: a fact from a newer plugin must block
    # before anything replays a verdict, or the block becomes skippable by
    # having asked the same question once before. (The cache OBJECT is built by
    # the caller, from the same `read_facts` result the precheck grades — it
    # opens nothing and decides nothing.)
    diff_fn = _cached_diff_fn(project_dir)
    key_fn = _tree_key_fn(project_dir)

    def verdict_fn(facts: list[dict], base: str, target: str) -> dict:
        return cache.verdict(facts, base, target, diff_fn, key_fn)

    verdict = verdict_fn(read.get("facts", []), base_tree, head_tree)

    if verdict["status"] == "covered":
        steps = verdict.get("path", [])
        reviews = sum(1 for s in steps if s.get("kind") == "review")
        free = sum(1 for s in steps if s.get("kind") == "free")
        detail = (
            f"{reviews} review fact(s) + {free} free edge(s)"
            if steps
            else "empty span (base tree == HEAD tree)"
        )
        print(
            f"satisfied: composed review coverage spans "
            f"{base_tree[:12]}..{head_tree[:12]} at HEAD ({detail}, 0 unresolved blocking)."
        )
        return 0

    if verdict["status"] == "blocked":
        unresolved = verdict.get("unresolved", [])
        print(
            f"blocking: coverage composes over {base_tree[:12]}..{head_tree[:12]} "
            f"but carries {len(unresolved)} unresolved BLOCKING finding(s):",
            file=sys.stderr,
        )
        for entry in unresolved[:5]:
            print(
                f"  - {entry.get('review_id')}/{entry.get('fid')}: "
                f"{entry.get('title', '<no title>')}",
                file=sys.stderr,
            )
        if len(unresolved) > 5:
            print(f"  (+{len(unresolved) - 5} more)", file=sys.stderr)
        for line in blocking_remedy_lines(unresolved):
            print(line, file=sys.stderr)
        return 1

    # A base advance moves the span's START node, so a branch whose own diff did
    # not move a byte reads as uncovered and buys a full re-review. Attempt the
    # transfer BEFORE printing anything: when it holds, this is a pass, and the
    # remedy block below would be describing a problem the operator does not
    # have. Condition 3 lives here rather than in the diagnosis because the test
    # evidence is this module's — and because the near miss (byte identity
    # holds, the suite has not met the merged tree) has a remedy worth naming: a
    # suite run, which is minutes against a cumulative's tens of them.
    transfer = coverage.diagnose_base_advance_transfer(
        project_dir,
        read.get("facts", []),
        base_tree,
        head_tree,
        diff_fn,
        verdict_fn,
    )
    transfer_stale: "str | None" = None
    if transfer is not None and transfer.get("status") == "match":
        tests_ok, tests_reason = suite_vouches_for_tree(project_dir, head_tree)
        if tests_ok:
            record_transfer_grant(
                project_dir,
                read.get("facts", []),
                transfer,
                base_tree,
                head_tree,
                "check-cumulative-critic",
            )
            advance = transfer["advance_files"]
            advanced = (
                "the advance's own diff was unreadable, so its size is unknown"
                if advance is None
                else f"the advance touched {len(advance)} judgeable file(s), none of them yours"
            )
            print(
                f"satisfied (transferred across base advance "
                f"{transfer['prior_base'][:12]}→{base_tree[:12]}; branch diff "
                f"byte-identical; suite current): {transfer['prior_reviews']} review "
                f"fact(s) already span {transfer['prior_base'][:12]}.."
                f"{transfer['prior_head'][:12]} with 0 unresolved blocking, the "
                f"{len(transfer['files'])} judgeable file(s) this branch changes are "
                f"byte-identical in both spans, and {advanced}. "
                f"Test evidence: {tests_reason}."
            )
            return 0
        transfer_stale = tests_reason

    print(
        f"uncovered: no composed review evidence spans "
        f"{base_tree[:12]}..{head_tree[:12]} at HEAD "
        f"({verdict.get('reason', 'no path')}).",
        file=sys.stderr,
    )
    # Everything else in this block is a pure function of the current tree, so
    # without this line round five reads exactly like round one — the measured
    # complaint from a six-round branch was that block #6 was indistinguishable
    # from block #1. Printed FIRST because it frames every remedy below it: the
    # question "is another round the right move" is answered differently on
    # round one than on round five, and the reader decides that before choosing
    # among the routes.
    print(
        coverage.format_branch_rounds(
            coverage.count_branch_rounds(
                project_dir, read.get("facts", []), resolved.get("merge_base", "")
            )
        ),
        file=sys.stderr,
    )
    # Surfaced FIRST among the remedies for the reason the two NOTEs below are
    # surfaced before the generic route: the reader acts on the first one they
    # meet, and this is the cheapest of all of them — a suite run against a
    # review round.
    if transfer_stale is not None:
        print(f"NOTE: {transfer_remedy(transfer, transfer_stale)}", file=sys.stderr)
    elif transfer is not None and transfer.get("status") == "unavailable":
        print(f"NOTE: {transfer_remedy(transfer, None)}", file=sys.stderr)
    # COV-7K4N: a stale remote base (origin/<b> behind an ancestor-of-HEAD local
    # <b>) drags already-reviewed work into the required span and reads as
    # uncovered — the cheap, correct remedy is `git push origin <b>`, not a full
    # re-review. Surface it BEFORE the generic remedy so the wrong action isn't
    # the first thing the reader reaches for.
    stale = coverage.diagnose_stale_remote_base(project_dir, resolved["base_branch"])
    if stale is not None and stale["ancestor_of_head"]:
        plural = "" if stale["commits_ahead"] == 1 else "s"
        prep = (
            f" (including an unpushed {stale['release_prep_subject']!r})"
            if stale["release_prep_subject"]
            else ""
        )
        print(
            f"NOTE: {stale['remote']} is {stale['commits_ahead']} commit{plural} behind "
            f"local {stale['local']}, which is an ancestor of HEAD{prep} — the base may "
            f"just be stale, not the code unreviewed. Try `git push origin {stale['local']}` "
            f"and re-check BEFORE a full review; the gate then re-anchors the merge-base to "
            f"{stale['local']}'s tree.",
            file=sys.stderr,
        )
    # A gap whose whole content is the builder's own non-blocking fixes needs a
    # different first sentence than a gap that is unreviewed work. Surface it
    # BEFORE the generic remedy for the same reason the stale-base NOTE is
    # surfaced there: the reader acts on the first route they meet, and the
    # generic route here is a 4-10 minute round that will hand them the next
    # one's findings.
    churn = coverage.diagnose_fix_churn(
        project_dir,
        read.get("facts", []),
        head_tree,
        base_tree,
        resolved.get("merge_base", ""),
        verdict_fn,
    )
    if churn is not None and churn.get("status") == "unavailable":
        # A degraded advisory that says nothing is indistinguishable from one
        # that found nothing, and the builder then runs the round this control
        # exists to prevent with no record that it never ran (learnings.md:
        # "'Advice fails soft' is not 'advice fails silent'").
        print(
            f"NOTE: the fix-churn diagnosis could not run ({churn['reason']}) — "
            f"this is not a finding that your gap is genuine work, only that the "
            f"cheap check was unavailable.",
            file=sys.stderr,
        )
    elif churn is not None:
        shown = ", ".join(churn["delta_files"][:4])
        if len(churn["delta_files"]) > 4:
            shown += f" (+{len(churn['delta_files']) - 4} more)"
        print(
            f"NOTE: coverage composes all the way to review {churn['fact_id']} "
            f"(taken on this branch, after the merge-base, 0 unresolved BLOCKING), "
            f"and every judgeable change since it is in a file that review's OWN "
            f"findings named ({shown}). That is FILE-level evidence for fix churn: "
            f"it rules out work in a file that review never saw, not new work "
            f"written into one it named. If those commits were only the fixes you "
            f"were closing, they were optional — the {churn['warning']} warning + "
            f"{churn['note']} note "
            f"finding(s) gated nothing. ONE `/prawduct:critic verify-resolutions` "
            f"closes it; fix nothing further first, or you will re-open it. For "
            f"anything still undecided, `prawduct-hook disposition "
            f"{churn['fact_id']} <fid> --accept \"<reason>\"` records a won't-fix, "
            f"moves no tree, and needs no review. Before you make the NEXT commit, "
            f"`prawduct-hook cost-of-commit` says whether it re-opens this gate — "
            f"the answer that used to be learnable only after committing.",
            file=sys.stderr,
        )
    # The generic routes stay available but stop being the LAST imperative when
    # the churn NOTE fired: an agent reading a stderr block commonly acts on the
    # final instruction, and unqualified that is the 4-10 minute round this
    # control exists to displace. The sibling stale-base NOTE solves the same
    # problem with the same instrument — qualifying its own advice rather than
    # suppressing the block, so no remedy is lost when the diagnosis is wrong.
    lead = (
        "If that diagnosis does not fit — you bundled new work into those commits, "
        "or the gap is something else — the general routes are: run "
        if churn is not None and churn.get("status") == "churn"
        else "Run "
    )
    print(
        lead + "/prawduct:critic cumulative — it reviews the whole span and records "
        "the fact composition needs. If a pre-commit review was followed by a "
        "selective commit (only part of the reviewed state committed), the "
        "commit's tree was never reviewed — /prawduct:critic verify-resolutions "
        "reviews that delta and closes the gap. If verify-resolutions already ran "
        "but the working tree still holds an uncommitted fix with no committed "
        "delta, its fact anchored the WORKING tree, not committed HEAD — commit "
        "that tree VERBATIM and the fact ends at the tree this gate targets, so "
        "no further pass is owed. Only a selective or further-edited commit "
        "leaves a gap to close.",
        file=sys.stderr,
    )
    return 1


def verify_coverage(project_dir: Path) -> int:
    """Critic Goal-1 helper (v1.4 F4b): when ``coverage_required: true`` in
    project-state.yaml, verify every changed file in the diff appears in
    ``.test-evidence.json``'s ``changes_referenced`` list.

    Exit codes:
      0 — check passed, or skipped (``coverage_required: false`` — the v1.4
          default; opt-in by design).
      1 — at least one changed file the evidence can judge is missing from
          ``changes_referenced``, or a precondition failed (evidence
          missing/invalid, schema lacks F4a fields, git base unresolved).

    Gate-soundness ch.1: the gate only blocks on files its evidence producer
    can vouch for. Files listed in ``changes_unjudged`` (non-Python, symbol-less,
    deleted — see ``bin/test-reference-verify``) and files absent from the
    working tree (deleted on the branch) are reported informationally on
    stdout, never as ``missing-coverage``. Before this split, the whole-branch
    comparison guaranteed false blockers on docs/config changes, which trained
    products to neutralize the gate (scriob 4ca5bd3) — an unsatisfiable gate
    is worse than no gate.

    stderr lists each missing file with language scaled to the declared
    ``coverage_level`` — ``referenced`` (floor) vs ``executed`` (real
    coverage tool) — so the Critic can quote it directly in BLOCKING
    findings without re-deriving the wording.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    state_path = prawduct_dir / "project-state.yaml"

    if not read_bool_yaml_key(state_path, "coverage_required"):
        print("skipped: coverage_required is false (default in v1.4)")
        return 0

    evidence_path = prawduct_dir / ".test-evidence.json"
    if not evidence_path.is_file():
        print(
            f"error: coverage_required=true but {evidence_path} is missing — "
            "run the test suite + verifier first.",
            file=sys.stderr,
        )
        return 1

    try:
        evidence = json.loads(evidence_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: cannot read evidence: {exc}", file=sys.stderr)
        return 1

    if "verifier" not in evidence:
        print(
            "error: coverage_required=true but evidence lacks F4a schema "
            "(no `verifier` field) — emit coverage fields with "
            "`bin/test-reference-verify` (or a stronger product-specific "
            "verifier) before re-running.",
            file=sys.stderr,
        )
        return 1

    ok, reason = _validate_evidence_schema(evidence)
    if not ok:
        print(f"error: {reason}", file=sys.stderr)
        return 1

    coverage_level = evidence["coverage_level"]
    referenced = set(evidence.get("changes_referenced", []))
    unjudged = set(evidence.get("changes_unjudged", []))

    base, base_reason = coverage._coverage_resolve_base(project_dir)
    if base is None:
        print(f"error: cannot resolve diff base — {base_reason}", file=sys.stderr)
        return 1

    try:
        changed = coverage._coverage_changed_files(project_dir, base)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # A file the evidence declares unjudgeable, or one no longer on disk
    # (deleted on the branch — nothing to test), is outside the gate's
    # jurisdiction: reported, never blocked on.
    skipped = [
        f for f in changed
        if f in unjudged or not (project_dir / f).is_file()
    ]
    missing = [
        f for f in changed
        if f not in referenced and f not in skipped
    ]
    if skipped:
        print(
            f"note: {len(skipped)} changed file(s) outside the verifier's "
            f"judgment (changes_unjudged / deleted) — reported, not gated "
            f"(level: {coverage_level})."
        )
    if not missing:
        print(
            f"ok: {len(changed) - len(skipped)} judged changed file(s) covered "
            f"(level: {coverage_level})"
        )
        return 0

    # Severity wording is per the F4a spec — the floor (``referenced``)
    # explicitly disclaims execution, the real-coverage level
    # (``executed``) asserts it. Critic quotes these lines verbatim.
    if coverage_level == "executed":
        suffix = "has no executing test."
    else:
        suffix = (
            "is not referenced by any executed test "
            "(floor check — does not prove execution)."
        )

    for m in missing:
        print(
            f"missing-coverage: {m} (coverage_level: {coverage_level}) — {suffix}",
            file=sys.stderr,
        )
    return 1
