"""Which release-pending merges did a boundary review cover? (#1223, wave 1; #1232)

A per-release boundary review is only safe if, at the release, something can name
the merged work no boundary review read. This module is that one answer. It
classifies two sets of first-parent commits on the integration base, unioned and
de-duplicated by commit (each entry's ``source`` says which set named it):

- the **fragment join** (wave 1): for each release-pending scope
  (``release_readiness.pending_scopes``), the commit that added its fragment;
- the **walk** (#1232): every first-parent commit after the **release anchor**
  that changes a judgeable file, so work that never wrote a fragment is seen.

The anchor (:func:`release_anchor`) is the nearer to the base's tip of: the newest
first-parent commit adding a release file under ``.prawduct/releases/`` (the cut
writes one), and the oldest first-parent commit containing the newest version tag
reachable from the base. With neither there is no anchor, the walk is skipped and
the report says so; the fragment join is still given. The union keeps a scope a
pruned release withheld (merged before the anchor, still pending) classified.

Each commit is classified as:

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
- ``pr-transferred``: the branch synced its base after that review, so nothing
  composes over the span it merged with, and the PR gate's own base-advance
  transfer (``gates.base_advance_transfer``) carries it: the branch's judgeable
  diff is byte-identical across the advance, a suite run met the branch tip,
  and the span the transfer comes from is ``pr-covered`` by the rule above. It
  counts as covered and is named, so a release reader sees which coverage was
  carried rather than composed (#1250).
- ``batch-covered``: a boundary review with no open blocker brackets the merge on
  the base's first-parent line. Its base tree is at or before the merge's first
  parent, and its head tree is at or after the merge.
- ``inner-only``: coverage composes, but only through inner-stage reviews.
- ``uncovered``: nothing composes, or an open blocker stands on the path. When
  only the transfer's suite condition failed, the reason says so.
- ``release-bookkeeping``: a commit with one parent whose judgeable changes are all
  files the repo declares in ``release_version_files:``, read at its parent (the
  release reopen's version bump). Covered. An undeclared repo's fallback layout
  is a guess and never qualifies, and the declaration is read before the commit,
  so a commit cannot declare its own files bookkeeping.
- ``direct``: any other commit with one parent that changed a judgeable file. That
  is work committed on the base itself, or a squash merge; git cannot tell the
  two apart.
- ``unknown``: no commit on the base added the fragment (not merged yet, or the
  fragment is untracked), or git could not answer.

It is ADVICE (architecture: advice fails soft). Every degradation lands on a
classification that says "not covered" (``unknown``/``uncovered``), never on
``pr-covered``, because wave 2 turns this answer into a gate for a repo that defers
its boundary review to the release.

Composition is :func:`coverage_algebra.coverage_verdict`'s, stage is
:func:`critic_consolidate.stage_of_manifest`'s, the base-advance transfer is
:func:`gates.base_advance_transfer`'s, and the pending set is
``release_readiness``'s. This module owns only the classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import change_fragments, change_log, consumer_digest, coverage, coverage_algebra, evidence

NO_JUDGEABLE = "no-judgeable"
PR_COVERED = "pr-covered"
PR_TRANSFERRED = "pr-transferred"
BATCH_COVERED = "batch-covered"
RELEASE_BOOKKEEPING = "release-bookkeeping"
INNER_ONLY = "inner-only"
UNCOVERED = "uncovered"
DIRECT = "direct"
UNKNOWN = "unknown"

#: Every classification, in the order a report lists its counts. The covered ones
#: come first; the rest are what a release operator reads.
CLASSES = (NO_JUDGEABLE, PR_COVERED, PR_TRANSFERRED, BATCH_COVERED, RELEASE_BOOKKEEPING, INNER_ONLY,
           UNCOVERED, DIRECT, UNKNOWN)
COVERED = frozenset({NO_JUDGEABLE, PR_COVERED, PR_TRANSFERRED, BATCH_COVERED, RELEASE_BOOKKEEPING})

#: Which set named an entry: the pending-fragment join, the walk since the
#: release anchor, or both.
SOURCE_FRAGMENT = "fragment"
SOURCE_WALK = "walk"
SOURCE_BOTH = "both"

#: How the release anchor was found.
ANCHOR_RELEASE_FILE = "release-file"
ANCHOR_TAG = "tag"

_VERIFY = "verify-resolutions"
_STATE_REL = ".prawduct/project-state.yaml"


@dataclass
class Entry:
    scope: str
    classification: str
    reason: str
    commit: "str | None" = None
    subject: str = ""
    #: ``fragment``, ``walk`` or ``both`` in a report; empty for a commit asked
    #: about directly (:func:`classify_merge`).
    source: str = ""

    @property
    def label(self) -> str:
        """The scope, or, for a walked commit no fragment names, its short name and subject."""
        if self.scope:
            return self.scope
        return f'{(self.commit or "no commit")[:8]} "{self.subject}"'

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "classification": self.classification,
            "reason": self.reason,
            "commit": self.commit,
            "subject": self.subject,
            "source": self.source,
        }


@dataclass(frozen=True)
class Anchor:
    """The release the walk starts after: a first-parent commit on the base."""

    commit: str
    tree: str
    source: str  # ANCHOR_RELEASE_FILE | ANCHOR_TAG
    reason: str

    def as_dict(self) -> dict:
        return {"commit": self.commit, "tree": self.tree, "source": self.source, "reason": self.reason}


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
    anchor: "Anchor | None" = None
    #: Why there is no anchor (so no walk), when there is none on an ``ok`` report.
    no_anchor_reason: "str | None" = None

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
            "anchor": self.anchor.as_dict() if self.anchor else None,
            "no_anchor_reason": self.no_anchor_reason,
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
        self._gates = gates
        self._diff_fn = gates._cached_diff_fn(project_dir)
        self._key_fn = gates._tree_key_fn(project_dir)
        self._first_parent: "list[tuple[str, str]] | None" = None
        self._declared: dict = {}

    def _git(self, *args: str) -> "str | None":
        rc, out, _err = evidence.run_git(self.project_dir, *args)
        return out.strip() if rc == 0 else None

    def _full_verdict(self, facts: list[dict], base_tree: str, head_tree: str) -> dict:
        return coverage_algebra.coverage_verdict(
            facts, base_tree, head_tree, self._diff_fn, self._key_fn
        )

    def _verdict(self, facts: list[dict], base_tree: str, head_tree: str) -> str:
        return self._full_verdict(facts, base_tree, head_tree)["status"]

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
        return self.classify_known(commit, subject, parents)

    def classify_known(self, commit: str, subject: str, parents: list,
                       changed: "list[str] | None" = None) -> Entry:
        """Classify a full commit name whose subject and parents are already read
        (the walk reads them for every commit in one log). ``changed`` is the
        judgeable diff against the only parent, when the caller has it."""
        if not parents:
            return Entry("", UNKNOWN, "a root commit, or git could not read its parents", commit, subject)
        if len(parents) > 2:
            return Entry("", UNKNOWN, f"an octopus merge of {len(parents) - 1} branches, which this "
                                      "classification reads one branch at a time", commit, subject)
        if len(parents) == 1:
            if changed is None:
                changed = self._judgeable(parents[0], commit)
            if changed is None:
                return Entry("", UNKNOWN, "git could not diff the commit", commit, subject)
            if not changed:
                return Entry("", NO_JUDGEABLE, "a single-parent commit that changes no judgeable file",
                             commit, subject)
            declared = self._declared_version_files(parents[0])
            if declared and set(changed) <= declared:
                return Entry("", RELEASE_BOOKKEEPING, "a single-parent commit changing only declared "
                                                      f"release version file(s): {', '.join(changed)}",
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
            # The walk reaches a merge by its diff against the first parent, so
            # one whose branch changed nothing judgeable can still carry an edit
            # made in the merge itself, which no review of the branch read.
            resolved_here = self._merge_only_judgeable(commit)
            if resolved_here:
                return Entry("", UNCOVERED, f"the merged branch changes no judgeable file, but the merge "
                                           f"commit itself changes {len(resolved_here)} judgeable file(s) "
                                           "beyond both parents, and no review read the merge",
                             commit, subject)
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
        transferred = self._transferred(merge_base, tip, span_base, span_head)
        if transferred is not None:
            classification, reason = transferred
            return Entry("", classification, reason, commit, subject)
        return Entry("", UNCOVERED, "no review evidence composes over the branch (if it was reviewed "
                                    "in another clone, `prawduct-hook evidence sync` brings the "
                                    "reviews here)", commit, subject)

    def _transferred(self, merge_base: str, tip: str, span_base: str,
                     span_head: str) -> "tuple[str, str] | None":
        """The PR gate's base-advance transfer, asked of the merged span: a branch
        that synced its base after review composes from no fact, and the gate
        passed it by transfer. The decision is the gate's own
        (``gates.base_advance_transfer``), never a copy, with the suite asked
        about the branch tip, the tree the PR gate vouched for. Asked only of an
        ``uncovered`` span, as the gate asks it.

        A grant moves the boundary question to the span the coverage came from,
        and that span must pass the same split ``pr-covered`` requires there.
        Returns ``(classification, reason)``, or None when the transfer did not
        match, leaving the plain ``uncovered`` reading."""
        decided = self._gates.base_advance_transfer(
            self.project_dir, self.facts, span_base, span_head, self._diff_fn,
            self._full_verdict, suite_tree=span_head,
        )
        transfer = decided["transfer"]
        if decided["decision"] == self._gates.TRANSFER_SUITE_STALE:
            return UNCOVERED, ("the PR gate's base-advance transfer matched (branch diff byte-identical "
                               "across the advance), but no saved suite run met the branch tip: "
                               f"{decided['tests_reason']}")
        if decided["decision"] != self._gates.TRANSFER_GRANTED:
            return None
        prior_base, prior_head = transfer["prior_base"], transfer["prior_head"]
        carried = (f"transferred across base advance {prior_base[:12]}→{span_base[:12]}; branch "
                   f"diff byte-identical; {decided['tests_reason']}")
        if self._boundary_split(merge_base, tip, prior_base, prior_head):
            return PR_TRANSFERRED, (f"a boundary review covered the branch at its PR before it synced "
                                    f"its base, and only fix verification followed it ({carried})")
        return INNER_ONLY, f"the branch's coverage composes only through inner-stage reviews ({carried})"

    def _declared_version_files(self, commit: str) -> "frozenset[str] | None":
        """The paths ``release_version_files:`` declares in ``commit``'s tree, or None
        when it declares none (the fallback layout is a guess, never a declaration).
        Read at the PARENT of the commit being classified, so a commit cannot
        declare its own changes bookkeeping."""
        if commit not in self._declared:
            from . import release_verification  # noqa: PLC0415 — lazy: it imports release_readiness

            text = self._git("show", f"{commit}:{_STATE_REL}")
            specs = release_verification._read_declaration(text) if text is not None else None
            self._declared[commit] = frozenset(spec.path for spec in specs) if specs else None
        return self._declared[commit]

    def walk(self, anchor: str) -> "list[tuple[str, list, str, list]] | None":
        """``(commit, parents, subject, judgeable files)`` for every first-parent
        commit after ``anchor`` on the base whose diff against its first parent
        changes a judgeable file, oldest first; None when git could not answer.

        One log reads every commit's parents, subject and changed paths. `-m` with
        `--first-parent` diffs a merge against its first parent, which is what the
        merge brought onto the base."""
        rc, out, _err = evidence.run_git(
            self.project_dir, "log", "--first-parent", "-m", "--no-renames", "--name-only",
            "--format=%x1e%H%x1f%P%x1f%s", f"{anchor}..{self.base}", "--",
        )
        if rc != 0:
            return None
        found = []
        for record in out.split("\x1e"):
            head, _, names = record.partition("\n")
            if not head.strip():
                continue
            commit, parents, subject = (head.split("\x1f") + ["", ""])[:3]
            changed = list(dict.fromkeys(
                p for p in names.splitlines() if p and coverage_algebra.is_judgeable_path(p)
            ))
            if changed:
                found.append((commit, parents.split(), subject, changed))
        found.reverse()
        return found

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
    entries: list = []
    by_commit: dict = {}
    for scope in sorted(pending.scopes):
        entry = classifier.classify(scope)
        entry.source = SOURCE_FRAGMENT
        prior = by_commit.get(entry.commit) if entry.commit else None
        if prior is not None:
            # Two fragments one merge added: one commit, one entry, both scopes.
            prior.scope = f"{prior.scope}, {scope}"
            continue
        entries.append(entry)
        if entry.commit:
            by_commit[entry.commit] = entry
    anchor, no_anchor = _resolve_anchor(project_dir, base)
    if anchor is not None:
        walked = classifier.walk(anchor.commit)
        if walked is None:
            entries.append(Entry("", UNKNOWN, f"git could not list the first-parent commits on {base} "
                                              f"since the release anchor {anchor.commit[:8]}",
                                 source=SOURCE_WALK))
        for commit, parents, subject, changed in walked or []:
            prior = by_commit.get(commit)
            if prior is not None:
                prior.source = SOURCE_BOTH
                continue
            entry = classifier.classify_known(commit, subject, parents,
                                              changed if len(parents) == 1 else None)
            entry.source = SOURCE_WALK
            entries.append(entry)
            by_commit[commit] = entry
    return Report("ok", base=base, entries=entries, refusals=list(pending.refusals),
                  anchor=anchor, no_anchor_reason=no_anchor)


def _version_key(name: str) -> "tuple | None":
    """An ordering key for a version-shaped name (``v3.10.0``, ``3.10.0``, a
    four-part or prerelease form: ``change_log.RELEASE_VALUE_RE`` after
    ``release_readiness.normalize_version``), else None. A prerelease sorts below
    its release."""
    from . import release_readiness  # noqa: PLC0415 — lazy, as above

    version = release_readiness.normalize_version(name)
    if not change_log.RELEASE_VALUE_RE.match(version):
        return None
    numbers, _, pre = version[1:].partition("-")
    return tuple(int(part) for part in numbers.split(".")), (0, pre) if pre else (1, "")


def _release_file_candidate(git, base: str) -> "tuple[str, str] | None":
    """``(commit, path)``: the newest first-parent commit on ``base`` adding a
    release file (``.prawduct/releases/<version>.md``)."""
    out = git("log", "--first-parent", "-m", "--diff-filter=A", "--no-renames", "--name-only",
              "--format=%x1e%H", base, "--", f"{consumer_digest.RELEASES_DIR_REL}/")
    if out is None:
        return None
    for record in out.split("\x1e"):
        commit, _, names = record.strip().partition("\n")
        for name in names.splitlines():
            parent, _, leaf = name.rpartition("/")
            if (parent == consumer_digest.RELEASES_DIR_REL and leaf.endswith(".md")
                    and _version_key(leaf[:-3]) is not None):
                return commit, name
    return None


def _tag_candidate(git, base: str) -> "tuple[str, str] | None":
    """``(tag, commit)``: the newest version-shaped tag reachable from ``base``."""
    out = git("for-each-ref", f"--merged={base}",
              "--format=%(refname:strip=2)%00%(objectname)%00%(*objectname)", "refs/tags")
    if not out:
        return None
    best = None
    for line in out.splitlines():
        name, _, rest = line.partition("\0")
        target, _, peeled = rest.partition("\0")
        key = _version_key(name)
        if key is not None and (best is None or key > best[0]):
            best = (key, name, peeled or target)
    return (best[1], best[2]) if best else None


def _oldest_containing(git, base: str, tag_commit: str) -> "str | None":
    """The oldest first-parent commit on ``base`` that contains ``tag_commit``.
    A tag on the first-parent line is its own answer; a tag merged in from a side
    line (a gitflow back-merge) is answered by the merge that brought it in."""
    line = git("log", "--first-parent", "--format=%H %P", f"{tag_commit}..{base}")
    if line is None:
        return None
    rows = [row.split() for row in line.splitlines() if row.strip()]
    if not rows or (len(rows[-1]) > 1 and rows[-1][1] == tag_commit):
        return tag_commit
    descendants = git("rev-list", "--ancestry-path", f"{tag_commit}..{base}")
    if descendants is None:
        return None
    contains = set(descendants.split())
    for row in reversed(rows):
        if row[0] in contains:
            return row[0]
    return None


def release_anchor(project_dir: Path, base: str) -> "Anchor | None":
    """The release anchor on ``base``: whichever is nearer the tip of (A) the newest
    first-parent commit adding a release file under ``.prawduct/releases/`` and (B)
    the oldest first-parent commit containing the newest version tag reachable from
    ``base``. None when there is neither."""
    return _resolve_anchor(project_dir, base)[0]


def _resolve_anchor(project_dir: Path, base: str) -> "tuple[Anchor | None, str | None]":
    """``(anchor, None)``, or ``(None, why there is none)``. A candidate git could
    not answer counts as absent: the other is then the older or the same, so a
    failure only ever widens the walk, never narrows it."""
    def git(*args: str) -> "str | None":
        rc, out, _err = evidence.run_git(project_dir, *args)
        return out.strip() if rc == 0 else None

    by_file = _release_file_candidate(git, base)
    tag = _tag_candidate(git, base)
    chosen = None
    if by_file is not None:
        commit, path = by_file
        # The nearer wins. The tag's anchor is the oldest commit containing it, so
        # it is nearer than the release file's commit only if that commit does not
        # contain the tag; a tie goes to the release file.
        tag_older = tag is not None and evidence.run_git(
            project_dir, "merge-base", "--is-ancestor", tag[1], commit)[0] == 0
        if tag is None or tag_older:
            note = f"; tag {tag[0]} is older on this line" if tag else ""
            chosen = (commit, ANCHOR_RELEASE_FILE, f"{commit[:8]} adds the release file {path}{note}")
    if chosen is None and tag is not None:
        commit = _oldest_containing(git, base, tag[1])
        if commit is not None:
            note = f"; nearer the tip than the release file {by_file[1]}" if by_file else ""
            chosen = (commit, ANCHOR_TAG, f"{commit[:8]} is the oldest first-parent commit on {base} "
                                          f"containing tag {tag[0]}{note}")
    if chosen is None:
        return None, (f"no first-parent commit on {base} adds a release file under "
                      f"{consumer_digest.RELEASES_DIR_REL}/, and no version tag is reachable from it")
    tree = git("rev-parse", f"{chosen[0]}^{{tree}}")
    if not tree:
        return None, f"git could not read the release anchor {chosen[0][:8]}'s tree"
    return Anchor(chosen[0], tree, chosen[1], chosen[2]), None


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
    line check-releasability prints on every run. It names the release anchor and
    how many entries the walk since it found, or says there was no anchor."""
    counts = report.counts()
    covered = sum(counts[name] for name in COVERED)
    detail = ", ".join(f"{counts[name]} {name}" for name in CLASSES if counts[name])
    detail = f" ({detail})" if detail else ""
    total = len(report.entries)
    if report.anchor is None:
        return (f"boundary coverage: {covered} of {total} release-pending scope(s) covered on "
                f"{report.base}{detail}; no release anchor, so no commit since a release was walked")
    walked = sum(1 for e in report.entries if e.source in (SOURCE_WALK, SOURCE_BOTH))
    return (f"boundary coverage: {covered} of {total} covered on {report.base}{detail}: {walked} "
            f"judgeable commit(s) since release anchor {report.anchor.commit[:8]} "
            f"({report.anchor.source}), and {total - walked} more by release-pending fragment")


def render(report: Report) -> str:
    """The human report: one line per entry, the anchor, then the count line with its denominator."""
    if report.status != "ok":
        return f"check-boundary-coverage: could not evaluate — {report.reason}"
    lines = [
        f"{e.classification:19} {e.scope or '(no fragment) ' + repr(e.subject)}  "
        f"{(e.commit or '')[:8]}  {e.reason}"
        + ("" if e.classification in COVERED else "  [not covered]")
        for e in report.entries
    ]
    lines.append(f"release anchor: {report.anchor.reason} ({report.anchor.source})" if report.anchor
                 else f"release anchor: none — {report.no_anchor_reason}")
    lines.append(count_line(report))
    if report.refusals:
        lines.append(f"not classified: {len(report.refusals)} fragment(s) the pending set refused — "
                     + "; ".join(report.refusals))
    return "\n".join(lines)
