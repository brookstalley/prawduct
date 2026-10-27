"""``actor.build`` — which plugin build recorded a fact (#1086).

Every dev build of one version shares ``actor.plugin``, so the envelope also
records the plugin checkout's commit: 12 hex characters, ``+dirty`` when the
plugin tree has changes, and OMITTED (never null) when the plugin root is not a
git checkout or git fails. Real git repos stand in for the plugin root; the
plugin root of the running process is never the subject, so these pass on a
runner that ships the tree without its history.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import evidence  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _checkout(base: Path) -> Path:
    """A repo shaped like prawduct's: the plugin tree is a subdirectory."""
    repo = base / "checkout"
    plugin = repo / "plugin"
    plugin.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("__pycache__/\n")
    (plugin / "VERSION").write_text("3.8.0-dev\n")
    (plugin / "code.py").write_text("x = 1\n")
    (repo / "README").write_text("outside the plugin tree\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return plugin


def _head(plugin: Path) -> str:
    return _git(plugin, "rev-parse", "HEAD")


class TestReadPluginBuild:
    def test_a_clean_checkout_is_its_sha(self, tmp_path):
        plugin = _checkout(tmp_path)
        build = evidence.read_plugin_build(plugin)
        assert build == _head(plugin)[:12]
        assert len(build) == evidence.BUILD_SHA_LENGTH == 12

    def test_a_modified_tracked_file_marks_it_dirty(self, tmp_path):
        plugin = _checkout(tmp_path)
        (plugin / "code.py").write_text("x = 2\n")
        assert evidence.read_plugin_build(plugin) == _head(plugin)[:12] + "+dirty"

    def test_an_untracked_file_marks_it_dirty(self, tmp_path):
        """New code in the tree runs as much as edited code does."""
        plugin = _checkout(tmp_path)
        (plugin / "new.py").write_text("y = 1\n")
        assert evidence.read_plugin_build(plugin).endswith("+dirty")

    def test_an_ignored_file_does_not(self, tmp_path):
        """Bytecode caches appear under every plugin tree that has run."""
        plugin = _checkout(tmp_path)
        (plugin / "__pycache__").mkdir()
        (plugin / "__pycache__" / "code.cpython-312.pyc").write_bytes(b"\0")
        assert evidence.read_plugin_build(plugin) == _head(plugin)[:12]

    def test_a_change_outside_the_plugin_tree_does_not(self, tmp_path):
        """The dirty check is scoped to the code that ran; a dirty sibling in
        the same checkout did not change it."""
        plugin = _checkout(tmp_path)
        (plugin.parent / "README").write_text("edited\n")
        (plugin.parent / "scratch.txt").write_text("untracked\n")
        assert evidence.read_plugin_build(plugin) == _head(plugin)[:12]

    def test_a_non_git_root_has_no_build(self, tmp_path):
        plugin = tmp_path / "marketplace-copy"
        plugin.mkdir()
        (plugin / "VERSION").write_text("3.8.0\n")
        assert evidence.read_plugin_build(plugin) is None

    def test_a_root_inside_an_unrelated_repo_has_no_build(self, tmp_path):
        """A copy under a version-controlled home directory must not borrow
        the enclosing repo's sha: its VERSION is not tracked there."""
        home = tmp_path / "home"
        home.mkdir()
        _git(home, "init", "-q")
        (home / "dotfile").write_text("x\n")
        _git(home, "add", "-A")
        _git(home, "commit", "-q", "-m", "dotfiles")
        plugin = home / ".claude" / "plugins" / "cache" / "prawduct"
        plugin.mkdir(parents=True)
        (plugin / "VERSION").write_text("3.8.0\n")
        assert evidence.read_plugin_build(plugin) is None

    def test_a_checkout_with_no_commit_has_no_build(self, tmp_path):
        plugin = tmp_path / "fresh"
        plugin.mkdir()
        _git(plugin, "init", "-q")
        (plugin / "VERSION").write_text("3.8.0\n")
        _git(plugin, "add", "VERSION")
        assert evidence.read_plugin_build(plugin) is None

    def test_a_git_failure_has_no_build_and_does_not_raise(self, tmp_path, monkeypatch):
        """A malformed timeout makes every git call fail — the real failure
        path through the shared runner, not a stub of it."""
        plugin = _checkout(tmp_path)
        monkeypatch.setenv("PRAWDUCT_GIT_TIMEOUT", "not-a-number")
        assert evidence.read_plugin_build(plugin) is None

    def test_a_failure_of_the_status_call_alone_has_no_build(self, tmp_path, monkeypatch):
        """The sha and dirtiness come from one call; if it fails nothing is
        recorded rather than a sha whose dirtiness is unknown."""
        plugin = _checkout(tmp_path)
        real = evidence.run_git

        def failing_status(cwd, *args, **kw):
            if args and args[0] == "status":
                return 1, "", "boom"
            return real(cwd, *args, **kw)

        monkeypatch.setattr(evidence, "run_git", failing_status)
        assert evidence.read_plugin_build(plugin) is None

    def test_an_exported_git_dir_for_another_repo_is_ignored(self, tmp_path, monkeypatch):
        """A hook run under a product's git hook inherits GIT_DIR for the
        PRODUCT; the stamp must still describe the plugin checkout."""
        plugin = _checkout(tmp_path)
        other = tmp_path / "product"
        other.mkdir()
        _git(other, "init", "-q")
        (other / "f").write_text("x\n")
        _git(other, "add", "-A")
        _git(other, "commit", "-q", "-m", "product")
        expected = _head(plugin)[:12]  # read before the variables are exported
        assert expected != _head(other)[:12]
        monkeypatch.setenv("GIT_DIR", str(other / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(other))
        assert evidence.read_plugin_build(plugin) == expected


@pytest.fixture
def product(tmp_path):
    repo = tmp_path / "product"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


@pytest.fixture
def fresh_memo(monkeypatch):
    monkeypatch.setattr(evidence, "_build_memo", evidence._UNREAD)


def _stored_actor(repo: Path) -> dict:
    (line,) = evidence.store_path(repo).read_text().splitlines()
    return json.loads(line)["actor"]


class TestTheEnvelopeCarriesIt:
    def test_a_fact_records_the_plugin_build(self, product, tmp_path, monkeypatch, fresh_memo):
        plugin = _checkout(tmp_path)
        monkeypatch.setattr(evidence, "_plugin_root", lambda: plugin)
        evidence.append_fact(product, "review", "r-1", {})
        actor = _stored_actor(product)
        assert actor["build"] == _head(plugin)[:12]
        assert actor["branch"] == "main"  # beside the fields it joins

    def test_an_unreadable_build_is_omitted_never_null(self, product, tmp_path, monkeypatch, fresh_memo):
        plugin = tmp_path / "not-a-checkout"
        plugin.mkdir()
        monkeypatch.setattr(evidence, "_plugin_root", lambda: plugin)
        evidence.append_fact(product, "review", "r-1", {})
        actor = _stored_actor(product)
        assert "build" not in actor
        assert actor["worktree"] == str(product)  # the fact itself was written

    def test_it_is_read_once_per_process(self, product, monkeypatch, fresh_memo):
        calls = []

        def counted(root):
            calls.append(root)
            return "abcdef012345"

        monkeypatch.setattr(evidence, "read_plugin_build", counted)
        evidence.append_fact(product, "review", "r-1", {})
        evidence.append_fact(product, "review", "r-2", {})
        assert len(calls) == 1
        facts = evidence.read_facts(product)["facts"]
        assert [f["actor"]["build"] for f in facts] == ["abcdef012345"] * 2

    def test_an_omitted_build_is_also_remembered(self, product, monkeypatch, fresh_memo):
        """``None`` is an answer, not a miss: a marketplace install must not
        re-run git on every append."""
        calls = []
        monkeypatch.setattr(evidence, "read_plugin_build", lambda root: calls.append(root))
        evidence.append_fact(product, "review", "r-1", {})
        evidence.append_fact(product, "review", "r-2", {})
        assert len(calls) == 1
