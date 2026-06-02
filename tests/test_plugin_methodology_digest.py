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


def _run_digest(plugin_root: Path | None) -> subprocess.CompletedProcess:
    """Invoke hooks/digest.py as Claude Code would (CLAUDE_PLUGIN_ROOT set), or
    with it absent to exercise the __file__ fallback when plugin_root is None.

    HOME is kept outside any repo and PYTHONDONTWRITEBYTECODE=1 so the run leaves
    no caches behind (learnings: HOME=repo leaks the pyc cache into the tree).
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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
        copies = [p for p in ROOT.rglob("session-digest.md") if ".git" not in p.parts]
        assert copies == [DIGEST_SRC], f"expected one canonical digest, found {copies}"


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
        assert any(c.rstrip().endswith("clear") for c in cmds)


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
