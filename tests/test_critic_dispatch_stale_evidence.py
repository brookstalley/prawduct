"""`critic-begin --mode verify-resolutions` refuses on stale or red saved test
evidence (#724), before it derives anything.

A verify-resolutions round rates new findings from the inner BLOCKING set only,
so a stale suite that step 5 of the skill turns into a finding costs a whole
round (median ~300s) to report what `prawduct-hook test-status` already knows
for free. The dispatch now asks `gates.tests_are_current` first and refuses
with exit 7 — the remedy is the same mode, re-dispatched after the suite runs.

Absent evidence does NOT refuse: a product with no suite has no evidence file
and no `test-run` facts, and refusing there would leave verify-resolutions —
the only command that clears a BLOCKING finding — permanently behind
`--force`. Step 5's post-dispatch check still handles that case.

Exit 7, not 5: `api-contract.md`'s Error Model records 5 as withdrawn (#167
held it on `develop` until its revert), "left unclaimed rather than given a new
meaning". The value is pinned as a literal because it is a contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from test_critic_consolidate import (
    MARKER_REL,
    PARTIALS_REL,
    _commit_file,
    _git,
    _init_repo,
    _run_begin,
    _seed_prior_review_with_blocker,
    _store_facts,
)
from test_cumulative_gate import _write_test_evidence

from lib import critic_consolidate, evidence, gates, record_progress

STALE_EVIDENCE_EXIT = 7
GUARD = "critic-dispatch-stale-evidence"


def _repo_owing_a_verify(tmp_path: Path) -> Path:
    """One consolidated review with a blocking finding (the cache names it),
    and an uncommitted fix — the state a verify-resolutions pass is for."""
    repo = tmp_path / "r"
    _init_repo(repo)
    head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
    head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    (repo / ".prawduct").mkdir(exist_ok=True)
    _seed_prior_review_with_blocker(repo, head, head_tree=head_tree, head_commit=head)
    (repo / "src/app.py").write_text("x = 2  # the fix\n")
    return repo


def _stale_guard_facts(repo: Path) -> list[dict]:
    return [f for f in _store_facts(repo, "guard-refusal") if (f.get("body") or {}).get("guard") == GUARD]


def _assert_refused_before_dispatch(repo: Path, result, verdict_reason: str) -> None:
    assert result.returncode == STALE_EVIDENCE_EXIT, (
        f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # Verbatim, so the reason here cannot drift from what `test-status` says.
    assert verdict_reason and verdict_reason in result.stdout, result.stdout
    assert not (repo / PARTIALS_REL / "manifest.json").exists()
    assert not (repo / MARKER_REL).exists()
    # The remedy re-dispatches the SAME mode — never a demotion.
    assert "verify-resolutions" in result.stdout


def _verdict(repo: Path) -> str:
    current, reason, _clause = gates.tests_are_current(repo)
    assert not current, f"fixture is not stale: {reason}"
    return reason


class TestRefusesOnStaleEvidence:
    def test_a_red_saved_run_refuses(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo, failed=2)
        reason = _verdict(repo)
        assert "failing" in reason

        result = _run_begin(repo, "--mode", "verify-resolutions")

        _assert_refused_before_dispatch(repo, result, reason)

    def test_a_degraded_saved_run_refuses(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo, degraded="contended run, 3 workers lost")
        reason = _verdict(repo)
        assert "degraded" in reason

        result = _run_begin(repo, "--mode", "verify-resolutions")

        _assert_refused_before_dispatch(repo, result, reason)

    def test_a_run_on_another_tree_predating_the_session_refuses(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        # The run met the tree BEFORE the fix, and the session began after it.
        _write_test_evidence(repo, tree=_git(repo, "rev-parse", "HEAD^{tree}").stdout.strip())
        (repo / ".prawduct" / ".session-start").write_text("2026-08-14T00:00:00Z")
        reason = _verdict(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        _assert_refused_before_dispatch(repo, result, reason)

    def test_a_red_store_run_with_no_local_record_refuses(self, tmp_path):
        """"Evidence exists" counts the clone's shared store too: a fresh
        worktree has no record of its own, and a red run that met this tree
        elsewhere is still this tree's newest word."""
        repo = _repo_owing_a_verify(tmp_path)
        tree = evidence.capture_tree(repo)["tree"]
        appended = evidence.append_test_run(repo, {
            "tree": tree, "passed": 3, "failed": 1, "skipped": 0,
            "duration_seconds": 1, "source": "run",
        })
        assert appended["status"] == "appended", appended
        assert not (repo / ".prawduct" / ".test-evidence.json").exists()
        reason = _verdict(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        _assert_refused_before_dispatch(repo, result, reason)

    def test_the_slug_set_names_every_state_the_owner_returns(self):
        assert set(critic_consolidate.STALE_EVIDENCE_REASONS) == set(gates.SUITE_STATES)

    @pytest.mark.parametrize(("evidence_kwargs", "slug"), [
        ({"failed": 1}, "failing"),
        ({"degraded": "contended"}, "degraded"),
        ({"tree": "0" * 40}, "not-current"),
    ])
    def test_a_refusal_records_exactly_one_guard_fact(self, tmp_path, evidence_kwargs, slug):
        """`reason` is the sink's slug — `stats` groups firings on it, so prose
        there would make every firing its own bucket. The verdict's prose rides
        beside it as `verdict`."""
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo, **evidence_kwargs)
        verdict = _verdict(repo)

        assert _run_begin(repo, "--mode", "verify-resolutions").returncode == STALE_EVIDENCE_EXIT

        facts = _stale_guard_facts(repo)
        assert len(facts) == 1, facts
        body = facts[0]["body"]
        assert body["mode"] == "verify-resolutions"
        assert body["reason"] == slug
        assert body["verdict"] == verdict
        assert body["branch"] == "main"
        assert "refused_fields" not in body


def _in_progress_record(repo: Path, pid: int) -> None:
    """A void the recorder leaves while its run is going, naming `pid`."""
    record_progress.forget()
    _write_test_evidence(repo, degraded="record attempt did not complete", omit_tree=True)
    path = repo / ".prawduct" / ".test-evidence.json"
    record = json.loads(path.read_text())
    record["void"] = "record attempt did not complete"
    record["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["in_progress"] = record_progress.stamp("pytest", record["timestamp"]) | {"pid": pid}
    path.write_text(json.dumps(record))


class TestTheRemedyFollowsTheRecordsState:
    """R-4: the exit-7 text printed its own 'Run the declared suite' after a
    verdict that said a run was already going, so an obedient agent started a
    second suite on top of the first."""

    def test_a_run_in_progress_is_told_to_wait_not_to_run_the_suite(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        _in_progress_record(repo, os.getpid())  # this test process: alive
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == STALE_EVIDENCE_EXIT, result.stdout + result.stderr
        assert "test-status --wait" in result.stdout, result.stdout
        assert "Run the declared suite" not in result.stdout, result.stdout
        assert "run the suite and record it" not in result.stdout.lower(), result.stdout
        assert _stale_guard_facts(repo)[0]["body"]["reason"] == "running"

    def test_an_interrupted_run_is_told_to_run_the_suite(self, tmp_path):
        """The control: same refusal, recorder gone, so the remedy is a run."""
        repo = _repo_owing_a_verify(tmp_path)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        _in_progress_record(repo, dead.pid)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == STALE_EVIDENCE_EXIT, result.stdout + result.stderr
        assert "test-evidence record" in result.stdout, result.stdout
        assert "test-status --wait" not in result.stdout, result.stdout
        assert _stale_guard_facts(repo)[0]["body"]["reason"] == "interrupted"


class TestProceedsWhereItMust:
    def test_no_evidence_at_all_does_not_refuse(self, tmp_path):
        """A product with no suite: no record, no `test-run` fact."""
        repo = _repo_owing_a_verify(tmp_path)
        assert not (repo / ".prawduct" / ".test-evidence.json").exists()
        assert _store_facts(repo, "test-run") == []

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (repo / PARTIALS_REL / "manifest.json").exists()
        assert _stale_guard_facts(repo) == []

    def test_current_evidence_dispatches(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo)  # met the working tree, fix included
        current, reason, _ = gates.tests_are_current(repo)
        assert current, reason

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (repo / PARTIALS_REL / "manifest.json").exists()

    def test_force_dispatches_over_stale_evidence(self, tmp_path):
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo, failed=2)
        _verdict(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions", "--force")

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (repo / PARTIALS_REL / "manifest.json").exists()
        assert (repo / MARKER_REL).exists()
        assert _stale_guard_facts(repo) == []

    def test_a_live_review_refuses_as_in_flight_not_as_stale(self, tmp_path):
        """Placement: the in-flight guard answers first."""
        repo = _repo_owing_a_verify(tmp_path)
        _write_test_evidence(repo, failed=2)
        # Live: inside the marker's TTL, so the guard reads a running review.
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (repo / MARKER_REL).write_text(json.dumps({"started_at": now}))

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 1, result.stdout
        assert "already in flight" in result.stderr, result.stderr
        assert _stale_guard_facts(repo) == []

    @pytest.mark.parametrize("mode", ["chunk", "final", "cumulative"])
    def test_other_modes_behave_as_without_evidence(self, tmp_path, mode):
        """Only verify-resolutions promotes a stale suite to a round-costing
        BLOCKING finding, so only it refuses. Each mode's outcome on red
        evidence is compared with its outcome on none — the dispatch it would
        have made today."""
        outcomes = {}
        for label, red in (("none", False), ("red", True)):
            repo = _repo_owing_a_verify(tmp_path / label)
            if red:
                _write_test_evidence(repo, failed=2)
            outcomes[label] = _run_begin(repo, "--mode", mode).returncode
            assert _stale_guard_facts(repo) == []
        assert outcomes["red"] == outcomes["none"], outcomes
        assert outcomes["red"] != STALE_EVIDENCE_EXIT
