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

# The methodology guides, read via `/prawduct:methodology <topic>`. `delegation`
# joined on 2026-08-21; `principles` and `norms` are deliberately absent — they
# route to `docs/`, not to a guide, and the overview list below names phases.
PHASES = ("building", "discovery", "planning", "reflection", "session-hygiene", "delegation")

# Claude Code spills additionalContext over this many characters to a file
# instead of injecting it inline. The digest must stay comfortably under it.
ADDITIONAL_CONTEXT_INLINE_LIMIT = 10_000

#: The headroom the digest KEEPS, reserved for the next framework-wide default.
#:
#: Decided 2026-09-01 (#630), after a relief pass found the digest at 9,987 of
#: 10,000 -- thirteen characters, measured. Nothing was broken and the ceiling
#: is loud rather than silent, so the problem was never a failure; it was that
#: the next default reaching migrated and thin-anchor repos would have arrived
#: with no room, leaving two levers: relocate under deadline pressure, or
#: "merge" two rules that are not one rule. The second is a quality regression
#: dressed as a trim, and it is what a last-minute squeeze produces.
#:
#: So the reserve is stated rather than discovered. This assertion is a POLICY
#: ratchet and can be declared past by an owner ruling; 10,000 is a harness
#: threshold and cannot. Crossing 9,500 does not mean the digest is broken --
#: it means the next author is spending the reserve, and owes the relief pass
#: FIRST, with time to judge what belongs where.
#:
#: Relief is a placement decision, never a deletion: content leaves the digest
#: for a named on-demand surface with a stated retrieval path (§ Agent Stance
#: in `docs/principles.md` is the worked example), and a rule merge counts only
#: when re-derivation proves the two were one rule (the BP7 precedent).
DIGEST_HEADROOM_RESERVE = 500

#: The per-section placement decision, taken once (#630) so the next author
#: inherits a judgement instead of making one under deadline pressure.
#:
#: The test is "would a THIN-ANCHOR repo be wrong without this?" -- a repo whose
#: CLAUDE.md is only the governance anchor learns the framework defaults here or
#: nowhere. That is a question about the reader's position, not about
#: importance: a rule that has to FIRE unprompted is inline; a rule a reader
#: looks up once they know it exists can live one pointer away.
DIGEST_SECTION_PLACEMENT = {
    "(preamble)": (
        "inline -- names the governing framework and the read-on-demand model; "
        "a repo that does not know it is governed asks for none of the rest"
    ),
    "How work is governed here": (
        "inline -- the size/rigor scaling and the read-building-first trigger; "
        "nothing routes to the guides without it"
    ),
    "The hardest rules (these degrade at scale — hold them)": (
        "inline -- each fires unprompted, mid-work, on a surface with no "
        "opt-out. Individual bullets already point out for their detail "
        "(reflection.md, docs/waivers.md, review-cycle.md); what stays here is "
        "the trigger and the shortest true form of the rule"
    ),
    "Principles": (
        "inline -- a 26-name roster in six groups, already the compressed form "
        "of docs/principles.md"
    ),
    "How the agent shows up (stance)": (
        "SPLIT -- the lead position stays inline (it governs the first move on "
        "every substantive ask); the nine bars RELOCATED to docs/principles.md "
        "§ Agent Stance, reached by the pointer here and by "
        "/prawduct:methodology principles. A bar is consulted when you are "
        "checking yourself against it, which is a lookup, not a trigger"
    ),
    "Enforcement": (
        "inline -- names the Stop hook gates; a blocked session with no idea "
        "what blocked it is the failure"
    ),
    "Read on demand": (
        "inline -- this IS the retrieval path every relocation above depends on"
    ),
}


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
        # One digest for every governed repo, the framework repo included, so
        # what ROOT emits is the canonical source verbatim. Both repo shapes are
        # exercised independently in TestDigestReachesEveryRepoShape.
        result = _run_digest(ROOT)
        ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_additional_context_under_inline_limit(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        assert len(ctx) < ADDITIONAL_CONTEXT_INLINE_LIMIT, (
            f"digest is {len(ctx)} chars — over the {ADDITIONAL_CONTEXT_INLINE_LIMIT} "
            "inline threshold; Claude Code would spill it to a file"
        )

    def test_the_digest_source_is_under_the_inline_limit(self):
        """Pinned at the SOURCE, not only at whatever a given run emits.

        The sibling above asserts the EMITTED context is under the limit for one
        invocation; this asserts it of the shipped file itself, which is what
        every governed repo receives. The digest reached 11,143 chars (11% over)
        while only an emitted-value check existed, so the source-side pin is the
        one that has actually caught growth.

        Asserted against the stripped source because that is what the hook emits.
        """
        src = DIGEST_SRC
        emitted = src.read_text(encoding="utf-8").strip()
        assert len(emitted) < ADDITIONAL_CONTEXT_INLINE_LIMIT, (
            f"{src.name} is {len(emitted)} chars — over the "
            f"{ADDITIONAL_CONTEXT_INLINE_LIMIT} inline threshold; Claude Code "
            "would spill it to a file instead of injecting it. Trim or relocate; "
            "the digests are the tightest-budgeted surface in the framework, not "
            "a free destination for text trimmed out of a methodology guide."
        )

    def test_every_digest_section_carries_a_placement_decision(self):
        """A new section cannot appear without someone answering the question.

        The reserve above is the budget; this is the decision procedure that
        keeps the budget honest. Without it, relief gets done by whoever is
        closest to the wall in the moment they hit it -- which is the forced
        trim #630 names, and the condition under which a rule merge that is not
        a re-derivation looks like an ordinary edit.

        Reads the headings out of the digest itself rather than a list kept
        beside it: adding a section and forgetting the classification is the
        mistake being guarded, and a hand-kept list has that same blind spot.
        """
        headings = [
            ln[3:].strip()
            for ln in DIGEST_SRC.read_text(encoding="utf-8").splitlines()
            if ln.startswith("## ")
        ]
        assert headings, "no `## ` sections found -- the digest's shape changed"
        missing = [h for h in headings if h not in DIGEST_SECTION_PLACEMENT]
        assert not missing, (
            f"{missing} carry no placement decision. Classify each as "
            "must-be-inline (a thin-anchor repo is wrong without it) or "
            "relocatable, and say why, in DIGEST_SECTION_PLACEMENT."
        )
        dead = [
            h
            for h in DIGEST_SECTION_PLACEMENT
            if h not in headings and h != "(preamble)"
        ]
        assert not dead, (
            f"{dead} is classified but is no longer a digest section -- a "
            "stale entry reads as coverage of a decision nobody is making"
        )

    def test_the_digest_keeps_its_reserved_headroom(self):
        """The reserve is held, not merely available.

        The sibling above pins the hard harness threshold; this pins the policy
        one. Without it the reserve is a number in a comment, and a number in a
        comment is spent by the first author who does not read it -- which is
        the whole failure #630 records, one level up: the digest reached 13
        characters of headroom with every assertion green, because nothing
        asserted headroom, only the wall.

        Deliberately asserted on the SOURCE and not the emitted context: the
        reserve is a property of what every governed repo receives, and the
        emitted-value check is already the sibling's job.
        """
        emitted = DIGEST_SRC.read_text(encoding="utf-8").strip()
        budget = ADDITIONAL_CONTEXT_INLINE_LIMIT - DIGEST_HEADROOM_RESERVE
        assert len(emitted) <= budget, (
            f"{DIGEST_SRC.name} is {len(emitted)} chars, past the "
            f"{budget}-char working budget that reserves "
            f"{DIGEST_HEADROOM_RESERVE} characters for the next framework-wide "
            "default. This is not the harness wall -- it is the reserve, and "
            "spending it means doing the relief pass FIRST: classify a section "
            "as must-be-inline (a thin-anchor repo is wrong without it) or "
            "relocatable, move the relocatable one to a named on-demand "
            "surface with a stated retrieval path, and merge two rules only "
            "when re-derivation proves they were one."
        )

    def test_digest_points_at_load_bearing_readers(self):
        ctx = json.loads(_run_digest(ROOT).stdout)["hookSpecificOutput"]["additionalContext"]
        # The digest's job is to route to on-demand guidance and name the gate.
        assert "/prawduct:methodology building" in ctx, "must point to the read-before-coding guide"
        assert "/prawduct:methodology" in ctx, "must point to the methodology index"
        assert "Critic" in ctx and "Stop hook" in ctx, "must name the enforcement"

    def test_the_digest_carries_load_bearing_pointers(self):
        # Every session receives this file, so it must route to the
        # read-before-coding guide, the index, and name the enforcement.
        text = DIGEST_SRC.read_text(encoding="utf-8")
        assert "/prawduct:methodology building" in text
        assert "/prawduct:methodology" in text
        assert "Critic" in text and "Stop hook" in text

    def test_the_digest_states_where_project_memory_lives(self):
        """R10 (learnings v2): a framework-wide DEFAULT lands on the always-injected
        surface, because a place-once preference does not reach migrated repos.
        The harness's auto-memory must not hold project state or product rules;
        the repo's own files are authoritative."""
        digest = " ".join(DIGEST_SRC.read_text(encoding="utf-8").split())
        assert "auto-memory" in digest
        assert "`.claude/rules/learnings/` are authoritative" in digest

    def test_the_digest_surfaces_the_report_bug_channel(self):
        # Discoverability of the upstream-bug-reporting channel (regression guard
        # against a silent trim dropping the pointer). This one digest reaches
        # products (the filing side) and the framework repo (the receiving end).
        assert "/prawduct:report-bug" in DIGEST_SRC.read_text(encoding="utf-8")

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


class TestReloadSkills:
    """`reloadSkills` re-scans the skill directories at a session boundary.

    THE FAILURE THIS CLOSES IS SILENT, NOT SLOW. Claude Code caches skill bodies
    per session and `/clear` does not refresh them, so a session that edits
    `skills/*/SKILL.md` and then exercises that skill runs the PRE-EDIT body
    while believing it tests the new one. The work looks validated. Measured
    2026-08-02: a fork reported its own body matching a pre-edit commit
    byte-for-byte while HEAD carried the rewrite, and it cost #207 a designated
    acceptance test.

    Gated rather than unconditional. The re-scan buys nothing in a repo that
    never edits the plugin, and this hook fires in every governed repo — so a
    product session must not pay a directory walk for a defect it cannot have.
    """

    def _payload(self, plugin_root, project_dir=None):
        result = _run_digest(plugin_root, project_dir=project_dir)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["hookSpecificOutput"]

    def test_the_shipping_checkout_asks_for_the_rescan(self):
        # The default `_run_digest` shape IS the framework case: plugin root is
        # this repo's `plugin/`, project dir is this repo.
        out = self._payload(ROOT)
        assert out.get("reloadSkills") is True, (
            "the framework checkout did not request reloadSkills — a session "
            "that edits a skill here and then exercises it tests the previous "
            "version and cannot tell"
        )

    def test_a_product_repo_pays_nothing(self, tmp_path):
        # A governed repo that is NOT where this plugin lives: same plugin root,
        # a different project dir. This is every product session.
        (tmp_path / ".prawduct").mkdir()
        out = self._payload(ROOT, project_dir=tmp_path)
        assert out["additionalContext"].strip(), "the digest itself must still ship"
        assert "reloadSkills" not in out, (
            "a product repo was charged a skill-directory re-scan it cannot "
            "benefit from — it never edits the plugin"
        )

    def test_the_gate_is_structural_not_by_name(self, tmp_path):
        """A repo named `prawduct` that installed from the marketplace is a
        PRODUCT session, and a fork under any other name is not. So the question
        asked is "did this plugin come out of the repo I am governing?", which
        a name check answers wrong in both directions.
        """
        impostor = tmp_path / "prawduct"
        (impostor / ".prawduct").mkdir(parents=True)
        out = self._payload(ROOT, project_dir=impostor)
        assert "reloadSkills" not in out, (
            "the gate matched on the repo's NAME — an installed-from-the-"
            "marketplace repo that happens to be called prawduct is a product"
        )

    def test_a_nested_plugin_root_still_counts(self, tmp_path):
        """The plugin need not be the project dir, only inside it.

        A checkout is the shipping source when the plugin tree resolves under
        it — which is the `source: directory` install this repo uses, and which
        an equality-only check would answer `False` for.
        """
        repo = tmp_path / "checkout"
        (repo / ".prawduct").mkdir(parents=True)
        meth = repo / "plugin" / "methodology"
        meth.mkdir(parents=True)
        (meth / "session-digest.md").write_text("digest body\n", encoding="utf-8")
        out = self._payload(repo / "plugin", project_dir=repo)
        assert out.get("reloadSkills") is True

    def test_the_key_rides_the_same_boundaries_the_digest_does(self):
        """A refresh that fires only on `startup` would not fix this.

        The measured failure happens WITHIN a session -- edit, `/clear`,
        exercise -- so the registration has to cover `clear`, not just a cold
        start. The digest's matcher already does, and the key rides that same
        registration; this is the assertion that says the two cannot drift.
        """
        sessionstart = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
        entries = [
            e for e in sessionstart
            if any("digest.py" in h["command"] for h in e["hooks"])
        ]
        assert entries, "no digest SessionStart entry found"
        for entry in entries:
            assert "clear" in entry["matcher"], (
                "the digest hook stopped firing on `clear`, which is the "
                "boundary the skill-cache staleness is actually crossed at"
            )


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


class TestDigestReachesEveryRepoShape:
    """Repo shape does not select a digest: both shapes receive this one file.

    A per-shape variant is the change these pins exist to refuse. It trades one
    repository's duplication for a second shipped artifact every session of that
    shape carries, plus a must-agree pin per duplicated rule to stop the copies
    drifting. When a repo's own always-loaded CLAUDE.md overlaps the digest, the
    cheaper fix is to trim that CLAUDE.md.

    Both fixtures are exercised rather than one, because a single-shape test
    cannot see a divergence on the shape it does not run — the unrun path gets
    inferred, and an inference is what a pin is supposed to replace.
    """

    @staticmethod
    def _repo_fixture(tmp_path: Path, manifest: str | None = '{"name": "prawduct"}') -> Path:
        """A governed repo. With a prawduct plugin manifest it is the framework
        repo's shape; without one it is a product's."""
        # parents=True so a caller can build two fixtures under one tmp_path.
        (tmp_path / ".prawduct").mkdir(parents=True)
        if manifest is not None:
            mdir = tmp_path / ".claude-plugin"
            mdir.mkdir(parents=True)
            (mdir / "plugin.json").write_text(manifest, encoding="utf-8")
        return tmp_path

    def _emitted(self, project_dir: Path) -> str:
        result = _run_digest(ROOT, project_dir=project_dir)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_framework_fixture_gets_the_digest_verbatim(self, tmp_path):
        ctx = self._emitted(self._repo_fixture(tmp_path))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_product_fixture_gets_the_digest_verbatim(self, tmp_path):
        # A product repo (.prawduct/ but no plugin manifest). This is the path a
        # framework-only test cannot see, and the digest is the sole carrier of
        # framework defaults for a thin-anchor CLAUDE.md.
        ctx = self._emitted(self._repo_fixture(tmp_path, manifest=None))
        assert ctx == DIGEST_SRC.read_text(encoding="utf-8").strip()

    def test_both_shapes_receive_identical_context(self, tmp_path):
        """The positive form of the rule, so it cannot pass by both being empty.

        The two assertions above would each still hold if the digest were
        emptied; this states the property the collapse actually bought — the two
        shapes are indistinguishable at this surface — and pins it non-vacuously.
        """
        framework = self._emitted(self._repo_fixture(tmp_path / "fw"))
        product = self._emitted(self._repo_fixture(tmp_path / "prod", manifest=None))
        assert framework == product
        assert framework.strip(), "both shapes agreeing on an empty digest is not the contract"


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
        # The clear/briefing hook also fires on compact, but only through its
        # orientation-only registration: it resets session state, so it splits
        # boundary sources from continuations. The digest needs no such split —
        # it is pure guidance, so re-injecting it after a compaction is valuable
        # and costs nothing.
        entries = self._digest_entries(sessionstart)
        assert entries, "no digest SessionStart entry found"
        for e in entries:
            matcher = e["matcher"]
            for trigger in ("startup", "resume", "clear", "compact"):
                assert trigger in matcher, f"digest matcher should include {trigger!r}"

    def test_digest_does_not_clobber_banner_or_briefing(self, sessionstart):
        # Multiple SessionStart hooks compose; adding the digest must not drop the
        # version-delta banner or the clear briefing.
        cmds = [h["command"] for e in sessionstart for h in e["hooks"]]
        assert any("banner.py" in c for c in cmds)
        # The clear briefing now carries `--session-start` (CRT-3X9D guard bypass).
        assert any("bin/prawduct-hook" in c and "clear" in c.split() for c in cmds)


class TestReaderSkills:
    """prose-diet Chunk 03 folded the four thin delegator skills
    (skills/{building,discovery,planning,reflection}) into the methodology
    index — one reader skill, the canonical guides, zero duplicate routing
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

    def test_every_guide_is_named_at_all_four_routing_sites(self):
        """A topic is reachable only if all four surfaces name it.

        The index routes from four independent places — the frontmatter
        `description` and `argument-hint` (which is what a user sees before
        typing, and what the model matches on), the topic list the skill body
        dispatches from, and the overview's phase list (the only surface an
        agent that ran `/prawduct:methodology` bare will read). Adding a topic
        to three of the four is the predictable miss, and each omission fails
        differently: a missing `description` entry loses model invocation, a
        missing `argument-hint` entry loses discoverability, a missing topic-list
        line loses dispatch, and a missing overview line loses the agent who
        never passed an argument. Nothing else notices any of them, which is why
        this is asserted per site rather than by a single substring search over
        the file.
        """
        text = (ROOT / "skills" / "methodology" / "SKILL.md").read_text(encoding="utf-8")
        front, body = text.split("---", 2)[1], text.split("---", 2)[2]
        sites = {
            "frontmatter description": [
                ln for ln in front.splitlines() if ln.startswith("description:")],
            "argument-hint": [
                ln for ln in front.splitlines() if ln.startswith("argument-hint:")],
            "topic list": [
                ln for ln in body.splitlines()
                if ln.startswith("- `") and "→" in ln],
            "overview phase list": [
                ln for ln in body.splitlines()
                if ln.startswith("- `/prawduct:methodology ")],
        }
        for site, lines in sites.items():
            assert lines, f"the {site} routing site is gone from methodology/SKILL.md"
        missing = [
            f"{phase} @ {site}"
            for phase in PHASES
            for site, lines in sites.items()
            if not any(phase in ln for ln in lines)
        ]
        assert not missing, (
            "methodology/SKILL.md does not name every guide at every routing "
            f"site: {missing}"
        )

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
