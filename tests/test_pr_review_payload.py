"""Tests for `prawduct-hook pr-review-payload` (pr-review-payload ch.01).

The command emits no verdict, so it is ADVICE and fails soft per section. That
makes the degradation paths, not the happy path, where the invariant actually
lives: a section that renders EMPTY reads to the reviewer as "checked, nothing
found", which manufactures the false success the section exists to prevent. Most
of what follows therefore asserts that a broken section says, in the reviewer's
own words, which of its checks went unanswered.

The one hard failure is an unresolvable base — no base means no review interval,
so there is nothing for any other section to be about.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"

sys.path.insert(0, str(REPO_ROOT / "plugin"))
from lib import pr_payload  # noqa: E402


#: The sections the command promises, written out HERE rather than imported.
#: Asserting the emitted set against the module's own `SECTION_NAMES` would be
#: satisfied by dropping a section from both — the agreement would hold and the
#: contract would not. This literal is the independent side.
EXPECTED_SECTIONS = [
    "base",
    "commits",
    "diffstat",
    "work",
    "test_evidence",
    "build_plan",
    "change_log",
    "backlog",
    "default_branch",
]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, env=env, timeout=30
    )


def _repo(tmp_path: Path, *, with_plan: bool = True, with_change_log: bool = True) -> Path:
    """A governed repo with a base branch, a commit on a feature branch, and the
    `.prawduct/` state the payload reads."""
    repo = tmp_path / "repo"
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "develop")

    (repo / "app.py").write_text("print(1)\n")
    (repo / ".prawduct" / "project-state.yaml").write_text(
        "project_name: fixture\nbase_branch: develop\n"
    )
    if with_plan:
        (repo / ".prawduct" / "artifacts" / "build-plan-widget.md").write_text(
            "---\n"
            "artifact: build-plan\n"
            "scope: widget\n"
            "branch: feat/widget\n"
            "---\n\n"
            "## Status\n\n"
            "- [x] Chunk 01: the first one\n"
            "- [ ] Chunk 02: the second one\n"
        )
    if with_change_log:
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n"
            "## Widget arrives\n"
            "<!-- prawduct: scope=widget -->\n\n"
            "It does the widget thing.\n"
        )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", "feat/widget")
    (repo / "app.py").write_text("print(2)\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat(widget): the widget thing, closes: #41")
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    return subprocess.run(
        ["python3", str(HOOK), "pr-review-payload", *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=60,
    )


def _sections(repo: Path) -> dict[str, dict]:
    """Parse `--json` from the process's raw stdout.

    Fed straight from `capture_output`, never through a shell `echo` — zsh's
    `echo` interprets `\\n` and turns valid JSON into a false "malformed output"
    finding.
    """
    r = _run(repo, "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    return {s["name"]: s for s in data["sections"]}


class TestTheSectionSet:
    def test_every_promised_section_is_emitted(self, tmp_path):
        """Red if a section silently stops being assembled.

        The assertion is against a literal written in this file: comparing the
        output to the module's own `SECTION_NAMES` would go green if a section
        were dropped from both.
        """
        sections = _sections(_repo(tmp_path))
        assert list(sections) == EXPECTED_SECTIONS

    def test_the_module_roster_matches_what_is_emitted(self, tmp_path):
        """The other direction: `SECTION_NAMES` is the roster the docstring
        promises, so a section added to the output without being named there
        leaves the roster lying."""
        sections = _sections(_repo(tmp_path))
        assert list(pr_payload.SECTION_NAMES) == list(sections)

    def test_no_section_is_ever_both_empty_and_ok(self, tmp_path):
        """The core invariant. An `ok` section with no body renders as a blank
        heading, which reads as "checked, nothing found"."""
        for section in _sections(_repo(tmp_path)).values():
            if section["ok"]:
                assert section["body"], section["name"]
            else:
                assert section["degraded"], section["name"]

    def test_an_empty_review_interval_still_fills_every_section(self, tmp_path):
        """The case the ordinary fixture cannot reach.

        A branch level with its base has no commits and no diff, so `git log` and
        `git diff --stat` both return nothing — and "nothing" is exactly the
        input that turns an `ok` section into a blank heading the reviewer reads
        as "checked, nothing found". An empty RANGE is a real, reviewable answer
        and must be SAID; a mutation sweep found this gap, because every other
        fixture here has a diff and so never reaches the fallback.
        """
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-B", "feat/widget", "develop")

        sections = _sections(repo)
        for name in ("commits", "diffstat"):
            assert sections[name]["ok"], name
            assert sections[name]["body"], f"{name} rendered as a blank heading"
            assert "no " in sections[name]["body"].lower(), name

    def test_a_section_that_fails_to_assemble_becomes_a_named_degradation(self, monkeypatch, tmp_path):
        """The roster's whole claim, and it used to be a claim nothing enforced.

        `SECTION_NAMES` documented itself as the reason a failed section is "a
        NAMED degradation rather than a gap in a list nobody can count", while
        `assemble()` built its list by hand and never consulted it. A section
        that vanished left a GAP — which reads to the reviewer exactly like a
        section that found nothing.
        """
        monkeypatch.setattr(
            pr_payload, "_section_default_branch",
            lambda *a, **k: pr_payload.Section("something_else", body="x"),
        )
        sections, hard = pr_payload.assemble(_repo(tmp_path))
        assert hard is None
        by_name = {s.name: s for s in sections}
        assert "default_branch" in by_name, "the roster did not notice the gap"
        assert not by_name["default_branch"].ok
        assert "UNANSWERED" in by_name["default_branch"].degraded
        # And the stray one is shown rather than hidden.
        assert "something_else" in by_name

    def test_a_healthy_repo_degrades_only_the_section_it_cannot_answer(self, tmp_path):
        """The positive control for every degradation test below: if this repo
        degraded other sections anyway, a "names its reason" assertion elsewhere
        could be passing for the wrong reason.

        **`backlog` is the one exception, and it is the section working.** The
        fixture's commit cites `#41` and the fixture has no backlog cache, so
        R-1/R-2 genuinely cannot be answered — and this section's whole contract
        is that an unanswerable check says so rather than rendering as checked.
        It used to pass this control by reporting `ok` with `41` listed as a
        dangling citation, which is a finding ABOUT THE BRANCH manufactured out
        of a repo that simply has no cache to look in.
        """
        degraded = {n: s["degraded"] for n, s in _sections(_repo(tmp_path)).items() if not s["ok"]}
        assert set(degraded) == {"backlog"}, degraded
        assert "R-1 and R-2 are NOT answered" in degraded["backlog"]
        assert "41" in degraded["backlog"], "the ids it could not answer for are named"
        assert "dangling" not in degraded["backlog"], (
            "a repo with no cache has not proved a citation dangling — it has "
            "proved nothing, and saying otherwise is the false clean inverted"
        )

    def test_a_repo_citing_nothing_degrades_nothing_at_all(self, tmp_path):
        """The strict form of the control, so the carve-out above cannot quietly
        grow: with no id cited anywhere, every section including `backlog` is
        answerable and the payload is clean."""
        repo = _repo(tmp_path)
        _git(repo, "commit", "-q", "--amend", "-m", "feat(widget): the widget thing")
        degraded = {n: s["degraded"] for n, s in _sections(repo).items() if not s["ok"]}
        assert degraded == {}


class TestTheHappyPath:
    def test_the_base_and_commits_bound_the_review_interval(self, tmp_path):
        sections = _sections(_repo(tmp_path))
        assert "develop" in sections["base"]["body"]
        assert "the widget thing" in sections["commits"]["body"]

    def test_the_diff_stat_is_carried_and_the_diff_is_not(self, tmp_path):
        """The stat is the shape of the change; a second copy of the diff is the
        duplication this command exists to remove."""
        sections = _sections(_repo(tmp_path))
        assert "app.py" in sections["diffstat"]["body"]
        assert "print(2)" not in sections["diffstat"]["body"]

    def test_the_build_plan_status_boxes_are_carried_verbatim(self, tmp_path):
        body = _sections(_repo(tmp_path))["build_plan"]["body"]
        assert "build-plan-widget.md" in body
        assert "- [x] Chunk 01: the first one" in body
        assert "- [ ] Chunk 02: the second one" in body

    def test_the_change_log_entry_is_paired_by_scope(self, tmp_path):
        body = _sections(_repo(tmp_path))["change_log"]["body"]
        assert "Widget arrives" in body

    def test_the_work_section_carries_the_derived_scope(self, tmp_path):
        body = _sections(_repo(tmp_path))["work"]["body"]
        assert "scope: widget" in body
        assert "branch: feat/widget" in body


class TestDegradations:
    """One test per degradation path. Each asserts a NAMED reason, because the
    failure this command is built against is a section that degrades silently."""

    def test_an_unresolvable_base_is_the_one_hard_failure(self, tmp_path):
        repo = tmp_path / "norepo"
        (repo / ".prawduct").mkdir(parents=True)
        r = _run(repo)
        assert r.returncode == 1
        assert "base" in r.stderr.lower()
        assert r.stdout == "", "a hard failure must not also emit a partial payload"

    def test_no_build_plan_names_what_goes_unchecked(self, tmp_path):
        repo = _repo(tmp_path, with_plan=False)
        section = _sections(repo)["build_plan"]
        assert not section["ok"]
        assert "Status" in section["degraded"]

    def test_no_change_log_entry_names_the_finding_it_is(self, tmp_path):
        repo = _repo(tmp_path, with_change_log=False)
        section = _sections(repo)["change_log"]
        assert not section["ok"]
        assert "change log" in section["degraded"].lower()

    def test_a_commit_log_failure_names_the_goal_it_starves(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pr_payload, "_git", lambda *a, **k: (128, ""))
        section = pr_payload._section_commits(tmp_path, "develop")
        assert not section.ok
        assert "narrative" in section.degraded

    def test_a_diff_stat_failure_tells_the_reviewer_to_read_the_diff(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pr_payload, "_git", lambda *a, **k: (128, ""))
        section = pr_payload._section_diffstat(tmp_path, "develop")
        assert not section.ok
        assert "read the diff directly" in section.degraded

    def test_unreadable_test_evidence_degrades_toward_the_warning(self, monkeypatch, tmp_path):
        """The DIRECTION matters: a reviewer told nothing about test evidence
        must read that as "no fresh evidence" (its warning condition), never as
        the clear one."""
        class _Boom:
            def tests_are_current(self, *a, **k):
                raise RuntimeError("no")

        monkeypatch.setattr(
            pr_payload, "_lib",
            lambda: pr_payload._Lib(
                briefing=None, buildplan_refs=None, change_log=None,
                coverage=None, gates=_Boom(), gitstate=None,
            ),
        )
        section = pr_payload._section_test_evidence(tmp_path)
        assert not section.ok
        assert "NO fresh evidence" in section.degraded

    def test_no_default_branch_forbids_the_closing_keyword_reading(self, monkeypatch, tmp_path):
        """`Closes #N` fires only on merges into the default branch, so on a
        gitflow PR an open item is CORRECT state. Not knowing the default branch
        must forbid the inference, not silently permit it."""
        monkeypatch.setattr(pr_payload, "_git", lambda *a, **k: (1, ""))
        section = pr_payload._section_default_branch(tmp_path)
        assert not section.ok
        assert "do NOT read an open item" in section.degraded

    def test_no_scope_leaves_backlog_reconciliation_explicitly_unanswered(self, tmp_path):
        """R-2's degradation is the sharp one: `review-protocol.md` marks it as
        the check no other layer in the pipeline owns, so silence here is read as
        "reconciled" by the only thing that reconciles."""
        section = pr_payload._section_backlog(tmp_path, None, ["ABC-1234"])
        assert not section.ok
        assert "R-1 and R-2 are NOT answered" in section.degraded
        assert "ABC-1234" in section.degraded

    @staticmethod
    def _envelope(data: dict) -> dict:
        """The shape `cachequery.resolve` ACTUALLY returns.

        Every fixture below goes through here rather than hand-writing a flat
        dict, because a hand-written one encodes the consumer's belief about the
        producer — which is exactly how the envelope bug shipped green: the old
        fixtures returned `{"resolved": True, ...}` at the top level, a shape
        `resolve` has never produced, so the section read them correctly and read
        the real thing as a dangling citation for every id.
        `test_the_fixture_shape_matches_the_real_producer` is what keeps this
        honest; it asks the producer rather than me.
        """
        return {"status": "ok", "data": data, "warnings": []}

    def test_the_fixture_shape_matches_the_real_producer(self):
        """The pin that would have caught the envelope bug, and the only one here
        that cannot agree with a wrong belief: it asks `cachequery.resolve`
        itself what its top-level keys are, against this repo's own cache."""
        from datetime import datetime, timezone

        import lib.backlog.cachequery as cq

        real = cq.resolve(
            REPO_ROOT, scope="brookstalley/prawduct", id_raw="1", now=datetime.now(timezone.utc)
        )
        assert set(real) <= {"status", "data", "warnings", "error"}, real
        assert "resolved" not in real, (
            "`resolved` is INSIDE `data`; a fixture that puts it at the top level "
            "tests a producer that does not exist"
        )
        mine = self._envelope({"resolved": False})
        assert set(mine) == {"status", "data", "warnings"}
        assert set(mine) <= set(real) | {"warnings"}

    def test_a_backlog_lookup_failure_is_reported_as_partial_not_dropped(self, monkeypatch, tmp_path):
        """A short list of resolved ids reads as the whole set. The ids that
        could not be looked up have to be named, or the reviewer reconciles a
        subset believing it reconciled all of them."""
        import lib.backlog.cachequery as cq

        def _resolve(project_dir, *, scope, id_raw, now, default_owner=None):
            if id_raw == "ABC-1111":
                return TestDegradations._envelope(
                    {"resolved": True, "status": "open", "dead": False, "title": "a thing"}
                )
            raise RuntimeError("cache is gone")

        monkeypatch.setattr(cq, "resolve", _resolve)
        section = pr_payload._section_backlog(tmp_path, "owner/repo", ["ABC-1111", "ABC-2222"])
        assert section.ok, "a partial result is still a result"
        assert "ABC-1111: status=open" in section.body
        assert "NOT ANSWERED for: ABC-2222" in section.body

    def test_every_lookup_failing_degrades_the_whole_section(self, monkeypatch, tmp_path):
        import lib.backlog.cachequery as cq

        def _resolve(*a, **k):
            raise RuntimeError("cache is gone")

        monkeypatch.setattr(cq, "resolve", _resolve)
        section = pr_payload._section_backlog(tmp_path, "owner/repo", ["ABC-1111"])
        assert not section.ok
        assert "R-1 and R-2 are NOT answered" in section.degraded

    def test_an_error_envelope_degrades_rather_than_fabricating_dangling_ids(
        self, monkeypatch, tmp_path
    ):
        """`resolve` REPORTS an unreadable cache instead of raising, so the
        `except` arm never sees one. Read as a resolution result, an error
        envelope says "not resolved" for every id — which renders as a list of
        dangling citations and is a *finding about the branch* rather than a
        failure to look. That is the false clean this section exists to prevent,
        wearing the clothes of a real answer.
        """
        import lib.backlog.cachequery as cq

        monkeypatch.setattr(cq, "resolve", lambda *a, **k: {
            "status": "error",
            "error": {"code": "unavailable", "message": "the cache has no home"},
        })
        section = pr_payload._section_backlog(tmp_path, "owner/repo", ["ABC-1111"])
        assert not section.ok, "an unreadable cache is a degradation, not a verdict"
        assert "R-1 and R-2 are NOT answered" in section.degraded
        assert "the cache has no home" in section.degraded, (
            "the reader is owed the reason, in the producer's own words"
        )
        assert "dangling" not in section.degraded

    def test_a_resolved_item_is_read_out_of_the_data_envelope(self, monkeypatch, tmp_path):
        """The positive half. Without it, a section that degraded on everything
        would satisfy the error test above and still be broken."""
        import lib.backlog.cachequery as cq

        monkeypatch.setattr(cq, "resolve", lambda *a, **k: TestDegradations._envelope({
            "resolved": True, "status": "shipped", "dead": True,
            "title": "a shipped thing", "via": "alias",
        }))
        section = pr_payload._section_backlog(tmp_path, "owner/repo", ["ABC-1111"])
        assert section.ok
        assert "ABC-1111: status=shipped (closed)" in section.body
        assert "matched via alias" in section.body
        assert "dangling" not in section.body


class TestTheBacklogScopeIsNotThePlanScope:
    """Two different things are called "scope" one call frame apart.

    Every other section here takes the BUILD-PLAN scope (`pr-review-payload`,
    derived from the branch); `cachequery.resolve` wants the BACKLOG repo
    (`owner/repo`, from `backlog_service_repo:`). Handing it the plan's made
    every id report *"bare ID needs a repo"*, and nothing saw it, because on a
    fixture with no cache BOTH values degrade the section — just with different
    reasons. So this test asserts the VALUE that reaches the producer, which is
    the only thing the two spellings disagree about.
    """

    def test_resolve_is_called_with_the_backlog_repo(self, tmp_path, monkeypatch):
        import lib.backlog.cachequery as cq

        repo = _repo(tmp_path)
        state = repo / ".prawduct" / "project-state.yaml"
        state.write_text(state.read_text() + "\nbacklog_service_repo: acme/widgets\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "chore: cut over")

        seen = {}

        def _resolve(project_dir, *, scope, id_raw, now, default_owner=None):
            seen["scope"] = scope
            seen["default_owner"] = default_owner
            return {"status": "ok", "data": {"resolved": True, "status": "open",
                                             "dead": False, "title": "t"}}

        monkeypatch.setattr(cq, "resolve", _resolve)
        sections, hard = pr_payload.assemble(repo)
        assert hard is None, hard
        assert seen.get("scope") == "acme/widgets", (
            f"resolve was queried with {seen.get('scope')!r} — the build-plan "
            "scope is not a backlog repo and every id comes back needing one"
        )
        assert seen.get("default_owner") == "acme", (
            "a bare `#41` needs an owner to become a provider coordinate; "
            "`norm_probes._resolve_citation` derives it the same way"
        )

    def test_a_repo_that_has_not_cut_over_says_so_rather_than_guessing(self, tmp_path):
        """The other arm, and it must not borrow the plan scope to look busy:
        pre-cutover there is no cache scope at all, and inventing one is how the
        section produced dangling citations for a repo with nothing to look in.
        """
        sections = {s.name: s for s in pr_payload.assemble(_repo(tmp_path))[0]}
        backlog = sections["backlog"]
        assert not backlog.ok
        assert "backlog_service_repo" in backlog.degraded
        assert "widget" not in backlog.degraded, (
            "the build-plan scope has no business appearing in a message about "
            "which backlog to query"
        )


class TestTheChangeLogBodyReachesTheIdScan:
    """R-2's input set is the change-log entry as WRITTEN, not its heading.

    An id lives in an entry's prose far more often than in its title — this
    bundle's own entry is the worked example — and while the section carried only
    `line N: title` plus the tag map, every such id was invisible and the payload
    rendered "no backlog ids cited ... this is an answer, not a failure". A false
    clean on the one check `review-protocol.md` says nothing else in the pipeline
    owns. The body is also what Goal 2 tells the reviewer to read the diffstat
    against, so one omission starved two consumers.
    """

    def _repo_citing_in_the_body(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n"
            "## Widget arrives\n"
            "<!-- prawduct: scope=widget -->\n\n"
            "It does the widget thing, and closes #4242 on the way past.\n\n"
            "## An older entry\n"
            "<!-- prawduct: scope=sprocket -->\n\n"
            "Cites #9999, which belongs to a DIFFERENT scope.\n"
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "docs: change log")
        return repo

    def test_an_id_in_the_entry_body_is_scanned(self, tmp_path):
        sections = _sections(self._repo_citing_in_the_body(tmp_path))
        assert "4242" in sections["backlog"]["degraded"], (
            "an id written in the entry's prose never reached the id scan"
        )

    def test_the_body_is_carried_for_the_reviewer_to_read(self, tmp_path):
        """Goal 2's other consumer: the entry IS the release note, so a reviewer
        handed only its title cannot tell whether its prose covers the diff."""
        sections = _sections(self._repo_citing_in_the_body(tmp_path))
        assert "It does the widget thing" in sections["change_log"]["body"]

    def test_only_THIS_scope_entry_is_carried(self, tmp_path):
        """The bound that keeps the body from becoming the whole log: slicing to
        the next entry's start, not to EOF. Without it the section carries every
        older entry and `#9999` — another scope's citation — enters R-2's set."""
        sections = _sections(self._repo_citing_in_the_body(tmp_path))
        assert "9999" not in sections["change_log"]["body"]
        assert "9999" not in (sections["backlog"]["degraded"] or sections["backlog"]["body"] or "")


class TestBacklogIdExtraction:
    """`cited_backlog_ids` is R-2's input set: a change-log entry or a commit
    that CLAIMS a closure."""

    def test_both_id_spellings_are_found(self):
        ids = pr_payload.cited_backlog_ids(
            "abc1234 fix(thing): closes: #41 and BKL-9V2W", ""
        )
        assert ids == ["BKL-9V2W", "41"]

    def test_ids_are_deduped_in_first_seen_order(self):
        ids = pr_payload.cited_backlog_ids("BKL-9V2W once", "BKL-9V2W again, and ABC-1A2B")
        assert ids == ["BKL-9V2W", "ABC-1A2B"]

    def test_a_bare_number_after_a_slash_is_not_a_citation(self):
        """Red if the `#N` pattern stops requiring the `#`. `refs/pull/12` is a
        path, not a citation."""
        assert pr_payload.cited_backlog_ids("see refs/pull/12 for context", "") == []

    def test_a_qualified_citation_is_captured_whole_and_only_once(self):
        """The lookbehind's actual job, and the case that discriminates it.

        `owner/repo#249` is a spelling `cachequery.resolve` accepts. Captured
        whole it resolves to the item it names; capture the trailing number as
        well and the SAME citation is looked up twice, the second time as a bare
        `#249` in whatever repo the cache defaults to — a different item. Drop
        the lookbehind and this returns both.
        """
        assert pr_payload.cited_backlog_ids("fix: closes owner/repo#249", "") == [
            "owner/repo#249"
        ]

    def test_a_qualified_and_a_bare_citation_both_survive(self):
        """Paired positive: the lookbehind must not swallow a genuine bare `#N`
        that merely shares a line with a qualified one."""
        assert pr_payload.cited_backlog_ids("a/b#7 supersedes #8", "") == ["a/b#7", "8"]

    def test_nothing_cited_is_an_empty_list_not_a_guess(self):
        assert pr_payload.cited_backlog_ids("abc1234 chore: tidy up", "") == []


class TestCli:
    def test_an_unknown_argument_is_refused(self, tmp_path):
        r = _run(_repo(tmp_path), "--bogus")
        assert r.returncode == 1
        assert "unknown argument" in r.stderr

    def test_the_human_rendering_leads_with_the_degraded_count(self, tmp_path):
        repo = _repo(tmp_path, with_plan=False, with_change_log=False)
        r = _run(repo)
        assert r.returncode == 0, r.stderr
        assert "sections degraded" in r.stdout
        assert "An unanswered check is not a passed one." in r.stdout

    def test_the_human_rendering_says_nothing_about_degradation_when_there_is_none(self, tmp_path):
        """Paired with the test above — a bare negative would be satisfied by an
        empty output."""
        repo = _repo(tmp_path)
        # Citing nothing is what makes this repo fully answerable — the default
        # fixture's `closes: #41` leaves `backlog` honestly unanswered, and this
        # test is about the CLEAN rendering, not about that.
        _git(repo, "commit", "-q", "--amend", "-m", "feat(widget): the widget thing")
        r = _run(repo)
        assert r.returncode == 0, r.stderr
        assert "sections degraded" not in r.stdout
        for name in EXPECTED_SECTIONS:
            assert f"## {name}" in r.stdout

    def test_an_incomplete_lib_is_attributed_rather_than_a_traceback(self, tmp_path, monkeypatch, capsys):
        """`_lib` imports six sibling modules at FIRST USE, inside `assemble` —
        later than, and outside, the CLI wrapper's `from lib import pr_payload`
        handler. So a partially-installed plugin surfaced as a stack trace,
        which `api-contract.md` § Direction forbids, and `_lib`'s own docstring
        claimed the wrapper reported it.

        Entered at `emit`, which is the layer that owns the exit code — pinning
        `_lib` alone would prove the raiser and not the reporter.
        """
        def _boom() -> None:
            raise ImportError("No module named 'lib.gitstate'")

        monkeypatch.setattr(pr_payload, "_lib", _boom)
        rc = pr_payload.emit(_repo(tmp_path), [])
        assert rc == 1
        err = capsys.readouterr().err
        assert "the plugin lib/ is incomplete" in err
        assert "lib.gitstate" in err, (
            "the attribution must carry the missing module — 'something failed' "
            "leaves the operator with the same stack trace's worth of nothing"
        )

    def test_json_is_parseable_from_raw_process_bytes(self, tmp_path):
        r = _run(_repo(tmp_path), "--json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["schema_version"] == 1
        assert len(data["sections"]) == len(EXPECTED_SECTIONS)
