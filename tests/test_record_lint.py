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
* **The real 2026-07-29 defect is caught.** The GOV-8C3W under-disposition — an
  artifact carrying three ``## Direction`` norms against a plan disposing of
  one — is the fixture, because it is the finding that actually bought review
  rounds.
* **The right chunk is graded.** Build-plan Status resolves "current" to the
  first *unchecked* box, so a finished chunk's review silently grades the NEXT
  chunk's unbuilt deliverables. The dispatched chunk wins; an inference is
  reported as one.
* **Advice, never authority.** ``lint_records`` returns findings; nothing here
  gates, and a lint finding cannot change a review's verdict. ``_safe`` extends
  that to crashes: advice must never take down the dispatch it advises.

Real git repos, sterile config, mirroring ``test_dispositions.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import record_lint  # noqa: E402


def _run_hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        ["python3", str(HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "HOME": str(home),
            "CLAUDE_PROJECT_DIR": str(repo),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


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

    def test_many_records_are_attributed_correctly_from_one_diff(self, tmp_path):
        """Added lines come from a SINGLE `git diff` over every record — a
        subprocess per file would make this control's cost scale with file count
        rather than with the diff. Each finding must still land on its own file
        and line."""
        repo = _make_repo(tmp_path)
        arts = repo / ".prawduct" / "artifacts"
        for name in ("a", "b", "c"):
            (arts / f"{name}.md").write_text("seed\n")
        base = _commit(repo, "seed")
        (arts / "a.md").write_text("seed\n1812 tests pass.\n")
        (arts / "b.md").write_text("seed\nnothing numeric here\n")
        (arts / "c.md").write_text("seed\nfiller\nfull suite 849 green\n")
        head = _commit(repo, "add")

        paths = [f".prawduct/artifacts/{n}.md" for n in ("a", "b", "c")]
        found = _checks(_lint(repo, paths, base, head), "suite-total-claim")
        assert {(f["path"], f["line"]) for f in found} == {
            (".prawduct/artifacts/a.md", 2),
            (".prawduct/artifacts/c.md", 3),
        }

    def test_an_added_line_starting_with_plusplus_is_not_a_header(self, tmp_path):
        """`+++ b/x` is file metadata; `++foo` as content produces the same
        three leading `+` in the diff. Hunk-gating tells them apart."""
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_text("seed\n++ and then 1812 tests pass\n")
        head = _commit(repo, "add")

        found = _checks(_lint(repo, [".prawduct/artifacts/notes.md"], base, head), "suite-total-claim")
        assert [f["line"] for f in found] == [2]

    def test_a_diff_that_cannot_be_decoded_reports_unchecked(self, tmp_path):
        """`git diff` output carries file CONTENT, and `text=True` decodes it
        strictly — one non-UTF-8 byte in any consumer's changed `.md` used to
        raise straight through `critic-begin`. It must degrade to a reported
        non-answer, never a traceback and never a clean pass."""
        repo = _make_repo(tmp_path)
        doc = repo / ".prawduct" / "artifacts" / "notes.md"
        doc.write_text("seed\n")
        base = _commit(repo, "seed")
        doc.write_bytes("seed\nlatin1: caf\xe9\n".encode("latin-1"))
        head = _commit(repo, "add")

        result = _lint(repo, [".prawduct/artifacts/notes.md"], base, head)
        assert _checks(result, "suite-total-claim") == []
        assert any("could not read the diff" in r for r in result["unchecked"])

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
            "A total of 25 backlog items were triaged this session.",
            "The migration moved 295 items in total.",
        ):
            assert not self._fires(tmp_path, text), f"unexpected finding for {text!r}"


# ---------------------------------------------------------------------------
# chunk-ref-missing — the deliverable check, moved from a reviewer instruction
# ---------------------------------------------------------------------------


class TestChunkRefs:
    """`verify-chunk-refs` used to be an instruction a reviewer ran by hand.
    It now runs at dispatch and the answer rides the manifest — which means
    getting the SUBJECT right is load-bearing, since there is no longer a
    reviewer re-deriving it."""

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
        """A code-only diff still has a reviewed chunk whose declared outputs
        must exist by review time."""
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "codeonly")
        result = _lint(repo, ["code.py"], head, head)
        assert result["records"] == []
        assert [f["check"] for f in result["findings"]] == ["chunk-ref-missing"]

    def test_unparseable_plan_reports_unchecked_never_clean(self, tmp_path):
        plan = "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\nNo chunk section here.\n"
        repo, head = self._repo_with_plan(tmp_path, plan, "unparseable")
        result = _lint(repo, [], head, head)
        assert _checks(result, "chunk-ref-missing") == []
        assert any("chunk-ref-missing unchecked" in r for r in result["unchecked"])
        assert result["chunk_graded"] is None

    def test_no_current_chunk_is_quiet(self, tmp_path):
        plan = "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n"
        repo, head = self._repo_with_plan(tmp_path, plan, "allcomplete")
        result = _lint(repo, [], head, head)
        assert result["findings"] == []
        assert result["unchecked"] == []
        assert result["chunk_graded"] is None

    def test_the_dispatched_chunk_wins_over_build_plan_status(self, tmp_path):
        """The defect this closes: Status resolves "current" to the first
        UNCHECKED box, so the moment chunk 02 is marked `[x]` the check silently
        grades chunk 03's unbuilt deliverables and reports a confident zero.
        The manifest's chunk is the subject; Status is not."""
        plan = (
            "# Plan\n\n## Status\n\n- [x] Chunk 02: done\n- [ ] Chunk 03: next\n\n"
            "### Chunk 02: done\n\n- **Deliverables:** `src/built.py`\n\n"
            "### Chunk 03: next\n\n- **Deliverables:** `src/not_yet.py`\n"
        )
        repo, _base = self._repo_with_plan(tmp_path, plan, "wrongchunk")
        (repo / "src").mkdir()
        (repo / "src" / "built.py").write_text("x = 1\n")
        head = _commit(repo, "build 02")

        graded_02 = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="02"
        )
        assert graded_02["chunk_graded"] == "02"
        assert graded_02["findings"] == [], "02's declared deliverable exists"

        inferred = _lint(repo, [], head, head)
        assert inferred["chunk_graded"] == "03", "Status points at the NEXT chunk"
        assert [f["check"] for f in inferred["findings"]] == ["chunk-ref-missing"]

    def test_an_inferred_chunk_is_reported_as_an_assumption(self, tmp_path):
        """Inference is allowed but never silent — a zero from the wrong chunk
        reads exactly like a zero from the right one."""
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "inferred")
        result = _lint(repo, [], head, head)
        assert any("inferred from build-plan Status" in r for r in result["unchecked"])

        named = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="01"
        )
        assert named["unchecked"] == [], "no assumption to report when told"


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

    def test_a_cited_artifact_that_does_not_exist_is_reported(self, tmp_path):
        """A `governed_by:` name is a bare token, not a backticked path, so the
        citation scanner never sees it. A plan governed by a file nobody can
        read reads as MORE governed than an omission would."""
        repo = _make_repo(tmp_path, name="ghostartifact")
        arts = repo / ".prawduct" / "artifacts"
        base = _tree(repo)
        (arts / "build-plan-demo.md").write_text(_plan(2, artifact="no-such-artifact"))
        head = _commit(repo, "add plan")

        found = _checks(_lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head), "governed-by-gap")
        assert len(found) == 1
        assert "no-such-artifact" in found[0]["detail"]

    def test_an_artifact_outside_the_canonical_dir_still_resolves(self, tmp_path):
        """`.prawduct/artifacts/` is the canonical home, not the only one — this
        repo keeps several governing artifacts under `documentation/`. Guessing
        a second directory would be a guess about layout; asking git for a
        tracked basename is neither layout- nor language-specific. Without this
        the check cried wolf on a plan whose artifact was merely elsewhere."""
        repo = _make_repo(tmp_path, name="noncanonical")
        (repo / "documentation").mkdir()
        (repo / "documentation" / "service-contract.md").write_text(THREE_NORM_ARTIFACT)
        base = _commit(repo, "seed elsewhere")
        (repo / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
            _plan(1, artifact="service-contract")
        )
        head = _commit(repo, "add plan")

        found = _checks(_lint(repo, [".prawduct/artifacts/build-plan-demo.md"], base, head), "governed-by-gap")
        assert len(found) == 1, "resolved, then graded on its norm count"
        assert "carries 3" in found[0]["detail"]
        assert "no readable" not in found[0]["detail"]

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
    def test_undiffable_interval_reports_unchecked(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _tree(repo)
        result = _lint(repo, [".prawduct/artifacts/notes.md"], "0" * 40, head)
        assert result["findings"] == []
        assert any("could not read the diff" in reason for reason in result["unchecked"])

    def test_no_records_means_no_line_scoped_work(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = _lint(repo, ["plugin/lib/gates.py"], _tree(repo), _tree(repo))
        assert result == {
            "records": [],
            "chunk_graded": None,
            "findings": [],
            "unchecked": [],
            "counts": {check: 0 for check in record_lint.CHECKS},
        }

    def test_a_crash_degrades_to_unchecked_never_taking_dispatch_down(self, tmp_path, monkeypatch):
        """`lint_records_safe` is the only form the dispatch path may call.
        Advice failing hard on the authority path it advises is the inversion
        this guards — measured against a real crash, not a mocked return."""
        repo = _make_repo(tmp_path)

        def boom(*_a, **_k):
            raise RuntimeError("git exploded")

        monkeypatch.setattr(record_lint, "_check_chunk_refs", boom)
        result = record_lint.lint_records_safe(
            repo, repo / ".prawduct", ["a.md"], _tree(repo), _tree(repo), "02"
        )
        assert result["findings"] == []
        assert result["counts"] == {check: 0 for check in record_lint.CHECKS}
        assert any("record-lint did not run" in r for r in result["unchecked"])
        assert any("git exploded" in r for r in result["unchecked"]), "the cause is named"

    def test_safe_is_transparent_when_nothing_throws(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _tree(repo)
        assert record_lint.lint_records_safe(
            repo, repo / ".prawduct", [], head, head
        ) == record_lint.lint_records(repo, repo / ".prawduct", [], head, head)


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
        assert result["counts"]["suite-total-claim"] == 1
        assert result["counts"]["governed-by-gap"] == 0
        assert result["counts"]["chunk-ref-missing"] == 0
        assert result["records"] == [".prawduct/artifacts/notes.md"]

    def test_retired_checks_are_absent_from_the_contract(self):
        """`dangling-ref` and `unknown-backlog-id` were measured at zero true
        positives and removed. Their absence is a decision, and a consumer
        reading `counts` must not find a key that never fills."""
        assert "dangling-ref" not in record_lint.CHECKS
        assert "unknown-backlog-id" not in record_lint.CHECKS

    def test_format_findings_names_location_and_unchecked(self, tmp_path):
        result = {
            "findings": [
                {"check": "governed-by-gap", "path": "a.md", "line": 7, "detail": "short 2 of 3"}
            ],
            "unchecked": ["chunk-ref-missing unchecked — reason"],
        }
        lines = record_lint.format_findings(result)
        assert lines[0] == "governed-by-gap: a.md:7: short 2 of 3"
        assert lines[1] == "unchecked: chunk-ref-missing unchecked — reason"


# ---------------------------------------------------------------------------
# The `verify-records` CLI — the by-hand form of what critic-begin computes
# ---------------------------------------------------------------------------


class TestVerifyRecordsCLI:
    """`Exposed API: prawduct-hook-cli`, and `api-contract.md` records a
    three-way exit contract plus a `--json`-equals-the-manifest-block claim.
    Both are pinned here, because a contract nothing exercises is a sentence."""

    def _repo(self, tmp_path, name="cli"):
        repo = _make_repo(tmp_path, name=name)
        (repo / ".prawduct" / "artifacts" / "build-plan.md").write_text(
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `src/never.py`\n"
        )
        _commit(repo, "plan")
        _git(repo, "branch", "-M", "main")
        _git(repo, "checkout", "-q", "-b", "work")
        (repo / ".prawduct" / "artifacts" / "notes.md").write_text(
            "# Notes\n\n1812 tests pass.\n"
        )
        _commit(repo, "work")
        return repo

    def test_findings_exit_zero_because_the_lint_is_advice(self, tmp_path):
        """Exit 0 WITH findings is the contract: record-lint advises the builder
        and gates nothing. Exit 1 is reserved for could-not-run, so a failure to
        check is never confusable with a clean check."""
        result = _run_hook(self._repo(tmp_path, "advice"), "verify-records")
        assert result.returncode == 0, result.stderr
        assert "suite-total-claim" in result.stdout
        assert "chunk-ref-missing" in result.stdout

    def test_an_unresolvable_interval_exits_one(self, tmp_path):
        result = _run_hook(self._repo(tmp_path, "badbase"), "verify-records",
                           "--base", "definitely-not-a-ref")
        assert result.returncode == 1
        assert "cannot resolve" in result.stderr

    def test_json_is_the_manifest_record_lint_block_verbatim(self, tmp_path):
        """`api-contract.md` says the `--json` shape IS the manifest's
        `record_lint` block — which is what makes either surface readable by one
        consumer. Compared field-for-field against the library call the manifest
        stores, not eyeballed."""
        repo = self._repo(tmp_path, "jsonshape")
        result = _run_hook(repo, "verify-records", "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)

        base = _git(repo, "rev-parse", "main^{tree}")
        head = _git(repo, "rev-parse", "HEAD^{tree}")
        changed = _git(repo, "diff", "--name-only", base, head).splitlines()
        direct = record_lint.lint_records_safe(
            repo, repo / ".prawduct", changed, base, head, None
        )
        assert payload == direct

    def test_chunk_flag_names_the_subject(self, tmp_path):
        repo = self._repo(tmp_path, "chunkflag")
        result = _run_hook(repo, "verify-records", "--chunk", "01", "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["chunk_graded"] == "01"

    def test_summary_line_names_the_chunk_it_graded(self, tmp_path):
        """A zero count is only meaningful once the reader knows whose
        deliverables were counted."""
        result = _run_hook(self._repo(tmp_path, "subject"), "verify-records",
                           "--chunk", "01")
        assert result.returncode == 0, result.stderr
        assert "deliverables of chunk 01" in result.stdout

    def test_outside_an_onboarded_repo_it_is_a_clean_no_op(self, tmp_path):
        bare = tmp_path / "bare"
        bare.mkdir()
        _git(bare, "init", "-q")
        result = _run_hook(bare, "verify-records")
        assert result.returncode == 0, result.stderr
        assert "not an onboarded repo" in result.stdout
