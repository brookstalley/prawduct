"""Tests for deterministic record-lint — the record-class checks that used to
cost review rounds, answered in code at dispatch time.

The claims pinned here are the design's load-bearing ones:

* **Cost is proportional to the diff.** Every line-scoped check reads only the
  lines a change ADDED. A record whose history is full of old claims (the
  change-log) must not report them when one new entry lands, or the control is
  unusable on a real repo.
* **An unrun check reports itself.** A check that cannot read its inputs lands
  in ``unchecked`` with a reason. Silence-as-pass is the failure mode the
  per-language dispatch norm exists to prevent, and this control must not
  reproduce it.
* **The real 2026-07-29 defects are caught.** The GOV-8C3W under-disposition
  (an artifact carrying three ``## Direction`` norms against a plan disposing
  of one) and a dangling ``file:line`` citation are the fixtures, because they
  are the findings that actually bought review rounds.
* **Advice, never authority.** ``lint_records`` returns findings; nothing here
  gates, and a lint finding cannot change a review's verdict.

Real git repos, sterile config, mirroring ``test_dispositions.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import record_lint  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _make_repo(base: Path, name: str = "repo") -> Path:
    repo = base / name
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text("project_name: t\n")
    (repo / ".prawduct" / "backlog.md").write_text(
        "# Backlog\n\n## Open\n\n- **[GOV-8C3W]** a real item\n"
        "- **[CRT-3X9D]** another real item\n"
    )
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _tree(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{ref}^{{tree}}")


def _commit(repo: Path, message: str = "c") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _tree(repo)


def _lint(repo: Path, paths: list[str], base: str, head: str) -> dict:
    return record_lint.lint_records(repo, repo / ".prawduct", paths, base, head)


def _checks(result: dict, check: str) -> list[dict]:
    return [f for f in result["findings"] if f["check"] == check]


# ---------------------------------------------------------------------------
# Record classification
# ---------------------------------------------------------------------------


class TestRecordClassification:
    def test_markdown_is_a_record(self):
        assert record_lint.is_record(".prawduct/artifacts/architecture.md")
        assert record_lint.is_record("plugin/skills/critic/review-protocol.md")
        assert record_lint.is_record("README.md")

    def test_non_markdown_is_not_a_record(self):
        assert not record_lint.is_record("plugin/lib/gates.py")
        assert not record_lint.is_record("plugin/lib/Foo.swift")
        assert not record_lint.is_record(".prawduct/project-state.yaml")

    def test_archived_history_is_excluded(self):
        assert not record_lint.is_record(".prawduct/archive/artifacts/old-plan.md")
        assert not record_lint.is_record("archive/notes.md")

    def test_records_in_preserves_order_and_is_none_safe(self):
        assert record_lint.records_in(None) == []
        assert record_lint.records_in(["b.md", "a.py", "a.md"]) == ["b.md", "a.md"]


# ---------------------------------------------------------------------------
# Added-line scoping — the cost boundary
# ---------------------------------------------------------------------------


class TestAddedLineScoping:
    def test_only_added_lines_are_linted(self, tmp_path):
        """A record whose HISTORY carries a claim reports nothing when an
        unrelated line is added — the property that makes this runnable against
        a change-log with years of suite totals in it."""
        repo = _make_repo(tmp_path)
        log = repo / ".prawduct" / "change-log.md"
        log.write_text("# Change Log\n\n## Old entry\n\n**Tests:** 1724 passing.\n")
        base = _commit(repo, "seed history")

        log.write_text(log.read_text() + "\n## New entry\n\nNothing numeric here.\n")
        head = _commit(repo, "new entry")

        result = _lint(repo, [".prawduct/change-log.md"], base, head)
        assert _checks(result, "suite-total-claim") == []

    def test_a_new_claim_on_an_added_line_is_caught(self, tmp_path):
        repo = _make_repo(tmp_path)
        log = repo / ".prawduct" / "change-log.md"
        log.write_text("# Change Log\n\n## Old entry\n\nNothing numeric here.\n")
        base = _commit(repo, "seed history")

        log.write_text(log.read_text() + "\n## New entry\n\n**Tests:** 1812 passing.\n")
        head = _commit(repo, "new entry")

        found = _checks(_lint(repo, [".prawduct/change-log.md"], base, head), "suite-total-claim")
        assert len(found) == 1
        assert found[0]["path"] == ".prawduct/change-log.md"
        assert found[0]["line"] > 0

    def test_line_numbers_point_at_the_added_line(self, tmp_path):
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("a\nb\nc\n")
        base = _commit(repo, "seed")
        doc.write_text("a\nb\nc\nfull suite 900\n")
        head = _commit(repo, "add")

        found = _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "suite-total-claim")
        assert [f["line"] for f in found] == [4]


# ---------------------------------------------------------------------------
# suite-total-claim — the subtraction tripwire
# ---------------------------------------------------------------------------


class TestSuiteTotalClaim:
    """Fires on a suite TOTAL; stays quiet on a delta or a scoped count.

    Phrasings here are deliberately different from each other — a tripwire that
    only matches the one sentence that prompted it passes for every rewording of
    the same defect.
    """

    def _fires(self, tmp_path, text: str) -> bool:
        repo = _make_repo(tmp_path, name=f"r{abs(hash(text)) % 100000}")
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text(f"seed\n{text}\n")
        head = _commit(repo, "add")
        return bool(_checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "suite-total-claim"))

    def test_fires_on_total_phrasings(self, tmp_path):
        for text in (
            "**Tests:** 812 passing (+8).",
            "1012 tests pass.",
            "full suite 849 passing",
            "694 tests green.",
            "the whole suite (1724 tests) passes with no regression",
        ):
            assert self._fires(tmp_path, text), f"expected a finding for {text!r}"

    def test_quiet_on_deltas_and_scoped_counts(self, tmp_path):
        for text in (
            "New regression class `TestFoo` (+14 tests).",
            "28 tests cover the recognizer.",
            "0 blocking, 3 warning, 2 note across 1 reviewer(s).",
            "Released as v3.2.1 with 2 fixes.",
            "~30 tests in `test_views.py` target `parse_change_log` directly.",
        ):
            assert not self._fires(tmp_path, text), f"unexpected finding for {text!r}"


# ---------------------------------------------------------------------------
# dangling-ref
# ---------------------------------------------------------------------------


class TestDanglingRef:
    def test_missing_path_is_reported(self, tmp_path):
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nSee `plugin/lib/nope.py:42` for the mechanism.\n")
        head = _commit(repo, "add")

        found = _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "dangling-ref")
        assert len(found) == 1
        assert "plugin/lib/nope.py" in found[0]["detail"]
        assert ":42" not in found[0]["detail"], "the line suffix is stripped before the check"

    def test_existing_path_is_quiet(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / "plugin" / "lib").mkdir(parents=True)
        (repo / "plugin" / "lib" / "real.py").write_text("x = 1\n")
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nSee `plugin/lib/real.py:7`.\n")
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "dangling-ref") == []

    def test_non_path_tokens_are_not_treated_as_paths(self, tmp_path):
        """The carveouts `buildplan_refs` already earned apply here rather than
        being re-litigated: slash-commands, globs, URLs, placeholders, anchors,
        and git refs are not missing files."""
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text(
            "seed\nRun `/prawduct:critic`, glob `docs/*.md`, fetch `https://x.test/y`, "
            "write `<inbox>/<slug>.md`, cut `release/v3.2.0`, link `owner/repo#12`.\n"
        )
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "dangling-ref") == []

    def test_backticked_prose_is_not_a_path(self, tmp_path):
        """A backticked span containing whitespace is a command or a metadata
        bar, never a path. Without this the backlog's `·`-separated `refs:` bars
        produced 44 false findings on one branch — the ceremony ratchet this
        whole control exists to reverse."""
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text(
            "seed\nRun `python -m pytest tests/ -q`; bar reads "
            "`effort: M · area: critic · refs: plugin/lib/gates.py (the gate)`.\n"
        )
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "dangling-ref") == []

    def test_new_qualifier_exempts_a_deliverable_the_plan_creates(self, tmp_path):
        """`new `path`` in a plan declares a file the work CREATES. Flagging it
        would make every plan report its own deliverables as dangling until the
        chunk that builds them lands — and the exemption spans the file, because
        a plan names the same path again in a Done-when step."""
        repo = _make_repo(tmp_path)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-demo.md"
        plan.write_text("# Plan\n\nseed\n")
        base = _commit(repo, "seed")
        plan.write_text(
            "# Plan\n\nseed\n"
            "- **Deliverables:** new `plugin/lib/future.py`\n"
            "- **Done when:** `plugin/lib/future.py` has tests\n"
        )
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head), "dangling-ref") == []

    def test_new_qualifier_does_not_exempt_an_unrelated_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        plan = repo / ".prawduct" / "artifacts" / "build-plan-demo.md"
        plan.write_text("# Plan\n\nseed\n")
        base = _commit(repo, "seed")
        plan.write_text(
            "# Plan\n\nseed\n"
            "- **Deliverables:** new `plugin/lib/future.py`\n"
            "- **Consumes:** `plugin/lib/absent.py`\n"
        )
        head = _commit(repo, "add")

        found = _checks(_lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head), "dangling-ref")
        assert [f["detail"] for f in found] == ["`plugin/lib/absent.py` does not exist"]


# ---------------------------------------------------------------------------
# unknown-backlog-id
# ---------------------------------------------------------------------------


class TestChunkRefs:
    """The chunk-deliverable check moved from a reviewer instruction
    (`verify-chunk-refs`, run by hand) to dispatch, so the answer rides the
    manifest. It reads the CURRENT chunk whether or not the plan changed."""

    def _repo_with_plan(self, tmp_path, plan: str, name: str):
        repo = _make_repo(tmp_path, name=name)
        (repo / ".prawduct" / "artifacts" / "build-plan.md").write_text(plan)
        return repo, _commit(repo, "plan")

    def test_missing_deliverable_is_reported(self, tmp_path):
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "missingdeliv")
        found = _checks(_lint(repo, [], head, head), "chunk-ref-missing")
        assert len(found) == 1
        assert "src/never.py" in found[0]["detail"]

    def test_it_runs_even_when_no_record_changed(self, tmp_path):
        """A code-only diff still has a current chunk whose declared outputs
        must exist by review time."""
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "codeonly")
        result = _lint(repo, ["code.py"], head, head)
        assert result["records"] == []
        assert [f["check"] for f in result["findings"]] == ["chunk-ref-missing"]

    def test_a_missing_path_is_reported_once_not_twice(self, tmp_path):
        """Adding a chunk section names its deliverable on an added line too,
        so both checks can see the same absent file. It is reported ONCE — a
        control that double-counts is the one nobody trusts."""
        repo = _make_repo(tmp_path, name="dedupe")
        base = _tree(repo)
        (repo / ".prawduct" / "artifacts" / "build-plan.md").write_text(
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        head = _commit(repo, "plan")

        result = _lint(repo, [".prawduct/artifacts/build-plan.md"], base, head)
        assert [f["check"] for f in result["findings"]] == ["chunk-ref-missing"]

    def test_unparseable_plan_reports_unchecked_never_clean(self, tmp_path):
        plan = "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\nNo chunk section here.\n"
        repo, head = self._repo_with_plan(tmp_path, plan, "unparseable")
        result = _lint(repo, [], head, head)
        assert _checks(result, "chunk-ref-missing") == []
        assert any("chunk-ref-missing unchecked" in r for r in result["unchecked"])

    def test_no_current_chunk_is_quiet(self, tmp_path):
        plan = "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n"
        repo, head = self._repo_with_plan(tmp_path, plan, "allcomplete")
        result = _lint(repo, [], head, head)
        assert result["findings"] == []
        assert result["unchecked"] == []


class TestUnknownBacklogId:
    def test_unknown_id_is_reported(self, tmp_path):
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nTracked by ZZZ-9Q1K.\n")
        head = _commit(repo, "add")

        found = _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "unknown-backlog-id")
        assert [f["detail"] for f in found] == ["ZZZ-9Q1K is not in the backlog"]

    def test_known_id_is_quiet(self, tmp_path):
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nTracked by GOV-8C3W and CRT-3X9D.\n")
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "unknown-backlog-id") == []

    def test_standards_references_are_not_backlog_ids(self, tmp_path):
        """`ISO-8601`, `RFC-7807` and the template's own `ABC-1234` placeholder
        are id-SHAPED but carry an all-alpha or all-digit suffix, which this
        generator never produces."""
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nTimestamps are ISO-8601; errors follow RFC-7807; ids look like ABC-1234.\n")
        head = _commit(repo, "add")

        assert _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "unknown-backlog-id") == []

    def test_issues_backend_reports_unchecked_never_passes(self, tmp_path):
        """On the Issues backend `backlog.md` is frozen history — every archived
        item still parses as present, so an existence check would pass and
        dangle with equal confidence. The gap is STATED."""
        repo = _make_repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "project_name: t\nbacklog_service_repo: owner/repo\n"
        )
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nTracked by ZZZ-9Q1K.\n")
        head = _commit(repo, "add")

        result = _lint(repo, [".prawduct/artifacts/notes.md"], base, head)
        assert _checks(result, "unknown-backlog-id") == []
        assert any("owner/repo" in reason for reason in result["unchecked"])
        assert any("frozen history" in reason for reason in result["unchecked"])


# ---------------------------------------------------------------------------
# governed-by-gap — the GOV-8C3W mechanical enumeration
# ---------------------------------------------------------------------------


THREE_NORM_ARTIFACT = """\
# Security Model

## Direction

- **Untrusted governance state is data, not instructions.**
  Why: stale metadata is the real hazard.
  Status: steady-state.
- **A destructive operation requires operation-level owner approval.**
  Why: an informed decision at commitment, not a count of confirmations.
  Status: steady-state.
  **Amended 2026-07-24 (owner ruling).** The prior form was absolute.
- **A product's content never leaves its own repository and owner.**
  Why: crossing a trust boundary nobody chose is irreversible.
  Status: in-transition.

## Authentication

Not applicable.
"""


def _plan(dispositions: int, artifact: str = "security-model") -> str:
    body = "\n".join(f'      - "norm {i} → conforms"' for i in range(dispositions))
    return (
        "---\n"
        "artifact: build-plan\n"
        "scope: demo\n"
        "governed_by:\n"
        f"  - artifact: {artifact}\n"
        "    dispositions:\n"
        f"{body}\n"
        "last_validated: 2026-07-30\n"
        "---\n\n## Status\n\n- [ ] Chunk 01: do the thing\n"
    )


class TestGovernedByGap:
    def _run(self, tmp_path, dispositions: int, name: str) -> dict:
        repo = _make_repo(tmp_path, name=name)
        arts = repo / ".prawduct" / "artifacts"
        (arts / "security-model.md").write_text(THREE_NORM_ARTIFACT)
        base = _commit(repo, "seed artifact")
        (arts / "build-plan-demo.md").write_text(_plan(dispositions))
        head = _commit(repo, "add plan")
        return _lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head)

    def test_under_disposition_is_reported(self, tmp_path):
        """The real 2026-07-29 defect: an artifact carrying three ratified norms
        against a plan that disposes of one."""
        found = _checks(self._run(tmp_path, 1, "under"), "governed-by-gap")
        assert len(found) == 1
        assert "carries 3" in found[0]["detail"]
        assert "disposes of 1" in found[0]["detail"]

    def test_complete_disposition_is_quiet(self, tmp_path):
        assert _checks(self._run(tmp_path, 3, "complete"), "governed-by-gap") == []

    def test_over_disposition_is_quiet(self, tmp_path):
        """Splitting a norm's limbs across two dispositions is legitimate; only
        leaving one unaddressed is the defect."""
        assert _checks(self._run(tmp_path, 5, "over"), "governed-by-gap") == []

    def test_artifact_without_direction_section_is_skipped(self, tmp_path):
        repo = _make_repo(tmp_path, name="nodirection")
        arts = repo / ".prawduct" / "artifacts"
        (arts / "data-model.md").write_text("# Data Model\n\n## Entities\n\n- Thing\n")
        base = _commit(repo, "seed artifact")
        (arts / "build-plan-demo.md").write_text(_plan(0, artifact="data-model"))
        head = _commit(repo, "add plan")

        assert _checks(_lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head), "governed-by-gap") == []

    def test_a_changed_artifact_pulls_in_the_active_plan(self, tmp_path):
        """The GOV-8C3W CLASS, not its instance: adding a norm to an artifact
        silently shortens the disposition block of a plan that did not itself
        change, so a governing-artifact edit re-checks the active plan."""
        repo = _make_repo(tmp_path, name="classcheck")
        arts = repo / ".prawduct" / "artifacts"
        (arts / "security-model.md").write_text(THREE_NORM_ARTIFACT)
        (arts / "build-plan-demo.md").write_text(_plan(3))
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "project_name: t\nactive_build_plan: artifacts/build-plan-demo.md\n"
        )
        base = _commit(repo, "seed complete plan")

        (arts / "security-model.md").write_text(
            THREE_NORM_ARTIFACT.replace(
                "## Authentication",
                "- **A fourth norm lands.**\n  Status: steady-state.\n\n## Authentication",
            )
        )
        head = _commit(repo, "add a norm")

        found = _checks(_lint(repo, [".prawduct/artifacts/security-model.md"], base, head), "governed-by-gap")
        assert len(found) == 1, "the untouched active plan is now short a disposition"
        assert found[0]["path"].endswith("build-plan-demo.md")


class TestDirectionNormCount:
    def test_counts_top_level_bullets_only(self):
        assert record_lint.direction_norm_count(THREE_NORM_ARTIFACT) == 3

    def test_absent_section_is_none_not_zero(self):
        assert record_lint.direction_norm_count("# Doc\n\n## Other\n\n- a\n") is None

    def test_prose_mentioning_the_heading_does_not_open_a_section(self):
        text = "# Doc\n\nA `## Direction` section carries norms.\n\n- not a norm\n"
        assert record_lint.direction_norm_count(text) is None

    def test_section_closes_at_the_next_equal_level_heading(self):
        text = "## Direction\n\n- one\n\n## Elsewhere\n\n- two\n- three\n"
        assert record_lint.direction_norm_count(text) == 1

    def test_a_deeper_heading_does_not_close_the_section(self):
        text = "## Direction\n\n- one\n\n### Sub\n\n- two\n\n## Elsewhere\n\n- three\n"
        assert record_lint.direction_norm_count(text) == 2


class TestGovernedByParsing:
    def test_soft_wrapped_disposition_counts_once(self):
        text = (
            "---\n"
            "governed_by:\n"
            "  - artifact: architecture\n"
            "    dispositions:\n"
            '      - "a long disposition that\n'
            '        wraps across physical lines"\n'
            '      - "a second one"\n'
            "---\n"
        )
        assert record_lint._parse_governed_by(text) == [
            {"artifact": "architecture", "dispositions": 2, "line": 3}
        ]

    def test_multiple_artifacts_are_counted_separately(self):
        text = (
            "---\n"
            "governed_by:\n"
            "  - artifact: a\n"
            "    dispositions:\n"
            '      - "one"\n'
            "  - artifact: b\n"
            "    dispositions:\n"
            '      - "one"\n'
            '      - "two"\n'
            "---\n"
        )
        counts = {e["artifact"]: e["dispositions"] for e in record_lint._parse_governed_by(text)}
        assert counts == {"a": 1, "b": 2}

    def test_a_later_top_level_key_closes_the_block(self):
        text = (
            "---\n"
            "governed_by:\n"
            "  - artifact: a\n"
            "    dispositions:\n"
            '      - "one"\n'
            "depends_on:\n"
            "  - artifact: b\n"
            "---\n"
        )
        assert [e["artifact"] for e in record_lint._parse_governed_by(text)] == ["a"]

    def test_no_frontmatter_yields_nothing(self):
        assert record_lint._parse_governed_by("# Plan\n\ngoverned_by:\n  - artifact: a\n") == []


# ---------------------------------------------------------------------------
# Unchecked reporting — an unrun check is never a clean one
# ---------------------------------------------------------------------------


class TestUncheckedReporting:
    def test_undiffable_path_reports_unchecked(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _tree(repo)
        result = _lint(repo, [".prawduct/artifacts/notes.md"], "0" * 40, head)
        assert result["findings"] == []
        assert any("could not diff" in reason for reason in result["unchecked"])

    def test_missing_backlog_reports_unchecked(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".prawduct" / "backlog.md").unlink()
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nTracked by ZZZ-9Q1K.\n")
        head = _commit(repo, "add")

        result = _lint(repo, [".prawduct/artifacts/notes.md"], base, head)
        assert _checks(result, "unknown-backlog-id") == []
        assert any("backlog ids unchecked" in reason for reason in result["unchecked"])

    def test_no_records_means_no_work_and_no_unchecked(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = _lint(repo, ["plugin/lib/gates.py"], _tree(repo), _tree(repo))
        assert result == {
            "records": [],
            "findings": [],
            "unchecked": [],
            "counts": {check: 0 for check in record_lint.CHECKS},
        }


# ---------------------------------------------------------------------------
# Result shape — what the manifest and the fact carry
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_counts_cover_every_check(self, tmp_path):
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\nSee `plugin/lib/nope.py`; tracked by ZZZ-9Q1K; 1812 tests pass.\n")
        head = _commit(repo, "add")

        result = _lint(repo, [".prawduct/artifacts/notes.md"], base, head)
        assert set(result["counts"]) == set(record_lint.CHECKS)
        assert result["counts"]["dangling-ref"] == 1
        assert result["counts"]["unknown-backlog-id"] == 1
        assert result["counts"]["suite-total-claim"] == 1
        assert result["counts"]["governed-by-gap"] == 0
        assert result["records"] == [".prawduct/artifacts/notes.md"]

    def test_format_findings_names_location_and_unchecked(self, tmp_path):
        result = {
            "findings": [
                {"check": "dangling-ref", "path": "a.md", "line": 7, "detail": "`x/y.py` does not exist"}
            ],
            "unchecked": ["backlog ids unchecked — reason"],
        }
        lines = record_lint.format_findings(result)
        assert lines[0] == "dangling-ref: a.md:7: `x/y.py` does not exist"
        assert lines[1] == "unchecked: backlog ids unchecked — reason"
