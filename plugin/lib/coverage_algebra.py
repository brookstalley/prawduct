"""Coverage algebra — pure composition over evidence facts (kernel v3, ch.02).

The one question every v3 review gate asks, as a pure function
(``kernel-v3-evidence-design.md`` D4–D6): *does composed review coverage span
tree A → tree B, with zero unresolved blocking findings on the way?* The PR
gate instantiates it as Q1 (merge-base tree → HEAD tree); the Stop-hook
Critic gate as Q2 (session baseline tree → working tree). Mode labels,
`extends_cumulative` chains, demotion special cases, and mtime freshness all
dissolve into this composition — that is the point of the module.

**Purity.** No I/O and no git in here: facts come in as the envelopes
``lib.evidence.read_facts`` returned, and tree-to-tree diffs are supplied by
the caller as ``diff_fn(tree_a, tree_b) -> list[str] | None`` (``None`` =
could not compute — never guessed). Tests inject a table; the gate layer
(chunk 04) injects ``git diff --name-only <a> <b>``.

**The one judgeability predicate.** ``is_judgeable_path`` is the single
answer to "does this file need review coverage?" — the question v2.3.3
answered three divergent ways (``cmd_stop``, ``coverage._pr_diff_is_doc_only``,
``_record_covers_head``), whose disagreement over the metadata boundary was
the CRT-5D8Q deadlock. It composes the two existing canonical sources:
``gitstate.METADATA_PREFIXES`` (framework/session metadata is never
judgeable) and ``buildplan_refs.protected_path_violation`` (a ``.md`` under
``skills/``, ``methodology/``, ``templates/``, or root ``CLAUDE.md`` IS
behavioral logic here — PR-5K8D — so protection overrides the doc carveout).

**Edges (D6).**

- A ``review`` fact contributes edge ``base_tree → head_tree``, valid iff
  every judgeable file it recorded as changed is in its reviewed set — a
  scoped review that saw less than its diff yields NO edge (stricter, never
  looser). A malformed body yields no edge for the same reason.
- The caller's ``diff_fn`` contributes **free edges**: an interval whose
  entire diff is non-judgeable needs no review (the doc-only allowance,
  computed — never stored). "No judgeable path differs" is equality of a
  value each tree has alone, so a caller that supplies ``key_fn`` (a tree →
  judgeable-content digest) gets the same relation from *n* keys instead of
  *n²* diffs; the pairwise form remains as the reference implementation.

**Verdict.** ``covered`` — a path exists using only free edges and facts
with zero unresolved blockers, AND no tree on that path still carries one;
``blocked`` — otherwise, with the surviving findings listed (fixing or
verifying resolutions unblocks without re-review); ``uncovered`` — no path
composes. Resolutions are ``resolution`` facts joined by (review id, finding
id) with disposition ``fixed`` or ``waived`` (D5).

**Findings are a property of nodes, not of edges (CRT-5H2D).** Connectivity
asks "which intervals has review spanned"; the blocker question asks "is the
code at this tree fit to ship". Answering both from the edge set let a
blocking finding recorded on a zero-length interval (``base_tree ==
head_tree``) gate nothing at all — the self-loop is not an edge, so it was
invisible to the phase whose job is to return ``blocked``, and an equal-trees
span short-circuited before the edges were even built. So the verdict sweeps
every review fact standing at a tree on the found path, self-loops included.
Scope is still the path: an abandoned state's findings don't haunt unrelated
coverage, because its tree is not a node the path stands on.
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from . import buildplan_refs
from .gitstate import METADATA_PREFIXES, is_object_id

DiffFn = Callable[[str, str], "list[str] | None"]
KeyFn = Callable[[str], "str | None"]

_RESOLVING_DISPOSITIONS = frozenset({"fixed", "waived"})


def is_judgeable_path(path: str) -> bool:
    """True if a change to ``path`` needs review coverage.

    THE predicate (CRT-5D8Q fix): framework/session metadata is never
    judgeable; a ``.md`` file is judgeable only when governance-protected
    (fork-skill prose is behavioral logic); everything else — code, config,
    data — is judgeable. Deliberately no size or content inspection: paths
    classify, contents don't (do-not-reintroduce: content-hash freshness).

    **Ruled 2026-07-29, after building the exception and reverting it: content
    equivalence cannot relax this, and "the change is only a comment" is not a
    safe exception in THIS repo.** The attempt keyed Python by normalized AST so
    a comment- or docstring-only edit would stay a free edge and cost no review
    pass. It is unsound here for a repo-specific reason no amount of narrowing
    fixes: ``waivers.py`` defines the ``prawduct:allow`` **source-comment**
    pragma and ``compliance.py`` acts on it, so adding
    ``# prawduct:allow prawduct/broad-except -- looks fine`` to an existing
    ``except Exception:`` suppresses a compliance check while leaving the AST
    byte-identical — exactly where ``skills/critic/review-protocol.md`` Goal 3
    obliges a reviewer to judge that waiver. A second channel compounds it:
    tests assert over ``.py`` prose, so docstring edits can break them. AST
    equality proves the *parser* sees the same program, not that the *system*
    behaves the same, and here source is read as text. The failure direction is
    the fatal one — a wrongly granted free edge ships unreviewed code. Prior
    art and the standing item: ``COV-3M8Q``. The sound way to stop paying for
    behaviour-neutral edits is to make review *cheap*, not skippable.
    """
    if any(path.startswith(p) for p in METADATA_PREFIXES):
        return False
    if path.endswith(".md"):
        return buildplan_refs.protected_path_violation(path) is not None
    return True


def judgeable_files(paths: "list[str] | None") -> list[str]:
    """The judgeable subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_judgeable_path(p)]


#: Live repo state that a NON-HERMETIC test in this repo reads (COV-4H7N).
#:
#: A named inventory, deliberately not a ``.prawduct/**`` rule. These paths are
#: not judgeable — editing one needs no Critic review — but a change to one CAN
#: flip a test red, because a test reads the committed file rather than a
#: fixture. Observed: PR #125 changed only ``.prawduct/*.md`` plus
#: ``project-state.yaml``; ``check-pr-doc-only`` took the fast path (no Critic,
#: no PR review, no suite) and ``test-status`` read *current*, while
#: ``tests/test_norm_probes.py::TestSilentAgainstThisRepo`` reads the live
#: ``project-state.yaml`` — so ratifying the norm registry broke develop
#: silently, and only an unrelated branch's suite run found it.
#:
#: Membership rule, so this stays an inventory rather than a drift-collector:
#: a path belongs here when a repo-coupled test asserts a CONTENT property of
#: it AND the file is low-churn framework configuration.
#:
#: - ``project-state.yaml`` — ``test_norm_probes.TestSilentAgainstThisRepo``
#:   requires every norm-lifecycle probe to stay silent against it, and
#:   ``test_audit_learnings`` requires a ``sentinel_command:`` spelled with the
#:   canonical placeholder.
#: - ``cross-cutting-concerns.md`` — ``test_v5_methodology.TestCrossCuttingConcerns``
#:   pins named sections and references in it.
#:
#: **The residual, stated rather than implied.** ``backlog.md``,
#: ``change-log.md``, ``learnings.md`` and ``artifacts/**`` are ALSO read by
#: repo-coupled tests (``test_backlog_parser`` pins an item id;
#: ``test_change_log`` pins the tagged/untagged split, the scope-to-plan join
#: and same-line duplicates). They are held out on cost, not on principle: all
#: four are written as ordinary bookkeeping in nearly every session, and a
#: change-log entry is written LATE by construction because the PR gate demands
#: one — so suite-coupling them would tax every PR with a re-run after the
#: bookkeeping. The sound close for those is to make their tests hermetic
#: (COV-4H7N option c proper), not to widen this set.
TEST_COUPLED_STATE = frozenset(
    {
        ".prawduct/project-state.yaml",
        ".prawduct/cross-cutting-concerns.md",
    }
)


def affects_test_outcome(path: str) -> bool:
    """True if a change to ``path`` can change what the test suite says.

    A strict superset of :func:`is_judgeable_path`, and the distinction is the
    point. "Does this need review coverage?" and "can this flip a test red?"
    are different questions that the metadata boundary answers differently:
    framework state needs no reviewer, and a non-hermetic test still reads it.
    Conflating them is what let a state-only PR skip the suite AND read its
    stale evidence as current (COV-4H7N).

    Kept as a second function rather than a second rule inside
    :func:`is_judgeable_path` because review coverage must NOT widen here: the
    ``_BATCH_FIX_DIRECTIVE`` tells a builder that ``.prawduct/`` writes are
    free mid-review, and that promise stays true.
    """
    return is_judgeable_path(path) or path in TEST_COUPLED_STATE


def suite_coupled_files(paths: "list[str] | None") -> list[str]:
    """The subset of ``paths`` a test outcome can depend on (order preserved,
    None-safe) — :func:`affects_test_outcome` over :func:`judgeable_files`."""
    return [p for p in (paths or []) if affects_test_outcome(p)]


# ---------------------------------------------------------------------------
# Findings / resolutions join (D5)
# ---------------------------------------------------------------------------


def blocking_findings(review_fact: dict) -> list[dict]:
    """The BLOCKING findings a review fact carries (case-insensitive on
    severity; malformed findings entries are ignored — they cannot *satisfy*
    anything, and treating garbage as blocking would let a corrupt entry
    wedge a gate forever with nothing actionable to resolve)."""
    body = review_fact.get("body") or {}
    findings = body.get("findings")
    if not isinstance(findings, list):
        return []
    out = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if isinstance(severity, str) and severity.strip().upper() == "BLOCKING":
            out.append(finding)
    return out


def resolution_index(facts: list[dict]) -> set[tuple[str, str]]:
    """(review id, finding id) pairs resolved by ``resolution`` facts with a
    recognized disposition. Unknown dispositions resolve nothing (fail toward
    stricter — escape hatches in classification create silent failures)."""
    resolved: set[tuple[str, str]] = set()
    for fact in facts:
        if fact.get("kind") != "resolution":
            continue
        body = fact.get("body") or {}
        target = body.get("finding") or {}
        review_id = target.get("review_id")
        fid = target.get("fid")
        disposition = body.get("disposition")
        if (
            isinstance(review_id, str)
            and isinstance(fid, str)
            and isinstance(disposition, str)
            and disposition in _RESOLVING_DISPOSITIONS
        ):
            resolved.add((review_id, fid))
    return resolved


def unresolved_blocking(review_fact: dict, resolved: set[tuple[str, str]]) -> list[dict]:
    """Blocking findings of ``review_fact`` not resolved by ``resolved``.
    A blocking finding without a usable ``fid`` can never be matched by a
    resolution fact, so it stays unresolved forever by construction — the
    writer (chunk 03) must always assign fids."""
    review_id = review_fact.get("id")
    out = []
    for finding in blocking_findings(review_fact):
        fid = finding.get("fid")
        if not isinstance(fid, str) or (review_id, fid) not in resolved:
            out.append(finding)
    return out


# ---------------------------------------------------------------------------
# Edges (D6)
# ---------------------------------------------------------------------------


def review_edges(facts: list[dict]) -> list[dict]:
    """Valid edges from ``review`` facts:
    ``{"src", "dst", "fact"}``. Validity — the fact recorded both trees as
    full-length git object ids and every judgeable changed file is within its
    reviewed set; anything less yields no edge (a partial or malformed fact
    must weaken coverage, never strengthen it).

    The tree ids are shape-checked here rather than trusted because facts are
    read back from a plain file on disk: a corrupted or hand-edited one can
    carry any string, and these values become git argv downstream. Rejecting
    the edge is the same direction as every other malformedness in this
    function — it costs coverage, so it can only ever demand more review.

    Rejection here is **silent by construction**: this module is pure (no I/O,
    see the module docstring), so it has no channel to attribute on. The
    attribution belongs to the layer that owns the store, and
    ``evidence.tree_diff``/``tree_entries`` emit it when the same malformed id
    reaches the git boundary — see ``evidence._attribute_bad_tree``."""
    edges = []
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        src = body.get("base_tree")
        dst = body.get("head_tree")
        files_changed = body.get("files_changed")
        files_reviewed = body.get("files_reviewed")
        if not (
            is_object_id(src)
            and is_object_id(dst)
            and isinstance(files_changed, list)
            and isinstance(files_reviewed, list)
        ):
            continue
        reviewed = {f for f in files_reviewed if isinstance(f, str)}
        changed = [f for f in files_changed if isinstance(f, str)]
        if any(f not in reviewed for f in judgeable_files(changed)):
            continue  # under-reviewed interval — not an edge
        if src == dst:
            # Degenerate interval: contributes nothing to *connectivity* that
            # the node does not already give. It still carries findings, and
            # those are swept by `_unresolved_at_nodes` at verdict time —
            # CRT-5H2D, where dropping the edge dropped the payload with it.
            continue
        edges.append({"src": src, "dst": dst, "fact": fact})
    return edges


def _free_edge_files(diff_fn: DiffFn, src: str, dst: str) -> "list[str] | None":
    """The interval's diff when it qualifies as a free edge (entirely
    non-judgeable), else ``None``. A ``diff_fn`` failure (``None``) is never
    a free edge — unknown diffs don't get free passes."""
    files = diff_fn(src, dst)
    if files is None:
        return None
    if judgeable_files(files):
        return None
    return files


def _free_classes(nodes: "set[str]", key_fn: KeyFn) -> dict[str, list[str]]:
    """Free-edge adjacency derived from per-tree keys instead of pairwise
    probing — the linear form of the same relation.

    A free edge ``a → b`` exists iff the interval's diff holds no judgeable
    path, i.e. iff ``a`` and ``b`` agree on every judgeable ``(path, blob)``.
    That is equality of a value each tree has on its own, so a caller that
    can key a tree by its judgeable content turns *n²* diffs into *n* keys:
    equal keys ⇒ mutually free-connected, and each key class is a clique.

    A tree whose key cannot be computed (``None`` — unreadable object, git
    failure) joins no class and so gets no free edge, matching
    :func:`_free_edge_files`'s refusal to grant one on a failed diff. Speed
    must never buy a free pass; the fast path fails in the same direction as
    the slow one.
    """
    classes: dict[str, list[str]] = {}
    for node in nodes:
        key = key_fn(node)
        if key is None:
            continue
        classes.setdefault(key, []).append(node)
    adjacency: dict[str, list[str]] = {}
    for members in classes.values():
        if len(members) < 2:
            continue
        for member in members:
            adjacency[member] = [o for o in members if o != member]
    return adjacency


def _attribute_free_steps(path: list[dict], diff_fn: DiffFn) -> list[dict]:
    """Fill in the ``files`` a ``free`` step reports, for the steps on a
    *found* path only.

    Key-derived free edges know an interval is free without having listed
    its files, and the verdict's path carries that list for attribution. The
    diff is therefore deferred to here — O(path length) calls rather than one
    per candidate examined, which is the whole point of the key form. An
    unavailable diff degrades to ``[]``: the key already established the
    interval is free, so attribution detail may be missing but the verdict
    may not change.
    """
    for step in path:
        if step.get("kind") == "free" and "files" not in step:
            step["files"] = diff_fn(step["src"], step["dst"]) or []
    return path


# ---------------------------------------------------------------------------
# The verdict (Q1/Q2)
# ---------------------------------------------------------------------------


def _path_nodes(base_tree: str, path: list[dict]) -> set[str]:
    """Every tree the composed ``path`` stands at — the base plus each step's
    endpoints. ``path == []`` (the degenerate span) still yields ``{base}``,
    which is what makes the equal-trees short-circuit answerable."""
    nodes = {base_tree}
    for step in path:
        for end in (step.get("src"), step.get("dst")):
            if isinstance(end, str) and end:
                nodes.add(end)
    return nodes


def _facts_at_nodes(facts: list[dict], nodes: "set[str]") -> list[dict]:
    """Review facts recorded *at* one of ``nodes`` — head_tree lands there.

    Edge validity is deliberately NOT required. A fact whose reviewed set was
    narrower than its diff yields no edge (it cannot vouch for an interval),
    but the blocking findings it *did* record are real and must still weigh;
    validity gates what evidence proves, never what it accuses. Self-loops
    (``base_tree == head_tree``) land here too, which is the whole point:
    ``review_edges`` drops them for connectivity, so this is where their
    payload re-enters (CRT-5H2D).
    """
    out = []
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        head = body.get("head_tree")
        if isinstance(head, str) and head in nodes:
            out.append(fact)
    return out


def _verify_anchor_id(facts: list[dict], nodes: "set[str]") -> "str | None":
    """The review fact at one of ``nodes`` that a verify-resolutions pass would
    anchor to: the most recently appended one. ``None`` when no review fact
    stands at any node on the path.

    This is what makes a blocking finding *reachable*. A verify pass reviews
    the delta from one prior fact and records resolutions against that fact
    alone, so a blocker carried by any OTHER fact on the path is one no verify
    pass will ever name again — it is superseded, and only a review spanning
    the whole interval can supply a clean path around it.

    Two deliberate choices, because both directions of error are wrong advice:

    - **Appended order, not the derived findings cache.** The dispatcher finds
      its anchor through that cache's pointer, but no gate may read it (D7),
      and it is per-worktree while facts are the shared truth. The store is
      append-only and :func:`evidence.read_facts` preserves that order, so the
      last review fact IS the newest one.
    - **Restricted to the path's nodes, not the whole store.** The store is
      shared by every worktree of the clone, so a sibling's newer review would
      otherwise make a perfectly reachable finding look stranded. A fact
      standing at a tree on this path is on this interval's lineage by
      construction — and every review *step* on the path is such a fact, since
      a step's ``dst`` IS its fact's ``head_tree``, so this is a superset of
      the path-step reading rather than a different one.

    **The residual, stated rather than implied.** This is a faithful *proxy*
    for the dispatcher's anchor, not the same value. Should the cache point at
    a fact that is not on the composed path, an on-path blocker is reported
    reachable and the message prescribes a verify pass that will demote rather
    than clear it — the original defect in a narrower case. Nothing detects
    that, and nothing here can: reading the cache to check is the very thing
    D7 forbids a gate to do. It stays a proxy because the failure is soft (the
    verdict never moves, only the advice) and because closing it properly means
    giving the anchor a home in the shared store, which is a larger change than
    a message correction.
    """
    newest = None
    for fact in _facts_at_nodes(facts, nodes):
        newest = fact.get("id")
    return newest


def _unresolved_at_nodes(
    facts: list[dict], resolved: set[tuple[str, str]], nodes: "set[str]"
) -> list[dict]:
    """Every unresolved blocking finding recorded at a tree on the path.

    This is the composition-side answer to CRT-5H2D. Connectivity and findings
    were previously answered by one edge set, and that conflation is what let a
    blocker on a zero-length interval gate nothing: ``review_edges`` drops the
    self-loop before either search phase runs, and ``coverage_verdict``
    short-circuits an equal-trees span before the edges are built at all. Both
    doors close by asking the findings question of the *nodes* the verdict
    stands on rather than of the edges it traversed.

    The widening is deliberate and load-bearing beyond self-loops: a blocker
    recorded at a tree the path passes through counts even when the path
    routed around its edge (over a free edge, or over a second review of the
    same interval). A blocking finding says "the code at this tree is not fit
    to ship"; a *different* fact reaching the same tree does not make that
    untrue. Clearing it takes a resolution fact — ``fixed`` or ``waived`` — or
    a spanning review that never stands at the tree in question. This is
    strictly stricter than the pre-CRT-5H2D reading, which is the only safe
    direction for a gate that had been reporting ``satisfied`` while the store
    held an unresolved blocker.
    """
    anchor = _verify_anchor_id(facts, nodes)
    entries = []
    for fact in _facts_at_nodes(facts, nodes):
        for finding in unresolved_blocking(fact, resolved):
            entry = {
                "review_id": fact.get("id"),
                "superseded": fact.get("id") != anchor,
            }
            entry.update(
                {
                    k: finding.get(k)
                    for k in ("fid", "severity", "title", "files")
                    if k in finding
                }
            )
            entries.append(entry)
    return entries


def coverage_verdict(
    facts: list[dict],
    base_tree: str,
    target_tree: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None" = None,
) -> dict:
    """Does composed coverage span ``base_tree → target_tree`` with zero
    unresolved blocking findings?

    Returns::

        {"status": "covered",   "path": [step, ...]}
      | {"status": "blocked",   "path": [step, ...], "unresolved": [
            {"review_id", "fid", "title", "superseded", ...}, ...]}
      | {"status": "uncovered", "reason": str}

    Path steps are ``{"kind": "review", "id", "src", "dst"}`` or
    ``{"kind": "free", "src", "dst", "files"}`` — enough for a gate message
    to attribute exactly which evidence vouched for what.

    Search is two-phase: first over blocker-free facts + free edges; then over
    all valid edges; neither = ``uncovered``. A path found by either phase is
    then settled by :func:`_unresolved_at_nodes` — ``covered`` only if no tree
    it stands on still carries an unresolved blocker, ``blocked`` otherwise
    (fix/verify them and the same evidence passes, no re-review). The equal-
    trees span skips the search but not the settlement: it has one node, and a
    node can carry findings (CRT-5H2D).

    Each unresolved entry carries ``superseded``: True when its fact is not the
    one a verify-resolutions pass would anchor to (:func:`_verify_anchor_id`),
    which means no verify pass will revisit it and only a spanning review can
    clear it. Gate messages need this to avoid prescribing a route the operator
    cannot take; the verdict itself is unaffected — a blocker blocks either way.
    """
    if not isinstance(base_tree, str) or not base_tree:
        return {"status": "uncovered", "reason": "no base tree to compose from"}
    if not isinstance(target_tree, str) or not target_tree:
        return {"status": "uncovered", "reason": "no target tree to compose to"}
    resolved = resolution_index(facts)

    def _settle(path: list[dict]) -> dict:
        """``covered`` unless a tree on ``path`` still carries a blocker."""
        unresolved = _unresolved_at_nodes(
            facts, resolved, _path_nodes(base_tree, path)
        )
        if unresolved:
            return {"status": "blocked", "path": path, "unresolved": unresolved}
        return {"status": "covered", "path": path}

    if base_tree == target_tree:
        # A zero-length span still has a node, and a node can carry findings.
        return _settle([])

    edges = review_edges(facts)
    clean_edges = [
        e for e in edges if not unresolved_blocking(e["fact"], resolved)
    ]

    path = _find_path(clean_edges, base_tree, target_tree, diff_fn, key_fn)
    if path is not None:
        return _settle(path)

    path = _find_path(edges, base_tree, target_tree, diff_fn, key_fn)
    if path is not None:
        settled = _settle(path)
        if settled["status"] == "covered":
            # Unreachable by construction — this phase only finds a path the
            # clean-edge phase could not, so it used an edge whose fact carries
            # an unresolved blocker, and that fact stands at a node on the
            # path. Kept explicit rather than asserted: a search that somehow
            # disagreed must not be reported as coverage the first phase
            # already refused.
            return {"status": "blocked", "path": path, "unresolved": []}
        return settled

    return {
        "status": "uncovered",
        "reason": (
            f"no evidence path composes from {base_tree[:12]} to "
            f"{target_tree[:12]} — a review at the current tree closes the gap"
        ),
    }


def _find_path(
    edges: list[dict],
    src: str,
    dst: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None" = None,
) -> "list[dict] | None":
    """BFS from ``src`` to ``dst`` over review edges plus free edges between
    known nodes. Nodes are the trees the evidence mentions plus the two
    endpoints — free edges between *unknown* trees can't help because nothing
    connects them to anything.

    Free edges come from ``key_fn`` when one is supplied (``_free_classes`` —
    *n* keys, the form every gate uses) and from pairwise ``diff_fn`` probing
    otherwise (*n²* diffs, retained as the reference implementation the
    injected-table tests exercise). The two agree by construction: both
    decide "no judgeable path differs", one per tree and one per pair.
    """
    nodes = {src, dst}
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        nodes.add(edge["src"])
        nodes.add(edge["dst"])
        adjacency.setdefault(edge["src"], []).append(
            {
                "kind": "review",
                "id": edge["fact"].get("id"),
                "src": edge["src"],
                "dst": edge["dst"],
            }
        )

    free_adjacency = _free_classes(nodes, key_fn) if key_fn is not None else None

    visited = {src}
    queue: deque[tuple[str, list[dict]]] = deque([(src, [])])
    probed: set[tuple[str, str]] = set()
    while queue:
        node, path = queue.popleft()
        if node == dst:
            return _attribute_free_steps(path, diff_fn)
        for step in adjacency.get(node, []):
            if step["dst"] not in visited:
                visited.add(step["dst"])
                queue.append((step["dst"], path + [step]))
        if free_adjacency is not None:
            for other in free_adjacency.get(node, ()):
                if other in visited:
                    continue
                visited.add(other)
                queue.append(
                    (other, path + [{"kind": "free", "src": node, "dst": other}])
                )
            continue
        for other in nodes:
            if other in visited or (node, other) in probed:
                continue
            probed.add((node, other))
            files = _free_edge_files(diff_fn, node, other)
            if files is None:
                continue
            visited.add(other)
            queue.append(
                (
                    other,
                    path
                    + [{"kind": "free", "src": node, "dst": other, "files": files}],
                )
            )
    return None
