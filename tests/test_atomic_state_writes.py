"""Atomic `.prawduct` state-file writes + cmd_clear OSError resilience (STH-8M3V).

`core.atomic_write_text` (tmp sibling + `os.replace`) is the shared writer for
the session state files whose readers fail open — `.session-start`,
`.session-git-baseline`, `.session-handoff.md`, `.advisories.json` — so a torn
write from two concurrent sessions on one repo can no longer silently misfire
a gate. (`.gates-waived` was audited into the set but has no code write site —
it is agent-written — so there is nothing to convert.)

STH-9T4F extends the converted set with the two sites that were out of
STH-8M3V's groomed scope: the critic-active marker write
(`lib/critic_marker.py`) and the operator-verification queue rewrite
(`lib/operator_verification.py`) — same rationale (readers fail open, a torn
write misfires governance silently).

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
import sys
from pathlib import Path

import pytest

from lib import advisory_store, briefing, core, critic_marker, operator_verification

ROOT = Path(__file__).resolve().parent.parent / "plugin"
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

    def test_writes_utf8_under_a_non_utf8_locale(self, tmp_path):
        """The shared writer must not write at the locale encoding.

        A locale-encoded write is lossy on the round trip and raises outright
        on non-ASCII. This has been latent because most callers write JSON at
        `ensure_ascii=True`; `.session-handoff.md` does not, and it routinely
        carries em-dashes.

        The writer is only half the round trip and this test only pins that
        half — several readers under `plugin/lib/` still use a bare
        `read_text()`. Where a reader pairs with a write through this helper
        the pair must agree, or a default change turns a self-inverse pair
        asymmetric; `operator_verification` is that case and is pinned
        separately in `tests/test_operator_verification.py`.

        Runs in a subprocess with the locale forced, because **the defect is
        invisible on a UTF-8 machine** — an in-process assertion here would
        pass identically against the broken code. Verified that this env really
        does reproduce it: `locale.getpreferredencoding(False)` returns
        `US-ASCII` and the bare write raises `UnicodeEncodeError`.
        """
        target = tmp_path / "handoff.md"
        script = (
            "from pathlib import Path\n"
            "from lib import core\n"
            f"core.atomic_write_text(Path({str(target)!r}), 'em\\u2014dash \\u00e9\\n')\n"
        )
        env = {
            **os.environ,
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONUTF8": "0",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONPATH": str(ROOT),
        }
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env
        )
        assert result.returncode == 0, (
            "atomic_write_text raised under a non-UTF-8 locale — it is still "
            f"writing at the locale encoding. stderr={result.stderr!r}"
        )
        assert target.read_bytes().decode("utf-8") == "em—dash é\n"

    def test_explicit_encoding_and_newline_still_honoured(self, tmp_path):
        """The utf-8 default must not swallow a caller's explicit arguments.

        `learnings_obligation.repair` writes into a product's *authored* file
        and passes `newline=""` so the bytes around its insertion are not
        re-line-ended. That opt-out is independent of the encoding default and
        has to survive it.
        """
        target = tmp_path / "authored.md"
        core.atomic_write_text(target, "a\r\nb\n", encoding="utf-8", newline="")
        assert target.read_bytes() == b"a\r\nb\n"

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

    def test_critic_marker_written_atomically_no_residue(self, tmp_path):
        """STH-9T4F: the critic-active marker — read by the session-mutation
        guard, which fails open on a missing/corrupt marker — is written
        atomically, so a torn write can't silently drop the guard."""
        pr = tmp_path / ".prawduct"
        pr.mkdir()
        assert critic_marker.write_marker(pr) is True
        marker = pr / critic_marker.MARKER_NAME
        assert json.loads(marker.read_text())["tool"] == "critic"
        assert not marker.with_name(marker.name + ".tmp").exists()

    def test_operator_queue_written_atomically_no_residue(self, tmp_path):
        """STH-9T4F: the operator-verification queue rewrite — a `/pr create`
        gate input — is written atomically."""
        queue = tmp_path / "operator-verification.md"
        operator_verification._write_queue(queue, "# Operator Verification\n", [])
        assert queue.is_file()
        assert not queue.with_name(queue.name + ".tmp").exists()
        # Round-trips through the parser (the gate reads it back).
        preamble, entries = operator_verification.parse_operator_verification(
            queue.read_text()
        )
        assert "Operator Verification" in preamble and entries == []

    def test_source_pins_audited_sites_use_atomic_writer(self):
        """The audited non-atomic writes (STH-8M3V groom 2026-06-10, plus the
        STH-9T4F follow-ups) must not quietly revert to bare write_text."""
        hook_src = HOOK.read_text()
        assert 'atomic_write_text(prawduct_dir / ".session-start"' in hook_src
        assert 'atomic_write_text(prawduct_dir / ".session-git-baseline"' in hook_src
        assert '".session-start").write_text' not in hook_src
        assert '".session-git-baseline").write_text' not in hook_src
        briefing_src = (ROOT / "lib" / "briefing.py").read_text()
        assert '".session-handoff.md").write_text' not in briefing_src
        adv_src = (ROOT / "lib" / "advisory_store.py").read_text()
        assert "path.write_text" not in adv_src
        # STH-9T4F sites.
        cm_src = (ROOT / "lib" / "critic_marker.py").read_text()
        assert "atomic_write_text(_marker_path(prawduct_dir)" in cm_src
        assert "_marker_path(prawduct_dir).write_text" not in cm_src
        ov_src = (ROOT / "lib" / "operator_verification.py").read_text()
        assert "atomic_write_text(" in ov_src
        assert "queue_path.write_text" not in ov_src


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


# ---------------------------------------------------------------------------
# `write_all_or_none` — atomicity ACROSS a pair of files
# ---------------------------------------------------------------------------


class TestWriteAllOrNone:
    """One file's write is already all-or-nothing; two files' was not.

    The shape this closes is a record and its archive, where entries MOVE from
    one to the other: a first write landing and a second raising leaves every
    moved entry in both files, and the natural recovery — run it again —
    duplicates them into an append-only record. Three modules reach for this
    shape (`change_log_archive`, `plan_archive`, `audit_learnings_cmd`); this is
    the one implementation rather than a third hand-rolled rollback.
    """

    def _core(self):
        import sys
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parent.parent / "plugin"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from lib import core

        return core

    def test_both_files_are_written_on_success(self, tmp_path):
        core = self._core()
        a, b = tmp_path / "a.md", tmp_path / "b.md"
        core.write_all_or_none([(a, "A"), (b, "B")])
        assert a.read_text(encoding="utf-8") == "A"
        assert b.read_text(encoding="utf-8") == "B"

    def test_a_failure_restores_prior_content(self, tmp_path, monkeypatch):
        core = self._core()
        a, b = tmp_path / "a.md", tmp_path / "b.md"
        a.write_text("original A", encoding="utf-8")
        b.write_text("original B", encoding="utf-8")

        real = core.atomic_write_text
        seen = {"n": 0}

        def _explode(path, text, **kwargs):
            seen["n"] += 1
            if seen["n"] == 2:
                raise OSError("disk full")
            return real(path, text, **kwargs)

        monkeypatch.setattr(core, "atomic_write_text", _explode)
        with pytest.raises(OSError):
            core.write_all_or_none([(a, "new A"), (b, "new B")])

        assert a.read_text(encoding="utf-8") == "original A"
        assert b.read_text(encoding="utf-8") == "original B"

    def test_a_file_that_did_not_exist_is_removed_again(self, tmp_path, monkeypatch):
        """Restoring "as it was" includes not existing — a leftover half-written
        archive is exactly the duplicate-on-retry state this prevents."""
        core = self._core()
        a, b = tmp_path / "a.md", tmp_path / "b.md"

        real = core.atomic_write_text
        seen = {"n": 0}

        def _explode(path, text, **kwargs):
            seen["n"] += 1
            if seen["n"] == 2:
                raise OSError("disk full")
            return real(path, text, **kwargs)

        monkeypatch.setattr(core, "atomic_write_text", _explode)
        with pytest.raises(OSError):
            core.write_all_or_none([(a, "new A"), (b, "new B")])

        assert not a.exists()
        assert not b.exists()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
    def test_an_existing_file_it_cannot_read_refuses_before_any_write(self, tmp_path):
        """A prior the rollback cannot restore is a prior it would only delete.

        The old shape read each prior just before its own write and turned an
        `OSError` into "no prior" — so an unreadable file was written over, and
        when a LATER write failed the rollback deleted it: unreadable became
        gone. Reading every prior BEFORE the first write turns the same
        condition into a refusal with nothing touched."""
        core = self._core()
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("old A", encoding="utf-8")
        a.chmod(0)
        try:
            with pytest.raises(PermissionError):
                core.write_all_or_none([(a, "new A"), (b, "B")])
            assert not b.exists()
        finally:
            a.chmod(stat.S_IRUSR | stat.S_IWUSR)
        assert a.read_text(encoding="utf-8") == "old A"

    def test_an_interrupt_between_the_two_writes_rolls_the_first_back(
        self, tmp_path, monkeypatch
    ):
        """Ctrl-C is not an `Exception`, and it is exactly the moment the pair is
        half-applied — a re-run would then duplicate every moved entry into the
        append-only file. The rollback runs and the interrupt is re-raised."""
        core = self._core()
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("old A", encoding="utf-8")
        real = core.atomic_write_text
        calls: list = []

        def _interrupted(path, text, *args, **kwargs):
            calls.append(path)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real(path, text, *args, **kwargs)

        monkeypatch.setattr(core, "atomic_write_text", _interrupted)
        with pytest.raises(KeyboardInterrupt):
            core.write_all_or_none([(a, "new A"), (b, "B")])
        assert a.read_text(encoding="utf-8") == "old A"
        assert not b.exists()

    def test_the_original_error_survives_a_failing_rollback(
        self, tmp_path, monkeypatch
    ):
        """A restore that also fails must not replace the exception worth
        reporting — there is nothing left to try, and the first failure is the
        one that explains the state.

        The first write must SUCCEED for this to test anything: with nothing
        written there is no restore to fail, and an earlier version of this test
        raised on write one and asserted its way past the branch it named.
        """
        core = self._core()
        a, b = tmp_path / "a.md", tmp_path / "b.md"
        a.write_text("original A", encoding="utf-8")

        real = core.atomic_write_text
        seen = {"n": 0}

        def _explode_after_the_first(path, text, **kwargs):
            seen["n"] += 1
            if seen["n"] == 1:
                return real(path, text, **kwargs)
            # The second write AND every restore attempt.
            raise OSError("disk full" if seen["n"] == 2 else "rollback failed too")

        monkeypatch.setattr(core, "atomic_write_text", _explode_after_the_first)
        with pytest.raises(OSError, match="disk full"):
            core.write_all_or_none([(a, "new A"), (b, "new B")])

        assert seen["n"] >= 3, "the restore was never attempted — branch ungraded"
