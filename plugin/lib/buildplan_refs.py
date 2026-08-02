"""Build-plan reference parsing + trivial-change classification for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 3) — the build-plan
parsing cluster: it reads the active build plan's Status section and per-chunk
sections (file-path refs, ``Type:`` declaration, ``Trivial because:`` rationale)
and classifies a single file change against the ``Type: trivial`` / doc-only
file-set bounds. Parsing + path inspection, plus read-only ``git log`` /
``git rev-list`` queries where "which chunk is current" cannot be answered from
the file alone — no git mutation, no network.

Depends on its lib siblings ``gitstate`` (for ``_is_metadata_path``), ``core``
(``resolve_build_plan_path``, ``read_bool_yaml_key``), ``coverage``
(``_resolve_base_branch``) and ``views`` (the canonical frontmatter ``scope:``
reader) plus the stdlib — still a clean DAG node, since ``coverage`` and
``views`` each depend only on ``core``. The hook's inline build-plan-resolution
mirror (``_resolve_build_plan_path``) stays in the hook for its import-light hot
path; this module is a lib citizen and reaches the canonical resolver in
``lib.core`` directly, exactly as ``critic_mode`` and ``views`` do.

Every read of the plan — here and in every other module that reads it — is
explicitly UTF-8, and every guarded read catches ``UnicodeDecodeError`` beside
``OSError``. Both axes are pinned by
``tests/preferences/test_build_plan_decoding.py``. The
plan is markdown authored by a model or a human (em dashes, arrows,
box-drawing), and which of its readers can decode it must not depend on the
operator's locale. The divergence this rule exists to prevent is not a decode
failure but a DISAGREEMENT: readers of the same file on different codecs, with
different except-sets, answering differently about whether it parses. It was
found three review rounds running — first six of seven reads in this module,
then two more outside it, one of them inside a function that reads the plan
twice — which is why the rule is now a pin rather than a convention.

``_parse_build_plan_status`` was reassigned here from the briefing cluster (it is
build-plan parsing, not briefing assembly) — that reassignment turns the hook's
concern clusters into an acyclic dependency graph (STH-9V4K constraint 2). The
hook calls these lazily via ``_buildplan_refs()``, keeping its top level lib-free.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from . import gitstate
from .core import read_bool_yaml_key, read_str_yaml_key, resolve_build_plan_path
from .coverage import _resolve_base_branch

# `lib.views` is a HEAVY_SUBMODULE and is imported lazily, inside the one
# function that needs it (see `_plan_description_fallback`). Unlike `ledger`'s
# identical call — where the cost was hypothetical — this module IS the hot
# path: `briefing` and `gates` both import it at module scope, so a
# module-scope `from .views import ...` here bills every SessionStart and every
# Stop for a parse that most of them never use.


def _iter_status_section_lines(content: str):
    """Yield stripped lines inside the build plan's ``## Status`` section.

    The one canonical Status-section walk (BLD-6Q1N): starts after a line that
    is exactly ``## Status``, stops at the next ``## `` heading, and skips
    HTML-comment spans (``<!-- ... -->``, multi-line). This skeleton was
    previously copied in five readers across ``buildplan_refs`` / ``gates`` /
    ``critic_mode``; all of them now fold onto this generator. (The index-based
    Status *rewriter* in ``lib/views.py`` is deliberately separate — it splices
    lines back into the file, so it needs positions, not a reader's view.)
    """
    in_status = False
    in_comment = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Status":
            in_status = True
            continue
        if not in_status:
            continue
        if stripped.startswith("## ") and stripped != "## Status":
            break
        if "<!--" in stripped:
            in_comment = True
        if "-->" in stripped:
            in_comment = False
            continue
        if in_comment:
            continue
        yield stripped


def _iter_status_section_items(content: str):
    """Yield ``(checked, text)`` for each ``- [ ]`` / ``- [x]`` Status item."""
    for stripped in _iter_status_section_lines(content):
        if stripped.startswith("- [ ]"):
            yield False, stripped[5:].strip()
        elif stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            yield True, stripped[5:].strip()


# Build-plan chunk id extraction — the two supported forms:
#   "### Chunk 02: Name"            (H3, colon — the template default)
#   "## Chunk 2 (RES-K3QP) — Name"  (H2, optional "(ID)", en/em dash — research plans)
# The id is the first whitespace-delimited word after "Chunk", and it MUST be
# followed by a separator (``: — – - (``) or end-of-line — so a notes heading
# like "### Chunk 2 build-session decisions" is NOT mistaken for chunk 2's
# deliverable heading. Leading zeros are tolerated downstream ("2" matches
# "### Chunk 02:"). Previously only the colon form parsed, so an em-dash heading
# silently disabled Goal-2 ref verification and per-chunk mode scoping for the
# whole plan.
# `**` closes a bolded label (`**Chunk A** — Name`) and so terminates the id
# exactly as `:` or an em-dash does. It is in the SEPARATOR set, and `_CHUNK_BOLD`
# allows the opening `**`, because `views.CHUNK_LINE_RE` — the Status-line twin —
# accepts the bold form and the two must agree. When they did not, the failure
# was worse than either alone: the checkbox flipped (views matched) while
# `_chunk_id_from_item_text` returned None (this matcher did not), so the plan
# read as having NO current chunk and `verify-chunk-refs` exited 0 having
# verified nothing. A one-sided widening of a shared contract is not a partial
# fix, it is a new defect.
_CHUNK_ID_SEP = r"\s*(?:[:—–(-]|\*\*|$)"
_CHUNK_BOLD = r"(?:\*\*\s*)?"
_CHUNK_HEADING_RE = re.compile(r"^#{2,3}\s+" + _CHUNK_BOLD + r"Chunk\s+(\w+)" + _CHUNK_ID_SEP)
_CHUNK_ITEM_RE = re.compile(r"^" + _CHUNK_BOLD + r"Chunk\s+(\w+)" + _CHUNK_ID_SEP)


def _chunk_id_from_item_text(text: str) -> str | None:
    """``"Chunk 02: name"`` / ``"Chunk 2 (ID) — name"`` → ``"02"`` / ``"2"``;
    ``None`` for non-chunk items. Accepts the colon (``### Chunk N:``) and the
    em/en-dash + optional ``(ID)`` (``## Chunk N (ID) — name``) forms."""
    m = _CHUNK_ITEM_RE.match(text)
    return m.group(1) if m else None


def _count_build_plan_chunks(
    prawduct_dir: Path, plan_path: "Path | None" = None
) -> tuple[int, int]:
    """Count chunks in the active build plan's Status section.

    Resolves the plan via the ``active_build_plan:`` pointer (falls back to
    ``artifacts/build-plan.md``), so scope-named plans are counted too.
    Returns ``(total, complete)``; ``(0, 0)`` if the plan or its Status section
    is missing or unreadable. The single canonical implementation — both callers
    are in ``lib.gates`` (the end-of-cycle synthesis gate and its sibling); they
    and ``lib.critic_mode`` carried near-duplicate copies until STH-2K8R/BLD-6Q1N.
    ``critic_mode`` no longer calls this at all: it asks
    :func:`resolve_chunk_progress`, which is the one place the checkbox and
    git-derived readings are reconciled.
    """
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return 0, 0
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0, 0
    total = 0
    complete = 0
    for checked, _text in _iter_status_section_items(content):
        total += 1
        if checked:
            complete += 1
    return total, complete


# A commit subject that references a build-plan chunk, e.g. "feat: … (Chunk 03)".
# Capital-C + digits matches the "Chunk NN" commit convention without
# false-matching prose like "10-chunk plan" (CRT-7B4M).
_CHUNK_COMMIT_RE = re.compile(r"Chunk\s+(\d+)")
# Conventional-commit scope: `fix(session-boundary-events): … (Chunk 01)`.
_COMMIT_SCOPE_RE = re.compile(r"^\w+\(([^)]+)\)!?:")
# NOTE: the plan's own `scope:` is read through `views._parse_build_plan_frontmatter_scope`,
# NOT a regex here. A hand-rolled `^scope:\s*(\S+)$` shipped briefly and was wrong in three
# ways the canonical reader already handles: it kept surrounding quotes (so a legal
# `scope: "session-boundary-events"` matched no commit scope, `scoped` came back empty, and
# the filter silently fell through to the unscoped reading — reinstating the very cross-plan
# contamination it was added to stop), it ignored the documented `null`/`~` opt-out, and it
# searched the whole document rather than the frontmatter block. This module's docstring
# already names `views` as the canonical frontmatter reader, and the same bundle deleted
# `ledger`'s inline copy for exactly this reason (ROB-7T2N).


def _commits_ahead_of_base(project_dir: Path, base: str) -> int:
    """Number of commits on HEAD since merge-base with ``base``. ``-1`` on failure."""
    proc = subprocess.run(
        ["git", "rev-list", "--count", f"{base}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return -1
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return -1


def _committed_chunk_ids(
    project_dir: Path, base: str, plan_scope: str | None = None
) -> set[str]:
    """Normalized chunk ids referenced in commit subjects on ``base..HEAD``.

    The branch-robust progress signal for CRT-7B4M: when the build-plan Status
    checkboxes are a non-flipping derived view (``views_enabled`` on a feature
    branch), git commits are the only record of which chunks are done. Counts
    distinct chunk numbers (``Chunk <n>`` in a commit subject), leading-zero-
    normalized to match Status ids. Returns ``set()`` on git failure.

    **Chunk ids are per-plan, so a branch carrying two plans cross-contaminates**
    (SCN-5B8Q review R-2/R-7): a foreign plan's ``(Chunk 02)`` would otherwise
    mark the active plan's chunk 02 complete. ``plan_scope`` — the active plan's
    ``scope:`` frontmatter — restricts the count to commits whose
    conventional-commit scope matches.

    The filter is applied **only when some commit carries the plan's scope** —
    that condition, precisely, and not "when the scoped commits yield ids." Scope
    tags are a convention, not a guarantee: on this very branch the continuity
    plan's commits say ``session-continuity`` while its frontmatter says
    ``session-handoff-continuity``, so a strict always-on filter would silently
    erase that plan's entire git signal and fall back to all-unchecked boxes —
    replacing cross-contamination with a different wrong answer. When no commit
    carries the plan's scope we therefore keep the pre-existing unscoped reading.

    The two conditions come apart exactly where the defect lives: a plan whose
    commits DO carry its scope but that has not landed a ``(Chunk NN)`` subject
    yet yields an empty id set, and falling through there would re-import a
    sibling plan's ids. Once this plan is identifiable in the log, its empty id
    set is the truthful answer — git knows nothing about its chunks — and the
    caller degrades to the checkbox reading.

    Bounding by the plan's own declared chunk ids needs no code here: the caller
    walks Status items and asks whether each item's id is in this set, so an id
    that belongs to no Status item is never consulted.
    """
    proc = subprocess.run(
        ["git", "log", "--format=%s", f"{base}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return set()

    def _ids(subjects: list[str]) -> set[str]:
        out: set[str] = set()
        for subject in subjects:
            for m in _CHUNK_COMMIT_RE.finditer(subject):
                out.add(m.group(1).lstrip("0") or "0")
        return out

    subjects = proc.stdout.splitlines()
    if plan_scope:
        scoped = [
            s for s in subjects
            if (m := _COMMIT_SCOPE_RE.match(s)) and m.group(1).strip() == plan_scope
        ]
        # Discriminate on `scoped`, NOT on the ids it yields. Those differ exactly
        # where the defect lives: a plan whose commits carry the right scope but
        # has not landed a `(Chunk NN)` subject yet yields no ids, and falling
        # through would re-import a sibling plan's chunk ids — the very
        # cross-contamination this filter exists to stop. Returning the empty set
        # is the truthful answer (git knows nothing about this plan's chunks), and
        # the caller already degrades to the checkbox reading on an empty set.
        if scoped:
            return _ids(scoped)
    return _ids(subjects)


def _git_aware_progress(
    project_dir: Path, content: str, total: int
) -> tuple[int, str] | None:
    """Git-derived ``(complete, current_item_text)``, or ``None`` to use checkboxes.

    Applies ONLY when the Status checkboxes can't be trusted as the progress
    signal (CRT-7B4M): (a) ``views_enabled`` (checkboxes derive from
    ``status=shipped`` change-log entries and won't flip until release),
    (b) a base branch resolves and HEAD is ahead of it (a pre-release feature
    branch), and (c) at least one chunk is referenced by a commit since base.
    Returns ``None`` whenever any condition fails — the caller then uses the
    checkbox reading.

    A Status item counts as complete when its box is ``[x]`` **or** it names a
    chunk whose id appears in a commit subject since base. The commit signal
    alone is not enough: on a plan whose earlier chunks shipped in a *prior*
    release, those boxes ARE flipped and their commits are behind the base, so a
    commit-only reading resolves "current" back to an already-shipped Chunk 01 —
    strictly worse than the checkbox fallback this is supposed to never be worse
    than. The union is what makes the promise true; the same union also keeps a
    branch whose commits only partly follow the ``Chunk NN`` convention from
    reading a half-populated set as authoritative.

    The walk covers **every** Status item, not just the chunk-shaped ones. A
    Status section may hold an item that names no chunk (a plain to-do); such an
    item can never be "committed", so it is done iff its box is checked — which
    is precisely the checkbox reading, applied to the items git cannot speak to.
    Walking only the chunk-shaped items instead made "no chunk left" mean
    "nothing left", so a plan with every chunk committed and an unchecked to-do
    beside them read as COMPLETE, retiring a live plan and blanking the
    handoff's work section. That is the same "strictly worse than the checkbox
    fallback" failure the union above exists to prevent, entering by the other
    door: not from the wrong signal, but from an incomplete domain.

    This is the ONE implementation of git-derived chunk progress. It shipped in
    ``lib.critic_mode`` for the ``infer-critic-mode`` consumer alone; the same
    defect then recurred at ``verify-chunk-refs`` (BLD-7K3Q) and at the session
    handoff, so it now lives here — with the rest of the build-plan Status
    parsing — and every consumer reaches "which chunk is current" through
    :func:`resolve_chunk_progress`.

    Every git touchpoint is guarded. ``_resolve_base_branch``, ``rev-list`` and
    ``git log`` all handle a non-zero return code but none catches a *raise*
    (absent git binary → ``OSError``; the ``timeout=`` → ``TimeoutExpired``),
    and the only catch above this is the parser's broad-except, which would
    return ``{}`` — turning a transient git hiccup into "there is no build
    plan," blanking the handoff's work section and quietly relaxing gates. The
    correct degradation is to the checkbox reading, so the promise is kept here,
    at the function that makes it, rather than at each of its callers.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if total <= 0:
        return None
    if not read_bool_yaml_key(prawduct_dir / "project-state.yaml", "views_enabled"):
        return None
    try:
        base, _ = _resolve_base_branch(project_dir)
        if not base:
            return None
        if _commits_ahead_of_base(project_dir, base) <= 0:
            return None
        # Canonical reader: strips quotes, honours the `null`/`~` opt-out, and is
        # bounded to the frontmatter block. Both `(True, None)` (explicit opt-out)
        # and `(False, None)` (no key) yield None here, which correctly means
        # "do not scope-filter" — the same unscoped reading as before the filter.
        from .views import _parse_build_plan_frontmatter_scope  # noqa: PLC0415 — heavy; see the module-header note

        _present, plan_scope = _parse_build_plan_frontmatter_scope(content)
        committed = _committed_chunk_ids(project_dir, base, plan_scope)
    except (OSError, subprocess.SubprocessError):
        return None
    if not committed:
        return None

    def _done(checked: bool, text: str) -> bool:
        if checked:
            return True
        cid = _chunk_id_from_item_text(text)
        return cid is not None and (cid.lstrip("0") or "0") in committed

    items = list(_iter_status_section_items(content))
    complete = sum(1 for checked, text in items if _done(checked, text))
    current = next((text for checked, text in items if not _done(checked, text)), "")
    return complete, current


class ChunkProgress(NamedTuple):
    """How far the active build plan has got, and which chunk is current.

    ``current_id`` / ``current_text`` are empty-ish (``None`` / ``""``) when the
    plan has no remaining chunk.

    ``git_derived`` records which of the two readings answered, and
    :func:`degraded_progress_notice` is its production consumer: when the
    git-derived path bails (absent base branch, git failure, a branch not ahead)
    the answer becomes the checkbox reading, and on a ``views_enabled`` repo
    mid-branch that is the reading known to be wrong. It used to become that
    silently. The notice reports it from deliberately-invoked surfaces only —
    most ``git_derived=False`` answers are perfectly normal, so this hot path
    stays quiet.

    ``complete`` is a COUNT of done items, not a positional boundary: done-ness
    is deliberately non-contiguous (see :func:`_git_aware_progress` on why the
    union exists), so slicing a roster by it names the wrong chunks. Callers
    needing "which chunks are done" take the prefix before ``current_id`` **on
    the git-derived reading only** — on the checkbox reading the per-item
    predicate is the ``checked`` flag itself, which is exact, and the prefix
    would under-report a checked item sitting after ``current_id``.
    """

    total: int
    complete: int
    current_id: str | None
    current_text: str
    has_status_items: bool
    git_derived: bool


class ReviewedPlan(NamedTuple):
    """Which build plan a review is actually about, and how that was decided.

    ``path`` is ``None`` when no plan could be resolved at all. ``gap`` carries a
    reason when the resolution is an assumption or a failure, so a caller can
    report it rather than grade a subject it only guessed at; it is ``None`` when
    the answer is grounded.

    The distinction this type exists for: **a chunk id from the dispatch and a
    plan from ``active_build_plan`` are two halves of one question resolved from
    different places, with nothing checking they agree.** When they disagree the
    deliverable check grades a chunk of a plan the diff has nothing to do with,
    and answers zero — which is the shape of a clean result.
    """

    path: Path | None
    rel: str | None
    scope: str | None
    source: str  # "scope-named" | "active-pointer" | "none"
    gap: str | None


def _scope_plan_map(prawduct_dir: Path) -> dict[str, Path]:
    """``{frontmatter scope: plan path}`` over this repo's artifacts directory.

    Lazy import: ``lib.views`` is a HEAVY_SUBMODULE. **Two paths ask this**:
    review dispatch, and — since the Stop hook began resolving its gate plan
    from the branch — every session end where a build plan and changes both
    exist. So the cost moved onto a hot path from one already measured in
    minutes. Lazy still earns its keep: sessions that skip the gate block skip
    this entirely.

    **Nothing memoizes the scan, and the Stop path runs it twice** — once via
    :func:`infer_scope_from_branch`, once inside :func:`resolve_reviewed_plan`.
    The import is cached by the module system; the recursive walk of
    ``artifacts/`` and its per-file frontmatter parse are not. Stated as a count
    rather than a duration deliberately: a millisecond figure here would be a
    machine-held fact hand-copied into prose that ships to consumer repos whose
    ``artifacts/`` is nothing like this one's — the drift ``record_lint``'s
    suite-total tripwire exists to catch, one file over. Whether the second walk
    is worth caching is open; the count is what a reader needs to decide.
    """
    from . import views  # noqa: PLC0415 — lazy; views is a HEAVY_SUBMODULE

    return views.build_scope_to_plan_map(prawduct_dir / "artifacts")


def resolve_branch_plan(project_dir: Path, prawduct_dir: Path) -> ReviewedPlan:
    """**The** answer to "which plan is this branch building" — infer the scope
    from the branch, then resolve the plan it names.

    The one entry point for that composite. Written out longhand it is
    ``resolve_reviewed_plan(pd, prd, infer_scope_from_branch(pd, prd))``, which
    appeared at every caller and scanned ``artifacts/`` **twice** per resolution
    — once to match the branch name, once to resolve the match. Building the map
    here and handing it to both halves makes it one scan, and gives the composite
    a name so the next consumer asks rather than re-assembles. A repeated
    two-call composite is how two callers end up answering the same question
    differently, which is the defect class this module's plan resolution exists
    to close.
    """
    known = _scope_plan_map(prawduct_dir)
    scope = infer_scope_from_branch(project_dir, prawduct_dir, known=known)
    return resolve_reviewed_plan(project_dir, prawduct_dir, scope, known=known)


def infer_scope_from_branch(
    project_dir: Path, prawduct_dir: Path, known: "dict[str, Path] | None" = None
) -> str | None:
    """The scope this branch is building, or ``None`` when it cannot be shown.

    A **match against declared data, never a guess**: the branch name's last
    segment (and the whole name, for branches without a prefix) is accepted only
    when some build plan under ``artifacts/`` declares it as a frontmatter
    ``scope:``. ``fix/backlog-burndown`` → ``backlog-burndown`` because
    ``build-plan-backlog-burndown.md`` says so; ``develop`` → ``None`` because
    nothing declares it.

    Two narrowings, and the honest statement of what remains:

    - A branch matching no declared scope infers nothing, leaving every caller
      on the behaviour it had before.
    - A matched plan whose Status is **entirely checked** is rejected. Those
      boxes flip at release, so an all-checked plan has shipped, and a branch
      named after a shipped scope is far more likely to be new work near old
      code than a resumption of finished work. Without this, every one of the
      dozens of released plans a long-lived repo accumulates is a live target.

    **What is still possible, stated plainly:** a branch whose name matches an
    *unfinished* plan it is not actually building will be attributed to that
    plan. Nothing here can tell those apart — a name is the only signal — so the
    residual case is real and the remedy is explicit ``--scope``. This is
    narrower than "can only add, never redirect," which is true of the no-match
    case only.
    """
    branch = gitstate.current_branch(project_dir)
    if not branch:
        return None  # detached HEAD — nothing to read a scope from
    candidates = [branch]
    if "/" in branch:
        candidates.append(branch.rsplit("/", 1)[1])
    if known is None:
        known = _scope_plan_map(prawduct_dir)
    for candidate in candidates:
        plan_path = known.get(candidate)
        if plan_path is not None and _has_unfinished_chunk(plan_path):
            return candidate
    return None


def _has_unfinished_chunk(plan_path: Path) -> bool:
    """True when ``plan_path``'s Status section still holds an unchecked chunk.

    The liveness signal for :func:`infer_scope_from_branch`. Read from the
    checkboxes deliberately rather than through the git-aware resolver, which
    would answer the different question "which chunk is being built right now".

    **The signal is sharp under ``views_enabled`` and blunt elsewhere, and the
    difference is worth knowing.** Where views are enabled the boxes flip at
    *release*, so "all checked" means shipped — exactly the question being asked.
    Everywhere else the boxes flip per chunk, so a plan reads finished from the
    moment its last chunk is ticked, which is typically before the branch merges.
    In that window the branch stops matching and every caller falls back to the
    ``active_build_plan`` pointer: attribution, ``plan_graded``, and the Stop
    hook's ``Type:`` carveouts. That is the behaviour those callers had before
    branch inference existed, so the window is a *lapse of the improvement*, not
    a new defect — but it lands at end-of-plan, which is exactly when a
    `cumulative` review and the last gate run happen. Narrowing it needs a
    liveness signal a non-views plan does not carry; ``--scope`` is the remedy
    meanwhile.

    A plan with no Status items at all reads as unfinished — an unparseable plan
    is not evidence of completion, and the caller's fallback (the pointer) is no
    better an answer for it.
    """
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    items = list(_iter_status_section_items(content))
    if not items:
        return True
    return any(not checked for checked, _text in items)


def resolve_reviewed_plan(
    project_dir: Path,
    prawduct_dir: Path,
    scope: "str | None",
    known: "dict[str, Path] | None" = None,
) -> ReviewedPlan:
    """Resolve the build plan a review is about, preferring the reviewed SCOPE's
    plan over the ``active_build_plan`` pointer.

    The pointer answers "which plan is in progress in this repo," which is not
    the same question as "which plan is this review of" — and on a repo running
    several plans across worktrees the two legitimately differ. The pointer is
    then *correct* and still the wrong answer here, which is why this resolves
    around it rather than asking anyone to repoint it.

    Three outcomes:

    - **scope names a plan** → that plan, ``gap=None``. The pointer is not the
      subject and needs no comment; ``rel`` names the file that was graded.
    - **scope names no plan** → ``path=None`` and a ``gap``. Falling back to the
      pointer here is precisely the silent grade of an unrelated plan, so the
      caller must report instead of answering.
    - **no scope** → the pointer's plan, with a ``gap`` stating the assumption.
      A plan-less repo yields ``path=None`` and no gap: that is an absence, not
      a failure.
    """
    if scope and scope.strip():
        scope = scope.strip()
        match = (known if known is not None else _scope_plan_map(prawduct_dir)).get(scope)
        if match is None:
            return ReviewedPlan(
                None,
                None,
                scope,
                "none",
                f"the dispatch names scope {scope!r} but no build plan under "
                "artifacts/ declares it — grading the active_build_plan pointer's "
                "plan would grade a different subject",
            )
        return ReviewedPlan(match, _repo_rel(prawduct_dir, match), scope, "scope-named", None)

    pointer = resolve_build_plan_path(prawduct_dir)
    if not pointer.is_file():
        return ReviewedPlan(None, None, None, "none", None)
    rel = _repo_rel(prawduct_dir, pointer)
    # The assumption is only worth reporting where it could be WRONG and the
    # reader has a remedy: two or more plans declaring scopes means the pointer
    # picked one of several, and `--scope` would have said which. Below that
    # there is nothing to have chosen differently, and a note fires on every
    # review of every such repo — which is how a channel stops being read
    # (`nonfunctional-requirements.md` § Direction: a control that fires
    # repeatedly with no yield is removed by default).
    ambiguous = len(known if known is not None else _scope_plan_map(prawduct_dir)) > 1
    return ReviewedPlan(
        pointer,
        rel,
        None,
        "active-pointer",
        (
            f"graded {rel}, resolved from the active_build_plan pointer because "
            "the dispatch carried no scope — the pointer names the plan in "
            "progress in this repo, which need not be the plan this branch is "
            "building, and this repo declares several"
        )
        if ambiguous
        else None,
    )


def _repo_rel(prawduct_dir: Path, path: Path) -> str:
    """``path`` relative to the repo root, or its bare name when it lies outside."""
    try:
        return str(path.relative_to(prawduct_dir.parent))
    except ValueError:
        return path.name


def resolve_chunk_progress(
    project_dir: Path, plan_path: "Path | None" = None
) -> ChunkProgress:
    """The ONE answer to "how far along is the plan, and which chunk is current."

    Two readings exist — the Status checkboxes, and the git-derived one for
    ``views_enabled`` repos where those checkboxes only flip at release — and the
    *precedence between them* is what this function owns. Moving the three git
    helpers into this module was not enough on its own: while `infer_mode` still
    wrote "try git, else checkboxes" for itself, the composition existed twice,
    and a third progress signal would make the two diverge again with the
    consolidation pins still green. That duplication is the exact shape that let
    the original defect reach three consumers.

    Every consumer — :func:`_parse_build_plan_status` and so the handoff, the
    briefing, ``verify-chunk-refs``, and ``critic_mode.infer_mode`` — resolves
    through here.

    ``plan_path`` overrides which plan is read. It defaults to the
    ``active_build_plan`` pointer, so every existing caller is unchanged; mode
    inference passes the branch's own plan when :func:`resolve_reviewed_plan`
    found one, so "which chunk is current" and "which plan the record names"
    cannot answer about two different files.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return ChunkProgress(0, 0, None, "", False, False)
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ChunkProgress(0, 0, None, "", False, False)
    return _resolve_chunk_progress_from(project_dir, content)


def _resolve_chunk_progress_from(project_dir: Path, content: str) -> ChunkProgress:
    """:func:`resolve_chunk_progress` against already-read plan content — so the
    parser below resolves progress without re-reading the file it already holds."""
    items = list(_iter_status_section_items(content))
    total = len(items)
    checkbox_complete = sum(1 for checked, _t in items if checked)
    checkbox_current = next((t for checked, t in items if not checked), "")

    git_progress = _git_aware_progress(project_dir, content, total)
    if git_progress is None:
        return ChunkProgress(
            total,
            checkbox_complete,
            _chunk_id_from_item_text(checkbox_current),
            checkbox_current,
            total > 0,
            False,
        )

    complete, current_text = git_progress
    return ChunkProgress(
        total,
        complete,
        _chunk_id_from_item_text(current_text),
        current_text,
        total > 0,
        True,
    )


# Stable token on every degraded-reading emission, so occurrences can be counted
# by whoever is deciding whether this control still earns its place (the
# proportionality norm: a finding that is printed and forgotten can never be
# retired on evidence). **Do not reword it** — that instruction stands on its own
# and needs no mechanism to obey. No counter is claimed here: the notice reaches
# the agent transcript, which lives outside this repo, so asserting a specific
# counting command would be a mechanism claim nothing in the tree implements.
DEGRADED_PROGRESS_TOKEN = "degraded-chunk-reading"


def degraded_progress_notice(project_dir: Path) -> str | None:
    """A notice when the chunk reading in force is the one known to be wrong.

    Closes the gap :class:`ChunkProgress` names: when the git-derived path bails
    (no base branch, git failure, a branch not ahead) the answer silently
    becomes the checkbox reading, and on a ``views_enabled`` repo mid-branch
    that is the reading known to be wrong. Nothing told anyone (#327).

    Fires only when all three hold:

    * ``views_enabled`` — the Status checkboxes are a derived view that does not
      flip until release, so mid-branch they read all-incomplete;
    * a plan with a Status roster was actually read (``has_status_items``), so
      "there is no plan" is never reported as a degraded reading;
    * the git-derived path bailed (``git_derived`` false).

    Returns ``None`` otherwise. **Reporting the ``views_enabled``-unset case
    would be pure noise** — there the checkbox reading is authoritative and a
    ``git_derived=False`` answer is simply correct, which is most of them.

    Deliberately NOT emitted from :func:`_git_aware_progress`, which is on the
    SessionStart/Stop hot path: a per-invocation diagnostic there spends
    wall-clock the nonfunctional budget protects and reaches an audience that
    cannot act on it. Callers are deliberately-invoked surfaces only.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if not read_bool_yaml_key(prawduct_dir / "project-state.yaml", "views_enabled"):
        return None
    progress = resolve_chunk_progress(project_dir)
    if not progress.has_status_items or progress.git_derived:
        return None
    current = progress.current_text or "(none — plan reads complete)"
    return (
        f"WARNING: {DEGRADED_PROGRESS_TOKEN}: views_enabled is set, so this "
        f"plan's ## Status checkboxes do not flip until release — and the "
        f"git-derived reading bailed (no base branch resolved, git unavailable, "
        f"or HEAD not ahead of base), so chunk progress fell back to those "
        f"checkboxes. Reporting {current!r} as current; on a feature branch that "
        f"is likely the FIRST chunk rather than the live one. Pass --chunk "
        f"explicitly to anything that grades a chunk."
    )


def _plan_description_fallback(plan_path: Path, content: str) -> str:
    """Name the plan when it carries no ``# Build Plan`` H1.

    The frontmatter-style plans this repo writes open with a ``---`` block and a
    ``## Requirements Confidence`` heading — no H1 at all. Requiring one made
    ``description`` empty, and an empty description is not a cosmetic loss: it
    is the sole key gating the handoff's Work In Progress section, so the whole
    section vanished from a live four-chunk plan's handoff. Fall back to the
    frontmatter ``scope:``, then to the filename with the conventional
    ``build-plan-`` prefix stripped, so the section can never silently vanish.
    """
    from .views import _parse_build_plan_frontmatter_scope  # noqa: PLC0415 — heavy; see the module-header note

    _present, scope = _parse_build_plan_frontmatter_scope(content)
    if scope:
        return scope
    return plan_path.stem.removeprefix("build-plan-") or plan_path.stem


def _parse_build_plan_status(
    project_dir: Path, plan_path: "Path | None" = None
) -> dict[str, str]:
    """Parse work context from the active build plan's Status section.

    Returns dict with keys matching _parse_wip output:
    description, size, type, current_chunk, context, governance_level.
    Returns empty dict if no build plan or no Status section.

    Takes ``project_dir`` (not ``.prawduct/``) because ``current_chunk`` is not
    always answerable from the file: on a ``views_enabled`` repo the checkboxes
    are a derived view that only flips at release, so mid-branch every box reads
    ``- [ ]`` and "first unchecked" reports Chunk 01 forever. Resolution goes
    through :func:`_git_aware_progress`, which needs the repo. The explicit
    parameter is the point — every caller can see that this reads git, which the
    three separate local patches of the same defect could not.

    ``plan_path`` overrides which plan is read, defaulting to the
    ``active_build_plan`` pointer (see :func:`resolve_chunk_progress`).
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return {}
    try:
        content = plan_path.read_text(encoding="utf-8")
        result: dict[str, str] = {}

        # Extract title from header: "# Build Plan — Title (date)"
        for line in content.splitlines():
            if line.startswith("# Build Plan"):
                title = line.lstrip("# ").removeprefix("Build Plan").strip()
                if title.startswith("—") or title.startswith("-"):
                    title = title.lstrip("—- ").strip()
                # Remove trailing date in parens
                if title.endswith(")") and "(" in title:
                    title = title[:title.rfind("(")].strip()
                if title:
                    result["description"] = title
                break
        if not result.get("description"):
            result["description"] = _plan_description_fallback(plan_path, content)

        # Extract Size and Type from metadata line: **Size**: X | **Type**: Y
        for line in content.splitlines():
            if "**Size**:" in line:
                for segment in line.split("|"):
                    segment = segment.strip()
                    if segment.startswith("**Size**:"):
                        result["size"] = segment.removeprefix("**Size**:").strip()
                    elif segment.startswith("**Type**:"):
                        result["type"] = segment.removeprefix("**Type**:").strip()
                    elif segment.startswith("**Governance**:"):
                        result["governance_level"] = segment.removeprefix("**Governance**:").strip()
                break

        # Which chunk is current — resolved by the one owner of that question,
        # checkbox-wise or git-wise as the repo demands. Note it can come back
        # EMPTY on a plan that has items: every chunk done means there is no
        # current chunk, which is what stops a finished plan being reported as
        # active work.
        progress = _resolve_chunk_progress_from(project_dir, content)
        if progress.current_text:
            result["current_chunk"] = progress.current_text
        if progress.has_status_items:
            result["_has_status_items"] = "true"

        # The Context BLOCK runs from the first `Context:` line to the end of the
        # Status section, not to the end of that physical line. `building.md`
        # calls Context "the cross-session handoff" and plans write it as several
        # paragraphs; reading one line truncated it at the first newline. Block
        # semantics also settle the multiple-`Context:` question by dissolving
        # it: the FIRST `Context:` opens the block and a later one is simply text
        # inside it, so neither wins and nothing is dropped.
        context_lines: list[str] = []
        in_context = False
        for stripped in _iter_status_section_lines(content):
            if (
                stripped.startswith("- [ ]")
                or stripped.startswith("- [x]")
                or stripped.startswith("- [X]")
            ):
                # A chunk item after Context ends the block — Context is
                # conventionally last, but a plan that interleaves them should
                # not swallow its own checklist into the handoff.
                in_context = False
                continue
            if not in_context and stripped.startswith("Context:"):
                in_context = True
                context_lines.append(stripped.removeprefix("Context:").strip())
                continue
            if in_context:
                context_lines.append(stripped)

        context = "\n".join(context_lines).strip()
        if context:
            result["context"] = context

        return result
    except Exception:  # prawduct:allow prawduct/broad-except -- build plan parsing is best-effort
        return {}


def build_plan_is_complete(status: dict[str, str]) -> bool:
    """Does this parsed Status say the plan's chunks are all done?

    The done-predicate, in one place. A Status section with items but no current
    chunk means every chunk is complete; that is a *finished* plan, not active
    work. ``staleness_scan`` had this logic inline and the handoff's
    ``_get_active_work`` read the identical parse without it, so a completed plan
    was stamped as the next session's ``**Task**`` — the two now share this.

    A plan with no Status items at all is NOT complete (there is nothing to be
    complete); callers distinguish that case via ``_has_status_items``.
    """
    return bool(status.get("_has_status_items")) and not status.get("current_chunk")


_BUILD_PLAN_PATH_RE = re.compile(r"`([^`\s]+)`")
_BUILD_PLAN_NEW_QUALIFIER_RE = re.compile(r"\bnew\s+`([^`\s]+)`")
# #224(b): `new` is also an ordinary English adjective. Narrative prose ABOUT a
# file — a `Context:` paragraph recording that a chunk "added new `x.py`" — is
# not a declaration that THIS chunk creates it, but the qualifier matched any
# `new` before any backticked token anywhere in the section, so one such
# sentence silently exempted a real path from verification for the whole chunk.
#
# **The item prescribed scoping to a Deliverables list item; that is too narrow
# and this departs from it deliberately.** Real plans in this repo declare
# creations outside Deliverables as a matter of course —
# `build-plan-api-design.md:177` names a new test file in `- **Tests:**` and
# `:109` names one in acceptance criteria. Honouring the qualifier only inside
# Deliverables would turn every one of those into a false missing-ref, which is
# the failure the exemption exists to prevent. The distinction that actually
# separates the two cases is STRUCTURAL rather than positional: a declaration is
# a list item (`- new \`x\``, `1. new \`x\``), while the adjectival use that
# motivated the item lives in running paragraphs. Scoping to list items excludes
# the prose without breaking the fields plans really use, and #224(a) — the
# expiry below — is what actually catches a file the chunk promised and skipped.
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s)")
# A list item does not end at its first newline. This repo's plans wrap
# deliverable bullets across several lines, and the `new `path`` declaration
# routinely lands on a CONTINUATION line rather than the one carrying the
# bullet marker. Matching per-line therefore dropped the exemption for the
# dominant declaration form and would have produced BLOCKING `missing-ref:`
# findings on open chunks — a worse failure than the one #224(b) set out to fix.
# A continuation is a non-blank line that starts no new item and is not a
# column-0 field; a blank line or a column-0 non-list line closes the block.
_PLAN_FIELD_RE = re.compile(r"^\S")
# A trailing `:<line>`, `:<line>:<col>`, or `:<line>-<line>` on a backticked
# token is a code-location citation (`lib/critic_mode.py:452`, `lib/foo.py:5-8`,
# the editor-style `lib/foo.py:12:34`), not part of the filename.
_BUILD_PLAN_LINE_SUFFIX_RE = re.compile(r":\d+(?::\d+)?(?:-\d+)?$")
# Per-chunk Type declaration (v1.4 F6 — proportional Critic via chunk type).
# Matches `- **Type:** <token>` or `**Type:** <token>` as a list item; trailing
# parenthetical prose is allowed and ignored.
_BUILD_PLAN_TYPE_RE = re.compile(r"^[\s\-\*]*\*\*Type:\*\*\s*([A-Za-z][\w\-]*)")
# v1.5 Chunk 04 — `trivial` joins the allowed set. File-set bounds (no
# edits under skills/, methodology/, templates/; no CLAUDE.md edit; no
# test deletion; no new files) + required `**Trivial because:**`
# rationale are enforced structurally; semantic-fit is Critic Goal 3 in
# Chunk 05. Size is unbounded — trivial is a semantic claim, not a LOC
# metric.
_BUILD_PLAN_ALLOWED_TYPES = frozenset(
    {"code", "doc-only", "cleanup", "designer-handoff", "cumulative-final", "trivial"}
)
# `**Trivial because:** <rationale>` — first line; continuation lines (no
# list-item / heading prefix) are joined onto the rationale until the next
# field. Empty after the colon → missing-rationale.
_BUILD_PLAN_TRIVIAL_RATIONALE_RE = re.compile(
    r"^[\s\-\*]*\*\*Trivial because:\*\*\s*(.*)$"
)

# Git branch/ref names (`feature/backlog-service-relayout`, `origin/develop`) are
# backticked identifiers that contain `/` but name a branch, not a file — the same
# "contains `/`, isn't a path" family as the slash-command / URL carveouts in
# `_looks_like_file_path`. A token whose first segment is one of these prefixes and
# whose final segment carries no extension is a ref to skip, not a missing file.
# `refs` is the ref NAMESPACE rather than a branch prefix — `refs/tags/v3.2.1`,
# `refs/heads/develop`, `refs/remotes/origin/main` — and a release plan backticks
# it for exactly the same reason it backticks a branch. It belongs to this set on
# the same test: it names something in git, not on disk. A repo-root directory
# literally called `refs/` would be shadowed, which is why the extension guard
# below still applies (`refs/foo.py` stays checked).
#
# #333: the original set covered git-flow only, so every consumer on
# Conventional-Commits branch naming (`feat/…`, `chore/…`) or with a dependency
# bot got a spurious BLOCKING `missing-ref:` for a branch named in plan prose —
# `missing-ref:` is BLOCKING in `skills/critic/review-protocol.md`, so this
# failed a review on the branch name itself.
#
# **The shape-rule alternative was evaluated and rejected**, though the item and
# the plan both proposed it as the better route. "A token is a path only if its
# final segment carries an extension-shaped suffix" would drop the guessing
# entirely — but it also stops verifying real extensionless paths, and this
# repo's single most-cited path is one: `plugin/bin/prawduct-hook`. Trading a
# spurious-finding class for a missed-finding class on the most-referenced file
# in the tree is the wrong direction, so the allowlist stays and grows.
_GIT_REF_PREFIXES = frozenset(
    {
        # git-flow
        "feature", "fix", "hotfix", "release", "bugfix", "support",
        # remotes and raw refs
        "origin", "upstream", "refs",
        # Conventional-Commits branch naming, as enumerated by #333. Deliberately
        # NOT `docs`, `test`, `build` or `style`: those are plausible top-level
        # DIRECTORY names, and every prefix added here stops an extensionless
        # token under it from being verified (`docs/requirements` would go
        # unchecked). The set is entries whose collision risk with a real
        # directory is near zero — `ci` and `perf` are the weakest two and are
        # here because the item named them.
        "feat", "chore", "refactor", "perf", "ci", "wip",
        # dependency bots
        "dependabot", "renovate",
    }
)

# "Carries an extension" is not "contains a dot". A version-numbered branch —
# `release/v3.2.0`, `feature/v3.2.0-c02-adapter-safety` — contains dots and is
# still a ref, so a dot-presence test makes the carveout above inert for exactly
# the branches a release cuts, and `verify-chunk-refs` then emits a BLOCKING
# `missing-ref:` for a branch named in plan prose. A file extension is short and
# alphabetic (`py`, `md`, `tsx`); the trailing dot-part of a version is not
# (`v3.2.0` -> `0`, `v3.2.0-c02-adapter-safety` -> `0-c02-adapter-safety`). Test
# the SUFFIX SHAPE so `feature/foo.py` stays checked while `release/v3.2.0` does not.
_FILE_EXTENSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,7}$")


def _has_file_extension(segment: str) -> bool:
    """True when ``segment`` ends in something shaped like a file extension.

    Requires a non-empty stem, so a dotfile (``.hidden``) is not an extension,
    and an extension-shaped suffix, so ``v3.2.0`` is not one either.
    """
    stem, dot, suffix = segment.rpartition(".")
    return bool(dot) and bool(stem) and bool(_FILE_EXTENSION_RE.match(suffix))


def _looks_like_file_path(token: str) -> bool:
    """A backticked token is a precise file-path reference only when it
    contains ``/`` — i.e. the chunk author wrote a specific relative path.
    Bare filenames in prose (e.g. ``backlog.md``, ``SKILL.md``) are usually
    conceptual references whose actual location varies, so they're not
    verifiable in a useful way.

    Slash-commands (``/prawduct:pr``, ``/prawduct:learnings``, ``/prawduct:critic``) also contain
    ``/`` but are not file paths. Exclude tokens that start with ``/``,
    have no further ``/``, and contain no ``.`` — that shape is a single
    slash-command identifier, not a path.

    Glob patterns written in prose (e.g. ``docs/requirements/*.md`` in a Tests
    bullet) also contain ``/`` but name a *set*, not a literal file — a literal
    source path never contains the shell-glob metacharacters ``*``, ``?``, or
    ``[``, so a token carrying one is a glob to skip rather than a missing file
    to flag (BLD-2R9X). Sibling of the ``path::symbol`` carveout the chunk-ref
    parser applies before calling this.

    Write-target templates with angle-bracket placeholders (e.g.
    ``<inbox>/<kebab-slug>.md``) and URLs (e.g. ``https://example.com/x``) also
    contain ``/`` but are not literal on-disk paths — a token carrying ``<``,
    ``>``, or ``://`` is a placeholder/URL to skip, not a missing file to flag
    (BLD-4K7P; same form-family as the glob carveout above).

    Issue references and anchors (e.g. ``owner/repo#12``, ``docs/api#usage``)
    contain ``/`` but the ``#`` names a location in a *tracker or document*,
    not a file — no source file this verifier could be asked about carries one.
    Excluding them is a property of the token's shape, so it belongs here
    rather than at a caller, and it is correct for every consumer: a contract
    surface with a ``#`` in it is not a path either. Sibling of the URL and
    placeholder carveouts above.

    Git branch/ref names (e.g. ``feature/backlog-service-relayout``,
    ``origin/develop``, ``release/v3.2.0``) also contain ``/`` but name a branch,
    not a file — a build/release plan legitimately backticks them in prose. A
    token whose first segment is a git-flow branch prefix (``_GIT_REF_PREFIXES``)
    and whose final segment carries no extension-shaped suffix
    (:func:`_has_file_extension`) is a ref to skip; a real path keeps its
    extension (``feature/foo.py`` stays checked), so this does not blind the
    verifier to genuine missing files. Version-numbered branches are the case a
    dot-presence test gets wrong — see the note on ``_FILE_EXTENSION_RE``."""
    if "/" not in token:
        return False
    if token.startswith("/") and "/" not in token[1:] and "." not in token:
        return False
    if any(ch in token for ch in "*?["):
        return False
    if "<" in token or ">" in token:
        return False
    if "://" in token:
        return False
    if "#" in token:
        return False
    first, _, rest = token.partition("/")
    if first in _GIT_REF_PREFIXES and not _has_file_extension(rest.rsplit("/", 1)[-1]):
        return False
    return True


def _ref_path_part(token: str) -> str:
    """Reduce a backticked ref token to the file path that gets existence-checked.

    Two suffix forms name a location *inside* a file rather than a different
    file, so both are stripped before the check:

    - ``path::symbol`` (e.g. ``lib/views.py::is_views_enabled``) — verified by
      its file half; symbol verification stays deferred.
    - ``path:line`` / ``path:line-range`` (e.g. ``lib/critic_mode.py:452``,
      ``lib/foo.py:5-8``) — a code-location citation. Without this the whole
      ``path:line`` string is existence-checked literally and a present file
      reports as a missing ref.

    Order matters: the ``::`` split runs first, so a symbol that happens to end
    in digits (``lib/foo.py::rule42``) is discarded with the rest of the symbol
    half rather than being mistaken for a line number.
    """
    path_part = token.split("::", 1)[0]
    return _BUILD_PLAN_LINE_SUFFIX_RE.sub("", path_part)


def _chunk_section_lines(
    content: str, chunk_id: str
) -> tuple[bool, list[tuple[int, str]]]:
    """Locate the ``Chunk <chunk_id>`` section and return its body lines.

    The one canonical chunk-section walk: name-anchored with leading-zero
    tolerance (``"02"`` matches ``### Chunk 2:`` and vice versa), matches both
    supported heading forms (``### Chunk NN: Name`` and ``## Chunk N (ID) — Name``
    via ``_CHUNK_HEADING_RE``), stops at the next sibling chunk heading or a
    non-chunk ``## `` heading, and drops fenced code blocks (project-structure
    diagrams aren't load-bearing prose). Returns
    ``(found, [(line_num, raw_line), ...])`` with 1-based line numbers into
    ``content``. This skeleton was previously copied in the three chunk-field
    parsers below and ``lib.critic_mode``'s ``**Critic mode:**`` reader; all
    four now fold onto it.
    """
    target = chunk_id.lstrip("0") or "0"
    in_section = False
    in_fence = False
    section_lines: list[tuple[int, str]] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        heading = _CHUNK_HEADING_RE.match(stripped)
        if heading:
            head_norm = heading.group(1).lstrip("0") or "0"
            if in_section:
                # Entered a sibling chunk; stop accumulating.
                break
            if head_norm == target:
                in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("## "):
            # Left the Build Chunks section entirely (a non-chunk H2).
            break
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        section_lines.append((line_num, line))
    return in_section, section_lines


def _normalize_chunk_id(chunk_id: str) -> str:
    """Leading-zero-normalized chunk id (``01`` -> ``1``), for comparison only.

    **Not** :func:`views.normalize_chunk_id`, which is the canonical one and
    additionally casefolds and unifies ``_``/``-``. This is the weaker idiom this
    module already used inline at four other sites, named here so new comparisons
    stop adding copies. The two are NOT interchangeable: this one compares
    ``Chunk_A`` and ``Chunk-A`` as different. Both are only ever applied to both
    sides of a comparison within one module, so the difference is contained —
    unifying them is worth doing but is its own change, not a rider on this one.
    """
    return chunk_id.lstrip("0") or "0"


def _qualifier_scope_lines(
    section_lines: list[tuple[int, str]],
) -> Iterator[tuple[int, str]]:
    """A chunk's LIST-ITEM lines, **wrapped continuations included** — where a
    ``new `path`` declaration counts.

    See ``_LIST_ITEM_RE`` for why this is list items rather than the
    Deliverables block the item prescribed, and why a per-line test is wrong.
    Narrative paragraphs are excluded, which is where the adjectival ``new``
    that motivated #224(b) lives.
    """
    in_item = False
    for line_num, line in section_lines:
        if _LIST_ITEM_RE.match(line):
            in_item = True
        elif not line.strip() or _PLAN_FIELD_RE.match(line):
            # A blank line, or a line starting in column 0 — either closes the
            # item. Column-0 prose is a narrative paragraph, not a wrap: this
            # repo indents continuations.
            in_item = False
        if in_item:
            yield line_num, line


def _completed_chunk_ids(project_dir: Path, content: str) -> set[str] | None:
    """Normalized ids of the chunks this plan's progress reading says are DONE.

    ``None`` means *cannot tell*, and callers must read it as "expire nothing"
    — #224a fails toward the exemption on purpose, because a false missing-ref
    fires on every review of an in-progress chunk while a missed one surfaces at
    the next verify.

    Precedence belongs to :func:`resolve_chunk_progress` and is not re-derived
    here. That matters: under ``views_enabled`` the Status checkboxes are a
    derived view that only flips at release, so on a feature branch they read
    all-incomplete and a checkbox-based expiry would never fire on the only
    surface where it matters.

    The two readings get different treatment, because precision is free in one
    and not in the other:

    * **Checkbox reading** — the done-predicate IS the ``checked`` flag, already
      in hand. Read it directly and be exact. An earlier version applied the
      prefix rule here too and justified the imprecision as "the predicate lives
      in a closure", which is true of the git path and false of this one; the
      cost was real, since a checked chunk after ``current_id`` kept an
      exemption it had no claim to.
    * **Git-derived reading** — ``progress.complete`` is a COUNT of done items
      *anywhere* in the roster, deliberately non-contiguous (see
      :func:`_git_aware_progress` on why the union exists), and the per-item
      predicate is a closure over that function's git state. Slicing by the count
      names the wrong chunks: on ``01 open / 02 committed / 03 committed`` it
      yields ``{01, 02}``, expiring the exemption on the chunk
      ``resolve_chunk_progress`` simultaneously calls CURRENT. So take the roster
      prefix strictly before ``current_id`` — sound by construction, since
      "current" is the first item that is not done. It under-reports a done item
      sitting after ``current_id``, which is the safe direction.
    """
    progress = _resolve_chunk_progress_from(project_dir, content)
    if not progress.has_status_items:
        return None  # no roster to reason about
    items = list(_iter_status_section_items(content))
    ordered = [_chunk_id_from_item_text(text) for _checked, text in items]
    if any(cid is None for cid in ordered):
        return None  # an unparseable roster entry — placement is unsafe
    normalized = [_normalize_chunk_id(cid) for cid in ordered]
    if not progress.git_derived:
        return {
            cid for (checked, _text), cid in zip(items, normalized) if checked
        }
    if progress.current_id is None:
        return set(normalized)  # nothing left open: every chunk is complete
    current = _normalize_chunk_id(progress.current_id)
    if current not in normalized:
        return None  # current is not in the roster we just read — placement unsafe
    return set(normalized[: normalized.index(current)])


def _parse_build_plan_chunk_refs(
    prawduct_dir: Path, chunk_id: str, plan_path: "Path | None" = None
) -> dict:
    """Extract backticked file-path references from a single chunk's section
    in ``.prawduct/artifacts/build-plan.md``.

    ``plan_path`` names the plan to read; it defaults to the
    ``active_build_plan`` pointer, which is right for ``verify-chunk-refs``
    (a repo-level question) and wrong for a review (a question about the plan
    the DISPATCH named). The review path passes
    :func:`resolve_reviewed_plan`'s answer.

    The section is located by ``_chunk_section_lines`` (both the ``### Chunk NN:``
    and ``## Chunk N (ID) — Name`` heading forms, leading zeros tolerant), and
    parsing stops at the next sibling chunk heading or a non-chunk ``## `` heading
    — sibling chunks' refs are NOT returned. Fenced code blocks (```...```)
    are skipped because project-structure diagrams aren't load-bearing prose.
    A path declared with the ``new`` qualifier anywhere in the chunk is skipped
    for the whole section — it's a file the chunk creates rather than modifies,
    and re-naming it in a later Done-when step doesn't make it exist yet.

    Returns ``{"file_paths": [{"line_num": int, "ref": str}, ...],
    "error": str | None}``. The stored ``ref`` is the path half of the token as
    reduced by ``_ref_path_part`` — any ``::symbol`` or ``:line`` suffix is
    dropped, so a missing-ref message names the file rather than the citation.
    Symbol and backlog-ID verification remain deferred.
    """
    result: dict = {"file_paths": [], "error": None}
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        result["error"] = f"missing build-plan: {plan_path}"
        return result
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result["error"] = f"unreadable build-plan: {exc}"
        return result

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        result["error"] = f"chunk {chunk_id!r} not found in build-plan"
        return result

    # A path the chunk declares with the `new ` qualifier is a forward reference
    # for the WHOLE chunk section, not just the occurrence carrying the word.
    # Chunks routinely declare `new `path`` on Deliverables and then name the
    # same path again in a Done-when step; keying the exemption to that one
    # occurrence made every re-reference a false missing-ref. Normalized the same
    # way as the tokens below so a `new `path`` declaration also exempts a later
    # `path:42` citation of it.
    #
    # Scoped to list items (#224b) — see `_LIST_ITEM_RE` for why not Deliverables.
    forward_refs: set[str] = {
        _ref_path_part(m.group(1))
        for _, section_line in _qualifier_scope_lines(section_lines)
        for m in _BUILD_PLAN_NEW_QUALIFIER_RE.finditer(section_line)
    }
    # #224(a): the exemption EXPIRES when the chunk completes. `new `path`` says
    # "this chunk will create it" — once the chunk is done, a file that still
    # does not exist is a real missing ref, and the un-expiring exemption meant a
    # chunk could claim to create a file, not create it, and never be caught.
    #
    # Completion is re-derived through `resolve_chunk_progress`, never from "the
    # first unchecked box": under `views_enabled` the checkboxes are a derived
    # view that stays `[ ]` until release, so on a feature branch every chunk
    # reads incomplete and the expiry would never fire on the only surface where
    # it matters. `_completed_chunk_ids` returns None when it cannot tell, and
    # None keeps every exemption — failing TOWARD the exemption, because a false
    # missing-ref fires on every review of an in-progress chunk while a missed
    # one surfaces at the next verify.
    completed = _completed_chunk_ids(prawduct_dir.parent, content)
    if completed is not None and _normalize_chunk_id(chunk_id) in completed:
        forward_refs = set()

    seen: set[tuple[str, int]] = set()
    for line_num, line in section_lines:
        for match in _BUILD_PLAN_PATH_RE.finditer(line):
            path_part = _ref_path_part(match.group(1))
            if not _looks_like_file_path(path_part):
                continue
            if path_part in forward_refs:
                continue
            key = (path_part, line_num)
            if key in seen:
                continue
            seen.add(key)
            result["file_paths"].append({"line_num": line_num, "ref": path_part})
    return result


def _parse_build_plan_chunk_type(
    prawduct_dir: Path, chunk_id: str, plan_path: "Path | None" = None
) -> tuple[str | None, str | None]:
    """Extract the `Type:` declaration from a chunk's build-plan section.

    ``plan_path`` names the plan to read, defaulting to the ``active_build_plan``
    pointer. It exists so a caller that has already resolved *which plan* — via
    :func:`resolve_reviewed_plan` — reads this chunk field from the same file it
    read the others from. Two chunk-level fields resolving from two different
    plans is the same "one question, two answers" defect one field over.

    Returns ``(chunk_type, error)``. ``chunk_type`` is one of
    ``code | doc-only | cleanup | designer-handoff | cumulative-final | trivial``.
    Default (field absent) is ``code`` — fail-closed so a missing declaration
    runs the full Critic protocol rather than silently triggering a carveout
    (learnings: "escape hatches in classification create silent failures").
    Unknown values surface as ``(None, "unknown type: <value>")`` so the
    author fixes the typo instead of getting silent fall-through.

    Section discovery is the shared ``_chunk_section_lines`` walker —
    name-anchored on ``### Chunk <chunk_id>:`` with leading-zero tolerance;
    fenced code blocks are skipped.
    """
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None, f"missing build-plan: {plan_path}"
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable build-plan: {exc}"

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        return None, f"chunk {chunk_id!r} not found in build-plan"

    declared: str | None = None
    for _line_num, line in section_lines:
        m = _BUILD_PLAN_TYPE_RE.match(line)
        if m:
            declared = m.group(1)
            break

    if declared is None:
        return "code", None  # fail-closed default
    if declared not in _BUILD_PLAN_ALLOWED_TYPES:
        allowed = ", ".join(sorted(_BUILD_PLAN_ALLOWED_TYPES))
        return None, f"unknown type: {declared!r} (allowed: {allowed})"
    return declared, None


def _parse_build_plan_chunk_trivial_rationale(
    prawduct_dir: Path, chunk_id: str, plan_path: "Path | None" = None
) -> tuple[str | None, str | None]:
    """Extract the ``**Trivial because:**`` rationale from a chunk's section.

    Returns ``(rationale, error)``. Empty or absent field → ``(None,
    "missing-rationale: Type: trivial requires non-empty **Trivial
    because:** field")``. Multi-line rationale (continuation lines without
    a list-item / heading prefix) is joined into a single string until the
    next field.

    Section discovery is the shared ``_chunk_section_lines`` walker —
    name-anchored on ``### Chunk <chunk_id>:`` with leading-zero tolerance;
    fenced code blocks are skipped.

    ``plan_path`` names the plan to read, defaulting to the pointer — the third
    of the chunk-level fields to take it. The chunk id and the rationale must
    come from the SAME plan: validating a trivial declaration against another
    plan's same-numbered chunk either blocks on a rationale that is present, or
    passes on one written for different work.
    """
    if plan_path is None:
        plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None, f"missing build-plan: {plan_path}"
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable build-plan: {exc}"

    found, section_lines = _chunk_section_lines(content, chunk_id)
    if not found:
        return None, f"chunk {chunk_id!r} not found in build-plan"

    capturing = False
    rationale_lines: list[str] = []
    for _line_num, line in section_lines:
        stripped = line.strip()
        m = _BUILD_PLAN_TRIVIAL_RATIONALE_RE.match(line)
        if m:
            capturing = True
            first = m.group(1).strip()
            if first:
                rationale_lines.append(first)
            continue
        if capturing:
            # Stop at the next list-item field, bolded label, or sub-heading.
            if (
                stripped.startswith("- **")
                or stripped.startswith("* **")
                or stripped.startswith("**")
                or stripped.startswith("#")
            ):
                break
            if stripped:
                rationale_lines.append(stripped)

    if not capturing:
        return None, (
            "missing-rationale: Type: trivial requires non-empty "
            "**Trivial because:** field"
        )
    rationale = " ".join(rationale_lines).strip()
    if not rationale:
        return None, (
            "missing-rationale: Type: trivial requires non-empty "
            "**Trivial because:** field"
        )
    return rationale, None


# STH-1W5N — single source of truth for the unconditional ``Type: trivial`` /
# doc-only protected-path bounds. Each entry is ``(path, is_exact, reason_label)``:
# a change touching ``path`` (prefix match unless ``is_exact``) is a
# catastrophic-blast-radius edit that a trivial/doc-only chunk may never make,
# and the violation is reported as ``"<reason_label>: <path>"``. Centralized
# here (was inline in ``_classify_trivial_change``) so the stop-hook gate and
# the PR-boundary gate share one provably-identical list — and so the bound set
# is testable as data. The conditional bounds (test-file removals, newly-tracked
# files) stay in ``_classify_trivial_change`` because they depend on the change
# verb, not just the path.
#   skills/       — the critic/pr/etc. SKILL definitions + bundled protocols ARE
#                   the governance; editing one changes the framework itself.
#   methodology/  — the build/discovery/planning/reflection guides Claude reads
#                   as operating instructions; a "trivial" rewrite is never trivial.
#   templates/    — the artifact templates every product's specs are generated
#                   from; a silent change propagates to all downstream output.
#   CLAUDE.md     — the project's top-level operating contract (exact match —
#                   a nested ``foo/CLAUDE.md`` is ordinary product doc).
_TRIVIAL_PROTECTED_PATHS: frozenset[tuple[str, bool, str]] = frozenset({
    ("skills/", False, "skill-file-edited"),
    ("methodology/", False, "methodology-edited"),
    ("templates/", False, "template-edited"),
    ("CLAUDE.md", True, "claude-md-edited"),
})


def protected_path_violation(path: str) -> str | None:
    """Return the violation label (``"<reason_label>: <path>"``) when *path*
    falls under a governance-protected bound (``skills/``, ``methodology/``,
    ``templates/``, root ``CLAUDE.md``), else ``None``.

    Shared by the ``Type: trivial`` gate (via ``_classify_trivial_change``)
    and the PR-boundary doc-only gate (``lib/coverage.py``, PR-5K8D): fork-
    skill prose is behavioral logic in this framework, so a ``skills/*.md``
    change must never ride a doc-only fast path past the reviewers.

    **Directory bounds match the path SEGMENT, not a root anchor.** They were
    root-anchored, which silently stopped matching the moment a repo kept its
    skills anywhere but the top level: every ``plugin/skills/**.md`` edit read
    as non-judgeable, so a skills-only session was classified doc-only and
    skipped the reviewers entirely — the precise inverse of what this function
    exists to guarantee, and invisible because the failure is silence.

    A segment match over-includes rather than under-includes (a product's own
    ``src/skills/`` is caught too). That is the deliberate direction: this is
    authority, and authority fails closed. The cost of a false positive is one
    session that reviews when it need not; the cost of the false negative was
    governance-protected prose shipping unreviewed. The leading ``/`` in the
    containment test keeps ``myskills/`` from matching ``skills/``."""
    for protected, is_exact, reason_label in _TRIVIAL_PROTECTED_PATHS:
        if is_exact:
            matched = path == protected
        else:
            matched = path.startswith(protected) or f"/{protected}" in path
        if matched:
            return f"{reason_label}: {path}"
    return None


def _classify_trivial_change(
    *,
    path: str,
    src_path: str | None,
    is_addition: bool,
    is_deletion: bool,
) -> str | None:
    """Single-file path-rule check for the ``Type: trivial`` file-set
    bounds. Returns the violation reason or ``None`` when the change
    is eligible. Used by ``_is_trivial_fileset_eligible`` (Chunk 04 —
    working-tree porcelain) to enforce a *declared* ``Type: trivial``
    chunk at session-end. (The ``_pr_diff_is_trivial`` PR-boundary
    co-consumer was retired — it used these bounds as a triviality
    *detector* at the bundle boundary, with no link to a ``Type: trivial``
    declaration, so multi-chunk feature work that only touched existing
    files skipped both review gates.)

    The unconditional path bounds live in the module-level
    ``_TRIVIAL_PROTECTED_PATHS`` constant (STH-1W5N — single source of
    truth, referenced from this one call site). The conditional bounds
    (test-file removals, newly-tracked files) stay inline below because
    they depend on the change verb, not just the path.

    Metadata paths (``.prawduct/``, ``.claude/settings.json``, etc. —
    see ``_is_metadata_path``) are treated as out-of-scope and return
    ``None``. The check applies to BOTH ``path`` (rename dst / single-
    file change) AND ``src_path`` (rename src) — without that
    symmetry, a rename FROM a metadata path that landed somewhere
    interesting would silently be classified, and a rename TO a
    metadata path would be classified differently depending on which
    gate ran (the callers previously did dst-only filtering before
    calling this helper — v1.5.1 Chunk 04(b) consolidates).

    The caller translates its status format into the boolean inputs
    (porcelain handles 2-char codes; name-status handles single-char).
    Path bounds are catastrophic-blast-radius classes regardless of
    size — size is intentionally not a bound.
    """
    if gitstate._is_metadata_path(path):
        return None
    if src_path is not None and gitstate._is_metadata_path(src_path):
        return None
    # Unconditional path bounds — shared with the PR-boundary doc-only gate
    # via protected_path_violation (one provably-identical list).
    violation = protected_path_violation(path)
    if violation is not None:
        return violation
    if is_deletion and path.startswith("tests/"):
        return f"test-file-deleted: {path}"
    if src_path is not None and src_path.startswith("tests/"):
        return f"test-file-deleted: {src_path} (renamed out)"
    if is_addition:
        return f"new-file: {path}"
    return None


def _current_chunk_id_from_status(
    project_dir: Path, plan_path: "Path | None" = None
) -> str | None:
    """Extract the chunk id of the build-plan Status section's current item,
    e.g. ``"03"`` for ``- [ ] Chunk 03: Foo`` and ``"2"`` for
    ``- [ ] Chunk 2 (ID) — Foo``. Returns ``None`` if Status is missing, has no
    current chunk (all complete), or the item isn't a recognized chunk form.

    Thin id-extractor over :func:`_parse_build_plan_status` — which resolves
    "current" checkbox-wise or git-wise as the repo demands — so the stop hook,
    ``verify-chunk-refs``, and mode inference agree on which chunk is current by
    construction rather than by three parallel patches.

    ``plan_path`` overrides which plan is read (see
    :func:`resolve_chunk_progress`); the review path passes the plan the dispatch
    named so the fallback cannot answer about a different file than the one being
    graded.
    """
    status = _parse_build_plan_status(project_dir, plan_path)
    return _chunk_id_from_item_text(status.get("current_chunk", ""))


REF_ROOT_KEY = "build_plan_ref_root"


def _ref_root(project_dir: Path) -> Path | None:
    """A second root that this repo's plan refs may be written relative to,
    declared by the repo — or ``None``, which is the default everywhere.

    Some repos write plan refs relative to a subdirectory rather than the repo
    root, because that is how the paths read from inside the thing being built:
    a repo that *ships* a plugin names ``lib/gates.py`` and
    ``skills/backlog/SKILL.md``, which resolve from nowhere at the root. Those
    would otherwise report as missing deliverables.

    **The repo declares this; the verifier never infers it.** Sniffing for a
    subdirectory that "looks like" such a root — by name, or by a marker file
    inside it — silently weakens the gate for every repo whose layout happens
    to match: a genuinely missing deliverable gets resolved against an
    unrelated directory and never reported. A product that ships a plugin, an
    extension, or a bundled vendor tree is an ordinary layout, not a signal of
    intent. So the affordance is opt-in and available to any repo that wants
    it, and an absent key means the root is the only root, which is both the
    prior behaviour and the fail-closed one.

    A declared root that escapes the repo, does not exist, or is not a
    directory is ignored rather than honoured — the same fail-closed posture.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    declared = read_str_yaml_key(prawduct_dir / "project-state.yaml", REF_ROOT_KEY)
    if not declared:
        return None
    root = project_dir / declared
    try:
        root.resolve().relative_to(project_dir.resolve())
    except (ValueError, OSError):
        return None
    return root if root.is_dir() else None


def _verify_chunk_refs(project_dir: Path, refs: dict) -> list[dict]:
    """Verify each file-path ref names something that exists.

    Returns a list of ``{"kind", "ref", "line_num", "reason"}`` for missing
    entries. Empty list = all refs resolved.

    A ref resolves at the repo root or, when the repo declares one, under its
    additional ref root (:func:`_ref_root`). Anything else is
    reported. **Ambiguity is reported, not excused**: a token that is
    path-shaped but resolves nowhere gets named, even when it looks like it
    might be prose (a repo slug, a placeholder). A gate that guesses "probably
    not a file" fails open on exactly the input it exists to judge; the author
    disambiguates in the plan instead — placeholders as ``<owner>/<repo>``,
    real repositories unbackticked or as URLs, both of which this module
    already declines to treat as paths.
    """
    missing: list[dict] = []
    ref_root = _ref_root(project_dir)
    for entry in refs.get("file_paths", []):
        ref = entry["ref"]
        target = project_dir / ref
        if not target.exists():
            if ref_root is not None and (ref_root / ref).exists():
                continue
            if gitstate.git_path_is_ignored(project_dir, ref):
                # BLD-4K7P: an intentionally-gitignored managed path (e.g.
                # `.prawduct/.bug-inbox`) is a generated/managed file,
                # legitimately absent from a fresh checkout — not a missing
                # deliverable. Skip rather than cry wolf.
                continue
            missing.append({
                "kind": "file_path",
                "ref": ref,
                "line_num": entry["line_num"],
                "reason": "file does not exist",
            })
    return missing
