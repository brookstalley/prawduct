"""Nothing tells the builder to buy a round a later review will cover (#167).

When the branch's plan still owes a later review, and a covered frontier exists,
the next ``chunk``/``final`` review starts at that frontier and covers any fix
committed after it (``gates.covered_frontier``). So mode inference, the Stop
gate, the review close and ``cost-of-commit`` must stop recommending a
``verify-resolutions`` or ``cumulative`` round for that fix. Each surface is
tested in both directions: mid-plan (two or more chunks unticked, the round is
deferred) and near the end (one chunk unticked, today's answer stands).

Plans here have five chunks so the short-plan deferral (at most three) cannot
pre-empt what is being tested.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lib import critic_consolidate as cc
from lib import critic_mode
from lib.critic_mode import MODE_DEFERRED, infer_mode
from test_critic_consolidate import (
    HOOK,
    PARTIALS_REL,
    ROOT,
    _commit_file,
    _git,
    _git_env,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)
from test_short_plan_deferral import _GENERIC_BLOCK, _arm_stop, _run_stop

WARNING = {"name": "Tighten the loop", "goal": "Nothing Is Unintended",
           "severity": "warning", "recommendation": "Tighten", "files": ["src/app.py"]}
BLOCKING = {"name": "Broken", "goal": "Nothing Is Broken",
            "severity": "blocking", "recommendation": "Fix", "files": ["src/app.py"]}
# Chunks already ticked of five. The chunk under review is the next one, still
# unticked: MID leaves it and four more (a later review is owed); END leaves it alone.
MID, END = 0, 4


def _plan(ticked: int) -> str:
    rows = "".join(
        f"- [{'x' if n <= ticked else ' '}] Chunk {n}: part {n}\n" for n in range(1, 6)
    )
    sections = "".join(f"\n### Chunk {n}: part {n}\n\n- **Delivers:** part {n}\n" for n in range(1, 6))
    return (
        "---\nartifact: build-plan\nscope: work\nbranch: feat/work\n---\n\n"
        f"# Plan\n\n## Status\n\n{rows}{sections}"
    )


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _scenario(
    tmp_path: Path, ticked: int, findings: list, *, commit_fix: bool, commit_reviewed: bool = True
) -> tuple[Path, str]:
    """The current chunk reviewed with ``findings``, committed verbatim (unless
    ``commit_reviewed`` is False: the fix then goes straight onto the reviewed,
    uncommitted tree), then the fix — committed or left in the working tree.
    Returns the repo and the NEXT-ACTION line."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    _commit_file(repo, ".prawduct/artifacts/build-plan-work.md", _plan(ticked), "plan")
    _git(repo, "checkout", "-b", "feat/work", "--quiet")
    (repo / "src/app.py").write_text("x = 2\n")
    begin = _run_begin(repo, "--mode", "chunk", "--chunk", str(ticked + 1))
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=findings)
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    next_action = next(
        line for line in done.stdout.splitlines() if line.startswith("NEXT-ACTION:")
    )
    if commit_reviewed:
        _commit_all(repo, "the chunk, reviewed")
    (repo / "src/app.py").write_text("x = 3  # the finding, fixed\n")
    if commit_fix:
        _commit_all(repo, "fix, unreviewed")
    return repo, next_action


class TestLaterReviewOwed:
    def test_two_or_more_unticked_chunks_owe_a_later_review(self):
        progress = type("P", (), {"total": 5, "complete": 3})
        assert critic_mode.later_review_owed(progress)

    def test_one_unticked_chunk_is_ambiguous_and_owes_nothing(self):
        # Just reviewed but not yet ticked, or one chunk left: the conservative
        # reading keeps the round rather than defer a fix nothing will cover.
        progress = type("P", (), {"total": 5, "complete": 4})
        assert not critic_mode.later_review_owed(progress)


class TestModeInference:
    def test_a_fix_in_progress_mid_plan_is_deferred(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "extension-deferred (fix in progress)" in why

    def test_a_fix_in_progress_near_the_end_still_verifies(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == "verify-resolutions", why

    def test_a_committed_fix_mid_plan_is_deferred_not_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "extension-deferred (mid-plan, clean tree)" in why

    def test_a_committed_fix_near_the_end_still_infers_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why

    def test_a_blocker_is_never_deferred(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [BLOCKING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == "verify-resolutions", why


class TestStopGate:
    def test_mid_plan_the_uncovered_fix_warns_instead_of_blocking(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 0, result.stderr
        assert _GENERIC_BLOCK not in result.stderr
        assert "deferred-boundary-review" in result.stderr
        assert "starts from the last reviewed state" in result.stderr

    def test_near_the_end_the_uncovered_fix_still_blocks(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr


class TestReviewClose:
    def test_mid_plan_the_close_leads_with_the_later_review(self, tmp_path):
        _, line = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        assert "This plan still owes a later review" in line
        # The advice it replaces must be gone, not trailing after it.
        assert cc._RIDE_ALONG_ROUTE.strip() not in line
        assert cc._IF_YOU_FIX_SOME.strip() not in line

    def test_near_the_end_the_close_keeps_its_price(self, tmp_path):
        _, line = _scenario(tmp_path, END, [WARNING], commit_fix=False)
        assert "This plan still owes a later review" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() in line

    def test_a_blocking_close_is_unchanged_mid_plan(self):
        line = cc.next_action_line("rev-x", 1, 0, 0, rides_next_review=True)
        assert "This plan still owes a later review" not in line
        assert "verify-resolutions" in line


class TestCostOfCommit:
    def _price(self, repo: Path) -> dict:
        result = subprocess.run(
            ["python3", str(HOOK), "cost-of-commit", "--json"],
            cwd=str(repo), capture_output=True, text=True,
            env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_mid_plan_the_unreviewed_commit_is_free(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        answer = self._price(repo)
        assert answer["verdict"] == "free"
        assert "starts from the last reviewed state" in answer["rides_next_review"]

    def test_near_the_end_it_still_costs_a_round(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        answer = self._price(repo)
        assert answer["verdict"] == "costs-a-round"
        assert answer["rides_next_review"] is None


class TestWidenedFallback:
    def test_final_is_recommended_when_a_frontier_sits_behind_the_commits(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        mode, why = cc._widened_fallback_mode(repo, head_tree, True)
        assert mode == "final", why
        assert "last reviewed state" in why

    def test_cumulative_when_no_reviewed_state_sits_behind_them(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _git(repo, "checkout", "-b", "feat/work", "--quiet")
        head = _commit_file(repo, "src/app.py", "x = 2\n", "unreviewed")
        head_tree = _git(repo, "rev-parse", f"{head}^{{tree}}").stdout.strip()
        mode, why = cc._widened_fallback_mode(repo, head_tree, True)
        assert mode == "cumulative", why


class TestNothingOwedIsSkipped:
    """The two ways a deferral could skip a review that is owed."""

    def test_a_blocker_on_an_uncommitted_review_is_never_deferred(self, tmp_path):
        """The ordinary flow: review the uncommitted chunk, fix its blocker in
        place. The blocked tree was never committed, so the history walk cannot
        see it and finds the OLDER clean commit behind it — chunk 1's — as the
        frontier. Only the check on the newest review itself stops the defer."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2\n")
        begin = _run_begin(repo, "--mode", "chunk", "--chunk", "2")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"],
                       findings=[{**BLOCKING, "files": ["src/other.py"]}])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 2  # the blocker, fixed in place\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_a_later_chunk_nobody_reviewed_is_not_deferred(self, tmp_path):
        """Chunk 1 reviewed, committed and ticked; chunk 2 built and not
        reviewed. The frontier exists, a later review is owed — and still the
        pending work is a whole chunk, whose own review this must not skip."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2, unreviewed\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_a_blocker_a_verify_pass_left_open_is_never_deferred(self, tmp_path):
        """A verify pass that names no resolution and raises nothing new is clean
        on its own, while the blocker it was verifying is still open one review
        back. The chain has to be walked, not just the newest fact read."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2\n")
        begin = _run_begin(repo, "--mode", "chunk", "--chunk", "2")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"],
                       findings=[{**BLOCKING, "files": ["src/other.py"]}])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 2  # an attempted fix\n")
        verify = _run_begin(repo, "--mode", "verify-resolutions", "--chunk", "2")
        assert verify.returncode == 0, verify.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 3  # keeps editing\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_after_a_cumulative_nothing_defers_and_the_close_promises_nothing(self, tmp_path):
        """A `cumulative` spans every chunk built so far and records at most one
        chunk id, so afterwards unticked boxes may be chunks awaiting their tick
        rather than chunks still to build. Found on this change's own branch:
        the boundary review's verify pass promised 'the next chunk's review
        covers the fix' with every chunk already built."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        _commit_all(repo, "fix")
        begin = _run_begin(repo, "--mode", "cumulative", "--chunk", "1")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[WARNING])
        done = _run_consolidate(repo)
        assert done.returncode == 0, done.stderr
        line = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
        assert "This plan still owes a later review" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() in line  # the ordinary close, priced
        (repo / "src/app.py").write_text("x = 4  # a fix after the boundary review\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why


class TestReviewChain:
    def _review(self, rid, base, head, ts, blocking=False, mode="chunk"):
        findings = [{"fid": "R-1", "severity": "blocking", "title": "x"}] if blocking else []
        return {"kind": "review", "id": rid, "ts": ts,
                "body": {"base_tree": base, "head_tree": head, "findings": findings, "mode": mode}}

    def test_every_review_at_a_linked_tree_is_on_the_chain(self):
        """A second review of an unchanged tree must not hide a blocker the
        first one raised at that same tree."""
        blocked = self._review("r1", "t0", "t1", "2026-09-22T10:00:00Z", blocking=True)
        rereview = self._review("r2", "t0", "t1", "2026-09-22T11:00:00Z")
        newest = self._review("r3", "t1", "t2", "2026-09-22T12:00:00Z")
        facts = [blocked, rereview, newest]
        chain = critic_mode.review_chain(facts, newest)
        assert {f["id"] for f in chain} == {"r1", "r2", "r3"}
        assert critic_mode._open_blocker_on_chain(facts, chain)

    def test_a_cumulative_anywhere_on_the_chain_marks_the_boundary(self):
        cumulative = self._review("r1", "t0", "t1", "2026-09-22T10:00:00Z",
                                  mode="cumulative (bundle review, ready for merge)")
        verify = self._review("r2", "t1", "t2", "2026-09-22T11:00:00Z",
                              mode="verify-resolutions (delta review, prior findings only)")
        assert critic_mode.boundary_review_on_chain(critic_mode.review_chain([cumulative, verify], verify))
        assert not critic_mode.boundary_review_on_chain(critic_mode.review_chain([verify], verify))

    def test_same_second_reviews_are_ordered_by_the_store_not_the_clock(self, monkeypatch):
        """`ts` has one-second resolution; CI records a chunk review and the
        cumulative after it in the same second. The store is append-only, so
        its order is the recording order, and it alone can break the tie."""
        ts = "2026-09-22T10:00:00Z"
        chunk = self._review("r1", "t0", "t1", ts)
        cumulative = self._review("r2", "t0", "t1", ts, mode="cumulative (bundle review, ready for merge)")
        verify = self._review("r3", "t1", "t2", ts,
                              mode="verify-resolutions (delta review, prior findings only)")
        for f in (chunk, cumulative, verify):
            f["actor"] = {"branch": "feat/work"}
        monkeypatch.setattr(critic_mode.gitstate, "current_branch", lambda _p: "feat/work")
        from lib import evidence
        monkeypatch.setattr(evidence, "read_facts",
                            lambda _p: {"status": "ok", "facts": [chunk, cumulative, verify]})
        newest = critic_mode._newest_branch_review(Path("."))
        assert newest["id"] == "r3"
        chain = critic_mode.review_chain([chunk, cumulative, verify], newest)
        assert {f["id"] for f in chain} == {"r1", "r2", "r3"}
        assert critic_mode.boundary_review_on_chain(chain)
        # And the newest pick with a same-second tie at the END of the store.
        monkeypatch.setattr(evidence, "read_facts",
                            lambda _p: {"status": "ok", "facts": [chunk, cumulative]})
        assert critic_mode._newest_branch_review(Path("."))["id"] == "r2"
