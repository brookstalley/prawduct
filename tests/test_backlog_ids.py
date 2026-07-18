"""Tests for lib/backlog/ids.py — ID normalization (ID-1, D4/DM4).

The four accepted spellings normalize to one canonical ``owner/repo#number``,
short/shell forms resolve same-owner only, and normalization is idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import ids  # noqa: E402


class TestNormalizeFourSpellings:
    """ID-1 — the four accepted spellings all normalize to canonical."""

    CANON = "octo/repo#123"

    @pytest.mark.parametrize(
        "spelling",
        [
            "octo/repo#123",  # canonical
            "repo#123",  # short, same-owner
            "repo/123",  # shell-friendly slash
            "repo-123",  # shell-friendly hyphen
        ],
    )
    def test_all_spellings_reach_one_canonical(self, spelling):
        result = ids.normalize_id(spelling, default_owner="octo")
        assert result.ok
        assert result.canonical == self.CANON
        assert result.owner == "octo"
        assert result.repo == "repo"
        assert result.number == 123

    @pytest.mark.parametrize(
        "spelling",
        ["octo/repo#123", "repo#123", "repo/123", "repo-123"],
    )
    def test_normalization_is_idempotent(self, spelling):
        once = ids.normalize_id(spelling, default_owner="octo")
        twice = ids.normalize_id(once.canonical, default_owner="octo")
        assert twice.canonical == once.canonical

    def test_canonical_needs_no_default_owner(self):
        result = ids.normalize_id("octo/repo#7")
        assert result.ok
        assert result.canonical == "octo/repo#7"


class TestRepoNamesWithHyphens:
    """A repo name may itself contain hyphens; the number is the trailing group."""

    def test_hyphenated_repo_splits_on_last_hyphen(self):
        result = ids.normalize_id("my-repo-42", default_owner="octo")
        assert result.ok
        assert result.canonical == "octo/my-repo#42"

    def test_hyphenated_repo_hash_form(self):
        result = ids.normalize_id("my-repo#42", default_owner="octo")
        assert result.canonical == "octo/my-repo#42"


class TestShortFormNeedsOwner:
    """Short/shell spellings are same-owner only — no owner is a validation error, not a guess."""

    @pytest.mark.parametrize("spelling", ["repo#5", "repo/5", "repo-5"])
    def test_missing_owner_is_validation(self, spelling):
        result = ids.normalize_id(spelling)  # no default_owner
        assert not result.ok
        assert result.error == "validation"
        assert result.message


class TestRejections:
    def test_non_numeric_issue_number_rejected(self):
        result = ids.normalize_id("octo/repo#abc")
        assert not result.ok
        assert result.error == "validation"

    def test_owner_repo_without_number_rejected(self):
        # 'owner/repo' with no '#number' is not an item ID.
        result = ids.normalize_id("octo/repo", default_owner="octo")
        assert not result.ok
        assert result.error == "validation"
        assert "no issue number" in result.message

    @pytest.mark.parametrize("spelling", ["", "   ", "garbage", "#123"])
    def test_malformed_rejected(self, spelling):
        result = ids.normalize_id(spelling, default_owner="octo")
        assert not result.ok
        assert result.error == "validation"


class TestParseRepo:
    def test_valid_owner_repo(self):
        assert ids.parse_repo("octo/repo") == ("octo", "repo")

    @pytest.mark.parametrize("spec", ["", "norepo", "a/b/c", "octo/", "/repo"])
    def test_invalid_owner_repo(self, spec):
        assert ids.parse_repo(spec) is None


class TestPfxAliases:
    """The PFX-alias machinery (D4/DM4/§5): a hand-minted ``PFX-XXXX`` ↔ its
    permanent ``id:PFX-XXXX`` alias label. No new PFX is ever minted."""

    @pytest.mark.parametrize("pfx", ["BKL-7M4Q", "ADR-12", "A-1", "DIS-0001", "P00-2001"])
    def test_wellformed_pfx_accepted(self, pfx):
        assert ids.is_pfx(pfx)

    @pytest.mark.parametrize("token", ["", None, "nodash", "-1234", "BKL", "  ", "a b-1"])
    def test_malformed_pfx_rejected(self, token):
        assert not ids.is_pfx(token)

    def test_alias_label_roundtrips(self):
        assert ids.alias_label("BKL-7M4Q") == "id:BKL-7M4Q"
        assert ids.pfx_from_alias_label("id:BKL-7M4Q") == "BKL-7M4Q"

    def test_alias_label_tolerates_whitespace(self):
        assert ids.alias_label(" BKL-1 ") == "id:BKL-1"

    @pytest.mark.parametrize("name", ["stage:ready", "id:not a pfx", "id:", "notid:BKL-1"])
    def test_non_alias_label_returns_none(self, name):
        assert ids.pfx_from_alias_label(name) is None


class TestResolveRedirect:
    """The pure redirect-follow (merge/transfer): a ref to a merged-away source
    resolves to its survivor, with a cycle guard so it never loops (CRASH-2)."""

    def test_follows_a_chain_to_the_end(self):
        chain = {"o/r#1": "o/r#2", "o/r#2": "o/r#3"}
        assert ids.resolve_redirect("o/r#1", fetch=chain.get) == "o/r#3"

    def test_no_redirect_is_self(self):
        assert ids.resolve_redirect("o/r#9", fetch=lambda _c: None) == "o/r#9"

    def test_self_redirect_terminates(self):
        assert ids.resolve_redirect("o/r#1", fetch=lambda _c: "o/r#1") == "o/r#1"

    def test_cycle_terminates_fail_open(self):
        cycle = {"o/r#1": "o/r#2", "o/r#2": "o/r#1"}
        assert ids.resolve_redirect("o/r#1", fetch=cycle.get) in ("o/r#1", "o/r#2")
