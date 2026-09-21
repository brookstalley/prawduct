"""CLI coverage for ``lifecycle-repair`` and ``plan-backfill``.

The ``lib/`` behaviour is covered by ``test_lifecycle_repair.py`` and
``test_plan_backfill.py``. This file covers the **wrapper**, which is where three
things live that no library test can see:

* the exit-code split — a dry run is an advisory report (a finding is not a
  failure), ``--apply`` is a state-mutating writer;
* the hand-rolled ``--date`` scan, whose usage errors must be exit 2 rather than
  a silently-defaulted date, because the date is the record;
* the ``--json`` object shape, which is a **live contract, not an internal
  detail**: ``skills/doctor/SKILL.md`` Health Check #15 grades a repo degraded on
  ``retired_flag`` being ``present``, and #16 reads ``plans_to_review``. Nothing
  else pins those key names, so a rename would break doctor silently with the
  whole suite green — the exact class of failure this repo keeps paying for.

Subprocess against the real hook, mirroring ``TestArchivePlanCommand``: the
dispatch table and the argument scan are only exercised by actually invoking it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"

STATE_WITH_FLAG = """\
project: demo

# =============================================================================
# DERIVED VIEWS
# =============================================================================
# When true, the Status block is a derived view.

views_enabled: true

coverage_required: false
"""

PLAN_WITH_INSTRUCTION = """\
---
artifact: build-plan
scope: demo
---

## Status

<!-- Derived view (`views_enabled: true`). Do not hand-edit. -->

- [x] Chunk 01: done
- [ ] Chunk 02: pending

## Build Chunks
"""

#: The same plan with every box ticked. Two commands read this fixture and want
#: opposite things from it: `lifecycle-repair` reports plans with unticked
#: chunks, so ITS fixture must have one, while `plan-backfill` refuses them
#: since #634, so its fixture must not. Ticking the shared one silently stopped
#: `test_json_plans_to_review_names_the_unticked_chunk` from having anything to
#: find — it still passed its own assertions until one of them counted. Checkbox
#: policy itself is pinned in `test_plan_backfill.py`, not here.
PLAN_COMPLETE = PLAN_WITH_INSTRUCTION.replace(
    "- [ ] Chunk 02: pending", "- [x] Chunk 02: done"
)


CHANGE_LOG = """\
# Change Log

## 2026-08-01: shipped demo
<!-- prawduct: scope=demo | release=v1.2.0 -->
"""


def _repo(
    tmp_path: Path,
    *,
    state: str = STATE_WITH_FLAG,
    change_log: str = CHANGE_LOG,
    plan: str = PLAN_WITH_INSTRUCTION,
) -> Path:
    prawduct = tmp_path / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(state, encoding="utf-8")
    (prawduct / "change-log.md").write_text(change_log, encoding="utf-8")
    (prawduct / "artifacts" / "build-plan-demo.md").write_text(
        plan, encoding="utf-8"
    )
    return tmp_path


def _run(project: Path, command: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH), command, *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class TestLifecycleRepairCommand:
    def test_dry_run_reports_and_writes_nothing(self, tmp_path: Path) -> None:
        project = _repo(tmp_path)
        before = _tree(project)
        proc = _run(project, "lifecycle-repair")

        assert proc.returncode == 0, proc.stderr
        assert "would change" in proc.stdout
        assert _tree(project) == before, "a dry run must leave the tree byte-identical"

    def test_apply_writes_and_exits_zero(self, tmp_path: Path) -> None:
        project = _repo(tmp_path)
        proc = _run(project, "lifecycle-repair", "--apply")

        assert proc.returncode == 0, proc.stderr
        assert "views_enabled" not in (project / ".prawduct" / "project-state.yaml").read_text()

    def test_a_converged_repo_is_exit_zero_and_says_so(self, tmp_path: Path) -> None:
        """A finding is not a failure, and neither is its absence."""
        project = _repo(tmp_path, state="project: demo\n")
        (project / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
            "---\nartifact: build-plan\nscope: demo\n---\n\n## Status\n\n- [x] Chunk 01: done\n",
            encoding="utf-8",
        )
        proc = _run(project, "lifecycle-repair")

        assert proc.returncode == 0, proc.stderr
        assert "already in the target state" in proc.stdout

    def test_an_unknown_flag_is_exit_two(self, tmp_path: Path) -> None:
        proc = _run(_repo(tmp_path), "lifecycle-repair", "--wat")
        assert proc.returncode == 2
        assert "unknown argument" in proc.stderr

    def test_a_positional_is_exit_two(self, tmp_path: Path) -> None:
        """The guard that exists because a stray path once made a command audit
        the live repo instead of the fixture."""
        proc = _run(_repo(tmp_path), "lifecycle-repair", "/some/path")
        assert proc.returncode == 2

    def test_json_carries_the_keys_doctor_reads(self, tmp_path: Path) -> None:
        """The contract, pinned. `skills/doctor/SKILL.md` #15 grades on
        `retired_flag` and #16 on `plans_to_review`; renaming either would break
        the health check with nothing failing here to say so."""
        proc = _run(_repo(tmp_path), "lifecycle-repair", "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)

        assert set(payload) >= {"applied", "edits", "retired_flag", "plans_to_review", "outcome"}
        assert payload["retired_flag"]["status"] == "present"
        assert payload["retired_flag"]["line"] == 8
        assert payload["applied"] is False
        # Every edit is JSON-serialisable and self-describing — the reason is what
        # the operator is shown, so it must survive the machine route too.
        for edit in payload["edits"]:
            assert set(edit) == {"path", "kind", "reason", "detail"}
            assert edit["reason"]

    def test_json_plans_to_review_names_the_unticked_chunk(self, tmp_path: Path) -> None:
        payload = json.loads(_run(_repo(tmp_path), "lifecycle-repair", "--json").stdout)
        reviews = payload["plans_to_review"]

        assert len(reviews) == 1
        assert reviews[0]["chunks"] == ["Chunk 02: pending"]


class TestUnreadableFilesChangeTheVerdict:
    """The command must not grade a repo it could not fully read.

    Exit 1 is "could not run", the same meaning every sibling repair gives it —
    a check that declined must never be indistinguishable from one that passed.
    """

    def _repo_with_unreadable_plan(self, tmp_path: Path) -> Path:
        project = _repo(tmp_path, state="project: demo\n")
        (project / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
            "---\nartifact: build-plan\nscope: demo\n---\n\n## Status\n\n- [x] Chunk 01: done\n",
            encoding="utf-8",
        )
        bad = project / ".prawduct" / "artifacts" / "build-plan-bad.md"
        bad.write_bytes(b"---\nartifact: build-plan\nscope: bad\n---\n\xff\xfe\x00")
        return project

    def test_dry_run_says_not_checked_and_exits_one(self, tmp_path: Path) -> None:
        proc = _run(self._repo_with_unreadable_plan(tmp_path), "lifecycle-repair")

        assert proc.returncode == 1
        assert "has NOT been checked" in proc.stdout
        assert "already in the target state" not in proc.stdout
        assert "could not read" in proc.stderr

    def test_apply_also_exits_one(self, tmp_path: Path) -> None:
        proc = _run(self._repo_with_unreadable_plan(tmp_path), "lifecycle-repair", "--apply")
        assert proc.returncode == 1

    def test_json_carries_the_unreadable_list(self, tmp_path: Path) -> None:
        proc = _run(self._repo_with_unreadable_plan(tmp_path), "lifecycle-repair", "--json")
        payload = json.loads(proc.stdout)

        assert len(payload["unreadable"]) == 1
        assert payload["unreadable"][0]["path"].endswith("build-plan-bad.md")


class TestPlanBackfillCommand:
    def test_dry_run_moves_nothing(self, tmp_path: Path) -> None:
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        before = _tree(project)
        proc = _run(project, "plan-backfill")

        assert proc.returncode == 0, proc.stderr
        assert "would archive" in proc.stdout
        assert _tree(project) == before

    def test_apply_archives_and_exits_zero(self, tmp_path: Path) -> None:
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        proc = _run(project, "plan-backfill", "--apply", "--date", "2026-08-10")

        assert proc.returncode == 0, proc.stderr
        archived = project / ".prawduct" / "artifacts" / "archive" / "build-plan-demo.md"
        assert archived.is_file()
        assert "archived: 2026-08-10" in archived.read_text()

    def test_apply_names_the_staging_remedy(self, tmp_path: Path) -> None:
        """The move is a write plus an unlink and this command stages neither.

        A plan in the index and gone from disk fails any test that enumerates
        tracked paths and opens them, which went red at two release cuts. The
        operator learns that here, from the run that created the state, or they
        learn it from a red suite.
        """
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        proc = _run(project, "plan-backfill", "--apply", "--date", "2026-08-10")

        assert proc.returncode == 0, proc.stderr
        assert "git add -A .prawduct/artifacts" in proc.stdout

    def test_a_dry_run_does_not_name_it(self, tmp_path: Path) -> None:
        """The control. A preview moves nothing, so there is nothing to stage —
        advice given where it does not apply is how advice stops being read."""
        proc = _run(_repo(tmp_path, plan=PLAN_COMPLETE), "plan-backfill")

        assert proc.returncode == 0, proc.stderr
        assert "would archive" in proc.stdout, "the premise: this run had plans to list"
        assert "git add" not in proc.stdout

    def test_an_apply_that_moved_nothing_does_not_name_it_either(self, tmp_path: Path) -> None:
        """The guard's precision, not merely its existence.

        `--apply` is not the predicate and neither is `shipped` — what MOVED is.
        This needs a run where those two DISAGREE, which the blocked-plan repo
        cannot supply (a blocked plan never reaches `shipped`): a plan that
        qualifies, is attempted, and fails at write time. An unwritable
        `archive/` produces exactly that, and it is the only fixture here under
        which a guard keyed on `--apply` and one keyed on what moved give
        different answers.
        """
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        archive = project / ".prawduct" / "artifacts" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        archive.chmod(0o500)
        try:
            proc = _run(project, "plan-backfill", "--apply", "--date", "2026-08-10")
        finally:
            archive.chmod(0o700)  # or tmp_path teardown cannot remove it

        assert "would archive" not in proc.stdout, "the premise: this was an --apply"
        assert "archived 1 finished plan(s)" in proc.stdout, (
            "the premise that makes this discriminate: the plan DID qualify, so "
            "`shipped` is non-empty while nothing moved"
        )
        assert (project / ".prawduct" / "artifacts" / "build-plan-demo.md").is_file(), (
            "nothing moved — the live plan is still live"
        )
        assert "git add" not in proc.stdout

    def test_date_equals_form_is_accepted(self, tmp_path: Path) -> None:
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        proc = _run(project, "plan-backfill", "--apply", "--date=2026-01-02")

        assert proc.returncode == 0, proc.stderr
        archived = project / ".prawduct" / "artifacts" / "archive" / "build-plan-demo.md"
        assert "archived: 2026-01-02" in archived.read_text()

    def test_date_with_no_value_is_exit_two(self, tmp_path: Path) -> None:
        """Never a silently-defaulted date: the date is the record."""
        proc = _run(_repo(tmp_path, plan=PLAN_COMPLETE), "plan-backfill", "--date")
        assert proc.returncode == 2
        assert "--date requires" in proc.stderr

    def test_empty_date_is_exit_two(self, tmp_path: Path) -> None:
        proc = _run(_repo(tmp_path, plan=PLAN_COMPLETE), "plan-backfill", "--date=")
        assert proc.returncode == 2

    def test_an_unknown_flag_is_exit_two(self, tmp_path: Path) -> None:
        proc = _run(_repo(tmp_path, plan=PLAN_COMPLETE), "plan-backfill", "--wat")
        assert proc.returncode == 2
        assert "unknown argument" in proc.stderr

    def test_a_product_with_no_release_tags_moves_nothing_and_says_why(
        self, tmp_path: Path
    ) -> None:
        project = _repo(
            tmp_path,
            change_log="# Change Log\n\n## 2026-01-01: a thing\n",
            plan=PLAN_COMPLETE,
        )
        before = _tree(project)
        proc = _run(project, "plan-backfill", "--apply")

        assert proc.returncode == 0, proc.stderr
        assert "no mechanical way" in proc.stdout
        assert _tree(project) == before

    def test_json_shape(self, tmp_path: Path) -> None:
        proc = _run(_repo(tmp_path, plan=PLAN_COMPLETE), "plan-backfill", "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)

        assert set(payload) >= {
            "applied",
            "has_release_tags",
            "shipped",
            "blocked",
            "kept_live",
            "archived",
            "refused",
        }
        assert payload["has_release_tags"] is True
        assert [item["scope"] for item in payload["shipped"]] == ["demo"]
        assert payload["blocked"] == []

    def _repo_with_a_blocked_plan(self, tmp_path: Path) -> Path:
        """A plan the change log says shipped but whose archive name is taken."""
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        archive = project / ".prawduct" / "artifacts" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        (archive / "build-plan-demo.md").write_text("an earlier plan\n", encoding="utf-8")
        return project

    def test_a_blocked_plan_is_named_in_json_and_on_stdout(self, tmp_path: Path) -> None:
        """`blocked` is the preview's promise matching the write's behaviour.

        Pinned at the CLI because that is the surface the operator approves
        from: a plan counted under *would archive N* and then refused is consent
        to a set that was never achievable.
        """
        project = self._repo_with_a_blocked_plan(tmp_path)
        proc = _run(project, "plan-backfill", "--json")
        payload = json.loads(proc.stdout)

        assert payload["shipped"] == []
        assert [item["scope"] for item in payload["blocked"]] == ["demo"]
        assert "already exists" in payload["blocked"][0]["reason"]

        human = _run(project, "plan-backfill")
        assert "NOT moving 1 plan(s)" in human.stdout

    def test_a_preview_with_blocked_plans_still_exits_zero(self, tmp_path: Path) -> None:
        """Nothing was skipped because nothing was attempted — and a dry run
        that exits 1 on every repo holding one already-archived namesake is
        noise the release checklist would learn to ignore."""
        proc = _run(self._repo_with_a_blocked_plan(tmp_path), "plan-backfill")
        assert proc.returncode == 0, proc.stderr

    def test_an_apply_that_could_not_move_everything_exits_one(self, tmp_path: Path) -> None:
        """The signal `refused` used to carry, restored.

        Before the preview consulted the refusal predicate this repo attempted
        the collision, failed, and exited 1. Pre-filtering into `blocked` made
        the same repo exit 0 — a run that skipped work reporting as one that had
        none, which is the shape this whole change exists to end.
        """
        project = self._repo_with_a_blocked_plan(tmp_path)
        before = _tree(project)
        proc = _run(project, "plan-backfill", "--apply", "--date", "2026-08-10")

        assert proc.returncode == 1, proc.stdout
        assert [] == [p for p in _tree(project) if p not in before]
        # The live plan and the namesake it collided with are both untouched.
        assert (project / ".prawduct" / "artifacts" / "build-plan-demo.md").is_file()
        assert (
            project / ".prawduct" / "artifacts" / "archive" / "build-plan-demo.md"
        ).read_text() == "an earlier plan\n"

    def test_the_active_plan_is_refused_rather_than_archived(self, tmp_path: Path) -> None:
        """The pointer's target is never this sweep's to move.

        Archiving it dangles the pointer, and a dangling pointer reads to every
        gate as "no active build plan" — they go quiet rather than fail, which is
        this work's worst failure class.
        """
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        state = project / ".prawduct" / "project-state.yaml"
        state.write_text(
            STATE_WITH_FLAG + "active_build_plan: artifacts/build-plan-demo.md\n",
            encoding="utf-8",
        )
        proc = _run(project, "plan-backfill", "--apply")

        assert proc.returncode == 0, proc.stderr
        assert (project / ".prawduct" / "artifacts" / "build-plan-demo.md").is_file()

    def test_it_reports_a_pointer_that_names_a_missing_plan(self, tmp_path: Path) -> None:
        """Reachable for any reason — archived by hand, moved, renamed, lost to
        an interrupted run — and silent gates are the cost every time."""
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        state = project / ".prawduct" / "project-state.yaml"
        state.write_text(
            STATE_WITH_FLAG + "active_build_plan: artifacts/build-plan-gone.md\n",
            encoding="utf-8",
        )
        proc = _run(project, "plan-backfill")

        assert "which is not there" in proc.stderr
        assert "goes quiet" in proc.stderr

    def test_it_stays_quiet_when_the_pointer_names_a_live_plan(self, tmp_path: Path) -> None:
        """Without this, the assertion above passes on a notice that always fires."""
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        live = project / ".prawduct" / "artifacts" / "build-plan-live.md"
        live.write_text(
            "---\nartifact: build-plan\nscope: unreleased\n---\n\n## Status\n\n- [ ] Chunk 01: x\n",
            encoding="utf-8",
        )
        state = project / ".prawduct" / "project-state.yaml"
        state.write_text(
            STATE_WITH_FLAG + "active_build_plan: artifacts/build-plan-live.md\n",
            encoding="utf-8",
        )
        proc = _run(project, "plan-backfill", "--apply")

        assert proc.returncode == 0, proc.stderr
        assert "active_build_plan still names" not in proc.stderr

    def test_running_twice_under_apply_stays_exit_zero(self, tmp_path: Path) -> None:
        """Idempotence at the CLI boundary — the second run finds nothing to do
        and must not report that as a failure."""
        project = _repo(tmp_path, plan=PLAN_COMPLETE)
        assert _run(project, "plan-backfill", "--apply").returncode == 0
        second = _run(project, "plan-backfill", "--apply")
        assert second.returncode == 0, second.stderr
