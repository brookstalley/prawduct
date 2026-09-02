"""Tests for lib/waivers.py — the intentional-waiver pragma recognizer.

Covers parsing (general + legacy forms), scope-matching (no cross-waiving),
language-agnostic comment leaders, the mandatory-reason rule, and line-above
placement. Spec: docs/waivers.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import compliance  # noqa: E402 — canary checks now live in lib/compliance (STH-9V4K ch.4)
from lib import waivers  # noqa: E402
from lib.waivers import Waiver  # noqa: E402


class TestParseGeneral:
    def test_single_ref_and_reason(self):
        line = "    except Exception:  # prawduct:allow prawduct/broad-except -- boundary; logs + re-raises"
        (w,) = waivers.parse_waivers(line)
        assert w.scope == "prawduct"
        assert w.rule_id == "broad-except"
        assert w.ref == "prawduct/broad-except"
        assert w.reason == "boundary; logs + re-raises"
        assert w.has_reason

    def test_em_dash_separator_accepted(self):
        line = "x  # prawduct:allow prawduct/legacy-ref — kept for 1.x migration"
        (w,) = waivers.parse_waivers(line)
        assert w.ref == "prawduct/legacy-ref"
        assert w.reason == "kept for 1.x migration"

    def test_project_scope(self):
        line = "-- prawduct:allow project/full-table-scan -- nightly job, < 10k rows"
        (w,) = waivers.parse_waivers(line)
        assert w.scope == "project"
        assert w.rule_id == "full-table-scan"

    def test_multiple_comma_separated_refs_share_reason(self):
        line = "x  // prawduct:allow prawduct/broad-except,project/no-log -- top-level pump"
        ws = waivers.parse_waivers(line)
        assert {w.ref for w in ws} == {"prawduct/broad-except", "project/no-log"}
        assert all(w.reason == "top-level pump" for w in ws)

    def test_no_waiver_returns_empty(self):
        assert waivers.parse_waivers("just a normal line of code") == []


class TestLegacyForm:
    def test_legacy_maps_to_broad_except(self):
        line = "    except Exception:  # prawduct:ok-broad-except — git failure must not crash hook"
        (w,) = waivers.parse_waivers(line)
        assert w.ref == "prawduct/broad-except"
        assert w.reason == "git failure must not crash hook"

    def test_legacy_waives_broad_except(self):
        line = "except Exception:  # prawduct:ok-broad-except — reason here"
        assert waivers.line_waives(line, "prawduct/broad-except")

    def test_general_and_legacy_do_not_double_count(self):
        # The general keyword is `prawduct:allow`; the legacy token is distinct,
        # so a migrated line yields exactly one waiver, not two.
        line = "x  # prawduct:allow prawduct/broad-except -- reason"
        assert len(waivers.parse_waivers(line)) == 1

    def test_legacy_keyword_not_matched_as_word_prefix(self):
        # `prawduct:ok-broad-exception` must NOT false-match the legacy keyword.
        line = "x  # prawduct:ok-broad-exception is not a waiver"
        assert waivers.parse_waivers(line) == []
        assert not waivers.line_waives(line, "prawduct/broad-except")

    def test_legacy_separator_adjacent_still_parses(self):
        # A reason butted directly against `--` (no space) still parses.
        line = "except Exception:  # prawduct:ok-broad-except--boundary"
        (w,) = waivers.parse_waivers(line)
        assert w.ref == "prawduct/broad-except" and w.reason == "boundary"


class TestScopeMatching:
    def test_matching_ref_waives(self):
        line = "x  # prawduct:allow prawduct/broad-except -- reason"
        assert waivers.line_waives(line, "prawduct/broad-except")

    def test_non_matching_ref_does_not_waive(self):
        line = "x  # prawduct:allow prawduct/duplication -- reason"
        assert not waivers.line_waives(line, "prawduct/broad-except")

    def test_project_waiver_does_not_waive_prawduct_check(self):
        # The cross-waiving guard: a project-scope waiver must not silence a
        # framework check, and vice-versa.
        line = "x  # prawduct:allow project/broad-except -- reason"
        assert not waivers.line_waives(line, "prawduct/broad-except")

    def test_malformed_scopeless_ref_does_not_match(self):
        # No slash => not a well-formed ref => underlying finding resurfaces.
        line = "x  # prawduct:allow broad-except -- reason"
        assert waivers.parse_waivers(line) == []
        assert not waivers.line_waives(line, "prawduct/broad-except")


class TestLanguageAgnostic:
    """The recognizer keys on the token, not the comment syntax."""

    def test_comment_leaders(self):
        for leader in ("#", "//", "--", ";", "%", "<!--", "/*"):
            line = f"code {leader} prawduct:allow prawduct/broad-except -- reason"
            assert waivers.line_waives(line, "prawduct/broad-except"), leader


class TestReasonRequired:
    def test_reasonless_waiver_does_not_waive(self):
        line = "except Exception:  # prawduct:allow prawduct/broad-except"
        assert not waivers.line_waives(line, "prawduct/broad-except")

    def test_bare_separator_is_reasonless(self):
        line = "except Exception:  # prawduct:allow prawduct/broad-except --"
        assert not waivers.line_waives(line, "prawduct/broad-except")

    def test_an_html_comment_terminator_is_not_a_reason(self):
        """A waiver in a markdown file must live inside `<!-- ... -->`, and the
        closing token parses as the `--` separator followed by a reason of `>`.
        Left alone, every bare pragma in markdown would satisfy the reason
        requirement — the requirement's whole point being that an unexplained
        exemption is itself a finding."""
        bare = "<!-- prawduct:allow prawduct/chunk-ref-missing -->"
        assert not waivers.line_waives(bare, "prawduct/chunk-ref-missing")
        assert [w.ref for w in waivers.invalid_waivers([bare])] == [
            "prawduct/chunk-ref-missing"
        ]

    def test_a_real_reason_survives_the_terminator_strip(self):
        """The paired positive: stripping `-->` must not eat the reason with it."""
        line = "<!-- prawduct:allow prawduct/chunk-ref-missing -- names a dead path -->"
        assert waivers.line_waives(line, "prawduct/chunk-ref-missing")
        assert waivers.parse_waivers(line)[0].reason == "names a dead path"

    def test_prose_after_a_closed_comment_is_not_a_reason(self):
        """The comment ENDS at `-->`; text after it is ordinary document prose
        and cannot supply the justification.

        An end-of-line-only strip leaves exactly this hole — the reason comes
        back as `"> and then some prose"`, which is non-empty, so a bare pragma
        waives after all. The guard has to truncate at the token, not trim it
        off the end.
        """
        line = "<!-- prawduct:allow prawduct/chunk-ref-missing --> and then some prose"
        assert not waivers.line_waives(line, "prawduct/chunk-ref-missing")

    def test_a_reason_inside_the_comment_still_wins_with_prose_after_it(self):
        """Paired positive for the truncation: a real reason before the
        terminator survives, and the prose after it is simply not part of it."""
        line = (
            "<!-- prawduct:allow prawduct/chunk-ref-missing -- the absence is the "
            "point --> and then some prose"
        )
        assert waivers.line_waives(line, "prawduct/chunk-ref-missing")
        assert waivers.parse_waivers(line)[0].reason == "the absence is the point"

    def test_invalid_waivers_collects_reasonless(self):
        lines = [
            "ok  # prawduct:allow prawduct/broad-except -- has reason",
            "bad  # prawduct:allow prawduct/legacy-ref",
        ]
        bad = waivers.invalid_waivers(lines)
        assert [w.ref for w in bad] == ["prawduct/legacy-ref"]

    def test_invalid_waivers_empty_when_all_have_reasons(self):
        lines = ["x  # prawduct:allow prawduct/broad-except -- r"]
        assert waivers.invalid_waivers(lines) == []


class TestPlacement:
    def test_trailing_on_same_line(self):
        lines = ["except Exception:  # prawduct:allow prawduct/broad-except -- r"]
        assert waivers.waives(lines, 0, "prawduct/broad-except")

    def test_leading_line_above(self):
        lines = [
            "# prawduct:allow prawduct/broad-except -- reason on its own line",
            "except Exception:",
        ]
        assert waivers.waives(lines, 1, "prawduct/broad-except")

    def test_two_lines_below_does_not_waive(self):
        lines = [
            "# prawduct:allow prawduct/broad-except -- reason",
            "intervening = 1",
            "except Exception:",
        ]
        assert not waivers.waives(lines, 2, "prawduct/broad-except")

    def test_index_out_of_range_is_false(self):
        assert not waivers.waives([], 0, "prawduct/broad-except")
        assert not waivers.waives(["x"], 5, "prawduct/broad-except")


class TestWaiverValueObject:
    def test_ref_and_has_reason(self):
        w = Waiver(scope="prawduct", rule_id="duplication", reason="parity-tested mirror", line="x")
        assert w.ref == "prawduct/duplication"
        assert w.has_reason

    def test_empty_reason_has_no_reason(self):
        w = Waiver(scope="prawduct", rule_id="broad-except", reason="", line="x")
        assert not w.has_reason


class TestCanaryWiring:
    """The compliance canary consumes the shared recognizer, honoring both the
    general and legacy spellings and flagging reason-less waivers."""

    def _write(self, tmp_path: Path, body: str) -> Path:
        f = tmp_path / "mod.py"
        f.write_text(body)
        return f

    def test_unwaived_broad_except_is_flagged(self, tmp_path: Path):
        self._write(tmp_path, "def f():\n    try:\n        g()\n    except Exception:\n        pass\n")
        assert compliance._check_broad_exceptions(tmp_path, ["mod.py"]) == ["mod.py"]

    def test_general_form_waiver_suppresses(self, tmp_path: Path):
        self._write(
            tmp_path,
            "def f():\n    try:\n        g()\n"
            "    except Exception:  # prawduct:allow prawduct/broad-except -- boundary\n        pass\n",
        )
        assert compliance._check_broad_exceptions(tmp_path, ["mod.py"]) == []

    def test_legacy_form_waiver_still_suppresses(self, tmp_path: Path):
        self._write(
            tmp_path,
            "def f():\n    try:\n        g()\n"
            "    except Exception:  # prawduct:ok-broad-except — boundary\n        pass\n",
        )
        assert compliance._check_broad_exceptions(tmp_path, ["mod.py"]) == []

    def test_reasonless_waiver_is_flagged_by_invalid_check(self, tmp_path: Path):
        self._write(
            tmp_path,
            "def f():\n    try:\n        g()\n"
            "    except Exception:  # prawduct:allow prawduct/broad-except\n        pass\n",
        )
        assert compliance._check_invalid_waivers(tmp_path, ["mod.py"]) == ["mod.py"]

    def test_valid_waiver_not_flagged_by_invalid_check(self, tmp_path: Path):
        self._write(
            tmp_path,
            "x = 1  # prawduct:allow prawduct/legacy-ref -- required for 1.x migration\n",
        )
        assert compliance._check_invalid_waivers(tmp_path, ["mod.py"]) == []
