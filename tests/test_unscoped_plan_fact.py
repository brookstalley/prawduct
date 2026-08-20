"""A build plan declaring no ``scope:`` is invisible to the scope walk — and says so.

``plan_index.iter_scoped_plan_candidates`` yields only scope-declaring plans, by
design: it backs a *map*, and a map keyed on scope has nothing to do with a plan
that declares none. Every consumer of that walk therefore reports a set that
reads as the whole artifacts directory while silently omitting those plans. The
remedy is the one the module already uses for an *unreadable* file: the swallow
stays where the map needs it, and the fact is published separately on a cold
path.

**What makes an unscoped document a build plan is the whole difficulty**, and it
is not the predicate the walk already has. ``_declares_non_build_plan_artifact``
excludes only a document declaring some *other* ``artifact:`` type and treats one
declaring none as a plan — a direction chosen for the map, where a declared
``scope:`` is already strong evidence. The unscoped population carries no such
evidence, and against this repo's live ``artifacts/`` that direction alone names
22 documents of which 20 are release plans, spikes, audits and preferences. So
the published fact requires POSITIVE evidence of plan-ness, and
:class:`TestTheShapePredicateAgainstTheRealCorpus` is what keeps that claim
honest — a fixture written from the same belief as the predicate can only ever
confirm the belief.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import buildplan_refs, plan_index  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent

SCOPED = "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n\n- [x] Chunk 01: a\n"
# The three shapes each carry EXACTLY ONE of the signals, so a case claiming a
# signal suffices cannot be passing on a second one it also happens to have.
#: Declared type alone — no roster, no chunk heading.
UNSCOPED_PLAN = "---\nartifact: build-plan\n---\n\n# A plan\n\nProse only.\n"
#: Roster alone — `waiver-pragma-plan.md`'s real shape, chunks as list items
#: under a heading no chunk matcher parses.
UNSCOPED_BY_ROSTER = "# A plan\n\n## Status\n\n- [ ] Chunk 01: a\n"
#: Chunk heading alone — `build-plan-coverage-perf.md` carries no Status section.
UNSCOPED_BY_HEADING = "# A plan\n\n## Chunks\n\n### Chunk 01 — a\n"
#: A design note. No frontmatter at all, so the map's predicate calls it a plan.
NOT_A_PLAN = "# Boundary Patterns\n\nProse about contract surfaces.\n"
#: Declares another type, so even the map's predicate excludes it.
OTHER_ARTIFACT = "---\nartifact: design\n---\n\n# A design note\n"
#: `scope:` present and null — the parser's documented explicit opt-out.
OPTED_OUT = "---\nartifact: build-plan\nscope: null\n---\n\n## Status\n\n- [ ] Chunk 01: a\n"


def _tree(root: Path, files: dict) -> Path:
    """Write ``{relative path: content}`` under ``root/artifacts`` and return it."""
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return artifacts


MIXED = {
    "build-plan-alpha.md": SCOPED,
    "build-plan-typed.md": UNSCOPED_PLAN,
    "waiver-plan.md": UNSCOPED_BY_ROSTER,
    "perf-plan.md": UNSCOPED_BY_HEADING,
    "boundary-patterns.md": NOT_A_PLAN,
    "a-design.md": OTHER_ARTIFACT,
    f"{plan_index.ARCHIVE_DIR_NAME}/build-plan-old.md": UNSCOPED_PLAN,
    f"plans/007/{plan_index.ARCHIVE_DIR_NAME}/build-plan-nested-old.md": UNSCOPED_PLAN,
}


class TestTheDefectIsRealBeforeItIsFixed:
    """The positive control: assert the blind spot, don't assume it.

    The precondition is WALKED, never resolved through the mechanism under
    test — a fixture built by asking the resolver turns that resolver's failure
    into a silent agreement.
    """

    def test_the_hot_walk_omits_every_unscoped_plan(self, tmp_path: Path) -> None:
        artifacts = _tree(tmp_path, MIXED)
        on_disk = {p.name for p in artifacts.rglob("*.md")}
        assert {"build-plan-typed.md", "waiver-plan.md", "perf-plan.md"} <= on_disk

        yielded = {p.name for p, _scope in plan_index.iter_scoped_plan_candidates(artifacts)}
        assert yielded == {"build-plan-alpha.md"}, (
            "the map yields only scope-declaring plans — if this ever changes, the "
            "published fact below is measuring something else"
        )


class TestPlansMissingScope:
    def test_names_exactly_the_unscoped_plans(self, tmp_path: Path) -> None:
        artifacts = _tree(tmp_path, MIXED)
        assert [p.name for p in buildplan_refs.plans_missing_scope(artifacts)] == [
            "build-plan-typed.md",
            "perf-plan.md",
            "waiver-plan.md",
        ]

    def test_a_fully_scoped_tree_reports_none(self, tmp_path: Path) -> None:
        """The other half — without it the assertion above passes on a list that
        is never empty, and the fact would say nothing."""
        artifacts = _tree(tmp_path, {"build-plan-alpha.md": SCOPED})
        assert buildplan_refs.plans_missing_scope(artifacts) == []

    def test_a_document_that_is_not_a_plan_is_not_named(self, tmp_path: Path) -> None:
        """The measured failure mode. `boundary-patterns.md` declares no
        `artifact:` at all, so the MAP's predicate calls it a build plan; naming
        it here is how a control that fires 20 times on its first run stops being
        read."""
        artifacts = _tree(tmp_path, {"boundary-patterns.md": NOT_A_PLAN})
        assert buildplan_refs.plans_missing_scope(artifacts) == []

    def test_a_document_declaring_another_type_is_not_named_even_with_plan_shape(
        self, tmp_path: Path
    ) -> None:
        """A declared type outranks the shape signals, and only this shape can
        show it: a design note is rejected for having no shape at all, so it
        leaves the type check untested. A release plan carrying a chunk roster
        is the authoring shape that separates them — it has said what it is, and
        the sweep it would otherwise be counted into is about build plans."""
        content = "---\nartifact: release-plan\n---\n\n## Status\n\n- [ ] Chunk 01: cut\n"
        assert buildplan_refs.has_build_plan_shape(content), (
            "the fixture must carry plan shape, or it passes for the wrong reason"
        )
        artifacts = _tree(tmp_path, {"release-plan-v9.md": content})
        assert buildplan_refs.plans_missing_scope(artifacts) == []

    def test_an_archived_plan_is_not_named(self, tmp_path: Path) -> None:
        """An archived plan is a record, and nothing is going to re-scope it —
        the same rule the walk it shadows applies, at every depth."""
        artifacts = _tree(
            tmp_path,
            {
                f"{plan_index.ARCHIVE_DIR_NAME}/build-plan-old.md": UNSCOPED_PLAN,
                f"plans/007/{plan_index.ARCHIVE_DIR_NAME}/nested-old.md": UNSCOPED_PLAN,
            },
        )
        assert buildplan_refs.plans_missing_scope(artifacts) == []

    def test_an_explicit_scope_opt_out_is_not_named(self, tmp_path: Path) -> None:
        """`scope:` set to the YAML null literal is the parser's documented "do
        not scope-filter me". A declared choice reported back as a coverage gap
        is a control that can never go quiet."""
        artifacts = _tree(tmp_path, {"opted-out.md": OPTED_OUT})
        assert plan_index.parse_build_plan_frontmatter_scope(OPTED_OUT) == (True, None)
        assert buildplan_refs.plans_missing_scope(artifacts) == []

    def test_an_unreadable_file_is_left_to_its_own_published_fact(
        self, tmp_path: Path
    ) -> None:
        """Two facts, two questions. A file that cannot be decoded is
        `unreadable_candidates`' subject; reporting it here too would double-count
        it in the operator's coverage figure."""
        artifacts = _tree(tmp_path, {"build-plan-alpha.md": SCOPED})
        (artifacts / "binary.md").write_bytes(b"---\nartifact: build-plan\n---\n\xff\xfe\x00")

        assert buildplan_refs.plans_missing_scope(artifacts) == []
        assert [
            Path(item["path"]).name for item in plan_index.unreadable_candidates(artifacts)
        ] == ["binary.md"]

    def test_a_missing_artifacts_dir_is_no_candidates(self, tmp_path: Path) -> None:
        assert buildplan_refs.plans_missing_scope(tmp_path / "nope") == []

    def test_nested_plans_are_kept_distinct(self, tmp_path: Path) -> None:
        """Repos organizing plans as `plans/<id>/build-plan.md` have several
        sharing one filename, and the operator reads this list to act on it."""
        artifacts = _tree(
            tmp_path,
            {
                "plans/ALPHA/build-plan.md": UNSCOPED_PLAN,
                "plans/BETA/build-plan.md": UNSCOPED_PLAN,
            },
        )
        found = buildplan_refs.plans_missing_scope(artifacts)
        assert {plan_index.display_path(p, artifacts) for p in found} == {
            "plans/ALPHA/build-plan.md",
            "plans/BETA/build-plan.md",
        }


class TestEachShapeSignalCarriesItsOwnPlan:
    """Each signal in the union is load-bearing on its own — one real plan in
    this repo's corpus is reachable by that signal and no other, so dropping any
    one of them silently re-blinds a plan the fact exists to name."""

    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("declared type", UNSCOPED_PLAN),
            ("status roster", UNSCOPED_BY_ROSTER),
            ("chunk heading", UNSCOPED_BY_HEADING),
        ],
    )
    def test_the_signal_alone_is_enough(self, tmp_path: Path, name: str, content: str) -> None:
        artifacts = _tree(tmp_path, {"plan.md": content})
        assert [p.name for p in buildplan_refs.plans_missing_scope(artifacts)] == [
            "plan.md"
        ], f"{name} alone must identify a build plan"


class TestTheGapSentenceNamesTheInvisiblePlans:
    """`#642` cause 1 at the surface it was asked for.

    A dispatch scope that resolves to no plan produces ``chunk-ref-missing
    unchecked`` — and the sentence explaining it gave the reader one of the two
    explanations. "No such plan exists" and "a plan exists but declares no
    `scope:`, so this lookup could never have found it" are different problems
    with different remedies, and the second is the one the reader cannot deduce.
    """

    def _repo(self, tmp_path: Path, files: dict) -> Path:
        prawduct = tmp_path / ".prawduct"
        _tree(prawduct, files)
        return prawduct

    def test_the_gap_names_a_scopeless_plan(self, tmp_path: Path) -> None:
        prawduct = self._repo(tmp_path, {"build-plan-mystery.md": UNSCOPED_PLAN})
        plan = buildplan_refs.resolve_reviewed_plan(tmp_path, prawduct, "mystery")

        assert plan.path is None
        assert "declare no `scope:`" in plan.gap
        assert "build-plan-mystery.md" in plan.gap

    def test_a_repo_with_none_gets_no_footnote(self, tmp_path: Path) -> None:
        """Without this the assertion above passes on a sentence that always
        carries the clause, and the clause would tell the reader nothing."""
        prawduct = self._repo(tmp_path, {"build-plan-alpha.md": SCOPED})
        plan = buildplan_refs.resolve_reviewed_plan(tmp_path, prawduct, "mystery")

        assert plan.path is None
        assert "declare no `scope:`" not in plan.gap

    def test_a_resolved_scope_pays_nothing_and_says_nothing(self, tmp_path: Path) -> None:
        """The footnote belongs to the failure branch. A resolution that found
        its plan has no gap at all — and must not grow one, nor the walk behind
        it, on the path every review dispatch takes."""
        prawduct = self._repo(
            tmp_path,
            {"build-plan-alpha.md": SCOPED, "build-plan-mystery.md": UNSCOPED_PLAN},
        )
        plan = buildplan_refs.resolve_reviewed_plan(tmp_path, prawduct, "alpha")

        assert plan.path is not None
        assert plan.gap is None

    def test_a_long_list_is_summarised_and_says_that_it_was(self, tmp_path: Path) -> None:
        """The gap is prose inside a reviewer's payload, so the list is bounded —
        and the remainder is counted, because a truncation that does not say so
        is the same silence this whole fact exists to end."""
        many = {f"build-plan-{i:02d}.md": UNSCOPED_PLAN for i in range(9)}
        prawduct = self._repo(tmp_path, many)
        plan = buildplan_refs.resolve_reviewed_plan(tmp_path, prawduct, "mystery")

        named = [name for name in many if name in plan.gap]
        assert len(named) == buildplan_refs._UNSCOPED_NAMED_LIMIT
        assert f"and {len(many) - len(named)} more" in plan.gap
        assert f"{len(many)} build plan(s)" in plan.gap

    def test_an_unreadable_artifacts_dir_degrades_to_the_bare_gap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A footnote on an already-reported non-answer must never become an
        exception in the dispatch path — advice fails soft."""
        prawduct = self._repo(tmp_path, {"build-plan-mystery.md": UNSCOPED_PLAN})

        def boom(_artifacts_dir):
            raise OSError("artifacts/ is not readable")

        monkeypatch.setattr(buildplan_refs, "plans_missing_scope", boom)
        plan = buildplan_refs.resolve_reviewed_plan(tmp_path, prawduct, "mystery")

        assert plan.path is None
        assert "no build plan under" in plan.gap
        assert "declare no `scope:`" not in plan.gap


class TestTheShapePredicateAgainstTheRealCorpus:
    """A fixture encodes the belief the predicate was written from, so a suite
    made of them is green precisely where that belief is wrong. These read the
    documents this repo actually carries.

    Stated as invariants, never as counts: entries get scoped, archived and
    added, and a count here would be stale before it was useful.
    """

    @pytest.fixture
    def artifacts(self) -> Path:
        directory = REPO_ROOT / ".prawduct" / "artifacts"
        assert directory.is_dir(), (
            f"{directory} is missing — this control is the only thing standing "
            "between the shape predicate and a corpus it was never measured on, "
            "so a skip here would be indistinguishable from a pass"
        )
        return directory

    def test_every_named_document_carries_real_plan_evidence(self, artifacts: Path) -> None:
        named = buildplan_refs.plans_missing_scope(artifacts)
        for path in named:
            content = path.read_text(encoding="utf-8")
            assert buildplan_refs.has_build_plan_shape(content), (
                f"{path} was named without the evidence that admits it"
            )

    def test_the_design_notes_beside_them_are_not_named(self, artifacts: Path) -> None:
        """The specificity half. Each of these is scope-less, declares no
        `artifact:` type, and is emphatically not a build plan — the population
        the map's own predicate would hand over wholesale."""
        named = {p.name for p in buildplan_refs.plans_missing_scope(artifacts)}
        for name in ("project-preferences.md", "boundary-patterns.md"):
            assert (artifacts / name).is_file(), (
                f"{name} is this test's subject and is gone — re-pick a real "
                "scope-less non-plan from artifacts/ rather than deleting the case"
            )
            assert name not in named

    def test_every_archived_plan_would_have_been_recognised(self, artifacts: Path) -> None:
        """Sensitivity, measured where the answer is known: everything under
        `archive/` reached a terminal state as a build plan. If the predicate
        cannot recognise those, it cannot recognise a live one either."""
        archive = artifacts / plan_index.ARCHIVE_DIR_NAME
        assert archive.is_dir(), f"{archive} is missing — no known-plan corpus to measure against"

        plans = [
            path
            for path, _scope in plan_index.iter_scoped_plan_candidates(
                archive, include_archived=False
            )
        ]
        assert len(plans) > 20, (
            f"only {len(plans)} archived plan(s) — too few to be evidence of anything"
        )
        unrecognised = [
            path
            for path in plans
            if not buildplan_refs.has_build_plan_shape(
                path.read_text(encoding="utf-8")
            )
        ]
        assert unrecognised == [], (
            f"{len(unrecognised)} archived build plan(s) carry none of the three "
            f"signals: {[p.name for p in unrecognised]}"
        )
