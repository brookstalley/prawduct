"""The briefing summarizes the checked-out branch's review, not whatever the
single-slot findings cache last held (#1179).

``.prawduct/.critic-findings.json`` survives a branch switch, so after one it
names the other branch's review — and the session handoff's ``## Critic
Findings`` section, read by the builder who lost the reviewer's report, used to
summarize it as this branch's. "Which review is this branch's" has one owner
(``critic_consolidate.select_branch_review``, asked read-only through
``verify_anchor``); the briefing now asks it, shows the answer, names it when
it differs from the cache, and writes nothing.

Real git throughout, on the two-branch fixture the verify-anchor tests use.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_critic_consolidate import (
    FINDINGS_REL,
    _commit_file,
    _full_roster_partials,
    _git,
    _init_repo,
    _run_consolidate,
    _set_marker,
    _store_facts,
    _write_manifest,
)

from lib import briefing
from lib import critic_consolidate as cc
from lib import evidence


def _finding(name: str) -> dict:
    return {"correctness": [{"name": name, "goal": "Nothing Is Broken", "severity": "blocking",
                             "recommendation": "Fix it", "files": ["src/app.py"]}]}


def _review(repo: Path, review_id: str, head: str, finding: str, **overrides) -> None:
    _set_marker(repo)
    _write_manifest(repo, head, id=review_id, **overrides)
    _full_roster_partials(repo, head, findings_by_role=_finding(finding))
    result = _run_consolidate(repo)
    assert result.returncode == 0, f"seed {review_id} failed: {result.stderr!r}"


def _two_branches(tmp_path: Path) -> Path:
    """``feature/b`` reviewed (rev-b, "B's own defect"), then ``feature/a``
    reviewed (rev-a, "A's own defect") and checked out — so the slot names
    rev-a. Each branch's review names a finding only it has."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore review bookkeeping")
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    (repo / ".prawduct").mkdir(exist_ok=True)
    for branch, rid, finding in (("feature/b", "rev-b-000001", "B's own defect"),
                                 ("feature/a", "rev-a-000001", "A's own defect")):
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", branch)
        tip = _commit_file(repo, f"src/{branch[-1]}.py", "v = 1\n", f"feat: {branch}")
        tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        _review(repo, rid, tip, finding, head_tree=tree, head_commit=tip,
                files_changed=[f"src/{branch[-1]}.py"], files_reviewed=[f"src/{branch[-1]}.py"])
    assert json.loads((repo / FINDINGS_REL).read_text())["fact_id"] == "rev-a-000001"
    return repo


def _summary(repo: Path) -> str:
    out = briefing._summarize_critic_findings(repo / ".prawduct", repo)
    assert out is not None
    return out


class TestTheBriefingShowsThisBranchsReview:
    def test_after_a_switch_it_summarizes_the_switched_to_branchs_review(self, tmp_path):
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        before = (repo / FINDINGS_REL).read_text()

        out = _summary(repo)

        assert "BLOCKING: B's own defect" in out, out
        assert "A's own defect" not in out, out
        # Named, with the review the cache holds beside it: a reader comparing
        # this to the file must be told why they differ.
        lead = out.splitlines()[0]
        assert lead.startswith("Showing review rev-b-000001, this branch's newest."), lead
        assert "rev-a-000001" in lead, lead
        # Display only: the slot is the dispatch's and ingest's to re-point.
        assert (repo / FINDINGS_REL).read_text() == before

    def test_on_the_branch_the_cache_names_it_is_shown_as_written(self, tmp_path):
        """Control: the cache is this branch's, so nothing is named and the
        record is summarized as the file holds it."""
        repo = _two_branches(tmp_path)

        out = _summary(repo)

        assert out.splitlines()[0] != "" and not out.startswith("Showing review"), out
        assert not out.startswith("Could not confirm"), out
        assert "BLOCKING: A's own defect" in out, out
        assert "B's own defect" not in out, out

    def test_with_no_review_of_its_own_the_doubt_is_named(self, tmp_path):
        """A branch with no review: the owner finds none to show instead, so
        the cache's record stands — said to be possibly another branch's."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")

        out = _summary(repo)

        lead = out.splitlines()[0]
        assert lead.startswith("Could not confirm review rev-a-000001"), lead
        assert "another branch's review" in lead, lead
        assert "BLOCKING: A's own defect" in out, out

    def test_the_handoff_carries_it(self, tmp_path):
        """At the layer the defect was reported: the session handoff's
        `## Critic Findings` section."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")

        text = briefing.render_session_handoff(repo).text

        section = text.split("## Critic Findings", 1)[1].split("\n## ", 1)[0]
        assert "BLOCKING: B's own defect" in section, section
        assert "A's own defect" not in section, section

    def test_the_record_shown_is_the_one_the_cache_writer_would_write(self, tmp_path):
        """`branch_review_record` renders what `derive_branch_cache` writes;
        pinned against the writer so the two cannot drift. A verify pass is the
        case that differs from a bare projection: it carries its anchor's
        unresolved blockers."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        rev_b = next(f for f in _store_facts(repo, "review") if f["id"] == "rev-b-000001")
        verify = {**rev_b, "id": "rev-b-verify1", "ts": "2099-01-01T00:00:00Z",
                  "body": {**rev_b["body"], "findings": [],
                           "mode": cc._VERBOSE_VERIFY_RESOLUTIONS,
                           "base_tree": rev_b["body"]["head_tree"]}}
        assert evidence.append_envelope(repo, verify)["status"] == "appended"
        facts = evidence.read_facts(repo)["facts"]
        prawduct = repo / ".prawduct"

        shown = cc.branch_review_record(prawduct, verify, facts)
        out = _summary(repo)
        written = cc.derive_branch_cache(
            prawduct, facts, [_git(repo, "rev-parse", "HEAD").stdout.strip()]
        )

        assert written["status"] == "derived" and written["review"] == "rev-b-verify1", written
        assert json.loads((repo / FINDINGS_REL).read_text()) == shown
        assert "B's own defect" in out, "the carried blocker reaches the briefing"
