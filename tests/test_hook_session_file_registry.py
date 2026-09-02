"""The session-file registry — four sites, and now four guarded (#324).

Adding one session file requires editing at least four places in lockstep:

1. ``core.GITIGNORE_ENTRIES`` — the canonical set, and what ``update_gitignore``
   writes into a governed repo;
2. the hook's ``_SESSION_GITIGNORED_PATHS`` — the untrack set
   ``_untrack_session_files`` feeds to ``git ls-files``;
3. **this repo's own** ``.gitignore`` — prawduct is itself a governed repo, and
   nothing writes its copy for it;
4. the ``/clear`` boundary's disposition of the file — deleted with the session,
   or deliberately carried across it.

Only 1↔2 were guarded (``TestSessionGitignoreMirror`` in
``test_build_plan_resolution.py``). A new session file that missed site 3 got
**committed by accident**; one that missed site 4 **survived `/clear` and leaked
state into the next session**. Both failures are silent, and both were reached in
practice — ``.handoff-notes.md`` had to be threaded through all four by hand.

**Site 4 is not a set to match, it is a decision to force.** Most of the session
set deliberately outlives a boundary (the per-clone advisory nag log, the
findings archive, the handoff the boundary *writes into*), so equality
would be the wrong assertion and a subset check would let a new file default to
"never deleted" — which is exactly the leak. Instead the two dispositions are
enumerated with reasons and asserted to PARTITION the session set, so a new
session file fails here until someone says which side it is on.

Both lists are read from the source, never transcribed: ``doomed`` is parsed out
of ``_boundary_close_session`` and the entries out of ``core``, because a registry
test that carries its own copy of the registry is a fifth site.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"

_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_registry", str(HOOK))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_registry", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)

from lib import core as _core  # noqa: E402


def _session_set() -> set[str]:
    """Site 1, normalised: every session path, no trailing slash.

    ``__pycache__`` is excluded for the reason the 1↔2 mirror test already gives
    — it is a ``.gitignore`` line, not a session file.
    """
    return {p.rstrip("/") for p in _core.GITIGNORE_ENTRIES} - {"__pycache__"}


def _boundary_deleted() -> set[str]:
    """Site 4, parsed from ``_boundary_close_session``'s own source.

    Both forms the loop uses: the ``doomed = [...]`` literal, and the
    ``doomed.insert(0, "…")`` that adds the reflection once it has been safely
    archived. Parsed rather than transcribed — a copy here would drift the first
    time the loop changed, and a registry test that drifts is worse than none.
    """
    source = inspect.getsource(_hook._boundary_close_session)
    literal = re.search(r"\n    doomed = \[(.*?)\]", source, re.S)
    assert literal is not None, (
        "the boundary's `doomed` list moved out of `_boundary_close_session` — "
        "re-point this parser rather than transcribing the list"
    )
    names = set(re.findall(r'"([^"]+)"', literal.group(1)))
    for inserted in re.findall(r'doomed\.insert\(\d+,\s*"([^"]+)"\)', source):
        names.add(inserted)
    assert names, "parsed no names from the deletion loop — the test would be vacuous"
    return {f".prawduct/{name}" for name in names}


#: Every session file that OUTLIVES a boundary, and the reason it does. A file
#: is here or it is deleted; there is no third answer, and no default.
_BOUNDARY_SURVIVORS = {
    ".claude/settings.local.json":
        "the user's own harness settings — not prawduct state at all, gitignored so a "
        "local permission grant is never committed",
    ".prawduct/.bug-inbox":
        "the upstream drop-box's marker; its contents are triaged by a person, on their "
        "own schedule, not by a session ending",
    ".prawduct/.critic-active":
        "swept by its OWN boundary step, not this loop — the sweep has to weigh the "
        "marker's TTL and announce a retained one, which a blind unlink cannot do",
    ".prawduct/.critic-findings.json":
        "the review's verdict, which the PR gate reads across sessions; deleting it at "
        "the boundary would make every review session-local",
    ".prawduct/.critic-partials":
        "cleared by `critic-begin`, which knows whether a review is live; a boundary "
        "does not, and a fork's parent may still be writing into it",
    ".prawduct/.critic-partials-archive":
        "the archive `critic-restore` reads — its whole purpose is outliving the review",
    ".prawduct/.delegate-brief.md":
        "a delegate worktree's dispatch record, and the ONLY signal the unintegrated-"
        "delegate advisory has; a boundary deleting it would erase the evidence of "
        "compute already spent",
    ".prawduct/.governance-ledger.jsonl":
        "the append-only ledger; it is history, and history does not end with a session",
    ".prawduct/.test-evidence.json":
        "the test record the freshness gates compare against `.session-start` — the "
        "comparison is what makes it stale, so deleting it would defeat the gate",
    ".prawduct/.pr-reviews":
        "PR review records, read at the merge boundary rather than the session one",
    ".prawduct/.session-handoff.md":
        "REWRITTEN by the boundary, not removed — it is the bridge the next session "
        "reads, so an unlink here would delete the thing being handed over",
    ".prawduct/.subagent-briefing.md":
        "regenerated at the end of every boundary; unlinking it first would only "
        "widen the window in which a subagent reads nothing",
    ".prawduct/.advisories.json":
        "the per-clone nag log, which holds DISMISSALS — deleting it would un-dismiss "
        "every advisory the owner had already decided about",
    ".prawduct/.work-model-index.json":
        "retired in v3.3.2 along with the tripwire that wrote it; nothing produces it, "
        "and the gitignore entry only keeps pre-3.3.2 leftovers invisible",
    ".prawduct/.handoff-notes.md":
        "deleted at the boundary, but by the handoff generator rather than this loop — "
        "consumption keys on the handoff having been PRESERVED, so an unconditional "
        "unlink here would destroy notes that never reached a handoff",
}


class TestSitesOneAndTwoStillAgree:
    """Restated here so this file can be read alone. The canonical assertion
    still lives with the mirror in ``test_build_plan_resolution.py``."""

    def test_the_untrack_set_covers_the_session_set(self):
        assert {p.rstrip("/") for p in _hook._SESSION_GITIGNORED_PATHS} == _session_set()


class TestSiteThreeThisReposOwnGitignore:
    """Prawduct is itself a governed repo, and nothing writes its ``.gitignore``
    for it — ``update_gitignore`` runs in the repos prawduct onboards, not in
    prawduct. So the file that keeps this repo's own session state untracked is
    maintained by hand, and a new entry missed here is a session file committed
    by accident into the framework repo itself.
    """

    @staticmethod
    def _lines() -> set[str]:
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        return {
            line.strip().rstrip("/")
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    def test_every_canonical_entry_is_ignored_here_too(self):
        missing = sorted(_session_set() - self._lines())
        assert not missing, (
            "session file(s) in core.GITIGNORE_ENTRIES that this repo's own "
            f".gitignore does not cover — they get committed by accident: {missing}"
        )

    def test_the_pycache_entry_is_here_as_well(self):
        # Not a session file, but the same list writes it, and its absence here
        # would be just as noisy.
        assert "__pycache__" in self._lines()


class TestSiteFourTheBoundaryDisposition:
    """A session file is deleted at the boundary or it deliberately outlives it,
    and the two sets must partition the registry.

    The failure this prevents is the quiet one: a new session file that nobody
    added to the deletion loop survives `/clear` and leaks its state into the
    next session, where it reads as this session's own.
    """

    def test_the_two_dispositions_are_disjoint(self):
        both = _boundary_deleted() & set(_BOUNDARY_SURVIVORS)
        assert not both, f"a file cannot both be deleted and survive: {sorted(both)}"

    def test_every_session_file_has_a_boundary_disposition(self):
        undecided = sorted(_session_set() - _boundary_deleted() - set(_BOUNDARY_SURVIVORS))
        assert not undecided, (
            "session file(s) with no recorded boundary disposition. Add each to "
            "cmd_clear's deletion loop, or to _BOUNDARY_SURVIVORS with the reason it "
            f"must outlive a session: {undecided}"
        )

    def test_neither_disposition_names_a_file_that_is_not_a_session_file(self):
        strays = sorted((_boundary_deleted() | set(_BOUNDARY_SURVIVORS)) - _session_set())
        assert not strays, (
            "the boundary disposition names path(s) that are not in "
            f"core.GITIGNORE_ENTRIES — one of the two lists is stale: {strays}"
        )

    def test_every_survivor_states_why(self):
        # A bare list would re-create the defect one level up: the next author
        # reads "not deleted" and cannot tell a decision from an omission.
        thin = sorted(p for p, why in _BOUNDARY_SURVIVORS.items() if len(why) < 40)
        assert not thin, f"survivor(s) with no real reason recorded: {thin}"

    def test_the_deletion_loop_is_what_this_reads(self):
        # The parser is the load-bearing part: a transcribed copy would pass
        # forever after the loop changed. Pin what it found.
        assert ".prawduct/.session-start" in _boundary_deleted()
        assert ".prawduct/.session-base-tree" in _boundary_deleted()
        assert ".prawduct/.gates-waived" in _boundary_deleted()
        # Conditionally inserted once the reflection is safely archived, and the
        # parser has to see that form too.
        assert ".prawduct/.session-reflected" in _boundary_deleted()
