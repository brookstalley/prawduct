"""Tests for lib/backlog/issuefmt.py — the issue-structure standard.

Covers §1 title normalization, §2 body composition (the shared composer reused by
migration), and the §4 WARN-only linter. Pure/deterministic — no transport, no
model (INV-1).
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.backlog import issuefmt  # noqa: E402


def _rules(findings):
    return {f.rule for f in findings}


class TestNormalizeTitle:
    def test_prepends_area_prefix(self):
        assert issuefmt.normalize_title("thing broke", "importer") == "importer: thing broke"

    def test_idempotent_when_already_prefixed_with_area(self):
        assert issuefmt.normalize_title("importer: thing broke", "importer") == "importer: thing broke"

    def test_respects_a_different_existing_prefix(self):
        # Never fights an author-chosen prefix, even a different one.
        assert issuefmt.normalize_title("cli: thing broke", "importer") == "cli: thing broke"

    def test_no_area_returns_trimmed_title(self):
        assert issuefmt.normalize_title("  thing broke  ", None) == "thing broke"

    def test_does_not_double_prefix_uppercase_existing(self):
        # An author's uppercase prefix still counts as a prefix (R-3 regression).
        assert issuefmt.normalize_title("CLI: thing broke", "cli") == "CLI: thing broke"

    def test_blank_area_is_noop(self):
        assert issuefmt.normalize_title("thing broke", "   ") == "thing broke"

    def test_midsentence_colon_is_not_a_prefix(self):
        # A `word:` with no space, or a non-area colon, must not block prefixing.
        assert issuefmt.normalize_title("fix ratio 3:1 scaling", "cli") == "cli: fix ratio 3:1 scaling"


class TestRenderBody:
    def test_emits_sections_in_template_order(self):
        body = issuefmt.render_body(
            "bug",
            {"Expected": "it works", "Problem": "it broke", "Actual": "it errors"},
        )
        # Order follows the bug template (Problem before Actual before Expected),
        # not the dict's insertion order.
        assert body.index("### Problem") < body.index("### Actual") < body.index("### Expected")

    def test_skips_empty_sections(self):
        body = issuefmt.render_body("bug", {"Problem": "x", "Evidence": "   "})
        assert "### Problem" in body
        assert "### Evidence" not in body

    def test_matches_aliases_to_canonical_label(self):
        body = issuefmt.render_body("task", {"change": "do the thing"})
        assert "### Proposed change" in body
        assert "do the thing" in body

    def test_extra_sections_appended_not_dropped(self):
        body = issuefmt.render_body("bug", {"Problem": "x", "Notes": "keep me"})
        assert "### Notes" in body
        assert body.index("### Problem") < body.index("### Notes")

    def test_unknown_kind_still_renders_given_sections(self):
        body = issuefmt.render_body(None, {"Problem": "x"})
        assert "### Problem" in body


class TestLintTitle:
    def test_too_long(self):
        title = "area: " + "x" * 80
        assert "title-too-long" in _rules(issuefmt.lint(title, "", ["kind:bug", "area:a"]))

    def test_too_short(self):
        assert "title-too-short" in _rules(issuefmt.lint("cli: x", "", ["kind:bug", "area:cli"]))

    def test_placeholder(self):
        assert "title-placeholder" in _rules(issuefmt.lint("cli: fix", "", ["kind:bug", "area:cli"]))

    def test_placeholder_phrase(self):
        findings = issuefmt.lint("cli: bug in the thing", "", ["kind:bug", "area:cli"])
        assert "title-placeholder" in _rules(findings)

    def test_non_atomic_em_dash(self):
        title = "cli: parser drops flags — and the linter double-counts words"
        assert "title-non-atomic" in _rules(issuefmt.lint(title, "", ["kind:bug", "area:cli"]))

    def test_non_atomic_semicolon(self):
        title = "cli: parser drops flags; linter double-counts words"
        assert "title-non-atomic" in _rules(issuefmt.lint(title, "", ["kind:bug", "area:cli"]))

    def test_good_title_no_title_findings(self):
        title = "importer: PFX alias read-resolution unwired, breaks idempotency"
        findings = _rules(issuefmt.lint(title, "", ["kind:bug", "area:importer"]))
        assert not ({"title-too-long", "title-too-short", "title-placeholder", "title-non-atomic"} & findings)


class TestLintLabels:
    def test_no_kind(self):
        assert "no-kind" in _rules(issuefmt.lint("cli: something specific here", "", ["area:cli"]))

    def test_no_area(self):
        assert "no-area" in _rules(issuefmt.lint("cli: something specific here", "", ["kind:bug"]))

    def test_too_many_labels(self):
        labels = ["kind:bug", "area:cli", "stage:ready", "impact:high", "effort:m", "source:user", "extra:x"]
        assert "too-many-labels" in _rules(issuefmt.lint("cli: something specific here", "", labels))

    def test_six_labels_is_ok(self):
        labels = ["kind:bug", "area:cli", "stage:ready", "impact:high", "effort:m", "source:user"]
        assert "too-many-labels" not in _rules(issuefmt.lint("cli: something specific here", "", labels))


class TestLintBodySections:
    def test_missing_required_section(self):
        body = "### Problem\n\nit broke\n"
        findings = _rules(issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"]))
        assert "missing-section" in findings  # Repro/Actual/Expected/Evidence absent

    def test_empty_required_section(self):
        body = "### Problem\n\n### Actual\n\nerrors\n"
        findings = issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"])
        assert any(f.rule == "empty-section" and "Problem" in f.message for f in findings)

    def test_no_section_check_without_kind(self):
        # Can't know the template without a kind → no section findings.
        findings = _rules(issuefmt.lint("cli: something specific here", "### Problem\n\nx", ["area:cli"]))
        assert "missing-section" not in findings

    def test_acceptance_without_checkbox(self):
        body = (
            "### Problem\n\nx\n\n### Proposed change\n\ny\n\n"
            "### Acceptance\n\nit should work well\n\n### Scope-out\n\nz\n"
        )
        findings = _rules(issuefmt.lint("cli: something specific here", body, ["kind:task", "area:cli"]))
        assert "acceptance-no-checkbox" in findings

    def test_acceptance_with_checkbox_ok(self):
        body = (
            "### Problem\n\nx\n\n### Proposed change\n\ny\n\n"
            "### Acceptance\n\n- [ ] it works\n\n### Scope-out\n\nz\n"
        )
        findings = _rules(issuefmt.lint("cli: something specific here", body, ["kind:task", "area:cli"]))
        assert "acceptance-no-checkbox" not in findings

    def test_compliant_bug_lints_clean(self):
        title = "importer: alias read-resolution unwired breaks idempotency"
        body = issuefmt.render_body(
            "bug",
            {
                "Problem": "The importer never reads the id:PFX alias, so a re-import duplicates.",
                "Repro": "Run import twice against the same source.",
                "Actual": "Two issues per source item.",
                "Expected": "The second run skips existing items.",
                "Evidence": "migrate.py:120",
                "Env": "prawduct v3.1.0 (plugin)",  # §2: bugs carry the product version
            },
        )
        assert issuefmt.lint(title, body, ["kind:bug", "area:importer"]) == []

    def test_bug_without_env_nudges(self):
        # A bug that records no product version gets the WARN nudge (§2/§4).
        body = issuefmt.render_body(
            "bug",
            {"Problem": "x", "Repro": "y", "Actual": "z", "Expected": "w", "Evidence": "f.py:1"},
        )
        findings = _rules(issuefmt.lint("cli: a specific real bug here", body, ["kind:bug", "area:cli"]))
        assert "bug-missing-env" in findings

    def test_bug_with_env_no_nudge(self):
        body = issuefmt.render_body(
            "bug",
            {"Problem": "x", "Repro": "y", "Actual": "z", "Expected": "w",
             "Evidence": "f.py:1", "Env": "prawduct v3.1.0 (plugin)"},
        )
        findings = _rules(issuefmt.lint("cli: a specific real bug here", body, ["kind:bug", "area:cli"]))
        assert "bug-missing-env" not in findings

    def test_env_nudge_is_bug_only(self):
        # Env is a bug-provenance field; a task without Env is not nudged.
        body = issuefmt.render_body(
            "task",
            {"Problem": "x", "Proposed change": "y", "Acceptance": "- [ ] done", "Scope-out": "z"},
        )
        findings = _rules(issuefmt.lint("cli: a specific real task here", body, ["kind:task", "area:cli"]))
        assert "bug-missing-env" not in findings

    def test_env_nudge_tolerates_environment_spelling(self):
        # Alias-aware like the rest of the section contract: a bug that spells the
        # section "Environment" is not falsely nudged.
        body = (
            "### Problem\n\nx\n\n### Repro\n\ny\n\n### Actual\n\nz\n\n"
            "### Expected\n\nw\n\n### Evidence\n\nf.py:1\n\n### Environment\n\nprawduct v3.1.0\n"
        )
        findings = _rules(issuefmt.lint("cli: a specific real bug here", body, ["kind:bug", "area:cli"]))
        assert "bug-missing-env" not in findings


class TestLintBodyBudgets:
    def test_body_too_long(self):
        body = "### Problem\n\n" + " ".join(["word"] * 200)
        assert "body-too-long" in _rules(issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"]))

    def test_the_budget_is_the_reconciled_number_not_the_old_one(self):
        """The 200-word case above trips at 150 and at 175 alike, so it cannot
        tell the reconciled budget from the one BKL-7H2M retired. This one can:
        160 visible words is over the old 150 and under the current budget, so a
        revert to 150 turns this red. Pinned as a pair with the over-budget case
        below so the boundary is asserted from both sides rather than assumed."""
        assert issuefmt.BODY_MAX_WORDS == 175
        under = "### Problem\n\n" + " ".join(["word"] * 160)
        assert "body-too-long" not in _rules(
            issuefmt.lint("cli: something specific here", under, ["kind:bug", "area:cli"])
        )
        over = "### Problem\n\n" + " ".join(["word"] * 176)
        assert "body-too-long" in _rules(
            issuefmt.lint("cli: something specific here", over, ["kind:bug", "area:cli"])
        )

    def test_fenced_content_excluded_from_word_count(self):
        body = "### Problem\n\nshort prose\n\n```\n" + "\n".join(["log line here"] * 100) + "\n```\n"
        assert "body-too-long" not in _rules(
            issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"])
        )

    def test_unwrapped_evidence_run(self):
        body = "### Problem\n\n" + "\n".join([f"line {i}" for i in range(40)])
        assert "evidence-unwrapped" in _rules(
            issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"])
        )

    def test_wrapped_evidence_ok(self):
        body = "### Problem\n\nx\n\n```\n" + "\n".join([f"line {i}" for i in range(40)]) + "\n```\n"
        assert "evidence-unwrapped" not in _rules(
            issuefmt.lint("cli: something specific here", body, ["kind:bug", "area:cli"])
        )


class TestLintContract:
    def test_returns_findings_never_raises_on_empty(self):
        # Never blocks, never raises — even on degenerate input.
        assert isinstance(issuefmt.lint("", "", None), list)

    def test_findings_are_warn_severity(self):
        findings = issuefmt.lint("cli: fix", "", ["area:cli"])
        assert findings and all(f.severity == "warn" for f in findings)
