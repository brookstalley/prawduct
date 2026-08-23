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
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
sys.path.insert(0, str(ROOT))
from lib import critic_consolidate as cc  # noqa: E402
# The anchor predicates the dispatch guard is built on. Imported rather than
# re-implemented so a test asserting "the OLD guard would have passed" is
# asserting it about the real one.
from lib.critic_mode import _commit_is_ancestor, _commit_resolves  # noqa: E402
from lib import evidence  # noqa: E402
from lib import gates  # noqa: E402
from lib import record_lint  # noqa: E402
from lib import telemetry  # noqa: E402

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
        "id": FAKE_REVIEW_ID,
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
    # Derived last so an overridden roster or id still gets a consistent
    # rendezvous — the real `begin_review` resolves these the same way, and a
    # manifest whose rendezvous disagrees with its roster is invalid by design.
    manifest.setdefault("rendezvous", {
        role: {
            "partial": f"{PARTIALS_REL}/{role}.{manifest['id']}.json",
            "started": f"{PARTIALS_REL}/{role}.{manifest['id']}.started",
        }
        for role in manifest["roster"]
    })
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


def _abandon(repo: Path) -> subprocess.CompletedProcess:
    """Abandon the dispatched review — the real lifecycle step between two
    dispatches, now that `critic-begin` refuses to displace a live one.

    A test that dispatches twice is testing something about the SECOND dispatch
    (roster derivation, superseded re-stamping); it is not asserting that an
    unguarded concurrent dispatch is allowed. Going through `critic-end` is what
    a caller genuinely does, so the setup models the lifecycle instead of a path
    the guard now refuses."""
    return subprocess.run(
        ["python3", str(HOOK), "critic-end"],
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


FAKE_REVIEW_ID = "rev-test-0001"

from conftest import V2_MANIFEST as _V2_MANIFEST  # noqa: E402 — one home (R-8)


def _review_id(repo: Path) -> str:
    """The id of the review currently on disk.

    A partial is keyed by the review that dispatched it, so a test that wrote a
    real manifest (via `critic-begin`) must write its partial under that
    review's id or the consolidator will not look at it. Falls back to the id
    `_manifest_dict` mints for the many tests that hand-write a manifest."""
    try:
        return json.loads((_partials_dir(repo) / "manifest.json").read_text())["id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return FAKE_REVIEW_ID


def _partial(role: str, head: str, findings=None, *,
             dispatch_id: str = FAKE_REVIEW_ID, **overrides) -> dict:
    data = {
        "role": role,
        "goals": "1-3",
        "dispatch_id": dispatch_id,
        "commit_reviewed": head,
        "model": "opus",
        "duration_seconds": 90,
        "findings": findings if findings is not None else [],
        "summary": f"{role} review complete.",
    }
    data.update(overrides)
    return data


def _write_partial(repo: Path, role: str, head: str, **kwargs) -> None:
    """Write `role`'s partial where the review on disk expects it."""
    rid = kwargs.pop("dispatch_id", None) or _review_id(repo)
    (_partials_dir(repo) / f"{role}.{rid}.json").write_text(
        json.dumps(_partial(role, head, dispatch_id=rid, **kwargs))
    )


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
        ok, reason = cc.validate_manifest({**_V2_MANIFEST, "mode": FINAL_MODE})
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
        # The builder's copy of the termination rule rides in the same record.
        assert "next_action" in record


class TestNextActionLine:
    """``.critic-findings.json`` is the one carrier of the loop-termination
    rule that has a reader in the BUILDER role.

    ``methodology/building.md`` states the rule but is reached only by entering
    a build plan; ``review-cycle.md`` is read by nobody building; and
    ``_BATCH_FIX_DIRECTIVE`` prints wherever ``critic-consolidate`` runs, which
    on the always-single-pass modes is the reviewing FORK. Measured on the
    consumer branch that ran ten rounds: zero reads of either prose file, zero
    occurrences of the directive in the builder's context against seven inside
    reviewer forks — and the builder did read the findings. So the field must
    say what gates, in the record the builder already opens."""

    def test_the_free_write_question_is_delegated_not_restated(self):
        """The zero-blocking line tells a builder which batches need no verify
        pass. It used to answer that by ENUMERATING the free paths — a prose
        copy of a rule owned by `coverage_algebra.is_judgeable_path`, which the
        builder then had to match against their own batch by hand, and which
        went stale the moment `METADATA_PREFIXES` moved.

        It now cites `cost-of-commit`, which asks that classifier about the
        exact paths in hand. So the pin changes shape with the message: the
        message must NAME the command, and it must not have grown a second
        authoritative copy of the carve-out. Nothing here can drift from the
        classifier, because nothing here restates it.

        The command being named must also exist — a message citing a command
        the hook does not dispatch is worse than the list it replaced.
        """
        line = cc.next_action_line("rev-1", 0, 1, 1)
        assert "prawduct-hook cost-of-commit" in line
        assert "needs no pass at all" in line
        # The enumeration is what was deleted; its return would reintroduce the
        # drift this delegation removes.
        for carve_out in ("`.prawduct/` prose", "`.claude/settings.json`", "`templates/`"):
            assert carve_out not in line, (
                f"{carve_out!r} is back in next_action_line — the free-path rule has "
                "one home (`coverage_algebra.is_judgeable_path`) and this message "
                "asks it via `cost-of-commit` rather than copying it"
            )
        hook = (ROOT / "bin" / "prawduct-hook").read_text()
        assert '"cost-of-commit"' in hook, (
            "next_action_line cites `prawduct-hook cost-of-commit`, which the hook "
            "no longer dispatches"
        )

    def test_blocking_names_one_commit_and_one_verify_pass(self):
        line = cc.next_action_line("rev-1", 2, 5, 3)
        assert "2 BLOCKING" in line
        assert "ONE commit" in line
        assert "ONE `/prawduct:critic verify-resolutions`" in line
        # The non-blocking findings are decided in the SAME pass — deferring
        # them to a later round is the pump this field exists to stop.
        assert "SAME pass" in line

    def test_the_blocking_arm_reaches_parity_with_the_zero_blocking_arm(self):
        """Reporter failure 1, read against the two arms: *"it stated a rule,
        not a price. I never saw a number."*

        The blocking arm ordered the builder to decide the WARNING/NOTE
        findings in the same pass, but the command for the cheapest of those
        decisions — and any statement of what a round costs — lived only in the
        arm a builder with a blocking finding never reaches. Both are now on
        both arms.
        """
        priced = "One more round costs about 5 min here (median of 9 rounds)."
        line = cc.next_action_line("rev-9", 3, 2, 1, priced)
        assert 'prawduct-hook disposition rev-9 <fid> --accept "<reason>"' in line
        assert "moves no tree" in line
        assert priced in line

    def test_both_arms_quote_the_same_price_sentence(self):
        priced = "One more round costs about 5 min here (median of 9 rounds)."
        for counts in ((2, 1, 1), (0, 1, 1)):
            assert priced in cc.next_action_line("rev-9", *counts, priced), counts

    def test_an_unavailable_price_is_relayed_rather_than_dropped(self):
        """The helper's unavailable sentence is a first-class answer — a
        message that goes quiet when the ledger cannot be read lets the builder
        assume a round is cheap, which is the assumption the whole change
        exists to correct."""
        unavailable = telemetry.format_round_price({"status": "unavailable", "reason": "no history"})
        line = cc.next_action_line("rev-9", 1, 0, 0, unavailable)
        assert "unavailable" in line and "not a small one" in line

    def test_no_price_at_all_still_produces_a_whole_sentence(self):
        """The default path (tests, and any caller without a prawduct dir) must
        not leave a dangling clause or a trailing double space."""
        for counts in ((2, 1, 1), (0, 1, 1), (0, 0, 0)):
            line = cc.next_action_line("rev-9", *counts)
            assert line == line.strip() and "  " not in line, counts
            # "." or the coverage caveat's closing paren — never a dangling
            # connector left behind by the omitted clause.
            assert line.endswith((".", ")")), counts

    def test_both_arms_offer_the_ride_along_route_with_its_condition(self):
        """The fix/accept/file trio was missing the option that costs nothing
        extra: when the branch has more judgeable work coming, a small fix
        carried into the next chunk's commit rides a round that was going to be
        bought anyway.

        Both arms carry it — a builder with a blocking finding still has
        WARNING/NOTE companions to decide, and deferring one IS a decision made
        in that same pass. It ships with its condition ("if this branch has more
        judgeable work coming") because it is not universally right, and with
        its failure mode named, because an unwritten deferral is a drop.
        """
        for counts in ((2, 1, 1), (0, 1, 1)):
            line = cc.next_action_line("rev-9", *counts)
            assert "carry the fix into the NEXT chunk's commit" in line, counts
            assert "if this branch has more judgeable work coming" in line.lower(), counts
            assert "it is not a deferral, it is a drop" in line, counts
            # And it distinguishes itself from the deferral the same message
            # warns against two sentences earlier. Without that, the blocking
            # arm says "deferring turns one review into several" and then
            # offers a deferral — a reader resolves the contradiction by
            # ignoring one of them, and there is no telling which.
            assert "NOT the deferral" in line, counts
            assert "buys a second round" in line and "buys none" in line, counts

    def test_the_clean_pass_is_not_offered_a_route_for_findings_it_lacks(self):
        # 0/0/0 has nothing to carry anywhere; a deferral route on a review with
        # no findings reads as work the builder does not have.
        line = cc.next_action_line("rev-9", 0, 0, 0)
        assert "NEXT chunk's commit" not in line

    def test_zero_blocking_says_the_review_is_over_and_names_disposition(self):
        line = cc.next_action_line("rev-abc", 0, 4, 7)
        assert "THE REVIEW IS OVER" in line
        assert "gate NOTHING" in line
        # The command arrives with this review's own id already substituted —
        # an operator who has to go find the id is one who will not run it.
        assert "prawduct-hook disposition rev-abc <fid> --accept" in line
        assert "4 warning + 7 note" in line
        # And the stale-gate-output trap is named where the decision is made.
        assert "re-run the gate" in line

    def test_clean_pass_has_nothing_to_disposition(self):
        line = cc.next_action_line("rev-1", 0, 0, 0)
        assert "THE REVIEW IS OVER" in line
        assert "nothing" in line
        assert "disposition" not in line.split("nothing to disposition")[-1]

    def test_every_zero_blocking_variant_carries_the_coverage_caveat(self):
        # "The review is over" and "you may merge" are different claims. A
        # clean `chunk` mid-plan still owes a final/cumulative at end of cycle
        # — `_critic_session_satisfies_gate` fires an advisory saying exactly
        # that — so a variant asserting the first without disclaiming the
        # second puts two code-owned surfaces in contradiction, with the newer
        # one saying "stop". The caveat is a shared constant precisely so a
        # branch cannot forget it.
        for counts in ((0, 0, 0), (0, 4, 7), (0, 0, 2), (0, 1, 0)):
            line = cc.next_action_line("rev-1", *counts)
            assert cc._COVERAGE_IS_A_SEPARATE_QUESTION in line, counts

    def test_the_verify_pass_is_conditioned_on_judgeable_files(self):
        # `_BATCH_FIX_DIRECTIVE` prints immediately above this line and
        # conditions the pass on "if that commit touches judgeable files". On
        # framework work the non-blocking findings concentrate in `.prawduct/`
        # prose — all non-judgeable — so the most common fix batch is exactly
        # the one needing no pass, and an unconditional order buys the round
        # this whole change exists to prevent.
        line = cc.next_action_line("rev-1", 0, 3, 0)
        assert "ONLY if that commit touched judgeable files" in line
        assert "needs no pass at all" in line

    def test_missing_fact_id_degrades_to_a_placeholder(self):
        # A record with no id must still produce a runnable-shaped instruction
        # rather than the string "None".
        line = cc.next_action_line(None, 0, 1, 0)
        assert "None" not in line
        assert "<review-id>" in line


class TestNextLineRelayContract:
    """`NEXT-ACTION:` is code-owned and relay-only — the design that made this
    affordable inside two files at their token ceilings.

    The alternative was quoting both gate-line variants in each protocol: ~160
    tokens per file, duplicated, and paraphrasable. Owning the wording in
    :func:`next_action_line` costs ~35 and cannot drift, so the same sentence
    reaches the builder whether they read the fork's report (single-pass) or
    `next_action` in the findings cache (coordinator).

    Both protocols must carry the relay order, because mode decides which one a
    reviewer reads — `goals-1-3.md` for chunk/verify-resolutions,
    `review-protocol.md` for final/cumulative. The measured ten-round loop ran
    on the verify-resolutions path, so pinning only the full protocol would
    leave exactly the observed case uncovered."""

    PROTOCOLS = ("goals-1-3.md", "review-protocol.md")

    def _text(self, name):
        """Wrap- and emphasis-insensitive. These two files are line-wrapped to
        different widths and one bolds inside the clause, so a literal
        substring pin would fail on a re-wrap that changed nothing — the kind
        of false failure that gets a pin deleted rather than fixed."""
        raw = (ROOT / "skills" / "critic" / name).read_text()
        return re.sub(r"\s+", " ", raw.replace("*", "").replace("`", ""))

    def test_both_protocols_order_the_relay(self):
        for name in self.PROTOCOLS:
            text = self._text(name)
            assert "NEXT-ACTION:" in text, name
            assert "verbatim" in text, name

    def test_goals_1_3_relay_survives_the_clean_pass_shorthand(self):
        """The relay order must not sit where the no-findings shorthand can
        swallow it — and `goals-1-3.md` serves the two always-single-pass
        modes, where the measured data put most reviews at zero blocking. So
        the clean pass is the relay's highest-value case, and the one a reader
        is likeliest to shortcut. Modelling the READER, not just the artifact:
        the words being present in the file is what the other pins assert, and
        it is not the same as the instruction having effect."""
        text = self._text("goals-1-3.md")
        shorthand = text.index("No issues found")
        relay = text.index("your last line is consolidate's")
        assert relay > shorthand, (
            "the relay order precedes the no-findings shorthand, so the "
            "shorthand reads as a total replacement and drops the carrier"
        )
        assert "Either way" in text

    def test_both_protocols_say_why_the_relay_is_not_optional(self):
        # Without the reason, a token-diet pass reads the order as redundant
        # with "report to the user" and trims it. The reason is structural:
        # on the single-pass path the reviewer runs consolidate, so its output
        # lands in the reviewer's context and reaches the builder only if
        # relayed.
        for name in self.PROTOCOLS:
            text = self._text(name)
            assert "dies in your context" in text, name
            assert "terminates the review loop" in text, name

    def test_the_prefix_does_not_collide_with_the_standing_block(self):
        # `NEXT` reads as framework vocabulary: the turn-closing standing
        # block (session digest, reflection.md) opens a disposition line with a
        # short backticked label, so a bare `NEXT` near the end of a turn is
        # exactly the shape an agent expects to be a disposition. This line is a paragraph that must be relayed verbatim,
        # so an agent holding both contracts would have a standing instruction
        # to compress the very text it was told to copy.
        for name in self.PROTOCOLS:
            text = self._text(name)
            assert "NEXT-ACTION:" in text, name
            assert re.search(r"(?<!-)\bNEXT:", text) is None, name


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

    def test_wait_side_never_carries_the_fix_strategy(self):
        # The batch directive answers "how do I fix these?"; a caller with no
        # findings in hand yet has not asked it. Emitting it on the wait side
        # would have the reader planning fixes for findings they cannot read.
        for missing, present, total, age in (
            (["correctness"], 1, 3, 2),
            (["reviewer"], 0, 1, 2),
            (["sustainability"], 2, 3, 45),
        ):
            msg = cc._incomplete_noop_message(
                missing, present, total, self._fresh_id(age))
            assert cc._BATCH_FIX_DIRECTIVE not in msg

    # -- per-role started markers (the reviewer-written liveness signal) ------

    def _prawduct_with_started(self, tmp_path, roles_minutes: dict,
                               review_id: str = FAKE_REVIEW_ID) -> Path:
        """A .prawduct dir whose partials dir holds one started marker per
        entry, backdated by the given minutes via mtime. Markers are keyed by
        review id, so they belong to `review_id`'s review and to no other."""
        import os
        prawduct = tmp_path / ".prawduct"
        cc.partials_dir(prawduct).mkdir(parents=True)
        now = datetime.now(timezone.utc).timestamp()
        for role, minutes in roles_minutes.items():
            marker = cc.started_path(prawduct, role, review_id)
            marker.write_text(role)
            os.utime(marker, (now - minutes * 60, now - minutes * 60))
        return prawduct

    def test_started_marker_annotates_the_missing_role(self, tmp_path):
        rid = self._fresh_id(4)
        prawduct = self._prawduct_with_started(tmp_path, {"design": 3.0}, rid)
        msg = cc._incomplete_noop_message(
            ["design", "sustainability"], 1, 3, rid, prawduct)
        assert re.search(r"design \(started 3\.\d min ago\)", msg)
        # No marker → bare role name, no started claim.
        assert "sustainability (started" not in msg

    def test_a_prior_reviews_started_marker_is_not_this_reviews_liveness(self, tmp_path):
        # The reason markers are keyed by review id. An abandoned review's
        # marker under a shared name would age into the NEXT review's verdict
        # and report a reviewer that never started as one at work — the exact
        # false-liveness signal the keying exists to prevent.
        rid = self._fresh_id(4)
        prawduct = self._prawduct_with_started(
            tmp_path, {"design": 3.0}, "rev-20260101T000000Z-0ldrev00")
        msg = cc._incomplete_noop_message(
            ["design", "sustainability"], 1, 3, rid, prawduct)
        assert "design (started" not in msg

    def test_fresh_started_marker_holds_wait_past_dispatch_grace(self, tmp_path):
        # The observed field failure: reviewers (re)started late, so dispatch
        # age blew past the grace window while every reviewer was demonstrably
        # at work. A fresh started marker must keep the verdict on the wait
        # side — dispatch age alone no longer declares death.
        rid = self._fresh_id(45)
        prawduct = self._prawduct_with_started(
            tmp_path, {"correctness": 2.0, "design": 2.0}, rid)
        msg = cc._incomplete_noop_message(
            ["correctness", "design"], 1, 3, rid, prawduct)
        assert "may have died" not in msg
        assert "NOT evidence the reviewers died" in msg

    def test_stale_started_markers_advise_critic_end(self, tmp_path):
        # A reviewer that started long ago and never wrote its partial is the
        # genuine-death case — the marker's own age carries the verdict.
        rid = self._fresh_id(45)
        prawduct = self._prawduct_with_started(tmp_path, {"design": 40.0}, rid)
        msg = cc._incomplete_noop_message(["design"], 2, 3, rid, prawduct)
        assert "may have died" in msg
        assert "critic-end" in msg

    def test_one_fresh_role_holds_the_whole_verdict_on_wait(self, tmp_path):
        # Mixed state: one missing role has a fresh marker, the other none at a
        # stale dispatch. Death advice requires EVERY missing role past grace
        # on its own effective age — a live reviewer will report and shrink
        # `missing`, after which the dead one's age decides alone.
        rid = self._fresh_id(45)
        prawduct = self._prawduct_with_started(tmp_path, {"correctness": 1.0}, rid)
        msg = cc._incomplete_noop_message(
            ["correctness", "design"], 1, 3, rid, prawduct)
        assert "may have died" not in msg

    def test_single_pass_roster_ignores_started_markers(self, tmp_path):
        # The single-pass reviewer IS the dispatching fork — there is no
        # waiting caller mid-review, so the coordinator liveness story (and its
        # markers) must not leak into that message.
        rid = self._fresh_id(2)
        prawduct = self._prawduct_with_started(tmp_path, {"reviewer": 2.0}, rid)
        msg = cc._incomplete_noop_message(["reviewer"], 0, 1, rid, prawduct)
        assert "(started" not in msg
        assert "consolidates when it finishes" in msg

    def test_dispatch_surfaces_route_the_started_marker_through_the_manifest(self):
        # The marker is written by the model, so the instruction lives in prose.
        # It used to name the filename directly, which made the prose a second
        # home for a shape only `started_path` owns. The CONTRACT — not the
        # literal — is what binds: both dispatch surfaces must send the reviewer
        # to the manifest's rendezvous entry, and the manifest must actually
        # carry the path `started_path` reads. Asserting the old literal would
        # now pass on prose that names a path nothing writes.
        agent_doc = (ROOT / "agents" / "critic-reviewer.md").read_text()
        protocol = (ROOT / "skills" / "critic" / "review-protocol.md").read_text()
        for surface, text in (("agent definition", agent_doc), ("protocol", protocol)):
            assert "rendezvous" in text, f"{surface} does not route through the manifest"
            assert "liveness marker" in text, f"{surface} no longer instructs the marker"
        assert "FIRST" in agent_doc
        # The coordinator SUBSTITUTES; it needs a slot per value it substitutes.
        # Trading these for a bare `"rendezvous" in text` was too loose — the
        # template could lose the started-marker slot entirely and still pass on
        # the word appearing in the surrounding sentence.
        for slot in ("<STARTED>", "<PARTIAL>", "<ID>"):
            assert slot in protocol, (
                f"the coordinator prompt template no longer carries {slot} — a "
                "reviewer cannot be told where to write, or which review it is for"
            )
        # The other half of the contract: what begin_review records IS what
        # started_path reads. A rendezvous entry that drifted from the reader
        # would leave the prose correct and the marker unread.
        prawduct = Path("/repo/.prawduct")
        rz = cc._rendezvous(Path("/repo"), prawduct, ["design"], "rev-x-1")
        assert rz["design"]["started"] == str(
            cc.started_path(prawduct, "design", "rev-x-1").relative_to(Path("/repo")))
        assert rz["design"]["partial"] == str(
            cc.partial_path(prawduct, "design", "rev-x-1").relative_to(Path("/repo")))


# ---------------------------------------------------------------------------
# Unit: the batch-fix directive
# ---------------------------------------------------------------------------


#: Every path class the directive can name, mapped to (representative path,
#: expected JUDGEABILITY) — True means "costs a review round", i.e. the directive
#: must place it in the costly clause. Adding a class to the directive without
#: adding it here fails ``test_directive_names_no_unpinned_path_class``, which is
#: the half that makes the drift guard bidirectional.
_DIRECTIVE_PATH_CLASSES = {
    ".prawduct/": (".prawduct/change-log.md", False),
    "`.claude/settings.json`": (".claude/settings.json", False),
    # The suffix class: `.md` OUTSIDE the protected dirs below is free. Product
    # docs and READMEs are the common case, and the whole point of the four
    # protected entries is that they are the exception to this line.
    "`.md`": ("docs/architecture.md", False),
    "`skills/`": ("plugin/skills/critic/review-cycle.md", True),
    "`methodology/`": ("plugin/methodology/building.md", True),
    "`templates/`": ("plugin/templates/runbook.md", True),
    "`CLAUDE.md`": ("CLAUDE.md", True),
}


class TestBatchFixDirective:
    """The directive states which writes are free mid-review. That is a prose
    restatement of ``coverage_algebra.is_judgeable_path``, so these tests parse
    the directive's own text and drive the assertions from it — drift in either
    direction fails, not just a predicate change.

    Why bidirectional matters: asserting hardcoded paths against the predicate
    catches a predicate that narrows, but leaves the cheaper mistake unguarded —
    editing the free-list alone (adding `docs/`, dropping `.claude/settings.json`)
    would keep the suite green while shipping a runtime message that tells a
    builder to commit mid-review and lose their coverage."""

    def test_the_directive_makes_no_positional_cross_reference(self):
        """It has TWO emission sites and they print different things after it:
        `consolidate` follows with the `NEXT-ACTION:` line, while
        `_already_consolidated_note` follows with nothing — the coordinator
        path's normal case, where the reviewing fork has already returned.

        So a clause pointing at "the line below" is true on one path and a
        dangling pointer on the other. That shipped briefly while replacing a
        hardcoded "5-10 minute rounds", trading a wrong number for a broken
        reference on the path that most needed the number. Whatever this text
        needs the reader to have must be inside it.
        """
        d = cc._BATCH_FIX_DIRECTIVE
        for pointer in ("line below", "below prices", "above", "following line"):
            assert pointer not in d, (
                f"{pointer!r} points outside the directive, which is emitted from "
                "two sites printing different things after it — see "
                "`_already_consolidated_note`, which prints nothing below"
            )

    def test_directive_dispositions_rather_than_mandating_fixes(self):
        # Only unresolved BLOCKING gates anything. "Fix them ALL" contradicted
        # building.md's "warnings and notes gate nothing — disposition each
        # rather than reflexively fixing", on the surface with the most
        # authority at the moment the builder decides.
        d = cc._BATCH_FIX_DIRECTIVE
        assert "Disposition them ALL in ONE pass" in d
        assert "accept or file the rest" in d
        assert "Fix them ALL" not in d
        assert "ONE commit" in d
        assert "ONE `/prawduct:critic verify-resolutions`" in d
        # The verify pass is a coverage consequence, not an obligation.
        assert "if that commit touches judgeable files" in d

    #: Where the directive stops claiming things are free. NOT "Everything else"
    #: — that marks the costly *sentence*, but the free sentence already turns
    #: negative before it: "`.md` files OUTSIDE `skills/`, `methodology/`,
    #: `templates/` and a root `CLAUDE.md`". Those four are named inside the free
    #: clause as EXCLUSIONS, so a naive split reads them as free claims. Every
    #: token from `OUTSIDE` onward is a costly claim.
    _FREE_CLAUSE_ENDS_AT = "OUTSIDE"
    _COSTLY_SENTENCE_MARKER = "Everything else"

    def _clause_says_free(self, token: str) -> bool:
        """True if the directive names ``token`` while still claiming free."""
        directive = cc._BATCH_FIX_DIRECTIVE
        return directive.index(token) < directive.index(self._FREE_CLAUSE_ENDS_AT)

    def test_directive_free_and_costly_claims_match_the_predicate(self):
        """Each path class is classified as the directive's own PROSE claims.

        Derived from clause placement, not from a flag in the table beside it.
        With a hardcoded flag, *moving* a token between clauses — dropping
        `templates/` into the free list — left the suite green while shipping a
        message that tells a builder to edit a governance-protected file
        mid-review and lose their coverage: the higher-cost direction.
        """
        from lib import coverage_algebra

        directive = cc._BATCH_FIX_DIRECTIVE
        for marker in (self._FREE_CLAUSE_ENDS_AT, self._COSTLY_SENTENCE_MARKER):
            assert marker in directive, (
                "the directive no longer carries the clause boundary the tests "
                f"split on ({marker!r}) — every placement check below would read "
                "the wrong region. Restore it or update the marker."
            )
        for token, (path, expected_judgeable) in _DIRECTIVE_PATH_CLASSES.items():
            assert token in directive, (
                f"_DIRECTIVE_PATH_CLASSES pins {token!r}, but the directive no "
                "longer names it — drop the entry or restore the text"
            )
            claimed_free = self._clause_says_free(token)
            assert claimed_free is not expected_judgeable, (
                f"the directive now places {token} in the "
                f"{'free' if claimed_free else 'costly'} clause, but the table "
                f"expects {'costly' if expected_judgeable else 'free'} — a token "
                "moved between clauses. Confirm against is_judgeable_path before "
                "updating either."
            )
            assert coverage_algebra.is_judgeable_path(path) is expected_judgeable, (
                f"the directive classifies {token} as "
                f"{'costly' if expected_judgeable else 'free'} to write "
                f"mid-review, but is_judgeable_path({path!r}) now disagrees. "
                "Amend both together: a wrong 'free' claim costs a reader their "
                "coverage, and a wrong 'costly' claim sends them to a round they "
                "did not owe."
            )

    def test_directive_names_no_unpinned_path_class(self):
        """A path token in the directive that no entry above pins fails here.

        This is the half that catches an edit to the prose ALONE — the drift
        direction the first version of these tests missed entirely.
        """
        # Backticked tokens that look like paths (contain `/` or end in `.md`
        # /`.json`), minus the ones that are commands or files-to-read.
        tokens = set(re.findall(r"`([^`]+)`", cc._BATCH_FIX_DIRECTIVE))
        pathish = {
            t for t in tokens
            if ("/" in t or t.endswith((".md", ".json", ".yaml")))
            and not t.startswith("/prawduct:")
        }
        pinned = set(_DIRECTIVE_PATH_CLASSES)
        # `.prawduct/` is pinned unbackticked in the map key; normalize.
        pinned_bare = {p.strip("`") for p in pinned}
        unpinned = {t for t in pathish if t not in pinned_bare}
        assert not unpinned, (
            f"_BATCH_FIX_DIRECTIVE names path class(es) {sorted(unpinned)} that "
            "no _DIRECTIVE_PATH_CLASSES entry pins against is_judgeable_path. "
            "Add each with a representative path and its expected judgeability."
        )

    def test_directive_names_the_comment_only_trap(self):
        # The single most expensive misread of "free": a `.py` comment edit
        # looks like prose and is judgeable. coverage_algebra's docstring
        # records the ruling; the runtime message has to carry it too.
        assert "comment-only edit to" in cc._BATCH_FIX_DIRECTIVE

    def test_unbackticked_free_surfaces_still_match_the_predicate(self):
        # The directive also names free surfaces in prose rather than backticks
        # ("everything under `.prawduct/` — change-log, backlog, project-state
        # and build plans"). Pin the concrete files those words denote; the token
        # scan above cannot see them. `release-notes.md` stays in this list after
        # the directive stopped naming it: the file is still there, now a frozen
        # archive, and "everything under `.prawduct/`" still covers it.
        from lib import coverage_algebra

        for path in (
            ".prawduct/backlog.md",
            ".prawduct/project-state.yaml",
            ".prawduct/artifacts/build-plan-demo.md",
            ".prawduct/release-notes.md",   # frozen archive of the retired views
        ):
            assert not coverage_algebra.is_judgeable_path(path)


# ---------------------------------------------------------------------------
# Unit: the resolution-is-a-claim directive
# ---------------------------------------------------------------------------


#: Shell binaries a reviewer-facing directive could plausibly name. Any
#: backticked token in the directive whose first word is one of these is a
#: COMMAND claim and gets checked against the Critic skill's own `allowed-tools`
#: grant. Deliberately over-broad: an entry the directive never names costs
#: nothing, while a missing entry silently exempts the command it would catch.
_COMMAND_HEADS = (
    "git", "grep", "rg", "pytest", "python", "python3", "prawduct-hook",
    "wc", "find", "ls", "cat", "sed", "awk", "make", "npm", "node", "bash",
)

#: Sentence openers that mark a DESCRIPTIVE closing rather than an instruction.
#: Closed around the failure mode (a directive that trails off explaining
#: itself) rather than enumerating acceptable verbs — a whitelist of verbs goes
#: red on any correct rewording, which is how the previous version of this check
#: ended up documenting four spellings while testing one.
_DESCRIPTIVE_OPENERS = frozenset(
    """a an and but everything anything nothing five four three two one the this
    that these those there here it its they their his her your our so because
    which what when where while since although however""".split()
)

_CRITIC_SKILL = ROOT / "skills" / "critic" / "SKILL.md"


def _critic_bash_grants() -> list[str]:
    """Literal command prefixes the Critic skill's `allowed-tools` grants.

    `!Bash(...)` deny entries are excluded — skill-frontmatter deny is not
    reliably enforced (see `tests/test_critic_skill_metadata.py`), so treating
    one as a grant would be the wrong direction, and treating it as a *denial*
    would let the allow-list look narrower than it is. Neither: only the
    pure-allow entries define what the reviewer can actually run.
    """
    content = _CRITIC_SKILL.read_text(encoding="utf-8")
    m = re.search(r"^allowed-tools:\s*(.+)$", content, re.MULTILINE)
    assert m is not None, f"{_CRITIC_SKILL} has no `allowed-tools:` frontmatter"
    grants = re.findall(r"(?<!!)Bash\(([^)]+)\)", m.group(1))
    assert grants, "parsed no Bash grants — the frontmatter shape changed"
    return [g.split("*")[0].strip() for g in grants]


def _reviewer_can_run(command: str) -> bool:
    """True when `command` falls under some Critic Bash grant.

    Prefix match in both directions: the grant `git show ` covers the bare
    token `git show`, and it also covers `git show HEAD`.
    """
    return any(
        command.startswith(prefix) or prefix.startswith(command)
        for prefix in _critic_bash_grants()
    )


class TestResolutionIsAClaimDirective:
    """The directive delivered at `verify-resolutions` DISPATCH.

    Three properties, none of them "the right words are present":

    1. Its claims about the gate are TRUE — asserted against
       `coverage_algebra`, not against the sentence that makes them. A runtime
       message stating a false property of the gate is worse than silence.
    2. Every command it names is one the reviewer can actually run. Its reader
       is tool-restricted; advice it cannot follow is discovered mid-review,
       holding a claim it now has no way to check.
    3. It descends. An upleveled rule is durable because it is general and
       inert for the same reason — the reader agrees with it and writes the
       same unchecked disposition. The act, the instances, and the spend-it-here
       instruction are what convert agreement into a changed decision, so they
       are pinned as deliverables rather than as style.
    """

    def test_the_gate_claims_it_makes_are_true(self):
        """`fixed` and `waived` BOTH resolve; omission is the only fail-closed
        answer. Driven from the algebra so a third disposition, or a change to
        which ones resolve, fails here instead of shipping a message that sends
        reviewers to an escape hatch that does not exist."""
        from lib import coverage_algebra

        fact = {
            "id": "rev-x",
            "body": {"findings": [
                {"fid": "R-1", "severity": "blocking", "title": "t"}
            ]},
        }
        # The directive's core promise: no resolution fact → still blocking.
        assert [
            f["fid"] for f in coverage_algebra.unresolved_blocking(fact, set())
        ] == ["R-1"], (
            "the directive tells reviewers that leaving a finding out of "
            "`resolutions` keeps it blocking. It no longer does."
        )
        # And why omission is the ONLY fail-closed answer: every recognized
        # disposition clears it, so "waive it when unsure" would weaken the
        # very gate this text warns about.
        for disposition in sorted(coverage_algebra._RESOLVING_DISPOSITIONS):
            resolved = coverage_algebra.resolution_index([{
                "kind": "resolution",
                "body": {
                    "finding": {"review_id": "rev-x", "fid": "R-1"},
                    "disposition": disposition,
                },
            }])
            assert coverage_algebra.unresolved_blocking(fact, resolved) == [], (
                f"{disposition!r} no longer resolves — the directive names it "
                "as one of the two that lift a blocker"
            )
            assert f"`{disposition}`" in cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE, (
                f"{disposition!r} resolves a blocking finding but the directive "
                "does not name it. A reviewer told only about `fixed` reads the "
                "unnamed one as the safe answer for a finding it could not check."
            )

    def test_names_no_command_the_reviewer_cannot_run(self):
        """The Critic's `allowed-tools` is pure-allow and grants no test runner
        (CRT-3X9D). "Run the suite" is therefore not advice — it is an
        instruction the reader must discover it cannot follow, mid-review.
        """
        tokens = set(re.findall(r"`([^`]+)`", cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE))
        commands = {t for t in tokens if t.split()[0] in _COMMAND_HEADS}
        for command in sorted(commands):
            assert _reviewer_can_run(command), (
                f"the directive tells the reviewer to run {command!r}, which no "
                "Bash grant in skills/critic/SKILL.md covers. Name evidence the "
                "reader can actually produce, or widen the grant deliberately."
            )

    def test_the_command_check_would_catch_an_ungranted_command(self):
        """Negative control for the check above.

        Without this, `test_names_no_command_the_reviewer_cannot_run` passes
        just as happily when the token scan matches nothing at all — which is
        what a typo in `_COMMAND_HEADS`, or a directive rewritten to drop its
        backticks, would produce. Pin that the matcher discriminates.
        """
        assert not _reviewer_can_run("pytest -q")
        assert not _reviewer_can_run("grep -rn foo")  # the TOOL is granted; bash grep is not
        assert _reviewer_can_run("git show")
        assert _reviewer_can_run("git diff --stat")

    def test_the_directive_descends_rather_than_only_stating_a_rule(self):
        """Structure, not wording.

        An upleveled rule is agreed with and not applied unless it also carries
        the descent: the act to perform, and instances concrete enough to
        pattern-match against. That is a property of the text's SHAPE, and it
        is what this asserts.

        An earlier cut asserted four exact phrases — "surest about", "actually
        in front of you", "name the evidence you read". Those had no mechanism
        behind them; they froze wording chosen an hour earlier and would fail
        for every improvement to the sentence while passing for any defect that
        kept the words. `learnings.md` already carries the rule ("assert the
        PROPERTY, not one spelling of it"), and it did not fire — in the
        changeset whose thesis is that stored rules do not fire. Deleted rather
        than elaborated.
        """
        d = cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE
        # An imperative: the reader is told to produce something, not to feel
        # something. Any of these verbs satisfies it; the point is that one is
        # present, not which.
        assert any(verb in d for verb in ("name ", "say ", "state ", "run ")), (
            "the directive states a rule but never tells the reader what to DO "
            "with a specific finding — agreement is not application"
        )
        # NOT asserting "it carries concrete instances." The draft of this test
        # tried `d.count(", and ") >= 2`, which is a conjunction count, not an
        # instance count — it passes for any prose with two `and`s and fails for
        # a rewrite that uses semicolons. Substituting a fragile proxy for a
        # property you cannot express is the same defect as pinning a spelling,
        # so the claim is left to review rather than faked in CI.
        #
        # It must point at the case in hand rather than the rule in
        # general. Detected as a second-person present-tense reference to the
        # reader's own situation, which is what distinguishes descent from
        # exhortation.
        assert "you" in d and ("this " in d or " in front of " in d), (
            "the directive no longer aims at the decision the reader is making "
            "right now, which is the whole difference between a rule that "
            "fires and one that is agreed with"
        )

    def test_a_class_finding_is_not_resolved_by_the_sites_it_named(self):
        """The clause that makes this directive the grading half of
        instance-vs-class, and the three parts that make it act.

        It replaced an instance-shaped version of itself — "a finding whose
        second site is in a file this delta does not touch" — which named a
        list of two where the property was meant, in a directive whose subject
        is dispositions made from memory. A reviewer holding a finding with
        five surviving members reads "second site", finds no second site, and
        writes `fixed`.

        Why the rule lands HERE rather than in a protocol file: this reviewer
        reads `goals-1-3.md` and these two directives, and nothing else.
        `review-cycle.md` — where fix-by-fudging's siblings are defined — is a
        file this mode's reviewer is forbidden to open, which that file itself
        records about its own workaround clause.
        """
        d = cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE
        assert "CLASS" in d, (
            "the directive no longer names the class case, so the only "
            "resolution defect it warns about is a misread diff"
        )
        # The act: re-run the reason as a search. Without it the reviewer is
        # told a class exists and given no way to find its members.
        assert "search" in d, (
            "the directive names the class case but not the act that settles "
            "it — a reviewer cannot check membership by reading the delta"
        )
        # The withholding, which is the only part with teeth: an enumeration
        # offered as the whole fix is not a resolution.
        assert "not a resolution" in d, (
            "the directive no longer says an enumeration fails to resolve, so "
            "a list of names still reads as a fix and clears the blocker"
        )

    def test_the_directive_has_a_size_ceiling(self):
        """Pinned for the same reason its sibling is, and pinned now because
        this is the edit that spent it.

        Its sibling's ceiling docstring records that this directive is "the
        overflow route by default" — capped homes on either side, none here —
        and the instance-vs-class grading clause took that route on 2026-08-18
        (`goals-1-3.md` sat 2 tokens under its ceiling, `review-cycle.md` 1, and
        neither is read by this mode's reviewer anyway). Leaving the route
        unguarded after using it is how the next editor uses it silently.

        235 -> 280 on 2026-08-18: the class clause, replacing a two-item list
        with the property plus the act and the withholding. Measured with the
        estimator every budgeted file in this repo uses. Two numbers, two jobs:
        the pin fails on any drift and carries the new figure; the ceiling says
        how much drift is allowed before a clause has to move out.
        """
        tokens = int(len(cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE.split()) * 1.3)

        assert tokens == 280, (
            f"RESOLUTION_IS_A_CLAIM_DIRECTIVE is ~{tokens} tokens; this pin "
            f"says 280. Update it to {tokens} and say in the docstring what paid "
            f"for the change — the ceiling below is not a budget to spend."
        )
        assert tokens < 400, (
            f"the directive is ~{tokens} tokens. It is delivered on every "
            f"verify dispatch, immediately before the reviewer writes the one "
            f"output that weakens a gate, and it competes with the review for "
            f"attention. Trim, or move a clause to the file that owns it."
        )

    def test_delivery_is_upstream_of_the_claim(self):
        """WHERE this prints is the chunk's substance, so it is pinned here.

        `verify-resolutions` is always single-pass, so the reviewing fork
        writes its `resolutions` into the partial and only THEN runs
        consolidate. Emitting there — beside `_BATCH_FIX_DIRECTIVE`, the
        obvious slot — would reach an agent that has already made the claim and
        is one step from exiting, and would never reach the builder at all
        (the Critic skill is `context: fork`, and `goals-1-3.md`'s report-back
        enumerates findings and a summary, not consolidate's stdout).

        Asserted against the modules rather than the docstring: `critic-begin`
        must reference it, `consolidate` must not.
        """
        begin_src = HOOK.read_text(encoding="utf-8")
        assert "RESOLUTION_IS_A_CLAIM_DIRECTIVE" in begin_src, (
            "the dispatch command no longer emits the directive — it is "
            "delivered at critic-begin precisely because that is the last "
            "moment before the reviewer writes its resolutions"
        )
        consolidate_src = (
            ROOT / "lib" / "critic_consolidate.py"
        ).read_text(encoding="utf-8")
        body = consolidate_src.split("def consolidate(", 1)
        assert len(body) == 2, "consolidate() not found — update this guard"
        assert "RESOLUTION_IS_A_CLAIM_DIRECTIVE" not in body[1], (
            "the directive is now also emitted from consolidate(), which runs "
            "AFTER the reviewer has written its resolutions. A directive there "
            "cannot change the claim it is about. Delete it, or move the "
            "delivery deliberately and rewrite this test's rationale."
        )


class TestVerifyRatesBlockingOnlyDirective:
    """The severity narrowing delivered at `verify-resolutions` dispatch.

    Same three properties its sibling is held to — its claims about the gate
    are true, it names nothing the reader cannot do, and it descends — plus the
    one specific to a rule that REMOVES review output: the classes it exempts
    from the narrowing must actually still be blocking-rated in the protocol
    the reviewer reads. A narrowing whose carve-out has drifted out of
    `goals-1-3.md` silently demotes the thing it promised to keep.
    """

    def test_it_is_true_that_only_blocking_gates(self):
        """The narrowing's whole justification is that nothing which gated
        stops gating. Driven from the algebra: a warning and a note left in a
        fact must not appear in `unresolved_blocking`. If that ever changes,
        this directive is telling reviewers to drop findings a gate reads.
        """
        from lib import coverage_algebra

        fact = {
            "id": "rev-x",
            "body": {"findings": [
                {"fid": "R-1", "severity": "warning", "title": "w"},
                {"fid": "R-2", "severity": "note", "title": "n"},
                {"fid": "R-3", "severity": "blocking", "title": "b"},
            ]},
        }
        unresolved = [f["fid"] for f in coverage_algebra.unresolved_blocking(fact, set())]
        assert unresolved == ["R-3"], (
            "the directive tells reviewers that demoting a WARNING/NOTE to an "
            f"observation costs no gate. unresolved_blocking now returns "
            f"{unresolved} — a demoted finding would be a dropped gate input."
        )

    def test_the_carve_out_classes_the_protocol_rates_are_still_blocking(self):
        """Half the carve-out is a CITATION — these classes are BLOCKING in
        `goals-1-3.md` already, and the directive relies on that. If one is
        downgraded there, the directive's promise silently becomes false.

        Judged per CLAUSE, not per line. The first version asked only that some
        line containing `**BLOCKING**` also contained the anchor — and
        goals-1-3.md's security bullet carries five verdicts on one line (three
        BLOCKING, two WARNING), so downgrading `injection` to WARNING left the
        line matching and this test green. A drift detector with slack in it is
        indistinguishable from the drift it watches for.
        """
        goals = (ROOT / "skills" / "critic" / "goals-1-3.md").read_text(encoding="utf-8")
        # Split into severity-bearing clauses so a multi-verdict line cannot
        # lend its BLOCKING to a neighbour that was downgraded.
        clauses = [c for ln in goals.split("\n") for c in ln.split(";")]
        for promise, anchor in (
            ("weakened or deleted test", "assertions weakened"),
            ("dropped requirement", "explicitly descoped"),
            ("changed behavior with no test", "Changed/added behavior"),
            ("injection vectors", "injection"),
        ):
            carrying = [c for c in clauses if anchor in c]
            assert carrying, f"goals-1-3.md no longer mentions {anchor!r} at all"
            assert any("**BLOCKING**" in c for c in carrying), (
                f"goals-1-3.md no longer rates {anchor!r} BLOCKING in its own "
                f"clause, but VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE relies on "
                f"{promise!r} already being blocking there. One of the two is "
                "now lying to a reviewer told to demote everything else."
            )

    def test_the_escalated_carve_out_classes_are_named_as_escalations(self):
        """The other half of the carve-out is an ESCALATION, and the reason this
        test exists is that the directive once claimed it was not.

        `goals-1-3.md` rates *auth/authz on new endpoints* and *known critical
        vulnerabilities* **WARNING**, and does not rate fix-by-fudging at all —
        its workaround leg was rated only in `review-cycle.md`, which a
        `verify-resolutions` reviewer is forbidden to open. The directive
        claiming these were "already BLOCKING-rated" handed the same reviewer
        two contradictory answers. So: the protocol's rating is pinned as
        WARNING (if it ever becomes BLOCKING, the escalation wording is stale
        and should be re-read), and the directive must carry the classes
        explicitly, since it is now their only rating in this mode.
        """
        goals = (ROOT / "skills" / "critic" / "goals-1-3.md").read_text(encoding="utf-8")
        d = cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE
        # Judged per CLAUSE, exactly like the sibling above — and for the same
        # reason, which this test reintroduced one method over while fixing it
        # there. `auth/authz` shares its line with four other verdicts, so a
        # line-level `"**WARNING**" in authz` is satisfied by the vulnerable-
        # dependency clause beside it: promote auth/authz to BLOCKING and this
        # stays green while the escalation wording it guards goes stale.
        authz = next(
            (c for ln in goals.split("\n") for c in ln.split(";") if "auth/authz" in c),
            None,
        )
        assert authz is not None and "**WARNING**" in authz, (
            "goals-1-3.md's auth/authz rating moved. The directive escalates it "
            "to BLOCKING for verify-resolutions and says so explicitly — re-read "
            "that wording against the new rating rather than updating this pin."
        )
        assert "fudging" not in goals, (
            "goals-1-3.md now rates fix-by-fudging. The directive carries that "
            "rating solely because the protocol did not — fold it in and drop "
            "the escalation clause."
        )
        for named in ("auth/authz", "fudging", "workaround"):
            assert named in d, (
                f"the directive no longer names {named!r}. It is the ONLY "
                "carrier rating that class for this mode; dropping it demotes "
                "the class to an observation by silence."
            )
        assert "whatever they are rated elsewhere" in d or "escalat" in d.lower(), (
            "the directive no longer marks the carve-out as an escalation, "
            "which is the claim that made it honest"
        )

    def test_names_no_command_the_reviewer_cannot_run(self):
        """Same grant check its sibling gets — the reader is tool-restricted,
        and advice it cannot follow is discovered mid-review.

        **Vacuous today, and deliberately kept.** This directive names no
        commands, so the loop body does not execute — which is worth stating
        rather than leaving for a reader to discover, because a silently vacuous
        test reads as coverage. It is a forward guard: the moment an edit adds a
        backticked command, the grant check starts biting. The assertion below
        is what keeps the test from being vacuous in BOTH directions — the
        backtick scan must still find the identifiers the rule depends on, so a
        rewrite that dropped its formatting could not slip past as "no commands
        named".
        """
        tokens = set(re.findall(r"`([^`]+)`", cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE))
        assert "findings" in tokens and "resolutions" in tokens, (
            "the backtick scan no longer finds the arrays this rule routes "
            "between — either the directive lost its formatting (making the "
            "command check below vacuous for the wrong reason) or it stopped "
            "naming where a demoted finding does and does not go"
        )
        commands = {t for t in tokens if t.split()[0] in _COMMAND_HEADS}
        for command in sorted(commands):
            assert _reviewer_can_run(command), (
                f"the directive tells the reviewer to run {command!r}, which no "
                "Bash grant in skills/critic/SKILL.md covers."
            )

    def test_blocking_is_defined_as_a_claim_about_the_tree(self):
        """BLOCKING must be stated as a SCHEDULING claim, not only a risk rating.

        Measured on `feat/gate-as-dispatcher` (2026-08-06): the same finding
        class was a WARNING in the cumulative (a stale registry row — dispositioned,
        no round) and BLOCKING in a verify pass (a registry row — a full round),
        decided by which mode noticed it rather than by its cost. The verify
        reviewer wrote both halves of the contradiction in one report — "it rides
        the commit already owed ... it does not need one of its own", then rated
        it BLOCKING, which by the gates' own semantics guarantees it gets one.
        It knew the schedule and had no severity to say it in.

        Pinned as STRUCTURE, like every sibling here: the directive must (a)
        define BLOCKING against whether the TREE may move rather than whether
        the fix is owed, and (b) distinguish the two on record-class gaps. The
        wording is free. This clause lives ONLY in this constant — not in
        `goals-1-3.md`, not in `review-cycle.md`, both of which sit against
        their token ceilings — so without a pin a prose-diet pass deletes the
        whole distinction with the suite green.
        """
        d = cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE

        assert "tree" in d.lower(), (
            "the directive no longer defines BLOCKING against the TREE. Without "
            "that anchor 'blocking' collapses back to 'important', which is what "
            "made a one-row doc gap cost a full review round"
        )
        # The distinction itself: something is owed AND the tree is still fine.
        assert "owed" in d.lower(), (
            "the directive no longer separates 'the tree must not move' from "
            "'this fix is owed' — the two coming apart is the entire point"
        )
        # The class the distinction exists for, and its escape. `"record"` alone
        # would be worthless here: the constant already says "record-lint",
        # "recorded here" and "the record demands" elsewhere, so a bare
        # substring passes on pre-existing text and guards nothing while its
        # failure message claims otherwise. Pin the compound.
        assert "record gap" in d.lower(), (
            "the directive no longer names RECORD GAPS as the class the "
            "distinction exists for, so a reviewer holding a registry row is "
            "back to choosing between forcing a round and saying nothing"
        )
        assert "ride" in d.lower(), (
            "the directive no longer offers the ride-along route for a demoted "
            "record gap"
        )
        # A demotion with no destination is a drop. The route only works if the
        # reviewer is told WHERE the builder must write it — deleting just this
        # parenthetical would leave the clause reading fine and silently turn
        # every demoted record gap into lost work.
        assert ".handoff-notes.md" in d, (
            "the ride-along route no longer names where the builder must write "
            "the demoted gap. Without a destination the demotion is a drop, "
            "which is the one way this rule could lose something real"
        )
        # The exemption must survive too, or the distinction silently weakens
        # the five classes that mean the tree is ALREADY wrong.
        assert "exempt" in d.lower() or "already wrong" in d.lower(), (
            "the record-gap carve-out no longer states that the five BLOCKING "
            "classes are exempt — as written it could be read as licensing a "
            "demotion of a weakened test or an untested behavior change"
        )
        # And the close case, or the escape becomes a permanent deferral: a
        # chunk with no further commit has nothing for the gap to ride.
        assert "clos" in d.lower(), (
            "the directive no longer says a record gap blocks a chunk CLOSE. "
            "Without it the ride-along route has no terminator and a registry "
            "row can be deferred forever by a chunk that never commits again"
        )

    def test_the_directive_has_a_size_ceiling(self):
        """Its two alternative homes are capped and it is not, which makes it
        the overflow route by default — the clause added on 2026-08-06 went here
        precisely because `goals-1-3.md` and `review-cycle.md` sat 2 and 4 tokens
        under their ceilings.

        A dispatch directive is read by a model on every verify pass, so it
        competes with the review itself for attention; unbounded growth here is
        the same defect as unbounded growth there, minus the test that catches
        it.

        Measured in TOKENS with the same estimator every budgeted file in this
        repo uses, and with the current reading pinned — a ceiling alone lets
        growth accrete silently inside the headroom, which is the failure the
        `LAST_MEASURED_TOKENS` convention exists to prevent. Two numbers, two
        jobs: the pin fails on any drift and carries the new figure; the ceiling
        says how much drift is allowed before a clause has to move out.
        """
        tokens = int(len(cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE.split()) * 1.3)

        assert tokens == 707, (
            f"VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE is ~{tokens} tokens; this pin "
            f"says 707. Update it to {tokens} and say in the docstring what paid "
            f"for the change — the ceiling below is not a budget to spend."
        )
        assert tokens < 900, (
            f"the directive is ~{tokens} tokens. It is delivered on every verify "
            f"dispatch and competes with the review for attention. Trim, or move "
            f"a clause to the protocol file that owns it."
        )

    def test_it_descends_rather_than_only_stating_a_rule(self):
        """Structure, not wording — the same property its sibling is held to,
        and for the same measured reason: a reviewer agrees that re-reviews
        should not manufacture work and then records the WARNING in front of
        it, because nothing made it recognize THIS finding as the instance.

        The first cut of this check was itself the defect it screens for. Its
        verb tuple was `("goes ", "report", "rate ", "spend ", "Spend ")`:
        `"report"` matched the NOUN in "in your report", `"rate "` never matched
        the capitalized "Rate these", and `"spend "`/`"Spend "` were leftovers
        from a draft wording — so a test claiming to detect an imperative was
        satisfied by descriptive text. Imperatives are capitalized sentence
        openers here, which is what makes them matchable without pinning a
        spelling.

        The second cut replaced that tuple with `("Rate ", "Apply ", "Report ",
        "Say ")` and only `"Apply "` ever matched — a whitelist that documents
        four spellings while checking one, and that goes spuriously red the
        first time someone rewords to a correct imperative outside it. So the
        check is derived from the directive's LAST sentence instead: the closing
        move is where the rule is handed to the reader, and the failure mode is
        an opener that describes ("The demotion is not politeness…") rather than
        instructs. The exclusion list is closed around that failure mode; the
        set of acceptable verbs stays open.
        """
        d = cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE
        last = [s for s in re.split(r"(?<=[.!?])\s+", d.strip()) if s][-1]
        opener = last.split()[0].strip("*_`,:").lower()
        assert opener not in _DESCRIPTIVE_OPENERS and last[0].isupper(), (
            f"the directive's closing sentence opens with {opener!r} — it "
            "describes the rule instead of telling the reader what to DO with "
            "the finding in front of it, and agreement is not application"
        )
        assert "you" in last, (
            "the closing sentence no longer addresses the reader, so nothing "
            "connects the rule to the finding being rated right now"
        )
        assert "you" in d and ("this " in d or "the one you" in d), (
            "the directive no longer aims at the decision the reader is making "
            "right now"
        )
        # The demotion has a destination, and it is STRUCTURAL. "In prose" was
        # not enough: goals-1-3.md's report contract enumerates findings and a
        # summary with no slot for anything else, so a pass that demoted three
        # observations was instructed to report "No issues found" — the exact
        # silence the cost analysis assumes will not happen.
        assert "### Observations" in d, (
            "the directive no longer names a structural destination for demoted "
            "findings. The report contract has no slot for them otherwise, so "
            "they vanish — and the whole cost-bound rests on the builder "
            "reading them."
        )
        # Half-emitted yield: the count must at least reach the builder, or a
        # rule that fired is indistinguishable from a reviewer that found
        # nothing.
        assert "how many" in d, (
            "the directive no longer asks for a demotion count. Verify-mode "
            "WARNING/NOTE totals are zero by construction, so this line is the "
            "only signal that the narrowing fired at all."
        )

    def test_delivery_is_upstream_of_the_rating(self):
        """WHERE this prints is its substance: the reviewer must meet it before
        it assigns a severity, not after. `verify-resolutions` is single-pass,
        so the fork runs consolidate itself AFTER writing its findings —
        emitting there would reach an agent that has already rated everything.
        """
        begin_src = HOOK.read_text(encoding="utf-8")
        assert "VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE" in begin_src, (
            "the dispatch command no longer emits the narrowing — dispatch is "
            "the only moment before the reviewer rates the delta"
        )
        consolidate_src = (
            ROOT / "lib" / "critic_consolidate.py"
        ).read_text(encoding="utf-8")
        body = consolidate_src.split("def consolidate(", 1)
        assert len(body) == 2, "consolidate() not found — update this guard"
        assert "VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE" not in body[1], (
            "the narrowing is now also emitted from consolidate(), which runs "
            "AFTER the reviewer has written its findings."
        )

    def test_the_protocol_carries_it_before_any_severity_is_assigned(self):
        """The reader-modeling guardrail, and the reason the rule is NOT in
        `goals-1-3.md`'s `## Severity` section.

        Severity sits below all three goal sections, so a reviewer walking Goal
        1 → Goal 2 → Goal 3 has already assigned every WARNING by the time it
        arrives — presence would be real and effect zero. This repo has shipped
        that exact defect once already: `SKILL.md`'s header said to read
        `review-protocol.md` "first" 26 lines above the routing that said
        otherwise, and six guardrails measuring the artifact all stayed green.
        Ordering beats presence, so ordering is what this asserts.
        """
        goals = (ROOT / "skills" / "critic" / "goals-1-3.md").read_text(encoding="utf-8")
        assert "verify-resolutions" in goals
        rule_at = goals.find("only **BLOCKING** is a finding")
        assert rule_at != -1, (
            "goals-1-3.md no longer states the narrowing. The dispatch "
            "directive is a transient channel; this file is the reviewer's "
            "durable protocol and must carry the rule too."
        )
        first_goal_at = goals.index("## 1. Nothing Is Broken")
        assert rule_at < first_goal_at, (
            "the narrowing moved below the first goal section. A reviewer "
            "assigns severities as it reads the goals, so a rule stated after "
            "them is read after the decisions it governs — present, and inert."
        )


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

    def test_stale_schema_dispatch_is_not_wedged(self, tmp_path):
        """#676's premise, tested rather than believed.

        The source report said a pre-3.3.4 manifest "wedged all dispatch". It
        does not, and the fix shipped here is a message fix precisely BECAUSE
        this holds: `begin_review`'s in-flight guard fires on `active` or
        `"complete"`, and a stale-schema manifest is neither. If this ever goes
        red, the defect is a real wedge and the message work is the wrong
        repair."""
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _partials_dir(repo)
        (repo / PARTIALS_REL / "manifest.json").write_text(json.dumps(_V2_MANIFEST))
        state, _missing = cc.pending_state(repo / ".prawduct")
        assert state == "unreadable"
        assert state != "complete", "would trip begin_review's in-flight guard"

    def test_stale_schema_manifest_is_also_unreadable(self, tmp_path):
        """The COLLAPSE is deliberate and must not regress (#676).

        Corrupt and stale-schema are one answer to "can this be consolidated",
        and four callers branch on that answer. Splitting this vocabulary to fix
        a message would have made them all handle a case that changes none of
        their decisions — the distinction belongs to `manifest_condition`, which
        the message surfaces read, and this pins that `pending_state` stays out
        of it."""
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _partials_dir(repo)
        (repo / PARTIALS_REL / "manifest.json").write_text(json.dumps(_V2_MANIFEST))
        assert cc.pending_state(repo / ".prawduct") == ("unreadable", [])


# ---------------------------------------------------------------------------
# Unit: manifest_condition + what each condition is TOLD to an operator (#676)
#
# The defect these pin is not a crash and not a wrong decision — every decision
# was already right. It is that two surfaces described one disk differently and
# the more dangerous one described it falsely, telling an operator to discard
# reviewer output that the mechanism beside it deliberately archives. So these
# assert SENTENCES, and each names the false clause it exists to keep out.
# ---------------------------------------------------------------------------


def _plant(prawduct: Path, text: str) -> Path:
    (prawduct / ".critic-partials").mkdir(parents=True, exist_ok=True)
    (prawduct / ".critic-partials" / "manifest.json").write_text(text)
    return prawduct


class TestManifestCondition:
    def test_absent(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        condition, detail, manifest = cc.manifest_condition(tmp_path / ".prawduct")
        assert condition == cc.MANIFEST_ABSENT
        assert (detail, manifest) == ("", None)

    def test_corrupt_carries_the_parse_reason(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        condition, detail, manifest = cc.manifest_condition(_plant(tmp_path / ".prawduct", "{not json"))
        assert condition == cc.MANIFEST_CORRUPT
        assert detail, "the parse error is the whole diagnostic — dropping it re-hides the cause"
        assert manifest is None

    def test_stale_schema_carries_the_reason_and_the_record(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        condition, detail, manifest = cc.manifest_condition(
            _plant(tmp_path / ".prawduct", json.dumps(_V2_MANIFEST))
        )
        assert condition == cc.MANIFEST_STALE_SCHEMA
        assert detail
        # The parsed record comes back so a caller can say what the stale
        # manifest still knows — which is the fact that decides whether the
        # partials beside it are worth restoring.
        assert manifest["commit_reviewed"] == "abc"

    def test_valid(self, tmp_path):
        repo = tmp_path
        (repo / ".prawduct").mkdir()
        _write_manifest(repo, "abc")
        condition, detail, manifest = cc.manifest_condition(repo / ".prawduct")
        assert (condition, detail) == (cc.MANIFEST_VALID, "")
        assert manifest["id"] == FAKE_REVIEW_ID


class TestPendingRosterReadingNamesTheRealCondition:
    def _reading(self, tmp_path, text=None):
        (tmp_path / ".prawduct").mkdir(parents=True)
        if text is not None:
            _plant(tmp_path / ".prawduct", text)
        return cc.pending_roster_reading(tmp_path / ".prawduct")

    def test_stale_schema_does_not_claim_the_manifest_is_unreadable(self, tmp_path):
        """The three false clauses, pinned out one at a time.

        A v2 manifest IS readable and DID record what it was reviewing."""
        state, reading = self._reading(tmp_path, json.dumps(_V2_MANIFEST))
        assert state == "unreadable"  # the DECISION is unchanged
        assert "no readable dispatch manifest" not in reading
        assert "never recorded what it was reviewing" not in reading
        assert "Nothing here is worth keeping" not in reading
        # ...and says the true thing instead, including what it still knows.
        assert "OLDER PRAWDUCT" in reading
        assert "abc" in reading, "what it recorded is what the reading exists to surface"
        # The keep/discard verdict is deliberately NOT here: it is computed from
        # the partials on disk, which this reading cannot see. See
        # TestNoSurfacePairsPreservationWithDiscard.
        assert "worth keeping" not in reading

    def test_corrupt_says_corrupt_not_stale(self, tmp_path):
        state, reading = self._reading(tmp_path, "{not json")
        assert state == "unreadable"
        assert "not valid JSON" in reading
        assert "OLDER PRAWDUCT" not in reading, "an interrupted write is not a version skew"

    def test_absent_says_absent(self, tmp_path):
        """The harsh verdict moved to `anything_worth_keeping`, which computes
        it from the disk rather than inferring it from the manifest — an absent
        manifest beside ORPHANED partials is a real state, and a reading that
        pre-judged it would contradict the verdict composed beneath it."""
        state, reading = self._reading(tmp_path)
        assert state == "none"
        assert "no dispatch manifest at all" in reading
        assert "worth keeping" not in reading

    def test_the_three_readings_are_mutually_distinguishable(self, tmp_path):
        """The point of the change is that an operator can tell which disk they
        have. Identical-looking readings would satisfy every assertion above
        while restoring the defect."""
        readings = {
            name: self._reading(tmp_path / name, text)[1]
            for name, text in (
                ("absent", None),
                ("corrupt", "{not json"),
                ("stale", json.dumps(_V2_MANIFEST)),
            )
        }
        assert len(set(readings.values())) == 3, readings

    def test_every_reading_is_indented_two_spaces(self, tmp_path):
        """The shared formatting contract the docstring states — every caller
        composes these into an already-indented block."""
        for idx, text in enumerate((None, "{not json", json.dumps(_V2_MANIFEST))):
            _, reading = self._reading(tmp_path / f"case{idx}", text)
            assert reading.endswith("\n")
            for line in reading.splitlines():
                assert line.startswith("  "), f"{line!r} in {reading!r}"


class TestActiveDispatchRefusalDescribesTheDisk:
    def test_refusal_carries_the_stale_schema_reading(self, tmp_path):
        """`critic-begin`'s refusal is the surface #676 was filed against —
        the reading has to reach it, not just exist."""
        (tmp_path / ".prawduct").mkdir()
        _plant(tmp_path / ".prawduct", json.dumps(_V2_MANIFEST))
        message = cc.active_dispatch_refusal(tmp_path / ".prawduct", 120.0, True)
        assert "OLDER PRAWDUCT" in message
        assert "no readable dispatch manifest" not in message
        # The recovery was already named and stays named — #676's third
        # acceptance criterion is about the DIAGNOSIS, not the remedy.
        assert "prawduct-hook critic-end" in message


class TestAnythingWorthKeeping:
    """The keep-or-discard VERDICT has one home (#676 follow-up, R-6).

    Routing the *reading* through one place did not route this: two of five
    surfaces kept a locally-authored tail, so a stale-schema manifest printed
    "any partials beside it are real reviewer output" and then, four lines
    later, "Nothing here is worth keeping" — one message, both verdicts,
    discard last.
    """

    def _verdict(self, tmp_path, text=None, partials=0):
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        if text is not None:
            _plant(pd, text)
        for i in range(partials):
            (pd / ".critic-partials" / f"role{i}.rev-x.json").write_text("{}")
        return cc.anything_worth_keeping(pd)

    def test_a_lone_stale_manifest_has_nothing_to_keep(self, tmp_path):
        """R-11: the disk that broke the first cut. A stale-schema manifest
        sitting alone promises a `critic-restore` handle with nothing behind
        it — the operator goes looking for an empty archive."""
        keep, clause = self._verdict(tmp_path, json.dumps(_V2_MANIFEST), partials=0)
        assert keep is False
        assert "nothing here is worth keeping" in clause.lower()
        assert "critic-restore" not in clause

    def test_a_stale_manifest_with_partials_is_worth_keeping(self, tmp_path):
        keep, clause = self._verdict(tmp_path, json.dumps(_V2_MANIFEST), partials=2)
        assert keep is True
        assert "2 reviewer partial(s)" in clause
        assert "critic-restore" in clause

    def test_absent_manifest_with_partials_is_still_worth_keeping(self, tmp_path):
        """The verdict keys on reviewer output, not on the manifest: orphaned
        partials are real output whether or not anything describes them."""
        keep, clause = self._verdict(tmp_path, None, partials=1)
        assert keep is True

    def test_a_valid_manifest_is_worth_keeping_before_any_reviewer_reports(self, tmp_path):
        """"Is there reviewer output" and "is there a review here" are different
        questions, and only the second licenses a discard.

        An earlier cut counted partials alone, so a live review with an
        incomplete roster answered "nothing is worth keeping" — and
        `_forced_live_sweep_notice` dropped its `critic-restore` instruction
        entirely, which `test_forcing_a_sweep_names_a_recovery_that_can_actually
        _be_run` caught. Reviewers may still be writing; the manifest records
        what is under review; `critic-restore` restores the directory including
        it."""
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        _write_manifest(tmp_path, "abc")
        keep, clause = cc.anything_worth_keeping(pd)
        assert keep is True
        assert "dispatched review is here" in clause
        assert "not reported yet" in clause

    def test_orphaned_partials_with_no_manifest_are_named_as_orphaned(self, tmp_path):
        keep, clause = self._verdict(tmp_path, None, partials=1)
        assert keep is True
        assert "orphaned" in clause

    def test_the_manifest_itself_is_not_counted_as_reviewer_output(self, tmp_path):
        keep, _clause = self._verdict(tmp_path, json.dumps(_V2_MANIFEST), partials=0)
        assert keep is False, "manifest.json is not a partial"


def _load_hook():
    """The hook script, in-process. Same idiom as
    `test_critic_session_guard.py` — the boundary notices are plain functions
    and composing them is the only way to assert what an operator actually
    reads; a subprocess would give the CLI's output, not these."""
    import importlib.machinery  # noqa: PLC0415 — the extensionless hook script
    import importlib.util  # noqa: PLC0415

    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_for_notice_composition",
        str(Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    hook = importlib.util.module_from_spec(spec)
    loader.exec_module(hook)
    return hook


class TestNoSurfacePairsPreservationWithDiscard:
    """The construction R-6 asked for, as a property rather than string
    assertions: compose the operator-facing messages under every manifest
    condition and assert none says both things at once.

    **Three of the four production verdict-bearing notices**, named rather than
    rounded up to "every surface"; `reading+verdict` below is this test's own
    direct call, not a fourth. All four now reach the verdict through
    `prawduct-hook`'s `_keep_verdict` rather than each guarding the call
    itself — deliberately no line numbers here, since they renumber and the
    function name does not. The remaining production site is `cmd_stop`'s,
    reachable only through the CLI, and it is pinned in
    `test_stop_abandoned_critic.py::test_the_stop_blocker_carries_the_shared_keep_verdict`.
    An earlier docstring here did say "every surface" while composing a set
    disjoint from the one the finding named, which is how a pin comes to read as
    coverage it does not have.

    **It must compose the surfaces R-6 was actually about.** The first cut of
    this class composed three LIB surfaces and none of the two hook boundary
    notices R-6 named — while its own docstring claimed "every surface". A pin
    that names a class and covers a disjoint set is worse than none: it reads
    as coverage. The hook notices are loaded in-process below so the assertion
    runs over the bytes an operator reads.
    """

    _DISCARD = (
        "nothing here is worth keeping",
        "nothing recoverable was attached",
        "no reviewer output is on disk",
    )
    _PRESERVE = (
        "critic-restore",
        "are real output",
        "archives them rather than",
        "reviewer partial(s) are on disk",
    )

    #: The surfaces that report a keep/discard verdict about the CURRENT disk.
    #: The two refusals are composed above for the contradiction check but are
    #: not verdict-bearing — they describe what a dispatch WOULD do.
    _VERDICT_BEARING = (
        "reading+verdict", "boundary_retained", "boundary_swept", "forced_live_sweep",
    )

    def _compose(self, tmp_path, text, partials):
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        if text is not None:
            _plant(pd, text)
        for i in range(partials):
            (pd / ".critic-partials" / f"role{i}.rev-x.json").write_text("{}")
        _state, reading = cc.pending_roster_reading(pd)
        _keep, verdict = cc.anything_worth_keeping(pd)
        hook = _load_hook()
        from lib import critic_marker as marker  # noqa: PLC0415 — the sweep outcome vocabulary
        return {
            "reading+verdict": reading + verdict,
            "dispatch_refusal": cc.active_dispatch_refusal(pd, 60.0, True),
            "restore_refusal": cc.restore_refusal(pd, ["correctness.x.json"], False),
            # The two members of the class R-6 named.
            "boundary_retained": hook._boundary_retained_marker_notice(
                pd, marker.SWEEP_RETAINED_LIVE
            ),
            "boundary_swept": hook._boundary_swept_marker_notice(pd),
            "forced_live_sweep": hook._forced_live_sweep_notice(pd, 60.0),
        }

    @pytest.mark.parametrize("partials", [0, 2])
    @pytest.mark.parametrize("text", [None, "{not json", "V2"])
    def test_no_composed_message_contradicts_itself(self, tmp_path, text, partials):
        payload = json.dumps(_V2_MANIFEST) if text == "V2" else text
        root = tmp_path / f"contra-{text}-{partials}"
        for name, message in self._compose(root, payload, partials).items():
            low = message.lower()
            says_discard = any(d in low for d in self._DISCARD)
            says_preserve = any(p in low for p in self._PRESERVE)
            assert not (says_discard and says_preserve), (
                f"{name} says BOTH under text={text!r} partials={partials}:\n{message}"
            )

    @pytest.mark.parametrize("partials", [0, 2])
    @pytest.mark.parametrize("text", [None, "{not json", "V2"])
    def test_every_verdict_matches_the_disk(self, tmp_path, text, partials):
        """The property that actually has teeth, and the reason the sibling
        above does not carry this alone.

        Once the readings stopped making keep/discard claims, "says both" became
        unreachable at the two hook notices — so a mutation putting the
        hardcoded "Nothing recoverable was attached" back into
        `_boundary_swept_marker_notice` passed the contradiction test cleanly.
        A pin that cannot fail is decoration. The real requirement was never
        internal consistency: it is that the verdict match the DISK. Reviewer
        output present => no message may tell the operator to discard; none
        present => no message may promise a `critic-restore` handle for an
        archive that will be empty.
        """
        payload = json.dumps(_V2_MANIFEST) if text == "V2" else text
        root = tmp_path / f"disk-{text}-{partials}"
        pd = root / ".prawduct"
        composed = self._compose(root, payload, partials)

        # Exact clause, not a keyword sweep. A keyword list flagged
        # `active_dispatch_refusal` for naming `critic-restore` inside a
        # HYPOTHETICAL ("dispatching now would … until someone ran
        # `critic-restore` on it by name"), which is not a claim about this
        # disk at all — the crude version was finding its own noise.
        _keep, right = cc.anything_worth_keeping(pd)
        for i in range(partials):
            (pd / ".critic-partials" / f"role{i}.rev-x.json").unlink()
        if not partials:
            (pd / ".critic-partials" / "spare.rev-x.json").write_text("{}")
        _other, wrong = cc.anything_worth_keeping(pd)
        assert right != wrong, "fixture guard: the two disks must differ"

        for name in self._VERDICT_BEARING:
            message = composed[name]
            assert right in message, (
                f"{name} does not carry the verdict for its disk "
                f"(text={text!r} partials={partials}). Expected:\n{right}\nGot:\n{message}"
            )
            assert wrong not in message, (
                f"{name} carries the verdict for the OPPOSITE disk "
                f"(text={text!r} partials={partials}):\n{message}"
            )


class TestTheReviewIdReadIsSharedToo:
    """R-5, built as the class it was scoped at rather than closed at the site
    that happened to hurt. Three notices hand-read the manifest for its `id`:
    one tracebacked on an undecodable manifest; the other two swallowed it, and
    one of those ran the read first inside the same `except` — a latent ordering
    hazard no disk could actually show (mutation-checked; `state` there only
    selects a branch a valid manifest is a precondition for), which is why
    nothing below pretends to pin it."""

    def test_a_stale_schema_record_still_lends_its_id(self, tmp_path):
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        stale = _manifest_dict()
        stale.pop("rendezvous")
        _plant(pd, json.dumps(stale))
        assert cc.manifest_condition(pd)[0] == cc.MANIFEST_STALE_SCHEMA
        assert cc.manifest_review_id(pd) == stale["id"]

    @pytest.mark.parametrize("disk", ["absent", "corrupt", "undecodable", "no-id"])
    def test_no_disk_makes_the_read_raise(self, tmp_path, disk):
        """The property the three `except` clauses were standing in for — and
        `undecodable` is the member that used to escape as a traceback."""
        pd = tmp_path / f"d-{disk}" / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        mpath = pd / ".critic-partials" / "manifest.json"
        if disk == "corrupt":
            mpath.write_text("{not json")
        elif disk == "undecodable":
            mpath.write_bytes(b"\xff\xfe\x00binary")
        elif disk == "no-id":
            without_id = _manifest_dict()
            without_id.pop("id")
            mpath.write_text(json.dumps(without_id))
        assert cc.manifest_review_id(pd) == cc.MANIFEST_ID_UNAVAILABLE

    def test_the_lib_unreachable_excuse_is_a_different_fact(self, monkeypatch, tmp_path):
        """Two excuses, deliberately: "no usable manifest" is the lib's answer
        about a disk; "the lib could not be loaded" is the only thing the hook
        can say when there is no lib to ask. A single string for both would
        state one of them falsely."""
        hook = _load_hook()

        def _boom():
            raise RuntimeError("plugin root moved")

        monkeypatch.setattr(hook, "_critic_consolidate", _boom)
        excuse = hook._review_id_for_notice(tmp_path / ".prawduct")
        assert "could not be loaded" in excuse
        assert excuse != cc.MANIFEST_ID_UNAVAILABLE

    def test_the_hooks_unknown_default_is_the_modules_word(self):
        """`cmd_stop` falls back to the literal `"unknown"` where the module it
        would ask is what failed. Inert while they agree — this is what keeps
        them agreeing."""
        hook_src = (
            Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"
        ).read_text()
        assert f'getattr(_cc, "MANIFEST_UNKNOWN", "{cc.MANIFEST_UNKNOWN}")' in hook_src


class TestTheDegradedVerdictIsSharedToo:
    """The verdict clause has one home; so does what it says when the lib that
    owns it cannot be reached. Each of the four notices used to carry its own
    copy of the guard AND of the degraded wording, in the change whose thesis is
    that a verdict has one home — and the copy said only "could not tell",
    naming neither a cause nor anything to run, while the sibling degradations
    in that file all point at `evidence status`."""

    def _degraded(self, monkeypatch, tmp_path):
        hook = _load_hook()

        def _boom():
            raise RuntimeError("plugin root moved")

        monkeypatch.setattr(hook, "_critic_consolidate", _boom)
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        return hook, pd

    def test_the_degraded_clause_names_its_cause_and_a_command(self, monkeypatch, tmp_path):
        hook, pd = self._degraded(monkeypatch, tmp_path)
        keep, verdict = hook._keep_verdict(pd)
        assert keep is True, "err toward preserve: the alternative discards real output"
        assert "RuntimeError" in verdict and "plugin root moved" in verdict
        assert "prawduct-hook evidence status" in verdict

    def test_a_multi_line_exception_cannot_break_the_notice_shape(self, monkeypatch, tmp_path):
        """The clause is spliced into a 2-space-indented block, and an
        exception message is not obliged to be one line — an ImportError
        carrying a traceback-ish body would have laid its own lines into the
        middle of an operator notice."""
        hook = _load_hook()

        def _boom():
            raise RuntimeError("could not import lib\nbecause the root moved\n  badly")

        monkeypatch.setattr(hook, "_critic_consolidate", _boom)
        _keep, verdict = hook._keep_verdict(tmp_path / ".prawduct")
        body = [line for line in verdict.split("\n") if line]
        assert all(line.startswith("  ") for line in body), verdict
        assert "because the root moved badly" in verdict, "flattened, not truncated"

    def test_every_notice_takes_its_verdict_from_the_one_helper(self, monkeypatch, tmp_path):
        """Substituting the helper — not the lib — must move all three boundary
        surfaces, which is only true while none of them still calls
        `anything_worth_keeping` itself. The disk is a marker with no manifest
        (`pending_state` "none"), the one state that reaches the verdict tail:
        complete, incomplete and unknown each return earlier with a remedy of
        their own."""
        hook = _load_hook()
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        from lib import critic_marker as marker  # noqa: PLC0415 — the sweep outcome vocabulary

        monkeypatch.setattr(hook, "_keep_verdict", lambda _pd: (True, "  SENTINEL-CLAUSE\n"))
        composed = [
            hook._boundary_retained_marker_notice(pd, marker.SWEEP_RETAINED_LIVE),
            hook._boundary_swept_marker_notice(pd),
            hook._forced_live_sweep_notice(pd, 60.0),
        ]
        for message in composed:
            assert "SENTINEL-CLAUSE" in message, message


class TestShortDetail:
    """R-12: a validation reason can be a seven-sentence paragraph carrying its
    own recovery sequence. Embedded in a message that then gives a different
    remedy, that is one disk with two recovery stories."""

    def test_the_rendezvous_reason_is_not_smuggled_whole_into_a_message(self, tmp_path):
        """The manifest shape #676 actually describes — a v3-ish record missing
        only `rendezvous`. No earlier fixture reached it: `_V2_MANIFEST`'s
        invalid `mode` short-circuits validation first, so the composed output
        for the MOTIVATING disk had never been read."""
        manifest = _manifest_dict()
        manifest.pop("rendezvous")
        ok, reason = cc.validate_manifest(manifest)
        assert not ok and "rendezvous" in reason
        assert len(reason) > 200, "fixture guard: this is the long remedy-bearing reason"

        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        _plant(pd, json.dumps(manifest))
        _state, reading = cc.pending_roster_reading(pd)
        assert "OLDER PRAWDUCT" in reading
        # The borrowed reason must not bring its own competing remedy along.
        assert "critic-end" not in reading
        assert "/reload-plugins" not in reading
        assert len(reading) < len(reason)

    def test_short_detail_keeps_a_short_reason_intact(self):
        assert cc.short_detail("missing/empty 'id'") == "missing/empty 'id'"

    def test_short_detail_is_empty_for_no_detail(self):
        assert cc.short_detail("") == ""

    def test_the_hard_cap_is_the_backstop_when_there_is_no_sentence_to_cut_at(self):
        """The clause split handles reasons that HAVE sentence ends; the cap is
        what stands between a message and a 700-character reason that has none.
        Every other test here exercises it incidentally and asserts nothing
        about it, so deleting the branch shipped green — the standard this
        bundle set for itself is that a pin which cannot fail is decoration."""
        run_on = "rendezvous covers " + ", ".join(f"role{i}" for i in range(60))
        assert len(run_on) > 400 and ". " not in run_on and "; " not in run_on
        short = cc.short_detail(run_on)
        assert len(short) <= cc._DETAIL_MAX_CHARS
        assert short.endswith("\u2026")
        assert short[:40] == run_on[:40]


class TestManifestConditionIsTotal:
    """R-7: the vocabulary is only a vocabulary if every disk maps into it."""

    def test_undecodable_manifest_is_corrupt_not_a_traceback(self, tmp_path):
        """`read_text()` raises UnicodeDecodeError — a ValueError, not a
        JSONDecodeError — so the narrower clause let it out of a refusal at the
        one moment the caller was trying to explain a broken file."""
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        (pd / ".critic-partials" / "manifest.json").write_bytes(b"\xff\xfe\x00binary")
        condition, detail, manifest = cc.manifest_condition(pd)
        assert condition == cc.MANIFEST_CORRUPT
        assert detail and manifest is None
        # ...and every surface that composes it survives the same disk.
        assert cc.pending_roster_reading(pd)[0] == "unreadable"
        assert cc.restore_refusal(pd, ["x.json"], False)
        assert cc.anything_worth_keeping(pd)[0] is False
        # The surface #676 was filed against, and the one this test's first cut
        # left out: `active_dispatch_refusal` hand-read the manifest under the
        # pre-R-7 narrow `except`, so the widening landed everywhere EXCEPT the
        # refusal that motivated it and this disk tracebacked out of
        # `critic-begin` instead of refusing.
        refusal = cc.active_dispatch_refusal(pd, 60.0, True)
        assert "id unavailable" in refusal
        # The two members the FIRST enumeration of this class missed, both
        # reachable and both worse than the refusal: `_archive_leftovers` runs
        # inside `begin_review` on exactly this disk (an unusable manifest is
        # why the sweep is reached at all), and `consolidate` is driven by the
        # SubagentStop hook. Composed here rather than trusted to the site list,
        # because a class closed at the sites someone remembered is how this one
        # survived two rounds.
        (pd / ".critic-partials" / "correctness.rev-x.json").write_text("{}")
        archived = cc._archive_leftovers(pd)
        assert archived is not None and archived.name.startswith("unmanifested-")
        assert (archived / "correctness.rev-x.json").is_file()

    def test_a_stale_schema_record_still_lends_the_refusal_its_id(self, tmp_path):
        """The reason the refusal reads the classifier's RECORD and not just a
        `valid` verdict: a manifest can fail validation on some other field and
        still carry the id the operator needs to name the review."""
        pd = tmp_path / ".prawduct"
        (pd / ".critic-partials").mkdir(parents=True)
        stale = _manifest_dict()
        stale.pop("rendezvous")
        _plant(pd, json.dumps(stale))
        assert cc.manifest_condition(pd)[0] == cc.MANIFEST_STALE_SCHEMA
        assert stale["id"] in cc.active_dispatch_refusal(pd, 60.0, True)

    def test_the_unknown_word_belongs_to_the_module(self):
        """A caller that catches an exception needs a word for "could not
        tell"; the first cut invented one at the call site, re-opening in
        miniature the split this module exists to close."""
        assert cc.MANIFEST_UNKNOWN == "unknown"
        assert cc.MANIFEST_UNKNOWN not in {
            cc.MANIFEST_ABSENT, cc.MANIFEST_CORRUPT,
            cc.MANIFEST_STALE_SCHEMA, cc.MANIFEST_VALID,
        }


class TestRestoreRefusalDescribesTheDisk:
    """`restore_refusal` carried the same defect in miniature and had no test
    of its own — it printed "no readable dispatch manifest" for an ABSENT
    manifest and for a stale-schema one alike."""

    def _refuse(self, tmp_path, text=None):
        (tmp_path / ".prawduct").mkdir(parents=True)
        if text is not None:
            _plant(tmp_path / ".prawduct", text)
        return cc.restore_refusal(tmp_path / ".prawduct", ["correctness.x.json"], False)

    def test_absent(self, tmp_path):
        message = self._refuse(tmp_path / "a")
        assert "no dispatch manifest" in message
        assert "older prawduct" not in message

    def test_corrupt(self, tmp_path):
        message = self._refuse(tmp_path / "c", "{not json")
        assert "not valid JSON" in message

    def test_stale_schema(self, tmp_path):
        message = self._refuse(tmp_path / "s", json.dumps(_V2_MANIFEST))
        assert "older prawduct" in message

    def test_all_three_stay_distinguishable(self, tmp_path):
        messages = [
            self._refuse(tmp_path / f"d{i}", text)
            for i, text in enumerate((None, "{not json", json.dumps(_V2_MANIFEST)))
        ]
        assert len(set(messages)) == 3, messages

    def test_every_condition_still_names_critic_discard(self, tmp_path):
        """The remedy is what this surface exists for, and it must survive the
        message split — `critic-end` would send the caller back to an identical
        refusal, which is the failure the function's docstring names."""
        for i, text in enumerate((None, "{not json", json.dumps(_V2_MANIFEST))):
            message = self._refuse(tmp_path / f"r{i}", text)
            assert "prawduct-hook critic-discard" in message
            assert "archived, never deleted" in message


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

    def test_consolidated_with_findings_carries_the_fix_strategy(self, tmp_path):
        """A review that lands findings states the fix strategy in the same
        breath. This is the single-pass path's delivery: the reviewing fork
        runs consolidate itself, so this stdout IS what the builder reads."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head, findings_by_role={
            "correctness": [{"name": "A", "goal": "Nothing Is Broken",
                             "severity": "blocking", "recommendation": "Fix"}],
            "design": [{"name": "B", "goal": "The Design Is Sound",
                        "severity": "warning", "recommendation": "Reconsider"}],
        })
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated:" in result.stdout
        assert cc._BATCH_FIX_DIRECTIVE in result.stdout

    def test_an_undecodable_manifest_exits_one_rather_than_tracebacking(self, tmp_path):
        """The CLI leg of the same class. This path is driven by the
        SubagentStop hook, so a traceback here surfaces as a hook crash rather
        than as the "manifest unreadable" refusal the code already had — the
        narrow `except` simply never covered the byte sequence that produces
        it."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        (repo / PARTIALS_REL / "manifest.json").write_bytes(b"\xff\xfe\x00binary")

        result = _run_consolidate(repo)
        assert result.returncode == 1, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert "manifest unreadable" in result.stderr
        assert "Traceback" not in result.stderr

    def test_clean_pass_does_not_carry_the_fix_strategy(self, tmp_path):
        """Zero findings, zero fix advice — a clean review that ended with
        batching instructions reads as work the builder does not have."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "consolidated: 0 blocking" in result.stdout
        assert cc._BATCH_FIX_DIRECTIVE not in result.stdout
        # ...but the relay line is UNCONDITIONAL, and the clean pass is the
        # case it matters most in — "the review is over" is the whole message.
        # The batch directive two lines above is deliberately `if all_findings`;
        # an editor mirroring that condition onto this print would kill the
        # clean-pass variant while every prose pin stayed green, so the producer
        # is asserted against real stdout rather than against source text.
        assert "NEXT-ACTION: " in result.stdout
        assert "THE REVIEW IS OVER" in result.stdout

    def test_already_consolidated_noop_reports_the_recorded_findings(self, tmp_path):
        """The COORDINATOR path's normal case. The SubagentStop trigger
        consolidated while the main agent was elsewhere; that agent then runs
        consolidate before reading the cache (CLAUDE.md's staleness guard) and
        lands here. A bare "nothing to consolidate" answers the wrong question
        and drops the fix strategy on the one path that has no other channel
        for it — the reviewing fork returns after dispatch without a summary."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head, findings_by_role={
            "correctness": [{"name": "A", "goal": "Nothing Is Broken",
                             "severity": "blocking", "recommendation": "Fix"}],
        })
        assert _run_consolidate(repo).returncode == 0   # the trigger's run
        second = _run_consolidate(repo)                 # the main agent's run
        assert second.returncode == 0, f"stderr={second.stderr!r}"
        assert "no-op: no pending review manifest" in second.stdout
        assert "holds 1 finding(s)" in second.stdout
        assert "rev-test-0001" in second.stdout
        # The path must be readable as-is: the caller's next action is to open
        # it, and a bare basename is not a path from the project root.
        assert f"`{FINDINGS_REL}`" in second.stdout
        assert cc._BATCH_FIX_DIRECTIVE in second.stdout

    def test_noop_stays_bare_when_the_recorded_review_was_clean(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        _full_roster_partials(repo, head)
        assert _run_consolidate(repo).returncode == 0
        second = _run_consolidate(repo)
        assert second.returncode == 0
        assert "no-op: no pending review manifest" in second.stdout
        assert "finding(s)" not in second.stdout
        assert cc._BATCH_FIX_DIRECTIVE not in second.stdout

    def test_noop_survives_an_unreadable_findings_cache(self, tmp_path):
        """A corrupt cache must not crash an informational no-op — AND must not
        pass silently, because absence of the note is the "clean review" signal.

        Returning "" here would report a corrupt cache as a clean review to the
        exact caller CLAUDE.md routes through this branch. The diagnostic is what
        makes absence mean only "clean"; without this assertion a revert to
        ``return ""`` passes green and reinstates the swallow-into-empty-string
        defect.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        (repo / FINDINGS_REL).write_text("{not json")
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "no-op: no pending review manifest" in result.stdout
        assert "unreadable" in result.stdout
        assert "not a clean-review signal" in result.stdout
        assert cc._BATCH_FIX_DIRECTIVE not in result.stdout

    def test_noop_reports_a_byte_corrupted_cache_rather_than_crashing(self, tmp_path):
        # read_text() raises UnicodeDecodeError — a ValueError, NOT an OSError
        # and not a JSONDecodeError. The original narrower catch would traceback
        # on the branch the SubagentStop hook reaches.
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        (repo / FINDINGS_REL).write_bytes(b"\xff\xfe not utf-8")
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "unreadable" in result.stdout
        assert "not a clean-review signal" in result.stdout

    def test_noop_reports_a_wrong_shaped_cache_rather_than_reading_it_as_clean(
        self, tmp_path
    ):
        # Valid JSON, wrong shape: parses fine, has no findings list. Silence
        # here would be indistinguishable from a genuinely clean review.
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        (repo / FINDINGS_REL).write_text('["not", "a", "record"]')
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "not a findings record" in result.stdout
        assert "not a clean-review signal" in result.stdout

    def test_noop_stays_silent_when_no_cache_exists_at_all(self, tmp_path):
        # A repo that has never been reviewed is not a corrupt one — no
        # diagnostic, or every first-ever consolidate cries wolf.
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert result.stdout.strip() == (
            "no-op: no pending review manifest — nothing to consolidate."
        )

    def test_noop_note_states_the_age_and_qualifies_dispositioned_findings(
        self, tmp_path
    ):
        """The note names a review it cannot prove is the caller's, so it says
        how old it is and that already-dispositioned findings are history.

        Uses a REAL minted id: the neighbouring fixtures use ``rev-test-0001``,
        which ``_REVIEW_ID_TS`` never matches, so the age branch is unreachable
        with them — the gap that let this ship untested.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        (repo / FINDINGS_REL).write_text(json.dumps({
            "fact_id": cc.mint_review_id(),
            "findings": [{"fid": "R-1", "severity": "warning", "summary": "x"}],
        }))
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "holds 1 finding(s)" in result.stdout
        assert "dispatched 0 min ago" in result.stdout
        assert "already dispositioned, this is history, not work" in result.stdout
        assert cc._BATCH_FIX_DIRECTIVE in result.stdout

    def test_noop_note_omits_the_age_when_the_id_carries_no_timestamp(self, tmp_path):
        # Hand-written ids have no parseable stamp; the note must degrade to no
        # age claim rather than invent or crash on one.
        repo = tmp_path / "r"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        (repo / FINDINGS_REL).write_text(json.dumps({
            "fact_id": "rev-test-0001",
            "findings": [{"fid": "R-1", "severity": "note", "summary": "x"}],
        }))
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "holds 1 finding(s)" in result.stdout
        assert "min ago" not in result.stdout

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
        (repo / PARTIALS_REL / f"sustainability.{FAKE_REVIEW_ID}.json").write_text(json.dumps({
            "role": "sustainability", "goals": "5-6", "commit_reviewed": head,
            "dispatch_id": FAKE_REVIEW_ID,
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
        _abandon(repo)  # the first dispatch is live; abandon before re-dispatching
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


class TestBeginArchivesLeftovers:
    """A leftover manifest at critic-begin belongs to a review that never
    consolidated (consolidate removes everything on success). Deleting it
    erased the only evidence that review ran — observed 2026-08-02 when a
    premature death verdict led to a re-dispatch and the first review became
    unreconstructable from disk. begin_review archives instead."""

    ARCHIVE_REL = ".prawduct/.critic-partials-archive"

    def _repo_with_leftovers(self, tmp_path, manifest_id: str | None):
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        stale = repo / PARTIALS_REL
        stale.mkdir(parents=True)
        if manifest_id is not None:
            (stale / "manifest.json").write_text(json.dumps({"id": manifest_id}))
        (stale / "correctness.json").write_text('{"role": "correctness"}')
        (repo / "src/app.py").write_text("x = 2\n")  # dirty tree → reviewable
        return repo

    def test_prior_manifest_archived_under_its_review_id(self, tmp_path):
        repo = self._repo_with_leftovers(tmp_path, "rev-20260802T190415Z-0e2cd074")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        archived = repo / self.ARCHIVE_REL / "rev-20260802T190415Z-0e2cd074"
        assert json.loads((archived / "manifest.json").read_text())["id"] == (
            "rev-20260802T190415Z-0e2cd074"
        )
        assert (archived / "correctness.json").is_file()
        # The new dispatch proceeded normally on a clean partials dir.
        new_manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert new_manifest["id"] != "rev-20260802T190415Z-0e2cd074"
        assert not (repo / PARTIALS_REL / "correctness.json").exists()
        assert "archived" in result.stdout

    def test_partials_without_a_manifest_archive_under_a_fallback_name(self, tmp_path):
        # Partials can outlive their manifest (a late reviewer re-creates the
        # dir after consolidation) — they still archive rather than vanish.
        repo = self._repo_with_leftovers(tmp_path, manifest_id=None)
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        adir = repo / self.ARCHIVE_REL
        entries = [d for d in adir.iterdir() if d.is_dir()]
        assert len(entries) == 1
        assert entries[0].name.startswith("unmanifested-")
        assert (entries[0] / "correctness.json").is_file()

    def test_a_traversal_shaped_manifest_id_archives_under_the_fallback_name(self, tmp_path):
        # The hostile twin of the fallback test above. `_archive_leftovers`
        # takes the id from a record that may be STALE-SCHEMA — it must work
        # when the manifest is unusable, which is the case that reaches it — so
        # the validator's verdict is discarded here and the id becomes a
        # directory name on the strength of the local component gate alone.
        # `rev-../../escape` walked up out of the archive dir; and the failure
        # is silent by construction, because a successful traversal prints
        # nothing and an OSError degrades to DELETE.
        repo = self._repo_with_leftovers(tmp_path, "rev-../../escape")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        entries = [d for d in (repo / self.ARCHIVE_REL).iterdir() if d.is_dir()]
        assert len(entries) == 1
        assert entries[0].name.startswith("unmanifested-"), (
            f"a traversal-shaped id was used as a directory name: {entries[0].name}"
        )
        assert (entries[0] / "correctness.json").is_file(), "the partial still archived"
        # Nothing landed outside the repo — the assertion the name check exists for.
        assert not (tmp_path / "escape").exists()
        assert not (repo / ".prawduct" / "escape").exists()

    def test_archive_prunes_to_the_newest_three(self, tmp_path):
        import os
        repo = self._repo_with_leftovers(tmp_path, "rev-20260802T190415Z-0e2cd074")
        adir = repo / self.ARCHIVE_REL
        now = datetime.now(timezone.utc).timestamp()
        for i in range(3):
            old = adir / f"rev-old-{i}"
            old.mkdir(parents=True)
            (old / "manifest.json").write_text("{}")
            os.utime(old, (now - (i + 1) * 3600, now - (i + 1) * 3600))
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        kept = sorted(d.name for d in adir.iterdir() if d.is_dir())
        assert len(kept) == cc._ARCHIVE_KEEP == 3
        assert "rev-20260802T190415Z-0e2cd074" in kept  # newest survives
        assert "rev-old-2" not in kept  # oldest pruned

    def test_archive_dir_is_gitignored_for_products(self):
        from lib import core
        assert ".prawduct/.critic-partials-archive/" in core.GITIGNORE_ENTRIES

    def test_failed_archive_degrades_to_delete_never_blocks_dispatch(self, tmp_path):
        # The archive is forensics, not a gate: when it cannot be written the
        # dispatch must proceed exactly as the old delete behavior did. Forced
        # here by pre-creating the archive path as a FILE, so dest.mkdir()
        # raises OSError. The failure is named on stderr, not swallowed.
        repo = self._repo_with_leftovers(tmp_path, "rev-20260802T190415Z-0e2cd074")
        (repo / self.ARCHIVE_REL).write_text("not a directory")
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "archive failed" in result.stderr
        assert "falling back to delete" in result.stderr
        assert "archived" not in result.stdout  # no false preservation claim
        # Old delete behavior held: leftovers gone, fresh dispatch on disk.
        assert not (repo / PARTIALS_REL / "correctness.json").exists()
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    def test_remove_partials_clears_started_markers(self, tmp_path):
        # remove_partials unlinks ALL children, .started markers included —
        # pinned because a future narrowing to *.json would leave stale
        # markers feeding the NEXT review's death verdict (the exact
        # false-signal class this fix targets) with the suite still green.
        prawduct = tmp_path / ".prawduct"
        pdir = cc.partials_dir(prawduct)
        pdir.mkdir(parents=True)
        (pdir / "manifest.json").write_text("{}")
        (pdir / "correctness.json").write_text("{}")
        cc.started_path(prawduct, "correctness", FAKE_REVIEW_ID).write_text("correctness")
        cc.remove_partials(prawduct)
        assert not pdir.exists()


class TestBeginMarksFindingsSuperseded:
    """The derived view's half of the problem the class above solves for
    partials (#595).

    Leftover partials are archived at dispatch, so nothing from the previous
    review is left where the current one's belongs. `.critic-findings.json`
    got no such treatment: it survived every dispatch carrying nothing that
    marked it stale, so between `critic-begin` and the consolidation that
    regenerates it a reader met the PREVIOUS review's findings in a file that
    looked exactly like the current one's — on the one surface the builder is
    guaranteed to meet.

    It MARKS rather than deletes, and the distinction is load-bearing:
    `_prior_review_fact` reads this file's `fact_id` to anchor a
    verify-resolutions delta, so deleting at dispatch would strand the next
    verify after any review waived or abandoned before consolidating —
    trading a cosmetic ambiguity for a lost anchor.
    `test_verify_still_anchors_after_an_abandoned_review` is the pin that goes
    red if a later edit "simplifies" the mark into a delete.
    """

    def _repo_with_a_completed_review(self, tmp_path) -> tuple[Path, str, str]:
        """A repo holding one consolidated review (blocking finding, cache
        pointing at its fact) and a dirty tree, so the next dispatch has both
        something to mark and something to review. Returns (repo, head, id)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        (repo / ".prawduct").mkdir(exist_ok=True)
        prior_id = _seed_prior_review_with_blocker(
            repo, head, head_tree=head_tree, head_commit=head
        )
        (repo / "src/app.py").write_text("x = 2\n")
        return repo, head, prior_id

    def test_dispatch_marks_the_prior_record_naming_both_reviews(self, tmp_path):
        repo, _head, prior_id = self._repo_with_a_completed_review(tmp_path)
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        new_id = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())["id"]

        raw = (repo / FINDINGS_REL).read_text()
        record = json.loads(raw)
        assert record["superseded_by"] == new_id
        assert record["superseded_at"]
        # Both ids: which review superseded this record, and which review this
        # record IS. A reader holding neither can place the file from the text
        # alone — no timestamp arithmetic against an id it may not have.
        notice = record["superseded_notice"]
        assert new_id in notice and prior_id in notice

        # FIRST in the file, so the marker is met before the findings and the
        # `next_action` it qualifies — a reader that stops early stops on the
        # warning, not on the previous review's directive.
        assert list(record)[:3] == list(cc._SUPERSEDED_KEYS)
        assert raw.index("superseded_by") < raw.index('"next_action"')

        # And said at the dispatching context too: that is the one reader
        # certain to be present at the moment the stale window opens.
        assert "superseded_by" in result.stdout and new_id in result.stdout

    def test_marking_preserves_every_other_field(self, tmp_path):
        repo, _head, prior_id = self._repo_with_a_completed_review(tmp_path)
        before = json.loads((repo / FINDINGS_REL).read_text())
        assert before.get("findings"), "fixture must seed a finding to preserve"
        assert _run_begin(repo, "--mode", "chunk").returncode == 0
        after = json.loads((repo / FINDINGS_REL).read_text())
        # Marked AND preserved. Without the first assertion this reduces to
        # "the file did not change", which holds identically when the marker
        # is not written at all — the variable under test erased by the check.
        assert after.get("superseded_by")
        assert {k: v for k, v in after.items() if k not in cc._SUPERSEDED_KEYS} == before
        # The anchor pointer specifically — everything below rests on it.
        assert after["fact_id"] == prior_id

    def test_verify_still_anchors_after_an_abandoned_review(self, tmp_path):
        """The reason this marks instead of deleting.

        Review A consolidates; review B is dispatched and never consolidates
        (waived, crashed, or abandoned via `critic-end`); the next
        verify-resolutions must still anchor to A — which is the correct
        anchor, since B produced no fact. Deleting the cache at B's dispatch
        would leave this pass with no anchor at all, failing it closed.
        """
        repo, _head, prior_id = self._repo_with_a_completed_review(tmp_path)
        assert _run_begin(repo, "--mode", "chunk").returncode == 0  # B dispatched…
        subprocess.run(  # …and abandoned without consolidating
            ["python3", str(HOOK), "critic-end"],
            cwd=str(repo), capture_output=True, text=True,
            env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
        )
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        prior_fact = next(f for f in _store_facts(repo, "review") if f["id"] == prior_id)
        assert manifest["base_tree"] == prior_fact["body"]["head_tree"]

    def test_consolidation_clears_the_marker(self, tmp_path):
        repo, _head, prior_id = self._repo_with_a_completed_review(tmp_path)
        assert _run_begin(repo, "--mode", "chunk").returncode == 0
        assert "superseded_by" in json.loads((repo / FINDINGS_REL).read_text())

        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        for role in manifest["roster"]:
            _write_partial(repo, role, manifest["commit_reviewed"])
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"

        after = json.loads((repo / FINDINGS_REL).read_text())
        assert [k for k in cc._SUPERSEDED_KEYS if k in after] == []
        # Cleared because the whole record was rewritten from the NEW fact —
        # not because anything went looking for the keys.
        assert after["fact_id"] == manifest["id"] != prior_id

    def test_a_second_dispatch_restamps_rather_than_stacks(self, tmp_path):
        repo, _head, prior_id = self._repo_with_a_completed_review(tmp_path)
        assert _run_begin(repo, "--mode", "chunk").returncode == 0
        first_marker = json.loads((repo / FINDINGS_REL).read_text())["superseded_by"]
        _abandon(repo)  # the first dispatch is live; abandon before re-dispatching
        assert _run_begin(repo, "--mode", "chunk").returncode == 0

        raw = (repo / FINDINGS_REL).read_text()
        record = json.loads(raw)
        second = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())["id"]
        assert second != first_marker
        assert record["superseded_by"] == second
        assert first_marker not in raw  # re-stamped, not layered
        for key in cc._SUPERSEDED_KEYS:
            assert raw.count(f'"{key}"') == 1
        assert record["fact_id"] == prior_id  # still the last COMPLETED review

    def test_a_marked_record_still_passes_the_findings_validator(self, tmp_path):
        # `ledger.py` validates this record through
        # `gates.validate_critic_findings` before anchoring a `review.critic`
        # event. Extra keys must not turn a legitimate record into a rejected
        # one — the marker is additive or it is a regression.
        repo, _head, _prior = self._repo_with_a_completed_review(tmp_path)
        assert gates.validate_critic_findings(repo / FINDINGS_REL)
        assert _run_begin(repo, "--mode", "chunk").returncode == 0
        # Assert the marker landed FIRST: without it this validates an
        # unmarked record and passes whether or not the marker exists.
        assert json.loads((repo / FINDINGS_REL).read_text()).get("superseded_by")
        assert gates.validate_critic_findings(repo / FINDINGS_REL)

    def _repo_without_a_review(self, tmp_path) -> Path:
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")
        return repo

    def test_no_cache_is_not_an_error_and_invents_nothing(self, tmp_path):
        repo = self._repo_without_a_review(tmp_path)
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert not (repo / FINDINGS_REL).exists()
        assert "superseded" not in result.stdout

    def test_an_unreadable_cache_is_left_alone_and_never_blocks_dispatch(self, tmp_path):
        # The view is advisory; a dispatch must never fail over it. A truncated
        # cache is the shape `critic_findings_note` already reads this file
        # behind (UnicodeDecodeError, not just JSONDecodeError).
        repo = self._repo_without_a_review(tmp_path)
        raw = '{"summary": "truncated mid-w'
        (repo / FINDINGS_REL).write_text(raw)
        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (repo / FINDINGS_REL).read_text() == raw  # untouched, not half-rewritten
        assert (repo / PARTIALS_REL / "manifest.json").is_file()  # dispatch proceeded
        assert "superseded" not in result.stdout


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
        # And it must prescribe the verbatim commit rather than another pass.
        # The half above survived an edit that replaced "commit (or stash) the
        # fix and re-run verify-resolutions" — a superfluous round, and wrong on
        # the merits, since the commit carries the very tree this pass vouched
        # for. An unpinned rule is what the next trim deletes first.
        assert "Commit this tree VERBATIM and no further pass is needed" in result.stderr
        assert "Only a selective or further-edited commit leaves a gap" in result.stderr

    def _seed_dirty_tree_review_with_blocker(
        self, repo: Path
    ) -> tuple[str, str, str]:
        """A review of a DIRTY tree that left a blocker — then a fix, uncommitted.

        This is the ordinary shape of a `chunk`-mode review: the fact records the
        working tree's hash as ``head_tree`` and **no** ``head_commit``, so the
        anchor it leaves is AHEAD of committed HEAD. Returns
        ``(head commit, reviewed tree, prior id)``.

        `.prawduct/` is gitignored for the same reason as the clean-review
        fixture: consolidating writes the ledger and the findings cache, which
        would otherwise dirty the tree by the act of recording that it reviewed
        it.
        """
        _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir(exist_ok=True)
        (repo / "src/app.py").write_text("x = 2  # reviewed while dirty\n")
        reviewed_tree = evidence.capture_tree(repo)["tree"]
        prior_id = _seed_prior_review_with_blocker(
            repo, head, head_tree=reviewed_tree, head_commit=None
        )
        # The builder fixes the blocker WITHOUT committing — the case the issue
        # describes, and the case `review-cycle.md` explicitly permits.
        (repo / "src/app.py").write_text("x = 2  # reviewed while dirty, then fixed\n")
        return head, reviewed_tree, prior_id

    def test_uncommitted_fix_after_dirty_tree_review_runs_the_interval_forward(
        self, tmp_path
    ):
        """A prior anchor that is AHEAD of HEAD is not a committed delta.

        `committed_differs` asked only whether the captured committed tree
        differs from the prior fact's ``head_tree``. That is true in two
        opposite situations: a commit landed after the prior review (anchor
        BEHIND — the case the code was written for), and the prior review
        vouched for a dirty tree and nothing has been committed since (anchor
        AHEAD — this case, and the normal shape of a `chunk`-mode review).

        Taking the committed-HEAD branch here inverts the edge: base becomes the
        dirty snapshot that is ahead, head becomes the committed tree that is
        behind, and the recorded delta describes the fix being *deleted*. The
        load-bearing consequence is that the resolution facts this pass writes
        are anchored to a tree in which the fixes do not exist — and a
        resolution lifts a BLOCKING finding.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        head, reviewed_tree, prior_id = self._seed_dirty_tree_review_with_blocker(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())

        committed_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        working_tree = evidence.capture_tree(repo)["tree"]
        assert committed_tree != reviewed_tree, (
            "fixture precondition: the prior anchor must be AHEAD of committed "
            "HEAD, which is what makes the two situations indistinguishable"
        )

        # Nothing was committed, so this pass vouches for the WORKING tree.
        assert manifest["head_commit"] is None
        assert manifest["head_tree"] == working_tree
        assert manifest["head_tree"] != committed_tree
        assert manifest["base_tree"] == reviewed_tree

        # The edge runs forward: base is the tree the prior review saw, head is
        # the tree carrying the fix. Diffing it must show the fix, not its
        # removal.
        diff = _git(
            repo, "diff", manifest["base_tree"], manifest["head_tree"]
        ).stdout
        assert "then fixed" in diff, (
            "the interval must show the fix ARRIVING; a swapped edge shows it "
            "being deleted"
        )
        assert manifest["commit_reviewed"] == head
        assert prior_id  # the fact this pass chains from

    def test_dirty_prior_with_a_landed_commit_still_anchors_committed_head(
        self, tmp_path
    ):
        """A commit that CHANGES content moves the anchor — dirty prior or not.

        `anchor_is_ahead` has two conjuncts, and the second — HEAD still
        standing where the prior review dispatched — is what stops the first
        from over-reaching. Against a dirty prior fact (`head_commit: null`) the
        first conjunct is already true on its own, so dropping the second would
        force the working-tree anchor even after a real fix landed. A stray
        judgeable uncommitted file would then leave the PR gate `uncovered`:
        CRT-7H2W re-opened one prior-fact-shape over, where
        `test_committed_fix_with_dirty_wip_anchors_committed_head` cannot see it
        because its prior fact is clean.

        This is the (dirty prior × content-changing landed commit) cell of the
        four-way matrix; the other three are covered above.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        head, reviewed_tree, _prior_id = self._seed_dirty_tree_review_with_blocker(repo)

        # The fix LANDS as a commit, carrying content the prior review never saw.
        fix = _commit_file(
            repo,
            "src/app.py",
            "x = 2  # reviewed while dirty, then fixed\n",
            "fix blocker",
        )
        committed_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        assert fix != head, "fixture precondition: HEAD must have moved"
        assert committed_tree != reviewed_tree, (
            "fixture precondition: the landed commit must CHANGE content — a "
            "verbatim vouching commit is the other case, covered separately"
        )
        (repo / "src/extra.py").write_text("y = 3\n")  # judgeable uncommitted WIP

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())

        # A commit landed, so this pass anchors the PR-gate target, and the WIP
        # is noted-and-excluded rather than silently swept in.
        assert manifest["head_commit"] == fix
        assert manifest["head_tree"] == committed_tree
        assert manifest["base_tree"] == reviewed_tree
        assert "anchored to committed HEAD" in result.stderr

    def _seed_clean_dirty_tree_review(self, repo: Path) -> str:
        """A CLEAN review of a DIRTY working tree — the state
        `review-cycle.md` says vouches for the commit that materializes it.

        The fact records the working tree's hash as `head_tree` and no
        `head_commit`, which is exactly what a dirty-tree dispatch writes.
        Returns that tree hash.

        The review's own bookkeeping is gitignored — the findings cache, the
        partials and the ledger all land under `.prawduct/`, and consolidating
        would otherwise dirty the tree by the act of recording that it reviewed
        it, so no fixture could reach the state under test. Ignoring the whole
        directory is broader than a real repo does; what it buys here is a tree
        whose only content is the code under review.
        """
        _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir(exist_ok=True)
        (repo / "src/app.py").write_text("x = 2  # reviewed while dirty\n")
        capture = evidence.capture_tree(repo)
        reviewed_tree = capture["tree"]
        _set_marker(repo)
        _write_manifest(
            repo, head, id="rev-prior-0001", head_tree=reviewed_tree,
            head_commit=None,
        )
        _full_roster_partials(repo, head)  # clean: no findings at all
        result = _run_consolidate(repo)
        assert result.returncode == 0, f"seed failed: {result.stderr!r}"
        return reviewed_tree

    def test_the_vouching_commit_does_not_move_the_anchor(self, tmp_path):
        """Committing the reviewed tree verbatim, then working on: the pass runs.

        The anchor branch used to read a COMMIT-set diff while the refusal guard
        read a TREE delta, and the two disagree here and nowhere else. The
        vouching commit — the one `review-cycle.md` says the dirty-tree review
        vouches FOR — made the commit set non-empty, moved the anchor to
        committed HEAD, and left the tree delta empty. `critic-begin` then exited
        1 saying "nothing changed since" while unreviewed work sat in the tree:
        a refusal that reads as "everything is reviewed" and means "everything I
        chose to look at is reviewed".
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        reviewed_tree = self._seed_clean_dirty_tree_review(repo)

        # The vouching commit: the reviewed content, committed verbatim.
        vouching = _commit_file(repo, "src/app.py", "x = 2  # reviewed while dirty\n",
                                "commit the reviewed tree")
        assert _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip() == reviewed_tree, (
            "the fixture must commit the reviewed tree VERBATIM — that is the "
            "whole mechanism"
        )
        # …then real, unreviewed work lands in the working tree.
        (repo / "src/app.py").write_text("x = 3  # NOT reviewed by anyone\n")

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        # Anchored at the WORKING tree: the commit changed no content, so it is
        # not a change of intent.
        assert manifest["base_tree"] == reviewed_tree
        assert manifest["head_tree"] != reviewed_tree
        assert manifest["head_commit"] is None
        assert "src/app.py" in manifest["files_changed"], (
            "the unreviewed work is IN the reviewed scope, which is the point"
        )
        assert vouching  # the commit exists; it simply does not move the anchor

    def test_nothing_to_verify_names_the_tree_it_compared(self, tmp_path):
        """The genuine no-op still refuses — with a message that says what it read.

        Under the tree-inequality anchor an empty delta means the tree really is
        unchanged, so this refusal is honest. It names the anchor and both tree
        hashes anyway: the previous wording was true of the anchor and false of
        the repo, and nothing in it let a builder tell which.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        reviewed_tree = self._seed_clean_dirty_tree_review(repo)
        _commit_file(repo, "src/app.py", "x = 2  # reviewed while dirty\n",
                     "commit the reviewed tree")

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 1
        assert "nothing to verify" in result.stderr
        assert "the working tree" in result.stderr
        assert reviewed_tree[:12] in result.stderr

    def test_a_non_ancestor_prior_anchor_refuses_for_demotion(self, tmp_path):
        """A sibling branch's review fact must not anchor this branch's pass.

        The findings cache is single-slot and survives a branch switch, and
        worktrees of one clone share an object store — so the anchor still
        RESOLVES, which is all the old guard asked. The delta from it would span
        the divergence and fill the review with changes this branch never made.
        The `_commit_resolves` assertion below is the load-bearing half: without
        it this test would stay green against a build that dropped the ancestor
        check, because it would be proving nothing about which guard refused.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()

        _git(repo, "checkout", "--quiet", "-b", "sibling")
        sibling_tip = _commit_file(repo, "src/app.py", "x = 99  # sibling\n", "sibling")
        sibling_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        _git(repo, "checkout", "--quiet", "main")

        # The prior fact belongs to the sibling: its anchor is that branch's tip.
        prior_id = _seed_prior_review_with_blocker(
            repo, sibling_tip, head_tree=sibling_tree, head_commit=sibling_tip
        )
        (repo / "src/app.py").write_text("x = 2  # my fix\n")

        assert _commit_resolves(repo, sibling_tip), (
            "the old guard passes this anchor — that is the defect"
        )
        assert not _commit_is_ancestor(repo, sibling_tip)

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 1
        assert "another lineage" in result.stderr, result.stderr
        assert prior_id in result.stderr

    def test_a_dirty_tree_fact_falling_back_to_dispatch_commit_is_not_refused(
        self, tmp_path
    ):
        """Fail-closed must not tighten into stranding the builder.

        A review of a dirty tree records **no `head_commit`**, so the anchor
        falls back to `dispatch_commit`. That fallback is the branch the guard
        could most easily break, so the fixture must actually reach it: an
        earlier version of this test seeded `head_commit=head` and never left the
        first branch, pinning a case its own name did not describe. On a branch
        that landed a commit for tests which "proved" a fix while passing against
        the defect, a test misdescribing its own fixture is that hazard one layer
        up.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        reviewed_tree = self._seed_clean_dirty_tree_review(repo)
        prior = next(
            f for f in _store_facts(repo, "review") if f["id"] == "rev-prior-0001"
        )
        assert prior["body"]["head_commit"] is None, (
            "the fixture must reach the dispatch_commit fallback, not the "
            "head_commit branch — that is the whole point of this test"
        )
        anchor = prior["body"]["dispatch_commit"]
        assert _commit_is_ancestor(repo, anchor)

        # Real unreviewed work, so the pass has something to verify.
        (repo / "src/app.py").write_text("x = 3  # further fix\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["base_tree"] == reviewed_tree

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

    def test_an_uncommitted_widening_names_final(self, tmp_path):
        """`_seed_and_fix` leaves everything uncommitted, so HEAD-tree →
        working-tree is exactly the widened delta. `final` covers it.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        for i in range(2 * 1 + 6):
            (repo / f"src/new_{i}.py").write_text(f"n = {i}\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert "Re-dispatch as `final`" in result.stderr, result.stderr
        # The reason, not just the mode. This fixture sits on `main`, where
        # merge-base == HEAD, so a wrongly-True `committed_differs` would reach
        # `final` through the empty-span guard instead and the mode assertion
        # alone would still pass — leaving the branch this test names untested.
        assert "every change since the prior review is uncommitted" in result.stderr

    def test_a_committed_widening_names_cumulative_not_final(self, tmp_path):
        """The defect this pins: a widening made of COMMITTED work demoted to
        `final`, whose HEAD-tree → working-tree interval cannot see a commit.
        The replacement was narrower than the interval refused for being too
        wide, so the re-dispatch reviewed whatever the working tree held —
        untracked strays, in the observed case — and reported it as the chunk's
        review. `cumulative` spans merge-base…HEAD and actually covers it.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        # A feature branch, so a merge-base exists to span. The fix and the
        # widening both LAND — this is the post-commit shape of the incident.
        _git(repo, "checkout", "-q", "-b", "feature/demo")
        _commit_file(repo, "src/app.py", "x = 2  # fixed\n", "fix")
        for i in range(2 * 1 + 6):
            _commit_file(repo, f"src/new_{i}.py", f"n = {i}\n", f"more {i}")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert "Re-dispatch as `cumulative`" in result.stderr, result.stderr
        assert "Re-dispatch as `final`" not in result.stderr

    def test_a_committed_widening_with_no_span_falls_back_to_final(self, tmp_path):
        """Recommending a mode that would itself refuse at dispatch is the same
        class of defect. On the base branch `cumulative`'s merge-base IS HEAD,
        so its interval is empty; `final` is then the remaining full review and
        the message says it sees only the uncommitted part rather than claiming
        coverage it does not have.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        _commit_file(repo, "src/app.py", "x = 2  # fixed\n", "fix")
        for i in range(2 * 1 + 6):
            _commit_file(repo, f"src/new_{i}.py", f"n = {i}\n", f"more {i}")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert "Re-dispatch as `final`" in result.stderr, result.stderr
        # The reason, not just the mode: `final` is reached by three different
        # routes and only this one means "the span is empty".
        assert "HEAD's tree matches the merge-base's" in result.stderr
        assert "sees only the uncommitted part" in result.stderr

    def test_the_structured_fallback_mode_carries_both_answers(self, tmp_path):
        """`fallback_mode` is the structured half of the recommendation, and a
        key that is always the same string is indistinguishable from a constant
        — so both routes are asserted here, on the return value rather than on
        the English. That keeps the prose free to be reworded without the
        contract riding on it.
        """
        uncommitted = tmp_path / "u"
        _init_repo(uncommitted)
        self._seed_and_fix(uncommitted)
        for i in range(2 * 1 + 6):
            (uncommitted / f"src/new_{i}.py").write_text(f"n = {i}\n")
        result = cc.begin_review(uncommitted, "verify-resolutions")
        assert result["kind"] == "scope-widened"
        assert result["fallback_mode"] == "final"

        committed = tmp_path / "c"
        _init_repo(committed)
        self._seed_and_fix(committed)
        _git(committed, "checkout", "-q", "-b", "feature/demo")
        _commit_file(committed, "src/app.py", "x = 2  # fixed\n", "fix")
        for i in range(2 * 1 + 6):
            _commit_file(committed, f"src/new_{i}.py", f"n = {i}\n", f"more {i}")
        result = cc.begin_review(committed, "verify-resolutions")
        assert result["kind"] == "scope-widened"
        assert result["fallback_mode"] == "cumulative"
        # The prose and the structured field must not drift apart — the reader
        # acts on the message, the caller could act on the key.
        assert "`cumulative`" in result["reason"]

    def test_a_committed_widening_with_an_unresolvable_base_falls_back_to_final(
        self, tmp_path
    ):
        """Third route to `final`, and the one that rots quietly: a configured
        `base_branch:` that does not resolve fails closed upstream, so
        `cumulative` could not dispatch either. Same posture — recommend the
        mode that can run, and do not claim it covers the committed part.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        _git(repo, "checkout", "-q", "-b", "feature/demo")
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "base_branch: no-such-branch\n"
        )
        _commit_file(repo, "src/app.py", "x = 2  # fixed\n", "fix")
        for i in range(2 * 1 + 6):
            _commit_file(repo, f"src/new_{i}.py", f"n = {i}\n", f"more {i}")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert "Re-dispatch as `final`" in result.stderr, result.stderr
        assert "no merge-base resolves" in result.stderr
        assert "sees only the uncommitted part" in result.stderr


class TestResolutionDirectiveDelivery:
    """End-to-end: the directive reaches the reviewer at dispatch, on that one
    mode, and changes no exit code.

    The trigger is narrow on purpose. A directive that prints on every dispatch
    is one the reader learns to skip, and `verify-resolutions` is the only mode
    whose output can weaken a gate — the other three cannot carry `resolutions`
    at all (consolidate fails closed on a resolutions payload in any other
    mode).
    """

    def _seed_and_fix(self, repo: Path) -> str:
        """Prior review fact with a blocker at the initial commit's real tree,
        then an uncommitted fix — the state a verify-resolutions dispatch needs.
        """
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        (repo / ".prawduct").mkdir(exist_ok=True)
        _seed_prior_review_with_blocker(
            repo, head, head_tree=head_tree, head_commit=head
        )
        (repo / "src/app.py").write_text("x = 2  # fixed\n")
        return head

    def test_verify_resolutions_dispatch_delivers_it(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE in result.stdout

    def test_it_is_the_last_thing_in_the_dispatch_output(self, tmp_path):
        """Position is a deliverable, not a detail. This is a long tool result —
        manifest line, worktree line, record-lint block, marker line — and the
        reader acts on what it read last. Anything appended after this would
        push the one instruction in the message off the bottom.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert result.stdout.rstrip().endswith(
            cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE.rstrip()
        ), (
            "something now prints after the directive. Move it above, or move "
            "the directive back to last — the reader acts on the tail."
        )

    def test_the_severity_narrowing_rides_the_same_dispatch(self, tmp_path):
        """Both halves of the termination contract reach the same reader in the
        same tool result: what to rate, and what a resolution claims."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE in result.stdout

    def test_the_narrowing_precedes_the_resolution_directive(self, tmp_path):
        """Order tracks the reviewer's own sequence: it rates the delta, then
        judges the prior findings. The resolution warning stays last because it
        is the only one of the two whose subject can WEAKEN a gate, and the
        reader acts on the tail.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert result.stdout.index(cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE) < result.stdout.index(
            cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE
        ), (
            "the narrowing now prints after the resolution directive, which "
            "displaces the gate-weakening warning from the tail and states the "
            "severity rule after the severities were assigned."
        )

    @pytest.mark.parametrize("mode", ["chunk", "final", "cumulative"])
    def test_no_other_mode_delivers_the_narrowing(self, tmp_path, mode):
        """The narrowing is false in every other mode — those review work the
        builder CHOSE to do, and demoting their warnings would lose real
        review output rather than stop a self-inflicted round.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        if mode == "cumulative":
            _git(repo, "checkout", "-q", "-b", "feature/demo")
            _commit_file(repo, "src/feat.py", "z = 1\n", "feature work")
        else:
            (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", mode)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE not in result.stdout

    def test_a_demoted_dispatch_delivers_no_narrowing(self, tmp_path):
        """Exit 2 demotes to a full review (`final` on this fixture, whose
        widening is uncommitted), which rates every severity. Shipping the
        narrowing to that reviewer would silence warnings on a delta wide
        enough that the scope threshold just refused a partial review of it.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        for i in range(2 * 1 + 6):
            (repo / f"src/new_{i}.py").write_text(f"n = {i}\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE not in result.stdout

    @pytest.mark.parametrize("mode", ["chunk", "final", "cumulative"])
    def test_no_other_mode_delivers_it(self, tmp_path, mode):
        """These modes cannot record resolutions, so the advice is noise — and
        noise is what teaches a reader to skip the line that matters.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        if mode == "cumulative":
            # cumulative scopes a COMMITTED bundle against the merge base, so a
            # dirty tree on the base branch is an empty diff and it refuses to
            # dispatch at all — which would pass this assertion for the wrong
            # reason (no dispatch rather than no directive).
            _git(repo, "checkout", "-q", "-b", "feature/demo")
            _commit_file(repo, "src/feat.py", "z = 1\n", "feature work")
        else:
            (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", mode)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE not in result.stdout

    def test_a_refused_dispatch_delivers_nothing(self, tmp_path):
        """No prior review → exit 1 and the skill re-dispatches as chunk/final.
        Advice for a review that is not happening would be read as if it were.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir()
        (repo / "src/app.py").write_text("x = 2\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 1
        assert cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE not in result.stdout

    def test_a_widened_dispatch_delivers_nothing(self, tmp_path):
        """Exit 2 — the dispatch is demoted to `final`, which records no
        resolutions. Keyed off the manifest's mode rather than the `--mode`
        argument, so a demoted dispatch never reaches the print at all.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        for i in range(2 * 1 + 6):
            (repo / f"src/new_{i}.py").write_text(f"n = {i}\n")
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 2
        assert cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE not in result.stdout

    def test_the_dispatch_it_annotates_is_otherwise_unchanged(self, tmp_path):
        """Advice fails soft: it rides an existing report and alters nothing
        about it. Same exit code, same manifest, same marker as the dispatch
        tests above assert without it.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._seed_and_fix(repo)
        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["mode"] == VERIFY_MODE
        assert manifest["roster"] == ["reviewer"]
        ok, reason = cc.validate_manifest(manifest)
        assert ok, reason
        assert (repo / MARKER_REL).is_file()


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
        assert set(lint) == {
            "records", "chunk_graded", "plan_graded", "findings", "unchecked", "counts",
        }
        # Every check is present with an explicit tally, so a zero is visibly a
        # zero rather than a key a consumer has to interpret — and a check that
        # produced no answer is None, which a zero cannot be told apart from.
        assert set(lint["counts"]) == set(record_lint.CHECKS)


    def test_manifest_carries_a_prior_dispositions_block(self, tmp_path):
        """The wiring, not the pure function. Every other test of this feature
        exercises `dispositions.prior_dispositions` directly; this is the only
        path a REVIEWER ever sees, and the protocol text teaches them to read
        these exact keys."""
        _repo, manifest, _res = self._dispatch(tmp_path)
        priors = manifest["prior_dispositions"]
        assert set(priors) >= {"entries", "matched", "shown", "truncated"}
        # A repo with no dispositions yields an EMPTY block, not a missing key —
        # the protocol tells reviewers `unavailable` means the join failed, so
        # absence has to be distinguishable from failure.
        assert priors["entries"] == []
        assert priors["matched"] == 0
        assert "unavailable" not in priors

    def test_a_dispositioned_finding_in_scope_reaches_the_manifest(self, tmp_path):
        """End to end: a recorded ACCEPT on a finding citing a file this
        dispatch changes comes back on the manifest, through the real
        `begin_review` path."""
        from lib import dispositions as _d

        repo, manifest, _res = self._dispatch(tmp_path)
        changed = manifest["files_changed"][0]
        scope = "tactical-scope"
        evidence.append_fact(
            repo, "review", "rev-prior-1",
            {
                "base_tree": "a" * 40, "head_tree": "b" * 40, "mode": "final",
                "scope": scope,
                "findings": [{
                    "fid": "R-9", "severity": "warning", "goal": "Nothing Is Broken",
                    "title": "an answered question", "files": [changed],
                }],
            },
        )
        _d.record(repo, "rev-prior-1", "R-9", _d.ACCEPT, reason="by design")
        _abandon(repo)
        result = _run_begin(repo, "--mode", "chunk", "--scope", scope)
        assert result.returncode == 0, result.stderr
        priors = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())[
            "prior_dispositions"
        ]
        assert [e["fid"] for e in priors["entries"]] == ["R-9"]
        assert priors["entries"][0]["reason"] == "by design"

    def test_a_disposition_from_another_scope_does_not_reach_the_manifest(self, tmp_path):
        """The filter that keeps the block from becoming 91% of the manifest.
        Measured on a live dispatch before it existed: 92 entries, ~5,700
        tokens, 2.7x the protocol file the block exists to shorten — because a
        repo's hottest files are cited by nearly every finding it has ever
        recorded."""
        from lib import dispositions as _d

        repo, manifest, _res = self._dispatch(tmp_path)
        changed = manifest["files_changed"][0]
        evidence.append_fact(
            repo, "review", "rev-other-1",
            {
                "base_tree": "a" * 40, "head_tree": "b" * 40, "mode": "final",
                "scope": "some-unrelated-scope",
                "findings": [{
                    "fid": "R-9", "severity": "warning", "goal": "Nothing Is Broken",
                    "title": "answered for other work", "files": [changed],
                }],
            },
        )
        _d.record(repo, "rev-other-1", "R-9", _d.ACCEPT, reason="different work")
        _abandon(repo)
        result = _run_begin(repo, "--mode", "chunk", "--scope", "tactical-scope")
        assert result.returncode == 0, result.stderr
        priors = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())[
            "prior_dispositions"
        ]
        assert priors["entries"] == []

    def test_a_review_recorded_without_a_scope_matches_nothing(self, tmp_path):
        """The docstring makes this normative — "reviews recorded without a
        scope match nothing rather than everything" — because an unscoped fact
        cannot claim to be about this work, and an advisory block whose failure
        mode is drowning the review should fail toward carrying less."""
        from lib import dispositions as _d

        repo, manifest, _res = self._dispatch(tmp_path)
        changed = manifest["files_changed"][0]
        evidence.append_fact(
            repo, "review", "rev-unscoped-1",
            {
                "base_tree": "a" * 40, "head_tree": "b" * 40, "mode": "final",
                "scope": None,
                "findings": [{
                    "fid": "R-9", "severity": "warning", "goal": "Nothing Is Broken",
                    "title": "answered, but for unknown work", "files": [changed],
                }],
            },
        )
        _d.record(repo, "rev-unscoped-1", "R-9", _d.ACCEPT, reason="no scope recorded")
        store = evidence.read_facts(repo)
        assert _d.prior_dispositions(store, [changed], scope="tactical-scope")["entries"] == []
        # ...and the same fact IS carried when the caller asks unscoped, so this
        # is the scope axis filtering, not the file axis silently dropping it.
        assert _d.prior_dispositions(store, [changed], scope=None)["matched"] == 1

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


class TestScopeAttribution:
    """Which plan the RECORD says the review was of.

    An unbounded `active_build_plan` has attributed the manifest, the review
    fact and the ledger event to an unrelated plan — with the pointer correct
    every time, which is why nothing here repoints it.
    """

    def _repo_with_scoped_plan(self, tmp_path, branch: str) -> Path:
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "project_name: t\nactive_build_plan: artifacts/build-plan-other.md\n"
        )
        (artifacts / "build-plan-other.md").write_text(
            "---\nartifact: build-plan\nscope: other\n---\n\n# Plan\n\n"
            "## Status\n\n- [ ] Chunk 01: other\n\n"
            "### Chunk 01: other\n\n- **Deliverables:** `src/app.py`\n"
        )
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\n---\n\n# Plan\n\n"
            "## Status\n\n- [ ] Chunk 01: mine\n\n"
            "### Chunk 01: mine\n\n- **Deliverables:** `src/app.py`\n"
        )
        _commit_file(repo, ".prawduct/keep", "", "seed prawduct")
        _git(repo, "checkout", "-b", branch, "--quiet")
        (repo / "src/app.py").write_text("x = 2\n")
        return repo

    def test_scope_is_derived_from_the_branch_when_the_dispatch_omits_it(
        self, tmp_path
    ):
        """No `--scope`, and the record still names this branch's plan.

        Derived in code rather than left to the dispatching agent to read off
        the pointer — that read is where the misattribution enters.
        """
        repo = self._repo_with_scoped_plan(tmp_path, "fix/mine")
        result = _run_begin(repo, "--mode", "chunk", "--chunk", "01")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["scope"] == "mine"
        assert manifest["scope_chosen_by"] == "branch-name"
        assert manifest["record_lint"]["plan_graded"].endswith("build-plan-mine.md")

    def test_an_explicit_scope_still_wins(self, tmp_path):
        repo = self._repo_with_scoped_plan(tmp_path, "fix/mine")
        result = _run_begin(repo, "--mode", "chunk", "--chunk", "01", "--scope", "other")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["scope"] == "other"
        assert manifest["scope_chosen_by"] == "explicit-args"
        assert manifest["record_lint"]["plan_graded"].endswith("build-plan-other.md")

    def test_the_dispatch_line_names_the_subject_and_what_did_not_run(
        self, tmp_path
    ):
        """The dispatch output is what the reviewing agent reads before assessing
        anything, so it is where a null must not pass for a zero.

        `record-lint clean … checks run: <every check>` was the old line, printed
        whether or not each check ran — the report that vouched for work nobody
        did, which is the thing record-lint exists to refuse.
        """
        repo = self._repo_with_scoped_plan(tmp_path, "fix/mine")
        result = _run_begin(repo, "--mode", "chunk", "--chunk", "01")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "record-lint graded chunk 01 of" in result.stdout
        assert "build-plan-mine.md" in result.stdout
        assert "scope mine, branch-name" in result.stdout

    def test_a_dispatch_with_no_gradable_chunk_says_what_did_not_run(self, tmp_path):
        """A check with no subject is reported as not-run, not as a clean pass."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct" / "artifacts").mkdir(parents=True)
        (repo / ".prawduct" / "project-state.yaml").write_text("project_name: t\n")
        _commit_file(repo, ".prawduct/keep", "", "seed prawduct")
        (repo / ".prawduct" / "artifacts" / "notes.md").write_text("# Notes\n\nplain\n")
        # A judgeable file in the diff, or there is no dispatch to attribute:
        # an interval of `.prawduct/` prose alone is a free edge, and
        # `critic-begin` now declines it (exit 3) rather than spending a
        # reviewer the coverage gate never asked for. This test is about what
        # record-lint REPORTS on a real dispatch, so it needs one.
        (repo / "src" / "app.py").write_text("x = 2\n")

        result = _run_begin(repo, "--mode", "chunk")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "NOT run: chunk-ref-missing" in result.stdout, result.stdout
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["record_lint"]["counts"]["chunk-ref-missing"] is None

    def test_a_branch_matching_no_declared_scope_infers_nothing(self, tmp_path):
        """The inference can only ADD attribution, never redirect it.

        A branch name matching nothing leaves every caller on the behaviour it
        had before — which is the whole safety argument for reading a branch
        name at all.
        """
        repo = self._repo_with_scoped_plan(tmp_path, "fix/unrelated-name")
        result = _run_begin(repo, "--mode", "chunk", "--chunk", "01")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["scope"] is None
        assert manifest["scope_chosen_by"] == "not-resolved"
        assert manifest["record_lint"]["plan_graded"].endswith("build-plan-other.md")


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

    def test_the_observed_triplicate_now_groups(self):
        """The case the Jaccard bar missed. Three reviewers met ONE defect on
        one file and described it at three levels of detail; `[]` came back,
        and the builder dispositioned it three times.

        Jaccard divides by the union, so a terse title inside a verbose one
        scores low while sharing every word it has. Same files + overlap
        coefficient is the length-insensitive form of the same question.
        """
        files = ["plugin/lib/gates.py"]
        findings = [
            self._f("R-1", "Nothing Is Broken", "Gate remedy omits the batch instruction", files),
            self._f(
                "R-5",
                "The Design Is Sound",
                "The gate remedy omits the batch instruction that consolidate "
                "prints, so an agent reading stderr fixes one finding at a time",
                files,
            ),
            self._f(
                "R-11",
                "Everything Is Coherent",
                "Gate remedy text omits the batch instruction stated in "
                "building.md and in consolidate output",
                files,
            ),
        ]
        groups = cc.likely_duplicate_groups(findings)
        assert groups == [["R-1", "R-5", "R-11"]]
        assert cc.distinct_finding_count(findings, groups) == 1

    def test_containment_needs_identical_files_not_merely_overlapping(self):
        """The containment path is gated on the file sets MATCHING — the same
        two titles that group above must not group when the attributions
        differ. Two findings about one subsystem in different files are two
        findings, and a contained title is not evidence otherwise.

        These titles sit at Jaccard ~0.38, below the similarity bar, so only
        the containment path could group them: this isolates that path rather
        than re-testing the one that already existed.
        """
        findings = [
            self._f(
                "R-1", "Nothing Is Broken", "Gate remedy omits the batch instruction", ["a.py"]
            ),
            self._f(
                "R-2",
                "The Design Is Sound",
                "The gate remedy omits the batch instruction that consolidate "
                "prints, so an agent reading stderr fixes one finding at a time",
                ["a.py", "b.py"],
            ),
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_a_short_title_is_not_trivially_contained(self):
        """The degenerate case the containment rule invites: a one-word title
        is contained in ANY title sharing that word, at a coefficient of 1.0.
        Without a floor on the shorter title, every terse finding would join
        whichever neighbour happened to use the same noun — caught by this test
        before it shipped."""
        findings = [
            self._f("R-1", "Nothing Is Broken", "Ordering", ["x.py"]),
            self._f(
                "R-2",
                "The Design Is Sound",
                "Ordering between the precheck and the cache read is unpinned",
                ["x.py"],
            ),
        ]
        assert cc.likely_duplicate_groups(findings) == []

    def test_a_group_renders_as_one_defect_with_every_fid_named(self):
        """The count told the builder there were 2; the LIST is what gets
        worked, and three separately-worded lines read as three jobs. Every fid
        stays visible — this is presentation, never a merge, which is why a
        wrong group can cost clarity but never hide a finding."""
        files = ["plugin/lib/gates.py"]
        findings = [
            self._f("R-1", "Nothing Is Broken", "Gate remedy omits the batch instruction", files),
            self._f(
                "R-5",
                "The Design Is Sound",
                "The gate remedy omits the batch instruction that consolidate prints",
                files,
            ),
        ]
        # The SHORTEST title carries the LOWEST severity — the shape that made
        # a group containing a BLOCKING print as [NOTE], above an instruction to
        # dispose of the group once. Lead is chosen for wording; severity is the
        # group's maximum, and wording has nothing to do with severity.
        findings[0]["severity"] = "note"
        findings[1]["severity"] = "blocking"
        rendered = cc._render_duplicate_groups(findings, cc.likely_duplicate_groups(findings))
        assert "R-1+R-5" in rendered
        # The shortest title leads: it is the claim the reviewers agree on.
        assert "Gate remedy omits the batch instruction" in rendered
        assert "[BLOCKING]" in rendered and "[NOTE]" not in rendered
        assert "Nothing Is Broken" in rendered and "The Design Is Sound" in rendered

    def test_no_groups_renders_nothing(self):
        assert cc._render_duplicate_groups([], []) == ""

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


# ---------------------------------------------------------------------------
# A partial belongs to the review that dispatched it
# ---------------------------------------------------------------------------


class TestPartialBelongsToItsReview:
    """Part 1 of this defect stopped a dispatch DISPLACING a live review. It did
    not stop the displaced review's stragglers being consolidated as the new
    one: a partial was bound to the commit it reviewed and to nothing else, so
    at an unchanged HEAD it was schema-valid and commit-valid against any
    manifest. These pin both halves of the binding — the keyed filename, which
    makes contention unrepresentable, and the declared `dispatch_id`, which
    catches a reviewer handed the wrong id at a name that happens to be right.
    """

    _ABANDONED = "rev-20260101T000000Z-abandoned"

    def _pending_three_roster(self, repo: Path) -> str:
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _set_marker(repo)
        _write_manifest(repo, head)
        return head

    def test_a_straggler_from_another_review_does_not_complete_this_roster(self, tmp_path):
        # The live incident, inverted: an abandoned review's third reviewer
        # finally writes, at the same HEAD, into the current review's directory.
        # Before the binding it satisfied that roster and consolidated as a fact
        # attributed to a review that never read the files.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        (repo / PARTIALS_REL / f"sustainability.{self._ABANDONED}.json").write_text(
            json.dumps(_partial("sustainability", head, dispatch_id=self._ABANDONED))
        )

        result = _run_consolidate(repo)

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "no-op" in result.stdout
        assert "waiting on sustainability" in result.stdout
        assert _store_lines(repo) == [], "a straggler must not become a review fact"

    def test_the_straggler_is_named_as_another_reviews_and_not_as_silence(self, tmp_path):
        # Correctly ignoring it is only half the job. Bare silence about a file
        # sitting right there is what a caller reads as "the reviewer never
        # wrote anything" — the death verdict that produced the double dispatch.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        (repo / PARTIALS_REL / f"sustainability.{self._ABANDONED}.json").write_text(
            json.dumps(_partial("sustainability", head, dispatch_id=self._ABANDONED))
        )

        out = _run_consolidate(repo).stdout

        assert f"sustainability.{self._ABANDONED}.json" in out
        assert "belongs to an earlier review" in out
        assert "not evidence" in out.lower()
        # And the two REAL partials were counted. Without this the test passes
        # on a build where nothing keyed is found at all, which is the opposite
        # of what it claims to show.
        assert "2/3 partials present" in out

    def test_a_straggler_cannot_overwrite_this_reviews_partial(self, tmp_path):
        # The 2026-07-30 collision: two reviews contended for one filename and
        # the loser's only signal was a failed write, with nothing in the
        # protocol saying what that meant. A BLOCKING finding was discarded that
        # way. Keyed names make the two writes disjoint.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        _write_partial(repo, "sustainability", head, findings=[{
            "name": "real", "goal": "Nothing Is Broken", "severity": "blocking",
            "recommendation": "fix it"}])
        (repo / PARTIALS_REL / f"sustainability.{self._ABANDONED}.json").write_text(
            json.dumps(_partial("sustainability", head, dispatch_id=self._ABANDONED))
        )

        # Read back through `partial_path` — the subject. Composing the name
        # here would assert only that the fixture wrote what the fixture wrote,
        # and would stay green with the keying removed.
        mine = json.loads(
            cc.partial_path(repo / ".prawduct", "sustainability",
                            FAKE_REVIEW_ID).read_text())
        assert mine["findings"][0]["name"] == "real"
        assert mine["dispatch_id"] == FAKE_REVIEW_ID

    def test_a_wrong_dispatch_id_at_the_right_name_fails_closed(self, tmp_path):
        # The case the filename cannot catch: a reviewer handed the wrong review
        # id in its prompt writes to the path this review reads. Genuine
        # ambiguity about whose judgment this is — so it blocks, and names both.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        (repo / PARTIALS_REL / f"sustainability.{FAKE_REVIEW_ID}.json").write_text(
            json.dumps(_partial("sustainability", head, dispatch_id=self._ABANDONED))
        )

        result = _run_consolidate(repo)

        assert result.returncode == 1
        assert self._ABANDONED in result.stderr
        assert FAKE_REVIEW_ID in result.stderr
        assert _store_lines(repo) == []

    def test_a_whitespace_padded_dispatch_id_still_consolidates(self, tmp_path):
        # The other side of the same check, and the reason it strips first: a
        # fail-closed validator over a model-written field rejects genuine
        # ambiguity and tolerates the variant that normalizes identically.
        # `files: []` aborting a whole consolidation is the precedent, in this
        # same module — and its strictness was never pinned by a test, so both
        # sides of this one are.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        for role in ("correctness", "design"):
            _write_partial(repo, role, head)
        (repo / PARTIALS_REL / f"sustainability.{FAKE_REVIEW_ID}.json").write_text(
            json.dumps(_partial("sustainability", head,
                                dispatch_id=f"  {FAKE_REVIEW_ID}\n"))
        )

        result = _run_consolidate(repo)

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert len(_store_lines(repo)) == 1

    def test_a_missing_dispatch_id_fails_closed(self, tmp_path):
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        for role in ("correctness", "design"):
            _write_partial(repo, role, head)
        body = _partial("sustainability", head)
        del body["dispatch_id"]
        (repo / PARTIALS_REL / f"sustainability.{FAKE_REVIEW_ID}.json").write_text(
            json.dumps(body))

        result = _run_consolidate(repo)

        assert result.returncode == 1
        assert "dispatch_id" in result.stderr

    def test_a_partial_at_the_pre_keyed_path_is_named_with_its_remedy(self, tmp_path):
        # Version skew, and the one behaviour change an operator will hit: a
        # skill older than this hook writes `<role>.json`, does its whole run,
        # and is never read. Accepting it as a fallback would reopen the hole,
        # so the answer is to say so — a refusal that names no remedy is the
        # failure this subsystem has already paid for once.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        _write_partial(repo, "correctness", head)
        _write_partial(repo, "design", head)
        (repo / PARTIALS_REL / "sustainability.json").write_text(
            json.dumps(_partial("sustainability", head)))

        out = _run_consolidate(repo).stdout

        assert "sustainability.json" in out
        assert "older than this hook" in out
        assert "/reload-plugins" in out
        # The remedy must REACH the state, which is the whole criterion. This
        # note is appended to a message whose roster branch has just said "do
        # not re-dispatch", and a bare re-dispatch is refused while the marker
        # is live — so the abandon step and the override are both load-bearing,
        # and pinning only the reload leaves the half that makes it work
        # unasserted.
        assert "critic-end" in out
        assert "overrides the wait advice" in out
        assert _store_lines(repo) == []

    def test_a_manifest_without_a_rendezvous_is_refused_loudly(self, tmp_path):
        # The forward-incompatibility posture the data-model norm requires: a
        # manifest from an older hook is a loud block, never a silent skip.
        repo = tmp_path / "r"
        head = self._pending_three_roster(repo)
        manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
        del manifest["rendezvous"]
        (repo / PARTIALS_REL / "manifest.json").write_text(json.dumps(manifest))
        _full_roster_partials(repo, head)

        result = _run_consolidate(repo)

        assert result.returncode == 1
        assert "rendezvous" in result.stderr

    def test_a_review_id_that_is_not_a_filename_component_is_refused(self, tmp_path):
        # The id becomes a path segment. Refused by the validator rather than by
        # the path builder, so a malformed record yields a verdict the caller can
        # name instead of an exception on the session-end backstop's read.
        ok, reason = cc.validate_manifest(
            _manifest_dict("abc123", id="rev-../../escape"))
        assert not ok
        assert "filename component" in reason

    def test_the_partial_filename_shape_has_exactly_one_home(self, tmp_path):
        # The norm this design serves: if changing a fact requires editing N
        # places, N-1 are already wrong. The shape lives in `partial_path`; the
        # manifest carries the RESOLVED paths; no instruction surface spells a
        # partial filename. `manifest.json` is excluded — that one IS a fixed
        # path an agent must be able to find without being told.
        source = (ROOT / "lib" / "critic_consolidate.py").read_text()
        assert source.count('f"{role}.{review_id}.json"') == 1
        assert source.count('f"{role}.{review_id}.started"') == 1

        # Both suffixes `partial_path`/`started_path` own, not just `.json`:
        # `started_path` owns its shape on exactly the same terms, so a surface
        # reintroducing `.critic-partials/<role>.started` would pass a
        # json-only guard while breaking the identical invariant. No live
        # offender — this closes the axis rather than fixing a defect.
        pattern = re.compile(r'\.critic-partials/[A-Za-z<][^/ `")]*\.(?:json|started)')
        offenders = []
        for path in sorted((ROOT / "skills").rglob("*.md")) + \
                sorted((ROOT / "agents").rglob("*.md")) + \
                sorted((ROOT / "methodology").rglob("*.md")):
            for hit in pattern.findall(path.read_text()):
                if not hit.endswith("/manifest.json"):
                    offenders.append(f"{path.name}: {hit}")
        assert offenders == [], (
            "an instruction surface spells a partial filename — the shape must "
            f"come from the manifest's `rendezvous` entry: {offenders}"
        )
