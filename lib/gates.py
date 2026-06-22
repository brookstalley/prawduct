"""Session-end governance gates + test-evidence/critic-findings validators.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 6). Holds the gate
*decision helpers* the Stop hook orchestrates — test-evidence currency + schema
validation, critic-findings schema + cumulative/verify-resolutions gate logic,
build-plan chunk counting, and the trivial/build-plan state probes — plus the
four self-contained gate CLI commands (``test_status`` / ``validate_evidence`` /
``check_cumulative_critic`` / ``verify_coverage``). The hook keeps thin ``cmd_*``
wrappers delegating here via the lazy ``_gates()`` accessor.

``cmd_stop`` itself STAYS in the hook (it is the deliberately-inline hot-path
gate per design constraint 1 + Chunk 7, and it uses the hook-resident gate
*attribution* machinery shared with ``cmd_clear``); it calls these helpers via
``_gates()``. ``_has_active_build_plan_file`` and ``_is_trivial_fileset_eligible``
were reassigned here (they are gate logic, lib-clean) from the briefing region.

Depends on its lib siblings ``gitstate`` / ``coverage`` / ``buildplan_refs``
(build-plan Status parsing, including ``_count_build_plan_chunks``) and ``core``
(``read_bool_yaml_key`` — canonical twin of the hook's parity-pinned inline
mirror), plus the stdlib — the DAG node
``gitstate``/``coverage``/``buildplan_refs`` ← ``gates``.
"""


from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import buildplan_refs, coverage, gitstate
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
}


def tests_are_current(project_dir: Path) -> tuple[bool, str]:
    """Decide whether saved test evidence is fresh enough to trust.

    Uses a "trust the cycle" model: evidence is current if it was written
    during this session (timestamp >= session start) and all tests passed.
    No tree-hashing or content fingerprinting (those mechanisms were
    removed pre-v1.4 after chronic false positives from metadata churn) —
    the build cycle (write code → run tests → Critic reviews) is the
    trust boundary.

    Falls back to timestamp-only comparison when no session-start marker
    exists (e.g., running outside a governed session).

    Returns (is_current, reason). reason is a short human-readable string suitable
    for printing back to the agent.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    evidence_path = prawduct_dir / ".test-evidence.json"
    if not evidence_path.is_file():
        return False, "no .test-evidence.json on disk"

    try:
        evidence = json.loads(evidence_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"unreadable evidence ({exc})"

    if not isinstance(evidence, dict):
        return False, "evidence is not a JSON object"

    # Schema check — catches writer typos like ``ran_at`` for ``timestamp`` or
    # ``num_passed`` for ``passed``. Without this, missing fields silently fall
    # through ``.get()`` calls and the evidence parses as "no failures, no
    # timestamp" which the freshness check below would reject for the wrong
    # reason. Loud failure makes the writer bug obvious.
    schema_ok, schema_err = _validate_evidence_schema(evidence)
    if not schema_ok:
        return False, schema_err

    # Test pass/fail check — fail counts make evidence stale regardless of timing.
    failed = evidence.get("failed")
    if isinstance(failed, int) and failed > 0:
        return False, f"{failed} test(s) failing in saved evidence"

    # Timestamp check — evidence must have been written during this session.
    evidence_ts = evidence.get("timestamp")
    if not isinstance(evidence_ts, str) or not evidence_ts:
        return False, "no timestamp in evidence"

    session_start = _read_session_start(prawduct_dir)
    if session_start:
        if evidence_ts >= session_start:
            return True, f"evidence from this session ({evidence_ts})"
        return False, f"evidence predates session ({evidence_ts} < {session_start})"

    # No session-start marker — fall back to recency check.
    # Evidence exists with passing tests and a timestamp, but we can't verify
    # it's from this session. Accept it with a note.
    return True, f"evidence has passing tests ({evidence_ts}, no session marker to verify)"


def _read_session_start(prawduct_dir: Path) -> str:
    """Content of the ``.session-start`` marker, or ``""`` when the marker is
    missing or unreadable. Shared by the test-evidence freshness check
    (:func:`tests_are_current`) and the PR gate's ledger-fallback freshness
    bound (CRT-8W3F) — both compare ISO-8601 UTC strings against it."""
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
        # CRT-4J8W — extends_cumulative chains a verify-resolutions record
        # to the cumulative review it extends, so the PR gate can accept
        # cumulative@X + clean delta-review covering X..HEAD instead of
        # forcing a full bundle re-review. Optional; when present and
        # non-null it must be a dict whose commit_reviewed is a non-empty
        # string — anything else is writer drift (a malformed anchor would
        # silently break the chain check at the gate), surfaced here.
        if "extends_cumulative" in data:
            ext = data["extends_cumulative"]
            if ext is not None:
                if not isinstance(ext, dict):
                    return False
                anchor = ext.get("commit_reviewed")
                if not isinstance(anchor, str) or not anchor.strip():
                    return False
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


def _chain_anchor(data: dict) -> str | None:
    """Return the cumulative anchor a verify-resolutions pass over ``data``
    would extend, or ``None`` when the record is not chain-extendable.

    Chain-extendable (CRT-4J8W): a ``cumulative``-mode record (anchor = its
    own ``commit_reviewed`` — the bundle review being extended), or a
    ``verify-resolutions``-mode record that itself carries a valid
    ``extends_cumulative`` (multi-link propagation: the original anchor is
    carried forward; ``files_reviewed`` accumulates link by link, so the
    gate's ``X..HEAD ⊆ files_reviewed`` check stays sound, and the
    scope-widening demotion bounds chain length naturally). Prior BLOCKING
    findings do NOT disqualify the anchor — the verify pass adjudicates
    resolution and re-emits anything unresolved, and the PR gate accepts
    only 0-BLOCKING chain records (build plan gate-soundness ch.5
    declared decision).
    """
    mode = data.get("mode")
    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return None
    if mode == _CRITIC_MODE_CUMULATIVE:
        return commit_reviewed
    if mode == _CRITIC_MODE_VERIFY_RESOLUTIONS:
        ext = data.get("extends_cumulative")
        if isinstance(ext, dict):
            anchor = ext.get("commit_reviewed")
            if isinstance(anchor, str) and anchor.strip():
                return anchor
    return None


def _compute_verify_resolutions_scope(
    prawduct_dir: Path, project_dir: Path
) -> tuple[list[str], str]:
    """Compute the file scope a ``/prawduct:critic verify-resolutions`` pass should review.

    Reads the *prior* ``.prawduct/.critic-findings.json`` (the record the
    builder is about to re-verify) and returns the union of:

      1. ``files_reviewed`` from the prior record — files the Critic already
         examined — but only when actionable findings (BLOCKING or WARNING)
         exist. NOTE-only and clean records have nothing to verify.
      2. Files changed since ``commit_reviewed`` — anchor recorded in Chunk
         01 — computed as ``git diff --name-only <commit_reviewed>`` plus
         untracked files. Mirrors ``_coverage_changed_files``'s diff +
         ls-files-others union so the verify pass sees the same shape the
         cumulative-Critic flow does.

    Returns ``(scope, reason)``. ``scope`` is sorted; ``reason`` is human-
    readable. Successful computations return a non-empty scope and a reason
    prefixed ``ok:``. All other cases return an empty scope and a categorized
    reason so the caller (Critic agent or stop-hook gate) can fall safely
    through to ``/prawduct:critic chunk`` or ``/prawduct:critic final``:

      - ``no-findings:`` — prior findings file missing.
      - ``unreadable-findings:`` — JSON parse or I/O failure.
      - ``no-commit-reviewed:`` — anchor absent / null / empty. Pre-v1.5
        records are valid for the schema but cannot serve as a verify
        baseline; the helper fails closed.
      - ``no-actionable-findings:`` — only NOTEs (or empty findings). Verify-
        resolutions has nothing to re-check.
      - ``invalid-files-reviewed:`` — schema-permitted but unusable
        (non-list or empty list).
      - ``unresolved-commit:`` — ``commit_reviewed`` does not resolve in
        the current repo (rebase, force-push, or simply never on this
        branch). Cannot compute a delta.
      - ``non-ancestor-commit:`` — ``commit_reviewed`` resolves but is not
        an ancestor of HEAD (CRT-8H3R — the session switched to a
        divergent/sibling branch). A delta would span the divergence point
        and surface the sibling branch's changes as phantom findings;
        demote rather than compute it.
      - ``git-diff-failed:`` — the diff invocation itself failed.
      - ``scope-widened:`` — demotion criterion ``len(delta) > 2 * len(prior)
        + 5`` tripped. The prior surface no longer covers what changed; a
        partial review would mislead. Fall through to ``/prawduct:critic final``.

    Fail-closed throughout — when the helper cannot anchor a delta it
    refuses to compute one rather than silently shrinking the review.
    """
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return [], (
            "no-findings: .prawduct/.critic-findings.json is missing — "
            "run /prawduct:critic chunk or /prawduct:critic final first"
        )
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return [], f"unreadable-findings: {exc}"

    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return [], (
            "no-commit-reviewed: prior findings lack commit_reviewed — "
            "cannot anchor delta. Run /prawduct:critic chunk or /prawduct:critic final."
        )

    findings = data.get("findings")
    if not isinstance(findings, list):
        return [], "invalid-findings: prior findings.findings is not a list"
    actionable = [
        f for f in findings
        if isinstance(f, dict) and f.get("severity") in ("blocking", "warning")
    ]
    # CRT-4J8W — a chain-extendable prior (cumulative, or a chain record
    # propagating its anchor) with no actionable findings is still a valid
    # verify baseline IF something changed since the review: the pass has a
    # delta to review and the resulting record extends the cumulative's
    # vouching to HEAD (the "no-delta" refusal below keeps the original
    # demotion when there is truly nothing to look at). Non-chain priors
    # keep today's demotion unchanged.
    chain_anchor = _chain_anchor(data)
    if not actionable and chain_anchor is None:
        return [], (
            "no-actionable-findings: prior review had no blocking/warning "
            "findings — verify-resolutions has nothing to verify. "
            "Run /prawduct:critic chunk or /prawduct:critic final."
        )

    prior_files = data.get("files_reviewed")
    if not isinstance(prior_files, list) or not prior_files:
        return [], (
            "invalid-files-reviewed: prior findings.files_reviewed is "
            "missing or empty"
        )
    prior_files_set = {f for f in prior_files if isinstance(f, str) and f.strip()}

    # rev-parse with the `^{commit}` peel rejects non-commit refs and SHAs
    # that don't resolve. fail-closed: any non-0 → no delta computable.
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit_reviewed}^{{commit}}"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return [], (
            f"unresolved-commit: commit_reviewed {commit_reviewed[:12]} "
            "does not resolve in the current repo — cannot compute delta. "
            "Run /prawduct:critic chunk or /prawduct:critic final."
        )

    # CRT-8H3R: the anchor resolves, but if it is not an ancestor of HEAD the
    # session switched to a divergent/sibling branch — a `commit_reviewed..`
    # delta would span the divergence and surface that branch's changes as
    # phantom findings. Fail closed: only a genuine ancestor (exit 0) anchors
    # a delta; non-ancestor (exit 1) and any other failure demote to final.
    ancestor_proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_reviewed, "HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if ancestor_proc.returncode != 0:
        return [], (
            f"non-ancestor-commit: commit_reviewed {commit_reviewed[:12]} "
            "resolves but is not an ancestor of HEAD — the session switched "
            "to a divergent/sibling branch, so a delta would surface phantom "
            "findings. Run /prawduct:critic chunk or /prawduct:critic final."
        )

    diff_proc = subprocess.run(
        ["git", "diff", "--name-only", commit_reviewed],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if diff_proc.returncode != 0:
        return [], f"git-diff-failed: {diff_proc.stderr.strip()}"
    delta_files = {
        line.strip() for line in diff_proc.stdout.splitlines() if line.strip()
    }

    ls_proc = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if ls_proc.returncode == 0:
        delta_files.update(
            line.strip() for line in ls_proc.stdout.splitlines() if line.strip()
        )

    # Filter metadata before threshold and scope union. The session-end
    # gate already ignores ``_is_metadata_path`` files (``.prawduct/``,
    # ``.claude/settings.json``, etc.) when computing the chunk diff;
    # counting them here would inflate ``delta_files`` against the
    # widening threshold and falsely demote a legitimate fix flow whose
    # only delta beyond the prior surface is incidental state churn
    # (the very ``.critic-findings.json`` the prior review wrote,
    # ``.session-reflected``, ``.session-git-baseline``, etc.). Symmetric
    # with ``_verify_resolutions_gate_check`` — both sides of "what
    # counts as a chunk file" agree.
    delta_files = {f for f in delta_files if not gitstate._is_metadata_path(f)}

    # Demotion: when the delta has grown well past the prior review's
    # surface, a verify pass would mislead — most of what changed wasn't
    # part of the prior review's scope at all. Threshold mirrors the build
    # plan (Chunk 02): linear factor 2 plus floor 5 so small priors don't
    # demote on a single unrelated edit.
    if len(delta_files) > 2 * len(prior_files_set) + 5:
        return [], (
            f"scope-widened: {len(delta_files)} files changed since "
            f"commit_reviewed (prior surface {len(prior_files_set)} files; "
            f"demotion threshold len(delta) > 2 * prior + 5). Fall through "
            "to /prawduct:critic chunk or /prawduct:critic final."
        )

    # CRT-4J8W — chain-extendable prior with neither actionable findings nor
    # a delta: nothing to verify AND nothing to extend over; keep the
    # original demotion semantics rather than running an empty review.
    if not actionable and not delta_files:
        return [], (
            "no-actionable-findings: prior review had no blocking/warning "
            "findings and nothing changed since commit_reviewed — "
            "verify-resolutions has nothing to verify. "
            "Run /prawduct:critic chunk or /prawduct:critic final."
        )

    scope = sorted(prior_files_set | delta_files)
    reason = (
        f"ok: scope = {len(scope)} files "
        f"(prior surface {len(prior_files_set)} + delta {len(delta_files)} "
        f"since {commit_reviewed[:12]})"
    )
    # CRT-4J8W — tell the Critic which cumulative this verify pass extends,
    # so it embeds ``extends_cumulative: {"commit_reviewed": <anchor>}`` in
    # the new record and the PR gate can accept the chain.
    if chain_anchor is not None:
        reason += f" extends-cumulative={chain_anchor}"
    return scope, reason


def _verify_resolutions_gate_check(
    prawduct_dir: Path, project_dir: Path, findings_path: Path
) -> tuple[bool, str]:
    """Stop-hook gate helper: when the Critic findings file is in
    ``verify-resolutions`` mode, accept only when the current chunk diff is
    a subset of the verify pass's declared scope.

    Returns ``(True, "")`` for any other mode — the standard gate logic
    applies. For ``verify-resolutions``:

      - ``(True, "")`` — current session-changed files (excluding metadata
        paths the regular Critic gate also ignores) are all within the
        findings' ``files_reviewed`` set.
      - ``(False, reason)`` — at least one chunk-diff file is outside the
        declared scope. The verify pass is stale relative to the current
        diff; the gate keeps the block in place and surfaces the reason so
        the builder runs ``/prawduct:critic chunk`` or ``/prawduct:critic final`` instead.

    Fail-closed: a JSON read failure or schema gap returns ``(False, reason)``
    rather than silently clearing the gate (see learnings: "Escape hatches
    in classification create silent failures").
    """
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return False, (
            f"verify-resolutions findings unreadable ({exc}). Run /prawduct:critic "
            "chunk or /prawduct:critic final."
        )

    if data.get("mode") != _CRITIC_MODE_VERIFY_RESOLUTIONS:
        return True, ""

    files_reviewed = data.get("files_reviewed")
    if not isinstance(files_reviewed, list):
        return False, (
            "verify-resolutions findings have no files_reviewed list. "
            "Run /prawduct:critic chunk or /prawduct:critic final."
        )
    scope = {f for f in files_reviewed if isinstance(f, str) and f.strip()}

    session_changed = {
        f for f in gitstate._get_session_changed_files(project_dir)
        if not gitstate._is_metadata_path(f)
    }

    out_of_scope = sorted(session_changed - scope)
    if not out_of_scope:
        return True, ""

    sample = ", ".join(out_of_scope[:3])
    more = f" (+{len(out_of_scope) - 3} more)" if len(out_of_scope) > 3 else ""
    return False, (
        f"verify-resolutions findings declare {len(scope)} file(s) in scope "
        f"but the current chunk diff includes {len(out_of_scope)} file(s) "
        f"outside scope ({sample}{more}). Run /prawduct:critic chunk or /prawduct:critic final."
    )


_CRITIC_MODE_GOALS_1_3_ONLY = frozenset({
    _CRITIC_MODE_CHUNK,
    _CRITIC_MODE_VERIFY_RESOLUTIONS,
})


def critic_findings_satisfy_session_gate(
    prawduct_dir: Path, project_dir: Path
) -> tuple[bool, str]:
    """Shared session Critic gate: does ``.critic-findings.json`` vouch for
    this session's changes?

    Single source of truth (STH-4F7C) for the freshness check previously
    duplicated — and diverged — between ``cmd_stop``'s blocking gate
    (``bin/prawduct-hook``) and the session-start advisory
    (``briefing._check_previous_session_gates``): the advisory copy had not
    gained the verify-resolutions scope check, so it could report a stale
    record as satisfying. Satisfied requires ALL of:

    1. ``.critic-findings.json`` and ``.session-start`` both exist;
    2. findings mtime is strictly newer than session start. STH-6B4R:
       identical-precision compare — the mtime is formatted to the same
       whole-second ``%Y-%m-%dT%H:%M:%SZ`` shape ``.session-start`` is
       written in, so the comparison is order-preserving lexicographic with
       no format mismatch on either side. Tie rule: ``findings_mtime ==
       session_start`` is NOT fresh — the strict ``>`` rejects a
       same-whole-second tie, consistent with the cumulative-critic site's
       ``<= -> stale``. Only ``_test_status``'s evidence freshness uses
       ``>=`` (deliberately);
    3. the findings are schema-valid (:func:`validate_critic_findings`);
    4. for a ``verify-resolutions`` record, the current session diff is
       within the declared scope (:func:`_verify_resolutions_gate_check`).

    Returns:
      - ``(True, "")`` — gate satisfied.
      - ``(False, "")`` — no qualifying findings (missing, stale, or
        schema-invalid); the caller phrases its own "review not recorded"
        message.
      - ``(False, reason)`` — fresh, valid ``verify-resolutions`` findings
        whose declared scope the session diff has outgrown; ``reason`` names
        the widening files (``cmd_stop`` surfaces it verbatim in its
        dedicated blocker variant).

    No-raise, fail-closed: any unexpected error returns ``(False, "")``.
    """
    critic_findings = prawduct_dir / ".critic-findings.json"
    session_start = _read_session_start(prawduct_dir)
    if not critic_findings.is_file() or not session_start:
        return False, ""
    try:
        findings_mtime = datetime.fromtimestamp(
            critic_findings.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        if findings_mtime > session_start and validate_critic_findings(critic_findings):
            return _verify_resolutions_gate_check(prawduct_dir, project_dir, critic_findings)
        return False, ""
    except Exception:  # prawduct:allow prawduct/broad-except -- gate check must not crash session start/end
        return False, ""


def _critic_session_satisfies_gate(prawduct_dir: Path) -> tuple[bool, str]:
    """Check whether the latest Critic findings satisfy end-of-cycle synthesis.

    Returns ``(True, "")`` when the gate is satisfied, ``(False, reason)``
    otherwise. The gate is advisory: it fires when a multi-chunk build plan
    has all chunks marked ``[x]`` but the most recent Critic review ran
    Goals 1-3 only — ``chunk`` and ``verify-resolutions`` modes both skip
    end-of-cycle goals (Coherence, Design, Learnings Cross-Check, Backlog
    Reconciliation, Framework-Specific Checks). v1.5 Chunk 02 extended the
    case-4 trigger to verify-resolutions so a plan that closes with a delta
    re-review doesn't silently bypass final-mode synthesis.

    Specific cases (in order):
    1. No build plan, or no chunks declared → satisfied (non-chunked work).
    2. Single-chunk plan → satisfied (the one Critic run is the final).
    3. Multi-chunk plan with incomplete chunks → satisfied (mid-cycle).
    4. Multi-chunk plan, all chunks ``[x]``, latest mode is in
       ``_CRITIC_MODE_GOALS_1_3_ONLY`` (chunk or verify-resolutions)
       → unsatisfied. Run ``/prawduct:critic final`` for end-of-cycle synthesis.
    5. Multi-chunk plan, all chunks ``[x]``, latest mode is ``_CRITIC_MODE_FINAL``
       (or absent — legacy records default to final), or ``_CRITIC_MODE_CUMULATIVE``
       → satisfied (full goal set ran).

    Caller is expected to invoke this only after the existing critic-required
    blocker has cleared (i.e. findings exist and ``validate_critic_findings``
    returned True). Defensive checks here keep the helper standalone-safe.
    """
    total, complete = buildplan_refs._count_build_plan_chunks(prawduct_dir)
    if total == 0:
        return True, ""
    if total == 1:
        return True, ""
    if complete < total:
        return True, ""

    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return True, ""
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return True, ""
    mode = data.get("mode", _CRITIC_MODE_FINAL)
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


def _has_active_build_plan_file(prawduct_dir: Path) -> bool:
    """Return True if build-plan.md has at least one incomplete chunk.

    A completed plan (all [x]) or a missing file both return False — only an
    in-progress plan with remaining work triggers governance gates.
    """
    status = buildplan_refs._parse_build_plan_status(prawduct_dir)
    return bool(status.get("current_chunk"))


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


def _record_covers_head(project_dir: Path, commit_reviewed) -> tuple[str, str]:
    """Evaluate the CRT-7M2D coverage rule: does ``commit_reviewed`` cover HEAD?

    Coverage = ``commit_reviewed`` resolves to HEAD itself, OR every file
    changed in ``commit_reviewed..HEAD`` is documentation (``.md``).

    Returns ``(status, detail)``:
      - ``("covered", "")``
      - ``("stale", "<reviewed12>..<head12>: <sample non-doc files>")``
      - ``("no-anchor", <reason>)`` — ``commit_reviewed`` absent/blank.
      - ``("unresolved", <reason>)`` — HEAD or ``commit_reviewed`` does not
        resolve in this repo.
      - ``("error", <reason>)`` — a git step itself failed. Callers fail
        closed on all three failure statuses (the gate must not vouch for
        coverage it can't verify — "Escape hatches in classification create
        silent failures", learnings.md).

    Shared by the cumulative path and the CRT-4J8W chain path of
    :func:`check_cumulative_critic` so both judge HEAD-coverage identically.
    """
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return "no-anchor", "record lacks a commit_reviewed anchor"
    try:
        head_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
        reviewed_proc = subprocess.run(
            ["git", "rev-parse", "--verify", f"{commit_reviewed}^{{commit}}"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- fail closed if git is unavailable
        return "error", f"could not resolve commits ({exc!r})"
    if head_proc.returncode != 0 or reviewed_proc.returncode != 0:
        return "unresolved", (
            f"could not resolve HEAD or commit_reviewed ({commit_reviewed[:12]})"
        )
    head_sha = head_proc.stdout.strip()
    reviewed_sha = reviewed_proc.stdout.strip()
    if reviewed_sha == head_sha:
        return "covered", ""
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", f"{reviewed_sha}..HEAD"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- fail closed if git diff fails
        return "error", f"could not diff {reviewed_sha[:12]}..HEAD ({exc!r})"
    if diff_proc.returncode != 0:
        return "error", (
            f"git diff {reviewed_sha[:12]}..HEAD failed: {diff_proc.stderr.strip()}"
        )
    changed = [ln.strip() for ln in diff_proc.stdout.splitlines() if ln.strip()]
    non_doc = [f for f in changed if not f.endswith(".md")]
    if non_doc:
        sample = ", ".join(non_doc[:3])
        more = f" (+{len(non_doc) - 3} more)" if len(non_doc) > 3 else ""
        return "stale", f"{reviewed_sha[:12]}..{head_sha[:12]}: {sample}{more}"
    # Only .md changed since the review — coverage holds, no re-run.
    return "covered", ""


def check_cumulative_critic(project_dir: Path) -> int:
    """Structural gate for `/prawduct:pr create`: require a fresh cumulative-Critic record.

    Exit 0 only when the Critic findings file exists, parses, is schema-valid
    (``validate_critic_findings``), contains no unresolved BLOCKING findings
    (WARNING and NOTE are advisory at the PR gate, matching the PR reviewer's
    semantics), and is ONE of:

    1. **A HEAD-covering cumulative record** — ``mode == _CRITIC_MODE_CUMULATIVE``
       and the recorded ``commit_reviewed`` covers HEAD (CRT-7M2D): it IS HEAD,
       or the only changes since are documentation (``.md``). A clean cumulative
       review vouches for the *code* being shipped — a code change since the
       review fails the gate (re-run genuinely needed), a doc-only change does
       not (no needless re-run). This replaced the mtime-vs-``.session-start``
       recency check, which both false-passed stale records and forced a full
       re-run after every inert post-review fix.

    2. **A chain record** (CRT-4J8W — the run-count fix): ``mode ==
       _CRITIC_MODE_VERIFY_RESOLUTIONS`` with an ``extends_cumulative`` anchor
       ``X`` that resolves, whose own ``commit_reviewed`` covers HEAD (same
       rule as above), and where every non-``.md``, non-metadata file changed
       in ``X..HEAD`` is in the record's ``files_reviewed`` — fail closed on
       any gap. Soundness: cumulative@X vouches for the bundle; a 0-BLOCKING
       delta review whose recorded scope covers ``X..HEAD`` extends that
       vouching to HEAD — the same shape as the doc-only allowance, with
       scope verification. This turns the fix-after-cumulative path into a
       1-2 min delta review instead of a full bundle re-review. The ``.md``
       and metadata exclusions mirror the doc-only allowance and the
       scope/stop-hook helpers' ``_is_metadata_path`` symmetry (gate-soundness
       ch.5 declared decision).

    **Ledger fallback** (review-proportionality ch.02): when the latest
    findings record is the wrong KIND (chunk/final, or verify-resolutions
    with no chain anchor), the gate scans
    ``.prawduct/.governance-ledger.jsonl`` newest-first for the first
    qualifying ``review.critic`` payload and evaluates THAT under the same
    checks unchanged — a stale or blocking ledger record still fails
    honestly. The fallback record must additionally be from THIS session
    (envelope ``ts >= .session-start``; fail closed without the marker —
    CRT-8W3F, see :func:`_ledger_fallback_record`). Corrupt lines are
    skipped with a stderr note; no qualifying event → the original
    wrong-mode / chain-missing-anchor message.

    Exit 1 otherwise. stderr names the specific check that failed so the
    caller (`/prawduct:pr` skill) can present an actionable message to the user.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    findings_path = prawduct_dir / ".critic-findings.json"

    if not findings_path.is_file():
        print(
            "missing: no cumulative-Critic findings at "
            f"{findings_path}. Run /prawduct:critic cumulative before opening a PR.",
            file=sys.stderr,
        )
        return 1

    if not validate_critic_findings(findings_path):
        print(
            f"invalid: {findings_path} did not pass schema validation",
            file=sys.stderr,
        )
        return 1

    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"unreadable: {exc}", file=sys.stderr)
        return 1

    if _pr_gate_record_qualifies(data):
        return _evaluate_pr_gate_record(project_dir, data, str(findings_path))

    # Ledger fallback (review-proportionality ch.02): the latest findings
    # record is the wrong KIND for this gate (a chunk/final review, or a
    # verify pass with no chain anchor) — but the append-only ledger may
    # still hold the qualifying review this branch already paid for. Scan
    # newest-first for the first qualifying ``review.critic`` payload and
    # evaluate THAT under the same checks unchanged — a stale ledger record
    # still fails honestly. This dissolves the single-slot conflict: a chunk
    # review after the cumulative no longer destroys the PR gate's evidence.
    fallback = _ledger_fallback_record(prawduct_dir)
    if fallback is not None:
        lineno, payload, ledger_file = fallback
        print(
            f"ledger-fallback: latest findings record (mode "
            f"{data.get('mode')!r}) does not qualify at the PR gate; "
            f"evaluating the newest qualifying review.critic event "
            f"({ledger_file.name} line {lineno}) instead.",
            file=sys.stderr,
        )
        return _evaluate_pr_gate_record(
            project_dir, payload, f"{ledger_file} line {lineno}, ledger fallback"
        )

    mode = data.get("mode")
    if mode == _CRITIC_MODE_VERIFY_RESOLUTIONS:
        print(
            "chain-missing-anchor: this verify-resolutions record has no "
            "extends_cumulative anchor — it re-verifies prior findings but "
            "cannot certify the bundle. Chain sequence: land all non-.md "
            "fixes, run /prawduct:critic cumulative once; for fixes AFTER "
            "the cumulative — fix, commit, then /prawduct:critic "
            "verify-resolutions (the Critic embeds the anchor when the "
            "prior record is that cumulative). If the cumulative record is "
            "gone, re-run /prawduct:critic cumulative.",
            file=sys.stderr,
        )
        return 1
    print(
        f"wrong-mode: findings mode is {mode!r}, expected cumulative "
        f"({_CRITIC_MODE_CUMULATIVE!r}) or a chained verify-resolutions "
        "record (CRT-4J8W). Sequence: land ALL non-.md fixes first, then "
        "run /prawduct:critic cumulative once; for fixes after the "
        "cumulative — fix, commit, then /prawduct:critic verify-resolutions "
        "(the chain record extends the cumulative to HEAD; no full re-run).",
        file=sys.stderr,
    )
    return 1


def _pr_gate_record_qualifies(data: dict) -> bool:
    """Is this record the right KIND for the PR gate — a cumulative, or a
    verify-resolutions carrying a chain anchor? Kind only; coverage, chain
    scope, and blocking findings are judged by :func:`_evaluate_pr_gate_record`."""
    mode = data.get("mode")
    if mode == _CRITIC_MODE_CUMULATIVE:
        return True
    if mode == _CRITIC_MODE_VERIFY_RESOLUTIONS:
        ext = data.get("extends_cumulative")
        anchor = ext.get("commit_reviewed") if isinstance(ext, dict) else None
        return isinstance(anchor, str) and bool(anchor.strip())
    return False


def _ledger_fallback_record(prawduct_dir: Path):
    """Newest qualifying ``review.critic`` payload from the governance ledger,
    as ``(lineno, payload, ledger_path)`` — or ``None``. Skips corrupt lines
    (the reader emits stderr notes), non-review events, schema-invalid
    payloads, and payloads of the wrong kind. Never raises — the gate must
    fail with its own honest message, not a fallback crash.

    **Freshness bound (CRT-8W3F).** Unlike the single-slot findings file,
    the ledger keeps every review forever — so "newest qualifying" alone
    would let a days-old cumulative from prior work satisfy the PR gate
    whenever only ``.md`` changed since. A qualifying event is therefore
    accepted only when its envelope ``ts`` is ``>= .session-start`` (the
    same ISO-8601 string comparison :func:`tests_are_current` uses). Fail
    closed: a missing/unreadable session marker, or a qualifying event with
    no usable ``ts``, yields no fallback — the gate's own wrong-mode /
    chain-missing-anchor message stands, and the skip is taught on stderr.
    """
    try:
        from . import ledger  # noqa: PLC0415 — lazy keeps gates' import DAG light

        session_start = _read_session_start(prawduct_dir)
        for lineno, event in ledger.iter_events_newest_first(prawduct_dir):
            if event.get("event") != "review.critic":
                continue
            payload = event.get("review")
            if not isinstance(payload, dict):
                continue
            if not _validate_critic_findings_data(payload):
                print(
                    f"ledger: skipping line {lineno} (review payload failed "
                    "schema validation)",
                    file=sys.stderr,
                )
                continue
            if not _pr_gate_record_qualifies(payload):
                continue
            # Freshness — judged only for records that would otherwise be
            # selected, so the notes below never fire for unrelated events.
            ts = event.get("ts")
            if not isinstance(ts, str) or not ts:
                print(
                    f"ledger: skipping line {lineno} (no envelope ts — "
                    "freshness unverifiable, CRT-8W3F)",
                    file=sys.stderr,
                )
                continue
            if not session_start:
                print(
                    f"ledger: line {lineno} qualifies but there is no "
                    ".session-start marker to verify it is from this "
                    "session — failing closed (CRT-8W3F)",
                    file=sys.stderr,
                )
                return None
            if ts < session_start:
                print(
                    f"ledger: skipping line {lineno} (predates session: "
                    f"{ts} < {session_start} — run /prawduct:critic "
                    "cumulative this session, CRT-8W3F)",
                    file=sys.stderr,
                )
                continue
            return lineno, payload, ledger.ledger_path(prawduct_dir)
    except Exception:  # prawduct:allow prawduct/broad-except -- fallback is best-effort; the gate's own message stands
        return None
    return None


def _evaluate_pr_gate_record(project_dir: Path, data: dict, source: str) -> int:
    """Evaluate one kind-qualifying record under the PR-gate checks (commit
    coverage, chain scope, 0 BLOCKING). Prints the verdict; returns the gate
    exit code. ``source`` names where the record came from (the findings file,
    or a ledger line) so the satisfied message stays attributable."""
    mode = data.get("mode")
    if mode == _CRITIC_MODE_CUMULATIVE:
        # CRT-7M2D — judge the record by COMMIT-COVERAGE, not mtime-recency.
        # The gate's real question is "has the bundle being PR'd had a clean
        # cumulative review?" — a fact about COMMITS, not timestamps (full
        # rationale in the docstring; rule mechanics in _record_covers_head).
        status, detail = _record_covers_head(project_dir, data.get("commit_reviewed"))
        if status == "no-anchor":
            print(
                "no-commit-reviewed: the cumulative record lacks a "
                "commit_reviewed anchor, so the gate cannot verify it covers "
                "HEAD. Re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        if status == "unresolved":
            print(
                f"unresolved-commit: {detail}. Re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        if status == "error":
            print(
                f"coverage-check-failed: {detail}. "
                "Re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        if status == "stale":
            print(
                f"stale: code changed since the cumulative review ({detail}). "
                "Fix, commit, then run /prawduct:critic verify-resolutions — the "
                "chain record extends this cumulative to HEAD (CRT-4J8W); a full "
                "cumulative re-run is only needed if this record is gone or the "
                "delta outgrows the verify scope. (Doc-only — all .md — changes "
                "since the review never require a re-run.)",
                file=sys.stderr,
            )
            return 1
        satisfied_msg = (
            f"satisfied: cumulative-Critic record covers HEAD and is clean "
            f"({source})"
        )
    elif mode == _CRITIC_MODE_VERIFY_RESOLUTIONS:
        # CRT-4J8W — the chain path. A verify-resolutions record certifies
        # the bundle ONLY by extending a cumulative: anchor present, record
        # at HEAD, and the anchor..HEAD delta inside the record's reviewed
        # scope. Every check fails closed.
        ext = data.get("extends_cumulative")
        anchor = ext.get("commit_reviewed") if isinstance(ext, dict) else None
        if not isinstance(anchor, str) or not anchor.strip():
            print(
                "chain-missing-anchor: this verify-resolutions record has no "
                "extends_cumulative anchor — it re-verifies prior findings but "
                "cannot certify the bundle. Chain sequence: land all non-.md "
                "fixes, run /prawduct:critic cumulative once; for fixes AFTER "
                "the cumulative — fix, commit, then /prawduct:critic "
                "verify-resolutions (the Critic embeds the anchor when the "
                "prior record is that cumulative). If the cumulative record is "
                "gone, re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        status, detail = _record_covers_head(project_dir, data.get("commit_reviewed"))
        if status in ("no-anchor", "unresolved", "error"):
            print(
                f"chain-coverage-failed: {detail}. Re-run /prawduct:critic "
                "verify-resolutions (or cumulative).",
                file=sys.stderr,
            )
            return 1
        if status == "stale":
            print(
                f"chain-stale: code changed since the verify-resolutions record "
                f"({detail}). Commit fixes BEFORE running verify-resolutions — a "
                "verify record anchored pre-commit can never cover HEAD. Fix, "
                "commit, then re-run /prawduct:critic verify-resolutions.",
                file=sys.stderr,
            )
            return 1
        try:
            anchor_proc = subprocess.run(
                ["git", "rev-parse", "--verify", f"{anchor}^{{commit}}"],
                cwd=str(project_dir), capture_output=True, text=True, timeout=30,
            )
            chain_diff_proc = subprocess.run(
                ["git", "diff", "--name-only", f"{anchor}..HEAD"],
                cwd=str(project_dir), capture_output=True, text=True, timeout=30,
            )
        except Exception as exc:  # prawduct:allow prawduct/broad-except -- fail closed if git is unavailable
            print(
                f"chain-coverage-failed: could not evaluate the chain range "
                f"({exc!r}). Re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        if anchor_proc.returncode != 0:
            print(
                f"chain-unresolved-anchor: extends_cumulative anchor "
                f"({anchor[:12]}) does not resolve in this repo — the extended "
                "cumulative cannot be located (rebase/force-push?). Re-run "
                "/prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        if chain_diff_proc.returncode != 0:
            print(
                f"chain-coverage-failed: git diff {anchor[:12]}..HEAD failed: "
                f"{chain_diff_proc.stderr.strip()}. Re-run /prawduct:critic "
                "cumulative.",
                file=sys.stderr,
            )
            return 1
        files_reviewed = {
            f for f in data.get("files_reviewed", [])
            if isinstance(f, str) and f.strip()
        }
        changed = [
            ln.strip() for ln in chain_diff_proc.stdout.splitlines() if ln.strip()
        ]
        gap = sorted(
            f for f in changed
            if not f.endswith(".md")
            and not gitstate._is_metadata_path(f)
            and f not in files_reviewed
        )
        if gap:
            sample = ", ".join(gap[:3])
            more = f" (+{len(gap) - 3} more)" if len(gap) > 3 else ""
            print(
                f"chain-scope-gap: {len(gap)} file(s) changed since the extended "
                f"cumulative ({anchor[:12]}..HEAD) but are not in the verify "
                f"record's files_reviewed: {sample}{more}. The chain cannot vouch "
                "for unreviewed code — re-run /prawduct:critic cumulative.",
                file=sys.stderr,
            )
            return 1
        satisfied_msg = (
            f"satisfied: verify-resolutions chain extends cumulative "
            f"{anchor[:12]} and covers HEAD ({source})"
        )
    else:
        # Defensive only — callers pre-filter via _pr_gate_record_qualifies,
        # so this branch is unreachable today; kept so a future caller that
        # skips the filter fails closed with the canonical message.
        print(
            f"wrong-mode: findings mode is {mode!r}, expected cumulative "
            f"({_CRITIC_MODE_CUMULATIVE!r}) or a chained verify-resolutions "
            "record (CRT-4J8W). Sequence: land ALL non-.md fixes first, then "
            "run /prawduct:critic cumulative once; for fixes after the "
            "cumulative — fix, commit, then /prawduct:critic verify-resolutions "
            "(the chain record extends the cumulative to HEAD; no full re-run).",
            file=sys.stderr,
        )
        return 1

    findings = data.get("findings", [])
    blocking = [f for f in findings if isinstance(f, dict) and f.get("severity") == "blocking"]
    if blocking:
        first = blocking[0].get("summary", "<no summary>")
        print(
            f"blocking: the Critic record holds {len(blocking)} BLOCKING "
            f"finding(s). First: {first}. Resolve before opening a PR.",
            file=sys.stderr,
        )
        return 1

    print(satisfied_msg)
    return 0


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
