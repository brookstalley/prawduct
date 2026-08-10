"""Build-plan reference parsing + trivial-change classification for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 3) — the build-plan
parsing cluster: it reads the active build plan's Status section and per-chunk
sections (file-path refs, ``Type:`` declaration, ``Trivial because:`` rationale)
and classifies a single file change against the ``Type: trivial`` / doc-only
file-set bounds. Parsing + path inspection, plus read-only ``git log`` /
``git rev-list`` queries where "which chunk is current" cannot be answered from
the file alone — no git mutation, no network.

Depends on its lib siblings ``gitstate`` (for ``_is_metadata_path``), ``core``
(``resolve_build_plan_path``, ``read_str_yaml_key``), ``coverage``
(``_resolve_base_branch``) and ``plan_index`` (the canonical frontmatter ``scope:``
reader) plus the stdlib — still a clean DAG node, since ``coverage`` depends only
on ``core`` and ``plan_index`` on nothing in ``lib`` at all. The hook's inline build-plan-resolution
mirror (``_resolve_build_plan_path``) stays in the hook for its import-light hot
path; this module is a lib citizen and reaches the canonical resolver in
``lib.core`` directly, exactly as ``critic_mode`` and ``change_log`` do.

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

from . import gitstate, plan_index, waivers
from .core import read_str_yaml_key, resolve_build_plan_path
from .coverage import _resolve_base_branch

# `plan_index` is imported at MODULE scope, deliberately, where its predecessor
# `lib.views` had to be lazy. This module IS the hot path — `briefing` and
# `gates` both import it at module scope, so it is billed at every SessionStart
# and every Stop — and a lazy import inside the function is a cost of its own
# once the callee is cheap. Measured marginal cost on top of this module's own
# imports: `plan_index` 0.29ms, against 7.39ms for the module it replaced (now
# deleted, so that figure is history rather than a comparison anyone can re-run).
# `plan_index` shares `pathlib` and `collections.abc` with this module and pulls
# nothing else, which is the property that has to hold, not the number:
# `tests/test_lib_lazy_imports.py` asserts it structurally, against a positive
# control that proves the probe can fail. Re-measure with
# `python3 -c "import lib.buildplan_refs, time; ..."`, do not trust these
# figures on a different tree.
#
# This replaces a "deliberately no millisecond figure here" note that used to sit
# on `_scope_plan_map`, and the reversal is narrower than it looks: that note
# governed the SCAN cost, which is a property of each consumer's artifacts/ tree
# and therefore drifts the moment it is written down. These are IMPORT costs — a
# property of this code, identical in every checkout of a given version — and what
# binds is the structural test, not the numbers.


def status_section_bounds(lines: list[str]) -> "tuple[int, int] | None":
    """0-based ``[start, end)`` line indices of the ``## Status`` section BODY.

    ``None`` when the plan has no Status section. The section opens after a line
    that is exactly ``## Status`` and runs to the next ``## `` heading (a ``###``
    chunk heading does NOT close it) or to end of document.

    **Public, and the single home for the section's BOUNDS** — which is the part
    two readers genuinely share. :func:`_iter_status_section_lines` wants the
    body with comments skipped; ``lifecycle_repair`` wants the comment spans
    themselves, by index, because it deletes them. Neither can reuse the other's
    body handling, and a private bounds rule copied into both is how BLD-6Q1N's
    five divergent Status readers started. The two agreed when the second was
    written; that is the moment to merge them, not evidence that they will stay
    agreed.
    """
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "## Status":
            start = index + 1
            break
    if start is None:
        return None
    end = start
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("## ") and stripped != "## Status":
            break
        end += 1
    return (start, end)


def _iter_status_section_lines(content: str):
    """Yield stripped lines inside the build plan's ``## Status`` section.

    The one canonical Status-section walk (BLD-6Q1N): bounded by
    :func:`status_section_bounds`, skipping HTML-comment spans (``<!-- ... -->``,
    multi-line). This skeleton was previously copied in five readers across
    ``buildplan_refs`` / ``gates`` / ``critic_mode``; all of them now fold onto
    this generator, which is now the only Status-section *content* reader in the
    tree — the index-based Status *rewriter* that once stood beside it went with
    the derived view it regenerated.
    """
    lines = content.splitlines()
    bounds = status_section_bounds(lines)
    if bounds is None:
        return
    in_comment = False
    for line in lines[bounds[0] : bounds[1]]:
        stripped = line.strip()
        # A repeated `## Status` does not close the section (see the bounds
        # walk) and is not content either — it was skipped before this function
        # was bounded elsewhere, and it stays skipped.
        if stripped == "## Status":
            continue
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
# allows the opening `**`. The bold form is accepted because plans in the wild
# write it, and because this matcher once had a Status-line twin in the derived-
# view machinery that accepted it while this one did not. That disagreement cost
# more than either matcher's gap alone: the checkbox flipped (the twin matched)
# while `_chunk_id_from_item_text` returned None (this matcher did not), so the
# plan read as having NO current chunk and `verify-chunk-refs` exited 0 having
# verified nothing. The twin is gone and this is the sole matcher, so the
# disagreement cannot recur — but the widening stays, because the plans that
# provoked it are still on disk. A one-sided widening of a shared contract is not a partial
# fix, it is a new defect.
_CHUNK_ID_SEP = r"\s*(?:[:—–(-]|\*\*|$)"
_CHUNK_BOLD = r"(?:\*\*\s*)?"
_CHUNK_HEADING_RE = re.compile(r"^#{2,3}\s+" + _CHUNK_BOLD + r"Chunk\s+(\w+)" + _CHUNK_ID_SEP)
_CHUNK_ITEM_RE = re.compile(r"^" + _CHUNK_BOLD + r"Chunk\s+(\w+)" + _CHUNK_ID_SEP)


def unticked_chunk_items(content: str) -> list[str]:
    """The text of every unticked ``## Status`` item in ``content``.

    **The answer, exported — not the walker.** A caller outside this module that
    needs "which chunks are unmarked" must not reach for the Status walkers
    themselves: walking Status and testing checkboxes IS re-deriving currency,
    and a module that does it privately is how one question came to have three
    answers (BLD-7K3Q). Handing back the finished list keeps the derivation here
    while giving the caller what it actually wanted, so the structural guard
    against direct walkers stays without exception.

    Reports item text verbatim, so a caller can print what the plan says rather
    than a reconstruction of it. Returns ``[]`` for a plan with no Status
    roster — the same silence every other reader of an absent roster produces.
    """
    return [text for checked, text in _iter_status_section_items(content) if not checked]


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
    ``artifacts/build-plan.md``), so scope-named plans are counted too —
    unless ``plan_path`` names one, which the gate paths pass so that
    "is there governed work" and "what does it declare" read one file.
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


# A commit subject whose commit IS a chunk's work — three ANCHORED forms, not a
# match anywhere in the subject. Capital-C + digits still matches the "Chunk NN"
# convention without false-matching prose like "10-chunk plan" (CRT-7B4M); what
# the anchors add is the distinction between *carrying* a chunk and merely
# *mentioning* one.
#
# Why it had to narrow: `Chunk\s+(\d+)` matched a chunk id anywhere, so
# "…carry R-9's tail to Chunk 03" reported chunk 03 as finished-but-unticked
# minutes after this tripwire shipped. A brand-new control whose first firing is
# wrong teaches its first readers to ignore it — the habituation the
# proportionality norm exists to prevent, and doubly bad here because this
# control's whole defence is that it emits its yield observably.
#
# Why THREE forms and not the two the plan specified: the plan's narrowing was
# verified against one branch. Over this repo's last 800 subjects it also
# silenced two entire plans (`drift-burndown`, `critic-burndown`), whose chunks
# were only ever named by the third idiom — "close Chunk NN". Losing a real
# convention to drop a false positive trades one wrong answer for a quieter one.
# Each form is explicit and adjacent (a delimiter or a verb touching the id),
# never a heuristic over the whole subject:
#   1. `feat(scope): land it (Chunk 04)`      — parenthesised
#   2. `docs(scope): Chunk 03 — the prose half` — immediately after the conventional-commit colon
#   3. `docs(scope): close Chunk 01 — the census` — the explicit closing idiom
# Verified strictly narrowing: over 800 subjects it matches nothing the old
# pattern missed, and every subject it newly drops is a prose reference. Other
# idioms ("resolve Chunk 02 Critic findings") fall to this control's documented
# failure mode, silence — enumerating verbs is the slide this stops short of.
_CHUNK_COMMIT_RE = re.compile(
    r"\(Chunk\s+(\d+)\)"
    r"|:\s*Chunk\s+(\d+)\b"
    r"|\bclos(?:e|es|ed)\s+Chunk\s+(\d+)\b"
)
# Conventional-commit scope: `fix(session-boundary-events): … (Chunk 01)`.
_COMMIT_SCOPE_RE = re.compile(r"^\w+\(([^)]+)\)!?:")
# NOTE: the plan's own `scope:` is read through `plan_index.parse_build_plan_frontmatter_scope`,
# NOT a regex here. A hand-rolled `^scope:\s*(\S+)$` shipped briefly and was wrong in three
# ways the canonical reader already handles: it kept surrounding quotes (so a legal
# `scope: "session-boundary-events"` matched no commit scope, `scoped` came back empty, and
# the filter silently fell through to the unscoped reading — reinstating the very cross-plan
# contamination it was added to stop), it ignored the documented `null`/`~` opt-out, and it
# searched the whole document rather than the frontmatter block. `plan_index` is the ONE home
# for that reading — the module exists to be it — and the same bundle deleted `ledger`'s inline
# copy for exactly this reason (ROB-7T2N).


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
) -> dict[str, str]:
    """Chunk ids referenced in commit subjects on ``base..HEAD``, id → subject.

    **Reporting only.** This was once half of a second reading of chunk
    progress, standing in for Status checkboxes that could not be trusted
    because they were a derived view flipping at release. That derivation is
    gone: the checkbox is now the single reading, ticked by hand when a chunk
    finishes. What survives is the one thing the git signal was genuinely good
    for — noticing that a chunk's work is *committed* while its box is still
    empty — and :func:`unticked_committed_chunk_notice` is its only consumer.

    Ids are leading-zero-normalized to match Status ids. The mapped value is the
    subject of the FIRST commit naming that chunk, so a report can cite the
    evidence rather than assert a conclusion; a notice nobody can check is a
    notice nobody acts on. Returns ``{}`` on git failure.

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
    yet yields an empty mapping, and falling through there would re-import a
    sibling plan's ids. Once this plan is identifiable in the log, its empty
    mapping is the truthful answer — git knows nothing about its chunks — and
    the caller reports nothing.

    Bounding by the plan's own declared chunk ids needs no code here: the caller
    intersects against the Status roster, so an id belonging to no Status item is
    never reported.
    """
    proc = subprocess.run(
        ["git", "log", "--format=%s", f"{base}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return {}

    def _ids(subjects: list[str]) -> dict[str, str]:
        # `git log` is newest-first; walking it reversed makes the retained
        # subject the EARLIEST commit naming the chunk, which is the one that
        # dates the work — a later "fix(...) (Chunk 02)" is not when 02 landed.
        out: dict[str, str] = {}
        for subject in reversed(subjects):
            for m in _CHUNK_COMMIT_RE.finditer(subject):
                # One group per anchored form; exactly one is ever set, and
                # reading `group(1)` alone would silently drop forms 2 and 3.
                cid = next(g for g in m.groups() if g is not None)
                out.setdefault(cid.lstrip("0") or "0", subject)
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
        # cross-contamination this filter exists to stop. Returning the empty
        # mapping is the truthful answer (git knows nothing about this plan's
        # chunks), and the caller reports nothing on it.
        if scoped:
            return _ids(scoped)
    return _ids(subjects)


class ChunkProgress(NamedTuple):
    """How far the active build plan has got, and which chunk is current.

    ``current_id`` / ``current_text`` are empty-ish (``None`` / ``""``) when the
    plan has no remaining chunk.

    There is ONE reading — the ``## Status`` checkboxes, ticked by hand when a
    chunk finishes — so this type no longer carries a flag saying which reading
    answered. A second, git-derived reading used to exist for repos whose
    checkboxes were a derived view that only flipped at release; retiring the
    derived view retired the reason for it, and with it the whole question of
    precedence between two answers to one question.

    ``complete`` is a COUNT of done items, not a positional boundary. Under the
    checkbox reading the per-item predicate is the ``checked`` flag itself, which
    is exact — so a caller wanting "which chunks are done" filters on that flag
    and never slices a roster by this count. Done-ness is not contiguous: a
    plan may legitimately carry a ticked chunk after an unticked one, and
    slicing would name the wrong chunks in exactly that case.
    """

    total: int
    complete: int
    current_id: str | None
    current_text: str
    has_status_items: bool


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

    **Three paths ask this**: review dispatch, every session END (the Stop hook
    resolves its gate plan from the branch BEFORE deciding whether a plan is
    active, so the scan runs whenever the hook runs — not only where a plan and
    changes both exist), and every session START (the briefing's advisory reads
    the same plan so it cannot diverge from the gate). The cost sits on a hot
    path, which is why the callee is now :mod:`lib.plan_index` — a module that
    answers only this question — rather than the module that also carried the
    change-log parser and had to be imported lazily to keep its weight off these
    three paths. See this module's header for the measurement and the structural
    test that holds it.

    **Nothing memoizes the scan across calls.** The recursive walk of
    ``artifacts/`` and its per-file frontmatter parse happen every time.
    :func:`resolve_branch_plan` builds the map ONCE and hands it to both halves,
    so a resolution is one walk — an earlier version wrote the composite longhand
    at each caller and paid two. What bounds the walk as plans accumulate is
    :mod:`lib.plan_index` pruning the archive at directory level, so a repo's
    completed plans are not re-read twice a session forever.
    """
    return plan_index.build_scope_to_plan_map(prawduct_dir / "artifacts")


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

    ``known`` is a prebuilt scope→plan map — pass it to share one walk of
    ``artifacts/`` with a caller that also resolves the plan (:func:`resolve_branch_plan`).

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

    The liveness signal for :func:`infer_scope_from_branch`.

    **The signal is blunt, and the bluntness is now universal — worth knowing,
    because it used to be sharp on some repos.** The boxes flip per chunk, so a
    plan reads finished from the moment its last chunk is ticked, which is
    typically before the branch merges. In that window the branch stops matching
    and every caller falls back to the ``active_build_plan`` pointer:
    attribution, ``plan_graded``, and the Stop hook's ``Type:`` carveouts. That
    is the behaviour those callers had before branch inference existed, so the
    window is a *lapse of the improvement*, not a new defect — but it lands at
    end-of-plan, which is exactly when a `cumulative` review and the last gate
    run happen.

    Repos whose checkboxes were a derived view did not have this window: their
    boxes flipped at *release*, so "all checked" meant shipped, which is precisely
    the question asked here. Retiring the derived view removes that sharpness
    along with the false readings it produced everywhere else — a deliberate
    trade, stated here rather than discovered later. Narrowing the window needs a
    liveness signal a plan does not currently carry (a terminal state in
    frontmatter is the obvious candidate, and archival introduces exactly that);
    ``--scope`` is the remedy meanwhile.

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

    ``known`` is a prebuilt scope→plan map, so a caller resolving both halves
    pays one walk of ``artifacts/`` rather than two — see
    :func:`resolve_branch_plan`, which is the reason it exists. Omitted, it
    builds its own.

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

    The reading is the plan's ``## Status`` checkboxes: an item is done when its
    box is ticked, and the current chunk is the first unticked one. A ticked box
    is now a statement the builder made, not a value regenerated from elsewhere,
    so this file says what it means.

    **This function used to own a precedence** between that reading and a
    git-derived one, which existed because on some repos the checkboxes were a
    derived view that did not flip until release. Two readings of one question is
    what let the original defect reach three consumers, and the derived view is
    what made the second reading necessary; removing the view removes the need,
    and the precedence with it. The single-owner discipline still binds — every
    consumer (:func:`_parse_build_plan_status` and so the handoff, the briefing,
    ``verify-chunk-refs``, and ``critic_mode.infer_mode``) resolves through here
    rather than walking Status for itself, which is what
    ``TestOneCurrentChunkImplementation`` pins.

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
        return ChunkProgress(0, 0, None, "", False)
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ChunkProgress(0, 0, None, "", False)
    return _resolve_chunk_progress_from(content)


def _resolve_chunk_progress_from(content: str) -> ChunkProgress:
    """:func:`resolve_chunk_progress` against already-read plan content — so the
    parser below resolves progress without re-reading the file it already holds.

    Takes no ``project_dir``: with the git-derived reading gone, progress is a
    pure function of the plan text. That is the point of the collapse, and it is
    why this signature changed rather than keeping an unused parameter.
    """
    items = list(_iter_status_section_items(content))
    current = next((t for checked, t in items if not checked), "")
    return ChunkProgress(
        len(items),
        sum(1 for checked, _t in items if checked),
        _chunk_id_from_item_text(current),
        current,
        len(items) > 0,
    )


# Stable token on every unticked-but-committed emission, so occurrences can be
# counted by whoever is deciding whether this control still earns its place (the
# proportionality norm: a control that is printed and forgotten can never be
# retired on evidence, and this one is NEW, so it owes that evidence from the
# start). **Do not reword it** — that instruction stands on its own and needs no
# mechanism to obey. No counter is claimed here: the notice reaches the agent
# transcript, which lives outside this repo, so asserting a specific counting
# command would be a mechanism claim nothing in the tree implements.
UNTICKED_CHUNK_TOKEN = "unticked-committed-chunk"


def unticked_committed_chunk_notice(project_dir: Path) -> str | None:
    """A notice when a chunk's work is committed but its Status box is empty.

    **The tripwire that replaces the second reading** (DV7). With the checkbox as
    the single reading, a plan is only as accurate as the hand that ticks it, and
    the failure mode is specific: a chunk finishes, its commit lands, and the box
    stays ``- [ ]``. Every downstream answer — the briefing's ``Resume:`` line,
    the handoff, mode inference, chunk-ref grading — then names a chunk that is
    already done. That is not hypothetical; it is what this branch's own opening
    session inherited from a derived Status block, believed, and wrote forward
    into its handoff as testimony.

    Git is what the retired reading was genuinely good for, so it is kept for
    exactly this and nothing else: **it reports, it never writes and never
    decides.** Nothing here feeds :func:`resolve_chunk_progress`, so a wrong
    guess costs a line of stderr rather than a wrong gate. That asymmetry is the
    whole reason a signal too weak to be authoritative is still worth printing.

    Returns ``None`` unless a plan with a Status roster was read AND at least one
    of its unticked chunks is named by a commit since the base branch. Reported
    ids are intersected with the roster, so a sibling plan's ``(Chunk 02)``
    cannot manufacture a report about a chunk this plan does not have.

    **Expected yield, stated so it can be judged later:** it fires on a
    finished-but-unticked chunk before the session boundary, and it names the
    chunk and the commit subject that carried it — so a reader can confirm or
    dismiss it without re-deriving anything, and so the control can be retired on
    evidence rather than defended on principle.

    **Its precondition is a commit convention, and its failure mode is silence —
    which is worth stating because the two together are how a control looks
    healthy while covering nothing.** Firing requires a commit subject naming
    ``Chunk <n>`` (digits only) in one of :data:`_CHUNK_COMMIT_RE`'s three
    anchored forms, and, where any commit carries the plan's conventional-commit
    scope, a matching scope. A repo without that habit gets permanent silence,
    and silence here is indistinguishable from "every box is correct" — so this
    reports cleanest in exactly the repos least likely to be ticking reliably. A
    git failure degrades to the same silence. The honest summary is that this
    catches the mistake in repos that already follow the convention and does
    nothing elsewhere; a signal independent of commit subjects (comparing the
    ticked set against which chunks' *files* changed) is the obvious
    strengthening and is not attempted here.

    **Where it is emitted, and the one budget line that governs it.** This runs
    ``git log``, so it stays off the surfaces that run twice a session: never
    from the SessionStart orientation path and never from the Stop hook. Its
    call sites are the deliberately-invoked commands (``verify-chunk-refs``,
    ``handoff preview``) and the ``/clear`` session boundary, which runs once,
    already shells out to git, and is the only one an ordinary governed session
    passes through. Wiring it there is what makes the control *armed*: while its
    only callers were the two commands, an ordinary session never reached it, so
    a later "zero recorded yield" would have read as *no defect occurred* when
    the truth was *never in the path* — and the retirement-on-evidence argument
    this control offers would have been made from a control nothing ran.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    plan_path = resolve_build_plan_path(prawduct_dir)
    if not plan_path.is_file():
        return None
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    items = list(_iter_status_section_items(content))
    if not items:
        return None
    unticked = {
        _normalize_chunk_id(cid): text
        for checked, text in items
        if not checked and (cid := _chunk_id_from_item_text(text)) is not None
    }
    if not unticked:
        return None
    try:
        base, _ = _resolve_base_branch(project_dir)
        if not base or _commits_ahead_of_base(project_dir, base) <= 0:
            return None
        _present, plan_scope = plan_index.parse_build_plan_frontmatter_scope(content)
        committed = _committed_chunk_ids(project_dir, base, plan_scope)
    except (OSError, subprocess.SubprocessError):
        # A git hiccup must degrade to silence, never to a claim. Every caller
        # treats `None` as "nothing to report", which is the honest answer when
        # the evidence could not be read.
        return None
    # Numeric order, and the key is TOTAL on this domain rather than merely
    # usually-right: the input is a SET, so a key with ties would leave the
    # tied ids in set-iteration order and the same repo could print the same
    # finding two ways on two runs. Every key here is a digit string because
    # every `_CHUNK_COMMIT_RE` group captures `\d+` — which also means a plan using
    # non-numeric chunk ids (`Chunk A`) gets no report at all, since no commit
    # subject can ever match one. That is a real gap in this control's coverage,
    # not a case handled elsewhere.
    flagged = sorted(set(unticked) & set(committed), key=int)
    if not flagged:
        return None
    lines = [
        f"WARNING: {UNTICKED_CHUNK_TOKEN}: {len(flagged)} chunk(s) of "
        f"{plan_path.name} have commits on this branch but an unticked ## Status "
        f"box. Tick the box if the chunk is done — every reader of this plan, "
        f"including the next session's briefing, believes the boxes."
    ]
    lines.extend(
        f"  - {unticked[cid].strip()} — committed as {committed[cid]!r}" for cid in flagged
    )
    return "\n".join(lines)


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
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
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
        progress = _resolve_chunk_progress_from(content)
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
# The mirror of `new`: a deliverable declared as a REMOVAL is satisfied by the
# file's absence, not falsified by it.
#
# Without this the ref check is structurally unable to pass a retirement chunk.
# It asserts existence for every backticked deliverable ref, so a chunk whose
# job is deleting `x.py` reports `missing-ref: x.py` **because it succeeded** —
# and the check is rated BLOCKING, so the work cannot be closed honestly. The
# tempting workaround is to reword the plan until the parser stops seeing the
# path, which satisfies the checker by making the plan describe its own deletion
# less clearly. That is fixing the symptom at the cost of the artifact.
#
# Deliberately an EXPLICIT qualifier rather than a heuristic over removal verbs
# near a path. A fuzzy rule would exempt real deliverables sitting in a sentence
# that happens to mention a deletion, and an exemption that fires by accident is
# worse than no exemption — it fails open on exactly the input the gate exists
# to judge. Both orders are accepted because both read naturally in a
# Deliverables line (``deleted `x.py` `` and ``` `x.py` deleted ```), but the
# verb must be ADJACENT to the path, so the binding is visible to a reader.
#
# No expiry, where `new` has one. `new` expires when the chunk completes because
# a promised file that still does not exist is a real miss; a removal is the
# opposite — before completion the file is still there and resolves on its own,
# and after completion its absence IS the delivery.
_REMOVAL_VERBS = r"(?:deleted|removed|retired)"
_BUILD_PLAN_GONE_QUALIFIER_RE = re.compile(
    rf"\b{_REMOVAL_VERBS}\s+`([^`\s]+)`|`([^`\s]+)`\s+(?:is\s+|are\s+)?{_REMOVAL_VERBS}\b"
)
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

    - ``path::symbol`` (e.g. ``lib/plan_index.py::build_scope_to_plan_map``) —
      verified by its file half; symbol verification stays deferred.
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

    **The only chunk-id normalizer in the tree.** A stronger one — casefolding
    and unifying ``_``/``-`` — lived in the derived-view module and went with it,
    which settles a difference this docstring used to have to warn about: the two
    disagreed on ``Chunk_A`` vs ``Chunk-A``, contained only because each was
    applied to both sides of a comparison within its own module. Nothing here
    grew to cover the retired one's extra folding, because nothing asked for it;
    if a caller ever needs case- or separator-insensitive matching, widen this
    one rather than adding a second.
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


def _completed_chunk_ids(content: str) -> set[str] | None:
    """Normalized ids of the chunks this plan's Status section says are DONE.

    ``None`` means *cannot tell*, and callers must read it as "expire nothing"
    — #224a fails toward the exemption on purpose, because a false missing-ref
    fires on every review of an in-progress chunk while a missed one surfaces at
    the next verify.

    The done-predicate IS the ``checked`` flag, already in hand, so this reads it
    directly and is exact. **It used to have to be inexact.** A second,
    git-derived reading once answered here for repos whose checkboxes were a
    derived view; on that path done-ness was a bare COUNT with the per-item
    predicate locked inside a closure, so the only sound recovery was the roster
    prefix strictly before ``current_id`` — which under-reported a done item
    sitting after the current one. With one reading the flag is per-item and
    positional reasoning is gone, along with the class of error it carried.
    """
    items = list(_iter_status_section_items(content))
    if not items:
        return None  # no roster to reason about
    ordered = [_chunk_id_from_item_text(text) for _checked, text in items]
    if any(cid is None for cid in ordered):
        return None  # an unparseable roster entry — placement is unsafe
    return {
        _normalize_chunk_id(cid)
        for (checked, _text), cid in zip(items, ordered)
        if checked
    }


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

    A line carrying ``prawduct:allow prawduct/chunk-ref-missing -- <reason>``
    (or the same pragma on the line above) contributes no refs: that is the
    escape for prose which *discusses* a path rather than declaring it, where
    the path's absence is the point being recorded. It needs a reason like every
    other waiver, and the Critic checks that the reason is legitimate.
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
    # `_completed_chunk_ids` returns None when it cannot tell, and None keeps
    # every exemption — failing TOWARD the exemption, because a false missing-ref
    # fires on every review of an in-progress chunk while a missed one surfaces
    # at the next verify.
    completed = _completed_chunk_ids(content)
    if completed is not None and _normalize_chunk_id(chunk_id) in completed:
        forward_refs = set()

    # Paths this chunk declares it REMOVES — satisfied by absence. Same list-item
    # scoping as `new` above and for the same reason: the declaration routinely
    # lands on a wrapped continuation line. See `_BUILD_PLAN_GONE_QUALIFIER_RE`
    # for why this is an explicit qualifier and why it never expires.
    gone_refs: set[str] = {
        _ref_path_part(m.group(1) or m.group(2))
        for _, section_line in _qualifier_scope_lines(section_lines)
        for m in _BUILD_PLAN_GONE_QUALIFIER_RE.finditer(section_line)
    }

    seen: set[tuple[str, int]] = set()
    # Waiver lookup needs the line ABOVE as well as the line itself (both
    # placements are supported — `waivers.waives`), and a plan puts the pragma
    # above far more often than beside: the path usually sits mid-sentence in
    # wrapped prose, where a trailing comment would land on whichever line the
    # wrap happened to end on.
    section_texts = [text for _, text in section_lines]
    for index, (line_num, line) in enumerate(section_lines):
        # A chunk body does not only DECLARE paths — it also DISCUSSES them, and
        # the two are indistinguishable to a backtick scan. The case that forced
        # this: a carried-in review observation naming the path a past defect was
        # about (`plugin/tests`, a scan root that never existed on any branch).
        # The prose is correct precisely BECAUSE the path is missing, so the
        # check fires forever and the only ways out are to launder the record to
        # satisfy the linter or to leave a permanent blocking finding.
        #
        # The exemption is the repo's ordinary waiver pragma (`docs/waivers.md`)
        # rather than a new rule of its own: it demands a reason, it is visible
        # to the next reader at the line it applies to, the Critic verifies each
        # one is legitimate, and a reason-less waiver still fires. Deliberately
        # NOT solved by scoping extraction to `**Deliverables:**` — a chunk names
        # load-bearing paths in Tests, Done-when and Artifacts-consumed too, and
        # narrowing the scan would stop checking them to silence prose.
        if waivers.waives(section_texts, index, "prawduct/chunk-ref-missing"):
            continue
        for match in _BUILD_PLAN_PATH_RE.finditer(line):
            path_part = _ref_path_part(match.group(1))
            if not _looks_like_file_path(path_part):
                continue
            if path_part in forward_refs or path_part in gone_refs:
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
