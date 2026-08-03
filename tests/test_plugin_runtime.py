"""Tests for the v2.0.0 plugin runtime: bin/prawduct-hook, lib/, hooks (Chunk 5).

The architectural keystone. These enforce the load-bearing invariants of the
ported runtime:

  * **Structure** — bin/prawduct-hook is an executable, parseable Python script
    with the sync cluster excised; hooks.json wires the briefing (clear) +
    Critic/reflection gate (stop) via ${CLAUDE_PLUGIN_ROOT}/bin/, and keeps the
    Chunk-1 banner.
  * **Behavioral** — invoked as a subprocess with CLAUDE_PLUGIN_ROOT +
    CLAUDE_PROJECT_DIR, the briefing renders, the Stop-hook Critic gate BLOCKS
    (exit 2) when code changed against an active plan with no findings, the
    lib-backed subcommands resolve, and NOTHING is written outside .prawduct/
    (the design §2 invariant).
  * **Gitflow base resolution** — the 2.0.0 ship-blocker fix: a configured
    base_branch (develop) drives resolve-base AND the PR gates' diff range, so a
    feature branch is reviewed against develop..HEAD, not the develop..main
    range; a repo with no base_branch is unchanged (main fallback).
"""
from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"

class TestPluginHookStructure:
    def test_hook_exists_and_executable(self):
        assert HOOK.is_file(), "bin/prawduct-hook must exist"
        assert os.access(HOOK, os.X_OK), (
            "bin/prawduct-hook must be executable — bin/ is on the Bash PATH and "
            "skills invoke it as bare `prawduct-hook`"
        )

    def test_hook_has_python_shebang(self):
        first = HOOK.read_text().splitlines()[0]
        assert first == "#!/usr/bin/env python3", first

    def test_hook_parses(self):
        ast.parse(HOOK.read_text())  # raises on syntax error

    def test_sync_cluster_excised(self):
        src = HOOK.read_text()
        for sym in ("def try_sync(", "def _check_framework_version(", "def _compute_framework_freshness("):
            assert sym not in src, (
                f"{sym!r} is sync-only machinery and must be excised from the "
                "plugin runtime (Chunk 5)"
            )
        assert "try_sync(" not in src, "cmd_clear must not call try_sync in the plugin runtime"
        # The sync entry-point script is never spawned by the plugin runtime.
        assert "prawduct-setup.py" not in src and "prawduct-sync.py" not in src

    def test_resolve_base_subcommand_wired(self):
        src = HOOK.read_text()
        assert 'command == "resolve-base"' in src
        assert "def cmd_resolve_base(" in src
        # _resolve_base_branch moved to lib/coverage (STH-9V4K ch.5); the hook's
        # cmd_resolve_base wrapper reaches it lazily via the _coverage() accessor.
        assert "_coverage()._resolve_base_branch(" in src
        assert "resolve-base" in src.split("_USAGE = (", 1)[1].split(")", 1)[0]

    def test_lib_imported_via_plugin_root(self):
        src = HOOK.read_text()
        assert "def _plugin_root(" in src
        assert "CLAUDE_PLUGIN_ROOT" in src
        # The legacy tools/-relative lib path must be gone from the import sites.
        assert "tools_dir = str(Path(__file__).resolve().parent)" not in src

    def test_hooks_json_wires_briefing_and_gate(self):
        data = json.loads(HOOKS_JSON.read_text())
        ss = data["hooks"]["SessionStart"]
        stop = data["hooks"]["Stop"]
        ss_cmds = [h["command"] for e in ss for h in e["hooks"]]
        stop_cmds = [h["command"] for e in stop for h in e["hooks"]]
        # Briefing (clear) wired via the bundled hook, by plugin root. The clear
        # command carries `--session-start` so the genuine SessionStart invocation
        # bypasses the critic-active session-mutation guard and sweeps any stale
        # marker (CRT-3X9D) — a bare reviewer-issued `clear` is the guarded path.
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "bin/prawduct-hook" in c and c.rstrip().endswith("clear --session-start")
            for c in ss_cmds
        ), "SessionStart must run the bundled prawduct-hook clear --session-start briefing"
        # Stop gate wired.
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "bin/prawduct-hook" in c and c.rstrip().endswith("stop")
            for c in stop_cmds
        ), "Stop must run the bundled prawduct-hook stop gate"
        # Chunk-1 banner is preserved.
        assert any("banner.py" in c for c in ss_cmds), "the version banner must stay wired"

    def test_state_reset_matcher_excludes_every_continuation(self):
        # Successor to test_clear_matcher_excludes_compact (SCN-5B8Q). The
        # invariant is unchanged — the state-reset hook must not fire on a
        # compaction — but `clear` now runs on TWO entries, and the continuation
        # one carries `--brief-only` (orientation, no reset). So identifying the
        # reset entry by the `clear` token alone no longer distinguishes them.
        #
        # The assertion is STRENGTHENED rather than relaxed: `resume` and `fork`
        # are continuations by the same test as `compact` (all three restore the
        # transcript), and the original checked only `compact`. `fork` is the one
        # that matters most — its parent session is often still running, so a
        # reset there destroys a LIVE session's evidence.
        #
        # The exhaustive partition over all five documented sources is asserted
        # in test_session_boundary_events.py::TestMatcherPartition; this keeps a
        # local guard in the file that owns hooks.json wiring.
        data = json.loads(HOOKS_JSON.read_text())
        reset_entries = [
            e for e in data["hooks"]["SessionStart"]
            if any(
                "bin/prawduct-hook" in c and "clear" in c.split()
                and "--brief-only" not in c
                for c in (h["command"] for h in e["hooks"])
            )
        ]
        assert len(reset_entries) == 1, (
            f"expected exactly one state-reset clear entry, got {len(reset_entries)}"
        )
        sources = set(reset_entries[0]["matcher"].split("|"))
        for continuation in ("compact", "resume", "fork"):
            assert continuation not in sources, (
                f"the clear (state-reset) hook must not fire on {continuation}"
            )


# =============================================================================
# Behavioral — subprocess invocation with a mock git
# =============================================================================


def _write_mock_git(mock_bin: Path, *, status: str = "", branch: str = "main", head: str = "deadbeef" * 5):
    mock_bin.mkdir(parents=True, exist_ok=True)
    status_file = mock_bin / "_status"
    status_file.write_text(status)
    git = mock_bin / "git"
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        'if [[ "$1" == "status" ]]; then cat "%s"; exit 0; fi\n'
        'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "worktree" ]]; then exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n" % (head, status_file, branch)
    )
    git.chmod(0o755)
    gh = mock_bin / "gh"
    gh.write_text("#!/bin/bash\necho '[]'\nexit 0\n")
    gh.chmod(0o755)


def run_plugin_hook(
    command: str,
    project_dir: Path,
    *args: str,
    git_status: str = "",
    branch: str = "main",
    mock_bin: Path | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess:
    """Invoke bin/prawduct-hook as Claude Code would: CLAUDE_PLUGIN_ROOT points
    at the plugin (this repo), CLAUDE_PROJECT_DIR at the consuming repo, and a
    mock git on PATH. mock_bin defaults OUTSIDE project_dir so the §2
    write-isolation assertion can snapshot the project dir cleanly. Extra
    positional ``*args`` are passed through as subcommand argv (e.g.
    ``run_plugin_hook("clear", proj, "--session-start")``).

    ``stdin`` is fed to the child as ``input=`` — Claude Code writes a JSON
    payload to a Stop hook's stdin (``background_tasks`` etc.); the default
    ``""`` gives a clean closed pipe (EOF), which the hook reads as "no signal"
    so existing callers keep their pre-STH-3W7F behavior.
    """
    if mock_bin is None:
        mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin, status=git_status, branch=branch)
    # HOME outside project_dir so per-user caches don't land under the project
    # (would confound the §2 write-isolation snapshot). PYTHONDONTWRITEBYTECODE
    # keeps the plugin-lib import from writing .pyc into this repo during tests.
    home = mock_bin.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), command, *args],
        capture_output=True, text=True, env=env, timeout=20, input=stdin,
    )


def _make_session_start(prawduct: Path, offset_seconds: int = -60) -> None:
    ts = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


class TestPluginClearBriefing:
    def test_clear_renders_briefing_and_writes_session_markers(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        # Session markers written under .prawduct/
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".session-git-baseline").is_file()
        assert (prawduct / ".session-git-baseline").read_text() == " M src/app.py"

    def test_clear_does_not_sync_even_with_manifest(self, tmp_path):
        # A sync-manifest would trigger file-sync in the legacy hook. The plugin
        # runtime must never sync (design §2/§7) — no "PRAWDUCT SYNC" output.
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "sync-manifest.json").write_text(
            json.dumps({"framework_version": "1.8.1", "framework_source": "/nonexistent"})
        )
        result = run_plugin_hook("clear", tmp_path)
        assert result.returncode == 0, result.stderr
        assert "PRAWDUCT SYNC" not in result.stdout
        assert "framework file(s) updated" not in result.stdout

    def test_clear_briefing_namespaces_status_hints(self, tmp_path):
        # ADV-3K7Q (whole-briefing coherence): the plugin clear briefing's status
        # lines — backlog triage and learnings lookup — must name the
        # plugin-namespaced skills, not the bare file-sync forms that do not
        # resolve in a plugin repo's command namespace. (The file-sync engine that
        # kept the bare forms was retired in M4.)
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # A structured backlog (two items) so the count line fires and we isolate
        # the status-line hints.
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n## Open\n- [ABC-0001] a pending item\n- [ABC-0002] another\n"
        )
        (prawduct / "learnings.md").write_text("# Learnings\n\n- a standing rule\n")
        result = run_plugin_hook("clear", tmp_path)
        assert result.returncode == 0, result.stderr
        # Both status hints name the plugin-namespaced skills...
        assert "/prawduct:backlog to triage" in result.stdout
        assert "/prawduct:learnings <topic>" in result.stdout
        # ...and the bare file-sync forms do not leak into a plugin briefing.
        assert "(/backlog to triage)" not in result.stdout
        assert "/learnings <topic>" not in result.stdout


class TestPluginClearNonPrawductRepo:
    """The clear/briefing SessionStart hook fires in every repo (the plugin is
    user-scoped). In a repo with no .prawduct/ it must emit nothing and write
    nothing — no session briefing, no project-preferences CRITICAL, no session
    markers — mirroring cmd_stop, which already early-returns. Skills like
    /prawduct:onboard stay available; only the always-on briefing is silenced.
    This is the fix for the user-scoped plugin leaking governance into unrelated
    repos.
    """

    def test_clear_silent_and_inert_without_prawduct_dir(self, tmp_path):
        # A real codebase (has source) that never onboarded: no .prawduct/. Before
        # the fix this printed the project-preferences CRITICAL (gated on code).
        (tmp_path / "app.py").write_text("print('hi')\n")
        result = run_plugin_hook("clear", tmp_path, git_status=" M app.py")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            f"clear hook leaked into a non-Prawduct repo: {result.stdout!r}"
        )
        # The loud pre-fix leak specifically: the code-gated prefs CRITICAL.
        assert "project-preferences.md" not in result.stdout
        # Wrote nothing — no .prawduct/ scaffolded, no session markers.
        assert not (tmp_path / ".prawduct").exists()


class TestPluginStopGate:
    def _active_plan_repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        return prawduct

    def test_stop_blocks_when_critic_findings_absent(self, tmp_path):
        """Keystone acceptance: code changed vs active plan + no findings -> exit 2."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr
        # The gate names the plugin-namespaced command — a bare `/critic` does not
        # resolve in a plugin repo's command namespace, so the message must surface
        # `/prawduct:critic` and never a bare `/critic`. Both assertions pin the
        # backtick command form so they match the command the message tells users to
        # run, not an incidental `/critic` substring elsewhere in the output.
        assert "`/prawduct:critic`" in result.stderr
        assert "`/critic`" not in result.stderr

    def test_findings_cache_alone_no_longer_clears_the_gate(self, tmp_path):
        # Kernel-v3 chunk 04 still-blocks regression: a fresh, schema-valid,
        # blocking-free .critic-findings.json is a derived CACHE (D7) — no
        # gate reads it. Only a review FACT whose trees compose over the
        # session's changes clears the gate, so this v2-satisfying state now
        # blocks (real coverage lives in test_session_critic_gate.py and the
        # gate-cutover scenarios).
        prawduct = self._active_plan_repo(tmp_path)
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "findings": [], "files_reviewed": ["src/app.py"], "summary": "No issues found.",
        }))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "no composed review coverage" in result.stderr

    def test_stop_passes_with_no_build_plan(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, (result.stdout, result.stderr)

    def test_stop_blocks_when_findings_mtime_exactly_ties_session_start(self, tmp_path):
        """STH-6B4R tie rule: findings_mtime == session_start is NOT fresh.

        The Critic gate clears only on a strict `findings_mtime > session_start`
        at identical (whole-second) precision. A findings file whose mtime lands
        in the exact same whole second as session-start must NOT clear the gate
        — so this otherwise-valid, blocking-free findings file still blocks
        (exit 2). Pins the tie semantics against a future `>=` regression.
        """
        prawduct = self._active_plan_repo(tmp_path)
        findings = prawduct / ".critic-findings.json"
        findings.write_text(json.dumps({
            "findings": [], "files_reviewed": ["src/app.py"], "summary": "No issues found.",
        }))
        # Force the findings mtime to a fixed whole second, then write
        # session-start to that SAME whole-second string -> an exact tie.
        tie = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
        epoch = tie.timestamp()
        os.utime(findings, (epoch, epoch))
        (prawduct / ".session-start").write_text(tie.strftime("%Y-%m-%dT%H:%M:%SZ"))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr


class TestPluginStopGateBackgroundDefer:
    """STH-3W7F: while harness-tracked background work is in flight, the Stop
    hook DEFERS the session-end blockers (exit 0 + a note) instead of blocking,
    because the diff isn't final and the session can't end anyway. The deferral
    is stateless — it re-arms the instant `background_tasks` empties — so the
    Critic still fires when the work lands. Fixture mirrors TestPluginStopGate:
    active plan + code diff + NO findings is the state that blocks today (exit 2);
    these tests pin that a non-empty `background_tasks` stdin converts it to 0.
    """

    _CODE_DIFF = " M src/app.py"

    def _active_plan_repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        return prawduct

    @staticmethod
    def _stdin(tasks) -> str:
        return json.dumps({"background_tasks": tasks, "session_crons": []})

    def test_defers_while_background_work_in_flight(self, tmp_path):
        """Non-empty background_tasks -> exit 0 with a deferral note, NOT a block."""
        self._active_plan_repo(tmp_path)
        stdin = self._stdin([{"id": "wf-1", "type": "workflow", "name": "build-pipeline"}])
        result = run_plugin_hook("stop", tmp_path, git_status=self._CODE_DIFF, stdin=stdin)
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "GATES DEFERRED" in result.stderr
        # The note names the in-flight task and the deferred gate, and is explicit
        # that the gate is deferred, not skipped.
        assert "workflow:build-pipeline" in result.stderr
        assert "deferred:" in result.stderr
        assert "NOT skipped" in result.stderr

    def test_blocks_when_background_tasks_empty(self, tmp_path):
        """Present-but-empty array = genuinely idle -> block exactly as today."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=self._CODE_DIFF, stdin=self._stdin([])
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr
        assert "GATES DEFERRED" not in result.stderr

    def test_blocks_when_stdin_absent(self, tmp_path):
        """No stdin (older client / no signal) -> block as today (no regression)."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook("stop", tmp_path, git_status=self._CODE_DIFF, stdin="")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr

    def test_blocks_on_malformed_stdin(self, tmp_path):
        """Garbage stdin must fail-soft to the blocking default, never defer."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=self._CODE_DIFF, stdin="not json {{{"
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "CRITIC" in result.stderr
        assert "GATES DEFERRED" not in result.stderr

    def test_deferral_rearms_when_work_lands(self, tmp_path):
        """Deferral is stateless: a deferred Stop (work in flight -> 0) followed by
        an idle Stop on the same fixture (empty array -> 2) proves the gate
        re-arms. Not a one-shot waiver, not a persisted skip."""
        self._active_plan_repo(tmp_path)
        in_flight = run_plugin_hook(
            "stop", tmp_path, git_status=self._CODE_DIFF,
            stdin=self._stdin([{"id": "t-1", "type": "subagent", "agent_type": "Explore"}]),
        )
        assert in_flight.returncode == 0, (in_flight.stdout, in_flight.stderr)
        landed = run_plugin_hook(
            "stop", tmp_path, git_status=self._CODE_DIFF, stdin=self._stdin([])
        )
        assert landed.returncode == 2, (landed.stdout, landed.stderr)
        assert "CRITIC" in landed.stderr

    def test_satisfied_gate_emits_no_deferral_note(self, tmp_path):
        """When no gate is in play (here: a doc-only diff — the kernel-v3
        judgeability carveout), an in-flight array changes nothing — still a
        clean exit 0 and NO deferral note (there was no blocker to defer)."""
        self._active_plan_repo(tmp_path)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=" M docs/notes.md",
            stdin=self._stdin([{"id": "wf-1", "type": "workflow", "name": "x"}]),
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "GATES DEFERRED" not in result.stderr


class TestPluginStopGateRegressions:
    """TST-7Q3D: regression coverage for three previously-untested stop-gate
    branches — verify-resolutions out-of-scope blocking, Type:trivial fileset
    violations, and the unknown-gate-waiver-key diagnostic. Mirrors
    TestPluginStopGate's fixtures (active plan + session markers + fresh findings).
    """

    # The verbose persisted form of the verify-resolutions mode (the bare
    # `verify-resolutions` token is the caller-side input, rejected on disk).
    _VERIFY_RESOLUTIONS_MODE = "verify-resolutions (delta review, prior findings only)"

    def _active_plan_repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        return prawduct

    def test_verify_resolutions_cache_with_out_of_scope_diff_still_blocks(self, tmp_path):
        # (a) Kernel-v3 chunk 04: the v-r scope-subset mechanism is deleted —
        # a verify-resolutions findings CACHE clears nothing (no gate reads
        # it), and a diff beyond what any review saw is simply an uncovered
        # tree. The v2-blocking state must STILL block (learnings: every
        # deleted check keeps a still-blocks regression).
        prawduct = self._active_plan_repo(tmp_path)
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "findings": [],
            "files_reviewed": ["a.py"],
            "summary": "Resolutions verified.",
            "mode": self._VERIFY_RESOLUTIONS_MODE,
        }))
        result = run_plugin_hook(
            "stop", tmp_path, git_status=" M a.py\n M b.py",
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "no composed review coverage" in result.stderr
        # The remedy names the verify-resolutions flow (the fact-recording
        # successor of the deleted scope check).
        assert "verify-resolutions" in result.stderr

    def test_trivial_chunk_outside_fileset_bounds_blocks(self, tmp_path):
        # (b) A chunk declaring Type: trivial that edits skills/ (a catastrophic-
        # blast-radius bound) must block with the fileset reason, even though the
        # rationale is present.
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: tweak a skill\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: tweak a skill\n"
            "**Type:** trivial\n"
            "**Trivial because:** a one-word typo fix in a skill doc.\n"
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: edited the skill doc and confirmed the change reads cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook(
            "stop", tmp_path, git_status=" M skills/critic/SKILL.md",
        )
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "TYPE: TRIVIAL" in result.stderr
        assert "skill-file-edited" in result.stderr

    def test_unknown_gate_waiver_key_warns_without_blocking(self, tmp_path):
        # (c) An unknown key in .gates-waived emits a stderr diagnostic but never
        # blocks — unknown keys simply have no effect. Use a no-build-plan repo so
        # nothing else would block: exit 0, with the diagnostic present.
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        (prawduct / ".gates-waived").write_text(json.dumps({"bogus": "not a real gate"}))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "unknown keys" in result.stderr
        assert "bogus" in result.stderr


class TestStopGateAttribution:
    """Design §5a: a blocking message names the version + gate that caused it,
    so a surprise block is always traceable to the update, never mysterious."""

    PLUGIN_VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]

    def test_critic_block_names_version_and_gate(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 1\n"
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented the chunk and verified all tests pass cleanly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "gate: critic-review" in result.stderr
        assert f"prawduct v{self.PLUGIN_VERSION}" in result.stderr

    def test_reflection_block_names_gate(self, tmp_path):
        # Critic satisfied (fresh blocking-free findings) but reflection missing
        # -> only the reflection gate blocks, and it carries its own attribution.
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 1\n"
        )
        (prawduct / ".session-git-baseline").write_text("")
        _make_session_start(prawduct)
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "findings": [], "files_reviewed": ["src/app.py"], "summary": "No issues found.",
        }))
        result = run_plugin_hook("stop", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "REFLECTION" in result.stderr
        assert "gate: reflection" in result.stderr


class TestPluginRuntimeNamespacing:
    """Full-coherence namespace sweep: the plugin runtime names the
    /prawduct:-namespaced skills in ALL agent-facing gate output AND its own
    docstrings/comments. A bare `/critic` or `/pr` does not resolve in a plugin
    repo's command namespace. (The frozen file-sync runtime that kept the bare
    forms was retired in M4.) Source-scan, matching this module's other
    structural-invariant tests (test_sync_cluster_excised): assert the BAD form
    is ABSENT, because a presence-only check lets sibling leaks survive (the
    prior namespace sweep's recurring failure mode — see learnings.md)."""

    # Bare command phrases that must never appear in the plugin hook. Each is
    # collision-free with file paths and prose: the command+arg phrases contain a
    # space (no path does), and the backtick forms only ever wrap a command
    # invocation. (Legit survivors are file paths like `.prawduct/critic-review.md`
    # and the prose `critic/pr skills` — none match these needles.)
    FORBIDDEN_BARE = (
        "/critic chunk",
        "/critic final",
        "/critic cumulative",
        "/critic verify-resolutions",
        "`/critic`",
        "/pr create",
        "`/pr`",
        "Run /pr ",
        # The hyphenated `/prawduct-advisory` is the FROZEN file-sync skill name;
        # the plugin skill is `/prawduct:advisory`. (Collision-free with the binary
        # path `bin/prawduct-hook`, which contains `/prawduct-hook`, not `-advisory`.)
        "/prawduct-advisory",
    )

    def test_hook_emits_no_bare_command_forms(self):
        # The runtime command surface is the hook PLUS the lib modules that now
        # hold extracted command bodies + their agent-facing gate messages
        # (STH-9V4K hook decomposition — e.g. check_cumulative_critic moved to
        # lib/gates ch.6, the PR fast-path commands to lib/coverage ch.5, and the
        # session-briefing assembly — the most command-hint-dense surface, with the
        # backlog/learnings/advisory hints — to lib/briefing ch.7). Scan all of them
        # so a bare form can't hide in a relocated command body or briefing hint.
        runtime_sources = [HOOK]
        for libmod in ("gates.py", "coverage.py", "briefing.py"):
            p = ROOT / "lib" / libmod
            if p.is_file():
                runtime_sources.append(p)
        src = "\n".join(p.read_text() for p in runtime_sources)
        leaked = [needle for needle in self.FORBIDDEN_BARE if needle in src]
        assert not leaked, (
            f"plugin runtime leaks bare command form(s) {leaked} — the runtime "
            "(bin/prawduct-hook + its command-body lib modules) must name the "
            "/prawduct:-namespaced skills in agent-facing output and docstrings "
            "alike (a bare form does not resolve in a plugin repo). The frozen "
            "file-sync copies keep the bare forms; the plugin diverges."
        )
        # ...and the namespaced forms ARE present (the sweep replaced, not deleted).
        assert "`/prawduct:critic`" in src, "stop-hook Critic gate must name /prawduct:critic"
        assert "/prawduct:critic cumulative" in src, "pr-create gate must name /prawduct:critic cumulative"
        assert "Run /prawduct:pr to invoke" in src, "stop-hook PR gate must name /prawduct:pr"


class TestPluginDocsNamespacing:
    """The plugin-bundled TEACHING PROSE names /prawduct:-namespaced commands, not
    bare /critic / /pr forms. These files are read by an agent ONLY when the plugin
    governs (the skills point at them via ${CLAUDE_SKILL_DIR}/../../methodology/…),
    so a bare `/critic chunk` would not resolve in the repo's command namespace —
    the same leak class as the runtime sweep (TestPluginRuntimeNamespacing), one
    surface over. Source-scan, assert the bad form is ABSENT.

    The needle is the FULL skill-command vocabulary (not just the tokens that
    happened to leak), encoding the learnings.md rule: a partial sweep that pins
    only the spellings present today silently passes over a sibling added later.
    (The file-sync copies under tools/ + templates/ that once kept the bare forms
    were deleted with the engine in M4 — only these plugin-bundled files remain.)"""

    DOCS = (
        "methodology/building.md",
        "methodology/planning.md",
        "methodology/reflection.md",
        "skills/critic/review-cycle.md",
        "skills/critic/review-protocol.md",
        "skills/pr/review-protocol.md",
    )
    # A genuine command-invocation token: a `/` that starts a command (NOT preceded
    # by a word/path char — so paths like `skills/critic/…`, `.prawduct/backlog.md`,
    # and the already-namespaced `/prawduct:critic` are excluded) followed by a
    # skill name on a word boundary (so `/pr` does not match inside `/prawduct`).
    # `/clear` is a Claude Code built-in, not a prawduct skill — deliberately absent.
    BARE_INVOCATION = re.compile(
        r"(?<![\w/:.\-])/(critic|pr|backlog|learnings|janitor|discovery|planning"
        r"|building|reflection|methodology|doctor|onboard|advisory)\b"
    )

    @pytest.mark.parametrize("rel", DOCS)
    def test_no_bare_command_invocations(self, rel):
        src = (ROOT / rel).read_text(encoding="utf-8")
        leaks = sorted({m.group(0) for m in self.BARE_INVOCATION.finditer(src)})
        assert not leaks, (
            f"{rel} carries bare command invocation(s) {leaks} — plugin-bundled "
            "teaching prose must name the /prawduct:-namespaced skill (a bare form "
            "does not resolve in a plugin repo's command namespace). The file-sync "
            "tools/ + templates/ copies that once kept the bare forms were deleted "
            "with the engine in M4."
        )

    def test_namespaced_forms_present(self):
        # The sweep REPLACED bare forms; it didn't delete the references.
        cycle = (ROOT / "skills/critic/review-cycle.md").read_text(encoding="utf-8")
        assert "/prawduct:critic" in cycle and "/prawduct:pr create" in cycle
        planning = (ROOT / "methodology/planning.md").read_text(encoding="utf-8")
        assert "/prawduct:learnings" in planning
        building = (ROOT / "methodology/building.md").read_text(encoding="utf-8")
        assert "/prawduct:critic" in building and "/prawduct:pr" in building

    @pytest.mark.parametrize("rel", DOCS)
    def test_no_legacy_binary_name(self, rel):
        """The runtime binary is `prawduct-hook`; the file-sync binary was
        `product-hook`. The Chunk-1 sweep namespaced the slash-commands on these
        lines but missed the bare BINARY name (caught by the M4 cumulative Critic),
        because the slash-command scan above never matches a binary name. Pin it:
        plugin teaching prose must never name `product-hook` (note `prawduct-hook`
        does NOT contain the substring, so this is false-positive-free)."""
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "product-hook" not in src, (
            f"{rel} names the retired file-sync binary `product-hook` — the plugin "
            "runtime is `prawduct-hook`. (Legitimate consumer-side `tools/product-hook` "
            "detection lives in lib/migrate_plugin + the MANAGED_FILES registry, not here.)"
        )


class TestJanitorSkillPluginEra:
    """`skills/janitor/SKILL.md`'s Template Currency theme must teach the plugin
    model, not the retired file-sync workflow. Replaces the deleted
    `test_v5_templates.py::TestJanitorSkillTemplateCurrency` mirror (it pinned the
    file-sync language via the now-removed `templates/skill-janitor.md`) — closing
    [JAN-4F7M]. A regression here means the skill drifted back to teaching
    `sync-manifest.json`/`framework_source`, neither of which exists in a plugin
    repo (init never creates them; `/prawduct:migrate` removes them)."""

    SKILL = "skills/janitor/SKILL.md"

    @pytest.mark.parametrize("needle", ["sync-manifest", "framework_source", "place_once"])
    def test_no_filesync_residue(self, needle):
        src = (ROOT / self.SKILL).read_text(encoding="utf-8")
        assert needle not in src, (
            f"{self.SKILL} still teaches the retired file-sync term `{needle}` — "
            "post-M4 a plugin repo carries no sync-manifest and no framework_source; "
            "Template Currency compares against the read-only plugin templates."
        )

    def test_template_currency_targets_plugin_root(self):
        src = (ROOT / self.SKILL).read_text(encoding="utf-8")
        assert "${CLAUDE_PLUGIN_ROOT}/templates/" in src, (
            f"{self.SKILL} must resolve framework templates from "
            "`${CLAUDE_PLUGIN_ROOT}/templates/` (the plugin ships them read-only)."
        )


class TestPluginSubcommandsResolveViaLib:
    def _repo(self, tmp_path) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
        return prawduct

    def test_infer_critic_mode(self, tmp_path):
        self._repo(tmp_path)
        result = run_plugin_hook("infer-critic-mode", tmp_path)
        # Resolves through the bundled lib/ (exit 0, a real `<mode>|<rationale>`).
        # The pre-2.0 `final|fallback-no-tools-lib` degradation was removed in M4 —
        # a failed import now exits non-zero, so a clean run proves lib resolved.
        assert result.returncode == 0, result.stderr
        mode, sep, _rationale = result.stdout.strip().partition("|")
        assert sep == "|", result.stdout
        assert mode in {"chunk", "final", "cumulative", "verify-resolutions"}, result.stdout

    def test_advisory_list(self, tmp_path):
        # `advisory` takes a subcommand; invoke `advisory list` via argv. Proves
        # the advisory CLI resolves through the bundled lib (not the missing-lib
        # fallback message).
        self._repo(tmp_path)
        result = subprocess.run(
            ["python3", str(HOOK), "advisory", "list"],
            capture_output=True, text=True, timeout=20,
            env={"HOME": str(tmp_path / "_home"), "CLAUDE_PROJECT_DIR": str(tmp_path),
                 "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": "/usr/bin:/bin",
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, result.stderr
        assert "advisory CLI unavailable" not in (result.stdout + result.stderr)


class TestValidateEvidenceSchema:
    """`prawduct-hook validate-evidence` requires the full F4a coverage schema.

    The pre-v1.4 compat path that accepted ``verifier``-less "legacy" evidence
    was removed in M4 (file-sync retirement): the plugin runtime always emits
    the F4a fields (directly, or via ``test-reference-verify --merge-into``), so
    no remaining writer produces the legacy shape.
    """

    _COMPLETE = {
        "timestamp": "2026-06-03T12:00:00Z",
        "passed": 10, "failed": 0, "skipped": 0,
        "duration_seconds": 1, "command": "pytest",
        "verifier": "test-reference-verify (floor: symbol-grep)",
        "tests_executed": ["tests/test_x.py"],
        "changes_referenced": ["lib/x.py"],
        "coverage_level": "referenced",
    }

    def _write_evidence(self, tmp_path: Path, evidence: dict) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))
        return tmp_path

    def test_complete_f4a_evidence_accepted(self, tmp_path):
        repo = self._write_evidence(tmp_path, self._COMPLETE)
        result = _run_in(repo, "validate-evidence")
        assert result.returncode == 0, result.stderr
        assert "valid" in result.stdout

    def test_legacy_no_verifier_evidence_rejected(self, tmp_path):
        # The pre-v1.4 "legacy" shape: the 6 base fields, no F4a coverage fields.
        legacy = {k: self._COMPLETE[k] for k in (
            "timestamp", "passed", "failed", "skipped", "duration_seconds", "command",
        )}
        repo = self._write_evidence(tmp_path, legacy)
        result = _run_in(repo, "validate-evidence")
        assert result.returncode == 1, result.stdout
        # Names the now-required F4a fields so the writer bug is obvious.
        assert "verifier" in result.stderr
        assert "coverage_level" in result.stderr

    def test_bool_rejected_for_int_field(self, tmp_path):
        # TST-1D5W: bool is a subclass of int, so `{"passed": true}` would slip
        # through a bare isinstance(v, int) check and be read as the integer 1.
        # The schema must reject a JSON boolean in an int-typed count field —
        # it is always writer drift, never a real test count.
        evidence = dict(self._COMPLETE)
        evidence["passed"] = True  # JSON bool where an int count is required
        repo = self._write_evidence(tmp_path, evidence)
        result = _run_in(repo, "validate-evidence")
        assert result.returncode == 1, result.stdout
        # The violation names the offending field and the bool type it got.
        assert "passed" in result.stderr
        assert "bool" in result.stderr


class TestWriteIsolationInvariant:
    """Design §2: the runtime reads/writes ONLY .prawduct/ — never elsewhere."""

    def test_clear_and_stop_write_only_under_prawduct(self, tmp_path):
        project = tmp_path / "repo"
        project.mkdir()
        prawduct = project / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        # Product files OUTSIDE .prawduct that must be untouched.
        (project / "app.py").write_text("print('hi')\n")
        (project / "README.md").write_text("# Repo\n")
        src = project / "src"
        src.mkdir()
        (src / "lib.py").write_text("x = 1\n")

        def snapshot() -> dict[str, bytes]:
            out: dict[str, bytes] = {}
            for p in project.rglob("*"):
                if p.is_file() and ".prawduct" not in p.relative_to(project).parts:
                    out[str(p.relative_to(project))] = p.read_bytes()
            return out

        before = snapshot()
        r1 = run_plugin_hook("clear", project, git_status=" M src/lib.py", mock_bin=tmp_path / "_mock_bin")
        _make_session_start(prawduct)
        r2 = run_plugin_hook("stop", project, git_status=" M src/lib.py", mock_bin=tmp_path / "_mock_bin")
        after = snapshot()
        assert before == after, (
            "the plugin runtime modified files outside .prawduct/ — violates the "
            f"§2 write-isolation invariant. clear={r1.returncode} stop={r2.returncode}"
        )


# =============================================================================
# Gitflow base resolution — the 2.0.0 ship-blocker fix (real git repo)
# =============================================================================


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30, check=True,
        env={**os.environ,
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"},
    )


def _run_in(repo: Path, *args: str) -> subprocess.CompletedProcess:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        ["python3", str(HOOK), *args],
        capture_output=True, text=True, timeout=20,
        env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
             "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.fixture
def gitflow_repo(tmp_path):
    """A gitflow topology where develop..main diverges from the feature branch:

        main:    M1 ──────────── M2        (M2 = a .py change on main after branch)
                  \\
        develop:   └─ D1                    (D1 = a .py change on develop)
                       \\
        feature:        └─ F1 ─ F2          (F1, F2 = .md-only changes)

    With base_branch=develop the PR diff is develop..feature = {F1,F2 .md only}
    (doc-only). With the main fallback the diff main..feature includes D1's .py
    -> NOT doc-only. That difference proves the base knob drives the range.
    """
    repo = tmp_path / "gitflow"
    repo.mkdir()
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("# r\n")
    (repo / "code.py").write_text("x = 0\n")
    (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "M1")
    # Branch develop, make a .py change (the develop..main pollution).
    _git(repo, "checkout", "-b", "develop")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "commit", "-am", "D1 py change on develop")
    # Feature off develop: two .md-only commits.
    _git(repo, "checkout", "-b", "feature/x")
    (repo / "README.md").write_text("# r\n\nfeature line 1\n")
    _git(repo, "commit", "-am", "F1 doc")
    (repo / "README.md").write_text("# r\n\nfeature line 1\nfeature line 2\n")
    _git(repo, "commit", "-am", "F2 doc")
    # Advance main past the branch point (M2, a .py change) so develop..main is non-trivial.
    _git(repo, "checkout", "main")
    (repo / "code.py").write_text("x = 99\n")
    _git(repo, "commit", "-am", "M2 py change on main")
    _git(repo, "checkout", "feature/x")
    return repo


class TestGitflowBaseResolution:
    def test_resolve_base_honors_configured_develop(self, gitflow_repo):
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: develop\n"
        )
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "develop"

    def test_resolve_base_falls_back_to_main_without_knob(self, gitflow_repo):
        # No base_branch set -> historical candidate list (trunk repos unchanged).
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "main"

    def test_doc_only_gate_uses_develop_range(self, gitflow_repo):
        # base_branch=develop: feature diff is develop..HEAD = README.md only -> doc-only.
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: develop\n"
        )
        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "develop" in (r.stdout + r.stderr)

    def test_doc_only_gate_pollutes_with_main_base(self, gitflow_repo):
        # No knob -> base resolves to main; main..HEAD includes develop's .py change
        # (D1) -> NOT doc-only. This is the bug the knob fixes.
        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "code.py" in (r.stdout + r.stderr) or "not-doc-only" in (r.stdout + r.stderr)

    def test_configured_base_unresolvable_fails_closed(self, gitflow_repo):
        (gitflow_repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: nonexistent-branch\n"
        )
        r = _run_in(gitflow_repo, "resolve-base")
        assert r.returncode == 1
        assert "nonexistent-branch" in r.stderr


class TestDocOnlyProtectedPaths:
    """PR-5K8D: governance-protected paths are never doc-only, even as .md.

    Fork-skill prose is behavioral logic in this framework, so a PR touching
    `skills/*.md` (or methodology/, templates/, root CLAUDE.md) must not take
    the doc-only fast path past the cumulative-Critic and PR-reviewer gates.
    Bound list shared with the `Type: trivial` gate (_TRIVIAL_PROTECTED_PATHS).
    """

    @staticmethod
    def _use_develop_base(repo):
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\nbase_branch: develop\n"
        )

    @pytest.mark.parametrize(
        "relpath",
        [
            "skills/critic/SKILL.md",
            "methodology/building.md",
            "templates/spec.md",
            "CLAUDE.md",
        ],
    )
    def test_protected_md_in_pr_is_not_doc_only(self, gitflow_repo, relpath):
        # Kernel-v3 chunk 04: the judgeability predicate answers this (a
        # protected .md is judgeable), so the message names the file rather
        # than the retired per-bound violation label.
        self._use_develop_base(gitflow_repo)
        target = gitflow_repo / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# governance prose\n")
        _git(gitflow_repo, "add", relpath)
        _git(gitflow_repo, "commit", "-m", f"F3 governance edit: {relpath}")

        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 1, (r.stdout, r.stderr)
        out = r.stdout + r.stderr
        assert "not-doc-only" in out and relpath in out

    def test_nested_claude_md_is_still_doc_only(self, gitflow_repo):
        # The CLAUDE.md bound is exact-match: a nested foo/CLAUDE.md is
        # ordinary product doc (mirrors the trivial gate's semantics).
        self._use_develop_base(gitflow_repo)
        nested = gitflow_repo / "subpkg" / "CLAUDE.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("# nested instructions\n")
        _git(gitflow_repo, "add", "subpkg/CLAUDE.md")
        _git(gitflow_repo, "commit", "-m", "F3 nested claude md")

        r = _run_in(gitflow_repo, "check-pr-doc-only")
        assert r.returncode == 0, (r.stdout, r.stderr)


class TestVerifyOperatorVerificationSubcommand:
    """`prawduct-hook verify-operator-verification <VRF-id>` (Chunk 11) is the
    plugin-native replacement for the legacy `prawduct-setup.py verify` path,
    which no longer exists in a migrated consumer. It flips one pending entry
    to verified, operating only on the consumer's own
    .prawduct/operator-verification.md — the /prawduct:pr and /prawduct:doctor
    skills invoke it.
    """

    def _seed(self, tmp_path: Path, body: str) -> Path:
        repo = tmp_path / "consumer"
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "operator-verification.md").write_text(body)
        return repo

    def test_flips_pending_to_verified(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-001")
        assert result.returncode == 0, result.stderr
        assert "VRF-001" in result.stdout
        assert "pending" in result.stdout and "verified" in result.stdout
        queue = (repo / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** verified" in queue

    def test_missing_id_errors_and_leaves_queue_untouched(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification")
        assert result.returncode == 1
        assert "requires a VRF id" in result.stderr
        queue = (repo / ".prawduct" / "operator-verification.md").read_text()
        assert "**Status:** pending" in queue

    def test_unknown_id_errors(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** pending\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-999")
        assert result.returncode == 1
        assert "VRF-999" in result.stderr

    def test_accepted_entry_refuses_verify(self, tmp_path):
        repo = self._seed(tmp_path, "## VRF-001 — a\n**Status:** accepted\n")
        result = _run_in(repo, "verify-operator-verification", "VRF-001")
        assert result.returncode == 1
        assert "accepted" in result.stderr.lower()

    def test_subcommand_listed_in_usage(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "bogus-subcommand")
        assert result.returncode == 1
        assert "verify-operator-verification" in result.stderr


class TestAuditLearningsSubcommand:
    """`prawduct-hook audit-learnings [--apply] [--json]` (Chunk 13) is the
    plugin-native replacement for the legacy `prawduct-setup.py audit-learnings`
    path, gone in a migrated consumer. It operates purely on the consumer's own
    `.prawduct/learnings.md`; `/prawduct:doctor`'s Audit-Learnings flow invokes
    it with --json. (Entries here carry NO `sentinel=` so no pytest subprocess
    runs — the runner only shells out for retirement-candidate sentinels.)
    """

    def _seed(self, tmp_path: Path, learnings: str | None) -> Path:
        repo = tmp_path / "consumer"
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True)
        if learnings is not None:
            (prawduct / "learnings.md").write_text(learnings)
        return repo

    def test_promotion_candidate_surfaced_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## A confirmed rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2026-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["applied"] is False
        assert [p["title"] for p in data["promotions"]] == ["A confirmed rule"]

    def test_stale_flag_surfaced_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## An old unconfirmed rule\n"
            "<!-- prawduct-learning: confirmations=1; created=2020-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert [s["title"] for s in data["stale_flags"]] == ["An old unconfirmed rule"]

    def test_missing_learnings_is_clean_empty_not_error(self, tmp_path):
        # A .prawduct/ with no learnings.md is a clean empty result, not an error.
        repo = self._seed(tmp_path, None)
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["promotions"] == [] and data["retirements"] == []
        assert "error" not in data

    def test_non_prawduct_dir_errors(self, tmp_path):
        repo = tmp_path / "bare"
        repo.mkdir()
        result = _run_in(repo, "audit-learnings", "--json")
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_human_summary_without_json(self, tmp_path):
        repo = self._seed(
            tmp_path,
            "# Learnings\n\n## A confirmed rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2026-01-01 -->\n\nBody.\n",
        )
        result = _run_in(repo, "audit-learnings")
        assert result.returncode == 0, result.stderr
        assert "promotion candidate" in result.stdout
        assert "A confirmed rule" in result.stdout

    def test_subcommand_listed_in_usage(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "bogus-subcommand")
        assert result.returncode == 1
        assert "audit-learnings" in result.stderr


class TestFlagOnlyArgRejection:
    """STH-5R2Q: flag-only subcommands (no positionals; options detected via
    `"--flag" in argv`) historically swallowed any unrecognized token. That
    masked a real bug — a test passed `tmp_path` positionally to
    `audit-learnings`, which silently ignored it and audited the inherited
    CLAUDE_PROJECT_DIR repo instead. Each flag-only command now rejects unknown
    args with exit 2 (the hook's usage-error convention), matching the
    fail-closed arg handling in lib.ledger / lib.telemetry / lib.risk.
    """

    def test_audit_learnings_rejects_unknown_positional(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run_in(repo, "audit-learnings", str(repo), "--json")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr

    def test_audit_learnings_rejects_unknown_flag(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run_in(repo, "audit-learnings", "--bogus")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr

    def test_audit_learnings_recognized_flags_still_pass(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        (repo / ".prawduct" / "learnings.md").write_text("# Learnings\n")
        result = _run_in(repo, "audit-learnings", "--apply", "--json")
        assert result.returncode == 0, result.stderr

    def test_repo_disable_rejects_unknown_arg(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run_in(repo, "repo-disable", "--bogus")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr

    def test_clear_rejects_unknown_arg(self, tmp_path):
        """The hot-path SessionStart command also rejects unknowns — the guard
        fires before any git/state work, so it needs no repo scaffolding."""
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "clear", "--bogus")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr

    def test_clear_recognized_flags_still_pass(self, tmp_path):
        """A bare `clear` and `clear --session-start` must still proceed — a
        non-onboarded repo (no .prawduct/) exits 0 cleanly (no briefing)."""
        repo = tmp_path / "r"
        repo.mkdir()
        result = _run_in(repo, "clear", "--session-start")
        assert result.returncode == 0, result.stderr

    def test_verify_records_rejects_unknown_flag(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run_in(repo, "verify-records", "--bogus")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr

    def test_verify_records_rejects_a_flag_missing_its_value(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".prawduct").mkdir(parents=True)
        result = _run_in(repo, "verify-records", "--base")
        assert result.returncode == 2
        assert "requires a value" in result.stderr


class TestNoBareSkillShadowing:
    """A bare `.claude/skills/<name>/` in this framework repo would double-load as
    a `/<name>` skill and shadow the plugin's `/prawduct:<name>`. Chunk 14 first
    relocated the six file-sync skill *sources* out of `.claude/skills/` into
    `templates/skill-<name>.md`; M4 Chunk 4 deleted those templates outright when
    the file-sync engine retired (governance ships from the plugin's `skills/`).
    This guards the structure so a future edit can't silently re-introduce a bare
    shadowing skill dir.
    """

    SHADOWABLE = ("pr", "janitor", "learnings", "backlog", "prawduct-advisory", "prawduct-doctor")

    @pytest.mark.parametrize("name", SHADOWABLE)
    def test_no_shadowing_bare_skill_dir(self, name):
        assert not (ROOT / ".claude" / "skills" / name).exists(), (
            f".claude/skills/{name}/ re-introduced — a bare /{name} skill would "
            f"shadow the plugin's /prawduct:{name} with a stale file-sync copy "
            "(Chunk 14 relocation / M4 Chunk 4 deletion)"
        )


class TestTestEvidenceRecord:
    """TST-6V2N: `test-evidence record` RUNS the suite and WRITES the evidence
    the freshness gate (`test-status`) reads — closing the reader-without-a-writer
    gap that forced every product repo to hand-maintain a sha-stamp shim.
    """

    def _repo_with_test(self, tmp_path, body: str) -> Path:
        repo = tmp_path / "ev"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_sample.py").write_text(body)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def test_passing_suite_writes_schema_valid_evidence(self, tmp_path):
        repo = self._repo_with_test(tmp_path, "def test_ok():\n    assert True\n")
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev_path = repo / ".prawduct" / ".test-evidence.json"
        assert ev_path.is_file()
        ev = json.loads(ev_path.read_text())
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (1, 0, 0)
        # git_sha retired (TST-4K2P): it was dead-read by every runtime consumer
        # and misleading when stamped before commit (review agents eyeballed the
        # lagging sha and wrongly flagged "stale"). Freshness is the timestamp vs
        # session-start (test-status), never a commit field — so the record must
        # NOT carry a git_sha.
        assert "git_sha" not in ev
        assert ev["timestamp"] and ev["duration_seconds"] >= 0
        # the plugin's own validator accepts what the plugin produced
        assert _run_in(repo, "validate-evidence").returncode == 0

    def test_failing_suite_exits_nonzero_but_still_writes(self, tmp_path):
        # A mixed run (some pass, some fail): at least one pass proves the
        # suite launched in a working environment, so the failure is real
        # evidence and must be recorded, not dropped. The 0-passed-only-errors
        # fallback signature is the ONE deliberate carve-out — refused as a
        # launch-environment error (TestDeclaredCommandEnvironments covers it).
        repo = self._repo_with_test(
            tmp_path,
            "def test_ok():\n    assert True\n"
            "def test_bad():\n    assert False\n",
        )
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 1, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["failed"] >= 1 and ev["passed"] == 1
        # evidence is still schema-valid (a failing run is recorded, not dropped)
        assert _run_in(repo, "validate-evidence").returncode == 0

    def test_skipped_tests_are_counted(self, tmp_path):
        body = (
            "import pytest\n"
            "@pytest.mark.skip(reason='x')\n"
            "def test_s():\n    pass\n"
            "def test_ok():\n    assert True\n"
        )
        repo = self._repo_with_test(tmp_path, body)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 1 and ev["skipped"] == 1

    def test_record_makes_test_status_current(self, tmp_path):
        repo = self._repo_with_test(tmp_path, "def test_ok():\n    assert True\n")
        _make_session_start(repo / ".prawduct", offset_seconds=-120)
        assert _run_in(repo, "test-evidence", "record").returncode == 0
        assert _run_in(repo, "test-status").returncode == 0

    def test_unknown_subcommand_is_a_usage_error(self, tmp_path):
        repo = self._repo_with_test(tmp_path, "def test_ok():\n    assert True\n")
        res = _run_in(repo, "test-evidence", "bogus")
        assert res.returncode == 2
        assert "usage" in res.stderr.lower()


class TestFromJunitIngest:
    """TST-7M3K: `record --from-junit <report>` ingests a JUnit XML the builder
    already produced instead of re-running the suite — the gate stops paying for
    the suite twice per stamp point.
    """

    def _repo(self, tmp_path, body: str = "def test_ok():\n    assert True\n") -> Path:
        repo = tmp_path / "fj"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_sample.py").write_text(body)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def _junit(self, repo: Path, *, tests: int = 2, failures: int = 0,
               errors: int = 0, skipped: int = 0, time: str = "1.5",
               name: str = "report.xml") -> Path:
        path = repo / name
        path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<testsuites>\n"
            f'  <testsuite name="pytest" tests="{tests}" failures="{failures}" '
            f'errors="{errors}" skipped="{skipped}" time="{time}"></testsuite>\n'
            "</testsuites>\n"
        )
        return path

    def test_ingests_report_without_running_the_suite(self, tmp_path):
        # The repo's OWN test would FAIL if run; the report claims 2 passed, 0
        # failed. An ingested record reflecting the report (exit 0, 2 passed)
        # proves the suite was never executed — the double-run is gone.
        repo = self._repo(tmp_path, "def test_bad():\n    assert False\n")
        junit = self._junit(repo, tests=2, failures=0)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit))
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (2, 0, 0)
        assert "git_sha" not in ev
        assert ev["command"] == f"--from-junit {junit}"
        # the plugin's own validator accepts what the plugin produced
        assert _run_in(repo, "validate-evidence").returncode == 0
        # the caller's report is read, not consumed — it must survive
        assert junit.is_file()

    def test_failing_report_exits_nonzero(self, tmp_path):
        repo = self._repo(tmp_path)
        junit = self._junit(repo, tests=3, failures=1)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit))
        assert res.returncode == 1, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["failed"] == 1 and ev["passed"] == 2

    def test_missing_report_is_a_clean_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-junit",
                      str(repo / "nope.xml"))
        assert res.returncode == 2
        assert "not found" in res.stderr.lower()

    def test_malformed_report_is_a_clean_error(self, tmp_path):
        repo = self._repo(tmp_path)
        bad = repo / "bad.xml"
        bad.write_text("<not-valid-xml")
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(bad))
        assert res.returncode == 2
        assert "parse" in res.stderr.lower()

    def test_missing_path_argument_is_a_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-junit")
        assert res.returncode == 2
        assert "--from-junit" in res.stderr

    def test_rejects_extra_pytest_args(self, tmp_path):
        repo = self._repo(tmp_path)
        junit = self._junit(repo)
        res = _run_in(repo, "test-evidence", "record", "--from-junit",
                      str(junit), "--", "-k", "foo")
        assert res.returncode == 2
        assert "from-junit" in res.stderr.lower()

    def test_ingests_with_declared_test_command(self, tmp_path):
        # A declared test_command emits JUnit; the single-run path is to run it
        # once and ingest its report — NOT re-run inside `record`. The repo's own
        # test would FAIL if run; ingesting a passing report proves the declared
        # command was not re-executed. (Was a rejection; the exclusion forced the
        # exact double-run the on-ramp exists to remove — see change-log.)
        repo = self._repo(tmp_path, "def test_bad():\n    assert False\n")
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "test_command: python3 -m pytest --junit-xml={junit_xml} -q\n"
        )
        junit = self._junit(repo, tests=2, failures=0)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit))
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert (ev["passed"], ev["failed"]) == (2, 0)
        assert ev["command"] == f"--from-junit {junit}"
        assert junit.is_file()  # report read, not consumed


class TestJunitLeafCounting:
    """#128: counts come from leaf `<testcase>` elements, not the `tests=` attribute.

    The attribute's meaning is reporter-specific, and the two live conventions
    cannot both be served by summing it:

    | reporter   | `tests=` counts   | summing top-level | summing every suite |
    |------------|-------------------|-------------------|---------------------|
    | Ant-style  | all descendants   | correct           | double-counts       |
    | node:test  | direct children   | **undercounts**   | correct             |

    A leaf `<testcase>` appears exactly once however the suites nest, so counting
    leaves is correct under both with no reporter detection. Each convention is a
    first-class test here, since a fix for either one alone silently reintroduces
    the other.
    """

    def _repo(self, tmp_path) -> Path:
        repo = tmp_path / "leaf"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def _write(self, repo: Path, xml: str) -> Path:
        path = repo / "report.xml"
        path.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + xml)
        return path

    def _record(self, repo: Path, xml: str) -> dict:
        junit = self._write(repo, xml)
        _run_in(repo, "test-evidence", "record", "--from-junit", str(junit))
        return json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())

    # Two child describes holding 3 leaves each; the outer suite declares 2.
    NODE_STYLE = """
<testsuites>
  <testsuite name="outer" tests="2" failures="0" errors="0" skipped="0" time="1.0">
    <testsuite name="a" tests="3" failures="0" errors="0" skipped="0" time="0.5">
      <testcase name="a1"/><testcase name="a2"/><testcase name="a3"/>
    </testsuite>
    <testsuite name="b" tests="3" failures="0" errors="0" skipped="0" time="0.5">
      <testcase name="b1"/><testcase name="b2"/><testcase name="b3"/>
    </testsuite>
  </testsuite>
</testsuites>
"""

    def test_nested_describes_are_not_undercounted(self, tmp_path):
        # The reported bug: 6 real tests recorded as 2, scaling with nest depth.
        ev = self._record(self._repo(tmp_path), self.NODE_STYLE)
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (6, 0, 0)

    def test_ant_style_descendant_counts_are_not_double_counted(self, tmp_path):
        # Same tree, Ant semantics: outer declares 6 (its descendants). Summing
        # every suite's attribute would report 12; leaves report 6.
        ev = self._record(
            self._repo(tmp_path), self.NODE_STYLE.replace('name="outer" tests="2"',
                                                          'name="outer" tests="6"')
        )
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (6, 0, 0)

    def test_flat_suite_is_unchanged(self, tmp_path):
        # pytest's shape — one suite, leaves directly beneath. The common case
        # must not move.
        ev = self._record(self._repo(tmp_path), """
<testsuites><testsuite name="pytest" tests="4" failures="1" errors="0" skipped="1" time="2.5">
  <testcase name="t1"/><testcase name="t2"/>
  <testcase name="t3"><failure message="boom"/></testcase>
  <testcase name="t4"><skipped/></testcase>
</testsuite></testsuites>
""")
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (2, 1, 1)

    def test_status_is_classified_per_leaf_with_error_precedence(self, tmp_path):
        # A case carrying BOTH <error> and <failure> counts once, as an error —
        # otherwise `failed` exceeds the number of tests that actually ran.
        ev = self._record(self._repo(tmp_path), """
<testsuites><testsuite name="m" tests="4" failures="9" errors="9" skipped="9" time="1.0">
  <testcase name="p"/>
  <testcase name="both"><error message="e"/><failure message="f"/></testcase>
  <testcase name="f"><failure message="f"/></testcase>
  <testcase name="s"><skipped/></testcase>
</testsuite></testsuites>
""")
        # 1 passed, 1 error + 1 failure = 2 failed, 1 skipped — and the wrong
        # suite-level attributes (9/9/9) are ignored entirely.
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (1, 2, 1)

    def test_summary_only_report_falls_back_to_attributes(self, tmp_path):
        # Some CI aggregators emit suite attributes with no <testcase> children.
        # Recording a confident 0 would be worse than the bug being fixed, so the
        # attribute sum remains the fallback when there are no leaves anywhere.
        ev = self._record(self._repo(tmp_path), """
<testsuites><testsuite name="agg" tests="10" failures="2" errors="1" skipped="3" time="9.0"/></testsuites>
""")
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (4, 3, 3)

    def test_multiple_roots_still_aggregate(self, tmp_path):
        # The multi-root behaviour that top-level summing was introduced for must
        # survive leaf counting: two sibling suites, three leaves each.
        ev = self._record(self._repo(tmp_path), """
<testsuites>
  <testsuite name="one" tests="3" failures="0" errors="0" skipped="0" time="1.0">
    <testcase name="x1"/><testcase name="x2"/><testcase name="x3"/>
  </testsuite>
  <testsuite name="two" tests="3" failures="1" errors="0" skipped="0" time="1.0">
    <testcase name="y1"/><testcase name="y2"/>
    <testcase name="y3"><failure message="b"/></testcase>
  </testsuite>
</testsuites>
""")
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (5, 1, 0)

    def _record_many(self, repo: Path, *xmls: str) -> dict:
        args = []
        for i, xml in enumerate(xmls):
            path = repo / f"report{i}.xml"
            path.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + xml)
            args += ["--from-junit", str(path)]
        _run_in(repo, "test-evidence", "record", *args)
        return json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())

    def test_summary_only_suite_survives_alongside_a_populated_one(self, tmp_path):
        # One report can mix shapes: a populated suite plus one that died before
        # emitting any <testcase> and carries only attributes. Choosing
        # leaf-vs-attribute once for the whole ingest drops the second entirely —
        # and with it a real error.
        ev = self._record(self._repo(tmp_path), """
<testsuites>
  <testsuite name="ok" tests="2" failures="0" errors="0" skipped="0" time="1.0">
    <testcase name="a"/><testcase name="b"/>
  </testsuite>
  <testsuite name="died" tests="1" failures="0" errors="1" skipped="0" time="0.0"/>
</testsuites>
""")
        # 2 leaves plus the summary-only suite's 1 error. A global switch reports
        # (2, 0, 0) here — a broken run recorded as green.
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (2, 1, 0)

    def test_mixed_multi_report_ingest_keeps_every_failure(self, tmp_path):
        # `--from-junit` is repeatable — the documented multi-environment on-ramp.
        # One runner emitting leaves and another emitting a summary-only report is
        # the shape that turns a global leaf/attribute switch into a FALSE GREEN:
        # `failed` drives this command's exit status AND `tests_are_current`, so a
        # dropped failing environment would let the stop gate pass.
        ev = self._record_many(
            self._repo(tmp_path),
            """
<testsuites><testsuite name="leafy" tests="2" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="a"/><testcase name="b"/>
</testsuite></testsuites>
""",
            """
<testsuites><testsuite name="summary" tests="5" failures="2" errors="0" skipped="0" time="3.0"/></testsuites>
""",
        )
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (5, 2, 0)

    def test_skipped_loses_to_failure_in_the_precedence_chain(self, tmp_path):
        # The precedence rule claims `skipped` loses to BOTH <error> and <failure>.
        # The error half is pinned above; this pins the failure half, so reordering
        # the chain to test `skipped` first cannot pass silently.
        ev = self._record(self._repo(tmp_path), """
<testsuites><testsuite name="p" tests="2" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="ok"/>
  <testcase name="both"><skipped/><failure message="f"/></testcase>
</testsuite></testsuites>
""")
        # The dual case is a failure, never a skip: (1, 1, 0), not (1, 0, 1).
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (1, 1, 0)

    def test_malformed_count_attribute_exits_two_not_traceback(self, tmp_path):
        # Every other bad-report path here exits 2 with a named cause. A
        # non-numeric `tests=` must not be the one that tracebacks instead.
        repo = self._repo(tmp_path)
        junit = self._write(repo, """
<testsuites><testsuite name="bad" tests="oops" failures="0" errors="0" skipped="0" time="1.0"/></testsuites>
""")
        res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit))
        assert res.returncode == 2, res.stderr
        assert "malformed count attribute" in res.stderr
        assert "Traceback" not in res.stderr

    def test_empty_count_attribute_reads_zero(self, tmp_path):
        # `tests=""` is absent-with-extra-steps, not malformed: it must read 0 and
        # let the run record, rather than taking the exit-2 path a non-numeric
        # value earns. Without that distinction this report fails to record at all.
        ev = self._record(self._repo(tmp_path), """
<testsuites>
  <testsuite name="leafy" tests="1" failures="0" errors="0" skipped="0" time="1.0">
    <testcase name="a"/>
  </testsuite>
  <testsuite name="blank" tests="" failures="" errors="" skipped="" time="0.0"/>
</testsuites>
""")
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (1, 0, 0)


class TestFromCountsIngest:
    """`record --from-counts passed=N failed=M skipped=K [duration=S]` records
    counts supplied directly — the language-/runner-agnostic on-ramp for a
    toolchain that cannot emit JUnit XML (embedded HIL, a bespoke harness). Like
    `--from-junit` it runs nothing.
    """

    def _repo(self, tmp_path, body: str = "def test_ok():\n    assert True\n") -> Path:
        repo = tmp_path / "fc"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_sample.py").write_text(body)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def test_records_counts_without_running_the_suite(self, tmp_path):
        # The repo's OWN test would FAIL if run; the counts claim 5 passed, 0
        # failed. A record reflecting the counts (exit 0, 5 passed) proves the
        # suite was never executed — a non-JUnit toolchain recorded evidence.
        repo = self._repo(tmp_path, "def test_bad():\n    assert False\n")
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=5", "failed=0", "skipped=1", "duration=3.2")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (5, 0, 1)
        assert ev["duration_seconds"] == 3.2
        assert "git_sha" not in ev
        assert "--from-counts" in ev["command"]
        # the plugin's own validator accepts what the plugin produced
        assert _run_in(repo, "validate-evidence").returncode == 0

    def test_skipped_and_duration_default_to_zero(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=3", "failed=0")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert (ev["passed"], ev["failed"], ev["skipped"]) == (3, 0, 0)
        assert ev["duration_seconds"] == 0

    def test_makes_test_status_current(self, tmp_path):
        repo = self._repo(tmp_path)
        _make_session_start(repo / ".prawduct", offset_seconds=-120)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=2", "failed=0").returncode == 0
        assert _run_in(repo, "test-status").returncode == 0

    def test_failing_counts_exit_nonzero(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=2", "failed=1")
        assert res.returncode == 1, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["failed"] == 1 and ev["passed"] == 2

    def test_missing_required_key_is_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts", "passed=2")
        assert res.returncode == 2
        assert "failed" in res.stderr.lower()

    def test_unknown_key_is_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=2", "failed=0", "bogus=1")
        assert res.returncode == 2
        assert "unknown key" in res.stderr.lower()

    def test_non_integer_count_is_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=lots", "failed=0")
        assert res.returncode == 2
        assert "integer" in res.stderr.lower()

    def test_negative_count_is_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=-1", "failed=0")
        assert res.returncode == 2
        assert ">= 0" in res.stderr

    def test_duplicate_key_is_usage_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=1", "passed=2", "failed=0")
        assert res.returncode == 2
        assert "duplicate" in res.stderr.lower()

    def test_tolerates_double_dash_separator(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts", "--",
                      "passed=4", "failed=0")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 4

    def test_rejects_combination_with_from_junit(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-junit", "r.xml",
                      "--from-counts", "passed=1", "failed=0")
        assert res.returncode == 2
        assert "mutually exclusive" in res.stderr.lower()

    def test_rejects_extra_args(self, tmp_path):
        repo = self._repo(tmp_path)
        # tokens before --from-counts are stray args; an ingest mode runs nothing.
        res = _run_in(repo, "test-evidence", "record", "-k", "foo",
                      "--from-counts", "passed=1", "failed=0")
        assert res.returncode == 2
        assert "from-counts" in res.stderr.lower()

    def test_rejects_combination_with_test_command(self, tmp_path):
        # A declared test_command emits JUnit, so hand-typed counts (no artifact)
        # stay rejected — but the error redirects to --from-junit, which ingests
        # that report without a re-run (fixes the discoverability half: the agent
        # need not guess the escape hatch).
        repo = self._repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "test_command: python3 -m pytest --junit-xml={junit_xml} -q\n"
        )
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=1", "failed=0")
        assert res.returncode == 2
        assert "test_command" in res.stderr
        assert "from-junit" in res.stderr.lower()

    def test_head_tilde1_base_emits_advisory(self, tmp_path):
        # A repo NOT on main with no origin → the recorder's overlay base falls
        # back to the moving HEAD~1; record warns (naming base_branch:) even via
        # an ingest mode that runs nothing.
        repo = tmp_path / "fc_h1"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "a.py").write_text("def a():\n    return 1\n")
        _git(repo, "init", "-b", "work")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c0")
        (repo / "b.py").write_text("def b():\n    return 2\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=1", "failed=0")
        assert res.returncode == 0, res.stderr
        assert "head~1" in res.stderr.lower()
        assert "base_branch" in res.stderr


class TestNoRerunRestamp:
    """`record --no-rerun` (alias --restamp) reuses the existing record's counts
    and refreshes the timestamp + F4a half against the current tree — no suite
    run. The sanctioned cheap refresh after a rename/force-add shifted
    changes_referenced; trust posture matches --from-junit.
    """

    def _repo(self, tmp_path, body: str = "def test_ok():\n    assert True\n") -> Path:
        repo = tmp_path / "nr"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_sample.py").write_text(body)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def test_reuses_counts_and_refreshes_without_running(self, tmp_path):
        # Seed a record via --from-counts (no run) in a repo whose own test would
        # FAIL if run. A restamp reflecting the seeded counts (7 passed) proves no
        # suite ran.
        repo = self._repo(tmp_path, "def test_bad():\n    assert False\n")
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=7", "failed=0", "skipped=0").returncode == 0
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 0, res.stderr
        after = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert (after["passed"], after["failed"], after["skipped"]) == (7, 0, 0)
        assert _run_in(repo, "validate-evidence").returncode == 0

    def test_refreshes_changes_referenced_against_current_tree(self, tmp_path):
        # The feature's stated purpose: restamp re-derives the F4a coverage half
        # against the CURRENT tree. Seed on a clean tree (nothing changed vs
        # main), then modify a referenced source file and restamp — the changed
        # file must now appear in changes_referenced, with no suite run.
        repo = tmp_path / "nr2"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "mod.py").write_text("def feature():\n    return 1\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_mod.py").write_text(
            "from mod import feature\n\ndef test_feature():\n    assert feature() == 1\n"
        )
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=1", "failed=0").returncode == 0
        seeded = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert "mod.py" not in seeded["changes_referenced"]
        (repo / "mod.py").write_text("def feature():\n    return 2\n")
        assert _run_in(repo, "test-evidence", "record", "--no-rerun").returncode == 0
        after = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert "mod.py" in after["changes_referenced"]

    def test_restamp_flips_stale_record_to_current(self, tmp_path):
        # The freshness-refresh reason to restamp: a record from before this
        # session reads stale; --no-rerun re-stamps the timestamp (reusing counts,
        # no run) so test-status reads current again.
        repo = self._repo(tmp_path)
        _make_session_start(repo / ".prawduct", offset_seconds=-60)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=2", "failed=0").returncode == 0
        ev_path = repo / ".prawduct" / ".test-evidence.json"
        ev = json.loads(ev_path.read_text())
        ev["timestamp"] = "2000-01-01T00:00:00Z"  # backdate → stale
        ev_path.write_text(json.dumps(ev))
        assert _run_in(repo, "test-status").returncode == 1, "expected stale"
        assert _run_in(repo, "test-evidence", "record", "--no-rerun").returncode == 0
        assert _run_in(repo, "test-status").returncode == 0, "expected current after restamp"

    def test_restamp_alias_works(self, tmp_path):
        repo = self._repo(tmp_path)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=3", "failed=0").returncode == 0
        assert _run_in(repo, "test-evidence", "record", "--restamp").returncode == 0
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 3

    def test_failing_prior_record_stays_failing(self, tmp_path):
        repo = self._repo(tmp_path)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=1", "failed=2").returncode == 1
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 1, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["failed"] == 2

    def test_preserves_prior_command(self, tmp_path):
        repo = self._repo(tmp_path)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=1", "failed=0").returncode == 0
        before = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert _run_in(repo, "test-evidence", "record", "--no-rerun").returncode == 0
        after = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert after["command"] == before["command"]

    def test_missing_evidence_is_clean_error(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 2
        assert "existing" in res.stderr.lower()

    def test_malformed_evidence_is_clean_error(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / ".prawduct" / ".test-evidence.json").write_text("{not json")
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 2
        assert "unreadable" in res.stderr.lower()

    def test_evidence_missing_counts_is_clean_error(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / ".prawduct" / ".test-evidence.json").write_text(
            json.dumps({"timestamp": "2026-01-01T00:00:00Z"})
        )
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 2
        assert "counts" in res.stderr.lower()

    def test_rejects_combination_with_from_junit(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun",
                      "--from-junit", "r.xml")
        assert res.returncode == 2
        assert "mutually exclusive" in res.stderr.lower()

    def test_rejects_combination_with_from_counts(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun",
                      "--from-counts", "passed=1", "failed=0")
        assert res.returncode == 2
        assert "mutually exclusive" in res.stderr.lower()

    def test_rejects_extra_args(self, tmp_path):
        repo = self._repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun", "--", "-k", "foo")
        assert res.returncode == 2
        assert "no-rerun" in res.stderr.lower() or "restamp" in res.stderr.lower()

    def test_allows_restamp_with_declared_test_command(self, tmp_path):
        # Restamp reuses the existing record's counts and re-derives only the
        # coverage half — no suite run — so a declared test_command is fine.
        # Seed via --from-junit (the declared-command ingest path), then restamp.
        repo = self._repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "test_command: python3 -m pytest --junit-xml={junit_xml} -q\n"
        )
        junit = repo / "r.xml"
        junit.write_text(
            '<testsuites><testsuite name="pytest" tests="4" failures="0" '
            'errors="0" skipped="0" time="1.0"></testsuite></testsuites>\n'
        )
        assert _run_in(repo, "test-evidence", "record",
                       "--from-junit", str(junit)).returncode == 0
        assert _run_in(repo, "test-evidence", "record", "--no-rerun").returncode == 0
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 4


class TestTreeValidatedFreshness:
    """spike-tree-validated-test-evidence.md §9 — the build gate for the
    additive tree-validity clause. Each case seeds a real `record` (which
    captures `evidence_tree`), backdates the record's timestamp so it PREDATES
    the session (timestamp alone now reads stale), then asserts the tree clause
    decides correctly: an unchanged judgeable tree reads `current` across the
    session boundary; ANY judgeable change reads `stale`. Proves the disjunction
    only ever relaxes stale->current — structurally incapable of the false-stale
    that retired the fingerprint and git_sha mechanisms.
    """

    def _seed(self, tmp_path, name: str) -> Path:
        repo = tmp_path / name
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "src").mkdir()
        # A judgeable src file to mutate in the "stale" cases; the suite itself
        # is trivial and self-contained so the seed `record` never depends on
        # import paths.
        (repo / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n")
        (repo / "test_app.py").write_text("def test_ok():\n    assert True\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        _make_session_start(repo / ".prawduct", offset_seconds=-60)
        assert _run_in(repo, "test-evidence", "record").returncode == 0, "seed record"
        ev_path = repo / ".prawduct" / ".test-evidence.json"
        ev = json.loads(ev_path.read_text())
        # End-to-end: a real run captures evidence_tree AND the F4a overlay's
        # existing.update() preserves it.
        assert isinstance(ev.get("evidence_tree"), str) and ev["evidence_tree"], \
            "a real run must persist evidence_tree through the F4a overlay"
        ev["timestamp"] = "2000-01-01T00:00:00Z"  # predate the session
        ev_path.write_text(json.dumps(ev))
        return repo

    # --- relax-only: an unchanged judgeable tree stays current across sessions ---

    def test_restart_no_change_is_current(self, tmp_path):
        repo = self._seed(tmp_path, "restart")
        assert _run_in(repo, "test-status").returncode == 0, \
            "unchanged tree must read current despite predating the session"

    def test_metadata_yaml_edit_is_current(self, tmp_path):
        repo = self._seed(tmp_path, "meta")
        (repo / ".prawduct" / "project-state.yaml").write_text("views_enabled: true\n")
        assert _run_in(repo, "test-status").returncode == 0, \
            ".prawduct/*.yaml is not judgeable — must stay current"

    def test_non_protected_md_edit_is_current(self, tmp_path):
        repo = self._seed(tmp_path, "doc")
        (repo / "README.md").write_text("# notes\nchanged\n")
        assert _run_in(repo, "test-status").returncode == 0, \
            "a non-protected .md is not judgeable — must stay current"

    def test_untracked_incoming_bug_note_is_current(self, tmp_path):
        repo = self._seed(tmp_path, "bug")
        (repo / "incoming-bugs").mkdir()
        (repo / "incoming-bugs" / "report.md").write_text("# bug report\n")
        assert _run_in(repo, "test-status").returncode == 0, \
            "an untracked .md note is not judgeable — must stay current"

    def test_verbatim_commit_is_current(self, tmp_path):
        # Committing the already-recorded state must not invalidate: the tree's
        # judgeable content is unchanged (only the record's own metadata moved).
        repo = self._seed(tmp_path, "commit")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "commit recorded state verbatim")
        assert _run_in(repo, "test-status").returncode == 0, \
            "a verbatim commit preserves the judgeable tree — must stay current"

    # --- correctly stale: any judgeable change re-stales ---

    def test_src_edit_is_stale(self, tmp_path):
        repo = self._seed(tmp_path, "src")
        (repo / "src" / "app.py").write_text("def add(a, b):\n    return a + b + 1\n")
        assert _run_in(repo, "test-status").returncode == 1, \
            "a src edit is judgeable — must read stale"

    def test_test_edit_is_stale(self, tmp_path):
        repo = self._seed(tmp_path, "tst")
        (repo / "test_app.py").write_text("def test_ok():\n    assert 1 == 1\n")
        assert _run_in(repo, "test-status").returncode == 1, \
            "a test edit is judgeable — must read stale"

    def test_untracked_test_file_is_stale(self, tmp_path):
        repo = self._seed(tmp_path, "newtest")
        (repo / "test_extra.py").write_text("def test_x():\n    assert True\n")
        assert _run_in(repo, "test-status").returncode == 1, \
            "an untracked test file is judgeable — must read stale"

    def test_lockfile_edit_is_stale(self, tmp_path):
        repo = self._seed(tmp_path, "lock")
        (repo / "uv.lock").write_text("# dependency footprint changed\n")
        assert _run_in(repo, "test-status").returncode == 1, \
            "a lockfile is judgeable — a recorded dep change must read stale"

    def test_hook_edit_is_stale(self, tmp_path):
        # The vetted judgeability predicate makes bin/prawduct-hook judgeable, so
        # editing it invalidates — closing the inverse false-fresh the old
        # metadata-filter patch introduced by skipping the hook itself.
        repo = self._seed(tmp_path, "hook")
        (repo / "bin").mkdir()
        (repo / "bin" / "prawduct-hook").write_text("#!/usr/bin/env python3\n")
        assert _run_in(repo, "test-status").returncode == 1, \
            "the hook is judgeable — editing it must read stale"

    # --- from-counts stays timestamp-only (captures no tree) ---

    def test_from_counts_captures_no_tree_and_stays_stale_when_backdated(self, tmp_path):
        # --from-counts is the untied on-ramp: it captures no evidence_tree, so a
        # backdated count record reads stale (timestamp-only), preserving the
        # pre-clause contract even though the working tree is unchanged.
        repo = tmp_path / "counts"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / "test_ok.py").write_text("def test_ok():\n    assert True\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        _make_session_start(repo / ".prawduct", offset_seconds=-60)
        assert _run_in(repo, "test-evidence", "record", "--from-counts",
                       "passed=1", "failed=0").returncode == 0
        ev_path = repo / ".prawduct" / ".test-evidence.json"
        ev = json.loads(ev_path.read_text())
        assert "evidence_tree" not in ev, "--from-counts must not capture a tree"
        ev["timestamp"] = "2000-01-01T00:00:00Z"
        ev_path.write_text(json.dumps(ev))
        assert _run_in(repo, "test-status").returncode == 1, \
            "backdated --from-counts is stale (timestamp-only; no tree clause)"


class TestTreeValidHelperFailsToStale:
    """The tree-validity clause must FAIL TOWARD STALE on any git error: a
    capture or diff failure can only leave evidence stale, never flip it fresh
    (the false-fresh a gate must never produce). Unit-level with monkeypatch —
    these fail-safe branches are impractical to trigger through a real repo.
    """

    def _gates(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from lib import gates  # noqa: PLC0415 — in-process import, mirrors other lib unit tests
        return gates

    def test_capture_failure_reads_not_valid(self, monkeypatch):
        gates = self._gates()
        monkeypatch.setattr(
            gates.evidence, "capture_tree",
            lambda project_dir: {"status": "error", "reason": "git exploded"},
        )
        ok, reason = gates._test_evidence_tree_valid(ROOT, "deadbeefdeadbeef")
        assert ok is False and "capture" in reason.lower()

    def test_tree_diff_unavailable_reads_not_valid(self, monkeypatch):
        gates = self._gates()
        # capture succeeds but returns a DIFFERENT tree, so the diff path is
        # reached; tree_diff then returns None (missing object / git failure).
        monkeypatch.setattr(
            gates.evidence, "capture_tree",
            lambda project_dir: {"status": "ok", "tree": "1111111111111111"},
        )
        monkeypatch.setattr(
            gates.evidence, "tree_diff",
            lambda project_dir, a, b: None,
        )
        ok, reason = gates._test_evidence_tree_valid(ROOT, "2222222222222222")
        assert ok is False and "diff" in reason.lower()


class TestTestEvidenceKnobs:
    """Gate-soundness ch.2: `test_command:` / `tests_dirs:` in
    project-state.yaml replace the hardcoded `sys.executable -m pytest`-from-
    repo-root assumption that forced non-default repo shapes (uv venvs,
    monorepo test trees) into wrapper scripts around the recorder.
    """

    def _repo(self, tmp_path, state: str, test_body: str = "def test_ok():\n    assert True\n") -> Path:
        repo = tmp_path / "ev"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / "project-state.yaml").write_text(state)
        (repo / "test_sample.py").write_text(test_body)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        return repo

    def test_declared_test_command_is_run(self, tmp_path):
        """The declared command runs (shlex-split list-form — never a shell —
        from the repo root) and its JUnit output feeds the evidence counts,
        proving the hook executed IT, not its own pytest guess."""
        repo = self._repo(
            tmp_path,
            f"test_command: {sys.executable} -m pytest --junit-xml={{junit_xml}} -q test_sample.py\n",
        )
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 1 and ev["failed"] == 0
        # The evidence records the DECLARED command, placeholder intact.
        assert "{junit_xml}" in ev["command"]

    def test_test_command_without_placeholder_is_an_error(self, tmp_path):
        repo = self._repo(tmp_path, "test_command: pytest -q\n")
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 2
        assert "{junit_xml}" in res.stderr

    def test_extra_args_rejected_when_test_command_declared(self, tmp_path):
        """The declared command IS the invocation — ad-hoc arg injection would
        recreate the scoped-subset trap the knob exists to close."""
        repo = self._repo(
            tmp_path,
            f"test_command: {sys.executable} -m pytest --junit-xml={{junit_xml}} -q\n",
        )
        res = _run_in(repo, "test-evidence", "record", "--", "-k", "ok")
        assert res.returncode == 2
        assert "test_command" in res.stderr

    def test_multi_suite_junit_report_is_aggregated(self, tmp_path):
        """A declared test_command may be any runner — jest-junit and merged
        CI reports emit MULTIPLE <testsuite> elements under <testsuites>.
        Counts must sum across all of them, not read only the first."""
        writer = (
            "import sys\n"
            "open(sys.argv[1], 'w').write(\n"
            "    '<testsuites>'\n"
            "    '<testsuite tests=\"3\" failures=\"1\" errors=\"0\" skipped=\"0\" time=\"1.0\"/>'\n"
            "    '<testsuite tests=\"4\" failures=\"0\" errors=\"0\" skipped=\"2\" time=\"2.0\"/>'\n"
            "    '</testsuites>')\n"
        )
        repo = self._repo(tmp_path, "placeholder: x\n")
        (repo / "fake_runner.py").write_text(writer)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_command: {sys.executable} fake_runner.py {{junit_xml}}\n"
        )
        res = _run_in(repo, "test-evidence", "record")
        # Exit mirrors the COMMAND (the fake runner exits 0); the failure
        # lives in the recorded counts, which is what the gates read.
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 4 and ev["failed"] == 1 and ev["skipped"] == 2
        assert ev["duration_seconds"] == 3.0

    def test_missing_executable_is_a_clean_error(self, tmp_path):
        """A typo'd test_command executable exits 2 with an actionable
        message, not a raw FileNotFoundError traceback."""
        repo = self._repo(
            tmp_path,
            "test_command: no-such-binary-xyz --junit-xml={junit_xml}\n",
        )
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 2
        assert "no-such-binary-xyz" in res.stderr
        assert "Traceback" not in res.stderr

    def test_non_executable_target_is_a_clean_error(self, tmp_path):
        """TST-3E8V: a *non-executable* target (exists but no +x) raises
        PermissionError, not FileNotFoundError — both are OSError, so the
        widened catch routes it to the same clean exit-2 path rather than a
        raw traceback."""
        repo = self._repo(tmp_path, "placeholder: x\n")
        target = repo / "not_executable.sh"
        target.write_text("#!/bin/sh\necho hi\n")
        target.chmod(0o644)  # readable, NOT executable
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "test_command: ./not_executable.sh --junit-xml={junit_xml}\n"
        )
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 2
        assert "not_executable.sh" in res.stderr
        assert "Traceback" not in res.stderr

    def test_tests_dirs_forwarded_to_coverage_overlay(self, tmp_path):
        """A monorepo shape: tests live in component trees, not root `tests/`.
        With `tests_dirs:` declared, the F4a overlay discovers them and the
        changed source file is referenced — the exact false "missing-coverage"
        scriob's wrapper existed to fix."""
        repo = self._repo(
            tmp_path,
            "tests_dirs: engine/tests server/tests\n",
        )
        (repo / "engine" / "tests").mkdir(parents=True)
        (repo / "server" / "tests").mkdir(parents=True)
        (repo / "engine" / "core.py").write_text("def engine_fn():\n    return 1\n")
        (repo / "engine" / "tests" / "test_core.py").write_text(
            "def test_engine_fn():\n    assert 'engine_fn'\n"
        )
        (repo / "server" / "tests" / "test_api.py").write_text(
            "def test_api():\n    assert True\n"
        )
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert "engine/core.py" in ev["changes_referenced"]
        executed = set(ev["tests_executed"])
        assert "engine/tests/test_core.py" in executed
        assert "server/tests/test_api.py" in executed

    def test_absent_knobs_keep_default_behavior(self, tmp_path):
        """No knobs declared: the recorder behaves exactly as before."""
        repo = self._repo(tmp_path, "views_enabled: false\n")
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 1
        assert ev["command"].startswith("python3 -m pytest")


class TestJurisdictionSubcommand:
    """`prawduct-hook jurisdiction [--file <path>|<text...>] [--artifacts-only]`
    (norm-lifecycle Chunk 2) is the on-demand authoring aid that seeds a plan's
    `governed_by:` — the inverse of the orphan tripwire. It reads the same
    governing corpus the work-model index indexes, ranks artifacts by salient-
    term overlap, and — being an aid, never a gate — ALWAYS exits 0 (a bad
    `--file` path yields a stderr NOTE, not a failure).
    """

    def _seed(self, tmp_path: Path) -> Path:
        repo = tmp_path / "consumer"
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "telemetry-strategy.md").write_text(
            "# Telemetry Substrate\n"
            "The **telemetry** substrate governs **tracing** and observability.\n"
        )
        return repo

    def test_positional_text_surfaces_the_governing_artifact(self, tmp_path):
        repo = self._seed(tmp_path)
        result = _run_in(
            repo, "jurisdiction", "unify the telemetry substrate for tracing"
        )
        assert result.returncode == 0, result.stderr
        # Path is relative to the project dir; the matched terms are listed.
        assert ".prawduct/artifacts/telemetry-strategy.md" in result.stdout
        assert "telemetry" in result.stdout and "tracing" in result.stdout

    def test_file_input_matches_positional(self, tmp_path):
        repo = self._seed(tmp_path)
        plan = repo / "plan.txt"
        plan.write_text("adopt the telemetry substrate as the tracing layer")
        result = _run_in(repo, "jurisdiction", "--file", str(plan))
        assert result.returncode == 0, result.stderr
        assert ".prawduct/artifacts/telemetry-strategy.md" in result.stdout

    def test_no_overlap_prints_nothing_and_exits_zero(self, tmp_path):
        repo = self._seed(tmp_path)
        result = _run_in(repo, "jurisdiction", "quaternion holography magnetosphere")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""

    def test_missing_file_is_fail_open_note_not_error(self, tmp_path):
        # An unreadable --file is an aid failure, not a gate failure: NOTE + 0.
        repo = self._seed(tmp_path)
        result = _run_in(repo, "jurisdiction", "--file", str(repo / "nope.md"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "NOTE" in result.stderr

    def test_artifacts_only_excludes_docs_corpus(self, tmp_path):
        # The full corpus spans artifacts + CLAUDE.md + docs/ + methodology/;
        # --artifacts-only restricts to `.prawduct/artifacts/` (the governed_by:
        # target set). A docs/ file sharing the query's vocabulary must appear
        # without the flag and vanish with it.
        repo = self._seed(tmp_path)
        docs = repo / "docs"
        docs.mkdir()
        (docs / "style-guide.md").write_text(
            "# Style\nAll **tracing** conventions live here.\n"
        )
        full = _run_in(repo, "jurisdiction", "unify telemetry tracing")
        assert "docs/style-guide.md" in full.stdout
        restricted = _run_in(
            repo, "jurisdiction", "--artifacts-only", "unify telemetry tracing"
        )
        assert restricted.returncode == 0, restricted.stderr
        assert "docs/style-guide.md" not in restricted.stdout
        assert ".prawduct/artifacts/telemetry-strategy.md" in restricted.stdout

    def test_stdin_input_when_no_text_or_file(self, tmp_path):
        repo = self._seed(tmp_path)
        home = repo.parent / "_home"
        home.mkdir(exist_ok=True)
        result = subprocess.run(
            ["python3", str(HOOK), "jurisdiction"],
            input="adopt the telemetry substrate for tracing",
            capture_output=True, text=True, timeout=20,
            env={"HOME": str(home), "CLAUDE_PROJECT_DIR": str(repo),
                 "CLAUDE_PLUGIN_ROOT": str(ROOT),
                 "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, result.stderr
        assert ".prawduct/artifacts/telemetry-strategy.md" in result.stdout


# =============================================================================
# Green-is-evidence directive — a rule DELIVERED at its moment, not stored
# =============================================================================


def _load_hook_module():
    """Import bin/prawduct-hook as a module.

    The script guards its entry point with ``if __name__ == "__main__"``, so
    importing runs definitions only. Needed because the trigger under test is a
    pure function whose end-to-end path runs a subprocess overlay — testing it
    only through that path would leave the assertion unable to distinguish "the
    trigger is wrong" from "the overlay populated nothing," which is the exact
    fixture-cannot-reach-the-subject failure this directive warns about.
    """
    # bin/prawduct-hook is deliberately extensionless (it is invoked as a bare
    # command on the Bash PATH), so spec_from_file_location cannot infer a
    # loader and returns None. Supply SourceFileLoader explicitly.
    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_under_test", str(HOOK)
    )
    spec = importlib.util.spec_from_file_location(
        "prawduct_hook_under_test", HOOK, loader=loader
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGreenIsEvidenceDelivery:
    """The PRINT SITE, end to end — not the predicate behind it.

    `TestGreenIsEvidenceTrigger` below covers `_evidence_changed_judged_code`
    and pins phrases in the constant, and every one of those stayed green while
    the wiring in `cmd_test_evidence` was unverified: inverting the condition,
    or deleting the concatenation outright, changed nothing the suite could see.
    A directive nobody proved reaches stdout is a directive that can silently
    stop being delivered — and the constant's own first clause is *"confirm the
    fixture actually REACHES the subject,"* which is the rule that gap violated.
    """

    def _repo(self, tmp_path) -> Path:
        """A committed baseline. Callers then make the change under test.

        Two fixture mistakes are designed out here, both found by these tests
        failing. (1) Files written BEFORE the baseline commit leave an empty
        diff, so `changes_referenced` is empty and the positive case cannot
        fire. (2) The test file must live under `tests/` — the F4a overlay
        discovers test roots there unless `tests_dirs:` says otherwise, and
        without that it reports no coverage rather than a judged change.
        """
        repo = tmp_path / "gie"
        repo.mkdir(parents=True)
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_command: {sys.executable} -m pytest --junit-xml={{junit_xml}} -q\n"
        )
        (repo / "tests").mkdir()
        (repo / "tests" / "test_baseline.py").write_text(
            "def test_ok():\n    assert True\n"
        )
        (repo / "README.md").write_text("seed\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "baseline")
        return repo

    def _judged_change(self, repo: Path) -> None:
        """A changed `.py` whose symbol a test references — the one shape the
        overlay puts into `changes_referenced`."""
        (repo / "widget.py").write_text("def widget_fn():\n    return 1\n")
        (repo / "tests" / "test_widget.py").write_text(
            "def test_widget_fn():\n    assert 'widget_fn'\n"
        )

    def _docs_only_change(self, repo: Path) -> None:
        """The cycle the directive claims to stay silent on. NOT 'no source
        file' — an uncommitted `tests/test_*.py` is itself a judged change,
        because it declares symbols that appear in a test file (itself), which
        is how the first cut of this negative case fired the directive it was
        written to prove absent."""
        (repo / "README.md").write_text("seed\nmore prose\n")

    def _non_python_change(self, repo: Path) -> None:
        """A changed source file the symbol-grep overlay cannot judge at all.

        `.swift` stands in for every non-Python product (Go, Rust, C#, TS): the
        overlay classifies it `changes_unjudged` and leaves `changes_referenced`
        empty, which is the exact shape that kept this directive dark in every
        such repo.
        """
        (repo / "Widget.swift").write_text("struct Widget { let n = 1 }\n")

    def test_directive_fires_when_the_changed_set_holds_no_python_at_all(
        self, tmp_path
    ):
        """The whole point of the language-agnostic trigger.

        Asserts the fixture's *shape* before its outcome: a Python fixture
        passes this test today and proves nothing, so the empty
        `changes_referenced` is checked first — without it, a green here cannot
        distinguish "the trigger widened" from "the overlay judged the file
        after all".
        """
        repo = self._repo(tmp_path)
        self._non_python_change(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert not ev["changes_referenced"], (
            "fixture leaked a judged Python change — this test would then pass "
            "on the OLD trigger and prove nothing about non-Python products"
        )
        assert "Widget.swift" in ev["changes_unjudged"]
        hook = _load_hook_module()
        assert hook._GREEN_IS_EVIDENCE_DIRECTIVE in res.stdout

    def test_directive_reaches_stdout_when_judged_code_changed(self, tmp_path):
        repo = self._repo(tmp_path)
        self._judged_change(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["changes_referenced"], (
            "fixture did not produce a judged change, so this test cannot "
            "distinguish 'directive missing' from 'trigger never held'"
        )
        hook = _load_hook_module()
        assert hook._GREEN_IS_EVIDENCE_DIRECTIVE in res.stdout

    def test_directive_absent_on_a_docs_only_cycle(self, tmp_path):
        repo = self._repo(tmp_path)
        self._docs_only_change(repo)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert not ev["changes_referenced"]
        hook = _load_hook_module()
        assert hook._GREEN_IS_EVIDENCE_DIRECTIVE not in res.stdout
        # And the record still went out — advice fails soft, so its absence
        # must not take the confirmation with it.
        assert "recorded:" in res.stdout

    def test_the_directive_never_changes_the_exit_code(self, tmp_path):
        """Acceptance criterion, asserted rather than assumed: the firing and
        non-firing runs agree on exit status, so the advice rides the record
        instead of grading it."""
        fired = self._repo(tmp_path / "a")
        self._judged_change(fired)
        silent = self._repo(tmp_path / "b")
        self._docs_only_change(silent)
        a = _run_in(fired, "test-evidence", "record")
        b = _run_in(silent, "test-evidence", "record")
        hook = _load_hook_module()
        assert hook._GREEN_IS_EVIDENCE_DIRECTIVE in a.stdout
        assert hook._GREEN_IS_EVIDENCE_DIRECTIVE not in b.stdout
        assert a.returncode == b.returncode == 0


class TestGreenIsEvidenceTrigger:
    """`_evidence_changed_judged_code` decides whether the directive prints.

    The rule it carries has existed in `learnings.md` in general form for a long
    time (line 292, "anything one command could check is a CLAIM") and does not
    fire from there. Delivering it at `test-evidence record` — the moment green
    stops being an observation and becomes evidence the gates read — is the
    whole point, so the trigger must be exact in BOTH directions: a directive
    that prints on every invocation is one the reader learns to skip.
    """

    def _write(self, tmp_path, payload: str) -> Path:
        path = tmp_path / ".test-evidence.json"
        path.write_text(payload)
        return path

    def test_fires_when_judged_code_changed(self, tmp_path):
        hook = _load_hook_module()
        path = self._write(tmp_path, json.dumps({"changes_referenced": ["lib/a.py"]}))
        assert hook._evidence_changed_judged_code(path) is True

    def test_silent_when_nothing_judged_changed(self, tmp_path):
        hook = _load_hook_module()
        path = self._write(tmp_path, json.dumps({"changes_referenced": []}))
        assert hook._evidence_changed_judged_code(path) is False

    def test_fires_on_non_python_source_the_overlay_could_not_judge(self, tmp_path):
        """The non-Python product, at the predicate. `changes_referenced` is
        empty there by construction — symbol-grep judges Python only — so the
        trigger has to read `changes_unjudged` or it can never fire off Python.
        """
        hook = _load_hook_module()
        path = self._write(
            tmp_path,
            json.dumps(
                {"changes_referenced": [], "changes_unjudged": ["src/main.swift"]}
            ),
        )
        assert hook._evidence_changed_judged_code(path) is True

    @pytest.mark.parametrize(
        "unjudged",
        [
            ["README.md", "docs/guide.md"],
            [".prawduct/project-state.yaml", ".claude/settings.json"],
        ],
        ids=["prose", "framework-metadata"],
    )
    def test_silent_when_every_unjudged_path_needs_no_review(self, tmp_path, unjudged):
        """Widening the trigger must not cost it its silence.

        `changes_unjudged` is a mixed bag — non-Python source, prose, framework
        metadata, and files deleted in the diff all land there — so reading it
        wholesale would fire on every docs-only cycle, and a directive that
        prints every time is one the reader learns to skip. Only the paths that
        need review coverage count.
        """
        hook = _load_hook_module()
        path = self._write(
            tmp_path,
            json.dumps({"changes_referenced": [], "changes_unjudged": unjudged}),
        )
        assert hook._evidence_changed_judged_code(path) is False

    def test_framework_metadata_alone_does_not_fire_it(self, tmp_path):
        """The carve-out that keeps the widened trigger from firing every cycle.

        `changes_unjudged` carries a lot of `.prawduct/` in practice, because the
        methodology *requires* each chunk to update the change-log and the build
        plan — so governed work puts framework metadata in its own changed set by
        construction. Measured on this repo while recording the evidence for this
        chunk: 26 unjudged entries, none judgeable — 16 under `.prawduct/`, the
        other 10 unprotected prose (`documentation/`, `tests/scenarios/*.md`).
        **Two different branches of the predicate hold those two groups out**, and
        the fixture below must exercise the metadata one specifically. Reading
        `changes_unjudged` wholesale would print the directive on cycles that
        changed no product code at all, which is the failure the class docstring
        names.

        Deliberately NOT claimed: that `.prawduct/.test-evidence.json` is itself
        always present. `lib/core.py` scaffolds it into `.gitignore`, and
        `_changed_files` builds its untracked half with `--exclude-standard`, so
        in any onboarded repo it is in neither half. An earlier draft of this
        docstring asserted the opposite from a scratch repo that had no
        `.gitignore` — the fixture was unrepresentative, and the conclusion
        ("prints 100% of the time") over-priced the carve-out for whoever next
        weighs relaxing it.
        """
        hook = _load_hook_module()
        path = self._write(
            tmp_path,
            json.dumps(
                {
                    "changes_referenced": [],
                    "changes_unjudged": [
                        # NON-`.md`, and load-bearing for what this test claims to
                        # pin: only `METADATA_PREFIXES` can hold this one out. The
                        # two records below it are `.md`, so with the metadata
                        # branch deleted they fall through to the unprotected-prose
                        # branch and answer False anyway — an all-`.md` fixture
                        # cannot fail when the carve-out it is named for is removed.
                        ".prawduct/project-state.yaml",
                        ".prawduct/artifacts/build-plan-drift-burndown.md",
                        ".prawduct/change-log.md",
                    ],
                }
            ),
        )
        assert hook._evidence_changed_judged_code(path) is False

    def test_a_deleted_source_file_fires(self, tmp_path):
        """Admitted deliberately, recorded because it is not obvious.

        The overlay files diff-deleted paths under `changes_unjudged` alongside
        prose, and by the time this predicate reads the record there is nothing
        left on disk to tell the two apart — only the path. Classifying by path
        means a deleted `.py` fires, which is the right direction anyway: code
        leaving the tree is a change the suite should still vouch for.
        """
        hook = _load_hook_module()
        path = self._write(
            tmp_path,
            json.dumps({"changes_referenced": [], "changes_unjudged": ["gone.py"]}),
        )
        assert hook._evidence_changed_judged_code(path) is True

    def test_a_referenced_change_fires_even_where_the_path_is_unjudgeable(
        self, tmp_path
    ):
        """The widening is strict: every record that fired before still fires.

        `is_judgeable_path` calls anything under `.prawduct/` framework metadata
        and therefore not review-needing, so a `.prawduct/`-resident Python file
        in `changes_referenced` would go dark if the new predicate REPLACED the
        old one. It is an OR, not a substitution, and this pins that.
        """
        hook = _load_hook_module()
        path = self._write(
            tmp_path,
            json.dumps({"changes_referenced": [".prawduct/tools/gen.py"]}),
        )
        assert hook._evidence_changed_judged_code(path) is True

    def test_silent_when_field_absent(self, tmp_path):
        # A record written before the F4a overlay existed, or one whose overlay
        # was skipped (test-reference-verify missing), carries no field at all.
        # NOT "a restamp": `--no-rerun` re-runs the overlay and repopulates the
        # field against the current tree, so a restamp with judged changes in
        # the diff DOES fire. That claim was wrong in four places at once.
        hook = _load_hook_module()
        path = self._write(tmp_path, json.dumps({"passed": 3}))
        assert hook._evidence_changed_judged_code(path) is False

    @pytest.mark.parametrize(
        "payload",
        [
            "{not json at all",              # malformed
            json.dumps(["a", "list"]),       # valid JSON, wrong shape
            json.dumps({"changes_referenced": "lib/a.py"}),  # str, not list
        ],
        ids=["malformed", "not-a-dict", "field-not-a-list"],
    )
    def test_advice_fails_soft_on_unusable_records(self, tmp_path, payload):
        # Architecture norm: authority fails closed, ADVICE fails soft. The
        # evidence is already written and schema-valid by this point, so an
        # uncomputable trigger omits a hint — it must never raise into a
        # recording run.
        hook = _load_hook_module()
        assert hook._evidence_changed_judged_code(self._write(tmp_path, payload)) is False

    def test_missing_file_is_false_not_an_error(self, tmp_path):
        hook = _load_hook_module()
        assert hook._evidence_changed_judged_code(tmp_path / "absent.json") is False

    def test_directive_names_the_check_not_the_virtue(self):
        """The text must stay actionable prose, not an exhortation.

        Pins the three failure modes it exists to prevent — an unreachable
        fixture, a non-discriminating assertion, and a machine-dependent branch
        — plus the one-directional-mutation caveat that is the reason a builder
        who already ran a mutation pass still needs to read it.
        """
        hook = _load_hook_module()
        text = hook._GREEN_IS_EVIDENCE_DIRECTIVE
        assert "REACHES the subject" in text
        assert "cannot tell the two orderings apart" in text
        assert "happens to exist on this machine" in text
        assert "blind to what your change broke beside it" in text


# =============================================================================
# test-evidence record — declared commands, multi-environment, false-red guard
# =============================================================================


class TestDeclaredCommandEnvironments:
    """The record on-ramp for real environments: the interpreter fallback can
    no longer persist a wrong-environment false-red (0 passed + only errors
    refuses, with migration guidance), it nudges toward declaring the canonical
    command on every run, and ``test_commands:`` lets a polyglot product
    (backend + web + mobile) declare one environment-aware invocation per
    suite — each emits its own JUnit, counts aggregate into ONE record, and
    any launch failure fails the whole record rather than persisting partial
    evidence."""

    def _repo(self, tmp_path, name: str, state: str = "") -> Path:
        repo = tmp_path / name
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / "project-state.yaml").write_text(state)
        (repo / "README.md").write_text("t\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c1")
        _make_session_start(repo / ".prawduct", offset_seconds=-60)
        return repo

    @staticmethod
    def _junit_script(repo: Path, name: str, passed: int, failed: int = 0) -> str:
        """A tiny runner writing a JUnit report to argv[1] — stands in for an
        arbitrary toolchain (npm test, gradle, swift test) without depending
        on one being installed."""
        cases = "".join(
            f'<testcase classname="c" name="p{i}" time="0.01"/>'
            for i in range(passed)
        ) + "".join(
            f'<testcase classname="c" name="f{i}" time="0.01">'
            '<failure message="boom"/></testcase>'
            for i in range(failed)
        )
        xml = (
            f'<?xml version="1.0"?><testsuite name="{name}" '
            f'tests="{passed + failed}" failures="{failed}" errors="0" '
            f'skipped="0" time="1.0">{cases}</testsuite>'
        )
        script = repo / f"run_{name}.py"
        script.write_text(
            "import sys, pathlib\n"
            f"pathlib.Path(sys.argv[1]).write_text({xml!r})\n"
            + ("sys.exit(1)\n" if failed else "sys.exit(0)\n")
        )
        return f"python3 {script} {{junit_xml}}"

    def test_fallback_false_red_refused_nothing_persisted(self, tmp_path):
        # The upstream discodon signature: every test dies at collection under
        # the hook's interpreter (module not importable) -> 0 passed, errors>0.
        repo = self._repo(tmp_path, "falsered")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_env.py").write_text(
            "import module_that_does_not_exist_xyz_6f2r\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2, r.stderr
        assert "refusing to record" in r.stderr
        assert "test_command" in r.stderr  # the migration guidance names the knob
        assert not (repo / ".prawduct" / ".test-evidence.json").exists(), \
            "a wrong-environment run must never persist evidence"

    def test_fallback_pass_records_and_nudges(self, tmp_path):
        repo = self._repo(tmp_path, "fallbackok")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 0, r.stderr
        assert "falling back to the hook interpreter" in r.stderr  # the nudge
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 1 and ev["failed"] == 0

    def test_multi_commands_aggregate_one_record(self, tmp_path):
        repo = self._repo(tmp_path, "polyglot")
        a = self._junit_script(repo, "backend", passed=3)
        b = self._junit_script(repo, "web", passed=2)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_commands:\n  - {a}\n  - {b}\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 0, r.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 5 and ev["failed"] == 0
        assert " ; ".join([a, b]) == ev["command"]

    def test_multi_commands_red_records_honestly(self, tmp_path):
        # A DECLARED command's failures are real evidence (unlike the fallback
        # guard): recorded, and the exit mirrors the failing suite.
        repo = self._repo(tmp_path, "polyred")
        a = self._junit_script(repo, "backend", passed=3)
        b = self._junit_script(repo, "web", passed=1, failed=1)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_commands:\n  - {a}\n  - {b}\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 1, r.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 4 and ev["failed"] == 1

    def test_both_keys_rejected(self, tmp_path):
        repo = self._repo(
            tmp_path, "bothkeys",
            "test_command: python3 x.py {junit_xml}\n"
            "test_commands:\n  - python3 y.py {junit_xml}\n",
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2
        assert "BOTH" in r.stderr

    def test_missing_placeholder_names_the_command(self, tmp_path):
        repo = self._repo(
            tmp_path, "noplaceholder",
            "test_commands:\n"
            "  - python3 a.py {junit_xml}\n"
            "  - python3 b.py\n",
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2
        assert "python3 b.py" in r.stderr and "{junit_xml}" in r.stderr

    def test_launch_failure_persists_nothing(self, tmp_path):
        repo = self._repo(tmp_path, "launchfail")
        a = self._junit_script(repo, "backend", passed=3)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_commands:\n  - {a}\n  - /nonexistent/runner_6f2r {{junit_xml}}\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2
        assert "could not launch" in r.stderr
        assert not (repo / ".prawduct" / ".test-evidence.json").exists(), \
            "no partial multi-environment evidence"

    def test_from_counts_rejected_with_declared_list(self, tmp_path):
        repo = self._repo(
            tmp_path, "countsreject",
            "test_commands:\n  - python3 a.py {junit_xml}\n",
        )
        r = _run_in(repo, "test-evidence", "record",
                    "--from-counts", "passed=1", "failed=0", "skipped=0")
        assert r.returncode == 2
        assert "--from-junit" in r.stderr  # redirected to the machine-backed ramp


    def test_flow_style_list_refused_not_silently_ignored(self, tmp_path):
        # The natural-but-unsupported spelling must refuse loudly — silently
        # degrading to the interpreter fallback could persist GREEN
        # partial-environment evidence for an invocation nobody declared.
        repo = self._repo(
            tmp_path, "flowstyle",
            "test_commands: [python3 a.py {junit_xml}, python3 b.py {junit_xml}]\n",
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2
        assert "block sequence" in r.stderr
        assert not (repo / ".prawduct" / ".test-evidence.json").exists()

    def test_comment_lines_inside_list_do_not_truncate(self, tmp_path):
        # A full-line comment (even at column 0) between items must not end
        # the list — truncation would silently skip environments while the
        # record claimed full evidence.
        repo = self._repo(tmp_path, "commented")
        a = self._junit_script(repo, "backend", passed=3)
        b = self._junit_script(repo, "web", passed=2)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_commands:\n  - {a}\n# the web half\n  - {b}\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 0, r.stderr
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 5

    def test_unparseable_report_persists_nothing(self, tmp_path):
        # The "unparseable report fails the whole record" half of the
        # no-partial-evidence guarantee, pinned.
        repo = self._repo(tmp_path, "garbage")
        a = self._junit_script(repo, "backend", passed=3)
        bad = repo / "run_bad.py"
        bad.write_text(
            "import sys, pathlib\n"
            "pathlib.Path(sys.argv[1]).write_text('this is not xml')\n"
        )
        (repo / ".prawduct" / "project-state.yaml").write_text(
            f"test_commands:\n  - {a}\n  - python3 {bad} {{junit_xml}}\n"
        )
        r = _run_in(repo, "test-evidence", "record")
        assert r.returncode == 2
        assert "could not parse" in r.stderr
        assert not (repo / ".prawduct" / ".test-evidence.json").exists()

    def test_repeated_from_junit_aggregates(self, tmp_path):
        # The ingest on-ramp scales with test_commands: run each command
        # yourself, ingest every report in one record.
        repo = self._repo(tmp_path, "multijunit")
        r1 = repo / "a.xml"
        r1.write_text('<testsuite name="a" tests="3" failures="0" errors="0" '
                      'skipped="0" time="1.0"/>')
        r2 = repo / "b.xml"
        r2.write_text('<testsuite name="b" tests="2" failures="1" errors="0" '
                      'skipped="0" time="1.0"/>')
        r = _run_in(repo, "test-evidence", "record",
                    "--from-junit", str(r1), "--from-junit", str(r2))
        assert r.returncode == 1, r.stderr  # a failure in any report
        ev = json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())
        assert ev["passed"] == 4 and ev["failed"] == 1
        assert str(r1) in ev["command"] and str(r2) in ev["command"]
        # the caller's reports are never deleted
        assert r1.exists() and r2.exists()


    def test_anomalous_block_lines_refuse_whole_declaration(self, tmp_path):
        # A bare dash or a wrapped command's continuation line makes the WHOLE
        # declaration unparseable (loud exit 2) — never a partial list that
        # silently skips environments.
        for name, state in (
            ("baredash", "test_commands:\n  - python3 a.py {junit_xml}\n  -\n  - python3 b.py {junit_xml}\n"),
            ("wrapped", "test_commands:\n  - python3 a.py\n    {junit_xml}\n"),
        ):
            repo = self._repo(tmp_path, name, state)
            r = _run_in(repo, "test-evidence", "record")
            assert r.returncode == 2, f"{name}: {r.stderr}"
            assert "block sequence" in r.stderr, name
            assert not (repo / ".prawduct" / ".test-evidence.json").exists(), name
