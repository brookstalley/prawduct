"""Deterministic Critic data plane — dispatch manifest + consolidation (D8).

Both ends of the ``.prawduct/.critic-partials/`` contract live here: the
begin side (``begin_review`` — code derives the roster from mode, captures
the reviewed trees, and writes the dispatch manifest) and the consolidate
side (``consolidate`` — merges reviewer partials against that manifest,
appends the review fact to the evidence store, and regenerates the derived
findings cache). Models hand judgment to this data plane as *content* (the
partials), never as file-format authorship.

Two defect families die here rather than being patched:

- **Model-authored persistence** (CRT-W2NV, CRT-J4PM(1)): the v2 coordinator
  hand-wrote ``manifest.json`` (omitting keys) and single-pass reviews
  hand-wrote ``.critic-findings.json`` itself. In v3 ``critic-begin`` writes
  the manifest and ``consolidate`` writes everything downstream — the only
  model-written input is the per-role partial (the judgment payload),
  validated fail-closed.
- **Fork-resume loss** (critic-persistence-redesign, Option A): Claude Code
  v2.1.198 made ``Agent`` subagents background-by-default, so a coordinator
  that persisted findings after dispatch silently never did. Persistence is
  decoupled: reviewers write partials; consolidation is a pure function of
  on-disk state, idempotent, triggered per-reviewer by ``SubagentStop`` and
  floored by the session-end backstop.

**On-disk contract** (all under ``.prawduct/.critic-partials/``, gitignored):

- ``manifest.json`` — written by ``critic-begin`` (code, never a model). The
  single source of truth for the pending review: the fixed review ``id``
  (CRT-4B7X idempotency key), verbose ``mode`` + ``mode_chosen_by``, the
  code-derived ``roster`` + ``roster_chosen_by``, the reviewed interval
  (``base_commit``/``base_tree`` → ``head_tree``/``head_commit``, D3 tree
  keying via ``evidence.capture_tree``), the ``files_changed`` snapshot
  (``git diff`` between exactly those trees, so the recorded set and the
  D6 edge-validity check agree by construction), ``files_reviewed``, and
  telemetry/attribution (``tier``, ``scope``, ``chunk``).
- ``<role>.json`` — one partial per roster role, written by that reviewer.
  Carries the reviewer's findings, and — for a verify-resolutions dispatch
  only — its ``resolutions`` judgments (D5).

**Consolidation is idempotent and fail-closed.** It persists ONLY when every
roster role has reported a schema-valid partial at the manifest's dispatch
commit. Anything else is a no-op naming the missing roles (still in flight)
or a hard error (malformed / inconsistent / off-protocol). Success appends
the review fact (skipped when the id already exists — the CRT-4B7X race dies
here), appends any resolution facts, regenerates ``.critic-findings.json``
as a derived cache carrying its source ``fact_id`` (D7), anchors the ledger,
clears the critic-active marker, and removes the partials so every repeat
call is a clean no-op.

**No staleness refusal (v3 posture change).** The v2 consolidate refused to
persist when the dispatch commit no longer covered HEAD. A review fact is a
true statement about the tree the reviewers saw — it is appended regardless;
whether that tree still suffices is the gate-time coverage composition's
question (design D6), not the writer's. Refusing was the "evidence dies on
staleness" defect class this plan deletes.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import critic_marker, evidence, gitstate, ledger
from .core import atomic_write_text

PARTIALS_DIRNAME = ".critic-partials"
MANIFEST_NAME = "manifest.json"

# Severity vocabulary + ranking (highest wins on dedup). The stop-hook and PR
# gate key on "blocking"; restricting the partial vocabulary here means a typo'd
# severity fails partial validation rather than silently downgrading a blocker.
_SEVERITY_RANK = {"blocking": 3, "warning": 2, "note": 1}

# Caller-side short token → persisted verbose string (the two-form rule;
# values match gates._CRITIC_MODE_VALUES — pinned by test).
MODE_TOKEN_TO_VERBOSE = {
    "chunk": "chunk (lighter pass, not ready for push)",
    "final": "final (full review, ready for push)",
    "cumulative": "cumulative (bundle review, ready for merge)",
    "verify-resolutions": "verify-resolutions (delta review, prior findings only)",
}
_VERBOSE_VERIFY_RESOLUTIONS = MODE_TOKEN_TO_VERBOSE["verify-resolutions"]

# Roster config (D8): protocol roles per execution shape. chunk and
# verify-resolutions are always single-pass; final/cumulative go coordinator
# at the building.md size heuristic ("5+ files = medium").
SINGLE_PASS_ROSTER = ("reviewer",)
COORDINATOR_ROSTER = ("correctness", "design", "sustainability")
COORDINATOR_FILE_THRESHOLD = 5

_RESOLUTION_DISPOSITIONS = frozenset({"fixed", "waived"})

# verify-resolutions scope-widening demotion threshold (unchanged from v2's
# canonical helper): a delta this much larger than the prior surface means a
# partial re-review would mislead — fall back to a full review.
def _scope_widened(delta_count: int, prior_count: int) -> bool:
    return delta_count > 2 * prior_count + 5


def partials_dir(prawduct_dir: Path) -> Path:
    return prawduct_dir / PARTIALS_DIRNAME


def manifest_path(prawduct_dir: Path) -> Path:
    return partials_dir(prawduct_dir) / MANIFEST_NAME


def partial_path(prawduct_dir: Path, role: str) -> Path:
    return partials_dir(prawduct_dir) / f"{role}.json"


# ---------------------------------------------------------------------------
# Dispatch (critic-begin) — code writes the manifest; the model never does.
# ---------------------------------------------------------------------------


def _derive_roster(mode_token: str, files_changed: list[str]) -> tuple[list[str], str]:
    """The roster this dispatch requires, plus the rationale (Q7 debugging)."""
    if mode_token in ("chunk", "verify-resolutions"):
        return list(SINGLE_PASS_ROSTER), f"mode={mode_token} is always single-pass"
    n = len(files_changed)
    if n >= COORDINATOR_FILE_THRESHOLD:
        return list(COORDINATOR_ROSTER), (
            f"mode={mode_token}, {n} files changed >= "
            f"{COORDINATOR_FILE_THRESHOLD} — coordinator"
        )
    return list(SINGLE_PASS_ROSTER), (
        f"mode={mode_token}, {n} files changed < "
        f"{COORDINATOR_FILE_THRESHOLD} — single-pass"
    )


def _prior_review_fact(project_dir: Path, prawduct_dir: Path) -> tuple[dict | None, str]:
    """The review fact a verify-resolutions pass anchors to, located via the
    derived cache's ``fact_id`` pointer (D7 — this is what the pointer is
    for). Returns ``(fact, "")`` or ``(None, reason)`` — the caller fails
    loud and the skill demotes to chunk/final."""
    cache = prawduct_dir / ".critic-findings.json"
    try:
        data = json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"no readable prior findings cache ({exc})"
    fact_id = data.get("fact_id") if isinstance(data, dict) else None
    if not isinstance(fact_id, str) or not fact_id.strip():
        return None, (
            "prior findings cache carries no fact_id — it predates the "
            "evidence store (a fresh review re-establishes coverage)"
        )
    store = evidence.read_facts(project_dir)
    for fact in evidence.facts_of_kind(store, "review"):
        if fact.get("id") == fact_id:
            return fact, ""
    return None, f"prior review fact {fact_id!r} not found in the evidence store"


def begin_review(
    project_dir: Path,
    mode_token: str,
    chosen_by: str | None = None,
    chunk: str | None = None,
    scope: str | None = None,
    tier: str | None = None,
) -> dict:
    """Derive and write the dispatch manifest for one review. All code.

    Returns ``{"status": "ok", "id", "roster", "path", "notes": [...],
    "cleared_leftovers": bool, "manifest": {...}}`` or ``{"status": "error",
    "reason", "kind"?}`` where ``kind == "scope-widened"`` tells the CLI to
    exit 2 (the skill's fall-back-to-final signal).

    Per-mode interval (design D8, chunk-03 refinements):

    - ``chunk``/``final`` — base = ``HEAD`` (the uncommitted diff), head =
      the captured working tree (D3 temp-index capture; non-mutating).
    - ``cumulative`` — base = merge-base(resolve-base, HEAD), head = ``HEAD``
      (the committed bundle; a dirty working tree is noted, not reviewed).
    - ``verify-resolutions`` — base = the prior review FACT's ``head_tree``,
      head = the captured working tree. Tree keying makes a dirty-tree
      verify sound (the v2 "commit first, then verify" rule dissolves).

    ``files_changed`` is uniformly ``git diff --name-only <base_tree>
    <head_tree>``, so the recorded snapshot and the D6 edge-validity check
    agree by construction.
    """
    verbose = MODE_TOKEN_TO_VERBOSE.get(mode_token)
    if verbose is None:
        return {
            "status": "error",
            "reason": (
                f"unknown mode token {mode_token!r} — expected one of "
                f"{sorted(MODE_TOKEN_TO_VERBOSE)}"
            ),
        }
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)

    capture = evidence.capture_tree(project_dir)
    if capture.get("status") != "ok":
        return {
            "status": "error",
            "reason": f"tree capture failed: {capture.get('reason', 'unknown')}",
        }
    dispatch_commit = capture.get("head_commit")
    if not dispatch_commit:
        return {
            "status": "error",
            "reason": "no HEAD commit — nothing to anchor a review to "
            "(commit an initial state first)",
        }

    notes: list[str] = []
    base_reviewed = None
    files_reviewed: list[str] | None = None

    if mode_token in ("chunk", "final"):
        base_commit = dispatch_commit
        base_tree = capture["head_tree"]
        head_tree = capture["tree"]
        head_commit = dispatch_commit if capture["clean"] else None
    elif mode_token == "cumulative":
        from . import coverage  # noqa: PLC0415 — lazy; coverage pulls git helpers

        resolved = coverage.resolve_merge_base_tree(project_dir)
        if resolved["status"] != "ok":
            return {"status": "error", "reason": resolved["reason"]}
        base_commit = resolved["merge_base"]
        base_tree = resolved["tree"]
        head_commit = dispatch_commit
        head_tree = capture["head_tree"]  # the committed state, not the dirty tree
        base_reviewed = base_commit
        if not capture["clean"]:
            notes.append(
                "working tree dirty at cumulative dispatch — uncommitted "
                "changes are NOT in the reviewed scope"
            )
    else:  # verify-resolutions
        prior, reason = _prior_review_fact(project_dir, prawduct_dir)
        if prior is None:
            return {"status": "error", "reason": f"no prior review to verify: {reason}"}
        prior_body = prior.get("body") or {}
        base_tree = prior_body.get("head_tree")
        if not isinstance(base_tree, str) or not base_tree:
            return {
                "status": "error",
                "reason": f"prior review fact {prior.get('id')!r} records no head_tree",
            }
        base_commit = prior_body.get("head_commit")

        # Intent-aware head anchor (CRT-7H2W). verify-resolutions serves two gate
        # targets that DIVERGE once the working tree is dirty: the PR gate
        # composes to COMMITTED HEAD, the Stop-hook gate to the WORKING tree. A
        # single working-tree anchor left the PR gate ``uncovered`` whenever a
        # committed fix carried along a stray judgeable uncommitted file. Read
        # intent from git: if the builder COMMITTED work since the prior review
        # (the post-cumulative-fix / PR-gate case), anchor the review edge at
        # committed HEAD so it composes to the PR gate's target and note-and-
        # exclude any WIP, exactly like the cumulative branch. Otherwise
        # (fix-in-progress in a dirty tree) keep the working-tree anchor so the
        # Stop-hook gate composes and the PR gate legitimately stays pending until
        # the fix is committed — preserving CRT-4J8W dirty-tree verify.
        from . import critic_mode  # noqa: PLC0415 — lazy; avoids an import cycle
        prior_commit = prior_body.get("head_commit") or prior_body.get("dispatch_commit")
        committed_since = (
            critic_mode._committed_files_since(project_dir, prior_commit)
            if prior_commit else set()
        )
        if committed_since:
            head_tree = capture["head_tree"]  # committed HEAD — the PR-gate target
            head_commit = dispatch_commit
            if not capture["clean"]:
                notes.append(
                    "working tree dirty at verify-resolutions dispatch — anchored "
                    "to committed HEAD (a committed delta exists since the prior "
                    "review); uncommitted changes are NOT in the reviewed scope"
                )
        else:
            head_tree = capture["tree"]  # working tree — the Stop-hook target
            head_commit = dispatch_commit if capture["clean"] else None
            if not capture["clean"]:
                from . import coverage_algebra  # noqa: PLC0415 — lazy
                wip = (
                    evidence.tree_diff(project_dir, capture["head_tree"], capture["tree"])
                    or []
                )
                if coverage_algebra.judgeable_files(wip):
                    notes.append(
                        "working tree dirty with judgeable uncommitted files and no "
                        "committed delta since the prior review — this fact vouches "
                        "for the WORKING tree, but the cumulative/PR gate targets "
                        "committed HEAD, so it will read `uncovered` until you commit "
                        "(or stash) the fix and re-run verify-resolutions"
                    )
        delta = evidence.tree_diff(project_dir, base_tree, head_tree)
        if delta is None:
            return {
                "status": "error",
                "reason": (
                    f"cannot diff prior reviewed tree {base_tree[:12]} against "
                    "the current tree (rewritten history?) — anchor unreliable"
                ),
            }
        prior_files = [
            f for f in (prior_body.get("files_reviewed") or []) if isinstance(f, str)
        ]
        if _scope_widened(len(delta), len(prior_files)):
            return {
                "status": "error",
                "kind": "scope-widened",
                "reason": (
                    f"scope-widened: {len(delta)} files changed since the prior "
                    f"review of {len(prior_files)} — a partial re-review would "
                    "mislead; run a full review"
                ),
            }
        prior_counts = prior_body.get("counts") or {}
        actionable = (prior_counts.get("blocking") or 0) + (
            prior_counts.get("warning") or 0
        )
        if not delta and not actionable:
            return {
                "status": "error",
                "reason": (
                    "nothing to verify: the prior review has no blocking/warning "
                    "findings and nothing changed since"
                ),
            }
        files_reviewed = list(prior_files)
        for f in delta:
            if f not in files_reviewed:
                files_reviewed.append(f)

    files_changed = evidence.tree_diff(project_dir, base_tree, head_tree)
    if files_changed is None:
        return {
            "status": "error",
            "reason": f"cannot diff {base_tree[:12]}..{head_tree[:12]}",
        }
    if not files_changed and mode_token != "verify-resolutions":
        return {
            "status": "error",
            "reason": (
                f"empty diff for mode {mode_token!r} — nothing to review "
                "between the base and the current state (already committed? "
                "a committed bundle is cumulative's scope)"
            ),
        }
    if files_reviewed is None:
        files_reviewed = list(files_changed)

    roster, roster_chosen_by = _derive_roster(mode_token, files_changed)
    review_id = "rev-{}-{}".format(
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8]
    )

    manifest = {
        "id": review_id,
        "mode": verbose,
        "mode_chosen_by": (chosen_by or "").strip() or "not-recorded",
        "roster": roster,
        "roster_chosen_by": roster_chosen_by,
        "commit_reviewed": dispatch_commit,
        "base_commit": base_commit,
        "base_tree": base_tree,
        "head_tree": head_tree,
        "head_commit": head_commit,
        "files_changed": files_changed,
        "files_reviewed": files_reviewed,
        "tier": tier,
        "scope": scope,
        "chunk": chunk,
        "base_reviewed": base_reviewed,
    }
    ok, reason = validate_manifest(manifest)
    if not ok:
        # A manifest this function derived failing its own validator is a bug
        # here — fail loudly rather than dispatch a review that can never
        # consolidate.
        return {"status": "error", "reason": f"internal error — derived manifest invalid: {reason}"}

    cleared = False
    pdir = partials_dir(prawduct_dir)
    if pdir.is_dir():
        remove_partials(prawduct_dir)
        cleared = True
    pdir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path(prawduct_dir), json.dumps(manifest, indent=2))

    return {
        "status": "ok",
        "id": review_id,
        "roster": roster,
        "path": str(manifest_path(prawduct_dir)),
        "notes": notes,
        "cleared_leftovers": cleared,
        "manifest": manifest,
    }


# ---------------------------------------------------------------------------
# Schema validation — every validator returns (ok, reason) so the caller can
# name the specific defect. Fail-closed: a malformed record is NEVER treated as
# a complete review.
# ---------------------------------------------------------------------------


def _nonempty_str(val) -> bool:
    return isinstance(val, str) and bool(val.strip())


def _nonempty_str_list(val) -> bool:
    return isinstance(val, list) and bool(val) and all(_nonempty_str(v) for v in val)


def _str_list(val) -> bool:
    """A list — possibly empty — of non-empty strings."""
    return isinstance(val, list) and all(_nonempty_str(v) for v in val)


def validate_partial(data) -> tuple[bool, str]:
    """Validate a single reviewer partial.

    Schema: ``{role, goals, commit_reviewed, model?, duration_seconds?,
    findings:[{name, goal, severity, recommendation, files?}],
    resolutions?:[{review_id, fid, disposition, rationale?}], summary}``.
    ``model``/``duration_seconds`` are nullable telemetry; everything else is
    load-bearing. ``severity`` must be one of the known vocabulary so a typo
    can't silently persist as a non-blocking finding. ``resolutions`` is the
    verify-resolutions judgment payload (D5): ``disposition`` is ``fixed`` or
    ``waived``, and ``waived`` REQUIRES a non-empty ``rationale`` (R7 — a
    waiver carries its justification).
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
        # ``files`` is optional attribution, normalized away downstream: a
        # blank/non-string element is dropped in ``merge_findings`` and an
        # all-blank list collapses to no ``files`` at all — exactly like ``[]``
        # or an omitted key. Reject only a value that is not a list; a single
        # malformed element must never fail-close the WHOLE consolidation over
        # optional attribution (a reviewer's ``files:[""]`` on a file-less
        # META-finding otherwise bricked every review).
        if "files" in f and not isinstance(f["files"], list):
            return False, f"finding[{idx}] 'files' must be a list"
    resolutions = data.get("resolutions")
    if resolutions is not None:
        if not isinstance(resolutions, list):
            return False, "'resolutions' must be a list"
        for idx, r in enumerate(resolutions):
            if not isinstance(r, dict):
                return False, f"resolution[{idx}] is not an object"
            for field in ("review_id", "fid"):
                if not _nonempty_str(r.get(field)):
                    return False, f"resolution[{idx}] missing/empty '{field}'"
            if r.get("disposition") not in _RESOLUTION_DISPOSITIONS:
                return False, (
                    f"resolution[{idx}] disposition {r.get('disposition')!r} "
                    f"not in {sorted(_RESOLUTION_DISPOSITIONS)}"
                )
            rationale = r.get("rationale")
            if rationale is not None and not _nonempty_str(rationale):
                return False, f"resolution[{idx}] 'rationale' must be a non-empty string or null"
            if r["disposition"] == "waived" and not _nonempty_str(rationale):
                return False, (
                    f"resolution[{idx}] disposition 'waived' requires a "
                    "non-empty 'rationale' (R7)"
                )
    return True, ""


def validate_manifest(data) -> tuple[bool, str]:
    """Validate the dispatch manifest (v3 shape — written by ``begin_review``
    only).

    Required: ``id``, verbose ``mode``, ``mode_chosen_by``, ``roster``,
    ``roster_chosen_by``, ``commit_reviewed``, ``base_tree``, ``head_tree``,
    non-empty ``files_reviewed``, ``files_changed`` (a list, possibly empty —
    a same-tree verify-resolutions pass legitimately changes nothing).
    Nullable: ``base_commit``/``head_commit`` (a prior review of a dirty tree
    has no commit), ``tier``/``scope``/``chunk``/``model``/``base_reviewed``.

    The v2 (model-written) manifest shape carries none of the v3 interval
    fields, so it fails here loudly — a stale cached skill hand-authoring a
    manifest can no longer produce something consolidation trusts (CRT-W2NV
    regression pin).
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
    for req in ("id", "mode_chosen_by", "roster_chosen_by", "commit_reviewed",
                "base_tree", "head_tree"):
        if not _nonempty_str(data.get(req)):
            return False, f"missing/empty '{req}'"
    if not _nonempty_str_list(data.get("roster")):
        return False, "missing 'roster' (non-empty list of role names)"
    if not _nonempty_str_list(data.get("files_reviewed")):
        return False, "missing 'files_reviewed' (non-empty list)"
    if not _str_list(data.get("files_changed")):
        return False, "'files_changed' must be a list of non-empty strings"
    for opt in ("base_commit", "head_commit", "tier", "scope", "chunk", "model",
                "base_reviewed"):
        val = data.get(opt)
        if val is not None and not _nonempty_str(val):
            return False, f"'{opt}' must be a non-empty string or null"
    return True, ""


# ---------------------------------------------------------------------------
# Pending-state inspection — read-only, no git. The session-end backstop
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
    contents (that is :func:`consolidate`'s job). This is the cheap liveness
    read; the full fail-closed check happens at consolidation.
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
    """Union every reviewer's findings into the fact-body shape,
    de-duplicated by ``(goal, name, files)`` keeping the highest severity,
    with sequential ``fid``s assigned in merge order (deterministic: roster
    order × each partial's findings order).

    Each partial finding ``{name, goal, severity, recommendation, files?}``
    maps to ``{fid, goal, severity, title, recommendation, files?}`` — the
    reviewer's ``name`` becomes the fact ``title`` (the field the coverage
    algebra surfaces for unresolved blockers; the derived cache renders it
    as the record ``summary``). The ``fid`` is what resolution facts join on
    (D5) — a blocking finding without one could never be resolved, so the
    writer always assigns them.
    """
    merged: dict[tuple, dict] = {}
    for partial in partials:
        for f in partial.get("findings", []):
            # Normalize optional attribution to non-empty string paths, so a
            # blank/non-string element collapses to no ``files`` exactly like
            # ``[]`` or an omitted key — the validator tolerates such elements
            # rather than fail-closing, and normalization happens here.
            files = [
                x for x in (f.get("files") or []) if isinstance(x, str) and x.strip()
            ]
            key = (f["goal"], f["name"], tuple(files))
            entry = {
                "goal": f["goal"],
                "severity": f["severity"],
                "title": f["name"],
                "recommendation": f["recommendation"],
            }
            if files:
                entry["files"] = files
            existing = merged.get(key)
            if existing is None or (
                _SEVERITY_RANK[f["severity"]] > _SEVERITY_RANK[existing["severity"]]
            ):
                merged[key] = entry
    findings = list(merged.values())
    for idx, entry in enumerate(findings, start=1):
        entry["fid"] = f"R-{idx}"
    return findings


def _severity_counts(findings: list[dict]) -> tuple[int, int, int]:
    blocking = sum(1 for f in findings if f["severity"] == "blocking")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    note = sum(1 for f in findings if f["severity"] == "note")
    return blocking, warning, note


def build_fact_body(manifest: dict, partials: list[dict]) -> dict:
    """Assemble the review fact body (design D4) from the manifest interval
    and the merged partials. The derived cache is rendered FROM this body
    (:func:`fact_to_cache_record`), so it carries everything the cache needs."""
    findings = merge_findings(partials)
    blocking, warning, note = _severity_counts(findings)
    # Parallel reviewers → wall-clock is the slowest, not the sum. None when no
    # reviewer reported a duration.
    durations = [
        p["duration_seconds"]
        for p in partials
        if isinstance(p.get("duration_seconds"), (int, float))
        and not isinstance(p.get("duration_seconds"), bool)
    ]
    return {
        "base_commit": manifest.get("base_commit"),
        "base_tree": manifest["base_tree"],
        "head_tree": manifest["head_tree"],
        "head_commit": manifest.get("head_commit"),
        "dispatch_commit": manifest["commit_reviewed"],
        "mode": manifest["mode"],
        "mode_chosen_by": manifest["mode_chosen_by"],
        "tier": manifest.get("tier"),
        "roster": [
            {"role": p["role"], "model": p.get("model")} for p in partials
        ],
        "files_reviewed": list(manifest["files_reviewed"]),
        "files_changed": list(manifest["files_changed"]),
        "findings": findings,
        "counts": {"blocking": blocking, "warning": warning, "note": note},
        "duration_seconds": max(durations) if durations else None,
        "scope": manifest.get("scope"),
        "chunk": manifest.get("chunk"),
        "base_reviewed": manifest.get("base_reviewed"),
    }


def fact_to_cache_record(fact: dict) -> dict:
    """Render the derived ``.critic-findings.json`` record from a review fact
    (D7: the cache is a code-regenerated VIEW of the latest fact — builders
    and briefings read it for content; no gate reads it). Carries the source
    ``fact_id`` so staleness is detectable and the verify-resolutions
    dispatch can locate its anchor fact."""
    body = fact.get("body") or {}
    findings = []
    for f in body.get("findings", []):
        entry = {
            "fid": f.get("fid"),
            "goal": f.get("goal"),
            "severity": f.get("severity"),
            "summary": f.get("title"),
            "recommendation": f.get("recommendation"),
        }
        if f.get("files"):
            entry["files"] = list(f["files"])
        findings.append(entry)
    counts = body.get("counts") or {}
    blocking = counts.get("blocking", 0)
    warning = counts.get("warning", 0)
    note = counts.get("note", 0)
    if blocking:
        verdict = "Blocking findings must be resolved before proceeding."
    else:
        verdict = "Changes ready to proceed."
    roster = body.get("roster") or []
    models = [r.get("model") for r in roster if r.get("model")]
    return {
        "timestamp": fact.get("ts"),
        "duration_seconds": body.get("duration_seconds"),
        "mode": body.get("mode"),
        "mode_chosen_by": body.get("mode_chosen_by"),
        "model": models[0] if models else None,
        "commit_reviewed": body.get("dispatch_commit"),
        "base_reviewed": body.get("base_reviewed"),
        "files_reviewed": list(body.get("files_reviewed") or []),
        "findings": findings,
        "summary": (
            f"{blocking} blocking, {warning} warning, {note} note "
            f"across {len(roster)} reviewer(s). {verdict}"
        ),
        "fact_id": fact.get("id"),
    }


# ---------------------------------------------------------------------------
# Consolidate — the command body
# ---------------------------------------------------------------------------


def _known_findings_index(store: dict) -> set[tuple[str, str]]:
    """Every ``(review_id, fid)`` recorded in the store — the existence check
    a resolution must pass before it may weaken a gate."""
    known: set[tuple[str, str]] = set()
    for fact in evidence.facts_of_kind(store, "review"):
        body = fact.get("body") or {}
        for f in body.get("findings", []):
            if isinstance(f, dict) and _nonempty_str(f.get("fid")):
                known.add((fact.get("id"), f["fid"]))
    return known


def consolidate(project_dir: Path) -> int:
    """Merge complete reviewer partials into evidence facts + the derived
    cache. Idempotent.

    Exit codes:
      - ``0`` + ``no-op:`` — nothing to do (no manifest, or roster incomplete —
        the message names the missing roles). The common in-flight case as
        reviewers finish one by one.
      - ``0`` + ``consolidated:`` — review fact appended (or already present),
        resolution facts appended, cache regenerated, ledger anchored, marker
        cleared, partials removed.
      - ``1`` — fail-closed: malformed manifest/partial, a partial reviewed a
        different commit than dispatched, off-protocol resolutions, a
        resolution referencing a finding the store doesn't hold, a store
        write failure, or a ledger failure. Nothing partial is persisted as
        complete; the manifest is left in place so the fix can retry (fact
        appends already made are healed by the id-idempotency probe).
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
    review_id = manifest["id"]
    is_verify = manifest["mode"] == _VERBOSE_VERIFY_RESOLUTIONS

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

    # Resolutions may only arrive from a verify-resolutions dispatch — they
    # WEAKEN gates (they unblock findings), so off-protocol ones fail closed.
    resolutions: list[dict] = []
    seen_res: set[tuple[str, str]] = set()
    for partial in partials:
        entries = partial.get("resolutions") or []
        if entries and not is_verify:
            print(
                f"critic-consolidate: partial {partial['role']!r} carries "
                f"resolutions but the dispatch mode is {manifest['mode']!r} — "
                "only a verify-resolutions dispatch may resolve findings; "
                "fail-closed.",
                file=sys.stderr,
            )
            return 1
        for r in entries:
            key = (r["review_id"], r["fid"])
            if key not in seen_res:
                seen_res.add(key)
                resolutions.append(r)

    store = evidence.read_facts(project_dir)
    if store["status"] == "error":
        print(
            f"critic-consolidate: evidence store unreadable — {store['reason']}",
            file=sys.stderr,
        )
        return 1
    if resolutions:
        known = _known_findings_index(store)
        for r in resolutions:
            if (r["review_id"], r["fid"]) not in known:
                print(
                    f"critic-consolidate: resolution targets finding "
                    f"{r['fid']!r} of review {r['review_id']!r}, which the "
                    "evidence store does not hold — a resolution must "
                    "reference a recorded finding; fail-closed.",
                    file=sys.stderr,
                )
                return 1

    # All preconditions met — append the review fact (idempotent by id: the
    # CRT-4B7X double-consolidate race appends exactly one).
    already = any(
        f.get("id") == review_id for f in evidence.facts_of_kind(store, "review")
    )
    if not already:
        body = build_fact_body(manifest, partials)
        result = evidence.append_fact(project_dir, "review", review_id, body)
        if result["status"] != "appended":
            print(
                f"critic-consolidate: could not append review fact — "
                f"{result['reason']}",
                file=sys.stderr,
            )
            return 1

    # Resolution facts (D5) — deterministic ids so a retry appends nothing new.
    appended_resolutions = 0
    for r in resolutions:
        res_id = f"{review_id}:{r['review_id']}:{r['fid']}"
        if evidence.has_fact(project_dir, "resolution", res_id):
            continue
        res_body = {
            "finding": {"review_id": r["review_id"], "fid": r["fid"]},
            "disposition": r["disposition"],
            "verified_by": review_id,
            "at_tree": manifest["head_tree"],
            "rationale": r.get("rationale"),
        }
        result = evidence.append_fact(project_dir, "resolution", res_id, res_body)
        if result["status"] != "appended":
            print(
                f"critic-consolidate: could not append resolution fact — "
                f"{result['reason']}",
                file=sys.stderr,
            )
            return 1
        appended_resolutions += 1

    # Regenerate the derived cache FROM the stored fact (D7) — re-read so a
    # retry after a partial failure renders the original fact, not a new one.
    store = evidence.read_facts(project_dir)
    fact = next(
        (
            f
            for f in evidence.facts_of_kind(store, "review")
            if f.get("id") == review_id
        ),
        None,
    )
    if fact is None:
        print(
            "critic-consolidate: internal error — appended review fact "
            f"{review_id!r} not readable back from the store.",
            file=sys.stderr,
        )
        return 1
    record = fact_to_cache_record(fact)
    findings_path = prawduct_dir / ".critic-findings.json"
    atomic_write_text(findings_path, json.dumps(record, indent=2))

    # Belt-and-suspenders: the cache we just rendered must satisfy the schema
    # its readers trust. If it doesn't, that is a bug in fact_to_cache_record —
    # fail loudly rather than anchor an invalid record in the ledger.
    if not gates.validate_critic_findings(findings_path):
        print(
            "critic-consolidate: internal error — rendered cache record failed "
            "schema validation; not anchoring in the ledger.",
            file=sys.stderr,
        )
        return 1

    # Anchor in the governance ledger (telemetry + v2 gate continuity).
    models = [p.get("model") for p in partials if p.get("model")]
    argv = ["--event", "review.critic"]
    if manifest.get("scope"):
        argv += ["--scope", manifest["scope"]]
    if manifest.get("chunk"):
        argv += ["--chunk", manifest["chunk"]]
    if models:
        argv += ["--model", models[0]]
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

    counts = (fact.get("body") or {}).get("counts") or {}
    res_note = f", {appended_resolutions} resolution fact(s)" if resolutions else ""
    print(
        f"consolidated: {counts.get('blocking', 0)} blocking, "
        f"{counts.get('warning', 0)} warning, {counts.get('note', 0)} note "
        f"from {len(partials)} reviewer(s) → fact {review_id}{res_note} + "
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
