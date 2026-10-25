"""Chunk status as a query — the one walker of a plan's progress (#1051).

"Is chunk N done" and "is this plan finished" each have one answer, derived
from the facts the Critic already writes, never from a hand-ticked box or a
commit (``1050-design.md`` § 3). Every consumer takes the answer computed here
and none re-derives it:

- :func:`chunk_states` — each chunk's state, ``open``, ``done`` or ``dropped``;
- :func:`is_finished` — every chunk ``done`` or ``dropped`` (the only function
  answering "finished");
- :func:`current_chunks` — the ``open`` chunks, in plan order;
- :func:`built_chunks` — a RENDERING convenience, the one git-walking function
  here; no gate reads it and :func:`chunk_states` never calls it;
- :func:`propose_chunks` — the chunk set a review dispatch proposes (ST8).

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
<reason>``. The reason is required.

**Authority fails closed** (``architecture.md`` § Direction): what cannot be
read leaves a chunk ``open``, which keeps every gate armed. An unreadable
``dropped:`` entry drops nothing; a review fact whose blocking findings cannot
all be read certifies nothing; an anchor git cannot place completes nothing; a
plan file that cannot be read answers with one open :data:`UNREADABLE_PLAN`
entry rather than the empty mapping, which would read as finished; and a chunk
heading the parser rejects is an open chunk of its own rather than an absence.

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
from typing import Literal

from . import buildplan_refs, core, coverage, dispositions, evidence, gitstate, plan_index, work_unit

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
    """

    state: State
    fact_id: str | None = None
    date: str | None = None
    imported: bool = False
    reason: str | None = None


# ---------------------------------------------------------------------------
# The plan: chunk ids, scope, branches, dropped declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Plan:
    chunks: tuple[str, ...]  # ids as the plan prints them, plan order
    unparsed: tuple[tuple[str, str], ...]  # (key, heading) rejected headings
    scope: str | None
    branches: tuple[str, ...]
    dropped: dict[str, str]  # normalized id -> reason
    dropped_faults: dict[str, str]  # normalized id -> why its entry is unreadable
    ticked: frozenset[str]  # normalized ids of ticked Status boxes


def _norm(chunk_id: object) -> str:
    return buildplan_refs._normalize_chunk_id(str(chunk_id))


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
    branch = plan_index.parse_build_plan_frontmatter_branch(content)
    working = work_unit._working_branches(fm) or ()
    branches = tuple(
        dict.fromkeys(b for b in (branch, *working) if b and not b.startswith("-"))
    )
    dropped, faults = _read_dropped(fm)
    return _Plan(tuple(chunks), unparsed, scope, branches, dropped, faults, frozenset(ticked))


def _read_dropped(fm: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """``(dropped, faults)`` from the frontmatter's ``dropped:`` block.

    One form: a block sequence of ``- <id>: <reason>``. A declaration the
    sequence reader cannot read whole drops nothing; an item whose id reads but
    whose reason is empty drops nothing and is reported against that id.
    """
    status, items = core.read_block_sequence("\n".join(fm), DROPPED_KEY)
    if status != core.YAML_DECLARED:
        return {}, {}
    dropped: dict[str, str] = {}
    faults: dict[str, str] = {}
    for item in items:
        raw_id, colon, reason = item.partition(":")
        chunk_id = core.unquote_scalar(raw_id.strip())
        reason = core.unquote_scalar(reason.strip())
        if not _DROPPED_ID_RE.match(chunk_id):
            continue  # names no chunk this reader can identify: drops nothing
        if not colon or not reason:
            faults[_norm(chunk_id)] = (
                f"`{DROPPED_KEY}:` entry for {chunk_id} gives no reason "
                f"(write `- {chunk_id}: <reason>`), so it drops nothing"
            )
            continue
        dropped[_norm(chunk_id)] = reason
    return dropped, faults


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


def _store(facts: object) -> dict:
    """A ``read_facts`` result; a bare envelope list is accepted and wrapped."""
    if isinstance(facts, dict):
        return facts
    if isinstance(facts, list):
        return {"facts": facts}
    return {"facts": []}


def fact_chunks(body: dict) -> list[str]:
    """The chunk ids a review fact names — the one reader rule for the field.

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

    ``facts`` is an ``evidence.read_facts`` result (a bare envelope list is
    accepted). ``repo_dir`` is the work tree git runs in for the reachability
    probe. A plan with no chunks answers ``{}``; an unreadable plan answers
    ``{UNREADABLE_PLAN: open}``; each heading the chunk parser rejects is an
    open chunk keyed ``?L<line>``. Never raises; never walks git history and
    never calls :func:`built_chunks` (module docstring, NF1).
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {UNREADABLE_PLAN: ChunkState("open", reason=f"plan unreadable ({exc})")}
    plan = _read_plan(content)
    store = _store(facts)

    states: dict[str, ChunkState] = {}
    by_norm: dict[str, str] = {}
    for chunk_id in plan.chunks:
        by_norm[_norm(chunk_id)] = chunk_id
        states[chunk_id] = ChunkState("open", reason=plan.dropped_faults.get(_norm(chunk_id)))

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
            anchor = body.get("head_commit") or body.get("dispatch_commit")
            if not gitstate.is_object_id(anchor) or not plan.branches or not reachable(anchor):
                where = " or ".join(f"`{b}`" for b in plan.branches) or "no declared branch"
                for n in targets:
                    note(n, f"review {fact['id']} names it, but its commit is not on {where}")
                continue
            for n in targets:
                states[by_norm[n]] = ChunkState("done", fact["id"], _date(fact.get("ts")))

    for key, heading in plan.unparsed:
        states[key] = ChunkState(
            "open",
            reason=f"{buildplan_refs.UNPARSED_HEADING_MARKER}: `{heading}` is not a chunk "
            "heading the parser reads, so it cannot be certified — fix the heading",
        )
    return states


def is_finished(plan_path: Path, facts: object, *, repo_dir: Path) -> bool:
    """Every chunk ``done`` or ``dropped``. A plan with no chunks is finished."""
    states = chunk_states(plan_path, facts, repo_dir=repo_dir)
    return all(s.state != "open" for s in states.values())


def current_chunks(plan_path: Path, facts: object, *, repo_dir: Path) -> list[str]:
    """The ``open`` chunks, in plan order."""
    states = chunk_states(plan_path, facts, repo_dir=repo_dir)
    return [chunk_id for chunk_id, s in states.items() if s.state == "open"]


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
    for path in deliverables:
        prefix = path.rstrip("/") + "/"
        if path in changed or any(c.startswith(prefix) for c in changed):
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


# Copied from `buildplan_refs._committed_chunk_ids`' rule (Chunk 06 deletes the
# original): a subject CARRIES a chunk in one of three anchored forms, and a
# plan whose scope some commit carries counts only its scoped commits.
_CHUNK_COMMIT_RE = re.compile(
    r"\(Chunk\s+(\d+(?:\.\d+)*)\)"
    r"|:\s*Chunk\s+(\d+(?:\.\d+)*)\b"
    r"|\bclos(?:e|es|ed)\s+Chunk\s+(\d+(?:\.\d+)*)\b"
)
_COMMIT_SCOPE_RE = re.compile(r"^\w+\(([^)]+)\)!?:")
#: Opens each commit's subject line in the log; file names follow it. Not a
#: control character: `str.strip` treats \x1c-\x1f as whitespace.
_COMMIT_MARK = "@@prawduct-commit@@ "


def built_chunks(plan_path: Path, repo_dir: Path) -> set[str]:
    """Chunks with work committed on the plan's branch — render-only, git-walking.

    A chunk is built when a commit on ``base..branch`` names it in its subject
    (``_committed_chunk_ids``' three anchored forms and its scope filter) or
    touches one of its Deliverables paths. ``branch`` is the plan's ``branch:``
    when that ref resolves, else ``HEAD``; ``base`` is the plan's ``base:``
    (``origin/<b>`` preferred), else the repo's. Returns the ids as the plan
    prints them; ``set()`` when the plan or git cannot be read. No gate reads it.
    """
    try:
        content = Path(plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    repo_dir = Path(repo_dir)
    plan = _read_plan(content)
    if not plan.chunks:
        return set()
    base = None
    declared_base = plan_index.parse_build_plan_frontmatter_base(content)
    if declared_base and not declared_base.startswith("-"):
        base = next(
            (r for r in (f"origin/{declared_base}", declared_base)
             if coverage._git_ref_exists(repo_dir, r)),
            None,
        )
    if base is None:
        base, _why = coverage.repo_base_branch(repo_dir)
    if base is None:
        return set()
    branch = plan_index.parse_build_plan_frontmatter_branch(content)
    head = branch if branch and coverage._git_ref_exists(repo_dir, branch) else "HEAD"
    rc, out, _err = evidence.run_git(
        repo_dir, "log", f"--format={_COMMIT_MARK}%s", "--name-only", f"{base}..{head}", "--",
        strip=False,
    )
    if rc != 0:
        return set()
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
    return {
        c for c in plan.chunks
        if _norm(c) in named or _touches(deliverable_paths(content, c), changed)
    }
