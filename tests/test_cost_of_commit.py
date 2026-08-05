"""Tests for `prawduct-hook cost-of-commit` and the round-price helper.

The command answers, before a commit is made, whether making it buys a review
round. It exists because a consuming agent on v3.2.4 ran six Critic rounds on
one branch and reported that the one fact that would have changed its
sequencing — that `.gitignore` is not a free edge — was only learnable *after*
committing.

Two properties are load-bearing and pinned hard:

1. **The classification is the gate's own.** The command must not re-derive
   "does this need review"; it asks `coverage_algebra.is_judgeable_path`, the
   same predicate that will charge for the commit afterwards. A pricing tool
   that disagrees with the gate is worse than none.
2. **Degradation reports `unknown`, never `free`.** A builder who reads "free"
   from a broken check makes exactly the commit the command exists to price.
   The asymmetry is the whole safety argument.

The price itself is *derived from the repo's own ledger at call time* and
never written down — a number copied into prose drifts, and correcting it
costs the very review round this is meant to save. So there is also a test
asserting no message carries a hardcoded duration.

Real git repos, sterile env (HOME outside the repo), mirroring
tests/test_classify_diff_risk.py.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import telemetry  # noqa: E402
from lib.coverage import commit_cost  # noqa: E402
from lib.coverage_algebra import is_judgeable_path  # noqa: E402


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".prawduct").mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init", "--quiet")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "cost-of-commit", *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def _ledger(repo: Path, rounds: list[float], mode: str = "verify-resolutions") -> None:
    """Write a governance ledger carrying `rounds` timed reviews of `mode`."""
    lines = []
    for seconds in rounds:
        lines.append(json.dumps({
            "event": "review.critic",
            "duration_seconds": seconds,
            "actor": {"role": "critic", "model": "opus"},
            "review": {"mode": f"{mode} (some verbose suffix)", "findings": []},
        }))
    (repo / ".prawduct" / ".governance-ledger.jsonl").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# The classification — one predicate, shared with the gate
# ---------------------------------------------------------------------------


class TestClassification:
    def test_gitignore_costs_a_round(self, tmp_path: Path) -> None:
        """The reporter's exact case, pinned so it cannot silently become free.

        `.gitignore` is not metadata and not `.md`, so it is judgeable — which
        is precisely what the reporting agent learned one commit too late.
        """
        assert is_judgeable_path(".gitignore") is True
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, ".gitignore")
        assert result.returncode == 0
        assert result.stdout.splitlines()[0] == "costs-a-round"
        assert ".gitignore" in result.stdout

    def test_a_free_path_set_reports_free(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, ".prawduct/learnings.md", ".prawduct/backlog.md")
        assert result.returncode == 0
        assert result.stdout.splitlines()[0] == "free"

    def test_one_judgeable_path_makes_the_whole_commit_cost(self, tmp_path: Path) -> None:
        """Coverage is not proportional — a single judgeable path in an
        otherwise-free batch buys the round for the batch, and the verdict
        must name WHICH path did it so the builder can drop it."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, ".prawduct/learnings.md", "src/app.py", ".prawduct/backlog.md")
        assert result.stdout.splitlines()[0] == "costs-a-round"
        assert "src/app.py" in result.stdout
        assert "1 of 3" in result.stdout

    def test_it_asks_the_gates_own_predicate(self) -> None:
        """The anti-drift property: every path the command calls judgeable is
        judgeable to `is_judgeable_path`, and every path it calls free is not.

        A second copy of this classification is the failure this test exists
        to make impossible — it would let the command promise "free" for a
        commit the gate then charges for.
        """
        paths = [
            ".gitignore", "src/app.py", "plugin/lib/x.py", "CLAUDE.md",
            ".prawduct/learnings.md", "docs/guide.md", "skills/critic/x.md",
            ".claude/settings.json", "methodology/building.md",
        ]
        cost = commit_cost(Path("/nonexistent"), paths)
        for path in cost["judgeable"]:
            assert is_judgeable_path(path), f"{path} reported judgeable but the predicate disagrees"
        for path in cost["free"]:
            assert not is_judgeable_path(path), f"{path} reported free but the predicate disagrees"
        assert set(cost["judgeable"]) | set(cost["free"]) == set(paths)


# ---------------------------------------------------------------------------
# The no-argument form — the question actually being asked
# ---------------------------------------------------------------------------


class TestWorkingTree:
    def test_no_arguments_prices_the_working_tree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("x = 1\n")
        result = _run(repo)
        assert result.stdout.splitlines()[0] == "costs-a-round"
        assert "src/app.py" in result.stdout

    def test_a_clean_tree_has_nothing_to_price(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo)
        assert result.stdout.splitlines()[0] == "free"
        assert "nothing to price" in result.stdout

    def test_an_untracked_directory_is_priced_by_its_files(self, tmp_path: Path) -> None:
        """`git status --porcelain` collapses an untracked directory to one
        `docs/` entry, which is wrong here twice: it names a path the builder
        cannot drop from the commit, and a directory of nothing but free files
        classifies as judgeable (not metadata, not `.md`) — pricing a free
        commit as costly.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / "docs").mkdir()
        (repo / "docs" / "a.md").write_text("a\n")
        (repo / "docs" / "b.md").write_text("b\n")
        result = _run(repo)
        assert result.stdout.splitlines()[0] == "free", (
            "an untracked directory of doc files was priced as costing a round"
        )
        assert "docs/" not in result.stdout.replace("docs/a.md", "").replace("docs/b.md", "")

    def test_a_directory_argument_is_priced_by_its_files(self, tmp_path: Path) -> None:
        """The explicit-argument twin of the untracked-directory case.

        `git add docs/` stages the files beneath it, never an entry named
        `docs/` — and the directory string classifies as judgeable (neither
        metadata nor `.md`), so pricing it directly reports a doc-only
        directory as costing a round.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / "docs").mkdir()
        (repo / "docs" / "a.md").write_text("a\n")
        result = _run(repo, "docs/")
        assert result.stdout.splitlines()[0] == "free", (
            "a doc-only directory argument was priced as costing a round"
        )

    def test_a_directory_argument_still_catches_a_judgeable_file(self, tmp_path: Path) -> None:
        """Expansion must not become a way to under-charge."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("x = 1\n")
        result = _run(repo, "src")
        assert result.stdout.splitlines()[0] == "costs-a-round"
        assert "src/app.py" in result.stdout

    def test_a_path_that_does_not_exist_is_classified_as_given(self, tmp_path: Path) -> None:
        """Pricing a file before creating it is a legitimate question, so a
        non-existent path is never silently dropped by the expansion."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, "src/not_yet.py")
        assert result.stdout.splitlines()[0] == "costs-a-round"
        assert "src/not_yet.py" in result.stdout

    def test_untracked_and_staged_both_count(self, tmp_path: Path) -> None:
        """A commit takes the whole working tree, so pricing must not miss
        either side of the index."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / "staged.py").write_text("a = 1\n")
        _git(repo, "add", "staged.py")
        (repo / "untracked.py").write_text("b = 2\n")
        result = _run(repo)
        assert "staged.py" in result.stdout
        assert "untracked.py" in result.stdout


# ---------------------------------------------------------------------------
# The price — derived, never asserted; unavailable, never wrong
# ---------------------------------------------------------------------------


class TestRoundPrice:
    def test_a_thin_sample_is_unavailable_not_a_median(self, tmp_path: Path) -> None:
        """Two rounds do not establish a repo's price. Reporting their median
        as one would be the same drifting-number defect the helper exists to
        avoid, only computed instead of typed."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _ledger(repo, [300.0, 900.0])
        price = telemetry.round_price(repo / ".prawduct")
        assert price["status"] == "unavailable"
        assert "too few" in price["reason"]

    def test_a_sufficient_sample_is_priced(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _ledger(repo, [120.0, 240.0, 300.0, 360.0, 600.0])
        price = telemetry.round_price(repo / ".prawduct")
        assert price["status"] == "priced"
        assert price["median_seconds"] == 300.0
        assert price["reviews"] == 5

    def test_no_ledger_is_unavailable(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        assert telemetry.round_price(repo / ".prawduct")["status"] == "unavailable"

    def test_it_prices_the_round_a_fix_actually_buys(self, tmp_path: Path) -> None:
        """A fix commit buys a `verify-resolutions` pass, not a cumulative.
        Pricing the wrong mode quotes a number the builder never pays."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _ledger(repo, [600.0] * 5, mode="cumulative")
        assert telemetry.round_price(repo / ".prawduct")["status"] == "unavailable"

    def test_unavailable_is_stated_not_swallowed(self, tmp_path: Path) -> None:
        """'Advice fails soft' is not 'advice fails silent' — a price that
        could not be computed must say so, or its absence reads as free."""
        rendered = telemetry.format_round_price({"status": "unavailable", "reason": "no history"})
        assert "unavailable" in rendered
        assert "no history" in rendered
        assert "missing number, not a small one" in rendered


# ---------------------------------------------------------------------------
# Degradation — the asymmetry that makes this safe
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_an_unreadable_tree_reports_unknown_not_free(self, tmp_path: Path) -> None:
        """The load-bearing safety property. `free` from a broken check sends
        the builder into the exact commit this command exists to price, and
        the gate would tell them only afterwards."""
        not_a_repo = tmp_path / "bare"
        (not_a_repo / ".prawduct").mkdir(parents=True)
        result = _run(not_a_repo)
        assert result.stdout.splitlines()[0] == "unknown"
        assert "not a free one" in result.stdout

    def test_a_bad_argument_exits_one(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, "--bogus")
        assert result.returncode == 1
        assert "unknown argument" in result.stderr

    def test_a_missing_price_never_blocks_the_verdict(self, tmp_path: Path) -> None:
        """The command answers whether a commit costs a round even when it
        cannot say how much — the two facts are independent."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, "src/app.py")
        assert result.returncode == 0
        assert result.stdout.splitlines()[0] == "costs-a-round"


# ---------------------------------------------------------------------------
# The output contract
# ---------------------------------------------------------------------------


class TestOutput:
    def test_the_verdict_leads_on_stdout(self, tmp_path: Path) -> None:
        """stdout is the agent-facing channel, and the first token is the
        machine-readable answer — matching `classify-diff-risk`."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        result = _run(repo, "src/app.py")
        assert result.stdout.splitlines()[0] in {"free", "costs-a-round", "unknown"}

    def test_the_human_path_is_exercised_not_only_json(self, tmp_path: Path) -> None:
        """A `--json`-only test never runs the formatter, which is where the
        reader-facing defects live."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _ledger(repo, [300.0] * 6)
        result = _run(repo, "src/app.py")
        assert "review-stats" in result.stdout, "the re-derivation command is not cited"
        assert "5 min" in result.stdout

    def test_json_carries_the_verdict_and_the_price(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _ledger(repo, [300.0] * 6)
        result = _run(repo, "--json", "src/app.py", ".prawduct/learnings.md")
        payload = json.loads(result.stdout)
        assert payload["verdict"] == "costs-a-round"
        assert payload["judgeable"] == ["src/app.py"]
        assert payload["free"] == [".prawduct/learnings.md"]
        assert payload["round_price"]["status"] == "priced"

    def test_no_message_hardcodes_a_duration(self) -> None:
        """The regression this repo has already paid for: a number written
        into prose drifts, and correcting it buys the round the message is
        trying to prevent. Assert the WRONG form is absent, not merely that
        the right form is present.

        Only literals in the *emitted* strings are the subject — the sample
        sizes and thresholds in code are not quoted to anyone.

        **The scope is the surfaces that quote a PRICE**, and the granularity
        differs on purpose. `coverage.py` and `telemetry.py` exist to answer
        "what does this cost", so they are scanned whole. `gates.py` and
        `critic_consolidate.py` also carry a duration of a different kind — how
        long a reviewer typically runs, which tells a reader whether silence is
        still normal. That number is an expectation about a subagent, not a
        price offered to change a spending decision, and it is not derivable
        from the ledger at the point it is printed. Scanning those modules
        whole would flag it forever, and a guard people have to argue with gets
        deleted rather than fixed — so the price-bearing surfaces inside them
        are named individually.

        The list is maintained alongside the callers rather than frozen: a
        guard aimed at the one file that cannot regress reports green forever,
        which is precisely how this test's first draft passed while the
        sentence it guarded lived somewhere else.
        """
        from lib import critic_consolidate, gates  # noqa: PLC0415

        scanned = {
            "lib/coverage.py": (ROOT / "lib" / "coverage.py").read_text(),
            "lib/telemetry.py": (ROOT / "lib" / "telemetry.py").read_text(),
            "gates.check_cumulative_critic": inspect.getsource(
                gates.check_cumulative_critic
            ),
            "critic_consolidate.next_action_line": inspect.getsource(
                critic_consolidate.next_action_line
            ),
        }
        # A module constant has no source to scan for interpolation — every
        # digit in its VALUE is hardcoded by construction, so the value itself
        # is the subject. It printed "5-10 minute rounds" until the round price
        # became derivable, which is the case that put it on this list.
        emitted = [
            (f"{name} (emitted line)", line)
            for name, source in scanned.items()
            for line in re.findall(r'^\s*(?:print\(|\s+f?")(.*)$', source, re.MULTILINE)
        ] + [
            ("critic_consolidate._BATCH_FIX_DIRECTIVE", critic_consolidate._BATCH_FIX_DIRECTIVE),
        ]
        for name, line in emitted:
            assert not re.search(r"\b\d+\s*(?:min|minute|sec|second)s?\b", line), (
                f"a duration is hardcoded into emitted text in {name}: "
                f"{line.strip()!r} — the price must be derived from the ledger "
                "at call time"
            )
