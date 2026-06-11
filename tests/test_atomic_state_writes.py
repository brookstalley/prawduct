"""Atomic `.prawduct` state-file writes + cmd_clear OSError resilience (STH-8M3V).

`core.atomic_write_text` (tmp sibling + `os.replace`) is the shared writer for
the session state files whose readers fail open — `.session-start`,
`.session-git-baseline`, `.session-handoff.md`, `.advisories.json` — so a torn
write from two concurrent sessions on one repo can no longer silently misfire
a gate. (`.gates-waived` was audited into the set but has no code write site —
it is agent-written — so there is nothing to convert.)

The second half pins cmd_clear's failure policy: the session-file unlink loop
and the marker/baseline writes are best-effort — an OSError degrades to a
stderr NOTE naming the consequence and the SessionStart hook still exits 0,
matching the meticulously guarded code around them.

Harness mirrors `test_plugin_runtime.py` (subprocess `bin/prawduct-hook clear`
with a mock git on PATH) because the resilience contract is only observable
end-to-end: the guards compose inside `cmd_clear`.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from lib import advisory_store, briefing, core

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"


# --------------------------------------------------------------------------- #
# core.atomic_write_text — unit truth table
# --------------------------------------------------------------------------- #
class TestAtomicWriteText:
    def test_writes_content(self, tmp_path):
        target = tmp_path / "f.txt"
        core.atomic_write_text(target, "hello\n")
        assert target.read_text() == "hello\n"

    def test_replaces_existing_file(self, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old")
        core.atomic_write_text(target, "new")
        assert target.read_text() == "new"

    def test_no_tmp_residue_on_success(self, tmp_path):
        target = tmp_path / "f.txt"
        core.atomic_write_text(target, "x")
        assert list(tmp_path.iterdir()) == [target]

    def test_oserror_propagates_and_target_untouched(self, tmp_path):
        """Caller owns failure policy, so the helper must raise — and the
        destination must keep its old content (the atomicity contract: old
        or new, never torn/clobbered)."""
        target = tmp_path / "missing-parent" / "f.txt"
        with pytest.raises(OSError):
            core.atomic_write_text(target, "x")  # tmp write fails: no parent dir
        assert not target.exists()

    def test_failed_replace_leaves_old_content(self, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old")
        ro = tmp_path
        ro.chmod(stat.S_IRUSR | stat.S_IXUSR)  # read-only dir: tmp write fails
        try:
            with pytest.raises(OSError):
                core.atomic_write_text(target, "new")
            assert target.read_text() == "old"
        finally:
            ro.chmod(stat.S_IRWXU)


# --------------------------------------------------------------------------- #
# Converted call sites keep their contracts
# --------------------------------------------------------------------------- #
class TestConvertedWriteSites:
    def test_write_store_atomic_and_error_contract(self, tmp_path, monkeypatch):
        ok = advisory_store.write_store(tmp_path, {"schema_version": 1, "advisories": []})
        assert ok["status"] == "ok"
        store_path = tmp_path / ".prawduct" / ".advisories.json"
        assert store_path.is_file()
        assert not store_path.with_name(store_path.name + ".tmp").exists()

        def boom(path, text):
            raise OSError("disk full")

        monkeypatch.setattr(advisory_store, "atomic_write_text", boom)
        bad = advisory_store.write_store(tmp_path, {"schema_version": 1, "advisories": []})
        assert bad["status"] == "error"
        assert "disk full" in bad["reason"]

    def test_handoff_written_atomically_no_residue(self, tmp_path, monkeypatch):
        pr = tmp_path / ".prawduct"
        pr.mkdir()
        (pr / ".session-reflected").write_text("a reflection long enough to persist")
        monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})
        monkeypatch.setattr(briefing.gitstate, "_get_session_changed_files", lambda d: [])
        monkeypatch.setattr(briefing, "_git_session_commits", lambda d: [])
        briefing.generate_session_handoff(tmp_path)
        handoff = pr / ".session-handoff.md"
        assert handoff.is_file()
        assert not handoff.with_name(handoff.name + ".tmp").exists()

    def test_source_pins_audited_sites_use_atomic_writer(self):
        """The audited non-atomic writes (STH-8M3V groom 2026-06-10) must not
        quietly revert to bare write_text."""
        hook_src = HOOK.read_text()
        assert 'atomic_write_text(prawduct_dir / ".session-start"' in hook_src
        assert 'atomic_write_text(prawduct_dir / ".session-git-baseline"' in hook_src
        assert '".session-start").write_text' not in hook_src
        assert '".session-git-baseline").write_text' not in hook_src
        briefing_src = (ROOT / "lib" / "briefing.py").read_text()
        assert '".session-handoff.md").write_text' not in briefing_src
        adv_src = (ROOT / "lib" / "advisory_store.py").read_text()
        assert "path.write_text" not in adv_src


# --------------------------------------------------------------------------- #
# cmd_clear resilience — read-only .prawduct must not traceback SessionStart
# --------------------------------------------------------------------------- #
def _write_mock_git(mock_bin: Path) -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    git = mock_bin / "git"
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "deadbeefdeadbeef"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        'if [[ "$1" == "status" ]]; then echo ""; exit 0; fi\n'
        'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "main"; exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n"
    )
    git.chmod(0o755)


def _run_clear(project_dir: Path) -> subprocess.CompletedProcess:
    mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin)
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "clear", "--session-start"],
        capture_output=True, text=True, env=env, timeout=20,
    )


class TestClearSurvivesReadOnlyPrawduct:
    def test_readonly_prawduct_exits_zero_with_notes(self, tmp_path):
        project = tmp_path / "proj"
        pr = project / ".prawduct"
        pr.mkdir(parents=True)
        (pr / "project-state.yaml").write_text("backlog_format_version: 2\n")
        (pr / ".session-start").write_text("2026-01-01T00:00:00Z")  # unlink target
        pr.chmod(stat.S_IRUSR | stat.S_IXUSR)  # read-only: unlinks + writes fail
        try:
            result = _run_clear(project)
        finally:
            pr.chmod(stat.S_IRWXU)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert "could not remove .session-start" in result.stderr
        assert "could not write .session-start" in result.stderr
        assert "freshness gates will fail closed" in result.stderr

    def test_healthy_clear_writes_markers_atomically(self, tmp_path):
        project = tmp_path / "proj"
        pr = project / ".prawduct"
        pr.mkdir(parents=True)
        (pr / "project-state.yaml").write_text("backlog_format_version: 2\n")
        result = _run_clear(project)
        assert result.returncode == 0, result.stderr
        assert (pr / ".session-start").is_file()
        assert not (pr / ".session-start.tmp").exists()
        assert not (pr / ".session-git-baseline.tmp").exists()
