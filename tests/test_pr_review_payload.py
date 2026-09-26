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
    "learnings_cap",
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


def _claimed(item_id: str) -> "pr_payload.Citation":
    """A citation that CLAIMS a closure — the shape R-2 is stated over.

    The degradation tests below are about the lookup, not about the citing form,
    so they use the claiming shape deliberately: a merely-mentioned id takes a
    different render path, and `TestTheCitationFormReachesTheSection` is where
    that distinction is graded.
    """
    return pr_payload.Citation(item_id, True)


def _repo(tmp_path: Path, *, with_plan: bool = True, with_change_log: bool = True) -> Path:
    """A governed repo with a base branch, a commit on a feature branch, and the
    `.prawduct/` state the payload reads."""
    repo = tmp_path / "repo"
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "develop")
    # Hermetic by construction. `_section_default_branch` falls back to
    # `git config --get init.defaultBranch` when a repo has no `origin/HEAD`,
    # and that read reaches the HOST's global config — so on a machine that
    # sets it (most developers') the section answers, and on one that does not
    # (the CI runner) it degrades. The suite was green for its maintainer and
    # red in CI for four tests on exactly this. Set it in the fixture's own
    # config so the repo answers for itself; `TestDegradations` covers the
    # unset case explicitly rather than leaving it to the host.
    _git(repo, "config", "init.defaultBranch", "main")

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

    def test_the_payload_says_WHICH_freshness_clause_answered(self):
        """Both disjuncts exit 0 and they are NOT the same evidence.

        `review-protocol.md` tells the reviewer to read which guarantee a bundle
        rests on — `tree-valid` means the recorded run met this exact tree,
        `session-fresh` means a run from earlier in the session that never did.
        A payload reporting only "current" makes that unanswerable from the one
        section the reviewer was told to read, and the reviewer does not run the
        suite itself, so there is no second source.

        Parametrized over the clause rather than asserting one spelling: the
        labels are `lib.gates` constants precisely so prose and payload cannot
        drift apart, and reading them here is what keeps this test honest if
        they are reworded.

        What turns this red: unpacking `tests_are_current` without the clause,
        or rendering a bare "current" for either disjunct.
        """
        from lib import gates  # via conftest's sys.path shim, like every sibling

        seen = {}
        for clause, expected in (
            ("tree", gates.CURRENT_TREE_LABEL),
            ("session", gates.CURRENT_SESSION_LABEL),
        ):
            class _Stub:
                CURRENT_TREE_LABEL = gates.CURRENT_TREE_LABEL
                CURRENT_SESSION_LABEL = gates.CURRENT_SESSION_LABEL

                def __init__(self, c):
                    self._c = c

                def tests_are_current(self, *a, **k):
                    # ONE reason string for both clauses on purpose: if it
                    # varied, the closing assertion below would differ because
                    # of the reason and pass even when both labels render the
                    # same, which is the defect it exists to catch.
                    return True, "a reason that does not vary by clause", self._c

            import unittest.mock as _m
            with _m.patch.object(
                pr_payload, "_lib",
                lambda c=clause: pr_payload._Lib(
                    briefing=None, buildplan_refs=None, change_log=None,
                    coverage=None, gates=_Stub(c), gitstate=None,
                ),
            ):
                section = pr_payload._section_test_evidence(REPO_ROOT)
            assert section.ok, clause
            assert expected in section.body, (
                f"the {clause} clause renders as {section.body!r}, which does not "
                f"name {expected!r} — the reviewer cannot tell the two apart"
            )
            seen[clause] = section.body

        # The `test-status:` LINE, not the whole body — the body also carries
        # `reason:`, so comparing bodies passes on a difference that is not the
        # label's.
        first = {k: v.splitlines()[0] for k, v in seen.items()}
        assert first["tree"] != first["session"], (
            f"both clauses render their test-status line identically ({first['tree']!r}), "
            "so the payload carries the verdict but not the guarantee — which is "
            "the whole distinction"
        )

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
        section = pr_payload._section_backlog(tmp_path, None, [_claimed("ABC-1234")])
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
        # Reachability first. `.prawduct/` caches are gitignored, so on a fresh
        # clone this gets an ERROR envelope rather than an `ok` one — which is
        # still the producer answering, and still carries `status` at the top
        # level, which is the shape under test. Without this line a producer
        # that returned `None` or blew up into a caught default would satisfy
        # both assertions below by vacuity.
        assert isinstance(real, dict) and "status" in real, (
            f"`cachequery.resolve` returned no envelope at all: {real!r}"
        )
        assert set(real) <= {"status", "data", "warnings", "error"}, real
        assert "resolved" not in real, (
            "`resolved` is INSIDE `data`; a fixture that puts it at the top level "
            "tests a producer that does not exist"
        )
        mine = self._envelope({"resolved": False})
        assert set(mine) == {"status", "data", "warnings"}
        # **The producer has TWO shapes and this test sees only one of them per
        # environment**, so the comparison branches explicitly rather than
        # assuming the `ok` one. `.prawduct/` caches are gitignored: the
        # maintainer's machine has a synced cache and answers `ok`, a fresh
        # clone and CI answer `error`. `set(mine) <= set(real)` held on the
        # first and failed on the second, which is how this went green for
        # months and red on its first CI run. Each branch asserts something,
        # so neither is a silent skip.
        if real["status"] == "ok":
            assert "data" in real, real
            assert set(mine) <= set(real) | {"warnings"}
        else:
            assert "error" in real, real
            assert "data" not in real, (
                "an error envelope must not carry `data` — the section reads "
                "`data` only after checking `status`, and a producer that sent "
                "both would make that check meaningless"
            )

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
        section = pr_payload._section_backlog(tmp_path, "owner/repo", [_claimed("ABC-1111"), _claimed("ABC-2222")])
        assert section.ok, "a partial result is still a result"
        assert "ABC-1111: status=open" in section.body
        assert "NOT ANSWERED for: ABC-2222" in section.body

    def test_every_lookup_failing_degrades_the_whole_section(self, monkeypatch, tmp_path):
        import lib.backlog.cachequery as cq

        def _resolve(*a, **k):
            raise RuntimeError("cache is gone")

        monkeypatch.setattr(cq, "resolve", _resolve)
        section = pr_payload._section_backlog(tmp_path, "owner/repo", [_claimed("ABC-1111")])
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
        section = pr_payload._section_backlog(tmp_path, "owner/repo", [_claimed("ABC-1111")])
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
        section = pr_payload._section_backlog(tmp_path, "owner/repo", [_claimed("ABC-1111")])
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


class TestTheCommitBodyReachesTheIdScan:
    """R-2's other input: a commit MESSAGE, not a commit subject.

    `_section_commits` renders `--oneline` because that is what the narrative
    goal reads, and the id scan was handed that rendering — so a citation in a
    commit body was invisible. That is the ordinary case, not the exotic one:
    across 120 commits on this repo's own integration branch a backlog `#N`
    appears on 69 body lines against 15 subject lines.

    The two assertions are a pair by design. The body id must be FOUND, and the
    `--oneline` section must stay a rendering rather than quietly becoming the
    scan set's carrier — a fix that simply widened the section would pass the
    first and dissolve the separation the second pins.
    """

    def _repo_citing_in_a_commit_body(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        (repo / "widget.py").write_text("# the widget\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm",
             "feat(widget): the widget thing\n\nA body paragraph.\n\nresolves #4242\n")
        return repo

    def test_an_id_in_a_commit_body_is_scanned(self, tmp_path):
        repo = self._repo_citing_in_a_commit_body(tmp_path)
        sections = _sections(repo)
        haystack = (sections["backlog"]["degraded"] or "") + (sections["backlog"]["body"] or "")
        assert "4242" in haystack, (
            "an id written in a commit's body never reached the id scan — the "
            "scan read `git log --oneline`, which is subjects only"
        )

    def test_the_commits_section_stays_a_rendering(self, tmp_path):
        """The subject line is what the narrative goal reads; the body belongs
        to the scan and nowhere else. If the trailer shows up here, the section
        became `--format=%B` and the reviewer pays for the whole log."""
        repo = self._repo_citing_in_a_commit_body(tmp_path)
        sections = _sections(repo)
        commits = sections["commits"]["body"]
        assert "the widget thing" in commits
        assert "A body paragraph." not in commits, (
            "the commits section is `--oneline` by design — widening IT is not "
            "the fix for the scan set"
        )


class TestAnUnscannedInputIsNeverAnAnswer:
    """The backlog id set has two inputs — the commit messages and the branch's
    change-log entry — and "no ids cited" is an ANSWER only when both were read.

    It used to be claimed over whatever arrived: each input degraded to `""`
    when it could not be read, so an empty set from an unread input rendered as
    *"R-2 has nothing to check (this is an answer, not a failure)"*. The
    ordinary trigger was not a git failure but a branch no build plan claims —
    a docs or fix branch — whose change-log section degraded for want of a
    scope, so every id the entry cited was invisible. Found on a real PR whose
    entry cited two ids the payload reported as none.
    """

    def _scopeless_repo_adding_an_entry(self, tmp_path: Path) -> Path:
        """No plan claims the branch; the branch ADDS a change-log entry citing
        an id, and the base's entry cites another the branch did not write."""
        repo = _repo(tmp_path, with_plan=False)
        _git(repo, "commit", "-q", "--amend", "-m", "docs: the widget note")
        log = repo / ".prawduct" / "change-log.md"
        log.write_text(
            "# Change Log\n\n"
            "## The widget note\n"
            "<!-- prawduct: type=docs | scope=widget-note -->\n\n"
            "Measures the thing #4242 is about.\n\n"
            + log.read_text().split("\n", 2)[2].replace(
                "It does the widget thing.", "It does the widget thing, per #9999."
            )
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "docs: change log")
        return repo

    def test_a_scopeless_branch_carries_the_entry_it_adds(self, tmp_path):
        section = _sections(self._scopeless_repo_adding_an_entry(tmp_path))["change_log"]
        assert section["ok"] is True, section["degraded"]
        assert "Measures the thing #4242" in section["body"]
        assert "no build plan claims this branch" in section["body"], (
            "the reviewer is owed HOW the entry was paired, since it was not by scope"
        )

    def test_a_scopeless_branch_scans_the_entry_it_adds(self, tmp_path):
        """The reported defect, end to end: the entry's id reaches R-2's set."""
        backlog = _sections(self._scopeless_repo_adding_an_entry(tmp_path))["backlog"]
        haystack = (backlog["degraded"] or "") + (backlog["body"] or "")
        assert "4242" in haystack, (
            "the id the branch's own change-log entry cites never reached R-2"
        )
        assert "no backlog ids cited" not in haystack

    def test_an_entry_the_branch_did_not_add_is_not_carried(self, tmp_path):
        """The bound that keeps diff-pairing from becoming the whole log: the
        base's entry is someone else's release note, and its id is not this
        branch's claim."""
        sections = _sections(self._scopeless_repo_adding_an_entry(tmp_path))
        assert "It does the widget thing" not in sections["change_log"]["body"]
        backlog = sections["backlog"]
        assert "9999" not in (backlog["degraded"] or "") + (backlog["body"] or "")

    def test_a_scopeless_branch_adding_no_entry_is_an_answer(self, tmp_path):
        """The diff was read and adds nothing — that is the finding, and it is
        a read that succeeded, so it must not degrade."""
        section = _sections(_repo(tmp_path, with_plan=False))["change_log"]
        assert section["ok"] is True, section["degraded"]
        assert "adds no change-log entry" in section["body"]

    def test_an_unreadable_entry_makes_an_empty_set_a_degradation(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "commit", "-q", "--amend", "-m", "feat(widget): the widget thing")
        (repo / ".prawduct" / "change-log.md").unlink()
        backlog = _sections(repo)["backlog"]
        assert backlog["ok"] is False, (
            "no ids found in an entry nobody could read is not 'nothing cited'"
        )
        assert "change-log entry" in backlog["degraded"]
        assert "R-2 is NOT answered" in backlog["degraded"]

    def test_an_unreadable_commit_log_makes_an_empty_set_a_degradation(self, tmp_path):
        section = pr_payload._section_backlog(
            tmp_path, "owner/repo", [], unscanned=["the commit messages"]
        )
        assert not section.ok
        assert "the commit messages" in section.degraded

    def test_a_partial_scan_says_what_it_did_not_see(self, monkeypatch, tmp_path):
        """Ids found in one input are still reported — but a short list must not
        read as the whole set when the other input went unread."""
        import lib.backlog.cachequery as cq

        monkeypatch.setattr(cq, "resolve", lambda *a, **k: TestDegradations._envelope(
            {"resolved": True, "status": "open", "dead": False, "title": "a thing"}
        ))
        section = pr_payload._section_backlog(
            tmp_path, "owner/repo", [_claimed("ABC-1111")],
            unscanned=["the change-log entry"],
        )
        assert section.ok
        assert "ABC-1111: status=open" in section.body
        assert "NOT SCANNED: the change-log entry" in section.body

    def test_a_failed_commit_read_reaches_the_backlog_section(self, monkeypatch, tmp_path):
        """The wiring, not just the helper: `assemble` must hand an unread
        commit log to the backlog section as unscanned. The fixture's entry is
        readable and cites nothing, so the commit messages are the only input
        that can make this degrade."""
        repo = _repo(tmp_path)
        _git(repo, "commit", "-q", "--amend", "-m", "feat(widget): the widget thing")
        monkeypatch.setattr(pr_payload, "_commit_bodies", lambda *a, **k: None)
        sections, failure = pr_payload.assemble(repo)
        assert failure is None
        backlog = {s.name: s for s in sections}["backlog"]
        assert not backlog.ok, "an unread commit log was reported as 'nothing cited'"
        assert "the commit messages" in backlog.degraded

    def test_a_failed_commit_read_is_named_not_emptied(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pr_payload, "_git", lambda *a, **k: (128, ""))
        assert pr_payload._commit_bodies(tmp_path, "develop") is None


class TestTheSilentDegradationIsCoupledToALoudOne:
    """The scan and the commits section must ask about the SAME range.

    A failed scan read is named to the backlog section as an unscanned input
    (`TestAnUnscannedInputIsNeverAnAnswer`), so it no longer depends on this
    coupling to be seen. The coupling still matters on the success path: two
    reads over different ranges would hand the reviewer a commit list and a
    citation set describing different intervals, and both would look healthy.
    The two calls are near-identical enough that a file-wide mutation restore
    once rewrote the wrong one of the pair, so this is checked, not stated.
    """

    def _ranges(self, monkeypatch, tmp_path) -> dict[str, list[tuple[str, ...]]]:
        """Every `git log` invocation each function issues, by caller."""
        calls: list[tuple[str, ...]] = []
        real_git = pr_payload._git

        def _recording(project_dir, *args):
            if args and args[0] == "log":
                calls.append(args)
            return real_git(project_dir, *args)

        monkeypatch.setattr(pr_payload, "_git", _recording)
        repo = _repo(tmp_path)
        base, _ = pr_payload._lib().coverage._resolve_base_branch(repo)
        calls.clear()
        pr_payload._section_commits(repo, base)
        section = list(calls)
        calls.clear()
        pr_payload._commit_bodies(repo, base)
        return {"section": section, "bodies": list(calls)}

    def test_both_reads_cover_the_same_range(self, monkeypatch, tmp_path):
        seen = self._ranges(monkeypatch, tmp_path)
        assert len(seen["section"]) == 1 and len(seen["bodies"]) == 1, seen
        assert seen["section"][0][-1] == seen["bodies"][0][-1], (
            "the scan and the commits section no longer ask about the same "
            f"range ({seen}) — the citation set and the commit list the reviewer "
            "reads would describe different intervals, and both would look healthy"
        )

    def test_they_differ_only_in_the_format(self, monkeypatch, tmp_path):
        """The control for the assertion above: same range is worth asserting
        only because the two calls are otherwise NOT identical — one renders,
        one scans. Without this, `_commit_bodies` could be made a second
        `--oneline` read and the coupling test would still pass."""
        seen = self._ranges(monkeypatch, tmp_path)
        assert "--oneline" in seen["section"][0]
        assert "--format=%B" in seen["bodies"][0]


class TestThePayloadCanBeAimedAtATree:
    """The command's own premise is that its reader cannot trust its cwd.

    `agents/pr-reviewer.md` states it ("a relative path here resolves into the
    primary checkout — a different tree ... which reviews clean") and mandates
    `git -C <dir>` for every git read; the payload then had no way to be told
    which tree at all, and the reviewer's allow-list grants no `cd`. The named
    mitigation — compare the payload's `base` against the prompt's base — cannot
    discriminate, because both trees in a gitflow repo answer `develop`.
    """

    def test_a_directory_argument_aims_the_read(self, tmp_path):
        """Run from a DIFFERENT cwd and assert the answer is about the argument.
        `_run` pins `CLAUDE_PROJECT_DIR` and cwd to the fixture, which is exactly
        why no existing test could reach this path."""
        target = _repo(tmp_path / "target")
        elsewhere = _repo(tmp_path / "elsewhere")
        r = _run(elsewhere, "--json", str(target))
        assert r.returncode == 0, r.stderr
        base = {x["name"]: x for x in json.loads(r.stdout)["sections"]}["base"]
        assert str(target.resolve()) in base["body"], base

    def test_without_the_argument_it_answers_about_its_own_tree(self, tmp_path):
        """The control: the positional must not become the only way to get an
        answer, and it must not leak the previous case's directory."""
        here = _repo(tmp_path / "here")
        r = _run(here, "--json")
        assert r.returncode == 0, r.stderr
        base = {x["name"]: x for x in json.loads(r.stdout)["sections"]}["base"]
        assert str(here.resolve()) in base["body"], base

    def test_the_base_section_names_the_tree_it_answered_about(self, tmp_path):
        """The discriminator the base BRANCH cannot be: a worktree and its
        primary checkout both resolve the same base name."""
        repo = _repo(tmp_path)
        base = _sections(repo)["base"]["body"]
        assert "project dir:" in base
        assert "HEAD:" in base
        assert "different tree than the caller thinks" in base

    def test_a_directory_that_is_not_a_project_is_refused_not_guessed(self, tmp_path):
        """Hard failure, deliberately: a degraded section here would answer about
        the wrong tree, which is the silent pass the argument exists to stop."""
        empty = tmp_path / "not-a-repo"
        empty.mkdir()
        r = _run(_repo(tmp_path / "real"), str(empty))
        assert r.returncode == 1
        assert "is not a project directory" in r.stderr


class TestAnAnswerIsNotADegradation:
    """The module says it three times — "NOT a degradation: an empty range is a
    real, reviewable answer", "An absent block is therefore an ANSWER", "this is
    an answer, not a failure" — and the change-log section broke its own rule.

    The cost is not cosmetic: `render_human`'s banner says "N of M sections
    degraded — each says which of your checks it leaves unanswered", which is
    false of a healthy read with a negative result, and `--json` consumers read
    `ok: false` for it. The pair below is the point — the answer case must be a
    body AND the genuinely-unreadable case must still degrade, or "fix" here
    just means "never degrade".
    """

    def _repo_with_a_log_naming_another_scope(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## Something else\n<!-- prawduct: scope=elsewhere -->\n\n"
            "Not this bundle.\n"
        )
        return repo

    def test_no_entry_for_this_scope_is_an_answer(self, tmp_path):
        section = _sections(self._repo_with_a_log_naming_another_scope(tmp_path))["change_log"]
        assert section["ok"] is True, (
            "a parsed log that simply has no entry for this scope is a READ that "
            "succeeded — the missing entry is the finding, not a failure to look"
        )
        assert "ships with nothing describing it" in section["body"]

    def test_an_unreadable_log_still_degrades(self, tmp_path):
        """The control. Without it, `ok is True` above is satisfied by a section
        that never degrades at all."""
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "change-log.md").unlink()
        section = _sections(repo)["change_log"]
        assert section["ok"] is False
        assert section["degraded"]


class TestTheCitationFormReachesTheSection:
    """R-2 asks whether a commit CLAIMED a closure the backlog does not show —
    not whether an id appears somewhere.

    Widening the scan to commit BODIES is what made this load-bearing: bodies
    discuss ids as context far more than they claim closures, and an id list with
    the form stripped renders every mention as `STILL OPEN`. A reviewer applying
    R-2 literally then files a closure-that-never-happened against work nobody
    claimed to close — or re-reads `git log` to find out, which is the round-trip
    this command exists to remove.
    """

    def test_a_closing_keyword_marks_the_citation_as_a_claim(self):
        cited = pr_payload.cited_backlog_citations("fix(x): closes #41", "")
        assert [(c.id, c.claims_closure) for c in cited] == [("41", True)]

    def test_a_mere_mention_is_not_a_claim(self):
        """The discriminating case, and the one this bundle's own commits are:
        an id discussed as context carries no closing keyword."""
        cited = pr_payload.cited_backlog_citations(
            "the open question from #672 is whether the tree snapshot is voided", ""
        )
        assert [(c.id, c.claims_closure) for c in cited] == [("672", False)]

    def test_a_claim_anywhere_wins_over_a_mention(self):
        """One id, cited twice — discussed in one commit, closed in another.
        R-2's question is whether the branch claimed it, so any claim wins; the
        opposite order must give the same answer."""
        mention_first = pr_payload.cited_backlog_citations(
            "context for #41\nfix: closes #41", ""
        )
        claim_first = pr_payload.cited_backlog_citations(
            "fix: closes #41\ncontext for #41", ""
        )
        assert [(c.id, c.claims_closure) for c in mention_first] == [("41", True)]
        assert [(c.id, c.claims_closure) for c in claim_first] == [("41", True)]

    def test_a_keyword_bearing_citation_with_no_hash_is_a_claim(self):
        """The case the first implementation inverted, and the reason the answer
        is derived from a claim REGION rather than a lookback.

        `_ID_PATTERNS[2]` BEGINS at the closing keyword, so "the text before this
        match" stops one character short of the word that proves the claim. With
        a `#` present the bare-`#N` pattern re-matched the number and the
        any-claim-wins upgrade hid it; remove the `#` and the citation renders as
        `mentioned only — no closing keyword` on text that literally reads
        `closes:`. That is `review-protocol.md`'s R-2 predicate inverted, on the
        check it assigns to no other layer.
        """
        cited = pr_payload.cited_backlog_citations("fix(x): closes: 678", "")
        assert [(c.id, c.claims_closure) for c in cited] == [("678", True)]

    def test_every_id_in_a_run_shares_the_claim(self):
        """Second member of the same class: only the FIRST id of a run follows
        the keyword directly. Every later one is preceded by its siblings, which
        no fixed lookback can cross."""
        cited = pr_payload.cited_backlog_citations("fix: closes #41 and BKL-9V2W", "")
        assert {(c.id, c.claims_closure) for c in cited} == {
            ("41", True), ("BKL-9V2W", True),
        }
        commas = pr_payload.cited_backlog_citations("closed-by: a/b#7, #8", "")
        assert {(c.id, c.claims_closure) for c in commas} == {
            ("a/b#7", True), ("8", True),
        }

    def test_the_run_ends_at_prose_rather_than_swallowing_the_sentence(self):
        """The control for both tests above, and the failure mode a region-based
        answer could have instead of a lookback's: a region bounded too loosely
        marks every id after a claim as claimed. `#999` here is discussed, not
        closed, and the two must come apart in ONE fixture."""
        cited = pr_payload.cited_backlog_citations(
            "resolves 678 and then we discuss #999 separately", ""
        )
        assert [(c.id, c.claims_closure) for c in cited] == [("678", True), ("999", False)]

    def test_the_section_says_which_it_is(self, tmp_path, monkeypatch):
        """Both renderings, in one assertion pair — a test of only the claim
        branch would pass with the form hard-coded."""
        import lib.backlog.cachequery as cq

        def _resolve(project_dir, *, scope, id_raw, now, default_owner=None):
            return TestDegradations._envelope(
                {"resolved": True, "status": "open", "dead": False, "title": "a thing"}
            )

        monkeypatch.setattr(cq, "resolve", _resolve)
        claimed = pr_payload._section_backlog(
            tmp_path, "owner/repo", [pr_payload.Citation("41", True)]
        )
        mentioned = pr_payload._section_backlog(
            tmp_path, "owner/repo", [pr_payload.Citation("41", False)]
        )
        assert "CLAIMS this closure" in claimed.body
        assert "R-2 does not apply" not in claimed.body
        assert "R-2 does not apply" in mentioned.body
        assert "CLAIMS this closure" not in mentioned.body

    def test_an_unresolved_token_does_not_assert_it_was_ever_an_id(self, tmp_path, monkeypatch):
        """`_ID_PATTERNS[0]` matches any `AAA-9999` token, so `ISO-8601` in a
        commit body reaches the lookup. Rendering that as "a dangling citation"
        invites a finding about an id that never existed, on the one check
        nothing else in the pipeline owns."""
        import lib.backlog.cachequery as cq

        monkeypatch.setattr(
            cq, "resolve",
            lambda *a, **k: TestDegradations._envelope({"resolved": False}),
        )
        section = pr_payload._section_backlog(
            tmp_path, "owner/repo", [pr_payload.Citation("ISO-8601", False)]
        )
        assert "or not an id at all" in section.body
        assert "check the citing text before filing" in section.body


class TestTheWorkSectionNeverFabricatesABranch:
    """`briefing._get_current_branch` returns the STRING "main" on git failure or
    a detached HEAD — a display default for the briefing, and a fabrication in
    the one command whose contract is that an absent answer is always named.

    The damage is not the printed word: `_parse_wip` keys off it, so a repo with
    a `main:` block under `work_in_progress:` hands the reviewer ANOTHER branch's
    description, size and type as this PR's stated scope — the operand Goal 1
    grades the diff against — and the section never degrades, because a
    description IS present.
    """

    def _repo_with_a_main_wip_block(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        state = repo / ".prawduct" / "project-state.yaml"
        state.write_text(
            state.read_text()
            + "\nwork_in_progress:\n  main:\n    description: SOMEBODY ELSE'S WORK\n"
              "    size: large\n    type: feature\n"
        )
        return repo

    def test_an_unreadable_branch_is_named_not_guessed(self, tmp_path, monkeypatch):
        repo = self._repo_with_a_main_wip_block(tmp_path)
        monkeypatch.setattr(pr_payload._lib().gitstate, "current_branch", lambda _d: None)
        section = pr_payload._section_work(repo, repo / ".prawduct", None)
        rendered = (section.body or "") + (section.degraded or "")
        assert "could not be read" in rendered, rendered
        assert "SOMEBODY ELSE'S WORK" not in rendered, (
            "a failed branch read reached `_parse_wip` as a branch NAME and "
            "matched another branch's work block"
        )
        assert "branch: main" not in rendered

    def test_a_readable_branch_still_resolves_its_own_work(self, tmp_path, monkeypatch):
        """The control: the guard must not blank out the healthy path."""
        repo = self._repo_with_a_main_wip_block(tmp_path)
        monkeypatch.setattr(pr_payload._lib().gitstate, "current_branch", lambda _d: "main")
        section = pr_payload._section_work(repo, repo / ".prawduct", None)
        assert "SOMEBODY ELSE'S WORK" in (section.body or "")
        assert "could not be read" not in (section.body or "")


class TestBacklogIdExtraction:
    """`cited_backlog_citations` is R-2's input set: a change-log entry or a commit
    that CLAIMS a closure."""

    def test_both_id_spellings_are_found(self):
        cited = pr_payload.cited_backlog_citations(
            "abc1234 fix(thing): closes: #41 and BKL-9V2W", ""
        )
        assert [c.id for c in cited] == ["BKL-9V2W", "41"]

    def test_ids_are_deduped_in_first_seen_order(self):
        cited = pr_payload.cited_backlog_citations(
            "BKL-9V2W once", "BKL-9V2W again, and ABC-1A2B"
        )
        assert [c.id for c in cited] == ["BKL-9V2W", "ABC-1A2B"]

    def test_a_bare_number_after_a_slash_is_not_a_citation(self):
        """Red if the `#N` pattern stops requiring the `#`. `refs/pull/12` is a
        path, not a citation."""
        assert pr_payload.cited_backlog_citations("see refs/pull/12 for context", "") == []

    def test_a_qualified_citation_is_captured_whole_and_only_once(self):
        """The lookbehind's actual job, and the case that discriminates it.

        `owner/repo#249` is a spelling `cachequery.resolve` accepts. Captured
        whole it resolves to the item it names; capture the trailing number as
        well and the SAME citation is looked up twice, the second time as a bare
        `#249` in whatever repo the cache defaults to — a different item. Drop
        the lookbehind and this returns both.
        """
        cited = pr_payload.cited_backlog_citations("fix: closes owner/repo#249", "")
        assert [c.id for c in cited] == ["owner/repo#249"]

    def test_a_qualified_and_a_bare_citation_both_survive(self):
        """Paired positive: the lookbehind must not swallow a genuine bare `#N`
        that merely shares a line with a qualified one."""
        cited = pr_payload.cited_backlog_citations("a/b#7 supersedes #8", "")
        assert [c.id for c in cited] == ["a/b#7", "8"]

    def test_nothing_cited_is_an_empty_list_not_a_guess(self):
        assert pr_payload.cited_backlog_citations("abc1234 chore: tidy up", "") == []


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



class TestLearningsCapSection:
    """An owner-approved core.md raise is visible at the PR boundary, because
    `owner_approved:` is text an agent can write. Red if the section stops
    naming a changed cap."""

    def test_a_cap_changed_on_the_base_after_the_fork_is_not_this_branchs(self, tmp_path):
        """Red if the comparison uses the base branch's tip instead of the merge-base."""
        from lib import pr_payload as pp
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        state = repo / ".prawduct" / "project-state.yaml"
        state.write_text("x: 1\n")
        g = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo, check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("add", "-A"); g("commit", "-qm", "base")
        g("checkout", "-q", "-b", "feature"); g("commit", "-qm", "work", "--allow-empty")
        g("checkout", "-q", "main")
        state.write_text('x: 1\nlearnings_budgets:\n  core.md: {kb: 24, reason: "r", owner_approved: 2026-09-24}\n')
        g("add", "-A"); g("commit", "-qm", "raise on main")
        g("checkout", "-q", "feature")
        section = pp._section_learnings_cap(repo, repo / ".prawduct", "main")
        assert section.body == "this branch does not change core.md's cap"

    def test_an_unchanged_cap_says_so(self, tmp_path):
        from lib import pr_payload as pp
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        (repo / ".prawduct" / "project-state.yaml").write_text("x: 1\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b", "--allow-empty"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "s"], cwd=repo, check=True)
        section = pp._section_learnings_cap(repo, repo / ".prawduct", "HEAD")
        assert section.body == "this branch does not change core.md's cap"

    def test_a_raised_cap_names_the_change_and_the_ask(self, tmp_path):
        from lib import pr_payload as pp
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        state = repo / ".prawduct" / "project-state.yaml"
        state.write_text("x: 1\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], cwd=repo, check=True)
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        state.write_text('x: 1\nlearnings_budgets:\n  core.md: {kb: 24, reason: "r", owner_approved: 2026-09-24}\n')
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "raise"], cwd=repo, check=True)
        body = pp._section_learnings_cap(repo, repo / ".prawduct", base).body
        assert "RISES on this branch" in body and "2026-09-24" in body and "quoted in the PR description" in body
        assert "reason" not in body

    def test_no_merge_base_degrades_and_names_what_to_read(self, tmp_path):
        """An unrelated base has no merge-base, so the section cannot compare.
        It must degrade (an unanswered check is not a passed one) and tell the
        reviewer where to look by hand."""
        from lib import pr_payload as pp
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        (repo / ".prawduct" / "project-state.yaml").write_text("x: 1\n")
        g = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo, check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("add", "-A"); g("commit", "-qm", "base")
        g("checkout", "-q", "--orphan", "unrelated"); g("commit", "-qm", "other root")
        section = pp._section_learnings_cap(repo, repo / ".prawduct", "main")
        assert section.degraded and "learnings_budgets.core.md" in section.degraded
        assert not section.body

    def test_a_removed_cap_is_not_called_a_raise(self, tmp_path):
        """Compacting a corpus drops its old override. The cap in force falls to
        the default, so the section must not ask for the owner's approval."""
        from lib import pr_payload as pp
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        state = repo / ".prawduct" / "project-state.yaml"
        state.write_text('x: 1\nlearnings_budgets:\n  core.md: {kb: 105, reason: "legacy", owner_approved: 2026-09-01}\n')
        g = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo, check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("add", "-A"); g("commit", "-qm", "base")
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        state.write_text("x: 1\n")
        g("add", "-A"); g("commit", "-qm", "compact")
        body = pp._section_learnings_cap(repo, repo / ".prawduct", base).body
        assert "does not rise" in body and "105KB -> 12KB" in body
        assert "quoted in the PR description" not in body and "legacy" not in body
