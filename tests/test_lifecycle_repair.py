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


#: The shapes `build_state.test_tracking` actually takes, drawn from a survey of
#: every governed product carrying it (2026-08-14). They are fixtures rather than
#: one invented example because the block's membership is the whole risk: the
#: field it was named for is the *sole* member in exactly one product, and a
#: removal tuned to that one shape would leave the other seven untouched.
TT_SOLE_MEMBER = """\
project: demo

build_state:
  source_root: "app/"

  test_tracking:
    test_count: 27414  # 2026-08-14: python 23549 + web 3242 + activity 623
    # CORRECTED 2026-07-30: three successive edits recorded the *passed* tally
    #   instead of the collected count, leaving this field 26 low.

active_build_plan: artifacts/build-plan.md
"""

TT_WITH_SIBLINGS = """\
project: demo

build_state:
  source_root: "src/"

  test_tracking:
    test_count: 1724
    assertion_count: 4102
    test_files: 118
    history:
      - tests_added: 24
        date: 2026-08-14
      - tests_added: 11
        date: 2026-08-13

  spec_compliance: partial
  reviews:
    last: 2026-08-01

active_build_plan: artifacts/build-plan.md
"""


class TestRetiredTestTrackingBlock:
    """The block is removed whole, not member by member.

    Every member measured across the fleet — ``test_count``, ``assertion_count``,
    ``test_files``, and a ``history`` of per-chunk ``tests_added`` entries — is
    hand-maintained bookkeeping of a fact ``.test-evidence.json`` already holds,
    and nothing in the runtime reads any of them. Removing only the field the
    backlog item was named for would fully clean one product and leave the same
    treadmill running in seven.

    The mechanics differ from the two retired keys above in one way that matters:
    this key is **nested**, so neither the column-0 predicate nor the column-0
    block span applies to it.
    """

    def test_removes_the_whole_block_when_test_count_is_its_only_member(
        self, tmp_path: Path
    ) -> None:
        repo = _make_repo(tmp_path, state=TT_SOLE_MEMBER)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "test_tracking" not in text
        assert "test_count" not in text
        # The trailing provenance comments live INSIDE the block, indented under
        # it. A span that stopped at the last `key: value` line would leave them
        # orphaned under `source_root`, attributing them to the wrong key.
        assert "CORRECTED" not in text

    def test_removes_the_whole_block_when_it_carries_other_members(
        self, tmp_path: Path
    ) -> None:
        """The case the parent item originally carved out.

        ``history`` nests a list of mappings two levels deeper than the key, so a
        span that stopped at the first line back at the members' indent would cut
        the block in half and leave a bare ``- tests_added:`` list behind.
        """
        repo = _make_repo(tmp_path, state=TT_WITH_SIBLINGS)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        for member in ("test_tracking", "test_count", "assertion_count", "test_files"):
            assert member not in text, f"{member} survived the block removal"
        assert "tests_added" not in text
        assert "2026-08-13" not in text

    def test_the_blocks_siblings_survive(self, tmp_path: Path) -> None:
        """``source_root`` is the reason the parent is never left empty.

        It is read in ten places and sits *beside* ``test_tracking`` under
        ``build_state``, never inside it. ``spec_compliance`` and ``reviews``
        follow the block, so a span walking too far forward takes them.
        """
        repo = _make_repo(tmp_path, state=TT_WITH_SIBLINGS)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "build_state:" in text
        assert 'source_root: "src/"' in text
        assert "spec_compliance: partial" in text
        assert "reviews:" in text
        assert "last: 2026-08-01" in text
        assert "active_build_plan: artifacts/build-plan.md" in text

    def test_a_test_tracking_under_some_other_parent_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        """The nested predicate resolves the ENCLOSING key, not the name.

        This is the nested restatement of ``_is_top_level_key``'s own rule: a key
        under a mapping this repair knows nothing about belongs to that mapping.
        """
        repo = _make_repo(
            tmp_path,
            state=(
                "project: demo\n"
                "vendor_metrics:\n"
                "  test_tracking:\n"
                "    test_count: 9\n"
                "build_state:\n"
                '  source_root: "src/"\n'
            ),
        )
        assert lifecycle_repair.plan_repair(repo)["edits"] == []

    def test_a_top_level_test_tracking_is_left_alone(self, tmp_path: Path) -> None:
        """No product writes one, and inventing a removal for a shape nothing has
        is how a repair acquires a blast radius nobody reviewed."""
        repo = _make_repo(
            tmp_path, state="project: demo\ntest_tracking:\n  test_count: 9\n"
        )
        assert lifecycle_repair.plan_repair(repo)["edits"] == []

    def test_the_span_does_not_depend_on_the_blocks_size(
        self, tmp_path: Path
    ) -> None:
        """The worst real instance is 343 lines, one of them 52 KB.

        Nothing in the span logic is length-sensitive, so this pins the property
        rather than the instance: a block an order of magnitude larger, with a
        pathologically long line in it, is still bounded by the first line back
        at the key's own indent.
        """
        body = "".join(f"    entry_{i}: {i}\n" for i in range(400))
        repo = _make_repo(
            tmp_path,
            state=(
                "build_state:\n"
                '  source_root: "src/"\n'
                "  test_tracking:\n"
                "    test_count: 27414  # " + ("x" * 50_000) + "\n"
                + body
                + "  spec_compliance: partial\n"
            ),
        )
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "test_tracking" not in text
        assert "entry_399" not in text, "the span stopped short of the block's end"
        assert "x" * 100 not in text
        assert 'source_root: "src/"' in text
        assert "spec_compliance: partial" in text

    def test_a_prose_mention_of_the_block_elsewhere_survives(
        self, tmp_path: Path
    ) -> None:
        """Found in a real product's state file, not imagined.

        One repo records, under an unrelated key, that *"build_state.test_tracking
        was stale (0 tests recorded vs 17 actual) — corrected during migration"*.
        That is history about the field, held somewhere else; removing the field
        must not remove the record of what it cost. The predicate matches a key
        (``^\\s+test_tracking:``), never the name in a value, which is what makes
        this hold — so it is pinned rather than left to that detail.
        """
        note = (
            '        - description: "build_state.test_tracking was stale '
            '(0 recorded vs 17 actual) — corrected during migration"\n'
        )
        repo = _make_repo(
            tmp_path,
            state=(
                "build_state:\n"
                '  source_root: "src/"\n'
                "  test_tracking:\n"
                "    test_count: 18\n\n"
                "migration_notes:\n"
                "  entries:\n"
                "    - date: 2026-01-01\n"
                "      findings:\n" + note
            ),
        )
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "  test_tracking:\n" not in text, "the block itself survived"
        assert "test_count" not in text
        assert "corrected during migration" in text, "ate a record of the field's cost"

    def test_running_twice_changes_nothing_the_second_time(
        self, tmp_path: Path
    ) -> None:
        repo = _make_repo(tmp_path, state=TT_WITH_SIBLINGS)
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        after_first = (repo / ".prawduct" / "project-state.yaml").read_bytes()

        second = lifecycle_repair.plan_repair(repo)
        assert second["edits"] == []
        lifecycle_repair.apply_repair(repo, second)
        assert (repo / ".prawduct" / "project-state.yaml").read_bytes() == after_first

    def test_the_section_banner_above_the_block_goes_with_it(
        self, tmp_path: Path
    ) -> None:
        """The comment walk-back is reused unchanged, and its bound still holds:
        it stops at ``source_root``, which is content."""
        repo = _make_repo(
            tmp_path,
            state=(
                "project: demo\n\n"
                "build_state:\n"
                '  source_root: "src/"\n\n'
                "  # ---------------------------------------------------------\n"
                "  # TEST TRACKING — hand-maintained, corrected on every merge\n"
                "  # ---------------------------------------------------------\n"
                "  test_tracking:\n"
                "    test_count: 1724\n\n"
                "  spec_compliance: partial\n"
            ),
        )
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        assert "TEST TRACKING" not in text, "a heading left standing over a hole"
        assert 'source_root: "src/"' in text
        assert "spec_compliance: partial" in text

    def test_it_coexists_with_the_two_column_zero_removals(
        self, tmp_path: Path
    ) -> None:
        """Removals are applied in descending order so one cannot shift another's
        indices. A nested span lands between the two column-0 ones here, which is
        the ordering case a single-key fixture cannot reach."""
        repo = _make_repo(
            tmp_path,
            state=(
                "project: demo\n\n"
                "views_enabled: true\n\n"
                "build_state:\n"
                '  source_root: "src/"\n'
                "  test_tracking:\n"
                "    test_count: 1724\n\n"
                "scope_rollups:\n"
                "  alpha:\n"
                '    chunks: ["01"]\n\n'
                "trailing_key: kept\n"
            ),
        )
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        text = (repo / ".prawduct" / "project-state.yaml").read_text()

        for gone in ("views_enabled", "scope_rollups", "test_tracking", "test_count"):
            assert gone not in text
        assert "project: demo" in text
        assert 'source_root: "src/"' in text
        assert "trailing_key: kept" in text

    def test_crlf_line_endings_are_preserved(self, tmp_path: Path) -> None:
        """The nested span is a new caller of the same write path, so it inherits
        the obligation the module already carries: a repair that promises to
        remove one block must not rewrite every line in a product's file."""
        repo = _make_repo(
            tmp_path,
            state=(
                "project: demo\r\n\r\n"
                "build_state:\r\n"
                '  source_root: "src/"\r\n'
                "  test_tracking:\r\n"
                "    test_count: 1724\r\n\r\n"
                "trailing_key: kept\r\n"
            ),
        )
        lifecycle_repair.apply_repair(repo, lifecycle_repair.plan_repair(repo))
        raw = (repo / ".prawduct" / "project-state.yaml").read_bytes()

        assert b"test_tracking" not in raw
        assert b'source_root: "src/"' in raw
        assert raw.count(b"\n") == raw.count(b"\r\n"), "a bare LF appeared in a CRLF file"

    def test_the_reason_names_where_the_fact_actually_lives(
        self, tmp_path: Path
    ) -> None:
        """An operator reading the preview decides on the reason text alone.

        "Nothing reads it" is not actionable on its own — the answer they need is
        what to consult instead, which is why the reason names the evidence store.
        """
        repo = _make_repo(tmp_path, state=TT_SOLE_MEMBER)
        edits = [
            edit
            for edit in lifecycle_repair.plan_repair(repo)["edits"]
            if edit["kind"] == "state-key"
        ]
        assert len(edits) == 1
        assert "evidence" in edits[0]["reason"].lower()


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
