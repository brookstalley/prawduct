"""A blocker-free fix tail is deferred to the release (#1222, #1232 Chunk 05).

Under ``boundary_review: per_release`` a fix for a non-blocking finding does not
buy its own verify round: a tail after a blocker-free review, confined to files
that review's findings named and on no risk surface, merges with the PR gate's
exit 0 and is owed to the release check. A DEFERRAL, never coverage, and a
BLOCKING finding never defers.

One predicate, ``gates.fix_tail_deferral``, asked by three callers, each pinned
here at its own layer: the PR gate (``check-cumulative-critic``), the Stop gate
(the hook's ``stop``), and the release op (``boundary_coverage``), which asks it
of a merged span and names the merge ``tail-deferred``. Each refusing condition
has a control that differs from the deferring fixture in that one respect.

Real git repos throughout: the policy is read from a tracked
``project-state.yaml`` at the merge-base, and the anchor review is placed on the
branch's lineage by commit.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from conftest import SHAPED_REFLECTION, scrubbed_env, suite_now
from lib import boundary_coverage as bc
from lib import critic_consolidate, critic_mode, gates, pr_gate
from test_cumulative_gate import _commit, _fact, _git, _resolution, _run_gate, _tree

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

_DEFERRED_OUT = "satisfied (fix tail deferred to the release)"
_NOTE_BODY = "boundary_review is per_release, so this fix tail is DEFERRED to the release"
_NOTE = f"NOTE: {_NOTE_BODY}"


#: A plan bound to ``feature`` arms the Stop gate's Critic block. Its first
#: chunk declares ``Critic mode:``, so the short-plan deferral stays out of the way
#: and the Stop gate's per_pr answer is the plain block.
_PLAN = """---
artifact: build-plan
scope: tail
branch: feature
base: main
---

# Build Plan

### Chunk 01: one
- **Type:** code
- **Critic mode:** chunk
- **Deliverables:** `feature.py`

### Chunk 02: two
- **Type:** code
- **Deliverables:** `feature.py`
"""


def _repo(tmp_path: Path, *, key: "str | None" = "per_release", state_extra: str = "",
          plan: bool = False) -> Path:
    """``main`` declares ``base_branch: main`` (and ``boundary_review: <key>``)
    in a tracked state file; ``feature`` adds ``feature.py`` in one commit."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".prawduct/.*\n")
    if plan:
        (repo / ".prawduct" / "artifacts").mkdir(parents=True)
        (repo / ".prawduct" / "artifacts" / "build-plan-tail.md").write_text(_PLAN)
    state = "base_branch: main\n" + (f"boundary_review: {key}\n" if key else "") + state_extra
    _commit(repo, ".prawduct/project-state.yaml", state, "c1")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature.py", "y = 2\n", "f1")
    return repo


def _review(repo: Path, *, severity: str = "warning", files=("feature.py",), base_rev: str = "main",
            head_rev: str = "HEAD") -> str:
    """A review of ``base_rev`` → ``head_rev`` whose findings name ``files``."""
    blocking = 1 if severity == "blocking" else 0
    return _fact(
        repo, _tree(repo, base_rev), _tree(repo, head_rev), ["feature.py"],
        findings=[{"fid": "R-1", "severity": severity, "title": "t", "files": list(files)}],
        counts={"blocking": blocking, "warning": 1 - blocking, "note": 0},
        head_commit=_git(repo, "rev-parse", head_rev),
    )


def _stray_tree(repo: Path) -> str:
    """A tree holding one judgeable file no tree of the branch holds, so no
    composition reaches it: a review based on it is one the gate never walks."""
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input="stray = 1\n",
                          capture_output=True, text=True, check=True).stdout.strip()
    return subprocess.run(["git", "mktree"], cwd=repo, input=f"100644 blob {blob}\tstray.py\n",
                          capture_output=True, text=True, check=True).stdout.strip()


def _deferring(tmp_path: Path, **kw) -> "tuple[Path, str]":
    """The fixture every control differs from in one respect: a reviewed branch
    whose only change since the review is a fix to the file a warning named."""
    repo = _repo(tmp_path, **kw)
    rid = _review(repo)
    _commit(repo, "feature.py", "y = 3  # addressed R-1\n", "fix the warning")
    return repo, rid


# ---------------------------------------------------------------------------
# The PR gate
# ---------------------------------------------------------------------------


class TestThePrGate:
    def test_a_fix_in_a_named_file_passes_deferred_with_the_note(self, tmp_path, capsys):
        repo, rid = _deferring(tmp_path)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert _DEFERRED_OUT in out
        note = next(line for line in err.splitlines() if line.startswith("NOTE: boundary_review"))
        assert note.startswith(_NOTE), note
        # The review, the tail's files and the release check that owes them a read.
        assert f"since review {rid}" in note and "feature.py" in note, note
        assert "check-boundary-coverage" in note and "`tail-deferred`" in note, note
        # The release batch review by the invocation every remedy names: a plain
        # `/prawduct:critic cumulative` at the integration branch's tip derives
        # the release span, so the note no longer spells the `--span` flag.
        assert ("release batch review (`/prawduct:critic cumulative` on the integration "
                "branch's own checkout at its tip") in note, note
        answer = gates.branch_coverage_verdict(repo)
        assert answer["status"] == "deferred", answer
        assert answer["deferral"]["fact_id"] == rid
        assert answer["deferral"]["files"] == ["feature.py"]
        assert rid in answer["deferral"]["path"]

    def test_per_pr_is_unchanged(self, tmp_path, capsys):
        """The default: the same branch without the key reads uncovered, with
        the fix-churn advice it always printed."""
        repo, _rid = _deferring(tmp_path, key=None)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert _DEFERRED_OUT not in out and _NOTE not in err
        assert "uncovered:" in err and "fix churn" in err
        assert gates.branch_coverage_verdict(repo)["status"] == "uncovered"

    def test_a_branch_cannot_opt_itself_in(self, tmp_path, capsys):
        """`per_release` written on the branch only: the merge-base says per_pr."""
        repo = _repo(tmp_path, key=None)
        _commit(repo, ".prawduct/project-state.yaml",
                "base_branch: main\nboundary_review: per_release\n", "opt in")
        _review(repo)
        _commit(repo, "feature.py", "y = 3\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1 and _NOTE not in err

    def test_an_open_blocker_on_the_anchor_never_defers(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo, severity="blocking")
        _commit(repo, "feature.py", "y = 3\n", "fix the blocker")
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 1 and _DEFERRED_OUT not in out
        assert gates.branch_coverage_verdict(repo)["status"] == "uncovered"

    def test_a_blocker_no_composition_walks_still_never_defers(self, tmp_path, capsys):
        """A review that read the tip itself and found a BLOCKING, from a base
        nothing composes to: the anchor and its prefix are clean, so only the
        branch-wide blocker condition can refuse. Red under a mutant dropping it."""
        repo, _rid = _deferring(tmp_path)
        stray = _stray_tree(repo)  # a base nothing on this branch composes to
        _fact(repo, stray, _tree(repo), ["feature.py"],
              findings=[{"fid": "B-1", "severity": "blocking", "title": "b", "files": ["feature.py"]}],
              counts={"blocking": 1, "warning": 0, "note": 0}, head_commit=_git(repo, "rev-parse", "HEAD"))
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 1 and _DEFERRED_OUT not in out, out + err

    def test_a_resolved_blocker_does_not_refuse(self, tmp_path, capsys):
        """Control for the condition above: the same stray review with its
        blocker resolved defers again, so the refusal is the blocker's."""
        repo, _rid = _deferring(tmp_path)
        stray = _stray_tree(repo)
        bid = _fact(repo, stray, _tree(repo), ["feature.py"],
                    findings=[{"fid": "B-1", "severity": "blocking", "title": "b", "files": ["feature.py"]}],
                    counts={"blocking": 1, "warning": 0, "note": 0},
                    head_commit=_git(repo, "rev-parse", "HEAD"))
        _resolution(repo, bid, "B-1")
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0 and _DEFERRED_OUT in out, err

    def test_a_crashed_predicate_fails_closed_and_says_so(self, tmp_path, capsys, monkeypatch):
        """The predicate sits on the PR gate's and inference's path: a crash is
        no deferral, never a traceback, and the gate says the deferral never
        got a look rather than reading as "not a fix tail"."""
        from lib import review_lane

        repo, _rid = _deferring(tmp_path)

        def boom(*_a, **_k):
            raise RuntimeError("policy read exploded")

        monkeypatch.setattr(review_lane, "boundary_review_policy", boom)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 1 and _DEFERRED_OUT not in out
        assert "NOTE: the fix-tail deferral could not be evaluated (RuntimeError: policy read exploded)" in err
        assert gates.branch_coverage_verdict(repo)["status"] == "uncovered"

    def test_a_tail_file_the_review_did_not_name_is_not_deferred(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _review(repo)
        _commit(repo, "other.py", "z = 9\n", "unrelated work")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1 and _NOTE not in err

    def test_a_tail_on_a_risk_surface_buys_its_verify_round(self, tmp_path, capsys):
        repo, _rid = _deferring(tmp_path, state_extra="risk_surfaces:\n  - feature.py\n")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1 and _NOTE not in err
        assert "fix churn" in err  # it IS churn; only the risk surface refused it

    def test_a_branch_cannot_drop_its_own_risk_surface_to_defer(self, tmp_path, capsys):
        """The self-authority hole `boundary_review:` is read around, for risk
        surfaces: main declares `feature.py` one, and the branch rewrites
        `risk_surfaces: []`. Read from this checkout alone, the tail deferred;
        the integration branch still holds the surface, so it buys its round."""
        repo = _repo(tmp_path, state_extra="risk_surfaces:\n  - feature.py\n")
        _commit(repo, ".prawduct/project-state.yaml",
                "base_branch: main\nboundary_review: per_release\nrisk_surfaces: []\n", "drop it")
        _review(repo)
        _commit(repo, "feature.py", "y = 3  # addressed R-1\n", "fix the warning")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1 and _NOTE not in err, err
        assert "fix churn" in err  # it IS churn; only the held surface refused it

    def test_a_surface_the_base_tip_added_after_the_fork_refuses(self, tmp_path, capsys):
        repo, _rid = _deferring(tmp_path)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, ".prawduct/project-state.yaml",
                "base_branch: main\nboundary_review: per_release\nrisk_surfaces:\n  - feature.py\n",
                "declare the surface")
        _git(repo, "checkout", "-q", "feature")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1 and _NOTE not in err, err

    def test_an_anchor_review_predating_the_merge_base_does_not_anchor(self, tmp_path, capsys):
        """A review on main, at the merge-base, never saw this branch."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        (repo / ".gitignore").write_text(".prawduct/.*\n")
        _commit(repo, ".prawduct/project-state.yaml",
                "base_branch: main\nboundary_review: per_release\n", "c1")
        _commit(repo, "feature.py", "y = 1\n", "c2")
        _review(repo, base_rev="HEAD~1", head_rev="HEAD")
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 2\n", "f1")
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 1 and _DEFERRED_OUT not in out and _NOTE not in err


# ---------------------------------------------------------------------------
# Readers of the status
# ---------------------------------------------------------------------------


class TestStatusReaders:
    def test_inference_does_not_name_a_cumulative_for_a_deferred_branch(self, tmp_path):
        repo, _rid = _deferring(tmp_path)
        assert critic_mode._branch_already_covered(repo, None) is True
        control, _ = _deferring(tmp_path / "per_pr", key=None)
        assert critic_mode._branch_already_covered(control, None) is False

    def test_the_span_clause_says_deferred_and_never_covered(self, tmp_path):
        repo, _rid = _deferring(tmp_path)
        clause = critic_consolidate.span_clause(gates.branch_coverage_verdict(repo), 2)
        assert "The branch is not covered, but its PR gate passes" in clause
        assert "deferred to the release check" in clause
        assert "The branch was covered too" not in clause

    def test_an_unknown_status_never_reads_covered(self):
        clause = critic_consolidate.span_clause({"status": "something-new"})
        assert clause == critic_consolidate._COVERAGE_IS_A_SEPARATE_QUESTION
        assert "covered too" not in clause

    def test_pr_hygiene_credits_the_reviews_the_deferral_stands_on(self, tmp_path):
        """`review-tree-changed` lists reviews on the coverage path; a deferred
        branch's path is the composition up to its anchor."""
        repo = _repo(tmp_path)
        # The anchor carries the builder's attestation that its tree moved.
        result = gates.evidence.append_fact(repo, "review", "rev-tree-changed", {
            "base_tree": _tree(repo, "main"), "head_tree": _tree(repo),
            "files_changed": ["feature.py"], "files_reviewed": ["feature.py"],
            "findings": [{"fid": "R-1", "severity": "warning", "title": "t", "files": ["feature.py"]}],
            "counts": {"blocking": 0, "warning": 1, "note": 0},
            "mode": "chunk (lighter pass, not ready for push)",
            "head_commit": _git(repo, "rev-parse", "HEAD"),
            critic_consolidate.TREE_CHANGED_KEY: {"paths": ["feature.py"], "reason": "mine"},
        })
        assert result["status"] == "appended", result
        _commit(repo, "feature.py", "y = 3\n", "fix the warning")
        answer = gates.branch_coverage_verdict(repo)
        assert answer["status"] == "deferred", answer
        results = pr_gate._review_tree_changed(repo)
        assert results and any(item.startswith("rev-tree-changed:") for item in results[0].items), results
        # Control: per_pr, the same store shape, reads no path and lists nothing.
        control = _repo(tmp_path / "per_pr", key=None)
        gates.evidence.append_fact(control, "review", "rev-tree-changed-2", {
            "base_tree": _tree(control, "main"), "head_tree": _tree(control),
            "files_changed": ["feature.py"], "files_reviewed": ["feature.py"],
            "findings": [{"fid": "R-1", "severity": "warning", "title": "t", "files": ["feature.py"]}],
            "counts": {"blocking": 0, "warning": 1, "note": 0},
            "mode": "chunk (lighter pass, not ready for push)",
            "head_commit": _git(control, "rev-parse", "HEAD"),
            critic_consolidate.TREE_CHANGED_KEY: {"paths": ["feature.py"], "reason": "mine"},
        })
        _commit(control, "feature.py", "y = 3\n", "fix the warning")
        assert pr_gate._review_tree_changed(control) == []


# ---------------------------------------------------------------------------
# The Stop gate
# ---------------------------------------------------------------------------


def _arm_stop(repo: Path) -> None:
    prawduct = repo / ".prawduct"
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".session-git-baseline").write_text("")
    ts = suite_now() - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _run_stop(repo: Path) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    env = scrubbed_env(home, CLAUDE_PROJECT_DIR=str(repo), CLAUDE_PLUGIN_ROOT=str(ROOT))
    return subprocess.run(
        [sys.executable, str(HOOK), "stop"],
        capture_output=True, text=True, env=env, cwd=str(repo), timeout=60, input="",
    )


class TestTheStopGate:
    def _in_flight(self, tmp_path: Path, **kw) -> Path:
        """The fix to the named file is uncommitted: the Stop gate's span ends
        at the working tree."""
        repo = _repo(tmp_path, plan=True, **kw)
        _review(repo)
        (repo / "feature.py").write_text("y = 3  # addressed R-1\n")
        _arm_stop(repo)
        return repo

    def test_a_deferred_tail_does_not_block_session_end(self, tmp_path):
        repo = self._in_flight(tmp_path)
        result = _run_stop(repo)
        assert result.returncode == 0, result.stderr
        flat = " ".join(result.stderr.split())
        assert "none is owed before the release" in flat, flat
        assert _NOTE_BODY in flat, flat
        assert "CRITIC REVIEW: no composed review coverage" not in flat

    def test_per_pr_blocks_as_ever(self, tmp_path):
        repo = self._in_flight(tmp_path, key=None)
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "CRITIC REVIEW: no composed review coverage" in result.stderr
        assert _NOTE_BODY not in " ".join(result.stderr.split())

    def test_uncommitted_work_outside_the_named_files_blocks(self, tmp_path):
        repo = self._in_flight(tmp_path)
        (repo / "other.py").write_text("z = 9\n")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert _NOTE_BODY not in " ".join(result.stderr.split())


    def test_per_pr_asks_the_policy_before_paying_for_the_span(self, tmp_path, monkeypatch):
        """Every uncovered Stop asks the deferral. In a per_pr repo condition 1
        (the policy) is the whole answer, so the store read, the merge-base and
        the composition it would otherwise run must not happen. Control: a
        per_release repo does reach them. Red while the policy is asked only
        inside `fix_tail_deferral`, after that work."""
        from lib import evidence

        calls: list = []
        real = evidence.read_facts

        def counting(*a, **k):
            calls.append(a)
            return real(*a, **k)

        monkeypatch.setattr(evidence, "read_facts", counting)
        per_pr = self._in_flight(tmp_path / "per_pr", key=None)
        assert gates.session_fix_tail_deferral(per_pr) is None
        assert calls == [], calls
        per_release = self._in_flight(tmp_path / "per_release")
        assert gates.session_fix_tail_deferral(per_release) is not None
        assert calls, "the per_release control never reached the store read"


# ---------------------------------------------------------------------------
# Risk surfaces read at a revision go through the bounded git runner
# ---------------------------------------------------------------------------


class TestRiskSurfacesAtARevision:
    def test_every_git_call_is_bounded_and_a_hang_reads_unknown(self, tmp_path, monkeypatch):
        """`risk._surfaces_at` runs on the PR gate's, the Stop gate's and
        inference's path (the lane and the fix-tail deferral). Every git call it
        makes carries a timeout, and a call that times out is "could not read",
        which the relaxation reads as touched, never a raise or a hang. Red
        under a private `subprocess.run` with no timeout."""
        from lib import risk

        repo = _repo(tmp_path)
        assert risk._surfaces_at(repo, "main") is not None  # control: it reads
        seen: list = []

        def hung(cmd, *a, **k):
            seen.append((cmd, k.get("timeout")))
            raise subprocess.TimeoutExpired(cmd, k.get("timeout") or 0)

        monkeypatch.setattr(subprocess, "run", hung)
        assert risk._surfaces_at(repo, "main") is None
        assert seen and all(timeout for _cmd, timeout in seen), seen
        touched, why = risk.paths_touch_held_risk_surface(
            repo, repo / ".prawduct", ["feature.py"], ("main",)
        )
        assert touched and "git could not read the risk surfaces at main" in why, why

    def test_the_shared_runner_hands_file_content_back_verbatim(self, tmp_path):
        """`_surfaces_at` reads file content through `evidence.run_git(...,
        strip=False)`: a file is content, not a porcelain line, and its edges
        (a leading indent, a trailing newline) are part of it. Control: the
        default strips, which is right for a sha and wrong for a file."""
        from lib import evidence

        repo = _repo(tmp_path)
        content = "  risk_surfaces:\n  - src/\n\n"
        _commit(repo, "edges.yaml", content, "edges")
        rc, out, _err = evidence.run_git(repo, "show", "HEAD:edges.yaml", strip=False)
        assert (rc, out) == (0, content), out
        rc, out, _err = evidence.run_git(repo, "show", "HEAD:edges.yaml")
        assert (rc, out) == (0, content.strip()), out


# ---------------------------------------------------------------------------
# The release op: the same predicate, asked of a merged span
# ---------------------------------------------------------------------------


def _merged(tmp_path: Path, **kw) -> "tuple[Path, str]":
    repo, _rid = _deferring(tmp_path, **kw)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
    return repo, _git(repo, "rev-parse", "HEAD")


class TestTheReleaseOp:
    def test_a_merged_deferred_tail_reads_tail_deferred(self, tmp_path):
        repo, merge = _merged(tmp_path)
        entry = bc.classify_merge(repo, merge)
        assert entry.classification == bc.TAIL_DEFERRED, entry
        assert entry.classification not in bc.COVERED
        assert "deferred the fix tail" in entry.reason and "feature.py" in entry.reason

    def test_per_pr_reads_uncovered(self, tmp_path):
        repo, merge = _merged(tmp_path, key=None)
        assert bc.classify_merge(repo, merge).classification == bc.UNCOVERED

    def test_a_merged_tail_with_an_open_blocker_reads_uncovered(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, severity="blocking")
        _commit(repo, "feature.py", "y = 3\n", "fix the blocker")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        entry = bc.classify_merge(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.UNCOVERED, entry

    def test_the_predicate_asks_the_merged_tip_not_head(self, tmp_path):
        """On the base, HEAD is the merge: asked HEAD-relative, the anchor review
        sits behind the merge-base's descendant HEAD and its tail would be the
        whole merge. The merged span's answer comes from its own tip."""
        repo, merge = _merged(tmp_path)
        tip = _git(repo, "rev-parse", f"{merge}^2")
        mb = _git(repo, "merge-base", f"{merge}^1", tip)
        facts = gates.evidence.read_facts(repo)["facts"]
        verdict = gates.coverage_algebra.coverage_verdict
        diff_fn, key_fn = gates._cached_diff_fn(repo), gates._tree_key_fn(repo)

        def verdict_fn(f, b, t):
            return verdict(f, b, t, diff_fn, key_fn)

        answer = gates.fix_tail_deferral(repo, facts, _tree(repo, mb), _tree(repo, tip), mb, verdict_fn, tip=tip)
        assert answer is not None and answer["files"] == ["feature.py"], answer

    def test_a_later_merge_s_review_does_not_anchor_an_earlier_merge(self, tmp_path):
        """Asked HEAD-relative, every merged branch's review is behind HEAD, so a
        LATER branch's review is the nearest anchor for an earlier merge and the
        answer comes from the wrong branch. The merged span's own tip excludes it."""
        repo, first = _merged(tmp_path)
        _git(repo, "checkout", "-q", "-b", "feature2")
        _commit(repo, "second.py", "s = 1\n", "s1")
        _fact(repo, _tree(repo, "main"), _tree(repo), ["second.py"],
              findings=[{"fid": "R-9", "severity": "warning", "title": "t", "files": ["second.py"]}],
              counts={"blocking": 0, "warning": 1, "note": 0}, head_commit=_git(repo, "rev-parse", "HEAD"))
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature2", "feature2")
        assert bc.classify_merge(repo, first).classification == bc.TAIL_DEFERRED
