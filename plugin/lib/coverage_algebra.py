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
  computed — never stored).

**Verdict.** ``covered`` — a path exists using only free edges and facts
with zero unresolved blockers; ``blocked`` — every path carries a fact with
unresolved blocking findings (they are listed; fixing or verifying
resolutions unblocks without re-review); ``uncovered`` — no path composes.
Resolutions are ``resolution`` facts joined by (review id, finding id) with
disposition ``fixed`` or ``waived`` (D5); only facts on the used path count
(an abandoned state's findings don't haunt unrelated coverage).
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from . import buildplan_refs
from .gitstate import METADATA_PREFIXES

DiffFn = Callable[[str, str], "list[str] | None"]

_RESOLVING_DISPOSITIONS = frozenset({"fixed", "waived"})


def is_judgeable_path(path: str) -> bool:
    """True if a change to ``path`` needs review coverage.

    THE predicate (CRT-5D8Q fix): framework/session metadata is never
    judgeable; a ``.md`` file is judgeable only when governance-protected
    (fork-skill prose is behavioral logic); everything else — code, config,
    data — is judgeable. Deliberately no size or content inspection: paths
    classify, contents don't (do-not-reintroduce: content-hash freshness).
    """
    if any(path.startswith(p) for p in METADATA_PREFIXES):
        return False
    if path.endswith(".md"):
        return buildplan_refs.protected_path_violation(path) is not None
    return True


def judgeable_files(paths: "list[str] | None") -> list[str]:
    """The judgeable subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_judgeable_path(p)]


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
    ``{"src", "dst", "fact"}``. Validity — the fact recorded both trees and
    every judgeable changed file is within its reviewed set; anything less
    yields no edge (a partial or malformed fact must weaken coverage, never
    strengthen it)."""
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
            isinstance(src, str)
            and src
            and isinstance(dst, str)
            and dst
            and isinstance(files_changed, list)
            and isinstance(files_reviewed, list)
        ):
            continue
        reviewed = {f for f in files_reviewed if isinstance(f, str)}
        changed = [f for f in files_changed if isinstance(f, str)]
        if any(f not in reviewed for f in judgeable_files(changed)):
            continue  # under-reviewed interval — not an edge
        if src == dst:
            continue  # degenerate; contributes nothing a node doesn't
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


# ---------------------------------------------------------------------------
# The verdict (Q1/Q2)
# ---------------------------------------------------------------------------


def coverage_verdict(
    facts: list[dict],
    base_tree: str,
    target_tree: str,
    diff_fn: DiffFn,
) -> dict:
    """Does composed coverage span ``base_tree → target_tree`` with zero
    unresolved blocking findings?

    Returns::

        {"status": "covered",   "path": [step, ...]}
      | {"status": "blocked",   "path": [step, ...], "unresolved": [
            {"review_id", "fid", "title", ...}, ...]}
      | {"status": "uncovered", "reason": str}

    Path steps are ``{"kind": "review", "id", "src", "dst"}`` or
    ``{"kind": "free", "src", "dst", "files"}`` — enough for a gate message
    to attribute exactly which evidence vouched for what.

    Search is two-phase: first over blocker-free facts + free edges (success
    = ``covered``); then over all valid edges (success = ``blocked``, listing
    the unresolved findings of the path found — fix/verify them and the same
    evidence passes, no re-review); neither = ``uncovered``.
    """
    if not isinstance(base_tree, str) or not base_tree:
        return {"status": "uncovered", "reason": "no base tree to compose from"}
    if not isinstance(target_tree, str) or not target_tree:
        return {"status": "uncovered", "reason": "no target tree to compose to"}
    if base_tree == target_tree:
        return {"status": "covered", "path": []}

    edges = review_edges(facts)
    resolved = resolution_index(facts)
    clean_edges = [
        e for e in edges if not unresolved_blocking(e["fact"], resolved)
    ]

    path = _find_path(clean_edges, base_tree, target_tree, diff_fn)
    if path is not None:
        return {"status": "covered", "path": path}

    path = _find_path(edges, base_tree, target_tree, diff_fn)
    if path is not None:
        unresolved = []
        for step in path:
            if step["kind"] != "review":
                continue
            fact = next(
                e["fact"] for e in edges if e["fact"].get("id") == step["id"]
            )
            for finding in unresolved_blocking(fact, resolved):
                entry = {"review_id": fact.get("id")}
                entry.update(
                    {
                        k: finding.get(k)
                        for k in ("fid", "severity", "title", "files")
                        if k in finding
                    }
                )
                unresolved.append(entry)
        return {"status": "blocked", "path": path, "unresolved": unresolved}

    return {
        "status": "uncovered",
        "reason": (
            f"no evidence path composes from {base_tree[:12]} to "
            f"{target_tree[:12]} — a review at the current tree closes the gap"
        ),
    }


def _find_path(
    edges: list[dict], src: str, dst: str, diff_fn: DiffFn
) -> "list[dict] | None":
    """BFS from ``src`` to ``dst`` over review edges plus lazily-probed free
    edges between known nodes. Nodes are the trees the evidence mentions plus
    the two endpoints — free edges between *unknown* trees can't help because
    nothing connects them to anything."""
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

    visited = {src}
    queue: deque[tuple[str, list[dict]]] = deque([(src, [])])
    probed: set[tuple[str, str]] = set()
    while queue:
        node, path = queue.popleft()
        if node == dst:
            return path
        for step in adjacency.get(node, []):
            if step["dst"] not in visited:
                visited.add(step["dst"])
                queue.append((step["dst"], path + [step]))
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
