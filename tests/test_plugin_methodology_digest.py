"""Tests for the v2.0.0 plugin Chunk 6: methodology readers + session digest.

These enforce the load-bearing invariants of the guidance layer (design §4):

  * The session digest is injected at session start via the SessionStart
    ``additionalContext`` channel — exact JSON shape verified against the hooks
    reference, kept under the 10k-char spill threshold so it stays inline.
  * The digest hook is read-only and never breaks session start (design §2 —
    the plugin ships immutable read-only code; a banner/digest failure must not
    block the session).
  * Methodology is readable via plugin reader skills that point at ONE canonical
    source at the plugin root (``${CLAUDE_SKILL_DIR}/../../methodology/*.md``) —
    no per-skill copy, no committed repo copy in a consuming product.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
DIGEST_HOOK = ROOT / "hooks" / "digest.py"
DIGEST_SRC = ROOT / "methodology" / "session-digest.md"

# The four methodology guides, each surfaced by a phase reader skill.
PHASES = ("building", "discovery", "planning", "reflection")
READER_SKILLS = ("methodology", *PHASES)

# Claude Code spills additionalContext over this many characters to a file
# instead of injecting it inline. The digest must stay comfortably under it.
ADDITIONAL_CONTEXT_INLINE_LIMIT = 10_000


def _canonical_digest_copies(root: Path = ROOT) -> list[Path]:
    """All `session-digest.md` files under `root`, excluding scratch trees.

    Excludes `.git/` and `.claude/` — the latter holds worktree-isolated
    workflow checkouts (`.claude/worktrees/wf_*/`) that carry a full duplicate
    methodology tree. Those copies are a nested checkout, not a rogue
    non-canonical source, so they must not fail the single-source assertion
    (TST-9K4W). Filtered on the path COMPONENT, not a prefix, so it matches at
    any depth and never trips on an unrelated file literally named `.claude`.
    """
    return sorted(
        p
        for p in root.rglob("session-digest.md")
        if ".git" not in p.parts and ".claude" not in p.parts
    )


def _run_digest(
    plugin_root: Path | None, project_dir: Path | None = None
) -> subprocess.CompletedProcess:
    """Invoke hooks/digest.py as Claude Code would (CLAUDE_PLUGIN_ROOT set), or
    with it absent to exercise the __file__ fallback when plugin_root is None.

    CLAUDE_PROJECT_DIR is set explicitly — defaulting to the plugin repo ROOT,
    which is itself a Prawduct repo (has .prawduct/) — so the .prawduct/ repo gate
    is deterministic regardless of the ambient environment. Pass a project_dir
    without a .prawduct/ to exercise the non-Prawduct-repo silence path.

    HOME is kept outside any repo and PYTHONDONTWRITEBYTECODE=1 so the run leaves
    no caches behind (learnings: HOME=repo leaks the pyc cache into the tree).
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CLAUDE_PROJECT_DIR"] = str(project_dir if project_dir is not None else ROOT)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(
        [sys.executable, str(DIGEST_HOOK)],
        capture_output=True, text=True, env=env, timeout=20,
    )


class TestDigestSource:
    def test_source_exists_and_nonempty(self):
        assert DIGEST_SRC.is_file(), "the canonical session digest must be bundled"
        assert DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_source_is_one_canonical_copy(self):
        # The digest lives once, at the plugin root — not duplicated into a skill
        # dir. (Single source of truth; the readers serve the full guides.)
        copies = _canonical_digest_copies()
        assert copies == [DIGEST_SRC], f"expected one canonical digest, found {copies}"

    def test_canonical_copy_check_ignores_claude_worktrees(self, tmp_path: Path):
        # TST-9K4W: a session-digest.md inside a .claude/worktrees/ checkout must
        # NOT count as a second canonical copy (it is a nested workflow checkout).
        meth = tmp_path / "methodology"
        meth.mkdir()
        canonical = meth / "session-digest.md"
        canonical.write_text("digest\n")
        stray = tmp_path / ".claude" / "worktrees" / "wf_x" / "methodology"
        stray.mkdir(parents=True)
        (stray / "session-digest.md").write_text("digest copy\n")
        assert _canonical_digest_copies(tmp_path) == [canonical]


class TestDigestHook:
    def test_emits_sessionstart_additional_context(self):
        result = _run_digest(ROOT)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        out = payload["hookSpecificOutput"]
        assert out["hookEventName"] == "SessionStart"
        assert out["additionalContext"].strip(), "additionalContext must be non-empty"

    def test_additional_context_matches_source(self):
        result = _run_digest(ROOT)
        ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_additional_context_under_inline_limit(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        assert len(ctx) < ADDITIONAL_CONTEXT_INLINE_LIMIT, (
            f"digest is {len(ctx)} chars — over the {ADDITIONAL_CONTEXT_INLINE_LIMIT} "
            "inline threshold; Claude Code would spill it to a file"
        )

    def test_digest_points_at_load_bearing_readers(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        # The digest's job is to route to on-demand guidance and name the gate.
        assert "/prawduct:building" in ctx, "must point to the read-before-coding guide"
        assert "/prawduct:methodology" in ctx, "must point to the methodology index"
        assert "Critic" in ctx and "Stop hook" in ctx, "must name the enforcement"

    def test_resolves_root_without_env(self):
        # No CLAUDE_PLUGIN_ROOT -> falls back to hooks/ parent (the plugin root).
        result = _run_digest(None)
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)["hookSpecificOutput"]
        assert out["hookEventName"] == "SessionStart"

    def test_never_breaks_session_start_when_source_missing(self, tmp_path):
        # Empty plugin root (no methodology/session-digest.md) -> exit 0, no JSON.
        result = _run_digest(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == "", "no digest -> emit nothing, never crash"

    def test_hook_is_read_only(self, tmp_path):
        # The plugin ships read-only code (§2). Running the hook against a fake
        # plugin root must not create, modify, or delete any file there.
        meth = tmp_path / "methodology"
        meth.mkdir()
        (meth / "session-digest.md").write_text("digest body\n")

        def snapshot() -> dict[str, bytes]:
            return {
                str(p.relative_to(tmp_path)): p.read_bytes()
                for p in tmp_path.rglob("*") if p.is_file()
            }

        before = snapshot()
        result = _run_digest(tmp_path)
        assert result.returncode == 0
        assert snapshot() == before, "digest hook wrote to the plugin tree — must be read-only"

    def test_hook_has_python_shebang(self):
        assert DIGEST_HOOK.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


class TestDigestRepoGate:
    """The plugin is user-scoped, so the digest SessionStart hook fires in every
    repo the user opens. It must inject the governance digest ONLY in a
    Prawduct-governed repo (one with a .prawduct/ dir) and stay silent everywhere
    else — mirroring the banner (hooks/banner.py) and the Stop hook (cmd_stop),
    which already gate on .prawduct/. This is the fix for the user-scoped plugin
    leaking governance into unrelated repos.
    """

    def test_emits_in_prawduct_repo(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        result = _run_digest(ROOT, project_dir=tmp_path)
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)["hookSpecificOutput"]
        assert out["hookEventName"] == "SessionStart"
        assert out["additionalContext"].strip()

    def test_silent_in_non_prawduct_repo(self, tmp_path):
        # No .prawduct/ -> emit nothing (no additionalContext injected), exit 0.
        result = _run_digest(ROOT, project_dir=tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            "digest leaked into a non-Prawduct repo — it must stay silent without .prawduct/"
        )

    def test_silent_run_writes_nothing(self, tmp_path):
        # The gate is read-only: a silent run must not scaffold .prawduct/ or any file.
        before = {p for p in tmp_path.rglob("*")}
        _run_digest(ROOT, project_dir=tmp_path)
        assert {p for p in tmp_path.rglob("*")} == before, "gate must not write to the repo"
        assert not (tmp_path / ".prawduct").exists()


class TestDigestWiring:
    @pytest.fixture(scope="class")
    def sessionstart(self):
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        return data["hooks"]["SessionStart"]

    def _digest_entries(self, sessionstart):
        return [
            e for e in sessionstart
            if any("digest.py" in h["command"] for h in e["hooks"])
        ]

    def test_digest_wired_via_plugin_root(self, sessionstart):
        cmds = [h["command"] for e in sessionstart for h in e["hooks"]]
        assert any(
            "${CLAUDE_PLUGIN_ROOT}" in c and "hooks/digest.py" in c for c in cmds
        ), "SessionStart must run the bundled digest via ${CLAUDE_PLUGIN_ROOT}"

    def test_digest_matcher_includes_compact(self, sessionstart):
        # Unlike the clear/briefing hook (a state-reset, excluded on compact), the
        # digest is pure guidance — re-injecting it after a compaction is valuable.
        entries = self._digest_entries(sessionstart)
        assert entries, "no digest SessionStart entry found"
        for e in entries:
            matcher = e["matcher"]
            for trigger in ("startup", "resume", "clear", "compact"):
                assert trigger in matcher, f"digest matcher should include {trigger!r}"

    def test_digest_does_not_clobber_banner_or_briefing(self, sessionstart):
        # Multiple SessionStart hooks compose; adding the digest must not drop the
        # Chunk-1 banner or the Chunk-5 clear briefing.
        cmds = [h["command"] for e in sessionstart for h in e["hooks"]]
        assert any("banner.py" in c for c in cmds)
        # The clear briefing now carries `--session-start` (CRT-3X9D guard bypass).
        assert any("bin/prawduct-hook" in c and "clear" in c.split() for c in cmds)


class TestReaderSkills:
    @pytest.mark.parametrize("skill", READER_SKILLS)
    def test_skill_has_description_frontmatter(self, skill):
        text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---"), f"{skill}/SKILL.md must open with frontmatter"
        front = text.split("---", 2)[1]
        assert "description:" in front, f"{skill} skill requires a description"

    @pytest.mark.parametrize("phase", PHASES)
    def test_phase_reader_points_at_canonical_source(self, phase):
        text = (ROOT / "skills" / phase / "SKILL.md").read_text(encoding="utf-8")
        ref = f"${{CLAUDE_SKILL_DIR}}/../../methodology/{phase}.md"
        assert ref in text, f"{phase} reader must read the canonical {ref}"
        # The traversal target must actually exist at the plugin root (one source).
        target = ROOT / "skills" / phase / ".." / ".." / "methodology" / f"{phase}.md"
        assert target.resolve() == (ROOT / "methodology" / f"{phase}.md").resolve()
        assert target.is_file()

    @pytest.mark.parametrize("phase", PHASES)
    def test_phase_reader_holds_no_local_copy(self, phase):
        # Single source of truth: the reader points at the plugin-root guide and
        # does NOT bundle its own duplicate (which would drift).
        skill_dir = ROOT / "skills" / phase
        assert not (skill_dir / f"{phase}.md").exists(), (
            f"{phase} skill must not carry a local methodology copy"
        )

    def test_index_routes_to_every_guide(self):
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        for phase in PHASES:
            assert f"methodology/{phase}.md" in text, f"index must route to {phase}"
        assert "docs/principles.md" in text, "index must route to the principles"
        assert "methodology/agent-stance.md" in text, "index must route to the agent stance"


class TestAgentStance:
    """The agent stance (rigor-and-stance Chunk 02) operationalizes the principles
    into communication/conduct. Its canonical home is methodology/agent-stance.md;
    the always-on session digest carries a condensed version. The digest is the
    carrier (not a plugin Output Style) because a force-for-plugin output style
    HARD-OVERRIDES a consumer's own style and doesn't compose, whereas the
    SessionStart digest is unconditional AND composable (verified against the
    Claude Code output-styles docs during design)."""

    STANCE_SRC = ROOT / "methodology" / "agent-stance.md"

    def test_stance_doc_exists_and_nonempty(self):
        assert self.STANCE_SRC.is_file(), "agent-stance.md must be bundled"
        assert self.STANCE_SRC.read_text(encoding="utf-8").strip()

    def test_stance_doc_links_to_principles(self):
        # The stance operationalizes the principles, so it must point back at them.
        assert "principles.md" in self.STANCE_SRC.read_text(encoding="utf-8")

    def test_digest_carries_condensed_stance(self):
        # The always-on digest is the stance's reach-every-session carrier: it must
        # point at the full doc and carry the condensed directives (tolerant
        # substring checks, mirroring TestCommitAttributionDefault).
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "agent-stance.md" in digest, "digest must point at the full stance doc"
        assert "Verify, don't guess" in digest, "digest must carry the condensed stance"
        assert "Stress-test before agreeing" in digest

    def test_digest_carries_rigor_scaling(self):
        # rigor-and-stance Chunk 03 (digest sweep): the always-on layer carries the
        # requirements-rigor headline and routes to the full model on-demand.
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "Calibrate Rigor" in digest, "digest must route to the full rigor model"
        assert "volatility" in digest.lower(), "digest must name the volatility driver"


class TestCommitAttributionDefault:
    """The framework default is NO commit/PR attribution trailers, opt-in via
    ``project-preferences.md`` (``Commit attribution``). The carrier is the
    always-injected session digest — it reaches every product session including
    migrated repos, whose CLAUDE.md is only the thin anchor and whose
    place-once ``project-preferences.md`` is never regenerated, making the digest
    their SOLE carrier. The digest is deliberately budget-bound (see
    ``test_additional_context_under_inline_limit``), so the rule lives there once
    and is not duplicated across the methodology guides. Tolerant substring checks,
    not verbatim prose.
    """

    PROJECT_PREFS = ROOT / "templates" / "project-preferences.md"

    def test_digest_carries_no_attribution_default(self):
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "Co-Authored-By" in digest, "digest must name the trailer it suppresses"
        assert "Commit attribution" in digest, "digest must point at the opt-in preference"

    def test_project_preferences_defines_opt_in_toggle(self):
        lines = self.PROJECT_PREFS.read_text(encoding="utf-8").splitlines()
        toggle = next((ln for ln in lines if "Commit attribution" in ln), None)
        assert toggle is not None, "Workflow section must define the Commit attribution toggle"
        assert "none" in toggle, "the documented default must be none"
        assert "co-authored" in toggle, "the toggle must document the opt-in value"
