"""Canonical guide resolution and observed-only doctor receipts."""

import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ADAPTER = Path(__file__).resolve().parents[1]
PLUGIN = ADAPTER.parents[1] / "plugin"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(PLUGIN))

import doctor  # noqa: E402
import observation  # noqa: E402
from lib import host  # noqa: E402


def _repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "develop"], cwd=path, check=True)
    (path / ".prawduct").mkdir()
    return path


def _event(kind, repo, session="current", source=None):
    raw = {"session_id": session, "cwd": str(repo)}
    if source is not None:
        raw["source"] = source
    return host.read_event(kind, raw)


def test_skill_resolves_exact_canonical_files_in_source_and_isolated_layout(tmp_path):
    overview = PLUGIN / "skills" / "methodology" / "SKILL.md"
    guide = PLUGIN / "methodology" / "building.md"
    expected = {
        overview.resolve(): "87953b9984645092bc93b344af3fd242f762b5c1b778f5f0699e37e70233e7de",
        guide.resolve(): "d15712de890b5b3da80d82435da7bb3a5e076ad61af869045d55b295fb56e136",
    }
    for isolated in (False, True):
        root = tmp_path / "isolated" if isolated else ADAPTER
        if isolated:
            root.mkdir()
            for name in ("methodology.py", "session_start.py"):
                (root / name).write_bytes((ADAPTER / name).read_bytes())
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("PRAWDUCT_CANONICAL_PLUGIN_ROOT", None)
        if isolated:
            env["PRAWDUCT_CANONICAL_PLUGIN_ROOT"] = str(PLUGIN)
        result = subprocess.run([sys.executable, str(root / "methodology.py")],
                                capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        resolved = [Path(line) for line in result.stdout.splitlines()]
        assert resolved == list(expected)
        for path in resolved:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[path]
    assert not any(path.name == "building.md" for path in ADAPTER.rglob("*"))
    skill = ADAPTER / "skills" / "methodology" / "SKILL.md"
    assert "name: methodology\n" in skill.read_text()
    assert "Read the printed canonical overview in full first" in skill.read_text()
    link = tmp_path / "repo" / ".agents" / "skills" / "methodology"
    link.parent.mkdir(parents=True)
    link.symlink_to(skill.parent, target_is_directory=True)
    assert (link / "SKILL.md").resolve() == skill
    assert not any(path.name == "SKILL.md" and path != skill
                   for path in ADAPTER.rglob("SKILL.md"))


def test_no_canonical_plugin_files_are_copied_into_adapter():
    # Cache output is generated locally and is not part of the adapter artifact.
    canonical = {}
    for path in PLUGIN.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            canonical.setdefault(hashlib.sha256(data).digest(), []).append((path, data))
    copies = []
    for path in ADAPTER.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        data = path.read_bytes()
        for original, expected in canonical.get(hashlib.sha256(data).digest(), []):
            if data == expected:
                copies.append((str(path.relative_to(ADAPTER)), str(original.relative_to(PLUGIN))))
    assert not copies, f"Canonical plugin files copied into adapter: {copies}"


def test_isolated_skill_refuses_missing_root(tmp_path):
    root = tmp_path / "isolated"
    root.mkdir()
    for name in ("methodology.py", "session_start.py"):
        (root / name).write_bytes((ADAPTER / name).read_bytes())
    env = {**os.environ, "PRAWDUCT_CANONICAL_PLUGIN_ROOT": str(tmp_path / "missing"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, str(root / "methodology.py")],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert "unavailable" in result.stderr


def test_exact_doctor_entrypoint_in_governed_repo(tmp_path):
    repo = _repo(tmp_path / "repo")
    entry = ADAPTER / "bin" / "doctor"
    assert entry.stat().st_mode & stat.S_IXUSR
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([str(entry), "--session-id", "fixture"], cwd=repo,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["experimental"] is True
    assert report["hook_declaration"]["status"] == "ok"
    assert report["registration"]["status"] == "not-verified"
    assert report["session_identity"]["status"] == "not-verified"
    assert report["trust"]["status"] == "not-verified"


def test_uninstalled_adapter_declaration_is_not_effective_registration(tmp_path):
    repo = _repo(tmp_path / "repo")
    adapter = tmp_path / "uninstalled-adapter"
    (adapter / "hooks").mkdir(parents=True)
    for name in ("doctor.py", "observation.py"):
        (adapter / name).write_bytes((ADAPTER / name).read_bytes())
    (adapter / "hooks" / "hooks.json").write_bytes(
        (ADAPTER / "hooks" / "hooks.json").read_bytes())
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, str(adapter / "doctor.py"),
                             "--repo", str(repo), "--session-id", "uninstalled"],
                            capture_output=True, text=True, env=env, timeout=15)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["hook_declaration"]["status"] == "ok"
    assert report["registration"]["status"] == "not-verified"
    assert "no independent read-only Codex host registry receipt" in report["registration"]["detail"]


def test_marker_is_bound_to_repo_session_and_boundary(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    other = _repo(tmp_path / "other")
    monkeypatch.setenv("PRAWDUCT_HOST", "codex")
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "state"))
    assert not observation.record(repo, _event("session_start", repo, source="fork"),
                                  source="fork", overflow=False)
    assert not (tmp_path / "state").exists()
    first = _event("session_start", repo, source="startup")
    assert observation.record(repo, first, source=first.source, overflow=True)
    stop = _event("stop", repo)
    assert observation.record(repo, stop)
    assert [item["event"] for item in observation.read_marker(repo, "current")["events"]] == [
        "session_start", "stop"]
    assert observation.read_marker(repo, "other-session") is None
    assert observation.read_marker(other, "current") is None
    assert doctor.diagnose(repo, "other-session", ADAPTER)["stop"]["status"] == "not-verified"
    assert doctor.diagnose(other, "current", ADAPTER)["stop"]["status"] == "not-verified"
    assert doctor.diagnose(repo, "current", ADAPTER)["stop"]["status"] == "not-verified"
    assert doctor.diagnose(repo, "current", ADAPTER)["d9_overflow"]["status"] == "not-verified"
    boundary = _event("session_start", repo, source="clear")
    assert observation.record(repo, boundary, source=boundary.source, overflow=False)
    events = observation.read_marker(repo, "current")["events"]
    assert [item["event"] for item in events] == ["session_start"]
    assert events[0]["fields_present"] == ["cwd", "session_id", "source"]
    assert events[0]["boundary"] is True
    assert doctor.diagnose(repo, "current", ADAPTER)["stop"]["status"] == "not-verified"


def test_doctor_never_promotes_stale_or_absent_identity_and_trust(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("PRAWDUCT_HOST", "codex")
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "state"))
    start = _event("session_start", repo, source="startup")
    observation.record(repo, start, source=start.source, overflow=False)
    observation.record(repo, _event("stop", repo))
    assert doctor.diagnose(repo, None, ADAPTER)["session_start"]["status"] == "not-verified"
    result = doctor.diagnose(repo, "current", ADAPTER)
    assert result["trust"]["status"] == "not-verified"
    assert result["hook_declaration"]["status"] == "ok"
    assert result["registration"]["status"] == "not-verified"
    path = observation.marker_path(repo, "current")
    marker = json.loads(path.read_text())
    for event in marker["events"]:
        event["observed_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(marker))
    stale = doctor.diagnose(repo, "current", ADAPTER)
    assert stale["session_start"]["status"] == "not-verified"
    assert stale["stop"]["status"] == "not-verified"
    assert stale["d9_overflow"]["status"] == "not-verified"


def test_receipt_does_not_write_inside_governed_repo(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("PRAWDUCT_HOST", "codex")
    monkeypatch.setenv("PLUGIN_DATA", str(repo / "state"))
    assert not observation.record(repo, _event("session_start", repo, source="startup"),
                                  source="startup", overflow=False)
    assert not (repo / "state").exists()


def test_entry_points_record_real_payloads_without_inventing_trust(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    state = tmp_path / "plugin-data"
    env = {**os.environ, "PLUGIN_DATA": str(state),
           "PRAWDUCT_CANONICAL_PLUGIN_ROOT": str(PLUGIN),
           "PYTHONDONTWRITEBYTECODE": "1"}

    def fire(script, payload):
        return subprocess.run([sys.executable, str(ADAPTER / script)],
                              input=json.dumps({"cwd": str(repo), "session_id": "live-fixture",
                                                **payload}), capture_output=True,
                              text=True, cwd=repo, env=env, timeout=120)

    assert fire("session_start.py", {"source": "unknown"}).returncode == 0
    assert not state.exists()
    assert fire("session_start.py", {"source": "startup"}).returncode == 0
    monkeypatch.setenv("PLUGIN_DATA", str(state))
    marker = observation.read_marker(repo, "live-fixture")
    assert marker["events"][0]["event"] == "session_start"
    assert marker["events"][0]["source"] == "startup"
    assert marker["events"][0]["boundary"] is True
    fire("stop.py", {"last_assistant_message": None})
    marker = observation.read_marker(repo, "live-fixture")
    assert marker["events"][-1]["event"] == "stop"
    assert "last_assistant_message" in marker["events"][-1]["fields_present"]
    result = doctor.diagnose(repo, "live-fixture", ADAPTER)
    assert result["session_identity"]["status"] == "not-verified"
    assert result["session_start"]["status"] == "not-verified"
    assert result["stop"]["status"] == "not-verified"
    assert [item["event"] for item in result["observed_events"]] == ["session_start", "stop"]
    assert result["trust"]["status"] == "not-verified"


def test_pinned_version_needs_exact_observed_binary(monkeypatch):
    monkeypatch.setattr(doctor.subprocess, "check_output", lambda *a, **k: "codex-cli 0.156.1\n")
    assert doctor._version()["status"] == "ok"
    monkeypatch.setattr(doctor.subprocess, "check_output", lambda *a, **k: "codex-cli 0.157.0\n")
    assert doctor._version()["status"] == "not-verified"


def test_actual_session_start_overflow_reaches_doctor(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    core = repo / ".claude" / "rules" / "learnings" / "core.md"
    core.parent.mkdir(parents=True)
    core.write_text("x" * 25000)
    state = tmp_path / "plugin-data"
    env = {**os.environ, "PLUGIN_DATA": str(state),
           "PRAWDUCT_CANONICAL_PLUGIN_ROOT": str(PLUGIN),
           "PYTHONDONTWRITEBYTECODE": "1"}
    payload = {"cwd": str(repo), "session_id": "overflow-fixture", "source": "startup"}
    result = subprocess.run([sys.executable, str(ADAPTER / "session_start.py")],
                            input=json.dumps(payload), capture_output=True, text=True,
                            cwd=repo, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("Prawduct experimental Codex SessionStart context exceeds")
    monkeypatch.setenv("PLUGIN_DATA", str(state))
    report = doctor.diagnose(repo, "overflow-fixture", ADAPTER)
    assert report["d9_overflow"]["status"] == "not-verified"
    assert report["observed_events"][0]["overflow"] is True


def test_fresh_old_session_receipt_cannot_make_current_claim(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    monkeypatch.setenv("PRAWDUCT_HOST", "codex")
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "state"))
    old = _event("session_start", repo, session="old-session", source="startup")
    observation.record(repo, old, source=old.source, overflow=False)
    observation.record(repo, _event("stop", repo, session="old-session"))
    new = _event("session_start", repo, session="new-session", source="startup")
    observation.record(repo, new, source=new.source, overflow=False)
    # Both markers are fresh and valid. The caller chooses the old ID.
    report = doctor.diagnose(repo, "old-session", ADAPTER)
    assert len(report["observed_events"]) == 2
    for check in ("session_identity", "session_start", "stop", "d9_overflow"):
        assert report[check]["status"] == "not-verified"
