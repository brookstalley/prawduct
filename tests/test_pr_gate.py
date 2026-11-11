"""Tests for the PR gate commands — ``check-pr-hygiene`` and ``check-pr-body``.

Both are read-only gates the `/prawduct:pr` flow runs by command. Each test
names the input that must trip it, and the fixture is built so that input is
the only thing between a pass and the result asserted: a guard test whose
fixture cannot reach the guard passes forever.

The PR template layouts below are built from GitHub's documented rules (read
2026-11-11, recorded in the build plan's Constraints): one
``pull_request_template`` in the root, ``docs/`` or ``.github/``, the filename
case-insensitive and taking an extension such as ``.md`` or ``.txt``; several
templates in a ``PULL_REQUEST_TEMPLATE/`` subdirectory of any of those.
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
from lib import evidence, pr_gate  # noqa: E402


# --- fixtures ---------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, env=env, timeout=30
    )


def _fragment(scope: str, closes: list[str]) -> str:
    closes_line = f"closes: [{', '.join(closes)}]\n" if closes else ""
    return (
        "---\n"
        "schema: 1\n"
        "type: feature\n"
        f"scope: {scope}\n"
        "date: 2026-11-11\n"
        "title: the widget arrives\n"
        f"{closes_line}"
        "---\n"
        "The widget arrives.\n\n"
        "## Consumer note\n"
        "none: internal\n"
    )


def _repo(
    tmp_path: Path,
    *,
    base_branch: str = "develop",
    state_extra: str = "",
    backlog: str | None = None,
    closes: list[str] | None = None,
    branch_files: dict[str, str] | None = None,
) -> Path:
    """A governed repo: ``develop`` carries the base, ``feat/widget`` one commit.

    ``closes`` writes the branch's change fragment; ``backlog`` the markdown
    backlog at the base; ``branch_files`` anything else the branch adds.
    """
    repo = tmp_path / "repo"
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "develop")
    (repo / "app.py").write_text("print(1)\n")
    (repo / ".prawduct" / "project-state.yaml").write_text(
        f"project_name: fixture\nbase_branch: {base_branch}\n{state_extra}"
    )
    if backlog is not None:
        (repo / ".prawduct" / "backlog.md").write_text(backlog)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", "feat/widget")
    (repo / "app.py").write_text("print(2)\n")
    if closes is not None:
        (repo / ".prawduct" / "changes").mkdir(exist_ok=True)
        (repo / ".prawduct" / "changes" / "widget.md").write_text(_fragment("widget", closes))
    for rel, text in (branch_files or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat(widget): the widget thing")
    return repo


def _run(repo: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(cwd or repo), capture_output=True, text=True, env=env, timeout=60,
    )


def _refusals(repo: Path, guard: str) -> list[dict]:
    read = evidence.read_facts(repo)
    return [
        f for f in evidence.facts_of_kind(read, "guard-refusal")
        if (f.get("body") or {}).get("guard") == guard
    ]


BACKLOG = (
    "# Backlog\n\n"
    "## Open\n\n"
    "- **[BKL-0PEN]** A thing still to do\n"
    "  `effort: S · impact: S · area: core · source: builder · added: 2026-11-01 · status: open`\n\n"
    "## Archive\n\n"
    "- **[BKL-D0NE]** A thing already done\n"
    "  `effort: S · impact: S · area: core · source: builder · added: 2026-11-01 · status: done`\n"
)


# --- check-pr-hygiene: answering at all --------------------------------------


class TestHygieneAnswers:
    def test_an_unresolvable_base_exits_3(self, tmp_path):
        """Input that trips it: `base_branch:` names a branch no ref resolves.
        No base means no interval, so nothing can be answered."""
        repo = _repo(tmp_path, base_branch="no-such-branch")
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 3, (r.stdout, r.stderr)
        assert "could not answer" in r.stderr
        assert "base" in r.stderr

    def test_an_unresolvable_base_exits_3_under_json_too(self, tmp_path):
        repo = _repo(tmp_path, base_branch="no-such-branch")
        r = _run(repo, "check-pr-hygiene", "--json")
        assert r.returncode == 3
        data = json.loads(r.stdout)
        assert data["exit"] == 3 and data["error"]

    def test_a_clean_branch_prints_one_line(self, tmp_path):
        """The control: same fixture, nothing for any result to find."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=[])
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert len(r.stdout.strip().splitlines()) == 1, r.stdout
        assert "nothing to report" in r.stdout

    def test_an_unknown_argument_is_a_usage_error(self, tmp_path):
        repo = _repo(tmp_path)
        r = _run(repo, "check-pr-hygiene", "--nope")
        assert r.returncode == 2
        assert "--nope" in r.stderr


# --- check-pr-hygiene: the closure check -------------------------------------


class TestClosuresMarkdownBackend:
    def test_an_id_the_backlog_does_not_know_warns(self, tmp_path):
        """Input that trips it: `closes: [BKL-GH0S]`, an id in neither file."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=["BKL-GH0S"])
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0, r.stderr
        assert "closes-unresolved" in r.stdout
        assert "BKL-GH0S" in r.stdout

    def test_a_warning_lands_one_fact_and_a_rerun_lands_none(self, tmp_path):
        """Input that trips it: `closes: [BKL-GH0S]`. A warning's yield is a
        query like a refusal's: one `guard-refusal` fact under `pr-hygiene`
        with the result's name as the reason, the same event on a re-run of
        the unchanged branch."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=["BKL-GH0S"])
        assert _run(repo, "check-pr-hygiene").returncode == 0
        facts = _refusals(repo, pr_gate.HYGIENE_GUARD)
        assert len(facts) == 1, facts
        assert facts[0]["body"]["reason"] == "closes-unresolved"
        assert facts[0]["body"]["results"] == {"closes-unresolved": ["BKL-GH0S"]}
        assert _run(repo, "check-pr-hygiene").returncode == 0
        assert len(_refusals(repo, pr_gate.HYGIENE_GUARD)) == 1

    def test_a_clean_branch_and_an_unchecked_warning_land_no_fact(self, tmp_path):
        """Controls: nothing found records nothing, and a closure check that
        could not look (no backlog file) found nothing either."""
        clean = _repo(tmp_path / "clean", backlog=BACKLOG, closes=["BKL-D0NE"])
        assert _run(clean, "check-pr-hygiene").returncode == 0
        assert _refusals(clean, pr_gate.HYGIENE_GUARD) == []
        blind = _repo(tmp_path / "blind", closes=["BKL-0PEN"])
        r = _run(blind, "check-pr-hygiene")
        assert "unchecked" in r.stdout
        assert _refusals(blind, pr_gate.HYGIENE_GUARD) == []

    def test_information_results_land_no_fact(self, tmp_path, monkeypatch):
        """`chunks-open` and the rest are not a control firing."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=[])
        monkeypatch.setattr(pr_gate, "_chunks_open", lambda _d: [
            pr_gate.Result("chunks-open", pr_gate.INFO, ["Chunk 02: x"])])
        assert pr_gate.hygiene_cmd(repo, []) == 0
        assert _refusals(repo, pr_gate.HYGIENE_GUARD) == []

    def test_an_id_still_open_warns(self, tmp_path):
        """Input that trips it: `closes: [BKL-0PEN]`, an item under `## Open`
        on the branch's own backlog — the archive rides the branch, so a close
        the branch claims should have moved it."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=["BKL-0PEN"])
        r = _run(repo, "check-pr-hygiene", "--json")
        assert r.returncode == 0, r.stderr
        results = {res["name"]: res for res in json.loads(r.stdout)["results"]}
        assert "closes-still-open" in results, results
        assert any("BKL-0PEN" in item for item in results["closes-still-open"]["items"])
        assert results["closes-still-open"]["severity"] == "warning"

    def test_an_archived_id_is_a_clean_close(self, tmp_path):
        """The control for both above: the archived item reports nothing."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=["BKL-D0NE"])
        r = _run(repo, "check-pr-hygiene", "--json")
        data = json.loads(r.stdout)
        assert data["results"] == [], data

    def test_an_issue_id_on_a_markdown_backend_is_unchecked_not_clean(self, tmp_path):
        """The markdown backlog cannot say whether a GitHub issue is open; saying
        nothing would read as reconciled."""
        repo = _repo(tmp_path, backlog=BACKLOG, closes=["owner/repo#41"])
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0
        assert "unchecked" in r.stdout and "owner/repo#41" in r.stdout

    def test_no_backlog_file_is_unchecked_not_clean(self, tmp_path):
        repo = _repo(tmp_path, closes=["BKL-0PEN"])
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0
        assert "unchecked" in r.stdout
        assert "nothing to report" not in r.stdout

    def test_a_legacy_log_entry_is_unchecked_not_clean(self, tmp_path):
        """Input that trips it: the branch records its change only in the
        single-file log, which this check does not read."""
        repo = _repo(
            tmp_path,
            backlog=BACKLOG,
            branch_files={".prawduct/change-log.md": "# Change Log\n\n## 2026-11-11: x\n"},
        )
        r = _run(repo, "check-pr-hygiene")
        assert "unchecked" in r.stdout and "change-log.md" in r.stdout


class TestClosuresIssuesBackend:
    STATE = "backlog_service_repo: owner/repo\n"

    @staticmethod
    def _envelope(data: dict) -> dict:
        """The shape `cachequery.resolve` actually returns: `resolved` inside `data`."""
        return {"status": "ok", "data": data, "warnings": []}

    def _resolver(self, table: dict):
        def _resolve(project_dir, *, scope, id_raw, now, default_owner=None):
            assert scope == "owner/repo"
            return table[id_raw]
        return _resolve

    def test_an_open_id_is_owed_at_merge_and_an_unknown_one_warns(self, tmp_path, monkeypatch):
        """Inputs that trip it: `#41` resolves open (owed: GitHub closes it from
        the PR description), `#99` resolves to nothing (unresolved)."""
        import lib.backlog.cachequery as cq

        repo = _repo(tmp_path, state_extra=self.STATE, closes=["owner/repo#41", "owner/repo#99", "owner/repo#7"])
        monkeypatch.setattr(cq, "resolve", self._resolver({
            "owner/repo#41": self._envelope({"resolved": True, "dead": False, "status": "open", "title": "the widget"}),
            "owner/repo#99": self._envelope({"resolved": False, "reason": "not-found"}),
            "owner/repo#7": self._envelope({"resolved": True, "dead": True, "status": "closed"}),
        }))
        report = pr_gate.hygiene(repo)
        assert report.error is None, report.error
        results = {r.name: r for r in report.results}
        assert set(results) == {"close-owed-at-merge", "closes-unresolved"}, results
        assert results["close-owed-at-merge"].severity == "information"
        assert any("owner/repo#41" in i for i in results["close-owed-at-merge"].items)
        assert not any("#7" in i for i in results["close-owed-at-merge"].items)
        assert any("owner/repo#99" in i for i in results["closes-unresolved"].items)
        # Never the markdown-only result on this backend.
        assert "closes-still-open" not in results
        assert pr_gate.hygiene_exit(report) == 0

    def test_a_cache_that_cannot_answer_is_unchecked_not_clean(self, tmp_path, monkeypatch):
        import lib.backlog.cachequery as cq

        repo = _repo(tmp_path, state_extra=self.STATE, closes=["owner/repo#41"])
        monkeypatch.setattr(cq, "resolve", self._resolver({
            "owner/repo#41": {"status": "error", "error": {"code": "no-cache", "message": "no cache"}},
        }))
        report = pr_gate.hygiene(repo)
        unchecked = [r for r in report.results if r.unchecked]
        assert unchecked, report.results
        assert "owner/repo#41" in unchecked[0].unchecked and "no cache" in unchecked[0].unchecked


# --- check-pr-hygiene: chunks and review attestations ------------------------


PLAN = (
    "---\n"
    "artifact: build-plan\n"
    "scope: widget\n"
    "branch: feat/widget\n"
    "---\n\n"
    "## Build Chunks\n\n"
    "### Chunk 01: the first one\n\n"
    "### Chunk 02: the second one\n"
)


class TestChunksOpen:
    def test_a_bound_plans_open_chunks_are_listed(self, tmp_path):
        """Input that trips it: a plan claiming this branch with chunks no fact
        has certified."""
        repo = _repo(tmp_path, branch_files={".prawduct/artifacts/build-plan-widget.md": PLAN})
        r = _run(repo, "check-pr-hygiene", "--json")
        assert r.returncode == 0, r.stderr
        results = {res["name"]: res for res in json.loads(r.stdout)["results"]}
        assert "chunks-open" in results, results
        items = " ".join(results["chunks-open"]["items"])
        assert "01" in items and "02" in items

    def test_an_unbound_branch_prints_nothing_for_chunks(self, tmp_path):
        """The control: the same branch with no plan claiming it."""
        repo = _repo(tmp_path)
        data = json.loads(_run(repo, "check-pr-hygiene", "--json").stdout)
        assert all(res["name"] != "chunks-open" for res in data["results"]), data


class TestReviewTreeChanged:
    def test_a_review_consolidated_over_a_changed_tree_is_listed(self, tmp_path, monkeypatch):
        """Input that trips it: a review on the composed coverage path whose
        fact carries the builder's tree-changed attestation."""
        from lib import critic_consolidate, gates

        repo = _repo(tmp_path)
        monkeypatch.setattr(gates, "branch_coverage_verdict", lambda _d, **_k: {
            "status": "covered",
            "verdict": {"path": [{"kind": "review", "id": "rev-1"}, {"kind": "review", "id": "rev-2"}]},
        })
        monkeypatch.setattr(evidence, "read_facts", lambda _d: {"facts": [
            {"kind": "review", "id": "rev-1", "body": {
                critic_consolidate.TREE_CHANGED_KEY: {"paths": ["app.py"], "reason": "my own fix"}}},
            {"kind": "review", "id": "rev-2", "body": {}},
            {"kind": "review", "id": "rev-off-path", "body": {
                critic_consolidate.TREE_CHANGED_KEY: {"paths": ["x.py"], "reason": "elsewhere"}}},
        ]})
        monkeypatch.setattr(evidence, "facts_of_kind", lambda read, kind: [
            f for f in read["facts"] if f["kind"] == kind
        ])
        result = pr_gate._review_tree_changed(repo)
        assert len(result) == 1 and result[0].name == "review-tree-changed"
        assert len(result[0].items) == 1
        assert "rev-1" in result[0].items[0] and "my own fix" in result[0].items[0]

    def test_an_unreadable_store_is_unchecked(self, tmp_path, monkeypatch):
        from lib import gates

        repo = _repo(tmp_path)

        def _boom(*_a, **_k):
            raise OSError("store gone")

        monkeypatch.setattr(gates, "branch_coverage_verdict", _boom)
        result = pr_gate._review_tree_changed(repo)
        assert result and result[0].unchecked and "store gone" in result[0].unchecked


# --- check-pr-body ----------------------------------------------------------


TEMPLATE = (
    "<!-- Describe the change. This comment is an instruction, not a section. -->\n"
    "## Summary\n\n"
    "<!--\n## Not a section either\n-->\n"
    "## Test plan\n\n"
    "```\n# a code comment, not a heading\n```\n\n"
    "- [ ] Tests added\n"
    "- [ ] Docs updated\n"
)

GOOD_BODY = (
    "##   Summary\n\nWidgets.\n\n"
    "## Test plan ##\n\nRan it.\n\n"
    "- [x] Tests added\n"
    "* [ ]   Docs   updated\n"
)


def _body_repo(tmp_path: Path, templates: dict[str, str] | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "develop")
    for rel, text in (templates or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    return repo


def _write_body(tmp_path: Path, text: str) -> Path:
    body = tmp_path / "body.md"
    body.write_text(text)
    return body


class TestPrBodyFollowsTheTemplate:
    def test_a_body_with_every_heading_and_item_exits_0(self, tmp_path):
        """Whitespace, closing hashes, bullet marker and checkbox state differ
        from the template and must not matter; the template's HTML comments and
        fenced code are not required."""
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, GOOD_BODY)))
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert len(r.stdout.strip().splitlines()) == 1, r.stdout
        assert ".github/pull_request_template.md" in r.stdout

    def test_a_body_missing_one_heading_exits_1_naming_it(self, tmp_path):
        """Input that trips it: the body drops `## Test plan`."""
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        body = GOOD_BODY.replace("## Test plan ##", "Testing:")
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "## Test plan" in r.stdout
        assert "## Summary" not in r.stdout.split("missing", 1)[-1]

    def test_a_body_missing_one_checklist_item_exits_1_naming_it(self, tmp_path):
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        body = GOOD_BODY.replace("* [ ]   Docs   updated\n", "")
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert r.returncode == 1
        assert "Docs updated" in r.stdout

    def test_a_checklist_item_written_as_prose_does_not_count(self, tmp_path):
        """Input that trips it: the item's text present, but not as a checkbox."""
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        body = GOOD_BODY.replace("* [ ]   Docs   updated\n", "Docs updated\n")
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert r.returncode == 1
        assert "Docs updated" in r.stdout

    def test_a_heading_hidden_in_a_body_comment_does_not_count(self, tmp_path):
        """Input that trips it: the body carries `## Test plan` only inside an
        HTML comment, which GitHub does not render. Multi-line, so the heading
        is a line of its own: a one-line `<!-- ## x -->` is no heading anyway,
        and would pass with the comment handling deleted."""
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        body = GOOD_BODY.replace("## Test plan ##", "<!--\n## Test plan\n-->")
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert r.returncode == 1
        assert "## Test plan" in r.stdout

    def test_a_refusal_lands_a_guard_refusal_fact(self, tmp_path):
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        body = GOOD_BODY.replace("## Test plan ##", "Testing:")
        assert _refusals(repo, pr_gate.BODY_GUARD) == []
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert r.returncode == 1
        facts = _refusals(repo, pr_gate.BODY_GUARD)
        assert len(facts) == 1, facts
        assert facts[0]["body"]["reason"] == "missing-template-lines"
        # Re-asking about the same body records the same event, not a second one.
        _run(repo, "check-pr-body", str(_write_body(tmp_path, body)))
        assert len(_refusals(repo, pr_gate.BODY_GUARD)) == 1

    def test_a_passing_body_records_no_refusal(self, tmp_path):
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        _run(repo, "check-pr-body", str(_write_body(tmp_path, GOOD_BODY)))
        assert _refusals(repo, pr_gate.BODY_GUARD) == []

    def test_an_unreadable_body_exits_3(self, tmp_path):
        repo = _body_repo(tmp_path, {".github/pull_request_template.md": TEMPLATE})
        r = _run(repo, "check-pr-body", str(tmp_path / "no-such-body.md"))
        assert r.returncode == 3, (r.stdout, r.stderr)
        assert "no-such-body.md" in r.stderr


class TestPrTemplateDiscovery:
    @pytest.mark.parametrize("rel", [
        "pull_request_template.md",
        "PULL_REQUEST_TEMPLATE.md",
        "docs/Pull_Request_Template.txt",
        ".github/pull_request_template",
        ".github/PULL_REQUEST_TEMPLATE.TXT",
    ])
    def test_a_template_in_each_location_and_spelling_is_found(self, tmp_path, rel):
        repo = _body_repo(tmp_path, {rel: TEMPLATE})
        assert [p.relative_to(repo).as_posix() for p in pr_gate.find_templates(repo)] == [rel]
        r = _run(repo, "check-pr-body")
        assert r.returncode == 0
        assert rel in r.stdout

    @pytest.mark.parametrize("rel", [
        "src/pull_request_template.md",          # not one of the three locations
        "docs/sub/pull_request_template.md",     # not directly in one
        ".github/pull_request_template.md.bak",  # a backup, not a template
        ".github/my_pull_request_template.md",
    ])
    def test_a_file_outside_the_documented_rules_is_not_a_template(self, tmp_path, rel):
        repo = _body_repo(tmp_path, {rel: TEMPLATE})
        assert pr_gate.find_templates(repo) == []

    def test_the_multiple_template_directory_contributes_each_file(self, tmp_path):
        repo = _body_repo(tmp_path, {
            ".github/PULL_REQUEST_TEMPLATE/feature.md": TEMPLATE,
            ".github/PULL_REQUEST_TEMPLATE/fix.md": "## Fix\n",
        })
        found = [p.relative_to(repo).as_posix() for p in pr_gate.find_templates(repo)]
        assert found == [
            ".github/PULL_REQUEST_TEMPLATE/feature.md",
            ".github/PULL_REQUEST_TEMPLATE/fix.md",
        ]

    def test_no_template_exits_0_and_names_the_locations_searched(self, tmp_path):
        repo = _body_repo(tmp_path)
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, "anything")))
        assert r.returncode == 0, (r.stdout, r.stderr)
        for where in ("docs/", ".github/", "PULL_REQUEST_TEMPLATE/"):
            assert where in r.stdout, r.stdout
        assert len(r.stdout.strip().splitlines()) == 1

    def test_two_candidates_without_template_exit_1_and_list_both(self, tmp_path):
        repo = _body_repo(tmp_path, {
            "pull_request_template.md": TEMPLATE,
            ".github/pull_request_template.md": "## Other\n",
        })
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, GOOD_BODY)))
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "pull_request_template.md" in r.stdout
        assert ".github/pull_request_template.md" in r.stdout
        assert "--template" in r.stdout
        facts = _refusals(repo, pr_gate.BODY_GUARD)
        assert [f["body"]["reason"] for f in facts] == ["ambiguous-template"]

    def test_template_flag_resolves_the_ambiguity(self, tmp_path):
        repo = _body_repo(tmp_path, {
            "pull_request_template.md": TEMPLATE,
            ".github/pull_request_template.md": "## Other\n",
        })
        body = _write_body(tmp_path, GOOD_BODY)
        ok = _run(repo, "check-pr-body", str(body), "--template", "pull_request_template.md")
        assert ok.returncode == 0, (ok.stdout, ok.stderr)
        other = _run(repo, "check-pr-body", str(body), "--template", ".github/pull_request_template.md")
        assert other.returncode == 1
        assert "## Other" in other.stdout

    def test_an_unreadable_template_flag_exits_3(self, tmp_path):
        repo = _body_repo(tmp_path, {"pull_request_template.md": TEMPLATE})
        r = _run(repo, "check-pr-body", str(_write_body(tmp_path, GOOD_BODY)), "--template", "nope.md")
        assert r.returncode == 3
        assert "nope.md" in r.stderr

    def test_no_file_prints_what_the_description_must_follow(self, tmp_path):
        repo = _body_repo(tmp_path, {
            ".github/pull_request_template.md": TEMPLATE,
            "docs/CONTRIBUTING.md": "# Contributing\n",
        })
        r = _run(repo, "check-pr-body")
        assert r.returncode == 0
        assert ".github/pull_request_template.md" in r.stdout
        assert "docs/CONTRIBUTING.md" in r.stdout
        # The required lines, so the description can be drafted against them.
        assert "## Summary" in r.stdout and "- [ ] Tests added" in r.stdout
        assert "Not a section either" not in r.stdout

    def test_no_file_with_two_candidates_lists_both_and_exits_0(self, tmp_path):
        repo = _body_repo(tmp_path, {
            "pull_request_template.md": TEMPLATE,
            "docs/pull_request_template.md": "## Other\n",
        })
        r = _run(repo, "check-pr-body", "--json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        # Location order (root, docs/, .github/) — a listing, never a precedence.
        assert data["templates"] == ["pull_request_template.md", "docs/pull_request_template.md"]
        assert data["template"] is None

    def test_a_usage_error_exits_2(self, tmp_path):
        repo = _body_repo(tmp_path)
        assert _run(repo, "check-pr-body", "a.md", "b.md").returncode == 2
        assert _run(repo, "check-pr-body", "--template").returncode == 2
        assert _run(repo, "check-pr-body", "--nope").returncode == 2


# --- the dispatcher's classification ----------------------------------------


def _hook_module():
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("prawduct_hook_pr_gate", str(HOOK))
    spec = importlib.util.spec_from_loader("prawduct_hook_pr_gate", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("command", ["check-pr-hygiene", "check-pr-body"])
def test_both_commands_are_read_only_to_both_guards(command):
    """Neither strands anything in a disposable worktree: the one thing either
    writes is a `guard-refusal` fact in the clone-shared store, which outlives
    the tree. Neither is a governance write the skew guard refuses."""
    hook = _hook_module()
    assert command in hook._EPHEMERAL_SAFE_COMMANDS
    assert not hook._is_data_plane_write(command, [])
    assert command in hook._USAGE


# --- check-pr-hygiene: credential shapes on added lines ----------------------
#
# Every credential below is assembled at run time, so this file's own source
# carries no line the check would flag.

_TOKEN = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
_KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
_WAIVER = "prawduct:allow " + "prawduct/credential-shape -- a documented fixture token, revoked"


class TestCredentialShapeClassifier:
    """The per-line classifier on the one credential denylist."""

    def test_each_credential_class_is_named_never_echoed(self):
        from lib.backlog import transport

        cases = {
            f"token = '{_TOKEN}'": "github token",
            "pat = github_pat_" + "x" * 30: "github fine-grained token",
            "auth: eyJ" + "hbGciOi.eyJzdWIiOi.SflKxwRJSMeKKF2QT4": "jwt",
            _KEY_HEADER: "private key",
            "url = https://" + "user:hunter2@example.com/x": "url-embedded password",
        }
        for line, expected in cases.items():
            assert transport.credential_shape(line) == expected, line

    def test_ordinary_lines_and_the_placeholder_are_not_credentials(self):
        """The control, and the one shape the denylist carries that is not a
        credential: the cloud proxy's placeholder literal, named in docs."""
        from lib.backlog import transport

        for line in ("print('hello')", "https://example.com/a:b", "the " + "proxy-injected" + " token"):
            assert transport.credential_shape(line) is None, line

    def test_scrubbing_is_unchanged_by_the_classifier(self):
        """The scrub still reads every pattern, the placeholder and the whole
        multi-line key included."""
        from lib.backlog import transport

        key = _KEY_HEADER + "\nMIIabc\n-----END " + "RSA PRIVATE KEY-----"
        assert transport.scrub_secrets(f"a {_TOKEN} b") == "a [REDACTED] b"
        assert transport.scrub_secrets(key) == "[REDACTED]"
        assert transport.scrub_secrets("x proxy-" + "injected y") == "x [REDACTED] y"


class TestCredentialShape:
    def test_an_added_credential_line_refuses_and_never_prints_it(self, tmp_path):
        """Input that trips it: the branch adds `token = '<github token>'`."""
        repo = _repo(tmp_path, branch_files={"config.py": f"x = 1\ntoken = '{_TOKEN}'\n"})
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "credential-shape" in r.stdout
        assert "config.py:2" in r.stdout and "github token" in r.stdout
        assert _TOKEN not in r.stdout + r.stderr
        facts = _refusals(repo, pr_gate.HYGIENE_GUARD)
        assert len(facts) == 1, facts
        assert facts[0]["body"]["reason"] == "credential-shape"
        assert _TOKEN not in json.dumps(facts)
        # A re-check of the unchanged branch is the same event, not a second one.
        _run(repo, "check-pr-hygiene")
        assert len(_refusals(repo, pr_gate.HYGIENE_GUARD)) == 1

    def test_the_same_line_with_a_waiver_passes(self, tmp_path):
        repo = _repo(tmp_path, branch_files={"config.py": f"token = '{_TOKEN}'  # {_WAIVER}\n"})
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert _refusals(repo, pr_gate.HYGIENE_GUARD) == []

    def test_a_waiver_on_the_line_above_passes(self, tmp_path):
        repo = _repo(tmp_path, branch_files={"config.py": f"# {_WAIVER}\ntoken = '{_TOKEN}'\n"})
        assert _run(repo, "check-pr-hygiene").returncode == 0

    def test_a_reasonless_waiver_does_not_waive(self, tmp_path):
        bare = "prawduct:allow " + "prawduct/credential-shape"
        repo = _repo(tmp_path, branch_files={"config.py": f"token = '{_TOKEN}'  # {bare}\n"})
        assert _run(repo, "check-pr-hygiene").returncode == 1

    def test_another_rules_waiver_does_not_waive(self, tmp_path):
        other = "prawduct:allow " + "prawduct/broad-except -- not this rule"
        repo = _repo(tmp_path, branch_files={"config.py": f"token = '{_TOKEN}'  # {other}\n"})
        assert _run(repo, "check-pr-hygiene").returncode == 1

    def test_a_credential_on_a_line_the_branch_did_not_add_is_not_reported(self, tmp_path):
        """The base already carries the token; the branch edits another line of
        the same file. Only added lines are this PR's."""
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        _git(repo, "init", "-q", "-b", "develop")
        (repo / ".prawduct" / "project-state.yaml").write_text("project_name: f\nbase_branch: develop\n")
        (repo / "config.py").write_text(f"token = '{_TOKEN}'\nx = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "base")
        _git(repo, "checkout", "-q", "-b", "feat/x")
        (repo / "config.py").write_text(f"token = '{_TOKEN}'\nx = 2\n")
        _git(repo, "commit", "-qam", "change x")
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "nothing to report" in r.stdout and "config.py" not in r.stdout

    def test_a_private_key_header_line_refuses(self, tmp_path):
        """The denylist's key pattern spans lines; one added header line is a key."""
        repo = _repo(tmp_path, branch_files={"id_rsa": f"{_KEY_HEADER}\nMIIabc\n"})
        r = _run(repo, "check-pr-hygiene")
        assert r.returncode == 1
        assert "id_rsa:1" in r.stdout and "private key" in r.stdout

    def test_an_unreadable_diff_is_3_never_clean(self, tmp_path, monkeypatch):
        """Authority fails closed: the refusing check could not look."""
        from lib import record_lint

        repo = _repo(tmp_path)
        monkeypatch.setattr(record_lint, "_added_lines", lambda *_a, **_k: None)
        report = pr_gate.hygiene(repo)
        cred = [r for r in report.results if r.name == "credential-shape"]
        assert cred and cred[0].unchecked and not cred[0].items
        assert pr_gate.hygiene_exit(report) == 3
