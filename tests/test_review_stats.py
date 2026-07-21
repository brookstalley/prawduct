"""Tests for `prawduct-hook review-stats` (review-proportionality ch.03).

The aggregation contract: per role × model × mode (and overall) — review
count, total/median duration, findings by severity, actionable rate,
findings-per-review; a findings-by-file rollup from per-finding ``files``
attribution; per-``scope`` rollups. Skips are COUNTED, never silent: corrupt
lines, non-``review.*`` event kinds (forward-compat with future producers),
and unusable payloads each have their own counter pinned here.

The ``--json`` shape is the stable machine contract TEL-7A4X builds on, so
its keys are pinned exactly — a key change must consciously bump
``REPORT_SCHEMA_VERSION`` (and this test).

No git needed (review-stats only reads the ledger file); sterile env per the
pyc-cache learning, mirroring tests/test_governance_ledger.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"
FINAL_MODE = "final (full review, ready for push)"
CUMULATIVE_MODE = "cumulative (bundle review, ready for merge)"


def _env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLAUDE_PROJECT_DIR": str(repo),
    }


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "review-stats", *args],
        cwd=str(repo), capture_output=True, text=True, env=_env(repo), timeout=30,
    )


def _event(
    *,
    kind: str = "review.critic",
    role: str = "critic",
    model: str | None = "opus",
    mode: str = CHUNK_MODE,
    scope: str | None = "feat-a",
    duration: float | None = 100,
    findings: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "event": kind,
        "ts": "2026-06-10T12:00:00Z",
        "duration_seconds": duration,
        "project": "proj",
        "scope": scope,
        "chunk": None,
        "actor": {"role": role, "model": model},
        "git": {"head": "a" * 40, "base": "main"},
        "review": {
            "mode": mode,
            "files_reviewed": ["app.py"],
            "findings": findings or [],
            "summary": "Review.",
        },
    }


def _write_ledger(repo: Path, lines: list) -> None:
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        ln if isinstance(ln, str) else json.dumps(ln) for ln in lines
    )
    (repo / LEDGER_REL).write_text(text + "\n")


class TestMissingAndEmptyLedger:
    def test_missing_ledger_human_is_an_answer_not_an_error(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo)
        assert result.returncode == 0
        assert "no review history" in result.stdout

    def test_missing_ledger_json_emits_stable_zero_report(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "--json")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["events_total"] == 0
        assert report["overall"]["reviews"] == 0
        assert report["by_role_model_mode"] == []
        assert report["top_files"] == []

    def test_unknown_argument_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "--jsonn")
        assert result.returncode == 1
        assert "unknown argument" in result.stderr


class TestAggregationMath:
    def _mixed_ledger(self, repo: Path) -> None:
        _write_ledger(repo, [
            _event(mode=CHUNK_MODE, duration=100,
                   findings=[{"goal": "1", "severity": "note", "summary": "n"}]),
            _event(mode=FINAL_MODE, duration=200, findings=[
                {"goal": "1", "severity": "blocking", "summary": "b",
                 "files": ["lib/gates.py"]},
                {"goal": "4", "severity": "warning", "summary": "w",
                 "files": ["lib/gates.py", "docs/x.md"]},
            ]),
            _event(model="fable", mode=CUMULATIVE_MODE, scope="feat-b",
                   duration=300, findings=[
                       {"goal": "7", "severity": "warning", "summary": "w",
                        "files": ["docs/x.md"]}]),
            # A future review.pr producer (ch.05) must aggregate today —
            # the reader reports on review.*, not review.critic alone.
            _event(kind="review.pr", role="pr-reviewer", mode=CUMULATIVE_MODE,
                   scope="feat-b", duration=None,
                   findings=[{"goal": "2", "severity": "weird", "summary": "o"}]),
        ])

    def test_overall_stats(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        result = _run(repo, "--json")
        assert result.returncode == 0
        overall = json.loads(result.stdout)["overall"]
        assert overall["reviews"] == 4
        assert overall["duration_total_seconds"] == 600  # null duration excluded
        assert overall["duration_median_seconds"] == 200  # median of 100/200/300
        assert overall["findings"] == {"blocking": 1, "warning": 2, "note": 1, "other": 1}
        assert overall["findings_per_review"] == 1.25
        assert overall["actionable_rate"] == 0.5  # 2 of 4 had blocking/warning

    def test_role_model_mode_grouping(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        groups = {
            (e["role"], e["model"], e["mode"]): e
            for e in report["by_role_model_mode"]
        }
        assert set(groups) == {
            ("critic", "opus", "chunk"),
            ("critic", "opus", "final"),
            ("critic", "fable", "cumulative"),
            ("pr-reviewer", "opus", "cumulative"),
        }
        final = groups[("critic", "opus", "final")]
        assert final["reviews"] == 1
        assert final["actionable_rate"] == 1.0
        assert final["findings_per_review"] == 2.0
        pr = groups[("pr-reviewer", "opus", "cumulative")]
        assert pr["duration_median_seconds"] is None
        assert pr["duration_total_seconds"] == 0

    def test_scope_rollup(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        scopes = {e["scope"]: e for e in report["by_scope"]}
        assert set(scopes) == {"feat-a", "feat-b"}
        assert scopes["feat-a"]["reviews"] == 2
        assert scopes["feat-b"]["reviews"] == 2

    def test_top_files_ranked_by_actionable(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        # Both paths tie at 2 actionable / 2 total; the path tie-break is
        # ascending so the order is deterministic.
        assert report["top_files"] == [
            {"path": "docs/x.md", "actionable_findings": 2, "findings": 2},
            {"path": "lib/gates.py", "actionable_findings": 2, "findings": 2},
        ]
        assert report["files_attributed_total"] == 2

    def test_human_rendering_carries_the_same_numbers(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        result = _run(repo)
        assert result.returncode == 0
        assert "4 review event(s)" in result.stdout
        assert "critic / opus / final" in result.stdout
        assert "lib/gates.py: 2 actionable / 2 total" in result.stdout

    def test_pr_evidence_modes_flow_through_verbatim(self, tmp_path):
        # PR evidence `mode` values flow through the existing mode grouping
        # verbatim — no telemetry special-casing. (kernel-v3 chunk 05 note:
        # the record-audit era's pr-scoped/pr-full split is gone; today's
        # protocol emits "pr", and any unfamiliar value still passes through.)
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(kind="review.pr", role="pr", mode="pr", duration=120),
            _event(kind="review.pr", role="pr", mode="pr-custom", duration=600),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        modes = {(e["role"], e["mode"]) for e in report["by_role_model_mode"]}
        assert modes == {("pr", "pr"), ("pr", "pr-custom")}


class TestModelCanonicalization:
    """Model-id aliases for one model fold to a single family bucket so the
    reviewer-model A/B isn't fragmented across id strings; distinct families
    and unfamiliar ids stay separate, a missing model stays None (TEL-4M9X)."""

    def test_opus_aliases_fold_to_one_bucket(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(model="opus", mode=CHUNK_MODE),
            _event(model="claude-opus-4-8", mode=CHUNK_MODE),
            _event(model="claude-opus-4-8[1m]", mode=CHUNK_MODE),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        groups = {(e["role"], e["model"], e["mode"]): e for e in report["by_role_model_mode"]}
        assert set(groups) == {("critic", "opus", "chunk")}
        assert groups[("critic", "opus", "chunk")]["reviews"] == 3

    def test_distinct_families_stay_separate(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(model="claude-opus-4-8[1m]", mode=CHUNK_MODE),
            _event(model="fable", mode=CHUNK_MODE),
            _event(model="claude-sonnet-4-6", mode=CHUNK_MODE),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        models = {e["model"] for e in report["by_role_model_mode"]}
        assert models == {"opus", "fable", "sonnet"}

    def test_unfamiliar_model_passes_through_visibly(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(model="some-future-model", mode=CHUNK_MODE)])
        report = json.loads(_run(repo, "--json").stdout)
        assert {e["model"] for e in report["by_role_model_mode"]} == {"some-future-model"}

    def test_missing_model_groups_as_none(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(model=None, mode=CHUNK_MODE)])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["by_role_model_mode"][0]["model"] is None


class TestSkipCounting:
    def test_corrupt_unknown_and_invalid_each_counted(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            "{not json",                                   # corrupt: unparseable
            json.dumps(["a", "list"]),                     # corrupt: non-object
            json.dumps({"no_event_key": True}),            # corrupt: no event kind
            _event(kind="build.chunk"),                    # unknown kind (future producer)
            {**_event(), "review": {"mode": CHUNK_MODE}},  # invalid payload: no findings list
            _event(duration=50),                           # the one good event
        ])
        result = _run(repo, "--json")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["skipped"] == {
            "corrupt_lines": 3,
            "unknown_kinds": 1,
            "invalid_payloads": 1,
        }
        assert report["events_total"] == 1

    def test_skips_surface_in_human_output(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, ["{not json", _event()])
        result = _run(repo)
        assert result.returncode == 0
        assert "1 corrupt line(s)" in result.stdout


class TestJsonSchemaStability:
    """The --json shape is TEL-7A4X's contract — key changes must bump
    REPORT_SCHEMA_VERSION (and these pins) deliberately, never drift."""

    def test_top_level_keys_pinned(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        report = json.loads(_run(repo, "--json").stdout)
        assert list(report) == [
            "schema_version", "project", "generated_at", "events_total",
            "skipped", "overall", "by_role_model_mode", "by_scope",
            "top_files", "files_attributed_total",
        ]
        assert report["schema_version"] == 1
        assert report["project"] == "repo"

    def test_group_entry_keys_pinned(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            {"goal": "1", "severity": "warning", "summary": "w", "files": ["a.py"]},
        ])])
        report = json.loads(_run(repo, "--json").stdout)
        stat_keys = [
            "reviews", "duration_total_seconds", "duration_median_seconds",
            "findings", "findings_per_review", "actionable_rate",
        ]
        assert list(report["overall"]) == stat_keys
        assert list(report["by_role_model_mode"][0]) == ["role", "model", "mode", *stat_keys]
        assert list(report["by_scope"][0]) == ["scope", *stat_keys]
        assert list(report["top_files"][0]) == ["path", "actionable_findings", "findings"]
