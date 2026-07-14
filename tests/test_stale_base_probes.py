"""Tests for the stale-remote-base detection + advisory probe (COV-7K4N).

Two surfaces share one detector, so both are tested here:

* ``coverage.diagnose_stale_remote_base`` — the pure git-inspection helper the
  gate hint and the probe both call. It returns a dict ONLY when ``origin/<b>``
  trails a local ``<b>`` that exists; every other shape (remote current, base
  not a remote ref, local branch absent) returns ``None``, never raises.
* ``stale_base_probes.probe_unpromoted_release_prep`` — fires only on the
  *release-prep-qualified* stale base (the phantom release), stays inert for an
  ordinary unpushed commit, and **self-resolves** once the branch is pushed
  (the same observable state that triggers it). Registry isolation mirrors
  ``test_gitignore_probes.py`` (autouse ``clear_registry``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import coverage
from lib import stale_base_probes as sbp
from lib.advisory_store import (
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


# ---------------------------------------------------------------------------
# Repo builder — origin/main trails local main (the phantom-release shape)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _repo(
    tmp_path: Path,
    *,
    with_origin: bool = True,
    ahead: str = "release-prep",  # "release-prep" | "ordinary" | "none"
    push_after: bool = False,
    feature_on_local: bool = True,
) -> Path:
    """Build a repo in the COV-7K4N shape (see module docstring)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    if with_origin:
        origin = tmp_path / "origin.git"
        subprocess.run(
            ["git", "init", "--bare", "-q", str(origin)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        _git(repo, "remote", "add", "origin", str(origin))
        _git(repo, "push", "-q", "origin", "main")  # origin/main == c1
    if ahead == "release-prep":
        _commit(repo, "VERSION", "1.0.1\n", "release-prep(v1.0.1): bump version")
    elif ahead == "ordinary":
        _commit(repo, "more.py", "y = 1\n", "feat: ordinary work")
    if push_after and with_origin:
        _git(repo, "push", "-q", "origin", "main")
    if feature_on_local:
        _git(repo, "checkout", "-q", "-b", "feature")
    else:
        _git(repo, "checkout", "-q", "-b", "feature", "origin/main")
    _commit(repo, "feature.py", "z = 2\n", "f1")
    return repo


# ---------------------------------------------------------------------------
# diagnose_stale_remote_base — the shared detector
# ---------------------------------------------------------------------------


class TestDiagnoseStaleRemoteBase:
    def test_dict_when_origin_behind_local_with_release_prep(self, tmp_path):
        repo = _repo(tmp_path)
        diag = coverage.diagnose_stale_remote_base(repo, "origin/main")
        assert diag is not None
        assert diag["local"] == "main"
        assert diag["remote"] == "origin/main"
        assert diag["commits_ahead"] == 1
        assert diag["ancestor_of_head"] is True
        assert diag["release_prep_subject"].startswith("release-prep(v1.0.1)")

    def test_none_when_remote_up_to_date(self, tmp_path):
        repo = _repo(tmp_path, push_after=True)
        assert coverage.diagnose_stale_remote_base(repo, "origin/main") is None

    def test_none_when_base_is_not_a_remote_ref(self, tmp_path):
        repo = _repo(tmp_path)
        assert coverage.diagnose_stale_remote_base(repo, "main") is None

    def test_none_when_local_branch_absent(self, tmp_path):
        repo = _repo(tmp_path)
        # origin/<b> shape, but there is no local branch of that name.
        assert coverage.diagnose_stale_remote_base(repo, "origin/nope") is None

    def test_ancestor_false_when_local_diverged_from_head(self, tmp_path):
        repo = _repo(tmp_path, feature_on_local=False)
        diag = coverage.diagnose_stale_remote_base(repo, "origin/main")
        assert diag is not None
        assert diag["commits_ahead"] == 1
        assert diag["ancestor_of_head"] is False  # pushing wouldn't move merge-base

    def test_release_prep_subject_none_for_ordinary_ahead(self, tmp_path):
        # Ahead by a non-release-prep commit → dict still returned, but the
        # phantom-release signal is absent (the gate hint still fires on the
        # ancestor relation; the advisory does not).
        repo = _repo(tmp_path, ahead="ordinary")
        diag = coverage.diagnose_stale_remote_base(repo, "origin/main")
        assert diag is not None
        assert diag["commits_ahead"] == 1
        assert diag["release_prep_subject"] is None


# ---------------------------------------------------------------------------
# The advisory probe — fires on the phantom release, self-resolves on push
# ---------------------------------------------------------------------------


class TestProbe:
    def test_fires_on_unpushed_release_prep(self, tmp_path):
        repo = _repo(tmp_path)
        out = sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo))
        assert len(out) == 1
        cand = out[0]
        assert cand.type == "unpromoted-release-prep"
        assert cand.recommended_action == "git push origin main"
        assert cand.priority == "warn"
        assert "release-prep(v1.0.1" in cand.trigger_summary
        assert "1 commit ahead" in cand.trigger_summary

    def test_inert_after_push_self_resolves(self, tmp_path):
        # The push that fixes the base also clears the trigger: probe returns []
        # → reconcile flips the advisory to resolved on the next sync.
        repo = _repo(tmp_path, push_after=True)
        assert sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo)) == []

    def test_inert_when_ahead_without_release_prep(self, tmp_path):
        # Ordinary unpushed work is normal development — no nag.
        repo = _repo(tmp_path, ahead="ordinary")
        assert sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo)) == []

    def test_inert_when_no_remote(self, tmp_path):
        # No origin at all → base resolves to bare local `main`, not origin/<b>.
        repo = _repo(tmp_path, with_origin=False)
        assert sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo)) == []

    def test_evidence_is_version_independent(self, tmp_path):
        # Evidence is hashed into the advisory id: stacking a second release-prep
        # before the push must NOT churn the id, so evidence stays identical
        # while the summary tracks the live count/version.
        repo = _repo(tmp_path)
        one = sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo))
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "VERSION", "1.0.2\n", "release-prep(v1.0.2): another bump")
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "rebase", "-q", "main")
        two = sbp.probe_unpromoted_release_prep(ProjectState({}), make_codebase(repo))
        assert one[0].evidence == two[0].evidence
        assert "1 commit ahead" in one[0].trigger_summary
        assert "2 commits ahead" in two[0].trigger_summary

    def test_register_runs_in_the_roster(self, tmp_path):
        repo = _repo(tmp_path)
        sbp.register()
        sbp.register()  # idempotent — register_probe overwrites
        cands = run_all_probes(ProjectState({}), make_codebase(repo))
        fired = [c for c in cands if c.type == "unpromoted-release-prep"]
        assert len(fired) == 1
        assert fired[0].feature == "stale-base"
        assert fired[0].probe_version == sbp.PROBE_VERSION
