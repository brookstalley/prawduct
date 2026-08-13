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

ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(ROOT))
from lib import coverage, evidence, gates  # noqa: E402

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


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _advance_and_merge(repo: Path, *, merge: bool = True) -> None:
    """Move ``main`` forward by one commit touching a file the feature branch
    never saw, then bring it into the branch — by merge (the common shape) or
    by rebase (which rewrites the very commits the branch's facts anchor to)."""
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.py", "u = 1\n", "u1")
    _git(repo, "checkout", "-q", branch)
    if merge:
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
    else:
        _git(repo, "rebase", "-q", "main")


def _advanced_base_repo(
    tmp_path: Path, *, merge: bool = True, branch_file: str = "feature.py"
) -> tuple[Path, str, str]:
    """The F1 shape: a feature branch reviewed at its tip, then the base
    advances into it touching nothing the branch changed. Returns the repo and
    the reviewed span's endpoints. ``branch_file`` names the branch's one
    judgeable file, so a test can put a hostile name on the path condition 2
    compares."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, branch_file, "y = 2\n", "f1")
    prior_base, prior_head = _tree(repo, "main"), _tree(repo)
    # The fact's `files_changed` snapshot comes from `evidence.tree_diff`, the
    # way `begin_review` produces it — not from a hand-written literal. With a
    # hostile filename the two differ (a hand-written raw name would be pruned
    # out before the check under test is ever reached), and a fixture that
    # cannot reach the subject passes forever.
    _fact(
        repo,
        prior_base,
        prior_head,
        evidence.tree_diff(repo, prior_base, prior_head),
        head_commit=_head(repo),
    )
    _advance_and_merge(repo, merge=merge)
    return repo, prior_base, prior_head


def _write_test_evidence(
    repo: Path, *, failed: int = 0, tree: "str | None" = ..., omit_tree: bool = False
) -> None:
    """Saved test evidence in the shape ``gates.suite_vouches_for_current_tree``
    accepts: a run whose recorded ``evidence_tree`` is the CURRENT working tree.

    Timing is deliberately not what the transfer's condition 3 reads, so these
    fixtures cannot be satisfied by a plausible-looking timestamp — pass
    ``tree=<some other tree>`` to model the run that happened before the base
    advance, or ``omit_tree=True`` to model a record that cannot answer at all.
    """
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": "2026-08-13T12:00:00Z",
        "passed": 12,
        "failed": failed,
        "skipped": 0,
        "duration_seconds": 3,
        "command": "pytest",
        "verifier": "test-reference-verify (floor: symbol-grep)",
        "tests_executed": ["tests/test_x.py"],
        "changes_referenced": ["feature.py"],
        "coverage_level": "referenced",
    }
    if not omit_tree:
        record["evidence_tree"] = (
            evidence.capture_tree(repo)["tree"] if tree is ... else tree
        )
    (prawduct / ".test-evidence.json").write_text(json.dumps(record))


def _stale_origin_repo(
    tmp_path: Path, *, push_after_prep: bool = False, feature_on_local: bool = True
) -> Path:
    """A repo whose ``origin/main`` trails local ``main`` — the COV-7K4N shape.

    ``origin/main`` == c1; local ``main`` then gains an unpushed ``release-prep``
    commit; a feature branch is cut on top of local ``main`` (or, when
    ``feature_on_local`` is False, on ``origin/main`` so local ``main`` is NOT
    an ancestor of HEAD — the diverged case where pushing wouldn't help). With
    ``base_branch`` unset the gate resolves the base to ``origin/main``, so
    merge-base anchors to the stale c1 and the whole unshipped range reads as
    the required span."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(origin)],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")  # origin/main == c1
    _commit(repo, "VERSION", "1.0.1\n", "release-prep(v1.0.1): bump version")
    if push_after_prep:
        _git(repo, "push", "-q", "origin", "main")  # remote caught up → not stale
    start = "main" if feature_on_local else "origin/main"
    _git(repo, "checkout", "-q", "-b", "feature", start)
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
    head_commit: "str | None" = None,
    counts: "dict | None" = None,
    dispatch_commit: "str | None" = None,
    duration_seconds: "float | None" = None,
) -> str:
    fact_id = f"rev-test-{next(_ids):04d}"
    body = {
        "base_tree": base_tree,
        "head_tree": head_tree,
        "files_changed": list(files),
        "files_reviewed": list(files_reviewed if files_reviewed is not None else files),
        "findings": findings or [],
        "mode": mode,
    }
    # `head_commit` is written by `build_fact_body` on every real consolidation;
    # it is optional here because most of this file's cases compose purely by
    # tree and never need the commit. `diagnose_fix_churn` does — it is the only
    # thing that can place a fact on HEAD's lineage.
    if head_commit is not None:
        body["head_commit"] = head_commit
    if counts is not None:
        body["counts"] = counts
    # A real dirty-tree review records `head_commit: null` and keeps the commit
    # HEAD sat at in `dispatch_commit` — the only thing that can place THAT
    # round on a branch, which is why `count_branch_rounds` falls back to it.
    if dispatch_commit is not None:
        body["dispatch_commit"] = dispatch_commit
    if duration_seconds is not None:
        body["duration_seconds"] = duration_seconds
    result = evidence.append_fact(repo, "review", fact_id, body)
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
# Stale remote base — the uncovered path names the cheap remedy (COV-7K4N)
# ---------------------------------------------------------------------------


class TestStaleBaseHint:
    """The false-``uncovered`` case where ``origin/<b>`` trails an ancestor-of-HEAD
    local ``<b>``: the gate must surface ``git push origin <b>`` (cheap, correct)
    BEFORE the generic full-review remedy, and must NOT surface it when pushing
    wouldn't move the merge-base."""

    def test_hint_when_origin_behind_ancestor_local(self, tmp_path, capsys):
        repo = _stale_origin_repo(tmp_path)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "behind local main" in err
        assert "git push origin main" in err
        assert "release-prep(v1.0.1" in err  # the phantom-release signal is named
        assert "/prawduct:critic cumulative" in err  # generic remedy still offered

    def test_no_hint_when_remote_current(self, tmp_path, capsys):
        # Local main pushed → origin is up to date; the feature is still
        # uncovered (no facts), but there is nothing stale to push.
        repo = _stale_origin_repo(tmp_path, push_after_prep=True)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "git push origin" not in err
        assert "/prawduct:critic cumulative" in err

    def test_no_hint_when_local_diverged_from_head(self, tmp_path, capsys):
        # Local main is ahead of origin but NOT an ancestor of HEAD (feature cut
        # from origin/main) — pushing wouldn't advance the merge-base, so the
        # ancestor guard suppresses the hint.
        repo = _stale_origin_repo(tmp_path, feature_on_local=False)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "behind local" not in err


class TestBaseAdvanceTransfer:
    """A base sync moves the span's START node, so a branch whose own diff did
    not move a byte reads ``uncovered`` and buys a full re-review. Coverage
    **transfers** across the advance when the branch diff is byte-identical in
    both spans, the advance touched none of its files, and the suite is current.

    Every denial fixture here is the point of the class as much as the grant is:
    the transfer is byte equality across contexts, never content equivalence
    within one (COV-3M8Q stands), so any edit at all to a branch file — and any
    check that cannot be computed — denies it.
    """

    def test_clean_base_merge_transfers(self, tmp_path, capsys):
        repo, prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out
        assert prior_base[:12] in out
        assert "byte-identical" in out

    def test_transfer_survives_a_verify_pass_between_review_and_sync(
        self, tmp_path, capsys
    ):
        # The covered span is composed, not carried by one fact: a cumulative
        # (merge-base → tip) then a verify pass (tip → fixed tip). Its endpoints
        # live on DIFFERENT facts, so a per-fact candidate search misses it.
        repo = _branch_repo(tmp_path)
        prior_base, reviewed = _tree(repo, "main"), _tree(repo)
        _fact(repo, prior_base, reviewed, ["feature.py"], head_commit=_head(repo))
        _commit(repo, "feature.py", "y = 2\nz = 3\n", "fix")
        _fact(repo, reviewed, _tree(repo), ["feature.py"], head_commit=_head(repo))
        _advance_and_merge(repo)
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out
        assert "2 review fact(s)" in out

    def test_rebase_onto_the_advanced_base_transfers(self, tmp_path, capsys):
        # Rebasing rewrites the commits the branch's facts anchor to, so a
        # commit-ancestry candidate filter would exclude every one of them —
        # while the trees they vouch for are untouched and the branch diff is
        # still byte-identical.
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path, merge=False)
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out

    def test_edit_to_a_branch_file_during_the_merge_denies(self, tmp_path, capsys):
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _commit(repo, "feature.py", "y = 2  # touched up\n", "tweak after merge")
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "transferred" not in err

    def test_upstream_touching_a_branch_file_denies(self, tmp_path, capsys):
        # The advance moved a file the branch also changed, so blob(base, f) !=
        # blob(base', f) — the branch diff is no longer the one that was
        # reviewed, whether or not git had to raise a conflict about it.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "code.py", "a = 1\n\n\n\n\n\nz = 9\n", "c1")
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "code.py", "a = 2\n\n\n\n\n\nz = 9\n", "f1")
        _fact(repo, _tree(repo, "main"), _tree(repo), ["code.py"], head_commit=_head(repo))
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "code.py", "a = 1\n\n\n\n\n\nz = 10\n", "u1")
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "transferred" not in err

    def test_stale_test_evidence_denies_and_names_the_cheap_remedy(
        self, tmp_path, capsys
    ):
        # Condition 3 alone missing is the near miss worth naming: running the
        # suite is minutes, and the alternative the generic block prescribes is
        # a full cumulative.
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "ONLY condition denying the transfer" in err
        assert "no .test-evidence.json on disk" in err
        assert "test-evidence record" in err

    def test_a_suite_run_predating_the_advance_denies(self, tmp_path, capsys):
        # The hole `tests_are_current` would have left open: a run from earlier
        # in the same session satisfies session-freshness while having never
        # seen the merged tree — which is the ONE exposure condition 3 exists to
        # price. Timing must not be able to answer this question.
        repo, _prior_base, prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo, tree=prior_head)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "transferred" not in err
        assert "judgeable path(s) changed since the run" in err

    def test_evidence_without_a_recorded_tree_denies(self, tmp_path, capsys):
        # A `--from-counts` record cannot say which tree it ran against, so it
        # cannot answer condition 3 — deny rather than fall back to timing.
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo, omit_tree=True)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "records no evidence_tree" in err

    def test_a_glob_metacharacter_filename_is_compared_as_itself(
        self, tmp_path, capsys
    ):
        # Condition 2 asks git "do these trees differ on THESE paths", and a
        # pathspec is a wildmatch pattern. Git matches literally as well, so the
        # branch's own `x[a].py` is never MISSED — but as a pattern it also
        # selects `xa.py`, and here the base advance changed exactly that file.
        # Without `:(literal)` an unrelated file answers the question, the base
        # endpoint is rejected, and a sound transfer is silently denied.
        #
        # This is the assertion that distinguishes the two spellings: the
        # edited-file DENIAL passes either way, so it pins nothing.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "xa.py", "unrelated = 1\n", "c1")
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "x[a].py", "route = 1\n", "f1")
        _fact(repo, _tree(repo, "main"), _tree(repo), ["x[a].py"], head_commit=_head(repo))
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "xa.py", "unrelated = 2\n", "u1")  # the advance, in the glob's shadow
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out

    def test_a_non_ascii_branch_filename_is_compared_as_itself(
        self, tmp_path, capsys
    ):
        # `git diff --name-only` honours core.quotepath (on by default), so a
        # non-ASCII path comes back C-quoted — `"caf\303\251.py"`, quotes and
        # all. Sent back as a pathspec that string matches nothing, git reports
        # "no difference" over a file it never compared, and condition 2 passes
        # vacuously: a fail-OPEN that `:(literal)` alone does not close, because
        # the corruption happens on the way OUT. Hence `-z`.
        repo, _prior_base, _prior_head = _advanced_base_repo(
            tmp_path, branch_file="café.py"
        )
        _commit(repo, "café.py", "y = 2  # edited after the review\n", "tweak")
        _write_test_evidence(repo)
        rc, out, _err = _run_gate(repo, capsys)
        assert rc == 1, out
        assert "transferred" not in out

    def test_a_non_ascii_branch_filename_still_transfers_when_untouched(
        self, tmp_path, capsys
    ):
        repo, _prior_base, _prior_head = _advanced_base_repo(
            tmp_path, branch_file="café.py"
        )
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out

    def test_a_glob_metacharacter_filename_still_denies_when_edited(
        self, tmp_path, capsys
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "code.py", "x = 1\n", "c1")
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "app/[id]/page.py", "route = 1\n", "f1")
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["app/[id]/page.py"],
            head_commit=_head(repo),
        )
        _advance_and_merge(repo)
        _commit(repo, "app/[id]/page.py", "route = 2\n", "edit after review")
        _write_test_evidence(repo)
        rc, out, _err = _run_gate(repo, capsys)
        assert rc == 1, out
        assert "transferred" not in out

    def test_failing_saved_tests_deny(self, tmp_path, capsys):
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo, failed=2)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "2 test(s) failing" in err

    def test_unreadable_git_object_fails_closed_and_says_so(self, tmp_path, capsys):
        # A candidate tree git cannot read must deny the transfer, and the
        # degraded check must say it never ran — "advice fails soft" is not
        # "advice fails silent".
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo)
        store = evidence.store_path(repo)
        lines = [json.loads(line) for line in store.read_text().splitlines()]
        for line in lines:
            if line.get("kind") == "review":
                line["body"]["head_tree"] = "0" * 40  # well-formed, absent
        store.write_text("".join(json.dumps(line) + "\n" for line in lines))
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "base-advance transfer check could not run" in err

    def test_a_blocked_prior_span_transfers_nothing(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            head_commit=_head(repo),
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "unsound"}],
        )
        _advance_and_merge(repo)
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "transferred" not in err

    def test_no_prior_review_leaves_uncovered_untouched(self, tmp_path, capsys):
        # The still-blocks regression: an unreviewed branch on an advanced base
        # gets exactly today's message, transfer machinery or not.
        repo = _branch_repo(tmp_path)
        _advance_and_merge(repo)
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "/prawduct:critic cumulative" in err
        assert "transfer" not in err

    def test_new_work_alongside_the_sync_denies(self, tmp_path, capsys):
        # The file set grew, so the reviewed span is not this span — set
        # equality, not the containment the blob checks already force.
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _commit(repo, "extra.py", "w = 4\n", "new work")
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "transferred" not in err

    def test_non_judgeable_conflict_resolution_does_not_deny(self, tmp_path, capsys):
        # The measured case: on both observed forced syncs, 100% of the
        # conflicts were prawduct's own record files — non-judgeable paths that
        # must not cost a review round.
        repo, _prior_base, _prior_head = _advanced_base_repo(tmp_path)
        _commit(repo, ".prawduct/change-log.md", "reconciled\n", "chore: reconcile")
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out


class TestFixChurnDiagnosis:
    """An ``uncovered`` gap whose whole content is the builder's own
    non-blocking fixes must SAY so and name ``disposition`` — otherwise the
    only route the message offers is another 4-10 minute round, which reviews
    the prose the last fix wrote and supplies the next round's findings. The
    ten-round consumer branch that motivated this reached round 5+ entirely
    this way.

    The discriminator is what moved the tree, never a round counter: CRT-3W6P's
    counter-example is a post-merge round that looked identical from a counter
    and was genuinely required. Every negative case below is a shape that must
    stay silent, because telling a builder their gap is self-inflicted when it
    is real would send unreviewed work to merge."""

    def _reviewed_feature(self, tmp_path, **fact_kw):
        """feature.py reviewed at f1 with two non-blocking findings naming it."""
        repo = _branch_repo(tmp_path)
        rid = _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[
                {"fid": "R-1", "severity": "warning", "title": "w",
                 "files": ["feature.py"]},
                {"fid": "R-2", "severity": "note", "title": "n",
                 "files": ["feature.py"]},
            ],
            counts={"blocking": 0, "warning": 1, "note": 1},
            head_commit=_git(repo, "rev-parse", "HEAD"),
            **fact_kw,
        )
        return repo, rid

    def test_the_slow_path_cannot_be_reached_by_forgetting_an_argument(self):
        """The accepted Chunk 01 finding this resolves was 'the n-squared path
        is reachable by default', and deleting the defaults is the whole fix —
        so the fix needs a pin, or a later editor restores a default for
        convenience and nothing notices until a `/prawduct:pr create` hangs for
        five minutes.

        Asserted on the SIGNATURE, not by calling: `diagnose_fix_churn` never
        raises by contract, so a behavioural probe would have to reach the
        `coverage_verdict` call to see anything, and both parameters must be
        required at the boundary regardless of what the body does. The sibling
        one frame up (`_merge_base_verdict`) carried the identical unreachable
        default and is pinned here too — same call chain, same slow path, same
        gate.
        """
        import inspect

        from lib import coverage

        # The injected names changed when the verdict gained a memo — the two
        # diagnoses now receive `verdict_fn`, which carries BOTH properties a
        # forgotten argument would cost: the n-key free-edge form and the
        # cross-call cache. Same contract, same direction, applied to whichever
        # parameter now holds it; nothing here is relaxed.
        pinned = {
            coverage.diagnose_fix_churn: ("verdict_fn",),
            coverage.diagnose_base_advance_transfer: ("diff_fn", "verdict_fn"),
            gates._merge_base_verdict: ("diff_fn", "key_fn"),
        }
        for fn, names in pinned.items():
            params = inspect.signature(fn).parameters
            for name in names:
                assert params[name].default is inspect.Parameter.empty, (
                    f"{fn.__name__}'s {name} has a default again. A missing "
                    "argument then silently selects the pairwise free-edge "
                    "branch (~5.6k `git diff` subprocesses on this repo's "
                    "store) or an uncached recomputation (17 s on this repo's "
                    "store) on the interactive PR path, instead of raising a "
                    "TypeError the caller can see."
                )

    def test_fix_commit_on_named_file_is_diagnosed_as_churn(self, tmp_path, capsys):
        repo, rid = self._reviewed_feature(tmp_path)
        _commit(repo, "feature.py", "y = 3  # addressed R-1\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "fix churn" in err
        assert rid in err
        assert "feature.py" in err
        # The claim must not exceed the evidence. The subset test is FILE
        # granular, so it cannot tell a fix from new work written into a file
        # some finding merely named — and the remedy it routes to
        # (`verify-resolutions`) records BLOCKING findings only, so an
        # overclaim here sends genuinely unreviewed content to the narrowest
        # review in the framework. The message says what it actually proved.
        assert "FILE-level evidence" in err
        assert "is your fix churn, not unreviewed work" not in err, (
            "the gate asserts content-level certainty on file-level evidence again"
        )
        # Both routes out are named, and the cheap one is named first.
        assert "prawduct-hook disposition" in err
        assert err.index("fix churn") < err.index("/prawduct:critic cumulative")
        # ...and the generic route no longer CONTRADICTS the cheap one. Ordering
        # was pinned; agreement was not, and an agent reading a stderr block
        # commonly acts on the last imperative — which unqualified is the 4-10
        # minute round this control exists to displace.
        assert "If that diagnosis does not fit" in err
        assert err.index("If that diagnosis does not fit") < err.index(
            "/prawduct:critic cumulative"
        ), "the generic block is unqualified again, so the last imperative wins"
        # The counts it quotes come from the fact, not from a guess.
        assert "1 warning + 1 note" in err

    def test_the_churn_note_names_the_command_that_prices_the_next_commit(
        self, tmp_path, capsys
    ):
        """`cost-of-commit` is useless to a builder who does not know it exists,
        and a command nobody knows about is a PULL carrier — the exact failure
        the push carriers were built to fix. This block is where the builder is
        standing when they decide whether to make one more commit, so it is
        where the command has to be named."""
        repo, _rid = self._reviewed_feature(tmp_path)
        _commit(repo, "feature.py", "y = 3  # addressed R-1\n", "fix the warning")
        _rc, _out, err = _run_gate(repo, capsys)
        assert "fix churn" in err
        assert "prawduct-hook cost-of-commit" in err

    def test_change_outside_the_named_files_is_not_churn(self, tmp_path, capsys):
        # CRT-3W6P's counter-example in miniature: the tree moved for a reason
        # the review loop did not cause, so the round it needs is real.
        repo, _rid = self._reviewed_feature(tmp_path)
        _commit(repo, "other.py", "z = 9\n", "unrelated work")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "fix churn" not in err

    def test_partial_overlap_is_not_churn(self, tmp_path, capsys):
        # One named file plus one nobody reviewed: not a subset, so the claim
        # "this is only your churn" would be false. Stay silent.
        repo, _rid = self._reviewed_feature(tmp_path)
        (repo / "feature.py").write_text("y = 3\n")
        (repo / "new.py").write_text("brand = 'new'\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "fix plus new work")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_unresolved_blocking_never_diagnoses_as_churn(self, tmp_path, capsys):
        # The round IS required here, so the message must not suggest the
        # builder could disposition their way out of it.
        repo = _branch_repo(tmp_path)
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "blocking", "title": "boom",
                       "files": ["feature.py"]}],
            counts={"blocking": 1, "warning": 0, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _commit(repo, "feature.py", "y = 3\n", "fix the blocker")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_sibling_branch_fact_does_not_anchor_the_diagnosis(self, tmp_path, capsys):
        # The evidence store is shared by every worktree of a clone. A fact
        # whose commit is not an ancestor of HEAD describes another lineage;
        # anchoring on it would attribute this branch's gap to that branch's
        # findings.
        repo = _branch_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "sibling", "main")
        _commit(repo, "feature.py", "sibling = 1\n", "sibling work")
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _git(repo, "checkout", "-q", "feature")
        _commit(repo, "feature.py", "y = 3\n", "fix on feature")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_dirty_tree_fact_without_head_commit_is_skipped(self, tmp_path, capsys):
        # A review of a dirty tree records `head_commit: null` — it vouches for
        # a tree no commit materialized, so it cannot be placed on the lineage.
        repo = _branch_repo(tmp_path)
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
        )  # no head_commit — the dirty-tree shape
        _commit(repo, "feature.py", "y = 3\n", "fix")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_findings_with_no_file_attribution_are_not_enough(self, tmp_path, capsys):
        # Without `files` there is nothing to compare the delta against, so the
        # subset claim cannot be made honestly.
        repo = _branch_repo(tmp_path)
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w"}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _commit(repo, "feature.py", "y = 3\n", "fix")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_base_branch_fact_never_anchors_an_unreviewed_branch(self, tmp_path, capsys):
        # The dangerous false positive. `merge-base --is-ancestor <fact> HEAD`
        # is satisfied by EVERY fact on the base branch, and one clone's store
        # is shared by all its worktrees — so a branch with no review of its
        # own would anchor on the last review of `main`. Reviews in a real repo
        # name the same hot files over and over, so a whole unreviewed branch
        # can land inside the subset test and be reported as churn. The anchor
        # must be a strict descendant of the merge-base: a review at or before
        # it never saw this branch.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "feature.py", "x = 1\n", "c1")
        _fact(  # a review OF MAIN that happens to name feature.py
            repo,
            _tree(repo, "HEAD~0"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "entirely new unreviewed work\n", "f1")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "fix churn" not in err

    def test_merge_of_the_base_does_not_switch_the_anchor_to_a_base_fact(
        self, tmp_path, capsys
    ):
        # CRT-3W6P's counter-example, delivered as an actual merge. After
        # merging the base in, a base-side fact can be NEARER to HEAD by commit
        # distance than the branch's own review — which would switch the anchor
        # and drop the merged-in lines out of the delta, exactly reversing the
        # answer. The merge-base filter is what holds here.
        repo = _branch_repo(tmp_path)
        _fact(  # the branch's own review, at f1
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "code.py", "x = 2  # base moved on\n", "base work")
        _fact(  # a base-side review naming the same file the branch touches
            repo,
            _tree(repo, "HEAD~1"),
            _tree(repo),
            ["code.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        _commit(repo, "feature.py", "y = 3  # fix\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        # The merge brought unreviewed base work into the span. Whatever the
        # gate says, it must not say this gap is only the builder's churn.
        assert "fix churn" not in err

    def test_a_gap_below_the_anchor_is_not_reported_as_churn(self, tmp_path, capsys):
        # `uncovered` means composition failed SOMEWHERE in base→HEAD, not
        # necessarily on the last leg. With an unreviewed commit below the
        # anchor, the last leg can be pure churn while the real gap is
        # upstream — and then "ONE verify-resolutions closes this gap; fix
        # nothing further first" is advice that does not close it.
        repo = _branch_repo(tmp_path)
        _commit(repo, "feature.py", "y = 2\nunreviewed = True\n", "f2 — never reviewed")
        _fact(  # anchor sits ABOVE the unreviewed f2, so base→anchor has a hole
            repo,
            _tree(repo, "HEAD~1"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "warning", "title": "w",
                       "files": ["feature.py"]}],
            counts={"blocking": 0, "warning": 1, "note": 0},
            head_commit=_git(repo, "rev-parse", "HEAD"),
        )
        _commit(repo, "feature.py", "y = 3\nunreviewed = True\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "fix churn" not in err

    def test_a_degraded_diagnosis_says_so_rather_than_going_quiet(self, tmp_path, capsys):
        # "Advice fails soft" is not "advice fails silent" (learnings.md): a
        # control that could not run must not render identically to one that
        # ran and found nothing, or the builder pays the round it exists to
        # prevent with no record that it never fired.
        repo = _branch_repo(tmp_path)
        rc = gates.check_cumulative_critic(repo)  # warm the normal path first
        capsys.readouterr()
        import lib.coverage as cov_mod

        real = cov_mod.diagnose_fix_churn
        try:
            cov_mod.diagnose_fix_churn = lambda *a, **k: {
                "status": "unavailable",
                "reason": "ancestry check failed (fatal: bad object)",
            }
            rc, _out, err = _run_gate(repo, capsys)
        finally:
            cov_mod.diagnose_fix_churn = real
        assert rc == 1
        assert "could not run" in err
        assert "ancestry check failed" in err
        # And it must not be mistaken for a verdict about the work.
        assert "not a finding that your gap is genuine work" in err

    def test_the_producer_itself_returns_unavailable_when_git_cannot_answer(
        self, tmp_path
    ):
        """The test above pins the gate's RENDERING of a degraded diagnosis, and
        it gets the signal from a monkeypatched stand-in — so it proves nothing
        about the function that has to produce it.

        That is the shape Goal 1 names: a fixture that synthesizes the
        producer's signal proves the consumer reads it, never that the producer
        emits it. Five sites in `diagnose_fix_churn` return
        `{"status": "unavailable"}`, and the `None`-vs-`unavailable` split
        exists *because* a prior round found the function silent when it could
        not run. Without this, a refactor collapsing those returns to `None`
        keeps the whole suite green and restores that defect.

        Driven through the real git failure rather than a patched return: a fact
        whose `head_commit` names no object makes `merge-base --is-ancestor`
        exit 128, which is neither the 0 ("ancestor") nor the 1 ("not an
        ancestor") the loop treats as an answer.
        """
        from lib import coverage

        repo = _branch_repo(tmp_path)
        head_tree = _tree(repo, "HEAD")
        bogus = {
            "kind": "review",
            "id": "rev-bogus",
            "ts": "2026-08-04T00:00:00Z",
            "body": {
                "head_tree": "0" * 40,
                "head_commit": "deadbeef" * 5,
                "findings": [],
            },
        }
        out = coverage.diagnose_fix_churn(
            repo, [bogus], head_tree, "1" * 40, "2" * 40,
            verdict_fn=lambda *a: {"status": "uncovered"},
        )
        assert out is not None, (
            "the producer went silent on a git failure — `None` here is read by "
            "the gate as 'ran and found nothing', which is the exact collapse "
            "the unavailable/None split was introduced to prevent"
        )
        assert out["status"] == "unavailable"
        assert "ancestry check failed" in out["reason"], out["reason"]

    def test_the_producer_returns_unavailable_on_missing_span_endpoints(self, tmp_path):
        """The cheapest of the five `unavailable` sites, and the only one
        reachable without git failing — pinned here so the guard above is not
        the sole witness that this return shape exists at all."""
        from lib import coverage

        repo = _branch_repo(tmp_path)
        out = coverage.diagnose_fix_churn(
            repo, [], "", "b" * 40, "c" * 40,
            verdict_fn=lambda *a: {"status": "uncovered"},
        )
        assert out == {"status": "unavailable", "reason": "missing span endpoints"}


# ---------------------------------------------------------------------------
# Blocking findings and resolutions (D5 join)
# ---------------------------------------------------------------------------


class TestRoundTally:
    """The uncovered block used to be a pure function of the current tree, so
    round five printed the same words as round one.

    Measured on a v3.2.4 consumer branch that ran six rounds: *"the gate
    re-fires identically — block #6 read exactly like block #1."* Nothing in
    the message let the builder see they were in a sequence, so each round was
    priced as if it were the first. The tally is the discriminator, and it is
    derived from the branch's own facts rather than a counter, because the
    evidence store is shared by every worktree of the clone.
    """

    def _uncovered_branch(self, tmp_path, rounds: int, **fact_kwargs) -> Path:
        """A feature branch whose gate is uncovered, carrying ``rounds``
        recorded reviews of its own.

        Each fact spans main→f1 only, so the judgeable commits after f1 leave
        the gate uncovered — the state that prints the block under test — while
        every fact still sits on this branch's lineage and counts.
        """
        repo = _branch_repo(tmp_path)
        f1_commit, f1_tree = _git(repo, "rev-parse", "HEAD"), _tree(repo)
        _commit(repo, "later.py", "z = 3\n", "f2")
        for _ in range(rounds):
            _fact(
                repo,
                _tree(repo, "main"),
                f1_tree,
                ["feature.py"],
                head_commit=f1_commit,
                **fact_kwargs,
            )
        return repo

    def test_a_first_round_branch_says_it_is_the_first(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "no review round has been recorded against this branch" in err
        assert "this branch's first" in err

    def test_a_fifth_round_branch_reads_differently_from_a_first(self, tmp_path, capsys):
        """The acceptance criterion, asserted as a DIFFERENCE and not merely as
        the presence of the right words — identical output is the reported
        defect, so the test has to be able to see identity."""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        first = _branch_repo(tmp_path / "a")
        rc_first, _out, err_first = _run_gate(first, capsys)
        repeat = self._uncovered_branch(tmp_path / "b", 4)
        rc_repeat, _out, err_repeat = _run_gate(repeat, capsys)

        assert rc_first == 1 and rc_repeat == 1
        assert "the next one is round 5, not its first" in err_repeat
        assert "4 review rounds" in err_repeat
        assert err_first != err_repeat

    def test_the_tally_asks_for_a_reason_instead_of_discouraging_the_round(
        self, tmp_path, capsys
    ):
        """A repeat round is sometimes exactly right — CRT-3W6P's own
        counter-example is one that looked like waste because a merge had
        brought unreviewed lines into files the branch already touched. A bare
        "you have spent four already" suppresses that round, so the sentence
        has to name what a good answer looks like; a reader agrees with a
        general prompt and spends the round anyway."""
        repo = self._uncovered_branch(tmp_path, 4)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "a merge or genuinely new work is a good answer" in err
        assert "'one more fix commit' is not" in err
        # ...and it never tells the builder NOT to review. The generic route
        # below it stays reachable and unqualified when nothing diagnosed churn.
        assert "/prawduct:critic cumulative" in err

    def test_the_cost_comes_from_the_rounds_own_durations(self, tmp_path, capsys):
        repo = self._uncovered_branch(tmp_path, 4, duration_seconds=300.0)
        _rc, _out, err = _run_gate(repo, capsys)
        # 4 × 300s = 20 min, computed at call time from the facts themselves —
        # never a figure written into the message (see the no-hardcoded-duration
        # sweep in tests/test_cost_of_commit.py).
        assert "costing about 20 min so far" in err
        # And it says WHOSE rounds those are. The other duration a builder meets
        # in the same session is a repo-wide median from the ledger; two
        # unlabelled figures read as one number contradicting itself.
        assert "this branch's own rounds, not a repo-wide median" in err

    def test_a_partly_timed_history_says_how_much_it_could_price(
        self, tmp_path, capsys
    ):
        repo = self._uncovered_branch(tmp_path, 2, duration_seconds=300.0)
        _fact(repo, _tree(repo, "main"), "deadbeef" * 5, ["feature.py"],
              head_commit=_git(repo, "rev-parse", "HEAD~1"))
        _rc, _out, err = _run_gate(repo, capsys)
        assert "3 review rounds" in err
        assert "costing about 10 min so far" in err
        assert "2 of 3 timed" in err

    def test_a_sub_minute_total_never_reads_as_about_zero_minutes(
        self, tmp_path, capsys
    ):
        """The guard's whole point, asserted as the WRONG form being ABSENT.
        A total under a minute formats to "about 0 min", which reads as a claim
        that rounds are free — the opposite of what this sentence is for. Every
        other case in this class is measured in whole minutes, so without this
        a future edit dropping the guard goes green."""
        repo = self._uncovered_branch(tmp_path, 2, duration_seconds=10.0)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "costing under a minute so far" in err
        assert "about 0 min" not in err

    def test_untimed_rounds_are_counted_without_inventing_a_cost(self, tmp_path, capsys):
        repo = self._uncovered_branch(tmp_path, 3)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "3 review rounds" in err
        assert "min between them" not in err

    def test_a_dirty_tree_round_is_placed_by_its_dispatch_commit(self, tmp_path, capsys):
        """A `chunk` review of an uncommitted tree records `head_commit: null`.
        Dropping it would undercount exactly the mid-chunk rounds a long branch
        spends most of — `dispatch_commit` is the commit HEAD sat at, and that
        round was bought by this branch just as surely."""
        repo = _branch_repo(tmp_path)
        dispatched_at = _git(repo, "rev-parse", "HEAD")
        _commit(repo, "later.py", "z = 3\n", "f2")
        _fact(repo, _tree(repo, "main"), "deadbeef" * 5, ["feature.py"],
              dispatch_commit=dispatched_at)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "already recorded 1 review round since" in err
        assert "round 2, not its first" in err
        # Reads as English at n=1 too — the plural forms were caught by running
        # the real gate on a one-round branch, which no unit test had done.
        assert "still uncovered after it" in err

    def test_a_sibling_branchs_round_is_not_this_branchs(self, tmp_path, capsys):
        """The store is shared by every worktree of the clone, so "reviews that
        exist" is not "reviews this branch bought". A fact off this lineage
        must not inflate the count — an inflated count tells a first-round
        builder they are churning, which discredits the whole message."""
        repo = _branch_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "sibling", "main")
        _commit(repo, "sibling.py", "s = 1\n", "s1")
        sibling_commit = _git(repo, "rev-parse", "HEAD")
        _git(repo, "checkout", "-q", "feature")
        _fact(repo, _tree(repo, "main"), _tree(repo, "sibling"), ["sibling.py"],
              head_commit=sibling_commit)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "no review round has been recorded against this branch" in err

    def test_a_review_at_the_merge_base_is_not_counted(self, tmp_path, capsys):
        """The documented lower bound, pinned so the fix for it is a decision
        and not an accident: a dirty-tree review dispatched before the branch's
        first commit sits AT the merge-base. Counting it would mean counting
        the BASE branch's reviews too, which is the error that tells a
        first-round builder they are on round four."""
        repo = _branch_repo(tmp_path)
        merge_base = _git(repo, "rev-parse", "main")
        _fact(repo, _tree(repo, "main"), "deadbeef" * 5, ["feature.py"],
              dispatch_commit=merge_base)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "no review round has been recorded against this branch" in err

    def test_the_tally_degrades_to_a_reason_never_to_a_count(self, tmp_path):
        """`advice fails soft` is not `advice fails silent`: a tally that
        vanishes when it breaks reads as "round one" to the builder it exists
        to warn."""
        repo = _branch_repo(tmp_path)
        for bad_base in ("", "deadbeef" * 5):
            tally = coverage.count_branch_rounds(repo, [], bad_base)
            assert tally["status"] == "unavailable", bad_base
            line = coverage.format_branch_rounds(tally)
            assert "could not be derived" in line
            assert "unknown, not as one" in line
        assert "could not be derived" in coverage.format_branch_rounds(None)

    def test_the_producer_counts_and_totals_without_the_gate(self, tmp_path):
        repo = _branch_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        merge_base = _git(repo, "merge-base", "main", "HEAD")
        facts = [
            {"kind": "review", "body": {"head_commit": head, "duration_seconds": 120}},
            {"kind": "review", "body": {"head_commit": head}},
            {"kind": "resolution", "body": {"head_commit": head}},
            {"kind": "review", "body": {"head_commit": "deadbeef" * 5}},
        ]
        tally = coverage.count_branch_rounds(repo, facts, merge_base)
        assert tally == {
            "status": "counted", "rounds": 2, "seconds": 120.0, "timed": 1,
        }

    def test_the_tally_leads_the_block_it_frames(self, tmp_path, capsys):
        """Placement is the deliverable, not the sentence. The routes below it
        are answered differently on round five than on round one, so a reader
        who acts on the first thing they meet has to meet this first."""
        repo = self._uncovered_branch(tmp_path, 2)
        _rc, _out, err = _run_gate(repo, capsys)
        lines = [line for line in err.splitlines() if line.strip()]
        tally_at = next(i for i, line in enumerate(lines) if "round 3" in line)
        route_at = next(i for i, line in enumerate(lines) if "/prawduct:critic" in line)
        assert lines[0].startswith("uncovered:")
        assert 0 < tally_at < route_at


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

    def test_superseded_blocker_names_the_route_that_can_clear_it(
        self, tmp_path, capsys
    ):
        """#536: a blocker left on an EARLIER review round is never named by a
        verify-resolutions pass again (each anchors to the most recent review),
        so prescribing only that route sends the operator down a path that
        cannot work. The state already self-heals through a spanning review —
        the defect was that nothing said so.

        Field repro: round N blocks, round N+1 reports a new blocker about the
        fix and declines to resolve N's, round N+2 resolves N+1's. N's is now
        stranded.
        """
        repo = _branch_repo(tmp_path)
        first_tree = _tree(repo)
        stranded = _fact(
            repo,
            _tree(repo, "main"),
            first_tree,
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "stranded"}],
        )
        # A later, clean round over the next commit — this is what a verify pass
        # would anchor to, and it never names R-1.
        _commit(repo, "later.py", "z = 3\n", "f2")
        _fact(repo, first_tree, _tree(repo), ["later.py"])

        rc, _out, err = _run_gate(repo, capsys)

        assert rc == 1  # advice only — a superseded blocker still blocks
        assert f"{stranded}/R-1" in err
        assert "/prawduct:critic cumulative" in err  # the route that CAN clear it

    def test_reachable_blocker_is_not_sent_to_a_spanning_review(
        self, tmp_path, capsys
    ):
        """Contrast pin for the test above. The blocker sits on the newest
        review fact, so verify-resolutions WILL revisit it — naming the
        spanning cumulative here would be the opposite wrong advice, and a
        predicate stuck at True is the likeliest way this breaks."""
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
        assert f"{rid}/R-1" in err
        assert "verify-resolutions" in err  # the standard remedy still stands
        assert "cumulative" not in err

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
# The superseded-blocker remedy text (shared by both blocking messages)
# ---------------------------------------------------------------------------


class TestBlockingRemedyLines:
    """``gates.blocking_remedy_lines`` is the single home for the remedy two
    gates emit — the PR gate here and the Stop hook's. Pinned directly because
    the three cases differ in WHICH route leads, and leading with the wrong one
    is the defect this whole change exists to remove."""

    @staticmethod
    def _text(unresolved):
        return " ".join(gates.blocking_remedy_lines(unresolved))

    def test_standard_remedy_when_every_blocker_is_reachable(self):
        for reachable in (None, [], [{"superseded": False}], [{"fid": "R-1"}]):
            text = self._text(reachable)
            assert "verify-resolutions" in text, reachable
            # A pre-annotation entry (no key at all) must not read as superseded.
            assert "Superseded" not in text, reachable
            assert "/prawduct:critic cumulative" not in text, reachable

    def test_mixed_set_keeps_the_standard_remedy_and_adds_the_exception(self):
        lines = gates.blocking_remedy_lines(
            [{"superseded": True}, {"superseded": False}, {"superseded": True}]
        )
        text = " ".join(lines)
        # The standard route still leads — one of the three IS reachable by it.
        assert lines[0].startswith("Fix them, then run /prawduct:critic verify-resolutions")
        assert "Superseded: 2 findings" in text
        assert "/prawduct:critic cumulative" in text

    def test_all_superseded_leads_with_the_spanning_review(self):
        """The case the first pass got wrong: appending the exception after
        'run verify-resolutions' hands the operator the one route that cannot
        work as their FIRST instruction."""
        for unresolved in ([{"superseded": True}], [{"superseded": True}] * 3):
            lines = gates.blocking_remedy_lines(unresolved)
            text = " ".join(lines)
            assert lines[0].startswith("Superseded:"), lines
            assert "/prawduct:critic cumulative" in text
            # The unreachable route is never prescribed as the action to take.
            assert "run /prawduct:critic verify-resolutions" not in text, lines

    def test_reads_naturally_for_one_and_for_many(self):
        assert "the blocker above sits" in self._text([{"superseded": True}])
        assert "all 3 blockers above sit" in self._text([{"superseded": True}] * 3)


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
