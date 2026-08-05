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
        # A shallow clone answers every content search with "never shipped",
        # which this test would otherwise report as a wrong row — a confident
        # accusation against the code when the truth is a truncated checkout.
        # Measured on the first CI run: `actions/checkout` defaults to depth 1.
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=str(repo), capture_output=True, text=True,
        )
        if shallow.stdout.strip() == "true":
            pytest.fail(
                "this pin searches history by content and the checkout is "
                "shallow, so it cannot run — fetch full history (CI: "
                "`fetch-depth: 0`) rather than reading this as a wrong row"
            )
        # Searched by CONTENT across all history rather than pinned to a
        # branch-local SHA. The first cut named `3bfd4bf~1`, which stops
        # resolving the moment this branch is squashed or rebased — and it
        # degraded to `pytest.skip`, so the pin would have gone SILENT exactly
        # when it stopped working. A pin that disappears quietly is the defect
        # this whole scope is named after.
        for row in nis.SCAFFOLD_ROWS:
            found = subprocess.run(
                ["git", "log", "--all", "-S", row.rstrip(), "--oneline",
                 "--", "plugin/templates/project-preferences.md"],
                cwd=str(repo), capture_output=True, text=True,
            )
            if found.returncode != 0:
                pytest.fail(
                    "git history is unavailable, so this pin cannot run — "
                    "reported rather than skipped, because a silently skipped "
                    f"pin is indistinguishable from a passing one. {found.stderr}"
                )
            assert found.stdout.strip(), (
                "SCAFFOLD_ROWS carries a row the template never shipped — the "
                "detector is exact-match, so one wrong byte makes it find "
                f"nothing in every repo forever: {row[:60]}"
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

    def test_a_failed_write_returns_a_status_instead_of_raising(self, tmp_path, monkeypatch):
        """The failure policy `atomic_write_text` requires each caller to own.

        That helper propagates `OSError` by design. Doctor Health Check #14
        RELAYS this result, so a traceback escaping here crashes the health
        check rather than degrading it to a finding — fail-soft inverted at a
        fail-soft site.

        This test exists because the policy shipped with none: the module cites
        `learnings_obligation` as its precedent, and that precedent's test file
        monkeypatches the writer to raise. Following a precedent's *code* while
        skipping its *tests* is how ~50 untested lines got here once already in
        this same chunk.
        """
        _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n")

        def _boom(*args, **kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(nis.core, "atomic_write_text", _boom)
        out = nis.repair(tmp_path, apply=True)
        assert out["status"] == nis.STATUS_UNWRITABLE, (
            "a write failure is not a read failure — one status meaning both "
            "leaves doctor #14 and the api-contract describing only the first"
        )
        assert out["applied"] is False and out["removed"] == 0
        assert "nothing was changed" in out["detail"]

    def test_write_failure_and_read_failure_are_different_statuses(self, tmp_path):
        d = tmp_path / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_bytes(b"\xff\xfe \xff")
        assert nis.repair(tmp_path, apply=True)["status"] == nis.STATUS_UNREADABLE
        assert nis.STATUS_UNREADABLE != nis.STATUS_UNWRITABLE

    def test_repair_declines_on_an_undecodable_file(self, tmp_path):
        d = tmp_path / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_bytes(b"\xff\xfe \xff")
        out = nis.repair(tmp_path, apply=True)
        assert out["status"] == nis.STATUS_UNREADABLE
        assert out["applied"] is False


# =============================================================================
# the subcommand — the binary is a named deliverable, so it gets driven
# =============================================================================

import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


def _run(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "norm-index-scaffold", *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


class TestCommand:
    """The chunk names `plugin/bin/prawduct-hook` as a deliverable, so the
    command is driven rather than only its lib.

    The first cut tested the lib alone and left ~50 lines — both exit-code
    mappings, the confirmation block, `--json`, unknown-arg rejection and the
    dispatch arm — executing in no test at all, against the very pattern this
    chunk models itself on (`test_learnings_obligation.py::TestCommand`).
    """

    def test_dry_run_reports_the_finding_and_exits_zero(self, tmp_path):
        # An advisory report: a finding is not a failure state.
        path = _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n")
        before = path.read_bytes()
        result = _run(tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == nis.STATUS_LEFTOVER
        assert data["applied"] is False
        assert path.read_bytes() == before, "a dry run must not touch the file"

    def test_the_human_dry_run_names_the_rows_it_would_delete(self, tmp_path):
        # `--json`-only tests never execute the formatter, and this formatter IS
        # the informed confirmation required before editing a file the framework
        # did not author.
        _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n" + _ROW_POINTER + "\n")
        result = _run(tmp_path)
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert "Would delete from" in result.stdout
        assert "line 7" in result.stdout and "line 8" in result.stdout

    def test_apply_writes_and_exits_zero(self, tmp_path):
        path = _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n")
        result = _run(tmp_path, "--apply", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["applied"] is True and data["removed"] == 1
        assert _ROW_ORDINARY not in path.read_text(encoding="utf-8")

    def test_apply_on_a_clean_repo_is_an_idempotent_zero(self, tmp_path):
        _write_prefs(tmp_path, _HEADER)
        result = _run(tmp_path, "--apply")
        assert result.returncode == 0, "an idempotent no-op is not a failure"
        assert "apply" in result.stdout and nis.STATUS_OK in result.stdout

    def test_absent_preferences_exits_zero(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        result = _run(tmp_path)
        assert result.returncode == 0
        assert nis.STATUS_ABSENT in result.stdout

    def test_undecodable_exits_one_because_it_could_not_run(self, tmp_path):
        d = tmp_path / ".prawduct" / "artifacts"
        d.mkdir(parents=True)
        (d / "project-preferences.md").write_bytes(b"\xff\xfe \xff")
        result = _run(tmp_path)
        assert result.returncode == 1, (
            "could-not-run is exit 1; reporting 0 would make a declined check "
            "indistinguishable from one that ran and found nothing"
        )
        assert nis.STATUS_UNREADABLE in result.stdout

    def test_apply_that_cannot_write_exits_one(self, tmp_path):
        """`--apply` is a state-mutating writer: refused means exit 1.

        R-1 asked for both exit-code mappings and this half was skipped — the
        same "ported the precedent's code, not its cases" gap the round was
        about. Made unwritable by taking the directory's write permission,
        which is the real shape of the failure rather than a monkeypatch.
        """
        import os
        import stat

        d = tmp_path / ".prawduct" / "artifacts"
        path = _write_prefs(tmp_path, _HEADER + _ROW_ORDINARY + "\n")
        before = path.read_bytes()
        mode = d.stat().st_mode
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)  # r-x: cannot create the tmp sibling
        try:
            result = _run(tmp_path, "--apply", "--json")
        finally:
            os.chmod(d, mode)
        assert result.returncode == 1, (
            "a write that did not happen must not report success"
        )
        assert nis.STATUS_UNWRITABLE in result.stdout
        assert path.read_bytes() == before, "and it must have changed nothing"

    def test_unknown_flag_is_a_usage_error(self, tmp_path):
        _write_prefs(tmp_path, _HEADER)
        result = _run(tmp_path, "--delete-everything")
        assert result.returncode == 2, "usage errors are 2 per the error model"
