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

from lib import plan_archive, plan_backfill, plan_index

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

    def test_unticked_boxes_block_the_AUTOMATIC_sweep(self, tmp_path: Path) -> None:
        """Unticked chunks route to ``blocked``, naming them (#634).

        **This assertion was inverted on 2026-08-11, and the reason it used to
        read the other way still stands — it is now served differently.** The
        original contract was "checkbox state is explicitly NOT a precondition",
        because *"requiring all boxes ticked is what left half-finished dead
        plans in live artifacts forever — they can never satisfy it."* That
        failure mode is real and this change must not reintroduce it.

        What it missed is that the sweep cannot tell those two apart:

        - a **dead** plan with unbuilt chunks — archive it, the boxes are how
          the work ended and that is worth keeping; and
        - **live work whose scope shipped partially** — `scope=tour` released in
          hallucinote v1.8.0 with two of seven chunks unbuilt, while the plan was
          still the tracker for them.

        Selecting by the change log's ``release=`` tag answers "did the scope
        ship", never "did the plan finish", so it archived the second as
        ``lifecycle: completed`` + ``released_in:`` — unbuilt work recorded as
        shipped. That product declined the proposal at two consecutive cuts and
        accepted it at the third, which is the cost of a judgement the tool
        re-asks every release.

        So the sweep surfaces instead of deciding, and nothing is stuck forever:
        an explicit ``archive-plan <path>`` still archives a dead plan in one
        command — deliberately unchanged, because there a human is asserting the
        plan is done. Only the mechanical path is conservative.
        """
        prawduct = _make_repo(tmp_path, plans=())
        (prawduct / "artifacts" / "build-plan-alpha.md").write_text(
            _plan("alpha", ticked=False), encoding="utf-8"
        )
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()
        assert not (prawduct / "artifacts" / "archive" / "build-plan-alpha.md").exists()

        blocked = plan_backfill.survey(prawduct)["blocked"]
        assert len(blocked) == 1
        # The chunk is NAMED — an operator who cannot see which chunk is unbuilt
        # cannot make the call the block exists to hand them.
        assert "Chunk 01: the work" in blocked[0]["reason"]
        assert "1 of 1" in blocked[0]["reason"]

    def test_the_explicit_route_still_archives_an_unfinished_plan(
        self, tmp_path: Path
    ) -> None:
        """The escape hatch the block above depends on being real.

        The original contract's fear — dead plans live forever — is answered
        here rather than by the sweep. `archive-plan` is a human asserting the
        plan is done, and `plan_archive`'s module docstring already says an
        archived plan may carry unticked boxes. If this ever starts refusing,
        the block in the sweep becomes a trap and #634's fix is worse than the
        defect it closed.
        """
        prawduct = _make_repo(tmp_path, plans=())
        plan = prawduct / "artifacts" / "build-plan-alpha.md"
        plan.write_text(_plan("alpha", ticked=False), encoding="utf-8")

        assert (
            plan_archive.refusal_reason(
                plan, prawduct / "artifacts", state=plan_archive.COMPLETED
            )
            is None
        )
        result = plan_archive.archive_plan(
            plan, prawduct / "artifacts", state=plan_archive.COMPLETED, date=DATE
        )
        assert result["status"] == "archived"
        archived = prawduct / "artifacts" / "archive" / "build-plan-alpha.md"
        # Still not corrected on the way in — how the work ended is a fact worth
        # keeping, which was the original test's other half and survives intact.
        assert "- [ ] Chunk 01: the work" in archived.read_text()

    def test_a_plan_with_no_status_roster_is_refused_not_passed(
        self, tmp_path: Path
    ) -> None:
        """Absence of a roster is unreadable, not complete.

        `unticked_chunk_items` returns `[]` for a plan with no Status section,
        identically to a fully-ticked one, so the obvious one-line version of
        this fix has a hole: a plan predating the Status convention sails
        through as finished. Two such plans were live in hallucinote when #634
        was found. Same rule the Critic applies rating `chunk-ref-missing
        unchecked` at BLOCKING — a check that could not run must not read as a
        pass.
        """
        prawduct = _make_repo(tmp_path, plans=())
        rosterless = _plan("alpha").replace("## Status", "## Notes")
        (prawduct / "artifacts" / "build-plan-alpha.md").write_text(
            rosterless, encoding="utf-8"
        )
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        blocked = plan_backfill.survey(prawduct)["blocked"]
        assert len(blocked) == 1
        assert "no readable `## Status` roster" in blocked[0]["reason"]

    def test_running_twice_is_a_no_op_the_second_time(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path)
        plan_backfill.backfill(prawduct, date=DATE, apply=True)
        second = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert second["archived"] == []
        assert second["refused"] == []

    def test_a_name_collision_is_reported_not_fatal(self, tmp_path: Path) -> None:
        """One collision must not abandon a 73-plan sweep with no report.

        **The report now lands in ``blocked``, and it lands on the PREVIEW too.**
        The survey asks ``plan_archive.refusal_reason`` before counting a plan as
        one it would archive, so a collision is caught before the attempt rather
        than at it. That is the point of the change: the previous version
        promised this plan under *would archive N finished plan(s)* and then
        refused it at ``--apply``, so the operator approved a set that was never
        achievable. ``refused`` therefore stays EMPTY here — it now carries only
        a refusal that appears between the survey and the write, not one the
        survey could see.
        """
        prawduct = _make_repo(tmp_path)
        archive = prawduct / "artifacts" / "archive"
        archive.mkdir()
        (archive / "build-plan-alpha.md").write_text("an earlier plan\n", encoding="utf-8")

        preview = plan_backfill.backfill(prawduct, date=DATE, apply=False)
        assert [item["scope"] for item in preview["shipped"]] == []
        assert [item["scope"] for item in preview["blocked"]] == ["alpha"]
        assert "already exists" in preview["blocked"][0]["reason"]

        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)
        assert result["archived"] == []
        assert [item["scope"] for item in result["blocked"]] == ["alpha"]
        assert result["refused"] == []
        # The live plan is still there — reported means nothing happened, not
        # half-happened.
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()
        # And the archived namesake it collided with is untouched.
        assert (archive / "build-plan-alpha.md").read_text() == "an earlier plan\n"

    def test_no_release_tags_moves_nothing_even_on_apply(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path, change_log="# Change Log\n\n## 2026-01-01: a thing\n")
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()


class TestAReusedScopeDoesNotArchiveLiveWork:
    """The sweep's worst reachable outcome, and the two guards against it.

    A work-stream name gets reused — a second round of `auth` — and the older
    round's release tag makes the in-flight plan look finished. Archiving it
    moves a live plan out from under an in-flight chunk, stamps it with a release
    that did not carry it, and dangles `active_build_plan` so every gate reading
    that pointer goes quiet. The release checklist runs this sweep unattended, so
    the reuse only has to happen once.
    """

    REUSED = """\
# Change Log

## 2026-08-01: second round of auth, not released
<!-- prawduct: scope=auth -->

## 2026-01-01: first round of auth
<!-- prawduct: scope=auth | release=v1.0.0 -->
"""

    def test_a_newer_untagged_entry_withholds_the_scope(self) -> None:
        assert "auth" not in plan_backfill.shipped_scopes(self.REUSED)

    def test_same_day_chunk_entries_do_not_withhold_it(self) -> None:
        """The normal pattern must still ship: per-chunk entries are untagged by
        convention and land the same day as the release entry. A rule that
        withheld on *any* untagged entry would stop archiving almost everything.
        """
        same_day = (
            "# Change Log\n\n"
            "## 2026-05-23: v1.5.1 (release)\n<!-- prawduct: scope=v151 | release=v1.5.1 -->\n\n"
            "## 2026-05-23: v1.5.1 Chunk 02\n<!-- prawduct: scope=v151 -->\n\n"
            "## 2026-05-23: v1.5.1 Chunk 01\n<!-- prawduct: scope=v151 -->\n"
        )
        assert plan_backfill.shipped_scopes(same_day)["v151"] == "v1.5.1"

    def test_the_decision_does_not_depend_on_document_order(self) -> None:
        """Half the surveyed fleet has at least one out-of-order pair, so
        first-entry-wins would be wrong on those repos. Same entries, reversed."""
        reversed_log = (
            "# Change Log\n\n"
            "## 2026-01-01: first round of auth\n<!-- prawduct: scope=auth | release=v1.0.0 -->\n\n"
            "## 2026-08-01: second round of auth, not released\n<!-- prawduct: scope=auth -->\n"
        )
        assert "auth" not in plan_backfill.shipped_scopes(reversed_log)

    def test_the_live_plan_survives_the_sweep(self, tmp_path: Path) -> None:
        prawduct = _make_repo(tmp_path, change_log=self.REUSED, plans=("auth",))
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        assert (prawduct / "artifacts" / "build-plan-auth.md").is_file()

    def test_the_active_plan_is_never_swept_even_if_the_log_says_shipped(
        self, tmp_path: Path
    ) -> None:
        """The second guard, tested with the first one defeated.

        Here the change log offers no protection at all — one tagged entry, no
        newer untagged one — so only the pointer stands between an in-flight plan
        and the archive.
        """
        prawduct = _make_repo(tmp_path, plans=("alpha",))
        (prawduct / "project-state.yaml").write_text(
            "project: demo\nactive_build_plan: artifacts/build-plan-alpha.md\n",
            encoding="utf-8",
        )
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert result["archived"] == []
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()

    def test_a_non_active_shipped_plan_still_archives_alongside_it(
        self, tmp_path: Path
    ) -> None:
        """The control: the pointer protects one plan, not the whole sweep."""
        prawduct = _make_repo(tmp_path, plans=("alpha",))
        (prawduct / "artifacts" / "build-plan-other.md").write_text(
            _plan("alpha2"), encoding="utf-8"
        )
        (prawduct / "change-log.md").write_text(
            CHANGE_LOG + "\n## 2026-08-02: alpha2\n<!-- prawduct: scope=alpha2 | release=v1.3.0 -->\n",
            encoding="utf-8",
        )
        (prawduct / "project-state.yaml").write_text(
            "project: demo\nactive_build_plan: artifacts/build-plan-alpha.md\n",
            encoding="utf-8",
        )
        result = plan_backfill.backfill(prawduct, date=DATE, apply=True)

        assert [item["scope"] for item in result["archived"]] == ["alpha2"]
        assert (prawduct / "artifacts" / "build-plan-alpha.md").is_file()


class TestVersioningIsReportedIndependentlyOfTheShippedSet:
    def test_a_repo_with_tags_but_no_qualifying_scope_still_reads_as_versioned(
        self, tmp_path: Path
    ) -> None:
        """Deriving `has_release_tags` from the shipped set made a repo whose
        every scope has newer work report "records no releases" — false, and it
        sends the operator to fix the wrong thing."""
        prawduct = _make_repo(
            tmp_path,
            change_log=TestAReusedScopeDoesNotArchiveLiveWork.REUSED,
            plans=("auth",),
        )
        result = plan_backfill.survey(prawduct)

        assert result["has_release_tags"] is True
        assert result["shipped"] == []
