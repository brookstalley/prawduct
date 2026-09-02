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
from lib import learnings_files, record_lint  # noqa: E402


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

    def test_governance_state_yaml_is_a_record(self):
        """The boundary this file used to pin the other way.

        ``.prawduct/project-state.yaml`` was excluded while "a record is
        markdown" was the whole rule, and the suite-total claim it excluded is
        exactly the one that survived: ten products carry a hand-maintained test
        count in that file, one of them on a 52 KB line the markdown-only sweep
        could not see. The state file is hand-authored governance too, so it is
        linted as one. Changed deliberately, on the owner's decision — the
        pinned behaviour is what was re-decided, not an assertion relaxed to let
        code pass.
        """
        assert record_lint.is_record(".prawduct/project-state.yaml")
        assert record_lint.is_record(".prawduct/some-config.yml")

    def test_yaml_outside_the_governance_dir_is_not_a_record(self):
        """The widening is scoped to governance state, not to YAML.

        A product's CI config, its dependency lockfiles and its own app config
        are not governance records, and linting them would put this control in
        the business of reviewing product data.
        """
        assert not record_lint.is_record(".github/workflows/ci.yaml")
        assert not record_lint.is_record("config/settings.yaml")
        assert not record_lint.is_record("plugin/templates/project-state.yaml")

    def test_archived_history_is_excluded(self):
        assert not record_lint.is_record(".prawduct/archive/artifacts/old-plan.md")
        assert not record_lint.is_record("archive/notes.md")
        # The exclusion reaches the newly-included suffix too — archived state is
        # not being asserted any more, whatever its file type.
        assert not record_lint.is_record(".prawduct/archive/project-state.yaml")

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

    def test_a_non_ascii_pathname_is_attributed_to_itself(self, tmp_path):
        """`core.quotepath` defaults on, and git then C-quotes the whole
        `diff --git` header for a non-ASCII name. Without the flag the header
        parser misses it and this record's added line lands on the PREVIOUS
        file's findings — a finding naming a record that never held the text.

        The two files and their order are the whole test: `a.md` sorts first and
        adds nothing lintable, so a misattributed `café.md` line surfaces as a
        finding against `a.md` rather than as no finding at all."""
        repo = _make_repo(tmp_path)
        arts = repo / ".prawduct" / "artifacts"
        (arts / "a.md").write_text("seed\n")
        (arts / "café.md").write_text("seed\n")
        base = _commit(repo, "seed")
        (arts / "a.md").write_text("seed\nnothing numeric here\n")
        (arts / "café.md").write_text("seed\n1812 tests pass.\n")
        head = _commit(repo, "add")

        paths = [".prawduct/artifacts/a.md", ".prawduct/artifacts/café.md"]
        found = _checks(_lint(repo, paths, base, head), "suite-total-claim")
        assert [(f["path"], f["line"]) for f in found] == [
            (".prawduct/artifacts/café.md", 2)
        ]

    def test_an_unparseable_header_drops_its_file_rather_than_misattributing(self):
        """Pathnames holding `"` or `\\` stay C-quoted whatever `core.quotepath`
        says, so the header parser can still meet a line it cannot read. When it
        does, the file is dropped: losing one file's findings is recoverable,
        while attaching its lines to the previous file produces a confident
        finding against a record that never contained the text.

        Parsed at the unit rather than through a repo because git will not let a
        pathname with a quote in it exist on every platform this runs on."""
        diff = (
            'diff --git a/one.md b/one.md\n'
            "--- a/one.md\n"
            "+++ b/one.md\n"
            "@@ -1,0 +2 @@\n"
            "+belongs to one\n"
            'diff --git "a/we\\"ird.md" "b/we\\"ird.md"\n'
            '--- "a/we\\"ird.md"\n'
            '+++ "b/we\\"ird.md"\n'
            "@@ -1,0 +2 @@\n"
            "+must not land on one.md\n"
        )
        by_path = record_lint._parse_diff(diff)
        assert by_path == {"one.md": [(2, "belongs to one")]}


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
            "suite total 92 after the split",
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


class TestTheStateFileIsLintedToo:
    """The tripwire that keeps `build_state.test_tracking` from coming back.

    It has come back once already: prawduct removed the block through the
    file-sync engine's `strip_test_tracking()`, that engine was retired, and the
    block is live in ten products today. Deleting a field does not delete the
    habit that writes it — so the deletion ships with a check that sees the file
    the habit writes into.

    Nothing about the PATTERN changes here; it already matched the real offending
    line many times over. What changed is which files the check is allowed to
    look at.
    """

    def _findings(self, tmp_path, rel: str, added: str, name: str) -> list[dict]:
        repo = _make_repo(tmp_path, name=name)
        doc = repo / rel
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("seed: 1\n")
        base = _commit(repo, "seed")
        doc.write_text(f"seed: 1\n{added}\n")
        head = _commit(repo, "add")
        return _lint(repo, [rel], base, head)

    def test_a_reintroduced_test_count_is_caught(self, tmp_path):
        """The shape that actually recurs: the block, with its provenance."""
        block = (
            "build_state:\n"
            "  test_tracking:\n"
            "    test_count: 27414  # post-Stage-4 GREEN: recorder line "
            "27064 passed / 0 failed / 33 skipped"
        )
        found = _checks(
            self._findings(tmp_path, ".prawduct/project-state.yaml", block, "reintro"),
            "suite-total-claim",
        )
        assert found, "the state file's suite-total claim went unseen"

    def test_one_finding_per_line_not_one_per_match(self, tmp_path):
        """The real line matched the pattern 33 times.

        A finding per match would bury a reviewer in one line's worth of noise
        and make the check's own yield unreadable.
        """
        crowded = "  note: 27064 passed, then 27062 passed, then 27059 passed"
        found = _checks(
            self._findings(tmp_path, ".prawduct/project-state.yaml", crowded, "crowded"),
            "suite-total-claim",
        )
        assert len(found) == 1, f"expected one finding, got {len(found)}"

    def test_a_products_own_yaml_is_not_linted(self, tmp_path):
        """Scoped to governance state, not to YAML.

        A product's CI config legitimately says "1200 tests"; this control has no
        business grading it.
        """
        found = _checks(
            self._findings(
                tmp_path, ".github/workflows/ci.yaml", "  # 1200 tests pass", "ci"
            ),
            "suite-total-claim",
        )
        assert not found, "linted a product file this control does not own"

    def test_the_markdown_only_checks_stay_markdown_only(self, tmp_path):
        """The other three checks must not start firing on a YAML path.

        Each already self-filters — `learnings-entry-shape` guards on the
        filename, `governed-by-gap` runs only over paths matching a build-plan
        name — so this pins the guards rather than adding new ones. Without it,
        widening the record set is a silent widening of three unrelated checks.
        """
        result = self._findings(
            tmp_path, ".prawduct/project-state.yaml", "  harmless: true", "guards"
        )
        for check in ("learnings-entry-shape", "governed-by-gap"):
            assert not _checks(result, check), (
                f"{check} fired on a YAML path — it is a markdown check"
            )


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

    def test_structurally_ungradeable_plan_is_not_quiet(self, tmp_path):
        """#642 Route 2 — the wholly-silent one.

        Chunks written as list items under `## Chunks` match no heading pattern,
        so no chunk section can be located and the deliverable check grades
        nothing for the plan's whole life. Unlike every other failure on this
        path it emitted no `unchecked` line at all — a null count that reads
        exactly like a healthy plan — so nothing downstream had a word to carry.
        """
        plan = "# Plan\n\n## Chunks\n\n- Chunk 01: do it\n"
        repo, head = self._repo_with_plan(tmp_path, plan, "nogradeable")
        result = _lint(repo, [], head, head)
        assert result["findings"] == [], "this is a gap, not a per-chunk finding"
        assert any("no parseable chunk heading" in u for u in result["unchecked"]), (
            f"the silent route stayed silent: {result['unchecked']}"
        )

    def test_a_finished_plan_stays_quiet(self, tmp_path):
        """The discriminator, pinned from the other side.

        Every box ticked ALSO yields "no current chunk", and that is grading
        being over rather than disabled. A first draft of the check above keyed
        only on the absent heading and reported this healthy case too — a
        signal whose first firing is wrong is one its readers learn to ignore.
        """
        plan = (
            "# Plan\n\n## Status\n\n- [x] Chunk 01: done\n\n"
            "### Chunk 01: done\n\n- **Deliverables:** none\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "finishedquiet")
        result = _lint(repo, [], head, head)
        assert not any("no parseable chunk heading" in u for u in result["unchecked"])

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

    def _repo_with_two_scoped_plans(self, tmp_path, name: str):
        """Two plans, both declaring a scope, with the pointer aimed at the one
        the review is NOT about — the shape that cost a true positive.

        `pointed` chunk 03 declares a deliverable that exists; `reviewed` chunk
        03 declares one that does not. So grading the pointer's plan reports a
        confident zero over a diff with a missing deliverable in it.
        """
        repo = _make_repo(tmp_path, name=name)
        artifacts = repo / ".prawduct" / "artifacts"
        (artifacts / "build-plan-pointed.md").write_text(
            "---\nartifact: build-plan\nscope: pointed\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 03: pointed\n\n"
            "### Chunk 03: pointed\n\n- **Deliverables:** `code.py`\n"
        )
        (artifacts / "build-plan-reviewed.md").write_text(
            "---\nartifact: build-plan\nscope: reviewed\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 03: reviewed\n\n"
            "### Chunk 03: reviewed\n\n- **Deliverables:** `src/absent.py`\n"
        )
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "project_name: t\nactive_build_plan: artifacts/build-plan-pointed.md\n"
        )
        return repo, _commit(repo, "two plans")

    def test_the_dispatched_scope_selects_the_plan_not_the_pointer(self, tmp_path):
        """The measured defect: the chunk came from the dispatch and the plan
        came from `active_build_plan`, and nothing checked they agreed.

        The deliverable check grades the pointer's plan while the reviewed plan
        cites deliverables that do not exist, and reports 0 — the check that
        exists to catch "a declared deliverable that isn't there" reporting
        clean on a diff full of them.
        """
        repo, head = self._repo_with_two_scoped_plans(tmp_path, "scoped")

        pointed = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03"
        )
        assert pointed["findings"] == [], "the pointer's plan is genuinely clean"
        assert pointed["plan_graded"].endswith("build-plan-pointed.md")

        reviewed = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03", scope="reviewed"
        )
        assert reviewed["plan_graded"].endswith("build-plan-reviewed.md")
        assert [f["check"] for f in reviewed["findings"]] == ["chunk-ref-missing"]
        assert "src/absent.py" in reviewed["findings"][0]["detail"]
        assert reviewed["counts"]["chunk-ref-missing"] == 1

    def test_a_scope_naming_no_plan_is_unchecked_not_a_fallback(self, tmp_path):
        """A scope no plan declares cannot be resolved — and falling back to the
        pointer is precisely the silent grade of another plan.

        The counter must say so too: a zero here reads exactly like "checked the
        deliverables, all present", and a tally gets quoted without its caveat.
        """
        repo, head = self._repo_with_two_scoped_plans(tmp_path, "noplan")
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03", scope="ghost"
        )
        assert result["plan_graded"] is None
        assert result["chunk_graded"] is None
        assert result["findings"] == []
        assert result["counts"]["chunk-ref-missing"] is None, (
            "a zero would read identically to a clean check"
        )
        assert any("chunk-ref-missing unchecked" in r for r in result["unchecked"])
        assert any("'ghost'" in r for r in result["unchecked"])

    def test_a_change_log_declared_scope_with_no_plan_is_no_subject_not_unchecked(
        self, tmp_path
    ):
        """A framework-only fix has no build plan — `building.md` says small work
        needs none — so `unchecked` made it a false blocker whose only exits were
        a retroactive plan or a silent departure from the rule. Three consecutive
        reviews took the second, which is what a rule with no remedy buys.

        The change-log is what tells this apart from a typo: a code branch cannot
        reach a PR without an entry tagged with its scope, so a real scope is
        declared there and a typo is declared nowhere.
        """
        repo, _head = self._repo_with_two_scoped_plans(tmp_path, "declared")
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-08-15: a framework-only fix\n\n"
            "<!-- prawduct: type=bugfix | scope=planless -->\n\nBody.\n"
        )
        head = _commit(repo, "change-log declares the scope")
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03", scope="planless"
        )
        entry = next(
            r for r in result["unchecked"] if r.startswith("chunk-ref-missing")
        )
        assert entry.startswith("chunk-ref-missing no-subject"), entry
        assert "'planless'" in entry
        # Still an honest non-answer: nothing was graded, so the count stays
        # null. The downgrade is of SEVERITY, not of the absence itself.
        assert result["counts"]["chunk-ref-missing"] is None
        assert result["plan_graded"] is None

    def test_an_undeclared_scope_still_blocks_even_with_a_change_log(self, tmp_path):
        """The other half — otherwise the downgrade is unconditional and a
        typo'd or stale scope quietly stops grading a plan that exists. The
        witness has to be the scope, not the mere presence of a change-log.
        """
        repo, _head = self._repo_with_two_scoped_plans(tmp_path, "undeclared")
        (repo / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-08-15: something else entirely\n\n"
            "<!-- prawduct: type=bugfix | scope=unrelated -->\n\nBody.\n"
        )
        head = _commit(repo, "change-log declares a different scope")
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03", scope="ghost"
        )
        entry = next(
            r for r in result["unchecked"] if r.startswith("chunk-ref-missing")
        )
        assert entry.startswith("chunk-ref-missing unchecked"), entry

    def test_an_unreadable_change_log_keeps_the_block(self, tmp_path):
        """Fail closed. An absent or malformed witness proves nothing, and the
        severity it would otherwise grant is the one that stops a deliverable
        check from going quiet.
        """
        repo, head = self._repo_with_two_scoped_plans(tmp_path, "nolog")
        assert not (repo / ".prawduct" / "change-log.md").exists(), (
            "the fixture must reach the unreadable-witness branch, not pass "
            "because some change-log happened to be absent of the scope"
        )
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03", scope="ghost"
        )
        entry = next(
            r for r in result["unchecked"] if r.startswith("chunk-ref-missing")
        )
        assert entry.startswith("chunk-ref-missing unchecked"), entry

    def test_the_pointer_assumption_is_reported_when_plans_are_ambiguous(
        self, tmp_path
    ):
        """Supplying `--chunk` without `--scope` still assumes a plan.

        `_check_chunk_refs`'s older `assumed` flag could not see this: it fires
        only when the dispatch carried NO chunk, so an explicitly-supplied chunk
        graded against the wrong plan produced no gap line at all.
        """
        repo, head = self._repo_with_two_scoped_plans(tmp_path, "ambiguous")
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="03"
        )
        assert result["chunk_graded"] == "03"
        assert any("active_build_plan pointer" in r for r in result["unchecked"])
        # NOT the BLOCKING prefix: the check ran, against a named plan.
        assert not any(
            r.startswith("chunk-ref-missing unchecked") for r in result["unchecked"]
        )

    def test_a_single_plan_repo_reports_no_pointer_assumption(self, tmp_path):
        """With one plan there was nothing to choose between, and a note on
        every review of every such repo is how a channel stops being read.

        A GUARD, not evidence: it passes against the pre-fix code too. What it
        pins is that the assumption line beside it stays bounded.
        """
        plan = (
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: do it\n\n"
            "### Chunk 01: do it\n\n- **Deliverables:** `code.py`\n"
        )
        repo, head = self._repo_with_plan(tmp_path, plan, "singleplan")
        result = record_lint.lint_records(
            repo, repo / ".prawduct", [], head, head, chunk_id="01"
        )
        assert result["unchecked"] == []
        assert result["counts"]["chunk-ref-missing"] == 0

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
        # Bullets carry a norm field because a norm entry IS a field-bearing
        # bullet; the bare `- one` these fixtures used encoded the older
        # count-every-bullet definition as a side effect of testing heading
        # levels. Assertions unchanged — only the scaffolding is now well-formed.
        text = (
            "## Direction\n\n- one\n  Why: because.\n\n"
            "## Elsewhere\n\n- two\n  Why: x.\n- three\n  Why: y.\n"
        )
        assert record_lint.direction_norm_count(text) == 1

    def test_a_deeper_heading_does_not_close_the_section(self):
        text = (
            "## Direction\n\n- one\n  Why: because.\n\n"
            "### Sub\n\n- two\n  Why: also.\n\n"
            "## Elsewhere\n\n- three\n  Why: nope.\n"
        )
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
            "plan_graded": None,
            "findings": [],
            "unchecked": [],
            # `chunk-ref-missing` is None, not 0: no chunk was in scope, so the
            # check produced no answer — the same fact `chunk_graded: None`
            # already carried while the counter beside it said zero. The other
            # rest ran over an empty record set and honestly found nothing.
            "counts": {
                "chunk-ref-missing": None,
                "governed-by-gap": 0,
                "suite-total-claim": 0,
                "learnings-entry-shape": 0,
                # The budget check is not record-scoped — it runs over the rules
                # corpus whatever the diff touched. This fixture has none, so it
                # honestly found nothing.
                "learnings-over-budget": 0,
                "learnings-budget-unreasoned": 0,
                "learnings-area-dead": 0,
            },
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
        # Every counter is None. Zeros here would be the crash reporting itself
        # in the shape of a clean check, and a tally gets quoted without the
        # caveat line above it.
        assert result["counts"] == {check: None for check in record_lint.CHECKS}
        assert any("record-lint did not run" in r for r in result["unchecked"])
        assert any("git exploded" in r for r in result["unchecked"]), "the cause is named"
        # The crash must reach the reviewer at the DELIVERABLE check's severity:
        # `review-cycle.md` grades this prefix BLOCKING, inheriting the retired
        # `cannot-verify:` bar. A generic note is the BLD-5J8N habituation.
        assert any(
            r.startswith("chunk-ref-missing unchecked") for r in result["unchecked"]
        )
        # …and nothing was graded, so the subject is null — a named chunk with
        # zero counts is the shape a CLEAN result has.
        assert result["chunk_graded"] is None

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
        # No plan in this fixture, so no chunk was graded — None, not a zero
        # that reads as "checked the deliverables and they were all there".
        assert result["counts"]["chunk-ref-missing"] is None
        assert result["chunk_graded"] is None
        assert result["records"] == [".prawduct/artifacts/notes.md"]

    def test_a_partial_run_withholds_its_tally(self):
        """A check can be BOTH skipped and productive, and the tally must withhold.

        `governed-by-gap` lands in `no_answer` per unreadable plan while other,
        readable plans still contribute findings. Reporting that partial as a
        bare integer says "this check ran and found N" — the exact confusion the
        None exists to remove, reachable through the increment loop rather than
        the initialiser. Nothing is lost: the findings stay in `findings`, and
        only the count withholds, because a count over some of the inputs is not
        a count.
        """
        counts = record_lint._count(
            [{"check": "governed-by-gap", "path": "b.md", "line": 1, "detail": "x"}],
            {"governed-by-gap"},
        )
        assert counts["governed-by-gap"] is None, (
            "a check that produced no answer for one input must not report an "
            "integer because another input produced findings"
        )
        # A check that genuinely ran still counts normally.
        assert record_lint._count(
            [{"check": "suite-total-claim", "path": "a.md", "line": 1, "detail": "x"}],
            {"governed-by-gap"},
        )["suite-total-claim"] == 1

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

    def test_a_null_count_renders_as_did_not_run_never_as_a_tally(self, tmp_path):
        """The rendering is where the `0` -> `None` change is actually kept.

        The data contract is pinned elsewhere; this pins the only surface an
        operator reads. A tidy-up back to `f"{k}={v}"` would print
        `chunk-ref-missing=None` beside three integers — which scans as a tally,
        and a tally of nothing is what reads as clean — with the suite green.
        """
        repo = _make_repo(tmp_path, name="nullrender")
        _git(repo, "branch", "-M", "main")
        _git(repo, "checkout", "-q", "-b", "work")
        (repo / ".prawduct" / "artifacts" / "notes.md").write_text("# Notes\n\nplain\n")
        _commit(repo, "work")

        result = _run_hook(repo, "verify-records")
        assert result.returncode == 0, result.stderr
        # No build plan in this fixture, so the deliverable check has no subject.
        assert "chunk-ref-missing=did-not-run" in result.stdout
        assert "chunk-ref-missing=None" not in result.stdout
        assert "chunk-ref-missing=0" not in result.stdout
        # The checks that DID run still report real integers.
        assert "governed-by-gap=0" in result.stdout
        assert "no chunk in scope" in result.stdout

    def test_it_derives_the_same_scope_the_dispatch_would(self, tmp_path):
        """The by-hand form exists to pre-answer the record checks. Grading a
        different plan than `critic-begin` will makes it answer a different
        question — confidently, and in the shape of the real answer."""
        repo = _make_repo(tmp_path, name="scopeparity")
        artifacts = repo / ".prawduct" / "artifacts"
        (artifacts / "build-plan-pointed.md").write_text(
            "---\nartifact: build-plan\nscope: pointed\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: pointed\n\n"
            "### Chunk 01: pointed\n\n- **Deliverables:** `code.py`\n"
        )
        (artifacts / "build-plan-mine.md").write_text(
            "---\nartifact: build-plan\nscope: mine\n---\n\n"
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: mine\n\n"
            "### Chunk 01: mine\n\n- **Deliverables:** `code.py`\n"
        )
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "project_name: t\nactive_build_plan: artifacts/build-plan-pointed.md\n"
        )
        _commit(repo, "plans")
        _git(repo, "branch", "-M", "main")
        _git(repo, "checkout", "-q", "-b", "fix/mine")
        (artifacts / "notes.md").write_text("# Notes\n\nnothing numeric\n")
        _commit(repo, "work")

        result = _run_hook(repo, "verify-records", "--chunk", "01", "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["plan_graded"].endswith("build-plan-mine.md")


class TestLearningsEntryShape:
    """`learnings.md` is the rule index; the narrative lives in detail.

    Two prior compactions (2026-06-10, 2026-07-17) each returned the file to a
    size larger than before, because a one-time sweep cannot hold a line against
    continuous addition. This check is the per-entry half.
    """

    def _findings(self, tmp_path, added: str, name: str = "learnings.md"):
        repo = _make_repo(tmp_path, name=f"r{abs(hash(added + name)) % 100000}")
        doc = repo / ".prawduct" / name
        doc.write_text("# Learnings\n\n---\n")
        base = _commit(repo, "seed")
        doc.write_text(f"# Learnings\n\n---\n{added}\n")
        head = _commit(repo, "add")
        return _checks(_lint(repo, [f".prawduct/{name}"], base, head),
                       "learnings-entry-shape")

    def test_fires_on_an_over_long_rule(self, tmp_path):
        rule = "When X happens do Y because Z, " + ("and here is the evidence " * 20)
        assert len(rule) > 400
        assert self._findings(tmp_path, f"## {rule}")

    def test_quiet_on_a_normal_rule(self, tmp_path):
        rule = ("When a review ends with zero blocking, dispose every remaining "
                "finding as FIX or ACCEPT because filing by default turns the "
                "backlog into a guilt pile")
        assert len(rule) < 400
        assert not self._findings(tmp_path, f"## {rule}")

    def test_quiet_on_a_learnings_md_that_is_not_the_root_record(self, tmp_path):
        """Only `.prawduct/learnings.md` is this repo's rule index.

        A `learnings.md` nested elsewhere — the learnings-migrate fixtures under
        tests/ carry three legacy corpora on purpose — is data. Grading its shape
        reported thirty findings about files nobody maintains as an index
        (learnings-v2 integration, 2026-09-02).
        """
        repo = _make_repo(tmp_path, name="nested-learnings")
        doc = repo / "tests" / "fixtures" / "sample" / ".prawduct" / "learnings.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Learnings\n\n---\n")
        base = _commit(repo, "seed")
        doc.write_text("# Learnings\n\n---\n## When X do Y because Z\n\nNarrative body.\n")
        head = _commit(repo, "add")
        rel = "tests/fixtures/sample/.prawduct/learnings.md"
        assert not _checks(_lint(repo, [rel], base, head), "learnings-entry-shape")

    def test_fires_on_a_narrative_body(self, tmp_path):
        """The channel the sweep was built for.

        This body sits directly under its heading, which is also where a
        continuation would sit — so it gets the both-remedies message rather
        than the bare move instruction. `test_prose_after_intervening_body_...`
        covers the position where the plain instruction is safe.
        """
        entry = "## When X do Y because Z\n\nHere is a paragraph of narrative evidence."
        findings = self._findings(tmp_path, entry)
        assert findings
        assert "move it to learnings-detail.md" in findings[0]["detail"]

    def test_a_line_under_the_heading_offers_both_remedies_with_the_guard(self, tmp_path):
        """The two remedies are opposite and one of them destroys the rule.

        A continuation told to "move to detail" leaves the heading truncated
        mid-sentence, and the loss is silent — the entry still parses and still
        reads as a rule up to the dangling word. Three rules were lost that way
        and repaired on 2026-07-31 from learnings-detail.md, where the move had
        parked the text. Nothing can classify continuation-vs-evidence reliably,
        so position decides which ADVICE is safe: adjacent to the heading, the
        bare "move it" instruction is never issued alone.
        """
        entry = "## When a guard test pins a safety claim, assert the PROPERTY — a test that\n\nmatches a literal passes for every rewording of the same defect"
        findings = self._findings(tmp_path, entry)
        assert findings, "a body line must still be reported"
        message = findings[0]["detail"]
        assert "join it onto the heading" in message
        assert "must still read as a complete rule" in message

    def test_a_backtick_initial_continuation_is_not_told_to_move(self, tmp_path):
        """The case test this replaced got this exactly backwards.

        `islower()` is False for a continuation resuming with code punctuation,
        so the old discriminator handed it the destructive instruction — the
        same one that truncated three rules.
        """
        entry = "## When a plan resolves by scope name, never a version, because\n\n`regen-views` silently skips Status flipping otherwise"
        message = self._findings(tmp_path, entry)[0]["detail"]
        assert "must still read as a complete rule" in message
        assert message.count("belongs in learnings-detail.md") == 0

    def test_every_line_of_a_wrapped_rule_gets_the_same_remedy(self, tmp_path):
        """A hard-wrapped rule is one sentence, so it needs ONE instruction.

        Rules in this file run to several hundred characters on a single
        physical line; wrapping one at terminal width yields a heading plus
        several body lines. An earlier fix checked only the immediate
        predecessor, so line 2 was guarded and line 3 was told to move — the
        same sentence, opposite remedies, in one report. An author following
        both truncates the rule, which is the original defect reintroduced one
        line deeper.
        """
        entry = (
            "## When a release has two documents tracking its state, one is already wrong\n"
            "— designate a single live tracker and demote the other to a decision record;\n"
            "and author each build chunk from the TREE, never from the upstream plan,\n"
            "because a plan derived from a plan describes intent the code may have overtaken"
        )
        details = [f["detail"] for f in self._findings(tmp_path, entry)]
        assert len(details) == 3, f"expected one finding per wrapped line, got {len(details)}"
        assert all("must still read as a complete rule" in d for d in details), details
        assert not any("(a move, never a deletion)" in d for d in details), details

    def test_prose_after_intervening_body_still_says_move(self, tmp_path):
        """Where a continuation cannot be, the plain instruction is safe."""
        entry = ("## When X do Y because Z\n\nFirst narrative paragraph of evidence.\n\n"
                 "Second narrative paragraph, which cannot be continuing the heading.")
        details = [f["detail"] for f in self._findings(tmp_path, entry)]
        assert any("belongs in learnings-detail.md" in d for d in details)

    def test_quiet_on_structural_lines(self, tmp_path):
        """Separators, comments and wiki-links are not narrative."""
        for line in ("---", "<!-- a note -->", "[[another-rule]]", "# Learnings"):
            assert not self._findings(tmp_path, line), line

    def test_does_not_apply_to_the_detail_file(self, tmp_path):
        """`learnings-detail.md` is explicitly unbounded — it is the destination."""
        entry = "## When X do Y\n\nA long narrative body belongs here."
        assert not self._findings(tmp_path, entry, name="learnings-detail.md")

    def test_quiet_on_the_files_own_preamble(self, tmp_path):
        """The header paragraph explains the format; it is not a violation of it.

        Without the preamble boundary the check reports line 3 of the real
        `learnings.md` — the sentence describing what the file is for.
        """
        repo = _make_repo(tmp_path, name="rpreamble")
        doc = repo / ".prawduct" / "learnings.md"
        doc.write_text("# Learnings\n\n---\n\n## When X do Y because Z\n")
        base = _commit(repo, "seed")
        doc.write_text(
            "# Learnings\n\nActive rules from this project's development, surfaced "
            "by topic.\n\n---\n\n## When X do Y because Z\n"
        )
        head = _commit(repo, "add preamble prose")
        assert not _checks(
            _lint(repo, [".prawduct/learnings.md"], base, head),
            "learnings-entry-shape",
        )


class TestEveryCheckCarriesASeverity:
    """`CHECKS` and the reviewer-facing severity surfaces cannot drift apart.

    A check that fires with no documented severity leaves the Goal-2 reviewer —
    told to "raise them at the severities given there" — to invent one or drop
    the finding. `learnings-entry-shape` shipped in exactly that state and all
    three coordinator reviewers found it independently, which is the signal that
    nothing pinned the relationship.
    """

    SURFACES = (
        "plugin/skills/critic/review-cycle.md",
        "plugin/skills/critic/goals-1-3.md",
        ".prawduct/cross-cutting-concerns.md",
    )

    def test_every_check_name_appears_on_every_reviewer_surface(self):
        import sys
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "plugin"))
        from lib.record_lint import CHECKS

        for rel in self.SURFACES:
            text = (root / rel).read_text()
            missing = [c for c in CHECKS if c not in text]
            assert not missing, (
                f"{rel} documents no severity for {missing} — a reviewer meets "
                "the finding with no verdict. Add a row, or remove the check."
            )

    def test_both_unchecked_shapes_are_graded_on_every_reviewer_surface(self):
        """The two `unchecked` shapes are told apart by PREFIX, on both surfaces.

        `_check_chunk_refs` emits two textually distinct strings and only one
        means the check could not run. Compressing them to "a
        `chunk-ref-missing` entry is BLOCKING" — which `goals-1-3.md` did, and
        which is the natural casualty of a token-diet pass on a file with ~50
        tokens of headroom — turns the *assumption* shape into a BLOCKING with
        no remedy available: a branch that builds no chunk has no `--chunk` to
        supply. That fired on real reviews before it was caught, and a blocker
        is the one severity that gates.

        Keyed off the strings the emitters actually produce, so the pin tracks
        the code rather than the prose that describes it.
        """
        import sys
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "plugin"))
        from lib import record_lint

        from lib import buildplan_refs

        # Both shapes must still be what the code emits, or the anchors below
        # are pinning prose against a contract that moved. The assumption shape
        # has two causes — an inferred chunk and an inferred plan — assembled
        # from two modules, and a surface naming only one leaves the other to be
        # read as a clean grade.
        emitter_src = Path(record_lint.__file__).read_text()
        assert "chunk-ref-missing unchecked — " in emitter_src
        assert "chunk-ref-missing graded chunk " in emitter_src
        assert "inferred from build-plan Status" in emitter_src
        assert "active_build_plan pointer" in Path(buildplan_refs.__file__).read_text()

        for rel in ("plugin/skills/critic/review-cycle.md",
                    "plugin/skills/critic/goals-1-3.md"):
            text = (root / rel).read_text()
            assert "chunk-ref-missing unchecked" in text, (
                f"{rel} no longer names the cannot-run shape by its prefix — a "
                "reviewer cannot tell which `unchecked` entry blocks."
            )
            assert "inferred from build-plan Status" in text, (
                f"{rel} dropped the assumption shape, so the compressed reading "
                "('any chunk-ref-missing entry is BLOCKING') returns and with it "
                "a false blocker that no --chunk value can clear."
            )
            assert "active_build_plan` pointer" in text, (
                f"{rel} names only the chunk half of the assumption. The plan "
                "half is the one that graded another plan's chunk and reported "
                "zero over deliverables that were not there."
            )
            # The assumption shape must be graded NOTE somewhere after it is
            # named — the specific severity, not merely a mention.
            tail = text[text.index("inferred from build-plan Status"):]
            assert "NOTE" in tail[:600], (
                f"{rel} names the assumption shape but does not grade it NOTE "
                "nearby; an ungraded mention is how the BLOCKING reading wins."
            )
            # …and a null count must never be presentable as a zero.
            assert "not a zero" in text, (
                f"{rel} does not tell the reviewer that a `null` count differs "
                "from a `0` — the reading a quoted tally invites."
            )


# ---------------------------------------------------------------------------
# The learnings budget — over AND grown blocks the next addition
# ---------------------------------------------------------------------------


def _rules_file(repo: Path, name: str, size: int) -> Path:
    """A rules file of exactly ``size`` bytes under the resolver's directory."""
    path = repo / learnings_files.RULES_DIR_REL / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x" * size)
    return path


_CORE_REL = f"{learnings_files.RULES_DIR_REL}/{learnings_files.CORE_NAME}"
_BUDGET = record_lint._LEARNINGS_BUDGET_DEFAULT_KB * 1024


def _state(repo: Path, block: str) -> None:
    (repo / ".prawduct" / "project-state.yaml").write_text(
        f"project_name: t\n{block}"
    )


class TestLearningsBudget:
    """The curation gate. Direction of travel is the finding, not size.

    Every fixture writes the CURRENT size into the working tree and compares it
    against a committed base tree, because that is the pair the check reads: a
    session's growth is only visible as working-tree-vs-base, and a check that
    compared two commits would go quiet for exactly the session that is adding
    the rule.
    """

    def _lint_budget(self, repo: Path, base: str) -> dict:
        return _lint(repo, [], base, _tree(repo))

    def test_over_budget_and_grown_blocks(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 1000)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)

        findings = _checks(self._lint_budget(repo, base), "learnings-over-budget")
        assert len(findings) == 1
        assert findings[0]["path"] == _CORE_REL
        detail = findings[0]["detail"]
        # Both sizes and the budget, so the author can see the trade without
        # re-deriving any of the three.
        assert str(_BUDGET + 500) in detail and "1000B" in detail
        assert f"{_BUDGET}B budget" in detail
        # The payment rule, verbatim — the finding has to say what paying looks
        # like, or the cheapest way out is to shorten a rule until it fits.
        assert "pay from genuine duplication (merge or delete in this commit)" in detail
        assert "never trim a rule to fit" in detail
        assert "learnings_budgets.core.md" in detail

    def test_over_budget_but_shrunk_passes(self, tmp_path):
        """An inherited corpus is not asked to stop the world and compact.

        The two prior sweeps were one-time subtractions against a continuous
        addition and the file regrew both times; what this gate buys is payment
        for the NEXT addition, so a file moving in the right direction is quiet
        even while it is still over.
        """
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 5000)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)

        assert _checks(self._lint_budget(repo, base), "learnings-over-budget") == []

    def test_unchanged_over_budget_file_is_quiet(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)
        base = _commit(repo, "seed rules")

        assert _checks(self._lint_budget(repo, base), "learnings-over-budget") == []

    def test_under_budget_growth_passes(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 100)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, 8000)

        assert _checks(self._lint_budget(repo, base), "learnings-over-budget") == []

    def test_absent_at_base_counts_as_grown(self, tmp_path):
        """A file that did not exist before is all addition.

        Exempting the first commit of an area file would let a repo land a 40KB
        one and be told from then on that it may never touch it.
        """
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _rules_file(repo, "critic.md", _BUDGET + 1)

        findings = _checks(self._lint_budget(repo, base), "learnings-over-budget")
        assert len(findings) == 1
        assert findings[0]["path"].endswith("critic.md")
        assert "grown from 0B" in findings[0]["detail"]

    def test_an_area_file_is_budgeted_beside_core(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 10)
        _rules_file(repo, "critic.md", 10)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 1)
        _rules_file(repo, "critic.md", _BUDGET + 1)

        paths = {
            f["path"] for f in _checks(self._lint_budget(repo, base), "learnings-over-budget")
        }
        assert paths == {_CORE_REL, f"{learnings_files.RULES_DIR_REL}/critic.md"}

    def test_a_declared_budget_raises_the_ceiling(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 10)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)
        _state(
            repo,
            'learnings_budgets:\n'
            '  core.md: {kb: 32, reason: "the fleet-wide rules, sweep is done"}\n',
        )

        result = self._lint_budget(repo, base)
        assert _checks(result, "learnings-over-budget") == []
        assert _checks(result, "learnings-budget-unreasoned") == []

    def test_the_nested_form_is_read_too(self, tmp_path):
        """A user writing ordinary block YAML must not have the override
        silently dropped — a half-read declaration applies the default while the
        operator believes their number is in force."""
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 10)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)
        _state(
            repo,
            "learnings_budgets:\n"
            "  core.md:\n"
            "    kb: 32\n"
            '    reason: "reviewers read this file every cycle"\n',
        )

        result = self._lint_budget(repo, base)
        assert _checks(result, "learnings-over-budget") == []
        assert result["unchecked"] == []

    def test_a_declared_budget_without_a_reason_blocks(self, tmp_path):
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _state(repo, "learnings_budgets:\n  core.md: {kb: 32}\n")

        findings = _checks(self._lint_budget(repo, base), "learnings-budget-unreasoned")
        assert len(findings) == 1
        assert findings[0]["path"] == ".prawduct/project-state.yaml"
        assert "learnings_budgets.core.md" in findings[0]["detail"]
        assert "`reason:`" in findings[0]["detail"]

    def test_an_empty_reason_is_no_reason(self, tmp_path):
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _state(repo, 'learnings_budgets:\n  core.md: {kb: 32, reason: ""}\n')

        assert _checks(self._lint_budget(repo, base), "learnings-budget-unreasoned")

    def test_a_reason_holding_a_comma_or_hash_survives(self, tmp_path):
        """The reason is prose, and both separators this file's other readers
        split on appear in prose. Truncating inside the quotes and then
        reporting the truncation as "no reason given" manufactures a blocking
        finding out of punctuation."""
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _state(
            repo,
            "learnings_budgets:\n"
            '  core.md: {kb: 32, reason: "merged, deduped # see PR 12"}\n',
        )

        result = self._lint_budget(repo, base)
        assert _checks(result, "learnings-budget-unreasoned") == []
        assert result["unchecked"] == []
        budgets, malformed = record_lint.parse_learnings_budgets(
            (repo / ".prawduct" / "project-state.yaml").read_text()
        )
        assert malformed == []
        assert budgets["core.md"]["reason"] == "merged, deduped # see PR 12"

    def test_a_legacy_layout_yields_no_finding(self, tmp_path):
        """The unmigrated state is the migration directive's business (R4).
        Two controls naming the same state teach a reader to skip both."""
        repo = _make_repo(tmp_path)
        legacy = repo / learnings_files.LEGACY_REL
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("x" * (_BUDGET * 4))
        base = _tree(repo)

        result = self._lint_budget(repo, base)
        assert _checks(result, "learnings-over-budget") == []
        assert result["unchecked"] == []

    def test_an_unparseable_entry_is_unchecked_never_a_silent_default(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 10)
        base = _commit(repo, "seed rules")
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)
        _state(repo, "learnings_budgets:\n  core.md: 32\n")

        result = self._lint_budget(repo, base)
        loud = [
            r for r in result["unchecked"]
            if r.startswith("learnings-over-budget, learnings-budget-unreasoned unchecked")
        ]
        assert len(loud) == 1, result["unchecked"]
        assert "learnings_budgets.core.md" in loud[0], "it must name the entry"
        assert "NOT applied" in loud[0] and "default governs" in loud[0], (
            "the operator has to be told their declaration is inert and which "
            "ceiling took over — a silent fallback is the failure mode"
        )
        # A check that produced no answer counts None, never 0 — the tally is
        # what gets quoted, so the distinction has to live in the number.
        assert result["counts"]["learnings-over-budget"] is None
        assert result["counts"]["learnings-budget-unreasoned"] is None

    def test_each_unreadable_entry_gets_its_own_line(self, tmp_path):
        """Joining several into one line buries the one the operator must fix.

        This is the only branch here a person triggers by hand, and it fails in
        the dangerous direction: the declaration stays in the file, looks
        applied, and the default ceiling quietly governs instead.
        """
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _state(
            repo,
            "learnings_budgets:\n  core.md: 32\n  critic.md: {kb: big}\n",
        )

        lines = [
            r for r in self._lint_budget(repo, base)["unchecked"]
            if "learnings_budgets." in r
        ]
        assert len(lines) == 2, lines
        assert {"core.md", "critic.md"} == {
            r.split("learnings_budgets.")[1].split("`")[0] for r in lines
        }

    def test_an_unresolvable_base_tree_is_unchecked_not_a_wall_of_blockers(
        self, tmp_path
    ):
        """Reading a per-file `cat-file` failure as "absent at base" would make
        every rules file look grown-from-nothing whenever the interval itself is
        the broken thing. The tree is validated once, before any file is."""
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 500)

        result = _lint(repo, [], "0" * 40, _tree(repo))
        assert _checks(result, "learnings-over-budget") == []
        assert any(
            "learnings-over-budget unchecked" in r and "base tree" in r
            for r in result["unchecked"]
        ), result["unchecked"]
        assert result["counts"]["learnings-over-budget"] is None

    def test_the_budget_runs_without_a_changed_record(self, tmp_path):
        """The corpus grows on commits that change nothing else, and the budget
        is about the file's size rather than its added lines — so this check
        cannot be gated on the record subset the line-scoped checks read."""
        repo = _make_repo(tmp_path)
        base = _tree(repo)
        _rules_file(repo, learnings_files.CORE_NAME, _BUDGET + 1)

        result = record_lint.lint_records(
            repo, repo / ".prawduct", ["code.py"], base, _tree(repo)
        )
        assert result["records"] == []
        assert len(_checks(result, "learnings-over-budget")) == 1


class TestLearningsAreaDead:
    """An area file reachable by nothing is a rule nobody will ever be shown.

    The rules directory only grows, and an area file is reached by its globs or
    not at all. Rename the directory those globs name and the file stops being
    loaded by the harness and stops being returned by `files_for_paths`, so the
    Critic stops reading it too — while the file sits there, valid and full of
    rules, looking exactly like a live one.
    """

    def _area(self, repo: Path, name: str, globs: list[str]) -> None:
        path = repo / learnings_files.RULES_DIR_REL / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f'  - "{glob}"' for glob in globs)
        path.write_text(f"---\npaths:\n{body}\n---\n\n## a rule\n")

    def _dead(self, repo: Path) -> list[dict]:
        return _checks(
            _lint(repo, [], _tree(repo), _tree(repo)), "learnings-area-dead"
        )

    def test_globs_matching_no_tracked_file_fire(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._area(repo, "engine.md", ["engine/**", "engine/*.py"])
        _commit(repo, "add a dead area")

        findings = self._dead(repo)
        assert len(findings) == 1
        assert findings[0]["path"].endswith("engine.md")
        # The globs are named, or the reader cannot tell which one to rename.
        assert "`engine/**`" in findings[0]["detail"]
        assert "fold the rules into core.md" in findings[0]["detail"]

    def test_globs_matching_a_tracked_file_are_quiet(self, tmp_path):
        repo = _make_repo(tmp_path)
        self._area(repo, "code.md", ["code.py"])
        _commit(repo, "add a live area")

        assert self._dead(repo) == []

    def test_an_unscoped_area_is_exempt(self, tmp_path):
        """No `paths:` means the harness loads it unconditionally, exactly like
        `core.md` — it cannot be unreachable, so it cannot be dead."""
        repo = _make_repo(tmp_path)
        path = repo / learnings_files.RULES_DIR_REL / "always.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("## a rule that applies everywhere\n")
        _commit(repo, "add an unscoped area")

        assert self._dead(repo) == []

    def test_core_is_never_reported(self, tmp_path):
        repo = _make_repo(tmp_path)
        _rules_file(repo, learnings_files.CORE_NAME, 100)
        _commit(repo, "seed core")

        assert self._dead(repo) == []

    def test_an_untracked_area_file_is_still_matched_against_tracked_paths(
        self, tmp_path
    ):
        """Matched against `git ls-files`, not the working tree: build output and
        ignored scratch trees would keep a dead area alive, and the globs are
        meant to name code that is committed."""
        repo = _make_repo(tmp_path)
        (repo / "build").mkdir()
        (repo / "build" / "out.py").write_text("x = 1\n")
        self._area(repo, "build.md", ["build/**"])

        assert len(self._dead(repo)) == 1

    def test_an_unlistable_tree_is_unchecked_never_a_wall_of_dead_areas(
        self, tmp_path, monkeypatch
    ):
        """A glob matches nothing when nothing can be listed — reporting that as
        a dead area would blame the corpus for a broken git call."""
        repo = _make_repo(tmp_path)
        self._area(repo, "code.md", ["code.py"])
        _commit(repo, "add a live area")

        real = record_lint.evidence.run_git

        def fail(project_dir, *args, **kwargs):
            if args and args[0] == "ls-files":
                return 1, "", "fatal: not a git repository"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(record_lint.evidence, "run_git", fail)
        result = _lint(repo, [], _tree(repo), _tree(repo))
        assert _checks(result, "learnings-area-dead") == []
        assert any(
            "learnings-area-dead unchecked" in r for r in result["unchecked"]
        ), result["unchecked"]
        assert result["counts"]["learnings-area-dead"] is None


class TestBudgetDeclarationParsing:
    def test_absent_key_is_no_budgets_and_no_complaint(self):
        assert record_lint.parse_learnings_budgets("project_name: t\n") == ({}, [])

    def test_comments_and_blanks_are_inert_inside_the_block(self):
        budgets, malformed = record_lint.parse_learnings_budgets(
            "learnings_budgets:\n"
            "  # why these are raised\n"
            "\n"
            '  core.md: {kb: 24, reason: "swept"}\n'
            "next_key: 1\n"
            "  core.md: {kb: 99}\n"
        )
        assert malformed == []
        # A column-0 key ends the block; anything after it belongs to that key.
        assert budgets == {"core.md": {"kb": 24, "reason": "swept"}}

    def test_an_unknown_field_makes_the_entry_malformed_not_partial(self):
        budgets, malformed = record_lint.parse_learnings_budgets(
            'learnings_budgets:\n  core.md: {kb: 24, why: "swept"}\n'
        )
        assert budgets == {}
        assert malformed == ["core.md"]

    def test_a_non_integer_kb_is_malformed(self):
        budgets, malformed = record_lint.parse_learnings_budgets(
            'learnings_budgets:\n  core.md: {kb: big, reason: "swept"}\n'
        )
        assert budgets == {}
        assert malformed == ["core.md"]
