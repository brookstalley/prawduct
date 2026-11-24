"""Which release-pending merges did a boundary review cover? (#1223, wave 1)

A per-release boundary review is only safe if, at the release, something can name
the merged work no boundary review read. This module is that one answer. For each
release-pending scope (``release_readiness.pending_scopes``) it finds the
first-parent commit on the integration base that added the scope's fragment, and
classifies that commit:

- ``no-judgeable``: its span changes no judgeable file
  (``coverage_algebra.is_judgeable_path``).
- ``pr-covered``: the branch it merged was covered by a boundary review at its PR.
  That means coverage composes over the branch's span with no open blocker, and
  some boundary-stage review ``B`` splits the span in two:
  - boundary-stage edges alone compose the span's base to ``B``'s head tree;
  - ``verify-resolutions`` edges (and free edges) alone compose ``B``'s head tree to
    the branch tip.

  The tail is fix verification only. A tail of new chunk reviews does not pass,
  because no boundary review read that work.
- ``batch-covered``: a boundary review with no open blocker brackets the merge on
  the base's first-parent line. Its base tree is at or before the merge's first
  parent, and its head tree is at or after the merge.
- ``inner-only``: coverage composes, but only through inner-stage reviews.
- ``uncovered``: nothing composes, or an open blocker stands on the path.
- ``direct``: a commit with one parent changed a judgeable file. That is work
  committed on the base itself, or a squash merge; git cannot tell the two apart.
- ``unknown``: no commit on the base added the fragment (not merged yet, or the
  fragment is untracked), or git could not answer.

It is ADVICE (architecture: advice fails soft). Every degradation lands on a
classification that says "not covered" (``unknown``/``uncovered``), never on
``pr-covered``, because wave 2 turns this answer into a gate for a repo that defers
its boundary review to the release.

Composition is :func:`coverage_algebra.coverage_verdict`'s, stage is
:func:`critic_consolidate.stage_of_manifest`'s, and the pending set is
``release_readiness``'s. This module owns only the classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import change_fragments, coverage, coverage_algebra, evidence

NO_JUDGEABLE = "no-judgeable"
PR_COVERED = "pr-covered"
BATCH_COVERED = "batch-covered"
INNER_ONLY = "inner-only"
UNCOVERED = "uncovered"
DIRECT = "direct"
UNKNOWN = "unknown"

#: Every classification, in the order a report lists its counts. The covered ones
#: come first; the rest are what a release operator reads.
CLASSES = (NO_JUDGEABLE, PR_COVERED, BATCH_COVERED, INNER_ONLY, UNCOVERED, DIRECT, UNKNOWN)
COVERED = frozenset({NO_JUDGEABLE, PR_COVERED, BATCH_COVERED})

_VERIFY = "verify-resolutions"


@dataclass
class Entry:
    scope: str
    classification: str
    reason: str
    commit: "str | None" = None
    subject: str = ""

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "classification": self.classification,
            "reason": self.reason,
            "commit": self.commit,
            "subject": self.subject,
        }


@dataclass
class Report:
    status: str  # "ok" | "unevaluable"
    base: "str | None" = None
    reason: "str | None" = None
    entries: list = field(default_factory=list)
    #: Fragments the pending set refused (``release_readiness.pending_scopes``):
    #: invalid ones, which carry no trustworthy scope, so they are not classified,
    #: and are named here so the count line cannot read as the whole pending set.
    refusals: list = field(default_factory=list)

    def counts(self) -> dict:
        tally = {name: 0 for name in CLASSES}
        for entry in self.entries:
            tally[entry.classification] += 1
        return tally

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "base": self.base,
            "reason": self.reason,
            "counts": self.counts(),
            "entries": [entry.as_dict() for entry in self.entries],
            "refusals": list(self.refusals),
        }


def _is_boundary(fact: dict) -> bool:
    """A review fact dispatched at the boundary stage. A fact whose mode cannot be
    read is not one: the safe reading of "unknown stage" is "not the boundary"."""
    from . import critic_consolidate  # noqa: PLC0415 — lazy: the consolidator is large and imports gates

    try:
        return critic_consolidate.stage_of_manifest(fact.get("body") or {}) == critic_consolidate.STAGE_BOUNDARY
    except ValueError:
        return False


def _is_verify(fact: dict) -> bool:
    from . import critic_consolidate  # noqa: PLC0415 — lazy, as above

    return critic_consolidate.mode_token_of((fact.get("body") or {}).get("mode")) == _VERIFY


def _has_span(fact: dict) -> bool:
    body = fact.get("body") or {}
    return all(isinstance(body.get(k), str) and body.get(k) for k in ("base_tree", "head_tree"))


class _Classifier:
    """One store read and one set of git answers, shared by every scope."""

    def __init__(self, project_dir: Path, facts: list[dict], base: str):
        from . import gates  # noqa: PLC0415 — lazy, as the coverage callers in this package import it

        self.project_dir = project_dir
        self.base = base
        self.facts = facts
        reviews = [f for f in facts if f.get("kind") == "review"]
        others = [f for f in facts if f.get("kind") != "review"]
        # A boundary fact whose trees are not strings cannot be a span: the store
        # keeps every line it was ever given, so a malformed one is skipped here
        # rather than crashing every later release check.
        self.boundary = [f for f in reviews if _is_boundary(f) and _has_span(f)]
        self.others = others
        self.boundary_facts = others + self.boundary
        self.tail_facts = others + [f for f in reviews if _is_verify(f)]
        self._diff_fn = gates._cached_diff_fn(project_dir)
        self._key_fn = gates._tree_key_fn(project_dir)
        self._first_parent: "list[tuple[str, str]] | None" = None

    def _git(self, *args: str) -> "str | None":
        rc, out, _err = evidence.run_git(self.project_dir, *args)
        return out.strip() if rc == 0 else None

    def _verdict(self, facts: list[dict], base_tree: str, head_tree: str) -> str:
        return coverage_algebra.coverage_verdict(
            facts, base_tree, head_tree, self._diff_fn, self._key_fn
        )["status"]

    def _judgeable(self, older: str, newer: str) -> "list[str] | None":
        out = self._git("diff", "--name-only", "--no-renames", older, newer, "--")
        if out is None:
            return None
        return [p for p in out.splitlines() if p and coverage_algebra.is_judgeable_path(p)]

    def first_parent(self) -> "list[tuple[str, str]] | None":
        """``(commit, tree)`` along the base's first-parent line, newest first."""
        if self._first_parent is None:
            out = self._git("log", "--first-parent", "--format=%H %T", self.base)
            if out is None:
                return None
            self._first_parent = [tuple(line.split()) for line in out.splitlines() if line]
        return self._first_parent

    def adding_commit(self, scope: str) -> "str | None":
        rel = f"{change_fragments.FRAGMENT_DIR_REL}/{scope}.md"
        # `-m` with `--first-parent` diffs each merge against its first parent on
        # every git (only 2.31+ implies it). A fragment moved in from another path
        # still reads as an add: the pathspec filters before rename detection runs,
        # so the deleted source is never in the diff to be paired with it.
        out = self._git("log", "--first-parent", "-m", "--diff-filter=A",
                        "--format=%H", self.base, "--", rel)
        if not out:
            return None
        # The NEWEST add: a release deletes shipped fragments, so a scope name used
        # again after a release was re-added, and the fragment pending now is the
        # one its latest add brought in. The oldest would classify a merge that
        # already shipped, which can read covered when the pending one is not.
        return out.splitlines()[0]

    def classify(self, scope: str) -> Entry:
        commit = self.adding_commit(scope)
        if commit is None:
            return Entry(scope, UNKNOWN, f"no first-parent commit on {self.base} added its fragment "
                                         "(not merged yet, or the fragment is untracked)")
        entry = self.classify_commit(commit)
        entry.scope = scope
        return entry

    def classify_commit(self, commit: str) -> Entry:
        resolved = self._git("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
        if not resolved:
            return Entry("", UNKNOWN, "git does not know that commit", commit)
        commit = resolved  # the full name, which the first-parent line is keyed by
        subject = self._git("log", "-1", "--format=%s", commit) or ""
        parents = (self._git("rev-list", "--parents", "-n", "1", commit) or "").split()[1:]
        if not parents:
            return Entry("", UNKNOWN, "a root commit, or git could not read its parents", commit, subject)
        if len(parents) > 2:
            return Entry("", UNKNOWN, f"an octopus merge of {len(parents) - 1} branches, which this "
                                      "classification reads one branch at a time", commit, subject)
        if len(parents) == 1:
            changed = self._judgeable(parents[0], commit)
            if changed is None:
                return Entry("", UNKNOWN, "git could not diff the commit", commit, subject)
            if not changed:
                return Entry("", NO_JUDGEABLE, "a single-parent commit that changes no judgeable file",
                             commit, subject)
            return Entry("", DIRECT, f"a single-parent commit changing {len(changed)} judgeable file(s): "
                                     "work committed on the base, or a squash merge", commit, subject)
        first, tip = parents[0], parents[1]
        merge_base = self._git("merge-base", first, tip)
        if not merge_base:
            return Entry("", UNKNOWN, "the merged branch shares no merge-base with the base", commit, subject)
        changed = self._judgeable(merge_base, tip)
        if changed is None:
            return Entry("", UNKNOWN, "git could not diff the merged branch", commit, subject)
        if not changed:
            return Entry("", NO_JUDGEABLE, "the merged branch changes no judgeable file", commit, subject)
        span_base = self._git("rev-parse", f"{merge_base}^{{tree}}")
        span_head = self._git("rev-parse", f"{tip}^{{tree}}")
        if not span_base or not span_head:
            return Entry("", UNKNOWN, "git could not read the merged branch's trees", commit, subject)

        # The merge commit's own content (a conflict resolution, or an edit made in
        # the merge) is in neither parent, so no review of the branch read it.
        resolved_here = self._merge_only_judgeable(commit)
        overall = self._verdict(self.facts, span_base, span_head)
        if (overall == "covered" and not resolved_here
                and self._boundary_split(merge_base, tip, span_base, span_head)):
            return Entry("", PR_COVERED, "a boundary review covered the branch at its PR; only fix "
                                         "verification followed it", commit, subject)
        batch = self._batch_review(commit, first)
        if batch is not None:
            return Entry("", BATCH_COVERED, f"boundary review {batch} spans the merge", commit, subject)
        if resolved_here:
            return Entry("", UNCOVERED, f"the merge commit itself changes {len(resolved_here)} judgeable "
                                       "file(s) beyond both parents, and no review read the merge",
                         commit, subject)
        if overall == "covered":
            return Entry("", INNER_ONLY, "the branch's coverage composes only through inner-stage reviews",
                         commit, subject)
        if overall == "blocked":
            return Entry("", UNCOVERED, "an unresolved blocking finding stands on the branch's coverage",
                         commit, subject)
        return Entry("", UNCOVERED, "no review evidence composes over the branch (if it was reviewed "
                                    "in another clone, `prawduct-hook evidence sync` brings the "
                                    "reviews here)", commit, subject)

    def _merge_only_judgeable(self, commit: str) -> list:
        """Judgeable files the merge's tree holds in a state neither parent had: the
        combined diff (`--cc`) lists exactly those. An unreadable answer counts as
        one, so the merge reads not covered rather than covered."""
        out = self._git("diff-tree", "--cc", "--no-commit-id", "--name-only", "-r", commit)
        if out is None:
            return ["<git could not read the merge's combined diff>"]
        return [p for p in out.splitlines() if p and coverage_algebra.is_judgeable_path(p)]

    def _boundary_split(self, merge_base: str, tip: str, span_base: str, span_head: str) -> bool:
        trees = self._git("log", "--format=%T", f"{merge_base}..{tip}")
        if trees is None:
            return False
        branch_trees = set(trees.split()) | {span_head}
        for fact in self.boundary:
            body = fact.get("body") or {}
            split = body["head_tree"]
            # A candidate's head is a tree of the branch, or its base is the span's
            # base or a tree of the branch: a cumulative over a dirty tree records
            # a head no commit has, and still splits the span if the tail composes.
            if split not in branch_trees and body["base_tree"] not in branch_trees | {span_base}:
                continue
            if (self._verdict(self.boundary_facts, span_base, split) == "covered"
                    and self._verdict(self.tail_facts, split, span_head) == "covered"):
                return True
        return False

    def _batch_review(self, commit: str, first_parent: str) -> "str | None":
        line = self.first_parent()
        if not line:
            return None
        position = {sha: i for i, (sha, _tree) in enumerate(line)}
        if commit not in position or first_parent not in position:
            return None
        at_merge, before = position[commit], position[first_parent]
        trees_at: dict = {}
        for i, (_sha, tree) in enumerate(line):
            trees_at.setdefault(tree, []).append(i)
        for fact in self.boundary:
            body = fact.get("body") or {}
            older = trees_at.get(body.get("base_tree"), [])
            newer = trees_at.get(body.get("head_tree"), [])
            # Newest-first: a larger index is older. The review's base must be at or
            # before the merge's first parent; its head at or after the merge.
            if not any(i >= before for i in older) or not any(i <= at_merge for i in newer):
                continue
            # The review it names must itself span the bracket: composing over every
            # fact would let chunk reviews carry it, naming a review that never
            # vouched for the merge. Blockers still settle over every fact.
            alone = self.others + [fact]
            if (self._verdict(alone, body["base_tree"], body["head_tree"]) == "covered"
                    and self._verdict(self.facts, body["base_tree"], body["head_tree"]) == "covered"):
                return str(fact.get("id"))
        return None


def classify_pending(project_dir: Path) -> Report:
    """Classify every release-pending scope against the repo's integration base.

    Never raises: a fault anywhere in the classification is an ``unevaluable``
    report naming it, so the op exits 3 with an attributed reason (api-contract:
    errors are attributed, never stack traces across the boundary), and no caller
    reading this as advice can be failed by it."""
    try:
        return _classify_pending(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- advice: a fault becomes the "could not evaluate" answer, attributed, never a traceback or a moved exit
        return Report("unevaluable", reason=f"the classification failed: {type(exc).__name__}: {exc}")


def _classify_pending(project_dir: Path) -> Report:
    from . import release_readiness  # noqa: PLC0415 — lazy: release_readiness imports widely

    base, why = coverage.repo_base_branch(project_dir)
    if not base:
        return Report("unevaluable", reason=f"no integration base resolves: {why}")
    pending = release_readiness.pending_scopes(project_dir)
    if pending.read_error is not None:
        return Report("unevaluable", base=base, reason=pending.read_error)
    read = evidence.read_facts(project_dir)
    unreadable = _unreadable_store(read)
    if unreadable:
        return Report("unevaluable", base=base, reason=unreadable)
    classifier = _Classifier(project_dir, read.get("facts", []), base)
    return Report(
        "ok", base=base, entries=[classifier.classify(scope) for scope in sorted(pending.scopes)],
        refusals=list(pending.refusals),
    )


def _unreadable_store(read: dict) -> "str | None":
    """Why the store cannot be classified against, or None. Facts a newer plugin
    wrote are unreadable to this one, and one of them could be a review with an
    open blocker: classifying without it could read covered, so the answer is
    withheld rather than given over a partial store (the reader's contract for any
    pass/fail decision)."""
    if read.get("status") == "error":
        return f"the evidence store could not be read: {read.get('reason')}"
    ahead = read.get("schema_ahead") or []
    if ahead:
        return (f"{len(ahead)} evidence fact(s) were written by a newer plugin and cannot be read "
                "here; update the plugin, then re-run")
    return None


def classify_merge(project_dir: Path, commit: str) -> Entry:
    """Classify one commit on the base as :func:`classify_pending` would — for a
    caller that knows the commit rather than the scope."""
    base, why = coverage.repo_base_branch(project_dir)
    if not base:
        return Entry("", UNKNOWN, f"no integration base resolves: {why}", commit)
    read = evidence.read_facts(project_dir)
    unreadable = _unreadable_store(read)
    if unreadable:
        return Entry("", UNKNOWN, unreadable, commit)
    return _Classifier(project_dir, read.get("facts", []), base).classify_commit(commit)


def count_line(report: Report) -> str:
    """The one summary line, with its denominator: the report's last word, and the
    line check-releasability prints on every run."""
    counts = report.counts()
    covered = sum(counts[name] for name in COVERED)
    detail = ", ".join(f"{counts[name]} {name}" for name in CLASSES if counts[name])
    return (
        f"boundary coverage: {covered} of {len(report.entries)} release-pending scope(s) covered "
        f"on {report.base}" + (f" ({detail})" if detail else "")
    )


def render(report: Report) -> str:
    """The human report: one line per scope, then the count line with its denominator."""
    if report.status != "ok":
        return f"check-boundary-coverage: could not evaluate — {report.reason}"
    lines = [
        f"{e.classification:13} {e.scope}  {(e.commit or '')[:8]}  {e.reason}"
        + ("" if e.classification in COVERED else "  [not covered]")
        for e in report.entries
    ]
    lines.append(count_line(report))
    if report.refusals:
        lines.append(f"not classified: {len(report.refusals)} fragment(s) the pending set refused — "
                     + "; ".join(report.refusals))
    return "\n".join(lines)
