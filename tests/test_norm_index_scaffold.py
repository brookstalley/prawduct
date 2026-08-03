"""#570 — the template fix that never reached already-onboarded repos.

`#567`'s blocking finding was closed by shipping the norm-index table empty.
`init_product` and `core.write_template` skip existing destinations, so that
reaches new onboards only and every already-onboarded repo keeps the two
illustrative rows — which read as homed norms and nudge the repo about a Norm
Health sweep it owes nothing to. This is the detect-and-repair for the
installed base, on the Health-Check-#13 pattern.

The pin that matters most is `test_the_shipped_template_reads_ok`: it reads the
REAL template through `core.TEMPLATES_DIR`, so the detector and the artifact are
tested against each other rather than each against a fixture I wrote. That rule
was paid for in `#567`, where two hand-written over-fire fixtures both passed
while the shipped file said otherwise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import core, norm_index_scaffold as nis

# The rows verbatim, spelled out here rather than imported from the module —
# importing them would make this suite agree with the module by construction
# and prove nothing about whether either matches what prawduct actually shipped.
# `test_scaffold_rows_match_the_shipped_history` closes that loop against git.
_ROW_ORDINARY = (
    "| *(a code-level convention)* | Test | `tests/preferences/test_*.py` | janitor | "
    "*(the constraint's rationale)* |"
)
_ROW_POINTER = (
    "| norm lives in `observability-strategy.md` § Direction | Critic | — | advisory | "
    "*(pointer row — the why lives in the Direction entry)* |"
)

_HEADER = (
    "# Project Preferences\n\n## Enforcement\n\n"
    "| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |\n"
    "|---|---|---|---|---|\n"
)


def _write_prefs(root: Path, body: str) -> Path:
    d = root / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "project-preferences.md"
    path.write_text(body, encoding="utf-8")
    return path


class TestCheck:
    def test_leftover_scaffold_rows_are_found_with_their_line_numbers(self, tmp_path):
        _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n" + _ROW_POINTER + "\n")
        out = nis.check(tmp_path)
        assert out["status"] == nis.STATUS_LEFTOVER
        assert out["rows"] == [7, 8], "name the lines, don't send the owner looking"
        assert "Norm Health sweep" in out["detail"], (
            "the report must say what the leftover rows COST, not just that "
            "they exist — a finding with no consequence gets ignored"
        )

    def test_an_authored_row_is_not_a_scaffold_row(self, tmp_path):
        """The over-fire case. A real norm must never be deleted.

        Detection is exact-match on what prawduct shipped, so a row that merely
        *looks* like a placeholder — italics, parentheses — is untouched. That
        is the whole reason for exact-match over sniffing.
        """
        authored = (
            "| naming | Critic | reviewer reads the diff | janitor | "
            "*(kept italic on purpose)* |"
        )
        _write_prefs(tmp_path, _HEADER + authored + "\n")
        assert nis.check(tmp_path)["status"] == nis.STATUS_OK

    def test_a_scaffold_row_edited_by_a_human_is_theirs(self, tmp_path):
        # One cell changed → no longer the row we shipped → hands off.
        edited = _ROW_ORDINARY.replace("janitor", "advisory")
        _write_prefs(tmp_path, _HEADER + edited + "\n")
        assert nis.check(tmp_path)["status"] == nis.STATUS_OK

    def test_trailing_whitespace_does_not_hide_a_scaffold_row(self, tmp_path):
        _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "   \n")
        assert nis.check(tmp_path)["status"] == nis.STATUS_LEFTOVER

    def test_empty_table_reads_ok(self, tmp_path):
        _write_prefs(tmp_path, _HEADER)
        assert nis.check(tmp_path)["status"] == nis.STATUS_OK

    def test_missing_file_is_absent_not_ok(self, tmp_path):
        assert nis.check(tmp_path)["status"] == nis.STATUS_ABSENT

    def test_undecodable_file_is_ungraded_not_passed(self, tmp_path):
        """A check that could not run must never report as one that found nothing."""
        d = tmp_path / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_bytes(b"\xff\xfe not utf-8 \xff")
        out = nis.check(tmp_path)
        assert out["status"] == nis.STATUS_UNREADABLE
        assert out["status"] != nis.STATUS_OK

    def test_the_shipped_template_reads_ok(self):
        """Detector and artifact pinned against each other, not against a fixture.

        If the template ever ships illustrative rows again, this goes red — the
        exact failure mode `#567` produced, where two hand-written fixtures
        both passed while the real file said otherwise.
        """
        template = (core.TEMPLATES_DIR / "project-preferences.md").read_text(
            encoding="utf-8"
        )
        assert nis._scaffold_line_numbers(template) == [], (
            "the shipped template must carry no scaffold rows"
        )

    def test_scaffold_rows_match_the_shipped_history(self):
        """The constants are what prawduct really shipped, not what I recall.

        Guards the one assumption exact-matching rests on: get a byte wrong and
        the detector silently finds nothing, in every repo, forever — the
        quietest possible failure and exactly this branch's subject.
        """
        import subprocess

        repo = Path(__file__).resolve().parent.parent
        shipped = subprocess.run(
            ["git", "show", "3bfd4bf~1:plugin/templates/project-preferences.md"],
            cwd=str(repo), capture_output=True, text=True,
        )
        if shipped.returncode != 0:
            pytest.skip("shallow clone — the pre-fix template revision is unavailable")
        lines = {line.rstrip() for line in shipped.stdout.splitlines()}
        for row in nis.SCAFFOLD_ROWS:
            assert row.rstrip() in lines, (
                f"SCAFFOLD_ROWS carries a row the template never shipped: {row[:60]}"
            )


class TestRepair:
    def test_dry_run_reports_but_writes_nothing(self, tmp_path):
        path = _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n" + _ROW_POINTER + "\n")
        before = path.read_bytes()
        out = nis.repair(tmp_path, apply=False)
        assert out["applied"] is False
        assert out["removed"] == 2
        assert "`--apply` would delete" in out["detail"]
        assert path.read_bytes() == before, "a dry run must not touch the file"

    def test_apply_removes_only_the_scaffold_rows(self, tmp_path):
        authored = "| naming | Critic | reviewer reads the diff | janitor | consistency |"
        path = _write_prefs(
            tmp_path,
            _HEADER + _ROW_ORDINARY + "\n" + authored + "\n" + _ROW_POINTER + "\n"
            + "\nTrailing prose stays.\n",
        )
        out = nis.repair(tmp_path, apply=True)
        assert out["applied"] is True and out["removed"] == 2
        after = path.read_text(encoding="utf-8")
        assert authored in after, "an authored norm row must survive"
        assert "Trailing prose stays." in after
        assert _ROW_ORDINARY not in after and _ROW_POINTER not in after
        assert nis.check(tmp_path)["status"] == nis.STATUS_OK

    def test_apply_preserves_crlf_line_endings(self, tmp_path):
        """A product's authored file must not be silently re-line-ended."""
        body = (_HEADER + _ROW_ORDINARY + "\n" + "| a | b | c | d | e |\n").replace(
            "\n", "\r\n"
        )
        path = _write_prefs(tmp_path, body)
        nis.repair(tmp_path, apply=True)
        raw = path.read_bytes()
        assert b"\r\n" in raw, "CRLF must survive the repair"
        # Every LF must be part of a CRLF: strip the pairs and none may remain.
        assert b"\n" not in raw.replace(b"\r\n", b""), (
            "a bare LF was introduced — the file's line endings were rewritten"
        )

    def test_repair_is_a_noop_when_nothing_is_leftover(self, tmp_path):
        path = _write_prefs(tmp_path, _HEADER)
        before = path.read_bytes()
        out = nis.repair(tmp_path, apply=True)
        assert out["applied"] is False and out["removed"] == 0
        assert path.read_bytes() == before

    def test_repair_declines_on_an_undecodable_file(self, tmp_path):
        d = tmp_path / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_bytes(b"\xff\xfe \xff")
        out = nis.repair(tmp_path, apply=True)
        assert out["status"] == nis.STATUS_UNREADABLE
        assert out["applied"] is False
