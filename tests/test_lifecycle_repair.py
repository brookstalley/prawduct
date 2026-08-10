"""FL2 / FL3 / GD2 — converging a repo off the retired derived-view model.

The behaviours under test, in the order they matter:

* the repair is **idempotent** — running it twice changes nothing the second
  time, which is what makes it safe to ship to a fleet where some repos have
  already converged;
* the comment strip decides by **position**, so a plan that merely *mentions*
  the retired flag keeps its prose while one that *instructs* the reader loses
  the instruction;
* FL3 **reports and never writes**, because only a session with the work in
  context may say which chunk is done.
"""

from __future__ import annotations

from pathlib import Path

from lib import lifecycle_repair

STATE_WITH_BOTH = """\
project: demo

# =============================================================================
# DERIVED VIEWS (enabled by default, v1.4+)
# =============================================================================
# When true (default), the build-plan `## Status` block is a derived view.

views_enabled: true

coverage_required: false

# =============================================================================
# SCOPE ROLLUPS (derived view, v1.4+)
# =============================================================================
# Auto-generated. Do not hand-edit.

scope_rollups:
  alpha:
    chunks: ["01"]
    releases: ["v1.0.0"]
  beta:
    chunks: []
    releases: ["v1.1.0"]

trailing_key: kept
"""


def _make_repo(tmp_path: Path, state: str = STATE_WITH_BOTH) -> Path:
    prawduct = tmp_path / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(state, encoding="utf-8")
    return tmp_path


def _comment_edits(repo: Path) -> list[dict]:
    """Only the plan-comment edits.

    The fixture repo also carries the retired state keys, so asserting on the
    whole edit list would pass or fail for reasons that have nothing to do with
    the comment rule under test.
    """
    return [
        edit
        for edit in lifecycle_repair.plan_repair(repo)["edits"]
        if edit["kind"] == "plan-comment"
    ]


def _write_plan(repo: Path, name: str, body: str) -> Path:
    path = repo / ".prawduct" / "artifacts" / name
    path.write_text(body, encoding="utf-8")
    return path


class TestStateFileRepair:
    def test_removes_both_keys_and_their_comment_headers(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        plan = lifecycle_repair.plan_repair(repo)
        lifecycle_repair.apply_repair(repo, plan)
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "views_enabled" not in text
        assert "scope_rollups" not in text
        # The section banners documenting them go too — a heading left over a
        # hole is worse than either the key or the heading alone.
        assert "DERIVED VIEWS" not in text
        assert "SCOPE ROLLUPS" not in text

    def test_leaves_every_other_key_untouched(self, tmp_path: Path) -> None:
        """The blast radius is the two retired keys and nothing else.

        `coverage_required` sits between them, so a removal that walked too far
        in either direction would take a live opt-in flag with it.
        """
        repo = _make_repo(tmp_path)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "project: demo" in text
        assert "coverage_required: false" in text
        assert "trailing_key: kept" in text

    def test_running_twice_changes_nothing_the_second_time(self, tmp_path: Path) -> None:
        """Idempotence, asserted on the bytes rather than on a status word.

        A repair that reported "no-op" while rewriting the file would satisfy a
        status assertion and still produce a diff in every repo it touched.
        """
        repo = _make_repo(tmp_path)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        after_first = (repo / ".prawduct" / "project-state.yaml").read_bytes()

        second = lifecycle_repair.plan_repair(repo)
        assert second["edits"] == []
        lifecycle_repair.apply_repair(repo, second)
        assert (repo / ".prawduct" / "project-state.yaml").read_bytes() == after_first

    def test_converged_repo_is_a_no_op_from_the_start(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, state="project: demo\ncoverage_required: false\n")
        assert lifecycle_repair.plan_repair(repo)["edits"] == []

    def test_indented_lookalike_key_is_not_removed(self, tmp_path: Path) -> None:
        """A nested key belongs to its parent mapping, not to this repair."""
        repo = _make_repo(
            tmp_path, state="project: demo\nsomething:\n  views_enabled: true\n"
        )
        assert lifecycle_repair.plan_repair(repo)["edits"] == []


class TestPlanCommentStrip:
    STATUS_INSTRUCTION = """\
---
artifact: build-plan
scope: demo
---

## Status

<!-- Derived view (`views_enabled: true`). Do not hand-edit — add a tagged
     change-log entry and regenerate. -->

- [x] Chunk 01: done
- [ ] Chunk 02: not done

## Build Chunks
"""

    def test_strips_an_instruction_inside_the_status_section(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", self.STATUS_INSTRUCTION)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = plan_path.read_text()

        assert "views_enabled" not in text
        # The checkboxes it was instructing about are untouched — the repair
        # removes the false instruction, never the state a human wrote.
        assert "- [x] Chunk 01: done" in text
        assert "- [ ] Chunk 02: not done" in text

    def test_keeps_a_mention_outside_the_status_section(self, tmp_path: Path) -> None:
        """A plan header narrating the work is not an instruction about Status.

        This is the case a prose-sniffing predicate got wrong: the narrative uses
        the same vocabulary as the instruction, so only position separates them.
        """
        body = (
            "<!-- Written after the work. `views_enabled: true` meant a statusless\n"
            "     change-log scope had to resolve to a plan file. -->\n"
            "---\nartifact: build-plan\nscope: demo\n---\n\n"
            "## Status\n\n- [x] Chunk 01: done\n"
        )
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", body)
        assert _comment_edits(repo) == []
        assert "Written after the work" in plan_path.read_text()

    def test_keeps_a_backticked_comment_in_a_chunk_deliverable(self, tmp_path: Path) -> None:
        """A spec quoting the comment syntax is describing it, not carrying it.

        This plan's own Chunk 05 deliverable contains the literal text
        ``<!-- views_enabled: … -->`` as inline code, so a scanner blind to
        backticks would delete the sentence specifying its own behaviour.
        """
        body = (
            "---\nartifact: build-plan\nscope: demo\n---\n\n"
            "## Status\n\n- [x] Chunk 01: done\n\n"
            "## Build Chunks\n\n"
            "- strip `<!-- views_enabled: … -->` comments from build plans.\n"
        )
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", body)
        assert _comment_edits(repo) == []
        assert "strip `<!-- views_enabled: … -->` comments" in plan_path.read_text()

    def test_an_unterminated_comment_removes_nothing(self, tmp_path: Path) -> None:
        """The worst outcome this operation can produce, from likely input.

        Treating an unopened-but-unclosed comment as running to end-of-document
        is safe for a reader and catastrophic for a writer: the first cut deleted
        from the ``<!--`` through the last line, taking the plan's checkboxes and
        every chunk with it. A malformed plan is exactly what a fleet-wide repair
        eventually meets, so the writer claims nothing it cannot delimit.
        """
        body = (
            "---\nartifact: build-plan\nscope: demo\n---\n\n"
            "## Status\n\n"
            "<!-- Derived view (`views_enabled: true`). Do not hand-edit.\n\n"
            "- [x] Chunk 01: done\n- [ ] Chunk 02: pending\n\n"
            "## Build Chunks\n\nContent that must survive.\n"
        )
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", body)
        before = plan_path.read_bytes()

        assert _comment_edits(repo) == []
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        assert plan_path.read_bytes() == before

    def test_no_repair_ever_removes_a_checkbox(self, tmp_path: Path) -> None:
        """The invariant behind every case above, asserted once directly.

        Checkbox lines are the only reading of chunk progress the session gates
        have. Whatever this repair decides about a comment, the boxes are not
        its business — so a future widening of the strip rule fails here rather
        than in a consumer's repo.
        """
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", self.STATUS_INSTRUCTION)
        before = [ln for ln in plan_path.read_text().splitlines() if ln.startswith("- [")]

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        after = [ln for ln in plan_path.read_text().splitlines() if ln.startswith("- [")]
        assert after == before

    def test_archived_plans_are_not_touched(self, tmp_path: Path) -> None:
        """An archived plan is a record; editing it falsifies what it records."""
        repo = _make_repo(tmp_path)
        archive = repo / ".prawduct" / "artifacts" / "archive"
        archive.mkdir()
        archived = archive / "build-plan-old.md"
        archived.write_text(self.STATUS_INSTRUCTION, encoding="utf-8")

        assert _comment_edits(repo) == []
        assert "views_enabled" in archived.read_text()


class TestFreezeReleaseNotes:
    def test_adds_the_notice_and_keeps_the_content(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        notes = repo / ".prawduct" / "release-notes.md"
        notes.write_text("# Release Notes\n\n## v1.0.0\n\nShipped a thing.\n", "utf-8")

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = notes.read_text()
        assert lifecycle_repair.FROZEN_MARKER in text
        assert "Shipped a thing." in text

    def test_an_already_frozen_file_is_left_alone(self, tmp_path: Path) -> None:
        """Re-freezing would stack a second banner on a repo that froze by hand."""
        repo = _make_repo(tmp_path)
        notes = repo / ".prawduct" / "release-notes.md"
        notes.write_text(f"# Notes — {lifecycle_repair.FROZEN_MARKER}\n\nold\n", "utf-8")
        before = notes.read_bytes()

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        assert notes.read_bytes() == before


class TestUnreadableFilesAreNotSilentlySkipped:
    """A file that could not be read must never report as a file with nothing wrong.

    Every finding this repair was built to fix has the same shape — a path that
    cannot answer, reporting as one that answered — so the repair silently
    skipping a plan it could not decode and then printing "already in the target
    state" was the same defect one level up. An unreadable plan may hold the one
    piece of residue that still changes behaviour.
    """

    def test_an_unreadable_plan_is_collected_not_skipped(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, state="project: demo\n")
        bad = repo / ".prawduct" / "artifacts" / "build-plan-bad.md"
        bad.write_bytes(b"---\nartifact: build-plan\nscope: bad\n---\n\xff\xfe\x00")

        plan = lifecycle_repair.plan_repair(repo)
        assert [item["path"] for item in plan["unreadable"]] == [str(bad)]

    def test_a_converged_repo_reports_no_unreadable_files(self, tmp_path: Path) -> None:
        """The other half — without this, the assertion above passes on a list
        that is never empty and the key would say nothing."""
        repo = _make_repo(tmp_path, state="project: demo\n")
        assert lifecycle_repair.plan_repair(repo)["unreadable"] == []

    def test_an_unreadable_release_notes_is_collected(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, state="project: demo\n")
        notes = repo / ".prawduct" / "release-notes.md"
        notes.write_bytes(b"\xff\xfe\x00not text")

        plan = lifecycle_repair.plan_repair(repo)
        assert [item["path"] for item in plan["unreadable"]] == [str(notes)]
        # And no freeze edit is invented for a file whose content is unknown.
        assert [e for e in plan["edits"] if e["kind"] == "freeze-notes"] == []


class TestRetiredFlagGuard:
    """GD2 — the flag coming back, typically by copying an older state file."""

    def test_detects_the_flag_and_names_its_line(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        result = lifecycle_repair.views_flag_present(repo)
        assert result["status"] == "present"
        assert result["line"] == 8

    def test_clean_repo_reports_ok(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, state="project: demo\n")
        assert lifecycle_repair.views_flag_present(repo)["status"] == "ok"

    def test_unreadable_state_is_not_reported_as_clean(self, tmp_path: Path) -> None:
        """A check that could not run must never be indistinguishable from one
        that ran and found nothing."""
        repo = _make_repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_bytes(b"\xff\xfe\x00bad")
        assert lifecycle_repair.views_flag_present(repo)["status"] == "unreadable"


class TestStaleStatusReport:
    """FL3 — report only, and only for plans that stay live."""

    DERIVED_WITH_UNTICKED = """\
---
artifact: build-plan
scope: demo
---

## Status

<!-- Derived view (`views_enabled: true`). Do not hand-edit. -->

- [x] Chunk 01: shipped
- [ ] Chunk 02: in flight

## Build Chunks
"""

    def test_names_the_plan_and_the_unticked_chunks(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_plan(repo, "build-plan-demo.md", self.DERIVED_WITH_UNTICKED)
        reports = lifecycle_repair.stale_status_reports(repo / ".prawduct" / "artifacts")

        assert len(reports) == 1
        assert reports[0]["chunks"] == ["Chunk 02: in flight"]

    def test_writes_nothing(self, tmp_path: Path) -> None:
        """The prohibition is the requirement, so it is asserted on the bytes."""
        repo = _make_repo(tmp_path)
        plan_path = _write_plan(repo, "build-plan-demo.md", self.DERIVED_WITH_UNTICKED)
        before = plan_path.read_bytes()

        lifecycle_repair.stale_status_reports(repo / ".prawduct" / "artifacts")
        assert plan_path.read_bytes() == before

    def test_silent_when_every_box_is_ticked(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        _write_plan(
            repo,
            "build-plan-demo.md",
            self.DERIVED_WITH_UNTICKED.replace("- [ ] Chunk 02", "- [x] Chunk 02"),
        )
        assert lifecycle_repair.stale_status_reports(repo / ".prawduct" / "artifacts") == []

    def test_silent_for_a_plan_that_never_carried_the_instruction(self, tmp_path: Path) -> None:
        """A hand-authored plan's unticked chunk is ordinary in-flight work, not
        a derived block that may be stale — reporting it would never go quiet."""
        repo = _make_repo(tmp_path)
        _write_plan(
            repo,
            "build-plan-demo.md",
            "---\nartifact: build-plan\nscope: demo\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: in flight\n",
        )
        assert lifecycle_repair.stale_status_reports(repo / ".prawduct" / "artifacts") == []


class TestTheFilesOwnBytesSurvive:
    """A repair that promises to remove two keys must remove two keys.

    Both defects here produced a whole-file diff in a product's *hand-authored*
    governance state, and both were invisible to every fixture in this file
    because the fixtures are LF and start with an ordinary key.
    """

    CRLF_STATE = (
        "project: demo\r\n\r\n"
        "# =============================================================================\r\n"
        "# DERIVED VIEWS\r\n"
        "# =============================================================================\r\n\r\n"
        "views_enabled: true\r\n\r\n"
        "coverage_required: false\r\n"
    )

    def test_crlf_line_endings_are_preserved(self, tmp_path: Path) -> None:
        """Reading without ``newline=""`` turns a CRLF file into an LF one on the
        way back out — nine CRLF lines became zero, and the real change hides
        inside a whole-file reformat."""
        repo = _make_repo(tmp_path, state=self.CRLF_STATE)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        raw = (repo / ".prawduct" / "project-state.yaml").read_bytes()

        assert raw == b"project: demo\r\n\r\ncoverage_required: false\r\n"
        assert raw.count(b"\n") == raw.count(b"\r\n"), "a bare LF appeared in a CRLF file"

    def test_the_frozen_banner_matches_the_files_endings(self, tmp_path: Path) -> None:
        """Prepending LF text to a CRLF document produces a file with two
        conventions in it, which is worse than either."""
        repo = _make_repo(tmp_path, state=self.CRLF_STATE)
        notes = repo / ".prawduct" / "release-notes.md"
        notes.write_bytes(b"# Release Notes\r\n\r\n## v1.0.0\r\n\r\nshipped\r\n")

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        raw = notes.read_bytes()
        assert lifecycle_repair.FROZEN_MARKER.encode() in raw
        assert raw.count(b"\n") == raw.count(b"\r\n"), "banner mixed LF into a CRLF file"

    def test_the_documents_own_header_is_not_taken_with_the_key(
        self, tmp_path: Path
    ) -> None:
        """The comment walk-back had no upper bound, so when the retired key was
        the FIRST key in the file it removed the document's opening block — the
        sentence naming the file as the product's source of truth."""
        header_first = (
            "# =============================================================================\n"
            "# PROJECT STATE — the source of truth for this product\n"
            "# Hand-authored. Every key below is read by some gate.\n"
            "# =============================================================================\n\n"
            "views_enabled: true\n\n"
            "project: demo\n"
        )
        repo = _make_repo(tmp_path, state=header_first)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "views_enabled" not in text
        assert "the source of truth for this product" in text, "ate the document header"
        assert "project: demo" in text

    def test_a_section_banner_IS_still_taken_with_its_key(self, tmp_path: Path) -> None:
        """The control — bounding the walk must not stop it doing its job, or a
        heading is left standing over a hole."""
        repo = _make_repo(tmp_path)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "DERIVED VIEWS" not in text
        assert "SCOPE ROLLUPS" not in text


class TestCrlfSurvivesTheCommentStripToo:
    """The third edit kind. Structurally identical to the other two, but the
    fixture that would have caught the original defect did not exist for it."""

    def test_stripping_a_status_note_keeps_crlf(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, state="project: demo\n")
        plan = repo / ".prawduct" / "artifacts" / "build-plan-demo.md"
        plan.write_bytes(
            b"---\r\nartifact: build-plan\r\nscope: demo\r\n---\r\n\r\n"
            b"## Status\r\n\r\n"
            b"<!-- Derived view (`views_enabled: true`). Do not hand-edit. -->\r\n\r\n"
            b"- [x] Chunk 01: done\r\n"
        )

        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        raw = plan.read_bytes()

        assert b"views_enabled" not in raw
        assert b"- [x] Chunk 01: done\r\n" in raw
        assert raw.count(b"\n") == raw.count(b"\r\n"), "a bare LF appeared in a CRLF plan"
