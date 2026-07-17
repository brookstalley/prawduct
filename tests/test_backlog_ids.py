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
