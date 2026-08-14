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

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import coverage_algebra, dispositions, evidence  # noqa: E402

KIND_DISPOSITION = dispositions.KIND


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
) -> None:
    """Append a review fact carrying ``(fid, severity)`` findings.

    ``files`` sets every finding's attribution — the axis
    ``prior_dispositions`` scopes on, so a test about it must be able to set
    it."""
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

        store = evidence.read_facts(repo)
        assert len(dispositions.disposition_history(store, "rev-1", "R-1")) == 2

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
        dispositions.record(repo, "rev-1", "R-1", dispositions.ACCEPT, reason="one")
        second = dispositions.record(
            repo, "rev-1", "R-1", dispositions.FILE, backlog_id="ABC-1234"
        )

        # Prune the FIRST disposition, shortening the history under the store.
        path = evidence.store_path(repo)
        kept = [
            line
            for line in path.read_text().splitlines()
            if '"disp:rev-1:R-1:1"' not in line
        ]
        path.write_text("\n".join(kept) + "\n")

        third = dispositions.record(
            repo, "rev-1", "R-1", dispositions.ACCEPT, reason="three"
        )
        assert third["status"] == "recorded", third
        assert third["id"] != second["id"], "recycled a live id — answer would be lost"

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
# Prior dispositions on the dispatch manifest (tactical-efficiency Chunk 03)
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
