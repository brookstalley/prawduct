"""Disposition facts travel between clones on the notes transport (#1207).

A finding's answer (ACCEPT, FILE, a free fix) is about the finding, not the
clone that recorded it. Left behind, every other clone reports the finding
unanswered, re-raises it to its reviewers and sweeps it again. So
``disposition`` is a transported kind: it hangs on the note of the review whose
finding it answers, ``evidence sync`` reconciles any that never attached, and
``ingest`` takes it in.

What must hold once it travels:

* every clone that synced the branch reads the same answer, and the same winner
  when a finding has several (the winner is ``dispositions``' to pick);
* a disposition hangs on its review's anchor, not on HEAD, whichever branch it
  was written from;
* an id two clones minted for different answers before ids carried a body tag
  is reported, since only a new answer makes them agree;
* nothing that travels lifts a gate.

Fixtures are real git, a bare origin and clones of it, as in
``test_evidence_sync.py``: every claim is about what reaches the other clone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import (  # noqa: E402
    coverage_algebra,
    critic_consolidate,
    dispositions,
    evidence,
    evidence_notes,
    evidence_sync,
    plan_status,
    stats,
    telemetry,
)

NOTES_REF = "refs/notes/prawduct"
TRACKING_REF = "refs/notes/origin/prawduct"
SCOPE = "unit"
#: The transported set before dispositions joined it: what a plugin from
#: before #1207 filters on.
OLD_TRANSPORTED_KINDS = frozenset({"review", "resolution", "chunk-imported", "chunk-retracted"})
DIVERGED = "disposition(s) share an id with a different answer recorded here"


# ---------------------------------------------------------------------------
# Fixtures: real git, sterile env (mirrors test_evidence_sync.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sterile_git(monkeypatch, tmp_path):
    home = tmp_path / "_home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "T")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "t@example.com")
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("PRAWDUCT_ALLOW_EPHEMERAL_WRITES", raising=False)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=check, timeout=20,
    )
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, text: str, subject: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    """A bare origin holding `main` and `feature/unit` (one commit past main)."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _commit(seed, ".gitignore", ".prawduct/\n", "seed")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")
    _git(seed, "checkout", "-q", "-b", "feature/unit")
    _commit(seed, "src/app.py", "x = 1\n", "work")
    _git(seed, "push", "-q", "origin", "feature/unit")
    return origin


def _clone(tmp_path: Path, origin: Path, name: str) -> Path:
    repo = tmp_path / name
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "checkout", "-q", "feature/unit")
    return repo.resolve()


@pytest.fixture
def a(tmp_path: Path, origin: Path) -> Path:
    return _clone(tmp_path, origin, "a")


@pytest.fixture
def b(tmp_path: Path, origin: Path) -> Path:
    return _clone(tmp_path, origin, "b")


def _finding(fid: str, severity: str, **extra) -> dict:
    return {"fid": fid, "severity": severity, "goal": "Nothing Is Broken",
            "title": f"finding {fid}", "recommendation": "do the thing",
            "files": ["src/app.py"], **extra}


def _review(repo: Path, review_id: str, findings: "list[dict]", *,
            anchor: "str | None" = None) -> str:
    """A review fact over main → ``anchor`` (HEAD by default) carrying
    ``findings``, attached to its note as consolidation attaches it."""
    anchor = anchor or _git(repo, "rev-parse", "HEAD")
    body = {
        "mode": "final", "scope": SCOPE, "chunk": "01",
        "base_tree": _git(repo, "rev-parse", "main^{tree}"),
        "head_tree": _git(repo, "rev-parse", f"{anchor}^{{tree}}"),
        "head_commit": anchor,
        "files_changed": ["src/app.py"], "files_reviewed": ["src/app.py"],
        "findings": findings,
    }
    appended = evidence.append_fact(repo, "review", review_id, body)
    assert appended["status"] == "appended", appended
    assert evidence_notes.attach(repo, appended["envelope"], anchor)["status"] == "attached"
    return anchor


def _record(repo: Path, fid: str, action: str, review_id: str = "rev-1", **kw) -> dict:
    result = dispositions.record(repo, review_id, fid, action, **kw)
    assert result["status"] == "recorded", result
    return result


def _raw_disposition(repo: Path, fact_id: str, fid: str, *, reason: str,
                     review_id: str = "rev-1") -> dict:
    """A disposition appended to the store and never attached: the state a
    failed attach leaves, or a disposition recorded before the kind travelled.
    The body is the one ``record`` writes for an ACCEPT."""
    body = {"finding": {"review_id": review_id, "fid": fid}, "action": dispositions.ACCEPT,
            "reason": reason, "backlog_id": None, "owner_ruling": None, "paths": None}
    appended = evidence.append_fact(repo, dispositions.KIND, fact_id, body)
    assert appended["status"] == "appended", appended
    return appended["envelope"]


def _sync(repo: Path, *, push: bool = True) -> dict:
    result = evidence_sync.sync(repo, push=push)
    assert result["status"] == "ok", result
    return result


def _fetch_and_ingest(repo: Path) -> dict:
    """A plain fetch of the remote's notes into the tracking ref, then ingest:
    the receiving half without a merge, reconcile or push."""
    _git(repo, "fetch", "-q", "origin", f"+{NOTES_REF}:{TRACKING_REF}")
    result = evidence_notes.ingest(repo)
    assert result["status"] == "ok", result
    return result


def _store(repo: Path) -> dict:
    store = evidence.read_facts(repo)
    assert store["status"] != "error", store
    return store


def _states(repo: Path, review_id: str = "rev-1") -> dict[str, str]:
    report = dispositions.census(_store(repo), review_id=review_id)
    assert report["status"] == "ok", report
    return {row["fid"]: row["state"] for row in report["reviews"][0]["rows"]}


def _winner(repo: Path, fid: str, review_id: str = "rev-1") -> dict:
    return dispositions.disposition_index(_store(repo))[(review_id, fid)]


def _note_keys(repo: Path, commit: str) -> set[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "notes", "--ref", NOTES_REF, "show", commit],
        cwd=str(repo), capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return set()
    return {(r["kind"], r["id"]) for r in map(json.loads, filter(str.strip, proc.stdout.splitlines()))}


def _disposition_keys(repo: Path) -> set[str]:
    return {f["id"] for f in evidence.facts_of_kind(_store(repo), dispositions.KIND)}


# ---------------------------------------------------------------------------
# T1, T2, T13: an answer given in one clone reads the same in the other
# ---------------------------------------------------------------------------


class TestAnAnswerReachesTheOtherClone:
    def test_accept_file_and_fixed_recorded_in_a_read_the_same_in_b(self, a, b):
        _review(a, "rev-1", [_finding("R-1", "warning"), _finding("R-2", "warning"),
                             _finding("R-3", "note")])
        _record(a, "R-1", dispositions.ACCEPT, reason="the cost outweighs it")
        _record(a, "R-2", dispositions.FILE, backlog_id="ABC-1234")
        _record(a, "R-3", dispositions.FIXED, paths=["docs/notes.md"])
        _sync(a)

        # Control: before B reads the notes it holds nothing of A's.
        assert _disposition_keys(b) == set()
        _fetch_and_ingest(b)

        assert _states(b) == {
            "R-1": dispositions.STATE_ACCEPTED,
            "R-2": dispositions.STATE_FILED,
            "R-3": dispositions.STATE_FIXED_FREE,
        }
        assert _states(b) == _states(a)

    def test_b_hands_its_reviewers_a_s_accept(self, a, b):
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _record(a, "R-1", dispositions.ACCEPT, reason="the cost outweighs it")
        _sync(a)
        _fetch_and_ingest(b)

        block = dispositions.prior_dispositions(_store(b), ["src/app.py"], scope=SCOPE)
        assert "unavailable" not in block, block
        assert [(e["fid"], e["action"], e["reason"]) for e in block["entries"]] == [
            ("R-1", dispositions.ACCEPT, "the cost outweighs it"),
        ]

    def test_a_budget_sweep_in_b_skips_a_finding_a_answered(self, a, b):
        _review(a, "rev-1", [_finding("R-1", "warning"), _finding("R-2", "warning")])
        _record(a, "R-1", dispositions.ACCEPT, reason="answered by hand in A")
        _sync(a)
        _sync(b, push=False)

        swept = dispositions.auto_accept(b, ["rev-1"], reason="round budget exhausted")
        assert (swept["status"], swept["accepted"]) == ("swept", 1), swept
        assert _winner(b, "R-1")["body"]["reason"] == "answered by hand in A"
        assert _winner(b, "R-2")["body"]["reason"] == "round budget exhausted"


# ---------------------------------------------------------------------------
# T4, T5: every clone picks the same winner (dispositions' D4/D5)
# ---------------------------------------------------------------------------


class TestEveryCloneAgreesOnTheWinner:
    def test_two_clones_answering_one_finding_differently_converge(self, a, b):
        """A and B answer R-1 without having seen each other's answer. After
        syncing both ways each clone holds both answers and both pick the same
        winner. Who wins a genuine conflict is arbitrary; that the clones
        agree is the requirement."""
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _sync(a)
        _sync(b, push=False)  # B holds the review, so it can answer it
        _record(a, "R-1", dispositions.ACCEPT, reason="A's answer")
        _record(b, "R-1", dispositions.FILE, backlog_id="ABC-1234")
        _sync(a)
        _sync(b)
        _sync(a)

        for clone in (a, b):
            history = dispositions.disposition_history(_store(clone), "rev-1", "R-1")
            assert len(history) == 2, (clone.name, [f["id"] for f in history])
        assert _winner(a, "R-1")["id"] == _winner(b, "R-1")["id"]
        assert _winner(a, "R-1")["body"] == _winner(b, "R-1")["body"]

    def test_a_re_answer_wins_everywhere_even_with_an_earlier_clock(self, a, b, monkeypatch):
        """B saw A's answer and answered again, on a machine whose clock is
        behind. The later answer is B's, so B's must win in both clones; a
        winner keyed on ``ts`` would pick A's."""
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _record(a, "R-1", dispositions.ACCEPT, reason="A's answer")
        _sync(a)
        _sync(b, push=False)
        assert _winner(b, "R-1")["body"]["reason"] == "A's answer"

        with monkeypatch.context() as clock:
            clock.setattr(evidence, "_now_iso", lambda: "2020-01-01T00:00:00Z")
            _record(b, "R-1", dispositions.FILE, backlog_id="ABC-1234")
        _sync(b)
        _sync(a)

        for clone in (a, b):
            winner = _winner(clone, "R-1")
            assert winner["ts"] == "2020-01-01T00:00:00Z", clone.name
            assert winner["body"]["action"] == dispositions.FILE, clone.name


# ---------------------------------------------------------------------------
# T6: a disposition hangs on its review's anchor
# ---------------------------------------------------------------------------


class TestADispositionHangsOnItsReviewsAnchor:
    def test_one_that_never_attached_is_reconciled_onto_the_review_not_head(self, a):
        c1 = _review(a, "rev-1", [_finding("R-1", "warning")])
        c2 = _commit(a, "src/app.py", "x = 2\n", "later work")
        envelope = _raw_disposition(a, "disp:rev-1:R-1:1", "R-1", reason="never attached")
        key = (envelope["kind"], envelope["id"])

        found = evidence_notes.unattached(a)
        assert found["status"] == "ok", found
        assert [(m["anchor"], m["envelope"]["id"]) for m in found["missing"]] == [(c1, envelope["id"])]

        reconciled = evidence_notes.reconcile(a)
        assert (reconciled["status"], reconciled["attached"]) == ("ok", 1), reconciled
        assert key in _note_keys(a, c1)
        assert key not in _note_keys(a, c2), "attached on HEAD, not on the review it answers"
        # Idempotent: the repair over a fact already sent finds nothing.
        assert evidence_notes.unattached(a)["missing"] == []

    def test_one_written_from_a_scratch_branch_is_still_this_branchs(self, a):
        c1 = _review(a, "rev-1", [_finding("R-1", "warning")])
        _git(a, "checkout", "-q", "-b", "scratch")
        envelope = _raw_disposition(a, "disp:rev-1:R-1:1", "R-1", reason="from scratch")
        assert envelope["actor"]["branch"] == "scratch"
        _git(a, "checkout", "-q", "feature/unit")
        _commit(a, "src/app.py", "x = 2\n", "later work")

        reconciled = evidence_notes.reconcile(a)
        assert (reconciled["status"], reconciled["attached"]) == ("ok", 1), reconciled
        assert (envelope["kind"], envelope["id"]) in _note_keys(a, c1)

    def test_one_whose_review_is_not_held_or_is_off_this_branch_is_not_missing(self, a):
        _git(a, "checkout", "-q", "-b", "side", "main")
        side = _commit(a, "src/other.py", "y = 1\n", "side work")
        _git(a, "checkout", "-q", "feature/unit")
        _review(a, "rev-side", [_finding("R-1", "warning")], anchor=side)
        _raw_disposition(a, "disp:rev-side:R-1:1", "R-1", reason="off branch", review_id="rev-side")
        _raw_disposition(a, "disp:rev-ghost:R-1:1", "R-1", reason="no review", review_id="rev-ghost")
        # Control: one whose review is on this branch IS missing.
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _raw_disposition(a, "disp:rev-1:R-1:1", "R-1", reason="on branch")

        found = evidence_notes.unattached(a)
        assert found["status"] == "ok", found
        assert [m["envelope"]["id"] for m in found["missing"]
                if m["envelope"]["kind"] == dispositions.KIND] == ["disp:rev-1:R-1:1"]


# ---------------------------------------------------------------------------
# T7: nothing that travels lifts a gate
# ---------------------------------------------------------------------------


class TestAnIngestedAnswerLiftsNoGate:
    def test_an_owner_ruled_accept_of_a_blocker_from_a_leaves_b_blocked(self, a, b):
        lint = _finding("R-2", "blocking", source=critic_consolidate.RECORD_LINT_SOURCE)
        _review(a, "rev-1", [_finding("R-1", "blocking"), lint])
        for fid in ("R-1", "R-2"):
            _record(a, fid, dispositions.ACCEPT, reason="owner accepts the risk",
                    owner_ruling="owner ruled 2026-11-23")
        _sync(a)
        _sync(b, push=False)

        store = _store(b)
        # The answers arrived and are read: otherwise nothing below is tested.
        assert _states(b) == {"R-1": dispositions.STATE_ACCEPTED, "R-2": dispositions.STATE_ACCEPTED}

        verdict = coverage_algebra.coverage_verdict(
            store["facts"], _git(b, "rev-parse", "main^{tree}"), _git(b, "rev-parse", "HEAD^{tree}"),
            lambda x, y: evidence.tree_diff(b, x, y),
        )
        assert verdict["status"] == "blocked", verdict
        assert sorted(u["fid"] for u in verdict["unresolved"]) == ["R-1", "R-2"]

        clear = plan_status._blocking_clear(store, ["rev-1"])
        assert clear["rev-1"] is not None and "R-1" in clear["rev-1"], clear

        answered = critic_consolidate.answered_lint_results(store, SCOPE)
        assert answered["blocking"] == {}, answered
        # Control: the lint result's answer was read, as a WARNING suppression.
        assert len(answered["warning"]) == 1, answered


# ---------------------------------------------------------------------------
# T8: a plugin from before the change skips dispositions and says so
# ---------------------------------------------------------------------------


class TestAnOlderPluginSkipsThem:
    def test_ingest_with_the_old_transported_set_appends_none_and_names_the_skip(self, a, b, monkeypatch):
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _record(a, "R-1", dispositions.ACCEPT, reason="the cost outweighs it")
        _sync(a)

        with monkeypatch.context() as old_plugin:
            old_plugin.setattr(evidence, "TRANSPORTED_KINDS", OLD_TRANSPORTED_KINDS)
            result = _fetch_and_ingest(b)
        assert result["appended"] == 1, result  # the review
        assert _disposition_keys(b) == set()
        assert "1 record(s) of a kind not transported skipped" in result["reason"], result

        # Control: the current set takes the same note's disposition.
        again = _fetch_and_ingest(b)
        assert again["appended"] == 1, again
        assert len(_disposition_keys(b)) == 1


# ---------------------------------------------------------------------------
# T10: stats count one outcome per finding
# ---------------------------------------------------------------------------


def _warning_counts(repo: Path) -> dict:
    report = stats.aggregate(_store(repo)["facts"], bucket=lambda _f: "all")
    return report["all"]["findings"]["warning"]


def _review_stats_outcomes(repo: Path) -> dict:
    events = [{"review": {"fact_id": "rev-1", "findings": [{"fid": "R-1"}]}}]
    joined = telemetry._read_dispositions(repo, events)
    assert joined["status"] == "available", joined
    return joined["outcomes"]


class TestStatsCountAnAnswerOnce:
    def test_an_ingested_answer_counts_once(self, a, b):
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _record(a, "R-1", dispositions.ACCEPT, reason="the cost outweighs it")
        _sync(a)
        _fetch_and_ingest(b)

        counts = _warning_counts(b)
        assert (counts["raised"], counts["accepted"], counts["undispositioned"]) == (1, 1, 0), counts
        assert _review_stats_outcomes(b) == {"rev-1": {"R-1": "accepted"}}

    def test_two_answers_to_one_finding_count_once(self, a, b):
        _review(a, "rev-1", [_finding("R-1", "warning")])
        _sync(a)
        _sync(b, push=False)
        _record(a, "R-1", dispositions.ACCEPT, reason="A's answer")
        _record(b, "R-1", dispositions.FILE, backlog_id="ABC-1234")
        _sync(a)
        _sync(b)
        _sync(a)
        # And one re-answer on top, so at least two answers are held whatever
        # the ids of the concurrent pair.
        _record(b, "R-1", dispositions.ACCEPT, reason="B's second answer")
        assert len(dispositions.disposition_history(_store(b), "rev-1", "R-1")) >= 2

        for clone in (a, b):
            counts = _warning_counts(clone)
            answered = sum(counts[o] for o in stats.OUTCOMES)
            assert (counts["raised"], answered) == (1, 1), (clone.name, counts)
            outcomes = _review_stats_outcomes(clone)
            assert list(outcomes) == ["rev-1"] and list(outcomes["rev-1"]) == ["R-1"], outcomes


# ---------------------------------------------------------------------------
# T11 (D6): an id two clones minted for different answers is reported
# ---------------------------------------------------------------------------


class TestALegacyIdCollisionIsReported:
    def _collide(self, a: Path, b: Path, *, same_body: bool = False) -> str:
        """A and B each hold a legacy ``disp:rev-1:R-1:1``: with different
        bodies, or (``same_body``) with one answer recorded twice. B's is on
        B's local note, as its writer attaches it, so after B merges, A's line
        sits on two different note blobs: B's merged local note and the
        fetched tracking note."""
        anchor = _review(a, "rev-1", [_finding("R-1", "warning")])
        _sync(a)
        _sync(b, push=False)
        _raw_disposition(a, "disp:rev-1:R-1:1", "R-1", reason="A's answer")
        mine = _raw_disposition(b, "disp:rev-1:R-1:1", "R-1",
                                reason="A's answer" if same_body else "B's answer")
        assert evidence_notes.attach(b, mine, anchor)["status"] == "attached"
        _sync(a)
        return anchor

    def test_ingest_counts_one_collision_once(self, a, b):
        anchor = self._collide(a, b)
        result = _sync(b, push=False)
        assert (f"1 {DIVERGED} before #1207; re-answer the finding to converge"
                in result["reason"]), result
        # The premise of "once": A's line is on two refs, as two blobs.
        local = _git(b, "notes", "--ref", NOTES_REF, "list", anchor)
        tracking = _git(b, "notes", "--ref", TRACKING_REF, "list", anchor)
        assert local and tracking and local != tracking
        # B keeps its own answer: facts are immutable and dedupe keeps the first.
        assert _winner(b, "R-1")["body"]["reason"] == "B's answer"
        again = _fetch_and_ingest(b)
        assert f"1 {DIVERGED}" in again["reason"], again

    def test_the_same_answer_under_one_id_is_no_collision(self, a, b):
        self._collide(a, b, same_body=True)
        result = _sync(b, push=False)
        assert DIVERGED not in (result["reason"] or ""), result

    def test_evidence_ingest_and_evidence_sync_print_it(self, a, b):
        self._collide(a, b)

        def run(*args: str) -> subprocess.CompletedProcess:
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "CLAUDE_PROJECT_DIR": str(b),
                   "CLAUDE_PLUGIN_ROOT": str(ROOT)}
            return subprocess.run([sys.executable, str(HOOK), "evidence", *args], cwd=str(b),
                                  capture_output=True, text=True, env=env, timeout=60)

        _git(b, "fetch", "-q", "origin", f"+{NOTES_REF}:{TRACKING_REF}")
        ingested = run("ingest")
        assert ingested.returncode == 0, ingested.stderr
        assert DIVERGED in ingested.stdout, (ingested.stdout, ingested.stderr)

        synced = run("sync", "--no-push")
        assert synced.returncode == 0, synced.stderr
        assert DIVERGED in synced.stdout, (synced.stdout, synced.stderr)


# ---------------------------------------------------------------------------
# The budget refusal says how many sweep ACCEPTs did not attach
# ---------------------------------------------------------------------------


class TestTheBudgetRefusalReportsUnsentAccepts:
    _BUDGET = {"spent": 3, "budget": 1, "review_ids": ["rev-1"],
               "bound": critic_consolidate.BOUND_LINEAGE, "cadence_ids": []}

    def _refuse(self, repo: Path, monkeypatch, swept: dict) -> dict:
        monkeypatch.setattr(dispositions, "auto_accept", lambda *_a, **_k: dict(swept))
        return critic_consolidate._refuse_over_budget(
            repo, dict(self._BUDGET), "cumulative", SCOPE, None, None, [],
        )

    def test_an_unsent_count_reaches_the_swept_block_and_a_note(self, a, monkeypatch):
        result = self._refuse(a, monkeypatch, {"status": "swept", "accepted": 2,
                                               "skipped_blocking": 0, "failed": [], "unsent": 2})
        assert result["swept"]["unsent"] == 2
        assert [n for n in result["notes"] if "2 budget ACCEPT(s)" in n and "evidence sync" in n]

    def test_a_sweep_that_reports_no_unsent_reads_as_zero_and_says_nothing(self, a, monkeypatch):
        result = self._refuse(a, monkeypatch, {"status": "swept", "accepted": 2,
                                               "skipped_blocking": 0, "failed": []})
        assert result["swept"]["unsent"] == 0
        assert not [n for n in result["notes"] if "budget ACCEPT(s)" in n]
