"""End-to-end upgrade-posture + composition scenarios for kernel v3 (ch.06).

Two claims from the discovery get their proof here, driven through the REAL
plugin surface (repo-local ``bin/prawduct-hook``, scratch git repos, the
production ``clear``/review/gate lifecycle — no in-process shortcuts):

* **C9 zero-touch upgrade** — a v2.3.3-era repo waking on the new plugin
  needs NO migration commit (the store is lazily initialized under
  ``.git/``), and the gates must IGNORE the old v2 state files — a
  fresh-looking ``.critic-findings.json`` at HEAD and a populated
  ``.governance-ledger.jsonl`` — blocking loudly toward a fresh review
  rather than misreading them as current evidence (C3: no state a later
  reader mistakes for current). The tier-3 interlock is exercised in the
  other direction too: a fact written by a NEWER plugin fails both gates
  closed with the update-the-plugin remedy.

* **Discovery success criterion 3** — evidence composes across worktrees
  and sequential sessions: a review fact recorded in one worktree/session
  vouches for the same trees from any other checkout or later session,
  with no stale warning and no re-run.

Success criteria 1–4 trace (the chunk's acceptance bar — each criterion has
a named passing test or a pointer to the chunk that proved it):

1. *Zero silent failures* — ``tests/test_evidence_store.py::TestErrorPosture``
   (torn tail healed, interior corruption excluded loudly, schema-ahead
   surfaced; ch.01) and ``tests/test_cumulative_gate.py::TestFailClosed``
   (ch.04), plus ``TestSchemaAheadFailsClosed`` here end-to-end.
2. *A review is never re-run to relabel or re-persist* —
   ``tests/scenarios/test_kernel_v3_gate_cutover.py`` (CRT-J4PM + CRT-5D8Q
   reproductions, ch.04).
3. *Evidence composes across worktrees and sequential sessions* —
   ``TestWorktreeComposition`` and ``TestSequentialSessions`` here.
4. *No model writes protocol state* —
   ``tests/test_critic_consolidate.py::TestCriticBeginCLI`` (code writes
   the dispatch manifest) and ``tests/test_critic_consolidate.py::
   TestDeterministicCycleEndToEnd`` (code appends the fact and regenerates
   the derived cache; the model's only write is its judgment partial; ch.03).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Put the repo root on sys.path before importing lib/ — this module must be
# self-sufficient rather than depend on another test module having inserted it
# first (under parallel file distribution the two scenario files can land on
# different workers, so the ordering dependency flakes). Mirrors the idiom every
# other lib-importing test uses (e.g. tests/test_advisory_store.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.evidence import SCHEMA_VERSION  # noqa: E402
from kernel_v3_harness import (  # noqa: E402
    HOOK,
    _commit_all,
    _gate,
    _git,
    _hook,
    _run_review,
    _scratch_repo,
    _write_edit,
)

# These scenarios chain a dozen-plus subprocess invocations (two full session
# lifecycles each) — the suite-wide 30s per-test cap is too tight for the
# slowest of them on a loaded machine.
pytestmark = pytest.mark.timeout(60)


# ---------------------------------------------------------------------------
# Session-lifecycle helpers (the parts the cutover scenarios didn't need)
# ---------------------------------------------------------------------------


def _session_start(repo: Path) -> None:
    """A genuine session boundary: the SessionStart hook path (``clear
    --session-start``) — archives the old session's markers and records the
    new ``.session-start`` / ``.session-git-baseline`` / ``.session-base-tree``."""
    proc = _hook(repo, "clear", "--session-start")
    assert proc.returncode == 0, proc.stderr


def _stop(repo: Path) -> subprocess.CompletedProcess:
    """The Stop-hook gate. PATH is trimmed to the system dirs so the PR
    gate's ``gh`` probe can never leave the sandbox (hermetic, fast)."""
    return subprocess.run(
        ["python3", str(HOOK), "stop"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
        input="{}",
        env={
            "CLAUDE_PROJECT_DIR": str(repo),
            "PATH": "/usr/bin:/bin",
            "HOME": str(repo.parent / "_home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


def _write_reflection(repo: Path) -> None:
    """Satisfy the reflection gate so Stop-gate assertions isolate the
    Critic gate (the reflection gate is not under test here)."""
    (repo / ".prawduct" / ".session-reflected").write_text(
        "Scenario reflection: exercised the upgrade path end-to-end, "
        "observed the gates compose over the evidence store as designed.\n"
    )


def _write_active_build_plan(repo: Path) -> None:
    """An in-progress build plan — the Stop hook's Critic gate only arms for
    sessions working against one."""
    plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "# Build Plan\n\n## Status\n\n- [ ] Chunk 01: scenario work\n"
    )


def _store_file(repo: Path) -> Path:
    common = _git(repo, "rev-parse", "--git-common-dir")
    return (repo / common).resolve() / "prawduct" / "evidence.jsonl"


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


# ---------------------------------------------------------------------------
# C9 — a v2.3.3-era repo wakes up on the new plugin
# ---------------------------------------------------------------------------


def _v2_era_repo(tmp_path: Path) -> Path:
    """A repo as v2.3.3 left it: committed feature work, a fresh-looking
    single-slot findings record at HEAD (which satisfied the v2 PR gate),
    a populated governance ledger — and NO evidence store."""
    repo = _scratch_repo(tmp_path)
    _write_edit(repo, "feature.py", "y = 1\n")
    _commit_all(repo, "feature work")

    head = _git(repo, "rev-parse", "HEAD")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (repo / ".prawduct" / ".critic-findings.json").write_text(json.dumps({
        "timestamp": now,
        "mode": "cumulative (bundle review, ready for merge)",
        "mode_chosen_by": "explicit",
        "commit_reviewed": head,
        "files_reviewed": ["feature.py"],
        "findings": [],
        "summary": "v2-era bundle review — clean.",
    }))
    (repo / ".prawduct" / ".governance-ledger.jsonl").write_text(json.dumps({
        "schema_version": 1,
        "event": "review.critic",
        "ts": now,
        "project": "scenario",
        "git": {"head": head, "base": None},
        "review": {"mode": "cumulative", "findings_count": 0},
    }) + "\n")

    assert not _store_file(repo).exists(), "precondition: no v3 evidence store"
    return repo


class TestV2EraStateIgnored:
    def test_pr_gate_blocks_toward_a_fresh_review(self, tmp_path):
        # Under v2 this exact state passed the gate (cumulative record at
        # HEAD, fresh timestamp). v3 must not misread it as current — the
        # store has no facts, so the only honest answer is uncovered, with
        # the fresh-review remedy named.
        repo = _v2_era_repo(tmp_path)
        result = _gate(repo)
        assert result.returncode == 1, (
            f"v2-era records must not satisfy the v3 PR gate.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "uncovered" in result.stderr
        assert "/prawduct:critic cumulative" in result.stderr

    def test_stop_gate_blocks_toward_a_fresh_review(self, tmp_path):
        repo = _v2_era_repo(tmp_path)
        _write_active_build_plan(repo)
        _session_start(repo)
        _write_edit(repo, "more.py", "z = 1\n")
        _write_reflection(repo)

        result = _stop(repo)
        assert result.returncode == 2, (
            f"expected the Stop gate to block.\nstderr={result.stderr!r}"
        )
        assert "CRITIC REVIEW" in result.stderr
        assert "/prawduct:critic" in result.stderr
        # Isolation: the reflection gate was satisfied — the block above is
        # the Critic gate's, not a bystander's.
        assert "REFLECTION:" not in result.stderr

    def test_gate_reads_leave_no_migration_footprint(self, tmp_path):
        # The C9 tier-1 claim, observed: waking up on the new plugin costs
        # the consumer nothing — no store materializes from reads, nothing
        # new appears in the working tree, so there is no migration commit
        # for ANY consumer.
        repo = _v2_era_repo(tmp_path)
        before = _porcelain(repo)

        status = _hook(repo, "evidence", "status")
        assert status.returncode == 0, status.stderr
        assert "empty store" in status.stdout
        _gate(repo)

        assert _porcelain(repo) == before
        assert not _store_file(repo).exists(), (
            "gate reads must not materialize the store — it is created "
            "lazily on the first recorded fact"
        )

    def test_fresh_review_clears_the_block_with_no_migration_commit(self, tmp_path):
        # The remedy the gate named actually works, and the cutover still
        # leaves the working tree untouched: the store materializes under
        # .git/ on the first recorded fact.
        repo = _v2_era_repo(tmp_path)
        before = _porcelain(repo)
        assert _gate(repo).returncode == 1

        _run_review(repo, "cumulative")

        cleared = _gate(repo)
        assert cleared.returncode == 0, (
            f"the named remedy must clear the gate.\nstderr={cleared.stderr!r}"
        )
        assert "satisfied" in cleared.stdout
        assert _store_file(repo).exists()
        assert _porcelain(repo) == before


# ---------------------------------------------------------------------------
# C9 tier 3 — the version interlock in the other direction
# ---------------------------------------------------------------------------


class TestSchemaAheadFailsClosed:
    def _repo_with_ahead_fact(self, tmp_path) -> Path:
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _commit_all(repo, "feature work")
        # Simulate a NEWER plugin having written to the shared store (e.g. an
        # auto-update landed in another worktree). This reader cannot know
        # what the fact attests — and it may be the freshest review — so
        # both gates must fail closed with the exact remedy.
        store = _store_file(repo)
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps({
            "schema": SCHEMA_VERSION + 1,
            "kind": "review",
            "id": "rev-from-the-future",
            "ts": "2099-01-01T00:00:00Z",
        }) + "\n")
        return repo

    def test_pr_gate_fails_closed_with_update_remedy(self, tmp_path):
        repo = self._repo_with_ahead_fact(tmp_path)
        result = _gate(repo)
        assert result.returncode == 1
        assert "newer than this plugin" in result.stderr
        assert "Update the plugin" in result.stderr

    def test_stop_gate_fails_closed_with_update_remedy(self, tmp_path):
        repo = self._repo_with_ahead_fact(tmp_path)
        _write_active_build_plan(repo)
        _session_start(repo)
        _write_edit(repo, "more.py", "z = 1\n")
        _write_reflection(repo)

        result = _stop(repo)
        assert result.returncode == 2
        assert "newer plugin" in result.stderr
        assert "Update the plugin" in result.stderr


# ---------------------------------------------------------------------------
# Success criterion 3 — evidence composes across worktrees
# ---------------------------------------------------------------------------


class TestWorktreeComposition:
    def test_worktree_a_reviews_worktree_b_passes(self, tmp_path):
        # The full session lifecycle in BOTH checkouts — including that a
        # genuine session start in B (clear --session-start, which deletes
        # session markers and rewrites baselines) cannot damage the shared
        # evidence A recorded: the store is per-clone state under the git
        # common dir, not per-worktree session state.
        repo = _scratch_repo(tmp_path)
        _session_start(repo)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "feature^0")
        (wt / ".prawduct").mkdir(exist_ok=True)
        _session_start(wt)

        # Both checkouts resolve the SAME store file.
        assert _store_file(wt) == _store_file(repo)

        result = _gate(wt)
        assert result.returncode == 0, (
            f"worktree B must compose over the fact A recorded.\n"
            f"stderr={result.stderr!r}"
        )
        assert "1 review fact(s)" in result.stdout


# ---------------------------------------------------------------------------
# Success criterion 3 — evidence composes across sequential sessions
# ---------------------------------------------------------------------------


class TestSequentialSessions:
    def test_session_1_reviews_session_2_passes_with_no_stale_warning(self, tmp_path):
        # The v2 defect class: freshness was mtime-vs-.session-start, so any
        # later session called a perfectly good review "stale". v3: the fact
        # names the trees it reviewed, and trees don't age.
        repo = _scratch_repo(tmp_path)
        _session_start(repo)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        _session_start(repo)  # session 2 — .session-start now postdates the fact
        result = _gate(repo)
        assert result.returncode == 0, result.stderr
        assert "satisfied" in result.stdout
        assert "1 review fact(s)" in result.stdout
        assert "stale" not in (result.stdout + result.stderr).lower()

    def test_cross_session_composition_and_clean_session_end(self, tmp_path):
        # Session 2 does its own chunk on top of session 1's: its Stop gate
        # passes pre-commit on its OWN fact (base-tree marker → working
        # tree), and after the commit the PR gate composes BOTH sessions'
        # facts across the branch span — CRT-J4PM's history, now with a
        # session boundary in the middle.
        repo = _scratch_repo(tmp_path)
        _write_active_build_plan(repo)
        _session_start(repo)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        _session_start(repo)  # session 2
        _write_edit(repo, "more.py", "z = 1\n")
        _run_review(repo, "chunk")
        _write_reflection(repo)

        stopped = _stop(repo)  # pre-commit: dirty tree, reviewed verbatim
        assert stopped.returncode == 0, (
            f"session 2's Stop gate must pass on its own recorded fact.\n"
            f"stderr={stopped.stderr!r}"
        )
        assert "CRITIC REVIEW" not in stopped.stderr

        _commit_all(repo, "chunk 2")
        result = _gate(repo)
        assert result.returncode == 0, result.stderr
        assert "2 review fact(s)" in result.stdout
        assert "stale" not in (result.stdout + result.stderr).lower()
