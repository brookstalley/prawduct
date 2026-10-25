"""Tests for lib/work_unit_probes.py — the `plan-unbound-legacy` advisory (#1050, MG3).

A plan served through the legacy window (the `active_build_plan` pointer or the
conventional `artifacts/build-plan.md`, in a repo where no plan claims a branch)
raises one advisory whose text is the binding's own reason and whose remedy is
`prawduct-hook plan bind`. Nothing else raises it. Following the remedy resolves
it, and the briefing says the sentence once.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from lib import briefing, probe_families, work_unit
from lib import work_unit_probes as wup
from lib.advisory_store import (
    ProjectState,
    clear_registry,
    make_codebase,
    read_store,
    run_sync_advisories,
)

HOOK = Path(__file__).resolve().parents[1] / "plugin" / "bin" / "prawduct-hook"


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), capture_output=True, text=True, check=True,
    ).stdout


def _repo(tmp_path: Path, branch: str = "feat/work", state: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", branch)
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text(state)
    return repo


def _plan(repo: Path, rel: str, frontmatter: str = "scope: lonely\n") -> Path:
    path = repo / ".prawduct" / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nartifact: build-plan\n{frontmatter}---\n\n# Build Plan\n\n"
        "## Status\n\n- [ ] Chunk 01: open\n"
    )
    return path


def _probe(repo: Path) -> list:
    return list(wup.probe_plan_unbound_legacy(ProjectState({}), make_codebase(repo)))


class TestFires:
    def test_a_default_bound_plan_raises_the_advisory_with_the_bindings_reason(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md")
        binding = work_unit.resolve(repo)
        assert binding.chosen_by == "legacy-default"
        [candidate] = _probe(repo)
        assert candidate.type == work_unit.LEGACY_ADVISORY_KEY == "plan-unbound-legacy"
        assert candidate.trigger_summary == binding.reason
        assert candidate.priority == "warn"
        # The remedy is the bind command, concrete for this plan and branch —
        # spelled out at the construction site for the actionability lint, so
        # the two spellings are pinned together here.
        assert candidate.recommended_action == (
            f"{work_unit.BIND_COMMAND} build-plan.md --branch feat/work"
        )

    def test_a_pointer_bound_plan_raises_it_too(self, tmp_path):
        """The pointer-only fixture the plan's acceptance names."""
        repo = _repo(tmp_path, state="active_build_plan: artifacts/v2-plan.md\n")
        _plan(repo, "v2-plan.md", "scope: v2\n")
        [candidate] = _probe(repo)
        assert work_unit.resolve(repo).chosen_by == "legacy-pointer"
        assert "the active_build_plan pointer" in candidate.evidence[0]
        assert candidate.recommended_action.endswith("v2-plan.md --branch feat/work")

    def test_a_branch_name_needing_quotes_is_quoted(self, tmp_path):
        # The action is a command the runtime executes as given.
        repo = _repo(tmp_path, branch="feat/a$(x)")
        _plan(repo, "build-plan.md")
        [candidate] = _probe(repo)
        assert shlex.split(candidate.recommended_action)[-1] == "feat/a$(x)"

    def test_evidence_does_not_name_the_branch(self, tmp_path):
        """One dismissal covers the plan across branches: the id is the
        evidence's hash, and binding the plan anywhere ends it everywhere."""
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md")
        [first] = _probe(repo)
        _git(repo, "switch", "-q", "-c", "feat/other")
        [second] = _probe(repo)
        assert first.evidence == second.evidence
        assert first.trigger_summary != second.trigger_summary


class TestSilent:
    def test_a_claimed_plan_raises_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md", "scope: lonely\nbranch: feat/work\n")
        assert work_unit.resolve(repo).chosen_by == "binding"
        assert _probe(repo) == []

    def test_an_unbound_checkout_raises_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-x.md", "scope: x\nbranch: feat/x\n")
        assert work_unit.resolve(repo).state == "unbound"
        assert _probe(repo) == []

    def test_a_detached_head_raises_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md")
        head = _git(repo, "rev-parse", "HEAD").strip()
        _git(repo, "checkout", "-q", "--detach", head)
        assert _probe(repo) == []


def test_it_is_registered_at_the_composition_root():
    from lib import advisory_store

    probe_families.register_all()
    record = advisory_store._REGISTRY.get(f"{wup.FEATURE}:{work_unit.LEGACY_ADVISORY_KEY}")
    assert record is not None, sorted(advisory_store._REGISTRY)
    assert record["fn"] is wup.probe_plan_unbound_legacy


class TestFollowingTheRemedy:
    def test_running_the_recommended_action_resolves_the_advisory(self, tmp_path):
        """The advisory's effect, not its shape: sync, run what it says, sync
        again — it resolves, and the plan now binds by its claim. The
        un-applied repo beside it is the control: it stays active."""
        probe_families.register_all()
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md")
        run_sync_advisories(repo)
        active = [a for a in read_store(repo)["advisories"]
                  if a.get("type") == work_unit.LEGACY_ADVISORY_KEY and a.get("state") == "active"]
        assert len(active) == 1
        action = active[0]["recommended_action"]

        argv = shlex.split(action)
        assert argv[:3] == ["prawduct-hook", "plan", "bind"]
        proc = subprocess.run(
            [sys.executable, str(HOOK), *argv[1:]],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                 "HOME": str(tmp_path), "CLAUDE_PROJECT_DIR": str(repo)},
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.startswith("bound: ")

        binding = work_unit.resolve(repo)
        assert (binding.state, binding.chosen_by) == ("bound", "binding")
        run_sync_advisories(repo)
        # By id: retention compacts a resolved entry and drops its descriptive
        # fields, so its type is not what finds it.
        [entry] = [a for a in read_store(repo)["advisories"] if a.get("id") == active[0]["id"]]
        assert entry["state"] == "resolved"
        assert not [a for a in read_store(repo)["advisories"]
                    if a.get("type") == work_unit.LEGACY_ADVISORY_KEY and a.get("state") == "active"]

        control = _repo(tmp_path / "control")
        _plan(control, "build-plan.md")
        run_sync_advisories(control)
        assert [a.get("state") for a in read_store(control)["advisories"]
                if a.get("type") == work_unit.LEGACY_ADVISORY_KEY] == ["active"]


class TestTheBriefingSaysItOnce:
    def test_the_legacy_reason_appears_once_through_the_advisory(self, tmp_path):
        """Chunk 02 put a legacy binding's reason on a `⚠ build plan:` line;
        the advisory now carries the same sentence, so the briefing line skips
        a legacy binding and the advisory block is where it is read."""
        probe_families.register_all()
        repo = _repo(tmp_path)
        _plan(repo, "build-plan.md")
        reason = work_unit.resolve(repo).reason
        run_sync_advisories(repo)
        text = briefing.assemble_session_briefing(repo, [])
        assert text.count(reason) == 1, text
        assert not any(ln.startswith("⚠ build plan:") for ln in text.splitlines())
        assert f"[work-unit] {reason}" in text

    def test_a_claimant_without_scope_keeps_its_briefing_line(self, tmp_path):
        """The control: a bound reason that is NOT the advisory's still prints."""
        repo = _repo(tmp_path)
        _plan(repo, "build-plan-x.md", "branch: feat/work\n")
        text = briefing.assemble_session_briefing(repo, [])
        line = next(ln for ln in text.splitlines() if ln.startswith("⚠ build plan:"))
        assert "declares no `scope:`" in line
