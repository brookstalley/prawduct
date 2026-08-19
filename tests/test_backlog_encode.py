"""Tests for lib/backlog/encode.py — block parse/serialize, soft enums, decode.

Covers the Chunk-01 encoding subset: ENC-1 (soft-enum tolerance), ENC-3
(exactly-one block, last-block-wins), ENC-4 (tolerant parse, unknown keys
preserved verbatim), plus the decode precedence the two-axis keystone builds on.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import encode  # noqa: E402


class TestSoftEnumTolerance:
    """ENC-1 — unknown soft value flagged, never rejected; unknown status rejected."""

    def test_the_buildable_stage_is_one_of_the_stages(self):
        """`READY_STAGE` is written out rather than derived from the ladder, so a
        rung added past `ready` cannot silently become the buildable one. That
        deliberate non-derivation is what needs a test: nothing else would notice
        the constant drifting off the vocabulary it names a member of."""
        assert encode.READY_STAGE in encode.STAGE_VALUES

    def test_unknown_stage_is_warned_not_rejected(self):
        result = encode.check_enum("stage", "brainstorming")
        assert result.ok
        assert result.warning and "brainstorming" in result.warning

    def test_known_stage_is_clean(self):
        result = encode.check_enum("stage", "ready")
        assert result.ok
        assert result.warning is None

    def test_open_facet_accepts_any_value_no_warning(self):
        # `kind` is an open soft enum (scriob's 158 items) — no vocabulary to miss.
        result = encode.check_enum("kind", "anything-goes")
        assert result.ok
        assert result.warning is None

    def test_unknown_status_is_hard_reject(self):
        result = encode.check_enum("status", "frozen")
        assert not result.ok
        assert result.message and "frozen" in result.message

    def test_known_status_ok(self):
        assert encode.check_enum("status", "in-progress").ok


class TestBlockParse:
    """ENC-3 / ENC-4 — last-block-wins, tolerant parse, verbatim round-trip."""

    def test_no_block_is_empty_defaults(self):
        block = encode.parse_block("just a body, no block")
        assert block.fields == {}
        assert block.warnings == []
        assert block.version() == 1
        assert block.id_aliases() == []

    def test_two_blocks_last_wins_and_flags_earlier(self):
        body = (
            "intro\n"
            "```prawduct\n"
            "v: 1\n"
            "id_aliases: [OLD-0001]\n"
            "```\n"
            "middle\n"
            "```prawduct\n"
            "v: 1\n"
            "id_aliases: [NEW-0002]\n"
            "```\n"
        )
        block = encode.parse_block(body)
        assert block.id_aliases() == ["NEW-0002"]
        assert any("prawduct blocks" in w for w in block.warnings)

    def test_unknown_key_preserved_verbatim_on_round_trip(self):
        body = (
            "```prawduct\n"
            "v: 1\n"
            "future_key: some-unrecognized-value\n"
            "id_aliases: [BKL-7M4Q]\n"
            "```\n"
        )
        block = encode.parse_block(body)
        assert block.get("future_key") == "some-unrecognized-value"
        reserialized = block.reserialize()
        assert "future_key: some-unrecognized-value" in reserialized
        # A second parse of the re-serialized block preserves the unknown key.
        again = encode.parse_block(reserialized)
        assert again.get("future_key") == "some-unrecognized-value"

    def test_missing_key_takes_default(self):
        block = encode.parse_block("```prawduct\nid_aliases: [A-1]\n```\n")
        assert block.version() == 1  # 'v' absent → default

    def test_malformed_line_skipped_with_warning_not_error(self):
        block = encode.parse_block(
            "```prawduct\nv: 1\nthis line has no separator\n```\n"
        )
        assert block.version() == 1
        assert any("malformed block line" in w for w in block.warnings)

    def test_value_containing_hash_is_not_truncated(self):
        # `superseded_by` values contain '#'; naive comment-stripping would corrupt them.
        block = encode.parse_block(
            "```prawduct\nv: 1\nsuperseded_by: octo/repo#123\n```\n"
        )
        assert block.get("superseded_by") == "octo/repo#123"


class TestComposeBodyMergesAnEmbeddedBlock:
    """A filer's own `prawduct:` block survives filing instead of being buried.

    THE REPRODUCTION. Filing writes a fresh `v: 1` block onto the caller's body,
    and the caller's body is where a filer declares `related:` — the docs tell
    them to. The old `compose_body` appended, producing two blocks; parsing is
    last-block-wins, so the filer's fields were dropped and the loss surfaced
    only as a warning that reads cosmetic ("carries 2 prawduct blocks; using the
    last"). Items #690, #691 and #692 all lost their `related:` edges this way
    on 2026-08-19, and nothing failed.
    """

    def test_a_filer_supplied_block_yields_exactly_one_block(self):
        body = "Why this matters.\n\n```prawduct\nv: 1\nrelated: [owner/repo#7]\n```"
        out = encode.compose_body(body, {"v": "1"})
        assert out.count("```prawduct") == 1, (
            f"composition emitted {out.count('```prawduct')} blocks; a second one "
            "makes the first unreadable, because parsing is last-block-wins"
        )

    def test_the_filers_own_fields_survive(self):
        body = "Why.\n\n```prawduct\nv: 1\nrelated: [owner/repo#7]\n```"
        out = encode.compose_body(body, {"v": "1"})
        # Asserted through the PARSER, not by grepping the text: the defect was
        # that a field present in the body was invisible to the reader, so a
        # substring check on the raw body would have passed against it.
        assert encode.parse_block(out).get("related") == "[owner/repo#7]", (
            "the filer's `related:` edge did not survive composition — this is "
            "the exact loss that silently stripped #690/#691/#692"
        )

    def test_the_human_text_is_kept_once(self):
        body = "Why this matters.\n\n```prawduct\nv: 1\nrelated: [owner/repo#7]\n```"
        out = encode.compose_body(body, {"v": "1"})
        assert out.count("Why this matters.") == 1
        assert "```prawduct" not in out.split("Why this matters.")[0]

    def test_two_embedded_blocks_both_survive(self):
        """The residual loss the first fix left — and made silent.

        `parse_block` keeps only the LAST block while `strip_block` removes them
        all, so merging via `parse_block` still dropped an earlier block's
        fields. Worse than before: composition now emits exactly one block, so
        the downstream "carries N prawduct blocks" warning — the only signal the
        2026-08-19 losses ever produced — could never fire again. Merging every
        block means nothing is lost, which beats restoring a warning about a
        loss.
        """
        body = (
            "Why.\n\n```prawduct\nv: 1\nrelated: [owner/repo#7]\n```\n\n"
            "More prose.\n\n```prawduct\nv: 1\nrefs: [owner/repo#9]\n```"
        )
        out = encode.compose_body(body, {"v": "1"})
        assert out.count("```prawduct") == 1
        block = encode.parse_block(out)
        assert block.get("related") == "[owner/repo#7]", (
            "the EARLIER block's field was dropped — last-block-wins reasserted "
            "itself through the merge, and now with no warning at all"
        )
        assert block.get("refs") == "[owner/repo#9]"

    def test_a_later_block_wins_a_collision_between_two(self):
        """Merging all blocks must not invent a new precedence: last still wins,
        matching `parse_block`'s own rule, so the two cannot disagree about which
        value a body means.
        """
        body = (
            "```prawduct\nv: 1\nrelated: [owner/repo#1]\n```\n\n"
            "```prawduct\nv: 1\nrelated: [owner/repo#2]\n```"
        )
        out = encode.compose_body(body, {"v": "1"})
        assert encode.parse_block(out).get("related") == "[owner/repo#2]"

    def test_a_body_cannot_claim_the_attribution_stamps(self):
        """The direction precedence alone does not cover.

        An ATTENDED create passes only `{"v": "1"}`, so a body that self-declared
        `automated: true` meets no colliding key and would survive a plain merge
        — misattributing a human's filing to a background sweep. `automated` and
        `worker` describe *who filed this*, which the filed text never gets to
        assert; every other block field is the filer's to set.
        """
        body = "Why.\n\n```prawduct\nv: 1\nautomated: true\nworker: ghost\nrelated: [owner/repo#7]\n```"
        out = encode.compose_body(body, {"v": "1"})
        block = encode.parse_block(out)
        assert block.get("automated") is None, (
            "a body declared itself automated on an attended create — a human's "
            "filing would be attributed to a sweep"
        )
        assert block.get("worker") is None
        # The filer's own field is untouched: this strips two keys, not the block.
        assert block.get("related") == "[owner/repo#7]"

    def test_the_fresh_fields_win_a_collision(self):
        """Precedence is not arbitrary: a body must not be able to launder an
        unattended create into looking human. `automated`/`worker` are the
        caller's authoritative stamps, so they override anything the body claims.
        """
        body = "Why.\n\n```prawduct\nv: 1\nautomated: false\nrelated: [owner/repo#7]\n```"
        out = encode.compose_body(body, {"v": "1", "automated": "true", "worker": "sweep"})
        block = encode.parse_block(out)
        assert block.get("automated") == "true", (
            "a body claiming `automated: false` overrode the caller's stamp — a "
            "background sweep could then be misattributed to a human"
        )
        assert block.get("worker") == "sweep"
        # ...and the non-colliding field still survives.
        assert block.get("related") == "[owner/repo#7]"

    def test_a_blockless_body_is_unchanged_in_behaviour(self):
        """The path everything else already used stays exactly as it was."""
        out = encode.compose_body("Just prose.", {"v": "1"})
        assert out.count("```prawduct") == 1
        assert out.startswith("Just prose.\n\n")


class TestBlockSerialize:
    def test_version_emitted_first(self):
        out = encode.serialize_block({"id_aliases": "[BKL-0001]", "v": "1"})
        lines = out.splitlines()
        assert lines[0] == "```prawduct"
        assert lines[1] == "v: 1"
        assert "id_aliases: [BKL-0001]" in lines
        assert lines[-1] == "```"


class TestDecodeStatus:
    """Decode precedence (Data Model §4) — the basis the self-heal keystone extends."""

    def test_open_no_status_label_is_open(self):
        status, warns = encode.decode_status({"state": "open"}, [])
        assert status == "open"
        assert warns == []

    def test_open_in_progress_label(self):
        status, _ = encode.decode_status({"state": "open"}, ["status:in-progress"])
        assert status == "in-progress"

    def test_open_multiple_status_labels_highest_wins_and_warns(self):
        status, warns = encode.decode_status(
            {"state": "open"}, ["status:submitted", "status:in-progress"]
        )
        assert status == "in-progress"
        assert any("multiple status labels" in w for w in warns)

    def test_closed_completed_is_shipped(self):
        status, _ = encode.decode_status(
            {"state": "closed", "state_reason": "completed"}, []
        )
        assert status == "shipped"

    def test_closed_not_planned_is_dropped(self):
        status, _ = encode.decode_status(
            {"state": "closed", "state_reason": "not_planned"}, []
        )
        assert status == "dropped"

    def test_closed_with_stray_status_label_warns(self):
        status, warns = encode.decode_status(
            {"state": "closed", "state_reason": "completed"}, ["status:in-progress"]
        )
        assert status == "shipped"
        assert any("status: label" in w for w in warns)

    def test_closed_unknown_reason_fails_open(self):
        status, warns = encode.decode_status(
            {"state": "closed", "state_reason": "some_future_reason"}, []
        )
        assert status == "dropped"
        assert any("state_reason" in w for w in warns)


class TestEncodeStatus:
    """The write-side status encoder (Data Model §4) and its ENC-2 round-trip."""

    def test_each_status_encodes_to_its_canonical_shape(self):
        assert encode.encode_status("submitted") == ("open", None, "status:submitted")
        assert encode.encode_status("open") == ("open", None, None)
        assert encode.encode_status("in-progress") == ("open", None, "status:in-progress")
        assert encode.encode_status("shipped") == ("closed", "completed", None)
        assert encode.encode_status("dropped") == ("closed", "not_planned", None)

    def test_closed_states_carry_no_status_label(self):
        # There is no status:shipped / status:dropped in the taxonomy — closed
        # states live in state_reason (Data Model §4).
        assert encode.canonical_status_label("shipped") is None
        assert encode.canonical_status_label("dropped") is None
        assert encode.canonical_status_label("open") is None
        assert encode.canonical_status_label("submitted") == "status:submitted"

    def test_enc2_encode_then_decode_round_trips_every_status(self):
        # ENC-2 — the two axes never flatten: encode → decode returns the same
        # status, cleanly, for every value.
        for status in encode.STATUS_VALUES:
            state, reason, label = encode.encode_status(status)
            issue = {"state": state, "state_reason": reason}
            labels = [label] if label else []
            decoded, warns = encode.decode_status(issue, labels)
            assert decoded == status, (status, decoded)
            assert warns == []


class TestReconcileStatusLabels:
    """The reconciliation primitive shared by set-status and self-heal (Data Model §4)."""

    def test_add_missing_target_label(self):
        add, remove = encode.reconcile_status_labels([], "status:in-progress")
        assert add == ["status:in-progress"] and remove == []

    def test_keep_present_target_and_strip_losers(self):
        add, remove = encode.reconcile_status_labels(
            ["status:submitted", "status:in-progress"], "status:in-progress"
        )
        assert add == [] and remove == ["status:submitted"]

    def test_none_keep_strips_all(self):
        # closed target / plain open — keep nothing.
        add, remove = encode.reconcile_status_labels(["status:in-progress"], None)
        assert add == [] and remove == ["status:in-progress"]

    def test_already_canonical_is_noop(self):
        add, remove = encode.reconcile_status_labels(["status:submitted"], "status:submitted")
        assert add == [] and remove == []

    def test_status_labels_present_filters_by_facet(self):
        present = encode.status_labels_present(
            ["status:submitted", "stage:ready", "area:cli"]
        )
        assert present == ["status:submitted"]


class TestDecodeItem:
    def test_decodes_axes_independently(self):
        issue = {
            "number": 7,
            "node_id": "I_abc",
            "title": "Do the thing",
            "body": "body\n```prawduct\nv: 1\nid_aliases: [BKL-0007]\n```\n",
            "state": "open",
            "labels": [{"name": "stage:ready"}, {"name": "area:backlog"}],
            "html_url": "https://github.com/octo/repo/issues/7",
        }
        item, warns = encode.decode_item(issue, canonical_id="octo/repo#7")
        assert item["id"] == "octo/repo#7"
        assert item["status"] == "open"  # no status label
        assert item["stage"] == "ready"  # independent axis
        assert item["area"] == "backlog"
        assert item["id_aliases"] == ["BKL-0007"]
        assert item["number"] == 7


class TestAffected:
    """The structured path list — read tolerantly, written strictly.

    `affected` exists because `refs` mixes governance artifacts, code paths and
    prose annotations, which is exactly why `refs` can never be matched against a
    changed-file set. Every test here is about keeping that boundary sharp.
    """

    def test_a_path_list_round_trips_through_the_block(self):
        body = "text\n```prawduct\nv: 1\naffected: [plugin/lib/backlog/sync.py, tests]\n```\n"

        block = encode.parse_block(body)

        assert block.affected() == ["plugin/lib/backlog/sync.py", "tests"]

    def test_natural_spellings_of_one_path_collapse_to_one_entry(self):
        """A trailing slash, a leading `./`, and backticks are three ways of
        writing the same path — tolerating them is the difference between a
        matcher and a spelling test."""
        assert encode.normalize_affected(
            ["plugin/lib/", "./plugin/lib", "`plugin/lib`", "/plugin/lib"]
        ) == ["plugin/lib"]

    def test_prose_is_rejected_at_the_write_and_told_where_to_go(self):
        entries, message = encode.validate_affected(["the sync path and its tests"])

        assert message is not None
        assert "body" in message, "a refusal must say where the annotation belongs"
        assert entries == ["the sync path and its tests"], "normalization still ran"

    def test_a_hand_edited_prose_body_still_decodes_rather_than_failing(self):
        """Decode is tolerant even where the write path refuses: an item someone
        edited in the GitHub UI must stay readable, not become undecodable."""
        body = "```prawduct\nv: 1\naffected: [the sync path]\n```\n"

        assert encode.parse_block(body).affected() == ["the sync path"]

    def test_a_glob_is_refused_and_the_working_form_is_named(self):
        """A glob is not a broader match — it is a literal that matches nothing
        forever: a silent NEGATIVE in the one query this field serves, and the
        mirror of the stale positive the index's delete prevents."""
        _entries, message = encode.validate_affected(["plugin/lib/backlog/**"])

        assert message is not None
        assert "not patterns" in message
        assert "plugin/lib/backlog`" in message, "name the directory form that works"

    def test_a_bare_path_list_validates_clean(self):
        entries, message = encode.validate_affected(["plugin/lib/backlog/", "docs/x.md"])

        assert message is None
        assert entries == ["plugin/lib/backlog", "docs/x.md"]


class TestAffectedIntersection:
    """Consumers 1 and 4: a set intersection instead of a reviewer inferring."""

    def test_a_directory_entry_covers_the_files_under_it(self):
        touched = encode.affected_matches(
            ["plugin/lib/backlog"], ["plugin/lib/backlog/sync.py", "README.md"]
        )

        assert touched == ["plugin/lib/backlog"]

    def test_an_exact_file_entry_matches_only_that_file(self):
        assert encode.affected_matches(["docs/a.md"], ["docs/a.md"]) == ["docs/a.md"]
        assert encode.affected_matches(["docs/a.md"], ["docs/ab.md"]) == []

    def test_a_sibling_prefix_is_not_a_match(self):
        """`plugin/lib` must not swallow `plugin/libexec` — the failure a naive
        string-prefix comparison makes, and one that reads as a confident hit."""
        assert encode.affected_matches(["plugin/lib"], ["plugin/libexec/x.py"]) == []

    def test_no_overlap_and_no_paths_recorded_are_different_answers(self):
        assert encode.affected_matches(["docs"], ["src/x.py"]) == []
        assert encode.affected_matches([], ["src/x.py"]) == []

    def test_ancestors_are_the_keys_a_changed_file_answers_to(self):
        assert encode.path_ancestors("a/b/c.py") == ["a/b/c.py", "a/b", "a"]


class TestTags:
    def test_tags_decode_from_labels_sorted_and_deduplicated(self):
        issue = {
            "number": 3,
            "title": "t",
            "state": "open",
            "labels": [{"name": "tag:perf"}, {"name": "area:cli"}, {"name": "tag:api"}],
        }

        item, _warns = encode.decode_item(issue, canonical_id="octo/repo#3")

        assert item["tags"] == ["api", "perf"]

    def test_a_tag_label_alone_makes_an_issue_ours(self):
        """`tag:` is namespaced prawduct metadata, so an item someone tagged and
        never faceted is an item — not a plain repo issue to be ignored."""
        assert encode.is_prawduct_issue({"labels": [{"name": "tag:perf"}], "body": ""})

    def test_a_comma_is_refused_because_it_separates_tags(self):
        _tags, message = encode.validate_tags(["a,b"])

        assert message is not None and "comma" in message

    def test_a_tag_too_long_to_become_a_label_is_refused_at_the_seam(self):
        _tags, message = encode.validate_tags(["x" * 60])

        assert message is not None

    def test_there_is_no_vocabulary_to_be_unknown_against(self):
        """An open folksonomy has no closed set — the binding rule that nothing
        gates on tags is what makes that safe."""
        tags, message = encode.validate_tags(["whatever-someone-wants"])

        assert message is None and tags == ["whatever-someone-wants"]


class TestWorkingBranch:
    def test_a_repo_qualified_ref_parses(self):
        assert encode.parse_working_branch("octo/repo@feat/x") == ("octo", "repo", "feat/x")

    def test_a_bare_branch_name_names_nothing_and_is_refused(self):
        """The backlog repo and the code repo are not necessarily the same one,
        so an unqualified branch cannot be looked up by anyone else."""
        assert encode.parse_working_branch("feat/x") is None

    def test_a_slash_bearing_branch_survives_the_split(self):
        assert encode.parse_working_branch("o/r@feat/a/b") == ("o", "r", "feat/a/b")

    def test_an_at_sign_inside_the_branch_name_is_kept(self):
        assert encode.parse_working_branch("o/r@feat@2") == ("o", "r", "feat@2")

    def test_a_three_segment_repo_is_refused(self):
        assert encode.parse_working_branch("a/b/c@main") is None

    def test_a_traversal_sequence_is_refused_before_it_reaches_a_url_path(self):
        """`owner/repo@../../../user` would otherwise resolve a DIFFERENT endpoint
        and be stored as a verified working branch — the pushed-ref control
        failing open, which is the invisible claim it exists to prevent."""
        assert encode.parse_working_branch("o/r@../../../user") is None
        assert encode.parse_working_branch("o/..@main") is None

    @pytest.mark.parametrize(
        "bad",
        [
            "o/r@feat~1", "o/r@feat^", "o/r@feat:x", "o/r@feat?x", "o/r@feat*",
            "o/r@feat[x]", "o/r@feat\\x", "o/r@feat@{0}", "o/r@a//b", "o/r@-feat",
            "o/r@feat.", "o/r@feat.lock", "o/r@.hidden", "o/r@a/.b", "o/r@a/b.lock",
            "o/r@@", "o/r@feat\x01x",
        ],
    )
    def test_names_git_itself_would_refuse_are_refused_here(self, bad):
        """A name git could never create cannot be a pushed ref, so accepting one
        can only ever mean the check passed against something else."""
        assert encode.parse_working_branch(bad) is None

    @pytest.mark.parametrize(
        "good",
        ["o/r@main", "o/r@feat/a/b", "o/r@feat@2", "o/r@release-1.2", "o/docs.github.com@main"],
    )
    def test_ordinary_names_still_parse(self, good):
        """The refusal must not be incidental strictness — a dot is legal in a
        repo name (`docs.github.com`) and mid-name in a branch."""
        assert encode.parse_working_branch(good) is not None

    def test_it_round_trips_through_the_block_under_its_snake_key(self):
        body = "```prawduct\nv: 1\nworking_branch: octo/repo@feat/x\n```\n"

        assert encode.parse_block(body).working_branch() == "octo/repo@feat/x"

    def test_decode_surfaces_all_three_fields_on_the_item(self):
        issue = {
            "number": 9,
            "title": "t",
            "state": "open",
            "labels": [{"name": "tag:perf"}],
            "body": (
                "```prawduct\nv: 1\naffected: [plugin/lib]\n"
                "working_branch: octo/repo@feat/x\n```\n"
            ),
        }

        item, _warns = encode.decode_item(issue, canonical_id="octo/repo#9")

        assert item["affected"] == ["plugin/lib"]
        assert item["tags"] == ["perf"]
        assert item["working_branch"] == "octo/repo@feat/x"
