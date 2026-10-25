"""Pins which build-plan `Type:` values skip the Stop-hook Critic gate.

The carveout is deliberately a single value: `Type: designer-handoff` (v1.4 F6).
Every other declared Type — `code`, `doc-only`, `cleanup`, `cumulative-final` —
falls through to the *default* gate path, so the Critic gate still fires when
code changed against an active plan with no findings.

Today the only behavioral coverage of the carveout is the implicit
`Type: code` default path. There is no test pinning that the *non-handoff*
Types do NOT join the skip-list. A refactor that broadened the branch — e.g.
`if chunk_type in {"designer-handoff", "doc-only"}:` — would silently regress:
a `doc-only`-typed code chunk would stop being reviewed. `TestNonHandoffTypes\
FallThroughToGate` is the regression guard (verified to FAIL under exactly that
broadening). `TestDesignerHandoffSkipsCriticGate` is its contrast partner —
the one value that legitimately skips — so the pair reads as a complete
truth-table for the carveout (Tests Are Contracts).

Harness mirrors `test_plugin_runtime.py::TestPluginStopGate` — subprocess
invocation of `bin/prawduct-hook stop` with a mock git on PATH — because the
gate decision is only observable end-to-end (the Type parse, the empirical
doc-only check, and the findings-freshness check all compose inside `cmd_stop`).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import SHAPED_REFLECTION

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

# The empirical diff is a non-`.md` code file. This keeps the gate's *other*
# carveout — `gates.session_changes_all_non_judgeable` (a fully non-judgeable
# diff) — False, so the only thing that could skip the gate is the Type ->
# designer_handoff_skip branch. That isolation is the whole point: we are
# pinning the Type field's effect, not the empirical doc-only shortcut.
_CODE_DIFF = " M src/app.py"


def _write_mock_git(
    mock_bin: Path, *, status: str, branch: str = "main", symbolic_ref: str = "main"
) -> None:
    """A mock git for the stop path.

    ``symbolic_ref`` answers ``git symbolic-ref --short HEAD``, which is what
    ``gitstate.current_branch`` — and so ``work_unit.resolve`` — reads; a
    different probe from ``branch --show-current`` above it. The default is
    ``main``, so a fixture whose plans declare no ``branch:`` sits in the legacy
    window and its conventional plan governs. Empty means the probe fails: a
    detached HEAD, which is unbound and arms no plan gate. Every other
    ``symbolic-ref`` (``origin/HEAD``) fails, as it always has here.
    """
    mock_bin.mkdir(parents=True, exist_ok=True)
    status_file = mock_bin / "_status"
    status_file.write_text(status)
    git = mock_bin / "git"
    symref = (
        f'if [[ "$1" == "symbolic-ref" && "${{@: -1}}" == "HEAD" ]]; then echo "{symbolic_ref}"; exit 0; fi\n'
        if symbolic_ref
        else ""
    ) + 'if [[ "$1" == "symbolic-ref" ]]; then exit 1; fi\n'
    # f-strings throughout: `+`-concatenating a pre-formatted fragment into a
    # `%`-formatted literal silently applies `%` to the LAST literal only.
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "deadbeefdeadbeef"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        f'if [[ "$1" == "status" ]]; then cat "{status_file}"; exit 0; fi\n'
        f'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "{branch}"; exit 0; fi\n'
        f"{symref}"
        'if [[ "$1" == "worktree" ]]; then exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n"
    )
    git.chmod(0o755)
    gh = mock_bin / "gh"
    gh.write_text("#!/bin/bash\necho '[]'\nexit 0\n")
    gh.chmod(0o755)


def _run_stop(
    project_dir: Path, *, status: str, symbolic_ref: str = "main"
) -> subprocess.CompletedProcess:
    """Invoke `bin/prawduct-hook stop` as Claude Code would, with a mock git on
    PATH and the plugin/project roots wired. mock_bin + HOME live OUTSIDE
    project_dir so nothing per-user lands under the fixture."""
    mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin, status=status, symbolic_ref=symbolic_ref)
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "stop"],
        capture_output=True, text=True, env=env, timeout=20,
    )


def _active_plan_repo(tmp_path: Path, *, chunk_type: str) -> Path:
    """An active-build-plan fixture whose single current chunk declares
    `**Type:** <chunk_type>`. Reflection is pre-satisfied — with
    `SHAPED_REFLECTION`, since the gate grades shape rather than length (#685) —
    so the *only* gate in play is the Critic gate; a non-CRITIC block would be a
    confounder, and after #685 the reflection gate fires on this fixture's code
    diff whether or not its plan is active. No `.critic-findings.json` is
    written: the gate fires unless the Type carves it out."""
    prawduct = tmp_path / ".prawduct"
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(
        "# Build Plan\n\n"
        "## Status\n- [ ] Chunk 01: Demo\n\n"
        f"### Chunk 01: Demo\n**Type:** {chunk_type}\n\nBody.\n"
    )
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".session-git-baseline").write_text("")
    ts = datetime.now(timezone.utc) - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return prawduct


# The four Types that are NOT carveouts. `code` is the fail-closed default but is
# pinned explicitly here so the truth-table is complete and a future default
# change can't quietly drop it from coverage.
_NON_HANDOFF_TYPES = ["code", "doc-only", "cleanup", "cumulative-final"]


class TestNonHandoffTypesFallThroughToGate:
    """Regression guard: only `designer-handoff` skips the gate. Each of the
    four non-handoff Types must STILL trip the Critic gate (exit 2, CRITIC
    block) when code changed against an active plan with no findings. Broaden
    the skip-list to include any of these and the corresponding case fails."""

    @pytest.mark.parametrize("chunk_type", _NON_HANDOFF_TYPES)
    def test_gate_fires_for_non_handoff_type(self, tmp_path, chunk_type):
        _active_plan_repo(tmp_path, chunk_type=chunk_type)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2, (
            f"Type: {chunk_type} must NOT skip the Critic gate — only "
            f"designer-handoff does. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" in result.stderr, (
            f"Type: {chunk_type} must produce the Critic block (the gate that "
            f"fired), not some other gate. stderr={result.stderr!r}"
        )

    @pytest.mark.parametrize("chunk_type", _NON_HANDOFF_TYPES)
    def test_non_handoff_type_does_not_emit_handoff_skip_note(self, tmp_path, chunk_type):
        # The skip branch also appends a "critic: skipped (… designer-handoff …)"
        # waiver note. A non-handoff Type must never emit it — guards against a
        # refactor that flips the skip flag while leaving the exit code coincidentally
        # at 2 for an unrelated reason.
        _active_plan_repo(tmp_path, chunk_type=chunk_type)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert "designer-handoff" not in result.stdout, (
            f"Type: {chunk_type} must not trigger the designer-handoff skip note. "
            f"stdout={result.stdout!r}"
        )


class TestDesignerHandoffSkipsCriticGate:
    """Contrast partner: the one Type that legitimately skips. Same fixture,
    same code diff — only the declared Type differs — so the pair isolates the
    Type field as the sole cause of the divergent gate decision."""

    def test_designer_handoff_skips_the_gate(self, tmp_path):
        _active_plan_repo(tmp_path, chunk_type="designer-handoff")
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 0, (
            "Type: designer-handoff must skip the Critic gate (v1.4 F6 carveout). "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC REVIEW" not in result.stderr, (
            f"the Critic block must be absent when skipped. stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Cumulative-as-final: the end-of-cycle synthesis advisory accepts cumulative
# ---------------------------------------------------------------------------

# Persisted-side (verbose) mode strings, pinned as literals: the advisory's
# contract is over the `mode` telemetry reviews record in their store FACT
# (kernel-v3 chunk 04 — the advisory reads the latest review fact, never the
# .critic-findings.json cache), so the test must break if either the
# constants or the acceptance set drifts.
_MODE_CHUNK = "chunk (lighter pass, not ready for push)"
_MODE_FINAL = "final (full review, ready for push)"
_MODE_CUMULATIVE = "cumulative (bundle review, ready for merge)"
_MODE_VERIFY = "verify-resolutions (delta review, prior findings only)"


def _all_complete_plan_repo(tmp_path: Path, *, mode: str | None) -> Path:
    """A git repo with a multi-chunk plan, every chunk `[x]`, and (unless
    ``mode`` is None) a latest review FACT in the given persisted-side mode —
    exactly the state the synthesis advisory
    (`_critic_session_satisfies_gate` case 4/5) inspects."""
    import sys

    sys.path.insert(0, str(ROOT))
    from lib import evidence

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True, timeout=15
    )
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(
        "# Build Plan\n\n## Status\n- [x] Chunk 01: A\n- [x] Chunk 02: B\n"
    )
    if mode is not None:
        result = evidence.append_fact(
            repo,
            "review",
            "rev-advisory-1",
            {"mode": mode, "findings": [], "files_reviewed": ["a.py"]},
        )
        assert result["status"] == "appended", result
    return repo


class TestSynthesisAdvisoryAcceptsCumulative:
    """Pins `_critic_session_satisfies_gate` case 5 for `cumulative` records
    (review-proportionality ch.01 — cumulative-as-final). The one-review rule
    makes a `Type: cumulative-final` plan's LAST review legitimately
    `cumulative` instead of `final`; if the advisory ever stopped accepting
    cumulative records, every such plan would close with a spurious "run
    /prawduct:critic final" warning — re-introducing the duplicate full review
    the rule removed. Kernel-v3 chunk 04 re-sourced the mode from the latest
    review FACT (no gate reads the findings cache); the acceptance set is
    unchanged."""

    def test_cumulative_fact_satisfies_synthesis_advisory(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_CUMULATIVE)
        ok, reason = _critic_session_satisfies_gate(repo)
        assert ok, f"cumulative must satisfy the synthesis advisory: {reason!r}"

    def test_final_fact_satisfies_synthesis_advisory(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_FINAL)
        ok, reason = _critic_session_satisfies_gate(repo)
        assert ok, f"final must satisfy the synthesis advisory: {reason!r}"

    def test_no_review_fact_means_nothing_to_judge(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=None)
        ok, _reason = _critic_session_satisfies_gate(repo)
        assert ok

    @pytest.mark.parametrize("mode", [_MODE_CHUNK, _MODE_VERIFY])
    def test_goals_1_3_modes_still_trip_the_advisory(self, tmp_path, mode):
        # Contrast partner — the advisory's whole job. Goals-1-3-only closers
        # must keep tripping it, or cumulative-as-final would quietly widen
        # into accepting ANY closing mode (a no-review rule).
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=mode)
        ok, reason = _critic_session_satisfies_gate(repo)
        assert not ok, f"{mode!r} must trip the synthesis advisory"
        assert "/prawduct:critic final" in reason


def _append_foreign_review(repo: Path, mode: str, *, worktree: str, branch: str) -> None:
    """A review fact recorded from ANOTHER worktree or branch of the same clone:
    the store is clone-global, so it lands in this repo's store too."""
    import sys

    sys.path.insert(0, str(ROOT))
    from lib import evidence

    with open(evidence.store_path(repo), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schema": evidence.SCHEMA_VERSION,
            "kind": "review",
            "id": f"rev-foreign-{worktree.strip('/')}-{branch}",
            "ts": "2026-10-21T00:00:00Z",
            "actor": {"session": "s", "worktree": worktree, "plugin": "x", "branch": branch},
            "body": {"mode": mode, "findings": [], "files_reviewed": ["a.py"]},
        }) + "\n")


class TestSynthesisAdvisoryReadsThisSessionsReview:
    """#305(b): the advisory keys its "latest review" to this worktree and
    branch. Another worktree's newer review must not steer it either way."""

    def test_a_newer_final_from_another_worktree_does_not_satisfy_it(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_CHUNK)
        _append_foreign_review(repo, _MODE_FINAL, worktree="/elsewhere", branch="main")
        ok, reason = _critic_session_satisfies_gate(repo)
        assert not ok, "another worktree's final review steered this session's advisory"
        assert "/prawduct:critic final" in reason

    def test_a_newer_chunk_from_another_worktree_does_not_trip_it(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_FINAL)
        _append_foreign_review(repo, _MODE_CHUNK, worktree="/elsewhere", branch="main")
        ok, reason = _critic_session_satisfies_gate(repo)
        assert ok, reason

    def test_a_newer_review_on_another_branch_here_does_not_steer_it(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_FINAL)
        _append_foreign_review(repo, _MODE_CHUNK, worktree=str(repo), branch="other")
        ok, reason = _critic_session_satisfies_gate(repo)
        assert ok, reason

    def test_the_control_a_newer_review_from_here_does_steer_it(self, tmp_path):
        from lib.gates import _critic_session_satisfies_gate

        repo = _all_complete_plan_repo(tmp_path, mode=_MODE_FINAL)
        _append_foreign_review(repo, _MODE_CHUNK, worktree=str(repo), branch="main")
        ok, _reason = _critic_session_satisfies_gate(repo)
        assert not ok


class TestGateReadsTheBranchsPlanNotThePointer:
    """The chunk-level fields the gate acts on come from ONE plan.

    `active_build_plan` answers "which plan is in progress in this repo". On a
    repo running several plans across worktrees that is not "which plan is this
    branch building" — and the gate's Type-driven carveouts were being decided
    by a chunk of a plan the session never touched. Both fields come from the
    checkout's binding (`work_unit.resolve`): the plan whose `branch:` claims
    this branch. A branch no plan claims borrows none — not the pointer's, not a
    name-matched one (#1050 BR3) — unless the repo is in the legacy window,
    where no plan claims anything and the conventional plan governs (every
    other fixture in this file).
    """

    def _two_plan_repo(self, tmp_path: Path, *, branch_type: str, pointer_type: str):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        # The pointer's plan — legitimately in progress, and not this branch's.
        (artifacts / "build-plan.md").write_text(
            "---\nartifact: build-plan\nscope: pointed\n---\n\n"
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Pointed\n\n"
            f"### Chunk 01: Pointed\n**Type:** {pointer_type}\n\nBody.\n"
        )
        # This branch's plan — it CLAIMS `fix/mine`. A name match alone binds
        # nothing any more; the claim is what makes it the branch's plan.
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\nbranch: fix/mine\n---\n\n"
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Mine\n\n"
            f"### Chunk 01: Mine\n**Type:** {branch_type}\n\nBody.\n"
        )
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        (prawduct / ".session-git-baseline").write_text("")
        ts = datetime.now(timezone.utc) - timedelta(seconds=60)
        (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
        return prawduct

    def test_the_carveout_follows_the_branchs_plan(self, tmp_path):
        """Branch plan says `designer-handoff`, pointer says `code` → skip.

        Reverting the gate-plan threading reads the pointer's `code` and the
        gate fires, so this dies with the fix removed.
        """
        self._two_plan_repo(
            tmp_path, branch_type="designer-handoff", pointer_type="code"
        )
        result = _run_stop(tmp_path, status=_CODE_DIFF, symbolic_ref="fix/mine")
        assert result.returncode == 0, (
            "the branch's chunk declares designer-handoff, so the Critic gate is "
            f"carved out. stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_the_pointers_carveout_does_not_leak_onto_this_branch(self, tmp_path):
        """The mirror, and the one that matters more.

        Pointer says `designer-handoff`, branch says `code`. Reading the pointer
        here SKIPS the Critic gate for a chunk that never asked for it — a
        governance carveout granted by an unrelated plan.
        """
        self._two_plan_repo(
            tmp_path, branch_type="code", pointer_type="designer-handoff"
        )
        result = _run_stop(tmp_path, status=_CODE_DIFF, symbolic_ref="fix/mine")
        assert result.returncode == 2, (
            "this branch's chunk is `code`; the pointer's designer-handoff must "
            f"not carve it out. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" in result.stderr

    def test_an_unclaimed_branch_borrows_no_plan(self, tmp_path):
        """Renegotiated for #1050 (it was `..._still_uses_the_pointer`).

        The old contract was the fallback: a branch no scope matched read the
        pointer's plan. That fallback is the defect class — it looks right while
        being wrong — so it is gone. Here a plan in the repo claims `fix/mine`,
        which closes the legacy window, so `fix/unrelated-name` is UNBOUND: no
        plan governs it and the Critic gate does not arm. The pointer's plan is
        `code`, so the old reading blocks; seeing exit 0 needs the binding.
        """
        self._two_plan_repo(
            tmp_path, branch_type="designer-handoff", pointer_type="code"
        )
        result = _run_stop(
            tmp_path, status=_CODE_DIFF, symbolic_ref="fix/unrelated-name"
        )
        assert result.returncode == 0, (
            "no plan claims this branch, so none governs it and no Critic gate "
            f"arms. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" not in result.stderr
        assert "designer-handoff" not in result.stderr, (
            "the claimed plan's carveout must not be what let this through"
        )

    def test_a_broken_binding_fails_closed_and_says_why(self, tmp_path):
        """Two live plans claiming one branch is a BROKEN binding (BR5): no plan
        can be chosen, so none may be chosen by precedence — and authority fails
        closed. The gate arms as a bound plan's would, no claimant's carveout
        applies (both declare `designer-handoff` here, so honouring either one
        would let this through), and the block names the reason."""
        self._two_plan_repo(
            tmp_path, branch_type="designer-handoff", pointer_type="designer-handoff"
        )
        pointed = tmp_path / ".prawduct" / "artifacts" / "build-plan.md"
        pointed.write_text(
            pointed.read_text().replace("scope: pointed\n", "scope: pointed\nbranch: fix/mine\n")
        )
        result = _run_stop(tmp_path, status=_CODE_DIFF, symbolic_ref="fix/mine")
        assert result.returncode == 2, (
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # The note is wrapped to the block's width; compare its words.
        block = " ".join(result.stderr[result.stderr.index("CRITIC REVIEW"):].split())
        assert "plan binding for this checkout is broken" in block
        assert "2 live plans claim `fix/mine`" in block

    def test_the_legacy_window_still_serves_the_conventional_plan(self, tmp_path):
        """The other half of the fallback's demotion (MG3): while NO plan in the
        repo declares `branch:`, the conventional plan still governs every
        branch — so a pre-claims repo keeps its gate until it binds."""
        self._two_plan_repo(
            tmp_path, branch_type="designer-handoff", pointer_type="code"
        )
        mine = tmp_path / ".prawduct" / "artifacts" / "build-plan-mine.md"
        mine.write_text(mine.read_text().replace("branch: fix/mine\n", ""))
        result = _run_stop(
            tmp_path, status=_CODE_DIFF, symbolic_ref="fix/unrelated-name"
        )
        assert result.returncode == 2, (
            "no claims anywhere → the conventional plan (`code`) governs and the "
            f"Critic gate fires. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" in result.stderr

    def test_whether_the_gate_runs_follows_the_branchs_plan_too(self, tmp_path):
        """The gate's WHETHER must read the same plan as its WHAT.

        `has_build_plan` decides whether the CRITIC gate runs at all. It
        resolved through `active_build_plan` while the three chunk-level fields
        beneath it came from the branch's plan — one question answered from two
        places, at the gate that decides whether the rest happen.

        **Narrowed on 2026-09-02 (#685), not weakened: this used to say
        "the reflection and Critic gates", and the reflection half is no longer
        true.** That gate stopped asking whether a plan is active and now asks
        whether this session changed judgeable code, so `has_build_plan` decides
        nothing for it — a planless session with a code diff blocks. The
        assertion below is unchanged and still discriminates, because the
        fixture pre-satisfies reflection; the added negative pins that, so the
        exit code can only have come from the gate this test names.

        This fixture is built to DISCRIMINATE, which the three above it are not:
        the POINTER's plan is entirely `[x]`, so `_has_active_build_plan_file`
        reads False through it and the Critic gate goes silent; the BRANCH's
        plan has an open chunk, so it reads True. Revert `gate_plan` out of the
        `has_build_plan` line and this sees exit 0 instead of the Critic block.
        """
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "---\nartifact: build-plan\nscope: pointed\n---\n\n"
            "# Build Plan\n\n## Status\n- [x] Chunk 01: shipped\n\n"
            "### Chunk 01: shipped\n**Type:** code\n\nBody.\n"
        )
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\nbranch: fix/mine\n---\n\n"
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: in progress\n\n"
            "### Chunk 01: in progress\n**Type:** code\n\nBody.\n"
        )
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
        (prawduct / ".session-git-baseline").write_text("")
        ts = datetime.now(timezone.utc) - timedelta(seconds=60)
        (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))

        result = _run_stop(tmp_path, status=_CODE_DIFF, symbolic_ref="fix/mine")
        assert result.returncode == 2, (
            "the branch's plan has an open chunk, so there IS governed work and "
            f"the Critic gate must fire. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" in result.stderr
        assert "REFLECTION:" not in result.stderr, (
            "the exit code must come from the Critic gate, not from the "
            f"reflection gate this fixture pre-satisfies. stderr={result.stderr!r}"
        )
