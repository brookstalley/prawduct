"""Hot-path git-batching regression tests (STH-6Q9D).

The SessionStart/Stop hooks fanned out one git subprocess per session path
(`_untrack_session_files`), re-ran `git status --porcelain` across the
baseline-diff probes, and walked the whole tree (including `node_modules`) in
`_has_product_code`. These tests pin the three optimizations — and, crucially,
that none of them changed observable behavior:

  D1  `_untrack_session_files` learns the tracked set in ONE `git ls-files` and
      untracks in ONE `git rm` (was 15 ls-files + N rm on the hot path).
  D2  the status-family probes accept a pre-captured porcelain snapshot via an
      optional `status_output=` param so a caller spawns git once, not per probe.
  D3  `_has_product_code` prunes `node_modules`/`.git`/`.prawduct` at the
      directory level and short-circuits on the first product-code file.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

import pytest

from lib import gates, gitstate

_ROOT = Path(__file__).resolve().parent.parent / "plugin"


def _load_hook():
    """Load the extensionless hook as a module (its cmd_*/_untrack live behind __main__)."""
    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_hot_path_batching", str(_ROOT / "bin" / "prawduct-hook")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _init_repo(tmp_path: Path, monkeypatch) -> Path:
    """A fresh git repo with HOME outside it (learning: HOME-in-repo leaks pyc /
    global gitconfig into `git ls-files`)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def _count_git_subcommands(hook, monkeypatch) -> list[str]:
    """Patch the hook module's subprocess.run to record each `git <sub>` it runs,
    delegating to the real run. Returns the live list of subcommands."""
    seen: list[str] = []
    real_run = hook.subprocess.run

    def counting_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git" and len(cmd) > 1:
            seen.append(cmd[1])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(hook.subprocess, "run", counting_run)
    return seen


def _tracked(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=repo, capture_output=True, text=True
    ).stdout
    return {line for line in out.splitlines() if line}


# =============================================================================
# D1 — _untrack_session_files batches the fan-out
# =============================================================================


class TestUntrackBatching:
    def test_two_tracked_session_files_use_one_lsfiles_one_rm(self, tmp_path, monkeypatch):
        repo = _init_repo(tmp_path, monkeypatch)
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / ".session-handoff.md").write_text("h")
        (repo / ".prawduct" / ".session-reflected").write_text("r")
        subprocess.run(
            ["git", "add", "-f", ".prawduct/.session-handoff.md", ".prawduct/.session-reflected"],
            cwd=repo, check=True,
        )
        subprocess.run(["git", "commit", "-qm", "oops"], cwd=repo, check=True)

        hook = _load_hook()
        calls = _count_git_subcommands(hook, monkeypatch)
        untracked = hook._untrack_session_files(repo)

        assert set(untracked) == {
            ".prawduct/.session-handoff.md",
            ".prawduct/.session-reflected",
        }
        # Batched: one ls-files for ALL session paths (not one per path), one rm.
        assert calls.count("ls-files") == 1
        assert calls.count("rm") == 1
        # Both are actually untracked now.
        assert _tracked(repo) == set()

    def test_nothing_tracked_skips_the_rm(self, tmp_path, monkeypatch):
        repo = _init_repo(tmp_path, monkeypatch)
        (repo / "app.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "c"], cwd=repo, check=True)

        hook = _load_hook()
        calls = _count_git_subcommands(hook, monkeypatch)
        assert hook._untrack_session_files(repo) == []
        assert calls.count("ls-files") == 1
        assert calls.count("rm") == 0  # no matches → no rm spawned

    def test_leaves_untracked_session_files_and_product_files_alone(self, tmp_path, monkeypatch):
        repo = _init_repo(tmp_path, monkeypatch)
        (repo / ".prawduct").mkdir()
        # present but never tracked → must not be reported
        (repo / ".prawduct" / ".session-start").write_text("s")
        # tracked session file → reported + untracked
        (repo / ".prawduct" / ".session-handoff.md").write_text("h")
        # tracked product file → must stay tracked
        (repo / "app.py").write_text("x = 1\n")
        subprocess.run(
            ["git", "add", "-f", ".prawduct/.session-handoff.md", "app.py"],
            cwd=repo, check=True,
        )
        subprocess.run(["git", "commit", "-qm", "c"], cwd=repo, check=True)

        hook = _load_hook()
        assert hook._untrack_session_files(repo) == [".prawduct/.session-handoff.md"]
        assert _tracked(repo) == {"app.py"}

    def test_tracked_pr_reviews_dir_collapses_to_declared_pathspec(self, tmp_path, monkeypatch):
        # `.prawduct/.pr-reviews` is the one DIRECTORY pathspec in the session set:
        # `git ls-files` expands it to member files, so D1 must collapse those back
        # to the declared pathspec (the trickiest branch of the batch logic) so the
        # report and the rm target stay the canonical session-path set.
        repo = _init_repo(tmp_path, monkeypatch)
        reviews = repo / ".prawduct" / ".pr-reviews"
        reviews.mkdir(parents=True)
        (reviews / "pr-42.json").write_text("{}")
        (reviews / "pr-43.json").write_text("{}")
        subprocess.run(
            ["git", "add", "-f",
             ".prawduct/.pr-reviews/pr-42.json", ".prawduct/.pr-reviews/pr-43.json"],
            cwd=repo, check=True,
        )
        subprocess.run(["git", "commit", "-qm", "oops reviews"], cwd=repo, check=True)

        hook = _load_hook()
        untracked = hook._untrack_session_files(repo)
        # Reported once as the declared directory pathspec — not the member files.
        assert untracked == [".prawduct/.pr-reviews"]
        # Both member files are actually untracked.
        assert _tracked(repo) == set()

    def test_non_repo_returns_empty_without_crashing(self, tmp_path, monkeypatch):
        hook = _load_hook()
        # tmp_path is not a git repo — the rev-parse guard short-circuits.
        assert hook._untrack_session_files(tmp_path / "nope") == []


# =============================================================================
# D2 — status-family probes accept a pre-captured snapshot
# =============================================================================


def _baseline_repo(tmp_path: Path, baseline: str = "") -> Path:
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    (prawduct / ".session-git-baseline").write_text(baseline)
    return tmp_path


def _boom(_):
    raise AssertionError("git_status_output must not be called when status_output is passed")


class TestStatusCaptureOnce:
    def test_passed_output_is_used_without_recomputing(self, tmp_path, monkeypatch):
        project = _baseline_repo(tmp_path)
        monkeypatch.setattr(gitstate, "git_status_output", _boom)
        porcelain = " M src/app.py\n"
        assert gitstate.git_has_session_changes(project, porcelain) != ""
        assert gates.session_changes_all_non_judgeable(project, porcelain) is False
        assert gitstate.git_has_code_changes(project, porcelain) is True
        assert gitstate._get_session_changed_files(project, porcelain) == ["src/app.py"]

    def test_no_baseline_fallback_also_honors_passed_output(self, tmp_path, monkeypatch):
        # No .session-git-baseline → git_has_session_changes falls back to
        # git_has_changes, which must thread the same snapshot (no recompute).
        (tmp_path / ".prawduct").mkdir()
        monkeypatch.setattr(gitstate, "git_status_output", _boom)
        assert gitstate.git_has_session_changes(tmp_path, " M src/app.py\n") != ""

    def test_passed_matches_computed(self, tmp_path, monkeypatch):
        project = _baseline_repo(tmp_path)
        porcelain = " M a.md\n M b.py\n"
        monkeypatch.setattr(gitstate, "git_status_output", lambda _: porcelain)
        computed = gitstate._get_session_changed_files(project)
        doc_only_computed = gates.session_changes_all_non_judgeable(project)
        monkeypatch.setattr(gitstate, "git_status_output", _boom)
        assert gitstate._get_session_changed_files(project, porcelain) == computed
        assert gates.session_changes_all_non_judgeable(project, porcelain) == doc_only_computed

    def test_default_none_still_computes(self, tmp_path, monkeypatch):
        # Backward compat: omitting the param computes via git_status_output.
        project = _baseline_repo(tmp_path)
        monkeypatch.setattr(gitstate, "git_status_output", lambda _: " M src/app.py\n")
        assert gitstate.git_has_session_changes(project) != ""
        assert gitstate._get_session_changed_files(project) == ["src/app.py"]


# =============================================================================
# D3 — _has_product_code prunes the walk
# =============================================================================


class TestHasProductCodePrune:
    def test_node_modules_only_is_not_product_code(self, tmp_path):
        nm = tmp_path / "node_modules" / "left-pad"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = 1\n")
        assert gitstate._has_product_code(tmp_path) is False

    def test_git_internals_are_excluded(self, tmp_path):
        # .git is pruned (STH-6Q9D): a product-suffix file inside .git — which a
        # real repo never has — is not product code. Locks in the deliberate,
        # more-correct verdict the prune introduces.
        hooks = tmp_path / ".git" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "weird.py").write_text("x = 1\n")
        assert gitstate._has_product_code(tmp_path) is False

    def test_product_code_alongside_node_modules_is_detected(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n")
        nm = tmp_path / "node_modules" / "dep"
        nm.mkdir(parents=True)
        (nm / "i.js").write_text("1\n")
        assert gitstate._has_product_code(tmp_path) is True

    def test_walk_never_descends_node_modules(self, tmp_path, monkeypatch):
        # Perf contract: node_modules is pruned at the directory level, never
        # enumerated — the whole point on a JS repo being onboarded.
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "huge.js").write_text("1\n")
        walked: list[str] = []
        real_walk = gitstate.os.walk

        def tracking_walk(top, *args, **kwargs):
            for dirpath, dirnames, filenames in real_walk(top, *args, **kwargs):
                walked.append(dirpath)
                yield dirpath, dirnames, filenames

        monkeypatch.setattr(gitstate.os, "walk", tracking_walk)
        assert gitstate._has_product_code(tmp_path) is False
        assert not any(Path(w).name == "node_modules" for w in walked), (
            "node_modules must be pruned from the walk, not enumerated"
        )
