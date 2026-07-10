"""Tests for the deterministic Critic-consolidation core (critic-persistence-redesign Ch.02).

``prawduct-hook critic-consolidate`` is the write path with no model in it: reviewer
subagents drop per-role partials + a coordinator manifest under
``.prawduct/.critic-partials/``; this command merges them into the canonical
``.critic-findings.json`` + a ``review.critic`` ledger anchor, clears the
critic-active marker, and removes the partials — but ONLY when every roster role
reported a schema-valid partial at the manifest commit and that commit still covers
HEAD. Everything else is a no-op (incomplete) or a fail-closed error (malformed,
stale, inconsistent). The command is the load-bearing piece of the redesign, so the
truth table is pinned exhaustively.

Two layers: pure-function unit tests (validators + merge) and real-git integration
through ``bin/prawduct-hook critic-consolidate`` with a real ``ledger-append`` — the
sterile-env pattern from ``test_governance_ledger.py`` (HOME outside the repo so
pyc-cache doesn't leak, GIT_CONFIG neutralized).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
sys.path.insert(0, str(ROOT))
from lib import critic_consolidate as cc  # noqa: E402
from lib import gates  # noqa: E402

PARTIALS_REL = ".prawduct/.critic-partials"
FINDINGS_REL = ".prawduct/.critic-findings.json"
MARKER_REL = ".prawduct/.critic-active"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"
FINAL_MODE = "final (full review, ready for push)"


# ---------------------------------------------------------------------------
# Real-git helpers (sterile env — mirrors test_governance_ledger.py)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_consolidate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-consolidate"],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _partials_dir(repo: Path) -> Path:
    d = repo / PARTIALS_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_manifest(repo: Path, head: str, *, roster=None, **overrides) -> None:
    manifest = {
        "mode": FINAL_MODE,
        "mode_chosen_by": "rule-3 final",
        "roster": roster if roster is not None else ["correctness", "design", "sustainability"],
        "commit_reviewed": head,
        "files_reviewed": ["src/app.py"],
        "scope": "demo-scope",
        "chunk": "01",
        "model": "opus",
    }
    manifest.update(overrides)
    (_partials_dir(repo) / "manifest.json").write_text(json.dumps(manifest))


def _partial(role: str, head: str, findings=None, **overrides) -> dict:
    data = {
        "role": role,
        "goals": "1-3",
        "commit_reviewed": head,
        "model": "opus",
        "duration_seconds": 90,
        "findings": findings if findings is not None else [],
        "summary": f"{role} review complete.",
    }
    data.update(overrides)
    return data


def _write_partial(repo: Path, role: str, head: str, **kwargs) -> None:
    (_partials_dir(repo) / f"{role}.json").write_text(json.dumps(_partial(role, head, **kwargs)))


def _set_marker(repo: Path) -> None:
    (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
    (repo / MARKER_REL).write_text(json.dumps({"started_at": "2026-07-09T00:00:00Z"}))


def _full_roster_partials(repo: Path, head: str, findings_by_role=None) -> None:
    findings_by_role = findings_by_role or {}
    for role in ("correctness", "design", "sustainability"):
        _write_partial(repo, role, head, findings=findings_by_role.get(role, []))


# ---------------------------------------------------------------------------
# Unit: validators
# ---------------------------------------------------------------------------


class TestValidatePartial:
    def test_minimal_clean_partial_valid(self):
        ok, reason = cc.validate_partial(_partial("correctness", "abc123"))
        assert ok, reason

    def test_partial_with_finding_valid(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "Missing test", "goal": "Nothing Is Missing",
             "severity": "warning", "recommendation": "Add one", "files": ["a.py"]}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    @pytest.mark.parametrize("mutate,frag", [
        (lambda p: p.pop("role"), "role"),
        (lambda p: p.pop("commit_reviewed"), "commit_reviewed"),
        (lambda p: p.pop("summary"), "summary"),
        (lambda p: p.update(goals=""), "goals"),
        (lambda p: p.update(findings="nope"), "findings"),
        (lambda p: p.update(model=42), "model"),
        (lambda p: p.update(duration_seconds="slow"), "duration_seconds"),
    ])
    def test_malformed_partial_rejected(self, mutate, frag):
        p = _partial("correctness", "abc")
        mutate(p)
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert frag in reason

    def test_unknown_severity_rejected(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "critical", "recommendation": "y"}
        ])
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert "severity" in reason

    def test_finding_missing_recommendation_rejected(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "warning"}
        ])
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert "recommendation" in reason


class TestValidateManifest:
    def test_clean_manifest_valid(self):
        manifest = {
            "mode": FINAL_MODE, "mode_chosen_by": "rule-3", "roster": ["a"],
            "commit_reviewed": "abc", "files_reviewed": ["x.py"],
        }
        ok, reason = cc.validate_manifest(manifest)
        assert ok, reason

    def test_bare_mode_token_rejected(self):
        manifest = {
            "mode": "final", "mode_chosen_by": "rule-3", "roster": ["a"],
            "commit_reviewed": "abc", "files_reviewed": ["x.py"],
        }
        ok, reason = cc.validate_manifest(manifest)
        assert not ok
        assert "mode" in reason

    @pytest.mark.parametrize("field", ["mode_chosen_by", "roster", "commit_reviewed", "files_reviewed"])
    def test_missing_required_field_rejected(self, field):
        manifest = {
            "mode": FINAL_MODE, "mode_chosen_by": "rule-3", "roster": ["a"],
            "commit_reviewed": "abc", "files_reviewed": ["x.py"],
        }
        manifest.pop(field)
        ok, reason = cc.validate_manifest(manifest)
        assert not ok
        assert field in reason


# ---------------------------------------------------------------------------
# Unit: merge / dedup / severity
# ---------------------------------------------------------------------------


class TestMergeFindings:
    def test_maps_name_to_summary_keeps_recommendation(self):
        partials = [_partial("correctness", "a", findings=[
            {"name": "Broken thing", "goal": "Nothing Is Broken",
             "severity": "blocking", "recommendation": "Fix it", "files": ["a.py"]}
        ])]
        merged = cc.merge_findings(partials)
        assert merged == [{
            "goal": "Nothing Is Broken", "severity": "blocking",
            "summary": "Broken thing", "recommendation": "Fix it", "files": ["a.py"],
        }]

    def test_dedup_keeps_highest_severity(self):
        # Same (goal, name, files) reported by two reviewers at differing severity.
        f_warn = {"name": "Dup", "goal": "G", "severity": "warning", "recommendation": "r"}
        f_block = {"name": "Dup", "goal": "G", "severity": "blocking", "recommendation": "r"}
        merged = cc.merge_findings([
            _partial("correctness", "a", findings=[f_warn]),
            _partial("design", "a", findings=[f_block]),
        ])
        assert len(merged) == 1
        assert merged[0]["severity"] == "blocking"

    def test_distinct_findings_all_kept(self):
        merged = cc.merge_findings([
            _partial("correctness", "a", findings=[
                {"name": "A", "goal": "G1", "severity": "warning", "recommendation": "r"}]),
            _partial("design", "a", findings=[
                {"name": "B", "goal": "G2", "severity": "note", "recommendation": "r"}]),
        ])
        assert len(merged) == 2

    def test_build_record_is_schema_valid(self, tmp_path):
        manifest = {
            "mode": FINAL_MODE, "mode_chosen_by": "rule-3",
            "roster": ["correctness"], "commit_reviewed": "abc123",
            "files_reviewed": ["src/app.py"], "model": "opus",
        }
        record = cc.build_record(manifest, [_partial("correctness", "abc123")])
        p = tmp_path / "f.json"
        p.write_text(json.dumps(record))
        assert gates.validate_critic_findings(p)


# ---------------------------------------------------------------------------
# Unit: pending_state
# ---------------------------------------------------------------------------


class TestPendingState:
    def test_no_manifest_is_none(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        assert cc.pending_state(tmp_path / ".prawduct") == ("none", [])

    def test_incomplete_names_missing_roles(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _write_manifest(repo, "abc")
        _write_partial(repo, "correctness", "abc")
        state, missing = cc.pending_state(repo / ".prawduct")
        assert state == "incomplete"
        assert set(missing) == {"design", "sustainability"}

    def test_complete_when_all_partial_files_present(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _write_manifest(repo, "abc")
        _full_roster_partials(repo, "abc")
        assert cc.pending_state(repo / ".prawduct") == ("complete", [])

    def test_corrupt_manifest_is_unreadable(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _partials_dir(repo)
        (repo / PARTIALS_REL / "manifest.json").write_text("{not json")
        assert cc.pending_state(repo / ".prawduct") == ("unreadable", [])


# ---------------------------------------------------------------------------
# Integration: real git + real ledger-append through the hook
# ---------------------------------------------------------------------------


class TestConsolidateIntegration:
    def test_complete_partials_at_head_consolidates(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head, findings_by_role={
            "correctness": [{"name": "Missing edge test", "goal": "Nothing Is Missing",
                             "severity": "warning", "recommendation": "Add it", "files": ["src/app.py"]}],
        })
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated:" in result.stdout

        # Findings written + schema-valid + covers HEAD.
        findings_path = repo / FINDINGS_REL
        assert findings_path.is_file()
        assert gates.validate_critic_findings(findings_path)
        record = json.loads(findings_path.read_text())
        assert record["commit_reviewed"] == head
        assert record["mode"] == FINAL_MODE
        assert len(record["findings"]) == 1
        assert record["findings"][0]["summary"] == "Missing edge test"

        # Ledger anchor present.
        ledger_lines = (repo / LEDGER_REL).read_text().strip().splitlines()
        assert len(ledger_lines) == 1
        event = json.loads(ledger_lines[0])
        assert event["event"] == "review.critic"
        assert event["scope"] == "demo-scope"

        # Marker cleared + partials removed.
        assert not (repo / MARKER_REL).is_file()
        assert not (repo / PARTIALS_REL).exists()

    def test_missing_role_is_noop_names_role(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        # sustainability absent.
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "no-op" in result.stdout
        assert "sustainability" in result.stdout
        # Nothing persisted; marker + partials intact for the straggler to complete.
        assert not (repo / FINDINGS_REL).is_file()
        assert (repo / MARKER_REL).is_file()
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_head_moved_since_dispatch_is_stale_error(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        # A code commit lands after dispatch — the review is now stale.
        _commit_file(repo, "src/app.py", "x = 2\n", "later")
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "no longer covers HEAD" in result.stderr
        assert not (repo / FINDINGS_REL).is_file()
        # Left in place to retry after re-review.
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_md_only_commit_after_dispatch_still_covers(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        # A docs-only commit after dispatch does NOT invalidate the review.
        _commit_file(repo, "notes.md", "# notes\n", "docs")
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated:" in result.stdout

    def test_malformed_partial_fails_closed(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        # sustainability present but malformed (bad severity).
        (repo / PARTIALS_REL / "sustainability.json").write_text(json.dumps({
            "role": "sustainability", "goals": "5-6", "commit_reviewed": head,
            "summary": "s", "findings": [
                {"name": "x", "goal": "g", "severity": "showstopper", "recommendation": "y"}],
        }))
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "sustainability" in result.stderr
        assert not (repo / FINDINGS_REL).is_file()

    def test_partial_reviewed_wrong_commit_fails_closed(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        _write_partial(repo, "sustainability", "deadbeefdeadbeef")  # different commit
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "inconsistent" in result.stderr or "reviewed" in result.stderr
        assert not (repo / FINDINGS_REL).is_file()

    def test_no_manifest_is_clean_noop(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        result = _run_consolidate(repo)
        assert result.returncode == 0
        assert "no-op" in result.stdout

    def test_idempotent_second_call_is_clean_noop(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        first = _run_consolidate(repo)
        assert first.returncode == 0 and "consolidated:" in first.stdout
        second = _run_consolidate(repo)
        assert second.returncode == 0
        assert "no-op" in second.stdout
        # Exactly one ledger anchor — the second call added nothing.
        ledger_lines = (repo / LEDGER_REL).read_text().strip().splitlines()
        assert len(ledger_lines) == 1

    def test_clean_review_no_findings_still_valid(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)  # all clean, zero findings
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["findings"] == []
        assert "0 blocking" in record["summary"]
        # files_reviewed non-empty (from manifest) so schema holds even clean.
        assert gates.validate_critic_findings(repo / FINDINGS_REL)
