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

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
DIGEST_HOOK = ROOT / "hooks" / "digest.py"
DIGEST_SRC = ROOT / "methodology" / "session-digest.md"
SLIM_DIGEST_SRC = ROOT / "methodology" / "session-digest-slim.md"

# The four methodology guides, read via `/prawduct:methodology <topic>`.
PHASES = ("building", "discovery", "planning", "reflection")

# Claude Code spills additionalContext over this many characters to a file
# instead of injecting it inline. The digest must stay comfortably under it.
ADDITIONAL_CONTEXT_INLINE_LIMIT = 10_000


def _canonical_digest_copies(root: Path = ROOT) -> list[Path]:
    """All `session-digest.md` files under `root`, excluding scratch trees.

    Excludes `.git/` and `.claude/` — the latter holds worktree-isolated
    workflow checkouts (`.claude/worktrees/wf_*/`) that carry a full duplicate
    methodology tree. Those copies are a nested checkout, not a rogue
    non-canonical source, so they must not fail the single-source assertion
    (TST-9K4W). Filtered on path components RELATIVE to `root` — the checkout
    itself may live under a `.claude/worktrees/` session worktree, and an
    absolute-parts filter would exclude the canonical copy along with the strays.
    """
    return sorted(
        p
        for p in root.rglob("session-digest.md")
        if ".git" not in p.relative_to(root).parts
        and ".claude" not in p.relative_to(root).parts
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
    env["CLAUDE_PROJECT_DIR"] = str(project_dir if project_dir is not None else REPO_ROOT)
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

    def test_slim_source_exists_and_nonempty(self):
        # review-fixes Chunk 4: the slim framework-repo variant is a second
        # canonical document, not a runtime derivation of the full digest.
        assert SLIM_DIGEST_SRC.is_file(), "the slim session digest must be bundled"
        assert SLIM_DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_slim_source_is_one_canonical_copy(self):
        copies = sorted(
            p
            for p in ROOT.rglob("session-digest-slim.md")
            if ".git" not in p.relative_to(ROOT).parts
            and ".claude" not in p.relative_to(ROOT).parts
        )
        assert copies == [SLIM_DIGEST_SRC], f"expected one canonical slim digest, found {copies}"

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
        # Renegotiated in review-fixes Chunk 4: the default project_dir is ROOT —
        # the prawduct framework repo itself — so the emitted context is now the
        # SLIM variant (CLAUDE.md already carries what the full digest restates).
        # The full-digest-verbatim contract moved to the product fixture in
        # TestDigestVariantSelection.
        result = _run_digest(ROOT)
        ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert ctx == SLIM_DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_additional_context_under_inline_limit(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        assert len(ctx) < ADDITIONAL_CONTEXT_INLINE_LIMIT, (
            f"digest is {len(ctx)} chars — over the {ADDITIONAL_CONTEXT_INLINE_LIMIT} "
            "inline threshold; Claude Code would spill it to a file"
        )

    @pytest.mark.parametrize("src", [DIGEST_SRC, SLIM_DIGEST_SRC], ids=["full", "slim"])
    def test_every_digest_variant_is_under_the_inline_limit(self, src: Path):
        """Both variants, pinned at the SOURCE — not just whichever one ROOT emits.

        The test above runs `_run_digest(ROOT)`, and since the variant
        renegotiation ROOT emits the SLIM digest — so the FULL digest, the one
        injected into every product session and the sole carrier of framework
        defaults for thin-anchor repos, was pinned by nothing. It reached 11,143
        chars (11% over) before this assertion existed. `test_slim_budget_at
        _most_half_of_full` is not a substitute: it gets *easier* to satisfy as
        the full digest grows, so it cannot brake growth in the wider-blast-radius
        file.

        Asserted against the stripped source because that is what the hook emits
        (`test_additional_context_matches_source` pins the equality).
        """
        emitted = src.read_text(encoding="utf-8").strip()
        assert len(emitted) < ADDITIONAL_CONTEXT_INLINE_LIMIT, (
            f"{src.name} is {len(emitted)} chars — over the "
            f"{ADDITIONAL_CONTEXT_INLINE_LIMIT} inline threshold; Claude Code "
            "would spill it to a file instead of injecting it. Trim or relocate; "
            "the digests are the tightest-budgeted surface in the framework, not "
            "a free destination for text trimmed out of a methodology guide."
        )

    def test_digest_points_at_load_bearing_readers(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        # The digest's job is to route to on-demand guidance and name the gate.
        assert "/prawduct:methodology building" in ctx, "must point to the read-before-coding guide"
        assert "/prawduct:methodology" in ctx, "must point to the methodology index"
        assert "Critic" in ctx and "Stop hook" in ctx, "must name the enforcement"

    @pytest.mark.parametrize("src", [DIGEST_SRC, SLIM_DIGEST_SRC], ids=["full", "slim"])
    def test_both_variants_carry_load_bearing_pointers(self, src):
        # Whatever variant a session receives, it must route to the
        # read-before-coding guide, the index, and name the enforcement.
        text = src.read_text(encoding="utf-8")
        assert "/prawduct:methodology building" in text
        assert "/prawduct:methodology" in text
        assert "Critic" in text and "Stop hook" in text

    @pytest.mark.parametrize("src", [DIGEST_SRC, SLIM_DIGEST_SRC], ids=["full", "slim"])
    def test_both_variants_surface_the_report_bug_channel(self, src):
        # Discoverability of the upstream-bug-reporting channel (regression guard
        # against a silent trim dropping the pointer). The full digest reaches
        # products (the filing side); the slim reaches the framework repo.
        assert "/prawduct:report-bug" in src.read_text(encoding="utf-8")

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


class TestDigestVariantSelection:
    """review-fixes Chunk 4: the framework repo's always-loaded CLAUDE.md already
    carries 40-50% of the full digest nearly 1:1 (principles roster, Critic/Stop
    explanation, attribution rule), so a session governed by the framework repo
    itself gets a SLIM variant — pointers plus only the rules CLAUDE.md does not
    restate. Every product repo keeps the FULL digest verbatim: it is the only
    carrier of framework defaults for thin-anchor CLAUDE.md repos. Detection is
    the plugin manifest (`.claude-plugin/plugin.json` with name=prawduct) at the
    governed repo's root; every anomaly fails safe to the full digest.
    """

    @staticmethod
    def _framework_fixture(tmp_path: Path, manifest: str | None = '{"name": "prawduct"}') -> Path:
        (tmp_path / ".prawduct").mkdir()
        if manifest is not None:
            mdir = tmp_path / ".claude-plugin"
            mdir.mkdir()
            (mdir / "plugin.json").write_text(manifest, encoding="utf-8")
        return tmp_path

    def _emitted(self, project_dir: Path) -> str:
        result = _run_digest(ROOT, project_dir=project_dir)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_framework_fixture_gets_slim_variant(self, tmp_path):
        ctx = self._emitted(self._framework_fixture(tmp_path))
        assert ctx == SLIM_DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_product_fixture_gets_full_digest_verbatim(self, tmp_path):
        # A product repo (.prawduct/ but no plugin manifest) must receive the
        # full digest unchanged — it is the sole carrier of framework defaults.
        ctx = self._emitted(self._framework_fixture(tmp_path, manifest=None))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_other_plugin_manifest_gets_full_digest(self, tmp_path):
        # A product that happens to develop its OWN plugin is not the framework.
        ctx = self._emitted(self._framework_fixture(tmp_path, manifest='{"name": "my-plugin"}'))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_malformed_manifest_fails_safe_to_full_digest(self, tmp_path):
        ctx = self._emitted(self._framework_fixture(tmp_path, manifest="{not json"))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_non_dict_manifest_fails_safe_to_full_digest(self, tmp_path):
        ctx = self._emitted(self._framework_fixture(tmp_path, manifest='["prawduct"]'))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_framework_repo_falls_back_to_full_when_slim_missing(self, tmp_path):
        # An older cached plugin copy may not bundle the slim file yet. A
        # framework session must still get A digest — never silence.
        plugin = tmp_path / "plugin"
        (plugin / "methodology").mkdir(parents=True)
        (plugin / "methodology" / "session-digest.md").write_text("full digest body\n")
        repo = tmp_path / "repo"
        repo.mkdir()
        framework = self._framework_fixture(repo)
        result = _run_digest(plugin, project_dir=framework)
        assert result.returncode == 0, result.stderr
        ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert ctx == "full digest body"

    def test_slim_budget_at_most_half_of_full(self):
        # The slim variant's reason to exist is the token saving; pin it.
        slim = len(SLIM_DIGEST_SRC.read_text(encoding="utf-8"))
        full = len(DIGEST_SRC.read_text(encoding="utf-8"))
        assert slim <= full * 0.5, (
            f"slim digest is {slim} chars vs full {full} — over the 50% budget"
        )


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
    """prose-diet Chunk 03 folded the four thin delegator skills
    (skills/{building,discovery,planning,reflection}) into the methodology
    index — one reader skill, four canonical guides, zero duplicate routing
    surfaces. These tests pin the folded shape."""

    def test_methodology_index_has_description_frontmatter(self):
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---"), "methodology/SKILL.md must open with frontmatter"
        front = text.split("---", 2)[1]
        assert "description:" in front, "methodology skill requires a description"

    @pytest.mark.parametrize("phase", PHASES)
    def test_delegator_skill_stays_deleted(self, phase):
        # The fold is one-way: a re-created skills/<phase>/ delegator would
        # resurrect the duplicate surface the diet removed.
        assert not (ROOT / "skills" / phase).exists(), (
            f"skills/{phase}/ was folded into /prawduct:methodology {phase}; "
            "do not re-create the delegator"
        )

    @pytest.mark.parametrize("phase", PHASES)
    def test_index_routes_to_canonical_source(self, phase):
        # The index is now the reader: it must route each topic to the
        # canonical plugin-root guide, and that guide must exist.
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        ref = f"${{CLAUDE_SKILL_DIR}}/../../methodology/{phase}.md"
        assert ref in text, f"methodology index must read the canonical {ref}"
        assert (ROOT / "methodology" / f"{phase}.md").is_file()

    def test_index_routes_to_principles(self):
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        assert "docs/principles.md" in text, "index must route to the principles"

    def test_index_carries_stop_before_code_line(self):
        # The building delegator's load-bearing line survives the fold here.
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        assert "before writing ANY code" in text or "before writing any code" in text


class TestAgentStance:
    """The agent stance operationalizes the principles into communication and
    conduct. prose-diet Chunk 03 (STN-4W7R part a) made the always-injected
    session digest its SOLE operational surface — methodology/agent-stance.md
    was folded away — and reframed it advisor-first: the expert take (risks,
    stronger/simpler alternative, recommendation) leads; compliance is second.
    The digest is the carrier (not a plugin Output Style) because a force-for-
    plugin output style hard-overrides a consumer's own style and doesn't
    compose, whereas the SessionStart digest is unconditional AND composable."""

    def test_long_form_stance_doc_stays_deleted(self):
        assert not (ROOT / "methodology" / "agent-stance.md").exists(), (
            "agent-stance.md was folded into the digest stance block; "
            "do not re-create the long form"
        )

    def test_digest_leads_advisor_first(self):
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "expert take" in digest, "stance block must lead advisor-first"
        assert "compliance second" in digest

    def test_digest_carries_condensed_stance(self):
        # The always-on digest is the stance's reach-every-session carrier:
        # the checkable bars survive the fold (tolerant substring checks).
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "Verify, don't guess" in digest, "digest must carry the condensed stance"
        assert "Stress-test before agreeing" in digest
        assert "principles.md" in digest, "stance block must point back at the principles"

    def test_slim_digest_carries_condensed_stance(self):
        slim = SLIM_DIGEST_SRC.read_text(encoding="utf-8")
        assert "expert take" in slim
        assert "Verify, don't guess" in slim

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


class TestDigestCarriesBacklogDiscipline:
    """The backlog-rework default behaviors (use the skill, archive don't
    strikethrough, early-stage routes to discovery) must ride the always-injected
    digest — the only surface every already-onboarded repo re-reads (the same
    carrier rationale as the attribution default). Guards against a budget-trim
    silently deleting the rule. Tolerant substring checks."""

    def test_digest_carries_backlog_routing(self):
        digest = DIGEST_SRC.read_text(encoding="utf-8")
        assert "/prawduct:backlog" in digest, "digest must route backlog work to the skill"
        assert "strikethrough" in digest, "digest must state the archive (not strikethrough) discipline"
        assert "stage" in digest and "discovery" in digest, (
            "digest must state early-stage items route to discovery, not code"
        )


class TestIsFrameworkRepoCandidates:
    """`is_framework_repo` decides slim-vs-full digest, and the move broke it once already.

    It originally keyed on `.claude-plugin/plugin.json` at the repo root. v3.1.1 relocated that
    manifest into `plugin/`, so the framework repo silently began classifying as a product repo and
    receiving the full digest -- no error, no test failure, just the wrong variant. It now checks
    three locations, but only the first is reachable in this repo, so the other two were shipping
    unexercised. These fixtures cover each independently. (Critic, 2026-07-21.)
    """

    @staticmethod
    def _digest_mod():
        import importlib.util
        spec = importlib.util.spec_from_file_location("prawduct_digest_hook", DIGEST_HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _write(self, root: Path, rel: str) -> None:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"name": "prawduct"}), encoding="utf-8")

    @pytest.mark.parametrize("rel", [
        ".claude-plugin/marketplace.json",          # current layout (v3.1.1+)
        "plugin/.claude-plugin/plugin.json",        # relocated plugin manifest
        ".claude-plugin/plugin.json",               # pre-v3.1.1, kept for older checkouts
    ])
    def test_each_candidate_location_classifies_as_framework(self, tmp_path, rel):
        self._write(tmp_path, rel)
        assert self._digest_mod().is_framework_repo(tmp_path), (
            f"{rel} must identify the framework repo -- a miss here silently swaps the digest variant"
        )

    def test_a_product_repo_is_not_the_framework(self, tmp_path):
        (tmp_path / ".prawduct").mkdir()
        assert not self._digest_mod().is_framework_repo(tmp_path)

    def test_a_foreign_manifest_is_not_the_framework(self, tmp_path):
        self._write(tmp_path, ".claude-plugin/marketplace.json")
        (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"name": "someone-else"}), encoding="utf-8")
        assert not self._digest_mod().is_framework_repo(tmp_path), (
            "fail-safe: an unrelated plugin manifest must not classify as prawduct"
        )
