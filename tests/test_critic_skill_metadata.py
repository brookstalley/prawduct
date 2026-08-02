"""Critic skill metadata tests — structural enforcement of "no test execution"
and "no working-tree mutation".

The recurring failure mode (memory rule `feedback_critic_no_test_execution.md`)
is "Critic invokes pytest despite prose forbidding it." Prose alone doesn't hold
under load. The REAL structural block is the pure-allow `allowed-tools` list: no
allow pattern matches a pytest invocation (`test_no_allow_pattern_permits_pytest`,
CRT-8H3D). The `!Bash(...pytest*)` deny entries are kept as belt-and-suspenders
documentation and still asserted present, but skill-frontmatter `!`-deny is not
reliably honored by the harness, so they are not the mechanism. Git is likewise
restricted to read-only verbs so a review can't mutate the tree (CRT-2M5P).
Drift in the plugin-distributed Critic skill fails loud.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1] / "plugin"

# Critic skill surface that must carry the structural safety set (pure-allow deny
# set, read-only git verbs only). Chunk 13 removed the legacy framework
# `.claude/skills/critic/SKILL.md` (this repo is now governed by the plugin) and
# retired the `critic-test` shadow skill; M4 Chunk 4 deleted the file-sync product
# template (`templates/skill-critic.md`) when the engine retired. The plugin-
# distributed skill is the sole surviving surface — its runtime-hook invocations
# call the bundled `prawduct-hook …` (Chunk 5 repoint).
_PLUGIN_CRITIC_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"
CRITIC_SKILL_SURFACES = [_PLUGIN_CRITIC_SKILL]

# The same read-only-git constraint (CRT-2M5P) applies to every Critic surface.
GIT_READONLY_SURFACES = CRITIC_SKILL_SURFACES

REQUIRED_DENY_PATTERNS = [
    "!Bash(pytest*)",
    "!Bash(python -m pytest*)",
    "!Bash(python3 -m pytest*)",
    "!Bash(* python -m pytest*)",
]


def _extract_allowed_tools(content: str) -> str:
    """Return the verbatim `allowed-tools:` value from a skill's frontmatter."""
    m = re.search(r"^allowed-tools:\s*(.+)$", content, re.MULTILINE)
    assert m is not None, "skill missing `allowed-tools:` frontmatter field"
    return m.group(1).strip()


class TestCriticSkillDenyPatterns:
    """Both Critic skill surfaces must structurally deny pytest invocations."""

    def test_plugin_skill_has_all_deny_patterns(self):
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        for pat in REQUIRED_DENY_PATTERNS:
            assert pat in allowed, (
                f"plugin skills/critic/SKILL.md is missing deny pattern `{pat}` "
                f"in allowed-tools"
            )

    def test_existing_legitimate_tools_preserved(self):
        """The deny additions must not accidentally drop existing allows.

        The plugin Critic surface calls the bundled `prawduct-hook …` runtime
        (Chunk 5 repoint, replacing the retired `python3 tools/product-hook …`)."""
        expected = [
            "Read", "Glob", "Grep", "Bash(wc *)", "Write", "Agent",
            "Bash(prawduct-hook test-status)",
            "Bash(prawduct-hook infer-critic-mode *)",
        ]
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        for tool in expected:
            assert tool in allowed, (
                f"{_PLUGIN_CRITIC_SKILL.relative_to(REPO_ROOT)} dropped legitimate "
                f"tool `{tool}` from allowed-tools"
            )

    def test_verify_chunk_refs_grant_is_retired(self):
        """`verify-chunk-refs` left this list on purpose, not by accident.

        The chunk-deliverable check now runs at DISPATCH (`critic-begin`
        computes it into the manifest's `record_lint` block), and
        `review-protocol.md` tells reviewers to read that result rather than
        re-derive it. A standing grant for a command no instruction issues is a
        mechanism's name outliving its mechanism — and re-running it by hand is
        precisely the duplicated work the dispatch-time move removed. The
        assertion is here rather than the entry merely being deleted above so a
        future re-add has to argue with a stated decision instead of silently
        restoring a line that looks like an oversight."""
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        assert "verify-chunk-refs" not in allowed
        assert "critic-begin" in allowed, "dispatch is where the check now runs"

    def test_git_is_read_only(self):
        """CRT-2M5P: the Critic must NOT have the broad `Bash(git *)` allow —
        it let a review run `git checkout` and corrupt the working tree. Git is
        restricted to read-only verbs."""
        readonly_verbs = [
            "Bash(git diff *)",
            "Bash(git log *)",
            "Bash(git status *)",
            "Bash(git show *)",
            "Bash(git rev-parse *)",
            "Bash(git merge-base *)",
        ]
        for surface in GIT_READONLY_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            assert "Bash(git *)" not in allowed, (
                f"{surface.relative_to(REPO_ROOT)} still grants broad `Bash(git *)` "
                f"— it permits state-mutating verbs (checkout/reset/stash). Use "
                f"explicit read-only verbs (CRT-2M5P)."
            )
            for verb in readonly_verbs:
                assert verb in allowed, (
                    f"{surface.relative_to(REPO_ROOT)} missing read-only git verb "
                    f"`{verb}`"
                )

    def test_no_allow_pattern_permits_pytest(self):
        """CRT-8H3D: the real, structural pytest block is the PURE-ALLOW list —
        the `!Bash(...pytest*)` deny entries are documented as non-functional
        (skill-frontmatter `!`-deny isn't reliably honored). This is the
        negative-path probe that backs that claim: no ALLOW pattern may match a
        pytest invocation."""
        import fnmatch

        pytest_cmds = [
            "pytest",
            "python -m pytest",
            "python3 -m pytest tests/",
            "cd foo && python3 -m pytest",
        ]
        for surface in CRITIC_SKILL_SURFACES:
            allowed = _extract_allowed_tools(surface.read_text())
            allow_patterns = [
                entry.strip()[len("Bash("):-1]
                for entry in allowed.split(",")
                if entry.strip().startswith("Bash(") and entry.strip().endswith(")")
            ]
            for cmd in pytest_cmds:
                for pat in allow_patterns:
                    assert not fnmatch.fnmatch(cmd, pat), (
                        f"{surface.relative_to(REPO_ROOT)}: allow pattern "
                        f"`Bash({pat})` would permit `{cmd}` — pytest is not "
                        f"structurally blocked by the allow-list"
                    )



class TestExplicitModeArgContract:
    """CRT-2N7V: Skill-tool invocation of a fork-context skill does not
    substitute `$ARGUMENTS` (anthropics/claude-code#34164), so the SKILL must
    never parse the placeholder itself — it forwards whatever arguments were
    delivered to `prawduct-hook infer-critic-mode`, which owns the full
    precedence (explicit token > plan-override > inference) and returns
    rationale `explicit-args` for a recognized forwarded token. These pins
    keep the prose contract from regressing to self-parsing."""

    def test_exactly_one_substitution_placeholder(self):
        """One labeled placeholder line. More would garble sentences when
        substitution DOES fire (all occurrences are replaced — a precedence
        parenthetical containing the placeholder once read 'explicit `chunk`'
        after substitution); zero would switch delivery to the auto-append
        path, whose fork behavior is unverified."""
        content = _PLUGIN_CRITIC_SKILL.read_text()
        assert content.count("$ARGUMENTS") == 1
        assert '**Invocation arguments:** "$ARGUMENTS"' in content

    def test_step1_forwards_to_helper_not_self_parses(self):
        content = _PLUGIN_CRITIC_SKILL.read_text()
        # The forwarding instruction and the helper invocation are present...
        assert "infer-critic-mode <args" in content
        assert "Do NOT interpret the arguments yourself" in content
        # ...and the known harness limitation travels with the contract.
        assert "34164" in content
        # The old self-parse instruction must not return: the only line
        # mentioning the placeholder is the labeled one (asserted above), so
        # an "If `$ARGUMENTS` contains a recognized mode token" revival would
        # bump the count and fail test_exactly_one_substitution_placeholder.

    def test_helper_wildcard_still_in_allowed_tools(self):
        """Forwarding needs the wildcarded allow entry — the bare
        `Bash(prawduct-hook infer-critic-mode)` form would reject the
        argument-carrying invocation."""
        allowed = _extract_allowed_tools(_PLUGIN_CRITIC_SKILL.read_text())
        assert "Bash(prawduct-hook infer-critic-mode *)" in allowed


_PLUGIN_REVIEW_PROTOCOL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"


class TestCoordinatorDispatchIsConcurrent:
    """The three coordinator reviewers go out in ONE message, each synchronous.

    The two halves are independent and neither substitutes for the other, which
    is why both are pinned on both surfaces:

    * **One message** buys concurrency. The reviewers are independent by
      construction — disjoint goals, per-role partial files — so serial
      dispatch pays the pattern's whole cost (three agents, three context
      loads, a consolidation step) and discards the wall-clock saving that is
      the only thing it buys.
    * **`run_in_background: false`** buys the await, and it is the fix for the
      defect this pattern shipped with: a backgrounded dispatch returns the
      coordinator to a turn holding 0/3 partials with nothing to report, so the
      invoking session sees a review that "ran and came back empty" and cannot
      tell a healthy review from a dead one. Synchronous dispatch does not
      serialise them — the harness's Agent tool is concurrency-safe, so one
      message of synchronous calls still overlaps.

    Neither was ever specified: the framework relied on the harness's ambient
    defaults, which are outside its control (the background default is what bit
    us) and have been observed to differ between sessions. An unpinned
    instruction is how it silently reverts, so both dispatch surfaces are
    asserted for both halves.
    """

    def test_review_protocol_step_2_demands_one_message(self):
        content = _PLUGIN_REVIEW_PROTOCOL.read_text()
        assert "ONE message" in content
        assert "concurrently" in content

    def test_skill_routing_bullet_demands_one_message(self):
        content = _PLUGIN_CRITIC_SKILL.read_text()
        assert "in a single message so they run concurrently" in content

    def test_review_protocol_step_2_demands_synchronous_dispatch(self):
        content = _PLUGIN_REVIEW_PROTOCOL.read_text()
        assert "`run_in_background: false`" in content, (
            "review-protocol.md's Coordinator Pattern must name "
            "`run_in_background: false` — without it the coordinator returns "
            "holding zero partials, which is the defect the pattern shipped with"
        )

    def test_skill_routing_bullet_demands_synchronous_dispatch(self):
        content = _PLUGIN_CRITIC_SKILL.read_text()
        assert "`run_in_background: false`" in content, (
            "the SKILL routing bullet must name `run_in_background: false` too "
            "— it is the surface the coordinator acts on, and an instruction "
            "pinned on only one of two surfaces drifts"
        )

    def test_protocol_owns_the_sequence_and_the_skill_only_points_at_it(self):
        """The split this pair of surfaces settles on, pinned so it cannot drift.

        The two *dispatch flags* above are deliberately asserted twice — they
        are single tokens that revert silently and cost a whole review when
        they do. The *sequence* (wait → consolidate → report) is not: it has
        one home, `review-protocol.md`'s Coordinator Pattern, which SKILL step
        2 has already made every `final`/`cumulative` reviewer open before it
        can reach the routing bullet.

        Asserted as an absence on the SKILL side because that is the direction
        this drifts: the coordinator bullet accreted the full contract once
        already (92 → 131 words) and read perfectly well, which is exactly why
        nothing but a test catches it. `architecture.md`'s one-home norm is the
        authority — if changing the sequence needs two edits, one of them is
        already wrong.
        """
        protocol = _PLUGIN_REVIEW_PROTOCOL.read_text()
        assert "prawduct-hook critic-consolidate" in protocol
        assert "final message" in protocol

        bullet = (
            _PLUGIN_CRITIC_SKILL.read_text()
            .split("(coordinator)**", 1)[1]
            .split("\n\n", 1)[0]
        )
        assert "Coordinator Pattern" in bullet, (
            "the SKILL coordinator bullet must route to the protocol section "
            "that owns the sequence"
        )
        assert "critic-consolidate" not in bullet, (
            "the SKILL coordinator bullet restates the consolidate step — that "
            "is review-protocol.md's to own. Point at the Coordinator Pattern "
            "instead; only the two dispatch flags are pinned on both surfaces"
        )
