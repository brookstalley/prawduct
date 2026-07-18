"""Tests for lib/backlog/core.py — file / get / provision via the L1 fake.

Covers the envelope (ERR-3/ERR-4), the file→get round-trip, SEC-3 attribution
(API identity, resolved once), ERR-6 boundary-exception handling, and PROV-1
(namespaced labels created without colliding).
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import core, encode, ids  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"

_STATUS_LABELS = ["status:submitted", "status:in-progress"]
_MUTATING = {"create_issue", "create_label", "update_issue", "add_labels", "remove_label", "create_comment"}


@pytest.fixture
def fake():
    return FakeGitHub()


def _seed_item(fake, *, labels=(), body="b"):
    """Create one open issue carrying `labels` (all pre-seeded so create succeeds)."""
    fake.seed_labels(OWNER, REPO, sorted(set(list(labels) + _STATUS_LABELS)))
    issue = fake.create_issue(OWNER, REPO, title="t", body=body, labels=list(labels))
    return issue["number"]


def _decoded_status(fake, number):
    issue = fake.get_issue(OWNER, REPO, number)
    return encode.decode_status(issue, encode.label_names(issue))[0]


def _status_labels(item_or_data):
    labels = item_or_data["labels"] if isinstance(item_or_data, dict) else item_or_data
    return [name for name in labels if name.startswith("status:")]


class TestFileItem:
    def test_returns_ok_envelope_with_immediate_id(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="Do X", body="why")
        assert result["status"] == "ok"
        assert result["data"]["id"] == "octo/repo#1"
        assert result["data"]["number"] == 1
        assert result["data"]["node_id"]
        assert result["warnings"] == []

    def test_new_item_defaults_to_open(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        assert result["data"]["status"] == "open"  # no status: label

    def test_stage_facet_provisioned_and_applied(self, fake):
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="X", body="b", facets={"stage": "ready"}
        )
        assert result["status"] == "ok"
        assert result["data"]["stage"] == "ready"
        assert "stage:ready" in {name for name in fake.repos[(OWNER, REPO)].labels}

    def test_unknown_stage_warns_but_succeeds(self, fake):
        # ENC-1 at the op level — flagged, not rejected.
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="X", body="b", facets={"stage": "brainstorm"}
        )
        assert result["status"] == "ok"
        assert result["data"]["stage"] == "brainstorm"
        assert any("brainstorm" in w for w in result["warnings"])

    def test_missing_title_is_validation(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="  ", body="b")
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"

    def test_body_carries_prawduct_block(self, fake):
        core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="the body")
        issue = fake.repos[(OWNER, REPO)].issues[1]
        assert "```prawduct" in issue["body"]
        assert "v: 1" in issue["body"]
        assert "the body" in issue["body"]


class TestFileStandard:
    """BKL-2H9W/BKL-4C6P — the `file` path applies the issue-structure standard
    (title normalization + kind/area) and lints the result (WARN-only)."""

    def test_normalizes_area_prefixed_title(self, fake):
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="parser drops flags", body="b",
            facets={"area": "cli"},
        )
        assert result["data"]["title"] == "cli: parser drops flags"

    def test_does_not_double_prefix(self, fake):
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="cli: parser drops flags", body="b",
            facets={"area": "cli"},
        )
        assert result["data"]["title"] == "cli: parser drops flags"

    def test_lint_field_present_and_flags_terse_item(self, fake):
        # A terse, kind-less item lints (short title, no kind:) — WARN-only, so it
        # still succeeds, and the findings ride in `lint`, not `warnings`.
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        assert result["status"] == "ok"
        rules = {f["rule"] for f in result["lint"]}
        assert "no-kind" in rules
        assert "title-too-short" in rules
        assert result["warnings"] == []  # lint is a distinct channel

    def test_compliant_item_lints_clean(self, fake):
        from lib.backlog import issuefmt

        body = issuefmt.render_body(
            "bug",
            {
                "Problem": "The importer never reads the id:PFX alias, so re-import duplicates.",
                "Repro": "Run import twice against the same source file.",
                "Actual": "Two issues per source item.",
                "Expected": "The second run skips existing items.",
                "Evidence": "migrate.py:120",
                "Env": "prawduct v3.1.0 (plugin)",  # §2: bugs carry the product version
            },
        )
        result = core.file_item(
            fake, owner=OWNER, repo=REPO,
            title="alias read-resolution unwired breaks idempotency", body=body,
            facets={"kind": "bug", "area": "importer"},
        )
        assert result["status"] == "ok"
        assert result["lint"] == []


class TestAttribution:
    """SEC-3 — actor is the API identity, resolved once across a sweep."""

    def test_actor_is_api_identity(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        assert result["data"]["actor"] == fake.user["login"]

    def test_identity_resolved_once_across_a_sweep(self, fake):
        for n in range(3):
            core.file_item(fake, owner=OWNER, repo=REPO, title=f"X{n}", body="b")
        # One resolution for the whole sweep — not one per mutation.
        assert fake.user_resolutions == 1


class TestGetItem:
    def test_file_then_get_round_trip(self, fake):
        filed = core.file_item(
            fake, owner=OWNER, repo=REPO, title="Round trip", body="b", facets={"stage": "ready"}
        )
        got = core.get_item(fake, id_raw=filed["data"]["id"])
        assert got["status"] == "ok"
        assert got["data"]["id"] == "octo/repo#1"
        assert got["data"]["title"] == "Round trip"
        assert got["data"]["stage"] == "ready"

    def test_get_short_form_with_default_owner(self, fake):
        core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        got = core.get_item(fake, id_raw="repo#1", default_owner=OWNER)
        assert got["status"] == "ok"
        assert got["data"]["id"] == "octo/repo#1"

    def test_get_missing_is_not_found(self, fake):
        got = core.get_item(fake, id_raw="octo/repo#999")
        assert got["status"] == "error"
        assert got["error"]["code"] == "not_found"

    def test_get_bad_id_is_validation(self, fake):
        got = core.get_item(fake, id_raw="not-an-id-at-all")
        assert got["status"] == "error"
        assert got["error"]["code"] == "validation"


class TestGetByPfxAlias:
    """BKL-4W7H / MG1 read path — a hand-minted PFX (e.g. ``BKL-0QR1``) resolves via
    its ``id:PFX`` alias label against ``--repo``, so a migrated id stays a valid
    ref forever. A real spelling still resolves purely (no label search)."""

    def _seed_alias(self, fake, pfx):
        return _seed_item(fake, labels=[ids.alias_label(pfx)])

    def test_pfx_resolves_to_its_aliased_issue(self, fake):
        number = self._seed_alias(fake, "BKL-0QR1")
        got = core.get_item(fake, id_raw="BKL-0QR1", default_repo=(OWNER, REPO))
        assert got["status"] == "ok"
        assert got["data"]["id"] == f"{OWNER}/{REPO}#{number}"

    def test_pfx_without_a_repo_is_a_clear_validation_error(self, fake):
        self._seed_alias(fake, "BKL-0QR1")
        got = core.get_item(fake, id_raw="BKL-0QR1")  # no default_repo
        assert got["status"] == "error"
        assert got["error"]["code"] == "validation"
        assert "--repo" in got["error"]["message"]

    def test_unknown_pfx_is_not_found(self, fake):
        got = core.get_item(fake, id_raw="BKL-9ZZZ", default_repo=(OWNER, REPO))
        assert got["status"] == "error"
        assert got["error"]["code"] == "not_found"

    def test_colliding_pfx_is_flagged_not_guessed(self, fake):
        # Two issues carry id:BKL-0QR1 — the §5 alias-uniqueness invariant broke.
        self._seed_alias(fake, "BKL-0QR1")
        self._seed_alias(fake, "BKL-0QR1")
        got = core.get_item(fake, id_raw="BKL-0QR1", default_repo=(OWNER, REPO))
        assert got["status"] == "error"
        assert got["error"]["code"] == "alias_collision"

    def test_canonical_id_bypasses_the_alias_search(self, fake):
        core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        fake.calls.clear()
        got = core.get_item(fake, id_raw=f"{OWNER}/{REPO}#1", default_repo=(OWNER, REPO))
        assert got["status"] == "ok"
        # A resolved spelling does no label search — only the get_issue.
        assert not any(c[0] == "list_issues" for c in fake.calls)


class TestDigitSuffixPfxDisambiguation:
    """A digit-suffix token (``ADR-12``) matches BOTH the shell ``repo-number``
    spelling and the PFX grammar. With a target repo present the alias is
    authoritative when an item carries it (an exact, uniqueness-checked match —
    MG1) and the ``repo-number`` reading stands when none does; the ``#``
    spellings never enter the alias path, so they stay the escape hatch."""

    PFX = "ADR-12"

    def test_digit_suffix_alias_wins_over_the_repo_number_reading(self, fake):
        number = _seed_item(fake, labels=[ids.alias_label(self.PFX)])
        got = core.get_item(fake, id_raw=self.PFX, default_repo=(OWNER, REPO))
        assert got["status"] == "ok"
        assert got["data"]["id"] == f"{OWNER}/{REPO}#{number}"

    def test_digit_suffix_without_an_alias_falls_back_to_repo_number(self, fake):
        nid = core.resolve_ref(
            fake, self.PFX, default_owner=OWNER, default_repo=(OWNER, REPO)
        )
        assert nid.ok
        assert nid.canonical == f"{OWNER}/ADR#12"

    def test_digit_suffix_collision_is_flagged_not_guessed(self, fake):
        _seed_item(fake, labels=[ids.alias_label(self.PFX)])
        _seed_item(fake, labels=[ids.alias_label(self.PFX)])
        nid = core.resolve_ref(
            fake, self.PFX, default_owner=OWNER, default_repo=(OWNER, REPO)
        )
        assert not nid.ok
        assert nid.error == "alias_collision"

    def test_hash_spelling_never_enters_the_alias_path(self, fake):
        _seed_item(fake, labels=[ids.alias_label(self.PFX)])  # bait alias
        fake.calls.clear()
        nid = core.resolve_ref(
            fake, "ADR#12", default_owner=OWNER, default_repo=(OWNER, REPO)
        )
        assert nid.ok
        assert nid.canonical == f"{OWNER}/ADR#12"
        assert not any(c[0] == "list_issues" for c in fake.calls)

    def test_without_a_target_repo_the_repo_number_reading_stands(self, fake):
        _seed_item(fake, labels=[ids.alias_label(self.PFX)])  # bait alias
        fake.calls.clear()
        nid = core.resolve_ref(fake, self.PFX, default_owner=OWNER)
        assert nid.ok
        assert nid.canonical == f"{OWNER}/ADR#12"
        assert not any(c[0] == "list_issues" for c in fake.calls)


class TestMutatorsByPfxAlias:
    """BKL-7Q2N / MG1 — every single-id mutator (not just get/link) resolves a bare
    hand-minted ``PFX`` via its ``id:PFX`` alias against ``--repo``, so a migrated id
    stays a valid ref forever across ``status``/``update``/``comment``/``claim``/
    ``unclaim``. Absent ``--repo`` a bare PFX is a clear validation error, never a
    silent guess; an unknown PFX is ``not_found`` (a real spelling still does no I/O)."""

    PFX = "BKL-0QR1"

    def _seed_alias(self, fake):
        return _seed_item(fake, labels=[ids.alias_label(self.PFX)])

    def test_status_resolves_a_bare_pfx(self, fake):
        number = self._seed_alias(fake)
        got = core.set_status(
            fake, id_raw=self.PFX, target="in-progress", default_repo=(OWNER, REPO)
        )
        assert got["status"] == "ok", got
        assert got["data"]["id"] == f"{OWNER}/{REPO}#{number}"
        assert _decoded_status(fake, number) == "in-progress"

    def test_update_resolves_a_bare_pfx(self, fake):
        number = self._seed_alias(fake)
        got = core.update_item(
            fake, id_raw=self.PFX, fields={"title": "renamed"}, default_repo=(OWNER, REPO)
        )
        assert got["status"] == "ok", got
        assert got["data"]["id"] == f"{OWNER}/{REPO}#{number}"

    def test_comment_resolves_a_bare_pfx(self, fake):
        number = self._seed_alias(fake)
        got = core.comment_item(
            fake, id_raw=self.PFX, body="a note", default_repo=(OWNER, REPO)
        )
        assert got["status"] == "ok", got
        assert got["data"]["item"] == f"{OWNER}/{REPO}#{number}"

    def test_claim_and_unclaim_resolve_a_bare_pfx(self, fake):
        number = self._seed_alias(fake)
        claimed = core.claim(fake, id_raw=self.PFX, default_repo=(OWNER, REPO))
        assert claimed["status"] == "ok", claimed
        assert claimed["data"]["id"] == f"{OWNER}/{REPO}#{number}"
        released = core.unclaim(fake, id_raw=self.PFX, default_repo=(OWNER, REPO))
        assert released["status"] == "ok", released
        assert released["data"]["assignee"] is None

    @pytest.mark.parametrize(
        "call",
        [
            lambda f, pfx: core.set_status(f, id_raw=pfx, target="in-progress"),
            lambda f, pfx: core.update_item(f, id_raw=pfx, fields={"title": "x"}),
            lambda f, pfx: core.comment_item(f, id_raw=pfx, body="x"),
            lambda f, pfx: core.claim(f, id_raw=pfx),
            lambda f, pfx: core.unclaim(f, id_raw=pfx),
        ],
    )
    def test_bare_pfx_without_a_repo_is_a_clear_validation_error(self, fake, call):
        self._seed_alias(fake)
        got = call(fake, self.PFX)  # no default_repo
        assert got["status"] == "error"
        assert got["error"]["code"] == "validation"
        assert "--repo" in got["error"]["message"]

    def test_unknown_pfx_mutation_is_not_found(self, fake):
        got = core.set_status(
            fake, id_raw="BKL-9ZZZ", target="in-progress", default_repo=(OWNER, REPO)
        )
        assert got["status"] == "error"
        assert got["error"]["code"] == "not_found"


class TestBoundaryExceptions:
    """ERR-6 — an unexpected transport OSError is caught and mapped, not swallowed."""

    def test_unexpected_oserror_maps_to_unavailable(self, fake):
        class Broken(FakeGitHub):
            def create_issue(self, *a, **k):
                raise OSError("socket exploded")

        result = core.file_item(Broken(), owner=OWNER, repo=REPO, title="X", body="b")
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"


class TestProvision:
    """PROV-1 — namespaced labels created without colliding; existing untouched."""

    def test_creates_base_taxonomy(self, fake):
        result = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert result["status"] == "ok"
        created = set(result["data"]["created"])
        assert "stage:ready" in created
        assert "status:in-progress" in created

    def test_existing_non_prawduct_label_untouched(self, fake):
        fake.seed_labels(OWNER, REPO, ["bug"])
        before = dict(fake.repos[(OWNER, REPO)].labels["bug"])
        result = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert "bug" not in result["data"]["created"]
        assert fake.repos[(OWNER, REPO)].labels["bug"] == before  # not modified

    def test_provision_is_idempotent(self, fake):
        first = core.provision_labels(fake, owner=OWNER, repo=REPO)
        second = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert second["data"]["created"] == []
        assert set(second["data"]["existing"]) == set(first["data"]["created"])


class TestEnvelopeShape:
    """ERR-3 / ERR-4 — uniform ok/error/warnings structure."""

    def test_ok_shape(self):
        env = core.ok({"a": 1}, ["heads up"])
        assert env == {"status": "ok", "data": {"a": 1}, "warnings": ["heads up"]}

    def test_error_shape_and_retryable_default(self):
        env = core.error("unavailable", "down")
        assert env["status"] == "error"
        assert env["error"]["code"] == "unavailable"
        assert env["error"]["retryable"] is True  # from the vocabulary default
        assert env["error"]["details"] == {}

    def test_validation_is_not_retryable(self):
        assert core.error("validation", "bad")["error"]["retryable"] is False


class TestSetStatus:
    """The idempotent two-axis transition (Data Model §4 B1, CC1/M5)."""

    def test_open_to_shipped_closes_and_strips_status_label(self, fake):
        n = _seed_item(fake, labels=["status:in-progress"])
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert r["status"] == "ok"
        assert r["data"]["status"] == "shipped"
        assert _status_labels(r["data"]) == []  # closed states carry no status: label

    def test_open_substate_transition_add_before_remove(self, fake):
        n = _seed_item(fake, labels=["status:submitted"])
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="in-progress")
        assert r["data"]["status"] == "in-progress"
        assert _status_labels(r["data"]) == ["status:in-progress"]  # loser gone

    def test_reopen_clears_close_reason(self, fake):
        n = _seed_item(fake, labels=[])
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="in-progress")
        issue = fake.get_issue(OWNER, REPO, n)
        assert issue["state"] == "open" and issue["state_reason"] is None
        assert r["data"]["status"] == "in-progress"

    def test_rerun_is_a_noop(self, fake):
        n = _seed_item(fake, labels=["status:in-progress"])
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        mark = len(fake.calls)
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert r["data"]["status"] == "shipped"
        mutating = [c for c in fake.calls[mark:] if c[0] in _MUTATING]
        assert mutating == []  # re-run touches nothing (idempotent)

    def test_unknown_target_is_validation(self, fake):
        n = _seed_item(fake)
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="frozen")
        assert r["status"] == "error" and r["error"]["code"] == "validation"

    def test_bad_id_is_validation(self, fake):
        r = core.set_status(fake, id_raw="not an id", target="shipped")
        assert r["status"] == "error" and r["error"]["code"] == "validation"


class TestSetStatusCrashSafety:
    """CRASH-1 — set-status partial-transition recovery (Test Specs §3.2, CC1/M5).

    Spec-coherence note: for a *closed* target the canonical order is
    state-authority-first, then strip labels — there is no ``status:shipped`` label
    in the taxonomy (Data Model §4), so the illustrative "(2) add status:shipped" in
    Test Specs §3.2 does not apply; the closed ``state_reason`` is the authority the
    decoder reads at every cut point, so there is never an unreadable window.
    """

    @pytest.mark.parametrize("fail_call", [1, 2])
    def test_crash_at_each_cut_point_stays_valid_and_reruns_converge(self, fake, fail_call):
        n = _seed_item(fake, labels=["status:in-progress"])  # open ∧ status:in-progress
        fake.fail_at_mutation(fail_call)
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert r["status"] == "error" and r["error"]["code"] == "unavailable"
        # the decoder reads a VALID status at the cut point — never a torn two-value
        assert _decoded_status(fake, n) in {"in-progress", "shipped"}
        # the first completing re-run reaches closed ∧ shipped, no status: label
        r2 = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert r2["data"]["status"] == "shipped"
        assert _status_labels(r2["data"]) == []
        # a further re-run is a no-op
        mark = len(fake.calls)
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert [c for c in fake.calls[mark:] if c[0] in _MUTATING] == []

    def test_open_substate_transition_never_opens_a_zero_label_window(self, fake):
        # submitted → in-progress with the loser-removal (call 2) failing: the label
        # was added before the remove, so the item still carries a status label.
        n = _seed_item(fake, labels=["status:submitted"])
        fake.fail_at_mutation(2)  # 1 = add status:in-progress, 2 = remove status:submitted
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="in-progress")
        assert r["status"] == "error"
        issue = fake.get_issue(OWNER, REPO, n)
        present = _status_labels(encode.label_names(issue))
        assert "status:in-progress" in present  # never a zero-label window
        assert _decoded_status(fake, n) == "in-progress"  # precedence over the transient submitted
        r2 = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="in-progress")
        assert _status_labels(r2["data"]) == ["status:in-progress"]


class TestReconcilingWrite:
    """ENC-5 — a torn / multi-label state self-heals on the next reconciling write."""

    def test_two_open_labels_reconcile_removes_the_loser(self, fake):
        n = _seed_item(fake, labels=["status:submitted", "status:in-progress"])
        assert _decoded_status(fake, n) == "in-progress"  # (a) highest precedence
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="in-progress")
        assert _status_labels(r["data"]) == ["status:in-progress"]  # loser stripped

    def test_closed_with_stray_status_label_is_stripped(self, fake):
        n = _seed_item(fake, labels=["status:in-progress"])
        # a human closes it in the UI (state only), leaving the stray label
        fake.update_issue(OWNER, REPO, n, fields={"state": "closed", "state_reason": "completed"})
        assert _decoded_status(fake, n) == "shipped"  # (b) state_reason authoritative
        r = core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{n}", target="shipped")
        assert r["data"]["status"] == "shipped"
        assert _status_labels(r["data"]) == []  # stray stripped


class TestUpdateItem:
    """update — field-wise edit with optimistic CAS (CC2) and mass-assignment guard (SEC-2)."""

    def test_updates_title_and_body(self, fake):
        n = _seed_item(fake)
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"title": "new", "body": "changed"})
        assert r["status"] == "ok" and r["data"]["title"] == "new"

    def test_body_update_preserves_the_prawduct_block(self, fake):
        # A --body edit must NOT drop body-authoritative block fields (id_aliases,
        # etc.) that live only in the body (Data Model §2) — the MG2/permanent-
        # alias-loss footgun the update path would otherwise open.
        fake.seed_labels(OWNER, REPO, _STATUS_LABELS)
        body = "original text\n\n```prawduct\nv: 1\nid_aliases: [BKL-0007]\n```\n"
        n = fake.create_issue(OWNER, REPO, title="t", body=body, labels=[])["number"]
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"body": "rewritten body"})
        assert r["status"] == "ok"
        new_body = fake.get_issue(OWNER, REPO, n)["body"]
        assert "rewritten body" in new_body and "original text" not in new_body  # text replaced
        assert "id_aliases: [BKL-0007]" in new_body  # block preserved intact

    def test_body_update_without_existing_block_adds_a_fresh_one(self, fake):
        n = _seed_item(fake, body="plain, no block")
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"body": "new plain"})
        assert r["status"] == "ok"
        new_body = fake.get_issue(OWNER, REPO, n)["body"]
        assert "```prawduct" in new_body and "v: 1" in new_body

    def test_body_update_drops_a_caller_pasted_block_no_duplicate(self, fake):
        # The block is edited through its own fields, not free-text --body: a block
        # the caller pastes in is stripped so there is never a duplicated block.
        fake.seed_labels(OWNER, REPO, _STATUS_LABELS)
        body = "x\n\n```prawduct\nv: 1\nid_aliases: [BKL-0001]\n```\n"
        n = fake.create_issue(OWNER, REPO, title="t", body=body, labels=[])["number"]
        pasted = "new\n\n```prawduct\nv: 1\nid_aliases: [ATTACKER]\n```\n"
        core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"body": pasted})
        new_body = fake.get_issue(OWNER, REPO, n)["body"]
        assert new_body.count("```prawduct") == 1  # exactly one block
        assert "BKL-0001" in new_body and "ATTACKER" not in new_body  # existing block wins

    def test_facet_edit_swaps_the_label(self, fake):
        n = _seed_item(fake, labels=["stage:idea"])
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"stage": "ready"})
        assert r["data"]["stage"] == "ready"
        assert "stage:ready" in r["data"]["labels"] and "stage:idea" not in r["data"]["labels"]

    def test_unknown_facet_value_warns_not_rejects(self, fake):
        # ENC-1 on the update path — flagged, not a validation error.
        n = _seed_item(fake)
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"stage": "brainstorm"})
        assert r["status"] == "ok" and r["data"]["stage"] == "brainstorm"
        assert any("brainstorm" in w for w in r["warnings"])

    def test_empty_update_is_validation(self, fake):
        n = _seed_item(fake)
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={})
        assert r["status"] == "error" and r["error"]["code"] == "validation"

    def test_cc2_stale_updated_at_is_conflict_retryable(self, fake):
        n = _seed_item(fake)
        stale = fake.get_issue(OWNER, REPO, n)["updated_at"]
        core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"title": "moved"})  # someone else edits
        r = core.update_item(
            fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"title": "mine"}, expected_updated_at=stale
        )
        assert r["status"] == "error" and r["error"]["code"] == "conflict"
        assert r["error"]["retryable"] is True

    def test_cc2_fresh_updated_at_succeeds(self, fake):
        n = _seed_item(fake)
        fresh = fake.get_issue(OWNER, REPO, n)["updated_at"]
        r = core.update_item(
            fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"title": "ok"}, expected_updated_at=fresh
        )
        assert r["status"] == "ok"

    @pytest.mark.parametrize(
        "bad_field",
        [{"node_id": "x"}, {"history": "[]"}, {"state": "closed"}, {"status": "shipped"},
         {"assignee": "evil"}, {"automated": "yes"}, {"number": "99"}],
    )
    def test_sec2_protected_fields_are_rejected(self, fake, bad_field):
        # SEC-2 — a native/protected field in the request is refused, never written.
        n = _seed_item(fake)
        r = core.update_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", fields=bad_field)
        assert r["status"] == "error" and r["error"]["code"] == "validation"
        assert list(bad_field)[0] in r["error"]["details"]["rejected"]

    def test_sec2_rejects_the_whole_request_even_with_a_valid_field(self, fake):
        # A mix of a writable and a protected field is refused — the guard binds
        # only documented fields; it does not silently apply the allowed part.
        n = _seed_item(fake)
        r = core.update_item(
            fake, id_raw=f"{OWNER}/{REPO}#{n}", fields={"title": "ok", "node_id": "x"}
        )
        assert r["status"] == "error" and r["error"]["code"] == "validation"
        assert fake.get_issue(OWNER, REPO, n)["title"] == "t"  # nothing was written


class TestCommentItem:
    def test_comment_is_attributed_to_the_api_identity(self, fake):
        n = _seed_item(fake)
        r = core.comment_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", body="a note")
        assert r["status"] == "ok"
        assert r["data"]["actor"] == "octocat"  # API identity, never caller-supplied
        assert r["data"]["item"] == f"{OWNER}/{REPO}#{n}"

    def test_empty_comment_is_validation(self, fake):
        n = _seed_item(fake)
        r = core.comment_item(fake, id_raw=f"{OWNER}/{REPO}#{n}", body="   ")
        assert r["status"] == "error" and r["error"]["code"] == "validation"

    def test_comment_on_missing_item_is_not_found(self, fake):
        fake.seed_labels(OWNER, REPO, _STATUS_LABELS)
        r = core.comment_item(fake, id_raw=f"{OWNER}/{REPO}#999", body="hi")
        assert r["status"] == "error" and r["error"]["code"] == "not_found"
