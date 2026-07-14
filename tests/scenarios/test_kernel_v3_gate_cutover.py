"""End-to-end reproduction scenarios for the kernel-v3 gate cutover (ch.04).

Discovery success criterion 2, verbatim: the two defect sequences that
motivated the redesign must pass against the REAL plugin surface — the
repo-local ``bin/prawduct-hook`` driving the full dispatch → partial →
consolidate → gate pipeline in a scratch git repo (no in-process shortcuts,
no hand-written facts):

* **CRT-J4PM** — chunk-mode reviews recorded per-chunk (pre-commit, committed
  verbatim) compose across commits, and ``check-cumulative-critic`` passes at
  HEAD with NO cumulative-labeled review ever run. In v2 the gate demanded a
  record whose mode LABEL matched, so this exact history forced a redundant
  full re-review.

* **CRT-5D8Q** — the metadata-boundary deadlock cannot occur. In v2, two
  predicates drew the metadata boundary differently: ``_record_covers_head``
  exempted only ``.md`` (a committed ``.prawduct/`` state file made the
  record "stale") while the verify-resolutions scope helper filtered metadata
  out (so the recommended remedy could never re-cover it) — a wedge with no
  exit. In v3 ONE predicate (``coverage_algebra.is_judgeable_path``) answers
  both gates: a metadata-only tail is a free edge and the gate passes; a
  judgeable tail still blocks and the verify-resolutions flow genuinely
  clears it (the exit exists).
"""

from __future__ import annotations

# Harness — everything through subprocess, like production; shared with the
# chunk-06 upgrade scenarios (kernel_v3_harness.py).
from kernel_v3_harness import (
    _commit_all,
    _gate,
    _git,
    _run_review,
    _scratch_repo,
    _write_edit,
)


# ---------------------------------------------------------------------------
# CRT-J4PM — composition replaces mode-label matching
# ---------------------------------------------------------------------------


class TestCrtJ4pmReproduction:
    def test_chunk_reviews_compose_to_pass_the_pr_gate_with_no_rerun(self, tmp_path):
        repo = _scratch_repo(tmp_path)

        # Chunk 1: edit → chunk review on the dirty tree → commit verbatim.
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        # Chunk 2: same cycle again.
        _write_edit(repo, "more.py", "z = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 2")

        # The v2 defect: gate demanded a cumulative-labeled record and failed
        # here, forcing a redundant bundle re-review. v3: the two chunk facts
        # compose merge-base tree → HEAD tree — pass, no re-run.
        result = _gate(repo)
        assert result.returncode == 0, (
            f"CRT-J4PM repro must pass with no cumulative re-run.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "satisfied" in result.stdout
        assert "2 review fact(s)" in result.stdout

    def test_gate_passes_from_a_second_worktree(self, tmp_path):
        # The store is per-clone (D1): evidence recorded in the primary
        # checkout vouches for the same trees from a linked worktree.
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "feature^0")
        (wt / ".prawduct").mkdir(exist_ok=True)
        result = _gate(wt)
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# CRT-5D8Q — one predicate, no metadata-boundary deadlock
# ---------------------------------------------------------------------------


class TestCrt5d8qReproduction:
    def test_metadata_only_tail_cannot_wedge_the_gate(self, tmp_path):
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")
        assert _gate(repo).returncode == 0

        # The v2 deadlock trigger: a committed non-.md METADATA change after
        # the review. _record_covers_head called it stale (non-.md), while
        # the verify-scope helper filtered it out (metadata) — no review the
        # gate recommended could ever re-cover it. v3: metadata is never
        # judgeable, the interval is a free edge, the gate stays green.
        _write_edit(repo, ".prawduct/project-state.yaml", "product_identity:\n  name: X\n")
        _commit_all(repo, "state bookkeeping")
        result = _gate(repo)
        assert result.returncode == 0, (
            f"metadata-only tail must not wedge the gate (CRT-5D8Q).\n"
            f"stderr={result.stderr!r}"
        )

    def test_judgeable_tail_blocks_and_verify_resolutions_genuinely_clears_it(self, tmp_path):
        # The contrast half: a judgeable tail still blocks (no silent
        # carveout), and the remedy the message names actually works — the
        # exit that v2's deadlock lacked.
        repo = _scratch_repo(tmp_path)
        _write_edit(repo, "feature.py", "y = 1\n")
        _run_review(repo, "chunk")
        _commit_all(repo, "chunk 1")

        _write_edit(repo, "hotfix.py", "h = 1\n")
        _commit_all(repo, "unreviewed hotfix")
        blocked = _gate(repo)
        assert blocked.returncode == 1
        assert "uncovered" in blocked.stderr
        assert "verify-resolutions" in blocked.stderr

        _run_review(repo, "verify-resolutions")
        cleared = _gate(repo)
        assert cleared.returncode == 0, (
            f"the named remedy must clear the gate.\nstderr={cleared.stderr!r}"
        )
