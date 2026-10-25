"""Chunk status as a query — the walker of a plan's progress (#1051).

"Is chunk N done" and "is this plan finished" are to have one answer each,
derived from the facts the Critic already writes, never from a hand-ticked box
or a commit (``1050-design.md`` § 3). This module computes it, and it is the
only module outside ``plan_index`` (the Status section's bounds and walk) and
the hook's ``plan import-status`` writer that reads a ``## Status`` box —
``tests/test_handoff_parser_correctness.py::TestOneCurrentChunkImplementation``
pins that over every ``lib`` module and the hook.

- :func:`chunk_states` — each chunk's state, ``open``, ``done`` or ``dropped``;
- :func:`is_finished` — every chunk ``done`` or ``dropped`` (the only function
  here answering "finished");
- :func:`current_chunks` — the ``open`` chunks, in plan order, real ids only
  (the fail-closed entries below are left out; see :attr:`ChunkState.synthetic`);
- :func:`built_chunks` — a RENDERING convenience, the one git-walking function
  here; no gate reads it and :func:`chunk_states` never calls it;
- :func:`propose_chunks` — the chunk set a review dispatch proposes (ST8);
- :func:`render_table` — the ``plan status`` table, the one renderer the CLI,
  the ``/clear`` handoff and the PR payload print;
- :func:`built_not_done_notice` — the bound plan's chunks that are built and
  not done, for the two deliberately-run surfaces that print it.

**done** is a ``review`` fact whose body ``scope`` is this plan's ``scope:``,
whose chunk list names the chunk (``chunks`` when present, else ``[chunk]``
when ``chunk`` is set, else nothing), whose blocking findings are zero or all
resolved by a passing ``resolution`` fact (``dispositions.census`` owns that
rule), and whose anchor commit is reachable from the plan's ``branch:`` or a
declared ``working-branches:`` entry. Mode labels do not matter. A
``chunk-imported`` fact (``{scope, chunk, source: "status-box", imported_at}``,
written by the MG2 migration) is ``done`` too, tagged ``imported``. Until a plan
is migrated, each ticked ``## Status`` box reads exactly as such a fact would —
in memory, nothing written (MG1).

**dropped** is a frontmatter declaration, hand-written on purpose and never
inferred: a block sequence under ``dropped:`` whose items read ``- <id>:
<reason>`` (``<id>`` as the plan prints it, ``Chunk 02`` or ``02``). The reason
is required.

**Authority fails closed** (``architecture.md`` § Direction): what cannot be
read leaves a chunk ``open``, which keeps every gate armed, and says why in its
``reason``. An unreadable ``dropped:`` entry drops nothing; a review fact whose
blocking findings cannot all be read certifies nothing; an anchor git cannot
place completes nothing. A plan file that cannot be read answers with one open
:data:`UNREADABLE_PLAN` entry rather than the empty mapping, which would read as
finished, and a chunk heading the parser rejects is an open entry of its own
rather than an absence. Both are ``synthetic``: they keep :func:`is_finished`
false, but they are not chunk ids, so :func:`current_chunks` and
:func:`propose_chunks` never hand one out.

**Cost (NF1).** :func:`chunk_states` is called on every Stop. It walks no git
history and makes no network call: its only subprocess is one ``git merge-base
--is-ancestor`` per distinct anchor, run only for a fact that would otherwise
certify a chunk still open, memoized per call — so a store holding no such fact
costs no subprocess at all. Pinned by call in ``tests/test_plan_status.py``.
That is also why precedence follows cost: an import (fact or box) answers
first, then ``dropped:``, and a review fact only for a chunk those leave open —
so a chunk both ticked and reviewed reads ``done, imported`` with no fact cited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from . import buildplan_refs, core, coverage, dispositions, evidence, gitstate, plan_index, work_unit

if TYPE_CHECKING:
    # For readers only: a runtime import would close a cycle, because
    # plan_lifecycle imports release_readiness, which imports gates, which
    # imports this module.
    from . import plan_lifecycle

State = Literal["open", "done", "dropped"]

#: Frontmatter key declaring chunks the plan will not build.
DROPPED_KEY = "dropped"

#: The fact kind the MG2 migration writes for a ticked ``## Status`` box.
IMPORTED_KIND = "chunk-imported"

#: The key :func:`chunk_states` answers under when the plan file itself cannot
#: be read — one open entry, so the answer is "not finished" rather than the
#: empty mapping a plan with no chunks gives.
UNREADABLE_PLAN = "?"

#: Resolution dispositions that clear a blocking finding — the values
#: ``dispositions.finding_state`` returns for a passing ``resolution`` fact.
_PASSING = frozenset({dispositions.STATE_FIXED, dispositions.STATE_WAIVED})

#: Review modes that propose every open chunk; ``chunk`` proposes by diff.
_WHOLE_PLAN_MODES = frozenset({"final", "cumulative"})

_DROPPED_ID_RE = re.compile(r"^\w+(?:\.\w+)*$")


@dataclass(frozen=True)
class ChunkState:
    """One chunk's answer.

    ``fact_id`` and ``date`` (``YYYY-MM-DD``) name the fact that certified a
    ``done`` chunk; both are ``None`` for a box read in memory, which no fact
    backs yet. ``imported`` marks a ``done`` that came from a box, as a
    ``chunk-imported`` fact or in memory. ``reason`` is the declared reason for
    a ``dropped`` chunk, and for an ``open`` one says why something that looked
    like an answer was not one (an unreadable ``dropped:`` entry, a review that
    names the chunk but cannot certify it, an unparseable heading); ``None``
    for a plain open chunk.

    ``synthetic`` marks an entry that is not a chunk of the plan but stands in,
    open, for what could not be read — the :data:`UNREADABLE_PLAN` key and a
    ``?L<line>`` key per rejected heading. Its key is not a chunk id: never name
    it in a fact or a dispatch. It keeps the plan unfinished.
    """

    state: State
    fact_id: str | None = None
    date: str | None = None
    imported: bool = False
    reason: str | None = None
    synthetic: bool = False


# ---------------------------------------------------------------------------
# The plan: chunk ids, scope, branches, dropped declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Plan:
    chunks: tuple[str, ...]  # ids as the plan prints them, plan order
    unparsed: tuple[tuple[str, str], ...]  # (key, heading) rejected headings
    scope: str | None
    branch: str | None  # the integration branch, argv-safe
    branches: tuple[str, ...]  # integration + working branches, argv-safe
    dropped: dict[str, str]  # normalized id -> reason
    dropped_faults: dict[str, str]  # normalized id -> why its entry is unreadable
    dropped_plan_faults: tuple[str, ...]  # why the declaration, or an entry naming no chunk, dropped nothing
    ticked: frozenset[str]  # normalized ids of ticked Status boxes


def _norm(chunk_id: object) -> str:
    return buildplan_refs._normalize_chunk_id(str(chunk_id))


def _ref_token(value: str | None) -> str | None:
    """A frontmatter branch name fit for a git argv, else ``None``.

    The one guard every frontmatter token reaching git passes: a value opening
    with ``-`` would be read as an option (the exposure ``gitstate.is_object_id``
    documents for ids).
    """
    return value if value and not value.startswith("-") else None


def _read_plan(content: str) -> _Plan:
    chunks: list[str] = []
    seen: set[str] = set()
    in_fence = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = buildplan_refs._CHUNK_HEADING_RE.match(stripped)
        if heading and _norm(heading.group(1)) not in seen:
            seen.add(_norm(heading.group(1)))
            chunks.append(heading.group(1))

    ticked: set[str] = set()
    for checked, text in plan_index.iter_status_section_items(content):
        chunk_id = buildplan_refs._chunk_id_from_item_text(text)
        if chunk_id is None:
            continue
        if _norm(chunk_id) not in seen:
            # A roster entry with no heading is still a chunk of this plan.
            seen.add(_norm(chunk_id))
            chunks.append(chunk_id)
        if checked:
            ticked.add(_norm(chunk_id))

    unparsed = tuple(
        (f"?L{line_num}", text)
        for line_num, text in buildplan_refs._unparsed_chunk_headings(content)
    )

    fm = plan_index.frontmatter_lines(content) or []
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    branch = _ref_token(plan_index.parse_build_plan_frontmatter_branch(content))
    working = work_unit._working_branches(fm) or ()
    branches = tuple(dict.fromkeys(b for b in (branch, *map(_ref_token, working)) if b))
    dropped, faults, plan_faults = _read_dropped(fm, seen)
    return _Plan(
        tuple(chunks), unparsed, scope, branch, branches, dropped, faults, plan_faults,
        frozenset(ticked),
    )


def _read_dropped(
    fm: list[str], chunk_ids: "set[str]"
) -> tuple[dict[str, str], dict[str, str], tuple[str, ...]]:
    """``(dropped, faults, plan_faults)`` from the frontmatter's ``dropped:`` block.

    One form: a block sequence of ``- <id>: <reason>``, ``<id>`` normalized as
    every chunk id is (``Chunk 02`` and ``2`` both name ``02``). Nothing that
    cannot be read drops anything, and each such case says why: an item whose
    id reads but whose reason is empty is reported against that chunk; a
    declaration the sequence reader cannot read whole, an item naming no id
    this reader reads, and an id that is no chunk of the plan are reported
    against every chunk, because none of them can be pinned to one.
    ``chunk_ids`` are the plan's normalized ids.
    """
    status, items = core.read_block_sequence("\n".join(fm), DROPPED_KEY)
    if status == core.YAML_UNPARSEABLE:
        return {}, {}, (
            f"`{DROPPED_KEY}:` is declared in a shape this reader does not parse — "
            f"write a block of `- <id>: <reason>` items — so it drops nothing",
        )
    dropped: dict[str, str] = {}
    faults: dict[str, str] = {}
    plan_faults: list[str] = []
    for item in items:
        raw_id, colon, reason = item.partition(":")
        written = core.unquote_scalar(raw_id.strip())
        chunk_id = _norm(written)
        reason = core.unquote_scalar(reason.strip())
        if not _DROPPED_ID_RE.match(chunk_id):
            plan_faults.append(
                f"`{DROPPED_KEY}:` entry `{item}` names no chunk id "
                f"(write `- <id>: <reason>`), so it drops nothing"
            )
            continue
        if chunk_id not in chunk_ids:
            plan_faults.append(
                f"`{DROPPED_KEY}:` names {written}, which is not a chunk of this plan"
            )
            continue
        if not colon or not reason:
            faults[chunk_id] = (
                f"`{DROPPED_KEY}:` entry for {written} gives no reason "
                f"(write `- {written}: <reason>`), so it drops nothing"
            )
            continue
        dropped[chunk_id] = reason
    return dropped, faults, tuple(plan_faults)


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


def _store(facts: object) -> dict:
    """The ``read_facts`` result, or an empty store for anything else."""
    return facts if isinstance(facts, dict) else {"facts": []}


def fact_chunks(body: dict) -> list[str]:
    """The chunk ids a review fact names, by the reader rule the plan's fact
    shape fixes — the rule every reader of the field is to take from here.

    ``chunks`` when present, else ``[chunk]`` when ``chunk`` is set, else
    ``[]``. A ``chunks`` that is not a list names nothing.
    """
    chunks = body.get("chunks")
    if chunks is not None:
        if not isinstance(chunks, list):
            return []
        return [str(c) for c in chunks if isinstance(c, (str, int)) and str(c).strip()]
    chunk = body.get("chunk")
    if isinstance(chunk, (str, int)) and str(chunk).strip():
        return [str(chunk)]
    return []


def _date(value: object) -> str | None:
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _blocking_clear(store: dict, review_ids: list[str]) -> dict[str, str | None]:
    """review id → ``None`` when every blocking finding is resolved, else why not.

    The rule is ``dispositions.census``'s; this adds only the read-it-all check:
    a review whose ``counts.blocking`` exceeds the blocking findings census
    could read (one with no ``fid`` is skipped there) certifies nothing.
    """
    if not review_ids:
        return {}
    report = dispositions.census(store, review_ids=review_ids)
    if report.get("status") != "ok":
        return {rid: "its findings could not be read" for rid in review_ids}
    verdicts: dict[str, str | None] = {}
    bodies = {
        f.get("id"): f.get("body") or {} for f in evidence.facts_of_kind(store, "review")
    }
    for review in report.get("reviews", []):
        rid = review.get("review_id")
        blocking = [r for r in review.get("rows", []) if r.get("severity") == "blocking"]
        open_ids = [r["fid"] for r in blocking if r.get("state") not in _PASSING]
        counts = (bodies.get(rid) or {}).get("counts")
        declared = counts.get("blocking") if isinstance(counts, dict) else None
        if open_ids:
            verdicts[rid] = f"blocking {', '.join(open_ids)} not resolved"
        elif isinstance(declared, int) and declared > len(blocking):
            verdicts[rid] = "a blocking finding carries no id, so its resolution cannot be read"
        else:
            verdicts[rid] = None
    for rid in review_ids:
        verdicts.setdefault(rid, "its findings could not be read")
    return verdicts


class _Reachability:
    """``merge-base --is-ancestor`` against the plan's branches, memoized."""

    def __init__(self, repo_dir: Path, branches: tuple[str, ...]):
        self._repo_dir = repo_dir
        self._branches = branches
        self._memo: dict[str, bool] = {}

    def __call__(self, anchor: str) -> bool:
        if anchor not in self._memo:
            self._memo[anchor] = any(
                evidence.run_git(self._repo_dir, "merge-base", "--is-ancestor", anchor, b)[0]
                == 0
                for b in self._branches
            )
        return self._memo[anchor]


# ---------------------------------------------------------------------------
# The answers
# ---------------------------------------------------------------------------


def chunk_states(plan_path: Path, facts: object, *, repo_dir: Path) -> dict[str, ChunkState]:
    """Each chunk's :class:`ChunkState`, keyed by the id the plan prints, in plan order.

    ``facts`` is an ``evidence.read_facts`` result. ``repo_dir`` is the work
    tree git runs in for the reachability probe. A plan with no chunks answers
    ``{}``; an unreadable plan answers ``{UNREADABLE_PLAN: open}``; each heading
    the chunk parser rejects adds an open entry keyed ``?L<line>``. Those two
    are ``synthetic`` (:class:`ChunkState`). Never raises; never walks git
    history and never calls :func:`built_chunks` (module docstring, NF1).
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            UNREADABLE_PLAN: ChunkState("open", reason=f"plan unreadable ({exc})", synthetic=True)
        }
    plan = _read_plan(content)
    store = _store(facts)

    states: dict[str, ChunkState] = {}
    by_norm: dict[str, str] = {}
    plan_fault = "; ".join(plan.dropped_plan_faults) or None
    for chunk_id in plan.chunks:
        by_norm[_norm(chunk_id)] = chunk_id
        states[chunk_id] = ChunkState(
            "open", reason=plan.dropped_faults.get(_norm(chunk_id)) or plan_fault
        )

    def still_open(norm_id: str) -> bool:
        key = by_norm.get(norm_id)
        return key is not None and states[key].state == "open"

    def note(norm_id: str, why: str) -> None:
        key = by_norm[norm_id]
        if states[key].reason is None:
            states[key] = ChunkState("open", reason=why)

    # The answers that cost nothing come first, so the reachability probe below
    # runs only for a chunk they leave open (NF1). Imports: a `chunk-imported`
    # fact, then — MG1 — a box not yet migrated, read exactly as the fact MG2
    # would write, in memory. Then the hand-written `dropped:` declaration.
    if plan.scope:
        for fact in evidence.facts_of_kind(store, IMPORTED_KIND):
            body = fact.get("body") or {}
            if body.get("scope") != plan.scope or not isinstance(fact.get("id"), str):
                continue
            n = _norm(body.get("chunk")) if body.get("chunk") is not None else None
            if n is not None and still_open(n):
                states[by_norm[n]] = ChunkState(
                    "done",
                    fact["id"],
                    _date(body.get("imported_at")) or _date(fact.get("ts")),
                    imported=True,
                )
    for n in plan.ticked:
        if still_open(n):
            states[by_norm[n]] = ChunkState("done", imported=True)
    for n, reason in plan.dropped.items():
        if still_open(n):
            states[by_norm[n]] = ChunkState("dropped", reason=reason)

    if plan.scope:
        # Review facts: scope and chunks first (free), census next (no git), the
        # reachability probe last and only for a fact that would certify.
        candidates = []
        for fact in evidence.facts_of_kind(store, "review"):
            body = fact.get("body") or {}
            if body.get("scope") != plan.scope or not isinstance(fact.get("id"), str):
                continue
            named = [n for n in dict.fromkeys(_norm(c) for c in fact_chunks(body)) if still_open(n)]
            if named:
                candidates.append((fact, body, named))
        verdicts = _blocking_clear(store, [f["id"] for f, _b, _n in candidates])
        reachable = _Reachability(Path(repo_dir), plan.branches)
        for fact, body, named in candidates:
            targets = [n for n in named if still_open(n)]
            if not targets:
                continue
            blocked = verdicts.get(fact["id"])
            if blocked is not None:
                for n in targets:
                    note(n, f"review {fact['id']} names it, but {blocked}")
                continue
            # A dirty-tree review records no `head_commit`; its `dispatch_commit`
            # is the anchor (critic_consolidate's prior-fact rule). So such a
            # review certifies once its dispatch commit is in the branch's
            # history; that the reviewed TREE was committed is the Stop gate's
            # coverage verdict to carry, not this function's.
            anchor = evidence.review_anchor(body)
            if not plan.branches:
                why = "the plan declares no `branch:` its commit could be on"
            elif not gitstate.is_object_id(anchor):
                why = "it records no commit to place"
            elif not reachable(anchor):
                where = " or ".join(f"`{b}`" for b in plan.branches)
                why = f"its commit is not on {where}"
            else:
                why = None
            if why is not None:
                for n in targets:
                    note(n, f"review {fact['id']} names it, but {why}")
                continue
            for n in targets:
                states[by_norm[n]] = ChunkState("done", fact["id"], _date(fact.get("ts")))

    for key, heading in plan.unparsed:
        states[key] = ChunkState(
            "open",
            reason=f"{buildplan_refs.UNPARSED_HEADING_MARKER}: `{heading}` is not a chunk "
            "heading the parser reads, so it cannot be certified — fix the heading",
            synthetic=True,
        )
    return states


def is_finished(
    plan_path: Path,
    facts: object,
    *,
    repo_dir: Path,
    states: "dict[str, ChunkState] | None" = None,
) -> bool:
    """Every entry ``done`` or ``dropped``. A plan with no chunks is finished;
    a synthetic entry (always open) keeps it unfinished.

    ``states`` is this plan's :func:`chunk_states` answer when the caller
    already holds it, so the walk is not run twice.
    """
    if states is None:
        states = chunk_states(plan_path, facts, repo_dir=repo_dir)
    return all(s.state != "open" for s in states.values())


def current_chunks(
    plan_path: Path,
    facts: object,
    *,
    repo_dir: Path,
    states: "dict[str, ChunkState] | None" = None,
) -> list[str]:
    """The ``open`` chunk ids, in plan order — synthetic entries left out.

    So a plan can be unfinished with no current chunk: when all that is open is
    an unreadable plan or a rejected heading. "Finished" is :func:`is_finished`'s
    question, never ``not current_chunks(...)``. ``states`` as for
    :func:`is_finished`.
    """
    if states is None:
        states = chunk_states(plan_path, facts, repo_dir=repo_dir)
    return [k for k, s in states.items() if s.state == "open" and not s.synthetic]


# ---------------------------------------------------------------------------
# Deliverables paths, the diff proposal, and the render-only `built`
# ---------------------------------------------------------------------------


def _path_shaped(token: str) -> bool:
    if not token or any(ch.isspace() for ch in token):
        return False
    return "/" in token or bool(re.search(r"\.[A-Za-z][A-Za-z0-9]{0,7}$", token))


def deliverable_paths(content: str, chunk_id: str) -> list[str]:
    """The backticked paths in a chunk's ``**Deliverables:**`` field, in order.

    Only that field: the section is located by the one chunk-section walk, and
    a later field label (``**Tests:**`` …) ends it. ``path::symbol`` and
    ``path:line`` reduce to the path. A token is path-shaped when it has a
    ``/`` or a file extension — no git is asked.
    """
    section = buildplan_refs._chunk_section_lines(content, chunk_id)
    paths: list[str] = []
    in_field = False
    for _line_num, line in section.lines:
        label = buildplan_refs._chunk_field_label(line)
        if label is not None:
            in_field = label in ("deliverables", "delivers")
        if not in_field:
            continue
        for match in buildplan_refs._BUILD_PLAN_PATH_RE.finditer(line):
            path = buildplan_refs._ref_path_part(match.group(1))
            if _path_shaped(path) and path not in paths:
                paths.append(path)
    return paths


def _touches(deliverables: list[str], changed: "set[str]") -> bool:
    """Whether a changed path is a deliverable, or under a deliverable directory.

    A directory matches what is under it only when it has two or more segments
    (``plugin/lib/backlog/``): a one-segment token (``.prawduct/``, ``tests/``)
    names a whole tree, and in a Deliverables bullet it is prose about that
    tree — matching it would read every governance write as this chunk's work.
    """
    for path in deliverables:
        bare = path.rstrip("/")
        if path in changed or bare in changed:
            return True
        if bare.count("/") >= 1 and any(c.startswith(bare + "/") for c in changed):
            return True
    return False


def propose_chunks(
    plan_path: Path,
    facts: object,
    diff_paths: "list[str] | set[str]",
    mode: str,
    *,
    repo_dir: Path | None = None,
) -> list[str]:
    """The chunks a review dispatched in ``mode`` proposes to name (ST8).

    ``chunk`` mode: the open chunks whose Deliverables paths intersect
    ``diff_paths`` (repo-relative; a deliverable directory matches what is
    under it). ``final`` / ``cumulative``: every open chunk. Any other mode
    proposes nothing. Plan order. ``repo_dir`` defaults to the work tree that
    holds the plan's ``.prawduct/``.
    """
    if repo_dir is None:
        repo_dir = _repo_of(Path(plan_path))
    open_ids = current_chunks(plan_path, facts, repo_dir=repo_dir)
    if mode in _WHOLE_PLAN_MODES:
        return open_ids
    if mode != "chunk":
        return []
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    changed = {str(p) for p in diff_paths}
    return [c for c in open_ids if _touches(deliverable_paths(content, c), changed)]


def _repo_of(plan_path: Path) -> Path:
    for parent in plan_path.resolve().parents:
        if parent.name == ".prawduct":
            return parent.parent
    return plan_path.resolve().parent


# A subject CARRIES a chunk in one of three anchored forms — never a mention
# anywhere in it ("…carried to Chunk 04" is prose), and digits-and-dots only, so
# "close Chunk work" names no id. A plan whose scope some commit carries counts
# only its scoped commits; when none carries it (scope tags are a convention, and
# drift), every subject counts. This is the rule's one home.
_CHUNK_COMMIT_RE = re.compile(
    r"\(Chunk\s+(\d+(?:\.\d+)*)\)"
    r"|:\s*Chunk\s+(\d+(?:\.\d+)*)\b"
    r"|\bclos(?:e|es|ed)\s+Chunk\s+(\d+(?:\.\d+)*)\b"
)
_COMMIT_SCOPE_RE = re.compile(r"^\w+\(([^)]+)\)!?:")
#: Opens each commit's subject line in the log; file names follow it. Not a
#: control character: `str.strip` treats \x1c-\x1f as whitespace.
_COMMIT_MARK = "@@prawduct-commit@@ "


@dataclass(frozen=True)
class BuiltReport:
    """:func:`built_report`'s answer: the built chunk ids, and why git could not
    say when it could not.

    ``unavailable`` is ``None`` when the walk ran — ``built`` is then the whole
    answer, empty meaning nothing is built — else a short cause (the plan could
    not be read, no base ref resolves, ``git log`` failed), and ``built`` is
    empty because nothing could be asked, not because nothing was built.
    """

    built: "set[str]"
    unavailable: "str | None" = None


def built_report(plan_path: Path, repo_dir: Path) -> BuiltReport:
    """Chunks with work committed on the plan's branch — render-only, git-walking.

    A chunk is built when a commit on ``base..branch`` names it in its subject
    (:data:`_CHUNK_COMMIT_RE`'s three anchored forms and the scope filter above
    it) or touches one of its Deliverables paths. ``branch`` is the plan's ``branch:``
    when that ref resolves, else ``HEAD``; ``base`` is the plan's ``base:``
    (``origin/<b>`` preferred), else the repo's. A declared ``base:`` that
    resolves to no ref is a cause, never a fallback to the repo's base: that
    would walk a different interval and answer as though it were this one.
    Returns the ids as the plan prints them. No gate reads it.
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return BuiltReport(set(), f"the plan cannot be read ({exc})")
    repo_dir = Path(repo_dir)
    plan = _read_plan(content)
    if not plan.chunks:
        return BuiltReport(set())
    declared_base = _ref_token(plan_index.parse_build_plan_frontmatter_base(content))
    if declared_base:
        base = next(
            (r for r in (f"origin/{declared_base}", declared_base)
             if coverage._git_ref_exists(repo_dir, r)),
            None,
        )
        if base is None:
            return BuiltReport(
                set(), f"the plan's `base: {declared_base}` names no ref in this clone"
            )
    else:
        base, why = coverage.repo_base_branch(repo_dir)
        if base is None:
            return BuiltReport(set(), why or "no base branch resolves")
    head = plan.branch if plan.branch and coverage._git_ref_exists(repo_dir, plan.branch) else "HEAD"
    rc, out, err = evidence.run_git(
        repo_dir, "log", f"--format={_COMMIT_MARK}%s", "--name-only", f"{base}..{head}", "--",
        strip=False,
    )
    if rc != 0:
        detail = (err or "").strip().splitlines()
        return BuiltReport(
            set(), f"`git log {base}..{head}` failed ({detail[0] if detail else f'exit {rc}'})"
        )
    commits: list[tuple[str, set[str]]] = []
    for line in out.splitlines():
        if line.startswith(_COMMIT_MARK):
            commits.append((line[len(_COMMIT_MARK):], set()))
        elif line.strip() and commits:
            commits[-1][1].add(line.strip())

    subjects = [s for s, _files in commits]
    if plan.scope:
        scoped = [
            s for s in subjects
            if (m := _COMMIT_SCOPE_RE.match(s)) and m.group(1).strip() == plan.scope
        ]
        if scoped:
            subjects = scoped
    named = {
        _norm(next(g for g in m.groups() if g is not None))
        for s in subjects
        for m in _CHUNK_COMMIT_RE.finditer(s)
    }
    changed = set().union(*(files for _s, files in commits)) if commits else set()
    return BuiltReport({
        c for c in plan.chunks
        if _norm(c) in named or _touches(deliverable_paths(content, c), changed)
    })


def built_chunks(plan_path: Path, repo_dir: Path) -> set[str]:
    """:func:`built_report`'s ids alone — ``set()`` both when nothing is built and
    when git could not say. A caller that prints or advises from the answer asks
    :func:`built_report`, so the second case is named rather than read as the
    first."""
    return built_report(plan_path, repo_dir).built


def gate_arms(binding: "work_unit.Binding") -> bool:
    """Whether the Stop hook's Critic and reflection gates arm for this checkout (ST2).

    The one predicate both the Stop hook and the briefing's previous-session
    check read, so the two never disagree. It is binding-derived and reads no
    chunk progress: a ``broken`` binding arms (authority fails closed — it blocks
    what ``bound`` would have blocked); a ``bound`` binding arms while its plan
    is live, i.e. the claimed plan file exists and is not under ``archive/``;
    ``unbound`` never arms. A tick, a commit or an edit before the review cannot
    disarm it; only archiving the plan (or the branch losing its claim) does.

    So nothing commit-derived may feed it — not :func:`built_chunks`, not
    :func:`built_not_done_notice`. A chunk's last commit lands BEFORE its review
    and its reflection; a gate reading commits once switched the blocking gates
    off for the whole complete-but-unmerged window, silently.
    """
    if binding.state == "broken":
        return True
    if binding.state != "bound" or binding.plan_path is None:
        return False
    plan_path = Path(binding.plan_path)
    # Live is `work_unit.is_live_plan_file`'s rule, asked of the plan's own
    # `.prawduct/artifacts/` — never an `archive` component anywhere in the
    # absolute path, which disarmed every repo checked out under `~/archive/`
    # (cumulative R-1). A plan with no `.prawduct` above it cannot be placed;
    # authority fails closed, so it arms while the file exists.
    prawduct = next((d for d in plan_path.parents if d.name == ".prawduct"), None)
    if prawduct is None:
        return plan_path.is_file()
    return work_unit.is_live_plan_file(plan_path, prawduct / "artifacts")


# ---------------------------------------------------------------------------
# Rendering: the chunk table, a chunk's title, the built-but-not-done notice
# ---------------------------------------------------------------------------


def render_table(
    states: "dict[str, ChunkState]",
    *,
    built: "set[str] | frozenset[str]" = frozenset(),
    built_unavailable: "str | None" = None,
) -> list[str]:
    """The ``plan status`` chunk table, as lines — the one renderer.

    Columns: chunk id, state, the certifying fact id, its date, and the tags
    ``imported`` and ``built`` (``built`` is :func:`built_chunks`' answer, passed
    in because it walks git and only the caller knows whether to pay for it);
    a chunk's ``reason`` is indented beneath its row. ``plan status``, the
    ``/clear`` handoff's progress block and the PR payload's build-plan section
    all print these lines, each under its own indent. ``[]`` for a plan with no
    chunks. ``built_unavailable`` is :class:`BuiltReport`'s cause: when set, a
    closing ``built: unavailable (<cause>)`` line says no row's missing
    ``built`` tag means "not built".
    """
    if not states:
        return []
    rows = [
        (
            chunk_id,
            st.state,
            st.fact_id or "-",
            st.date or "-",
            ", ".join(
                tag for tag, on in (("imported", st.imported), ("built", chunk_id in built)) if on
            ) or "-",
            st.reason,
        )
        for chunk_id, st in states.items()
    ]
    table = [("chunk", "state", "fact", "date", "tags", None), *rows]
    widths = [max(len(row[i]) for row in table) for i in range(4)]
    lines: list[str] = []
    for row in table:
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row[:4]))
        lines.append(f"{line}  {row[4]}".rstrip())
        if row[5]:
            lines.append(f"    {row[5]}")
    if built_unavailable:
        lines.append(f"built: unavailable ({built_unavailable})")
    return lines


def render_lifecycle(lifecycle: "plan_lifecycle.Lifecycle") -> str:
    """The ``plan status`` lifecycle line: ``lifecycle: <state>[ <release>] — <reason>``.

    ``lifecycle`` is a ``plan_lifecycle.observe`` answer. The release tag
    follows the state when there is one; the reason, which says what was
    observed, closes the line.
    """
    release = f" {lifecycle.released_in}" if lifecycle.released_in else ""
    return f"lifecycle: {lifecycle.state}{release} — {lifecycle.reason}"


def chunk_title(content: str, chunk_id: str) -> str:
    """``Chunk 04: The Critic summary`` — the chunk's own heading, for display.

    A chunk with no heading (an entry only an unmigrated Status roster lists)
    is named by that roster line's text; only its words are read, never whether
    it is ticked. ``Chunk <id>`` otherwise.
    """
    target = _norm(chunk_id)
    for line in content.splitlines():
        stripped = line.strip()
        match = buildplan_refs._CHUNK_HEADING_RE.match(stripped)
        if match and _norm(match.group(1)) == target:
            return stripped.lstrip("#").strip()
    for _ticked, text in plan_index.iter_status_section_items(content):
        item_id = buildplan_refs._chunk_id_from_item_text(text)
        if item_id is not None and _norm(item_id) == target:
            return text
    return f"Chunk {chunk_id}"


#: Opens every :func:`built_not_done_notice`, so its firings can be counted when
#: deciding whether it still earns its place. Do not reword it.
BUILT_NOT_DONE_TOKEN = "built-not-done"


def built_not_done_notice(project_dir: Path) -> "str | None":
    """Name the bound plan's chunks that are built and not done, or ``None``.

    A chunk is named when :func:`chunk_states` reads it ``open`` (a real chunk,
    not a synthetic entry) and :func:`built_chunks` sees work for it on the
    plan's branch: committed work no review has certified. The remedy is a
    review, so that is what the notice says. It reports and never writes.

    ``None`` for an unbound or broken checkout (no plan is borrowed), and when
    nothing is both open and built. When git cannot say what is built
    (:class:`BuiltReport`), one degraded line names the cause instead. It walks git, so it is printed only by the
    two deliberately-run surfaces — the ``/clear`` boundary and ``handoff`` —
    never by SessionStart or Stop (NF1).
    """
    project_dir = Path(project_dir)
    binding = work_unit.resolve(project_dir)
    if binding.state != "bound" or binding.plan_path is None:
        return None
    plan_path = Path(binding.plan_path)
    states = chunk_states(plan_path, evidence.read_facts(project_dir), repo_dir=project_dir)
    open_ids = [k for k, s in states.items() if s.state == "open" and not s.synthetic]
    if not open_ids:
        return None
    report = built_report(plan_path, project_dir)
    if report.unavailable:
        # Advice fails soft and names its consequence: silence here would read
        # as "nothing committed is unreviewed", which is exactly what is unknown.
        subject = (
            f"whether {plan_path.name}'s open chunk has"
            if len(open_ids) == 1
            else f"which of {plan_path.name}'s {len(open_ids)} open chunks have"
        )
        return (
            f"WARNING: {BUILT_NOT_DONE_TOKEN}: cannot tell {subject} committed work — "
            f"{report.unavailable}; committed work no review has certified is not named here."
        )
    flagged = [k for k in open_ids if k in report.built]
    if not flagged:
        return None
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        content = ""
    count, verb = ("1 chunk", "has") if len(flagged) == 1 else (f"{len(flagged)} chunks", "have")
    subject = (
        f"{count} of {plan_path.name} {verb} work committed on the plan's branch "
        "that no review has certified"
    )
    lines = [f"WARNING: {BUILT_NOT_DONE_TOKEN}: {subject} — built, not done — run the Critic."]
    lines.extend(f"  - {chunk_title(content, k)}" for k in flagged)
    return "\n".join(lines)
