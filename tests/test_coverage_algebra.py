"""Tests for the coverage algebra (kernel-evidence-store ch.02).

Pure-function coverage: facts and a diff table in, verdict out — no git, no
I/O. The load-bearing cases are the plan's acceptance bar:

* **CRT-J4PM dissolved** — a composition of chunk reviews + a cumulative +
  a later ``final`` passes the base→HEAD question with NO label consulted
  and no re-run.
* **CRT-5D8Q dissolved** — the metadata/doc-only boundary questions get one
  answer from one predicate (``is_judgeable_path``), pinned pair by pair.
* **Stricter-never-looser** — partial edges, rebase gaps, malformed bodies,
  unknown dispositions, and diff failures all weaken coverage; nothing
  strengthens it except a valid fact, a valid resolution, or a genuinely
  non-judgeable interval.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage_algebra as ca  # noqa: E402


def _tree(name: str) -> str:
    """A realistic full-length tree id for a symbolic fixture name.

    Production tree ids are 40-hex git object ids and the algebra rejects
    anything else, so a corrupted or hand-edited fact cannot compose. Fixtures
    therefore have to carry the real shape; deriving each id from its readable
    name keeps them stable, distinct, and greppable back to the label.
    """
    return hashlib.sha1(name.encode()).hexdigest()


T0, T1, T2, T3, T11 = (_tree(n) for n in ("t0", "t1", "t2", "t3", "t11"))
T_REVIEWED = _tree("t-reviewed")
T_DEAD = _tree("t-dead")


def _diff(table: dict):
    """A diff_fn backed by a table; unknown pairs -> None (can't compute)."""
    return lambda a, b: table.get((a, b))


def _review(
    rid: str,
    src: str,
    dst: str,
    changed: list[str],
    reviewed: "list[str] | None" = None,
    findings: "list[dict] | None" = None,
    mode: str = "chunk",
) -> dict:
    body = {
        "base_tree": src,
        "head_tree": dst,
        "files_changed": changed,
        "files_reviewed": changed if reviewed is None else reviewed,
        "mode": mode,
        "findings": findings or [],
    }
    return {"schema": 1, "kind": "review", "id": rid, "ts": "t", "body": body}


def _resolution(rid: str, review_id: str, fid: str, disposition: str = "fixed") -> dict:
    return {
        "schema": 1,
        "kind": "resolution",
        "id": rid,
        "ts": "t",
        "body": {
            "finding": {"review_id": review_id, "fid": fid},
            "disposition": disposition,
        },
    }


BLOCKER = {"fid": "F-1", "severity": "BLOCKING", "title": "broken thing"}


# ---------------------------------------------------------------------------
# The one judgeability predicate (CRT-5D8Q)
# ---------------------------------------------------------------------------


class TestJudgeablePath:
    """One answer per path class — the boundary v2.3.3 drew three ways."""

    JUDGEABLE = [
        "lib/gates.py",
        "bin/prawduct-hook",
        "src/app.ts",
        "config.json",
        "skills/critic/SKILL.md",  # governance-protected .md IS behavior
        "methodology/building.md",
        "templates/build-plan.md",
        "CLAUDE.md",
    ]
    NON_JUDGEABLE = [
        ".prawduct/backlog.md",  # metadata — the CRT-5D8Q boundary, one way
        ".prawduct/artifacts/build-plan-x.md",
        ".prawduct/.critic-findings.json",
        ".claude/settings.json",
        "docs/notes.md",  # unprotected prose — the doc-only allowance
        "README.md",
    ]

    def test_judgeable(self):
        for path in self.JUDGEABLE:
            assert ca.is_judgeable_path(path), path

    def test_non_judgeable(self):
        for path in self.NON_JUDGEABLE:
            assert not ca.is_judgeable_path(path), path

    def test_judgeable_files_filter(self):
        mixed = ["lib/a.py", "docs/a.md", ".prawduct/x", "CLAUDE.md"]
        assert ca.judgeable_files(mixed) == ["lib/a.py", "CLAUDE.md"]
        assert ca.judgeable_files(None) == []


# ---------------------------------------------------------------------------
# Composition verdicts
# ---------------------------------------------------------------------------


class TestCoverageVerdict:
    def test_identical_trees_trivially_covered(self):
        verdict = ca.coverage_verdict([], T0, T0, _diff({}))
        assert verdict["status"] == "covered"
        assert verdict["path"] == []

    def test_direct_span(self):
        facts = [_review("r1", T0, T1, ["lib/a.py"])]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "covered"
        assert [s["id"] for s in verdict["path"]] == ["r1"]

    def test_two_fact_chain(self):
        facts = [
            _review("r1", T0, T1, ["lib/a.py"]),
            _review("r2", T1, T2, ["lib/b.py"]),
        ]
        verdict = ca.coverage_verdict(facts, T0, T2, _diff({}))
        assert verdict["status"] == "covered"
        assert [s["id"] for s in verdict["path"]] == ["r1", "r2"]

    def test_doc_only_free_edge_tail(self):
        facts = [_review("r1", T0, T1, ["lib/a.py"])]
        table = {(T1, T2): ["docs/readme.md"]}
        verdict = ca.coverage_verdict(facts, T0, T2, _diff(table))
        assert verdict["status"] == "covered"
        kinds = [s["kind"] for s in verdict["path"]]
        assert kinds == ["review", "free"]

    def test_whole_span_doc_only_needs_no_facts(self):
        table = {(T0, T1): ["docs/a.md", "README.md"]}
        verdict = ca.coverage_verdict([], T0, T1, _diff(table))
        assert verdict["status"] == "covered"

    def test_partial_edge_does_not_compose(self):
        # The review saw less than its own diff — a judgeable file escaped.
        facts = [
            _review("r1", T0, T1, ["lib/a.py", "lib/b.py"], reviewed=["lib/a.py"])
        ]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "uncovered"

    def test_unreviewed_non_judgeable_file_does_not_invalidate(self):
        facts = [
            _review(
                "r1", T0, T1, ["lib/a.py", "docs/x.md"], reviewed=["lib/a.py"]
            )
        ]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "covered"

    def test_rebase_gap_does_not_compose(self):
        # Review covered t1->t2, but a rebase moved the base: nothing spans
        # t0->t1 and the interval carries judgeable changes.
        facts = [_review("r1", T1, T2, ["lib/a.py"])]
        table = {(T0, T1): ["lib/other.py"]}
        verdict = ca.coverage_verdict(facts, T0, T2, _diff(table))
        assert verdict["status"] == "uncovered"
        assert "no evidence path" in verdict["reason"]

    def test_squash_merge_tree_identity_composes(self):
        # A squash commit carries the SAME tree the review saw — coverage
        # holds with no knowledge of the new commit SHA.
        facts = [_review("r1", T0, T_REVIEWED, ["lib/a.py"])]
        verdict = ca.coverage_verdict(facts, T0, T_REVIEWED, _diff({}))
        assert verdict["status"] == "covered"

    def test_diff_failure_is_never_a_free_edge(self):
        verdict = ca.coverage_verdict([], T0, T1, _diff({}))  # all None
        assert verdict["status"] == "uncovered"

    def test_malformed_fact_body_yields_no_edge(self):
        facts = [
            {"schema": 1, "kind": "review", "id": "r-bad", "body": {"head_tree": T1}},
            {"schema": 1, "kind": "review", "id": "r-bad2", "body": None},
        ]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "uncovered"

    def test_malformed_tree_id_yields_no_edge(self):
        # The store is a plain file every worktree of the clone shares, so a
        # corrupted or hand-edited fact can put any string where a tree id
        # belongs. It must weaken coverage like any other malformedness --
        # never compose, and never reach git argv as an option-shaped token.
        for bad in ("--upload-pack=evil", "t0", "", "Z" * 40, T1[:39], T1 + "\n"):
            facts = [_review("r1", T0, bad, ["lib/a.py"]), _review("r2", bad, T1, [])]
            verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
            assert verdict["status"] == "uncovered", f"{bad!r} composed an edge"

    def test_uppercase_hex_is_not_a_tree_id(self):
        # git emits lowercase; accepting both would let one tree carry two
        # spellings and silently split its coverage into two nodes.
        facts = [_review("r1", T0, T1.upper(), ["lib/a.py"])]
        assert ca.coverage_verdict(facts, T0, T1.upper(), _diff({}))["status"] == "uncovered"

    def test_sha256_tree_ids_compose(self):
        # 64-hex is the other real width; the repo is SHA-1 today and this is
        # what keeps that from being baked in. A guard against the gate being
        # too STRICT, so it passes pre-fix too — green here is not evidence
        # the shape check works, only that it did not overreach.
        src, dst = hashlib.sha256(b"a").hexdigest(), hashlib.sha256(b"b").hexdigest()
        facts = [_review("r1", src, dst, ["lib/a.py"])]
        assert ca.coverage_verdict(facts, src, dst, _diff({}))["status"] == "covered"

    def test_mode_label_is_never_consulted(self):
        # A 'chunk'-labeled fact satisfies a span a v2 PR gate would have
        # rejected by label — composition only reads trees and files.
        facts = [_review("r1", T0, T1, ["lib/a.py"], mode="chunk")]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "covered"


def _trees(contents: "dict[str, dict[str, str]]"):
    """A ``(diff_fn, key_fn)`` pair over ONE ``tree -> {path: blob}`` table,
    so both free-edge oracles answer from identical ground truth and any
    disagreement is the implementation's, not the fixture's. A tree absent
    from the table is unreadable: ``diff_fn`` -> None, ``key_fn`` -> None."""

    def diff_fn(a, b):
        ta, tb = contents.get(a), contents.get(b)
        if ta is None or tb is None:
            return None
        return sorted(p for p in set(ta) | set(tb) if ta.get(p) != tb.get(p))

    def key_fn(t):
        tree = contents.get(t)
        if tree is None:
            return None
        return repr(
            sorted((p, b) for p, b in tree.items() if ca.is_judgeable_path(p))
        )

    return diff_fn, key_fn


# Each case: (label, facts, base, target, tree contents, expected status)
_ORACLE_CASES = [
    (
        "whole span doc-only",
        [],
        T0,
        T1,
        {T0: {"lib/a.py": "x", "docs/r.md": "1"},
         T1: {"lib/a.py": "x", "docs/r.md": "2"}},
        "covered",
    ),
    (
        "review then doc-only tail",
        [_review("r1", T0, T1, ["lib/a.py"])],
        T0,
        T2,
        {T0: {"lib/a.py": "x"},
         T1: {"lib/a.py": "y"},
         T2: {"lib/a.py": "y", "docs/r.md": "1"}},
        "covered",
    ),
    (
        "judgeable difference is never free",
        [],
        T0,
        T1,
        {T0: {"lib/a.py": "x"}, T1: {"lib/a.py": "y"}},
        "uncovered",
    ),
    (
        "rebase gap does not compose",
        [_review("r1", T1, T2, ["lib/a.py"])],
        T0,
        T2,
        {T0: {"lib/o.py": "x"},
         T1: {"lib/o.py": "y"},
         T2: {"lib/o.py": "y", "lib/a.py": "z"}},
        "uncovered",
    ),
    (
        "protected skill prose is judgeable, so not free",
        [],
        T0,
        T1,
        {T0: {"plugin/skills/critic/SKILL.md": "1"},
         T1: {"plugin/skills/critic/SKILL.md": "2"}},
        "uncovered",
    ),
]


class TestFreeEdgeOracleEquivalence:
    """The key-derived oracle is the linear form of the pairwise probe: it
    must decide every case identically, or it is a different gate wearing the
    same name. Pairwise stays as the reference implementation."""

    def test_oracles_agree_on_status_and_path(self):
        for label, facts, base, target, contents, expected in _ORACLE_CASES:
            diff_fn, key_fn = _trees(contents)
            pairwise = ca.coverage_verdict(facts, base, target, diff_fn)
            keyed = ca.coverage_verdict(facts, base, target, diff_fn, key_fn)
            assert pairwise["status"] == expected, label
            assert keyed["status"] == pairwise["status"], label
            assert [s["kind"] for s in keyed.get("path", [])] == [
                s["kind"] for s in pairwise.get("path", [])
            ], label

    def test_unreadable_tree_grants_no_free_edge(self):
        # t1 is absent from the table: ls-tree would have failed. The keyed
        # form must refuse the free edge exactly as a failed diff does —
        # speed may never buy a free pass (authority fails closed).
        diff_fn, key_fn = _trees({T0: {"docs/r.md": "1"}})
        verdict = ca.coverage_verdict([], T0, T1, diff_fn, key_fn)
        assert verdict["status"] == "uncovered"

    def test_keyed_free_step_still_carries_files(self):
        # Attribution is deferred, not dropped: a free step on the RETURNED
        # path reports its files even though the key never listed them.
        contents = {
            T0: {"lib/a.py": "x"},
            T1: {"lib/a.py": "x", "docs/r.md": "1"},
        }
        diff_fn, key_fn = _trees(contents)
        verdict = ca.coverage_verdict([], T0, T1, diff_fn, key_fn)
        assert verdict["status"] == "covered"
        free = [s for s in verdict["path"] if s["kind"] == "free"]
        assert free and free[0]["files"] == ["docs/r.md"]

    def test_key_classes_are_transitive(self):
        # Three trees agreeing on judgeable content form one clique, so the
        # span composes without any fact and without probing every pair.
        contents = {
            T0: {"lib/a.py": "x", "docs/r.md": "1"},
            T1: {"lib/a.py": "x", "docs/r.md": "2"},
            T2: {"lib/a.py": "x", "docs/r.md": "3"},
        }
        diff_fn, key_fn = _trees(contents)
        facts = [_review("r1", T1, T2, ["docs/r.md"])]  # puts t1/t2 in nodes
        verdict = ca.coverage_verdict(facts, T0, T2, diff_fn, key_fn)
        assert verdict["status"] == "covered"

    def test_key_form_issues_one_call_per_tree(self):
        # The defect this replaced was the CALL COUNT, so pin it: keys are
        # per tree, never per pair.
        contents = {_tree(f"t{i}"): {"docs/r.md": str(i)} for i in range(12)}
        facts = [
            _review(f"r{i}", _tree(f"t{i}"), _tree(f"t{i + 1}"), ["docs/r.md"])
            for i in range(11)
        ]
        diff_fn, key_fn = _trees(contents)
        calls = []

        def counting_key_fn(t):
            calls.append(t)
            return key_fn(t)

        ca.coverage_verdict(facts, T0, T11, diff_fn, counting_key_fn)
        assert len(calls) == len(set(calls)) <= len(contents)


class TestBlockingAndResolutions:
    def test_unresolved_blocker_blocks_with_attribution(self):
        facts = [_review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER])]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "blocked"
        assert verdict["unresolved"] == [
            {
                "review_id": "r1",
                "fid": "F-1",
                "severity": "BLOCKING",
                "title": "broken thing",
                # Reachable: r1 is the only review on the path, so it is exactly
                # what a verify-resolutions pass anchors to.
                "superseded": False,
            }
        ]

    def test_blocker_on_an_earlier_round_is_marked_superseded(self):
        """A verify-resolutions pass anchors to the most recent review on the
        path, so a blocker any earlier fact still carries is one no verify pass
        will name again. Marked so gate messages can offer the spanning review
        instead of a route the operator cannot take."""
        facts = [
            _review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
            _review("r2", T1, T2, ["lib/b.py"]),  # newer, clean — the verify anchor
        ]
        verdict = ca.coverage_verdict(facts, T0, T2, _diff({}))
        assert verdict["status"] == "blocked"
        assert [(e["review_id"], e["superseded"]) for e in verdict["unresolved"]] == [
            ("r1", True)
        ]

    def test_the_anchor_is_the_newest_fact_not_the_last_path_step(self):
        """Store order decides, because that is what the dispatcher's anchor
        follows — appended last is newest. Here the newest fact covers the
        EARLIER interval, so a path-position reading would mark the wrong one."""
        facts = [
            _review("r-late-interval", T1, T2, ["lib/b.py"], findings=[BLOCKER]),
            _review("r-appended-last", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
        ]
        verdict = ca.coverage_verdict(facts, T0, T2, _diff({}))
        assert verdict["status"] == "blocked"
        marked = {e["review_id"]: e["superseded"] for e in verdict["unresolved"]}
        assert marked == {"r-late-interval": True, "r-appended-last": False}

    def test_resolution_fact_unblocks_without_rerun(self):
        facts = [
            _review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
            _resolution("s1", "r1", "F-1"),
        ]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "covered"

    def test_waived_disposition_also_resolves(self):
        facts = [
            _review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
            _resolution("s1", "r1", "F-1", disposition="waived"),
        ]
        assert ca.coverage_verdict(facts, T0, T1, _diff({}))["status"] == "covered"

    def test_unknown_disposition_resolves_nothing(self):
        facts = [
            _review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
            _resolution("s1", "r1", "F-1", disposition="ignored"),
        ]
        assert ca.coverage_verdict(facts, T0, T1, _diff({}))["status"] == "blocked"

    def test_resolution_for_other_review_does_not_leak(self):
        facts = [
            _review("r1", T0, T1, ["lib/a.py"], findings=[BLOCKER]),
            _resolution("s1", "r-other", "F-1"),
        ]
        assert ca.coverage_verdict(facts, T0, T1, _diff({}))["status"] == "blocked"

    def test_blocker_off_path_does_not_haunt(self):
        # An abandoned state's blocked review is not on the composing path.
        facts = [
            _review("r-dead", T0, T_DEAD, ["lib/x.py"], findings=[BLOCKER]),
            _review("r1", T0, T1, ["lib/a.py"]),
        ]
        verdict = ca.coverage_verdict(facts, T0, T1, _diff({}))
        assert verdict["status"] == "covered"

    def test_warning_and_note_severities_never_block(self):
        findings = [
            {"fid": "F-2", "severity": "WARNING", "title": "w"},
            {"fid": "F-3", "severity": "note", "title": "n"},
        ]
        facts = [_review("r1", T0, T1, ["lib/a.py"], findings=findings)]
        assert ca.coverage_verdict(facts, T0, T1, _diff({}))["status"] == "covered"

    def test_malformed_findings_entries_do_not_wedge_the_gate(self):
        facts = [
            _review(
                "r1", T0, T1, ["lib/a.py"], findings=["garbage", {"severity": 3}]
            )
        ]
        assert ca.coverage_verdict(facts, T0, T1, _diff({}))["status"] == "covered"


class TestReproScenarios:
    def test_crt_j4pm_no_rerun_after_label_mismatch(self):
        """The v2.3.3 deadlock: chunk reviews + a cumulative + a post-fix
        'final' — the v2 PR gate rejected the final BY LABEL and demanded a
        fourth identical run. Composition passes it: base→HEAD spans via
        cumulative (t0→t2) + final (t2→t3), labels never read."""
        facts = [
            _review("chunk-a", T0, T1, ["lib/a.py"], mode="chunk"),
            _review("chunk-b", T1, T2, ["lib/b.py"], mode="chunk"),
            _review("cumulative", T0, T2, ["lib/a.py", "lib/b.py"], mode="cumulative"),
            _review("final-after-fix", T2, T3, ["lib/a.py"], mode="final"),
        ]
        verdict = ca.coverage_verdict(facts, T0, T3, _diff({}))
        assert verdict["status"] == "covered"
        ids = [s["id"] for s in verdict["path"]]
        assert ids in (
            ["cumulative", "final-after-fix"],
            ["chunk-a", "chunk-b", "final-after-fix"],
        )

    def test_crt_5d8q_one_boundary_no_deadlock(self):
        """The v2.3.3 deadlock was two helpers disagreeing on whether
        .prawduct/ metadata needed coverage. Here both questions — 'does this
        interval need review?' and 'is this file in scope?' — go through
        is_judgeable_path, so a metadata-only tail is free BY THE SAME RULE
        that excludes metadata from edge validity."""
        facts = [
            _review(
                "r1",
                T0,
                T1,
                ["lib/a.py", ".prawduct/backlog.md"],
                reviewed=["lib/a.py"],  # metadata unreviewed — still valid
            )
        ]
        table = {(T1, T2): [".prawduct/artifacts/build-plan-x.md"]}
        verdict = ca.coverage_verdict(facts, T0, T2, _diff(table))
        assert verdict["status"] == "covered"
