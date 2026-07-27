"""Critic mode inference — picks the right ``/critic`` mode from git +
build-plan state so the builder doesn't have to declare it at every chunk.

Explicit ``$ARGUMENTS`` always wins (the per-invocation override path).
Below it sits the **plan-level override**: when the active build plan's
CURRENT chunk declares a valid ``**Critic mode:**`` field, that mode is
honored as a successive override (rationale ``"plan-override: <mode>"``).
"Current" is normally the first unchecked ``- [ ]`` item, but on a
``views_enabled`` feature branch the Status checkboxes are a derived view
that only flips at release (so "first unchecked" is always Chunk 01) — there
the current chunk is derived from git instead (CRT-7B4M). Choosing between
those two readings lives in :func:`lib.buildplan_refs.resolve_chunk_progress`,
which this module consumes rather than reimplements. The methodology has always called this field
a "successive override," and this is where it is read (CRT-3M8Q). Only when neither override fires
does :func:`infer_mode` walk four inference rules in precedence order and
return the first that fires:

  1. ``verify-resolutions`` — prior ``.critic-findings.json`` has
     BLOCKING/WARNING findings + ``commit_reviewed`` anchor resolves +
     uncommitted diff is non-empty AND is a subset of prior
     ``files_reviewed``. Signal: builder is in the middle of fixing
     findings from the last review.
  1b. ``verify-resolutions`` (post-cumulative fix, CRT-4J8W) — tree clean,
     prior record is a ``cumulative`` review, and the committed delta since
     its ``commit_reviewed`` has ≥1 non-``.md`` file under the widening
     threshold. Signal: builder committed a fix after the cumulative; a
     verify pass reviews the delta instead of re-paying a full bundle
     review. (The v2 multi-link chain arm — a verify record carrying an
     ``extends_cumulative`` anchor — died in the kernel-v3 cutover: no
     writer emits the field, and the gates compose facts by tree, so the
     recommendation no longer needs to propagate anchors.)
  2. ``cumulative`` — working tree is clean (no uncommitted code) AND
     branch is ≥2 commits ahead of the detected base branch AND no
     ``cumulative``-mode findings file exists for current HEAD. Signal:
     builder has shipped chunks and is at the ``/pr create`` precondition
     point.
  3. ``final`` — active build plan with exactly one unchecked chunk left
     AND uncommitted work is present (the builder is on the last chunk),
     OR no build plan + uncommitted diff has ≥5 files (medium+
     non-chunked work).
  4. ``chunk`` when an active build plan grounds the choice (default
     for mid-plan reviews); ``final`` otherwise (no plan + no other
     rule fired — fail-safe to thoroughness, matching the SKILL's
     historical "missing/unrecognized → final" norm).

Deviation from build-plan rule 2: the spec reads "branch ahead of base by
≥2 commits AND no cumulative-mode record exists for the current HEAD"
with no working-tree-clean guard. Implemented WITH the clean-tree guard
so the rule doesn't over-fire mid-chunk-3-of-5 (which would silently
demote ``chunk``-mode reviews to 4-10 min ``cumulative`` runs at every
commit). The user-feedback motivation for the whole proportionality
thread was reducing review latency for small fixes — over-firing
cumulative would undo that. The guard preserves the spec's intent (run
cumulative when about to PR) without the cost.

Pure-ish: takes ``project_dir``, reads files under it, runs ``git``
subprocesses against it. Deterministic given fixed git state. Imports only
from the stdlib + light lib siblings (``core``, ``coverage``, ``gitstate``,
``buildplan_refs``) — never ``bin/prawduct-hook``, and never ``lib.gates``
(keeping gates out of this module's import graph is why the chain-anchor
helper below is a deliberate, test-pinned mirror rather than an import).
The metadata/build-plan helpers once re-implemented here moved to their
canonical homes in ``gitstate``/``buildplan_refs`` (STH-2K8R); this module
consumes them.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import buildplan_refs, gitstate
from .core import resolve_build_plan_path
from .coverage import _resolve_base_branch

# Verbose-string mode constant — used to recognize prior findings'
# ``mode`` field. Must stay in lockstep with ``lib.gates``'s
# ``_CRITIC_MODE_*`` constants and ``critic_consolidate``'s
# ``MODE_TOKEN_TO_VERBOSE``. (Persisted form is verbose; caller-side
# short tokens are what we return / accept as ``args``.)
_MODE_CUMULATIVE_VERBOSE = "cumulative (bundle review, ready for merge)"

# Short-token caller-side mode names — what ``$ARGUMENTS`` carries and
# what :func:`infer_mode` returns as the first element of its tuple. The
# same token set is accepted in the build plan's per-chunk
# ``**Critic mode:**`` field (the plan-level override).
_VALID_ARG_MODES = frozenset({
    "chunk",
    "final",
    "cumulative",
    "verify-resolutions",
})

# Matches a chunk's ``- **Critic mode:** <value>`` build-plan field.
# Mirrors ``bin/prawduct-hook``'s ``_BUILD_PLAN_TYPE_RE`` shape (leading
# list-item / bold markers tolerated). The value token is hyphen-aware so
# ``verify-resolutions`` is captured whole.
_BUILD_PLAN_CRITIC_MODE_RE = re.compile(
    r"^[\s\-\*]*\*\*Critic mode:\*\*\s*([A-Za-z][\w\-]*)"
)


def infer_mode(
    project_dir: Path | str,
    args: str | None = None,
) -> tuple[str, str]:
    """Infer the right ``/critic`` mode for the current project state.

    Parameters
    ----------
    project_dir : Path | str
        Project root (contains ``.prawduct/``). Coerced to ``Path``.
    args : str | None
        The ``$ARGUMENTS`` string passed to ``/critic``. When non-empty
        and parseable as one of the recognized mode tokens, that token
        wins outright (rationale ``"explicit-args"``). Empty / None /
        unrecognized → trigger inference.

    Returns
    -------
    (mode, rationale) : tuple[str, str]
        ``mode`` is the short-token form (``chunk`` / ``final`` /
        ``cumulative`` / ``verify-resolutions``). ``rationale`` is a
        human-readable string suitable both for stdout reporting and the
        ``mode_chosen_by`` field in ``.critic-findings.json``.
    """
    project_dir = Path(project_dir)

    if args is not None:
        stripped = args.strip()
        if stripped:
            token = stripped.split()[0]
            if token in _VALID_ARG_MODES:
                return token, "explicit-args"

    prawduct_dir = project_dir / ".prawduct"

    # Resolve chunk progress ONCE, through the one owner of the question. The
    # Status checkboxes are the default signal, but with ``views_enabled`` they
    # are a *derived view* that only flips at release — so on a pre-release
    # feature branch they never flip and "first unchecked" is always Chunk 01,
    # which would pin every chunk's mode to Chunk 01's declaration; there
    # progress comes from git instead (CRT-7B4M). Choosing BETWEEN those two
    # readings is exactly what `resolve_chunk_progress` owns. Writing that
    # choice out here as well is what let the defect reach three consumers, so
    # this module asks rather than re-derives.
    progress = buildplan_refs.resolve_chunk_progress(project_dir)
    total, complete = progress.total, progress.complete
    current_chunk_id = progress.current_id

    # Plan-level override: the CURRENT chunk may declare a ``**Critic mode:**``
    # field. Honor it here (above inference, below explicit args) so a
    # plan-mandated ``final`` is no longer silently demoted to the inferred
    # ``chunk`` (CRT-3M8Q). "Current" is the git-aware chunk above, so on a
    # feature branch the override reads the chunk actually in progress, not
    # always Chunk 01 (CRT-7B4M). Only a recognized token overrides; an absent /
    # blank / unrecognized field falls through to ordinary inference.
    plan_mode = (
        _critic_mode_for_chunk(prawduct_dir, current_chunk_id)
        if current_chunk_id is not None
        else None
    )
    if plan_mode is not None:
        return plan_mode, f"plan-override: {plan_mode}"

    if _rule_verify_resolutions_fires(prawduct_dir, project_dir):
        return "verify-resolutions", (
            "rule-1 verify-resolutions: prior findings have actionable "
            "(BLOCKING/WARNING) entries with a resolvable commit_reviewed "
            "anchor, and the current uncommitted diff is a non-empty "
            "subset of prior files_reviewed (builder is mid-fix)"
        )

    postfix_reason = _rule_postfix_fix_fires(prawduct_dir, project_dir)
    if postfix_reason:
        return "verify-resolutions", (
            f"rule-1b verify-resolutions (post-cumulative fix): {postfix_reason}"
        )

    cumulative_reason = _rule_cumulative_fires(prawduct_dir, project_dir)
    if cumulative_reason:
        return "cumulative", f"rule-2 cumulative: {cumulative_reason}"

    final_reason = _rule_final_fires(project_dir, total, complete)
    if final_reason:
        return "final", f"rule-3 final: {final_reason}"

    # Rule 4: chunk only when an active build plan grounds the choice;
    # otherwise fall through to ``final`` (the historical fail-safe norm
    # documented in the SKILL files). Without a plan there's no "chunk"
    # for chunk-mode to scope to — defaulting to ``final`` matches the
    # rule "missing/unrecognized → final" the SKILL has always promised.
    if total > 0:
        return "chunk", (
            "rule-4 chunk: active build plan, prior chunks committed, "
            "no fix-in-progress signal, no cumulative precondition"
        )
    return "final", (
        "rule-4 final: no active build plan and no other rule fired — "
        "fail-safe to thoroughness"
    )


# ---------------------------------------------------------------------------
# Rule predicates
# ---------------------------------------------------------------------------


def _rule_verify_resolutions_fires(
    prawduct_dir: Path, project_dir: Path
) -> bool:
    """Rule 1: prior findings + anchor resolves + diff ⊆ prior scope."""
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return False
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return False

    findings = data.get("findings")
    if not isinstance(findings, list):
        return False
    actionable = [
        f for f in findings
        if isinstance(f, dict) and f.get("severity") in ("blocking", "warning")
    ]
    if not actionable:
        return False

    prior_files = data.get("files_reviewed")
    if not isinstance(prior_files, list) or not prior_files:
        return False
    prior_set = {f for f in prior_files if isinstance(f, str) and f.strip()}
    if not prior_set:
        return False

    if not _commit_resolves(project_dir, commit_reviewed):
        return False

    diff_files = _get_uncommitted_code_files(project_dir)
    if not diff_files:
        return False

    # Subset check: every uncommitted file must be in the prior review's
    # surface. Even one file outside scope means the builder added new
    # work alongside the fix — that's a chunk/final case, not a verify
    # pass. (Symmetric with ``_verify_resolutions_gate_check`` in
    # bin/prawduct-hook; same "diff ⊆ scope" contract.)
    return diff_files.issubset(prior_set)


def _cumulative_anchor(data: dict) -> str | None:
    """Return the prior ``cumulative`` review's ``commit_reviewed`` when
    ``data`` is one, else ``None`` — the only record kind rule 1b extends.

    The v2 multi-link arm (a ``verify-resolutions`` record carrying an
    ``extends_cumulative`` anchor) was deleted in the kernel-v3 chunk-06
    vestige sweep: nothing writes the field since the cutover, and the
    gates compose review FACTS by tree, so mode inference no longer needs
    to propagate anchors through the single-slot cache. Stays-deleted
    guards live in ``tests/test_critic_mode_inference.py``.
    """
    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return None
    if data.get("mode") == _MODE_CUMULATIVE_VERBOSE:
        return commit_reviewed
    return None


def _rule_postfix_fix_fires(prawduct_dir: Path, project_dir: Path) -> str:
    """Rule 1b (CRT-4J8W): a committed fix after a cumulative review.

    Fires when the working tree is clean, the prior record is a
    ``cumulative`` review (see :func:`_cumulative_anchor`), its
    ``commit_reviewed`` resolves, and the committed delta since it has at
    least one non-``.md`` file while staying under the verify-resolutions
    widening threshold (``len(delta) > 2 * prior + 5`` — mirrored so the
    rule never recommends a mode that would immediately demote). Without
    this rule the canonical no-args ``/prawduct:critic`` after a
    post-cumulative fix falls through to rule 2 and recommends a FULL
    bundle re-review — the run-count treadmill this rule exists to kill
    (under v3 either recommendation records a fact the gates compose;
    the verify pass is simply the delta-cost one). A doc-only
    (all-``.md``) or empty delta does not fire: the existing coverage
    still spans HEAD, so no review is needed at all.

    Returns a rationale string when the rule fires, ``""`` otherwise.
    """
    if _get_uncommitted_code_files(project_dir):
        return ""
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return ""
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""
    anchor = _cumulative_anchor(data)
    if anchor is None:
        return ""
    commit_reviewed = data["commit_reviewed"]  # non-empty str when anchor is not None
    if not _commit_resolves(project_dir, commit_reviewed):
        return ""
    prior_files = data.get("files_reviewed")
    if not isinstance(prior_files, list) or not prior_files:
        return ""
    prior_set = {f for f in prior_files if isinstance(f, str) and f.strip()}
    if not prior_set:
        return ""
    delta = {
        f for f in _committed_files_since(project_dir, commit_reviewed)
        if not gitstate._is_metadata_path(f)
    }
    if not any(not f.endswith(".md") for f in delta):
        return ""
    if len(delta) > 2 * len(prior_set) + 5:
        return ""
    return (
        f"committed delta of {len(delta)} file(s) since the prior "
        f"cumulative review ({commit_reviewed[:12]}); a verify pass "
        "extends the cumulative's vouching to HEAD at delta-review cost"
    )


def _rule_cumulative_fires(
    prawduct_dir: Path, project_dir: Path
) -> str:
    """Rule 2: clean tree + ≥2 commits ahead + no fresh cumulative record.

    Returns rationale string when the rule fires, empty string otherwise.
    """
    # Clean working tree — see module docstring's deviation note for why
    # this guard is added on top of the spec.
    if _get_uncommitted_code_files(project_dir):
        return ""

    base_branch, _ = _resolve_base_branch(project_dir)
    if not base_branch:
        return ""

    commits_ahead = buildplan_refs._commits_ahead_of_base(project_dir, base_branch)
    if commits_ahead < 2:
        return ""

    # Skip if a cumulative-mode record already covers current HEAD —
    # re-recommending the bundle review the builder just ran is noise.
    # (The v2 chain-record arm — verify-resolutions + extends_cumulative —
    # died in the kernel-v3 chunk-06 vestige sweep: nothing writes the
    # field, so a record carrying it is v2-era state the gates ignore.)
    head_sha = gitstate._git_head_sha(project_dir)
    findings_path = prawduct_dir / ".critic-findings.json"
    if head_sha and findings_path.is_file():
        try:
            data = json.loads(findings_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        if (
            data.get("commit_reviewed") == head_sha
            and data.get("mode") == _MODE_CUMULATIVE_VERBOSE
        ):
            return ""

    return (
        f"branch is {commits_ahead} commits ahead of {base_branch}, "
        "working tree clean, no fresh cumulative-mode record for "
        "current HEAD"
    )


def _rule_final_fires(project_dir: Path, total: int, complete: int) -> str:
    """Rule 3: last chunk in progress, or no-plan medium+ work.

    Takes the chunk counts resolved by :func:`infer_mode` (``complete`` may be
    git-derived on a views-enabled feature branch — CRT-7B4M — not the raw
    checkbox count). Returns a rationale string when the rule fires, ``""``
    otherwise.
    """
    if total > 0:
        # Active build plan.
        unchecked = total - complete
        if unchecked == 1 and _get_uncommitted_code_files(project_dir):
            return (
                f"last unchecked chunk of {total}-chunk plan is in "
                f"progress ({complete} marked [x], current chunk has "
                "uncommitted work)"
            )
        return ""

    # No active plan — fall back to size-based final for medium+ work.
    diff_files = _get_uncommitted_code_files(project_dir)
    if len(diff_files) >= 5:
        return (
            f"no build plan, session diff has {len(diff_files)} changed "
            "files (medium+ work — full review warranted)"
        )
    return ""


# ---------------------------------------------------------------------------
# Internal helpers — git + build-plan parsing
# ---------------------------------------------------------------------------


def _get_uncommitted_code_files(project_dir: Path) -> set[str]:
    """Return uncommitted-change file paths (vs HEAD), minus metadata.

    Includes modifications, staged changes, untracked files. Rename
    targets are returned (porcelain ``XY <old> -> <new>``). Uses
    ``--untracked-files=all`` so a new directory expands to per-file
    entries rather than collapsing to ``?? subdir/`` (the default
    ``--untracked-files=normal`` undercounts new directories — caught
    by ``test_wins_for_no_plan_medium_plus_work``). The ``-uall`` flag is
    why this keeps its own ``git status`` call instead of
    ``gitstate.git_status_output``; line parsing (quoted paths, renames)
    is ``gitstate.parse_porcelain_line``.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return set()
    files: set[str] = set()
    for line in proc.stdout.splitlines():
        parsed = gitstate.parse_porcelain_line(line)
        if parsed is None:
            continue
        path = parsed[2]
        if not gitstate._is_metadata_path(path):
            files.add(path)
    return files


def _committed_files_since(project_dir: Path, sha: str) -> set[str]:
    """Files changed in ``<sha>..HEAD`` (committed delta). ``set()`` on failure."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{sha}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _commit_resolves(project_dir: Path, sha: str) -> bool:
    """True iff ``sha`` resolves to a commit in this repo."""
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode == 0


# `_commits_ahead_of_base` / `_committed_chunk_ids` / `_git_aware_progress` moved
# to lib/buildplan_refs.py — they answer "which chunk is current," which is
# build-plan Status parsing, and keeping the derivation here made it reachable
# only by this module's consumer (the defect recurred at two others: BLD-7K3Q,
# SCN-4H9T). This module now reaches it through `buildplan_refs.resolve_chunk_progress`
# like every other consumer — `infer_mode` calls that directly.


def _critic_mode_for_chunk(prawduct_dir: Path, chunk_id: str | None) -> str | None:
    """Return ``chunk_id``'s declared ``**Critic mode:**`` token, or ``None``.

    Finds that chunk's ``### Chunk <id>:`` detail section and reads its
    ``- **Critic mode:** <value>`` field. Returns the short-token value
    only when it is one of the recognized modes; an absent, blank, or
    unrecognized value yields ``None`` (fall through to inference rather
    than honoring a typo as a mode override — same fail-open-to-inference
    posture the methodology's "optional field" contract implies).

    ``chunk_id`` is resolved by the caller via
    ``buildplan_refs`` — git-aware on a views-enabled feature branch
    (CRT-7B4M), otherwise the first ``- [ ]`` chunk. Section discovery is
    the shared ``buildplan_refs._chunk_section_lines`` walker: name-anchored
    on ``### Chunk <id>:`` with leading-zero tolerance, fenced code blocks
    skipped, stop at the next sibling chunk or top-level section.
    """
    if chunk_id is None:
        return None

    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None
    try:
        # Explicit UTF-8 with the same except-set as every other build-plan
        # reader. `infer_mode` reads the plan TWICE — here and through
        # `buildplan_refs.resolve_chunk_progress` — so a locale codec here made
        # one function disagree with itself about whether the plan decodes.
        # `UnicodeDecodeError` is a `ValueError`, so a bare `except OSError`
        # let it escape past a caller that has no guard.
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    _found, section_lines = buildplan_refs._chunk_section_lines(content, chunk_id)
    for _line_num, line in section_lines:
        m = _BUILD_PLAN_CRITIC_MODE_RE.match(line)
        if m:
            token = m.group(1)
            return token if token in _VALID_ARG_MODES else None
    return None
