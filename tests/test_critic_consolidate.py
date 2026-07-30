"""Tests for the deterministic Critic data plane (kernel v3, GOV-4C7X ch.03).

Both ends of the ``.prawduct/.critic-partials/`` contract: ``prawduct-hook
critic-begin --mode <m>`` derives + writes the dispatch manifest (code, never
a model — the CRT-W2NV defect class dies at its author), and
``critic-consolidate`` merges the reviewer partials against it, appends the
review fact (and any resolution facts) to the evidence store, regenerates
``.critic-findings.json`` as a derived cache carrying its source ``fact_id``,
and anchors the ledger — but ONLY when every roster role reported a
schema-valid partial at the manifest's dispatch commit. Everything else is a
no-op naming the missing roles (incomplete) or a fail-closed error
(malformed, inconsistent, off-protocol). The pair is the load-bearing piece
of the review data plane, so the truth table is pinned exhaustively.

Posture change pinned here (design D8, chunk-03 refinements): consolidation
no longer refuses when HEAD moved after dispatch — the fact is a true
statement about the tree the reviewers saw; sufficiency is the gate-time
coverage composition's question.

Two layers: pure-function unit tests (validators + merge) and real-git
integration through ``bin/prawduct-hook`` with a real ``ledger-append`` — the
sterile-env pattern from ``test_governance_ledger.py`` (HOME outside the repo
so pyc-cache doesn't leak, GIT_CONFIG neutralized).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
sys.path.insert(0, str(ROOT))
from lib import critic_consolidate as cc  # noqa: E402
from lib import evidence  # noqa: E402
from lib import gates  # noqa: E402
from lib import record_lint  # noqa: E402

PARTIALS_REL = ".prawduct/.critic-partials"
FINDINGS_REL = ".prawduct/.critic-findings.json"
MARKER_REL = ".prawduct/.critic-active"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"
FINAL_MODE = "final (full review, ready for push)"
VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"


# ---------------------------------------------------------------------------
# Real-git helpers (sterile env — mirrors test_governance_ledger.py)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_consolidate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-consolidate"],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _partials_dir(repo: Path) -> Path:
    d = repo / PARTIALS_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_dict(head: str = "abc123", *, roster=None, **overrides) -> dict:
    """A schema-valid v3 manifest. Tree SHAs are opaque strings to the
    consolidator (it never resolves them via git), so fakes suffice for
    consolidate-side tests; begin-side tests use real captures."""
    manifest = {
        "id": "rev-test-0001",
        "mode": FINAL_MODE,
        "mode_chosen_by": "rule-3 final",
        "roster": roster if roster is not None else ["correctness", "design", "sustainability"],
        "roster_chosen_by": "mode=final, 1 files changed < 5 — single-pass",
        "commit_reviewed": head,
        "base_commit": head,
        "base_tree": "basetree000000000000",
        "head_tree": "headtree000000000000",
        "head_commit": None,
        "files_changed": ["src/app.py"],
        "files_reviewed": ["src/app.py"],
        "tier": None,
        "scope": "demo-scope",
        "chunk": "01",
        "base_reviewed": None,
    }
    manifest.update(overrides)
    return manifest


def _write_manifest(repo: Path, head: str, *, roster=None, **overrides) -> None:
    (_partials_dir(repo) / "manifest.json").write_text(
        json.dumps(_manifest_dict(head, roster=roster, **overrides))
    )


def _run_begin(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-begin", *args],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _store_facts(repo: Path, kind: str | None = None) -> list[dict]:
    """Facts currently in the repo's evidence store (deduped, schema-checked
    read — the same read gates will use)."""
    result = evidence.read_facts(repo)
    facts = result["facts"]
    if kind is not None:
        facts = [f for f in facts if f.get("kind") == kind]
    return facts


def _store_lines(repo: Path) -> list[str]:
    """Raw store lines — for asserting exactly-one-append (dedup would hide a
    double write)."""
    path = evidence.store_path(repo)
    if path is None or not path.is_file():
        return []
    return [ln for ln in path.read_text().splitlines() if ln.strip()]


def _partial(role: str, head: str, findings=None, **overrides) -> dict:
    data = {
        "role": role,
        "goals": "1-3",
        "commit_reviewed": head,
        "model": "opus",
        "duration_seconds": 90,
        "findings": findings if findings is not None else [],
        "summary": f"{role} review complete.",
    }
    data.update(overrides)
    return data


def _write_partial(repo: Path, role: str, head: str, **kwargs) -> None:
    (_partials_dir(repo) / f"{role}.json").write_text(json.dumps(_partial(role, head, **kwargs)))


def _set_marker(repo: Path) -> None:
    (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
    (repo / MARKER_REL).write_text(json.dumps({"started_at": "2026-07-09T00:00:00Z"}))


def _full_roster_partials(repo: Path, head: str, findings_by_role=None) -> None:
    findings_by_role = findings_by_role or {}
    for role in ("correctness", "design", "sustainability"):
        _write_partial(repo, role, head, findings=findings_by_role.get(role, []))


# ---------------------------------------------------------------------------
# Unit: validators
# ---------------------------------------------------------------------------


class TestValidatePartial:
    def test_minimal_clean_partial_valid(self):
        ok, reason = cc.validate_partial(_partial("correctness", "abc123"))
        assert ok, reason

    def test_partial_with_finding_valid(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "Missing test", "goal": "Nothing Is Missing",
             "severity": "warning", "recommendation": "Add one", "files": ["a.py"]}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_finding_with_empty_files_accepted(self):
        # A process/evidence finding with ``files: []`` (semantically identical
        # to omitting the key) must NOT fail-close the consolidation.
        p = _partial("correctness", "abc", findings=[
            {"name": "Stale test-status", "goal": "Nothing Is Broken",
             "severity": "warning", "recommendation": "Re-run", "files": []}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_finding_files_with_blank_element_normalized_not_rejected(self):
        # A blank/non-string element in ``files`` is optional attribution — it
        # must be normalized away downstream, NOT fail-close the whole
        # consolidation. (This previously rejected; that rejection WAS the
        # defect — one reviewer's ``files:[""]`` on a file-less META-finding
        # bricked every review.)
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "warning",
             "recommendation": "y", "files": ["a.py", ""]}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_finding_files_all_blank_accepted(self):
        # ``files: [""]`` — the exact live trigger — must consolidate, not abort.
        p = _partial("correctness", "abc", findings=[
            {"name": "Learnings cross-check", "goal": "g", "severity": "note",
             "recommendation": "y", "files": [""]}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_finding_files_nonstring_element_accepted(self):
        # A list holding a non-string element is tolerated at validation (it is
        # dropped in merge_findings), consistent with the blank-element rule —
        # only a non-*list* ``files`` value is a hard schema error.
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "warning",
             "recommendation": "y", "files": [5, "a.py"]}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_finding_files_not_a_list_rejected(self):
        # A non-list ``files`` is still a hard schema error (a bare string is a
        # common mis-emission) — only malformed *elements* are tolerated.
        for bad in ("a.py", 5, {"a.py": 1}):
            p = _partial("correctness", "abc", findings=[
                {"name": "x", "goal": "g", "severity": "warning",
                 "recommendation": "y", "files": bad}
            ])
            ok, reason = cc.validate_partial(p)
            assert not ok, f"{bad!r} should be rejected"
            assert "files" in reason

    @pytest.mark.parametrize("mutate,frag", [
        (lambda p: p.pop("role"), "role"),
        (lambda p: p.pop("commit_reviewed"), "commit_reviewed"),
        (lambda p: p.pop("summary"), "summary"),
        (lambda p: p.update(goals=""), "goals"),
        (lambda p: p.update(findings="nope"), "findings"),
        (lambda p: p.update(model=42), "model"),
        (lambda p: p.update(duration_seconds="slow"), "duration_seconds"),
    ])
    def test_malformed_partial_rejected(self, mutate, frag):
        p = _partial("correctness", "abc")
        mutate(p)
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert frag in reason

    def test_unknown_severity_rejected(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "critical", "recommendation": "y"}
        ])
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert "severity" in reason

    def test_finding_missing_recommendation_rejected(self):
        p = _partial("correctness", "abc", findings=[
            {"name": "x", "goal": "g", "severity": "warning"}
        ])
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert "recommendation" in reason

    def test_resolutions_fixed_valid(self):
        p = _partial("reviewer", "abc", resolutions=[
            {"review_id": "rev-1", "fid": "R-1", "disposition": "fixed"}
        ])
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    def test_resolutions_empty_list_valid(self):
        # []/omitted collapse (tolerant-encoding rule) — an empty list is the
        # shape a model naturally emits for "nothing resolved".
        ok, reason = cc.validate_partial(_partial("reviewer", "abc", resolutions=[]))
        assert ok, reason

    def test_resolution_waived_requires_rationale(self):
        # R7 — a waiver carries its justification; a bare "waived" would let a
        # blocking finding vanish with no recorded why.
        p = _partial("reviewer", "abc", resolutions=[
            {"review_id": "rev-1", "fid": "R-1", "disposition": "waived"}
        ])
        ok, reason = cc.validate_partial(p)
        assert not ok
        assert "rationale" in reason
        p["resolutions"][0]["rationale"] = "accepted risk, documented in plan"
        ok, reason = cc.validate_partial(p)
        assert ok, reason

    @pytest.mark.parametrize("mutate,frag", [
        (lambda r: r.pop("review_id"), "review_id"),
        (lambda r: r.pop("fid"), "fid"),
        (lambda r: r.update(disposition="resolved"), "disposition"),
    ])
    def test_malformed_resolution_rejected(self, mutate, frag):
        res = {"review_id": "rev-1", "fid": "R-1", "disposition": "fixed"}
        mutate(res)
        ok, reason = cc.validate_partial(_partial("reviewer", "abc", resolutions=[res]))
        assert not ok
        assert frag in reason


class TestValidateManifest:
    def test_clean_manifest_valid(self):
        ok, reason = cc.validate_manifest(_manifest_dict())
        assert ok, reason

    def test_bare_mode_token_rejected(self):
        ok, reason = cc.validate_manifest(_manifest_dict(mode="final"))
        assert not ok
        assert "mode" in reason

    def test_worktree_branch_nullable_accepted(self):
        # PDT-WT9K visibility fields: both null (detached HEAD → branch None) and
        # populated are valid; an absent key (older manifest) is fine too.
        assert cc.validate_manifest(_manifest_dict(worktree=None, branch=None))[0]
        assert cc.validate_manifest(_manifest_dict(worktree="/r", branch="main"))[0]

    def test_non_string_worktree_rejected(self):
        ok, reason = cc.validate_manifest(_manifest_dict(worktree=5))
        assert not ok
        assert "worktree" in reason

    @pytest.mark.parametrize("field", [
        "id", "mode_chosen_by", "roster", "roster_chosen_by",
        "commit_reviewed", "base_tree", "head_tree",
        "files_reviewed", "files_changed",
    ])
    def test_missing_required_field_rejected(self, field):
        manifest = _manifest_dict()
        manifest.pop(field)
        ok, reason = cc.validate_manifest(manifest)
        assert not ok
        assert field in reason

    def test_v2_model_written_shape_rejected(self):
        """CRT-W2NV regression pin: the v2 manifest shape — the one a model
        hand-authored (and omitted keys from) — carries none of the v3
        interval fields, so nothing a stale cached skill writes by hand can
        pass validation. The omitted-key defect class has no author left."""
        v2_manifest = {
            "mode": FINAL_MODE, "mode_chosen_by": "rule-3",
            "roster": ["correctness", "design", "sustainability"],
            "commit_reviewed": "abc", "files_reviewed": ["x.py"],
            "scope": "demo", "model": "opus",
        }
        ok, reason = cc.validate_manifest(v2_manifest)
        assert not ok
        assert "id" in reason

    def test_empty_files_changed_accepted(self):
        # A same-tree verify-resolutions pass legitimately changes nothing.
        ok, reason = cc.validate_manifest(_manifest_dict(files_changed=[]))
        assert ok, reason

    def test_nullable_commits_accepted(self):
        # A prior review of a dirty tree has no head_commit; verify-resolutions
        # anchored to it has no base_commit.
        ok, reason = cc.validate_manifest(
            _manifest_dict(base_commit=None, head_commit=None)
        )
        assert ok, reason

    def test_mode_map_matches_gates_vocabulary(self):
        # The dispatch-side token map must write exactly the verbose strings
        # the persisted-record validator accepts — drift = unconsolidatable
        # reviews.
        assert set(cc.MODE_TOKEN_TO_VERBOSE.values()) == set(gates._CRITIC_MODE_VALUES)


# ---------------------------------------------------------------------------
# Unit: merge / dedup / severity
# ---------------------------------------------------------------------------


class TestMergeFindings:
    def test_maps_name_to_title_assigns_fid(self):
        # The reviewer's ``name`` becomes the fact ``title`` (rendered as the
        # cache ``summary``), and every finding gets a fid — the join key a
        # resolution fact needs (a blocking finding without one could never
        # be resolved).
        partials = [_partial("correctness", "a", findings=[
            {"name": "Broken thing", "goal": "Nothing Is Broken",
             "severity": "blocking", "recommendation": "Fix it", "files": ["a.py"]}
        ])]
        merged = cc.merge_findings(partials)
        assert merged == [{
            "goal": "Nothing Is Broken", "severity": "blocking",
            "title": "Broken thing", "recommendation": "Fix it",
            "files": ["a.py"], "fid": "R-1",
        }]

    def test_empty_files_normalized_out_of_record(self):
        # ``files: []`` must be dropped from the canonical entry — the same shape
        # an omitted key produces — so the record stays schema-clean.
        merged = cc.merge_findings([_partial("correctness", "a", findings=[
            {"name": "Stale evidence", "goal": "Nothing Is Broken",
             "severity": "warning", "recommendation": "Re-run", "files": []}
        ])])
        assert merged == [{
            "goal": "Nothing Is Broken", "severity": "warning",
            "title": "Stale evidence", "recommendation": "Re-run", "fid": "R-1",
        }]
        assert "files" not in merged[0]

    def test_blank_and_nonstring_files_elements_dropped(self):
        # Both blank strings AND genuinely non-string elements normalize out,
        # mirroring ``[]`` — only real path strings survive.
        merged = cc.merge_findings([_partial("correctness", "a", findings=[
            {"name": "Meta note", "goal": "Nothing Is Missing",
             "severity": "note", "recommendation": "n",
             "files": ["", 5, None, "  ", "a.py"]}
        ])])
        assert merged[0]["files"] == ["a.py"]

    def test_all_blank_files_normalized_out_of_record(self):
        # ``files: [""]`` collapses to no ``files`` key, like ``[]``.
        merged = cc.merge_findings([_partial("correctness", "a", findings=[
            {"name": "Meta note", "goal": "Nothing Is Missing",
             "severity": "note", "recommendation": "n", "files": [""]}
        ])])
        assert "files" not in merged[0]

    def test_dedup_keeps_highest_severity(self):
        # Same (goal, name, files) reported by two reviewers at differing severity.
        f_warn = {"name": "Dup", "goal": "G", "severity": "warning", "recommendation": "r"}
        f_block = {"name": "Dup", "goal": "G", "severity": "blocking", "recommendation": "r"}
        merged = cc.merge_findings([
            _partial("correctness", "a", findings=[f_warn]),
            _partial("design", "a", findings=[f_block]),
        ])
        assert len(merged) == 1
        assert merged[0]["severity"] == "blocking"

    def test_distinct_findings_get_sequential_fids(self):
        merged = cc.merge_findings([
            _partial("correctness", "a", findings=[
                {"name": "A", "goal": "G1", "severity": "warning", "recommendation": "r"}]),
            _partial("design", "a", findings=[
                {"name": "B", "goal": "G2", "severity": "note", "recommendation": "r"}]),
        ])
        assert [f["fid"] for f in merged] == ["R-1", "R-2"]

    def test_fact_body_renders_to_schema_valid_cache(self, tmp_path):
        # The cache is a derived view of the fact (D7): body → record must
        # satisfy the schema the record's readers trust, name → title →
        # summary end-to-end, and the record must point back at its fact.
        manifest = _manifest_dict(roster=["correctness"])
        body = cc.build_fact_body(manifest, [_partial(
            "correctness", "abc123", findings=[
                {"name": "Broken thing", "goal": "Nothing Is Broken",
                 "severity": "blocking", "recommendation": "Fix it"}])])
        fact = {"schema": 1, "kind": "review", "id": manifest["id"],
                "ts": "2026-07-13T00:00:00Z", "body": body}
        record = cc.fact_to_cache_record(fact)
        p = tmp_path / "f.json"
        p.write_text(json.dumps(record))
        assert gates.validate_critic_findings(p)
        assert record["fact_id"] == manifest["id"]
        assert record["findings"][0]["summary"] == "Broken thing"
        assert record["findings"][0]["fid"] == "R-1"
        assert record["commit_reviewed"] == manifest["commit_reviewed"]
        assert record["model"] == "opus"  # from the partial, not the manifest
        assert body["counts"] == {"blocking": 1, "warning": 0, "note": 0}
        assert body["roster"] == [{"role": "correctness", "model": "opus"}]


# ---------------------------------------------------------------------------
# Unit: dispatch age + the incomplete no-op's liveness verdict
# ---------------------------------------------------------------------------


class TestIncompleteNoopLiveness:
    """The incomplete no-op must carry a liveness verdict, not just a partial
    count: a parent session that consolidates during the reviewers' background
    run window sees 0/N partials, and bare silence reads as "the reviewers
    died with the fork" — triggering a duplicate dispatch while the first
    roster is still alive (the observed double-review-cost failure)."""

    def _fresh_id(self, minutes_ago: float) -> str:
        ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return f"rev-{ts.strftime('%Y%m%dT%H%M%SZ')}-deadbeef"

    def test_age_parses_synthetic_begin_shaped_id(self):
        age = cc.dispatch_age_minutes(self._fresh_id(3))
        assert age is not None
        assert 2.5 < age < 4.0

    def test_age_none_for_non_timestamp_id(self):
        assert cc.dispatch_age_minutes("rev-test-0001") is None

    def test_age_none_for_invalid_calendar_stamp(self):
        # Matches the shape regex but is not a real date — parse must not raise.
        assert cc.dispatch_age_minutes("rev-20261399T996161Z-deadbeef") is None

    def test_future_stamp_clamps_to_zero(self):
        assert cc.dispatch_age_minutes(self._fresh_id(-30)) == 0.0

    def test_young_dispatch_says_wait_not_dead(self):
        msg = cc._incomplete_noop_message(
            ["correctness", "design"], 1, 3, self._fresh_id(2))
        assert "no-op" in msg
        assert "correctness, design" in msg
        assert "1/3 partials present" in msg
        assert "dispatched 2.0 min ago" in msg
        assert "NOT evidence the reviewers died" in msg
        assert "Do not" in msg and "re-dispatch" in msg
        assert "critic-end" in msg  # the sanctioned escape hatch is named
        assert "may have died" not in msg

    def test_stale_dispatch_advises_critic_end(self):
        msg = cc._incomplete_noop_message(
            ["sustainability"], 2, 3, self._fresh_id(45))
        assert "no-op" in msg
        assert "sustainability" in msg
        assert "may have died" in msg
        assert "critic-end" in msg
        assert "NOT evidence" not in msg

    def test_single_pass_young_says_fork_consolidates_itself(self):
        # Roster ["reviewer"]: the reviewer IS the dispatching fork — no
        # SubagentStop trigger will ever land it, so the message must not
        # tell the coordinator-roster story.
        msg = cc._incomplete_noop_message(["reviewer"], 0, 1, self._fresh_id(2))
        assert "0/1 partials present" in msg
        assert "consolidates when it finishes" in msg
        assert "SubagentStop" not in msg
        assert "NOT evidence the reviewer died" in msg
        assert "critic-end" in msg

    def test_unparseable_id_still_carries_wait_guidance(self):
        # Hand-written manifests (no timestamp in the id) get the wait-side
        # guidance with no age claim — never a crash, never bare silence.
        msg = cc._incomplete_noop_message(["design"], 0, 3, "rev-test-0001")
        assert "0/3 partials present" in msg
        assert "dispatched" not in msg
        assert "NOT evidence the reviewers died" in msg
        # No age claim, but it is still a wait — the readout directive applies.
        assert cc._CACHE_WARM_DIRECTIVE in msg

    def test_wait_side_directs_a_periodic_readout(self):
        # An idle waiting session issues no requests, so its prompt cache
        # expires and the next turn replays the whole prefix. Both wait-side
        # variants must carry the readout directive, and it must name a cadence
        # strictly under the 5-minute cache it is sized against.
        assert cc._CACHE_WARM_INTERVAL_MINUTES < 5
        for missing, present, total in (
            (["correctness", "design"], 1, 3),  # coordinator roster
            (["reviewer"], 0, 1),               # single-pass roster
        ):
            msg = cc._incomplete_noop_message(
                missing, present, total, self._fresh_id(2))
            assert cc._CACHE_WARM_DIRECTIVE in msg
            assert f"every {cc._CACHE_WARM_INTERVAL_MINUTES} minutes" in msg
            assert "idling silently" in msg

    def test_begin_review_routes_through_the_single_minter(self):
        # The round-trip below proves the MINTER agrees with the parser. It does
        # not prove begin_review still uses the minter — a future edit could
        # inline a format string again and reopen the drift hole with the
        # round-trip test still green. Asserted structurally instead.
        #
        # Scope, stated exactly: this catches a second site copied in the SAME
        # literal shape. An f-string minting site would pass both assertions —
        # the guard narrows the hole, it does not close it.
        src = (ROOT / "lib" / "critic_consolidate.py").read_text()
        assert src.count('"rev-{}-{}"') == 1, "more than one site formats a review id"
        assert "review_id = mint_review_id()" in src

    def test_minted_review_id_round_trips_through_dispatch_age(self):
        # The producer/consumer contract, exercised end-to-end rather than
        # against a hand-built id: begin_review mints the id, dispatch_age_minutes
        # parses it. If the format drifts, parsing returns None, the
        # past-grace branch becomes UNREACHABLE, and the no-op tells a session to
        # wait forever on dead reviewers — the exact failure this message exists
        # to prevent, and one no hand-written fixture can catch.
        rid = cc.mint_review_id()
        assert cc._REVIEW_ID_TS.match(rid), f"minted id {rid!r} is unparseable"
        age = cc.dispatch_age_minutes(rid)
        assert age is not None and age < 1.0

    def test_review_cycle_prose_matches_the_code_cadence(self):
        # The cadence is interpolated into the CLI message but written as a bare
        # literal in the skill prose. CRT-8Q6R expects that number to change, so
        # bind them: a bump that updates only the constant would leave the
        # operator-facing guide quietly contradicting the tool.
        prose = (ROOT / "skills" / "critic" / "review-cycle.md").read_text()
        assert f"every {cc._CACHE_WARM_INTERVAL_MINUTES} minutes" in prose, (
            "review-cycle.md's cadence no longer matches "
            f"_CACHE_WARM_INTERVAL_MINUTES ({cc._CACHE_WARM_INTERVAL_MINUTES})"
        )

    def test_stale_dispatch_omits_the_readout_directive(self):
        # Past the grace window the advice is to STOP waiting (critic-end +
        # re-dispatch). Telling the caller to keep narrating there would warm
        # the cache for a state it should be leaving.
        msg = cc._incomplete_noop_message(
            ["sustainability"], 2, 3, self._fresh_id(45))
        assert "may have died" in msg
        assert cc._CACHE_WARM_DIRECTIVE not in msg


# ---------------------------------------------------------------------------
# Unit: pending_state
# ---------------------------------------------------------------------------


class TestPendingState:
    def test_no_manifest_is_none(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        assert cc.pending_state(tmp_path / ".prawduct") == ("none", [])

    def test_incomplete_names_missing_roles(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _write_manifest(repo, "abc")
        _write_partial(repo, "correctness", "abc")
        state, missing = cc.pending_state(repo / ".prawduct")
        assert state == "incomplete"
        assert set(missing) == {"design", "sustainability"}

    def test_complete_when_all_partial_files_present(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _write_manifest(repo, "abc")
        _full_roster_partials(repo, "abc")
        assert cc.pending_state(repo / ".prawduct") == ("complete", [])

    def test_corrupt_manifest_is_unreadable(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _partials_dir(repo)
        (repo / PARTIALS_REL / "manifest.json").write_text("{not json")
        assert cc.pending_state(repo / ".prawduct") == ("unreadable", [])


# ---------------------------------------------------------------------------
# Integration: real git + real ledger-append through the hook
# ---------------------------------------------------------------------------


class TestConsolidateIntegration:
    def test_complete_partials_at_head_consolidates(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head, findings_by_role={
            "correctness": [{"name": "Missing edge test", "goal": "Nothing Is Missing",
                             "severity": "warning", "recommendation": "Add it", "files": ["src/app.py"]}],
        })
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated:" in result.stdout

        # The review fact is in the store, keyed by the manifest's fixed id.
        facts = _store_facts(repo, "review")
        assert len(facts) == 1
        fact = facts[0]
        assert fact["id"] == "rev-test-0001"
        assert fact["body"]["findings"][0]["title"] == "Missing edge test"
        assert fact["body"]["findings"][0]["fid"] == "R-1"
        assert fact["body"]["base_tree"] and fact["body"]["head_tree"]

        # The derived cache: schema-valid and pointing at its source fact.
        findings_path = repo / FINDINGS_REL
        assert findings_path.is_file()
        assert gates.validate_critic_findings(findings_path)
        record = json.loads(findings_path.read_text())
        assert record["fact_id"] == fact["id"]
        assert record["commit_reviewed"] == head
        assert record["mode"] == FINAL_MODE
        assert len(record["findings"]) == 1
        assert record["findings"][0]["summary"] == "Missing edge test"

        # Ledger anchor present.
        ledger_lines = (repo / LEDGER_REL).read_text().strip().splitlines()
        assert len(ledger_lines) == 1
        event = json.loads(ledger_lines[0])
        assert event["event"] == "review.critic"
        assert event["scope"] == "demo-scope"

        # Marker cleared + partials removed.
        assert not (repo / MARKER_REL).is_file()
        assert not (repo / PARTIALS_REL).exists()

    def test_missing_role_is_noop_names_role(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        # sustainability absent.
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "no-op" in result.stdout
        assert "sustainability" in result.stdout
        # Nothing persisted; marker + partials intact for the straggler to complete.
        assert not (repo / FINDINGS_REL).is_file()
        assert (repo / MARKER_REL).is_file()
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_early_check_noop_carries_liveness_guidance(self, tmp_path):
        """An early consolidate (0/3 partials, seconds after dispatch) must
        say the silence is normal — the bare count was being misread as
        reviewer death, triggering duplicate dispatch."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        fresh_id = "rev-{}-cafe0001".format(
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        _write_manifest(repo, head, id=fresh_id)
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "no-op" in result.stdout
        assert "0/3 partials present" in result.stdout
        assert "dispatched 0." in result.stdout  # 0.x min — subprocess slop
        assert "NOT evidence the reviewers died" in result.stdout
        # Marker + manifest untouched — the review is still in flight.
        assert (repo / MARKER_REL).is_file()
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_head_moved_since_dispatch_still_consolidates(self, tmp_path):
        """v3 posture change (design D8): a commit after dispatch does NOT
        block consolidation. The fact is a true statement about the tree the
        reviewers saw — whether it still covers the new state is the
        gate-time coverage composition's question, not the writer's. (The v2
        consolidate refused here, killing the evidence — the
        'evidence dies on staleness' defect class.)"""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        # A code commit lands after dispatch.
        _commit_file(repo, "src/app.py", "x = 2\n", "later")
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated:" in result.stdout
        # The fact records the DISPATCHED interval, not the moved HEAD.
        fact = _store_facts(repo, "review")[0]
        assert fact["body"]["dispatch_commit"] == head

    def test_malformed_partial_fails_closed(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        # sustainability present but malformed (bad severity).
        (repo / PARTIALS_REL / "sustainability.json").write_text(json.dumps({
            "role": "sustainability", "goals": "5-6", "commit_reviewed": head,
            "summary": "s", "findings": [
                {"name": "x", "goal": "g", "severity": "showstopper", "recommendation": "y"}],
        }))
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "sustainability" in result.stderr
        assert not (repo / FINDINGS_REL).is_file()

    def test_partial_reviewed_wrong_commit_fails_closed(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        _write_partial(repo, "sustainability", "deadbeefdeadbeef")  # different commit
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "inconsistent" in result.stderr or "reviewed" in result.stderr
        assert not (repo / FINDINGS_REL).is_file()

    def test_no_manifest_is_clean_noop(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        result = _run_consolidate(repo)
        assert result.returncode == 0
        assert "no-op" in result.stdout

    def test_idempotent_second_call_is_clean_noop(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        first = _run_consolidate(repo)
        assert first.returncode == 0 and "consolidated:" in first.stdout
        second = _run_consolidate(repo)
        assert second.returncode == 0
        assert "no-op" in second.stdout
        # Exactly one fact line and one ledger anchor — the second call added
        # nothing (raw line count, so reader-side dedup can't mask a double
        # append).
        assert len(_store_lines(repo)) == 1
        ledger_lines = (repo / LEDGER_REL).read_text().strip().splitlines()
        assert len(ledger_lines) == 1

    def test_retry_after_success_appends_no_second_fact(self, tmp_path):
        """The CRT-4B7X race, simulated: the same manifest+partials land
        again after a successful consolidation (a straggler SubagentStop
        firing against a re-created dispatch dir, or a crash between fact
        append and partials removal). The id-idempotency probe must skip the
        append — one review, one fact, ever."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        assert _run_consolidate(repo).returncode == 0
        # Same review id re-materializes on disk (crash-window replay).
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert len(_store_lines(repo)) == 1, "the same review id must never append twice"
        # ...and the ledger anchor is idempotent too. Without this assertion the
        # probe in `consolidate` could be deleted and the suite would still pass
        # green: the fact append is protected by (kind, id) dedupe, the ledger
        # by nothing. `review-stats` counts these lines, so a second event
        # double-counts the review in the instrument review proportionality is
        # measured with.
        ledger_lines = (repo / LEDGER_REL).read_text().strip().splitlines()
        assert len(ledger_lines) == 1, "one review must anchor exactly one ledger event"
        # Cache still present, still pointing at the one fact.
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["fact_id"] == "rev-test-0001"

    def test_clean_review_no_findings_still_valid(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)  # all clean, zero findings
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["findings"] == []
        assert "0 blocking" in record["summary"]
        # files_reviewed non-empty (from manifest) so schema holds even clean.
        assert gates.validate_critic_findings(repo / FINDINGS_REL)


# ---------------------------------------------------------------------------
# Integration: resolution facts (D5) — the verify-resolutions write path
# ---------------------------------------------------------------------------


def _seed_prior_review_with_blocker(repo: Path, head: str, **overrides) -> str:
    """Run a full consolidation that leaves one blocking finding in the store
    and the cache pointing at its fact. Returns the prior review's fact id.
    Pass real tree SHAs via ``overrides`` when a later begin-side dispatch
    will resolve them through git (the defaults are fakes)."""
    _set_marker(repo)
    _write_manifest(repo, head, id="rev-prior-0001", **overrides)
    _full_roster_partials(repo, head, findings_by_role={
        "correctness": [{"name": "Broken invariant", "goal": "Nothing Is Broken",
                         "severity": "blocking", "recommendation": "Fix it",
                         "files": ["src/app.py"]}],
    })
    result = _run_consolidate(repo)
    assert result.returncode == 0, f"seed failed: {result.stderr!r}"
    return "rev-prior-0001"


class TestResolutionFacts:
    def test_verify_resolutions_appends_resolution_fact(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        prior_id = _seed_prior_review_with_blocker(repo, head)

        _set_marker(repo)
        _write_manifest(
            repo, head, id="rev-verify-0002", mode=VERIFY_MODE,
            roster=["reviewer"],
        )
        _write_partial(repo, "reviewer", head, resolutions=[
            {"review_id": prior_id, "fid": "R-1", "disposition": "fixed"}
        ])
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "1 resolution fact(s)" in result.stdout

        resolutions = _store_facts(repo, "resolution")
        assert len(resolutions) == 1
        body = resolutions[0]["body"]
        assert body["finding"] == {"review_id": prior_id, "fid": "R-1"}
        assert body["disposition"] == "fixed"
        assert body["verified_by"] == "rev-verify-0002"
        assert body["at_tree"] == "headtree000000000000"

    def test_resolution_fact_append_is_idempotent(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        prior_id = _seed_prior_review_with_blocker(repo, head)
        for _ in range(2):  # replay the whole verify dispatch (crash window)
            _set_marker(repo)
            _write_manifest(repo, head, id="rev-verify-0002", mode=VERIFY_MODE,
                            roster=["reviewer"])
            _write_partial(repo, "reviewer", head, resolutions=[
                {"review_id": prior_id, "fid": "R-1", "disposition": "fixed"}
            ])
            assert _run_consolidate(repo).returncode == 0
        # 1 prior review + 1 verify review + 1 resolution — no dupes.
        assert len(_store_lines(repo)) == 3
        assert len(_store_facts(repo, "resolution")) == 1

    def test_resolutions_outside_verify_mode_fail_closed(self, tmp_path):
        """Resolution facts WEAKEN gates (they unblock findings), so only the
        flow designed to produce them may. A final-mode partial carrying
        resolutions is off-protocol → loud error, nothing persisted."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        prior_id = _seed_prior_review_with_blocker(repo, head)

        _set_marker(repo)
        _write_manifest(repo, head, id="rev-final-0002")  # final mode
        _full_roster_partials(repo, head)
        _write_partial(repo, "correctness", head, resolutions=[
            {"review_id": prior_id, "fid": "R-1", "disposition": "fixed"}
        ])
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "verify-resolutions" in result.stderr
        assert len(_store_facts(repo, "resolution")) == 0

    def test_resolution_of_unknown_finding_fails_closed(self, tmp_path):
        """A resolution must reference a finding the store actually holds —
        a hallucinated (review_id, fid) would otherwise persist as a silent
        no-op the operator reads as 'resolved'."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _seed_prior_review_with_blocker(repo, head)

        _set_marker(repo)
        _write_manifest(repo, head, id="rev-verify-0002", mode=VERIFY_MODE,
                        roster=["reviewer"])
        _write_partial(repo, "reviewer", head, resolutions=[
            {"review_id": "rev-prior-0001", "fid": "R-99", "disposition": "fixed"}
        ])
        result = _run_consolidate(repo)
        assert result.returncode == 1
        assert "does not hold" in result.stderr
        assert len(_store_facts(repo, "resolution")) == 0
        # Manifest left in place for the corrected retry.
        assert (repo / PARTIALS_REL / "manifest.json").is_file()


# ---------------------------------------------------------------------------
# Integration: critic-begin — the code-written manifest (D8)
# ---------------------------------------------------------------------------


class TestCriticBeginCLI:
    def test_bare_invocation_fails_with_skew_remedy(self, tmp_path):
        """No --mode = a stale cached skill driving a newer hook. Refuse AT
        DISPATCH with the reload remedy — not 4-10 minutes later when the
        consolidator rejects a hand-written manifest (C9 tier 3)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        result = _run_begin(repo)
        assert result.returncode == 1
        assert "--mode is required" in result.stderr
        assert "reload" in result.stderr
        assert not (repo / PARTIALS_REL).exists()
        assert not (repo / MARKER_REL).is_file()

    def test_chunk_mode_dirty_tree(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")  # the chunk's dirty diff
        status_before = _git(repo, "status", "--porcelain").stdout
        result = _run_begin(repo, "--mode", "chunk", "--chosen-by", "rule-4 chunk",
                            "--chunk", "03", "--scope", "demo")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        ok, reason = cc.validate_manifest(manifest)
        assert ok, reason  # round-trip: begin's manifest passes consolidate's validator
        assert manifest["mode"] == "chunk (lighter pass, not ready for push)"
        assert manifest["roster"] == ["reviewer"]  # chunk is always single-pass
        assert manifest["commit_reviewed"] == head
        assert manifest["base_commit"] == head
        assert manifest["head_commit"] is None  # dirty tree — not a commit
        assert manifest["base_tree"] != manifest["head_tree"]
        assert manifest["files_changed"] == ["src/app.py"]
        assert manifest["files_reviewed"] == ["src/app.py"]
        assert manifest["scope"] == "demo" and manifest["chunk"] == "03"
        # The marker is set (the session-mutation guard rides the dispatch).
        assert (repo / MARKER_REL).is_file()
        # And the working tree/index were not touched by the capture (R1) —
        # the only status delta is .prawduct/ turning visible (the manifest
        # landed in the previously-empty untracked dir).
        status_after = _git(repo, "status", "--porcelain").stdout
        delta = set(status_after.splitlines()) - set(status_before.splitlines())
        assert delta <= {"?? .prawduct/"}, f"capture mutated the session: {delta}"

    def test_final_small_single_pass_large_coordinator(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "final")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["roster"] == ["reviewer"], "1 file < threshold → single-pass"

        # Widen past the judgeable threshold — same mode now goes coordinator
        # on volume alone, with no risk surface anywhere in the diff.
        for i in range(cc.COORDINATOR_JUDGEABLE_THRESHOLD):
            p = repo / f"src/mod_{i}.py"
            p.write_text(f"y = {i}\n")
        result = _run_begin(repo, "--mode", "final", "--tier", "escalate")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["roster"] == ["correctness", "design", "sustainability"]
        assert str(cc.COORDINATOR_JUDGEABLE_THRESHOLD) in manifest["roster_chosen_by"]
        assert manifest["tier"] == "escalate"


class TestRosterKeyedToRiskSurface:
    """Roster derivation asks a RISK question, not a size question.

    Established by replaying all 82 final/cumulative review facts in the
    evidence store: keying to judgeable file count at any threshold would have
    sent 54% of historical blocking findings to a single reviewer, because the
    record-heavy diffs it demotes are governance diffs — 20 such reviews carried
    17 blocking findings, 13 pointing at code. See the roster config block in
    lib/critic_consolidate.py for the full table.
    """

    def _roster(self, tmp_path, files, mode="final", declare=True):
        """Roster for ``files``.

        ``declare=True`` writes a `risk_surfaces:` list that the test diffs do
        NOT match, so the repo has opted into the risk-keyed rule and the
        risk predicate is genuinely "on but not matched" — the state that
        exercises the judgeable-volume branch. ``declare=False`` leaves the
        repo undeclared, which is the product case that keeps the prior rule.
        """
        prawduct_dir = tmp_path / ".prawduct"
        prawduct_dir.mkdir(exist_ok=True)
        state = prawduct_dir / "project-state.yaml"
        if declare:
            state.write_text("risk_surfaces:\n  - untouched/by/these/tests/\n")
        elif state.exists():
            state.unlink()
        return cc._derive_roster(mode, list(files), prawduct_dir)

    def test_risk_surface_forces_coordinator_at_any_size(self, tmp_path):
        """A one-file gate-kernel change outranks every size rule.

        The live counter-example this rule exists for: the AST free-edge
        relaxation changed 3 judgeable files (5 total) and the coordinator
        returned 10 blocking findings, including "the gate can now relax itself
        with no way to detect it". Every judgeable-count rule reviews it
        single-pass.
        """
        roster, why = self._roster(tmp_path, ["plugin/lib/gates.py"], declare=False)
        assert roster == ["correctness", "design", "sustainability"], why
        assert "risk surface" in why

    def test_record_heavy_diff_is_not_demoted_when_it_touches_the_kernel(self, tmp_path):
        """The exact shape the rejected spec would have demoted: few judgeable
        files, many records — which is what a governance change looks like."""
        files = [
            "plugin/lib/gates.py",
            "plugin/lib/coverage_algebra.py",
            ".prawduct/backlog.md",
            ".prawduct/change-log.md",
            ".prawduct/artifacts/build-plan-x.md",
        ]
        roster, why = self._roster(tmp_path, files, declare=False)
        assert roster == ["correctness", "design", "sustainability"], why

    def test_no_risk_surface_below_threshold_is_single_pass(self, tmp_path):
        """The one band the replay clears: 5-11 judgeable files touching no
        risk surface is 13 historical coordinator reviews with ZERO blocking
        findings."""
        files = [f"src/mod_{i}.py" for i in range(8)]
        roster, why = self._roster(tmp_path, files)
        assert roster == ["reviewer"], why
        assert "judgeable" in why

    def test_volume_alone_escalates_at_the_threshold(self, tmp_path):
        n = cc.COORDINATOR_JUDGEABLE_THRESHOLD
        below, why_below = self._roster(tmp_path, [f"src/m{i}.py" for i in range(n - 1)])
        at, why_at = self._roster(tmp_path, [f"src/m{i}.py" for i in range(n)])
        assert below == ["reviewer"], why_below
        assert at == ["correctness", "design", "sustainability"], why_at

    def test_records_do_not_count_toward_the_volume_escalator(self, tmp_path):
        """Judgeability is the right question for the SIZE half — a diff of 30
        records with no code is not 30 files of review work. It is the wrong
        question for the RISK half, which is why risk is asked first."""
        files = [f".prawduct/artifacts/doc-{i}.md" for i in range(30)]
        roster, why = self._roster(tmp_path, files)
        assert roster == ["reviewer"], why

    def test_undeclared_repo_keeps_the_prior_file_count_rule(self, tmp_path):
        """The product case, and the reason the risk-keyed rule is gated.

        An as-scaffolded product declares no `risk_surfaces:` and its
        boundary-patterns template yields no parseable paths, so the
        framework-shaped derived defaults match nothing in its tree. If "no
        surface matched" fell straight through to judgeable volume, the
        effective product rule would be `judgeable >= 12` alone — the row the
        replay rejected at 54% of historical blockers demoted — and it would
        REPLACE a rule that gave that product a coordinator at 5 files.

        So an undeclared repo keeps the prior escalator unchanged.
        """
        files = [f"src/mod_{i}.py" for i in range(6)]  # 6 judgeable, < 12
        roster, why = self._roster(tmp_path, files, declare=False)
        assert roster == ["correctness", "design", "sustainability"], why
        assert "prior rule retained" in why

    def test_undeclared_repo_below_the_prior_threshold_is_single_pass(self, tmp_path):
        roster, why = self._roster(tmp_path, ["src/a.py", "src/b.py"], declare=False)
        assert roster == ["reviewer"], why
        assert "prior rule retained" in why

    def test_declared_empty_is_no_signal_not_an_opt_in(self, tmp_path):
        """Pins a DELIBERATE asymmetry between two readers of one key.

        ``resolve_surfaces`` tests ``declared is not None`` (an empty list is an
        exclusive opt-out, so no surface ever matches). ``has_product_risk_
        declaration`` tests truthiness, so ``risk_surfaces: []`` reads as *no
        signal* and the conservative file-count rule is retained.

        The obvious tidy-up — aligning the two for symmetry — would turn the
        opt-out into "risk-keyed rule with an empty surface list", i.e.
        single-pass for every final/cumulative under 12 judgeable files, which
        is the rejected rule reached by accident. This test is what fails first.
        """
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))
        from lib import risk as risk_mod

        prawduct_dir = tmp_path / ".prawduct"
        prawduct_dir.mkdir(exist_ok=True)
        (prawduct_dir / "project-state.yaml").write_text("risk_surfaces: []\n")

        assert risk_mod.has_product_risk_declaration(prawduct_dir) is False

        # …and it stays False even with a FILLED boundary-patterns.md. A present
        # `risk_surfaces:` key is exclusive in resolve_surfaces, so if this fell
        # through to boundary paths the repo would report "has a signal" while
        # its surface set is empty — the predicate could never fire, the
        # conservative fallback would be skipped, and judgeable-volume alone
        # would decide. That is the rejected rule reached by accident.
        (prawduct_dir / "artifacts").mkdir(exist_ok=True)
        (prawduct_dir / "artifacts" / "boundary-patterns.md").write_text(
            "The shared contract is `src/api/contract.py`.\n"
        )
        assert risk_mod.has_product_risk_declaration(prawduct_dir) is False
        roster_again, why_again = cc._derive_roster(
            "final", [f"src/m{i}.py" for i in range(6)], prawduct_dir
        )
        assert roster_again == ["correctness", "design", "sustainability"], why_again
        assert "prior rule retained" in why_again
        # …while resolve_surfaces still treats it as an exclusive declaration.
        surfaces, source = risk_mod.resolve_surfaces(prawduct_dir)
        assert surfaces == [] and source == risk_mod.SOURCE_DECLARED

        roster, why = cc._derive_roster(
            "final", [f"src/m{i}.py" for i in range(6)], prawduct_dir
        )
        assert roster == ["correctness", "design", "sustainability"], why
        assert "prior rule retained" in why

    def test_a_documented_contract_surface_is_not_consent_to_less_review(self, tmp_path):
        """`boundary-patterns.md` escalates but can never relax.

        `discovery.md` asks every contract-bearing product to fill that file. If
        those paths counted as a risk declaration, merely documenting your API
        would opt you into the 12-judgeable threshold and skip the conservative
        fallback — so a 6-file diff touching no contract path would go from
        coordinator to single-pass, silently, while four instruction surfaces
        promise an undeclared repo is never reviewed less than before.

        Escalating is a safe inference from a documented contract; relaxing is
        not. The paths still feed resolve_surfaces, so they still escalate.
        """
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (prawduct_dir / "artifacts" / "boundary-patterns.md").write_text(
            "The shared shape is `src/api/contract.py`.\n"
        )
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))
        from lib import risk as risk_mod

        assert risk_mod.has_product_risk_declaration(prawduct_dir) is False
        roster, why = cc._derive_roster(
            "final", [f"src/m{i}.py" for i in range(6)], prawduct_dir
        )
        assert roster == ["correctness", "design", "sustainability"], why
        assert "prior rule retained" in why

        # …but the documented contract path still ESCALATES at any size.
        hot, why_hot = cc._derive_roster(
            "final", ["src/api/contract.py"], prawduct_dir
        )
        assert hot == ["correctness", "design", "sustainability"], why_hot

    def test_declaring_surfaces_opts_into_the_risk_keyed_rule(self, tmp_path):
        """The same 6-file diff reviews single-pass once the repo has said where
        its risk lives — the saving is bought by the declaration, not assumed."""
        prawduct_dir = tmp_path / ".prawduct"
        prawduct_dir.mkdir(exist_ok=True)
        (prawduct_dir / "project-state.yaml").write_text(
            "risk_surfaces:\n  - src/payments/\n"
        )
        files = [f"src/mod_{i}.py" for i in range(6)]
        roster, why = cc._derive_roster("final", files, prawduct_dir)
        assert roster == ["reviewer"], why
        assert "prior rule retained" not in why

    def test_this_repo_declares_its_surfaces(self):
        """The framework repo must opt in, or its own replay describes a rule it
        does not run. Fails if the declaration is dropped from project-state."""
        import sys
        repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(repo_root / "plugin"))
        from lib import risk as risk_mod
        assert risk_mod.has_product_risk_declaration(repo_root / ".prawduct")
        surfaces, source = risk_mod.resolve_surfaces(repo_root / ".prawduct")
        assert source == risk_mod.SOURCE_DECLARED
        # Declared list must still cover the framework's own machinery, or the
        # opt-in would silently change which reviews escalate.
        for real in ("plugin/lib/gates.py", "plugin/bin/prawduct-hook",
                     "plugin/skills/critic/SKILL.md"):
            assert risk_mod.surface_matches([real], surfaces), real

    def test_declared_risk_surfaces_override_the_defaults(self, tmp_path):
        """A product repo's own hot spots decide, per the resolution order."""
        prawduct_dir = tmp_path / ".prawduct"
        prawduct_dir.mkdir(exist_ok=True)
        (prawduct_dir / "project-state.yaml").write_text(
            "risk_surfaces:\n  - src/payments/\n"
        )
        hot, why_hot = cc._derive_roster("final", ["src/payments/charge.py"], prawduct_dir)
        assert hot == ["correctness", "design", "sustainability"], why_hot
        # …and the framework defaults stop applying entirely when declared.
        cold, why_cold = cc._derive_roster("final", ["plugin/lib/gates.py"], prawduct_dir)
        assert cold == ["reviewer"], why_cold

    def test_single_pass_modes_are_unchanged(self, tmp_path):
        """Regression: chunk and verify-resolutions never go coordinator, no
        matter what the diff touches."""
        for mode in ("chunk", "verify-resolutions"):
            roster, why = self._roster(
                tmp_path, ["plugin/lib/gates.py"] + [f"src/m{i}.py" for i in range(40)],
                mode=mode,
            )
            assert roster == ["reviewer"], f"{mode}: {why}"
            assert "always single-pass" in why

    def test_cumulative_mode_uses_merge_base(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        base_head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _git(repo, "checkout", "-q", "-b", "feature/demo")
        feat_head = _commit_file(repo, "src/feat.py", "z = 1\n", "feature work")
        (repo / ".prawduct").mkdir()
        result = _run_begin(repo, "--mode", "cumulative")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["base_commit"] == base_head
        assert manifest["base_reviewed"] == base_head
        assert manifest["head_commit"] == feat_head  # committed bundle IS the scope
        assert manifest["files_changed"] == ["src/feat.py"]
        expected_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        assert manifest["head_tree"] == expected_tree

    def test_empty_diff_refused_for_non_verify_modes(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        result = _run_begin(repo, "--mode", "chunk")  # clean tree, nothing to review
        assert result.returncode == 1
        assert "empty diff" in result.stderr
        assert not (repo / PARTIALS_REL).exists()

    def test_unknown_mode_token_rejected(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        result = _run_begin(repo, "--mode", "thorough")
        assert result.returncode == 1
        assert "unknown mode token" in result.stderr

    def test_begin_clears_leftover_partials(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        stale = repo / PARTIALS_REL
        stale.mkdir(parents=True)
        (stale / "correctness.json").write_text("{}")
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "leftover" in result.stdout
        assert not (stale / "correctness.json").exists()
        assert (stale / "manifest.json").is_file()


class TestVerifyResolutionsDispatch:
    def _seed_and_fix(self, repo: Path) -> tuple[str, str]:
        """Prior review fact (with a blocker) at the initial commit's REAL
        tree, then a fix lands in the working tree. Returns (initial head,
        prior id)."""
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        (repo / ".prawduct").mkdir(exist_ok=True)
        prior_id = _seed_prior_review_with_blocker(
            repo, head, head_tree=head_tree, head_commit=head
        )
        (repo / "src/app.py").write_text("x = 2  # fixed\n")
        return head, prior_id

    def test_verify_anchors_to_prior_fact_tree(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head, prior_id = self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        prior_fact = next(f for f in _store_facts(repo, "review") if f["id"] == prior_id)
        # The delta edge chains from the tree the prior review actually saw —
        # dirty-tree verify is sound under tree keying (no "commit first" rule).
        assert manifest["base_tree"] == prior_fact["body"]["head_tree"]
        assert manifest["roster"] == ["reviewer"]
        assert "src/app.py" in manifest["files_reviewed"]

    def test_verify_without_prior_fact_fails_for_demotion(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 1
        assert "no prior review" in result.stderr

    def _seed_commit_then_fix_with_dirty_wip(self, repo: Path) -> tuple[str, str]:
        """Prior review at the initial commit; the fix is COMMITTED (a real
        committed delta since the prior review), then a judgeable uncommitted
        file dirties the tree. Returns (fix commit sha, prior id)."""
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        (repo / ".prawduct").mkdir(exist_ok=True)
        prior_id = _seed_prior_review_with_blocker(
            repo, head, head_tree=head_tree, head_commit=head
        )
        fix = _commit_file(repo, "src/app.py", "x = 2  # fixed\n", "fix blocker")
        (repo / "src/extra.py").write_text("y = 3\n")  # judgeable uncommitted WIP
        return fix, prior_id

    def test_committed_fix_with_dirty_wip_anchors_committed_head(self, tmp_path):
        # CRT-7H2W: with a committed delta since the prior review, the head
        # anchors COMMITTED HEAD (the PR-gate target), not the dirty working
        # tree — so a stray judgeable uncommitted file no longer leaves the PR
        # gate uncovered after a successful verify-resolutions.
        repo = tmp_path / "r"
        _init_repo(repo)
        fix, prior_id = self._seed_commit_then_fix_with_dirty_wip(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        committed_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        assert manifest["head_commit"] == fix          # committed HEAD, not None
        assert manifest["head_tree"] == committed_tree  # committed tree, not working
        prior_fact = next(f for f in _store_facts(repo, "review") if f["id"] == prior_id)
        assert manifest["base_tree"] == prior_fact["body"]["head_tree"]
        # The dirty-but-anchored-to-committed-HEAD diagnostic note fires.
        assert "anchored to committed HEAD" in result.stderr

    def test_uncommitted_fix_keeps_working_tree_anchor(self, tmp_path):
        # Case (b): no committed delta — the fix is still in the working tree.
        # The anchor stays the working tree (head_commit None) so the Stop-hook
        # gate composes and the PR gate legitimately stays pending (CRT-4J8W
        # dirty-tree verify preserved).
        repo = tmp_path / "r"
        _init_repo(repo)
        head, _prior_id = self._seed_and_fix(repo)  # fix left UNCOMMITTED
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["head_commit"] is None  # dirty tree, no committed delta
        # The judgeable-WIP "uncovered until you commit" WARNING fires so the
        # working-tree-vs-committed-HEAD mismatch is surfaced, not silent.
        assert "vouches for the WORKING tree" in result.stderr

    def test_verify_scope_widened_exits_2(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head, _prior_id = self._seed_and_fix(repo)
        # Blow the scope past 2 * len(prior) + 5.
        for i in range(2 * 1 + 6):
            (repo / f"src/new_{i}.py").write_text(f"n = {i}\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert "scope-widened" in result.stderr


class TestWorktreeVisibility:
    """PDT-WT9K — the review makes its resolved target VISIBLE, and refuses when
    the shell's repo differs from the resolved tree (never a silent wrong tree)."""

    def test_manifest_carries_worktree_and_branch(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)  # -b main
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")  # a chunk diff
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert Path(manifest["worktree"]).name == "r"
        assert manifest["branch"] == "main"
        # The dispatch print names the tree so a wrong one is obvious.
        assert "reviewing worktree" in result.stdout
        assert "branch main" in result.stdout

    def test_refuses_when_cwd_repo_differs_from_resolved(self, tmp_path):
        # Shell in repo A, but CLAUDE_PROJECT_DIR pinned to a DIFFERENT repo B —
        # the review would target B while you work in A. Refuse loudly.
        repo_a = tmp_path / "a"
        _init_repo(repo_a)
        _commit_file(repo_a, "a.py", "x = 1\n", "a")
        repo_b = tmp_path / "b"
        _init_repo(repo_b)
        _commit_file(repo_b, "b.py", "y = 1\n", "b")
        (repo_b / ".prawduct").mkdir()  # onboarded, so we reach the refuse
        (repo_b / "b.py").write_text("y = 2\n")
        result = subprocess.run(
            ["python3", str(HOOK), "critic-begin", "--mode", "chunk"],
            cwd=str(repo_a), capture_output=True, text=True,
            env={**_git_env(repo_a), "CLAUDE_PLUGIN_ROOT": str(ROOT),
                 "CLAUDE_PROJECT_DIR": str(repo_b)}, timeout=30,
        )
        assert result.returncode == 1
        assert "refusing" in result.stderr
        # And no manifest was written for the wrong tree.
        assert not (repo_b / PARTIALS_REL / "manifest.json").exists()

    def test_same_worktree_does_not_refuse(self, tmp_path):
        # The common case: cwd IS the resolved tree — no refuse.
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "refusing" not in result.stderr
        assert (repo / PARTIALS_REL / "manifest.json").exists()

    def test_detached_head_records_null_branch(self, tmp_path):
        # gitstate.current_branch returns None on a detached HEAD (an honest
        # null, not a misleading guess), so the manifest carries branch: null
        # and validate_manifest accepts it — the case current_branch exists for.
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        _git(repo, "checkout", "--quiet", head)  # detach HEAD
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["branch"] is None
        assert "(detached)" in result.stdout


class TestRecordLintInManifest:
    """Record checks are answered at DISPATCH and carried in the manifest, so a
    reviewer reads the result instead of re-deriving it — and the control's own
    yield rides into the review fact, where it can be queried rather than
    argued about (`nonfunctional-requirements.md` § Direction)."""

    def _dispatch(self, tmp_path, plan: str | None = None):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct" / "artifacts").mkdir(parents=True)
        (repo / ".prawduct" / "project-state.yaml").write_text("project_name: t\n")
        if plan is not None:
            (repo / ".prawduct" / "artifacts" / "build-plan.md").write_text(plan)
        _commit_file(repo, ".prawduct/keep", "", "seed prawduct")
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        return repo, manifest, result

    def test_manifest_carries_a_record_lint_block(self, tmp_path):
        _repo, manifest, _res = self._dispatch(tmp_path)
        lint = manifest["record_lint"]
        assert set(lint) == {"records", "chunk_graded", "findings", "unchecked", "counts"}
        # Every check is present with an explicit tally, so a zero is visibly a
        # zero rather than a key a consumer has to interpret.
        assert set(lint["counts"]) == set(record_lint.CHECKS)

    def test_a_missing_declared_deliverable_lands_in_the_manifest(self, tmp_path):
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n"
            "- **Deliverables:** `src/never_built.py`\n"
        )
        _repo, manifest, result = self._dispatch(tmp_path, plan)
        findings = manifest["record_lint"]["findings"]
        assert [f["check"] for f in findings] == ["chunk-ref-missing"]
        assert "src/never_built.py" in findings[0]["detail"]
        # The dispatching agent sees it without opening the manifest.
        assert "record-lint" in result.stdout
        assert "src/never_built.py" in result.stdout

    def test_lint_findings_do_not_gate(self, tmp_path):
        """Advice, not authority: a lint finding never blocks dispatch and never
        reaches the fact's severity counts."""
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n"
            "- **Deliverables:** `src/never_built.py`\n"
        )
        _repo, manifest, result = self._dispatch(tmp_path, plan)
        assert result.returncode == 0
        assert manifest["record_lint"]["findings"], "the finding exists…"
        body = cc.build_fact_body(manifest, [])
        assert body["counts"] == {"blocking": 0, "warning": 0, "note": 0}
        assert body["findings"] == []

    def test_the_fact_carries_the_yield(self, tmp_path):
        """The observable-yield obligation: a control born after 2026-07-29
        must leave something queryable behind, not printed output."""
        _repo, manifest, _res = self._dispatch(tmp_path)
        body = cc.build_fact_body(manifest, [])
        assert body["record_lint"] == manifest["record_lint"]

    def test_an_absent_lint_block_does_not_break_the_fact(self, tmp_path):
        """A manifest written by an older dispatch carries no `record_lint`;
        the fact records None rather than failing to build."""
        _repo, manifest, _res = self._dispatch(tmp_path)
        manifest.pop("record_lint")
        assert cc.build_fact_body(manifest, [])["record_lint"] is None


# ---------------------------------------------------------------------------
# The D8 acceptance invariant: nothing in the write path parses model-authored
# JSON except the partials — a full cycle driven ONLY by code + partials.
# ---------------------------------------------------------------------------


class TestDeterministicCycleEndToEnd:
    def test_begin_partials_consolidate_full_cycle(self, tmp_path):
        """The chunk's acceptance scenario: begin → partials → consolidate
        produces exactly one fact and one cache, whether consolidate fires
        once or twice; no model-written manifest exists anywhere in the
        flow (the only hand-written JSON is the reviewer partial)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")

        begin = _run_begin(repo, "--mode", "chunk", "--chosen-by", "rule-4",
                           "--scope", "demo")
        assert begin.returncode == 0, f"stderr={begin.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        review_id = manifest["id"]

        # The single-pass reviewer writes its one partial (the judgment payload).
        _write_partial(repo, "reviewer", manifest["commit_reviewed"])

        first = _run_consolidate(repo)
        assert first.returncode == 0, f"stderr={first.stderr!r}"
        second = _run_consolidate(repo)  # straggler/backstop double-fire
        assert second.returncode == 0

        assert len(_store_lines(repo)) == 1
        fact = _store_facts(repo, "review")[0]
        assert fact["id"] == review_id
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["fact_id"] == review_id
        assert gates.validate_critic_findings(repo / FINDINGS_REL)
        assert not (repo / PARTIALS_REL).exists()
        assert not (repo / MARKER_REL).is_file()

        # The derived view always carries the advisory grouping key, empty when
        # nothing looks duplicated — a reader can distinguish "no duplicates"
        # from "this plugin predates the check" without guessing.
        assert record["likely_duplicate_groups"] == []
        # With no groups the summary carries no duplicate note and no stray
        # spacing where the clause would have gone.
        assert "distinct" not in first.stdout
        assert "note from" in first.stdout

    def test_consolidate_reports_a_likely_duplicate_group(self, tmp_path):
        """The user-facing half of the double-counting fix: two reviewers
        describing ONE defect under different goals both survive the merge (the
        key cannot collide across disjoint goal sets), so consolidation says so
        rather than letting the raw count read as two defects."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)

        same_defect = [
            {
                "name": "A clean review's census renders a truncated sentence",
                "goal": "Nothing Is Broken",
                "severity": "note",
                "recommendation": "guard the summary clause",
                "files": ["src/app.py"],
            }
        ]
        _write_partial(repo, "correctness", head, findings=same_defect)
        _write_partial(
            repo,
            "design",
            head,
            findings=[
                {
                    "name": "A clean review renders a malformed census summary line",
                    "goal": "The Design Is Sound",
                    "severity": "note",
                    "recommendation": "guard the summary clause",
                    "files": ["src/app.py"],
                }
            ],
        )
        _write_partial(repo, "sustainability", head, findings=[])

        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        # Both findings are kept — advisory detection never drops one.
        fact = _store_facts(repo, "review")[0]
        assert len(fact["body"]["findings"]) == 2
        assert fact["body"]["counts"]["note"] == 2
        # ...and the count is reported alongside an honest distinct count.
        assert "~1 distinct" in result.stdout
        assert "likely-duplicate group(s): R-1+R-2" in result.stdout
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["likely_duplicate_groups"] == [["R-1", "R-2"]]


class TestLikelyDuplicateGroups:
    """A finding count is not a defect count.

    `merge_findings` keys on `(goal, name, files)`, and the coordinator's goal
    sets are disjoint by construction — each reviewer is told to review ONLY
    its goals — so two reviewers meeting one defect always produce two findings
    that no exact key can collapse. Detection is therefore advisory: it reports
    groups and never drops a finding, because a fuzzily-dropped real finding is
    invisible in the output and strictly worse than over-counting.
    """

    @staticmethod
    def _f(fid, goal, title, files=None):
        entry = {"fid": fid, "goal": goal, "severity": "note", "title": title}
        if files:
            entry["files"] = files
        return entry

    def test_the_real_cross_goal_duplicate_is_grouped(self):
        """The pair that prompted this, verbatim from review
        rev-20260729T230420Z-71b7f129 (similarity 0.44)."""
        findings = [
            self._f(
                "R-7",
                "Nothing Is Broken",
                "A clean review's census renders a truncated sentence",
                ["plugin/lib/dispositions.py"],
            ),
            self._f(
                "R-13",
                "The Design Is Sound",
                "A clean review renders a malformed census summary line",
                ["plugin/lib/dispositions.py", "tests/test_dispositions.py"],
            ),
        ]
        groups = cc.likely_duplicate_groups(findings)
        assert groups == [["R-7", "R-13"]]
        assert cc.distinct_finding_count(findings, groups) == 1

    def test_same_goal_is_never_grouped(self):
        """Same goal means one reviewer, which means deliberately distinct
        findings — not a merge failure."""
        findings = [
            self._f("R-1", "Nothing Is Broken", "The census renders a truncated sentence"),
            self._f("R-2", "Nothing Is Broken", "The census renders a truncated sentence"),
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_disjoint_files_are_never_grouped(self):
        findings = [
            self._f("R-1", "Nothing Is Broken", "The census renders a truncated line", ["a.py"]),
            self._f("R-2", "The Design Is Sound", "The census renders a truncated line", ["b.py"]),
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_unrelated_titles_are_never_grouped(self):
        findings = [
            self._f("R-1", "Nothing Is Broken", "Store readers raise on a malformed body"),
            self._f("R-2", "The Design Is Sound", "Exit codes absent from the contract table"),
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_grouping_is_transitive_across_three_reviewers(self):
        """One defect found by all three reviewers is ONE group, not three
        pairs — otherwise the distinct count over-corrects."""
        title = "The digest topic roster still omits the norms topic entirely"
        findings = [
            self._f("R-1", "Nothing Is Broken", title),
            self._f("R-2", "The Design Is Sound", title),
            self._f("R-3", "Everything Is Coherent", title),
        ]
        groups = cc.likely_duplicate_groups(findings)
        assert groups == [["R-1", "R-2", "R-3"]]
        assert cc.distinct_finding_count(findings, groups) == 1

    def test_nothing_is_dropped_or_reordered(self):
        """The advisory contract: detection must not mutate the finding list."""
        findings = [
            self._f("R-1", "Nothing Is Broken", "A clean review renders a truncated census line"),
            self._f("R-2", "The Design Is Sound", "A clean review renders a malformed census line"),
        ]
        before = [dict(f) for f in findings]
        cc.likely_duplicate_groups(findings)
        assert findings == before

    def test_malformed_findings_do_not_raise(self):
        findings = [
            "not a dict",
            {"goal": "g", "title": "t"},          # no fid
            {"fid": "  ", "goal": "g", "title": "t"},
            {"fid": "R-1", "goal": "g"},          # no title
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_distinct_count_with_no_groups_is_the_raw_count(self):
        findings = [self._f("R-1", "g", "alpha beta gamma"), self._f("R-2", "h", "delta epsilon zeta")]
        assert cc.distinct_finding_count(findings, []) == 2
