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

    def test_with_no_review_of_its_own_it_says_so_and_shows_none(self, tmp_path):
        """A branch with no review, and a cache naming a review off its lineage:
        the answer is definitive, not a doubt. Renegotiated from "Could not
        confirm… may be another branch's", which hedged a fact `verify_anchor`
        had established and then showed that review's blocking count as if it
        were this branch's."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")

        out = _summary(repo)

        assert out.splitlines() == [
            "This branch has no review; the findings cache holds `feature/a`'s "
            "review rev-a-000001, not shown here."
        ], out
        assert "A's own defect" not in out and "blocking" not in out.lower(), out

    def test_the_owner_names_the_other_branch(self, tmp_path):
        """One owner of the answer: `verify_anchor` says WHOSE review the
        cache holds (`foreign_branch`), so no reader reaches for the fact's
        recorded branch itself."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")

        answer = cc.verify_anchor(repo, repo / ".prawduct", evidence.read_facts(repo))

        assert answer["fact"] is None and answer["foreign"]["id"] == "rev-a-000001", answer
        assert answer["foreign_branch"] == "feature/a", answer

    def test_the_briefing_reaches_into_no_private_name_of_the_owner(self):
        source = Path(briefing.__file__).read_text(encoding="utf-8")
        assert "critic_consolidate._" not in source, (
            "ask critic_consolidate's public answer (verify_anchor), not its helpers"
        )

    def test_after_an_amend_this_branchs_findings_stay_shown_hedged(self, tmp_path):
        """`git commit --amend` on the reviewed branch: the reviewed head is no
        longer an ancestor, and no other review anchors on the rewritten
        lineage. That is not another branch's review — the cache's review was
        recorded on THIS branch — so its BLOCKING findings and NEXT-ACTION
        stay in front of the builder, under the "could not confirm" lead."""
        repo = _two_branches(tmp_path)  # on feature/a; the cache holds rev-a
        _git(repo, "commit", "--quiet", "--amend", "-m", "feat: feature/a (amended)")

        answer = cc.verify_anchor(repo, repo / ".prawduct", evidence.read_facts(repo))
        out = _summary(repo)

        assert answer["fact"] is None and answer["foreign"] is None, answer
        assert answer["foreign_branch"] is None, answer
        lead = out.splitlines()[0]
        assert lead.startswith("Could not confirm review rev-a-000001"), lead
        assert "BLOCKING: A's own defect" in out, out
        assert "NEXT-ACTION:" in out, out
        assert "This branch has no review" not in out, out

    def test_after_a_rebase_this_branchs_findings_stay_shown_hedged(self, tmp_path):
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _commit_file(repo, "src/m.py", "m = 1\n", "feat: main moves on")
        _git(repo, "checkout", "--quiet", "feature/a")
        _git(repo, "rebase", "--quiet", "main")

        out = _summary(repo)

        assert out.splitlines()[0].startswith("Could not confirm review rev-a-000001"), out
        assert "BLOCKING: A's own defect" in out, out

    def test_when_the_owner_cannot_answer_the_doubt_is_named(self, tmp_path):
        """Control for the definitive case: an unreadable store cannot say
        whose review the cache holds, so the record stands, hedged."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "feature/b")
        evidence.store_path(repo).write_bytes(b"\xff\xfe not utf-8\n")

        out = _summary(repo)

        lead = out.splitlines()[0]
        assert lead.startswith("Could not confirm review rev-a-000001"), lead
        assert "another branch's review" in lead, lead
        assert "BLOCKING: A's own defect" in out, out

    def test_a_fresh_worktree_with_no_cache_shows_its_branchs_review(self, tmp_path):
        """The cache is per-worktree and the store clone-shared: a fresh
        worktree of a reviewed branch has no cache, and its briefing used to
        say nothing about a review the store holds."""
        repo = _two_branches(tmp_path)
        (repo / FINDINGS_REL).unlink()

        out = _summary(repo)

        lead = out.splitlines()[0]
        assert lead.startswith("Showing review rev-a-000001, this branch's newest"), lead
        assert "no readable findings cache" in lead, lead
        assert "BLOCKING: A's own defect" in out, out
        assert not (repo / FINDINGS_REL).exists(), "display only: nothing is written"

    def test_an_undecodable_cache_defers_to_the_owner_too(self, tmp_path):
        repo = _two_branches(tmp_path)
        (repo / FINDINGS_REL).write_bytes(b"\xff\xfe not utf-8\n")

        out = _summary(repo)

        assert out.splitlines()[0].startswith("Showing review rev-a-000001"), out
        assert "BLOCKING: A's own defect" in out, out

    def test_an_undecodable_cache_with_no_review_to_show_is_still_reported(self, tmp_path):
        """Control: with nothing the owner can show, the unreadable record is
        named — never rendered as "no review has run"."""
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")
        (repo / FINDINGS_REL).write_bytes(b"\xff\xfe not utf-8\n")

        out = _summary(repo)

        assert "could not be read" in out and "NOT a statement" in out, out

    def test_no_cache_and_no_review_reports_nothing(self, tmp_path):
        repo = _two_branches(tmp_path)
        _git(repo, "checkout", "--quiet", "main")
        _git(repo, "checkout", "--quiet", "-b", "feature/c")
        _commit_file(repo, "src/c.py", "c = 1\n", "feat: c")
        (repo / FINDINGS_REL).unlink()

        assert briefing._summarize_critic_findings(repo / ".prawduct", repo) is None

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


def _branch_line(out: str) -> str:
    lines = [ln for ln in out.splitlines() if ln.startswith("Branch findings")]
    assert len(lines) == 1, out
    return lines[0]


class TestTheBranchsOpenFindingsComeFromFacts:
    """#334, the read side. The handoff summarized the newest review's record,
    so a clean newest round hid an earlier round's open blocker from the fresh
    session that reads it — which then re-opens closed work or misses open
    work. A line composed from facts over the branch's review set now sits
    under the record."""

    def _clean_round_after_a_blocker(self, tmp_path: Path) -> Path:
        """feature/a: round 1 (rev-a) carries a blocker; round 2 (rev-a2), at
        the next commit, is clean — so the cache names a 0-blocking review."""
        repo = _two_branches(tmp_path)
        tip = _commit_file(repo, "src/a2.py", "w = 1\n", "feat: more of a")
        tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        _set_marker(repo)
        _write_manifest(repo, tip, id="rev-a2-000002", head_tree=tree, head_commit=tip,
                        files_changed=["src/a2.py"], files_reviewed=["src/a2.py"])
        _full_roster_partials(repo, tip, findings_by_role={})
        assert _run_consolidate(repo).returncode == 0
        record = json.loads((repo / FINDINGS_REL).read_text())
        assert record["fact_id"] == "rev-a2-000002"
        assert not [f for f in record.get("findings", []) if f.get("severity") == "blocking"], (
            "the premise: the cache claims 0 blocking"
        )
        return repo

    def test_the_cache_says_zero_and_the_facts_say_one(self, tmp_path):
        repo = self._clean_round_after_a_blocker(tmp_path)

        line = _branch_line(_summary(repo))

        assert "2 review round(s)" in line, line
        assert "1 open blocking" in line, line

    def test_the_handoff_carries_it(self, tmp_path):
        """At the layer the acceptance names: the session handoff."""
        repo = self._clean_round_after_a_blocker(tmp_path)

        text = briefing.render_session_handoff(repo).text

        section = text.split("## Critic Findings", 1)[1].split("\n## ", 1)[0]
        assert "1 open blocking" in _branch_line(section), section

    def test_a_resolution_fact_closes_it(self, tmp_path):
        """Control: the count is the gate's — a resolution fact lifts it."""
        repo = self._clean_round_after_a_blocker(tmp_path)
        evidence.append_fact(repo, "resolution", "res-a-R-1", {
            "finding": {"review_id": "rev-a-000001", "fid": "R-1"},
            "disposition": "fixed",
        })

        assert "0 open blocking" in _branch_line(_summary(repo))

    def test_another_branchs_blocker_is_not_counted(self, tmp_path):
        """The store is clone-wide: feature/b's blocker is not feature/a's."""
        repo = self._clean_round_after_a_blocker(tmp_path)
        evidence.append_fact(repo, "resolution", "res-a-R-1", {
            "finding": {"review_id": "rev-a-000001", "fid": "R-1"},
            "disposition": "fixed",
        })

        line = _branch_line(_summary(repo))

        assert "2 review round(s)" in line and "0 open blocking" in line, line

    def test_an_unreadable_store_is_said_never_clean(self, tmp_path):
        repo = _two_branches(tmp_path)
        evidence.store_path(repo).write_bytes(b"\xff\xfe not utf-8\n")

        line = _branch_line(_summary(repo))

        assert "could not be read" in line and "NOT a statement" in line, line
        assert "open blocking" not in line, line


_PLAN = (
    "---\nscope: s\n---\n\n# Build Plan — from plan (2026-10-25)\n\n"
    "**Size**: small | **Type**: refactor\n\n"
    "## Build Chunks\n\n### Chunk 01: First\n\n### Chunk 02: Second\n"
)


class TestTheSessionStartCost:
    """The section renders on every SessionStart boundary. Asking the owner
    for a review when the cache is absent (a fresh worktree) costs an
    evidence-store parse and git reads, where it used to return at once. The
    cost is the PARSE and the GIT READS, so those are what is counted."""

    @staticmethod
    def _count(monkeypatch, module, name) -> list:
        calls: list = []
        real = getattr(module, name)

        def counted(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)
        return calls

    def test_the_handoff_parses_the_store_once(self, tmp_path, monkeypatch):
        """The plan's work context, its progress table and this section each
        read the store; they share one parse."""
        from lib import work_unit

        repo = _two_branches(tmp_path)
        plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(_PLAN)
        binding = work_unit.Binding("bound", "s", plan, "integration", None, "binding")
        monkeypatch.setattr(briefing.work_unit, "resolve", lambda _project_dir: binding)
        parses = self._count(monkeypatch, evidence, "read_facts")

        text = briefing.render_session_handoff(repo).text

        assert "## Work In Progress" in text and "## Critic Findings" in text, text
        assert "A's own defect" in text, "the section rendered from the shared read"
        assert len(parses) == 1, f"{len(parses)} store parses for one handoff"

    def test_no_cache_and_no_review_in_the_store_asks_no_git(self, tmp_path, monkeypatch):
        """A fresh worktree in a repo whose store holds no review: nothing to
        show and nothing to doubt, answered without the owner's git reads."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir(exist_ok=True)
        asked = self._count(monkeypatch, cc, "verify_anchor")
        git = self._count(monkeypatch, briefing.subprocess, "run")

        assert briefing._summarize_critic_findings(repo / ".prawduct", repo) is None
        assert asked == [], asked
        # The one git call left locates the store (`rev-parse --git-common-dir`);
        # none walks the branch range or reads HEAD's branch.
        commands = [" ".join(map(str, call[0])) for call in git]
        assert len(commands) == 1 and "--git-common-dir" in commands[0], commands

    def test_control_no_cache_with_a_review_in_the_store_asks_the_owner(self, tmp_path, monkeypatch):
        repo = _two_branches(tmp_path)
        (repo / FINDINGS_REL).unlink()
        asked = self._count(monkeypatch, cc, "verify_anchor")

        out = _summary(repo)

        assert len(asked) == 1 and "BLOCKING: A's own defect" in out, out
