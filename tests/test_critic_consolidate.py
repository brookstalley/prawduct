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

    def test_blocking_names_one_commit_and_one_verify_pass(self):
        line = cc.next_action_line("rev-1", 2, 5, 3)
        assert "2 BLOCKING" in line
        assert "ONE commit" in line
        assert "ONE `/prawduct:critic verify-resolutions`" in line
        # The non-blocking findings are decided in the SAME pass — deferring
        # them to a later round is the pump this field exists to stop.
        assert "SAME pass" in line

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
    """`NEXT:` is code-owned and relay-only — the design that made this
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
        # `NEXT` is already framework-wide: the turn-closing standing block
        # (session digest, building.md, reflection.md) defines it as "the ONE
        # next action" — one line. This line is a paragraph that must be
        # relayed verbatim, so an agent holding both contracts would have a
        # standing instruction to compress the very text it was told to copy.
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

    def _prawduct_with_started(self, tmp_path, roles_minutes: dict) -> Path:
        """A .prawduct dir whose partials dir holds a ``<role>.started`` marker
        per entry, backdated by the given minutes via mtime."""
        import os
        prawduct = tmp_path / ".prawduct"
        cc.partials_dir(prawduct).mkdir(parents=True)
        now = datetime.now(timezone.utc).timestamp()
        for role, minutes in roles_minutes.items():
            marker = cc.started_path(prawduct, role)
            marker.write_text(role)
            os.utime(marker, (now - minutes * 60, now - minutes * 60))
        return prawduct

    def test_started_marker_annotates_the_missing_role(self, tmp_path):
        prawduct = self._prawduct_with_started(tmp_path, {"design": 3.0})
        msg = cc._incomplete_noop_message(
            ["design", "sustainability"], 1, 3, self._fresh_id(4), prawduct)
        assert re.search(r"design \(started 3\.\d min ago\)", msg)
        # No marker → bare role name, no started claim.
        assert "sustainability (started" not in msg

    def test_fresh_started_marker_holds_wait_past_dispatch_grace(self, tmp_path):
        # The observed field failure: reviewers (re)started late, so dispatch
        # age blew past the grace window while every reviewer was demonstrably
        # at work. A fresh started marker must keep the verdict on the wait
        # side — dispatch age alone no longer declares death.
        prawduct = self._prawduct_with_started(
            tmp_path, {"correctness": 2.0, "design": 2.0})
        msg = cc._incomplete_noop_message(
            ["correctness", "design"], 1, 3, self._fresh_id(45), prawduct)
        assert "may have died" not in msg
        assert "NOT evidence the reviewers died" in msg

    def test_stale_started_markers_advise_critic_end(self, tmp_path):
        # A reviewer that started long ago and never wrote its partial is the
        # genuine-death case — the marker's own age carries the verdict.
        prawduct = self._prawduct_with_started(tmp_path, {"design": 40.0})
        msg = cc._incomplete_noop_message(
            ["design"], 2, 3, self._fresh_id(45), prawduct)
        assert "may have died" in msg
        assert "critic-end" in msg

    def test_one_fresh_role_holds_the_whole_verdict_on_wait(self, tmp_path):
        # Mixed state: one missing role has a fresh marker, the other none at a
        # stale dispatch. Death advice requires EVERY missing role past grace
        # on its own effective age — a live reviewer will report and shrink
        # `missing`, after which the dead one's age decides alone.
        prawduct = self._prawduct_with_started(tmp_path, {"correctness": 1.0})
        msg = cc._incomplete_noop_message(
            ["correctness", "design"], 1, 3, self._fresh_id(45), prawduct)
        assert "may have died" not in msg

    def test_single_pass_roster_ignores_started_markers(self, tmp_path):
        # The single-pass reviewer IS the dispatching fork — there is no
        # waiting caller mid-review, so the coordinator liveness story (and its
        # markers) must not leak into that message.
        prawduct = self._prawduct_with_started(tmp_path, {"reviewer": 2.0})
        msg = cc._incomplete_noop_message(
            ["reviewer"], 0, 1, self._fresh_id(2), prawduct)
        assert "(started" not in msg
        assert "consolidates when it finishes" in msg

    def test_dispatch_surfaces_instruct_the_started_marker(self):
        # The marker is written by the model, so the instruction lives in
        # prose — bind BOTH dispatch surfaces (the agent definition every
        # dispatched reviewer loads, and the coordinator's prompt template) to
        # the filename convention started_path() reads, or the signal silently
        # stops being written while the reader keeps trusting its absence.
        convention = cc.started_path(Path("x"), "<role>").name  # "<role>.started"
        assert convention == "<role>.started"
        agent_doc = (ROOT / "agents" / "critic-reviewer.md").read_text()
        protocol = (ROOT / "skills" / "critic" / "review-protocol.md").read_text()
        assert "`.prawduct/.critic-partials/<role>.started`" in agent_doc
        assert "FIRST" in agent_doc
        assert ".critic-partials/<ROLE>.started" in protocol


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
        # ("everything under `.prawduct/` — change-log, backlog, project-state,
        # build plans, regen-views output"). Pin the concrete files those words
        # denote; the token scan above cannot see them.
        from lib import coverage_algebra

        for path in (
            ".prawduct/backlog.md",
            ".prawduct/project-state.yaml",
            ".prawduct/artifacts/build-plan-demo.md",
            ".prawduct/release-notes.md",   # regen-views output
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
        cc.started_path(prawduct, "correctness").write_text("correctness")
        cc.remove_partials(prawduct)
        assert not pdir.exists()


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
