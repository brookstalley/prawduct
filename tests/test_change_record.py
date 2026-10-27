"""Tests for the one owner of "this PR's change record" (#1023, wave 2 of #1012).

A trunk PR cuts its own fragment into the archive before review (PR Step 1d),
so the fragment is in neither its diff nor the merged tree. Every reader that
later asks for the branch's record (Step 1c, the reviewer payload, the
merge-time close) goes through `change_fragments.branch_change_record` or
`scope_change_record`, and these tests walk that path end to end on a real
trunk repo, as the release operator and the PR flow would.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import change_fragments, pr_payload  # noqa: E402

HOOK = _PLUGIN / "bin" / "prawduct-hook"
ARCHIVE = ".prawduct/change-log-archive"


def _env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLAUDE_PROJECT_DIR": str(repo),
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), capture_output=True, text=True, env=_env(repo), check=True, timeout=15,
    ).stdout


def _hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(repo), timeout=60,
    )


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fragment(scope: str, closes: str = "") -> str:
    extra = f"closes: [{closes}]\n" if closes else ""
    return (
        f"---\nschema: 1\ntype: fix\nscope: {scope}\ndate: 2026-10-20\ntitle: {scope} work\n{extra}---\n"
        f"What {scope} changed.\n\n## Consumer note\nnone: test fixture\n"
    )


SHIPPED = "## 2026-09-01: old work\n\n<!-- prawduct: type=fix | scope=old | release=v0.9.0 -->\n\nOld body.\n"


def _trunk(tmp_path: Path) -> Path:
    """A trunk repo recording fragments, with one shipped entry in its live log."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "app.py", "print(1)\n")
    _write(repo, ".prawduct/changes/.gitkeep", "")
    _write(repo, ".prawduct/change-log.md", "# Change Log\n\n" + SHIPPED)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "feature/x")
    return repo


def _branch_with_fragment(tmp_path: Path) -> Path:
    repo = _trunk(tmp_path)
    _write(repo, "app.py", "print(2)\n")
    _write(repo, ".prawduct/changes/x.md", _fragment("x", "owner/repo#7"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work")
    return repo


def _cut_own_fragment(repo: Path) -> None:
    cut = _hook(repo, "cut-change-log", "--release", "v1.0.0", "--scope", "x", "--apply")
    assert cut.returncode == 0, cut.stderr
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "Step 1d: cut x")


class TestTheTrunkWalk:
    def test_step_1c_the_payload_and_the_close_all_find_a_cut_record(self, tmp_path):
        repo = _branch_with_fragment(tmp_path)
        before = _hook(repo, "check-change-log-entry")
        assert before.returncode == 0 and before.stdout.startswith("fragment-present:"), before.stderr

        _cut_own_fragment(repo)
        assert not (repo / ".prawduct/changes/x.md").exists()

        after = _hook(repo, "check-change-log-entry")
        assert after.returncode == 0, after.stderr
        assert after.stdout.startswith("fragment-cut: x cut into the change-log archive")

        record = change_fragments.branch_change_record(repo, "main")
        assert record.error is None
        assert [(c.scope, c.source) for c in record.changes] == [("x", "archive")]
        assert [c.closes for c in record.changes] == [("owner/repo#7",)]

        section = pr_payload._fragment_section(repo, "x", "main")
        assert section is not None and section.ok
        assert f"archive entry in {ARCHIVE}/2026-10.md" in section.body
        assert "scope=x" in section.body and "release=v1.0.0" in section.body

        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature/x")
        close = _hook(repo, "change-record", "x", "--json")
        assert close.returncode == 0, close.stderr
        assert json.loads(close.stdout)["x"] == {
            "source": "archive", "path": f"{ARCHIVE}/2026-10.md", "closes": ["owner/repo#7"],
        }

    def test_a_pending_fragment_is_its_own_record_before_the_cut(self, tmp_path):
        repo = _branch_with_fragment(tmp_path)
        record = change_fragments.branch_change_record(repo, "main")
        assert [(c.scope, c.source, c.path) for c in record.changes] == [("x", "fragment", ".prawduct/changes/x.md")]
        close = _hook(repo, "change-record", "x")
        assert close.returncode == 0 and "x: fragment .prawduct/changes/x.md; closes: owner/repo#7" in close.stdout


class TestWhatIsNotTheBranchsRecord:
    def test_entries_the_size_archive_moved_out_of_the_live_log_are_history(self, tmp_path):
        # The size archive moves shipped entries verbatim; a branch doing that
        # added no record of its own and must still be told to write one.
        repo = _trunk(tmp_path)
        _write(repo, "app.py", "print(2)\n")
        _write(repo, f"{ARCHIVE}/2026-09.md", "# Archive\n\n" + SHIPPED)
        _write(repo, ".prawduct/change-log.md", "# Change Log\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "archive move")
        assert change_fragments.branch_change_record(repo, "main").changes == ()
        probe = _hook(repo, "check-change-log-entry")
        # Refused (the legacy branch names the edited log); never `fragment-cut`.
        assert probe.returncode == 1 and "fragment-cut" not in probe.stdout + probe.stderr

    def test_a_branch_with_no_record_at_all_is_no_entry(self, tmp_path):
        repo = _trunk(tmp_path)
        _write(repo, "app.py", "print(2)\n")
        _git(repo, "commit", "-qam", "code only")
        probe = _hook(repo, "check-change-log-entry")
        assert probe.returncode == 1 and "no-entry:" in probe.stderr

    def test_an_unknown_scope_has_no_record_and_exits_1(self, tmp_path):
        repo = _trunk(tmp_path)
        result = _hook(repo, "change-record", "nope")
        assert result.returncode == 1 and "nope: no record" in result.stdout

    def test_change_record_without_a_scope_is_a_usage_error(self, tmp_path):
        assert _hook(_trunk(tmp_path), "change-record").returncode == 2

    def test_an_unreadable_base_is_an_error_not_an_empty_record(self, tmp_path):
        record = change_fragments.branch_change_record(_trunk(tmp_path), "no-such-base")
        assert record.error is not None and record.changes == ()


AUGUST = "## 2026-08-20: august work\n\n<!-- prawduct: type=fix | scope=aug | release=v0.8.0 -->\n\nAug body.\n"


class TestStepOneDAsPrescribed:
    def test_a_cut_followed_by_a_size_archive_move_still_reads_as_the_cut(self, tmp_path):
        # Step 1d runs the cut, then `archive-change-log --apply`, which edits the
        # live log when its shipped history is over the threshold.
        repo = _branch_with_fragment(tmp_path)
        _cut_own_fragment(repo)
        _write(repo, ".prawduct/change-log.md", "# Change Log\n")
        _write(repo, f"{ARCHIVE}/2026-09.md", "# Archive\n\n" + SHIPPED)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "Step 1d: size archive")
        probe = _hook(repo, "check-change-log-entry")
        assert probe.returncode == 0, probe.stderr
        assert probe.stdout.startswith("fragment-cut: x ")


class TestMovedHistoryAcrossFiles:
    def test_a_move_spanning_months_and_an_existing_bucket_is_not_a_record(self, tmp_path):
        # The writer ends a middle block with a blank line and the last with none,
        # so a moved entry's text changes with its position; identity must not.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _write(repo, "app.py", "print(1)\n")
        _write(repo, ".prawduct/changes/.gitkeep", "")
        _write(repo, ".prawduct/change-log.md", "# Change Log\n\n" + SHIPPED + "\n" + AUGUST)
        _write(repo, f"{ARCHIVE}/2026-08.md", "# Archive\n\n" + AUGUST.replace("aug", "aug0").replace("08-20", "08-01"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "base")
        _git(repo, "checkout", "-qb", "feature/x")
        _write(repo, "app.py", "print(2)\n")
        _write(repo, ".prawduct/change-log.md", "# Change Log\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "code")
        moved = _hook(repo, "archive-change-log", "--apply")
        assert moved.returncode == 0, moved.stderr
        # Re-create the move by hand if the threshold left everything live.
        _write(repo, f"{ARCHIVE}/2026-09.md", "# Archive\n\n" + SHIPPED)
        bucket = (repo / ARCHIVE / "2026-08.md").read_text()
        if "scope=aug |" not in bucket:
            _write(repo, f"{ARCHIVE}/2026-08.md", bucket.rstrip("\n") + "\n\n" + AUGUST)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "move")
        assert change_fragments.branch_change_record(repo, "main").changes == ()
        probe = _hook(repo, "check-change-log-entry")
        assert probe.returncode == 1 and "fragment-cut" not in probe.stdout


class TestAGitFailureIsNotAMissingRecord:
    def test_step_1c_says_git_failed(self, tmp_path, monkeypatch, capsys):
        from lib import coverage

        repo = _trunk(tmp_path)
        _write(repo, "app.py", "print(2)\n")
        _git(repo, "commit", "-qam", "code only")
        monkeypatch.setattr(
            change_fragments, "branch_change_record",
            lambda *_a, **_k: change_fragments.BranchRecord(error="git diff exited 128"),
        )
        verdict = coverage._fragment_entry_verdict(repo, "main", ["app.py"], ["app.py"])
        err = capsys.readouterr().err
        assert verdict == 1
        assert err.startswith("git-failed: git diff exited 128") and "no-entry" not in err

    def test_the_payload_degrades_rather_than_falling_back(self, tmp_path, monkeypatch):
        repo = _trunk(tmp_path)
        monkeypatch.setattr(
            change_fragments, "branch_change_record",
            lambda *_a, **_k: change_fragments.BranchRecord(error="git diff exited 128"),
        )
        section = pr_payload._fragment_section(repo, "x", "main")
        assert section is not None and not section.ok
        assert "could not be read" in section.degraded


class TestAnUnreadableArchiveBucket:
    def test_change_record_names_the_bucket_it_could_not_search(self, tmp_path):
        repo = _trunk(tmp_path)
        (repo / ARCHIVE).mkdir(parents=True)
        (repo / ARCHIVE / "2026-08.md").write_bytes(b"# Archive\n\n\xff\xfe not utf-8\n")
        _write(repo, f"{ARCHIVE}/2026-09.md", "# Archive\n\n" + SHIPPED)
        found = _hook(repo, "change-record", "old")
        assert found.returncode == 0 and "old: archive" in found.stdout  # the readable bucket is still searched
        assert "NOTE: could not read 2026-08.md" in found.stderr
        missing = _hook(repo, "change-record", "nope")
        assert missing.returncode == 1 and "NOTE: could not read 2026-08.md" in missing.stderr
