"""#594 chunk 02 — evidence facts recorded from a disposable worktree.

A `/prawduct:critic` run inside an `isolation: "worktree"` agent worktree spends
full review unit-cost on a fact whose tree no branch will ever carry. Tree-keying
already makes such a fact cover nothing, so the gates compose correctly — what it
also did was read in `evidence status` exactly like a review that covers the
branch. That is the false reassurance these tests pin.

Two invariants are load-bearing and asserted directly rather than assumed:
provenance is derived on READ (no schema version moves, so facts already in the
store classify retroactively), and NO fact is filtered out of anything — the
coverage algebra must see exactly what it saw before, because suppressing a fact
would *change* gate behaviour rather than describe it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(ROOT))
from lib import evidence  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        cwd=str(repo), capture_output=True, text=True, check=True, timeout=10,
    )


def _make_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _seed_store(repo: Path, facts: list[dict]) -> None:
    """Write envelopes straight into the store.

    `append_fact` derives `actor.worktree` from the project dir it is called
    with, so seeding a fact that *claims* an ephemeral origin means writing the
    JSONL — which is also exactly the shape a real agent worktree would have
    appended into this same clone-shared store.
    """
    path = evidence.store_path(repo)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(f) + "\n" for f in facts))


def _fact(
    worktree: str,
    fid: str = "rev-x",
    kind: str = "review",
    tree: str = "abc123def456",
) -> dict:
    # `tree` is a parameter, not a constant, because a shared hardcoded tree
    # made the coverage-algebra test below hold by construction — it passed
    # identically whether or not ephemeral facts reached `distinct_trees`,
    # which is the one thing it exists to detect.
    return {
        "schema": 1,
        "kind": kind,
        "id": fid,
        "ts": "2026-08-05T00:00:00Z",
        "actor": {"session": 1, "worktree": worktree, "plugin": "3.2.4"},
        "body": {"head_tree": tree},
    }


AGENT_WT = "/repo/.claude/worktrees/agent-a287823214767feaa"
WORKFLOW_WT = "/repo/.claude/worktrees/wf_abc123"
ENTERED_WT = "/repo/.claude/worktrees/my-feature"


class TestClassification:
    def test_agent_and_workflow_worktrees_are_ephemeral(self):
        facts = [_fact(AGENT_WT, "rev-a"), _fact(WORKFLOW_WT, "rev-b")]
        assert {f["id"] for f in evidence.ephemeral_facts(facts)} == {"rev-a", "rev-b"}

    def test_normal_and_entered_worktrees_are_not(self):
        """An `EnterWorktree` session worktree lives under the same parent and is
        a real checkout whose reviews really do cover its branch. Mislabelling
        one would tell a truthful review it vouched for nothing."""
        facts = [_fact("/repo"), _fact("/repo/../wt-feature"), _fact(ENTERED_WT)]
        assert evidence.ephemeral_facts(facts) == []

    def test_opaque_envelope_does_not_crash_the_reader(self):
        """Store convention: a reader never crashes on a record it doesn't
        understand."""
        facts = [
            {"schema": 1, "kind": "review", "id": "r1", "actor": "not-a-dict"},
            {"schema": 1, "kind": "review", "id": "r2"},
            {"schema": 1, "kind": "review", "id": "r3", "actor": {"worktree": None}},
        ]
        assert evidence.ephemeral_facts(facts) == []


class TestNoFactIsSuppressed:
    def test_classification_does_not_remove_facts_from_the_list(self):
        """The gates compose over facts, not over this view. Filtering an
        ephemeral fact out would CHANGE gate behaviour rather than describe it —
        tree-keying already makes it cover nothing."""
        facts = [_fact(AGENT_WT, "rev-a"), _fact("/repo", "rev-b")]
        before = list(facts)

        evidence.ephemeral_facts(facts)

        assert facts == before

    def test_ephemeral_facts_still_reach_the_coverage_algebra(self):
        """The "no gate verdict changes" claim, stated so it can actually fail.

        The invariant is *the ephemeral fact still contributes its tree*, not
        *the two sets happen to match* — an earlier version asserted the latter
        with both facts sharing a hardcoded tree, so it held by construction and
        would have passed even if ephemeral facts were dropped from the algebra,
        which is precisely the regression it guards.
        """
        ephemeral_tree = "eeee1111eeee"
        normal_tree = "nnnn2222nnnn"
        mixed = [
            _fact(AGENT_WT, "rev-a", tree=ephemeral_tree),
            _fact("/repo", "rev-b", tree=normal_tree),
        ]

        trees = evidence.distinct_trees(mixed)

        assert ephemeral_tree in trees, (
            "an ephemeral fact must still reach the coverage algebra — "
            "tree-keying is what makes it cover nothing, not suppression"
        )
        assert normal_tree in trees


class TestCliSurfaces:
    """The chunk's acceptance criteria are stated at the CLI, so they are
    asserted at the CLI. Classifying correctly in `ephemeral_facts` proves
    nothing about what `evidence status` actually prints."""

    def test_status_reports_the_ephemeral_count_and_says_it_covers_nothing(
        self, tmp_path, capsys
    ):
        repo = _make_repo(tmp_path)
        _seed_store(repo, [
            _fact(AGENT_WT, "rev-a", tree="eeee1111eeee"),
            _fact(str(repo), "rev-b", tree="nnnn2222nnnn"),
        ])

        assert evidence._cmd_status(repo) == 0
        out = capsys.readouterr().out

        assert "from ephemeral worktrees: 1" in out
        assert "COVER NO BRANCH" in out

    def test_status_is_silent_when_no_fact_is_ephemeral(self, tmp_path, capsys):
        """A line that always prints is not a signal."""
        repo = _make_repo(tmp_path)
        _seed_store(repo, [_fact(str(repo), "rev-b")])

        assert evidence._cmd_status(repo) == 0

        assert "ephemeral" not in capsys.readouterr().out

    def test_list_marks_exactly_the_ephemeral_fact(self, tmp_path, capsys):
        repo = _make_repo(tmp_path)
        _seed_store(repo, [
            _fact(AGENT_WT, "rev-ephemeral", tree="eeee1111eeee"),
            _fact(str(repo), "rev-normal", tree="nnnn2222nnnn"),
        ])

        assert evidence._cmd_list(repo, []) == 0
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

        marked = [ln for ln in lines if "[ephemeral" in ln]
        assert len(marked) == 1, lines
        assert "rev-ephemeral" in marked[0]
        # And the normal fact is still listed, unmarked — nothing is filtered.
        assert any("rev-normal" in ln and "[ephemeral" not in ln for ln in lines)


class TestSchemaUnchanged:
    def test_provenance_is_derived_not_stored(self):
        """No new field, so no schema version moves and every fact already in the
        store classifies retroactively — the whole reason this is a read-side
        classification instead of a write-side tag."""
        fact = _fact(AGENT_WT)
        assert evidence.ephemeral_facts([fact])

        assert fact["schema"] == evidence.SCHEMA_VERSION
        assert set(fact["actor"]) == {"session", "worktree", "plugin"}
        assert "ephemeral" not in fact and "provenance" not in fact
