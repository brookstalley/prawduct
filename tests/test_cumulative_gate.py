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

        for fn in (coverage.diagnose_fix_churn, gates._merge_base_verdict):
            params = inspect.signature(fn).parameters
            for name in ("diff_fn", "key_fn"):
                assert params[name].default is inspect.Parameter.empty, (
                    f"{fn.__name__}'s {name} has a default again. A missing "
                    "argument then silently selects the pairwise free-edge "
                    "branch (~5.6k `git diff` subprocesses on this repo's "
                    "store) on the interactive PR path, instead of raising a "
                    "TypeError the caller can see."
                )

    def test_fix_commit_on_named_file_is_diagnosed_as_churn(self, tmp_path, capsys):
        repo, rid = self._reviewed_feature(tmp_path)
        _commit(repo, "feature.py", "y = 3  # addressed R-1\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncovered" in err
        assert "is your fix churn, not unreviewed work" in err
        assert rid in err
        assert "feature.py" in err
        # Both routes out are named, and the cheap one is named first.
        assert "prawduct-hook disposition" in err
        assert err.index("fix churn") < err.index("/prawduct:critic cumulative")
        # The counts it quotes come from the fact, not from a guess.
        assert "1 warning + 1 note" in err

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
