"""Tests for the post-release verification gate (``lib/release_verification``).

Structure ported from ``test_release_readiness.py`` — the precedent this
subcommand is modelled on — before adding cases of its own.

Two deliberate choices, each answering "what change would turn this red?":

* The tree-reading checks run against a **real git repository** built in
  ``tmp_path``, not a fixture standing in for one. ``check_version_files`` reads
  through ``git show <tag>:<path>``, so a fixture would exercise the parser and
  never the thing that can actually be wrong — which tree got read. Point these
  at the working tree instead of the tag and the mismatch tests go green while
  the gate reports on the wrong commit.
* The network check is exercised through a substituted ``_run``, so no test
  reaches GitHub. Collapse ``UNVERIFIABLE`` into ``FAILED`` and
  ``test_missing_gh_is_unverifiable_not_failed`` goes red — which is the whole
  point of that state existing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import release_verification as rv  # noqa: E402

HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path: Path, *, version: str = "3.2.0", tag: str | None = None) -> Path:
    """A real repo whose tagged tree carries ``version`` in all three files."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _write(repo / "plugin" / "VERSION", version + "\n")
    _write(
        repo / "plugin" / ".claude-plugin" / "plugin.json",
        json.dumps({"name": "prawduct", "version": version}) + "\n",
    )
    _write(repo / "pyproject.toml", f'[project]\nname = "x"\nversion = "{version}"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "release")
    _git(repo, "tag", tag or f"v{version}")
    # `origin/main` is what the gate compares against; a local clone has none,
    # so point a ref at the same commit under the name the gate reads.
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


class TestVersionParsing:
    @pytest.mark.parametrize(
        ("kind", "content", "expected"),
        [
            ("bare", "3.2.0\n", "3.2.0"),
            ("bare", "  3.2.0  ", "3.2.0"),
            ("bare", "", None),
            ("json", '{"version": "3.2.0"}', "3.2.0"),
            ("json", '{"name": "x"}', None),
            ("json", "not json at all", None),
            ("toml", 'version = "3.2.0"\n', "3.2.0"),
            ("toml", "version = '3.2.0'\n", "3.2.0"),
            ("toml", "[project]\nname = 'x'\n", None),
        ],
    )
    def test_extracts_or_reports_absent(self, kind, content, expected):
        assert rv._version_from(kind, content) == expected

    def test_toml_takes_the_first_assignment(self):
        """`[project].version` sits above any `[tool.*]` table that repeats it."""
        content = '[project]\nversion = "3.2.0"\n\n[tool.other]\nversion = "9.9.9"\n'
        assert rv._version_from("toml", content) == "3.2.0"

    @pytest.mark.parametrize("key", ["versioning", "version_scheme", "versions"])
    def test_toml_key_must_be_version_not_merely_start_with_it(self, key):
        """A prefix match reads a neighbouring key as the release version.

        Red before the key comparison replaced `startswith`: each of these
        returned its own value, so a `pyproject.toml` growing a `versioning`
        key would have made the gate report a confident wrong number.
        """
        assert rv._version_from("toml", f'{key} = "scheme-x"\n') is None

    def test_toml_finds_version_after_an_unrelated_prefix_key(self):
        content = '[tool.x]\nversioning = "calver"\n\n[project]\nversion = "3.2.0"\n'
        assert rv._version_from("toml", content) == "3.2.0"


class TestVersionFiles:
    def test_agreeing_tree_has_no_problems(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        assert rv.check_version_files(repo, "v3.2.0") == []

    def test_disagreeing_file_is_named_with_both_values(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0", tag="v3.2.1")
        problems = dict(rv.check_version_files(repo, "v3.2.1"))
        assert set(problems) == {
            "plugin/VERSION",
            "plugin/.claude-plugin/plugin.json",
            "pyproject.toml",
        }
        assert "says 3.2.0" in problems["plugin/VERSION"]
        assert "tag says 3.2.1" in problems["plugin/VERSION"]

    def test_reads_the_tag_tree_not_the_working_tree(self, tmp_path):
        """The regression this gate exists to prevent, in one test.

        The tag's tree says 3.2.0; the working tree is then moved to 9.9.9 and
        left dirty. A gate reading the checkout would report 9.9.9 and, on a
        later branch, confidently grade a release that never shipped.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _write(repo / "plugin" / "VERSION", "9.9.9\n")
        assert rv.check_version_files(repo, "v3.2.0") == []

    def test_missing_file_in_tree_fails_closed(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "rm", "-q", "pyproject.toml")
        _git(repo, "commit", "-qm", "drop")
        _git(repo, "tag", "v3.2.2")
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        problems = dict(rv.check_version_files(repo, "v3.2.2"))
        assert "not present" in problems["pyproject.toml"]


class TestTagOnMain:
    def test_tag_on_main_is_ok(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, _ = rv.check_tag_on_main(repo, "v3.2.0")
        assert state == rv.OK

    def test_unresolvable_tag_fails(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_tag_on_main(repo, "v9.9.9")
        assert state == rv.FAILED
        assert "does not resolve" in detail

    def test_absent_origin_main_is_unverifiable_not_failed(self, tmp_path):
        """A clone that cannot answer must not answer "broken".

        Red before the ref-existence check: a repo with no `origin/main` — a
        fresh checkout, a fork, a shallow CI fetch — reported
        `not contained in origin/main`, which reads as a broken release.
        """
        repo = tmp_path / "noremote"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "x")
        _git(repo, "tag", "v1.0.0")
        state, detail = rv.check_tag_on_main(repo, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "origin/main is not present" in detail

    def test_tag_off_main_fails(self, tmp_path):
        """A tag on a side branch is not a release, however real the tag is."""
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "checkout", "-q", "-b", "side")
        _write(repo / "extra.txt", "x\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "side work")
        _git(repo, "tag", "v3.2.9")
        state, detail = rv.check_tag_on_main(repo, "v3.2.9")
        assert state == rv.FAILED
        assert "not contained in origin/main" in detail


class TestGithubRelease:
    def test_release_present_is_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (0, "https://example/tag/v1", ""))
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.OK
        assert detail == "https://example/tag/v1"

    def test_absent_release_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (1, "", "release not found"))
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.FAILED
        assert "the tag alone is not a release" in detail

    def test_missing_gh_is_unverifiable_not_failed(self, tmp_path, monkeypatch):
        """A machine without `gh` must not be told its release is broken."""
        monkeypatch.setattr(rv, "_run", lambda *a, **k: None)
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE
        assert "not installed" in detail

    def test_other_gh_error_is_unverifiable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (1, "", "HTTP 503 upstream"))
        state, _ = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE


class TestCheckReleased:
    def _stub_gh(self, monkeypatch, result):
        real = rv._run

        def fake(args, cwd):
            if args and args[0] == "gh":
                return result
            return real(args, cwd)

        monkeypatch.setattr(rv, "_run", fake)

    def test_complete_release_exits_zero(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        assert rv.check_released(repo, "v3.2.0") == 0
        out = capsys.readouterr().out
        assert "released: v3.2.0" in out
        assert "3 of 3 checks verified" in out

    def test_accepts_bare_version(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        assert rv.check_released(repo, "3.2.0") == 0

    def test_missing_github_release_exits_one(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "release not found"))
        assert rv.check_released(repo, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "not-released: v3.2.0" in err
        assert "github-release" in err

    def test_unverifiable_alone_does_not_fail(self, tmp_path, monkeypatch, capsys):
        """`gh` absent, everything else good: exit 0, and say what went unchecked."""
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, None)
        assert rv.check_released(repo, "v3.2.0") == 0
        captured = capsys.readouterr()
        assert "2 of 3 checks verified" in captured.out
        assert "unverified: github-release" in captured.err

    def test_json_output_carries_every_check(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "release not found"))
        assert rv.check_released(repo, "v3.2.0", json_output=True) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["release"] == "v3.2.0"
        assert payload["verdict"] == "not-released"
        assert {c["check"] for c in payload["checks"]} == {
            "version-files",
            "tag-on-main",
            "github-release",
        }


class TestCli:
    """The wrapper's own contract. Exercised through the real hook, because the
    argument scan and the exit-code mapping live there and nowhere else.

    **Pointed at an isolated project dir on purpose.** ``main()`` resolves
    ``get_project_dir()`` and runs the binary-skew check *before* dispatch, so a
    bare ``subprocess.run`` with no ``cwd`` aims the real hook at this working
    repository — reading, and potentially writing, live ``.prawduct/`` state from
    inside the test suite. Tests are independent or they are not tests.
    """

    def _run(self, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
        project = tmp_path / "isolated"
        project.mkdir(exist_ok=True)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
        return subprocess.run(
            [sys.executable, str(HOOK), "check-released", *args],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(project),
            env=env,
        )

    def test_no_version_is_usage_error(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 2
        assert "a version argument is required" in result.stderr

    def test_unknown_flag_is_usage_error_not_ignored(self, tmp_path):
        result = self._run(tmp_path, "v1.0.0", "--bogus")
        assert result.returncode == 2
        assert "unknown argument: --bogus" in result.stderr

    def test_second_version_is_usage_error(self, tmp_path):
        result = self._run(tmp_path, "v1.0.0", "v2.0.0")
        assert result.returncode == 2
        assert "unexpected second version" in result.stderr
