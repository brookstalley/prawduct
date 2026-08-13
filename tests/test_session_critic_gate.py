"""The Stop-hook Critic gate answers by composition (kernel-v3 chunk 04, Q2).

``gates.session_review_verdict`` replaces the mtime-vs-``.session-start``
freshness check and the verify-resolutions scope-subset check: the gate's
question is whether composed review coverage spans the session's base tree
(``.session-base-tree``, HEAD's tree recorded at session start) → the
current working tree (D3 capture), with zero unresolved blocking findings.
Both consumers — ``cmd_stop``'s blocking gate and the session-start advisory
(``briefing._check_previous_session_gates``) — delegate here, preserving the
STH-4F7C single-source property across the cutover.

Still-blocks regressions for the deleted mechanisms (learnings rule):

* mtime freshness → a fact at the wrong TREE never satisfies, however fresh;
  post-review edits leave a gap (the v2 file-level scope check's soundness
  hole — an in-scope edit after the review passed — cannot recur).
* verify-resolutions scope subsets → out-of-scope-shaped states are simply
  uncovered trees; no mode-specific carveout exists to widen.

Also pins the deliberate degradations: marker missing → HEAD-tree base (v2
jurisdiction, never a wedge); committed-unreviewed mid-session → satisfiable
via the merge-base fallback (composed coverage of merge-base → working tree,
the PR gate's own bar); schema-ahead facts → loud block with the reload
remedy, never a pass.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(ROOT))
from lib import briefing, evidence, gates  # noqa: E402

# The Stop hook itself, for the one class that pins its RENDERING rather than
# the shared verdict (extensionless shebang script; the module name is not
# "__main__", so CLI dispatch stays inert on import).
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_session_gate", str(ROOT / "bin" / "prawduct-hook")
)
_hook = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("prawduct_hook_session_gate", _hook_loader)
)
_hook_loader.exec_module(_hook)

_ids = itertools.count(1)


# ---------------------------------------------------------------------------
# Helpers (real git — capture/diff must behave as in production)
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


def _session_repo(tmp_path: Path) -> Path:
    """One-commit repo with .prawduct/ and the session base-tree marker set
    to HEAD's tree — the state cmd_clear leaves behind at session start."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    # Session-state files are gitignored in every onboarded repo (the
    # GITIGNORE_ENTRIES contract) — without this, the D3 capture would sweep
    # the markers themselves into the tree and every verdict would churn.
    (repo / ".gitignore").write_text(".prawduct/.session-*\n")
    _commit(repo, "code.py", "x = 1\n", "c1")
    (repo / ".prawduct").mkdir()
    _write_marker(repo)
    return repo


def _write_marker(repo: Path, tree: "str | None" = None) -> None:
    (repo / ".prawduct" / ".session-base-tree").write_text(tree or _tree(repo))


def _captured_tree(repo: Path) -> str:
    capture = evidence.capture_tree(repo)
    assert capture["status"] == "ok", capture
    return capture["tree"]


def _fact(
    repo: Path,
    base_tree: str,
    head_tree: str,
    files: list[str],
    *,
    findings: "list[dict] | None" = None,
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
            "files_reviewed": list(files),
            "findings": findings or [],
        },
    )
    assert result["status"] == "appended", result
    return fact_id


# ---------------------------------------------------------------------------
# Truth table
# ---------------------------------------------------------------------------


class TestSessionVerdictTruthTable:
    def test_fact_spanning_base_to_working_tree_covers(self, tmp_path):
        # The canonical chunk flow: edit → review (fact base=HEAD tree,
        # head=captured dirty tree) → gate at session end, pre-commit.
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        _fact(repo, _tree(repo), _captured_tree(repo), ["code.py"])
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered", verdict
        assert verdict["base_source"] == "marker"

    def test_clean_unchanged_tree_is_trivially_covered(self, tmp_path):
        repo = _session_repo(tmp_path)
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered"
        assert verdict["path"] == []

    def test_unreviewed_judgeable_edit_is_uncovered(self, tmp_path):
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"
        assert verdict["base"] and verdict["target"]

    def test_post_review_edit_reopens_the_gap(self, tmp_path):
        # The v2 soundness hole closed: an edit AFTER the review — even to a
        # file the review saw — moves the tree, and the old fact no longer
        # reaches the current state. Remedy: verify-resolutions (new fact).
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        reviewed = _captured_tree(repo)
        _fact(repo, _tree(repo), reviewed, ["code.py"])
        (repo / "code.py").write_text("x = 3\n")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"

    def test_verify_resolutions_shaped_fact_closes_the_gap(self, tmp_path):
        # …and the v-r fact (base = prior fact's head tree, head = current
        # capture) composes: review → fix → verify chains to covered.
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        reviewed = _captured_tree(repo)
        _fact(repo, _tree(repo), reviewed, ["code.py"])
        (repo / "code.py").write_text("x = 3\n")
        _fact(repo, reviewed, _captured_tree(repo), ["code.py"])
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered", verdict

    def test_non_judgeable_edit_composes_as_free_edge(self, tmp_path):
        # cmd_stop skips the gate for doc-only sessions, but the verdict
        # itself must also hold: a plain-.md delta needs no fact.
        repo = _session_repo(tmp_path)
        (repo / "notes.md").write_text("notes\n")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered"
        assert any(step["kind"] == "free" for step in verdict["path"])

    def test_protected_md_edit_still_uncovered(self, tmp_path):
        # CRT-5D8Q pin at the session boundary: skills/ prose is judgeable.
        repo = _session_repo(tmp_path)
        (repo / "skills" / "demo").mkdir(parents=True)
        (repo / "skills" / "demo" / "SKILL.md").write_text("prose\n")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"


class TestBlockingAndResolutions:
    def test_blocking_finding_on_path_blocks_and_lists(self, tmp_path):
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        rid = _fact(
            repo,
            _tree(repo),
            _captured_tree(repo),
            ["code.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "blocked"
        assert verdict["unresolved"][0]["review_id"] == rid
        assert verdict["unresolved"][0]["fid"] == "R-1"

    def test_resolution_fact_flips_blocked_to_covered(self, tmp_path):
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        rid = _fact(
            repo,
            _tree(repo),
            _captured_tree(repo),
            ["code.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        result = evidence.append_fact(
            repo,
            "resolution",
            "res-1",
            {"finding": {"review_id": rid, "fid": "R-1"}, "disposition": "fixed"},
        )
        assert result["status"] == "appended"
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered", verdict


# ---------------------------------------------------------------------------
# Degradations and fallbacks
# ---------------------------------------------------------------------------


class TestBaseFallbacks:
    def test_missing_marker_degrades_to_head_tree_base(self, tmp_path):
        # Pre-upgrade session / mid-session worktree entry: jurisdiction
        # shrinks to uncommitted work instead of wedging.
        repo = _session_repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").unlink()
        (repo / "code.py").write_text("x = 2\n")
        _fact(repo, _tree(repo), _captured_tree(repo), ["code.py"])
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered"
        assert verdict["base_source"] == "head-fallback"

    def test_missing_marker_still_blocks_unreviewed_uncommitted_work(self, tmp_path):
        repo = _session_repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").unlink()
        (repo / "code.py").write_text("x = 2\n")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"

    def test_merge_base_fallback_unwedges_committed_unreviewed_history(self, tmp_path):
        # Session base S is a mid-branch tree; a commit lands without review
        # (no dispatchable review can ever anchor at S again), then a
        # cumulative-shaped fact spans merge-base → HEAD. Q2 from S cannot
        # compose — the fallback accepts the strictly-stronger merge-base
        # coverage instead of leaving the session permanently blocked.
        repo = _session_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 1\n", "f1")
        _write_marker(repo)  # session starts here: S = feature tip tree
        _commit(repo, "more.py", "z = 1\n", "f2 (unreviewed commit)")
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py", "more.py"])
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered", verdict
        assert verdict["base_source"] == "merge-base-fallback"

    def test_merge_base_fallback_is_not_a_soft_pass(self, tmp_path):
        # Without evidence spanning merge-base → working tree, the fallback
        # changes nothing: still uncovered.
        repo = _session_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 1\n", "f1")
        _write_marker(repo)
        _commit(repo, "more.py", "z = 1\n", "f2 (unreviewed commit)")
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"


def _write_test_evidence(repo: Path, *, tree: "str | None" = ...) -> None:
    """A saved suite run in the shape ``gates.suite_vouches_for_current_tree``
    accepts — recorded ``evidence_tree`` == the current working tree. Timing is
    deliberately not what the transfer's third condition reads, so pass an
    explicit ``tree`` to model a run that predates the base advance."""
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".test-evidence.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-08-13T12:00:00Z",
                "passed": 12,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 3,
                "command": "pytest",
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "tests_executed": ["tests/test_x.py"],
                "changes_referenced": ["feature.py"],
                "coverage_level": "referenced",
                "evidence_tree": (
                    _captured_tree(repo) if tree is ... else tree
                ),
            }
        )
    )


def _advanced_base_session(tmp_path: Path) -> tuple[Path, str, str]:
    """The shape #654 is about: a branch reviewed at its tip, the session opens
    THERE, and the base is then synced into it during the session.

    The session base marker is the pre-sync branch tip, so the gate's own span
    (marker → working tree) is the advance itself and cannot compose; the
    merge-base span is the branch diff, which the review already covered before
    the base moved. That is exactly the span `/prawduct:pr` passes by transfer.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".prawduct/.session-*\n")
    _commit(repo, "code.py", "x = 1\n", "c1")
    (repo / ".prawduct").mkdir()
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature.py", "y = 2\n", "f1")
    prior_base, prior_head = _tree(repo, "main"), _tree(repo)
    _fact(repo, prior_base, prior_head, ["feature.py"])
    _write_marker(repo)  # the session opens at the reviewed branch tip
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "upstream.py", "u = 1\n", "u1")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
    return repo, prior_base, prior_head


class TestBaseAdvanceTransferAtTheSessionGate:
    """This gate asks the PR gate's composition question, so a span the PR gate
    passes by transfer has to pass here too.

    Before #654 it did not: `/prawduct:pr` Step 1 prescribes syncing the base,
    the synced span passed the PR gate by transfer, and the same tree was then
    blocked at session end — sending the builder to run exactly the cumulative
    round the transfer exists to remove. The conditions are unchanged; only this
    gate's merge-base fallback gained the attempt.
    """

    def test_a_base_advanced_session_passing_the_pr_gate_passes_here_too(
        self, tmp_path, capsys
    ):
        repo, prior_base, prior_head = _advanced_base_session(tmp_path)
        _write_test_evidence(repo)
        # Both gates, one fixture — the claim is about their agreement, and
        # asserting only this gate would let them drift apart again.
        assert gates.check_cumulative_critic(repo) == 0, capsys.readouterr().err
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "covered", verdict
        assert verdict["base_source"] == "merge-base-fallback"
        assert verdict["transferred"]["prior_base"] == prior_base
        assert verdict["transferred"]["prior_head"] == prior_head
        assert verdict["transferred"]["files"] == ["feature.py"]

    def test_the_grant_emits_the_same_yield_signal(self, tmp_path):
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        _write_test_evidence(repo)
        assert gates.session_review_verdict(repo)["status"] == "covered"
        records = [
            f
            for f in evidence.read_facts(repo)["facts"]
            if f.get("kind") == "guard-refusal"
        ]
        assert len(records) == 1
        assert records[0]["body"]["guard"] == "base-advance-transfer"
        assert records[0]["body"]["gate"] == "session-review-verdict"

    def test_a_repeated_gate_call_leaves_the_store_byte_identical(self, tmp_path):
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        _write_test_evidence(repo)
        assert gates.session_review_verdict(repo)["status"] == "covered"
        store = evidence.store_path(repo)
        after_first = store.read_bytes()
        for _ in range(3):
            assert gates.session_review_verdict(repo)["status"] == "covered"
        assert store.read_bytes() == after_first

    def test_an_unreviewed_judgeable_change_on_an_advanced_base_still_blocks(
        self, tmp_path
    ):
        # The regression the transfer must not weaken: the branch diff is no
        # longer the reviewed one, so nothing transfers.
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        _commit(repo, "extra.py", "w = 4\n", "new work, unreviewed")
        _write_test_evidence(repo)
        assert gates.session_review_verdict(repo)["status"] == "uncovered"

    def test_uncommitted_judgeable_work_denies_the_transfer(self, tmp_path):
        # This gate's target is the WORKING tree, not HEAD's — the one shape
        # difference from the PR gate. An uncommitted edit is in the required
        # diff, so no reviewed span matches it and the transfer fails closed
        # with no special case needed.
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        (repo / "feature.py").write_text("y = 2  # uncommitted\n")
        _write_test_evidence(repo)
        assert gates.session_review_verdict(repo)["status"] == "uncovered"

    def test_a_blocked_prior_span_transfers_nothing(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        (repo / ".gitignore").write_text(".prawduct/.session-*\n")
        _commit(repo, "code.py", "x = 1\n", "c1")
        (repo / ".prawduct").mkdir()
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 2\n", "f1")
        _fact(
            repo,
            _tree(repo, "main"),
            _tree(repo),
            ["feature.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "unsound"}],
        )
        _write_marker(repo)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "upstream.py", "u = 1\n", "u1")
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        _write_test_evidence(repo)
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] != "covered", verdict
        assert "transferred" not in verdict

    def test_a_stale_suite_denies_and_names_the_cheap_remedy_in_the_reason(
        self, tmp_path
    ):
        # The near miss worth naming: a suite run is minutes, and the block this
        # gate renders otherwise sends the builder to a full cumulative. This
        # gate has no stderr of its own, so the sentence rides on `reason` —
        # which is what the Stop hook prints.
        repo, _prior_base, prior_head = _advanced_base_session(tmp_path)
        _write_test_evidence(repo, tree=prior_head)
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"
        assert "ONLY condition denying the transfer" in verdict["reason"]
        assert "test-evidence record" in verdict["reason"]

    def test_no_saved_suite_at_all_still_names_the_remedy(self, tmp_path):
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"
        assert "no .test-evidence.json on disk" in verdict["reason"]

    def test_a_degraded_transfer_check_says_it_never_ran(self, tmp_path):
        # "Advice fails soft" is not "advice fails silent": a check that could
        # not run must not read as a finding that the gap is genuine work.
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        _write_test_evidence(repo)
        store = evidence.store_path(repo)
        lines = [json.loads(line) for line in store.read_text().splitlines()]
        for line in lines:
            if line.get("kind") == "review":
                line["body"]["head_tree"] = "0" * 40  # well-formed, absent
        store.write_text("".join(json.dumps(line) + "\n" for line in lines))
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"
        assert "could not run" in verdict["reason"]

    def test_an_unreviewed_branch_gets_the_unchanged_message(self, tmp_path):
        # The still-blocks regression: no prior review means no transfer, and
        # nothing about the transfer appears in what the builder reads.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        (repo / ".gitignore").write_text(".prawduct/.session-*\n")
        _commit(repo, "code.py", "x = 1\n", "c1")
        (repo / ".prawduct").mkdir()
        _git(repo, "checkout", "-q", "-b", "feature")
        _commit(repo, "feature.py", "y = 2\n", "f1")
        _write_marker(repo)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "upstream.py", "u = 1\n", "u1")
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        _write_test_evidence(repo)
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "uncovered"
        assert "transfer" not in verdict["reason"]

    def test_the_verdict_never_carries_the_internal_note_key(self, tmp_path):
        # `transfer_note` is a channel between the fallback and its caller, not
        # part of the verdict shape two consumers render.
        repo, _prior_base, _prior_head = _advanced_base_session(tmp_path)
        assert "transfer_note" not in gates.session_review_verdict(repo)


class TestFailClosed:
    def test_schema_ahead_fact_blocks_with_remedy(self, tmp_path):
        repo = _session_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        _fact(repo, _tree(repo), _captured_tree(repo), ["code.py"])
        store = evidence.store_path(repo)
        with open(store, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"schema": 99, "kind": "review", "id": "future-1", "ts": "t", "body": {}}
                )
                + "\n"
            )
        verdict = gates.session_review_verdict(repo)
        assert verdict["status"] == "schema-ahead"
        assert "Update the plugin" in verdict["reason"]

    def test_no_repo_is_an_error_not_a_pass(self, tmp_path):
        plain = tmp_path / "plain"
        (plain / ".prawduct").mkdir(parents=True)
        verdict = gates.session_review_verdict(plain)
        assert verdict["status"] == "error"


# ---------------------------------------------------------------------------
# The doc-only carveout helper (moved here from gitstate — one predicate)
# ---------------------------------------------------------------------------


class TestSessionChangesAllNonJudgeable:
    def _repo_with_baseline(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "code.py", "x = 1\n", "c1")
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / ".session-git-baseline").write_text("")
        return repo

    def test_plain_md_changes_qualify(self, tmp_path):
        repo = self._repo_with_baseline(tmp_path)
        (repo / "notes.md").write_text("n\n")
        assert gates.session_changes_all_non_judgeable(repo) is True

    def test_code_change_disqualifies(self, tmp_path):
        repo = self._repo_with_baseline(tmp_path)
        (repo / "notes.md").write_text("n\n")
        (repo / "code.py").write_text("x = 2\n")
        assert gates.session_changes_all_non_judgeable(repo) is False

    def test_protected_md_disqualifies(self, tmp_path):
        # The unification's behavior change, pinned deliberately: fork-skill
        # prose is behavioral logic, so it no longer rides the doc-only skip.
        repo = self._repo_with_baseline(tmp_path)
        (repo / "skills" / "demo").mkdir(parents=True)
        (repo / "skills" / "demo" / "SKILL.md").write_text("prose\n")
        assert gates.session_changes_all_non_judgeable(repo) is False

    def test_metadata_only_changes_do_not_qualify_as_doc_only(self, tmp_path):
        # No non-metadata change → False (the gate's has_changes guard owns
        # that case); metadata alone must not flip the doc-only carveout on.
        repo = self._repo_with_baseline(tmp_path)
        (repo / ".prawduct" / "backlog.md").write_text("b\n")
        assert gates.session_changes_all_non_judgeable(repo) is False

    def test_no_changes_is_false(self, tmp_path):
        repo = self._repo_with_baseline(tmp_path)
        assert gates.session_changes_all_non_judgeable(repo) is False


# ---------------------------------------------------------------------------
# The session-start advisory delegates to the same verdict (STH-4F7C survives)
# ---------------------------------------------------------------------------


class TestBriefingAdvisoryUsesSharedGate:
    def _plan_repo(self, tmp_path: Path) -> Path:
        repo = _session_repo(tmp_path)
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Demo\n"
        )
        (repo / ".prawduct" / ".session-git-baseline").write_text("")
        (repo / ".prawduct" / ".session-reflected").write_text(
            "Session reflection long enough to satisfy the fifty-character floor check."
        )
        return repo

    def test_uncovered_changes_warn(self, tmp_path):
        repo = self._plan_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        warnings = briefing._check_previous_session_gates(repo)
        assert "Critic review not recorded" in warnings

    def test_covered_changes_do_not_warn(self, tmp_path):
        repo = self._plan_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        _fact(repo, _tree(repo), _captured_tree(repo), ["code.py"])
        warnings = briefing._check_previous_session_gates(repo)
        assert not any("Critic" in w for w in warnings)

    def test_unresolved_blocking_findings_warn_with_count(self, tmp_path):
        repo = self._plan_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        _fact(
            repo,
            _tree(repo),
            _captured_tree(repo),
            ["code.py"],
            findings=[{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}],
        )
        warnings = briefing._check_previous_session_gates(repo)
        assert any("unresolved blocking" in w for w in warnings)


# ---------------------------------------------------------------------------
# Source-level: both consumers delegate; no inline copy re-grows
# ---------------------------------------------------------------------------


class TestSessionBaseTreeMarker:
    """`clear --session-start` records HEAD's tree — the base of every Q2
    verdict this session. Written best-effort: an unborn HEAD leaves the
    marker absent (the gate degrades to head-fallback) and never blocks
    session start."""

    def _run_clear(self, repo: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(ROOT / "bin" / "prawduct-hook"), "clear", "--session-start"],
            capture_output=True,
            text=True,
            cwd=str(repo),
            timeout=30,
            env={
                "CLAUDE_PROJECT_DIR": str(repo),
                "CLAUDE_PLUGIN_ROOT": str(ROOT),
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                "HOME": str(repo.parent / "_home"),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

    def test_clear_writes_head_tree_marker(self, tmp_path):
        (tmp_path / "_home").mkdir()
        repo = _session_repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").unlink()
        result = self._run_clear(repo)
        assert result.returncode == 0, result.stderr
        marker = (repo / ".prawduct" / ".session-base-tree").read_text().strip()
        assert marker == _tree(repo)

    def test_unborn_head_leaves_marker_absent_and_does_not_block(self, tmp_path):
        (tmp_path / "_home").mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        (repo / ".prawduct").mkdir()
        result = self._run_clear(repo)
        assert result.returncode == 0, result.stderr
        assert not (repo / ".prawduct" / ".session-base-tree").is_file()

    def test_clear_replaces_a_stale_marker(self, tmp_path):
        # The delete-then-rewrite in cmd_clear: a marker from the previous
        # session never leaks into this one.
        (tmp_path / "_home").mkdir()
        repo = _session_repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").write_text("stale" * 8)
        result = self._run_clear(repo)
        assert result.returncode == 0, result.stderr
        marker = (repo / ".prawduct" / ".session-base-tree").read_text().strip()
        assert marker == _tree(repo)


class TestNoInlineCopiesRemain:
    def test_both_consumers_delegate_to_the_shared_verdict(self):
        hook = (ROOT / "bin" / "prawduct-hook").read_text()
        brief = (ROOT / "lib" / "briefing.py").read_text()
        assert "session_review_verdict" in hook
        assert "session_review_verdict" in brief

    def test_no_mtime_freshness_against_findings_file_anywhere(self):
        # The deleted mechanism's signature: an mtime read of the findings
        # cache. Neither consumer nor the gate module may re-grow it.
        for rel in ("lib/gates.py", "lib/briefing.py"):
            source = (ROOT / rel).read_text()
            assert "critic_findings.stat" not in source, rel


class TestBriefingAdvisoryReadsTheBranchsPlan:
    """The advisory and the blocking gate must resolve the SAME plan.

    `briefing.py`'s comment promises they "can never diverge". Reading the
    pointer here while `cmd_stop` reads the branch is a divergence, and in the
    silent direction: nothing at session start about the gate that blocks at
    session end. The sibling suite stubs the predicate, so this is the only
    place the resolution itself is exercised.

    Discriminating by construction — the POINTER's plan is all `[x]` (so
    `_has_active_build_plan_file` reads False through it and the advisory goes
    quiet), the BRANCH's plan has an open chunk. Revert the branch resolution
    and this warning disappears.
    """

    def _two_plan_repo(self, tmp_path: Path) -> Path:
        repo = _session_repo(tmp_path)
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "---\nartifact: build-plan\nscope: pointed\n---\n\n"
            "# Build Plan\n\n## Status\n- [x] Chunk 01: shipped\n"
        )
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\n---\n\n"
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: in progress\n"
        )
        (repo / ".prawduct" / ".session-git-baseline").write_text("")
        (repo / ".prawduct" / ".session-reflected").write_text(
            "Session reflection long enough to satisfy the fifty-character floor check."
        )
        _git(repo, "checkout", "-q", "-b", "fix/mine")
        return repo

    def test_the_advisory_follows_the_branchs_plan(self, tmp_path):
        repo = self._two_plan_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        warnings = briefing._check_previous_session_gates(repo)
        assert "Critic review not recorded" in " ".join(warnings), (
            "the branch's plan has an open chunk, so there IS governed work and "
            f"the advisory must fire. warnings={warnings!r}"
        )

    def test_an_unmatched_branch_keeps_the_pointer_reading(self, tmp_path):
        """The fallback, pinned: no declared scope matches, behaviour unchanged."""
        repo = self._two_plan_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "fix/unrelated-name")
        (repo / "code.py").write_text("x = 2\n")
        warnings = briefing._check_previous_session_gates(repo)
        assert not any("Critic" in w for w in warnings), (
            "no branch match → the all-[x] pointer plan decides, exactly as "
            f"before. warnings={warnings!r}"
        )


# ---------------------------------------------------------------------------
# The superseded-blocker remedy reaches the Stop hook's message too (#536)
# ---------------------------------------------------------------------------


class TestSupersededAdviceReachesTheStopHook:
    """Two gates render a blocking verdict — the PR gate (pinned in
    ``test_cumulative_gate.py``) and ``cmd_stop``. Both prescribe
    verify-resolutions, which cannot clear a superseded blocker, so both must
    carry the spanning-review escape. This is the second site: the wording is
    shared, but a call site that never runs is the failure mode this catches.
    """

    @staticmethod
    def _blocking_session(tmp_path: Path) -> Path:
        """A session whose Stop reaches the Critic gate: committed baseline, an
        uncommitted judgeable change, an active build plan, reflection already
        satisfied so the Critic gate is the only blocker."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _commit(repo, "code.py", "x = 1\n", "c1")
        prawduct = repo / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n\n- [ ] Chunk 01: work\n"
        )
        (prawduct / ".session-reflected").write_text(
            "A sufficiently long session reflection so only the Critic gate blocks.\n"
        )
        (repo / "code.py").write_text("x = 2\n")
        return repo

    def _run_stop(self, repo: Path, monkeypatch, capsys, *, superseded: bool) -> str:
        monkeypatch.setattr(
            gates,
            "session_review_verdict",
            lambda project_dir: {
                "status": "blocked",
                "unresolved": [
                    {
                        "review_id": "rev-test-stranded",
                        "fid": "R-1",
                        "title": "a blocker",
                        "superseded": superseded,
                    }
                ],
                "base": "a" * 40,
                "target": "b" * 40,
            },
        )
        _hook.cmd_stop(repo, {})
        return capsys.readouterr().err

    @staticmethod
    def _shared_lines(*, superseded: bool) -> list[str]:
        return gates.blocking_remedy_lines([{"superseded": superseded}])

    def test_blocked_render_names_the_spanning_review(
        self, tmp_path, monkeypatch, capsys
    ):
        err = self._run_stop(
            self._blocking_session(tmp_path), monkeypatch, capsys, superseded=True
        )
        assert "unresolved blocking findings" in err
        assert "/prawduct:critic cumulative" in err

    def test_reachable_blocker_keeps_the_standard_remedy_only(
        self, tmp_path, monkeypatch, capsys
    ):
        err = self._run_stop(
            self._blocking_session(tmp_path), monkeypatch, capsys, superseded=False
        )
        assert "verify-resolutions" in err
        assert "/prawduct:critic cumulative" not in err

    @pytest.mark.parametrize("superseded", [True, False])
    def test_the_rendered_remedy_is_the_shared_one_verbatim(
        self, tmp_path, monkeypatch, capsys, superseded
    ):
        """The drift guard the two tests above do NOT give: they match a phrase,
        so a future edit that inlined divergent wording at ``cmd_stop`` would
        keep passing as long as that phrase survived. Every shared line must
        appear intact (indented) in the rendered block, which is what makes the
        one-home claim mechanical rather than aspirational."""
        err = self._run_stop(
            self._blocking_session(tmp_path), monkeypatch, capsys, superseded=superseded
        )
        for line in self._shared_lines(superseded=superseded):
            assert f"  {line}\n" in err, line
