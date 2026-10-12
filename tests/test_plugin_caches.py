"""`lib/plugin_caches.py` and `prawduct-hook stale-plugin-caches`.

Claude Code keeps every plugin version it ever installed under each config
root's `plugins/cache/<marketplace>/<plugin>/<version>/`, and nothing prunes
them. The report names the prawduct version directories no install record
uses, so an operator can delete them. The properties under test are the ones a
wrong answer would cost: an in-use version is never listed, a cache shared by
several profiles is counted once, a record whose path only exists inside a
container still protects its version, a profile whose record cannot be read is
never called all-stale, and the command changes nothing on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib import plugin_caches

HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _cache(root: Path, *versions: str, marketplace: str = "prawduct") -> Path:
    base = root / "plugins" / "cache" / marketplace / "prawduct"
    for version in versions:
        (base / version).mkdir(parents=True, exist_ok=True)
        (base / version / "payload.txt").write_text("x" * 5000, encoding="utf-8")
    return base


def _manifest(root: Path, records: list[dict]) -> None:
    path = root / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 2, "plugins": {"prawduct@prawduct": records}}),
        encoding="utf-8",
    )


def _home(tmp_path: Path) -> Path:
    """Three profiles, shaped like a real multi-account machine:

    - `.claude`: its own cache, 1.0 and 2.0 on disk, 2.0 recorded in use;
    - `.claude-second`: `plugins/` is a symlink to `.claude`'s, so it is the
      same cache and must not be counted twice;
    - `.claude-box-devcontainer`: its record names a container path that does
      not exist here, so its version is kept by name.
    """
    home = tmp_path / "home"
    main = home / ".claude"
    base = _cache(main, "1.0.0", "2.0.0")
    _manifest(main, [{"scope": "user", "installPath": str(base / "2.0.0"), "version": "2.0.0"}])

    second = home / ".claude-second"
    second.mkdir(parents=True)
    (second / "plugins").symlink_to(main / "plugins")

    box = home / ".claude-box-devcontainer"
    _cache(box, "0.9.0", "1.5.0")
    _manifest(box, [{
        "scope": "project",
        "installPath": "/home/vscode/.claude/plugins/cache/prawduct/prawduct/1.5.0",
        "version": "1.5.0",
    }])
    return home


def _report(home: Path, running: Path | None = None) -> dict:
    return plugin_caches.scan(env={}, home=home, running_root=running)


def _stale(report: dict) -> set[str]:
    return {Path(item["path"]).name for p in report["profiles"] for item in p["stale"]}


class TestWhatIsStale:
    def test_unrecorded_versions_are_listed_and_recorded_ones_are_not(self, tmp_path):
        report = _report(_home(tmp_path))
        assert _stale(report) == {"1.0.0", "0.9.0"}

    def test_a_shared_cache_is_one_profile_naming_every_root(self, tmp_path):
        home = _home(tmp_path)
        report = _report(home)
        caches = [Path(p["cache"]).resolve() for p in report["profiles"]]
        assert len(caches) == len(set(caches)), "a shared cache was counted twice"
        shared = next(p for p in report["profiles"] if len(p["config_roots"]) > 1)
        assert {Path(r).name for r in shared["config_roots"]} == {".claude", ".claude-second"}
        assert report["stale_count"] == 2

    def test_a_container_path_protects_its_version_by_name(self, tmp_path):
        report = _report(_home(tmp_path))
        box = next(p for p in report["profiles"] if "box" in p["config_roots"][0])
        assert box["in_use"] == ["1.5.0"]
        assert [Path(i["path"]).name for i in box["stale"]] == ["0.9.0"]

    def test_a_container_record_protects_only_its_own_profile(self, tmp_path):
        """The container's cache is its own; the same version number in another
        profile's cache is a different directory nothing there uses."""
        home = _home(tmp_path)
        _cache(home / ".claude", "1.5.0")
        report = _report(home)
        main = next(p for p in report["profiles"] if len(p["config_roots"]) > 1)
        assert "1.5.0" in [Path(i["path"]).name for i in main["stale"]]

    def test_a_version_named_by_another_roots_record_is_in_use(self, tmp_path):
        """A record may name a cache under a different profile directory than its
        own (a symlinked `plugins/` makes that the normal case)."""
        home = _home(tmp_path)
        _manifest(home / ".claude-box-devcontainer", [{
            "installPath": str(home / ".claude-second" / "plugins" / "cache" / "prawduct"
                               / "prawduct" / "1.0.0"),
            "version": "1.0.0",
        }])
        assert "1.0.0" not in _stale(_report(home))

    def test_the_running_plugin_is_never_stale(self, tmp_path):
        """A session already running keeps using the version it started with,
        whatever the record now says."""
        home = _home(tmp_path)
        running = home / ".claude" / "plugins" / "cache" / "prawduct" / "prawduct" / "1.0.0"
        assert "1.0.0" not in _stale(_report(home, running=running))

    def test_sizes_are_reported_per_directory_and_in_total(self, tmp_path):
        report = _report(_home(tmp_path))
        sizes = [i["bytes"] for p in report["profiles"] for i in p["stale"]]
        assert all(size >= 5000 for size in sizes)
        assert report["stale_bytes"] == sum(sizes)

    @pytest.mark.skipif(shutil.which("du") is None, reason="needs du")
    def test_sizes_agree_with_du(self, tmp_path):
        """`du -sk` rounds to KiB; within that, the sizes are the same count."""
        report = _report(_home(tmp_path))
        for item in (i for p in report["profiles"] for i in p["stale"]):
            du_kib = int(subprocess.check_output(["du", "-sk", item["path"]]).split()[0])
            assert abs(du_kib * 1024 - item["bytes"]) < 1024, item["path"]


class TestWhatCannotBeGraded:
    def test_a_missing_record_grades_nothing_stale(self, tmp_path):
        home = _home(tmp_path)
        (home / ".claude-box-devcontainer" / "plugins" / "installed_plugins.json").unlink()
        box = next(p for p in _report(home)["profiles"] if "box" in p["config_roots"][0])
        assert box["manifest"] == "missing"
        assert "does not exist" in box["ungraded_reason"]
        assert box["stale"] == []
        assert sorted(box["ungraded"]) == ["0.9.0", "1.5.0"]

    def test_an_unreadable_record_grades_nothing_stale(self, tmp_path):
        home = _home(tmp_path)
        (home / ".claude-box-devcontainer" / "plugins" / "installed_plugins.json").write_text(
            "{not json", encoding="utf-8")
        box = next(p for p in _report(home)["profiles"] if "box" in p["config_roots"][0])
        assert box["manifest"] == "unreadable"
        assert box["stale"] == []

    @pytest.mark.parametrize("plugins", [
        {"prawduct@prawduct": {"installPath": "x"}},           # entry not a list
        {"prawduct@prawduct": ["not a record"]},               # record not an object
        {"prawduct@prawduct": [{"version": "1.5.0"}]},          # record without installPath
        {"prawduct@prawduct": [{"installPath": 7}]},            # installPath not a string
        {"prawduct@other": [{}], "prawduct@prawduct": []},      # bad record under another marketplace
    ])
    def test_a_record_it_cannot_read_grades_nothing_stale(self, tmp_path, plugins):
        """An unreadable record might be the one naming the version a profile
        loads, so its profile gets no delete command at all."""
        home = _home(tmp_path)
        (home / ".claude-box-devcontainer" / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8")
        box = next(p for p in _report(home)["profiles"] if "box" in p["config_roots"][0])
        assert box["manifest"] == "unreadable"
        assert box["stale"] == []
        assert sorted(box["ungraded"]) == ["0.9.0", "1.5.0"]
        assert "installed_plugins.json" in box["ungraded_reason"]
        assert "prawduct@" in box["ungraded_reason"], "the reason must name the record"

    def test_another_plugins_odd_record_does_not_ungrade_the_profile(self, tmp_path):
        home = _home(tmp_path)
        path = home / ".claude-box-devcontainer" / "plugins" / "installed_plugins.json"
        data = json.loads(path.read_text())
        data["plugins"]["someone-else@market"] = "anything"
        path.write_text(json.dumps(data), encoding="utf-8")
        box = next(p for p in _report(home)["profiles"] if "box" in p["config_roots"][0])
        assert box["manifest"] == "ok"

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable directories")
    def test_a_cache_it_cannot_list_is_reported_not_dropped(self, tmp_path):
        home = _home(tmp_path)
        cache = home / ".claude-box-devcontainer" / "plugins" / "cache"
        cache.chmod(0)
        try:
            report = _report(home)
        finally:
            cache.chmod(0o755)
        box = next(p for p in report["profiles"] if "box" in p["config_roots"][0])
        assert box["cache_readable"] is False
        assert "could not be listed" in box["ungraded_reason"]
        assert box["stale"] == []

    def test_a_root_without_a_prawduct_cache_is_not_a_profile(self, tmp_path):
        home = _home(tmp_path)
        (home / ".claude-empty").mkdir()
        roots = {Path(r).name for p in _report(home)["profiles"] for r in p["config_roots"]}
        assert ".claude-empty" not in roots

    def test_no_home_yields_an_empty_report(self, tmp_path):
        report = _report(tmp_path / "nowhere")
        assert report["profiles"] == [] and report["stale_count"] == 0


def _digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        h.update(str(path.relative_to(root)).encode())
        if path.is_file() and not path.is_symlink():
            h.update(path.read_bytes())
    return h.hexdigest()


class TestTheCommand:
    def _run(self, home: Path, *args: str):
        env = {**os.environ, "HOME": str(home)}
        env.pop("CLAUDE_CONFIG_DIR", None)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        return subprocess.run(
            [sys.executable, str(HOOK), "stale-plugin-caches", *args],
            capture_output=True, text=True, env=env, cwd=str(home),
        )

    def test_it_reports_and_changes_nothing(self, tmp_path):
        home = _home(tmp_path)
        before = _digest(home)
        result = self._run(home)
        assert result.returncode == 0, result.stderr
        assert before == _digest(home), "a read-only report changed the tree"
        deletes = [line for line in result.stdout.splitlines() if "rm -rf" in line]
        assert {Path(line.split()[-1].strip("'")).name for line in deletes} == {"1.0.0", "0.9.0"}
        assert "close" in result.stdout.lower(), "the running-session warning is missing"

    def test_the_plugin_running_the_command_is_never_offered_for_deletion(self, tmp_path):
        """The wiring, not the predicate: a hook executing from inside a cache
        version that no record names must protect its own directory."""
        home = _home(tmp_path)
        running = home / ".claude" / "plugins" / "cache" / "prawduct" / "prawduct" / "1.0.0"
        (running / "bin").mkdir(parents=True)
        shutil.copy2(HOOK, running / "bin" / "prawduct-hook")
        env = {**os.environ, "HOME": str(home),
               "CLAUDE_PLUGIN_ROOT": str(HOOK.parent.parent)}  # the real lib/ to import
        env.pop("CLAUDE_CONFIG_DIR", None)
        result = subprocess.run(
            [sys.executable, str(running / "bin" / "prawduct-hook"), "stale-plugin-caches", "--json"],
            capture_output=True, text=True, env=env, cwd=str(home),
        )
        assert result.returncode == 0, result.stderr
        stale = {Path(i["path"]).name for p in json.loads(result.stdout)["profiles"] for i in p["stale"]}
        assert stale == {"0.9.0"}, "the running version, or the control, was misclassified"

    def test_an_ungraded_profile_says_why_in_the_human_report(self, tmp_path):
        home = _home(tmp_path)
        (home / ".claude-box-devcontainer" / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {"prawduct@prawduct": [{"version": "1"}]}}),
            encoding="utf-8")
        result = self._run(home)
        line = next(l for l in result.stdout.splitlines() if "not graded" in l)
        assert "installPath" in line and "0.9.0" in line

    def test_json_carries_the_report(self, tmp_path):
        result = self._run(_home(tmp_path), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema_version"] == 1
        assert data["stale_count"] == 2
        # The key sets are the ones api-contract.md publishes for `stale-plugin-caches --json`;
        # an exact set catches an added key as well as a dropped one.
        assert set(data) == {"schema_version", "stale_count", "stale_bytes", "profiles"}
        assert data["profiles"]
        for profile in data["profiles"]:
            assert set(profile) == {
                "config_roots", "cache", "cache_readable", "manifest", "ungraded_reason",
                "in_use", "stale", "stale_bytes", "ungraded",
            }
            for item in profile["stale"]:
                assert set(item) == {"path", "bytes"}
        assert any(profile["stale"] for profile in data["profiles"])

    def test_an_unknown_argument_is_a_usage_error(self, tmp_path):
        result = self._run(_home(tmp_path), "--delete")
        assert result.returncode == 2
        assert "--delete" in result.stderr
