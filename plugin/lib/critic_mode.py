"""Critic mode inference — picks the right ``/critic`` mode from git +
build-plan state so the builder doesn't have to declare it at every chunk.

Explicit ``$ARGUMENTS`` always wins (the per-invocation override path).
Below it sits the **plan-level override**: when the active build plan's
CURRENT chunk declares a valid ``**Critic mode:**`` field, that mode is
honored as a successive override (rationale ``"plan-override: <mode>"``).
"Current" is the first unchecked ``- [ ]`` item, read through
:func:`lib.buildplan_refs.resolve_chunk_progress`, which this module consumes
rather than reimplements. A second, git-derived reading of that question once
existed for repos whose checkboxes only flipped at release; both it and the
precedence between the two are retired, but the single-owner discipline is not
— re-deriving "current" here is what let the original defect reach three
consumers (CRT-7B4M). The methodology has always called this field
a "successive override," and this is where it is read (CRT-3M8Q). Only when neither override fires
does :func:`infer_mode` walk four inference rules in precedence order and
return the first that fires:

  1. ``verify-resolutions`` — prior ``.critic-findings.json`` has
     BLOCKING/WARNING findings + ``commit_reviewed`` anchor resolves **and is
     an ancestor of HEAD** + uncommitted diff is non-empty AND is a subset of
     prior ``files_reviewed``. Signal: builder is in the middle of fixing
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
  4. ``chunk`` when a build plan grounds the choice **and the working tree
     holds something to review** (default for mid-plan reviews);
     ``cumulative`` when the tree is clean, since ``chunk``/``final`` scope to
     the uncommitted diff and dispatching one would refuse on an empty
     interval; ``final`` otherwise (no plan + no other rule fired — fail-safe
     to thoroughness, matching the SKILL's historical
     "missing/unrecognized → final" norm).

The plan rule 4 grounds on is **this branch's**, not necessarily the
``active_build_plan`` pointer's: a branch whose name matches a scope some plan
declares is building that plan (``buildplan_refs.resolve_reviewed_plan``). A
branch matching nothing keeps the pointer, and the rationale — which is what
lands in ``mode_chosen_by`` — says the relation is assumed rather than shown.

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
from typing import NamedTuple

from . import buildplan_refs, coverage_algebra, gitstate
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

    # Resolve chunk progress ONCE, through the one owner of the question.
    # Re-deriving "which chunk is current" locally is what let the original
    # defect reach three consumers (CRT-7B4M), so this module asks rather than
    # re-derives — that discipline outlives the second reading it was written
    # for.
    # Which plan this branch is building. The `active_build_plan` pointer answers
    # "which plan is in progress in this repo", which on a repo running several
    # plans across worktrees is a different question — and rule 4 used to ground
    # `chunk` on whatever it named, so a branch with no plan of its own inherited
    # an unrelated one's chunk count. When the branch names a scope some plan
    # declares, that plan is the subject and the pointer is not consulted; when
    # it names nothing, the pointer stands and rule 4 says so in its rationale
    # rather than presenting an assumption as a finding.
    plan = buildplan_refs.resolve_branch_plan(project_dir, prawduct_dir)
    progress = buildplan_refs.resolve_chunk_progress(project_dir, plan.path)
    total, complete = progress.total, progress.complete
    current_chunk_id = progress.current_id

    # Plan-level override: the CURRENT chunk may declare a ``**Critic mode:**``
    # field. Honor it here (above inference, below explicit args) so a
    # plan-mandated ``final`` is no longer silently demoted to the inferred
    # ``chunk`` (CRT-3M8Q). "Current" is the git-aware chunk above, so on a
    # feature branch the override reads the chunk actually in progress, not
    # always Chunk 01 (CRT-7B4M). Only a recognized token overrides; an absent /
    # blank / unrecognized field falls through to ordinary inference.
    plan_read = (
        _critic_mode_for_chunk(prawduct_dir, current_chunk_id, plan.path)
        if current_chunk_id is not None
        else ChunkModeRead(None, None)
    )
    if plan_read.mode is not None:
        return plan_read.mode, f"plan-override: {plan_read.mode}"

    # An unreadable plan escalates rather than falling through. Rule 4 would
    # answer `chunk` — the narrowest mode there is — on the strength of a plan
    # nobody could parse, which is the canonical rule inverted: "missing,
    # unrecognized, or inference cannot make a confident call → final". The
    # reason travels with it, so the rationale names the plan instead of
    # reporting a confident `chunk`.
    if plan_read.unreadable:
        return "final", f"rule-0 final (plan unreadable): {plan_read.unreadable}"

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

    # Rule 4: chunk only when a build plan grounds the choice AND there is
    # something a working-tree-scoped mode could review; otherwise fall through
    # to ``final`` (the historical fail-safe norm documented in the SKILL
    # files). Without a plan there's no "chunk" for chunk-mode to scope to —
    # defaulting to ``final`` matches the rule "missing/unrecognized → final"
    # the SKILL has always promised.
    #
    # `chunk` and `final` both review the uncommitted diff (HEAD tree → captured
    # working tree), so on a clean tree their interval is EMPTY and
    # `critic-begin` refuses — correctly, but only after the round-trip. A mode
    # that cannot review anything is not the answer to "what should I run",
    # whichever rule matched. `cumulative` is the mode whose interval is
    # committed, and it is what the refusal message named as the remedy.
    if _working_tree_is_empty(project_dir):
        redirect = _clean_tree_redirect(prawduct_dir, project_dir)
        if redirect:
            return "cumulative", f"rule-4 cumulative: {redirect}"
    if total > 0:
        return "chunk", (
            f"rule-4 chunk: {_plan_relation_note(plan)}, prior chunks "
            "committed, no fix-in-progress signal, no cumulative precondition"
        )
    return "final", (
        "rule-4 final: no active build plan and no other rule fired — "
        "fail-safe to thoroughness"
    )


def _clean_tree_redirect(prawduct_dir: Path, project_dir: Path) -> str:
    """Rationale for answering ``cumulative`` on a clean tree, or ``""``.

    ``chunk`` and ``final`` both review HEAD-tree → working-tree, so with an
    empty interval ``critic-begin`` refuses. Recommending one anyway costs a
    round-trip and names no remedy the caller didn't already have.

    The caller gates this on :func:`_working_tree_is_empty`, NOT on
    :func:`_get_uncommitted_code_files` — those answer different questions, and
    the difference is exactly a record-only work cycle. That helper drops every
    path under ``.prawduct/``, while the interval comes from ``capture_tree``,
    which stages everything tracked; so uncommitted plan and change-log edits DO
    make the interval non-empty. Redirecting them to ``cumulative`` would
    note-and-exclude the records just written and stamp "working tree is clean"
    into ``mode_chosen_by`` — a durable field of the review fact — over a dirty
    tree.

    **What such a dispatch then does changed on 2026-08-06, and this distinction
    survived it.** A record-only interval is non-empty but holds nothing
    *judgeable*, so ``critic-begin`` now answers exit 3 (no review needed) rather
    than reviewing it. The reason to keep the two helpers apart is therefore no
    longer "those edits get reviewed" — it is that the two refusals are different
    answers and only one of them is true here: an empty interval is "there is
    nothing here", while a record-only interval is "there is something here and
    the gate does not need it reviewed". Redirecting the second to ``cumulative``
    would still stamp a false claim into a durable field, and would still name a
    remedy the caller does not need.

    **Only redirects when the redirect works.** ``cumulative`` needs a resolvable
    base and at least one commit beyond it, or it refuses in its own way; and a
    fresh cumulative record already covering HEAD means the bundle review was
    just run, so re-recommending it is the noise rule 2 declines to make. When
    none of that holds there is genuinely nothing dispatchable, and the caller
    keeps the fail-safe answer with its honest refusal rather than a redirect to
    a second refusal.
    """
    base_branch, _ = _resolve_base_branch(project_dir)
    if not base_branch:
        return ""
    commits_ahead = buildplan_refs._commits_ahead_of_base(project_dir, base_branch)
    if commits_ahead < 1:
        return ""
    if _fresh_cumulative_covers_head(prawduct_dir, project_dir):
        return ""
    return (
        "working tree is clean, so chunk/final would dispatch an empty "
        f"interval; branch is {commits_ahead} commit(s) ahead of {base_branch} "
        "and no cumulative record covers current HEAD — the committed bundle "
        "is cumulative's scope"
    )


def _fresh_cumulative_covers_head(prawduct_dir: Path, project_dir: Path) -> bool:
    """True when the derived cache records a ``cumulative`` review of this exact
    HEAD — i.e. the bundle review has already been run and re-recommending it
    would be noise.

    One home for the question: rule 2 skips on it, and rule 4's clean-tree
    redirect must not undo that skip by routing to the mode rule 2 just declined.
    """
    head_sha = gitstate._git_head_sha(project_dir)
    findings_path = prawduct_dir / ".critic-findings.json"
    if not head_sha or not findings_path.is_file():
        return False
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return (
        data.get("commit_reviewed") == head_sha
        and data.get("mode") == _MODE_CUMULATIVE_VERBOSE
    )


def _plan_relation_note(plan) -> str:
    """How rule 4's grounding plan was chosen — confirmed, or assumed.

    The relation is *confirmable* only when the branch names a scope some plan
    declares; a branch whose name matches nothing cannot be shown related OR
    unrelated, and declining there would demote every repo whose branch names
    differ from its scopes. So the unconfirmable case keeps the pointer and says
    so, which puts the assumption in ``mode_chosen_by`` — the record where a
    reader can find it — instead of leaving it implied by a bare "active build
    plan" (`nonfunctional-requirements.md` § Direction: a control emits its
    yield observably or it can only be defended on principle).
    """
    if plan.source == buildplan_refs.SOURCE_SCOPE_NAMED:
        return f"build plan {plan.rel} declares this branch's scope {plan.scope!r}"
    return (
        f"active build plan {plan.rel or '(unresolved)'}, assumed related — this "
        "branch's name matches no plan's declared scope, so the pointer stands "
        "unconfirmed"
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

    # Resolving is not enough: a sibling branch's anchor resolves in the shared
    # object store, and the delta from it would span the divergence.
    if not _commit_resolves(project_dir, commit_reviewed):
        return False
    if not _commit_is_ancestor(project_dir, commit_reviewed):
        return False

    diff_files = _get_uncommitted_code_files(project_dir)
    if not diff_files:
        return False

    # Subset check: every uncommitted file must be in the prior review's
    # surface. Even one file outside scope means the builder added new
    # work alongside the fix — that's a chunk/final case, not a verify
    # pass. The dispatch side enforces the same "diff ⊆ scope" contract in
    # ``critic_consolidate.begin_review``, whose verify arm anchors on
    # ``_prior_review_fact`` and refuses once ``_scope_widened`` trips.
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
    the verify pass is simply the delta-cost one). A delta holding no
    **judgeable** file, or an empty one, does not fire: the existing coverage
    still spans HEAD, so no review is needed at all. Judgeable is
    :func:`coverage_algebra.is_judgeable_path`, NOT a ``.md`` suffix test —
    governance-protected prose is judgeable and does fire, which is the case
    this docstring used to get wrong along with the code below it.

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
    # Same reason as rule 1: an anchor off this lineage yields a cross-branch
    # delta, and `_committed_files_since` below would take exactly that diff.
    if not _commit_is_ancestor(project_dir, commit_reviewed):
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
    # THE predicate again (CRT-5D8Q). This was a FIFTH bare-suffix classifier,
    # found by the class scan the change-log-gate fix triggered — the same
    # `.endswith(".md")` shape, and wrong in the same direction: governance-
    # protected prose (`skills/`, `methodology/`, `templates/`, root CLAUDE.md)
    # IS judgeable, so a committed delta of only skill prose used to suppress the
    # verify-resolutions suggestion as though nothing reviewable had landed.
    if not coverage_algebra.judgeable_files(list(delta)):
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
    """Rule 2: no code in flight + ≥2 commits ahead + no fresh cumulative record.

    Returns rationale string when the rule fires, empty string otherwise.
    """
    # No CODE in flight — deliberately the metadata-stripped predicate, not the
    # strict :func:`_working_tree_is_empty` that rule 4's redirect uses. The two
    # ask different questions and the difference is load-bearing in opposite
    # directions: rule 4 asks "would a working-tree mode have anything to
    # review", where uncommitted records ARE content; rule 2 asks "is the
    # builder mid-work", where they are not. Tightening this one would mean a
    # builder with an uncommitted change-log entry — the normal state just
    # before a PR — could never be recommended the bundle review the PR gate
    # wants. See the module docstring's deviation note for why the guard exists.
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
    if _fresh_cumulative_covers_head(prawduct_dir, project_dir):
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


def _working_tree_is_empty(project_dir: Path) -> bool:
    """True when the working tree holds NO uncommitted change at all.

    The honest predicate for "a working-tree-scoped mode has nothing to review":
    it counts metadata too, because ``capture_tree`` — which derives the actual
    interval — stages everything tracked and does not strip ``.prawduct/``.
    :func:`_get_uncommitted_code_files` answers the narrower "is there *code* in
    flight", which the size-based rules want and this does not.

    Fails toward NOT empty: any git failure returns False, so an unreadable
    state keeps the caller on the fail-safe answer rather than redirecting on a
    tree it could not read. The guard covers the *raise* class too — an absent
    binary or the timeout — because a docstring promising a return value while
    the call propagates is a promise the code does not keep.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    return not proc.stdout.strip()


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
    """True iff ``sha`` resolves to a commit in this repo.

    Necessary but NOT sufficient for an anchor — see :func:`_commit_is_ancestor`.
    Worktrees of one clone share an object store, so this succeeds for any object
    in it, a sibling branch's tip included.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode == 0


def _commit_is_ancestor(project_dir: Path, sha: str) -> bool:
    """True iff ``sha`` is an ancestor of HEAD — i.e. on *this* lineage.

    The guard :func:`_commit_resolves` is not. A record left by a sibling branch
    survives a branch switch in the single-slot ``.critic-findings.json``, and
    its anchor still resolves in the shared object store — so resolution alone
    let a verify-resolutions dispatch latch onto a cross-branch anchor and diff
    across the divergence, reviewing phantom changes this branch never made.

    **Fails closed.** Only exit 0 is an ancestor; exit 1 (genuinely not one) and
    any other failure — git missing, timeout, a malformed SHA — all return False,
    so an anchor that cannot be *placed* is never trusted. The mirror shape is
    ``coverage.py``'s and ``briefing.py``'s, which run the same plumbing command.
    """
    try:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# `_commits_ahead_of_base` / `_committed_chunk_ids` moved to lib/buildplan_refs.py
# (a third mover, `_git_aware_progress`, was not moved but DELETED — the
# git-derived second reading of chunk progress is retired, so a reader following
# this pointer would grep for a function that exists nowhere) — they answer "which chunk is current," which is
# build-plan Status parsing, and keeping the derivation here made it reachable
# only by this module's consumer (the defect recurred at two others: BLD-7K3Q,
# SCN-4H9T). This module now reaches it through `buildplan_refs.resolve_chunk_progress`
# like every other consumer — `infer_mode` calls that directly.


class ChunkModeRead(NamedTuple):
    """What reading a chunk's ``**Critic mode:**`` field found.

    Two fields because ``None`` alone cannot carry the difference that matters:
    *this chunk declares no mode* and *this plan could not be read* both mean
    "no override", but only the second means inference is working from a plan it
    cannot trust. Collapsing them sends an unreadable plan down rule 4 to
    ``chunk`` with a rationale that never mentions the plan — the silent
    demotion CRT-3M8Q exists to prevent, arriving by a different door.

    ``unreadable`` is prose naming why, for the rationale string; ``None`` when
    the plan read fine.
    """

    mode: str | None
    unreadable: str | None


def _critic_mode_for_chunk(
    prawduct_dir: Path, chunk_id: str | None, plan_path: Path | None = None
) -> ChunkModeRead:
    """Return ``chunk_id``'s declared mode and whether its plan could be read.

    Finds that chunk's ``### Chunk <id>:`` detail section and reads its
    ``- **Critic mode:** <value>`` field. Returns the short-token value
    only when it is one of the recognized modes; an absent, blank, or
    unrecognized value yields ``ChunkModeRead(None, None)`` (fall through to inference rather
    than honoring a typo as a mode override — same fail-open-to-inference
    posture the methodology's "optional field" contract implies).

    ``chunk_id`` is resolved by the caller via
    ``buildplan_refs`` — git-aware on a views-enabled feature branch
    (CRT-7B4M), otherwise the first ``- [ ]`` chunk. Section discovery is
    the shared ``buildplan_refs._chunk_section_lines`` walker: name-anchored
    on ``### Chunk <id>:`` with leading-zero tolerance, fenced code blocks
    skipped, stop at the next sibling chunk or top-level section. A plan carrying a chunk heading that walker cannot read yields
    ``ChunkModeRead(None, <reason>)`` instead, and the caller escalates on it.
    """
    if chunk_id is None:
        return ChunkModeRead(None, None)

    # ``plan_path`` is the plan `infer_mode` resolved for this branch; the
    # pointer is the fallback. Reading a different plan here than the one the
    # chunk id came from is how a chunk's declared mode gets read off the wrong
    # file.
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        # No plan at all is not an unreadable plan: rule 4 already grounds its
        # choice on the plan's absence and says so, so there is nothing here that
        # inference does not already know.
        return ChunkModeRead(None, None)
    try:
        # Explicit UTF-8 with the same except-set as every other build-plan
        # reader. `infer_mode` reads the plan TWICE — here and through
        # `buildplan_refs.resolve_chunk_progress` — so a locale codec here made
        # one function disagree with itself about whether the plan decodes.
        # `UnicodeDecodeError` is a `ValueError`, so a bare `except OSError`
        # let it escape past a caller that has no guard.
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ChunkModeRead(None, f"{plan_path.name} could not be read ({exc})")

    section = buildplan_refs._chunk_section_lines(content, chunk_id)
    # The same gate the deliverable and `Type:` readers apply. Reading the field
    # anyway is not safe: a section whose end was never detected runs on into the
    # next chunk, so the first `**Critic mode:**` in it can belong to a different
    # one — and this field OVERRIDES inference, so a `chunk` picked up from a
    # neighbour silently downgrades a plan-mandated `final`.
    #
    # But declining is not safe either, which is why the gap is REPORTED rather
    # than swallowed. A bare `None` here means "no override", and inference then
    # walks down to rule 4 and picks `chunk` — narrower than the `final` the
    # unreadable plan might have mandated, with a rationale that never says the
    # plan could not be read. That is CRT-3M8Q's silent demotion arriving through
    # the gate meant to prevent it. The caller escalates instead.
    # Only the UNTRUSTWORTHY half escalates. `chunk_section_gap` also refuses a
    # chunk that simply has no detail section in a plan that reads perfectly —
    # an ordinary shape (a Status roster whose later chunks are not written up
    # yet), where the plan states no mode and inference is exactly right to
    # proceed. Escalating that would turn every not-yet-detailed chunk into a
    # `final`. What must not proceed silently is a plan carrying a heading
    # nothing can parse, because then the field this function did not find may
    # exist under it, and the section that did resolve may not be its own.
    unparsed = buildplan_refs.unparsed_chunk_heading_reason(section)
    if unparsed:
        return ChunkModeRead(None, unparsed)
    if buildplan_refs.chunk_section_gap(chunk_id, section):
        return ChunkModeRead(None, None)
    for _line_num, line in section.lines:
        m = _BUILD_PLAN_CRITIC_MODE_RE.match(line)
        if m:
            token = m.group(1)
            return ChunkModeRead(token if token in _VALID_ARG_MODES else None, None)
    return ChunkModeRead(None, None)
