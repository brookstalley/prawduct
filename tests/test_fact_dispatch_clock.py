"""The review FACT carries the dispatch clock, so every worktree's rounds are countable.

The owner's ruling on #882 (option 1): the dispatch interval rides the review
fact body in the clone-shared evidence store, not only the per-worktree ledger.
A tally joining facts to the ledger at read time sees only its own worktree's
rounds and undercounts delegated or parallel work.

What these tests pin:

- **The order.** `critic-consolidate` mints the fact BEFORE its ledger append
  consumes the mark, so the fact reads the mark with a non-consuming `peek`
  and the ledger still gets it. Both records carry the same stamp.
- **Absent means not measured.** No mark, a stale mark, or a mark for another
  tree writes NO key — never a null or a zero naming the absence.
- **One reader for the interval.** `review_dispatch.fact_interval_seconds` ends
  the interval at the fact's envelope `ts` and carries the plausibility bound.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "plugin"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import critic_consolidate, evidence, review_dispatch  # noqa: E402
from test_critic_dispatch_refusal import (  # noqa: E402
    _commit_file,
    _git,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)

CRITIC_MARKER_REL = ".prawduct/.critic-review-dispatch.json"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"


def _mark(prawduct_dir: Path, head: "str | None", stamp: str = "2026-09-25T12:00:00Z") -> Path:
    prawduct_dir.mkdir(parents=True, exist_ok=True)
    path = prawduct_dir / ".critic-review-dispatch.json"
    path.write_text(json.dumps({"dispatched_at": stamp, "head": head}) + "\n")
    return path


class TestPeekLeavesTheMarkForTheLedger:
    """`peek` is `consume`'s judgement without its side effect."""

    def test_peek_reads_the_stamp_and_clears_nothing(self, tmp_path):
        path = _mark(tmp_path, "abc123")
        stamp, reason = review_dispatch.peek(tmp_path, "review.critic", "abc123")
        assert stamp == "2026-09-25T12:00:00Z"
        assert "measured from a dispatch mark" in reason
        assert path.is_file(), "peek consumed the mark the ledger append still needs"

        # The consumer after it still gets the same stamp, and clears it.
        assert review_dispatch.consume(tmp_path, "review.critic", "abc123")[0] == stamp
        assert not path.is_file()

    def test_peek_refuses_a_mark_for_another_tree_as_consume_does(self, tmp_path):
        """One judgement, two verbs: a fact and a ledger event minted from the
        same mark must not disagree about whether it was this review's."""
        path = _mark(tmp_path, "abc123")
        peeked = review_dispatch.peek(tmp_path, "review.critic", "def456")
        assert peeked[0] is None
        assert "different tree" in peeked[1]
        assert path.is_file()
        assert review_dispatch.consume(tmp_path, "review.critic", "def456") == peeked

    def test_peek_refuses_when_git_did_not_answer(self, tmp_path):
        _mark(tmp_path, "abc123")
        assert review_dispatch.peek(tmp_path, "review.critic", None)[0] is None

    def test_peek_with_no_mark_is_not_measured(self, tmp_path):
        stamp, reason = review_dispatch.peek(tmp_path, "review.critic", "abc123")
        assert stamp is None
        assert "no dispatch mark" in reason


class TestFactIntervalSeconds:
    """The fact-level door to the interval predicate."""

    def _fact(self, dispatched_at=..., ts="2026-09-25T12:05:00Z") -> dict:
        body = {"mode": "chunk", "duration_seconds": 900}
        if dispatched_at is not ...:
            body["dispatched_at"] = dispatched_at
        return {"kind": "review", "ts": ts, "body": body}

    def test_the_interval_ends_at_the_facts_own_ts(self):
        assert review_dispatch.fact_interval_seconds(
            self._fact("2026-09-25T12:00:00Z")
        ) == 300.0

    def test_a_fact_without_the_key_is_not_measured(self):
        """Every fact minted before the key existed. Its estimate stays the
        estimate; the clock reports nothing rather than zero."""
        assert review_dispatch.fact_interval_seconds(self._fact()) is None

    def test_the_plausibility_bound_is_carried(self):
        """A 7h interval is a stale mark, not a review — the same bound the
        ledger readers carry, because it is the same predicate."""
        assert review_dispatch.fact_interval_seconds(
            self._fact("2026-09-25T05:05:00Z")
        ) is None

    def test_an_out_of_order_or_malformed_fact_is_not_measured(self):
        assert review_dispatch.fact_interval_seconds(
            self._fact("2026-09-25T13:00:00Z")
        ) is None
        assert review_dispatch.fact_interval_seconds(self._fact(None)) is None
        assert review_dispatch.fact_interval_seconds({"ts": "x", "body": None}) is None
        assert review_dispatch.fact_interval_seconds(None) is None


class TestBuildFactBodyWritesTheKeyOnlyWhenMeasured:
    MANIFEST = {
        "base_tree": "b" * 40, "head_tree": "h" * 40, "commit_reviewed": "c" * 40,
        "mode": "chunk", "mode_chosen_by": "explicit",
        "files_reviewed": ["a.py"], "files_changed": ["a.py"],
    }

    def test_a_stamp_is_carried(self):
        body = critic_consolidate.build_fact_body(
            self.MANIFEST, [], dispatched_at="2026-09-25T12:00:00Z"
        )
        assert body["dispatched_at"] == "2026-09-25T12:00:00Z"

    def test_no_stamp_writes_no_key(self):
        """Red if the absence is ever written as a VALUE. A null reads as
        deliberate, and every reader would have to special-case it."""
        body = critic_consolidate.build_fact_body(self.MANIFEST, [])
        assert "dispatched_at" not in body
        body = critic_consolidate.build_fact_body(self.MANIFEST, [], dispatched_at=None)
        assert "dispatched_at" not in body


def _reviewed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    (repo / "src/app.py").write_text("x = 2\n")
    begun = _run_begin(repo, "--mode", "chunk")
    assert begun.returncode == 0, begun.stderr
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write_partial(repo, head)
    return repo


def _review_fact(repo: Path) -> dict:
    facts = evidence.facts_of_kind(evidence.read_facts(repo), "review")
    assert len(facts) == 1, facts
    return facts[0]


def _ledger_events(repo: Path) -> list[dict]:
    path = repo / LEDGER_REL
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


class TestConsolidationStampsTheFact:
    """End to end through the real lifecycle: `critic-begin` marks,
    `critic-consolidate` mints the fact and then appends the ledger event."""

    def test_the_fact_and_the_ledger_event_carry_the_same_stamp(self, tmp_path):
        """The TREATMENT. Also the ordering claim, asserted rather than argued:
        if consolidate consumed the mark before minting, or the ledger ran
        first, one of the two records would lack the stamp."""
        repo = _reviewed_repo(tmp_path)
        marked = json.loads((repo / CRITIC_MARKER_REL).read_text())["dispatched_at"]

        result = _run_consolidate(repo)
        assert result.returncode == 0, result.stderr

        fact = _review_fact(repo)
        assert fact["body"]["dispatched_at"] == marked
        assert review_dispatch.fact_interval_seconds(fact) is not None
        # The estimate is not displaced: both stay readable.
        assert fact["body"]["duration_seconds"] == 90
        events = [e for e in _ledger_events(repo) if e["event"] == "review.critic"]
        assert len(events) == 1
        assert events[0]["dispatched_at"] == marked, "the ledger lost the mark"
        assert not (repo / CRITIC_MARKER_REL).is_file(), "the mark was never consumed"

    def test_an_unmarked_review_mints_a_fact_with_no_key(self, tmp_path):
        """The CONTROL: same fixture, mark withheld."""
        repo = _reviewed_repo(tmp_path)
        (repo / CRITIC_MARKER_REL).unlink()

        result = _run_consolidate(repo)
        assert result.returncode == 0, result.stderr

        fact = _review_fact(repo)
        assert "dispatched_at" not in fact["body"]
        assert review_dispatch.fact_interval_seconds(fact) is None

    def test_a_mark_for_another_tree_is_not_attached(self, tmp_path):
        """An abandoned run's mark must not hand this review its interval."""
        repo = _reviewed_repo(tmp_path)
        _mark(repo / ".prawduct", "f" * 40)

        result = _run_consolidate(repo)
        assert result.returncode == 0, result.stderr

        fact = _review_fact(repo)
        assert "dispatched_at" not in fact["body"]
