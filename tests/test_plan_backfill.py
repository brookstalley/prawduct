"""FL6 — backfilling already-shipped build plans into the archive.

The load-bearing claims, each asserted rather than described:

* shipped is decided by the change log's ``release=`` tag and by nothing else,
  so no judgment enters the sweep;
* **checkbox state is neither a precondition nor corrected**, which is what
  makes the operation fully mechanical — it was the only step that could not be
  automated before;
* a product with no release tags gets **nothing moved**, because the mechanical
  test cannot answer there and proposing is the most that may happen.
"""

from __future__ import annotations

from pathlib import Path

from lib import plan_backfill, plan_index

DATE = "2026-08-10"

CHANGE_LOG = """\
# Change Log

## 2026-08-01: shipped alpha
<!-- prawduct: scope=alpha | release=v1.2.0 -->

## 2026-07-01: shipped alpha the first time
<!-- prawduct: scope=alpha | release=v1.1.0 -->

## 2026-06-01: work on beta
<!-- prawduct: scope=beta -->
"""


def _plan(scope: str, *, ticked: bool = True) -> str:
    box = "x" if ticked else " "
    return (
        f"---\nartifact: build-plan\nscope: {scope}\n---\n\n"
        f"## Status\n\n- [{box}] Chunk 01: the work\n\n## Build Chunks\n"
    )


def _make_repo(tmp_path: Path, *, change_log: str = CHANGE_LOG, plans=("alpha", "beta")) -> Path:
    prawduct = tmp_path / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "change-log.md").write_text(change_log, encoding="utf-8")
    for scope in plans:
        (prawduct / "artifacts" / f"build-plan-{scope}.md").write_text(
            _plan(scope), encoding="utf-8"
        )
    return prawduct


class TestShippedSetDerivation:
    def test_a_scope_with_a_release_tag_is_shipped(self) -> None:
        assert plan_backfill.shipped_scopes(CHANGE_LOG)["alpha"] == "v1.2.0"

    def test_a_scope_without_a_release_tag_is_not(self) -> None:
        assert "beta" not in plan_backfill.shipped_scopes(CHANGE_LOG)

    def test_the_latest_release_wins(self) -> None:
        """The change log is newest-first, so the first entry seen for a scope is
        the most recent — and that is the release worth stamping on the plan."""
        assert plan_backfill.shipped_scopes(CHANGE_LOG)["alpha"] == "v1.2.0"


class TestSurvey:
    def test_splits_live_plans_into_shipped_and_kept(self, tmp_path: Path) -> None:
        result = plan_backfill.survey(_make_repo(tmp_path))
        assert [item["scope"] for item in result["shipped"]] == ["alpha"]
        assert [item["scope"] for item in result["unshipped"]] == ["beta"]

    def test_a_product_with_no_release_tags_reports_the_fork(self, tmp_path: Path) -> None:
        """Not "nothing to do" — "nobody but you can decide"."""
        prawduct = _make_repo(tmp_path, change_log="# Change Log\n\n## 2026-01-01: a thing\n")
        result = plan_backfill.survey(prawduct)
        assert result["has_release_tags"] is False
        assert result["shipped"] == []
        assert len(result["unshipped"]) == 2


class TestNestedPlansAreDistinguishable:
    """A real consumer layout every fixture in this file would otherwise miss.

    Repos that organize plans as ``artifacts/plans/<id>/build-plan.md`` have
    several plans sharing that one filename. The backfill's preview is the list a
    single operation-level approval is given for, so a preview that shows four
    identical ``build-plan.md`` lines cannot be consented to — and the flat
    fixtures above can never surface it.
    """

    def test_survey_keeps_nested_plans_separate(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path, plans=())
        for scope in ("alpha", "beta"):
            nested = prawduct / "artifacts" / "plans" / scope.upper()
            nested.mkdir(parents=True)
            (nested / "build-plan.md").write_text(_plan(scope), encoding="utf-8")

        result = plan_backfill.survey(prawduct)
        assert [i["scope"] for i in result["shipped"]] == ["alpha"]
        assert [i["scope"] for i in result["unshipped"]] == ["beta"]

    def test_display_path_distinguishes_them(self, tmp_path: Path) -> None:
        """The helper the preview uses, pinned on the shape that needs it."""
        artifacts = tmp_path / "artifacts"
        labels = {
            plan_index.display_path(artifacts / "plans" / plan_id / "build-plan.md", artifacts)
            for plan_id in ("ALPHA", "BETA")
        }
        assert labels == {"plans/ALPHA/build-plan.md", "plans/BETA/build-plan.md"}
        assert len(labels) == 2, "two different plans must not render as one label"


class TestBackfill:
    def test_preview_moves_nothing(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path)
        result = plan_backfill.backfill(prawduct, date=DATE)
        assert result["status"] == "preview"
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()

    def test_apply_moves_the_shipped_plan_and_stamps_it(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path)
        plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert not (prawduct / "artifacts" / "build-plan-alpha.md").exists()
        archived = prawduct / "artifacts" / "archive" / "build-plan-alpha.md"
        text = archived.read_text()
        assert "lifecycle: completed" in text
        # `released_in`, never `release` — a release plan already uses `release:`
        # for the release it GOVERNS, which is a different fact.
        assert "released_in: v1.2.0" in text

    def test_apply_leaves_the_unshipped_plan_live(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path)
        plan_backfill.backfill(prawduct, date=DATE, apply=True)
        assert (prawduct / "artifacts" / "build-plan-beta.md").is_file()

    def test_unticked_boxes_do_not_block_archiving(self, tmp_path: Path) -> None:
        """Checkbox state is explicitly NOT a precondition.

        Requiring "all boxes ticked" is what left half-finished dead plans in
        live artifacts forever — they can never satisfy it. Removing the
        precondition is what makes this mechanical.
        """
        prawduct = _make_repo(tmp_path, plans=())
        (prawduct / "artifacts" / "build-plan-alpha.md").write_text(
            _plan("alpha", ticked=False), encoding="utf-8"
        )
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert len(result["archived"]) == 1
        archived = prawduct / "artifacts" / "archive" / "build-plan-alpha.md"
        # And it is NOT corrected on the way in: the box is preserved as it was,
        # because how the work ended is a fact worth keeping.
        assert "- [ ] Chunk 01: the work" in archived.read_text()

    def test_running_twice_is_a_no_op_the_second_time(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path)
        plan_backfill.backfill(prawduct, date=DATE, apply=True)
        second = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert second["archived"] == []
        assert second["refused"] == []

    def test_a_name_collision_is_refused_not_fatal(self, tmp_path: Path) -> None:
        """One collision must not abandon a 73-plan sweep with no report."""
        prawduct = _make_repo(tmp_path)
        archive = prawduct / "artifacts" / "archive"
        archive.mkdir()
        (archive / "build-plan-alpha.md").write_text("an earlier plan\n", encoding="utf-8")

        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)
        assert result["archived"] == []
        assert [item["scope"] for item in result["refused"]] == ["alpha"]
        # The live plan is still there — refused means nothing happened, not
        # half-happened.
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()

    def test_no_release_tags_moves_nothing_even_on_apply(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path, change_log="# Change Log\n\n## 2026-01-01: a thing\n")
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()
