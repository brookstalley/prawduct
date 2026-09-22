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
MID, END = 1, 4  # chunks ticked of five: four left (a later review is owed), one left


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


def _scenario(tmp_path: Path, ticked: int, findings: list, *, commit_fix: bool) -> tuple[Path, str]:
    """Chunk reviewed with ``findings``, committed verbatim, then the fix — committed
    or left in the working tree. Returns the repo and the NEXT-ACTION line."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    _commit_file(repo, ".prawduct/artifacts/build-plan-work.md", _plan(ticked), "plan")
    _git(repo, "checkout", "-b", "feat/work", "--quiet")
    (repo / "src/app.py").write_text("x = 2\n")
    begin = _run_begin(repo, "--mode", "chunk", "--chunk", "1")
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=findings)
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    next_action = next(
        line for line in done.stdout.splitlines() if line.startswith("NEXT-ACTION:")
    )
    _commit_all(repo, "chunk 1, reviewed")
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
