"""`lib/control_checks.py` — the structured `check` a Critic control's firing
carries, derived from the title token the reviewer already writes (#548).

A control's yield was recoverable only from free text: the persisted `goal`
is reviewer-written and drifts, and a title token is free text at one remove.
`derive_check` reads the token once, at consolidation, from a closed registry,
so the persisted record carries a field a query can group on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import control_checks  # noqa: E402
from lib import evidence  # noqa: E402


class TestDeriveCheck:
    @pytest.mark.parametrize("title, slug", [
        # The issue's three acceptance titles: capitalisation, a leading
        # filename, and a dropped colon are each a miss for a naive startswith.
        ("Scope-Trace: x", "scope-trace"),
        ("foo.py: cross-component-contract — y", "cross-component-contract"),
        ("rule-unenforced x", "rule-unenforced"),
        ("read-cost: a per-request read walks the whole store", "read-cost"),
        # Leading markup a reviewer adds around the token.
        ("`rule-unenforced:` stale counts have no check", "rule-unenforced"),
        ("plugin/lib/x.py:12: read-cost: walks the dir", "read-cost"),
    ])
    def test_a_token_at_the_lead_derives_its_slug(self, title, slug):
        assert control_checks.derive_check(title) == slug

    def test_a_title_with_no_token_derives_nothing(self):
        assert control_checks.derive_check("Off-by-one in the span walk") is None
        assert control_checks.derive_check("") is None
        assert control_checks.derive_check(None) is None

    @pytest.mark.parametrize("title", [
        # Real titles from this clone's evidence store (2026-11-18): each NAMES
        # a control while reporting a defect ABOUT it, which is not a firing of
        # it. Matching anywhere in the title counts all of them — 8 of the 172
        # token-bearing titles in the store, and exactly the class a retire
        # numerator was already found polluted by. So the token is read at the
        # title's lead, after an optional file prefix, and nowhere else.
        "The cross-component-contract stopping rule's denominator is not "
        "derivable from the store its numerator lives in",
        "The scope-trace: retire rule's numerator is already polluted",
        "change-log states the scope-trace: retire denominator as `cumulative` only",
        "Framework Check 8: the PR scope-trace bullet does not disambiguate which "
        "`summary` to open",
        "the `rule-unenforced:` token is instructed into a field a Critic finding "
        "does not have",
    ])
    def test_a_title_about_a_control_is_not_a_firing_of_it(self, title):
        assert control_checks.derive_check(title) is None

    def test_a_longer_hyphenated_word_is_not_the_slug(self):
        # A word boundary that admits a hyphen would read `scope-trace-ish` as
        # `scope-trace`.
        assert control_checks.derive_check("scope-trace-ish: x") is None
        assert control_checks.derive_check("read-costs: x") is None

    def test_the_registry_is_closed_and_canonical(self):
        assert control_checks.KNOWN_CHECKS == (
            "cross-component-contract", "scope-trace", "rule-unenforced", "read-cost",
        )
        for slug in control_checks.KNOWN_CHECKS:
            assert control_checks.derive_check(f"{slug.upper()}: x") == slug


class TestTheFieldIsAdditive:
    def test_the_evidence_schema_version_does_not_move(self):
        """Pinned absolute, not relative: readers already ignore unknown finding
        keys, so an additive `check` is no reason to bump the store's schema —
        and a bump would refuse every older reader's store."""
        assert evidence.SCHEMA_VERSION == 1
