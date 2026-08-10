"""Tests for `lib/change_log.py` — reading and validating change-log tag lines.

Moved here from `test_views.py` when the parser left the derived-view module.
They are the contract for the tag format: what a tag line means, what a
malformed one costs, and which failures the release gate must refuse.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import change_log  # noqa: E402


def version_sort_key(version: str) -> tuple:
    """Sort key for a bare version string (no leading ``v``).

    Real versions sort numerically. Anything unparseable sorts ABOVE every real
    one, so a malformed stamp cannot hide under a larger numeric neighbour — a
    malformed stamp is the thing being looked for, not noise to be tolerated.
    """
    parts = version.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return (1, version)
    return (0, tuple(int(p) for p in parts))


def explain_empty_pending(stamped: set[str], version: str) -> str | None:
    """``None`` when an empty release-pending side is explained, else why not.

    Module level, and tested directly by :class:`TestExplainEmptyPending`,
    because the caller that matters only reaches it when the repo has *just cut
    a release* — a state the suite is in for a few commits every few weeks. Left
    inline it would have been unreachable code between cuts, and the first run
    that exercised it would be a release. That is the same shape as the defect
    this whole change exists to repair, one level down: a guard whose only
    exercise is the rare event it guards.
    """
    if not stamped:
        return "nothing is release-pending and nothing is stamped — release= is unreadable"
    newest = max(stamped, key=version_sort_key)
    if newest == version:
        return None
    return (
        f"nothing is release-pending, so the newest release= stamp should be this "
        f"repo's own version (v{version}) — but it is v{newest}. An empty pending "
        f"side is only explained by a just-cut release; a stamp ahead of, or "
        f"unparseable against, what the repo claims is drift. "
        f"Stamped versions: {sorted(stamped, key=version_sort_key)}"
    )


class TestParseTagLine:
    def test_simple_pairs(self):
        tags = change_log.parse_tag_line("release=v1.4.0 | status=shipped")
        assert tags == {"release": "v1.4.0", "status": "shipped"}

    def test_chunks_split_into_list(self):
        tags = change_log.parse_tag_line("chunks=00,01,02 | status=shipped")
        assert tags["chunks"] == ["00", "01", "02"]
        assert tags["status"] == "shipped"

    def test_single_chunk_still_a_list(self):
        tags = change_log.parse_tag_line("chunks=05")
        assert tags["chunks"] == ["05"]

    def test_extra_whitespace_tolerated(self):
        tags = change_log.parse_tag_line("  chunks = 00 , 01  |  status = shipped  ")
        assert tags["chunks"] == ["00", "01"]
        assert tags["status"] == "shipped"

    def test_unknown_keys_preserved(self):
        tags = change_log.parse_tag_line("custom=foo | release=v1.4.0")
        assert tags["custom"] == "foo"
        assert tags["release"] == "v1.4.0"

    def test_empty_pairs_skipped(self):
        tags = change_log.parse_tag_line("status=shipped | | release=v1.4")
        assert tags == {"status": "shipped", "release": "v1.4"}

    def test_malformed_pair_without_equals_skipped(self):
        tags = change_log.parse_tag_line("status=shipped | broken | release=v1.4")
        assert tags == {"status": "shipped", "release": "v1.4"}


class TestParseChangeLog:
    def test_tag_line_directly_after_h2(self):
        content = textwrap.dedent(
            """\
            # Change Log

            ## 2026-05-18: v1.4 Wave 1 (v1.3.17)
            <!-- prawduct: chunks=00,01 | release=v1.3.17 | status=shipped -->

            **Why:** ...
            """
        )
        entries = change_log.parse_change_log(content)
        assert len(entries) == 1
        assert entries[0].title.startswith("2026-05-18:")
        assert entries[0].tags["chunks"] == ["00", "01"]
        assert entries[0].tags["status"] == "shipped"

    def test_tag_line_after_blank_line(self):
        content = textwrap.dedent(
            """\
            ## 2026-05-18: Release

            <!-- prawduct: chunks=03 | status=shipped -->

            Body.
            """
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags.get("chunks") == ["03"]

    def test_untagged_entry_has_empty_tags(self):
        content = textwrap.dedent(
            """\
            ## 2026-04-01: Old entry

            **Why:** Pre-tagging era.
            """
        )
        entries = change_log.parse_change_log(content)
        assert len(entries) == 1
        assert entries[0].tags == {}

    def test_multiple_entries(self):
        content = textwrap.dedent(
            """\
            ## 2026-05-18: New entry
            <!-- prawduct: chunks=05 | status=shipped -->

            ## 2026-05-10: Older entry
            <!-- prawduct: chunks=01 | status=shipped -->

            ## 2026-05-01: Untagged
            """
        )
        entries = change_log.parse_change_log(content)
        assert len(entries) == 3
        # The retired `chunks=`/`status=` keys still PARSE — asserted on the
        # tags directly since the `shipped_chunks` property that composed them
        # went with its only caller. Historical entries must keep round-tripping.
        assert entries[0].tags["chunks"] == ["05"]
        assert entries[0].tags["status"] == "shipped"
        assert entries[1].tags["chunks"] == ["01"]
        assert entries[2].tags == {}

    def test_body_paragraph_before_tag_line_blocks_parse(self):
        """If a prose paragraph appears before the tag line, the tag line is not
        an entry header — it's later body content. parse_change_log only looks
        forward from the H2 to the first non-blank line."""
        content = textwrap.dedent(
            """\
            ## 2026-05-18: Entry

            **Why:** This entry has no tag line.

            <!-- prawduct: chunks=99 | status=shipped -->
            """
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags == {}

    def test_an_unrecognized_status_value_still_parses(self):
        """No validator rejects a `status=` value anymore — the one that did
        went with its only caller — so an arbitrary value must survive the
        parse rather than be dropped."""
        content = "## X\n<!-- prawduct: chunks=07 | status=in-progress -->\n"
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["07"]
        assert entries[0].tags["status"] == "in-progress"


class TestParseChangeLogMultiTagLines:
    """Multiple consecutive tag lines per entry are unioned, not dropped.

    VWS-4D8J: the historical parse settled tag-vs-no-tag at the FIRST non-blank
    line, so a second `<!-- prawduct: ... -->` line was silently ignored — at
    the v2.1.0 release the reviewer-model-tiering `chunks=02` tag nearly
    shipped unflipped. Consecutive tag lines now merge (chunks union,
    first-wins scalars) and the multiplicity is recorded for the validator.
    """

    def test_consecutive_tag_lines_union_chunks(self):
        content = textwrap.dedent(
            """\
            ## 2026-06-09: Reviewer model tiering
            <!-- prawduct: chunks=01 | status=shipped | scope=tiering -->
            <!-- prawduct: chunks=02 | status=shipped | scope=tiering -->

            Body.
            """
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].tag_line_count == 2
        assert entries[0].tag_conflicts == []

    def test_duplicate_chunk_ids_deduped_order_preserving(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=02,01 -->\n"
            "<!-- prawduct: chunks=01,03 -->\n"
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["02", "01", "03"]

    def test_conflicting_scalar_keeps_first_and_records_conflict(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: chunks=02 | status=merged -->\n"
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["status"] == "shipped"
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].tag_conflicts == ["status: kept 'shipped', ignored 'merged'"]

    def test_same_scalar_value_on_both_lines_is_not_a_conflict(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | scope=v9 -->\n"
            "<!-- prawduct: chunks=02 | scope=v9 -->\n"
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tag_conflicts == []

    def test_new_key_on_second_line_adopted(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: release=v2.1.0 -->\n"
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["release"] == "v2.1.0"

    def test_blank_line_between_tag_lines_tolerated(self):
        content = textwrap.dedent(
            """\
            ## X

            <!-- prawduct: chunks=01 -->

            <!-- prawduct: chunks=02 -->

            Body.
            """
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].tag_line_count == 2

    def test_tag_line_after_prose_still_not_consumed(self):
        content = textwrap.dedent(
            """\
            ## X
            <!-- prawduct: chunks=01 -->

            **Why:** body prose.

            <!-- prawduct: chunks=99 -->
            """
        )
        entries = change_log.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01"]
        assert entries[0].tag_line_count == 1

    def test_tag_line_count_zero_for_untagged_entry(self):
        entries = change_log.parse_change_log("## X\n\nBody only.\n")
        assert entries[0].tag_line_count == 0

    def test_next_h2_ends_the_tag_block(self):
        content = (
            "## Newer\n"
            "<!-- prawduct: chunks=01 -->\n"
            "## Older\n"
            "<!-- prawduct: chunks=02 -->\n"
        )
        entries = change_log.parse_change_log(content)
        assert len(entries) == 2
        assert entries[0].tags["chunks"] == ["01"]
        assert entries[1].tags["chunks"] == ["02"]


class TestValidateChangeLogTags:
    """The merged validator, and the three shapes it refuses or reports.

    It replaces `validate_release_values`, `validate_tag_conflicts` and
    `validate_tag_line_multiplicity`, whose only caller was the derived-view
    regenerator. The split between error and warning is the contract: an error
    means the release gate must fail closed, a warning means report and proceed.
    """

    # --- release= value format -------------------------------------------------
    #
    # A `release=` that isn't a version hides its whole scope from the release.
    # The unreleased set is every entry tagged `scope=` with NO `release=`, so
    # any value at all — a placeholder most of all — marks the entry
    # already-released and drops its scope from `check-releasability`.

    def test_placeholder_release_is_an_error(self):
        entries = [
            change_log.ChangeLogEntry(
                title="2026-08-07: cache",
                tags={"scope": "backlog-cache", "release": "unreleased"},
            )
        ]
        errors, warnings = change_log.validate_change_log_tags(entries)
        assert len(errors) == 1
        assert "unreleased" in errors[0]
        assert warnings == []

    def test_version_release_is_clean(self):
        entries = [
            change_log.ChangeLogEntry(title="ok", tags={"release": "v3.2.7"}),
            change_log.ChangeLogEntry(title="ok", tags={"release": "v2.0.10"}),
            change_log.ChangeLogEntry(title="ok", tags={"release": "v1.3.16"}),
        ]
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_prerelease_suffix_is_clean(self):
        entries = [
            change_log.ChangeLogEntry(title="rc", tags={"release": "v3.2.8-rc.1"})
        ]
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_absent_release_is_the_pending_state_not_an_error(self):
        entries = [
            change_log.ChangeLogEntry(title="untagged", tags={}),
            change_log.ChangeLogEntry(
                title="release-pending", tags={"chunks": ["01"], "scope": "s"}
            ),
        ]
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_other_placeholders_and_malformed_versions(self):
        for bad in ("TBD", "next", "pending", "unknown", "3.2.7", "v3.2", "v3.2.x", ""):
            entries = [change_log.ChangeLogEntry(title="b", tags={"release": bad})]
            errors, _warnings = change_log.validate_change_log_tags(entries)
            assert len(errors) == 1, bad

    # --- conflicting tag lines -------------------------------------------------

    def test_conflicting_scalars_are_errors(self):
        entries = change_log.parse_change_log(
            "## X\n"
            "<!-- prawduct: status=shipped -->\n"
            "<!-- prawduct: status=merged -->\n"
        )
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert len(errors) == 1
        assert "first-wins" in errors[0]
        assert "ignored 'merged'" in errors[0]

    def test_union_without_conflict_is_not_an_error(self):
        # Multiple tag lines whose scalars AGREE (or don't overlap) union
        # cleanly — that is the multiplicity warning's business, not an error.
        entries = change_log.parse_change_log(
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: chunks=02 | status=shipped -->\n"
        )
        errors, warnings = change_log.validate_change_log_tags(entries)
        assert errors == []
        assert len(warnings) == 1

    # --- multiple tag lines ----------------------------------------------------

    def test_single_tag_line_is_silent(self):
        entries = change_log.parse_change_log(
            "## X\n<!-- prawduct: chunks=01 | status=shipped -->\n"
        )
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_untagged_entry_is_silent(self):
        entries = change_log.parse_change_log("## X\n\nBody.\n")
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_multi_tag_entry_warns_with_title_and_count(self):
        entries = change_log.parse_change_log(
            "## 2026-06-09: Tiering\n"
            "<!-- prawduct: chunks=01 -->\n"
            "<!-- prawduct: chunks=02 -->\n"
        )
        _errors, warnings = change_log.validate_change_log_tags(entries)
        assert len(warnings) == 1
        assert "2026-06-09: Tiering" in warnings[0]
        assert "2 prawduct tag lines" in warnings[0]
        assert "unioned" in warnings[0]

    def test_one_warning_per_multi_tag_entry(self):
        entries = change_log.parse_change_log(
            "## A\n<!-- prawduct: chunks=01 -->\n<!-- prawduct: chunks=02 -->\n"
            "## B\n<!-- prawduct: chunks=03 -->\n"
            "## C\n<!-- prawduct: chunks=04 -->\n<!-- prawduct: chunks=05 -->\n"
        )
        _errors, warnings = change_log.validate_change_log_tags(entries)
        assert len(warnings) == 2

    def test_a_conflict_is_both_an_error_and_a_multiplicity_warning(self):
        # The two findings are about different things — the union happened
        # (style), and it may have kept the wrong value (correctness) — so an
        # entry that trips both must report both rather than collapse them.
        entries = change_log.parse_change_log(
            "## X\n"
            "<!-- prawduct: release=v1.0.0 -->\n"
            "<!-- prawduct: release=v2.0.0 -->\n"
        )
        errors, warnings = change_log.validate_change_log_tags(entries)
        assert len(errors) == 1 and "first-wins" in errors[0]
        assert len(warnings) == 1 and "canonical format" in warnings[0]


class TestAgainstTheRealChangeLog:
    """Characterization: the tag-side properties that must survive `views.py`.

    DECISION-3 replaced an A-vs-B oracle with tests over real data, on the
    grounds that an oracle dies with the module it compares against. That
    argument obliges BOTH halves — the plan-side lives in `test_plan_index.py`,
    and this is the tag side. Every assertion here is a property of this repo's
    actual change log, so it keeps discriminating after the old parser is gone.

    Skipped when `.prawduct/change-log.md` is absent so the plugin's own suite
    still runs from a checkout without product state.
    """

    def _entries(self):
        log = Path(__file__).resolve().parents[1] / ".prawduct" / "change-log.md"
        if not log.is_file():
            pytest.skip("no .prawduct/change-log.md in this checkout")
        return change_log.parse_change_log(log.read_text(encoding="utf-8"))

    def test_the_real_log_parses_into_tagged_and_untagged_entries(self):
        entries = self._entries()
        tagged = [e for e in entries if e.tag_line_count > 0]
        untagged = [e for e in entries if e.tag_line_count == 0]
        # Both populations must be non-empty: a parser that stopped recognising
        # tag lines still returns every H2, and a parser that mistook prose for
        # a tag line still returns a plausible count. Only the SPLIT falsifies
        # either, which is why it is asserted rather than the total.
        assert tagged, "no tagged entries parsed — the tag-line reader is broken"
        assert untagged, "no untagged entries — historical entries went missing"

    def test_every_tagged_entry_has_a_line_number_pointing_at_its_heading(self):
        for entry in self._entries():
            if entry.tag_line_count == 0:
                continue
            assert entry.line_number > 0
            assert entry.title, entry.line_number

    def test_the_real_log_is_clean_under_the_validator(self):
        errors, _warnings = change_log.validate_change_log_tags(self._entries())
        assert errors == [], errors

    def test_release_tags_partition_into_released_and_pending(self):
        """The partition `check-releasability` acts on, on real data.

        A `release=` tag means shipped; its absence means release-pending. If
        this repo ever showed one side empty, the gate would be answering from
        a degenerate set — which is exactly the shape the v3.2.8 placeholder
        incident produced.

        **But an empty PENDING side is legitimate, and only sometimes.** Phase 1
        step 3 of the release runbook stamps `release=` on every shipping entry,
        so between that step and the next cycle's first change there is nothing
        left to cut — the runbook working as designed, not a broken reader. An
        earlier version asserted the pending side non-empty unconditionally and
        went red mid-release, under pressure to relax it.

        So the assertion says WHICH emptiness it rejects. `released` must be
        non-empty — a reader that stopped seeing `release=` still fails — and an
        empty pending side must be *explained*: the NEWEST `release=` stamp has
        to be the version `plugin/VERSION` claims. Equality, not membership: a
        set containing one current stamp beside a stale or fabricated one passes
        a membership check while being exactly the drift worth catching, and an
        unparseable stamp sorts above every real version rather than hiding
        under a larger neighbour. That is the shape the v3.2.8 placeholder
        incident actually had.

        **What this does not catch:** a log stamped entirely to a version BEHIND
        `plugin/VERSION` while the pending side is non-empty — the early return
        above skips the check, because a repo mid-cycle legitimately has its
        newest stamp one release back. This guard is about the post-cut state
        only; `check-releasability` grades the mid-cycle partition.

        Deliberately NOT asserted: that the two sides partition the entries
        totally and disjointly. They are built by complementary filters over one
        list, so no input can falsify it — the statement would read like a
        guarantee while measuring nothing, which is the failure this class
        exists to avoid. The partition is a property of this test's own two
        lines, not of the data; `check-releasability` does its own split and is
        graded where it lives.
        """
        entries = [e for e in self._entries() if e.tag_line_count > 0]
        released = [e for e in entries if e.tags.get("release")]
        pending = [e for e in entries if not e.tags.get("release")]

        assert released, "no released entries — release= is not being read"

        if pending:
            return

        version = (
            Path(__file__).resolve().parents[1] / "plugin" / "VERSION"
        ).read_text(encoding="utf-8").strip()
        stamped = {str(e.tags["release"]).removeprefix("v") for e in released}
        complaint = explain_empty_pending(stamped, version)
        assert complaint is None, complaint

    def test_every_scope_tag_is_a_non_empty_string(self):
        for entry in self._entries():
            scope = entry.tags.get("scope")
            if scope is None:
                continue
            assert isinstance(scope, str) and scope.strip(), (entry.title, scope)

    def test_every_log_scope_that_resolves_maps_to_a_plan_declaring_it(self):
        """The log→plan join, in the only form that is true of real history.

        The unrestricted property R-3 named — "every scope the log declares
        resolves to a plan file" — is FALSE here by design, and asserting it
        would pin a bug rather than a contract: a `status=shipped` scope whose
        plan predates the `scope:` frontmatter convention, or was retired, has
        no file, and `diagnose_scope_plan_coverage` deliberately does not flag
        that case. So the restricted form: of the log's scopes that DO resolve,
        every one maps to a plan that declares that same scope in its
        frontmatter. That is the property the two modules must agree on, and it
        is the one the branch's join actually relies on.

        The plan side is read WITH the archive, because that is the corpus the
        log describes: a change-log entry outlives the branch that produced it,
        and its plan is archived when the work ships. Joining against live plans
        alone made this assert "some logged scope is still in flight", which a
        release falsifies by archiving every shipped plan — and it shrank the
        corpus from every plan the repo has ever written to whatever this branch
        happens to be building.

        **What turns this red** (measured, not assumed): losing the plan corpus
        so the join goes empty — the half the archive read restores — and a
        resolver that returns a plan other than the one declaring the scope,
        which is the mis-attribution the join exists to catch. What it does not
        catch is a scope whose *value* is wrong in both places at once: the map
        keys through the same frontmatter parser this re-reads, so a consistent
        lie agrees with itself. That is a known limit of a self-join, recorded
        rather than papered over.
        """
        from lib import plan_index

        artifacts = Path(__file__).resolve().parents[1] / ".prawduct" / "artifacts"
        if not artifacts.is_dir():
            pytest.skip("no .prawduct/artifacts/ in this checkout")
        mapping = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)

        log_scopes = {
            e.tags["scope"]
            for e in self._entries()
            if isinstance(e.tags.get("scope"), str) and e.tags["scope"]
        }
        joined = log_scopes & set(mapping)
        # Non-emptiness first: an empty intersection would make the loop below
        # pass while asserting nothing, which is the failure this whole class
        # was rewritten to stop.
        assert joined, "no change-log scope resolves to a plan — the join is broken"
        for scope in sorted(joined):
            present, declared = plan_index.parse_build_plan_frontmatter_scope(
                mapping[scope].read_text(encoding="utf-8")
            )
            assert present and declared == scope, (scope, mapping[scope])


class TestExplainEmptyPending:
    """The post-cut branch of the release partition, exercised on every run.

    `test_release_tags_partition_into_released_and_pending` reaches this logic
    only when the real change log has nothing release-pending — true for a few
    commits after each cut and false the rest of the time. So the branch that
    decides whether an empty pending side is legitimate would, left to the real
    data alone, first execute during a release. These fixtures make it run every
    time, which is what the rule this change earned actually asks for: prove a
    guard can go red before believing it, rather than at the moment it matters.
    """

    def test_a_just_cut_release_is_explained(self):
        assert explain_empty_pending({"3.2.7", "3.3.0"}, "3.3.0") is None

    def test_a_stale_stamp_beside_a_current_one_is_not_explained(self):
        """The case a membership check waved through.

        `version in stamped` passes here — the repo's version IS present. Only
        comparing the NEWEST stamp catches a log carrying a version the repo
        does not claim, which is the drift the v3.2.8 placeholder incident had.
        """
        complaint = explain_empty_pending({"3.3.0", "9.9.9"}, "3.3.0")
        assert complaint and "v9.9.9" in complaint

    def test_a_log_stamped_entirely_behind_the_repo_is_not_explained(self):
        complaint = explain_empty_pending({"3.2.6", "3.2.7"}, "3.3.0")
        assert complaint and "v3.2.7" in complaint

    def test_an_unparseable_stamp_cannot_hide_under_a_numeric_neighbour(self):
        """`unreleased` sorts ABOVE 3.3.0, so it surfaces instead of being
        shadowed — the placeholder value is exactly what went undetected."""
        complaint = explain_empty_pending({"3.3.0", "unreleased"}, "3.3.0")
        assert complaint and "unreleased" in complaint

    def test_nothing_stamped_at_all_is_not_explained(self):
        assert explain_empty_pending(set(), "3.3.0") is not None

    def test_version_ordering_is_numeric_not_lexicographic(self):
        """`3.10.0` is newer than `3.9.0`; string comparison says otherwise, and
        this repo will reach a two-digit minor."""
        assert version_sort_key("3.10.0") > version_sort_key("3.9.0")
        assert explain_empty_pending({"3.9.0", "3.10.0"}, "3.10.0") is None
        assert explain_empty_pending({"3.9.0", "3.10.0"}, "3.9.0") is not None

    def test_differing_segment_counts_compare_without_error(self):
        assert version_sort_key("3.3") < version_sort_key("3.3.1")
        assert explain_empty_pending({"3.3", "3.3.1"}, "3.3.1") is None


class TestSameLineDuplicateKeys:
    """A key repeated WITHIN one tag line — the unguarded half of "set twice".

    Cross-line duplicates have been caught since `_merge_tag_line` existed. The
    same-line repeat was assigned last-wins into a bare dict with nothing
    recorded, so it reached `validate_change_log_tags` as a clean entry. CL6
    names duplicate-key as one of the three shapes the single validator must
    cover, and the incident behind that requirement — `release=unreleased` on
    six entries hiding a whole branch from a release — is a duplicate-key
    failure, so the gap sat directly under the requirement that closed it.
    """

    @staticmethod
    def _entry(tag_body: str):
        text = f"## 2026-08-10: a thing\n\n<!-- prawduct: {tag_body} -->\n\nbody\n"
        return change_log.parse_change_log(text)

    def test_a_repeated_scope_is_an_error_not_a_silent_reattribution(self):
        entries = self._entry("type=fix | scope=alpha | scope=beta")
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert errors, "scope= set twice on one line passed validation"
        assert "same key twice" in errors[0]
        # First-wins, matching the cross-line rule, so the resolution does not
        # depend on which side of a line break the repeat fell on.
        assert entries[0].tags["scope"] == "alpha"

    def test_a_repeated_release_cannot_launder_a_bad_value(self):
        """The exact CL6 shape: a placeholder followed by a real version.

        Under last-wins this parsed to `v3.2.8` and passed every check, so the
        malformed value that drops a scope out of the release-pending set was
        invisible. Both errors now fire — the duplicate and the placeholder.
        """
        entries = self._entry("scope=a | release=unreleased | release=v3.2.8")
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert len(errors) == 2, errors
        assert any("same key twice" in e for e in errors)
        assert any("not a version" in e for e in errors)

    def test_an_identical_repeat_is_tolerated(self):
        """Set twice to the SAME value is noise, not a conflict — nothing was
        lost and no reading is ambiguous. Matches `_merge_tag_line`, which
        records a conflict only on `existing != v`."""
        entries = self._entry("type=fix | scope=a | scope=a")
        errors, warnings = change_log.validate_change_log_tags(entries)
        assert errors == [] and warnings == []
        assert entries[0].tags["scope"] == "a"

    def test_the_message_does_not_tell_a_one_line_author_to_merge_lines(self):
        """The remedy differs by shape. A single tag line has nothing to merge,
        and the cross-line wording sends its author looking for a second line
        that is not there."""
        one_line = self._entry("scope=a | scope=b")
        errors, _ = change_log.validate_change_log_tags(one_line)
        assert "on its prawduct tag line" in errors[0]
        assert "tag lines" not in errors[0].split("(kept")[0].replace(
            "prawduct tag line", ""
        )

        two_lines = change_log.parse_change_log(
            "## 2026-08-10: t\n\n<!-- prawduct: scope=a -->\n"
            "<!-- prawduct: scope=b -->\n\nbody\n"
        )
        errors, _ = change_log.validate_change_log_tags(two_lines)
        assert "across its 2 prawduct tag lines" in errors[0]

    def test_the_real_change_log_has_no_same_line_duplicates(self):
        """Measured before shipping the error: zero across all 21 checkouts, so
        this turns nothing red that was green. Pinned here because the fleet is
        the thing the fixtures cannot represent."""
        log = Path(__file__).resolve().parents[1] / ".prawduct" / "change-log.md"
        if not log.is_file():
            pytest.skip("no .prawduct/change-log.md in this checkout")
        entries = change_log.parse_change_log(log.read_text(encoding="utf-8"))
        offenders = [e.title for e in entries if e.tag_conflicts]
        assert offenders == [], offenders
