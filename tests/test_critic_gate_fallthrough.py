"""Pins which build-plan `Type:` values skip the Stop-hook Critic gate.

The carveout is deliberately a single value: `Type: designer-handoff` (v1.4 F6).
Every other declared Type — `code`, `doc-only`, `cleanup`, `cumulative-final` —
falls through to the *default* gate path, so the Critic gate still fires when
code changed against an active plan with no findings.

Today the only behavioral coverage of the carveout is the implicit
`Type: code` default path. There is no test pinning that the *non-handoff*
Types do NOT join the skip-list. A refactor that broadened the branch — e.g.
`if chunk_type in {"designer-handoff", "doc-only"}:` — would silently regress:
a `doc-only`-typed code chunk would stop being reviewed. `TestNonHandoffTypes\
FallThroughToGate` is the regression guard (verified to FAIL under exactly that
broadening). `TestDesignerHandoffSkipsCriticGate` is its contrast partner —
the one value that legitimately skips — so the pair reads as a complete
truth-table for the carveout (Tests Are Contracts).

Harness mirrors `test_plugin_runtime.py::TestPluginStopGate` — subprocess
invocation of `bin/prawduct-hook stop` with a mock git on PATH — because the
gate decision is only observable end-to-end (the Type parse, the empirical
doc-only check, and the findings-freshness check all compose inside `cmd_stop`).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"

# The empirical diff is a non-`.md` code file. This keeps the gate's *other*
# carveout — `_session_changes_are_doc_only` (an all-`.md` diff) — False, so the
# only thing that could skip the gate is the Type -> designer_handoff_skip
# branch. That isolation is the whole point: we are pinning the Type field's
# effect, not the empirical doc-only shortcut.
_CODE_DIFF = " M src/app.py"


def _write_mock_git(mock_bin: Path, *, status: str, branch: str = "main") -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    status_file = mock_bin / "_status"
    status_file.write_text(status)
    git = mock_bin / "git"
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "deadbeefdeadbeef"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        'if [[ "$1" == "status" ]]; then cat "%s"; exit 0; fi\n'
        'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "worktree" ]]; then exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n" % (status_file, branch)
    )
    git.chmod(0o755)
    gh = mock_bin / "gh"
    gh.write_text("#!/bin/bash\necho '[]'\nexit 0\n")
    gh.chmod(0o755)


def _run_stop(project_dir: Path, *, status: str) -> subprocess.CompletedProcess:
    """Invoke `bin/prawduct-hook stop` as Claude Code would, with a mock git on
    PATH and the plugin/project roots wired. mock_bin + HOME live OUTSIDE
    project_dir so nothing per-user lands under the fixture."""
    mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin, status=status)
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "stop"],
        capture_output=True, text=True, env=env, timeout=20,
    )


def _active_plan_repo(tmp_path: Path, *, chunk_type: str) -> Path:
    """An active-build-plan fixture whose single current chunk declares
    `**Type:** <chunk_type>`. Reflection is pre-satisfied so the *only* gate in
    play is the Critic gate — a non-CRITIC block (e.g. reflection) would be a
    confounder. No `.critic-findings.json` is written: the gate fires unless the
    Type carves it out."""
    prawduct = tmp_path / ".prawduct"
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(
        "# Build Plan\n\n"
        "## Status\n- [ ] Chunk 01: Demo\n\n"
        f"### Chunk 01: Demo\n**Type:** {chunk_type}\n\nBody.\n"
    )
    (prawduct / ".session-reflected").write_text(
        "Session reflection: implemented the chunk and verified all tests pass cleanly."
    )
    (prawduct / ".session-git-baseline").write_text("")
    ts = datetime.now(timezone.utc) - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return prawduct


# The four Types that are NOT carveouts. `code` is the fail-closed default but is
# pinned explicitly here so the truth-table is complete and a future default
# change can't quietly drop it from coverage.
_NON_HANDOFF_TYPES = ["code", "doc-only", "cleanup", "cumulative-final"]


class TestNonHandoffTypesFallThroughToGate:
    """Regression guard: only `designer-handoff` skips the gate. Each of the
    four non-handoff Types must STILL trip the Critic gate (exit 2, CRITIC
    block) when code changed against an active plan with no findings. Broaden
    the skip-list to include any of these and the corresponding case fails."""

    @pytest.mark.parametrize("chunk_type", _NON_HANDOFF_TYPES)
    def test_gate_fires_for_non_handoff_type(self, tmp_path, chunk_type):
        _active_plan_repo(tmp_path, chunk_type=chunk_type)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2, (
            f"Type: {chunk_type} must NOT skip the Critic gate — only "
            f"designer-handoff does. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC" in result.stderr, (
            f"Type: {chunk_type} must produce the Critic block (the gate that "
            f"fired), not some other gate. stderr={result.stderr!r}"
        )

    @pytest.mark.parametrize("chunk_type", _NON_HANDOFF_TYPES)
    def test_non_handoff_type_does_not_emit_handoff_skip_note(self, tmp_path, chunk_type):
        # The skip branch also appends a "critic: skipped (… designer-handoff …)"
        # waiver note. A non-handoff Type must never emit it — guards against a
        # refactor that flips the skip flag while leaving the exit code coincidentally
        # at 2 for an unrelated reason.
        _active_plan_repo(tmp_path, chunk_type=chunk_type)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert "designer-handoff" not in result.stdout, (
            f"Type: {chunk_type} must not trigger the designer-handoff skip note. "
            f"stdout={result.stdout!r}"
        )


class TestDesignerHandoffSkipsCriticGate:
    """Contrast partner: the one Type that legitimately skips. Same fixture,
    same code diff — only the declared Type differs — so the pair isolates the
    Type field as the sole cause of the divergent gate decision."""

    def test_designer_handoff_skips_the_gate(self, tmp_path):
        _active_plan_repo(tmp_path, chunk_type="designer-handoff")
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 0, (
            "Type: designer-handoff must skip the Critic gate (v1.4 F6 carveout). "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CRITIC REVIEW" not in result.stderr, (
            f"the Critic block must be absent when skipped. stderr={result.stderr!r}"
        )
