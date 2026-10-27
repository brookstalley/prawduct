"""The chunk-state case table — one test per row (#1092).

The build plan of scope ``chunk-state-table`` lists, under "## Case table",
every situation :func:`plan_status.chunk_states` must answer, with the state it
must answer (the plan resolves by its scope wherever it is filed). Each test here is one row, named by its row id, so a row and its
test are found by the same id. Fixtures are real git repositories, because the
answer depends on git's: whether an anchor is in a branch's history, whether a
merge put it there through a first parent or a second, which commits a review's
span carries.

A row pins the STATE (and, where the row is about why, the reason). Where the
same behaviour has an older, more detailed test in ``test_plan_status.py``, this
row restates it at the level of the table rather than replacing it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import change_fragments, evidence, gitstate, plan_archive, plan_status  # noqa: E402

TS = "2026-10-27T10:00:00Z"
MODES = ("chunk", "final", "cumulative", "verify-resolutions")


# ---------------------------------------------------------------------------
# Fixtures: a repo on `feature/unit` off `main`, a three-chunk plan
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


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(repo, "add", rel)


def _commit(repo: Path, rel: str, text: str, subject: str) -> str:
    _write(repo, rel, text)
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


def _stage(repo: Path, rel: str, text: str) -> str:
    """Stage ``rel`` and return the index tree: the tree a dirty-tree review
    sees, which a later commit of the same index carries verbatim."""
    _write(repo, rel, text)
    return _git(repo, "write-tree")


def _tree(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


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
    deliverables: "dict[str, str] | None" = None,
    extra_frontmatter: str = "",
    claim: tuple[str, ...] = ("branch: feature/unit", "base: main"),
    status: "dict[str, bool] | None" = None,
) -> Path:
    lines = ["---", "artifact: build-plan", "scope: unit", *claim]
    if extra_frontmatter:
        lines.append(extra_frontmatter.rstrip("\n"))
    lines += ["---", "", "# Build Plan", ""]
    if status is not None:
        lines += ["## Status", ""]
        lines += [f"- [{'x' if done else ' '}] Chunk {c}: c{c}" for c, done in status.items()]
        lines.append("")
    lines += ["## Chunks", ""]
    for cid in chunks:
        lines += [f"### Chunk {cid}: c{cid}", ""]
        lines.append(f"- **Deliverables:** {(deliverables or {}).get(cid, f'`src/c{cid}.py`')}")
        lines.append("")
    path = repo / ".prawduct" / "artifacts" / "build-plan-unit.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def _envelope(kind: str, fact_id: str, body: dict) -> dict:
    return {"schema": 1, "kind": kind, "id": fact_id, "ts": TS, "actor": {}, "body": body}


def _review(
    repo: Path,
    fact_id: str,
    *,
    base: "str | None",
    head: "str | None" = None,
    dispatch: "str | None" = None,
    head_tree: "str | None" = None,
    chunks: "list[str] | None" = None,
    mode: str = "cumulative",
    blocking: "tuple[str, ...]" = (),
    scope: str = "unit",
    reviewed_all: bool = True,
    base_tree: "str | None" = None,
) -> dict:
    """A review fact shaped as ``critic-consolidate`` writes one: the tree
    interval ``base_tree → head_tree`` with its commits, the files that changed
    over it and the files reviewed. ``head`` omitted is a dirty-tree review:
    ``head_commit`` null, anchored at ``dispatch``, its ``head_tree`` given.
    ``chunks`` omitted names no chunk (``chunks: []``, ``chunk: null``)."""
    base_tree = base_tree or (_tree(repo, base) if base else None)
    head_tree = head_tree or _tree(repo, head)
    changed = _git(repo, "diff", "--name-only", base_tree, head_tree).splitlines() if base_tree else []
    named = list(chunks or [])
    body = {
        "scope": scope,
        "mode": mode,
        # A commit id, as the writer records it — never the ref it was named by.
        "base_commit": _git(repo, "rev-parse", base) if base else None,
        "base_tree": base_tree,
        "head_commit": head,
        "head_tree": head_tree,
        "dispatch_commit": dispatch or head,
        "files_changed": changed,
        "files_reviewed": changed if reviewed_all else [],
        "chunks": named,
        "chunk": named[0] if named else None,
        "findings": [
            {"fid": fid, "severity": "blocking", "goal": "g", "title": f"t {fid}"}
            for fid in blocking
        ],
        "counts": {"blocking": len(blocking), "warning": 0, "note": 0},
    }
    return _envelope("review", fact_id, body)


def _resolution(fact_id: str, review_id: str, fid: str) -> dict:
    return _envelope(
        "resolution", fact_id,
        {"finding": {"review_id": review_id, "fid": fid}, "disposition": "fixed"},
    )


def _retracted(fact_id: str, chunk: str, certified_by: str) -> dict:
    return _envelope(
        plan_status.RETRACTED_KIND, fact_id,
        {"scope": "unit", "chunk": chunk, "fact_id": certified_by, "reason": "wrong",
         "retracted_at": TS},
    )


def _facts(*envelopes: dict) -> dict:
    return {"status": "ok", "facts": list(envelopes)}


def _states(plan: Path, facts: dict, repo: Path) -> dict[str, str]:
    return {k: s.state for k, s in plan_status.chunk_states(plan, facts, repo_dir=repo).items()}


def _merge_no_ff(repo: Path, delete: bool = True) -> None:
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature/unit", "feature/unit")
    if delete:
        _git(repo, "branch", "-D", "feature/unit")


def _plan_commit(repo: Path) -> str:
    """The branch's plan commit — the HEAD a first dirty-tree review sits on."""
    return _commit(repo, "notes/plan.txt", "plan\n", "plan(unit): the plan")


def _dirty_review_then_commit(repo: Path, rel: str, subject: str, **kw) -> "tuple[dict, str]":
    """#1079's shape: a review of uncommitted work at the branch HEAD (its
    ``base_commit`` IS that HEAD), then the reviewed tree committed verbatim."""
    at = _git(repo, "rev-parse", "HEAD")
    tree = _stage(repo, rel, "x\n")
    fact = _review(repo, kw.pop("fact_id", "R1"), base=at, dispatch=at, head_tree=tree, **kw)
    _git(repo, "commit", "-qm", subject)
    assert _tree(repo, "HEAD") == tree
    return fact, _git(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# A — anchor placement, branch present
# ---------------------------------------------------------------------------


def test_A1_anchor_on_the_plans_branch_is_done(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    assert _states(plan, _facts(_review(repo, "R1", base="main", head=head, chunks=["01"])), repo) == {
        "01": "done", "02": "open", "03": "open",
    }


def test_A2_anchor_on_no_claimed_branch_is_open(repo):
    _git(repo, "checkout", "-q", "-b", "side", "main")
    stray = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _git(repo, "checkout", "-q", "feature/unit")
    plan = _plan(repo)
    state = plan_status.chunk_states(
        plan, _facts(_review(repo, "R1", base="main", head=stray, chunks=["01"])), repo_dir=repo
    )["01"]
    assert state.state == "open"
    assert "not on `feature/unit`" in state.reason


def test_A3_anchor_on_a_declared_working_branch_is_done(repo):
    _git(repo, "checkout", "-q", "-b", "feature/unit-delegate")
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _git(repo, "checkout", "-q", "feature/unit")
    plan = _plan(repo, extra_frontmatter="working-branches:\n  - feature/unit-delegate")
    fact = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    assert _states(plan, fact, repo)["01"] == "done"


def test_A4_branch_only_on_a_remote_is_probed_by_its_tracking_ref(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _git(repo, "update-ref", "refs/remotes/origin/feature/unit", head)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "feature/unit")
    plan = _plan(repo)
    fact = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    assert _states(plan, fact, repo)["01"] == "done"


def test_A5_git_unable_to_list_branches_takes_no_fallback(repo, monkeypatch):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _merge_no_ff(repo)
    plan = _plan(repo)
    fact = _facts(_review(repo, "R1", base="main~1", head=head, chunks=["01"]))
    monkeypatch.setattr(gitstate, "branch_refs", lambda _repo, _branches: None)
    assert _states(plan, fact, repo)["01"] == "open"


def test_A6_a_plan_declaring_no_branch_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo, claim=())
    state = plan_status.chunk_states(
        plan, _facts(_review(repo, "R1", base="main", head=head, chunks=["01"])), repo_dir=repo
    )["01"]
    assert state.state == "open"
    assert "declares no `branch:`" in state.reason


def test_A7_a_fact_recording_no_commit_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"])
    fact["body"]["head_commit"] = fact["body"]["dispatch_commit"] = None
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "records no commit" in state.reason


def test_A8_a_dirty_tree_review_anchors_at_its_dispatch_commit(repo):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    assert _states(plan, _facts(fact), repo)["01"] == "done"


# ---------------------------------------------------------------------------
# M — after the merge: branch deleted or kept, merge commit / fast-forward / squash
# ---------------------------------------------------------------------------


def test_M1_no_ff_merge_branch_deleted_committed_review_is_done(repo):
    """#1065."""
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    _merge_no_ff(repo)
    assert _states(plan, fact, repo)["01"] == "done"


def test_M2_no_ff_merge_branch_deleted_dirty_review_at_branch_head_is_done(repo):
    """#1079: the anchor equals the review's ``base_commit`` and reaches the
    base only through the merge's second parent, so it was not on the base
    when the review ran."""
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    _merge_no_ff(repo)
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert (state.state, state.fact_id) == ("done", "R1"), state.reason


def test_M3_no_ff_merge_branch_kept_dirty_review_at_branch_head_is_done(repo):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    _merge_no_ff(repo, delete=False)
    assert _states(plan, _facts(fact), repo)["01"] == "done"


def test_M4_fast_forward_merge_branch_deleted_committed_review_is_done(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "feature/unit")
    _git(repo, "branch", "-D", "feature/unit")
    assert _states(plan, fact, repo)["01"] == "done"


def test_M5_fast_forward_merge_dirty_review_at_branch_head_fails_closed(repo):
    """A fast-forward puts the branch's commits on the base's first-parent
    history, where an anchor that is its review's own ``base_commit`` cannot be
    told from a fork point the base already held. Open, with the reason."""
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "feature/unit")
    _git(repo, "branch", "-D", "feature/unit")
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "review's own base commit" in state.reason


def test_M6_squash_merge_branch_deleted_is_open(repo):
    """A squash puts new commits on the base; the reviewed anchor is on no ref."""
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--squash", "feature/unit")
    _git(repo, "commit", "-qm", "squashed")
    _git(repo, "branch", "-D", "feature/unit")
    state = plan_status.chunk_states(plan, fact, repo_dir=repo)["01"]
    assert state.state == "open"
    assert "not on `main`" in state.reason


def test_M7_branch_deleted_unmerged_is_open(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "feature/unit")
    plan = _plan(repo)
    state = plan_status.chunk_states(
        plan, _facts(_review(repo, "R1", base="main", head=head, chunks=["01"])), repo_dir=repo
    )["01"]
    assert state.state == "open"
    assert "`feature/unit` is on no local or remote branch" in state.reason


def test_M8_fork_point_anchor_branch_deleted_is_open(repo):
    fork = _git(repo, "rev-parse", "HEAD")
    tree = _stage(repo, "src/c01.py", "x\n")
    _git(repo, "reset", "-q")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "feature/unit")
    plan = _plan(repo)
    fact = _review(repo, "R1", base=fork, dispatch=fork, head_tree=tree, chunks=["01"])
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "review's own base commit" in state.reason
    # The base moving on past the fork point leaves it on the first-parent history.
    _commit(repo, "other.txt", "x\n", "unrelated work on main")
    assert plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"].state == "open"


def test_M9_gone_branch_with_an_unresolvable_base_is_open(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "feature/unit")
    plan = _plan(repo, claim=("branch: feature/unit", "base: nowhere"))
    state = plan_status.chunk_states(
        plan, _facts(_review(repo, "R1", base="main", head=head, chunks=["01"])), repo_dir=repo
    )["01"]
    assert state.state == "open"
    assert "names no ref" in state.reason


# ---------------------------------------------------------------------------
# C — named vs span coverage
# ---------------------------------------------------------------------------


def test_C1_a_fact_naming_the_chunk_certifies_it_and_not_the_others(repo):
    c1 = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    _commit(repo, "src/c02.py", "x\n", "feat(unit): two (Chunk 02)")
    plan = _plan(repo)
    # c1's review names 01 and its span stops at c1, so 02 stays open.
    fact = _review(repo, "R1", base="main", head=c1, chunks=["01"], mode="chunk")
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open", "03": "open"}


def test_C2_an_unnamed_span_certifies_a_chunk_its_subject_carries(repo):
    _commit(repo, "notes/a.txt", "a\n", "feat(unit): one (Chunk 01)")
    head = _commit(repo, "notes/b.txt", "b\n", "feat(unit): two (Chunk 02)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    states = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)
    assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "done", "03": "open"}
    assert states["01"].fact_id == "R1"


def test_C3_an_unnamed_span_certifies_a_chunk_whose_deliverables_it_touches(repo):
    head = _commit(repo, "src/c02.py", "x\n", "feat(unit): the second part")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "open", "02": "done", "03": "open"}


def test_C4_a_fact_naming_one_chunk_certifies_another_its_span_carries(repo):
    _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    head = _commit(repo, "src/c02.py", "x\n", "feat(unit): two (Chunk 02)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"])
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "done", "03": "open"}


def test_C5_a_span_with_no_commit_for_the_chunk_leaves_it_open(repo):
    """#1072's invariant: no commit in the span builds the unbuilt chunks."""
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, mode="final")
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open", "03": "open"}


def test_C6_a_deliverable_touched_before_the_span_is_not_carried_by_it(repo):
    early = _commit(repo, "src/c03.py", "stub\n", "feat(unit): one (Chunk 01)")
    head = _commit(repo, "src/c01.py", "x\n", "fix(unit): one again")
    plan = _plan(repo)
    fact = _review(repo, "R1", base=early, head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open", "03": "open"}


def test_C7_a_chunk_only_an_unscoped_subject_carries_is_not_certified_by_a_span(repo):
    """The proposal's certifying rule: another plan's ``Chunk N`` on the branch
    must not certify this plan's."""
    head = _commit(repo, "notes/a.txt", "a\n", "feat(other): theirs (Chunk 02)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "open", "02": "open", "03": "open"}


def test_C8_an_under_reviewed_span_is_no_edge_and_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, reviewed_all=False)
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_C9_another_scopes_span_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, scope="other")
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_C10_a_dirty_tree_span_committed_verbatim_certifies_the_commit(repo):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "notes/one.txt", "feat(unit): one (Chunk 01)", mode="chunk"
    )
    assert _states(plan, _facts(fact), repo)["01"] == "done"


def test_C11_a_dirty_tree_span_edited_before_commit_certifies_nothing_uncommitted(repo):
    at = _plan_commit(repo)
    plan = _plan(repo)
    tree = _stage(repo, "notes/one.txt", "x\n")
    fact = _review(repo, "R1", base=at, dispatch=at, head_tree=tree, mode="chunk")
    _write(repo, "notes/one.txt", "edited after the review\n")
    _git(repo, "commit", "-qm", "feat(unit): one (Chunk 01)")
    assert _tree(repo, "HEAD") != tree
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_C12_a_span_whose_base_commit_is_unrecorded_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    fact["body"]["base_commit"] = None
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def _issue_1082(repo: Path) -> "tuple[Path, dict]":
    """#1082 steps 1-7: chunks 01 and 02 committed and covered by a cumulative
    naming them; chunk 03 built in the working tree, a verify-resolutions pass
    over it naming no chunk comes back clean, and the tree is committed
    verbatim with a ``(Chunk 03)`` subject."""
    plan = _plan(repo, extra_frontmatter="Type: cumulative-final")
    _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    c2 = _commit(repo, "src/c02.py", "x\n", "feat(unit): two (Chunk 02)")
    cumulative = _review(repo, "R1", base="main", head=c2, chunks=["01", "02"])
    tree = _stage(repo, "src/c03.py", "x\n")
    verify = _review(
        repo, "V1", base=c2, dispatch=c2, head_tree=tree, mode="verify-resolutions"
    )
    _git(repo, "commit", "-qm", "feat(unit): three (Chunk 03)")
    assert _tree(repo, "HEAD") == tree
    return plan, _facts(cumulative, verify)


def test_C13_issue_1082_repro_reads_chunk_03_done(repo):
    plan, facts = _issue_1082(repo)
    states = plan_status.chunk_states(plan, facts, repo_dir=repo)
    assert {k: s.state for k, s in states.items()} == {"01": "done", "02": "done", "03": "done"}
    assert states["03"].fact_id == "V1"
    assert plan_status.is_finished(plan, facts, repo_dir=repo)


def test_C14_issue_1082_after_merge_archives_with_no_unbuilt_chunk(repo):
    plan, facts = _issue_1082(repo)
    _merge_no_ff(repo)
    assert _states(plan, facts, repo) == {"01": "done", "02": "done", "03": "done"}
    assert plan_archive.unbuilt_at_archive(plan, repo_dir=repo, facts=facts) is None


# ---------------------------------------------------------------------------
# K — mode labels do not matter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_K1_a_named_fact_certifies_in_every_mode(repo, mode):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"], mode=mode)
    assert _states(plan, _facts(fact), repo)["01"] == "done"


@pytest.mark.parametrize("mode", MODES)
def test_K2_an_unnamed_span_certifies_in_every_mode(repo, mode):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, mode=mode)
    assert _states(plan, _facts(fact), repo)["01"] == "done"


# ---------------------------------------------------------------------------
# S — a Deliverables path several chunks list attributes a commit to none
# ---------------------------------------------------------------------------

SHARED = {"01": "`src/c01.py`; `src/shared.py`", "02": "`src/shared.py`; `src/c02.py`"}


def test_S1_a_shared_path_certifies_neither_chunk_by_a_span(repo):
    """Chunk 01's commit touches its own file and the file both chunks list;
    the span certifies 01 by its own file, and 02, unbuilt, by nothing."""
    _write(repo, "src/c01.py", "x\n")
    head = _commit(repo, "src/shared.py", "x\n", "feat(unit): the first part")
    plan = _plan(repo, ("01", "02"), deliverables=SHARED)
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open"}


def test_S2_a_scoped_subject_certifies_the_chunk_a_shared_path_cannot(repo):
    head = _commit(repo, "src/shared.py", "x\n", "feat(unit): two (Chunk 02)")
    plan = _plan(repo, ("01", "02"), deliverables=SHARED)
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "open", "02": "done"}


def test_S3_a_path_one_chunk_owns_still_certifies_it(repo):
    """The control, with a directory: chunk 01 lists `lib/pkg/`, chunk 02 lists
    one file under it. A file only 01's directory covers certifies 01; the
    file both cover certifies neither."""
    _write(repo, "lib/pkg/a.py", "x\n")
    head = _commit(repo, "lib/pkg/b.py", "x\n", "feat(unit): package work")
    plan = _plan(repo, ("01", "02"), deliverables={"01": "`lib/pkg/`", "02": "`lib/pkg/b.py`"})
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open"}


def test_S4_the_proposal_names_no_chunk_by_a_shared_path_and_says_so(repo):
    _commit(repo, "src/shared.py", "x\n", "feat(unit): shared groundwork")
    plan = _plan(repo, ("01", "02"), deliverables=SHARED)
    proposal = plan_status.chunk_proposal(
        plan, _facts(), ["src/shared.py"], "chunk", repo_dir=repo
    )
    assert proposal.chunks == []
    assert any("`src/shared.py`" in n and "01, 02" in n for n in proposal.notes), proposal.notes
    # Control: a path one chunk owns is proposed.
    assert plan_status.propose_chunks(plan, _facts(), ["src/c01.py"], "chunk", repo_dir=repo) == ["01"]


def test_S5_the_built_tag_still_reads_a_shared_path_as_both_chunks_work(repo):
    """The tag certifies nothing and only arms a gate early, so it keeps the
    looser rule: work on a path two chunks list tags both."""
    _commit(repo, "src/shared.py", "x\n", "feat(unit): shared groundwork")
    plan = _plan(repo, ("01", "02"), deliverables=SHARED)
    assert plan_status.built_report(plan, repo).built == {"01", "02"}


# ---------------------------------------------------------------------------
# P — the proposal at dispatch, then the fact it certifies
# ---------------------------------------------------------------------------


def _proposed_fact(repo, plan, facts, fid, *, mode, base, head, diff):
    chunks = plan_status.propose_chunks(
        plan, facts, diff, mode, repo_dir=repo, since=_git(repo, "rev-parse", base),
    )
    return _review(repo, fid, base=base, head=head, chunks=chunks, mode=mode), chunks


def test_P1_a_mid_plan_final_names_only_built_chunks(repo):
    """#1072."""
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact, named = _proposed_fact(
        repo, plan, _facts(), "R1", mode="final", base="main", head=head, diff=["src/c01.py"]
    )
    assert named == ["01"]
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open", "03": "open"}


def test_P2_a_boundary_cumulative_names_every_built_chunk(repo):
    _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    head = _commit(repo, "notes/b.txt", "b\n", "feat(unit): two (Chunk 02)")
    plan = _plan(repo)
    base = _git(repo, "merge-base", "main", "HEAD")
    fact, named = _proposed_fact(
        repo, plan, _facts(), "R1", mode="cumulative", base=base, head=head,
        diff=["src/c01.py", "notes/b.txt"],
    )
    assert named == ["01", "02"]
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "done", "03": "open"}


def test_P3_a_chunk_review_proposes_by_its_diff(repo):
    c1 = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact, named = _proposed_fact(
        repo, plan, _facts(), "R1", mode="chunk", base="main", head=c1, diff=["src/c01.py"]
    )
    assert named == ["01"]
    assert _states(plan, _facts(fact), repo)["01"] == "done"


def test_P4_the_plan_new_stub_is_not_the_change_record_chunks_work(repo):
    """#1075."""
    fragment = ".prawduct/changes/unit.md"
    stub = change_fragments.render_fragment(
        kind="fix", scope="unit", date="2026-10-26", title="The unit",
        narrative="", consumer_note="",
    )
    assert change_fragments.is_unwritten_stub(stub)
    _commit(repo, fragment, stub, "docs(unit): build plan")
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo, ("01", "02"), deliverables={"02": f"`{fragment}`"})
    fact, named = _proposed_fact(
        repo, plan, _facts(), "R1", mode="cumulative", base="main", head=head,
        diff=[fragment, "src/c01.py"],
    )
    assert named == ["01"]
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "open"}
    # The same interval reviewed naming nothing: the span reads the stub as no work too.
    unnamed = _review(repo, "R2", base="main", head=head)
    assert _states(plan, _facts(unnamed), repo) == {"01": "done", "02": "open"}


def test_P5_bare_deliverables_and_plain_prefix_subjects_are_found(repo):
    """#1081."""
    _commit(repo, "lib/one.py", "x\n", "unit chunk 01: the first part")
    head = _commit(repo, "lib/two.py", "x\n", "unit chunk 02: the second part")
    plan = _plan(repo, ("01", "02"), deliverables={"01": "`one.py`", "02": "`two.py`"})
    base = _git(repo, "merge-base", "main", "HEAD")
    fact, named = _proposed_fact(
        repo, plan, _facts(), "R1", mode="cumulative", base=base, head=head,
        diff=["lib/one.py", "lib/two.py"],
    )
    assert named == ["01", "02"]
    assert _states(plan, _facts(fact), repo) == {"01": "done", "02": "done"}


# ---------------------------------------------------------------------------
# B — blocking findings
# ---------------------------------------------------------------------------


def test_B1_an_unresolved_blocking_finding_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"], blocking=("R-1",))
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "R-1 not resolved" in state.reason


def test_B2_a_resolved_blocking_finding_certifies(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"], blocking=("R-1",))
    assert _states(plan, _facts(fact, _resolution("V1", "R1", "R-1")), repo)["01"] == "done"


def test_B3_a_blocking_count_with_no_finding_id_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01"])
    fact["body"]["findings"] = [{"severity": "blocking", "title": "no fid"}]
    fact["body"]["counts"]["blocking"] = 1
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_B4_an_unnamed_span_with_an_unresolved_blocker_certifies_nothing(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, blocking=("R-1",))
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_B5_an_unnamed_span_whose_blocker_is_resolved_certifies(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, blocking=("R-1",))
    assert _states(plan, _facts(fact, _resolution("V1", "R1", "R-1")), repo)["01"] == "done"


# ---------------------------------------------------------------------------
# X — retraction
# ---------------------------------------------------------------------------


def test_X1_a_retraction_reopens_only_its_pair(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head, chunks=["01", "02"])
    facts = _facts(fact, _retracted("T1", "01", "R1"))
    states = plan_status.chunk_states(plan, facts, repo_dir=repo)
    assert {k: s.state for k, s in states.items()} == {"01": "open", "02": "done", "03": "open"}
    assert "retracted" in states["01"].reason


def test_X2_a_later_fact_naming_a_retracted_chunk_certifies_it_again(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    first = _review(repo, "R1", base="main", head=head, chunks=["01"])
    again = _review(repo, "R2", base="main", head=head, chunks=["01"])
    state = plan_status.chunk_states(
        plan, _facts(first, _retracted("T1", "01", "R1"), again), repo_dir=repo
    )["01"]
    assert (state.state, state.fact_id) == ("done", "R2")


def test_X3_a_span_certification_can_be_retracted(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    assert plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"].fact_id == "R1"
    target = plan_status.retraction_target(plan, _facts(fact), "01", repo_dir=repo)
    assert (target.status, target.fact_id) == ("ok", "R1")
    state = plan_status.chunk_states(
        plan, _facts(fact, _retracted("T1", "01", "R1")), repo_dir=repo
    )["01"]
    assert state.state == "open"
    assert "retracted" in state.reason


# ---------------------------------------------------------------------------
# D / I — dropped declarations and imports
# ---------------------------------------------------------------------------


def test_D1_a_dropped_chunk_with_a_reason_finishes_the_plan(repo):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo, ("01", "02"), extra_frontmatter="dropped:\n  - 02: cut")
    facts = _facts(_review(repo, "R1", base="main", head=head, chunks=["01"]))
    assert _states(plan, facts, repo) == {"01": "done", "02": "dropped"}
    assert plan_status.is_finished(plan, facts, repo_dir=repo)


def test_D2_a_dropped_entry_with_no_reason_drops_nothing(repo):
    plan = _plan(repo, ("01",), extra_frontmatter="dropped:\n  - 01:")
    state = plan_status.chunk_states(plan, _facts(), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "gives no reason" in state.reason


def test_I1_a_ticked_box_is_done_imported(repo):
    plan = _plan(repo, ("01", "02"), status={"01": True, "02": False})
    states = plan_status.chunk_states(plan, _facts(), repo_dir=repo)
    assert (states["01"].state, states["01"].imported) == ("done", True)
    assert states["02"].state == "open"


def test_I2_a_chunk_imported_fact_is_done_imported(repo):
    plan = _plan(repo, ("01",))
    imported = _envelope(
        plan_status.IMPORTED_KIND, "I1",
        {"scope": "unit", "chunk": "01", "source": "status-box", "imported_at": TS},
    )
    state = plan_status.chunk_states(plan, _facts(imported), repo_dir=repo)["01"]
    assert (state.state, state.fact_id, state.imported) == ("done", "I1", True)


# ---------------------------------------------------------------------------
# F — git failing on an authority path certifies nothing
# ---------------------------------------------------------------------------


def _git_fails(monkeypatch, when):
    """Make every ``evidence.run_git`` call whose argv ``when`` matches fail."""
    real = evidence.run_git

    def run_git(repo_dir, *args, **kw):
        if when(args):
            return 128, "", "fatal: injected failure"
        return real(repo_dir, *args, **kw)

    monkeypatch.setattr(evidence, "run_git", run_git)


def test_F1_first_parent_rev_list_failing_refuses_the_anchor(repo, monkeypatch):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    _merge_no_ff(repo)
    assert _states(plan, _facts(fact), repo)["01"] == "done"  # control: M2
    _git_fails(monkeypatch, lambda a: a[:1] == ("rev-list",))
    state = plan_status.chunk_states(plan, _facts(fact), repo_dir=repo)["01"]
    assert state.state == "open"
    assert "first-parent history" in state.reason


def test_F2_a_span_log_failing_certifies_nothing(repo, monkeypatch):
    head = _commit(repo, "src/c01.py", "x\n", "feat(unit): one (Chunk 01)")
    plan = _plan(repo)
    fact = _review(repo, "R1", base="main", head=head)
    assert _states(plan, _facts(fact), repo)["01"] == "done"  # control: C2
    _git_fails(monkeypatch, lambda a: a[:1] == ("log",))
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_F3_a_dirty_tree_spans_descendant_log_failing_certifies_nothing(repo, monkeypatch):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "notes/one.txt", "feat(unit): one (Chunk 01)", mode="chunk"
    )
    assert _states(plan, _facts(fact), repo)["01"] == "done"  # control: C10
    _git_fails(monkeypatch, lambda a: a[:1] == ("log",) and "--ancestry-path" in a)
    assert _states(plan, _facts(fact), repo)["01"] == "open"


def test_F4_a_dirty_tree_span_with_no_holding_ref_certifies_nothing(repo, monkeypatch):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "notes/one.txt", "feat(unit): one (Chunk 01)", mode="chunk"
    )
    assert _states(plan, _facts(fact), repo)["01"] == "done"  # control: C10
    monkeypatch.setattr(plan_status._Reachability, "holder", lambda self, anchor: None)
    assert _states(plan, _facts(fact), repo)["01"] == "open"


# ---------------------------------------------------------------------------
# G — the git calls a span and the first-parent rule add (NF1)
# ---------------------------------------------------------------------------


def _record_git(monkeypatch) -> "list[tuple[str, ...]]":
    calls: list[tuple[str, ...]] = []
    real = evidence.run_git

    def run_git(repo_dir, *args, **kw):
        calls.append(args)
        return real(repo_dir, *args, **kw)

    monkeypatch.setattr(evidence, "run_git", run_git)
    return calls


def test_G1_a_dirty_tree_span_costs_its_two_interval_logs(repo, monkeypatch):
    base = _plan_commit(repo)
    at = _commit(repo, "notes/zero.txt", "z\n", "chore(unit): groundwork")
    plan = _plan(repo)
    tree = _stage(repo, "notes/one.txt", "x\n")
    fact = _review(repo, "R1", base=base, dispatch=at, head_tree=tree, mode="chunk")
    _git(repo, "commit", "-qm", "feat(unit): one (Chunk 01)")
    calls = _record_git(monkeypatch)
    # Two facts over one interval: the second costs nothing more.
    assert _states(plan, _facts(fact, {**fact, "id": "R2"}), repo)["01"] == "done"
    assert [c[0] for c in calls] == ["merge-base", "log", "log"]
    assert [c[3:-1] for c in calls[1:]] == [
        (f"{base}..{at}",), ("--ancestry-path", f"{at}..feature/unit"),
    ]


def test_G2_the_first_parent_rule_costs_one_rev_list_per_anchor(repo, monkeypatch):
    _plan_commit(repo)
    plan = _plan(repo)
    fact, _c1 = _dirty_review_then_commit(
        repo, "src/c01.py", "feat(unit): one (Chunk 01)", chunks=["01"], mode="chunk"
    )
    _merge_no_ff(repo)
    anchor = fact["body"]["dispatch_commit"]
    calls = _record_git(monkeypatch)
    assert _states(plan, _facts(fact, {**fact, "id": "R2"}), repo)["01"] == "done"
    assert [c for c in calls if c[0] == "rev-list"] == [
        ("rev-list", "--first-parent", "--parents", f"{anchor}..main"),
    ]
