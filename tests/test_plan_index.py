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

from lib import plan_index  # noqa: E402


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
    """

    def _artifacts(self) -> Path:
        artifacts = Path(__file__).resolve().parent.parent / ".prawduct" / "artifacts"
        if not artifacts.is_dir():
            pytest.skip("no .prawduct/artifacts/ in this checkout")
        return artifacts

    def test_the_real_tree_resolves_many_scopes_and_no_duplicates(self):
        artifacts = self._artifacts()
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        # A floor, and deliberately a low one. The assertion is "this resolver
        # reaches the repo's real plans at all"; the number must survive Chunk
        # 05's archive backfill, which moves most of this tree into `archive/`
        # inside this same PR. A tighter bound would fail on a change that is
        # the plan working as designed.
        assert len(mapping) >= 2, mapping
        assert plan_index.duplicate_scope_errors(artifacts) == []

    def test_this_branchs_own_scope_resolves(self):
        """The resolution three governance paths make every session, on real data.

        Named rather than parameterised: if this stops resolving, review
        dispatch grades the wrong plan and the Stop hook's gates read the wrong
        Status — the failure mode is silent at both.

        Safe against Chunk 05's archive backfill, which archives plans whose
        scope carries a `release=` tag: this one is in flight and has none, so
        it stays live for exactly as long as this assertion is meaningful.
        """
        artifacts = self._artifacts()
        mapping = plan_index.build_scope_to_plan_map(artifacts)
        assert "governance-artifact-lifecycle" in mapping
        assert mapping["governance-artifact-lifecycle"].name == (
            "build-plan-governance-artifact-lifecycle.md"
        )

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

    def test_a_live_plan_still_beats_its_archived_namesake(self):
        """Live-wins, on the real tree now that both halves are populated.

        The rule is load-bearing and order-dependent: discovery is sorted and
        first-wins, and `archive/build-plan-foo.md` sorts BEFORE its live
        sibling, so only walking live-first keeps a live plan winning its scope.
        """
        artifacts = self._artifacts()
        with_archive = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
        scope = "governance-artifact-lifecycle"
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
        """
        real = self._artifacts()
        artifacts = tmp_path / "artifacts"
        shutil.copytree(real, artifacts)

        before = plan_index.build_scope_to_plan_map(artifacts)
        scope = "governance-artifact-lifecycle"
        assert scope in before, "fixture assumption: this plan resolves before archival"

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
