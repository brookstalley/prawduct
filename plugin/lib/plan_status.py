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
- :func:`built_chunks` — the ``built`` tag: rendered, and read by one gate
  only to ARM it (``critic_mode.short_plan_deferral``'s ``read_built``: a
  short plan's last chunk), never to disarm one; :func:`chunk_states` never
  calls it;
- :func:`chunk_proposal` — the chunk set a review dispatch proposes (ST8),
  with notes saying why it named fewer than it might; :func:`propose_chunks`
  is its chunk list alone. It and :func:`built_chunks` are the two git-walking
  answers here, sharing one ``git log`` reader;
- :func:`retraction_target` — whether a fact's certification of a chunk can be
  withdrawn, the one check ``plan retract`` writes behind;
- :func:`render_table` — the ``plan status`` table, the one renderer the CLI,
  the ``/clear`` handoff and the PR payload print;
- :func:`built_not_done_notice` — the bound plan's chunks that are built and
  not done, for the two deliberately-run surfaces that print it.

**done** is a ``review`` fact whose body ``scope`` is this plan's ``scope:``,
whose blocking findings are zero or all resolved by a passing ``resolution``
fact (``dispositions.census`` owns that rule), whose anchor commit is reachable
from the plan's ``branch:`` or a declared ``working-branches:`` entry — or,
once every one of those is gone from every local and remote ref (the merge took
them), from the plan's base, which is where their commits went
(:class:`_Reachability`, #1065, #1079) — and which either names the chunk
(``chunks`` when present, else ``[chunk]`` when ``chunk`` is set, else nothing)
or SPANS it: the fact is an edge the coverage algebra composes
(``coverage_algebra.review_edges``) and its own interval carries a commit that
builds the chunk (:class:`_Spans`, #1082). Only a fact the coverage algebra
accepts as an edge may span, so chunk state never credits an interval the
coverage gate rejects — though an edge may certify no chunk. A commit builds a
chunk by a scoped subject carrying it or by a path ONLY that chunk's
Deliverables cover, so a neighbour's commit on a shared path certifies no
unbuilt chunk (:func:`_deliverable_chunks`). Naming answers first, in store
order, and a span only for a chunk naming left open. Mode labels do not matter. A
``chunk-imported`` fact (``{scope, chunk, source: "status-box", imported_at}``,
written by the MG2 migration) is ``done`` too, tagged ``imported``. Until a plan
is migrated, each ticked ``## Status`` box reads exactly as such a fact would —
in memory, nothing written (MG1).

**Retracted** is a ``chunk-retracted`` fact naming this plan's scope, a chunk
and the fact that certified it, by name or by span: that fact no longer certifies that chunk, and
the chunk says so in its ``reason`` while it stays open. Only that pair is
withdrawn — the fact's other chunks stay done, and a later fact naming the
chunk certifies it again. A box read in memory has no fact to retract.

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
:func:`chunk_proposal` never hand one out.

**Cost (NF1).** :func:`chunk_states` is called on every Stop. It makes no
network call and never walks the branch's or the base's whole history: its
subprocesses are one ``git merge-base --is-ancestor`` per distinct anchor, run
only for a fact that could still certify an open chunk, memoized per call — so
a store holding no such fact costs no subprocess at all — and, for a spanning
fact so placed, one ``git log`` of that fact's own interval (two for a
dirty-tree fact: its committed part, and the commits descending from its
dispatch commit, where its verbatim commit is looked for), memoized per
interval, plus one ``git show`` per change-fragment path in that interval.
Only an anchor the first probe refuses pays more: one ``for-each-ref`` per
call to place the claimed branches, one further probe per anchor against a
remote tracking ref or the base, and on the base, for an anchor that is its
review's own ``base_commit``, one first-parent ``rev-list`` bounded by the
base's commits since it, memoized per anchor. Pinned by call in
``tests/test_plan_status.py`` (``TestNoGitWalk``) and
``tests/test_chunk_state_table.py`` (rows G1, G2).
That is also why precedence follows cost: an import (fact or box) answers
first, then ``dropped:``, and a review fact only for a chunk those leave open —
so a chunk both ticked and reviewed reads ``done, imported`` with no fact cited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Literal

from . import (
    buildplan_refs, change_fragments, core, coverage, coverage_algebra, dispositions, evidence,
    gitstate, plan_index, work_unit,
)

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

#: The fact kind ``plan retract`` writes: ``{scope, chunk, fact_id, reason,
#: retracted_at}`` withdraws one fact's certification of one chunk. A fact is
#: never edited, so a wrong certification is answered by a new fact; it can
#: only reopen a chunk, never close one.
RETRACTED_KIND = "chunk-retracted"

#: The key :func:`chunk_states` answers under when the plan file itself cannot
#: be read — one open entry, so the answer is "not finished" rather than the
#: empty mapping a plan with no chunks gives.
UNREADABLE_PLAN = "?"

#: Resolution dispositions that clear a blocking finding — the values
#: ``dispositions.finding_state`` returns for a passing ``resolution`` fact.
_PASSING = frozenset({dispositions.STATE_FIXED, dispositions.STATE_WAIVED})

#: Review modes whose proposal also counts the chunks a commit subject names;
#: ``chunk`` proposes by diff alone (:func:`chunk_proposal`).
_WHOLE_PLAN_MODES = frozenset({"final", "cumulative"})

_DROPPED_ID_RE = re.compile(r"^\w+(?:\.\w+)*$")


@dataclass(frozen=True)
class ChunkState:
    """One chunk's answer.

    ``fact_id`` and ``date`` (``YYYY-MM-DD``) name the fact that certified a
    ``done`` chunk; both are ``None`` for a box read in memory, which no fact
    backs yet. ``imported`` marks a ``done`` that came from a box, as a
    ``chunk-imported`` fact or in memory. ``reason`` is the declared reason for
    a ``dropped`` chunk; for an ``open`` one it says why something that looked
    like an answer was not one (an unreadable ``dropped:`` entry, a review that
    names the chunk but cannot certify it, an unparseable heading); for a
    ``done`` one certified by span it says so, since that fact does not name
    it. ``None`` for a plain open chunk and a done one certified by name.

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


def retractions(store: dict, scope: "str | None") -> dict[tuple[str, str], str]:
    """``(fact id, normalized chunk id) → reason`` for this scope's
    ``chunk-retracted`` facts. An entry missing its fact id, chunk or reason
    withdraws nothing: what cannot be read must not reopen a chunk on a guess
    either, and the writer refuses all three."""
    if not scope:
        return {}
    pairs: dict[tuple[str, str], str] = {}
    for fact in evidence.facts_of_kind(store, RETRACTED_KIND):
        body = fact.get("body") or {}
        fact_id, chunk, reason = body.get("fact_id"), body.get("chunk"), body.get("reason")
        if body.get("scope") != scope or not all(
            isinstance(v, str) and v.strip() for v in (fact_id, chunk, reason)
        ):
            continue
        pairs.setdefault((fact_id, _norm(chunk)), reason.strip())
    return pairs


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


def _resolve_base(repo_dir: Path, content: str) -> tuple[str | None, str | None]:
    """``(base ref, cause)`` for the plan whose frontmatter is in ``content``:
    the plan's ``base:`` (``origin/<b>`` preferred over ``<b>``), else the
    repo's integration base. A declared ``base:`` that resolves to no ref is a
    cause, never a fallback to the repo's base, which would answer for a
    different interval as though it were this one. Exactly one of the two is
    ``None``."""
    declared_base = _ref_token(plan_index.parse_build_plan_frontmatter_base(content))
    if declared_base:
        base = next(
            (r for r in (f"origin/{declared_base}", declared_base)
             if coverage._git_ref_exists(repo_dir, r)),
            None,
        )
        if base is None:
            return None, f"the plan's `base: {declared_base}` names no ref in this clone"
        return base, None
    base, why = coverage.repo_base_branch(repo_dir)
    if base is None:
        return None, why or "no base branch resolves"
    return base, None


@dataclass(frozen=True)
class _Placement:
    """Where a plan's claimed branches are, asked once per :func:`chunk_states`
    call and only after a probe by name refused (:class:`_Reachability`)."""

    remote_refs: tuple[str, ...]  # tracking refs of claimed branches present only on a remote
    gone: bool  # no claimed branch is on any local or remote ref
    base: str | None  # the base a gone plan's commits are placed on, when it resolves
    base_cause: str | None  # why no base resolves, for the reason a chunk left open prints


class _Reachability:
    """Whether an anchor is in the history of the plan's branches, memoized per
    anchor. Answers ``None`` when it is, else the reason it is not.

    The claimed branches are probed by name first, so the common path costs one
    ``merge-base --is-ancestor`` per anchor and nothing else (NF1). Only when
    every name refuses is git asked, once per call, where those branches are:
    a branch present only on a remote is probed by its tracking ref, and a plan
    whose claimed branches are all gone is probed against its base — which is
    where a merged branch's commits went once ``/prawduct:pr`` deleted it, and
    the case that read every chunk of a merged plan as open (#1065).

    On the base path an anchor that is its own review's ``base_commit`` is
    refused only when it is on the base's FIRST-PARENT history: the fork point
    of a review dispatched before the branch's first commit is there, held by
    the base before the review ran, so finding it says nothing about a merge.
    A dirty-tree review's ``base_commit`` is the branch HEAD the tree sat on,
    which a merge commit brings in through its second parent; that anchor is
    accepted (#1079). A fast-forward merge puts branch commits on the
    first-parent history too, so there such an anchor still reads as a fork
    point — open, failing closed.

    :meth:`holder` names the ref that held an accepted anchor, which is where
    a dirty-tree review's verbatim commit is looked for (:class:`_Spans`).
    """

    def __init__(self, repo_dir: Path, plan: _Plan, content: str):
        self._repo_dir = repo_dir
        self._plan = plan
        self._content = content
        self._memo: dict[str, bool] = {}
        self._holder: dict[str, str] = {}
        self._placement: _Placement | None = None

    def _probe(self, anchor: str, target: str) -> bool:
        return (
            evidence.run_git(self._repo_dir, "merge-base", "--is-ancestor", anchor, target)[0]
            == 0
        )

    def _first_held(self, anchor: str, refs: "tuple[str, ...]") -> bool:
        held = next((r for r in refs if self._probe(anchor, r)), None)
        if held is not None:
            self._holder[anchor] = held
        return held is not None

    def _on_first_parent(self, anchor: str, base: str) -> bool:
        return on_first_parent(self._repo_dir, anchor, base)

    def holder(self, anchor: str) -> "str | None":
        """The ref an accepted ``anchor`` was found on, else ``None``."""
        return self._holder.get(anchor)

    def placement(self) -> _Placement:
        if self._placement is None:
            refs = gitstate.branch_refs(self._repo_dir, self._plan.branches)
            if refs is None:
                # Git could not say where the branches are: not evidence they are
                # gone (``gitstate.local_branches``), so no fallback is taken.
                self._placement = _Placement((), False, None, None)
            elif not refs:
                base, cause = _resolve_base(self._repo_dir, self._content)
                self._placement = _Placement((), True, base, cause)
            else:
                remote = tuple(r for r in sorted(refs) if not r.startswith("refs/heads/"))
                self._placement = _Placement(remote, False, None, None)
        return self._placement

    def __call__(self, anchor: str, fork_point: object = None) -> str | None:
        names = " or ".join(f"`{b}`" for b in self._plan.branches)
        if anchor not in self._memo:
            self._memo[anchor] = self._first_held(anchor, self._plan.branches)
        if self._memo[anchor]:
            return None
        where = self.placement()
        if where.remote_refs:
            key = f"remote:{anchor}"
            if key not in self._memo:
                self._memo[key] = self._first_held(anchor, where.remote_refs)
            return None if self._memo[key] else f"its commit is not on {names}"
        if not where.gone:
            return f"its commit is not on {names}"
        if where.base is None:
            return f"{names} is on no local or remote branch, and {where.base_cause}"
        key = f"base:{anchor}"
        if key not in self._memo:
            self._memo[key] = self._probe(anchor, where.base)
        if not self._memo[key]:
            return (
                f"its commit is not on `{where.base}` ({names} is on no local or remote "
                "branch, so the base it merged into is asked)"
            )
        if anchor == fork_point:
            first = f"first-parent:{anchor}"
            if first not in self._memo:
                self._memo[first] = self._on_first_parent(anchor, where.base)
            if self._memo[first]:
                return (
                    f"its commit is the review's own base commit, which is on `{where.base}`'s "
                    "first-parent history, so the base held it before the review ran"
                )
        self._holder[anchor] = where.base
        return None


def on_first_parent(repo_dir: Path, anchor: str, base: str) -> bool:
    """Whether ``anchor`` — known to be in ``base``'s history — is on its
    first-parent chain: there before any merge brought it, rather than brought
    in by one. A review anchored at its own ``base_commit`` proves a merge only
    when this is false (#1079); ``plan_lifecycle`` asks the same question of the
    same anchors, so this is the one place it is answered.

    ``rev-list --first-parent anchor..base`` walks from the base down to the
    first commit ``anchor`` reaches; the anchor is on the chain exactly when
    that last commit's first parent is the anchor (or nothing is listed: the
    base is the anchor). Git failing answers yes, which refuses: authority
    fails closed. The walk is bounded by the base's commits since the anchor,
    never its whole history."""
    rc, out, _err = evidence.run_git(
        repo_dir, "rev-list", "--first-parent", "--parents", f"{anchor}..{base}"
    )
    if rc != 0:
        return True
    lines = out.splitlines()
    if not lines:
        return True
    last = lines[-1].split()
    return len(last) > 1 and last[1] == anchor


class _Spans:
    """Which chunks a review fact's own interval carries a commit for — the
    span half of ``done`` (#1082), asked by :func:`chunk_states` only for a
    fact the cheap answers leave able to certify an open chunk.

    The interval is the fact's, never the branch's, so it reads the same after
    the merge deletes the branch: ``base_commit..head_commit``; for a
    dirty-tree fact, ``base_commit..dispatch_commit`` and then the
    first-parent chain from ``dispatch_commit`` to the first commit whose tree
    is the fact's ``head_tree`` — the reviewed tree, committed verbatim. A
    tree edited again before it was committed was not the tree reviewed, so
    that part carries nothing. A commit carries a chunk by the certifying
    rule the proposal applies, from the same owners: :func:`_subject_chunks`
    (a subject carrying the plan's scope and the chunk) and
    :func:`_deliverable_chunks` (a path it touches that only that chunk's
    Deliverables cover, less a change fragment still the ``plan new`` stub at
    the reviewed tree). A chunk with no commit of its own in the interval is
    carried by nothing. A fact whose ``base_commit``
    is not a commit id, whose interval git cannot list, or — dirty-tree — whose
    anchor's holding ref is unknown carries nothing.

    One :func:`_log_commits` per distinct interval, memoized per call, plus one
    ``git show`` per change-fragment path in the interval to tell the stub.
    """

    def __init__(self, repo_dir: Path, plan: _Plan, content: str):
        self._repo_dir = repo_dir
        self._plan = plan
        self._content = content
        self._logs: dict[tuple[str, ...], "list[_Commit] | None"] = {}

    def _log(self, *revs: str) -> "list[_Commit] | None":
        if revs not in self._logs:
            commits = _log_commits(self._repo_dir, *revs)
            self._logs[revs] = None if isinstance(commits, str) else commits
        return self._logs[revs]

    @staticmethod
    def _verbatim_chain(after: "list[_Commit]", start: str, tree: str) -> "list[_Commit]":
        """The first-parent chain from ``start`` (exclusive) to the nearest
        commit whose tree is ``tree``, else ``[]``."""
        children: dict[str, list[_Commit]] = {}
        for commit in after:
            if commit.parents:
                children.setdefault(commit.parents[0], []).append(commit)
        frontier: list[tuple[str, list[_Commit]]] = [(start, [])]
        seen = {start}
        while frontier:
            nxt: list[tuple[str, list[_Commit]]] = []
            for sha, chain in frontier:
                for child in children.get(sha, ()):
                    if child.sha in seen:
                        continue
                    seen.add(child.sha)
                    if child.tree == tree:
                        return [*chain, child]
                    nxt.append((child.sha, [*chain, child]))
            frontier = nxt
        return []

    def carried(self, body: dict, holder: "str | None") -> "set[str]":
        """The normalized ids of the chunks ``body``'s interval carries a
        commit for. ``holder`` is the ref the fact's anchor was found on."""
        base = body.get("base_commit")
        head = body.get("head_commit")
        head_tree = body.get("head_tree")
        if not gitstate.is_object_id(base) or not gitstate.is_object_id(head_tree):
            return set()
        if gitstate.is_object_id(head):
            commits = self._log(f"{base}..{head}")
        else:
            dispatch = body.get("dispatch_commit")
            if not gitstate.is_object_id(dispatch) or holder is None:
                return set()
            before = [] if dispatch == base else self._log(f"{base}..{dispatch}")
            after = self._log("--ancestry-path", f"{dispatch}..{holder}")
            if before is None or after is None:
                return set()
            commits = [*before, *self._verbatim_chain(after, dispatch, head_tree)]
        if not commits:
            return set()
        return _subject_chunks((c.subject for c in commits), self._plan.scope) | _deliverable_chunks(
            self._content, self._plan.chunks, self._plan.chunks,
            set().union(*(c.files for c in commits)), _read_at(self._repo_dir, head_tree),
        ).chunks


# ---------------------------------------------------------------------------
# The answers
# ---------------------------------------------------------------------------


def chunk_states(plan_path: Path, facts: object, *, repo_dir: Path) -> dict[str, ChunkState]:
    """Each chunk's :class:`ChunkState`, keyed by the id the plan prints, in plan order.

    ``facts`` is an ``evidence.read_facts`` result. ``repo_dir`` is the work
    tree git runs in for the reachability probe. A plan with no chunks answers
    ``{}``; an unreadable plan answers ``{UNREADABLE_PLAN: open}``; each heading
    the chunk parser rejects adds an open entry keyed ``?L<line>``. Those two
    are ``synthetic`` (:class:`ChunkState`). Never raises; never walks the
    branch's history and never calls :func:`built_chunks` — a span reads only
    the interval its own fact records (module docstring, NF1).
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
    retracted = retractions(store, plan.scope)

    def withdrawn(fact_id: str, norm_id: str, what: str, how: str = "names it") -> bool:
        reason = retracted.get((fact_id, norm_id))
        if reason is None:
            return False
        note(norm_id, f"{what} {fact_id} {how}, but it was retracted: {reason}")
        return True

    if plan.scope:
        for fact in evidence.facts_of_kind(store, IMPORTED_KIND):
            body = fact.get("body") or {}
            if body.get("scope") != plan.scope or not isinstance(fact.get("id"), str):
                continue
            n = _norm(body.get("chunk")) if body.get("chunk") is not None else None
            if n is not None and still_open(n) and not withdrawn(fact["id"], n, "import"):
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
        # reachability probe last and only for a fact that would certify. A
        # fact certifies the chunks it names, then — for chunks still open —
        # those its interval carries a commit for (`_Spans`), but only when it
        # is an edge the coverage algebra composes: chunk state never spans an
        # interval the coverage gate rejects (#1082).
        candidates = []
        spanning = []
        for fact in evidence.facts_of_kind(store, "review"):
            body = fact.get("body") or {}
            if body.get("scope") != plan.scope or not isinstance(fact.get("id"), str):
                continue
            named = [
                n for n in dict.fromkeys(_norm(c) for c in fact_chunks(body))
                if still_open(n) and not withdrawn(fact["id"], n, "review")
            ]
            if named:
                candidates.append((fact, body, named))
            if coverage_algebra.review_edges([fact]):
                spanning.append((fact, body))
        if not any(still_open(n) for n in by_norm):
            spanning = []
        verdicts = _blocking_clear(store, list(dict.fromkeys(
            [f["id"] for f, _b, _n in candidates] + [f["id"] for f, _b in spanning]
        )))
        reachable = _Reachability(Path(repo_dir), plan, content)
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
            # review certifies the chunks it NAMES once its dispatch commit is
            # in the branch's history; that the reviewed TREE was committed is
            # the Stop gate's coverage verdict to carry. A span is stricter,
            # because it certifies chunks nobody named: its uncommitted part
            # counts only once committed verbatim (`_Spans`).
            anchor = evidence.review_anchor(body)
            if not plan.branches:
                why = "the plan declares no `branch:` its commit could be on"
            elif not gitstate.is_object_id(anchor):
                why = "it records no commit to place"
            else:
                why = reachable(anchor, body.get("base_commit"))
            if why is not None:
                for n in targets:
                    note(n, f"review {fact['id']} names it, but {why}")
                continue
            for n in targets:
                states[by_norm[n]] = ChunkState("done", fact["id"], _date(fact.get("ts")))

        spans = _Spans(Path(repo_dir), plan, content)
        for fact, body in spanning:
            if not any(still_open(n) for n in by_norm):
                break
            anchor = evidence.review_anchor(body)
            if (
                verdicts.get(fact["id"]) is not None
                or not plan.branches
                or not gitstate.is_object_id(anchor)
                or reachable(anchor, body.get("base_commit")) is not None
            ):
                continue
            for n in sorted(spans.carried(body, reachable.holder(anchor))):
                if still_open(n) and not withdrawn(
                    fact["id"], n, "review", "carries its commit in its interval"
                ):
                    states[by_norm[n]] = ChunkState(
                        "done", fact["id"], _date(fact.get("ts")),
                        reason="by span: its review's interval carries the chunk's commit",
                    )

    for key, heading in plan.unparsed:
        states[key] = ChunkState(
            "open",
            reason=f"{buildplan_refs.UNPARSED_HEADING_MARKER}: `{heading}` is not a chunk "
            "heading the parser reads, so it cannot be certified — fix the heading",
            synthetic=True,
        )
    return states


@dataclass(frozen=True)
class RetractionTarget:
    """:func:`retraction_target`'s answer.

    ``status`` is ``"ok"`` (write it), ``"already"`` (this pair is already
    withdrawn; write nothing) or a refusal code — ``no-scope``,
    ``unknown-chunk``, ``box-import``, ``not-certified``, ``unknown-fact``,
    ``other-scope``, ``not-named`` — with ``detail`` saying why and what to do.
    ``chunk`` is the id as the plan prints it, ``fact_id`` the fact to withdraw.
    """

    status: str
    detail: str
    scope: "str | None" = None
    chunk: "str | None" = None
    fact_id: "str | None" = None


def retraction_target(
    plan_path: Path, facts: object, chunk: str, fact_id: "str | None" = None, *, repo_dir: Path
) -> RetractionTarget:
    """Whether ``fact_id``'s certification of ``chunk`` can be withdrawn, and
    the exact pair to record — the one check ``plan retract`` writes behind.

    ``fact_id`` omitted: the fact that certifies the chunk now, by name or by
    span. Given: a ``review`` or ``chunk-imported`` fact of this plan's scope
    that names the chunk — the chunk need not read ``done`` (a fact blocked
    today may certify tomorrow, once its blocker resolves) — or the review fact
    certifying it by span now; a span that does not certify it today cannot be
    withdrawn ahead of time. A chunk whose ``## Status`` box is
    ticked is refused whatever the fact: the box certifies it in memory after
    any withdrawal, so unticking it comes first. ``fact_id`` omitted on a chunk
    whose certification is already withdrawn answers ``already``, so a re-run
    is idempotent.
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return RetractionTarget("unknown-chunk", f"the plan cannot be read ({exc})")
    plan = _read_plan(content)
    if not plan.scope:
        return RetractionTarget(
            "no-scope", "the plan declares no `scope:`, so no fact certifies its chunks"
        )
    states = chunk_states(plan_path, facts, repo_dir=repo_dir)
    key = next(
        (k for k, st in states.items() if not st.synthetic and _norm(k) == _norm(chunk)), None
    )
    if key is None:
        return RetractionTarget(
            "unknown-chunk", f"`{chunk}` is not a chunk of this plan", plan.scope
        )
    state = states[key]
    store = _store(facts)
    if _norm(key) in plan.ticked:
        # Read after every fact (MG1), a ticked box re-certifies the chunk
        # whatever is withdrawn, and a later `import-status --apply` would mint
        # an import no retraction names.
        return RetractionTarget(
            "box-import",
            f"chunk {key}'s `## Status` box is ticked, and a ticked box certifies it "
            "whatever fact is withdrawn — untick the box first",
            plan.scope, key, fact_id,
        )
    withdrawn = [fid for (fid, n) in retractions(store, plan.scope) if n == _norm(key)]
    if fact_id is None:
        if state.fact_id is None and withdrawn:
            return RetractionTarget(
                "already",
                f"chunk {key} is {state.state}; its certification by {', '.join(withdrawn)} "
                "is already retracted",
                plan.scope, key, withdrawn[-1],
            )
        if state.fact_id is None:
            return RetractionTarget(
                "not-certified",
                f"chunk {key} is {state.state} and no fact certifies it, so there is "
                "nothing to retract (name one with `--fact` to withdraw it before it can certify)",
                plan.scope, key,
            )
        fact_id = state.fact_id
    fact = next(
        (f for kind in ("review", IMPORTED_KIND) for f in evidence.facts_of_kind(store, kind)
         if f.get("id") == fact_id),
        None,
    )
    if fact is None:
        return RetractionTarget(
            "unknown-fact",
            f"no review or chunk-imported fact `{fact_id}` is in the evidence store",
            plan.scope, key, fact_id,
        )
    body = fact.get("body") or {}
    if body.get("scope") != plan.scope:
        return RetractionTarget(
            "other-scope",
            f"`{fact_id}` is a fact of scope `{body.get('scope')}`, not this plan's "
            f"`{plan.scope}`, so it certifies nothing here",
            plan.scope, key, fact_id,
        )
    named = (
        fact_chunks(body) if fact.get("kind") == "review"
        else ([str(body["chunk"])] if body.get("chunk") is not None else [])
    )
    # A fact certifies a chunk it names, or one its interval carries while it
    # is the fact certifying it now (`chunk_states`' span answer).
    by_span = state.state == "done" and state.fact_id == fact_id
    if _norm(key) not in {_norm(c) for c in named} and not by_span:
        return RetractionTarget(
            "not-named",
            f"`{fact_id}` does not name chunk {key} (it names "
            f"{', '.join(named) or 'no chunk'}) and does not certify it by its interval, "
            "so it certifies nothing to retract",
            plan.scope, key, fact_id,
        )
    if (fact_id, _norm(key)) in retractions(store, plan.scope):
        return RetractionTarget(
            "already", f"`{fact_id}`'s certification of chunk {key} is already retracted",
            plan.scope, key, fact_id,
        )
    return RetractionTarget("ok", "", plan.scope, key, fact_id)


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
# Deliverables paths, the diff proposal, and the `built` tag
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


#: Reads a repo-relative path's text at one tree; ``None`` when it cannot.
_ReadAt = Callable[[str], "str | None"]


def _read_at(repo_dir: Path, treeish: str) -> _ReadAt:
    """A reader of paths at ``treeish``, a commit, ref or tree id."""
    def read(rel: str) -> "str | None":
        rc, out, _err = evidence.run_git(repo_dir, "show", f"{treeish}:{rel}", strip=False)
        return out if rc == 0 else None
    return read


def _read_worktree(repo_dir: Path) -> _ReadAt:
    def read(rel: str) -> "str | None":
        try:
            return (repo_dir / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return read


def _work_paths(changed: "set[str]", read: _ReadAt) -> "set[str]":
    """``changed`` less each change fragment that, read at the tree the caller
    judges, is still the stub ``plan new`` mints
    (:func:`change_fragments.is_unwritten_stub`). The stub lands in the plan's
    first commit while a plan's change-record chunk lists the fragment under
    Deliverables, so without this the plan commit reads as that chunk built.
    A fragment that cannot be read at that tree (deleted, or git failed) is
    left out too: on the certifying path that names fewer chunks, which fails
    closed. Every other path stands. Both readers of "which chunks have work"
    — :func:`built_report` and :func:`chunk_proposal` — ask here."""
    def scaffold(rel: str) -> bool:
        if not change_fragments.is_fragment_path(rel):
            return False
        text = read(rel)
        return text is None or change_fragments.is_unwritten_stub(text)
    return {p for p in changed if not scaffold(p)}


@dataclass(frozen=True)
class ChunkProposal:
    """:func:`chunk_proposal`'s answer: the chunks, in plan order, and notes
    for the dispatch to print — each one a reason the proposal named fewer
    than a reader might expect. Advice: no gate reads the notes."""

    chunks: "list[str]"
    notes: "tuple[str, ...]" = ()


def propose_chunks(
    plan_path: Path,
    facts: object,
    diff_paths: "list[str] | set[str]",
    mode: str,
    *,
    repo_dir: Path | None = None,
    since: "str | None" = None,
    head_tree: "str | None" = None,
) -> list[str]:
    """:func:`chunk_proposal`'s chunk list alone, for a caller that prints nothing."""
    return chunk_proposal(
        plan_path, facts, diff_paths, mode, repo_dir=repo_dir, since=since, head_tree=head_tree
    ).chunks


def chunk_proposal(
    plan_path: Path,
    facts: object,
    diff_paths: "list[str] | set[str]",
    mode: str,
    *,
    repo_dir: Path | None = None,
    since: "str | None" = None,
    head_tree: "str | None" = None,
) -> ChunkProposal:
    """The chunks a review dispatched in ``mode`` proposes to name (ST8).

    A mode sets a review's depth, never its reach: every mode proposes only
    chunks there is work for, because the proposal is what the fact names when
    the builder declares nothing, a named chunk is certified (beside what the
    fact's span certifies, ``methodology/planning.md`` "Chunk state"), and a
    certified chunk is never reviewed again. The path and subject halves are
    :func:`_deliverable_chunks` and :func:`_subject_chunks`, the rule a span
    applies too.

    ``chunk`` mode: the open chunks whose Deliverables paths intersect
    ``diff_paths`` (repo-relative; a deliverable directory matches what is
    under it), less a change fragment still the ``plan new`` stub
    (:func:`_work_paths`). ``head_tree`` is the full id of the tree
    ``diff_paths`` ends at, which is where a fragment is read; without one,
    the working tree.
    ``final`` / ``cumulative``: those, and the open chunks a commit subject in
    the review's own commit range names (``since..branch``, ``since`` being the
    interval's base commit; the plan's whole branch when the caller has none)
    — so a mid-plan ``final`` names nothing built before its interval, while
    the boundary ``cumulative``, whose interval starts at the merge-base, spans
    every chunk built so far, including one whose Deliverables name no path
    and which reads as built only by its subject. When the plan declares
    ``scope:``, only a subject carrying that scope counts here, never
    :func:`built_report`'s fallback to every subject: another plan's
    ``Chunk N`` on the branch would certify this plan's. Never
    :func:`built_report`'s path rule either: a later chunk's Deliverable that
    an earlier commit touched reads as built there before anyone builds it. A
    touch inside the review's interval is already the diff's answer. When git
    cannot say, the diff's answer stands alone: naming fewer leaves a chunk
    open, which keeps every gate armed — and a note says so, as one does for a
    chunk only an unscoped subject names. A chunk left out whose Deliverables
    are all bare names (:func:`_bare_only`) is noted in those modes, because
    only a subject can find it. Any other mode proposes nothing.
    ``repo_dir`` defaults to the work tree that holds the plan's
    ``.prawduct/``.

    Only the whole-plan modes walk git (one ``git log``), and they are asked
    only at a review's dispatch; ``chunk`` mode is also asked on the Stop path
    (``critic_mode.extension_deferral_owed``) and stays walk-free: it reads at
    most one file per changed fragment path.
    """
    if mode != "chunk" and mode not in _WHOLE_PLAN_MODES:
        return ChunkProposal([])
    if repo_dir is None:
        repo_dir = _repo_of(Path(plan_path))
    repo_dir = Path(repo_dir)
    open_ids = current_chunks(plan_path, facts, repo_dir=repo_dir)
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ChunkProposal([])
    if head_tree is None:
        read = _read_worktree(repo_dir)
    elif gitstate.is_object_id(head_tree):
        read = _read_at(repo_dir, head_tree)
    else:
        read = lambda _rel: None  # noqa: E731 — never a git argv; every fragment unreadable, naming fewer
    by_path = _deliverable_chunks(
        content, open_ids, _read_plan(content).chunks, (str(p) for p in diff_paths), read
    )
    touched = {c for c in open_ids if _norm(c) in by_path.chunks}
    notes: list[str] = []
    if mode in _WHOLE_PLAN_MODES and open_ids:
        walk = _walk_branch(Path(plan_path), repo_dir, since)
        if isinstance(walk, str):
            notes.append(
                f"no chunk named only by a commit subject is proposed: {walk}"
            )
        elif walk is not None:
            touched |= {c for c in open_ids if _norm(c) in walk.scoped_named}
            unscoped = [
                c for c in open_ids
                if c not in touched and _norm(c) in walk.all_named
            ]
            if unscoped:
                notes.append(
                    f"chunk(s) {', '.join(unscoped)} not proposed: a commit subject names "
                    f"them without this plan's scope `{walk.plan.scope}` "
                    f"(`<type>({walk.plan.scope}): …`), and an unscoped subject may be "
                    "another plan's; pass --chunks if they are this plan's work"
                )
    # Whole-plan modes only: a `chunk` review mid-plan has every later, unbuilt
    # chunk open, and would note each one on every dispatch.
    for c in open_ids if mode in _WHOLE_PLAN_MODES else ():
        if c in touched:
            continue
        bare = _bare_only(deliverable_paths(content, c), repo_dir)
        if bare:
            notes.append(
                f"chunk {c} not proposed: its Deliverables name only bare file names "
                f"({', '.join(f'`{b}`' for b in bare)}), which no path in the diff can equal "
                "and the record lint does not check — write them from the repo root, or "
                "pass --chunks if it is this review's work"
            )
    # A shared path names no chunk; say so when it is why an open owner was left out.
    for path, owners in by_path.shared.items():
        left_out = [c for c in owners if c in open_ids and c not in touched]
        if left_out:
            notes.append(
                f"`{path}` proposes none of chunk(s) {', '.join(owners)}: each lists it under "
                "Deliverables, so a touch cannot say whose work it is — a scoped "
                "`(Chunk N)` subject or --chunks names "
                f"{'it' if len(left_out) == 1 else 'them'}"
            )
    return ChunkProposal([c for c in open_ids if c in touched], tuple(notes))


def _bare_only(deliverables: "list[str]", repo_dir: Path) -> "list[str]":
    """``deliverables`` when every one is a bare name (no ``/``) naming no file
    at the repo root, else ``[]``. Such a chunk can be found only by a commit
    subject naming it: a diff path is repo-relative, and a root-level file is
    the one bare name that is also a path (#1081)."""
    if deliverables and all("/" not in d and not (repo_dir / d).exists() for d in deliverables):
        return deliverables
    return []


def _repo_of(plan_path: Path) -> Path:
    for parent in plan_path.resolve().parents:
        if parent.name == ".prawduct":
            return parent.parent
    return plan_path.resolve().parent


# A subject CARRIES a chunk in one of four anchored forms, in any case — never a
# mention anywhere in it ("…carried to Chunk 04" is prose), and digits-and-dots
# only, so "close Chunk work" names no id. `chunk 01:` (the id then a colon) is a
# form because `<scope> chunk 01: …` is how products write it (#1081). Which
# subjects count has two answers, by what a wrong one costs. A review proposal,
# which certifies, counts only subjects carrying the plan's scope when it
# declares one — as `<type>(<scope>):` or as the subject's first word — because
# another plan's `Chunk N` on the branch must not certify this plan's. The render tag counts a scoped plan's
# scoped subjects too, but when none carries the scope (scope tags are a
# convention, and drift), every subject — a misread table tag is cheap. A plan
# with no scope counts every subject in both. `_subject_chunks` is the rules' one home.
_CHUNK_COMMIT_RE = re.compile(
    r"\(Chunk\s+(\d+(?:\.\d+)*)\)"
    r"|:\s*Chunk\s+(\d+(?:\.\d+)*)\b"
    r"|\bclos(?:e|es|ed)\s+Chunk\s+(\d+(?:\.\d+)*)\b"
    r"|\bChunk\s+(\d+(?:\.\d+)*)\s*:",
    re.IGNORECASE,
)
_COMMIT_SCOPE_RE = re.compile(r"^\w+\(([^)]+)\)!?:")


def _carries_scope(subject: str, scope: str) -> bool:
    """Whether ``subject`` carries ``scope``: as a conventional commit's
    ``<type>(<scope>):``, or as its whole first word (``<scope> chunk 01: …``,
    ``<scope>: …``) — never a word that merely starts with it."""
    m = _COMMIT_SCOPE_RE.match(subject)
    if m:
        return m.group(1).strip() == scope
    return re.match(rf"{re.escape(scope)}(?::|\s)", subject) is not None


def _named_ids(subjects: "Iterable[str]") -> "set[str]":
    """The normalized chunk ids ``subjects`` carry, in :data:`_CHUNK_COMMIT_RE`'s
    anchored forms. Which subjects to pass is the caller's scope rule."""
    return {
        _norm(next(g for g in m.groups() if g is not None))
        for s in subjects
        for m in _CHUNK_COMMIT_RE.finditer(s)
    }

#: Opens each commit's line in the log; file names follow it. Not a control
#: character: `str.strip` treats \x1c-\x1f as whitespace.
_COMMIT_MARK = "@@prawduct-commit@@ "

#: Separates a logged commit's ids from its subject. Read only after the
#: commit mark, so a subject holding it still parses: the split is the first.
_FIELD_SEP = "\x1f"


@dataclass(frozen=True)
class _Commit:
    sha: str
    tree: str
    parents: tuple[str, ...]
    subject: str
    files: frozenset[str]


def _log_commits(repo_dir: Path, *revs: str) -> "list[_Commit] | str":
    """The commits ``git log <revs>`` lists, each with the paths it touched —
    the one reader every chunk-to-commit answer here takes its commits from
    (:func:`_walk_branch`, :class:`_Spans`). A cause string when git fails."""
    rc, out, err = evidence.run_git(
        repo_dir, "log", f"--format={_COMMIT_MARK}%H %T %P{_FIELD_SEP}%s", "--name-only",
        *revs, "--", strip=False,
    )
    if rc != 0:
        detail = (err or "").strip().splitlines()
        return f"`git log {' '.join(revs)}` failed ({detail[0] if detail else f'exit {rc}'})"
    parsed: list[tuple[str, str, tuple[str, ...], str, set[str]]] = []
    for line in out.splitlines():
        if line.startswith(_COMMIT_MARK):
            ids, _sep, subject = line[len(_COMMIT_MARK):].partition(_FIELD_SEP)
            sha, tree, *parents = ids.split()
            parsed.append((sha, tree, tuple(parents), subject, set()))
        elif line.strip() and parsed:
            parsed[-1][4].add(line.strip())
    return [_Commit(s, t, p, subj, frozenset(f)) for s, t, p, subj, f in parsed]


def _subject_chunks(subjects: "Iterable[str]", scope: "str | None", *, fallback: bool = False) -> "set[str]":
    """The normalized chunk ids commit ``subjects`` carry, by the scope rule
    in the comment above :data:`_CHUNK_COMMIT_RE` — its one home. With
    ``scope``, only subjects carrying it count: the certifying rule, which the
    proposal and a span both apply. ``fallback`` is the render tag's rule:
    every subject when none carries the scope."""
    subjects = list(subjects)
    if not scope:
        return _named_ids(subjects)
    scoped = [s for s in subjects if _carries_scope(s, scope)]
    return _named_ids(subjects if fallback and not scoped else scoped)


@dataclass(frozen=True)
class _PathAnswer:
    """:func:`_deliverable_chunks`' answer: the normalized ids credited, and
    each touched path more than one chunk's Deliverables cover, with those
    chunks (as the plan prints them), which the certifying rule credits to none."""

    chunks: "set[str]"
    shared: "dict[str, tuple[str, ...]]"


def _deliverable_chunks(
    content: str,
    chunk_ids: "Iterable[str]",
    plan_chunks: "Iterable[str]",
    paths: "Iterable[str]",
    read: "_ReadAt",
    *,
    certifying: bool = True,
) -> _PathAnswer:
    """The chunks of ``chunk_ids`` that touched ``paths`` attribute work to —
    the path half of the chunk-to-commit rule, the one home every reader of it
    asks. A change fragment still the ``plan new`` stub as ``read`` reads it
    touches nothing (:func:`_work_paths`).

    A path is attributed by who OWNS it among all ``plan_chunks``: every chunk
    whose Deliverables cover it (the path itself, or a directory above it). The
    certifying rule (``certifying``, for the proposal and a span) credits a
    path only to its one owner: a path two chunks list cannot say whose work a
    touch was, and crediting both certified the unbuilt one — such a chunk is
    found by a scoped subject or a naming fact instead. The ``built`` tag,
    which certifies nothing and arms a gate only early, passes
    ``certifying=False`` and credits every owner."""
    changed = _work_paths(set(paths), read)
    deliverables = {c: deliverable_paths(content, c) for c in plan_chunks}
    wanted = {_norm(c) for c in chunk_ids}
    credited: set[str] = set()
    shared: dict[str, tuple[str, ...]] = {}
    for path in sorted(changed):
        owners = tuple(c for c, d in deliverables.items() if _touches(d, {path}))
        if len(owners) > 1:
            shared[path] = owners
            if certifying:
                continue
        credited |= {_norm(c) for c in owners}
    return _PathAnswer(credited & wanted, shared)


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


@dataclass(frozen=True)
class _BranchWalk:
    """One ``git log base..branch`` over a plan's branch, read once for both
    of its answers: which chunks a subject names, and which paths changed."""

    content: str
    plan: _Plan
    head: str  # the ref walked to, where a changed path's text is read
    named: "set[str]"  # normalized ids, by the render rule (scoped, else every subject)
    scoped_named: "set[str]"  # normalized ids a subject carrying the plan's scope names
    all_named: "set[str]"  # normalized ids any subject names
    changed: "set[str]"  # every path a commit on the branch touched


def _walk_branch(
    plan_path: Path, repo_dir: Path, since: "str | None" = None
) -> "_BranchWalk | str | None":
    """The walk :func:`built_report` and :func:`chunk_proposal` answer
    from; a cause string when git or the plan cannot answer; ``None`` for a
    plan with no chunks, which has nothing to walk for.

    ``branch`` is the plan's ``branch:`` when that ref resolves, else ``HEAD``;
    ``base`` is ``since`` when given (a full commit id: a review interval's
    base), else the plan's ``base:`` (``origin/<b>`` preferred), else the
    repo's. A declared ``base:`` that resolves to no ref is a cause, never a
    fallback to the repo's base: that would walk a different interval and
    answer as though it were this one. A subject counts when it carries a
    chunk in one of :data:`_CHUNK_COMMIT_RE`'s anchored forms, filtered by
    scope as that pattern's comment says: ``named`` is the render rule,
    ``scoped_named`` the proposal's, ``all_named`` every subject's.
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"the plan cannot be read ({exc})"
    repo_dir = Path(repo_dir)
    plan = _read_plan(content)
    if not plan.chunks:
        return None
    if since is not None:
        if not gitstate.is_object_id(since):
            return f"the interval's base {since!r} is not a commit id"
        base, cause = since, None
    else:
        base, cause = _resolve_base(repo_dir, content)
    if base is None:
        return cause
    head = plan.branch if plan.branch and coverage._git_ref_exists(repo_dir, plan.branch) else "HEAD"
    commits = _log_commits(repo_dir, f"{base}..{head}")
    if isinstance(commits, str):
        return commits
    subjects = [c.subject for c in commits]
    changed = set().union(*(c.files for c in commits)) if commits else set()
    return _BranchWalk(
        content, plan, head,
        named=_subject_chunks(subjects, plan.scope, fallback=True),
        scoped_named=_subject_chunks(subjects, plan.scope),
        all_named=_named_ids(subjects),
        changed=changed,
    )


def built_report(plan_path: Path, repo_dir: Path) -> BuiltReport:
    """Chunks with work committed on the plan's branch — git-walking, certifying nothing.

    A chunk is built when a commit on ``base..branch`` names it in its subject
    or touches one of its Deliverables paths (:func:`_walk_branch` says which
    commits and subjects count), a change fragment still the ``plan new`` stub
    at the branch head touching nothing (:func:`_work_paths`). Returns the ids
    as the plan prints them. A gate may read it only to ARM itself
    (``critic_mode.short_plan_deferral``), and no review proposal reads it: a
    Deliverables path another chunk's commit touched first reads as built
    here, which a tag and an early arm can afford and a certification cannot
    (:func:`chunk_proposal`).
    """
    walk = _walk_branch(plan_path, repo_dir)
    if walk is None:
        return BuiltReport(set())
    if isinstance(walk, str):
        return BuiltReport(set(), walk)
    built = walk.named | _deliverable_chunks(
        walk.content, walk.plan.chunks, walk.plan.chunks, walk.changed,
        _read_at(Path(repo_dir), walk.head), certifying=False,
    ).chunks
    return BuiltReport({c for c in walk.plan.chunks if _norm(c) in built})


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
