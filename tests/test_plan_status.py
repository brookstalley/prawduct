"""``lib/plan_status.py`` — chunk status as a query (#1051, Chunk 01).

The subject is the one answer to "is chunk N done" and "is this plan finished",
derived from review / resolution / ``chunk-imported`` facts, ``dropped:``
frontmatter and (until migration) the plan's ticked boxes. Fixtures are real git
repos, because ``done`` needs the certifying review's commit to be reachable
from the plan's branch, and that is git's answer, not a field.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import evidence, plan_status  # noqa: E402

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
) -> Path:
    lines = [
        "---", "artifact: build-plan", "scope: unit", "branch: feature/unit", "base: main",
    ]
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

    def test_the_earliest_certifying_fact_is_the_one_cited(self, repo):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo, ("01",))
        facts = _facts(
            _review("R1", head, chunks=["01"], ts="2026-10-20T00:00:00Z"),
            _review("R2", head, chunks=["01"], ts="2026-10-24T00:00:00Z"),
        )
        state = plan_status.chunk_states(plan, facts, repo_dir=repo)["01"]
        assert (state.fact_id, state.date) == ("R1", "2026-10-20")


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
        "declaration",
        [
            "dropped:\n  - 02",               # no reason
            "dropped:\n  - '02:'",            # empty reason
            "dropped: [02]",                  # flow form: not the documented one
            "dropped:\n  - 02: ok\n  -",      # a bare dash poisons the whole block
            "dropped:\n  - {id: 02, reason: x}",  # mapping form: not the documented one
        ],
    )
    def test_an_unreadable_dropped_entry_leaves_the_chunk_open(self, repo, declaration):
        plan = _plan(repo, ("01", "02"), extra_frontmatter=declaration)
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
        assert states["02"].state == "open"
        assert not plan_status.is_finished(plan, _facts(), repo_dir=repo)

    def test_a_reasonless_entry_says_why_it_dropped_nothing(self, repo):
        plan = _plan(repo, ("01", "02"), extra_frontmatter="dropped:\n  - 02")
        assert "gives no reason" in plan_status.chunk_states(plan, _facts(), repo_dir=repo)["02"].reason

    def test_a_plan_with_no_chunks_is_finished(self, repo):
        plan = _plan(repo, ())
        assert plan_status.chunk_states(plan, _facts(), repo_dir=repo) == {}
        assert plan_status.is_finished(plan, _facts(), repo_dir=repo)
        assert plan_status.current_chunks(plan, _facts(), repo_dir=repo) == []

    def test_an_unreadable_plan_is_not_finished(self, repo):
        missing = repo / ".prawduct" / "artifacts" / "build-plan-gone.md"
        states = plan_status.chunk_states(missing, _facts(), repo_dir=repo)
        assert list(states) == [plan_status.UNREADABLE_PLAN]
        assert not plan_status.is_finished(missing, _facts(), repo_dir=repo)

    def test_an_unparseable_chunk_heading_is_an_open_chunk_not_an_absence(self, repo):
        """A plan whose only heading the parser rejects must not read as 'no chunks'."""
        plan = _plan(repo, (), body="#### Chunk 01: too deep\n")
        states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
        assert [s.state for s in states.values()] == ["open"]
        assert "unparseable-chunk-heading" in next(iter(states.values())).reason
        assert not plan_status.is_finished(plan, _facts(), repo_dir=repo)


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
    def test_whole_plan_modes_propose_every_open_chunk(self, repo, mode):
        head = _commit(repo, "src/c01.py", "x\n", "work")
        plan = _plan(repo)
        done01 = _facts(_review("R1", head, chunks=["01"]))
        assert plan_status.propose_chunks(plan, done01, [], mode, repo_dir=repo) == ["02", "03"]
        # repo_dir omitted: derived from the plan's `.prawduct/` ancestor.
        assert plan_status.propose_chunks(plan, done01, [], mode) == ["02", "03"]

    def test_another_mode_proposes_nothing(self, repo):
        plan = _plan(repo)
        assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], "verify-resolutions", repo_dir=repo) == []


class TestBuiltChunks:
    def test_a_subject_naming_the_chunk_or_a_diff_touching_its_deliverables(self, repo):
        plan = _plan(repo, ("01", "02", "03"))
        _commit(repo, "notes.txt", "x\n", "feat(unit): Chunk 02 — the second")
        _commit(repo, "src/c03.py", "x\n", "unlabelled work")
        assert plan_status.built_chunks(plan, repo) == {"02", "03"}

    def test_a_scoped_branch_ignores_a_foreign_plans_chunk_subject(self, repo):
        plan = _plan(repo, ("01", "02"))
        _commit(repo, "a.txt", "x\n", "feat(unit): scaffolding")
        _commit(repo, "b.txt", "x\n", "feat(other): land it (Chunk 01)")
        assert plan_status.built_chunks(plan, repo) == set()


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------


def test_every_build_plan_in_this_repo_reads_without_an_unreadable_or_unparsed_key():
    """The parser reads every real plan this repo has: none answers the
    unreadable sentinel or an unparsed-heading key, and the walk saw plans."""
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
        keys = list(plan_status.chunk_states(p, _facts(), repo_dir=repo_root))
        odd = [k for k in keys if k == plan_status.UNREADABLE_PLAN or k.startswith("?L")]
        if odd:
            bad[p.relative_to(repo_root).as_posix()] = odd
    assert not bad, bad
