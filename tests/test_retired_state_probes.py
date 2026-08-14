"""Tests for the retired-`test_tracking` advisory probe.

**Why this probe exists at all**, since that is what its tests have to protect:
the block is removable through `/prawduct:doctor` and through the plugin
cutover, and *both need someone to decide to run them*. Nothing told them there
was anything to run. Nine repos still carried it after the removal shipped, and
their correct route differed per repo.

The harm the probe addresses is **behavioural, not spatial**. An agent that
meets a stale count in a product's source of truth is obliged to correct it, and
each correction is a commit that buys a review round. So the advisory's job is
done the moment an agent reads *"retired — do not maintain this"* at session
start, whether or not the repair is ever run. That is why
:func:`test_the_summary_leads_with_the_instruction_not_the_diagnosis` asserts on
the shape of the message rather than merely on the fact that one appeared.

Registry isolation mirrors `test_gitattributes_probes.py` (autouse
`clear_registry`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import lifecycle_repair, probe_families
from lib import retired_state_probes as rsp
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


WITH_BLOCK = """\
project: demo

build_state:
  source_root: "src/"

  test_tracking:
    test_count: 1724
    assertion_count: 4102
    history:
      - tests_added: 24
        date: 2026-08-14

  spec_compliance: partial
"""

WITHOUT_BLOCK = """\
project: demo

build_state:
  source_root: "src/"
  spec_compliance: partial
"""


def _repo(tmp_path: Path, state: str | None = WITH_BLOCK) -> Path:
    (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
    if state is not None:
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            state, encoding="utf-8"
        )
    return tmp_path


def _probe(repo: Path):
    return rsp.probe_retired_test_tracking(ProjectState({}), make_codebase(repo))


# ---------------------------------------------------------------------------
# Firing and not firing
# ---------------------------------------------------------------------------


class TestWhenItFires:
    def test_fires_once_on_a_repo_carrying_the_block(self, tmp_path: Path) -> None:
        found = _probe(_repo(tmp_path))
        assert len(found) == 1
        assert found[0].type == rsp.PROBE_TYPE

    def test_silent_on_a_repo_without_it(self, tmp_path: Path) -> None:
        assert _probe(_repo(tmp_path, WITHOUT_BLOCK)) == []

    def test_silent_when_only_the_INERT_retired_keys_are_present(
        self, tmp_path: Path
    ) -> None:
        """`views_enabled` and `scope_rollups` are deliberately out of scope.

        Nobody maintains them, so they carry no behavioural cost, and doctor's
        health check already covers their cleanup. Nagging every session about
        inert residue is precisely the control `nonfunctional-requirements.md`
        § Direction says to remove — so this probe must not fire on them, and
        that exclusion is pinned rather than left to the delegation's shape.
        """
        state = (
            "project: demo\n\n"
            "views_enabled: true\n\n"
            "scope_rollups:\n"
            "  alpha:\n"
            '    chunks: ["01"]\n'
        )
        assert _probe(_repo(tmp_path, state)) == []

    def test_silent_on_a_test_tracking_under_a_foreign_parent(
        self, tmp_path: Path
    ) -> None:
        """Inherited from `lifecycle_repair`'s enclosing-parent rule.

        Pinned here anyway: if the delegation were ever replaced by a looser
        substring match, this repo would start being nagged about a key that is
        not the one under discussion, and nothing else would notice.
        """
        state = (
            "project: demo\n"
            "vendor_metrics:\n"
            "  test_tracking:\n"
            "    test_count: 9\n"
            "build_state:\n"
            '  source_root: "src/"\n'
        )
        assert _probe(_repo(tmp_path, state)) == []


class TestWhenItCannotAnswer:
    """Fail soft — raise no advisory — but do not fail SILENT.

    The *advice* half of `architecture.md` § Direction's
    authority-fails-closed / advice-fails-soft split: nagging a repo whose state
    file could not be read would be a confident claim about something unread, so
    no advisory is raised. The three inputs are not one answer, though. An
    ABSENT state file genuinely has nothing to report and says nothing; a file
    that EXISTS and could not be read is a different answer, and saying nothing
    there is indistinguishable from a clean repo.
    """

    def test_no_state_file(self, tmp_path: Path) -> None:
        assert _probe(_repo(tmp_path, state=None)) == []

    def test_no_prawduct_dir_at_all(self, tmp_path: Path) -> None:
        assert _probe(tmp_path) == []

    def test_undecodable_state_file(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, WITH_BLOCK)
        (repo / ".prawduct" / "project-state.yaml").write_bytes(b"\xff\xfe\x80 bad")
        assert _probe(repo) == []

    def test_an_unreadable_state_file_is_SAID_not_merely_survived(
        self, tmp_path: Path, capsys
    ) -> None:
        """Fail soft, never fail silent — the sibling probes' contract.

        Verified rather than assumed that this is needed: nothing else at
        session start reports an undecodable `project-state.yaml`. Every reader
        fails soft to a default, and `core.read_str_yaml_key` — the last one that
        raised — was deliberately made fail-soft so an unreadable state file
        could not abort a cutover. A session start over a corrupted state file
        prints nothing, so without this line the repo whose source of truth is
        unreadable gets no signal at all.
        """
        repo = _repo(tmp_path, WITH_BLOCK)
        (repo / ".prawduct" / "project-state.yaml").write_bytes(b"\xff\xfe\x80 bad")

        assert _probe(repo) == []

        said = capsys.readouterr()
        assert "could not be read" in (said.out + said.err), (
            "an unreadable state file was skipped silently"
        )


# ---------------------------------------------------------------------------
# The message, and the identity
# ---------------------------------------------------------------------------


class TestTheMessage:
    def test_the_summary_leads_with_the_instruction_not_the_diagnosis(
        self, tmp_path: Path
    ) -> None:
        """The behavioural half is the whole point.

        An advisory that only says "you have a retired key" leaves the agent
        free to keep correcting the number until someone runs the repair. The
        instruction not to maintain it is what stops the bleeding on the first
        session, so it leads.
        """
        summary = _probe(_repo(tmp_path))[0].trigger_summary.lower()
        assert "retired" in summary
        assert "maintain" in summary, "the don't-maintain instruction is missing"

    def test_it_names_where_the_real_number_lives(self, tmp_path: Path) -> None:
        """An operator told to drop a count needs to know what to read instead."""
        candidate = _probe(_repo(tmp_path))[0]
        blob = f"{candidate.trigger_summary} {candidate.recommended_action}".lower()
        assert "evidence" in blob or "test-status" in blob

    def test_it_offers_both_routes(self, tmp_path: Path) -> None:
        """Four of the nine repos measured needed `migrate`, not `doctor`.

        A single recommended command would send more than half of them to a
        path that early-returns on their repo and changes nothing — which reads
        as the feature being broken.
        """
        candidate = _probe(_repo(tmp_path))[0]
        routes = " ".join(
            (candidate.recommended_action, *candidate.alternative_actions)
        ).lower()
        assert "doctor" in routes or "lifecycle-repair" in routes
        assert "migrate" in routes


class TestTheIdentityIsStable:
    def test_evidence_does_not_move_when_the_block_changes(
        self, tmp_path: Path
    ) -> None:
        """The advisory id hashes the evidence.

        These state files are edited by their own sessions — one shrank by 52 KB
        mid-measurement while this feature was being built. If the evidence
        carried a count or a byte size, the id would move on every such edit and
        a dismissal would silently stop applying.
        """
        small = _probe(_repo(tmp_path))[0]

        other = Path(str(tmp_path) + "-2")
        bigger = WITH_BLOCK.replace(
            "test_count: 1724", "test_count: 27414  # " + ("x" * 5_000)
        )
        second = _probe(_repo(other, bigger))[0]

        assert small.evidence == second.evidence


# ---------------------------------------------------------------------------
# Reachability — a probe nobody registered is a probe that never runs
# ---------------------------------------------------------------------------


class TestItIsActuallyWired:
    def test_the_production_roster_runs_it(self, tmp_path: Path) -> None:
        """Registered at the composition root, not merely importable.

        The failure this catches is silent by construction: a correct probe that
        `register_all` never mentions produces no advisory and no error, and
        looks exactly like a repo with nothing to report.
        """
        probe_families.register_all()
        found = run_all_probes(ProjectState({}), make_codebase(_repo(tmp_path)))
        assert any(c.type == rsp.PROBE_TYPE for c in found), (
            "the probe is not reachable through register_all()"
        )

    def test_the_roster_stays_quiet_on_a_clean_repo(self, tmp_path: Path) -> None:
        probe_families.register_all()
        found = run_all_probes(
            ProjectState({}), make_codebase(_repo(tmp_path, WITHOUT_BLOCK))
        )
        assert not [c for c in found if c.type == rsp.PROBE_TYPE]


class TestItSelfResolves:
    def test_running_the_repair_clears_it(self, tmp_path: Path) -> None:
        """Trigger and resolution are one observable state.

        The advisory system auto-resolves a probe that stops matching, so this
        is what makes the nudge disappear on its own rather than needing a
        dismissal — and it is asserted end-to-end through the real repair rather
        than by editing the fixture to look fixed.
        """
        repo = _repo(tmp_path)
        assert len(_probe(repo)) == 1

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))

        assert _probe(repo) == [], "the advisory survived its own remedy"
