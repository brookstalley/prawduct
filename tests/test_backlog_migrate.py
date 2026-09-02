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
- The S2 spike's standalone-script bootstrap — the one path no other test
  reaches, because nothing imports the spike.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, encode, ids, issuefmt, legacy, migrate  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
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


def _file(fake, *, title="merge: the t item under test", body="b"):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body=body)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _alias_issues(fake, pfx: str) -> list[dict]:
    return fake.list_issues(OWNER, REPO, state="all", labels=[ids.alias_label(pfx)])


def _fake_clock():
    """A deterministic (now, sleep) pair: ``now()`` reads a virtual clock that only
    advances when ``sleep(s)`` is called, so pacing decisions are asserted with no
    wall-clock wait. Returns ``(state, now, sleep)`` — ``state['slept']`` records the
    sleeps."""
    state = {"t": 0.0, "slept": []}
    return (
        state,
        lambda: state["t"],
        lambda s: (state["slept"].append(s), state.__setitem__("t", state["t"] + s)),
    )


def _archive_heavy_backlog(n: int) -> str:
    """A backlog whose items all sit in the ``## Archive`` section (``status:
    shipped``), so each import is a **create *and* a close** — the create-then-close
    stretch BKL-6X5D part (b) meters against the 900-pts/min REST burst."""
    lines = ["# Backlog — archive-heavy", "", "## Archive", ""]
    for i in range(1, n + 1):
        lines += [
            f"- **[ARC-{i:04d}]** Archived item {i}",
            "  `effort: S · impact: S · area: core · source: builder · "
            "added: 2026-01-01 · status: shipped`",
            "",
        ]
    return "\n".join(lines)


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
            # Title: the [PFX] marker stripped, then normalized to the §1
            # `area: summary` shape (#728 — prefixing is a property of import,
            # not of having been retitled). Fidelity is preserved, not waived:
            # the pre-migration string is stashed verbatim in the block, so the
            # source title still comes back exactly.
            source_title = _ID_MARKER.sub("", item.title).strip()
            expected = issuefmt.normalize_title(source_title, item.metadata.get("area"))
            assert rec["title"] == expected
            if expected != source_title:
                assert rec["block"].get("original_title") == source_title
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


# --- #729: promoted survives, and the gate no longer grades its own homework -


class TestPromotedSurvivesTheImport:
    """`promoted` is documented markdown vocabulary and a first-class section, but
    it is not an `encode.STATUS_VALUES` member, so it fell through the
    unknown-value path to `open` — losing the in-flight signal on exactly the item
    most likely to carry it."""

    PROMOTED = (
        "# Backlog\n\n## Promoted\n\n"
        "- **[SWD-K3M1]** The active spike\n"
        "  `effort: M · impact: L · area: core · stage: ready · status: promoted`\n"
    )

    def test_promoted_maps_to_in_progress(self):
        records, _ = migrate.collect_records(self.PROMOTED)
        assert [r.status for r in records] == ["in-progress"]

    def test_the_created_issue_carries_the_in_progress_sub_state(self, fake):
        assert _import(fake, self.PROMOTED)["status"] == "ok"
        issue = _alias_issues(fake, "SWD-K3M1")[0]
        assert "status:in-progress" in encode.label_names(issue)

    def test_the_source_spelling_is_still_preserved_in_the_block(self, fake):
        # The alias maps the value; it does not erase what the author wrote.
        _import(fake, self.PROMOTED)
        issue = _alias_issues(fake, "SWD-K3M1")[0]
        assert encode.parse_block(issue["body"]).get("status") == "promoted"

    def test_the_gate_passes_on_a_faithful_promoted_import(self, fake):
        _import(fake, self.PROMOTED)
        verified = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=self.PROMOTED
        )
        assert verified["status"] == "ok", verified


class TestGateExpectationIsIndependent:
    """The gate derived its expectation through `_target_status` — the very
    function that produced the outcome — so it could only confirm that the code
    agreed with itself. These pin the second implementation, and the fact that a
    disagreement between the two is now visible rather than certified."""

    def test_the_expectation_table_covers_the_documented_vocabulary(self):
        """`templates/backlog.md` is what an author writes against; every status
        it documents must be a status the gate can grade."""
        template = (
            Path(__file__).resolve().parent.parent
            / "plugin" / "templates" / "backlog.md"
        ).read_text(encoding="utf-8")
        documented = re.search(r"^\s*status: (.+)$", template, re.M).group(1)
        for value in (v.strip() for v in documented.split("|")):
            assert value in migrate._GATE_EXPECTED_STATUS, (
                f"the template documents `status: {value}` but the completeness "
                "gate has no expectation for it, so an item carrying it cannot be "
                "graded — the divergence #729 was about"
            )

    def test_a_regressed_target_status_is_reported_not_certified(self, fake):
        """The regression itself: with the importer's mapping reverted, the gate
        must still see `open` where `in-progress` was expected."""
        _import(fake, TestPromotedSurvivesTheImport.PROMOTED)
        number = _alias_issues(fake, "SWD-K3M1")[0]["number"]
        # Drive the target back to what the pre-fix import produced.
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{number}", target="open")

        verified = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=TestPromotedSurvivesTheImport.PROMOTED
        )

        assert verified["status"] == "error"
        assert verified["error"]["details"]["status_mismatch"] == [
            "SWD-K3M1 (source: in-progress, target: open)"
        ]

    def test_an_undocumented_status_is_its_own_class_with_its_own_remedy(self, fake):
        """A status in no vocabulary was silently substituted with `open` and the
        gate passed. It is not a `status_mismatch`: re-running the import — that
        list's remedy — substitutes it again."""
        content = (
            "# Backlog\n\n## Open\n\n"
            "- **[SWD-0009]** An item with a typo'd status\n"
            "  `effort: S · impact: M · area: core · status: opne`\n"
        )
        assert _import(fake, content)["status"] == "ok"

        verified = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=content)

        assert verified["status"] == "error"
        details = verified["error"]["details"]
        assert details["unencodable_status"] == ["SWD-0009 (source status: 'opne')"]
        assert details["status_mismatch"] == []
        assert "do not re-run the import" in verified["error"]["message"]

    def test_the_mismatch_remedy_warns_that_a_re_import_overwrites_a_repair(self, fake):
        """The message steered an operator who had repaired the target into
        reverting their own repair."""
        remedy = migrate._incompleteness_remedy([], [], [], ["X (source: a, target: b)"], [])
        assert "overwrites a deliberate correction" in remedy


# --- #727: an invisible backlog is refused, never imported as empty ----------


class TestInvisibleSourceIsRefused:
    """A backlog whose items are indented parses as zero items — and zero items
    imported cleanly, then `verify-migration` compared an empty source set
    against an empty alias set, found them consistent, and recorded a successful
    cutover over a backlog it had silently emptied.

    Both halves are pinned. Fixing only `import` leaves the gate certifying the
    loss for anyone who imported before the fix; fixing only the gate leaves the
    import doing it.
    """

    INDENTED = (
        "# Backlog\n\n## Open\n\n"
        "  - **[SWD-0001]** Weapon feel is wrong\n"
        "    `effort: M · impact: L · area: weapon-feel · status: open`\n\n"
        "  - **[SWD-0002]** Safety net is missing\n"
        "    `effort: S · impact: M · area: safety · status: open`\n"
    )
    FLUSH = (
        "# Backlog\n\n## Open\n\n"
        "- **[SWD-0001]** Weapon feel is wrong\n"
        "  `effort: M · impact: L · area: weapon-feel · status: open`\n"
    )
    EMPTY = "# Backlog\n\n## Open\n\n## Promoted\n\n## Archive\n"

    def test_import_refuses_and_writes_nothing(self, fake):
        result = _import(fake, self.INDENTED)
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"
        assert result["error"]["details"]["items_if_dedented"] == 2
        assert "column 0" in result["error"]["message"]
        assert fake.list_issues(OWNER, REPO, state="all") == []

    def test_verify_migration_refuses_instead_of_certifying_the_loss(self, fake):
        verified = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=self.INDENTED
        )
        assert verified["status"] == "error"
        assert verified["error"]["code"] == "validation"
        assert verified["error"]["details"]["items_if_dedented"] == 2

    def test_a_genuinely_empty_backlog_is_not_accused(self, fake):
        # "Nothing to migrate" must stay a clean pass — the refusal keys on
        # items that WOULD parse, not on the file being large.
        assert _import(fake, self.EMPTY)["status"] == "ok"
        verified = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=self.EMPTY)
        assert verified["status"] == "ok", verified

    def test_the_shipped_template_is_not_accused(self, fake):
        """The scaffolded backlog is exactly the "big file, zero items" shape a
        byte-count heuristic would have failed on."""
        template = (
            Path(__file__).resolve().parent.parent
            / "plugin" / "templates" / "backlog.md"
        ).read_text(encoding="utf-8")
        assert _import(fake, template)["status"] == "ok"

    def test_a_flush_left_backlog_imports(self, fake):
        assert _import(fake, self.FLUSH)["status"] == "ok"

    def test_an_indented_archive_file_is_caught_too(self, fake):
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO,
            content=self.EMPTY, archive_content=self.INDENTED,
        )
        assert result["status"] == "error"
        assert result["error"]["details"]["items_if_dedented"] == 2


class TestTemplateDocumentsTheColumnZeroRule:
    """The template is what an author pattern-matches against; it was the source
    of the trap and is the only place a new repo can learn the rule."""

    def _template(self):
        return (
            Path(__file__).resolve().parent.parent
            / "plugin" / "templates" / "backlog.md"
        ).read_text(encoding="utf-8")

    def test_the_item_example_is_flush_left(self):
        text = self._template()
        assert re.search(r"^- \*\*\[PFX-XXXX\]\*\*", text, re.M), (
            "the template's item-shape example is indented again — an author "
            "copying it authors a backlog that parses as zero items"
        )

    def test_the_column_zero_rule_is_stated(self):
        assert "COLUMN 0" in self._template()


# --- #728: prefixing is a property of import ---------------------------------


class TestImportAppliesTheAreaPrefix:
    """The import path must normalize titles itself, not inherit prefixing as a
    side effect of a restructure plan happening to name the item.

    The trap this closes is a DEFAULT-PATH one: the obvious way to author a
    restructure plan is to retitle the items the linter complained about and
    leave the rest. That produced an issue list where the retitled items carried
    `area:` and the untouched ones did not — in a new repo, the whole backlog —
    and nothing caught it, because no §1 rule requires the prefix, so the import
    succeeded and the preview reported clean.
    """

    def _records(self, content):
        records, _collisions = migrate.collect_records(content)
        return {r.pfx: r for r in records}

    def test_an_untouched_item_still_gains_its_prefix(self):
        content = (
            "## Open\n\n"
            "- **[BKL-0001]** Rate-limit the trade API\n"
            "  `effort: S · impact: M · area: backend · status: open`\n"
        )
        record = self._records(content)["BKL-0001"]
        assert record.title == "backend: Rate-limit the trade API"

    def test_an_already_prefixed_title_is_left_alone(self):
        # Composition with restructure rests on this: normalize_title never
        # double-prefixes, so import and a plan can both run it.
        content = (
            "## Open\n\n"
            "- **[BKL-0002]** backend: Rate-limit the trade API\n"
            "  `effort: S · impact: M · area: backend · status: open`\n"
        )
        record = self._records(content)["BKL-0002"]
        assert record.title == "backend: Rate-limit the trade API"
        assert record.block.get("original_title") is None

    def test_a_slash_bearing_area_prefixes_once(self):
        """#591 is a prerequisite, not a coincidence: with the old charset every
        slash-bearing area double-prefixed, so wiring normalization into import
        would have mis-titled twelve areas' worth of items on every migration."""
        content = (
            "## Open\n\n"
            "- **[BKL-0003]** governance/kernel: a summary\n"
            "  `effort: S · impact: M · area: governance/kernel · status: open`\n"
        )
        assert self._records(content)["BKL-0003"].title == "governance/kernel: a summary"

    def test_an_item_with_no_area_is_untouched(self):
        content = (
            "## Open\n\n"
            "- **[BKL-0004]** Rate-limit the trade API\n"
            "  `effort: S · impact: M · status: open`\n"
        )
        record = self._records(content)["BKL-0004"]
        assert record.title == "Rate-limit the trade API"
        assert record.block.get("original_title") is None


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
            "- **[DUP-0001]** core: the first claimant of this prefix\n"
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

    def test_multi_segment_id_gets_an_alias_and_a_clean_title(self, fake):
        """An id with two or more hyphens is absorbed like any other hand-minted id.

        Both halves matter and they live in different modules: the parser has to
        recognize the id (else no alias keys the item back to the source, and the
        completeness gate blocks the cutover), and the title's marker-strip has to
        recognize the same shape (else the id is aliased but left embedded, and the
        issue reads ``[MIG-M4-REMOVE] Remove the shim``). A widening that lands in
        one and not the other is worse than neither."""
        content = (
            "## Open\n\n"
            "- **[MIG-M4-REMOVE]** Remove the shim\n"
            "  `effort: S · impact: M · area: core · status: open`\n"
        )
        result = _import(fake, content)
        assert result["status"] == "ok", result
        assert [c["pfx"] for c in result["data"]["created"]] == ["MIG-M4-REMOVE"]

        issues = _alias_issues(fake, "MIG-M4-REMOVE")
        assert len(issues) == 1
        # Normalized on import (#728): the marker is stripped and the `area:`
        # prefix applied, so the issue reads `core: Remove the shim` rather
        # than `[MIG-M4-REMOVE] Remove the shim` OR a bare summary.
        assert issues[0]["title"] == "core: Remove the shim"

    def test_multi_segment_id_satisfies_the_completeness_gate(self, fake):
        """The end the widening exists to serve: such an item no longer lands in
        ``unaliasable``, so ``verify-migration`` returns ok instead of exit-4.

        ``unaliasable`` is derived from parsing the source alone — nothing done to
        the target can clear it — so the source-side shape is the whole fix."""
        content = (
            "## Open\n\n"
            "- **[MIG-M4-REMOVE]** Remove the shim\n"
            "  `effort: S · impact: M · area: core · status: open`\n"
        )
        assert _import(fake, content)["status"] == "ok"
        verified = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=content)
        assert verified["status"] == "ok", verified
        assert verified["data"]["unaliasable"] == []
        assert verified["data"]["missing"] == []
        assert verified["data"]["aliased"] == 1

    def test_markerless_item_still_blocks_the_completeness_gate(self, fake):
        """The widening must not cost the gate its teeth: an item with no id at all
        is still unaliasable, still exit-4. This is the residual class step 1b of the
        scrub runbook hunts, and the one its grep cannot find."""
        content = "## Open\n\n- A bare legacy item with no id\n  `area: core · status: open`\n"
        assert _import(fake, content)["status"] == "ok"
        verified = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=content)
        assert verified["status"] == "error", verified
        assert verified["error"]["code"] == "conflict"
        assert verified["error"]["details"]["unaliasable"] == [
            "core: A bare legacy item with no id"
        ]

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
        main = "## Open\n\n- **[ARC-0001]** core: the open item this run must import\n  `area: core · status: open`\n"
        archive = "## Archive\n\n- **[ARC-0002]** core: the shipped item in the archive file\n  `area: core · status: shipped`\n"
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
        main = "## Open\n\n- **[DUP-9]** core: the item living in the main file\n  `area: core · status: open`\n"
        archive = "## Archive\n\n- **[DUP-9]** core: the item living in the archive file\n  `area: core · status: shipped`\n"
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=main, archive_content=archive
        )
        assert result["status"] == "ok"
        assert any(c.get("pfx") == "DUP-9" for c in result["data"]["collisions"])
        assert len(_alias_issues(fake, "DUP-9")) == 1  # only the first (main-file) item

    def test_import_with_archive_cli_flag(self, fake, tmp_path):
        (tmp_path / "main.md").write_text("## Open\n\n- **[CLI-1]** core: the first synthetic cli item\n  `area: core · status: open`\n")
        (tmp_path / "arc.md").write_text("## Archive\n\n- **[CLI-2]** core: the second synthetic cli item\n  `area: core · status: shipped`\n")
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


# --- MG4b: the owner-confirmed --archive-scope lever -------------------------


class TestArchiveScope:
    """MG4b — the owner-confirmed ``--archive-scope {all,open}`` lever. ``open``
    imports only the live/open set as issues; the historical archive stays in the
    git-tracked source markdown rather than minting a closed issue per ancient
    item. ``all`` is the pre-scrub default."""

    _MAIN = "## Open\n\n- **[SCP-0001]** core: the open item this run must import\n  `area: core · status: open`\n"
    _ARCHIVE = (
        "## Archive\n\n"
        "- **[SCP-0002]** core: the shipped item in the archive file\n  `area: core · status: shipped`\n"
        "- **[SCP-0003]** core: the dropped item in the archive file\n  `area: core · status: dropped`\n"
    )

    @staticmethod
    def _assert_preservation_claim_is_true(warnings):
        """The ``open`` warning tells an operator where the skipped items went, and
        that sentence has to be **true**. It once said they remain in "the MG2
        export" — impossible, since ``export_backlog`` dumps the *migrated repo*
        and runs after the import, so it can never hold what the lever excluded.
        An operator who believed it would choose ``open`` expecting a restorable
        archive artifact that does not exist. Guarded here rather than left to
        review because a false safety claim reads as reassuring in every diff.

        This is the *behavioral* half — it asserts the value actually emitted at
        runtime. The source-level companion,
        ``test_backlog_invariants.TestArchiveScopeWarningTruthfulness``, scans every
        such literal in the package and so covers emission sites this test does not
        reach; keep both. As there, the bare ``export`` ban is deliberately blunt and
        bans a word where the defect is a false credit: if some export artifact ever
        genuinely holds the skipped set, retarget this assertion to the new mechanism
        and re-verify it — never delete it to green a red suite."""
        skip_warning = next(w for w in warnings if "archive-scope open" in w)
        assert "export" not in skip_warning.lower(), (
            "the --archive-scope open warning credits the MG2 export with preserving "
            f"skipped items; the export dumps the migrated repo: {skip_warning!r}"
        )
        assert "source markdown" in skip_warning

    def test_apply_open_filters_closed_records(self):
        records, _ = migrate.collect_records(self._MAIN, self._ARCHIVE)
        kept, skipped = migrate.apply_archive_scope(records, "open")
        assert skipped == 2  # the two closed archive items dropped
        assert [r.status for r in kept] == ["open"]

    def test_apply_all_keeps_everything(self):
        records, _ = migrate.collect_records(self._MAIN, self._ARCHIVE)
        kept, skipped = migrate.apply_archive_scope(records, "all")
        assert skipped == 0 and len(kept) == 3

    def test_import_open_scope_skips_archive_items(self, fake):
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="open",
        )
        assert result["status"] == "ok"
        assert len(result["data"]["created"]) == 1  # only the open item
        assert result["data"]["archive_skipped"] == 2
        assert any("archive-scope open" in w for w in result["warnings"])
        self._assert_preservation_claim_is_true(result["warnings"])
        assert _alias_issues(fake, "SCP-0001")  # open item created
        assert _alias_issues(fake, "SCP-0002") == []  # shipped item NOT minted
        assert _alias_issues(fake, "SCP-0003") == []  # dropped item NOT minted

    def test_import_all_scope_mints_closed_archive_issues(self, fake):
        # The default preserves the pre-scrub behavior: archive items DO become
        # closed issues (regression guard on MG4b `all`).
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="all",
        )
        assert result["status"] == "ok"
        assert len(result["data"]["created"]) == 3
        assert "archive_skipped" not in result["data"]
        arc = _alias_issues(fake, "SCP-0002")[0]
        assert (arc.get("state") or "open").lower() == "closed"

    def test_open_then_all_backfills_the_archive_without_duplicating(self, fake):
        """`open` defers the archive, it does not discard it — the migration runbook
        tells owners the choice is not a one-way door, so the reversal is guarded.

        Re-running a repo migrated with `open` under `all` must mint exactly the
        items the first run skipped and leave the already-migrated ones alone: the
        skip authority is the `id:PFX` alias written atomically in the create, so
        the second pass finds-or-creates rather than re-creating."""
        first = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="open",
        )
        assert len(first["data"]["created"]) == 1

        second = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="all",
        )
        assert second["status"] == "ok"
        # The two archive items get minted now; the open item is skipped, not remade.
        assert len(second["data"]["created"]) == 2
        assert len(second["data"]["skipped"]) == 1
        for pfx in ("SCP-0001", "SCP-0002", "SCP-0003"):
            assert len(_alias_issues(fake, pfx)) == 1, f"{pfx} duplicated across runs"
        assert (_alias_issues(fake, "SCP-0002")[0].get("state") or "open").lower() == "closed"

    def test_backfill_re_syncs_status_from_the_markdown(self, fake):
        """The backfill re-run is not a free top-up, and the runbook says so — this
        pins the behavior that claim rests on.

        The skip branch reconciles the status axis (it is what makes a
        created-but-crashed-before-close item converge on resume, CRASH-4). The
        side effect on a *backfill*: an item closed on the service after cutover is
        driven back to its markdown status, i.e. reopened. If someone later scopes
        `_reconcile_status` to fresh creates, this test fails and the runbook
        paragraph must change with it — which is the point of pinning it."""
        migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="open",
        )
        number = _alias_issues(fake, "SCP-0001")[0]["number"]
        # Someone closes the item on the service after cutover.
        core.set_status(fake, id_raw=f"{SCOPE}#{number}", target="shipped")
        assert (fake.get_issue(OWNER, REPO, number).get("state") or "").lower() == "closed"

        migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN,
            archive_content=self._ARCHIVE, archive_scope="all",
        )
        # Reopened — the markdown still says `open`, and the skip path re-syncs it.
        assert (fake.get_issue(OWNER, REPO, number).get("state") or "open").lower() == "open"

    def test_default_scope_is_all(self, fake):
        # No archive_scope passed → `all` (backward-compatible with every existing
        # importer caller, incl. the owner's locked dogfood "import as-is" decision).
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=self._MAIN, archive_content=self._ARCHIVE
        )
        assert len(result["data"]["created"]) == 3

    def test_cli_open_scope(self, fake, tmp_path):
        (tmp_path / "main.md").write_text(self._MAIN)
        (tmp_path / "arc.md").write_text(self._ARCHIVE)
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", str(tmp_path / "main.md"),
             "--archive", str(tmp_path / "arc.md"), "--archive-scope", "open", "--json"],
            transport=fake,
        )
        assert code == 0
        assert _alias_issues(fake, "SCP-0001")
        assert _alias_issues(fake, "SCP-0002") == []

    def test_cli_rejects_bad_scope(self, fake, tmp_path):
        (tmp_path / "main.md").write_text(self._MAIN)
        code = cli.run(
            str(tmp_path),
            ["import", "--repo", SCOPE, "--from", str(tmp_path / "main.md"),
             "--archive-scope", "bogus", "--json"],
            transport=fake,
        )
        assert code == 2  # validation error, before any write


# --- MIG-3: export serializes the native graph -------------------------------


class TestExportNativeGraph:
    def test_deps_subissues_assignees_timeline_serialized(self, fake, tmp_path):
        a = _file(fake, title="merge: the parent A item under test")
        b = _file(fake, title="merge: the child B item under test")
        blk = _file(fake, title="merge: the blocker item under test")
        assert core.link(fake, id_raw=a, edge="child", target_raw=b)["status"] == "ok"
        assert core.link(fake, id_raw=a, edge="blocked-by", target_raw=blk)["status"] == "ok"
        # Assigned directly rather than through prawduct: assignment is a native
        # GitHub field prawduct no longer writes (the claim op that once wrote it
        # is retired), and `export` must still carry it — a full-fidelity dump is
        # about what the provider holds, not about which of it prawduct authored.
        _repo_part, _, _number = a.rpartition("#")
        _owner, _, _name = _repo_part.partition("/")
        fake.update_issue(_owner, _name, int(_number), fields={"assignees": ["agent-a"]})
        assert core.set_status(fake, id_raw=blk, target="shipped")["status"] == "ok"

        assert _export(fake, tmp_path / "g")["status"] == "ok"
        records = _read_export(tmp_path / "g")

        a_rec = _by_id(records, a)
        assert b in a_rec["relationships"]["sub_issues"]
        assert blk in a_rec["relationships"]["blocked_by"]
        assert a_rec["assignees"] == ["agent-a"]  # the provider's own assignment, carried verbatim

        blk_rec = _by_id(records, blk)
        assert any(event["event"] == "closed" for event in blk_rec["timeline"])

    def test_export_ignores_non_prawduct_issues(self, fake, tmp_path):
        # A plain repo issue (no prawduct marker) is out of scope (PROV-2).
        fake.seed_labels(OWNER, REPO, ["bug"])
        fake.create_issue(OWNER, REPO, title="merge: the a plain issue item under test", body="no block", labels=["bug"])
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

# Minimal open-only fixtures for the resumable-envelope warnings regression: a
# subset (DIS-0001) and its superset (DIS-0001 + DIS-0002). A re-import of the
# superset self-heals the first (a mutation) and then creates the second (the
# mutation that fails), so a completed record's warning precedes the cut.
_ONE_OPEN_ITEM = """# Backlog — mini

## Open

- **[DIS-0001]** Add the harbor map overlay
  `effort: M · impact: L · area: ui · source: user · added: 2026-05-01 · status: open · stage: ready`

  Players want a top-down harbor map.
"""

_TWO_OPEN_ITEMS = _ONE_OPEN_ITEM + """
- **[DIS-0002]** Rate-limit the trade API
  `effort: S · impact: M · area: backend · source: builder · added: 2026-05-02 · status: open · stage: ready`

  Bursts of trades exceed the upstream cap.
"""


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

    def test_a_deferred_close_is_counted_not_only_warned_about(self, fake):
        """BKL-7V2D leg 1b. The deferral policy above is right; reporting it *only*
        as prose in `warnings` is what made a partial migration look complete. In a
        ~900-item run those lines scroll past, and the import then returns a plain
        `ok` whose `data` cannot distinguish "imported" from "imported AND at its
        target status" — which is the state `verify-migration` also could not see."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # C1..C4 land, then fail DIS-0004's close
        result = _import(fake, DISCODON_MINI)

        assert result["status"] == "ok"
        deferred = result["data"]["status_unreconciled"]
        assert len(deferred) == 1
        assert deferred[0]["pfx"] == "DIS-0004"
        assert deferred[0]["target"] == "shipped"  # the archive close that didn't land
        assert deferred[0]["code"] == "unavailable"
        assert deferred[0]["id"].endswith(f"#{_alias_issues(fake, 'DIS-0004')[0]['number']}")
        # The count rides the summary too — the per-item audit line is not the only
        # place an operator can learn the run left work undone.
        assert any("imported but NOT reconciled" in w for w in result["warnings"])

    def test_a_converged_resume_reports_nothing_unreconciled(self, fake):
        """The field has to clear, or it is a permanent smear rather than a signal:
        the resume closes DIS-0004, so the second run's list is empty."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)
        first = _import(fake, DISCODON_MINI)
        assert len(first["data"]["status_unreconciled"]) == 1

        second = _import(fake, DISCODON_MINI)
        assert second["status"] == "ok"
        assert second["data"]["status_unreconciled"] == []
        assert not any("imported but NOT reconciled" in w for w in second["warnings"])

    def test_a_deferral_accrued_before_a_cut_rides_the_resumable_envelope(
        self, fake, monkeypatch
    ):
        """Same argument as the self-heal warnings below: a deferral recorded before
        an abort is not reconstructible from the envelope's other fields — the item
        IS in `created`, which is precisely what makes it look finished — so dropping
        it here loses the only record that it sits at the wrong status."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # DIS-0004's close defers (mutation 5 = U4)

        real_create = fake.create_issue
        creates = {"n": 0}

        def _cut_on_the_next_create(*args, **kwargs):
            creates["n"] += 1
            if creates["n"] == 5:  # DIS-0005 — strictly after DIS-0004's deferral
                raise TransportError("unavailable", "cut after the deferral")
            return real_create(*args, **kwargs)

        monkeypatch.setattr(fake, "create_issue", _cut_on_the_next_create)
        result = _import(fake, DISCODON_MINI)

        assert result["status"] == "error"
        details = result["error"]["details"]
        assert details["resumable"] is True
        assert [d["pfx"] for d in details["status_unreconciled"]] == ["DIS-0004"]
        # The trap this pins: DIS-0004 is in `created`, so the envelope alone reads
        # as "four landed, one to go" unless the deferral rides along with it.
        assert any(e["pfx"] == "DIS-0004" for e in details["created"])

    def test_a_self_heal_line_survives_a_rate_limited_close_replay(self, fake):
        """Critic R-2. `_import_one_with_retry` discards a retried attempt's local
        warnings so nothing doubles (BKL-3K9N). Putting the close on the retry
        contract made that discard reachable *after* a self-heal has already landed:
        the label restore is a persisted write, the replay then finds the label on
        the fast path so `healed` is False, and the line would never be re-emitted —
        by this run or any later resume. That is the permanent loss BKL-9V2W's
        envelope fix exists to prevent, arriving through a new door."""
        _seed_labels(fake, _TWO_OPEN_ITEMS)
        _import(fake, _ONE_OPEN_ITEM)  # DIS-0001 lands
        number = _alias_issues(fake, "DIS-0001")[0]["number"]
        fake.remove_label(OWNER, REPO, number, ids.alias_label("DIS-0001"))
        # Give DIS-0001 a status the re-import must reconcile, so its record reaches
        # the close at all — the heal alone would not.
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{number}", target="shipped")

        # The heal lands (mutation 1: label restore), then the reconcile back to
        # `open` 429s once — replaying the whole record and discarding its local list.
        fake.fail_at_mutation(2, code="rate_limited")
        backoff = migrate.RateLimitBackoff(sleep=lambda _s: None, base_seconds=0.0)
        result = _import(fake, _TWO_OPEN_ITEMS, backoff=backoff)

        assert result["status"] == "ok", result
        assert backoff.pauses == 1  # the close genuinely replayed
        assert any("restored missing alias label" in w for w in result["warnings"])

    def test_the_other_resumable_cut_also_carries_the_deferrals(self, fake, monkeypatch):
        """Critic R-3. `import_items` has two cut paths and the sibling
        `except (OSError, json.JSONDecodeError)` branch has drifted from the
        `TransportError` one before — that drift is why it carries `resumable` and
        the accrued warnings at all. Pinning only one of the two is what let it
        happen, so `status_unreconciled` is asserted on both."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # DIS-0004's close defers

        real_create = fake.create_issue
        creates = {"n": 0}

        def _socket_dies_after_the_deferral(*args, **kwargs):
            creates["n"] += 1
            if creates["n"] == 5:
                raise OSError("connection reset mid-import")
            return real_create(*args, **kwargs)

        monkeypatch.setattr(fake, "create_issue", _socket_dies_after_the_deferral)
        result = _import(fake, DISCODON_MINI)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        details = result["error"]["details"]
        assert details["resumable"] is True
        assert [d["pfx"] for d in details["status_unreconciled"]] == ["DIS-0004"]

    def test_resumable_error_carries_accrued_self_heal_warnings(self, fake):
        # Regression (BKL-9V2W): an alias self-heal audit line emitted by an
        # already-completed record must ride the resumable TransportError envelope.
        # It cannot be recovered on resume — the restored id:PFX label makes the
        # record skip the fast label path, so the heal never re-runs — so dropping
        # it from the error envelope loses the audit line permanently.
        _seed_labels(fake, _TWO_OPEN_ITEMS)
        _import(fake, _ONE_OPEN_ITEM)  # DIS-0001 lands on GitHub
        number = _alias_issues(fake, "DIS-0001")[0]["number"]

        # A human deletes DIS-0001's id:PFX label; the block id_aliases survives.
        fake.remove_label(OWNER, REPO, number, ids.alias_label("DIS-0001"))

        # Re-import the superset: DIS-0001 self-heals (mutation 1 — restores the
        # label, emitting the audit line), then DIS-0002's create (mutation 2) hits
        # the injected failure and returns the resumable envelope.
        fake.fail_at_mutation(2)
        result = _import(fake, _TWO_OPEN_ITEMS)

        assert result["status"] == "error"
        assert result["error"]["details"]["resumable"] is True
        assert result["error"]["details"]["skipped"]  # DIS-0001 healed before the cut
        assert any("restored missing alias label" in w for w in result["warnings"])

    def test_unexpected_boundary_failure_carries_the_same_resumable_envelope(
        self, fake, monkeypatch
    ):
        # Regression: the `except (OSError, json.JSONDecodeError)` sibling of the
        # TransportError cut returned a bare error, dropping created/skipped/
        # resumable AND the accrued warnings — contradicting import_items' own
        # docstring one screen above it. An unexpected boundary failure is no less
        # resumable, and a self-heal audit line no less unrecoverable, than a
        # transport one; same setup as the test above, different exception class.
        _seed_labels(fake, _TWO_OPEN_ITEMS)
        _import(fake, _ONE_OPEN_ITEM)  # DIS-0001 lands on GitHub
        number = _alias_issues(fake, "DIS-0001")[0]["number"]
        fake.remove_label(OWNER, REPO, number, ids.alias_label("DIS-0001"))

        def _socket_dies(*args, **kwargs):
            raise OSError("connection reset mid-import")

        # DIS-0001 self-heals first (a label restore, emitting the audit line),
        # then DIS-0002's create hits the unexpected boundary failure.
        monkeypatch.setattr(fake, "create_issue", _socket_dies)
        result = _import(fake, _TWO_OPEN_ITEMS)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        details = result["error"]["details"]
        assert details["resumable"] is True
        assert details["skipped"]  # DIS-0001 healed before the cut
        assert any("restored missing alias label" in w for w in result["warnings"])


# --- BKL-4W7H: id:PFX alias self-heal (deleted label ↛ permanent duplicate) ---


class TestAliasSelfHeal:
    """A human-deleted ``id:PFX`` label must not turn a re-import into a permanent
    duplicate (GitHub never reuses issue numbers). The block ``id_aliases`` record
    is the fallback skip-authority, and the re-import self-heals the missing label
    so the alias resolves again on the fast label path."""

    def test_deleted_alias_label_reimport_neither_duplicates_nor_leaves_it_missing(self, fake):
        _import(fake, DISCODON_MINI)
        pfx = "DIS-0001"
        number = _alias_issues(fake, pfx)[0]["number"]
        total_before = len(fake.list_issues(OWNER, REPO, state="all"))

        # A human deletes the id:PFX label; the block id_aliases record survives.
        fake.remove_label(OWNER, REPO, number, ids.alias_label(pfx))
        assert _alias_issues(fake, pfx) == []  # the label search now misses

        # Re-import the SAME content: the block fallback finds the existing issue.
        result = _import(fake, DISCODON_MINI)
        assert result["status"] == "ok", result

        healed = _alias_issues(fake, pfx)
        assert [i["number"] for i in healed] == [number]  # same issue — no duplicate
        assert len(fake.list_issues(OWNER, REPO, state="all")) == total_before
        assert any("restored missing alias label" in w for w in result["warnings"])

    def test_clean_reimport_never_scans_blocks(self, fake):
        # Every id:PFX label intact ⇒ the label fast-path finds everything and the
        # alias index is never built (no full-issue scan on the common resume path).
        _import(fake, DISCODON_MINI)
        fake.calls.clear()
        result = _import(fake, DISCODON_MINI)
        assert result["status"] == "ok"
        # The block scan pages issues with NO label filter; the label fast-path
        # always passes labels=[...]. An unfiltered list_issues ⇒ the scan ran.
        unfiltered = [c for c in fake.calls if c[0] == "list_issues" and not c[4]]
        assert unfiltered == []


# --- CRASH-2 / merge ---------------------------------------------------------


class TestMerge:
    def test_merge_redirects_then_closes(self, fake):
        a = _file(fake, title="merge: the dup A item under test")
        b = _file(fake, title="merge: the keep B item under test")
        result = migrate.merge(fake, source_raw=a, target_raw=b)
        assert result["status"] == "ok", result

        src = core.get_item(fake, id_raw=a)["data"]
        assert src["status"] == "dropped"  # closed, not deleted (body preserved)
        assert src["superseded_by"] == b
        assert core.get_item(fake, id_raw=b)["data"]["status"] == "open"  # target untouched
        assert migrate.resolve(fake, a, owner=OWNER, repo=REPO) == b  # a resolves to b

    def test_crash_before_close_leaves_source_open_but_redirected(self, fake):
        a = _file(fake, title="merge: the dup A item under test")
        b = _file(fake, title="merge: the keep B item under test")
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
        a = _file(fake, title="merge: the x item under test")
        assert migrate.merge(fake, source_raw=a, target_raw=a)["error"]["code"] == "validation"

    def test_merge_bad_ids_rejected(self, fake):
        assert migrate.merge(fake, source_raw="not-an-id", target_raw="also/bad")[
            "status"
        ] == "error"

    def _file_with_alias(self, fake, pfx, *, title="merge: the t item under test"):
        cid = _file(fake, title=title)
        number = int(cid.split("#")[1])
        fake.seed_labels(OWNER, REPO, [ids.alias_label(pfx)])
        fake.add_labels(OWNER, REPO, number, [ids.alias_label(pfx)])
        return number

    def test_merge_resolves_bare_pfx_endpoints(self, fake):
        # BKL-7Q2N — both merge endpoints may be hand-minted PFX aliases (the scrub
        # disposes duplicates by their original ids). Resolve each via id:PFX + --repo.
        na = self._file_with_alias(fake, "SRC-0001", title="merge: the dup A item under test")
        nb = self._file_with_alias(fake, "DST-0001", title="merge: the keep B item under test")
        result = migrate.merge(
            fake, source_raw="SRC-0001", target_raw="DST-0001", default_repo=(OWNER, REPO)
        )
        assert result["status"] == "ok", result
        src = core.get_item(fake, id_raw="SRC-0001", default_repo=(OWNER, REPO))["data"]
        assert src["status"] == "dropped"
        assert src["superseded_by"] == f"{OWNER}/{REPO}#{nb}"
        assert na != nb

    def test_merge_bare_pfx_without_a_repo_is_a_validation_error(self, fake):
        self._file_with_alias(fake, "SRC-0001")
        self._file_with_alias(fake, "DST-0001")
        result = migrate.merge(fake, source_raw="SRC-0001", target_raw="DST-0001")  # no --repo
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"
        assert "--repo" in result["error"]["message"]


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
        return _fake_clock()

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

    # --- REST-points budget (900/min) — BKL-6X5D part (b) --------------------

    def test_points_under_the_cap_never_waits(self):
        state, now, sleep = self._clock()
        pacer = migrate.Pacer(per_minute_points=900, now=now, sleep=sleep)
        for _ in range(100):  # 100 reads = 100 pts, well under 900
            pacer.before_points(migrate._REST_READ_POINTS)
        assert pacer.point_waits == 0
        assert state["slept"] == []
        assert pacer.points_charged == 100

    def test_points_cap_paces_writes(self):
        state, now, sleep = self._clock()
        # Ceiling 10 pts/min → two 5-pt writes fill the window; the third must wait.
        pacer = migrate.Pacer(per_minute_points=10, now=now, sleep=sleep)
        pacer.before_points(migrate._REST_WRITE_POINTS)  # t=0
        pacer.before_points(migrate._REST_WRITE_POINTS)  # t=0 — window now 10/10
        assert pacer.point_waits == 0
        pacer.before_points(migrate._REST_WRITE_POINTS)  # waits ~60s for a slot
        assert pacer.point_waits == 1
        assert state["slept"] and abs(state["slept"][0] - 60) < 1e-6
        assert pacer.points_charged == 15

    def test_points_cap_counts_reads_and_writes_together(self):
        state, now, sleep = self._clock()
        # Ceiling 6 → a write (5) + a read (1) fills it; the next read must wait.
        # This is the create-then-close insight: it is the SUM of read+write points,
        # not creates alone, that binds (BKL-6X5D part b).
        pacer = migrate.Pacer(per_minute_points=6, now=now, sleep=sleep)
        pacer.before_points(migrate._REST_WRITE_POINTS)  # 5
        pacer.before_points(migrate._REST_READ_POINTS)   # +1 = 6/6
        assert pacer.point_waits == 0
        pacer.before_points(migrate._REST_READ_POINTS)   # 7th point — must wait
        assert pacer.point_waits == 1
        assert abs(state["slept"][0] - 60) < 1e-6


class TestPacingTransport:
    """Every transport METHOD call is metered against the 900-pts/min budget by
    name-classification, and an unclassified call fails loud rather than silently
    escaping the budget (BKL-6X5D part b — the anti-fragility of the seam).

    Per method, not per HTTP request: a paged read is charged once, so the metered
    total is a floor (BKL-3H7W). These tests pin the classification and the
    fail-loud seam, not an exact request count."""

    def test_write_charges_five_read_charges_one(self, fake):
        pacer = migrate.Pacer()
        wrapped = migrate._PacingTransport(fake, pacer)
        wrapped.create_label(OWNER, REPO, name="x", color="ededed", description="")
        assert pacer.points_charged == migrate._REST_WRITE_POINTS  # a write = 5
        wrapped.list_labels(OWNER, REPO)
        assert pacer.points_charged == migrate._REST_WRITE_POINTS + migrate._REST_READ_POINTS

    def test_delegates_args_and_return_value_unchanged(self, fake):
        pacer = migrate.Pacer()
        wrapped = migrate._PacingTransport(fake, pacer)
        issue = wrapped.create_issue(OWNER, REPO, title="merge: the t item under test", body="b", labels=[])
        # The wrapper is transparent: it returns the transport's own result verbatim.
        assert wrapped.get_issue(OWNER, REPO, issue["number"])["number"] == issue["number"]

    def test_unclassified_method_raises_rather_than_bypassing(self, fake):
        pacer = migrate.Pacer()
        wrapped = migrate._PacingTransport(fake, pacer)
        fake.frobnicate = lambda: None  # a method fitting neither read nor write prefix
        with pytest.raises(AssertionError, match="unclassified"):
            _ = wrapped.frobnicate

    def test_every_transport_method_classifies(self, fake):
        """Metering is keyed on the method-name verb, and an unclassified name raises
        only at *call* time — i.e. mid-migration. This pins the classification at test
        time instead: every public Transport method must resolve to a known read or
        write cost, so a future method with a novel verb fails here, not in a live run."""
        import inspect

        from lib.backlog import transport as transport_mod

        wrapped = migrate._PacingTransport(fake, migrate.Pacer())
        methods = [
            name
            for name, _ in inspect.getmembers(
                transport_mod.Transport, predicate=inspect.isfunction
            )
            if not name.startswith("_")
        ]
        assert methods, "expected to enumerate the Transport surface"
        for name in methods:
            cost = wrapped._cost(name)  # raises AssertionError if the verb is unknown
            assert cost in (migrate._REST_READ_POINTS, migrate._REST_WRITE_POINTS)

    def test_import_meters_create_and_close_not_just_create(self, fake):
        """The create-then-close stretch is fully metered: points are charged for the
        closes and reconcile reads, not only the creates (BKL-6X5D part b — the old
        bug metered 'only the create')."""
        _seed_labels(fake, DISCODON_MINI)
        pacer = migrate.Pacer()  # real caps; DISCODON_MINI is tiny, so no waits
        _import(fake, DISCODON_MINI, pacer=pacer)
        creates_only = len(_DIS_PFXS) * migrate._REST_WRITE_POINTS
        # DIS-0004 (shipped) and DIS-0005 (dropped) each add a close write — so the
        # metered points must exceed creates-alone by at least those two closes.
        assert pacer.points_charged >= creates_only + 2 * migrate._REST_WRITE_POINTS

    def test_archive_stretch_throttles_on_the_points_ceiling(self, fake):
        """S2 by construction: an all-scope import whose create+close point rate
        breaches the ceiling throttles on the REST-points budget — the burst is held
        inside the ceiling, asserted as a decision (no wall clock)."""
        content = _archive_heavy_backlog(n=6)
        _seed_labels(fake, content)
        state, now, sleep = _fake_clock()
        # A deliberately tight ceiling so a few create+close items breach it.
        pacer = migrate.Pacer(per_minute_points=25, now=now, sleep=sleep)
        assert _import(fake, content, pacer=pacer)["status"] == "ok"
        assert pacer.point_waits > 0  # the points budget bound and throttled the run


# --- BKL-3K9N: reactive rate-limit backoff (pause-and-resume, never a hard-stop)


class TestRateLimitBackoff:
    """The reactive counterpart to the Pacer: a mid-import secondary 429 pauses and
    retries the SAME idempotent record in the same run (honoring Retry-After when
    present, else exponential backoff), and is **bounded** — a persistent limit falls
    through to the resumable envelope rather than spinning forever."""

    def _spy_backoff(self, **kw):
        waited: list[float] = []
        kw.setdefault("base_seconds", 1.0)
        return migrate.RateLimitBackoff(sleep=waited.append, **kw), waited

    # -- the backoff policy in isolation --------------------------------------

    def test_exponential_backoff_without_retry_after(self):
        b = migrate.RateLimitBackoff(base_seconds=2.0, max_seconds=60.0)
        assert b.wait_seconds(0) == 2.0
        assert b.wait_seconds(1) == 4.0
        assert b.wait_seconds(2) == 8.0

    def test_retry_after_is_honored_and_capped(self):
        b = migrate.RateLimitBackoff(base_seconds=2.0, max_seconds=60.0)
        assert b.wait_seconds(0, {"retry_after": 5}) == 5.0
        assert b.wait_seconds(9, {"retry_after": 9999}) == 60.0  # a hostile hint can't hang

    def test_unparseable_retry_after_falls_back_to_backoff(self):
        b = migrate.RateLimitBackoff(base_seconds=3.0)
        assert b.wait_seconds(0, {"retry_after": "soon"}) == 3.0
        assert b.wait_seconds(0, {}) == 3.0

    # -- wired into the importer ---------------------------------------------

    def test_a_mid_import_429_pauses_and_resumes_the_same_run(self, fake):
        _seed_labels(fake, DISCODON_MINI)
        # The 1st create raises a one-shot 429; the backoff pauses and retries the
        # same record — the run COMPLETES rather than hard-stopping.
        fake.fail_at_mutation(1, code="rate_limited")
        backoff, waited = self._spy_backoff()

        result = _import(fake, DISCODON_MINI, backoff=backoff)

        assert result["status"] == "ok", result  # resumed in-run, not aborted
        for pfx in _DIS_PFXS:
            assert len(_alias_issues(fake, pfx)) == 1  # every item once — no duplicate
        assert backoff.pauses == 1
        assert waited == [1.0]  # one exponential-backoff pause (attempt 0, base 1.0)

    def test_pause_honors_a_server_retry_after(self, fake):
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(1, code="rate_limited", details={"retry_after": 7})
        backoff, waited = self._spy_backoff()

        result = _import(fake, DISCODON_MINI, backoff=backoff)

        assert result["status"] == "ok", result
        assert waited == [7.0]  # the server hint, not the exponential default

    def test_a_persistent_rate_limit_is_bounded_and_stays_resumable(self, fake):
        _seed_labels(fake, DISCODON_MINI)
        fake.set_rate_limited(True)  # every call keeps 429-ing
        backoff, waited = self._spy_backoff(max_retries=3)

        result = _import(fake, DISCODON_MINI, backoff=backoff)

        # Bounded: exactly max_retries pauses, then it gives up cleanly (never-block).
        assert backoff.pauses == 3
        assert result["status"] == "error"
        assert result["error"]["code"] == "rate_limited"
        assert result["error"]["details"]["resumable"] is True

    def test_a_rate_limited_close_pauses_and_retries_like_a_create(self, fake):
        """BKL-7V2D leg 1a — the gap this class could not previously reach.

        `core.set_status` catches `TransportError` and returns an envelope, so a 429
        on the *close* never reached `_import_one_with_retry`'s handler and the
        backoff never paused: it only ever saw creates. That is backwards for the
        migration this exists to survive — under `--archive-scope all` the run closes
        about as many items as it creates, and the close stretch is where a secondary
        limit actually bites. Here the 429 lands on DIS-0004's close (mutation 5), and
        the record replays to completion in the same run."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5, code="rate_limited", details={"retry_after": 3})
        backoff, waited = self._spy_backoff()

        result = _import(fake, DISCODON_MINI, backoff=backoff)

        assert result["status"] == "ok", result
        assert backoff.pauses == 1
        assert waited == [3.0]  # the server hint honored on the close, as on a create
        # Retried to success, so it is NOT reported as left behind...
        assert result["data"]["status_unreconciled"] == []
        # ...and the close actually landed (the whole point — a replay of an
        # idempotent record converges rather than duplicating).
        dis4 = _alias_issues(fake, "DIS-0004")[0]
        assert (dis4.get("state") or "open").lower() == "closed"
        assert len(_alias_issues(fake, "DIS-0004")) == 1  # no duplicate from the replay

    def test_an_exhausted_budget_on_a_close_names_the_close_and_the_item(
        self, fake, monkeypatch
    ):
        """The bound applies to the close exactly as it does to the create: a
        persistent limit gives up cleanly into the resumable envelope rather than
        spinning, and never silently converts back into a deferral.

        The message is asserted because it is the only evidence distinguishing a 429
        storm on the close stretch from one on the creates — and that distinction is
        the whole reason the close was put on the retry contract. Without this, a
        future edit drops the attribution and the suite stays green."""
        _seed_labels(fake, DISCODON_MINI)
        backoff, waited = self._spy_backoff(max_retries=2)

        def _always_rate_limited(*args, **kwargs):
            raise TransportError("rate_limited", "secondary rate limit", details={})

        # Every create still lands; only the close keeps 429-ing.
        monkeypatch.setattr(fake, "update_issue", _always_rate_limited)
        result = _import(fake, DISCODON_MINI, backoff=backoff)

        assert backoff.pauses == 2  # bounded
        assert result["status"] == "error"
        assert result["error"]["code"] == "rate_limited"
        assert result["error"]["details"]["resumable"] is True
        # Attributed to the close stretch, and to the item — not a bare 429.
        message = result["error"]["message"]
        assert "status reconcile" in message
        assert f"{OWNER}/{REPO}#" in message

    def test_a_completed_run_never_pauses(self, fake):
        _seed_labels(fake, DISCODON_MINI)
        backoff, waited = self._spy_backoff()
        result = _import(fake, DISCODON_MINI, backoff=backoff)
        assert result["status"] == "ok"
        assert backoff.pauses == 0 and waited == []  # the happy path is untouched


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
        a = _file(fake, title="merge: the dup item under test")
        b = _file(fake, title="merge: the keep item under test")
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

    def test_human_mode_announces_items_left_at_the_wrong_status(
        self, fake, tmp_path, capsys
    ):
        """A deferred item is counted in `created`, so the summary line reads as a
        clean run. The scrub runbook drives import without `--json` (the same
        argument the pacing footer records), so a data-only field would reach every
        consumer except the one person running the irreversible migration."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # DIS-0004's close defers
        src = tmp_path / "backlog.md"
        src.write_text(DISCODON_MINI)

        assert cli.run(
            str(tmp_path), ["import", "--repo", SCOPE, "--from", str(src)], transport=fake
        ) == 0
        captured = capsys.readouterr()
        assert "imported 5 created" in captured.out  # still reads as complete...
        assert "1 item(s) imported but NOT reconciled" in captured.out  # ...but not alone
        # The per-item audit line still names WHICH item, on stderr as before.
        assert "status reconcile deferred" in captured.err

    def test_merge_human_mode_output(self, fake, capsys):
        a = _file(fake, title="merge: the dup item under test")
        b = _file(fake, title="merge: the keep item under test")
        assert cli.run("/x", ["merge", a, "--into", b], transport=fake) == 0
        assert "superseded-by" in capsys.readouterr().out


class TestPacingObservability:
    """A ~900-issue irreversible migration must be legible WHILE it runs and AFTER
    it stops (BKL-8K2N).

    `import_items` already constructs a default `Pacer`, so pacing was never absent
    — but every counter it accumulated was dropped on the floor (the SPIKE-S2
    harness was the only reader in the tree), and both blocking sleeps were silent.
    Together that meant an operator watching a paused run could not distinguish
    "waiting out a rate budget" from "wedged", and could not say afterward where the
    budget stood. For an act GitHub cannot undo, that is the observability that
    matters most.
    """

    _KEYS = {
        "rest_points_charged",
        "rest_point_waits",
        "rest_point_wait_seconds",
        "content_creation_waits",
        "content_creation_wait_seconds",
        "rate_limit_pauses",
        "rate_limit_paused_seconds",
        "budgets",
    }

    def test_run_summary_carries_pacing_telemetry(self, fake):
        result = _import(fake, DISCODON_MINI)
        assert result["status"] == "ok"
        pacing = result["data"]["pacing"]
        assert set(pacing) >= self._KEYS
        # Charged points prove the meter ran; the wait counters are the operator's
        # answer to "was I throttled, and for how long?"
        assert pacing["rest_points_charged"] > 0
        assert pacing["rest_point_waits"] == 0
        assert pacing["content_creation_waits"] == 0
        assert pacing["rate_limit_pauses"] == 0
        assert pacing["budgets"]["per_minute_points"] == 900

    def test_pacing_telemetry_survives_a_resumable_cut(self, fake):
        """The cut path is where telemetry matters MOST — a run that stopped is
        exactly when someone asks "how far did it get, and was it throttled?".
        Reporting only on the success path would describe only the runs that never
        had a problem."""
        _seed_labels(fake, DISCODON_MINI)
        original = fake.create_issue
        calls = {"n": 0}

        def failing_create(*a, **kw):
            calls["n"] += 1
            if calls["n"] > 1:
                raise TransportError("unavailable", "backend down")
            return original(*a, **kw)

        fake.create_issue = failing_create
        result = _import(fake, DISCODON_MINI)
        assert result["status"] == "error"
        assert result["error"]["details"]["resumable"] is True
        pacing = result["error"]["details"]["pacing"]
        assert set(pacing) >= self._KEYS
        assert pacing["rest_points_charged"] > 0

    def test_a_points_throttle_announces_itself(self, capsys):
        """A silent sleep is indistinguishable from a hang."""
        _state, now, sleep = _fake_clock()
        pacer = migrate.Pacer(per_minute_points=10, now=now, sleep=sleep)
        pacer.before_points(8)
        capsys.readouterr()  # under budget — nothing to announce
        pacer.before_points(8)  # breaches 10/min → must block AND say so
        err = capsys.readouterr().err
        assert "rest-point budget" in err
        assert "resuming in" in err

    def test_a_content_cap_throttle_announces_itself(self, capsys):
        _state, now, sleep = _fake_clock()
        pacer = migrate.Pacer(per_minute=1, per_hour=1000, now=now, sleep=sleep)
        pacer.before_create()
        capsys.readouterr()
        pacer.before_create()
        err = capsys.readouterr().err
        assert "content-creation budget" in err
        assert "resuming in" in err

    def test_a_rate_limit_pause_announces_itself(self, capsys):
        backoff = migrate.RateLimitBackoff(sleep=lambda s: None)
        backoff.pause(0, {"retry_after": 30})
        err = capsys.readouterr().err
        assert "rate-limited" in err
        assert "30" in err

    def test_an_unthrottled_run_stays_quiet(self, fake, capsys):
        """Pacing output must be exception reporting, not a running commentary — a
        line per call would bury the one message that matters."""
        _import(fake, DISCODON_MINI)
        assert "budget" not in capsys.readouterr().err

    def test_a_long_run_emits_periodic_progress(self, fake, capsys):
        """The complement of the guard above, and the reason it is not enough.

        VRF-009 settled that under the serial importer NO pacing budget ever
        binds (`rest_point_waits: 0` and `content_creation_waits: 0`), so every
        announcement in this class is exception-only and a *healthy* ~900-issue
        run emits nothing for 18-40 minutes. An operator with no signal is an
        operator who kills a healthy run. Progress is a different signal from
        pacing state: it says "alive and here", not "throttled"."""
        content = "# Backlog\n\n## Open\n\n" + "\n".join(
            f"- **[ITM-{i:04d}]** core: paced import item number {i}\n  `status: open · stage: ready`\n"
            for i in range(1, migrate.PROGRESS_EVERY * 2 + 2)
        )
        result = _import(fake, content)
        assert result["status"] == "ok", result
        err = capsys.readouterr().err
        assert "migrating:" in err
        # Periodic, not per-record: one line per PROGRESS_EVERY records.
        assert err.count("migrating:") == 2
        assert "budget" not in err  # still not pacing commentary

    def test_a_short_run_emits_no_progress(self, fake, capsys):
        """Below one interval there is nothing to reassure anyone about, and a
        line would be the commentary the sibling guard forbids."""
        _import(fake, DISCODON_MINI)
        assert "migrating:" not in capsys.readouterr().err

    def test_progress_goes_to_stderr_so_json_stdout_stays_pure(self, fake, tmp_path, capsys):
        """SEC-1 / VRF-004 pinned `--json` stdout as parseable JSON and nothing
        else. A progress line on stdout would break every machine caller."""
        src = tmp_path / "backlog.md"
        src.write_text(
            "# Backlog\n\n## Open\n\n"
            + "\n".join(
                f"- **[ITM-{i:04d}]** core: paced import item number {i}\n  `status: open · stage: ready`\n"
                for i in range(1, migrate.PROGRESS_EVERY + 2)
            ),
            encoding="utf-8",
        )
        assert cli.run(
            str(tmp_path),
            ["import", "--repo", f"{OWNER}/{REPO}", "--from", str(src), "--json"],
            transport=fake,
        ) == 0
        captured = capsys.readouterr()
        json.loads(captured.out)  # raises if a progress line leaked onto stdout
        assert "migrating:" in captured.err

    def test_human_mode_import_prints_a_pacing_footer(self, fake, tmp_path, capsys):
        """`migration-scrub.md` invokes import WITHOUT --json, so a JSON-only
        summary would reach every consumer except the operator running the
        irreversible migration."""
        src = tmp_path / "backlog.md"
        src.write_text(DISCODON_MINI, encoding="utf-8")
        assert cli.run(
            str(tmp_path),
            ["import", "--repo", f"{OWNER}/{REPO}", "--from", str(src)],
            transport=fake,
        ) == 0
        out = capsys.readouterr().out
        assert "pacing:" in out
        assert "REST points" in out
        assert "no throttling" in out
        # A floor, not an exact figure: the meter charges per transport method call,
        # not per HTTP request (BKL-3H7W), so an unqualified number would read as
        # precise to the person sizing an irreversible run.
        assert "\u2265" in out


def test_s2_spike_imports_when_run_as_a_script(tmp_path: Path):
    """`python tests/spikes/s2_migration.py` must import outside pytest.

    The spike bootstraps `sys.path` itself, because the root conftest's insert
    is absent when it runs as a script — and running it as a script IS the
    point: it drives a live `gh` session against a throwaway repo. Nothing else
    covers that path, since no test imports the spike, so a removed bootstrap
    would surface only when someone reached for it mid-migration. Run from an
    unrelated cwd to pin that the bootstrap resolves from the file's own
    location, not the caller's. `--help` exits before any `gh` call.
    """
    spike = _TESTS_DIR / "spikes" / "s2_migration.py"
    proc = subprocess.run(
        [sys.executable, str(spike), "--help"],
        capture_output=True, text=True, timeout=30, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, f"standalone spike run failed:\n{proc.stderr}"


# --- verify-migration: the completeness gate (F9) ----------------------------


class TestVerifyMigration:
    """The check that `samsung-frame-art-loader` needed and did not have.

    That repo recorded its cutover with 7 of 9 source items never imported. The
    runbook *did* prescribe the comparison ("Total issue count = every source
    item") but only as a human eyeball step, so a partial import passed
    unnoticed — and the moment `backlog_service_repo` was set the markdown
    stopped being read, which made the failure invisible at exactly the step
    that should have caught it."""

    def test_a_complete_migration_verifies_clean(self, fake):
        result = _import(fake, DISCODON_MINI)
        assert result["status"] == "ok", result
        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "ok", verdict
        assert verdict["data"]["missing"] == []
        assert verdict["data"]["source_items"] == verdict["data"]["aliased"]

    def test_an_unmigrated_source_item_is_named_not_counted(self, fake):
        """The verdict must name the stranded ids. A count tells the operator
        something is wrong; only the ids tell them what to re-import."""
        _import(fake, DISCODON_MINI)
        extra = DISCODON_MINI + (
            "\n- **[ZZZ-9999]** core: the item this run never imported\n  `status: open · stage: ready`\n"
        )
        verdict = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=extra)
        assert verdict["status"] == "error"
        assert verdict["error"]["code"] == "conflict"
        assert verdict["error"]["details"]["missing"] == ["ZZZ-9999"]

    def test_it_gates_on_the_source_not_on_issue_count(self, fake):
        """Issues filed natively after cutover carry a prawduct block but no
        `id:` alias, so a raw issue-count comparison passes while source items
        are still stranded — which is exactly how the observed repo looked (17
        issues, 2 aliases, 9 source items)."""
        _import(fake, DISCODON_MINI)
        for i in range(5):
            core.file_item(
                fake, owner=OWNER, repo=REPO, title=f"native {i}", body="b", facets={}
            )
        extra = DISCODON_MINI + (
            "\n- **[ZZZ-9999]** core: the stranded item with no alias\n  `status: open · stage: ready`\n"
        )
        verdict = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=extra)
        assert verdict["status"] == "error"
        assert verdict["error"]["details"]["missing"] == ["ZZZ-9999"]

    def test_cli_exit_code_is_non_zero_so_it_can_gate(self, fake, tmp_path):
        """Step 6 of the runbook must be able to depend on this mechanically."""
        _import(fake, DISCODON_MINI)
        src = tmp_path / "backlog.md"
        src.write_text(
            DISCODON_MINI
            + "\n- **[ZZZ-9999]** core: the stranded item with no alias\n  `status: open · stage: ready`\n",
            encoding="utf-8",
        )
        code = cli.run(
            str(tmp_path),
            ["verify-migration", "--repo", f"{OWNER}/{REPO}", "--from", str(src)],
            transport=fake,
        )
        assert code == 4  # conflict — source and target disagree

    def test_an_item_imported_but_never_closed_is_caught(self, fake):
        """BKL-7V2D leg 2 — the third door onto F9, and the one that gates the real
        ~900-write run.

        The import creates every item and *defers* a failed status reconcile so the
        run can continue, so an item can be present, correctly keyed, and still not
        migrated. Under `--archive-scope all` a flaky or rate-limited close stretch
        does that in bulk. Comparing alias coverage alone reported 100% here while
        the archived item sat open — the gate green and the migration not done."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)  # DIS-0004's close defers; the item stays open
        imported = _import(fake, DISCODON_MINI)
        assert imported["status"] == "ok"  # the import itself reports success

        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "error", verdict
        assert verdict["error"]["code"] == "conflict"
        details = verdict["error"]["details"]
        assert details["missing"] == []  # coverage IS complete — that was the trap
        assert details["status_mismatch"] == ["DIS-0004 (source: shipped, target: open)"]

    def test_two_issues_recording_one_alias_at_odds_is_reported_not_coin_flipped(
        self, fake
    ):
        """Critic R-10. The first-wins read was justified by the importer's collision
        branch, but that fires on two issues carrying the same `id:PFX` **label**,
        while this scan derives its PFXs from the body block `id_aliases` — a
        deliberately different source of truth (`_AliasIndex` exists *because* the
        label can be deleted while the block survives). A block-only duplicate is
        therefore invisible to the cited check, and whichever page GitHub returned
        first would decide the verdict. On the gate for ~900 irreversible writes, a
        answer that flips with page order is worse than a false positive."""
        _import(fake, DISCODON_MINI)
        # A second issue whose BLOCK claims DIS-0001, carrying no `id:` label, and
        # closed while the real DIS-0001 is open — so the two disagree.
        dup = fake.create_issue(
            OWNER, REPO,
            title="a second issue recording the same alias",
            body="Body.\n\n```prawduct\nv: 1\nid_aliases: [DIS-0001]\n```\n",
            labels=[],
        )
        fake.update_issue(
            OWNER, REPO, dup["number"],
            fields={"state": "closed", "state_reason": "completed"},
        )

        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "error", verdict
        details = verdict["error"]["details"]
        assert details["duplicate_alias"] == ["DIS-0001"]
        # It is NOT a status mismatch, and the distinction is the whole point: that
        # list's remedy is "re-run the import", which cannot clear this. The labelled
        # issue already matches so the re-run writes nothing, and the block-only
        # duplicate is never looked up — so a re-run burns a full pass and the gate
        # returns the identical exit 4. Verified below rather than argued.
        assert details["status_mismatch"] == []

        message = verdict["error"]["message"]
        assert "do not re-run the import" in message
        assert "deduplicate" in message

        second = _import(fake, DISCODON_MINI)  # the remedy the WRONG bucket prescribes
        assert second["status"] == "ok"
        again = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert again["status"] == "error"  # converges on nothing, exactly as claimed
        assert again["error"]["details"]["duplicate_alias"] == ["DIS-0001"]

    def test_the_gate_clears_once_the_resume_converges(self, fake):
        """The mismatch must be a live reading, not a sticky one: re-running the
        import closes DIS-0004, and the gate then passes. A check that stayed red
        after the remedy it prescribes would be as useless as one that never fired."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)
        _import(fake, DISCODON_MINI)
        _import(fake, DISCODON_MINI)  # the resume reconciles the deferred close

        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "ok", verdict
        assert verdict["data"]["status_mismatch"] == []

    def test_a_status_mismatch_gates_the_cli_with_the_same_exit_code(self, fake, tmp_path):
        """Folded into the existing exit-4 `conflict` rather than given its own code:
        the two stores disagree, which is the same class of answer, and step 6 of the
        runbook already depends on that number."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)
        _import(fake, DISCODON_MINI)
        src = tmp_path / "backlog.md"
        src.write_text(DISCODON_MINI, encoding="utf-8")

        code = cli.run(
            str(tmp_path),
            ["verify-migration", "--repo", f"{OWNER}/{REPO}", "--from", str(src)],
            transport=fake,
        )
        assert code == 4

    def test_the_remedy_for_a_status_mismatch_says_re_run_not_re_key(self, fake):
        """Re-running IS the fix here — the skip branch reconciles the status axis on
        already-migrated items — which puts a mismatch in `missing`'s recoverability
        class, not `unaliasable`'s. Telling the operator to re-key would be wrong."""
        _seed_labels(fake, DISCODON_MINI)
        fake.fail_at_mutation(5)
        _import(fake, DISCODON_MINI)

        message = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )["error"]["message"]
        assert "status_mismatch" in message
        assert "re-run the import" in message
        assert "give each a real PFX" not in message  # the unaliasable remedy

    def test_every_status_round_trips_so_a_clean_run_raises_no_false_positive(self, fake):
        """The gate's own risk: it now compares a decoded value against the source
        for EVERY item, so a decode that disagreed with the encoder would fail a
        healthy migration wholesale. DISCODON_MINI carries all five statuses across
        the three sections, so a clean import is the round-trip proof."""
        _import(fake, DISCODON_MINI)
        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "ok", verdict
        targets = {r.pfx: r.status for r in migrate.collect_records(DISCODON_MINI)[0]}
        assert set(targets.values()) == set(encode.STATUS_VALUES)  # all five exercised

    def test_an_id_that_is_not_a_pfx_is_reported_not_excluded(self, fake):
        """The gate's own blind spot.

        Alias coverage can only speak for items an alias can key, so building the
        source set from PFX-bearing records alone puts a hand-written id outside
        the comparison entirely: the item imports, nothing is `missing`, and a
        repo one item short of complete reports clean. This is the shape that
        passed before `unaliasable` existed.

        The two ids that originally exercised this (`AUD-TIMBRE-CALIB`,
        `MIG-M4-REMOVE`) are now absorbed as ordinary multi-segment ids, so the
        case is pinned here with a bracketed *date* — still not an id, and the
        reason the accepted shape insists on a leading letter."""
        extra = DISCODON_MINI + (
            "\n- **[2026-07-28]** hand-written id, not a PFX\n"
            "  `status: open · stage: ready`\n"
        )
        result = migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=extra)
        assert result["status"] == "ok", result

        verdict = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=extra)
        assert verdict["status"] == "error", verdict
        assert verdict["error"]["code"] == "conflict"
        details = verdict["error"]["details"]
        assert details["missing"] == []  # every *aliasable* item did make it across
        assert details["unaliasable"] == ["[2026-07-28] hand-written id, not a PFX"]

    def test_source_items_counts_every_item_not_just_the_aliasable_ones(self, fake):
        """`source_items` is read as "the complete source set". If it counted only
        PFX-bearing records it would under-report the source while claiming full
        coverage — the arithmetic has to be visible."""
        extra = DISCODON_MINI + (
            "\n- **[2026-07-28]** core: the item that cannot be aliased\n  `status: open · stage: ready`\n"
        )
        migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=extra)
        details = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=extra
        )["error"]["details"]
        assert details["source_items"] == details["aliased"] + 1

    def test_the_remedy_does_not_tell_you_to_re_import_an_unaliasable_item(self, fake):
        """Re-import is the right fix for `missing` and the WRONG one here: the
        idempotency key is a digest of title+body, so giving the item a real PFX
        changes the key and mints a second issue instead of adopting the first."""
        extra = DISCODON_MINI + (
            "\n- **[2026-07-28]** core: the item that cannot be aliased\n  `status: open · stage: ready`\n"
        )
        migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=extra)
        message = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=extra
        )["error"]["message"]
        assert "BEFORE importing" in message
        assert "re-run import" not in message  # no `missing` items in this run

    def test_a_clean_migration_still_verifies_clean_with_the_new_field(self, fake):
        """The added field must not turn a good migration into a conflict."""
        _import(fake, DISCODON_MINI)
        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI
        )
        assert verdict["status"] == "ok", verdict
        assert verdict["data"]["unaliasable"] == []

    def test_archive_scope_open_does_not_strand_the_items_it_deliberately_skips(
        self, fake
    ):
        """The gate's source set must be the importer's create set.

        `--archive-scope open` skips items that would be created closed — by
        *status*, and in the main `backlog.md` too, not only in a separate
        `--archive` file. A gate that re-derives the source set by file instead
        counts every shipped/dropped item as `missing`: ~150 of them on a mature
        backlog, on a gate whose prescribed remedy is "re-run the import", which
        cannot ever clear it."""
        src = DISCODON_MINI + (
            "\n- **[SHP-0001]** already shipped\n  `status: shipped · stage: ready`\n"
            "- **[DRP-0002]** dropped long ago\n  `status: dropped · stage: ready`\n"
        )
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=src, archive_scope="open"
        )
        assert result["status"] == "ok", result

        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=src, archive_scope="open"
        )
        assert verdict["status"] == "ok", verdict
        assert verdict["data"]["missing"] == []

    def test_archive_scope_open_still_catches_a_genuinely_stranded_open_item(
        self, fake
    ):
        """The scope fix must not buy its silence by loosening the gate: an
        *open* item that never imported is still a conflict under `open`."""
        src = DISCODON_MINI + (
            "\n- **[SHP-0001]** already shipped\n  `status: shipped · stage: ready`\n"
        )
        migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=src, archive_scope="open"
        )
        stranded = src + "\n- **[ZZZ-9999]** core: an open item never imported here\n  `status: open`\n"
        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=stranded, archive_scope="open"
        )
        assert verdict["status"] == "error"
        assert verdict["error"]["details"]["missing"] == ["ZZZ-9999"]

    def test_a_duplicate_pfx_collision_is_reported_not_dropped(self, fake):
        """The one class of un-imported item the gate structurally could not see.

        `collect_records` drops a collided item rather than merging two items
        onto one alias — so it is never created, and being absent from `records`
        it left `missing` empty and the gate green."""
        src = DISCODON_MINI + (
            "\n- **[DUP-0001]** core: the first claimant of this prefix\n  `status: open · stage: ready`\n"
            "- **[DUP-0001]** second claimant, same pfx\n  `status: open · stage: ready`\n"
        )
        result = migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=src)
        assert result["status"] == "ok", result

        verdict = migrate.verify_migration(fake, owner=OWNER, repo=REPO, content=src)
        assert verdict["status"] == "error", verdict
        assert verdict["error"]["details"]["missing"] == []  # the second door
        assert len(verdict["error"]["details"]["collisions"]) == 1
        assert "DUP-0001" in verdict["error"]["details"]["collisions"][0]

    def test_an_archive_file_is_included_in_the_source_set(self, fake, tmp_path):
        """A migration run with --archive must be verifiable the same way, or
        the check silently passes on a partially-imported archive."""
        archive = "# Archive\n\n## Archive\n\n- **[ARC-0001]** core: the archived item for this case\n  `status: shipped`\n"
        result = migrate.import_backlog(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI, archive_content=archive
        )
        assert result["status"] == "ok", result
        verdict = migrate.verify_migration(
            fake, owner=OWNER, repo=REPO, content=DISCODON_MINI, archive_content=archive
        )
        assert verdict["status"] == "ok", verdict
        assert "ARC-0001" not in verdict["data"]["missing"]
