"""Tests for lib/backlog/migrate.py — the migration guard-sweep (Chunk 05, L1).

Covers the highest-risk operations against the transport-seam fake (offline, no
``gh``, no network):

- **MIG-1** verbatim id/title/body/section fidelity via an ``import``→``export``
  round-trip.
- **MIG-2** multi-prefix absorption — every hand-minted PFX → a permanent
  ``id:PFX`` alias, no new PFX, duplicate-PFX collisions flagged.
- **MIG-3** ``export`` serializes the native graph (deps, sub-issues, timeline,
  assignees), not just the body block.
- **MIG-4** (scaffold) a deleted derived store (the import checkpoint) rebuilds
  from GitHub with no loss/duplication — the W1 cache-rebuild property in miniature.
- **CRASH-4** ``import`` resumes without duplicating after a mid-run failure.
- **CRASH-2** ``merge`` writes the redirect before closing the source.
- **MIG-5** the MG4 scrub keeps the model in the *decision*, not the data plane:
  an owner-confirmed disposition plan (plain data) is applied through
  ``status``/``merge`` — nothing hard-deleted (DM7) — and the import consumes a
  concrete record set (module-level model-freedom is INV-1's job, not re-tested).
- **PROBE-RATE** the write-pacer's decisions (deterministic clock, no real sleep).
- The ``import``/``export``/``merge`` CLI front.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, encode, ids, legacy, migrate  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402
from fixtures.backlog_fixtures import DISCODON_MINI, multi_prefix_backlog  # noqa: E402

OWNER, REPO = "octo", "backlog"
SCOPE = f"{OWNER}/{REPO}"
_DIS_PFXS = ("DIS-0001", "DIS-0002", "DIS-0003", "DIS-0004", "DIS-0005")
_ID_MARKER = re.compile(r"^\s*\[[^\]]+\]\s*")


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


# --- helpers -----------------------------------------------------------------


def _seed_labels(fake, content):
    """Pre-create every label the import needs, so the mutation sequence is exactly
    one create per item (+ the archive closes) — deterministic fault injection."""
    records, _ = migrate._records_from_backlog(content)
    labels: set[str] = set()
    for record in records:
        labels.update(record.labels)
        labels.add(record.key_label())
    fake.seed_labels(OWNER, REPO, sorted(labels))


def _import(fake, content, **kw):
    return migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=content, **kw)


def _export(fake, dest):
    return migrate.export_backlog(fake, owner=OWNER, repo=REPO, dest=dest)


def _read_export(dest: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(Path(dest).glob("item-*.json"))]


def _by_pfx(records: list[dict], pfx: str) -> dict | None:
    for rec in records:
        if pfx in (rec.get("id_aliases") or []):
            return rec
    return None


def _by_id(records: list[dict], canonical: str) -> dict | None:
    for rec in records:
        if rec.get("id") == canonical:
            return rec
    return None


def _file(fake, *, title="t", body="b"):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body=body)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _alias_issues(fake, pfx: str) -> list[dict]:
    return fake.list_issues(OWNER, REPO, state="all", labels=[ids.alias_label(pfx)])


# --- MIG-1: import→export round-trip fidelity --------------------------------


class TestRoundTripFidelity:
    def test_id_title_body_status_metadata_preserved(self, fake, tmp_path):
        src = legacy.parse_backlog(DISCODON_MINI)
        assert _import(fake, DISCODON_MINI)["status"] == "ok"
        assert _export(fake, tmp_path / "export")["status"] == "ok"
        exported = _read_export(tmp_path / "export")

        for item in src.items:
            pfx = item.item_id
            rec = _by_pfx(exported, pfx)
            assert rec is not None, f"{pfx} missing from export"
            # ID: the hand-minted PFX survives as a permanent alias (verbatim).
            assert pfx in (rec["id_aliases"] or [])
            # Title: the [PFX] marker stripped, the rest verbatim.
            assert rec["title"] == _ID_MARKER.sub("", item.title).strip()
            # Body: verbatim, minus the appended prawduct: block.
            assert encode.strip_block(rec["body"]).strip() == item.body.strip()
            # Status (section/metadata → the two axes).
            assert rec["status"] == item.metadata["status"]
            # Metadata: facet → label; non-facet keys preserved verbatim in the block.
            assert f"effort:{item.metadata['effort']}" in rec["labels"]
            assert rec["block"].get("added") == item.metadata["added"]

    def test_related_ref_preserved_in_block(self, fake, tmp_path):
        _import(fake, DISCODON_MINI)
        _export(fake, tmp_path / "export")
        rec = _by_pfx(_read_export(tmp_path / "export"), "DIS-0002")
        assert rec["block"].get("related") == "DIS-0001"

    def test_manifest_lists_every_item(self, fake, tmp_path):
        _import(fake, DISCODON_MINI)
        _export(fake, tmp_path / "export")
        manifest = json.loads((tmp_path / "export" / "export-manifest.json").read_text())
        assert manifest["repo"] == SCOPE
        assert manifest["count"] == len(_DIS_PFXS)
        assert len(manifest["items"]) == len(_DIS_PFXS)


# --- MIG-2: multi-prefix absorption ------------------------------------------


class TestMultiPrefixAbsorption:
    def test_every_prefix_becomes_a_permanent_alias_no_new_pfx(self, fake):
        content = multi_prefix_backlog(single_use=31)
        src = legacy.parse_backlog(content)
        result = _import(fake, content)
        assert result["status"] == "ok", result

        source_pfxs = {item.item_id for item in src.items}
        assert len(source_pfxs) == len(src.items)  # every item has a distinct PFX
        # Every hand-minted PFX resolves to EXACTLY ONE id:PFX-labelled issue (§5).
        for pfx in source_pfxs:
            assert len(_alias_issues(fake, pfx)) == 1, pfx
        # No new PFX minted: every created alias is a source PFX.
        created_pfxs = {c["pfx"] for c in result["data"]["created"]}
        assert created_pfxs == source_pfxs

    def test_duplicate_pfx_is_flagged_not_merged(self, fake):
        content = (
            "## Open\n\n"
            "- **[DUP-0001]** first claimant\n"
            "  `effort: S · impact: S · area: core · status: open`\n\n"
            "- **[DUP-0001]** second claimant (collision)\n"
            "  `effort: M · impact: M · area: core · status: open`\n"
        )
        result = _import(fake, content)
        assert result["status"] == "ok"
        assert len(result["data"]["collisions"]) == 1
        assert result["data"]["collisions"][0]["pfx"] == "DUP-0001"
        # Only the first claimant was imported — the alias resolves to one item.
        assert len(_alias_issues(fake, "DUP-0001")) == 1

    def test_id_less_item_keyed_on_import_marker_not_duplicated(self, fake):
        content = "## Open\n\n- A bare legacy item with no id\n  `area: core · status: open`\n"
        first = _import(fake, content)
        assert first["status"] == "ok"
        assert len(first["data"]["created"]) == 1
        # Re-run: the import-key marker (idempotency-only, never an identity) makes
        # even an id-less item resumable — no duplicate.
        second = _import(fake, content)
        assert second["status"] == "ok"
        assert len(second["data"]["created"]) == 0
        assert len(second["data"]["skipped"]) == 1


class TestArchiveAndCheckpoint:
    def test_separate_archive_file_imports_closed(self, fake):
        main = "## Open\n\n- **[ARC-0001]** open item\n  `area: core · status: open`\n"
        archive = "## Archive\n\n- **[ARC-0002]** shipped item\n  `area: core · status: shipped`\n"
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=main, archive_content=archive
        )
        assert result["status"] == "ok"
        assert len(result["data"]["created"]) == 2  # both files imported
        arc2 = _alias_issues(fake, "ARC-0002")[0]
        assert (arc2.get("state") or "open").lower() == "closed"  # the archive item lands closed

    def test_cross_file_duplicate_pfx_flagged(self, fake):
        # A PFX in BOTH the main file and the archive file is a cross-file collision
        # (the shared seen-set catches it) — not a silent skip at the alias query.
        main = "## Open\n\n- **[DUP-9]** in main\n  `area: core · status: open`\n"
        archive = "## Archive\n\n- **[DUP-9]** in archive\n  `area: core · status: shipped`\n"
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=main, archive_content=archive
        )
        assert result["status"] == "ok"
        assert any(c.get("pfx") == "DUP-9" for c in result["data"]["collisions"])
        assert len(_alias_issues(fake, "DUP-9")) == 1  # only the first (main-file) item

    def test_import_with_archive_cli_flag(self, fake, tmp_path):
        (tmp_path / "main.md").write_text("## Open\n\n- **[CLI-1]** x\n  `area: core · status: open`\n")
        (tmp_path / "arc.md").write_text("## Archive\n\n- **[CLI-2]** y\n  `area: core · status: shipped`\n")
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", str(tmp_path / "main.md"),
             "--archive", str(tmp_path / "arc.md"), "--json"],
            transport=fake,
        )
        assert code == 0
        assert len(_alias_issues(fake, "CLI-2")) == 1

    def test_checkpoint_is_a_progress_record_not_the_skip_authority(self, fake, tmp_path):
        cp = migrate.Checkpoint(tmp_path / "cp.json", SCOPE, "r")
        _import(fake, DISCODON_MINI, checkpoint=cp)
        # is_done is a durable progress read (reporting), populated as items land.
        assert cp.is_done("id:DIS-0001")
        assert not cp.is_done("id:NOPE-0000")

    def test_stale_checkpoint_does_not_skip_a_missing_item(self, fake, tmp_path):
        # A checkpoint that claims an item is done, but the item is NOT on GitHub
        # (deleted / never landed), must NOT skip it — the item would be lost. The
        # live alias query is the sole authority, so the item is (re-)created.
        cp = migrate.Checkpoint(tmp_path / "cp.json", SCOPE, "r")
        cp.mark("id:DIS-0001")  # a lie: nothing was actually created
        result = _import(fake, DISCODON_MINI, checkpoint=cp)
        assert result["status"] == "ok"
        assert len(_alias_issues(fake, "DIS-0001")) == 1  # created despite the stale mark


# --- MIG-3: export serializes the native graph -------------------------------


class TestExportNativeGraph:
    def test_deps_subissues_assignees_timeline_serialized(self, fake, tmp_path):
        a = _file(fake, title="parent A")
        b = _file(fake, title="child B")
        blk = _file(fake, title="blocker")
        assert core.link(fake, id_raw=a, edge="child", target_raw=b)["status"] == "ok"
        assert core.link(fake, id_raw=a, edge="blocked-by", target_raw=blk)["status"] == "ok"
        assert core.claim(fake, id_raw=a)["status"] == "ok"
        assert core.set_status(fake, id_raw=blk, target="shipped")["status"] == "ok"

        assert _export(fake, tmp_path / "g")["status"] == "ok"
        records = _read_export(tmp_path / "g")

        a_rec = _by_id(records, a)
        assert b in a_rec["relationships"]["sub_issues"]
        assert blk in a_rec["relationships"]["blocked_by"]
        assert a_rec["assignees"] == ["agent-a"]  # the claim's API-identity assignee

        blk_rec = _by_id(records, blk)
        assert any(event["event"] == "closed" for event in blk_rec["timeline"])

    def test_export_ignores_non_prawduct_issues(self, fake, tmp_path):
        # A plain repo issue (no prawduct marker) is out of scope (PROV-2).
        fake.seed_labels(OWNER, REPO, ["bug"])
        fake.create_issue(OWNER, REPO, title="a plain issue", body="no block", labels=["bug"])
        _file(fake, title="a real backlog item")
        assert _export(fake, tmp_path / "x")["status"] == "ok"
        assert _export(fake, tmp_path / "x")["data"]["count"] == 1


# --- MIG-4 (scaffold): a deleted derived store rebuilds with no loss ----------


class TestCheckpointLossRebuild:
    def test_deleted_checkpoint_reconverges_via_the_label_truth(self, fake, tmp_path):
        cp_path = tmp_path / "cp.json"
        cp1 = migrate.Checkpoint(cp_path, SCOPE, "run1")
        first = _import(fake, DISCODON_MINI, checkpoint=cp1)
        assert first["status"] == "ok"
        assert len(first["data"]["created"]) == len(_DIS_PFXS)
        assert cp_path.exists()

        # Lose the derived checkpoint (a "cache" wipe) and re-run.
        cp_path.unlink()
        cp2 = migrate.Checkpoint(cp_path, SCOPE, "run1")
        second = _import(fake, DISCODON_MINI, checkpoint=cp2)
        assert second["status"] == "ok"
        # Nothing re-created — the on-GitHub alias label is the durable truth.
        assert len(second["data"]["created"]) == 0
        assert len(second["data"]["skipped"]) == len(_DIS_PFXS)
        for pfx in _DIS_PFXS:
            assert len(_alias_issues(fake, pfx)) == 1  # no data loss, no duplication


# --- CRASH-4: import resumable / idempotent ----------------------------------


class TestImportResumable:
    def test_crash_mid_import_resumes_without_duplicates(self, fake, tmp_path):
        _seed_labels(fake, DISCODON_MINI)  # deterministic: 1 create per item
        fake.fail_at_mutation(4)  # fail the create of the 4th item (DIS-0004)
        cp = migrate.Checkpoint(tmp_path / "cp.json", SCOPE, "r")

        first = _import(fake, DISCODON_MINI, checkpoint=cp)
        assert first["status"] == "error"
        details = first["error"]["details"]
        assert details["resumable"] is True
        assert len(details["created"]) == 3  # DIS-0001..0003 landed before the cut

        second = _import(fake, DISCODON_MINI, checkpoint=cp)
        assert second["status"] == "ok", second
        for pfx in _DIS_PFXS:
            assert len(_alias_issues(fake, pfx)) == 1  # exactly one — no duplicates

        third = _import(fake, DISCODON_MINI, checkpoint=cp)
        assert third["status"] == "ok"
        assert third["data"]["created"] == []  # a completed re-run is a full no-op
        assert len(third["data"]["skipped"]) == len(_DIS_PFXS)

    def test_archive_close_failure_defers_to_warning_and_resume_converges(self, fake, tmp_path):
        # Policy: a *create* failure aborts (content budget — the scarce/risky path);
        # a *status-reconcile* failure is core-budget + transient, so it DEFERS to a
        # warning and the item stays open — the resume's reconcile-status closes it.
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # C1..C4 land, then fail DIS-0004's close (mutation 5 = U4)
        first = _import(fake, DISCODON_MINI)
        assert first["status"] == "ok"  # not aborted — the create succeeded
        assert any("reconcile deferred" in w for w in first["warnings"])
        dis4 = _alias_issues(fake, "DIS-0004")[0]
        assert (dis4.get("state") or "open").lower() == "open"  # created, not yet closed

        second = _import(fake, DISCODON_MINI)
        assert second["status"] == "ok"
        dis4 = _alias_issues(fake, "DIS-0004")[0]
        assert (dis4.get("state") or "open").lower() == "closed"  # resume converged


# --- CRASH-2 / merge ---------------------------------------------------------


class TestMerge:
    def test_merge_redirects_then_closes(self, fake):
        a = _file(fake, title="dup A")
        b = _file(fake, title="keep B")
        result = migrate.merge(fake, source_raw=a, target_raw=b)
        assert result["status"] == "ok", result

        src = core.get_item(fake, id_raw=a)["data"]
        assert src["status"] == "dropped"  # closed, not deleted (body preserved)
        assert src["superseded_by"] == b
        assert core.get_item(fake, id_raw=b)["data"]["status"] == "open"  # target untouched
        assert migrate.resolve(fake, a, owner=OWNER, repo=REPO) == b  # a resolves to b

    def test_crash_before_close_leaves_source_open_but_redirected(self, fake):
        a = _file(fake, title="dup A")
        b = _file(fake, title="keep B")
        fake.fail_at_mutation(2)  # step1 (redirect) lands; fail step2 (the close)
        broken = migrate.merge(fake, source_raw=a, target_raw=b)
        assert broken["status"] == "error"

        src = core.get_item(fake, id_raw=a)["data"]
        assert src["status"] != "dropped"  # still open — never closed-then-orphaned
        assert src["superseded_by"] == b  # redirect written BEFORE the close
        assert migrate.resolve(fake, a, owner=OWNER, repo=REPO) == b  # already resolvable

        fixed = migrate.merge(fake, source_raw=a, target_raw=b)
        assert fixed["status"] == "ok"
        assert core.get_item(fake, id_raw=a)["data"]["status"] == "dropped"
        assert migrate.merge(fake, source_raw=a, target_raw=b)["status"] == "ok"  # 3rd = no-op

    def test_merge_into_self_rejected(self, fake):
        a = _file(fake, title="x")
        assert migrate.merge(fake, source_raw=a, target_raw=a)["error"]["code"] == "validation"

    def test_merge_bad_ids_rejected(self, fake):
        assert migrate.merge(fake, source_raw="not-an-id", target_raw="also/bad")[
            "status"
        ] == "error"


# --- redirect resolution (ids.resolve_redirect, pure) ------------------------


class TestRedirectResolution:
    def test_follows_a_chain(self):
        chain = {"r#1": "r#2", "r#2": "r#3"}
        assert ids.resolve_redirect("r#1", fetch=chain.get) == "r#3"

    def test_cycle_fails_open_at_current_node(self):
        cycle = {"r#1": "r#2", "r#2": "r#1"}
        # Terminates (never loops) — returns a node in the cycle, not a hang.
        assert ids.resolve_redirect("r#1", fetch=cycle.get) in ("r#1", "r#2")

    def test_no_redirect_returns_self(self):
        assert ids.resolve_redirect("r#1", fetch=lambda _c: None) == "r#1"


# --- MIG-5: the scrub keeps the model in the decision, not the data plane -----

# A concrete scrub corpus: a survivor, its duplicate, a stale item, and a live
# item to leave untouched. This mirrors what the model surfaces from `list` —
# but every test supplies the *disposition plan* as plain data (an owner's
# already-confirmed decision), never a model call. The scrub's deterministic
# tail then applies it through the same `status`/`merge`/`import` ops any caller
# uses (API §2.5: the scrub is a workflow over these ops, not a new op).
_SCRUB_BACKLOG = """# Backlog — scrub corpus

## Open

- **[KEEP-0001]** Canonical harbor-map item
  `effort: M · impact: L · area: ui · source: user · added: 2026-05-01 · status: open · stage: ready`

  The surviving item a duplicate folds into.

- **[DUP-0002]** Harbor map (a near-duplicate of KEEP-0001)
  `effort: M · impact: L · area: ui · source: user · added: 2026-05-02 · status: open · stage: ready`

  The owner confirms merging this into KEEP-0001.

- **[STALE-0003]** Abandoned fog-of-war spike
  `effort: S · impact: S · area: ui · source: user · added: 2026-01-01 · status: open · stage: idea`

  Unmoved for months; the owner confirms dropping it.

- **[LIVE-0004]** Rate-limit the trade API
  `effort: S · impact: M · area: backend · source: builder · added: 2026-05-02 · status: open · stage: ready`

  A live item the scrub must leave untouched.
"""


class TestScrubDataPlaneBoundary:
    """MIG-5 — the MG4 scrub is a model-assisted, owner-confirmed *workflow* over
    ``list``/``status``/``merge``/``import`` (API §2.5); the model is in the
    *decision*, never the data plane (G1). These assert the deterministic tail:
    given an owner-confirmed disposition plan expressed purely as **data**,
    disposal goes through ``status``/``merge`` (nothing hard-deleted, DM7) and the
    import op consumes a concrete record set — no model call reaches a mutating op.
    (Module-level model-freedom of the whole package is INV-1's contract.)"""

    def _import_corpus(self, fake):
        result = _import(fake, _SCRUB_BACKLOG)
        assert result["status"] == "ok", result
        # hand-minted PFX -> canonical GitHub id, read from the import result.
        return {c["pfx"]: c["id"] for c in result["data"]["created"]}

    def test_dispositions_are_data_and_nothing_is_hard_deleted(self, fake):
        ids_by_pfx = self._import_corpus(fake)
        assert set(ids_by_pfx) == {"KEEP-0001", "DUP-0002", "STALE-0003", "LIVE-0004"}

        # The owner-confirmed disposition plan — plain data. The model's decision
        # is already made and confirmed; nothing below consults a model.
        plan = {
            "merge": [{"source": "DUP-0002", "into": "KEEP-0001"}],
            "drop": ["STALE-0003"],
        }

        # Apply the plan deterministically through the existing ops.
        for m in plan["merge"]:
            r = migrate.merge(
                fake, source_raw=ids_by_pfx[m["source"]], target_raw=ids_by_pfx[m["into"]]
            )
            assert r["status"] == "ok", r
        for pfx in plan["drop"]:
            r = core.set_status(fake, id_raw=ids_by_pfx[pfx], target="dropped")
            assert r["status"] == "ok", r

        # DM7: nothing hard-deleted — every source item still exists on GitHub.
        assert len(fake.list_issues(OWNER, REPO, state="all")) == 4

        # The duplicate is disposed by redirect-then-close, its body preserved.
        dup = core.get_item(fake, id_raw=ids_by_pfx["DUP-0002"])["data"]
        assert dup["status"] == "dropped"
        assert dup["superseded_by"] == ids_by_pfx["KEEP-0001"]

        # The stale item is disposed by close, not removal.
        assert core.get_item(fake, id_raw=ids_by_pfx["STALE-0003"])["data"]["status"] == "dropped"

        # The survivor and the untouched live item stay open.
        assert core.get_item(fake, id_raw=ids_by_pfx["KEEP-0001"])["data"]["status"] == "open"
        assert core.get_item(fake, id_raw=ids_by_pfx["LIVE-0004"])["data"]["status"] == "open"

    def test_disposal_touches_only_the_named_items(self, fake):
        # Owner-confirmed means the deterministic tail disposes *exactly* what the
        # plan names — it never autonomously closes an item the owner didn't pick.
        ids_by_pfx = self._import_corpus(fake)
        core.set_status(fake, id_raw=ids_by_pfx["STALE-0003"], target="dropped")

        open_now = {i["number"] for i in fake.list_issues(OWNER, REPO, state="open")}
        closed_now = {i["number"] for i in fake.list_issues(OWNER, REPO, state="closed")}
        dropped_num = ids.normalize_id(ids_by_pfx["STALE-0003"]).number
        assert closed_now == {dropped_num}  # only the named item moved
        assert len(open_now) == 3

    def test_import_op_is_typed_to_consume_a_concrete_record_set(self):
        # Structural: the import op takes a concrete `records` list (data), never a
        # callback/model handle — the model can only act *upstream*, by choosing
        # which records to pass. This is the "concrete cleaned set, not a model
        # call" boundary; package-wide model-freedom is INV-1.
        import inspect

        for name in ("import_items", "import_backlog", "merge"):
            params = inspect.signature(getattr(migrate, name)).parameters
            for p in params.values():
                ann = str(p.annotation).lower()
                assert not any(h in ann for h in ("callable", "model", "client")), (
                    f"{name}.{p.name} must not accept a model/callback in the data plane"
                )
        records_ann = str(inspect.signature(migrate.import_items).parameters["records"].annotation)
        assert "ImportRecord" in records_ann  # list[ImportRecord] — data, not a call


# --- PROBE-RATE: the write-pacer's decisions (deterministic) ------------------


class TestPacer:
    def _clock(self):
        state = {"t": 0.0, "slept": []}
        return (
            state,
            lambda: state["t"],
            lambda s: (state["slept"].append(s), state.__setitem__("t", state["t"] + s)),
        )

    def test_under_the_cap_never_waits(self):
        state, now, sleep = self._clock()
        pacer = migrate.Pacer(per_minute=80, per_hour=500, now=now, sleep=sleep)
        for _ in range(10):
            pacer.before_create()
        assert pacer.waits == 0
        assert state["slept"] == []

    def test_minute_cap_paces(self):
        state, now, sleep = self._clock()
        pacer = migrate.Pacer(per_minute=3, per_hour=1000, now=now, sleep=sleep)
        for _ in range(3):
            pacer.before_create()  # all at t=0, fills the minute window
        assert pacer.waits == 0
        pacer.before_create()  # 4th must wait ~60s for a slot to free
        assert pacer.waits == 1
        assert state["slept"] and abs(state["slept"][0] - 60) < 1e-6

    def test_hour_cap_paces(self):
        state, now, sleep = self._clock()
        pacer = migrate.Pacer(per_minute=1000, per_hour=2, now=now, sleep=sleep)
        for _ in range(2):
            pacer.before_create()
        pacer.before_create()  # 3rd hits the hourly cap
        assert pacer.waits == 1
        assert abs(state["slept"][0] - 3600) < 1e-6

    def test_import_paces_one_create_at_a_time(self, fake):
        _seed_labels(fake, DISCODON_MINI)

        class CountingPacer(migrate.Pacer):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def before_create(self):
                self.calls += 1

        pacer = CountingPacer()
        _import(fake, DISCODON_MINI, pacer=pacer)
        assert pacer.calls == len(_DIS_PFXS)  # one paced create per source item


# --- the import / export / merge CLI front -----------------------------------


class TestMigrateCli:
    def test_import_then_export_roundtrip(self, fake, tmp_path, capsys):
        src = tmp_path / "backlog.md"
        src.write_text(DISCODON_MINI)
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", str(src), "--json"],
            transport=fake,
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "ok"
        assert len(payload["data"]["created"]) == len(_DIS_PFXS)

        out_dir = tmp_path / "export"
        code = cli.run(
            str(tmp_path),
            ["export", "--repo", SCOPE, "--to", str(out_dir), "--json"],
            transport=fake,
        )
        assert code == 0
        assert (out_dir / "export-manifest.json").exists()

    def test_import_requires_from(self, fake):
        code = cli.run("/nowhere", ["import", "--repo", SCOPE], transport=fake)
        assert code == 2  # validation

    def test_import_bad_path_is_validation(self, fake, tmp_path):
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", str(tmp_path / "missing.md")],
            transport=fake,
        )
        assert code == 2

    def test_merge_cli(self, fake):
        a = _file(fake, title="dup")
        b = _file(fake, title="keep")
        code = cli.run("/x", ["merge", a, "--into", b, "--json"], transport=fake)
        assert code == 0

    def test_import_and_merge_are_writes_export_is_not(self):
        # SEC-5 classification for the new ops (import/merge mutate; export reads).
        assert cli._is_write("import", []) is True
        assert cli._is_write("merge", []) is True
        assert cli._is_write("export", []) is False

    def test_human_mode_output_does_not_crash(self, fake, tmp_path, capsys):
        # Human mode (no --json) formats each result. The export result carries an
        # `items` key of id STRINGS — regression guard against it being formatted as
        # a `list`-of-item-dicts result (which would AttributeError on `.get`).
        src = tmp_path / "backlog.md"
        src.write_text(DISCODON_MINI)
        assert cli.run(str(tmp_path), ["import", "--repo", SCOPE, "--from", str(src)], transport=fake) == 0
        assert cli.run(str(tmp_path), ["export", "--repo", SCOPE, "--to", str(tmp_path / "e")], transport=fake) == 0
        out = capsys.readouterr().out
        assert "imported 5 created" in out
        assert "exported 5 item(s)" in out

    def test_merge_human_mode_output(self, fake, capsys):
        a = _file(fake, title="dup")
        b = _file(fake, title="keep")
        assert cli.run("/x", ["merge", a, "--into", b], transport=fake) == 0
        assert "superseded-by" in capsys.readouterr().out
