"""Tests for `prawduct-hook review-stats` (review-proportionality ch.03).

The aggregation contract: per role × model × mode (and overall) — review
count, total/median duration, findings by severity, actionable rate,
findings-per-review; a findings-by-file rollup from per-finding ``files``
attribution; per-``scope`` rollups. Skips are COUNTED, never silent: corrupt
lines, event kinds it aggregates neither of (forward-compat with future
producers), and unusable payloads each have their own counter pinned here.
The ``learning.*`` kinds are TALLIED rather than skipped — they were bucketed
under ``unknown_kinds`` while nothing read them, and the block that reads them
is pinned below.

The ``--json`` shape is the stable machine contract TEL-7A4X builds on, so
its keys are pinned exactly — a key change must consciously bump
``REPORT_SCHEMA_VERSION`` (and this test).

No git needed (review-stats only reads the ledger file); sterile env per the
pyc-cache learning, mirroring tests/test_governance_ledger.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"
FINAL_MODE = "final (full review, ready for push)"
CUMULATIVE_MODE = "cumulative (bundle review, ready for merge)"


def _env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLAUDE_PROJECT_DIR": str(repo),
    }


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "review-stats", *args],
        cwd=str(repo), capture_output=True, text=True, env=_env(repo), timeout=30,
    )


def _event(
    *,
    kind: str = "review.critic",
    role: str = "critic",
    model: str | None = "opus",
    mode: str = CHUNK_MODE,
    scope: str | None = "feat-a",
    duration: float | None = 100,
    findings: list[dict] | None = None,
    observations: list[dict] | None = None,
    stage: str | None = None,
    dispatched_at: str | None = None,
    ts: str = "2026-06-10T12:00:00Z",
) -> dict:
    event = {
        "schema_version": 1,
        "event": kind,
        "ts": ts,
        "duration_seconds": duration,
        "project": "proj",
        "scope": scope,
        "chunk": None,
        "actor": {"role": role, "model": model},
        "git": {"head": "a" * 40, "base": "main"},
        "review": {
            "mode": mode,
            "files_reviewed": ["app.py"],
            "findings": findings or [],
            "summary": "Review.",
        },
    }
    # Absent, not empty, by default: every event written before observations
    # were persisted lacks the key, and that must stay distinguishable from a
    # review that demoted nothing.
    if observations is not None:
        event["review"]["observations"] = observations
    # Same posture: absent by default. `stage` was stamped by `critic-begin`
    # from a given release on, and an event without it must group as
    # "unrecorded", never as a stage this reader guessed from the mode.
    if stage is not None:
        event["review"]["stage"] = stage
    # Same posture again, and here it is the whole point: absence means NOT
    # MEASURED. Every one of the 1,008 real events in this repo's ledger lacks
    # the key, so the default is the population the split exists to separate.
    if dispatched_at is not None:
        event["dispatched_at"] = dispatched_at
    return event


def _write_ledger(repo: Path, lines: list) -> None:
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        ln if isinstance(ln, str) else json.dumps(ln) for ln in lines
    )
    (repo / LEDGER_REL).write_text(text + "\n")


class TestMissingAndEmptyLedger:
    def test_missing_ledger_human_is_an_answer_not_an_error(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo)
        assert result.returncode == 0
        assert "no review history" in result.stdout

    def test_missing_ledger_json_emits_stable_zero_report(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "--json")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["events_total"] == 0
        assert report["overall"]["reviews"] == 0
        assert report["by_role_model_mode"] == []
        assert report["top_files"] == []

    def test_unknown_argument_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run(repo, "--jsonn")
        assert result.returncode == 1
        assert "unknown argument" in result.stderr


class TestAggregationMath:
    def _mixed_ledger(self, repo: Path) -> None:
        _write_ledger(repo, [
            _event(mode=CHUNK_MODE, duration=100,
                   findings=[{"goal": "1", "severity": "note", "summary": "n"}]),
            _event(mode=FINAL_MODE, duration=200, findings=[
                {"goal": "1", "severity": "blocking", "summary": "b",
                 "files": ["lib/gates.py"]},
                {"goal": "4", "severity": "warning", "summary": "w",
                 "files": ["lib/gates.py", "docs/x.md"]},
            ]),
            _event(model="fable", mode=CUMULATIVE_MODE, scope="feat-b",
                   duration=300, findings=[
                       {"goal": "7", "severity": "warning", "summary": "w",
                        "files": ["docs/x.md"]}]),
            # A future review.pr producer (ch.05) must aggregate today —
            # the reader reports on review.*, not review.critic alone.
            _event(kind="review.pr", role="pr-reviewer", mode=CUMULATIVE_MODE,
                   scope="feat-b", duration=None,
                   findings=[{"goal": "2", "severity": "weird", "summary": "o"}]),
        ])

    def test_overall_stats(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        result = _run(repo, "--json")
        assert result.returncode == 0
        overall = json.loads(result.stdout)["overall"]
        assert overall["reviews"] == 4
        assert overall["duration_total_seconds"] == 600  # null duration excluded
        assert overall["duration_median_seconds"] == 200  # median of 100/200/300
        assert overall["findings"] == {"blocking": 1, "warning": 2, "note": 1, "other": 1}
        assert overall["findings_per_review"] == 1.25
        assert overall["actionable_rate"] == 0.5  # 2 of 4 had blocking/warning

    def test_role_model_mode_grouping(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        groups = {
            (e["role"], e["model"], e["mode"]): e
            for e in report["by_role_model_mode"]
        }
        assert set(groups) == {
            ("critic", "opus", "chunk"),
            ("critic", "opus", "final"),
            ("critic", "fable", "cumulative"),
            ("pr-reviewer", "opus", "cumulative"),
        }
        final = groups[("critic", "opus", "final")]
        assert final["reviews"] == 1
        assert final["actionable_rate"] == 1.0
        assert final["findings_per_review"] == 2.0
        pr = groups[("pr-reviewer", "opus", "cumulative")]
        assert pr["duration_median_seconds"] is None
        assert pr["duration_total_seconds"] == 0

    def test_scope_rollup(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        scopes = {e["scope"]: e for e in report["by_scope"]}
        assert set(scopes) == {"feat-a", "feat-b"}
        assert scopes["feat-a"]["reviews"] == 2
        assert scopes["feat-b"]["reviews"] == 2

    def test_top_files_ranked_by_actionable(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        report = json.loads(_run(repo, "--json").stdout)
        # Both paths tie at 2 actionable / 2 total; the path tie-break is
        # ascending so the order is deterministic.
        assert report["top_files"] == [
            {"path": "docs/x.md", "actionable_findings": 2, "findings": 2},
            {"path": "lib/gates.py", "actionable_findings": 2, "findings": 2},
        ]
        assert report["files_attributed_total"] == 2

    def test_human_rendering_carries_the_same_numbers(self, tmp_path):
        repo = tmp_path / "repo"
        self._mixed_ledger(repo)
        result = _run(repo)
        assert result.returncode == 0
        assert "4 review event(s)" in result.stdout
        assert "critic / opus / final" in result.stdout
        assert "lib/gates.py: 2 actionable / 2 total" in result.stdout

    def test_pr_evidence_modes_flow_through_verbatim(self, tmp_path):
        # PR evidence `mode` values flow through the existing mode grouping
        # verbatim — no telemetry special-casing. (kernel-v3 chunk 05 note:
        # the record-audit era's pr-scoped/pr-full split is gone; today's
        # protocol emits "pr", and any unfamiliar value still passes through.)
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(kind="review.pr", role="pr", mode="pr", duration=120),
            _event(kind="review.pr", role="pr", mode="pr-custom", duration=600),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        modes = {(e["role"], e["mode"]) for e in report["by_role_model_mode"]}
        assert modes == {("pr", "pr"), ("pr", "pr-custom")}


class TestObservationCounts:
    """A verify pass rates new findings BLOCKING-only and demotes the rest to
    observations, which never reach `findings`. Without their count, a
    narrowing that suppresses real findings is invisible in this report."""

    VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"

    def _obs(self, n: int) -> list[dict]:
        return [
            {"id": f"O-{i}", "name": f"o{i}", "goal": "4", "recommendation": "r"}
            for i in range(1, n + 1)
        ]

    def test_demoted_items_counted_per_mode(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(mode=self.VERIFY_MODE, observations=self._obs(3)),
            _event(mode=self.VERIFY_MODE, observations=self._obs(2)),
            _event(mode=CUMULATIVE_MODE, observations=[]),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["overall"]["observations"] == 5
        assert report["overall"]["reviews_recording_observations"] == 3
        groups = {e["mode"]: e for e in report["by_role_model_mode"]}
        assert groups["verify-resolutions"]["observations"] == 5
        assert groups["cumulative"]["observations"] == 0
        # Observations are not findings: they move no severity count.
        assert report["overall"]["findings"] == {
            "blocking": 0, "warning": 0, "note": 0, "other": 0,
        }

    def test_events_without_the_key_are_not_counted_as_zero(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(mode=self.VERIFY_MODE),  # written before the field existed
            _event(mode=self.VERIFY_MODE, observations=self._obs(1)),
            _event(mode=self.VERIFY_MODE, observations="garbage"),
        ])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["reviews"] == 3
        assert overall["observations"] == 1
        assert overall["reviews_recording_observations"] == 1

    def test_non_object_entries_are_not_counted(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(mode=self.VERIFY_MODE, observations=[*self._obs(1), "x", 7]),
        ])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["observations"] == 1
        assert overall["reviews_recording_observations"] == 1

    def test_human_rendering_distinguishes_unrecorded_from_zero(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(mode=self.VERIFY_MODE, scope="new", observations=self._obs(4)),
            _event(mode=CHUNK_MODE, scope="old"),
        ])
        lines = _run(repo).stdout.splitlines()
        new = next(ln for ln in lines if ln.startswith("  new: "))
        old = next(ln for ln in lines if ln.startswith("  old: "))
        assert "observations 4 in 1 recording review(s)" in new
        assert "observations not recorded" in old


class TestStageRollup:
    """The yield-by-stage query the stage-keyed rigor norm was drawn to answer
    (`nonfunctional-requirements.md` § Direction). `critic-begin` stamps
    `stage` on the manifest, it rides the fact and the findings cache, and the
    `review.critic` event copies the cache — so this report READS it. It never
    derives a stage from the mode: `critic_consolidate.STAGE_OF_MODE` is that
    mapping's one home, and an event written before the field existed says
    nothing about its stage."""

    VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"

    def test_groups_by_recorded_stage_with_the_unrecorded_bucket_last(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(mode=CHUNK_MODE, stage="inner",
                   observations=[{"name": "o", "goal": "2", "recommendation": "r"}]),
            _event(mode=self.VERIFY_MODE, stage="inner"),
            _event(mode=CUMULATIVE_MODE, stage="boundary", findings=[
                {"goal": "2", "severity": "warning", "summary": "w"},
            ]),
            _event(mode=CUMULATIVE_MODE),  # written before the field existed
        ])
        report = json.loads(_run(repo, "--json").stdout)
        assert [e["stage"] for e in report["by_stage"]] == ["inner", "boundary", None]
        by = {e["stage"]: e for e in report["by_stage"]}
        assert by["inner"]["reviews"] == 2 and by["inner"]["observations"] == 1
        assert by["boundary"]["reviews"] == 1 and by["boundary"]["findings"]["warning"] == 1
        assert by[None]["reviews"] == 1

    def test_an_unrecorded_stage_is_never_derived_from_the_mode(self, tmp_path):
        """The falsifying case for a reader that quietly backfilled from the
        mode: a `cumulative` event with no `stage` would then land under
        `boundary`. It must land under the unrecorded bucket."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(mode=CUMULATIVE_MODE), _event(mode=CHUNK_MODE)])
        report = json.loads(_run(repo, "--json").stdout)
        assert [e["stage"] for e in report["by_stage"]] == [None]
        assert report["by_stage"][0]["reviews"] == 2

    def test_an_unknown_stage_value_groups_as_unrecorded(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(stage="middle")])
        report = json.loads(_run(repo, "--json").stdout)
        assert [e["stage"] for e in report["by_stage"]] == [None]

    def test_human_rendering_names_the_stages_and_the_unrecorded_bucket(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(stage="inner"), _event(stage="boundary"), _event()])
        out = _run(repo).stdout
        assert "by stage:" in out
        block = out.split("by stage:", 1)[1].split("\n\n", 1)[0]
        assert "  inner: 1 review(s)" in block
        assert "  boundary: 1 review(s)" in block
        assert "  (unrecorded): 1 review(s)" in block


class TestModelCanonicalization:
    """Model-id aliases for one model fold to a single family bucket so the
    reviewer-model A/B isn't fragmented across id strings; distinct families
    and unfamiliar ids stay separate, a missing model stays None (TEL-4M9X)."""

    def test_opus_aliases_fold_to_one_bucket(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(model="opus", mode=CHUNK_MODE),
            _event(model="claude-opus-4-8", mode=CHUNK_MODE),
            _event(model="claude-opus-4-8[1m]", mode=CHUNK_MODE),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        groups = {(e["role"], e["model"], e["mode"]): e for e in report["by_role_model_mode"]}
        assert set(groups) == {("critic", "opus", "chunk")}
        assert groups[("critic", "opus", "chunk")]["reviews"] == 3

    def test_distinct_families_stay_separate(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(model="claude-opus-4-8[1m]", mode=CHUNK_MODE),
            _event(model="fable", mode=CHUNK_MODE),
            _event(model="claude-sonnet-4-6", mode=CHUNK_MODE),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        models = {e["model"] for e in report["by_role_model_mode"]}
        assert models == {"opus", "fable", "sonnet"}

    def test_unfamiliar_model_passes_through_visibly(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(model="some-future-model", mode=CHUNK_MODE)])
        report = json.loads(_run(repo, "--json").stdout)
        assert {e["model"] for e in report["by_role_model_mode"]} == {"some-future-model"}

    def test_missing_model_groups_as_none(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(model=None, mode=CHUNK_MODE)])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["by_role_model_mode"][0]["model"] is None


class TestSkipCounting:
    def test_corrupt_unknown_and_invalid_each_counted(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            "{not json",                                   # corrupt: unparseable
            json.dumps(["a", "list"]),                     # corrupt: non-object
            json.dumps({"no_event_key": True}),            # corrupt: no event kind
            _event(kind="build.chunk"),                    # unknown kind (future producer)
            {**_event(), "review": {"mode": CHUNK_MODE}},  # invalid payload: no findings list
            _event(duration=50),                           # the one good event
        ])
        result = _run(repo, "--json")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["skipped"] == {
            "corrupt_lines": 3,
            "unknown_kinds": 1,
            "invalid_payloads": 1,
        }
        assert report["events_total"] == 1

    def test_skips_surface_in_human_output(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, ["{not json", _event()])
        result = _run(repo)
        assert result.returncode == 0
        assert "1 corrupt line(s)" in result.stdout


class TestJsonSchemaStability:
    """The --json shape is TEL-7A4X's contract — key changes must bump
    REPORT_SCHEMA_VERSION (and these pins) deliberately, never drift."""

    def test_top_level_keys_pinned(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        report = json.loads(_run(repo, "--json").stdout)
        assert list(report) == [
            "schema_version", "project", "generated_at", "window", "events_total",
            "skipped", "overall", "by_role_model_mode", "by_scope", "by_stage",
            "top_files", "files_attributed_total", "learning",
        ]
        # 1 -> 2 when the `learning` block arrived. A key change, so the
        # version moves with it — that is the whole contract this class exists
        # to hold, and a silent add would break TEL-7A4X's consumers quietly.
        # 2 -> 3 on 2026-09-03: `learning` gained `units_uncited` (a key change).
        # 3 -> 4 on 2026-09-16 (develop sync): every stat block gained
        # `observations` and `reviews_recording_observations` (a key change).
        # 4 -> 5 on 2026-09-17 (review-stages Chunk 02): a `by_stage` grouping
        # joined the top level (a key change).
        # 5 -> 6 on 2026-09-18 (pr-review-payload Chunk 01): every stat block
        # gained `duration_measured` / `duration_self_reported`, because a
        # duration read from a dispatch clock and one recollected by the
        # reviewing model are two populations and a median over the mixture
        # measures neither.
        # 6 -> 7 (review-yield-instrument): a `window` header, stated even
        # when null so a windowed report is never mistaken for a whole-corpus
        # one, and a `remedies` block on every stat block. Both ADDED; no key
        # was removed or repurposed, which is what `api-contract.md`'s
        # additive-first norm permits and what this pin exists to hold you to.
        assert report["schema_version"] == 7
        assert report["project"] == "repo"

    def test_group_entry_keys_pinned(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            {"goal": "1", "severity": "warning", "summary": "w", "files": ["a.py"]},
        ])])
        report = json.loads(_run(repo, "--json").stdout)
        stat_keys = [
            "reviews", "duration_total_seconds", "duration_median_seconds",
            "duration_measured", "duration_self_reported",
            "findings", "remedies", "findings_per_review", "actionable_rate",
            "observations", "reviews_recording_observations",
        ]
        assert list(report["overall"]) == stat_keys
        assert list(report["by_role_model_mode"][0]) == ["role", "model", "mode", *stat_keys]
        assert list(report["by_scope"][0]) == ["scope", *stat_keys]
        assert list(report["by_stage"][0]) == ["stage", *stat_keys]
        assert list(report["top_files"][0]) == ["path", "actionable_findings", "findings"]
        for key in ("duration_measured", "duration_self_reported"):
            assert list(report["overall"][key]) == ["reviews", "total_seconds", "median_seconds"]
        assert list(report["overall"]["remedies"]) == ["blocking", "warning", "note", "other"]
        assert list(report["overall"]["remedies"]["note"]) == [
            "findings", "with_remedy", "blank_remedy", "no_remedy_field", "rate", "median_words",
        ]


def _learning(
    *, kind: str = "learning.written", unit: str | None = "h1",
    file: str = ".claude/rules/learnings/core.md", review_id: str | None = None,
) -> dict:
    payload: dict = {"file": file, "session": "2026-09-02T00:00:00Z",
                     "review_id": review_id}
    if unit is not None:
        payload["unit_hash"] = unit
    return {
        "schema_version": 1, "event": kind, "ts": "2026-09-02T00:00:00Z",
        "duration_seconds": None, "project": "p", "scope": None, "chunk": None,
        "actor": {"role": "builder", "model": None},
        "git": {"head": None, "base": None},
        "learning": payload,
    }


class TestLearningLoopBlock:
    """The reader the two learning events were produced for.

    A channel produced and never consumed is a defect, not an inefficiency —
    these events spent their first release counted as `unknown_kinds`, which is
    indistinguishable from a kind nobody ever wired up.
    """

    def test_counts_events_and_distinct_rules(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _learning(unit="h1"),
            _learning(unit="h1"),                       # same rule, second session
            _learning(unit="h2"),
            _learning(kind="learning.fired", unit="h1", review_id="rev-1"),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["learning"] == {
            "written": 3, "fired": 1, "units_written": 2, "units_fired": 1,
            "units_uncited": 1,
        }
        # Tallied, not skipped — the defect this block closes.
        assert report["skipped"]["unknown_kinds"] == 0
        # ...and NOT folded into the review count, which means reviews.
        assert report["events_total"] == 0

    def test_uncited_is_a_set_difference_not_a_size_difference(self, tmp_path):
        """A rule can FIRE without ever being WRITTEN — every rule authored
        before the emitter shipped does — so the two sets are not nested, and
        on a migrated fleet repo they are disjoint. A size subtraction clamped
        at zero read 0 there forever; the true count is the written set minus
        the fired set. Found live on this repo's own ledger (2 written, 3
        fired, disjoint, printed 0)."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _learning(unit="w1"), _learning(unit="w2"),
            _learning(kind="learning.fired", unit="f1", review_id="rev-1"),
            _learning(kind="learning.fired", unit="f2", review_id="rev-1"),
            _learning(kind="learning.fired", unit="f3", review_id="rev-1"),
        ])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["learning"]["units_written"] == 2
        assert report["learning"]["units_fired"] == 3
        assert report["learning"]["units_uncited"] == 2
        assert "2 written rule(s) no review has cited" in _run(repo).stdout

    def test_zeros_when_the_ledger_holds_none(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["learning"] == {
            "written": 0, "fired": 0, "units_written": 0, "units_fired": 0,
            "units_uncited": 0,
        }

    def test_zeros_when_there_is_no_ledger_at_all(self, tmp_path):
        """The missing-ledger branch builds the block by hand, so it is a
        second place the key set can drift from the reader's."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        report = json.loads(_run(repo, "--json").stdout)
        assert report["learning"] == {
            "written": 0, "fired": 0, "units_written": 0, "units_fired": 0,
            "units_uncited": 0,
        }

    def test_a_corrupt_learning_line_is_still_corrupt(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, ["{not json", _learning()])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["skipped"]["corrupt_lines"] == 1
        assert report["learning"]["written"] == 1

    def test_a_learning_event_with_no_unit_hash_is_an_invalid_payload(self, tmp_path):
        """Never a silent drop: such an event can answer none of the four
        questions, so it is named the way an unusable review payload is."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_learning(unit=None), _learning(unit="   ")])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["skipped"]["invalid_payloads"] == 2
        assert report["learning"]["written"] == 0

    def test_an_unrecognised_learning_kind_stays_an_unknown_kind(self, tmp_path):
        """Exact kinds, not a `learning.` prefix: a future kind with no column
        here must surface rather than be folded into `written`."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_learning(kind="learning.retired")])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["skipped"]["unknown_kinds"] == 1
        assert report["learning"]["written"] == 0

    def test_the_review_block_is_unaffected(self, tmp_path):
        """The control. A reader that swallowed learning events into the review
        path would satisfy every assertion above and break the report."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(duration=50), _learning(), _event(duration=70)])
        report = json.loads(_run(repo, "--json").stdout)
        assert report["events_total"] == 2
        assert report["overall"]["reviews"] == 2
        assert report["overall"]["duration_total_seconds"] == 120
        assert report["learning"]["written"] == 1

    def test_the_human_rendering_names_the_uncited_rules(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _learning(unit="h1"), _learning(unit="h2"), _learning(unit="h3"),
            _learning(kind="learning.fired", unit="h1", review_id="rev-1"),
        ])
        out = _run(repo).stdout
        assert "learning loop:" in out
        # The DIFFERENCE, computed for the reader: 3 written, 1 cited.
        assert "2 written rule(s) no review has cited" in out


class TestDurationProvenanceSplit:
    """A duration read from a dispatch clock and one recollected by the
    reviewing model are two populations. Reporting a median over the mixture
    measures neither, which is the hazard `dispatched_at` was added to retire —
    so the split, not the pooled figure, is what a protocol change is graded on.
    """

    def test_a_measured_and_an_estimated_review_land_in_different_populations(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            # Dispatched 12:00:00, appended 12:00:00 + 240s. The estimate on the
            # SAME event says 100 — deliberately disagreeing, so a reader that
            # silently prefers one cannot pass by coincidence.
            _event(duration=100, dispatched_at="2026-06-10T11:56:00Z"),
            _event(duration=600),
        ])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["duration_measured"] == {
            "reviews": 1, "total_seconds": 240.0, "median_seconds": 240.0,
        }
        assert overall["duration_self_reported"] == {
            "reviews": 1, "total_seconds": 600, "median_seconds": 600,
        }

    def test_an_event_with_no_mark_is_never_counted_as_measured(self, tmp_path):
        """Red if absence is ever read as zero. A zero-second review averaged
        into the measured population is the exact inverse of the signal."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(duration=300), _event(duration=300)])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["duration_measured"]["reviews"] == 0
        assert overall["duration_measured"]["median_seconds"] is None
        assert overall["duration_self_reported"]["reviews"] == 2

    def test_an_out_of_order_pair_is_refused_not_rendered_negative(self, tmp_path):
        """A hand-edited row or a clock skew can stamp the dispatch AFTER the
        write. A negative interval parses cleanly and would be labelled
        measured, which is worse than no measurement: the estimate it displaces
        at least knows it is one."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(duration=300, dispatched_at="2026-06-10T13:00:00Z")])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["duration_measured"]["reviews"] == 0
        assert overall["duration_self_reported"]["reviews"] == 1

    def test_an_unparseable_mark_falls_back_rather_than_ending_the_report(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(duration=300, dispatched_at="not-a-timestamp")])
        overall = json.loads(_run(repo, "--json").stdout)["overall"]
        assert overall["duration_measured"]["reviews"] == 0
        assert overall["duration_self_reported"]["reviews"] == 1

    def test_the_split_reaches_every_grouping_not_just_overall(self, tmp_path):
        """The groupings are what a role-vs-role or before/after comparison is
        actually read from, so a split present only at the top level would leave
        every comparison pooled."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(duration=100, dispatched_at="2026-06-10T11:56:00Z")])
        report = json.loads(_run(repo, "--json").stdout)
        for grouping in ("by_role_model_mode", "by_scope", "by_stage"):
            assert report[grouping][0]["duration_measured"]["reviews"] == 1, grouping
            assert report[grouping][0]["duration_self_reported"]["reviews"] == 0, grouping

    def test_the_human_rendering_states_the_provenance_beside_the_median(self, tmp_path):
        """A median printed without its provenance invites the reader to take an
        estimate for a measurement, which is the whole failure being retired."""
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _event(duration=100, dispatched_at="2026-06-10T11:56:00Z"),
            _event(duration=600),
        ])
        out = _run(repo).stdout
        assert "measured 1 (median 240.0s)" in out
        assert "self-reported 1 (median 600s)" in out


def _finding(severity: str = "note", *, recommendation=..., files=("a.py",)) -> dict:
    """A finding, with the remedy field present / blank / ABSENT on demand.

    The three-way default matters: `recommendation` is omitted entirely unless
    asked for, because the PR reviewer's findings carry no such key and folding
    that into "wrote no remedy" is the defect these tests exist to prevent.
    """
    f = {"goal": "Nothing Is Missing", "severity": severity,
         "summary": "s", "files": list(files)}
    if recommendation is not ...:
        f["recommendation"] = recommendation
    return f


class TestWindowBounds:
    """`--since` / `--until` are inclusive, and a bound shorter than a full
    timestamp names a PERIOD — `2026-09` is the whole of September. Compared as
    bare strings every such bound excludes its own period, silently shortening
    whichever window it closes; the window a before/after comparison closes is
    the one the conclusion is read from. The predicate is SHARED with
    `tools/pr-review-yield.py`, which answers the same question for the PR
    reviewer: `plugin/lib/timewindow.py` is its one home and both import it.
    """

    def _report(self, repo, *args):
        return json.loads(_run(repo, "--json", *args).stdout)

    def test_the_bounds_filter(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-08-01T00:00:00Z"), _event(ts="2026-09-01T00:00:00Z")])
        assert self._report(repo, "--since", "2026-08-15")["events_total"] == 1
        assert self._report(repo, "--until", "2026-08-15")["events_total"] == 1

    def test_a_date_only_until_covers_that_whole_day(self, tmp_path):
        # "2026-09-01T18:00:00Z" > "2026-09-01" as strings, so a naive compare
        # drops events from the bound's own day.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-09-01T18:00:00Z")])
        assert self._report(repo, "--until", "2026-09-01")["events_total"] == 1

    def test_a_month_only_until_covers_that_whole_month(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-09-30T23:59:59Z")])
        assert self._report(repo, "--until", "2026-09")["events_total"] == 1
        assert self._report(repo, "--until", "2026-08")["events_total"] == 0

    def test_a_since_bound_is_inclusive_of_its_own_period(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-08-04T09:00:00Z")])
        assert self._report(repo, "--since", "2026-08-04")["events_total"] == 1

    def test_an_event_with_no_timestamp_is_dropped_once_a_bound_exists(self, tmp_path):
        # Keeping it would claim it for BOTH halves of a before/after split.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="")])
        assert self._report(repo)["events_total"] == 1
        assert self._report(repo, "--since", "2026-08-04")["events_total"] == 0

    def test_the_two_halves_partition_the_corpus(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts=f"2026-08-{d:02d}T00:00:00Z") for d in range(1, 11)])
        pre = self._report(repo, "--until", "2026-08-04")["events_total"]
        post = self._report(repo, "--since", "2026-08-05")["events_total"]
        assert pre + post == self._report(repo)["events_total"] == 10

    def test_the_window_is_stated_even_when_absent(self, tmp_path):
        # A windowed report and a whole-corpus one are the same shape; a
        # consumer that cannot tell them apart will compare one against the other.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        assert self._report(repo)["window"] == {"since": None, "until": None}
        assert self._report(repo, "--since", "2026-01-01")["window"] == {
            "since": "2026-01-01", "until": None}

    def test_a_bad_bound_is_refused_rather_than_filtered_on(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        r = _run(repo, "--since", "nonsense")
        assert r.returncode == 1
        assert "not a date, month or ISO timestamp" in r.stderr

    def test_a_bound_with_no_value_is_refused(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        r = _run(repo, "--until")
        assert r.returncode == 1
        assert "needs a value" in r.stderr


class TestZonedBounds:
    """A full-timestamp bound carrying a zone offset must be INTERPRETED.

    Found by a mutation that survived the whole suite: for period bounds a bare
    string compare agrees with the prefix compare by luck — a period's inclusive
    start is its own string prefix — so no period fixture can discriminate the
    two. Only a zoned instant can, and `2026-08-04T12:00:00+02:00` is 10:00Z.
    """

    def _report(self, repo, *args):
        return json.loads(_run(repo, "--json", *args).stdout)

    def test_a_zoned_since_is_interpreted_not_string_compared(self, tmp_path):
        # 11:00Z is AFTER 10:00Z and must be kept; a bare compare drops it,
        # because "2026-08-04T11" sorts before "2026-08-04T12".
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-08-04T11:00:00Z")])
        assert self._report(repo, "--since", "2026-08-04T12:00:00+02:00")["events_total"] == 1

    def test_a_zoned_since_still_excludes_what_precedes_it(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-08-04T09:59:59Z")])
        assert self._report(repo, "--since", "2026-08-04T12:00:00+02:00")["events_total"] == 0

    def test_a_zoned_until_is_interpreted_not_string_compared(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-08-04T11:00:00Z")])
        assert self._report(repo, "--until", "2026-08-04T12:00:00+02:00")["events_total"] == 0
        assert self._report(repo, "--until", "2026-08-04T14:00:00+02:00")["events_total"] == 1


class TestRemedyDimension:
    """Does a finding SHIP A FIX PLAN? The severity label says what a finding is
    worth; the remedy beside it is what makes it read as work, and the two can
    disagree — a NOTE carrying a finished fix plan is indistinguishable from a
    WARNING at the point the builder decides what to do.
    """

    def _note(self, repo, *args):
        return json.loads(_run(repo, "--json", *args).stdout)["overall"]["remedies"]["note"]

    def test_present_blank_and_absent_are_counted_apart(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            _finding(recommendation="do the thing properly"),
            _finding(recommendation="   "),
            _finding(),
        ])])
        note = self._note(repo)
        assert (note["findings"], note["with_remedy"], note["blank_remedy"],
                note["no_remedy_field"]) == (3, 1, 1, 1)

    def test_the_rate_is_null_when_no_finding_carries_the_field(self, tmp_path):
        # The PR reviewer's real shape: `{goal, severity, file, line, summary}`,
        # no remedy slot. Reporting 0% would be a claim about behaviour the
        # schema makes meaningless.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[_finding(), _finding()])])
        note = self._note(repo)
        assert note["rate"] is None and note["no_remedy_field"] == 2

    def test_the_rate_is_null_when_there_are_no_findings_at_all(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[])])
        assert self._note(repo)["rate"] is None

    def test_the_rate_ignores_findings_whose_schema_lacks_the_field(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            _finding(recommendation="a remedy"), _finding(), _finding()])])
        assert self._note(repo)["rate"] == 1.0

    def test_the_measurement_discriminates(self, tmp_path):
        """The control: two corpora identical but for remedy presence must report
        DIFFERENT rates. A rate assertion that passes on both measured nothing."""
        with_r, without = tmp_path / "with", tmp_path / "without"
        _write_ledger(with_r, [_event(findings=[_finding(recommendation="x y z")] * 4)])
        _write_ledger(without, [_event(findings=[_finding(recommendation="")] * 4)])
        a, b = self._note(with_r)["rate"], self._note(without)["rate"]
        assert (a, b) == (1.0, 0.0) and a != b

    def test_median_words_counts_words_not_characters(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[_finding(recommendation="one two three four five")])])
        assert self._note(repo)["median_words"] == 5

    def test_severities_are_reported_apart(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            _finding("note", recommendation="n"),
            _finding("warning", recommendation="w w"),
            _finding("blocking", recommendation=""),
        ])])
        rem = json.loads(_run(repo, "--json").stdout)["overall"]["remedies"]
        assert rem["note"]["with_remedy"] == 1
        assert rem["warning"]["median_words"] == 2
        assert rem["blocking"]["with_remedy"] == 0


class TestHumanRenderOfWindowAndRemedies:
    """The formatter is exercised by no `--json` test, and both surfaces added
    here render through it."""

    def test_a_windowed_report_says_so(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(ts="2026-09-01T00:00:00Z")])
        out = _run(repo, "--since", "2026-08-04").stdout
        banner = [ln for ln in out.splitlines() if ln.startswith("WINDOW:")]
        assert banner and "SLICE" in banner[0]

    def test_an_unwindowed_report_prints_no_banner(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        assert not [ln for ln in _run(repo).stdout.splitlines() if ln.startswith("WINDOW:")]

    def test_the_remedy_line_reports_the_rate(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            _finding("note", recommendation="one two three"),
            _finding("note", recommendation=""),
        ])])
        line = next(ln for ln in _run(repo).stdout.splitlines() if ln.startswith("remedies:"))
        assert "note 50% of 2" in line

    def test_a_population_with_no_remedy_field_renders_n_a_not_zero_percent(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[_finding("note")])])
        line = next(ln for ln in _run(repo).stdout.splitlines() if ln.startswith("remedies:"))
        assert "n/a" in line and "0%" not in line

    def test_the_remedy_line_survives_a_corpus_with_no_findings(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[])])
        assert "remedies: (no findings)" in _run(repo).stdout


class TestWindowScopesEveryTally:
    """The window scopes the READ, not the result.

    Filtering after `_read_events` re-scopes only the review list, so a windowed
    report prints whole-corpus `learning` and `skipped` counts under a banner
    saying it is a slice — and two windows summed by a `--json` consumer
    double-count them.
    A before/after split, which is this command's whole purpose, showed
    identical learning numbers in both halves.
    """

    def _report(self, repo, *args):
        return json.loads(_run(repo, "--json", *args).stdout)

    def test_learning_counts_partition_across_the_window(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            _learning(unit="old"), _learning(unit="new"), _event(ts="2026-09-01T00:00:00Z"),
        ])
        # Both learning rows carry the helper's own ts; pin that the two halves
        # SUM to the whole rather than each reporting it.
        whole = self._report(repo)["learning"]["written"]
        pre = self._report(repo, "--until", "2026-06-10")["learning"]["written"]
        post = self._report(repo, "--since", "2026-06-11")["learning"]["written"]
        assert whole == 2
        assert pre + post == whole, "a windowed report must not print whole-corpus learning counts"

    def test_skip_counts_partition_across_the_window(self, tmp_path):
        repo = tmp_path / "repo"
        _write_ledger(repo, [
            json.dumps({"event": "deploy.thing", "ts": "2026-06-10T12:00:00Z"}),
            json.dumps({"event": "deploy.thing", "ts": "2026-12-01T00:00:00Z"}),
            _event(),
        ])
        whole = self._report(repo)["skipped"]["unknown_kinds"]
        pre = self._report(repo, "--until", "2026-06-30")["skipped"]["unknown_kinds"]
        post = self._report(repo, "--since", "2026-07-01")["skipped"]["unknown_kinds"]
        assert whole == 2
        assert pre + post == whole, "skips must describe the windowed population too"

    def test_an_out_of_window_corrupt_line_is_not_counted(self, tmp_path):
        # A line with no `ts` cannot be claimed for a window at all.
        repo = tmp_path / "repo"
        _write_ledger(repo, ["{not json", _event(ts="2026-09-01T00:00:00Z")])
        assert self._report(repo)["skipped"]["corrupt_lines"] == 1
        assert self._report(repo, "--since", "2026-01-01")["skipped"]["corrupt_lines"] == 1


class TestBoundValidation:
    def test_an_impossible_date_is_refused_not_silently_shifted(self, tmp_path):
        # `2026-09-31` matches the period shape and is not a date; accepting it
        # silently means 2026-10-01 — a bound meaning something other than what
        # was typed, which is the one failure a window must never have.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        r = _run(repo, "--since", "2026-09-31")
        assert r.returncode == 1
        assert "not a date, month or ISO timestamp" in r.stderr

    def test_a_real_period_bound_is_still_accepted(self, tmp_path):
        # The control: the refusal above must not be refusing every period.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event()])
        assert _run(repo, "--json", "--since", "2026-09-30").returncode == 0
        assert _run(repo, "--json", "--since", "2026-02-29").returncode == 1, "2026 is not a leap year"


class TestRemedyLineCoversTheWholePopulation:
    def test_an_unknown_severity_appears_on_the_remedies_line(self, tmp_path):
        # `_group_stats` and `_fmt_stats` both carry `other`; a remedies line
        # iterating only the three named severities makes the two lines of one
        # report disagree about the population they describe.
        repo = tmp_path / "repo"
        _write_ledger(repo, [_event(findings=[
            {"goal": "g", "severity": "nitpick", "summary": "s",
             "recommendation": "one two", "files": ["a.py"]},
        ])])
        out = _run(repo).stdout
        findings_line = next(ln for ln in out.splitlines() if ln.startswith("overall:"))
        remedies_line = next(ln for ln in out.splitlines() if ln.startswith("remedies:"))
        # The findings line already counts it under `other` — that is the
        # population the remedies line must agree with, and asserting on the
        # whole report would be satisfied by this line alone.
        assert "0/0/0/1" in findings_line
        assert "other" in remedies_line, (
            "the remedies line omits a population the findings line counts, so "
            "the two lines of one report describe different sets")
