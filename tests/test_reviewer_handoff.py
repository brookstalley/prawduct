"""A capped single-pass review is handed to one dispatched reviewer.

On a session above the reviewer ceiling the manifest carries `reviewer_model`,
and the forked Critic reviews nothing itself: it dispatches the roster's
reviewers on that model and stops — for the single-pass roster, one
`critic-reviewer` in role `reviewer`. That reviewer writes its marker and its
partial; the `SubagentStop` hook consolidates, as it does for the three-reviewer
roster. Without a reviewer model, the fork reviews inline and consolidates its
own partial, exactly as before.

The directives `critic-begin` prints for a reviewer are rendered once, by
`critic_consolidate.dispatch_directives`, and the same list rides the manifest
when a reviewer model is set, because the handed-off reviewer never sees the
fork's tool output.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import critic_consolidate as cc  # noqa: E402
from lib import evidence  # noqa: E402

PARTIALS_REL = ".prawduct/.critic-partials"
MANIFEST_REL = f"{PARTIALS_REL}/manifest.json"
MARKER_REL = ".prawduct/.critic-active"
ABOVE = "claude-fable-1"
AT_CEILING = "claude-opus-4-8[1m]"


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


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    ).stdout.strip()


def _hook(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True, input=stdin,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "maintenance.auto", "false")
    (repo / ".prawduct").mkdir()
    (repo / ".gitignore").write_text(".prawduct/.*\n")
    for rel in ("src/app.py", "src/two.py", "src/three.py"):
        (repo / rel).parent.mkdir(exist_ok=True)
        (repo / rel).write_text("x = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init", "--quiet")
    for rel in ("src/app.py", "src/two.py", "src/three.py"):
        (repo / rel).write_text("x = 2\n")
    return repo


def _manifest(repo: Path) -> dict:
    return json.loads((repo / MANIFEST_REL).read_text())


def _begin(repo: Path, mode: str, session_model: str) -> tuple[subprocess.CompletedProcess, dict]:
    result = _hook(repo, "critic-begin", "--mode", mode, "--session-model", session_model)
    assert result.returncode == 0, result.stderr
    return result, _manifest(repo)


def _write_as_dispatched_reviewer(repo: Path, *, findings=None, resolutions=None) -> None:
    """What a handed-off `critic-reviewer` writes: its started marker, then its
    partial, both at the paths the manifest's rendezvous names."""
    manifest = _manifest(repo)
    paths = manifest["rendezvous"]["reviewer"]
    (repo / paths["started"]).write_text("reviewer")
    partial = {
        "role": "reviewer",
        "goals": "1-3",
        "dispatch_id": manifest["id"],
        "commit_reviewed": manifest["commit_reviewed"],
        "model": "claude-opus-4-8",
        "duration_seconds": 60,
        "findings": findings or [],
        "summary": "reviewed",
    }
    if resolutions is not None:
        partial["resolutions"] = resolutions
    (repo / paths["partial"]).write_text(json.dumps(partial))


def _subagent_stop(repo: Path) -> subprocess.CompletedProcess:
    return _hook(
        repo, "subagent-stop",
        stdin=json.dumps({"cwd": str(repo), "agent_type": "prawduct:critic-reviewer"}),
    )


def _review_facts(repo: Path) -> list[dict]:
    return [f for f in evidence.read_facts(repo).get("facts") or [] if f.get("kind") == "review"]


class TestTheDirectivesHaveOneRenderer:
    def test_a_capped_chunk_carries_its_directives_and_prints_the_same(self, tmp_path):
        repo = _repo(tmp_path)
        result, manifest = _begin(repo, "chunk", ABOVE)
        assert manifest["reviewer_model"] is not None
        assert manifest["roster"] == ["reviewer"]
        assert manifest["dispatch_directives"] == [cc.FINDING_SCOPE_DIRECTIVE]
        # Same text, and last in the output, where the pinned order puts it.
        assert result.stdout.rstrip("\n").endswith("\n".join(manifest["dispatch_directives"]))

    def test_without_a_reviewer_model_the_manifest_carries_none(self, tmp_path):
        repo = _repo(tmp_path)
        result, manifest = _begin(repo, "chunk", AT_CEILING)
        assert manifest["reviewer_model"] is None
        assert "dispatch_directives" not in manifest
        # The fork still reads them, from the dispatch output.
        assert result.stdout.rstrip("\n").endswith(cc.FINDING_SCOPE_DIRECTIVE)

    @pytest.mark.parametrize("mode", ["final", "cumulative"])
    def test_a_capped_full_review_owes_no_directive(self, tmp_path, mode):
        repo = _repo(tmp_path)
        if mode == "cumulative":
            _git(repo, "checkout", "--quiet", "-b", "feature/x")
            _git(repo, "commit", "-am", "work", "--quiet")
        result = _hook(repo, "critic-begin", "--mode", mode, "--session-model", ABOVE)
        assert result.returncode == 0, result.stderr
        assert _manifest(repo)["dispatch_directives"] == []

    def test_a_capped_verify_carries_all_four_in_the_pinned_order(self, tmp_path):
        repo = _repo(tmp_path)
        prior_id = _seed_a_blocking_review(repo)
        result, manifest = _begin(repo, "verify-resolutions", ABOVE)
        directives = manifest["dispatch_directives"]
        assert len(directives) == 4, directives
        assert directives[0] == cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE
        assert directives[1] == cc.FINDING_SCOPE_DIRECTIVE
        assert f"{prior_id}/R-1" in directives[2] and "must come back with a verdict" in directives[2]
        assert directives[3] == cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE
        assert result.stdout.rstrip("\n").endswith("\n".join(directives))

    def test_the_renderer_is_what_the_dispatch_prints(self, tmp_path):
        """Control on the claim 'one renderer': the function, called on the
        written manifest and the store, returns exactly what was printed."""
        repo = _repo(tmp_path)
        _seed_a_blocking_review(repo)
        result, manifest = _begin(repo, "verify-resolutions", AT_CEILING)
        rendered = cc.dispatch_directives(manifest, evidence.read_facts(repo)["facts"])
        assert len(rendered) == 4
        assert result.stdout.rstrip("\n").endswith("\n".join(rendered))


def _seed_a_blocking_review(repo: Path) -> str:
    """A real capped chunk review carrying one blocking finding, consolidated
    by the SubagentStop trigger; then the fix lands in the working tree."""
    _begin(repo, "chunk", ABOVE)
    prior_id = _manifest(repo)["id"]
    _write_as_dispatched_reviewer(repo, findings=[{
        "name": "Broken", "goal": "Nothing Is Broken", "severity": "blocking",
        "recommendation": "fix it", "files": ["src/app.py"],
    }])
    stopped = _subagent_stop(repo)
    assert stopped.returncode == 0, stopped.stderr
    assert not (repo / MANIFEST_REL).exists(), "the seed review did not consolidate"
    _git(repo, "add", "src")
    _git(repo, "commit", "-m", "land the reviewed change", "--quiet")
    (repo / "src/app.py").write_text("x = 3  # fixed\n")
    return prior_id


class TestAHandedOffReviewConsolidatesWithoutTheFork:
    def test_a_chunk_review_lands_through_subagent_stop(self, tmp_path):
        repo = _repo(tmp_path)
        _begin(repo, "chunk", ABOVE)
        review_id = _manifest(repo)["id"]
        _write_as_dispatched_reviewer(repo)
        stopped = _subagent_stop(repo)
        assert stopped.returncode == 0, stopped.stderr
        facts = _review_facts(repo)
        assert facts, "no review fact was appended"
        assert any(review_id in json.dumps(f) for f in facts), "the review fact did not land"
        assert not (repo / MARKER_REL).exists(), "consolidation clears the critic-active marker"

    def test_a_verify_review_records_its_resolutions(self, tmp_path):
        repo = _repo(tmp_path)
        prior_id = _seed_a_blocking_review(repo)
        _begin(repo, "verify-resolutions", ABOVE)
        _write_as_dispatched_reviewer(
            repo, resolutions=[{"review_id": prior_id, "fid": "R-1", "disposition": "fixed"}],
        )
        stopped = _subagent_stop(repo)
        assert stopped.returncode == 0, stopped.stderr
        resolutions = [
            f for f in evidence.read_facts(repo).get("facts") or []
            if f.get("kind") == "resolution"
        ]
        assert any(prior_id in json.dumps(f) and "R-1" in json.dumps(f) for f in resolutions), resolutions

    def test_while_the_reviewer_works_the_wait_names_a_dispatched_reviewer(self, tmp_path):
        """A handed-off single-pass review is in the background, like a roster
        review: the wait message must not tell the reader the fork consolidates
        it, or a builder reads a returned fork as an abandoned review."""
        repo = _repo(tmp_path)
        _begin(repo, "chunk", ABOVE)
        waiting = _hook(repo, "critic-consolidate")
        assert waiting.returncode == 0, waiting.stderr
        assert "waiting on reviewer" in waiting.stdout
        assert "dispatching fork itself" not in waiting.stdout
        assert "SubagentStop" in waiting.stdout

    def test_an_inline_review_still_says_the_fork_consolidates(self, tmp_path):
        repo = _repo(tmp_path)
        _begin(repo, "chunk", AT_CEILING)
        waiting = _hook(repo, "critic-consolidate")
        assert "dispatching fork itself" in waiting.stdout


class TestTheReviewerContractReadsForAHandedOffReviewer:
    """Read `agents/critic-reviewer.md` as the reviewer a capped single-pass
    review dispatches: role `reviewer`, on a `chunk` or `verify-resolutions`."""

    AGENT = ROOT / "agents" / "critic-reviewer.md"
    GOALS_1_3 = ROOT / "skills" / "critic" / "goals-1-3.md"

    def _body(self) -> str:
        return self.AGENT.read_text(encoding="utf-8").split("---", 2)[2]

    def test_it_knows_the_reviewer_role_and_its_protocol_file(self):
        body = self._body()
        role_line = next(
            (ln for ln in body.splitlines() if ln.lstrip().startswith("- **reviewer**")), None
        )
        assert role_line is not None, "the role list has no `reviewer` entry"
        block = body[body.index(role_line):].split("\n\n", 1)[0]
        assert "goals-1-3.md" in block and "`chunk`" in block and "`verify-resolutions`" in block
        assert "review-protocol.md" in block

    def test_it_names_its_two_write_paths(self):
        body = self._body()
        assert "rendezvous.<your role>.started" in body
        assert "rendezvous.<your role>.partial" in body

    def test_it_reads_the_directives_from_the_manifest(self):
        body = self._body()
        assert "`dispatch_directives`" in body

    def test_resolutions_are_allowed_only_on_a_verify_dispatch(self):
        body = self._body()
        assert "you exist only for a coordinator roster" not in body
        assert "which is always single-pass. Emitting one" not in body
        sentence = next(s for s in re.split(r"(?<=\.)\s+", body) if "`resolutions`" in s and "only" in s)
        assert "verify-resolutions" in sentence

    def test_its_tools_cover_every_command_the_single_pass_protocol_names(self):
        """Every `prawduct-hook` command `goals-1-3.md` tells its reader to run is
        granted to the dispatched reviewer, except `critic-consolidate`, which
        only the fork runs and which both files must say a dispatched reviewer
        does not."""
        tools = self.AGENT.read_text(encoding="utf-8").split("---", 2)[1]
        named = set(re.findall(r"prawduct-hook ([a-z-]+)", self.GOALS_1_3.read_text(encoding="utf-8")))
        assert {"test-status", "verify-coverage"} <= named, f"control: the scan found {named}"
        for command in sorted(named - {"critic-consolidate"}):
            assert f"Bash(prawduct-hook {command}" in tools, f"`{command}` is not granted"
        assert "Bash(prawduct-hook critic-consolidate" not in tools
        record = self.GOALS_1_3.read_text(encoding="utf-8").split("## Record your judgment", 1)[1]
        assert "as the fork, run" in " ".join(record.split()), (
            "goals-1-3.md tells every reader to consolidate; a dispatched reviewer must not"
        )
