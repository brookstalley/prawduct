"""Tests for finding dispositions as facts — ACCEPT/FILE recorded in the
evidence store so a review's census is derived rather than hand-written.

The claims pinned here are the design's load-bearing ones:

* **The gate cannot be weakened.** A ``disposition`` fact is structurally
  incapable of unblocking a BLOCKING finding — the property that makes it safe
  to let a builder record ACCEPT/FILE without a reviewer in the loop.
* **The join is validated in code.** A disposition must reference a finding the
  store actually holds, and an ACCEPT of a BLOCKING finding needs an explicit
  owner ruling (``review-cycle.md``'s severity rule).
* **Re-disposition appends.** ``read_facts`` dedupes ``(kind, id)`` keeping the
  first occurrence, so a changed answer must land under a new id or it vanishes
  silently. An *unchanged* re-run is a reported no-op, not an accidental dedupe.
* **The census is derived.** The renderer reproduces, from facts, the
  2026-07-29 census that four separate hand-written corrections still got
  wrong — including the accepted-note count and the one finding recorded
  ``waived`` that the prose called FIXED.

Real git repos, sterile config, mirroring ``test_evidence_store.py``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import coverage_algebra, dispositions, evidence, evidence_notes  # noqa: E402

KIND_DISPOSITION = dispositions.KIND


def _seq(fact_id: str) -> int:
    """The sequence a minted disposition id carries, read here rather than by
    :func:`dispositions.answer_key`, so a test of that function cannot grade
    itself: ``disp:<review>:<fid>:<seq>[:<tag>]``, with the review and fid
    free of ``:`` in every fixture in this file."""
    return int(fact_id.split(":")[3])


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


def _make_repo(base: Path, name: str = "repo") -> Path:
    repo = base / name
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _review_fact(
    repo: Path,
    review_id: str,
    findings: list[tuple[str, str]],
    *,
    scope: str | None = None,
    chunk: str | None = None,
    files: "list[str] | None" = None,
    head_commit: "str | None" = None,
) -> None:
    """Append a review fact carrying ``(fid, severity)`` findings.

    ``files`` sets every finding's attribution — the axis
    ``prior_dispositions`` scopes on, so a test about it must be able to set
    it. ``head_commit`` places the review on a lineage — what makes it one of a
    branch's reviews (``coverage.branch_review_ids``)."""
    body = {
        "base_tree": "a" * 40,
        "head_tree": "b" * 40,
        "mode": "final",
        "scope": scope,
        "chunk": chunk,
        "findings": [
            {
                "fid": fid,
                "severity": severity,
                "goal": "Nothing Is Broken",
                "title": f"finding {fid}",
                "recommendation": "do the thing",
                "files": list(files) if files is not None else [],
            }
            for fid, severity in findings
        ],
    }
    if head_commit is not None:
        body["head_commit"] = head_commit
    result = evidence.append_fact(repo, "review", review_id, body)
    assert result["status"] == "appended", result


def _resolution_fact(
    repo: Path, review_id: str, fid: str, disposition: str
) -> None:
    result = evidence.append_fact(
        repo,
        "resolution",
        f"verify-1:{review_id}:{fid}",
        {
            "finding": {"review_id": review_id, "fid": fid},
            "disposition": disposition,
            "verified_by": "verify-1",
            "at_tree": "c" * 40,
        },
    )
    assert result["status"] == "appended", result


def _hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(ROOT)},
    )


# ---------------------------------------------------------------------------
# The safety property: a disposition can never weaken a gate
# ---------------------------------------------------------------------------


class TestDispositionNeverUnblocks:
    def test_accepted_blocking_finding_stays_unresolved(self, tmp_path):
        """The load-bearing invariant. An owner-ruled ACCEPT records the
        decision; only a resolution fact clears the gate."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        result = dispositions.record(
            repo,
            "rev-1",
            "R-1",
            dispositions.ACCEPT,
            reason="superseded by the fail-closed gate",
            owner_ruling="owner confirmed 2026-07-29",
        )
        assert result["status"] == "recorded", result

        store = evidence.read_facts(repo)
        review = evidence.facts_of_kind(store, "review")[0]
        resolved = coverage_algebra.resolution_index(store["facts"])
        unresolved = coverage_algebra.unresolved_blocking(review, resolved)
        assert [f["fid"] for f in unresolved] == ["R-1"]

    def test_disposition_facts_are_invisible_to_the_resolution_index(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )
        store = evidence.read_facts(repo)
        assert coverage_algebra.resolution_index(store["facts"]) == set()

    def test_a_disposition_carries_no_tree_key(self, tmp_path):
        """``distinct_trees`` drives the store-growth advisory; a disposition
        is an answer about a finding, not a coverage edge."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft")
        store = evidence.read_facts(repo)
        disposition = dispositions.disposition_facts(store)[0]
        assert "base_tree" not in disposition["body"]
        assert "head_tree" not in disposition["body"]
        assert evidence.distinct_trees(
            [disposition]
        ) == set(), "a disposition must not inflate the tree-count advisory"


# ---------------------------------------------------------------------------
# Join validation and the severity rule
# ---------------------------------------------------------------------------


class TestJoinValidation:
    def test_unknown_review_is_refused(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(
            repo, "rev-nope", "R-1", dispositions.ACCEPT, reason="x"
        )
        assert result["status"] == "error"
        assert "no finding" in result["reason"]

    def test_unknown_fid_is_refused(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(
            repo, "rev-1", "R-99", dispositions.ACCEPT, reason="x"
        )
        assert result["status"] == "error"
        assert "R-99" in result["reason"]

    def test_nothing_is_written_when_the_join_fails(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        dispositions.record(repo, "rev-1", "R-99", dispositions.ACCEPT, reason="x")
        store = evidence.read_facts(repo)
        assert dispositions.disposition_facts(store) == []

    def test_schema_ahead_records_fail_closed(self, tmp_path):
        """A newer plugin's review fact is invisible here, so the join could
        reject a finding that really exists — refuse rather than record a
        falsehood."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        path = evidence.store_path(repo)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": 99,
                        "kind": "review",
                        "id": "rev-future",
                        "ts": "2030-01-01T00:00:00Z",
                        "body": {},
                    }
                )
                + "\n"
            )
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="x"
        )
        assert result["status"] == "error"
        assert "newer schema" in result["reason"]


class TestMalformedBodiesNeverRaise:
    """``read_facts`` validates the envelope, not the body's shape, so a
    JSON-valid fact whose ``finding`` is not an object reaches these readers.
    They must skip it, not raise an unattributed traceback out of the CLI."""

    def _append_raw(self, repo: Path, kind: str, fact_id: str, body: object) -> None:
        path = evidence.store_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": 1,
                        "kind": kind,
                        "id": fact_id,
                        "ts": "2026-07-29T00:00:00Z",
                        "body": body,
                    }
                )
                + "\n"
            )

    def test_non_object_finding_is_skipped_by_every_reader(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        self._append_raw(repo, KIND_DISPOSITION, "disp:bogus:1", {"finding": "nope"})
        self._append_raw(repo, KIND_DISPOSITION, "disp:bogus:2", {"finding": ["x"]})
        self._append_raw(
            repo, "resolution", "res:bogus", {"finding": "nope", "disposition": "fixed"}
        )

        store = evidence.read_facts(repo)
        assert dispositions.disposition_facts(store) == []
        assert dispositions.disposition_index(store) == {}
        assert dispositions.disposition_history(store, "rev-1", "R-1") == []
        assert dispositions.resolution_detail_index(store) == {}
        report = dispositions.census(store)
        assert report["status"] == "ok"
        assert report["reviews"][0]["rows"][0]["state"] == "undispositioned"

    def test_record_still_returns_rather_than_raising(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        self._append_raw(repo, KIND_DISPOSITION, "disp:bogus:1", {"finding": 42})
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        assert result["status"] == "recorded", result

    def test_cli_emits_no_traceback_on_a_malformed_body(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        self._append_raw(repo, KIND_DISPOSITION, "disp:bogus:1", {"finding": "nope"})
        proc = _hook(repo, "render-dispositions", "--review", "rev-1")
        assert proc.returncode == 0, proc.stderr
        assert "Traceback" not in proc.stderr


class TestSchemaAheadFailsClosed:
    def _append_future(self, repo: Path) -> None:
        path = evidence.store_path(repo)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": 99,
                        "kind": "review",
                        "id": "rev-future",
                        "ts": "2030-01-01T00:00:00Z",
                        "body": {},
                    }
                )
                + "\n"
            )

    def test_render_refuses_rather_than_showing_a_partial_census(self, tmp_path):
        """The recorder's twin was pinned from the start; the renderer's was
        not — and a census silently missing a newer plugin's reviews is exactly
        the drift this command exists to end."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        self._append_future(repo)
        proc = _hook(repo, "render-dispositions", "--review", "rev-1")
        assert proc.returncode == 1
        assert "newer schema" in proc.stderr
        assert proc.stdout.strip() == ""

    def test_recorder_refuses_too(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        self._append_future(repo)
        proc = _hook(repo, "disposition", "rev-1", "R-1", "--accept", "craft")
        assert proc.returncode == 1
        assert "newer schema" in proc.stderr


class TestSeverityRule:
    def test_accepting_a_blocking_finding_needs_an_owner_ruling(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="not worth it"
        )
        assert result["status"] == "error"
        assert "BLOCKING" in result["reason"]

    def test_owner_ruling_permits_the_accept_and_is_persisted(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        result = dispositions.record(
            repo,
            "rev-1",
            "R-1",
            dispositions.ACCEPT,
            reason="superseded",
            owner_ruling="owner confirmed",
        )
        assert result["status"] == "recorded", result
        store = evidence.read_facts(repo)
        body = dispositions.disposition_facts(store)[0]["body"]
        assert body["owner_ruling"] == "owner confirmed"

    def test_warning_and_note_need_no_ruling(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning"), ("R-2", "note")])
        for fid in ("R-1", "R-2"):
            result = dispositions.record(
                repo, "rev-1", fid, dispositions.ACCEPT, reason="craft observation"
            )
            assert result["status"] == "recorded", result

    def test_filing_a_blocking_finding_is_allowed_but_does_not_unblock(self, tmp_path):
        """The severity rule governs ACCEPT. A FILE is permitted and the gate
        keeps blocking on its own — no second mechanism needed."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )
        assert result["status"] == "recorded", result
        store = evidence.read_facts(repo)
        review = evidence.facts_of_kind(store, "review")[0]
        resolved = coverage_algebra.resolution_index(store["facts"])
        assert coverage_algebra.unresolved_blocking(review, resolved)


class TestArgumentValidation:
    def test_accept_requires_a_reason(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT)
        assert result["status"] == "error"
        assert "--accept" in result["reason"]

    def test_file_requires_a_backlog_id(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.FILE)
        assert result["status"] == "error"
        assert "--file" in result["reason"]

    def test_accept_and_backlog_id_are_mutually_exclusive(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(
            repo,
            "rev-1",
            "R-1",
            dispositions.ACCEPT,
            reason="x",
            backlog_id="ABC-1234",
        )
        assert result["status"] == "error"
        assert "never both" in result["reason"]

    def test_unknown_action_is_refused(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(repo, "rev-1", "R-1", "ignore")
        assert result["status"] == "error"
        assert "unknown action" in result["reason"]


# ---------------------------------------------------------------------------
# Re-disposition: append, never edit
# ---------------------------------------------------------------------------


class TestRedisposition:
    def test_changed_answer_appends_under_a_new_id(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        first = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        second = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )
        assert first["id"] != second["id"]
        assert second["superseded"] == first["id"]
        assert (_seq(first["id"]), _seq(second["id"])) == (1, 2)

        store = evidence.read_facts(repo)
        assert len(dispositions.disposition_history(store, "rev-1", "R-1")) == 2

    def test_a_new_id_carries_its_sequence_and_a_tag_of_its_body(self, tmp_path):
        """``disp:<review>:<fid>:<seq>:<tag>``, the tag the first 12 hex chars
        of SHA-256 over the canonical body. Two different answers at one
        ``seq`` then get two ids, and the same answer at one ``seq`` gets one."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        assert result["status"] == "recorded", result
        stored = dispositions.disposition_index(evidence.read_facts(repo))[
            ("rev-1", "R-1")
        ]
        assert stored["id"] == result["id"]
        prefix, seq, tag = result["id"].rsplit(":", 2)
        assert prefix == "disp:rev-1:R-1" and seq == "1"
        canonical = json.dumps(stored["body"], sort_keys=True, separators=(",", ":"))
        assert tag == hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def test_newest_answer_wins(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft")
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )
        store = evidence.read_facts(repo)
        newest = dispositions.disposition_index(store)[("rev-1", "R-1")]
        assert newest["body"]["action"] == dispositions.FILE
        assert newest["body"]["backlog_id"] == "ABC-1234"

    def test_reverting_to_an_earlier_answer_still_appends(self, tmp_path):
        """The trap a content-keyed id would fall into: accept → file → accept
        must land a third fact, not collide with the first and leave FILE
        winning."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft")
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )
        third = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        assert third["status"] == "recorded", third
        store = evidence.read_facts(repo)
        assert len(dispositions.disposition_history(store, "rev-1", "R-1")) == 3
        newest = dispositions.disposition_index(store)[("rev-1", "R-1")]
        assert newest["body"]["action"] == dispositions.ACCEPT

    def test_a_pruned_superseded_line_cannot_recycle_a_live_id(self, tmp_path):
        """The sequence must step past ids the store already holds. Deriving it
        from history length alone would recycle a live id once a superseded line
        is pruned — and a colliding append is discarded by dedupe while the
        caller is still told it was recorded."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        first = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="one"
        )
        second = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )

        # Prune the FIRST disposition, shortening the history under the store.
        # Its id carries a body tag, so the line is found by the id the writer
        # reported rather than by a spelled-out id.
        path = evidence.store_path(repo)
        lines = path.read_text().splitlines()
        kept = [line for line in lines if f'"{first["id"]}"' not in line]
        assert len(kept) == len(lines) - 1, "the first answer was not pruned"
        path.write_text("\n".join(kept) + "\n")

        third = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="three"
        )
        assert third["status"] == "recorded", third
        assert third["id"] != second["id"], "recycled a live id — answer would be lost"
        # The surviving history holds only seq 2, so the new answer must rank
        # above it: the winner rule reads the sequence, not store order.
        assert _seq(third["id"]) == 3

        store = evidence.read_facts(repo)
        newest = dispositions.disposition_index(store)[("rev-1", "R-1")]
        assert newest["body"]["reason"] == "three"

    def test_identical_rerun_is_a_reported_noop(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        first = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        again = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft"
        )
        assert again["status"] == "unchanged"
        assert again["id"] == first["id"]
        store = evidence.read_facts(repo)
        assert len(dispositions.disposition_history(store, "rev-1", "R-1")) == 1

    def test_dispositions_of_different_findings_do_not_share_a_sequence(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note"), ("R-2", "note")])
        a = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="x")
        b = dispositions.record(repo, "rev-1", "R-2", dispositions.ACCEPT, reason="y")
        assert a["id"] != b["id"]
        store = evidence.read_facts(repo)
        assert len(dispositions.disposition_facts(store)) == 2


# ---------------------------------------------------------------------------
# One winner, whatever order the store holds the answers in
# ---------------------------------------------------------------------------


def _envelope(kind: str, fact_id: str, body: dict, ts: str) -> dict:
    """A store envelope as another clone's writer would have built it — the
    shape ``evidence.append_envelope`` takes from the notes transport."""
    return {
        "schema": evidence.SCHEMA_VERSION,
        "kind": kind,
        "id": fact_id,
        "ts": ts,
        "body": body,
    }


def _answer(fid: str, action: str, **fields) -> dict:
    body = {
        "finding": {"review_id": "rev-1", "fid": fid},
        "action": action,
        "reason": None,
        "backlog_id": None,
        "owner_ruling": None,
        "paths": None,
    }
    body.update(fields)
    return body


def _append_all(repo: Path, envelopes: "list[dict]") -> None:
    for envelope in envelopes:
        result = evidence.append_envelope(repo, envelope)
        assert result["status"] == "appended", result


def _held(repo: Path, fid: str = "R-1") -> dict:
    """What one store says about one finding: the winner's id, the history's
    ids, and the census — the three views a clone shows."""
    store = evidence.read_facts(repo)
    assert store["status"] == "ok", store
    winner = dispositions.disposition_index(store).get(("rev-1", fid))
    return {
        "winner": winner and winner["id"],
        "history": [
            f["id"] for f in dispositions.disposition_history(store, "rev-1", fid)
        ],
        "census": dispositions.census(store, review_id="rev-1"),
    }


class TestOneWinnerInEveryOrder:
    """A finding's winner is its answer with the greatest ``(seq, id)``, so
    every clone holding the same facts shows the same answer, however its store
    came to hold them: ingest appends note lines in the order it reads them,
    and ``evidence sync`` merges notes with ``cat_sort_uniq``, which sorts the
    lines."""

    def _facts(self) -> "list[dict]":
        review = _envelope(
            "review",
            "rev-1",
            {
                "mode": "final",
                "scope": "s",
                "findings": [
                    {"fid": "R-1", "severity": "warning", "title": "one", "files": []},
                    {"fid": "R-2", "severity": "note", "title": "two", "files": []},
                ],
            },
            "2026-11-01T00:00:00Z",
        )
        answers = [
            # Legacy ids, no tag. `:10` is the newest answer, and its ``ts`` is
            # the EARLIEST, so neither a timestamp nor a lexical order of ids
            # nor store order can pick it by accident.
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-1:1",
                      _answer("R-1", "accept", reason="first"), "2026-11-02T00:00:00Z"),
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-1:2",
                      _answer("R-1", "file", backlog_id="X-2"), "2026-11-03T00:00:00Z"),
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-1:10",
                      _answer("R-1", "accept", reason="tenth"), "2026-11-01T12:00:00Z"),
            # Tagged ids, two concurrent answers at seq 2.
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-2:1:aaaaaaaaaaaa",
                      _answer("R-2", "accept", reason="one"), "2026-11-02T00:00:00Z"),
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-2:2:cccccccccccc",
                      _answer("R-2", "file", backlog_id="X-9"), "2026-11-03T00:00:00Z"),
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-2:2:bbbbbbbbbbbb",
                      _answer("R-2", "accept", reason="two"), "2026-11-04T00:00:00Z"),
        ]
        return [review, *answers]

    def test_three_orders_give_one_index_one_history_and_one_census(self, tmp_path):
        facts = self._facts()
        review, answers = facts[0], facts[1:]
        # The order `cat_sort_uniq` leaves a merged note in: its lines sorted
        # bytewise. Every envelope line starts `{"schema": 1, "kind": …, "id":`,
        # so this is id order, which puts `:10` between `:1` and `:2`.
        merged = sorted(answers, key=evidence.envelope_line)
        assert [e["id"] for e in merged][:3] == [
            "disp:rev-1:R-1:1", "disp:rev-1:R-1:10", "disp:rev-1:R-1:2",
        ]
        orders = {
            "appended": answers,
            "reversed": list(reversed(answers)),
            "merged": merged,
        }
        held = {}
        for name, order in orders.items():
            repo = _make_repo(tmp_path, name)
            _append_all(repo, [review, *order])
            held[name] = {fid: _held(repo, fid) for fid in ("R-1", "R-2")}

        assert held["appended"] == held["reversed"] == held["merged"]
        r1, r2 = held["merged"]["R-1"], held["merged"]["R-2"]
        assert r1["winner"] == "disp:rev-1:R-1:10"
        assert r1["history"] == [
            "disp:rev-1:R-1:1", "disp:rev-1:R-1:2", "disp:rev-1:R-1:10",
        ]
        # Concurrent answers at one seq rank by id: arbitrary, but the same
        # in every clone.
        assert r2["winner"] == "disp:rev-1:R-2:2:cccccccccccc"
        rows = {row["fid"]: row for row in r1["census"]["reviews"][0]["rows"]}
        assert rows["R-1"]["state"] == dispositions.STATE_ACCEPTED
        assert rows["R-1"]["reason"] == "tenth"
        assert rows["R-2"]["state"] == dispositions.STATE_FILED

    def test_the_prior_block_shows_the_winner_in_every_order(self, tmp_path):
        facts = self._facts()
        review, answers = facts[0], facts[1:]
        seen = []
        for name, order in (("a", answers), ("b", list(reversed(answers)))):
            repo = _make_repo(tmp_path, name)
            _append_all(repo, [review, *order])
            block = dispositions.prior_dispositions(evidence.read_facts(repo), [])
            seen.append({(e["fid"], e["action"], e["reason"]) for e in block["entries"]})
        assert seen[0] == seen[1] == {("R-1", "accept", "tenth"), ("R-2", "file", None)}

    def test_the_key_reads_legacy_tagged_and_unparseable_ids(self):
        def fact(fact_id: str) -> dict:
            return _envelope(KIND_DISPOSITION, fact_id, _answer("R-1", "accept",
                             reason="r"), "2026-11-01T00:00:00Z")

        assert dispositions.answer_key(fact("disp:rev-1:R-1:10")) == (
            10, "disp:rev-1:R-1:10")
        assert dispositions.answer_key(fact("disp:rev-1:R-1:3:0123456789ab")) == (
            3, "disp:rev-1:R-1:3:0123456789ab")
        # The prefix is built from the fact's own body, so an id naming some
        # other finding does not parse, and neither does a non-integer seq.
        for unparseable in ("disp:bogus:1", "disp:rev-1:R-2:7", "disp:rev-1:R-1:x",
                            "disp:rev-1:R-1:", "disp:rev-1:R-1:-1"):
            assert dispositions.answer_key(fact(unparseable)) == (0, unparseable)
        assert dispositions.answer_key({"id": 5, "body": "nope"}) == (0, "")

    def test_an_unparseable_id_ranks_below_every_well_formed_answer(self, tmp_path):
        repo = _make_repo(tmp_path)
        _append_all(repo, [
            self._facts()[0],
            _envelope(KIND_DISPOSITION, "disp:rev-1:R-1:1",
                      _answer("R-1", "file", backlog_id="X-1"), "2026-11-01T00:00:00Z"),
            _envelope(KIND_DISPOSITION, "zzz-not-a-disposition-id",
                      _answer("R-1", "accept", reason="odd"), "2026-11-09T00:00:00Z"),
        ])
        assert _held(repo)["winner"] == "disp:rev-1:R-1:1"

    def test_two_answers_at_one_seq_keep_both_and_agree_on_a_winner(self, tmp_path):
        """Two clones answer one finding without seeing each other, then each
        receives the other's line. Both answers survive in both stores, and
        both stores pick the same one."""
        a = _make_repo(tmp_path, "a")
        _review_fact(a, "rev-1", [("R-1", "warning")])
        review = next(
            f for f in evidence.read_facts(a)["facts"] if f["kind"] == "review"
        )
        b = _make_repo(tmp_path, "b")
        _append_all(b, [review])

        in_a = dispositions.record(a, "rev-1", "R-1", dispositions.ACCEPT, reason="mine")
        in_b = dispositions.record(b, "rev-1", "R-1", dispositions.FILE, backlog_id="X-1")
        assert in_a["status"] == in_b["status"] == "recorded"
        assert _seq(in_a["id"]) == _seq(in_b["id"]) == 1
        assert in_a["id"] != in_b["id"], "two different answers minted one id"

        def stored(repo: Path, fact_id: str) -> dict:
            return next(
                f for f in evidence.read_facts(repo)["facts"] if f["id"] == fact_id
            )

        from_a, from_b = stored(a, in_a["id"]), stored(b, in_b["id"])
        _append_all(a, [from_b])
        _append_all(b, [from_a])

        held_a, held_b = _held(a), _held(b)
        assert held_a["winner"] == held_b["winner"] == max(in_a["id"], in_b["id"])
        assert held_a["history"] == held_b["history"]
        assert sorted(held_a["history"]) == sorted([in_a["id"], in_b["id"]])

    def test_an_answer_given_after_another_wins_despite_an_earlier_clock(
        self, tmp_path
    ):
        """B re-answers having seen A's answer, on a machine whose clock runs
        behind. B's answer still wins, in A, and in a third store that
        receives B's line before A's — because B minted the higher seq."""
        a = _make_repo(tmp_path, "a")
        _review_fact(a, "rev-1", [("R-1", "warning")])
        first = dispositions.record(a, "rev-1", "R-1", dispositions.ACCEPT, reason="first")
        held = {f["id"]: f for f in evidence.read_facts(a)["facts"]}
        review, from_a = held["rev-1"], held[first["id"]]

        b = _make_repo(tmp_path, "b")
        _append_all(b, [review, from_a])
        second = dispositions.record(b, "rev-1", "R-1", dispositions.FILE, backlog_id="X-1")
        assert second["status"] == "recorded", second
        from_b = next(
            f for f in evidence.read_facts(b)["facts"] if f["id"] == second["id"]
        )
        from_b = {**from_b, "ts": "2000-01-01T00:00:00Z"}
        assert from_b["ts"] < from_a["ts"]

        c = _make_repo(tmp_path, "c")
        _append_all(c, [review, from_b, from_a])
        _append_all(a, [from_b])

        for repo in (a, c):
            assert _held(repo)["winner"] == second["id"]
            block = dispositions.prior_dispositions(evidence.read_facts(repo), [])
            assert [(e["action"], e["backlog_id"]) for e in block["entries"]] == [
                ("file", "X-1")
            ]

    def test_a_pruned_history_mints_above_the_sequence_it_still_holds(self, tmp_path):
        """With only seq 3 left, one more than the history's LENGTH is 2, which
        would rank below the answer it supersedes. One more than the history's
        greatest seq is 4, and wins."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        ids = [
            dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="one")["id"],
            dispositions.record(repo, "rev-1", "R-1", dispositions.FILE, backlog_id="X-1")["id"],
            dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="three")["id"],
        ]
        assert [_seq(i) for i in ids] == [1, 2, 3]
        path = evidence.store_path(repo)
        lines = path.read_text().splitlines()
        kept = [
            line for line in lines
            if f'"{ids[0]}"' not in line and f'"{ids[1]}"' not in line
        ]
        assert len(kept) == len(lines) - 2, "the first two answers were not pruned"
        path.write_text("\n".join(kept) + "\n")
        assert _held(repo)["history"] == [ids[2]]

        fourth = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="X-4"
        )
        assert fourth["status"] == "recorded", fourth
        assert _seq(fourth["id"]) == 4
        assert _held(repo)["winner"] == fourth["id"]


# ---------------------------------------------------------------------------
# The writer puts its fact on the notes transport
# ---------------------------------------------------------------------------


def _note_on(repo: Path, commit: str) -> "str | None":
    proc = subprocess.run(
        ["git", "notes", "--ref", evidence_notes.NOTES_REF, "show", commit],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    return proc.stdout if proc.returncode == 0 else None


class TestTheWriterAttaches:
    """``record`` attaches the fact it appended to the note on the anchor of
    the review it answers, and reports how that went. The fact is in the
    store either way, so a note that cannot be written never fails the
    record."""

    def _anchored(self, tmp_path) -> "tuple[Path, str]":
        """A repo whose review is anchored on its first commit, with HEAD
        moved past it — so a note on HEAD and a note on the anchor differ."""
        repo = _make_repo(tmp_path)
        anchor = _git(repo, "rev-parse", "HEAD")
        _review_fact(repo, "rev-1", [("R-1", "warning"), ("R-2", "note")],
                     head_commit=anchor)
        (repo / "code.py").write_text("x = 2\n")
        _git(repo, "commit", "-qam", "c2")
        assert _git(repo, "rev-parse", "HEAD") != anchor
        return repo, anchor

    def test_with_no_remote_and_no_ref_it_records_and_writes_a_local_note(
        self, tmp_path, monkeypatch
    ):
        # Dispositions join the transported set in another change; admitting
        # the kind here drives the real `attach` through this writer's call.
        monkeypatch.setattr(
            evidence, "TRANSPORTED_KINDS", evidence.TRANSPORTED_KINDS | {KIND_DISPOSITION}
        )
        repo, anchor = self._anchored(tmp_path)
        # `git notes append` commits to the notes ref, so it needs an identity
        # the runner's environment may not supply.
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        assert _git(repo, "remote") == ""
        assert _note_on(repo, anchor) is None

        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        assert result["status"] == "recorded", result
        assert result["note"] == {"status": "attached", "reason": None}
        note = _note_on(repo, anchor)
        assert note is not None and f'"{result["id"]}"' in note
        assert _note_on(repo, _git(repo, "rev-parse", "HEAD")) is None

    def test_unpatched_the_result_carries_the_note_and_nothing_fails(self, tmp_path):
        """Nothing injected: the production `attach` runs. Whether it writes or
        skips depends on whether the kind is in the transported set, which
        another change owns; either way the record stands and says which."""
        repo, _anchor = self._anchored(tmp_path)
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        assert result["status"] == "recorded", result
        assert set(result["note"]) == {"status", "reason"}
        assert result["note"]["status"] in ("skipped", "attached")

    def test_a_review_with_no_anchor_skips_the_note(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            evidence, "TRANSPORTED_KINDS", evidence.TRANSPORTED_KINDS | {KIND_DISPOSITION}
        )
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        assert result["status"] == "recorded", result
        assert result["note"]["status"] == "skipped"
        assert "not a commit id" in result["note"]["reason"]

    def test_it_hands_attach_the_stored_envelope_and_the_review_anchor(
        self, tmp_path, monkeypatch
    ):
        calls = []

        def fake(project_dir, envelope, anchor):
            calls.append((envelope, anchor))
            return {"status": "attached", "reason": None}

        monkeypatch.setattr(evidence_notes, "attach", fake)
        repo, anchor = self._anchored(tmp_path)
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        stored = next(
            f for f in evidence.read_facts(repo)["facts"] if f["id"] == result["id"]
        )
        assert calls == [(stored, anchor)]

    def test_an_unchanged_rerun_attaches_nothing(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            evidence_notes, "attach",
            lambda *a: calls.append(a) or {"status": "attached", "reason": None},
        )
        repo, _anchor = self._anchored(tmp_path)
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        again = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        assert again["status"] == "unchanged"
        assert len(calls) == 1

    def _failing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            evidence_notes, "attach",
            lambda *a: {"status": "error", "reason": "git notes append failed (boom)"},
        )

    def test_a_failed_attach_still_records(self, tmp_path, monkeypatch):
        self._failing(monkeypatch)
        repo, _anchor = self._anchored(tmp_path)
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="ok")
        assert result["status"] == "recorded", result
        assert result["note"] == {
            "status": "error", "reason": "git notes append failed (boom)",
        }
        index = dispositions.disposition_index(evidence.read_facts(repo))
        assert index[("rev-1", "R-1")]["id"] == result["id"]

    def test_the_cli_says_the_note_failed_and_exits_zero(
        self, tmp_path, monkeypatch, capsys
    ):
        repo, _anchor = self._anchored(tmp_path)
        assert dispositions.disposition_cmd(
            repo, ["rev-1", "R-2", "--accept", "fine"]
        ) == 0
        control = capsys.readouterr()
        assert "recorded ACCEPT" in control.out
        assert "git note" not in control.err

        self._failing(monkeypatch)
        assert dispositions.disposition_cmd(
            repo, ["rev-1", "R-1", "--accept", "ok"]
        ) == 0
        out = capsys.readouterr()
        assert "recorded ACCEPT" in out.out
        fact_id = dispositions.disposition_index(evidence.read_facts(repo))[
            ("rev-1", "R-1")]["id"]
        notes = [line for line in out.err.splitlines() if line.startswith("NOTE: disposition:")]
        assert len(notes) == 1, out.err
        assert repr(fact_id) in notes[0]
        assert "(git notes append failed (boom))" in notes[0]
        assert "does not travel to other clones" in notes[0]

    def test_the_sweep_counts_its_unsent_records(self, tmp_path, monkeypatch):
        self._failing(monkeypatch)
        repo, _anchor = self._anchored(tmp_path)
        swept = dispositions.auto_accept(repo, ["rev-1"], reason="budget spent")
        assert swept["accepted"] == 2 and swept["failed"] == []
        assert swept["unsent"] == 2
        assert len(dispositions.disposition_index(evidence.read_facts(repo))) == 2


# ---------------------------------------------------------------------------
# The census
# ---------------------------------------------------------------------------


class TestCensus:
    def test_states_are_derived_from_the_right_fact_kind(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(
            repo,
            "rev-1",
            [
                ("R-1", "blocking"),
                ("R-2", "warning"),
                ("R-3", "note"),
                ("R-4", "note"),
                ("R-5", "note"),
            ],
        )
        _resolution_fact(repo, "rev-1", "R-1", "fixed")
        _resolution_fact(repo, "rev-1", "R-2", "waived")
        dispositions.record(repo, "rev-1", "R-3", dispositions.ACCEPT, reason="craft")
        dispositions.record(
            repo, "rev-1", "R-4", dispositions.FILE, backlog_id="ABC-1234"
        )
        # R-5 left alone — the gap the census exists to surface.

        report = dispositions.census(evidence.read_facts(repo))
        states = {r["fid"]: r["state"] for r in report["reviews"][0]["rows"]}
        assert states == {
            "R-1": "fixed",
            "R-2": "waived",
            "R-3": "accepted",
            "R-4": "filed",
            "R-5": "undispositioned",
        }
        assert report["summary"]["undispositioned"] == 1
        assert report["summary"]["findings"] == 5

    def test_a_summary_only_finding_is_named_in_the_census_and_the_prior_block(
        self, tmp_path
    ):
        """Both readers must fall back to `summary` when there is no `title`.

        A DERIVED findings record — the shape `.critic-findings.json` and the
        review facts written from it actually carry — states the finding under
        `summary`. `prior_dispositions` already fell back; `_row` did not, so the
        census rendered `title: null` for exactly the records a human reads to
        check a disposition was filed against the right finding, and a null title
        makes that check impossible.

        This module's own `_review_fact` helper always set `title`, which is why
        nothing caught it: the fixture was shaped like the input that works. So
        the finding here is built with `summary` and no `title` at all, and both
        readers are asserted, because fixing one and leaving the other is how
        this defect came to exist.
        """
        repo = _make_repo(tmp_path)
        body = {
            "base_tree": "a" * 40,
            "head_tree": "b" * 40,
            "mode": "final",
            "scope": None,
            "chunk": None,
            "findings": [
                {
                    "fid": "R-1",
                    "severity": "warning",
                    "goal": "Nothing Is Broken",
                    "summary": "the gate reads a stale tree",
                    "files": ["lib/a.py"],
                }
            ],
        }
        assert evidence.append_fact(repo, "review", "rev-1", body)["status"] == "appended"
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design"
        )
        store = evidence.read_facts(repo)

        row = dispositions.census(store)["reviews"][0]["rows"][0]
        assert row["title"] == "the gate reads a stale tree", (
            "the census renders no name for a summary-only finding, so the row "
            "cannot be matched to the finding it dispositions"
        )
        entry = dispositions.prior_dispositions(store, ["lib/a.py"])["entries"][0]
        assert entry["title"] == "the gate reads a stale tree"

    def test_unrecognized_resolution_disposition_is_shown_not_hidden(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        _resolution_fact(repo, "rev-1", "R-1", "transmuted")
        report = dispositions.census(evidence.read_facts(repo))
        assert report["reviews"][0]["rows"][0]["state"] == "resolved-transmuted"

    def test_conflicting_records_are_surfaced(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        _resolution_fact(repo, "rev-1", "R-1", "fixed")
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="huh")
        report = dispositions.census(evidence.read_facts(repo))
        assert report["summary"]["conflicts"] == 1
        assert report["reviews"][0]["rows"][0]["conflict"] is True

    def test_scope_selector_spans_every_review_of_that_scope(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")], scope="alpha")
        _review_fact(repo, "rev-2", [("R-1", "note")], scope="alpha")
        _review_fact(repo, "rev-3", [("R-1", "note")], scope="beta")
        report = dispositions.census(evidence.read_facts(repo), scope="alpha")
        assert [r["review_id"] for r in report["reviews"]] == ["rev-1", "rev-2"]
        assert report["summary"]["findings"] == 2

    def test_default_selection_is_the_newest_review(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        _review_fact(repo, "rev-2", [("R-1", "note"), ("R-2", "note")])
        report = dispositions.census(evidence.read_facts(repo))
        assert [r["review_id"] for r in report["reviews"]] == ["rev-2"]

    def test_unknown_selector_is_an_error_not_an_empty_table(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")], scope="alpha")
        assert dispositions.census(
            evidence.read_facts(repo), review_id="rev-typo"
        )["status"] == "error"
        assert dispositions.census(
            evidence.read_facts(repo), scope="typo"
        )["status"] == "error"

    def test_empty_store_is_an_error(self, tmp_path):
        repo = _make_repo(tmp_path)
        report = dispositions.census(evidence.read_facts(repo))
        assert report["status"] == "error"
        assert "no review facts" in report["reason"]


class TestMarkdownRendering:
    """The human path — ``--json``-only tests never exercise the formatter."""

    def test_table_carries_each_finding_and_its_state(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(
            repo, "rev-1", [("R-1", "note"), ("R-2", "note")], scope="alpha", chunk="01"
        )
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="craft")
        dispositions.record(
            repo, "rev-1", "R-2", dispositions.FILE, backlog_id="ABC-1234"
        )
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "| Finding | Severity | State | Detail |" in text
        assert "| R-1 | note | accepted | craft |" in text
        assert "| R-2 | note | filed | `ABC-1234` |" in text
        assert "scope `alpha`" in text
        assert "chunk 01" in text
        assert "**2 findings** (2 note)" in text

    def test_the_undispositioned_line_names_only_verbs_that_exist(self, tmp_path):
        """#606's wording defect: the line said every finding takes "an ACCEPT,
        FIX or FILE", but `disposition` has no `--fix`. A fix is verified by a
        verify pass or recorded with `--fixed`; the line names both routes."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        text = dispositions.render_markdown(dispositions.census(evidence.read_facts(repo)))
        line = next(ln for ln in text.splitlines() if "undispositioned**" in ln)
        assert "ACCEPT, FIX or FILE" not in line
        assert "`disposition --fixed <paths>`" in line and "verify-resolutions" in line

    def test_owner_ruled_accept_is_labelled_distinctly(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        dispositions.record(
            repo,
            "rev-1",
            "R-1",
            dispositions.ACCEPT,
            reason="superseded",
            owner_ruling="owner confirmed",
        )
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "accepted (owner ruling)" in text
        assert "owner ruling: owner confirmed" in text

    def test_severity_parenthetical_sums_to_the_total(self, tmp_path):
        """A census whose parenthetical disagrees with its own total is the
        defect class this renderer retires, so an unrated severity is shown
        rather than dropped from the breakdown."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        path = evidence.store_path(repo)
        lines = path.read_text().splitlines()
        record = json.loads(lines[0])
        record["body"]["findings"].append({"fid": "R-2", "title": "no severity"})
        lines[0] = json.dumps(record)
        path.write_text("\n".join(lines) + "\n")

        report = dispositions.census(evidence.read_facts(repo))
        assert report["summary"]["findings"] == 2
        text = dispositions.render_markdown(report)
        assert "**2 findings** (1 note, 1 unrated)" in text

    def test_singular_finding_reads_as_singular(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "**1 finding** (1 note)" in text

    def test_clean_pass_renders_a_whole_sentence(self, tmp_path):
        """A clean pass records an empty findings array, so this is an ordinary
        case — and its summary is pasted into a change-log entry."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [])
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "_No findings._" in text
        assert "**No findings** — a clean pass." in text
        assert "— ." not in text
        assert "(none)" not in text

    def test_undispositioned_findings_are_called_out(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "1 undispositioned" in text

    def test_a_reason_containing_a_pipe_cannot_break_the_table(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="a | b\nc"
        )
        text = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        row = [line for line in text.splitlines() if line.startswith("| R-1 ")][0]
        # The pipe survives as an escaped literal, so the row still has exactly
        # the four cells the header declares.
        assert "\\|" in row
        assert row.replace("\\|", "").count("|") == 5
        assert "\n" not in row


# ---------------------------------------------------------------------------
# The 2026-07-29 case study — real facts, real census, real corrections
# ---------------------------------------------------------------------------

#: The findings of ``rev-20260729T185143Z-b35e7646`` as the real store records
#: them: 1 blocking, 12 warning, 10 note.
CASE_FINDINGS = [
    ("R-1", "blocking"),
    ("R-2", "warning"),
    ("R-3", "warning"),
    ("R-4", "warning"),
    ("R-5", "note"),
    ("R-6", "note"),
    ("R-7", "note"),
    ("R-8", "warning"),
    ("R-9", "warning"),
    ("R-10", "warning"),
    ("R-11", "warning"),
    ("R-12", "warning"),
    ("R-13", "note"),
    ("R-14", "note"),
    ("R-15", "note"),
    ("R-16", "warning"),
    ("R-17", "warning"),
    ("R-18", "warning"),
    ("R-19", "warning"),
    ("R-20", "note"),
    ("R-21", "note"),
    ("R-22", "note"),
    ("R-23", "note"),
]

#: The resolutions its verify pass recorded. Twelve fixed and **one waived** —
#: the prose census called all thirteen "FIXED".
CASE_RESOLUTIONS = [
    ("R-1", "fixed"),
    ("R-2", "fixed"),
    ("R-3", "fixed"),
    ("R-4", "fixed"),
    ("R-8", "fixed"),
    ("R-9", "fixed"),
    ("R-10", "fixed"),
    ("R-11", "fixed"),
    ("R-12", "waived"),
    ("R-16", "fixed"),
    ("R-17", "fixed"),
    ("R-18", "fixed"),
    ("R-19", "fixed"),
]

CASE_REVIEW = "rev-20260729T185143Z-b35e7646"


def _case_repo(base: Path) -> Path:
    repo = _make_repo(base, "case")
    _review_fact(
        repo, CASE_REVIEW, CASE_FINDINGS, scope="release-readiness", chunk="03"
    )
    for fid, disposition in CASE_RESOLUTIONS:
        _resolution_fact(repo, CASE_REVIEW, fid, disposition)
    return repo


class TestJuly29CaseStudy:
    def test_census_before_dispositions_names_the_ten_undispositioned_notes(
        self, tmp_path
    ):
        """The state of the record as it actually shipped: thirteen findings
        resolved, ten notes answered only in prose."""
        repo = _case_repo(tmp_path)
        report = dispositions.census(evidence.read_facts(repo))
        assert report["summary"]["findings"] == 23
        assert report["summary"]["undispositioned"] == 10
        assert report["summary"]["by_severity"] == {
            "blocking": 1,
            "warning": 12,
            "note": 10,
        }

    def test_waived_finding_is_not_reported_as_fixed(self, tmp_path):
        """Correction the prose never made: R-12 was waived, not fixed."""
        repo = _case_repo(tmp_path)
        report = dispositions.census(evidence.read_facts(repo))
        states = {r["fid"]: r["state"] for r in report["reviews"][0]["rows"]}
        assert states["R-12"] == "waived"
        assert report["summary"]["by_state"]["fixed"] == 12
        assert report["summary"]["by_state"]["waived"] == 1

    def test_recording_the_real_dispositions_reproduces_the_corrected_census(
        self, tmp_path
    ):
        """The census took four hand-written corrections and still disagreed
        with itself: it claimed "ACCEPTED (10 notes)" and then, in its closing
        sentence, "9 accepted notes and one discharged question". Recorded as
        facts, both numbers are derived and cannot drift."""
        repo = _case_repo(tmp_path)
        craft = "craft observation on reviewed, tested, working code"
        for fid in ("R-5", "R-6", "R-14", "R-15", "R-22"):
            assert (
                dispositions.record(
                    repo, CASE_REVIEW, fid, dispositions.ACCEPT, reason=craft
                )["status"]
                == "recorded"
            )
        for fid in ("R-13", "R-21"):
            assert (
                dispositions.record(
                    repo,
                    CASE_REVIEW,
                    fid,
                    dispositions.ACCEPT,
                    reason="larger than this bundle; the ledger conversation is open",
                )["status"]
                == "recorded"
            )
        for fid in ("R-20", "R-23"):
            assert (
                dispositions.record(
                    repo,
                    CASE_REVIEW,
                    fid,
                    dispositions.ACCEPT,
                    reason="repo hygiene for the janitor, not this chunk",
                )["status"]
                == "recorded"
            )
        assert (
            dispositions.record(
                repo,
                CASE_REVIEW,
                "R-7",
                dispositions.ACCEPT,
                reason="norm amendment judged legitimate; provenance attested in-diff",
                owner_ruling="owner confirmed the ruling 2026-07-29",
            )["status"]
            == "recorded"
        )

        report = dispositions.census(evidence.read_facts(repo))
        summary = report["summary"]
        assert summary["undispositioned"] == 0
        assert summary["by_state"]["accepted"] == 10
        # The distinction the prose kept losing: nine plain accepts plus one
        # question discharged by an owner ruling.
        assert summary["owner_ruled"] == 1
        assert summary["by_state"]["accepted"] - summary["owner_ruled"] == 9
        assert summary["conflicts"] == 0

        text = dispositions.render_markdown(report)
        assert "undispositioned" not in text
        assert "accepted (owner ruling)" in text


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCli:
    def test_record_then_render_end_to_end(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")], scope="alpha")

        recorded = _hook(
            repo, "disposition", "rev-1", "R-1", "--accept", "craft observation"
        )
        assert recorded.returncode == 0, recorded.stderr
        assert "recorded ACCEPT" in recorded.stdout

        rendered = _hook(repo, "render-dispositions", "--review", "rev-1")
        assert rendered.returncode == 0, rendered.stderr
        assert "| R-1 | note | accepted | craft observation |" in rendered.stdout

    def test_json_output_is_parseable_and_versioned(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        proc = _hook(repo, "render-dispositions", "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["schema_version"] == dispositions.REPORT_SCHEMA_VERSION
        assert payload["summary"]["undispositioned"] == 1

    def test_refusal_exits_one_and_attributes_the_reason(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        proc = _hook(repo, "disposition", "rev-1", "R-1", "--accept", "nope")
        assert proc.returncode == 1
        assert "BLOCKING" in proc.stderr
        assert "Traceback" not in proc.stderr

    def test_blocking_disposition_warns_that_the_gate_still_blocks(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        proc = _hook(
            repo,
            "disposition",
            "rev-1",
            "R-1",
            "--accept",
            "superseded",
            "--owner-ruling",
            "owner confirmed",
        )
        assert proc.returncode == 0, proc.stderr
        assert "verify-resolutions" in proc.stderr

    def test_usage_errors_exit_two(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        # Missing disposition flag.
        assert _hook(repo, "disposition", "rev-1", "R-1").returncode == 2
        # Two dispositions for one finding.
        assert (
            _hook(
                repo,
                "disposition",
                "rev-1",
                "R-1",
                "--accept",
                "x",
                "--file",
                "ABC-1234",
            ).returncode
            == 2
        )
        # Unknown flag.
        assert (
            _hook(repo, "disposition", "rev-1", "R-1", "--maybe", "x").returncode == 2
        )
        # Exclusive selectors.
        assert (
            _hook(
                repo, "render-dispositions", "--review", "rev-1", "--scope", "alpha"
            ).returncode
            == 2
        )

    def test_unknown_review_renders_nothing_and_exits_one(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        proc = _hook(repo, "render-dispositions", "--review", "rev-typo")
        assert proc.returncode == 1
        assert "rev-typo" in proc.stderr
        assert proc.stdout.strip() == ""

    def test_idempotent_rerun_reports_the_noop(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        first = _hook(repo, "disposition", "rev-1", "R-1", "--accept", "craft")
        assert first.returncode == 0, first.stderr
        again = _hook(repo, "disposition", "rev-1", "R-1", "--accept", "craft")
        assert again.returncode == 0, again.stderr
        assert "no-op" in again.stdout


# ---------------------------------------------------------------------------
# Prior dispositions on the dispatch manifest
# ---------------------------------------------------------------------------


class TestPriorDispositions:
    """Answers already given, put where a REVIEWER can see them.

    Dispositions have been facts for a while, but nothing carried one into a
    dispatch — so a cumulative run after an ``--accept`` handed its reviewers a
    diff and no memory, and they found the same true thing again. Measured on
    one consumer branch: round 9 re-raised six of round 7's findings verbatim,
    several already accepted.
    """

    def test_an_accepted_finding_in_scope_is_carried(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        block = dispositions.prior_dispositions(evidence.read_facts(repo), ["lib/a.py"])
        assert block["matched"] == 1 and block["shown"] == 1
        entry = block["entries"][0]
        assert entry["review_id"] == "rev-1" and entry["fid"] == "R-1"
        assert entry["action"] == dispositions.ACCEPT
        assert entry["reason"] == "by design"
        assert entry["title"] == "finding R-1"
        assert entry["files"] == ["lib/a.py"]

    def test_an_unreadable_store_says_so_instead_of_reading_empty(self, tmp_path):
        """A block with no ``unavailable`` tells every reviewer that nothing was
        dispositioned. For a store this reader could not read, that is false —
        and false in the case where the accepted answers are most likely to be
        re-raised, because they exist and are simply unreachable."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        store = evidence.read_facts(repo)
        store["status"] = "error"
        store["reason"] = "store is a directory"
        block = dispositions.prior_dispositions(store, ["lib/a.py"])
        assert block["entries"] == [] and block["matched"] == 0
        assert "store is a directory" in block["unavailable"]

    def test_a_schema_ahead_store_says_so_instead_of_reading_empty(self, tmp_path):
        """Same reason, the other degraded state: records a newer plugin wrote
        are filtered out of ``facts``, so the dispositions they carry are
        invisible — which is not the same fact as their absence."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        with open(evidence.store_path(repo), "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": 99,
                        "kind": "disposition",
                        "id": "rev-future",
                        "ts": "2030-01-01T00:00:00Z",
                        "body": {},
                    }
                )
                + "\n"
            )
        block = dispositions.prior_dispositions(evidence.read_facts(repo), ["lib/a.py"])
        assert block["entries"] == [] and block["matched"] == 0
        assert "newer schema" in block["unavailable"]

    def test_a_healthy_store_carries_no_unavailable_key(self, tmp_path):
        # The control for the two above: the key's PRESENCE is the whole signal,
        # so a block that always carried it would say nothing.
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        block = dispositions.prior_dispositions(evidence.read_facts(repo), ["lib/a.py"])
        assert "unavailable" not in block

    def test_a_disposition_about_other_files_is_not_carried(self, tmp_path):
        # The scope rule is what keeps a store shared by every worktree of a
        # clone (652 dispositions on this repo) from becoming a second document
        # prepended to every review.
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/elsewhere.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        block = dispositions.prior_dispositions(evidence.read_facts(repo), ["lib/a.py"])
        assert block["entries"] == [] and block["matched"] == 0

    def test_only_the_live_answer_is_carried(self, tmp_path):
        # Re-disposition APPENDS. Showing both would hand a reviewer two
        # contradictory answers about one finding.
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="first answer")
        dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="owner/repo#1"
        )
        block = dispositions.prior_dispositions(evidence.read_facts(repo), ["lib/a.py"])
        assert block["matched"] == 1
        assert block["entries"][0]["action"] == dispositions.FILE
        assert block["entries"][0]["backlog_id"] == "owner/repo#1"

    def test_a_disposition_whose_finding_is_gone_is_skipped(self, tmp_path):
        # A hand-edited store can hold a disposition with nothing to join to;
        # there is no title to show and nothing a reviewer could match against.
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        store = evidence.read_facts(repo)
        store["facts"] = [f for f in store["facts"] if f.get("kind") != "review"]
        assert dispositions.prior_dispositions(store, ["lib/a.py"])["entries"] == []

    def test_truncation_is_reported_never_silent(self, tmp_path):
        repo = _make_repo(tmp_path)
        pairs = [(f"R-{i}", "note") for i in range(1, 8)]
        _review_fact(repo, "rev-1", pairs, files=["lib/a.py"])
        for fid, _ in pairs:
            dispositions.record(repo, "rev-1", fid, dispositions.ACCEPT, reason="ok")
        block = dispositions.prior_dispositions(
            evidence.read_facts(repo), ["lib/a.py"], limit=3
        )
        assert block["matched"] == 7
        assert block["shown"] == 3
        assert block["truncated"] == 4
        # Newest-first, so truncation drops the oldest answers, not the live ones.
        assert block["entries"][0]["fid"] == "R-7"

    def test_an_empty_scope_carries_everything(self, tmp_path):
        # A review whose files_changed is empty (a same-tree verify pass) must
        # not silently mean "no priors apply".
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=["lib/a.py"])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        assert dispositions.prior_dispositions(evidence.read_facts(repo), [])["matched"] == 1

    def test_a_finding_with_no_file_attribution_is_carried_only_unscoped(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")], files=[])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design")
        store = evidence.read_facts(repo)
        assert dispositions.prior_dispositions(store, ["lib/a.py"])["matched"] == 0
        assert dispositions.prior_dispositions(store, [])["matched"] == 1


class TestFindingTitleAccessor:
    """One finding, three key names, one place that knows it.

    The same sentence is `name` in a reviewer's partial, `title` once
    consolidation writes the review fact, and `summary` again in the derived
    `.critic-findings.json`. Five readers each re-derived that chain by hand and
    the only thing carrying the contract was a comment in each one pointing at
    the last — a countdown, not a redundancy: the reader that forgets emits
    `title: null` into the record a human checks a disposition against, which
    has already happened once.
    """

    def test_each_layers_key_resolves(self):
        for key in ("title", "summary", "name"):
            assert evidence.finding_title({key: "the sentence"}) == "the sentence", (
                f"a finding carrying only {key!r} — the shape one whole layer "
                "emits — no longer resolves, so that layer reads as untitled"
            )

    def test_precedence_is_fact_then_cache_then_partial(self):
        """Not alphabetical, and not arbitrary. A finding that carries more than
        one is one that has been through a projection, and the later layer is
        the one a human was shown.
        """
        assert evidence.finding_title(
            {"title": "fact", "summary": "cache", "name": "partial"}
        ) == "fact"
        assert evidence.finding_title({"summary": "cache", "name": "partial"}) == "cache"

    def test_blank_and_missing_both_fall_through(self):
        """Presence is not a title. `""` and `"   "` reached the old chains as
        falsey and fell through; a `key in finding` test would not, and would
        put an empty string where a caller asked for `<no title>`.
        """
        assert evidence.finding_title({}) == ""
        assert evidence.finding_title({"title": "", "summary": "cache"}) == "cache"
        assert evidence.finding_title({"title": "   ", "name": "partial"}) == "partial"
        assert evidence.finding_title({"title": None}, "<no title>") == "<no title>"

    def test_a_non_string_does_not_reach_the_caller(self):
        """The chains this replaces used `or`, so a truthy non-string (a dict a
        malformed partial might carry) propagated into `len()` and `str()` at
        different call sites with different results. It is skipped now.
        """
        assert evidence.finding_title({"title": {"nested": 1}, "summary": "cache"}) == "cache"
        assert evidence.finding_title({"title": 42}, "fallback") == "fallback"

    def test_no_reader_re_derives_the_chain(self):
        """The property that closes the class — asserted over the source, because
        the defect is a SIXTH reader being added, and no behavioural test can see
        one that does not exist yet.

        **What turns this red, and what does not.** It matches a single-line
        `x.get("a") or y.get("b")` pair — the idiom that actually existed, five
        times. A chain a formatter wrapped across lines, or a three-key one split
        at a paren, slips it. That is a real limit and it is stated rather than
        implied: the scan raises the cost of re-deriving the chain, it does not
        make it impossible, and a reader who believes otherwise will not look.
        """
        import re as _re
        offenders = []
        for path in sorted((ROOT / "lib").rglob("*.py")):
            src = path.read_text(encoding="utf-8")
            for num, line in enumerate(src.splitlines(), 1):
                if _re.search(r'get\("(title|summary|name)"\)\s+or\s+\w+\.get\("(title|summary|name)"\)', line):
                    offenders.append(f"{path.name}:{num}: {line.strip()}")
        assert offenders == [], (
            "a reader re-derives the finding-title alias chain instead of "
            "calling `evidence.finding_title`:\n  " + "\n  ".join(offenders)
        )


# ---------------------------------------------------------------------------
# --fixed: the free fix becomes recordable, and only where it was free
# ---------------------------------------------------------------------------


class TestFixedDisposition:
    """A fix confined to non-judgeable paths buys no round, so no verify pass
    runs and no resolution fact is written — and the census then reported it
    ``undispositioned`` forever. That made the cheapest correct action the only
    one the record could not see."""

    def test_a_free_path_set_records(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])

        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FIXED,
            paths=[".prawduct/change-log.md", "docs/notes.md"],
        )
        assert result["status"] == "recorded", result
        rows = dispositions.census(evidence.read_facts(repo))["reviews"][0]["rows"]
        assert rows[0]["state"] == dispositions.STATE_FIXED_FREE
        assert rows[0]["paths"] == [".prawduct/change-log.md", "docs/notes.md"]

    def test_the_state_is_not_plain_fixed(self, tmp_path):
        """Both say the defect is gone; only one says a reviewer looked.

        Collapsing them would let a census claim a review that never ran, which
        is the class of misdescription the census exists to retire.
        """
        assert dispositions.STATE_FIXED_FREE != dispositions.STATE_FIXED

    def test_a_judgeable_path_is_refused(self, tmp_path):
        """The guard that keeps this from being a way past a gate.

        A judgeable edit re-opens coverage, so the round is already bought by
        the edit itself — recording it here would claim a review nobody ran.
        """
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])

        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FIXED,
            paths=[".prawduct/change-log.md", "lib/gates.py"],
        )
        assert result["status"] == "error", result
        assert "lib/gates.py" in result["reason"]
        assert "verify-resolutions" in result["reason"]
        assert not [
            f for f in evidence.read_facts(repo)["facts"]
            if f.get("kind") == KIND_DISPOSITION
        ], "a judgeable fix recorded without a review"

    def test_governance_protected_prose_counts_as_judgeable(self, tmp_path):
        """The predicate is the one that prices the edit, not a private notion
        of 'docs' — fork-skill prose and a subagent's own prompt are behaviour."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        for path in ("skills/critic/SKILL.md", "plugin/agents/critic-reviewer.md"):
            result = dispositions.record(
                repo, "rev-1", "R-1", dispositions.FIXED, paths=[path]
            )
            assert result["status"] == "error", (path, result)

    def test_an_empty_path_set_is_refused(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        result = dispositions.record(repo, "rev-1", "R-1", dispositions.FIXED, paths=[])
        assert result["status"] == "error" and "--fixed" in result["reason"]

    def test_blocking_is_refused_outright(self, tmp_path):
        """No owner-ruling escape, unlike ACCEPT: the real route exists and is
        cheap. `begin_review`'s free-interval refusal deliberately lets a verify
        pass through while findings are outstanding, so a blocking finding on a
        free interval is always clearable — and recording it here would leave
        the census saying `fixed` while the gate says `blocked`."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking")])
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FIXED, paths=[".prawduct/backlog.md"],
        )
        assert result["status"] == "error"
        assert "verify-resolutions" in result["reason"]

    def test_paths_are_refused_on_the_other_actions(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        result = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="by design",
            paths=[".prawduct/backlog.md"],
        )
        assert result["status"] == "error"

    def test_the_cli_parses_a_comma_separated_set(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        proc = _hook(
            repo, "disposition", "rev-1", "R-1",
            "--fixed", ".prawduct/change-log.md,.prawduct/learnings.md",
        )
        assert proc.returncode == 0, proc.stderr
        rendered = _hook(repo, "render-dispositions", "--review", "rev-1")
        assert "fixed in" in rendered.stdout
        assert dispositions.STATE_FIXED_FREE in rendered.stdout

    def test_the_cli_refuses_a_judgeable_set_at_exit_1(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        proc = _hook(repo, "disposition", "rev-1", "R-1", "--fixed", "lib/gates.py")
        assert proc.returncode == 1, (proc.stdout, proc.stderr)


# ---------------------------------------------------------------------------
# Auto-accept at budget exhaustion
# ---------------------------------------------------------------------------


class TestAutoAccept:
    """Exhaustion has to ANSWER the outstanding findings — the loop that would
    have dispositioned them is the loop being ended."""

    def test_it_accepts_warnings_and_notes(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning"), ("R-2", "note")])

        swept = dispositions.auto_accept(repo, ["rev-1"], reason="budget spent")
        # ``unsent`` counts the sweep's records whose git note failed. A note
        # that was written, or skipped because the kind does not travel, is
        # not one.
        assert swept == {
            "status": "swept", "accepted": 2, "skipped_blocking": 0, "failed": [],
            "unsent": 0,
        }
        rows = {
            row["fid"]: row
            for row in dispositions.census(evidence.read_facts(repo))["reviews"][0]["rows"]
        }
        assert rows["R-1"]["state"] == dispositions.STATE_ACCEPTED
        assert rows["R-1"]["reason"] == "budget spent"

    def test_a_blocking_finding_is_never_swept(self, tmp_path):
        """The load-bearing safety property: a budget may end a review loop and
        may never open a gate. Guarded twice — filtered here, and independently
        refused by `record`, which needs an owner ruling no caller supplies."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "blocking"), ("R-2", "warning")])

        swept = dispositions.auto_accept(repo, ["rev-1"], reason="budget spent")
        assert swept["accepted"] == 1 and swept["skipped_blocking"] == 1

        facts = [
            f for f in evidence.read_facts(repo)["facts"]
            if f.get("kind") == KIND_DISPOSITION
        ]
        assert [f["body"]["finding"]["fid"] for f in facts] == ["R-2"], (
            "a BLOCKING finding was auto-accepted"
        )

    def test_it_leaves_already_answered_findings_alone(self, tmp_path):
        """Re-disposition appends, so a blind sweep would bury a real answer
        under a generic one and make the budget the last word on every finding
        it touched."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning"), ("R-2", "note"), ("R-3", "note")])
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="mine")
        _resolution_fact(repo, "rev-1", "R-2", "fixed")

        swept = dispositions.auto_accept(repo, ["rev-1"], reason="budget spent")
        assert swept["accepted"] == 1
        rows = {
            row["fid"]: row
            for row in dispositions.census(evidence.read_facts(repo))["reviews"][0]["rows"]
        }
        assert rows["R-1"]["reason"] == "mine"
        assert rows["R-2"]["state"] == dispositions.STATE_FIXED

    def test_reviews_outside_the_set_are_untouched(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "warning")])
        _review_fact(repo, "rev-2", [("R-1", "warning")])

        dispositions.auto_accept(repo, ["rev-1"], reason="budget spent")
        rows = dispositions.census(evidence.read_facts(repo), review_id="rev-2")[
            "reviews"][0]["rows"]
        assert rows[0]["state"] == dispositions.STATE_OPEN


# ---------------------------------------------------------------------------
# Observations — the demoted items a builder can now answer on the record
# ---------------------------------------------------------------------------


def _review_fact_with_observations(
    repo: Path,
    review_id: str,
    observations: "list[str]",
    *,
    findings: "list[tuple[str, str]] | None" = None,
) -> None:
    """A review fact carrying ``observations`` beside its findings.

    Titles in, ``O-n`` ids assigned the way ``merge_observations`` assigns
    them — the fixture mirrors the writer rather than inventing a shape, so a
    change to the writer's id scheme fails these tests instead of passing them
    against a fossil."""
    body = {
        "base_tree": "a" * 40,
        "head_tree": "b" * 40,
        "mode": "verify-resolutions",
        "findings": [
            {
                "fid": fid,
                "severity": severity,
                "goal": "Nothing Is Broken",
                "title": f"finding {fid}",
                "recommendation": "do the thing",
            }
            for fid, severity in (findings or [])
        ],
        "observations": [
            {
                "oid": f"O-{idx}",
                "goal": "Nothing Is Unintended",
                "title": title,
                "recommendation": "consider it",
            }
            for idx, title in enumerate(observations, start=1)
        ],
    }
    result = evidence.append_fact(repo, "review", review_id, body)
    assert result["status"] == "appended", result


class TestAnObservationCanBeAccepted:
    """The defect this closes: a demoted observation could be discharged by
    FIXING it — which moves the tree and buys a review round — or by saying
    nothing, which loses the reasoning. There was no third answer."""

    def test_an_observation_accepts_with_a_reason(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["a name I'd have picked differently"])

        result = dispositions.record(
            repo, "rev-1", "O-1", dispositions.ACCEPT, reason="the name is fine"
        )
        assert result["status"] == "recorded", result

        store = evidence.read_facts(repo)
        fact = evidence.facts_of_kind(store, KIND_DISPOSITION)[0]
        assert fact["body"]["finding"] == {"review_id": "rev-1", "fid": "O-1"}
        assert fact["body"]["reason"] == "the name is fine"

    def test_an_unrecorded_observation_id_is_refused(self, tmp_path):
        """The join stays validated — widening the id DOMAIN is not widening it
        to anything a caller cares to type."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["only one"])
        result = dispositions.record(
            repo, "rev-1", "O-9", dispositions.ACCEPT, reason="no such thing"
        )
        assert result["status"] == "error"
        assert "O-9" in result["reason"]

    def test_the_two_id_namespaces_do_not_shadow_each_other(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(
            repo, "rev-1", ["an observation"], findings=[("R-1", "warning")]
        )
        assert (
            dispositions.record(
                repo, "rev-1", "R-1", dispositions.ACCEPT, reason="finding"
            )["status"]
            == "recorded"
        )
        assert (
            dispositions.record(
                repo, "rev-1", "O-1", dispositions.ACCEPT, reason="observation"
            )["status"]
            == "recorded"
        )
        rows = dispositions.census(evidence.read_facts(repo))["reviews"][0]
        assert rows["rows"][0]["reason"] == "finding"
        assert rows["observations"][0]["reason"] == "observation"


class TestTheCLITakesAnObservationId:
    """`api-contract.md` states the id argument takes a finding's `fid` **or**
    an observation's `oid`, with the flags meaning exactly what they mean for a
    finding. That is a documented contract, so it is exercised through the
    process boundary rather than through :func:`dispositions.record`."""

    def test_accept_through_the_cli(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["a name I would not pick"])
        result = _hook(repo, "disposition", "rev-1", "O-1", "--accept",
                       "idiomatic here; renaming buys a round for nothing")
        assert result.returncode == 0, result.stderr
        assert "O-1" in result.stdout and "ACCEPT" in result.stdout
        # No BLOCKING nag on stderr: an observation has no severity to be
        # blocking, and printing the gate warning would tell the builder the
        # gate is waiting on something it cannot see.
        assert "BLOCKING" not in result.stderr

    def test_file_through_the_cli(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["the docstring lags the signature"])
        result = _hook(repo, "disposition", "rev-1", "O-1", "--file", "DOC-1234")
        assert result.returncode == 0, result.stderr
        row = dispositions.census(evidence.read_facts(repo))[
            "reviews"][0]["observations"][0]
        assert row["state"] == dispositions.STATE_FILED
        assert row["backlog_id"] == "DOC-1234"

    def test_a_free_fix_records_against_an_observation(self, tmp_path):
        """`--fixed` keeps its guard: the paths must buy no round. An
        observation does not exempt a judgeable path, because the guard is
        about what the EDIT costs, never about what the finding was."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["prose could be tighter"])
        ok = _hook(repo, "disposition", "rev-1", "O-1", "--fixed", "README.md")
        assert ok.returncode == 0, ok.stderr
        row = dispositions.census(evidence.read_facts(repo))[
            "reviews"][0]["observations"][0]
        assert row["state"] == dispositions.STATE_FIXED_FREE

        _review_fact_with_observations(repo, "rev-2", ["same shape, judgeable path"])
        refused = _hook(repo, "disposition", "rev-2", "O-1", "--fixed", "code.py")
        assert refused.returncode == 1
        assert "code.py" in refused.stderr

    def test_an_unknown_id_is_refused_through_the_cli(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["only one"])
        result = _hook(repo, "disposition", "rev-1", "O-9", "--accept", "nope")
        assert result.returncode == 1
        assert "O-9" in result.stderr


class TestAnAcceptedObservationGatesNothing:
    """The whole safety argument for this chunk, asserted rather than assumed.

    An accepted observation gates exactly what it gated before, which is
    nothing — and the reason is structural: observations live outside
    ``findings``, which is the only array the coverage algebra walks."""

    def test_no_gate_reads_an_observation(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(
            repo, "rev-1", ["something worth saying"], findings=[("R-1", "blocking")]
        )
        dispositions.record(
            repo, "rev-1", "O-1", dispositions.ACCEPT, reason="reads fine to me"
        )

        store = evidence.read_facts(repo)
        review = evidence.facts_of_kind(store, "review")[0]
        resolved = coverage_algebra.resolution_index(store["facts"])
        unresolved = coverage_algebra.unresolved_blocking(review, resolved)
        # The blocking finding is still blocking, and the observation never
        # appears in a verdict's input at all.
        assert [f["fid"] for f in unresolved] == ["R-1"]
        assert not any(
            f.get("oid") or f.get("fid", "").startswith("O-") for f in unresolved
        )

    def test_an_observation_never_enters_the_findings_index(self, tmp_path):
        """The index the resolution existence check reads. If an observation
        reached it, a resolution could target one — and a resolution is the one
        reviewer output that weakens a gate."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["not a finding"])
        store = evidence.read_facts(repo)
        assert evidence.findings_index(store) == {}
        assert list(evidence.observations_index(store)) == [("rev-1", "O-1")]

    def test_an_accepted_observation_is_not_a_resolution(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["x"])
        dispositions.record(repo, "rev-1", "O-1", dispositions.ACCEPT, reason="fine")
        store = evidence.read_facts(repo)
        assert coverage_algebra.resolution_index(store["facts"]) == set()


class TestTheCensusReadsObservations:
    def test_an_accepted_observation_is_not_undispositioned(self, tmp_path):
        """The census correctness deliverable: the acceptance must show."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["tighten this prose"])
        dispositions.record(
            repo, "rev-1", "O-1", dispositions.ACCEPT, reason="prose is fine"
        )
        report = dispositions.census(evidence.read_facts(repo))
        row = report["reviews"][0]["observations"][0]
        assert row["state"] == dispositions.STATE_ACCEPTED
        assert row["state"] != dispositions.STATE_OPEN
        assert report["summary"]["undispositioned"] == 0
        assert report["summary"]["observations"] == 1
        assert report["summary"]["observations_answered"] == 1

    def test_an_unanswered_observation_is_noted_never_a_debt(self, tmp_path):
        """An observation is explicitly not work the record demands. Counting
        an unanswered one as `undispositioned` would rebuild the obligation the
        verify-mode demotion exists to remove."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["one", "two"])
        report = dispositions.census(evidence.read_facts(repo))
        assert [r["state"] for r in report["reviews"][0]["observations"]] == [
            dispositions.STATE_NOTED,
            dispositions.STATE_NOTED,
        ]
        assert report["summary"]["undispositioned"] == 0
        assert report["summary"]["observations_answered"] == 0

    def test_observations_do_not_inflate_the_findings_tallies(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(
            repo, "rev-1", ["a", "b", "c"], findings=[("R-1", "warning")]
        )
        summary = dispositions.census(evidence.read_facts(repo))["summary"]
        assert summary["findings"] == 1
        assert summary["by_severity"] == {"warning": 1}
        assert summary["observations"] == 3

    def test_the_markdown_reports_both_without_summing_them(self, tmp_path):
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(
            repo, "rev-1", ["tighten this prose"], findings=[("R-1", "note")]
        )
        dispositions.record(
            repo, "rev-1", "O-1", dispositions.ACCEPT, reason="prose is fine"
        )
        md = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "1 finding" in md
        assert "1 observation demoted" in md
        assert "prose is fine" in md

    def test_a_review_that_demoted_everything_still_renders_them(self, tmp_path):
        """The case this block most needs to reach: a verify pass that demoted
        all it saw records zero findings, so it takes the clean-review branch."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["the only thing I found"])
        md = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "_No findings._" in md
        assert "the only thing I found" in md

    def test_the_clean_pass_summary_still_reports_the_demotion(self, tmp_path):
        """The clean-pass branch returns early, and it is the branch a verify
        pass that demoted everything lands on — so a tally appended after it
        would be missing in exactly the case it exists for."""
        repo = _make_repo(tmp_path)
        _review_fact_with_observations(repo, "rev-1", ["one", "two"])
        dispositions.record(repo, "rev-1", "O-1", dispositions.ACCEPT, reason="fine")
        md = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "**No findings** — a clean pass." in md
        assert "2 observations demoted" in md
        assert "1 answered" in md

    def test_a_review_with_no_observations_renders_no_block(self, tmp_path):
        """Most reviews demote nothing — only `verify-resolutions` demotes at
        all — so a heading over an empty table would be on nearly every census."""
        repo = _make_repo(tmp_path)
        _review_fact(repo, "rev-1", [("R-1", "note")])
        md = dispositions.render_markdown(
            dispositions.census(evidence.read_facts(repo))
        )
        assert "Observations" not in md


# ---------------------------------------------------------------------------
# A bare render composes the BRANCH's reviews, not the newest one (#334)
# ---------------------------------------------------------------------------


def _feature_branch(base: Path) -> "tuple[Path, str, str, str]":
    """``main`` with one commit, ``feature`` with two on top. Returns
    ``(repo, merge_base, first, second)`` — the commits a review anchors on."""
    repo = base / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    merge_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feature")
    commits = []
    for i in (1, 2):
        (repo / f"f{i}.py").write_text(f"y = {i}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", f"f{i}")
        commits.append(_git(repo, "rev-parse", "HEAD"))
    return repo, merge_base, commits[0], commits[1]


class TestABareRenderComposesTheBranch:
    """`render-dispositions` with no selector rendered the NEWEST review only,
    so an earlier round's undispositioned findings were invisible while the
    census read clean — observed live, R-10..R-14 never dispositioned and three
    still unfixed at head. It now renders the branch's review set
    (`coverage.branch_review_ids`), the one the round budget and the verify
    roll-call compose over."""

    def _two_rounds(self, tmp_path):
        repo, merge_base, first, second = _feature_branch(tmp_path)
        _review_fact(
            repo, "rev-old", [("R-1", "warning"), ("R-2", "blocking")],
            head_commit=first,
        )
        _review_fact(repo, "rev-new", [("R-1", "note")], head_commit=second)
        return repo, merge_base

    def test_both_rounds_are_listed_and_counted(self, tmp_path):
        repo, _ = self._two_rounds(tmp_path)

        proc = _hook(repo, "render-dispositions", "--json")

        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert [r["review_id"] for r in payload["reviews"]] == ["rev-old", "rev-new"]
        summary = payload["summary"]
        assert summary["findings"] == 3
        assert summary["undispositioned"] == 3
        assert summary["open_blocking"] == 1
        assert summary["undispositioned_warning"] == 1
        # No fallback was taken, so nothing is said about one.
        assert "newest review only" not in proc.stderr

    def test_the_markdown_census_names_the_earlier_round(self, tmp_path):
        repo, _ = self._two_rounds(tmp_path)

        proc = _hook(repo, "render-dispositions")

        assert proc.returncode == 0, proc.stderr
        assert "**rev-old**" in proc.stdout and "**rev-new**" in proc.stdout
        assert "| R-2 | blocking | undispositioned |" in proc.stdout

    def test_a_review_off_this_branch_is_not_swept_in(self, tmp_path):
        """The store is clone-wide; the set is bounded by lineage. A review
        anchored at the merge base (a sibling's, or the base branch's) is not
        this branch's — the census would otherwise report debt it does not owe."""
        repo, merge_base = self._two_rounds(tmp_path)
        _review_fact(repo, "rev-elsewhere", [("R-9", "blocking")], head_commit=merge_base)

        payload = json.loads(_hook(repo, "render-dispositions", "--json").stdout)

        assert [r["review_id"] for r in payload["reviews"]] == ["rev-old", "rev-new"]
        assert payload["summary"]["open_blocking"] == 1

    def test_an_explicit_selector_is_unchanged(self, tmp_path):
        repo, _ = self._two_rounds(tmp_path)

        payload = json.loads(
            _hook(repo, "render-dispositions", "--review", "rev-new", "--json").stdout
        )

        assert [r["review_id"] for r in payload["reviews"]] == ["rev-new"]

    def test_with_no_branch_set_it_falls_back_to_the_newest_and_says_so(self, tmp_path):
        """No review anchors on this branch's lineage, so there is no set to
        render. The newest review stands in — and ONE stderr line says so,
        because a newest-review census silently standing in for the branch is
        the defect this replaces."""
        repo, _, _, _ = _feature_branch(tmp_path)
        _review_fact(repo, "rev-a", [("R-1", "warning")])
        _review_fact(repo, "rev-b", [("R-1", "note")])

        proc = _hook(repo, "render-dispositions", "--json")

        assert proc.returncode == 0, proc.stderr
        assert [r["review_id"] for r in json.loads(proc.stdout)["reviews"]] == ["rev-b"]
        said = [ln for ln in proc.stderr.splitlines() if "newest review only" in ln]
        assert len(said) == 1, proc.stderr
        assert "no review anchors on this branch" in said[0]
