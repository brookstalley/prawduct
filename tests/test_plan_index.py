"""Tests for `lib/plan_index.py` — which files are build plans, and their scopes.

Moved here from `test_views.py` when plan resolution left the derived-view
module. They are the contract three governance paths depend on: review dispatch,
the session briefing, and the Stop hook all resolve a branch's plan through this.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import core, plan_index  # noqa: E402


class TestParseBuildPlanFrontmatterScope:
    def test_scope_field_present(self):
        content = (
            "---\n"
            "artifact: build-plan\n"
            "scope: v1.5\n"
            "version: 2\n"
            "---\n"
            "## Status\n"
        )
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v1.5")

    def test_scope_field_quoted(self):
        content = '---\nscope: "v1.5.1"\n---\n'
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v1.5.1")

    def test_scope_field_null_or_empty_is_present_with_no_value(self):
        # YAML null literals are the documented explicit opt-out: the key is
        # PRESENT (present=True) but carries no value (None). Distinguishing
        # this from key-absent is what lets _detect_active_scope suppress
        # change-log inference rather than silently inheriting a prior scope
        # (BLD-4Q9X).
        assert plan_index.parse_build_plan_frontmatter_scope("---\nscope: null\n---\n") == (True, None)
        assert plan_index.parse_build_plan_frontmatter_scope("---\nscope: NULL\n---\n") == (True, None)
        assert plan_index.parse_build_plan_frontmatter_scope("---\nscope: ~\n---\n") == (True, None)
        # Empty value is likewise an explicit opt-out (key present, no value).
        assert plan_index.parse_build_plan_frontmatter_scope("---\nscope:\n---\n") == (True, None)
        assert plan_index.parse_build_plan_frontmatter_scope("---\nscope: \n---\n") == (True, None)

    def test_scope_field_with_inline_comment(self):
        content = "---\nscope: v1.5  # active version\n---\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v1.5")

    def test_no_frontmatter_is_absent(self):
        assert plan_index.parse_build_plan_frontmatter_scope("# Plan\nNo frontmatter.\n") == (
            False,
            None,
        )

    def test_frontmatter_without_scope_is_absent(self):
        content = "---\nartifact: build-plan\nversion: 2\n---\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_scope_after_closing_frontmatter_marker_ignored(self):
        """A `scope:` line outside the frontmatter is not the frontmatter scope."""
        content = "---\nartifact: build-plan\n---\n## Notes\nscope: shouldnotmatch\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_indented_scope_ignored(self):
        """Only column-0 `scope:` counts; nested keys don't."""
        content = "---\ndepends_on:\n  scope: nested-not-frontmatter\n---\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_leading_html_comment_tolerated(self):
        """Every real build-plan starts with an HTML comment header; the
        parser must skip it before the opening ``---``."""
        content = (
            "<!-- Build Plan: v1.5.1\n"
            "     Tier: 1 (Source of Truth)\n"
            "-->\n"
            "---\n"
            "artifact: build-plan\n"
            "scope: v1.5.1\n"
            "---\n"
            "## Status\n"
        )
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v1.5.1")

    def test_leading_single_line_html_comment_tolerated(self):
        content = "<!-- one-liner -->\n---\nscope: v2\n---\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v2")

    def test_leading_blank_lines_before_comment_tolerated(self):
        content = "\n\n<!-- header -->\n\n---\nscope: v3\n---\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (True, "v3")

    def test_html_comment_without_frontmatter_is_absent(self):
        """Comment header but no frontmatter at all → key absent."""
        content = "<!-- header -->\n# Plan\nNo frontmatter.\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_unclosed_html_comment_is_handled_leniently(self):
        """VWS-8M2Q (v1.5.1 R5): a leading HTML comment that is never closed
        (no ``-->``) must not raise or misparse. The comment scan walks to EOF,
        no ``---`` opener is found, and the result is the safe ``(False, None)``
        absent reading — the documented lenient handling of malformed input."""
        content = (
            "<!-- Build Plan: this header is never closed\n"
            "     no terminator on any line\n"
            "---\n"
            "scope: v9.9\n"
            "---\n"
            "## Status\n"
        )
        # The `---`/`scope:` lines are swallowed by the unterminated comment scan,
        # so the frontmatter is unreachable → (False, None), no exception.
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_unclosed_html_comment_only_input(self):
        """An input that is nothing but an unclosed comment also degrades to
        absent rather than raising (empty/EOF edge of the lenient path)."""
        content = "<!-- open and never closed\nstill open\n"
        assert plan_index.parse_build_plan_frontmatter_scope(content) == (False, None)


def _write_scoped_plan(
    artifacts_dir: Path, filename: str, scope: str | None, chunk_ids: list[str]
) -> None:
    """Write a minimal scope-tagged build plan with the given chunk lines."""
    front = "---\nartifact: build-plan\n"
    if scope is not None:
        front += f"scope: {scope}\n"
    front += "---\n\n## Status\n"
    body = "".join(f"- [ ] Chunk {cid}: work\n" for cid in chunk_ids)
    (artifacts_dir / filename).write_text(front + body)


class TestBuildScopeToPlanMap:
    def test_maps_each_scope_to_its_plan_file(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan-beta.md", "beta", ["01"])
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert set(mapping) == {"alpha", "beta"}
        assert mapping["alpha"].name == "build-plan-alpha.md"
        assert mapping["beta"].name == "build-plan-beta.md"

    def test_excludes_plans_without_scope_frontmatter(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan.md", None, ["01"])  # no scope
        (artifacts / "project-preferences.md").write_text("# prefs, not a plan\n")
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert set(mapping) == {"alpha"}

    def test_duplicate_scope_keeps_first_by_sorted_filename(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "b-plan.md", "dup", ["01"])
        _write_scoped_plan(artifacts, "a-plan.md", "dup", ["02"])
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert mapping["dup"].name == "a-plan.md"  # first by sorted filename

    def test_missing_dir_returns_empty(self, tmp_path: Path):
        assert plan_index.build_scope_to_plan_map(tmp_path / "nope") == {}

    def test_a_nested_plan_is_discovered(self, tmp_path: Path):
        """#201 leg 1: plans below the top level of `artifacts/` must be visible.

        A `glob("*.md")` saw only the top level, so a repo organizing plans as
        `artifacts/plans/<id>/build-plan.md` had every one invisible — the scope
        resolved to nothing, the coverage diagnostic errored, and the caller then
        failed closed for the whole run. Four surveyed repos carried 16 nested
        plans each (2026-07-21 fleet survey).

        This is the POSITIVE half of the archive-pruning walk. `TestArchivePruning`
        asserts subtrees are skipped; without this, a walk that descended nothing
        at all would satisfy every pruning test in this file.
        """
        artifacts = tmp_path / "artifacts"
        nested = artifacts / "plans" / "deep"
        nested.mkdir(parents=True)
        _write_scoped_plan(nested, "build-plan.md", "nested", ["01"])
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert set(mapping) == {"nested"}
        assert mapping["nested"] == nested / "build-plan.md"


class TestDeclaresNonBuildPlanArtifact:
    """Direct cases for the plan/not-a-plan predicate.

    `TestScopeCollectorsAgainstTheRealArtifactsDirectory` exercises this against
    the live tree, but only ACCIDENTALLY pins the fail-safe half: "an absent
    `artifact:` key still reads as a build plan" holds there solely because
    `build-plan-release-readiness.md` happens to omit the key today. Adding it
    — ordinary hygiene, and a reviewer would wave it through — silently unpins
    the property, and a later tightening to a strict `artifact: build-plan`
    requirement would then go GREEN while dropping real plans from regen-plan_index.

    A fixture whose coverage depends on a fact nobody is guarding is the
    corpus's "a fixture's world is narrower than the requirement it certifies"
    one level up: the world is right today and nothing holds it there.
    """

    def _fm(self, body: str) -> str:
        return f"---\n{body}\n---\n\n# Title\n"

    def test_absent_artifact_key_reads_as_a_build_plan(self):
        # The fail-safe direction. Excluding a real plan is the worse error:
        # its scope regenerates nothing, and nothing says so.
        assert not plan_index._declares_non_build_plan_artifact(
            self._fm("scope: some-scope")
        )

    def test_explicit_build_plan_type_reads_as_a_build_plan(self):
        assert not plan_index._declares_non_build_plan_artifact(
            self._fm("artifact: build-plan\nscope: some-scope")
        )

    def test_another_declared_type_is_excluded(self):
        for kind in ("collapse-map", "design", "design-note", "discovery",
                     "reference", "release-plan"):
            assert plan_index._declares_non_build_plan_artifact(
                self._fm(f"artifact: {kind}\nscope: some-scope")
            ), f"artifact: {kind} should not be treated as a build plan"

    def test_empty_artifact_value_reads_as_a_build_plan(self):
        # Mirrors the `scope:` parser's opt-out reading: a present-but-empty
        # key is not a declaration of some OTHER type, so it must not exclude.
        assert not plan_index._declares_non_build_plan_artifact(
            self._fm("artifact:\nscope: some-scope")
        )

    def test_a_nested_artifact_key_is_not_a_declaration(self):
        # `governed_by:` blocks in this repo's plans contain indented
        # `- artifact: architecture` lines. Reading those as the file's own
        # type would exclude most build plans in the repo — the highest-stakes
        # case here.
        #
        # Honest note on what enforces it: the explicit indent skip in
        # `_declares_non_build_plan_artifact` is REDUNDANT. `startswith` runs
        # on the un-lstripped line, so `  - artifact: …` and `\tartifact: …`
        # are already rejected; deleting the skip leaves this green. The skip
        # is kept only for symmetry with `_parse_build_plan_frontmatter_scope`,
        # where it is equally redundant — the two readers should look identical
        # so a future edit to one is obviously owed to the other.
        #
        # This test pins the PROPERTY (a nested key is not a declaration),
        # which is worth pinning however many mechanisms enforce it. It does
        # not prove the skip line, and a mutation of that line will not turn it
        # red — recorded because a test whose stated subject and actual subject
        # differ is how a guard silently stops guarding.
        assert not plan_index._declares_non_build_plan_artifact(
            self._fm("scope: some-scope\ngoverned_by:\n  - artifact: architecture")
        )

    def test_quoted_and_commented_values_are_handled(self):
        assert plan_index._declares_non_build_plan_artifact(
            self._fm('artifact: "collapse-map"  # a map, not a plan\nscope: s')
        )
        assert not plan_index._declares_non_build_plan_artifact(
            self._fm("artifact: 'build-plan'\nscope: s")
        )

    def test_no_frontmatter_reads_as_a_build_plan(self):
        assert not plan_index._declares_non_build_plan_artifact("# Just a title\n")

    def test_is_build_plan_is_the_same_predicate_read_forward(self):
        """The public spelling, added when `plan_archive` needed the question
        asked positively. Pinned as an exact inverse so the two cannot drift into
        disagreeing about the same document — which is the failure mode a second
        name for one predicate invites."""
        for content in (
            self._fm("artifact: build-plan\nscope: s"),
            self._fm("artifact: release-plan\nrelease: v1.0.0"),
            self._fm("scope: s"),
            "# Just a title\n",
        ):
            assert plan_index.is_build_plan(content) is not (
                plan_index._declares_non_build_plan_artifact(content)
            )

    def test_is_build_plan_fails_safe_toward_being_a_plan(self):
        """A document declaring no ``artifact:`` at all counts as a plan.

        `build-plan-release-readiness.md` is the real counter-example: requiring
        an explicit `build-plan` would silently drop it. Callers reading a plan's
        completeness depend on this direction — excluding an unlabelled plan is
        how one gets filed away as finished without ever being read.
        """
        assert plan_index.is_build_plan(self._fm("scope: s")) is True
        assert plan_index.is_build_plan(self._fm("artifact: discovery\nscope: s")) is False


class TestArchivePruning:
    """An archived plan is history, not a live assertion — and is never read.

    Two properties, and they fail in different directions. **Correctness:**
    discovery is `sorted()` and its consumers are first-wins, and
    `archive/build-plan-foo.md` sorts BEFORE `build-plan-foo.md`, so an archived
    copy would shadow its own live sibling and resolve the retired plan.
    **Cost:** this walk runs at every session start and every session end, so
    reading-then-skipping would make each session pay for every plan the repo
    has ever completed — a per-session cost that grows without limit.
    """

    def test_archived_namesake_does_not_shadow_its_live_sibling(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        (artifacts / "archive").mkdir(parents=True)
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts / "archive", "build-plan-alpha.md", "alpha", ["01"])
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert mapping["alpha"] == artifacts / "build-plan-alpha.md"

    def test_archive_only_scope_is_invisible_by_default(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        (artifacts / "archive").mkdir(parents=True)
        _write_scoped_plan(artifacts / "archive", "build-plan-old.md", "old", ["01"])
        assert plan_index.build_scope_to_plan_map(artifacts) == {}

    def test_nested_archive_component_is_pruned_too(self, tmp_path: Path):
        # The rule is "any path component named archive", not "the top-level
        # archive dir" — a repo laying plans out as plans/<id>/ archives inside
        # that structure, and a top-level-only test passes on both readings.
        artifacts = tmp_path / "artifacts"
        nested = artifacts / "plans" / "deep" / "archive"
        nested.mkdir(parents=True)
        _write_scoped_plan(nested, "build-plan-old.md", "old", ["01"])
        assert plan_index.build_scope_to_plan_map(artifacts) == {}

    def test_the_archive_directory_is_never_descended(self, tmp_path: Path, monkeypatch):
        """The prune is a SKIPPED SUBTREE, not a discarded result.

        This is the assertion the first version of this test failed to make. It
        asserted only that no archived file was *opened*, which
        `rglob("*.md")` + `continue` also satisfies — that shape walks the whole
        archive, stats every file in it, and throws the paths away. The cost
        BP9 exists to bound is the traversal, so the test has to see the
        traversal: `os.walk` reaches directories through `os.scandir`, so a spy
        there records exactly which directories were entered.
        """
        artifacts = tmp_path / "artifacts"
        (artifacts / "archive" / "deep").mkdir(parents=True)
        _write_scoped_plan(artifacts, "build-plan-live.md", "live", ["01"])
        _write_scoped_plan(artifacts / "archive" / "deep", "build-plan-old.md", "old", ["01"])

        scanned: list[str] = []
        real_scandir = os.scandir

        def spy(path=".", *args, **kwargs):
            scanned.append(str(path))
            return real_scandir(path, *args, **kwargs)

        monkeypatch.setattr(os, "scandir", spy)
        plan_index.build_scope_to_plan_map(artifacts)

        assert any(str(artifacts) == s for s in scanned), "the live tree must be walked"
        assert not [s for s in scanned if "archive" in Path(s).parts], scanned

    def test_an_archived_plan_is_never_opened(self, tmp_path: Path, monkeypatch):
        """The weaker half of the same property, kept because it fails differently.

        A future implementation could skip the subtree and still open an
        archived file by another route (a name lookup, a fallback glob). This
        catches that; the descent test above catches the cost regression.
        """
        artifacts = tmp_path / "artifacts"
        (artifacts / "archive").mkdir(parents=True)
        _write_scoped_plan(artifacts, "build-plan-live.md", "live", ["01"])
        _write_scoped_plan(artifacts / "archive", "build-plan-old.md", "old", ["01"])

        opened: list[Path] = []
        real_read_text = Path.read_text

        def spy(self, *args, **kwargs):
            opened.append(self)
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", spy)
        plan_index.build_scope_to_plan_map(artifacts)

        assert artifacts / "build-plan-live.md" in opened, "the live plan must be read"
        assert not [p for p in opened if "archive" in p.parts], opened

    def test_include_archived_finds_history_and_still_prefers_live(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        (artifacts / "archive").mkdir(parents=True)
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts / "archive", "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts / "archive", "build-plan-old.md", "old", ["01"])
        mapping = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert mapping["old"] == artifacts / "archive" / "build-plan-old.md"
        assert mapping["alpha"] == artifacts / "build-plan-alpha.md"

    def test_absent_archive_directory_is_a_no_op(self, tmp_path: Path):
        # Pruning a directory that does not exist must be silent: this landed
        # before anything created the archive, and every repo in the fleet is in
        # that state until it archives its first plan.
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        assert set(plan_index.build_scope_to_plan_map(artifacts)) == {"alpha"}
        assert set(plan_index.build_scope_to_plan_map(artifacts, include_archived=True)) == {
            "alpha"
        }


class TestDuplicateScopeErrors:
    def test_duplicate_scope_is_reported_with_its_scope(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-a.md", "dup", ["01"])
        _write_scoped_plan(artifacts, "build-plan-b.md", "dup", ["01"])
        errors = plan_index.duplicate_scope_errors(artifacts)
        assert len(errors) == 1
        scope, message = errors[0]
        assert scope == "dup"
        assert "build-plan-b.md" in message and "keeping" in message

    def test_distinct_scopes_are_clean(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-a.md", "a", ["01"])
        _write_scoped_plan(artifacts, "build-plan-b.md", "b", ["01"])
        assert plan_index.duplicate_scope_errors(artifacts) == []


class TestAgainstTheRealArtifactsDirectory:
    """Characterization: the properties that must survive `views.py`'s deletion.

    Every other test here builds a tmp `artifacts/` with two or three
    hand-written files, and all of them stayed green while `regen-views` was
    fatally broken on the real tree for an entire branch — a scope-tagged
    collapse-map artifact that no fixture author would think to write. That is
    the corpus rule *a fixture's world is narrower than the requirement it
    certifies*, and the fix is not a better fixture: it is running the real
    resolver over the real directory, which holds every artifact type this repo
    has ever produced.

    Skipped when `.prawduct/artifacts/` is absent so the plugin's own suite
    still runs from a checkout without product state.

    **The corpus is live + archived, and that is load-bearing.** An earlier
    version read the LIVE tree only, which made "this repo is mid-development"
    an unnamed invariant of five assertions: the release runbook archives every
    shipped plan, so a repo that has just cut a release has an empty live map
    and all five went red at once — the release working exactly as designed.
    The archive is the phase-independent corpus (it only ever grows, and an
    archived plan is still a real plan with real frontmatter), so reading it is
    not a relaxation but a strictly larger and more discriminating corpus. The
    two assertions that genuinely need a LIVE plan construct one by perturbing
    a copy rather than borrowing whichever plan the branch is building.
    """

    def _artifacts(self) -> Path:
        artifacts = Path(__file__).resolve().parent.parent / ".prawduct" / "artifacts"
        if not artifacts.is_dir():
            pytest.skip("no .prawduct/artifacts/ in this checkout")
        return artifacts

    def _copy_with_a_live_plan(self, tmp_path: Path) -> tuple[Path, str, Path]:
        """A tmp copy of the real tree with one archived plan promoted to live.

        Returns ``(artifacts, scope, live_path)``. Two assertions below need a
        live plan to perturb, and taking the repo's current one made them fail
        the moment it was archived — which is a release, not a regression.
        Promoting a real archived plan supplies one at any point in the release
        cycle while keeping the corpus real: the plan's frontmatter, name and
        scope are the repo's own, not a fixture author's guess.

        **The candidate is chosen from the filesystem, never from the resolver
        under test.** Deriving it as "in the archived map but not the live one"
        reads plausibly and is a trap: when the live walk stops pruning
        ``archive/`` — precisely the defect
        ``test_archiving_a_real_plan_removes_it_from_the_live_map`` exists to
        catch — that difference goes empty, the helper skips, and the test
        reports "not applicable" for a repo whose resolver is broken. A skip is
        indistinguishable from a pass in a summary, so the bug would ship green.
        Walking the archive directory instead keeps the selection independent of
        the thing being graded, and the live-map check below is an assertion
        rather than a skip for the same reason.
        """
        real = self._artifacts()
        artifacts = tmp_path / "artifacts"
        shutil.copytree(real, artifacts)

        archive = artifacts / plan_index.ARCHIVE_DIR_NAME
        if not archive.is_dir():
            pytest.skip("no archive/ in this checkout — nothing to promote")

        scope = archived_path = None
        for candidate in sorted(archive.rglob("*.md")):
            present, declared = plan_index.parse_build_plan_frontmatter_scope(
                candidate.read_text(encoding="utf-8")
            )
            if present and declared:
                scope, archived_path = declared, candidate
                break
        if archived_path is None:
            pytest.skip("no scope-declaring plan in archive/ — nothing to promote")

        assert scope not in plan_index.build_scope_to_plan_map(artifacts), (
            f"archived scope {scope!r} already resolves as LIVE before anything was "
            f"promoted — the live walk is not pruning archive/"
        )

        live_path = artifacts / archived_path.name
        shutil.copy2(archived_path, live_path)
        return artifacts, scope, live_path

    def test_the_real_tree_resolves_many_scopes_and_no_duplicates(self):
        artifacts = self._artifacts()
        mapping = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        # A floor over the live+archived corpus, which only grows: every plan
        # this repo has ever finished stays in `archive/`. Reading the live
        # tree alone made this assert "a plan is currently in flight", which is
        # false for the whole of a release and is not a resolver failure.
        assert len(mapping) >= 20, len(mapping)
        # Duplicate detection stays on the LIVE tree, where it is the contract:
        # `duplicate_scope_errors` reports plans that would make a live lookup a
        # coin toss, and it is meaningful at any size including zero.
        assert plan_index.duplicate_scope_errors(artifacts) == []

    def test_the_active_build_plan_pointer_resolves(self):
        """The resolution three governance paths make every session, on real data.

        If this stops resolving, review dispatch grades the wrong plan and the
        Stop hook's gates read the wrong Status — the failure mode is silent at
        both. So it is graded through the same pointer those three paths read,
        `active_build_plan`, rather than a hardcoded scope name: a literal has
        to be edited every branch and goes red the day its plan is archived,
        which is the plan succeeding.

        A null pointer means no plan is under active build — true between work
        cycles and for the whole of a release. That is skipped with the reason
        named, not asserted away.

        **What turns this red**, stated because a guard nobody can falsify is a
        guard that measured nothing: a pointer left at a plan that moved or was
        archived (the recurring stale-pointer defect this file's own comments
        record three times), a plan carrying no frontmatter `scope:`, and a
        second plan declaring the same scope and sorting earlier — which steals
        the key and sends dispatch at the wrong file, silently, which is the
        whole failure mode. What it does **not** grade is whether the scope's
        *value* is the right one: the map is keyed from the same frontmatter
        this reads, so the two agree by construction. The old hardcoded literal
        did grade that, at the cost of needing an edit every branch and going
        red the day its plan was archived; nothing here replaces it, and the
        change-log join in `test_change_log.py` is the assertion that pairs a
        scope with an independent source.
        """
        artifacts = self._artifacts()
        prawduct_dir = artifacts.parent
        # The production reader, not a second parse of the same file: the point
        # is to grade the resolution those three paths really make, and a
        # private re-implementation here could agree with the YAML while
        # disagreeing with them.
        pointer = core.read_str_yaml_key(
            prawduct_dir / "project-state.yaml", core.BUILD_PLAN_POINTER_KEY
        )
        if not pointer:
            pytest.skip("active_build_plan is null — no plan under active build")

        plan_path = prawduct_dir / pointer.removeprefix(".prawduct/")
        if not plan_path.is_file():
            pytest.fail(f"active_build_plan points at a missing file: {pointer}")

        present, scope = plan_index.parse_build_plan_frontmatter_scope(
            plan_path.read_text(encoding="utf-8")
        )
        assert present and scope, f"{pointer} declares no frontmatter scope"
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert scope in mapping, (scope, sorted(mapping))
        assert mapping[scope] == plan_path

    def test_the_backfilled_archive_still_resolves_by_scope(self):
        """The backfill's 73 plans must stay findable, on the real archive.

        This assertion could not be written before the backfill existed — the
        repo had no populated archive to run it against — and it guards the
        failure the backfill could plausibly have caused: `check-releasability`
        resolves a release's plan with `include_archived=True`, so if archiving
        had made those plans unresolvable, every release-readiness check on a
        past scope would have started answering "no plan" instead of failing.
        Silent, and only at release time.

        A floor rather than an exact count: the archive grows every time a plan
        finishes, and a test that has to be edited on each archival is a test
        people learn to edit rather than read.
        """
        artifacts = self._artifacts()
        live = plan_index.build_scope_to_plan_map(artifacts)
        with_archive = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)

        recovered = set(with_archive) - set(live)
        assert len(recovered) >= 20, (
            f"only {len(recovered)} archived scope(s) resolve; the backfill moved "
            f"dozens of shipped plans into archive/ and release readiness reads "
            f"them from there"
        )
        # Every recovered plan really is under an archive/ directory — otherwise
        # this passes on a live plan that merely failed to appear in `live`.
        for scope in sorted(recovered):
            assert plan_index.ARCHIVE_DIR_NAME in with_archive[scope].parts, scope

    def test_a_live_plan_still_beats_its_archived_namesake(self, tmp_path: Path):
        """Live-wins, with the namesake collision actually constructed.

        The rule is load-bearing and order-dependent: discovery is sorted and
        first-wins, and `archive/build-plan-foo.md` sorts BEFORE its live
        sibling, so only walking live-first keeps a live plan winning its scope.

        Constructed rather than observed, and that is the substance of this
        repair. The real tree holds no live/archived namesake — every plan is
        in exactly one half — so asserting live-wins about a scope that merely
        happens to be live passed without the collision ever existing, and it
        died the moment that plan was archived. Promoting a real archived plan
        into the live tree of a copy puts BOTH copies of one scope in the same
        corpus, which is the only shape in which live-wins can fail.
        """
        artifacts, scope, live_path = self._copy_with_a_live_plan(tmp_path)

        with_archive = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert with_archive[scope] == live_path
        assert plan_index.ARCHIVE_DIR_NAME not in with_archive[scope].parts

    def test_archiving_a_real_plan_removes_it_from_the_live_map(self, tmp_path: Path):
        """Archival, exercised on the real corpus rather than asserted about it.

        An earlier version of this test asserted that no archived path appears
        in the live map — which passes on a tree that HAS no archive, and this
        repo has none until Chunk 04 creates one. Perturbing the real tree is
        what makes the assertion capable of failing: copy it, archive a plan
        that really exists, and require the live map to lose exactly that scope
        while `include_archived` recovers it.

        The other half is `TestArchivePruning`, whose fixtures can construct the
        shapes a real tree does not happen to contain. This one covers what a
        fixture author would not think to write.

        The live plan it archives is one it promotes itself, not whichever plan
        the branch is building: borrowing the branch's plan made this assert
        "a plan is currently in flight", which a release legitimately falsifies.
        """
        artifacts, scope, _live_path = self._copy_with_a_live_plan(tmp_path)

        before = plan_index.build_scope_to_plan_map(artifacts)
        assert scope in before, "promoted plan must resolve as live before archival"

        archive = artifacts / plan_index.ARCHIVE_DIR_NAME
        archive.mkdir(exist_ok=True)
        shutil.move(str(before[scope]), str(archive / before[scope].name))

        after = plan_index.build_scope_to_plan_map(artifacts)
        assert scope not in after, "an archived plan must not resolve as live"
        assert set(before) - set(after) == {scope}, "archival moved more than one scope"

        recovered = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        assert recovered[scope] == archive / before[scope].name
        assert not [
            path
            for path in after.values()
            if plan_index.ARCHIVE_DIR_NAME in path.parts
        ]
