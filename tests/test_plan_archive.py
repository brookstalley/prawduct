"""Tests for `lib/plan_archive.py` and the `archive-plan` subcommand.

A build plan's end of life. The properties under test are the ones the lifecycle
rests on: a completed plan is never deleted, both terminal states archive (not
just the tidy one), an archived plan answers "is this current?" when opened
directly, it stays findable by name, and checkbox state survives untouched.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import plan_archive, plan_index  # noqa: E402

_HOOK_PATH = _REPO_ROOT / "bin" / "prawduct-hook"

PLAN = (
    "---\n"
    "artifact: build-plan\n"
    "scope: demo\n"
    "---\n"
    "\n"
    "## Status\n"
    "\n"
    "- [x] Chunk 01: one\n"
    "- [ ] Chunk 02: two\n"
)


def _repo(tmp_path: Path, *, rel: str = "artifacts/build-plan-demo.md", body: str = PLAN) -> Path:
    """A project dir with one plan at ``rel`` under ``.prawduct/``."""
    plan = tmp_path / ".prawduct" / rel
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(body, encoding="utf-8")
    return tmp_path


def _artifacts(project: Path) -> Path:
    return project / ".prawduct" / "artifacts"


def _run_hook(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH), "archive-plan", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=30,
    )


# =============================================================================
# Completion frontmatter — the round trip, both terminal states
# =============================================================================


class TestCompletionFrontmatter:
    """The frontmatter is what makes an archived plan self-describing. A reader
    arriving by link or grep has no directory context, so "it was under
    archive/" is not information they have."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"state": plan_archive.COMPLETED, "date": "2026-08-08", "release": "v3.2.9"},
            {
                "state": plan_archive.SUPERSEDED,
                "date": "2026-08-08",
                "superseded_by": "absorbed into build-plan-beta.md",
            },
        ],
        ids=["completed", "superseded"],
    )
    def test_it_round_trips(self, kwargs):
        stamped = plan_archive.apply_completion_frontmatter(PLAN, **kwargs)
        read = plan_archive.read_completion(stamped)
        assert read is not None
        assert read[plan_archive.LIFECYCLE_KEY] == kwargs["state"]
        assert read[plan_archive.ARCHIVED_KEY] == kwargs["date"]
        assert read[plan_archive.MAINTAINED_KEY] == "false"
        for key, value in (
            (plan_archive.RELEASE_KEY, kwargs.get("release")),
            (plan_archive.SUPERSEDED_BY_KEY, kwargs.get("superseded_by")),
        ):
            assert read.get(key) == value

    def test_a_plan_recording_no_terminal_state_reads_as_none(self):
        """The predicate has to answer "no" on a live plan, or every reader that
        asks "is this current?" gets a false positive on work in flight."""
        assert plan_archive.read_completion(PLAN) is None
        assert plan_archive.read_completion("# no frontmatter at all\n") is None

    def test_the_no_longer_maintained_statement_is_prose_not_only_data(self):
        """`maintained: false` is for a parser. A person opening the file reads
        a future-tense build plan as present intent unless something interrupts
        them, so the statement exists in both registers."""
        stamped = plan_archive.apply_completion_frontmatter(
            PLAN, state=plan_archive.COMPLETED, date="2026-08-08"
        )
        assert plan_archive.NOT_MAINTAINED_BANNER in stamped
        assert "no longer maintained" in stamped.lower()

    def test_re_stamping_replaces_rather_than_appends(self):
        """A plan corrected from superseded to completed must end with ONE
        answer. Two contradicting keys resolve in whatever order a parser reads
        them, which is a coin toss dressed as a record."""
        once = plan_archive.apply_completion_frontmatter(
            PLAN,
            state=plan_archive.SUPERSEDED,
            date="2026-08-01",
            superseded_by="build-plan-beta.md",
        )
        twice = plan_archive.apply_completion_frontmatter(
            once, state=plan_archive.COMPLETED, date="2026-08-08", release="v3.2.9"
        )
        assert twice.count(f"{plan_archive.LIFECYCLE_KEY}:") == 1
        assert twice.count(plan_archive.NOT_MAINTAINED_BANNER) == 1
        read = plan_archive.read_completion(twice)
        assert read[plan_archive.LIFECYCLE_KEY] == plan_archive.COMPLETED
        # The superseded key is this writer's own and must not survive a
        # correction — a completed plan carrying `superseded_by` is a record
        # that contradicts itself.
        assert plan_archive.SUPERSEDED_BY_KEY not in read

    def test_it_writes_into_a_block_behind_a_leading_comment_header(self):
        """A third of this repo's plans open with an HTML comment before the
        frontmatter. Writing a SECOND block above it would produce a file whose
        archived state no reader finds, because the readers skip to the same
        place this writer must."""
        body = "<!-- a header comment -->\n" + PLAN
        stamped = plan_archive.apply_completion_frontmatter(
            body, state=plan_archive.COMPLETED, date="2026-08-08"
        )
        assert stamped.count("\n---\n") + stamped.startswith("---\n") <= 2
        assert plan_archive.read_completion(stamped) is not None
        # The pre-existing keys survive: this adds to the block, never replaces it.
        assert plan_index.parse_build_plan_frontmatter_scope(stamped) == (True, "demo")

    def test_a_plan_with_no_frontmatter_gains_a_block_the_readers_can_find(self):
        stamped = plan_archive.apply_completion_frontmatter(
            "# Old Plan\n\nNo frontmatter here.\n",
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert plan_archive.read_completion(stamped) is not None

    @pytest.mark.parametrize(
        "value",
        [
            "stopped: the API went away",  # a colon would turn one key into two
            'absorbed "here"',  # bare + a real quote the reader once ate
            "he said: \"no\"",  # quoted AND escaped
            "tracked in #630",  # a `#` the comment-strip would truncate
            "path\\to\\thing",  # a backslash the unescape would consume
            "  leading and trailing  ",  # whitespace the writer must fence
            "plain english with no punctuation",  # the bare case must stay bare
            "",  # empty: quoted, and must not read back as a missing key
        ],
    )
    def test_operator_free_text_round_trips_byte_identically(self, value):
        """`superseded_by` is operator free text, and it is the field Chunk 05's
        backfill is the first thing to read back.

        The writer and the reader are one contract: whatever the writer leaves
        BARE the reader must return unchanged, and whatever it quotes the reader
        must unescape. Both directions were lossy — `absorbed "here"` did not
        trip the quoting rule, was written bare, and read back as
        `absorbed "here` because the reader stripped the real trailing quote.
        """
        stamped = plan_archive.apply_completion_frontmatter(
            PLAN,
            state=plan_archive.SUPERSEDED,
            date="2026-08-08",
            superseded_by=value,
        )
        read = plan_archive.read_completion(stamped)
        assert read is not None
        # An empty value carries no fact, so the key is omitted rather than
        # written blank — the same rule `released_in` follows. Everything else
        # comes back exactly as given, whitespace included: "byte-identical"
        # means the reader does not get to tidy the operator's text.
        assert read.get(plan_archive.SUPERSEDED_BY_KEY) == (value or None)

    def test_a_quoted_value_is_not_truncated_at_a_hash(self):
        """Comment-stripping applies to a BARE value only. Doing it first — the
        shape every other reader here uses, because their values cannot contain
        a `#` — truncates a quoted value at the first one inside it."""
        stamped = plan_archive.apply_completion_frontmatter(
            PLAN,
            state=plan_archive.SUPERSEDED,
            date="2026-08-08",
            superseded_by="absorbed into #630 # not a comment",
        )
        read = plan_archive.read_completion(stamped)
        assert read[plan_archive.SUPERSEDED_BY_KEY] == "absorbed into #630 # not a comment"

    def test_an_inline_comment_on_a_bare_value_is_still_stripped(self):
        """The tolerance the other readers have, kept: a hand-written
        `archived: 2026-08-08  # backfilled` must not read the comment as data."""
        stamped = (
            "---\nartifact: build-plan\nlifecycle: completed\n"
            "archived: 2026-08-08  # backfilled by hand\nmaintained: false\n---\n"
        )
        assert plan_archive.read_completion(stamped)[plan_archive.ARCHIVED_KEY] == "2026-08-08"

    def test_a_release_plans_own_release_key_survives_archival(self):
        """**Regression.** This writer's "which release carried the work" key is
        `released_in`, deliberately not `release` — a release plan already
        carries `release: vX.Y.Z` meaning *the release this plan governs*, and
        release plans are among the artifacts most likely to be archived (the
        gate that reads them searches the archive by design).

        With the short name, re-stamping would have stripped a key whose meaning
        this operation knows nothing about — silent loss, on the operation whose
        whole purpose is to stop losing plans. The two facts must both survive.
        """
        release_plan = (
            "---\nartifact: release-plan\nrelease: v3.2.7\nscope: demo\n---\n\n# Release plan\n"
        )
        stamped = plan_archive.apply_completion_frontmatter(
            release_plan,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
            release="v3.2.9",
        )
        assert "release: v3.2.7" in stamped, "the plan's own release key was stripped"
        read = plan_archive.read_completion(stamped)
        assert read[plan_archive.RELEASE_KEY] == "v3.2.9"
        # And it survives a SECOND stamp, which is where the strip would happen.
        twice = plan_archive.apply_completion_frontmatter(
            stamped, state=plan_archive.COMPLETED, date="2026-08-09", release="v3.3.0"
        )
        assert "release: v3.2.7" in twice
        assert plan_archive.read_completion(twice)[plan_archive.RELEASE_KEY] == "v3.3.0"

    def test_the_release_key_is_omitted_rather_than_written_empty(self):
        """An empty key claims the field was considered and found blank. A
        product that does not version has no such fact to record."""
        stamped = plan_archive.apply_completion_frontmatter(
            PLAN, state=plan_archive.COMPLETED, date="2026-08-08"
        )
        assert f"{plan_archive.RELEASE_KEY}:" not in stamped


# =============================================================================
# The move — and what it must not touch
# =============================================================================


class TestArchivePlan:
    def test_it_stamps_and_moves_in_one_operation(self, tmp_path: Path):
        project = _repo(tmp_path)
        plan = _artifacts(project) / "build-plan-demo.md"
        result = plan_archive.archive_plan(
            plan,
            _artifacts(project),
            state=plan_archive.COMPLETED,
            date="2026-08-08",
            release="v3.2.9",
        )
        assert result["status"] == "archived"
        assert not plan.exists()
        destination = Path(result["destination"])
        assert destination.is_file()
        assert plan_archive.read_completion(destination.read_text(encoding="utf-8"))

    def test_checkbox_state_is_left_exactly_as_it_was(self, tmp_path: Path):
        """Not a precondition, and not corrected on the way in. Nothing reads an
        archived plan's boxes, so ticking them would be ceremony with no
        consumer — and it would put a writer where only a session with the work
        in context may say which chunk is done. The unticked box IS the record
        of how the work ended."""
        project = _repo(tmp_path)
        result = plan_archive.archive_plan(
            _artifacts(project) / "build-plan-demo.md",
            _artifacts(project),
            state=plan_archive.SUPERSEDED,
            date="2026-08-08",
            superseded_by="descoped",
        )
        archived = Path(result["destination"]).read_text(encoding="utf-8")
        assert "- [x] Chunk 01: one" in archived
        assert "- [ ] Chunk 02: two" in archived

    def test_a_superseded_plan_must_say_what_replaced_it(self, tmp_path: Path):
        """An unexplained dead plan is the thing archiving exists to stop
        producing — moving one into the archive unlabelled just relocates it."""
        project = _repo(tmp_path)
        plan = _artifacts(project) / "build-plan-demo.md"
        result = plan_archive.archive_plan(
            plan, _artifacts(project), state=plan_archive.SUPERSEDED, date="2026-08-08"
        )
        assert result["status"] == "refused"
        assert plan.is_file(), "a refusal must leave the live plan untouched"

    def test_an_unknown_terminal_state_is_refused(self, tmp_path: Path):
        project = _repo(tmp_path)
        result = plan_archive.archive_plan(
            _artifacts(project) / "build-plan-demo.md",
            _artifacts(project),
            state="finished",
            date="2026-08-08",
        )
        assert result["status"] == "refused"

    def test_a_missing_plan_is_refused_not_invented(self, tmp_path: Path):
        project = _repo(tmp_path)
        (project / ".prawduct" / "artifacts").mkdir(parents=True, exist_ok=True)
        result = plan_archive.archive_plan(
            _artifacts(project) / "nope.md",
            _artifacts(project),
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert result["status"] == "refused"

    def test_it_refuses_to_overwrite_an_earlier_archived_namesake(self, tmp_path: Path):
        """Two plans called `build-plan.md` from different cycles is the normal
        case in a repo that nests them. Silently overwriting destroys the record
        this whole operation exists to keep."""
        project = _repo(tmp_path)
        artifacts = _artifacts(project)
        (artifacts / "archive").mkdir(parents=True)
        (artifacts / "archive" / "build-plan-demo.md").write_text("earlier\n", encoding="utf-8")
        plan = artifacts / "build-plan-demo.md"
        result = plan_archive.archive_plan(
            plan, artifacts, state=plan_archive.COMPLETED, date="2026-08-08"
        )
        assert result["status"] == "refused"
        assert plan.is_file()
        assert (artifacts / "archive" / "build-plan-demo.md").read_text() == "earlier\n"

    def test_a_nested_plan_archives_beside_itself_not_into_one_central_pile(
        self, tmp_path: Path
    ):
        """A repo nesting `plans/<id>/build-plan.md` would otherwise collapse
        every plan onto the single name `artifacts/archive/build-plan.md` and
        collide on the first archival."""
        project = _repo(tmp_path, rel="artifacts/plans/alpha/build-plan.md")
        artifacts = _artifacts(project)
        result = plan_archive.archive_plan(
            artifacts / "plans" / "alpha" / "build-plan.md",
            artifacts,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert result["status"] == "archived"
        assert Path(result["destination"]) == artifacts / "plans" / "alpha" / "archive" / "build-plan.md"


# =============================================================================
# BP8 / BP5 — findability and non-assertion after the move
# =============================================================================


class TestArchiveRefusesWhatIsNotItsToMove:
    """`archive_plan` moves a file and then UNLINKS the original.

    So "is this mine to move?" has to be answered before the move, not assumed
    from the caller's good intentions — and the caller is not always a keystroke:
    the PR flow has an *agent* supply the path.
    """

    def test_a_path_outside_the_artifacts_tree_is_refused(self, tmp_path: Path):
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        outsider = tmp_path / "README.md"
        outsider.write_text("not a plan\n", encoding="utf-8")

        result = plan_archive.archive_plan(
            outsider, artifacts, state="completed", date="2026-08-10"
        )
        assert result["status"] == "refused"
        assert outsider.is_file(), "a refusal must leave the original alone"

    def test_dot_dot_does_not_walk_through_the_guard(self, tmp_path: Path):
        """The first cut of this guard was lexical, and one `..` defeated it.

        ``Path.is_relative_to`` compares path parts and never collapses ``..``,
        so ``artifacts/../../README.md`` satisfied the check, took the matching
        lexical branch when computing the destination, wrote the stamped copy
        outside the tree and unlinked the original — at exit 0. This is that
        exact input.
        """
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        outsider = tmp_path / "README.md"
        outsider.write_text("not a plan\n", encoding="utf-8")
        traversal = artifacts / ".." / ".." / "README.md"

        result = plan_archive.archive_plan(
            traversal, artifacts, state="completed", date="2026-08-10"
        )
        assert result["status"] == "refused", result
        assert outsider.is_file(), "the traversal deleted a file outside the tree"

    def test_an_already_archived_plan_is_not_restamped(self, tmp_path: Path):
        """Re-stamping is how a `superseded` record silently becomes `completed`,
        and the frontmatter is the whole content of the record."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        plan = artifacts / "build-plan-demo.md"
        plan.write_text(
            "---\nartifact: build-plan\nscope: demo\nlifecycle: superseded\n"
            "archived: 2026-01-01\nsuperseded_by: something else\nmaintained: false\n---\n",
            encoding="utf-8",
        )

        result = plan_archive.archive_plan(
            plan, artifacts, state="completed", date="2026-08-10"
        )
        assert result["status"] == "refused"
        assert "superseded" in result["reason"]
        assert "lifecycle: superseded" in plan.read_text()

    def test_the_preview_refuses_exactly_what_the_write_refuses(self, tmp_path: Path):
        """The preview and the write share one predicate, so they cannot disagree.

        They did: `--dry-run` computed a destination and printed *would archive*
        at exit 0 without consulting a single guard, so for the traversal input
        the containment check exists to stop, the preview promised an operation
        the real run refuses. A preview that overstates permission is worse than
        no preview — it reports clean about something that is wrong.
        """
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (tmp_path / "README.md").write_text("not a plan\n", encoding="utf-8")
        good = artifacts / "build-plan-demo.md"
        good.write_text("---\nartifact: build-plan\nscope: demo\n---\n", encoding="utf-8")

        for target in (artifacts / ".." / ".." / "README.md", artifacts / "missing.md"):
            preview = plan_archive.refusal_reason(target, artifacts, state="completed")
            written = plan_archive.archive_plan(
                target, artifacts, state="completed", date="2026-08-10"
            )
            assert preview is not None, f"preview allowed {target}"
            assert written["status"] == "refused"
            assert preview == written["reason"], "preview and write gave different reasons"

        # And they agree on the allowed case too, or the test above passes on a
        # predicate that refuses everything.
        assert plan_archive.refusal_reason(good, artifacts, state="completed") is None

    def test_a_normal_plan_under_artifacts_still_archives(self, tmp_path: Path):
        """The guards must refuse the two bad shapes and nothing else — without
        this, all three assertions above pass on a function that refuses
        everything."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        plan = artifacts / "build-plan-demo.md"
        plan.write_text("---\nartifact: build-plan\nscope: demo\n---\n", encoding="utf-8")

        result = plan_archive.archive_plan(
            plan, artifacts, state="completed", date="2026-08-10"
        )
        assert result["status"] == "archived", result
        assert (artifacts / "archive" / "build-plan-demo.md").is_file()


class TestArchivedPlansStayFindableButStopAsserting:
    def test_a_named_plan_still_resolves_after_archival(self, tmp_path: Path):
        """Archival must never change whether a document can be found by name —
        the release gate resolves a release-pending scope to the plan declaring
        it, and a plan that reached its end of life is documented, not missing."""
        project = _repo(tmp_path)
        artifacts = _artifacts(project)
        plan_archive.archive_plan(
            artifacts / "build-plan-demo.md",
            artifacts,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert plan_index.build_scope_to_plan_map(artifacts) == {}
        found = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert "demo" in found

    def test_a_nested_archive_is_findable_too(self, tmp_path: Path):
        """The live walk prunes an `archive` component at EVERY depth, so the
        archived pass has to find them at every depth. Re-walking only the
        top-level archive left a nested one pruned from the live pass AND absent
        from the archived one — invisible to both. A flat fixture passes under
        either rule; only this shape tells them apart."""
        project = _repo(tmp_path, rel="artifacts/plans/alpha/build-plan.md")
        artifacts = _artifacts(project)
        plan_archive.archive_plan(
            artifacts / "plans" / "alpha" / "build-plan.md",
            artifacts,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert plan_index.build_scope_to_plan_map(artifacts) == {}
        found = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert "demo" in found
        assert plan_index.ARCHIVE_DIR_NAME in found["demo"].parts

    def test_a_live_plan_wins_over_an_archived_namesake(self, tmp_path: Path):
        """Ordering matters as much as coverage: an archived plan for a scope
        being re-worked must never shadow the live one that supersedes it."""
        project = _repo(tmp_path)
        artifacts = _artifacts(project)
        plan_archive.archive_plan(
            artifacts / "build-plan-demo.md",
            artifacts,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        (artifacts / "build-plan-demo-v2.md").write_text(PLAN, encoding="utf-8")
        found = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert found["demo"] == artifacts / "build-plan-demo-v2.md"

    def test_an_archived_plan_is_not_a_live_assertion(self, tmp_path: Path):
        """Every reader that scans artifacts/ treats archive/ as history. The
        default walk must not see it at all — not see it and filter it, which is
        indistinguishable in any test that only checks the result, and is the
        shape that makes each session pay for every plan the repo ever
        completed."""
        project = _repo(tmp_path)
        artifacts = _artifacts(project)
        plan_archive.archive_plan(
            artifacts / "build-plan-demo.md",
            artifacts,
            state=plan_archive.COMPLETED,
            date="2026-08-08",
        )
        assert list(plan_index.iter_scoped_plan_candidates(artifacts)) == []
        assert plan_index.duplicate_scope_errors(artifacts) == []

    def test_two_archived_namesakes_do_not_report_as_a_duplicate_scope(
        self, tmp_path: Path
    ):
        """Duplicate-scope is a defect in LIVE plans — two of them make a
        scope→plan lookup a coin toss. Two archived plans of one scope is just
        history, and reporting it would make the advisory grow without bound as
        the archive does."""
        project = _repo(tmp_path)
        artifacts = _artifacts(project)
        (artifacts / "archive").mkdir(parents=True)
        (artifacts / "archive" / "old-a.md").write_text(PLAN, encoding="utf-8")
        (artifacts / "archive" / "old-b.md").write_text(PLAN, encoding="utf-8")
        assert plan_index.duplicate_scope_errors(artifacts) == []


# =============================================================================
# Assert-absent — the behaviour is retired everywhere, not at one site
# =============================================================================


class TestNoShippedSurfaceInstructsDeletingAPlan:
    """A plan is never deleted, and fixing one site leaves the behaviour in
    force in the rest — the deletion premise lived in five places, and a
    requirement naming one would have retired none of the other four.

    Matched by PROPERTY rather than by the exact sentences that were removed: a
    test pinned to one spelling passes for every rewording of the same
    instruction, which is precisely how a retired behaviour comes back.
    """

    #: Anything that tells a reader to delete, remove, or `rm` a plan. Both
    #: word orders, because "delete the plan file" and "the plan is deleted"
    #: are the same instruction.
    #: `\b` after each verb is load-bearing: without it `removeprefix(
    #: "build-plan-")` reads as an instruction to remove a plan. The gap
    #: tolerates `.` because the instruction most worth catching is
    #: ``rm .prawduct/artifacts/build-plan.md``, which is nothing but dots.
    _INSTRUCTS_DELETION = re.compile(
        r"\b(?:delete|deleting|deleted|remove|removing|removed|rm)\b"
        r"[^\n]{0,40}\bplans?\b"
        r"|\bplans?\b[^\n]{0,40}\b(?:is|are|be|been|gets?)\s+(?:deleted|removed)\b",
        re.IGNORECASE,
    )

    #: A negator immediately before the verb turns the instruction into its
    #: retirement. Kept short and adjacent — a negator three clauses away
    #: negates something else.
    _NEGATED = re.compile(
        r"\b(?:never|not|no longer|rather than|instead of|without)\b[^\n]{0,12}$",
        re.IGNORECASE,
    )

    #: Records, not instructions. A record is falsified by editing it: the
    #: change log states what was true at a version, and this test file has to
    #: contain the phrases it forbids in order to forbid them.
    _RECORDS = ("CHANGELOG.md",)

    def _shipped_files(self) -> list[Path]:
        plugin_root = _REPO_ROOT
        files: list[Path] = []
        for pattern in ("**/*.md", "**/*.py", "bin/prawduct-hook"):
            files.extend(
                p
                for p in plugin_root.glob(pattern)
                if p.is_file() and p.name not in self._RECORDS
            )
        return files

    def test_the_sweep_has_subjects(self):
        """A green assert-absent test proves nothing if it swept an empty set —
        the failure mode of every negative check."""
        files = self._shipped_files()
        assert len(files) > 50, f"only {len(files)} shipped files swept"
        assert any(p.name == "SKILL.md" for p in files)
        assert any(p.name == "prawduct-hook" for p in files)

    def _offends(self, line: str) -> bool:
        """Does ``line`` instruct deleting a plan, un-negated?

        The scan and the guard-verification tests share this, so what is
        verified red is the predicate the sweep actually runs — not a second
        implementation of it that can drift into agreeing.
        """
        for match in self._INSTRUCTS_DELETION.finditer(line):
            # A NEGATED verb is the retirement being STATED — "archive it,
            # never delete it" — and a reader looking for the old rule must
            # find its retirement, not silence. Scoped to the words immediately
            # before the verb rather than a window around the whole match: a
            # window merely containing "archive" would excuse a genuine deletion
            # instruction written on a line that happens to mention archiving,
            # which every line on these surfaces now does.
            if self._NEGATED.search(line[max(0, match.start() - 24) : match.start()]):
                continue
            return True
        return False

    @pytest.mark.parametrize(
        "prior",
        [
            # The real prior text, verbatim.
            "Clean up: delete plan file",
            "if work is done, delete the plan",
            "delete the plan file (resolve via the `active_build_plan` pointer)",
            # Rewordings that never shipped — the guard must still catch them,
            # or it is pinned to sentences rather than to the instruction.
            "the completed plan should be removed from artifacts/",
            "once the work ships the build plan is deleted",
            "run `rm .prawduct/artifacts/build-plan.md`",
            # The one the negation exemption could have let through: a real
            # deletion instruction on a line that also talks about archiving.
            "Archive the plan at the release; on trunk, delete the plan file now.",
        ],
    )
    def test_the_guard_catches_the_instruction_not_one_spelling_of_it(self, prior):
        assert self._offends(prior), f"the guard would not have caught {prior!r}"

    @pytest.mark.parametrize(
        "retirement",
        [
            "**archive it, never delete it**: `prawduct-hook archive-plan <path>`",
            "a completed plan is archived, not deleted",
            "Clean up: **archive, never delete** the plan",
            "archived rather than deleted, so a reference into the plan resolves",
        ],
    )
    def test_the_guard_does_not_fire_on_the_retirement_being_stated(self, retirement):
        """Stating the retired rule is required, not forbidden — silence would
        leave a reader who remembers "delete the plan" with no correction."""
        assert not self._offends(retirement)

    def test_no_shipped_surface_instructs_it(self):
        offenders: list[str] = []
        for path in self._shipped_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            offenders.extend(
                f"{path.relative_to(_REPO_ROOT)}:{lineno}: {line.strip()[:120]}"
                for lineno, line in enumerate(text.splitlines(), 1)
                if self._offends(line)
            )
        assert offenders == [], "shipped surfaces still instruct deleting a plan:\n" + "\n".join(
            offenders
        )


class TestTheMergeFlowArchivesOnBothPaths:
    """The POSITIVE half, and it is not redundant with the assert-absent sweep.

    Silence passes a negative guard by construction: an edit that simply DROPS
    the archive instruction from either merge-flow branch leaves the sweep and
    every other test green, because nothing then instructs deletion either. That
    is the same never-armed failure this branch closed for the unticked-chunk
    tripwire, and leaving it open on the surface that actually retires plans
    would have been the same mistake one file over.

    Scoped to the two branches rather than to the file, because a whole-file
    grep passes when the instruction is present but sitting in the wrong branch
    — and which branch it is in is the entire content of the rule: gitflow
    decides *when* a plan is archived, never *whether*.
    """

    def _pr_skill(self) -> str:
        return (_REPO_ROOT / "skills" / "pr" / "SKILL.md").read_text(encoding="utf-8")

    def _bullet_containing(self, text: str, *needles: str) -> str:
        """The single line carrying every needle — the branch under test."""
        matches = [
            line
            for line in text.splitlines()
            if all(needle in line for needle in needles)
        ]
        assert len(matches) == 1, (
            f"expected exactly one line containing {needles!r}, found {len(matches)} — "
            "the fixture no longer locates the branch it means to test"
        )
        return matches[0]

    def test_the_trunk_path_archives_and_names_the_operation(self):
        """On trunk this merge ships the work, so the plan reaches its end of
        life here. Naming the operation matters: an instruction to 'retire' the
        plan without naming `archive-plan` is answered with `rm`."""
        bullet = self._bullet_containing(self._pr_skill(), "Build plan (trunk only)")
        assert "archive-plan" in bullet
        assert "never delete" in bullet.lower()

    def test_the_gitflow_path_retains_rather_than_archiving_yet(self):
        """Gitflow decides WHEN, not WHETHER. The plan stays live until the
        release, because it is still the description of unshipped work and the
        release gate resolves each release-pending scope to it."""
        bullet = self._bullet_containing(
            self._pr_skill(), "Base is `develop`", "RETAIN"
        )
        assert "keep the plan live" in bullet.lower() or "retain" in bullet.lower()
        assert not re.search(r"\barchive-plan\b", bullet), (
            "the gitflow branch names the archive operation — it must defer it "
            "to the release, or a plan describing unshipped work leaves the live "
            "directory while the release gate still needs it there"
        )

    def test_the_janitor_cleanup_step_archives(self):
        """The other surface that retires plans on its own initiative."""
        janitor = (_REPO_ROOT / "skills" / "janitor" / "SKILL.md").read_text(encoding="utf-8")
        bullet = self._bullet_containing(janitor, "Stale build plans")
        assert "archive-plan" in bullet
        assert "superseded" in bullet, (
            "the janitor sweep must cover BOTH terminal states — a half-finished "
            "dead plan can never satisfy 'all boxes ticked', so if this step only "
            "handles completed plans nothing ever sweeps the ones that accumulate"
        )

    def test_the_planning_guide_teaches_archival_as_the_ending(self):
        planning = (_REPO_ROOT / "methodology" / "planning.md").read_text(encoding="utf-8")
        bullet = self._bullet_containing(planning, "Plan lifecycle")
        assert "archive-plan" in bullet
        assert "never deleted" in bullet

    def test_the_locator_fails_loudly_when_its_branch_disappears(self):
        """These pins are only as good as `_bullet_containing` finding the right
        line. If a rewrite renames a branch, the pin must go RED (the locator
        raises) rather than silently matching nothing and passing — the exact
        vacuous-pass failure the assert-absent guard beside it can also have.
        """
        with pytest.raises(AssertionError, match="no longer locates"):
            self._bullet_containing(self._pr_skill(), "Build plan (submodule only)")


# =============================================================================
# The CLI boundary — exit codes are the contract
# =============================================================================


class TestArchivePlanCommand:
    def test_it_writes_and_reports_exit_zero(self, tmp_path: Path):
        project = _repo(tmp_path)
        proc = _run_hook(
            project,
            ".prawduct/artifacts/build-plan-demo.md",
            "--state",
            "completed",
            "--date",
            "2026-08-08",
            "--release",
            "v3.2.9",
        )
        assert proc.returncode == 0, proc.stderr
        assert "archived:" in proc.stdout
        assert (_artifacts(project) / "archive" / "build-plan-demo.md").is_file()

    def test_dry_run_writes_nothing(self, tmp_path: Path):
        project = _repo(tmp_path)
        proc = _run_hook(
            project, ".prawduct/artifacts/build-plan-demo.md", "--dry-run"
        )
        assert proc.returncode == 0, proc.stderr
        assert "would archive:" in proc.stdout
        assert (_artifacts(project) / "build-plan-demo.md").is_file()
        assert not (_artifacts(project) / "archive").exists()

    def test_dry_run_refuses_a_traversal_path_at_the_cli(self, tmp_path: Path):
        """The preview's refusal branch, pinned where the defect actually lived.

        The reported defect was CLI-level: `--dry-run` printed `would archive:`
        at exit 0 for an input the write refuses. Pinning `refusal_reason` proves
        the predicate and not the wiring — delete the six lines in
        `cmd_archive_plan` and a lib-level test stays green while the defect
        returns. This drives the traversal input the guard exists for, through
        the actual command.
        """
        project = _repo(tmp_path)
        outsider = project / "README.md"
        outsider.write_text("not a plan\n", encoding="utf-8")

        proc = _run_hook(project, ".prawduct/artifacts/../../README.md", "--dry-run")

        assert proc.returncode == 1, proc.stdout
        assert "not-archived:" in proc.stderr
        assert "would archive:" not in proc.stdout
        assert outsider.is_file(), "the preview's own run touched a file outside the tree"

    def test_dry_run_still_previews_an_archivable_plan(self, tmp_path: Path):
        """The control: without it, the assertion above passes on a preview that
        refuses everything, which would be a different defect of equal size."""
        proc = _run_hook(_repo(tmp_path), ".prawduct/artifacts/build-plan-demo.md", "--dry-run")

        assert proc.returncode == 0, proc.stderr
        assert "would archive:" in proc.stdout

    def test_a_refusal_is_exit_one_with_nothing_written(self, tmp_path: Path):
        project = _repo(tmp_path)
        proc = _run_hook(
            project, ".prawduct/artifacts/build-plan-demo.md", "--state", "superseded"
        )
        assert proc.returncode == 1
        assert "not-archived:" in proc.stderr
        assert (_artifacts(project) / "build-plan-demo.md").is_file()

    @pytest.mark.parametrize(
        "argv",
        [
            (),
            ("plan.md", "--bogus"),
            ("plan.md", "--state", "finished"),
            ("plan.md", "--state"),
            ("plan.md", "extra.md"),
            ("plan.md", "--state="),
        ],
        ids=["no-path", "unknown-flag", "bad-state", "missing-value", "second-path", "empty-value"],
    )
    def test_usage_errors_are_exit_two_and_never_ignored(self, tmp_path: Path, argv):
        """A swallowed token would archive under a DIFFERENT terminal state than
        the operator named, and the state is the whole content of the record."""
        project = _repo(tmp_path)
        proc = _run_hook(project, *argv)
        assert proc.returncode == 2, (proc.stdout, proc.stderr)
        assert (_artifacts(project) / "build-plan-demo.md").is_file()

    def test_it_names_a_pointer_left_dangling_by_the_move(self, tmp_path: Path):
        """A pointer still naming a moved file reads to every gate as "no active
        build plan" — the right end state reached by an accident nobody
        recorded. This reports rather than writes: the pointer is state a
        session owns."""
        project = _repo(tmp_path)
        (project / ".prawduct" / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-demo.md\n", encoding="utf-8"
        )
        proc = _run_hook(project, ".prawduct/artifacts/build-plan-demo.md")
        assert proc.returncode == 0, proc.stderr
        assert "active_build_plan" in proc.stderr

    def test_it_stays_silent_when_the_pointer_names_another_plan(self, tmp_path: Path):
        project = _repo(tmp_path)
        (_artifacts(project) / "build-plan-other.md").write_text(PLAN, encoding="utf-8")
        (project / ".prawduct" / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-other.md\n", encoding="utf-8"
        )
        proc = _run_hook(project, ".prawduct/artifacts/build-plan-demo.md")
        assert proc.returncode == 0, proc.stderr
        assert "active_build_plan" not in proc.stderr


class TestArchivingPreservesTheFilesBytes:
    """A plan is archived by MOVING it, and a move should read as a move.

    Normalizing a CRLF plan to LF rewrites every line, which turns a rename git
    can follow into a delete-plus-add that loses the file's history — multiplied
    by an unattended fleet sweep of dozens of plans per repo.
    """

    def test_crlf_survives_the_stamp_and_the_move(self, tmp_path: Path):
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        plan = artifacts / "build-plan-demo.md"
        plan.write_bytes(
            b"---\r\nartifact: build-plan\r\nscope: demo\r\n---\r\n\r\n"
            b"## Status\r\n\r\n- [x] Chunk 01: done\r\n"
        )

        result = plan_archive.archive_plan(
            plan, artifacts, state="completed", date="2026-08-10", release="v1.0.0"
        )
        assert result["status"] == "archived", result
        raw = (artifacts / "archive" / "build-plan-demo.md").read_bytes()

        assert b"lifecycle: completed" in raw
        assert raw.count(b"\n") == raw.count(b"\r\n"), "a bare LF appeared in a CRLF plan"

    def test_an_lf_plan_stays_lf(self, tmp_path: Path):
        """The control — restoring CRLF must not push CRLF onto everyone else."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        plan = artifacts / "build-plan-demo.md"
        plan.write_bytes(b"---\nartifact: build-plan\nscope: demo\n---\n\n## Status\n")

        plan_archive.archive_plan(
            plan, artifacts, state="completed", date="2026-08-10"
        )
        raw = (artifacts / "archive" / "build-plan-demo.md").read_bytes()
        assert b"\r\n" not in raw


class TestTheWriteAndTheUnlinkAreSeparate:
    """`archive_plan` must not half-complete while reporting `refused`.

    The write and the `unlink` shared one `except OSError`, so a failure to
    remove the source left the stamped copy in `archive/` AND the original live
    — two files, one scope — under a result saying nothing happened. Both this
    function's docstring ("refuses rather than half-completing") and
    `api-contract.md`'s exit-1 row ("nothing written") promised otherwise.

    It is reachable, not theoretical: a read-only `artifacts/` reproduces it,
    and it is the same shape this work keeps meeting — a path that could not
    finish, answering as one that never started.
    """

    @staticmethod
    def _repo(tmp_path: Path) -> tuple[Path, Path]:
        """`archive/` is created UP FRONT, and that is the whole fixture.

        Writing into `artifacts/archive/` needs write permission on `archive/`;
        unlinking the plan needs it on `artifacts/`. Pre-creating the archive is
        what splits the two, so a read-only `artifacts/` fails the unlink with
        the write already done. Without it `destination.parent.mkdir()` fails
        first and the test passes on the WRITE path — green while exercising
        nothing, which is how this test would have shipped believing itself.
        """
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / plan_index.ARCHIVE_DIR_NAME).mkdir()
        plan = artifacts / "build-plan-demo.md"
        plan.write_text(PLAN, encoding="utf-8")
        return artifacts, plan

    def test_an_unremovable_source_rolls_the_archived_copy_back(self, tmp_path):
        import os
        import stat

        if os.geteuid() == 0:
            pytest.skip("root ignores directory write permissions")
        artifacts, plan = self._repo(tmp_path)
        destination = plan_archive.archive_destination(plan, artifacts)
        os.chmod(artifacts, stat.S_IRUSR | stat.S_IXUSR)  # unlink(plan) will fail
        try:
            result = plan_archive.archive_plan(
                plan, artifacts, state=plan_archive.COMPLETED, date="2026-08-10"
            )
        finally:
            os.chmod(artifacts, 0o755)

        assert result["status"] == "refused"
        # "Refused" has to mean it: no orphan in the archive, source untouched.
        assert not destination.exists(), "a stamped copy survived a refused archive"
        assert plan.is_file()
        assert plan.read_text(encoding="utf-8") == PLAN

    def test_the_reason_names_the_unlink_not_the_write(self, tmp_path):
        """The two failures need different fixes — a full disk on the archive
        side, a permission problem on the source side — so one message for both
        sends the operator to the wrong one."""
        import os
        import stat

        if os.geteuid() == 0:
            pytest.skip("root ignores directory write permissions")
        artifacts, plan = self._repo(tmp_path)
        os.chmod(artifacts, stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = plan_archive.archive_plan(
                plan, artifacts, state=plan_archive.COMPLETED, date="2026-08-10"
            )
        finally:
            os.chmod(artifacts, 0o755)
        assert "after writing the archived copy" in result["reason"]
