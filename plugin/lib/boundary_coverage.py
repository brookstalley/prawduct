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
writes one), and the oldest first-parent commit containing the merge-base of the
base and the newest release (not prerelease) version tag sharing history with it.
A candidate that reached the base through a merge's side parent (a back-merge) resolves to the base's own commit it released,
never to the merge. With neither there is no anchor, the walk is
skipped and the report says so; the fragment join is still given. The union keeps a scope a
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
- ``batch-covered``: a boundary review on the base credits the commit (a merge,
  or work committed on the base) by :func:`coverage_algebra.batch_review_covers`,
  the relax-only batch rule: the review brackets the commit on the base's
  first-parent line (its base tree at or before the commit's first parent, its
  head tree at or after the commit), it rated every judgeable file of the commit
  still changed across its interval, and no unresolved blocker stands at its
  trees or at the commit's own (a merged branch's: a blocker the PR gate was
  bypassed over is resolved, never outlived, by a ``verify-resolutions`` pass on
  the base whose roll-call names it: :func:`release_owed_blockers`). A release
  batch review (``/prawduct:critic cumulative`` at the base's tip, ``span:
  release``) rates only the not-covered entries' files, so it is credited here and never composes as an
  edge. Also the **batch fix tail**: a commit on the base after such a review,
  covered when ``verify-resolutions`` and free edges alone compose the review's
  head tree to a first-parent tree at or after the commit, and the review's
  blockers are resolved (a boundary prefix plus a verify-only tail, applied to
  the batch).
- ``inner-only``: coverage composes, but only through inner-stage reviews.
- ``tail-deferred``: the PR gate let the branch merge with a blocker-free fix
  tail no review read, deferred to this release check (per_release only). Not
  covered: the release batch review owes it a read. Asked of the merged span
  after the transfer fails, by the PR gate's own predicate
  (``gates.fix_tail_deferral``), so a release reader can tell "deferred" from
  "nothing reviewed this".
- ``uncovered``: nothing composes, or an open blocker stands on the path. When
  only the transfer's suite condition failed, the reason says so.
- ``release-bookkeeping``: a commit with one parent, after the release anchor,
  whose judgeable changes are all files the repo declares in
  ``release_version_files:`` at that anchor (the release reopen's version bump).
  Covered. An undeclared repo's fallback layout is a guess and never qualifies,
  and the declaration must already have been in force at the release, so no
  commit since it (this one, or one before it) can declare a file bookkeeping.
- ``direct``: any other commit with one parent that changed a judgeable file. That
  is work committed on the base itself, or a squash merge; git cannot tell the
  two apart.
- ``unknown``: no commit on the base added the fragment (not merged yet, or the
  fragment is untracked), git could not answer, an octopus merge, or a merge of
  a history sharing no merge-base with the base. The batch rule is asked of
  every one that names a parent, so a release batch review credits it.

The classification is ADVICE under ``boundary_review: per_pr`` (architecture:
advice fails soft), and the answer a GATE reads under ``per_release``
(:func:`release_gate`, which ``check-boundary-coverage --gate`` exits with and
``check-releasability`` refuses on). So every degradation lands on a
classification that says "not covered" (``unknown``/``uncovered``), never on
``pr-covered``, and a report that could not be read refuses the gate.

Composition is :func:`coverage_algebra.coverage_verdict`'s, stage is
:func:`critic_consolidate.stage_of_manifest`'s, the base-advance transfer is
:func:`gates.base_advance_transfer`'s, the fix-tail deferral is
:func:`gates.fix_tail_deferral`'s, and the pending set is
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
TAIL_DEFERRED = "tail-deferred"
UNCOVERED = "uncovered"
DIRECT = "direct"
UNKNOWN = "unknown"

#: Every classification, in the order a report lists its counts. The covered ones
#: come first; the rest are what a release operator reads.
CLASSES = (NO_JUDGEABLE, PR_COVERED, PR_TRANSFERRED, BATCH_COVERED, RELEASE_BOOKKEEPING, INNER_ONLY,
           TAIL_DEFERRED, UNCOVERED, DIRECT, UNKNOWN)
COVERED = frozenset({NO_JUDGEABLE, PR_COVERED, PR_TRANSFERRED, BATCH_COVERED, RELEASE_BOOKKEEPING})

#: Which set named an entry: the pending-fragment join, the walk since the
#: release anchor, or both. ``walk-failed`` marks the one ``unknown`` entry that
#: stands for a walk git could not run: it names no commit, and keeps the count
#: short of fully covered.
SOURCE_FRAGMENT = "fragment"
SOURCE_WALK = "walk"
SOURCE_BOTH = "both"
SOURCE_WALK_FAILED = "walk-failed"

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
    #: The unresolved blocking findings standing at the entry's own trees (a
    #: merged branch's reviews), for an entry not covered: no batch review
    #: credits it over them, and a resolution, recorded by ``verify-resolutions``
    #: on the base, is what clears them (:func:`release_owed_blockers`).
    blockers: list = field(default_factory=list)

    @property
    def label(self) -> str:
        """The scope, or, for a walked commit no fragment names, its short name and
        subject; for a walk that could not run, says so."""
        if self.scope:
            return self.scope
        if self.source == SOURCE_WALK_FAILED:
            return "(the walk since the release anchor)"
        return f'{(self.commit or "no commit")[:8]} "{self.subject}"'

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "classification": self.classification,
            "reason": self.reason,
            "commit": self.commit,
            "subject": self.subject,
            "source": self.source,
            "blockers": [{k: b.get(k) for k in ("review_id", "fid", "title") if k in b}
                         for b in self.blockers],
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


def _merged_blockers(*lists: list) -> list:
    """Blocker lists joined, each ``(review_id, fid)`` once, first seen first."""
    seen: set = set()
    out: list = []
    for blockers in lists:
        for b in blockers:
            key = (b.get("review_id"), b.get("fid"))
            if key not in seen:
                seen.add(key)
                out.append(b)
    return out


class _Classifier:
    """One store read and one set of git answers, shared by every scope."""

    def __init__(self, project_dir: Path, facts: list[dict], base: str, anchor: "str | None" = None):
        from . import gates  # noqa: PLC0415 — lazy, as the coverage callers in this package import it

        self.project_dir = project_dir
        self.base = base
        #: The release anchor's commit: bookkeeping is read against it, so with
        #: none no commit is release bookkeeping.
        self.anchor = anchor
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
        self._index: "tuple[dict, dict] | None" = None

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
        judgeable diff against the only parent, when the caller has it.

        The commit's own shape answers first (:meth:`_classify_shape`). Only a
        commit that reads not covered there is asked of the boundary reviews on
        the base: the batch rule, then, for work committed on the base, the
        batch fix tail. Both can only turn not covered into covered, and
        neither while a blocker stands on the commit's own trees
        (:meth:`_entry_trees`). Every ``unknown`` that names a parent is asked
        too, whatever its shape (an octopus merge, a merge of a history sharing
        no merge-base with the base, a merged branch git could not diff):
        what it brought onto the base, its diff against its first parent, is
        what a release batch review rates (:func:`release_subject` dispatches
        one for it), so without the batch rule a ``per_release`` release would
        be held by it for good. Only a root commit, or one whose parents git
        could not read, names no parent, and stays ``unknown``."""
        entry = self._classify_shape(commit, subject, parents, changed)
        if entry.classification in COVERED or not parents:
            return entry
        # A shape reading blocked by its branch's own blockers is credited by no
        # batch review until they are resolved: they may stand at a tree none of
        # the entry's commits holds, which the batch's settlement never reads.
        shape_blockers = list(entry.blockers)
        if len(parents) == 1:
            files = changed if changed is not None else self._judgeable(parents[0], commit)
        else:
            files = self._judgeable(parents[0], commit)
        trees = self._entry_trees(commit, parents[0])
        batch = self._batch(commit, parents[0], files, trees)
        if batch is not None and batch[0] == "covered" and shape_blockers:
            batch = ("blocked", batch[1], "the merged branch's own blocking finding is unresolved")
        if batch is not None and batch[0] == "covered":
            return Entry("", BATCH_COVERED, f"boundary review {batch[1]} on {self.base} spans it and "
                                            "rated its judgeable files", commit, subject)
        if len(parents) == 1 and not shape_blockers:
            tail = self._batch_tail(commit, parents[0], trees)
            if tail is not None:
                return Entry("", BATCH_COVERED, f"a fix on {self.base} after boundary review {tail}: "
                                                "verify-resolutions composes that review's tree to it, "
                                                "and the review's blockers are resolved", commit, subject)
        if batch is not None:
            entry.reason += (f"; boundary review {batch[1]} on {self.base} spans it, but "
                             f"{batch[2]} (fix it on {self.base} and run `/prawduct:critic "
                             "verify-resolutions` there)")
        entry.blockers = _merged_blockers(
            shape_blockers, coverage_algebra.entry_blockers(self.facts, trees or ()))
        return entry

    def _entry_trees(self, commit: str, first_parent: str) -> "list[str] | None":
        """The trees of ``commit`` and of every commit it brought onto the base
        (``first_parent..commit``: for a merge, its branch's own commits), where
        a blocker must be resolved before any batch review credits it; None
        when git could not list them."""
        out = self._git("log", "--format=%T", f"{first_parent}..{commit}")
        return None if out is None else list(dict.fromkeys(out.split()))

    def _classify_shape(self, commit: str, subject: str, parents: list,
                        changed: "list[str] | None" = None) -> Entry:
        """The commit's classification from its own shape and its branch's
        coverage, before any boundary review on the base is asked."""
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
            if self._release_bookkeeping(commit, parents[0], changed):
                return Entry("", RELEASE_BOOKKEEPING, "a single-parent commit after the release anchor "
                                                      "changing only the version in release version "
                                                      f"file(s) declared there: {', '.join(changed)}",
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
        full = self._full_verdict(self.facts, span_base, span_head)
        overall = full["status"]
        if (overall == "covered" and not resolved_here
                and self._boundary_split(merge_base, tip, span_base, span_head)):
            return Entry("", PR_COVERED, "a boundary review covered the branch at its PR; only fix "
                                         "verification followed it", commit, subject)
        if resolved_here:
            return Entry("", UNCOVERED, f"the merge commit itself changes {len(resolved_here)} judgeable "
                                       "file(s) beyond both parents, and no review read the merge",
                         commit, subject)
        if overall == "covered":
            return Entry("", INNER_ONLY, "the branch's coverage composes only through inner-stage reviews",
                         commit, subject)
        if overall == "blocked":
            # The verdict's own blockers, wherever their review stood: a review of
            # an uncommitted tree records its blocker at a tree no commit holds,
            # which the entry's commit trees (_entry_trees) never reach.
            entry = Entry("", UNCOVERED, "an unresolved blocking finding stands on the branch's coverage",
                          commit, subject)
            entry.blockers = [dict(u) for u in full.get("unresolved") or []]
            return entry
        transferred = self._transferred(merge_base, tip, span_base, span_head)
        if transferred is not None and transferred[0] != UNCOVERED:
            classification, reason = transferred
            return Entry("", classification, reason, commit, subject)
        # The transfer failed, so ask what the PR gate asked next: was the
        # branch's blocker-free fix tail deferred to this release? The one
        # predicate, asked of the merged span (its tip is the merge's second
        # parent). Not covered either way: it names WHY the merge is owed a read.
        # A deferral that crashed must say so in the reason, or the entry reads as
        # "nothing reviewed this" and sends the operator to the wrong remedy.
        deferral_why: list = []
        deferral = self._gates.fix_tail_deferral(
            self.project_dir, self.facts, span_base, span_head, merge_base,
            self._full_verdict, tip=tip, why=deferral_why,
        )
        if deferral is not None:
            return Entry("", TAIL_DEFERRED, (
                f"the PR gate deferred the fix tail after review {deferral['fact_id']} to the release: "
                f"{len(deferral['files'])} judgeable file(s) its findings named, unread since "
                f"({', '.join(deferral['files'][:3])}{' …' if len(deferral['files']) > 3 else ''})"
            ), commit, subject)
        unread = "".join(f"; {sentence}, so whether the PR gate deferred its fix tail is unknown"
                         for sentence in deferral_why)
        if transferred is not None:
            classification, reason = transferred
            return Entry("", classification, reason + unread, commit, subject)
        return Entry("", UNCOVERED, "no review evidence composes over the branch (if it was reviewed "
                                    "in another clone, `prawduct-hook evidence sync` brings the "
                                    "reviews here)" + unread, commit, subject)

    def _transferred(self, merge_base: str, tip: str, span_base: str,
                     span_head: str) -> "tuple[str, str] | None":
        """The PR gate's base-advance transfer, asked of the merged span: a branch
        that synced its base after review composes from no fact, and the gate
        passed it by transfer. Asked only of an ``uncovered`` span, as the gate
        asks it.

        A gate's recorded grant for exactly this span answers first
        (``gates.recorded_transfer_grant``: the PR gate's, or the Stop gate's,
        which is the only record when both granted one span): the authority
        decided, and nothing
        is re-checked. Only without one is the transfer re-decided, by the
        gate's own function (``gates.base_advance_transfer``), with the suite
        asked about the branch (its commits and tip), never this checkout.

        A grant moves the boundary question to the span the coverage came from,
        and that span must pass the same split ``pr-covered`` requires there.
        Returns ``(classification, reason)``, or None when no transfer was
        found, leaving the plain ``uncovered`` reading."""
        grant = self._gates.recorded_transfer_grant(self.facts, span_base, span_head)
        if grant is not None and self._verdict(self.facts, grant["prior_base"],
                                               grant["prior_head"]) == "covered":
            transfer = grant
            carried = (f"{grant['gate']} recorded its base-advance transfer grant {grant['grant_id']}, "
                       f"{grant['prior_base'][:12]}→{span_base[:12]}")
        else:
            commits = self._git("rev-list", f"{merge_base}..{tip}")
            decided = self._gates.base_advance_transfer(
                self.project_dir, self.facts, span_base, span_head, self._diff_fn,
                self._full_verdict, suite_tree=span_head,
                suite_branch=frozenset((commits or "").split()),
            )
            transfer = decided["transfer"]
            if decided["kind"] == "unavailable":
                return UNCOVERED, ("no review evidence composes over the branch, and the base-advance "
                                   f"transfer check could not run ({transfer.get('reason')})")
            if decided["decision"] == self._gates.TRANSFER_SUITE_STALE:
                return UNCOVERED, ("the branch's diff is byte-identical across its base advance, but no "
                                   "PR-gate transfer grant is recorded for the merged span and no suite run "
                                   f"met the branch tip ({decided['tests_reason']}); grants and suite runs "
                                   "stay in the clone that recorded them, so they may exist in another clone")
            if decided["decision"] != self._gates.TRANSFER_GRANTED:
                return None
            carried = (f"transferred across base advance {transfer['prior_base'][:12]}→{span_base[:12]}; "
                       f"branch diff byte-identical; {decided['tests_reason']}")
        prior_base, prior_head = transfer["prior_base"], transfer["prior_head"]
        if self._boundary_split(merge_base, tip, prior_base, prior_head):
            return PR_TRANSFERRED, (f"a boundary review covered the branch at its PR before it synced "
                                    f"its base, and only fix verification followed it ({carried})")
        return INNER_ONLY, f"the branch's coverage composes only through inner-stage reviews ({carried})"

    def _release_bookkeeping(self, commit: str, parent: str, changed: list) -> bool:
        """Does a single-parent commit (``parent``, judgeable ``changed``) change
        only the version in files the repo declared release version files AT THE
        RELEASE ANCHOR?

        The declaration is read at the anchor, not at the parent: one added after
        the release (by this commit, or by an earlier metadata-only one) would let
        any later commit name a source file a version file and read covered. So the
        commit must follow the anchor (its parent is the anchor or descends from
        it). And a declared file is credited only for its version
        (:meth:`_version_only`): a manifest carries more than a version, and a
        dependency or entry point changed beside the bump is work no review read.
        With no anchor, or any git failure, the answer is no, which reads
        ``direct``: not covered."""
        if self.anchor is None:
            return False
        declared = self._declared_version_files(self.anchor)
        if not declared or not set(changed) <= set(declared):
            return False
        rc, _out, _err = evidence.run_git(self.project_dir, "merge-base", "--is-ancestor",
                                          self.anchor, parent)
        return rc == 0 and all(self._version_only(declared[path], parent, commit) for path in changed)

    def _version_only(self, spec, older: str, newer: str) -> bool:
        """Does the declared file ``spec`` differ between two revisions in its
        version alone? A ``bare`` file is its version, so both sides must be one
        version-shaped line (:func:`_is_version`): a one-line rewrite into
        anything else, or out of it, is a change no review read. A ``json`` or ``toml`` one must read a version on both sides and decode to
        the same data once the declared key is set aside. Anything unreadable, or
        a format this cannot decode, is no."""
        before = self._git("show", f"{older}:{spec.path}")
        after = self._git("show", f"{newer}:{spec.path}")
        if before is None or after is None:
            return False
        if spec.fmt == "bare":
            return _is_version(before) and _is_version(after)
        import json  # noqa: PLC0415 — only a declared structured version file needs a decoder
        import tomllib  # noqa: PLC0415

        loader = {"json": json.loads, "toml": tomllib.loads}.get(spec.fmt)
        if loader is None or not spec.key:
            return False
        try:
            sides = [loader(before), loader(after)]
        except ValueError:
            return False
        *parents, leaf = spec.key.split(".")
        for data in sides:
            for part in parents:
                data = data.get(part) if isinstance(data, dict) else None
            if not isinstance(data, dict) or data.pop(leaf, None) in (None, ""):
                return False
        return sides[0] == sides[1]

    def _declared_version_files(self, commit: str) -> "dict | None":
        """``{path: spec}`` for what ``release_version_files:`` declares in
        ``commit``'s tree, or None when it declares none (the fallback layout is a
        guess, never a declaration). Read at the release anchor
        (:meth:`_release_bookkeeping`)."""
        if commit not in self._declared:
            from . import release_verification  # noqa: PLC0415 — lazy: it imports release_readiness

            text = self._git("show", f"{commit}:{_STATE_REL}")
            specs = release_verification._read_declaration(text) if text is not None else None
            self._declared[commit] = {spec.path: spec for spec in specs} if specs else None
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

    def _line_index(self) -> "tuple[dict, dict] | None":
        """``(position of each commit, positions of each tree)`` on the base's
        first-parent line, newest first (a larger index is older); None when
        git could not list it."""
        if self._index is None:
            line = self.first_parent()
            if not line:
                return None
            position = {sha: i for i, (sha, _tree) in enumerate(line)}
            trees_at: dict = {}
            for i, (_sha, tree) in enumerate(line):
                trees_at.setdefault(tree, []).append(i)
            self._index = (position, trees_at)
        return self._index

    def _batch(self, commit: str, first_parent: str, files: "list[str] | None",
               trees: "list[str] | None") -> "tuple[str, str, str] | None":
        """``(status, review id, reason)`` from the relax-only batch rule
        (:func:`coverage_algebra.batch_review_covers`) over every boundary review
        on the base: the first review that covers the commit, else the first
        that brackets it and is blocked, else None. ``files`` is the commit's
        judgeable diff against its first parent, ``trees`` its own trees
        (:meth:`_entry_trees`), each None when unread.

        The review is named only when the rule credits it: a review that never
        rated the commit's files is not named, even when other facts compose
        over the same trees."""
        index = self._line_index()
        if index is None:
            return None
        position, trees_at = index
        if commit not in position or first_parent not in position:
            return None
        at_commit, before = position[commit], position[first_parent]
        blocked = None
        for fact in self.boundary:
            body = fact.get("body") or {}
            older = trees_at.get(body.get("base_tree"), [])
            newer = trees_at.get(body.get("head_tree"), [])
            # The review's base at or before the commit's first parent; its head
            # at or after the commit.
            brackets = any(i >= before for i in older) and any(i <= at_commit for i in newer)
            verdict = coverage_algebra.batch_review_covers(self.facts, fact, files, brackets=brackets,
                                                           entry_trees=trees)
            if verdict["status"] == "covered":
                return "covered", str(fact.get("id")), verdict["reason"]
            if verdict["status"] == "blocked" and blocked is None:
                blocked = ("blocked", str(fact.get("id")), verdict["reason"])
        return blocked

    def _batch_tail(self, commit: str, parent: str, trees: "list[str] | None") -> "str | None":
        """The id of a boundary review on the base whose fix tail covers
        ``commit``, a single-parent commit after it, or None.

        The tail is the accepted "boundary prefix plus verify-only tail" shape,
        applied to a review on the base: the review's head tree is at or before
        the commit's parent, ``verify-resolutions`` edges and free edges alone
        compose that head tree to a first-parent tree at or after the commit
        (so a verify pass read the commit's change), and no unresolved blocker
        stands at the review's trees (the pass resolved them) or at the
        commit's own (``trees``; unread is no)."""
        index = self._line_index()
        if index is None or trees is None:
            return None
        position, trees_at = index
        if commit not in position or parent not in position:
            return None
        at_commit, before = position[commit], position[parent]
        line = self.first_parent() or []
        # Where a tail can end: a first-parent tree at or after the commit that a
        # verify pass recorded as its head, or the commit's own tree.
        verified = {(f.get("body") or {}).get("head_tree") for f in self.tail_facts
                    if f.get("kind") == "review"}
        ends = [tree for i, (_sha, tree) in enumerate(line)
                if i <= at_commit and (tree in verified or i == at_commit)]
        # Newest first: two boundary reviews can stand at one tree (a release batch
        # reviewed the tree a PR's cumulative also ended at), and the fix answers
        # the newer one, which is the one its verify pass anchored to.
        for fact in reversed(self.boundary):
            head = (fact.get("body") or {}).get("head_tree")
            if not any(i >= before for i in trees_at.get(head, [])):
                continue
            if coverage_algebra.batch_review_blockers(self.facts, fact, trees):
                continue
            if any(self._verdict(self.tail_facts, head, end) == "covered" for end in dict.fromkeys(ends)):
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
    anchor, no_anchor = _resolve_anchor(project_dir, base)
    classifier = _Classifier(project_dir, read.get("facts", []), base,
                             anchor.commit if anchor is not None else None)
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
    if anchor is not None:
        walked = classifier.walk(anchor.commit)
        if walked is None:
            entries.append(Entry("", UNKNOWN, f"git could not list the first-parent commits on {base} "
                                              f"since the release anchor {anchor.commit[:8]}, so none "
                                              "of them was classified",
                                 source=SOURCE_WALK_FAILED))
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
    its release, and prerelease identifiers compare as SemVer orders them: split
    on dots, a numeric identifier by number and below any alphanumeric one, and a
    shorter run below a longer one it begins (``rc.9`` < ``rc.10`` < ``rc.10.1``)."""
    from . import release_readiness  # noqa: PLC0415 — lazy, as above

    version = release_readiness.normalize_version(name)
    if not change_log.RELEASE_VALUE_RE.match(version):
        return None
    numbers, _, pre = version[1:].partition("-")
    release = tuple(int(part) for part in numbers.split("."))
    if not pre:
        return release, (1,)
    return release, (0, tuple((0, int(part), "") if part.isdigit() else (1, 0, part)
                              for part in pre.split(".")))


def _is_version(text: str) -> bool:
    """Is ``text`` (already stripped) exactly one version, with or without its
    ``v`` (``3.10.1-dev``, ``v3.10.0``)? :func:`_version_key`'s shape."""
    return "\n" not in text and _version_key(text) is not None


#: How many side lines :func:`_released_on_line` follows back before giving up.
#: Each hop moves strictly older on the base's first-parent line, so the bound
#: only cuts off a pathological history, and giving up drops the candidate.
_MAX_SIDE_HOPS = 64


def _one_merge_base(git, one: str, other: str) -> "str | None":
    """A common ancestor of ``one`` and ``other``, or None (no shared history, or
    git could not answer). With several best merge-bases (criss-cross merges) it
    is their own merge-base, an ancestor of every one of them, so the answer is
    never newer than any: an anchor read from it can only widen the walk."""
    bases = (git("merge-base", "--all", one, other) or "").split()
    if len(bases) <= 1:
        return bases[0] if bases else None
    return git("merge-base", "--octopus", *bases) or None


def _release_file_records(git, base: str) -> "list[tuple[str, list, str]] | None":
    """``(commit, parents, path)`` for each first-parent commit on ``base`` whose
    diff against its first parent adds a release file
    (``.prawduct/releases/<version>.md``), newest first; None when git could not
    answer. A merge is listed when its merged line brought the file in, too."""
    out = git("log", "--first-parent", "-m", "--diff-filter=A", "--no-renames", "--name-only",
              "--format=%x1e%H %P", base, "--", f"{consumer_digest.RELEASES_DIR_REL}/")
    if out is None:
        return None
    records = []
    for record in out.split("\x1e"):
        head, _, names = record.strip().partition("\n")
        if not head:
            continue
        commit, *parents = head.split()
        for name in names.splitlines():
            parent, _, leaf = name.rpartition("/")
            if (parent == consumer_digest.RELEASES_DIR_REL and leaf.endswith(".md")
                    and _version_key(leaf[:-3]) is not None):
                records.append((commit, parents, name))
                break
    return records


def _release_file_candidate(git, base: str, line: dict) -> "tuple[str, str] | None":
    """``(anchor commit, reason)`` from the release files, or None.

    A commit that adds the file itself is its own answer. A merge that brought the
    file in through a side parent (a back-merge of ``main``, say) released nothing
    of the base's own: the answer is the base's own first-parent commit that the
    side line's adding commit released (:func:`_released_on_line`), which sits
    before the merge, so work the base took before the merge is walked. Of every
    record, the one whose answer is nearest the tip wins. Any git failure drops the
    candidate, and the other candidate is then the older or the same."""
    records = _release_file_records(git, base)
    if records is None:
        return None
    best = None  # (index on the line, commit, reason)
    for commit, parents, path in records:
        position = line.get(commit)
        if position is None:
            return None
        if best is not None and position > best[0]:
            break  # every later record is older, and resolves older still
        # (One at the best answer's own commit adds the file there: its reason wins.)
        through = None
        for side in parents[1:]:
            listed = git("ls-tree", "--name-only", side, "--", path)
            if listed is None:
                return None
            if listed:
                through = side
                break
        if through is None:
            best = (position, commit, f"{commit[:8]} adds the release file {path}")
            continue
        adder = git("log", "-1", "--format=%H", "--diff-filter=A", through, "--", path)
        released = _released_on_line(git, base, adder) if adder else None
        if released is None or released not in line:
            return None
        if best is None or line[released] < best[0]:
            best = (line[released], released,
                    f"{released[:8]} is the commit on {base} that {adder[:8]} released: its release "
                    f"file {path} came in through a side parent of {commit[:8]}")
    return (best[1], best[2]) if best else None


def _tag_candidates(git) -> "list[tuple[str, str]]":
    """``(tag, commit)`` for every release version tag, newest first by version
    order, whether or not the base can reach it (a release tagged on a promotion
    merge on ``main`` is never in the integration branch's history).

    A prerelease tag (``v3.12.0-rc.1``, ``-dev.N``) is no candidate: it marks no
    release, so commits between the last release and it would never be walked
    if it anchored. Only a release file the cut wrote can make a prerelease an
    anchor."""
    out = git("for-each-ref", "--format=%(refname:strip=2)%00%(objectname)%00%(*objectname)",
              "refs/tags")
    found = []
    for line in (out or "").splitlines():
        name, _, rest = line.partition("\0")
        target, _, peeled = rest.partition("\0")
        key = _version_key(name)
        if key is not None and key[1] == (1,):  # (1,) is a release; a prerelease is (0, ...)
            found.append((key, name, peeled or target))
    found.sort(key=lambda item: item[0], reverse=True)
    return [(name, commit) for _key, name, commit in found]


def _oldest_containing(git, base: str, tag_commit: str) -> "str | None":
    """The oldest first-parent commit on ``base`` that contains ``tag_commit``, an
    ancestor of ``base``. One on the first-parent line is its own answer; one
    merged in from a side line is answered by the merge that brought it in, which
    :func:`_released_on_line` follows back. None when git could not answer."""
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


def _released_on_line(git, base: str, released: str) -> "str | None":
    """The base's own first-parent commit that ``released`` (an ancestor of
    ``base``) shipped: ``released`` itself when it is on the first-parent line.

    One that arrived through a merge's side parent (a hotfix tag, or ``main``
    merged back into the base) shipped none of the work the base took before that
    merge, so the merge is not the answer: what the release shipped of the base's
    own line is its merge-base with the merge's first parent, followed back the
    same way until it lands on the line. Each hop is strictly older. None when git
    could not answer, or the side line shares no history with the base's own."""
    for _ in range(_MAX_SIDE_HOPS):
        holder = _oldest_containing(git, base, released)
        if holder is None or holder == released:
            return holder
        first = git("rev-parse", "--verify", "--quiet", f"{holder}^1")
        if not first:
            return None
        released = _one_merge_base(git, first, released)
        if released is None:
            return None
    return None


def release_anchor(project_dir: Path, base: str) -> "Anchor | None":
    """The release anchor on ``base``: whichever is nearer the tip of

    - (A) the newest first-parent commit adding a release file under
      ``.prawduct/releases/``, and
    - (B) the oldest first-parent commit containing the merge-base of ``base`` and
      the newest release version tag sharing history with it (by version order;
      a prerelease tag is never a candidate, :func:`_tag_candidates`).

    B reads the merge-base so that a release tagged where the base never goes (a
    promotion merge of develop into ``main``) anchors on the base commit it
    released. Where the base reaches the tag, the merge-base is the tag commit.

    Either candidate that reaches the base through a merge's side parent (a hotfix
    tag or a release file on ``main``, merged back) resolves to the base's own
    commit the release shipped (:func:`_released_on_line`), never to the merge:
    work merged into the base before the back-merge was not released, and is walked.

    A newest tag on a line that forked long ago (a hotfix branch) has an old
    merge-base, so B lands early and widens the walk, the safe direction; A, when
    present, then wins by being nearer. A tag sharing no history with the base
    is passed over for the next older one. None when there is neither candidate."""
    return _resolve_anchor(project_dir, base)[0]


def _resolve_anchor(project_dir: Path, base: str) -> "tuple[Anchor | None, str | None]":
    """``(anchor, None)``, or ``(None, why there is none)``.

    Every git failure fails toward the wider walk. A candidate git could not
    answer counts as absent, and the other is then the older or the same, because
    the anchor is the nearer of the two. The two are ordered by their place on the
    base's first-parent line, so without that line there is no anchor, which a
    gate refuses."""
    def git(*args: str) -> "str | None":
        rc, out, _err = evidence.run_git(project_dir, *args)
        return out.strip() if rc == 0 else None

    listed = git("rev-list", "--first-parent", base)
    if listed is None:
        return None, f"git could not list the first-parent line of {base}"
    line = {sha: i for i, sha in enumerate(listed.split())}  # 0 is the tip

    by_file = _release_file_candidate(git, base, line)
    tag = None
    by_tag = None
    # The newest release tag RELATED to the base: one sharing no history with it
    # (a fork's or a vendored tag), or whose release git cannot place on the
    # line, says nothing about what the base released, so the next older one is
    # asked rather than dropping the tag candidate altogether.
    for tag in _tag_candidates(git):
        released = _one_merge_base(git, base, tag[1])
        anchor = _released_on_line(git, base, released) if released else None
        if anchor is not None and anchor in line:
            what = (f"tag {tag[0]}" if released == tag[1]
                    else f"{released[:8]}, its merge-base with tag {tag[0]}")
            by_tag = (anchor, f"{anchor[:8]} is the oldest first-parent commit on {base} containing {what}"
                      if anchor == released else
                      f"{anchor[:8]} is the commit on {base} that {what} released: {what} came in "
                      "through a merge's side parent, which released none of the work merged before it")
            break

    # The nearer the tip wins (the smaller index); a tie goes to the release file.
    if by_file is not None and (by_tag is None or line[by_file[0]] <= line[by_tag[0]]):
        note = ("" if not by_tag else f"; tag {tag[0]} anchors at the same commit"
                if by_tag[0] == by_file[0] else f"; tag {tag[0]} anchors older on this line")
        chosen = (by_file[0], ANCHOR_RELEASE_FILE, by_file[1] + note)
    elif by_tag is not None:
        note = "; nearer the tip than the release file" if by_file else ""
        chosen = (by_tag[0], ANCHOR_TAG, by_tag[1] + note)
    else:
        return None, (f"no first-parent commit on {base} adds a release file under "
                      f"{consumer_digest.RELEASES_DIR_REL}/, and no version tag shares history with it "
                      "(or git could not answer for one of them)")
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


def classify_merge(project_dir: Path, commit: str, base: "str | None" = None) -> Entry:
    """Classify one commit on the base as :func:`classify_pending` would — for a
    caller that knows the commit rather than the scope. ``base`` (default: the
    repo's integration base) is the revision whose release anchor bookkeeping is
    read against, so a past reopen commit reads as it did before the next release."""
    if base is None:
        base, why = coverage.repo_base_branch(project_dir)
        if not base:
            return Entry("", UNKNOWN, f"no integration base resolves: {why}", commit)
    read = evidence.read_facts(project_dir)
    unreadable = _unreadable_store(read)
    if unreadable:
        return Entry("", UNKNOWN, unreadable, commit)
    anchor = release_anchor(project_dir, base)
    return _Classifier(project_dir, read.get("facts", []), base,
                       anchor.commit if anchor is not None else None).classify_commit(commit)


#: What :func:`release_subject` answers: a subject to dispatch, nothing owed
#: (``critic-begin`` exit 3), or a refusal naming one of the codes below.
RELEASE_OK = "ok"
RELEASE_NO_REVIEW_NEEDED = "no-review-needed"
RELEASE_REFUSED = "refused"

#: Why a release batch review dispatch refuses, each named in its reason.
RELEASE_OFF_BASE = "off-base"
RELEASE_DIRTY = "dirty-tree"
RELEASE_NO_ANCHOR = "no-anchor"
RELEASE_UNEVALUABLE = "unevaluable"
RELEASE_NO_SUBJECT = "no-subject"
#: The code of the no-review-needed answer.
RELEASE_NOTHING_OWED = "nothing-owed"


@dataclass(frozen=True)
class BaseTip:
    """Whether this checkout is the integration base's own branch with ``HEAD``
    at that base's tip (:func:`integration_base_tip`): ``code`` is empty there,
    else ``off-base`` or ``unevaluable`` with ``reason`` naming why."""

    base: "str | None"
    code: str = ""
    reason: str = ""
    #: The checkout is the base's own branch, at its tip or not.
    on_branch: bool = False

    @property
    def at_tip(self) -> bool:
        return self.base is not None and not self.code


def integration_base_tip(project_dir: Path) -> BaseTip:
    """THE answer to "is this checkout the integration base at its tip?", the
    one state where merge-base…``HEAD`` is empty for want of any branch, so the
    one place a release batch review can be taken and its head be a commit the
    release check walks. Two readers ask it: :func:`release_subject` refuses
    off it, and ``critic_consolidate.begin_review`` derives the release span on
    it for a plain ``cumulative`` (under ``per_release`` only), so the two
    cannot disagree about where the release review runs.

    The base is ``coverage.repo_base_branch``'s; a remote-tracking base
    (``origin/main``) is checked out as its local name, and ``HEAD`` must be
    that base's tip, so a local branch ahead of or behind its remote is off it.
    No base is ``unevaluable``; a git failure reads off the base, never on it."""
    from . import gitstate  # noqa: PLC0415 — lazy, as this module's other readers are

    def git(*args: str) -> "str | None":
        rc, out, _err = evidence.run_git(project_dir, *args)
        return out.strip() if rc == 0 else None

    base, why = coverage.repo_base_branch(project_dir)
    if not base:
        return BaseTip(None, RELEASE_UNEVALUABLE, f"no integration base resolves: {why}")
    branch = gitstate.current_branch(project_dir)
    local = base
    for remote in (git("remote") or "").split():
        if base.startswith(f"{remote}/"):
            local = base[len(remote) + 1:]
            break
    if branch != local:
        return BaseTip(base, RELEASE_OFF_BASE, (
            f"a release batch review runs on the integration base {base}'s own checkout, and this "
            f"one is on {branch or 'a detached HEAD'}"))
    head, tip = git("rev-parse", "HEAD"), git("rev-parse", f"{base}^{{commit}}")
    if not head or head != tip:
        return BaseTip(base, RELEASE_OFF_BASE, (
            f"HEAD {(head or '?')[:12]} is not {base}'s tip {(tip or '?')[:12]}: push or pull until "
            "they agree, so the review reads the line the release check walks"), on_branch=True)
    return BaseTip(base, on_branch=True)


def release_owed_blockers(project_dir: Path, facts: "list[dict] | None" = None) -> list[dict]:
    """The unresolved blocking findings the release check holds a ``per_release``
    release over that no review on the base raised: those standing at the own
    trees of a release entry no boundary review covered (``Entry.blockers``: a
    merged branch's, whose PR gate was bypassed). Deduplicated, in entry order.

    The second input of a ``verify-resolutions`` roll-call on the integration
    base (``critic_consolidate.carried_blocking``'s ``owed``). That pass anchors
    to the release batch review, the newest review on the base, and composes
    nothing from the base's own merge-base, so without this its roll-call never
    names a merged branch's blocker, nothing resolves it, and the release is
    held for good. ``BLOCKING findings clear only through verify-resolutions``,
    so this is how that route reaches them.

    ``[]`` off the base's own branch (at its tip or ahead of it, as after the
    fix is committed and before it is pushed), under ``per_pr`` (no release gate
    counts them, so naming them would manufacture a round), when ``facts`` holds
    no unresolved blocker at all (the cheap answer, asked first), or when the
    classification cannot be read: the release check refuses on its own then, so
    an omission here can hold a release longer, never pass it. Never raises."""
    if facts is not None:
        resolved = coverage_algebra.resolution_index(facts)
        if not any(coverage_algebra.unresolved_blocking(f, resolved)
                   for f in facts if f.get("kind") == "review"):
            return []
    from . import review_lane  # noqa: PLC0415 — lazy, as this module's other readers are

    try:
        if not integration_base_tip(project_dir).on_branch:
            return []
        if not review_lane.release_policy(project_dir).per_release:
            return []
        report = classify_pending(project_dir)
    except Exception:  # prawduct:allow prawduct/broad-except -- a roll-call input; the release check refuses on its own, so an omission holds a release longer and never passes one
        return []
    if report.status != "ok":
        return []
    out: list = []
    seen: set = set()
    for entry in report.entries:
        if entry.classification in COVERED:
            continue
        for blocker in entry.blockers:
            key = (blocker.get("review_id"), blocker.get("fid"))
            if key not in seen:
                seen.add(key)
                out.append(dict(blocker))
    return out


@dataclass
class ReleaseSubject:
    """What a release batch review rates, or why there is none to dispatch."""

    status: str  # RELEASE_OK | RELEASE_NO_REVIEW_NEEDED | RELEASE_REFUSED
    code: str
    reason: str
    base: "str | None" = None
    anchor: "Anchor | None" = None
    #: The release entries no boundary review covered.
    owed: list = field(default_factory=list)
    #: Their changed files that still differ from :attr:`start`: the review's subject.
    files: list = field(default_factory=list)
    #: Owed entries no review can credit: they name no commit (a fragment no
    #: commit on the base added, or a walk git could not run).
    uncreditable: list = field(default_factory=list)
    #: Where the review's interval starts, ``(commit, tree, reason)``: the
    #: anchor, or older when an owed entry sits at or before it (a scope a
    #: pruned release withheld), so the one review brackets every owed entry.
    start: "tuple | None" = None


def release_subject(project_dir: Path, *, clean: bool) -> ReleaseSubject:
    """The subject of a release batch review (``critic-begin --mode cumulative`` at
    the base's tip, which derives ``--span release``),
    asked from the checkout that would dispatch it. ``clean`` is whether the
    working tree equals ``HEAD`` (the dispatch's tree capture answers it).

    Refused, in this order, naming the code: the checkout is not the integration
    base at its tip (``off-base``: the review's head must be a commit the release
    check walks), the tree is dirty (``dirty-tree``: the review reads committed
    ``HEAD``), the classification cannot be read (``unevaluable``), there is no
    release anchor (``no-anchor``: nothing to start the span from), or the owed
    entries change no judgeable file that still differs from where the span
    starts (``no-subject``). The span starts at the anchor, or at the first
    parent of the oldest owed entry when one sits at or before it. Every entry covered is ``no-review-needed``
    (``nothing-owed``). Never raises: a fault is ``unevaluable``."""
    try:
        return _release_subject(project_dir, clean)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a dispatch refusal, attributed, never a traceback
        return ReleaseSubject(RELEASE_REFUSED, RELEASE_UNEVALUABLE,
                              f"the release classification failed: {type(exc).__name__}: {exc}")


def _release_subject(project_dir: Path, clean: bool) -> ReleaseSubject:
    def git(*args: str) -> "str | None":
        rc, out, _err = evidence.run_git(project_dir, *args)
        return out.strip() if rc == 0 else None

    def refused(code: str, reason: str, **kw) -> ReleaseSubject:
        return ReleaseSubject(RELEASE_REFUSED, code, reason, **kw)

    where = integration_base_tip(project_dir)
    if not where.at_tip:
        return refused(where.code, where.reason, base=where.base)
    base = where.base
    if not clean:
        return refused(RELEASE_DIRTY, "the working tree differs from HEAD: a release batch review reads "
                                      "committed HEAD, so commit or set the changes aside first", base=base)
    report = classify_pending(project_dir)
    if report.status != "ok":
        return refused(RELEASE_UNEVALUABLE, report.reason or "the release classification could not run",
                       base=base)
    anchor = report.anchor
    if anchor is None:
        return refused(RELEASE_NO_ANCHOR, f"there is no release anchor to start the span from: "
                                          f"{report.no_anchor_reason}", base=base)
    owed = [e for e in report.entries if e.classification not in COVERED]
    if not owed:
        return ReleaseSubject(RELEASE_NO_REVIEW_NEEDED, RELEASE_NOTHING_OWED,
                              f"every release entry is already covered ({count_line(report)})",
                              base=base, anchor=anchor)
    # Each owed entry's first parent on the base's first-parent line. An entry at
    # or before the anchor (a scope a pruned release withheld: merged before it,
    # still pending) moves the interval's start back to the oldest such parent,
    # so the review brackets it and the batch rule can credit it; a review that
    # started at the anchor never could, and the release would be held forever.
    line = git("rev-list", "--first-parent", "HEAD")
    if line is None:
        return refused(RELEASE_UNEVALUABLE, f"git could not list {base}'s first-parent line",
                       base=base, anchor=anchor)
    position = {sha: i for i, sha in enumerate(line.split())}  # 0 is the tip
    start = (anchor.commit, anchor.tree, anchor.reason)
    creditable: list = []
    uncreditable: list = []
    for entry in owed:
        parents = (git("rev-list", "--parents", "-n", "1", entry.commit) or "").split()[1:] if entry.commit else []
        if not parents or parents[0] not in position:
            uncreditable.append(entry)
            continue
        creditable.append((entry, parents[0]))
        if position[parents[0]] > position[start[0]]:
            tree = git("rev-parse", f"{parents[0]}^{{tree}}")
            if not tree:
                return refused(RELEASE_UNEVALUABLE, f"git could not read {parents[0][:12]}'s tree",
                               base=base, anchor=anchor)
            start = (parents[0], tree, f"{parents[0][:12]} is the first parent of {entry.label}, an entry "
                                       f"at or before the release anchor {anchor.commit[:12]} that no "
                                       f"boundary review covered, so the span starts there ({anchor.reason})")
    span = git("diff", "--name-only", "--no-renames", start[1], "HEAD", "--")
    if span is None:
        return refused(RELEASE_UNEVALUABLE, f"git could not diff {start[0][:12]} to HEAD",
                       base=base, anchor=anchor)
    in_span = set(span.splitlines())
    files: list = []
    for entry, parent in creditable:
        # What the commit brought onto the base: its diff against its first parent.
        changed = git("diff", "--name-only", "--no-renames", parent, entry.commit, "--")
        if changed is None:
            return refused(RELEASE_UNEVALUABLE, f"git could not diff {entry.label}",
                           base=base, anchor=anchor)
        files.extend(f for f in changed.splitlines() if f in in_span and f not in files)
    if not coverage_algebra.judgeable_files(files):
        return refused(RELEASE_NO_SUBJECT, f"{len(owed)} release entr{'y' if len(owed) == 1 else 'ies'} "
                                           f"no boundary review covered ({', '.join(e.label for e in owed)}) "
                                           "change no judgeable file that still differs from "
                                           f"{start[0][:12]}, where the span would start, so a batch "
                                           "review would rate nothing", base=base, anchor=anchor,
                       owed=owed, uncreditable=uncreditable, start=start)
    return ReleaseSubject(RELEASE_OK, "", f"{len(files)} file(s) owed a read since {start[0][:12]}",
                          base=base, anchor=anchor, owed=owed, files=files,
                          uncreditable=uncreditable, start=start)


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
    anchor = f"release anchor {report.anchor.commit[:8]} ({report.anchor.source})"
    by_fragment = sum(1 for e in report.entries if e.source == SOURCE_FRAGMENT)
    if any(e.source == SOURCE_WALK_FAILED for e in report.entries):
        return (f"boundary coverage: {covered} of {total} covered on {report.base}{detail}: the walk "
                f"since {anchor} could not run, so no commit since it was classified; "
                f"{by_fragment} by release-pending fragment")
    walked = sum(1 for e in report.entries if e.source in (SOURCE_WALK, SOURCE_BOTH))
    return (f"boundary coverage: {covered} of {total} covered on {report.base}{detail}: {walked} "
            f"judgeable commit(s) since {anchor}, and {by_fragment} more by release-pending fragment")


#: The release gate's two refusal codes: ``check-boundary-coverage --gate``'s
#: exit 1 and exit 3, and the prefix of ``check-releasability``'s refusal line.
GATE_UNCOVERED = "boundary-uncovered"
GATE_UNEVALUABLE = "boundary-unevaluable"


@dataclass(frozen=True)
class ReleaseGate:
    """The release check's verdict on one report under one policy."""

    exit: int  # 0 passes, 1 not covered, 3 could not answer
    code: str  # GATE_UNCOVERED | GATE_UNEVALUABLE | "" when it passes
    message: str  # the refusal, its remedy included; "" when it passes
    #: The entries it refused over (exit 1), for a caller listing them.
    owed: tuple = ()

    def as_dict(self) -> dict:
        return {"exit": self.exit, "code": self.code, "message": self.message}


def release_gate(report: Report, policy) -> ReleaseGate:
    """Does ``report`` hold the release, under ``policy``
    (``review_lane.release_policy``)? The one answer ``check-boundary-coverage
    --gate`` exits with and ``check-releasability`` refuses on (#1232).

    Under ``per_pr`` it passes whatever the report says: the op stays advice.
    Under ``per_release`` it fails closed, in this order: a policy whose read
    failed (``policy.read_failed``: the value is this checkout's fallback, so the
    check cannot say which policy the merged PRs were judged under), a report
    that could not be evaluated, a pending fragment the pending set refused (it
    is unclassified), or no release anchor (no commit since the last release was
    walked) is exit 3, ``boundary-unevaluable``; any entry not covered is exit 1,
    ``boundary-uncovered``; otherwise exit 0. Each refusal carries its remedy."""
    if not getattr(policy, "per_release", False):
        return ReleaseGate(0, "", "")
    held = "and `boundary_review: per_release` refuses a release its check cannot answer"
    if getattr(policy, "read_failed", False):
        return ReleaseGate(3, GATE_UNEVALUABLE, (
            f"{GATE_UNEVALUABLE}: {policy.note}, {held}: fix what the reason names, then re-run"))
    if report.status != "ok":
        return ReleaseGate(3, GATE_UNEVALUABLE, (
            f"{GATE_UNEVALUABLE}: the release's boundary coverage could not be evaluated "
            f"({report.reason}), {held}: fix what the reason names, then re-run"))
    if report.refusals:
        return ReleaseGate(3, GATE_UNEVALUABLE, (
            f"{GATE_UNEVALUABLE}: {len(report.refusals)} release-pending fragment(s) the pending set "
            f"refused are not classified ({'; '.join(report.refusals)}), {held}: fix each fragment, "
            "then re-run"))
    if report.anchor is None:
        return ReleaseGate(3, GATE_UNEVALUABLE, (
            f"{GATE_UNEVALUABLE}: there is no release anchor ({report.no_anchor_reason}), so no "
            f"commit since the last release was walked, {held}: tag the {report.base} commit your "
            "last release shipped with its version (`git tag vX.Y.Z <commit>`), or cut releases "
            f"with `cut-change-log`, which commits a `{consumer_digest.RELEASES_DIR_REL}/` file; "
            "a repo with no release yet keeps `per_pr` until its first"))
    owed = tuple(e for e in report.entries if e.classification not in COVERED)
    if not owed:
        return ReleaseGate(0, "", "")
    unreachable = [e.label for e in owed if not e.commit]
    message = (
        f"{GATE_UNCOVERED}: {len(owed)} of {len(report.entries)} release entr"
        f"{'y' if len(report.entries) == 1 else 'ies'} on {report.base} no boundary review "
        "covered, and `boundary_review: per_release` holds the release until one has read them: "
        f"run the release batch review, `/prawduct:critic cumulative`, on {report.base}'s own "
        "checkout at its tip with a clean tree, where its dispatch `prawduct-hook critic-begin "
        "--mode cumulative` derives the release span (`prawduct-hook critic-begin --mode "
        "cumulative --span release` is the explicit form); fix a blocker it raises on "
        f"{report.base} and clear it with `/prawduct:critic verify-resolutions` there; then re-run")
    blocked = [e for e in owed if e.blockers]
    if blocked:
        # A merged branch's blocker is not the batch review's, so the batch never
        # clears it; the verify pass on the base names it in its roll-call
        # (release_owed_blockers), which is the one route that resolves it.
        named = [f"{b.get('review_id')} {b.get('fid')}" for e in blocked for b in e.blockers]
        one = len(blocked) == 1
        message += (
            f". {', '.join(e.label for e in blocked)} also {'carries' if one else 'carry'} an "
            f"unresolved blocking finding on {'its' if one else 'their'} own trees "
            f"({', '.join(named[:3])}{' …' if len(named) > 3 else ''}), a merged branch's, which "
            f"no batch review clears: fix it on {report.base}'s own checkout and run "
            "`/prawduct:critic verify-resolutions` there, whose roll-call names it")
    if unreachable:
        message += (f". {', '.join(unreachable)} name no commit, so no review can credit "
                    f"{'it' if len(unreachable) == 1 else 'them'}: commit the fragment on "
                    f"{report.base}, or fix the git failure the reason names")
    return ReleaseGate(1, GATE_UNCOVERED, message, owed)


def render(report: Report) -> str:
    """The human report: one line per entry, the anchor, then the count line with its denominator."""
    if report.status != "ok":
        return f"check-boundary-coverage: could not evaluate — {report.reason}"
    lines = [
        f"{e.classification:19} "
        f"{e.label if e.scope or e.source == SOURCE_WALK_FAILED else '(no fragment) ' + repr(e.subject)}  "
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
