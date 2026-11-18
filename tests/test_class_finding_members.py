"""A class finding carries its members as data, and a `fixed` claim answers each (#847).

The incident: a reviewer rated a finding `class` and listed its members in
prose; the builder fixed the member the finding led with and claimed `fixed`;
`verify-resolutions` graded the FINDING, and the next round found the members
nobody touched. Three rounds where one would do, with the rule quoted back
correctly the whole time.

- D1: a finding may carry `scope`, `closure` and `members`. They round-trip into
  the review fact; a malformed member is dropped with a warning, never refused.
- D2: a `fixed` resolution of a finding with recorded members is appended only
  when its own `members` answers every id. Otherwise NO resolution fact is
  appended (the fail-closed state omission already has), the finding keeps
  blocking, and NEXT-ACTION names the missing ids. A finding without members
  resolves as it always did.
- D3: the verify dispatch's roll-call hands the verifier each carried finding's
  closure and members, and names a class with no members as unbounded.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib import coverage_algebra
from lib import critic_consolidate as cc
from test_critic_consolidate import (
    VERIFY_MODE,
    _commit_file,
    _full_roster_partials,
    _init_repo,
    _partial,
    _partial_file,
    _run_consolidate,
    _run_validate_partial,
    _set_marker,
    _store_facts,
    _write_manifest,
    _write_partial,
)

MEMBERS = [
    {"id": "m1", "site": "plugin/lib/a.py::alpha"},
    {"id": "m2", "site": "plugin/lib/b.py::beta", "note": "the second writer"},
    {"id": "m3", "site": "plugin/lib/c.py::gamma"},
]
CLASS_FINDING = {
    "name": "Three writers skip the guard",
    "goal": "Nothing Is Broken",
    "severity": "blocking",
    "recommendation": "Class: every writer of the record skips the guard.",
    "files": ["plugin/lib/a.py"],
    "scope": "class",
    "closure": "every function that writes the record without calling guard()",
    "members": MEMBERS,
}
PLAIN_FINDING = {
    "name": "Broken invariant",
    "goal": "Nothing Is Broken",
    "severity": "blocking",
    "recommendation": "Fix it",
    "files": ["src/app.py"],
}
PRIOR_ID = "rev-prior-0001"


# ---------------------------------------------------------------------------
# D1 — the partial schema carries scope, closure and members
# ---------------------------------------------------------------------------


class TestOldShapeIsUnchanged:
    """An old-shape partial validates and merges to exactly the entry it always
    did: no new key appears, absent or null."""

    def test_the_merged_entry_is_byte_identical(self):
        partial = _partial("correctness", "abc123", findings=[PLAIN_FINDING])
        ok, reason = cc.validate_partial(partial)
        assert ok, reason
        merged = cc.merge_findings([partial])
        assert json.dumps(merged, sort_keys=True) == json.dumps([{
            "fid": "R-1", "goal": "Nothing Is Broken", "severity": "blocking",
            "title": "Broken invariant", "recommendation": "Fix it",
            "files": ["src/app.py"],
        }], sort_keys=True)

    def test_the_cache_entry_gains_no_key(self):
        fact = {"id": "rev-x", "body": {"findings": cc.merge_findings(
            [_partial("correctness", "abc123", findings=[PLAIN_FINDING])]
        ), "counts": {"blocking": 1}}}
        entry = cc.fact_to_cache_record(fact, store={"facts": []})["findings"][0]
        assert set(entry) == {"fid", "goal", "severity", "summary", "recommendation",
                              "files", "fix_cost"}


class TestTheFieldsRoundTrip:
    def test_merge_findings_persists_scope_closure_and_members(self):
        partial = _partial("correctness", "abc123", findings=[CLASS_FINDING])
        ok, reason = cc.validate_partial(partial)
        assert ok, reason
        entry = cc.merge_findings([partial])[0]
        assert entry["scope"] == "class"
        assert entry["closure"] == CLASS_FINDING["closure"]
        assert entry["members"] == MEMBERS

    def test_the_review_fact_and_the_cache_carry_them(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _seed(repo, head, CLASS_FINDING)
        finding = _store_facts(repo, "review")[0]["body"]["findings"][0]
        assert (finding["scope"], finding["closure"], finding["members"]) == (
            "class", CLASS_FINDING["closure"], MEMBERS)
        cache = json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())
        assert cache["findings"][0]["members"] == MEMBERS
        assert cache["findings"][0]["closure"] == CLASS_FINDING["closure"]

    def test_a_malformed_member_is_dropped_not_refused(self, capsys):
        bad = dict(CLASS_FINDING, members=[
            {"id": "m1", "site": "a.py"},
            {"id": "", "site": "b.py"},          # blank id
            "c.py",                               # not an object
            {"id": "m1", "site": "dup.py"},      # duplicate id
            {"id": "m4"},                         # no site
            {"id": "m5", "site": "e.py", "note": 7},  # bad note: dropped, member kept
        ], scope="Class", closure="  ")
        partial = _partial("correctness", "abc123", findings=[bad])
        ok, reason = cc.validate_partial(partial)
        assert ok, reason
        entry = cc.merge_findings([partial])[0]
        assert entry["members"] == [{"id": "m1", "site": "a.py"}, {"id": "m5", "site": "e.py"}]
        assert entry["scope"] == "class"  # case is the natural encoding variant
        assert "closure" not in entry
        err = capsys.readouterr().err
        assert "member" in err and "dropped" in err
        assert "m4" in err

    def test_validate_partial_passes_and_warns_the_reviewer(self, tmp_path):
        """At the CLI the reviewer runs before it returns: the partial passes
        (a malformed member never refuses), and the drop is said to the one
        reader who can still rewrite the field. A clean partial says nothing."""
        repo = tmp_path / "r"
        _init_repo(repo)
        head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
        _write_manifest(repo, head)
        bad = dict(CLASS_FINDING, members=[{"id": "m1", "site": "a.py"}, {"id": "m2"}])
        _write_partial(repo, "correctness", head, findings=[bad])
        result = _run_validate_partial(repo, _partial_file(repo, "correctness"))
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"
        assert "warning" in result.stderr and "member[1]" in result.stderr
        _write_partial(repo, "correctness", head, findings=[CLASS_FINDING])
        clean = _run_validate_partial(repo, _partial_file(repo, "correctness"))
        assert (clean.returncode, clean.stderr) == (0, "")

    def test_a_non_list_members_and_unknown_scope_are_dropped(self, capsys):
        bad = dict(CLASS_FINDING, members="m1, m2", scope="unbounded")
        partial = _partial("correctness", "abc123", findings=[bad])
        assert cc.validate_partial(partial)[0]
        entry = cc.merge_findings([partial])[0]
        assert "members" not in entry and "scope" not in entry
        assert "unbounded" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# D2 — a `fixed` resolution answers every recorded member
# ---------------------------------------------------------------------------


def _seed(repo: Path, head: str, finding: dict) -> None:
    _set_marker(repo)
    _write_manifest(repo, head, id=PRIOR_ID)
    _full_roster_partials(repo, head, findings_by_role={"correctness": [finding]})
    result = _run_consolidate(repo)
    assert result.returncode == 0, result.stderr


def _verify(repo: Path, head: str, resolution: dict):
    _set_marker(repo)
    _write_manifest(repo, head, id="rev-verify-0002", mode=VERIFY_MODE, roster=["reviewer"])
    _write_partial(repo, "reviewer", head, resolutions=[resolution])
    return _run_consolidate(repo)


def _repo(tmp_path: Path, finding: dict) -> tuple[Path, str]:
    repo = tmp_path / "r"
    _init_repo(repo)
    head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _seed(repo, head, finding)
    return repo, head


def _still_blocking(repo: Path) -> bool:
    facts = _store_facts(repo)
    prior = next(f for f in facts if f.get("id") == PRIOR_ID)
    resolved = coverage_algebra.resolution_index(facts)
    return any(f.get("fid") == "R-1" for f in coverage_algebra.unresolved_blocking(prior, resolved))


def _fixed(*ids: str) -> list[dict]:
    return [{"id": i, "disposition": "fixed", "evidence": f"read {i}"} for i in ids]


class TestResolutionsGradeMembers:
    def test_two_of_three_appends_no_resolution_and_names_the_third(self, tmp_path):
        repo, head = _repo(tmp_path, CLASS_FINDING)
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1",
                                      "disposition": "fixed", "members": _fixed("m1", "m2")})
        assert result.returncode == 0, result.stderr
        assert _store_facts(repo, "resolution") == []
        assert _still_blocking(repo)
        next_action = next(ln for ln in result.stdout.splitlines() if ln.startswith("NEXT-ACTION:"))
        assert "m3" in next_action and f"{PRIOR_ID}/R-1" in next_action
        assert "m1" not in next_action.split("m3")[0].rsplit("R-1", 1)[-1]  # names the missing, not the covered
        cache = json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())
        assert cache["next_action"] == next_action.removeprefix("NEXT-ACTION: ")

    def test_a_waived_member_without_a_rationale_does_not_cover_it(self, tmp_path):
        repo, head = _repo(tmp_path, CLASS_FINDING)
        members = _fixed("m1", "m2") + [{"id": "m3", "disposition": "waived"}]
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1",
                                      "disposition": "fixed", "members": members})
        assert result.returncode == 0, result.stderr
        assert _store_facts(repo, "resolution") == []
        assert "m3" in result.stdout

    def test_a_resolution_without_members_does_not_cover_a_finding_with_them(self, tmp_path):
        repo, head = _repo(tmp_path, CLASS_FINDING)
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1", "disposition": "fixed"})
        assert result.returncode == 0, result.stderr
        assert _store_facts(repo, "resolution") == []
        assert _still_blocking(repo)

    def test_covering_all_three_appends_the_fact_with_its_members(self, tmp_path):
        repo, head = _repo(tmp_path, CLASS_FINDING)
        members = _fixed("m1", "m3") + [{"id": "m2", "disposition": "waived", "rationale": "dead code"}]
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1",
                                      "disposition": "fixed", "members": members})
        assert result.returncode == 0, result.stderr
        (fact,) = _store_facts(repo, "resolution")
        assert [m["id"] for m in fact["body"]["members"]] == ["m1", "m2", "m3"]
        assert fact["body"]["members"][1] == {"id": "m2", "disposition": "waived",
                                              "rationale": "dead code"}
        assert not _still_blocking(repo)

    def test_a_finding_without_members_resolves_as_today(self, tmp_path):
        repo, head = _repo(tmp_path, PLAIN_FINDING)
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1", "disposition": "fixed",
                                      "members": _fixed("m1")})
        assert result.returncode == 0, result.stderr
        (fact,) = _store_facts(repo, "resolution")
        assert set(fact["body"]) == {"finding", "disposition", "verified_by", "at_tree", "rationale"}
        assert not _still_blocking(repo)

    def test_a_finding_level_waiver_still_waives(self, tmp_path):
        """D2 grades a `fixed` claim. A waiver carries its own rationale for the
        whole finding, as it always did."""
        repo, head = _repo(tmp_path, CLASS_FINDING)
        result = _verify(repo, head, {"review_id": PRIOR_ID, "fid": "R-1",
                                      "disposition": "waived", "rationale": "out of scope"})
        assert result.returncode == 0, result.stderr
        assert len(_store_facts(repo, "resolution")) == 1


# ---------------------------------------------------------------------------
# D3 — the verify roll-call hands the verifier the member list
# ---------------------------------------------------------------------------


class TestTheRollCallRendersMembers:
    def test_members_and_closure_are_rendered(self):
        text = cc.account_for_prior_blockers_directive([{
            "review_id": "rev-a", "fid": "R-1", "title": "t", "scope": "class",
            "closure": "every writer that skips guard()", "members": MEMBERS,
        }])
        assert "every writer that skips guard()" in text
        for m in MEMBERS:
            assert f"{m['id']} {m['site']}" in text or f"{m['id']} `{m['site']}`" in text
        assert "unbounded" not in text
        assert "`members`" in text  # how a resolution answers them

    def test_a_class_without_members_is_unbounded(self):
        text = cc.account_for_prior_blockers_directive([{
            "review_id": "rev-a", "fid": "R-1", "title": "t", "scope": "class",
        }])
        assert "class, unbounded — closes only by a construction" in text

    def test_an_instance_renders_neither(self):
        plain = cc.account_for_prior_blockers_directive([
            {"review_id": "rev-a", "fid": "R-1", "title": "t"}])
        instance = cc.account_for_prior_blockers_directive([
            {"review_id": "rev-a", "fid": "R-1", "title": "t", "scope": "instance"}])
        assert plain == instance
        assert "unbounded" not in plain and "members" not in plain.split("\n", 2)[1]

    def test_carried_blocking_carries_the_fields_on_both_paths(self, tmp_path):
        repo, head = _repo(tmp_path, CLASS_FINDING)
        facts = _store_facts(repo)
        anchor = cc.carried_blocking(facts, "headtree000000000000", "rev-next",
                                     anchor_id=PRIOR_ID)
        counted = cc.carried_blocking(facts, None, "rev-next",
                                      [{"review_id": PRIOR_ID, "fid": "R-1", "title": "t"}])
        for entries in (anchor, counted):
            (entry,) = entries
            assert entry["members"] == MEMBERS
            assert entry["closure"] == CLASS_FINDING["closure"]
            assert entry["scope"] == "class"
