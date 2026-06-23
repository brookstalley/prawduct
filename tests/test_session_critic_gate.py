"""Unit coverage for the shared session Critic gate (STH-4F7C).

`gates.critic_findings_satisfy_session_gate` is the single source of truth for
the freshness + schema + verify-resolutions-scope check that was previously
duplicated — and had diverged — between `cmd_stop`'s blocking gate
(`bin/prawduct-hook`) and the session-start advisory
(`briefing._check_previous_session_gates`): the advisory copy never gained the
v1.5 Chunk 02 scope check, so it reported a stale verify-resolutions record as
satisfying. These tests pin the shared function's truth table, the regression
the extraction fixes (the advisory now warns on a scope-exceeded record), and
— source-level — that neither consumer re-grows an inline copy.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import briefing, gates

ROOT = Path(__file__).resolve().parent.parent

_MODE_VERIFY_RESOLUTIONS = "verify-resolutions (delta review, prior findings only)"


def _prawduct(tmp_path: Path) -> Path:
    p = tmp_path / ".prawduct"
    p.mkdir(exist_ok=True)
    return p


def _stamp(offset_seconds: int = 0) -> str:
    ts = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_findings(mode: str | None = None, files_reviewed=None) -> dict:
    data = {
        "findings": [],
        "files_reviewed": files_reviewed or ["src/app.py"],
        "summary": "Reviewed; no findings.",
    }
    if mode is not None:
        data["mode"] = mode
    return data


def _write_findings(prawduct_dir: Path, data: dict) -> Path:
    path = prawduct_dir / ".critic-findings.json"
    path.write_text(json.dumps(data))
    return path


class TestSatisfySessionGateTruthTable:
    def test_fresh_valid_findings_satisfy(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text(_stamp(-60))
        _write_findings(pr, _valid_findings())
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (True, "")

    def test_missing_findings_fail_closed(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text(_stamp(-60))
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")

    def test_missing_session_start_fails_closed(self, tmp_path):
        pr = _prawduct(tmp_path)
        _write_findings(pr, _valid_findings())
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")

    def test_empty_session_start_fails_closed(self, tmp_path):
        """Tightened vs. the old inline copies (which compared against ""
        and so failed OPEN on an empty marker): an empty `.session-start`
        now rejects, consistent with CRT-8W3F's ledger-fallback stance."""
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text("")
        _write_findings(pr, _valid_findings())
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")

    def test_stale_findings_fail(self, tmp_path):
        pr = _prawduct(tmp_path)
        _write_findings(pr, _valid_findings())
        (pr / ".session-start").write_text(_stamp(60))  # session started "after"
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")

    def test_same_whole_second_tie_is_not_fresh(self, tmp_path):
        """STH-6B4R strict-`>`: a findings mtime in the same whole second as
        `.session-start` does NOT clear the gate."""
        pr = _prawduct(tmp_path)
        findings = _write_findings(pr, _valid_findings())
        tie = datetime.fromtimestamp(
            findings.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        (pr / ".session-start").write_text(tie)
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")

    def test_schema_invalid_findings_fail(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text(_stamp(-60))
        _write_findings(pr, {"findings": "not-a-list"})
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (False, "")


class TestSatisfySessionGateVerifyResolutionsScope:
    def _fresh_vr(self, tmp_path, monkeypatch, *, session_changed):
        pr = _prawduct(tmp_path)
        (pr / ".session-start").write_text(_stamp(-60))
        _write_findings(
            pr,
            _valid_findings(mode=_MODE_VERIFY_RESOLUTIONS, files_reviewed=["src/app.py"]),
        )
        monkeypatch.setattr(
            gates.gitstate, "_get_session_changed_files", lambda d: session_changed
        )
        return pr

    def test_in_scope_satisfies(self, tmp_path, monkeypatch):
        pr = self._fresh_vr(tmp_path, monkeypatch, session_changed=["src/app.py"])
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (True, "")

    def test_out_of_scope_fails_with_reason(self, tmp_path, monkeypatch):
        pr = self._fresh_vr(
            tmp_path, monkeypatch, session_changed=["src/app.py", "src/new_module.py"]
        )
        satisfied, reason = gates.critic_findings_satisfy_session_gate(pr, tmp_path)
        assert satisfied is False
        assert "src/new_module.py" in reason

    # STH-6T9W — an untracked, non-code file outside the work roots is operator
    # noise and must not push an otherwise-in-scope tree out of scope.
    def _patch_untracked(self, monkeypatch, *, untracked, work_roots):
        monkeypatch.setattr(gates, "_untracked_files", lambda d: set(untracked))
        monkeypatch.setattr(gates, "_tracked_work_roots", lambda d: set(work_roots))

    def test_untracked_noncode_note_does_not_inflate_scope(self, tmp_path, monkeypatch):
        pr = self._fresh_vr(
            tmp_path, monkeypatch,
            session_changed=["src/app.py", "scratch/note.txt"],
        )
        self._patch_untracked(
            monkeypatch, untracked={"scratch/note.txt"}, work_roots={"src", "tests"}
        )
        # src/app.py is in scope; the stray untracked note is excluded as noise.
        assert gates.critic_findings_satisfy_session_gate(pr, tmp_path) == (True, "")

    def test_untracked_code_file_still_counts(self, tmp_path, monkeypatch):
        """True-positive preserved: an untracked CODE file is real new work and
        still pushes the tree out of scope."""
        pr = self._fresh_vr(
            tmp_path, monkeypatch,
            session_changed=["src/app.py", "newpkg/feature.py"],
        )
        self._patch_untracked(
            monkeypatch, untracked={"newpkg/feature.py"}, work_roots={"src"}
        )
        satisfied, reason = gates.critic_findings_satisfy_session_gate(pr, tmp_path)
        assert satisfied is False
        assert "newpkg/feature.py" in reason

    def test_untracked_noncode_under_work_root_still_counts(self, tmp_path, monkeypatch):
        """Over-exclusion guard: a non-code file UNDER a work root (a test
        fixture, a governance doc) is presumed real work and stays in scope."""
        pr = self._fresh_vr(
            tmp_path, monkeypatch,
            session_changed=["src/app.py", "tests/fixture.json"],
        )
        self._patch_untracked(
            monkeypatch, untracked={"tests/fixture.json"}, work_roots={"src", "tests"}
        )
        satisfied, reason = gates.critic_findings_satisfy_session_gate(pr, tmp_path)
        assert satisfied is False
        assert "tests/fixture.json" in reason


class TestUntrackedNoncodeNoisePredicate:
    """Unit coverage of the STH-6T9W classifier both scope filters route through."""

    def test_noncode_outside_roots_is_noise(self):
        assert gates._is_untracked_noncode_noise("scratch/note.txt", {"src", "tests"})
        assert gates._is_untracked_noncode_noise("stray.md", set())
        assert gates._is_untracked_noncode_noise("incoming-bugs/x.md", {"src"})

    def test_code_file_is_never_noise(self):
        assert not gates._is_untracked_noncode_noise("anywhere/new.py", set())
        assert not gates._is_untracked_noncode_noise("x.ts", {"src"})
        assert not gates._is_untracked_noncode_noise("newpkg/mod.go", {"src"})

    def test_noncode_under_work_root_is_kept(self):
        assert not gates._is_untracked_noncode_noise("tests/fixture.json", {"tests"})
        assert not gates._is_untracked_noncode_noise("src/data.yaml", {"src", "tests"})


class TestBriefingAdvisoryUsesSharedGate:
    """The regression STH-4F7C fixes: the session-start advisory must warn on a
    fresh verify-resolutions record whose declared scope the diff outgrew —
    before the extraction, the briefing copy had no scope check and reported
    that record as satisfying (no warning)."""

    def _patch(self, monkeypatch):
        # Stubs accept the optional status_output param (STH-6Q9D) the real
        # signatures gained — the gate captures porcelain once and threads it.
        monkeypatch.setattr(briefing.gitstate, "git_has_session_changes", lambda d, s=None: True)
        monkeypatch.setattr(briefing.gitstate, "_session_changes_are_doc_only", lambda d, s=None: False)
        monkeypatch.setattr(briefing.gitstate, "git_has_code_changes", lambda d, s=None: True)
        monkeypatch.setattr(briefing.gates, "_read_gates_waived", lambda d: {})
        monkeypatch.setattr(briefing.gates, "_has_active_build_plan_file", lambda d: True)
        monkeypatch.setattr(briefing.gates, "_has_build_plan_in_state", lambda d: False)

    def test_scope_exceeded_vr_record_now_warns(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / ".session-reflected").write_text("x" * 60)  # silence reflection gate
        (pr / ".session-start").write_text(_stamp(-60))
        _write_findings(
            pr,
            _valid_findings(mode=_MODE_VERIFY_RESOLUTIONS, files_reviewed=["src/app.py"]),
        )
        self._patch(monkeypatch)
        monkeypatch.setattr(
            gates.gitstate,
            "_get_session_changed_files",
            lambda d: ["src/app.py", "src/new_module.py"],
        )
        warnings = briefing._check_previous_session_gates(tmp_path)
        assert any("verify-resolutions scope exceeded" in w for w in warnings)

    def test_fresh_valid_record_no_warning(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        (pr / ".session-reflected").write_text("x" * 60)
        (pr / ".session-start").write_text(_stamp(-60))
        _write_findings(pr, _valid_findings())
        self._patch(monkeypatch)
        assert briefing._check_previous_session_gates(tmp_path) == []


class TestNoInlineCopiesRemain:
    """Source-level re-divergence guard: the freshness computation
    (`'.critic-findings.json'` mtime formatted against `.session-start`) lives
    ONLY in lib/gates.py; both former hosts delegate to the shared gate. The
    pair diverged once already (the advisory missed the scope check) — this
    pins the extraction so a hotfix can't quietly re-inline a third copy."""

    def test_both_consumers_delegate(self):
        hook_src = (ROOT / "bin" / "prawduct-hook").read_text()
        briefing_src = (ROOT / "lib" / "briefing.py").read_text()
        assert "critic_findings_satisfy_session_gate(" in hook_src
        assert "critic_findings_satisfy_session_gate(" in briefing_src

    def test_freshness_computation_only_in_gates(self):
        # Mentions of the findings path are fine (blocker messages); the
        # inline freshness pattern — stat().st_mtime on the findings file —
        # is what must not return to either former host.
        for rel in ("bin/prawduct-hook", "lib/briefing.py"):
            src = (ROOT / rel).read_text()
            assert "critic_findings.stat().st_mtime" not in src, (
                f"{rel} re-grew an inline findings-freshness computation"
            )
        assert "critic_findings.stat().st_mtime" in (ROOT / "lib" / "gates.py").read_text()
