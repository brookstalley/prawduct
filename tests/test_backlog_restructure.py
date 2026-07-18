"""Tests for lib/backlog/restructure.py — the MG6 restructure pre-pass (L1).

The issue-standard §5 owner decision ("restructure, preserve, no split") made
deterministic: plan validation is fail-closed (a typo'd PFX or unknown key must
never silently drop a confirmed rewrite on an irreversible run), application
rebuilds records through the shared ``issuefmt`` composer, the original title/
body are stashed **verbatim-recoverable** in the block (``encode.format_text``
JSON-string encoding — the block is line-based, and an escaped body can never
close the fence), non-atomic items are flagged never split, and the preview the
owner approves is generated from the same ``apply`` result the import consumes.

Integration (fake transport, offline): ``import --restructure`` writes the
restructured title/body/kind with ``original_*`` recoverable from the created
issue, stays idempotent on re-run, and refuses to start on a plan/source
mismatch (fail-before-touching).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, encode, migrate, restructure  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402
from fixtures.backlog_fixtures import DISCODON_MINI  # noqa: E402

OWNER, REPO = "octo", "backlog"
SCOPE = f"{OWNER}/{REPO}"


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _plan(items: dict) -> dict:
    plan, err = restructure.parse_plan(json.dumps({"v": 1, "items": items}))
    assert err is None, err
    return plan


_SECTIONS = {
    "Problem": "The harbor has no map.",
    "Proposed change": "Render a top-down overlay of docks and tide line.",
    "Acceptance": "- [ ] overlay renders",
    "Scope-out": "No minimap.",
}


# --- format_text / parse_text (the block encoding the stash rides on) --------


class TestTextEncoding:
    def test_multiline_round_trips_verbatim(self):
        text = "line one\nline two\n```\nfenced\n```\nafter"
        assert encode.parse_text(encode.format_text(text)) == text

    def test_encoded_value_is_single_line_and_fence_safe(self):
        text = "a body\n```prawduct\nv: 1\n```\ntail"
        raw = encode.format_text(text)
        assert "\n" not in raw
        assert not raw.startswith("```")

    def test_unicode_and_empty_round_trip(self):
        assert encode.parse_text(encode.format_text("naïve — ünïcode")) == "naïve — ünïcode"
        assert encode.parse_text(encode.format_text("")) == ""

    def test_parse_text_tolerates_unencoded_values(self):
        # A hand-edited (pre-encoding) raw value comes back as-is, never an error.
        assert encode.parse_text("plain old text") == "plain old text"
        assert encode.parse_text(None) is None
        assert encode.parse_text("  ") is None


# --- parse_plan (fail-closed validation) -------------------------------------


class TestParsePlan:
    def test_valid_plan_parses(self):
        plan = _plan({"DIS-0001": {"title": "ui: harbor map", "kind": "task"}})
        assert "DIS-0001" in plan["items"]

    def test_flag_only_entry_is_valid(self):
        plan = _plan({"DIS-0001": {"non_atomic": True, "note": "two claims"}})
        assert plan["items"]["DIS-0001"]["non_atomic"] is True

    def test_string_v_is_accepted(self):
        # The block convention serializes v as a string, so "1" is a natural
        # encoding variant, not an ambiguity — tolerated, never rejected.
        plan, err = restructure.parse_plan(
            '{"v": "1", "items": {"DIS-0001": {"kind": "task"}}}'
        )
        assert err is None
        assert "DIS-0001" in plan["items"]

    @pytest.mark.parametrize(
        "text,fragment",
        [
            ("not json", "not valid JSON"),
            ("[]", "must be a JSON object"),
            ('{"v": 2, "items": {"A-1": {}}}', '"v": 1'),
            ('{"v": 1}', "non-empty"),
            ('{"v": 1, "items": {}}', "non-empty"),
            ('{"v": 1, "items": {"A-1": "x"}}', "must be an object"),
            ('{"v": 1, "items": {"A-1": {"titel": "x"}}}', "unknown key"),
            ('{"v": 1, "items": {"A-1": {"title": ""}}}', "single-line"),
            ('{"v": 1, "items": {"A-1": {"title": "a\\nb"}}}', "single-line"),
            ('{"v": 1, "items": {"A-1": {"kind": "epic"}}}', "not one of"),
            ('{"v": 1, "items": {"A-1": {"sections": {}}}}', "non-empty object"),
            ('{"v": 1, "items": {"A-1": {"sections": {"Problem": 3}}}}', "string"),
            ('{"v": 1, "items": {"A-1": {"non_atomic": "yes"}}}', "boolean"),
            ('{"v": 1, "items": {"A-1": {"note": 7}}}', "must be a string"),
        ],
    )
    def test_invalid_plans_fail_closed(self, text, fragment):
        plan, err = restructure.parse_plan(text)
        assert plan is None
        assert fragment in err


# --- apply -------------------------------------------------------------------


class TestApply:
    def _records(self, content: str = DISCODON_MINI):
        records, collisions = migrate.collect_records(content)
        assert not collisions
        return records

    def test_unmatched_pfx_fails_before_anything(self):
        records = self._records()
        result = restructure.apply(records, _plan({"DIS-9999": {"kind": "task"}}))
        assert result["ok"] is False
        assert "DIS-9999" in result["error"]

    def test_title_rewrite_normalizes_and_stashes_original(self):
        records = self._records()
        plan = _plan({"DIS-0001": {"title": "top-down harbor map overlay renders"}})
        result = restructure.apply(records, plan)
        rec = next(r for r in result["records"] if r.pfx == "DIS-0001")
        # normalize_title prepends the record's own `area:` facet (ui).
        assert rec.title == "ui: top-down harbor map overlay renders"
        assert rec.block["original_title"] == "Add the harbor map overlay"

    def test_identical_rewrite_leaves_no_original_residue(self):
        # A source title already in canonical form, re-proposed verbatim: the
        # normalizer is idempotent, nothing changes, nothing is stashed.
        source = (
            "# Backlog\n\n## Open\n\n"
            "- **[DIS-0001]** ui: harbor map overlay renders top-down\n"
            "  `effort: M · impact: L · area: ui · added: 2026-05-01 · status: open`\n\n"
            "  Body text.\n"
        )
        records = self._records(source)
        plan = _plan({"DIS-0001": {"title": "ui: harbor map overlay renders top-down"}})
        result = restructure.apply(records, plan)
        rec = next(r for r in result["records"] if r.pfx == "DIS-0001")
        assert rec.title == "ui: harbor map overlay renders top-down"
        assert "original_title" not in rec.block
        report = result["entries"][0]
        assert report["title_changed"] is False

    def test_sections_compose_through_render_body_and_stash_original(self):
        records = self._records()
        original_body = next(r for r in records if r.pfx == "DIS-0001").body
        plan = _plan({"DIS-0001": {"kind": "task", "sections": _SECTIONS}})
        result = restructure.apply(records, plan)
        rec = next(r for r in result["records"] if r.pfx == "DIS-0001")
        # Template order (task): Problem → Proposed change → Acceptance → Scope-out.
        assert rec.body.index("### Problem") < rec.body.index("### Proposed change")
        assert rec.body.index("### Acceptance") < rec.body.index("### Scope-out")
        assert encode.parse_text(rec.block["original_body"]) == original_body

    def test_kind_backfill_relabel_and_noop(self):
        records = self._records()
        # DIS-0001 has no kind → backfilled without a warning.
        result = restructure.apply(records, _plan({"DIS-0001": {"kind": "feature"}}))
        rec = next(r for r in result["records"] if r.pfx == "DIS-0001")
        assert "kind:feature" in rec.labels
        assert result["warnings"] == []
        # Relabeling a *different* existing kind warns.
        again = restructure.apply(result["records"], _plan({"DIS-0001": {"kind": "bug"}}))
        rec3 = next(r for r in again["records"] if r.pfx == "DIS-0001")
        assert "kind:bug" in rec3.labels and "kind:feature" not in rec3.labels
        assert any("relabeled" in w for w in again["warnings"])
        # Same kind again → no-op, no warning, single label.
        same = restructure.apply(again["records"], _plan({"DIS-0001": {"kind": "bug"}}))
        rec4 = next(r for r in same["records"] if r.pfx == "DIS-0001")
        assert rec4.labels.count("kind:bug") == 1
        assert same["warnings"] == []

    def test_untouched_records_pass_through_unchanged(self):
        records = self._records()
        result = restructure.apply(records, _plan({"DIS-0001": {"kind": "task"}}))
        untouched = [r for r in result["records"] if r.pfx != "DIS-0001"]
        originals = [r for r in records if r.pfx != "DIS-0001"]
        assert all(a is b for a, b in zip(untouched, originals))
        assert len(result["entries"]) == 1

    def test_lint_audit_and_non_atomic_flag_ride_the_report(self):
        records = self._records()
        plan = _plan(
            {"DIS-0001": {"non_atomic": True, "note": "map + tide = two claims"}}
        )
        result = restructure.apply(records, plan)
        report = result["entries"][0]
        assert report["non_atomic"] is True
        assert report["note"] == "map + tide = two claims"
        # The audit runs regardless of rewrites (flag-only entries still lint).
        assert isinstance(report["lint"], list)

    def test_idempotent_key_survives_restructure(self):
        # The PFX (identity/idempotency key) never changes — a restructured
        # record still keys to the same `id:PFX` alias (MG1/MIG-2).
        records = self._records()
        plan = _plan({"DIS-0001": {"title": "ui: renamed", "kind": "task"}})
        result = restructure.apply(records, plan)
        rec = next(r for r in result["records"] if r.pfx == "DIS-0001")
        assert rec.key_label() == "id:DIS-0001"


# --- render_preview ----------------------------------------------------------


class TestRenderPreview:
    def _applied(self):
        records, _ = migrate.collect_records(DISCODON_MINI)
        plan = _plan(
            {
                "DIS-0001": {"title": "ui: harbor map overlay renders top-down",
                             "kind": "feature", "sections": _SECTIONS},
                "DIS-0002": {"non_atomic": True, "note": "rate-limit + retry"},
            }
        )
        return restructure.apply(records, plan)

    def test_preview_is_deterministic(self):
        one = restructure.render_preview(self._applied(), source_label="s.md")
        two = restructure.render_preview(self._applied(), source_label="s.md")
        assert one == two

    def test_preview_carries_before_after_flags_and_lint(self):
        text = restructure.render_preview(self._applied(), source_label="s.md")
        assert "### DIS-0001" in text
        assert "`Add the harbor map overlay`" in text  # title before
        assert "body before" in text and "**body after:**" in text
        assert "Flagged non-atomic" in text and "DIS-0002" in text

    def test_preview_surfaces_collisions_loudly(self):
        applied = self._applied()
        text = restructure.render_preview(
            applied,
            source_label="s.md",
            collisions=[{"pfx": "DIS-0009", "title": "dup", "first": "orig"}],
        )
        assert "collisions" in text and "DIS-0009" in text


# --- integration: import --restructure through the fake transport ------------


class TestImportWithPlan:
    def _import(self, fake, plan):
        return migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI, plan=plan
        )

    def test_created_issue_carries_restructured_content_and_recoverable_original(
        self, fake
    ):
        plan = _plan(
            {"DIS-0001": {"title": "ui: harbor map overlay renders top-down",
                          "kind": "feature", "sections": _SECTIONS}}
        )
        result = self._import(fake, plan)
        assert result["status"] == "ok"
        assert result["data"]["restructured"] == 1
        created = {e["pfx"]: e for e in result["data"]["created"] if e.get("pfx")}
        number = int(created["DIS-0001"]["id"].rsplit("#", 1)[1])
        issue = fake.get_issue(OWNER, REPO, number)
        assert issue["title"] == "ui: harbor map overlay renders top-down"
        assert "### Problem" in issue["body"]
        labels = encode.label_names(issue)
        assert "kind:feature" in labels and "id:DIS-0001" in labels
        block = encode.parse_block(issue["body"])
        original = encode.parse_text(block.get("original_body"))
        records, _ = migrate.collect_records(DISCODON_MINI)
        assert original == next(r for r in records if r.pfx == "DIS-0001").body
        assert block.get("original_title") == "Add the harbor map overlay"

    def test_rerun_with_plan_stays_idempotent(self, fake):
        plan = _plan({"DIS-0001": {"title": "ui: renamed overlay item properly"}})
        first = self._import(fake, plan)
        assert len(first["data"]["created"]) == 5
        second = self._import(fake, plan)
        assert second["data"]["created"] == []
        assert len(second["data"]["skipped"]) == 5

    def test_unmatched_plan_refuses_before_touching_the_repo(self, fake):
        result = self._import(fake, _plan({"DIS-9999": {"kind": "task"}}))
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"
        assert fake.list_issues(OWNER, REPO, state="all") == []

    def test_unplanned_items_import_verbatim(self, fake):
        plan = _plan({"DIS-0001": {"kind": "feature"}})
        result = self._import(fake, plan)
        created = {e["pfx"]: e for e in result["data"]["created"] if e.get("pfx")}
        number = int(created["DIS-0002"]["id"].rsplit("#", 1)[1])
        issue = fake.get_issue(OWNER, REPO, number)
        assert "Bursts of trades exceed the upstream cap." in issue["body"]
        block = encode.parse_block(issue["body"])
        assert block.get("original_body") is None
        assert block.get("original_title") is None

    def test_run_key_varies_with_plan(self):
        base = migrate.run_key(DISCODON_MINI)
        planned = migrate.run_key(DISCODON_MINI, None, '{"v":1}')
        assert base != planned
        assert migrate.run_key(DISCODON_MINI) == base


# --- CLI front ---------------------------------------------------------------


class TestCliFront:
    def _write(self, tmp_path, name, text):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_import_with_bad_plan_is_validation(self, fake, tmp_path, capsys):
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(tmp_path, "plan.json", '{"v": 1, "items": {"A-1": {"x": 1}}}')
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", src, "--restructure", plan, "--json"],
            transport=fake,
        )
        assert code == 2
        payload = json.loads(capsys.readouterr().out)
        assert "unknown key" in payload["error"]["message"]

    def test_import_with_plan_reports_restructured(self, fake, tmp_path, capsys):
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(
            tmp_path, "plan.json",
            json.dumps({"v": 1, "items": {"DIS-0001": {"kind": "feature"}}}),
        )
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", src, "--restructure", plan],
            transport=fake,
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "(1 restructured by plan)" in out

    def test_preview_writes_artifact_offline(self, tmp_path, capsys):
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(
            tmp_path, "plan.json",
            json.dumps({"v": 1, "items": {
                "DIS-0001": {"title": "ui: harbor overlay renders top-down",
                             "kind": "feature", "sections": _SECTIONS},
            }}),
        )
        out_path = tmp_path / "preview.md"
        # transport=None: the preview must never need (or build) a transport.
        code = cli.run(
            str(tmp_path),
            ["restructure-preview", "--from", src, "--plan", plan,
             "--out", str(out_path), "--json"],
            transport=None,
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["data"]["plan_entries"] == 1
        assert payload["data"]["titles_rewritten"] == 1
        assert payload["data"]["total_source"] == 5
        text = out_path.read_text(encoding="utf-8")
        assert "### DIS-0001" in text and "**body after:**" in text

    def test_preview_human_line_not_shadowed_by_import(self, tmp_path, capsys):
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(
            tmp_path, "plan.json",
            json.dumps({"v": 1, "items": {"DIS-0001": {"kind": "task"}}}),
        )
        out_path = tmp_path / "preview.md"
        code = cli.run(
            str(tmp_path),
            ["restructure-preview", "--from", src, "--plan", plan, "--out", str(out_path)],
            transport=None,
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "wrote restructure preview" in out
        assert "imported" not in out  # the import branch must not shadow it

    def test_preview_out_write_failure_is_unavailable(
        self, tmp_path, capsys, monkeypatch
    ):
        # An --out write failure is an environment failure ("unavailable",
        # exit 6), matching export's local-write class — not bad input.
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(
            tmp_path, "plan.json",
            json.dumps({"v": 1, "items": {"DIS-0001": {"kind": "task"}}}),
        )

        def _refuse(self, *args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", _refuse)
        code = cli.run(
            str(tmp_path),
            ["restructure-preview", "--from", src, "--plan", plan,
             "--out", str(tmp_path / "preview.md"), "--json"],
            transport=None,
        )
        assert code == 6
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"]["code"] == "unavailable"

    def test_export_write_failure_is_unavailable(self, fake, tmp_path):
        # The sibling branch in export: an unwritable dest (a file, not a dir)
        # also classifies "unavailable".
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        result = migrate.export_backlog(fake, owner=OWNER, repo=REPO, dest=blocker)
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    @pytest.mark.parametrize("missing", ["from", "plan", "out"])
    def test_preview_missing_required_flag(self, tmp_path, capsys, missing):
        src = self._write(tmp_path, "backlog.md", DISCODON_MINI)
        plan = self._write(tmp_path, "plan.json", '{"v": 1, "items": {"A-1": {}}}')
        flags = {"from": src, "plan": plan, "out": str(tmp_path / "p.md")}
        del flags[missing]
        argv = ["restructure-preview", "--json"]
        for key, value in flags.items():
            argv.extend([f"--{key}", value])
        code = cli.run(str(tmp_path), argv, transport=None)
        assert code == 2
        payload = json.loads(capsys.readouterr().out)
        assert f"--{missing}" in payload["error"]["message"]
