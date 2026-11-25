"""`critic-begin --mode cumulative` refuses when `check-pr-hygiene` would refuse
the PR for a credential-shaped line the branch adds, before it derives anything.

The cumulative is the review `/prawduct:pr create` composes. Met at PR time,
after it, the waiver or the removal moves HEAD and buys another round, and a
waiver in a code file buys a suite run too. Met at dispatch, it lands before
the round is spent. The check is the PR gate's own over the same span, so it
refuses only what the PR would; every other mode, and every branch the PR gate
passes, dispatches as before.

Exit 9 is pinned as a literal because it is a contract (`api-contract.md`,
Error Model). Credentials are assembled at run time, so this file's own source
carries no line the check would flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_critic_consolidate import MARKER_REL, PARTIALS_REL, _commit_file, _git, _init_repo, _run_begin, _store_facts

from lib import critic_consolidate, pr_gate

CREDENTIAL_EXIT = 9
_REAL = "postgres://" + "app:Xk9mQ2vLr7@db/app"
_PLACEHOLDER = "postgres://" + "app:password@db/app"
_WAIVER = "prawduct:allow " + "prawduct/credential-shape -- a test fixture, never a live database"


def _branch(tmp_path: Path, content: str) -> Path:
    """A `develop` base and a feature branch that adds ``settings.py``."""
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / ".prawduct").mkdir()
    (repo / ".prawduct" / "project-state.yaml").write_text("base_branch: develop\n")
    _git(repo, "checkout", "-q", "-b", "develop")
    _commit_file(repo, "src/app.py", "x = 1\n", "base")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    _commit_file(repo, "settings.py", content, "add settings")
    return repo


def _guard_facts(repo: Path) -> list[dict]:
    return [
        f for f in _store_facts(repo, "guard-refusal")
        if (f.get("body") or {}).get("guard") == critic_consolidate.CREDENTIAL_GUARD
    ]


def _dispatched(result) -> bool:
    return result.returncode == 0


class TestCumulativeRefusesWhatThePrGateWould:
    def test_a_real_looking_credential_refuses_before_anything_is_written(self, tmp_path):
        repo = _branch(tmp_path, f'DSN = "{_REAL}"\n')
        assert pr_gate.branch_credential_shapes(repo)[0], "fixture: the PR gate must refuse it"

        result = _run_begin(repo, "--mode", "cumulative")

        assert result.returncode == CREDENTIAL_EXIT, (result.stdout, result.stderr)
        assert "settings.py:1" in result.stdout and "url-embedded password" in result.stdout
        assert "Xk9mQ2vLr7" not in result.stdout + result.stderr
        assert "prawduct/credential-shape" in result.stdout
        assert "/prawduct:critic cumulative" in result.stdout
        assert not (repo / PARTIALS_REL / "manifest.json").exists()
        assert not (repo / MARKER_REL).exists()
        facts = _guard_facts(repo)
        assert len(facts) == 1 and facts[0]["body"]["reason"] == "credential-shape", facts

    def test_force_dispatches_anyway(self, tmp_path):
        repo = _branch(tmp_path, f'DSN = "{_REAL}"\n')
        result = _run_begin(repo, "--mode", "cumulative", "--force")
        assert _dispatched(result), (result.stdout, result.stderr)
        assert _guard_facts(repo) == []
        # Forced past the round budget, it must not lose this refusal silently.
        assert "credential-shaped line(s)" in result.stderr and "settings.py:1" in result.stderr
        assert "Xk9mQ2vLr7" not in result.stdout + result.stderr


class TestEverythingElseDispatchesAsBefore:
    def test_a_waived_line_dispatches(self, tmp_path):
        repo = _branch(tmp_path, f'DSN = "{_REAL}"  # {_WAIVER}\n')
        result = _run_begin(repo, "--mode", "cumulative")
        assert _dispatched(result), (result.stdout, result.stderr)

    def test_a_placeholder_only_branch_dispatches(self, tmp_path):
        repo = _branch(tmp_path, f'DSN = "{_PLACEHOLDER}"\n')
        result = _run_begin(repo, "--mode", "cumulative")
        assert _dispatched(result), (result.stdout, result.stderr)
        assert _guard_facts(repo) == []

    @pytest.mark.parametrize("mode", ["chunk", "final", "verify-resolutions"])
    def test_inner_modes_do_not_run_the_check(self, tmp_path, monkeypatch, mode):
        """Only the review the PR gate composes meets the PR gate's check: the
        check is never asked, whatever else the dispatch then answers."""
        repo = _branch(tmp_path, f'DSN = "{_REAL}"\n')
        asked: list[str] = []
        monkeypatch.setattr(pr_gate, "branch_credential_shapes", lambda d: asked.append(mode) or ([], None))

        critic_consolidate.begin_review(repo, mode)

        assert asked == []
        assert _guard_facts(repo) == []

    def test_the_cumulative_does_ask_the_check(self, tmp_path, monkeypatch):
        """The control for the test above: the same probe does see a cumulative."""
        repo = _branch(tmp_path, f'DSN = "{_PLACEHOLDER}"\n')
        asked: list[str] = []
        monkeypatch.setattr(pr_gate, "branch_credential_shapes", lambda d: asked.append("c") or ([], None))

        critic_consolidate.begin_review(repo, "cumulative")

        assert asked == ["c"]

    def test_an_unreadable_span_dispatches_with_a_note(self, tmp_path, monkeypatch):
        """The check could not read the lines (a git fault): the PR gate fails
        closed on that itself, so the review dispatches and says so."""
        repo = _branch(tmp_path, f'DSN = "{_REAL}"\n')
        monkeypatch.setattr(
            pr_gate, "branch_credential_shapes", lambda _d: ([], "the diff could not be read")
        )

        result = critic_consolidate.begin_review(repo, "cumulative")

        assert result["status"] == "ok", result
        assert any("could not read this branch's lines" in n for n in result["notes"]), result["notes"]
