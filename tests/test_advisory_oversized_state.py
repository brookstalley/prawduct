"""Tests for the oversized-governance-file advisory probe.

The note this replaced fired every session for months in a real product while
being **unactionable in three separate ways**, and each way is a rule here:

* it prescribed cutting content that was not in the file it measured, so every
  bullet is now gated on a content class actually present in the measured file
  (:class:`test_bullets_are_gated_on_the_measured_file`);
* it measured ``project-state.yaml`` and prescribed edits to ``build-plan.md``
  and ``change-log.md``, so the file named is now the file to edit;
* it was a bare ``print``, so a repo that had correctly decided not to compact
  could not silence it — it is an advisory now, and dismissal is what records
  that decision.

The fourth defect is the one that shapes the copy: the more faithfully a repo
recorded its reasoning, the louder the framework told it to stop. A file whose
bulk is ``technical_decisions`` is told so rather than told to cut, and the
ceiling itself is repo-configurable.

Registry isolation mirrors ``test_retired_state_probes.py`` (autouse
``clear_registry``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import core, probe_families
from lib import oversized_state_probes as osp
from lib.advisory_store import ProjectState, clear_registry, make_codebase, run_all_probes


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


#: Comfortably over the 40 KB default, and nothing the bullets look for.
_FILLER = "# nothing the advice knows how to name\n" + ("x" * 80 + "\n") * 700


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text("project: demo\n", encoding="utf-8")
    return tmp_path


def _write(tmp_path: Path, rel: str, body: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _probe(root: Path):
    return osp.probe_oversized_governance_file(ProjectState({}), make_codebase(root))


def _by_type(root: Path, type_: str):
    return next((c for c in _probe(root) if c.type == type_), None)


class TestThreshold:
    def test_a_file_under_the_threshold_is_silent(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", "project: demo\n")
        assert _probe(repo) == []

    def test_a_file_over_the_threshold_fires_once(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        fired = [c for c in _probe(repo) if c.type == "oversized-project-state"]
        assert len(fired) == 1

    def test_the_threshold_is_configurable_per_repo(self, tmp_path):
        # The defect this closes: a bare constant penalises thorough decision
        # recording, and a repo that has weighed the trade had no way to say so
        # short of living with the nag forever.
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER + "oversized_file_threshold_kb: 500\n")
        assert _by_type(repo, "oversized-project-state") is None

    def test_a_junk_threshold_falls_back_to_the_default(self, tmp_path):
        # A typo in a tuning knob must not silence the nudge, and must not make
        # every file oversized either.
        for junk in ("banana", "0", "-5", ""):
            root = tmp_path / f"r{abs(hash(junk))}"
            root.mkdir()
            repo = _repo(root)
            _write(repo, ".prawduct/project-state.yaml",
                   _FILLER + f"oversized_file_threshold_kb: {junk}\n")
            assert _by_type(repo, "oversized-project-state") is not None, junk


class TestBulletsAreGatedOnTheMeasuredFile:
    def test_a_bullet_whose_class_is_absent_is_not_printed(self, tmp_path):
        # The original defect, verbatim: all three of the old note's bullets had
        # ZERO hits in the file it measured.
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        summary = _by_type(repo, "oversized-project-state").trigger_summary
        for absent in ("deliverables", "test history", "change log"):
            assert absent not in summary, summary

    def test_a_bullet_whose_class_is_present_is_printed(self, tmp_path):
        repo = _repo(tmp_path)
        _write(
            repo,
            ".prawduct/project-state.yaml",
            _FILLER + "chunks:\n  - id: 01\n    deliverables: [a]\n    acceptance_criteria: [b]\n",
        )
        summary = _by_type(repo, "oversized-project-state").trigger_summary
        assert "`deliverables:` / `acceptance_criteria:`" in summary

    def test_test_history_and_inline_change_log_are_each_gated(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER + "  test_history:\n    - n: 1\n")
        summary = _by_type(repo, "oversized-project-state").trigger_summary
        assert "test history" in summary
        assert "inline change log" not in summary

    def test_a_file_with_nothing_nameable_says_so_rather_than_guessing(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        summary = _by_type(repo, "oversized-project-state").trigger_summary
        assert "Nothing this nudge knows how to name is in it" in summary


class TestTheFileNamedIsTheFileToEdit:
    def test_the_build_plan_is_measured_and_named_in_its_own_right(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/artifacts/build-plan.md",
               _FILLER + "\ndeliverables: one\n")
        cand = _by_type(repo, "oversized-build-plan")
        assert cand is not None
        assert ".prawduct/artifacts/build-plan.md" in cand.trigger_summary
        # ...and the oversize of the plan says nothing about project-state.yaml.
        assert _by_type(repo, "oversized-project-state") is None

    def test_each_oversized_file_is_separately_dismissable(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        _write(repo, ".prawduct/change-log.md", _FILLER)
        types = {c.type for c in _probe(repo)}
        assert types == {"oversized-project-state", "oversized-change-log"}

    def test_evidence_carries_no_size_so_an_edit_cannot_undismiss_it(self, tmp_path):
        # Evidence is hashed into the advisory id, and these files are edited by
        # the sessions that read them. A size in the evidence would mint a new id
        # on every edit, silently re-opening a decision the owner had made.
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        first = _by_type(repo, "oversized-project-state").evidence
        _write(repo, ".prawduct/project-state.yaml", _FILLER + _FILLER)
        assert _by_type(repo, "oversized-project-state").evidence == first


class TestTheChangeLogBulletIsGuarded:
    def test_a_tagged_log_is_never_told_to_delete_tagged_entries(self, tmp_path):
        # "keep the last ~10, git has the history" is unsafe wherever entries
        # carry prawduct tags: the release-pending set is every `scope=`-tagged
        # entry with no `release=`, so a deleted tagged entry drops out of that
        # derivation silently. The old note printed it unconditionally.
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/change-log.md",
               _FILLER + "\n<!-- prawduct: scope=v1.4 | release=v1.3.18 -->\n")
        summary = _by_type(repo, "oversized-change-log").trigger_summary
        assert "NEVER one carrying a" in summary
        assert "nothing here derives from them" not in summary

    def test_an_untagged_log_gets_the_plain_advice(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/change-log.md", "# Change Log\n" + _FILLER)
        summary = _by_type(repo, "oversized-change-log").trigger_summary
        assert "nothing here derives from them" in summary
        assert "NEVER one carrying a" not in summary


class TestRecordedReasoningIsNotTheThingToCut:
    def test_a_decision_heavy_file_is_told_so(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml",
               _FILLER + "technical_decisions:\n  data_model: because…\n")
        summary = _by_type(repo, "oversized-project-state").trigger_summary
        assert "that is not the thing to cut" in summary

    def test_the_owner_action_offers_keeping_it_as_a_real_answer(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        cand = _by_type(repo, "oversized-project-state")
        assert "Keeping it is a real answer" in cand.owner_action
        assert "oversized_file_threshold_kb" in cand.owner_action
        # No command for the runtime: choosing what to cut is a content judgement,
        # and the old note put its three guesses behind a literal "Run" prefix.
        assert cand.recommended_action == ""


class TestFailSoft:
    def test_a_missing_file_is_silent(self, tmp_path):
        assert _probe(_repo(tmp_path)) == []

    def test_an_undecodable_file_is_silent(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "change-log.md").write_bytes(b"\xff\xfe" + b"\x00" * 60000)
        assert _by_type(repo, "oversized-change-log") is None


class TestRegistration:
    def test_one_registration_emits_every_type_exactly_once(self, tmp_path):
        # Registering the same function once per measured file would run it N
        # times and emit N copies of every candidate; the types are what keep the
        # advisories separately dismissable, not the registrations.
        repo = _repo(tmp_path)
        _write(repo, ".prawduct/project-state.yaml", _FILLER)
        _write(repo, ".prawduct/change-log.md", _FILLER)
        osp.register()
        produced = [
            c for c in run_all_probes(ProjectState({}), make_codebase(repo))
            if c.type.startswith("oversized-")
        ]
        assert sorted(c.type for c in produced) == [
            "oversized-change-log", "oversized-project-state",
        ]
        assert all(c.feature == "governance" for c in produced)

    def test_the_composition_root_registers_it(self, tmp_path):
        from lib import advisory_store

        probe_families.register_all()
        assert f"{osp.FEATURE}:{osp.PROBE_TYPE}" in advisory_store._REGISTRY


def test_the_default_threshold_is_the_constant_the_old_note_used():
    # 40000 bytes, unchanged: an unconfigured repo must see exactly the threshold
    # it always did, or this refactor moves a nag it was only meant to make
    # tunable.
    assert core.OVERSIZED_FILE_KB * 1000 == 40000
