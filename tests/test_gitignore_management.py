"""Tests for ``lib.core.update_gitignore`` + the tracked-build-plan contract.

Gate-soundness ch.3: build plans are TRACKED artifacts. The framework used to
gitignore ``.prawduct/artifacts/build-plan.md`` while tracked
``project-state.yaml`` pointed ``active_build_plan:`` at it and the PR skill
retained the plan through a gitflow release-pending window — so every
multi-clone repo carried a tracked pointer to a file the other clones didn't
have (scriob PR #43), and ``_untrack_session_files`` force-reverted any
product that tracked its plan anyway. These tests pin the reversal:

  * the entry is gone from ``GITIGNORE_ENTRIES`` (and, via the mirror-parity
    test in ``test_build_plan_resolution.py``, from the hook's untrack list)
  * ``update_gitignore`` strips the stale line from existing repos and
    reports it via ``unignored`` so init-product/doctor advise ``git add``

``update_gitignore`` previously had no behavioral tests — an untested
governance bound rots silently (learnings.md), so the pre-existing behavior
(add missing session entries, unignore managed files) gets pinned here too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))

from lib.core import (  # noqa: E402
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    RETIRED_GITIGNORE_ENTRIES,
    gitignore_contract_drift,
    update_gitignore,
)

BUILD_PLAN_REL = ".prawduct/artifacts/build-plan.md"


class TestBuildPlanIsTracked:
    def test_build_plan_not_in_gitignore_entries(self):
        assert BUILD_PLAN_REL not in GITIGNORE_ENTRIES

    def test_build_plan_is_a_retired_entry(self):
        """The retirement is explicit, not an accidental omission — doctor and
        init-product strip it from repos that still carry it."""
        assert BUILD_PLAN_REL in RETIRED_GITIGNORE_ENTRIES

    def test_update_gitignore_strips_stale_build_plan_line(self, tmp_path: Path):
        gi = tmp_path / ".gitignore"
        gi.write_text(
            "# Prawduct session files\n"
            ".prawduct/.session-start\n"
            f"{BUILD_PLAN_REL}\n"
            "__pycache__/\n"
        )

        result = update_gitignore(tmp_path)

        assert result["modified"] is True
        assert BUILD_PLAN_REL in result["unignored"]
        lines = gi.read_text().splitlines()
        assert BUILD_PLAN_REL not in lines
        # The legitimate session entries survive.
        assert ".prawduct/.session-start" in lines

    def test_update_gitignore_does_not_reintroduce_retired_entries(
        self, tmp_path: Path
    ):
        """Running on a clean repo writes the session set WITHOUT the retired
        build-plan line — the writer and the untrack list agree the plan is
        a tracked artifact."""
        update_gitignore(tmp_path)

        lines = (tmp_path / ".gitignore").read_text().splitlines()
        assert BUILD_PLAN_REL not in lines
        assert ".prawduct/.critic-findings.json" in lines


class TestUpdateGitignoreSubcommand:
    """`prawduct-hook update-gitignore` — the on-demand repair path doctor
    runs for already-onboarded repos (init-product early-exits on them, and
    session hooks must never edit a tracked file)."""

    def _run(self, repo: Path):
        import os
        import subprocess

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(repo)
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "update-gitignore"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_strips_retired_entry_and_advises_git_add(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text(f"{BUILD_PLAN_REL}\n")

        res = self._run(tmp_path)

        assert res.returncode == 0, res.stderr
        assert f"unignored: {BUILD_PLAN_REL}" in res.stdout
        assert "git add" in res.stdout
        assert BUILD_PLAN_REL not in (tmp_path / ".gitignore").read_text().splitlines()

    def test_no_changes_needed_is_quiet_success(self, tmp_path: Path):
        update_gitignore(tmp_path)

        res = self._run(tmp_path)

        assert res.returncode == 0, res.stderr
        assert "no changes needed" in res.stdout
        assert "unignored:" not in res.stdout


class TestInitProductUnignoredPresentation:
    """The onboard-facing layer: `init_product.run` must SURFACE the
    `unignored` advice in both output modes. This exact seam absorbed two
    Critic warnings during the build (report computed but discarded; then
    plumbed but never printed on the documented flow) — pin it."""

    def test_apply_text_mode_prints_git_add_advice(self, tmp_path, capsys):
        from lib.init_product import run

        (tmp_path / ".gitignore").write_text(f"{BUILD_PLAN_REL}\n")

        rc = run([str(tmp_path), "--name", "TestProd", "--apply"])

        assert rc == 0
        out = capsys.readouterr().out
        assert BUILD_PLAN_REL in out
        assert "git add" in out

    def test_apply_json_mode_carries_unignored(self, tmp_path, capsys):
        import json as _json

        from lib.init_product import run

        (tmp_path / ".gitignore").write_text(f"{BUILD_PLAN_REL}\n")

        rc = run([str(tmp_path), "--name", "TestProd", "--apply", "--json"])

        assert rc == 0
        result = _json.loads(capsys.readouterr().out)
        assert BUILD_PLAN_REL in result["unignored"]


class TestExistingBehaviorPinned:
    """Pre-existing update_gitignore behavior, previously untested."""

    def test_creates_gitignore_with_session_entries(self, tmp_path: Path):
        result = update_gitignore(tmp_path)

        assert result["modified"] is True
        lines = (tmp_path / ".gitignore").read_text().splitlines()
        for entry in GITIGNORE_ENTRIES:
            assert entry in lines

    def test_idempotent_second_run(self, tmp_path: Path):
        update_gitignore(tmp_path)
        result = update_gitignore(tmp_path)

        assert result["modified"] is False
        assert result["unignored"] == []

    def test_managed_file_line_is_unignored(self, tmp_path: Path):
        gi = tmp_path / ".gitignore"
        gi.write_text("CLAUDE.md\n")

        result = update_gitignore(tmp_path)

        assert "CLAUDE.md" in result["unignored"]
        assert "CLAUDE.md" not in (tmp_path / ".gitignore").read_text().splitlines()


class TestContractDriftHelper:
    """``gitignore_contract_drift`` — the read-only diff the advisory probe reads.

    The load-bearing invariant is *parity with the fixer*: the probe must fire
    exactly when ``update_gitignore`` would modify the file, or the nudge would
    outlive the fix (perpetual nag) or miss real drift (silent gap). Both derive
    from the shared ``_contract_diff``, and this pins that they never disagree.
    """

    def _drift(self, tmp_path: Path) -> bool:
        d = gitignore_contract_drift(tmp_path)
        return bool(d["missing"] or d["incorrectly_ignored"])

    def test_contract_lists_are_pairwise_disjoint(self):
        """The refactor computes ``missing`` from the *original* line set (not the
        post-removal one), which is behavior-preserving ONLY because the three
        contract lists share no entry. Pin that invariant so a future maintainer
        who adds a path to two lists fails here, not silently in production."""
        session = set(GITIGNORE_ENTRIES)
        managed = set(MANAGED_FILES)
        retired = set(RETIRED_GITIGNORE_ENTRIES)
        assert session.isdisjoint(managed)
        assert session.isdisjoint(retired)
        assert managed.isdisjoint(retired)

    def test_absent_gitignore_reads_as_full_drift(self, tmp_path: Path):
        d = gitignore_contract_drift(tmp_path)
        assert d["missing"] == GITIGNORE_ENTRIES
        assert d["incorrectly_ignored"] == []

    def test_satisfied_contract_is_no_drift(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")
        d = gitignore_contract_drift(tmp_path)
        assert d == {"missing": [], "incorrectly_ignored": []}

    def test_managed_and_retired_entries_are_flagged(self, tmp_path: Path):
        managed = sorted(MANAGED_FILES)[0]
        retired = RETIRED_GITIGNORE_ENTRIES[0]
        (tmp_path / ".gitignore").write_text(
            "\n".join([*GITIGNORE_ENTRIES, managed, retired]) + "\n"
        )
        d = gitignore_contract_drift(tmp_path)
        assert d["missing"] == []
        assert managed in d["incorrectly_ignored"]
        assert retired in d["incorrectly_ignored"]

    @pytest.mark.parametrize(
        "seed",
        [
            None,  # no .gitignore at all
            "",  # empty file
            "\n".join(GITIGNORE_ENTRIES) + "\n",  # satisfied
            "\n".join(GITIGNORE_ENTRIES[:-1]) + "\n",  # one entry short
            "CLAUDE.md\n",  # a managed file wrongly ignored, everything else missing
            "\n".join([*GITIGNORE_ENTRIES, RETIRED_GITIGNORE_ENTRIES[0]]) + "\n",  # retired line
        ],
    )
    def test_drift_matches_fixer_modified(self, tmp_path: Path, seed):
        # Parity: drift-detected BEFORE the fixer runs == the fixer's `modified`.
        if seed is not None:
            (tmp_path / ".gitignore").write_text(seed)
        drift_before = self._drift(tmp_path)
        modified = update_gitignore(tmp_path)["modified"]
        assert drift_before == modified
        # And the fix is a fixed point: after reconciling, no drift remains.
        assert self._drift(tmp_path) is False
