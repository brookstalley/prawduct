"""The PR gate answers by composition (kernel-v3 chunk 04 — design Q1/D6).

``gates.check_cumulative_critic`` asks ONE question: does composed review
coverage span ``merge-base(base_branch, HEAD)`` → ``HEAD`` *by tree*, with
zero unresolved blocking findings on the path? Evidence is facts in the
shared store; no mode label, file mtime, ``extends_cumulative`` chain, or
``.critic-findings.json`` read participates — those v2 mechanisms are
deleted, and each deleted acceptance keeps a still-blocks regression here
(learnings: every skip-gate needs a test that a non-eligible case still
BLOCKS):

* mode-label acceptance → labels are never consulted: chunk-labeled facts
  compose to a pass (CRT-J4PM), and NO label makes an under-spanning fact
  pass.
* ``_record_covers_head`` (.md-tail rule) → an unreviewed judgeable commit
  after the reviewed tree still blocks; a non-judgeable tail composes as a
  free edge; a governance-protected ``.md`` tail still blocks (CRT-5D8Q:
  one predicate, one answer).
* mtime freshness → facts never expire: trees compose, they don't age.
* ledger fallback → subsumed: the store is multi-record, so a later chunk
  review can't destroy the PR gate's evidence.

Real git repos throughout (the gate shells out for merge-base and tree
diffs); facts are written through ``evidence.append_fact`` — the same
writer consolidation uses.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
from lib import evidence, gates  # noqa: E402

_ids = itertools.count(1)


# ---------------------------------------------------------------------------
# Helpers
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


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _branch_repo(tmp_path: Path) -> Path:
    """main with one commit, feature branch with one code commit on top —
    merge-base(main, HEAD) is main's tip, the canonical PR shape."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature.py", "y = 2\n", "f1")
    return repo


def _fact(
    repo: Path,
    base_tree: str,
    head_tree: str,
    files: list[str],
    *,
    files_reviewed: "list[str] | None" = None,
    findings: "list[dict] | None" = None,
    mode: str = "chunk (lighter pass, not ready for push)",
) -> str:
    fact_id = f"rev-test-{next(_ids):04d}"
    result = evidence.append_fact(
        repo,
        "review",
        fact_id,
        {
            "base_tree": base_tree,
            "head_tree": head_tree,
            "files_changed": list(files),
            "files_reviewed": list(files_reviewed if files_reviewed is not None else files),
            "findings": findings or [],
            "mode": mode,
        },
    )
    assert result["status"] == "appended", result
    return fact_id


def _resolution(repo: Path, review_id: str, fid: str, disposition: str = "fixed") -> None:
    result = evidence.append_fact(
        repo,
        "resolution",
        f"res-test-{next(_ids):04d}",
        {"finding": {"review_id": review_id, "fid": fid}, "disposition": disposition},
    )
    assert result["status"] == "appended", result


def _run_gate(repo: Path, capsys) -> tuple[int, str, str]:
    rc = gates.check_cumulative_critic(repo)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ---------------------------------------------------------------------------
# Composition passes — no label ever consulted
# ---------------------------------------------------------------------------


class TestComposedCoveragePasses:
    def test_single_fact_spanning_merge_base_to_head_passes(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "satisfied" in out

    def test_crt_j4pm_chunk_facts_compose_no_matching_label_needed(self, tmp_path, capsys):
        # THE composition fix: chunk-labeled reviews recorded per-chunk span
        # the bundle; the gate at HEAD passes with no re-run and no
        # cumulative-labeled record anywhere.
        repo = _branch_repo(tmp_path)
        t1 = _tree(repo)
        _commit(repo, "more.py", "z = 3\n", "f2")
        t2 = _tree(repo)
        _fact(repo, _tree(repo, "main"), t1, ["feature.py"])
        _fact(repo, t1, t2, ["more.py"])
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "2 review fact(s)" in out

    def test_facts_from_a_prior_session_never_expire(self, tmp_path, capsys):
        # mtime-freshness still-works regression: nothing compares timestamps —
        # a fact whose session is long gone still vouches for its trees.
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        store = evidence.store_path(repo)
        lines = [json.loads(line) for line in store.read_text().splitlines()]
        for line in lines:
            line["ts"] = "2001-01-01T00:00:00Z"
            line["actor"]["session"] = "1999-12-31T00:00:00Z"
        store.write_text("".join(json.dumps(line) + "\n" for line in lines))
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 0, err

    def test_non_judgeable_tail_composes_as_free_edge(self, tmp_path, capsys):
        # The doc-only allowance, computed not stored: a plain-.md commit
        # after the reviewed tree needs no review.
        repo = _branch_repo(tmp_path)
        reviewed = _tree(repo)
        _fact(repo, _tree(repo, "main"), reviewed, ["feature.py"])
        _commit(repo, "notes.md", "notes\n", "docs")
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "free edge" in out

    def test_empty_span_passes_trivially(self, tmp_path, capsys):
        # On the base branch itself, merge-base tree == HEAD tree — nothing
        # to review, nothing to block on.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "code.py", "x = 1\n", "c1")
        rc, out, _err = _run_gate(repo, capsys)
        assert rc == 0
        assert "empty span" in out

    def test_squash_merge_tree_identity_composes(self, tmp_path, capsys):
        # A squash commit carries the same tree as the reviewed branch tip, so
        # the reviewed-tree fact vouches for it (D3).
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "--squash", "-q", "feature")
        _git(repo, "commit", "-q", "-m", "squash: feature")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 0, err

    def test_verify_resolutions_at_committed_head_composes_over_fix_commit(self, tmp_path, capsys):
        # CRT-7H2W: a post-cumulative fix COMMIT is judgeable, so the cumulative
        # fact alone does not cover it (cf. test_unreviewed_judgeable_commit_...
        # _blocks). A verify-resolutions fact anchored at the COMMITTED HEAD tree
        # — what begin_review now records when a committed delta exists since the
        # prior review — bridges reviewed-tree -> committed HEAD, so the gate
        # composes. Anchored at a dirty WORKING tree it would not; that is the
        # point of the intent-aware head anchor.
        repo = _branch_repo(tmp_path)
        reviewed = _tree(repo)  # T_c — the cumulative-reviewed feature tip
        _fact(repo, _tree(repo, "main"), reviewed, ["feature.py"])
        _commit(repo, "feature.py", "y = 3  # fixed\n", "fix blocker")
        fixed = _tree(repo)  # T_c2 — committed HEAD after the fix commit
        _fact(
            repo, reviewed, fixed, ["feature.py"],
            mode="verify-resolutions (delta review, prior findings only)",
        )
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 0, err


# ---------------------------------------------------------------------------
# Still blocks — one regression per deleted v2 acceptance path
# ---------------------------------------------------------------------------


class TestStillBlocks:
    def test_no_facts_blocks_with_cumulative_remedy(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "/prawduct:critic cumulative" in err

    def test_unreviewed_judgeable_commit_after_review_blocks(self, tmp_path, capsys):
        # Replaces _record_covers_head's stale verdict: the tail commit's tree
        # was never reviewed and touches code — no free edge, no pass.
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        _commit(repo, "sneaky.py", "s = 1\n", "unreviewed code")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        # The selective-commit caveat (D3): the message names the v-r remedy.
        assert "verify-resolutions" in err

    def test_protected_md_tail_still_blocks(self, tmp_path, capsys):
        # CRT-5D8Q pin at the PR boundary: skills/ prose is judgeable, so the
        # doc-only free edge must NOT absorb it.
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        _commit(repo, "skills/demo/SKILL.md", "prose\n", "skill prose")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err

    def test_under_reviewed_fact_is_not_an_edge(self, tmp_path, capsys):
        # A scoped review that saw less than its diff weakens coverage, never
        # strengthens it (D6 edge validity).
        repo = _branch_repo(tmp_path)
        _commit(repo, "other.py", "o = 1\n", "f2")
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py", "other.py"],
            files_reviewed=["feature.py"],
        )
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err

    def test_rebased_history_gap_blocks(self, tmp_path, capsys):
        # Rebase/amend changes the tree → coverage gap → re-review (D3,
        # correct by design).
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        (repo / "feature.py").write_text("y = 99\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "--amend", "--no-edit")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1

    def test_unknown_fact_kind_never_satisfies(self, tmp_path, capsys):
        # Forward-compat (D2/Q9): a future kind coexists but cannot satisfy a
        # gate it wasn't written for.
        repo = _branch_repo(tmp_path)
        store = evidence.store_path(repo)
        store.parent.mkdir(parents=True, exist_ok=True)
        with open(store, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "schema": 1,
                        "kind": "test-run",
                        "id": "tr-1",
                        "ts": "2026-07-13T00:00:00Z",
                        "body": {
                            "base_tree": _tree(repo, "main"),
                            "head_tree": _tree(repo),
                            "files_changed": ["feature.py"],
                            "files_reviewed": ["feature.py"],
                        },
                    }
                )
                + "\n"
            )
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err


# ---------------------------------------------------------------------------
# Blocking findings and resolutions (D5 join)
# ---------------------------------------------------------------------------


class TestBlockingAndResolutions:
    def test_unresolved_blocking_finding_blocks_and_lists_it(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rid = _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "blocking" in err
        assert f"{rid}/R-1" in err
        assert "boom" in err
        assert "verify-resolutions" in err

    def test_resolution_fact_unblocks_without_rereview(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rid = _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        _resolution(repo, rid, "R-1", "fixed")
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "satisfied" in out

    def test_waived_disposition_also_resolves(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rid = _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        _resolution(repo, rid, "R-1", "waived")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 0, err


# ---------------------------------------------------------------------------
# Fail-closed paths
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_schema_ahead_fact_blocks_with_remedy_even_when_covered(self, tmp_path, capsys):
        # C9 tier 3: a fact from a newer plugin may be the freshest review —
        # this reader cannot know, so it must never pass around it.
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        store = evidence.store_path(repo)
        with open(store, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"schema": 99, "kind": "review", "id": "future-1", "ts": "t", "body": {}}
                )
                + "\n"
            )
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "schema-ahead" in err
        assert "Update the plugin" in err

    def test_unresolvable_configured_base_fails_closed(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("base_branch: nonexistent\n")
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "no-base" in err

    def test_no_git_repo_fails_closed(self, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()
        rc, _out, _err = _run_gate(plain, capsys)
        assert rc == 1


# ---------------------------------------------------------------------------
# Source-level pins: the deleted mechanisms stay deleted
# ---------------------------------------------------------------------------


class TestDeletedMechanismsStayDeleted:
    def test_gate_module_never_opens_the_findings_cache(self):
        # Acceptance criterion (chunk 04): no gate reads .critic-findings.json.
        # The quoted literal is the path-construction form; docstrings that
        # narrate history use the double-backtick form and don't match.
        source = (ROOT / "lib" / "gates.py").read_text()
        assert '".critic-findings.json"' not in source

    def test_deleted_symbols_are_gone(self):
        source = (ROOT / "lib" / "gates.py").read_text()
        for symbol in (
            "def _record_covers_head",
            "def _compute_verify_resolutions_scope",
            "def _verify_resolutions_gate_check",
            "def critic_findings_satisfy_session_gate",
            "def _ledger_fallback_record",
            "def _pr_gate_record_qualifies",
            "def _evaluate_pr_gate_record",
            "def _chain_anchor",
        ):
            assert symbol not in source, f"{symbol} should be deleted (chunk 04)"

    def test_hook_no_longer_dispatches_verify_resolutions_scope(self):
        source = (ROOT / "bin" / "prawduct-hook").read_text()
        assert "compute-verify-resolutions-scope" not in source
