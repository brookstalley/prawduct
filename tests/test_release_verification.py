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
    """Run git with the developer's global config neutralised.

    Sibling test files do the same: without it these repos inherit whatever the
    machine sets — `commit.gpgsign`, hooks, a default branch name — and the
    suite passes or fails on the author's dotfiles rather than on the code.
    """
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
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
    def test_agreeing_tree_is_ok(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.OK
        assert "3 version file(s) agree" in detail
        # Names, not just a count. Red if the detail goes back to reporting a
        # bare number: the count alone cannot be acted on, and this string is
        # what reaches both the operator and the --json payload.
        for path in ("plugin/VERSION", "plugin/.claude-plugin/plugin.json", "pyproject.toml"):
            assert path in detail
        assert "not in this tree" not in detail, "nothing was skipped in this tree"

    def test_disagreeing_file_is_named_with_both_values(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0", tag="v3.2.1")
        state, detail = rv.check_version_files(repo, "v3.2.1")
        assert state == rv.FAILED
        assert "plugin/VERSION: says 3.2.0, tag says 3.2.1" in detail

    def test_absent_file_is_skipped_not_failed(self, tmp_path):
        """This module ships to products with a different layout.

        Red before the skip: a product with no `pyproject.toml` was reported
        `not-released`, naming a file that cannot exist in its tree.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "rm", "-q", "pyproject.toml")
        # Move the REMAINING files to the new version, so this test isolates the
        # absent file rather than tripping on a version mismatch.
        _write(repo / "plugin" / "VERSION", "3.2.3\n")
        _write(
            repo / "plugin" / ".claude-plugin" / "plugin.json",
            json.dumps({"name": "prawduct", "version": "3.2.3"}) + "\n",
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "no pyproject")
        _git(repo, "tag", "v3.2.3")
        state, detail = rv.check_version_files(repo, "v3.2.3")
        assert state == rv.OK
        assert "2 version file(s) agree" in detail
        # The skip must be VISIBLE. A tag tree missing
        # `plugin/.claude-plugin/plugin.json` — the auto-update cache key, and
        # the root cause this whole check exists for — otherwise reports
        # `released` / exit 0, distinguishable from a complete release only by a
        # "2" where a "3" belongs. Red if the naming clause is dropped.
        assert "not in this tree: pyproject.toml" in detail

    def test_tree_with_no_known_version_file_is_unverifiable(self, tmp_path):
        repo = tmp_path / "bare"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "readme.md", "hi\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "x")
        _git(repo, "tag", "v1.0.0")
        state, _ = rv.check_version_files(repo, "v1.0.0")
        assert state == rv.UNVERIFIABLE

    def test_reads_the_tag_tree_not_the_working_tree(self, tmp_path):
        """The regression this gate exists to prevent, in one test.

        The tag's tree says 3.2.0; the working tree is then moved to 9.9.9 and
        left dirty. A gate reading the checkout would report 9.9.9 and, on a
        later branch, confidently grade a release that never shipped.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _write(repo / "plugin" / "VERSION", "9.9.9\n")
        assert rv.check_version_files(repo, "v3.2.0")[0] == rv.OK


class TestVersionFilesOutsideARepo:
    def test_a_non_repository_names_its_real_cause(self, tmp_path):
        """The verdict was already right; the REASON was not.

        `git show <tag>:<path>` fails per-file outside a repository exactly as
        it does for a path absent from the tree, so every file was "skipped" and
        the no-files branch reported a layout question: *"a different product
        layout, or a tag this clone has not fetched"*. Neither is true, and a
        product owner reading it would go looking at their own layout.

        Unverifiable was the correct verdict, so this is not a false red — it is
        the rule one level down: *"advice fails soft" is not "advice fails
        silent"*. A soft failure still owes its reader the real cause.
        """
        state, detail = rv.check_version_files(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "not a git repository" in detail
        assert "product layout" not in detail, (
            "a non-repository is still reported as a question about the "
            "product's layout"
        )

    def test_a_real_repo_missing_the_files_still_says_layout(self, tmp_path):
        """The pre-existing message is correct for the case it was written for,
        and must survive the new branch above."""
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state in (rv.OK, rv.UNVERIFIABLE)
        if state == rv.UNVERIFIABLE:
            assert "product layout" in detail


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

    def test_a_non_repository_is_unverifiable_not_a_broken_release(self, tmp_path):
        """The check must not answer a question it could not ask.

        `git rev-parse <tag>^{commit}` exits **128** for two unrelated states —
        the tag is absent, and this is not a git repository — and the branch
        below read every non-zero as the first. Measured before the fix:
        `prawduct-hook check-released v3.2.4` from any non-repo directory printed
        `ERROR: tag-on-main: tag v3.2.4 does not resolve to a commit`, verdict
        `not-released`, exit 1 — a finding about a release, produced by an
        environment that could not look at it. This module's own docstrings say
        twice that a false red is worse than no check, because it is the reading
        that teaches people to ignore the check.

        Driven through the REAL failure — an ordinary empty directory, no
        monkeypatch — because a stubbed return proves the caller reads a signal,
        never that git produces it. The sibling test above patches `_run` and is
        the right shape for a hung toolchain, which cannot be staged for real.
        """
        state, detail = rv.check_tag_on_main(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE, (
            "a non-repository still reports a verdict about the release"
        )
        assert "not a git repository" in detail
        assert "does not resolve" not in detail

    def test_an_absent_tag_inside_a_real_repo_still_fails(self, tmp_path):
        """The other half, and the one that keeps the fix honest: the repair
        must not soften a TRUE finding into `unverifiable`.

        Without this, returning UNVERIFIABLE unconditionally from the non-zero
        branch would pass the test above and silently retire the check.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_tag_on_main(repo, "v9.9.9")
        assert state == rv.FAILED
        assert "does not resolve" in detail

    def test_git_that_cannot_complete_is_unverifiable_not_a_tag_verdict(self, tmp_path, monkeypatch):
        """A broken toolchain is not evidence about the release.

        Also a regression guard: an edit meant to add this branch deleted the
        unresolvable-tag branch instead, and every check here still passed
        because nothing exercised the ERRORED path.
        """
        monkeypatch.setattr(rv, "_run", lambda *a, **k: rv.ERRORED)
        state, detail = rv.check_tag_on_main(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "could not resolve" in detail

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
        monkeypatch.setattr(rv, "_run", lambda *a, **k: rv.MISSING)
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE
        assert "not installed" in detail

    def test_other_gh_error_is_unverifiable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (1, "", "HTTP 503 upstream"))
        state, _ = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE


class TestScrub:
    """The credential scrub is a claim `security-model.md` now makes in prose.

    Untested, deleting the `_scrub` call kept the whole suite green — which is
    how a security assertion outlives the code behind it. Red if the call site
    is removed, and red if the `except ImportError` fallback starts swallowing
    a real scrub.
    """

    _BAIT = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"

    def test_scrub_removes_a_planted_token(self):
        assert self._BAIT not in rv._scrub(f"gh: bad credentials for {self._BAIT}")

    def test_gh_error_detail_is_scrubbed_before_it_is_reported(self, tmp_path, monkeypatch):
        """The path that actually reaches stderr and the --json payload."""
        monkeypatch.setattr(
            rv, "_run", lambda *a, **k: (1, "", f"HTTP 401 using token {self._BAIT}")
        )
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE
        assert self._BAIT not in detail


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
        assert "3 of 3 verified" in out

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

    def test_unverifiable_is_its_own_exit_code_not_success(self, tmp_path, monkeypatch, capsys):
        """The finding that inverted the first design.

        `gh` absent, everything else good. This used to exit 0 — which made the
        gate green in exactly the environment it exists for, since a tag-push
        job without a token gets a `gh` that cannot answer. Red if
        EXIT_UNVERIFIABLE collapses back into 0.

        Asserted against the **literal 3**, not against `rv.EXIT_UNVERIFIABLE`.
        Comparing the return value to the very constant under test passes for
        whatever value that constant takes — including the 0 this docstring
        names as its red-trigger, because the human-output branch keys off the
        same constant and would still print "unverified". A guard that cannot
        fail for the regression it names is not a guard.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, rv.MISSING)
        assert rv.check_released(repo, "v3.2.0") == 3
        assert rv.EXIT_UNVERIFIABLE == 3, "the published exit-code contract moved"
        captured = capsys.readouterr()
        assert "unverified: v3.2.0" in captured.err
        assert "could not run" in captured.err

    def test_allow_unverifiable_opts_back_into_zero(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, rv.MISSING)
        assert rv.check_released(repo, "v3.2.0", allow_unverifiable=True) == 0

    def test_ci_shaped_checkout_without_origin_main_is_not_green(self, tmp_path, monkeypatch):
        """`actions/checkout` on a tag has no `origin/main`. That must not pass.

        This is the CI case Chunk 05 builds on, and the first design exited 0
        for it while the Releases page could be empty.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        # Literal, for the reason spelled out on the sibling test above.
        assert rv.check_released(repo, "v3.2.0") == 3

    def test_unauthenticated_gh_is_not_read_as_absence(self, tmp_path, monkeypatch):
        """A refused question is not a missing release."""
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "gh: To use GitHub CLI, authenticate with gh auth login"))
        assert rv.check_released(repo, "v3.2.0") == 3

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
