"""Mid-plan, the router answers from what is unreviewed, not from commit order.

The stage-keyed rigor norm (`nonfunctional-requirements.md` § Direction) keys a
review's stage on WHERE IN THE CYCLE it sits (owner ruling, 2026-09-25). A
builder who commits a chunk before reviewing it leaves a clean tree, and rule 2
(and rule 4's clean-tree redirect, and the explicit-token redirect) used to
answer `cumulative` there — boundary rigor on inner-stage work, at 12, 17, 27
and 31 commits ahead on one branch. Mid-plan (the branch's own plan still owes
a later review) the answer is now `chunk` over the unreviewed interval: from the
covered frontier, or from the merge-base when no blocker-free reviewed state is behind HEAD.
At the PR point (plan complete, or its last chunk committed) it is `cumulative`
as before, and a branch whose plan cannot be shown keeps rule 2.

Each inference case is paired with the interval `critic-begin` then captures,
because a mode named into an interval that cannot see the work is the failure
this replaces with a different one.

Plans here have five chunks, so the short-plan deferral (at most three) cannot
pre-empt what is tested — except where a short plan is the subject.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import buildplan_refs, gates
from lib import critic_consolidate as cc
from lib.critic_mode import MODE_DEFERRED, infer_mode
from test_critic_consolidate import (
    PARTIALS_REL,
    _commit_file,
    _git,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)


def _plan(ticked: int, *, chunks: int = 5, scoped: bool = True) -> str:
    rows = "".join(
        f"- [{'x' if n <= ticked else ' '}] Chunk {n}: part {n}\n" for n in range(1, chunks + 1)
    )
    sections = "".join(
        f"\n### Chunk {n}: part {n}\n\n- **Delivers:** part {n}\n" for n in range(1, chunks + 1)
    )
    front = "---\nartifact: build-plan\nscope: work\nbranch: feat/work\n---\n\n" if scoped else ""
    return f"{front}# Plan\n\n## Status\n\n{rows}{sections}"


def _plan_path(repo: Path, scoped: bool = True) -> Path:
    name = "build-plan-work.md" if scoped else "build-plan.md"
    return repo / ".prawduct" / "artifacts" / name


def _repo(tmp_path: Path, *, ticked: int = 0, chunks: int = 5, scoped: bool = True) -> Path:
    """A branch building a plan, with session state gitignored the way a real
    repo ignores it — so a clean tree means clean, not "the fixture's findings
    file happened to be committed"."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, ".gitignore", ".prawduct/.*\n", "ignore session state")
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    rel = str(_plan_path(repo, scoped).relative_to(repo))
    _commit_file(repo, rel, _plan(ticked, chunks=chunks, scoped=scoped), "plan")
    _git(repo, "checkout", "-b", "feat/work", "--quiet")
    return repo


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _review_uncommitted(repo: Path, chunk: str) -> None:
    """The contract's order: review the chunk while it is uncommitted."""
    begin = _run_begin(repo, "--mode", "chunk", "--chunk", chunk)
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr


def _tick(repo: Path, ticked: int, *, scoped: bool = True, chunks: int = 5) -> str:
    _plan_path(repo, scoped).write_text(_plan(ticked, chunks=chunks, scoped=scoped))
    return _commit_all(repo, f"tick chunk {ticked}")


def _commit_first(repo: Path, n_commits: int = 2, name: str = "chunk") -> list[str]:
    """A chunk committed BEFORE its review, in ``n_commits`` commits."""
    return [
        _commit_file(repo, f"src/{name}_{i}.py", f"# {name} part {i}\n", f"{name} part {i}")
        for i in range(n_commits)
    ]


def _begin_manifest(repo: Path, mode: str) -> dict:
    begin = _run_begin(repo, "--mode", mode)
    assert begin.returncode == 0, f"{mode}: {begin.stderr}"
    return json.loads((repo / PARTIALS_REL / "manifest.json").read_text())


def _merge_base(repo: Path) -> str:
    return _git(repo, "merge-base", "main", "HEAD").stdout.strip()


class TestCommitFirstMidPlanIsAChunk:
    def test_a_committed_chunk_behind_a_reviewed_one_is_reviewed_from_the_frontier(
        self, tmp_path
    ):
        """Chunk 1 reviewed (uncommitted), committed and ticked; chunk 2 committed
        before its review. The frontier is the tick; the chunk review covers
        chunk 2's commits and nothing chunk 1's review already saw."""
        repo = _repo(tmp_path)
        (repo / "src/app.py").write_text("x = 2  # chunk 1\n")
        _review_uncommitted(repo, "1")
        _commit_all(repo, "chunk 1, reviewed")
        tick = _tick(repo, 1)
        _commit_first(repo, 2, "chunk2")

        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        assert why.startswith("rule-2 mid-plan chunk:"), why
        assert "last reviewed state" in why

        manifest = _begin_manifest(repo, mode)
        assert manifest["base_commit"] == tick
        assert sorted(manifest["files_changed"]) == ["src/chunk2_0.py", "src/chunk2_1.py"]

    @pytest.mark.parametrize("n_commits", [1, 2, 12, 31])
    def test_a_first_chunk_committed_before_any_review_is_reviewed_from_the_merge_base(
        self, tmp_path, n_commits
    ):
        """Nothing on the branch is reviewed, so the unreviewed interval is
        everything the branch committed. One commit ahead reaches rule 4's
        redirect; two or more reach rule 2 — both answer `chunk` mid-plan, at
        any distance (the observed mid-plan cumulatives fired at 12 to 31)."""
        repo = _repo(tmp_path)
        _commit_first(repo, n_commits)

        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        rule = "rule-4" if n_commits == 1 else "rule-2"
        assert why.startswith(f"{rule} mid-plan chunk:"), why
        assert "merge-base" in why

        manifest = _begin_manifest(repo, mode)
        assert manifest["base_commit"] == _merge_base(repo)
        assert manifest["base_extended_from"] is not None
        assert sorted(manifest["files_changed"]) == sorted(
            f"src/chunk_{i}.py" for i in range(n_commits)
        )

    def test_the_merge_base_review_composes_for_the_gates(self, tmp_path):
        """The interval is not just dispatchable: the fact it records covers the
        branch, so no `cumulative` is owed for the commits it reviewed."""
        repo = _repo(tmp_path)
        _commit_first(repo, 2)
        manifest = _begin_manifest(repo, "chunk")
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
        assert _run_consolidate(repo).returncode == 0
        assert gates.branch_coverage_verdict(repo)["status"] == "covered"


class TestTheBoundaryIsKept:
    def test_the_last_chunk_committed_is_the_boundary(self, tmp_path):
        """One unticked chunk and a clean tree: the last chunk is committed, and
        the boundary review is the right answer."""
        repo = _repo(tmp_path, ticked=4)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why
        assert why.startswith("rule-2 cumulative:"), why

    def test_a_complete_plan_is_the_boundary(self, tmp_path):
        repo = _repo(tmp_path, ticked=5)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why

    def test_a_plan_not_shown_to_be_this_branchs_keeps_rule_2(self, tmp_path):
        """A plan reached only through the active-plan pointer is assumed
        related, and the boundary is never inferred away on an assumption."""
        repo = _repo(tmp_path, scoped=False)
        plan = buildplan_refs.resolve_branch_plan(repo, repo / ".prawduct")
        assert plan.path is not None  # the plan IS found — just not as this branch's
        assert plan.source != buildplan_refs.SOURCE_SCOPE_NAMED
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why
        assert why.startswith("rule-2 cumulative:"), why

    def test_uncommitted_records_over_an_unreviewed_branch_keep_rule_2(self, tmp_path):
        """The interval's merge-base start is bounded to a clean tree. With only
        records uncommitted, a `chunk` interval would start at HEAD and reach no
        committed work, so the router must not name it — it keeps today's
        answer rather than recommend a review that sees nothing."""
        repo = _repo(tmp_path)
        _commit_first(repo, 2)
        path = _plan_path(repo)
        path.write_text(path.read_text() + "\nContext: edited.\n")
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why


class TestNothingOwedNow:
    def test_a_reviewed_committed_and_ticked_chunk_owes_nothing(self, tmp_path):
        """The contract's order, completed: nothing is unreviewed, so a `chunk`
        would dispatch an empty interval and a `cumulative` would re-review the
        whole branch mid-plan. Neither is owed."""
        repo = _repo(tmp_path)
        (repo / "src/app.py").write_text("x = 2  # chunk 1\n")
        _review_uncommitted(repo, "1")
        _commit_all(repo, "chunk 1, reviewed")
        _tick(repo, 1)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "nothing unreviewed" in why

    def test_a_short_plan_mid_plan_defers_on_a_clean_tree_too(self, tmp_path):
        """A short plan traded per-chunk review for the boundary one. Committing
        the chunk first does not buy the review back."""
        repo = _repo(tmp_path, chunks=3)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert why.startswith("short-plan deferral:"), why


class TestExplicitTokensMidPlan:
    @pytest.mark.parametrize("token", ["chunk", "final"])
    def test_a_named_working_tree_mode_is_not_redirected_mid_plan(self, tmp_path, token):
        repo = _repo(tmp_path)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, token)
        assert mode == token, why
        assert why.startswith(f"explicit-args {token} (mid-plan, not redirected):"), why
        manifest = _begin_manifest(repo, mode)
        assert manifest["base_commit"] == _merge_base(repo)

    @pytest.mark.parametrize("token", ["chunk", "final"])
    def test_a_named_mode_with_nothing_unreviewed_stands_rather_than_redirecting(
        self, tmp_path, token
    ):
        """Mid-plan with the reviewed chunk committed verbatim, inference answers
        `deferred`. The named token must come from the same verdict. It stands, so
        `critic-begin` gives the honest empty-interval refusal, and it never becomes
        a whole-branch `cumulative` mid-plan."""
        repo = _repo(tmp_path)
        (repo / "src/app.py").write_text("x = 2  # chunk 1\n")
        _review_uncommitted(repo, "1")
        _commit_all(repo, "chunk 1, reviewed")
        _tick(repo, 1)
        mode, why = infer_mode(repo, token)
        assert mode == token, why
        assert why.startswith(f"explicit-args {token} (mid-plan, nothing unreviewed):"), why

    @pytest.mark.parametrize("token", ["chunk", "final"])
    def test_at_the_boundary_the_redirect_stands(self, tmp_path, token):
        repo = _repo(tmp_path, ticked=5)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, token)
        assert mode == "cumulative", why
        assert why.startswith(f"explicit-args {token} redirected:"), why


class TestTheIntervalOwner:
    """`critic-begin`'s side, driven directly: where the interval starts."""

    def test_a_clean_unreviewed_branch_starts_at_the_merge_base(self, tmp_path):
        repo = _repo(tmp_path)
        _commit_first(repo, 1)
        manifest = _begin_manifest(repo, "chunk")
        assert manifest["base_commit"] == _merge_base(repo)
        assert manifest["files_changed"] == ["src/chunk_0.py"]

    def test_uncommitted_work_keeps_the_head_anchored_interval(self, tmp_path):
        """The control: with work in flight the HEAD-anchored interval is not
        empty, and the first review of it must not become a whole-branch one."""
        repo = _repo(tmp_path)
        head = _commit_first(repo, 1)[-1]
        (repo / "src/wip.py").write_text("# in flight\n")
        manifest = _begin_manifest(repo, "chunk")
        assert manifest["base_commit"] == head
        assert manifest["base_extended_from"] is None

    def test_a_frontier_that_could_not_be_looked_for_does_not_fall_back(
        self, tmp_path, monkeypatch
    ):
        """"Could not look" is not "nothing reviewed": no whole-branch interval
        is chosen on a failed read, so the clean tree's empty interval refuses."""
        repo = _repo(tmp_path)
        _commit_first(repo, 2)
        monkeypatch.setattr(gates, "FRONTIER_WALK_LIMIT", 1)
        result = cc.begin_review(repo, "chunk")
        assert result["status"] == "error", result
        assert "empty diff" in result["reason"]


class TestTheMergeBaseStartSaysWhy:
    """``covered_frontier`` returns ``None`` for three different states, and the
    merge-base start must say which. Only one of them is "nothing reviewed": the
    others are an open blocker on the nearest reviewed state, and a reviewed
    state that no longer composes (a base sync). Calling a blocker "nothing
    reviewed" hides it, and a ``chunk`` review records no resolutions, so the
    blocker outlives it."""

    def _blocked_then_committed(self, tmp_path) -> Path:
        repo = _repo(tmp_path)
        (repo / "src/app.py").write_text("x = 2  # chunk 1\n")
        begin = _run_begin(repo, "--mode", "chunk", "--chunk", "1")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[
            {"name": "Broken", "goal": "Nothing Is Broken", "severity": "blocking",
             "recommendation": "Fix", "files": ["src/app.py"]},
        ])
        assert _run_consolidate(repo).returncode == 0
        _commit_all(repo, "chunk 1, reviewed with an open blocker")
        _commit_first(repo, 2, "chunk2")
        return repo

    def test_the_frontier_names_which_none_it_returned(self, tmp_path):
        repo = self._blocked_then_committed(tmp_path)
        absent: list[str] = []
        assert gates.covered_frontier(repo, absent=absent) is None
        assert absent == [gates.FRONTIER_ABSENT_BLOCKED]

        fresh = _repo(tmp_path / "fresh")
        _commit_first(fresh, 2)
        absent = []
        assert gates.covered_frontier(fresh, absent=absent) is None
        assert absent == [gates.FRONTIER_ABSENT_NONE_COMPOSES]

        # Only free (non-judgeable) commits: covered by free edges, no review on
        # the path. That is the one state the plain "nothing reviewed" describes.
        free = _repo(tmp_path / "free")
        _commit_file(free, "notes.md", "a note\n", "free commit 1")
        _commit_file(free, "notes.md", "a note, revised\n", "free commit 2")
        absent = []
        assert gates.covered_frontier(free, absent=absent) is None
        assert absent == [gates.FRONTIER_ABSENT_UNREVIEWED]

    def test_an_open_blocker_is_named_by_the_router_not_called_unreviewed(self, tmp_path):
        repo = self._blocked_then_committed(tmp_path)
        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        assert "unresolved blocking finding" in why, why
        assert "verify-resolutions" in why, why
        assert "nothing on this branch is reviewed" not in why, why

    def test_an_open_blocker_is_named_by_critic_begin(self, tmp_path):
        repo = self._blocked_then_committed(tmp_path)
        begin = _run_begin(repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        out = begin.stdout + begin.stderr
        assert "unresolved blocking finding" in out, out
        assert "nothing on this branch has been reviewed yet" not in out, out

    def test_a_never_reviewed_branch_says_so_and_names_the_sync_case(self, tmp_path):
        """No reviewed state composes: the rationale cannot tell "never reviewed"
        from "reviewed before a base sync", so it names both, never just one."""
        repo = _repo(tmp_path)
        _commit_first(repo, 2)
        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        assert "no reviewed state on this branch composes" in why, why
        assert "base sync" in why, why
