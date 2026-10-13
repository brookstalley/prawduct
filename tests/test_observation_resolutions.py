"""A verify pass can confirm an observation fix.

An observation is what an inner-stage review demoted below BLOCKING. A builder
who fixes one in judgeable code buys a `verify-resolutions` round for it, and
until this existed that round could record nothing: a resolution could only
target a finding. So the round counted as "empty" in `stats` (it confirmed no
resolution and raised nothing), and the census showed the fixed observation as
accepted or never answered. Measured on sibling repos on 3.7.x, about a fifth
of verify rounds had nothing but observations to check.

The resolution names the observation's `O-n` id in the `finding.fid` slot, the
slot a disposition already uses for one. `R-n` and `O-n` never collide, so no
gate changes: gates read only blocking findings.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib import coverage_algebra, dispositions, evidence, stats
from test_critic_consolidate import (
    PARTIALS_REL,
    _commit_file,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)

OBSERVATION = {"name": "Name the constant", "goal": "Everything Is Coherent",
               "recommendation": "Give the magic number a name"}


def _review_with_observation(tmp_path: Path) -> tuple[Path, str]:
    """A chunk review that raised one observation and nothing else; returns the
    repo and that review's id. The builder then fixes it in judgeable code."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    (repo / "src/app.py").write_text("x = 2\n")
    begin = _run_begin(repo, "--mode", "chunk")
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], observations=[OBSERVATION])
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    (repo / "src/app.py").write_text("SCALE = 2\nx = SCALE  # the observation, fixed\n")
    return repo, manifest["id"]


def _verify(repo: Path, resolutions: list) -> tuple[int, str, str]:
    begin = _run_begin(repo, "--mode", "verify-resolutions")
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], resolutions=resolutions)
    done = _run_consolidate(repo)
    return done.returncode, done.stderr, manifest["id"]


def _store(repo: Path) -> dict:
    return evidence.read_facts(repo)


class TestARoundThatConfirmsAnObservationFix:
    def test_it_records_a_resolution_on_the_observation(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        rc, err, verify_id = _verify(
            repo, [{"review_id": rid, "fid": "O-1", "disposition": "fixed"}]
        )
        assert rc == 0, err
        facts = evidence.facts_of_kind(_store(repo), "resolution")
        assert [f["body"]["finding"] for f in facts] == [{"review_id": rid, "fid": "O-1"}]
        assert facts[0]["body"]["verified_by"] == verify_id

    def test_the_census_shows_the_observation_fixed(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [{"review_id": rid, "fid": "O-1", "disposition": "fixed"}])
        assert rc == 0, err
        report = dispositions.census(_store(repo), review_id=rid)
        assert [o["state"] for o in report["reviews"][0]["observations"]] == ["fixed"]

    def test_the_census_shows_it_noted_without_one(self, tmp_path):
        """Control: the same fix, verified by a round that records nothing."""
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [])
        assert rc == 0, err
        report = dispositions.census(_store(repo), review_id=rid)
        assert [o["state"] for o in report["reviews"][0]["observations"]] == ["noted"]

    def test_stats_no_longer_counts_the_round_empty(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [{"review_id": rid, "fid": "O-1", "disposition": "fixed"}])
        assert rc == 0, err
        (bucket,) = stats.aggregate(_store(repo)["facts"]).values()
        assert bucket["verify_rounds"] == {"total": 1, "empty": 0}

    def test_stats_counts_a_round_that_confirmed_nothing_empty(self, tmp_path):
        """Control: without the resolution the same round is empty."""
        repo, _rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [])
        assert rc == 0, err
        (bucket,) = stats.aggregate(_store(repo)["facts"]).values()
        assert bucket["verify_rounds"] == {"total": 1, "empty": 1}

    def test_no_gate_reads_it(self, tmp_path):
        """The resolution lands in the gate's index under an `O-n` key that no
        blocking finding carries, so the blocking set it filters is unchanged."""
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [{"review_id": rid, "fid": "O-1", "disposition": "fixed"}])
        assert rc == 0, err
        store = _store(repo)
        resolved = coverage_algebra.resolution_index(store["facts"])
        review = next(f for f in evidence.facts_of_kind(store, "review") if f["id"] == rid)
        assert coverage_algebra.unresolved_blocking(review, resolved) == []
        assert not any(fid.startswith("R-") for _r, fid in resolved)


class TestRefusals:
    def test_an_observation_cannot_be_waived(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [{"review_id": rid, "fid": "O-1", "disposition": "waived",
                                     "rationale": "not worth it"}])
        assert rc == 1
        assert "only verdict that records anything is 'fixed'" in err
        assert evidence.facts_of_kind(_store(repo), "resolution") == []

    def test_an_unknown_observation_is_refused(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        rc, err, _ = _verify(repo, [{"review_id": rid, "fid": "O-9", "disposition": "fixed"}])
        assert rc == 1
        assert "recorded finding or observation" in err
        assert evidence.facts_of_kind(_store(repo), "resolution") == []


def _verify_with_observations(repo: Path, observations: list):
    begin = _run_begin(repo, "--mode", "verify-resolutions")
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], observations=observations)
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    fact = next(f for f in evidence.facts_of_kind(_store(repo), "review") if f["id"] == manifest["id"])
    next_action = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
    return fact["body"].get("observations") or [], done.stderr, next_action


class TestAVerifyPassObservesOnlyNamedFixes:
    """A verify pass's observation about anything but a named fix is what the
    builder fixes next, which buys the next verify round. So in that mode an
    observation must say, in `about`, whose fix it judges; one that names none
    is dropped from the record (advice: never refused)."""

    TIGHTER_PROSE = {"name": "Tighten the docstring", "goal": "Everything Is Coherent",
                     "recommendation": "Say it in fewer words"}

    def test_one_that_names_the_fix_it_judges_is_kept(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        judged = {**self.TIGHTER_PROSE, "name": "The constant is named but not used twice",
                  "about": {"review_id": rid, "fid": "O-1"}}
        kept, err, line = _verify_with_observations(repo, [judged])
        assert [o["about"] for o in kept] == [{"review_id": rid, "fid": "O-1"}]
        assert "dropped" not in err
        assert "1 observation(s)" in line

    def test_one_that_names_no_fix_is_dropped_and_counted(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        judged = {**self.TIGHTER_PROSE, "name": "Judged", "about": {"review_id": rid, "fid": "O-1"}}
        kept, err, line = _verify_with_observations(repo, [self.TIGHTER_PROSE, judged])
        assert [o["title"] for o in kept] == ["Judged"]
        assert "dropped 1 observation(s) that judge no named fix" in err
        assert "1 observation(s)" in line

    def test_one_naming_an_unrecorded_target_is_dropped(self, tmp_path):
        repo, rid = _review_with_observation(tmp_path)
        stray = {**self.TIGHTER_PROSE, "about": {"review_id": rid, "fid": "R-7"}}
        kept, err, line = _verify_with_observations(repo, [stray])
        assert kept == []
        assert "dropped 1 observation(s)" in err
        assert "observation(s)" not in line

    def test_a_chunk_review_keeps_observations_without_about(self, tmp_path):
        """Control: the scoping is verify-only. The chunk review in the fixture
        recorded its observation with no `about`."""
        repo, rid = _review_with_observation(tmp_path)
        review = next(f for f in evidence.facts_of_kind(_store(repo), "review") if f["id"] == rid)
        assert [o["oid"] for o in review["body"]["observations"]] == ["O-1"]
        assert "about" not in review["body"]["observations"][0]
