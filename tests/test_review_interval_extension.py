"""Nothing tells the builder to buy a round a later review will cover (#167).

When the branch's plan still owes a later review, and a covered frontier exists,
the next ``chunk``/``final`` review starts at that frontier and covers any fix
committed after it (``gates.covered_frontier``). So mode inference, the Stop
gate, the review close and ``cost-of-commit`` must stop recommending a
``verify-resolutions`` or ``cumulative`` round for that fix. Each surface is
tested in both directions: mid-plan (two or more chunks unticked, the round is
deferred) and near the end (one chunk unticked, today's answer stands).

Plans here have five chunks so the short-plan deferral (at most three) cannot
pre-empt what is being tested.
"""

from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

from lib import critic_consolidate as cc
from lib import critic_mode, work_unit
from lib.critic_mode import MODE_DEFERRED, infer_mode
from test_critic_consolidate import (
    FINDINGS_REL,
    HOOK,
    PARTIALS_REL,
    ROOT,
    _commit_file,
    _git,
    _git_env,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)
from test_short_plan_deferral import _GENERIC_BLOCK, _arm_stop, _run_stop, _short_plan_branch

WARNING = {"name": "Tighten the loop", "goal": "Nothing Is Unintended",
           "severity": "warning", "recommendation": "Tighten", "files": ["src/app.py"]}
BLOCKING = {"name": "Broken", "goal": "Nothing Is Broken",
            "severity": "blocking", "recommendation": "Fix", "files": ["src/app.py"]}
# Chunks already ticked of five. The chunk under review is the next one, still
# unticked: MID leaves it and four more (a later review is owed); END leaves it alone.
MID, END = 0, 4

#: A stubbed branch range for the fixtures below that build facts by hand:
#: ``feat/work``'s tip and the merge base it was cut from, newest first, the
#: shape ``evidence_notes._branch_commits`` answers. Which review is the
#: branch's is ``critic_consolidate.select_branch_review``'s to say, and it
#: decides by where a review ANCHORS on this range, so a hand-built fact
#: needs an anchor there, not only a branch name (#1180).
TIP, MERGE_BASE, OFF_LINEAGE = "1" * 40, "2" * 40, "3" * 40


def _on_the_branch(monkeypatch, facts: list, *, anchor: str = TIP,
                   recorded_on: "str | None" = "feat/work",
                   branch_range: "dict | None" = None) -> None:
    """Make ``facts`` reviews recorded on ``recorded_on`` (``None``: no
    ``actor.branch``, a pre-3.8 fact or a detached HEAD) and anchored at
    ``anchor``, with ``feat/work`` checked out over the stubbed range."""
    from lib import evidence, evidence_notes

    for f in facts:
        f["schema"] = evidence.SCHEMA_VERSION
        f["actor"] = {"branch": recorded_on} if recorded_on else {}
        f["body"]["head_commit"] = anchor
    monkeypatch.setattr(critic_mode.gitstate, "current_branch", lambda _p: "feat/work")
    monkeypatch.setattr(
        evidence_notes, "_branch_commits",
        lambda _p: branch_range or {"status": "ok", "commits": {TIP, MERGE_BASE},
                                    "ordered": [TIP, MERGE_BASE]},
    )


def _plan(
    ticked: int, last_type: "str | None" = None, deliverables: "dict[int, str] | None" = None
) -> str:
    """Five chunks, ``ticked`` of them done. ``last_type`` declares the LAST
    chunk's ``Type:`` (``cumulative-final`` makes its review the boundary one).
    A chunk delivers prose (``part N``, no path) unless ``deliverables`` maps
    its number to a backticked path."""
    rows = "".join(
        f"- [{'x' if n <= ticked else ' '}] Chunk {n}: part {n}\n" for n in range(1, 6)
    )
    sections = "".join(
        f"\n### Chunk {n}: part {n}\n\n"
        + (f"**Type:** {last_type}\n\n" if last_type and n == 5 else "")
        + (
            f"- **Delivers:** `{deliverables[n]}`\n"
            if deliverables and n in deliverables
            else f"- **Delivers:** part {n}\n"
        )
        for n in range(1, 6)
    )
    return (
        "---\nartifact: build-plan\nscope: work\nbranch: feat/work\n---\n\n"
        f"# Plan\n\n## Status\n\n{rows}{sections}"
    )


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _scenario(
    tmp_path: Path, ticked: int, findings: list, *, commit_fix: bool, commit_reviewed: bool = True,
    last_type: "str | None" = None, deliverables: "dict[int, str] | None" = None,
    chunks: "str | None" = None, seed: "dict[str, str] | None" = None,
) -> tuple[Path, str]:
    """The current chunk reviewed with ``findings``, committed verbatim (unless
    ``commit_reviewed`` is False: the fix then goes straight onto the reviewed,
    uncommitted tree), then the fix — committed or left in the working tree.
    Returns the repo and the NEXT-ACTION line."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    for rel, text in (seed or {}).items():  # files a later chunk's Deliverables name
        _commit_file(repo, rel, text, f"seed {rel}")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    _commit_file(
        repo, ".prawduct/artifacts/build-plan-work.md",
        _plan(ticked, last_type, deliverables), "plan",
    )
    _git(repo, "checkout", "-b", "feat/work", "--quiet")
    (repo / "src/app.py").write_text("x = 2\n")
    begin = _run_begin(repo, "--mode", "chunk", "--chunks", chunks or str(ticked + 1))
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=findings)
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    next_action = next(
        line for line in done.stdout.splitlines() if line.startswith("NEXT-ACTION:")
    )
    if commit_reviewed:
        _commit_all(repo, "the chunk, reviewed")
    (repo / "src/app.py").write_text("x = 3  # the finding, fixed\n")
    if commit_fix:
        _commit_all(repo, "fix, unreviewed")
    return repo, next_action


class TestLaterReviewOwed:
    def test_two_or_more_unticked_chunks_owe_a_later_review(self):
        progress = type("P", (), {"total": 5, "complete": 3})
        assert critic_mode.later_review_owed(progress)

    def test_one_unticked_chunk_is_ambiguous_and_owes_nothing(self):
        # Just reviewed but not yet ticked, or one chunk left: the conservative
        # reading keeps the round rather than defer a fix nothing will cover.
        progress = type("P", (), {"total": 5, "complete": 4})
        assert not critic_mode.later_review_owed(progress)


class TestModeInference:
    def test_a_fix_in_progress_mid_plan_is_deferred(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "extension-deferred (fix in progress)" in why

    def test_a_fix_in_progress_near_the_end_still_verifies(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == "verify-resolutions", why

    def test_a_committed_fix_mid_plan_is_deferred_not_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "extension-deferred (mid-plan, clean tree)" in why

    def test_a_committed_fix_near_the_end_still_infers_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why

    def test_a_blocker_is_never_deferred(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [BLOCKING], commit_fix=False)
        mode, why = infer_mode(repo, None)
        assert mode == "verify-resolutions", why

    def test_a_deferred_fix_reads_the_store_once(self, tmp_path, monkeypatch):
        """The extension path walks the covered frontier too; it takes the
        inference's one store read (`covered_frontier(read=)`), not its own."""
        from lib import evidence

        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        calls: list = []
        real = evidence.read_facts
        monkeypatch.setattr(
            evidence, "read_facts", lambda p: (calls.append(p), real(p))[1]
        )
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert len(calls) == 1, calls


class TestAFixIsToldFromTheNextChunkByItsDeliverables:
    """#1051: a review now closes the chunks it names the moment it records, so
    no unticked box says "still fixing this chunk". Condition (1a) asks the
    observable instead: does the work since the reviewed tree touch an OPEN
    chunk's Deliverables? Here chunk 1 was reviewed (WARNING) and certified."""

    def test_work_on_an_open_chunks_deliverable_is_not_deferred(self, tmp_path):
        """The control: chunk 2 delivers `src/two.py`, and that file is in the
        work in flight — it is chunk 2's build, not a fix, so its review is owed
        now and nothing defers."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False,
                            deliverables={2: "src/two.py"})
        (repo / "src/two.py").write_text("y = 1  # chunk 2's own work\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        assert critic_mode.extension_deferral_owed(
            repo, repo / ".prawduct", work_unit.resolve(repo),
            critic_mode.binding_progress(repo, work_unit.resolve(repo)),
        ) is None

    def test_the_fix_alone_beside_a_declared_deliverable_is_deferred(self, tmp_path):
        """Same plan, the fix only: no open chunk's Deliverables are touched,
        so the deferral stands — the pair shows the Deliverables test is what
        decides."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False,
                            deliverables={2: "src/two.py"})
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "chunk 1 was reviewed" in why, why

    def test_1141_shared_module_leaves_a_later_chunk_open_and_its_work_infers_a_review(self, tmp_path):
        """#1141-R3. Chunks 1 and 3 both list `src/app.py`, so the one-owner
        rule credits a touch of it to neither, and the review that names chunk 1
        leaves 3 open. Work that then touches the shared module may be 3's: the
        deferral asks whether the work touches an open chunk at all
        (`touched`), not whether a review could name one, or it would defer the
        review of a chunk nobody reviewed. Red before #1141: the proposal over
        the shared path was empty, so the work deferred."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True,
                            deliverables={1: "src/app.py", 3: "src/app.py"})
        owed = critic_mode.extension_deferral_owed(
            repo, repo / ".prawduct", work_unit.resolve(repo),
            critic_mode.binding_progress(repo, work_unit.resolve(repo)),
        )
        assert owed is None, owed
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why

    def test_work_on_a_chunk_ahead_of_an_open_one_is_not_deferred(self, tmp_path):
        """Design D4. Chunk 1 is reviewed and done, 2 is open (it lists no
        path), and the work touches only 3's path. The plan-order rule withholds
        3 from a proposal while 2 is open, so a deferral reading the proposal
        would read "no open chunk touched" and defer 3's review."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False,
                            deliverables={3: "src/three.py"})
        (repo / "src/app.py").write_text("x = 2\n")
        (repo / "src/three.py").write_text("w = 1  # chunk 3, built ahead of 2\n")
        _commit_all(repo, "the work")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        assert critic_mode.extension_deferral_owed(
            repo, repo / ".prawduct", work_unit.resolve(repo),
            critic_mode.binding_progress(repo, work_unit.resolve(repo)),
        ) is None

    def _owed(self, repo: Path):
        return critic_mode.extension_deferral_owed(
            repo, repo / ".prawduct", work_unit.resolve(repo),
            critic_mode.binding_progress(repo, work_unit.resolve(repo)),
        )

    def test_a_fix_to_the_reviewed_chunk_names_no_done_chunk(self, tmp_path):
        """Design D8's control: the deferral's ordinary case, a fix to the one
        chunk just reviewed, says nothing about retracting it."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False,
                            deliverables={1: "src/app.py"})
        owed = self._owed(repo)
        assert owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK, owed
        assert "plan retract" not in owed[1]

    def test_a_chunk_the_builder_named_is_not_questioned(self, tmp_path):
        """D8's other exclusion: the same two-chunk review, named by the
        builder with `--chunks 1,3`, so 3's route is their own words. Work on 3
        then defers with no clause: a declared certification is not second-
        guessed. The 1141 sequence below is the same shape with the route
        unrecorded, and does print it."""
        repo, _ = _scenario(
            tmp_path, MID, [WARNING], commit_fix=False, chunks="1,3",
            deliverables={1: "src/app.py", 3: "src/three.py"}, seed={"src/three.py": "w = 0\n"},
        )
        (repo / "src/app.py").write_text("x = 2\n")
        (repo / "src/three.py").write_text("w = 1\n")
        _commit_all(repo, "chunk 3's work")
        owed = self._owed(repo)
        assert owed is not None, owed
        assert "plan retract" not in owed[1], owed

    def test_the_1141_sequence_names_the_wrong_certification_then_retracting_it_reviews_it(self, tmp_path):
        """#1141 (A2, R8, R9) end to end. A pre-#1141 fact named 1 and 3, so 3
        reads done though nobody built it. 3's work then reads as a fix and
        defers, and the deferral names 3 and the fact so the builder can see
        the wrong certification where they meet it. Retracting 3 reopens it,
        its work then infers a review, and a review naming 3 certifies it."""
        from lib import evidence, plan_status

        repo, _ = _scenario(
            tmp_path, MID, [WARNING], commit_fix=False, chunks="1,3",
            deliverables={1: "src/app.py", 3: "src/three.py"}, seed={"src/three.py": "w = 0\n"},
        )
        # The reported repos' facts predate `chunks_declared`, and their
        # proposal named 3 (a path it merely touched): rewrite the fact so, as
        # `--chunks` cannot produce it now. Its route then reads unrecorded,
        # not the builder's own words.
        store = evidence.store_path(repo)
        lines = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
        for fact in lines:
            if fact.get("kind") == "review":
                fact["body"].pop("chunks_declared", None)
                fact["body"].pop("chunks_evidence", None)
                fact["body"]["chunks_proposed"] = ["1", "3"]
        store.write_text("".join(json.dumps(f) + "\n" for f in lines))
        (repo / "src/app.py").write_text("x = 2\n")  # the reviewed tree: no fix
        (repo / "src/three.py").write_text("w = 1  # chunk 3's real work\n")
        _commit_all(repo, "chunk 3's work")
        owed = self._owed(repo)
        assert owed is not None, owed
        assert "touches chunk 3's Deliverables" in owed[1] and "plan retract 3 --all" in owed[1], owed
        plan = repo / ".prawduct/artifacts/build-plan-work.md"
        fact_id = plan_status.chunk_states(plan, evidence.read_facts(repo), repo_dir=repo)["3"].fact_id
        assert f"`{fact_id}`" in owed[1]

        retract = subprocess.run(
            [sys.executable, str(HOOK), "plan", "retract", "3", "--all", "--reason", "never built"],
            cwd=str(repo), capture_output=True, text=True,
            env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
        )
        assert retract.returncode == 0, retract.stderr
        assert self._owed(repo) is None
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        begin = _run_begin(repo, "--mode", "chunk", "--chunks", "3")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"])
        assert _run_consolidate(repo).returncode == 0
        states = plan_status.chunk_states(plan, evidence.read_facts(repo), repo_dir=repo)
        assert states["3"].state == "done" and states["3"].fact_id != fact_id

    def test_a_chunk_with_no_path_deliverables_reads_as_a_fix_and_loses_nothing(self, tmp_path):
        """The accepted fail-open, with its DIRECTION asserted. No chunk here
        declares a path-shaped Deliverable, so chunk 2's own work (`src/two.py`)
        reads as a fix and defers. What makes that safe is that the next
        `chunk` review starts at the covered frontier and spans everything
        since — the fix AND the work — so nothing is left uncovered."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        reviewed = _git(repo, "rev-parse", "HEAD~1").stdout.strip()
        (repo / "src/two.py").write_text("y = 1  # chunk 2's own work\n")
        # The Stop gate's predicate (inference answers `chunk` here anyway: the
        # new file is outside the prior review, so rule 1 does not fire).
        owed = critic_mode.extension_deferral_owed(
            repo, repo / ".prawduct", work_unit.resolve(repo),
            critic_mode.binding_progress(repo, work_unit.resolve(repo)),
        )
        assert owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK, owed
        begin = _run_begin(repo, "--mode", "chunk", "--chunks", "2")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["base_commit"] == reviewed, manifest["base_commit"]
        assert manifest["base_extended_from"] is not None
        assert {"src/app.py", "src/two.py"} <= set(manifest["files_changed"]), manifest


class TestStopGate:
    def test_mid_plan_the_uncovered_fix_warns_instead_of_blocking(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 0, result.stderr
        assert _GENERIC_BLOCK not in result.stderr
        assert "deferred-boundary-review" in result.stderr
        assert "starts from the newest committed state a review covers" in result.stderr
        # A status nobody at exit 0 can act on stays in the log: no
        # `systemMessage` puts it in the user's transcript every turn. (Other
        # advisories, e.g. the handoff note, may still be shown.)
        shown = json.loads(result.stdout)["systemMessage"] if result.stdout.strip() else ""
        assert "deferred-boundary-review" not in shown

    def test_near_the_end_the_uncovered_fix_still_blocks(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert _GENERIC_BLOCK in result.stderr


class TestReviewClose:
    def test_mid_plan_the_close_leads_with_the_later_review(self, tmp_path):
        _, line = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        assert "This plan still owes a later review" in line
        # The advice it replaces must be gone, not trailing after it.
        assert cc._RIDE_ALONG_ROUTE.strip() not in line
        assert cc._IF_YOU_FIX_SOME.strip() not in line

    def test_near_the_end_the_close_keeps_its_price(self, tmp_path):
        _, line = _scenario(tmp_path, END, [WARNING], commit_fix=False)
        assert "This plan still owes a later review" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() in line

    def test_a_blocking_close_is_unchanged_mid_plan(self):
        line = cc.next_action_line("rev-x", 1, 0, 0, rides_next_review=critic_mode.OWED_LATER_CHUNK)
        assert "This plan still owes a later review" not in line
        assert "verify-resolutions" in line


class TestCostOfCommit:
    def _price(self, repo: Path) -> dict:
        result = subprocess.run(
            [sys.executable, str(HOOK), "cost-of-commit", "--json"],
            cwd=str(repo), capture_output=True, text=True,
            env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_mid_plan_the_unreviewed_commit_is_free(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        answer = self._price(repo)
        assert answer["verdict"] == "free"
        assert "starts from the newest committed state a review covers" in answer["rides_next_review"]

    def test_near_the_end_it_still_costs_a_round(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True)
        (repo / "src/other.py").write_text("y = 1\n")
        answer = self._price(repo)
        assert answer["verdict"] == "costs-a-round"
        assert answer["rides_next_review"] is None


class TestCoveringFallback:
    def test_final_is_recommended_when_a_frontier_sits_behind_the_commits(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        mode, why = cc.covering_fallback_mode(repo, head_tree, True)
        assert mode == "final", why
        assert "last reviewed state" in why

    def _unreviewed_commit(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _git(repo, "checkout", "-b", "feat/work", "--quiet")
        head = _commit_file(repo, "src/app.py", "x = 2\n", "unreviewed")
        return repo, _git(repo, "rev-parse", f"{head}^{{tree}}").stdout.strip()

    def test_cumulative_when_nothing_reviewed_and_code_is_in_flight(self, tmp_path):
        """No reviewed state behind the commits and judgeable work uncommitted:
        `final` would start at HEAD and miss them, so `cumulative` covers them."""
        repo, head_tree = self._unreviewed_commit(tmp_path)
        (repo / "src" / "wip.py").write_text("w = 1\n")
        mode, why = cc.covering_fallback_mode(repo, head_tree, True)
        assert mode == "cumulative", why

    def test_final_from_the_merge_base_when_nothing_judgeable_is_uncommitted(self, tmp_path):
        """The same commits with nothing judgeable in flight: the interval owner
        starts `final` at the merge-base, so it reaches them at inner-stage
        rigor. Red if the fallback re-derives the start instead of asking."""
        repo, head_tree = self._unreviewed_commit(tmp_path)
        mode, why = cc.covering_fallback_mode(repo, head_tree, True)
        assert mode == "final", why
        assert "merge-base" in why, why


class TestNothingOwedIsSkipped:
    """The two ways a deferral could skip a review that is owed."""

    def test_a_blocker_on_an_uncommitted_review_is_never_deferred(self, tmp_path):
        """The ordinary flow: review the uncommitted chunk, fix its blocker in
        place. The blocked tree was never committed, so the history walk cannot
        see it and finds the OLDER clean commit behind it — chunk 1's — as the
        frontier. Only the check on the newest review itself stops the defer."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2\n")
        begin = _run_begin(repo, "--mode", "chunk", "--chunks", "2")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"],
                       findings=[{**BLOCKING, "files": ["src/other.py"]}])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 2  # the blocker, fixed in place\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_a_later_chunk_nobody_reviewed_is_not_deferred(self, tmp_path):
        """Chunk 1 reviewed, committed and ticked; chunk 2 built and not
        reviewed. The frontier exists, a later review is owed — and still the
        pending work is a whole chunk, whose own review this must not skip."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2, unreviewed\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_a_blocker_a_verify_pass_left_open_is_never_deferred(self, tmp_path):
        """A verify pass that names no resolution and raises nothing new is clean
        on its own, while the blocker it was verifying is still open one review
        back. The chain has to be walked, not just the newest fact read."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=True)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-work.md"
        plan.write_text(_plan(1))
        _commit_all(repo, "tick chunk 1")
        (repo / "src/other.py").write_text("y = 1  # chunk 2\n")
        begin = _run_begin(repo, "--mode", "chunk", "--chunks", "2")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"],
                       findings=[{**BLOCKING, "files": ["src/other.py"]}])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 2  # an attempted fix\n")
        verify = _run_begin(repo, "--mode", "verify-resolutions", "--chunks", "2")
        assert verify.returncode == 0, verify.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
        assert _run_consolidate(repo).returncode == 0
        (repo / "src/other.py").write_text("y = 3  # keeps editing\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "deferred-boundary-review" not in result.stderr

    def test_after_a_cumulative_nothing_defers_and_the_close_promises_nothing(self, tmp_path):
        """A `cumulative` spans every chunk built so far and records at most one
        chunk id, so afterwards unticked boxes may be chunks awaiting their tick
        rather than chunks still to build. Found on this change's own branch:
        the boundary review's verify pass promised 'the next chunk's review
        covers the fix' with every chunk already built."""
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False)
        _commit_all(repo, "fix")
        begin = _run_begin(repo, "--mode", "cumulative", "--chunks", "1")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[WARNING])
        done = _run_consolidate(repo)
        assert done.returncode == 0, done.stderr
        line = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
        assert "This plan still owes a later review" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() in line  # the ordinary close, priced
        (repo / "src/app.py").write_text("x = 4  # a fix after the boundary review\n")
        mode, why = infer_mode(repo, None)
        assert mode != MODE_DEFERRED, why


class TestReviewChain:
    def _review(self, rid, base, head, ts, blocking=False, mode="chunk"):
        findings = [{"fid": "R-1", "severity": "blocking", "title": "x"}] if blocking else []
        return {"kind": "review", "id": rid, "ts": ts,
                "body": {"base_tree": base, "head_tree": head, "findings": findings, "mode": mode}}

    def test_every_review_at_a_linked_tree_is_on_the_chain(self):
        """A second review of an unchanged tree must not hide a blocker the
        first one raised at that same tree."""
        blocked = self._review("r1", "t0", "t1", "2026-09-22T10:00:00Z", blocking=True)
        rereview = self._review("r2", "t0", "t1", "2026-09-22T11:00:00Z")
        newest = self._review("r3", "t1", "t2", "2026-09-22T12:00:00Z")
        facts = [blocked, rereview, newest]
        chain = critic_mode.review_chain(facts, newest)
        assert {f["id"] for f in chain} == {"r1", "r2", "r3"}
        assert critic_mode._open_blocker_on_chain(facts, chain)

    def test_a_cumulative_anywhere_on_the_chain_marks_the_boundary(self):
        cumulative = self._review("r1", "t0", "t1", "2026-09-22T10:00:00Z",
                                  mode="cumulative (bundle review, ready for merge)")
        verify = self._review("r2", "t1", "t2", "2026-09-22T11:00:00Z",
                              mode="verify-resolutions (delta review, prior findings only)")
        assert critic_mode.boundary_review_on_chain(critic_mode.review_chain([cumulative, verify], verify))
        assert not critic_mode.boundary_review_on_chain(critic_mode.review_chain([verify], verify))

    def test_same_second_reviews_are_ordered_by_the_store_not_the_clock(self, monkeypatch):
        """`ts` has one-second resolution; CI records a chunk review and the
        cumulative after it in the same second. The store is append-only, so
        its order is the recording order, and it alone can break the tie."""
        ts = "2026-09-22T10:00:00Z"
        chunk = self._review("r1", "t0", "t1", ts)
        cumulative = self._review("r2", "t0", "t1", ts, mode="cumulative (bundle review, ready for merge)")
        verify = self._review("r3", "t1", "t2", ts,
                              mode="verify-resolutions (delta review, prior findings only)")
        _on_the_branch(monkeypatch, [chunk, cumulative, verify])
        from lib import evidence
        monkeypatch.setattr(evidence, "read_facts",
                            lambda _p: {"status": "ok", "facts": [chunk, cumulative, verify]})
        newest = critic_mode._newest_branch_review(Path("."))
        assert newest["id"] == "r3"
        chain = critic_mode.review_chain([chunk, cumulative, verify], newest)
        assert {f["id"] for f in chain} == {"r1", "r2", "r3"}
        assert critic_mode.boundary_review_on_chain(chain)
        # And the newest pick with a same-second tie at the END of the store.
        monkeypatch.setattr(evidence, "read_facts",
                            lambda _p: {"status": "ok", "facts": [chunk, cumulative]})
        assert critic_mode._newest_branch_review(Path("."))["id"] == "r2"


class TestOnlyASuppliedChunkIdIsCredited:
    """Condition 1 credits a chunk id a dispatch supplied, inherited along the
    review chain — never record-lint's Status-derived graded chunk, which is
    the same first-unticked reading as ``progress.current_id`` (#911)."""

    def _owed(self, monkeypatch, facts: list, states: dict, *, legacy: bool = False, **where):
        """``states`` maps id → ``ChunkState``: the answer ``plan_status`` gave.
        The work since the newest review is stubbed to touch no Deliverables.
        ``where`` places the facts on the branch (:func:`_on_the_branch`)."""
        from lib import evidence, gates, plan_status
        _on_the_branch(monkeypatch, facts, **where)
        monkeypatch.setattr(evidence, "read_facts", lambda _p: {"status": "ok", "facts": facts})
        monkeypatch.setattr(gates, "covered_frontier", lambda _p, **_k: {"commit": "abcdef1234567890"})
        monkeypatch.setattr(critic_mode, "_paths_since_tree", lambda _t, _p: set())
        monkeypatch.setattr(plan_status, "propose_chunks", lambda *_a, **_k: [])
        plan = type("Binding", (), {"plan_path": Path("plan.md"), "chosen_by": "binding",
                                    "is_legacy": legacy})
        open_ids = tuple(k for k, s in states.items() if s.state == "open")
        progress = critic_mode.PlanProgress(
            total=len(states), complete=len(states) - len(open_ids),
            current_id=open_ids[0] if open_ids else None, open_ids=open_ids,
            states=states, finished=not open_ids,
        )
        return critic_mode.extension_deferral_owed(Path("."), Path(".prawduct"), plan, progress)

    def test_a_chunkless_verify_is_not_credited_to_a_parked_chunk(self, monkeypatch):
        """Status `[ ] 01` (parked), `[x] 02`, `[x] 03`, `[ ] 04`, `[ ] 05`: the
        newest review is a verify pass with no `--chunk`, so record-lint graded
        the parked 01 — and so does current_id. No dispatch said 01, on a
        claimed plan or a legacy one."""
        from lib.plan_status import ChunkState
        verify = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [],
            "mode": "verify-resolutions (delta review, prior findings only)",
            "record_lint": {"chunk_graded": "01"}}}
        states = {"01": ChunkState("open"), "02": ChunkState("done", imported=True),
                  "03": ChunkState("done", imported=True), "04": ChunkState("open"),
                  "05": ChunkState("open")}
        assert self._owed(monkeypatch, [verify], states) is None
        assert self._owed(monkeypatch, [verify], states, legacy=True) is None

    def test_a_chunkless_verify_inherits_the_chunk_review_it_verifies(self, monkeypatch):
        """Ported to `chunk_states` (#1051): the chunk review r1 certified 04
        (its fact is the one ``chunk_states`` cites), the verify pass names no
        chunk and inherits 04 along the chain, and 05 is the later chunk whose
        review covers the fix."""
        from lib.plan_status import ChunkState
        chunk = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [], "mode": "chunk",
            "chunk": "04"}}
        verify = {"kind": "review", "id": "r2", "body": {
            "base_tree": "t1", "head_tree": "t2", "findings": [],
            "mode": "verify-resolutions (delta review, prior findings only)"}}
        states = {c: ChunkState("done", imported=True) for c in ("01", "02", "03")}
        states["04"] = ChunkState("done", fact_id="r1")
        states["05"] = ChunkState("open")
        owed = self._owed(monkeypatch, [chunk, verify], states)
        assert owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK, owed
        assert owed[1].startswith("chunk 04 was reviewed"), owed
        assert "starts from the newest committed state a review covers (abcdef123456)" in owed[1]
        assert "last reviewed state" not in owed[1]

    def test_a_reviewed_chunk_certified_by_its_box_defers_nothing(self, monkeypatch):
        """The chain names 04, but ``chunk_states`` answers 04 from a ticked box
        (an import), not from a fact on the chain: a box ticked after its review
        is the builder saying they moved on, so the work in flight may be the
        next chunk. No deferral — the control for the test above."""
        from lib.plan_status import ChunkState
        chunk = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [], "mode": "chunk",
            "chunk": "04"}}
        states = {c: ChunkState("done", imported=True) for c in ("01", "02", "03", "04")}
        states["05"] = ChunkState("open")
        assert self._owed(monkeypatch, [chunk], states) is None

    def test_an_earlier_chunk_review_on_the_chain_does_not_widen_the_set(self, monkeypatch):
        """The reviewed set is the NEWEST naming fact's, not the chain's union:
        r1 reviewed 03 (since ticked, so it reads as an import), r2 reviewed 04
        from r1's tree and certified it. The work in flight answers to 04, which
        r2 closed; a union would read 03's box as "moved on" and defer nothing."""
        from lib.plan_status import ChunkState
        chunk3 = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [], "mode": "chunk",
            "chunk": "03"}}
        chunk4 = {"kind": "review", "id": "r2", "body": {
            "base_tree": "t1", "head_tree": "t2", "findings": [], "mode": "chunk",
            "chunks": ["04"], "chunk": "04"}}
        states = {c: ChunkState("done", imported=True) for c in ("01", "02", "03")}
        states["04"] = ChunkState("done", fact_id="r2")
        states["05"] = ChunkState("open")
        owed = self._owed(monkeypatch, [chunk3, chunk4], states)
        assert owed is not None and owed[1].startswith("chunk 04 was reviewed"), owed

    def test_a_legacy_plan_keeps_the_open_current_chunk_reading(self, monkeypatch):
        """A legacy-window plan declares no `branch:`, so review facts certify
        nothing and the reviewed chunk stays open: there the reading before
        #1051 stands — the newest named chunk is the current one, and two or
        more open chunks owe a later review. A claimed plan in the same state
        (the chunk named but open, so not certified by the chain) defers
        nothing."""
        from lib.plan_status import ChunkState
        chunk = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [], "mode": "chunk",
            "chunk": "04"}}
        states = {c: ChunkState("done", imported=True) for c in ("01", "02", "03")}
        states["04"] = ChunkState("open")
        states["05"] = ChunkState("open")
        owed = self._owed(monkeypatch, [chunk], states, legacy=True)
        assert owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK, owed
        assert self._owed(monkeypatch, [chunk], states) is None


class TestTheDeferralStandsOnTheOwnersReview:
    """#1180 — the deferral's question is "may this review be deferred, given
    the newest review that covers this branch's lineage?". Which review covers
    the lineage is ``critic_consolidate.select_branch_review``'s answer, the
    one dispatch and inference use; it used to be a filter on the branch NAME
    a fact carries, which answered a nearby question. Each case runs the full
    predicate on one deferrable state (04 certified by r1, 05 still to build)
    and moves only where r1 sits; the first is the control that defers."""

    _owed = TestOnlyASuppliedChunkIdIsCredited._owed

    def _deferrable(self) -> "tuple[list, dict]":
        from lib.plan_status import ChunkState
        chunk = {"kind": "review", "id": "r1", "body": {
            "base_tree": "t0", "head_tree": "t1", "findings": [], "mode": "chunk",
            "chunk": "04"}}
        states = {c: ChunkState("done", imported=True) for c in ("01", "02", "03")}
        states["04"] = ChunkState("done", fact_id="r1")
        states["05"] = ChunkState("open")
        return [chunk], states

    def _deferred(self, monkeypatch, **where) -> bool:
        owed = self._owed(monkeypatch, *self._deferrable(), **where)
        return owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK

    def test_a_review_anchored_on_this_branch_defers(self, monkeypatch):
        assert self._deferred(monkeypatch)

    def test_a_review_off_this_lineage_defers_nothing_though_it_carries_this_branchs_name(
        self, monkeypatch
    ):
        """A reused branch name: `feat/work` deleted and cut again, its old
        review still in the clone-wide store under the same name. That review
        covers a lineage this branch is not on, so nothing it says can carry
        this branch's fix — the name filter deferred on it."""
        assert not self._deferred(monkeypatch, anchor=OFF_LINEAGE)

    def test_a_review_past_the_merge_base_answers_whatever_branch_recorded_it(self, monkeypatch):
        """A delegate's review merged in carries the delegate's branch name; a
        pre-3.8 fact or a detached-HEAD review carries none. Anchored on a
        commit of this branch, either covers this lineage — the name filter
        could not see them."""
        assert self._deferred(monkeypatch, recorded_on="delegate/chunk-04")
        assert self._deferred(monkeypatch, recorded_on=None)

    def test_at_the_merge_base_only_this_branchs_own_review_settles_it(self, monkeypatch):
        """The merge base is shared with every sibling cut from it. There the
        owner prefers a review recorded on this branch and, with none, falls
        back to whichever it has — right for a verify anchor, but it does not
        show this lineage was reviewed. Doubt keeps the review owed."""
        assert self._deferred(monkeypatch, anchor=MERGE_BASE)
        assert not self._deferred(monkeypatch, anchor=MERGE_BASE, recorded_on="feat/sibling")
        assert not self._deferred(monkeypatch, anchor=MERGE_BASE, recorded_on=None)

    def test_no_branch_range_defers_nothing(self, monkeypatch):
        """No merge base resolves: no review can be placed on the lineage."""
        assert not self._deferred(
            monkeypatch, branch_range={"status": "unbounded", "reason": "no base branch"}
        )

    def test_the_answer_is_the_owners(self, monkeypatch):
        """Settled, the review the deferral stands on is the one the cache
        writer and verify dispatch select — not a second answer that agrees."""
        from lib import evidence

        older = {"kind": "review", "id": "r-old", "ts": "2026-09-22T09:00:00Z",
                 "body": {"head_tree": "t0", "mode": "chunk"}}
        newer = {"kind": "review", "id": "r-new", "ts": "2026-09-22T10:00:00Z",
                 "body": {"head_tree": "t1", "mode": "chunk"}}
        _on_the_branch(monkeypatch, [older])
        _on_the_branch(monkeypatch, [newer], anchor=MERGE_BASE)
        facts = [older, newer]
        monkeypatch.setattr(evidence, "read_facts", lambda _p: {"status": "ok", "facts": facts})
        picked = critic_mode._newest_branch_review(Path("."))
        # Depth, not recording order: the review further along the branch.
        assert picked["id"] == "r-old"
        assert picked is cc.select_branch_review(facts, [TIP, MERGE_BASE], "feat/work")


CUMULATIVE_FINAL = "cumulative-final"


class TestBoundaryReviewOwed:
    """On a `Type: cumulative-final` plan the last chunk's review IS the boundary
    `cumulative`, which spans the branch from the merge-base. So a fix after an
    earlier review of that chunk rides it, and inference does not run a `final`
    first. Measured on consumers: every cumulative-final plan inspected ran
    final → verify-resolutions → cumulative, two rounds where one was owed."""

    def _owed(self, repo: Path, chain: list) -> "tuple[str, str] | None":
        prawduct = repo / ".prawduct"
        plan = work_unit.resolve(repo)
        progress = critic_mode.binding_progress(repo, plan)
        return critic_mode.review_owed_after(repo, prawduct, plan, progress, chain)

    def _newest_chain(self, repo: Path) -> list:
        from lib import evidence

        facts = evidence.read_facts(repo).get("facts") or []
        return critic_mode.review_chain(facts, critic_mode._newest_branch_review(repo))

    def test_a_cumulative_final_last_chunk_owes_the_boundary_review(self, tmp_path):
        """Renegotiated in the open (#1051): the chunk review of 05 now
        CERTIFIES 05 (a review fact closes the chunks it names), so the plan
        reads finished and "one box left" no longer carries the question. What
        is owed is read off the chain that closed it — the review just recorded
        — and with every chunk closed by that chain and the last one
        `Type: cumulative-final`, the boundary `cumulative` is still owed.
        Asked with an EMPTY chain, nothing shows the chunk closed by a review,
        and a finished plan owes nothing: the reading before #1051, kept."""
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        owed = self._owed(repo, self._newest_chain(repo))
        assert owed is not None and owed[0] == critic_mode.OWED_BOUNDARY, owed
        assert self._owed(repo, []) is None

    def test_a_plain_last_chunk_owes_nothing(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False)
        assert self._owed(repo, []) is None

    def test_mid_plan_owes_the_later_chunk_review(self, tmp_path):
        repo, _ = _scenario(tmp_path, MID, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        owed = self._owed(repo, [])
        assert owed is not None and owed[0] == critic_mode.OWED_LATER_CHUNK, owed

    def test_nothing_is_owed_once_a_cumulative_is_on_the_chain(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        cumulative = {"kind": "review", "id": "r1",
                      "body": {"mode": "cumulative (bundle review, ready for merge)"}}
        assert self._owed(repo, [cumulative]) is None

    def test_an_unreadable_plan_declares_nothing(self, tmp_path):
        missing = type("Binding", (), {"plan_path": tmp_path / "gone.md"})
        assert not critic_mode.declares_boundary_cumulative(tmp_path, missing)
        assert not critic_mode.declares_boundary_cumulative(tmp_path, None)

    def test_inference_defers_the_uncommitted_last_chunk_to_the_cumulative(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
        _commit_file(repo, ".prawduct/artifacts/build-plan-work.md",
                     _plan(END, CUMULATIVE_FINAL), "plan")
        _git(repo, "checkout", "-b", "feat/work", "--quiet")
        (repo / "src/app.py").write_text("x = 2  # the last chunk, uncommitted\n")
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert why.startswith("cumulative-final deferral"), why
        assert critic_mode.LAST_CHUNK_BOUNDARY_STEP in why
        # The way back is honoured: an explicit `final` still runs one.
        assert infer_mode(repo, "final")[0] == "final"
        # Control: the same state on a plain plan still infers `final`.
        _commit_file(repo, ".prawduct/artifacts/build-plan-work.md", _plan(END), "plain plan")
        (repo / "src/app.py").write_text("x = 3  # still uncommitted\n")
        assert infer_mode(repo, None)[0] == "final"

    def test_the_committed_last_chunk_infers_the_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True, last_type=CUMULATIVE_FINAL)
        mode, why = infer_mode(repo, None)
        assert mode == "cumulative", why

    def test_a_fix_in_progress_rides_the_cumulative(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        mode, why = infer_mode(repo, None)
        assert mode == MODE_DEFERRED, why
        assert "boundary `cumulative`" in why

    def test_the_close_names_the_cumulative_and_drops_the_price(self, tmp_path):
        _, line = _scenario(tmp_path, END, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        assert "This plan still owes its boundary `cumulative`" in line
        assert "This plan still owes a later review" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() not in line
        assert cc._IF_YOU_FIX_SOME.strip() not in line

    def test_a_blocking_close_still_verifies(self):
        line = cc.next_action_line("rev-x", 1, 0, 0, rides_next_review=critic_mode.OWED_BOUNDARY)
        assert "boundary `cumulative`" not in line
        assert "verify-resolutions" in line

    def test_the_stop_gate_defers_the_uncovered_fix(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True, last_type=CUMULATIVE_FINAL)
        (repo / "src/other.py").write_text("y = 1\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 0, result.stderr
        assert _GENERIC_BLOCK not in result.stderr
        assert "deferred-boundary-review" in result.stderr
        assert "spans the branch from the merge-base" in result.stderr

    def test_the_commit_is_free(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=True, last_type=CUMULATIVE_FINAL)
        (repo / "src/other.py").write_text("y = 1\n")
        answer = TestCostOfCommit()._price(repo)
        assert answer["verdict"] == "free"
        assert "boundary `cumulative`" in answer["rides_next_review"]

    def test_an_unreviewed_last_chunk_blocks_and_says_to_commit_first(self, tmp_path):
        """The gate still blocks the uncovered chunk — its review has not run —
        but its message agrees with inference: commit, then the cumulative."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
        _commit_file(repo, ".prawduct/artifacts/build-plan-work.md",
                     _plan(END, CUMULATIVE_FINAL), "plan")
        _git(repo, "checkout", "-b", "feat/work", "--quiet")
        (repo / "src/app.py").write_text("x = 2  # the last chunk, unreviewed\n")
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "last chunk is `Type: cumulative-final`" in result.stderr
        assert "no separate `final`" in result.stderr

    def test_after_the_cumulative_nothing_rides_it(self, tmp_path):
        repo, _ = _scenario(tmp_path, END, [WARNING], commit_fix=False, last_type=CUMULATIVE_FINAL)
        _commit_all(repo, "fix")
        begin = _run_begin(repo, "--mode", "cumulative", "--chunks", "5")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[WARNING])
        done = _run_consolidate(repo)
        assert done.returncode == 0, done.stderr
        line = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
        assert "This plan still owes" not in line
        assert cc._RIDE_ALONG_ROUTE.strip() in line
        # And inference no longer defers the chunk to a cumulative that has
        # already run: a later edit is reviewed, not sent to a second one.
        (repo / "src/later.py").write_text("z = 1  # an edit after the boundary review\n")
        # Renegotiated in the open (#1051): the cumulative names chunk 05 and
        # certifies it (the chunk review before it already had), so the plan is
        # FINISHED and rule 3 — "one chunk left" — is no longer reached; rule 4
        # answers `chunk`. The property kept is the one this test exists for:
        # the later edit is reviewed, never deferred to a second cumulative.
        # The post-cumulative check itself is pinned directly in
        # `test_a_cumulative_on_the_chain_discharges_the_boundary` below.
        mode, why = infer_mode(repo, None)
        assert mode == "chunk", why
        assert why.startswith("rule-4 chunk"), why
        # And the Stop gate's message agrees: it no longer says "then cumulative".
        _arm_stop(repo / ".prawduct")
        result = _run_stop(repo)
        assert result.returncode == 2, result.stderr
        assert "last chunk is `Type: cumulative-final`" not in result.stderr

    def test_a_cumulative_on_the_chain_discharges_the_boundary(self, monkeypatch):
        """`boundary_cumulative_still_owed` with exactly one chunk open and a
        cumulative-final last chunk: owed until a `cumulative` stands on the
        newest review's chain, and not after. Both directions, one fixture."""
        from lib import evidence
        monkeypatch.setattr(critic_mode, "declares_boundary_cumulative", lambda _p, _b: True)
        progress = critic_mode.PlanProgress(5, 4, "05", ("05",), {}, False)
        chunk = {"kind": "review", "id": "r1", "body": {"mode": "chunk", "head_tree": "t1"}}
        cumulative = {"kind": "review", "id": "r2",
                      "body": {"mode": "cumulative (bundle review, ready for merge)",
                               "base_tree": "t1", "head_tree": "t2"}}
        for facts, owed in (([chunk], True), ([chunk, cumulative], False)):
            monkeypatch.setattr(
                critic_mode, "_newest_branch_review", lambda _p, _read=None, f=facts: f[-1]
            )
            monkeypatch.setattr(evidence, "read_facts", lambda _p, f=facts: {"status": "ok", "facts": f})
            assert critic_mode.boundary_cumulative_still_owed(
                Path("."), Path(".prawduct"), object(), progress
            ) is owed, facts

    def test_a_cumulative_off_this_lineage_does_not_discharge_the_boundary(self, monkeypatch):
        """#1180, the boundary half: a `cumulative` recorded under this
        branch's name on a lineage it is not on (the name reused) says nothing
        about this branch, so the boundary review is still owed. The same
        cumulative anchored on the branch discharges it — the control. Asked
        through the real selection, not a stubbed one."""
        from lib import evidence
        monkeypatch.setattr(critic_mode, "declares_boundary_cumulative", lambda _p, _b: True)
        progress = critic_mode.PlanProgress(5, 4, "05", ("05",), {}, False)
        for anchor, owed in ((OFF_LINEAGE, True), (TIP, False)):
            cumulative = {"kind": "review", "id": "r2",
                          "body": {"mode": "cumulative (bundle review, ready for merge)",
                                   "base_tree": "t1", "head_tree": "t2"}}
            _on_the_branch(monkeypatch, [cumulative], anchor=anchor)
            monkeypatch.setattr(evidence, "read_facts",
                                lambda _p, f=[cumulative]: {"status": "ok", "facts": f})
            assert critic_mode.boundary_cumulative_still_owed(
                Path("."), Path(".prawduct"), object(), progress
            ) is owed, anchor


class TestShortPlanBoundaryOwed:
    """A short plan's boundary `cumulative` is every chunk's review, so on its
    last chunk a fix after an earlier review rides it — with no declaration.
    The 5-chunk fixtures above can never reach this arm (a short plan has at
    most three chunks)."""

    def _owed(self, repo: Path):
        prawduct = repo / ".prawduct"
        plan = work_unit.resolve(repo)
        progress = critic_mode.binding_progress(repo, plan)
        return critic_mode.review_owed_after(repo, prawduct, plan, progress, [])

    def test_the_last_chunk_of_a_short_plan_owes_the_boundary_review(self, tmp_path):
        _short_plan_branch(tmp_path, chunks=3, committed=("01", "02"))
        owed = self._owed(tmp_path)
        assert owed is not None and owed[0] == critic_mode.OWED_BOUNDARY, owed
        assert "the plan is short" in owed[1]

    def test_a_long_plan_on_its_last_chunk_owes_nothing(self, tmp_path):
        """Control: same state, five chunks — not short, no declaration."""
        _short_plan_branch(tmp_path, chunks=5, committed=("01", "02", "03", "04"))
        assert self._owed(tmp_path) is None

    def test_the_close_after_a_review_of_that_chunk_names_the_cumulative(self, tmp_path):
        _short_plan_branch(tmp_path, chunks=3, committed=("01", "02"))
        begin = _run_begin(tmp_path, "--mode", "chunk", "--chunks", "3")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((tmp_path / PARTIALS_REL / "manifest.json").read_text())
        _write_partial(tmp_path, "reviewer", manifest["commit_reviewed"],
                       findings=[{**WARNING, "files": ["src/wip.py"]}])
        done = _run_consolidate(tmp_path)
        assert done.returncode == 0, done.stderr
        line = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
        assert "This plan still owes its boundary `cumulative`" in line
        assert cc._RIDE_ALONG_ROUTE.strip() not in line


class TestAnchorRefusalsNameACoveringMode:
    """Every ``verify-resolutions`` demotion names the mode that covers the work
    (#662). The exit-2 widening always did; the exit-1 anchor refusals (no
    prior review on this lineage, a fact with no ``head_tree``, a prior tree
    that cannot be diffed) returned prose only, and the reader applied the
    demotion property by hand — the rule exit 2 moved out of prose because
    prose did not hold. Each now carries ``kind: "anchor-unusable"`` and the
    one recommender's ``fallback_mode``, at exit 1 still."""

    def _reviewed_commit(self, tmp_path: Path, branch: str = "feat/work") -> Path:
        """``branch`` cut from ``main``, one judgeable commit on it, reviewed
        clean on a clean tree (so the review spans merge-base → that commit)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
        _git(repo, "checkout", "-b", branch, "--quiet")
        _commit_file(repo, "src/app.py", "x = 2\n", "the chunk")
        begin = _run_begin(repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert "src/app.py" in manifest["files_changed"], manifest
        _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
        done = _run_consolidate(repo)
        assert done.returncode == 0, done.stderr
        return repo

    def _reword_the_reviewed_commit(self, repo: Path) -> None:
        """Rewritten history: the reviewed commit's anchor leaves the lineage,
        while its TREE — which the coverage composition reads — survives."""
        reworded = _git(repo, "commit", "--amend", "-m", "the chunk, reworded", "--quiet")
        assert reworded.returncode == 0, reworded.stderr

    def test_committed_work_after_a_rewritten_anchor_names_final_from_the_frontier(
        self, tmp_path
    ):
        """The issue's committed-delta case. Since #1150 a deleted cache alone
        re-derives the anchor from this branch's review, so the refusal is
        reached the way it now is: the reviewed commit was reworded (its anchor
        is off the lineage, its tree still composes). Two commits after it, a
        clean tree, the cache deleted. The named mode is `final`, and the
        `final` it names starts at the frontier, so the two commits are in its
        interval."""
        repo = self._reviewed_commit(tmp_path)
        self._reword_the_reviewed_commit(repo)
        _commit_file(repo, "src/b.py", "b = 1\n", "after one")
        _commit_file(repo, "src/c.py", "c = 1\n", "after two")
        (repo / FINDINGS_REL).unlink()

        refused = cc.begin_review(repo, "verify-resolutions")
        assert refused["status"] == "error", refused
        assert refused.get("kind") == "anchor-unusable", refused
        assert refused.get("fallback_mode") == "final", refused
        assert refused["reason"].startswith("no prior review to verify: "), refused
        assert "Re-dispatch as `final`" in refused["reason"], refused
        assert "last reviewed state" in refused["reason"], refused

        final = cc.begin_review(repo, refused["fallback_mode"])
        assert final["status"] == "ok", final
        changed = final["manifest"]["files_changed"]
        assert "src/b.py" in changed and "src/c.py" in changed, changed
        assert "src/app.py" not in changed, changed  # it starts at the frontier

    def test_a_branch_switch_with_a_stray_names_cumulative(self, tmp_path):
        """A sibling branch's review in the cache, nothing reviewed on this
        lineage, committed work, and one stray judgeable untracked file: `final`
        would start at HEAD and review the stray, so `cumulative` is named."""
        repo = self._reviewed_commit(tmp_path, branch="feat/a")
        _git(repo, "checkout", "main", "--quiet")
        _git(repo, "checkout", "-b", "feat/b", "--quiet")
        _commit_file(repo, "src/b.py", "b = 1\n", "unreviewed work")
        (repo / "src" / "stray.py").write_text("s = 1\n")

        refused = cc.begin_review(repo, "verify-resolutions")
        assert refused.get("kind") == "anchor-unusable", refused
        assert refused.get("fallback_mode") == "cumulative", refused
        assert "not an ancestor of HEAD" in refused["reason"], refused
        assert "Re-dispatch as `cumulative`" in refused["reason"], refused

    def test_a_covered_head_with_uncommitted_work_names_final(self, tmp_path):
        """The new arm: the frontier IS HEAD's tree (the reworded commit is
        HEAD), so the committed work is covered and only the uncommitted part
        remains — `final`, not the `cumulative` the fall-through gave."""
        repo = self._reviewed_commit(tmp_path)
        self._reword_the_reviewed_commit(repo)
        (repo / "src" / "wip.py").write_text("w = 1\n")

        refused = cc.begin_review(repo, "verify-resolutions")
        assert refused.get("kind") == "anchor-unusable", refused
        assert refused.get("fallback_mode") == "final", refused
        assert "already covered" in refused["reason"], refused

    def test_the_covered_head_arm_at_the_recommender(self, tmp_path):
        """The same arm at the recommender, which the exit-2 door shares."""
        repo = self._reviewed_commit(tmp_path)
        (repo / "src" / "wip.py").write_text("w = 1\n")
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        mode, why = cc.covering_fallback_mode(repo, head_tree, True)
        assert mode == "final", why
        assert "already covered" in why, why

    def test_a_prior_fact_without_a_head_tree_names_a_mode(self, tmp_path, monkeypatch):
        """The second refusal site: the prior fact records no ``head_tree``."""
        repo = self._reviewed_commit(tmp_path)
        (repo / "src" / "wip.py").write_text("w = 1\n")
        real = cc._prior_review_fact

        def headless(*args, **kwargs):
            fact, note = real(*args, **kwargs)
            assert fact is not None, note
            return {**fact, "body": {**fact["body"], "head_tree": None}}, note

        monkeypatch.setattr(cc, "_prior_review_fact", headless)
        refused = cc.begin_review(repo, "verify-resolutions")
        assert refused.get("kind") == "anchor-unusable", refused
        assert refused.get("fallback_mode") == "final", refused
        assert "records no head_tree" in refused["reason"], refused
        assert "Re-dispatch as `final`" in refused["reason"], refused

    def test_an_undiffable_prior_tree_names_a_mode(self, tmp_path, monkeypatch):
        """The third refusal site: the prior tree cannot be diffed."""
        repo = self._reviewed_commit(tmp_path)
        _commit_file(repo, "src/b.py", "b = 1\n", "after")
        monkeypatch.setattr(cc.evidence, "tree_diff", lambda *_a, **_k: None)
        refused = cc.begin_review(repo, "verify-resolutions")
        assert refused.get("kind") == "anchor-unusable", refused
        assert refused.get("fallback_mode") == "final", refused
        assert "cannot diff prior reviewed tree" in refused["reason"], refused
        assert "Re-dispatch as `final`" in refused["reason"], refused

    def test_the_cli_still_exits_1_and_names_the_mode(self, tmp_path):
        repo = self._reviewed_commit(tmp_path)
        self._reword_the_reviewed_commit(repo)
        _commit_file(repo, "src/b.py", "b = 1\n", "after")
        done = _run_begin(repo, "--mode", "verify-resolutions")
        assert done.returncode == 1, (done.stdout, done.stderr)
        assert "Re-dispatch as `final`" in done.stderr, done.stderr

    def test_an_unusable_store_still_exits_6_and_names_no_mode(self, tmp_path):
        """Control: no re-dispatch repairs a store, so it keeps its own exit
        and names no mode."""
        from lib import evidence

        repo = self._reviewed_commit(tmp_path)
        self._reword_the_reviewed_commit(repo)
        store = evidence.store_path(repo)
        with store.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"schema": max(evidence.SUPPORTED_SCHEMAS) + 1,
                                 "kind": "review", "id": "from-the-future"}) + "\n")
        result = cc.begin_review(repo, "verify-resolutions")
        assert result.get("kind") == "store-unusable", result
        assert "fallback_mode" not in result, result
        done = _run_begin(repo, "--mode", "verify-resolutions")
        assert done.returncode == 6, (done.stdout, done.stderr)
        assert "Re-dispatch" not in done.stderr, done.stderr
