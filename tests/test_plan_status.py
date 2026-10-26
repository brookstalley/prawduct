"""``lib/plan_status.py`` — chunk status as a query (#1051, Chunk 01).

The subject is the one answer to "is chunk N done" and "is this plan finished",
derived from review / resolution / ``chunk-imported`` facts, ``dropped:``
frontmatter and (until migration) the plan's ticked boxes. Fixtures are real git
repos, because ``done`` needs the certifying review's commit to be reachable
from the plan's branch, and that is git's answer, not a field.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import evidence, gitstate, plan_status  # noqa: E402

TS = "2026-10-25T10:00:00Z"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, env=env,
        check=True, timeout=10,
    ).stdout.strip()


def _commit(repo: Path, rel: str, text: str, subject: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, "seed.txt", "seed\n", "seed")
    _git(repo, "checkout", "-q", "-b", "feature/unit")
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    return repo.resolve()


def _plan(
    repo: Path,
    chunks: tuple[str, ...] = ("01", "02", "03"),
    *,
    extra_frontmatter: str = "",
    status: "dict[str, bool] | None" = None,
    deliverables: "dict[str, str] | None" = None,
    body: str = "",
    claim: tuple[str, ...] = ("branch: feature/unit", "base: main"),
) -> Path:
    lines = ["---", "artifact: build-plan", "scope: unit", *claim]
    if extra_frontmatter:
        lines.append(extra_frontmatter.rstrip("\n"))
    lines += ["---", "", "# Build Plan", ""]
    if status is not None:
        lines += ["## Status", ""]
        lines += [f"- [{'x' if done else ' '}] Chunk {cid}: c{cid}" for cid, done in status.items()]
        lines.append("")
    lines += ["## Build Chunks", ""]
    for cid in chunks:
        lines += [f"### Chunk {cid}: c{cid}", ""]
        lines.append(f"- **Deliverables:** {(deliverables or {}).get(cid, f'`src/c{cid}.py`')}")
        lines += ["- **Tests:** `tests/shared.py`", ""]
    lines.append(body)
    path = repo / ".prawduct" / "artifacts" / "build-plan-unit.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def _envelope(kind: str, fact_id: str, body: dict, ts: str = TS) -> dict:
    return {"schema": 1, "kind": kind, "id": fact_id, "ts": ts, "actor": {}, "body": body}


def _review(
    fact_id: str,
    anchor: "str | None",
    *,
    chunks: "list[str] | None" = None,
    chunk: "str | None" = None,
    blocking: "list[str]" = (),
    scope: str = "unit",
    dispatch_commit: "str | None" = None,
    ts: str = TS,
) -> dict:
    body: dict = {
        "scope": scope,
        "mode": "chunk",
        "chunk": chunk if chunk is not None else (chunks[0] if chunks else None),
        "head_commit": anchor,
        "dispatch_commit": dispatch_commit or anchor,
        "findings": [
            {"fid": fid, "severity": "blocking", "goal": "g", "title": f"t {fid}"}
            for fid in blocking
        ],
        "counts": {"blocking": len(blocking), "warning": 0, "note": 0},
    }
    if chunks is not None:
        body["chunks"] = chunks
    return _envelope("review", fact_id, body, ts)


def _resolution(fact_id: str, review_id: str, fid: str, disposition: str = "fixed") -> dict:
    return _envelope(
        "resolution", fact_id,
        {"finding": {"review_id": review_id, "fid": fid}, "disposition": disposition},
    )


def _imported(fact_id: str, chunk: str, scope: str = "unit") -> dict:
    return _envelope(
        IMPORTED, fact_id,
        {"scope": scope, "chunk": chunk, "source": "status-box", "imported_at": "2026-10-20T09:00:00Z"},
    )


IMPORTED = "chunk-imported"


def _facts(*envelopes: dict) -> dict:
    return {"status": "ok", "facts": list(envelopes)}


def _states(plan: Path, facts: dict, repo: Path) -> dict[str, str]:
    return {k: s.state for k, s in plan_status.chunk_states(plan, facts, repo_dir=repo).items()}


def _write_store(repo: Path, *envelopes: dict) -> Path:
    import json

    path = evidence.store_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in envelopes))
    return path


# ---------------------------------------------------------------------------
# done — review facts
# ---------------------------------------------------------------------------


class TestDoneFromReviewFacts:
    def test_one_fact_naming_two_chunks_completes_both_and_not_the_third(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "feat(unit): work (Chunk 01)")
        plan = _plan(repo)
        states = plan_status.chunk_states(plan, _facts(_review("R1", head, chunks=["01", "03"])), repo_dir=repo)
        assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "open", "03": "done"}
        assert (states["01"].fact_id, states["01"].date, states["01"].imported) == ("R1", "2026-10-25", False)
        assert states["02"] == plan_status.ChunkState("open")
        assert plan_status.current_chunks(plan, _facts(_review("R1", head, chunks=["01", "03"])), repo_dir=repo) == ["02"]

    def test_unresolved_blocking_completes_nothing_until_a_passing_resolution(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        review = _review("R1", head, chunks=["01"], blocking=["R-1", "R-2"])
        blocked = plan_status.chunk_states(plan, _facts(review), repo_dir=repo)["01"]
        assert blocked.state == "open"
        assert "R-1, R-2 not resolved" in blocked.reason

        half = _facts(review, _resolution("V1", "R1", "R-1"))
        assert _states(plan, half, repo) == {"01": "open"}
        # A resolution whose disposition is not a passing one clears nothing.
        unknown = _facts(review, _resolution("V1", "R1", "R-1"), _resolution("V2", "R1", "R-2", "deferred"))
        assert _states(plan, unknown, repo) == {"01": "open"}

        whole = _facts(review, _resolution("V1", "R1", "R-1"), _resolution("V2", "R1", "R-2", "waived"))
        assert _states(plan, whole, repo) == {"01": "done"}
        assert plan_status.is_finished(plan, whole, repo_dir=repo)

    def test_a_blocking_count_the_findings_cannot_account_for_certifies_nothing(self, repo):
        """census skips a finding with no fid; the count is what still says it exists."""
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        review = _review("R1", head, chunks=["01"])
        review["body"]["findings"] = [{"severity": "blocking", "title": "no fid"}]
        review["body"]["counts"]["blocking"] = 1
        assert _states(plan, _facts(review), repo) == {"01": "open"}

    def test_an_unreachable_commit_completes_nothing(self, repo):
        _commit(repo, "src/c01.py", "x\n", "work")
        _git(repo, "checkout", "-q", "-b", "side", "main")
        stray = _commit(repo, "src/stray.py", "x\n", "elsewhere")
        _git(repo, "checkout", "-q", "feature/unit")
        plan = _plan(repo, ("01",))
        state = plan_status.chunk_states(plan, _facts(_review("R1", stray, chunks=["01"])), repo_dir=repo)["01"]
        assert state.state == "open"
        assert "not on `feature/unit`" in state.reason
        # Control: the same fact anchored on the branch completes the chunk.
        head = _git(repo, "rev-parse", "HEAD")
        assert _states(plan, _facts(_review("R1", head, chunks=["01"])), repo) == {"01": "done"}

    def test_a_declared_working_branch_counts_as_reachable(self, repo):
        _git(repo, "checkout", "-q", "-b", "feature/unit-delegate")
        delegate = _commit(repo, "src/c01.py", "x\n", "delegate work")
        _git(repo, "checkout", "-q", "feature/unit")
        fact = _facts(_review("R1", delegate, chunks=["01"]))
        assert _states(_plan(repo, ("01",)), fact, repo) == {"01": "open"}
        plan = _plan(repo, ("01",), extra_frontmatter="working-branches:\n  - feature/unit-delegate")
        assert _states(plan, fact, repo) == {"01": "done"}

    def test_a_merged_plans_deleted_branch_is_probed_through_its_base(self, repo):
        """#1065: after the PR merge deletes the claimed branch, the review's
        commit is in the base, and the chunk reads done — not open with
        "its commit is not on `feature/unit`"."""
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        fact = _facts(_review("R1", head, chunks=["01"]))
        assert _states(plan, fact, repo) == {"01": "done"}
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature/unit")
        _git(repo, "branch", "-D", "feature/unit")
        state = plan_status.chunk_states(plan, fact, repo_dir=repo)["01"]
        assert (state.state, state.fact_id) == ("done", "R1")
        assert plan_status.is_finished(plan, fact, repo_dir=repo)

    def test_an_abandoned_branch_leaves_the_chunk_open_naming_the_base_and_the_gone_branch(self, repo):
        stray = _commit(repo, "src/c01.py", "x\n", "never merged")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "branch", "-D", "feature/unit")
        plan = _plan(repo, ("01",))
        state = plan_status.chunk_states(plan, _facts(_review("R1", stray, chunks=["01"])), repo_dir=repo)["01"]
        assert state.state == "open"
        assert "not on `main`" in state.reason
        assert "`feature/unit` is on no local or remote branch" in state.reason

    def test_a_fork_point_anchor_certifies_nothing_through_the_base(self, repo):
        """A review dispatched before the branch's first commit anchors at the
        fork point, which the base held before the review ran — the rule
        plan_lifecycle applies to the merge question."""
        fork = _git(repo, "rev-parse", "HEAD")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "branch", "-D", "feature/unit")
        plan = _plan(repo, ("01",))
        review = _review("R1", None, chunks=["01"], dispatch_commit=fork)
        review["body"]["base_commit"] = fork
        state = plan_status.chunk_states(plan, _facts(review), repo_dir=repo)["01"]
        assert state.state == "open"
        assert "review's own base commit" in state.reason
        # Control: the same anchor with a different base_commit is placed on main.
        review["body"]["base_commit"] = "0" * 40
        assert _states(plan, _facts(review), repo) == {"01": "done"}

    def test_a_branch_present_only_on_a_remote_is_probed_by_its_tracking_ref(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "pushed, not merged")
        _git(repo, "update-ref", "refs/remotes/origin/feature/unit", head)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "branch", "-D", "feature/unit")
        plan = _plan(repo, ("01",))
        assert _states(plan, _facts(_review("R1", head, chunks=["01"])), repo) == {"01": "done"}
        # A commit on neither the tracking ref nor anywhere else stays open, and
        # the base is NOT asked while the branch exists somewhere.
        _git(repo, "checkout", "-q", "-b", "side", "main")
        stray = _commit(repo, "src/stray.py", "x\n", "elsewhere")
        state = plan_status.chunk_states(plan, _facts(_review("R2", stray, chunks=["01"])), repo_dir=repo)["01"]
        assert state.state == "open"
        assert state.reason == "review R2 names it, but its commit is not on `feature/unit`"

    def test_a_prefix_sibling_of_the_gone_branch_does_not_count_as_present(self, repo, monkeypatch):
        """`for-each-ref refs/heads/feature/unit` also lists `feature/unit/spike`;
        the exact-name filter is what keeps that sibling from reading as the
        claimed branch, which would skip the base and leave the merged plan open."""
        head = _commit(repo, "src/c01.py", "x\n", "work")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature/unit")
        _git(repo, "branch", "-D", "feature/unit")
        _git(repo, "branch", "feature/unit/spike", "main")
        _git(repo, "update-ref", "refs/remotes/origin/feature/unit/spike", head)
        plan = _plan(repo, ("01",))
        fact = _facts(_review("R1", head, chunks=["01"]))
        assert gitstate.branch_refs(repo, ("feature/unit",)) == {}
        assert _states(plan, fact, repo) == {"01": "done"}
        # Positive control for the instrument: without the filter the sibling is
        # listed as present and the base is never asked.
        monkeypatch.setattr(gitstate, "ref_is_branch", lambda _ref, _branch: True)
        assert gitstate.branch_refs(repo, ("feature/unit",)) != {}
        state = plan_status.chunk_states(plan, fact, repo_dir=repo)["01"]
        assert (state.state, state.reason) == ("open", "review R1 names it, but its commit is not on `feature/unit`")

    def test_git_unable_to_list_the_branches_takes_no_fallback(self, repo, monkeypatch):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature/unit")
        _git(repo, "branch", "-D", "feature/unit")
        plan = _plan(repo, ("01",))
        fact = _facts(_review("R1", head, chunks=["01"]))
        assert _states(plan, fact, repo) == {"01": "done"}
        monkeypatch.setattr(gitstate, "branch_refs", lambda _repo, _branches: None)
        state = plan_status.chunk_states(plan, fact, repo_dir=repo)["01"]
        assert state.state == "open"
        assert state.reason == "review R1 names it, but its commit is not on `feature/unit`"

    def test_a_gone_branch_whose_base_resolves_nowhere_says_so(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "branch", "-D", "feature/unit")
        plan = _plan(repo, ("01",), claim=("branch: feature/unit", "base: nowhere"))
        state = plan_status.chunk_states(plan, _facts(_review("R1", head, chunks=["01"])), repo_dir=repo)["01"]
        assert state.state == "open"
        assert "`feature/unit` is on no local or remote branch, and the plan's `base: nowhere` names no ref" in state.reason

    def test_a_dirty_tree_review_anchors_at_its_dispatch_commit(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        review = _review("R1", None, chunks=["01"], dispatch_commit=head)
        assert _states(plan, _facts(review), repo) == {"01": "done"}

    def test_a_short_plans_one_boundary_fact_finishes_the_plan(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        boundary = _review("R9", head, chunks=["01", "02", "03"])
        boundary["body"]["mode"] = "cumulative"
        assert not plan_status.is_finished(plan, _facts(), repo_dir=repo)
        assert plan_status.is_finished(plan, _facts(boundary), repo_dir=repo)
        assert plan_status.current_chunks(plan, _facts(boundary), repo_dir=repo) == []

    def test_the_legacy_chunk_field_is_read_when_chunks_is_absent(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        legacy = _review("R1", head, chunk="2")  # no `chunks`; un-padded id
        assert _states(plan, _facts(legacy), repo) == {"01": "open", "02": "done", "03": "open"}
        assert plan_status.fact_chunks({"chunks": [], "chunk": "01"}) == []
        assert plan_status.fact_chunks({"chunk": None}) == []

    def test_another_scopes_fact_completes_nothing(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        assert _states(plan, _facts(_review("R1", head, chunks=["01"], scope="other")), repo) == {"01": "open"}

    def test_the_first_certifying_fact_in_store_order_is_cited_whatever_its_ts(self, repo):
        """Store (append) order decides, not the writer's clock: the second
        fact in the store carries the EARLIER `ts`, and the first is cited."""
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        facts = _facts(
            _review("R1", head, chunks=["01"], ts="2026-10-24T00:00:00Z"),
            _review("R2", head, chunks=["01"], ts="2026-10-20T00:00:00Z"),
        )
        state = plan_status.chunk_states(plan, facts, repo_dir=repo)["01"]
        assert (state.fact_id, state.date) == ("R1", "2026-10-24")

    def test_a_plan_declaring_no_branch_is_certified_by_no_review_and_says_so(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01", "02"), claim=(), status={"01": False, "02": True})
        states = plan_status.chunk_states(plan, _facts(_review("R1", head, chunks=["01"])), repo_dir=repo)
        assert states["01"] == plan_status.ChunkState(
            "open", reason="review R1 names it, but the plan declares no `branch:` its commit could be on"
        )
        assert states["02"].state == "done"  # an import still answers

    def test_a_review_recording_no_commit_says_so(self, repo):
        _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        review = _review("R1", None, chunks=["01"])
        review["body"]["dispatch_commit"] = None
        assert plan_status.chunk_states(plan, _facts(review), repo_dir=repo)["01"].reason == (
            "review R1 names it, but it records no commit to place"
        )


# ---------------------------------------------------------------------------
# done — imported boxes; dropped; edge plans
# ---------------------------------------------------------------------------


class TestImportedAndDropped:
    def test_a_ticked_box_reads_as_done_imported_and_writes_nothing(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, status={"01": True, "02": False, "03": False})
        store = _write_store(repo, _review("R0", head, chunks=["03"], scope="other"))
        before = store.read_bytes()
        plan_before = plan.read_bytes()
        facts = evidence.read_facts(repo)
        states = plan_status.chunk_states(plan, facts, repo_dir=repo)
        assert states["01"] == plan_status.ChunkState("done", imported=True)
        assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "open", "03": "open"}
        assert store.read_bytes() == before
        assert plan.read_bytes() == plan_before

    def test_a_chunk_imported_fact_is_done_imported_with_its_fact(self, repo):
        plan = _plan(repo, ("01", "02"))
        state = plan_status.chunk_states(plan, _facts(_imported("I1", "01")), repo_dir=repo)
        assert state["01"] == plan_status.ChunkState("done", "I1", "2026-10-20", imported=True)
        assert state["02"].state == "open"
        assert _states(plan, _facts(_imported("I1", "01", scope="other")), repo) == {"01": "open", "02": "open"}

    def test_a_box_answers_before_a_review_so_the_review_costs_no_probe(self, repo):
        """Precedence follows cost (NF1): a box or a `chunk-imported` fact is
        already an answer, so a review naming the same chunk is never probed.
        A box left unticked, the review answers (control)."""
        head = _commit(repo, "src/c01.py", "x\n", "work")
        review = _facts(_review("R1", head, chunks=["01"]))
        ticked = plan_status.chunk_states(_plan(repo, ("01",), status={"01": True}), review, repo_dir=repo)["01"]
        assert (ticked.state, ticked.fact_id, ticked.imported) == ("done", None, True)
        unticked = plan_status.chunk_states(_plan(repo, ("01",), status={"01": False}), review, repo_dir=repo)["01"]
        assert (unticked.state, unticked.fact_id, unticked.imported) == ("done", "R1", False)

    def test_dropped_with_a_reason_finishes_and_an_undeclared_unbuilt_chunk_does_not(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        fact = _facts(_review("R1", head, chunks=["01"]))
        undeclared = _plan(repo, ("01", "02"))
        assert not plan_status.is_finished(undeclared, fact, repo_dir=repo)
        assert plan_status.current_chunks(undeclared, fact, repo_dir=repo) == ["02"]

        declared = _plan(repo, ("01", "02"), extra_frontmatter="dropped:\n  - 02: superseded by the boundary review")
        states = plan_status.chunk_states(declared, fact, repo_dir=repo)
        assert states["02"] == plan_status.ChunkState("dropped", reason="superseded by the boundary review")
        assert plan_status.is_finished(declared, fact, repo_dir=repo)

    @pytest.mark.parametrize(
        "declaration, cause",
        [
            ("dropped:\n  - 02", "entry for 02 gives no reason"),
            ("dropped:\n  - '02:'", "entry for 02 gives no reason"),
            # The shapes the sequence reader refuses whole: flow, bare dash.
            ("dropped: [02]", "declared in a shape this reader does not parse"),
            ("dropped:\n  - 02: ok\n  -", "declared in a shape this reader does not parse"),
            # An item whose id is no id: the mapping form, prose.
            ("dropped:\n  - {id: 02, reason: x}", "names no chunk id"),
            ("dropped:\n  - the second one: x", "names no chunk id"),
            ("dropped:\n  - 09: not in this plan", "names 09, which is not a chunk of this plan"),
        ],
    )
    def test_an_unreadable_dropped_entry_leaves_the_chunk_open_and_says_why(
        self, repo, declaration, cause
    ):
        plan = _plan(repo, ("01", "02"), extra_frontmatter=declaration)
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
        assert states["02"].state == "open"
        assert cause in (states["02"].reason or ""), states["02"]
        assert not plan_status.is_finished(plan, _facts(), repo_dir=repo)

    @pytest.mark.parametrize("written", ["Chunk 02", "2", "'02'"])
    def test_a_dropped_id_is_read_as_the_plan_prints_it(self, repo, written):
        plan = _plan(repo, ("01", "02"), extra_frontmatter=f"dropped:\n  - {written}: cut")
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
        assert states["02"] == plan_status.ChunkState("dropped", reason="cut")
        assert states["01"] == plan_status.ChunkState("open")

    def test_a_reasonless_entry_says_why_it_dropped_nothing(self, repo):
        plan = _plan(repo, ("01", "02"), extra_frontmatter="dropped:\n  - 02")
        assert "gives no reason" in plan_status.chunk_states(plan, _facts(), repo_dir=repo)["02"].reason

    def test_a_plan_with_no_chunks_is_finished(self, repo):
        plan = _plan(repo, ())
        assert plan_status.chunk_states(plan, _facts(), repo_dir=repo) == {}
        assert plan_status.is_finished(plan, _facts(), repo_dir=repo)
        assert plan_status.current_chunks(plan, _facts(), repo_dir=repo) == []

    def test_an_unreadable_plan_is_not_finished_and_has_no_current_chunk(self, repo):
        missing = repo / ".prawduct" / "artifacts" / "build-plan-gone.md"
        states = plan_status.chunk_states(missing, _facts(), repo_dir=repo)
        assert list(states) == [plan_status.UNREADABLE_PLAN]
        assert states[plan_status.UNREADABLE_PLAN].synthetic
        assert not plan_status.is_finished(missing, _facts(), repo_dir=repo)
        assert plan_status.current_chunks(missing, _facts(), repo_dir=repo) == []
        assert plan_status.propose_chunks(missing, _facts(), [], "final", repo_dir=repo) == []

    def test_an_unparseable_chunk_heading_is_an_open_chunk_not_an_absence(self, repo):
        """A plan whose only heading the parser rejects must not read as 'no chunks'."""
        plan = _plan(repo, ("01",), body="#### Chunk 02: too deep\n")
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
        assert [(s.state, s.synthetic) for s in states.values()] == [("open", False), ("open", True)]
        synthetic = [k for k, s in states.items() if s.synthetic]
        assert synthetic[0].startswith("?L")
        assert "unparseable-chunk-heading" in states[synthetic[0]].reason
        assert not plan_status.is_finished(plan, _facts(), repo_dir=repo)
        # Not a chunk id: never handed out as one (a fact's `chunks` comes from these).
        assert plan_status.current_chunks(plan, _facts(), repo_dir=repo) == ["01"]
        for mode in ("final", "cumulative"):
            assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], mode, repo_dir=repo) == ["01"]

    def test_held_states_answer_without_a_second_walk(self, repo, monkeypatch):
        plan = _plan(repo, ("01",), status={"01": True})
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)

        def no_walk(*_a, **_kw):
            raise AssertionError("walked again")

        monkeypatch.setattr(plan_status, "chunk_states", no_walk)
        assert plan_status.is_finished(plan, _facts(), repo_dir=repo, states=states)
        assert plan_status.current_chunks(plan, _facts(), repo_dir=repo, states=states) == []


# ---------------------------------------------------------------------------
# NF1 — no git walk, no network, built_chunks never called
# ---------------------------------------------------------------------------


class _Spy:
    def __init__(self, monkeypatch):
        self.calls: list[list[str]] = []
        real = subprocess.Popen
        spy = self

        class Recording(real):  # type: ignore[misc, valid-type]
            def __init__(self, args, *a, **kw):
                spy.calls.append(list(args))
                super().__init__(args, *a, **kw)

        monkeypatch.setattr(subprocess, "Popen", Recording)

        def no_network(*_a, **_kw):
            raise AssertionError("chunk_states opened a socket")

        monkeypatch.setattr(socket, "socket", no_network)
        monkeypatch.setattr(socket, "create_connection", no_network)

        def no_built(*_a, **_kw):
            raise AssertionError("chunk_states called built_chunks")

        monkeypatch.setattr(plan_status, "built_chunks", no_built)


class TestNoGitWalk:
    def test_no_certifying_fact_costs_no_subprocess(self, repo, monkeypatch):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, status={"01": True, "02": False, "03": False},
                     extra_frontmatter="dropped:\n  - 03: cut")
        facts = _facts(
            _review("R0", head, chunks=["02"], scope="other"),   # another scope
            _review("R1", head, chunks=["02"], blocking=["R-1"]),  # blocked
            _review("R2", head, chunks=["01"]),                  # names a chunk already done
            _imported("I1", "02", scope="other"),
        )
        spy = _Spy(monkeypatch)
        states = plan_status.chunk_states(plan, facts, repo_dir=repo)
        assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "open", "03": "dropped"}
        assert spy.calls == []

    def test_a_certifying_fact_costs_only_ancestry_probes_memoized_per_anchor(self, repo, monkeypatch):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        facts = _facts(_review("R1", head, chunks=["01"]), _review("R2", head, chunks=["02"]))
        spy = _Spy(monkeypatch)
        assert _states(plan, facts, repo) == {"01": "done", "02": "done", "03": "open"}
        assert spy.calls == [["git", "merge-base", "--is-ancestor", head, "feature/unit"]]

    def test_a_gone_branch_costs_one_ref_lookup_and_one_base_probe_per_anchor(self, repo, monkeypatch):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature/unit")
        _git(repo, "branch", "-D", "feature/unit")
        facts = _facts(_review("R1", head, chunks=["01"]), _review("R2", head, chunks=["02"]))
        spy = _Spy(monkeypatch)
        assert _states(plan, facts, repo) == {"01": "done", "02": "done", "03": "open"}
        probes = [c for c in spy.calls if c[:2] == ["git", "merge-base"]]
        assert probes == [
            ["git", "merge-base", "--is-ancestor", head, "feature/unit"],
            ["git", "merge-base", "--is-ancestor", head, "main"],
        ]
        assert sum(1 for c in spy.calls if c[:2] == ["git", "for-each-ref"]) == 1

    def test_the_spy_sees_built_chunks_git_walk(self, repo, monkeypatch):
        """Positive control: the instrument catches a walk when one happens."""
        _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        real_built = plan_status.built_chunks
        spy = _Spy(monkeypatch)
        real_built(plan, repo)
        assert any(c[:2] == ["git", "log"] for c in spy.calls)


# ---------------------------------------------------------------------------
# propose_chunks and built_chunks
# ---------------------------------------------------------------------------


class TestProposeChunks:
    def test_chunk_mode_proposes_open_chunks_whose_deliverables_the_diff_touches(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01", "02", "03", "04"), deliverables={
            "01": "`src/c01.py`", "02": "new `src/c02.py`; `lib/pkg/` (the package)",
            "03": "`src/c03.py::main`", "04": "`src/c04.py`",
        })
        done01 = _facts(_review("R1", head, chunks=["01"]))
        diff = ["src/c01.py", "lib/pkg/mod.py", "src/c03.py", "tests/shared.py"]
        assert plan_status.propose_chunks(plan, _facts(), diff, "chunk", repo_dir=repo) == ["01", "02", "03"]
        # A done chunk is never proposed; a Tests path is not a Deliverable.
        assert plan_status.propose_chunks(plan, done01, diff, "chunk", repo_dir=repo) == ["02", "03"]
        assert plan_status.propose_chunks(plan, _facts(), ["tests/shared.py"], "chunk", repo_dir=repo) == []

    def test_a_one_segment_directory_in_deliverables_prose_matches_nothing_under_it(self, repo):
        """This repo's own plan: Chunk 03's Deliverables bullet says "any other
        `.prawduct/` write still refused" — prose about a tree, which must not
        make every governance write that chunk's work. A deeper directory still
        matches what is under it (control: `lib/pkg/` above)."""
        plan = _plan(repo, ("01", "02"), deliverables={
            "01": "`src/c01.py`; any other `.prawduct/` write still refused",
            "02": "`plugin/lib/backlog/`",
        })
        diff = [".prawduct/changes/x.md", "plugin/lib/backlog/cli.py"]
        assert plan_status.propose_chunks(plan, _facts(), diff, "chunk", repo_dir=repo) == ["02"]

    @pytest.mark.parametrize("mode", ["final", "cumulative"])
    def test_a_mid_plan_whole_plan_review_proposes_only_the_chunks_built(self, repo, mode):
        """#1072: a keystone `final` on Chunk 02 (planning.md's override) named
        02–07 and so certified four chunks nobody had built. Mode sets depth,
        not reach: the unbuilt 03 and 04 are not proposed."""
        head = _commit(repo, "src/c01.py", "x\n", "feat(unit): Chunk 01 — first")
        plan = _plan(repo, ("01", "02", "03", "04"))
        done01 = _facts(_review("R1", head, chunks=["01"]))
        _commit(repo, "src/c02.py", "x\n", "feat(unit): Chunk 02 — the keystone")
        assert plan_status.propose_chunks(plan, done01, ["src/c02.py"], mode, repo_dir=repo) == ["02"]
        # repo_dir omitted: derived from the plan's `.prawduct/` ancestor.
        assert plan_status.propose_chunks(plan, done01, ["src/c02.py"], mode) == ["02"]

    @pytest.mark.parametrize("mode", ["final", "cumulative"])
    def test_a_later_chunks_deliverable_touched_early_is_not_read_as_built(self, repo, mode):
        """The #1072 plan itself: `plan new`'s first commit stubs the change
        fragment, a Deliverable of the LAST chunk. A path touched outside the
        review's interval is not that chunk's work — only a subject naming it,
        or the interval's own diff, makes it so. Control: the same history read
        by `built_report`, which a table tag may afford, does tag 04."""
        plan = _plan(repo, ("01", "02", "03", "04"), deliverables={
            "04": "`.prawduct/changes/unit.md` (the change record)",
        })
        _commit(repo, ".prawduct/changes/unit.md", "stub\n", "docs(unit): build plan")
        head = _commit(repo, "src/c01.py", "x\n", "feat(unit): Chunk 01 — first")
        done01 = _facts(_review("R1", head, chunks=["01"]))
        _commit(repo, "src/c02.py", "x\n", "feat(unit): Chunk 02 — the keystone")
        assert plan_status.propose_chunks(plan, done01, ["src/c02.py"], mode, repo_dir=repo) == ["02"]
        assert "04" in plan_status.built_report(plan, repo).built

    def test_the_end_of_plan_cumulative_still_names_every_built_chunk(self, repo):
        """The boundary review is every open chunk's review once all are built —
        a short plan finishes on it — including a chunk whose Deliverables name
        no path, which reads as built only through a subject naming it (the
        commit `short_plan_next_step` tells the builder to make)."""
        plan = _plan(repo, ("01", "02", "03"), deliverables={"03": "the operator docs, revised"})
        _commit(repo, "src/c01.py", "x\n", "feat(unit): Chunk 01 — first")
        _commit(repo, "src/c02.py", "x\n", "feat(unit): Chunk 02 — second")
        _commit(repo, "notes.txt", "x\n", "docs(unit): the docs (Chunk 03)")
        diff = ["src/c01.py", "src/c02.py", "notes.txt"]
        assert plan_status.propose_chunks(plan, _facts(), diff, "cumulative", repo_dir=repo) == [
            "01", "02", "03"
        ]

    def test_uncommitted_work_in_the_interval_is_proposed_too(self, repo):
        """A dirty-tree `final` reviews work no commit carries yet: the diff
        reaches it even though `built_report` (commits only) cannot."""
        plan = _plan(repo, ("01", "02"))
        assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], "final", repo_dir=repo) == ["01"]

    def test_when_git_cannot_say_what_is_built_the_proposal_is_the_diffs_alone(self, repo):
        """Naming fewer fails closed (an open chunk keeps every gate armed);
        naming more is the defect. Control: the same commits with a base that
        resolves name 02 by its subject."""
        plan = _plan(repo, ("01", "02"), claim=("branch: feature/unit", "base: no-such-base"))
        _commit(repo, "notes.txt", "x\n", "feat(unit): Chunk 02 — second")
        assert plan_status.built_report(plan, repo).unavailable
        assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], "cumulative", repo_dir=repo) == ["01"]
        resolving = _plan(repo, ("01", "02"))
        assert plan_status.propose_chunks(resolving, _facts(), ["src/c01.py"], "cumulative", repo_dir=repo) == [
            "01", "02"
        ]

    def test_another_mode_proposes_nothing(self, repo):
        plan = _plan(repo)
        assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], "verify-resolutions", repo_dir=repo) == []


class TestBuiltChunks:
    def test_a_subject_naming_the_chunk_or_a_diff_touching_its_deliverables(self, repo):
        plan = _plan(repo, ("01", "02", "03"))
        _commit(repo, "notes.txt", "x\n", "feat(unit): Chunk 02 — the second")
        _commit(repo, "src/c03.py", "x\n", "unlabelled work")
        assert plan_status.built_chunks(plan, repo) == {"02", "03"}

    def test_with_no_base_or_branch_declared_it_walks_the_repo_base_to_head(self, repo):
        plan = _plan(repo, ("01", "02"), claim=())
        _commit(repo, "notes.txt", "x\n", "feat(unit): Chunk 02 — the second")
        assert plan_status.built_chunks(plan, repo) == {"02"}

    def test_an_option_shaped_branch_never_reaches_git(self, repo, monkeypatch):
        plan = _plan(repo, ("01", "02"), claim=("branch: --output=/tmp/x", "base: --all"))
        _commit(repo, "src/c01.py", "x\n", "work")
        built_chunks = plan_status.built_chunks  # the spy stubs the module name
        spy = _Spy(monkeypatch)
        assert built_chunks(plan, repo) == {"01"}  # walked from HEAD
        assert spy.calls, "the walk ran"
        assert not [c for c in spy.calls if any(a.startswith("--output") or a == "--all" for a in c)]

    def test_a_scoped_branch_ignores_a_foreign_plans_chunk_subject(self, repo):
        plan = _plan(repo, ("01", "02"))
        _commit(repo, "a.txt", "x\n", "feat(unit): scaffolding")
        _commit(repo, "b.txt", "x\n", "feat(other): land it (Chunk 01)")
        assert plan_status.built_chunks(plan, repo) == set()


class TestBuiltReportNamesWhyGitCouldNotAnswer:
    """Cumulative R-10: `built_chunks` answered `set()` for "nothing is built"
    and for "git could not say" alike, so `plan status` printed every row
    untagged and `built_not_done_notice` went silent exactly when git could not
    answer. `built_report` keeps the two apart; advice fails soft and names its
    consequence (`architecture.md`)."""

    def _cli(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        home = repo.parent / "_home"
        home.mkdir(exist_ok=True)
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "plan", "status", *args],
            cwd=str(repo), capture_output=True, text=True, timeout=30,
            env={**os.environ, "HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
                 "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
        )

    def test_a_declared_base_that_resolves_to_no_ref_is_unavailable(self, repo):
        plan = _plan(repo, ("01", "02"), claim=("branch: feature/unit", "base: no-such-base"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        report = plan_status.built_report(plan, repo)
        assert report.built == set()
        assert report.unavailable and "no-such-base" in report.unavailable, report
        assert plan_status.built_chunks(plan, repo) == set()  # the wrapper's signature holds

    def test_a_repo_with_no_commits_is_unavailable(self, tmp_path):
        bare = tmp_path / "fresh"
        bare.mkdir()
        _git(bare, "init", "-q", "-b", "main")
        (bare / ".prawduct" / "artifacts").mkdir(parents=True)
        plan = _plan(bare, ("01",), claim=())
        report = plan_status.built_report(plan, bare)
        assert report.built == set() and report.unavailable, report

    def test_the_control_answers_with_no_reason(self, repo):
        plan = _plan(repo, ("01", "02"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        report = plan_status.built_report(plan, repo)
        assert report == plan_status.BuiltReport({"01"}, None)

    def test_render_table_prints_the_marker_only_when_unavailable(self):
        states = {"01": plan_status.ChunkState("open")}
        assert plan_status.render_table(states, built_unavailable="git said no")[-1] == (
            "built: unavailable (git said no)"
        )
        assert not any(
            ln.startswith("built:") for ln in plan_status.render_table(states, built={"01"})
        )

    def test_plan_status_carries_the_marker_and_the_json_field(self, repo):
        _plan(repo, ("01", "02"), claim=("branch: feature/unit", "base: no-such-base"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        text = self._cli(repo)
        assert text.returncode == 0, text.stderr
        assert "  built: unavailable (" in text.stdout and "no-such-base" in text.stdout
        as_json = self._cli(repo, "--json")
        assert as_json.returncode == 0, as_json.stderr
        assert "no-such-base" in json.loads(as_json.stdout)["built_unavailable"]

    def test_plan_status_control_has_no_marker_and_a_null_field(self, repo):
        _plan(repo, ("01", "02"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        text = self._cli(repo)
        assert "built: unavailable" not in text.stdout and "built" in text.stdout
        assert json.loads(self._cli(repo, "--json").stdout)["built_unavailable"] is None

    def test_the_notice_degrades_to_a_named_cause_rather_than_silence(self, repo):
        _plan(repo, ("01", "02"), claim=("branch: feature/unit", "base: no-such-base"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        notice = plan_status.built_not_done_notice(repo)
        assert notice is not None and len(notice.splitlines()) == 1, notice
        assert notice.startswith(f"WARNING: {plan_status.BUILT_NOT_DONE_TOKEN}: ")
        assert "no-such-base" in notice and "cannot tell" in notice

    def test_the_notice_control_names_the_built_chunk(self, repo):
        _plan(repo, ("01", "02"))
        _commit(repo, "src/c01.py", "x\n", "feat(unit): land it (Chunk 01)")
        notice = plan_status.built_not_done_notice(repo)
        assert notice is not None and "  - Chunk 01: c01" in notice
        assert "cannot tell" not in notice


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------


def test_every_build_plan_in_this_repo_reads_without_an_unreadable_or_unparsed_key():
    """The parser reads every real plan this repo has: none answers a synthetic
    entry (the unreadable sentinel or an unparsed heading), and the walk saw
    plans.

    **Repo-coupled on purpose** (tests.md: a predicate that classifies real
    artifacts reads one). Plans are records, so a doc-only plan edit can red
    this while the test-status fast path still calls the last green current: a
    red here is the guard firing on a heading the parser cannot read — fix the
    heading it names. Ticking boxes or landing facts cannot red it: only which
    keys exist is asserted, never a state.
    """
    from lib import plan_index

    repo_root = ROOT.parent
    artifacts = repo_root / ".prawduct" / "artifacts"
    plans = [
        p for p in sorted(artifacts.rglob("*.md"))
        if plan_index.is_build_plan(p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert len(plans) >= 10, f"walked {len(plans)} plans — the corpus was not reached"
    bad = {}
    for p in plans:
        states = plan_status.chunk_states(p, _facts(), repo_dir=repo_root)
        odd = [s.reason for s in states.values() if s.synthetic]
        if odd:
            bad[p.relative_to(repo_root).as_posix()] = odd
    assert not bad, bad


# ---------------------------------------------------------------------------
# render_table — the one renderer, printed identically at three surfaces
# ---------------------------------------------------------------------------


class TestOneRenderer:
    """`plan status`, the `/clear` handoff and the PR payload print one table
    (#1051 Chunk 06 moved the renderer here from `briefing.chunk_table_lines`
    and the hook's `_cmd_plan_status`, which each had a copy)."""

    def _fixture(self, repo: Path) -> Path:
        """Every row shape: imported (a ticked box), built (a commit naming
        it), dropped with its reason beneath, and plain open."""
        plan = _plan(
            repo, ("01", "02", "03", "04"),
            status={"01": True, "02": False, "03": False, "04": False},
            extra_frontmatter="dropped:\n  - 03: descoped for the fixture",
        )
        _commit(repo, "src/c02.py", "x\n", "feat(unit): land it (Chunk 02)")
        return plan

    def test_render_table_shapes_every_row(self, repo):
        plan = self._fixture(repo)
        lines = plan_status.render_table(
            plan_status.chunk_states(plan, _facts(), repo_dir=repo),
            built=plan_status.built_chunks(plan, repo),
        )
        assert [ln.split() for ln in lines] == [
            ["chunk", "state", "fact", "date", "tags"],
            ["01", "done", "-", "-", "imported"],
            ["02", "open", "-", "-", "built"],
            ["03", "dropped", "-", "-", "-"],
            ["descoped", "for", "the", "fixture"],
            ["04", "open", "-", "-", "-"],
        ]
        assert lines[4] == "    descoped for the fixture"
        assert plan_status.render_table({}) == []

    def test_render_lifecycle_prints_state_release_and_reason(self):
        """The ``lifecycle:`` line ``plan status`` prints under the table: the
        release tag follows the state only when there is one."""
        from lib import plan_lifecycle

        in_progress = plan_lifecycle.Lifecycle(
            "in-progress", "`b` exists locally and its tip is not in `develop`'s history"
        )
        released = plan_lifecycle.Lifecycle(
            "released", "the change record ships scope `u` in v1.4.0", "v1.4.0"
        )
        assert plan_status.render_lifecycle(in_progress) == (
            "lifecycle: in-progress — `b` exists locally and its tip is not in `develop`'s history"
        )
        assert plan_status.render_lifecycle(released) == (
            "lifecycle: released v1.4.0 — the change record ships scope `u` in v1.4.0"
        )

    def test_plan_status_the_handoff_and_the_pr_payload_print_identical_rows(self, repo):
        import json

        from lib import briefing, pr_payload, work_unit

        self._fixture(repo)
        binding = work_unit.resolve(repo)
        assert binding.state == "bound", binding

        # `plan status` (the CLI), each line under its two-space indent.
        home = repo.parent / "_home"
        home.mkdir(exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "plan", "status"],
            cwd=str(repo), capture_output=True, text=True, timeout=30,
            env={**os.environ, "HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
                 "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # The table follows the summary and the lifecycle line (#1052); the
        # lifecycle is the CLI's alone — the handoff and payload show chunks.
        lines = proc.stdout.splitlines()
        assert lines[1].startswith("lifecycle: "), lines
        cli = [ln[2:] for ln in lines[2:]]

        # The handoff's fenced progress block.
        text = briefing.render_session_handoff(repo).text
        block = text.split("**Progress** (`prawduct-hook plan status`):\n```\n", 1)[1]
        handoff = block.split("```", 1)[0].splitlines()

        # The PR payload's build-plan section, under its two-space indent.
        body = pr_payload._section_build_plan(repo, binding).body
        after = body.split("## Chunk status (plan status; derived from facts):", 1)[1]
        payload = [ln[2:] for ln in after.splitlines()[1:]]

        assert len(cli) == 6 and cli[2].split()[-1] == "built", cli  # every row shape reached
        assert cli == handoff == payload, json.dumps(
            {"cli": cli, "handoff": handoff, "payload": payload}, indent=1
        )

