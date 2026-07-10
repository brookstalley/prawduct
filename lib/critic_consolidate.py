"""Deterministic Critic-review consolidation — the write path with no model in it.

Root cause this fixes (critic-persistence-redesign, Option A): Claude Code
v2.1.198 (2026-07-01) made ``Agent`` subagents background-by-default. The Critic's
``context: fork`` coordinator dispatches its reviewers and RETURNS before resuming,
so the old SKILL steps 7-8 (findings write, ledger anchor, ``critic-end``) never
run — the review is silently lost and surfaces later as a ``check-cumulative-critic``
deadlock. The fix decouples the *model judgment* (independent review) from the
*deterministic persistence*: reviewers write their own **partials**; this module
merges them into the canonical ``.critic-findings.json`` + ledger anchor as a pure
function of on-disk state. No model in the write path, so no background/fork-resume
behavior can skip it.

**On-disk contract** (all under ``.prawduct/.critic-partials/``, gitignored):

- ``manifest.json`` — written by the coordinator at dispatch time. The single
  source of truth for *what review is pending*: which roles must report
  (``roster``), against which commit (``commit_reviewed``), the resolved verbose
  ``mode`` + ``mode_chosen_by``, the reviewed file set (``files_reviewed``), and
  the ledger attribution (``scope`` / ``chunk`` / ``model`` / optional
  ``base_reviewed``). Its presence means "a review is in flight"; its absence
  means "nothing to consolidate."
- ``<role>.json`` — one partial per roster role, written by that reviewer
  subagent. Carries the reviewer's own findings and the commit it reviewed.

``files_reviewed`` lives on the **manifest**, not in the plan's original partial
list: the canonical findings record REQUIRES a non-empty ``files_reviewed``
(``gates.validate_critic_findings``) and the coordinator — which computed the
changed-file set to brief the reviewers — is the only party that knows it. A clean
review has zero findings, so it can't be reconstructed from findings alone.

**Consolidation is a pure function of on-disk state, idempotent, and fail-closed.**
It writes findings ONLY when every roster role has reported a schema-valid partial
AND every partial reviewed the manifest's commit AND that commit still covers HEAD.
Anything else is a no-op (incomplete → still waiting) or a hard error (malformed,
stale, or inconsistent → do not persist a partial review as complete). Success
removes the manifest + partials, so the next call is a clean no-op — this is what
makes the Chunk-04 per-reviewer ``SubagentStop`` trigger safe to fire N times:
the first N-1 fire while the roster is incomplete (no-op), the Nth (roster
complete) consolidates exactly once, and any straggler finds no manifest.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import critic_marker, gitstate, ledger
from .core import atomic_write_text

PARTIALS_DIRNAME = ".critic-partials"
MANIFEST_NAME = "manifest.json"

# Severity vocabulary + ranking (highest wins on dedup). The stop-hook and PR
# gate key on "blocking"; restricting the partial vocabulary here means a typo'd
# severity fails partial validation rather than silently downgrading a blocker.
_SEVERITY_RANK = {"blocking": 3, "warning": 2, "note": 1}


def partials_dir(prawduct_dir: Path) -> Path:
    return prawduct_dir / PARTIALS_DIRNAME


def manifest_path(prawduct_dir: Path) -> Path:
    return partials_dir(prawduct_dir) / MANIFEST_NAME


def partial_path(prawduct_dir: Path, role: str) -> Path:
    return partials_dir(prawduct_dir) / f"{role}.json"


# ---------------------------------------------------------------------------
# Schema validation — every validator returns (ok, reason) so the caller can
# name the specific defect. Fail-closed: a malformed record is NEVER treated as
# a complete review.
# ---------------------------------------------------------------------------


def _nonempty_str(val) -> bool:
    return isinstance(val, str) and bool(val.strip())


def _nonempty_str_list(val) -> bool:
    return isinstance(val, list) and bool(val) and all(_nonempty_str(v) for v in val)


def validate_partial(data) -> tuple[bool, str]:
    """Validate a single reviewer partial.

    Schema: ``{role, goals, commit_reviewed, model?, duration_seconds?,
    findings:[{name, goal, severity, recommendation, files?}], summary}``.
    ``model``/``duration_seconds`` are nullable telemetry; everything else is
    load-bearing. ``severity`` must be one of the known vocabulary so a typo
    can't silently persist as a non-blocking finding.
    """
    if not isinstance(data, dict):
        return False, "partial is not a JSON object"
    if not _nonempty_str(data.get("role")):
        return False, "missing/empty 'role'"
    goals = data.get("goals")
    if not (_nonempty_str(goals) or _nonempty_str_list(goals)):
        return False, "missing 'goals' (non-empty string or list)"
    if not _nonempty_str(data.get("commit_reviewed")):
        return False, "missing/empty 'commit_reviewed'"
    if not _nonempty_str(data.get("summary")):
        return False, "missing/empty 'summary'"
    model = data.get("model")
    if model is not None and not _nonempty_str(model):
        return False, "'model' must be a non-empty string or null"
    dur = data.get("duration_seconds")
    if dur is not None and (not isinstance(dur, (int, float)) or isinstance(dur, bool)):
        return False, "'duration_seconds' must be a number or null"
    findings = data.get("findings")
    if not isinstance(findings, list):
        return False, "'findings' must be a list"
    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            return False, f"finding[{idx}] is not an object"
        for field in ("name", "goal", "severity", "recommendation"):
            if not _nonempty_str(f.get(field)):
                return False, f"finding[{idx}] missing/empty '{field}'"
        if f["severity"] not in _SEVERITY_RANK:
            return False, (
                f"finding[{idx}] severity {f['severity']!r} not in "
                f"{sorted(_SEVERITY_RANK)}"
            )
        if "files" in f and not _nonempty_str_list(f["files"]):
            return False, f"finding[{idx}] 'files' must be a non-empty list of strings"
    return True, ""


def validate_manifest(data) -> tuple[bool, str]:
    """Validate the dispatch manifest.

    Schema: ``{mode, mode_chosen_by, roster, commit_reviewed, files_reviewed,
    scope?, chunk?, model?, base_reviewed?}``. ``mode`` must be a verbose
    persistence string (the same set ``gates.validate_critic_findings``
    accepts) — a bare token here would produce a findings file the gates reject.
    """
    from . import gates  # noqa: PLC0415 — lazy; gates is heavy and one-way

    if not isinstance(data, dict):
        return False, "manifest is not a JSON object"
    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in gates._CRITIC_MODE_VALUES:
        return False, (
            f"'mode' must be a verbose persistence string "
            f"({sorted(gates._CRITIC_MODE_VALUES)}), got {mode!r}"
        )
    if not _nonempty_str(data.get("mode_chosen_by")):
        return False, "missing/empty 'mode_chosen_by'"
    if not _nonempty_str_list(data.get("roster")):
        return False, "missing 'roster' (non-empty list of role names)"
    if not _nonempty_str(data.get("commit_reviewed")):
        return False, "missing/empty 'commit_reviewed'"
    if not _nonempty_str_list(data.get("files_reviewed")):
        return False, "missing 'files_reviewed' (non-empty list)"
    for opt in ("scope", "chunk", "model", "base_reviewed"):
        val = data.get(opt)
        if val is not None and not _nonempty_str(val):
            return False, f"'{opt}' must be a non-empty string or null"
    return True, ""


# ---------------------------------------------------------------------------
# Pending-state inspection — read-only, no git. Chunk 05's session-end backstop
# uses this to decide self-heal vs. block-naming-the-missing-reviewer without
# re-implementing the read.
# ---------------------------------------------------------------------------


def pending_state(prawduct_dir: Path) -> tuple[str, list[str]]:
    """Classify the on-disk consolidation state, purely by file presence.

    Returns ``(state, missing_roles)``:
      - ``("none", [])`` — no manifest: nothing pending.
      - ``("unreadable", [])`` — manifest present but not valid JSON/schema.
      - ``("incomplete", [roles])`` — manifest valid, some roster partials absent.
      - ``("complete", [])`` — manifest valid, every roster partial present on disk.

    "complete" means every partial FILE exists — it does NOT validate partial
    contents or HEAD-coverage (that is :func:`consolidate`'s job). This is the
    cheap liveness read; the full fail-closed check happens at consolidation.
    """
    mpath = manifest_path(prawduct_dir)
    if not mpath.is_file():
        return "none", []
    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, json.JSONDecodeError):
        return "unreadable", []
    ok, _reason = validate_manifest(manifest)
    if not ok:
        return "unreadable", []
    missing = [
        role
        for role in manifest["roster"]
        if not partial_path(prawduct_dir, role).is_file()
    ]
    if missing:
        return "incomplete", missing
    return "complete", []


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_findings(partials: list[dict]) -> list[dict]:
    """Union every reviewer's findings into the canonical record shape,
    de-duplicated by ``(goal, name, files)`` keeping the highest severity.

    Each partial finding ``{name, goal, severity, recommendation, files?}`` maps
    to the canonical ``{goal, severity, summary, recommendation, files?}`` — the
    reviewer's ``name`` becomes the record ``summary`` (the required field
    ``gates.validate_critic_findings`` checks), ``recommendation`` is retained.
    Reviewers cover disjoint goal sets, so cross-reviewer collisions are rare;
    dedup is a safety net that also protects against a re-dispatched reviewer.
    """
    merged: dict[tuple, dict] = {}
    for partial in partials:
        for f in partial.get("findings", []):
            files = f.get("files")
            key = (f["goal"], f["name"], tuple(files) if files else ())
            entry = {
                "goal": f["goal"],
                "severity": f["severity"],
                "summary": f["name"],
                "recommendation": f["recommendation"],
            }
            if files:
                entry["files"] = list(files)
            existing = merged.get(key)
            if existing is None or (
                _SEVERITY_RANK[f["severity"]] > _SEVERITY_RANK[existing["severity"]]
            ):
                merged[key] = entry
    return list(merged.values())


def _severity_counts(findings: list[dict]) -> tuple[int, int, int]:
    blocking = sum(1 for f in findings if f["severity"] == "blocking")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    note = sum(1 for f in findings if f["severity"] == "note")
    return blocking, warning, note


def build_record(manifest: dict, partials: list[dict]) -> dict:
    """Assemble the canonical ``.critic-findings.json`` record from the manifest
    envelope and the merged partials. Schema-valid by construction against
    ``gates.validate_critic_findings``."""
    findings = merge_findings(partials)
    blocking, warning, note = _severity_counts(findings)
    if blocking:
        verdict = "Blocking findings must be resolved before proceeding."
    else:
        verdict = "Changes ready to proceed."
    summary = (
        f"{blocking} blocking, {warning} warning, {note} note "
        f"across {len(partials)} reviewer(s). {verdict}"
    )
    # Parallel reviewers → wall-clock is the slowest, not the sum. None when no
    # reviewer reported a duration.
    durations = [
        p["duration_seconds"]
        for p in partials
        if isinstance(p.get("duration_seconds"), (int, float))
        and not isinstance(p.get("duration_seconds"), bool)
    ]
    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": max(durations) if durations else None,
        "mode": manifest["mode"],
        "mode_chosen_by": manifest["mode_chosen_by"],
        "model": manifest.get("model"),
        "commit_reviewed": manifest["commit_reviewed"],
        "base_reviewed": manifest.get("base_reviewed"),
        "files_reviewed": list(manifest["files_reviewed"]),
        "findings": findings,
        "summary": summary,
    }
    return record


# ---------------------------------------------------------------------------
# Consolidate — the command body
# ---------------------------------------------------------------------------


def consolidate(project_dir: Path) -> int:
    """Merge complete reviewer partials into the canonical record. Idempotent.

    Exit codes:
      - ``0`` + ``no-op:`` — nothing to do (no manifest, or roster incomplete).
        The common in-flight case as reviewers finish one by one.
      - ``0`` + ``consolidated:`` — findings written, ledger anchored, marker
        cleared, partials removed.
      - ``1`` — fail-closed: malformed manifest/partial, a partial reviewed a
        different commit than dispatched, HEAD moved since dispatch (stale →
        re-review), or the ledger append failed. Nothing partial is persisted
        as complete; the manifest is left in place so the fix can retry.
    """
    from . import gates  # noqa: PLC0415 — lazy; gates is heavy

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    mpath = manifest_path(prawduct_dir)
    if not mpath.is_file():
        print("no-op: no pending review manifest — nothing to consolidate.")
        return 0

    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"critic-consolidate: manifest unreadable ({exc})", file=sys.stderr)
        return 1
    ok, reason = validate_manifest(manifest)
    if not ok:
        print(f"critic-consolidate: invalid manifest — {reason}", file=sys.stderr)
        return 1

    roster = manifest["roster"]
    manifest_commit = manifest["commit_reviewed"]

    # Collect partials; missing roles → incomplete no-op (still in flight).
    partials: list[dict] = []
    missing: list[str] = []
    for role in roster:
        ppath = partial_path(prawduct_dir, role)
        if not ppath.is_file():
            missing.append(role)
            continue
        try:
            data = json.loads(ppath.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"critic-consolidate: partial {role!r} unreadable ({exc}) — "
                "fail-closed, not persisting a partial review as complete.",
                file=sys.stderr,
            )
            return 1
        valid, preason = validate_partial(data)
        if not valid:
            print(
                f"critic-consolidate: partial {role!r} invalid — {preason}. "
                "Fail-closed; not consolidating.",
                file=sys.stderr,
            )
            return 1
        if data["role"] != role:
            print(
                f"critic-consolidate: partial for {role!r} declares role "
                f"{data['role']!r} — roster mismatch, fail-closed.",
                file=sys.stderr,
            )
            return 1
        if data["commit_reviewed"] != manifest_commit:
            print(
                f"critic-consolidate: reviewer {role!r} reviewed "
                f"{data['commit_reviewed'][:12]} but dispatch was at "
                f"{manifest_commit[:12]} — inconsistent, re-review.",
                file=sys.stderr,
            )
            return 1
        partials.append(data)

    if missing:
        print(
            f"no-op: review incomplete — waiting on {', '.join(missing)} "
            f"({len(partials)}/{len(roster)} partials present)."
        )
        return 0

    # Every roster role reported at the manifest commit. Does that commit still
    # cover HEAD? (A commit made after dispatch — but before consolidation —
    # would make the review stale.)
    status, detail = gates._record_covers_head(project_dir, manifest_commit)
    if status != "covered":
        print(
            f"critic-consolidate: dispatch commit {manifest_commit[:12]} no "
            f"longer covers HEAD ({status}: {detail}) — re-review at HEAD.",
            file=sys.stderr,
        )
        return 1

    # All preconditions met — write the canonical record.
    record = build_record(manifest, partials)
    findings_path = prawduct_dir / ".critic-findings.json"
    atomic_write_text(findings_path, json.dumps(record, indent=2))

    # Belt-and-suspenders: the record we just built must satisfy the schema the
    # gates trust. If it doesn't, that is a bug in build_record — fail loudly
    # rather than anchor an invalid record in the ledger.
    if not gates.validate_critic_findings(findings_path):
        print(
            "critic-consolidate: internal error — assembled record failed "
            "schema validation; not anchoring in the ledger.",
            file=sys.stderr,
        )
        return 1

    # Anchor in the governance ledger (the record check-cumulative-critic reads).
    argv = ["--event", "review.critic"]
    if manifest.get("scope"):
        argv += ["--scope", manifest["scope"]]
    if manifest.get("chunk"):
        argv += ["--chunk", manifest["chunk"]]
    if manifest.get("model"):
        argv += ["--model", manifest["model"]]
    rc = ledger.ledger_append(project_dir, argv)
    if rc != 0:
        print(
            "critic-consolidate: ledger append failed — leaving the manifest in "
            "place so consolidation can retry.",
            file=sys.stderr,
        )
        return 1

    # Persisted + anchored. Clear the critic-active marker and remove the
    # partials so a repeat call (or a straggler SubagentStop) is a clean no-op.
    critic_marker.clear_marker(prawduct_dir)
    remove_partials(prawduct_dir)

    blocking, warning, note = _severity_counts(record["findings"])
    print(
        f"consolidated: {blocking} blocking, {warning} warning, {note} note "
        f"from {len(partials)} reviewer(s) at {manifest_commit[:12]} → "
        f"{findings_path.name} + ledger anchor; marker cleared."
    )
    return 0


def remove_partials(prawduct_dir: Path) -> None:
    """Remove the manifest + every partial + the partials directory. Best-effort
    and idempotent — a missing file is fine (the point is that nothing pending
    remains). Public: ``critic-begin`` also calls this so every review starts
    from a clean partials dir — consolidate removes partials only on success,
    so a waived or stale-failed review leaves them behind, and a leftover
    partial at the same commit as a fresh dispatch would otherwise merge as if
    the new reviewer had written it."""
    pdir = partials_dir(prawduct_dir)
    if not pdir.is_dir():
        return
    for child in pdir.iterdir():
        try:
            child.unlink()
        except OSError:
            pass
    try:
        pdir.rmdir()
    except OSError:
        pass
